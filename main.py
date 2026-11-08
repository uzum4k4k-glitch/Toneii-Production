from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from src.routers import websocket, upload
from src.db import init_db
import os

init_db()
app = FastAPI(title="Toneii - DnD Edition", description="Real-time RPG Soundboard")
app.include_router(websocket.router)
app.include_router(upload.router)

os.makedirs("src/static/audio", exist_ok=True)
app.mount("/static", StaticFiles(directory="src/static"), name="static")

@app.get("/")
async def root():
    return {"message": "Welcome to Toneii API. Please visit /static/host.html or /static/guest.html"}
