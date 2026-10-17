"""
FPV + BEV ego video recording for CARLA examples (ScenarioRunner external-control).

Copy of ChatScene-main/safebench/agent/osc_ego_recorder.py for use from PythonAPI/examples.
"""

from __future__ import annotations

import os
import queue
import shutil
import subprocess
import threading
import time
from datetime import datetime
from typing import Any, Dict, Optional


def check_ffmpeg_available() -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "ffmpeg not found on PATH. Install ffmpeg to use --record "
            "(e.g. apt install ffmpeg)."
        )


class AsyncFFmpegWriter:
    def __init__(self, out_path: str, w: int, h: int, fps: int, crf: int = 23, qsize: int = 96):
        self.q: queue.Queue = queue.Queue(maxsize=qsize)
        self.proc = subprocess.Popen(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "bgra",
                "-s",
                f"{w}x{h}",
                "-r",
                str(fps),
                "-i",
                "-",
                "-an",
                "-c:v",
                "libx264",
                "-crf",
                str(crf),
                "-pix_fmt",
                "yuv420p",
                out_path,
            ],
            stdin=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        self.running = True
        self.n_queued = 0
        self.n_written = 0
        self.blocked_seconds = 0.0
        self._frame_interval = 1.0 / fps
        self._start_wall = None
        self._frames_emitted = 0
        self._last_raw: Optional[bytes] = None
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def write(self, raw: bytes) -> None:
        # Blocking put: a scripted-scenario recording has no real-time
        # deadline to meet, so backpressuring the caller when the encoder
        # falls behind is correct. The previous put_nowait/except queue.Full
        # silently dropped frames under load; that's fixed here, but it
        # turned out not to be the actual cause of sped-up recordings (see
        # submit() below) — measured queue drops were zero even before this
        # fix mattered in practice for a 3-camera ScenarioRunner run.
        t0 = time.monotonic()
        self.q.put(raw)
        blocked = time.monotonic() - t0
        if blocked > 0.001:
            self.blocked_seconds += blocked
        self.n_queued += 1

    def submit(self, raw: bytes, clock: float) -> None:
        """
        Pace output to elapsed time on `clock` instead of trusting the camera
        to actually deliver at the requested sensor_tick rate.

        `clock` is the SIMULATION timestamp in synchronous mode and the wall
        clock otherwise (see EgoVideoRecorder._use_sim_clock). In sync mode the
        server renders every fixed tick before returning, so with
        sensor_tick == fixed_delta_seconds and fps == 1/fixed_delta_seconds
        `due` advances exactly one per delivered frame and the duplicate path
        below never runs — every output frame is a real, distinct render and
        playback duration equals simulated duration.

        Measured: 3 simultaneous 1280x720 cameras under -RenderOffScreen
        deliver at ~6 Hz against a 15 Hz sensor_tick request — CARLA's
        renderer just can't keep up within the synchronous-mode tick budget.
        The output pipe is raw video muxed at a fixed -r fps with no
        per-frame timestamps, so writing exactly one output frame per
        received image made a 20 s drive with ~125 delivered frames encode
        as a ~8 s clip (125 / 15 fps) — this was the entire "sped up and cut
        off" bug, not queue drops or the stdin-close race (both measured at
        zero loss). Duplicating the most recently received frame to fill
        the gap keeps output frame count, and therefore playback duration,
        tied to real elapsed time regardless of how sparse capture is.
        """
        if self._start_wall is None:
            self._start_wall = clock
        due = int((clock - self._start_wall) / self._frame_interval) + 1
        while self._frames_emitted < due - 1 and self._last_raw is not None:
            self.write(self._last_raw)
            self._frames_emitted += 1
        self.write(raw)
        self._frames_emitted += 1
        self._last_raw = raw

    def _worker(self) -> None:
        while self.running:
            item = self.q.get()
            if item is None:
                break
            try:
                if self.proc.stdin:
                    self.proc.stdin.write(item)
                    self.n_written += 1
            except Exception:
                break

    def close(self) -> None:
        self.running = False
        try:
            self.q.put_nowait(None)
        except Exception:
            pass
        # Join the worker before touching stdin, so every frame already
        # queued at stop() time is written before the pipe closes. Closing
        # stdin concurrently with the worker (the previous behavior) raced
        # it: a write to the now-closed pipe throws, is swallowed, and the
        # worker exits — silently dropping whatever was still queued, which
        # is what cut recordings off before the scenario actually ended.
        self._thread.join(timeout=30)
        try:
            if self.proc.stdin:
                self.proc.stdin.close()
            self.proc.wait(timeout=5)
        except Exception:
            pass


class EgoVideoRecorder:
    """Records FPV (attached) and BEV (top-down follow) to MP4 via ffmpeg."""

    def __init__(
        self,
        carla_mod: Any,
        world: Any,
        ego: Any,
        outdir: str,
        prefix: str,
        *,
        fps: int = 15,
        width: int = 1280,
        height: int = 720,
        bev_height: float = 50.0,
    ):
        self._carla = carla_mod
        self._world = world
        self._ego = ego
        self._outdir = outdir
        self._prefix = prefix
        self._fps = fps
        self._width = width
        self._height = height
        self._bev_height = bev_height

        self._writers: Dict[str, AsyncFFmpegWriter] = {}
        self._cams: Dict[str, Any] = {}
        self._active = False
        self.scene_dir: Optional[str] = None
        self._map_name: Optional[str] = None
        self._timestamp: Optional[str] = None
        self._capture_stats: Dict[str, Dict[str, Any]] = {}
        # Set in start(): true when the world is synchronous, which makes the
        # simulation timestamp a sound pacing clock (see AsyncFFmpegWriter.submit).
        self._use_sim_clock = False

    @property
    def active(self) -> bool:
        return self._active

    def _outpath(self, view: str) -> str:
        assert self._map_name is not None and self._timestamp is not None
        return os.path.join(
            self.scene_dir,
            f"{self._prefix}__{self._map_name}__{view}__{self._timestamp}.mp4",
        )

    def start(self) -> str:
        if self._active:
            return self.scene_dir or ""

        check_ffmpeg_available()

        map_name = self._world.get_map().name.split("/")[-1]
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")[:-3]
        scene_dir = os.path.join(self._outdir, f"{self._prefix}__{map_name}__{timestamp}")
        os.makedirs(scene_dir, exist_ok=True)

        self._map_name = map_name
        self._timestamp = timestamp
        self.scene_dir = scene_dir

        rel_fpv = self._carla.Transform(
            self._carla.Location(1.6, -0.25, 1.35),
            self._carla.Rotation(pitch=-5),
        )

        # In synchronous mode, capture exactly one frame per simulation tick.
        # A sensor_tick that is not a multiple of fixed_delta_seconds makes the
        # camera fire on some ticks and not others (1/15 s against a 1/20 s tick
        # fires every 2nd tick = 10 Hz), which the pacing logic then has to pad
        # back up to the requested fps with duplicates. Matching the two removes
        # the mismatch instead of papering over it.
        settings = self._world.get_settings()
        sensor_tick = 1.0 / self._fps
        if getattr(settings, "synchronous_mode", False) and settings.fixed_delta_seconds:
            sensor_tick = settings.fixed_delta_seconds
            self._fps = int(round(1.0 / settings.fixed_delta_seconds))
            self._use_sim_clock = True
            print(f"[RECORD] sync mode: {self._fps} fps, one frame per "
                  f"{settings.fixed_delta_seconds:.4f}s tick", flush=True)
        else:
            print(f"[RECORD] async mode: requesting {self._fps} fps — actual capture "
                  f"rate depends on render load, gaps padded with duplicate frames",
                  flush=True)

        bp = self._world.get_blueprint_library().find("sensor.camera.rgb")
        bp.set_attribute("image_size_x", str(self._width))
        bp.set_attribute("image_size_y", str(self._height))
        bp.set_attribute("sensor_tick", str(sensor_tick))
        bp.set_attribute("fov", "110")

        def on_image(img: Any, view: str) -> None:
            now = time.monotonic()
            stats = self._capture_stats[view]
            stats["n"] += 1
            stats["last_wall"] = now
            stats["last_sim"] = img.timestamp
            if stats["first_wall"] is None:
                stats["first_wall"] = now
                stats["first_sim"] = img.timestamp
            writer = self._writers.get(view)
            if writer is not None:
                writer.submit(img.raw_data, img.timestamp if self._use_sim_clock else now)

        def spawn_cam(view: str, tf: Any, attach_to: Any = None) -> None:
            self._capture_stats[view] = {
                "n": 0, "first_wall": None, "last_wall": None,
                "first_sim": None, "last_sim": None,
            }
            self._writers[view] = AsyncFFmpegWriter(
                self._outpath(view), self._width, self._height, self._fps
            )
            if attach_to is None:
                cam = self._world.spawn_actor(bp, tf)
            else:
                cam = self._world.spawn_actor(bp, tf, attach_to=attach_to)
            cam.listen(lambda img, v=view: on_image(img, v))
            self._cams[view] = cam

        ego_tf = self._ego.get_transform()
        spawn_cam("FPV", rel_fpv, attach_to=self._ego)
        spawn_cam(
            "THD",
            self._carla.Transform(
                self._carla.Location(-6.0, 0.0, 3.0),
                self._carla.Rotation(pitch=-12.0),
            ),
            attach_to=self._ego,
        )
        spawn_cam(
            "BEV",
            self._carla.Transform(
                self._carla.Location(
                    ego_tf.location.x,
                    ego_tf.location.y,
                    ego_tf.location.z + self._bev_height,
                ),
                self._carla.Rotation(pitch=-90),
            ),
        )

        self._active = True
        print(f"[RECORD] started -> {scene_dir}", flush=True)
        return scene_dir

    def update_bev(self) -> None:
        if not self._active or "BEV" not in self._cams:
            return
        tf = self._ego.get_transform()
        self._cams["BEV"].set_transform(
            self._carla.Transform(
                self._carla.Location(
                    tf.location.x,
                    tf.location.y,
                    tf.location.z + self._bev_height,
                ),
                self._carla.Rotation(pitch=-90),
            )
        )

    def stop(self) -> None:
        if not self._active and not self._cams and not self._writers:
            return

        for cam in list(self._cams.values()):
            try:
                cam.stop()
                cam.destroy()
            except Exception:
                pass
        self._cams.clear()

        for view, writer in list(self._writers.items()):
            try:
                writer.close()
            except Exception:
                pass
        self._writers.clear()

        if self._active and self.scene_dir:
            print(f"[RECORD] saved to {self.scene_dir}", flush=True)
        self._active = False
