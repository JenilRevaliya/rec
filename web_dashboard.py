"""
web_dashboard.py — Browser-based capture dashboard.
Run:  ./venv/bin/python web_dashboard.py
Open: http://localhost:8080
"""

import sys, os, time, threading, base64, json
import cv2
import numpy as np
import requests
from datetime import timedelta
from flask import Flask, Response, jsonify, request, send_from_directory, session, redirect, url_for
from functools import wraps

# Full-resolution capture storage
CAPTURE_DIR = os.path.join(os.path.dirname(__file__), 'capture-buffer')
os.makedirs(CAPTURE_DIR, exist_ok=True)

# Cloud server connection (configure this on the photographer's edge node)
CLOUD_API = os.environ.get("CLOUD_API_URL", "http://localhost:8001").rstrip("/")

sys.path.append(os.path.join(os.path.dirname(__file__), 'edge-node'))
from ultralytics import YOLO
from orchestrator.utils.aspect_framing import (
    compute_framing_box, compute_composition_score, compute_bbox_iou
)

# ─── helpers ──────────────────────────────────────────────────────────────────

def get_blur_score(image):
    if image is None or image.size == 0:
        return 0
    return cv2.Laplacian(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()

def analyze_eye(frame, cx, cy, size=20):
    x1 = max(0, int(cx - size/2)); y1 = max(0, int(cy - size/2))
    x2 = min(frame.shape[1], int(cx + size/2)); y2 = min(frame.shape[0], int(cy + size/2))
    if x2 - x1 < 5 or y2 - y1 < 5:
        return True, 1000.0
    ec = frame[y1:y2, x1:x2]
    g  = cv2.cvtColor(ec, cv2.COLOR_BGR2GRAY)
    return (np.std(g) > 12.0 and cv2.Laplacian(g, cv2.CV_64F).var() > 30.0), 0.0

def crop_with_padding(frame, box):
    x1, y1, x2, y2 = [int(v) for v in box]
    h, w = frame.shape[:2]
    oh, ow = y2 - y1, x2 - x1
    if oh <= 0 or ow <= 0:
        return np.zeros((10, 10, 3), dtype=np.uint8)
    canvas = np.zeros((oh, ow, 3), dtype=np.uint8)
    sx1, sy1 = max(0, x1), max(0, y1)
    sx2, sy2 = min(w, x2), min(h, y2)
    if sx1 >= sx2 or sy1 >= sy2:
        return canvas
    dx1, dy1 = sx1 - x1, sy1 - y1
    canvas[dy1:dy1+(sy2-sy1), dx1:dx1+(sx2-sx1)] = frame[sy1:sy2, sx1:sx2]
    return canvas

class EllipseKF:
    """
    10-state Kalman filter for ellipse parameters (cx, cy, MA, ma, angle).
    State: [cx, cy, MA, ma, angle, vcx, vcy, vMA, vma, vangle]
    Constant-velocity model — velocity states bridge frames and kill jitter.
    """
    def __init__(self):
        self.kf = cv2.KalmanFilter(10, 5)
        A = np.eye(10, dtype=np.float32)
        for i in range(5):
            A[i, i + 5] = 1.0
        self.kf.transitionMatrix = A

        H = np.zeros((5, 10), dtype=np.float32)
        for i in range(5):
            H[i, i] = 1.0
        self.kf.measurementMatrix = H

        self.kf.processNoiseCov = np.eye(10, dtype=np.float32) * 1e-2
        for i in range(5, 10):
            self.kf.processNoiseCov[i, i] = 1e-1
        self.kf.measurementNoiseCov = np.eye(5, dtype=np.float32) * 5.0
        self.kf.errorCovPost        = np.eye(10, dtype=np.float32) * 1.0

        self.initialized  = False
        self._last_angle  = 0.0

    def update(self, m):
        meas = np.array(m, dtype=np.float32)
        # Unwrap angle to prevent 180° flip jitter
        angle = meas[4]
        if self.initialized:
            diff = angle - self._last_angle
            if   diff >  90: angle -= 180
            elif diff < -90: angle += 180
        meas[4] = angle
        self._last_angle = angle

        if not self.initialized:
            self.kf.statePost = np.zeros((10, 1), dtype=np.float32)
            for i in range(5):
                self.kf.statePost[i, 0] = meas[i]
            self.initialized = True

        self.kf.predict()
        corrected = self.kf.correct(meas.reshape(5, 1))
        return corrected[:5, 0].tolist()


# ─── engine ───────────────────────────────────────────────────────────────────

class CaptureEngine:
    def __init__(self):
        print("Loading YOLOv8n-pose...")
        self.pose_model = YOLO('yolov8n-pose.pt')

        print("Loading MediaPipe...")
        import mediapipe as mp
        self.mp = mp
        self.mp_fmt = mp.ImageFormat.SRGB
        BO = mp.tasks.BaseOptions
        self.gesture_rec = mp.tasks.vision.GestureRecognizer.create_from_options(
            mp.tasks.vision.GestureRecognizerOptions(
                base_options=BO(model_asset_path='model/gesture_recognizer.task'),
                running_mode=mp.tasks.vision.RunningMode.IMAGE))
        self.face_rec = mp.tasks.vision.FaceLandmarker.create_from_options(
            mp.tasks.vision.FaceLandmarkerOptions(
                base_options=BO(model_asset_path='model/face_landmarker.task'),
                running_mode=mp.tasks.vision.RunningMode.IMAGE,
                output_face_blendshapes=True))

        print("Opening camera...")
        self.cap = cv2.VideoCapture(1)
        if not self.cap.isOpened():
            self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        self.lock = threading.Lock()
        self.frame_counter   = 0
        self.cooldown_frames = 0
        self.captured_count  = 0
        self.smoothed_boxes      = {}
        self.ellipse_kfs         = {}
        self.capture_buffers     = {}
        self.last_optimal_bboxes = {}
        self.gesture_cache   = {}
        self.gesture_history = {}
        self.require_smile   = False
        self.require_thumbs  = False
        self.auto_upload     = False
        self.auto_delete     = False
        self.event_id        = "EVT-UNKNOWN"
        self.photographer_id = "Unknown"
        self.latest_jpeg     = b''
        self.queue           = []
        self.status          = {}
        self._running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while self._running:
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.03); continue

            self.frame_counter += 1
            display = frame.copy()
            h, w = display.shape[:2]

            results = self.pose_model.track(frame, persist=True, verbose=False, imgsz=480)

            with self.lock:
                if self.cooldown_frames > 0:
                    self.cooldown_frames -= 1
                req_smile  = self.require_smile
                req_thumbs = self.require_thumbs

            optimal_found   = False
            captured_crop   = None
            captured_id     = None
            captured_reason = None
            live_ids        = []

            for result in results:
                boxes = result.boxes
                kpoints = result.keypoints
                if boxes is None or len(boxes) == 0: continue

                for i in range(len(boxes)):
                    if int(boxes.cls[i].item()) != 0: continue
                    x1, y1, x2, y2 = boxes.xyxy[i].tolist()
                    conf = boxes.conf[i].item()
                    tid  = int(boxes.id[i].item()) if boxes.id is not None else i
                    if conf < 0.5: continue

                    alpha = 0.5
                    if tid in self.smoothed_boxes:
                        px1,py1,px2,py2 = self.smoothed_boxes[tid]
                        x1=alpha*x1+(1-alpha)*px1; y1=alpha*y1+(1-alpha)*py1
                        x2=alpha*x2+(1-alpha)*px2; y2=alpha*y2+(1-alpha)*py2
                    self.smoothed_boxes[tid] = (x1,y1,x2,y2)

                    kpts = kpoints.data[i].cpu().numpy() if kpoints is not None else None
                    fb   = compute_framing_box([int(x1),int(y1),int(x2),int(y2)], w, h,
                                               aspect_ratio="4:3", framing_scale="AUTO",
                                               keypoints=kpts, clamp_to_sensor=False)
                    comp = compute_composition_score([int(x1),int(y1),int(x2),int(y2)], fb, kpts)
                    pcrop = frame[max(0,int(y1)):min(h,int(y2)), max(0,int(x1)):min(w,int(x2))]

                    # gesture
                    if tid not in self.gesture_cache:
                        self.gesture_cache[tid]   = (False, 0.0, False, None, None)
                        self.gesture_history[tid] = {'smile':[], 'thumbs':[]}
                    is_smiling, s_score, is_thumbs, face_lms, hand_lms = self.gesture_cache[tid]

                    if self.frame_counter % 3 == 0:
                        raw_s = raw_t = False; s_score = 0.0
                        fl_c = hl_c = None
                        if pcrop.size > 0:
                            try:
                                mp_img = self.mp.Image(image_format=self.mp_fmt,
                                    data=cv2.cvtColor(pcrop, cv2.COLOR_BGR2RGB))
                                if req_smile:
                                    fr = self.face_rec.detect(mp_img)
                                    if fr.face_blendshapes:
                                        fl_c = fr.face_landmarks[0] if fr.face_landmarks else None
                                        for s in fr.face_blendshapes[0]:
                                            if s.category_name in ('mouthSmileLeft','mouthSmileRight') and s.score > 0.45:
                                                raw_s = True; s_score = s.score*100; break
                                if req_thumbs:
                                    gr = self.gesture_rec.recognize(mp_img)
                                    if gr.gestures:
                                        hl_c = gr.hand_landmarks[0] if gr.hand_landmarks else None
                                        for g in gr.gestures[0]:
                                            if g.category_name == 'Thumb_Up' and g.score > 0.5:
                                                raw_t = True; break
                            except: pass

                        self.gesture_history[tid]['smile'].append(raw_s)
                        self.gesture_history[tid]['thumbs'].append(raw_t)
                        for k in ('smile','thumbs'):
                            if len(self.gesture_history[tid][k]) > 4:
                                self.gesture_history[tid][k].pop(0)
                        is_smiling = sum(self.gesture_history[tid]['smile']) >= 3
                        is_thumbs  = sum(self.gesture_history[tid]['thumbs']) >= 3
                        face_lms   = fl_c if is_smiling else None
                        hand_lms   = hl_c if is_thumbs  else None
                        self.gesture_cache[tid] = (is_smiling, s_score, is_thumbs, face_lms, hand_lms)

                    live_ids.append(tid)

                    # quality checks
                    is_opt = (comp >= 0.70)
                    alerts = []

                    meets = True
                    if req_smile or req_thumbs:
                        meets = False
                        if req_smile  and is_smiling: meets = True
                        if req_thumbs and is_thumbs:  meets = True
                    if not meets:
                        is_opt = False
                        if req_smile and req_thumbs: alerts.append("WAITING: Smile OR Thumbs Up")
                        elif req_smile:  alerts.append("WAITING: Smile")
                        else:            alerts.append("WAITING: Thumbs Up")

                    with self.lock:
                        cd = self.cooldown_frames
                    if cd > 0:
                        alerts.append("COOLDOWN"); is_opt = False
                    elif comp < 0.70:
                        bcx = (x1+x2)/2; fcx = (fb[0]+fb[2])/2; fh = fb[3]-fb[1]
                        if   bcx < fcx-30:           alerts.append("REJECTED: Move Right")
                        elif bcx > fcx+30:           alerts.append("REJECTED: Move Left")
                        elif y1 < fb[1]+fh*0.1:      alerts.append("REJECTED: Too High")
                        elif y1 > fb[1]+fh*0.25:     alerts.append("REJECTED: Too Low")
                        else:                        alerts.append("REJECTED: Center Yourself")

                    fill = ((x2-x1)*(y2-y1))/(w*h)
                    if   fill < 0.15: alerts.append("MOVE NEAR"); is_opt = False
                    elif fill > 0.65: alerts.append("MOVE BACK"); is_opt = False

                    is_frontal = False
                    if kpts is not None and len(kpts) >= 5:
                        if kpts[0][2]>0.2 and kpts[1][2]>0.2 and kpts[2][2]>0.2:
                            is_frontal = True
                            ed = np.sqrt((kpts[1][0]-kpts[2][0])**2+(kpts[1][1]-kpts[2][1])**2)
                            es = max(10, int(ed*0.45))
                            lo,_ = analyze_eye(frame, kpts[1][0], kpts[1][1], es)
                            ro,_ = analyze_eye(frame, kpts[2][0], kpts[2][1], es)
                            if not lo or not ro:
                                alerts.append("REJECTED: Open Eyes"); is_opt = False
                    if not is_frontal:
                        alerts.append("REJECTED: Face Not Frontal"); is_opt = False
                    if x1<=5 or y1<=5 or x2>=w-5:
                        alerts.append("REJECTED: Cut Off"); is_opt = False

                    cfb = [int(fb[0]),int(fb[1]),int(fb[2]),int(fb[3])]
                    rc  = crop_with_padding(frame, cfb)
                    blur = get_blur_score(rc)
                    exp  = float(np.mean(cv2.cvtColor(rc, cv2.COLOR_BGR2GRAY))) if rc.size>0 else 127

                    if   blur < 150: alerts.append("REJECTED: Blurry"); is_opt = False
                    elif exp  > 235: alerts.append("REJECTED: Overexposed"); is_opt = False
                    elif exp  < 30:  alerts.append("REJECTED: Too Dark"); is_opt = False

                    if tid in self.last_optimal_bboxes:
                        if compute_bbox_iou(cfb, self.last_optimal_bboxes[tid]) > 0.85:
                            alerts.append("CHANGE POSE"); is_opt = False

                    if tid not in self.capture_buffers:
                        self.capture_buffers[tid] = []
                    reason = "Auto-Framing"
                    if req_smile and req_thumbs:
                        if is_smiling and is_thumbs: reason = "Smile & Thumbs Up"
                        elif is_smiling: reason = "Smile"
                        elif is_thumbs:  reason = "Thumbs Up"
                    elif req_smile:  reason = "Smile"
                    elif req_thumbs: reason = "Thumbs Up"

                    self.capture_buffers[tid].append({
                        "crop":rc, "fb":cfb, "is_optimal":is_opt,
                        "comp_score":comp, "smile_score":s_score if is_smiling else 0.0,
                        "blur_score":blur, "reason":reason
                    })
                    if len(self.capture_buffers[tid]) > 10:
                        self.capture_buffers[tid].pop(0)

                    buf = self.capture_buffers[tid]
                    with self.lock:
                        cd2 = self.cooldown_frames
                    if len(buf) >= 5 and cd2 == 0:
                        recent = buf[-5:]
                        if sum(1 for b in recent if b["is_optimal"]) >= 4 and recent[-1]["is_optimal"]:
                            best = max(recent, key=lambda x: x["comp_score"]+x["smile_score"]*0.5+x["blur_score"]*0.001)
                            alerts.append("CAPTURED")
                            optimal_found=True; captured_id=tid
                            captured_crop=best["crop"]; captured_reason=best["reason"]
                            self.last_optimal_bboxes[tid] = best["fb"]

                    # ── draw overlays ─────────────────────────────────────
                    ov = display.copy()

                    # Bbox-derived ellipse — stable source, Kalman smooths motion
                    ecx  = (x1 + x2) / 2.0
                    ecy  = (y1 + y2) / 2.0
                    e_rx = (x2 - x1) * 0.38
                    e_ry = (y2 - y1) * 0.52
                    if tid not in self.ellipse_kfs:
                        self.ellipse_kfs[tid] = EllipseKF()
                    fcx,fcy,fMA,fma,fang = self.ellipse_kfs[tid].update([ecx, ecy, e_rx*2, e_ry*2, 0.0])
                    ax = (max(10, int(fMA/2)), max(10, int(fma/2)))
                    cv2.ellipse(ov,(int(fcx),int(fcy)),ax,fang,0,360,(235,206,135),-1)
                    cv2.addWeighted(ov,0.25,display,0.75,0,display)
                    cv2.ellipse(display,(int(fcx),int(fcy)),ax,fang,0,360,(235,206,135),2)


                    if is_smiling:
                        cv2.putText(display,"SMILING",(int(x1),max(30,int(y1)-10)),
                                    cv2.FONT_HERSHEY_DUPLEX,1.0,(0,255,255),2)
                        if face_lms:
                            for lm in face_lms:
                                cv2.circle(display,(int(lm.x*(x2-x1)+x1),int(lm.y*(y2-y1)+y1)),1,(203,192,255),-1)
                    if is_thumbs:
                        cv2.putText(display,"THUMBS UP",(int(x1),max(65,int(y1)-45)),
                                    cv2.FONT_HERSHEY_DUPLEX,1.0,(100,100,255),2)
                        if hand_lms:
                            pts = np.array([[int(lm.x*(x2-x1)+x1),int(lm.y*(y2-y1)+y1)] for lm in hand_lms],np.int32)
                            cv2.polylines(display,[pts.reshape((-1,1,2))],True,(203,192,255),2)
                            for pt in pts: cv2.circle(display,tuple(pt),4,(203,192,255),-1)

                    if is_frontal:
                        bc = (0,255,0) if is_opt else ((0,255,255) if ((req_smile and is_smiling) or (req_thumbs and is_thumbs)) else (0,0,255))
                        cv2.rectangle(display,(fb[0],fb[1]),(fb[2],fb[3]),bc,3)
                        cw2,ch2 = max(1,fb[2]-fb[0])//3, max(1,fb[3]-fb[1])//3
                        for n in (1,2):
                            cv2.line(display,(fb[0]+n*cw2,fb[1]),(fb[0]+n*cw2,fb[3]),bc,1)
                            cv2.line(display,(fb[0],fb[1]+n*ch2),(fb[2],fb[1]+n*ch2),bc,1)
                        cv2.putText(display,f"Score:{comp:.2f}",(max(5,fb[0]),min(fb[3]+20,h-5)),
                                    cv2.FONT_HERSHEY_SIMPLEX,0.5,bc,1)

                    th_a = len(alerts)*22
                    yo   = fb[1]-10 if fb[1]-th_a>=10 else max(22,fb[1]+22)
                    ys   = -22       if fb[1]-th_a>=10 else 22
                    for al in reversed(alerts):
                        col = (0,255,0) if "CAPTURED" in al else ((0,165,255) if ("CHANGE" in al or "MOVE" in al) else (80,80,255))
                        (tw,tth),_ = cv2.getTextSize(al,cv2.FONT_HERSHEY_SIMPLEX,0.55,1)
                        tx = max(5,min(fb[0]+4,w-tw-5))
                        if yo<tth+5: yo=tth+5
                        if yo>h-5: break
                        cv2.rectangle(display,(tx,yo-tth-3),(tx+tw+3,yo+3),(0,0,0),-1)
                        cv2.putText(display,al,(tx,yo),cv2.FONT_HERSHEY_SIMPLEX,0.55,col,1)
                        yo += ys

            # encode frame
            _, jpeg = cv2.imencode('.jpg', display, [cv2.IMWRITE_JPEG_QUALITY, 80])
            with self.lock:
                self.latest_jpeg = jpeg.tobytes()
                self.status = {
                    "subjects": live_ids, "cooldown": self.cooldown_frames,
                    "require_smile": self.require_smile,
                    "require_thumbs": self.require_thumbs,
                    "captures": self.captured_count,
                }

            if optimal_found and captured_crop is not None and captured_crop.size > 0:
                self._add_to_queue(captured_crop, captured_id, captured_reason)
                with self.lock:
                    self.cooldown_frames = 45
                    self.capture_buffers[captured_id].clear()

    def _add_to_queue(self, frame, tid, reason):
        ts = int(time.time() * 1000)
        filename = f"cap_{tid}_{ts}.jpg"
        filepath = os.path.join(CAPTURE_DIR, filename)
        cv2.imwrite(filepath, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])

        thumb = cv2.resize(frame, (240, 180))
        _, buf = cv2.imencode('.jpg', thumb, [cv2.IMWRITE_JPEG_QUALITY, 82])
        b64 = base64.b64encode(buf).decode()

        with self.lock:
            self.captured_count += 1
            item = {
                "id": self.captured_count, "track": tid,
                "time": time.strftime('%H:%M:%S'), "reason": reason,
                "thumb": b64, "filename": filename,
                "upload_status": "pending",  # pending | uploading | uploaded | failed
            }
            self.queue.insert(0, item)
            if len(self.queue) > 50:
                self.queue = self.queue[:50]
            # Auto-upload if enabled
            if self.auto_upload:
                threading.Thread(target=self._do_upload, args=(item,), daemon=True).start()

    def _do_upload(self, item):
        """Upload image to cloud lab_api.py."""
        item_id = item["id"]
        # Mark uploading
        with self.lock:
            for q in self.queue:
                if q["id"] == item_id:
                    q["upload_status"] = "uploading"
                    filename = q.get("filename", "")
                    break
        
        filepath = os.path.join(CAPTURE_DIR, filename)
        try:
            if not os.path.exists(filepath):
                raise Exception("File not found on disk")
                
            with open(filepath, "rb") as f:
                r = requests.post(f"{CLOUD_API}/upload", 
                                  files={"file": (filename, f, "image/jpeg")}, 
                                  data={"event": self.event_id, "photographer": self.photographer_id})
                
            if r.status_code == 200:
                with self.lock:
                    for q in self.queue:
                        if q["id"] == item_id:
                            q["upload_status"] = "uploaded"
                            if self.auto_delete and os.path.exists(filepath):
                                os.remove(filepath)
                            break
            else:
                raise Exception(f"Server returned {r.status_code}: {r.text}")
        except Exception as e:
            print(f"[UPLOAD] Failed for item {item_id}: {e}")
            with self.lock:
                for q in self.queue:
                    if q["id"] == item_id:
                        q["upload_status"] = "failed"
                        break

    def stop(self):
        self._running = False
        self.cap.release()


# ─── Flask ────────────────────────────────────────────────────────────────────

app    = Flask(__name__)
app.secret_key = os.environ.get('REC_SECRET', 'rec-dev-secret-change-in-prod')
app.permanent_session_lifetime = timedelta(hours=12)
engine = None

# ── Auth ──────────────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated


@app.route('/login', methods=['GET', 'POST'])
def login_page():
    error = None
    if request.method == 'POST':
        u = request.form.get('username', '').strip()
        p = request.form.get('password', '')
        
        try:
            r = requests.post(f"{CLOUD_API}/login", json={"username": u, "password": p})
            data = r.json()
            if r.status_code == 200 and "token" in data:
                if data.get("role") in ["admin", "photographer"]:
                    session.permanent = True
                    session['logged_in'] = True
                    session['username']  = data.get('username', u)
                    session['role']      = data.get('role')
                    session['token']     = data.get('token')
                    return redirect(url_for('setup_page'))
                else:
                    error = 'Unauthorized role. Only admins and photographers can access the capture dashboard.'
            else:
                error = data.get("error", "Invalid credentials.")
        except Exception as e:
            error = f"Could not connect to Cloud API. {e}"

    html_path = os.path.join(os.path.dirname(__file__), 'login.html')
    with open(html_path, 'r') as f:
        content = f.read()
    if error:
        content = content.replace('<!--ERROR-->', f'<div class="error">{error}</div>')
    resp = Response(content, mimetype='text/html')
    resp.headers['Cache-Control'] = 'no-store'
    return resp


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))


@app.route('/favicon.ico')
def favicon():
    return Response(status=204)

@app.route('/setup', methods=['GET', 'POST'])
@login_required
def setup_page():
    if request.method == 'POST':
        event_id = request.form.get('event_id', '').strip()
        if event_id:
            session['event_id'] = event_id
            if engine is not None:
                with engine.lock:
                    engine.event_id = event_id
                    engine.photographer_id = session.get('username', 'Unknown')
            return redirect(url_for('select_mode'))
            
    events = []
    try:
        r = requests.get(f"{CLOUD_API}/admin/events")
        if r.status_code == 200: events = r.json()
    except: pass
        
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <title>Select Event — REC</title>
      <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet" />
      <style>
        *, *::before, *::after {{ box-sizing: border-box; }}
        body {{ background: #0a0a0a; color: #e0e0e0; font-family: 'Inter', sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
        .card {{ background: #111; padding: 32px; border: 1px solid #1e1e1e; border-radius: 8px; width: 340px; display: flex; flex-direction: column; gap: 24px; }}
        h2 {{ margin: 0; font-size: 18px; font-weight: 600; letter-spacing: .05em; }}
        .field {{ display: flex; flex-direction: column; gap: 8px; }}
        .field label {{ font-size: 10px; color: #555; text-transform: uppercase; letter-spacing: .1em; }}
        select, input, button {{ width: 100%; padding: 12px; background: #0a0a0a; border: 1px solid #1e1e1e; color: white; border-radius: 5px; font-family: inherit; font-size: 13px; outline: none; }}
        input:focus {{ border-color: #333; }}
        button {{ background: #fff; color: #000; font-weight: 600; cursor: pointer; margin-top: 8px; transition: background .2s; border: none; }}
        button:hover {{ background: #e0e0e0; }}
        .logout {{ font-size: 11px; color: #555; text-align: center; text-decoration: none; margin-top: -8px; }}
        .logout:hover {{ color: #e0e0e0; }}
      </style>
    </head>
    <body>
      <div class="card">
        <h2>Workspace Setup</h2>
        <form method="POST" style="display:flex; flex-direction:column; gap:16px;">
          <div class="field">
            <label>Active Event ID</label>
            <input list="events" name="event_id" placeholder="Select or type new..." required autocomplete="off" />
            <datalist id="events">
              {''.join([f'<option value="{e["id"]}">{e["name"]} ({e["photographer_id"]})</option>' for e in events])}
            </datalist>
          </div>
          <button type="submit">Launch Dashboard</button>
          <a href="/logout" class="logout">Sign out</a>
        </form>
      </div>
    </body>
    </html>
    """
    return Response(html, mimetype='text/html')

@app.route('/select-mode')
@login_required
def select_mode():
    if not session.get('event_id'):
        return redirect(url_for('setup_page'))
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <title>Select Mode — REC</title>
      <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet" />
      <style>
        *, *::before, *::after {{ box-sizing: border-box; }}
        body {{ background: #0a0a0a; color: #e0e0e0; font-family: 'Inter', sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
        .card {{ background: #111; padding: 40px; border: 1px solid #1e1e1e; border-radius: 8px; width: 600px; display: flex; flex-direction: column; gap: 24px; text-align: center; }}
        h2 {{ margin: 0; font-size: 22px; font-weight: 600; letter-spacing: .05em; }}
        .modes {{ display: flex; gap: 20px; margin-top: 20px; }}
        .mode-btn {{ flex: 1; padding: 40px 20px; background: #0a0a0a; border: 2px solid #333; color: white; border-radius: 8px; cursor: pointer; transition: all .2s; text-decoration: none; display: flex; flex-direction: column; gap: 10px; align-items: center; justify-content: center; }}
        .mode-btn:hover {{ border-color: #fff; background: #1a1a1a; transform: translateY(-2px); }}
        .mode-title {{ font-size: 18px; font-weight: 600; }}
        .mode-desc {{ font-size: 12px; color: #888; }}
        .header-meta {{ font-size: 12px; color: #666; margin-top: -15px; }}
      </style>
    </head>
    <body>
      <div class="card">
        <h2>Dashboard Mode</h2>
        <div class="header-meta">Event: <strong>{session.get('event_id')}</strong></div>
        <div class="modes">
          <div onclick="window.location.href='/live-capture'" class="mode-btn">
            <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="margin-bottom: 10px;">
              <path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"></path>
              <circle cx="12" cy="13" r="3"></circle>
            </svg>
            <div class="mode-title">Live Auto Capture</div>
          </div>
          <div onclick="window.location.href='/upload-dashboard'" class="mode-btn">
            <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="margin-bottom: 10px;">
              <path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z"></path>
              <path d="M12 16v-9"></path>
              <path d="m8 11 4-4 4 4"></path>
            </svg>
            <div class="mode-title">Upload & Manage</div>
          </div>
        </div>
        <a href="/setup" style="color: #555; text-decoration: none; font-size: 12px; margin-top: 20px;">← Change Event</a>
      </div>
    </body>
    </html>
    """
    return Response(html, mimetype='text/html')

@app.route('/upload-dashboard')
@login_required
def upload_dashboard():
    if not session.get('event_id'):
        return redirect(url_for('setup_page'))
    
    html_path = os.path.join(os.path.dirname(__file__), 'upload_dashboard.html')
    with open(html_path, 'r') as f:
        content = f.read()
    
    content = content.replace("{{EVENT_ID}}", session.get('event_id'))
    content = content.replace("{{CLOUD_API}}", CLOUD_API)
    content = content.replace("{{USERNAME}}", session.get('username'))
    
    resp = Response(content, mimetype='text/html')
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    return resp

@app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login_page'))
    if not session.get('event_id'):
        return redirect(url_for('setup_page'))
    return redirect(url_for('select_mode'))

@app.route('/live-capture')
@login_required
def live_capture():
    global engine
    if not session.get('event_id'):
        return redirect(url_for('setup_page'))
        
    if engine is None:
        print("\n[INFO] Initializing Live Camera & AI Models...\n")
        engine = CaptureEngine()
        
    with engine.lock:
        engine.event_id = session.get('event_id')
        engine.photographer_id = session.get('username')

    """Serve dashboard HTML with no-cache so browser always gets latest version."""
    html_path = os.path.join(os.path.dirname(__file__), 'web_dashboard.html')
    with open(html_path, 'r') as f:
        content = f.read()
    resp = Response(content, mimetype='text/html')
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    return resp


@app.route('/api/frame')
@login_required
def api_frame():
    """Single JPEG frame — polled by JS canvas loop."""
    if engine is None or not engine.latest_jpeg:
        blank = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(blank, "Loading models...", (180, 240),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (80, 80, 80), 2)
        _, buf = cv2.imencode('.jpg', blank)
        data = buf.tobytes()
    else:
        with engine.lock:
            data = engine.latest_jpeg
    resp = Response(data, mimetype='image/jpeg')
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    return resp


@app.route('/api/status')
@login_required
def api_status():
    if engine is None:
        return jsonify({"subjects":[],"cooldown":0,"require_smile":False,
                        "require_thumbs":False,"captures":0,"loading":True})
    with engine.lock:
        return jsonify(engine.status)


@app.route('/api/queue')
@login_required
def api_queue():
    if engine is None:
        return jsonify([])
    with engine.lock:
        return jsonify(engine.queue)


@app.route('/api/settings', methods=['POST'])
@login_required
def api_settings():
    data = request.get_json(silent=True) or {}
    if engine is not None:
        with engine.lock:
            if 'require_smile'  in data: engine.require_smile  = bool(data['require_smile'])
            if 'require_thumbs' in data: engine.require_thumbs = bool(data['require_thumbs'])
    return jsonify({"ok": True})


@app.route('/captures/<path:filename>')
@login_required
def serve_capture(filename):
    """Serve a full-resolution capture file."""
    return send_from_directory(CAPTURE_DIR, filename)


@app.route('/api/clear-queue', methods=['POST'])
@login_required
def api_clear():
    if engine is not None:
        with engine.lock:
            # Delete files from disk as well
            for item in engine.queue:
                try:
                    fp = os.path.join(CAPTURE_DIR, item.get('filename', ''))
                    if os.path.exists(fp):
                        os.remove(fp)
                except Exception:
                    pass
            engine.queue.clear()
    return jsonify({"ok": True})



@app.route('/api/upload-settings', methods=['GET', 'POST'])
@login_required
def api_upload_settings():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        if engine is not None:
            with engine.lock:
                if 'auto_upload' in data: engine.auto_upload = bool(data['auto_upload'])
                if 'auto_delete' in data: engine.auto_delete = bool(data['auto_delete'])
                if 'event_id' in data: 
                    engine.event_id = str(data['event_id']).strip() or "EVT-UNKNOWN"
                    session['event_id'] = engine.event_id
                engine.photographer_id = session.get('username', 'Unknown')
        return jsonify({"ok": True})
    # GET
    if engine is None:
        return jsonify({"auto_upload": False, "auto_delete": False, "event_id": session.get('event_id', 'EVT-UNKNOWN')})
    with engine.lock:
        return jsonify({"auto_upload": engine.auto_upload, "auto_delete": engine.auto_delete, "event_id": engine.event_id})

@app.route('/api/events')
@login_required
def api_events():
    try:
        r = requests.get(f"{CLOUD_API}/admin/events")
        return jsonify(r.json() if r.status_code == 200 else [])
    except Exception:
        return jsonify([])


@app.route('/api/upload/<int:item_id>', methods=['POST'])
@login_required
def api_upload_item(item_id):
    """Trigger upload for a single item by id."""
    if engine is None:
        return jsonify({"ok": False, "error": "engine not ready"})
    target = None
    with engine.lock:
        for q in engine.queue:
            if q["id"] == item_id and q["upload_status"] == "pending":
                target = q
                break
    if target is None:
        return jsonify({"ok": False, "error": "item not found or not pending"})
    import threading as _t
    _t.Thread(target=engine._do_upload, args=(target,), daemon=True).start()
    return jsonify({"ok": True})


@app.route('/api/upload-all', methods=['POST'])
@login_required
def api_upload_all():
    """Trigger upload for all pending items."""
    if engine is None:
        return jsonify({"ok": False})
    import threading as _t
    with engine.lock:
        pending = [q for q in engine.queue if q["upload_status"] == "pending"]
    for item in pending:
        _t.Thread(target=engine._do_upload, args=(item,), daemon=True).start()
    return jsonify({"ok": True, "queued": len(pending)})


if __name__ == '__main__':
    import threading as _t
    import signal

    _t.Thread(
        target=lambda: app.run(host='0.0.0.0', port=8080, threaded=True, use_reloader=False),
        daemon=True
    ).start()
    print("\n  http://localhost:8080\n")

    def _shutdown(sig, frame):
        print("\nShutting down...")
        if engine is not None:
            engine.stop()
        os._exit(0)   # clean exit, avoids OpenCV/MediaPipe segfault on signal

    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # Park main thread
    signal.pause()
