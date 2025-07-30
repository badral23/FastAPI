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

            # NFT verification: Count unused NFTs
            unused_nfts = db.query(UserNFT).filter(
                UserNFT.user_id == user.id,
                UserNFT.used.is_(False),
                UserNFT.deleted.is_(False)
            ).all()

            nft_count = len(unused_nfts)

            # FIXED: NFT key calculation per specification
            if nft_count == 0:
                nft_keys = 0
            elif nft_count == 1:
                nft_keys = 2  # Minimum 2 keys for 1 NFT
            else:
                nft_keys = min(nft_count, 10)  # 1 key per NFT, max 10

            total_available = social_keys + nft_keys

            return {
                "social_keys": social_keys,
                "nft_keys": nft_keys,
                "total_available": total_available,
                "social_completed": social_tasks_completed,
                "nft_count": nft_count,
                "unused_nft_count": nft_count,
                "platforms_completed": list(platforms_completed),
                "required_platforms": list(required_platforms),
                "breakdown": {
                    "social_tasks": {
                        "completed": social_tasks_completed,
                        "platforms": list(platforms_completed),
                        "missing_platforms": list(required_platforms - platforms_completed),
                        "keys_earned": social_keys
                    },
                    "nft_ownership": {
                        "total_nfts": nft_count,
                        "unused_nfts": nft_count,
                        "keys_earned": nft_keys,
                        "key_calculation": f"{nft_count} NFTs -> {nft_keys} keys"
                    }
                }
            }

        except Exception as e:
            logger.error(f"Error calculating keys for user {user.id}: {e}")
            raise HTTPException(status_code=500, detail="Error calculating available keys")

    @staticmethod
    def assign_next_box_atomically(user: User, db: Session) -> Optional[Box]:
        """
        FIXED: Atomically assign the next available box to a user
        Removed manual db.begin() to fix transaction error
        """
        try:
            # Use FOR UPDATE SKIP LOCKED for atomic box assignment
            # SQLAlchemy will handle the transaction automatically
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
                logger.warning("No available boxes for assignment")
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

            # Flush to ensure the update is applied
            db.flush()

            # Fetch the updated box object
            assigned_box = db.query(Box).filter(Box.id == box_id).first()

            logger.info(f"Successfully assigned box {assigned_box.position} to user {user.id}")
            return assigned_box

        except SQLAlchemyError as e:
            logger.error(f"Database error in assign_next_box_atomically: {e}")
            raise HTTPException(status_code=500, detail="Database error during box assignment")
        except Exception as e:
            logger.error(f"Unexpected error in assign_next_box_atomically: {e}")
            raise HTTPException(status_code=500, detail="Unexpected error during box assignment")

    @staticmethod
    def mark_user_nfts_as_used(user: User, db: Session, nft_count_to_use: int = 1) -> List[Dict[str, Any]]:
        """
        FIXED: Mark user's NFTs as used to prevent double-spending
        Returns list of NFTs that were marked as used
        """
        try:
            # Get unused NFTs (ordered by creation date for fairness)
            unused_nfts = db.query(UserNFT).filter(
                UserNFT.user_id == user.id,
                UserNFT.used.is_(False),
                UserNFT.deleted.is_(False)
            ).order_by(UserNFT.created_at).limit(nft_count_to_use).all()

            if len(unused_nfts) < nft_count_to_use:
                raise HTTPException(
                    status_code=400,
                    detail=f"Not enough unused NFTs. Need {nft_count_to_use}, have {len(unused_nfts)}"
                )

            # Mark them as used
            marked_nfts = []
            for nft in unused_nfts:
                nft.used = True
                db.add(nft)
                marked_nfts.append({
                    "id": nft.id,
                    "collection": nft.nft_collection,
                    "nft_id": nft.nft_id
                })

            # Flush to ensure updates are applied
            db.flush()

            logger.info(f"Marked {len(marked_nfts)} NFTs as used for user {user.id}")
            return marked_nfts

        except Exception as e:
            logger.error(f"Error marking NFTs as used for user {user.id}: {e}")
            raise HTTPException(status_code=500, detail="Error updating NFT usage status")

    @staticmethod
    def open_box(user: User, db: Session) -> Dict[str, Any]:
        """
        FIXED: Main box opening function with proper transaction handling
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

            # Step 3: Consume one key by marking NFTs as used
            # Priority: Use NFT keys first (more valuable), then social keys
            nfts_marked = []
            key_source = "social"

            if key_info["nft_keys"] > 0:
                # Use NFT key - mark one NFT as used
                nfts_marked = BoxOpeningService.mark_user_nfts_as_used(user, db, 1)
                key_source = "nft"
            # Social keys don't need marking (they're permanent once earned)

            # Step 4: Commit all changes in one transaction
            db.commit()

            # Step 5: Log the box opening
            logger.info(f"User {user.id} opened box {assigned_box.position} using {key_source} key")

            # Step 6: Prepare response
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
                },
                "key_consumption": {
                    "key_source": key_source,
                    "nfts_used": nfts_marked,
                    "remaining_keys": BoxOpeningService.calculate_user_keys(user, db)["total_available"]
                },
                "message": f"Congratulations! You opened box #{assigned_box.position} and won: {assigned_box.reward_description}"
            }

            return response

        except HTTPException:
            # Re-raise HTTP exceptions (these have proper error messages)
            raise
        except Exception as e:
            # Rollback transaction on any error
            db.rollback()
            logger.error(f"Unexpected error in open_box for user {user.id}: {e}")
            raise HTTPException(status_code=500, detail="Unexpected error during box opening")

    @staticmethod
    def get_user_opened_boxes(user: User, db: Session, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """
        Get list of boxes opened by a user
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