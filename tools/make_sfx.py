"""Generates the game's sound effects and music as WAV files, using only the Python standard library.

Everything here is synthesized from scratch (sine/square waves and noise), so the sounds are ours
and need no CREDITS.md entry. Run: python tools/make_sfx.py <output folder>
"""
import math
import os
import random
import struct
import sys
import wave

RATE = 44100
random.seed(7)


def write(path, samples):
    peak = max(1e-9, max(abs(s) for s in samples))
    scale = 0.85 / peak if peak > 0.85 else 1.0
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, s * scale)) * 32767)) for s in samples))


def env(i, n, attack=0.005, release=None):
    t = i / RATE
    a = min(1.0, t / attack) if attack > 0 else 1.0
    r = 1.0 - i / n if release is None else max(0.0, 1.0 - max(0, i - (n - release * RATE)) / (release * RATE))
    return a * r


def tone(freq_fn, dur, wave_fn=math.sin, vol=1.0, attack=0.005, decay_pow=1.0):
    n = int(dur * RATE)
    out, phase = [], 0.0
    for i in range(n):
        phase += 2 * math.pi * freq_fn(i / n) / RATE
        out.append(wave_fn(phase) * vol * env(i, n, attack) ** decay_pow)
    return out


def square(p):
    return 1.0 if math.sin(p) >= 0 else -1.0


def tri(p):
    return 2 / math.pi * math.asin(math.sin(p))


def noise(dur, vol=1.0, lowpass=0.2, decay_pow=1.0):
    n = int(dur * RATE)
    out, y = [], 0.0
    for i in range(n):
        y += lowpass * (random.uniform(-1, 1) - y)
        out.append(y * vol * env(i, n, 0.002) ** decay_pow)
    return out


def mix(*tracks):
    n = max(len(t) for t in tracks)
    return [sum(t[i] for t in tracks if i < len(t)) for i in range(n)]


def seq(*parts):
    out = []
    for p in parts:
        out += p
    return out


def silence(dur):
    return [0.0] * int(dur * RATE)


def note(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def make_all(folder):
    os.makedirs(folder, exist_ok=True)
    # quick rising "boing" for each hop
    write(os.path.join(folder, "SFX_Hop.wav"),
          tone(lambda x: 380 + 520 * x, 0.11, lambda p: 0.7 * math.sin(p) + 0.3 * tri(p), 0.8, decay_pow=1.5))
    # soft thump on landing
    write(os.path.join(folder, "SFX_Land.wav"),
          mix(tone(lambda x: 140 - 60 * x, 0.08, math.sin, 0.9, decay_pow=2.0), noise(0.05, 0.25, 0.1, 2.0)))
    # car squash: crunchy noise + descending squeak
    write(os.path.join(folder, "SFX_Squash.wav"),
          mix(noise(0.35, 1.0, 0.35, 1.5), tone(lambda x: 900 - 700 * x, 0.3, square, 0.25, decay_pow=1.2)))
    # splash: filtered noise burst with a bubbly wobble
    splash = noise(0.6, 1.0, 0.08, 1.3)
    bubbles = tone(lambda x: 300 + 200 * math.sin(x * 40), 0.5, math.sin, 0.25, decay_pow=2.0)
    write(os.path.join(folder, "SFX_Splash.wav"), mix(splash, bubbles))
    # goal reached: bright rising arpeggio
    arp = seq(*[tone(lambda x, f=note(n): f, 0.09, lambda p: 0.6 * square(p) + 0.4 * math.sin(p), 0.35, decay_pow=0.8)
                for n in (72, 76, 79, 84)])
    write(os.path.join(folder, "SFX_Goal.wav"), mix(arp, silence(0.1) + tone(lambda x: note(88), 0.35, math.sin, 0.3)))
    # game over: sad descending notes
    write(os.path.join(folder, "SFX_GameOver.wav"),
          seq(*[tone(lambda x, f=note(n): f * (1 - 0.03 * x), 0.28, tri, 0.6, decay_pow=0.7) for n in (67, 63, 60, 55)]))
    # win: short fanfare
    fan = seq(*[tone(lambda x, f=note(n): f, d, lambda p: 0.5 * square(p) + 0.5 * tri(p), 0.4, decay_pow=0.6)
                for n, d in ((67, 0.12), (67, 0.12), (67, 0.12), (72, 0.5))])
    write(os.path.join(folder, "SFX_Win.wav"), fan)
    # dusk chime when the sky changes
    chime = mix(*[silence(0.12 * k) + tone(lambda x, f=note(n): f, 1.2, math.sin, 0.3, decay_pow=2.5)
                  for k, n in enumerate((76, 72, 69, 64))])
    write(os.path.join(folder, "SFX_Dusk.wav"), chime)
    # car horn (two-tone)
    write(os.path.join(folder, "SFX_Honk.wav"),
          mix(tone(lambda x: 400, 0.25, square, 0.3, decay_pow=0.3), tone(lambda x: 500, 0.25, square, 0.3, decay_pow=0.3)))
    # looping music: 8 bars of a bouncy pentatonic tune over a bass line, 120 bpm
    beat = 0.25
    melody = [72, 74, 76, 79, 76, 74, 72, 69, 72, 74, 76, 79, 81, 79, 76, 74,
              76, 79, 81, 84, 81, 79, 76, 74, 72, 74, 76, 74, 72, 69, 67, 69]
    bass = [48, 48, 55, 55, 45, 45, 52, 52, 41, 41, 48, 48, 43, 43, 50, 50]
    mel = seq(*[tone(lambda x, f=note(n): f, beat, lambda p: 0.5 * square(p) + 0.5 * tri(p), 0.18, decay_pow=1.2)
                for n in melody])
    bas = seq(*[tone(lambda x, f=note(n): f, beat * 2, tri, 0.35, attack=0.01, decay_pow=0.5) for n in bass])
    hats = seq(*[noise(0.04, 0.12, 0.9, 3.0) + silence(beat - 0.04) for _ in range(32)])
    write(os.path.join(folder, "SFX_Music.wav"), mix(mel, bas, hats))
    # daytime ambience loop: soft wind plus scattered bird chirps
    loop = 8.0
    wind = [0.5 * s for s in noise(loop, 0.25, 0.01, 0.0)]
    birds = silence(loop)
    for _ in range(14):
        start = int(random.uniform(0, loop - 0.6) * RATE)
        base = random.uniform(2200, 3800)
        chirp = seq(*[tone(lambda x, b=base: b * (1 + 0.25 * math.sin(x * math.pi)), random.uniform(0.04, 0.09),
                           math.sin, 0.25, decay_pow=1.5) + silence(0.03) for _ in range(random.randint(2, 4))])
        for i, s in enumerate(chirp):
            if start + i < len(birds):
                birds[start + i] += s
    write(os.path.join(folder, "SFX_AmbienceDay.wav"), mix(wind, birds))
    # night ambience loop: pulsing cricket trills over a low hum
    loop = 6.0
    crickets = silence(loop)
    for _ in range(9):
        start = int(random.uniform(0, loop - 0.8) * RATE)
        f = random.uniform(4200, 5200)
        trill = []
        for _ in range(random.randint(3, 6)):
            trill += tone(lambda x, f=f: f, 0.025, math.sin, 0.18, decay_pow=0.5) + silence(0.02)
        for i, s in enumerate(trill):
            if start + i < len(crickets):
                crickets[start + i] += s
    hum = [0.4 * s for s in noise(loop, 0.15, 0.005, 0.0)]
    write(os.path.join(folder, "SFX_AmbienceNight.wav"), mix(crickets, hum))


if __name__ == "__main__":
    make_all(sys.argv[1] if len(sys.argv) > 1 else "sfx")
