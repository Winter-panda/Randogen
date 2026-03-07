from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Randogen API"
    app_version: str = "0.1.0"
    debug: bool = True
    api_prefix: str = "/api"

    ors_api_key: str = ""
    ors_base_url: str = "https://api.openrouteservice.org"
    ors_profile: str = "foot-hiking"
    ors_request_timeout_s: int = 20
    enable_real_routing: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()