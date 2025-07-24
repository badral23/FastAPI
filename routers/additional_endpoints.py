from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import UserSocial, UserNFT, User
from schemas import UserSocialSchema, UserNFTSchema, UserSchema

additional_router = APIRouter()


# Helper functions
def get_user_by_wallet(db: Session, wallet_address: str) -> Optional[User]:
    """Get user by wallet address (try multiple search methods)"""
    # Clean the wallet address
    clean_address = wallet_address.strip()

    # Try exact match first
    user = db.query(User).filter(
        User.wallet_address == clean_address,
        User.deleted.is_(False)
    ).first()

    if user:
        return user

    # Try case-insensitive search if exact match fails
    try:
        user = db.query(User).filter(
            User.wallet_address.ilike(clean_address),
            User.deleted.is_(False)
        ).first()

        if user:
            return user
    except Exception:
        # If ilike fails, fall back to case-insensitive Python comparison
        pass

    # Fallback: Get all users and compare in Python (for debugging)
    all_users = db.query(User).filter(User.deleted.is_(False)).all()
    for user in all_users:
        if user.wallet_address and user.wallet_address.lower() == clean_address.lower():
            return user

    return None



def get_user_by_wallet_or_404(db: Session, wallet_address: str) -> User:
    """Get user by wallet address or raise 404"""
    user = get_user_by_wallet(db, wallet_address)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# Existing endpoints (by user ID)
@additional_router.get("/users/{user_id}/socials", response_model=List[UserSocialSchema])
async def get_user_socials(user_id: int, db: Session = Depends(get_db)):
    socials = db.query(UserSocial).filter(
        UserSocial.user_id == user_id,
        UserSocial.deleted.is_(False)
    ).all()
    return socials


@additional_router.get("/users/{user_id}/nfts", response_model=List[UserNFTSchema])
async def get_user_nfts(user_id: int, db: Session = Depends(get_db)):
    nfts = db.query(UserNFT).filter(
        UserNFT.user_id == user_id,
        UserNFT.deleted.is_(False)
    ).all()
    return nfts


# New wallet-based endpoints
@additional_router.get("/users/wallet/{wallet_address}", response_model=UserSchema)
async def get_user_by_wallet_address(wallet_address: str, db: Session = Depends(get_db)):
    """Get user by wallet address"""
    user = get_user_by_wallet_or_404(db, wallet_address)
    return user


@additional_router.get("/users/wallet/{wallet_address}/nfts", response_model=List[UserNFTSchema])
async def get_user_nfts_by_wallet(wallet_address: str, db: Session = Depends(get_db)):
    """Get user's NFTs by wallet address"""
    user = get_user_by_wallet_or_404(db, wallet_address)

    nfts = db.query(UserNFT).filter(
        UserNFT.user_id == user.id,
        UserNFT.deleted.is_(False)
    ).all()

    return nfts


@additional_router.get("/users/wallet/{wallet_address}/socials", response_model=List[UserSocialSchema])
async def get_user_socials_by_wallet(wallet_address: str, db: Session = Depends(get_db)):
    """Get user's social accounts by wallet address"""
    user = get_user_by_wallet_or_404(db, wallet_address)

    socials = db.query(UserSocial).filter(
        UserSocial.user_id == user.id,
        UserSocial.deleted.is_(False)
    ).all()

    return socials


@additional_router.get("/users/wallet/{wallet_address}/keys")
async def get_user_keys_by_wallet(wallet_address: str, db: Session = Depends(get_db)):
    """Get user's key count by wallet address"""
    user = get_user_by_wallet_or_404(db, wallet_address)

    return {
        "wallet_address": wallet_address,
        "key_count": user.key_count,
        "user_id": user.id
    }


@additional_router.get("/users/wallet/{wallet_address}/campaign-status")
async def get_campaign_status(wallet_address: str, db: Session = Depends(get_db)):
    """Get user's Hii Box campaign status"""
    user = get_user_by_wallet_or_404(db, wallet_address)
    print("sda")
    # Count user's NFTs
    nft_count = db.query(UserNFT).filter(
        UserNFT.user_id == user.id,
        UserNFT.deleted.is_(False)
    ).count()

    # Count user's social accounts
    social_count = db.query(UserSocial).filter(
        UserSocial.user_id == user.id,
        UserSocial.deleted.is_(False)
    ).count()

    return {
        "wallet_address": wallet_address,
        "user_id": user.id,
        "keys_collected": user.key_count,
        "nft_count": nft_count,
        "social_count": social_count,
        "boxes_claimed": 0,  # TODO: implement when Box model exists
        "boxes_opened": 0,  # TODO: implement when Box model exists
        "social_verified": social_count > 0,  # Basic check
        "nft_verified": nft_count > 0,  # Basic check
        "created_at": user.created_at,
        "updated_at": user.updated_at
    }


# Social handle availability check
@additional_router.get("/socials/check/{platform}/{handle}")
async def check_social_handle_availability(
        platform: str,
        handle: str,
        db: Session = Depends(get_db)
):
    existing = db.query(UserSocial).filter(
        UserSocial.handle == handle,
        UserSocial.platform == platform,
        UserSocial.deleted.is_(False)
    ).first()

    return {
        "platform": platform,
        "handle": handle,
        "available": existing is None,
        "message": "Handle is available" if existing is None else "Handle is already taken"
    }


# Wallet address availability check
@additional_router.get("/users/check-wallet/{wallet_address}")
async def check_wallet_availability(wallet_address: str, db: Session = Depends(get_db)):
    """Check if wallet address is available (not registered)"""
    existing_user = get_user_by_wallet(db, wallet_address)

    return {
        "wallet_address": wallet_address,
        "available": existing_user is None,
        "message": "Wallet is available" if existing_user is None else "Wallet is already registered",
        "user_exists": existing_user is not None
    }


# Debug endpoint to troubleshoot wallet search
@additional_router.get("/debug/wallets")
async def debug_wallets(db: Session = Depends(get_db)):
    """Debug endpoint to see all wallet addresses"""
    users = db.query(User).filter(User.deleted.is_(False)).all()

    return {
        "total_users": len(users),
        "wallet_addresses": [
            {
                "id": user.id,
                "wallet_address": user.wallet_address,
                "wallet_length": len(user.wallet_address or ""),
                "has_spaces": " " in (user.wallet_address or ""),
                "starts_with": (user.wallet_address or "")[:10] if user.wallet_address else None
            }
            for user in users
        ]
    }


@additional_router.get("/debug/wallet-search/{wallet_address}")
async def debug_wallet_search(wallet_address: str, db: Session = Depends(get_db)):
    """Debug specific wallet search"""
    # Try exact match
    exact_match = db.query(User).filter(
        User.wallet_address == wallet_address,
        User.deleted.is_(False)
    ).first()

    # Try case-insensitive match
    ilike_match = db.query(User).filter(
        User.wallet_address.ilike(wallet_address),
        User.deleted.is_(False)
    ).first()

    # Try with trimmed spaces
    trimmed_match = db.query(User).filter(
        User.wallet_address.ilike(wallet_address.strip()),
        User.deleted.is_(False)
    ).first()

    return {
        "searched_wallet": wallet_address,
        "searched_length": len(wallet_address),
        "exact_match_found": exact_match is not None,
        "ilike_match_found": ilike_match is not None,
        "trimmed_match_found": trimmed_match is not None,
        "exact_match_user": exact_match.id if exact_match else None,
        "ilike_match_user": ilike_match.id if ilike_match else None,
        "trimmed_match_user": trimmed_match.id if trimmed_match else None
    }