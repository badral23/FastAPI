import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from models import Box, User, UserNFT, UserSocial

logger = logging.getLogger(__name__)


class BoxOpeningService:
    """
    High-performance service for handling box opening operations
    All methods optimized for speed and concurrency
    """

    @staticmethod
    def calculate_user_keys(user: User, db: Session) -> Dict[str, Any]:
        """
        OPTIMIZED: Calculate user keys with single query
        """
        try:
            result = db.execute(text("""
                SELECT 
                    COUNT(DISTINCT CASE WHEN us.platform IN ('twitter', 'discord', 'telegram') 
                                       AND us.deleted = false THEN us.platform END) as social_platforms,
                    COUNT(CASE WHEN un.used = false AND un.deleted = false THEN 1 END) as unused_nfts,
                    STRING_AGG(DISTINCT us.platform, ',') as completed_platforms
                FROM users u
                LEFT JOIN user_social us ON u.id = us.user_id AND us.deleted = false
                LEFT JOIN user_nft un ON u.id = un.user_id AND un.deleted = false
                WHERE u.id = :user_id
                GROUP BY u.id
            """), {"user_id": user.id})

            row = result.fetchone()

            if not row:
                social_platforms = 0
                unused_nfts = 0
                completed_platforms = []
            else:
                social_platforms = row[0] or 0
                unused_nfts = row[1] or 0
                completed_platforms = (row[2] or "").split(",") if row[2] else []

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
                "platforms_completed": [p for p in completed_platforms if p],
                "required_platforms": list(required_platforms)
            }

        except Exception as e:
            logger.error(f"Error calculating keys for user {user.id}: {e}")
            raise HTTPException(status_code=500, detail="Error calculating available keys")

    @staticmethod
    def assign_next_box_atomically(user: User, db: Session) -> Optional[Box]:
        """
        LIGHTNING FAST: Atomic counter-based box assignment
        Target: <200ms response time
        """
        try:
            current_time = datetime.now(timezone.utc)

            # Step 1: Atomically get next position using counter
            result = db.execute(text("""
                UPDATE box_counter 
                SET next_position = next_position + 1
                WHERE id = 1 AND next_position <= total_boxes
                RETURNING next_position - 1 as assigned_position
            """))

            counter_row = result.fetchone()
            if not counter_row:
                logger.warning("No more boxes available (counter exhausted)")
                return None

            assigned_position = counter_row[0]

            # Step 2: Update specific box by position (no table scan)
            result = db.execute(text("""
                UPDATE boxes 
                SET is_opened = true,
                    opened_by_user_id = :user_id,
                    opened_at = :opened_at
                WHERE position = :position AND is_opened = false AND deleted = false
                RETURNING id, position, reward_type, reward_tier, reward_data, reward_description
            """), {
                "user_id": user.id,
                "opened_at": current_time,
                "position": assigned_position
            })

            box_row = result.fetchone()
            if not box_row:
                logger.error(f"Box at position {assigned_position} not found or already opened")
                return None

            # Create lightweight box object
            class FastBox:
                def __init__(self, data):
                    self.id = data[0]
                    self.position = data[1]
                    self.reward_type = data[2]
                    self.reward_tier = data[3]
                    self.reward_data = data[4]
                    self.reward_description = data[5]
                    self.opened_at = current_time
                    self.is_opened = True
                    self.opened_by_user_id = user.id

            assigned_box = FastBox(box_row)
            logger.info(f"Fast assignment: box {assigned_position} to user {user.id}")
            return assigned_box

        except SQLAlchemyError as e:
            logger.error(f"Database error in box assignment: {e}")
            raise HTTPException(status_code=500, detail="Database error during box assignment")
        except Exception as e:
            logger.error(f"Unexpected error in box assignment: {e}")
            raise HTTPException(status_code=500, detail="Unexpected error during box assignment")

    @staticmethod
    def mark_user_nfts_as_used(user: User, db: Session, nft_count_to_use: int = 1) -> List[Dict[str, Any]]:
        """
        OPTIMIZED: Mark NFTs as used with single query
        """
        try:
            result = db.execute(text("""
                WITH nfts_to_mark AS (
                    SELECT id, nft_collection, nft_id
                    FROM user_nft
                    WHERE user_id = :user_id 
                      AND used = false 
                      AND deleted = false
                    ORDER BY created_at
                    LIMIT :limit
                    FOR UPDATE SKIP LOCKED
                )
                UPDATE user_nft
                SET used = true
                FROM nfts_to_mark
                WHERE user_nft.id = nfts_to_mark.id
                RETURNING user_nft.id, nfts_to_mark.nft_collection, nfts_to_mark.nft_id
            """), {
                "user_id": user.id,
                "limit": nft_count_to_use
            })

            marked_nfts = []
            for row in result:
                marked_nfts.append({
                    "id": row[0],
                    "collection": row[1],
                    "nft_id": row[2]
                })

            if len(marked_nfts) < nft_count_to_use:
                raise HTTPException(
                    status_code=400,
                    detail=f"Not enough unused NFTs. Need {nft_count_to_use}, have {len(marked_nfts)}"
                )

            logger.info(f"Marked {len(marked_nfts)} NFTs as used for user {user.id}")
            return marked_nfts

        except Exception as e:
            logger.error(f"Error marking NFTs as used for user {user.id}: {e}")
            raise HTTPException(status_code=500, detail="Error updating NFT usage status")

    @staticmethod
    def open_box(user: User, db: Session) -> Dict[str, Any]:
        """
        LIGHTNING FAST: Main box opening function
        Target: <200ms response time with high concurrency support
        """
        try:
            # Quick validation
            if user.key_count <= 0:
                raise HTTPException(
                    status_code=400,
                    detail="No keys available. Complete social tasks or verify NFT ownership to earn keys."
                )

            # Atomic box assignment
            assigned_box = BoxOpeningService.assign_next_box_atomically(user, db)

            if not assigned_box:
                raise HTTPException(
                    status_code=404,
                    detail="No boxes available. All boxes have been opened!"
                )

            # Update user key count
            user.key_count -= 1
            db.add(user)

            # Commit all changes
            db.commit()
            db.refresh(user)

            logger.info(f"User {user.id} opened box {assigned_box.position}")

            # Calculate remaining keys properly
            key_info = BoxOpeningService.calculate_user_keys(user, db)

            return {
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
                    "remaining_keys": user.key_count
                },
                "key_consumption": {
                    "key_source": "social",
                    "nfts_used": [],
                    "remaining_keys": key_info["total_available"]
                },
                "message": f"🎉 Box #{assigned_box.position} opened! {assigned_box.reward_description}"
            }

        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Unexpected error in open_box for user {user.id}: {e}")
            raise HTTPException(status_code=500, detail="Unexpected error during box opening")

    @staticmethod
    def get_user_opened_boxes(user: User, db: Session, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """
        OPTIMIZED: Get user's opened boxes with single query
        """
        try:
            result = db.execute(text("""
                SELECT 
                    id, position, reward_type, reward_tier, reward_data, 
                    reward_description, opened_at,
                    COUNT(*) OVER() as total_count
                FROM boxes
                WHERE opened_by_user_id = :user_id 
                  AND is_opened = true 
                  AND deleted = false
                ORDER BY opened_at DESC
                LIMIT :limit OFFSET :offset
            """), {
                "user_id": user.id,
                "limit": limit,
                "offset": offset
            })

            boxes_data = []
            total_count = 0

            for row in result:
                if total_count == 0:
                    total_count = row[7]

                boxes_data.append({
                    "id": row[0],
                    "position": row[1],
                    "reward_type": row[2],
                    "reward_tier": row[3],
                    "reward_data": row[4],
                    "reward_description": row[5],
                    "opened_at": row[6].isoformat() if row[6] else None
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
        OPTIMIZED: Get statistics with single complex query
        """
        try:
            result = db.execute(text("""
                WITH stats AS (
                    SELECT 
                        COUNT(*) as total_boxes,
                        COUNT(CASE WHEN is_opened = true THEN 1 END) as opened_boxes,
                        COUNT(CASE WHEN is_opened = false THEN 1 END) as available_boxes,
                        MIN(CASE WHEN is_opened = false THEN position END) as next_position
                    FROM boxes 
                    WHERE deleted = false
                ),
                reward_stats AS (
                    SELECT 
                        reward_type,
                        COUNT(*) as count
                    FROM boxes
                    WHERE is_opened = true AND deleted = false
                    GROUP BY reward_type
                )
                SELECT 
                    s.total_boxes,
                    s.opened_boxes, 
                    s.available_boxes,
                    s.next_position,
                    COALESCE(
                        json_object_agg(rs.reward_type, rs.count) FILTER (WHERE rs.reward_type IS NOT NULL),
                        '{}'::json
                    ) as reward_distribution
                FROM stats s
                LEFT JOIN reward_stats rs ON true
                GROUP BY s.total_boxes, s.opened_boxes, s.available_boxes, s.next_position
            """))

            row = result.fetchone()
            if not row:
                return {"error": "No data available"}

            total_boxes = row[0] or 0
            opened_boxes = row[1] or 0
            available_boxes = row[2] or 0
            next_position = row[3]
            reward_distribution = row[4] or {}

            return {
                "total_boxes": total_boxes,
                "opened_boxes": opened_boxes,
                "available_boxes": available_boxes,
                "completion_percentage": round((opened_boxes / total_boxes) * 100, 2) if total_boxes > 0 else 0,
                "next_box_position": next_position,
                "reward_distribution": reward_distribution
            }

        except Exception as e:
            logger.error(f"Error getting box opening stats: {e}")
            raise HTTPException(status_code=500, detail="Error retrieving box opening statistics")

    @staticmethod
    def initialize_system(db: Session) -> Dict[str, Any]:
        """
        SETUP: Initialize the high-performance box system
        Run this once after populating your boxes
        """
        try:
            # Create counter table
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS box_counter (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    next_position INTEGER NOT NULL DEFAULT 1,
                    total_boxes INTEGER NOT NULL DEFAULT 50000,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW(),
                    CONSTRAINT single_row CHECK (id = 1)
                );
            """))

            # Initialize counter
            db.execute(text("""
                INSERT INTO box_counter (id, next_position, total_boxes) 
                VALUES (1, 1, 50000) 
                ON CONFLICT (id) DO UPDATE SET
                    next_position = 1,
                    total_boxes = 50000,
                    updated_at = NOW();
            """))

            # Add performance indexes
            db.execute(text("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_boxes_position_unopened 
                ON boxes (position) WHERE is_opened = false AND deleted = false;

                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_boxes_opened_by_user_time 
                ON boxes (opened_by_user_id, opened_at) WHERE is_opened = true;

                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_nft_unused 
                ON user_nft (user_id, used, deleted) WHERE deleted = false;

                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_social_platforms 
                ON user_social (user_id, platform, deleted) WHERE deleted = false;
            """))

            db.commit()

            logger.info("High-performance box system initialized")
            return {
                "success": True,
                "message": "System initialized for lightning-fast box opening",
                "performance": "Expected ~200ms response time with high concurrency"
            }

        except Exception as e:
            db.rollback()
            logger.error(f"Error initializing system: {e}")
            raise HTTPException(status_code=500, detail=f"System initialization failed: {str(e)}")

    @staticmethod
    def get_system_status(db: Session) -> Dict[str, Any]:
        """
        Get current system status for monitoring
        """
        try:
            result = db.execute(text("""
                SELECT next_position, total_boxes, updated_at
                FROM box_counter 
                WHERE id = 1
            """))

            row = result.fetchone()
            if not row:
                return {"error": "System not initialized"}

            next_pos, total, updated = row
            remaining = total - (next_pos - 1)

            return {
                "next_position": next_pos,
                "total_boxes": total,
                "boxes_opened": next_pos - 1,
                "boxes_remaining": remaining,
                "completion_percentage": round(((next_pos - 1) / total) * 100, 2),
                "last_updated": updated.isoformat() if updated else None,
                "status": "active" if remaining > 0 else "completed"
            }

        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {"error": str(e)}