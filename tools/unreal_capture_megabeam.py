"""Film the Mega Beam at one exact moment. Start Play (not Simulate) first, then type in the editor's console box:
    py <repo>/tools/unreal_capture_megabeam.py [seconds after the shot] [game|side] [attack event]
    (defaults 1.05, game, FireMegaBeam; FireFireBlast films the Fire Blast)
Makes Smugshi fire his Mega Beam (FireMegaBeam, the same event the E key uses), waits in game time with a tick
callback (no sleep, so the game keeps running), freezes time and takes a HighResShot 1920x1080
(Saved/Screenshots/WindowsEditor/HighresScreenshot*.png). The beam charges 0.75 s and is fully out at about 0.9 s.
'side': after freezing, a camera is parked 2.6 m beside the beam, a little above it, looking along it (to judge
whether the beam is round; the game camera only sees it from above). Stop Play afterwards. Writes Saved/megabeam_capture.txt."""
import sys
import unreal

ROOT = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()).rstrip('/')
AT = float(sys.argv[1]) if len(sys.argv) > 1 else 1.05
VIEW = sys.argv[2] if len(sys.argv) > 2 else 'game'
# 3rd argument: which of Smugshi's attack events to fire (FireMegaBeam, FireFireBlast); the beam by default
ATTACK = sys.argv[3] if len(sys.argv) > 3 else 'FireMegaBeam'
GS = unreal.GameplayStatics
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
note = []
if world is None:
    raise RuntimeError('Play is not running: press Play first')
pawn = GS.get_player_pawn(world, 0)
note.append(f'pawn {pawn.get_class().get_name() if pawn else None} view {VIEW} attack {ATTACK}')
pawn.call_method(ATTACK)
t0 = GS.get_time_seconds(world)
state = {'h': None, 'step': 0, 'wait': 0}


def park_side_camera():
    # aim from Smugshi toward Sparkit, the way BP_Smugshi aims the beam (reading the beam's Niagara component
    # gave a spot outside the room)
    foes = GS.get_all_actors_of_class(world, unreal.load_class(None, '/Game/Game/Blueprints/BP_Sparkit.BP_Sparkit_C'))
    if not foes:
        note.append('no Sparkit')
        return
    here = pawn.get_actor_location()
    d = foes[0].get_actor_location() - here
    d = unreal.Vector(d.x, d.y, 0).normal()
    o = here + d * 40.0 + unreal.Vector(0, 0, 10)
    side = d.cross(unreal.Vector(0, 0, 1)).normal()
    loc = o + d * 120.0 + side * 260.0 + unreal.Vector(0, 0, 70)
    look = o + d * 330.0
    rot = unreal.MathLibrary.find_look_at_rotation(loc, look)
    # Python can't spawn into the Play world (no deferred spawn), so borrow a prop: hide it, move it to the camera
    # spot and look through it (an actor without a camera views from its own location and rotation). Play-mode
    # changes are thrown away when Play stops.
    props = GS.get_all_actors_of_class(world, unreal.StaticMeshActor)
    if not props:
        note.append('no prop to look through')
        return
    def size(a):   # the smallest prop (props[0] was the floor: hiding it emptied the room)
        o_, e_ = a.get_actor_bounds(False)
        return e_.x + e_.y + e_.z
    eye = min(props, key=size)
    note.append(f'looking through {eye.get_actor_label() if hasattr(eye, "get_actor_label") else eye.get_name()}')
    eye.root_component.set_mobility(unreal.ComponentMobility.MOVABLE)   # props are Static and silently refuse to move
    eye.set_actor_hidden_in_game(True)
    eye.set_actor_enable_collision(False)
    eye.set_actor_location_and_rotation(loc, rot, False, True)
    GS.get_player_controller(world, 0).set_view_target_with_blend(eye, 0.0)
    note.append(f'side camera at {loc} looking at {look}')


def tick(dt):
    if state['step'] == 0 and GS.get_time_seconds(world) - t0 >= AT:
        GS.set_global_time_dilation(world, 0.0001)
        note.append(f'frozen at {GS.get_time_seconds(world) - t0:.3f} s after firing')
        if VIEW == 'side':
            try:
                park_side_camera()
            except Exception as e:      # never leave the callback failing every frame
                note.append(f'side camera failed: {e}')
        state['step'], state['wait'] = 1, 3          # let the view change reach the screen
    elif state['step'] == 1:
        state['wait'] -= 1
        if state['wait'] <= 0:
            unreal.SystemLibrary.execute_console_command(world, 'HighResShot 1920x1080')
            with open(f'{ROOT}/Saved/megabeam_capture.txt', 'w') as fh:
                fh.write('\n'.join(note) + '\n')
            state['step'] = 2
            unreal.unregister_slate_post_tick_callback(state['h'])


state['h'] = unreal.register_slate_post_tick_callback(tick)
