# Updated routers/router.py using ORM and new schemas

from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from handlers.auth_handlers import get_current_user
from models import User
from schemas import (
    BoxAssignmentRequest,
    BoxOpenRequest,
    BoxAssignmentResponse,
    BoxOpenResponse,
    UserAssignedBoxesResponse,
    BoxStatsResponse
)
from services.box_service import BoxOpeningService

router = APIRouter()


@router.post("/assign-from-nft", response_model=BoxAssignmentResponse)
async def assign_box_from_nft(
        request: BoxAssignmentRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Assign a box to user after they send their box NFT to the contract.

    This endpoint should be called after the user transfers their box NFT
    to your contract/wallet. The NFT token ID corresponds to the box position.

    Args:
        request: Contains nft_token_id and transaction_hash

    Returns:
        Box assignment confirmation with box details (without revealing rewards)
    """
    return BoxOpeningService.verify_nft_ownership_and_assign(
        current_user,
        request.nft_token_id,
        request.transaction_hash,
        db
    )


@router.post("/open", response_model=BoxOpenResponse)
async def open_assigned_box(
        request: BoxOpenRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Open a box that has already been assigned to the authenticated user.

    User must have already sent their box NFT and had the box assigned
    before they can open it to see the rewards.

    Args:
        request: Contains box_position to open

    Returns:
        Box opening result with full reward information
    """
    return BoxOpeningService.open_assigned_box(current_user, request.box_position, db)


@router.get("/my-boxes", response_model=UserAssignedBoxesResponse)
async def get_my_assigned_boxes(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Get all boxes assigned to the authenticated user.

    Shows both opened and unopened boxes. For unopened boxes,
    reward details are hidden until the box is opened.

    Returns:
        List of assigned boxes with their status and reward info (if opened)
    """
    return BoxOpeningService.get_user_assigned_boxes(current_user, db)


@router.get("/my-opened", response_model=Dict[str, Any])
async def get_my_opened_boxes(
        limit: int = Query(50, ge=1, le=100, description="Number of boxes to return"),
        offset: int = Query(0, ge=0, description="Number of boxes to skip"),
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Get list of boxes opened by the authenticated user with pagination.

    Args:
        limit: Maximum number of boxes to return (1-100)
        offset: Number of boxes to skip for pagination

    Returns:
        Paginated list of opened boxes with full reward details
    """
    # Get all user's boxes and filter opened ones
    all_boxes_result = BoxOpeningService.get_user_assigned_boxes(current_user, db)
    opened_boxes = [box for box in all_boxes_result["boxes"] if box["status"] == "opened"]

    # Apply pagination
    total_opened = len(opened_boxes)
    paginated_boxes = opened_boxes[offset:offset + limit]

    return {
        "boxes": paginated_boxes,
        "pagination": {
            "total": total_opened,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total_opened
        },
        "user": {
            "id": current_user.id,
            "wallet_address": current_user.wallet_address,
            "total_boxes_opened": total_opened
        }
    }


@router.get("/stats", response_model=BoxStatsResponse)
async def get_box_opening_stats(
        db: Session = Depends(get_db)
):
    """
    Get overall box opening statistics.
    PUBLIC ENDPOINT - No authentication required.

    Shows global stats including:
    - Total boxes in system
    - Number of boxes assigned to users
    - Number of boxes opened
    - Number of unassigned boxes
    - Assignment and opening percentages
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

    Keys are no longer used for opening boxes in the new system,
    but this endpoint is kept for backward compatibility.

    Returns:
        Detailed breakdown of user's available keys based on social and NFT verification
    """
    return BoxOpeningService.calculate_user_keys(current_user, db)


@router.get("/next-available")
async def get_next_available_box(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Get information about unassigned boxes available for assignment.

    In the new system, users choose which box to get by sending the
    corresponding NFT token ID, so this shows available options.

    Returns:
        Information about unassigned boxes (without revealing rewards)
    """
    try:
        from models import Box

        # Get some unassigned boxes (limit to prevent huge responses)
        unassigned_boxes = db.query(Box).filter(
            Box.assigned_to_user_id.is_(None),
            Box.deleted == False
        ).order_by(Box.position).limit(100).all()

        if not unassigned_boxes:
            raise HTTPException(status_code=404, detail="No boxes available for assignment")

        boxes_info = []
        for box in unassigned_boxes:
            boxes_info.append({
                "position": box.position,
                "reward_type": box.reward_type,
                "reward_tier": box.reward_tier,
                "reward_description": box.reward_description,
                "nft_token_id": str(box.position)  # Token ID matches position
            })

        return {
            "available_boxes": boxes_info[:10],  # Show first 10
            "total_available": len(unassigned_boxes),
            "message": f"Send NFT token ID (1-50000) to get the corresponding box assigned to you",
            "instructions": "Transfer your box NFT to our contract, then call /assign-from-nft with the token ID and transaction hash"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail="Error getting available boxes")


@router.get("/user/{user_id}/boxes", response_model=Dict[str, Any])
async def get_user_boxes_admin(
        user_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Admin endpoint to get boxes assigned to any user.

    TODO: Add admin role verification

    Args:
        user_id: ID of the user whose boxes to retrieve

    Returns:
        Specified user's assigned boxes
    """
    # TODO: Add admin role check
    # if not current_user.is_admin:
    #     raise HTTPException(status_code=403, detail="Admin access required")

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    return BoxOpeningService.get_user_assigned_boxes(target_user, db)


@router.post("/admin/assign-box", response_model=BoxAssignmentResponse)
async def admin_assign_box(
        user_id: int,
        box_position: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Admin endpoint to manually assign a box to a user.

    TODO: Add admin role verification

    Args:
        user_id: ID of the user to assign the box to
        box_position: Position of the box to assign

    Returns:
        Box assignment confirmation
    """
    # TODO: Add admin role check
    # if not current_user.is_admin:
    #     raise HTTPException(status_code=403, detail="Admin access required")

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    return BoxOpeningService.assign_box_to_user(target_user, str(box_position), db)


@router.get("/position/{position}")
async def get_box_by_position(
        position: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """
    Get information about a specific box by position.

    Shows assignment status and basic info. Reward details only
    shown if the box is opened and belongs to the requesting user.

    Args:
        position: Box position (1-50000)

    Returns:
        Box information with appropriate level of detail
    """
    try:
        from models import Box

        if position < 1 or position > 50000:
            raise HTTPException(status_code=400, detail="Invalid box position")

        box = db.query(Box).filter(
            Box.position == position,
            Box.deleted == False
        ).first()

        if not box:
            raise HTTPException(status_code=404, detail=f"Box #{position} not found")

        # Base info always visible
        box_info = {
            "id": box.id,
            "position": box.position,
            "reward_type": box.reward_type,
            "reward_tier": box.reward_tier,
            "reward_description": box.reward_description,
            "is_assigned": box.assigned_to_user_id is not None,
            "is_opened": box.is_opened
        }

        # Additional info based on ownership and status
        if box.assigned_to_user_id:
            box_info["assigned_at"] = box.assigned_at.isoformat() if box.assigned_at else None

            # Only show detailed reward info if opened and belongs to requesting user
            if box.is_opened and box.assigned_to_user_id == current_user.id:
                box_info.update({
                    "reward_data": box.reward_data,
                    "opened_at": box.opened_at.isoformat() if box.opened_at else None,
                    "full_reward_visible": True
                })
            else:
                box_info["full_reward_visible"] = False
        else:
            box_info.update({
                "status": "available_for_assignment",
                "nft_token_id": str(position),
                "instructions": f"Send NFT token #{position} to get this box assigned to you"
            })

        return box_info

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error retrieving box information")
