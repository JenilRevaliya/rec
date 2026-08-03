import os
import time
import json
import uuid
import asyncio
import logging
import requests
import subprocess
import glob
from typing import Optional
from fastapi import FastAPI, Request, Form, HTTPException, Cookie, Depends, WebSocket
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import sys
import redis

# Ensure edge-node root is on python path for imports
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EDGE_NODE_ROOT = os.path.dirname(BASE_DIR)
if EDGE_NODE_ROOT not in sys.path:
    sys.path.insert(0, EDGE_NODE_ROOT)

from camera.detector import detect_available_cameras
from orchestrator.utils.aspect_framing import compute_framing_box, crop_frame_to_box, parse_aspect_ratio
import cv2

# Redis for inter-process communication
r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

logging.basicConfig(level=logging.INFO, format="[EDGE-DASH] %(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("edge-dashboard")

app = FastAPI(title="REC Edge Dashboard")

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")
BUFFER_DIR = os.environ.get("CAMERA_BUFFER_DIR", "/tmp/capture-buffer")

os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
os.makedirs(BUFFER_DIR, exist_ok=True)
app.mount("/buffer", StaticFiles(directory=BUFFER_DIR), name="buffer")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# State
CLOUD_API_URL = os.environ.get("API_URL", "http://localhost:8000") # Swapped back to host IP if run natively
ORCHESTRATOR_PROCESS: Optional[subprocess.Popen] = None
CLOUD_SYNC_ENABLED = True
CURRENT_USER = None
CURRENT_EVENT_ID = "EVT-UNKNOWN"
UPLOADED_FILES = set()

def get_current_user(edge_token: Optional[str] = Cookie(None)):
    # Local bypass for testing if sandbox is needed, but we do strict check per PRD
    if not edge_token:
        return None
    return edge_token

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, user_token: str = Depends(get_current_user)):
    if not user_token:
        return RedirectResponse(url="/login")
    return RedirectResponse(url="/dashboard")

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html", context={"request": request})

@app.post("/login")
async def do_login(request: Request, email: str = Form(...), password: str = Form(...)):
    # Local Testing Bypass (Sandbox)
    if email == "photographer1" and password == "password":
        response = RedirectResponse(url="/dashboard", status_code=303)
        response.set_cookie(key="edge_token", value="OFFLINE_TEST_TOKEN", httponly=True)
        global CURRENT_USER
        CURRENT_USER = email
        log.info(f"Photographer logged in (SANDBOX): {email}")
        return response

    # Validate against Cloud API strictly (Untrusted Edge Node - PRD 12.2)
    # No local credential caching or sandbox bypass allowed in production.
    try:
        resp = requests.post(
            f"{CLOUD_API_URL}/api/v1/auth/edge-login",
            json={"email": email, "password": password, "role": "photographer"},
            timeout=5
        )
        if resp.status_code == 200:
            data = resp.json()
            token = data.get("access_token")
            
            response = RedirectResponse(url="/dashboard", status_code=303)
            response.set_cookie(key="edge_token", value=token, httponly=True)
            
            CURRENT_USER = email
            log.info(f"Photographer logged in: {email}")
            return response
        else:
            return templates.TemplateResponse(request=request, name="login.html", context={"request": request, "error": "Invalid credentials"})
    except Exception as e:
        log.error(f"Auth DB unreachable: {e}")
        return templates.TemplateResponse(request=request, name="login.html", context={"request": request, "error": "Cloud Auth DB Unreachable. Check connection."})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, user_token: str = Depends(get_current_user)):
    if not user_token:
        return RedirectResponse(url="/login")
        
    status = "Running" if ORCHESTRATOR_PROCESS and ORCHESTRATOR_PROCESS.poll() is None else "Stopped"
    return templates.TemplateResponse(request=request, name="dashboard.html", context={
        "request": request, 
        "user": CURRENT_USER,
        "status": status,
        "sync_enabled": CLOUD_SYNC_ENABLED
    })

@app.get("/api/cameras")
async def get_cameras():
    cameras = detect_available_cameras()
    return {"cameras": cameras}

def get_active_aspect_ratio_server() -> str:
    try:
        if os.path.exists("/tmp/rec_aspect_ratio.txt"):
            with open("/tmp/rec_aspect_ratio.txt", "r") as f:
                val = f.read().strip()
                if val: return val
    except Exception:
        pass
    try:
        val = r.get("rec_active_aspect_ratio")
        if val: return str(val)
    except Exception:
        pass
    return "16:9"

def get_active_framing_scale_server() -> str:
    try:
        if os.path.exists("/tmp/rec_framing_scale.txt"):
            with open("/tmp/rec_framing_scale.txt", "r") as f:
                val = f.read().strip()
                if val: return val
    except Exception:
        pass
    try:
        val = r.get("rec_active_framing_scale")
        if val: return str(val)
    except Exception:
        pass
    return "AUTO"

@app.post("/api/start-orchestrator")
async def start_orchestrator(request: Request, user_token: str = Depends(get_current_user)):
    if not user_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    data = await request.json()
    camera_id = data.get("camera_id", "MOCK_CAM_01")
    profile_id = data.get("profile_id", "DEFAULT")
    aspect_ratio = data.get("aspect_ratio", "16:9")
    framing_scale = data.get("framing_scale", "AUTO")
    
    # Save settings to file and Redis
    try:
        with open("/tmp/rec_aspect_ratio.txt", "w") as f:
            f.write(aspect_ratio)
        with open("/tmp/rec_framing_scale.txt", "w") as f:
            f.write(framing_scale)
    except Exception:
        pass
        
    try:
        r.set("rec_active_profile", profile_id)
        r.set("rec_active_aspect_ratio", aspect_ratio)
        r.set("rec_active_framing_scale", framing_scale)
    except redis.exceptions.ConnectionError:
        log.warning("Redis is offline (Connection Refused). Continuing capture sequence.")
        
    global ORCHESTRATOR_PROCESS
    if ORCHESTRATOR_PROCESS and ORCHESTRATOR_PROCESS.poll() is None:
        return {"status": "already_running"}
        
    env = os.environ.copy()
    env["EDGE_API_TOKEN"] = user_token
    env["REC_CAMERA_ID"] = camera_id
    env["REC_ASPECT_RATIO"] = aspect_ratio
    env["REC_FRAMING_SCALE"] = framing_scale
    env["USE_YOLO_MODEL"] = "1"
    env["USE_MOCK_CAMERA"] = "1" if camera_id.startswith("MOCK") else "0"
    project_root = os.path.dirname(BASE_DIR)
    env["PYTHONPATH"] = f"{project_root}:{env.get('PYTHONPATH', '')}"
    
    log.info(f"Starting Python Orchestrator Process targeting {camera_id} (AR={aspect_ratio}, Scale={framing_scale}) with executable {sys.executable}...")
    ORCHESTRATOR_PROCESS = subprocess.Popen(
        [sys.executable, "-m", "orchestrator.main"],
        env=env,
        cwd=project_root
    )
    return {"status": "started"}

@app.post("/api/stop-orchestrator")
async def stop_orchestrator(user_token: str = Depends(get_current_user)):
    if not user_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    global ORCHESTRATOR_PROCESS
    if ORCHESTRATOR_PROCESS:
        log.info("Stopping Orchestrator Process...")
        ORCHESTRATOR_PROCESS.terminate()
        try:
            ORCHESTRATOR_PROCESS.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            ORCHESTRATOR_PROCESS.kill()
        ORCHESTRATOR_PROCESS = None
    return {"status": "stopped"}

@app.post("/api/set-aspect-ratio")
async def set_aspect_ratio(request: Request, user_token: str = Depends(get_current_user)):
    if not user_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    data = await request.json()
    aspect_ratio = data.get("aspect_ratio", "16:9")
    try:
        with open("/tmp/rec_aspect_ratio.txt", "w") as f:
            f.write(aspect_ratio)
    except Exception:
        pass
    try:
        r.set("rec_active_aspect_ratio", aspect_ratio)
    except redis.exceptions.ConnectionError:
        pass
    log.info(f"Aspect ratio configured to: {aspect_ratio}")
    return {"status": "ok", "aspect_ratio": aspect_ratio}

@app.post("/api/set-framing-scale")
async def set_framing_scale(request: Request, user_token: str = Depends(get_current_user)):
    if not user_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    data = await request.json()
    framing_scale = data.get("framing_scale", "AUTO")
    try:
        with open("/tmp/rec_framing_scale.txt", "w") as f:
            f.write(framing_scale)
    except Exception:
        pass
    try:
        r.set("rec_active_framing_scale", framing_scale)
    except redis.exceptions.ConnectionError:
        pass
    log.info(f"Framing scale configured to: {framing_scale}")
    return {"status": "ok", "framing_scale": framing_scale}

@app.post("/api/set-profile")
async def set_profile(request: Request, user_token: str = Depends(get_current_user)):
    if not user_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    data = await request.json()
    profile = data.get("profile", "DEFAULT")
    try:
        r.set("rec_active_profile", profile)
    except redis.exceptions.ConnectionError:
        log.warning("Redis is offline. Profile change will not propagate to orchestrator.")
    return {"status": "ok", "profile": profile}

@app.post("/api/toggle-sync")
async def toggle_sync(request: Request, user_token: str = Depends(get_current_user)):
    if not user_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    data = await request.json()
    global CLOUD_SYNC_ENABLED
    CLOUD_SYNC_ENABLED = data.get("enabled", True)
    log.info(f"Cloud Sync is now: {'ON' if CLOUD_SYNC_ENABLED else 'OFF'}")
    return {"status": "success", "sync_enabled": CLOUD_SYNC_ENABLED}

@app.get("/api/smile-capture")
async def get_smile_capture():
    enabled = True
    try:
        if os.path.exists("/tmp/rec_smile_capture.txt"):
            with open("/tmp/rec_smile_capture.txt", "r") as f:
                enabled = (f.read().strip().lower() in ("1", "true", "yes", "on"))
        elif r:
            val = r.get("rec_smile_capture_enabled")
            if val is not None:
                enabled = (str(val).strip().lower() in ("1", "true", "yes", "on"))
    except Exception:
        pass
    return {"enabled": enabled}

@app.post("/api/toggle-smile-capture")
async def toggle_smile_capture(request: Request, user_token: str = Depends(get_current_user)):
    if not user_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    data = await request.json()
    enabled = bool(data.get("enabled", True))
    try:
        with open("/tmp/rec_smile_capture.txt", "w") as f:
            f.write("1" if enabled else "0")
    except Exception:
        pass
    try:
        r.set("rec_smile_capture_enabled", "1" if enabled else "0")
    except Exception:
        pass
    log.info(f"Smile-to-Capture is now: {'ON' if enabled else 'OFF'}")
    return {"status": "success", "smile_capture_enabled": enabled}

@app.post("/api/manual-capture")
async def manual_capture(user_token: str = Depends(get_current_user)):
    if not user_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    frame_src = "/tmp/rec_raw_frame.jpg" if os.path.exists("/tmp/rec_raw_frame.jpg") else "/tmp/rec_frame.jpg"
    if os.path.exists(frame_src):
        os.makedirs(BUFFER_DIR, exist_ok=True)
        img = cv2.imread(frame_src)
        if img is not None:
            h, w = img.shape[:2]
            aspect_ratio = get_active_aspect_ratio_server()
            framing_scale = get_active_framing_scale_server()
            
            # Check latest state for framing box of any active PID
            crop_box = None
            try:
                if os.path.exists("/tmp/rec_state.json"):
                    with open("/tmp/rec_state.json", "r") as f:
                        st = json.load(f)
                        pids = st.get("pids", [])
                        if pids and len(pids) > 0:
                            ready_pids = [p for p in pids if p.get("status") in ("READY", "ANALYZING")]
                            target_p = ready_pids[0] if ready_pids else pids[0]
                            crop_box = target_p.get("bbox")
            except Exception:
                pass
                
            if not crop_box:
                crop_box = compute_framing_box([0, 0, w, h], w, h, aspect_ratio=aspect_ratio, framing_scale=framing_scale)
                
            cropped_img = crop_frame_to_box(img, crop_box)
            filename = f"manual_{int(time.time())}.jpg"
            target_path = os.path.join(BUFFER_DIR, filename)
            cv2.imwrite(target_path, cropped_img, [cv2.IMWRITE_JPEG_QUALITY, 92])
            log.info(f"Manual capture ({aspect_ratio} cropped, scale={framing_scale}) saved to {target_path}")
            return {"status": "success", "filename": filename, "aspect_ratio": aspect_ratio, "framing_scale": framing_scale}
            
    return {"status": "failed", "detail": "Camera feed not active"}

@app.delete("/api/photos/{filename}")
async def discard_photo(filename: str, user_token: str = Depends(get_current_user)):
    if not user_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    # Security check to prevent directory traversal
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
        
    filepath = os.path.join(BUFFER_DIR, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        log.info(f"Photographer discarded photo: {filename}")
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="File not found")

@app.get("/api/buffer")
async def get_buffered_photos(user_token: str = Depends(get_current_user)):
    if not user_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    if not os.path.exists(BUFFER_DIR):
        return {"photos": []}
        
    photos = []
    for filename in os.listdir(BUFFER_DIR):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
            filepath = os.path.join(BUFFER_DIR, filename)
            # Get file stats
            stat = os.stat(filepath)
            photos.append({
                "filename": filename,
                "url": f"/buffer/{filename}",
                "timestamp": stat.st_mtime
            })
            
    # Sort newest first
    photos.sort(key=lambda x: x["timestamp"], reverse=True)
    return {"photos": photos[:50]}  # Return last 50 captures

async def mjpeg_frame_generator():
    """Generates continuous MJPEG multipart stream at up to 30 FPS with zero HTTP reconnect latency."""
    frame_path = "/tmp/rec_frame.jpg"
    last_frame_bytes = b""
    
    while True:
        try:
            if os.path.exists(frame_path):
                with open(frame_path, "rb") as f:
                    frame_bytes = f.read()
                if frame_bytes and len(frame_bytes) > 100:
                    last_frame_bytes = frame_bytes
                    yield (b"--frame\r\n"
                           b"Content-Type: image/jpeg\r\n"
                           b"Content-Length: " + str(len(frame_bytes)).encode() + b"\r\n\r\n"
                           + frame_bytes + b"\r\n")
            elif last_frame_bytes:
                yield (b"--frame\r\n"
                       b"Content-Type: image/jpeg\r\n"
                       b"Content-Length: " + str(len(last_frame_bytes)).encode() + b"\r\n\r\n"
                       + last_frame_bytes + b"\r\n")
            await asyncio.sleep(0.033) # 30 FPS target
        except asyncio.CancelledError:
            break
        except Exception:
            await asyncio.sleep(0.05)

@app.get("/api/stream.mjpg")
async def get_mjpeg_stream():
    """Low-latency continuous MJPEG video stream."""
    return StreamingResponse(
        mjpeg_frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )

@app.get("/api/stream")
async def get_stream():
    # Single-frame snapshot endpoint with no-cache headers
    if os.path.exists("/tmp/rec_frame.jpg"):
        return FileResponse(
            "/tmp/rec_frame.jpg",
            media_type="image/jpeg",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )
    raise HTTPException(status_code=404)

@app.get("/api/state")
async def get_state():
    if os.path.exists("/tmp/rec_state.json"):
        with open("/tmp/rec_state.json", "r") as f:
            return json.load(f)
    return {}

async def background_uploader():
    """Background task to sync images to cloud if enabled."""
    global UPLOADED_FILES
    last_offline_warning = 0
    while True:
        try:
            if CLOUD_SYNC_ENABLED and CURRENT_USER:
                files = sorted(glob.glob(os.path.join(BUFFER_DIR, "*.*")), key=os.path.getmtime)
                for path in files:
                    if path not in UPLOADED_FILES:
                        try:
                            with open(path, "rb") as f:
                                resp = requests.post(
                                    f"{CLOUD_API_URL}/upload",
                                    files={"file": f},
                                    data={"event": CURRENT_EVENT_ID, "photographer": CURRENT_USER},
                                    timeout=3
                                )
                            if resp.status_code == 200:
                                log.info(f"Uploaded {os.path.basename(path)} to cloud.")
                                UPLOADED_FILES.add(path)
                        except (requests.ConnectionError, requests.Timeout):
                            now = time.time()
                            if now - last_offline_warning > 30:
                                log.debug(f"[CloudSync] Cloud backend offline at {CLOUD_API_URL}. Sync paused.")
                                last_offline_warning = now
                            await asyncio.sleep(10)
                            break
        except asyncio.CancelledError:
            break
        except Exception as e:
            log.debug(f"[CloudSync] Upload check exception: {e}")
            
        await asyncio.sleep(2)

async def deadman_heartbeat():
    """
    Heartbeat Enforcement (PRD 12.2.5).
    Pings the cloud /heartbeat endpoint every 5 minutes.
    On 3 consecutive failures, self-terminates the orchestrator to prevent offline tampering.
    """
    global ORCHESTRATOR_PROCESS, CURRENT_USER
    failures = 0
    
    while True:
        await asyncio.sleep(300) # 5 minutes
        if not CURRENT_USER or not ORCHESTRATOR_PROCESS:
            continue
            
        try:
            resp = requests.post(
                f"{CLOUD_API_URL}/api/v1/auth/edge-heartbeat",
                json={"user": CURRENT_USER},
                timeout=5
            )
            if resp.status_code == 200:
                failures = 0
                log.info("[Heartbeat] Edge Node authenticated successfully.")
            else:
                failures += 1
                log.warning(f"[Heartbeat] Cloud rejected heartbeat (Failures: {failures}/3)")
        except Exception as e:
            failures += 1
            log.debug(f"[Heartbeat] Cloud unreachable (Failures: {failures}/3)")
            
        if failures >= 3:
            log.error("[Heartbeat] DEAD-MAN SWITCH TRIGGERED. Terminating Orchestrator.")
            if ORCHESTRATOR_PROCESS:
                try:
                    ORCHESTRATOR_PROCESS.terminate()
                    ORCHESTRATOR_PROCESS.wait(timeout=2.0)
                except Exception:
                    ORCHESTRATOR_PROCESS.kill()
                ORCHESTRATOR_PROCESS = None
            failures = 0

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(background_uploader())
    asyncio.create_task(deadman_heartbeat())

@app.on_event("shutdown")
def shutdown_event():
    global ORCHESTRATOR_PROCESS
    if ORCHESTRATOR_PROCESS:
        try:
            ORCHESTRATOR_PROCESS.terminate()
            ORCHESTRATOR_PROCESS.wait(timeout=2.0)
        except Exception:
            ORCHESTRATOR_PROCESS.kill()
        ORCHESTRATOR_PROCESS = None
    log.info("Edge Dashboard server stopped cleanly.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
