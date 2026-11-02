# MegaJam 2026 Game Plan

_Last updated: Nov 1, 2026_

## Overview

We're a two-person beginner team building a small, polished Unreal Engine 5.8 game in four days, with AI agents doing most of the implementation.

| What | When (Pacific) |
| --- | --- |
| Theme reveal livestream | Wed Nov 11, 11:00 AM |
| Jam runs | Thu Nov 12 – Sun Nov 15 |
| Submission deadline | Confirm on itch.io |

**Prize targets.** Each entry can win one main category and one modifier. Main: Best Overall in Unreal Engine ($7,500 / $5,000 / $2,500), plus up to $50,000 continuation grants for standout entries. Modifiers we're aiming at: **Best Team** ($5,000) and **Glass Box** ($2,500, best devlog showing how AI was used). Glass Box is our most realistic win: two gamers with no dev experience shipping an Unreal game is exactly its story.

**Our rule:** a tiny game that feels great beats an ambitious one that's broken. One mechanic, one level, 3–5 minutes of play.

## Team roles and machines

One person drives the editor; the other owns everything outside it. That splits the work with no file conflicts.

| Role | Owns | Machine |
| --- | --- | --- |
| Driver | Unreal, Claude Code, building the game, packaging builds | Gaming PC 1 (strongest) |
| Director | Assets, audio, Gemini art, playtesting, devlog, trailer, itch.io page | Teammate's PC |
| Clean test machine | Runs packaged builds only, to catch "works on my machine" bugs | Gaming PC 2 |

Both of us are game designers: we decide what's fun, test constantly, and give the agent precise feedback.

## Tools

Claude Code builds; Gemini makes art and gives second opinions. Never have two agents editing the project at once.

| Tool | Job | Who |
| --- | --- | --- |
| Unreal Engine 5.8 (Epic Games Launcher) | The engine; 5.8 has Epic's experimental MCP plugin | Driver |
| Claude Code | Main agent, drives the editor through MCP | Driver |
| Gemini (+ Gemini CLI as backup agent) | Concept art, textures, UI images, debugging second opinion | Director |
| Visual Studio 2022 ("Game development with C++") | Needed for packaging and some plugins | Driver |
| Node.js LTS | Some MCP setups need it | Driver |
| GitHub Desktop + Git LFS | Backups and version history | Driver |
| Fab (incl. free Megascans) | Ready-made environment assets | Director |
| Meshy or similar | AI-generated 3D props and characters | Director |
| ElevenLabs or similar | AI sound effects; plus a music generator or free library | Director |
| OBS Studio | Recording gameplay and devlog footage | Director |
| DaVinci Resolve (free) | Editing trailer and devlog video | Director |
| Discord | Voice and screen share while we work | Both |

Check every asset tool's license allows use in a game, and log each one in the credits as we go.

## Setup checklist

Setup is done when a packaged build made by the agent runs on Gaming PC 2.

**Accounts**

- [ ] Both of us registered on the jam's itch.io page
- [ ] Both of us have Epic Games accounts
- [ ] Claude plan includes Claude Code; Gemini set up

**Install on Gaming PC 1 (start the Unreal download first; it's huge)**

- [x] Epic Games Launcher + Unreal Engine 5.8
- [ ] Visual Studio 2022 with the "Game development with C++" workload
- [ ] Node.js LTS, GitHub Desktop, Claude Code, Gemini CLI

**First project**

- [ ] New project: Games → Third Person (or Top Down), C++ project, saved on an SSD
- [x] Edit → Plugins: enable Model Context Protocol (Unreal MCP), All Toolsets, Toolset Registry, Unreal Terminal; restart
- [x] Start the MCP server (Epic's default endpoint: http://127.0.0.1:8000/mcp). It does not start by itself: type `ModelContextProtocol.StartServer` in the editor's Cmd box. Auto-start is now set in `Config/DefaultEditorPerProjectUserSettings.ini` (`bAutoStartServer=True`), because the setting doesn't show up in the editor's settings windows. Stuck? Try the "Unreal MCP Setup Assistant" on Fab (third-party, early version)
- [x] Connect Claude Code to that endpoint as an HTTP MCP server
- [ ] Test: ask Claude Code to list the actors in the level

**Smoke test**

- [ ] Agent places a cube and gives it a colored material
- [ ] Agent turns it into a jump pad; we play it in the editor
- [ ] Package a Windows build (Platforms → Windows → Package Project)
- [ ] Copy to Gaming PC 2 and run it

**Workflow**

- [x] CLAUDE.md is in the repo root (done when the Unreal project is added)
- [x] Practice repo (waffle-widgets/megajam-2026-practice) with Git LFS; first commit
- [ ] Nov 11: fresh jam repo created; setup files copied over (see README)
- [ ] Devlog started (screenshots of setup, including what went wrong)

## Prep schedule (Nov 1–11)

By kickoff, asking the agent, testing, fixing and packaging should feel routine.

| Dates | Goal | Done when |
| --- | --- | --- |
| Sun Nov 1 – Tue Nov 3 | Install, connect MCP, learn the editor basics | Smoke test passes on Gaming PC 2 |
| Wed Nov 4 – Thu Nov 5 | Backups, CLAUDE.md, asset tools tried out | Repo has a first commit; one AI asset imported |
| Sat Nov 7 | Practice 1: remake a tiny arcade game we both know | Playable packaged build |
| Sun Nov 8 | Practice 2: random theme, 1-day mini jam | Build uploaded to a private itch.io page |
| Mon Nov 9 – Tue Nov 10 | Fix what hurt; build a starter project; read the official rules | Starter project with start/restart and working packaging |
| Wed Nov 11 | Watch the 11 AM reveal, brainstorm 1 hour, pick the idea | One-sentence pitch both of us agree on |

## Jam week (Nov 12–15)

Feature freeze is end of Friday; Sunday is bug fixes and submission only.

| Day | Driver | Director | Done when |
| --- | --- | --- | --- |
| Thu Nov 12 | Grey-box the core mechanic, no art | Gather asset and sound candidates; devlog day 1 | Core loop playable start to finish |
| Fri Nov 13 | Content: level, win/lose, start/restart | Generate final art and audio; first outside playtest | Feature freeze; packaged build works on PC 2 |
| Sat Nov 14 | Art, audio, juice (screen shake, particles, feedback sounds) | Playtest on someone new; record footage | Game feels good; no new features |
| Sun Nov 15 | Bug fixes only; final package by midday | Screenshots, short trailer, itch.io page, devlog | Submitted well before the deadline |

## Working with the agent

We direct, the agent builds, we test after every change.

- **Be concrete.** Not "add enemies" but "when the player lands on an enemy, it squashes flat, disappears, and the player bounces up."
- **One small change at a time.** Ask, play-test, then ask for the next thing.
- **Report bugs precisely.** What we did, what we expected, what happened, plus any error text.
- **Commit every time something works.** When the agent breaks things, roll back instead of debugging for an hour.
- **Prefer Blueprints.** Easier for us to see and understand what was built.
- **Stuck for 20+ minutes?** Ask Gemini for a second opinion, or simplify the feature.
- **Scope out:** multiplayer, story, dialogue, inventories, smart enemies, open worlds.

## Rules to confirm and devlog plan

Read the official rules on the itch.io page before Nov 9 and fill in the answers here.

- [ ] Submission deadline and timezone
- [ ] Rules on sourced and AI-generated assets (past MegaJams required crediting every asset we didn't make, and some years didn't score sourced assets)
- [ ] Required build platforms and file size limit
- [ ] Required gameplay video or screenshots
- [ ] How Glass Box devlogs are submitted and judged
- [ ] Whether a team needs one submission or all members registered

**Devlog (Glass Box).** Capture as we go: setup struggles, prompts that worked and failed, before/after clips, and what we'd do differently. Aim for a short written post plus a 2–3 minute video.

**Sources:** [2026 Epic AI MegaJam announcement](https://unrealengine.com/news/2026-epic-ai-megajam) · [Unreal MCP Setup Assistant on Fab](https://www.fab.com/listings/651ed47d-db10-4dfa-9a6c-b8080d0d6b8e)
