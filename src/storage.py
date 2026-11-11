from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


class StorageConfigurationError(RuntimeError):
    pass


def _config() -> tuple[str, str, str]:
    base_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    bucket = os.getenv("SUPABASE_STORAGE_BUCKET", "toneii-audio").strip()
    if not base_url or not service_key or not bucket:
        raise StorageConfigurationError(
            "Set SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, and SUPABASE_STORAGE_BUCKET."
        )
    return base_url, service_key, bucket


def _object_url(base_url: str, bucket: str, object_key: str) -> str:
    return f"{base_url}/storage/v1/object/{quote(bucket, safe='')}/{quote(object_key, safe='/')}"


def public_object_url(object_key: str) -> str:
    base_url, _, bucket = _config()
    return (
        f"{base_url}/storage/v1/object/public/"
        f"{quote(bucket, safe='')}/{quote(object_key, safe='/')}"
    )


def upload_object(object_key: str, content: bytes, content_type: str) -> str:
    base_url, service_key, bucket = _config()
    request = Request(
        _object_url(base_url, bucket, object_key),
        data=content,
        method="POST",
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": content_type or "application/octet-stream",
            "cache-control": "max-age=3600",
            "x-upsert": "false",
        },
    )
    try:
        with urlopen(request, timeout=60) as response:
            if response.status not in (200, 201):
                raise RuntimeError(f"Supabase Storage returned HTTP {response.status}.")
    except (HTTPError, URLError) as exc:
        raise RuntimeError("Could not upload the file to Supabase Storage.") from exc
    return public_object_url(object_key)


def delete_object(object_key: str) -> None:
    base_url, service_key, bucket = _config()
    request = Request(
        f"{base_url}/storage/v1/object/{quote(bucket, safe='')}",
        data=json.dumps({"prefixes": [object_key]}).encode("utf-8"),
        method="DELETE",
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            if response.status not in (200, 204):
                raise RuntimeError(f"Supabase Storage returned HTTP {response.status}.")
    except (HTTPError, URLError) as exc:
        raise RuntimeError("Could not delete the file from Supabase Storage.") from exc
