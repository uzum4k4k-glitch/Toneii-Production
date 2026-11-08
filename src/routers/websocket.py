from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Any
import json

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.rooms: Dict[str, Dict[WebSocket, Any]] = {}

    async def connect(self, ws: WebSocket, room_id: str, name: str, role: str):
        await ws.accept()
        if room_id not in self.rooms:
            self.rooms[room_id] = {}
        self.rooms[room_id][ws] = {"name": name, "role": role, "can_upload": False}
        await self.broadcast_users(room_id)

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

manager = ConnectionManager()

@router.websocket("/ws/{room_id}/{user_name}/{role}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, user_name: str, role: str):
    await manager.connect(websocket, room_id, user_name, role)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("action") == "grant_upload":
                await manager.set_permission(room_id, message.get("target_name"), message.get("can_upload"))
            else:
                await manager.broadcast(room_id, message)
    except WebSocketDisconnect:
        await manager.disconnect(websocket, room_id)
