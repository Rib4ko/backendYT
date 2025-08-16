from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, HttpUrl, field_validator, model_validator
import yt_dlp
import ffmpeg
import os
import logging
import shutil
from fastapi.responses import FileResponse, JSONResponse
from fastapi import BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware


# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# Setup FastAPI app
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://frontendyt-ohq8.onrender.com"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# File paths
TEMP_DIR = "/tmp/yt_clips/"
os.makedirs(TEMP_DIR, exist_ok=True)



# Pydantic v2 validation
class ClipRequest(BaseModel):
    url: HttpUrl
    start: int  # Start time in seconds
    end: int    # End time in seconds

    @field_validator('start')
    @classmethod
    def start_non_negative(cls, v):
        if v < 0:
            raise ValueError('start must be non-negative')
        return v

    @field_validator('end')
    @classmethod
    def end_non_negative(cls, v):
        if v < 0:
            raise ValueError('end must be non-negative')
        return v

    @model_validator(mode="after")
    def check_start_end(self):
        if self.end <= self.start:
            raise ValueError('end must be greater than start')
        return self


@app.post("/clip")
async def create_clip(request: ClipRequest):
    logger.info(f"Received clip request: url={request.url}, start={request.start}, end={request.end}")
    result = create_clip_task(request.url, request.start, request.end)
    if isinstance(result, dict) and "error" in result:
        logger.error(f"Clip creation failed: {result['error']}")
        raise HTTPException(status_code=500, detail=result["error"])
    logger.info(f"Clip created successfully: {result['downloadUrl']}")
    return result


def create_clip_task(url, start, end):
    downloaded_path = None
    trimmed_path = None
    try:
        # Step 1: Measure download time
        start_time = time.time()  # Start measuring the overall time

        logger.info("Starting video download")
        start_download = time.time()  # Start measuring download time

        # Download the video using yt-dlp (limit to max 1080p)
        ydl_opts = {
            'outtmpl': f'{TEMP_DIR}%(id)s.%(ext)s',
            'format': 'bestvideo[height<=1080]+bestaudio/best',  # Max resolution 1080p
            'merge_output_format': 'mp4',
            'noplaylist': True,  # Prevent downloading playlists if URL is a playlist
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(str(url), download=True)
            downloaded_path = ydl.prepare_filename(info_dict)
            trimmed_filename = f"{info_dict['id']}_clip.mp4"
            trimmed_path = os.path.join(TEMP_DIR, trimmed_filename)

        end_download = time.time()  # End download time
        download_time = end_download - start_download
        logger.info(f"Video download took {download_time:.2f} seconds")

        # Step 2: Measure trimming time
        logger.info("Starting video trimming")
        start_trimming = time.time()  # Start measuring trimming time

        # Use re-encoding with high quality settings for trimming
        (
            ffmpeg
            .input(downloaded_path, ss=start, to=end)
            .output(
                trimmed_path,
                vcodec='libx264',
                acodec='aac',
                video_bitrate='3000k',  # Higher video bitrate
                audio_bitrate='192k',   # Higher audio bitrate
                preset='medium',          # Better compression/quality
                crf=18                  # Visually lossless (lower is better)
            )
            .run(overwrite_output=True)
        )

        end_trimming = time.time()  # End trimming time
        trimming_time = end_trimming - start_trimming
        logger.info(f"Video trimming took {trimming_time:.2f} seconds")

        # Step 3: Measure total processing time
        end_time = time.time()  # End overall time
        total_time = end_time - start_time
        logger.info(f"Total processing time: {total_time:.2f} seconds")

        # Return download URL, wait time, and a warning about possible imprecise cuts
        download_url = f"http://localhost:8000/download/{trimmed_filename}"
        return {
            "downloadUrl": download_url,
            "waitSeconds": int(total_time),  # Total processing time
            "warning": "Clip boundaries are accurate with re-encoding."
        }

    except Exception as e:
        logger.error(f"Error during processing: {str(e)}")
        return {"error": f"Error during processing: {str(e)}"}
    finally:
        # Clean up the original downloaded file (not the trimmed one)
        if downloaded_path and os.path.exists(downloaded_path):
            try:
                os.remove(downloaded_path)
                logger.info(f"Deleted temp file: {downloaded_path}")
            except Exception as cleanup_err:
                logger.warning(f"Failed to delete temp file: {downloaded_path} ({cleanup_err})")

import time
import threading

@app.get("/download/{filename}")
async def download_clip(filename: str, background_tasks: BackgroundTasks):
    file_path = os.path.join(TEMP_DIR, filename)
    if os.path.exists(file_path):
        # Schedule file for deletion 25 seconds after response is sent
        def delayed_cleanup():
            time.sleep(25)
            try:
                os.remove(file_path)
                logger.info(f"Deleted served file after 25s: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to delete served file: {file_path} ({e})")
        background_tasks.add_task(threading.Thread, target=delayed_cleanup, daemon=True)
        return FileResponse(file_path)
    else:
        logger.warning(f"File not found for download: {file_path}")
        raise HTTPException(status_code=404, detail="File not found")

# Health check endpoint
@app.get("/health")
async def health():
    return JSONResponse(content={"status": "ok"})
