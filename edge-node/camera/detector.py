import os
import sys
import time
import platform
import subprocess
import json
import logging
from typing import List, Dict, Any

logger = logging.getLogger("camera_detector")

# Cache to avoid probing cameras on every single HTTP request if polled frequently
_CAMERA_CACHE = {
    "timestamp": 0.0,
    "cameras": []
}
CACHE_TTL_SECONDS = 5.0

def _get_macos_camera_names() -> List[str]:
    """Retrieve camera names on macOS using system_profiler."""
    names = []
    try:
        proc = subprocess.run(
            ["system_profiler", "-json", "SPCameraDataType"],
            capture_output=True,
            text=True,
            timeout=2.0
        )
        if proc.returncode == 0 and proc.stdout:
            data = json.loads(proc.stdout)
            cam_list = data.get("SPCameraDataType", [])
            for item in cam_list:
                name = item.get("_name") or item.get("spcamera_model-id")
                if name:
                    names.append(name.strip())
    except Exception as e:
        logger.debug(f"Error querying macOS system_profiler for cameras: {e}")
    return names

def _get_linux_camera_names() -> Dict[int, str]:
    """Retrieve Linux V4L2 camera names from /sys/class/video4linux/."""
    names = {}
    try:
        base_path = "/sys/class/video4linux"
        if os.path.exists(base_path):
            for entry in os.listdir(base_path):
                if entry.startswith("video"):
                    try:
                        idx = int(entry.replace("video", ""))
                        name_file = os.path.join(base_path, entry, "name")
                        if os.path.exists(name_file):
                            with open(name_file, "r") as f:
                                names[idx] = f.read().strip()
                    except (ValueError, IOError):
                        continue
    except Exception as e:
        logger.debug(f"Error reading Linux v4l2 camera names: {e}")
    return names

def detect_available_cameras(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """
    Scans the system for all connected webcams, virtual cameras, and fallback drivers.
    Returns a list of camera descriptors:
    [
        {"id": "Webcam_0", "label": "Webcam 0 (FaceTime HD Camera)", "type": "webcam", "index": 0},
        {"id": "Webcam_1", "label": "Webcam 1 (OBS Virtual Camera)", "type": "webcam", "index": 1},
        {"id": "MOCK_CAM_01", "label": "MOCK_CAM_01 (Virtual Simulator)", "type": "mock"},
        {"id": "DSLR_01", "label": "DSLR_01 (Tethered Camera)", "type": "dslr"}
    ]
    """
    global _CAMERA_CACHE
    now = time.time()
    if not force_refresh and (now - _CAMERA_CACHE["timestamp"]) < CACHE_TTL_SECONDS and _CAMERA_CACHE["cameras"]:
        return _CAMERA_CACHE["cameras"]

    import cv2

    system_name = platform.system()
    mac_names = _get_macos_camera_names() if system_name == "Darwin" else []
    linux_names = _get_linux_camera_names() if system_name == "Linux" else {}

    detected_webcams = []
    consecutive_failures = 0
    max_indices_to_check = 10

    # Suppress OpenCV C++ stderr output during probing
    devnull_fd = os.open(os.devnull, os.O_WRONLY)
    saved_stderr_fd = None
    try:
        saved_stderr_fd = os.dup(2)
        os.dup2(devnull_fd, 2)
    except Exception:
        pass

    try:
        for i in range(max_indices_to_check):
            # On Linux, skip checking index if /dev/video{i} does not exist
            if system_name == "Linux" and not os.path.exists(f"/dev/video{i}"):
                consecutive_failures += 1
                if consecutive_failures >= 3 and i >= 4:
                    break
                continue

            try:
                # Test opening camera
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    consecutive_failures = 0
                    label = f"Webcam {i}"
                    
                    # Assign friendly name if available
                    if system_name == "Darwin":
                        if i < len(mac_names):
                            label = f"Webcam {i} ({mac_names[i]})"
                        elif mac_names:
                            label = f"Webcam {i} ({mac_names[-1]})"
                    elif system_name == "Linux" and i in linux_names:
                        label = f"Webcam {i} ({linux_names[i]})"

                    detected_webcams.append({
                        "id": f"Webcam_{i}",
                        "label": label,
                        "type": "webcam",
                        "index": i
                    })
                    cap.release()
                else:
                    consecutive_failures += 1
                    if consecutive_failures >= 3 and i >= 4:
                        break
            except Exception as e:
                consecutive_failures += 1
                logger.debug(f"Exception probing camera index {i}: {e}")
    finally:
        if saved_stderr_fd is not None:
            try:
                os.dup2(saved_stderr_fd, 2)
                os.close(saved_stderr_fd)
            except Exception:
                pass
        try:
            os.close(devnull_fd)
        except Exception:
            pass

    # If no webcams could be opened (e.g. permissions or sandbox), but macOS reported camera hardware:
    if not detected_webcams and system_name == "Darwin" and mac_names:
        for idx, name in enumerate(mac_names):
            detected_webcams.append({
                "id": f"Webcam_{idx}",
                "label": f"Webcam {idx} ({name})",
                "type": "webcam",
                "index": idx
            })
    elif not detected_webcams and system_name == "Linux" and linux_names:
        for idx, name in linux_names.items():
            detected_webcams.append({
                "id": f"Webcam_{idx}",
                "label": f"Webcam {idx} ({name})",
                "type": "webcam",
                "index": idx
            })
    elif not detected_webcams:
        # Fallback default webcam 0
        detected_webcams.append({
            "id": "Webcam_0",
            "label": "Webcam 0 (Default Camera)",
            "type": "webcam",
            "index": 0
        })

    all_cameras = []
    # Add detected webcams first
    all_cameras.extend(detected_webcams)

    # Add mock and DSLR options for testing and production tethering
    all_cameras.append({
        "id": "MOCK_CAM_01",
        "label": "MOCK_CAM_01 (Virtual Simulator)",
        "type": "mock"
    })
    all_cameras.append({
        "id": "DSLR_01",
        "label": "DSLR_01 (Tethered Camera)",
        "type": "dslr"
    })

    _CAMERA_CACHE = {
        "timestamp": now,
        "cameras": all_cameras
    }
    return all_cameras

def get_camera_id_list() -> List[str]:
    """Returns a simple list of camera ID strings."""
    cams = detect_available_cameras()
    return [c["id"] for c in cams]
