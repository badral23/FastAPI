from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from validators import validate_unique_social_handle


def create_user_social_with_validation(db: Session, model, schema):
    """
    Custom create handler for UserSocial with validation.
    """
    # Validate unique social handle
    validate_unique_social_handle(db, schema)

    try:
        # Create the social account
        item_data = schema.model_dump(exclude_unset=True, exclude_none=True, exclude_defaults=True)
        db_item = model(**item_data)
        return db_item.save(db)

    except IntegrityError as e:
        db.rollback()
        if "duplicate key" in str(e).lower() or "unique constraint" in str(e).lower():
            raise HTTPException(status_code=409, detail="Social handle already exists")
        raise HTTPException(status_code=400, detail=f"Database constraint violation: {str(e)}")


def update_user_social_with_validation(db: Session, model, item_id: int, schema):
    """
    Custom update handler for UserSocial with validation.
    """
    existing_item = model.get(db, id=item_id)
    if not existing_item:
        return None

    # Validate uniqueness if handle is being updated
    if (hasattr(schema, 'social_handle') and schema.social_handle and
            existing_item.social_handle != schema.social_handle):
        validate_unique_social_handle(db, schema, exclude_id=item_id)

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
            raise HTTPException(status_code=409, detail="Social handle already exists")
        raise HTTPException(status_code=400, detail=f"Database constraint violation: {str(e)}")
