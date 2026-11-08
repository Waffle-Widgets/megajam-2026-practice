---
name: package-build
description: Package the Unreal game as a Windows build and zip it for itch.io / the jam submission with tools/package_build.ps1. Use when the user wants a playable build, a test on another PC, or the final submission.
---

# Packaging a Windows build

## Before
1. Everything the build needs is saved (`is_dirty` false for assets under `/Game/Game`) and tested.
2. `Config/DefaultEngine.ini` `GameDefaultMap` points at the level the game starts on (title map).
3. Tell the user it takes about 4-5 minutes and **nobody saves assets while it cooks**.

## Run (in the background, it's long)
```
powershell -ExecutionPolicy Bypass -File tools\package_build.ps1 -Run
```
Options: `-Game <Name>` (zip name), `-CopyTo <folder>` (copy the zip, e.g. to the other PC), `-Build` (force a compile
after C++ or plugin changes; needs the editor closed), `-Engine <UE folder>` if UE isn't in the default place.

What the script already handles: cooks the start map plus every map under `Content/Game/`, zips
`Builds/<Team>_<Game>.zip`, checks the 1 GB limit, keeps `.pdb` symbols out of the zip, uses `-nocompileeditor` and
`-unrealexe` (so the editor can stay open), and `-Run` launches the game for 20 seconds to check it stays up.

## After
- Report the zip path and size, and whether `-Run` passed. `Builds/` is gitignored: don't commit it.
- Ask the user to play the packaged build (not just PIE) start to finish: title, a full run, game over, play again, quit.
- If it fails, show the actual error lines from the log and your best guess. Don't retry blindly.

## Jam submission
Submitted by a human, not an agent (rules §17). Check `docs/RULES.md` for the deadline and what goes with the zip
(video, description, team names).
