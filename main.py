import asyncio
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import APIRouter
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import Base, engine
from database import SessionLocal
from handlers.nft_handlers import start_event_listener, listen_for_events
from routers.additional_endpoints import additional_router
from routers.auth_router import router as auth_router
from routers.box_router import router as box_router
from routers.dashboard_router import router as dashboard_router
from routers.public_router import router as public_router
from routers.user_router import router as user_router

Base.metadata.create_all(bind=engine)

load_dotenv()

FRONTEND_URL = os.getenv("FRONTEND_URL")


def run_event_listener():
    start_event_listener()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async def start_event_listener_func():
        db = SessionLocal()
        try:
            await listen_for_events(db)
        except Exception as e:
            print(f"Event listener crashed: {e}")
        finally:
            db.close()

    task = asyncio.create_task(start_event_listener_func())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            print("Event listener task cancelled")


app = FastAPI(
    title="Hii Box API",
    description="API for managing users, their NFTs, social accounts, and box opening",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth_router, prefix="/auth", tags=["Auth"])
api_router.include_router(dashboard_router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(additional_router)
api_router.include_router(box_router, prefix="/boxes", tags=["Boxes"])
api_router.include_router(user_router, prefix="/user", tags=["User"])
api_router.include_router(public_router, prefix="/public", tags=["Public"])

app.include_router(api_router)


@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
