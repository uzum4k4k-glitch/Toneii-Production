from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from src.routers import websocket, upload
from src.db import init_db
import os
import sqlite3

init_db()

def sync_audio_files():
    conn = sqlite3.connect("toneii.db")
    cursor = conn.cursor()
    audio_dir = "src/static/audio"
    os.makedirs(audio_dir, exist_ok=True)
    for filename in os.listdir(audio_dir):
        if filename.endswith(('.mp3', '.wav', '.ogg', '.m4a')):
            cursor.execute("SELECT id FROM audio_files WHERE file_path = ?", (filename,))
            if not cursor.fetchone():
                cat = "BGM" if filename.lower().startswith("bgm_") else "SFX"
                cursor.execute(
                    "INSERT INTO audio_files (file_path, display_name, category, uploader_name) VALUES (?, ?, ?, ?)",
                    (filename, filename, cat, "Host")
                )
    conn.commit()
    conn.close()

sync_audio_files()

app = FastAPI(title="Toneii - DnD Edition", description="Real-time RPG Soundboard")
app.include_router(websocket.router)
app.include_router(upload.router)

os.makedirs("src/static/audio", exist_ok=True)
app.mount("/static", StaticFiles(directory="src/static"), name="static")

@app.get("/")
async def root():
    return {"message": "Welcome to Toneii API. Please visit /static/host.html or /static/guest.html"}
