from fastapi import WebSocket
from typing import List

class ConnectionManager:
    def __init__(self):
        self.active_connectiions: List[WebSocket] = []
        
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connectiions.append(websocket)
        
    def disconnect(self, websocket: WebSocket):
        self.active_connectiions.remove(websocket)
        
    async def broadcast(self, message: str):
        for connection in self.active_connectiions:
            await connection.send_text(message)