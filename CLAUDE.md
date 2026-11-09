# Project notes for Claude Code

## Read these first
- `docs/PLAN.md` — the team plan, schedule, and rules of thumb
- `docs/PITCH.md` — the game we're making (filled in after the theme reveal)
- `docs/RULES.md` — the official jam rules we must follow
- `CREDITS.md` — every asset we didn't make ourselves

## Who we are
- A team of up to 5 (the jam's limit) entering the 2026 Epic AI MegaJam (Nov 12-15). Each teammate works on their own
  PC, with their own GitHub account and their own Claude account. Team list and who owns what: `docs/TEAM.md`.
- **This repo is our practice/setup sandbox, not the jam entry.** We're learning the tools and running practice jams here.
  When we discover a better way to work, suggest updating this CLAUDE.md so the improvement carries into the real jam repo.
- We are beginners: we play a lot of games but have little coding or Unreal experience.
- We act as game designers and testers. You do the implementation.

## Engine and project
- Unreal Engine 5.8, connected to you through Epic's Unreal MCP plugin.
- C++ project, but build gameplay in **Blueprints** unless C++ is truly required. Ask before writing C++.
- Target platform: Windows.

## Which computer am I on? (check at the start of every chat)
Run `hostname` and find this computer's row in the **Computers** table in `docs/TEAM.md`, and do only what its role allows:
- **builder:** the only role that saves or commits Unreal files (`.uasset`, `.umap`) and publishes test builds. Work on
  the `playtest` branch; merge into `main` when testers confirm (`playtest-issues` skill). `builder (Area)` = only that area.
- **maker:** Blender, Meshy, TRELLIS, sounds, scripts. Never save in Unreal, even if it's open: hand the files to the builder.
- **tester:** help play, file and check issues (`docs/PLAYTEST.md`). If Unreal is open to play, never save in it.
- Any role may edit docs and scripts.
If asked to do something the role doesn't allow, say which computer is the builder and offer to file an issue or hand it
over instead. If the user wants to change roles, edit the table, commit and push (`pc-handoff` skill when the builder
moves). If no row matches `hostname`, ask which computer this is and fix its name in the table.

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

## Skills (`.claude/skills/`)
Step-by-step checklists Claude loads when a task matches (or type `/<name>`). Use them; update the skill when we
learn something, and copy it into the jam repo (the bootstrap does). Allowed before the jam: they're prompts (§7h).
`unreal-blueprint`, `asset-import`, `trellis-model`, `make-sound`, `playtest-capture`, `package-build`,
`playtest-issues`, `devlog-entry`, `pc-handoff`, `jam-rules-check`.

## Lessons from practice (Unreal + MCP)
- **Lock before you edit.** Git LFS marks committed `.uasset`/`.umap` files read-only. Run `git lfs lock <file>` before changing
  an asset that's already committed, or the editor's save silently does nothing. After pushing, `git lfs unlock <file>`.
  Check `git status` after saving to confirm the file really changed.
- `Content/Game/` on disk is `/Game/Game/...` inside Unreal (and in MCP tool paths).
- A child Blueprint's input event does **not** replace the parent's. To stop the template character walking, override the
  parent's `Move` event with an empty one in the child.
- Claude can't send keyboard input into Play mode, so it can check that things compile and spawn, but **we** test movement and feel.
- The Blueprint graph tool (`write_graph_dsl`) can't attach code to Enhanced Input events or create Timelines. Put logic in a
  function, then wire the input event to it by hand; use Event Tick instead of a Timeline.
- **Never edit while Play mode is running.** Stop PIE first. Creating or editing Blueprints during PIE froze the editor
  for good and lost all unsaved work. Also **save after every batch** of changes, not at the end.
- Reset the input mode to "game only" when a level starts; "UI only" from an end screen survives a level reload.
- After deleting a Blueprint function, compile before re-adding one with the same name, or it becomes `Name_0`.
- Changing a Blueprint's components doesn't always update copies **already placed in the level**. After a component
  change, check one placed copy; if it's stale, re-place the actors (keep their transforms and settings).
- Blueprint "pure" nodes re-run every time they're read. Don't `bind` a value, then set the variable it came from and read
  the bind again (the goal count got +1 twice). Read the variable after setting it instead.
- Batch many MCP calls into one `execute_tool_script` (sandboxed Python) to save round trips. Don't `time.sleep` inside
  it; that freezes the game thread. Wait outside instead.
- With "prompt before auto-importing" off (Editor Preferences > Loading & Saving), `.wav` files dropped into or changed in
  `Content/` import by themselves within seconds, even while the editor is open. Save the new asset afterwards.
  `tools/make_sfx.py` generates our sounds and music from code: no downloads, no credits needed.
- Night scenes need fixed exposure (post-process Metering Mode = Manual), or auto-exposure brightens night back to day.
- **Lock new assets right after their first commit.** Committing makes them read-only, and the next save fails silently.
- `set_actor_transform` resets any part you leave out (location, rotation or scale). Always pass the full transform.
- When two engine classes share a node name (e.g. Set Volume Multiplier on Audio vs Synth components), the DSL may pick
  the wrong one. Write it, then use `retarget_node_class` and reconnect its pins.
- Give every Blueprint function a name that is unique across the engine **and** our project (not Clear, SetTime, or a
  second `SpeedUp`). Otherwise the graph tool quietly calls the wrong one and it still compiles. Always `read_graph_dsl`
  after writing to check what was really built.
- `write_graph_dsl` replaces the whole graph (good: a function can be rebuilt from text; read it out first as a backup).
  The reader prints literals as `(bind _x 1.0)` and the writer rejects exactly that: fold literals back into the
  expressions. Actor calls like `SetActorLocation` need `:NewLocation value`; a positional arg lands in the `self` pin. Same for `SetActorRotation` (`:NewRotation`). The reader prints a `b`-bool variable as `(|GetbIsHopping)`, but the writer needs `Variables|Default|GetIsHopping` / `SetIsHopping`.
- In Play mode, `SceneTools.find_actors` with `actor_type` = the Blueprint's generated class (`BP_Car.BP_Car_C`) lists the
  live actors, so captures can be aimed at a specific car.
- Never write `(return (SomeFunction ...))` with one of our own Blueprint functions inside. It compiles, but the call never
  runs and the return gives the default (0 / false). `bind` the call first, then `(return value)`. This made every endless
  row count as grass (checkpoints on roads) and switched off obstacle blocking.
- **Importing images and models:** save the file into `Content/Game/Imported/<Name>/`, then import it with the MCP's
  `StaticMeshTools.import_file` / `TextureTools.import_file`, which never open a window. Files dropped in also import by
  themselves: `Config/DefaultEngine.ini` sets Interchange's `bShowImportDialog=False` (read at editor start); without it an
  `.fbx` opens an "Import Content" window that freezes the MCP until a human clicks, so we can't answer it remotely.
  Re-importing a mesh resets its materials, so don't re-import once it's set up.
  **Never delete the source file afterwards:** Unreal opens a modal "Delete Assets" dialog that freezes the MCP until
  someone answers it (Escape = keep the assets). Raw sources under `Imported/` are gitignored instead.
- **GLB files** (TRELLIS.2, Pixal3D, Meshy): auto-import ignores `.glb`, and `StaticMeshTools.import_file` only takes
  FBX/OBJ. Run `tools/glb_for_unreal.py` (PNG textures, real size), then type
  `py <repo>/tools/unreal_import_glb.py <dest folder> <file.glb>` into the editor's console box with the Slate inspector
  (`Observe` the window and `Click` the box first, or `Type` returns false). It imports through Interchange, which keeps
  the glTF PBR material, and switches Nanite off through `StaticMeshEditorSubsystem.set_nanite_settings`: setting the
  property alone left Nanite's fallback mesh, a fifth of the triangles.
- **Meshes that rely on vertex colours** (flowers, leaf shading from our Blender kits): `StaticMeshTools.import_file` uses
  the old FBX importer with vertex colours set to Ignore, and that can't be changed. Copy the `.fbx` into
  `Content/Game/Imported/<Name>/` instead and let Interchange import it by itself (it keeps vertex colours). Afterwards:
  re-point the slots at our materials, delete the empty placeholder `M_*` materials it makes, and **switch Nanite off**
  (`set_nanite_enabled false`). Interchange turns Nanite on, and its simplified mesh drops thin parts like petals.
  Check with `get_triangle_count` that the full count is back.
- A `.png` that Unreal refuses with "produced no assets" may really be WebP (TRELLIS GLBs pack WebP). Check the first
  bytes (`RIFF....WEBP`) and re-save it as a real PNG.
- Fab in Claude's browser pane: the user signs in there once (the launcher login doesn't carry over). Free items still
  need "Add to My Library" and a one-time EULA; Megascans surfaces are free, but many Megascans 3D models are not.
  Downloads land in `~/Downloads` as `<guid>.tmp` zips; identify them by their contents.
- **Packaging a Windows build:** run `tools/package_build.ps1 [-Game Name] [-Run] [-CopyTo <folder>]`. It cooks the start
  map (`GameDefaultMap`) plus every map under `Content/Game/`, zips `Builds/<Team>_<Game>.zip` for itch.io, checks the
  1 GB limit, keeps the `.pdb` debug symbols out of the zip (`Builds/Symbols/`), and `-Run` checks the game launches.
  Works with the editor open (don't save while it cooks). What it handles for us:
  - Our editor plugins (MCP, toolsets) make Unreal build a game program of the project's own, even with no C++.
    `Binaries/` isn't in Git, so the first package on each PC compiles it (about 20 s); later runs reuse it.
  - `-nocompileeditor`: without it, `-build` also rebuilds the editor, which fails with the editor open and needs the
    .NET Framework SDK (not installed on GameStation). `-unrealexe=UnrealEditor-Cmd.exe` avoids the missing
    `<Project>Editor.target` error during the cook.
- Turn off "Use Less CPU when in Background" (Editor Preferences) so Play mode runs at full speed while Claude tests it.
  In a project's files it belongs in `Config/DefaultEditorSettings.ini`, not `DefaultEditorPerProjectUserSettings.ini`
  (the bootstrap script does this, and its `-Verify` reads it back from the running editor).
- To pass a per-actor number to a material (e.g. how often the log bark repeats), use a Scalar Parameter with
  "Use Custom Primitive Data" and set it with `SetDefaultCustomPrimitiveDataFloat`. The runtime `SetCustomPrimitiveDataFloat`
  doesn't stick when the editor runs a construction script. Every mesh using that material needs a value, or it reads 0.
- One Blueprint can be set up in more than one place. `BP_Log` is built by its construction script (placed logs) **and** by
  `LogSetup` (Endless spawns). Search for every caller before changing how an actor looks, and test both maps.
- `mcp__unreal__call_tool` needs `toolset_name` **and** `tool_name` (e.g. `EditorToolset.EditorAppToolset` / `StartPIE`).
- `ObjectTools.get_properties` takes exact property names only. `list_properties` returns a JSON schema, not a list:
  never turn its text into names by string-splitting. A 2,000-character "name" hit Unreal's 1,023-character FName
  limit and crashed the editor (assertion in UnrealNames.cpp). Save before any exploratory call during PIE.
- The frog's `CameraBoom` has Inherit Yaw off (that keeps the camera north while the frog turns). A spring arm
  with Inherit Yaw off ignores its world rotation's yaw and uses its *relative* yaw, so turn it with
  `SetRelativeRotation`, not `SetWorldRotation`. Debug camera problems with `CaptureEditorImage` during PIE: the
  variables can all look right while the picture shows the camera never moved.
- Measure frame time with the console commands `startfpschart` / `stopfpschart` (type them into the console box with the
  Slate inspector, read the result from the log). The `stat unit` overlay never shows in `CaptureEditorImage`. If it reads
  3 fps, the editor is throttling in the background: `bThrottleCPUWhenNotForeground` must be false.
- `TextureTools.import_file` / `StaticMeshTools.import_file` never overwrite: delete the old asset first, or use a new name.
  Deleting leaves every referencer pointing at nothing: run `AssetTools.get_referencers` first and re-point each one
  afterwards. `M_CarMasked` uses the coupe textures as its parameter defaults, so after a texture re-import its
  three `TextureSampleParameter2D` nodes need the new textures set (`ObjectTools.set_properties` `Texture`), then
  `MaterialTools.recompile` and save, or every car on it turns default grey ("Found NULL, requires Texture2D").
- Import 4096 textures one per call. Three in one script crashed the editor with a plain out-of-memory: each build
  needs about 1 GB, and a Blender that has run a long session can hold 100 GB of committed memory (undo history)
  that counts against the same limit. Save and restart Blender before heavy Unreal work; its MCP add-on autostarts.
- To get the real game lighting in a capture, `StartPIE` in Simulate mode, click the editor's Pause button via the Slate
  inspector, then `CaptureViewport` with a camera transform; `CaptureEditorImage` shows the game camera as the player sees it.
- Save captures without pulling the picture through the chat: inside `execute_tool_script`, write the capture's base64
  `data` to a `.txt` under `Saved/` with `AssetTools.write_file`, then decode it in PowerShell. `CaptureViewport` needs
  `captureTransform` and an all-zero `annotations` even when they're unused; `CaptureEditorImage` comes back 1280 px wide.
- Check the game's scale before comparing art with it. The practice city is built at **0.405**: the pedestrians' Man and
  Dog meshes are scaled 0.405 and the car meshes are modelled small (the RAV4 is 186 cm long).

- **Never click the editor's "N Unsaved" button** through the Slate inspector: it opens a modal Save Content window
  that freezes the MCP. Save with `AssetTools.save_assets`. (Escape it: find the window from PowerShell and send Enter.)
- `AssetTools.delete` on a **folder** also deletes the source files on disk inside it (a texture's `.png`).
- `ObjectTools.set_properties` on a placed actor doesn't mark the level as changed, so saving writes nothing. Re-set the
  actor's full transform afterwards, then save and check `git status`.
- To test untested `.uasset` work on another PC, push it to a branch (`<name>/<topic>`), play it there, then merge.

## AI-generated 3D models (Hunyuan3D 2.1 and TRELLIS.2, both local)
- **TRELLIS.2** (Microsoft, MIT licence, `D:\AI\TRELLIS2` on the main PC, `C:\AI\TRELLIS2` on GameStation) is the one to use: one photo with the background cut out ->
  `venv\Scripts\python.exe run_image_to_3d.py <cutout.png> out\<name> 1024_cascade` (about 5 minutes on the 3090) -> a GLB
  with real panel lines, handles, lights and wheel spokes. Hunyuan3D 2.1 (`D:\AI\Hunyuan3D2`) is lumpier and its licence is
  non-commercial. TRELLIS.2 is Linux-only upstream; the Windows port (patched CUDA extensions, `build_ext.py`, a
  `segment_reduce` replacement in `trellis2/modules/sparse/basic.py`) is done, don't `git pull` it away. Its DINOv3 image
  encoder is gated: the owner's Hugging Face login (`hf auth login`) must be on the PC.
- Generate from the photo that shows most of the car. A second photo does not merge into the first model; a front-photo run
  gave a different, misshapen car.
- **Cleanup lives in `Art/Blender/ai_car_clean.py`** and carries over to any AI model: `import_trellis` (orient, cut the
  reflection plates the generator puts on roofs, smooth, decimate with the high-poly normals transferred), `bake_maps` +
  `paint_pixels` (paint windows, lights and trim by baked 3D position, so outlines stay crisp on any triangles),
  `texture_lamps` (take lamps from the generator's own red texture pixels), `fill_gaps`, `smooth_body`, `fix_trunk`.
  Only the outlines and the wheel numbers are car-specific.
- When smoothing a textured mesh, move points only along their normals. Sliding them sideways drags the painted
  outlines into zigzags. Don't freeze "sharp" vertices either: the AI's jagged seams count as sharp and stay as ridges.
- Never `recalc_face_normals` on a whole AI mesh (it isn't closed, big areas flip inside out); orient new patches only.
- Decimating a smooth remeshed skin folds it into creases: smooth first, decimate, then transfer the smooth normals.
- Measure the real object (length, width, height, wheelbase) before judging an AI model. The BRZ was 15% too wide and
  only looked "squat" until the numbers said why.
- Never keep a generator's own UV atlas (thousands of micro-islands): mipmaps bleed them into smears, and without
  mipmaps the model sparkles at distance. Re-UV with `smart_project` (big islands), bake with margin 8, keep mipmaps on.
- **Fix the photo, not the mesh.** Reflections in the paint become raised plates on the model; flatten them first
  (`tools/deflect.py`), or use a studio shot. Five rounds of roof-patching code taught us this.
- **The generator only knows what the photo shows.** Whole car in frame, 3/4 angle, a little height. A clipped roof
  gave strips hanging under the car; a close rear shot gave an invented front. One photo gives one good end: join two
  (`Art/Blender/trellis_join.py`: rear-photo model is the body, its nose shrink-wrapped onto the front-photo model).
- **Bake the generator's own texture** (Cycles selected-to-active, full-res source -> clean smart-project UVs) instead of
  painting outlines by position; only wheels, glass, lamps and plastics are rules. Park nothing aside before a bake
  (an object at (3, 1.5, 0) bakes black), and never pick a datablock with `[-1]` on `bpy.data.images` (alphabetical).
- **Weld before decimating.** The glTF import splits vertices along every UV island; decimating that tears holes
  that show as dark flecks. `remove_doubles(dist=1e-5)` first. And never tell bmesh faces apart by index after a
  delete: freed slots are reused. Tag them in an int layer.
- Close Chrome and anything else not in use before a TRELLIS run (it peaks near 17 GB VRAM); the GLB bake runs in its
  own process (`export_glb.py`) after the model is unloaded. A forced Unreal close leaves a "Restore Packages" dialog
  that blocks the MCP; close it with a window message from PowerShell.
- After every TRELLIS build, render each wheel from a low side angle in Blender: the game camera hides the lower half of
  a wheel, and the strip filter in `trellis_build.py` cut every coupe's hub and spokes there for a day before anyone saw it.
- A nearest-point shrink-wrap can't carry recesses (grille, lamp pockets): where a generator model has them, use its own
  faces (`nose_transplant` in `trellis_join.py`). Join torn AI edges with an overlap (flange + dipped band), never by
  bridging or welding the edges: pairing fails and leaves holes.
- `git lfs unlock` makes the file read-only, and then `AssetTools.delete` fails and blames a referencer. `attrib -r` first.
- **Characters and animals** (`Art/Blender/trellis_character.py`, headless: `blender -b --factory-startup --python
  trellis_character.py -- <glb> <Name> human|dog <height_m>`): imports, sizes, finds which way it faces, adds a skeleton
  with the UE mannequin's bone names (humans) or a simple dog skeleton, weights it, and exports `SK_<Name>.fbx` and the colour
  texture to `Content/Game/Imported/<Name>/`, with rest and test-pose renders in `Art/Blender/cache/`.
  - Reference pictures come from Gemini in the user's Chrome (Claude in Chrome; the in-app browser isn't signed in).
    Ask for the full body on a plain white background; for people, an A-pose with clear gaps between the arms and body.
    Never pick a download by a filename pattern: `~/Downloads` holds older Gemini images. Take the newest file.
  - Let TRELLIS simplify: `DEC=30000 TEX=2048` before `run_image_to_3d.py`. Its export rebuilds the surface from the voxel
    volume, which is far cleaner than decimating the GLB in Blender (fur flaps stop the decimator and remeshes shatter).
  - Fur gives pale patches at `1024_cascade`; furry animals come out clean at `512`. Try that before changing seeds.
  - Blender's automatic bone weights fail on anything small (a 0.5 m dog got zero weights). The script weights at 10x scale.

- **Animations for our characters** (`Art/Blender/walk_cycle.py <Name> human|dog`): keys a looping walk/trot on the
  rig in a centimetre scene and exports mesh + rig + action. Import it the way the character came in: copy the FBX
  into its own new folder under `Content/Game/Imported/` and let Interchange auto-import it (mesh, skeleton and
  anim together), then point the slot at the character's `MI_`. `SkeletalMeshTools.import_file` onto the existing
  skeleton does NOT work: the old FBX importer read the bones differently from Interchange (first 1/100 size, then
  twisted) and the walk crushed the man. Test an animation on a placed `SkeletalMeshActor` next to a plain copy.
- **Grid games: put decoration (posts, lamps, props) on tile corners, never tile centres.** The frog lands on centres and
  hops along the lines between them; a corner is 50 cm from every path. Street lamps on tile centres had the frog jumping through them.
- **Judge art from the real game camera** (Simulate, pause, `CaptureViewport` from the game's height), not from
  close-ups. The TRELLIS coupe looked great close up and like a dark blob from the game camera.
- **Meshy (paid, cloud): retries go through the browser, never the API.** Every API call (and the Meshy MCP) costs
  credits; the free retries (4 per model on Pro, 40 on Ultra) are a feature of Meshy's website, for models made there.
  So make every Meshy model on meshy.ai in the user's Chrome from the start (Claude in Chrome: its `file_upload` sends our
  reference picture; the in-app browser can't upload files), and press its Retry until one is good. Use the API only for
  steps that never need a retry, and save its results at once (Meshy keeps them 3 days).
  The user signs in to Meshy themselves. Downloading needs the user's OK in chat unless the request already says to
  download (e.g. "make these five and download them"); take the newest file in `~/Downloads`, never one picked by name.
  Plan credits are monthly and reset each month (no carry-over); bought credit packs never expire.

## Blender (for building our own 3D models)
- Blender **5.2 LTS** with Blender's official MCP (Blender Lab). It is registered in `.mcp.json` as `blender`.
- Setup on a new PC:
  1. In Blender 5.2, enable online access, then drag the add-on link from blender.org/lab/mcp-server in twice
     (repository, then add-on), enable it, and click Start (it listens on port 9876).
  2. Install `uv` (`irm https://astral.sh/uv/install.ps1 | iex`), run
     `git clone https://projects.blender.org/lab/blender_mcp.git C:\blender_mcp`, then `uv --directory C:\blender_mcp\mcp sync`.
  3. `.mcp.json` runs plain `uv`, so `uv` must be on the PATH (the installer puts it in `%USERPROFILE%\.local\bin`). Check with `uv --version` in a new terminal.
  4. Start a new Claude Code session so the server is picked up.
- Blender warns that the MCP runs AI-written code with no guards: keep only scratch/project files open while connected.
- **Open Unreal and Blender yourselves** (Start menu, or Claude launches them with `explorer.exe <path>`), never as a
  child of a chat. An app a chat starts closes when that chat is deleted, and its MCP tools vanish from every chat.
  If tools disappear mid-chat, check both apps are running and listening (ports 8000 and 9876), relaunch, then start a new chat.
- The Claude desktop app keeps a private copy of `AppData\Roaming`: anything a chat installs there (e.g. a Python from
  `uv python install`) is invisible to the user's own terminal. Install tools outside `AppData` (e.g. `C:\AI\...`).
- `.claude/settings.local.json` (per PC, gitignored) holds `"enableAllProjectMcpServers": true` so the servers in
  `.mcp.json` load without an approval prompt. Create it on each new PC.
- Models made in Blender count as our own (scored) art in the jam. Export FBX into `Content/Game/Imported/<Name>/`.
- With our FBX settings (forward -Z, up Y, scale 1), Blender's +Y becomes Unreal's **-Y** (X and Z stay). Check a mesh's
  bounds after import before rotating it in a Blueprint.
- When building meshes from script, add the material slots **before** writing faces, and never `materials.clear()` later.
  Either one silently resets every face to material 0. `Art/Blender/log_kit_materials.py` is a worked example of
  procedural materials baked to textures, including bark that tiles seamlessly.

## Starting a new repo (Nov 11)
- `tools/bootstrap/new_jam_repo.ps1 -Repo <new folder> -Name <Game> [-Verify]` makes the jam repo: the Third Person BP
  template, our plugins and settings, scripts, agent files and docs, git with LFS. No practice gameplay or art.
  `-Verify` opens it in Unreal and checks the MCP, load errors and settings; close any other Unreal first (port 8000).
  It never commits. Its starter files are in `tools/bootstrap/templates/`.
- PowerShell variable names ignore case: `$uproject` and `$UProject` are the same variable.
- So do function names: a function called `Git` that runs `git` calls itself forever. Never name a function after a command.

## Working as a team (up to 5 people, each on their own PC)
Every teammate clones the repo and runs their own Claude Code. You only see and act on the PC this session runs on, and
your chat can't message chats on another person's Claude account: hand-offs go through Git (commits, `docs/TEAM.md`)
or through the humans. New teammate setup: `docs/SETUP_TEAMMATE.md`.
- **Unreal files can't be merged.** `.uasset`/`.umap` are binary: if two people change the same one, one person's work is
  lost. Git LFS locks are what stops that, and they work because everyone has their own GitHub account:
  - Before changing an asset: `git pull --rebase`, then `git lfs lock <file>`. If it's locked by someone else
    (`git lfs locks`), don't edit it: tell the user who has it, and suggest making a new asset or waiting.
  - New assets: commit, then lock right away if you'll keep editing them.
  - After pushing, unlock what you're done with (`git lfs unlock <file>`; by ID for many: `git lfs locks --json`,
    strip `\r` on Windows). Never `--force` unlock someone else's file unless that person agreed.
  - `git config lfs.locksverify true` (set by the setup guide) makes Git refuse a push over someone else's lock.
- **One level, many people:** the level uses "One File Per Actor" (World Settings > Use External Actors), so each placed
  actor is its own small file under `__ExternalActors__`. Two people can then place and move different things in the same
  map. Lock the actor files you change, not the whole `.umap`. Blueprints are still one file each: split big ones
  (e.g. separate `BP_` per system) so people don't queue for the same file.
- **Ownership:** `docs/TEAM.md` says who owns which Blueprints, folders and systems this jam. Stay in your owner's
  area; ask before editing another person's. Each person keeps work in their own folder for new assets
  (`Content/Game/<Type>/`, with clear names) to avoid name clashes.
- **Commit small, commit often, pull first:** `git pull --rebase` before every commit and before starting work. Text
  files (scripts, docs, `.ini`) merge normally; if a rebase stops on a conflict, show the user both sides.
- **Teammates on a Mac** (Justin): the project is Blueprint-only, so it opens without Xcode. Packaging, TRELLIS.2 and
  the bootstrap stay on Windows PCs. Their Blender MCP is a local-scope override (`docs/SETUP_TEAMMATE.md`, "On a
  Mac"); never put a Mac path in the shared `.mcp.json`. Use forward slashes and no `C:\` paths in anything shared.
- **Git identity:** every commit must be under the teammate's own name (`git config user.name` / `user.email`, their
  GitHub address). Epic may read our Git history, and it shows who built what.
- Push only tested work to `main` (see "How to work with us"). Bigger experiments go on a branch named
  `<name>/<topic>`; merge them once the team has played them.
- **Art made outside Unreal** (Blender, TRELLIS) is committed as FBX + textures under `Art/Blender/export/` and imported
  by whoever owns that area in Unreal (see `docs/TEAM.md`). Tell them the asset names in your hand-off.

## Switching computers (one person, two PCs)
Only one machine should have a given person's working copy of the project open at a time.
- **Which PC does what** is the Computers table in `docs/TEAM.md`, not a fixed rule here. The Team Owner's PCs share
  one GitHub account, so locks can't tell them apart: message the other PC's chat with the asset names after each push.
- **"I'm leaving this computer":** check every asset under `/Game/Game` is saved (`is_dirty`), make sure tested work is
  committed and pushed (ask about anything untested), release our LFS locks (`git lfs locks`), then close Unreal. If it
  stalls on a save prompt for a template asset we never meant to change, force-close it, but only after confirming our
  own assets are clean and pushed.
- **"Let's work on this computer":** `git pull` (LFS brings the assets), open `MegaJamPractice/MegaJamPractice.uproject`
  in UE 5.8, wait until the Unreal MCP at `http://127.0.0.1:8000/mcp` answers, then tell us it's ready.

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
