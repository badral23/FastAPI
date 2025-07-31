# Updated services/box_service.py using ORM instead of raw SQL

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy import func, case

from models import Box, User, UserNFT, UserSocial

logger = logging.getLogger(__name__)


class BoxOpeningService:
    """
    Updated service for NFT-based box opening operations using ORM
    """

    @staticmethod
    def assign_box_to_user(user: User, nft_token_id: str, db: Session) -> Dict[str, Any]:
        """
        Assign a specific box to user when they send their box NFT
        This happens BEFORE opening - just assigns ownership
        """
        try:
            # Validate that this is a valid box NFT token ID
            try:
                box_position = int(nft_token_id)
                if box_position < 1 or box_position > 50000:
                    raise ValueError("Invalid box position")
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid box NFT token ID"
                )

            # Get the box using ORM
            box = Box.get_unassigned_box_by_position(db, box_position)

            if not box:
                # Check if box exists but is already assigned
                existing_box = db.query(Box).filter(
                    Box.position == box_position,
                    Box.deleted == False
                ).first()

                if not existing_box:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Box #{box_position} not found"
                    )

                if existing_box.assigned_to_user_id:
                    if existing_box.assigned_to_user_id == user.id:
                        # Already assigned to this user
                        return {
                            "success": True,
                            "message": f"Box #{box_position} is already assigned to you",
                            "box": {
                                "id": existing_box.id,
                                "position": existing_box.position,
                                "reward_type": existing_box.reward_type,
                                "reward_tier": existing_box.reward_tier,
                                "reward_description": existing_box.reward_description,
                                "status": "opened" if existing_box.is_opened else "assigned_unopened"
                            }
                        }
                    else:
                        raise HTTPException(
                            status_code=409,
                            detail=f"Box #{box_position} is already assigned to another user"
                        )

            # Assign box to user using ORM method
            box.assign_to_user(db, user.id)

            logger.info(f"Box #{box_position} assigned to user {user.id}")

            return {
                "success": True,
                "message": f"Box #{box_position} has been assigned to you! You can now open it.",
                "box": {
                    "id": box.id,
                    "position": box.position,
                    "reward_type": box.reward_type,
                    "reward_tier": box.reward_tier,
                    "reward_description": box.reward_description,
                    "status": "assigned_unopened"
                }
            }

        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Error assigning box to user {user.id}: {e}")
            raise HTTPException(status_code=500, detail="Error assigning box")

    @staticmethod
    def open_assigned_box(user: User, box_position: int, db: Session) -> Dict[str, Any]:
        """
        Open a box that has already been assigned to the user
        """
        try:
            # Get the assigned box using ORM
            box = Box.get_assigned_box(db, user.id, box_position)

            if not box:
                raise HTTPException(
                    status_code=404,
                    detail=f"Box #{box_position} is not assigned to you or doesn't exist"
                )

            # Check if already opened
            if box.is_opened:
                raise HTTPException(
                    status_code=409,
                    detail=f"Box #{box_position} has already been opened"
                )

            # Open the box using ORM method
            box.open_box(db, user.id)

            logger.info(f"User {user.id} opened assigned box {box_position}")

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
                    "wallet_address": user.wallet_address
                },
                "message": f"🎉 Box #{box.position} opened! {box.reward_description}"
            }

        except HTTPException:
            raise
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            db.rollback()
            logger.error(f"Error opening box for user {user.id}: {e}")
            raise HTTPException(status_code=500, detail="Error opening box")

    @staticmethod
    def get_user_assigned_boxes(user: User, db: Session) -> Dict[str, Any]:
        """
        Get boxes assigned to user (both opened and unopened) using ORM
        """
        try:
            # Get all assigned boxes using ORM
            boxes = Box.get_user_assigned_boxes(db, user.id)

            boxes_data = []
            for box in boxes:
                box_data = {
                    "id": box.id,
                    "position": box.position,
                    "reward_type": box.reward_type,
                    "reward_tier": box.reward_tier,
                    "status": "opened" if box.is_opened else "assigned_unopened",
                    "assigned_at": box.assigned_at.isoformat() if box.assigned_at else None
                }

                # Only show reward details if opened
                if box.is_opened:
                    box_data.update({
                        "reward_data": box.reward_data,
                        "reward_description": box.reward_description,
                        "opened_at": box.opened_at.isoformat() if box.opened_at else None
                    })
                else:
                    box_data["reward_description"] = "Box not opened yet"

                boxes_data.append(box_data)

            opened_count = len([b for b in boxes if b.is_opened])
            unopened_count = len(boxes) - opened_count

            return {
                "boxes": boxes_data,
                "total_assigned": len(boxes),
                "opened_count": opened_count,
                "unopened_count": unopened_count
            }

        except Exception as e:
            logger.error(f"Error getting assigned boxes for user {user.id}: {e}")
            raise HTTPException(status_code=500, detail="Error retrieving assigned boxes")

    @staticmethod
    def get_box_opening_stats(db: Session) -> Dict[str, Any]:
        """
        Get statistics using ORM queries
        """
        try:
            # Get basic stats using ORM
            stats = Box.get_box_stats(db)

            if not stats:
                return {"error": "No data available"}

            # Get reward distribution using ORM
            reward_stats = db.query(
                Box.reward_type,
                func.count(Box.id).label('count')
            ).filter(
                Box.is_opened == True,
                Box.deleted == False
            ).group_by(Box.reward_type).all()

            reward_distribution = {stat.reward_type: stat.count for stat in reward_stats}

            total_boxes = stats.total_boxes or 0
            assigned_boxes = stats.assigned_boxes or 0
            opened_boxes = stats.opened_boxes or 0
            unassigned_boxes = stats.unassigned_boxes or 0

            return {
                "total_boxes": total_boxes,
                "assigned_boxes": assigned_boxes,
                "opened_boxes": opened_boxes,
                "unassigned_boxes": unassigned_boxes,
                "assignment_percentage": round((assigned_boxes / total_boxes) * 100, 2) if total_boxes > 0 else 0,
                "opening_percentage": round((opened_boxes / total_boxes) * 100, 2) if total_boxes > 0 else 0,
                "reward_distribution": reward_distribution
            }

        except Exception as e:
            logger.error(f"Error getting box opening stats: {e}")
            raise HTTPException(status_code=500, detail="Error retrieving box opening statistics")

    @staticmethod
    def calculate_user_keys(user: User, db: Session) -> Dict[str, Any]:
        """
        Calculate user keys using ORM queries
        """
        try:
            # Count social platforms using ORM
            social_platforms = db.query(UserSocial).filter(
                UserSocial.user_id == user.id,
                UserSocial.platform.in_(['twitter', 'discord', 'telegram']),
                UserSocial.deleted == False
            ).distinct(UserSocial.platform).count()

            # Count unused NFTs using ORM
            unused_nfts = db.query(UserNFT).filter(
                UserNFT.user_id == user.id,
                UserNFT.used == False,
                UserNFT.deleted == False
            ).count()

            # Get completed platforms
            completed_platforms_query = db.query(UserSocial.platform).filter(
                UserSocial.user_id == user.id,
                UserSocial.deleted == False
            ).distinct().all()

            completed_platforms = [platform[0] for platform in completed_platforms_query]

            # Calculate keys
            required_platforms = {"twitter", "discord", "telegram"}
            social_tasks_completed = social_platforms >= 3
            social_keys = 1 if social_tasks_completed else 0

            # NFT key calculation per specification
            if unused_nfts == 0:
                nft_keys = 0
            elif unused_nfts == 1:
                nft_keys = 2  # Minimum 2 keys for 1 NFT
            else:
                nft_keys = min(unused_nfts, 10)  # 1 key per NFT, max 10

            total_available = social_keys + nft_keys

            return {
                "social_keys": social_keys,
                "nft_keys": nft_keys,
                "total_available": total_available,
                "social_completed": social_tasks_completed,
                "nft_count": unused_nfts,
                "unused_nft_count": unused_nfts,
                "platforms_completed": completed_platforms,
                "required_platforms": list(required_platforms)
            }

        except Exception as e:
            logger.error(f"Error calculating keys for user {user.id}: {e}")
            raise HTTPException(status_code=500, detail="Error calculating available keys")

    @staticmethod
    def verify_nft_ownership_and_assign(user: User, nft_token_id: str, transaction_hash: str, db: Session) -> Dict[
        str, Any]:
        """
        Verify that user sent the NFT and assign the corresponding box
        """
        try:
            # TODO: Add actual NFT transfer verification logic here
            # This should check:
            # 1. Transaction hash is valid
            # 2. NFT was transferred to your contract/wallet
            # 3. Transaction sender matches user's wallet
            # 4. NFT token ID corresponds to a valid box

            # For now, we'll assume verification passed and assign the box
            result = BoxOpeningService.assign_box_to_user(user, nft_token_id, db)

            # Log the transaction for audit trail
            logger.info(f"NFT verification and box assignment for user {user.id}, "
                        f"token {nft_token_id}, tx {transaction_hash}")

            return result

        except Exception as e:
            logger.error(f"Error in NFT verification and assignment: {e}")
            raise