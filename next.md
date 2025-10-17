preview 이미지 깨짐. output 폴더 보면 0바이트 파일임

지형 크기가 terrain_generator_v2.py (기존 방식) 에 비해 작음. dimensions 기준
- 기존 : 1000m, 1000m, 77.2m
- 현재 : 100m, 100m, 16,5m
버텍스 개수도 적음
- 기존 : 2563201개 버텍스
- 현재 : 10201개 버텍스


나무 등 여러 오브젝트
- Point Distribute, Instance on Points 노드 이용 나무 오브젝트 배치
- Attribute Sample Texture 이용 마스크 기반 배치 가능?
- 도로 안가리게
- 오브젝트 생성 방법

    0. 미리 사용할 오브젝트들 인터넷 다운로드 후 asset 으로 사용
    - 배치할 asset 사용자 선택
    - poly haven
    ~~1. blender mcp 를 이용해 미리 사용할 오브젝트 생성 후 asset 으로 사용~~
    ~~2. 모든 클라이언트의 지형 요청 시마다 claude api 를 한번 더 호출해 오브젝트를 생성하는 스크립트 (또는 이미 정의된 오브젝트 생성 스크립트의 파라미터) 를 만들고, 이를 바탕으로 오브젝트 생성~~

~~지형 텍스쳐, 도로 텍스쳐를 claude ai 로 생성하기~~ 
- 이미지 생성은 claude ai 로 불가함

도로와 지형 메시 서로 자연스럽게 연결

도로에 가드레일, 가로수 등 오브젝트?

도로와 지형 메시 subdivision 으로 근접 디테일 향상