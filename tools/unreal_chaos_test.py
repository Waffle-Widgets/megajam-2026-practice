"""Chaos Destruction test (run in the editor's console box with the Slate inspector, see the chaos-physics skill):
    py <repo>/tools/unreal_chaos_test.py build <GeometryCollection path> [level path]
        Makes a small test level (default /Game/Scratch/Lvl_ChaosTest): floor, sun, sky, the Geometry Collection on the
        floor, a heavy physics ball 6 m away and a camera that Play mode looks through. Nothing else is touched.
    py <repo>/tools/unreal_chaos_test.py view                   (during Play: look through ChaosTest_Camera; throw/blast do it too)
    py <repo>/tools/unreal_chaos_test.py throw [speed cm/s]     (during Play)
        Throws the ball at the Geometry Collection (default 2500 cm/s). In our test (Nov 11) it hit and bounced off
        without breaking it, even with low damage thresholds: collision damage is unresolved, use blast.
    py <repo>/tools/unreal_chaos_test.py blast [strength]       (during Play)
        Breaks it from code: strain at its centre (5000000 broke a 2 m block), then an 8 m/s outward push.
Writes Saved/chaos_test.txt. Delete /Game/Scratch afterwards if it was only a test.
"""
import sys
import unreal

ROOT = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()).rstrip('/')
MODE = sys.argv[1] if len(sys.argv) > 1 else 'build'
log = []
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
V = unreal.Vector


def R(pitch, yaw, roll):
    # unreal.Rotator(a, b, c) is (roll, pitch, yaw): always name them
    return unreal.Rotator(roll=roll, pitch=pitch, yaw=yaw)


def mesh_actor(mesh, loc, scale, label, physics=False):
    a = eas.spawn_actor_from_class(unreal.StaticMeshActor, loc, R(0, 0, 0))
    a.set_actor_label(label)
    c = a.static_mesh_component
    c.set_editor_property('mobility', unreal.ComponentMobility.MOVABLE if physics else unreal.ComponentMobility.STATIC)
    c.set_static_mesh(unreal.load_asset(mesh))
    a.set_actor_scale3d(scale)
    if physics:
        c.set_simulate_physics(True)
        c.set_mass_override_in_kg('None', 200.0, True)   # heavy: a light ball just bounces off
    return a


if MODE == 'build':
    gc_path = sys.argv[2]
    level = sys.argv[3] if len(sys.argv) > 3 else '/Game/Scratch/Lvl_ChaosTest'
    # a Geometry Collection made from a Dataflow template stays EMPTY (invisible, no collision) until its graph runs
    gc_asset = unreal.load_asset(gc_path)
    unreal.DataflowBlueprintLibrary.regenerate_asset_from_dataflow(gc_asset)
    unreal.EditorAssetLibrary.save_loaded_asset(gc_asset)
    if not les.new_level(level):
        raise RuntimeError(f'could not make {level} (does it exist already?): stopping so the open level is not changed')
    if ues.get_editor_world().get_name() != level.split('/')[-1]:
        raise RuntimeError('the new level did not open: stopping')
    mesh_actor('/Engine/BasicShapes/Cube.Cube', V(0, 0, -50), V(40, 40, 1), 'ChaosTest_Floor')
    Y = 600   # the template's player spawns at the origin: keep the test 6 m to the side
    sun = eas.spawn_actor_from_class(unreal.DirectionalLight, V(0, 0, 500), R(-40, -50, 0))
    sun.set_actor_label('ChaosTest_Sun')
    eas.spawn_actor_from_class(unreal.SkyLight, V(0, 0, 300), R(0, 0, 0)).set_actor_label('ChaosTest_Sky')
    eas.spawn_actor_from_class(unreal.SkyAtmosphere, V(0, 0, 0), R(0, 0, 0)).set_actor_label('ChaosTest_Atmosphere')
    gca = eas.spawn_actor_from_class(unreal.GeometryCollectionActor, V(0, 0, 0), R(0, 0, 0))
    gca.set_actor_label('ChaosTest_Breakable')
    gcc = gca.get_component_by_class(unreal.GeometryCollectionComponent)
    gcc.set_rest_collection(gc_asset)
    # how hard a hit must be to break it, per cluster level (defaults 500000, 50000, 5000). The COMPONENT keeps its own
    # copy: changing the asset afterwards doesn't reach placed ones. (Our thrown ball still didn't break it.)
    gcc.set_editor_property('damage_threshold', [5000.0, 2000.0, 500.0])
    gca.set_actor_scale3d(V(2, 2, 2))     # the engine cube is 1 m; this makes a 2 m block
    gca.set_actor_location(V(0, Y, 100), False, False)
    mesh_actor('/Engine/BasicShapes/Sphere.Sphere', V(-600, Y, 100), V(0.8, 0.8, 0.8), 'ChaosTest_Ball', physics=True)
    cam = eas.spawn_actor_from_class(unreal.CameraActor, V(-500, Y - 900, 450), R(-22, 52, 0))
    cam.set_actor_label('ChaosTest_Camera')
    cam.set_editor_property('auto_activate_for_player', unreal.AutoReceiveInput.PLAYER0)
    les.save_current_level()
    log.append(f'built {level} with {gc_path}')
else:
    world = ues.get_game_world()
    if world is None:
        raise RuntimeError('Play is not running: press Play first')
    actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
    by = {a.get_actor_label(): a for a in actors}
    gca = by.get('ChaosTest_Breakable')
    target = gca.get_actor_location()
    # look through TestCamera (auto-activate alone lost to the project's own pawn camera)
    pc = unreal.GameplayStatics.get_player_controller(world, 0)
    if pc and 'ChaosTest_Camera' in by:
        cam = by['ChaosTest_Camera']
        cam.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(cam.get_actor_location(), target), False)
        pc.set_view_target_with_blend(cam, 0.0)
    if MODE == 'throw':
        speed = float(sys.argv[2]) if len(sys.argv) > 2 else 2500.0
        ball = by['ChaosTest_Ball']
        d = target - ball.get_actor_location()
        d = d / d.length()
        ball.static_mesh_component.set_physics_linear_velocity(d * speed, False)
        log.append(f'threw ball at {speed} cm/s')
    elif MODE == 'view':
        log.append('looking through ChaosTest_Camera')
    elif MODE == 'blast':
        strength = float(sys.argv[2]) if len(sys.argv) > 2 else 500000.0
        gcc = gca.get_component_by_class(unreal.GeometryCollectionComponent)
        gcc.apply_external_strain(0, target, 300.0, 0, 1.0, strength)      # break the bonds near the centre
        gcc.add_radial_impulse(target, 400.0, 800.0, unreal.RadialImpulseFalloff.RIF_LINEAR, True)   # 8 m/s outward: more throws the pieces out of sight
        log.append(f'blast {strength}')
with open(f'{ROOT}/Saved/chaos_test.txt', 'w') as fh:
    fh.write('\n'.join(log) + '\n')
unreal.log('CHAOS TEST ' + ' | '.join(log))
