"""Turntable builder — parameterized for any HOME asset (GitHub production route).
Same scene/lighting/material recipe as the Mega Metagross proof
(build_turntable_adaptive.py), but the asset code, model path, texture dir and
output dir are arguments instead of hardcoded Metagross values, so each episode's
#1 form drops into the same template with no code change.

v2 (user-approved Nov 16, 2026) — pose + arc + framing revision:
  * POSE: the armature is posed out of its bind stance into the X hover-attack
    stance before rendering. Shoulder pivots only (front pair LArm/RArm,
    rear pair LArm2/RArm2 on the HOME rig): front arms splayed ~35 deg
    outward + pitched ~12 deg forward; rear arms splayed ~30 deg outward +
    pitched ~15 deg back; outer claw fingers fanned ~10 deg. Rotations are
    applied as world-frame rotations conjugated into bone-local space, so the
    numbers mean the same thing on any HOME rig with this bone naming.
  * ARC: the sequence no longer spins 360 deg (40% of the proof loop was the
    featureless back). It pendulum-sweeps a +/-50 deg front arc around the
    hero center angle with a cosine profile over one seamless loop, so the
    face / gold X / red eyes are on screen at every frame.
  * FRAMING: camera distance is fitted to the POSED model's projected
    bounding box (85-90% of frame height target) instead of the loose
    bounding-sphere fit that left the proof hero at ~55% height.
Stills mode samples the sweep itself (offsets -50/-15/+15/+50 deg) so the
GitHub stills check verifies exactly what the sequence will show.

Usage: blender -b --python build_turntable_param.py -- <mode> <engine> <samples>
         <res> <fps> <seconds> [asset_code] [glb_path] [tex_dir] [out_dir]
  mode: stills | sequence
  engine: CYCLES | EEVEE
  asset_code: HOME asset code, e.g. pm0376_51_00 (default: pm0376_51_00)
  glb_path:   path to the .glb model file (default: proof folder model file)
  tex_dir:    dir holding <asset>_BodyA/B/C_col.png + <asset>_Eye_col.png
  out_dir:    where stills/ and sequence/ go (default: this proof folder)
Texture files that do not exist for a form (e.g. no BodyC) are skipped with a
warning instead of failing the render; the material keeps its steel recipe.
Env: STILLS_RES (stills height px, default 1080) — local iteration aid only.
"""
import bpy, os, math, sys
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
MODE    = argv[0] if len(argv) > 0 else "stills"
ENGINE  = argv[1] if len(argv) > 1 else "CYCLES"
SAMPLES = int(argv[2]) if len(argv) > 2 else 64
RES     = int(argv[3]) if len(argv) > 3 else 1080
FPS     = int(argv[4]) if len(argv) > 4 else 30
SECONDS = float(argv[5]) if len(argv) > 5 else 5.0
ASSET   = argv[6] if len(argv) > 6 else "pm0376_51_00"

BASE   = os.path.abspath(argv[9]) if len(argv) > 9 else (
    os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd())
GLB    = os.path.abspath(argv[7]) if len(argv) > 7 else os.path.join(BASE, "model", "pm0376_51_00_home.glb")
TEXDIR = os.path.abspath(argv[8]) if len(argv) > 8 else os.path.join(BASE, "model", "textures")
os.makedirs(os.path.join(BASE, "stills"), exist_ok=True)
os.makedirs(os.path.join(BASE, "sequence"), exist_ok=True)
print("ASSET", ASSET, "GLB", GLB, "TEXDIR", TEXDIR, "OUT", BASE)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB)

# remove converter env-helper mesh (no materials)
for o in list(bpy.context.scene.objects):
    if o.type == 'MESH' and not o.material_slots:
        bpy.data.objects.remove(o, do_unlink=True)

meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
mins = Vector((1e9,)*3); maxs = Vector((-1e9,)*3)
for o in meshes:
    for c in o.bound_box:
        w = o.matrix_world @ Vector(c)
        mins = Vector(map(min, mins, w)); maxs = Vector(map(max, maxs, w))
center = (mins + maxs) / 2
size = maxs - mins
print("CENTER", tuple(round(v,3) for v in center), "SIZE", tuple(round(v,3) for v in size))

# ---------- materials ----------
TEXMAP = [("BodyA", f"{ASSET}_BodyA_col.png"),
          ("BodyB", f"{ASSET}_BodyB_col.png"),
          ("BodyC", f"{ASSET}_BodyC_col.png"),
          ("Eye",   f"{ASSET}_Eye_col.png")]
for mat in bpy.data.materials:
    texfile = next((f for k, f in TEXMAP if k in mat.name), None)
    mat.use_nodes = True
    nt = mat.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    if texfile:
        texpath = os.path.join(TEXDIR, texfile)
        if os.path.exists(texpath):
            img = bpy.data.images.load(texpath)
            tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = img
            nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        else:
            print("TEXTURE MISSING, skipped:", texfile)
    if "Eye" in mat.name:
        bsdf.inputs["Metallic"].default_value = 0.0
        bsdf.inputs["Roughness"].default_value = 0.3
    else:
        # polished steel: high metalness, low-mid roughness, whisper of clearcoat
        bsdf.inputs["Metallic"].default_value = 0.9
        bsdf.inputs["Roughness"].default_value = 0.3
        if "Coat Weight" in bsdf.inputs:
            bsdf.inputs["Coat Weight"].default_value = 0.25
            bsdf.inputs["Coat Roughness"].default_value = 0.3

# ---------- POSE: X hover-attack stance (shoulders only) ----------
# The bind pose hangs all four arms vertically like pillars (user audit of the
# proof). Pose the shoulder pivots into a wide X: front pair (LArm/RArm)
# splayed outward + pitched forward; rear pair (LArm2/RArm2) splayed outward +
# pitched back; outer claw fingers fanned slightly. Rotations are specified in
# the WORLD frame and conjugated into each bone's local frame
# (q_local = R0^-1 @ R_world @ R0, R0 = bone's rest world orientation), which
# keeps the angles honest regardless of the rig's local bone axes. Parent
# (Waist) stays unposed, so each shoulder's math is independent.
from mathutils import Quaternion, Vector as _V

def _bone_world_quat(arm_obj, bone_name):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = arm_obj.evaluated_get(dg)
    m = ev.matrix_world @ ev.pose.bones[bone_name].matrix
    return m.to_quaternion()

def _apply_world_rot(arm_obj, bone_name, q_world):
    pb = arm_obj.pose.bones[bone_name]
    pb.rotation_mode = 'QUATERNION'
    bpy.context.view_layer.update()
    r0 = _bone_world_quat(arm_obj, bone_name)
    pb.rotation_quaternion = r0.inverted() @ q_world @ r0
    bpy.context.view_layer.update()

def _q(axis, deg):
    return Quaternion(_V(axis), math.radians(deg))

# (bone, splay_deg about world Y [+ = tip toward -X], pitch_deg about world X [+ = tip toward +Y/back])
# Left limbs sit at +X: outward splay needs negative Y rotation; right limbs mirror.
POSE_PLAN = [
    ("LArm",  -35.0, -12.0),   # front-left:  splay out, pitch forward
    ("RArm",  +35.0, -12.0),   # front-right: splay out, pitch forward
    ("LArm2", -30.0, +15.0),   # rear-left:   splay out, pitch back
    ("RArm2", +30.0, +15.0),   # rear-right:  splay out, pitch back
]
# outer claw fingers fan open in the front/back plane (about world X):
# finger A sits forward of the hand centre, finger C behind it.
FINGER_FAN = [
    ("LFingerA1", -10.0), ("LFingerC1", +10.0),
    ("RFingerA1", -10.0), ("RFingerC1", +10.0),
    ("LFingerD1", -10.0), ("LFingerF1", +10.0),
    ("RFingerD1", -10.0), ("RFingerF1", +10.0),
]
_armatures = [o for o in bpy.context.scene.objects if o.type == 'ARMATURE']
if _armatures:
    _arm = _armatures[0]
    for _bone, _splay, _pitch in POSE_PLAN:
        if _bone in _arm.pose.bones:
            _apply_world_rot(_arm, _bone, _q((1, 0, 0), _pitch) @ _q((0, 1, 0), _splay))
            print("POSED", _bone, "splay", _splay, "pitch", _pitch)
        else:
            print("POSE SKIP (bone missing):", _bone)
    for _bone, _fan in FINGER_FAN:
        if _bone in _arm.pose.bones:
            _apply_world_rot(_arm, _bone, _q((1, 0, 0), _fan))
            print("POSED", _bone, "fan", _fan)
        else:
            print("POSE SKIP (bone missing):", _bone)
else:
    print("POSE SKIP: no armature in scene")

# ---------- turntable rig ----------
rig = bpy.data.objects.new("TurntableRig", None)
bpy.context.collection.objects.link(rig)
rig.location = (center.x, center.y, center.z)
roots = [o for o in bpy.context.scene.objects if o.parent is None and o is not rig]
for o in roots:
    o.parent = rig
    o.matrix_parent_inverse = rig.matrix_world.inverted()

ARC_CENTER = math.radians(float(os.environ.get('TURNTABLE_CENTER_DEG', 22)))
ARC_AMP = math.radians(float(os.environ.get('TURNTABLE_AMP_DEG', 50)))
rig.rotation_euler = (0, 0, ARC_CENTER)

# ---------- studio: area lights + emissive softboxes (reflections) ----------
def add_area(name, loc, energy, size_, color):
    d = bpy.data.lights.new(name, 'AREA')
    d.energy = energy; d.shape = 'DISK'; d.size = size_; d.color = color
    o = bpy.data.objects.new(name, d); bpy.context.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (center - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()

def add_softbox(name, loc, scale, emit_color, strength):
    bpy.ops.mesh.primitive_plane_add(location=loc)
    o = bpy.context.active_object; o.name = name
    o.scale = scale
    o.rotation_euler = (center - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    m = bpy.data.materials.new(name + "_mat"); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    emi = nt.nodes.new("ShaderNodeEmission")
    emi.inputs["Color"].default_value = (*emit_color, 1)
    emi.inputs["Strength"].default_value = strength
    nt.links.new(emi.outputs["Emission"], out.inputs["Surface"])
    o.data.materials.append(m)
    o.visible_camera = False          # seen only in reflections/glossy
    return o

R = max(size) * 2.4
add_area("Key",  (center.x + R*0.7,  center.y - R*0.8,  center.z + R*0.7), 1100, R*0.9, (1.0, 0.98, 0.95))
add_area("Rim",  (center.x - R*0.45, center.y + R*0.95, center.z + R*0.5), 1700, R*0.7, (0.45, 0.65, 1.0))
add_area("Fill", (center.x - R*0.85, center.y - R*0.45, center.z - R*0.1), 300,  R*0.8, (0.8, 0.88, 1.0))
add_softbox("SoftKey",   (center.x + R*0.9,  center.y - R*0.4,  center.z + R*0.55), (R*0.55, R*0.38, 1), (1.0, 0.99, 0.97), 5.0)
add_softbox("SoftStrip", (center.x - R*0.95, center.y + R*0.25, center.z + R*0.3),  (R*0.16, R*0.5, 1),  (0.5, 0.68, 1.0), 7.0)
add_softbox("SoftTop",   (center.x,          center.y,          center.z + R*1.05), (R*0.5, R*0.3, 1),   (0.85, 0.92, 1.0), 3.5)

world = bpy.data.worlds.new("World"); bpy.context.scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.012, 0.018, 0.035, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.6

# ---------- camera ----------
cam_data = bpy.data.cameras.new("Cam")
cam = bpy.data.objects.new("Cam", cam_data)
bpy.context.collection.objects.link(cam)
cam_data.lens = 55
# Frame the POSED model at hero scale (the proof's bounding-sphere fit left
# it at ~55% of frame height). The model's projected height changes as it
# yaws through the sweep (wide splayed silhouette face-on, tall narrow one
# side-on), so no single distance holds 85-90% at every angle: the camera
# distance is FIT PER ANGLE from the posed bounding box projected onto the
# camera axes, riding smoothly with the sweep. Aim point is fixed.
STILLS_H = int(os.environ.get('STILLS_RES', 1080))
res_x = STILLS_H * 16 // 9 if MODE == "stills" else RES * 16 // 9
res_y = STILLS_H if MODE == "stills" else RES
frame_aspect = res_x / res_y
vfov = 2 * math.atan((cam_data.sensor_width / frame_aspect) / (2 * cam_data.lens))
view_dir = Vector((0.5, -0.85, 0.30)).normalized()
_fwd = -view_dir
_right = (_fwd.cross(Vector((0, 0, 1)))).normalized()
_up = _right.cross(_fwd)
TARGET_H = float(os.environ.get('TURNTABLE_TARGET_H', 0.87))
# Measured on this rig (Nov 16): the union of per-mesh bounding-box corners
# overestimates the true rendered silhouette by ~13% uniformly across the
# sweep, so distances are divided by this factor to land on TARGET_H.
FIT_CALIB = 1.13

def _posed_corners():
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    cs = []
    for o in meshes:
        ev = o.evaluated_get(dg)
        for c in ev.bound_box:
            cs.append(ev.matrix_world @ Vector(c))
    return cs

def _fit_dist(corners, aim):
    pr = [(c - aim) @ _right for c in corners]
    pu = [(c - aim) @ _up for c in corners]
    er = max(pr) - min(pr); eu = max(pu) - min(pu)
    dv = (eu / 2) / (math.tan(vfov / 2) * TARGET_H)
    dh = (er / 2) / (math.tan(vfov / 2) * frame_aspect * 0.97)
    return max(dv, dh) / FIT_CALIB, er, eu

rig.rotation_euler = (0, 0, ARC_CENTER)
_aim_corners = _posed_corners()
AIM = sum(_aim_corners, Vector()) / len(_aim_corners)
_dist0, _er0, _eu0 = _fit_dist(_aim_corners, AIM)
cam.location = AIM + view_dir * _dist0
cam.rotation_euler = (AIM - cam.location).to_track_quat('-Z', 'Y').to_euler()
print("CAM fit@center dist", round(_dist0, 2), "vfov deg", round(math.degrees(vfov), 1),
      "posed ext_r", round(_er0, 2), "ext_u", round(_eu0, 2), "target_h", TARGET_H)
bpy.context.scene.camera = cam

scene = bpy.context.scene
if ENGINE == "EEVEE":
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    scene.eevee.taa_render_samples = 64
else:
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = SAMPLES
    scene.cycles.use_denoise = True
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.025
    scene.cycles.adaptive_min_samples = 8
    scene.cycles.denoiser = 'OPENIMAGEDENOISE'
    scene.cycles.max_bounces = 8
    scene.cycles.glossy_bounces = 4
    scene.cycles.transmission_bounces = 2
scene.render.film_transparent = True
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.render.resolution_x = STILLS_H * 16 // 9 if MODE == "stills" else RES * 16 // 9
scene.render.resolution_y = STILLS_H if MODE == "stills" else RES

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BASE, "turntable_scene.blend"))

if MODE == "stills":
    # Sample the sweep itself: both extremes + near-center on both sides, so
    # the stills check verifies the exact angles the sequence will show.
    samples = [(-50, "m50"), (-15, "m15"), (15, "p15"), (50, "p50")]
    for i, (off, label) in enumerate(samples):
        rig.rotation_euler = (0, 0, ARC_CENTER + math.radians(off))
        _d, _er, _eu = _fit_dist(_posed_corners(), AIM)
        cam.location = AIM + view_dir * _d
        scene.render.filepath = os.path.join(BASE, "stills", f"hero_arc_{i+1}_{label}.png")
        bpy.ops.render.render(write_still=True)
        print("STILL DONE", label, off, "dist", round(_d, 2))
else:
    n = int(FPS * SECONDS)
    scene.frame_start = 1; scene.frame_end = int(os.environ.get('SEQ_FRAMES', n))
    scene.render.fps = FPS
    # Pendulum sweep: yaw(f) = ARC_CENTER + ARC_AMP * cos(2*pi*(f-1)/n).
    # One full cosine period across the loop -> frame n wraps seamlessly to
    # frame 1; the face stays within +/-50 deg of the hero angle throughout.
    # Camera distance is keyframed per frame from the same fit, so the hero
    # holds its 85-90% frame height through the whole sweep.
    for f in range(1, n + 2):
        yaw = ARC_CENTER + ARC_AMP * math.cos(2 * math.pi * (f - 1) / n)
        rig.rotation_euler = (0, 0, yaw)
        rig.keyframe_insert(data_path="rotation_euler", index=2, frame=f)
        _d, _er, _eu = _fit_dist(_posed_corners(), AIM)
        cam.location = AIM + view_dir * _d
        cam.keyframe_insert(data_path="location", frame=f)
    # gentle levitation bob: one full sine over the loop (seamless)
    rig.location = (center.x, center.y, center.z - 0.045)
    rig.keyframe_insert(data_path="location", index=2, frame=1)
    rig.location = (center.x, center.y, center.z + 0.045)
    rig.keyframe_insert(data_path="location", index=2, frame=n // 2 + 1)
    rig.location = (center.x, center.y, center.z - 0.045)
    rig.keyframe_insert(data_path="location", index=2, frame=n + 1)
    for _o in (rig, cam):
        if _o.animation_data and _o.animation_data.action:
            for fc in _o.animation_data.action.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = 'LINEAR'
    scene.render.filepath = os.path.join(BASE, "sequence", "tt_")
    bpy.ops.render.render(animation=True)
    print("SEQUENCE DONE", n, "frames")
print("ALL DONE", MODE, ENGINE)
