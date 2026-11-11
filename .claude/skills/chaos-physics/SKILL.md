---
name: chaos-physics
description: Physics with Unreal's Chaos through the MCP - breakable objects (Geometry Collections fractured by a Dataflow graph), breaking them from code (strain + impulse at a hit point), physics props, and where vehicles, ragdolls and cloth fit. Use when the game needs things that break, smash, topple, explode apart, or move by real physics.
---

# Chaos physics (tested Nov 11 2026 on M Station, Unreal 5.8, in a scratch level)

Proof: `docs/media/chaos_test_break.png` (a 2 m block broken into 20 Voronoi chunks by one call from code).
Test script: `tools/unreal_chaos_test.py` (builds a test level, then `throw` or `blast` during Play).
**Jam rule:** breakable assets are art: make them during the jam. Bring this skill and the script, not the assets.

## What Chaos gives a jam game
- **Physics props** (crates, barrels, balls): a Static Mesh with Simulate Physics on. Nothing to set up.
- **Destruction** (walls, pillars, crates that smash): a **Geometry Collection** (GC), a mesh pre-cut into pieces that
  hold together until something breaks them. This skill is mostly about these.
- **Fields** (explosions that push and break everything in a radius): the Field System plugin. Untested here.
- **Ragdolls:** a Physics Asset on a skeletal mesh (`PhysicsToolsets.PhysicsAssetToolset.CreateFromMesh`, constraints,
  bodies). Untested here.
- **Vehicles:** the Chaos Vehicles plugin (the Vehicle template). Untested here; it's a big system, so ask before using it.
- **Cloth:** Chaos Cloth on a skeletal mesh. Untested here.

## Plugins (project setup: allowed before the jam)
- **Geometry Collection** (`GeometryCollectionPlugin`, the Chaos Destruction plugin) is **off by default** in the engine; `tools/bootstrap/new_jam_repo.ps1` turns it on for the jam project.
  Something (our toolsets) loaded it in the Deep Archive project, but turn it on in the `.uproject` explicitly so the
  jam project doesn't depend on that. Add `FieldSystemPlugin` only if we use Fields, `ChaosVehiclesPlugin` only for cars.
- `Dataflow` (the graph that does the cutting) and `ChaosSolverPlugin` are on by default.

## Making a breakable from any static mesh, all through the MCP
1. **Create the GC from the "GC Template StaticMesh" template** (`DataflowAgent.DataflowAgentToolset`):
   `CreateDataflowCompatibleAssetFromTemplate` with `className` `GeometryCollection`, a `name`, a `path`, and `templateId`
   `/GeometryCollectionPlugin/DataflowTemplates/DF_GC_Template_StaticMesh.DF_GC_Template_StaticMesh`.
   Its graph: `SourceStaticMesh` (a variable, default the engine Cube) -> `StaticMeshToCollection` -> `UniformFracture`
   (20 Voronoi pieces) -> `GeometryCollectionTerminal`.
2. **Point it at our mesh** (untested: we used the default cube): `unreal.DataflowBlueprintLibrary` has
   `override_dataflow_variable_object`, and the GC's `DataflowInstance.variableOverrides.variables.sourceStaticMesh`
   holds the mesh (`ObjectTools.get_properties` shows it). Check with `GetGraphStructure` and a capture.
3. **Pieces:** nodes are addressed as `<GC path>:EmbeddedDataflow.<NodeName>`, e.g.
   `/Game/Game/Destruction/GC_Wall.GC_Wall:EmbeddedDataflow.UniformFracture`. `UpdateNode` with
   `{"MinVoronoiSites": 12, "MaxVoronoiSites": 16}`. `GetGraphStructure` on `<GC path>:EmbeddedDataflow` shows the graph.
   Other cutters exist (`ListNodeTypes`): `FBrickCutterDataflowNode` (walls), `FSliceCutterDataflowNode`,
   `FPlaneCutterDataflowNode`, `FVoronoiFractureDataflowNode` with `FRadialScatterPointsDataflowNode` (more pieces near
   an impact point), and `FAutoClusterDataflowNode` (chunks that break into smaller chunks).
4. **Run the graph: `unreal.DataflowBlueprintLibrary.regenerate_asset_from_dataflow(gc)`, then save.** Without this the GC
   is EMPTY: invisible in the level and nothing collides with it (our ball rolled straight through).
5. **Place it:** a `GeometryCollectionActor`; `component.set_rest_collection(gc)`. The engine cube is 1 m, so scale it.

## Breaking it (what worked)
- **From code at a point: strain, then a small push.** On the GC component:
  `apply_external_strain(0, location, radius, 0, 1.0, strain)` breaks the bonds near `location` (5,000,000 broke our
  2 m block in one call), then `add_radial_impulse(location, radius, 800.0, RIF_LINEAR, True)` (8 m/s velocity change)
  scatters the pieces. In a Blueprint: projectile **On Hit** -> `Apply External Strain` at Hit Location -> `Add Radial
  Impulse`. This is the reliable way for attacks, bombs and "smash" buttons.
- **A bigger push throws everything out of sight:** a radial impulse of 20,000 cm/s made the block vanish in one frame.
- **Collision damage did NOT break it in our test:** a 200 kg ball at 25 m/s hit and bounced off, even with damage
  thresholds of 50. Unresolved (one session). Don't promise "it breaks when you ram it" without testing; route the hit
  through the strain call above.
- **Damage thresholds live on the component, not just the asset.** The GC asset's `DamageThreshold` defaults to
  (500000, 50000, 5000) per cluster level; a placed component keeps its own copy (`damage_threshold`), so changing the
  asset afterwards doesn't reach placed ones. Set the component's.
- Broken pieces are removed after they settle (`allow_removal_on_break`/`on_sleep` default on): good for performance.

## Testing it
- `py <repo>/tools/unreal_chaos_test.py build <GC path> [level]` (in the editor console box, Slate inspector) makes a
  test level: floor, sun, the GC 6 m to the side of the player start, a 200 kg ball, a camera. During Play: `view`,
  `throw [speed]`, `blast [strain]`, then `HighResShot 1920x1080` for a picture.
- Keep the piece count low (about 20 per object, a handful of breakables on screen); check frame time
  (`playtest-capture` skill) after adding many.

## Traps that cost us a round
- **`unreal.Rotator(a, b, c)` is (roll, pitch, yaw)**, not (pitch, yaw, roll). Our camera looked at the sky. Always name them:
  `unreal.Rotator(roll=0, pitch=-22, yaw=52)`.
- **`LevelEditorSubsystem.new_level(path)` fails if the asset exists, and the script carries on in the open level.** Ours
  put its test objects into a real level (and deleted that level's own "Sun" by label). Check the return value and the
  world name, give test actors unique labels (`ChaosTest_*`), and on a mistake switch away without saving:
  `EditorLoadingAndSavingUtils.new_blank_map(False)`.
- `EditorAssetLibrary.delete_directory` refused to delete a folder holding a level that had just been open. Delete
  scratch folders with the editor closed.
- The Third Person template's player spawns at the origin: keep test objects away from it.
- `ObjectTools.set_properties` takes `values` as a JSON **string**.
