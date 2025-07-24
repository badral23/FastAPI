from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from validators import validate_unique_wallet_address


def create_user_with_wallet_address_validation(db: Session, model, schema):
    """
    Custom create handler for User with wallet address validation.
    """
    # Validate unique wallet address
    validate_unique_wallet_address(db, schema)

    try:
        # Create the user
        item_data = schema.model_dump(exclude_unset=True, exclude_none=True, exclude_defaults=True)
        db_item = model(**item_data)
        return db_item.save(db)

    except IntegrityError as e:
        db.rollback()
        if "duplicate key" in str(e).lower() or "unique constraint" in str(e).lower():
            raise HTTPException(status_code=409, detail="Wallet address already exists")
        raise HTTPException(status_code=400, detail=f"Database constraint violation: {str(e)}")


def update_user_with_wallet_address_validation(db: Session, model, item_id: int, schema):
    """
    Custom update handler for User with wallet address validation.
    """
    existing_item = model.get(db, id=item_id)
    if not existing_item:
        return None

    # Validate uniqueness if wallet address is being updated
    if (hasattr(schema, 'wallet_address') and schema.wallet_address and
            existing_item.wallet_address != schema.wallet_address):
        validate_unique_wallet_address(db, schema, exclude_id=item_id)

    try:
        update_data = schema.model_dump(exclude_unset=True, exclude_none=True, exclude_defaults=True)

        if hasattr(existing_item, 'update'):
            return existing_item.update(db, **update_data)
        else:
            for key, value in update_data.items():
                if hasattr(existing_item, key):
                    setattr(existing_item, key, value)
            return existing_item.save(db)

    except IntegrityError as e:
        db.rollback()
        if "duplicate key" in str(e).lower() or "unique constraint" in str(e).lower():
            raise HTTPException(status_code=409, detail="Wallet address already exists")
        raise HTTPException(status_code=400, detail=f"Database constraint violation: {str(e)}")