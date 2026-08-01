"""Tests for WebSocket real-time events."""

import json
import pytest
from dataclasses import dataclass

from flashapi.features.websocket import WebSocketHub, EVENT_MAP, broadcast_event, get_hub


class MockConnection:
    def __init__(self):
        self.messages = []
        self.closed = False

    def send_message(self, message: str):
        if self.closed:
            raise ConnectionError("closed")
        self.messages.append(json.loads(message))


class TestWebSocketHub:
    def setup_method(self):
        self.hub = WebSocketHub()

    def test_subscribe(self):
        conn = MockConnection()
        self.hub.subscribe("/topic/entities", conn)
        assert conn in self.hub.get_subscribers("Anything")

    def test_subscribe_entity_specific(self):
        conn = MockConnection()
        self.hub.subscribe("/topic/users", conn)
        assert conn in self.hub.get_subscribers("Users")
        assert conn not in self.hub.get_subscribers("Products")

    def test_unsubscribe(self):
        conn = MockConnection()
        self.hub.subscribe("/topic/entities", conn)
        self.hub.unsubscribe("/topic/entities", conn)
        assert conn not in self.hub.get_subscribers("Anything")

    def test_remove_connection(self):
        conn = MockConnection()
        self.hub.subscribe("/topic/entities", conn)
        self.hub.subscribe("/topic/users", conn)
        self.hub.remove_connection(conn)
        assert conn not in self.hub.get_subscribers("Users")
        assert conn not in self.hub.get_subscribers("Anything")

    def test_build_message(self):
        msg = self.hub.build_message("ENTITY_CREATED", "User", {"id": 1, "name": "Alice"})
        parsed = json.loads(msg)
        assert parsed["type"] == "ENTITY_CREATED"
        assert parsed["entity"] == "User"
        assert parsed["data"] == {"id": 1, "name": "Alice"}
        assert "timestamp" in parsed

    def test_global_and_entity_subscribers(self):
        global_conn = MockConnection()
        entity_conn = MockConnection()
        other_conn = MockConnection()

        self.hub.subscribe("/topic/entities", global_conn)
        self.hub.subscribe("/topic/users", entity_conn)
        self.hub.subscribe("/topic/products", other_conn)

        subs = self.hub.get_subscribers("Users")
        assert global_conn in subs
        assert entity_conn in subs
        assert other_conn not in subs


class TestBroadcastEvent:
    def setup_method(self):
        hub = get_hub()
        self._original_subscribers = dict(hub._subscribers)
        hub._subscribers.clear()

    def teardown_method(self):
        hub = get_hub()
        hub._subscribers.clear()
        hub._subscribers.update(self._original_subscribers)

    def test_broadcast_to_subscribers(self):
        hub = get_hub()
        conn = MockConnection()
        hub.subscribe("/topic/entities", conn)

        broadcast_event("User", "ENTITY_CREATED", {"id": 1, "name": "Alice"})

        assert len(conn.messages) == 1
        assert conn.messages[0]["type"] == "ENTITY_CREATED"
        assert conn.messages[0]["entity"] == "User"
        assert conn.messages[0]["data"] == {"id": 1, "name": "Alice"}

    def test_broadcast_no_subscribers_is_noop(self):
        broadcast_event("User", "ENTITY_CREATED", {"id": 1})

    def test_dead_connection_removed(self):
        hub = get_hub()
        conn = MockConnection()
        conn.closed = True
        hub.subscribe("/topic/entities", conn)

        broadcast_event("User", "ENTITY_CREATED", {"id": 1})
        assert conn not in hub.get_subscribers("User")

    def test_multiple_subscribers(self):
        hub = get_hub()
        conn1 = MockConnection()
        conn2 = MockConnection()
        hub.subscribe("/topic/entities", conn1)
        hub.subscribe("/topic/entities", conn2)

        broadcast_event("User", "ENTITY_CREATED", {"id": 1})

        assert len(conn1.messages) == 1
        assert len(conn2.messages) == 1

    def test_entity_specific_topic(self):
        hub = get_hub()
        user_conn = MockConnection()
        product_conn = MockConnection()
        hub.subscribe("/topic/user", user_conn)
        hub.subscribe("/topic/product", product_conn)

        broadcast_event("User", "ENTITY_CREATED", {"id": 1})

        assert len(user_conn.messages) == 1
        assert len(product_conn.messages) == 0


class TestEventMap:
    def test_all_events_mapped(self):
        assert EVENT_MAP["CREATE"] == "ENTITY_CREATED"
        assert EVENT_MAP["UPDATE"] == "ENTITY_UPDATED"
        assert EVENT_MAP["DELETE"] == "ENTITY_DELETED"
        assert EVENT_MAP["RESTORE"] == "ENTITY_RESTORED"


class TestFastAPIWebSocket:
    """Test that the WebSocket endpoint is properly configured."""

    @pytest.fixture
    def client(self, tmp_path):
        from fastapi.testclient import TestClient
        from flashapi.fastapi import FlashAPI

        hub = get_hub()
        hub._subscribers.clear()

        @dataclass
        class Item:
            name: str
            price: float = 0.0

        api = FlashAPI(models=[Item], database=str(tmp_path / "ws_test.db"))
        return TestClient(api.app)

    def test_websocket_connect_and_subscribe(self, client):
        with client.websocket_connect("/api/ws") as ws:
            ws.send_text(json.dumps({"action": "subscribe", "topic": "/topic/entities"}))

    def test_websocket_invalid_json_ignored(self, client):
        with client.websocket_connect("/api/ws") as ws:
            ws.send_text("not json")
            ws.send_text(json.dumps({"action": "subscribe", "topic": "/topic/entities"}))

    def test_websocket_unsubscribe(self, client):
        hub = get_hub()
        with client.websocket_connect("/api/ws") as ws:
            ws.send_text(json.dumps({"action": "subscribe", "topic": "/topic/entities"}))
            assert len(hub._subscribers.get("/topic/entities", set())) == 1
            ws.send_text(json.dumps({"action": "unsubscribe", "topic": "/topic/entities"}))

    def test_crud_triggers_broadcast_via_hub(self, client):
        """Verify CRUD operations call broadcast by pre-subscribing a mock."""
        hub = get_hub()
        conn = MockConnection()
        hub.subscribe("/topic/entities", conn)

        client.post("/api/items", json={"name": "Widget", "price": 9.99})
        assert len(conn.messages) == 1
        assert conn.messages[0]["type"] == "ENTITY_CREATED"
        assert conn.messages[0]["entity"] == "Item"
        assert conn.messages[0]["data"]["name"] == "Widget"

    def test_update_triggers_broadcast(self, client):
        hub = get_hub()
        conn = MockConnection()

        client.post("/api/items", json={"name": "Widget", "price": 9.99})
        hub.subscribe("/topic/entities", conn)

        client.put("/api/items/1", json={"name": "Updated"})
        assert len(conn.messages) == 1
        assert conn.messages[0]["type"] == "ENTITY_UPDATED"
        assert conn.messages[0]["data"]["name"] == "Updated"

    def test_delete_triggers_broadcast(self, client):
        hub = get_hub()
        conn = MockConnection()

        client.post("/api/items", json={"name": "Widget", "price": 9.99})
        hub.subscribe("/topic/entities", conn)

        client.delete("/api/items/1")
        assert len(conn.messages) == 1
        assert conn.messages[0]["type"] == "ENTITY_DELETED"
        assert conn.messages[0]["data"]["id"] == "1"

    def test_entity_specific_broadcast(self, client):
        hub = get_hub()
        item_conn = MockConnection()
        other_conn = MockConnection()
        hub.subscribe("/topic/item", item_conn)
        hub.subscribe("/topic/other", other_conn)

        client.post("/api/items", json={"name": "Widget", "price": 9.99})

        assert len(item_conn.messages) == 1
        assert len(other_conn.messages) == 0


class TestFlaskWebSocketIntegration:
    """Test that Flask adapter calls broadcast on CRUD operations."""

    @pytest.fixture
    def client(self, tmp_path):
        from flask import Flask
        from flashapi.flask import register_models
        from flashapi import Model

        hub = get_hub()
        hub._subscribers.clear()

        @dataclass
        class Task:
            title: str
            done: bool = False

        app = Flask(__name__)
        register_models(app, models=[Model(Task, soft_delete=True)], database=str(tmp_path / "ws_flask.db"))
        app.testing = True
        return app.test_client()

    def test_create_broadcasts(self, client):
        hub = get_hub()
        conn = MockConnection()
        hub.subscribe("/topic/entities", conn)

        client.post("/api/tasks", json={"title": "Do stuff"})
        assert len(conn.messages) == 1
        assert conn.messages[0]["type"] == "ENTITY_CREATED"
        assert conn.messages[0]["entity"] == "Task"

    def test_update_broadcasts(self, client):
        hub = get_hub()
        conn = MockConnection()

        client.post("/api/tasks", json={"title": "Do stuff"})
        hub.subscribe("/topic/entities", conn)

        client.put("/api/tasks/1", json={"title": "Updated"})
        assert len(conn.messages) == 1
        assert conn.messages[0]["type"] == "ENTITY_UPDATED"

    def test_delete_broadcasts(self, client):
        hub = get_hub()
        conn = MockConnection()

        client.post("/api/tasks", json={"title": "Do stuff"})
        hub.subscribe("/topic/entities", conn)

        client.delete("/api/tasks/1")
        assert len(conn.messages) == 1
        assert conn.messages[0]["type"] == "ENTITY_DELETED"

    def test_restore_broadcasts(self, client):
        hub = get_hub()
        conn = MockConnection()

        client.post("/api/tasks", json={"title": "Do stuff"})
        client.delete("/api/tasks/1")
        hub.subscribe("/topic/entities", conn)

        client.post("/api/tasks/1/restore")
        assert len(conn.messages) == 1
        assert conn.messages[0]["type"] == "ENTITY_RESTORED"
