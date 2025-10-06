import bpy
import sys

# Cube 생성
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))

# 파일 저장
output_path = sys.argv[-1]
bpy.ops.wm.save_as_mainfile(filepath=output_path)
print(f"SUCCESS: {output_path}")
