#!/usr/bin/env python3
"""cherubim_extended_demo.py — Cherubim v1.1.0 확장 모듈 통합 데모

행성 탐사 엔진 3단계 확장:
  【1】 EdenSearchEngine    — 파라미터 공간 탐색 (기존)
  【2】 EdenSpatialGrid     — 행성 표면 2D 공간 탐사 (위도×경도 히트맵) ★NEW
  【3】 EdenBasinStability  — Ring Attractor Basin 안정성 검증 ★NEW
  【4】 EdenParamScanner    — 2D~5D 다차원 파라미터 공간 탐사 ★NEW
  【5】 EdenBasinShape      — Basin 형태 분석 (5D 파라미터 공간) ★NEW

실행:
  cd /Users/jazzin/Desktop/00_BRAIN/Cherubim_Engine
  python examples/cherubim_extended_demo.py
"""

import sys
import os
import time

# 패키지 경로 설정
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cherubim

print("=" * 70)
print("  🌍 Cherubim — Eden Basin Finder  v" + cherubim.__version__)
print("  행성 탐사 엔진 (Planet Exploration Engine)")
print("=" * 70)
print(f"\n  모듈 로드 완료:")
print(f"    코어:   initial_conditions, firmament, flood, geography, search, biology")
print(f"    확장:   spatial_grid, basin_stability, param_space")
print()


# ════════════════════════════════════════════════════════════════════════════
# 【1】 기본 에덴 탐색 (기존 기능 확인)
# ════════════════════════════════════════════════════════════════════════════
print("\n" + "━" * 70)
print("  【1】 EdenSearchEngine — 파라미터 공간 에덴 탐색")
print("━" * 70)

from cherubim import EdenSearchEngine, make_antediluvian_space

engine = EdenSearchEngine(phase='antediluvian', verbose=True)
space  = make_antediluvian_space()
# steps 줄여서 빠른 데모
space.CO2_range        = (200.0, 300.0, 3)
space.H2O_atm_range    = (0.03,  0.08,  2)
space.H2O_canopy_range = (0.02,  0.06,  2)
space.O2_range         = (0.21,  0.24,  2)
space.albedo_range     = (0.15,  0.25,  2)
space.f_land_range     = (0.35,  0.45,  2)
space.UV_shield_range  = (0.80,  0.98,  2)

t0 = time.time()
result = engine.search(space, max_candidates=20, min_score=0.45)
print(f"\n  탐색 완료: {time.time()-t0:.1f}초  후보={result.total_passed}개")

if result.best:
    print("\n  ━ 최우선 에덴 후보 ━")
    print(result.best.summary())


# ════════════════════════════════════════════════════════════════════════════
# 【2】 행성 표면 2D 공간 탐사
# ════════════════════════════════════════════════════════════════════════════
print("\n" + "━" * 70)
print("  【2】 EdenSpatialGrid — 행성 표면 위도×경도 2D 히트맵")
print("━" * 70)

from cherubim import EdenSpatialGrid, make_antediluvian

ic_eden = make_antediluvian()
grid = EdenSpatialGrid(lat_steps=12, lon_steps=24)

print("\n  ── 에덴 시대 (antediluvian) 표면 스캔 ──")
heatmap_eden = grid.scan(ic_eden, verbose=True)
heatmap_eden.print_ascii(title="에덴 시대 행성 표면 에덴 점수", threshold=0.55)

print()
heatmap_eden.print_lat_profile()

zones = heatmap_eden.eden_zones(threshold=0.55)
if zones:
    print(f"\n  🌟 에덴 Zone {len(zones)}개 발견 (threshold=0.55):")
    for z in zones[:6]:
        print(f"     {z}")

print()

# 에덴 vs 현재 비교
from cherubim.initial_conditions import make_postdiluvian
ic_post = make_postdiluvian()

print("  ── 현재 지구 (postdiluvian) 표면 스캔 ──")
heatmap_post = grid.scan(ic_post, verbose=True)
heatmap_post.print_ascii(title="현재 지구 표면 에덴 점수", threshold=0.40)

delta = heatmap_eden.global_mean - heatmap_post.global_mean
print(f"\n  📊 에덴 vs 현재 비교:")
print(f"     에덴 평균: {heatmap_eden.global_mean:.3f}  최고: {heatmap_eden.global_max:.3f}")
print(f"     현재 평균: {heatmap_post.global_mean:.3f}  최고: {heatmap_post.global_max:.3f}")
print(f"     차이:     {delta:+.3f}  ({'에덴이 우수' if delta > 0 else '현재가 우수'})")


# ════════════════════════════════════════════════════════════════════════════
# 【3】 Ring Attractor Basin 안정성 검증
# ════════════════════════════════════════════════════════════════════════════
print("\n" + "━" * 70)
print("  【3】 EdenBasinStability — Ring Attractor Basin 안정성 검증")
print("  (교란에도 에덴 상태로 복귀하는 진정한 안정 Basin 판별)")
print("━" * 70)

from cherubim import EdenBasinStability

if result.candidates:
    bst = EdenBasinStability(use_ring_engine=True)
    top_candidates = result.candidates[:min(5, len(result.candidates))]
    basin_results  = bst.test_batch(top_candidates, verbose=True)
    bst.print_ranking(basin_results)

    if basin_results:
        print("  ━ 최고 Basin 안정성 후보 상세 ━")
        print(basin_results[0].summary())
else:
    print("  (후보 없음 — 탐색 결과 없음)")


# ════════════════════════════════════════════════════════════════════════════
# 【4】 다차원 파라미터 공간 탐사 (2D~3D)
# ════════════════════════════════════════════════════════════════════════════
print("\n" + "━" * 70)
print("  【4】 EdenParamScanner — 다차원 파라미터 공간 탐사 (GridND)")
print("━" * 70)

from cherubim import EdenParamScanner, CO2_AXIS, TEMP_AXIS, O2_AXIS, UV_AXIS, ALB_AXIS

scanner = EdenParamScanner(base_ic=ic_eden, threshold=0.50, verbose=True)

# 2D: CO2 × 온도 (기후 상태도)
print("\n  ── 2D 슬라이스: CO2 × 온도 (행성 기후 상태도) ──")
result_2d_co2_t = scanner.scan_2d(
    CO2_AXIS._replace(steps=10),
    TEMP_AXIS._replace(steps=10),
)
result_2d_co2_t.print_heatmap(
    title="CO2 × 표면온도 에덴 Basin 지도",
    threshold=0.50,
)
result_2d_co2_t.print_basin_boundary(threshold=0.50)

# 2D: UV × O2 (대기 보호막)
print("\n  ── 2D 슬라이스: UV 차폐 × O2 농도 (대기 보호막) ──")
result_2d_uv_o2 = scanner.scan_2d(
    UV_AXIS._replace(steps=10),
    O2_AXIS._replace(steps=8),
)
result_2d_uv_o2.print_heatmap(
    title="UV차폐 × O2농도 에덴 Basin 지도",
    threshold=0.50,
)

# 3D: CO2 × O2 × UV
print("\n  ── 3D 공간: CO2 × O2 × UV (핵심 기후 파라미터) ──")
result_3d = scanner.scan_nd([
    CO2_AXIS._replace(steps=6),
    O2_AXIS._replace(steps=5),
    UV_AXIS._replace(steps=5),
])
print(result_3d.summary())


# ════════════════════════════════════════════════════════════════════════════
# 【5】 5D Basin 형태 분석
# ════════════════════════════════════════════════════════════════════════════
print("\n" + "━" * 70)
print("  【5】 EdenBasinShape — 5D 파라미터 공간 Basin 형태 분석")
print("━" * 70)

print("\n  ── 5D 파라미터 공간 스캔 (CO2 × O2 × UV × Albedo × H2O) ──")
from cherubim import H2O_AXIS

result_5d = scanner.scan_nd([
    CO2_AXIS._replace(steps=4),
    O2_AXIS._replace(steps=4),
    UV_AXIS._replace(steps=4),
    ALB_AXIS._replace(steps=4),
    H2O_AXIS._replace(steps=4),
], max_points=5000)

print(result_5d.summary())

# Basin 형태 분석
shape = scanner.analyze_basin_shape(result_5d)
print(shape.summary())


# ════════════════════════════════════════════════════════════════════════════
# 최종 요약
# ════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  🏁 Cherubim v1.1.0 행성 탐사 엔진 — 전체 실행 완료")
print("=" * 70)
print()
print("  ┌──────────────────────────────────────────────────────────────┐")
print("  │  모듈           │  결과                                       │")
print("  ├──────────────────────────────────────────────────────────────┤")

n_candidates = len(result.candidates) if result else 0
best_score   = result.best.score if result and result.best else 0.0
print(f"  │  EdenSearchEngine │ 에덴 후보 {n_candidates:3d}개  "
      f"최고점={best_score:.3f}                │")

eden_pct_e = sum(1 for row in heatmap_eden.scores for s in row if s >= 0.55)
total_cells = len(heatmap_eden.lats) * len(heatmap_eden.lons)
print(f"  │  EdenSpatialGrid  │ Eden Zone {eden_pct_e}/{total_cells} 셀  "
      f"평균={heatmap_eden.global_mean:.3f}            │")

if result.candidates:
    n_stable = sum(1 for r in basin_results if r.is_stable)
    best_bd  = basin_results[0].basin_depth if basin_results else 0.0
    print(f"  │  EdenBasinStability│ 안정Basin {n_stable}/{len(basin_results)}개  "
          f"최고depth={best_bd:.3f}          │")

print(f"  │  EdenParamScanner │ 2D/3D/5D 스캔  "
      f"5D eden={result_5d.eden_frac*100:.1f}%           │")
print(f"  │  EdenBasinShape   │ {shape.dim}D Basin  "
      f"형태={shape.shape_label[:20]:20s}  │")
print("  └──────────────────────────────────────────────────────────────┘")
print()
print("  에덴 = 교란에도 유지되는 파라미터 공간의 안정 어트랙터")
print("  Cherubim이 그 Basin을 지킵니다.")
print()
