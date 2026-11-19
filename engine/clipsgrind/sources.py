"""Tudo que fala com a internet: metadados, chat, áudio e download só dos trechos escolhidos."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np


def log(msg: str) -> None:
    print(f"[clipsgrind] {msg}", flush=True)


def _ytdlp_base() -> list[str]:
    cmd = [sys.executable, "-m", "yt_dlp", "--no-warnings", "--no-playlist"]
    cookies = os.environ.get("YTDLP_COOKIES_FILE")
    if cookies and Path(cookies).exists():
        cmd += ["--cookies", cookies]
    return cmd


def fetch_info(url: str) -> dict:
    out = subprocess.run(_ytdlp_base() + ["-J", url], check=True, capture_output=True, text=True)
    info = json.loads(out.stdout)
    return {
        "title": info.get("title") or "Live",
        "duration": float(info.get("duration") or 0),
        "uploader": info.get("uploader") or info.get("channel") or "",
        "extractor": (info.get("extractor_key") or "").lower(),
        "webpage_url": info.get("webpage_url") or url,
    }


def fetch_chat(url: str, max_messages: int = 400_000) -> list[tuple[float, str]]:
    """Mensagens do chat (replay) com o segundo em que apareceram. Lista vazia se a plataforma não tiver."""
    try:
        from chat_downloader import ChatDownloader
    except Exception as e:  # pragma: no cover
        log(f"chat-downloader indisponível: {e}")
        return []
    msgs: list[tuple[float, str]] = []
    try:
        chat = ChatDownloader().get_chat(url, message_groups=["messages"])
        for m in chat:
            t = m.get("time_in_seconds")
            if t is None:
                continue
            msgs.append((float(t), m.get("message") or ""))
            if len(msgs) >= max_messages:
                break
            if len(msgs) % 20000 == 0:
                log(f"chat: {len(msgs)} mensagens lidas…")
    except Exception as e:
        log(f"não consegui ler o chat ({type(e).__name__}: {e}) — vou usar o volume do áudio")
        return []
    log(f"chat: {len(msgs)} mensagens")
    return msgs


def audio_loudness_series(url_or_file: str, workdir: Path, bucket: float = 5.0) -> list[float]:
    """Plano B sem chat: volume (RMS) do áudio por balde. Gritos/risadas costumam marcar os momentos."""
    if Path(url_or_file).exists():
        src = url_or_file
    else:
        target = workdir / "audio.%(ext)s"
        subprocess.run(
            _ytdlp_base() + ["-f", "worstaudio/bestaudio/worst", "-o", str(target), url_or_file],
            check=True,
        )
        src = str(next(workdir.glob("audio.*")))
    sr = 8000
    proc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-i", src, "-vn", "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"],
        stdout=subprocess.PIPE,
    )
    per = int(sr * bucket)
    series: list[float] = []
    buf = b""
    assert proc.stdout is not None
    while True:
        chunk = proc.stdout.read(per * 2 * 16)
        if not chunk:
            break
        buf += chunk
        while len(buf) >= per * 2:
            a = np.frombuffer(buf[: per * 2], dtype=np.int16).astype(np.float32)
            buf = buf[per * 2 :]
            series.append(float(np.sqrt(np.mean(a * a)) + 1e-6))
    proc.wait()
    # destaca subidas bruscas em vez de música alta constante
    arr = np.array(series)
    if len(arr) > 24:
        base = np.convolve(arr, np.ones(24) / 24, mode="same")
        arr = np.maximum(arr - base, 0) + arr * 0.15
    return arr.tolist()


def download_section(url_or_file: str, start: float, end: float, dest: Path) -> Path:
    """Baixa só o trecho [start, end] (ou recorta, se for arquivo local)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if Path(url_or_file).exists():
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.2f}", "-to", f"{end:.2f}", "-i", url_or_file,
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac", str(dest)],
            check=True,
        )
        return dest
    tmpl = str(dest.with_suffix("")) + ".%(ext)s"
    subprocess.run(
        _ytdlp_base() + [
            "-f", "bv*[height<=1080]+ba/b[height<=1080]/b",
            "--download-sections", f"*{start:.2f}-{end:.2f}",
            "--force-keyframes-at-cuts",
            "--merge-output-format", "mp4",
            "-o", tmpl, url_or_file,
        ],
        check=True,
    )
    got = next(dest.parent.glob(dest.stem + ".*"))
    if got != dest:
        got.rename(dest)
    return dest
