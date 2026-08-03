import cv2
import numpy as np
import logging
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)

def evaluate_sharpness(frame: np.ndarray) -> float:
    """
    Computes the variance of the Laplacian.
    This is an extremely fast (<0.5ms) metric for focus and motion blur.
    Returns a score typically between 0 (very blurry) and 500+ (very sharp).
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()

def get_best_backtrack_frame(candidates: List[np.ndarray]) -> Tuple[Optional[np.ndarray], float, int]:
    """
    Scans a list of candidate frames and returns the sharpest one.
    
    Args:
        candidates: List of OpenCV image frames (BGR).
        
    Returns:
        Tuple of (Best Frame, Sharpness Score, Index of Best Frame).
        Returns (None, 0.0, -1) if candidates list is empty.
    """
    if not candidates:
        return None, 0.0, -1

    best_frame = None
    best_score = -1.0
    best_idx = -1

    for idx, frame in enumerate(candidates):
        score = evaluate_sharpness(frame)
        if score > best_score:
            best_score = score
            best_frame = frame
            best_idx = idx

    logger.info(f"[FastIQG] Backtrack selected frame {best_idx}/{len(candidates)} with sharpness: {best_score:.1f}")
    return best_frame, best_score, best_idx
