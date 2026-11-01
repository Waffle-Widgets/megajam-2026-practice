# Project notes for Claude Code

## Read these first
- `docs/PLAN.md` — the team plan, schedule, and rules of thumb
- `docs/PITCH.md` — the game we're making (filled in after the theme reveal)
- `docs/RULES.md` — the official jam rules we must follow
- `CREDITS.md` — every asset we didn't make ourselves

## Who we are
- A two-person team entering the 2026 Epic AI MegaJam (Nov 12-15).
- **This repo is our practice/setup sandbox, not the jam entry.** We're learning the tools and running practice jams here.
  When we discover a better way to work, suggest updating this CLAUDE.md so the improvement carries into the real jam repo.
- We are beginners: we play a lot of games but have little coding or Unreal experience.
- We act as game designers and testers. You do the implementation.

## Engine and project
- Unreal Engine 5.8, connected to you through Epic's Unreal MCP plugin.
- C++ project, but build gameplay in **Blueprints** unless C++ is truly required. Ask before writing C++.
- Target platform: Windows.

## How to work with us
- Make **one small change at a time**, then stop and tell us exactly what to test in Play mode.
- Explain every change in plain language: what you made, where it lives in the Content Browser, and why.
- Before a big or risky change, tell us the plan and wait for "go".
- If something fails, tell us the actual error and your best guess at the cause. Don't silently retry many times.
- Remind us to commit in GitHub Desktop after each working feature.
- Keep the project tidy: put our content under `Content/Game/` in folders by type (Blueprints, Maps, Materials, Audio, UI).
- Use clear names: `BP_` for Blueprints, `M_` for materials, `MI_` for material instances, `WBP_` for widgets, `SFX_` for sounds.

## Scope guardrails
- The game should be one level, one core mechanic, 3-5 minutes of play.
- Push back if we ask for multiplayer, story/dialogue systems, inventories, complex enemy AI, or open worlds during the jam. Suggest a simpler version instead.
- Prioritize game feel (responsive controls, feedback, sound, juice) over feature count.

## Assets and credits
- When we import an asset we didn't make (Fab, AI-generated, sound libraries), remind us to add it to `CREDITS.md` with its source and license.

## The current game
See `docs/PITCH.md` for the current practice game. If it's empty, ask us what we're building before starting.
