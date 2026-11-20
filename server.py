import hashlib
import math
import os
import re
import shutil
import subprocess
import tempfile
import uuid
import wave
from pathlib import Path

import yt_dlp
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).parent
WORK = Path(os.getenv("CLIPFORGE_WORKDIR", Path(tempfile.gettempdir()) / "clipforge_v32"))
WORK.mkdir(parents=True, exist_ok=True)
MAX_VIDEO_BYTES = int(os.getenv("MAX_VIDEO_BYTES", str(2 * 1024 * 1024 * 1024)))
MAX_DURATION = int(os.getenv("MAX_VIDEO_DURATION", "14400"))  # 4 hours

app = FastAPI(title="ClipForge AI V32", version="32.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

class AnalyzeRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2048)
    target: int = Field(default=20, ge=1, le=100)
    clip_length: int = Field(default=60, ge=5, le=900)

class ExportRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2048)
    start: float = Field(ge=0)
    end: float = Field(gt=0)


def valid_youtube(url: str) -> bool:
    try:
        from urllib.parse import urlparse
        u = urlparse(url.strip())
        host = (u.hostname or "").lower().rstrip(".")
        return u.scheme in {"http", "https"} and host in {
            "youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtu.be"
        }
    except Exception:
        return False


def run(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=7200)
    if p.returncode:
        detail = (p.stderr or "Perintah media gagal")[-2500:]
        raise RuntimeError(detail)


def folder_for(url: str) -> Path:
    key = hashlib.sha256(url.strip().encode("utf-8")).hexdigest()[:24]
    folder = WORK / key
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def get_video(url: str):
    if not valid_youtube(url):
        raise ValueError("Masukkan URL YouTube publik yang valid.")
    folder = folder_for(url)
    existing = [p for p in folder.glob("source.*") if p.is_file() and p.stat().st_size > 0]
    if existing:
        return existing[0], folder

    opts = {
        "format": "best[ext=mp4]/best",
        "outtmpl": str(folder / "source.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
        "socket_timeout": 30,
        "retries": 2,
        "fragment_retries": 2,
        "max_filesize": MAX_VIDEO_BYTES,
        "match_filter": yt_dlp.utils.match_filter_func(f"duration <= {MAX_DURATION}"),
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
    except Exception as exc:
        raise RuntimeError(
            "Server tidak dapat mengambil video ini. Pastikan video publik, tidak live/privat/berbayar, "
            "dan server dapat mengakses YouTube. Detail: " + str(exc)[-900:]
        ) from exc

    files = [p for p in folder.glob("source.*") if p.is_file() and p.stat().st_size > 0]
    if not files:
        raise RuntimeError("Video tidak ditemukan setelah proses pengambilan.")
    if files[0].stat().st_size > MAX_VIDEO_BYTES:
        files[0].unlink(missing_ok=True)
        raise RuntimeError("Ukuran video melebihi batas server.")
    return files[0], folder


@app.get("/", response_class=HTMLResponse)
def home():
    page = ROOT / "ClipForge_AI_V32.html"
    if not page.exists():
        raise HTTPException(500, "File antarmuka tidak ditemukan di server.")
    return HTMLResponse(page.read_text(encoding="utf-8"))

@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "ClipForge AI V32",
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "yt_dlp": True,
    }

@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    if not valid_youtube(req.url):
        raise HTTPException(400, "Masukkan URL YouTube yang valid.")
    try:
        media, folder = get_video(req.url)
        wav_path = folder / "audio_mono.wav"
        run(["ffmpeg", "-y", "-i", str(media), "-vn", "-ac", "1", "-ar", "8000", "-f", "wav", str(wav_path)])
        with wave.open(str(wav_path), "rb") as wav:
            rate, frames = wav.getframerate(), wav.getnframes()
            duration = frames / rate
            if duration <= 0 or duration > MAX_DURATION:
                raise RuntimeError("Durasi video tidak didukung oleh batas server.")
            energies = []
            chunk = rate * 2
            index = 0
            while index < frames:
                raw = wav.readframes(min(chunk, frames - index))
                if not raw:
                    break
                # 16-bit mono PCM, downsampled in-memory for low CPU use.
                import array
                samples = array.array("h")
                samples.frombytes(raw)
                if os.sys.byteorder != "little":
                    samples.byteswap()
                stride = max(1, len(samples) // 2000)
                subset = samples[::stride]
                rms = math.sqrt(sum(float(x) * x for x in subset) / max(1, len(subset))) / 32768
                energies.append({"t": index / rate, "rms": rms})
                index += len(samples)

        vals = sorted(item["rms"] for item in energies)
        threshold = max(vals[int((len(vals) - 1) * .75)] if vals else 0, .006)
        clip_len = min(req.clip_length, max(5, int(duration)))
        peaks = sorted((x for x in energies if x["rms"] >= threshold), key=lambda x: x["rms"], reverse=True)
        denom = vals[int((len(vals) - 1) * .9)] if vals else .01
        found = []
        for peak in peaks:
            start = max(0, min(max(0, duration - clip_len), peak["t"] - clip_len / 2))
            end = min(duration, start + clip_len)
            if any(abs(item["start"] - start) < clip_len * .65 for item in found):
                continue
            found.append({
                "start": round(start, 2),
                "end": round(end, 2),
                "score": min(99, round(peak["rms"] / max(denom, .01) * 70)),
            })
            if len(found) >= req.target:
                break
        found.sort(key=lambda x: x["score"], reverse=True)
        return {"duration": round(duration, 2), "candidates": found}
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc

@app.post("/api/export")
def export(req: ExportRequest):
    if not valid_youtube(req.url):
        raise HTTPException(400, "URL YouTube tidak valid.")
    if req.end <= req.start or req.end - req.start > 900:
        raise HTTPException(400, "Rentang klip tidak valid (maksimal 15 menit).")
    try:
        media, folder = get_video(req.url)
        out = folder / f"clip_{uuid.uuid4().hex[:10]}.mp4"
        run([
            "ffmpeg", "-y", "-ss", str(req.start), "-i", str(media),
            "-t", str(req.end - req.start), "-map", "0:v:0", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-c:a", "aac", "-movflags", "+faststart", str(out)
        ])
        return FileResponse(out, media_type="video/mp4", filename="clipforge_clip.mp4")
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc
