"""Procedural chiptune + SFX generator for little games. Stdlib + numpy only.

No downloads, no models: square/triangle/noise synthesis, seeded melodies,
loop-safe bars. Output: 44.1kHz 16-bit wav, portable to any game engine.

  python scripts/music_gen.py --tune adventure --seed 7
  python scripts/music_gen.py --tune boss --bpm 140 --bars 8
  python scripts/music_gen.py --sfx jump coin hit powerup
  python scripts/music_gen.py --pack  # 4 tunes + 8 sfx into data/music/
"""
import argparse
import wave
from pathlib import Path

import numpy as np

SR = 44100
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/music'

A = 440.0
SEMI = 2 ** (1 / 12)
NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


def note(name, octave=4):
    idx = NAMES.index(name)
    midi = (octave + 1) * 12 + idx
    return A * SEMI ** (midi - 69)


def square(ph):
    return np.sign(np.sin(ph)).astype(float)


def tri(ph):
    return (2 / np.pi * np.arcsin(np.sin(ph))).astype(float)


def env(n, a=0.01, r=0.15):
    e = np.ones(n)
    na, nr = max(1, int(n * a)), max(1, int(n * r))
    e[:na] = np.linspace(0, 1, na)
    e[-nr:] *= np.linspace(1, 0, nr)
    return e


def tone(freq, dur, kind='square', vol=0.4, slide=0.0):
    n = int(SR * dur)
    t = np.arange(n) / SR
    f = freq * (1 + slide * t / max(dur, 1e-6))
    ph = 2 * np.pi * np.cumsum(f) / SR
    osc = square(ph) if kind == 'square' else tri(ph)
    return vol * osc * env(n)


def noise_hit(dur, vol=0.5, low=1000):
    n = int(SR * dur)
    x = np.random.default_rng(1234).standard_normal(n)
    k = np.ones(max(1, int(SR / low)))
    x = np.convolve(x, k / k.sum(), mode='same')
    return vol * x * env(n, a=0.005, r=0.4)


def kick(dur=0.18, vol=0.7):
    return tone(150, dur, 'tri', vol, slide=-0.75)


def mix(*parts):
    n = max(len(p) for p in parts)
    out = np.zeros(n)
    for p in parts:
        out[:len(p)] += p
    m = np.abs(out).max()
    if m > 0.95:
        out *= 0.95 / m
    return (out * 32767).astype(np.int16)


def save(path, pcm):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return path


PROGS = {
    'adventure': ([0, -4, -7, -2], 'minor', 128),
    'boss': ([0, 0, -1, -2], 'minor', 140),
    'calm': ([0, 5, -3, 4], 'major', 90),
    'title': ([0, 4, 5, 4], 'major', 112),
}

PENTA_MIN = [0, 3, 5, 7, 10, 12, 15]
PENTA_MAJ = [0, 2, 4, 7, 9, 12, 14]


def make_tune(style, seed=1, bpm=None, bars=4, root='A'):
    deg, mode, default_bpm = PROGS[style]
    bpm = bpm or default_bpm
    rng = np.random.default_rng(seed)
    beat = 60 / bpm
    bar = beat * 4
    base = note(root, 3)
    scale = PENTA_MIN if mode == 'minor' else PENTA_MAJ
    parts = []
    for b in range(bars):
        t0 = b * bar
        chord_root = base * SEMI ** deg[b % len(deg)]
        for i, iv in enumerate(([0, 3, 7] if mode == 'minor' else [0, 4, 7])):
            f = chord_root * SEMI ** iv
            s = tone(f, beat * 0.9, 'tri', 0.16)
            parts.append((t0 + i * beat, s))
        for q in range(4):
            f = chord_root / 2
            s = tone(f, beat * 0.45, 'square', 0.30)
            parts.append((t0 + q * beat, s))
        steps = rng.integers(0, len(scale), size=8)
        for e, st in enumerate(steps):
            if rng.random() < 0.2:
                continue
            f = chord_root * 2 * SEMI ** scale[st]
            s = tone(f, beat * 0.45, 'square', 0.22)
            parts.append((t0 + e * beat / 2, s))
        if style in ('boss', 'adventure'):
            for q in range(4):
                parts.append((t0 + q * beat, kick(0.12, 0.5)))
                parts.append((t0 + q * beat + beat / 2, noise_hit(0.05, 0.18)))
    total = int(bars * bar * SR)
    out = np.zeros(total)
    for t0, s in parts:
        i = int(t0 * SR)
        j = min(total, i + len(s))
        out[i:j] += s[:j - i]
    fade = int(0.02 * SR)
    out[-fade:] *= np.linspace(1, 0, fade)
    m = np.abs(out).max()
    if m > 0.95:
        out *= 0.95 / m
    return (out * 32767).astype(np.int16)


def make_sfx(kind):
    if kind == 'jump':
        return mix(tone(300, 0.22, 'square', 0.4, slide=1.2))
    if kind == 'coin':
        return mix(tone(990, 0.08, 'square', 0.35), tone(1320, 0.25, 'square', 0.35))
    if kind == 'hit':
        return mix(noise_hit(0.2, 0.5), tone(110, 0.2, 'tri', 0.5, slide=-0.5))
    if kind == 'powerup':
        seq = np.concatenate([tone(523 * SEMI ** i, 0.09, 'square', 0.35) for i in (0, 4, 7, 12)])
        return mix(seq)
    if kind == 'click':
        return mix(tone(800, 0.05, 'square', 0.3))
    if kind == 'boom':
        return mix(noise_hit(0.7, 0.7, low=400), tone(60, 0.7, 'tri', 0.6, slide=-0.6))
    if kind == 'win':
        seq = np.concatenate([tone(f, 0.14, 'tri', 0.4) for f in (523, 659, 784, 1047)])
        return mix(seq)
    if kind == 'lose':
        seq = np.concatenate([tone(f, 0.22, 'tri', 0.4) for f in (392, 370, 349, 311)])
        return mix(seq)
    raise SystemExit(f'unknown sfx: {kind}')


def main():
    ap = argparse.ArgumentParser(description='Procedural game music + SFX')
    ap.add_argument('--tune', choices=sorted(PROGS))
    ap.add_argument('--sfx', nargs='*')
    ap.add_argument('--pack', action='store_true')
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--bpm', type=int, default=None)
    ap.add_argument('--bars', type=int, default=4)
    ap.add_argument('--root', default='A')
    ap.add_argument('--out', default=None)
    args = ap.parse_args()

    made = []
    if args.pack or (not args.tune and not args.sfx):
        for style in PROGS:
            p = save(OUT / f'{style}.wav', make_tune(style, seed=args.seed, bars=8))
            made.append(p)
        for s in ('jump', 'coin', 'hit', 'powerup', 'click', 'boom', 'win', 'lose'):
            made.append(save(OUT / 'sfx' / f'{s}.wav', make_sfx(s)))
    else:
        if args.tune:
            pcm = make_tune(args.tune, seed=args.seed, bpm=args.bpm, bars=args.bars, root=args.root)
            made.append(save(Path(args.out) if args.out else OUT / f'{args.tune}.wav', pcm))
        for s in args.sfx or []:
            made.append(save(OUT / 'sfx' / f'{s}.wav', make_sfx(s)))
    for p in made:
        print(p)


if __name__ == '__main__':
    main()
