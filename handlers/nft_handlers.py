import os
from typing import List

from web3 import Web3

RPC_URL = os.getenv("APECHAIN_RPC_URL")
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
    }
]


def check_user_nfts(wallet_address: str, nft_collections: List[str]) -> List[dict]:
    owned_nfts = []

    try:
        if not w3.is_address(wallet_address):
            raise ValueError("Invalid wallet address")

        # Convert to checksum address
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
