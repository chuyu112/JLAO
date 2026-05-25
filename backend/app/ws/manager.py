from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.setdefault(session_id, []).append(websocket)

    def disconnect(self, session_id: str, websocket: WebSocket) -> None:
        connections = self.active_connections.get(session_id, [])
        if websocket in connections:
            connections.remove(websocket)
        if not connections and session_id in self.active_connections:
            self.active_connections.pop(session_id, None)

    async def broadcast(self, session_id: str, event: str, data: dict) -> None:
        dead_connections: list[WebSocket] = []
        for connection in self.active_connections.get(session_id, []):
            try:
                await connection.send_json({"event": event, "data": data})
            except Exception:
                dead_connections.append(connection)

        for connection in dead_connections:
            self.disconnect(session_id, connection)


manager = ConnectionManager()

