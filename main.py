from fastapi import FastAPI

import models
from database import engine
from routes import item

# Create database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# Include routers
app.include_router(item.router)


@app.get("/")
async def root():
    return {"message": "Welcome to the FastAPI application with Neon DB"}
