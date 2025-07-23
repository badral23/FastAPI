import logging
from functools import lru_cache
from typing import Type, TypeVar, List, Optional, Callable, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

import schemas
from database import get_db
from models import BaseModelC, BaseModelCU, User

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModelC)


class CRUDConfig:
    MAX_LIMIT = 1000
    DEFAULT_LIMIT = 100
    CACHE_SIZE = 128


config = CRUDConfig()


class CRUDError(Exception):
    """Base exception for CRUD operations."""
    pass


class ValidationError(CRUDError):
    """Raised when validation fails."""
    pass


class NotFoundError(CRUDError):
    """Raised when an item is not found."""
    pass


def validate_pagination(skip: int, limit: int) -> None:
    """Validate pagination parameters."""
    if skip < 0:
        raise HTTPException(status_code=400, detail="Skip must be non-negative")
    if limit <= 0:
        raise HTTPException(status_code=400, detail="Limit must be positive")
    if limit > config.MAX_LIMIT:
        raise HTTPException(status_code=400, detail=f"Limit cannot exceed {config.MAX_LIMIT}")


@lru_cache(maxsize=config.CACHE_SIZE)
def validate_user_exists(db: Session, user_id: int) -> bool:
    """Cache user existence validation."""
    return User.get(db, id=user_id) is not None


def validate_foreign_keys(db: Session, schema: schemas.BaseCreate) -> None:
    """Validate foreign key constraints."""
    if hasattr(schema, 'user_id') and schema.user_id is not None:
        if not validate_user_exists(db, schema.user_id):
            raise ValidationError("Invalid user_id")


def get_item_by_id(
        db: Session,
        model: Type[T],
        item_id: int,
        include_deleted: bool = False
) -> Optional[T]:
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
    try:
        return model.get(db, id=item_id, include_deleted=include_deleted)
    except SQLAlchemyError as e:
        logger.error(f"Database error retrieving {model.__tablename__} {item_id}: {e}")
        raise HTTPException(status_code=500, detail="Database error")


def get_items(
        db: Session,
        model: Type[T],
        skip: int = 0,
        limit: int = None,
        include_deleted: bool = False,
        filters: Optional[Dict[str, Any]] = None
) -> List[T]:
    """
    Retrieve a list of items with pagination and optional filtering.

    Args:
        db: SQLAlchemy database session.
        model: SQLAlchemy model class.
        skip: Number of items to skip (for pagination).
        limit: Maximum number of items to return.
        include_deleted: Whether to include soft-deleted items.
        filters: Optional dictionary of filters to apply.

    Returns:
        List of items.
    """
    if limit is None:
        limit = config.DEFAULT_LIMIT

    validate_pagination(skip, limit)

    try:
        query = model.find(db, include_deleted=include_deleted)

        # Apply filters if provided
        if filters:
            for key, value in filters.items():
                if hasattr(model, key) and value is not None:
                    query = query.filter(getattr(model, key) == value)

        return query.offset(skip).limit(limit).all()
    except SQLAlchemyError as e:
        logger.error(f"Database error retrieving {model.__tablename__} items: {e}")
        raise HTTPException(status_code=500, detail="Database error")


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
        HTTPException: If there's a database error during creation or validation fails.
    """
    try:
        # Validate foreign keys
        validate_foreign_keys(db, schema)

        # Create the item
        item_data = schema.model_dump(exclude_unset=True, exclude_none=True, exclude_defaults=True)
        db_item = model(**item_data)

        return db_item.save(db)

    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error creating {model.__tablename__}: {e}")
        raise HTTPException(status_code=409, detail="Duplicate or constraint violation")
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error creating {model.__tablename__}: {e}")
        raise HTTPException(status_code=500, detail="Database error")


def update_item(
        db: Session,
        model: Type[T],
        item_id: int,
        schema: schemas.BaseCreate,
        partial: bool = False
) -> Optional[T]:
    """
    Update an existing item in the database.

    Args:
        db: SQLAlchemy database session.
        model: SQLAlchemy model class.
        item_id: ID of the item to update.
        schema: Pydantic schema with updated item data.
        partial: Whether this is a partial update (PATCH vs PUT).

    Returns:
        The updated item or None if not found.

    Raises:
        HTTPException: If there's a database error during update or validation fails.
    """
    try:
        # Get the existing item
        db_item = model.get(db, id=item_id)
        if not db_item:
            return None

        # Validate foreign keys
        validate_foreign_keys(db, schema)

        # Prepare update data
        exclude_unset = partial  # For PATCH, exclude unset fields
        update_data = schema.model_dump(
            exclude_unset=exclude_unset,
            exclude_none=True,
            exclude_defaults=exclude_unset
        )

        # Perform update
        if isinstance(db_item, BaseModelCU) and hasattr(db_item, 'update'):
            return db_item.update(db, **update_data)
        else:
            for key, value in update_data.items():
                if hasattr(db_item, key):
                    setattr(db_item, key, value)
            return db_item.save(db)

    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error updating {model.__tablename__} {item_id}: {e}")
        raise HTTPException(status_code=409, detail="Duplicate or constraint violation")
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error updating {model.__tablename__} {item_id}: {e}")
        raise HTTPException(status_code=500, detail="Database error")


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
    try:
        item = model.get(db, id=item_id)
        if not item:
            return None
        return item.delete(db)
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error soft-deleting {model.__tablename__} {item_id}: {e}")
        raise HTTPException(status_code=500, detail="Database error")


def hard_delete_item(db: Session, model: Type[T], item_id: int) -> bool:
    """
    Hard-delete an item by ID.

    Args:
        db: SQLAlchemy database session.
        model: SQLAlchemy model class.
        item_id: ID of the item to hard-delete.

    Returns:
        True if item was deleted, False if not found.
    """
    try:
        item = model.get(db, id=item_id, include_deleted=True)
        if not item:
            return False
        item.hard_delete(db)
        return True
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error hard-deleting {model.__tablename__} {item_id}: {e}")
        raise HTTPException(status_code=500, detail="Database error")


def find_deleted(db: Session, model: Type[T]) -> List[T]:
    """
    Retrieve all soft-deleted items.

    Args:
        db: SQLAlchemy database session.
        model: SQLAlchemy model class.

    Returns:
        List of soft-deleted items.
    """
    try:
        return model.find_deleted(db)
    except SQLAlchemyError as e:
        logger.error(f"Database error retrieving deleted {model.__tablename__} items: {e}")
        raise HTTPException(status_code=500, detail="Database error")


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
    try:
        return model.count_documents(db, include_deleted=include_deleted)
    except SQLAlchemyError as e:
        logger.error(f"Database error counting {model.__tablename__} items: {e}")
        raise HTTPException(status_code=500, detail="Database error")


def restore_item(db: Session, model: Type[T], item_id: int) -> Optional[T]:
    """
    Restore a soft-deleted item.

    Args:
        db: SQLAlchemy database session.
        model: SQLAlchemy model class.
        item_id: ID of the item to restore.

    Returns:
        The restored item or None if not found.
    """
    try:
        item = model.get(db, id=item_id, include_deleted=True)
        if not item or not getattr(item, 'deleted_at', None):
            return None

        # Assuming your models have a restore method or we can set deleted_at to None
        if hasattr(item, 'restore'):
            return item.restore(db)
        else:
            item.deleted_at = None
            return item.save(db)
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error restoring {model.__tablename__} {item_id}: {e}")
        raise HTTPException(status_code=500, detail="Database error")


class CRUDRouterConfig:
    """Configuration for CRUD router generation."""

    def __init__(
            self,
            enable_soft_delete: bool = True,
            enable_hard_delete: bool = True,
            enable_restore: bool = True,
            enable_count: bool = True,
            enable_deleted_list: bool = True,
            enable_filtering: bool = False,
            custom_permissions: Optional[Dict[str, Callable]] = None
    ):
        self.enable_soft_delete = enable_soft_delete
        self.enable_hard_delete = enable_hard_delete
        self.enable_restore = enable_restore
        self.enable_count = enable_count
        self.enable_deleted_list = enable_deleted_list
        self.enable_filtering = enable_filtering
        self.custom_permissions = custom_permissions or {}


def create_crud_router(
        model: Type[T],
        schema_create: Type[schemas.BaseCreate],
        schema_read: Type[schemas.Base],
        custom_handlers: Optional[Dict[str, Callable]] = None,
        router_config: Optional[CRUDRouterConfig] = None
) -> APIRouter:
    """
    Create a FastAPI CRUD router for a given model with optional custom handlers.

    Args:
        model: SQLAlchemy model class.
        schema_create: Pydantic schema for creating items.
        schema_read: Pydantic schema for reading items.
        custom_handlers: Dictionary of custom endpoint handlers.
        router_config: Configuration for which endpoints to include.

    Returns:
        FastAPI APIRouter with CRUD endpoints.
    """
    if router_config is None:
        router_config = CRUDRouterConfig()

    router = APIRouter(
        prefix=f"/{model.__tablename__}",
        tags=[model.__tablename__],
    )

    # Use custom handlers if provided, otherwise default to standard functions
    custom_handlers = custom_handlers or {}

    # Helper function to get handler with permission check
    def get_handler(operation: str, default_handler: Callable) -> Callable:
        handler = custom_handlers.get(operation, default_handler)
        permission_check = router_config.custom_permissions.get(operation)

        if permission_check:
            def wrapped_handler(*args, **kwargs):
                permission_check(*args, **kwargs)
                return handler(*args, **kwargs)

            return wrapped_handler
        return handler

    # Create endpoints
    @router.post("", response_model=schema_read, status_code=201)
    def create_item_endpoint(item: schema_create, db: Session = Depends(get_db)):
        handler = get_handler("create", create_item)
        return handler(db=db, model=model, schema=item)

    @router.get("", response_model=List[schema_read])
    def read_items(
            skip: int = Query(0, ge=0, description="Number of items to skip"),
            limit: int = Query(config.DEFAULT_LIMIT, le=config.MAX_LIMIT, description="Number of items to return"),
            include_deleted: bool = Query(False, description="Include soft-deleted items"),
            db: Session = Depends(get_db)
    ):
        handler = get_handler("read_list", get_items)
        filters = None
        if router_config.enable_filtering:
            # Add filtering logic here based on query parameters
            pass
        return handler(db, model=model, skip=skip, limit=limit, include_deleted=include_deleted, filters=filters)

    @router.get("/{item_id}", response_model=schema_read)
    def read_item(
            item_id: int,
            include_deleted: bool = Query(False, description="Include soft-deleted items"),
            db: Session = Depends(get_db)
    ):
        handler = get_handler("read", get_item_by_id)
        db_item = handler(db, model=model, item_id=item_id, include_deleted=include_deleted)
        if db_item is None:
            raise HTTPException(status_code=404, detail=f"{model.__tablename__.capitalize()} not found")
        return db_item

    @router.put("/{item_id}", response_model=schema_read)
    def update_item_endpoint(item_id: int, item: schema_create, db: Session = Depends(get_db)):
        handler = get_handler("update",
                              lambda db, model, item_id, schema: update_item(db, model, item_id, schema, partial=False))
        db_item = handler(db, model=model, item_id=item_id, schema=item)
        if db_item is None:
            raise HTTPException(status_code=404, detail=f"{model.__tablename__.capitalize()} not found")
        return db_item

    @router.patch("/{item_id}", response_model=schema_read)
    def patch_item_endpoint(item_id: int, item: schema_create, db: Session = Depends(get_db)):
        handler = get_handler("patch",
                              lambda db, model, item_id, schema: update_item(db, model, item_id, schema, partial=True))
        db_item = handler(db, model=model, item_id=item_id, schema=item)
        if db_item is None:
            raise HTTPException(status_code=404, detail=f"{model.__tablename__.capitalize()} not found")
        return db_item

    if router_config.enable_soft_delete:
        @router.delete("/{item_id}", response_model=schema_read)
        def soft_delete_item_endpoint(item_id: int, db: Session = Depends(get_db)):
            handler = get_handler("delete", delete_item)
            db_item = handler(db, model=model, item_id=item_id)
            if db_item is None:
                raise HTTPException(status_code=404, detail=f"{model.__tablename__.capitalize()} not found")
            return db_item

    if router_config.enable_hard_delete:
        @router.delete("/{item_id}/hard", status_code=204)
        def hard_delete_item_endpoint(item_id: int, db: Session = Depends(get_db)):
            handler = get_handler("hard_delete", hard_delete_item)
            if not handler(db, model=model, item_id=item_id):
                raise HTTPException(status_code=404, detail=f"{model.__tablename__.capitalize()} not found")

    if router_config.enable_restore:
        @router.post("/{item_id}/restore", response_model=schema_read)
        def restore_item_endpoint(item_id: int, db: Session = Depends(get_db)):
            handler = get_handler("restore", restore_item)
            db_item = handler(db, model=model, item_id=item_id)
            if db_item is None:
                raise HTTPException(status_code=404,
                                    detail=f"{model.__tablename__.capitalize()} not found or not deleted")
            return db_item

    if router_config.enable_deleted_list:
        @router.get("/deleted/list", response_model=List[schema_read])
        def read_deleted_items(db: Session = Depends(get_db)):
            handler = get_handler("read_deleted", find_deleted)
            return handler(db, model=model)

    if router_config.enable_count:
        @router.get("/meta/count", response_model=int)
        def count_items(
                include_deleted: bool = Query(False, description="Include soft-deleted items"),
                db: Session = Depends(get_db)
        ):
            handler = get_handler("count", count_documents)
            return handler(db, model=model, include_deleted=include_deleted)

    return router


# Convenience function for basic CRUD router
def create_basic_crud_router(
        model: Type[T],
        schema_create: Type[schemas.BaseCreate],
        schema_read: Type[schemas.Base]
) -> APIRouter:
    """Create a basic CRUD router with default settings."""
    return create_crud_router(model, schema_create, schema_read)


# Convenience function for read-only router
def create_readonly_router(
        model: Type[T],
        schema_read: Type[schemas.Base]
) -> APIRouter:
    """Create a read-only router."""
    config = CRUDRouterConfig(
        enable_soft_delete=False,
        enable_hard_delete=False,
        enable_restore=False
    )
    return create_crud_router(model, None, schema_read, router_config=config)
