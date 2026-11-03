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
