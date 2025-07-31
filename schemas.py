# Fixed schemas.py - Replace your schemas.py with this

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel


# Base Pydantic schemas (NOT SQLAlchemy Base!)
class Base(BaseModel):
    class Config:
        from_attributes = True


class BaseCreate(BaseModel):
    class Config:
        from_attributes = True


# User schemas
class UserCreateSchema(BaseCreate):
    wallet_address: str
    key_count: Optional[int] = 0


class UserSchema(Base):
    id: int
    wallet_address: str
    key_count: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    deleted: bool


# User Social schemas
class UserSocialCreateSchema(BaseCreate):
    user_id: int
    platform: str
    handle: Optional[str] = None


class UserSocialSchema(Base):
    id: int
    user_id: int
    platform: str
    handle: Optional[str] = None
    created_at: datetime
    deleted: bool


# User NFT schemas
class UserNFTCreateSchema(BaseCreate):
    user_id: int
    nft_collection: str
    nft_id: int
    used: Optional[bool] = False


class UserNFTSchema(Base):
    id: int
    user_id: int
    nft_collection: str
    nft_id: int
    used: bool
    created_at: datetime
    deleted: bool


# Box schemas
class BoxCreateSchema(BaseCreate):
    position: int
    reward_type: str
    reward_tier: Optional[str] = None
    reward_data: Optional[Dict[str, Any]] = None
    reward_description: Optional[str] = None


class BoxSchema(Base):
    id: int
    position: int
    reward_type: str
    reward_tier: Optional[str] = None
    reward_data: Optional[Dict[str, Any]] = None
    reward_description: Optional[str] = None
    is_opened: bool
    opened_by_user_id: Optional[int] = None
    opened_at: Optional[datetime] = None
    # NEW ASSIGNMENT FIELDS
    assigned_to_user_id: Optional[int] = None
    assigned_at: Optional[datetime] = None
    created_at: datetime
    deleted: bool


# New assignment-specific schemas
class BoxAssignmentRequest(BaseCreate):
    nft_token_id: str
    transaction_hash: str  # Transaction hash of NFT transfer


class BoxOpenRequest(BaseCreate):
    box_position: int


class AssignedBoxSchema(Base):
    """Schema for boxes assigned to users"""
    id: int
    position: int
    reward_type: str
    reward_tier: Optional[str] = None
    status: str  # "assigned_unopened" or "opened"
    assigned_at: datetime
    reward_description: Optional[str] = None
    # Only include reward details if opened
    reward_data: Optional[Dict[str, Any]] = None
    opened_at: Optional[datetime] = None


class UserAssignedBoxesResponse(Base):
    """Response for user's assigned boxes"""
    boxes: List[AssignedBoxSchema]
    total_assigned: int
    opened_count: int
    unopened_count: int


class BoxAssignmentResponse(Base):
    """Response for box assignment"""
    success: bool
    message: str
    box: Dict[str, Any]


class BoxOpenResponse(Base):
    """Response for box opening"""
    success: bool
    message: str
    box: Dict[str, Any]
    user: Dict[str, Any]


class BoxStatsResponse(Base):
    """Response for box statistics"""
    total_boxes: int
    assigned_boxes: int
    opened_boxes: int
    unassigned_boxes: int
    assignment_percentage: float
    opening_percentage: float
    reward_distribution: Dict[str, int]


# Supported NFT Collection schemas
class SupportedNFTCollectionCreateSchema(BaseCreate):
    collection_name: str
    collection_address: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    website_url: Optional[str] = None


class SupportedNFTCollectionSchema(Base):
    id: int
    collection_name: str
    collection_address: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    website_url: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    deleted: bool


# Additional response schemas
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


class BoxOpeningResponseSchema(Base):
    """Response schema for successful box opening"""
    success: bool
    box: Dict[str, Any]
    user: Dict[str, Any]
    key_info: Dict[str, Any]
    message: str


class OpenedBoxSchema(Base):
    """Schema for a single opened box"""
    id: int
    position: int
    reward_type: str
    reward_tier: Optional[str] = None
    reward_data: Optional[Dict[str, Any]] = None
    reward_description: Optional[str] = None
    opened_at: str


class UserOpenedBoxesResponseSchema(Base):
    """Response schema for user's opened boxes list"""
    boxes: List[OpenedBoxSchema]
    pagination: Dict[str, Any]
    user: Dict[str, Any]


class NextBoxResponseSchema(Base):
    """Response schema for next available box info"""
    next_box: Dict[str, Any]
    can_open: bool
    key_info: Dict[str, Any]
    message: str


# Updated User schema with relationships
class UserWithBoxesSchema(Base):
    id: int
    wallet_address: str
    key_count: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    deleted: bool

    # Include box counts
    total_assigned_boxes: Optional[int] = 0
    total_opened_boxes: Optional[int] = 0