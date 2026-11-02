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
- Once we confirm a feature works in Play mode, save all assets in the editor, then commit and push to GitHub yourself
  with a short plain-language message. Tell us what you committed. Don't commit work we haven't tested.
- We often prompt you remotely from another machine, so send screenshots of the editor or results when they help us follow along.
- Keep the project tidy: put our content under `Content/Game/` in folders by type (Blueprints, Maps, Materials, Audio, UI).
- Use clear names: `BP_` for Blueprints, `M_` for materials, `MI_` for material instances, `WBP_` for widgets, `SFX_` for sounds.

## Scope guardrails
- The game should be one level, one core mechanic, 3-5 minutes of play.
- Push back if we ask for multiplayer, story/dialogue systems, inventories, complex enemy AI, or open worlds during the jam. Suggest a simpler version instead.
- Prioritize game feel (responsive controls, feedback, sound, juice) over feature count.

## Devlog (Glass Box)
- We're aiming for the Glass Box prize (best devlog showing how we built the game), so keep `docs/DEVLOG.md` going without being asked.
- After each change we test and you commit, add an entry using the template in `DEVLOG.md`: what we asked for, the actual prompt,
  what happened (including failures, retries and dead ends), and what we learned. Commit it with the change.
- Log setup problems and things that broke too, not just successes. Those are the most useful parts.
- When the editor is open, save a screenshot to `docs/media/` and link it from the entry.

## Assets and credits
- When we import an asset we didn't make (Fab, AI-generated, sound libraries), remind us to add it to `CREDITS.md` with its source and license.

## Jam rules to enforce
Full summary in `docs/RULES.md`. Warn us if a request would break one of these:
- Only tools, agent configs, MCP settings, prompts and scripts may be prepared before the jam. Gameplay, levels and art must be
  made between Nov 12 and 15, and Epic may check our Git history.
- Sourced assets (Fab, sound libraries) are allowed but not scored. Assets we make or generate with AI are scored, so prefer those.
- Everything in English, suitable for ages 13+, and no trademarks or logos except the Unreal Engine logo.
- The game must use the theme and go well beyond the Third Person template.

## The current game
See `docs/PITCH.md` for the current practice game. If it's empty, ask us what we're building before starting.
