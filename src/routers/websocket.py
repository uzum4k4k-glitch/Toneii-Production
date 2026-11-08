from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Any, List
import json

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.rooms: Dict[str, Dict[WebSocket, Any]] = {}
        self.room_profiles: Dict[str, str] = {} # room_id -> image_url

    async def connect(self, ws: WebSocket, room_id: str, name: str, role: str):
        await ws.accept()
        if room_id not in self.rooms:
            self.rooms[room_id] = {}
            if room_id not in self.room_profiles:
                self.room_profiles[room_id] = "https://via.placeholder.com/150/1a1514/d4af37?text=DnD"
        self.rooms[room_id][ws] = {"name": name, "role": role, "can_upload": False}
        await self.broadcast_users(room_id)
        # Send room profile on connect
        await ws.send_json({"action": "room_profile", "url": self.room_profiles[room_id]})

    async def disconnect(self, ws: WebSocket, room_id: str):
        if room_id in self.rooms and ws in self.rooms[room_id]:
            del self.rooms[room_id][ws]
            await self.broadcast_users(room_id)
            if not self.rooms[room_id]: # If room is empty, maybe clean up, but let's keep it alive for reconnects.
                pass

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
            
            if message.get("action") == "grant_upload":
                await manager.set_permission(room_id, message.get("target_name"), message.get("can_upload"))
            elif message.get("action") == "update_room_profile":
                manager.room_profiles[room_id] = message.get("url")
                await manager.broadcast(room_id, {"action": "room_profile", "url": message.get("url")})
            else:
                # Include sender name in sfx play for highlighting
                if message.get("action") == "play_sfx":
                     message["sender"] = user_name
                await manager.broadcast(room_id, message)
    except WebSocketDisconnect:
        await manager.disconnect(websocket, room_id)
