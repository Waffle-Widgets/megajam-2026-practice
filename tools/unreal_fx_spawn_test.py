"""Spawn a Niagara system on its own, 1.5 m beside Smugshi, and take a frozen HighResShot 0.3 s later: tells whether a
problem is in the particle system itself or in the Blueprint that uses it (niagara-fx skill). Start Play first, then:
    py <repo>/tools/unreal_fx_spawn_test.py /Game/Game/FX/NS_Something [seconds, default 0.3]
Writes Saved/fx_spawn_test.txt."""
import sys
import unreal
ROOT = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()).rstrip('/')
GS = unreal.GameplayStatics
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
pawn = GS.get_player_pawn(world, 0)
ns = unreal.load_asset(sys.argv[1])
WAIT = float(sys.argv[2]) if len(sys.argv) > 2 else 0.3      # seconds before the picture (fluid fire needs longer)
loc = pawn.get_actor_location() + unreal.Vector(150, 0, 30)
comp = unreal.NiagaraFunctionLibrary.spawn_system_at_location(world, ns, loc, unreal.Rotator(0, 0, 0), unreal.Vector(1, 1, 1), True, True)
note = [f'spawned {comp} active={comp.is_active() if comp else None}']
t0 = GS.get_time_seconds(world)
state = {'h': None, 'step': 0}


def tick(dt):
    try:
        if state['step'] == 0 and GS.get_time_seconds(world) - t0 > WAIT:
            GS.set_global_time_dilation(world, 0.0001)
            note.append(f'active={comp.is_active()}')
            unreal.SystemLibrary.execute_console_command(world, 'HighResShot 1920x1080')
            state['step'] = 1
            with open(f'{ROOT}/Saved/fx_spawn_test.txt', 'w') as fh:
                fh.write('\n'.join(note) + '\n')
            unreal.unregister_slate_post_tick_callback(state['h'])
    except Exception as e:
        state['step'] = 1
        unreal.unregister_slate_post_tick_callback(state['h'])
        unreal.log(f'FX TEST failed {e}')


state['h'] = unreal.register_slate_post_tick_callback(tick)
