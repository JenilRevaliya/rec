import cv2
import numpy as np
import insightface
from insightface.app import FaceAnalysis
from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uuid
import os
import json

from sqlalchemy import create_engine, Column, Integer, String, JSON
from sqlalchemy.orm import declarative_base, sessionmaker

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

app = FastAPI(title="REC Local Lab API")

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = create_engine("postgresql://rec:change_me_in_production@127.0.0.1:5433/rec")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "rec_users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)
    role = Column(String)

class Event(Base):
    __tablename__ = "rec_events"
    id = Column(String, primary_key=True, index=True)
    name = Column(String)
    photographer_id = Column(String)
    is_private = Column(Integer, default=0) # 0=Public, 1=Private

class ShareLink(Base):
    __tablename__ = "rec_share_links"
    token = Column(String, primary_key=True, index=True)
    event_id = Column(String, index=True)
    max_opens = Column(Integer, default=1)
    opens = Column(Integer, default=0)

class Photo(Base):
    __tablename__ = "rec_photos"
    id = Column(String, primary_key=True, index=True)
    event_id = Column(String)
    photographer_id = Column(String)
    url = Column(String)
    faces = Column(JSON)
    faces_detected = Column(Integer)

Base.metadata.create_all(bind=engine)

def seed_db():
    db = SessionLocal()
    if not db.query(User).filter(User.username == "admin").first():
        db.add(User(username="admin", password="password", role="admin"))
    if not db.query(User).filter(User.username == "photographer1").first():
        db.add(User(username="photographer1", password="password", role="photographer"))
    if not db.query(User).filter(User.username == "user1").first():
        db.add(User(username="user1", password="password", role="user"))
    db.commit()
    db.close()

seed_db()

print("Initializing InsightFace for Lab API...")
face_app = FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider'])
face_app.prepare(ctx_id=0, det_size=(640, 640))
print("Lab API Model loaded!")

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/login")
@limiter.limit("10/minute")
def login(request: Request, req: LoginRequest):
    db = SessionLocal()
    user = db.query(User).filter(User.username == req.username, User.password == req.password).first()
    db.close()
    if not user:
        return {"error": "Invalid credentials"}
    return {"token": f"mock_token_{user.id}", "role": user.role, "username": user.username}

@app.get("/admin/users")
def get_users():
    db = SessionLocal()
    users = db.query(User).all()
    db.close()
    return [{"id": u.id, "username": u.username, "role": u.role} for u in users]

@app.post("/admin/users")
def add_user(req: dict):
    db = SessionLocal()
    new_user = User(username=req["username"], password=req["password"], role=req["role"])
    db.add(new_user)
    db.commit()
    db.close()
    return {"status": "success"}

@app.get("/admin/events")
def get_events():
    db = SessionLocal()
    events = db.query(Event).all()
    db.close()
    return [{"id": e.id, "name": e.name, "photographer_id": e.photographer_id} for e in events]

@app.get("/admin/stats")
def get_stats():
    db = SessionLocal()
    users_count = db.query(User).count()
    photos_count = db.query(Photo).count()
    db.close()
    
    # Calculate live storage size
    total_size = 0
    if os.path.exists("static"):
        for f in os.listdir("static"):
            fp = os.path.join("static", f)
            if os.path.isfile(fp):
                total_size += os.path.getsize(fp)
                
    if total_size > 1073741824:
        storage_str = f"{total_size / 1073741824:.2f} GB"
    elif total_size > 1048576:
        storage_str = f"{total_size / 1048576:.2f} MB"
    else:
        storage_str = f"{total_size / 1024:.2f} KB"
        
    return {"users": users_count, "photos": photos_count, "storage": storage_str}

class GenerateLinkRequest(BaseModel):
    event_id: str
    count: int = 1
    max_opens: int = 5

@app.post("/links/generate")
def generate_links(req: GenerateLinkRequest):
    db = SessionLocal()
    event = db.query(Event).filter(Event.id == req.event_id).first()
    if event and event.is_private == 0:
        event.is_private = 1
        
    links = []
    for _ in range(req.count):
        token = uuid.uuid4().hex[:12]
        link = ShareLink(token=token, event_id=req.event_id, max_opens=req.max_opens)
        db.add(link)
        links.append(token)
        
    db.commit()
    db.close()
    return {"tokens": links}

@app.get("/links/validate/{token}")
def validate_link(token: str):
    db = SessionLocal()
    link = db.query(ShareLink).filter(ShareLink.token == token).first()
    if not link:
        db.close()
        return {"valid": False, "error": "Invalid token"}
        
    if link.opens >= link.max_opens:
        db.close()
        return {"valid": False, "error": "Link has expired (max opens reached)"}
        
    db.close()
    return {"valid": True, "event_id": link.event_id, "opens": link.opens, "max_opens": link.max_opens}

@app.get("/photos/{event_id}")
def get_photos(event_id: str):
    db = SessionLocal()
    photos = db.query(Photo).filter(Photo.event_id == event_id).order_by(Photo.id.desc()).all()
    db.close()
    return [{"id": p.id, "url": p.url, "faces_detected": p.faces_detected} for p in photos]

@app.post("/upload")
@limiter.limit("50/minute")
async def upload_photo(request: Request, file: UploadFile = File(...), event: str = Form("EVT-UNKNOWN"), photographer: str = Form("Unknown")):
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    if img is None:
        return {"error": "Invalid image format format"}
        
    try:
        faces = face_app.get(img)
    except Exception as e:
        print(f"Error extracting faces: {e}")
        faces = []
        
    photo_id = str(uuid.uuid4())
    cv2.imwrite(f"static/{photo_id}.jpg", img)
    
    face_data = []
    for face in faces:
        face_data.append({
            "bbox": face.bbox.tolist(),
            "embedding": face.embedding.tolist(),
            "gender": "Male" if face.gender == 1 else "Female",
            "age": int(face.age)
        })
        
    db = SessionLocal()
    
    # Save event if new
    existing_event = db.query(Event).filter(Event.id == event).first()
    if not existing_event:
        db.add(Event(id=event, name=f"Event {event}", photographer_id=photographer))
        
    photo = Photo(
        id=photo_id,
        event_id=event,
        photographer_id=photographer,
        url=f"http://localhost:8001/static/{photo_id}.jpg",
        faces=face_data,
        faces_detected=len(faces)
    )
    db.add(photo)
    db.commit()
    db.close()
    
    return {
        "photo_id": photo_id,
        "faces_detected": len(faces),
        "url": f"http://localhost:8001/static/{photo_id}.jpg"
    }

@app.post("/match")
@limiter.limit("20/minute")
async def match_webcam(request: Request, file: UploadFile = File(...)):
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    faces = face_app.get(img)
    if not faces:
        return {"error": "No face detected in subject image"}
        
    subject_embeddings = [np.array(f.embedding) for f in faces]
    matches = []
    
    db = SessionLocal()
    all_photos = db.query(Photo).all()
    
    for p in all_photos:
        matched = False
        best_score = 0
        for target_face in p.faces:
            target_emb = np.array(target_face["embedding"])
            for subj_emb in subject_embeddings:
                score = cosine_similarity(subj_emb, target_emb)
                if score > best_score:
                    best_score = score
                if score > 0.45:
                    matched = True
                
        if matched:
            matches.append({
                "photo_id": p.id,
                "score": float(best_score),
                "event": p.event_id,
                "photographer": p.photographer_id,
                "url": p.url
            })
            
    db.close()
    return {"matches": matches}

@app.post("/links/consume/{token}")
def consume_link(token: str):
    db = SessionLocal()
    link = db.query(ShareLink).filter(ShareLink.token == token).first()
    if link and link.opens < link.max_opens:
        link.opens += 1
        db.commit()
    db.close()
    return {"status": "consumed"}

@app.post("/reset")
def reset_lab():
    db = SessionLocal()
    db.query(Photo).delete()
    db.query(Event).delete()
    db.commit()
    db.close()
    return {"status": "cleared"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
