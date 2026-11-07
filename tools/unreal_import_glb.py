"""Imports GLB/glTF files with Unreal's own importer (Interchange), which keeps the glTF PBR materials.
Unreal's auto-import ignores .glb, and the MCP's StaticMeshTools.import_file only takes FBX/OBJ, so run this in the
editor's console box (Cmd mode), e.g. typed there with the Slate inspector:
    py C:/path/to/tools/unreal_import_glb.py /Game/Game/Imported/<Name> C:/path/model.glb [more.glb ...]
Run tools/glb_for_unreal.py on a generator's GLB first (PNG textures, real size, standing on the ground).
Each file lands in <dest>/<file name>/ (StaticMeshes, Materials, Textures). Nanite is switched off, like on our other
meshes. Lists what it made in Saved/glb_import_result.txt and in the Output Log (GLB_IMPORT ...)."""
import os
import sys
import unreal

dest, files = sys.argv[1], sys.argv[2:]
tasks = []
for f in files:
    t = unreal.AssetImportTask()
    t.filename = f
    t.destination_path = dest
    t.automated = True          # no dialogs
    t.replace_existing = True
    t.save = True
    tasks.append(t)
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)

lines = []
for f, t in zip(files, tasks):
    paths = list(t.imported_object_paths)
    lines.append(f'{os.path.basename(f)}: {len(paths)} assets')
    for p in paths:
        note = ''
        asset = unreal.load_asset(p)
        if isinstance(asset, unreal.StaticMesh):
            nanite = asset.get_editor_property('nanite_settings')
            if nanite.enabled:
                nanite.enabled = False
                # through the subsystem, so the mesh is rebuilt: setting the property alone leaves Nanite's
                # simplified fallback (a fifth of the triangles) as the mesh
                unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem).set_nanite_settings(asset, nanite, True)
                unreal.EditorAssetLibrary.save_loaded_asset(asset)
                note = '  (Nanite switched off)'
            note += f'  {asset.get_num_triangles(0)} triangles'
        lines.append('    ' + p + note)
with open(os.path.join(unreal.Paths.project_saved_dir(), 'glb_import_result.txt'), 'w') as out:
    out.write('\n'.join(lines) + '\n')
unreal.log('GLB_IMPORT ' + ' | '.join(l for l in lines if not l.startswith(' ')))
