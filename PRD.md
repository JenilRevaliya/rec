# Product Requirements Document (PRD)

## **Project: REC — Real-time Event Capture**

### Autonomous AI-Powered Photography System with Facial Embedding-Based Photo Retrieval

| Field | Detail |
|---|---|
| **Version** | 1.0.0 |
| **Date** | 2026-07-30 |
| **Status** | Draft |
| **Classification** | Internal / Engineering |

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Product Vision & Goals](#3-product-vision--goals)
4. [System Architecture Overview](#4-system-architecture-overview)
5. [Core Modules — Detailed Specification](#5-core-modules--detailed-specification)
   - 5.1 Camera Control & Tethering Layer
   - 5.2 Lightweight Human Detection Engine
   - 5.3 Auto-Capture Orchestrator
   - 5.4 Image Quality Gate (IQG)
   - 5.5 Intelligent Framing & Composition Engine
   - 5.6 Person Tracking & Unique Track ID System
   - 5.7 Group Detection & Classification Module
   - 5.8 Post-Capture Face Detection & Embedding Pipeline
   - 5.9 Face Clustering & Identity Graph
   - 5.10 User Portal & Selfie-Match Retrieval
6. [Tech Stack](#6-tech-stack)
7. [Photography Intelligence Rules](#7-photography-intelligence-rules)
8. [Data Models & Schema](#8-data-models--schema)
9. [API Contracts](#9-api-contracts)
10. [Processing Pipelines](#10-processing-pipelines)
11. [Performance Requirements](#11-performance-requirements)
12. [Security, Privacy & Compliance](#12-security-privacy--compliance)
13. [Deployment Architecture](#13-deployment-architecture)
14. [Competitive Landscape](#14-competitive-landscape)
15. [Risks & Mitigations](#15-risks--mitigations)
16. [Glossary](#16-glossary)

---

## 1. Executive Summary

**REC (Real-time Event Capture)** is an autonomous, AI-driven photography system that eliminates the need for a human photographer to manually compose, focus, and trigger each shot. The system connects to professional-grade cameras (DSLR, mirrorless, PTZ), continuously scans for human subjects using a lightweight detection model, and automatically captures high-quality photographs — individuals, duos, trios, group shots, and candids — without human intervention.

The **core differentiator** is the **Auto-Capture Pipeline**: the system does not simply record video and extract frames. It actively controls the camera hardware — adjusting autofocus, triggering the shutter at the optimal moment, and (where supported) commanding pan-tilt-zoom — to produce photographs indistinguishable from those taken by a skilled event photographer.

After capture, every image passes through a multi-stage **Image Quality Gate** that discards blurry, poorly-framed, or faceless images. Surviving images are processed through a **deep-learning facial embedding pipeline** (commercially licensed, AuraFace/ArcFace-based) that extracts 512-dimensional face vectors. These embeddings are clustered and stored in a vector database.

When a user later logs into the **Self-Service Portal** and uploads a selfie, the **same** embedding model generates a query vector. A nearest-neighbor search across the stored embeddings retrieves every photograph in which that person appears — across all cameras, all angles, all group sizes — with **≥99% precision at 97% recall**.

> **This is NOT a live surveillance or biometric identification system.** Face detection and embedding extraction happen exclusively on already-captured, saved images. No real-time facial recognition occurs during the camera scanning phase. The live pipeline uses only person-class object detection (bounding boxes) for triggering capture — never facial identity.

---

## 2. Problem Statement

### 2.1 Current State of Event Photography

| Pain Point | Impact |
|---|---|
| **Manual capture dependency** | A single photographer covers ~200-400 guests max; many attendees receive zero photos. |
| **Missed candid moments** | Photographers focus on staged shots; natural interactions go uncaptured. |
| **Post-event delivery delay** | Sorting, tagging, and distributing 2,000+ photos takes days or weeks. |
| **Photo discovery friction** | Guests must scroll through entire galleries to find themselves. |
| **Inconsistent quality** | Fatigue, lighting changes, and human error produce variable results. |
| **No diversity in capture** | Same person gets photographed repeatedly; others are ignored entirely. |

### 2.2 Why Existing Solutions Fall Short

| Solution | Limitation |
|---|---|
| **KwikPic, PicsDrop, SpotMyPhotos** | Post-capture AI only — they automate *delivery*, not *capture*. Still require human photographers. |
| **Photo booth robots** | Fixed-location, posed-only, require guest interaction. Not candid. |
| **Security camera frame extraction** | Produces low-quality, surveillance-style images. No compositional intelligence. |
| **Selfie stations / QR-triggered booths** | Require active guest participation. Miss candid moments entirely. |

### 2.3 The Gap REC Fills

REC is the **only system that automates both the capture and the delivery** — using professional camera hardware, photography composition rules, and deep-learning face matching — to produce and distribute professional-quality candid and portrait photography at scale, without a human operator.

---

## 3. Product Vision & Goals

### 3.1 Vision Statement

> *"Every person at every event, captured beautifully, delivered instantly."*

### 3.2 Primary Goals

| # | Goal | Success Metric |
|---|---|---|
| G1 | **Autonomous capture** — No human operator needed after initial setup | System runs unattended for ≥4 hours continuously |
| G2 | **Universal coverage** — Every attendee captured at least once | ≥95% of attendees appear in ≥1 photo |
| G3 | **Professional quality** — Output indistinguishable from human photographer | Blind test: ≥80% of photos rated "professional" by panel |
| G4 | **Zero blurry output** — Every delivered photo is sharp | 100% of delivered photos pass IQG sharpness threshold |
| G5 | **Instant retrieval** — User finds their photos in <10 seconds | Selfie-to-results latency ≤5s at p95 |
| G6 | **Diversity in subjects** — System actively seeks new faces, not the same person | Gini coefficient of per-person photo count ≤0.35 |
| G7 | **Group intelligence** — Automatically capture duos, trios, and group formations | ≥70% of natural groupings detected and captured |

### 3.3 Non-Goals (Explicitly Out of Scope)

- ❌ Live facial recognition / biometric surveillance during capture
- ❌ Real-time identity tracking (no names or IDs assigned during live operation)
- ❌ Video recording or streaming
- ❌ Audio capture
- ❌ Attendance tracking or access control
- ❌ Any integration with law enforcement or security databases

---

## 4. System Architecture Overview

### 4.1 High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        REC SYSTEM ARCHITECTURE                       │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────┐    ┌─────────────────────────────────────────────┐  │
│  │  CAMERA(S)  │◄──►│         CAMERA CONTROL LAYER                │  │
│  │ DSLR / PTZ  │    │  gPhoto2 · ONVIF · digiCamControl          │  │
│  └─────────────┘    └──────────────┬──────────────────────────────┘  │
│                                    │ Live Preview Stream (Low-Res)   │
│                                    ▼                                 │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │              LIGHTWEIGHT HUMAN DETECTION ENGINE                  │ │
│  │         YOLOv8n / NanoDet-Plus  (Person class only)             │ │
│  │    Runs on live preview @ 15-30 FPS · GPU or CPU                │ │
│  └──────────────┬──────────────────────────────────────────────────┘ │
│                 │ Detection Events (bbox, confidence, count)         │
│                 ▼                                                    │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │              AUTO-CAPTURE ORCHESTRATOR                           │ │
│  │  • Composition Rule Engine (Rule of Thirds, Framing)            │ │
│  │  • Subject Diversity Scheduler (anti-repeat logic)              │ │
│  │  • Group Formation Detector (solo/duo/trio/group)               │ │
│  │  • Shutter Decision Engine (timing, AF-confirm, motion-stop)    │ │
│  │  • PTZ Commander (pan/tilt/zoom for framing — if PTZ camera)    │ │
│  └──────────────┬──────────────────────────────────────────────────┘ │
│                 │ Trigger Shutter / Adjust Settings                  │
│                 ▼                                                    │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │              IMAGE QUALITY GATE (IQG)                            │ │
│  │  Stage 1: Blur Detection (Laplacian Variance)                   │ │
│  │  Stage 2: Face Presence Verification (RetinaFace)               │ │
│  │  Stage 3: Composition Score (NIMA Aesthetic Model)              │ │
│  │  Stage 4: Aspect Ratio Conformance & Smart Crop                 │ │
│  └──────────────┬──────────────────────────────────────────────────┘ │
│                 │ Approved Images Only                               │
│                 ▼                                                    │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │         POST-CAPTURE FACE EMBEDDING PIPELINE                    │ │
│  │  Detect → Align → Embed (AuraFace v1 / Apache 2.0)             │ │
│  │  512-dim normalized vectors per face                            │ │
│  └──────────────┬──────────────────────────────────────────────────┘ │
│                 │ Embeddings + Metadata                              │
│                 ▼                                                    │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │         FACE CLUSTERING & IDENTITY GRAPH                        │ │
│  │  DBSCAN / Chinese Whispers clustering                           │ │
│  │  Cluster → Assign anonymous PersonID                            │ │
│  │  Store in vector DB (Milvus / Qdrant / pgvector)                │ │
│  └──────────────┬──────────────────────────────────────────────────┘ │
│                 │                                                    │
│                 ▼                                                    │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │         USER PORTAL & SELFIE-MATCH RETRIEVAL                    │ │
│  │  Upload selfie → Extract embedding (same model) →              │ │
│  │  ANN search (cosine similarity) → Return matched photos         │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 4.2 Deployment Topology

```
┌──────────────────────────┐     ┌──────────────────────────┐
│    EDGE NODE (On-Site)   │     │     CLOUD BACKEND        │
│                          │     │                          │
│  • Camera(s)             │     │  • Object Storage (S3)   │
│  • GPU Workstation       │ ──► │  • Vector DB (Milvus)    │
│    (detection + capture) │WiFi │  • PostgreSQL            │
│  • Local SSD buffer      │/LAN │  • Face Embedding Worker │
│  • gPhoto2 / ONVIF       │     │  • User Portal (Web)     │
│                          │     │  • API Gateway           │
└──────────────────────────┘     └──────────────────────────┘
```

---

## 5. Core Modules — Detailed Specification

### 5.1 Camera Control & Tethering Layer

#### 5.1.1 Purpose

Provide a unified abstraction over heterogeneous camera hardware — DSLR (Canon, Nikon, Sony), mirrorless, and IP-based PTZ cameras — enabling programmatic control of shutter, autofocus, aperture, ISO, and (where supported) pan/tilt/zoom.

#### 5.1.2 Supported Camera Types & Protocols

| Camera Type | Control Protocol | Zoom Control | AF Control | Shutter Trigger | Live Preview |
|---|---|---|---|---|---|
| **DSLR (USB tethered)** | gPhoto2 / libgphoto2 | ❌ Mechanical lens | ✅ `autofocusdrive` | ✅ `GP_CAPTURE_IMAGE` | ✅ LiveView |
| **Mirrorless (USB/WiFi)** | gPhoto2 / Sony Remote API | ❌ Most lenses manual | ✅ AF-S / AF-C | ✅ Via API | ✅ LiveView / RTSP |
| **PTZ IP Camera** | ONVIF PTZ Service | ✅ Optical zoom `RelativeMove` | ✅ Camera-native AF | ✅ Snapshot endpoint | ✅ RTSP |
| **Raspberry Pi HQ** | libcamera / picamera2 | ❌ C/CS-mount manual | ✅ Software AF | ✅ Direct API | ✅ Direct buffer |

#### 5.1.3 Camera Abstraction Interface

```python
class CameraDriver(ABC):
    @abstractmethod
    def connect(self) -> bool: ...
    @abstractmethod
    def get_live_preview_frame(self) -> np.ndarray: ...
    @abstractmethod
    def trigger_autofocus(self) -> bool: ...
    @abstractmethod
    def capture_image(self) -> CapturedImage: ...
    @abstractmethod
    def set_aperture(self, f_stop: float) -> None: ...
    @abstractmethod
    def set_iso(self, iso: int) -> None: ...
    @abstractmethod
    def set_shutter_speed(self, speed_ms: float) -> None: ...
    @abstractmethod
    def move_ptz(self, pan: float, tilt: float, zoom: float) -> None:
        """Only for PTZ cameras. DSLR raises NotSupported."""
```

#### 5.1.4 DSLR Auto-Capture Flow (gPhoto2)

```
┌──────────┐    USB     ┌──────────────┐
│  DSLR    │◄──────────►│  Edge Node   │
│  Camera  │            │  (Python)    │
└──────────┘            └──────┬───────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        ▼                      ▼                      ▼
   LiveView              AF Trigger              Capture
   Stream                (autofocusdrive)        (GP_CAPTURE_IMAGE)
   (for detection)       (before each shot)      (full-res download)
```

**Critical Notes:**
- LiveView must be toggled OFF briefly before capture on some Canon bodies
- AF confirmation polled with 500ms timeout before shutter trigger
- Image download over USB: ~1.5-3s per RAW+JPEG capture cycle
- Burst mode: continuous capture with 300ms inter-frame delay

#### 5.1.5 PTZ Camera Auto-Tracking (ONVIF)

PID control loop keeps detected subjects centered:

```
Detection Loop (15 FPS):
  → Compute subject centroid from YOLO bbox
  → Compute error: (ex, ey) = centroid - frame_center
  → Normalize to [-1, 1]
  → Dead zone: if |ex| < 0.05 AND |ey| < 0.05 → no move
  → PID output → ONVIF ContinuousMove / RelativeMove
```

**PID Defaults:** `Kp=0.4`, `Ki=0.01`, `Kd=0.1`, `dead_zone=0.05`

#### 5.1.6 Auto-Zoom Logic (PTZ Only)

Adjusts zoom so subject occupies ~35% of frame area. Proportional control with 5% tolerance dead zone and clamped output `[-0.5, 0.5]`.

---

### 5.2 Lightweight Human Detection Engine

#### 5.2.1 Purpose

Detect human presence in live preview using an ultra-lightweight model. Outputs `person` class bounding boxes ONLY. No face recognition or identity matching occurs here.

#### 5.2.2 Model Selection

| Model | Size (FP16) | FPS (GPU) | FPS (CPU) | mAP@0.5 | License |
|---|---|---|---|---|---|
| **YOLOv8n** ⭐ | 6.2 MB | 450+ | 35-50 | 80.4% | AGPL-3.0 (commercial tier available) |
| **NanoDet-Plus** ⭐ | 1.2 MB | — | 60-80 | 73.1% | Apache 2.0 |
| **MobileNet-SSD v2** | 8.6 MB | 200+ | 30-40 | 72.8% | Apache 2.0 |

**Config:** Confidence `0.45`, NMS IoU `0.50`, person class only.

#### 5.2.3 Detection Output

```python
@dataclass
class PersonDetection:
    bbox: Tuple[int, int, int, int]   # (x1, y1, x2, y2)
    confidence: float                  # 0.0-1.0
    centroid: Tuple[int, int]          # (cx, cy)
    bbox_area: int
    frame_fill_ratio: float
    timestamp: float
    camera_id: str
```

#### 5.2.4 Optimization Techniques

- **Frame skipping:** Process every 2nd-3rd frame (2-3x throughput)
- **ROI masking:** Ignore static background regions
- **INT8 Quantization:** via TensorRT/OpenVINO (2-4x speedup)
- **Resolution reduction:** Downscale to 640×480 for detection

---

### 5.3 Auto-Capture Orchestrator

#### 5.3.1 Purpose

The brain of the system. Makes intelligent decisions about **when**, **what**, and **how** to capture based on detection events. This is the **primary differentiating module**.

#### 5.3.2 Capture Decision State Machine

```
SCANNING → (persons detected) → EVALUATING → (composition OK + not in cooldown)
→ FOCUSING → (AF confirmed) → CAPTURING → (image saved) → COOLDOWN → SCANNING
```

#### 5.3.3 Subject Diversity Scheduler

Prevents repeatedly photographing the same person:
- Per-track cooldown: `base_cooldown * (1 + 0.3 * capture_count)`
- Over-photographed subjects (>1.5× average count): cooldown doubled
- Under-photographed subjects get priority boost
- Target metric: **Gini coefficient ≤ 0.35** across all subjects

#### 5.3.4 Capture Mode Matrix

| Mode | Trigger | Aperture | Notes |
|---|---|---|---|
| **Solo Portrait** | 1 person, fill 0.15-0.60 | f/2.8 | Rule-of-thirds, shallow DOF |
| **Duo** | 2 persons within 1.5× body-width | f/4.0 | Symmetric composition |
| **Trio** | 3 persons, triangular proximity | f/5.6 | Balanced triangular frame |
| **Group (4+)** | 4+ clustered within 3× body-width | f/8.0 | All faces visible, wide framing |
| **Candid** | Person not facing camera | 1/250s+ shutter | Silent mode, fast shutter |
| **Interaction** | 2+ persons facing each other | f/3.5 | Conversation capture |

#### 5.3.5 Shutter Timing Intelligence

Does NOT fire instantly on detection. Waits for:
1. **Motion stability** — centroid velocity < 15px between frames for 5+ frames
2. **Face size** — estimated face height ≥ 80px
3. **Composition** — subject in acceptable frame position

---

### 5.4 Image Quality Gate (IQG)

Every captured image passes 4 stages. Failure at any stage = discard.

#### Stage 1: Blur Detection (Laplacian Variance)

```python
gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
score = cv2.Laplacian(gray, cv2.CV_64F).var()
# Threshold per camera: DSLR ~120, mirrorless ~80, PTZ ~50
```

Fallbacks: Brenner Gradient, Tenengrad (Sobel), FFT frequency analysis.

#### Stage 2: Face Presence Verification

Uses RetinaFace (InsightFace). Requires ≥1 face with height ≥60px and det_score ≥0.7.

#### Stage 3: Aesthetic Score (NIMA)

MobileNetV2 backbone, trained on AVA dataset (250K images), EMD loss. Minimum score: 4.5/10.

#### Stage 4: Aspect Ratio Conformance & Smart Crop

| Output | Ratio | Use Case |
|---|---|---|
| Portrait | 4:5 | Instagram, mobile |
| Landscape | 3:2 | Gallery, print |
| Square | 1:1 | Profile, social |
| Story | 9:16 | Stories format |
| Original | Native | Archive, editorial |

**Smart Crop Rules:** Face at rule-of-thirds intersections, never crop at joints, 15% padding around outermost faces.

**Expected Yield:** ~55-70% of raw captures survive IQG.

---

### 5.5 Intelligent Framing & Composition Engine

#### 5.5.1 Rule of Thirds

Face centroid scored against 4 power points (1/3 and 2/3 intersections). Portraits prefer upper power points (eyes in upper third).

#### 5.5.2 Portrait Rules

| Rule | Implementation |
|---|---|
| Eyes in upper third | Face top-edge y < 33% of frame height |
| Headroom | 10-20% space above head |
| Lead room | More space in gaze direction |
| Background simplicity | Low edge density outside subject bbox |
| No joint cropping | Never crop at neck, wrist, elbow, knee |

#### 5.5.3 Group Composition

| Size | Formation | Strategy |
|---|---|---|
| Duo | Side-by-side or angled | Symmetric, both faces upper-third |
| Trio | Triangular (1+2) | Triangle center at frame center |
| 4-6 | Two-row staggered | f/5.6-8.0, all faces above midline |
| 7+ | Multi-row height stagger | Max width, f/8-11, deep DOF |

---

### 5.6 Persistent Identity System (PIS) — Lightweight Real-Time Person Re-ID & Coverage Engine

> **This module is the backbone of fair, diverse, and consistent capture.** Without it, the diversity scheduler (5.3.3) cannot function — it would treat every frame-to-frame track loss as a "new person" and repeatedly photograph the same individual while ignoring others.

#### 5.6.1 The Core Problem

Standard multi-object trackers (ByteTrack, DeepSORT) assign a **local Track ID** that persists only while a person remains continuously visible in consecutive frames within a single camera. The moment any of these events occur, the Track ID is **destroyed and a new one is created**:

| Event | What Happens Without PIS |
|---|---|
| Person walks behind a pillar for 3 seconds | New Track ID — system thinks it's a new person |
| Person exits frame and re-enters 30 seconds later | New Track ID — gets photographed again as if first time |
| Person moves from Camera A to Camera B | Completely new Track ID — no link to previous captures |
| Person sits down / changes posture | May lose tracking — new Track ID on re-detection |
| Person turns around (back to camera) | Detection may drop → re-detected as new person |

**Result:** The same person gets 15+ photos while others get zero. The diversity scheduler's cooldown is useless because it can't recognize the person is the same.

#### 5.6.2 Solution Architecture — Two-Tier Identity System

```
┌─────────────────────────────────────────────────────────────────┐
│                    TIER 1: LOCAL TRACKER (per camera)            │
│                                                                 │
│  ByteTrack / BoT-SORT → Frame-to-frame Track ID                │
│  • Fast (pure IoU + Kalman, no CNN)                             │
│  • Handles intra-frame association only                         │
│  • Produces: local_track_id (short-lived)                       │
└────────────────────┬────────────────────────────────────────────┘
                     │ Every N frames (or on track creation):
                     │ Extract appearance descriptor
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│              TIER 2: GLOBAL IDENTITY LEDGER (cross-everything)  │
│                                                                 │
│  • Maintains a gallery of Persistent Identities (PID)           │
│  • Each PID has: multi-feature appearance signature             │
│  • Matches new tracks against gallery using multi-point scoring │
│  • Survives: re-entry, occlusion, camera switch, posture change │
│  • Produces: persistent_identity_id (event-lifetime)            │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  COVERAGE FAIRNESS ENGINE                               │    │
│  │  • Per-PID capture count, last-capture timestamp        │    │
│  │  • Adaptive cooldown, priority queue for under-covered  │    │
│  │  • Diversity score monitoring (Gini coefficient)        │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

#### 5.6.3 Multi-Feature Appearance Descriptor

The system does **NOT** rely on a single feature. It fuses multiple lightweight signals into a composite **Appearance Signature** for each person. This makes re-identification robust regardless of pose, posture, or position.

```python
@dataclass
class AppearanceSignature:
    """Multi-feature descriptor for persistent re-identification."""

    # === Feature 1: Deep Appearance Embedding (primary) ===
    # OSNet x0.25 — only 0.2M params, MIT license
    # Input: torso crop (128×256 px), Output: 512-dim normalized vector
    deep_embedding: np.ndarray          # shape (512,), L2-normalized

    # === Feature 2: Color Histogram (fast auxiliary) ===
    # HSV histogram of upper-body region (clothing)
    # Computed in <1ms, lighting-robust via HSV space
    upper_body_color_hist: np.ndarray   # shape (48,) — 16H × 3S bins
    lower_body_color_hist: np.ndarray   # shape (48,) — separate for pants/skirt

    # === Feature 3: Body Proportions (pose-invariant) ===
    # Aspect ratio of bounding box (height/width)
    # Relative torso-to-leg ratio estimated from bbox
    body_aspect_ratio: float            # height / width of person bbox
    estimated_height_class: str         # 'short', 'medium', 'tall' (relative)

    # === Feature 4: Spatial-Temporal Context ===
    # Where and when was this person last seen?
    last_known_position: Tuple[int, int]  # (x, y) in frame coords
    last_known_camera: str
    last_seen_timestamp: float
    movement_direction: float             # angle in degrees (0-360)

    # === Metadata ===
    confidence: float                     # 0.0-1.0, quality of this signature
    update_count: int                     # how many observations have refined this
```

#### 5.6.4 Feature Extraction Pipeline (Runs Per Detection, Every Nth Frame)

```python
class AppearanceExtractor:
    """
    Lightweight multi-feature extraction.
    Total inference: ~8ms per person on GPU, ~25ms on CPU.
    Runs every 5th frame (not every frame) to save compute.
    """

    def __init__(self):
        # OSNet x0.25 — ultra-light: 0.2M params, 512-dim output
        self.reid_model = torchreid.utils.FeatureExtractor(
            model_name='osnet_x0_25',
            device='cuda' if torch.cuda.is_available() else 'cpu'
        )
        self.extraction_interval = 5  # extract every 5th frame

    def extract(self, frame: np.ndarray, bbox: BBox,
                frame_idx: int) -> Optional[AppearanceSignature]:

        if frame_idx % self.extraction_interval != 0:
            return None  # Skip this frame for efficiency

        x1, y1, x2, y2 = bbox
        person_crop = frame[y1:y2, x1:x2]

        if person_crop.size == 0:
            return None

        h, w = person_crop.shape[:2]

        # --- Feature 1: Deep embedding (OSNet) ---
        resized = cv2.resize(person_crop, (128, 256))
        deep_emb = self.reid_model([resized])[0].cpu().numpy()
        deep_emb /= np.linalg.norm(deep_emb)  # L2 normalize

        # --- Feature 2: Color histograms (upper/lower body) ---
        mid_y = h // 2
        upper = person_crop[:mid_y, :]
        lower = person_crop[mid_y:, :]
        upper_hist = self._compute_hsv_histogram(upper)
        lower_hist = self._compute_hsv_histogram(lower)

        # --- Feature 3: Body proportions ---
        aspect = h / max(w, 1)
        height_class = 'short' if aspect < 2.5 else ('tall' if aspect > 3.5 else 'medium')

        return AppearanceSignature(
            deep_embedding=deep_emb,
            upper_body_color_hist=upper_hist,
            lower_body_color_hist=lower_hist,
            body_aspect_ratio=aspect,
            estimated_height_class=height_class,
            last_known_position=((x1+x2)//2, (y1+y2)//2),
            last_known_camera=self.camera_id,
            last_seen_timestamp=time.monotonic(),
            movement_direction=0.0,
            confidence=0.8,
            update_count=1
        )

    @staticmethod
    def _compute_hsv_histogram(region: np.ndarray) -> np.ndarray:
        """HSV color histogram — 16 hue bins × 3 saturation bins = 48 dims."""
        hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [16, 3], [0, 180, 0, 256])
        hist = cv2.normalize(hist, hist).flatten()
        return hist
```

#### 5.6.5 Multi-Point Matching Score (Weighted Fusion)

When a new track appears (or a lost track needs re-identification), the system computes a **composite similarity score** against every Persistent Identity in the gallery:

```python
class IdentityMatcher:
    """
    Multi-feature weighted matching.
    Uses 4 independent signals to decide if two observations are the same person.
    """

    # Weights (tunable per deployment)
    W_DEEP      = 0.55   # Deep appearance embedding (strongest signal)
    W_COLOR     = 0.20   # Clothing color histograms
    W_BODY      = 0.10   # Body proportions
    W_SPATIAL   = 0.15   # Spatial-temporal plausibility

    MATCH_THRESHOLD = 0.60   # Minimum composite score to consider a match
    HIGH_CONFIDENCE = 0.80   # Above this = certain match

    def compute_similarity(self, query: AppearanceSignature,
                           gallery_entry: PersistentIdentity) -> MatchResult:

        # 1. Deep embedding cosine similarity (0.0 to 1.0)
        deep_sim = np.dot(query.deep_embedding,
                          gallery_entry.appearance.deep_embedding)

        # 2. Color histogram correlation (Bhattacharyya, 0.0 to 1.0)
        upper_sim = cv2.compareHist(
            query.upper_body_color_hist,
            gallery_entry.appearance.upper_body_color_hist,
            cv2.HISTCMP_CORREL
        )
        lower_sim = cv2.compareHist(
            query.lower_body_color_hist,
            gallery_entry.appearance.lower_body_color_hist,
            cv2.HISTCMP_CORREL
        )
        color_sim = (upper_sim + lower_sim) / 2.0

        # 3. Body proportion similarity
        aspect_diff = abs(query.body_aspect_ratio -
                          gallery_entry.appearance.body_aspect_ratio)
        body_sim = max(0, 1.0 - aspect_diff / 2.0)

        # 4. Spatial-temporal plausibility
        spatial_sim = self._spatial_plausibility(query, gallery_entry)

        # --- Weighted fusion ---
        composite = (
            self.W_DEEP * deep_sim +
            self.W_COLOR * max(0, color_sim) +
            self.W_BODY * body_sim +
            self.W_SPATIAL * spatial_sim
        )

        return MatchResult(
            score=composite,
            deep_score=deep_sim,
            color_score=color_sim,
            body_score=body_sim,
            spatial_score=spatial_sim,
            is_match=composite >= self.MATCH_THRESHOLD,
            is_high_confidence=composite >= self.HIGH_CONFIDENCE
        )

    def _spatial_plausibility(self, query: AppearanceSignature,
                               gallery: PersistentIdentity) -> float:
        """
        A person can't teleport. Score based on:
        - Time elapsed since last seen
        - Distance from last known position
        - Whether they're on the same or adjacent camera
        """
        time_gap = query.last_seen_timestamp - gallery.appearance.last_seen_timestamp
        if time_gap < 0:
            return 0.0

        # Same camera: check pixel distance vs time (max walking speed ~2m/s)
        if query.last_known_camera == gallery.appearance.last_known_camera:
            pixel_dist = np.linalg.norm(
                np.array(query.last_known_position) -
                np.array(gallery.appearance.last_known_position)
            )
            max_plausible_dist = time_gap * 200  # ~200 px/sec walking speed
            if pixel_dist > max_plausible_dist:
                return 0.1  # Implausible but not impossible
            return 1.0 - (pixel_dist / max(max_plausible_dist, 1))

        # Different camera: just check time plausibility
        # Person needs at least 5 seconds to walk between cameras
        if time_gap < 5.0:
            return 0.1
        elif time_gap < 60.0:
            return 0.8  # Very plausible
        else:
            return 0.5  # Possible but uncertain
```

#### 5.6.6 Global Identity Ledger

The central data structure that survives the entire event session:

```python
class GlobalIdentityLedger:
    """
    Maintains persistent identities across all cameras for the entire event.
    This is the single source of truth for "who has been seen and how many
    times they've been photographed."
    """

    def __init__(self):
        self.identities: Dict[str, PersistentIdentity] = {}
        self.matcher = IdentityMatcher()
        self.ema_alpha = 0.85  # EMA momentum for embedding updates

    def register_or_match(self, local_track_id: str,
                          signature: AppearanceSignature) -> str:
        """
        Given a new appearance observation, either:
        1. Match to existing PID → return existing PID
        2. Create new PID → return new PID
        """
        best_match = None
        best_score = 0.0

        for pid, identity in self.identities.items():
            result = self.matcher.compute_similarity(signature, identity)
            if result.is_match and result.score > best_score:
                best_match = pid
                best_score = result.score

        if best_match:
            # Update existing identity with EMA
            self._update_identity(best_match, signature)
            return best_match
        else:
            # New person — create persistent identity
            new_pid = f"PID-{uuid4().hex[:8]}"
            self.identities[new_pid] = PersistentIdentity(
                pid=new_pid,
                appearance=signature,
                first_seen=signature.last_seen_timestamp,
                capture_count=0,
                last_capture_time=0.0,
                capture_modes_used=set(),
                group_combinations_captured=set(),
                cameras_seen_on=set([signature.last_known_camera])
            )
            return new_pid

    def _update_identity(self, pid: str, new_sig: AppearanceSignature):
        """
        EMA update: smoothly blend new observation into existing identity.
        Prevents noisy single-frame observations from corrupting the signature.
        """
        identity = self.identities[pid]
        old = identity.appearance
        α = self.ema_alpha

        # EMA on deep embedding
        blended = α * old.deep_embedding + (1 - α) * new_sig.deep_embedding
        blended /= np.linalg.norm(blended)  # Re-normalize

        # EMA on color histograms
        old.upper_body_color_hist = α * old.upper_body_color_hist + (1 - α) * new_sig.upper_body_color_hist
        old.lower_body_color_hist = α * old.lower_body_color_hist + (1 - α) * new_sig.lower_body_color_hist

        old.deep_embedding = blended
        old.last_known_position = new_sig.last_known_position
        old.last_known_camera = new_sig.last_known_camera
        old.last_seen_timestamp = new_sig.last_seen_timestamp
        old.confidence = min(1.0, old.confidence + 0.02)
        old.update_count += 1
        identity.cameras_seen_on.add(new_sig.last_known_camera)


@dataclass
class PersistentIdentity:
    pid: str
    appearance: AppearanceSignature
    first_seen: float
    capture_count: int
    last_capture_time: float
    capture_modes_used: Set[str]         # {'solo', 'duo', 'group', 'candid'}
    group_combinations_captured: Set[FrozenSet[str]]  # sets of PIDs in group photos
    cameras_seen_on: Set[str]
```

#### 5.6.7 Coverage Fairness Engine

This is the decision-making layer that uses PID capture history to enforce **equitable coverage**:

```python
class CoverageFairnessEngine:
    """
    Ensures every attendee gets photographed, and no one person dominates.
    Uses the Global Identity Ledger as its data source.
    """

    BASE_COOLDOWN = 15.0        # seconds between captures of same PID
    MAX_SOLO_CAPTURES = 8       # cap solo portraits per person
    MAX_TOTAL_CAPTURES = 20     # cap total appearances per person
    GINI_TARGET = 0.35          # target Gini coefficient (0 = perfectly equal)

    def should_capture(self, pid: str, capture_mode: str,
                       group_pids: Optional[Set[str]],
                       ledger: GlobalIdentityLedger) -> CaptureDecision:

        identity = ledger.identities[pid]
        now = time.monotonic()

        # --- Check 1: Hard cap on total captures ---
        if identity.capture_count >= self.MAX_TOTAL_CAPTURES:
            return CaptureDecision(allowed=False,
                reason=f"PID {pid} hit max capture limit ({self.MAX_TOTAL_CAPTURES})")

        # --- Check 2: Mode-specific caps ---
        if capture_mode == 'solo':
            solo_count = sum(1 for m in identity.capture_modes_used if m == 'solo')
            if solo_count >= self.MAX_SOLO_CAPTURES:
                return CaptureDecision(allowed=False,
                    reason=f"PID {pid} has enough solo portraits")

        # --- Check 3: Adaptive cooldown ---
        cooldown = self.BASE_COOLDOWN * (1 + 0.5 * identity.capture_count)
        time_since_last = now - identity.last_capture_time
        if time_since_last < cooldown:
            return CaptureDecision(allowed=False,
                reason=f"PID {pid} still in cooldown ({cooldown - time_since_last:.0f}s remaining)")

        # --- Check 4: Group combination novelty ---
        if group_pids and len(group_pids) > 1:
            combo = frozenset(group_pids)
            if combo in identity.group_combinations_captured:
                # This exact group has already been captured — lower priority
                return CaptureDecision(allowed=True, priority=0.3,
                    reason="Group already captured, low priority re-capture")

        # --- Check 5: Under-photographed priority boost ---
        avg_count = self._compute_average_captures(ledger)
        if identity.capture_count < avg_count * 0.5:
            return CaptureDecision(allowed=True, priority=1.0,
                reason=f"PID {pid} under-photographed — PRIORITY BOOST")

        return CaptureDecision(allowed=True, priority=0.6,
            reason="Normal capture allowed")

    def get_priority_queue(self, ledger: GlobalIdentityLedger,
                           visible_pids: Set[str]) -> List[Tuple[str, float]]:
        """
        Rank currently visible PIDs by capture priority.
        Under-photographed people go to the front of the queue.
        """
        priorities = []
        avg_count = self._compute_average_captures(ledger)

        for pid in visible_pids:
            identity = ledger.identities.get(pid)
            if not identity:
                priorities.append((pid, 1.0))  # New person — highest priority
                continue

            # Inverse of capture count relative to average
            if avg_count == 0:
                score = 1.0
            else:
                score = max(0.1, 1.0 - (identity.capture_count / (avg_count * 2)))

            # Bonus for never-captured
            if identity.capture_count == 0:
                score = 1.0

            # Bonus for not captured in this mode
            # (e.g., they have solo shots but no candids)
            score *= 1.0  # can be augmented per capture_mode check

            priorities.append((pid, score))

        return sorted(priorities, key=lambda x: x[1], reverse=True)

    def compute_gini_coefficient(self, ledger: GlobalIdentityLedger) -> float:
        """
        Gini coefficient of capture distribution.
        0.0 = perfectly equal, 1.0 = one person has all photos.
        Target: ≤ 0.35
        """
        counts = sorted([id.capture_count for id in ledger.identities.values()])
        n = len(counts)
        if n == 0:
            return 0.0
        total = sum(counts)
        if total == 0:
            return 0.0
        cumulative = sum((2 * (i + 1) - n - 1) * c for i, c in enumerate(counts))
        return cumulative / (n * total)

    @staticmethod
    def _compute_average_captures(ledger: GlobalIdentityLedger) -> float:
        if not ledger.identities:
            return 0.0
        return sum(id.capture_count for id in ledger.identities.values()) / len(ledger.identities)
```

#### 5.6.8 Integration: How PIS Connects to the Auto-Capture Orchestrator

```
Detection (YOLOv8n)
    │
    ▼
Local Tracker (ByteTrack)
    │ local_track_id
    ▼
Appearance Extractor (every 5th frame)
    │ AppearanceSignature
    ▼
Global Identity Ledger
    │ register_or_match() → persistent_identity_id (PID)
    ▼
Coverage Fairness Engine
    │ should_capture(PID, mode, group) → CaptureDecision
    │ get_priority_queue(visible_PIDs) → ranked list
    ▼
Auto-Capture Orchestrator
    │ Captures highest-priority, cooldown-cleared PID first
    │ Records: identity.capture_count++, last_capture_time = now
    ▼
Shutter Trigger
```

#### 5.6.9 Performance Budget

| Component | Inference Time (GPU) | Inference Time (CPU) | Frequency |
|---|---|---|---|
| OSNet x0.25 (per person crop) | ~3 ms | ~12 ms | Every 5th frame |
| HSV Histogram (upper+lower) | <1 ms | <1 ms | Every 5th frame |
| Body proportion calc | <0.1 ms | <0.1 ms | Every 5th frame |
| Gallery matching (vs 200 PIDs) | ~2 ms | ~5 ms | On new track / re-entry |
| EMA update | <0.1 ms | <0.1 ms | On match |
| **Total per person per extraction cycle** | **~6 ms** | **~18 ms** | **Every 5th frame** |

With 10 people visible and extraction every 5th frame at 15 FPS (= 3 extractions/sec): **GPU: ~18ms/sec**, **CPU: ~54ms/sec** — well within real-time budget.

#### 5.6.10 Robustness Matrix — What Each Feature Handles

| Scenario | Deep Embedding | Color Histogram | Body Proportions | Spatial-Temporal |
|---|---|---|---|---|
| Same person, same pose | ✅ Strong | ✅ Strong | ✅ Strong | ✅ Strong |
| Same person, turned around | ⚠️ Moderate | ✅ Strong | ✅ Strong | ✅ Strong |
| Same person, sitting down | ⚠️ Moderate | ✅ Strong | ⚠️ Changed | ✅ Strong |
| Same person, different camera | ✅ Strong | ✅ Strong | ✅ Strong | ⚠️ Time-based |
| Same person, after 5 min absence | ✅ Strong | ✅ Strong | ✅ Strong | ⚠️ Weak |
| Same person, jacket removed | ⚠️ Moderate | ❌ Changed | ✅ Strong | ✅ Strong |
| Different person, similar clothes | ❌ Different | ✅ Similar | ⚠️ May match | ✅ Separates |
| Different person, different clothes | ✅ Different | ✅ Different | ✅ Different | ✅ Different |

**Key insight:** No single feature is reliable in all scenarios. The weighted fusion ensures that even when 1-2 features fail, the remaining features maintain correct identity.

#### 5.6.11 Tech Stack for PIS

| Component | Technology | License | Size |
|---|---|---|---|
| Deep Re-ID model | OSNet x0.25 (torchreid) | MIT | 0.2M params, ~0.8 MB |
| Color histogram | OpenCV `cv2.calcHist` | Apache 2.0 | Built-in |
| Local tracker | ByteTrack | MIT | Pure Python |
| Local tracker (PTZ) | BoT-SORT | MIT | Pure Python |
| Gallery storage | In-memory dict + periodic Redis snapshot | BSD | — |
| Similarity metrics | NumPy dot product + OpenCV `compareHist` | BSD / Apache 2.0 | — |

---

### 5.7 Group Detection & Classification Module

#### 5.7.1 Purpose

Automatically detect when people form natural social groupings (duos, trios, clusters) and classify the group type to trigger appropriate capture modes.

#### 5.7.2 Proximity-Based Group Detection

```python
def detect_groups(detections: List[PersonDetection],
                  proximity_threshold: float = 1.5) -> List[Group]:
    """
    Groups people based on spatial proximity.
    proximity_threshold: multiple of average body width.
    """
    # 1. Compute pairwise centroid distances
    centroids = [d.centroid for d in detections]
    avg_body_width = np.mean([d.bbox[2] - d.bbox[0] for d in detections])
    max_distance = avg_body_width * proximity_threshold

    # 2. DBSCAN clustering on centroid positions
    coords = np.array(centroids)
    clustering = DBSCAN(eps=max_distance, min_samples=1).fit(coords)

    # 3. Build group objects
    groups = []
    for label in set(clustering.labels_):
        if label == -1:
            continue
        members = [d for d, l in zip(detections, clustering.labels_) if l == label]
        groups.append(Group(
            members=members,
            size=len(members),
            group_type=classify_group(len(members)),
            geometric_center=np.mean([m.centroid for m in members], axis=0)
        ))
    return groups
```

#### 5.7.3 Group Classification

| Count | Type | Trigger |
|---|---|---|
| 1 | `SOLO` | Individual portrait mode |
| 2 | `DUO` | Two-person composition |
| 3 | `TRIO` | Triangular arrangement |
| 4-6 | `SMALL_GROUP` | Multi-person wide frame |
| 7+ | `LARGE_GROUP` | Panoramic/ultra-wide mode |

#### 5.7.4 Interaction Detection (Candid Trigger)

People facing each other (detected via face landmark orientation or body pose) triggers the `INTERACTION` capture mode for candid conversational shots.

```python
def is_interaction(person_a: PersonDetection, person_b: PersonDetection,
                   max_distance: float, face_landmarks: dict) -> bool:
    distance = euclidean(person_a.centroid, person_b.centroid)
    if distance > max_distance:
        return False

    # Check if they face each other using nose-to-ear landmark direction
    a_facing_right = face_landmarks[person_a.track_id].nose_x < face_landmarks[person_a.track_id].right_ear_x
    b_facing_left = face_landmarks[person_b.track_id].nose_x > face_landmarks[person_b.track_id].left_ear_x

    return (a_facing_right and b_facing_left) or (not a_facing_right and not b_facing_left)
```

---

### 5.8 Post-Capture Face Detection & Embedding Pipeline

#### 5.8.1 Purpose

After an image passes the IQG, extract facial embeddings from every visible face. These embeddings are the foundation of the selfie-match retrieval system.

> **Timing:** This runs AFTER capture, on saved images. NOT during live camera operation.

#### 5.8.2 Pipeline: Detect → Align → Embed

```
Approved Image
    │
    ▼
┌────────────────────┐
│  RetinaFace Detect │  → Bounding boxes + 5 landmarks per face
│  (InsightFace)     │     (left_eye, right_eye, nose, left_mouth, right_mouth)
└────────┬───────────┘
         ▼
┌────────────────────┐
│  Face Alignment    │  → Affine transform to normalize pose
│  (ArcFace align)   │     112×112 pixel aligned face chip
└────────┬───────────┘
         ▼
┌────────────────────┐
│  AuraFace v1       │  → 512-dimensional L2-normalized embedding vector
│  (Apache 2.0)      │     Cosine similarity for matching
└────────┬───────────┘
         ▼
   Store: (image_id, face_index, embedding[512], bbox, landmarks, metadata)
```

#### 5.8.3 Embedding Model: AuraFace v1

| Property | Value |
|---|---|
| **Architecture** | IResNet-100 (Improved ResNet) |
| **Loss Function** | Additive Angular Margin (ArcFace) |
| **Embedding Dimension** | 512 |
| **Normalization** | L2-normalized (unit hypersphere) |
| **Similarity Metric** | Cosine similarity |
| **License** | **Apache 2.0** (code + weights) |
| **Commercial Use** | ✅ Explicitly permitted |
| **Source** | `fal/AuraFace-v1` on HuggingFace |

**Why AuraFace over alternatives:**
- **InsightFace/ArcFace `buffalo_l`:** MIT code, but weights are **non-commercial research only**
- **FaceNet:** Ambiguous licensing on pre-trained weights
- **AuraFace:** Apache 2.0 on BOTH code AND weights — safe for commercial deployment

#### 5.8.4 Face Embedding Quality Filters

Before storing an embedding, validate:
- Face detection confidence ≥ 0.80
- Face alignment quality (landmark symmetry check)
- Minimum face size: 60×60 pixels after alignment
- Yaw angle ≤ 45° (extreme profile views produce unreliable embeddings)
- No occlusion (sunglasses, masks) — detected via landmark visibility score

#### 5.8.5 Embedding Storage Schema

```sql
CREATE TABLE face_embeddings (
    id              UUID PRIMARY KEY,
    image_id        UUID REFERENCES images(id),
    face_index      INT,                    -- 0-indexed face within image
    embedding       VECTOR(512),            -- pgvector or Milvus
    bbox            JSONB,                  -- {x1, y1, x2, y2}
    landmarks       JSONB,                  -- 5-point landmarks
    det_score       FLOAT,
    yaw_angle       FLOAT,
    cluster_id      UUID REFERENCES face_clusters(id),
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Vector similarity index (HNSW for fast ANN search)
CREATE INDEX idx_embedding_hnsw ON face_embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 200);
```

---

### 5.9 Face Clustering & Identity Graph

#### 5.9.1 Purpose

Group all face embeddings belonging to the same person into clusters, assigning each cluster an anonymous `PersonID`. This pre-computation enables instant photo retrieval when a user uploads a selfie.

#### 5.9.2 Clustering Algorithm Selection

| Algorithm | Best For | Speed | Outlier Handling |
|---|---|---|---|
| **DBSCAN** ⭐ | Small-medium events (<5K faces) | Moderate | Excellent (labels noise) |
| **Chinese Whispers** | Large events (>10K faces) | Fast (time-linear) | Moderate |
| **Agglomerative** | High-precision requirements | Slow | Good |

**Recommended:** DBSCAN with `eps=0.45`, `min_samples=2` (tuned for cosine distance on AuraFace embeddings).

#### 5.9.3 Clustering Pipeline

```
1. Collect all embeddings from event
2. Compute pairwise cosine distance matrix (or use ANN approximation)
3. Run DBSCAN(eps=0.45, min_samples=2, metric='cosine')
4. Each cluster → new anonymous PersonID (UUID)
5. Noise points (label=-1) → singleton clusters (still searchable)
6. Store cluster assignments: face_embedding.cluster_id = PersonID
```

#### 5.9.4 Incremental Clustering (Real-Time Mode)

For live events where images stream in continuously:

```python
def assign_to_cluster(new_embedding: np.ndarray,
                      existing_clusters: Dict[str, List[np.ndarray]],
                      threshold: float = 0.55) -> str:
    """
    Try to match new embedding to existing cluster.
    If no match, create new cluster.
    """
    best_match_id = None
    best_similarity = 0.0

    for cluster_id, embeddings in existing_clusters.items():
        centroid = np.mean(embeddings, axis=0)
        centroid /= np.linalg.norm(centroid)
        sim = np.dot(new_embedding, centroid)

        if sim > best_similarity and sim >= threshold:
            best_similarity = sim
            best_match_id = cluster_id

    if best_match_id:
        existing_clusters[best_match_id].append(new_embedding)
        return best_match_id
    else:
        new_id = str(uuid4())
        existing_clusters[new_id] = [new_embedding]
        return new_id
```

---

### 5.10 User Portal & Selfie-Match Retrieval

#### 5.10.1 Purpose

Allow event attendees to find all their photos by uploading a single selfie. The portal uses the **same AuraFace embedding model** to vectorize the selfie, then performs approximate nearest-neighbor (ANN) search against all stored event embeddings.

#### 5.10.2 User Flow

```
1. User receives QR code / link at event
2. Opens portal in mobile browser (no app install required)
3. Uploads or takes a selfie
4. System extracts face → generates 512-dim embedding
5. ANN search against event's face embeddings (cosine similarity)
6. Returns all images where similarity ≥ threshold (0.55)
7. User views, downloads, or shares their photos
```

#### 5.10.3 Matching Algorithm

```python
def find_user_photos(selfie_embedding: np.ndarray,
                     event_id: str,
                     similarity_threshold: float = 0.55,
                     top_k: int = 500) -> List[MatchResult]:
    """
    ANN search using vector database (Milvus/Qdrant/pgvector).
    Returns images sorted by similarity score.
    """
    results = vector_db.search(
        collection=f"event_{event_id}",
        query_vector=selfie_embedding,
        metric="cosine",
        top_k=top_k,
        filter={"det_score": {"$gte": 0.80}}
    )

    matches = [
        MatchResult(
            image_id=r.image_id,
            similarity=r.score,
            face_bbox=r.metadata["bbox"],
            image_url=generate_presigned_url(r.image_id)
        )
        for r in results
        if r.score >= similarity_threshold
    ]

    return sorted(matches, key=lambda m: m.similarity, reverse=True)
```

#### 5.10.4 Matching Thresholds

| Threshold | Precision | Recall | Use Case |
|---|---|---|---|
| 0.65 | ~99.5% | ~85% | High-security / verification |
| **0.55** ⭐ | ~99.0% | ~95% | **Default event retrieval** |
| 0.45 | ~95% | ~99% | Maximum recall (may include lookalikes) |

#### 5.10.5 Anti-Spoofing (Liveness Detection)

To prevent users from uploading photos of others:
- **Passive liveness:** Analyze selfie for screen reflection patterns, moire artifacts
- **Active liveness (optional):** Request user to blink or turn head during selfie capture
- **Metadata check:** Verify selfie EXIF indicates front-facing camera, recent timestamp

---

## 6. Tech Stack

### 6.1 Complete Technology Matrix

#### Edge Node (On-Site Hardware)

| Layer | Technology | Version | License | Purpose |
|---|---|---|---|---|
| **OS** | Ubuntu Server 22.04 LTS | 22.04 | Free | Edge node operating system |
| **Runtime** | Python | 3.11+ | PSF | Primary application language |
| **Camera Control** | libgphoto2 + python-gphoto2 | 2.5.x | LGPL-2.1 | DSLR/mirrorless tethering |
| **Camera Control** | onvif-zeep | 0.3.x | MIT | PTZ camera ONVIF control |
| **Camera Discovery** | wsdiscovery | 2.0.x | MIT | ONVIF camera auto-discovery |
| **Video Stream** | OpenCV (cv2) | 4.9+ | Apache 2.0 | RTSP/LiveView frame capture |
| **Detection** | Ultralytics YOLOv8n | 8.x | AGPL-3.0 / Commercial | Person detection (live) |
| **Detection (Alt)** | NanoDet-Plus | 1.0 | Apache 2.0 | Lightweight fallback detector |
| **Tracking** | ByteTrack | — | MIT | Multi-object tracking |
| **Tracking (PTZ)** | BoT-SORT | — | MIT | Camera-motion-compensated tracking |
| **Inference Accel** | TensorRT / ONNX Runtime | 8.x / 1.17 | Apache 2.0 | INT8/FP16 model optimization |
| **GPU** | NVIDIA CUDA + cuDNN | 12.x | Proprietary | GPU acceleration |

#### Cloud Backend

| Layer | Technology | Version | License | Purpose |
|---|---|---|---|---|
| **API Framework** | FastAPI | 0.110+ | MIT | REST API server |
| **Task Queue** | Celery + Redis | 5.x / 7.x | BSD / BSD | Async embedding jobs |
| **Database** | PostgreSQL + pgvector | 16+ / 0.7+ | PostgreSQL / BSD | Relational + vector storage |
| **Vector DB (Alt)** | Milvus or Qdrant | 2.4+ / 1.9+ | Apache 2.0 | Dedicated vector search (at scale) |
| **Object Storage** | MinIO (self-hosted) or AWS S3 | — | AGPL-3.0 / — | Image file storage |
| **Face Detection** | RetinaFace (InsightFace) | 0.7+ | MIT | Post-capture face detection |
| **Face Alignment** | InsightFace alignment | 0.7+ | MIT | 5-point landmark alignment |
| **Face Embedding** | **AuraFace v1** | 1.0 | **Apache 2.0** | 512-dim facial embeddings |
| **Blur Detection** | OpenCV Laplacian | 4.9+ | Apache 2.0 | Image sharpness scoring |
| **Aesthetic Score** | NIMA (MobileNetV2) | — | Apache 2.0 | Image quality assessment |
| **Clustering** | scikit-learn DBSCAN | 1.4+ | BSD | Face embedding clustering |
| **Re-ID (Phase 2)** | OSNet via torchreid | — | MIT | Cross-camera person Re-ID |
| **Containerization** | Docker + Docker Compose | 24+ | Apache 2.0 | Service packaging |
| **Reverse Proxy** | Nginx / Traefik | — | BSD / MIT | API gateway, SSL termination |
| **Monitoring** | Prometheus + Grafana | — | Apache 2.0 | System health monitoring |

#### User Portal (Web Frontend)

| Layer | Technology | Purpose |
|---|---|---|
| **Framework** | Next.js 14+ (React) | SSR portal application |
| **Styling** | Vanilla CSS | Custom design system |
| **Camera API** | MediaDevices.getUserMedia | In-browser selfie capture |
| **State** | React Context / Zustand | Client state management |
| **Image Gallery** | Custom masonry grid | Photo display and download |

### 6.2 Hardware Requirements

#### Minimum Edge Node Specification

| Component | Minimum | Recommended |
|---|---|---|
| **CPU** | Intel i5-12400 / AMD Ryzen 5 5600 | Intel i7-13700 / AMD Ryzen 7 7700 |
| **GPU** | NVIDIA GTX 1650 (4GB VRAM) | NVIDIA RTX 3060 (12GB VRAM) |
| **RAM** | 16 GB | 32 GB |
| **Storage** | 256 GB SSD (buffer) | 1 TB NVMe SSD |
| **USB** | USB 3.0 (for DSLR tethering) | USB 3.1 Gen 2 |
| **Network** | Gigabit Ethernet or WiFi 5 | WiFi 6 + Ethernet backup |
| **Power** | 500W PSU | 650W PSU |

#### Alternative: NVIDIA Jetson (Compact Deployment)

| Model | GPU Cores | RAM | Power | Use Case |
|---|---|---|---|---|
| Jetson Orin Nano | 1024 CUDA | 8 GB | 15W | Single camera, NanoDet |
| Jetson Orin NX | 2048 CUDA | 16 GB | 25W | 2-3 cameras, YOLOv8n |
| Jetson AGX Orin | 2048 CUDA | 64 GB | 60W | 4+ cameras, full pipeline |

---

## 7. Photography Intelligence Rules

### 7.1 Camera Settings Decision Tree

```
IF scene == INDOOR:
    IF lighting == WELL_LIT:
        ISO = 400, Shutter = 1/125s
    ELIF lighting == DIM:
        ISO = 1600, Shutter = 1/80s
    ELIF lighting == DARK:
        ISO = 3200, Shutter = 1/60s, Flash = FILL
ELIF scene == OUTDOOR:
    IF lighting == BRIGHT_SUN:
        ISO = 100, Shutter = 1/500s
    ELIF lighting == OVERCAST:
        ISO = 200, Shutter = 1/250s
    ELIF lighting == GOLDEN_HOUR:
        ISO = 200, Shutter = 1/160s

# Aperture determined by capture mode (see 5.3.4)
# White balance: AWB or venue-calibrated preset
```

### 7.2 Portrait Photography Rules Matrix

| Rule | Solo | Duo | Group | Candid |
|---|---|---|---|---|
| **Aperture** | f/1.8-2.8 | f/3.5-4.0 | f/5.6-11 | f/2.8-4.0 |
| **Focus Point** | Nearest eye | Center-weighted | Wide zone | Nearest subject |
| **Min Shutter** | 1/125s | 1/125s | 1/125s | 1/250s |
| **Framing** | Rule of thirds | Symmetric balance | All faces visible | Natural, off-center |
| **Headroom** | 10-20% | 10-15% | 5-10% | Variable |
| **Eye Position** | Upper third | Upper third | Upper half | Any |
| **DOF Priority** | Shallow (isolation) | Moderate | Deep (all sharp) | Shallow (subject pop) |
| **Crop Danger Zones** | Never at joints | Never at joints | Waist-up preferred | Any natural |

### 7.3 Exposure Compensation Rules

```python
EXPOSURE_COMP_RULES = {
    "backlit_subject": +1.0,        # Subject darker than background
    "bright_background": +0.7,      # White walls, windows
    "dark_clothing_dominant": +0.3,  # Avoid underexposure
    "snow_or_beach": +1.5,          # Highly reflective scene
    "stage_spotlight": -0.7,        # Avoid blown highlights
    "default": 0.0
}
```

---

## 8. Data Models & Schema

### 8.1 Core Entities

```sql
-- Events
CREATE TABLE events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,
    venue           VARCHAR(255),
    start_time      TIMESTAMP NOT NULL,
    end_time        TIMESTAMP,
    status          VARCHAR(20) DEFAULT 'active',  -- active, completed, archived
    settings        JSONB,                          -- camera config, thresholds
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Cameras registered to an event
CREATE TABLE cameras (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id        UUID REFERENCES events(id),
    camera_type     VARCHAR(20),   -- dslr, mirrorless, ptz, rpi
    camera_model    VARCHAR(100),
    connection_type VARCHAR(20),   -- usb, onvif, wifi
    location_label  VARCHAR(100),  -- "Main Hall", "Entrance", etc.
    config          JSONB,         -- aperture, iso, etc.
    status          VARCHAR(20) DEFAULT 'connected'
);

-- Captured images
CREATE TABLE images (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id        UUID REFERENCES events(id),
    camera_id       UUID REFERENCES cameras(id),
    file_path       VARCHAR(500),       -- S3/MinIO key
    thumbnail_path  VARCHAR(500),
    original_width  INT,
    original_height INT,
    capture_mode    VARCHAR(20),        -- solo, duo, trio, group, candid
    iqg_blur_score  FLOAT,
    iqg_nima_score  FLOAT,
    iqg_face_count  INT,
    iqg_passed      BOOLEAN DEFAULT FALSE,
    captured_at     TIMESTAMP NOT NULL,
    processed_at    TIMESTAMP,
    metadata        JSONB               -- EXIF, camera settings, track_ids
);

-- Face embeddings (see 5.8.5 for vector index)
-- face_embeddings table defined in section 5.8.5

-- Face clusters (anonymous person identities)
CREATE TABLE face_clusters (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id        UUID REFERENCES events(id),
    centroid        VECTOR(512),
    face_count      INT DEFAULT 0,
    representative_face_id UUID,        -- best quality face in cluster
    created_at      TIMESTAMP DEFAULT NOW()
);

-- User registrations (portal users)
CREATE TABLE portal_users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id        UUID REFERENCES events(id),
    display_name    VARCHAR(100),
    selfie_path     VARCHAR(500),
    selfie_embedding VECTOR(512),
    matched_cluster_id UUID REFERENCES face_clusters(id),
    registered_at   TIMESTAMP DEFAULT NOW()
);
```

---

## 9. API Contracts

### 9.1 Event Management

```
POST   /api/v1/events                    Create new event
GET    /api/v1/events/{id}               Get event details
PUT    /api/v1/events/{id}               Update event settings
DELETE /api/v1/events/{id}               Archive event
```

### 9.2 Camera Control

```
POST   /api/v1/events/{id}/cameras       Register camera
GET    /api/v1/events/{id}/cameras       List cameras
POST   /api/v1/cameras/{id}/start        Start auto-capture
POST   /api/v1/cameras/{id}/stop         Stop auto-capture
GET    /api/v1/cameras/{id}/status       Camera health & stats
POST   /api/v1/cameras/{id}/configure    Update camera settings
```

### 9.3 Image & Gallery

```
GET    /api/v1/events/{id}/images        List event images (paginated)
GET    /api/v1/images/{id}               Get image details + faces
GET    /api/v1/images/{id}/download      Download full-res image
DELETE /api/v1/images/{id}               Delete image
GET    /api/v1/events/{id}/stats         Event statistics
```

### 9.4 Selfie Match (User Portal)

```
POST   /api/v1/events/{id}/match         Upload selfie → find photos
  Request:  multipart/form-data { selfie: File }
  Response: {
    matches: [
      { image_id, similarity, thumbnail_url, download_url, capture_mode }
    ],
    total_matches: int,
    processing_time_ms: int
  }

POST   /api/v1/events/{id}/register      Register user with selfie
GET    /api/v1/users/{id}/photos          Get registered user's photos
```

---

## 10. Processing Pipelines

### 10.1 End-to-End Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    REAL-TIME (EDGE NODE)                     │
│                                                             │
│  Camera → LiveView → Detection → Tracking → Orchestrator   │
│                                       ↓                     │
│                              Shutter Trigger                │
│                                       ↓                     │
│                              Raw Image → Local SSD          │
└────────────────────────────────┬────────────────────────────┘
                                 │ Upload (async, batched)
                                 ▼
┌─────────────────────────────────────────────────────────────┐
│                    ASYNC (CLOUD WORKERS)                     │
│                                                             │
│  S3 Upload → IQG Pipeline → Face Detect → Align → Embed   │
│                  ↓                              ↓           │
│           Rejected → /rejected bucket    Embedding → VectorDB│
│                                               ↓             │
│                                     Clustering (periodic)    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    ON-DEMAND (USER PORTAL)                   │
│                                                             │
│  Selfie → Face Detect → Align → Embed → ANN Search         │
│                                              ↓              │
│                                     Matched Images → Gallery │
└─────────────────────────────────────────────────────────────┘
```

### 10.2 Celery Task Definitions

```python
@celery_app.task(bind=True, max_retries=3)
def process_captured_image(self, image_id: str):
    """Full post-capture pipeline for a single image."""
    image = load_image(image_id)

    # Stage 1-4: IQG
    if not iqg_pipeline.run(image):
        mark_rejected(image_id, iqg_pipeline.rejection_reason)
        return

    # Face detection + embedding
    faces = face_detector.get(image.pixels)
    for i, face in enumerate(faces):
        if not passes_embedding_quality(face):
            continue
        embedding = face_embedder.get(image.pixels, face)
        store_embedding(image_id, i, embedding, face)

    # Incremental clustering
    cluster_service.assign_new_embeddings(image_id)

@celery_app.task
def run_full_clustering(event_id: str):
    """Batch re-clustering for an event (run periodically or on-demand)."""
    embeddings = load_all_embeddings(event_id)
    clusters = dbscan_cluster(embeddings, eps=0.45, min_samples=2)
    update_cluster_assignments(event_id, clusters)
```

---

## 11. Performance Requirements

### 11.1 Latency Budgets

| Operation | Target (p95) | Maximum (p99) |
|---|---|---|
| Live preview → Person detection | 30 ms | 50 ms |
| Detection → Shutter trigger | 200 ms | 500 ms |
| Image capture → Local SSD save | 1.5 s | 3.0 s |
| Image upload → S3/MinIO | 2.0 s | 5.0 s |
| IQG pipeline (all 4 stages) | 500 ms | 1.0 s |
| Face detect + align + embed (per image) | 300 ms | 800 ms |
| Selfie upload → ANN search results | 3.0 s | 5.0 s |
| Portal page load | 1.5 s | 3.0 s |

### 11.2 Throughput Targets

| Metric | Target |
|---|---|
| Detection FPS (per camera) | ≥15 FPS |
| Max simultaneous cameras per edge node | 4 (GPU) / 1 (CPU) |
| Images processed through IQG per minute | 60 images/min |
| Face embeddings generated per minute | 120 faces/min |
| Concurrent portal users per event | 500 users |
| ANN queries per second | 100 QPS |

### 11.3 Scalability Limits

| Dimension | Phase 1 Limit | Phase 2 Target |
|---|---|---|
| Cameras per event | 4 | 16 |
| Images per event | 10,000 | 100,000 |
| Face embeddings per event | 30,000 | 500,000 |
| Concurrent events | 5 | 50 |
| Vector DB total embeddings | 150,000 | 5,000,000 |

---

## 12. Security, Privacy & Compliance

### 12.1 Privacy-First Architecture

| Principle | Implementation |
|---|---|
| **No live facial recognition** | Detection engine uses person-class bbox only; facial analysis is post-capture only |
| **Anonymous clustering** | Face clusters use random UUIDs, not names or personal identifiers |
| **Opt-in matching** | Users actively choose to upload selfies; no passive matching |
| **Data minimization** | Embeddings stored as numerical vectors, not raw face images |
| **Right to deletion** | Users can request complete removal of their selfie, embedding, and matched photos |
| **Time-bound retention** | All biometric data auto-deleted after configurable period (default: 30 days post-event) |

### 12.2 Data Protection Measures

| Layer | Measure |
|---|---|
| **Transport** | TLS 1.3 for all API and file transfer traffic |
| **Storage** | AES-256 encryption at rest for S3/MinIO objects |
| **Database** | PostgreSQL TDE or column-level encryption for embeddings |
| **Access Control** | RBAC: Admin, Photographer, Viewer roles |
| **API Auth** | JWT with short-lived tokens (15min) + refresh tokens |
| **Selfie Upload** | Processed in memory, embedding extracted, raw selfie optionally deleted immediately |
| **Audit Logging** | All data access and deletion events logged immutably |

### 12.3 Regulatory Compliance Checklist

| Regulation | Applicability | Key Requirements |
|---|---|---|
| **GDPR** (EU) | If processing EU residents' data | Consent, right to erasure, DPA, DPIA required |
| **CCPA** (California) | If >50K CA consumers | Right to know, delete, opt-out of sale |
| **BIPA** (Illinois) | Any biometric data in Illinois | Written consent before collection, 3-year retention limit |
| **DPDPA** (India) | Processing Indian citizens' data | Purpose limitation, consent, data fiduciary obligations |
| **POPIA** (South Africa) | Processing SA residents' data | Consent, purpose specification, retention limits |

### 12.4 Consent Mechanism

```
Pre-Event:
  → Event organizer agrees to Data Processing Agreement (DPA)
  → Signage at venue: "AI-assisted photography in use"
  → QR code for opt-out (face exclusion list)

User Portal:
  → Explicit consent checkbox before selfie upload
  → Privacy policy link with biometric data handling details
  → One-click "Delete my data" button
```

---

## 13. Deployment Architecture

### 13.1 Docker Compose Services

```yaml
services:
  # --- Edge Node Services ---
  camera-controller:
    build: ./services/camera-controller
    devices: ["/dev/bus/usb"]            # USB passthrough for DSLR
    volumes: ["/capture-buffer:/data"]
    depends_on: [redis]

  detection-engine:
    build: ./services/detection-engine
    runtime: nvidia                       # GPU access
    deploy:
      resources:
        reservations:
          devices: [{capabilities: [gpu]}]
    depends_on: [camera-controller]

  capture-orchestrator:
    build: ./services/capture-orchestrator
    depends_on: [detection-engine, camera-controller]

  # --- Cloud Backend Services ---
  api-gateway:
    build: ./services/api-gateway
    ports: ["8000:8000"]
    depends_on: [postgres, redis, minio]

  embedding-worker:
    build: ./services/embedding-worker
    runtime: nvidia
    depends_on: [postgres, minio, redis]

  postgres:
    image: pgvector/pgvector:pg16
    volumes: ["pgdata:/var/lib/postgresql/data"]
    environment:
      POSTGRES_DB: rec
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password

  redis:
    image: redis:7-alpine
    volumes: ["redisdata:/data"]

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    volumes: ["miniodata:/data"]

  # --- User Portal ---
  portal:
    build: ./services/portal
    ports: ["3000:3000"]
    depends_on: [api-gateway]
```

### 13.2 Deployment Options

| Mode | Description | Use Case |
|---|---|---|
| **All-in-One** | Single machine runs edge + cloud services | Small events, demos |
| **Edge + Cloud** | Edge node on-site, backend on cloud (AWS/GCP) | Production events |
| **Multi-Edge** | Multiple edge nodes → central cloud backend | Large venues, multiple rooms |
| **Full Cloud** | IP cameras stream to cloud, all processing remote | PTZ/IP camera setups |

---

## 14. Competitive Landscape

### 14.1 Market Comparison

| Feature | **REC** | KwikPic | PicsDrop | SpotMyPhotos | Photo Booths |
|---|---|---|---|---|---|
| **Auto Capture** | ✅ Full autonomous | ❌ Manual | ❌ Manual | ❌ Manual | ⚠️ Fixed/posed |
| **DSLR Quality** | ✅ Native DSLR | ✅ (uploaded) | ✅ (uploaded) | ✅ (uploaded) | ⚠️ Webcam/compact |
| **Candid Photos** | ✅ AI-triggered | ❌ Photographer | ❌ Photographer | ❌ Photographer | ❌ Posed only |
| **Group Detection** | ✅ Auto duo/trio/group | ❌ Manual | ❌ Manual | ❌ Manual | ❌ N/A |
| **Face Matching** | ✅ Same-model pipeline | ✅ Proprietary | ✅ Proprietary | ✅ Proprietary | ❌ None |
| **Quality Gate** | ✅ 4-stage IQG | ❌ None | ❌ None | ❌ None | ❌ None |
| **Subject Diversity** | ✅ Anti-repeat scheduler | ❌ N/A | ❌ N/A | ❌ N/A | ❌ N/A |
| **Self-hosted** | ✅ Full control | ❌ SaaS only | ❌ SaaS only | ❌ SaaS only | ✅ On-premises |

### 14.2 Unique Differentiators

1. **Autonomous Capture** — No human photographer required after setup
2. **Photography Intelligence** — Rule-of-thirds, DOF control, exposure compensation
3. **Anti-Repeat Diversity** — Ensures fair coverage of all attendees
4. **Integrated Pipeline** — Same AI model for capture-time quality and retrieval-time matching
5. **Open-Source Core** — Built on commercially-licensed open-source models (no vendor lock-in)
6. **Quality Gate** — Guarantees zero blurry or faceless photos in final gallery

---

## 15. Risks & Mitigations

| # | Risk | Severity | Probability | Mitigation |
|---|---|---|---|---|
| R1 | **Camera compatibility issues** — specific DSLR models may not support all gPhoto2 features | Medium | High | Maintain tested-camera matrix; fallback to generic USB trigger; support Canon/Nikon/Sony tier-1 bodies |
| R2 | **DSLR zoom limitation** — optical zoom cannot be controlled programmatically on most DSLRs | High | Certain | Design system for prime lenses at fixed focal lengths; use PTZ cameras where zoom is required |
| R3 | **Embedding model bias** — AuraFace may perform unevenly across ethnicities | High | Medium | Conduct fairness audit on target demographic; fine-tune on diverse dataset if needed; offer threshold tuning per event |
| R4 | **Privacy litigation** — biometric data laws (BIPA, GDPR) create legal exposure | Critical | Medium | Implement consent flow, auto-deletion, right-to-erasure; legal review before each market launch |
| R5 | **High reject rate** — IQG discards too many images, leaving some attendees uncovered | Medium | Medium | Tune thresholds dynamically; lower aesthetic threshold in low-light venues; increase capture frequency |
| R6 | **USB disconnect during event** — DSLR loses tethering connection | Medium | Medium | Auto-reconnect loop with exponential backoff; alert operator via push notification |
| R7 | **GPU failure** — edge node GPU crash stops detection pipeline | High | Low | CPU fallback to NanoDet-Plus; hot-spare edge node for critical events |
| R8 | **False positive face matches** — lookalikes matched to wrong person | Medium | Low | Use 0.55 threshold (high-precision default); allow user to dispute matches via portal |
| R9 | **Network failure** — edge node loses cloud connectivity | Medium | Medium | Local buffer with retry queue; images cached on SSD until upload succeeds |
| R10 | **Shutter wear** — high-volume auto-capture accelerates mechanical shutter degradation | Low | High | Implement capture rate limits; use electronic shutter mode where available; budget shutter replacement |

---

## 16. Glossary

| Term | Definition |
|---|---|
| **ANN** | Approximate Nearest Neighbor — fast vector similarity search algorithm |
| **AuraFace** | Open-source (Apache 2.0) face embedding model by fal, based on ArcFace architecture |
| **ByteTrack** | Multi-object tracking algorithm using IoU-based association with low-score detection recovery |
| **DBSCAN** | Density-Based Spatial Clustering of Applications with Noise — clustering algorithm |
| **DOF** | Depth of Field — the range of distance in a photo that appears sharp |
| **Embedding** | A fixed-length numerical vector representing a face's identity features |
| **gPhoto2** | Open-source library for controlling digital cameras via USB |
| **HNSW** | Hierarchical Navigable Small World — graph-based ANN index structure |
| **IQG** | Image Quality Gate — multi-stage quality validation pipeline |
| **MOT** | Multi-Object Tracking — maintaining identity of multiple objects across video frames |
| **NIMA** | Neural Image Assessment — deep learning model for predicting image aesthetic quality |
| **ONVIF** | Open Network Video Interface Forum — protocol standard for IP camera control |
| **OSNet** | Omni-Scale Network — lightweight person re-identification model |
| **PID** | Proportional-Integral-Derivative — control loop algorithm for smooth PTZ movement |
| **PTZ** | Pan-Tilt-Zoom — motorized camera capable of remote directional and zoom control |
| **Re-ID** | Re-Identification — matching a person's appearance across different camera views |
| **RetinaFace** | High-precision single-stage face detector with landmark prediction |
| **Rule of Thirds** | Photography composition guideline dividing frame into 3×3 grid |
| **Track ID** | Unique identifier assigned to a detected person within a single camera's view |
| **Vector DB** | Database optimized for storing and searching high-dimensional vectors |

---

*End of PRD v1.0.0*






