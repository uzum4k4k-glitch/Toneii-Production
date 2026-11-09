from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Any, List
import json
import time

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.rooms: Dict[str, Dict[WebSocket, Any]] = {}
        self.room_profiles: Dict[str, str] = {}
        self.room_bgm_state: Dict[str, Dict[str, Any]] = {}

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
            # Ask Host for real-time BGM sync first
            host_found = False
            for client_ws, info in list(self.rooms[room_id].items()):
                if info["role"] == "host":
                    try:
                        await client_ws.send_json({"action": "request_sync", "target": name})
                        host_found = True
                    except Exception:
                        pass
            # Fallback to server-tracked state if Host hasn't responded yet
            if not host_found and room_id in self.room_bgm_state:
                state = self.room_bgm_state[room_id]
                if state.get("filename"):
                    est_time = float(state.get("time", 0.0))
                    if state.get("is_playing"):
                        est_time += max(0.0, time.time() - state.get("updated_at", time.time()))
                    await ws.send_json({
                        "action": "sync_bgm",
                        "filename": state["filename"],
                        "display_name": state.get("display_name", state["filename"]),
                        "volume": state.get("volume", 1.0),
                        "time": est_time,
                        "is_playing": state.get("is_playing", False)
                    })

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
        state = self.room_bgm_state.setdefault(room_id, {
            "filename": None,
            "display_name": None,
            "volume": 1.0,
            "time": 0.0,
            "is_playing": False,
            "updated_at": time.time()
        })
        now = time.time()
        if action in ("play_bgm", "sync_bgm"):
            state["filename"] = message.get("filename")
            state["display_name"] = message.get("display_name") or message.get("filename")
            state["volume"] = float(message.get("volume", 1.0))
            state["time"] = float(message.get("time", 0.0))
            state["is_playing"] = bool(message.get("is_playing", True))
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
            state["filename"] = message.get("filename", state["filename"])
            state["time"] = float(message.get("time", 0.0))
            if "volume" in message:
                state["volume"] = float(message["volume"])
            if "is_playing" in message:
                state["is_playing"] = bool(message["is_playing"])
            state["updated_at"] = now
        elif action == "volume_bgm":
            state["volume"] = float(message.get("volume", 1.0))
        elif action in ("stop_bgm", "stop_all"):
            state["filename"] = None
            state["display_name"] = None
            state["time"] = 0.0
            state["is_playing"] = False
            state["updated_at"] = now

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
                # Guest explicitly requesting current BGM state from Host
                for client_ws, info in list(manager.rooms.get(room_id, {}).items()):
                    if info["role"] == "host":
                        try:
                            await client_ws.send_json({"action": "request_sync", "target": user_name})
                        except Exception:
                            pass
            else:
                if action in ("play_bgm", "pause_bgm", "resume_bgm", "seek_bgm", "stop_bgm", "stop_all", "volume_bgm", "sync_bgm"):
                    manager.update_bgm_state(room_id, message)
                if action == "play_sfx":
                    message["sender"] = user_name
                await manager.broadcast(room_id, message)
    except WebSocketDisconnect:
        await manager.disconnect(websocket, room_id)
