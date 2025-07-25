

from crud import create_authenticated_crud_router, CRUDRouterConfig
from handlers.user_social_handlers import (
    create_user_social_with_validation,
    update_user_social_with_validation
)
from models import UserSocial
from schemas import UserSocialCreateSchema, UserSocialSchema

user_social_custom_handlers = {
    "create": create_user_social_with_validation,
    "update": update_user_social_with_validation,
}

user_social_config = CRUDRouterConfig(
    enable_hard_delete=False,
    enable_restore=True,
)

# Users can only manage their own social accounts
user_social_router = create_authenticated_crud_router(
    model=UserSocial,
    schema_create=UserSocialCreateSchema,
    schema_read=UserSocialSchema,
    custom_handlers=user_social_custom_handlers,
    router_config=user_social_config,
    require_auth=True,
    owner_field="user_id"  # Social accounts belong to users
)