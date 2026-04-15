import cloudinary
import cloudinary.uploader
from app.config import settings

cloudinary.config(
    cloud_name=settings.cloudinary_cloud_name,
    api_key=settings.cloudinary_api_key,
    api_secret=settings.cloudinary_api_secret,
)


def upload_image(file_bytes: bytes, folder: str = "gottabuyemall") -> str | None:
    try:
        result = cloudinary.uploader.upload(
            file_bytes,
            folder=folder,
            transformation=[
                {"width": 400, "height": 400, "crop": "fill", "gravity": "face"},
                {"quality": "auto", "fetch_format": "auto"},
            ],
        )
        return result.get("secure_url")
    except Exception as e:
        print(f"cloudinary upload error: {e}")
        return None