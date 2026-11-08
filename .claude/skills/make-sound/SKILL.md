---
name: make-sound
description: Make sound effects or music for the game from code with tools/make_sfx.py (no downloads, nothing to credit), and get them into Unreal. Use when the game needs a new sound, jingle or music loop.
---

# Sounds from code

`tools/make_sfx.py` synthesizes every sound from sine/square/triangle waves and noise with only the Python standard
library. The results are our own work: no `CREDITS.md` entry, and they count as made by us in the jam.

## Building blocks (all return lists of samples at 44.1 kHz)
- `tone(freq_fn, dur, wave_fn, vol, attack, decay_pow)`: `freq_fn(x)` gets 0..1 across the sound, so `lambda x: 380 + 520 * x`
  is a rising boing. `wave_fn`: `math.sin`, `square`, `tri`, or a blend like `lambda p: 0.7*math.sin(p) + 0.3*tri(p)`.
- `noise(dur, vol, lowpass, decay_pow)`: low `lowpass` = rumble, high = hiss.
- `mix(a, b, ...)` plays together, `seq(a, b, ...)` one after another, `silence(dur)`, `note(midi)` -> Hz (60 = middle C).
- `write(path, samples)` saves a 16-bit mono WAV.

## Recipes that worked
| Feel | Recipe |
|---|---|
| Hop / jump | short rising tone, sine + a little triangle, 0.1 s |
| Land / thump | low falling sine + a puff of low-passed noise |
| Hit / squash | crunchy noise + falling square squeak |
| Reward / pickup | two quick high sine pings |
| Level up | fast rising arpeggio, then a held chord |
| Warning (bell) | detuned metallic pings repeated |
| Near miss | noise swelling in and out + a tiny high tink |

## Steps
1. Add a new function (e.g. `make_<feature>(folder)`) next to the others, with a comment per sound. Don't change
   existing sounds unless asked: their `random.seed` order would change them all.
2. Run it into a scratch folder first and check durations (`wave` module), or play it for the user.
3. Write it into `MegaJamPractice/Content/Game/Audio/` on the PC that owns Unreal: `.wav` files there auto-import
   within seconds. Save the new `SFX_` assets.
4. Mix sounds quieter than you think (vol 0.2-0.4): many play at once in a busy lane.
