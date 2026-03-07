from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes.route_routes import router as route_router
from src.infrastructure.config.settings import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(route_router, prefix=settings.api_prefix)
