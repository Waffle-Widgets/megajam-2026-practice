# BP_MeltWall (parent DynamicMeshActor, needs the GeometryScripting plugin): a stone wall the Mega Beam melts through
# (the owner, 2026-11-11: "instead of completely breaking it ... pierce through the object, almost like melting through
# it"). Written with write_graph_dsl; kept here as text so the graphs can be rebuilt.
#   MeltWallBuild: a 45 x 260 x 170 cm box (fresh every Play: the construction script and BeginPlay both build it), with
#                  complex-as-simple collision so traces and Coreatures hit the real, carved shape. M_MeltWall.
#   MeltWallBurn(Loc, Dir): called by BP_MegaBeam3D every frame its beam touches the wall. At most every 0.07 s it
#                  subtracts a 24 cm ball 6 cm past the hit point (Geometry Script boolean). The beam's trace then
#                  hits the bottom of the new pit, so the tunnel deepens by itself until the beam is through.
#                  Custom primitive data for the glow: 0-2 newest bite, 3 its game time, 4-6 first bite.
import json, os

BUILD = '''
(fn MeltWallBuild ()
  (bind comp (DynamicMeshActor|GetDynamicMeshComponent :self self))
  (bind mesh (DynamicMeshComponent|GetDynamicMesh :self comp))
  (DynamicMesh|Reset :self mesh)
  (GeometryScript|Primitives|AppendBox :TargetMesh mesh :DimensionX 45.0 :DimensionY 260.0 :DimensionZ 170.0 :StepsX 0 :StepsY 0 :StepsZ 0 :Origin "Base")
  (DynamicMeshComponent|SetComplexasSimpleCollisionEnabled :self comp :bEnabled true :bImmediateUpdate true)
  (Rendering|Material|SetMaterial :self comp :ElementIndex 0 :Material "/Game/Game/Materials/M_MeltWall.M_MeltWall")
  (Rendering|Material|SetCustomPrimitiveDataFloat :self comp :DataIndex 3 :Value 0.0)
  (Variables|Default|SetLastBite -10.0)
  (Variables|Default|SetBites 0))
'''

BURN = '''
(fn MeltWallBurn (Loc Dir)
  (bind now (Utilities|Time|GetGameTimeinSeconds))
  (if (> (- now (Variables|Default|GetLastBite)) 0.07)
    (Variables|Default|SetLastBite now)
    (bind comp (DynamicMeshActor|GetDynamicMeshComponent :self self))
    (bind mesh (DynamicMeshComponent|GetDynamicMesh :self comp))
    (bind tool (DynamicMeshActor|AllocateComputeMesh :self self))
    (DynamicMesh|Reset :self tool)
    (GeometryScript|Primitives|AppendSphereBox :TargetMesh tool :Radius 24.0 :StepsX 5 :StepsY 5 :StepsZ 5 :Origin "Center")
    (bind c (+ Loc (* Dir 6.0)))
    (GeometryScript|Booleans|ApplyMeshBoolean :TargetMesh mesh :TargetTransform (Transformation|GetActorTransform) :ToolMesh tool :ToolTransform (Math|Transform|MakeTransform :Location c) :Operation "Subtract")
    (DynamicMeshActor|ReleaseComputeMesh :self self :Mesh tool)
    (DynamicMeshComponent|UpdateCollision :self comp :bOnlyIfPending false)
    (Rendering|Material|SetCustomPrimitiveDataVector3 :self comp :DataIndex 0 :Value c)
    (Rendering|Material|SetCustomPrimitiveDataFloat :self comp :DataIndex 3 :Value now)
    (if (== (Variables|Default|GetBites) 0)
      (Rendering|Material|SetCustomPrimitiveDataVector3 :self comp :DataIndex 4 :Value c))
    (Variables|Default|SetBites (+ (Variables|Default|GetBites) 1))))
'''

CONSTRUCT = '''
(fn ConstructionScript ()
  (CallFunction|MeltWallBuild))
'''

EVENTS = '''
(event EventBeginPlay
  (CallFunction|MeltWallBuild))
'''

if __name__ == '__main__':
    # the Unreal project is the folder next to tools/ that holds the .uproject
    import glob
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
    proj = os.path.dirname(glob.glob(os.path.join(root, '*', '*.uproject'))[0])
    os.makedirs(os.path.join(proj, 'Saved'), exist_ok=True)
    out = os.path.join(proj, 'Saved', 'meltwall_dsl.json')
    # the construction graph is UserConstructionScript, but the DSL names it ConstructionScript
    json.dump({'build': BUILD, 'burn': BURN, 'construct': CONSTRUCT, 'events': EVENTS}, open(out, 'w'), indent=1)
    print('wrote', os.path.abspath(out))
