from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import UserSocial, UserNFT
from schemas import UserSocialSchema, UserNFTSchema

additional_router = APIRouter()


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
