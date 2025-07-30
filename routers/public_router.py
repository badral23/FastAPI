from fastapi import Depends, HTTPException, status, APIRouter
from sqlalchemy.orm import Session

from database import get_db
from models import SupportedNFTCollection

router = APIRouter()


@router.post("/collections")
def get_collections(db: Session = Depends(get_db)):
    collections = db.query(SupportedNFTCollection).all()
    if not collections:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No collections found")
    return collections
