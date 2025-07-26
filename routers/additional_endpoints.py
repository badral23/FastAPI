# routers/additional_endpoints.py - All routes now authenticated

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from handlers.auth_handlers import get_current_user
from models import UserSocial, UserNFT, User
from schemas import UserSocialSchema, UserNFTSchema, UserSchema

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


@additional_router.get("/users/check-wallet/{wallet_address}")
async def check_wallet_availability(
        wallet_address: str,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)  # ← Added authentication
):
    """Check if wallet address is available (now requires auth)"""
    existing_user = get_user_by_wallet(db, wallet_address)
    return {
        "wallet_address": wallet_address,
        "available": existing_user is None,
        "message": "Wallet is available" if existing_user is None else "Wallet is already registered",
        "user_exists": existing_user is not None,
        "checked_by": current_user.wallet_address  # Show who checked
    }


# These were already authenticated - keeping as is
@additional_router.get("/users/me", response_model=UserSchema)
async def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Get current authenticated user's profile"""
    return current_user


@additional_router.get("/users/me/nfts", response_model=List[UserNFTSchema])
async def get_my_nfts(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Get current user's NFTs"""
    nfts = db.query(UserNFT).filter(
        UserNFT.user_id == current_user.id,
        UserNFT.deleted.is_(False)
    ).all()
    return nfts


@additional_router.get("/users/me/socials", response_model=List[UserSocialSchema])
async def get_my_socials(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Get current user's social accounts"""
    socials = db.query(UserSocial).filter(
        UserSocial.user_id == current_user.id,
        UserSocial.deleted.is_(False)
    ).all()
    return socials


@additional_router.get("/users/me/keys")
async def get_my_keys(current_user: User = Depends(get_current_user)):
    """Get current user's key count"""
    return {
        "wallet_address": current_user.wallet_address,
        "key_count": current_user.key_count,
        "user_id": current_user.id
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

    return {
        "wallet_address": current_user.wallet_address,
        "user_id": current_user.id,
        "keys_collected": current_user.key_count,
        "nft_count": nft_count,
        "social_count": social_count,
        "boxes_claimed": 0,  # TODO: implement when box claiming is added
        "boxes_opened": 0,  # TODO: implement when box opening is added
        "social_verified": social_count > 0,
        "nft_verified": nft_count > 0,
        "created_at": current_user.created_at,
        "updated_at": current_user.updated_at
    }


# Admin-only endpoints (if needed)
@additional_router.get("/admin/users/{user_id}/socials", response_model=List[UserSocialSchema])
async def admin_get_user_socials(
        user_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Admin endpoint to get any user's socials"""
    # TODO: Add admin role check
    # if not current_user.is_admin:
    #     raise HTTPException(status_code=403, detail="Admin access required")

    socials = db.query(UserSocial).filter(
        UserSocial.user_id == user_id,
        UserSocial.deleted.is_(False)
    ).all()
    return socials


# Helper functions (keep these)
def get_user_by_wallet(db: Session, wallet_address: str) -> Optional[User]:
    """Get user by wallet address (try multiple search methods)"""
    clean_address = wallet_address.strip()

    user = db.query(User).filter(
        User.wallet_address == clean_address,
        User.deleted.is_(False)
    ).first()

    if user:
        return user

    try:
        user = db.query(User).filter(
            User.wallet_address.ilike(clean_address),
            User.deleted.is_(False)
        ).first()
        if user:
            return user
    except Exception:
        pass

    all_users = db.query(User).filter(User.deleted.is_(False)).all()
    for user in all_users:
        if user.wallet_address and user.wallet_address.lower() == clean_address.lower():
            return user

    return None