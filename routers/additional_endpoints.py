from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from handlers.auth_handlers import get_current_user
from models import UserSocial, UserNFT, User, Box

additional_router = APIRouter()


# NOW ALL ENDPOINTS REQUIRE AUTHENTICATION
@additional_router.get("/socials/check/{platform}/{handle}")
async def check_social_handle_availability(
        platform: str,
        handle: str,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)  # ← Added authentication
):
    """Check if social handle is available (now requires auth)"""
    existing = db.query(UserSocial).filter(
        UserSocial.handle == handle,
        UserSocial.platform == platform,
        UserSocial.deleted.is_(False)
    ).first()

    return {
        "platform": platform,
        "handle": handle,
        "available": existing is None,
        "message": "Handle is available" if existing is None else "Handle is already taken",
        "checked_by": current_user.wallet_address  # Show who checked
    }


@additional_router.get("/users/me/campaign-status")
async def get_my_campaign_status(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Get current user's Hii Box campaign status"""
    # Count user's NFTs
    nft_count = db.query(UserNFT).filter(
        UserNFT.user_id == current_user.id,
        UserNFT.deleted.is_(False)
    ).count()

    # Count user's social accounts
    social_count = db.query(UserSocial).filter(
        UserSocial.user_id == current_user.id,
        UserSocial.deleted.is_(False)
    ).count()

    # Count user's owned boxes
    owned_boxes_count = db.query(Box).filter(
        Box.owned_by_user_id == current_user.id,
        # Changed from opened_by_user_id
        Box.is_opened == True,
        Box.deleted.is_(False)
    ).count()

    return {
        "wallet_address": current_user.wallet_address,
        "user_id": current_user.id,
        "keys_collected": current_user.key_count,
        "nft_count": nft_count,
        "social_count": social_count,
        "boxes_claimed": 0,  # TODO: implement when box claiming is added
        "boxes_owned": owned_boxes_count,
        # Changed from boxes_opened
        "social_verified": social_count > 0,
        "nft_verified": nft_count > 0,
        "created_at": current_user.created_at,
        "updated_at": current_user.updated_at
    }