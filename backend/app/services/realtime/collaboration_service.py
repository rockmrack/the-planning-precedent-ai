"""
Collaboration Service
Handles real-time collaboration on projects and cases
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum

from .websocket_manager import WebSocketManager, MessageType, WebSocketMessage

logger = logging.getLogger(__name__)


class CollaboratorRole(str, Enum):
    """Roles within a collaboration session"""
    OWNER = "owner"
    EDITOR = "editor"
    COMMENTER = "commenter"
    VIEWER = "viewer"


@dataclass
class Collaborator:
    """A user collaborating on a project"""
    user_id: str
    email: str
    full_name: str
    role: CollaboratorRole
    cursor_position: Optional[dict] = None
    last_activity: datetime = field(default_factory=datetime.utcnow)
    is_active: bool = True


@dataclass
class Comment:
    """A comment on a case or analysis"""
    id: str
    user_id: str
    user_name: str
    content: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    parent_id: Optional[str] = None  # For replies
    resolved: bool = False
    target_type: str = "case"  # case, analysis, note
    target_id: str = ""


@dataclass
class CollaborationSession:
    """An active collaboration session"""
    session_id: str
    project_id: str
    collaborators: Dict[str, Collaborator] = field(default_factory=dict)
    comments: List[Comment] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)


class CollaborationService:
    """Manages real-time collaboration features"""

    def __init__(self, ws_manager: WebSocketManager):
        self.ws = ws_manager
        self.sessions: Dict[str, CollaborationSession] = {}
        self._comment_counter = 0

    async def start_session(
        self,
        project_id: str,
        owner_id: str,
        owner_email: str,
        owner_name: str
    ) -> CollaborationSession:
        """Start a new collaboration session"""
        session_id = f"collab:{project_id}"

        if session_id in self.sessions:
            return self.sessions[session_id]

        session = CollaborationSession(
            session_id=session_id,
            project_id=project_id,
            collaborators={
                owner_id: Collaborator(
                    user_id=owner_id,
                    email=owner_email,
                    full_name=owner_name,
                    role=CollaboratorRole.OWNER
                )
            }
        )

        self.sessions[session_id] = session
        logger.info(f"Started collaboration session: {session_id}")

        return session

    async def join_session(
        self,
        project_id: str,
        user_id: str,
        email: str,
        full_name: str,
        role: CollaboratorRole = CollaboratorRole.VIEWER
    ) -> Optional[CollaborationSession]:
        """Join an existing collaboration session"""
        session_id = f"collab:{project_id}"

        if session_id not in self.sessions:
            return None

        session = self.sessions[session_id]

        # Add collaborator
        session.collaborators[user_id] = Collaborator(
            user_id=user_id,
            email=email,
            full_name=full_name,
            role=role
        )

        # Join WebSocket room
        await self.ws.manager.join_room(user_id, session_id)

        # Notify other collaborators
        await self._broadcast_presence(
            session,
            MessageType.USER_JOINED,
            user_id,
            {
                "user_id": user_id,
                "name": full_name,
                "role": role.value
            }
        )

        logger.info(f"User {user_id} joined session {session_id}")

        return session

    async def leave_session(
        self,
        project_id: str,
        user_id: str
    ) -> None:
        """Leave a collaboration session"""
        session_id = f"collab:{project_id}"

        if session_id not in self.sessions:
            return

        session = self.sessions[session_id]

        if user_id in session.collaborators:
            collaborator = session.collaborators[user_id]
            del session.collaborators[user_id]

            # Leave WebSocket room
            await self.ws.manager.leave_room(user_id, session_id)

            # Notify other collaborators
            await self._broadcast_presence(
                session,
                MessageType.USER_LEFT,
                user_id,
                {
                    "user_id": user_id,
                    "name": collaborator.full_name
                }
            )

        # Cleanup empty sessions (but keep owner's session)
        if not session.collaborators:
            del self.sessions[session_id]

    async def update_cursor(
        self,
        project_id: str,
        user_id: str,
        cursor_data: dict
    ) -> None:
        """Update user's cursor position for collaborative viewing"""
        session_id = f"collab:{project_id}"

        if session_id not in self.sessions:
            return

        session = self.sessions[session_id]

        if user_id in session.collaborators:
            session.collaborators[user_id].cursor_position = cursor_data
            session.collaborators[user_id].last_activity = datetime.utcnow()
            session.last_activity = datetime.utcnow()

            # Broadcast cursor update
            await self.ws.manager.broadcast_to_room(
                session_id,
                WebSocketMessage(
                    type=MessageType.PRESENCE_UPDATE,
                    data={
                        "user_id": user_id,
                        "cursor": cursor_data
                    },
                    room_id=session_id,
                    sender_id=user_id
                ),
                exclude_user=user_id
            )

    async def add_comment(
        self,
        project_id: str,
        user_id: str,
        user_name: str,
        content: str,
        target_type: str,
        target_id: str,
        parent_id: Optional[str] = None
    ) -> Comment:
        """Add a comment to a case or analysis"""
        session_id = f"collab:{project_id}"

        self._comment_counter += 1
        comment = Comment(
            id=f"comment_{self._comment_counter}",
            user_id=user_id,
            user_name=user_name,
            content=content,
            created_at=datetime.utcnow(),
            parent_id=parent_id,
            target_type=target_type,
            target_id=target_id
        )

        # Store in session if active
        if session_id in self.sessions:
            self.sessions[session_id].comments.append(comment)

            # Broadcast to collaborators
            await self.ws.manager.broadcast_to_room(
                session_id,
                WebSocketMessage(
                    type=MessageType.COMMENT_ADDED,
                    data={
                        "comment": {
                            "id": comment.id,
                            "user_id": comment.user_id,
                            "user_name": comment.user_name,
                            "content": comment.content,
                            "created_at": comment.created_at.isoformat(),
                            "parent_id": comment.parent_id,
                            "target_type": comment.target_type,
                            "target_id": comment.target_id
                        }
                    },
                    room_id=session_id,
                    sender_id=user_id
                )
            )

        return comment

    async def resolve_comment(
        self,
        project_id: str,
        comment_id: str,
        user_id: str
    ) -> bool:
        """Resolve a comment thread"""
        session_id = f"collab:{project_id}"

        if session_id not in self.sessions:
            return False

        session = self.sessions[session_id]

        for comment in session.comments:
            if comment.id == comment_id:
                comment.resolved = True

                # Broadcast resolution
                await self.ws.manager.broadcast_to_room(
                    session_id,
                    WebSocketMessage(
                        type=MessageType.PROJECT_UPDATE,
                        data={
                            "update_type": "comment_resolved",
                            "comment_id": comment_id,
                            "resolved_by": user_id
                        },
                        room_id=session_id,
                        sender_id=user_id
                    )
                )

                return True

        return False

    async def notify_case_saved(
        self,
        project_id: str,
        user_id: str,
        case_reference: str,
        case_data: dict
    ) -> None:
        """Notify collaborators when a case is saved"""
        session_id = f"collab:{project_id}"

        if session_id in self.sessions:
            await self.ws.manager.broadcast_to_room(
                session_id,
                WebSocketMessage(
                    type=MessageType.CASE_SAVED,
                    data={
                        "case_reference": case_reference,
                        "saved_by": user_id,
                        **case_data
                    },
                    room_id=session_id,
                    sender_id=user_id
                ),
                exclude_user=user_id
            )

    async def notify_note_update(
        self,
        project_id: str,
        user_id: str,
        case_reference: str,
        note_content: str
    ) -> None:
        """Notify collaborators of note updates"""
        session_id = f"collab:{project_id}"

        if session_id in self.sessions:
            await self.ws.manager.broadcast_to_room(
                session_id,
                WebSocketMessage(
                    type=MessageType.NOTE_UPDATED,
                    data={
                        "case_reference": case_reference,
                        "updated_by": user_id,
                        "note_preview": note_content[:200]  # First 200 chars
                    },
                    room_id=session_id,
                    sender_id=user_id
                ),
                exclude_user=user_id
            )

    def get_session(self, project_id: str) -> Optional[CollaborationSession]:
        """Get collaboration session for a project"""
        session_id = f"collab:{project_id}"
        return self.sessions.get(session_id)

    def get_active_collaborators(
        self,
        project_id: str
    ) -> List[dict]:
        """Get list of active collaborators"""
        session = self.get_session(project_id)
        if not session:
            return []

        return [
            {
                "user_id": c.user_id,
                "email": c.email,
                "name": c.full_name,
                "role": c.role.value,
                "cursor": c.cursor_position,
                "last_activity": c.last_activity.isoformat(),
                "is_active": c.is_active
            }
            for c in session.collaborators.values()
        ]

    def get_comments(
        self,
        project_id: str,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        include_resolved: bool = False
    ) -> List[dict]:
        """Get comments for a project"""
        session = self.get_session(project_id)
        if not session:
            return []

        comments = session.comments

        if target_type:
            comments = [c for c in comments if c.target_type == target_type]

        if target_id:
            comments = [c for c in comments if c.target_id == target_id]

        if not include_resolved:
            comments = [c for c in comments if not c.resolved]

        return [
            {
                "id": c.id,
                "user_id": c.user_id,
                "user_name": c.user_name,
                "content": c.content,
                "created_at": c.created_at.isoformat(),
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
                "parent_id": c.parent_id,
                "resolved": c.resolved,
                "target_type": c.target_type,
                "target_id": c.target_id
            }
            for c in comments
        ]

    async def _broadcast_presence(
        self,
        session: CollaborationSession,
        message_type: MessageType,
        sender_id: str,
        data: dict
    ) -> None:
        """Broadcast presence update to all collaborators"""
        # Include current collaborator list
        data["collaborators"] = [
            {
                "user_id": c.user_id,
                "name": c.full_name,
                "role": c.role.value
            }
            for c in session.collaborators.values()
        ]

        await self.ws.manager.broadcast_to_room(
            session.session_id,
            WebSocketMessage(
                type=message_type,
                data=data,
                room_id=session.session_id,
                sender_id=sender_id
            ),
            exclude_user=sender_id
        )
