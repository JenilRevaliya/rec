import os
import time
import json
import uuid
import asyncio
import logging
import requests
import subprocess
from typing import Optional
from fastapi import FastAPI, Request, Form, HTTPException, Cookie, Depends, WebSocket
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

logging.basicConfig(level=logging.INFO, format="[EDGE-DASH] %(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("edge-dashboard")

app = FastAPI(title="REC Edge Dashboard")

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")
BUFFER_DIR = os.environ.get("CAMERA_BUFFER_DIR", "/capture-buffer")

os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/buffer", StaticFiles(directory=BUFFER_DIR), name="buffer")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# State
CLOUD_API_URL = os.environ.get("API_URL", "http://api-gateway:8000")
ORCHESTRATOR_PROCESS: Optional[subprocess.Popen] = None
CLOUD_SYNC_ENABLED = True
CURRENT_USER = None
CURRENT_EVENT_ID = None

def get_current_user(edge_token: Optional[str] = Cookie(None)):
    if not edge_token:
        return None
    return edge_token # In a real app, decode JWT or validate token here

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, user_token: str = Depends(get_current_user)):
    if not user_token:
        return RedirectResponse(url="/login")
    return RedirectResponse(url="/dashboard")

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def do_login(request: Request, email: str = Form(...), password: str = Form(...)):
    # Validate against Cloud API
    try:
        resp = requests.post(
            f"{CLOUD_API_URL}/api/v1/auth/login",
            json={"email": email, "password": password, "role": "photographer"}
        )
        if resp.status_code == 200:
            data = resp.json()
            token = data.get("access_token")
            
            response = RedirectResponse(url="/dashboard", status_code=303)
            response.set_cookie(key="edge_token", value=token, httponly=True)
            
            global CURRENT_USER
            CURRENT_USER = email
            log.info(f"Photographer logged in: {email}")
            return response
        else:
            return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})
    except Exception as e:
        log.error(f"Auth DB unreachable: {e}")
        return templates.TemplateResponse("login.html", {"request": request, "error": "Cloud Auth DB Unreachable. Check connection."})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, user_token: str = Depends(get_current_user)):
    if not user_token:
        return RedirectResponse(url="/login")
        
    status = "Running" if ORCHESTRATOR_PROCESS and ORCHESTRATOR_PROCESS.poll() is None else "Stopped"
    return templates.TemplateResponse("dashboard.html", {
        "request": request, 
        "user": CURRENT_USER,
        "status": status,
        "sync_enabled": CLOUD_SYNC_ENABLED
    })

@app.post("/api/start-orchestrator")
async def start_orchestrator(user_token: str = Depends(get_current_user)):
    if not user_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    global ORCHESTRATOR_PROCESS
    if ORCHESTRATOR_PROCESS and ORCHESTRATOR_PROCESS.poll() is None:
        return {"status": "already_running"}
        
    # Start the actual camera orchestrator python script
    # We pass the token so the orchestrator can auth with the cloud
    env = os.environ.copy()
    env["EDGE_API_TOKEN"] = user_token
    
    log.info("Starting Python Orchestrator Process...")
    ORCHESTRATOR_PROCESS = subprocess.Popen(
        ["python", "-m", "orchestrator.main"],
        env=env,
        cwd=os.path.dirname(BASE_DIR)
    )
    return {"status": "started"}

@app.post("/api/stop-orchestrator")
async def stop_orchestrator(user_token: str = Depends(get_current_user)):
    if not user_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    global ORCHESTRATOR_PROCESS
    if ORCHESTRATOR_PROCESS:
        log.info("Terminating Orchestrator Process...")
        ORCHESTRATOR_PROCESS.terminate()
        ORCHESTRATOR_PROCESS = None
        
    return {"status": "stopped"}

@app.post("/api/toggle-sync")
async def toggle_sync(request: Request, user_token: str = Depends(get_current_user)):
    if not user_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    data = await request.json()
    global CLOUD_SYNC_ENABLED
    CLOUD_SYNC_ENABLED = data.get("enabled", True)
    log.info(f"Cloud Sync is now: {'ON' if CLOUD_SYNC_ENABLED else 'OFF'}")
    return {"status": "success", "sync_enabled": CLOUD_SYNC_ENABLED}

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

@app.websocket("/ws/live-feed")
async def websocket_live_feed(websocket: WebSocket):
    await websocket.accept()
    try:
        # In a real app, this would stream the MJPEG or base64 frames 
        # from the camera.mock/gphoto2 via a shared memory/Redis pubsub channel.
        while True:
            # Placeholder for actual live feed integration
            await asyncio.sleep(1)
            # await websocket.send_text("frame_data")
    except Exception as e:
        log.error(f"WebSocket closed: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
