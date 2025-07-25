from fastapi import Depends, HTTPException, status, APIRouter
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from handlers.auth_handlers import create_access_token, create_refresh_token, decode_refresh_token, verify_signature
from models import User

router = APIRouter()


class WalletLoginRequest(BaseModel):
    wallet_address: str
    signed_message: str
    message: str


class WalletLoginTestRequest(BaseModel):
    wallet_address: str
    private_key: str


@router.post("/login")
def login(request: WalletLoginRequest, db: Session = Depends(get_db)):
    # message = f"Sign this message to log in with your wallet: {request.wallet_address}"

    if not verify_signature(request.signed_message, request.wallet_address, request.message):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid message signature"
        )

    # Check if user exists
    user = db.query(User).filter(User.wallet_address == request.wallet_address).first()

    if not user:
        # Create new user if it doesn't exist
        user = User(wallet_address=request.wallet_address)
        db.add(user)
        db.commit()
        db.refresh(user)

    # Create JWT and refresh token
    access_token = create_access_token(data={"wallet_address": user.wallet_address})
    refresh_token = create_refresh_token(data={"wallet_address": user.wallet_address})

    # Optionally, store refresh token in DB
    user.refresh_token = refresh_token
    db.commit()

    return {"access_token": access_token, "refresh_token": refresh_token}


@router.post("/refresh-token")
def refresh_token(request: WalletLoginRequest, db: Session = Depends(get_db)):
    # Verify the refresh token
    payload = decode_refresh_token(request.signed_message)

    # Fetch the user and refresh token from the DB
    user = db.query(User).filter(User.wallet_address == payload['wallet_address']).first()
    if user is None or user.refresh_token != request.signed_message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid refresh token"
        )

    # Create new access token
    access_token = create_access_token(data={"wallet_address": user.wallet_address})

    return {"access_token": access_token}


@router.post("/test-login")
def test_auth_login(request: WalletLoginTestRequest, db: Session = Depends(get_db)):
    message = f"Sign this message to log in with your wallet: {request.wallet_address}"

    from eth_account import Account
    from eth_account.messages import encode_defunct

    msg = encode_defunct(text=message)
    signed_message = Account.sign_message(msg, private_key=request.private_key).signature.hex()
    print(signed_message)

    if not verify_signature(signed_message, request.wallet_address, message):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid message signature"
        )

    # Check if user exists
    user = db.query(User).filter(User.wallet_address == request.wallet_address).first()

    if not user:
        # Create new user if it doesn't exist
        user = User(wallet_address=request.wallet_address)
        db.add(user)
        db.commit()
        db.refresh(user)

    # Create JWT and refresh token
    access_token = create_access_token(data={"wallet_address": user.wallet_address})
    refresh_token = create_refresh_token(data={"wallet_address": user.wallet_address})

    # Optionally, store refresh token in DB
    user.refresh_token = refresh_token
    db.commit()

    return {"access_token": access_token, "refresh_token": refresh_token}
