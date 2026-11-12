from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
import os
import shutil
import sqlite3
from typing import List
from src.db import get_db
from pydantic import BaseModel

router = APIRouter()
AUDIO_DIR = "src/static/audio"

class NameUpdate(BaseModel):
    display_name: str

class VolumeUpdate(BaseModel):
    default_volume: float

@router.post("/api/upload")
async def upload_file(
    files: List[UploadFile] = File(...), 
    category: str = Form(...),
    uploader_name: str = Form("Host"),
    db: sqlite3.Connection = Depends(get_db)
):
    os.makedirs(AUDIO_DIR, exist_ok=True)
    cursor = db.cursor()
    saved_files = []
    
    for file in files:
        safe_filename = os.path.basename(file.filename)
        file_path = os.path.join(AUDIO_DIR, safe_filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        cursor.execute(
            "INSERT INTO audio_files (file_path, display_name, category, uploader_name) VALUES (?, ?, ?, ?)",
            (safe_filename, safe_filename, category, uploader_name)
        )
        saved_files.append(safe_filename)
        
    db.commit()
    return {"filenames": saved_files, "status": "uploaded_multiple"}

@router.get("/api/audio_files")
async def list_files(db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM audio_files ORDER BY id DESC")
    files = [dict(row) for row in cursor.fetchall()]
    return {"files": files}

@router.put("/api/audio_files/{file_id}/name")
async def update_name(file_id: int, update: NameUpdate, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("UPDATE audio_files SET display_name = ? WHERE id = ?", (update.display_name, file_id))
    db.commit()
    return {"status": "success"}

@router.put("/api/audio_files/{file_id}/volume")
async def update_volume(file_id: int, update: VolumeUpdate, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("UPDATE audio_files SET default_volume = ? WHERE id = ?", (update.default_volume, file_id))
    db.commit()
    return {"status": "success"}

@router.delete("/api/audio_files/{file_id}")
async def delete_file(file_id: int, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT file_path FROM audio_files WHERE id = ?", (file_id,))
    row = cursor.fetchone()
    if row:
        file_path = os.path.join(AUDIO_DIR, row['file_path'])
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except OSError:
            pass
        cursor.execute("DELETE FROM audio_files WHERE id = ?", (file_id,))
        db.commit()
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="File not found")
