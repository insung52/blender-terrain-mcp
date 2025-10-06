# 블렌더 terrain + road generation 프로그램? 스크립트? 개요
## 1. terrain 생성
- 사용자가 지형에 대한 설명이나 특성을 입력 (ex. 산악지형, 설산 지형)
- 또는 예시 이미지 또는 동영상 입력
- 프로그램이 해당 특성에 맞게 자동으로 지형을 생성함
- 크기 : 대략 100m * 100m
- 구현 방법 예시 : Terrain Generator GeoNodes 이용 (Terrain Generator GeoNodes.blend)
- https://chuckcg.gumroad.com/l/msvqs?_gl=1*fes73e*_ga*MTk2NTI0NzU1NC4xNzU5NzQ2MDM4*_ga_6LJN6D94N6*czE3NTk3NDYwMzckbzEkZzEkdDE3NTk3NDYxNjEkajYkbDAkaDA.

## 2. road 그리기
- 프로그램이 지형을 위에서 본 이미지를 보여줌 (또는 블렌더의 시점을 지형을 위에서 보는 시점으로 변경)
- 사용자가 그 위에 그림판처럼 자유롭게 곡선을 그음
- 프로그램이 자동으로 그 선을 따라 지형 위에 도로를 생성함
- 도로 폭 : 1차선 도로, 차선 당 1.6m
- 구현 방법 예시 : curve -> knife ? 
- https://www.youtube.com/watch?v=Ewt0eatttBw

---

교수님 요청사항 기록
outside

input 동영상 -> terrain?

선 그리기 -> 자동 fit 알고리즘

web -> terrain 을 workstation 에서 생성 -> 선 그어서 spline fitting -> road 생성

control point (spline)

road 생성용 input