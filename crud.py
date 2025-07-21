from sqlalchemy.orm import Session

from models import Item
from schemas import ItemCreate


def get_item(db: Session, item_id: int, include_deleted: bool = False):
    return Item.get(db, id=item_id, include_deleted=include_deleted)


def get_items(db: Session, skip: int = 0, limit: int = 100, include_deleted: bool = False):
    items = Item.find_all(db, include_deleted=include_deleted)
    return items[skip:skip + limit]


def create_item(db: Session, item: ItemCreate):
    db_item = Item(**item.dict())
    return db_item.save(db)


def delete_item(db: Session, item_id: int):
    item = Item.get(db, id=item_id)
    if not item:
        return None
    return item.delete(db)


def hard_delete_item(db: Session, item_id: int):
    item = Item.get(db, id=item_id, include_deleted=True)
    if not item:
        return None
    return item.hard_delete(db)
