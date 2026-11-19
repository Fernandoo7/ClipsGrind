import random
from clipsgrind import peaks


def test_finds_spikes_and_respects_gap():
    random.seed(1)
    dur = 3600
    msgs = [(random.uniform(0, dur), "oi") for _ in range(3000)]
    for center in (600, 1500, 1520, 2900):
        msgs += [(random.gauss(center, 6), "KKKKKKK") for _ in range(400)]
    s = peaks.series_from_chat(msgs, dur)
    ms = peaks.find_moments(s, dur, max_clips=6)
    found = sorted(round(m.peak, -1) for m in ms)
    assert any(abs(f - 600) < 20 for f in found)
    assert any(abs(f - 2900) < 20 for f in found)
    # 1500 e 1520 são o mesmo momento (gap mínimo de 90s)
    assert sum(1 for f in found if 1450 < f < 1570) == 1
    for m in ms:
        assert 0 <= m.start < m.peak < m.end <= dur
        assert 1 <= m.score <= 99


def test_hype_weight():
    assert peaks.message_weight("KKKKKK") > 1
    assert peaks.message_weight("show de bola") == 1  # 'w' dentro de palavra não conta
    assert peaks.message_weight("W") > 1


def test_quiet_stream_returns_few():
    dur = 1200
    s = [1.0] * int(dur / 5)
    assert len(peaks.find_moments(s, dur)) <= 1
