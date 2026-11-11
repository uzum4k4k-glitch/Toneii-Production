from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from src.routers import websocket, upload
from src.db import init_db, DATABASE_URL
from src.storage import public_object_url, StorageConfigurationError
import os
import sqlite3

init_db()


def sync_audio_files():
    conn = sqlite3.connect(DATABASE_URL)
    cursor = conn.cursor()
    audio_dir = "src/static/audio"
    os.makedirs(audio_dir, exist_ok=True)
    for filename in os.listdir(audio_dir):
        if filename.lower().endswith((".mp3", ".wav", ".ogg", ".m4a")):
            cursor.execute("SELECT id FROM audio_files WHERE file_path = ?", (filename,))
            if not cursor.fetchone():
                cat = "BGM" if filename.lower().startswith("bgm_") else "SFX"
                cursor.execute(
                    "INSERT INTO audio_files (file_path, display_name, category, uploader_name, storage_type) VALUES (?, ?, ?, ?, 'local')",
                    (filename, filename, cat, "Host"),
                )
    conn.commit()
    conn.close()


sync_audio_files()

app = FastAPI(title="Toneii - DnD Edition", description="Real-time RPG Soundboard")
app.include_router(websocket.router)
app.include_router(upload.router)

os.makedirs("src/static/audio", exist_ok=True)


@app.get("/static/audio/{filename}", include_in_schema=False)
async def serve_audio_file(filename: str):
    # The current dashboards request this path. Supabase-backed records redirect
    # their existing player URLs to the permanent public object URL.
    filename = os.path.basename(filename)
    conn = sqlite3.connect(DATABASE_URL)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT file_path, storage_type FROM audio_files WHERE file_path = ? LIMIT 1",
            (filename,),
        ).fetchone()
    finally:
        conn.close()

    if row and row["storage_type"] == "supabase":
        try:
            return RedirectResponse(public_object_url(row["file_path"]), status_code=307)
        except StorageConfigurationError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    local_path = os.path.join("src", "static", "audio", filename)
    if os.path.isfile(local_path):
        return FileResponse(local_path)
    raise HTTPException(status_code=404, detail="Audio file not found")


app.mount("/static", StaticFiles(directory="src/static"), name="static")


@app.get("/")
async def root():
    return {"message": "Welcome to Toneii API. Please visit /static/host.html or /static/guest.html"}
