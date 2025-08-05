from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from handlers.auth_handlers import get_current_user
from models import User
from schemas import BoxStatsResponse
from services.box_service import BoxOpeningService

router = APIRouter()


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
        ).first()

        if not next_box:
            # No boxes available
            raise HTTPException(status_code=404, detail="No boxes available")

        # Check if user can open boxes
        can_open = current_user.key_count > 0
        # User needs at least 1 key

        return {
            "next_box": {
                "reward_type": next_box.reward_type,
                "reward_tier": next_box.reward_tier,
                "reward_description": next_box.reward_description
            },
            "can_open": can_open,
            # Whether user has keys to open
            "user_keys": current_user.key_count,
            # Show user's current key count
            "message": f"Next available box is #{next_box.id}",
            "instructions": "Use POST /open to open the next available box, or specify box.id to open a specific box" if can_open else "You need keys to open boxes. Complete social tasks or verify NFT ownership to earn keys."
        }

    except Exception as e:
        # Handle errors
        raise HTTPException(status_code=500, detail="Error getting next available box")
