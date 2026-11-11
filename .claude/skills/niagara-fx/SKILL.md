---
name: niagara-fx
description: Make attack and impact effects with real Niagara particles through the Unreal MCP (beams, trails, sparks, flares, fades), judge them from the game camera and tune them with the owner. Use when an effect looks flat or weak, or the user asks for particles, a new attack, a hit effect or a fade-out.
---

# Particle effects with Niagara (learned on the Deep Archive Mega Beam, Nov 10 2026)

The worked example is the Mega Beam in the Deep Archive HD-2D repo (`Waffle-Widgets/deep-archive-hd2d`):
`Game/FX/NS_MegaBeam3D`, `BP_MegaBeam3D`, `tools/fx3d_graphs.py` (graph text), `tools/unreal_make_beam_particle_mat.py`,
`tools/unreal_capture_megabeam.py`, and the story with pictures in `docs/realistic-3d-test.md` (`docs/captures/21_*`-`30_*`).
**Jam rule:** effects are art, so they're made during the jam. Bring this skill and scripts, not the assets.

## What looks good (the owner's taste)
- **Shape and contrast read; texture detail doesn't.** At the game camera a beam is 30-40 px wide. Noise painted on
  tubes smeared into one yellow cloud, and brighter colours made it worse. Solid shapes, a bright core, a contrasting
  colour and dark outlines read instantly.
- **Show mock-ups before building.** Render 2-3 options in Blender from the game camera, at the capture's scale, laid
  over a real capture (`Art/Blender/beam_mockup.py` + a System.Drawing composite). The owner picked one in a single
  round; blind colour tweaks in Unreal had been rejected.
- **Solid colours, not "adds light".** Niagara's default sprite and ribbon materials add light: red over white turns
  white. Use an unlit **Masked** material that outputs the particle colour, with cartoon bands by how the surface faces
  the camera (dark outline at the silhouette, lighter band in the middle). The owner likes attacks crisp, no bloom haze.
  Keep the default see-through material only for soft glows.
- **Round, not flat.** Ribbons default to flat strips that turn to face the camera: fine from above, flat from the side.
  Set the ribbon renderer `Shape` to `Tube` (`TubeSubdivisions` 8-10) for anything a camera can orbit.
- **Taper the ends** into the muzzle flare and the impact, and give the fade-out its own beat (the Mega Beam breaks into
  thin strands that peel away over 0.8 s). The owner tuned fade length in 0.1 s steps: make it one number in the Blueprint.
- Tonemapping washes bright orange to yellow/cream: for red-orange keep emissive near 1-2 and push the red channel.

## How to build it (MCP NiagaraToolsets)
- **The Blueprint passes a few numbers; Niagara draws.** User parameters (`User.BeamLength`, `User.Thick`, `User.Hitting`,
  `User.Dissolve`), set every tick with `(Niagara|SetNiagaraVariable(Float) :self comp :InVariableName "BeamLength" :InValue len)`
  (name without `User.`). Positions and widths are HLSL expressions on SetParameters modules
  (`AddSetParametersModule` + `SetStackInputData` with an `HlslExpression`), e.g. a helix:
  `float3(r*cos(a), r*sin(a), Particles.U*User.BeamLength)`. Use local space and place the component at the mouth,
  rotated so local Z points along the beam (`MakeRotFromZ`).
- **Ribbons that fill a length:** `SpawnBurst_Instantaneous` N points, lifetime 100, `Particles.U = ExecIndex() / (N-1)`,
  `Particles.RibbonLinkOrder` = the same, then set `Particles.Position` from U every frame. Random U made the ribbon join
  points out of order and its curve smoothing swung them into huge loops: number them, and set `TessellationMode` Disabled.
- **One ribbon per emitter** (separate ribbons in one emitter need a NiagaraID RibbonID): copy a small builder function.
- Sprites (flares, sparks): `SpawnRate` + `AddVelocity` with a `RandomRangeVector` dynamic input (`['Velocity','Minimum']`
  sets its sub-input) + `GravityForce` + `SolveForcesAndVelocity`. Sparks: renderer `Alignment` `VelocityAligned`.
- Turn emitters on and off from numbers (`SpawnRate = 45 * step(0.01, User.Thick)`), not by deactivating early: a
  deactivated system stops everything, including a fade you still want to see.

## Traps that each cost us a round
- A ribbon renderer added by the toolset has **no material** and draws nothing. Set `Material` with `SetRendererData`.
- New systems from the `DirectionalBurst` template run **once for 1 s** (System State). Continuous emitters stopped
  before the beam even fired. Set `Loop Behavior` Infinite and a long `Loop Duration` (30 s) so bursts don't repeat.
- Minimal emitters use the system's life cycle, so their own `Inactive Response` is hidden and can't be set.
- `ObjectTools.set_properties` returned false on a Blueprint's Niagara component template. Set `asset` and
  `auto_activate` from an editor Python script on `.../BP_X.BP_X_C:Comp_GEN_VARIABLE`, then compile and save.
- `get_node_type_pins` can leave stray nodes in the graph; the next `write_graph_dsl` replaces them.
- `GetModuleInputValues` input names are the display names (`Lifetime`, `Spawn Count`, `Particles.Color` for a
  SetParameters entry). Inputs hidden by a static switch refuse to be set: change the switch first.
- An actor that removes itself (DestroyActor) cuts its effects off. If a fade needs more time, keep the actor alive
  longer but stop driving shared things (night sky, lights) at the old time, so a second shot isn't overwritten.

## Judging it (the owner plays it last)
- **Freeze-frame captures** (`tools/unreal_capture_megabeam.py <seconds> [game|side]`, typed into the console box in
  Play): it fires the attack, waits in game time with a Slate tick callback (never `sleep`), freezes time
  (`set_global_time_dilation` 0.0001) and takes `HighResShot 1920x1080`. Take shots at several moments: mid-fire, the
  hit, partway through the fade.
- **Check another angle**, not only the game camera: the flat strips only showed from the side. Python can't spawn into
  the Play world, so the script borrows the **smallest** prop, sets it Movable (Static props silently don't move), hides
  it and looks through it with `SetViewTargetWithBlend`.
- A tick callback that throws repeats every frame. Wrap its work in try/except. To stop a runaway one, find the
  function with `gc.get_objects()` (dicts of plain values aren't tracked) and unregister its handle.
- Stop Play before every edit; save; `git status` to confirm the asset changed; lock new assets after their first commit.
