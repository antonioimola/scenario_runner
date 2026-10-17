# CARLA Scenario Runner — Supported Formats & CARLA Leaderboard

---

## Overview

The scenario runner supports three scenario formats. Each serves a different purpose:

| | OpenSCENARIO (`.xosc`) | Python Native | Route-Based (Leaderboard) |
|---|---|---|---|
| **Standard** | ASAM international standard | CARLA-specific | CARLA Leaderboard |
| **Ego control** | External (e.g. Autoware, E2E model) | CARLA built-in autopilot or external | External agent (Autoware, E2E model) — mandatory |
| **Actor logic** | XML storyboard | py_trees behavior tree | py_trees behavior tree |
| **Trigger** | Condition-based (speed, distance, time) | Condition-based | GPS waypoint proximity |
| **Pass/Fail criteria** | Defined in `.xosc` | Defined in Python class | Fixed criteria set |
| **Best for** | Standardized, portable testing | Custom CARLA-specific logic | Benchmarking autonomous driving stacks |

---

## Ego Control — Explained

The "ego vehicle" is the vehicle under test — the one your autonomous driving stack is responsible for driving. How it is controlled differs across formats:

### OpenSCENARIO (`.xosc`) — External controller required
The ego is assigned `external_control` inside the `.xosc` file:
```xml
<Controller name="HeroAgent">
  <Properties>
    <Property name="module" value="external_control"/>
  </Properties>
</Controller>
```
This means the scenario runner **does not drive the ego at all** — it only spawns it and hands control to whatever external system is connected. In this repo that is **Autoware**, connected via `op_bridge`. It could equally be an **end-to-end neural network** or any ROS2-based planner. The scenario runner only controls the adversary actors (cyclist, pedestrian, NPC vehicles).

### Python Native — Built-in autopilot available
Python scenarios can either:
- Use **CARLA's built-in Traffic Manager autopilot** to drive the ego automatically (good for quick tests where you don't care about the planner)
- Or connect an **external controller** the same way as `.xosc` via `--waitForEgo`

The built-in autopilot is CARLA's own rule-based driver — it is not a real autonomous driving stack, just enough to keep the car moving for testing purposes.

### Route-Based (Leaderboard) — External agent mandatory
An agent is always **required** — there is no built-in fallback. The agent is passed explicitly:
```bash
python3 leaderboard_evaluator.py \
    --agent op_bridge/op_ros2_agent.py \   # ← must provide this
    --routes routes_devtest.xml \
    --scenarios all_towns_traffic_scenarios_public.json
```
The `op_ros2_agent.py` in this repo bridges CARLA sensor data into ROS2 topics so Autoware can subscribe to them, and forwards Autoware's control commands back to CARLA. An **end-to-end model** (e.g. CARLA's own Transfuser, InterFuser, or a custom model) could be dropped in here instead — which is exactly why the Leaderboard was designed: to benchmark and compare different autonomous driving approaches under the same set of scenarios and scoring criteria.

---

## Format 1 — OpenSCENARIO (`.xosc`)

### What it is
The international ASAM standard for describing traffic scenarios. Scenarios are written in XML and define all actors, their initial positions, triggering conditions, and actions in a hierarchical **storyboard**.

### Storyboard hierarchy

Every `.xosc` file is structured in the same way:

```
OpenSCENARIO
├── Entities          ← define all actors (ego + adversaries)
└── Storyboard
    ├── Init          ← set starting positions and environment
    ├── Story         ← top-level grouping (one per scenario)
    │   └── Act       ← a phase of the scenario, has its own start/stop trigger
    │       └── ManeuverGroup   ← which actors are involved
    │           └── Maneuver    ← a sequence of events
    │               └── Event   ← triggered by a condition
    │                   └── Action  ← what the actor does
    └── StopTrigger   ← global end condition (pass/fail criteria)
```

#### Real example — `CyclistCrossing.xosc`

This scenario has one story with 4 sequential events. Each event is triggered by a condition on the previous one:

```
Story: MyStory
└── Act: Behavior
    │   StartTrigger: hero travels 10m
    │   StopTrigger:  hero travels 200m
    │
    └── Maneuver: CyclistCrossingManeuver
        │
        ├── Event: CyclistStartsWalking
        │   Trigger:  hero distance to adversary < 14m   ← ego gets close
        │   Action:   adversary speed = 2.0 m/s          ← cyclist starts moving
        │
        ├── Event: CyclistStopsAndWaits
        │   Trigger:  adversary standstill + CyclistStartsWalking completed
        │   Action:   adversary speed = 0.0              ← cyclist stops in road
        │
        ├── Event: CyclistWalksAway
        │   Trigger:  hero standstill + CyclistStopsAndWaits completed
        │   Action:   adversary speed = 2.0 m/s          ← cyclist moves away
        │
        └── Event: CyclistWaits
            Trigger:  adversary standstill + CyclistWalksAway completed
            Action:   adversary speed = 0.0              ← cyclist waits at end
```

In XML, one event looks like this:
```xml
<Event name="CyclistStartsWalking" priority="overwrite">
  <Action name="CyclistStartsWalking">
    <PrivateAction>
      <LongitudinalAction>
        <SpeedAction>
          <SpeedActionDynamics dynamicsShape="step" value="1.5" dynamicsDimension="distance"/>
          <SpeedActionTarget>
            <AbsoluteTargetSpeed value="2.0"/>   <!-- set cyclist speed to 2 m/s -->
          </SpeedActionTarget>
        </SpeedAction>
      </LongitudinalAction>
    </PrivateAction>
  </Action>
  <StartTrigger>
    <ConditionGroup>
      <Condition name="StartCondition" delay="0" conditionEdge="rising">
        <ByEntityCondition>
          <TriggeringEntities triggeringEntitiesRule="any">
            <EntityRef entityRef="hero"/>         <!-- watch the ego -->
          </TriggeringEntities>
          <EntityCondition>
            <RelativeDistanceCondition
              entityRef="adversary"
              relativeDistanceType="cartesianDistance"
              value="14.0"
              rule="lessThan"/>                   <!-- fires when ego is within 14m of cyclist -->
          </EntityCondition>
        </ByEntityCondition>
      </Condition>
    </ConditionGroup>
  </StartTrigger>
</Event>
```

#### Trigger condition types

The `<StartTrigger>` can use many different condition types:

| Condition | Example use |
|---|---|
| `RelativeDistanceCondition` | Fire when ego is within X metres of an actor |
| `TraveledDistanceCondition` | Fire after ego has driven X metres total |
| `SimulationTimeCondition` | Fire at a specific simulation time |
| `StandStillCondition` | Fire when an actor has been stopped for X seconds |
| `SpeedCondition` | Fire when an actor reaches a target speed |
| `StoryboardElementStateCondition` | Fire when a previous event/action completes |

From `CyclistCrossing.xosc` and `FollowLeadingVehicle.xosc`:
```xml
<!-- trigger after ego travels 1 metre -->
<TraveledDistanceCondition value="1.0"/>

<!-- trigger when ego is within 40m of adversary (longitudinal only) -->
<RelativeDistanceCondition entityRef="adversary"
    relativeDistanceType="longitudinal" value="40.0" freespace="true" rule="lessThan"/>

<!-- trigger at simulation time = 0 (immediate start) -->
<SimulationTimeCondition value="0" rule="equalTo"/>

<!-- trigger when a previous action has fully completed -->
<StoryboardElementStateCondition
    storyboardElementType="action"
    storyboardElementRef="CyclistStartsWalking"
    state="completeState"/>
```

#### Init section — setting up the world

Before the storyboard runs, `<Init>` places all actors and sets the environment:

```xml
<Init>
  <Actions>
    <!-- Set weather -->
    <GlobalAction>
      <EnvironmentAction>
        <Environment name="Environment1">
          <TimeOfDay animation="false" dateTime="2019-06-25T12:00:00"/>
          <Weather cloudState="free">
            <Sun intensity="0.85" azimuth="0" elevation="1.31"/>
          </Weather>
          <RoadCondition frictionScaleFactor="1.0"/>
        </Environment>
      </EnvironmentAction>
    </GlobalAction>

    <!-- Spawn ego at world position, assign external controller (Autoware) -->
    <Private entityRef="hero">
      <PrivateAction>
        <TeleportAction>
          <Position>
            <WorldPosition x="130" y="55" z="0" h="3.14159265359"/>
          </Position>
        </TeleportAction>
      </PrivateAction>
      <PrivateAction>
        <ControllerAction>
          <AssignControllerAction>
            <Controller name="HeroAgent">
              <Properties>
                <Property name="module" value="external_control"/>  <!-- Autoware takes over -->
              </Properties>
            </Controller>
          </AssignControllerAction>
        </ControllerAction>
      </PrivateAction>
    </Private>

    <!-- Spawn cyclist at a different position -->
    <Private entityRef="adversary">
      <PrivateAction>
        <TeleportAction>
          <Position>
            <WorldPosition x="95.5" y="41" z="0.2" h="3.14159265359"/>
          </Position>
        </TeleportAction>
      </PrivateAction>
    </Private>
  </Actions>
</Init>
```

### How to run
```bash
export CARLA_ROOT=${HOME}/CC/carla_0.9.15
export PYTHONPATH="${CARLA_ROOT}/PythonAPI/carla/":${PYTHONPATH}
export PYTHONPATH=$PYTHONPATH:${CARLA_ROOT}/PythonAPI/carla/dist/carla-0.9.15-py3.10-linux-x86_64.egg

cd ~/CC/op_carla/scenario_runner
python3 scenario_runner.py --openscenario srunner/examples/CyclistCrossing.xosc --timeout 1600
```

Override parameters at runtime without editing the file:
```bash
python3 scenario_runner.py --openscenario srunner/examples/FollowLeadingVehicle.xosc \
    --openscenarioparams Speed:30
```

### Available scenarios

| Scenario | Map | Description |
|---|---|---|
| CyclistCrossing.xosc | Town01 | Cyclist crosses in front of ego at a right turn |
| FollowLeadingVehicle.xosc | Town01 | Ego follows a lead vehicle that brakes suddenly |
| PedestrianCrossingFront.xosc | Town01 | Pedestrian crosses in front of ego |
| IntersectionCollisionAvoidance.xosc | Town01 | Ego must avoid collision at an intersection |
| Slalom.xosc | Town01 | Ego navigates through a series of obstacles |
| ChangingWeather.xosc | Town01 | Weather changes dynamically during the scenario |
| OscControllerExample.xosc | Town01 | Example of using an OSC controller for ego |
| CatalogExample.xosc | Town01 | Demonstrates use of external catalogs |
| LaneChangeSimple.xosc | Town04 | Simple lane change on a multi-lane road |

### Map format
The map is referenced inside the `.xosc` file via:
```xml
<RoadNetwork>
    <LogicFile filepath="Town01"/>
</RoadNetwork>
```
CARLA uses this to load the corresponding town when the scenario starts.

---

## Format 2 — Python Native Scenarios

### What it is
Scenarios written as Python classes that inherit from `BasicScenario`. The runner auto-discovers all `.py` files in `srunner/scenarios/` using `importlib` — no manual registration needed.

Each Python scenario defines:
- **Actor initialization** — which vehicles/pedestrians to spawn and where
- **Behavior tree** — actor logic using the `py_trees` library
- **Test criteria** — pass/fail conditions (collision, route completion, red light, etc.)

### How to run
```bash
# Run by scenario name
python3 scenario_runner.py --scenario FollowLeadingVehicle_1 --reloadWorld

# List all available Python scenarios
python3 scenario_runner.py --list

# Run with an XML config to set exact spawn positions
python3 scenario_runner.py --scenario ControlLoss \
    --configFile srunner/examples/ControlLoss.xml

# Repeat the scenario multiple times
python3 scenario_runner.py --scenario CutIn --repetitions 5

# Load a custom scenario from outside srunner/scenarios/
python3 scenario_runner.py --scenario MyScenario \
    --additionalScenario /path/to/my_scenario.py
```

### XML config files
Each Python scenario has a companion XML config in `srunner/examples/` that defines specific ego spawn positions across multiple towns. Example from `ControlLoss.xml`:
```xml
<scenarios>
    <scenario name="ControlLoss_1" type="ControlLoss" town="Town01">
        <ego_vehicle x="392.5" y="195" z="0.5" yaw="90" model="vehicle.lincoln.mkz_2017" />
    </scenario>
    <scenario name="ControlLoss_2" type="ControlLoss" town="Town01">
        <ego_vehicle x="-2.0" y="160" z="0.5" yaw="90" model="vehicle.lincoln.mkz_2017" />
    </scenario>
    ...
</scenarios>
```

### Available Python scenarios

| Scenario Class | Source File | Description |
|---|---|---|
| ControlLoss | control_loss.py | Vehicle loses control on degraded road surface |
| FollowLeadingVehicle | follow_leading_vehicle.py | Lead vehicle brakes suddenly |
| CutIn | cut_in.py | Another vehicle cuts into ego's lane |
| ChangeLane | change_lane.py | Vehicle performs a lane change ahead of ego |
| DynamicObjectCrossing | object_crash_vehicle.py | Object (pedestrian/cyclist) crosses ego's path |
| VehicleTurningRoute | object_crash_intersection.py | Vehicle turns across ego's path at intersection |
| OtherLeadingVehicle | other_leading_vehicle.py | Slower vehicle ahead on a narrow road |
| ManeuverOppositeDirection | maneuver_opposite_direction.py | Vehicle comes from opposite direction |
| OppositeVehicleTakingPriority | opposite_vehicle_taking_priority.py | Oncoming vehicle takes priority |
| SignalizedJunctionLeftTurn | signalized_junction_left_turn.py | Left turn at a signalized intersection |
| SignalizedJunctionRightTurn | signalized_junction_right_turn.py | Right turn at a signalized intersection |
| NoSignalJunctionCrossing | no_signal_junction_crossing.py | Crossing at an unsignalized junction |
| SignalJunctionCrossingRoute | junction_crossing_route.py | Junction crossing for route-based mode |
| NoSignalJunctionCrossingRoute | junction_crossing_route.py | Unsignalized junction for route-based mode |
| ConstructionCrashVehicle | construction_crash_vehicle.py | Construction zone obstacle ahead |
| BackgroundActivity | background_activity.py | General background traffic activity |
| FreeRide | freeride.py | Free driving without specific scenario |

---

## Format 3 — Route-Based (CARLA Leaderboard)

### What it is
The CARLA Leaderboard format evaluates an autonomous agent over a **long multi-waypoint route**. Unlike the other two formats, the ego does not follow a scripted sequence — it must drive autonomously from start to finish while Python scenarios are dynamically injected at pre-defined GPS trigger points along the route.

This is the closest format to real-world AV evaluation: the agent is scored on route completion, collision avoidance, traffic rule compliance, and more.

### The two input files

#### File 1 — Route XML (`routes_training.xml` / `routes_devtest.xml`)
Defines the **ego's path** only — a sequence of GPS waypoints through the map. No scenario logic.

```xml
<route id="0" town="Town01">
    <weather cloudiness="0" precipitation="0" sun_altitude_angle="70" ... />
    <waypoint x="338.7" y="226.7" yaw="269.9" z="0.0" />
    <waypoint x="321.9" y="194.6" yaw="179.8" z="0.0" />
    <waypoint x="88.4"  y="210.5" yaw="89.9"  z="0.0" />
    ...
</route>
```

#### File 2 — Scenarios JSON (`all_towns_traffic_scenarios_public.json`)
A lookup table of **GPS trigger positions** per town per scenario type. When the ego passes near one of these positions, the corresponding Python scenario class is spawned.

```json
"Town01": [
  {
    "scenario_type": "Scenario1",
    "available_event_configurations": [
      { "transform": { "x": "319.64", "y": "-2.20", "yaw": "180" } },
      ...  ← 40 possible trigger locations in Town01 alone
    ]
  },
  {
    "scenario_type": "Scenario3",
    "available_event_configurations": [
      { "transform": { "x": "319.64", "y": "-2.20", "yaw": "180" } },
      ...  ← 18 possible trigger locations
    ]
  }
]
```

### Scenario type to Python class mapping

Defined in `op_bridge/leaderboard/scenarios/route_scenario.py`:

| Scenario ID | Python Class | Behavior |
|---|---|---|
| Scenario1 | ControlLoss | Vehicle loses control ahead |
| Scenario2 | FollowLeadingVehicle | Lead vehicle brakes suddenly |
| Scenario3 | DynamicObjectCrossing | Pedestrian/cyclist crosses path |
| Scenario4 | VehicleTurningRoute | Vehicle turns across ego at intersection |
| Scenario5 | OtherLeadingVehicle | Slower vehicle on narrow road |
| Scenario6 | ManeuverOppositeDirection | Oncoming vehicle blocks lane |
| Scenario7 | SignalJunctionCrossingRoute | Signalized junction conflict |
| Scenario8 | SignalJunctionCrossingRoute | Signalized junction conflict (variant) |
| Scenario9 | SignalJunctionCrossingRoute | Signalized junction conflict (variant) |
| Scenario10 | NoSignalJunctionCrossingRoute | Unsignalized junction conflict |

> Note: Scenario7, 8, and 9 all use the same Python class — they differ only in the GPS trigger position and approach angle defined in the JSON.

### How it connects at runtime

```
routes_devtest.xml               all_towns_traffic_scenarios_public.json
  (ego waypoints)        +            (trigger GPS positions per town)
        │                                          │
        └──────────────────┬────────────────────────┘
                           ▼
                  leaderboard_evaluator.py
                  + RouteScenario (Python)
                           │
                  checks: is any trigger position
                  within range of the ego's route?
                           │
                  YES → spawn Python scenario class
                  with its py_trees behavior tree
                           │
                  Ego agent (Autoware / op_ros2_agent)
                  must handle it autonomously
```

### How to run

In this repo, Leaderboard mode is launched via shell scripts in `op_bridge/op_scripts/`:

```bash
# Town01 (default)
. ~/CC/op_carla/op_bridge/op_scripts/run_route_scenarios_ros2.sh

# Other towns
. ~/CC/op_carla/op_bridge/op_scripts/run_route_scenarios_ros2_town03.sh
. ~/CC/op_carla/op_bridge/op_scripts/run_route_scenarios_ros2_town04.sh
. ~/CC/op_carla/op_bridge/op_scripts/run_route_scenarios_ros2_town06.sh
```

These scripts call `leaderboard_evaluator.py` with:
- `--routes` — the route XML file
- `--scenarios` — the scenarios JSON file
- `--agent` — the autonomous agent (`op_ros2_agent.py` → Autoware)

### Evaluation criteria
The Leaderboard scores the agent on:

| Criterion | Description |
|---|---|
| Route completion | % of the route successfully driven |
| Collision test | Any collision with vehicles, pedestrians, or static objects |
| Outside route lanes | Driving outside the designated lanes |
| Running red lights | Failing to stop at red traffic lights |
| Running stop signs | Failing to stop at stop signs |
| Agent speed above threshold | Exceeding speed limits |

---

## Key CLI Flags Reference

```bash
python3 scenario_runner.py [OPTIONS]
```

| Flag | Format | Description |
|---|---|---|
| `--openscenario FILE` | `.xosc` | Run an OpenSCENARIO file |
| `--openscenarioparams K:V` | `.xosc` | Override scenario parameters at runtime |
| `--scenario NAME` | Python | Run a Python scenario by class name |
| `--configFile FILE` | Python | XML config with ego spawn positions |
| `--additionalScenario FILE` | Python | Load extra scenario file from outside srunner/scenarios/ |
| `--route ROUTE SCENARIOS` | Leaderboard | Run route-based evaluation |
| `--agent FILE` | Leaderboard | Agent script for route mode |
| `--list` | Any | List all discoverable Python scenarios and exit |
| `--repetitions N` | Any | Repeat the scenario N times |
| `--randomize` | Any | Randomize scenario parameters |
| `--reloadWorld` | Any | Reload CARLA world before running |
| `--waitForEgo` | Any | Connect to an already-spawned ego vehicle |
| `--timeout N` | Any | Client timeout in seconds (default: 10) |
| `--record PATH` | Any | Save a CARLA recording to path |
| `--host` / `--port` | Any | CARLA server connection (default: localhost:2000) |
