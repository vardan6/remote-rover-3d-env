# Remote Rover 3D Environment — Initial High-Level Design

## 3D Virtual Environment Requirements

I need a platform to model a 3D virtual environment for an off-road rover car. The model must support movement: forward, backward, left, and right — matching what a real rover can do. A flat surface or 2D model may be sufficient, but a 3D environment is preferred. Ideally, the environment comes pre-built with varied but mostly flat terrain suitable for testing.

Physics simulation is highly desired. I want a 3D environment with realistic physics and a rover model operating within it. If full physics is too complex to implement initially, a simpler option without physics can be considered as a fallback, but both options should be evaluated.

The primary goal of this simulator is to support the design and development of a web server that will eventually connect to a real rover. For now, development will happen entirely in the virtual environment.

**Key requirements:**
- Written in Python
- Accessible via a web interface (browser-based GUI)
- As simple as possible
- Developed using Claude Code CLI in VS Code

## Control Interface

The rover is drivable via the arrow keys on the keyboard, similar to a standard game control scheme.

### Settings Menu

A settings panel, accessible from the main interface, allows the user to configure all communication options without restarting the application. The settings menu includes the following areas:

#### Protocol Selection

The user can enable or disable each supported server protocol independently. Where technically feasible, multiple protocols may be active simultaneously, allowing the simulator to accept commands from more than one source at the same time. Supported protocols (to be evaluated during implementation): MQTT, WebSocket, HTTP polling.

#### MQTT Broker Configuration

When MQTT is enabled, the following connection parameters must be specified:

| Field      | Description                          |
|------------|--------------------------------------|
| Broker URL | Hostname or IP of the MQTT broker    |
| Port       | Broker port (default: 1883 / 8883)   |
| Client ID  | Optional unique identifier           |

#### Topic Addressing

Each control action and data stream is mapped to a configurable MQTT topic. Topics are directional:

- **Subscribed topics (inputs):** The simulator listens on these topics to receive commands.
  - Forward, Backward, Left, Right, Stop — one topic per action, or a single command topic with a JSON payload.
- **Published topics (outputs):** The simulator publishes rover state data to these topics.
  - Accelerometer data
  - Gyroscope data
  - GPS position
  - Heading angle
  - Altitude

All topic addresses are user-configurable from the settings menu. Additional topics (both subscribed and published) should be addable in the future without code changes.

#### Telemetry Update Rate

The settings menu includes a configurable telemetry update interval that controls how frequently the simulator publishes rover state data (position, heading, altitude, accelerometer, gyroscope, GPS). The default is **0.5 seconds** (2 Hz). The user can increase or decrease this rate depending on bandwidth and display needs.

## Server Architecture

The server acts as the central communication hub between a ground control station (GCS) and the rover (virtual now, real later).

### Control Flow

```
Ground Control Station  ←→  Server  ←→  Rover (virtual / real)
```

The server receives control commands (forward, backward, left, right, and others) from the GCS and relays them to the rover with the lowest possible latency. Protocol selection should prioritize minimal communication delay end-to-end.

### Extensibility

Beyond movement commands, the server must be designed to support:
- Configuration updates and internal settings changes for the rover
- Any future remote command that may be needed to configure or control the rover

Command transmission should use MQTT with JSON-structured messages to allow flexibility for adding new command types later.

### Rover Telemetry (Rover → Server → GCS)

The rover should transmit its state back to the server, which displays it on a web interface. Telemetry data includes:
- Geometric position
- Heading angle
- Altitude
- Physical orientation

Telemetry does not need to be real-time; a minimum update rate of once per second is acceptable. If the 3D model can expose this data natively (position, angle, etc.), it should be wired into the telemetry pipeline automatically.

### Video

The rover should also be capable of streaming video back through the same server to the GCS.

### Single-Server Goal

All functionality — control relay, telemetry display, video streaming, and web interface — should reside on a single server. The backend should be implemented in **Python** (strongly preferred), or **Node.js** as a secondary option.

Candidate single-server stacks:

**Option A — Python: FastAPI + MQTT + WebSocket (recommended)**
- **FastAPI** (with Uvicorn) serves the web interface and exposes REST/WebSocket endpoints.
- An embedded **MQTT client** (e.g., `paho-mqtt`) handles rover command relay and telemetry.
- **WebSockets** push live telemetry and video frames to the browser without polling.
- Video streaming is handled via an MJPEG-over-HTTP endpoint or WebSocket frame push — no separate media server needed for low-to-moderate frame rates.
- Everything runs in a single Python process; async I/O (asyncio) keeps latency low.

**Option B — Python: Flask + Flask-SocketIO**
- Simpler to set up; suitable for prototyping.
- Less performant under concurrent load but sufficient for a single GCS client.
- Video can be streamed via a `/video_feed` MJPEG route.

**Option C — Node.js: Express + MQTT.js + Socket.IO**
- A viable alternative if Python proves insufficient.
- Express serves the web interface; Socket.IO handles real-time telemetry push; MQTT.js connects to the broker.
- Video streaming can be handled via an HTTP stream or WebSocket frames.

**Option D — Split server (fallback)**
- If video streaming degrades other services at higher frame rates, it can be offloaded to a separate lightweight process on a different port.
- All other services remain on the primary server.
- This split should only be considered if a measurable bottleneck is observed in practice.
