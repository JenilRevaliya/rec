from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI(title="REC Cloud API")

Instrumentator().instrument(app).expose(app)

@app.get("/")
def read_root():
    return {"status": "ok"}
