"""Título, gancho, descrição e hashtags de cada clipe.

Usa o GitHub Models (grátis dentro do GitHub Actions com o GITHUB_TOKEN). Se não estiver disponível,
cai num gerador simples a partir da transcrição — o clipe nunca fica sem texto.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

ENDPOINT = "https://models.github.ai/inference/chat/completions"
MODEL = os.environ.get("CLIPSGRIND_LLM_MODEL", "openai/gpt-4o-mini")

PROMPT = """Você escreve textos para YouTube Shorts a partir de cortes de lives.
Live: "{live_title}" — canal: {channel}
Transcrição do trecho (pode ter erros):
\"\"\"{transcript}\"\"\"

Responda SÓ com JSON, em {lang_name}, neste formato:
{{"title": "...", "hook": "...", "description": "...", "hashtags": ["#shorts", "..."]}}
Regras: title com até 60 caracteres, chamativo mas fiel ao que aconteceu, sem clickbait mentiroso;
hook = frase curta (até 5 palavras) que aparece no topo do vídeo; description com 1–2 frases e o nome do canal;
hashtags: 4 a 6, sempre incluindo #shorts."""

LANG_NAMES = {"pt": "português do Brasil", "en": "inglês", "es": "espanhol"}


def _llm(prompt: str) -> dict | None:
    token = os.environ.get("GITHUB_TOKEN")
    if not token or os.environ.get("CLIPSGRIND_NO_LLM"):
        return None
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
    }).encode()
    req = urllib.request.Request(ENDPOINT, data=body, headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json",
    })
    raw = b""
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
        data = json.loads(raw)
        content = data["choices"][0]["message"]["content"] or ""
        m = re.search(r"\{.*\}", content, re.S)  # aceita resposta com ```json … ``` em volta
        return json.loads(m.group(0) if m else content)
    except urllib.error.HTTPError as e:
        body = e.read()[:300].decode("utf-8", "replace")
        print(f"[clipsgrind] LLM recusou ({e.code}): {body}; usando texto automático simples")
    except Exception as e:
        print(f"[clipsgrind] LLM indisponível ({type(e).__name__}: {e}; resposta: {raw[:200]!r}); usando texto automático simples")
    return None


def _fallback(transcript: str, live_title: str, channel: str, n: int) -> dict:
    words = re.findall(r"\w[\w'-]*", transcript)
    snippet = " ".join(words[:9]).strip()
    title = (snippet[:1].upper() + snippet[1:]) if snippet else f"Momento {n} da live"
    if len(title) > 60:
        title = title[:57].rsplit(" ", 1)[0] + "…"
    tag = re.sub(r"[^\w]", "", channel.lower()) if channel else ""
    hashtags = ["#shorts", "#live", "#cortes"] + ([f"#{tag}"] if tag else [])
    return {
        "title": title,
        "hook": " ".join(words[:4]).upper() if words else "OLHA ISSO",
        "description": f"Corte da live \"{live_title}\"" + (f" de {channel}." if channel else "."),
        "hashtags": hashtags,
    }


def write_meta(transcript: str, live_title: str, channel: str, n: int, lang: str = "pt") -> dict:
    prompt = PROMPT.format(
        live_title=live_title, channel=channel or "desconhecido",
        transcript=(transcript or "(sem fala detectada)")[:3000], lang_name=LANG_NAMES.get(lang, "português do Brasil"),
    )
    out = _llm(prompt) or {}
    fb = _fallback(transcript, live_title, channel, n)
    meta = {k: out.get(k) or fb[k] for k in ("title", "hook", "description", "hashtags")}
    tags = [t if str(t).startswith("#") else f"#{t}" for t in meta["hashtags"]][:6]
    if "#shorts" not in [t.lower() for t in tags]:
        tags = ["#shorts"] + tags[:5]
    meta["hashtags"] = tags
    meta["title"] = str(meta["title"])[:100]
    return meta
