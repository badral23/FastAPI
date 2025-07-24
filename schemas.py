from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class Base(BaseModel):
    pass


class BaseCreate(BaseModel):
    pass


class UserCreateSchema(BaseCreate):
    wallet_address: str
    key_count: Optional[int] = 0

    class Config:
        from_attributes = True


class UserSchema(Base):
    id: int
    wallet_address: str
    key_count: int
    created_at: datetime
    updated_at: Optional[datetime]
    deleted: bool

    class Config:
        from_attributes = True


class UserSocialCreateSchema(BaseCreate):
    user_id: int
    platform: str
    handle: str

    class Config:
        from_attributes = True


class UserSocialSchema(Base):
    id: str
    user_id: int
    platform: str
    handle: str
    created_at: datetime
    deleted: bool

    class Config:
        from_attributes = True


class UserNFTCreateSchema(BaseCreate):
    user_id: int
    nft_collection: str
    nft_id: str
    used: Optional[bool] = False

    class Config:
        from_attributes = True


class UserNFTSchema(Base):
    id: str
    user_id: int
    nft_collection: str
    nft_id: str
    used: bool
    created_at: datetime
    deleted: bool

    class Config:
        from_attributes = True


class BoxSchema(Base):
    id: int
    position: int
    reward_type: str
    reward_tier: Optional[str]
    reward_data: Optional[dict]
    reward_description: Optional[str]
    is_opened: bool
    opened_by_user_id: Optional[int]
    opened_at: Optional[datetime]
    created_at: datetime
    deleted: bool

    class Config:
        from_attributes = True

class BoxCreateSchema(BaseCreate):
    position: int
    reward_type: str
    reward_tier: Optional[str] = None
    reward_data: Optional[dict] = None
    reward_description: Optional[str] = None

    class Config:
        from_attributes = True