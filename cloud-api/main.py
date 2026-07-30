from fastapi import FastAPI

app = FastAPI(title="REC Cloud API")

@app.get("/")
def read_root():
    return {"status": "ok"}
