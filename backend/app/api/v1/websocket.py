"""
WebSocket API Routes
Real-time collaboration endpoints
"""

from typing import Optional, List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends, HTTPException
from pydantic import BaseModel

from app.services.auth import JWTHandler
from app.services.realtime import WebSocketManager, CollaborationService

router = APIRouter(tags=["WebSocket"])

# Initialize services
ws_manager = WebSocketManager()
jwt_handler = JWTHandler()
collaboration_service = CollaborationService(ws_manager)


class CollaboratorResponse(BaseModel):
    """Active collaborator info"""
    user_id: str
    name: str
    role: str
    is_active: bool


class CommentRequest(BaseModel):
    """Add comment request"""
    content: str
    target_type: str
    target_id: str
    parent_id: Optional[str] = None


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    rooms: Optional[str] = Query(None)  # Comma-separated room IDs
):
    """
    WebSocket connection for real-time updates.

    Query parameters:
    - token: JWT access token for authentication
    - rooms: Comma-separated list of rooms to join (e.g., "project:123,team:456")

    Message format (JSON):
    {
        "type": "message_type",
        "data": {...},
        "room_id": "optional_room_id"
    }

    Supported message types:
    - ping/pong: Heartbeat
    - join_room: Join a room {"room_id": "..."}
    - leave_room: Leave a room {"room_id": "..."}
    - typing_start/typing_stop: Typing indicators {"room_id": "..."}
    """
    # Authenticate
    if not token:
        await websocket.close(code=4001, reason="Authentication required")
        return

    payload = jwt_handler.verify_token(token, expected_type="access")
    if not payload:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    user_id = payload.user_id

    # Parse initial rooms
    initial_rooms: List[str] = []
    if rooms:
        initial_rooms = [r.strip() for r in rooms.split(",") if r.strip()]

    # Handle connection
    await ws_manager.handle_connection(
        websocket=websocket,
        user_id=user_id,
        initial_rooms=initial_rooms
    )


@router.get("/ws/status")
async def websocket_status():
    """
    Get WebSocket server status.
    """
    return {
        "active_connections": ws_manager.manager.get_active_user_count(),
        "total_rooms": len(ws_manager.manager.rooms),
        "status": "running"
    }


@router.get("/ws/rooms/{room_id}/users")
async def get_room_users(room_id: str):
    """
    Get users in a specific room.
    """
    users = ws_manager.manager.get_room_users(room_id)
    return {
        "room_id": room_id,
        "users": users,
        "count": len(users)
    }


# Collaboration endpoints
@router.post("/collaboration/{project_id}/join")
async def join_collaboration(
    project_id: str,
    token: str = Query(...)
):
    """
    Join a project collaboration session.
    """
    payload = jwt_handler.verify_token(token, expected_type="access")
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    session = await collaboration_service.join_session(
        project_id=project_id,
        user_id=payload.user_id,
        email=payload.email,
        full_name=payload.email.split("@")[0],  # Fallback name
        role=collaboration_service.CollaboratorRole.VIEWER
    )

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session.session_id,
        "project_id": project_id,
        "collaborators": collaboration_service.get_active_collaborators(project_id)
    }


@router.post("/collaboration/{project_id}/leave")
async def leave_collaboration(
    project_id: str,
    token: str = Query(...)
):
    """
    Leave a project collaboration session.
    """
    payload = jwt_handler.verify_token(token, expected_type="access")
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    await collaboration_service.leave_session(project_id, payload.user_id)

    return {"message": "Left collaboration session"}


@router.get("/collaboration/{project_id}/collaborators")
async def get_collaborators(project_id: str):
    """
    Get active collaborators for a project.
    """
    collaborators = collaboration_service.get_active_collaborators(project_id)
    return {
        "project_id": project_id,
        "collaborators": collaborators
    }


@router.post("/collaboration/{project_id}/comments")
async def add_comment(
    project_id: str,
    comment: CommentRequest,
    token: str = Query(...)
):
    """
    Add a comment to a case or analysis.
    """
    payload = jwt_handler.verify_token(token, expected_type="access")
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    new_comment = await collaboration_service.add_comment(
        project_id=project_id,
        user_id=payload.user_id,
        user_name=payload.email.split("@")[0],
        content=comment.content,
        target_type=comment.target_type,
        target_id=comment.target_id,
        parent_id=comment.parent_id
    )

    return {
        "id": new_comment.id,
        "content": new_comment.content,
        "created_at": new_comment.created_at.isoformat()
    }


@router.get("/collaboration/{project_id}/comments")
async def get_comments(
    project_id: str,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    include_resolved: bool = False
):
    """
    Get comments for a project.
    """
    comments = collaboration_service.get_comments(
        project_id=project_id,
        target_type=target_type,
        target_id=target_id,
        include_resolved=include_resolved
    )

    return {"comments": comments}


@router.post("/collaboration/{project_id}/comments/{comment_id}/resolve")
async def resolve_comment(
    project_id: str,
    comment_id: str,
    token: str = Query(...)
):
    """
    Resolve a comment thread.
    """
    payload = jwt_handler.verify_token(token, expected_type="access")
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    success = await collaboration_service.resolve_comment(
        project_id=project_id,
        comment_id=comment_id,
        user_id=payload.user_id
    )

    if not success:
        raise HTTPException(status_code=404, detail="Comment not found")

    return {"message": "Comment resolved"}
