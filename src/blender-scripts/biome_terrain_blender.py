import bpy
import sys
import os
import math
import json
import traceback

# 로그 파일 설정
LOG_FILE = None


def log(message):
    """콘솔과 파일에 동시 출력"""
    print(message)
    if LOG_FILE:
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(message + "\n")
        except:
            pass


# 커맨드라인 인자 파싱

argv = sys.argv
argv = argv[argv.index("--") + 1 :]

if len(argv) < 4:
    print(
        "Usage: blender --background --python biome_terrain_blender.py -- <image_dir> <params_file> <output_blend> <preview_path>"
    )
    sys.exit(1)

IMAGE_DIR = argv[0]
PARAMS_FILE = argv[1]
OUTPUT_BLEND = argv[2]
PREVIEW_PATH = argv[3]

# 로그 파일 경로 설정
LOG_FILE = PREVIEW_PATH.replace(".png", "_log.txt")

# 로그 파일 초기화
with open(LOG_FILE, "w", encoding="utf-8") as f:
    f.write("=== Biome Terrain Blender Log ===\n\n")

log(f"[Biome Terrain] Image Directory: {IMAGE_DIR}")
log(f"[Biome Terrain] Parameters: {PARAMS_FILE}")
log(f"[Biome Terrain] Output: {OUTPUT_BLEND}")
log(f"[Biome Terrain] Preview: {PREVIEW_PATH}")
log(f"[Biome Terrain] Log File: {LOG_FILE}")

# 파라미터 로드

try:
    with open(PARAMS_FILE, "r", encoding="utf-8") as f:
        params = json.load(f)
    log(f"✅ Parameters loaded")
except Exception as e:
    log(f"❌ Failed to load parameters: {e}")
    log(traceback.format_exc())
    sys.exit(1)

# 기본값
base_size = 100
grid_subdivisions = params.get("grid_subdivisions", 200)
terrain_scale = params.get("terrain_scale", 10)  # 10배 = 1km
height_multiplier = params.get("height_multiplier", 30)
z_scale = params.get("z_scale", 3)

noise_scale = params.get("noise_scale", 0.05)
noise_detail = params.get("noise_detail", 5.0)

erosion_strength = params.get("erosion_strength", 20.0)
continentalness_strength = params.get("continentalness_strength", 10.0)
weirdness_strength = params.get("weirdness_strength", 5.0)
temperature_influence = params.get("temperature_influence", 0.2)

final_size = base_size * terrain_scale
max_height = height_multiplier * z_scale

log(f"[Biome Terrain] Grid: {grid_subdivisions}×{grid_subdivisions}")
log(f"[Biome Terrain] Final size: {final_size}m × {final_size}m")
log("")
log("🔥 Height System V2:")
log("  Phase 1: Parameter Redefinition")
log("    - Continentalness: -1~1 → -50m~1500m (actual elevation)")
log("    - Erosion: 0~1 → 0~400m (height variation range)")
log("    - Temperature: removed from height (material only)")
log("  Phase 2: Multi-Octave Noise")
log("    - Octave 1 (50%): scale=0.01 (100m features)")
log("    - Octave 2 (30%): scale=0.05 (20m features)")
log("    - Octave 3 (15%): scale=0.2 (5m features)")
log("    - Octave 4 (5%): scale=1.0 (1m details)")
log("")

# 메인 실행 (에러 캡처)

try:
    # 1. 기존 객체 삭제

    log("[1] Deleting existing objects...")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    log("✅ Objects deleted")

    # =============================================================================
    # 2. 그리드 메시 생성
    # =============================================================================

    log("[2] Creating grid mesh...")
    bpy.ops.mesh.primitive_grid_add(
        x_subdivisions=grid_subdivisions,
        y_subdivisions=grid_subdivisions,
        size=base_size,
        location=(0, 0, 0),
    )

    terrain_obj = bpy.context.active_object
    terrain_obj.name = "BiomeTerrain"
    mesh = terrain_obj.data

    log(
        f"✅ Grid mesh: {grid_subdivisions}×{grid_subdivisions} = {len(mesh.vertices):,} vertices"
    )

    # =============================================================================
    # 3. 바이옴 이미지 로드
    # =============================================================================

    log("[3] Loading biome images...")
    param_names = [
        "temperature",
        "humidity",
        "erosion",
        "continentalness",
        "weirdness",
        "vegetation_color_r",
        "vegetation_color_g",
        "vegetation_color_b",
        "ground_color_r",
        "ground_color_g",
        "ground_color_b",
        "snow_start_height",
        "rock_exposure",
    ]

    loaded_images = {}

    for param_name in param_names:
        img_path = os.path.join(IMAGE_DIR, f"biome_{param_name}.png")
        if os.path.exists(img_path):
            # 이미 로드된 이미지가 있으면 제거
            if f"biome_{param_name}" in bpy.data.images:
                bpy.data.images.remove(bpy.data.images[f"biome_{param_name}"])

            img = bpy.data.images.load(img_path)
            img.name = f"biome_{param_name}"
            loaded_images[param_name] = img
            log(f"✅ Loaded: {param_name} ({img.size[0]}x{img.size[1]})")
        else:
            log(f"❌ Not found: {img_path}")

    # =============================================================================
    # 4. Geometry Nodes 모디파이어 추가
    # =============================================================================

    log("[4] Creating Geometry Nodes modifier...")
    # Geometry Nodes 모디파이어 생성
    modifier = terrain_obj.modifiers.new(name="BiomeTerrainGenerator", type="NODES")

    # Node Group 생성
    node_group = bpy.data.node_groups.new(name="BiomeTerrain", type="GeometryNodeTree")
    modifier.node_group = node_group

    # Input/Output 노드
    nodes = node_group.nodes
    links = node_group.links

    group_input = nodes.new("NodeGroupInput")
    group_output = nodes.new("NodeGroupOutput")

    group_input.location = (-1000, 0)
    group_output.location = (1000, 0)

    # Input/Output 소켓 정의
    node_group.interface.new_socket(
        name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry"
    )
    node_group.interface.new_socket(
        name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry"
    )

    # =============================================================================
    # 5. Geometry Nodes 그래프 생성
    # =============================================================================

    log("[5] Building Geometry Nodes graph...")
    # Position 노드
    position_node = nodes.new("GeometryNodeInputPosition")
    position_node.location = (-800, 0)

    # Separate XYZ
    separate_xyz = nodes.new("ShaderNodeSeparateXYZ")
    separate_xyz.location = (-600, 0)
    links.new(position_node.outputs["Position"], separate_xyz.inputs["Vector"])

    # Normalize X, Y to 0~1
    # ⚠️ IMPORTANT: final_size 사용 (terrain_scale 적용 후 크기)
    # 스케일 적용 후 메시는 -final_size/2 ~ final_size/2 범위
    half_final_size = final_size / 2.0

    add_x_node = nodes.new("ShaderNodeMath")
    add_x_node.operation = "ADD"
    add_x_node.inputs[1].default_value = half_final_size
    add_x_node.location = (-400, 200)
    links.new(separate_xyz.outputs["X"], add_x_node.inputs[0])

    divide_x_node = nodes.new("ShaderNodeMath")
    divide_x_node.operation = "DIVIDE"
    divide_x_node.inputs[1].default_value = final_size
    divide_x_node.location = (-200, 200)
    links.new(add_x_node.outputs["Value"], divide_x_node.inputs[0])

    add_y_node = nodes.new("ShaderNodeMath")
    add_y_node.operation = "ADD"
    add_y_node.inputs[1].default_value = half_final_size
    add_y_node.location = (-400, 0)
    links.new(separate_xyz.outputs["Y"], add_y_node.inputs[0])

    divide_y_node = nodes.new("ShaderNodeMath")
    divide_y_node.operation = "DIVIDE"
    divide_y_node.inputs[1].default_value = final_size
    divide_y_node.location = (-200, 0)
    links.new(add_y_node.outputs["Value"], divide_y_node.inputs[0])

    # Combine XY for UV
    combine_xy = nodes.new("ShaderNodeCombineXYZ")
    combine_xy.location = (0, 100)
    links.new(divide_x_node.outputs["Value"], combine_xy.inputs["X"])
    links.new(divide_y_node.outputs["Value"], combine_xy.inputs["Y"])

    # =============================================================================
    # 6. Image Texture 샘플링 및 Attribute 저장
    # =============================================================================

    # 각 파라미터에 대해 Image Texture + Map Range + Store Named Attribute
    current_y = 500

    # 지형 높이에 사용할 파라미터만 로드 (temperature, erosion, continentalness, weirdness)
    height_params = ["temperature", "erosion", "continentalness", "weirdness"]

    stored_attributes = {}

    for param_name in height_params:
        if param_name not in loaded_images:
            continue

        # Image Texture 노드
        img_tex_node = nodes.new("GeometryNodeImageTexture")
        img_tex_node.location = (200, current_y)
        # Blender 4.5+에서는 inputs['Image']로 이미지 설정
        img_tex_node.inputs["Image"].default_value = loaded_images[param_name]
        # interpolation은 extension_type으로 변경됨
        img_tex_node.extension = "EXTEND"
        links.new(combine_xy.outputs["Vector"], img_tex_node.inputs["Vector"])

        # Map Range (0~1 이미지 값을 파라미터 범위로 변환)
        map_range = nodes.new("ShaderNodeMapRange")
        map_range.location = (400, current_y)

        if param_name in ["temperature", "continentalness"]:
            # 0~1 → -1~1
            map_range.inputs["From Min"].default_value = 0.0
            map_range.inputs["From Max"].default_value = 1.0
            map_range.inputs["To Min"].default_value = -1.0
            map_range.inputs["To Max"].default_value = 1.0
        else:
            # 0~1 → 0~1 (그대로)
            map_range.inputs["From Min"].default_value = 0.0
            map_range.inputs["From Max"].default_value = 1.0
            map_range.inputs["To Min"].default_value = 0.0
            map_range.inputs["To Max"].default_value = 1.0

        links.new(img_tex_node.outputs["Color"], map_range.inputs["Value"])

        # Store Named Attribute
        store_attr = nodes.new("GeometryNodeStoreNamedAttribute")
        store_attr.location = (600, current_y)
        store_attr.data_type = "FLOAT"
        store_attr.domain = "POINT"
        store_attr.inputs["Name"].default_value = param_name

        links.new(map_range.outputs["Result"], store_attr.inputs["Value"])

        # 체인 연결 (Input → Store Attr → Output)
        if not stored_attributes:
            # 첫 번째
            links.new(group_input.outputs["Geometry"], store_attr.inputs["Geometry"])
        else:
            # 이전 노드에서 연결
            prev_node = list(stored_attributes.values())[-1]
            links.new(prev_node.outputs["Geometry"], store_attr.inputs["Geometry"])

        stored_attributes[param_name] = store_attr

        current_y -= 300

    # =============================================================================
    # 7. Named Attribute 읽기 + Noise Texture + 지형 높이 계산
    # =============================================================================

    last_store_node = list(stored_attributes.values())[-1]

    # Named Attributes
    attr_temp = nodes.new("GeometryNodeInputNamedAttribute")
    attr_temp.location = (800, 400)
    attr_temp.data_type = "FLOAT"
    attr_temp.inputs["Name"].default_value = "temperature"

    attr_erosion = nodes.new("GeometryNodeInputNamedAttribute")
    attr_erosion.location = (800, 200)
    attr_erosion.data_type = "FLOAT"
    attr_erosion.inputs["Name"].default_value = "erosion"

    attr_continentalness = nodes.new("GeometryNodeInputNamedAttribute")
    attr_continentalness.location = (800, 0)
    attr_continentalness.data_type = "FLOAT"
    attr_continentalness.inputs["Name"].default_value = "continentalness"

    attr_weirdness = nodes.new("GeometryNodeInputNamedAttribute")
    attr_weirdness.location = (800, -200)
    attr_weirdness.data_type = "FLOAT"
    attr_weirdness.inputs["Name"].default_value = "weirdness"

    # =========================================================================
    # Phase 2: Multi-Octave Noise System
    # =========================================================================

    # Octave 1: Large-scale features (산맥, 계곡)
    noise_octave_1 = nodes.new("ShaderNodeTexNoise")
    noise_octave_1.location = (1000, -200)
    noise_octave_1.inputs["Scale"].default_value = 0.01  # 매우 큰 스케일 (100m 단위)
    noise_octave_1.inputs["Detail"].default_value = 2.0
    noise_octave_1.inputs["Roughness"].default_value = 0.5
    links.new(position_node.outputs["Position"], noise_octave_1.inputs["Vector"])

    # Octave 2: Medium features (개별 산봉우리)
    noise_octave_2 = nodes.new("ShaderNodeTexNoise")
    noise_octave_2.location = (1000, -350)
    noise_octave_2.inputs["Scale"].default_value = 0.05  # 현재 스케일 유지 (20m 단위)
    noise_octave_2.inputs["Detail"].default_value = 4.0
    noise_octave_2.inputs["Roughness"].default_value = 0.6
    links.new(position_node.outputs["Position"], noise_octave_2.inputs["Vector"])

    # Octave 3: Small features (언덕, 구릉)
    noise_octave_3 = nodes.new("ShaderNodeTexNoise")
    noise_octave_3.location = (1000, -500)
    noise_octave_3.inputs["Scale"].default_value = 0.2  # 작은 스케일 (5m 단위)
    noise_octave_3.inputs["Detail"].default_value = 5.0
    noise_octave_3.inputs["Roughness"].default_value = 0.7
    links.new(position_node.outputs["Position"], noise_octave_3.inputs["Vector"])

    # Octave 4: Micro details (바위, 표면 요철)
    noise_octave_4 = nodes.new("ShaderNodeTexNoise")
    noise_octave_4.location = (1000, -650)
    noise_octave_4.inputs["Scale"].default_value = 1.0  # 매우 작은 스케일 (1m 단위)
    noise_octave_4.inputs["Detail"].default_value = 6.0
    noise_octave_4.inputs["Roughness"].default_value = 0.8
    links.new(position_node.outputs["Position"], noise_octave_4.inputs["Vector"])

    # Octave 1 * 0.50
    multiply_octave_1 = nodes.new("ShaderNodeMath")
    multiply_octave_1.operation = "MULTIPLY"
    multiply_octave_1.inputs[1].default_value = 0.50
    multiply_octave_1.location = (1150, -200)
    links.new(noise_octave_1.outputs["Fac"], multiply_octave_1.inputs[0])

    # Octave 2 * 0.30
    multiply_octave_2 = nodes.new("ShaderNodeMath")
    multiply_octave_2.operation = "MULTIPLY"
    multiply_octave_2.inputs[1].default_value = 0.30
    multiply_octave_2.location = (1150, -350)
    links.new(noise_octave_2.outputs["Fac"], multiply_octave_2.inputs[0])

    # Octave 3 * 0.15
    multiply_octave_3 = nodes.new("ShaderNodeMath")
    multiply_octave_3.operation = "MULTIPLY"
    multiply_octave_3.inputs[1].default_value = 0.15
    multiply_octave_3.location = (1150, -500)
    links.new(noise_octave_3.outputs["Fac"], multiply_octave_3.inputs[0])

    # Octave 4 * 0.05
    multiply_octave_4 = nodes.new("ShaderNodeMath")
    multiply_octave_4.operation = "MULTIPLY"
    multiply_octave_4.inputs[1].default_value = 0.05
    multiply_octave_4.location = (1150, -650)
    links.new(noise_octave_4.outputs["Fac"], multiply_octave_4.inputs[0])

    # Add Octave 1 + 2
    add_octave_12 = nodes.new("ShaderNodeMath")
    add_octave_12.operation = "ADD"
    add_octave_12.location = (1300, -275)
    links.new(multiply_octave_1.outputs["Value"], add_octave_12.inputs[0])
    links.new(multiply_octave_2.outputs["Value"], add_octave_12.inputs[1])

    # Add Octave 3 + 4
    add_octave_34 = nodes.new("ShaderNodeMath")
    add_octave_34.operation = "ADD"
    add_octave_34.location = (1300, -575)
    links.new(multiply_octave_3.outputs["Value"], add_octave_34.inputs[0])
    links.new(multiply_octave_4.outputs["Value"], add_octave_34.inputs[1])

    # Combined Noise = Octave 1+2+3+4
    combined_noise = nodes.new("ShaderNodeMath")
    combined_noise.operation = "ADD"
    combined_noise.location = (1450, -400)
    links.new(add_octave_12.outputs["Value"], combined_noise.inputs[0])
    links.new(add_octave_34.outputs["Value"], combined_noise.inputs[1])

    # Noise Texture (weirdness용)
    noise_weird = nodes.new("ShaderNodeTexNoise")
    noise_weird.location = (1000, -800)
    noise_weird.inputs["Scale"].default_value = 0.1
    noise_weird.inputs["Detail"].default_value = 3.0
    links.new(position_node.outputs["Position"], noise_weird.inputs["Vector"])

    # =========================================================================
    # Phase 1 개선: Continentalness → 실제 고도, Erosion → 변동폭
    # =========================================================================

    # STEP 1: Continentalness를 실제 해발고도로 변환
    # -1~1 → -50m~1500m (스케일 조정: 3000m→1500m)
    map_continentalness = nodes.new("ShaderNodeMapRange")
    map_continentalness.location = (1200, 0)
    map_continentalness.inputs["From Min"].default_value = -1.0
    map_continentalness.inputs["From Max"].default_value = 1.0
    map_continentalness.inputs["To Min"].default_value = -50.0
    map_continentalness.inputs["To Max"].default_value = 1500.0
    links.new(attr_continentalness.outputs["Attribute"], map_continentalness.inputs["Value"])

    # STEP 2: Erosion을 높이 변동 범위로 변환
    # 0~1 → 0~400m (스케일 조정: 800m→400m)
    map_erosion = nodes.new("ShaderNodeMapRange")
    map_erosion.location = (1200, 200)
    map_erosion.inputs["From Min"].default_value = 0.0
    map_erosion.inputs["From Max"].default_value = 1.0
    map_erosion.inputs["To Min"].default_value = 0.0
    map_erosion.inputs["To Max"].default_value = 400.0
    links.new(attr_erosion.outputs["Attribute"], map_erosion.inputs["Value"])

    # STEP 3: Combined Multi-Octave Noise와 Erosion 범위를 곱셈
    # height_variation = combined_noise * erosion_range
    multiply_noise_erosion = nodes.new("ShaderNodeMath")
    multiply_noise_erosion.operation = "MULTIPLY"
    multiply_noise_erosion.location = (1600, 200)
    links.new(combined_noise.outputs["Value"], multiply_noise_erosion.inputs[0])
    links.new(map_erosion.outputs["Result"], multiply_noise_erosion.inputs[1])

    # STEP 4: Weirdness 효과 (기존 유지, 나중에 Phase 3에서 개선)
    multiply_weird_noise = nodes.new("ShaderNodeMath")
    multiply_weird_noise.operation = "MULTIPLY"
    multiply_weird_noise.location = (1200, -200)
    links.new(attr_weirdness.outputs["Attribute"], multiply_weird_noise.inputs[0])
    links.new(noise_weird.outputs["Fac"], multiply_weird_noise.inputs[1])

    multiply_weirdness_strength = nodes.new("ShaderNodeMath")
    multiply_weirdness_strength.operation = "MULTIPLY"
    multiply_weirdness_strength.inputs[1].default_value = weirdness_strength
    multiply_weirdness_strength.location = (1400, -200)
    links.new(
        multiply_weird_noise.outputs["Value"], multiply_weirdness_strength.inputs[0]
    )

    # STEP 5: 최종 높이 합성
    # final_height = base_height (continentalness) + height_variation (noise * erosion) + weirdness

    # base_height + height_variation
    add_base_variation = nodes.new("ShaderNodeMath")
    add_base_variation.operation = "ADD"
    add_base_variation.location = (1600, 100)
    links.new(map_continentalness.outputs["Result"], add_base_variation.inputs[0])
    links.new(multiply_noise_erosion.outputs["Value"], add_base_variation.inputs[1])

    # + weirdness
    add_weirdness = nodes.new("ShaderNodeMath")
    add_weirdness.operation = "ADD"
    add_weirdness.location = (1800, 100)
    links.new(add_base_variation.outputs["Value"], add_weirdness.inputs[0])
    links.new(multiply_weirdness_strength.outputs["Value"], add_weirdness.inputs[1])

    # ⚠️ Phase 1.3: Temperature는 높이 계산에서 제거!
    # Temperature는 Material에서만 사용 (눈선 계산)
    # 최종 높이 = add_weirdness 결과
    final_height = add_weirdness

    # =============================================================================
    # 8. Set Position (Z offset)
    # =============================================================================

    combine_offset = nodes.new("ShaderNodeCombineXYZ")
    combine_offset.location = (2000, 100)
    combine_offset.inputs["X"].default_value = 0.0
    combine_offset.inputs["Y"].default_value = 0.0
    links.new(final_height.outputs["Value"], combine_offset.inputs["Z"])

    set_position = nodes.new("GeometryNodeSetPosition")
    set_position.location = (2200, 0)
    links.new(last_store_node.outputs["Geometry"], set_position.inputs["Geometry"])
    links.new(combine_offset.outputs["Vector"], set_position.inputs["Offset"])

    # =============================================================================
    # 9. Set Shade Smooth
    # =============================================================================

    set_smooth = nodes.new("GeometryNodeSetShadeSmooth")
    set_smooth.location = (2600, 0)
    set_smooth.inputs["Shade Smooth"].default_value = True
    links.new(set_position.outputs["Geometry"], set_smooth.inputs["Geometry"])

    # Output 연결
    links.new(set_smooth.outputs["Geometry"], group_output.inputs["Geometry"])

    log("✅ Geometry Nodes graph created")

    # =============================================================================
    # 10. Material 추가 (간단한 높이 기반 색상)
    # =============================================================================

    material = bpy.data.materials.new(name="BiomeTerrainMaterial")
    material.use_nodes = True
    material_nodes = material.node_tree.nodes
    material_links = material.node_tree.links

    # 기존 노드 삭제
    material_nodes.clear()

    # Output
    mat_output = material_nodes.new("ShaderNodeOutputMaterial")
    mat_output.location = (400, 0)

    # Principled BSDF
    bsdf = material_nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (200, 0)

    # ColorRamp (높이 기반 색상)
    color_ramp = material_nodes.new("ShaderNodeValToRGB")
    color_ramp.location = (0, 0)
    color_ramp.color_ramp.elements[0].color = (0.2, 0.15, 0.1, 1.0)  # 낮은 곳: 갈색
    color_ramp.color_ramp.elements[1].color = (0.9, 0.9, 0.9, 1.0)  # 높은 곳: 흰색

    # Position Z
    position_mat = material_nodes.new("ShaderNodeNewGeometry")
    position_mat.location = (-400, 0)

    separate_xyz_mat = material_nodes.new("ShaderNodeSeparateXYZ")
    separate_xyz_mat.location = (-200, 0)

    material_links.new(
        position_mat.outputs["Position"], separate_xyz_mat.inputs["Vector"]
    )
    material_links.new(separate_xyz_mat.outputs["Z"], color_ramp.inputs["Fac"])
    material_links.new(color_ramp.outputs["Color"], bsdf.inputs["Base Color"])
    material_links.new(bsdf.outputs["BSDF"], mat_output.inputs["Surface"])

    # Material 할당
    if terrain_obj.data.materials:
        terrain_obj.data.materials[0] = material
    else:
        terrain_obj.data.materials.append(material)

    log("✅ Material created and assigned")

    # =============================================================================
    # 10.5. Terrain Scale 적용
    # =============================================================================

    log("[10.5] Applying terrain scale...")
    bpy.context.view_layer.objects.active = terrain_obj
    terrain_obj.select_set(True)

    terrain_obj.scale = (terrain_scale, terrain_scale, z_scale)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    final_size = base_size * terrain_scale
    max_height = height_multiplier * z_scale

    log(f"✅ Scale applied: XY={terrain_scale}x, Z={z_scale}x")
    log(f"   Final size: {final_size:,}m × {final_size:,}m × {max_height}m")

    # =============================================================================
    # 10.6. Geometry Nodes Modifier Apply
    # =============================================================================

    log("[10.6] Applying Geometry Nodes modifier...")
    bpy.context.view_layer.objects.active = terrain_obj
    terrain_obj.select_set(True)

    # Modifier 적용 전 상태 확인
    log(f"Before apply - Vertex count: {len(terrain_obj.data.vertices):,}")
    log(f"Before apply - Modifiers: {[m.name for m in terrain_obj.modifiers]}")

    # Modifier를 실제 메시로 적용
    for modifier in terrain_obj.modifiers:
        if modifier.type == "NODES":
            log(f"   Applying modifier: {modifier.name}")
            try:
                bpy.ops.object.modifier_apply(modifier=modifier.name)
                log(f"   ✅ Modifier applied successfully")
            except Exception as e:
                log(f"   ❌ Failed to apply modifier: {e}")

    log(f"After apply - Vertex count: {len(terrain_obj.data.vertices):,}")
    log(f"After apply - Mesh bounds: {terrain_obj.dimensions}")

    # 메시 검증
    if len(terrain_obj.data.vertices) == 0:
        log(f"❌ ERROR: Mesh has no vertices after modifier apply!")
    if len(terrain_obj.data.polygons) == 0:
        log(f"❌ ERROR: Mesh has no faces after modifier apply!")

    # =============================================================================
    # 11. 카메라 설정 (Orthographic Top-Down)
    # =============================================================================

    log("[11] Setting up camera...")
    camera_height = final_size * 1.5
    bpy.ops.object.camera_add(location=(0, 0, camera_height))
    camera = bpy.context.active_object
    camera.rotation_euler = (0, 0, 0)
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = final_size * 1.0
    camera.data.clip_end = final_size * 5
    bpy.context.scene.camera = camera
    log(f"✅ Camera: Orthographic, scale={final_size}m, height={camera_height}m")

    # =============================================================================
    # 12. 조명
    # =============================================================================

    log("[12] Adding lighting...")
    bpy.ops.object.light_add(
        type="SUN", location=(final_size / 2, final_size / 2, final_size * 2)
    )
    sun = bpy.context.active_object
    sun.data.energy = 3.0
    sun.rotation_euler = (math.radians(45), 0, math.radians(45))
    log(f"✅ Sun light added (energy={sun.data.energy})")

    # =============================================================================
    # 13. 렌더 설정
    # =============================================================================

    log("[13] Configuring render...")
    scene = bpy.context.scene
    scene.render.resolution_x = 1024
    scene.render.resolution_y = 1024
    scene.render.filepath = PREVIEW_PATH

    log(f"✅ Resolution: {scene.render.resolution_x}x{scene.render.resolution_y}")
    log(f"✅ Output path: {PREVIEW_PATH}")

    # =============================================================================
    # 14. 렌더링
    # =============================================================================

    log("[14] Rendering preview...")
    log(f"Camera: {scene.camera.name if scene.camera else 'None'}")
    log(f"Camera type: {scene.camera.data.type if scene.camera else 'None'}")
    log(f"Active objects: {len(bpy.context.scene.objects)}")

    # 씬 검증
    log("Scene validation:")
    for obj in scene.objects:
        log(
            f"  - {obj.name}: type={obj.type}, vertices={len(obj.data.vertices) if hasattr(obj.data, 'vertices') else 'N/A'}"
        )

    # 지형 객체 확인
    terrain_in_scene = scene.objects.get("BiomeTerrain")
    if terrain_in_scene:
        log(
            f"✅ Terrain found in scene: {len(terrain_in_scene.data.vertices):,} vertices"
        )
        log(f"   Dimensions: {terrain_in_scene.dimensions}")
        log(f"   Location: {terrain_in_scene.location}")
    else:
        log(f"❌ ERROR: BiomeTerrain not found in scene!")

    # View layer 업데이트
    bpy.context.view_layer.update()
    log("View layer updated")

    # EEVEE_NEXT 엔진으로 렌더링 (빠르고 GPU 사용)
    import time

    log("Using EEVEE_NEXT engine for fast rendering...")

    scene.render.engine = "BLENDER_EEVEE_NEXT"

    # 파일 경로 명시적으로 설정
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = PREVIEW_PATH

    # EEVEE 설정
    scene.eevee.use_gtao = True  # Ambient Occlusion
    scene.eevee.gtao_distance = 10

    log(f"Render settings:")
    log(f"  Engine: {scene.render.engine}")
    log(f"  Output: {scene.render.filepath}")

    # 렌더링 실행
    log("Starting EEVEE_NEXT render...")
    try:
        bpy.ops.render.render(write_still=True)
        log("Render operation completed")
    except Exception as e:
        log(f"❌ Render failed: {e}")
        log(traceback.format_exc())

    # 대기
    time.sleep(1.0)
    log("Waited 1 second for render to complete")

    # 렌더링 후 filepath 초기화 (blend 저장 시 덮어쓰기 방지!)
    scene.render.filepath = "//untitled"
    log("✅ Cleared render filepath to prevent overwrite")

    # 렌더링 후 파일 존재 확인
    if os.path.exists(PREVIEW_PATH):
        file_size = os.path.getsize(PREVIEW_PATH)
        log(f"✅ Preview file exists: {PREVIEW_PATH} ({file_size:,} bytes)")
        if file_size == 0:
            log(f"❌ ERROR: Preview file is 0 bytes!")
    else:
        log(f"❌ Preview file not created: {PREVIEW_PATH}")

    # =============================================================================
    # 15. 저장
    # =============================================================================

    log("[15] Saving blend file...")

    # 렌더링 완료 대기
    import time

    time.sleep(1.0)
    log("Waited for file system to flush")

    # 프리뷰 파일 최종 확인
    if os.path.exists(PREVIEW_PATH):
        final_size_bytes = os.path.getsize(PREVIEW_PATH)
        log(f"Preview file size before blend save: {final_size_bytes:,} bytes")
        if final_size_bytes == 0:
            log("❌ WARNING: Preview file is still 0 bytes!")

    bpy.ops.wm.save_as_mainfile(filepath=OUTPUT_BLEND)
    if os.path.exists(OUTPUT_BLEND):
        log(f"✅ Blend file saved: {OUTPUT_BLEND}")
    else:
        log(f"❌ Blend file not created: {OUTPUT_BLEND}")

    # 최종 대기 (파일 시스템 flush 보장)
    time.sleep(1.0)

    log("\n[Biome Terrain] SUCCESS!")
    log(f"[Biome Terrain] Blend: {OUTPUT_BLEND}")
    log(f"[Biome Terrain] Preview: {PREVIEW_PATH}")
    log(f"[Biome Terrain] Size: {final_size}m × {final_size}m × {max_height}m")

    # 로그 파일도 명시적으로 flush
    if LOG_FILE:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write("\n=== Script completed ===\n")
            f.flush()
            os.fsync(f.fileno())

except Exception as e:
    log(f"\n❌❌❌ FATAL ERROR ❌❌❌")
    log(f"Error: {e}")
    log(f"\nTraceback:")
    log(traceback.format_exc())
    sys.exit(1)
