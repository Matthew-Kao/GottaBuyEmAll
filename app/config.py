from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7
    google_client_id: str
    google_client_secret: str
    cloudinary_cloud_name: str
    cloudinary_api_key: str
    cloudinary_api_secret: str
    tripay_api_key: str
    tripay_private_key: str
    tripay_merchant_code: str

    class Config:
        env_file = ".env"


settings = Settings()