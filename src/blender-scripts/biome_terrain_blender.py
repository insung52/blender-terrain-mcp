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
grid_subdivisions = params.get("grid_subdivisions", 200)  # 200×200 base
terrain_scale = params.get("terrain_scale", 10)  # 10배 = 1km
height_multiplier = params.get("height_multiplier", 30)
z_scale = params.get("z_scale", 1.5)  # 🔧 3 → 1.5 (50% 감소)

noise_scale = params.get("noise_scale", 0.05)
noise_detail = params.get("noise_detail", 5.0)

erosion_strength = params.get("erosion_strength", 20.0)
continentalness_strength = params.get(
    "continentalness_strength", 5.0
)  # 🔧 10.0 → 5.0 (바이옴 간 높이 차이 감소)
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
log("    - Octave 1 (60%): scale=0.01 (100m smooth mountains)")
log("    - Octave 2 (25%): scale=0.05 (20m medium details)")
log("    - Octave 3 (12%): scale=0.2 (5m small details)")
log("    - Octave 4 (3%): scale=1.0 (1m micro details, spike prevention)")
log("  Phase 3: Weirdness Special Terrain")
log("    - Voronoi-based ridges & cliffs")
log("    - Ridge height: 200m * erosion * weirdness")
log("    - Breaks circular biome patterns")
log("  Phase 4: Subdivision Surface")
log("    - Level 3 applied (64x vertices → ≈2.5M)")
log("    - Applied immediately for road generation")
log("    - Smooth, highly detailed terrain")
log("  Phase 5: Ridge & Valley Features")
log("    - Ridge: Voronoi-based mountain ridges (200m * erosion * weirdness)")
log("    - Valley: Humidity-based erosion (100m * humidity * continentalness_mask)")
log("    - Natural river valleys and mountain peaks")
log("  Phase 6: Temperature-based Snowline")
log("    - Temperature: -1~1 → Snowline: 500m~4000m")
log("    - Cold regions: snow from 500m altitude")
log("    - Hot regions: snow only above 4000m")
log("    - Smooth transition zone ±50m")
log("")
log("✅ UV Distortion: ±60m total (large ±30m/100m, medium ±20m/40m, small ±10m/10m)")
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
        "rock_color_r",  # 🪨 바위 색상 (경사진 곳에 노출)
        "rock_color_g",
        "rock_color_b",
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

    # Combine XY for UV (원본)
    combine_xy = nodes.new("ShaderNodeCombineXYZ")
    combine_xy.location = (0, 100)
    links.new(divide_x_node.outputs["Value"], combine_xy.inputs["X"])
    links.new(divide_y_node.outputs["Value"], combine_xy.inputs["Y"])

    # =============================================================================
    # 6. UV Distortion (3단계 - 계단 현상 제거 + 자연스러운 디테일)
    # =============================================================================

    # 바이옴 맵: 경계를 울퉁불퉁하게 (Voronoi noise)
    # UV 왜곡: 지형 샘플링을 자연스럽게 (계단 현상 제거)

    # Large-scale distortion noise (±3% = ±30m, 100m 주기)
    noise_large = nodes.new("ShaderNodeTexNoise")
    noise_large.location = (200, 500)
    noise_large.inputs["Scale"].default_value = 0.01  # 100m 주기
    noise_large.inputs["Detail"].default_value = 4.0

    # Medium-scale distortion noise (±2% = ±20m, 40m 주기)
    noise_medium = nodes.new("ShaderNodeTexNoise")
    noise_medium.location = (200, 300)
    noise_medium.inputs["Scale"].default_value = 0.025  # 40m 주기
    noise_medium.inputs["Detail"].default_value = 3.0

    # Small-scale distortion noise (±1% = ±10m, 10m 주기)
    noise_small = nodes.new("ShaderNodeTexNoise")
    noise_small.location = (200, 100)
    noise_small.inputs["Scale"].default_value = 0.1  # 10m 주기
    noise_small.inputs["Detail"].default_value = 2.0

    # Noise를 X, Y 오프셋으로 분리
    separate_large = nodes.new("ShaderNodeSeparateXYZ")
    separate_large.location = (400, 500)
    links.new(noise_large.outputs["Color"], separate_large.inputs["Vector"])

    separate_medium = nodes.new("ShaderNodeSeparateXYZ")
    separate_medium.location = (400, 300)
    links.new(noise_medium.outputs["Color"], separate_medium.inputs["Vector"])

    separate_small = nodes.new("ShaderNodeSeparateXYZ")
    separate_small.location = (400, 100)
    links.new(noise_small.outputs["Color"], separate_small.inputs["Vector"])

    # Large X offset (±3%)
    math_large_x = nodes.new("ShaderNodeMath")
    math_large_x.operation = "MULTIPLY"
    math_large_x.location = (600, 550)
    links.new(separate_large.outputs["X"], math_large_x.inputs[0])
    math_large_x.inputs[1].default_value = 0.0001  # ±3% = ±30m 0.2

    # Large Y offset (±3%)
    math_large_y = nodes.new("ShaderNodeMath")
    math_large_y.operation = "MULTIPLY"
    math_large_y.location = (600, 450)
    links.new(separate_large.outputs["Y"], math_large_y.inputs[0])
    math_large_y.inputs[1].default_value = 0.0001

    # Medium X offset (±2%)
    math_medium_x = nodes.new("ShaderNodeMath")
    math_medium_x.operation = "MULTIPLY"
    math_medium_x.location = (600, 350)
    links.new(separate_medium.outputs["X"], math_medium_x.inputs[0])
    math_medium_x.inputs[1].default_value = 0.0001  # ±2% = ±20m 0.06

    # Medium Y offset (±2%)
    math_medium_y = nodes.new("ShaderNodeMath")
    math_medium_y.operation = "MULTIPLY"
    math_medium_y.location = (600, 250)
    links.new(separate_medium.outputs["Y"], math_medium_y.inputs[0])
    math_medium_y.inputs[1].default_value = 0.0001

    # Small X offset (±1%)
    math_small_x = nodes.new("ShaderNodeMath")
    math_small_x.operation = "MULTIPLY"
    math_small_x.location = (600, 150)
    links.new(separate_small.outputs["X"], math_small_x.inputs[0])
    math_small_x.inputs[1].default_value = 0.0003  # ±1% = ±10m  0.03

    # Small Y offset (±1%)
    math_small_y = nodes.new("ShaderNodeMath")
    math_small_y.operation = "MULTIPLY"
    math_small_y.location = (600, 50)
    links.new(separate_small.outputs["Y"], math_small_y.inputs[0])
    math_small_y.inputs[1].default_value = 0.0003

    # 합산: Large + Medium + Small
    add_x_1 = nodes.new("ShaderNodeMath")
    add_x_1.operation = "ADD"
    add_x_1.location = (800, 500)
    links.new(math_large_x.outputs["Value"], add_x_1.inputs[0])
    links.new(math_medium_x.outputs["Value"], add_x_1.inputs[1])

    add_x = nodes.new("ShaderNodeMath")
    add_x.operation = "ADD"
    add_x.location = (1000, 400)
    links.new(add_x_1.outputs["Value"], add_x.inputs[0])
    links.new(math_small_x.outputs["Value"], add_x.inputs[1])

    add_y_1 = nodes.new("ShaderNodeMath")
    add_y_1.operation = "ADD"
    add_y_1.location = (800, 250)
    links.new(math_large_y.outputs["Value"], add_y_1.inputs[0])
    links.new(math_medium_y.outputs["Value"], add_y_1.inputs[1])

    add_y = nodes.new("ShaderNodeMath")
    add_y.operation = "ADD"
    add_y.location = (1000, 200)
    links.new(add_y_1.outputs["Value"], add_y.inputs[0])
    links.new(math_small_y.outputs["Value"], add_y.inputs[1])

    # UV에 오프셋 적용
    distort_x = nodes.new("ShaderNodeMath")
    distort_x.operation = "ADD"
    distort_x.location = (1200, 350)
    links.new(divide_x_node.outputs["Value"], distort_x.inputs[0])
    links.new(add_x.outputs["Value"], distort_x.inputs[1])

    distort_y = nodes.new("ShaderNodeMath")
    distort_y.operation = "ADD"
    distort_y.location = (1200, 150)
    links.new(divide_y_node.outputs["Value"], distort_y.inputs[0])
    links.new(add_y.outputs["Value"], distort_y.inputs[1])

    # 왜곡된 UV 조합
    combine_xy_distorted = nodes.new("ShaderNodeCombineXYZ")
    combine_xy_distorted.location = (1400, 250)
    links.new(distort_x.outputs["Value"], combine_xy_distorted.inputs["X"])
    links.new(distort_y.outputs["Value"], combine_xy_distorted.inputs["Y"])

    # =============================================================================
    # 7. Image Texture 샘플링 및 Attribute 저장
    # =============================================================================

    # 각 파라미터에 대해 Image Texture + Map Range + Store Named Attribute
    current_y = 500

    # 지형 높이에 사용할 파라미터 로드 (Phase 5: humidity 추가)
    height_params = [
        "temperature",
        "erosion",
        "continentalness",
        "weirdness",
        "humidity",
    ]

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
        # 🔥 왜곡된 UV 사용 (계단 현상 제거)
        links.new(combine_xy_distorted.outputs["Vector"], img_tex_node.inputs["Vector"])

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

    # Octave 5: Fine details (세밀한 바위 표면)
    noise_octave_5 = nodes.new("ShaderNodeTexNoise")
    noise_octave_5.location = (1000, -800)
    noise_octave_5.inputs["Scale"].default_value = 5.0  # 0.2m 단위
    noise_octave_5.inputs["Detail"].default_value = 7.0
    noise_octave_5.inputs["Roughness"].default_value = 0.85
    links.new(position_node.outputs["Position"], noise_octave_5.inputs["Vector"])

    # Octave 6: Ultra-fine details (미세 표면 텍스처)
    noise_octave_6 = nodes.new("ShaderNodeTexNoise")
    noise_octave_6.location = (1000, -950)
    noise_octave_6.inputs["Scale"].default_value = 50.0  # 0.02m 단위
    noise_octave_6.inputs["Detail"].default_value = 8.0
    noise_octave_6.inputs["Roughness"].default_value = 0.9
    links.new(position_node.outputs["Position"], noise_octave_6.inputs["Vector"])

    # Octave 1 * 3.6 (부드러운 큰 산맥 강화)
    multiply_octave_1 = nodes.new("ShaderNodeMath")
    multiply_octave_1.operation = "MULTIPLY"
    multiply_octave_1.inputs[1].default_value = 3.6
    multiply_octave_1.location = (1150, -200)
    links.new(noise_octave_1.outputs["Fac"], multiply_octave_1.inputs[0])

    # Octave 2 * 0.25 (중간 디테일)
    multiply_octave_2 = nodes.new("ShaderNodeMath")
    multiply_octave_2.operation = "MULTIPLY"
    multiply_octave_2.inputs[1].default_value = 0.5
    multiply_octave_2.location = (1150, -350)
    links.new(noise_octave_2.outputs["Fac"], multiply_octave_2.inputs[0])

    # Octave 3 * 0.12 (작은 디테일 약화)
    multiply_octave_3 = nodes.new("ShaderNodeMath")
    multiply_octave_3.operation = "MULTIPLY"
    multiply_octave_3.inputs[1].default_value = 0.05
    multiply_octave_3.location = (1150, -500)
    links.new(noise_octave_3.outputs["Fac"], multiply_octave_3.inputs[0])

    # Octave 4 * 0.1 (미세 디테일)
    multiply_octave_4 = nodes.new("ShaderNodeMath")
    multiply_octave_4.operation = "MULTIPLY"
    multiply_octave_4.inputs[1].default_value = 0.05
    multiply_octave_4.location = (1150, -650)
    links.new(noise_octave_4.outputs["Fac"], multiply_octave_4.inputs[0])

    # Octave 5 * 0.03 (세밀한 디테일)
    multiply_octave_5 = nodes.new("ShaderNodeMath")
    multiply_octave_5.operation = "MULTIPLY"
    multiply_octave_5.inputs[1].default_value = 0.05
    multiply_octave_5.location = (1150, -800)
    links.new(noise_octave_5.outputs["Fac"], multiply_octave_5.inputs[0])

    # Octave 6 * 0.01 (초미세 디테일)
    multiply_octave_6 = nodes.new("ShaderNodeMath")
    multiply_octave_6.operation = "MULTIPLY"
    multiply_octave_6.inputs[1].default_value = 0.5
    multiply_octave_6.location = (1150, -950)
    links.new(noise_octave_6.outputs["Fac"], multiply_octave_6.inputs[0])

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

    # Add Octave 5 + 6
    add_octave_56 = nodes.new("ShaderNodeMath")
    add_octave_56.operation = "ADD"
    add_octave_56.location = (1300, -875)
    links.new(multiply_octave_5.outputs["Value"], add_octave_56.inputs[0])
    links.new(multiply_octave_6.outputs["Value"], add_octave_56.inputs[1])

    # Combined Octave 1+2+3+4
    combined_noise_1234 = nodes.new("ShaderNodeMath")
    combined_noise_1234.operation = "ADD"
    combined_noise_1234.location = (1450, -400)
    links.new(add_octave_12.outputs["Value"], combined_noise_1234.inputs[0])
    links.new(add_octave_34.outputs["Value"], combined_noise_1234.inputs[1])

    # Combined Noise = All Octaves (1+2+3+4+5+6)
    combined_noise = nodes.new("ShaderNodeMath")
    combined_noise.operation = "ADD"
    combined_noise.location = (1600, -550)
    links.new(combined_noise_1234.outputs["Value"], combined_noise.inputs[0])
    links.new(add_octave_56.outputs["Value"], combined_noise.inputs[1])

    # Noise Texture (weirdness용)
    noise_weird = nodes.new("ShaderNodeTexNoise")
    noise_weird.location = (1000, -1100)
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
    links.new(
        attr_continentalness.outputs["Attribute"], map_continentalness.inputs["Value"]
    )

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

    # =========================================================================
    # Phase 3: Weirdness 특수 지형 시스템
    # =========================================================================

    # Voronoi Texture for cliffs/canyons
    voronoi_node = nodes.new("ShaderNodeTexVoronoi")
    voronoi_node.location = (1200, -300)
    voronoi_node.voronoi_dimensions = "3D"
    voronoi_node.feature = "F1"  # F1 = Distance to closest feature point
    voronoi_node.inputs["Scale"].default_value = 0.1  # 절벽 스케일
    links.new(position_node.outputs["Position"], voronoi_node.inputs["Vector"])

    # Ridge mask: 1.0 - |distance - 0.5| * 2.0
    # Voronoi distance 0.5 = 셀 경계 = 능선/절벽
    # F1 feature uses "Distance" output socket
    subtract_half = nodes.new("ShaderNodeMath")
    subtract_half.operation = "SUBTRACT"
    subtract_half.inputs[1].default_value = 0.5
    subtract_half.location = (1400, -300)
    links.new(voronoi_node.outputs["Distance"], subtract_half.inputs[0])

    abs_node = nodes.new("ShaderNodeMath")
    abs_node.operation = "ABSOLUTE"
    abs_node.location = (1550, -300)
    links.new(subtract_half.outputs["Value"], abs_node.inputs[0])

    multiply_two = nodes.new("ShaderNodeMath")
    multiply_two.operation = "MULTIPLY"
    multiply_two.inputs[1].default_value = 2.0
    multiply_two.location = (1700, -300)
    links.new(abs_node.outputs["Value"], multiply_two.inputs[0])

    ridge_mask = nodes.new("ShaderNodeMath")
    ridge_mask.operation = "SUBTRACT"
    ridge_mask.inputs[0].default_value = 1.0
    ridge_mask.location = (1850, -300)
    links.new(multiply_two.outputs["Value"], ridge_mask.inputs[1])

    # Clamp 0~1
    clamp_ridge = nodes.new("ShaderNodeClamp")
    clamp_ridge.location = (2000, -300)
    clamp_ridge.inputs["Min"].default_value = 0.0
    clamp_ridge.inputs["Max"].default_value = 1.0
    links.new(ridge_mask.outputs["Value"], clamp_ridge.inputs["Value"])

    # Sharpen: pow(ridge_mask, 2.0) for pointy ridges
    power_node = nodes.new("ShaderNodeMath")
    power_node.operation = "POWER"
    power_node.inputs[1].default_value = 2.0
    power_node.location = (2150, -300)
    links.new(clamp_ridge.outputs["Result"], power_node.inputs[0])

    # Ridge height = ridge_mask * 200m * erosion
    multiply_ridge_height = nodes.new("ShaderNodeMath")
    multiply_ridge_height.operation = "MULTIPLY"
    multiply_ridge_height.inputs[1].default_value = 200.0  # 200m 능선
    multiply_ridge_height.location = (2300, -300)
    links.new(power_node.outputs["Value"], multiply_ridge_height.inputs[0])

    multiply_ridge_erosion = nodes.new("ShaderNodeMath")
    multiply_ridge_erosion.operation = "MULTIPLY"
    multiply_ridge_erosion.location = (2450, -300)
    links.new(multiply_ridge_height.outputs["Value"], multiply_ridge_erosion.inputs[0])
    links.new(attr_erosion.outputs["Attribute"], multiply_ridge_erosion.inputs[1])

    # Weirdness 강도 적용: ridge * weirdness
    # weirdness 높을수록 능선/절벽 강하게
    multiply_ridge_weirdness = nodes.new("ShaderNodeMath")
    multiply_ridge_weirdness.operation = "MULTIPLY"
    multiply_ridge_weirdness.location = (2600, -300)
    links.new(
        multiply_ridge_erosion.outputs["Value"], multiply_ridge_weirdness.inputs[0]
    )
    links.new(attr_weirdness.outputs["Attribute"], multiply_ridge_weirdness.inputs[1])

    # 기존 Weirdness 노이즈 효과 (약하게 유지)
    multiply_weird_noise = nodes.new("ShaderNodeMath")
    multiply_weird_noise.operation = "MULTIPLY"
    multiply_weird_noise.location = (1400, -500)
    links.new(attr_weirdness.outputs["Attribute"], multiply_weird_noise.inputs[0])
    links.new(noise_weird.outputs["Fac"], multiply_weird_noise.inputs[1])

    multiply_weird_strength = nodes.new("ShaderNodeMath")
    multiply_weird_strength.operation = "MULTIPLY"
    multiply_weird_strength.inputs[1].default_value = 20.0  # 약간의 랜덤 변화
    multiply_weird_strength.location = (1600, -500)
    links.new(multiply_weird_noise.outputs["Value"], multiply_weird_strength.inputs[0])

    # 최종 Weirdness = Ridge 효과 + 노이즈 효과
    add_weirdness_effects = nodes.new("ShaderNodeMath")
    add_weirdness_effects.operation = "ADD"
    add_weirdness_effects.location = (2750, -400)
    links.new(
        multiply_ridge_weirdness.outputs["Value"], add_weirdness_effects.inputs[0]
    )
    links.new(multiply_weird_strength.outputs["Value"], add_weirdness_effects.inputs[1])

    # =========================================================================
    # Phase 5: Valley (계곡) 침식
    # =========================================================================

    # Humidity attribute 읽기
    attr_humidity = nodes.new("GeometryNodeInputNamedAttribute")
    attr_humidity.location = (2100, -850)
    attr_humidity.data_type = "FLOAT"
    attr_humidity.inputs["Name"].default_value = "humidity"

    # Valley mask: continentalness 낮을수록 계곡
    # (1.0 - continentalness) / 2.0 → 0~1 범위
    subtract_from_one = nodes.new("ShaderNodeMath")
    subtract_from_one.operation = "SUBTRACT"
    subtract_from_one.inputs[0].default_value = 1.0
    subtract_from_one.location = (2300, -700)
    links.new(attr_continentalness.outputs["Attribute"], subtract_from_one.inputs[1])

    divide_by_two = nodes.new("ShaderNodeMath")
    divide_by_two.operation = "DIVIDE"
    divide_by_two.inputs[1].default_value = 2.0
    divide_by_two.location = (2450, -700)
    links.new(subtract_from_one.outputs["Value"], divide_by_two.inputs[0])

    # Valley strength = humidity * 100.0
    # 습한 지역일수록 물 흐름 → 침식 강화
    multiply_humidity_strength = nodes.new("ShaderNodeMath")
    multiply_humidity_strength.operation = "MULTIPLY"
    multiply_humidity_strength.inputs[1].default_value = 100.0
    multiply_humidity_strength.location = (2300, -850)
    links.new(attr_humidity.outputs["Attribute"], multiply_humidity_strength.inputs[0])

    # Valley depth = valley_mask * humidity_strength
    multiply_valley_depth = nodes.new("ShaderNodeMath")
    multiply_valley_depth.operation = "MULTIPLY"
    multiply_valley_depth.location = (2600, -750)
    links.new(divide_by_two.outputs["Value"], multiply_valley_depth.inputs[0])
    links.new(
        multiply_humidity_strength.outputs["Value"], multiply_valley_depth.inputs[1]
    )

    # STEP 5: 최종 높이 합성
    # final_height = base_height + height_variation + ridge_effects - valley_depth

    # base_height + height_variation
    add_base_variation = nodes.new("ShaderNodeMath")
    add_base_variation.operation = "ADD"
    add_base_variation.location = (1800, 200)
    links.new(map_continentalness.outputs["Result"], add_base_variation.inputs[0])
    links.new(multiply_noise_erosion.outputs["Value"], add_base_variation.inputs[1])

    # + weirdness effects (ridge + noise)
    add_ridge = nodes.new("ShaderNodeMath")
    add_ridge.operation = "ADD"
    add_ridge.location = (2900, 100)
    links.new(add_base_variation.outputs["Value"], add_ridge.inputs[0])
    links.new(add_weirdness_effects.outputs["Value"], add_ridge.inputs[1])

    # - valley depth
    subtract_valley = nodes.new("ShaderNodeMath")
    subtract_valley.operation = "SUBTRACT"
    subtract_valley.location = (3050, 0)
    links.new(add_ridge.outputs["Value"], subtract_valley.inputs[0])
    links.new(multiply_valley_depth.outputs["Value"], subtract_valley.inputs[1])

    # ⚠️ Phase 1.3: Temperature는 높이 계산에서 제거!
    # Temperature는 Material에서만 사용 (눈선 계산)
    # 최종 높이 = subtract_valley 결과
    final_height = subtract_valley

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
    # 10. Phase 6: Material with Temperature-based Snowline
    # =============================================================================

    log("[10] Creating Phase 6 Material...")
    material = bpy.data.materials.new(name="BiomeTerrainMaterial")
    material.use_nodes = True
    mat_nodes = material.node_tree.nodes
    mat_links = material.node_tree.links

    # 기존 노드 삭제
    mat_nodes.clear()

    # Output
    mat_output = mat_nodes.new("ShaderNodeOutputMaterial")
    mat_output.location = (800, 0)

    # 🔧 Material 구조: Ground → Snow (높이) → Rock (경사도)
    # 1. Ground BSDF
    # 2. Mix Snow (Ground vs Snow) - 높이 기반
    # 3. Mix Rock (Ground+Snow vs Rock) - 경사도 기반 → 최종 출력

    # Mix Shader (Ground+Snow vs Rock) - 최종 출력, 경사도 기반
    mix_rock = mat_nodes.new("ShaderNodeMixShader")
    mix_rock.location = (1000, 0)
    mat_links.new(mix_rock.outputs["Shader"], mat_output.inputs["Surface"])

    # Mix Shader (Ground vs Snow) - 높이 기반
    mix_snow = mat_nodes.new("ShaderNodeMixShader")
    mix_snow.location = (800, 100)
    mat_links.new(
        mix_snow.outputs["Shader"], mix_rock.inputs[1]
    )  # Shader 1 (Ground+Snow)

    # Ground Material (Principled BSDF)
    ground_bsdf = mat_nodes.new("ShaderNodeBsdfPrincipled")
    ground_bsdf.location = (200, 200)
    mat_links.new(ground_bsdf.outputs["BSDF"], mix_snow.inputs[1])  # Shader 1 (Ground)

    # Snow Material (Principled BSDF)
    snow_bsdf = mat_nodes.new("ShaderNodeBsdfPrincipled")
    snow_bsdf.location = (600, 0)
    snow_bsdf.inputs["Base Color"].default_value = (
        0.95,
        0.95,
        1.0,
        1.0,
    )  # 눈 (약간 파란빛)
    snow_bsdf.inputs["Roughness"].default_value = 0.8
    mat_links.new(snow_bsdf.outputs["BSDF"], mix_snow.inputs[2])  # Shader 2 (Snow)

    # Rock Material (Principled BSDF)
    rock_bsdf = mat_nodes.new("ShaderNodeBsdfPrincipled")
    rock_bsdf.location = (800, -200)
    rock_bsdf.inputs["Roughness"].default_value = 0.9  # 거친 바위 표면
    mat_links.new(rock_bsdf.outputs["BSDF"], mix_rock.inputs[2])  # Shader 2 (Rock)

    # 🔥 Ground Color from biome maps (RGB 채널 분리되어 있음)
    # UV 좌표 가져오기 (텍스처 샘플링용)
    uv_map_node = mat_nodes.new("ShaderNodeUVMap")
    uv_map_node.location = (-600, 400)
    uv_map_node.uv_map = "UVMap"  # 기본 UV

    # Ground Color R 채널
    if "ground_color_r" in loaded_images:
        img_tex_r = mat_nodes.new("ShaderNodeTexImage")
        img_tex_r.location = (-200, 500)
        img_tex_r.image = loaded_images["ground_color_r"]
        img_tex_r.extension = "EXTEND"
        mat_links.new(uv_map_node.outputs["UV"], img_tex_r.inputs["Vector"])
    else:
        img_tex_r = None
        log("⚠️ ground_color_r image not found")

    # Ground Color G 채널
    if "ground_color_g" in loaded_images:
        img_tex_g = mat_nodes.new("ShaderNodeTexImage")
        img_tex_g.location = (-200, 300)
        img_tex_g.image = loaded_images["ground_color_g"]
        img_tex_g.extension = "EXTEND"
        mat_links.new(uv_map_node.outputs["UV"], img_tex_g.inputs["Vector"])
    else:
        img_tex_g = None
        log("⚠️ ground_color_g image not found")

    # Ground Color B 채널
    if "ground_color_b" in loaded_images:
        img_tex_b = mat_nodes.new("ShaderNodeTexImage")
        img_tex_b.location = (-200, 100)
        img_tex_b.image = loaded_images["ground_color_b"]
        img_tex_b.extension = "EXTEND"
        mat_links.new(uv_map_node.outputs["UV"], img_tex_b.inputs["Vector"])
    else:
        img_tex_b = None
        log("⚠️ ground_color_b image not found")

    # RGB 채널 합성 (Ground)
    if img_tex_r and img_tex_g and img_tex_b:
        combine_ground_rgb = mat_nodes.new("ShaderNodeCombineRGB")
        combine_ground_rgb.location = (100, 300)
        mat_links.new(img_tex_r.outputs["Color"], combine_ground_rgb.inputs["R"])
        mat_links.new(img_tex_g.outputs["Color"], combine_ground_rgb.inputs["G"])
        mat_links.new(img_tex_b.outputs["Color"], combine_ground_rgb.inputs["B"])
        mat_links.new(
            combine_ground_rgb.outputs["Image"], ground_bsdf.inputs["Base Color"]
        )
        log("✅ Ground color from biome maps (RGB channels)")
    else:
        # Fallback: 기본 갈색
        ground_bsdf.inputs["Base Color"].default_value = (0.3, 0.25, 0.2, 1.0)
        log("⚠️ Using default brown color (biome maps missing)")

    # 🪨 Rock Color from biome maps (RGB 채널 분리되어 있음)
    # Rock Color R 채널
    if "rock_color_r" in loaded_images:
        rock_tex_r = mat_nodes.new("ShaderNodeTexImage")
        rock_tex_r.location = (-200, -100)
        rock_tex_r.image = loaded_images["rock_color_r"]
        rock_tex_r.extension = "EXTEND"
        mat_links.new(uv_map_node.outputs["UV"], rock_tex_r.inputs["Vector"])
    else:
        rock_tex_r = None
        log("⚠️ rock_color_r image not found")

    # Rock Color G 채널
    if "rock_color_g" in loaded_images:
        rock_tex_g = mat_nodes.new("ShaderNodeTexImage")
        rock_tex_g.location = (-200, -300)
        rock_tex_g.image = loaded_images["rock_color_g"]
        rock_tex_g.extension = "EXTEND"
        mat_links.new(uv_map_node.outputs["UV"], rock_tex_g.inputs["Vector"])
    else:
        rock_tex_g = None
        log("⚠️ rock_color_g image not found")

    # Rock Color B 채널
    if "rock_color_b" in loaded_images:
        rock_tex_b = mat_nodes.new("ShaderNodeTexImage")
        rock_tex_b.location = (-200, -500)
        rock_tex_b.image = loaded_images["rock_color_b"]
        rock_tex_b.extension = "EXTEND"
        mat_links.new(uv_map_node.outputs["UV"], rock_tex_b.inputs["Vector"])
    else:
        rock_tex_b = None
        log("⚠️ rock_color_b image not found")

    # RGB 채널 합성 (Rock)
    if rock_tex_r and rock_tex_g and rock_tex_b:
        combine_rock_rgb = mat_nodes.new("ShaderNodeCombineRGB")
        combine_rock_rgb.location = (100, -200)
        mat_links.new(rock_tex_r.outputs["Color"], combine_rock_rgb.inputs["R"])
        mat_links.new(rock_tex_g.outputs["Color"], combine_rock_rgb.inputs["G"])
        mat_links.new(rock_tex_b.outputs["Color"], combine_rock_rgb.inputs["B"])
        mat_links.new(combine_rock_rgb.outputs["Image"], rock_bsdf.inputs["Base Color"])
        log("✅ Rock color from biome maps (RGB channels)")
    else:
        # Fallback: 기본 회색-갈색 바위
        rock_bsdf.inputs["Base Color"].default_value = (0.45, 0.42, 0.38, 1.0)
        log("⚠️ Using default gray-brown rock color (biome maps missing)")

    # =========================================================================
    # Slope Calculation (경사도 계산 - 바위 노출용)
    # =========================================================================

    # Geometry Normal (법선 벡터)
    geometry_normal = mat_nodes.new("ShaderNodeNewGeometry")
    geometry_normal.location = (-800, -700)

    # Separate XYZ (Normal의 Z 성분 추출)
    separate_normal = mat_nodes.new("ShaderNodeSeparateXYZ")
    separate_normal.location = (-600, -700)
    mat_links.new(geometry_normal.outputs["Normal"], separate_normal.inputs["Vector"])

    # Slope = 1.0 - Normal.Z
    # Normal.Z = 1.0 → 평평 (수평)
    # Normal.Z = 0.0 → 수직 절벽
    slope_calc = mat_nodes.new("ShaderNodeMath")
    slope_calc.operation = "SUBTRACT"
    slope_calc.inputs[0].default_value = 1.0
    slope_calc.location = (-400, -700)
    mat_links.new(separate_normal.outputs["Z"], slope_calc.inputs[1])

    # Get rock_exposure attribute (바이옴별 바위 노출도)
    rock_exposure_attr = mat_nodes.new("ShaderNodeAttribute")
    rock_exposure_attr.location = (-600, -900)
    rock_exposure_attr.attribute_name = "rock_exposure"
    rock_exposure_attr.attribute_type = "GEOMETRY"

    # rock_exposure에 따라 임계값 조정
    # 🔧 임계값을 낮춰서 바위가 더 쉽게 노출되도록 수정
    # rock_exposure 높음 (0.7) → 매우 낮은 경사도에서도 바위 노출 (threshold 0.15)
    # rock_exposure 낮음 (0.1) → 중간 경사도에서 바위 노출 (threshold 0.45)
    # threshold = 0.5 - rock_exposure * 0.5
    multiply_exposure = mat_nodes.new("ShaderNodeMath")
    multiply_exposure.operation = "MULTIPLY"
    multiply_exposure.inputs[1].default_value = 0.07  # 0.7 → 0.5
    multiply_exposure.location = (-400, -900)
    mat_links.new(rock_exposure_attr.outputs["Fac"], multiply_exposure.inputs[0])

    subtract_threshold = mat_nodes.new("ShaderNodeMath")
    subtract_threshold.operation = "SUBTRACT"
    subtract_threshold.inputs[0].default_value = 0.07  # 0.8 → 0.5 (더 낮은 기본값)
    subtract_threshold.location = (-200, -900)
    mat_links.new(multiply_exposure.outputs["Value"], subtract_threshold.inputs[1])

    # Slope에서 threshold 뺀 값을 Map Range로 0~1로 정규화
    # slope < threshold → 0 (Ground)
    # slope > threshold+0.2 → 1 (Rock)
    add_threshold_high = mat_nodes.new("ShaderNodeMath")
    add_threshold_high.operation = "ADD"
    add_threshold_high.inputs[1].default_value = 0.2  # 블렌딩 범위
    add_threshold_high.location = (0, -900)
    mat_links.new(subtract_threshold.outputs["Value"], add_threshold_high.inputs[0])

    slope_map = mat_nodes.new("ShaderNodeMapRange")
    slope_map.location = (200, -800)
    slope_map.clamp = True
    mat_links.new(subtract_threshold.outputs["Value"], slope_map.inputs["From Min"])
    mat_links.new(add_threshold_high.outputs["Value"], slope_map.inputs["From Max"])
    slope_map.inputs["To Min"].default_value = 0.0
    slope_map.inputs["To Max"].default_value = 1.0
    mat_links.new(slope_calc.outputs["Value"], slope_map.inputs["Value"])

    # =========================================================================
    # Snowline Calculation (Temperature-based) - Rock보다 먼저 계산
    # =========================================================================

    # Get vertex position Z (height) - Reuse geometry_normal node
    separate_position = mat_nodes.new("ShaderNodeSeparateXYZ")
    separate_position.location = (-600, -1100)
    mat_links.new(
        geometry_normal.outputs["Position"], separate_position.inputs["Vector"]
    )

    # Get Temperature attribute (from vertex)
    # Temperature attribute는 Geometry Nodes에서 vertex attribute로 저장됨
    # Material에서는 Attribute 노드로 읽을 수 있음
    temp_attr = mat_nodes.new("ShaderNodeAttribute")
    temp_attr.location = (-600, -200)
    temp_attr.attribute_name = "temperature"
    temp_attr.attribute_type = "GEOMETRY"

    # Snowline height calculation: Map Range
    # Temperature: -1~1 → Snowline: 500m~4000m
    # 추운 곳: 낮은 곳부터 눈
    # 더운 곳: 높은 곳만 눈
    snowline_map = mat_nodes.new("ShaderNodeMapRange")
    snowline_map.location = (-200, -200)
    snowline_map.inputs["From Min"].default_value = -1.0
    snowline_map.inputs["From Max"].default_value = 1.0
    snowline_map.inputs["To Min"].default_value = 500.0  # 추운 곳: 500m부터 눈
    snowline_map.inputs["To Max"].default_value = 4000.0  # 더운 곳: 4000m부터만 눈
    mat_links.new(temp_attr.outputs["Fac"], snowline_map.inputs["Value"])

    # Compare: height >= snowline?
    # If height >= snowline → Snow (1.0)
    # If height < snowline → Ground (0.0)
    compare_height = mat_nodes.new("ShaderNodeMath")
    compare_height.operation = "GREATER_THAN"
    compare_height.location = (200, -1100)
    mat_links.new(separate_position.outputs["Z"], compare_height.inputs[0])
    mat_links.new(snowline_map.outputs["Result"], compare_height.inputs[1])

    # Smoothstep for gradual transition
    # 눈선 주변 ±50m에서 부드럽게 전환
    subtract_50 = mat_nodes.new("ShaderNodeMath")
    subtract_50.operation = "SUBTRACT"
    subtract_50.inputs[1].default_value = 50.0
    subtract_50.location = (0, -1200)
    mat_links.new(snowline_map.outputs["Result"], subtract_50.inputs[0])

    add_50 = mat_nodes.new("ShaderNodeMath")
    add_50.operation = "ADD"
    add_50.inputs[1].default_value = 50.0
    add_50.location = (0, -1350)
    mat_links.new(snowline_map.outputs["Result"], add_50.inputs[0])

    smooth_map = mat_nodes.new("ShaderNodeMapRange")
    smooth_map.location = (400, -1200)
    smooth_map.clamp = True
    mat_links.new(subtract_50.outputs["Value"], smooth_map.inputs["From Min"])
    mat_links.new(add_50.outputs["Value"], smooth_map.inputs["From Max"])
    smooth_map.inputs["To Min"].default_value = 0.0
    smooth_map.inputs["To Max"].default_value = 1.0
    # ⚠️ 주의: separate_position.Z는 사용하지 않음 (노이즈 적용된 높이 사용)

    # 🔧 눈선에 랜덤 노이즈 추가 (자연스러운 눈 경계)
    # Noise Texture (위치 기반)
    snow_noise = mat_nodes.new("ShaderNodeTexNoise")
    snow_noise.location = (200, -1400)
    snow_noise.inputs["Scale"].default_value = 5.0  # 작은 스케일로 디테일한 변화
    snow_noise.inputs["Detail"].default_value = 3.0
    snow_noise.inputs["Roughness"].default_value = 0.6
    mat_links.new(geometry_normal.outputs["Position"], snow_noise.inputs["Vector"])

    # Noise를 -30 ~ +30 범위로 변환 (눈선 변동폭)
    noise_map = mat_nodes.new("ShaderNodeMapRange")
    noise_map.location = (400, -1400)
    noise_map.inputs["From Min"].default_value = 0.0
    noise_map.inputs["From Max"].default_value = 1.0
    noise_map.inputs["To Min"].default_value = -30.0  # -30m
    noise_map.inputs["To Max"].default_value = 30.0  # +30m
    mat_links.new(snow_noise.outputs["Fac"], noise_map.inputs["Value"])

    # 높이 + 노이즈
    add_noise_to_height = mat_nodes.new("ShaderNodeMath")
    add_noise_to_height.operation = "ADD"
    add_noise_to_height.location = (200, -1100)
    mat_links.new(separate_position.outputs["Z"], add_noise_to_height.inputs[0])
    mat_links.new(noise_map.outputs["Result"], add_noise_to_height.inputs[1])

    # 노이즈 적용된 높이를 smooth_map에 연결
    mat_links.new(add_noise_to_height.outputs["Value"], smooth_map.inputs["Value"])

    # Connect to Mix Shader Fac (Ground vs Snow)
    mat_links.new(smooth_map.outputs["Result"], mix_snow.inputs["Fac"])
    log("✅ Snow with random noise configured (자연스러운 눈선)")

    # =========================================================================
    # Rock Application (Slope-based) - Snow 위에 적용
    # =========================================================================

    # Connect to Mix Shader Fac (Ground+Snow vs Rock)
    mat_links.new(slope_map.outputs["Result"], mix_rock.inputs["Fac"])
    log("✅ Slope-based rock blending configured (경사진 곳은 눈 위에 바위 노출)")

    # Material 할당
    if terrain_obj.data.materials:
        terrain_obj.data.materials[0] = material
    else:
        terrain_obj.data.materials.append(material)

    log("✅ Material created and assigned")

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
    # 10.7. Phase 4: Subdivision Surface (Apply Immediately)
    # =============================================================================

    log("[10.7] Phase 4: Applying Subdivision Surface...")
    bpy.context.view_layer.objects.active = terrain_obj
    terrain_obj.select_set(True)

    # Subdivision Surface Modifier 추가
    subsurf_modifier = terrain_obj.modifiers.new(name="Subdivision", type="SUBSURF")
    subsurf_modifier.levels = 3  # Level 3 적용 (64배 증가 → 2.5M vertices)
    subsurf_modifier.render_levels = 3  # 동일
    subsurf_modifier.subdivision_type = "CATMULL_CLARK"

    log(f"Before Subdivision - Vertex count: {len(terrain_obj.data.vertices):,}")
    log(
        f"Subdivision level: 3 (target: ≈{len(terrain_obj.data.vertices) * 64:,} vertices)"
    )

    # Modifier 즉시 적용 (실제 메시로 변환)
    try:
        bpy.ops.object.modifier_apply(modifier=subsurf_modifier.name)
        log(f"✅ Subdivision Surface applied")
        log(f"After Subdivision - Vertex count: {len(terrain_obj.data.vertices):,}")
    except Exception as e:
        log(f"❌ Failed to apply Subdivision: {e}")

    # =============================================================================
    # 10.8. Terrain Scale 적용 (Subdivision 이후)
    # =============================================================================

    log("[10.8] Applying terrain scale (after subdivision)...")
    bpy.context.view_layer.objects.active = terrain_obj
    terrain_obj.select_set(True)

    # 🔧 Z축 높이를 25% 감소 (next.md 3번 - 50%의 50%)
    z_scale_final = z_scale * 0.5 * 0.6
    log(f"🔧 Z-scale final adjustment: {z_scale} → {z_scale_final} (75% reduction)")

    terrain_obj.scale = (terrain_scale, terrain_scale, z_scale_final)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    final_size = base_size * terrain_scale
    max_height = height_multiplier * z_scale_final

    log(f"✅ Scale applied: XY={terrain_scale}x, Z={z_scale_final}x")
    log(f"   Final size: {final_size:,}m × {final_size:,}m × {max_height}m")

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

    log("Using EEVEE_NEXT with shadow disabled rendering...")

    scene.render.engine = "BLENDER_EEVEE_NEXT"

    # 파일 경로 명시적으로 설정
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = PREVIEW_PATH

    # ✅ 2️⃣ 개별 라이트의 그림자 끄기
    for obj in bpy.data.objects:
        if obj.type == "LIGHT":
            try:
                obj.data.use_shadow = False
                log(f"✅ Disabled shadows for light: {obj.name}")
            except AttributeError:
                log(f"⚠️ Cannot disable shadows for {obj.name}")

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
