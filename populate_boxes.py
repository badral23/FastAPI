import random
import json
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from database import SessionLocal, engine
from models import Base, Box

# Reward configuration based on your requirements
REWARD_CONFIG = {
    "standard_nft": {
        "quantity": 45000,
        "probability": 0.90,  # 90%
        "description": "Standard NFT from Hii Box collection"
    },
    "apecoin": {
        "quantity": 4000,
        "probability": 0.08,  # 8%
        "tiers": {
            "tier1": {"quantity": 2000, "amount": 10, "description": "10 ApeCoin"},
            "tier2": {"quantity": 1200, "amount": 25, "description": "25 ApeCoin"},
            "tier3": {"quantity": 600, "amount": 50, "description": "50 ApeCoin"},
            "tier4": {"quantity": 200, "amount": 100, "description": "100 ApeCoin"},
        }
    },
    "rare_nft": {
        "quantity": 999,
        "probability": 0.01998,  # ~1.998%
        "description": "Rare limited edition NFT"
    },
    "apefest_ticket": {
        "quantity": 1,
        "probability": 0.00002,  # ~0.002%
        "description": "Exclusive ApeFest Las Vegas Ticket - Ultra Rare!"
    }
}


def create_reward_list() -> List[Dict[str, Any]]:
    """
    Create a list of all 50,000 rewards based on the configuration.
    """
    rewards = []

    # Standard NFTs (45,000)
    for i in range(REWARD_CONFIG["standard_nft"]["quantity"]):
        rewards.append({
            "reward_type": "standard_nft",
            "reward_tier": None,
            "reward_data": {"nft_id": f"standard_{i + 1:05d}"},
            "reward_description": REWARD_CONFIG["standard_nft"]["description"]
        })

    # ApeCoin rewards (4,000 total)
    for tier, tier_config in REWARD_CONFIG["apecoin"]["tiers"].items():
        for i in range(tier_config["quantity"]):
            rewards.append({
                "reward_type": "apecoin",
                "reward_tier": tier,
                "reward_data": {
                    "amount": tier_config["amount"],
                    "currency": "APE",
                    "tier": tier
                },
                "reward_description": tier_config["description"]
            })

    # Rare NFTs (999)
    for i in range(REWARD_CONFIG["rare_nft"]["quantity"]):
        rewards.append({
            "reward_type": "rare_nft",
            "reward_tier": None,
            "reward_data": {"nft_id": f"rare_{i + 1:03d}"},
            "reward_description": REWARD_CONFIG["rare_nft"]["description"]
        })

    # ApeFest Ticket (1)
    rewards.append({
        "reward_type": "apefest_ticket",
        "reward_tier": "vip",
        "reward_data": {
            "event": "ApeFest Las Vegas 2025",
            "location": "Las Vegas, Nevada",
            "ticket_type": "VIP Access",
            "transferable": True
        },
        "reward_description": REWARD_CONFIG["apefest_ticket"]["description"]
    })

    return rewards


def shuffle_and_create_boxes(db: Session):
    """
    Create 50,000 boxes with shuffled rewards.
    """
    print("🎯 Creating reward list...")
    rewards = create_reward_list()

    # Verify we have exactly 50,000 rewards
    total_rewards = len(rewards)
    print(f"📊 Total rewards created: {total_rewards}")

    if total_rewards != 50000:
        raise ValueError(f"Expected 50,000 rewards, got {total_rewards}")

    # Shuffle the rewards randomly
    print("🔀 Shuffling rewards...")
    random.shuffle(rewards)

    # Create boxes with shuffled rewards
    print("📦 Creating boxes in database...")
    boxes_to_create = []

    for position in range(1, 50001):  # Positions 1 to 50,000
        reward = rewards[position - 1]  # Array is 0-indexed

        box_data = {
            "position": position,
            "reward_type": reward["reward_type"],
            "reward_tier": reward["reward_tier"],
            "reward_data": reward["reward_data"],
            "reward_description": reward["reward_description"],
            "is_opened": False,
            "opened_by_user_id": None,
            "opened_at": None
        }

        boxes_to_create.append(Box(**box_data))

        # Batch insert every 1000 boxes for better performance
        if len(boxes_to_create) >= 1000:
            db.add_all(boxes_to_create)
            db.commit()
            print(f"✅ Inserted boxes {position - 999} to {position}")
            boxes_to_create = []

    # Insert any remaining boxes
    if boxes_to_create:
        db.add_all(boxes_to_create)
        db.commit()
        print(f"✅ Inserted final {len(boxes_to_create)} boxes")

    print("🎉 All 50,000 boxes created successfully!")


def verify_box_distribution(db: Session):
    """
    Verify the reward distribution is correct.
    """
    print("\n📊 Verifying reward distribution...")

    # Count each reward type
    standard_nft_count = db.query(Box).filter(Box.reward_type == "standard_nft").count()
    apecoin_count = db.query(Box).filter(Box.reward_type == "apecoin").count()
    rare_nft_count = db.query(Box).filter(Box.reward_type == "rare_nft").count()
    apefest_count = db.query(Box).filter(Box.reward_type == "apefest_ticket").count()

    total_count = db.query(Box).count()

    print(f"Standard NFTs: {standard_nft_count:,} (Expected: 45,000)")
    print(f"ApeCoin: {apecoin_count:,} (Expected: 4,000)")
    print(f"Rare NFTs: {rare_nft_count:,} (Expected: 999)")
    print(f"ApeFest Tickets: {apefest_count:,} (Expected: 1)")
    print(f"Total Boxes: {total_count:,} (Expected: 50,000)")

    # Verify ApeCoin tier distribution
    print("\n🪙 ApeCoin Tier Distribution:")
    for tier in ["tier1", "tier2", "tier3", "tier4"]:
        tier_count = db.query(Box).filter(
            Box.reward_type == "apecoin",
            Box.reward_tier == tier
        ).count()
        expected = REWARD_CONFIG["apecoin"]["tiers"][tier]["quantity"]
        amount = REWARD_CONFIG["apecoin"]["tiers"][tier]["amount"]
        print(f"  {tier} ({amount} APE): {tier_count:,} (Expected: {expected:,})")


def main():
    """
    Main function to populate the boxes table.
    """
    print("🚀 Starting Hii Box population process...")

    # Create tables
    Base.metadata.create_all(bind=engine)

    # Create database session
    db = SessionLocal()

    try:
        # Check if boxes already exist
        existing_boxes = db.query(Box).count()
        if existing_boxes > 0:
            print(f"⚠️  Found {existing_boxes} existing boxes in database.")
            response = input("Do you want to delete them and recreate? (y/N): ")
            if response.lower() == 'y':
                print("🗑️  Deleting existing boxes...")
                db.query(Box).delete()
                db.commit()
                print("✅ Existing boxes deleted.")
            else:
                print("❌ Aborted. Existing boxes kept.")
                return

        # Set random seed for reproducible results (optional)
        random.seed(42)  # Remove this line for truly random results

        # Create and shuffle boxes
        shuffle_and_create_boxes(db)

        # Verify the distribution
        verify_box_distribution(db)

        print("\n🎉 Hii Box initialization completed successfully!")
        print("🎯 Your campaign is ready with 50,000 shuffled reward boxes!")

    except Exception as e:
        db.rollback()
        print(f"❌ Error occurred: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()