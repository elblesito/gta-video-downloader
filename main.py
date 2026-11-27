
import os
import tempfile
import secrets
import subprocess
import cloudinary
import cloudinary.uploader

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from urllib.parse import urlparse

app = FastAPI()

# Configuración de Cloudinary
cloudinary.config(
    cloud_name=os.environ["CLOUDINARY_CLOUD_NAME"],
    api_key=os.environ["CLOUDINARY_API_KEY"],
    api_secret=os.environ["CLOUDINARY_API_SECRET"],
    secure=True
)

class VideoRequest(BaseModel):
    url: str

@app.get("/")
def health():
    return {"status": "online"}

@app.post("/download")
def download_video(req: VideoRequest):

    parsed = urlparse(req.url)
    host = (parsed.hostname or "").lower()

    allowed = (
        host == "youtube.com"
        or host.endswith(".youtube.com")
        or host == "youtu.be"
        or host == "twitch.tv"
        or host.endswith(".twitch.tv")
    )

    if not allowed:
        raise HTTPException(
            400, "Only YouTube and Twitch URLs are accepted"
        )

    with tempfile.TemporaryDirectory() as folder:

        output = os.path.join(folder, "source.%(ext)s")

        command = [
            "yt-dlp",
            "--no-playlist",
            "--match-filter", "!is_live",
            "-f", "bv*[height<=1080]+ba/b[height<=1080]",
            "--merge-output-format", "mp4",
            "-o", output,
            req.url
        ]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=1800
        )

        if result.returncode != 0:
            raise HTTPException(
                400, result.stderr[-1500:]
            )

        files = [
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if f.endswith(".mp4")
        ]

        if not files:
            raise HTTPException(500, "No MP4 file generated")

        uploaded = cloudinary.uploader.upload_large(
            files[0],
            resource_type="video",
            folder="gtavi_clips",
            public_id="source_" + secrets.token_hex(8)
        )

        return {
            "status": "success",
            "video_url": uploaded["secure_url"],
            "public_id": uploaded["public_id"],
            "duration": uploaded.get("duration")
        }
