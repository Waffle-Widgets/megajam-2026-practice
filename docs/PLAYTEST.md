# Playtesting

One computer (the **builder**) changes the game. Everyone else plays test builds and reports what they find as
GitHub issues. Which computer does what: the Computers table in `docs/TEAM.md`. To change it, ask Claude.

```
 testers play Build N  ->  file issues  ->  builder's Claude fixes them on the `playtest` branch
        ^                                                   |
        |                                                   v
 "works" on the issue  <-  Build N+1 published  <-  issues marked ready-to-check
                                                    (confirmed fixes merge into main)
```

## Get the latest build
Just ask Claude on your computer: **"Get me the latest build."**
- **Windows:** it downloads the newest "Build N" from the repo's Releases page and unzips it. Run the `.exe`.
  (By hand: open `https://github.com/Waffle-Widgets/<repo>/releases/latest`, which always shows the newest build;
  bookmark it, or save it on your phone. Download the zip there.)
- **Mac:** a Windows build won't run on a Mac, so you play in Unreal. With Unreal closed, Claude switches the repo
  to the `playtest` branch and pulls. Open the project and press **Play**. **Never save** on a tester computer; if
  Unreal asks when you close it, choose **Don't Save**.

## Report something
Pick whichever is fastest:
- **Tell Claude:** "File an issue: on Build 14 the frog fell through the road on lane two, it breaks the game."
  It fills in the form and gives you the link to paste a screenshot.
- **GitHub website:** the repo > Issues > New issue > **Playtest report**.
- **Phone:** the GitHub app > the repo > Issues > +. Handy while the game stays on screen.

One problem per issue. Say which build, what happened, what you expected, and how bad it is. A screenshot helps:
Windows Win+Shift+S then paste; Mac Cmd+Shift+4 then drag the file in.

**Kinds:** **Bug** = broken. **Feel** = works, but too slow, too hard, mushy controls. **Idea** = something to add;
the team decides on ideas before anyone builds them.

## Check a fix
Issues labelled **ready-to-check** say which build has the fix. Play that build and reply on the issue:
**works**, or what's still wrong. Or tell Claude "issue 12 works". The builder merges confirmed fixes into `main`,
and that closes the issue.

## What the labels mean
| Label | Meaning |
|---|---|
| playtest | Found while playing |
| bug / feel / idea | What kind |
| breaks-game | Fixed first |
| in-progress | The builder is on it |
| ready-to-check | In a published build: please check |

## For the builder
Ask Claude: **"Work through the playtest issues"** (or `/loop 10m /playtest-issues` to keep going on its own). It
fixes one at a time on the `playtest` branch, publishes a build with `tools/publish_build.ps1` after a few fixes, and
merges into `main` once testers confirm. Details: `.claude/skills/playtest-issues/SKILL.md`.
