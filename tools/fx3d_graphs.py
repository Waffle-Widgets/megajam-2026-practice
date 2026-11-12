# The 3D attack effects' graphs (Lvl_Meadow3D only), written with the Unreal MCP's write_graph_dsl and kept here as
# text so they can be rebuilt. The shapes and materials come from tools/unreal_make_fx3d.py.
#
# BP_Smugshi3D overrides FireFireBlast / FireMegaBeam to spawn the 3D versions and turn his 3D body to face Sparkit
# (it stays that way until he walks again); everything else (keys, cooldowns,
# targets) is BP_Smugshi's. BP_FireBlast3D, BP_FireBoom3D and BP_MegaBeam3D are children of the pixel-art effects:
# the flight, timing, lights, hit flash and shake are the same, only the look changes.

SMUGSHI3D_FIRE = '''
(event EventFireFireBlast
  (bind here (Transformation|GetActorLocation))
  (bind foes (Actor|GetAllActorsOfClass "/Game/Game/Blueprints/BP_Sparkit.BP_Sparkit_C"))
  (if (> (Utilities|Array|Length foes) 0)
    (bind foe (Utilities|Array|Get(acopy) foes 0))
    (bind aim (- (Transformation|GetActorLocation :self foe) here))
    (Transformation|SetWorldRotation :self (Variables|Default|GetBody) :NewRotation (Math|Rotator|MakeRotator :Roll 0.0 :Pitch 0.0 :Yaw (- (Math|Trig|Atan2(Degrees) (.y aim) (.x aim)) 90.0)))
    (bind shot (Game|SpawnActorfromClass "/Game/Game/Blueprints/BP_FireBlast3D.BP_FireBlast3D_C" (Math|Transform|MakeTransform :Location (+ here (* (Math|Vector|Normalize (Math|Vector|MakeVector :X (.x aim) :Y (.y aim) :Z 0.0)) 28.0))) "AlwaysSpawn" "MultiplyWithRoot"))
    (Class|BPFireBlast|LaunchFireBlast shot aim foe)))
(event EventFireMegaBeam
  (bind foes (Actor|GetAllActorsOfClass "/Game/Game/Blueprints/BP_Sparkit.BP_Sparkit_C"))
  (if (> (Utilities|Array|Length foes) 0)
    (bind foe (Utilities|Array|Get(acopy) foes 0))
    (bind aim (- (Transformation|GetActorLocation :self foe) (Transformation|GetActorLocation)))
    (Transformation|SetWorldRotation :self (Variables|Default|GetBody) :NewRotation (Math|Rotator|MakeRotator :Roll 0.0 :Pitch 0.0 :Yaw (- (Math|Trig|Atan2(Degrees) (.y aim) (.x aim)) 90.0)))
    (bind beam (Game|SpawnActorfromClass "/Game/Game/Blueprints/BP_MegaBeam3D.BP_MegaBeam3D_C" (Transformation|GetActorTransform) "AlwaysSpawn" "MultiplyWithRoot"))
    (Class|BPMegaBeam|LaunchMegaBeam beam aim foe self)))
'''

# Fire Blast drill (2026-11-11): both now draw with Niagara (FX components: NS_FireBlast3D, NS_FireBoom3D); the blob
# meshes below are kept but hidden.
# Fire Blast in flight: a lumpy flame ball (38 cm) round a hot core (22 cm), with a comet tail of three smaller flame
# blobs behind it.
# The flicker and the rising flames are the material's; the parent's Tick moves it and detonates it.
FIREBLAST3D = '''
(event EventLaunchFireBlast (NewDir NewTarget)
  (bind d (Math|Vector|Normalize (Math|Vector|MakeVector :X (.x NewDir) :Y (.y NewDir) :Z 0.0)))
  (Variables|Default|SetDir d)
  (Variables|Default|SetTarget NewTarget)
  (Variables|Default|SetLaunched true)
  (Rendering|SetVisibility :self (Variables|Default|GetBall) :bNewVisibility false)
  (Components|Activation|Activate :self (Variables|Default|GetFX) :bReset true)
  (Rendering|SetVisibility :self (Variables|Default|GetFlame) :bNewVisibility false)
  (Rendering|SetVisibility :self (Variables|Default|GetCore) :bNewVisibility false)
  (Rendering|SetVisibility :self (Variables|Default|GetTail) :bNewVisibility false)
  (Transformation|SetRelativeScale3D :self (Variables|Default|GetFlame) :NewScale3D (Math|Vector|MakeVector :X 0.38 :Y 0.38 :Z 0.38))
  (Transformation|SetRelativeScale3D :self (Variables|Default|GetCore) :NewScale3D (Math|Vector|MakeVector :X 0.22 :Y 0.22 :Z 0.22))
  (Rendering|SetVisibility :self (Variables|Default|GetTail2) :bNewVisibility false)
  (Rendering|SetVisibility :self (Variables|Default|GetTail3) :bNewVisibility false)
  (bind along (Math|Rotator|MakeRotFromX :X d))
  (Transformation|SetRelativeLocationAndRotation :self (Variables|Default|GetTail) :NewLocation (* d -19.0) :NewRotation along)
  (Transformation|SetRelativeScale3D :self (Variables|Default|GetTail) :NewScale3D (Math|Vector|MakeVector :X 0.3 :Y 0.22 :Z 0.22))
  (Transformation|SetRelativeLocationAndRotation :self (Variables|Default|GetTail2) :NewLocation (* d -33.0) :NewRotation along)
  (Transformation|SetRelativeScale3D :self (Variables|Default|GetTail2) :NewScale3D (Math|Vector|MakeVector :X 0.2 :Y 0.13 :Z 0.13))
  (Transformation|SetRelativeLocationAndRotation :self (Variables|Default|GetTail3) :NewLocation (* d -43.0) :NewRotation along)
  (Transformation|SetRelativeScale3D :self (Variables|Default|GetTail3) :NewScale3D (Math|Vector|MakeVector :X 0.12 :Y 0.07 :Z 0.07)))
(event EventDetonateFireBlast (Hit)
  (if Hit
    (Game|SpawnActorfromClass "/Game/Game/Blueprints/BP_FireBoom3D.BP_FireBoom3D_C" (Transformation|GetActorTransform :self (Variables|Default|GetTarget)) "AlwaysSpawn" "MultiplyWithRoot")
    (Class|BPCoreature|CoreatureFlash :self (Variables|Default|GetTarget))
    (Actor|DestroyActor)
    (else
      (Game|SpawnActorfromClass "/Game/Game/Blueprints/BP_FireBoom3D.BP_FireBoom3D_C" (Transformation|GetActorTransform) "AlwaysSpawn" "MultiplyWithRoot")
      (Actor|DestroyActor))))
'''

# The explosion: a fire ball that swells from 40 to 100 cm and burns away from its weakest flames, a hot core that
# burns out first, sparks that fly out and shorten, and a grey smoke puff that rises and thins. The light flash and the
# shake are the parent's (same numbers); it lasts 0.9 s instead of 0.6 so the smoke can drift.
FIREBOOM3D = '''
(event EventBeginPlay
  (Rendering|Components|Light|SetLightColor :self (Variables|Default|GetFlash) :NewLightColor (Utilities|Struct|MakeLinearColor :R 1.0 :G 0.6 :B 0.3 :A 1.0))
  (Camera|PlayWorldCameraShake "/Game/Game/Blueprints/BP_ShakeSmall.BP_ShakeSmall_C" (Transformation|GetActorLocation) 3000.0 6000.0)
  (Rendering|SetVisibility :self (Variables|Default|GetBoom) :bNewVisibility false)
  (Rendering|SetVisibility :self (Variables|Default|GetBurst) :bNewVisibility false)
  (Rendering|SetVisibility :self (Variables|Default|GetBurstCore) :bNewVisibility false)
  (Rendering|SetVisibility :self (Variables|Default|GetSparks) :bNewVisibility false)
  (Rendering|SetVisibility :self (Variables|Default|GetSmoke) :bNewVisibility false)
  (Transformation|SetWorldRotation :self (Variables|Default|GetSparks) :NewRotation (Math|Random|RandomRotator :bRoll true)))
(event EventTick (DeltaSeconds)
  (Variables|Default|SetAge (+ (Variables|Default|GetAge) DeltaSeconds))
  (bind a (Variables|Default|GetAge))
  (bind k (Math|Float|Clamp(Float) (/ a 0.6) 0.0 1.0))
  (bind e (- 1.0 (* (- 1.0 k) (- 1.0 k))))
  (bind bs (+ 0.4 (* 0.6 e)))
  (bind k2 (Math|Float|Clamp(Float) (/ a 0.9) 0.0 1.0))
  (bind ss (+ 0.3 (* 0.75 k2)))
  (Transformation|SetRelativeLocation :self (Variables|Default|GetBurst) :NewLocation (Math|Vector|MakeVector :X 0.0 :Y 0.0 :Z 8.0))
  (Transformation|SetRelativeScale3D :self (Variables|Default|GetBurst) :NewScale3D (Math|Vector|MakeVector :X bs :Y bs :Z bs))
  (Rendering|Material|SetCustomPrimitiveDataFloat :self (Variables|Default|GetBurst) :DataIndex 0 :Value (* k k))
  (Transformation|SetRelativeLocation :self (Variables|Default|GetBurstCore) :NewLocation (Math|Vector|MakeVector :X 0.0 :Y 0.0 :Z 8.0))
  (Transformation|SetRelativeScale3D :self (Variables|Default|GetBurstCore) :NewScale3D (Math|Vector|MakeVector :X (* bs 0.62) :Y (* bs 0.62) :Z (* bs 0.62)))
  (Rendering|Material|SetCustomPrimitiveDataFloat :self (Variables|Default|GetBurstCore) :DataIndex 0 :Value (Math|Float|Min(Float) (* k 1.7) 1.0))
  (Transformation|SetRelativeScale3D :self (Variables|Default|GetSparks) :NewScale3D (Math|Vector|MakeVector :X (+ 0.5 (* 1.5 e)) :Y (+ 0.5 (* 1.5 e)) :Z (+ 0.5 (* 1.5 e))))
  (Rendering|Material|SetCustomPrimitiveDataFloat :self (Variables|Default|GetSparks) :DataIndex 0 :Value k)
  (Transformation|SetRelativeLocation :self (Variables|Default|GetSmoke) :NewLocation (Math|Vector|MakeVector :X 0.0 :Y 0.0 :Z (+ 10.0 (* 70.0 k2))))
  (Transformation|SetRelativeScale3D :self (Variables|Default|GetSmoke) :NewScale3D (Math|Vector|MakeVector :X ss :Y ss :Z ss))
  (Rendering|Material|SetCustomPrimitiveDataFloat :self (Variables|Default|GetSmoke) :DataIndex 0 :Value (* k2 k2))
  (Rendering|Components|Light|SetIntensity :self (Variables|Default|GetFlash) :NewIntensity (* 150.0 (* (Math|Float|Max(Float) (- 1.0 k) 0.0) (Math|Float|Max(Float) (- 1.0 k) 0.0))))
  (if (> a 0.9)
    (Actor|DestroyActor)))
'''

# Mega Beam, same timing as BP_MegaBeam (charge 0.75 s, fire 0.9 s, the starry night from the parent's Tick):
#  charge: a gold flame orb at the mouth swelling from 10 to 32 cm, with gold sparks spinning in toward it;
#  fire:   three tubes from the mouth to the tip: a solid white-gold core (16 cm), gold energy streaks flowing along
#          it (34 cm) and thin fast swirling strands (44 cm; the pixel beam was 48 cm); a gold orb at the mouth and at the tip, and sparks
#          spinning at the impact while it hits. Embers3D (Niagara NS_BeamEmbers3D, 2026-11-10): red-orange embers
#          orbiting the beam and carried along it, from the mouth over the beam's length (User.BeamLength), on while it fires.
#          Body3D (Niagara NS_MegaBeam3D, the owner: "all particles"): the beam itself as particle ribbons (white-hot
#          core, orange glow, two red-orange spirals) and its ends (muzzle flare, tip flash, impact sparks while it hits,
#          User.Hitting), and as it fades it breaks into four thin strands that spread, peel away from the mouth and thin
#          out (User.Dissolve 0..1 from 1.47 to 2.27 s; the actor lives until 3.2 s, see megabeam_graphs.py); the painted tubes and the old orbs/star (MuzzleOrb, TipOrb, TipSparks) are kept but hidden. The tubes' length goes to the material (custom primitive data 0),
#          so the streaks keep their size. Lights, hit flash and shake as the parent.
MEGABEAM3D = '''
(event EventMegaBeamDraw
  (bind age (Variables|Default|GetAge))
  (bind d (Variables|Default|GetDir))
  (bind gt (Utilities|Time|GetGameTimeInSeconds))
  (bind mouth (+ (+ (Transformation|GetActorLocation :self (Variables|Default|GetShooter)) (* d 40.0)) (Math|Vector|MakeVector :X 0.0 :Y 0.0 :Z 10.0)))
  (bind rotz (Math|Rotator|MakeRotFromZ :Z d))
  (bind spin (Math|Rotator|MakeRotator :Roll (* gt 90.0) :Pitch 0.0 :Yaw (* gt 260.0)))
  (bind lift (Math|Vector|MakeVector :X 0.0 :Y 25.0 :Z 15.0))
  (if (< age 0.75)
    (bind k (/ age 0.75))
    (bind cs (+ 0.1 (* k 0.22)))
    (bind ss (- 1.6 (* k 1.1)))
    (Rendering|SetVisibility :self (Variables|Default|GetOrb) :bNewVisibility true)
    (Rendering|SetVisibility :self (Variables|Default|GetChargeSparks) :bNewVisibility true)
    (Transformation|SetWorldLocation :self (Variables|Default|GetOrb) :NewLocation mouth)
    (Transformation|SetWorldScale3D :self (Variables|Default|GetOrb) :NewScale (Math|Vector|MakeVector :X cs :Y cs :Z cs))
    (Transformation|SetWorldLocationAndRotation :self (Variables|Default|GetChargeSparks) :NewLocation mouth :NewRotation spin)
    (Transformation|SetWorldScale3D :self (Variables|Default|GetChargeSparks) :NewScale (Math|Vector|MakeVector :X ss :Y ss :Z ss))
    (Rendering|Material|SetCustomPrimitiveDataFloat :self (Variables|Default|GetChargeSparks) :DataIndex 0 :Value (* k 0.55))
    (Transformation|SetWorldLocation :self (Variables|Default|GetL1) :NewLocation (+ (+ mouth (* d 30.0)) (Math|Vector|MakeVector :X 0.0 :Y 25.0 :Z 40.0)))
    (Rendering|Components|Light|SetIntensity :self (Variables|Default|GetL1) :NewIntensity (* 5.0 k)))
  (if (>= age 0.75)
    (bind t (- age 0.75))
    (bind out (Math|Float|Min(Float) (/ t 0.14) 1.0))
    (bind fade (Math|Float|Clamp(Float) (/ (- 0.9 t) 0.15) 0.0 1.0))
    (bind tgt (- (Transformation|GetActorLocation :self (Variables|Default|GetTarget)) mouth))
    (bind along (Math|Vector|DotProduct :A tgt :B d))
    (bind side (Math|Vector|VectorLengthXY (- tgt (* d along))))
    (bind inline (and (> along 0.0) (< side 45.0)))
    (bind reach (select inline (- along 4.0) 1320.0))
    (bind shooting (< (* 1320.0 out) reach))
    (bind len (Math|Float|Max(Float) (Math|Float|Min(Float) (* 1320.0 out) reach) 1.0))
    (bind s (* (+ 0.3 (* 0.7 fade)) (+ 1.0 (* 0.08 (Math|Trig|Sin(Radians) (* gt 22.0))))))
    (bind ms (* s (+ 0.95 (* 0.08 (Math|Trig|Sin(Radians) (* gt 30.0))))))
    (bind ts (* s (select shooting 1.0 1.15)))
    (bind lit (* 12.0 (* out fade)))
    (bind on (> fade 0.0))
    (bind hitting (and inline (not shooting)))
    (bind mid (+ mouth (* d (* len 0.5))))
    (bind tip (+ mouth (* d len)))
    (bind lz (/ len 100.0))
    (Rendering|SetVisibility :self (Variables|Default|GetOrb) :bNewVisibility false)
    (Rendering|SetVisibility :self (Variables|Default|GetChargeSparks) :bNewVisibility false)
    (Rendering|SetVisibility :self (Variables|Default|GetCore3D) :bNewVisibility false)
    (Rendering|SetVisibility :self (Variables|Default|GetShell3D) :bNewVisibility false)
    (Rendering|SetVisibility :self (Variables|Default|GetSwirl3D) :bNewVisibility false)
    (Transformation|SetWorldLocationAndRotation :self (Variables|Default|GetBody3D) :NewLocation mouth :NewRotation rotz)
    (Niagara|SetNiagaraVariable(Float) :self (Variables|Default|GetBody3D) :InVariableName "BeamLength" :InValue len)
    (Niagara|SetNiagaraVariable(Float) :self (Variables|Default|GetBody3D) :InVariableName "Thick" :InValue (select on s 0.0))
    (Niagara|SetNiagaraVariable(Float) :self (Variables|Default|GetBody3D) :InVariableName "Hitting" :InValue (select (and on hitting) 1.0 0.0))
    (bind dis (Math|Float|Clamp(Float) (/ (- t 0.72) 0.8) 0.0 1.0))
    (Niagara|SetNiagaraVariable(Float) :self (Variables|Default|GetBody3D) :InVariableName "Dissolve" :InValue dis)
    (if on (Components|Activation|Activate :self (Variables|Default|GetBody3D) :bReset false))
    (if (>= dis 1.0) (Components|Activation|Deactivate :self (Variables|Default|GetBody3D)))
    (Rendering|SetVisibility :self (Variables|Default|GetMuzzleOrb) :bNewVisibility false)
    (Rendering|SetVisibility :self (Variables|Default|GetTipOrb) :bNewVisibility false)
    (Rendering|SetVisibility :self (Variables|Default|GetTipSparks) :bNewVisibility false)
    (Transformation|SetWorldLocationAndRotation :self (Variables|Default|GetCore3D) :NewLocation mid :NewRotation rotz)
    (Transformation|SetWorldScale3D :self (Variables|Default|GetCore3D) :NewScale (Math|Vector|MakeVector :X (* 0.16 s) :Y (* 0.16 s) :Z lz))
    (Rendering|Material|SetCustomPrimitiveDataFloat :self (Variables|Default|GetCore3D) :DataIndex 0 :Value len)
    (Transformation|SetWorldLocationAndRotation :self (Variables|Default|GetShell3D) :NewLocation mid :NewRotation rotz)
    (Transformation|SetWorldScale3D :self (Variables|Default|GetShell3D) :NewScale (Math|Vector|MakeVector :X (* 0.34 s) :Y (* 0.34 s) :Z lz))
    (Rendering|Material|SetCustomPrimitiveDataFloat :self (Variables|Default|GetShell3D) :DataIndex 0 :Value len)
    (Transformation|SetWorldLocationAndRotation :self (Variables|Default|GetSwirl3D) :NewLocation mid :NewRotation rotz)
    (Transformation|SetWorldScale3D :self (Variables|Default|GetSwirl3D) :NewScale (Math|Vector|MakeVector :X (* 0.44 s) :Y (* 0.44 s) :Z lz))
    (Rendering|Material|SetCustomPrimitiveDataFloat :self (Variables|Default|GetSwirl3D) :DataIndex 0 :Value len)
    (Transformation|SetWorldLocationAndRotation :self (Variables|Default|GetEmbers3D) :NewLocation mouth :NewRotation rotz)
    (Niagara|SetNiagaraVariable(Float) :self (Variables|Default|GetEmbers3D) :InVariableName "BeamLength" :InValue len)
    (if on (Components|Activation|Activate :self (Variables|Default|GetEmbers3D) :bReset false))
    (if (not on) (Components|Activation|Deactivate :self (Variables|Default|GetEmbers3D)))
    (Transformation|SetWorldLocation :self (Variables|Default|GetMuzzleOrb) :NewLocation mouth)
    (Transformation|SetWorldScale3D :self (Variables|Default|GetMuzzleOrb) :NewScale (Math|Vector|MakeVector :X (* 0.38 ms) :Y (* 0.38 ms) :Z (* 0.38 ms)))
    (Transformation|SetWorldLocation :self (Variables|Default|GetTipOrb) :NewLocation tip)
    (Transformation|SetWorldScale3D :self (Variables|Default|GetTipOrb) :NewScale (Math|Vector|MakeVector :X (* 0.36 ts) :Y (* 0.36 ts) :Z (* 0.36 ts)))
    (Transformation|SetWorldLocationAndRotation :self (Variables|Default|GetTipSparks) :NewLocation tip :NewRotation spin)
    (Transformation|SetWorldScale3D :self (Variables|Default|GetTipSparks) :NewScale (Math|Vector|MakeVector :X (* 1.2 ts) :Y (* 1.2 ts) :Z (* 1.2 ts)))
    (Rendering|Material|SetCustomPrimitiveDataFloat :self (Variables|Default|GetTipSparks) :DataIndex 0 :Value (* 0.25 (+ 1.0 (Math|Trig|Sin(Radians) (* gt 37.0)))))
    (Transformation|SetWorldLocation :self (Variables|Default|GetL1) :NewLocation (+ (+ mouth (* d (* len 0.12))) lift))
    (Transformation|SetWorldLocation :self (Variables|Default|GetL2) :NewLocation (+ mid lift))
    (Transformation|SetWorldLocation :self (Variables|Default|GetL3) :NewLocation (+ (+ mouth (* d (* len 0.88))) lift))
    (Rendering|Components|Light|SetIntensity :self (Variables|Default|GetL1) :NewIntensity lit)
    (Rendering|Components|Light|SetIntensity :self (Variables|Default|GetL2) :NewIntensity lit)
    (Rendering|Components|Light|SetIntensity :self (Variables|Default|GetL3) :NewIntensity lit)
    (if (and hitting (not (Variables|Default|GetHit)))
      (Variables|Default|SetHit true)
      (Class|BPCoreature|CoreatureFlash :self (Variables|Default|GetTarget))
      (Camera|PlayWorldCameraShake "/Game/Game/Blueprints/BP_ShakeSmall.BP_ShakeSmall_C" mouth 3000.0 6000.0))))
'''
