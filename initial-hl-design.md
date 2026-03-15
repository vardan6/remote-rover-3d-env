# Remote Rover 3D Environment — Initial High-Level Design

## 3D Virtual Environment Requirements

I need a platform to model a 3D virtual environment for an off-road rover car. The model must support movement: forward, backward, left, and right — matching what a real rover can do. A flat surface or 2D model may be sufficient, but a 3D environment is preferred. Ideally, the environment comes pre-built with varied but mostly flat terrain suitable for testing.

Physics simulation is highly desired. I want a 3D environment with realistic physics and a rover model operating within it. If full physics is too complex to implement initially, a simpler option without physics can be considered as a fallback, but both options should be evaluated.

The primary goal of this simulator is to support the design and development of a web server that will eventually connect to a real rover. For now, development will happen entirely in the virtual environment.

**Key requirements:**
- 3D simulator and server backend written in Python
- GCS web frontend uses HTML/JavaScript
- As simple as possible
- Developed using Claude Code CLI in VS Code

### 3D Technology Choice

After evaluating available options against the project's requirements (Python, desktop app with own window, physics, simplicity, POV camera capture), the recommended stack is:

**Panda3D + PyBullet (Python desktop application)**

- **Panda3D** (v1.10.16, Dec 2024, actively maintained) provides the 3D rendering engine: desktop window, terrain rendering, rover model, offscreen POV camera capture via `GraphicsBuffer`, and built-in GUI via `DirectGUI` for in-app menus and settings.
- **panda3d.bullet** (Panda3D's built-in Bullet physics module) provides realistic physics: gravity, friction, terrain collision, and vehicle dynamics. This is the recommended physics integration — it is natively wired into Panda3D, so no manual synchronization between physics bodies and scene nodes is needed. Do **not** use standalone `pybullet` (the separate PyPI package), which requires manual position/rotation sync and adds unnecessary complexity.
- **paho-mqtt** provides MQTT connectivity: the simulator publishes telemetry and POV frames, and subscribes to control commands.

Alternatives evaluated and ruled out:
- **Ursina:** Active (v8.3.0), simpler API, but no built-in GUI or physics — would still need panda3d.bullet + tkinter, adding the same integration complexity with less control.
- **Babylon.js / Three.js (browser-based):** Good for web-first, but physics would not run in Python. Rover model and simulation logic would be in JavaScript, not Python.
- **Standalone pybullet (PyPI package):** Excellent physics, but has no built-in 3D renderer or GUI, and requires manual sync with any rendering layer — unnecessary when panda3d.bullet is already integrated.

### System Architecture

The system consists of three separate components connected via MQTT:

```
┌─────────────────────────────────────┐
│  Python 3D Rover Simulator          │  (Panda3D + PyBullet)
│  - Desktop window + DirectGUI menus │
│  - Physics simulation (PyBullet)    │
│  - POV camera capture               │
│  - Publishes telemetry + video      │
│  - Subscribes to control commands   │
└──────────────────┬──────────────────┘
                   │ MQTT (Mosquitto)
                   ▼
┌─────────────────────────────────────┐
│  Server (Python FastAPI)            │
│  - MQTT ↔ WebSocket relay           │
│  - Serves GCS web app               │
│  - Config / settings persistence    │
└──────────────────┬──────────────────┘
                   │ WebSocket / HTTP
                   ▼
┌─────────────────────────────────────┐
│  GCS Web App (browser)              │  ← multiple instances supported
│  - Displays POV video stream        │
│  - Telemetry dashboard              │
│  - Keyboard / peripheral controls   │
│  - Settings menu                    │
└─────────────────────────────────────┘
                   ▲
        Peripheral devices (joystick, etc.)
        can also send controls via MQTT
```

- In **virtual mode**, physics runs inside PyBullet in the simulator. The simulator owns the rover's state and publishes it.
- In **real-rover mode**, the physical rover publishes its own state via MQTT. The simulator can either visualize the real rover's state or be bypassed entirely — the server and GCS work the same way regardless.

## Control Interface

The rover is drivable via the arrow keys on the keyboard, similar to a standard game control scheme. Movement is **throttle-based** (proportional): arrow keys apply a configurable thrust force. Holding a key accelerates the rover; releasing it lets friction decelerate. MQTT control values are floating-point (0.0–1.0), where 0.0 means no input and 1.0 means full throttle/steering.

### Settings Menu

A settings panel, accessible from the main interface (DirectGUI in the simulator, web panel in the GCS), allows the user to configure all communication options without restarting the application. The settings menu includes the following areas:

#### Protocol Selection

The user can enable or disable each supported server protocol independently. Where technically feasible, multiple protocols may be active simultaneously, allowing the simulator to accept commands from more than one source at the same time. Supported protocols (to be evaluated during implementation): MQTT, WebSocket, HTTP polling.

#### MQTT Broker Configuration

When MQTT is enabled, the following connection parameters must be specified:

| Field      | Description                          |
|------------|--------------------------------------|
| Broker URL | Hostname or IP of the MQTT broker    |
| Port       | Broker port (default: 1883 / 8883)   |
| Client ID  | Optional unique identifier           |

The project uses an **external MQTT broker** (Mosquitto) running on a known IP address. No embedded broker is required. No authentication is configured initially (open broker); stricter access will be added later. The broker URL and port are configured in the settings menu and persisted in `config.json`.

#### Topic Addressing

Each control action and data stream is mapped to a configurable MQTT topic. Topics use a hierarchical prefix scheme, where the prefix identifies the rover instance (e.g., `/remote-rover-01/`):

**Control topics (subscribed by simulator):**
```
/remote-rover-01/controls/throttle     → {"value": 0.8}
/remote-rover-01/controls/steering     → {"value": -0.5}   (negative = left, positive = right)
/remote-rover-01/controls/brake        → {"value": 1.0}
```

**Telemetry topics (published by simulator):**
```
/remote-rover-01/telemetry/position    → {"x": 1.2, "y": 3.4, "z": 0.1}
/remote-rover-01/telemetry/imu         → {"accel": {"x": ..., "y": ..., "z": ...}, "gyro": {"x": ..., "y": ..., "z": ...}}
/remote-rover-01/telemetry/gps         → {"lat": ..., "lon": ..., "alt": ...}
/remote-rover-01/telemetry/heading     → {"deg": 45.2}
```

**Video topic (published by simulator):**
```
/remote-rover-01/video/pov             → [JPEG binary frame]
```

**Configuration topics:**
```
/remote-rover-01/configs/...           → configuration updates
```

The topic prefix (`/remote-rover-01/`) is configurable per rover instance from the settings menu. All topic addresses are user-configurable. Additional topics (both subscribed and published) should be addable in the future without code changes.

#### Telemetry Update Rate

The settings menu includes a configurable telemetry update interval that controls how frequently the simulator publishes rover state data (position, heading, altitude, accelerometer, gyroscope, GPS). The default is **0.5 seconds** (2 Hz). The user can increase or decrease this rate depending on bandwidth and display needs.

#### Settings Persistence

All settings (protocol toggles, broker URL, port, client ID, topic prefix, topic addresses, telemetry update rate) are automatically saved to a `config.json` file in the project root whenever the user applies changes. On startup, the application loads settings from this file if it exists. The file can also be edited manually and reloaded without restarting the application.

### GCS Web Interface Layout

The GCS is a web application served by the FastAPI server. Multiple GCS instances can connect simultaneously. The browser-based GCS interface is organized as follows:

- **Top / main area:** POV video feed from the rover (streamed via WebSocket)
- **Bottom-left panel:** Live telemetry display (position, heading, altitude, accelerometer, gyroscope, GPS)
- **Bottom-right panel / modal:** Settings panel (protocol selection, broker config, topic addressing, telemetry rate)
- **Keyboard control:** Active whenever the browser window is focused; no click required

The layout should be clean and minimal. A single HTML page with inline panels is sufficient for the initial implementation.

## Server Architecture

The server acts as the central communication hub between ground control stations (GCS) and the rover (virtual simulator now, real rover later).

### Control Flow

```
Peripheral Devices ──→ MQTT Broker ──→ Simulator
                                          │
GCS (browser) ←──WebSocket──→ Server ←──MQTT──→ Simulator
GCS (browser) ←──WebSocket──→ Server ←──MQTT──→ Simulator
   ...multiple GCS clients...
```

The server bridges MQTT and WebSocket: it subscribes to rover telemetry and video topics on MQTT and pushes them to connected GCS clients via WebSocket. Control commands from GCS clients travel the reverse path. Peripheral devices (joysticks, external controllers) can publish control commands directly to MQTT without going through the server.

### Extensibility

Beyond movement commands, the server must be designed to support:
- Configuration updates and internal settings changes for the rover
- Any future remote command that may be needed to configure or control the rover

Command transmission uses MQTT with JSON-structured messages to allow flexibility for adding new command types later.

### Rover Telemetry (Rover → Server → GCS)

The rover simulator publishes its state to MQTT telemetry topics. The server subscribes to these topics and pushes updates to connected GCS clients via WebSocket. Telemetry data includes:
- Geometric position (x, y, z)
- Heading angle
- Altitude
- IMU data (accelerometer, gyroscope)
- GPS position

The default update rate is 0.5 seconds (2 Hz), configurable from the settings menu. Panda3D exposes object position, rotation, and velocity natively — these are read each telemetry tick and published.

### Video

The 3D simulator captures POV frames from a virtual camera mounted at the rover's front using Panda3D's offscreen rendering (`GraphicsBuffer`). Frames are JPEG-encoded and published to the MQTT video topic (`/remote-rover-01/video/pov`). The server relays these to connected GCS clients via WebSocket, where they are displayed as a live video feed.

The default POV frame rate is **10 FPS**. At typical JPEG sizes (30–100 KB per frame), this results in 300 KB–1 MB/s through the MQTT broker — within Mosquitto's capability for a local network, but worth monitoring. If video throughput becomes a bottleneck at higher frame rates or over WAN, the video path can be switched to a direct WebSocket stream bypassing MQTT without changing the server or GCS code.

When connecting to a real rover, the physical camera feed replaces the virtual POV — published to the same MQTT topic, so the server and GCS work unchanged.

### Single-Server Goal

The **server** component (not the simulator) should be a single process handling all relay functionality: MQTT bridging, WebSocket push, GCS web app serving, and settings management. The 3D simulator runs as a separate process.

The server backend should be implemented in **Python** (strongly preferred), or **Node.js** as a secondary option.

**Recommended stack: Python FastAPI + paho-mqtt**
- **FastAPI** (with Uvicorn) serves the GCS web app and exposes WebSocket endpoints for telemetry, video, and control relay.
- An embedded **MQTT client** (`paho-mqtt`) subscribes to simulator telemetry/video topics and publishes control commands.
- **WebSockets** push live telemetry and video frames to GCS browsers without polling.
- Everything runs in a single Python process; async I/O (asyncio) keeps latency low.

**Node.js alternative: Express + MQTT.js + Socket.IO**
- A viable fallback if Python proves insufficient for WebSocket + video relay performance.

## Project Structure

```
remote-rover/
  3d-env/                 # Design documents
  simulator/              # Python 3D Rover Simulator (Panda3D + PyBullet)
    main.py               # Entry point
    rover.py              # Rover model, physics, movement
    terrain.py            # Terrain generation / loading
    camera.py             # POV camera + offscreen capture
    mqtt_bridge.py        # MQTT publish (telemetry, video) + subscribe (commands)
    gui.py                # DirectGUI menus / settings overlay
  server/                 # Python FastAPI Server
    main.py               # Entry point
    mqtt_relay.py         # MQTT ↔ WebSocket relay
    ws_manager.py         # WebSocket connection manager
    config.py             # Config load/save
  frontend/               # GCS Web App (served by server)
    index.html            # Main GCS page
    telemetry.js          # Telemetry display
    video.js              # POV video display
    controls.js           # Keyboard → WebSocket commands
    settings.js           # Settings UI
  config.json             # Persisted user settings (auto-generated)
  requirements.txt        # Python dependencies
```

## Build Phases

To keep development focused and testable, the implementation is divided into four phases:

**Phase 1 — 3D Simulator (desktop, standalone)**
- Set up Panda3D scene: terrain with varied but mostly flat surface
- Rover model (simple box/mesh, sufficient for testing)
- PyBullet physics: gravity, terrain collision, throttle-based movement
- Arrow-key controls (local keyboard input)
- POV camera toggle (V key) — switch between follow camera and rover-front camera
- DirectGUI overlay displaying rover telemetry (position, heading, speed)
- No MQTT, no server — just the standalone desktop simulator

**Phase 2 — MQTT Integration**
- Simulator publishes telemetry to MQTT topics (position, heading, IMU, GPS)
- Simulator publishes POV frames (JPEG) to video topic
- Simulator subscribes to control topics (throttle, steering, brake)
- Rover drivable from external MQTT commands (verifiable via `mosquitto_pub`)
- Settings for broker URL, port, topic prefix configurable via DirectGUI

**Phase 3 — Server + GCS Web App**
- FastAPI server: connects to MQTT broker, serves GCS frontend files
- GCS web app: displays POV video stream, telemetry dashboard, keyboard controls
- WebSocket relay between MQTT topics and browser clients
- Settings menu in GCS (broker config, topic addressing, telemetry rate)
- Settings persistence to/from `config.json`

**Phase 4 — Multi-GCS + Peripherals**
- Support multiple simultaneous GCS browser connections
- Peripheral device control input via MQTT (joystick, external controllers)
- Advanced settings and extensibility
