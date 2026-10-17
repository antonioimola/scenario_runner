#!/usr/bin/env python3
"""
run_selfref_video_test.py — Run a self-referencing SpeedAction/LaneChangeAction
.xosc test scenario in CARLA via this repo's own scenario_runner.py, and record
FPV/THD/BEV video of the ego ("hero") vehicle via osc_ego_recorder.EgoVideoRecorder.

This is Antonio's own copy (SCENARIO_RUNNER_ROOT below points at this fork, not
yungloon's scenario_runner-0.9.15) so it can be patched without touching another
user's directory. osc_ego_recorder.py lives next to this script and is imported
from there (no sys.path insert needed — the script's own directory is on
sys.path[0] automatically).

Prerequisites (run in the same shell before this script, or via run.sh):
  export CARLA_ROOT=/home/dellpro2/yungloon/carla-0.9.15   # shared CARLA install/client lib
  export PYTHONPATH="$CARLA_ROOT/PythonAPI/carla:$PYTHONPATH"
  # CARLA server already running, e.g. on port 2010

Usage:
  python3 scripts/run_selfref_video_test.py Debug/selfref_tests/test_speed_selfref.xosc
  python3 scripts/run_selfref_video_test.py Debug/selfref_tests/test_lanechange_selfref_negative.xosc --port 2010
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

SCENARIO_RUNNER_ROOT = "/home/dellpro2/Antonio/scenario_runner"

try:
    import carla
except ImportError:
    sys.exit(
        "ERROR: could not import carla. Did you set CARLA_ROOT and PYTHONPATH "
        "to a CARLA 0.9.15 PythonAPI/carla directory? (see run.sh)"
    )

from osc_ego_recorder import EgoVideoRecorder


def wait_for_hero(world, role="hero", timeout=2.0, poll=0.05):
    # poll defaults to 0.05s, not the old 0.5s: in --sync mode scenario_runner
    # is the sole tick-driver and races ahead unencumbered by render cost until
    # a camera actually attaches (see EgoVideoRecorder.start()), so every
    # real-time second spent polling here is sim-time the recording never
    # captures. A 0.5s poll (plus a 1.0s sleep per RuntimeError from the
    # --reloadWorld transition, in the caller below) measured losing 2-3s of
    # sim-time before recording started. get_actors() is a cheap, uncomputed
    # lookup, so a tight interval here is safe — this mirrors the poll-don't-
    # block-on-tick pattern tests/carla_telemetry.py already uses for the same
    # reason (role_name isn't on the on_tick snapshot, and issuing a blocking
    # RPC from inside the tick callback thread is the thing to avoid, not
    # polling frequently from the main thread).
    deadline = time.time() + timeout
    while time.time() < deadline:
        for actor in world.get_actors().filter("vehicle.*"):
            if actor.attributes.get("role_name") == role:
                return actor
        time.sleep(poll)
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("xosc", help="Path to .xosc scenario file")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", default=2010, type=int)
    ap.add_argument("--tm-port", default=None, type=int,
                    help="Traffic Manager port (default: first free port from 8000)")
    ap.add_argument("--timeout", default=120, type=int, help="scenario_runner --timeout (s)")
    ap.add_argument("--sync", action="store_true",
                    help="run scenario_runner in synchronous mode (fixed 1/20 s tick). "
                         "Required for a dropped-frame-free recording: async lets the "
                         "server free-run, so camera delivery falls below the requested "
                         "rate under load and the recorder pads with duplicate frames.")
    ap.add_argument("--spawn-timeout", default=90.0, type=float,
                     help="max seconds to wait for hero to spawn before giving up")
    ap.add_argument("--outdir", default="Debug/selfref_tests/videos")
    ap.add_argument("--prefix", default=None, help="video filename prefix (default: xosc stem)")
    ap.add_argument("--bg-traffic", default=None,
                    help="background traffic to replay beside the scenario (a .bgtraffic.json "
                         "exported by the scenario editor); run.sh passes it when one sits next "
                         "to the .xosc")
    ap.add_argument("--bg-traffic-player",
                    default="/home/dellpro2/Antonio/scenario_editor/tools/bg_traffic_player.py",
                    help="the scenario editor's puppet player script")
    args = ap.parse_args()

    xosc_path = Path(args.xosc).resolve()
    if not xosc_path.exists():
        sys.exit(f"ERROR: {xosc_path} not found")

    prefix = args.prefix or xosc_path.stem
    outdir = Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    tm_port = args.tm_port
    if tm_port is None:
        # scenario_runner's default 8000 is often held by another CARLA client
        # (or a stale TM), which makes get_trafficmanager() fail with a bind error.
        import socket
        for tm_port in range(8000, 8100):
            with socket.socket() as s:
                try:
                    s.bind(("0.0.0.0", tm_port))
                    break
                except OSError:
                    continue

    cmd = [
        sys.executable, "scenario_runner.py",
        "--trafficManagerPort", str(tm_port),
        "--openscenario", str(xosc_path),
        "--host", args.host,
        "--port", str(args.port),
        # No --reloadWorld: OpenScenarioConfiguration.__init__ (via
        # _set_carla_town, srunner/scenarioconfigs/openscenario_configuration.py)
        # unconditionally checks the current map against the .xosc's
        # <RoadNetwork> and calls client.load_world() itself whenever they
        # differ -- this runs BEFORE scenario_runner.py's own
        # _load_and_wait_for_world, which --reloadWorld would otherwise make
        # do the exact same client.load_world() call a second time.
        # Measured: two full ~1.5s map loads back to back cost ~3s of
        # sim-time before recording could start, all lost since no camera
        # exists yet to capture it. Dropping --reloadWorld keeps the
        # reload-on-mismatch guarantee (still handled by _set_carla_town)
        # while cutting the redundant second load -- and a repeat run on the
        # same town now reloads zero times instead of twice.
        "--timeout", str(args.timeout),
        "--output",
    ]
    if args.sync:
        cmd.append("--sync")
    print(f"[run_selfref_video_test] launching: {' '.join(cmd)}  (cwd={SCENARIO_RUNNER_ROOT})")
    proc_started = time.time()
    proc = subprocess.Popen(cmd, cwd=SCENARIO_RUNNER_ROOT)

    # Background traffic: a second client that only listens to ticks and moves
    # its own physics-off cars (it never ticks). Started now so it sees the
    # hero's first tick, which is its time zero.
    bg_proc = None
    if args.bg_traffic:
        bg_cmd = [sys.executable, args.bg_traffic_player, str(Path(args.bg_traffic).resolve()),
                  "--host", args.host, "--port", str(args.port)]
        print(f"[run_selfref_video_test] background traffic: {' '.join(bg_cmd)}")
        bg_proc = subprocess.Popen(bg_cmd)

    client = carla.Client(args.host, args.port)
    client.set_timeout(30.0)

    recorder = None
    returncode = None
    try:
        print("[run_selfref_video_test] waiting for hero vehicle to spawn ...")
        hero = None
        world = None
        deadline = time.time() + args.spawn_timeout
        while time.time() < deadline and proc.poll() is None:
            try:
                world = client.get_world()
                hero = wait_for_hero(world)
            except RuntimeError:
                # --reloadWorld reliably throws exactly one RuntimeError here
                # while the map swap is in flight; the old 1.0s sleep was
                # itself a meaningful chunk of the missing-first-seconds gap
                # once --sync stopped padding the rest with duplicate frames.
                time.sleep(0.1)
                continue
            if hero is not None:
                break

        if hero is None:
            print("[run_selfref_video_test] ERROR: hero never spawned "
                  "(scenario_runner may have exited early — check its output above).")
            if proc.poll() is None:
                proc.terminate()
            proc.wait(timeout=15)
            sys.exit(1)

        try:
            sim_t = world.get_snapshot().timestamp.elapsed_seconds
        except RuntimeError:
            sim_t = None
        print(f"[run_selfref_video_test] hero found: id={hero.id} type={hero.type_id} "
              f"sim_elapsed={sim_t if sim_t is None else f'{sim_t:.2f}s'} "
              f"wall_elapsed={time.time() - proc_started:.2f}s")
        recorder = EgoVideoRecorder(carla, world, hero, str(outdir), prefix)
        scene_dir = recorder.start()
        print(f"[run_selfref_video_test] recording FPV/THD/BEV -> {scene_dir}")

        while proc.poll() is None:
            try:
                recorder.update_bev()
            except RuntimeError:
                break
            time.sleep(0.1)

        returncode = proc.wait(timeout=30)
        print(f"[run_selfref_video_test] scenario_runner exited with code {returncode}")

    finally:
        if bg_proc is not None:
            if bg_proc.poll() is None:
                bg_proc.terminate()     # the player destroys its cars on SIGTERM
            try:
                bg_proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                bg_proc.kill()
        if recorder is not None:
            recorder.stop()
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()

    sys.exit(0 if returncode == 0 else 1)


if __name__ == "__main__":
    main()
