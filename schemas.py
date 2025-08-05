# schemas.py - Clean version without assignment functionality

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
    # Wallet address for the user
    key_count: Optional[int] = 0
    # Initial key count


class UserSchema(Base):
    id: int
    # User ID
    wallet_address: str
    # User's wallet address
    key_count: int
    # Number of keys user has
    created_at: datetime
    # When user was created
    updated_at: Optional[datetime] = None
    # When user was last updated
    deleted: bool
    # Soft delete flag


# User Social schemas
class UserSocialCreateSchema(BaseCreate):
    user_id: int
    # ID of the user
    platform: str
    # Social platform name
    handle: Optional[str] = None
    # User's handle on platform


class UserSocialSchema(Base):
    id: int
    # Social account ID
    user_id: int
    # Associated user ID
    platform: str
    # Platform name
    handle: Optional[str] = None
    # User's handle
    created_at: datetime
    # When social account was linked
    deleted: bool
    # Soft delete flag


# User NFT schemas
class UserNFTCreateSchema(BaseCreate):
    user_id: int
    # Owner user ID
    nft_collection: str
    # NFT collection address
    nft_id: int
    # NFT token ID
    used: Optional[bool] = False
    # Whether NFT has been used for keys


class UserNFTSchema(Base):
    id: int
    # NFT record ID
    user_id: int
    # Owner user ID
    nft_collection: str
    # Collection address
    nft_id: int
    # Token ID
    used: bool
    # Usage status
    created_at: datetime
    # When NFT was recorded
    deleted: bool
    # Soft delete flag


# Box schemas
class BoxCreateSchema(BaseCreate):
    reward_type: str
    # Type of reward
    reward_tier: Optional[str] = None
    # Reward tier if applicable
    reward_data: Optional[Dict[str, Any]] = None
    # Additional reward metadata
    reward_description: Optional[str] = None
    # Human-readable description


# Update Box schema to use owned_by instead of opened_by
class BoxSchema(Base):
    id: int
    reward_type: str
    # Type of reward
    reward_tier: Optional[str] = None
    # Reward tier if applicable
    reward_data: Optional[Dict[str, Any]] = None
    # Additional reward metadata
    reward_description: Optional[str] = None
    # Human-readable description
    is_opened: bool
    # Whether box has been opened
    owned_by_user_id: Optional[int] = None
    # User who owns the box (changed from opened_by_user_id)
    created_at: datetime
    # When box was created
    deleted: bool
    # Soft delete flag


class BoxOpenResponse(Base):
    """Response for box opening"""
    success: bool
    # Whether opening was successful
    message: str
    # Success/error message
    box: Dict[str, Any]
    # Box details with rewards
    user: Dict[str, Any]
    # User information


class BoxStatsResponse(Base):
    """Box opening statistics"""
    total_boxes: int
    # Total boxes in system
    opened_boxes: int
    # Number of boxes opened
    available_boxes: int
    # Number of boxes still available
    opening_percentage: float
    # Percentage of boxes opened
    reward_distribution: Dict[str, int]
    # Distribution of reward types


# Supported NFT Collection schemas
class SupportedNFTCollectionCreateSchema(BaseCreate):
    collection_name: str
    # Name of the collection
    collection_address: str
    # Contract address
    description: Optional[str] = None
    # Collection description
    image_url: Optional[str] = None
    # Collection image URL
    website_url: Optional[str] = None
    # Collection website


class SupportedNFTCollectionSchema(Base):
    id: int
    # Collection ID
    collection_name: str
    # Collection name
    collection_address: str
    # Contract address
    description: Optional[str] = None
    # Description
    image_url: Optional[str] = None
    # Image URL
    website_url: Optional[str] = None
    # Website URL
    created_at: datetime
    # When collection was added
    updated_at: Optional[datetime] = None
    # When collection was updated
    deleted: bool
    # Soft delete flag


# Key calculation schemas
class KeyBreakdownSchema(Base):
    """Detailed breakdown of how keys are calculated"""
    social_keys: int
    # Keys from social verification
    nft_keys: int
    # Keys from NFT ownership
    total_available: int
    # Total keys available
    social_completed: bool
    # Whether social tasks are complete
    nft_count: int
    # Number of qualifying NFTs
    platforms_completed: List[str]
    # List of completed platforms
    required_platforms: List[str]
    # List of required platforms
    breakdown: Dict[str, Any]
    # Detailed breakdown info


# Response schemas for owned boxes (changed from opened boxes)
class OwnedBoxSchema(Base):
    """Schema for a single owned box (changed from OpenedBoxSchema)"""
    id: int
    # Box ID
    reward_type: str
    # Reward type
    reward_tier: Optional[str] = None
    # Reward tier
    reward_data: Optional[Dict[str, Any]] = None
    # Reward metadata
    reward_description: Optional[str] = None
    # Reward description


class UserOwnedBoxesResponseSchema(Base):
    """Response schema for user's owned boxes list (changed from UserOpenedBoxesResponseSchema)"""
    boxes: List[OwnedBoxSchema]
    # List of owned boxes
    pagination: Dict[str, Any]
    # Pagination info
    user: Dict[str, Any]
    # User information


class NextBoxResponseSchema(Base):
    """Response schema for next available box info"""
    next_box: Dict[str, Any]
    # Next available box info
    can_open: bool
    # Whether user can open boxes
    key_info: Dict[str, Any]
    # User's key information
    message: str
    # Status message


# User with box statistics
class UserWithBoxesSchema(Base):
    """User schema with box statistics"""
    id: int
    # User ID
    wallet_address: str
    # Wallet address
    key_count: int
    # Current key count
    created_at: datetime
    # When user was created
    updated_at: Optional[datetime] = None
    # When user was updated
    deleted: bool
    # Soft delete flag
    total_owned_boxes: Optional[int] = 0
    # Number of boxes user owns (changed from total_opened_boxes)

# REMOVED: All assignment-related schemas since we removed that functionality
# - BoxAssignmentRequest
# - BoxAssignmentResponse
# - AssignedBoxSchema
# - UserAssignedBoxesResponse
# - assigned_boxes field from BoxStatsResponse
# - campaign_percentage field from BoxStatsResponse
