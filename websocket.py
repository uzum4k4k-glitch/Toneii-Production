from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Any, List
import json
import time

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.rooms: Dict[str, Dict[WebSocket, Any]] = {}
        self.room_profiles: Dict[str, str] = {}
        # Maps room_id -> { filename: { filename, display_name, volume, time, is_playing, loop, updated_at } }
        self.room_bgm_states: Dict[str, Dict[str, Dict[str, Any]]] = {}

    async def connect(self, ws: WebSocket, room_id: str, name: str, role: str):
        await ws.accept()
        if room_id not in self.rooms:
            self.rooms[room_id] = {}
            if room_id not in self.room_profiles:
                self.room_profiles[room_id] = "https://via.placeholder.com/150/1a1514/d4af37?text=DnD"
        self.rooms[room_id][ws] = {"name": name, "role": role, "can_upload": False}
        await self.broadcast_users(room_id)
        await ws.send_json({"action": "room_profile", "url": self.room_profiles[room_id]})

        if role == "guest":
            host_found = False
            for client_ws, info in list(self.rooms[room_id].items()):
                if info["role"] == "host":
                    try:
                        await client_ws.send_json({"action": "request_sync", "target": name})
                        host_found = True
                    except Exception:
                        pass
            if not host_found and room_id in self.room_bgm_states:
                tracks_payload = []
                now = time.time()
                for fname, state in self.room_bgm_states[room_id].items():
                    est_time = float(state.get("time", 0.0))
                    if state.get("is_playing"):
                        est_time += max(0.0, now - state.get("updated_at", now))
                    tracks_payload.append({
                        "filename": fname,
                        "display_name": state.get("display_name", fname),
                        "volume": state.get("volume", 1.0),
                        "time": est_time,
                        "is_playing": state.get("is_playing", False),
                        "loop": state.get("loop", False)
                    })
                if tracks_payload:
                    await ws.send_json({"action": "sync_all_bgm", "tracks": tracks_payload})

    async def disconnect(self, ws: WebSocket, room_id: str):
        if room_id in self.rooms and ws in self.rooms[room_id]:
            del self.rooms[room_id][ws]
            await self.broadcast_users(room_id)

    async def broadcast_users(self, room_id: str):
        if room_id in self.rooms:
            users_list = [
                {"name": data["name"], "role": data["role"], "can_upload": data["can_upload"]}
                for data in self.rooms[room_id].values()
            ]
            await self.broadcast(room_id, {"action": "user_update", "users": users_list})

    async def broadcast(self, room_id: str, message: dict):
        if room_id in self.rooms:
            for ws in list(self.rooms[room_id].keys()):
                try:
                    await ws.send_json(message)
                except Exception:
                    pass

    async def set_permission(self, room_id: str, target_name: str, can_upload: bool):
        if room_id in self.rooms:
            for ws, data in self.rooms[room_id].items():
                if data["name"] == target_name and data["role"] == "guest":
                    data["can_upload"] = can_upload
            await self.broadcast_users(room_id)

    def update_bgm_state(self, room_id: str, message: dict):
        action = message.get("action")
        room_tracks = self.room_bgm_states.setdefault(room_id, {})
        now = time.time()

        if action == "sync_all_bgm":
            room_tracks.clear()
            for t in message.get("tracks", []):
                fname = t.get("filename")
                if fname:
                    room_tracks[fname] = {
                        "filename": fname,
                        "display_name": t.get("display_name", fname),
                        "volume": float(t.get("volume", 1.0)),
                        "time": float(t.get("time", 0.0)),
                        "is_playing": bool(t.get("is_playing", True)),
                        "loop": bool(t.get("loop", False)),
                        "updated_at": now
                    }
            return

        if action == "stop_all":
            room_tracks.clear()
            return

        fname = message.get("filename")
        if not fname:
            return

        if action == "stop_bgm":
            room_tracks.pop(fname, None)
            return

        state = room_tracks.setdefault(fname, {
            "filename": fname,
            "display_name": message.get("display_name") or fname,
            "volume": 1.0,
            "time": 0.0,
            "is_playing": False,
            "loop": False,
            "updated_at": now
        })

        if action in ("play_bgm", "sync_bgm"):
            state["display_name"] = message.get("display_name") or state.get("display_name") or fname
            state["volume"] = float(message.get("volume", state.get("volume", 1.0)))
            state["time"] = float(message.get("time", 0.0))
            state["is_playing"] = bool(message.get("is_playing", True))
            if "loop" in message:
                state["loop"] = bool(message["loop"])
            state["updated_at"] = now
        elif action == "pause_bgm":
            if "time" in message:
                state["time"] = float(message["time"])
            elif state["is_playing"]:
                state["time"] += max(0.0, now - state["updated_at"])
            state["is_playing"] = False
            state["updated_at"] = now
        elif action == "resume_bgm":
            if "time" in message:
                state["time"] = float(message["time"])
            state["is_playing"] = True
            state["updated_at"] = now
        elif action == "seek_bgm":
            state["time"] = float(message.get("time", 0.0))
            if "volume" in message:
                state["volume"] = float(message["volume"])
            if "is_playing" in message:
                state["is_playing"] = bool(message["is_playing"])
            if "loop" in message:
                state["loop"] = bool(message["loop"])
            state["updated_at"] = now
        elif action == "volume_bgm":
            state["volume"] = float(message.get("volume", 1.0))
        elif action == "loop_bgm":
            state["loop"] = bool(message.get("loop", False))

    def get_active_rooms(self) -> List[str]:
        return [room_id for room_id, users in self.rooms.items() if any(u["role"] == "host" for u in users.values())]

manager = ConnectionManager()

@router.get("/api/active_rooms")
async def get_active_rooms():
    return {"rooms": manager.get_active_rooms()}

@router.websocket("/ws/{room_id}/{user_name}/{role}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, user_name: str, role: str):
    await manager.connect(websocket, room_id, user_name, role)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            action = message.get("action")

            if action == "grant_upload":
                await manager.set_permission(room_id, message.get("target_name"), message.get("can_upload"))
            elif action == "update_room_profile":
                manager.room_profiles[room_id] = message.get("url")
                await manager.broadcast(room_id, {"action": "room_profile", "url": message.get("url")})
            elif action == "request_sync":
                for client_ws, info in list(manager.rooms.get(room_id, {}).items()):
                    if info["role"] == "host":
                        try:
                            await client_ws.send_json({"action": "request_sync", "target": user_name})
                        except Exception:
                            pass
            else:
                if action in ("play_bgm", "pause_bgm", "resume_bgm", "seek_bgm", "stop_bgm", "stop_all", "volume_bgm", "loop_bgm", "sync_bgm", "sync_all_bgm"):
                    manager.update_bgm_state(room_id, message)
                if action == "play_sfx":
                    message["sender"] = user_name
                await manager.broadcast(room_id, message)
    except WebSocketDisconnect:
        await manager.disconnect(websocket, room_id)
