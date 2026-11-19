"""Detecção dos momentos: transforma atividade (chat ou áudio) numa lista de janelas de corte."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, asdict

# Mensagens que costumam marcar "momento": risada, choque, hype.
HYPE_PATTERNS = re.compile(
    r"(k{3,}|ha(ha)+|rs(rs)+|lol|lmao|kekw|lul|omegalul|pog|poggers|\bw+\b|\?{2,}|!{2,}|"
    r"clip|clipa|clipe|insano|absurdo|caraca|nossa|meu deus|que isso|wtf|omg|bruh)",
    re.IGNORECASE,
)

# (segundos antes do pico, segundos depois do pico). O chat reage atrasado, então a maior parte vem antes.
DURATION_PRESETS = {
    "auto": (38, 12),
    "curto": (18, 7),
    "medio": (38, 12),
    "longo": (75, 20),
}


@dataclass
class Moment:
    peak: float      # segundo do pico de atividade
    start: float     # início do corte
    end: float       # fim do corte
    score: int       # 0–100, "nota de viralidade"
    intensity: float # atividade no pico em relação à mediana (ex.: 6.2 = 6x o normal)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["start"] = round(self.start, 2)
        d["end"] = round(self.end, 2)
        d["peak"] = round(self.peak, 2)
        d["intensity"] = round(self.intensity, 2)
        return d


def message_weight(text: str) -> float:
    return 1.6 if text and HYPE_PATTERNS.search(text) else 1.0


def series_from_chat(messages: list[tuple[float, str]], duration: float, bucket: float = 5.0) -> list[float]:
    """Soma ponderada de mensagens por balde de `bucket` segundos."""
    n = max(1, int(math.ceil(duration / bucket)))
    s = [0.0] * n
    for t, text in messages:
        if t is None or t < 0 or t >= duration:
            continue
        s[int(t // bucket)] += message_weight(text)
    return s


def _smooth(values: list[float], radius: int) -> list[float]:
    if radius <= 0:
        return list(values)
    out = []
    n = len(values)
    for i in range(n):
        lo, hi = max(0, i - radius), min(n, i + radius + 1)
        out.append(sum(values[lo:hi]) / (hi - lo))
    return out


def _median(values: list[float]) -> float:
    v = sorted(values)
    if not v:
        return 0.0
    m = len(v) // 2
    return v[m] if len(v) % 2 else (v[m - 1] + v[m]) / 2


def find_moments(
    series: list[float],
    duration: float,
    bucket: float = 5.0,
    max_clips: int = 6,
    preset: str = "auto",
    min_gap: float = 90.0,
    smooth_radius: int = 2,
) -> list[Moment]:
    """Acha os maiores picos (com distância mínima entre eles) e devolve as janelas de corte."""
    if not series:
        return []
    pre, post = DURATION_PRESETS.get(preset, DURATION_PRESETS["auto"])
    sm = _smooth(series, smooth_radius)
    med = _median(sm)
    mad = _median([abs(x - med) for x in sm]) or 1e-6
    baseline = max(med, 1e-6)

    # candidatos = máximos locais
    candidates = []
    for i, v in enumerate(sm):
        left = sm[i - 1] if i > 0 else -1
        right = sm[i + 1] if i + 1 < len(sm) else -1
        if v >= left and v >= right and v > med:
            z = (v - med) / (1.4826 * mad)
            candidates.append((v, z, i))
    candidates.sort(reverse=True)

    chosen: list[Moment] = []
    for v, z, i in candidates:
        if len(chosen) >= max_clips:
            break
        peak_t = (i + 0.5) * bucket
        if any(abs(peak_t - m.peak) < min_gap for m in chosen):
            continue
        if z < 1.5 and chosen:  # depois do primeiro, ignora picos fracos
            break
        start = max(0.0, peak_t - pre)
        end = min(duration, peak_t + post)
        if end - start < 8:
            continue
        score = int(round(50 + 50 * math.tanh(z / 6)))
        chosen.append(Moment(peak=peak_t, start=start, end=end, score=max(1, min(99, score)), intensity=v / baseline))
    return chosen
