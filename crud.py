from typing import Type, TypeVar, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import schemas
from database import get_db
from models import BaseModelC, BaseModelCU, User

T = TypeVar('T', bound=BaseModelC)

MAX_LIMIT = 1000


def get_item_by_id(db: Session, model: Type[T], item_id: int, include_deleted: bool = False) -> Optional[T]:
    """
    Retrieve an item by ID from the database.

    Args:
        db: SQLAlchemy database session.
        model: SQLAlchemy model class.
        item_id: ID of the item to retrieve.
        include_deleted: Whether to include soft-deleted items.

    Returns:
        The requested item or None if not found.
    """
    return model.get(db, id=item_id, include_deleted=include_deleted)


def get_items(db: Session, model: Type[T], skip: int = 0, limit: int = 100, include_deleted: bool = False) -> List[T]:
    """
    Retrieve a list of items with pagination.

    Args:
        db: SQLAlchemy database session.
        model: SQLAlchemy model class.
        skip: Number of items to skip (for pagination).
        limit: Maximum number of items to return.
        include_deleted: Whether to include soft-deleted items.

    Returns:
        List of items.
    """
    if limit > MAX_LIMIT:
        raise HTTPException(status_code=400, detail=f"Limit cannot exceed {MAX_LIMIT}")
    query = model.find(db, include_deleted=include_deleted)
    return query.offset(skip).limit(limit).all()


def create_item(db: Session, model: Type[T], schema: schemas.BaseCreate) -> T:
    """
    Create a new item in the database.

    Args:
        db: SQLAlchemy database session.
        model: SQLAlchemy model class.
        schema: Pydantic schema with item data.

    Returns:
        The created database item.

    Raises:
        HTTPException: If there's a database error during creation or invalid foreign key.
    """
    try:
        # Validate user_id for models with a user_id foreign key
        if hasattr(schema, 'user_id') and schema.user_id is not None:
            if not User.get(db, id=schema.user_id):
                raise HTTPException(status_code=400, detail="Invalid user_id")
        db_item = model(**schema.model_dump(exclude_unset=True, exclude_none=True, exclude_defaults=True))
        return db_item.save(db)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error creating {model.__tablename__}: {str(e)}")


def update_item(db: Session, model: Type[T], item_id: int, schema: schemas.BaseCreate) -> Optional[T]:
    """
    Update an existing item in the database.

    Args:
        db: SQLAlchemy database session.
        model: SQLAlchemy model class.
        item_id: ID of the item to update.
        schema: Pydantic schema with updated item data.

    Returns:
        The updated item or None if not found.

    Raises:
        HTTPException: If there's a database error during update or invalid foreign key.
    """
    try:
        db_item = model.get(db, id=item_id)
        if not db_item:
            return None
        # Validate user_id for models with a user_id foreign key
        if hasattr(schema, 'user_id') and schema.user_id is not None:
            if not User.get(db, id=schema.user_id):
                raise HTTPException(status_code=400, detail="Invalid user_id")
        # Use BaseModelCU's update method if available, otherwise manual update
        if isinstance(db_item, BaseModelCU):
            return db_item.update(db, **schema.model_dump(exclude_unset=True, exclude_none=True, exclude_defaults=True))
        else:
            for key, value in schema.model_dump(exclude_unset=True, exclude_none=True, exclude_defaults=True).items():
                setattr(db_item, key, value)
            return db_item.save(db)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error updating {model.__tablename__}: {str(e)}")


def delete_item(db: Session, model: Type[T], item_id: int) -> Optional[T]:
    """
    Soft-delete an item by ID.

    Args:
        db: SQLAlchemy database session.
        model: SQLAlchemy model class.
        item_id: ID of the item to soft-delete.

    Returns:
        The soft-deleted item or None if not found.
    """
    item = model.get(db, id=item_id)
    if not item:
        return None
    return item.delete(db)


def hard_delete_item(db: Session, model: Type[T], item_id: int) -> None:
    """
    Hard-delete an item by ID.

    Args:
        db: SQLAlchemy database session.
        model: SQLAlchemy model class.
        item_id: ID of the item to hard-delete.

    Returns:
        None.
    """
    item = model.get(db, id=item_id, include_deleted=True)
    if not item:
        return None
    return item.hard_delete(db)


def find_deleted(db: Session, model: Type[T]) -> List[T]:
    """
    Retrieve all soft-deleted items.

    Args:
        db: SQLAlchemy database session.
        model: SQLAlchemy model class.

    Returns:
        List of soft-deleted items.
    """
    return model.find_deleted(db)


def count_documents(db: Session, model: Type[T], include_deleted: bool = False) -> int:
    """
    Count items in the database.

    Args:
        db: SQLAlchemy database session.
        model: SQLAlchemy model class.
        include_deleted: Whether to include soft-deleted items.

    Returns:
        The number of items.
    """
    return model.count_documents(db, include_deleted=include_deleted)


def create_crud_router(model: Type[T], schema_create: Type[schemas.BaseCreate], schema_read: Type[schemas.Base]):
    """
    Create a FastAPI CRUD router for a given model.

    Args:
        model: SQLAlchemy model class.
        schema_create: Pydantic schema for creating items.
        schema_read: Pydantic schema for reading items.

    Returns:
        FastAPI APIRouter with CRUD endpoints.
    """
    router = APIRouter(
        prefix=f"/{model.__tablename__}",
        tags=[model.__tablename__],
    )

    @router.post("", response_model=schema_read)
    def create_item_endpoint(item: schema_create, db: Session = Depends(get_db)):
        return create_item(db=db, model=model, schema=item)

    @router.get("", response_model=List[schema_read])
    def read_items(skip: int = 0, limit: int = 100, include_deleted: bool = False, db: Session = Depends(get_db)):
        if limit > MAX_LIMIT:
            raise HTTPException(status_code=400, detail=f"Limit cannot exceed {MAX_LIMIT}")
        return get_items(db, model=model, skip=skip, limit=limit, include_deleted=include_deleted)

    @router.get("/{item_id}", response_model=schema_read)
    def read_item(item_id: int, include_deleted: bool = False, db: Session = Depends(get_db)):
        db_item = get_item_by_id(db, model=model, item_id=item_id, include_deleted=include_deleted)
        if db_item is None:
            raise HTTPException(status_code=404, detail=f"{model.__tablename__.capitalize()} not found")
        return db_item

    @router.put("/{item_id}", response_model=schema_read)
    def update_item_endpoint(item_id: int, item: schema_create, db: Session = Depends(get_db)):
        db_item = update_item(db, model=model, item_id=item_id, schema=item)
        if db_item is None:
            raise HTTPException(status_code=404, detail=f"{model.__tablename__.capitalize()} not found")
        return db_item

    @router.delete("/{item_id}", response_model=schema_read)
    def soft_delete_item(item_id: int, db: Session = Depends(get_db)):
        db_item = delete_item(db, model=model, item_id=item_id)
        if db_item is None:
            raise HTTPException(status_code=404, detail=f"{model.__tablename__.capitalize()} not found")
        return db_item

    @router.delete("/{item_id}/hard", status_code=204)
    def hard_delete_item_endpoint(item_id: int, db: Session = Depends(get_db)):
        hard_delete_item(db, model=model, item_id=item_id)
        return None

    @router.get("/deleted", response_model=List[schema_read])
    def read_deleted_items(db: Session = Depends(get_db)):
        return find_deleted(db, model=model)

    @router.get("/count", response_model=int)
    def count_items(include_deleted: bool = False, db: Session = Depends(get_db)):
        return count_documents(db, model=model, include_deleted=include_deleted)

    return router
