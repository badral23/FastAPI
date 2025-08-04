from typing import List

from fastapi import Depends, HTTPException, status, APIRouter
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from database import get_db
from handlers.auth_handlers import get_current_user
from handlers.nft_handlers import check_user_nfts
from models import User, UserNFT, SupportedNFTCollection, UserSocial
from schemas import UserSchema, UserNFTSchema, UserSocialSchema

router = APIRouter()


class SocialRequest(BaseModel):
    platform: str
    handle: str = None


@router.get("/me", response_model=UserSchema)
async def get_current_user_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/socials", response_model=List[UserSocialSchema])
async def get_my_socials(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    socials = db.query(UserSocial).filter(
        UserSocial.user_id == current_user.id,
        UserSocial.deleted.is_(False)
    ).all()
    return socials


@router.get("/keys")
async def get_my_keys(current_user: User = Depends(get_current_user)):
    return {
        "wallet_address": current_user.wallet_address,
        "key_count": current_user.key_count,
        "user_id": current_user.id
    }


@router.get("/nfts", response_model=List[UserNFTSchema])
async def get_my_nfts(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    nfts = db.query(UserNFT).filter(
        UserNFT.user_id == current_user.id,
        UserNFT.deleted.is_(False)
    ).all()
    return nfts


@router.post("/nfts/check-nfts")
async def check_nfts_for_user(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    # Get all supported NFT collection addresses
    nft_collections = db.query(SupportedNFTCollection.collection_address).all()
    nft_collections = [collection.collection_address for collection in nft_collections]

    # Check what NFTs the user owns
    owned_nfts = check_user_nfts(current_user.wallet_address, nft_collections)

    if not owned_nfts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,  # ← Fixed: was HTTP_400_NOT_FOUND
            detail="User does not own any NFTs from the specified collections"
        )

    new_nfts = []

    # Process each owned NFT
    for nft in owned_nfts:
        # Check if this NFT is already recorded for this user
        existing_nft = db.query(UserNFT).filter(
            UserNFT.user_id == current_user.id,
            UserNFT.nft_collection == nft['collection'],
            UserNFT.nft_id == nft['nft_id'],
            UserNFT.deleted == False  # ← Added: check deleted status
        ).first()

        if existing_nft:
            # NFT already recorded, skip
            continue
        else:
            # Record new NFT
            user_nft = UserNFT(
                user_id=current_user.id,
                nft_collection=nft['collection'],
                nft_id=nft['nft_id'],
                used=False  # ← Changed: NFTs start as unused, not used=True
            )
            db.add(user_nft)
            new_nfts.append(nft)

    # Calculate keys based on new NFTs found
    if new_nfts:
        # Award keys based on specification: 2-10 keys for NFT ownership
        if len(new_nfts) == 1:
            keys_to_add = 2  # Minimum 2 keys for 1 NFT
        else:
            keys_to_add = min(len(new_nfts), 10)  # Max 10 keys total

        current_user.key_count += keys_to_add
        db.commit()
        db.refresh(current_user)

        return {
            "message": f"Found {len(new_nfts)} new NFTs! Earned {keys_to_add} keys.",
            "new_nfts_found": len(new_nfts),
            "keys_earned": keys_to_add,
            "total_key_count": current_user.key_count,
            "nfts": new_nfts
        }
    else:
        return {
            "message": "No new NFTs found. All your NFTs are already recorded.",
            "new_nfts_found": 0,
            "keys_earned": 0,
            "total_key_count": current_user.key_count,
            "total_owned_nfts": len(owned_nfts)
        }


@router.post("/nfts/check-nfts-test")
async def check_nfts_for_user_test(
        db: Session = Depends(get_db),
):
    nft_collections = db.query(SupportedNFTCollection.collection_address).all()
    nft_collections = [collection.collection_address for collection in nft_collections]
    wallet_address = "0x3989BCC4a9A4E356265AcC658fB10Dfb3a86ddd7"

    owned_nfts = check_user_nfts(wallet_address, nft_collections)

    return {
        "message": f"Owned NFTs: {owned_nfts}",
    }


@router.post("/socials")
async def add_social(
        social: SocialRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    valid_platforms = ["twitter", "discord", "telegram"]

    if social.platform not in valid_platforms:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid platform. Choose from 'twitter', 'discord', or 'telegram'."
        )

    existing_social = db.query(UserSocial).filter(
        UserSocial.user_id == current_user.id,
        UserSocial.platform == social.platform
    ).first()

    if existing_social:
        return JSONResponse(
            content={"message": f"{social.platform.capitalize()} handle is already connected."},
            status_code=status.HTTP_409_CONFLICT
        )

    new_social = UserSocial(
        user_id=current_user.id,
        platform=social.platform,
        handle=social.handle
    )
    db.add(new_social)
    db.commit()

    connected_socials = db.query(UserSocial).filter(
        UserSocial.user_id == current_user.id,
        UserSocial.platform.in_(valid_platforms)
    ).count()

    if connected_socials == 3:
        current_user.key_count += 1
        db.commit()

        return JSONResponse(
            content={"message": f"Congratulations! All three socials are now connected! You’ve earned 1 key."},
            status_code=status.HTTP_200_OK
        )

    return JSONResponse(
        content={"message": f"{social.platform.capitalize()} handle added successfully!"},
        status_code=status.HTTP_201_CREATED
    )
