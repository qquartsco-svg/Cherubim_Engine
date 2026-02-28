"""geography.py — 에덴 시대 지구 지형 + 자기장 좌표계

핵심 물리 전제:
  1. 지리 남극 근처 = 자기 N극 (magnetic north pole)
     → 자기력선이 빠져나오는 곳
     → 나침반 N이 끌리는 지리 북극은 자기 S극
     → 자기장 생성(다이나모) 기준으로는 남극이 "출발점"

  2. 세차운동 두 프레임:
     A. Rotation frame (교과서): 지리 북극 고정, 남극이 원뿔
     B. Magnetic frame (자기장): 자기 N극(지리 남극) 기준 자이로
     → B가 지구 다이나모(발전기) 구조와 일치

  3. 에덴 시대 f_land=0.40 조건:
     → 베링육교, 순다랜드, 북해 육지 노출
     → 북극해: 반폐쇄 내해 (현재 지중해 구조와 유사)
     → 남극: 빙하 없음 (T=+23°C) → 대륙 노출

참조:
  - solar/eden/initial_conditions.py (f_land=0.40)
  - solar/eden/firmament.py (pole_eq_delta=15K)
  - docs/ANTEDILUVIAN_ENV.md
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Tuple

# ── 물리 상수 ──────────────────────────────────────────────────────────────────

# 현재 자기축 기울기 (지리축 대비)
MAG_AXIS_TILT_DEG = 11.0       # 자기축 ↔ 자전축 각도차

# 세차운동 주기
PRECESSION_PERIOD_YR = 25_772  # 지구 세차 주기 [yr]

# 에덴 조건 (f_land=0.40) 에서 노출되는 대륙붕 깊이 기준
EDEN_SEA_LEVEL_OFFSET_M = -70.0  # 현재보다 70m 낮음 (빙하 없음)

# 자기장 프레임
FrameType = Literal['rotation', 'magnetic']


# ── 좌표 변환 ──────────────────────────────────────────────────────────────────

def rotation_to_magnetic_lat(geo_lat: float,
                               tilt_deg: float = MAG_AXIS_TILT_DEG) -> float:
    """지리 위도 → 자기 위도 근사 변환.

    실제 자기축은 공간적으로 복잡하지만,
    단순 기울기 모델로 1차 근사.

    Parameters
    ----------
    geo_lat : float   지리 위도 [-90, +90]
    tilt_deg: float   자기축 기울기 [°] (기본 11°)

    Returns
    -------
    float  자기 위도 (magnetic latitude)
    """
    # 자기축이 지리축에서 tilt_deg 기울어진 방향으로 투영
    # 단순화: lat_mag ≈ geo_lat + tilt_deg × cos(lon) — 여기서는 대칭 평균
    return geo_lat + tilt_deg * math.cos(math.radians(geo_lat))


def magnetic_protection_factor(geo_lat: float,
                                 tilt_deg: float = MAG_AXIS_TILT_DEG) -> float:
    """위도별 자기장 보호 강도 [0~1].

    자기 N극(지리 남극 근처) 주변: 자기력선 밀집 → 보호 강함
    자기 적도: 자기력선 수평 → 보호 중간
    자기 S극(지리 북극 근처): 자기력선 들어옴 → 보호 있으나 방향 반대

    물리적 근거:
      - 자기력선이 수직(극 근처): 하전입자가 지표 도달 전에 나선형으로 튕겨남
      - 자기력선이 수평(적도): Van Allen 벨트 최대 → 보호층 두꺼움
      - 종합: 극 > 적도 중간 > 남대서양 이상대(SAA) 최소
    """
    mag_lat = rotation_to_magnetic_lat(geo_lat, tilt_deg)
    # cos² 모델: 극(|lat|=90)→1.0, 적도→0.5 근사
    return 0.5 + 0.5 * math.sin(math.radians(abs(mag_lat)))


# ── 에덴 시대 노출 지형 ────────────────────────────────────────────────────────

@dataclass
class ExposedRegion:
    """현재 수몰되어 있지만 에덴 시대(f_land=0.40)에 노출된 지역."""
    name:        str
    lat:         float   # 중심 위도
    lon:         float   # 중심 경도
    area_km2:    float   # 면적 [km²]
    description: str


# 에덴 시대 노출 지형 목록 (f_land=0.40, 해수면 -70m 기준)
EDEN_EXPOSED_REGIONS: List[ExposedRegion] = [
    ExposedRegion(
        name        = 'Beringia',
        lat         = 65.0, lon = -168.0,
        area_km2    = 1_600_000,
        description = '베링 육교 — 시베리아-알래스카 연결. 현재 수심 50m → 완전 노출.'
                      '에덴 동쪽 문 역할. 에덴 이후 아메리카 인류 이동 경로.',
    ),
    ExposedRegion(
        name        = 'Sundaland',
        lat         = 2.0, lon = 108.0,
        area_km2    = 1_800_000,
        description = '순다랜드 — 동남아 대륙붕 노출. 인도네시아 섬들이 대륙으로 연결.'
                      '현재 수심 120m 이하 → 에덴 조건에서 노출.',
    ),
    ExposedRegion(
        name        = 'North_Sea_Land',
        lat         = 55.0, lon = 3.0,
        area_km2    = 600_000,
        description = '북해 육지 — 영국-유럽 대륙 연결. 도거랜드(Doggerland).'
                      '북극해 대서양 진입 경로 부분 차단.',
    ),
    ExposedRegion(
        name        = 'Arctic_Shelf_East',
        lat         = 75.0, lon = 140.0,
        area_km2    = 2_000_000,
        description = '동시베리아 대륙붕 노출. 북극해 동쪽 크게 육지화.'
                      '북극해 반폐쇄 내해 형성에 기여.',
    ),
    ExposedRegion(
        name        = 'Sahul',
        lat         = -15.0, lon = 130.0,
        area_km2    = 2_200_000,
        description = '사훌랜드 — 호주-뉴기니-태즈매니아 연결 대륙.'
                      '현재보다 훨씬 큰 남방 대륙.',
    ),
    ExposedRegion(
        name        = 'Antarctic_Coast',
        lat         = -70.0, lon = 0.0,
        area_km2    = 3_000_000,
        description = '남극 해안 노출 — 빙하 없는 에덴 조건 (T=+23°C) 에서'
                      '남극 대륙 해안선 완전 노출. 현재 빙하 아래 지형 드러남.',
    ),
]


# ── 북극해 내해 상태 ──────────────────────────────────────────────────────────

@dataclass
class ArcticBasinState:
    """에덴 시대 북극해 상태.

    핵심 가설:
      f_land=0.40 + 베링육교 + 동시베리아 대륙붕 노출
      → 북극해가 현재보다 훨씬 작은 반폐쇄 내해로 변환

    현재 지중해와 구조 유사성:
      - 둘 다 유라시아에 둘러싸인 내해
      - 동서 방향으로 긴 형태
      - 좁은 연결부로 외해와 통함
    """
    phase:              str    = 'antediluvian'

    # 연결부 상태
    bering_open:        bool   = False   # 베링 육교 → 동쪽 차단
    north_atlantic_open: bool  = True    # 그린란드-노르웨이 해 → 서쪽 일부 열림
    arctic_shelf_exposed: bool = True    # 동시베리아 대륙붕 → 북쪽 축소

    # 크기 추정
    area_fraction_of_current: float = 0.45  # 현재 북극해의 45% 크기
    mean_depth_m:              float = 800.0  # 현재 1038m → 해수면 하강으로 감소

    # 형태 특성
    enclosed_type:     str   = 'semi'   # 'full' / 'semi' / 'open'
    similarity_to_med: float = 0.6      # 지중해와 구조 유사도 [0~1]

    def summary(self) -> str:
        status = '반폐쇄 내해' if self.enclosed_type == 'semi' else '폐쇄 내해'
        return (
            f"북극해 상태 ({self.phase})\n"
            f"  크기: 현재의 {self.area_fraction_of_current*100:.0f}%\n"
            f"  형태: {status}\n"
            f"  베링해협: {'육지(차단)' if not self.bering_open else '열림'}\n"
            f"  북대서양: {'일부 열림' if self.north_atlantic_open else '차단'}\n"
            f"  지중해 유사도: {self.similarity_to_med*100:.0f}%\n"
        )


# ── 자기장 프레임 좌표계 ──────────────────────────────────────────────────────

@dataclass
class MagneticFrameGeography:
    """자기장 기준 지구 좌표계.

    핵심:
      교과서 모델 (Rotation frame):
        지리 북극 = 위, 지리 남극 = 아래
        → 팽이 모양 세차운동

      자기장 모델 (Magnetic frame):
        자기 N극 = 지리 남극 근처 = "출발점(source)"
        자기 S극 = 지리 북극 근처 = "도착점(sink)"
        → 자기력선이 남에서 나와 북으로 들어감
        → 자이로스코프 구조

    에덴 탐색에서의 의미:
      자기 N극(남극) 주변 = 자기장 보호 가장 강한 영역
      → 에덴 시대 남반구 고위도 = UV 차폐 + 변이 억제 최대
      → but 에덴 조건 T=+23°C 남극 = 온난 → 생태 가능
    """
    # 자기 N극 (현재: 지리 남극 근처)
    mag_N_geo_lat:  float = -80.0   # 지리 위도 기준
    mag_N_geo_lon:  float = 137.0   # 동경 (남극 자기 N극 실측 근사)

    # 자기 S극 (현재: 지리 북극 근처)
    mag_S_geo_lat:  float = +86.0
    mag_S_geo_lon:  float = 160.0   # 서경 (북극 자기 S극 실측 근사)

    # 자기축 기울기
    axis_tilt_deg:  float = MAG_AXIS_TILT_DEG   # 11°

    # 세차 프레임
    precession_frame: FrameType = 'magnetic'

    def band_protection(self, geo_lats: List[float]) -> List[float]:
        """12개 위도 밴드별 자기장 보호 강도."""
        return [magnetic_protection_factor(lat, self.axis_tilt_deg)
                for lat in geo_lats]

    def summary(self) -> str:
        return (
            f"자기장 좌표계\n"
            f"  자기 N극 (출발): 지리 {self.mag_N_geo_lat:.0f}°, "
            f"경도 {self.mag_N_geo_lon:.0f}°\n"
            f"  자기 S극 (도착): 지리 {self.mag_S_geo_lat:.0f}°, "
            f"경도 {self.mag_S_geo_lon:.0f}°\n"
            f"  자기축 기울기: {self.axis_tilt_deg}°\n"
            f"  세차 프레임: {self.precession_frame}\n"
            f"  해석: 지리 남극 = 자기 N극 = 자기력선 출발지\n"
        )


# ── 에덴 지리 통합 ────────────────────────────────────────────────────────────

@dataclass
class EdenGeography:
    """에덴 시대 전체 지리 상태.

    InitialConditions (f_land=0.40) 와 연동.
    """
    phase:          str                  = 'antediluvian'
    arctic_basin:   ArcticBasinState     = field(default_factory=ArcticBasinState)
    mag_frame:      MagneticFrameGeography = field(
                        default_factory=MagneticFrameGeography)
    exposed:        List[ExposedRegion]  = field(
                        default_factory=lambda: EDEN_EXPOSED_REGIONS.copy())

    # 위도 밴드별 육지 비율 (f_land=0.40, 에덴 조건)
    # 현재 대비 대륙붕 노출로 고위도 증가
    band_land_fraction: List[float] = field(default_factory=lambda: [
        0.45,   # -82.5° (남극 해안 노출, 빙하 없음)
        0.30,   # -67.5° (남극 주변 대륙붕)
        0.35,   # -52.5° (파타고니아, 사훌 남부)
        0.50,   # -37.5° (사훌, 아프리카 남부)
        0.42,   # -22.5° (열대)
        0.38,   # -7.5°  (순다랜드 포함)
        0.42,   # +7.5°  (순다랜드)
        0.48,   # +22.5° (인도, 아라비아)
        0.52,   # +37.5° (지중해, 북해 육지)
        0.58,   # +52.5° (북해 육지, 베링)
        0.62,   # +67.5° (동시베리아 대륙붕 노출)
        0.50,   # +82.5° (북극해 축소, 일부 육지)
    ])

    def band_protection(self) -> List[float]:
        """12개 밴드 자기장 보호 강도."""
        lats = [-82.5, -67.5, -52.5, -37.5, -22.5, -7.5,
                  7.5,  22.5,  37.5,  52.5,  67.5,  82.5]
        return self.mag_frame.band_protection(lats)

    def total_exposed_area_km2(self) -> float:
        return sum(r.area_km2 for r in self.exposed)

    def summary(self) -> str:
        prot = self.band_protection()
        lines = [
            f"=== 에덴 지리 상태 ({self.phase}) ===\n",
            self.arctic_basin.summary(),
            self.mag_frame.summary(),
            f"노출 지형 ({len(self.exposed)}개):",
        ]
        for r in self.exposed:
            lines.append(f"  {r.name:20s} {r.area_km2/1e6:.1f}M km²  "
                         f"({r.lat:+.0f}°, {r.lon:+.0f}°)")
        lines.append(
            f"\n총 신규 노출 면적: {self.total_exposed_area_km2()/1e6:.1f}M km²"
        )
        lines.append("\n위도밴드 자기장 보호 강도:")
        lats = [-82.5, -67.5, -52.5, -37.5, -22.5, -7.5,
                  7.5,  22.5,  37.5,  52.5,  67.5,  82.5]
        for lat, p, lf in zip(lats, prot, self.band_land_fraction):
            bar = '█' * int(p * 20)
            lines.append(f"  {lat:+6.1f}°  보호 {p:.2f} {bar:20s}  육지 {lf*100:.0f}%")
        return '\n'.join(lines)


# ── 팩토리 ────────────────────────────────────────────────────────────────────

def make_eden_geography() -> EdenGeography:
    """에덴 시대 지리 — 궁창 완전체, 대홍수 이전."""
    return EdenGeography(
        phase       = 'antediluvian',
        arctic_basin= ArcticBasinState(
            phase               = 'antediluvian',
            bering_open         = False,
            north_atlantic_open = True,
            arctic_shelf_exposed= True,
            area_fraction_of_current = 0.45,
            enclosed_type       = 'semi',
            similarity_to_med   = 0.60,
        ),
        mag_frame   = MagneticFrameGeography(
            precession_frame = 'magnetic',
        ),
    )


def make_postdiluvian_geography() -> EdenGeography:
    """대홍수 이후 지리 — 현재 지구."""
    return EdenGeography(
        phase       = 'postdiluvian',
        arctic_basin= ArcticBasinState(
            phase               = 'postdiluvian',
            bering_open         = False,   # 현재도 좁은 해협
            north_atlantic_open = True,
            arctic_shelf_exposed= False,
            area_fraction_of_current = 1.00,
            enclosed_type       = 'semi',
            similarity_to_med   = 0.40,   # 빙하·해수면 차이로 유사도 감소
        ),
        mag_frame   = MagneticFrameGeography(
            precession_frame = 'rotation',  # 현재 교과서 프레임
        ),
        band_land_fraction = [
            0.10, 0.15, 0.30, 0.45, 0.38, 0.32,
            0.35, 0.45, 0.50, 0.48, 0.30, 0.10,
        ],
    )


__all__ = [
    'EdenGeography',
    'ArcticBasinState',
    'MagneticFrameGeography',
    'ExposedRegion',
    'make_eden_geography',
    'make_postdiluvian_geography',
    'magnetic_protection_factor',
    'rotation_to_magnetic_lat',
    'EDEN_EXPOSED_REGIONS',
]
