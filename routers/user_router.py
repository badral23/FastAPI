from crud import create_crud_router, CRUDRouterConfig
from handlers.user_handlers import (
    create_user_with_wallet_address_validation,
    update_user_with_wallet_address_validation
)
from models import User
from schemas import UserCreateSchema, UserSchema

user_custom_handlers = {
    "create": create_user_with_wallet_address_validation,
    "update": update_user_with_wallet_address_validation,
}

user_config = CRUDRouterConfig(
    enable_hard_delete=False,
    enable_restore=True,
)

user_router = create_crud_router(
    model=User,
    schema_create=UserCreateSchema,
    schema_read=UserSchema,
    custom_handlers=user_custom_handlers,
    router_config=user_config
)
