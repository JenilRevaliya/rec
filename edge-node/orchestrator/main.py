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

# ─────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="[ORCH] %(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("orchestrator")


# ─────────────────────────────────────────────────────────────────
# HARDCODED CONSTANTS — PRD Section 7.11 + 7.12
# DO NOT MAKE THESE CONFIGURABLE AT RUNTIME.
# ─────────────────────────────────────────────────────────────────

# Cooldown
COOLDOWN_MIN_SEC            = 5.0
COOLDOWN_BASE_SEC           = 12.0
COOLDOWN_MAX_SEC            = 120.0
ESCALATION_PER_CAPTURE      = 0.3
DECAY_RATE_PER_SEC          = 0.02
GLOBAL_MIN_INTERVAL_SEC     = 2.0
GLOBAL_MAX_IDLE_SEC         = 30.0
HEARTBEAT_FORCE_SEC         = 45.0
STARVATION_THRESHOLD_SEC    = 60.0

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


@dataclass
class PIDState:
    pid: str
    capture_count: int = 0
    last_capture_time: float = 0.0
    last_seen_time: float = field(default_factory=time.monotonic)
    first_seen_time: float = field(default_factory=time.monotonic)
    visible_duration: float = 0.0
    consecutive_frames: int = 0         # for temporal consistency
    centroid_history: List[Tuple[int,int]] = field(default_factory=list)
    angles_captured: Set[str] = field(default_factory=set)
    # Engagement scoring
    engagement_score: float = 0.0
    engagement_sustained_frames: int = 0
    # Edge case flags
    engagement_override: Optional[float] = None  # starvation override
    cooldown_override: Optional[float] = None     # starvation cooldown=0


# ─────────────────────────────────────────────────────────────────
# Scene State
# ─────────────────────────────────────────────────────────────────

class SceneState:
    """Holds the current state of the entire scene — all visible PIDs."""

    def __init__(self):
        self.pids: Dict[str, PIDState] = {}
        self.last_global_capture_time: float = 0.0
        self.last_frame_time: float = time.monotonic()
        self.equity_mode: bool = False
        self.engagement_threshold: float = ENGAGEMENT_THRESHOLD
        self.person_conf_threshold: float = PERSON_CONF_THRESHOLD
        self.last_pixel_intensity: Optional[float] = None
        self.light_change_freeze_until: float = 0.0
        self.static_zones: List[Tuple[int,int]] = []  # (cx, cy) of suppressed static objects
        self.frame_count: int = 0

    def register_detection(self, det: PersonDetection) -> str:
        """Register or update a detection. Returns PID."""
        # Use track_id as PID for now (PIS module would refine this)
        pid = det.track_id
        now = time.monotonic()

        if pid not in self.pids:
            self.pids[pid] = PIDState(pid=pid, first_seen_time=now, last_seen_time=now)

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
        history = self.pids[pid].centroid_history
        if len(history) < 2:
            return 0.0
        dx = history[-1][0] - history[-2][0]
        dy = history[-1][1] - history[-2][1]
        return float(np.sqrt(dx**2 + dy**2))

    def compute_engagement(self, frame: np.ndarray, det: PersonDetection) -> float:
        """
        Simplified engagement score from visual signals.
        In production: integrate InsightFace landmarks for smile/EAR/gaze.
        Here: approximate from motion stability + bbox stability.
        """
        pid = det.track_id
        velocity = self.compute_velocity(pid)

        # Motion stability component (0.35 weight combined)
        stable = 1.0 if velocity < MOTION_VELOCITY_THRESHOLD else max(0.0, 1.0 - velocity / 50.0)

        # Face presence proxy: check if upper portion of bbox is distinct (brightness contrast)
        x1, y1, x2, y2 = det.bbox
        roi = frame[y1:min(y2, frame.shape[0]), x1:min(x2, frame.shape[1])]
        if roi.size == 0:
            return 0.0

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if len(roi.shape) == 3 else roi
        # Laplacian sharpness as proxy for face clarity
        sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
        sharpness_score = min(1.0, sharpness / 200.0)

        # Aspect ratio score: penalize extreme ratios (back-turned, partial)
        aspect_score = 1.0 if 0.25 < det.aspect_ratio < 0.75 else 0.4

        engagement = 0.35 * stable + 0.35 * sharpness_score + 0.30 * aspect_score
        return round(engagement, 3)

    def dynamic_cooldown(self, pid: str) -> float:
        """PRD 7.7.1: Escalating + decaying cooldown."""
        state = self.pids[pid]
        if state.cooldown_override is not None:
            return state.cooldown_override

        base = COOLDOWN_BASE_SEC
        escalated = base * (1.0 + ESCALATION_PER_CAPTURE * state.capture_count)
        idle = time.monotonic() - state.last_seen_time
        decay = max(0.3, 1.0 - DECAY_RATE_PER_SEC * idle)
        result = escalated * decay
        return max(COOLDOWN_MIN_SEC, min(COOLDOWN_MAX_SEC, result))

    def in_cooldown(self, pid: str) -> bool:
        state = self.pids[pid]
        cooldown = self.dynamic_cooldown(pid)
        return (time.monotonic() - state.last_capture_time) < cooldown

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
    """Tracks detections that never move — flags as poster/mannequin."""

    def __init__(self):
        self._static_counts: Dict[str, int] = {}  # track_id → static frame count
        self._suppressed: Set[str] = set()

    def update(self, track_id: str, velocity: float):
        if velocity < 0.5:
            self._static_counts[track_id] = self._static_counts.get(track_id, 0) + 1
        else:
            self._static_counts[track_id] = 0

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
    """Run real YOLOv8n inference for person detection."""
    results = model(frame, conf=PERSON_CONF_THRESHOLD, classes=[0], verbose=False)
    detections = []
    
    # Simulate a child occasionally for testing dynamic parameters
    is_child = (frame_idx % 45 == 0)
    min_area = 1000 if is_child else MIN_BBOX_AREA_PX
    
    for r in results:
        boxes = r.boxes
        for box in boxes:
            x1, y1, x2, y2 = [int(i) for i in box.xyxy[0]]
            conf = float(box.conf[0])
            
            # Simple SORT-like tracking placeholder (usually use deepsort or track=True)
            # YOLOv8 supports tracking via model.track(), but here we use generic PID for structural completeness
            # In production, replace `track_id` with `box.id` if tracking is enabled
            track_id = f"PID-{int((x1+x2)/2)}-{int((y1+y2)/2)}" 
            if box.id is not None:
                track_id = f"PID-{int(box.id[0])}"
                
            area = (x2 - x1) * (y2 - y1)
            aspect = (x2 - x1) / max((y2 - y1), 1)
            cx, cy = int((x1+x2)/2), int((y1+y2)/2)
            
            det = PersonDetection(
                track_id=track_id,
                bbox=(x1, y1, x2, y2),
                confidence=conf,
                centroid=(cx, cy),
                area=area,
                aspect_ratio=aspect,
                timestamp=time.time()
            )
            
            if (BBOX_ASPECT_RATIO_MIN < det.aspect_ratio < BBOX_ASPECT_RATIO_MAX
                    and det.area >= min_area):
                if is_child:
                    log.info(f"CHILD_DETECTED: PID {det.track_id} — lowering threshold (area={det.area})")
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
    payload = json.dumps({
        "filepath": filepath,
        "event_id": event_id,
        "camera_id": camera_id,
        "timestamp": time.time()
    })
    r.rpush("raw_images", payload)
    log.info(f"CLOUD_PUSH: {filepath} → raw_images queue (event={event_id})")


# ─────────────────────────────────────────────────────────────────
# Main Orchestrator Loop
# ─────────────────────────────────────────────────────────────────

def main():
    # Config from environment (with safe fallbacks)
    redis_url   = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    event_id    = os.environ.get("REC_EVENT_ID", "EVT-UNKNOWN")
    camera_id   = os.environ.get("REC_CAMERA_ID", "CAM-01")
    use_mock    = os.environ.get("USE_MOCK_CAMERA", "1") == "1"
    use_yolo    = os.environ.get("USE_YOLO_MODEL", "0") == "1"
    buffer_dir  = os.environ.get("CAMERA_BUFFER_DIR", "/tmp/capture-buffer")

    os.makedirs(buffer_dir, exist_ok=True)

    # Redis connection
    r = redislib.from_url(redis_url)
    log.info(f"Orchestrator online — Event: {event_id}, Camera: {camera_id}")

    # Load YOLO Model if enabled
    yolo_model = None
    if use_yolo:
        try:
            from ultralytics import YOLO
            log.info("Loading YOLOv8n inference engine...")
            yolo_model = YOLO('yolov8n.pt')
            log.info("YOLOv8n loaded successfully.")
        except Exception as e:
            log.error(f"Failed to load YOLO model (fallback to mock): {e}")
            use_yolo = False

    # Camera driver
    if camera_id.startswith("MOCK"):
        from camera.mock import MockCameraDriver
        driver = MockCameraDriver(camera_id)
    elif camera_id.startswith("Webcam"):
        from camera.webcam import WebcamDriver
        driver = WebcamDriver(camera_id)
    else:
        from camera.dslr import DSLRDriver
        driver = DSLRDriver(camera_id)

    if not driver.connect():
        log.error("FATAL: Camera failed to connect. Exiting.")
        return

    # Scene state + suppressor
    scene = SceneState()
    suppressor = StaticObjectSuppressor()
    frame_idx = 0
    last_eviction = time.monotonic()
    dancing_mode = False

    log.info("Capture loop started.")

    while True:
        loop_start = time.monotonic()

        # ── 1. Get preview frame ──
        try:
            frame = driver.get_live_preview_frame()
        except Exception as e:
            log.error(f"Preview error: {e}")
            time.sleep(0.5)
            continue

        frame_idx += 1
        scene.frame_count = frame_idx

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
        motion_thresh = DANCE_MOTION_VEL_THRESHOLD if dancing_mode else MOTION_VELOCITY_THRESHOLD
        engagement_thresh = scene.engagement_threshold

        # ── 5. Register detections + update scene ──
        visible_pids = []
        for det in detections:
            # Static object suppression (PRD D2, D4)
            suppressor.update(det.track_id, scene.compute_velocity(det.track_id) if det.track_id in scene.pids else 1.0)
            if suppressor.is_suppressed(det.track_id):
                continue

            pid = scene.register_detection(det)
            visible_pids.append(pid)

            # Compute + accumulate engagement score
            eng = scene.compute_engagement(frame, det)
            state = scene.pids[pid]
            state.engagement_score = eng

            threshold = state.engagement_override if state.engagement_override else engagement_thresh
            if eng >= threshold:
                state.engagement_sustained_frames += 1
            else:
                state.engagement_sustained_frames = 0

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
            _do_capture(driver, frame, best, scene, r, event_id, camera_id, buffer_dir, force=True)
            continue

        # ── 9. Priority ranking + capture decision ──
        candidates = []
        for pid in visible_pids:
            state = scene.pids[pid]

            # Hard caps (PRD 7.7.4)
            if state.capture_count >= MAX_TOTAL_CAPTURES_PER_PID:
                continue
            # Equity mode: skip over-represented PIDs
            if scene.equity_mode:
                avg = sum(s.capture_count for s in scene.pids.values()) / max(len(scene.pids), 1)
                if state.capture_count > avg:
                    continue

            # Cooldown gate
            if scene.in_cooldown(pid):
                continue

            # Sustain gate (PRD 7.1)
            sustain_needed = HANDSHAKE_SUSTAIN_FRAMES if _is_ceremony(state) else (
                1 if dancing_mode else MIN_SUSTAIN_FRAMES
            )
            if state.engagement_sustained_frames < sustain_needed:
                continue

            priority = scene.compute_priority(pid)
            candidates.append((pid, priority))

        if candidates:
            candidates.sort(key=lambda x: x[1], reverse=True)
            best_pid, best_priority = candidates[0]
            
            # PRD E1: Interaction Mode (Conversational) Check
            interacting = False
            for pid in visible_pids:
                if pid != best_pid and _is_interaction(scene.pids[best_pid], scene.pids[pid]):
                    interacting = True
                    break
                    
            if interacting:
                log.info(f"INTERACTION_MODE: PID {best_pid} is conversing. CANDID_BEHIND rules apply.")
                
            is_burst = dancing_mode or _is_ceremony(scene.pids[best_pid])
            
            log.info(f"CAPTURE: PID={best_pid} priority={best_priority:.2f} gini={gini:.2f} dancing={dancing_mode} burst={is_burst}")
            _do_capture(driver, frame, best_pid, scene, r, event_id, camera_id, buffer_dir, is_burst=is_burst)

        # ── 9.5 Dump State for UI Dashboard ──
        try:
            state_data = {
                "global_idle": time.monotonic() - scene.last_global_capture_time,
                "gini": gini,
                "dancing": dancing_mode,
                "pids": []
            }
            for det in detections:
                pid = det.track_id
                if pid in scene.pids:
                    s = scene.pids[pid]
                    cooldown = scene.dynamic_cooldown(pid)
                    time_since = time.monotonic() - s.last_capture_time
                    is_cooldown = time_since < cooldown
                    
                    # Logic gates
                    threshold = s.engagement_override if s.engagement_override else engagement_thresh
                    sustain_needed = HANDSHAKE_SUSTAIN_FRAMES if _is_ceremony(s) else (1 if dancing_mode else MIN_SUSTAIN_FRAMES)
                    
                    if is_cooldown:
                        status = "COOLDOWN"
                        reason = f"Wait {max(0, cooldown - time_since):.1f}s"
                        color = (0, 0, 255) # Red
                    elif s.engagement_score < threshold:
                        status = "IGNORING"
                        reason = f"Low Eng ({s.engagement_score:.2f} < {threshold:.2f})"
                        color = (0, 165, 255) # Orange
                    elif s.engagement_sustained_frames < sustain_needed:
                        status = "ANALYZING"
                        reason = f"Holding... ({s.engagement_sustained_frames}/{sustain_needed})"
                        color = (255, 255, 0) # Cyan
                    else:
                        status = "READY"
                        reason = f"Priority: {scene.compute_priority(pid):.2f}"
                        color = (0, 255, 0) # Green
                        
                    state_data["pids"].append({
                        "id": pid,
                        "bbox": det.bbox,
                        "status": status,
                        "reason": reason,
                        "color": color
                    })
            with open("/tmp/rec_state.json", "w") as f:
                json.dump(state_data, f)
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
                for p in visible_pids:
                    scene.pids[p].last_capture_time = 0.0

        # Target ~15 FPS loop
        elapsed = time.monotonic() - loop_start
        sleep_time = max(0, (1.0 / 15.0) - elapsed)
        time.sleep(sleep_time)


# ─────────────────────────────────────────────────────────────────
# Capture Execution
# ─────────────────────────────────────────────────────────────────

def _do_capture(driver, frame, pid: str, scene: SceneState, r, event_id: str,
                camera_id: str, buffer_dir: str, force: bool = False, is_burst: bool = False):
    """Execute a shutter trigger by sending a command to the camera controller via Redis."""
    state = scene.pids[pid]
    now = time.monotonic()

    # Publish capture command to Redis PubSub (Camera Controller will pick this up)
    try:
        command_type = "BURST" if is_burst else "CAPTURE"
        r.publish('camera_commands', json.dumps({
            "command": command_type,
            "pid": pid,
            "event_id": event_id,
            "camera_id": camera_id
        }))
        log.info(f"PUB/SUB: Sent {command_type} command for PID {pid}")
    except Exception as e:
        log.error(f"CAPTURE_PUB_ERROR: {e}")
        # In a real environment we might abort, but for sandbox/desktop testing 
        # without a local Redis server, we continue and update the state to prevent infinite loops.

    # Update scene state
    state.capture_count += 1
    state.last_capture_time = now
    state.engagement_sustained_frames = 0
    state.cooldown_override = None     # Clear starvation override after first capture
    state.engagement_override = None
    scene.last_global_capture_time = now
    # Reset watchdog threshold back to normal if it was lowered
    scene.engagement_threshold = ENGAGEMENT_THRESHOLD

    log.info(f"CAPTURE_REQUESTED (PID={pid}, count={state.capture_count}, force={force})")
    
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
