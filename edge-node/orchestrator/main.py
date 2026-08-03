"""
REC Edge Node — Capture Orchestrator
=====================================
The brain of the autonomous capture pipeline.

Flow:
  1. Pull live preview frame from camera driver
  2. Run person detection (simulated for mock; real YOLOv8n in production)
  3. Evaluate engagement + cooldown + diversity via PRD Section 7 rules
  4. Trigger shutter on the highest-priority PID
  5. Push captured image path to Redis `raw_images` queue for cloud sync
  6. Apply all edge case overrides (dancing, occlusion, AF fallback, etc.)

All constants match PRD Section 7.11 and 7.12 exactly.
"""

import os
import time
import json
import uuid
import logging
import cv2
import numpy as np
import redis as redislib
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Tuple, Set

# New Real-Time Pipeline Modules
from orchestrator.capture.ingestion import CameraIngestionProcess
from orchestrator.memory.shared_pool import attach_shared_frame
from orchestrator.utils.io_worker import io_worker
from orchestrator.capture.ring_buffer import FrameRingBuffer
from orchestrator.utils.profiles import get_profile, EventProfile
from orchestrator.intelligence.key_moment import TemporalFeatureBuffer, KeyMomentClassifier
from orchestrator.intelligence.smile_detector import SmileDetector

# Try importing fast_iqg from edge-node/iqg (added to path or relative)
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from orchestrator.utils.aspect_framing import compute_framing_box, crop_frame_to_box, parse_aspect_ratio, compute_composition_score, compute_bbox_iou, _clean_config_string

try:
    from iqg.fast_iqg import get_best_backtrack_frame
except Exception as e:
    def get_best_backtrack_frame(candidates):
        if not candidates:
            return None, 0.0, -1
        return candidates[-1], 0.0, len(candidates) - 1

# ─────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="[ORCH] %(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("orchestrator")


# ─────────────────────────────────────────────────────────────────
# HARDCODED CONSTANTS — PRD Section 7.11 + 7.12
# DO NOT MAKE THESE CONFIGURABLE AT RUNTIME.
# ─────────────────────────────────────────────────────────────────

# Cooldown & Burst Rules
COOLDOWN_MIN_SEC            = 3.0
COOLDOWN_BASE_SEC           = 8.0
COOLDOWN_MAX_SEC            = 60.0
ESCALATION_PER_CAPTURE      = 0.3
DECAY_RATE_PER_SEC          = 0.02
GLOBAL_MIN_INTERVAL_SEC     = 1.5
GLOBAL_MAX_IDLE_SEC         = 15.0
HEARTBEAT_FORCE_SEC         = 15.0
STARVATION_THRESHOLD_SEC    = 25.0
MAX_PHOTOS_PER_BURST_COOLDOWN = 3       # Max 3 captures per person before mandatory cooldown
PERSON_BURST_COOLDOWN_SEC     = 35.0    # 35s cooldown after 3 captures
DEFAULT_ASPECT_RATIO          = "16:9"  # Default aspect ratio (Landscape)
DEFAULT_FRAMING_SCALE         = "AUTO"  # Default framing scale (Auto-Fit)

# Pose-Change Gated Burst Control (Anti-Duplicate)
# PRD 7.7.3: Similarity Suppression — prevent identical captures
BURST_MIN_INTERVAL_SEC        = 2.5     # Minimum seconds between any two captures of same PID
POSE_CHANGE_IOU_THRESHOLD     = 0.72    # If IoU(current bbox, last captured bbox) > this, block = too similar
POSE_CHANGE_CENTROID_PX       = 20      # Minimum centroid displacement (px) required to consider pose changed
MIN_COMPOSITION_SCORE         = 0.25    # Minimum composition score to allow capture (avoid terrible framing)

# Quality Gating & Progressive Patience ("Best-of-Worst" Engine)
TARGET_QUALITY_THRESHOLD    = 0.48      # Initial high-quality standard
MIN_FALLBACK_QUALITY        = 0.20      # Minimum acceptable quality during starvation/timeout
PATIENCE_START_SEC          = 1.5       # Initial high-standard observation period
PATIENCE_MAX_SEC            = 4.5       # Maximum patience window before forcing best-of-worst candidate capture

# Engagement
ENGAGEMENT_THRESHOLD        = 0.55
ENGAGEMENT_EMERGENCY        = 0.35
ENGAGEMENT_STARVATION       = 0.30
MIN_SUSTAIN_FRAMES          = 3

# Diversity
MAX_SOLO_CAPTURES_PER_PID   = 8
MAX_TOTAL_CAPTURES_PER_PID  = 20
GINI_TARGET                 = 0.35
GINI_EQUITY_ENTER           = 0.40
GINI_EQUITY_EXIT            = 0.30

# Similarity suppression
SIMILARITY_WINDOW_SEC       = 60.0
MAX_SAME_ANGLE_PER_PID      = 2

# Detection filters
PERSON_CONF_THRESHOLD       = 0.50
BBOX_ASPECT_RATIO_MIN       = 0.15
BBOX_ASPECT_RATIO_MAX       = 0.80
MIN_BBOX_AREA_PX            = 2500
TEMPORAL_CONSISTENCY_FRAMES = 3
MOTION_VELOCITY_THRESHOLD   = 15    # px/frame (normal); 25 for dancing

# Edge case overrides (PRD Section 7.12)
DANCE_MOTION_VEL_THRESHOLD  = 25
DANCE_ENGAGEMENT_THRESHOLD  = 0.40
DANCE_BURST_FRAMES          = 3
CHILD_MIN_FACE_HEIGHT_PX    = 60
STATIC_OBJECT_SUPPRESS_FR   = 300   # 20s at 15fps
HANDSHAKE_SUSTAIN_FRAMES    = 1
ENTRANCE_TEMPORAL_FRAMES    = 2
AF_FALLBACK_ENABLED         = True
COOLDOWN_MASS_RESET_ENABLED = True
PID_GALLERY_MAX             = 500
PID_EVICTION_TIMEOUT_SEC    = 300
STORAGE_CRITICAL_MB         = 500
LOW_LIGHT_CONF_THRESHOLD    = 0.60
LIGHT_CHANGE_FREEZE_MS      = 500


# ─────────────────────────────────────────────────────────────────
# Data Structures
# ─────────────────────────────────────────────────────────────────

@dataclass
class PersonDetection:
    track_id: str
    bbox: Tuple[int, int, int, int]   # x1, y1, x2, y2
    confidence: float
    centroid: Tuple[int, int]
    area: int
    aspect_ratio: float
    timestamp: float
    keypoints: Optional[np.ndarray] = None


@dataclass
class FrameCandidate:
    """Holds a snapshot of the best observed candidate moment for a subject."""
    frame: np.ndarray                   # Snapshot frame
    score: float                        # Composite score (0.0 to 1.0)
    engagement: float                   # Engagement score (0.0 to 1.0)
    sharpness: float                    # Sharpness score (0.0 to 1.0)
    framing_box: List[int]              # Exact crop box
    aspect_ratio: str                   # Selected aspect ratio
    framing_scale: str                  # Framing scale
    timestamp: float                    # Monotonic time observed
    bbox: Tuple[int, int, int, int]     # Raw person bbox


@dataclass
class PIDState:
    pid: str
    capture_count: int = 0
    session_capture_count: int = 0      # Tracks photos toward 3-photo burst cap
    cooldown_until: float = 0.0         # Mandatory cooldown timestamp
    last_capture_time: float = 0.0
    last_seen_time: float = field(default_factory=time.monotonic)
    first_seen_time: float = field(default_factory=time.monotonic)
    visible_duration: float = 0.0
    consecutive_frames: int = 0         # for temporal consistency
    centroid_history: List[Tuple[int,int]] = field(default_factory=list)
    angles_captured: Set[str] = field(default_factory=set)
    # Quality & Engagement scoring
    engagement_score: float = 0.0
    sharpness_score: float = 0.0
    composite_score: float = 0.0
    composition_score: float = 0.0      # PRD 5.5 photographic composition quality
    engagement_sustained_frames: int = 0
    # Smile Detection Feature
    is_smiling: bool = False
    smile_score: float = 0.0
    # Progressive Patience & Rolling Candidate Tracking ("Best-of-Worst")
    patience_start_time: float = field(default_factory=time.monotonic)
    best_candidate: Optional[FrameCandidate] = None
    # Pose-Change Tracking (Anti-Duplicate Burst)
    last_captured_bbox: Optional[List[int]] = None           # bbox at last capture moment
    last_captured_centroid: Optional[Tuple[int,int]] = None  # centroid at last capture
    # Edge case flags
    engagement_override: Optional[float] = None  # starvation override
    cooldown_override: Optional[float] = None     # starvation cooldown=0


# ─────────────────────────────────────────────────────────────────
# Scene State
# ─────────────────────────────────────────────────────────────────

class SceneState:
    """Holds the current state of the entire scene — all visible PIDs with thread synchronization."""

    def __init__(self):
        import threading
        self._lock = threading.RLock()
        self.pids: Dict[str, PIDState] = {}
        self.last_global_capture_time: float = 0.0
        self.last_frame_time: float = time.monotonic()
        self.equity_mode: bool = False
        self.profile: EventProfile = get_profile("DEFAULT")
        self.engagement_threshold: float = self.profile.engagement_threshold
        self.person_conf_threshold: float = PERSON_CONF_THRESHOLD
        self.last_pixel_intensity: Optional[float] = None
        self.light_change_freeze_until: float = 0.0
        self.static_zones: List[Tuple[int,int]] = []  # (cx, cy) of suppressed static objects
        self.frame_count: int = 0

    def register_detection(self, det: PersonDetection) -> str:
        """Register or update a detection in a thread-safe manner. Returns PID."""
        pid = det.track_id
        now = time.monotonic()

        with self._lock:
            if pid not in self.pids:
                self.pids[pid] = PIDState(pid=pid, first_seen_time=now, last_seen_time=now, patience_start_time=now)

            state = self.pids[pid]
            state.last_seen_time = now
            state.visible_duration = now - state.first_seen_time
            state.consecutive_frames += 1

            # Track centroid history for velocity calculation
            state.centroid_history.append(det.centroid)
            if len(state.centroid_history) > 10:
                state.centroid_history.pop(0)

        return pid

    def compute_velocity(self, pid: str) -> float:
        """Compute centroid velocity in px/frame."""
        with self._lock:
            if pid not in self.pids:
                return 0.0
            history = self.pids[pid].centroid_history
            if len(history) < 2:
                return 0.0
            dx = history[-1][0] - history[-2][0]
            dy = history[-1][1] - history[-2][1]
            return float(np.sqrt(dx**2 + dy**2))

    def compute_composite_quality(self, frame: np.ndarray, det: PersonDetection, framing_box: List[int]) -> Tuple[float, float, float]:
        """
        Computes a multi-signal quality score: (composite_score, engagement_score, sharpness_score).
        Uses professional composition scoring (Rule-of-Thirds, headroom, subject fill)
        combined with sharpness analysis, motion stability, and body structure.
        """
        # 1. Laplacian sharpness of framed crop
        crop = crop_frame_to_box(frame, framing_box)
        if crop.size > 0:
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop
            lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            sharpness_score = min(1.0, float(lap_var) / 160.0)
        else:
            sharpness_score = 0.0

        # 2. Motion stability
        velocity = self.compute_velocity(det.track_id)
        stable = 1.0 if velocity < self.profile.motion_velocity_threshold else max(0.0, 1.0 - velocity / 45.0)

        # 3. Aspect ratio / Face region structure
        aspect_score = 1.0 if 0.20 < det.aspect_ratio < 0.85 else 0.45

        # 4. Professional composition scoring (eye-line, headroom, subject fill, RoT)
        comp_score = compute_composition_score(list(det.bbox), framing_box, keypoints=det.keypoints)

        engagement = 0.35 * stable + 0.35 * sharpness_score + 0.30 * aspect_score
        composite = 0.35 * sharpness_score + 0.35 * engagement + 0.30 * comp_score
        return round(composite, 3), round(engagement, 3), round(sharpness_score, 3)

    def compute_engagement(self, frame: np.ndarray, det: PersonDetection) -> float:
        """Legacy proxy wrapper for engagement calculation."""
        fb = [det.bbox[0], det.bbox[1], det.bbox[2], det.bbox[3]]
        _, eng, _ = self.compute_composite_quality(frame, det, fb)
        return eng

    def dynamic_cooldown(self, pid: str) -> float:
        """PRD 7.7.1: Escalating + decaying cooldown."""
        with self._lock:
            if pid not in self.pids:
                return COOLDOWN_BASE_SEC
            state = self.pids[pid]
            if state.cooldown_override is not None:
                return state.cooldown_override

            base = self.profile.cooldown_base_sec
            escalated = base * (1.0 + ESCALATION_PER_CAPTURE * state.capture_count)
            idle = time.monotonic() - state.last_seen_time
            decay = max(0.3, 1.0 - DECAY_RATE_PER_SEC * idle)
            result = escalated * decay
            return max(COOLDOWN_MIN_SEC, min(COOLDOWN_MAX_SEC, result))

    def in_cooldown(self, pid: str) -> bool:
        with self._lock:
            if pid not in self.pids:
                return False
            state = self.pids[pid]
            now = time.monotonic()
            # Mandatory 3-photo burst cooldown
            if now < state.cooldown_until:
                return True
            if state.cooldown_until > 0 and now >= state.cooldown_until:
                state.cooldown_until = 0.0
                state.session_capture_count = 0
                state.patience_start_time = now
                state.best_candidate = None
                
            cooldown = self.dynamic_cooldown(pid)
            return (now - state.last_capture_time) < cooldown

    def compute_gini(self) -> float:
        """PRD 7.7.4: Gini coefficient of capture distribution."""
        counts = sorted([s.capture_count for s in self.pids.values()])
        n = len(counts)
        if n == 0:
            return 0.0
        total = sum(counts)
        if total == 0:
            return 0.0
        cumulative = sum((2 * (i + 1) - n - 1) * c for i, c in enumerate(counts))
        return cumulative / (n * total)

    def compute_priority(self, pid: str) -> float:
        """PRD 7.7.4: Dynamic priority score."""
        state = self.pids[pid]
        avg = sum(s.capture_count for s in self.pids.values()) / max(len(self.pids), 1)

        base = max(0.1, 1.0 - (state.capture_count / max(avg * 2, 1)))
        novelty = 1.5 if state.capture_count == 0 else 1.0
        angle_var = 1.3 if len(state.angles_captured) < 3 else 1.0
        cooldown_mod = 0.0 if self.in_cooldown(pid) else 1.0
        starvation = 2.0 if state.capture_count == 0 and state.visible_duration > 30 else 1.0

        return base * novelty * angle_var * cooldown_mod * starvation

    def evict_stale_pids(self):
        """PRD F5: LRU eviction of PIDs unseen > 5 min."""
        now = time.monotonic()
        stale = [pid for pid, s in self.pids.items()
                 if (now - s.last_seen_time) > PID_EVICTION_TIMEOUT_SEC]
        for pid in stale:
            del self.pids[pid]
        if len(self.pids) > PID_GALLERY_MAX:
            # Evict oldest unseen
            sorted_pids = sorted(self.pids.items(), key=lambda x: x[1].last_seen_time)
            for pid, _ in sorted_pids[:len(self.pids) - PID_GALLERY_MAX]:
                del self.pids[pid]

    def watchdog_check(self):
        """PRD 7.7.2 Fail-Safe 1: Global idle watchdog."""
        now = time.monotonic()
        idle = now - self.last_global_capture_time
        if idle > GLOBAL_MAX_IDLE_SEC and self.last_global_capture_time > 0:
            log.warning(f"WATCHDOG: No capture for {idle:.0f}s — halving all cooldowns, dropping threshold")
            for state in self.pids.values():
                state.last_capture_time = max(0, state.last_capture_time - self.dynamic_cooldown(state.pid) * 0.5)
            self.engagement_threshold = ENGAGEMENT_EMERGENCY

    def starvation_check(self):
        """PRD 7.7.2 Fail-Safe 2: Starvation detector."""
        for pid, state in self.pids.items():
            if state.visible_duration > STARVATION_THRESHOLD_SEC and state.capture_count == 0:
                state.cooldown_override = 0.0
                state.engagement_override = ENGAGEMENT_STARVATION
                log.warning(f"STARVATION: PID {pid} unlocked after {state.visible_duration:.0f}s with 0 captures")

    def check_light_change(self, frame: np.ndarray) -> bool:
        """PRD C3: Detect sudden light change and freeze captures."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        intensity = float(np.mean(gray))
        freeze = False
        if self.last_pixel_intensity is not None:
            change = abs(intensity - self.last_pixel_intensity) / max(self.last_pixel_intensity, 1)
            if change > 0.50:
                self.light_change_freeze_until = time.monotonic() + (LIGHT_CHANGE_FREEZE_MS / 1000.0)
                log.info(f"LIGHT_CHANGE: {change:.1%} intensity shift — freezing {LIGHT_CHANGE_FREEZE_MS}ms")
                freeze = True
        self.last_pixel_intensity = intensity
        return freeze


# ─────────────────────────────────────────────────────────────────
# Static Object Suppressor (PRD D2, D4)
# ─────────────────────────────────────────────────────────────────

class StaticObjectSuppressor:
    """Tracks detections that never move — flags as poster/mannequin (unless keypoints indicate live human)."""

    def __init__(self):
        self._static_counts: Dict[str, int] = {}  # track_id → static frame count
        self._suppressed: Set[str] = set()

    def update(self, track_id: str, velocity: float, has_keypoints: bool = False):
        if has_keypoints:
            # Active human pose with skeletal keypoints detected — never suppress
            self._static_counts[track_id] = 0
            self._suppressed.discard(track_id)
            return

        if velocity < 0.5:
            self._static_counts[track_id] = self._static_counts.get(track_id, 0) + 1
        else:
            self._static_counts[track_id] = 0
            self._suppressed.discard(track_id)

        if self._static_counts.get(track_id, 0) >= STATIC_OBJECT_SUPPRESS_FR:
            if track_id not in self._suppressed:
                log.info(f"STATIC_SUPPRESS: {track_id} flagged as static object (poster/mannequin)")
            self._suppressed.add(track_id)

    def is_suppressed(self, track_id: str) -> bool:
        return track_id in self._suppressed


# ─────────────────────────────────────────────────────────────────
# Person Detection (YOLOv8 + Mock Fallback)
# ─────────────────────────────────────────────────────────────────

def detect_persons_yolo(model, frame: np.ndarray, frame_idx: int) -> List[PersonDetection]:
    """Run real YOLOv8/YOLOv8-pose inference with tracking for person detection."""
    try:
        results = model.track(frame, persist=True, conf=PERSON_CONF_THRESHOLD, classes=[0], verbose=False)
    except Exception:
        results = model(frame, conf=PERSON_CONF_THRESHOLD, classes=[0], verbose=False)

    detections = []
    for r in results:
        boxes = r.boxes
        kpts = r.keypoints.data.cpu().numpy() if (hasattr(r, 'keypoints') and r.keypoints is not None) else None
        
        for i, box in enumerate(boxes):
            x1, y1, x2, y2 = [int(val) for val in box.xyxy[0]]
            conf = float(box.conf[0])
            
            # Persistent track ID
            if box.id is not None:
                track_id = f"PID-{int(box.id[0])}"
            else:
                track_id = f"PID-{int((x1+x2)/25)*25}-{int((y1+y2)/25)*25}"
                
            area = (x2 - x1) * (y2 - y1)
            aspect = (x2 - x1) / max((y2 - y1), 1)
            cx, cy = int((x1+x2)/2), int((y1+y2)/2)
            
            kp = kpts[i] if kpts is not None and i < len(kpts) else None
            
            det = PersonDetection(
                track_id=track_id,
                bbox=(x1, y1, x2, y2),
                confidence=conf,
                centroid=(cx, cy),
                area=area,
                aspect_ratio=aspect,
                timestamp=time.time(),
                keypoints=kp
            )
            
            if (BBOX_ASPECT_RATIO_MIN < det.aspect_ratio < BBOX_ASPECT_RATIO_MAX
                    and det.area >= MIN_BBOX_AREA_PX):
                detections.append(det)
                
    return detections

def detect_persons_mock(frame: np.ndarray, frame_idx: int) -> List[PersonDetection]:
    """Simulated detection for testing without a YOLO model."""
    detections = []
    if frame_idx % 30 < 20:
        h, w = frame.shape[:2]
        cx, cy = w // 3 + (frame_idx % 10) * 2, h // 2
        x1, y1 = cx - 40, cy - 80
        x2, y2 = cx + 40, cy + 80
        area = (x2 - x1) * (y2 - y1)
        aspect = (x2 - x1) / max((y2 - y1), 1)
        det = PersonDetection(
            track_id="PID-MOCK-01",
            bbox=(x1, y1, x2, y2),
            confidence=0.75,
            centroid=(cx, cy),
            area=area,
            aspect_ratio=aspect,
            timestamp=time.time()
        )
        is_child = (frame_idx % 45 == 0)
        min_area = 1000 if is_child else MIN_BBOX_AREA_PX
        
        if (det.confidence >= PERSON_CONF_THRESHOLD
                and BBOX_ASPECT_RATIO_MIN < det.aspect_ratio < BBOX_ASPECT_RATIO_MAX
                and det.area >= min_area):
            if is_child:
                log.info(f"CHILD_DETECTED: PID {det.track_id} — lowering threshold (area={det.area})")
            detections.append(det)
    return detections


# ─────────────────────────────────────────────────────────────────
# Cloud Sync: push to Redis → lab_api picks up (or cloud-api)
# ─────────────────────────────────────────────────────────────────

def push_to_cloud(r: redislib.Redis, filepath: str, event_id: str, camera_id: str):
    def _task():
        payload = json.dumps({
            "filepath": filepath,
            "event_id": event_id,
            "camera_id": camera_id,
            "timestamp": time.time()
        })
        try:
            r.rpush("raw_images", payload)
            log.info(f"CLOUD_PUSH: {filepath} → raw_images queue (event={event_id})")
        except Exception as e:
            log.debug(f"CLOUD_PUSH failed (Redis offline): {e}")
        
    io_worker.submit(_task)


# ─────────────────────────────────────────────────────────────────
# Main Orchestrator Loop
# ─────────────────────────────────────────────────────────────────

def main():
    import signal
    def handle_sigterm(signum, frame):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, handle_sigterm)

    # Config from environment (with safe fallbacks)
    redis_url   = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    event_id    = os.environ.get("REC_EVENT_ID", "EVT-UNKNOWN")
    camera_id   = os.environ.get("REC_CAMERA_ID", "CAM-01")
    use_mock    = os.environ.get("USE_MOCK_CAMERA", "0") == "1"
    use_yolo    = os.environ.get("USE_YOLO_MODEL", "1") != "0"
    buffer_dir  = os.environ.get("CAMERA_BUFFER_DIR", "/tmp/capture-buffer")

    os.makedirs(buffer_dir, exist_ok=True)

    # Redis connection
    r = redislib.from_url(redis_url)
    log.info(f"Orchestrator online — Event: {event_id}, Camera: {camera_id}")

    # Load YOLO Model if enabled (Prefer YOLOv8n-pose for keypoints)
    yolo_model = None
    if use_yolo:
        try:
            from ultralytics import YOLO
            log.info("Loading YOLOv8n-pose inference engine...")
            try:
                yolo_model = YOLO('yolov8n-pose.pt')
                log.info("YOLOv8n-pose loaded successfully with skeletal keypoints.")
            except Exception as ep:
                log.warning(f"Could not load yolov8n-pose ({ep}), falling back to yolov8n.pt...")
                yolo_model = YOLO('yolov8n.pt')
                log.info("YOLOv8n loaded successfully.")
        except Exception as e:
            log.error(f"Failed to load YOLO model (fallback to mock): {e}")
            use_yolo = False

    # Camera driver (Dedicated Process)
    driver_class = None
    if camera_id.startswith("MOCK") or use_mock:
        from camera.mock import MockCameraDriver
        driver_class = MockCameraDriver
    elif camera_id.startswith("Webcam") or camera_id in ("0", "1", "2") or camera_id == "CAM-01":
        from camera.webcam import WebcamDriver
        driver_class = WebcamDriver
        if camera_id == "CAM-01":
            camera_id = "Webcam_0"
    elif camera_id.startswith("DSLR"):
        try:
            from camera.dslr import DSLRDriver
            driver_class = DSLRDriver
        except Exception:
            from camera.webcam import WebcamDriver
            driver_class = WebcamDriver
            camera_id = "Webcam_0"
    else:
        from camera.webcam import WebcamDriver
        driver_class = WebcamDriver
        camera_id = "Webcam_0"

    buffer_name = "camera_frame_buffer_0"
    frame_shape = (480, 640, 3)

    ingestion_proc = CameraIngestionProcess(camera_id, driver_class, buffer_name, frame_shape)
    ingestion_proc.start()
    
    # Wait for producer to allocate shared memory
    time.sleep(2.0)
    
    try:
        mem, frame_view = attach_shared_frame(buffer_name, frame_shape)
        log.info("Attached to zero-copy shared memory buffer.")
    except Exception as e:
        log.error(f"FATAL: Failed to attach to shared memory. {e}")
        ingestion_proc.stop()
        return

    # Scene state + suppressor + ring buffer + key moment
    scene = SceneState()
    
    active_profile_name = "DEFAULT"
    try:
        r_prof = r.get("rec_active_profile")
        if r_prof:
            active_profile_name = r_prof.decode('utf-8')
            scene.profile = get_profile(active_profile_name)
            scene.engagement_threshold = scene.profile.engagement_threshold
    except:
        pass
    log.info(f"Loaded Event Profile: {scene.profile.name}")
    
    suppressor = StaticObjectSuppressor()
    smile_detector = SmileDetector(confidence_threshold=0.35)
    ring_buffer = FrameRingBuffer(max_seconds=5.0, fps=15, compress=True)
    temporal_buffer = TemporalFeatureBuffer()
    key_moment_classifier = KeyMomentClassifier()
    frame_idx = 0
    last_processed_idx = -1
    last_eviction = time.monotonic()
    dancing_mode = False

    log.info("Capture loop started.")

    try:
        while True:
            loop_start = time.monotonic()

            # ── 1. Get preview frame (Zero-Copy) ──
            if not ingestion_proc.new_frame_event.wait(timeout=0.5):
                continue
                
            ingestion_proc.new_frame_event.clear()
            
            with ingestion_proc.frame_index.get_lock():
                current_idx = ingestion_proc.frame_index.value
                
            if current_idx == last_processed_idx:
                continue
            last_processed_idx = current_idx
                
            frame = frame_view.copy()  # Snapshot to prevent tearing from concurrent producer writes
            
            # ── 1.5 Push to Ring Buffer ──
            ring_buffer.push(frame)

            frame_idx += 1
            scene.frame_count = frame_idx
        
            # Profile Hot-Swapping Check (every ~2 seconds)
            if frame_idx % 30 == 0:
                try:
                    r_prof = r.get("rec_active_profile")
                    if r_prof:
                        new_prof = r_prof.decode('utf-8')
                        if new_prof != active_profile_name:
                            active_profile_name = new_prof
                            scene.profile = get_profile(active_profile_name)
                            scene.engagement_threshold = scene.profile.engagement_threshold
                            log.info(f"HOT-SWAP: Event Profile changed to {scene.profile.name}")
                except Exception as e:
                    pass

            # ── 0. Storage Halt Check (PRD F3) ──
            if os.path.exists(buffer_dir):
                try:
                    st = os.statvfs(buffer_dir)
                    free_mb = (st.f_bavail * st.f_frsize) / (1024 * 1024)
                    if free_mb < STORAGE_CRITICAL_MB:
                        log.error(f"STORAGE_CRITICAL: Only {free_mb:.1f}MB left on SSD. Halting captures!")
                        time.sleep(5)
                        continue
                except Exception as e:
                    log.error(f"Failed to check storage: {e}")

            # ── 2. Light change check (PRD C3) ──
            if scene.check_light_change(frame):
                time.sleep(LIGHT_CHANGE_FREEZE_MS / 1000.0)
                continue
            if time.monotonic() < scene.light_change_freeze_until:
                continue

            # ── 3. Detect persons ──
            if use_yolo and yolo_model:
                detections = detect_persons_yolo(yolo_model, frame, frame_idx)
            else:
                detections = detect_persons_mock(frame, frame_idx)

            # ── 4. Scene mode detection (dancing = high avg velocity) ──
            avg_velocity = 0.0
            if detections and scene.pids:
                vels = [scene.compute_velocity(d.track_id) for d in detections if d.track_id in scene.pids]
                avg_velocity = float(np.mean(vels)) if vels else 0.0
            dancing_mode = avg_velocity > 25
            motion_thresh = DANCE_MOTION_VEL_THRESHOLD if dancing_mode else scene.profile.motion_velocity_threshold
            engagement_thresh = scene.engagement_threshold


            # ── 5. Register detections + update scene & rolling candidates ──
            visible_pids = []
            key_moment_triggered = False
            best_key_moment_pid = None
            now = time.monotonic()

            # Dynamic Aspect Ratio & Framing Scale retrieval
            def _get_active_ar():
                try:
                    if os.path.exists("/tmp/rec_aspect_ratio.txt"):
                        with open("/tmp/rec_aspect_ratio.txt", "r") as f:
                            val = _clean_config_string(f.read())
                            if val: return val
                except Exception:
                    pass
                try:
                    val = _clean_config_string(r.get("rec_active_aspect_ratio"))
                    if val: return val
                except Exception:
                    pass
                return _clean_config_string(os.environ.get("REC_ASPECT_RATIO", DEFAULT_ASPECT_RATIO)) or DEFAULT_ASPECT_RATIO

            def _get_active_framing_scale():
                try:
                    if os.path.exists("/tmp/rec_framing_scale.txt"):
                        with open("/tmp/rec_framing_scale.txt", "r") as f:
                            val = _clean_config_string(f.read())
                            if val: return val
                except Exception:
                    pass
                try:
                    val = _clean_config_string(r.get("rec_active_framing_scale"))
                    if val: return val
                except Exception:
                    pass
            # Dynamic Smile-to-Capture setting polling
            def _get_smile_capture_enabled() -> bool:
                try:
                    if os.path.exists("/tmp/rec_smile_capture.txt"):
                        with open("/tmp/rec_smile_capture.txt", "r") as f:
                            return f.read().strip().lower() in ("1", "true", "yes", "on")
                    if r:
                        val = r.get("rec_smile_capture_enabled")
                        if val is not None:
                            return str(val).strip().lower() in ("1", "true", "yes", "on")
                except Exception:
                    pass
                return True

            active_ar = _get_active_ar()
            active_scale = _get_active_framing_scale()
            smile_capture_enabled = _get_smile_capture_enabled()

            pid_to_framing_box: Dict[str, List[int]] = {}
            for det in detections:
                has_kpts = det.keypoints is not None and len(det.keypoints) > 0
                # Static object suppression (PRD D2, D4)
                suppressor.update(det.track_id, scene.compute_velocity(det.track_id) if det.track_id in scene.pids else 1.0, has_keypoints=has_kpts)
                is_suppressed = suppressor.is_suppressed(det.track_id)
                if is_suppressed and not has_kpts:
                    continue

                pid = scene.register_detection(det)
                visible_pids.append(pid)

                # 1. Compute dynamic resizable aspect-ratio framing box with keypoints
                fb = compute_framing_box(
                    list(det.bbox), frame.shape[1], frame.shape[0],
                    aspect_ratio=active_ar, framing_scale=active_scale,
                    velocity=scene.compute_velocity(pid),
                    keypoints=det.keypoints
                )
                pid_to_framing_box[pid] = fb

                # 2. Compute multi-signal composite quality & Smile Detection
                comp_score, eng_score, sharp_score = scene.compute_composite_quality(frame, det, fb)
                
                # Real-time Smile-to-Capture Evaluation
                is_smiling, smile_score, smile_metrics = smile_detector.evaluate(frame, det.bbox, det.keypoints)
                if smile_capture_enabled and is_smiling:
                    # Boost composite score to prioritize genuine smiles
                    comp_score = max(comp_score, 0.70 + 0.25 * smile_score)

                with scene._lock:
                    state = scene.pids[pid]
                    state.composite_score = comp_score
                    state.engagement_score = eng_score
                    state.sharpness_score = sharp_score
                    state.is_smiling = is_smiling
                    state.smile_score = smile_score

                    # 3. Rolling Best Candidate Tracker ("Best-of-Worst" Buffer)
                    # Continuously cache the highest-scoring candidate observed across the tracking window
                    if state.best_candidate is None or comp_score > state.best_candidate.score:
                        state.best_candidate = FrameCandidate(
                            frame=frame.copy(),
                            score=comp_score,
                            engagement=eng_score,
                            sharpness=sharp_score,
                            framing_box=fb,
                            aspect_ratio=active_ar,
                            framing_scale=active_scale,
                            timestamp=now,
                            bbox=det.bbox
                        )

                # Key Moment Temporal Tracker
                if det.keypoints is not None:
                    temporal_buffer.update(pid, det.keypoints, det.bbox)
                
                # Run inference every 3rd frame (5 FPS)
                if frame_idx % 3 == 0 and det.keypoints is not None:
                    features = temporal_buffer.get_features(pid)
                    if features is not None and key_moment_classifier.predict(features):
                        key_moment_triggered = True
                        best_key_moment_pid = pid

                threshold = state.engagement_override if state.engagement_override else engagement_thresh
                if comp_score >= threshold or (pid == best_key_moment_pid and key_moment_triggered) or (smile_capture_enabled and is_smiling):
                    state.engagement_sustained_frames += 1
                else:
                    state.engagement_sustained_frames = max(0, state.engagement_sustained_frames - 1)
                
            if key_moment_triggered and best_key_moment_pid:
                log.info(f"KEY_MOMENT DETECTED for PID {best_key_moment_pid}! Forcing immediate backtrack capture.")
                km_det = next((d for d in detections if d.track_id == best_key_moment_pid), None)
                _do_capture(None, frame, best_key_moment_pid, scene, r, event_id, camera_id, buffer_dir, is_burst=True, ring_buffer=ring_buffer, framing_box=pid_to_framing_box.get(best_key_moment_pid), aspect_ratio=active_ar, person_bbox=list(km_det.bbox) if km_det else None)
                scene.pids[best_key_moment_pid].last_capture_time = time.monotonic()
                time.sleep(0.05)
                continue

            # ── 6. Fail-safes (PRD 7.7.2) ──
            scene.watchdog_check()
            scene.starvation_check()

            # Equity mode toggle with hysteresis (PRD 7.7.4)
            gini = scene.compute_gini()
            if gini > GINI_EQUITY_ENTER:
                scene.equity_mode = True
            elif gini < GINI_EQUITY_EXIT:
                scene.equity_mode = False

            # ── 7. Global minimum interval check ──
            if (time.monotonic() - scene.last_global_capture_time) < GLOBAL_MIN_INTERVAL_SEC:
                time.sleep(0.05)
                continue

            # ── 8. Heartbeat force-capture (PRD 7.7.2 Fail-Safe 3) ──
            idle_time = time.monotonic() - scene.last_global_capture_time
            if idle_time > HEARTBEAT_FORCE_SEC and visible_pids and scene.last_global_capture_time > 0:
                best = max(visible_pids, key=lambda p: scene.compute_priority(p))
                log.warning(f"HEARTBEAT: Force-capturing PID {best} (idle={idle_time:.0f}s)")
                hb_det = next((d for d in detections if d.track_id == best), None)
                _do_capture(None, frame, best, scene, r, event_id, camera_id, buffer_dir, force=True, framing_box=pid_to_framing_box.get(best), aspect_ratio=active_ar, person_bbox=list(hb_det.bbox) if hb_det else None)
                continue

            # ── 9. Quality Gating & Progressive Patience Decision ──
            live_candidates = []
            fallback_capture_pid = None
            fallback_candidate = None

            for pid in visible_pids:
                with scene._lock:
                    state = scene.pids[pid]

                    # Hard caps (PRD 7.7.4) & Burst Limit
                    if state.capture_count >= MAX_TOTAL_CAPTURES_PER_PID:
                        continue
                    if state.session_capture_count >= MAX_PHOTOS_PER_BURST_COOLDOWN:
                        continue

                    # Equity mode: skip over-represented PIDs
                    if scene.equity_mode:
                        avg = sum(s.capture_count for s in scene.pids.values()) / max(len(scene.pids), 1)
                        if state.capture_count > avg:
                            continue

                    # Cooldown gate
                    if scene.in_cooldown(pid):
                        continue

                    patience_elapsed = now - state.patience_start_time

                    # Progressive Threshold Relaxation:
                    # 0.0s to 2.5s: strict high-quality requirement (TARGET_QUALITY_THRESHOLD = 0.60)
                    # 2.5s to 7.5s: progressive linear decay down to MIN_FALLBACK_QUALITY (0.28)
                    # >7.5s: full patience fallback to best observed candidate
                    if patience_elapsed < PATIENCE_START_SEC:
                        effective_thresh = TARGET_QUALITY_THRESHOLD
                    elif patience_elapsed < PATIENCE_MAX_SEC:
                        frac = (patience_elapsed - PATIENCE_START_SEC) / (PATIENCE_MAX_SEC - PATIENCE_START_SEC)
                        effective_thresh = TARGET_QUALITY_THRESHOLD - frac * (TARGET_QUALITY_THRESHOLD - MIN_FALLBACK_QUALITY)
                    else:
                        effective_thresh = MIN_FALLBACK_QUALITY

                    if state.engagement_override is not None:
                        effective_thresh = min(effective_thresh, state.engagement_override)

                    sustain_needed = HANDSHAKE_SUSTAIN_FRAMES if _is_ceremony(state) else (
                        1 if dancing_mode else scene.profile.min_sustain_frames
                    )

                    # Condition 1: Live Quality Match (Meets current progressive threshold)
                    is_instant_smile = (smile_capture_enabled and state.is_smiling and state.session_capture_count == 0)
                    if (state.composite_score >= effective_thresh and state.engagement_sustained_frames >= sustain_needed) or is_instant_smile:
                        priority = scene.compute_priority(pid)
                        live_candidates.append((pid, priority))

                    # Condition 2: Patience Timeout Reached ("Capture the better frame from all the worst")
                    elif patience_elapsed >= PATIENCE_MAX_SEC and state.best_candidate is not None and state.best_candidate.score >= 0.15:
                        if fallback_capture_pid is None:
                            fallback_capture_pid = pid
                            fallback_candidate = state.best_candidate

                    # Condition 3: Subject rapidly moving away after being seen >= 1.5s with 0 captures
                    elif state.visible_duration >= 1.5 and state.capture_count == 0 and scene.compute_velocity(pid) > 28.0 and state.best_candidate is not None:
                        if fallback_capture_pid is None:
                            log.info(f"EXITING_SUBJECT: Subject {pid} leaving scene. Capturing best stored candidate.")
                            fallback_capture_pid = pid
                            fallback_candidate = state.best_candidate

            # ── 9.2 Execute Capture with Pose-Change Gate & Composition Validation ──
            if live_candidates:
                live_candidates.sort(key=lambda x: x[1], reverse=True)
                
                captured_this_frame = False
                for best_pid, best_priority in live_candidates:
                    with scene._lock:
                        bstate = scene.pids[best_pid]
                        
                        # ── Pose-Change Gate (PRD 7.7.3 Anti-Duplicate) ──
                        # Block capture if the subject hasn't changed pose since last capture
                        if bstate.last_captured_bbox is not None and bstate.session_capture_count > 0:
                            # Check per-session minimum interval
                            time_since_last = now - bstate.last_capture_time
                            if time_since_last < BURST_MIN_INTERVAL_SEC:
                                log.debug(f"BURST_GATE: PID {best_pid} blocked — only {time_since_last:.1f}s since last (min {BURST_MIN_INTERVAL_SEC}s)")
                                continue
                            
                            # Check pose similarity via IoU
                            current_bbox = list(bstate.centroid_history[-1]) if bstate.centroid_history else None
                            det_for_pid = next((d for d in detections if d.track_id == best_pid), None)
                            if det_for_pid:
                                iou = compute_bbox_iou(list(det_for_pid.bbox), bstate.last_captured_bbox)
                                if iou > POSE_CHANGE_IOU_THRESHOLD:
                                    # Check centroid displacement as secondary signal
                                    if bstate.last_captured_centroid is not None and bstate.centroid_history:
                                        cx, cy = bstate.centroid_history[-1]
                                        lcx, lcy = bstate.last_captured_centroid
                                        disp = np.sqrt((cx - lcx)**2 + (cy - lcy)**2)
                                        if disp < POSE_CHANGE_CENTROID_PX:
                                            log.info(f"POSE_GATE: PID {best_pid} blocked — pose unchanged (IoU={iou:.2f}, disp={disp:.0f}px)")
                                            continue
                        
                        # ── Composition Quality Gate ──
                        best_framing_box = pid_to_framing_box.get(best_pid)
                        if best_framing_box:
                            det_for_pid = next((d for d in detections if d.track_id == best_pid), None)
                            if det_for_pid:
                                comp_qual = compute_composition_score(list(det_for_pid.bbox), best_framing_box)
                                bstate.composition_score = comp_qual
                                if comp_qual < MIN_COMPOSITION_SCORE and bstate.session_capture_count == 0:
                                    # For first photo, be lenient. For subsequent, enforce composition.
                                    pass  # Allow first photo even with lower composition
                                elif comp_qual < MIN_COMPOSITION_SCORE:
                                    log.info(f"COMP_GATE: PID {best_pid} blocked — poor composition ({comp_qual:.2f} < {MIN_COMPOSITION_SCORE})")
                                    continue
                    
                    # ── Interaction check ──
                    interacting = False
                    for pid in visible_pids:
                        if pid != best_pid and _is_interaction(scene.pids[best_pid], scene.pids[pid]):
                            interacting = True
                            break
                        
                    if interacting:
                        log.info(f"INTERACTION_MODE: PID {best_pid} is conversing. CANDID_BEHIND rules apply.")
                    
                    # ── Burst decision: only burst if there's actual pose change (dancing) ──
                    is_burst = dancing_mode and scene.compute_velocity(best_pid) > DANCE_MOTION_VEL_THRESHOLD
                    best_framing_box = pid_to_framing_box.get(best_pid)
                
                    log.info(f"CAPTURE (Live): PID={best_pid} priority={best_priority:.2f} score={scene.pids[best_pid].composite_score:.2f} comp={scene.pids[best_pid].composition_score:.2f} AR={active_ar} burst={is_burst}")
                    _do_capture(None, frame, best_pid, scene, r, event_id, camera_id, buffer_dir, is_burst=is_burst, ring_buffer=ring_buffer, framing_box=best_framing_box, aspect_ratio=active_ar, person_bbox=list(det_for_pid.bbox) if det_for_pid else None)
                    captured_this_frame = True
                    break  # Only capture one person per frame cycle

            elif fallback_capture_pid and fallback_candidate:
                # ── Reframe the best candidate using its stored bbox for optimal composition ──
                reframed_box = compute_framing_box(
                    list(fallback_candidate.bbox), frame.shape[1], frame.shape[0],
                    aspect_ratio=fallback_candidate.aspect_ratio,
                    framing_scale=fallback_candidate.framing_scale
                )
                log.info(f"CAPTURE (Best-of-Worst Fallback): PID={fallback_capture_pid} (Best Score: {fallback_candidate.score:.2f}) AR={fallback_candidate.aspect_ratio}")
                _do_capture(None, frame, fallback_capture_pid, scene, r, event_id, camera_id, buffer_dir, is_burst=False, candidate=fallback_candidate, framing_box=reframed_box, aspect_ratio=fallback_candidate.aspect_ratio, person_bbox=list(fallback_candidate.bbox) if fallback_candidate.bbox else None)

            # ── 9.5 Dump State for UI Dashboard ──
            try:
                state_data = {
                    "global_idle": time.monotonic() - scene.last_global_capture_time,
                    "gini": gini,
                    "dancing": dancing_mode,
                    "aspect_ratio": active_ar,
                    "framing_scale": active_scale,
                    "pids": []
                }
                for det in detections:
                    pid = det.track_id
                    if pid in scene.pids:
                        with scene._lock:
                            s = scene.pids[pid]
                            cooldown = scene.dynamic_cooldown(pid)
                            time_since = time.monotonic() - s.last_capture_time
                            is_burst_cd = time.monotonic() < s.cooldown_until
                            is_cooldown = is_burst_cd or (time_since < cooldown)
                            
                            p_elapsed = now - s.patience_start_time
                            best_s = s.best_candidate.score if s.best_candidate else 0.0

                            # Dynamic effective threshold
                            if p_elapsed < PATIENCE_START_SEC:
                                eff_thresh = TARGET_QUALITY_THRESHOLD
                            elif p_elapsed < PATIENCE_MAX_SEC:
                                frac = (p_elapsed - PATIENCE_START_SEC) / (PATIENCE_MAX_SEC - PATIENCE_START_SEC)
                                eff_thresh = TARGET_QUALITY_THRESHOLD - frac * (TARGET_QUALITY_THRESHOLD - MIN_FALLBACK_QUALITY)
                            else:
                                eff_thresh = MIN_FALLBACK_QUALITY

                            sustain_needed = HANDSHAKE_SUSTAIN_FRAMES if _is_ceremony(s) else (1 if dancing_mode else scene.profile.min_sustain_frames)
                        
                            if is_burst_cd:
                                rem = max(0.0, s.cooldown_until - time.monotonic())
                                status = "COOLDOWN"
                                reason = f"Burst Cooldown ({rem:.0f}s left)"
                                color = (0, 0, 255) # Red
                            elif is_cooldown:
                                status = "COOLDOWN"
                                reason = f"Cooldown ({max(0, cooldown - time_since):.1f}s) [{s.session_capture_count}/3]"
                                color = (0, 0, 255) # Red
                            elif smile_capture_enabled and s.is_smiling:
                                status = "READY"
                                reason = f"Smile Detected 😄 ({s.smile_score:.2f}) [{s.session_capture_count}/3]"
                                color = (0, 255, 0) # Bright Green
                            elif s.composite_score < eff_thresh:
                                rem_patience = max(0.0, PATIENCE_MAX_SEC - p_elapsed)
                                status = "ANALYZING"
                                reason = f"Seeking Best ({s.composite_score:.2f}/{eff_thresh:.2f}) [Best: {best_s:.2f}]"
                                color = (0, 165, 255) # Orange
                            elif s.engagement_sustained_frames < sustain_needed:
                                status = "ANALYZING"
                                reason = f"Holding Focus ({s.engagement_sustained_frames}/{sustain_needed}) [{s.session_capture_count}/3]"
                                color = (255, 255, 0) # Cyan
                            else:
                                status = "READY"
                                reason = f"Optimal Frame ({s.composite_score:.2f}) [{s.session_capture_count}/3]"
                                color = (0, 255, 0) # Green
                            
                            f_box = pid_to_framing_box.get(pid, [int(v) for v in det.bbox])
                            state_data["pids"].append({
                                "id": pid,
                                "bbox": f_box, # Aspect-ratio framing crop box
                                "person_bbox": [int(v) for v in det.bbox], # Raw detection
                                "status": status,
                                "reason": reason,
                                "color": color,
                                "is_smiling": s.is_smiling,
                                "smile_score": round(s.smile_score, 2),
                                "priority": round(float(scene.compute_priority(pid)), 2),
                                "composite_score": round(s.composite_score, 2),
                                "composition_score": round(s.composition_score, 2),
                                "best_score": round(best_s, 2),
                                "patience_sec": round(p_elapsed, 1),
                                "photo_count": s.session_capture_count,
                                "max_photos": MAX_PHOTOS_PER_BURST_COOLDOWN,
                                "aspect_ratio": active_ar,
                                "framing_scale": active_scale
                            })
                
                state_data["frame_width"] = frame.shape[1]
                state_data["frame_height"] = frame.shape[0]
                state_data["smile_capture_enabled"] = smile_capture_enabled

                # Offload disk IO with atomic writes to provide pure raw video stream + live AI state
                def _write_state(data, img):
                    try:
                        with open("/tmp/rec_state.json.tmp", "w") as f:
                            json.dump(data, f)
                        os.replace("/tmp/rec_state.json.tmp", "/tmp/rec_state.json")
                        
                        # Fast JPEG encode of pure raw camera frame (quality 75)
                        cv2.imwrite("/tmp/rec_frame.tmp.jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 75])
                        os.replace("/tmp/rec_frame.tmp.jpg", "/tmp/rec_frame.jpg")
                        cv2.imwrite("/tmp/rec_raw_frame.tmp.jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])
                        os.replace("/tmp/rec_raw_frame.tmp.jpg", "/tmp/rec_raw_frame.jpg")
                    except Exception:
                        pass
                
                # Submit copy of raw frame to prevent tearing
                io_worker.submit(lambda: _write_state(state_data, frame.copy()))
            
            except Exception as e:
                pass

            # ── 10. Periodic maintenance ──
            if time.monotonic() - last_eviction > 60.0:
                scene.evict_stale_pids()
                last_eviction = time.monotonic()

            # Mass cooldown reset (PRD F4)
            if COOLDOWN_MASS_RESET_ENABLED and visible_pids:
                all_blocked = all(scene.in_cooldown(p) for p in visible_pids)
                if all_blocked:
                    log.warning("COOLDOWN_MASS_RESET: All PIDs blocked — resetting to minimum")
                    with scene._lock:
                        for p in visible_pids:
                            scene.pids[p].last_capture_time = 0.0

            # Target 30 FPS loop for ultra-smooth live stream
            elapsed = time.monotonic() - loop_start
            sleep_time = max(0, (1.0 / 30.0) - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        log.info("Orchestrator terminated by user.")
    except Exception as e:
        log.error(f"Orchestrator crashed: {e}")
    finally:
        ingestion_proc.stop()


# ─────────────────────────────────────────────────────────────────
# Capture Execution
# ─────────────────────────────────────────────────────────────────

def _do_capture(driver, frame, pid: str, scene: SceneState, r, event_id: str,
                camera_id: str, buffer_dir: str, force: bool = False, is_burst: bool = False,
                ring_buffer: FrameRingBuffer = None, candidate: Optional[FrameCandidate] = None,
                framing_box: Optional[List[int]] = None, aspect_ratio: str = "16:9",
                person_bbox: Optional[List[int]] = None):
    """
    Execute a shutter trigger. Supports saving candidate frames from progressive patience
    or retroactively backtracking sharpest frames from the ring buffer.
    """
    now = time.monotonic()
    
    with scene._lock:
        state = scene.pids[pid]
        # Update scene state and 3-photo burst cooldown tracking
        state.capture_count += 1
        state.session_capture_count += 1
        if state.session_capture_count >= MAX_PHOTOS_PER_BURST_COOLDOWN:
            state.cooldown_until = now + PERSON_BURST_COOLDOWN_SEC
            log.info(f"BURST_LIMIT: PID {pid} reached {MAX_PHOTOS_PER_BURST_COOLDOWN} photos limit. Imposing {PERSON_BURST_COOLDOWN_SEC}s cooldown.")

        state.last_capture_time = now
        state.patience_start_time = now
        state.best_candidate = None
        state.engagement_sustained_frames = 0
        state.cooldown_override = None     # Clear starvation override after first capture
        state.engagement_override = None
        # Record pose state at capture moment for future similarity checks
        if state.centroid_history:
            state.last_captured_centroid = state.centroid_history[-1]
        if person_bbox:
            state.last_captured_bbox = list(person_bbox)
        elif framing_box:
            state.last_captured_bbox = list(framing_box)
        scene.last_global_capture_time = now
        # Reset watchdog threshold back to normal if it was lowered
        scene.engagement_threshold = ENGAGEMENT_THRESHOLD

    # Publish capture command to Redis PubSub (Camera Controller will pick this up)
    def _publish_cmd():
        try:
            command_type = "BURST" if is_burst else "CAPTURE"
            r.publish('camera_commands', json.dumps({
                "command": command_type,
                "pid": pid,
                "event_id": event_id,
                "camera_id": camera_id,
                "framing_box": framing_box,
                "aspect_ratio": aspect_ratio
            }))
            log.info(f"PUB/SUB: Sent {command_type} command for PID {pid}")
        except Exception as e:
            log.debug(f"CAPTURE_PUB_ERROR (Redis offline): {e}")
            
    io_worker.submit(_publish_cmd)

    # ── Save Processed Frame: Candidate Snapshot or Backtrack Frame ──
    # Recompute professional framing box from the best source frame's bbox
    def _save_and_persist():
        try:
            target_frame = None
            target_crop_box = framing_box
            source_bbox = None
            score_desc = "live"

            if candidate is not None and candidate.frame is not None:
                target_frame = candidate.frame
                source_bbox = candidate.bbox
                score_desc = f"BestCandidate (Score: {candidate.score:.2f})"
                # Recompute professional framing from the candidate's actual bbox
                if source_bbox is not None:
                    h, w = target_frame.shape[:2]
                    target_crop_box = compute_framing_box(
                        list(source_bbox), w, h,
                        aspect_ratio=candidate.aspect_ratio if candidate.aspect_ratio else aspect_ratio,
                        framing_scale=candidate.framing_scale if candidate.framing_scale else "AUTO"
                    )
                elif candidate.framing_box:
                    target_crop_box = candidate.framing_box
            elif ring_buffer:
                lookback = 2.0 if is_burst else 1.0
                cands = ring_buffer.backtrack(lookback_seconds=lookback)
                if cands:
                    best_f, score, idx = get_best_backtrack_frame(cands)
                    if best_f is not None:
                        target_frame = best_f
                        score_desc = f"Backtrack (Sharpness: {score:.1f})"
                        # Use the provided framing box for backtracked frame
                        target_crop_box = framing_box
            
            if target_frame is None:
                target_frame = frame

            if target_frame is not None:
                os.makedirs(buffer_dir, exist_ok=True)
                timestamp = time.time()
                filepath = os.path.join(buffer_dir, f"capture_{pid}_{int(timestamp)}.jpg")
                
                # Crop strictly to professionally-composed framing box
                h, w = target_frame.shape[:2]
                final_crop_box = target_crop_box if target_crop_box else compute_framing_box([0, 0, w, h], w, h, aspect_ratio)
                
                # Final composition validation before save
                cropped_frame = crop_frame_to_box(target_frame, final_crop_box)
                
                # Ensure minimum output quality (not a sliver or garbage crop)
                ch, cw = cropped_frame.shape[:2]
                if cw >= 50 and ch >= 50:
                    cv2.imwrite(filepath, cropped_frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
                    log.info(f"CAPTURED: Saved {aspect_ratio} ({cw}x{ch}) [{score_desc}] to {filepath}")
                    push_to_cloud(r, filepath, event_id, camera_id)
                else:
                    log.warning(f"REJECTED: Crop too small ({cw}x{ch}), discarding.")
        except Exception as e:
            log.error(f"Failed to persist captured photo: {e}")

    io_worker.submit(_save_and_persist)

    log.info(f"CAPTURE_EXECUTED (PID={pid}, count={state.session_capture_count}/{MAX_PHOTOS_PER_BURST_COOLDOWN}, total={state.capture_count}, AR={aspect_ratio})")
    
    # Note: push_to_cloud is now handled by the camera-controller after successful capture


def _is_ceremony(state: PIDState) -> bool:
    """Heuristic: detect handshake/ceremony mode (PRD E2)."""
    # In production: arm-position detection via pose estimation
    # Here: if capture happened < 3s ago on another PID = ceremony context
    return False  # Placeholder; refined in PIS integration


def _is_interaction(p1: PIDState, p2: PIDState) -> bool:
    """PRD E1: Interaction mode (two people talking)."""
    if not p1.centroid_history or not p2.centroid_history:
        return False
    # Check if centroids are close horizontally (approx 1.5x body width)
    dx = abs(p1.centroid_history[-1][0] - p2.centroid_history[-1][0])
    dy = abs(p1.centroid_history[-1][1] - p2.centroid_history[-1][1])
    return dx < 150 and dy < 50


if __name__ == "__main__":
    main()
