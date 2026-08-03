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
   - 5.11 Photographer Edge Dashboard
   - 5.12 Event Sharing & Access Control
   - 5.13 Model Training & Domain Specialization
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
│  │ DSLR / PTZ  │    │  gPhoto2 · ONVIF · digiCamControl           │  │
│  └─────────────┘    └──────────────┬──────────────────────────────┘  │
│                                    │ Live Preview Stream (Low-Res)   │
│                                    ▼                                 │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │              LIGHTWEIGHT HUMAN DETECTION ENGINE                 │ │
│  │         YOLOv8n / NanoDet-Plus  (Person class only)             │ │
│  │    Runs on live preview @ 15-30 FPS · GPU or CPU                │ │
│  └──────────────┬──────────────────────────────────────────────────┘ │
│                 │ Detection Events (bbox, confidence, count)         │
│                 ▼                                                    │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │              AUTO-CAPTURE ORCHESTRATOR                          │ │
│  │  • Composition Rule Engine (Rule of Thirds, Framing)            │ │
│  │  • Subject Diversity Scheduler (anti-repeat logic)              │ │
│  │  • Group Formation Detector (solo/duo/trio/group)               │ │
│  │  • Shutter Decision Engine (timing, AF-confirm, motion-stop)    │ │
│  │  • PTZ Commander (pan/tilt/zoom for framing — if PTZ camera)    │ │
│  └──────────────┬──────────────────────────────────────────────────┘ │
│                 │ Trigger Shutter / Adjust Settings                  │
│                 ▼                                                    │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │              IMAGE QUALITY GATE (IQG)                           │ │
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
│  │  Upload selfie → Extract embedding (same model) →               │ │
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

### 5.11 Photographer Edge Dashboard (Local App Interface)

#### 5.11.1 Purpose

Provides photographers with a local, zero-latency interface running directly on their edge laptop. It orchestrates camera connection, real-time AI-annotated live preview, person tracking visualization, digital PTZ zoom, manual capture overrides, and cloud sync policies. The system uses a **dual-process architecture**: a lightweight PyQt6 system launcher that boots the edge server and a full-featured browser-based dashboard served on `localhost`.

#### 5.11.2 Dual-Process Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                    EDGE NODE LAUNCH SEQUENCE                         │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────────────────────────┐                            │
│  │  PROCESS 1: PyQt6 LAUNCHER           │                            │
│  │  (desktop_app.py — Minimal Dialog)   │                            │
│  │                                      │                            │
│  │  • Displays REC logo + status        │                            │
│  │  • Shows "System Running" indicator  │                            │
│  │  • Provides "Open Dashboard" button  │                            │
│  │    → opens http://localhost:5000      │                            │
│  │  • System tray icon with quick       │                            │
│  │    actions (Stop / Open / Quit)      │                            │
│  │  • Spawns FastAPI server as child    │                            │
│  │    process on startup                │                            │
│  └────────────────┬─────────────────────┘                            │
│                   │ subprocess.Popen(uvicorn)                        │
│                   ▼                                                   │
│  ┌──────────────────────────────────────┐                            │
│  │  PROCESS 2: FastAPI EDGE SERVER      │                            │
│  │  (dashboard/server.py — Port 5000)   │                            │
│  │                                      │                            │
│  │  • Serves HTML/CSS/JS dashboard      │                            │
│  │  • Handles authentication against    │                            │
│  │    cloud Auth DB (live API check)    │                            │
│  │  • Spawns/controls Orchestrator      │                            │
│  │  • Streams annotated MJPEG frames    │                            │
│  │  • Exposes REST API for all controls │                            │
│  │  • Runs background cloud sync task   │                            │
│  └──────────────────────────────────────┘                            │
│                                                                      │
│  Browser (localhost:5000) ◄── Photographer interacts here            │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

**Why dual-process?**
- The PyQt6 launcher is intentionally minimal (~100 LOC). Its sole job is to ensure the edge server is alive, display the REC branding, and provide a single-click route to the browser dashboard. It never renders complex UI, camera feeds, or interactive controls.
- The browser dashboard handles all rich interaction. This allows the photographer to use any device on the same LAN (tablet, phone, second laptop) to monitor the capture session. It also eliminates PyQt6 rendering overhead on the frame pipeline, keeping the AI orchestrator's CPU budget intact.

#### 5.11.3 Authentication & Execution Gate

The dashboard enforces a **strict authentication gate** before any hardware or AI systems are permitted to execute:

```
┌──────────┐     POST /login        ┌──────────────────┐
│ Browser  │ ──────────────────────► │  Edge Server     │
│ Login    │     (email, password)   │  (FastAPI)       │
│ Form     │                        │                  │
│          │                        │  ┌──────────────┐│
│          │                        │  │ Cloud Auth   ││
│          │                        │  │ API Check    ││
│          │ ◄──────────────────── │  │ (live POST   ││
│          │     Set-Cookie:        │  │  to DB)      ││
│          │     edge_token=JWT     │  └──────┬───────┘│
│          │                        │         │        │
│          │                        │  IF 200 → Unlock │
│          │                        │  IF 401 → Block  │
└──────────┘                        └──────────────────┘

EXECUTION GATE RULES:
1. The Orchestrator subprocess will NOT be spawned until authentication succeeds.
2. Camera hardware will NOT be accessed until authentication succeeds.
3. The /dashboard route returns HTTP 302 → /login if no valid edge_token cookie exists.
4. Sandbox bypass: credentials "photographer1" / "password" bypass the cloud check
   for offline development only. This bypass is disabled in production builds.
```

#### 5.11.4 Live Camera Feed — MJPEG Streaming with AI Annotations

The dashboard displays a **real-time, AI-annotated camera feed** directly in the browser. The Orchestrator burns detection overlays onto each frame before writing it to a shared buffer, which the FastAPI server streams as MJPEG to the browser `<img>` tag.

**Frame Pipeline:**

```
Camera (OpenCV) → YOLOv8n Detection → ByteTrack Tracking
    → Engagement Scoring → Draw Overlays → cv2.imencode('.jpg')
    → Write to /tmp/rec_frame.jpg → FastAPI serves as StreamingResponse
    → Browser <img> polls at ~15 FPS via cache-bust query param
```

**Overlay Specification — Color-Coded Person Tracking Ellipses:**

The system draws **elliptical (oval) overlays** around each tracked person instead of rectangular bounding boxes. Ellipses are computationally cheaper to render, visually less intrusive on the live feed, and better approximate the human silhouette.

| Color | Status | Meaning | Visual |
|---|---|---|---|
| 🟢 **Green** | `READY` | Person is engaged, sustained, and the system will capture or has just captured | Solid green ellipse, 2px stroke |
| 🟡 **Yellow** | `ANALYZING` | Person detected and being evaluated. Engagement sustain counter is building | Dashed yellow ellipse, 1px stroke |
| 🔴 **Red** | `COOLDOWN` | Person was recently captured. In cooldown period, will not be re-captured | Solid red ellipse, 1px stroke, dimmed |
| 🟠 **Orange** | `IGNORING` | Person is facing away, too small, or engagement score is below threshold | Dotted orange ellipse, 1px stroke |

**Overlay Label Format:**
Above each ellipse, a compact text label displays:
```
[STATUS]: [REASON]
Examples:
  "READY: Priority 2.45"
  "COOLDOWN: Wait 12.3s"
  "ANALYZING: Holding (3/10)"
  "IGNORING: Low Eng (0.32 < 0.65)"
```

**Capture Flash Effect:**
When the AI triggers a capture, the browser UI performs a brief white-flash CSS animation on the live feed container (`opacity: 0 → 1 → 0` over 150ms). This simulates a camera flash and provides immediate visual confirmation to the photographer that a shot was taken without requiring them to check the capture grid.

```css
@keyframes capture-flash {
  0%   { opacity: 0; }
  30%  { opacity: 0.8; }
  100% { opacity: 0; }
}
.flash-overlay {
  position: absolute;
  inset: 0;
  background: white;
  pointer-events: none;
  animation: capture-flash 150ms ease-out;
}
```

#### 5.11.5 Real-Time Person Tracking — ByteTrack Integration

The Orchestrator uses **ByteTrack** (MIT license) as the primary multi-object tracker for frame-to-frame identity persistence. ByteTrack was selected over BoT-SORT for the live dashboard context because:

1. **Speed:** ByteTrack uses pure IoU + Kalman filter association with zero CNN overhead. It adds <1ms per frame on CPU.
2. **Static cameras:** Edge nodes use tripod-mounted cameras. ByteTrack excels in static-camera scenarios where camera-motion compensation (BoT-SORT's primary advantage) is unnecessary.
3. **Low-confidence recovery:** ByteTrack's signature innovation is its two-stage association that recovers tracks using low-confidence detections, which is critical for event photography where people frequently turn sideways or are partially occluded by other guests.

**Tracker Configuration (bytetrack.yaml):**
```yaml
tracker_type: bytetrack
track_high_thresh: 0.5      # High-confidence detection threshold
track_low_thresh: 0.1       # Low-confidence recovery threshold
new_track_thresh: 0.6       # Minimum confidence to initialize new track
track_buffer: 30            # Frames to keep lost tracks alive (~2s at 15 FPS)
match_thresh: 0.8           # IoU threshold for association
```

**Track ID Lifecycle:**
```
New Detection (conf ≥ 0.6) → Assign Track ID → Active Tracking
    ↓ (person occluded / exits frame)
Lost Track → Keep in buffer for 30 frames (~2 seconds)
    ↓ (re-detected with IoU match)
Re-associated → Same Track ID preserved → Cooldowns/counts intact
    ↓ (not re-detected within buffer)
Track Evicted → PID removed from scene state
```

The **Persistent Identity System (PIS)** defined in Section 5.6 operates on top of ByteTrack, using OSNet appearance descriptors to survive longer re-entry gaps and cross-camera switches. For the live dashboard visualization, the ByteTrack local Track ID is sufficient for overlay rendering.

#### 5.11.6 Digital PTZ — Software Zoom & Auto-Framing

Even standard USB webcams and fixed-lens DSLRs gain **digital zoom and pan** capabilities through software-based Region-of-Interest (ROI) cropping. The system uses the detected person's bounding box to compute an optimal crop window that simulates physical PTZ movement.

**How Digital Zoom Works:**

```python
def digital_ptz(frame, target_bbox, zoom_scale=1.5):
    """
    Simulates PTZ by cropping a Region of Interest around the target
    and resizing it back to the output resolution.
    """
    h, w = frame.shape[:2]
    tx1, ty1, tx2, ty2 = target_bbox

    # Center the crop on the target person's centroid
    cx, cy = (tx1 + tx2) // 2, (ty1 + ty2) // 2

    # Compute crop dimensions (inversely proportional to zoom)
    crop_w = int(w / zoom_scale)
    crop_h = int(h / zoom_scale)

    # Clamp to frame boundaries
    x1 = max(0, cx - crop_w // 2)
    y1 = max(0, cy - crop_h // 2)
    x2 = min(w, x1 + crop_w)
    y2 = min(h, y1 + crop_h)

    # Crop and resize back to original resolution
    roi = frame[y1:y2, x1:x2]
    return cv2.resize(roi, (w, h), interpolation=cv2.INTER_LINEAR)
```

**Zoom Trigger Logic:**
- The dashboard provides a zoom slider (1.0x to 3.0x) for manual photographer control.
- **Auto-zoom** mode: When a single person is detected and is in `READY` state, the system automatically crops to ensure the person fills ~40% of the frame area. This produces tighter, more professional compositions even from a wide-angle webcam.
- Zoom resets to 1.0x when multiple people are detected (to avoid losing subjects outside the crop).

**Digital Pan Logic:**
- When the tracked subject moves within the frame, the crop window follows their centroid with a smoothed offset (exponential moving average, α=0.15) to prevent jittery panning.
- A dead zone of ±5% around frame center prevents micro-corrections.

#### 5.11.7 Manual Shutter Button (Circular)

The dashboard includes a prominent **circular shutter button** styled after professional camera interfaces:

```
┌─────────────────────────────────────────┐
│              LIVE FEED                  │
│                                         │
│   ┌─────┐                               │
│   │ 🟢  │  "READY: Priority 2.1"        │
│   └─────┘                               │
│                                         │
│              ┌───────┐                   │
│              │  ◉    │  ← Shutter Button │
│              └───────┘                   │
└─────────────────────────────────────────┘
```

**Behavior:**
1. Clicking the shutter button immediately captures the current annotated frame from `/tmp/rec_frame.jpg`.
2. The captured image is saved to the local SSD buffer (`/capture-buffer/manual_TIMESTAMP.jpg`).
3. The live feed flashes white (150ms) to confirm the capture.
4. The image appears instantly in the capture grid below.
5. If Cloud Auto-Sync is ON, the image is queued for immediate upload.

**Styling:** The button is rendered as a 64px white circle with a 3px dark border, centered below the live feed. On hover, the inner circle subtly pulses. On click, it briefly scales down (active state) to simulate a physical button press.

#### 5.11.8 Capture Grid & Queue System

Captured images (both AI-triggered and manual) appear in a **real-time scrolling grid** below the live feed:

```
┌─────────────────────────────────────────────────────────────┐
│  CAPTURE QUEUE                                    [SYNC: ON]│
├─────────────────────────────────────────────────────────────┤
│  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐    │
│  │ 📷  │  │ 📷  │  │ 📷  │  │ 📷  │  │ 📷  │  │ 📷  │    │
│  │     │  │     │  │     │  │     │  │     │  │     │    │
│  │ ✓☁  │  │ ✓☁  │  │ ⏳☁  │  │ 🗑   │  │ 🗑   │  │ 🗑   │    │
│  └─────┘  └─────┘  └─────┘  └─────┘  └─────┘  └─────┘    │
│  ✓☁ = Uploaded    ⏳☁ = Pending    🗑 = Discard available   │
└─────────────────────────────────────────────────────────────┘
```

**Queue Lifecycle:**
1. **Capture** → Image written to local SSD buffer.
2. **Grid Hydration** → Buffer polling thread detects new file, emits to UI grid (2s interval).
3. **Cloud Sync** → If toggle is ON, background task POSTs to `/upload` API endpoint. Upload status icon updates per-image (pending → uploaded).
4. **Discard** → Photographer can hover any image and click "Discard" to delete from buffer. If already uploaded, the cloud copy is retained.

#### 5.11.9 AI Telemetry Bar

A compact telemetry strip displayed between the live feed and the capture grid provides real-time insight into the Orchestrator's internal state:

```
┌─────────────────────────────────────────────────────────────┐
│  IDLE: 4.2s  │  GINI: 0.28  │  MODE: Standard  │  PIDs: 3 │
└─────────────────────────────────────────────────────────────┘
```

| Metric | Source | Update Rate |
|---|---|---|
| **Idle** | Seconds since last global capture | 500ms |
| **Gini** | Fairness coefficient (0.0 = perfect, 1.0 = monopoly) | 500ms |
| **Mode** | Standard / Dance Burst / Ceremony / Watchdog | 500ms |
| **PIDs** | Number of currently tracked persons | 500ms |

#### 5.11.10 Cloud Auto-Sync Engine

A background `asyncio` task runs continuously on the edge server. When the Cloud Auto-Sync toggle is ON, it:

1. Scans the local SSD buffer (`/capture-buffer/`) for new image files every 2 seconds.
2. For each new file not yet in the `UPLOADED_FILES` set:
   - POSTs to `{CLOUD_API_URL}/upload` with `multipart/form-data` containing the image, event ID, and photographer username.
   - On HTTP 200, marks the file as uploaded.
   - On failure, retries on the next scan cycle (automatic retry with no data loss).
3. Upload happens in a non-blocking thread to avoid stalling the MJPEG stream or API responses.

**The uploaded images appear immediately on the photographer's web portal** (cloud-side), where face embedding extraction and clustering begin automatically. This means event attendees can start finding their photos via selfie-match **while the event is still ongoing**.

#### 5.11.11 Lightweight Processing Constraints

The dashboard visualization must not degrade the Orchestrator's inference performance. The following constraints are enforced:

| Operation | Budget | Strategy |
|---|---|---|
| **Ellipse drawing** | <0.5ms per person | `cv2.ellipse()` — single OpenCV call per detection |
| **Text rendering** | <0.2ms per label | `cv2.putText()` — no font rendering libraries |
| **Frame JPEG encoding** | <3ms per frame | `cv2.imencode('.jpg', quality=70)` — reduced quality for stream |
| **State JSON write** | <0.1ms | Atomic write to `/tmp/rec_state.json` |
| **Browser poll interval** | 66ms (15 FPS) | `<img>` src swap with cache-bust timestamp |
| **State API poll** | 500ms | Telemetry bar update (separate from frame stream) |

**Total overhead per frame: <4ms** — well within the 66ms budget of a 15 FPS pipeline.

### 5.12 Event Sharing & Access Control

#### 5.12.1 Purpose
Governs how attendees access the user portal to scan their faces and retrieve their photos, providing strict privacy options for the photographer/event organizer.

#### 5.12.2 Sharing Modes
| Mode | Description |
|---|---|
| **Option 1: Private (Link-Only)** | Strict privacy. **Only** users who possess a specific, unique event link can access the portal, scan their face, and retrieve photos. Without the link, the event is completely invisible, even if a user's face was detected. |
| **Option 2: Public (Open Access)** | Open discovery. The event is visible on the main portal. Anyone whose face was detected during the event can find their photos simply by taking a selfie on the public platform. |

#### 5.12.3 Unique Link Generation & Constraints
When **Private Mode** is selected, the system generates secure, embedded links with strict usage controls:
- **Unique Tokens:** Each generated link contains a cryptographic token bound to that specific share.
- **Bulk Generation:** Photographers can generate bulk unique links (e.g., 500 links for 500 VIP attendees) via the admin dashboard.
- **Usage Limits:** Each link can be configured with a "Maximum Opens" or "Maximum Users" limit (e.g., a family link that expires after 5 different devices open it).

---

### 5.13 Model Training & Domain Specialization

#### 5.13.1 Do We Need to Train Any Models?

**Short answer: No for the core pipeline. Yes for domain-specific "key moment" triggers.**

The REC system uses a layered model architecture. The decision on whether to train, fine-tune, or use off-the-shelf depends on each layer:

| Layer | Model | Custom Training Needed? | Rationale |
|---|---|---|---|
| **Person Detection** | YOLOv8n (COCO pre-trained) | ❌ No | The COCO `person` class already achieves 80.4% mAP. People are the most heavily represented class in COCO. Works across all event types without modification. |
| **Multi-Object Tracking** | ByteTrack | ❌ No | ByteTrack is a tracking algorithm (IoU + Kalman filter), not a learned model. It requires no training data. |
| **Person Re-ID** | OSNet x0.25 | ❌ No (Phase 1) / ⚠️ Optional fine-tune (Phase 2) | Pre-trained OSNet achieves strong ReID on Market-1501. Fine-tuning on Indian clothing patterns (bright Navratri attire, wedding lehengas, cricket whites) could improve cross-camera re-identification by ~5-8%. |
| **Face Embedding** | AuraFace v1 | ❌ No | AuraFace is trained on millions of faces. Fine-tuning would require an equally large, licensed dataset and risks degrading generalization. Use as-is. |
| **Pose Estimation** | YOLOv8n-pose | ❌ No (for general use) / ✅ Yes (for cricket biomechanics) | The 17-point COCO skeleton is sufficient for engagement scoring (gaze, body openness). Cricket shot analysis requires custom keypoints (bat grip, elbow extension). |
| **Action Recognition** | Custom Lightweight Classifier | ✅ Yes — New Model Required | No off-the-shelf model can detect domain-specific "key moments" (handshakes, trophy presentations, Garba spins, cricket shots). This is a **new, lightweight temporal classifier** trained on our data. |

#### 5.13.2 The Key Moment Classifier (New Model)

This is the **only new model** REC needs to train. It operates as a lightweight post-processing layer on top of the existing YOLO + ByteTrack pipeline.

**Architecture:**

```
┌──────────────────────────────────────────────────────────────────────┐
│                    KEY MOMENT CLASSIFICATION PIPELINE                 │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  YOLOv8n-pose (pre-trained, frozen)                                  │
│  ├── Outputs: 17 keypoints per person (x, y, confidence)             │
│  └── Runs at 15 FPS (already running for engagement scoring)         │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────┐        │
│  │  TEMPORAL FEATURE BUFFER (per tracked person)            │        │
│  │  • Stores last 30 frames of keypoint sequences           │        │
│  │  • Shape: (30, 17, 3) per person — ~6 KB per person      │        │
│  └────────────────────┬─────────────────────────────────────┘        │
│                       ▼                                              │
│  ┌──────────────────────────────────────────────────────────┐        │
│  │  LIGHTWEIGHT TEMPORAL CLASSIFIER                         │        │
│  │  • Architecture: 2-layer GRU (64 hidden units)           │        │
│  │  • Input: (30, 34) — 30 frames × 17 keypoints × 2 (x,y) │        │
│  │  • Output: Action class probabilities                     │        │
│  │  • Size: ~200 KB (.onnx)                                 │        │
│  │  • Latency: <2ms per inference on CPU                    │        │
│  └────────────────────┬─────────────────────────────────────┘        │
│                       ▼                                              │
│  Action: "handshake" (0.92) → TRIGGER: Priority boost + Burst mode   │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

**Action Classes (Multi-Event):**

| Class | Events | Detection Method | Training Data Source |
|---|---|---|---|
| `handshake` | Weddings, Corporate, Sports | Wrist keypoints of two people within 40px for ≥10 frames | Manual annotation from event footage |
| `trophy_presentation` | Sports, School | One person extends arms forward, other person receives object | Sports ceremony footage |
| `garba_spin` | Navratri, Dance | Full-body rotation (>180° yaw change) in <1 second | Navratri event footage |
| `dandiya_strike` | Navratri | Arm extension with high velocity + two-person proximity | Dandiya footage |
| `cricket_shot` | Cricket | Batsman arm extension + bat-swing arc (>90° elbow angle change in <0.5s) | Cricket broadcast footage |
| `bowling_action` | Cricket | Run-up + arm rotation (>270° shoulder angle change) | Cricket broadcast footage |
| `stage_entry` | Weddings, Corporate | Person entering frame from side with 3+ people already facing them | Event footage |
| `dancing_pair` | Weddings, Navratri | Two people with synchronized high-velocity limb movement | Dance event footage |
| `group_photo_pose` | All | 3+ people standing still, facing camera, for ≥2 seconds | Any event footage |
| `child_activity` | School, Sports Day | Small bounding box (<60% avg height) + high velocity movement | School event footage |

**Training Strategy:**
- **Data Collection:** Record 50+ hours across all target event types. Extract 30-frame clips centered on each key moment.
- **Annotation:** Label each clip with the action class. Include "null" class clips (people standing, walking, talking) at 3:1 ratio to positive samples to minimize false positives.
- **Training:** Train the 2-layer GRU classifier on the keypoint sequences. Freeze the YOLO backbone entirely — we only train the ~50K parameter temporal head.
- **Export:** Export to ONNX for cross-platform CPU inference. The model is so small (~200 KB) it adds negligible overhead.

#### 5.13.3 Domain-Specific Event Profiles

Each event type requires different capture behavior, engagement thresholds, and key moment triggers. Instead of training separate YOLO models per domain, REC uses a **software-configurable Event Profile** that adjusts the Orchestrator's parameters:

##### Profile: Cricket Stadium / Sports Ground

| Parameter | Value | Rationale |
|---|---|---|
| **Detection confidence** | 0.50 | Outdoor, variable lighting, distant subjects |
| **MIN_FACE_HEIGHT_PX** | 40 | Players are often far from camera |
| **Engagement threshold** | 0.30 (lowered) | Players rarely face the camera directly; side profiles dominate |
| **Key moments** | `cricket_shot`, `bowling_action`, `trophy_presentation`, `handshake` | Trigger burst capture (3 frames) on detection |
| **Digital zoom** | Auto-zoom to 2.5x on batsman/bowler during action | Tight framing from stadium distance |
| **Cooldown (batsman)** | 3s (reduced) | Action changes rapidly; multiple shots of same person are expected |
| **Cooldown (spectators)** | 15s (standard) | Spectator capture follows normal diversity rules |
| **Special rule** | Split frame into "field zone" and "stands zone". Apply different engagement thresholds per zone | Ensures both player action and crowd reactions are captured |
| **Pose model** | YOLOv8n-pose | Required for cricket shot / bowling action classification |

##### Profile: Dance Events / Navratri / Garba

| Parameter | Value | Rationale |
|---|---|---|
| **Detection confidence** | 0.40 | Dynamic lighting (strobes, colored lights), motion blur |
| **Shutter speed override** | 1/500s minimum | Freeze fast Garba/Dandiya spins |
| **ISO override** | Auto-ISO up to 6400 | Compensate for low-light + fast shutter |
| **Engagement threshold** | 0.20 (very low) | Everyone is "engaged" — they're all dancing |
| **Burst mode** | Always ON | High-velocity movement demands multi-frame capture; IQG selects sharpest |
| **Key moments** | `garba_spin`, `dandiya_strike`, `dancing_pair` | Trigger burst capture on detection |
| **Cooldown** | 5s (reduced) | Costumes change appearance rapidly; faster re-capture is acceptable |
| **Digital zoom** | Disabled | Wide-angle preferred to capture group formations and circular patterns |
| **Special rule** | Increase JPEG quality to 95% for costume detail. Enable upper-body color histogram refresh every 30 frames (clothing patterns change under colored lighting) | Preserves vibrant Navratri attire details |
| **Crowd safety** | If >50 people detected in frame, switch to "crowd mode" — capture wide establishing shots every 60s | Prevents CPU overload from tracking too many individuals |

##### Profile: School Events / Sports Day / Kindergarten

| Parameter | Value | Rationale |
|---|---|---|
| **Detection confidence** | 0.55 | Controlled environment, good lighting |
| **MIN_FACE_HEIGHT_PX** | 40 (reduced from 80) | Children are physically smaller; standard thresholds miss them |
| **MIN_BBOX_AREA_PX** | 1500 (reduced from 2500) | Smaller bounding boxes for children |
| **Height class override** | Treat all subjects <65% of average bbox height as "child" | Activates child-specific capture rules |
| **Engagement threshold** | 0.25 (lowered) | Children rarely hold still or face the camera; candid-dominant |
| **Key moments** | `child_activity`, `trophy_presentation`, `group_photo_pose` | Sports Day race finishes, prize distribution |
| **Candid ratio** | 90/10 (heavily candid) | Professional school photography is almost entirely candid |
| **Cooldown** | 10s | Standard; ensures variety across all children |
| **Gini target** | ≤0.25 (stricter than default 0.35) | Critical that every child gets captured; parents expect photos of their child |
| **Special rule** | If a child PID has 0 captures after 120s of visibility, force-capture immediately regardless of engagement score | No-child-left-behind guarantee |
| **Privacy** | EXIF metadata stripping enabled. All uploads tagged as "minor_present=true" for cloud-side consent enforcement | Compliance with child photography regulations |

##### Profile: Weddings & Formal Events

| Parameter | Value | Rationale |
|---|---|---|
| **Detection confidence** | 0.50 | Mixed indoor/outdoor, variable lighting |
| **Engagement threshold** | 0.55 (standard) | Guests frequently face camera; natural engagement is high |
| **Key moments** | `handshake`, `stage_entry`, `trophy_presentation`, `dancing_pair`, `group_photo_pose` | VIP arrivals, garland ceremony, ring exchange, first dance |
| **Stage detection** | If a single PID remains stationary at the top-center of frame for >30s, classify as "stage performer". Lower cooldown to 5s. Increase burst frequency | Captures speakers, performers, and the couple on stage |
| **VIP priority** | If a PID receives >5 handshakes within 5 minutes, boost their priority by 2.0x for the next 10 minutes | The person being greeted is likely the bride/groom or VIP guest |
| **Interaction mode** | CANDID_BEHIND enabled | Capture guests talking to each other, not just facing camera |
| **Guest rotation** | Starvation detector activates at 45s (reduced from 60s) | Weddings have many guests; faster rotation ensures coverage |
| **Digital zoom** | Auto-zoom on stage area when only 1-2 people detected. Wide-angle for group photos | Tight framing for stage events, wide for baarat/reception |
| **Special rule** | "Golden Hour" detection: If outdoor and time is 30min before sunset, boost exposure compensation +0.5 EV and increase ISO tolerance | Warm lighting for outdoor wedding portraits |

#### 5.13.4 Training Data Requirements Summary

| Model | Training Needed | Data Volume | Annotation Cost | Timeline |
|---|---|---|---|---|
| **YOLOv8n (person detection)** | None | N/A | N/A | Ready now |
| **ByteTrack** | None | N/A | N/A | Ready now |
| **AuraFace v1** | None | N/A | N/A | Ready now |
| **YOLOv8n-pose** | None (COCO 17-point) | N/A | N/A | Ready now |
| **Key Moment Classifier (GRU)** | ✅ Custom training | 50+ hours video, ~10K labeled clips | ~40 hours annotation | 2-3 weeks |
| **OSNet fine-tune (optional)** | ⚠️ Optional | 5K+ images of Indian event attire | ~10 hours annotation | 1 week |

#### 5.13.5 Model Deployment Strategy

All models run on the edge node. No cloud inference is required during capture:

```
Edge Node Model Stack (Total: ~25 MB)
├── yolov8n.pt            (6.2 MB)  — Person detection
├── yolov8n-pose.pt       (6.4 MB)  — Pose estimation (optional per profile)
├── bytetrack.yaml        (1 KB)    — Tracker config (no model weights)
├── osnet_x0_25.pth       (2.2 MB)  — Re-ID appearance (optional)
├── key_moment_gru.onnx   (200 KB)  — Action recognition
└── Total inference budget: ~45ms/frame on M1 CPU
    ├── YOLO detection:     ~25ms
    ├── Pose estimation:    ~12ms (if enabled)
    ├── ByteTrack:          ~1ms
    ├── Engagement scoring: ~2ms
    ├── Key moment GRU:     ~2ms
    └── Overlay rendering:  ~3ms
```

---

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

> **Research-backed autonomous capture intelligence.** This section defines the complete decision-making framework for when, how, and whom to photograph. Every rule is derived from professional photography principles, computer vision research, and anti-redundancy algorithms.

### 7.1 The Engagement Score Model (Shutter Timing Intelligence)

REC does NOT fire the shutter the instant a person is detected. It continuously computes a real-time **Engagement Score (0.0-1.0)** from multiple facial and body signals, and only triggers when the score sustains above threshold:

| Signal | Weight | Detection Method | Threshold |
|---|---|---|---|
| **Smile Intensity** | 0.25 | Facial landmark mouth-corner distance ratio | > 0.6 |
| **Gaze Direction** | 0.20 | Eye landmark pupil-to-corner ratio (mutual gaze) | Within 15 deg of camera |
| **Eyes Open** | 0.20 | Eye Aspect Ratio (EAR) from 68-point landmarks | EAR > 0.21 |
| **Motion Stability** | 0.15 | Centroid velocity < 15px/frame for 5+ frames | Velocity < threshold |
| **Face Pose Quality** | 0.10 | Yaw < 45 deg, Pitch within [-30, 30] | Within bounds |
| **Body Openness** | 0.10 | Torso facing camera (bbox aspect check) | Aspect 0.3-0.7 |

**Trigger Rule:** `engagement_score >= 0.55` sustained for `MIN_SUSTAIN_FRAMES = 3` consecutive frames (~200ms at 15 FPS). This prevents capturing grimaces, blinks, and mid-motion blur.

### 7.2 Optimal Face Angles (Yaw/Pitch/Roll)

The **three-quarter view (30-45 degree yaw)** is universally the most flattering portrait angle. REC uses InsightFace's landmark model to compute head orientation in 3D and enforces angle quality:

| Angle | Optimal Range | Capture Gate | Rationale |
|---|---|---|---|
| **Yaw** (left/right) | 0-45 deg | Block if > 45 deg | Beyond 45 deg = unreliable face embeddings + unflattering profile |
| **Pitch** (up/down) | -10 to +15 deg | Block if outside [-30, 30] | Slight downward chin tilt is most flattering (research-backed) |
| **Roll** (head tilt) | -15 to +15 deg | Warn if > 15 deg | Subtle tilt adds personality; extreme tilt = awkward |

### 7.3 Anti-Monotony Angle Rotation System

To prevent every photo of the same person being identical, REC tracks `last_capture_angles` per PID and enforces variety:

```python
ANGLE_CATEGORIES = [
    "frontal",              # 0-15 deg yaw
    "three_quarter_left",   # 15-45 deg yaw left
    "three_quarter_right",  # 15-45 deg yaw right
    "elevated",             # Camera above subject
    "candid_behind",        # Subject not facing camera (interaction shots)
]
# Priority: angles NOT yet captured for this PID get 1.3x boost
```

### 7.4 Camera Settings Decision Tree

```
IF scene == INDOOR:
    IF lighting == WELL_LIT:     ISO = 400,  Shutter = 1/125s
    ELIF lighting == DIM:        ISO = 1600, Shutter = 1/80s
    ELIF lighting == DARK:       ISO = 3200, Shutter = 1/60s, Flash = FILL
ELIF scene == OUTDOOR:
    IF lighting == BRIGHT_SUN:   ISO = 100,  Shutter = 1/500s
    ELIF lighting == OVERCAST:   ISO = 200,  Shutter = 1/250s
    ELIF lighting == GOLDEN_HOUR:ISO = 200,  Shutter = 1/160s

# Reciprocal Rule: min_shutter = 1/focal_length (e.g., 85mm -> 1/100s)
# Aperture determined by capture mode (see 7.5)
```

### 7.5 Portrait Photography Rules Matrix

| Rule | Solo | Duo | Group (4+) | Candid |
|---|---|---|---|---|
| **Aperture** | f/1.8-2.8 | f/3.5-4.0 | f/5.6-11 | f/2.8-4.0 |
| **Focus Point** | Nearest eye | Center-weighted | Wide zone | Nearest subject |
| **Min Shutter** | 1/125s | 1/125s | 1/125s | 1/250s |
| **Framing** | Rule of Thirds | Symmetric balance | All faces visible | Off-center, natural |
| **Headroom** | 10-20% | 10-15% | 5-8% | Variable |
| **Eye Position** | Upper third | Upper third | Upper half | Any |
| **DOF Priority** | Shallow (isolation) | Moderate | Deep (all sharp) | Shallow (subject pop) |
| **Crop Danger** | Never at joints | Never at joints | Waist-up preferred | Any natural |
| **Composition** | Golden Ratio/Thirds | Center symmetric | Triangle/Pyramid stagger | Lead-room in gaze dir |

### 7.6 Group Photography Composition Rules

| Group Size | Arrangement | Spacing | Aperture | Key Rule |
|---|---|---|---|---|
| **Duo (2)** | Side-by-side or angled | Shoulder-to-shoulder | f/3.5-4.0 | Both faces in upper third, symmetric |
| **Trio (3)** | Triangular (1 high + 2 low) | Staggered heights | f/5.6 | Triangle center at frame center |
| **Small (4-6)** | Two-row stagger | Tight, no gaps | f/8.0 | Back row between front row shoulders |
| **Large (7+)** | Multi-row height stagger, slight arc | Very tight | f/8-11 | Arc formation keeps all faces equidistant from lens |

### 7.7 Dynamic Cooldown System (Fail-Safe, Anti-Deadlock)

> **CRITICAL DESIGN PRINCIPLE:** The system must NEVER enter a state where zero captures happen (deadlock), and must NEVER enter a state where it constantly fires the same type of shot (spam). The cooldown is fully dynamic and self-correcting.

#### 7.7.1 Per-PID Adaptive Cooldown (Escalating + Decaying)

```python
# === HARDCODED CONSTANTS (DO NOT DERIVE, DO NOT MAKE CONFIGURABLE) ===
COOLDOWN_MIN_SEC         = 5.0     # Absolute floor: never cool down less than 5s
COOLDOWN_BASE_SEC        = 12.0    # Starting cooldown for a fresh PID
COOLDOWN_MAX_SEC         = 120.0   # Absolute ceiling: never cool down more than 2 min
ESCALATION_PER_CAPTURE   = 0.3     # Each capture adds 30% to cooldown
DECAY_RATE_PER_SEC       = 0.02    # Cooldown shrinks 2% per second of inactivity
GLOBAL_MIN_INTERVAL_SEC  = 2.0     # Minimum between ANY two captures (any PID)
GLOBAL_MAX_IDLE_SEC      = 30.0    # If no capture for 30s, force emergency override

def compute_cooldown(pid_state):
    """Dynamic cooldown that escalates on spam and decays on inactivity."""
    base = COOLDOWN_BASE_SEC
    
    # Escalate: more captures = longer wait
    escalated = base * (1.0 + ESCALATION_PER_CAPTURE * pid_state.capture_count)
    
    # Decay: if not seen for a while, cooldown shrinks (person left and came back)
    idle_time = now() - pid_state.last_seen_time
    decay_factor = max(0.3, 1.0 - DECAY_RATE_PER_SEC * idle_time)
    adjusted = escalated * decay_factor
    
    # Clamp to hard bounds
    return clamp(adjusted, COOLDOWN_MIN_SEC, COOLDOWN_MAX_SEC)
```

#### 7.7.2 Anti-Deadlock: The Emergency Override System

The system has **3 independent fail-safes** to guarantee it NEVER stops capturing:

```python
# === FAIL-SAFE 1: Global Idle Watchdog ===
# If no capture has happened for GLOBAL_MAX_IDLE_SEC (30s),
# ALL cooldowns are halved and engagement threshold drops to 0.35.
# This prevents the system from going silent in a crowded room.

if (now() - last_global_capture_time) > GLOBAL_MAX_IDLE_SEC:
    for pid in all_pids:
        pid.current_cooldown *= 0.5  # Halve all cooldowns
    engagement_threshold = 0.35       # Drop from 0.55 to 0.35 (much easier to trigger)
    log("WATCHDOG: Emergency cooldown halving + threshold drop")

# === FAIL-SAFE 2: Starvation Detector ===
# If a specific PID has been visible for 60+ seconds with 0 captures,
# that PID gets INSTANT capture permission (cooldown = 0, threshold = 0.30).

if pid_state.visible_duration > 60.0 and pid_state.capture_count == 0:
    pid_state.current_cooldown = 0
    pid_state.engagement_override = 0.30
    log(f"STARVATION: PID {pid} force-unlocked after 60s with 0 captures")

# === FAIL-SAFE 3: Heartbeat Capture ===
# If NOTHING has been captured for 45 seconds despite people being visible,
# the system forcibly captures the highest-priority visible PID regardless
# of ALL other rules (cooldown, engagement, angle). Pure safety net.

HEARTBEAT_FORCE_SEC = 45.0

if (now() - last_global_capture_time) > HEARTBEAT_FORCE_SEC and visible_count > 0:
    best_pid = priority_queue[0]  # Highest priority PID
    force_capture(best_pid)       # Bypass ALL gates
    log(f"HEARTBEAT: Force-captured PID {best_pid} to prevent deadlock")
```

#### 7.7.3 Anti-Spam: Similarity Suppression

Prevents constant similar captures even when cooldown allows:

```python
# === SIMILARITY GATE ===
# Before capturing PID-X, check if the last N captures are "too similar":
#   - Same PID + Same angle category + < 60s apart = BLOCKED
#   - Same PID + Different angle = ALLOWED
#   - Same PID + Same angle but > 60s = ALLOWED (enough time passed)
#   - Different PID = ALWAYS ALLOWED

SIMILARITY_WINDOW_SEC = 60.0
MAX_SAME_ANGLE_PER_PID = 2  # Max 2 photos of same person at same angle

def is_too_similar(pid, current_angle, capture_history):
    recent = [c for c in capture_history 
              if c.pid == pid 
              and c.angle == current_angle 
              and (now() - c.timestamp) < SIMILARITY_WINDOW_SEC]
    return len(recent) >= MAX_SAME_ANGLE_PER_PID
```

#### 7.7.4 Subject Diversity & Fairness Algorithm

```python
# Priority Score per visible PID (dynamic, recalculated every frame):
def compute_priority(pid_state, avg_captures):
    base = max(0.1, 1.0 - (pid_state.capture_count / max(avg_captures * 2, 1)))
    novelty = 1.5 if pid_state.capture_count == 0 else 1.0
    angle_var = 1.3 if pid_state.has_uncaptured_angles() else 1.0
    cooldown = 0.0 if pid_state.in_cooldown() else 1.0
    starvation = 2.0 if pid_state.capture_count == 0 and pid_state.visible_duration > 30 else 1.0
    
    return base * novelty * angle_var * cooldown * starvation
```

**Gini Coefficient Target: <= 0.35.** When Gini exceeds 0.40, Equity Mode activates (only under-photographed PIDs trigger). When Gini drops below 0.30, normal mode resumes (hysteresis prevents oscillation).

### 7.8 False Positive Elimination (Multi-Layer)

**Detection-Level Filters:**

| Filter | Value | Purpose |
|---|---|---|
| Confidence threshold | `conf >= 0.50` | Reject ghost detections |
| Bbox aspect ratio | `0.15 < (w/h) < 0.80` | Reject poles, banners |
| Minimum bbox area | `>= 2500px` | Reject tiny/distant false triggers |
| Temporal consistency | 3+ consecutive frames | Reject single-frame hallucinations |

**Shutter-Level Safeguards:**

| Safeguard | Rule | Purpose |
|---|---|---|
| Face presence | >= 1 face with `det_score >= 0.7` | Don't shoot backs of heads |
| Motion freeze | Centroid velocity < 15px/frame for 5 frames | Prevent motion blur |
| AF confirmation | AF lock within 500ms timeout | Ensure sharpness |
| Engagement score | `>= 0.55` for 3 consecutive frames | Ensure good expression |

### 7.9 Shot Variety Ratio (Professional Standard: 70/30 Rule)

| Type | Target % | Description |
|---|---|---|
| **Candid** | 70% | Natural interactions, genuine emotions, unposed |
| **Posed/Guided** | 30% | VIP portraits, group shots, branding |

**Candid Sub-Distribution:**

| Sub-type | % of Total | Trigger |
|---|---|---|
| Solo candid | 25% | 1 person, natural pose, engagement > 0.5 |
| Duo interaction | 20% | 2 people facing each other |
| Group candid (3+) | 15% | 3+ clustered, >= 2 faces visible |
| Reaction shots | 10% | Person looking toward stage/speaker |

### 7.10 Exposure Compensation Rules

```python
EXPOSURE_COMP_RULES = {
    "backlit_subject": +1.0,
    "bright_background": +0.7,
    "dark_clothing_dominant": +0.3,
    "snow_or_beach": +1.5,
    "stage_spotlight": -0.7,
    "default": 0.0
}
```

### 7.11 Complete Hardcoded Constants (Single Source of Truth)

```python
# ══════════════════════════════════════════════════════════════
#  REC CAPTURE INTELLIGENCE - HARDCODED CONSTANTS
#  These values are NOT configurable at runtime.
#  They are the result of research + tuning and must be
#  changed ONLY via code review + testing.
# ══════════════════════════════════════════════════════════════

# --- Cooldown (Dynamic, Fail-Safe) ---
COOLDOWN_MIN_SEC             = 5.0      # Floor: never less than 5s
COOLDOWN_BASE_SEC            = 12.0     # Starting cooldown
COOLDOWN_MAX_SEC             = 120.0    # Ceiling: never more than 2 min
ESCALATION_PER_CAPTURE       = 0.3      # +30% per capture
DECAY_RATE_PER_SEC           = 0.02     # -2% per second idle
GLOBAL_MIN_INTERVAL_SEC      = 2.0      # Min between ANY two captures
GLOBAL_MAX_IDLE_SEC          = 30.0     # Watchdog: halve all cooldowns
HEARTBEAT_FORCE_SEC          = 45.0     # Force-capture safety net
STARVATION_THRESHOLD_SEC     = 60.0     # Force-unlock never-captured PIDs

# --- Engagement ---
ENGAGEMENT_THRESHOLD         = 0.55     # Normal trigger threshold
ENGAGEMENT_EMERGENCY         = 0.35     # Watchdog-lowered threshold
ENGAGEMENT_STARVATION        = 0.30     # Starvation-override threshold
MIN_SUSTAIN_FRAMES           = 3        # Frames above threshold before trigger

# --- Diversity ---
MAX_SOLO_CAPTURES_PER_PID    = 8
MAX_TOTAL_CAPTURES_PER_PID   = 20
GINI_TARGET                  = 0.35
GINI_EQUITY_ENTER            = 0.40     # Enter equity mode above this
GINI_EQUITY_EXIT             = 0.30     # Exit equity mode below this (hysteresis)

# --- Similarity Suppression ---
SIMILARITY_WINDOW_SEC        = 60.0
MAX_SAME_ANGLE_PER_PID       = 2

# --- Face Quality Gates ---
YAW_MAX_DEGREES              = 45
PITCH_RANGE_DEGREES          = (-30, 30)
ROLL_MAX_DEGREES             = 15
MIN_FACE_HEIGHT_PX           = 80
PERSON_CONF_THRESHOLD        = 0.50
FACE_DET_SCORE_THRESHOLD     = 0.70

# --- Detection Filters ---
BBOX_ASPECT_RATIO_RANGE      = (0.15, 0.80)
MIN_BBOX_AREA_PX             = 2500
TEMPORAL_CONSISTENCY_FRAMES  = 3
MOTION_VELOCITY_THRESHOLD    = 15       # px/frame

# --- Camera ---
AF_TIMEOUT_MS                = 500
CANDID_TARGET_RATIO          = 0.70
POSED_TARGET_RATIO           = 0.30
```

---

### 7.13 Retroactive Frame Backtracking (Ring Buffer Capture)

#### 7.13.1 The Problem

Real-time AI capture systems are inherently **reactive**: they can only trigger the shutter *after* detecting a worthy moment. This creates a fundamental timing gap:

```
Timeline:  ──────────────────────────────────────────────►
                    │                    │
               Moment Occurs      AI Detects It
               (handshake,         (50-100ms later)
                garba spin,
                child runs)
                    │ ◄── MISSED ──► │
                    │   ~3-6 frames  │
                    │   at 15 FPS    │
```

Even at a perfect 15 FPS pipeline with <50ms inference latency, the shutter fires 3-6 frames *after* the peak moment. For fast actions (handshakes, dance spins, cricket shots), the peak is already past. The resulting capture shows the *aftermath* of the moment, not the moment itself.

#### 7.13.2 Solution: Always-On Ring Buffer

The system maintains a **rolling circular buffer** of the last N seconds of raw, full-resolution frames in RAM. When the AI triggers a capture, it does NOT save the current frame. Instead, it **backtracks** into the ring buffer and selects the optimal frame from the recent history.

```
┌──────────────────────────────────────────────────────────────────┐
│                    RING BUFFER ARCHITECTURE                       │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Camera Stream (15 FPS) → Ring Buffer (deque, maxlen=75)         │
│                            ← 5 seconds of history →             │
│                                                                  │
│  Frame:  [F1][F2][F3]...[F70][F71][F72][F73][F74][F75]           │
│           ▲ oldest                              ▲ newest         │
│                                                                  │
│  AI triggers capture at F75 (detects handshake ending)           │
│                                                                  │
│  Backtrack Engine:                                               │
│    1. Scan buffer[F60..F75] (last 1 second)                      │
│    2. Run lightweight IQG on each candidate:                     │
│       - Laplacian sharpness score                                │
│       - Person detection confidence                              │
│       - Composition score (rule-of-thirds proximity)             │
│    3. Select frame with highest composite quality                │
│    4. Save THAT frame (not F75) to capture buffer                │
│                                                                  │
│  Result: Captures the PEAK of the handshake (F68),               │
│          not the aftermath (F75)                                  │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

#### 7.13.3 Ring Buffer Implementation

```python
from collections import deque
import numpy as np
import cv2
import time

class FrameRingBuffer:
    """
    Always-on circular buffer storing raw frames for retroactive capture.
    Memory: ~150 MB for 75 frames at 720p (1280×720×3 bytes × 75)
    """

    def __init__(self, max_seconds: float = 5.0, fps: int = 15):
        self.max_frames = int(max_seconds * fps)
        self.buffer = deque(maxlen=self.max_frames)
        self.timestamps = deque(maxlen=self.max_frames)

    def push(self, frame: np.ndarray):
        """Called every frame from the capture thread. O(1) amortized."""
        self.buffer.append(frame)
        self.timestamps.append(time.monotonic())

    def backtrack(self, lookback_seconds: float = 1.0,
                  candidates: int = 15) -> list:
        """
        Returns the last N frames for quality analysis.
        O(1) — deque supports efficient right-side slicing.
        """
        n = min(candidates, len(self.buffer))
        return list(self.buffer)[-n:]

    def get_best_frame(self, lookback_seconds: float = 1.0) -> np.ndarray:
        """
        Scan recent frames, score each for sharpness + composition,
        return the best one. Total cost: ~8ms for 15 candidates.
        """
        candidates = self.backtrack(lookback_seconds)
        if not candidates:
            return None

        best_frame = None
        best_score = -1

        for frame in candidates:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            # Laplacian sharpness (~0.3ms per frame at 720p)
            sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
            # Normalize to 0-1 range (empirical: good photos score 80-300)
            score = min(sharpness / 300.0, 1.0)

            if score > best_score:
                best_score = score
                best_frame = frame

        return best_frame

    @property
    def memory_usage_mb(self) -> float:
        """Estimated RAM usage."""
        if not self.buffer:
            return 0.0
        frame_bytes = self.buffer[0].nbytes
        return (frame_bytes * len(self.buffer)) / (1024 * 1024)
```

#### 7.13.4 Memory Budget

| Resolution | Bytes/Frame | Buffer Size (5s @ 15 FPS) | RAM Usage |
|---|---|---|---|
| 640×480 (VGA) | 921 KB | 75 frames | ~67 MB |
| 1280×720 (HD) | 2.7 MB | 75 frames | ~203 MB |
| 1920×1080 (FHD) | 6.2 MB | 75 frames | ~465 MB |
| **Recommended** | **720p** | **75 frames** | **~200 MB** |

**Optimization:** Store JPEG-compressed frames in the buffer instead of raw NumPy arrays. At quality=85, this reduces 720p from 2.7 MB to ~80 KB per frame, dropping total buffer RAM from 203 MB to ~6 MB. The trade-off is ~1ms encode + ~1ms decode per frame.

#### 7.13.5 Backtrack Trigger Events

The backtrack engine activates whenever the AI Orchestrator fires a capture. The backtrack depth (how far back to scan) varies by event type:

| Trigger | Backtrack Depth | Candidates Scanned | Rationale |
|---|---|---|---|
| **Standard capture** | 0.5s (8 frames) | 8 | Small window; the engagement sustain already delays the trigger |
| **Key moment detected** (handshake, spin) | 1.0s (15 frames) | 15 | Key moments are fast; need deeper lookback |
| **Dance burst mode** | 2.0s (30 frames) | 30 | Navratri/Garba spins complete in 1-2 seconds |
| **Cricket shot** | 1.5s (22 frames) | 22 | Bat-swing starts well before contact frame |
| **Manual shutter** | 0.3s (5 frames) | 5 | Photographer already timed it; minimal correction needed |

#### 7.13.6 Backtrack Quality Scoring (Composite)

Each candidate frame is scored on a weighted composite:

```
BacktrackScore = (0.50 × Sharpness) + (0.25 × FaceVisibility) + (0.25 × Composition)

Where:
  Sharpness    = Laplacian variance / 300.0, clamped [0, 1]
  FaceVisibility = (number of faces with det_score > 0.5) / expected_faces
  Composition  = Rule-of-thirds proximity score of primary subject centroid
```

**Total backtrack scoring cost: ~8ms for 15 candidates** (Laplacian only; face detection and composition scoring are optional and only run on the top 3 sharpest candidates to save compute).

---

### 7.14 Real-Time Performance Engineering

#### 7.14.1 Design Philosophy

The REC edge pipeline is a **hard real-time system**. Every millisecond of latency directly translates to missed moments. The architecture must be designed to:

1. **Never block the camera thread.** Frame capture runs in a dedicated thread with zero contention.
2. **Never process stale frames.** If inference is slower than capture, drop old frames and always process the newest.
3. **Never wait for I/O.** Disk writes, network uploads, and JSON state dumps happen asynchronously in background threads.

#### 7.14.2 Multi-Process Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│              EDGE NODE REAL-TIME PIPELINE (3-Stage)                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────┐   Shared    ┌──────────────────┐               │
│  │  STAGE 1:       │   Memory    │  STAGE 2:        │               │
│  │  CAPTURE THREAD │ ──────────► │  INFERENCE PROC  │               │
│  │  (I/O-bound)    │  (zero-copy)│  (CPU-bound)     │               │
│  │                 │             │                  │               │
│  │  • cv2.read()   │   Frame     │  • YOLOv8n       │               │
│  │  • Ring buffer  │   +         │  • ByteTrack     │               │
│  │    push         │   Metadata  │  • Engagement    │               │
│  │  • Timestamp    │             │  • Key Moment    │               │
│  └─────────────────┘             │  • Overlay draw  │               │
│                                  └────────┬─────────┘               │
│                                           │                         │
│                                    Queue (maxsize=1)                │
│                                           │                         │
│                                  ┌────────▼─────────┐               │
│                                  │  STAGE 3:        │               │
│                                  │  I/O WORKERS     │               │
│                                  │  (Background)    │               │
│                                  │                  │               │
│                                  │  • JPEG encode   │               │
│                                  │  • /tmp write    │               │
│                                  │  • State JSON    │               │
│                                  │  • Cloud upload  │               │
│                                  │  • Buffer save   │               │
│                                  └──────────────────┘               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

#### 7.14.3 Zero-Copy Shared Memory (Frame Passing)

Standard `multiprocessing.Queue` serializes NumPy arrays via `pickle`, which copies the entire frame (~2.7 MB at 720p) per transfer. At 15 FPS, this wastes ~40 MB/s of memory bandwidth and adds ~5ms latency per frame.

**Solution: `multiprocessing.shared_memory`**

```python
import multiprocessing.shared_memory as shm
import numpy as np

# Producer (Capture Thread) — writes frame to shared memory
def create_shared_frame(name: str, shape: tuple, dtype=np.uint8):
    """Create a shared memory block for a single frame."""
    nbytes = int(np.prod(shape)) * np.dtype(dtype).itemsize
    mem = shm.SharedMemory(name=name, create=True, size=nbytes)
    frame = np.ndarray(shape, dtype=dtype, buffer=mem.buf)
    return mem, frame

# Consumer (Inference Process) — reads frame without copy
def attach_shared_frame(name: str, shape: tuple, dtype=np.uint8):
    """Attach to existing shared memory. Zero-copy read."""
    mem = shm.SharedMemory(name=name, create=False)
    frame = np.ndarray(shape, dtype=dtype, buffer=mem.buf)
    return mem, frame
```

**Signaling:** A lightweight `multiprocessing.Event` or a 1-element `Queue` carrying only the frame index (not the frame data) signals the inference process that a new frame is ready.

#### 7.14.4 Lock-Free LIFO (Latest-Frame-Wins)

If the inference process is slower than the capture rate, a FIFO queue causes frames to pile up, increasing staleness. A **LIFO (Last-In-First-Out)** strategy ensures the inference process always works on the most recent frame:

```python
import threading

class LatestFrameBuffer:
    """
    Thread-safe single-slot buffer. Always returns the latest frame.
    Writers never block. Readers always get the newest data.
    """
    def __init__(self):
        self._frame = None
        self._lock = threading.Lock()

    def write(self, frame):
        with self._lock:
            self._frame = frame  # Overwrite — old frame is discarded

    def read(self):
        with self._lock:
            return self._frame
```

This is computationally equivalent to a `maxsize=1` queue but avoids the overhead of `Queue.put(block=False)` exception handling.

#### 7.14.5 Per-Stage Latency Budget (15 FPS = 66ms total)

| Stage | Operation | Budget | Optimization |
|---|---|---|---|
| **Capture** | `cv2.read()` + ring buffer push | 5ms | Threaded; never blocks inference |
| **Resize** | 720p → 640×640 for YOLO input | 1ms | `cv2.resize(INTER_NEAREST)` — fastest interpolation |
| **YOLO Detection** | YOLOv8n inference (person class) | 25ms | FP16 on GPU; INT8 via TensorRT on Jetson |
| **ByteTrack** | Multi-object tracking association | 1ms | Pure IoU + Kalman; zero CNN overhead |
| **Engagement Scoring** | Per-PID score computation | 2ms | NumPy vectorized; no Python loops |
| **Key Moment GRU** | Temporal action classification | 2ms | ONNX Runtime; 200 KB model |
| **Pose Estimation** | YOLOv8n-pose (if profile requires) | 12ms | Only enabled for Cricket/Dance profiles |
| **Overlay Drawing** | Ellipses + labels + state text | 3ms | `cv2.ellipse()` + `cv2.putText()` |
| **JPEG Encode** | Frame → JPEG for dashboard stream | 3ms | `cv2.imencode('.jpg', quality=70)` |
| **State JSON** | Orchestrator state → `/tmp/rec_state.json` | 0.5ms | `json.dumps()` + atomic file write |
| **Ring Buffer Save** | Capture-triggered backtrack + save | 8ms | Async; runs in I/O worker thread |
| **Total (Standard)** | Without pose estimation | **~41ms** | **24 FPS headroom** |
| **Total (Pose)** | With pose estimation | **~53ms** | **18 FPS headroom** |

#### 7.14.6 Frame Skipping Strategy

To maintain real-time performance on CPU-only hardware, apply intelligent frame skipping:

| Operation | Skip Pattern | Effective Rate | Rationale |
|---|---|---|---|
| **Frame Capture** | Every frame | 15 FPS | Never skip capture; ring buffer needs all frames |
| **YOLO Detection** | Every frame | 15 FPS | Core pipeline; must run at full rate |
| **ByteTrack** | Every frame | 15 FPS | Tracker needs continuous input for smooth association |
| **Engagement Scoring** | Every frame | 15 FPS | Sustain counter depends on frame-by-frame continuity |
| **Key Moment GRU** | Every 3rd frame | 5 FPS | Temporal model needs 30-frame windows; 5 FPS input is sufficient |
| **Pose Estimation** | Every 3rd frame | 5 FPS | Expensive; keypoints change slowly relative to pose duration |
| **Re-ID (OSNet)** | Every 15th frame | 1 FPS | Appearance signatures change slowly |
| **Overlay Rendering** | Every frame | 15 FPS | Visual continuity for dashboard |

#### 7.14.7 Async I/O Queue (Non-Blocking Writes)

All disk and network I/O is offloaded to a dedicated worker thread via a `queue.Queue`:

```python
import queue
import threading

class AsyncIOWorker:
    """
    Non-blocking I/O worker. Capture and inference never wait for disk.
    """
    def __init__(self):
        self.queue = queue.Queue(maxsize=50)
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def _worker(self):
        while True:
            task = self.queue.get()
            try:
                task()
            except Exception as e:
                logging.error(f"I/O worker error: {e}")
            self.queue.task_done()

    def submit(self, task_fn):
        """Submit a callable to be executed asynchronously."""
        try:
            self.queue.put_nowait(task_fn)
        except queue.Full:
            pass  # Drop oldest writes if queue is full (non-critical)
```

**Usage:** Frame saves, JSON state writes, JPEG encoding for the dashboard, and cloud uploads are all submitted to this worker, ensuring the inference loop never blocks on I/O.

#### 7.14.8 Algorithmic Optimizations (Micro-Level)

| Operation | Naive Cost | Optimized Cost | Technique |
|---|---|---|---|
| **Gini coefficient** | O(n log n) sort | O(n) | Pre-maintain sorted insertion list; incremental update on capture |
| **Cooldown lookup** | O(n) linear scan | O(1) | `dict` keyed by PID with expiry timestamps |
| **Priority queue** | O(n) linear scan | O(log n) | `heapq` with (negative_priority, PID) tuples |
| **IoU computation** | O(n²) pairwise | O(n log n) | Spatial indexing via interval trees for bbox overlap |
| **Frame resize** | `INTER_LINEAR` | `INTER_NEAREST` | 2-4x faster; negligible quality difference for detection input |
| **Color hist** | `cv2.calcHist` full frame | ROI-only crop | Process only the person bbox region, not the entire frame |
| **JSON state dump** | `json.dumps` every frame | Rate-limited to 2 Hz | State changes slowly; 2 Hz is sufficient for dashboard |
| **JPEG encode** | Quality=95 | Quality=70 | 2-3x faster encoding; dashboard stream doesn't need archival quality |

---



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

### 12.2 Data Protection & Edge Node Security

#### 12.2.1 Transport & Storage Security

| Layer | Measure |
|---|---|
| **Transport** | TLS 1.3 for all API and file transfer traffic |
| **Storage** | AES-256 encryption at rest for S3/MinIO objects |
| **Database** | PostgreSQL TDE or column-level encryption for embeddings |
| **Access Control** | RBAC: Admin, Photographer, Viewer roles |
| **API Auth** | JWT with short-lived tokens (15min) + refresh tokens |
| **Selfie Upload** | Processed in memory, embedding extracted, raw selfie optionally deleted immediately |
| **Audit Logging** | All data access and deletion events logged immutably |

#### 12.2.2 Edge Node Authentication — Server-Side Only (MANDATORY)

> **CRITICAL DESIGN CONSTRAINT:** All authentication and authorization decisions are made EXCLUSIVELY on the cloud backend server. The edge node is treated as an UNTRUSTED client. It never validates tokens locally, never stores signing secrets, and never makes access decisions independently.

**Authentication Flow (Strict Server-Side):**

```
┌──────────────────┐         ┌──────────────────────┐        ┌──────────────────┐
│   EDGE NODE      │         │   CLOUD BACKEND      │        │   PostgreSQL     │
│   (Untrusted)    │         │   (Trusted Authority)│        │   Auth DB        │
│                  │         │                      │        │                  │
│  1. Photographer │         │                      │        │                  │
│     enters creds │         │                      │        │                  │
│     in browser   │         │                      │        │                  │
│                  │  HTTPS  │                      │        │                  │
│  2. Edge server  │────────►│  3. Server validates  │───────►│  4. bcrypt hash  │
│     forwards     │  POST   │     against DB        │ SELECT │     comparison   │
│     credentials  │ /login  │                      │        │                  │
│     (plain relay)│         │                      │        │                  │
│                  │◄────────│  5. Returns signed    │        │                  │
│  6. Edge stores  │  JWT    │     JWT (RS256)      │        │                  │
│     token in     │  token  │     15min expiry     │        │                  │
│     HTTP-only    │         │                      │        │                  │
│     cookie ONLY  │         │                      │        │                  │
│                  │         │                      │        │                  │
│  7. ALL subsequent│        │                      │        │                  │
│     API calls    │────────►│  8. Server validates  │        │                  │
│     include JWT  │ Bearer  │     JWT signature,   │        │                  │
│     in header    │  token  │     expiry, claims   │        │                  │
│                  │         │                      │        │                  │
│  9. If 401 →     │◄────────│  10. Returns 401     │        │                  │
│     Kill orch,   │  401    │      if invalid      │        │                  │
│     redirect to  │         │                      │        │                  │
│     /login       │         │                      │        │                  │
└──────────────────┘         └──────────────────────┘        └──────────────────┘
```

#### 12.2.3 What the Edge Node MUST NOT Do

The following operations are STRICTLY PROHIBITED on the edge node. Violating any of these constitutes a critical security vulnerability:

| Prohibited Action | Reason |
|---|---|
| ❌ Store JWT signing secret (private key) on disk or in memory | An attacker with filesystem access could forge unlimited valid tokens |
| ❌ Validate JWT signatures locally | Local validation can be bypassed by patching the validation function in the Python source |
| ❌ Store credentials in plaintext, `.env`, or config files | Any local credential cache can be extracted by a malicious actor |
| ❌ Use hardcoded "backdoor" credentials in production builds | Sandbox bypass (`photographer1/password`) is disabled via `BUILD_MODE=production` environment variable |
| ❌ Allow the Orchestrator to start without a valid server-issued token | The Orchestrator subprocess receives the token as an environment variable; the cloud API validates it on every `/upload` call |
| ❌ Cache authentication state locally between app restarts | Every app launch requires a fresh login. No "remember me" on edge devices |
| ❌ Use symmetric JWT signing (HS256) | HS256 requires the secret on both sides. RS256/ES256 ensures only the server can sign |

#### 12.2.4 JWT Token Architecture

| Property | Value | Rationale |
|---|---|---|
| **Algorithm** | RS256 (RSA + SHA-256) | Asymmetric: only the cloud server holds the private key. The edge node cannot forge tokens. |
| **Access Token TTL** | 15 minutes | Short-lived to limit exposure window if token is intercepted |
| **Refresh Token TTL** | 24 hours | Allows session persistence during a full event day without re-login |
| **Refresh Token Rotation** | Enabled | Each refresh request issues a new refresh token and invalidates the old one. Detects token theft. |
| **Claims** | `sub` (photographer ID), `role` ("photographer"), `event_id`, `exp`, `jti` (unique token ID) | Minimal claims; no PII in token payload |
| **Revocation** | Server-side blacklist in Redis (`jti` → TTL matching token expiry) | Enables immediate revocation if device is compromised |
| **Audience** | `rec-edge-node` | Prevents tokens issued for other services from being used on the edge API |

#### 12.2.5 Edge Node Anti-Tampering Measures

Since the edge node runs on photographer-owned hardware (laptops), additional hardening is required:

| Threat | Mitigation |
|---|---|
| **Source code modification** (attacker edits `server.py` to skip auth) | PyInstaller binary compilation with `--key` flag encrypts bytecode. Source files are not shipped in production builds. |
| **Memory dumping** (attacker reads JWT from process memory) | Short-lived tokens (15min) limit the value of stolen tokens. Refresh token rotation detects reuse. |
| **Network interception** (MITM captures JWT in transit) | All edge ↔ cloud communication uses TLS 1.3. Certificate pinning enforced in production. |
| **Token replay** (attacker reuses captured JWT on different device) | `jti` claim + server-side Redis blacklist. Hardware fingerprint (`machine-id`) embedded in token claims for device binding. |
| **Offline operation** (attacker disconnects from internet to avoid auth) | The Orchestrator periodically (every 5 minutes) calls a cloud `/heartbeat` endpoint. If it receives 3 consecutive failures AND the token has expired, the Orchestrator self-terminates. Photos captured during brief offline periods are stored locally and synced when connectivity resumes. |
| **Binary reverse engineering** | UPX compression + PyInstaller `--key` AES encryption. While not unbreakable, it raises the difficulty significantly above the typical photographer threat model. |

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


---

### 7.12 Edge Case Scenarios & Handling Matrix

> **Every scenario below has been encountered in real-world event photography. Each one defines the exact detection strategy, camera adjustment, and capture decision to prevent deadlock or false output.**

#### Category A: High-Motion Scenarios

| # | Scenario | Detection Challenge | Camera Adjustment | Capture Strategy |
|---|---|---|---|---|
| A1 | **People Dancing** | Rapid limb movement causes bbox jitter, face blur, and tracking ID swaps | Shutter >= 1/500s, ISO auto-raise to 3200+, aperture f/2.8 for light | **Relax motion stability gate** to 25px/frame (up from 15). Use burst mode: fire 3-frame burst, keep sharpest via IQG blur score. Engagement threshold drops to 0.40 when scene `avg_velocity > 30px/frame`. |
| A2 | **Children Running** | Unpredictable trajectory, small bbox, frequent exit/re-entry | Shutter >= 1/500s, continuous AF (AF-C), burst mode | Lower `MIN_FACE_HEIGHT_PX` to 60 for child-size bboxes. Increase tracker `max_age` to 90 frames (children exit and re-enter fast). Starvation detector activates at 30s instead of 60s. |
| A3 | **Walking Subjects** | Moderate motion, periodic face occlusion (head turns while walking) | Shutter >= 1/250s | **Predict stop point:** if velocity is decelerating over 5 frames, pre-focus on predicted stop location. Capture on the deceleration frame where velocity < 10px/frame. |
| A4 | **Stage Performance** | Rapid movement, colored stage lighting, spotlight extremes | Shutter >= 1/500s, exposure comp -0.7 (spotlight), custom WB | Use `stage_zone` ROI mask. Accept higher motion blur for artistic effect. **Disable engagement score** for stage zone (performers don't look at autonomous cameras). Capture on beat pauses. |

#### Category B: Occlusion & Overlap

| # | Scenario | Detection Challenge | Handling Strategy |
|---|---|---|---|
| B1 | **People Overlapping (Crowd)** | Merged bounding boxes, suppressed detections via NMS | Use Soft-NMS (score decay instead of hard suppression). If two bboxes overlap > 60% IoU, track the merged entity and split when separation detected. **Never discard a high-confidence (>0.7) detection just because it overlaps another.** |
| B2 | **Person Behind Pillar/Object** | Track lost during occlusion, new ID assigned on re-emergence | Tracker `max_age = 60 frames` (4s at 15fps). On re-emergence, immediately run Re-ID matching against gallery within 200px radius of last-known position. Spatial-temporal plausibility score handles this. |
| B3 | **Person Sitting Down / Standing Up** | Bbox aspect ratio changes dramatically (0.5 → 1.2), tracker may lose ID | Body proportion feature weight reduced to 0.05 during transition (detect posture change via aspect ratio delta > 0.3 between frames). Deep embedding + color histogram maintain identity. |
| B4 | **Person Turns Around (Back to Camera)** | Face detection drops, person detection stays | Enter `CANDID_BEHIND` mode. **Do NOT trigger face-required shutter gate.** Instead, use body-only composition for interaction shots (two people facing each other, captured from behind one). Log as candid, not portrait. |

#### Category C: Lighting & Environment

| # | Scenario | Detection Challenge | Camera Adjustment | Handling Strategy |
|---|---|---|---|---|
| C1 | **Backlit Subject (Silhouette)** | Face underexposed, detection confidence drops | Exposure comp +1.0 to +1.5, fill flash if available | If face `det_score < 0.5` but person `conf > 0.7`, increase exposure comp and **retry detection on next frame** before giving up. Max 3 retries. |
| C2 | **Very Low Light (Dance Floor)** | Noise causes false detections, AF hunts | ISO 3200-6400, shutter 1/125s minimum, f/1.8-2.0 | Raise `PERSON_CONF_THRESHOLD` to 0.60 (more strict to filter noise-based ghosts). Accept lower aesthetic scores from NIMA (threshold 3.5 instead of 4.5). |
| C3 | **Sudden Light Change (Flash/Spotlight Sweep)** | Temporary whiteout/blackout causes mass track loss | Auto-exposure adaptation | **Freeze all capture decisions for 500ms** after detecting > 50% pixel intensity change between frames. Resume after exposure stabilizes. Prevents burst-firing during transitions. |
| C4 | **Mixed Color Temperature (LED + Daylight)** | Skin tones appear unnatural, face detection accuracy drops | Custom WB per zone, or shoot RAW | Post-capture WB correction. Detection models are trained on diverse lighting; no detection-level adjustment needed. |

#### Category D: False Positive Sources

| # | Scenario | False Positive Cause | Elimination Strategy |
|---|---|---|---|
| D1 | **Mirrors / Glass Reflections** | Model detects reflection as second person | **Static zone masking:** During venue setup, calibrate known mirror/glass locations and mask those ROIs. **Runtime:** If two detections are perfectly symmetric across a vertical axis and one is in a known reflective zone, suppress the reflected one. |
| D2 | **Posters / Banners with People** | High-res printed faces trigger face detection | **Temporal consistency filter:** If a "person" has zero pixel movement for > 10 seconds, flag as static object and permanently suppress that bbox region for the session. |
| D3 | **TV Screens / Projectors** | Video of people on screens triggers detection | **Screen zone exclusion:** Pre-calibrate known screen locations. **Runtime:** Detect rectangular high-refresh-rate regions (flickering at 60Hz vs static environment) and exclude from detection pipeline. |
| D4 | **Mannequins / Statues** | Human-shaped objects trigger person detection | Same as D2: zero-movement temporal filter. If `centroid_velocity == 0` for 300+ consecutive frames (20s), add bbox center to permanent exclusion list. |

#### Category E: Social & Interaction Scenarios

| # | Scenario | Detection Challenge | Capture Strategy |
|---|---|---|---|
| E1 | **Two People Talking (Conversation)** | Faces partially turned toward each other, not camera | **INTERACTION mode.** Detect via: two PIDs within 1.5x body-width, face yaw > 20 deg toward each other. Capture from slight angle showing both faces. Engagement gate uses body-language signals (leaning in, gestures) instead of smile/gaze. |
| E2 | **Handshake / Award Ceremony** | Brief moment (~2s), requires precise timing | **Event trigger mode:** When two people approach each other and arm positions suggest reaching, reduce `MIN_SUSTAIN_FRAMES` to 1 (instant trigger). Burst 3 frames. Pick best via IQG. |
| E3 | **Toast / Raised Glasses** | Arms raised obscure faces, unusual body pose | Lower face-height requirement to 50px. Accept partial face visibility. Prioritize wide-angle framing showing the gesture. Classify as `CEREMONY` mode with f/5.6 for group depth. |
| E4 | **Speaker at Podium** | Static person, same angle for extended time | After 3 captures of same PID at same angle from podium zone, **force-rotate to audience reaction shots**. Alternate: 2 speaker captures → 1 audience reaction capture. Prevents 50 identical speaker photos. |
| E5 | **Entrance / Exit Transition** | Person appears for < 3 seconds, moves quickly through frame | Reduce `TEMPORAL_CONSISTENCY_FRAMES` to 2 for entrance/exit zones. Pre-focus on entrance point. Capture on first valid engagement frame, bypass normal cooldown for entrance-zone PIDs. |

#### Category F: System & Hardware Edge Cases

| # | Scenario | Failure Mode | Fail-Safe |
|---|---|---|---|
| F1 | **Camera AF Fails to Lock** | AF timeout (500ms) exceeded, no capture | **Skip AF, capture anyway** with last-known focus distance. Better to have slightly soft focus than zero captures. Log as `AF_FALLBACK`. IQG blur filter will discard if truly unusable. |
| F2 | **Detection Model Returns Zero Detections Despite People Present** | Model blind spot, lighting, or angle issue | **Heartbeat system (Section 7.7.2)** force-captures after 45s of silence. Additionally: if person_count was > 0 for 10+ seconds then drops to 0, lower `PERSON_CONF_THRESHOLD` by 0.05 for 5 seconds and re-evaluate. |
| F3 | **Storage Full / Write Error** | Disk/SSD at capacity | **Stop capturing immediately.** Send Redis alert to Admin portal. Begin deleting IQG-rejected images first (lowest aesthetic score). Resume when > 500MB free. Never lose approved images. |
| F4 | **All PIDs in Cooldown Simultaneously** | Deadlock: everyone visible but everyone blocked | **Immediate override:** Reset all cooldowns to `COOLDOWN_MIN_SEC` (5s). Log `COOLDOWN_MASS_RESET`. This can only happen when very few people are present. The dynamic decay system (7.7.1) prevents this in crowds. |
| F5 | **Tracker ID Explosion (Too Many PIDs)** | Memory/CPU overload from hundreds of stale PIDs | **Garbage collection:** Every 60 seconds, prune PIDs not seen for > 300 seconds (5 min). Cap active gallery at 500 PIDs. Oldest unseen PIDs evicted first (LRU). |

#### Edge Case Constants

```python
# === EDGE CASE OVERRIDES (HARDCODED) ===
DANCE_MOTION_VELOCITY_THRESHOLD  = 25      # Relaxed from 15px/frame for dancing
DANCE_ENGAGEMENT_THRESHOLD       = 0.40    # Lowered from 0.55 for high-motion
DANCE_BURST_FRAMES               = 3       # Burst capture count in dance mode
CHILD_MIN_FACE_HEIGHT_PX         = 60      # Lowered from 80 for smaller faces
CHILD_STARVATION_SEC             = 30      # Faster starvation for children (vs 60s)
STAGE_ENGAGEMENT_BYPASS          = True    # Skip engagement score for performers
BACKLIT_RETRY_MAX                = 3       # Max exposure retry attempts
LIGHT_CHANGE_FREEZE_MS           = 500     # Pause captures during light transitions
STATIC_OBJECT_SUPPRESS_FRAMES   = 300     # 20s at 15fps = flag as poster/mannequin
HANDSHAKE_SUSTAIN_FRAMES         = 1       # Instant trigger for brief moments
ENTRANCE_ZONE_TEMPORAL_FRAMES   = 2       # Faster temporal consistency at doors
AF_FALLBACK_ENABLED              = True    # Capture even if AF fails
COOLDOWN_MASS_RESET_ENABLED      = True    # Emergency override when all PIDs blocked
PID_GALLERY_MAX                  = 500     # Max active PIDs in gallery
PID_EVICTION_TIMEOUT_SEC         = 300     # Prune PIDs unseen for 5 minutes
STORAGE_CRITICAL_MB              = 500     # Min free space before auto-cleanup
SPEAKER_AUDIENCE_RATIO           = (2, 1)  # 2 speaker shots per 1 audience reaction
LOW_LIGHT_NIMA_THRESHOLD         = 3.5     # Relaxed from 4.5 in low light
LOW_LIGHT_CONF_THRESHOLD         = 0.60    # Stricter person detection in noise
```

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

*End of PRD v1.1.0*






