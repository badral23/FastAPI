from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from handlers.auth_handlers import get_current_user
from models import User
from schemas import BoxOpenRequest, BoxOpenResponse, BoxStatsResponse
from services.box_service import BoxOpeningService

router = APIRouter()


@router.post("/open", response_model=BoxOpenResponse)
async def open_box(
        request: BoxOpenRequest = BoxOpenRequest(),
        # Default empty request for next available
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Open a box for the authenticated user.

    If box_position is specified, opens that specific box (if available).
    If box_position is None, opens the next available box in sequence.

    Args:
        request: Contains optional box_position

    Returns:
        Box opening result with full reward information
    """
    # Check if user has enough keys to open a box
    if current_user.key_count <= 0:
        # User has no keys available
        raise HTTPException(
            status_code=403,
            detail="You don't have any keys to open boxes. Complete social tasks or verify NFT ownership to earn keys."
        )

    if request.box_position:
        # Open specific box
        return BoxOpeningService.open_specific_box(current_user, request.box_position, db)
    else:
        # Open next available box
        return BoxOpeningService.open_next_available_box(current_user, db)


@router.get("/my-owned", response_model=Dict[str, Any])
# Changed endpoint from /my-opened to /my-owned
async def get_my_owned_boxes(
        limit: int = Query(50, ge=1, le=100, description="Number of boxes to return"),
        # Limit results per page
        offset: int = Query(0, ge=0, description="Number of boxes to skip"),
        # Offset for pagination
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Get list of boxes owned by the authenticated user with pagination.
    (Changed from opened boxes to owned boxes)

    Args:
        limit: Maximum number of boxes to return (1-100)
        offset: Number of boxes to skip for pagination

    Returns:
        Paginated list of owned boxes with full reward details
    """
    result = BoxOpeningService.get_user_owned_boxes(current_user, db, limit, offset)
    # Changed method call

    # Add user info to response
    result["user"] = {
        "id": current_user.id,
        "wallet_address": current_user.wallet_address,
        "total_boxes_owned": result["total_owned"]
        # Changed from total_boxes_opened
    }

    return result


@router.get("/position/{position}")
async def get_box_by_position(
        position: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Get information about a specific box by position.

    Shows basic info and status. Full reward details only shown
    if the box is owned by the requesting user.

    Args:
        position: Box position (1-50000)

    Returns:
        Box information with appropriate level of detail
    """
    try:
        from models import Box

        # Validate position range
        if position < 1 or position > 50000:
            raise HTTPException(status_code=400, detail="Invalid box position")

        # Get box by position
        box = db.query(Box).filter(
            Box.position == position,
            Box.deleted == False
        ).first()

        if not box:
            # Box not found
            raise HTTPException(status_code=404, detail=f"Box #{position} not found")

        # Base info always visible
        box_info = {
            "id": box.id,
            "position": box.position,
            "reward_type": box.reward_type,
            "reward_tier": box.reward_tier,
            "reward_description": box.reward_description,
            "is_opened": box.is_opened,
            "user_can_open": current_user.key_count > 0 and not box.is_opened
            # Show if user can open this specific box
        }

        if box.is_opened:
            # Box has been opened (now owned by someone)
            box_info["opened_at"] = box.opened_at.isoformat() if box.opened_at else None

            # Only show full rewards if user owns this box
            if box.owned_by_user_id == current_user.id:
                # Changed from opened_by_user_id
                box_info.update({
                    "reward_data": box.reward_data,
                    "full_reward_visible": True,
                    "owned_by_me": True
                    # Changed from opened_by_me
                })
            else:
                box_info.update({
                    "full_reward_visible": False,
                    "owned_by_me": False,
                    # Changed from opened_by_me
                    "message": "Box owned by another user"
                    # Changed from "opened by another user"
                })
        else:
            # Box is still available
            if current_user.key_count > 0:
                # User has keys to open
                box_info.update({
                    "status": "available",
                    "message": f"Box #{position} is available to open"
                })
            else:
                # User has no keys
                box_info.update({
                    "status": "available_but_no_keys",
                    "message": f"Box #{position} is available but you need keys to open it"
                })

        return box_info

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Handle other errors
        raise HTTPException(status_code=500, detail="Error retrieving box information")

@router.get("/stats", response_model=BoxStatsResponse)
async def get_box_opening_stats(db: Session = Depends(get_db)):
    """
    Get overall box opening statistics.
    PUBLIC ENDPOINT - No authentication required.

    Shows global stats including:
    - Total boxes in system
    - Number of boxes opened
    - Number of available boxes
    - Opening percentage
    - Reward distribution breakdown
    """
    return BoxOpeningService.get_box_opening_stats(db)


@router.get("/calculate-keys", response_model=Dict[str, Any])
async def calculate_available_keys(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Calculate available keys for the authenticated user.

    Keys determine how many boxes the user can open based on:
    - Social verification (1 key for completing all 3 platforms)
    - NFT ownership (2-10 keys based on number of qualifying NFTs)

    Returns:
        Detailed breakdown of user's available keys
    """
    return BoxOpeningService.calculate_user_keys(current_user, db)


@router.get("/next-available")
async def get_next_available_box(
        current_user: User = Depends(get_current_user),
        # Add authentication to show personalized info
        db: Session = Depends(get_db)
):
    """
    Get information about the next available box to be opened.

    Shows whether user can open boxes based on their key count.

    Returns:
        Information about next box in sequence and user's ability to open it
    """
    try:
        from models import Box

        # Get next unopened box
        next_box = db.query(Box).filter(
            Box.is_opened == False,
            Box.deleted == False
        ).order_by(Box.position).first()

        if not next_box:
            # No boxes available
            raise HTTPException(status_code=404, detail="No boxes available")

        # Check if user can open boxes
        can_open = current_user.key_count > 0
        # User needs at least 1 key

        return {
            "next_box": {
                "position": next_box.position,
                "reward_type": next_box.reward_type,
                "reward_tier": next_box.reward_tier,
                "reward_description": next_box.reward_description
            },
            "can_open": can_open,
            # Whether user has keys to open
            "user_keys": current_user.key_count,
            # Show user's current key count
            "message": f"Next available box is #{next_box.position}",
            "instructions": "Use POST /open to open the next available box, or specify box_position to open a specific box" if can_open else "You need keys to open boxes. Complete social tasks or verify NFT ownership to earn keys."
        }

    except Exception as e:
        # Handle errors
        raise HTTPException(status_code=500, detail="Error getting next available box")