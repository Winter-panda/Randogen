from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Randogen API"
    app_version: str = "0.1.0"
    debug: bool = False
    api_prefix: str = "/api"

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    ors_api_key: str = ""
    ors_base_url: str = "https://api.openrouteservice.org"
    ors_profile: str = "foot-hiking"
    ors_request_timeout_s: int = 20
    enable_real_routing: bool = True

    route_candidate_search_count: int = 8
    route_distance_tolerance_ratio: float = 0.45
    route_min_score: float = 0.2
    route_round_trip_points: int = 3

    prefer_trails: bool = True
    prefer_green_routes: bool = True
    avoid_noisy_roads: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
