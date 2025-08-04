import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy import func

from models import Box, User, UserNFT, UserSocial

logger = logging.getLogger(__name__)


class BoxOpeningService:
    """
    Service for direct box opening operations without assignment step
    """

    @staticmethod
    def open_next_available_box(user: User, db: Session) -> Dict[str, Any]:
        """
        Open the next available box in sequential order
        """
        try:
            # Use atomic operation to get and open next box
            box = db.query(Box).filter(
                Box.is_opened == False,
                Box.deleted == False
            ).order_by(Box.position).with_for_update().first()
            # Lock row to prevent race conditions

            if not box:
                # No boxes available
                raise HTTPException(
                    status_code=404,
                    detail="No boxes available to open"
                )

            # Open the box atomically
            box.open_box(db, user.id)

            # Deduct one key from user's key count
            user.key_count -= 1
            # Save user with updated key count
            user.save(db)

            # Commit the transaction
            db.commit()

            logger.info(f"User {user.id} opened box {box.position}, keys remaining: {user.key_count}")

            return {
                "success": True,
                "box": {
                    "id": box.id,
                    "position": box.position,
                    "reward_type": box.reward_type,
                    "reward_tier": box.reward_tier,
                    "reward_data": box.reward_data,
                    "reward_description": box.reward_description,
                    "opened_at": box.opened_at.isoformat()
                },
                "user": {
                    "id": user.id,
                    "wallet_address": user.wallet_address,
                    "keys_remaining": user.key_count
                    # Show remaining keys after opening
                },
                "message": f"🎉 Box #{box.position} opened! {box.reward_description}. You have {user.key_count} keys remaining."
            }

        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except ValueError as e:
            # Handle box opening errors
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            # Rollback on any error
            db.rollback()
            logger.error(f"Error opening box for user {user.id}: {e}")
            raise HTTPException(status_code=500, detail="Error opening box")

    @staticmethod
    def open_specific_box(user: User, box_position: int, db: Session) -> Dict[str, Any]:
        """
        Open a specific box by position (if available)
        """
        try:
            # Validate position
            if box_position < 1 or box_position > 50000:
                # Invalid position range
                raise HTTPException(
                    status_code=400,
                    detail="Invalid box position. Must be between 1 and 50000"
                )

            # Get specific box with atomic lock
            box = db.query(Box).filter(
                Box.position == box_position,
                Box.is_opened == False,
                Box.deleted == False
            ).with_for_update().first()
            # Lock to prevent concurrent opening

            if not box:
                # Check if box exists but is already opened
                existing_box = db.query(Box).filter(
                    Box.position == box_position,
                    Box.deleted == False
                ).first()

                if not existing_box:
                    # Box doesn't exist
                    raise HTTPException(
                        status_code=404,
                        detail=f"Box #{box_position} not found"
                    )
                else:
                    # Box already opened
                    raise HTTPException(
                        status_code=409,
                        detail=f"Box #{box_position} has already been opened"
                    )

            # Open the box
            box.open_box(db, user.id)

            # Deduct one key from user's key count
            user.key_count -= 1
            # Save user with updated key count
            user.save(db)

            # Commit changes
            db.commit()

            logger.info(f"User {user.id} opened specific box {box_position}, keys remaining: {user.key_count}")

            return {
                "success": True,
                "box": {
                    "id": box.id,
                    "position": box.position,
                    "reward_type": box.reward_type,
                    "reward_tier": box.reward_tier,
                    "reward_data": box.reward_data,
                    "reward_description": box.reward_description,
                    "opened_at": box.opened_at.isoformat()
                },
                "user": {
                    "id": user.id,
                    "wallet_address": user.wallet_address,
                    "keys_remaining": user.key_count
                    # Show remaining keys
                },
                "message": f"🎉 Box #{box.position} opened! {box.reward_description}. You have {user.key_count} keys remaining."
            }

        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except ValueError as e:
            # Handle validation errors
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            # Rollback on error
            db.rollback()
            logger.error(f"Error opening specific box for user {user.id}: {e}")
            raise HTTPException(status_code=500, detail="Error opening specific box")

    @staticmethod
    def get_user_owned_boxes(user: User, db: Session, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """
        Get boxes that user owns with pagination (changed from get_user_opened_boxes)
        """
        try:
            # Get owned boxes with pagination
            boxes = db.query(Box).filter(
                Box.owned_by_user_id == user.id,
                Box.is_opened == True,
                Box.deleted == False
            ).order_by(Box.opened_at.desc()).offset(offset).limit(limit).all()

            # Get total count for pagination
            total_count = db.query(Box).filter(
                Box.owned_by_user_id == user.id,
                Box.is_opened == True,
                Box.deleted == False
            ).count()

            boxes_data = []
            # Build response data
            for box in boxes:
                box_data = {
                    "id": box.id,
                    "position": box.position,
                    "reward_type": box.reward_type,
                    "reward_tier": box.reward_tier,
                    "reward_data": box.reward_data,
                    "reward_description": box.reward_description,
                    "opened_at": box.opened_at.isoformat() if box.opened_at else None
                }
                boxes_data.append(box_data)

            return {
                "boxes": boxes_data,
                "total_owned": total_count,
                # Changed from total_opened
                "pagination": {
                    "limit": limit,
                    "offset": offset,
                    "has_more": (offset + limit) < total_count
                }
            }

        except Exception as e:
            logger.error(f"Error getting owned boxes for user {user.id}: {e}")
            # Changed error message
            raise HTTPException(status_code=500, detail="Error retrieving owned boxes")

    @staticmethod
    def get_box_opening_stats(db: Session) -> Dict[str, Any]:
        """
        Get overall box opening statistics
        """
        try:
            # Get basic stats using ORM
            stats = Box.get_box_stats(db)

            if not stats:
                # No data available
                return {"error": "No data available"}

            # Get reward distribution
            reward_stats = db.query(
                Box.reward_type,
                func.count(Box.id).label('count')
            ).filter(
                Box.is_opened == True,
                Box.deleted == False
            ).group_by(Box.reward_type).all()

            reward_distribution = {stat.reward_type: stat.count for stat in reward_stats}

            total_boxes = stats.total_boxes or 0
            # Total boxes in system
            opened_boxes = stats.opened_boxes or 0
            # Boxes that have been opened (now owned by users)
            available_boxes = total_boxes - opened_boxes
            # Boxes still available to open

            return {
                "total_boxes": total_boxes,
                "opened_boxes": opened_boxes,
                "available_boxes": available_boxes,
                "opening_percentage": round((opened_boxes / total_boxes) * 100, 2) if total_boxes > 0 else 0,
                "reward_distribution": reward_distribution
            }

        except Exception as e:
            logger.error(f"Error getting box opening stats: {e}")
            raise HTTPException(status_code=500, detail="Error retrieving box opening statistics")


    @staticmethod
    def calculate_user_keys(user: User, db: Session) -> Dict[str, Any]:
        """
        Calculate available keys for user based on social and NFT verification
        """
        try:
            # Count social platforms completed
            social_platforms = db.query(UserSocial).filter(
                UserSocial.user_id == user.id,
                UserSocial.platform.in_(['twitter', 'discord', 'telegram']),
                UserSocial.deleted == False
            ).distinct(UserSocial.platform).count()

            # Count unused NFTs
            unused_nfts = db.query(UserNFT).filter(
                UserNFT.user_id == user.id,
                UserNFT.used == False,
                UserNFT.deleted == False
            ).count()

            # Get completed platforms list
            completed_platforms_query = db.query(UserSocial.platform).filter(
                UserSocial.user_id == user.id,
                UserSocial.deleted == False
            ).distinct().all()

            completed_platforms = [platform[0] for platform in completed_platforms_query]

            # Calculate keys per specification
            required_platforms = {"twitter", "discord", "telegram"}
            # Need all 3 platforms for social key
            social_tasks_completed = social_platforms >= 3
            # 1 key if all social tasks completed
            social_keys = 1 if social_tasks_completed else 0

            # NFT key calculation
            if unused_nfts == 0:
                # No NFTs = no NFT keys
                nft_keys = 0
            elif unused_nfts == 1:
                # 1 NFT = 2 keys minimum
                nft_keys = 2
            else:
                # Multiple NFTs = up to 10 keys max
                nft_keys = min(unused_nfts, 10)

            total_available = social_keys + nft_keys

            return {
                "social_keys": social_keys,
                "nft_keys": nft_keys,
                "total_available": total_available,
                "social_completed": social_tasks_completed,
                "nft_count": unused_nfts,
                "platforms_completed": completed_platforms,
                "required_platforms": list(required_platforms),
                "breakdown": {
                    "social_task_status": f"{social_platforms}/3 platforms completed",
                    "nft_status": f"{unused_nfts} qualifying NFTs found",
                    "keys_from_social": social_keys,
                    "keys_from_nfts": nft_keys
                }
            }

        except Exception as e:
            logger.error(f"Error calculating keys for user {user.id}: {e}")
            raise HTTPException(status_code=500, detail="Error calculating available keys")

    # REMOVED: assign_box_to_user, get_user_assigned_boxes, verify_nft_ownership_and_assign