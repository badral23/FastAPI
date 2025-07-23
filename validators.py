from fastapi import HTTPException
from sqlalchemy.orm import Session

from models import UserSocial, User


def validate_unique_social_handle(db: Session, schema, exclude_id: int = None) -> None:
    """
    Validate that social handle is unique across the platform.

    Args:
        db: Database session
        schema: UserSocialCreateSchema instance
        exclude_id: ID to exclude from uniqueness check (for updates)

    Raises:
        HTTPException: If social handle already exists
    """
    if not (hasattr(schema, 'handle') and schema.handle):
        return

    query = db.query(UserSocial).filter(
        UserSocial.handle == schema.handle,
        UserSocial.platform == getattr(schema, 'platform', None),
        UserSocial.deleted.is_(False)
    )

    # Exclude current item for updates
    if exclude_id:
        query = query.filter(UserSocial.id != exclude_id)

    existing_social = query.first()

    if existing_social:
        raise HTTPException(
            status_code=409,
            detail=f"Social handle '{schema.handle}' is already registered on {schema.platform}"
        )


def validate_unique_wallet_address(db: Session, schema, exclude_id: int = None) -> None:
    """
    Validate that wallet address is unique across the platform.

    Args:
        db: Database session
        schema: Schema instance containing wallet_address
        exclude_id: ID to exclude from uniqueness check (for updates)

    Raises:
        HTTPException: If wallet address already exists
    """
    if not (hasattr(schema, 'wallet_address') and schema.wallet_address):
        return

    query = db.query(User).filter(
        User.wallet_address == schema.wallet_address,
        User.deleted.is_(False)
    )

    # Exclude current user for updates
    if exclude_id:
        query = query.filter(User.id != exclude_id)

    existing_user = query.first()

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail=f"Wallet address '{schema.wallet_address}' is already registered"
        )
