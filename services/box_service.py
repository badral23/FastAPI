import logging
from typing import Dict, Any, Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from models import Box, User, UserNFT, UserSocial

logger = logging.getLogger(__name__)


class BoxOpeningService:
    """
    Service for direct box opening operations without assignment step
    """

    @staticmethod
    def open_next_available_box(user: User, db: Session) -> Dict[str, Any]:
        try:
            box = db.query(Box).filter(
                Box.is_opened == False,
                Box.deleted == False
            ).order_by(Box.id).with_for_update().first()

            if not box:
                raise HTTPException(
                    status_code=404,
                    detail="No boxes available to open"
                )

            box.is_opened = True

            user.key_count -= 1
            user.save(db)

            db.commit()
            db.refresh(box)
            db.refresh(user)

            logger.info(f"User {user.id} opened box {box.id}, keys remaining: {user.key_count}")

            return {
                "success": True,
                "box": {
                    "id": box.id,
                    "reward_type": box.reward_type,
                    "reward_tier": box.reward_tier,
                    "reward_data": box.reward_data,
                    "reward_description": box.reward_description,
                },
                "message": f"🎉 Box #{box.id} opened! {box.reward_description}. You have {user.key_count} keys remaining."
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
    def open_specific_box(user: User, box_id: int, db: Session) -> Dict[str, Any]:
        try:
            box = db.query(Box).filter(
                Box.id == box_id,
                Box.owned_by_user_id == user.id,
                Box.is_opened == False,
                Box.deleted == False
            ).with_for_update().first()

            if not box:
                raise ValueError("Box not found or already opened")

            box.is_opened = True

            user.key_count -= 1
            user.save(db)

            db.commit()
            db.refresh(box)
            db.refresh(user)

            logger.info(f"User {user.id} opened specific box {box_id}, keys remaining: {user.key_count}")

            return {
                "success": True,
                "box": {
                    "id": box.id,
                    "reward_type": box.reward_type,
                    "reward_tier": box.reward_tier,
                    "reward_data": box.reward_data,
                    "reward_description": box.reward_description,
                },
                "message": f"🎉 Box #{box.id} opened! {box.reward_description}. You have {user.key_count} keys remaining."
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
    def get_user_owned_boxes(user: User, db: Session) -> Dict[str, Any]:
        try:
            boxes = db.query(Box).filter(
                Box.owned_by_user_id == user.id,
                Box.deleted == False
            ).order_by(Box.opened_at.desc()).all()

            total_count = db.query(Box).filter(
                Box.owned_by_user_id == user.id,
                Box.deleted == False
            ).count()

            boxes_data = []
            for box in boxes:
                box_data = {
                    "id": box.id,
                    "opened_at": box.opened_at.isoformat() if box.opened_at else None
                }

                if box.is_opened:
                    box_data.update({
                        "reward_type": box.reward_type,
                        "reward_tier": box.reward_tier,
                        "reward_data": box.reward_data,
                        "reward_description": box.reward_description
                    })
                else:
                    box_data.update({
                        "reward_type": None,
                        "reward_tier": None,
                        "reward_data": None,
                        "reward_description": None
                    })

                boxes_data.append(box_data)

            return {
                "boxes": boxes_data,
                "total_owned": total_count,
            }

        except Exception as e:
            logger.error(f"Error getting owned boxes for user {user.id}: {e}")
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

    @staticmethod
    def get_box_by_box_id(token_id: int, db: Session) -> Optional[Box]:
        return db.query(Box).filter(Box.id == token_id).first()

    @staticmethod
    def update_box_ownership(box: Box, new_owner_id: int, db: Session) -> None:
        try:
            box.owned_by_user_id = new_owner_id
            db.commit()
            db.refresh(box)
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail="Error updating box ownership")
        finally:
            db.close()
