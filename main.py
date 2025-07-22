from fastapi import APIRouter, FastAPI

from crud import create_crud_router
from database import Base, engine
from models import User, UserNFT, UserSocial
from schemas import UserCreateSchema, UserSchema, UserNFTCreateSchema, UserNFTSchema, UserSocialCreateSchema, \
    UserSocialSchema

Base.metadata.create_all(bind=engine)

app = FastAPI()

user_router = create_crud_router(model=User, schema_create=UserCreateSchema, schema_read=UserSchema)
user_nft_router = create_crud_router(model=UserNFT, schema_create=UserNFTCreateSchema, schema_read=UserNFTSchema)
user_social_router = create_crud_router(model=UserSocial, schema_create=UserSocialCreateSchema,
                                        schema_read=UserSocialSchema)

router = APIRouter()
router.include_router(user_router)
router.include_router(user_nft_router)
router.include_router(user_social_router)

app.include_router(router)
