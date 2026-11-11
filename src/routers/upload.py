from __future__ import annotations

import asyncio
import os
import sqlite3
import uuid
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from src.db import get_db
from src.storage import StorageConfigurationError, delete_object, upload_object

router = APIRouter()
AUDIO_DIR = "src/static/audio"
MAX_AUDIO_SIZE = 50 * 1024 * 1024
ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a"}


class NameUpdate(BaseModel):
    display_name: str


class VolumeUpdate(BaseModel):
    default_volume: float


@router.post("/api/upload")
async def upload_file(
    files: List[UploadFile] = File(...),
    category: str = Form(...),
    uploader_name: str = Form("Host"),
    db: sqlite3.Connection = Depends(get_db),
):
    if category not in {"BGM", "SFX"}:
        raise HTTPException(status_code=400, detail="Category must be BGM or SFX.")
    if not files:
        raise HTTPException(status_code=400, detail="Select at least one audio file.")

    cursor = db.cursor()
    saved_files = []
    uploaded_keys = []
    try:
        for file in files:
            original_name = os.path.basename(file.filename or "").strip()
            extension = os.path.splitext(original_name)[1].lower()
            if not original_name or extension not in ALLOWED_AUDIO_EXTENSIONS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported audio file: {original_name or 'unnamed file'}. Use MP3, WAV, OGG, or M4A.",
                )

            content = await file.read(MAX_AUDIO_SIZE + 1)
            if len(content) > MAX_AUDIO_SIZE:
                raise HTTPException(status_code=413, detail="Each audio file must be 50 MB or smaller.")
            if not content:
                raise HTTPException(status_code=400, detail=f"{original_name} is empty.")

            object_key = f"{uuid.uuid4().hex}{extension}"
            public_url = await asyncio.to_thread(
                upload_object,
                object_key,
                content,
                file.content_type or "application/octet-stream",
            )
            uploaded_keys.append(object_key)
            cursor.execute(
                "INSERT INTO audio_files (file_path, display_name, category, uploader_name, storage_type) VALUES (?, ?, ?, ?, 'supabase')",
                (object_key, original_name, category, uploader_name.strip()[:80] or "Host"),
            )
            saved_files.append({"filename": object_key, "display_name": original_name, "url": public_url})

        db.commit()
    except StorageConfigurationError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except HTTPException:
        db.rollback()
        for object_key in uploaded_keys:
            try:
                await asyncio.to_thread(delete_object, object_key)
            except Exception:
                pass
        raise
    except Exception as exc:
        db.rollback()
        for object_key in uploaded_keys:
            try:
                await asyncio.to_thread(delete_object, object_key)
            except Exception:
                pass
        raise HTTPException(status_code=502, detail="Could not save audio to Supabase Storage.") from exc
    finally:
        for file in files:
            await file.close()

    return {"filenames": [f["filename"] for f in saved_files], "files": saved_files, "status": "uploaded_multiple"}


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
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Audio file not found.")
    db.commit()
    return {"status": "success"}


@router.put("/api/audio_files/{file_id}/volume")
async def update_volume(file_id: int, update: VolumeUpdate, db: sqlite3.Connection = Depends(get_db)):
    if not 0 <= update.default_volume <= 1:
        raise HTTPException(status_code=400, detail="Volume must be between 0 and 1.")
    cursor = db.cursor()
    cursor.execute("UPDATE audio_files SET default_volume = ? WHERE id = ?", (update.default_volume, file_id))
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Audio file not found.")
    db.commit()
    return {"status": "success"}


@router.delete("/api/audio_files/{file_id}")
async def delete_file(file_id: int, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT file_path, storage_type FROM audio_files WHERE id = ?", (file_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="File not found")

    if row["storage_type"] == "supabase":
        try:
            await asyncio.to_thread(delete_object, row["file_path"])
        except StorageConfigurationError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Could not delete audio from Supabase Storage.") from exc
    else:
        file_path = os.path.join(AUDIO_DIR, os.path.basename(row["file_path"]))
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except OSError:
            pass

    cursor.execute("DELETE FROM audio_files WHERE id = ?", (file_id,))
    db.commit()
    return {"status": "success"}
