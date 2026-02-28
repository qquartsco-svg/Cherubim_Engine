"""Cherubim — Eden Basin Finder

"에덴은 좌표가 아니라 파라미터 상태(state basin)이다."

창세기에서 체루빔(Cherubim)은 에덴 동산의 입구를 지키며 생명나무로 가는 길을
스캔하는 존재다. 이 엔진은 그 이름을 따, 행성의 물리 파라미터 공간을 탐색해
에덴(생명 가능 상태 basin)의 조건을 찾아낸다.

  지구뿐 아니라 외계 행성(Exoplanet)에도 즉시 투입 가능한 독립 탐색 엔진.

구조:
  initial_conditions.py — 6개 파라미터 → 전 지구 동역학 상태 생성
  firmament.py          — 궁창(수증기 캐노피) 물리 모델
  flood.py              — 대홍수 4단계 전이 곡선
  geography.py          — 자기장 좌표계 + 시대별 지형
  search.py             — EdenSearchEngine (파라미터 공간 탐색 / Basin Finder)
  biology.py            — 물리 환경 → 수명 / 체형 / 생태계 안정성

빠른 시작:
    from cherubim import EdenSearchEngine, make_antediluvian_space
    engine = EdenSearchEngine()
    result = engine.search(make_antediluvian_space())
    print(result.best.summary())

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

__version__ = "1.0.0"
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
]
