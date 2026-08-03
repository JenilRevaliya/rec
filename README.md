<div align="center">

# REC
**Realtime Event Capture System**

<img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" />
<img src="https://img.shields.io/badge/Next.js-000000?style=for-the-badge&logo=next.js&logoColor=white" />
<img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
<img src="https://img.shields.io/badge/OpenCV-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white" />
<img src="https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white" />
<img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" />

<br />

REC is an autonomous biometric photography platform. It connects intelligent edge hardware to a centralized cloud to instantly deliver photos to event attendees via facial recognition matching.

</div>

<br />

## Architecture Overview

The system is split into three distinct operational layers.

<table>
<tr>
<td width="33%" valign="top">
<div align="center">
<img src="https://api.iconify.design/lucide:camera.svg" width="32" height="32" />
<br />
<strong>1. Edge Node</strong>
</div>
<br />
<ul style="font-size: 13px;">
<li>Runs locally on photographer hardware.</li>
<li>Processes live webcam streams via OpenCV.</li>
<li>Extracts 512-dimensional facial embeddings using InsightFace.</li>
<li>Queues and processes uploads in the background.</li>
</ul>
</td>
<td width="33%" valign="top">
<div align="center">
<img src="https://api.iconify.design/lucide:server.svg" width="32" height="32" />
<br />
<strong>2. Cloud API</strong>
</div>
<br />
<ul style="font-size: 13px;">
<li>FastAPI microservice running inside Docker.</li>
<li>Handles PostgreSQL database transactions.</li>
<li>Calculates Cosine Similarity between user selfies and event photos.</li>
<li>Manages secure rate limiting and static file serving.</li>
</ul>
</td>
<td width="33%" valign="top">
<div align="center">
<img src="https://api.iconify.design/lucide:smartphone.svg" width="32" height="32" />
<br />
<strong>3. Client Portals</strong>
</div>
<br />
<ul style="font-size: 13px;">
<li>Next.js App Router providing three interfaces.</li>
<li><strong>Admin:</strong> Manage events and users.</li>
<li><strong>Photographer:</strong> Dynamic QR code generation for local networks.</li>
<li><strong>Attendee:</strong> Biometric selfie matching and personal gallery view.</li>
</ul>
</td>
</tr>
</table>

<br />

### Infrastructure Data Flow

```text
┌──────────────────────────────────────┐
│           1. EDGE NODE               │
│                                      │
│  [Webcam] -> [OpenCV] -> [Frames]    │
│                 │                    │
│                 v                    │
│  [InsightFace AI] -> [512d Vector]   │
│                 │                    │
│                 v                    │
│      [Background Uploader]           │
└─────────────────┬────────────────────┘
                  │ (REST API / Uploads)
                  v
┌──────────────────────────────────────┐
│          2. CLOUD ENGINE             │
│                                      │
│  [FastAPI Routes] <-> [Match Engine] │
│         │                   │        │
│         v                   v        │
│    (Static Disk)      (PostgreSQL)   │
└─────────────────┬────────────────────┘
                  │ (JSON / Photo URLs)
                  v
┌──────────────────────────────────────┐
│         3. CLIENT PORTALS            │
│                                      │
│  [Admin UI]   -> Event Management    │
│  [Studio UI]  -> LAN QR Generation   │
│  [Mobile UI]  -> Biometric Retrieval │
└──────────────────────────────────────┘
```

## Operational Workflow

The system follows a strict chronological flow from event creation to photo delivery.

1. <img src="https://api.iconify.design/lucide:calendar-plus.svg" width="14" height="14" style="vertical-align: middle;" /> **Event Initialization**: The Admin creates a new Event ID via the Next.js Admin portal and assigns a designated Photographer.
2. <img src="https://api.iconify.design/lucide:log-in.svg" width="14" height="14" style="vertical-align: middle;" /> **Edge Authentication**: The Photographer boots the local Python Edge Node, authenticates, and binds their session to the active Event ID.
3. <img src="https://api.iconify.design/lucide:aperture.svg" width="14" height="14" style="vertical-align: middle;" /> **Capture Execution**: The Photographer chooses between Live Auto Capture (automated background daemon) or Manual Batch Upload.
4. <img src="https://api.iconify.design/lucide:cpu.svg" width="14" height="14" style="vertical-align: middle;" /> **Data Ingestion**: Photos are analyzed locally. Facial vectors and compressed images are securely transmitted to the Cloud API.
5. <img src="https://api.iconify.design/lucide:qr-code.svg" width="14" height="14" style="vertical-align: middle;" /> **Attendee Onboarding**: Attendees scan a dynamically generated LAN IP QR Code provided by the Photographer.
6. <img src="https://api.iconify.design/lucide:scan-face.svg" width="14" height="14" style="vertical-align: middle;" /> **Biometric Retrieval**: Attendees take a live selfie on their phone. The Cloud API calculates similarity scores and instantly populates a private gallery.

## Technical Details & Features

* <img src="https://api.iconify.design/lucide:zap.svg" width="14" height="14" style="vertical-align: middle;" /> **Zero Blocking UI**: The Python Edge Node uses threading to ensure heavy OpenCV processing never freezes the interface.
* <img src="https://api.iconify.design/lucide:layout-dashboard.svg" width="14" height="14" style="vertical-align: middle;" /> **Dual Edge Dashboards**: The Edge app features a Live Camera UI and a distinct Cloud Management UI for hard deleting and reviewing content.
* <img src="https://api.iconify.design/lucide:network.svg" width="14" height="14" style="vertical-align: middle;" /> **Network Intelligence**: The startup script automatically determines the host machines Local Area Network IP. This ensures Next.js runs seamlessly across all mobile devices on the same Wi-Fi router.
* <img src="https://api.iconify.design/lucide:camera-off.svg" width="14" height="14" style="vertical-align: middle;" /> **Native Browser Fallbacks**: Strict mobile browsers block WebRTC cameras without HTTPS. The User Portal features a fallback mechanism invoking native OS camera applications directly over HTTP.
* <img src="https://api.iconify.design/lucide:database.svg" width="14" height="14" style="vertical-align: middle;" /> **Relational Architecture**: Built on robust PostgreSQL tables for scaling massive event capacities.

## Installation & Deployment

### Prerequisites
* Docker & Docker Compose
* Python 3.10+
* Local Wi-Fi Network (For cross device testing)

### Step 1: Boot Cloud Infrastructure
The core routing, database, and API are containerized for zero configuration boot up.

```bash
# Start Docker containers in the background
./start.sh
```

**Terminal Output Highlights:**
The script automatically provisions PostgreSQL, runs the FastAPI backend on Port `8001`, and exposes the Next.js Portals on Port `3000`. It prints specific local network links that you can directly open on your mobile device.

### Step 2: Boot Edge Node
The photographer client requires direct access to system hardware (Webcam) and must be run locally outside of Docker.

```bash
# Automatically sets up venv, installs dependencies, and runs the dashboard
./edge.sh
```

### Step 3: Default Credentials
Navigate to `http://localhost:8080` to access the Edge Node login. Use the bypass credentials:
* **Username**: `admin`
* **Password**: `rec2026`

## Development Notes

* <img src="https://api.iconify.design/lucide:refresh-cw.svg" width="14" height="14" style="vertical-align: middle;" /> **Volume Mounting**: The `docker-compose.yml` mounts the `/portal` directory. Saving any `.tsx` file will trigger an instant Hot Module Reload in the browser.
* <img src="https://api.iconify.design/lucide:mouse-pointer-click.svg" width="14" height="14" style="vertical-align: middle;" /> **Prefetch Prevention**: The Edge Node uses native JavaScript click handlers instead of standard hyperlink tags to prevent modern browsers from prematurely booting the camera hardware via background prefetching.

<br />

<div align="center">
  <p>Developed by <a href="https://github.com/JenilRevaliya">Jenil Soni</a></p>
</div>
