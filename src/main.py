from fastapi import FastAPI
from src.api.routes import user.py # Import your fixed route file

app.include_router(/api/routes/user.router)

# Metadata for your tags to make the UI look professional
tags_metadata = [
    {
        "name": "users",
        "description": "Operations with users. The **login** logic is also here.",
    },
    {
        "name": "items",
        "description": "Manage items. So _fancy_ they have their own docs.",
    },
]

app = FastAPI(
    title="StellArts API",
    description="A public API with full Swagger documentation.",
    version="1.0.0",
    openapi_tags=tags_metadata,
    
    # Register the router
    app.include_router(user.router)
    # Acceptance Criteria: Host at /api/docs
    docs_url="/api/docs", 
    # Optional: You can also move the schema logic to match
    openapi_url="/api/openapi.json",
    redoc_url="/api/redoc"
)
