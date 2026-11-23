"""
WebSocket connection manager and event publishing module for live hospital triage updates.
Supports real-time broadcasts, targeted doctor alerts, and sync-safe event dispatch.
"""

import asyncio
from dataclasses import dataclass
from typing import List, Optional
from fastapi import WebSocket


@dataclass
class ClientConnection:
    ws: WebSocket
    role: Optional[str] = None
    doctor_id: Optional[int] = None


class ConnectionManager:
    """Manages active WebSocket connections with role and provider metadata."""

    def __init__(self):
        self.connections: List[ClientConnection] = []

    async def connect(
        self,
        ws: WebSocket,
        role: Optional[str] = None,
        doctor_id: Optional[int] = None,
    ):
        """Accept incoming WebSocket connection and register client metadata."""
        await ws.accept()
        role_normalized = role.strip().lower() if role else None
        self.connections.append(ClientConnection(ws=ws, role=role_normalized, doctor_id=doctor_id))

    def disconnect(self, ws: WebSocket):
        """Remove WebSocket connection on client disconnect."""
        self.connections = [c for c in self.connections if c.ws != ws]

    async def broadcast(self, event: dict):
        """Send JSON payload to all connected clients; silently prune dead connections."""
        dead_connections = []
        for conn in self.connections:
            try:
                await conn.ws.send_json(event)
            except Exception:
                dead_connections.append(conn)

        for dead in dead_connections:
            if dead in self.connections:
                self.connections.remove(dead)

    async def send_to_doctor(self, doctor_id: int, event: dict):
        """Send JSON payload only to clients registered with the given doctor_id."""
        dead_connections = []
        for conn in self.connections:
            if conn.doctor_id == doctor_id:
                try:
                    await conn.ws.send_json(event)
                except Exception:
                    dead_connections.append(conn)

        for dead in dead_connections:
            if dead in self.connections:
                self.connections.remove(dead)

    async def send_to_roles(self, roles: List[str], event: dict):
        """Send JSON payload to clients whose registered role matches any in roles."""
        roles_set = {r.strip().lower() for r in roles}
        dead_connections = []
        for conn in self.connections:
            if conn.role and conn.role in roles_set:
                try:
                    await conn.ws.send_json(event)
                except Exception:
                    dead_connections.append(conn)

        for dead in dead_connections:
            if dead in self.connections:
                self.connections.remove(dead)

    async def send_alert_event(
        self,
        event: dict,
        doctor_id: Optional[int] = None,
        roles: Optional[List[str]] = None,
    ):
        """
        Send alert event to the specified doctor_id and/or specified roles
        without sending duplicates to the same connection.
        """
        roles_set = {r.strip().lower() for r in roles} if roles else set()
        target_conns = []
        for conn in self.connections:
            is_match = False
            if doctor_id is not None and conn.doctor_id == doctor_id:
                is_match = True
            elif conn.role and conn.role in roles_set:
                is_match = True

            if is_match and conn not in target_conns:
                target_conns.append(conn)

        dead_connections = []
        for conn in target_conns:
            try:
                await conn.ws.send_json(event)
            except Exception:
                dead_connections.append(conn)

        for dead in dead_connections:
            if dead in self.connections:
                self.connections.remove(dead)


# Module-level connection manager instance
manager = ConnectionManager()

# Main application event loop captured on startup
_main_event_loop: Optional[asyncio.AbstractEventLoop] = None


def set_event_loop(loop: asyncio.AbstractEventLoop):
    """Set the main application event loop captured on FastAPI startup."""
    global _main_event_loop
    _main_event_loop = loop


def get_event_loop() -> Optional[asyncio.AbstractEventLoop]:
    """Retrieve the main application event loop."""
    global _main_event_loop
    return _main_event_loop


def publish(
    event: dict,
    doctor_id: Optional[int] = None,
    roles: Optional[List[str]] = None,
):
    """
    Safely schedules asynchronous event dispatch from synchronous API endpoints.
    Never blocks or raises; does nothing if no clients are connected.
    """
    if not manager.connections:
        return

    async def _dispatch():
        if doctor_id is not None or roles is not None:
            await manager.send_alert_event(event, doctor_id=doctor_id, roles=roles)
        else:
            await manager.broadcast(event)

    try:
        loop = _main_event_loop
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(_dispatch(), loop)
        else:
            # Fallback for active async loop in current thread
            try:
                running_loop = asyncio.get_running_loop()
                running_loop.create_task(_dispatch())
            except RuntimeError:
                pass
    except Exception:
        # Guarantee that publishing never disrupts API responses
        pass
