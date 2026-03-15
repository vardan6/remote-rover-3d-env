# Remote Rover Simulator — CLAUDE.md

> Full design reference: `initial-hl-design.md` (same directory)

## Project Overview

This repo contains the **3D Rover Simulator** — a standalone Python desktop application. It is one of three separate components in the Remote Rover system:

1. **This repo — Python desktop simulator** (Panda3D + panda3d.bullet) — renders the rover, runs physics, captures POV frames
2. **remote-rover-server** *(separate repo, Phase 3)* — FastAPI MQTT ↔ WebSocket relay, serves GCS web app
3. **GCS web app** *(part of server repo)* — browser-based ground control station

All components communicate via an **external Mosquitto MQTT broker**.

## Current Phase: Phase 1 — 3D Simulator (standalone)

### Goal
Build a standalone Python desktop 3D rover simulator. No server, no MQTT yet — just the simulator running in its own window.

### What to Build

**`simulator/main.py`** — entry point, initializes and runs the Panda3D app

**`simulator/terrain.py`** — Panda3D terrain: varied but mostly flat surface (procedural or heightmap). Bullet terrain collision shape using `panda3d.bullet`.

**`simulator/rover.py`** — Rover model (simple box mesh is fine). Bullet rigid body with vehicle physics. Throttle-based movement: arrow keys apply proportional force (0.0–1.0), friction decelerates when released.

**`simulator/camera.py`** — Two cameras:
- Follow camera (default): third-person, tracks rover
- POV camera: mounted at rover front, toggled with V key
- Offscreen `GraphicsBuffer` for POV frame capture (needed in Phase 2)

**`simulator/gui.py`** — `DirectGUI` overlay showing live telemetry:
- Position (x, y, z)
- Heading (degrees)
- Speed

### Controls
| Key | Action |
|-----|--------|
| ↑ Arrow | Throttle forward |
| ↓ Arrow | Throttle backward |
| ← Arrow | Steer left |
| → Arrow | Steer right |
| V | Toggle follow / POV camera |

### Done Criteria
- Panda3D window opens with terrain and rover visible
- Arrow keys move the rover with proportional throttle (hold = accelerate, release = friction decelerate)
- V key toggles between follow camera and rover POV camera
- DirectGUI overlay shows live position, heading, speed

### Constraints
- Use **`panda3d.bullet`** (Panda3D's built-in Bullet module) — do NOT use the standalone `pybullet` PyPI package
- Keep each file focused and simple — no premature abstraction
- No MQTT, no server, no networking in this phase

### Dependencies
```
panda3d
```
Add to `requirements.txt`. `panda3d.bullet` is included with Panda3D — no separate package needed.

---

## Upcoming Phases (do not implement yet)

**Phase 2 — MQTT Integration**
- Publish telemetry + JPEG POV frames to MQTT
- Subscribe to control topics (throttle, steering, brake)
- DirectGUI settings for broker URL, port, topic prefix

**Phase 3 — Server + GCS Web App** *(separate repo)*
- FastAPI server: MQTT relay + WebSocket + serve frontend
- GCS: POV video, telemetry dashboard, keyboard controls, settings

**Phase 4 — Multi-GCS + Peripherals**
- Multiple simultaneous GCS connections
- Peripheral device MQTT control input

## MQTT Topic Structure (Phase 2+)
```
/remote-rover-01/controls/throttle    {"value": 0.8}
/remote-rover-01/controls/steering    {"value": -0.5}
/remote-rover-01/controls/brake       {"value": 1.0}
/remote-rover-01/telemetry/position   {"x": 1.2, "y": 3.4, "z": 0.1}
/remote-rover-01/telemetry/imu        {"accel": {...}, "gyro": {...}}
/remote-rover-01/telemetry/gps        {"lat": ..., "lon": ..., "alt": ...}
/remote-rover-01/telemetry/heading    {"deg": 45.2}
/remote-rover-01/video/pov            [JPEG binary, 10 FPS default]
/remote-rover-01/configs/...          configuration updates
```

## Project Structure
```
3d-env/                     ← this repo root (run `claude` from here)
  CLAUDE.md                 ← this file
  initial-hl-design.md      # Full system design reference
  simulator/                # Phase 1: Python desktop simulator
    main.py
    terrain.py
    rover.py
    camera.py
    gui.py
  requirements.txt          # Python dependencies
  config.json               # Auto-generated settings (Phase 2+)
```
