from crud import create_crud_router
from models import UserNFT
from schemas import UserNFTCreateSchema, UserNFTSchema

user_nft_router = create_crud_router(
    model=UserNFT,
    schema_create=UserNFTCreateSchema,
    schema_read=UserNFTSchema
)
