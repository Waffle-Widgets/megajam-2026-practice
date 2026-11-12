# The Mega Beam against the world (the owner, 2026-11-11: "test it with the beams ... instead of completely breaking it,
# pierce through the object, almost like melting through it"). Functions on BP_MegaBeam3D, written with write_graph_dsl:
#   MegaBeamTrace(Mouth, Dir) -> Dist: a line trace (complex collision) along the beam's full 13.2 m. Remembers what it
#       hit (HitWhat) and where (HitAt). Sparkit (Target) and Smugshi (Shooter) don't count: the old aim logic handles
#       Sparkit. Returns 1320 when nothing solid is in the way.
#   MegaBeamBurn(Dir): every frame the beam rests on something solid. A Geometry Collection (BP shatter pillar) gets
#       strain at the hit point (20 cm: breaks the pieces there) and a gentle push (40 cm/s a frame: it adds up, 350 flung
#       the whole pillar away in a quarter second) along the beam, so the beam chews its way
#       through; a BP_MeltWall gets MeltWallBurn (melts a pit; the next trace hits its bottom).
# EventMegaBeamDraw (tools/fx3d_graphs.py MEGABEAM3D) calls both.
import json, os

TRACE = '''
(fn MegaBeamTrace (Mouth Dir)
  (bind (hit ok) (Collision|LineTraceByChannel :Start Mouth :End (+ Mouth (* Dir 1320.0)) :TraceChannel "TraceTypeQuery1" :bTraceComplex true :bIgnoreSelf true))
  (bind (bb io tm dist loc ip nrm inrm pm actor comp hbn bn hi ei fi ts te) (Collision|BreakHitResult hit))
  (bind solid (and (and ok (not io)) (and (!= actor (Variables|Default|GetTarget)) (!= actor (Variables|Default|GetShooter)))))
  (Variables|Default|SetHitWhat actor)
  (Variables|Default|SetHitAt ip)
  (return (select solid dist 1320.0)))
'''

BURN = '''
(fn MegaBeamBurn (Dir)
  (bind a (Variables|Default|GetHitWhat))
  (bind at (Variables|Default|GetHitAt))
  (bind gc (Utilities|Casting|CastToGeometryCollectionComponent :Object (Actor|GetComponentbyClass :self a :ComponentClass "/Script/GeometryCollectionEngine.GeometryCollectionComponent"))
    (:then
      (ChaosPhysics|ApplyExternalStrain :self gc :ItemIndex 0 :Location at :Radius 20.0 :PropagationDepth 0 :PropagationFactor 1.0 :Strain 3000000.0)
      (Physics|AddRadialImpulse :self gc :Origin (- at (* Dir 20.0)) :Radius 35.0 :Strength 40.0 :Falloff "RIF_Linear" :bVelChange true))
    (:CastFailed
      (bind w (Utilities|Casting|CastToBP_MeltWall :Object a)
        (:then
          (Class|BPMeltWall|MeltWallBurn :self w :Loc at :Dir Dir))
        (:CastFailed)))))
'''

if __name__ == '__main__':
    # the Unreal project is the folder next to tools/ that holds the .uproject
    import glob
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
    proj = os.path.dirname(glob.glob(os.path.join(root, '*', '*.uproject'))[0])
    os.makedirs(os.path.join(proj, 'Saved'), exist_ok=True)
    out = os.path.join(proj, 'Saved', 'beam_destruction_dsl.json')
    json.dump({'trace': TRACE, 'burn': BURN}, open(out, 'w'), indent=1)
    print('wrote', os.path.abspath(out))
