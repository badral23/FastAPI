import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
from fastapi import HTTPException

from models import Box, User, UserNFT, UserSocial
from database_utils import retry_db_operation

logger = logging.getLogger(__name__)


class BoxOpeningService:
    """
    Service for handling box opening operations with atomic guarantees
    """

    @staticmethod
    def calculate_user_keys(user: User, db: Session) -> Dict[str, Any]:
        """
        Calculate total available keys for a user based on social tasks and NFT ownership

        Returns:
            dict: {
                "social_keys": int,
                "nft_keys": int,
                "total_available": int,
                "social_completed": bool,
                "nft_count": int,
                "breakdown": dict
            }
        """
        try:
            # Social verification: All 3 tasks completed = 1 key
            social_accounts = db.query(UserSocial).filter(
                UserSocial.user_id == user.id,
                UserSocial.deleted.is_(False)
            ).all()

            # Check if user has completed all required social tasks
            platforms_completed = set()
            for social in social_accounts:
                platforms_completed.add(social.platform.lower())

            # Required platforms: twitter, discord, telegram
            required_platforms = {"twitter", "discord", "telegram"}
            social_tasks_completed = required_platforms.issubset(platforms_completed)
            social_keys = 1 if social_tasks_completed else 0

            # NFT verification: Count unused NFTs (2-10 keys based on NFT count)
            unused_nfts = db.query(UserNFT).filter(
                UserNFT.user_id == user.id,
                UserNFT.used.is_(False),
                UserNFT.deleted.is_(False)
            ).all()

            nft_count = len(unused_nfts)
            # Scale NFT keys: 2-10 keys based on NFT count (cap at 10)
            nft_keys = min(max(nft_count, 0), 10)
            if nft_count > 0 and nft_keys < 2:
                nft_keys = 2  # Minimum 2 keys if user has any NFTs

            total_available = social_keys + nft_keys

            return {
                "social_keys": social_keys,
                "nft_keys": nft_keys,
                "total_available": total_available,
                "social_completed": social_tasks_completed,
                "nft_count": nft_count,
                "platforms_completed": list(platforms_completed),
                "required_platforms": list(required_platforms),
                "breakdown": {
                    "social_tasks": {
                        "completed": social_tasks_completed,
                        "platforms": list(platforms_completed),
                        "keys_earned": social_keys
                    },
                    "nft_ownership": {
                        "total_nfts": nft_count,
                        "unused_nfts": nft_count,
                        "keys_earned": nft_keys
                    }
                }
            }

        except Exception as e:
            logger.error(f"Error calculating keys for user {user.id}: {e}")
            raise HTTPException(status_code=500, detail="Error calculating available keys")

    @staticmethod
    @retry_db_operation(max_retries=3, delay=0.1)
    def assign_next_box_atomically(user: User, db: Session) -> Optional[Box]:
        """
        Atomically assign the next available box to a user
        Uses database-level locking to prevent race conditions

        Returns:
            Box: The assigned box, or None if no boxes available
        """
        try:
            # Start transaction
            db.begin()

            # Use FOR UPDATE SKIP LOCKED for atomic box assignment
            # This prevents race conditions when multiple users try to open boxes simultaneously
            result = db.execute(text("""
                SELECT id, position, reward_type, reward_tier, reward_data, reward_description
                FROM boxes 
                WHERE is_opened = false 
                  AND deleted = false
                ORDER BY position 
                LIMIT 1 
                FOR UPDATE SKIP LOCKED
            """))

            box_row = result.fetchone()

            if not box_row:
                db.rollback()
                return None

            # Update the box as opened
            box_id = box_row[0]
            current_time = datetime.now(timezone.utc)

            db.execute(text("""
                UPDATE boxes 
                SET is_opened = true,
                    opened_by_user_id = :user_id,
                    opened_at = :opened_at
                WHERE id = :box_id
            """), {
                "user_id": user.id,
                "opened_at": current_time,
                "box_id": box_id
            })

            # Commit transaction
            db.commit()

            # Fetch the updated box object
            assigned_box = db.query(Box).filter(Box.id == box_id).first()

            logger.info(f"Successfully assigned box {assigned_box.position} to user {user.id}")
            return assigned_box

        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error in assign_next_box_atomically: {e}")
            raise HTTPException(status_code=500, detail="Database error during box assignment")
        except Exception as e:
            db.rollback()
            logger.error(f"Unexpected error in assign_next_box_atomically: {e}")
            raise HTTPException(status_code=500, detail="Unexpected error during box assignment")

    @staticmethod
    def mark_user_nfts_as_used(user: User, db: Session, nfts_to_use: int = None) -> int:
        """
        Mark user's NFTs as used to prevent double-spending

        Args:
            user: User object
            db: Database session
            nfts_to_use: Number of NFTs to mark as used (None = mark all unused)

        Returns:
            int: Number of NFTs marked as used
        """
        try:
            # Get unused NFTs
            unused_nfts_query = db.query(UserNFT).filter(
                UserNFT.user_id == user.id,
                UserNFT.used.is_(False),
                UserNFT.deleted.is_(False)
            )

            if nfts_to_use is not None:
                unused_nfts = unused_nfts_query.limit(nfts_to_use).all()
            else:
                unused_nfts = unused_nfts_query.all()

            # Mark them as used
            nfts_marked = 0
            for nft in unused_nfts:
                nft.used = True
                db.add(nft)
                nfts_marked += 1

            db.commit()

            logger.info(f"Marked {nfts_marked} NFTs as used for user {user.id}")
            return nfts_marked

        except Exception as e:
            db.rollback()
            logger.error(f"Error marking NFTs as used for user {user.id}: {e}")
            raise HTTPException(status_code=500, detail="Error updating NFT usage status")

    @staticmethod
    def open_box(user: User, db: Session) -> Dict[str, Any]:
        """
        Main box opening function - handles the complete flow

        Args:
            user: Authenticated user
            db: Database session

        Returns:
            dict: Box opening result with reward details
        """
        try:
            # Step 1: Calculate available keys
            key_info = BoxOpeningService.calculate_user_keys(user, db)

            if key_info["total_available"] <= 0:
                raise HTTPException(
                    status_code=400,
                    detail="No keys available. Complete social tasks or verify NFT ownership to earn keys."
                )

            # Step 2: Atomically assign next available box
            assigned_box = BoxOpeningService.assign_next_box_atomically(user, db)

            if not assigned_box:
                raise HTTPException(
                    status_code=404,
                    detail="No boxes available. All boxes have been opened!"
                )

            # Step 3: Mark NFTs as used (prevent double-spending)
            if key_info["nft_count"] > 0:
                BoxOpeningService.mark_user_nfts_as_used(user, db, nfts_to_use=1)

            # Step 4: Update user's key count (decrement by 1)
            user.key_count = max(0, user.key_count - 1)
            db.add(user)
            db.commit()

            # Step 5: Prepare response
            response = {
                "success": True,
                "box": {
                    "id": assigned_box.id,
                    "position": assigned_box.position,
                    "reward_type": assigned_box.reward_type,
                    "reward_tier": assigned_box.reward_tier,
                    "reward_data": assigned_box.reward_data,
                    "reward_description": assigned_box.reward_description,
                    "opened_at": assigned_box.opened_at.isoformat()
                },
                "user": {
                    "id": user.id,
                    "wallet_address": user.wallet_address,
                    "keys_remaining": user.key_count
                },
                "key_info": key_info,
                "message": f"Congratulations! You opened box #{assigned_box.position} and won: {assigned_box.reward_description}"
            }

            logger.info(f"User {user.id} successfully opened box {assigned_box.position} - {assigned_box.reward_type}")
            return response

        except HTTPException:
            # Re-raise HTTP exceptions (these have proper error messages)
            raise
        except Exception as e:
            logger.error(f"Unexpected error in open_box for user {user.id}: {e}")
            raise HTTPException(status_code=500, detail="Unexpected error during box opening")

    @staticmethod
    def get_user_opened_boxes(user: User, db: Session, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """
        Get list of boxes opened by a user

        Args:
            user: User object
            db: Database session
            limit: Maximum number of results
            offset: Pagination offset

        Returns:
            dict: User's opened boxes with pagination info
        """
        try:
            # Get user's opened boxes
            opened_boxes_query = db.query(Box).filter(
                Box.opened_by_user_id == user.id,
                Box.is_opened.is_(True),
                Box.deleted.is_(False)
            ).order_by(Box.opened_at.desc())

            total_count = opened_boxes_query.count()
            opened_boxes = opened_boxes_query.offset(offset).limit(limit).all()

            boxes_data = []
            for box in opened_boxes:
                boxes_data.append({
                    "id": box.id,
                    "position": box.position,
                    "reward_type": box.reward_type,
                    "reward_tier": box.reward_tier,
                    "reward_data": box.reward_data,
                    "reward_description": box.reward_description,
                    "opened_at": box.opened_at.isoformat()
                })

            return {
                "boxes": boxes_data,
                "pagination": {
                    "total": total_count,
                    "limit": limit,
                    "offset": offset,
                    "has_more": (offset + limit) < total_count
                },
                "user": {
                    "id": user.id,
                    "wallet_address": user.wallet_address,
                    "total_boxes_opened": total_count
                }
            }

        except Exception as e:
            logger.error(f"Error getting opened boxes for user {user.id}: {e}")
            raise HTTPException(status_code=500, detail="Error retrieving opened boxes")

    @staticmethod
    def get_box_opening_stats(db: Session) -> Dict[str, Any]:
        """
        Get overall statistics about box openings

        Returns:
            dict: Box opening statistics
        """
        try:
            # Total boxes
            total_boxes = db.query(Box).filter(Box.deleted.is_(False)).count()

            # Opened boxes
            opened_boxes = db.query(Box).filter(
                Box.is_opened.is_(True),
                Box.deleted.is_(False)
            ).count()

            # Available boxes
            available_boxes = total_boxes - opened_boxes

            # Reward type distribution of opened boxes
            reward_distribution = db.execute(text("""
                SELECT reward_type, COUNT(*) as count
                FROM boxes 
                WHERE is_opened = true AND deleted = false
                GROUP BY reward_type
                ORDER BY count DESC
            """)).fetchall()

            # Next box to be opened
            next_box = db.query(Box).filter(
                Box.is_opened.is_(False),
                Box.deleted.is_(False)
            ).order_by(Box.position).first()

            return {
                "total_boxes": total_boxes,
                "opened_boxes": opened_boxes,
                "available_boxes": available_boxes,
                "completion_percentage": round((opened_boxes / total_boxes) * 100, 2) if total_boxes > 0 else 0,
                "next_box_position": next_box.position if next_box else None,
                "reward_distribution": {
                    row[0]: row[1] for row in reward_distribution
                }
            }

        except Exception as e:
            logger.error(f"Error getting box opening stats: {e}")
            raise HTTPException(status_code=500, detail="Error retrieving box opening statistics")