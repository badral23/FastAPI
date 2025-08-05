import asyncio
import os
from typing import List, Optional

from sqlalchemy.orm import Session
from web3 import Web3

from models import User
from services.box_service import BoxOpeningService

RPC_URL = os.getenv("APECHAIN_RPC_URL")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")
RECEIVER_ADDRESS = os.getenv("RECEIVER_ADDRESS")

w3 = Web3(Web3.HTTPProvider(RPC_URL))

ERC721_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [{"name": "owner", "type": "address"}, {"name": "index", "type": "uint256"}],
        "name": "tokenOfOwnerByIndex",
        "outputs": [{"name": "tokenId", "type": "uint256"}],
        "type": "function"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "from", "type": "address"},
            {"indexed": True, "name": "to", "type": "address"},
            {"indexed": True, "name": "tokenId", "type": "uint256"}
        ],
        "name": "Transfer",
        "type": "event"
    }
]

contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=ERC721_ABI)

event_filter = contract.events.Transfer.create_filter(from_block=26710864)


def check_user_nfts(wallet_address: str, nft_collections: List[str]) -> List[dict]:
    owned_nfts = []

    try:
        if not w3.is_address(wallet_address):
            raise ValueError("Invalid wallet address")

        wallet_address = w3.to_checksum_address(wallet_address)

        for collection_address in nft_collections:
            if not w3.is_address(collection_address):
                print(f"Invalid collection address: {collection_address}")
                continue

            contract = w3.eth.contract(
                address=w3.to_checksum_address(collection_address),
                abi=ERC721_ABI
            )

            balance = contract.functions.balanceOf(wallet_address).call()

            if balance > 0:
                for token_id in range(balance):
                    nft_id = contract.functions.tokenOfOwnerByIndex(wallet_address, token_id).call()
                    owned_nfts.append({
                        'collection': collection_address,
                        'nft_id': nft_id
                    })

    except Exception as e:
        print(f"Error fetching NFTs: {e}")

    return owned_nfts


async def listen_for_events(db: Session):
    if not w3.is_connected():
        print("Web3 provider not connected. Check APECHAIN_RPC_URL.")
        return

    print(f"Connected to Web3 provider, latest block: {w3.eth.block_number}")
    print(f"Listening for events on contract: {CONTRACT_ADDRESS} and receiver: {RECEIVER_ADDRESS}")

    last_processed_block = w3.eth.block_number
    event_filter = contract.events.Transfer.create_filter(from_block=last_processed_block)

    while True:
        try:
            current_block = w3.eth.block_number
            print(f"Current block: {current_block}")

            # Fetch new events
            new_entries = event_filter.get_new_entries()
            print(f"Checked for new entries, found: {len(new_entries)}")

            if new_entries:
                for event in new_entries:
                    try:
                        print(f"Raw event data: {event}")
                        from_address = event['args']['from']
                        to_address = event['args']['to']

                        if w3.to_checksum_address(to_address) == w3.to_checksum_address(RECEIVER_ADDRESS):
                            print(f"Transfer event to receiver detected: {event}")

                            user = get_user_by_wallet_address(from_address, db)
                            box = BoxOpeningService.get_box_by_box_id(event['args']['tokenId'], db)

                            if user:
                                if box:
                                    BoxOpeningService.update_box_ownership(box, user.id, db)
                                else:
                                    print(f"No box found for tokenId: {event['args']['tokenId']}")
                            else:
                                user = User(wallet_address=from_address)
                                db.add(user)
                                db.commit()

                                if box:
                                    box.owned_by_user_id = user.id
                                    db.commit()
                                    db.refresh(user)
                                    db.refresh(box)
                                else:
                                    print(f"No box found for tokenId: {event['args']['tokenId']}")

                    except Exception as e:
                        print(f"Error processing event {event}: {e}")

            if current_block > last_processed_block + 100:
                last_processed_block = current_block
                event_filter = contract.events.Transfer.create_filter(from_block=last_processed_block)
                print(f"Refreshed event filter at block {last_processed_block}")

            await asyncio.sleep(2)

        except Exception as e:
            print(f"Error in event listener: {e}")
            event_filter = contract.events.Transfer.create_filter(from_block=last_processed_block)
            await asyncio.sleep(2)


def get_user_by_wallet_address(wallet_address: str, db: Session) -> Optional[User]:
    return db.query(User).filter(User.wallet_address == wallet_address).first()


def start_event_listener():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(listen_for_events())
