"""Gives one of our own characters Unreal's motion-captured mannequin animations (idle, walk, jog, jump), instead of
a walk keyed by script. It works for any character whose skeleton uses the mannequin's bone names, which is what
Art/Blender/trellis_character.py builds (root, pelvis, spine_01..03, neck_01, head, clavicle/upperarm/lowerarm/hand,
thigh/calf/foot/ball).

Run it in the Unreal editor's console box (Cmd), with Play mode stopped:
    py <repo>/tools/unreal_retarget_mannequin.py <target skeletal mesh> <output folder> [ik|fk] [arms|all|none]
    py <repo>/tools/unreal_retarget_mannequin.py /Game/Game/Imported/CafeWalker/SK/SK_CafeWalker_Walk /Game/Game/Imported/CafeWalker/Anims
It makes, in the output folder: an IK Rig for the mannequin and one for our character (which bones form the spine,
arms and legs), an IK Retargeter that maps one onto the other (our character's rest pose is lined up with the
mannequin's first, so arms that hang straight down still work), and a copy of each animation in LIST for our skeleton,
named <original>_<suffix>. The mannequin animations ship with Unreal's template, so they are sourced, not scored.
Results and errors go to Saved/retarget_result.txt.
"""
import os
import sys
import traceback
import unreal

SRC_MESH = '/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple'
ANIMS = '/Game/Characters/Mannequins/Anims/Unarmed/'
LIST = ['BS_Idle_Walk_Run', 'MM_Idle', 'Walk/MF_Unarmed_Walk_Fwd', 'Jog/MF_Unarmed_Jog_Fwd', 'Jump/MM_Jump', 'Jump/MM_Fall_Loop', 'Jump/MM_Land']
SUFFIX = '_CW'
ALIGN = sys.argv[4] if len(sys.argv) > 4 else 'arms'      # arms | all | none
ARM_BONES = [b + s_ for s_ in ('_l', '_r') for b in ('clavicle', 'upperarm', 'lowerarm', 'hand')]
USE_IK = len(sys.argv) > 3 and sys.argv[3] == 'ik'      # add "ik" as a third argument to keep the IK pass
# our skeleton, as retarget chains (name, first bone, last bone); the names match what Unreal generates for the mannequin
CHAINS = [('Spine', 'spine_01', 'spine_03'), ('Neck', 'neck_01', 'neck_01'), ('Head', 'head', 'head'),
          ('LeftClavicle', 'clavicle_l', 'clavicle_l'), ('LeftArm', 'upperarm_l', 'hand_l'),
          ('RightClavicle', 'clavicle_r', 'clavicle_r'), ('RightArm', 'upperarm_r', 'hand_r'),
          ('LeftLeg', 'thigh_l', 'ball_l'), ('RightLeg', 'thigh_r', 'ball_r')]
eal = unreal.EditorAssetLibrary
out = []


def log(*a):
    out.append(' '.join(str(x) for x in a))


def fresh(name, folder, cls, factory):
    path = folder + '/' + name
    if eal.does_asset_exist(path):
        log('delete', name, eal.delete_asset(path), 'still there:', eal.does_asset_exist(path))
        if eal.does_asset_exist(path):
            # Creating over a file that is still on disk opens a modal "Overwrite Existing Object" box, which freezes
            # the MCP until someone answers it. Reuse the old asset instead: everything on it is set again below.
            return unreal.load_asset(path)
    return unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, cls, factory)


def make_rig(name, folder, mesh, manual):
    rig = fresh(name, folder, unreal.IKRigDefinition, unreal.IKRigDefinitionFactory())
    c = unreal.IKRigController.get_controller(rig)
    log(name, 'mesh set', c.set_skeletal_mesh(mesh))
    auto = c.apply_auto_generated_retarget_definition()
    log(name, 'auto definition', auto)
    if not auto and manual:
        c.set_retarget_root('pelvis')
        for cn, a, b in CHAINS:
            c.add_retarget_chain(cn, a, b, '')
    elif auto:
        log(name, 'auto full-body IK', c.apply_auto_fbik())
    log(name, 'root', c.get_retarget_root(), 'chains', [(str(ch.chain_name), str(c.get_retarget_chain_start_bone(ch.chain_name)), str(c.get_retarget_chain_end_bone(ch.chain_name))) for ch in c.get_retarget_chains()])
    eal.save_loaded_asset(rig)
    return rig


def run(target_path, folder):
    src_mesh, tgt_mesh = unreal.load_asset(SRC_MESH), unreal.load_asset(target_path)
    src = make_rig('IK_Mannequin_Src', folder, src_mesh, False)
    tgt = make_rig('IK_' + target_path.split('/')[-1], folder, tgt_mesh, True)
    rtg = fresh('RTG_Mannequin_to_' + target_path.split('/')[-1], folder, unreal.IKRetargeter, unreal.IKRetargetFactory())
    c = unreal.IKRetargeterController.get_controller(rtg)
    S, T = unreal.RetargetSourceOrTarget.SOURCE, unreal.RetargetSourceOrTarget.TARGET
    c.set_ik_rig(S, src)
    c.set_ik_rig(T, tgt)
    c.add_default_ops()
    try:
        c.assign_ik_rig_to_all_ops(S, src)
        c.assign_ik_rig_to_all_ops(T, tgt)
    except Exception as e:
        log('assign_ik_rig_to_all_ops:', str(e)[:200])
    c.auto_map_chains(unreal.AutoMapChainType.FUZZY, True)
    # Line the ARMS of our rest pose up with the mannequin's A-pose before copying motion (the default). Each bone
    # turns by as much as the mannequin's does from its own rest pose, so any difference in rest pose shows up in
    # every frame: without this his hands hung 8 cm behind his shoulders. Legs are left as modelled: "all" forces
    # them onto the mannequin's stance, which turned the knees in on a slim body.
    c.reset_retarget_pose(c.get_current_retarget_pose_name(T), [], T)      # no leftovers from an earlier model
    if ALIGN == 'all':
        c.auto_align_all_bones(T)
    elif ALIGN == 'arms':
        c.auto_align_bones([unreal.Name(b) for b in ARM_BONES], unreal.RetargetAutoAlignMethod.CHAIN_TO_CHAIN, T)
    log('aligned', ALIGN, 'upperarm_l offset', c.get_rotation_offset_for_retarget_pose_bone('upperarm_l', T),
        'thigh_l offset', c.get_rotation_offset_for_retarget_pose_bone('thigh_l', T))
    log('ops', c.get_num_retarget_ops(), [str(c.get_op_name(i)) for i in range(c.get_num_retarget_ops())])
    if not USE_IK:
        # Copy joint rotations only. The IK pass pulls our hands and feet to where the mannequin's are, and on a
        # body with other proportions that bent the knees inwards ("legs bow in" in playtest).
        for i in range(c.get_num_retarget_ops()):
            if 'IK' in str(c.get_op_name(i)):
                c.set_retarget_op_enabled(i, False)
                log('switched off op', c.get_op_name(i), 'enabled now', c.get_retarget_op_enabled(i))
    for cn, _, _ in CHAINS:
        try:
            log('map', cn, '<-', c.get_source_chain(cn))
        except Exception as e:
            log('map', cn, 'ERR', str(e)[:120])
    eal.save_loaded_asset(rtg)
    reg = unreal.AssetRegistryHelpers.get_asset_registry()
    assets = []
    for n in LIST:
        ad = reg.get_asset_by_object_path(ANIMS + n + '.' + n.split('/')[-1])
        log('source', n, ad.is_valid())
        if ad.is_valid():
            assets.append(ad)
    res = unreal.IKRetargetBatchOperation.duplicate_and_retarget(assets, src_mesh, tgt_mesh, rtg, '', '', '', SUFFIX, folder, False, True, True)
    for ad in res:
        log('made', ad.asset_class_path.asset_name, ad.package_name)
    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(False, True)


try:
    run(sys.argv[1], sys.argv[2])
    log('DONE')
except Exception:
    log('ERROR', traceback.format_exc())
with open(os.path.join(unreal.Paths.project_saved_dir(), 'retarget_result.txt'), 'w') as fh:
    fh.write('\n'.join(out) + '\n')
unreal.log('RETARGET ' + ' | '.join(out)[:900])
