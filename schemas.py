from datetime import datetime
from typing import Optional, Dict, Any, List

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


# ============= NEW BOX OPENING SCHEMAS =============

class BoxOpenRequest(BaseCreate):
    """Request schema for opening boxes - no input needed, uses JWT user"""
    pass


class KeyBreakdownSchema(Base):
    """Detailed breakdown of how keys are calculated"""
    social_keys: int
    nft_keys: int
    total_available: int
    social_completed: bool
    nft_count: int
    platforms_completed: List[str]
    required_platforms: List[str]
    breakdown: Dict[str, Any]

    class Config:
        from_attributes = True


class BoxOpenResponseSchema(Base):
    """Response schema for successful box opening"""
    success: bool
    box: Dict[str, Any]
    user: Dict[str, Any]
    key_info: Dict[str, Any]
    message: str

    class Config:
        from_attributes = True


class OpenedBoxSchema(Base):
    """Schema for a single opened box"""
    id: int
    position: int
    reward_type: str
    reward_tier: Optional[str]
    reward_data: Optional[Dict[str, Any]]
    reward_description: Optional[str]
    opened_at: str

    class Config:
        from_attributes = True


class UserOpenedBoxesResponseSchema(Base):
    """Response schema for user's opened boxes list"""
    boxes: List[OpenedBoxSchema]
    pagination: Dict[str, Any]
    user: Dict[str, Any]

    class Config:
        from_attributes = True


class BoxStatsResponseSchema(Base):
    """Response schema for box opening statistics"""
    total_boxes: int
    opened_boxes: int
    available_boxes: int
    completion_percentage: float
    next_box_position: Optional[int]
    reward_distribution: Dict[str, int]

    class Config:
        from_attributes = True


class NextBoxResponseSchema(Base):
    """Response schema for next available box info"""
    next_box: Dict[str, Any]
    can_open: bool
    key_info: Dict[str, Any]
    message: str

    class Config:
        from_attributes = True


class SupportedNFTCollectionSchema(Base):
    id: int
    collection_name: str
    collection_address: str
    description: str
    image_url: str
    website_url: str
    created_at: datetime
    updated_at: datetime
    deleted: bool

    class Config:
        from_attributes = True


class SupportedNFTCollectionCreateSchema(BaseCreate):
    collection_name: str
    collection_address: str
    description: str
    image_url: str
    website_url: str

    class Config:
        from_attributes = True
