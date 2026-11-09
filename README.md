# MegaJam 2026 — Practice & Setup

This is our **practice repo** for the 2026 Epic AI MegaJam. We use it to get Unreal Engine 5.8, Claude Code,
Gemini, MCP, Git LFS and packaging working, and to run our practice jams (Nov 7–8), *before* the real jam.

**This is not our jam entry.** On Nov 11 we create a fresh repo for the real game and copy over only the
setup files (see "Starting the real jam repo" below). Break things here freely.

## New to the team? Start here

1. [`docs/HOW_WE_WORK.md`](docs/HOW_WE_WORK.md): how we work, in five minutes (roles per computer, the playtest loop).
2. [`docs/SETUP_TEAMMATE.md`](docs/SETUP_TEAMMATE.md): set up your Windows PC or Mac.
3. [`docs/PLAYTEST.md`](docs/PLAYTEST.md): how to get test builds and report problems.

Almost everything is done by asking Claude in a chat opened on this repo folder.

## Where things are

| File | What it is |
| --- | --- |
| `docs/HOW_WE_WORK.md` | How the team works: start here |
| `docs/TEAM.md` | Who's on the team, what each computer does, who owns what |
| `docs/PLAYTEST.md` | Test builds and reporting problems as GitHub issues |
| `docs/PLAN.md` | Team plan: roles, tools, setup checklist, schedule |
| `docs/PITCH.md` | The current practice game's idea |
| `docs/RULES.md` | Official jam rules, pasted from itch.io |
| `docs/DEVLOG.md` | Running devlog notes for the Glass Box category |
| `CREDITS.md` | Every asset we didn't make, with source and license |
| `CLAUDE.md` / `GEMINI.md` | Standing instructions for our AI agents |

## Editing these files without Git

Open the file on GitHub, click the pencil icon, make your change, then click **Commit changes**.

## Adding the Unreal project

Create the Unreal project somewhere else first, close Unreal, then copy everything from that project folder
(the `.uproject` file, `Config/`, `Content/`, `Source/`, etc.) into the root of this repo and commit.
The `.gitignore` already skips Unreal's large generated folders.

## Starting the real jam repo (Nov 11)

Create a new private repo (e.g. `megajam-2026`) in waffle-widgets and copy these files into it, improved by
whatever we learned here:

- `CLAUDE.md`, `GEMINI.md`, `.gitignore`, `.gitattributes`
- `docs/PLAN.md`, `docs/RULES.md`, `docs/DEVLOG.md` (the devlog continues)
- An empty `CREDITS.md` and `docs/PITCH.md`

Do **not** copy practice Unreal content into the jam repo. Starting clean keeps it obvious that the game was
made during the jam, which matters for the rules and for the Glass Box devlog.
