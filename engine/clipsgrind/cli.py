"""ClipsGrind — do link da live aos clipes prontos.

Uso:
  python -m clipsgrind.cli URL [--max-clips 6] [--duration auto|curto|medio|longo] [--lang pt] [--out out]
Teste offline:
  python -m clipsgrind.cli video.mp4 --chat-json chat.json --no-transcribe
"""
from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

from . import meta as meta_mod
from . import peaks, render, sources
from .sources import log


def fmt_t(t: float) -> str:
    t = int(t)
    h, m, s = t // 3600, (t % 3600) // 60, t % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def run(args: argparse.Namespace) -> dict:
    t0 = time.time()
    out = Path(args.out)
    work = out / "_work"
    clips_dir = out / "clips"
    for d in (work, clips_dir):
        d.mkdir(parents=True, exist_ok=True)

    src = args.source
    local = Path(src).exists()
    if local:
        info = {"title": args.title or Path(src).stem, "duration": render.probe_duration(Path(src)),
                "uploader": args.channel or "", "extractor": "arquivo", "webpage_url": src}
    else:
        log("lendo informações do vídeo…")
        info = sources.fetch_info(src)
    duration = info["duration"]
    if duration <= 0:
        raise SystemExit("Não consegui descobrir a duração do vídeo (live ainda ao vivo?). Tente com o VOD/replay.")
    log(f"\"{info['title']}\" — {fmt_t(duration)} — {info['uploader'] or 'canal desconhecido'}")

    # 1) sinal de atividade: chat (melhor) ou volume do áudio (plano B)
    bucket = 5.0
    signal = "chat"
    if args.chat_json:
        raw = json.loads(Path(args.chat_json).read_text(encoding="utf-8"))
        msgs = [(float(m["t"]), m.get("text", "")) for m in raw]
    elif local or args.no_chat:
        msgs = []
    else:
        log("baixando o chat…")
        msgs = sources.fetch_chat(src)
    if len(msgs) >= 50:
        series = peaks.series_from_chat(msgs, duration, bucket)
    else:
        signal = "áudio"
        log("sem chat suficiente — analisando o volume do áudio")
        series = sources.audio_loudness_series(src, work, bucket)

    moments = peaks.find_moments(series, duration, bucket=bucket, max_clips=args.max_clips, preset=args.duration)
    log(f"{len(moments)} momentos escolhidos pelo {signal}")

    results = []
    for n, m in enumerate(moments, 1):
        log(f"clipe {n}/{len(moments)}: {fmt_t(m.start)}–{fmt_t(m.end)} (nota {m.score})")
        raw_clip = work / f"raw_{n:02d}.mp4"
        try:
            sources.download_section(src, m.start, m.end, raw_clip)
        except Exception as e:
            log(f"  falhou ao baixar o trecho: {e}")
            continue
        clip_len = render.probe_duration(raw_clip)

        words = [] if args.no_transcribe else render.transcribe(raw_clip, args.whisper_model, args.lang)
        transcript = " ".join(w["w"] for w in words)
        md = meta_mod.write_meta(transcript, info["title"], info["uploader"], n, args.lang)

        ass = work / f"cap_{n:02d}.ass"
        render.write_ass(ass, render.group_words(words), md["hook"], clip_len)
        final = clips_dir / f"clipe_{n:02d}.mp4"
        render.render_vertical(raw_clip, ass, final)
        (clips_dir / f"clipe_{n:02d}.txt").write_text(
            f"{md['title']}\n\n{md['description']}\n\n{' '.join(md['hashtags'])}\n", encoding="utf-8")
        results.append({
            "file": final.name, **m.to_dict(), "duration": round(clip_len, 1),
            "start_label": fmt_t(m.start), "end_label": fmt_t(m.end),
            **md, "transcript": transcript,
        })

    report = {
        "source": info, "signal": signal, "preset": args.duration,
        "elapsed_sec": round(time.time() - t0, 1), "clips": results,
    }
    (out / "clips.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "resumo.md").write_text(summary_md(report), encoding="utf-8")
    if not args.keep_work:
        shutil.rmtree(work, ignore_errors=True)
    log(f"pronto: {len(results)} clipes em {report['elapsed_sec']}s → {clips_dir}")
    return report


def summary_md(r: dict) -> str:
    s = r["source"]
    lines = [
        f"## ClipsGrind — {len(r['clips'])} clipes prontos",
        f"**{s['title']}** · {s['uploader'] or '—'} · momentos achados pelo **{r['signal']}** · {r['elapsed_sec']}s",
        "",
        "| # | Nota | Trecho da live | Título | Hashtags |",
        "|---|---|---|---|---|",
    ]
    for i, c in enumerate(r["clips"], 1):
        title = c["title"].replace("|", "/")
        lines.append(f"| {i} | {c['score']} | {c['start_label']}–{c['end_label']} | {title} | {' '.join(c['hashtags'])} |")
    lines += ["", "Baixe o pacote **clipes** no fim desta página (em *Artifacts*)."]
    return "\n".join(lines) + "\n"


def main() -> None:
    p = argparse.ArgumentParser(prog="clipsgrind")
    p.add_argument("source", help="link da live/VOD ou caminho de um vídeo")
    p.add_argument("--max-clips", type=int, default=6)
    p.add_argument("--duration", default="auto", choices=list(peaks.DURATION_PRESETS))
    p.add_argument("--lang", default="pt")
    p.add_argument("--whisper-model", default="small")
    p.add_argument("--out", default="out")
    p.add_argument("--chat-json", help="teste: JSON [{t, text}] no lugar do chat real")
    p.add_argument("--no-chat", action="store_true", help="ignora o chat e usa só o áudio")
    p.add_argument("--no-transcribe", action="store_true")
    p.add_argument("--title")
    p.add_argument("--channel")
    p.add_argument("--keep-work", action="store_true")
    run(p.parse_args())


if __name__ == "__main__":
    main()
