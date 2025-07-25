from crud import create_authenticated_crud_router
from models import UserNFT
from schemas import UserNFTCreateSchema, UserNFTSchema

# Users can only manage their own NFTs
user_nft_router = create_authenticated_crud_router(
    model=UserNFT,
    schema_create=UserNFTCreateSchema,
    schema_read=UserNFTSchema,
    require_auth=True,
    owner_field="user_id"  # NFTs belong to users
)