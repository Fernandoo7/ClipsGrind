"""Transcrição (faster-whisper), legenda estilo Shorts (.ass) e render vertical 1080x1920."""
from __future__ import annotations

import subprocess
from pathlib import Path

W, H = 1080, 1920
FONT = "DejaVu Sans"


def transcribe(clip: Path, model_name: str = "small", language: str | None = "pt") -> list[dict]:
    """Palavras com tempo: [{'w': 'texto', 's': 0.31, 'e': 0.58}, …]. Vazio se não der."""
    try:
        from faster_whisper import WhisperModel
    except Exception as e:  # pragma: no cover
        print(f"[clipsgrind] sem faster-whisper ({e}); clipe sai sem legenda")
        return []
    if not hasattr(transcribe, "_model"):
        try:
            transcribe._model = WhisperModel(model_name, device="cpu", compute_type="int8")  # type: ignore[attr-defined]
        except Exception as e:
            print(f"[clipsgrind] não consegui carregar o modelo de transcrição ({e}); clipes saem sem legenda")
            transcribe._model = None  # type: ignore[attr-defined]
    if transcribe._model is None:  # type: ignore[attr-defined]
        return []
    model = transcribe._model  # type: ignore[attr-defined]
    try:
        audio = _decode_audio_16k(clip)
        segments, _ = model.transcribe(
            audio, language=language or None, word_timestamps=True, vad_filter=True, beam_size=1
        )
        words = []
        for seg in segments:
            for w in seg.words or []:
                text = w.word.strip()
                if text:
                    words.append({"w": text, "s": float(w.start), "e": float(w.end)})
        return words
    except Exception as e:
        print(f"[clipsgrind] transcrição falhou ({type(e).__name__}: {e}); clipe sai sem legenda")
        return []


def _decode_audio_16k(clip: Path):
    """Áudio mono 16 kHz float32 via ffmpeg (não depende do PyAV)."""
    import numpy as np
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(clip), "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
        capture_output=True, check=True,
    ).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def _ts(t: float) -> str:
    t = max(0.0, t)
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _esc(text: str) -> str:
    return text.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def group_words(words: list[dict], max_words: int = 3, max_len: float = 1.4) -> list[dict]:
    """Junta palavras em blocos curtos (estilo Shorts: 1–3 palavras por vez)."""
    groups, cur = [], []
    for w in words:
        if cur and (len(cur) >= max_words or w["e"] - cur[0]["s"] > max_len or cur[-1]["w"][-1:] in ".!?"):
            groups.append(cur)
            cur = []
        cur.append(w)
    if cur:
        groups.append(cur)
    out = []
    for i, g in enumerate(groups):
        end = g[-1]["e"]
        if i + 1 < len(groups):
            end = min(max(end, g[-1]["e"] + 0.15), groups[i + 1][0]["s"])
        out.append({"text": " ".join(x["w"] for x in g), "s": g[0]["s"], "e": end})
    return out


def write_ass(path: Path, captions: list[dict], hook: str, duration: float, caption_color: str = "&H004DFFCF") -> None:
    """caption_color em formato ASS (&HAABBGGRR). Padrão = verde-limão do ClipsGrind (#CFFF4D)."""
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {W}",
        f"PlayResY: {H}",
        "WrapStyle: 0",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Cap,{FONT},86,{caption_color},&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,6,2,2,80,80,520,1",
        f"Style: Hook,{FONT},62,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,5,0,8,90,90,300,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    if hook:
        lines.append(f"Dialogue: 1,{_ts(0)},{_ts(duration)},Hook,,0,0,0,,{_esc(hook.upper())}")
    for c in captions:
        if c["e"] <= c["s"]:
            continue
        lines.append(f"Dialogue: 0,{_ts(c['s'])},{_ts(c['e'])},Cap,,0,0,0,,{{\\fscx92\\fscy92\\t(0,90,\\fscx100\\fscy100)}}{_esc(c['text'].upper())}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def render_vertical(src: Path, ass: Path | None, dest: Path) -> Path:
    """Vídeo original centralizado sobre um fundo desfocado dele mesmo, em 9:16, com legenda queimada."""
    fc = (
        f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=24:2,eq=brightness=-0.12[bg];"
        f"[0:v]scale={W}:-2[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1"
    )
    if ass is not None and ass.exists():
        fc += f",subtitles='{ass.as_posix()}'"
    fc += "[v]"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(src), "-filter_complex", fc, "-map", "[v]", "-map", "0:a?",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-r", "30",
         "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(dest)],
        check=True,
    )
    return dest


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nk=1:nw=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip() or 0)
