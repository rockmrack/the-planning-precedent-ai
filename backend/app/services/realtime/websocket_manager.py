"""
WebSocket Connection Manager
Handles real-time connections for collaboration features
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class MessageType(str, Enum):
    """WebSocket message types"""
    # Connection events
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"

    # User presence
    USER_JOINED = "user_joined"
    USER_LEFT = "user_left"
    PRESENCE_UPDATE = "presence_update"

    # Project collaboration
    PROJECT_UPDATE = "project_update"
    CASE_SAVED = "case_saved"
    CASE_REMOVED = "case_removed"
    NOTE_ADDED = "note_added"
    NOTE_UPDATED = "note_updated"

    # Analysis events
    ANALYSIS_STARTED = "analysis_started"
    ANALYSIS_PROGRESS = "analysis_progress"
    ANALYSIS_COMPLETED = "analysis_completed"
    ANALYSIS_ERROR = "analysis_error"

    # Notifications
    NOTIFICATION = "notification"
    ALERT_TRIGGERED = "alert_triggered"

    # Chat/comments
    COMMENT_ADDED = "comment_added"
    TYPING_START = "typing_start"
    TYPING_STOP = "typing_stop"


@dataclass
class WebSocketMessage:
    """WebSocket message structure"""
    type: MessageType
    data: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    sender_id: Optional[str] = None
    room_id: Optional[str] = None

    def to_json(self) -> str:
        return json.dumps({
            "type": self.type.value,
            "data": self.data,
            "timestamp": self.timestamp,
            "sender_id": self.sender_id,
            "room_id": self.room_id
        })


@dataclass
class UserConnection:
    """Represents a user's WebSocket connection"""
    user_id: str
    websocket: WebSocket
    room_ids: Set[str] = field(default_factory=set)
    connected_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    metadata: dict = field(default_factory=dict)


class ConnectionManager:
    """Manages WebSocket connections"""

    def __init__(self):
        # user_id -> UserConnection
        self.active_connections: Dict[str, UserConnection] = {}
        # room_id -> set of user_ids
        self.rooms: Dict[str, Set[str]] = {}
        # Keep track of connection history
        self.connection_count = 0

    async def connect(
        self,
        websocket: WebSocket,
        user_id: str,
        metadata: dict = None
    ) -> UserConnection:
        """Accept a new WebSocket connection"""
        await websocket.accept()

        connection = UserConnection(
            user_id=user_id,
            websocket=websocket,
            metadata=metadata or {}
        )

        self.active_connections[user_id] = connection
        self.connection_count += 1

        logger.info(f"WebSocket connected: {user_id}")

        # Send connection confirmation
        await self.send_to_user(
            user_id,
            WebSocketMessage(
                type=MessageType.CONNECTED,
                data={"user_id": user_id, "connection_id": self.connection_count}
            )
        )

        return connection

    def disconnect(self, user_id: str) -> None:
        """Handle WebSocket disconnection"""
        if user_id in self.active_connections:
            connection = self.active_connections[user_id]

            # Remove from all rooms
            for room_id in connection.room_ids:
                if room_id in self.rooms:
                    self.rooms[room_id].discard(user_id)
                    if not self.rooms[room_id]:
                        del self.rooms[room_id]

            del self.active_connections[user_id]
            logger.info(f"WebSocket disconnected: {user_id}")

    async def join_room(self, user_id: str, room_id: str) -> None:
        """Add user to a room"""
        if user_id not in self.active_connections:
            return

        if room_id not in self.rooms:
            self.rooms[room_id] = set()

        self.rooms[room_id].add(user_id)
        self.active_connections[user_id].room_ids.add(room_id)

        # Notify room members
        await self.broadcast_to_room(
            room_id,
            WebSocketMessage(
                type=MessageType.USER_JOINED,
                data={"user_id": user_id},
                room_id=room_id,
                sender_id=user_id
            ),
            exclude_user=user_id
        )

        logger.info(f"User {user_id} joined room {room_id}")

    async def leave_room(self, user_id: str, room_id: str) -> None:
        """Remove user from a room"""
        if room_id in self.rooms:
            self.rooms[room_id].discard(user_id)
            if not self.rooms[room_id]:
                del self.rooms[room_id]

        if user_id in self.active_connections:
            self.active_connections[user_id].room_ids.discard(room_id)

        # Notify room members
        await self.broadcast_to_room(
            room_id,
            WebSocketMessage(
                type=MessageType.USER_LEFT,
                data={"user_id": user_id},
                room_id=room_id,
                sender_id=user_id
            )
        )

        logger.info(f"User {user_id} left room {room_id}")

    async def send_to_user(
        self,
        user_id: str,
        message: WebSocketMessage
    ) -> bool:
        """Send message to a specific user"""
        if user_id not in self.active_connections:
            return False

        try:
            await self.active_connections[user_id].websocket.send_text(
                message.to_json()
            )
            self.active_connections[user_id].last_activity = datetime.utcnow()
            return True
        except Exception as e:
            logger.error(f"Error sending to {user_id}: {e}")
            self.disconnect(user_id)
            return False

    async def broadcast_to_room(
        self,
        room_id: str,
        message: WebSocketMessage,
        exclude_user: Optional[str] = None
    ) -> int:
        """Broadcast message to all users in a room"""
        if room_id not in self.rooms:
            return 0

        sent_count = 0
        for user_id in self.rooms[room_id]:
            if user_id != exclude_user:
                if await self.send_to_user(user_id, message):
                    sent_count += 1

        return sent_count

    async def broadcast_to_all(
        self,
        message: WebSocketMessage,
        exclude_user: Optional[str] = None
    ) -> int:
        """Broadcast message to all connected users"""
        sent_count = 0
        for user_id in list(self.active_connections.keys()):
            if user_id != exclude_user:
                if await self.send_to_user(user_id, message):
                    sent_count += 1

        return sent_count

    def get_room_users(self, room_id: str) -> List[str]:
        """Get list of users in a room"""
        return list(self.rooms.get(room_id, set()))

    def get_user_rooms(self, user_id: str) -> List[str]:
        """Get list of rooms a user is in"""
        if user_id in self.active_connections:
            return list(self.active_connections[user_id].room_ids)
        return []

    def is_user_connected(self, user_id: str) -> bool:
        """Check if user is connected"""
        return user_id in self.active_connections

    def get_active_user_count(self) -> int:
        """Get total number of connected users"""
        return len(self.active_connections)

    def get_user_presence(self, user_id: str) -> Optional[dict]:
        """Get user's presence information"""
        if user_id not in self.active_connections:
            return None

        connection = self.active_connections[user_id]
        return {
            "user_id": user_id,
            "connected_at": connection.connected_at.isoformat(),
            "last_activity": connection.last_activity.isoformat(),
            "rooms": list(connection.room_ids),
            "metadata": connection.metadata
        }


class WebSocketManager:
    """High-level WebSocket manager with room-based messaging"""

    def __init__(self):
        self.manager = ConnectionManager()
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._heartbeat_interval = 30  # seconds

    async def start_heartbeat(self):
        """Start heartbeat to detect stale connections"""
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def stop_heartbeat(self):
        """Stop heartbeat task"""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()

    async def _heartbeat_loop(self):
        """Send periodic heartbeats"""
        while True:
            try:
                await asyncio.sleep(self._heartbeat_interval)
                await self.manager.broadcast_to_all(
                    WebSocketMessage(type=MessageType.PING)
                )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

    async def handle_connection(
        self,
        websocket: WebSocket,
        user_id: str,
        initial_rooms: List[str] = None
    ):
        """Handle a WebSocket connection lifecycle"""
        try:
            # Connect
            connection = await self.manager.connect(websocket, user_id)

            # Join initial rooms
            if initial_rooms:
                for room_id in initial_rooms:
                    await self.manager.join_room(user_id, room_id)

            # Message loop
            while True:
                try:
                    data = await websocket.receive_text()
                    await self._handle_message(user_id, data)
                except WebSocketDisconnect:
                    break
                except Exception as e:
                    logger.error(f"Message handling error: {e}")
                    await self.manager.send_to_user(
                        user_id,
                        WebSocketMessage(
                            type=MessageType.ERROR,
                            data={"error": str(e)}
                        )
                    )

        finally:
            # Cleanup
            self.manager.disconnect(user_id)

    async def _handle_message(self, user_id: str, raw_data: str):
        """Handle incoming WebSocket message"""
        try:
            data = json.loads(raw_data)
            message_type = data.get("type")

            if message_type == "pong":
                # Update last activity
                if user_id in self.manager.active_connections:
                    self.manager.active_connections[user_id].last_activity = \
                        datetime.utcnow()

            elif message_type == "join_room":
                room_id = data.get("room_id")
                if room_id:
                    await self.manager.join_room(user_id, room_id)

            elif message_type == "leave_room":
                room_id = data.get("room_id")
                if room_id:
                    await self.manager.leave_room(user_id, room_id)

            elif message_type == "typing_start":
                room_id = data.get("room_id")
                if room_id:
                    await self.manager.broadcast_to_room(
                        room_id,
                        WebSocketMessage(
                            type=MessageType.TYPING_START,
                            data={"user_id": user_id},
                            room_id=room_id,
                            sender_id=user_id
                        ),
                        exclude_user=user_id
                    )

            elif message_type == "typing_stop":
                room_id = data.get("room_id")
                if room_id:
                    await self.manager.broadcast_to_room(
                        room_id,
                        WebSocketMessage(
                            type=MessageType.TYPING_STOP,
                            data={"user_id": user_id},
                            room_id=room_id,
                            sender_id=user_id
                        ),
                        exclude_user=user_id
                    )

            # Add more message handlers as needed

        except json.JSONDecodeError:
            logger.error(f"Invalid JSON from {user_id}")

    # Convenience methods for sending specific message types

    async def notify_project_update(
        self,
        project_id: str,
        update_type: str,
        data: dict,
        sender_id: str
    ):
        """Notify all project members of an update"""
        room_id = f"project:{project_id}"
        await self.manager.broadcast_to_room(
            room_id,
            WebSocketMessage(
                type=MessageType.PROJECT_UPDATE,
                data={"update_type": update_type, **data},
                room_id=room_id,
                sender_id=sender_id
            ),
            exclude_user=sender_id
        )

    async def notify_analysis_progress(
        self,
        user_id: str,
        analysis_id: str,
        progress: float,
        status: str
    ):
        """Send analysis progress update to user"""
        await self.manager.send_to_user(
            user_id,
            WebSocketMessage(
                type=MessageType.ANALYSIS_PROGRESS,
                data={
                    "analysis_id": analysis_id,
                    "progress": progress,
                    "status": status
                }
            )
        )

    async def notify_analysis_completed(
        self,
        user_id: str,
        analysis_id: str,
        result_summary: dict
    ):
        """Send analysis completion notification"""
        await self.manager.send_to_user(
            user_id,
            WebSocketMessage(
                type=MessageType.ANALYSIS_COMPLETED,
                data={
                    "analysis_id": analysis_id,
                    "result": result_summary
                }
            )
        )

    async def send_notification(
        self,
        user_id: str,
        title: str,
        message: str,
        notification_type: str = "info",
        data: dict = None
    ):
        """Send a notification to a user"""
        await self.manager.send_to_user(
            user_id,
            WebSocketMessage(
                type=MessageType.NOTIFICATION,
                data={
                    "title": title,
                    "message": message,
                    "notification_type": notification_type,
                    **(data or {})
                }
            )
        )

    async def send_alert(
        self,
        user_id: str,
        alert_id: str,
        case_reference: str,
        match_reason: str
    ):
        """Send alert trigger notification"""
        await self.manager.send_to_user(
            user_id,
            WebSocketMessage(
                type=MessageType.ALERT_TRIGGERED,
                data={
                    "alert_id": alert_id,
                    "case_reference": case_reference,
                    "match_reason": match_reason
                }
            )
        )
