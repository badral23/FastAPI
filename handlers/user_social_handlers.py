from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from validators import validate_unique_social_handle


def create_user_social_with_validation(db: Session, model, schema):
    """
    Custom create handler for UserSocial with validation.
    """
    validate_unique_social_handle(db, schema)
    try:
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
    existing_item = db.query(model).filter(model.id == item_id).first()
    if not existing_item:
        return None
    if (hasattr(schema, 'handle') and schema.handle and
            existing_item.handle != schema.handle):
        validate_unique_social_handle(db, schema, exclude_id=item_id)
    try:
        update_data = schema.model_dump(exclude_unset=True, exclude_none=True, exclude_defaults=True)
        for key, value in update_data.items():
            if hasattr(existing_item, key):
                setattr(existing_item, key, value)
        db.add(existing_item)
        db.commit()
        db.refresh(existing_item)
        return existing_item
    except IntegrityError as e:
        db.rollback()
        if "duplicate key" in str(e).lower() or "unique constraint" in str(e).lower():
            raise HTTPException(status_code=409, detail="Social handle already exists")
        raise HTTPException(status_code=400, detail=f"Database constraint violation: {str(e)}")
