from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, HttpUrl, field_validator, model_validator
import yt_dlp
import ffmpeg
import os
import logging
import time
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import threading

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # You can lock to your frontend domain later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Temp dir
TEMP_DIR = "/tmp/yt_clips/"
os.makedirs(TEMP_DIR, exist_ok=True)

# Cookies
COOKIES_FILE = os.path.join(os.path.dirname(__file__), "cookies.txt")
USE_COOKIES = os.path.exists(COOKIES_FILE)

# Pydantic model
class ClipRequest(BaseModel):
    url: HttpUrl
    start: int
    end: int

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
    if "error" in result:
        logger.error(f"Clip creation failed: {result['error']}")
        raise HTTPException(status_code=400, detail=result["error"])
    logger.info(f"Clip created successfully: {result['downloadUrl']}")
    return result

def create_clip_task(url, start, end):
    downloaded_path = None
    trimmed_path = None
    try:
        start_time = time.time()

        ydl_opts = {
            'outtmpl': f'{TEMP_DIR}%(id)s.%(ext)s',
            'format': 'bestvideo[height<=1080]+bestaudio/best',
            'merge_output_format': 'mp4',
            'noplaylist': True,
        }

        if USE_COOKIES:
            ydl_opts['cookies'] = COOKIES_FILE

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info_dict = ydl.extract_info(str(url), download=True)
            except yt_dlp.utils.DownloadError as de:
                # Most likely blocked by YouTube login/CAPTCHA
                return {"error": "Video requires login or is blocked by YouTube (cannot use cookies on this server)"}

            downloaded_path = ydl.prepare_filename(info_dict)
            trimmed_filename = f"{info_dict['id']}_clip.mp4"
            trimmed_path = os.path.join(TEMP_DIR, trimmed_filename)

        # Trimming
        (
            ffmpeg.input(downloaded_path, ss=start, to=end)
            .output(
                trimmed_path,
                vcodec='libx264',
                acodec='aac',
                video_bitrate='3000k',
                audio_bitrate='192k',
                preset='medium',
                crf=18
            )
            .run(overwrite_output=True)
        )

        total_time = time.time() - start_time

        # Use dynamic URL instead of localhost
        download_url = f"/download/{trimmed_filename}"

        return {
            "downloadUrl": download_url,
            "waitSeconds": int(total_time),
            "warning": "Clip boundaries are accurate with re-encoding."
        }

    except Exception as e:
        logger.error(f"Error during processing: {str(e)}")
        return {"error": f"Error during processing: {str(e)}"}
    finally:
        if downloaded_path and os.path.exists(downloaded_path):
            try:
                os.remove(downloaded_path)
            except Exception:
                pass

@app.get("/download/{filename}")
async def download_clip(filename: str, background_tasks: BackgroundTasks):
    file_path = os.path.join(TEMP_DIR, filename)
    if os.path.exists(file_path):
        def delayed_cleanup():
            time.sleep(25)
            try:
                os.remove(file_path)
                logger.info(f"Deleted served file: {file_path}")
            except Exception:
                pass
        background_tasks.add_task(threading.Thread, target=delayed_cleanup, daemon=True)
        return FileResponse(file_path)
    else:
        raise HTTPException(status_code=404, detail="File not found")

@app.get("/health")
async def health():
    return JSONResponse(content={"status": "ok"})
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, HttpUrl, field_validator, model_validator
import yt_dlp
import ffmpeg
import os
import logging
import time
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import threading

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # You can lock to your frontend domain later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Temp dir
TEMP_DIR = "/tmp/yt_clips/"
os.makedirs(TEMP_DIR, exist_ok=True)

# Cookies
COOKIES_FILE = os.path.join(os.path.dirname(__file__), "cookies.txt")
USE_COOKIES = os.path.exists(COOKIES_FILE)

# Pydantic model
class ClipRequest(BaseModel):
    url: HttpUrl
    start: int
    end: int

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
    if "error" in result:
        logger.error(f"Clip creation failed: {result['error']}")
        raise HTTPException(status_code=400, detail=result["error"])
    logger.info(f"Clip created successfully: {result['downloadUrl']}")
    return result

def create_clip_task(url, start, end):
    downloaded_path = None
    trimmed_path = None
    try:
        start_time = time.time()

        ydl_opts = {
            'outtmpl': f'{TEMP_DIR}%(id)s.%(ext)s',
            'format': 'bestvideo[height<=1080]+bestaudio/best',
            'merge_output_format': 'mp4',
            'noplaylist': True,
        }

        if USE_COOKIES:
            ydl_opts['cookies'] = COOKIES_FILE

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info_dict = ydl.extract_info(str(url), download=True)
            except yt_dlp.utils.DownloadError as de:
                # Most likely blocked by YouTube login/CAPTCHA
                return {"error": "Video requires login or is blocked by YouTube (cannot use cookies on this server)"}

            downloaded_path = ydl.prepare_filename(info_dict)
            trimmed_filename = f"{info_dict['id']}_clip.mp4"
            trimmed_path = os.path.join(TEMP_DIR, trimmed_filename)

        # Trimming
        (
            ffmpeg.input(downloaded_path, ss=start, to=end)
            .output(
                trimmed_path,
                vcodec='libx264',
                acodec='aac',
                video_bitrate='3000k',
                audio_bitrate='192k',
                preset='medium',
                crf=18
            )
            .run(overwrite_output=True)
        )

        total_time = time.time() - start_time

        # Use dynamic URL instead of localhost
        download_url = f"/download/{trimmed_filename}"

        return {
            "downloadUrl": download_url,
            "waitSeconds": int(total_time),
            "warning": "Clip boundaries are accurate with re-encoding."
        }

    except Exception as e:
        logger.error(f"Error during processing: {str(e)}")
        return {"error": f"Error during processing: {str(e)}"}
    finally:
        if downloaded_path and os.path.exists(downloaded_path):
            try:
                os.remove(downloaded_path)
            except Exception:
                pass

@app.get("/download/{filename}")
async def download_clip(filename: str, background_tasks: BackgroundTasks):
    file_path = os.path.join(TEMP_DIR, filename)
    if os.path.exists(file_path):
        def delayed_cleanup():
            time.sleep(25)
            try:
                os.remove(file_path)
                logger.info(f"Deleted served file: {file_path}")
            except Exception:
                pass
        background_tasks.add_task(threading.Thread, target=delayed_cleanup, daemon=True)
        return FileResponse(file_path)
    else:
        raise HTTPException(status_code=404, detail="File not found")

@app.get("/health")
async def health():
    return JSONResponse(content={"status": "ok"})
