import bpy  # type: ignore
import bmesh  # type: ignore
import mathutils  # type: ignore
import sys
import json
import math
import os
import traceback

# Command line argument parsing
args = sys.argv[sys.argv.index("--") + 1 :]
params_file = os.path.abspath(args[0])
terrain_blend_path = os.path.abspath(args[1])
output_path = os.path.abspath(args[2])
preview_path = os.path.abspath(args[3])

# Setup logging to file
log_path = output_path.replace('.blend', '_road_log.txt')
log_file = open(log_path, 'w', encoding='utf-8')

def log(msg):
    """Log to both console and file"""
    print(msg)
    log_file.write(msg + '\n')
    log_file.flush()

log(f"[Road] ========== Road Generation Start ==========")
log(f"[Road] Log file: {log_path}")

# Read parameters
with open(params_file, "r") as f:
    params = json.load(f)

control_points = params.get("controlPoints", [])
road_width = params.get("width", 1.6)

log(f"[Road] Parameters: {params}")
log(f"[Road] Control points: {len(control_points)}")
log(f"[Road] Terrain file: {terrain_blend_path}")
log(f"[Road] Output: {output_path}")

# 1. Load terrain file
log(f"[Road] Loading terrain file...")
bpy.ops.wm.open_mainfile(filepath=terrain_blend_path)

# Find terrain object
terrain_obj = None
for obj in bpy.data.objects:
    if obj.type == "MESH" and "Terrain" in obj.name:
        terrain_obj = obj
        break

if not terrain_obj:
    log(f"[Road] ERROR: Terrain object not found!")
    log_file.close()
    sys.exit(1)

log(f"[Road] Found terrain: {terrain_obj.name}")

# 2. Create Bezier Curve
log(f"[Road] Creating road curve...")
curve_data = bpy.data.curves.new("RoadCurve", type="CURVE")
curve_data.dimensions = "3D"

spline = curve_data.splines.new("BEZIER")
spline.bezier_points.add(len(control_points) - 1)

# Calculate total length
total_length = 0.0
converted_points = []

for i, point in enumerate(control_points):
    # Coordinate conversion: web -> Blender (Y flipped)
    if isinstance(point, dict):
        x = (point["x"] - 50) * 10
        y = (50 - point["y"]) * 10  # Y flip
    else:
        x = (point[0] - 50) * 10
        y = (50 - point[1]) * 10  # Y flip

    converted_points.append((x, y))

    if i > 0:
        prev_x, prev_y = converted_points[i - 1]
        segment_length = math.sqrt((x - prev_x) ** 2 + (y - prev_y) ** 2)
        total_length += segment_length

log(f"[Road] Total road length: {total_length:.1f}m")

# Set Bezier points
start_z = 10000
for i, (x, y) in enumerate(converted_points):
    bp = spline.bezier_points[i]
    bp.co = (x, y, start_z)
    bp.handle_left_type = "AUTO"
    bp.handle_right_type = "AUTO"

# Create curve object
curve_obj = bpy.data.objects.new("Road", curve_data)
bpy.context.collection.objects.link(curve_obj)

# 3. Manual resampling for uniform spacing
log(f"[Road] Starting resampling process...")

sample_distance = 1.0
num_samples = max(32, int(total_length / sample_distance))
log(f"[Road] Target samples: {num_samples} (every {sample_distance}m)")

try:
    # Step 1: Set high resolution
    log(f"[Road] Step 1: Setting high resolution for sampling...")
    temp_resolution = num_samples * 4
    curve_data.resolution_u = temp_resolution
    log(f"[Road] Temporary resolution_u: {temp_resolution}")

    # Step 2: Duplicate curve
    log(f"[Road] Step 2: Creating temporary mesh copy...")
    bpy.context.view_layer.objects.active = curve_obj
    bpy.ops.object.select_all(action='DESELECT')
    curve_obj.select_set(True)

    bpy.ops.object.duplicate()
    temp_curve_obj = bpy.context.active_object
    log(f"[Road] Duplicated curve object: {temp_curve_obj.name}")

    # Step 3: Convert to mesh
    log(f"[Road] Step 3: Converting duplicate to mesh...")
    bpy.ops.object.convert(target='MESH')
    temp_mesh_obj = bpy.context.active_object
    temp_mesh = temp_mesh_obj.data
    log(f"[Road] Mesh created with {len(temp_mesh.vertices)} vertices")

    # Step 4: Sample uniformly by arc length (not by vertex count)
    log(f"[Road] Step 4: Sampling by arc length (distance-based)...")
    total_verts = len(temp_mesh.vertices)

    # Calculate cumulative arc length for each vertex
    arc_lengths = [0.0]
    for i in range(1, total_verts):
        prev_vert = temp_mesh.vertices[i - 1].co
        curr_vert = temp_mesh.vertices[i].co
        segment_length = (curr_vert - prev_vert).length
        arc_lengths.append(arc_lengths[-1] + segment_length)

    total_arc_length = arc_lengths[-1]
    log(f"[Road] Total arc length: {total_arc_length:.1f}m, vertices: {total_verts}")

    # Sample at uniform distances
    sampled_points = []
    target_distance = total_arc_length / (num_samples - 1) if num_samples > 1 else 0
    log(f"[Road] Target distance between samples: {target_distance:.2f}m")

    current_target = 0.0
    for sample_idx in range(num_samples):
        # Find closest vertex to current_target distance
        closest_idx = 0
        min_diff = abs(arc_lengths[0] - current_target)

        for vert_idx in range(1, total_verts):
            diff = abs(arc_lengths[vert_idx] - current_target)
            if diff < min_diff:
                min_diff = diff
                closest_idx = vert_idx
            elif diff > min_diff:
                # Arc lengths are monotonic, so we can break early
                break

        sampled_points.append(temp_mesh.vertices[closest_idx].co.copy())
        current_target += target_distance

    log(f"[Road] Sampled {len(sampled_points)} points by arc length")

    # Step 5: Clean up temp mesh
    log(f"[Road] Step 5: Cleaning up temporary mesh...")
    bpy.data.objects.remove(temp_mesh_obj, do_unlink=True)
    bpy.data.meshes.remove(temp_mesh)
    log(f"[Road] Temporary mesh deleted")

    # Step 6: Replace spline
    log(f"[Road] Step 6: Replacing original spline with sampled points...")
    bpy.context.view_layer.objects.active = curve_obj

    curve_data.splines.clear()
    log(f"[Road] Original spline cleared")

    new_spline = curve_data.splines.new("POLY")
    new_spline.points.add(len(sampled_points) - 1)
    log(f"[Road] New POLY spline created with {len(sampled_points)} points")

    for i, point in enumerate(sampled_points):
        new_spline.points[i].co = (point.x, point.y, point.z, 1.0)

    log(f"[Road] SUCCESS: Resampling complete with {len(sampled_points)} uniform points")

    bevel_resolution = 6
    curve_data.bevel_resolution = bevel_resolution

except Exception as e:
    log(f"[Road] ERROR: Resampling FAILED: {str(e)}")
    log(f"[Road] Traceback: {traceback.format_exc()}")
    log(f"[Road] Falling back to default resolution method...")

    target_resolution = int(total_length / 2.0)
    resolution_u = max(64, min(target_resolution, 512))
    bevel_resolution = max(4, min(int(resolution_u / 64), 8))

    curve_data.resolution_u = resolution_u
    curve_data.bevel_resolution = bevel_resolution
    log(f"[Road] Fallback resolution: {resolution_u}")

# 4. Bevel setup
log(f"[Road] Setting road width: {road_width}m")

bevel_curve_data = bpy.data.curves.new("RoadProfile", type="CURVE")
bevel_curve_data.dimensions = "2D"
bevel_spline = bevel_curve_data.splines.new("POLY")
num_segments = 10
bevel_spline.points.add(num_segments)

half_width = road_width / 2
for i in range(num_segments + 1):
    x = -half_width + (i * road_width / num_segments)
    bevel_spline.points[i].co = (x, 0, 0, 1)
bevel_spline.use_cyclic_u = False

bevel_obj = bpy.data.objects.new("RoadProfile", bevel_curve_data)
bpy.context.collection.objects.link(bevel_obj)

curve_data.bevel_mode = "OBJECT"
curve_data.bevel_object = bevel_obj
curve_data.use_fill_caps = False

log(f"[Road] Using flat bevel profile")

# 5. Shrinkwrap
log(f"[Road] Adding shrinkwrap modifier...")
modifier = curve_obj.modifiers.new("Shrinkwrap", "SHRINKWRAP")
modifier.target = terrain_obj
modifier.wrap_method = "PROJECT"
modifier.use_project_z = True
modifier.use_negative_direction = True
modifier.use_positive_direction = False
modifier.offset = 0.1
# 6. Convert to mesh
log(f"[Road] Converting curve to mesh...")
bpy.context.view_layer.objects.active = curve_obj
curve_obj.select_set(True)
bpy.ops.object.convert(target="MESH")
log(f"[Road] Curve converted to mesh")

bpy.context.view_layer.objects.active = curve_obj
mesh = curve_obj.data

# 7. UV adjustment
y_scale_factor = total_length / 10.0 * 6.0

log(f"[Road] Adjusting UV coordinates (rotate 90deg + scale Y {y_scale_factor:.1f}x)...")
bpy.ops.object.mode_set(mode="EDIT")
bm = bmesh.from_edit_mesh(mesh)
uv_layer = bm.loops.layers.uv.active

if uv_layer:
    for face in bm.faces:
        for loop in face.loops:
            uv = loop[uv_layer].uv
            u, v = uv.x, uv.y

            uv.x = -v
            uv.y = u * y_scale_factor

    bmesh.update_edit_mesh(mesh)
    log(f"[Road] UV rotated 90deg and scaled Y by {y_scale_factor:.1f}x")

bm.free()
bpy.ops.object.mode_set(mode="OBJECT")

# 8. Material
log(f"[Road] Creating texture-based road material...")
mat = bpy.data.materials.new(name="RoadMaterial")
mat.use_nodes = True
nodes = mat.node_tree.nodes
links = mat.node_tree.links

nodes.clear()

mat_output = nodes.new("ShaderNodeOutputMaterial")
mat_output.location = (600, 0)

bsdf = nodes.new("ShaderNodeBsdfPrincipled")
bsdf.location = (400, 0)
links.new(bsdf.outputs["BSDF"], mat_output.inputs["Surface"])

tex_coord = nodes.new("ShaderNodeTexCoord")
tex_coord.location = (-400, 0)

texture_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "assets",
    "roadtexture.jpg",
)
texture_path = os.path.abspath(texture_path)
log(f"[Road] Loading texture: {texture_path}")

if os.path.exists(texture_path):
    img = bpy.data.images.load(texture_path)
    img_texture = nodes.new("ShaderNodeTexImage")
    img_texture.image = img
    img_texture.location = (-200, 0)

    links.new(tex_coord.outputs["UV"], img_texture.inputs["Vector"])
    links.new(img_texture.outputs["Color"], bsdf.inputs["Base Color"])
    log(f"[Road] Texture loaded successfully")
else:
    log(f"[Road] WARNING: Texture not found at {texture_path}")
    bsdf.inputs["Base Color"].default_value = (0.1, 0.1, 0.1, 1.0)

bsdf.inputs["Roughness"].default_value = 0.85
bsdf.inputs["Specular IOR Level"].default_value = 0.3

log(f"[Road] Material created")

if curve_obj.data.materials:
    curve_obj.data.materials[0] = mat
else:
    curve_obj.data.materials.append(mat)

# 9. Render
log(f"[Road] Rendering top view...")
bpy.context.scene.render.engine = "BLENDER_EEVEE_NEXT"
bpy.context.scene.render.resolution_x = 1024
bpy.context.scene.render.resolution_y = 1024
bpy.context.scene.render.filepath = preview_path

camera = bpy.context.scene.camera
if not camera:
    bpy.ops.object.camera_add(location=(0, 0, 1800))
    camera = bpy.context.active_object
    camera.rotation_euler = (0, 0, 0)
    bpy.context.scene.camera = camera

camera.data.clip_end = 10000

bpy.ops.render.render(write_still=True)

# 10. Save
log(f"[Road] Saving blend file...")
bpy.ops.wm.save_as_mainfile(filepath=output_path)

log(f"[Road] SUCCESS: Road created at {output_path}")
log(f"[Road] Preview saved to {preview_path}")
log(f"[Road] ========== Road Generation Complete ==========")
log_file.close()
