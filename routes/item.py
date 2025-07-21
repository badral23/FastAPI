from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import crud
import schemas
from database import get_db

router = APIRouter(
    prefix="/items",
    tags=["items"],
)


@router.post("/", response_model=schemas.Item)
def create_item(item: schemas.ItemCreate, db: Session = Depends(get_db)):
    return crud.create_item(db=db, item=item)


@router.get("/", response_model=List[schemas.Item])
def read_items(skip: int = 0, limit: int = 100, include_deleted: bool = False, db: Session = Depends(get_db)):
    items = crud.get_items(db, skip=skip, limit=limit, include_deleted=include_deleted)
    return items


@router.get("/{item_id}", response_model=schemas.Item)
def read_item(item_id: int, include_deleted: bool = False, db: Session = Depends(get_db)):
    db_item = crud.get_item(db, item_id=item_id, include_deleted=include_deleted)
    if db_item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return db_item


@router.delete("/{item_id}", response_model=schemas.Item)
def soft_delete_item(item_id: int, db: Session = Depends(get_db)):
    db_item = crud.delete_item(db, item_id=item_id)
    if db_item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return db_item


@router.delete("/{item_id}/hard", status_code=204)
def hard_delete_item(item_id: int, db: Session = Depends(get_db)):
    db_item = crud.hard_delete_item(db, item_id=item_id)
    if db_item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return None


@router.get("/deleted/", response_model=List[schemas.Item])
def read_deleted_items(db: Session = Depends(get_db)):
    items = crud.Item.find_deleted(db)
    return items


@router.get("/count/", response_model=int)
def count_items(include_deleted: bool = False, db: Session = Depends(get_db)):
    return crud.Item.count_documents(db, include_deleted=include_deleted)
