from fastapi import APIRouter
from app.api.routes import auth, datasets, health, users

api_router = APIRouter()

# Register routes
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(auth.router, tags=["Authentication"])
api_router.include_router(users.router, tags=["Users Administration"])
api_router.include_router(datasets.router, tags=["Datasets"])
