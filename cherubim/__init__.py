"""Cherubim — Eden Basin Finder  v1.3.0

"에덴은 좌표가 아니라 파라미터 상태(state basin)이다."

창세기에서 체루빔(Cherubim)은 에덴 동산의 입구를 지키며 생명나무로 가는 길을
스캔하는 존재다. 이 엔진은 그 이름을 따, 행성의 물리 파라미터 공간을 탐색해
에덴(생명 가능 상태 basin)의 조건을 찾아낸다.

  지구뿐 아니라 외계 행성(Exoplanet)에도 즉시 투입 가능한 독립 탐색 엔진.

구조 (코어):
  initial_conditions.py — 6개 파라미터 → 전 지구 동역학 상태 생성
  firmament.py          — 궁창(수증기 캐노피) 물리 모델
  flood.py              — 대홍수 4단계 전이 곡선
  geography.py          — 자기장 좌표계 + 시대별 지형
  search.py             — EdenSearchEngine (파라미터 공간 탐색 / Basin Finder)
  biology.py            — 물리 환경 → 수명 / 체형 / 생태계 안정성

확장 모듈 (v1.1.0 신규):
  spatial_grid.py       — 행성 표면 2D 공간 탐사 (위도×경도 히트맵)
  basin_stability.py    — Ring Attractor 기반 에덴 Basin 안정성 검증
  param_space.py        — 2D~7D 다차원 파라미터 공간 탐사 (GridND)

확장 모듈 (v1.2.0 신규):
  extinction.py         — 궁창 붕괴 전이 곡선 + 대멸종 기능 매핑
                          FirmamentDecayEngine (integrity 1.0→0.0 전이)
                          ExtinctionMapper (지질 이벤트 × 궁창 상태 비교)

확장 모듈 (v1.3.0 신규 — "우리가 잘못 알고 있는 것" 시뮬레이터):
  coordinate_inverter.py — 좌표계 역전 시뮬레이터
                           현재(북=위) vs 에덴 기준(남=위) 에덴 히트맵 비교
                           자기장 방향 분석 + 단테 연옥산 위치 검증
  calendar.py            — 시스템 시간 재계산 모듈
                           세 가지 시계: AD달력 / 대홍수 기점 / 세차 위상
                           세차 반주기 오차 40년 = 전환 마커 단위 분석
  biology_baseline.py    — 생물 기준점 재설정
                           에덴(FI=1.0) vs 현재(FI=0.0) 수명/신장/돌연변이 비교
                           창세기 장수 기록 × 엔진 예측 교차 검증

빠른 시작:
    from cherubim import EdenSearchEngine, make_antediluvian_space
    engine = EdenSearchEngine()
    result = engine.search(make_antediluvian_space())
    print(result.best.summary())

공간 탐사 (신규):
    from cherubim import EdenSpatialGrid
    grid = EdenSpatialGrid(lat_steps=12, lon_steps=24)
    heatmap = grid.scan()
    heatmap.print_ascii()

Basin 안정성 검증 (신규):
    from cherubim import EdenBasinStability
    bst = EdenBasinStability()
    results = bst.test_batch(search_result.candidates[:5])
    bst.print_ranking(results)

다차원 파라미터 탐사 (신규):
    from cherubim import EdenParamScanner, CO2_AXIS, TEMP_AXIS
    scanner = EdenParamScanner()
    result2d = scanner.scan_2d(CO2_AXIS, TEMP_AXIS)
    result2d.print_heatmap()

외계 행성 탐색:
    from cherubim import EdenSearchEngine, make_exoplanet_space
    result = EdenSearchEngine().search(make_exoplanet_space(stellar_flux_scale=0.85))
    print(result.best.summary())
"""

from .initial_conditions import (
    InitialConditions,
    EarthBandState,
    make_antediluvian,
    make_postdiluvian,
    make_flood_peak,
)
from .firmament import (
    FirmamentLayer,
    FirmamentState,
    FloodEvent,
    make_firmament,
)
from .flood import (
    FloodEngine,
    FloodSnapshot,
    make_flood_engine,
)
from .geography import (
    EdenGeography,
    ArcticBasinState,
    MagneticFrameGeography,
    ExposedRegion,
    make_eden_geography,
    make_postdiluvian_geography,
    magnetic_protection_factor,
)
from .search import (
    EdenCriteria,
    EdenCandidate,
    SearchSpace,
    SearchResult,
    EdenSearchEngine,
    compute_eden_score,
    make_eden_search,
    make_antediluvian_space,
    make_postdiluvian_space,
    make_exoplanet_space,
)
from .biology import (
    BiologyFactors,
    EdenBiologyState,
    compute_biology,
    compare_biology,
    make_biology,
    LIFESPAN_PHYSICAL_MAX_YR,
    BODY_SIZE_PHYS_MAX_RATIO,
)

# ── 확장 모듈 v1.1.0 ──────────────────────────────────────────────────────────
from .spatial_grid import (
    EdenSpatialGrid,
    SpatialHeatmap,
    EdenZone,
    compute_cell_eden_score,
    make_spatial_grid,
    quick_surface_scan,
)
from .basin_stability import (
    EdenBasinStability,
    BasinStabilityResult,
    make_basin_stability,
    quick_basin_test,
)
from .param_space import (
    ParamAxis,
    ParamSlice2D,
    ParamScanResult,
    EdenBasinShape,
    EdenParamScanner,
    make_param_scanner,
    CO2_AXIS,
    TEMP_AXIS,
    O2_AXIS,
    UV_AXIS,
    ALB_AXIS,
    H2O_AXIS,
    LAND_AXIS,
)
# ── 확장 모듈 v1.2.0 ──────────────────────────────────────────────────────────
from .extinction import (
    FirmamentSnapshot,
    FirmamentDecayEngine,
    ExtinctionEvent,
    ExtinctionMapper,
    GEOLOGICAL_EVENTS,
    THRESHOLD_UV_DAMAGE,
    THRESHOLD_POLAR_COLD,
    THRESHOLD_SEASON_START,
    THRESHOLD_ICE_SHEET,
    THRESHOLD_MASS_EXT1,
    THRESHOLD_RAIN_START,
    THRESHOLD_MASS_EXT2,
    THRESHOLD_COLLAPSE,
    make_extinction_mapper,
    quick_extinction_analysis,
)
# ── 확장 모듈 v1.3.0 ──────────────────────────────────────────────────────────
from .coordinate_inverter import (
    CoordSystem,
    CoordinateInverter,
    CoordCompareResult,
    MagneticDirectionAnalysis,
    invert_lat, invert_lon,
    current_to_inverted, inverted_to_current,
    lat_label_inverted,
    quick_coord_comparison,
)
from .calendar import (
    SystemClock,
    TimeSnapshot,
    TROPICAL_YEAR_DAYS, SIDEREAL_YEAR_DAYS,
    PRECESSION_PERIOD_YR, PRECESSION_HALF_YR,
    AD_CURRENT, FLOOD_BCE_ESTIMATE, SYSTEM_YEAR,
    PRECESSION_PHASE_NOW, HALF_CYCLE_OFFSET_YR,
    TRANSITION_UNIT,
    make_system_clock,
    quick_time_analysis,
)
from .biology_baseline import (
    BiologySnapshot,
    BiologyBaseline,
    EDEN_LIFESPAN_YR, EDEN_HEIGHT_CM,
    OBS_LIFESPAN_YR, OBS_HEIGHT_CM,
    GENESIS_RECORDS, GENESIS_AVG_LIFESPAN,
    make_biology_baseline,
    quick_biology_report,
)

__version__ = "1.3.0"
__author__  = "GNJz (Qquarts)"
__project__ = "Cherubim — Eden Basin Finder"

__all__ = [
    # initial_conditions
    "InitialConditions", "EarthBandState",
    "make_antediluvian", "make_postdiluvian", "make_flood_peak",
    # firmament
    "FirmamentLayer", "FirmamentState", "FloodEvent", "make_firmament",
    # flood
    "FloodEngine", "FloodSnapshot", "make_flood_engine",
    # geography
    "EdenGeography", "ArcticBasinState", "MagneticFrameGeography",
    "ExposedRegion", "make_eden_geography", "make_postdiluvian_geography",
    "magnetic_protection_factor",
    # search  ← Eden Basin Finder 핵심
    "EdenCriteria", "EdenCandidate", "SearchSpace", "SearchResult",
    "EdenSearchEngine", "compute_eden_score", "make_eden_search",
    "make_antediluvian_space", "make_postdiluvian_space", "make_exoplanet_space",
    # biology
    "BiologyFactors", "EdenBiologyState",
    "compute_biology", "compare_biology", "make_biology",
    "LIFESPAN_PHYSICAL_MAX_YR", "BODY_SIZE_PHYS_MAX_RATIO",
    # ── 확장 모듈 v1.1.0 ──
    # spatial_grid — 행성 표면 2D 공간 탐사
    "EdenSpatialGrid", "SpatialHeatmap", "EdenZone",
    "compute_cell_eden_score", "make_spatial_grid", "quick_surface_scan",
    # basin_stability — Ring Attractor Basin 안정성
    "EdenBasinStability", "BasinStabilityResult",
    "make_basin_stability", "quick_basin_test",
    # param_space — GridND 다차원 파라미터 탐사
    "ParamAxis", "ParamSlice2D", "ParamScanResult",
    "EdenBasinShape", "EdenParamScanner", "make_param_scanner",
    "CO2_AXIS", "TEMP_AXIS", "O2_AXIS", "UV_AXIS",
    "ALB_AXIS", "H2O_AXIS", "LAND_AXIS",
    # ── 확장 모듈 v1.2.0 ──
    # extinction — 궁창 붕괴 전이 곡선 + 대멸종 매핑
    "FirmamentSnapshot", "FirmamentDecayEngine",
    "ExtinctionEvent", "ExtinctionMapper", "GEOLOGICAL_EVENTS",
    "THRESHOLD_UV_DAMAGE", "THRESHOLD_POLAR_COLD", "THRESHOLD_SEASON_START",
    "THRESHOLD_ICE_SHEET", "THRESHOLD_MASS_EXT1", "THRESHOLD_RAIN_START",
    "THRESHOLD_MASS_EXT2", "THRESHOLD_COLLAPSE",
    "make_extinction_mapper", "quick_extinction_analysis",
    # ── 확장 모듈 v1.3.0 ── "우리가 잘못 알고 있는 것" 시뮬레이터
    # coordinate_inverter — 좌표계 역전
    "CoordSystem", "CoordinateInverter", "CoordCompareResult",
    "MagneticDirectionAnalysis",
    "invert_lat", "invert_lon",
    "current_to_inverted", "inverted_to_current", "lat_label_inverted",
    "quick_coord_comparison",
    # calendar — 시스템 시간 재계산
    "SystemClock", "TimeSnapshot",
    "TROPICAL_YEAR_DAYS", "SIDEREAL_YEAR_DAYS",
    "PRECESSION_PERIOD_YR", "PRECESSION_HALF_YR",
    "AD_CURRENT", "FLOOD_BCE_ESTIMATE", "SYSTEM_YEAR",
    "PRECESSION_PHASE_NOW", "HALF_CYCLE_OFFSET_YR", "TRANSITION_UNIT",
    "make_system_clock", "quick_time_analysis",
    # biology_baseline — 생물 기준점 재설정
    "BiologySnapshot", "BiologyBaseline",
    "EDEN_LIFESPAN_YR", "EDEN_HEIGHT_CM",
    "OBS_LIFESPAN_YR", "OBS_HEIGHT_CM",
    "GENESIS_RECORDS", "GENESIS_AVG_LIFESPAN",
    "make_biology_baseline", "quick_biology_report",
]
