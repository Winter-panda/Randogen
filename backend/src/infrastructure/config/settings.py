from pydantic import field_validator
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
    route_duplicate_similarity_threshold: float = 0.75

    prefer_trails: bool = True
    prefer_green_routes: bool = True
    avoid_noisy_roads: bool = True
    enable_weather_context: bool = True
    weather_request_timeout_s: int = 8

    @field_validator(
        "debug",
        "enable_real_routing",
        "prefer_trails",
        "prefer_green_routes",
        "avoid_noisy_roads",
        "enable_weather_context",
        mode="before",
    )
    @classmethod
    def _coerce_bool(cls, value: object) -> object:
        if not isinstance(value, str):
            return value

        normalized = value.strip().lower()
        truthy_values = {"1", "true", "yes", "y", "on"}
        falsy_values = {"0", "false", "no", "n", "off", "", "release", "prod", "production"}

        if normalized in truthy_values:
            return True
        if normalized in falsy_values:
            return False
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
