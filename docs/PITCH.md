# Pitch

_Theme revealed Wed Nov 11, 11:00 AM Pacific. Written 7:30 PM Pacific, Wed Nov 11 — **a draft, pending the team's go.**
Nothing for the game itself gets made before the jam opens at 9:00 PM Pacific tonight (`docs/RULES.md`, §7h).
When the jam repo exists, this file is copied into it and this one goes back to being the practice pitch._

**Theme:** Director's Cut

**Working title:** That's a Wrap — project/repo name `ThatsAWrap`, itch zip `WaffleWidgets_ThatsAWrap.zip`

**One-sentence pitch:** You're the stunt double on a doomed movie set: wreck the shot exactly the way the director asked
before he yells "CUT!" — and every new take is filmed in the rubble of your last one.

**Core mechanic (the one thing that has to feel great):** **The slam.** One button throws you shoulder-first into the set
and breaks whatever you hit — pillars into chunks, walls into holes, prop crates into splinters. It has to land with
weight: a short wind-up, a hard stop, screen shake, a dust burst, and a half-beat of slow motion on the biggest break of
each take. If the slam feels good, the game works; if it doesn't, nothing else saves it.

**How you win / how you lose:**
- A **take** is one 30-second shot with 2–3 **director's notes** on screen: _"both pillars down"_, _"end the shot on the
  balcony"_, _"nothing left standing on the left side"_.
- **"CUT!"** ends the take. Notes you filled are printed. Notes you missed come back as a re-shoot — and **the set does
  not reset**, so take 2 starts in the wreckage of take 1. Fewer things left to break, and new ways through.
- **Win:** all notes printed before the film runs out (4 takes). The wrap screen prints _The Director's Cut_: your takes,
  your score and a one-line review.
- **Lose:** film runs out with notes unfilled — the director recasts you.
- **Score:** +100 a printed note, +50 if it was printed in a single take, a debris bonus for how much of the set is on the
  floor, plus time left on the shot clock.

**How it uses the theme:** Literally and as the verb. The director's cut is the film he keeps, and the game is you
earning it. "CUT!" is how a take ends, his notes are the goal, the set that never resets between takes is the continuity
error nobody edits out, and the last thing you see is the cut he releases.

**Length of a playthrough:** 3–5 minutes (4 takes × 30 s, plus notes and the wrap screen).

**Art style in a few words:** A film soundstage — fake stone, visible rigging, light stands and a boom mic at the edges,
hard movie key-light with deep shadows and dust in the beam. Grey-box first, dressed on Saturday.

## Why this one, for this team, in four days

- **The one mechanic is already proven.** Breakables through the MCP were tested on Nov 11 (`chaos-physics` skill):
  Geometry Collections made from a Dataflow template, broken from code with strain plus a small impulse. The jam
  bootstrap turns the plugin on. The honest limit is in the skill too — **ramming a Geometry Collection did not break
  it** (a 200 kg ball at 25 m/s bounced), so the slam breaks things by an explicit strain call at the hit point, not by
  collision damage. Design around the tested path.
- **One soundstage = one level.** Matches our own rule: one mechanic, one level, 3–5 minutes.
- **Render Royalty (prize #2) is free here.** Destruction, dust and a hard key light photograph well, and we have real
  fire if a take calls for it (`niagara-fluids`).
- **Glass Box (prize #1) writes itself.** "We built a game about re-shooting a scene by re-shooting it" — and the devlog
  already has the negative results to show.
- **The director's notes are data, not AI.** A note is a condition on the level (is this actor broken, did the player
  reach this volume, is this half of the set clear). No enemy AI, no pathfinding, no dialogue system.

## Cut list (things we will NOT build)

- **No replay/highlight reel.** The wrap screen is a still "poster" of the final wreckage with the scores on it, not
  recorded footage. (First thing to add back if Saturday is calm — it would be a great trailer, and a terrible Thursday.)
- **No second set, no scene select.** One soundstage, dressed once.
- **No enemies, no NPCs, no other actors on set.** The director is a voice and a note card, never a character to model.
- **No voice acting.** Four or five synthesized barks ("CUT!", "AGAIN", "PRINT IT", "that's a wrap") from `make_sfx.py`,
  plus on-screen text. Everything in English (§7i).
- **No settings menu, no key rebinding, no volume sliders.** Title screen is PLAY / QUIT and the best score.
- **No physics puzzles, no stacking, no carrying objects.** You slam. That's the verb.
- **No Fields, no vehicles, no ragdolls, no cloth** — all untested in `chaos-physics`.
- **No mobile, no web, no macOS build.** Windows zip under 1 GB (§7f).
- **No multiplayer, no leaderboard.** Best score is local.
