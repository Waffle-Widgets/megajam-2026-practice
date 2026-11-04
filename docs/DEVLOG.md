# Devlog

Raw notes for our Glass Box entry. Write fast, clean up later. Link screenshots and clips from `docs/media/`.

## Template for each entry

### YYYY-MM-DD — short title
- **What we tried:**
- **Prompt(s) we gave the agent:**
- **What happened:**
- **What we learned:**
- **Media:**

---

### 2026-11-01 — Signed up
- Entered the 2026 Epic AI MegaJam as a two-person team with almost no game dev experience.
- Made a plan, picked tools (Unreal 5.8, Claude Code, Gemini), and set up a practice repo to get everything working before the jam.

### 2026-11-01 — Setting up the second PC (Gaming PC 1)
- **What we tried:** Getting this PC ready to drive the project: clone the repo, install the tools, open the Unreal project made on the other PC.
- **Prompt(s) we gave the agent:** "I need that repo here so we can send remote commands to it." / "Can you get what is needed set up on this machine?" / "UE is installed now we need to open the project that was created on another computer for this repo."
- **What happened:**
  - Claude found the repo in our GitHub org and cloned it, then checked what was installed. Git, Git LFS, Node, Claude Code and the Epic Launcher were already there.
  - It installed Gemini CLI, GitHub Desktop and Visual Studio 2022 with the C++ game workload, and turned on Git LFS. Unreal 5.8 we installed ourselves, because it needs an Epic login.
  - The project's `.uproject` was tied to an engine ID that only existed on the other PC, so this PC would have asked which engine to use. Claude opened it straight in the 5.8 editor, then changed the file to say `5.8` so it opens on both PCs.
  - The Unreal MCP server auto-started when the editor opened, thanks to the setting committed from the other PC.
  - The first commit failed because Git on the new PC didn't know who we were. We had to set a name and email first.
  - Claude Code can't use a newly added MCP server in the session it's already in. It needs a new session and an approval.
- **What we learned:**
  - Setting up a second machine shows "works on my machine" problems early, like the engine ID and the missing Git identity.
  - Some installs need us at the keyboard: Epic login, permission prompts, sign-ins. Everything else the agent can do.
  - We read the jam rules: no building the game before Nov 12, and anything made before then gets declared (see `docs/RULES.md`).
- **Media:** (none yet)

### 2026-11-01 — Checking the setup, and picking practice game 1
- **What we tried:** Making sure everything the agent needs works, then choosing what to build for practice round 1.
- **Prompt(s) we gave the agent:** "Check to see if everything you need is enabled to start working on this UE project." / "Let's do the pitch"
- **What happened:**
  - Claude connected to the editor over MCP, read the level and took an editor screenshot through it. Git, LFS, GitHub sign-in, Visual Studio and Node all checked out.
  - It noticed the project is Blueprint-only (no C++ source folder), which is fine for us.
  - It offered four tiny arcade games. We picked Frogger, since it fits the Third Person template. It drafted `docs/PITCH.md` with a cut list and we approved it.
- **What we learned:** Asking the agent to verify the setup with a real call (a screenshot) beats trusting the checklist.
- **Media:** (none)

### 2026-11-01 — One tile per hop
- **What we tried:** The core mechanic: each key press hops the character exactly one tile.
- **Prompt(s) we gave the agent:** "Yes, plan the hop" / "Go" / "Something's off" / "The model is not a frog. the person now hops but if you hold the button down it allows you to move very very slowly."
- **What happened:**
  - Claude planned first: a child Blueprint `BP_Frog` of the template character, a `BP_FroggerGameMode`, and a test level `Lvl_Frogger`. We said go.
  - Its Blueprint-writing tool couldn't attach code to the move input event, so it put the hop in a `TryHop` function and wired the input to it by hand. It also couldn't make a Timeline, so the hop arc runs on Event Tick.
  - Claude couldn't press keys inside Play mode itself, so we tested.
  - Bug 1: holding a key hopped once, then walked. The template's walking still ran alongside our hop.
  - First fix (walk speed 0) only half worked: the character still crept slowly. The template has a minimum walk speed.
  - Real fix: `BP_Frog` overrides the template's `Move` with an empty event, so walking is off at the source. That worked.
  - The model is still the mannequin. That's on purpose (it's on the pitch's cut list for now).
- **What we learned:** A child Blueprint doesn't replace the parent's input handling. Patching a symptom (speed 0) can hide the real cause. We're the testers for anything about feel.
- **Media:** [Frog spawned in Play mode](media/2026-11-01-frog-spawn.png)

### 2026-11-01 — Fixed Frogger camera, and the silent save
- **What we tried:** Lock the camera behind and above the frog, like the arcade game, with mouse look off.
- **Prompt(s) we gave the agent:** "Fixed camera"
- **What happened:**
  - Claude set up the camera arm on game start: fixed 55° angle, 10 m back, a little lag so it glides after each hop. The settings are tunable in the frog's Details panel.
  - The save reported success but nothing changed on disk. The cause: our Git LFS setup makes committed Unreal files read-only until someone locks them. Claude ran `git lfs lock` on `BP_Frog`, saved, committed, then unlocked.
- **What we learned:** Lock an asset before editing it. Always check the file actually changed after saving. We added these lessons to CLAUDE.md.
- **Media:** [Fixed camera in Play mode](media/2026-11-01-fixed-camera.png)

### 2026-11-01 — A frog that looks like a frog (sort of)
- **What we tried:** Swap the mannequin for a placeholder frog that fits our "chunky, toy-like" art style.
- **Prompt(s) we gave the agent:** "Yes, placeholder frog"
- **What happened:**
  - Claude locked `BP_Frog` first (the lesson from last time), then built a frog out of 10 basic shapes: body, head, two eyes with pupils, and four legs.
  - It made 4 color materials (`MI_FrogGreen`, `MI_FrogDarkGreen`, `MI_FrogEyeWhite`, `MI_FrogPupil`) from Unreal's basic shape material, just changing the color.
  - It turned collision off on all the shapes so the hop still only uses the invisible capsule, and hid the mannequin instead of deleting it.
  - The first Play-mode screenshot came out black because it was taken before the first frame was drawn. Taking it again worked.
- **What we learned:** Placeholder art from basic shapes is fast and good enough to judge size and feel. Hiding the old mesh is safer than deleting it when template code still uses it.
- **Media:** [Placeholder frog](media/2026-11-01-placeholder-frog.png)

### 2026-11-01 — Cars! The frog can die now
- **What we tried:** The first hazard: three lanes of cars that send the frog back to the start if they hit it.
- **Prompt(s) we gave the agent:** "Yes, plan the cars" / "do all the steps and then i will test it"
- **What happened:**
  - Claude planned three small steps (cars that drive, getting hit, filling the road). We told it to build all three before we tested, to save round trips.
  - It made `BP_Car` (blocky car plus an invisible hitbox that detects the frog without blocking it) with Speed, direction and color settings on each placed car. Cars that drive off one end of the road reappear at the other.
  - It added `Die` and `SaveStart` to `BP_Frog`, and laid out a road with 3 lanes and 9 cars (red, yellow, blue, getting faster).
  - Its tool's list of Blueprint functions didn't show the brand-new `Die` yet, but writing the call directly still worked.
  - Claude can't press keys in Play mode, but it *can* move the frog: it dropped the frog in front of a car (sent back to start) and on a safe row (stayed put) to check before handing it to us.
- **What we learned:** Batching small planned steps is fine when the plan is clear. The agent can test some things in Play mode by moving actors directly, even though it can't play.
- **Media:** [Road and cars](media/2026-11-01-road-and-cars.png)

### 2026-11-01 — The river: ride the logs or drown
- **What we tried:** The second half of the board: a river with drifting logs. Land on a log and you ride it; land in the water and you're back to the start.
- **Prompt(s) we gave the agent:** "Yes, plan the river" / "Go, all three steps"
- **What happened:**
  - Claude planned it first (layout, rules, risks), then built it all in one go: `BP_Log` (a log that stretches to its Length setting and drifts like the cars), `BP_Water` (a water surface with an invisible "you're in the river" zone), a purple safe strip, the far bank, and 10 logs in 3 lanes.
  - The frog got a new `CheckGround` function that runs whenever it isn't mid-hop: ride the log you're on, die if carried off the side, drown if you're in water with no log.
  - One write failed because a new variable's category didn't exist yet. Nothing half-built was left behind; Claude set the category and retried.
  - The tool's readout labelled the log's Speed reader as belonging to a wind component. Claude checked the actual nodes and they were correct (same labelling quirk as before).
  - Testing was tricky: the editor runs slowly when it's not the focused window, so logs drifted further than expected between checks, and the frog kept landing on logs instead of water. Claude moved one lane's logs out of the way to test drowning cleanly.
- **What we learned:** When testing moving things, control the setup (move things out of the way) instead of relying on timing. Don't trust a summary readout over the real node details.
- **Media:** [River and logs](media/2026-11-01-river-and-logs.png)

### 2026-11-01 — A real game: goals, lives, score, win and lose
- **What we tried:** Turn the board into a game you can win or lose: 3 goal slots on the far bank, 3 lives, a score, a HUD, and win / game-over screens with Play Again.
- **Prompt(s) we gave the agent:** "Yes, plan the loop" / "Go, all three steps" / "restarting from dying all your lives or winning makes it so the frog can no longer move."
- **What happened:**
  - Claude planned it, then built it in one go. The game mode became the "referee" that keeps lives, score and goals. The frog reports to it: new row (+10), goal filled (+50), died (-1 life).
  - It made its first UI widgets through the MCP: `WBP_HUD` (lives/score/goals across the top) and `WBP_EndScreen` (YOU WIN! / GAME OVER, final score, Play Again button). That worked on the first try.
  - Goal slots (`BP_GoalSlot`) use classic Frogger rules: landing on the hedge between slots or in a filled slot kills you. The frog also can't hop off the board anymore.
  - Rebuilding the hop function to add the board edges meant deleting and re-adding it. Unreal quietly named the new one `TryHop_0` until Claude compiled in between.
  - Claude tested every rule by moving the frog in Play mode (goal, full slot, hedge, last life, win). It couldn't click the Play Again button itself.
  - Bug we found: after Play Again the frog couldn't move. The end screen switches input to "UI only" so the mouse can click, and that setting survives a level reload. Fix: the game mode switches input back to "game only" every time a level starts.
  - Side note: "save all" tried to save the template character (which we never edited) and failed because it's locked read-only. Nothing changed on disk.
- **What we learned:** Input mode belongs to the game window, not the level, so reset it when a level starts. Human playtesting still catches things the agent's checks miss.
- **Media:** [HUD](media/2026-11-01-hud.png), [Game over](media/2026-11-01-game-over.png), [You win](media/2026-11-01-you-win.png)

### 2026-11-03 — "Take it to the max": an overnight solo run by the agent
- **What we tried:** We gave Claude free rein overnight (until 10:30 a.m.) to push the Frogger practice game as far as it could on graphics, game feel and a new twist, committing as it went. We would play-test in the morning.
- **Prompt(s) we gave the agent:** "Can you take the Frogger practice project ... to the max? See how good you can get the graphics and how smooth you can get that gameplay. Maybe even add a new twist?" / "I'm going to trust you on this and give you until 10:30 a.m. ... You do not need to wait for me to commit."
- **What happened:**
  - **Plan first.** Claude proposed five stages (game feel, lighting, materials and models, effects and sound, a twist) and a twist called **Sundown**. We approved all of it at once.
  - **Game feel.** The hop now eases into its landing, the frog stretches tall mid-air and squashes on landing, and key presses during a hop are remembered and played on landing (an input buffer), so fast tapping never drops a hop. Deaths got animations: cars flatten the frog with a wobble, water spins and sinks it, the camera shakes, and after respawning the frog blinks and can't be hit for 1.2 seconds. Hit boxes got a little more forgiving.
  - **Materials made from scratch in the MCP:** noisy grass and hedge, asphalt with dashed lane lines drawn by math (no textures), water with two moving ripple maps, shiny car paint, and a "glow" material whose brightness follows a world-wide Night value.
  - **Lighting:** a warm low sun with soft shadows, fog, and a post-process volume (bloom, vignette, saturation, fixed exposure).
  - **Scenery** built from basic shapes: a forest of round trees and pines, bushes, rocks, reeds, street lamps, plus round floating logs with end rings and cars with headlights, taillights and bumpers.
  - **Sound:** Claude wrote a Python script (`tools/make_sfx.py`) that synthesizes every sound and a looping chiptune song from sine/square waves and noise, so there's nothing to credit. Hop boing, landing thump, squash crunch, splash, goal chime, dusk chime, win fanfare, game-over tune.
  - **Effects:** little flying "bits" that pop out and fade: dust on every hop, a splash when drowning, green bits when squashed, gold sparkles when filling a lily pad.
  - **The twist, Sundown:** each lily pad you fill moves the day on. Afternoon → sunset → night. The sun sinks and turns orange, the moon rises, street lamps and headlight beams switch on, fireflies come out, the lily pads glow, and every car speeds up 15%. A label under the score says AFTERNOON / SUNSET / NIGHT, and a how-to-play hint shows for the first few seconds.
  - **Things that went wrong:**
    - Claude edited Blueprints while Play mode was still running, and the editor froze for good. It had to force-quit Unreal and lost about 25 minutes of unsaved material and lighting work, then rebuilt it from its own scripts. From then on it saved after every batch and always stopped Play mode before editing.
    - The editor ignored the sound files dropped into the Content folder until it was restarted (and a "prompt before importing" setting was switched off).
    - Logs and cars already placed in the level kept their old look after the Blueprint changed (box logs standing on end!). Claude replaced them with fresh copies, keeping their positions and speeds.
    - A Blueprint "pure node" bug: the goal count was calculated twice, so the first goal jumped straight to night. Fixed by reading the variable after setting it.
    - Auto-exposure made night as bright as day, the first street lamps lit the whole board green, and the logs were nearly invisible at night. Fixed by locking the exposure, dimming the lamps, and adding moonlight.
- **What we learned:**
  - Never edit while Play mode is running, and save after every batch of changes. An editor freeze loses everything unsaved.
  - Changing a Blueprint doesn't always update copies already placed in the level. Check a placed copy, and re-place it if needed.
  - Night scenes need fixed exposure, or the camera "adjusts" and ruins the mood.
  - Sounds can be generated by code instead of downloaded: they're ours, they score, and they need no credits.
- **Media:** [Before](media/2026-11-03-max-before.png), [Afternoon](media/2026-11-03-max-afternoon.png), [Sunset](media/2026-11-03-max-sunset.png), [Night](media/2026-11-03-max-night.png)
- **Later the same night:** Claude kept going after the first commits:
  - A **round, cute frog** made of spheres, with big eyes and a pale belly. The filled-goal marker is a round frog too.
  - A **"SUNDOWN FROGGER" title card** and a camera **swoop** from high above at the start of each round.
  - **Floating "+10 / +50" score pop-ups** and **near-miss honks** when a car is about to reach the frog.
  - **Victory fireworks** behind the win screen. They needed "tick even when paused", because the game pauses on the end screen.
  - **Ambience** that crossfades from birdsong and wind into crickets as night falls.
  - **Road curbs, stone riverbanks** and decorative lily pads at the river ends.
  - The frog **breathes** gently while sitting still and **blinks** every few seconds.
  - Two more surprises:
    - New assets became read-only after their first commit (our LFS lock rule), so two later saves silently failed. Claude now locks every newly committed asset straight away.
    - "Change only the scale" on the street lamps also reset their positions, stacking all four at the start tile. Always pass the full transform.
  - One engine quirk: the graph tool picked the wrong "Set Volume" node (the synth version, not the audio player one). Claude retargeted the node to the right class by hand.
- **Media (final):** [Afternoon](media/2026-11-03-final-afternoon.png), [Sunset](media/2026-11-03-final-sunset.png), [Night](media/2026-11-03-final-night.png), [Win](media/2026-11-03-final-win.png), [All four](media/2026-11-03-final-grid.png)
- **Morning extras (after "You still have time to make this better" and "You can also expand on levels"):**
  - **Three levels instead of one round.** Filling all three lily pads no longer ends the game: the sun comes back up, the pads clear, fireworks go off, and LEVEL 2 starts with +100 points and a bonus life. Winning means clearing level 3. The car speed-up per goal dropped from 15% to 10%, because it now stacks across all three levels. The HUD shows the level number.
  - Claude pushed back gently first: our scope rule says one map, so the levels reuse the same board and get harder, instead of being new maps.
  - **Logs bob** gently in the water and **dip** when the frog lands on them. **Cars bounce** slightly as if their engines are running.
  - **New music:** the song is twice as long (16 seconds), with a second melody section, kick and snare drums, and soft chords, so the loop is less repetitive.
  - **What went wrong:** the graph tool matched our new goal-slot function `Clear` to the array "Clear" node instead. It compiled without complaint and would have done nothing. Claude spotted it by reading the graph back, and renamed the function `Unfill`.
  - **Lesson:** don't give your own functions common names like Clear, Reset or Add. The graph tool may pick an engine node with the same name. Always read the graph back after writing it.
  - The editor re-imported the changed music file by itself while it was open (the auto-import setting from last night paid off).
- **Media:** [Level 2 at sunrise](media/2026-11-03-level2.png)
- **"Make this a full game" (9:20 a.m.):**
  - **Title screen** (`UI/WBP_Title`): the game name, how to play, your best score and a PLAY button, over a slow bird's-eye view of the board with traffic already moving. The HUD stays hidden until you press PLAY, then the camera swoops down to the frog. Play Again skips the title (the level is reopened with a `retry` option). Claude made it by duplicating the end screen, so the styling matched for free.
  - **Best score saved between plays** (`Blueprints/BP_FroggerSave`, a SaveGame). The end screen shows "BEST n", or "** NEW BEST! **" when you beat it.
  - **Levels feel different:** a big "LEVEL 2" / "LEVEL 3" banner with a one-line hint, and the logs speed up 15% each level (not only the cars).
  - **What went wrong:**
    - A long batch of graph writes stopped halfway at one wrong pin name (`Key` should have been `InKey`), and the next one at a node name (`FInterpTo_Constant`). Each graph write is all-or-nothing, so nothing was half-broken. Claude fixed the name and re-sent.
    - Hiding a widget needs an enum value the graph tool couldn't parse (`Hidden`). Claude used render opacity 0/1 instead.
    - Claude chose not to use mouse control to click PLAY, because it would pop up a permission dialog on the PC while we were away. So the PLAY button is the one thing a human must test first.
- **Media:** [Title screen](media/2026-11-03-title.png), [New best](media/2026-11-03-newbest.png)
- **Crossing timer:** each crossing has 30 seconds, shown next to the time of day ("SUNSET     TIME 18"). The last 5 seconds tick, running out costs a life, and seconds left over when you fill a pad become bonus points (2 per second, shown in the "+50  TIME +36" pop-up).
  - **Same mistake twice in one morning:** the HUD's new `SetTime` function became an unrelated engine node (`AnimatedSparseVolumeTextureController.SetTime`). Then, after Claude gave the logs a `SpeedUp` function, the cars' `SpeedUp` call was quietly re-pointed at the log version. Both were caught by reading the graph back and fixed with unique names (`ShowCrossTime`, `LogSpeedUp`). Verified in Play mode: a car went from speed 450 to 495 after a goal.
  - **Lesson:** give every function a name nobody else is likely to use, project-wide, not only engine-wide.
- **Pause menu:** press **P** during play to pause. A PAUSED screen (`UI/WBP_Pause`, another copy of the title screen) shows your score and a RESUME button. P instead of Esc because Esc stops Play mode in the editor.
  - The graph tool can't create keyboard events from text, so Claude placed the "P" key node with `create_node` and wired its Pressed pin to a small frog function (`RequestPauseMenu`) with `connect_pins`. The read-back shows the event with an empty body, so Claude checked the wire with `get_node_infos` instead.
  - Not tested with a real key press yet (Claude can't press keys in Play mode).
- **QUIT buttons** on the title and end screens (they close the game in a packaged build; in the editor they stop Play mode). Added with the UMG tools: a Button plus a TextBlock inside each screen's vertical box, bound to OnClicked.
- **Bonus fly:** every 7 seconds a glowing gold fly lands on a random empty lily pad and buzzes around. Fill that pad while it's there for **BONUS FLY +100**. Verified in Play mode: a pad with the fly gave 50 + time bonus + 100.
  - **Stale copies again:** the fly showed up in Play mode with **no mesh**, because the lily pads already placed in the level didn't pick up the new component's settings. Moving the settings into the construction script didn't help either. Replacing the three lily-pad actors with fresh copies (same names, positions and folder) fixed it. This is the third time this lesson has bitten us: after adding a component to a Blueprint, re-place the level copies straight away.
- **Three new sounds** made by `tools/make_sfx.py` (new `make_extras` function): a woody clock **tick** for the last 5 seconds, a rising **level-up** jingle, and a buzzy **bonus-fly** chime. Surprise: they imported while the editor was still open (we'd thought new files needed a restart). CLAUDE.md is corrected.
- **Small touches:** the timer blinks once a second for the last 5 seconds, and **Esc** also opens the pause menu (in the packaged game; in the editor Esc still stops Play mode). The first attempt at turning the timer red picked the wrong "Set Color and Opacity" node (Image instead of Text), and the graph tool has no modulo, so the blink uses integer division to check odd/even seconds.
- **Media:** [HUD with the timer](media/2026-11-03-timer-hud.png)
- **First packaged Windows build** (`Builds/Windows/MegaJamPractice.exe`, 665 MB, not committed). The first try compiled the game but failed at the cook step, looking for an editor "target" file our project doesn't have. Passing the engine's own `UnrealEditor-Cmd.exe` with `-unrealexe` fixed it: cook and package took 3.5 minutes with the editor still open. Claude launched the .exe and confirmed it opens on the Sundown Frogger title screen. Before packaging, the game's startup map was still the Third Person template level, so it was switched to `Lvl_Frogger`.
  - **Lesson:** package early in the real jam (by day 2), not in the last hour. The first build always finds something.

### 2026-11-03 (late morning) — Endless mode
- **What we asked for:** "Don't these games usually have an endless mode to compete for high score?" Claude offered two options. We picked a separate mode: "Option 2. But the endless mode should just be one level and it should evolve as you progress."
- **What happened:**
  - An **ENDLESS** button on the title, between PLAY and QUIT. PLAY is still the 3-level game you can win.
  - **Endless is one board that keeps evolving:** no level banners, no win. Every lily pad moves the clock on (sunset → night → dawn → sunset ...) and makes the cars 6% and the logs 4% faster, capped at about 2.2× so it stays possible. It also takes 1 second off the crossing timer, down to 15.
  - **Board clear:** when all 3 pads are full they empty with "BOARD CLEAR +100", fireworks and +1 life (max 5). The run ends only when you run out of lives.
  - Endless has its **own best score** (the title shows both), the HUD says ENDLESS instead of LEVEL n, and Play Again keeps you in the same mode (the level reopens with `?retry?endless`).
  - Verified in Play mode by dropping the frog on pads: after 3 goals the pads cleared, lives went 3 → 4, the timer went 30 → 27, and the game kept going. The 4th goal brought sunset again with the timer at 26.
- **What we learned:** passing options through `OpenLevel` (`?retry?endless`) is an easy way to remember choices across a level reload, with no GameInstance needed.
- **Media:** [Endless mode at sunset](media/2026-11-03-endless.png)

### 2026-11-03 (afternoon) — Endless becomes a never-ending world
- **What we asked for:** "what i meant by endless was that the user did not restart at the beginning each time they hit one of the markers, they just keep hopping until they die. So the level should continue going and creating new obstacles as we go instead of just being a road and a river over and over." Then: "We can also generate different landscapes if possible ... If you can add different types of roads and crossings and whatnot, get creative with it." Later: "Go ahead and add anything you think might make the game better or more interesting."
- **What happened:**
  - Our first endless mode (one board that just sped up) was a misunderstanding. Claude wrote up a plan for a Crossy Road-style version and waited for "go", since it was a big change.
  - **New map `Lvl_Endless`:** a copy of our level with the sky, sun, moon, fog and lighting, and 152 board pieces removed. The ENDLESS button now opens it.
  - **`BP_Lane` builds one row at a time:** grass, road, highway, river, railway or lily pond, with its own cars, logs, water, train, lamps and scenery. The game mode keeps about 22 rows built ahead of the frog and removes rows 10 behind, so the number of objects stays around 190.
  - **Five landscapes, 25 rows each:** meadow, autumn forest, desert, snowfields and city, each with its own ground, props, mix of row types and a banner with a tip. New props: autumn tree, snowy pine, cactus, building, fire hydrant.
  - **New crossings:** **railway** (`BP_Train`: red lights flash and a bell rings about 1.8 seconds before a fast train), **highways** with trucks and lane lines, **ice floes** instead of logs in the snow, and **lily ponds** with still pads.
  - **Fairness rules:** grass to start, never too many dangerous rows in a row, ponds always between grass, and no obstacle rows back to back. Difficulty goes up with distance.
  - **Checkpoints:** reaching a grass row makes it your respawn point. You can hop back 3 rows behind it.
  - **Other rules:** an 18-second "keep moving" clock that refills on each new row, day → sunset → night → dawn every 20 rows, and +1 life every 50 rows.
  - **Extras:** **golden flies** (+50) on some rows, and a **gold finish line** on the row of your best distance, with a "NEW RECORD!" banner when you pass it. The best distance is saved.
  - Three new sounds from code: crossing bell, train horn, and a chime for each new landscape.
- **What went wrong (lots):**
  - **Name clashes again:** three Blueprints each got a `Configure` function, and the lane's call was quietly pointed at the log's version. Claude renamed them `CarSetup`, `LogSetup` and `TrainSetup`, and gave all the lane's functions a `Lane` prefix. **Lesson:** a unique name per function, always.
  - **The silent save:** the edited car, log and water Blueprints didn't save because they were read-only until locked. `git status` showed it, and locking fixed it.
  - **Our bug report: "Unable to go back after moving forward, and you respawn where you were even if it isn't safe."**
    - Cause: the function asking a row "what kind are you?" was written as `(return (LaneKind ...))`. That compiles, but the call never runs, so it returned the default 0, which means grass.
    - So every row became a checkpoint, and you could never go back past the latest one. The obstacle check had the same mistake, so trees didn't block anything.
    - Fix: store the answer first, then return it. This lesson is now in CLAUDE.md.
  - **Our report: "the spaces you land on seem off center."** Riding a log moves the frog by any amount, so it ended up out of line with the grid. Each hop now snaps to the nearest column.
  - **Our report: no clear path before the clock ran out.**
    - The rows went river, obstacle grass, river, obstacle grass. You land wherever the log takes you, so you were stuck waiting for a lucky log.
    - Fixes: no obstacles on grass right after water, 4 logs per river early on, and an 18-second clock (was 12).
  - The first test run lost all its lives to the clock before anyone moved. The endless clock now waits for the first hop.
  - Claude compiled a Blueprint while we were in Play mode (against our own rule). It was lucky this time, and Claude now checks first.
- **What we learned:**
  - Building the world in small row pieces with a few fairness rules gives lots of variety for little work. Fairness problems only show up when a person plays, though.
  - Teleporting the frog and reading values is a quick way for the agent to test rules, but it can't tell how a level *feels*.
- **Media:** [Start of a run](media/endless-world-start.png), [Sunset with lily pads and lamps](media/endless-world-sunset.png), [Autumn forest banner](media/endless-world-autumn.png), [Best-distance line and golden flies](media/endless-bestline-flies.png), [Fairer rivers](media/endless-rivers-fairer.png)

### 2026-11-03 (evening) — Showing the side edges
- **What we asked for:** "is it normal to restrict how far left and right the player can move?" Claude said yes: every game like this has a side limit, or you could walk around the danger. The problem was that ours was invisible, so it felt like the controls had stopped working. We picked "Show the edges".
- **What happened:**
  - First version: a white border line on every row, a dark see-through shade past it (new material `M_EdgeShade`), and the obstacle "bump" sound when you try to hop past the edge or back past your checkpoint.
  - We said "it's a little distracting", so Claude removed the white line and roughly halved the shade (strength 0.5 → 0.28). Only a gentle dimming is left, plus the bump.
  - The editor popped up a Message Log window over the viewport during testing. Harmless, but it hid half the first screenshot.
- **What we learned:** feedback like the edge needs to be noticeable without pulling your eye off the frog. Start subtle and turn it up if players miss it.
- **Media:** [Toned-down edge](media/endless-edges.png)

### 2026-11-03 (night) — "As real as we can": photo-scans and a realistic toad
- **What we asked for:** "how realistic can you get this game looking ... Can we get this so realistic it's funny?" then "Let's go as real as we can." Then: "would you be able to get the scans from Fab yourself?"
- **What happened:**
  - **Camera and light pass (both maps):**
    - Our old settings were working *against* realism: a very shallow focus (f/2.2) made everything look like a miniature, and the colours were boosted.
    - Claude switched to a real-camera look: f/11 so everything is sharp, natural colour, light film grain, colour fringing at the edges, some motion blur, higher-quality Lumen lighting, sun light shafts and denser fog.
  - **Getting assets from Fab, using Claude's built-in browser:**
    - We signed in ourselves: Claude may not type passwords, and the Epic launcher login doesn't carry over to that browser.
    - Claude searched, then showed us a shortlist with prices, licences and sizes before getting anything. On our "yes" it added each item to our library, accepted Fab's licence once (leaving the marketing-emails box unticked) and downloaded 2K versions.
    - **Surprises:** Quixel Megascans *surfaces* are free, but the Granite Rock we'd picked is $2.99 for a Personal licence, so we skipped it. Free realistic frogs and cars basically don't exist.
  - **Six photo-scanned grounds:** asphalt, grass, gravel, sand, snow and fallen leaves. One new material, `M_Surface`, lines them up seamlessly across every row and still paints dashed lane lines on roads. Our existing ground materials were switched over to it, so both maps changed at once.
  - **The toad:** "Giang Demon_99" is a rigged fantasy toad with 34 animations, free with the Personal licence. It's 530 MB to download, so Claude asked us again before fetching it.
    - We clicked Import ourselves; that one step needs a human.
    - Claude deleted the import's 4K duplicate textures and 27 animations we don't need. The toad went from about 220 MB to 43 MB.
    - It now replaces the sphere frog, playing its idle animation.
- **What went wrong:**
  - **Frozen editor:** after importing the textures, Claude deleted the raw `.jpg` copies. Unreal took that as "the textures were deleted" and opened a **Delete Assets** pop-up, which froze the MCP for 5 minutes.
    - Claude found the pop-up by listing the editor's windows from PowerShell, because the screen-control tool couldn't find Unreal by name, and cancelled it with Escape.
    - Nothing was lost. Raw source files now stay in the project folder and are gitignored instead.
  - **Invisible toad:** at first the sphere frog still showed and the toad didn't. The frog's respawn-blink code switches its whole visual on every frame, which brought the spheres back. Hiding them with "hidden in game" fixed it.
  - **Backwards toad:** we tested it and found it facing backwards, so Claude turned it 180°.
  - **Downloads:** the browser pane saves downloads as `<random>.tmp` files, so Claude identified each one by what was inside the zip.
- **What we learned:**
  - **Assets:** most of "realistic" comes from scanned assets, not engine settings. In the real jam, Fab assets are allowed but not scored, so the scored art must be ours or AI-generated.
  - **Our role:** the agent can shop on Fab for us, but sign-in, licences and spending money stay our call.
- **Media:** [Camera pass](media/real-pass1-day.png), [Photo-scanned ground](media/real-pass2-scans.png), [The toad](media/real-pass3-toad.png), [Toad close-up](media/real-pass3-toad-closeup.png)

### 2026-11-03 (late night) — The toad moves like a toad
- **What we asked for:** "Yes, animate the toad".
- **What happened:**
  - **Hop:** the toad plays its own Jump animation at 2.5× speed, so it fits our 0.15-second hop, and goes back to idle about half a second after landing.
  - **Death and respawn:** dying plays its Death animation on top of our squash or sink effect, and respawning brings back the idle loop.
  - **How it's built:** two small helper functions in `BP_Frog`, `ToadPlay` and `ToadBackToIdle`, with a timer to return to idle.
  - **Testing:** Claude tested a drowning by teleporting the toad into a river. The hop animation needed a real key press, so we checked that one ourselves.
- **What went wrong:**
  - Every clip in the pack reports the same 8.35 seconds, as if they were all padded to one timeline. So Claude plays only the start of each clip, sped up.
  - One graph write failed on a wrong pin name (`NewSocketOffset` should be `SocketOffset`). The error message listed the valid pins, so it was a one-line fix.
- **What we learned:** a pack's animations rarely match our game's timing. Playing part of a clip, faster, is a cheap way to make them fit.

### 2026-11-03 (late night) — Blender tools keep vanishing: apps tied to a chat
- **What we tried:** Starting a fresh chat to build our first Blender model (a river log) through the new Blender MCP.
- **Prompt(s) we gave the agent:** "the OLD M Station - MegaJam Practice game chat had me open this new chat to create assets in blender" / "blender and UE closed when i deleted a chat"
- **What happened:**
  - Two chats in a row could see Blender and Unreal at the start, then lost both tool sets between messages, even though both apps were still running and listening.
  - First guess: the app dropped unapproved project servers when we reconnected from another machine. Claude added a per-PC, gitignored `.claude/settings.local.json` that pre-approves the servers in `.mcp.json`.
  - Then we deleted an old chat and Blender and Unreal both closed. An earlier chat had relaunched them itself, so Windows treated them as part of that chat and closed them with it.
  - Claude reopened both through `explorer.exe`, so they belong to Windows and not to any chat. Both MCPs answered within about 15 seconds. Unreal was force-closed, but git showed nothing unsaved that mattered.
- **What we learned:**
  - Open the editors yourself, or have the agent launch them via Explorer. Anything a chat starts lives and dies with that chat.
  - When tools vanish, check the apps first, then start a new chat. The log is still waiting to be built.
- **Media:** (none)
