"""List unsaved (dirty) packages and textures under /Game, e.g. to find what a Niagara bake just made. Run in the console box:
    py <repo>/tools/unreal_find_new_assets.py [path filter]
Writes Saved/find_new_assets.txt."""
import sys
import unreal

ROOT = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()).rstrip('/')
FILT = sys.argv[1] if len(sys.argv) > 1 else ''
lines = []
for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages():
    lines.append('dirty: ' + p.get_name())
ar = unreal.AssetRegistryHelpers.get_asset_registry()
for a in ar.get_assets_by_path('/Game', recursive=True):
    name = str(a.package_name)
    if FILT and FILT not in name:
        continue
    if 'Texture' in str(a.asset_class_path.asset_name) or 'Bake' in name:
        lines.append(f'asset: {name} ({a.asset_class_path.asset_name})')
with open(f'{ROOT}/Saved/find_new_assets.txt', 'w') as fh:
    fh.write('\n'.join(lines) + '\n')
unreal.log('FIND NEW ASSETS done')
