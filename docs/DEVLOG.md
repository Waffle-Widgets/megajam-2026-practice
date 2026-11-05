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

### 2026-11-03 (late night) — Our first Blender model: a river log, then a whole log kit
- **What we asked for:** a log modelled in Blender to replace the plain cylinder. After the first version: "they work but they look awful" and then "use blender for whatever you need. I want to see what you can do. Impress me."
- **Prompt(s) we gave the agent:** "Yes, bring it in" / "make sure you can import these items without me having to click on something in case I am controlling remotely" / "Yes, switch it off" / "Impress me."
- **What happened:**
  - **Version 1 (one log model):** Claude built a 1 m log in Blender: bark, sawn ends, two branch stubs, moss on top. The first render had bark like paving stones; the second render fixed it.
  - **The MCP tools vanished mid-chat again.** Both apps were still running and `.mcp.json` was fine, but the session had simply dropped the servers. A fresh chat picked the job up.
  - **Getting it into Unreal:** Claude baked the Blender look into a colour map and a bump (normal) map, then exported the FBX. The first bump map was almost flat, so it re-baked with a deeper bump.
  - The FBX opened Unreal's "Import Content" window, and the MCP froze until we clicked Import. The other chat added a project setting (`DefaultEngine.ini`) that turns that window off, so imports need no clicks when we play remotely.
  - **Version 1 looked awful in game.** Logs are 2-4 m long, so one 1 m model got stretched up to 4×: smeared bark and wide flat stubs. Worse, in Endless the logs stood on end. A second setup function, `LogSetup`, still used the old cylinder's sizing, which also squashed our log into the lily pads.
  - **Version 2 (a log kit):** endless logs can be any length from about 1.2 to 3.6 m, so a model per length would never cover them all. Claude built three pieces instead:
    - a **trunk** whose bark repeats seamlessly every metre (the pattern wraps around the log and along it);
    - a **sawn end** with growth rings, heartwood, radial cracks and a branch stub;
    - a **broken end** with splintered shards, a damp mossy core, a snapped twig and four bracket fungi.
  - In Unreal, `BP_Log` places one end at each side and stretches only the trunk between them. The material is told the trunk's length, so it repeats the bark instead of stretching it, and each log gets a random offset so no two look alike.
  - The no-click import worked first time: three models and four textures arrived with no window.
- **What went wrong on the way:**
  - The bark came out as rounded "paving stones" again, then far too pale. Fix: much longer, narrower ridge cells, and colours about 3× darker.
  - Every end face rendered as bark. Blender drops face material numbers on a mesh with no material slots yet, and Claude's script also reset them by clearing slots.
  - The broken end took three tries: first a crumpled paper bag, then a symmetrical "flower", then chunky clustered shards that read as broken wood.
  - The caps came into Unreal facing −Y. Blender's +Y becomes Unreal's −Y, so the left end needs turning 180°.
  - In Unreal the trunk first showed flat stripes. The "repeat the bark" value was set with a runtime-only node, which doesn't stick when the editor runs the Blueprint. `SetDefaultCustomPrimitiveDataFloat` works. The caps then went plain brown until they got a value of 1 too.
- **What we learned:**
  - Don't stretch one model to many sizes. Split it into ends that never stretch and a middle that repeats.
  - Baking procedural Blender materials into textures works well. Bark that wraps in 4D noise tiles with no seams.
  - Check every way a Blueprint is used (placed in a level vs spawned by `LogSetup`). The same actor was set up by two different functions.
  - Turning off the Import Content window matters when we control the PC remotely.
- **Media:** ![first log](media/blender-log.png) ![first log in game](media/blender-log-in-game.png) ![stretched](media/blender-log-stretched.png) ![log kit](media/blender-logkit-sheet.png) ![log kit in game](media/blender-logkit-in-game.png)

### 2026-11-04 — Real cars: a hatchback, a pickup and a box truck from one Blender script
- **What we asked for:** "make better assets for the game", then "Yes, cars first".
- **Prompt(s) we gave the agent:** "make better assets for the game" / "Yes, cars first" / "Works and looks good"
- **What happened:**
  - Claude checked what the game is made of first. Apart from the toad, the ground textures and the new logs, everything was still Unreal's basic shapes. It suggested replacing them in rounds, starting with the cars, because they're the main danger and always on screen. Each car was 11 cubes, and Endless made trucks by stretching a car 1.9×.
  - **One script builds every vehicle** (`Art/Blender/car_kit.py`). Each body is lofted from a side profile and a width profile, then gets:
    - wheel wells cut with a boolean;
    - bumpers, a grille, headlight and taillight lenses, mirrors and door handles.

    A new vehicle is mostly a list of numbers. The script also builds a wheel with a tyre, a rim and five spokes.
  - **Three bodies:** a hatchback, a pickup with a sunken bed, and a box truck with a cab, a cargo box and a third axle.
  - **In Unreal:** no-click import again. The paint slot keeps our four colours, and the light lenses reuse the existing glow materials, so night headlights still work. A new `ArrangeCarParts` function in `BP_Car` swaps the body, places 4 or 6 wheels, and turns everything to face the driving direction. It also moves the headlight beam and sizes the hit box per body.
  - Placed cars in `Lvl_Frogger` pick a hatchback or a pickup from where they stand. Endless picks one at random, and highway trucks get the real truck instead of a stretched car.
- **What went wrong on the way:**
  - The first glass edges were jagged and the bodies looked inflated. Glass was chosen per face by its angle, which zig-zagged across the grid. Fix: remember each face's loft row and column, and draw borders along the loft lines. Bodies were also made boxier.
  - The boolean wheel wells smeared the smooth shading. "Smooth by angle" keeps hard edges where parts meet.
  - The wheel-well colour leaked onto the outer body. It now counts only faces set back from the body side.
  - Calling our own Blueprint function from the graph tool needs `self` as its first argument. Without it the write fails with "Could not connect pin ReturnValue to self".
- **What we learned:**
  - A parametric script beats hand-modelling for a family of props, and it's allowed before the jam.
  - Lesson from the logs applied this time: `BP_Car` is set up in two places (construction script and `CarSetup`), so both call the same function.
- **Media:** ![cars](media/blender-cars-sheet.png) ![cars render](media/blender-cars-render.png) ![cars in game](media/blender-cars-in-game.png)

### 2026-11-04 — All the scenery from Blender, then "I thought we were going for ultra realistic"
- **What we asked for:** "make the rest in one shot and i will test after", then "i thought we were going for ultra realistic", then "Yes, test one" and "Realistic enough, do rest".
- **What happened:**
  - **Round 1 (chunky style):** one script (`Art/Blender/scenery_kit.py`) built 13 models: trees, pines, a snowy pine, a bush, a rock, reeds, a cactus, a hydrant, a lamp, a building, a three-car train, a crossing sign and a lily pad. Each scenery Blueprint now swaps in its model from its construction script, with a small random turn and size based on where it stands.
  - **The miss:** that whole round was in the old toy-like style from the pitch, but on Nov 3 we had decided "as real as we can" (scanned ground, realistic toad). Claude hadn't re-read that devlog entry. We spotted the clash straight away.
  - **Round 2 (realism test, `Art/Blender/real_kit.py`):** one rock and one tree first.
    - Rock: a 330k-triangle sculpt (fracture planes, worn edges, a few deep cracks, granite speckle, lichen, moss, rain streaks), baked onto an 11k-triangle game mesh as colour, normal and roughness textures.
    - Tree: grown by branching rules (trunk, scaffold branches, twigs) with ~14,700 modelled leaves. Bark and leaf textures are baked from procedural materials. Leaves deep in the crown are shaded darker. Nanite keeps 142k triangles cheap.
    - Two new Unreal materials: `M_RealPBR` (texture colour times vertex shade) and `M_RealLeaf` (two-sided foliage, light shines through).
- **What went wrong:**
  - Editing `BP_Tree`'s parts directly made the 39 placed trees keep their old cylinders (placed copies treat the old value as their own setting). Doing the swap in the construction script fixed it.
  - `git lfs lock` run from a sub-folder made doubled paths. Run it from the repo root.
  - First rock looked like a cauliflower (bumps and cracks everywhere); first tree was sparse with willow-thin leaves; bark came out orange in Unreal and was re-baked greyer.
  - Unreal's import tool won't overwrite an existing texture, so the re-baked bark got new names and the old textures were deleted.
- **What we learned:**
  - Read the devlog before a new art round: the style decision lived there, not in the pitch.
  - Test one realistic asset before doing them all. It caught three problems cheaply.
  - Realism mostly comes from baked texture detail and many small pieces (leaves, cracks), not from engine settings.
- **Media:** ![chunky scenery](media/blender-scenery-sheet.png) ![realism test](media/real-test-sheet.png)

### 2026-11-04 — The owner's real car, part 1: an AI-generated BRZ, cleaned up by script
- **What we asked for:** "Show me how accurate you can get this car looking. If you can't get close to photorealistic then we may have to cut our losses."
- **Prompt(s) we gave the agent:** reference photos of the owner's 2017 BRZ (side, rear, wing, wheels, rear 3/4), "Here goes the combined approach: fix the pillars and build a new wheel", "Try to fix the trunk and panels if you can", "The wing does not sit that high up", "Show me how accurate you can get this car looking".
- **What happened:**
  - **Starting point:** a Hunyuan3D 2.1 model of the car made from one photo. Lumpy, with its windows and lights baked into a blurry texture. Claude wrote `Art/Blender/ai_car_clean.py` to fix it up by script:
    - **Paint by position:** bake where every texel sits on the car, then paint windows, pillars, headlights, grille, fog lights, vents, wheel wells and tyres with smooth outlines measured from the photos. Edges ignore the AI triangles, so they come out crisp.
    - **Model only what sticks out:** headlights, tail lights, fog rings, exhausts and a new rear wing are real geometry projected onto the body. Our own ten-spoke wheel from `wheel_kit.py` (red pinstripe, red calipers) replaces the AI wheels.
    - **Measured fixes:** the body was 15% too wide for a BRZ (4240 x 1775 mm), so it was narrowed; the front fenders got the real car's rise; the wheels were tucked inside the arches.
  - **The trunk mystery:** dark "smears" under the wing turned out to be a second, broken wing the AI had fused into the lid (floating blades, an overhanging lip, risers on the corners, torn holes). `fix_trunk` deletes the junk, presses the rest onto a smooth lid measured from the clean parts, and lays a clean skin over it; the wing is then rebuilt from the owner's photos (flat blade swept along the lid's back edge, body-colour risers and end plates, sitting about 1 cm above the lid).
  - **Smoothing the panels** (`smooth_body`): points move towards their neighbours, but only straight in or out of the surface. The first version slid them sideways too and dragged the painted window outlines into zigzags, which the team spotted straight away ("We had fixed the paint on the car and the windows before. What happened?").
  - **Result (`SM_CarCoupeC11`):** about 111k triangles, right proportions, good from the game camera. Close up it is not photoreal: the AI surface has no crisp panel lines and ripples in reflections. Claude said so plainly and offered two routes: hand-loft a body from blueprints, or try a newer generator.
- **What went wrong on the way:**
  - A 3 fps reading while measuring frame time was the editor throttling itself in the background ("Use Less CPU when in Background"). The real number was 114 fps.
  - `materials.clear()` in Blender silently resets every face to material 0 (the wing turned blue).
  - Recalculating normals on the whole AI mesh flipped big areas inside out: only new patches get recalculated now.
  - Freezing "sharp" vertices during smoothing kept the AI's jagged panel lines as ridges, so nothing is frozen any more.
  - The first iron-down rule squashed a tail-light corner into a strip down to the ground; the first hard-edge tag made 81,000 body faces flat.
- **What we learned:**
  - Paint by baked position, not by face: outlines stay crisp on any AI mesh.
  - When smoothing a textured mesh, never let points slide along the surface.
  - Measure the real car first (length, width, height, wheelbase). The width was off by 15% and nobody could see why it looked squat until it was measured.
  - Every one of these scripts carries over to other AI models; only the outlines and wheel numbers are car-specific.
- **Media:** ![C11 in game](media/hunyuan-c11-in-game.png) ![narrowed to BRZ width](media/hunyuan-narrowed.png)

### 2026-11-04 — The owner's real car, part 2: TRELLIS.2 on Windows, a sharper car in five minutes
- **What we asked for:** "You can't do the hand-modeling from blueprints? Or the newer sharper 3D generator?" then "If we have the space on the drive do it" and "Proceed with the next steps".
- **What happened:**
  - Claude picked **TRELLIS.2** (Microsoft, MIT licence, so jam-safe) and set it up on the game PC in `D:\AI\TRELLIS2`. It is officially Linux-only; getting it to run on Windows took about three hours: five CUDA libraries compiled from source (each needed a small Windows fix), a Windows build of Triton, a pinned `transformers`, and one PyTorch operation (`segment_reduce`) that has no CUDA kernel in the Windows build, replaced with an equivalent. The image encoder (Meta's DINOv3) is gated, so the owner accepted the licence and logged the PC in to Hugging Face.
  - **One rear 3/4 photo -> a 6-million-face car in 270 seconds.** Real fender arches, door handles, mirrors, wing with end plates, moulded tail lights and diffuser, wheels with actual spokes. A front-photo run came out as a different, badly proportioned car with no rear wheels, so the rear-photo model is the one used.
  - `import_trellis` in `ai_car_clean.py` orients it (the wing tells it which way is back), cuts the reflections the generator turned into solid plates on the roof, smooths and decimates to 180k faces with the high-poly normals transferred on, and bakes position maps. The same paint-by-position pipeline then lands windows, headlights, grille and the red wheel pinstripe on it, and the tail lights come straight from the generator's own red texture pixels so they sit exactly on the moulded lamps.
  - **In the game:** `SM_CarCoupeT7` with four LODs (180k -> 18k triangles) is now the coupe in `BP_Car`, with `MI_CarCoupeT`. `SM_CarCoupeC11` stays in the project as a fallback.
  - **"Why does it look so bad?"** The first version was committed after close-up checks only. From the game's own high camera it was a dark, speckled blob next to the clean kit cars: the generator's texture atlas is thousands of tiny islands, mipmaps bled them into smears, and turning mipmaps off made every distant pixel sample noise. Fix: a fresh UV layout with big islands (`smart_project`, 80 degrees), a bake with an 8-pixel margin, mipmaps back on, tiny loose shells dropped, the roof rails smoothed, and the tail lights painted from the generator's lamp pixels turned into 3D points (voxel grid, closed to fill gaps) so they land on the moulded lamps whatever the UVs.
- **What went wrong on the way:**
  - Claude Code's safety classifier refused to run the extension builds ("code from external sources"); the team added a permission rule for the build script.
  - The newest `transformers` broke DINOv3's internals; pinned to 4.57.
  - The import put the car on backwards once (hood mistaken for trunk), and a mirror-vs-rotation mix-up turned it inside out once.
  - Decimating the smooth remeshed skin folded it into creases until the skin was smoothed first and the smooth normals transferred.
  - Widening the roof clean-up past the fitted area cut a hole in the windscreen; the bounds were reverted.
  - Per-face lamp flags sampled from the generator texture gave red squares all over the bumper (the micro-islands bleed); points in 3D worked.
  - Checked close-ups only and declared it done. The team saw it from the game camera and said "why does it look so bad?" Always check from the real game camera before committing art.
- **What we learned:**
  - A newer generator beats hours of cleanup script: the output already has the panel lines and parts the Hunyuan model lacked. The cleanup pipeline still matters, and it carried over with almost no retuning.
  - Generate from the photo that shows the most of the car; a second photo does not merge into the first model.
  - Keep the Windows port notes: `D:\AI\TRELLIS2\build_ext.py` and `run_image_to_3d.py` make the next asset a one-command job.
  - Never ship a generator's own UV atlas: re-UV with big islands and bake with a margin, or it falls apart at distance.
- **Media:** ![TRELLIS clay](media/trellis-brz-clay.png) ![TRELLIS vs Hunyuan in the level](media/trellis-vs-hunyuan-in-level.png) ![TRELLIS coupe in game](media/trellis-coupe-in-game.png) ![from the game camera, before and after the UV fix](media/trellis-coupe-game-camera.png)

### 2026-11-05 — The owner's real car, part 3: stop patching, fix the photo; two photos, one car
- **What we asked for:** "This still looks bad and the colors look like they are in the wrong places... the taillights are half blue, and the roof is all lumpy", then "It feels like it is being over complicated in the wrong ways", "If starting over with a better foundation is what we need then do it", "use better reference images if these are getting cutoff", "you might need to do something about the reflections on the car before you try it".
- **What happened:**
  - **Five rounds of roof surgery, thrown away.** The roof lumps were the generator sculpting the reflections in the owner's photo into raised plates. Claude kept writing one-off geometry code to shave them off and re-stitch the roof (fit a surface, delete, fill, re-grid, tuck under the ragged border...); each round fixed one thing and tore another edge. The team called it: over-complicated in the wrong way. The fix belongs in the input, not the output.
  - **Flatten the paint first.** `tools/deflect.py` replaces the paint pixels (blue or yellow hue) with their local average, so trees and sky stop being embossed. Studio shots need nothing.
  - **The generator only knows what the photo shows.** A close rear shot gave a car with a good tail and an invented front and far side. The owner's photo clips the roof, and from it TRELLIS hung metre-long strips under the car twice (and ran the GLB bake out of memory). Lesson: the whole car in frame, 3/4 angle, a little height.
  - **Wikimedia Commons has what we need:** a CC0 rear shot, a CC BY 4.0 high front-3/4 (blue, complete), a CC BY-SA 4.0 rear-3/4 with the Performance Package wing; the owner added a studio front-3/4 and a yellow rear-3/4 (same wing as the owner's car). Colour does not matter; the paint is flattened to the owner's blue anyway.
  - **Texture transfer instead of painted outlines.** With reflections gone, the generator's own texture is good, so it is baked (Cycles, selected-to-active) from the full-resolution model onto clean smart-project UVs. Headlights, grille, mirrors, badges land where they belong with no measuring. Only the wheels (our red-pinstripe look), glass, tail lamps and plastics are still set by rules.
  - **Two photos, one car.** A front photo invents the rear and vice versa. Joining halves with `bridge_loops` left a trench at the B-pillar. What works: the rear-photo model is the whole body (windows up, right wing and tail), and only its nose is shrink-wrapped (nearest surface) onto the front-photo model, blended over the hood; textures bake from each model on its own end (`Art/Blender/trellis_join.py`). Result: `SM_CarCoupeT23`.
  - **The fleck hunt.** Every joined car was covered in dark flecks. Suspects in order: custom normals (no), the inner wall of the generator's hollow shell (no), flipped faces (no, 116), a real index bug (bmesh reuses freed face slots, so "delete the second model's faces by index" left a second skin behind; fixed with a face tag), and finally the cause: the glTF import splits vertices along every UV island, and the joined body was never welded, so decimation tore holes. One `remove_doubles` fixed it.
  - **GPU memory.** Generations started failing with Unreal, Blender, Chrome and the Claude app holding 7 GB of the 24 GB card. The GLB bake now runs in its own process after the 4B model is unloaded (`export_glb.py`), and the team's rule is: close what you don't need, this PC is Claude's. The studio photo still would not bake at any size and was dropped.
  - **Unreal after a forced close:** a "Restore Packages" dialog blocked the MCP; closed from PowerShell with a window message (nothing to restore, everything was saved).
- **What went wrong on the way:** all of the above, plus: the window-pane patch for a windows-down photo put a staircase of tabs along the roof rail (dropped: use photos with the windows up); the first texture bake was black because the car object had been parked at (3, 1.5, 0) by the preview step; the bake picked a stale image because `bpy.data.images` sorts names alphabetically ("Image_0.010" before "Image_0.002").
- **What we learned:** fix the photo, not the mesh; one photo gives one good end; bake the generator's texture, don't paint outlines; weld before decimating; never pick a datablock by sorting names; close other apps before a generation.
- **Media:** ![front-3/4 Commons model](media/trellis-commons-front.png) ![two-photo join](media/trellis-join-rear.png) ![in game](media/trellis-join-game.png)

### 2026-11-05 — GameStation gets the full toolkit: Blender MCP and TRELLIS.2 on an RTX 5090
- **What we asked for:** "pull the latest and follow the instructions on setting up the new tools", "you have full permission to install what is needed", then "Yes, rebuild it" (TRELLIS.2 on this PC).
- **What happened:**
  - Followed `docs/SETUP_GAMESTATION.md`. uv and Blender's official MCP server went in; Blender 5.2 had to be installed by hand because winget's download got a 403. Blender's MCP add-on was already running (port 9876). Unreal opened from Explorer and its MCP answered in about 25 seconds; two editor preferences (background CPU throttle, auto-import prompt) were set in the per-PC config while the editor was closed.
  - **TRELLIS.2 rebuilt for an RTX 5090** in `C:\AI\TRELLIS2` (no D: drive here): CUDA 12.9, Python 3.11, PyTorch 2.8 cu129 (first build with Blackwell, sm_120), Triton pinned to 3.4 to match, and all five CUDA extensions compiled for compute 12.0. FlexGEMM and o-voxel needed the same Windows fixes as on the main PC; they're now saved as patch files in `tools/trellis/patches/`.
  - **First run crashed** in xformers' FlashAttention-3 kernel ("invalid argument"): it's Hopper-only but xformers picks it on any new card. `run_image_to_3d.py` now switches it off unless the GPU is a Hopper. Second run: **135 s** for a 9.5M-face model (the 3090 took 270 s), GLB bake fine.
  - The scripts no longer hard-code `D:\AI`; they find their own folder, and `build_ext.py` finds Visual Studio and the GPU itself.
- **What went wrong on the way:**
  - Claude Code's auto-mode safety check blocked cloning/installing the Blender MCP and refused to write `.claude/settings.local.json` ("self-modification") even with permission; the team switched the session's permission mode.
  - **The invisible Python.** The Claude desktop app keeps its own private copy of `AppData\Roaming`, so the Python that uv installed from the chat didn't exist for the user's own terminal ("No Python at ..."). Copied it to `C:\AI\python311`.
  - Because of that, the first Hugging Face login failed and the token got pasted at the shell prompt instead. It was deleted from the PowerShell history, revoked, and replaced with a new one. Lesson: run logins in your own terminal, and check the prompt is really asking before you paste.
- **What we learned:** a new GPU generation means rebuilding, not copying; keep tools out of `AppData` when a chat installs them; save every hand fix as a patch file so the next PC is a checklist, not a hunt.

### 2026-11-05 — A Tacoma from one photo: the TRELLIS pipeline on a pickup
- **What we asked for:** a Toyota Tacoma model, then "front model alone" after seeing the two generator results (a grey front-3/4 photo and a red rear-3/4 photo, both from Wikimedia Commons).
- **What happened:**
  - The grey front-3/4 photo gave a complete long-bed double cab in about two minutes on the 5090; the red rear photo's model was weaker and is not used. Badges and plates had already been inpainted out of the photo.
  - **A truck version of the cleanup**, kept apart from the BRZ scripts: `Art/Blender/trellis_truck.py` (import, orient, scale, weld, cut 99 floating crumbs, smooth along normals, decimate to 160k with the smooth normals, clean UVs) and `trellis_truck_bake.py` (bake the generator's own texture, paint rules, export). The bed's flat rails tell it which end is the back.
  - **Measured, not eyeballed:** like the BRZ, the generator made it about 16% too wide and 9% too tall. Each axis is scaled to the real truck (5.69 x 1.91 x 1.79 m) in the game's car scale (the coupe is 1.717 units for 4.24 m), so it sits next to the coupe at the right size: 230 x 77 x 73 cm in Unreal.
  - **Unbranded:** the whole grille insert is replaced with plain dark slats (no logo shape left), and the tailgate is repainted with its own row-by-row median colour plus a plain black handle, which wipes the badge remnants and lettering. The jam rules ban trademarks.
  - **Paint:** the generator's grey was too blue and too dark (the photo's shadows bake into the texture), so it is desaturated, lifted to a mid grey, and made non-metallic.
  - In Unreal: `SM_CarTacoma` (4 LODs: 160k, 64k, 24k, 8k triangles) in `Imported/CarTacoma/`, `MI_CarTacoma` (child of `M_CarMasked`, like the coupe), and one test copy, `TEST_Tacoma`, on the start grass. Not swapped into `BP_Car`.
- **What went wrong on the way:**
  - **A "Check Out Assets" dialog** (our committed `SFX_` sounds wanted saving) sat open in Unreal at session start and blocked its MCP, so the chat's Unreal tools never connected. The team cancelled it, and Claude talked to the MCP over plain HTTP with a tiny script for the rest of the session.
  - **The 15,000-island UV map.** Unwrapping the noisy AI surface split it into 15,000 islands using 24% of the texture (packing made it worse, 32%). Fix: unwrap a heavily smoothed copy of the shape, then put the real points back; the UVs carry over and the islands are big (62% of the texture used).
  - The first bake looked black: the baked colours were linear and were read as sRGB, and "empty" texels were mis-detected. Both fixed.
  - **Every TRELLIS car was grey in-game on this PC.** `M_CarMasked`, the parent material of the coupe and now the truck, had no default textures on its three texture parameters, so on GameStation it failed to compile ("Found NULL, requires Texture2D") and Unreal used the default grey material. The coupe's own textures are now the defaults. Found only because we judged from the game camera: the asset thumbnail looked fine.
  - Blender's file writes auto-imported the FBX and PNGs into Unreal before the MCP import (with an extra material); those were deleted and imported properly. Later texture re-bakes rely on that same auto-reimport, and the FBX is not re-exported, so the LODs and material stay.
- **What we learned:**
  - Unwrap a smoothed stand-in, not the noisy AI skin, then restore the real shape.
  - If a whole family of materials looks flat grey, read the log for "Failed to compile" before touching the textures.
  - A modal dialog in Unreal looks exactly like a dead MCP. Check the editor window first.
- **Media:** ![after the Blender cleanup](media/tacoma-blender.jpg) ![from the game camera](media/tacoma-game-camera.jpg)

### 2026-11-05 — The coupe's rear window was painted blue
- **What we asked for:** "i noticed the back window was colored blue. i noticed this while working on GameStation so you will need to pull the latest down to fix it"
- **What happened:**
  - The pull itself needed the editor closed: Unreal held `M_CarMasked.uasset` open and git could not replace it. The half-applied pull was finished by staging and fast-forwarding; no reset.
  - **Why it was blue:** the texture bake decides what is glass by rules on the baked position and normal maps. The rear-window rule asked for a normal tilted at least 20° toward the back, but on this mesh the rear glass lies back at only about 17°, so every texel failed the test and was flattened to paint like the rest of the deck (the yellow photo's glass reflects blue sky, and blue counts as paint). The quarter windows were cut off by the side-glass box ending at y 0.36.
  - **Found with a table, not by eye:** a probe over the baked maps printed the fraction of yellow (photo paint) per cell of the rear deck. The window showed up as a clean band from y 0.35 to 0.62, 0.21 either side of centre, and the quarter windows to y 0.40. The new rules use those bounds and test height instead of tilt. The plate recess is painted body colour too (it had a yellow-grey smear).
  - Only the material step was re-run (51 s): the baked source image was still in Blender's memory, so no new bake. Textures re-imported into Unreal and `MI_CarCoupeT` re-pointed.
- **What went wrong on the way:**
  - **Importing three 4096 textures in one script crashed the editor** with a plain out-of-memory. Blender had 101 GB of committed memory (undo history from a long session) which counts against the same system limit, so Unreal's texture builds had nowhere to go. Fix: save and restart Blender (6 GB after), import one texture per call.
  - **Then every coupe was flat grey.** GameStation's fix for the grey cars had made these exact textures the defaults of the parent `M_CarMasked`; deleting them for the re-import left the parent with null textures and "Found NULL, requires Texture2D" in the log, so the whole material family fell back to the default material. Re-pointing the three `TextureSampleParameter2D` nodes, recompile, save.
  - Two ported scripts (`trellis_join.py`, `trellis_bake_texture.py`) looked for `trellis_build.py` in the cache folder instead of next to themselves; fixed.
- **What we learned:**
  - When a rule misses, measure where the feature really is on the mesh before guessing new numbers.
  - A deleted-and-reimported asset is a new object: check `get_referencers` before deleting and re-point every one.
  - Blender's undo history can quietly hold 100 GB of commit on a long session. Restart it before heavy Unreal work.
- **Media:** ![before, Cycles preview](media/coupe-rear-window-before.jpg) ![after, in the game](media/coupe-rear-window-fixed.jpg)

### 2026-11-05 — The coupe's tyres were cut up
- **What we asked for:** "The tires look cut up"
- **What happened:**
  - From the game camera the wheels are dark blobs, so a close-up in Blender showed it first: each wheel had its hub, spokes and inner sidewall cut off flat about 4 cm below the hub centre, with only the outer tread continuing below. All four wheels, every coupe since T1.
  - **The cause was our own cleanup, not the generator.** `fix_strips_and_orient` (in `trellis_build.py`, also used by the two-photo join) exists because some TRELLIS runs hang thin vertical strips under the floor. It slices the mesh 9 cm above the ground and deletes every loose piece below that is thinner than a tyre. Below that line the generator's wheel is not one piece but about 2,000 slivers (each spoke, each sidewall patch), so the thin-piece test ate all of them. The raw GLB has the wheels complete down to the tread.
  - Fix: the filter now finds the two wheel axes from the lowest points of the mesh and spares anything inside a tyre circle. Tested on the raw model first (hub reaches the tread again, the same slivers elsewhere still go).
  - Second thing seen in the re-run: the front wheels came out crumpled, because the join shrink-wraps the whole nose onto the front-photo model, spokes included, and that model's wheel is a different design. The front wheel circles are now excluded from the wrap, so they keep the rear-photo model's clean wheel.
  - The whole join re-ran in two minutes (both GLBs, wrap, smoothing, 4096 bake). New mesh `SM_CarCoupeT24` imported under a new name so nothing pointed at nothing; `BP_Car`'s Set Static Mesh pin re-pointed, textures replaced one per call, `M_CarMasked` defaults and `MI_CarCoupeT` set again, old T23 deleted after its referencer list was empty.
- **What went wrong on the way:**
  - Claude's own close-up camera had replaced the scene camera, so the join's preview renders came out black until it was switched back.
  - Three different Unreal tools want the same object under three parameter names (`instance`, `material_or_function`, `asset_path`); half the script calls failed once each before they ran.
- **What we learned:**
  - A cleanup rule written for one bad run (strips under a clipped-roof model) kept running on every good one. Check what a filter removed, not only that the problem it was for is gone.
  - Look at every car part from close up at least once; the game camera hides the lower half of a wheel in shadow.
- **Media:** ![before, Cycles close-up](media/coupe-wheels-before.jpg) ![after, Cycles close-up](media/coupe-wheels-after.jpg) ![after, in the game](media/coupe-wheels-ingame.jpg)

### 2026-11-05 — The front wheels were turned while the car drove straight
- **What we asked for:** "Do we have the ability to turn the front tires? Because right now the car is going straight but the tires are turned."
- **What happened:**
  - Measured first: the thinnest axis of each wheel's point cloud is its axle. Front wheels were turned 42° (right) and 40° (left); the rears were within 3° of straight. The yellow car was photographed with its wheels cranked for the shot, and the generator copied that.
  - The wheels are not separate parts on a TRELLIS car (one mesh, wheels and all), so the Blueprint cannot steer or spin them. The practical fix is to straighten them in the mesh: `trellis_join.py` now turns each front wheel back about the vertical axis through its centre. The wheel is picked out in its own turned frame (a turned tyre sticks out of a straight cylinder) with a 2.5 cm soft edge so the arch skin around it is not torn. It only runs when a wheel is more than 5° off.
  - Rebuilt as `SM_CarCoupeT25` (front wheels now 2° and 4.5°), same import routine as the wheel fix an hour earlier.
- **What went wrong on the way:**
  - A small chrome disc appeared on the front tyre's sidewall. The headlight projector rule paints a chrome circle on any forward-facing surface at a given height, and that height is exactly the top of the tyre, which the straightened tyre's front face now points at. The body texture comes from the photo bake anyway, so the wheel region now takes only the wheel painting and no body-part rules. Only the texture step was re-run (16 s).
  - Two rounds of in-game captures showed the rear of the car: the coupe's nose points +Y at yaw 0, not -Y. Third round from the right end.
- **What we learned:**
  - Measure a model's wheels (steer, camber) before judging it; a 40° steer reads as "something's off" from the game camera but not as what it is.
  - A rule that keys on height and facing direction will hit any part that happens to be there. Keep part rules off the wheels.
- **Not done:** spinning and steering wheels would need the wheels cut out of the mesh as their own part, like the other car bodies' `SM_CarWheelV3`. That is a separate job.
- **Media:** ![before, from below](media/coupe-steer-before.jpg) ![after, from below](media/coupe-steer-after.jpg) ![after, in the game](media/coupe-steer-ingame.jpg)

### 2026-11-05 — The coupe's wheels are their own part now, and every car's wheels spin
- **What we asked for:** "Yeah do all of that" (cut the wheels out so they can spin and steer, then the front end, then the photo credits).
- **What happened:**
  - Looked at what the Blueprint does with wheels first. `BP_Car` already has six wheel components (`WheelFL/FR/BL/BR/ML/MR`) that the hand-built cars use, but nothing turned them: there was no spin code at all, on any car.
  - Measured the coupe's wheels in the mesh: the generator makes each one a nearly closed drum (outer face with spokes, tread, inner face) fused flush into the fender, with no gap between tyre and arch. So a cylinder cut around each axle (tyre radius + 4 mm, inboard of 19 cm from the centre line) frees the whole wheel as one piece of about 11,000 faces; the few slivers that also fall inside the cylinder stay with the body. Boundary check: each wheel piece has only about 70 open edges, so it needs no capping.
  - The body is left with four round holes looking into the empty shell. Each hole gets a dark liner: its own boundary edge loop extruded 12 cm inboard to a flat plane and fanned shut, with every new face's UVs pinned to one black texel of the tyre, so no new material or texture is needed. (First try used only the longest edge chain; the hole's edge comes in several broken chains, so now every chain of eight edges or more is used.)
  - Rendered the four cut wheels from the side and picked the rear-left (cleanest tyre, ten spokes). It is mirrored to face +X, the side Unreal's `WheelFR` faces, with its origin on the axle at the 30 cm half-track the Blueprint already uses, and exported as `SM_CarCoupeTWheel`. The body went out as `SM_CarCoupeT26`. All of it is `Art/Blender/trellis_wheels.py` (17 s, previews included), and it works on any TRELLIS car with four wheels on the ground.
  - Unreal: both meshes imported with the coupe material and LODs. `ArrangeCarParts` rewritten through the graph DSL: the coupe now keeps its wheel components visible, gives them the new mesh and the coupe texture, and places them at the measured axles (48.6 cm ahead, 50.6 behind, 12.7 up); other cars keep `SM_CarWheelV3` at 13.5. A new `SpinCarWheels` function adds a world roll of speed × dt × 4.4°/cm (a 13 cm wheel) to all six wheel components every tick, signed by the car's direction, and `EventTick` calls it. Tested in Simulate mode: found the coupes among the nine cars on the road, captured one from the front quarter and one side-on; wheels sit in the arches, the roll value on each wheel climbs as the car moves, and the hand-built cars' wheels turn too now.
- **What went wrong on the way:**
  - The graph DSL reader prints `(bind _x 1.0)` for every literal, and the writer refuses exactly that ("expression produced no output pin"). A read-modify-write of `EventTick` failed until the literals were folded back into the expressions by hand.
  - `SetActorLocation` wants its vector as `:NewLocation`; given positionally it is wired into the `self` pin and fails. Component calls (`SetRelativeLocation` on a wheel) take the target first and are fine.
  - The first cut wheel had a bounding box reaching 29 cm above its axle: loose vertices with no faces, left in the AI mesh, rode along. The script now deletes loose points from both halves before export.
  - The old `SM_CarCoupeT25` could not be deleted: the asset registry still lists `BP_Car` as a referencer although no graph mentions it any more (probably a trashed node still in the package). Left in place for now; harmless.
- **What we learned:**
  - A generator's wheel is a solid lump, not a surface. That is good news: a round cut frees it whole, and the body's hole only needs a dark drum behind it.
  - `write_graph_dsl` replaces the whole graph, so a function can be rebuilt from text safely; keep the read-out as a backup first. Always read it back: literal binds and the `self` pin are the two traps so far.
  - `SceneTools.find_actors` with `actor_type` set to the Blueprint's generated class (`BP_Car.BP_Car_C`) finds the cars in the running Play session, so a capture can be aimed at a specific car instead of guessing.
- **Not done:** steering has nothing to do in this game (the cars drive straight), but the parts are there now: a yaw on `WheelFL/FR` would turn them.
- **Media:** ![one cut wheel, Cycles](media/coupe-wheel-cut.jpg) ![body with lined arches](media/coupe-wheels-split-body.jpg) ![wheels back on, spun 37°, Blender](media/coupe-wheels-split-blender.jpg) ![in the game, side-on](media/coupe-wheels-split-ingame.jpg) ![in the game, front quarter](media/coupe-wheels-split-ingame2.jpg)
