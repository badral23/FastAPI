from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware

from database import Base, engine
from routers.additional_endpoints import additional_router
from routers.auth_router import router as auth_router
from routers.user_nft_router import user_nft_router
from routers.user_router import user_router
from routers.user_social_router import user_social_router

Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI(
    title="Hii Box API",
    description="API for managing users, their NFTs and social accounts",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth_router)
api_router.include_router(user_router)
api_router.include_router(user_nft_router)
api_router.include_router(user_social_router)
api_router.include_router(additional_router)

app.include_router(api_router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
