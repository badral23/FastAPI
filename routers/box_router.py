from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from handlers.auth_handlers import get_current_user
from models import User, Box
from services.box_service import BoxOpeningService

box_router = APIRouter()


@box_router.post("/open", response_model=Dict[str, Any])
async def open_box(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Open a box for the authenticated user.

    This endpoint:
    1. Calculates user's available keys (social + NFT verification)
    2. Atomically assigns the next available box
    3. Marks NFTs as used to prevent double-spending
    4. Returns the reward details

    Returns:
        dict: Box opening result with reward information
    """
    return BoxOpeningService.open_box(current_user, db)


@box_router.get("/my-opened", response_model=Dict[str, Any])
async def get_my_opened_boxes(
        limit: int = Query(50, ge=1, le=100, description="Number of boxes to return"),
        offset: int = Query(0, ge=0, description="Number of boxes to skip"),
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Get list of boxes opened by the authenticated user.

    Args:
        limit: Maximum number of boxes to return (1-100)
        offset: Number of boxes to skip for pagination

    Returns:
        dict: User's opened boxes with pagination info
    """
    return BoxOpeningService.get_user_opened_boxes(current_user, db, limit, offset)


@box_router.get("/stats", response_model=Dict[str, Any])
async def get_box_opening_stats(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Get overall box opening statistics.
    Requires authentication but shows global stats.

    Returns:
        dict: Global box opening statistics
    """
    return BoxOpeningService.get_box_opening_stats(db)


@box_router.get("/calculate-keys", response_model=Dict[str, Any])
async def calculate_available_keys(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Calculate available keys for the authenticated user without opening a box.
    Useful for frontend to show key count and requirements.

    Returns:
        dict: Detailed breakdown of user's available keys
    """
    return BoxOpeningService.calculate_user_keys(current_user, db)


@box_router.get("/next-available", response_model=Dict[str, Any])
async def get_next_available_box(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Get information about the next box that would be opened.
    Does not actually open the box.

    Returns:
        dict: Next available box information (without reward details)
    """
    try:
        # Get the next box that would be assigned
        next_box = db.query(Box).filter(
            Box.is_opened.is_(False),
            Box.deleted.is_(False)
        ).order_by(Box.position).first()

        if not next_box:
            raise HTTPException(status_code=404, detail="No boxes available")

        # Calculate user's keys
        key_info = BoxOpeningService.calculate_user_keys(current_user, db)

        return {
            "next_box": {
                "position": next_box.position,
                "reward_type": next_box.reward_type,
                "reward_tier": next_box.reward_tier,
                # Don't reveal exact reward details until opened
                "reward_description": next_box.reward_description
            },
            "can_open": key_info["total_available"] > 0,
            "key_info": key_info,
            "message": "This is the next box that will be opened" if key_info[
                                                                         "total_available"] > 0 else "Complete social tasks or verify NFT ownership to earn keys"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail="Error getting next available box")


@box_router.get("/user/{user_id}/opened", response_model=Dict[str, Any])
async def get_user_opened_boxes_admin(
        user_id: int,
        limit: int = Query(50, ge=1, le=100, description="Number of boxes to return"),
        offset: int = Query(0, ge=0, description="Number of boxes to skip"),
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Admin endpoint to get boxes opened by any user.

    TODO: Add admin role verification

    Args:
        user_id: ID of the user whose boxes to retrieve
        limit: Maximum number of boxes to return
        offset: Number of boxes to skip for pagination

    Returns:
        dict: Specified user's opened boxes
    """
    # TODO: Add admin role check
    # if not current_user.is_admin:
    #     raise HTTPException(status_code=403, detail="Admin access required")

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    return BoxOpeningService.get_user_opened_boxes(target_user, db, limit, offset)
