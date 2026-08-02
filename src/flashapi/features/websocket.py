"""WebSocket real-time events — broadcasts CRUD events to connected clients.

Protocol: raw WebSocket with JSON messages (compatible with the spec's event format).
Clients subscribe to topics via a SUBSCRIBE message, server pushes events.

Message format (server → client):
{
  "type": "ENTITY_CREATED" | "ENTITY_UPDATED" | "ENTITY_DELETED" | "ENTITY_RESTORED",
  "entity": "Eleve",
  "data": { ... },
  "timestamp": "2026-07-14T15:30:00Z"
}

Subscribe message (client → server):
{
  "action": "subscribe",
  "topic": "/topic/entities" | "/topic/{entity}"
}

Unsubscribe message (client → server):
{
  "action": "unsubscribe",
  "topic": "/topic/entities" | "/topic/{entity}"
}
"""

from __future__ import annotations

import json
from datetime import datetime, timezone


class WebSocketHub:
    """In-memory pub/sub hub for WebSocket connections.

    Framework adapters register connections and call broadcast() on CRUD events.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, set] = {}

    def subscribe(self, topic: str, connection) -> None:
        if topic not in self._subscribers:
            self._subscribers[topic] = set()
        self._subscribers[topic].add(connection)

    def unsubscribe(self, topic: str, connection) -> None:
        if topic in self._subscribers:
            self._subscribers[topic].discard(connection)
            if not self._subscribers[topic]:
                del self._subscribers[topic]

    def remove_connection(self, connection) -> None:
        for topic in list(self._subscribers.keys()):
            self._subscribers[topic].discard(connection)
            if not self._subscribers[topic]:
                del self._subscribers[topic]

    def get_subscribers(self, entity: str) -> set:
        global_subs = self._subscribers.get("/topic/entities", set())
        entity_subs = self._subscribers.get(f"/topic/{entity.lower()}", set())
        return global_subs | entity_subs

    def build_message(self, event_type: str, entity: str, data: dict | None = None) -> str:
        message = {
            "type": event_type,
            "entity": entity,
            "data": data or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return json.dumps(message)


_hub = WebSocketHub()


def get_hub() -> WebSocketHub:
    return _hub


def broadcast_event(entity: str, event_type: str, data: dict | None = None) -> None:
    """Broadcast an event to all subscribers. Called by adapters after CRUD ops.

    This is a no-op if no WebSocket connections are active (zero overhead).
    """
    hub = get_hub()
    subscribers = hub.get_subscribers(entity)
    if not subscribers:
        return

    message = hub.build_message(event_type, entity, data)

    dead = set()
    for conn in subscribers:
        try:
            conn.send_message(message)
        except Exception:
            dead.add(conn)

    for conn in dead:
        hub.remove_connection(conn)


async def broadcast_event_async(entity: str, event_type: str, data: dict | None = None) -> None:
    """Async version of broadcast_event for FastAPI/async frameworks."""
    hub = get_hub()
    subscribers = hub.get_subscribers(entity)
    if not subscribers:
        return

    message = hub.build_message(event_type, entity, data)

    dead = set()
    for conn in subscribers:
        try:
            await conn.send_message(message)
        except Exception:
            dead.add(conn)

    for conn in dead:
        hub.remove_connection(conn)


EVENT_MAP = {
    "CREATE": "ENTITY_CREATED",
    "UPDATE": "ENTITY_UPDATED",
    "DELETE": "ENTITY_DELETED",
    "RESTORE": "ENTITY_RESTORED",
}
