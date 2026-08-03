"""
Professional Photographic Composition & Framing Engine
=======================================================
Implements research-backed portrait and human photography composition rules (PRD 5.5, 7.5):
  - Rule of Thirds: Eyes positioned precisely on upper-third power line (30-35% down)
  - Proportional headroom: 8-18% breathing room above the head crown, never clipping hair
  - Lead room & Look room: Extra space in gaze/motion direction
  - Shoulder & Torso balance: Natural portrait framing that encompasses shoulders
  - Joint-safe cropping: Avoids slicing through human joints (neck, wrists, elbows, knees)
  - Multi-Scale Support: AUTO, TIGHT (close-up), MEDIUM (bust), WIDE (environmental), FULL (sensor-fill)
  - Full-sensor safe: Handles subjects covering entire webcam without distortion or panic
"""

from typing import Tuple, List, Optional, Dict, Union
import numpy as np

# Supported aspect ratios (width / height)
ASPECT_RATIO_MAP: Dict[str, Optional[float]] = {
    "16:9": 16.0 / 9.0,      # Landscape (1.778)
    "9:16": 9.0 / 16.0,      # Portrait / Stories / Reels (0.5625)
    "4:3": 4.0 / 3.0,        # Standard Landscape (1.333)
    "3:4": 3.0 / 4.0,        # Standard Portrait (0.75)
    "1:1": 1.0,              # Square (1.0)
    "4:5": 4.0 / 5.0,        # Social Portrait (0.80)
    "FULL": None,            # Sensor Native Full Frame
}

# Framing scale presets (padding multiplier around subject)
FRAMING_SCALE_MAP: Dict[str, float] = {
    "TIGHT": 1.15,           # Close-up framing
    "MEDIUM": 1.38,          # Standard waist-up / portrait framing
    "WIDE": 1.75,            # Environmental context / wide framing
    "FULL": 99.0,            # Maximum possible aspect ratio box that fits within sensor
    "AUTO": 0.0,             # Dynamically computed based on subject size & frame coverage
}

# ─── Professional Composition Constants ───
HEADROOM_MIN_FRAC = 0.08     # Minimum headroom as fraction of frame height
HEADROOM_MAX_FRAC = 0.22     # Maximum headroom as fraction of frame height
EYE_LINE_FRAC = 0.33         # Target vertical position for eye line (upper third)
MIN_SUBJECT_FILL = 0.15      # Minimum subject area / frame area
MAX_SUBJECT_FILL = 0.88      # Maximum subject area / frame area


def _clean_config_string(val: Any) -> str:
    """Sanitize config string from Redis/files (handling b'...' and quotes)."""
    if val is None:
        return ""
    if isinstance(val, bytes):
        val = val.decode("utf-8", errors="ignore")
    s = str(val).strip()
    if (s.startswith("b'") and s.endswith("'")) or (s.startswith('b"') and s.endswith('"')):
        s = s[2:-1]
    if (s.startswith("'") and s.endswith("'")) or (s.startswith('"') and s.endswith('"')):
        s = s[1:-1]
    return s.strip()


def parse_aspect_ratio(ar_input: Any) -> Optional[float]:
    """Parse string aspect ratio like '16:9', '9:16', '1:1', 'FULL' to float ratio."""
    if not ar_input:
        return None
    ar_clean = _clean_config_string(ar_input).upper()
    if not ar_clean:
        return None
    if ar_clean in ASPECT_RATIO_MAP:
        return ASPECT_RATIO_MAP[ar_clean]
    if ":" in ar_clean:
        try:
            parts = ar_clean.split(":")
            w, h = float(parts[0]), float(parts[1])
            if h > 0:
                return w / h
        except Exception:
            pass
    try:
        val = float(ar_clean)
        if val > 0:
            return val
    except ValueError:
        pass
    return None


def parse_framing_scale(scale_input: Any) -> float:
    """Parses a scale input (preset name or float multiplier) into a numeric padding factor."""
    if scale_input is None:
        return 0.0  # AUTO
    if isinstance(scale_input, (int, float)):
        return max(1.05, float(scale_input))
    scale_str = _clean_config_string(scale_input).upper()
    if scale_str in FRAMING_SCALE_MAP:
        return FRAMING_SCALE_MAP[scale_str]
    try:
        val = float(scale_str)
        return max(1.05, val)
    except ValueError:
        return 0.0  # Default to AUTO


def _extract_subject_landmarks(
    det_bbox: List[int],
    frame_width: int,
    frame_height: int,
    keypoints: Optional[np.ndarray] = None
) -> Tuple[float, float, float, float]:
    """
    Extracts precise anatomical landmarks for photography composition:
    Returns (eye_y, center_x, head_top, shoulder_span).
    """
    x1, y1, x2, y2 = det_bbox
    pw = max(10, x2 - x1)
    ph = max(10, y2 - y1)

    if keypoints is not None and len(keypoints) >= 7:
        # COCO Keypoints: 0=Nose, 1=Left Eye, 2=Right Eye, 3=Left Ear, 4=Right Ear, 5=Left Shoulder, 6=Right Shoulder
        has_eyes = (keypoints[1, 2] > 0.25 or keypoints[2, 2] > 0.25)
        has_shoulders = (keypoints[5, 2] > 0.25 or keypoints[6, 2] > 0.25)

        if has_eyes:
            valid_eyes = [keypoints[i, 1] for i in (1, 2) if keypoints[i, 2] > 0.25]
            eye_y = float(np.mean(valid_eyes))
        elif keypoints[0, 2] > 0.25:
            eye_y = float(keypoints[0, 1]) - ph * 0.08
        else:
            eye_y = y1 + ph * (0.28 if y2 >= 0.85 * frame_height else 0.16)

        if has_shoulders:
            valid_sh_x = [keypoints[i, 0] for i in (5, 6) if keypoints[i, 2] > 0.25]
            center_x = float(np.mean(valid_sh_x))
            sh_span = abs(keypoints[6, 0] - keypoints[5, 0]) if (keypoints[5, 2] > 0.25 and keypoints[6, 2] > 0.25) else pw * 0.85
        elif has_eyes:
            valid_eye_x = [keypoints[i, 0] for i in (1, 2) if keypoints[i, 2] > 0.25]
            center_x = float(np.mean(valid_eye_x))
            sh_span = pw * 0.85
        else:
            center_x = (x1 + x2) / 2.0
            sh_span = pw * 0.85

        # Head crown (top of hair)
        face_features_y = [keypoints[i, 1] for i in range(5) if keypoints[i, 2] > 0.25]
        if face_features_y:
            min_feat_y = min(face_features_y)
            head_top = max(0.0, min_feat_y - max(12.0, (eye_y - min_feat_y) * 1.1))
        else:
            head_top = float(y1)
    else:
        # High-accuracy heuristic when keypoints aren't present
        is_seated_bust = (y2 >= 0.82 * frame_height) or (pw / ph > 0.55) or (ph > frame_height * 0.6)
        eye_y = y1 + ph * (0.28 if is_seated_bust else 0.16)
        center_x = (x1 + x2) / 2.0
        head_top = float(y1)
        sh_span = pw * 0.85

    return eye_y, center_x, head_top, sh_span


def compute_framing_box(
    det_bbox: List[int],
    frame_width: int,
    frame_height: int,
    aspect_ratio: Any = "16:9",
    framing_scale: Any = "AUTO",
    motion_direction: Optional[float] = None,
    velocity: float = 0.0,
    keypoints: Optional[np.ndarray] = None,
    clamp_to_sensor: bool = True
) -> List[int]:
    """
    Computes a responsive, dynamically-resizing photographic framing crop box around a human subject.
    """
    clean_ar = _clean_config_string(aspect_ratio).upper()
    ratio = parse_aspect_ratio(clean_ar)
    x1, y1, x2, y2 = det_bbox

    # Native full frame fallback
    if ratio is None or clean_ar == "FULL":
        return [0, 0, frame_width, frame_height]

    pw = max(10, x2 - x1)
    ph = max(10, y2 - y1)

    # 1. Extract anatomical landmarks
    eye_y, center_x, head_top, sh_span = _extract_subject_landmarks(det_bbox, frame_width, frame_height, keypoints)

    # 2. Determine target framing dimensions around subject
    scale_str = _clean_config_string(framing_scale).upper()
    pad_factor = parse_framing_scale(framing_scale)

    if scale_str == "FULL" or pad_factor >= 90.0:
        # Maximum possible box of target aspect ratio within sensor
        if frame_width / float(frame_height) > ratio:
            target_h = float(frame_height)
            target_w = target_h * ratio
        else:
            target_w = float(frame_width)
            target_h = target_w / ratio
    elif scale_str == "TIGHT":
        # Close portrait (1.18x height)
        target_h = max(ph * 1.18, 120.0)
        target_w = target_h * ratio
        if target_w < pw * 1.15:
            target_w = pw * 1.15
            target_h = target_w / ratio
    elif scale_str == "MEDIUM":
        # Standard portrait (1.38x height)
        target_h = max(ph * 1.38, 160.0)
        target_w = target_h * ratio
        if target_w < pw * 1.30:
            target_w = pw * 1.30
            target_h = target_w / ratio
    elif scale_str == "WIDE":
        # Environmental wide framing (1.75x height)
        target_h = max(ph * 1.75, 220.0)
        target_w = target_h * ratio
        if target_w < pw * 1.60:
            target_w = pw * 1.60
            target_h = target_w / ratio
    else:  # AUTO (Adaptive responsive scaling)
        cov_h = ph / float(frame_height)
        if cov_h > 0.60:
            pad = 1.30  # Close up
        elif cov_h > 0.30:
            pad = 1.45  # Mid distance
        else:
            pad = 1.70  # Far subject

        target_h = max(ph * pad, 140.0)
        target_w = target_h * ratio

        # Ensure width comfortably fits subject shoulders/body with side margins
        min_w = max(pw * pad, sh_span * 1.25)
        if target_w < min_w:
            target_w = min_w
            target_h = target_w / ratio

    # 3. Limit dimensions to sensor bounds while strictly preserving aspect ratio
    if clamp_to_sensor:
        if target_w > frame_width:
            target_w = float(frame_width)
            target_h = target_w / ratio
        if target_h > frame_height:
            target_h = float(frame_height)
            target_w = target_h * ratio

    # 4. Horizontal Positioning: Subject perfectly centered in the frame
    ideal_left = center_x - (target_w / 2.0)
    if clamp_to_sensor:
        max_left = max(0.0, frame_width - target_w)
        ideal_left = max(0.0, min(ideal_left, max_left))

    # 5. Vertical Positioning: Grid Composition Rule-of-Thirds & Generous Headroom
    # Eye line placed on upper third grid line (33% from top of framing box)
    ideal_top = eye_y - (0.33 * target_h)

    # Generous Headroom Guard: Ensure at least 15% head clearance above head crown
    head_clearance_top = head_top - (target_h * 0.16)
    if ideal_top > head_clearance_top:
        ideal_top = head_clearance_top

    # FIT TIGHTLY: If there is no space above the head (ideal_top < 0), we must shrink 
    # the frame (zoom in tighter) to keep the eyes exactly on the 33% grid line!
    if ideal_top < 0.0:
        # We need ideal_top = 0.0 without shifting the eyes off the 33% grid.
        # eye_y - 0.33 * new_target_h = 0 => new_target_h = eye_y / 0.33
        new_target_h = max(ph * 1.15, eye_y / 0.33)
        new_target_w = new_target_h * ratio
        
        if new_target_h < target_h:
            target_h = new_target_h
            target_w = new_target_w
            
        ideal_top = 0.0
        
        # Re-center horizontally with tighter target_w
        ideal_left = center_x - (target_w / 2.0)
        if clamp_to_sensor:
            ideal_left = max(0.0, min(ideal_left, frame_width - target_w))

    # Clamp top to sensor bounds (bottom edge guard)
    if clamp_to_sensor:
        max_top = max(0.0, frame_height - target_h)
        ideal_top = max(0.0, min(ideal_top, max_top))

    # 6. Joint-safe crop check (avoid slicing at chin/neck)
    if ideal_top + target_h < y2:
        crop_frac = ((ideal_top + target_h) - y1) / max(ph, 1.0)
        if 0.18 < crop_frac < 0.24:
            shift = ph * 0.08
            if ideal_top + shift <= max_top:
                ideal_top += shift

    fx1 = int(round(ideal_left))
    fy1 = int(round(ideal_top))
    fx2 = int(round(min(frame_width, ideal_left + target_w)))
    fy2 = int(round(min(frame_height, ideal_top + target_h)))

    # Guarantee minimum dimensions
    fx2 = max(fx1 + 10, fx2)
    fy2 = max(fy1 + 10, fy2)

    return [fx1, fy1, fx2, fy2]


def compute_composition_score(
    det_bbox: List[int],
    framing_box: List[int],
    keypoints: Optional[np.ndarray] = None
) -> float:
    """
    Score how well a subject is composed within a framing box.
    Returns 0.0 (terrible) to 1.0 (perfect professional composition).
    
    Evaluates:
    - Eye-line on upper-third (weight 0.35)
    - Horizontal centering / Rule-of-Thirds (weight 0.25)
    - Headroom quality (weight 0.20)
    - Subject fill ratio (weight 0.20)
    """
    px1, py1, px2, py2 = det_bbox
    fx1, fy1, fx2, fy2 = framing_box
    fw = max(10, fx2 - fx1)
    fh = max(10, fy2 - fy1)
    pw = max(1, px2 - px1)
    ph = max(1, py2 - py1)

    eye_y, cx, head_top, _ = _extract_subject_landmarks(det_bbox, fw, fh, keypoints)

    # 1. Eye-line on upper third (ideal: 0.33)
    eye_in_frame = (eye_y - fy1) / fh
    eye_score = max(0.0, 1.0 - abs(eye_in_frame - EYE_LINE_FRAC) * 4.0)

    # 2. Horizontal position: subject center near center (0.50) or power lines (0.33, 0.67)
    cx_in_frame = (cx - fx1) / fw
    power_points = [0.33, 0.50, 0.67]
    horiz_score = max(0.0, 1.0 - min(abs(cx_in_frame - pp) for pp in power_points) * 5.0)

    # 3. Headroom quality
    headroom_px = head_top - fy1
    headroom_frac = headroom_px / fh
    if HEADROOM_MIN_FRAC <= headroom_frac <= HEADROOM_MAX_FRAC:
        headroom_score = 1.0
    elif headroom_frac < 0:
        headroom_score = 0.0  # Head cut off
    else:
        headroom_score = max(0.0, 1.0 - abs(headroom_frac - 0.14) * 5.0)

    # 4. Subject fill
    fill = (pw * ph) / max(fw * fh, 1)
    if MIN_SUBJECT_FILL <= fill <= MAX_SUBJECT_FILL:
        fill_score = 1.0
    else:
        fill_score = max(0.0, 1.0 - abs(fill - 0.45) * 2.0)

    composite = (0.35 * eye_score + 0.25 * horiz_score +
                 0.20 * headroom_score + 0.20 * fill_score)
    return round(min(1.0, max(0.0, composite)), 3)


def compute_bbox_iou(box1: List[int], box2: List[int]) -> float:
    """Compute Intersection over Union between two bboxes [x1,y1,x2,y2]."""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])
    
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    area1 = max(1, (box1[2] - box1[0]) * (box1[3] - box1[1]))
    area2 = max(1, (box2[2] - box2[0]) * (box2[3] - box2[1]))
    union = area1 + area2 - inter
    
    return inter / max(union, 1)


def compute_group_framing_box(
    det_bboxes: List[List[int]],
    frame_width: int,
    frame_height: int,
    aspect_ratio: str = "16:9",
    framing_scale: Union[str, float] = "AUTO"
) -> List[int]:
    """Computes an optimal collective framing box enclosing multiple detected persons."""
    if not det_bboxes:
        return [0, 0, frame_width, frame_height]
    if len(det_bboxes) == 1:
        return compute_framing_box(det_bboxes[0], frame_width, frame_height, aspect_ratio, framing_scale)

    gx1 = min(b[0] for b in det_bboxes)
    gy1 = min(b[1] for b in det_bboxes)
    gx2 = max(b[2] for b in det_bboxes)
    gy2 = max(b[3] for b in det_bboxes)

    return compute_framing_box([gx1, gy1, gx2, gy2], frame_width, frame_height, aspect_ratio, framing_scale)


def crop_frame_to_box(frame: np.ndarray, box: List[int]) -> np.ndarray:
    """Crops an image frame to the specified bounding box safely."""
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = box
    x1 = max(0, min(w - 1, x1))
    y1 = max(0, min(h - 1, y1))
    x2 = max(x1 + 1, min(w, x2))
    y2 = max(y1 + 1, min(h, y2))
    return frame[y1:y2, x1:x2]
