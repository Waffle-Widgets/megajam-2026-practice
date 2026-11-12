"""Point a Blueprint's Niagara component at a particle system (niagara-fx skill: ObjectTools.set_properties returns false
on a Blueprint's component template, so this is done from editor Python). Add the component first (ActorTools.add_component).
Run in the editor's console box:
    py <repo>/tools/unreal_fx_component_setup.py <BP path> <component> <Niagara system path> <auto-activate 0|1>
e.g. py .../unreal_fx_component_setup.py /Game/Game/Blueprints/BP_FireBoom3D FX /Game/Game/FX/NS_FireBoom3D 1
Compiles and saves the Blueprint, writes Saved/fx_component_setup.txt."""
import sys
import unreal

ROOT = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()).rstrip('/')
bp_path, comp_name, ns_path, auto = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] == '1'
name = bp_path.rsplit('/', 1)[1]
bp = unreal.load_asset(bp_path)
comp = unreal.find_object(None, f'{bp_path}.{name}_C:{comp_name}_GEN_VARIABLE')
if comp is None:
    res = f'{name}.{comp_name}: component missing (add it first)'
else:
    comp.set_editor_property('asset', unreal.load_asset(ns_path))
    comp.set_editor_property('auto_activate', auto)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    unreal.EditorAssetLibrary.save_loaded_asset(bp)
    res = (f"{name}.{comp_name}: asset={comp.get_editor_property('asset').get_name()} "
           f"auto_activate={comp.get_editor_property('auto_activate')}")
with open(f'{ROOT}/Saved/fx_component_setup.txt', 'a') as fh:
    fh.write(res + '\n')
unreal.log('FX SETUP ' + res)
