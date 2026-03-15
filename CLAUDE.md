# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> Full design reference: `initial-hl-design.md` (same directory)

## Project Overview

This repo is the **3D Rover Simulator** — a standalone Python desktop application (Phase 1 of 4). It is one of three separate components in the Remote Rover system:

1. **This repo** — Python desktop simulator (Panda3D + panda3d.bullet): renders rover, runs physics, captures POV frames
2. **remote-rover-server** *(separate repo, Phase 3)* — FastAPI MQTT ↔ WebSocket relay + GCS web app

All components communicate via an **external Mosquitto MQTT broker**.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the simulator
python simulator/main.py
```

## Architecture

The simulator is organized into five files under `simulator/`:

- **`main.py`** — Panda3D `ShowBase` entry point. Wires together terrain, rover, camera, and GUI. Runs the main game loop via Panda3D's `taskMgr`.
- **`terrain.py`** — Procedural or heightmap terrain with a `BulletTerrainShape` collision mesh.
- **`rover.py`** — Box-mesh rover with a `BulletRigidBodyNode`. Throttle-based movement: arrow keys apply proportional force; friction decelerates on release.
- **`camera.py`** — Two cameras: follow cam (default, third-person) and POV cam (rover-front, toggled with V). POV uses an offscreen `GraphicsBuffer` for Phase 2 frame capture.
- **`gui.py`** — `DirectGUI` overlay showing live position (x, y, z), heading, and speed.

### Key Constraints

- Use **`panda3d.bullet`** (built into Panda3D) — do NOT use the standalone `pybullet` PyPI package. `panda3d.bullet` is natively wired to the scene graph; standalone pybullet requires manual position/rotation sync.
- No MQTT, no networking in Phase 1.
- Keep each file focused — no premature abstraction.

### Controls

| Key | Action |
|-----|--------|
| ↑ | Throttle forward |
| ↓ | Throttle backward |
| ← | Steer left |
| → | Steer right |
| V | Toggle follow / POV camera |

## Upcoming Phases (do not implement yet)

**Phase 2 — MQTT Integration**
- Publish telemetry + JPEG POV frames to MQTT via `paho-mqtt`
- Subscribe to control topics (throttle, steering, brake)
- DirectGUI settings for broker URL, port, topic prefix
- Persist settings to `config.json`

**Phase 3 — Server + GCS Web App** *(separate repo)*
- FastAPI + paho-mqtt server: MQTT relay + WebSocket + serve GCS frontend
- GCS: POV video feed, telemetry dashboard, keyboard controls

**Phase 4 — Multi-GCS + Peripherals**

## MQTT Topic Structure (Phase 2+)

```
/remote-rover-01/controls/throttle    {"value": 0.8}
/remote-rover-01/controls/steering    {"value": -0.5}
/remote-rover-01/controls/brake       {"value": 1.0}
/remote-rover-01/telemetry/position   {"x": 1.2, "y": 3.4, "z": 0.1}
/remote-rover-01/telemetry/heading    {"deg": 45.2}
/remote-rover-01/telemetry/imu        {"accel": {...}, "gyro": {...}}
/remote-rover-01/video/pov            [JPEG binary, 10 FPS default]
```

Topic prefix (`/remote-rover-01/`) is configurable per rover instance. Telemetry default rate: 0.5s (2 Hz).
