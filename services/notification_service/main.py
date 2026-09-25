"""
Notification Service - сервис реального времени для обновления параметров пользователя.
Порт: 8013
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ParameterEvent(BaseModel):
    user_id: int = Field(..., ge=1)
    event: str = Field(default="parameters.updated", min_length=3)
    coins: Optional[int] = None
    satisfaction: Optional[int] = None
    intelligence_level: Optional[int] = None
    intelligence_points: Optional[int] = None
    rating: Optional[float] = None
    source: Optional[str] = Field(default=None, max_length=100)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GenericEvent(BaseModel):
    user_id: int = Field(..., ge=1)
    event: str = Field(..., min_length=3)
    payload: Dict[str, Any] = Field(default_factory=dict)
    metadata: Optional[Dict[str, Any]] = None


class OutboundMessage(BaseModel):
    type: str
    user_id: int
    timestamp: str
    payload: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None


class ConnectionManager:
    """
    Управляет активными WebSocket-подключениями.
    """

    def __init__(self) -> None:
        self._connections: Dict[int, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.setdefault(user_id, set()).add(websocket)
        logger.info("Новое WebSocket-подключение: user_id=%s", user_id)

    async def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        async with self._lock:
            if user_id in self._connections:
                self._connections[user_id].discard(websocket)
                if not self._connections[user_id]:
                    self._connections.pop(user_id, None)
        logger.info("WebSocket-подключение закрыто: user_id=%s", user_id)

    def _prepare_message(
        self,
        *,
        event_type: str,
        user_id: int,
        payload: Dict[str, Any],
        metadata: Optional[Dict[str, Any]],
    ) -> OutboundMessage:
        timestamp = datetime.now(timezone.utc).isoformat()
        outbound = OutboundMessage(
            type=event_type,
            user_id=user_id,
            timestamp=timestamp,
            payload=payload,
            metadata=metadata or None,
        )
        return outbound

    async def _deliver(self, user_id: int, message: OutboundMessage) -> int:
        async with self._lock:
            targets: List[WebSocket] = list(self._connections.get(user_id, ()))

        delivered = 0
        for websocket in targets:
            try:
                await websocket.send_json(message.model_dump())
                delivered += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Ошибка отправки сообщения user_id=%s: %s",
                    user_id,
                    exc,
                )
                # Попытка закрыть проблемное соединение
                try:
                    await websocket.close()
                finally:
                    await self.disconnect(user_id, websocket)
        return delivered

    async def send_personal(self, event: ParameterEvent) -> int:
        payload = event.model_dump(
            exclude={"user_id", "event", "metadata"},
            exclude_none=True,
        )
        message = self._prepare_message(
            event_type=event.event,
            user_id=event.user_id,
            payload=payload,
            metadata=event.metadata,
        )
        return await self._deliver(event.user_id, message)

    async def send_generic(self, event: GenericEvent) -> int:
        message = self._prepare_message(
            event_type=event.event,
            user_id=event.user_id,
            payload=event.payload,
            metadata=event.metadata,
        )
        return await self._deliver(event.user_id, message)

    async def close_all(self) -> None:
        async with self._lock:
            connections = [
                (user_id, socket)
                for user_id, sockets in self._connections.items()
                for socket in sockets
            ]
            self._connections.clear()

        for user_id, socket in connections:
            try:
                await socket.close()
            except Exception:  # noqa: BLE001
                pass
            logger.info("Соединение закрыто при остановке: user_id=%s", user_id)

    async def connections_count(self) -> int:
        async with self._lock:
            return sum(len(sockets) for sockets in self._connections.values())


app = FastAPI(title="Notification Service", version="1.0.0")
manager = ConnectionManager()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> Dict[str, Any]:
    return {"service": "Notification Service", "version": "1.0.0"}


@app.get("/health")
async def health() -> Dict[str, Any]:
    count = await manager.connections_count()
    return {"status": "healthy", "connections": count}


@app.post("/events/parameters")
async def push_parameter_event(event: ParameterEvent) -> Dict[str, Any]:
    delivered = await manager.send_personal(event)
    return {
        "delivered": delivered,
        "user_id": event.user_id,
        "type": event.event,
    }


@app.post("/events/generic")
async def push_generic_event(event: GenericEvent) -> Dict[str, Any]:
    delivered = await manager.send_generic(event)
    return {
        "delivered": delivered,
        "user_id": event.user_id,
        "type": event.event,
    }


@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int) -> None:
    if user_id <= 0:
        await websocket.close(code=4000)
        raise HTTPException(status_code=400, detail="Некорректный user_id")

    await manager.connect(user_id, websocket)
    try:
        # Отправляем приветственное сообщение
        await websocket.send_json(
            {
                "type": "connection.ack",
                "user_id": user_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

        while True:
            data = await websocket.receive_text()
            if data.strip().lower() == "ping":
                await websocket.send_json(
                    {
                        "type": "connection.pong",
                        "user_id": user_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )
    except WebSocketDisconnect:
        await manager.disconnect(user_id, websocket)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Ошибка в WebSocket соединении user_id=%s: %s", user_id, exc)
        await manager.disconnect(user_id, websocket)


@app.on_event("shutdown")
async def shutdown() -> None:
    await manager.close_all()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8013)


