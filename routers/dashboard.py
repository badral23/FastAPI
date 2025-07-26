from fastapi import APIRouter

from crud import create_crud_router, CRUDRouterConfig
from handlers.auth_handlers import get_current_user
from handlers.user_social_handlers import create_user_social_with_validation, update_user_social_with_validation
from models import User, UserSocial, SupportedNFTCollection
from schemas import UserCreateSchema, UserSchema, UserSocialCreateSchema, UserSocialSchema, \
    SupportedNFTCollectionCreateSchema, SupportedNFTCollectionSchema

router = APIRouter()

user_config = CRUDRouterConfig(
    enable_hard_delete=False,
    enable_restore=True,
)

user_social_config = CRUDRouterConfig(
    enable_hard_delete=False,
    enable_restore=True,
)

supported_nft_collection_config = CRUDRouterConfig(
    enable_hard_delete=False,
    enable_restore=True,
)

user_router = create_crud_router(
    model=User,
    prefix="/users",
    schema_create=UserCreateSchema,
    schema_read=UserSchema,
    router_config=user_config,
    auth_dependency=get_current_user,
    tags=["Users"]
)

user_social_router = create_crud_router(
    model=UserSocial,
    prefix="/user-socials",
    schema_create=UserSocialCreateSchema,
    schema_read=UserSocialSchema,
    router_config=user_social_config,
    auth_dependency=get_current_user,
    tags=["User Socials"],
    custom_handlers={
        "create": create_user_social_with_validation,
        "update": update_user_social_with_validation,
    }
)

supported_nft_collection_router = create_crud_router(
    model=SupportedNFTCollection,
    prefix="/supported-nft-collections",
    schema_create=SupportedNFTCollectionCreateSchema,
    schema_read=SupportedNFTCollectionSchema,
    router_config=supported_nft_collection_config,
    auth_dependency=get_current_user,
    tags=["User Socials"],
    custom_handlers={
        "create": create_user_social_with_validation,
        "update": update_user_social_with_validation,
    }
)

router.include_router(user_router)
router.include_router(user_social_router)
router.include_router(supported_nft_collection_router)
