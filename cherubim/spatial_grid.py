"""spatial_grid.py — 행성 표면 2D 공간 탐사 모듈

확장 설계 철학:
  "에덴은 파라미터 공간의 basin이다 — 그 basin은 행성 표면 어디에 펼쳐지는가?"

기존 EdenSearchEngine은 12개 위도밴드(1D 선형)로 행성을 분석한다.
이 모듈은 위도 × 경도 2D 그리드로 확장해 에덴 분포 지도(히트맵)를 생성한다.

주요 기능:
  EdenSpatialGrid   — 위도×경도 2D 그리드에서 에덴 점수 계산
  SpatialHeatmap    — 히트맵 결과 컨테이너 (ASCII + 수치)
  PlanetSurface     — 행성 표면 파라미터 공간 정의
  cluster_eden_zones — 에덴 클러스터 영역 식별

활용 예시:
  from cherubim.spatial_grid import EdenSpatialGrid
  grid = EdenSpatialGrid(lat_steps=24, lon_steps=48)
  heatmap = grid.scan(ic)
  heatmap.print_ascii()
  zones = heatmap.eden_zones(threshold=0.6)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .initial_conditions import InitialConditions, make_antediluvian
from .geography import magnetic_protection_factor

# ── 위도 / 경도 그리드 기본 설정 ────────────────────────────────────────────────

_DEFAULT_LAT_STEPS = 12   # 남→북 (−90 ~ +90), 기본 12단계 (기존 밴드와 호환)
_DEFAULT_LON_STEPS = 24   # 서→동 (−180 ~ +180), 기본 24단계


# ── 셀 단위 로컬 수정자 ──────────────────────────────────────────────────────────

def _lat_temperature_bias(lat_deg: float, precip_mode: str = 'rain') -> float:
    """위도에 따른 온도 편차 [°C 상대].

    현재(rain 모드): 적도(0°) → 0, 극(±90°) → −40°C.
    에덴/궁창(mist 모드): 수증기 캐노피 온실 효과 → 극지 편차 −15°C로 감소.
      - 궁창이 전 지구 균온을 유지 → 자전축 기울기 거의 0° 상태
      - 태양 입사각 편차를 수증기 캐노피가 흡수·재복사해 평탄화
      - 지질 기록(적도~극지 균등 화석): 극지 온도차 약 15°C 이내 추정
    """
    max_bias = -15.0 if precip_mode == 'mist' else -40.0
    return max_bias * (1.0 - math.cos(math.radians(lat_deg)))


def _lon_continental_bias(lon_deg: float, f_land: float) -> float:
    """경도에 따른 대륙/해양 분포 편차 (단순화).

    내륙성 기후 효과: 대륙 중심(180° 기준)에서 일교차 증폭.
    실제 구현에서는 고도 + 해안 거리 활용.
    여기서는 f_land를 사인파로 변조해 지역 차이를 모사.
    """
    # 경도 편차: sin 곡선으로 대륙/해양 분포 패턴 생성
    phase = math.radians(lon_deg * 2)   # 180° 주기 → 두 개의 대륙 (지구형)
    return f_land * 3.0 * math.sin(phase)  # 최대 ±3°C 대륙성 편차


def _local_magnetic_protection(lat_deg: float) -> float:
    """위도별 자기장 보호 지수 (극관 UV 노출 반영)."""
    return magnetic_protection_factor(lat_deg)


def _local_soil_moisture(lat_deg: float, precip_mode: str) -> float:
    """위도 + 강수 모드 → 로컬 토양수분 지수 [0~1]."""
    # 열대수렴대 (±10°) 최고, 아열대(±30°) 최저, 온대(±50°) 중간
    lat = abs(lat_deg)
    if precip_mode == 'mist':
        # 에덴: 안개 → 전 위도 균등 공급
        base = 0.80
    else:
        # 현재: 강수 → 위도별 강수대 패턴
        if lat < 10:
            base = 0.90   # 열대수렴대
        elif lat < 30:
            base = 0.30   # 아열대 사막
        elif lat < 60:
            base = 0.65   # 온대
        else:
            base = 0.20   # 극지 건조
    return base


# ── 셀 점수 계산 ────────────────────────────────────────────────────────────────

def compute_cell_eden_score(
    lat_deg: float,
    lon_deg: float,
    ic: InitialConditions,
) -> float:
    """단일 (위도, 경도) 셀의 에덴 점수 계산 [0~1].

    기본 행성 파라미터(ic)에 공간 편차를 더해
    각 셀의 실제 환경을 추정한다.

    점수 구성:
      온도 적합도   35%
      토양수분      20%
      GPP 추정     25%
      자기장 보호   20%
    """
    b = ic.band

    # ── 로컬 온도 추정 ─────────────────────────────────────────────────────────
    base_T_C = ic.T_surface_K - 273.15
    local_T_C = (
        base_T_C
        + _lat_temperature_bias(lat_deg, ic.precip_mode)   # 궁창 모드 반영
        + _lon_continental_bias(lon_deg, ic.f_land)
    )

    T_OPT, T_SIG = 28.0, 14.0
    t_score = math.exp(-0.5 * ((local_T_C - T_OPT) / T_SIG) ** 2)
    t_score = max(0.0, t_score) if 0.0 <= local_T_C <= 55.0 else 0.0

    # ── 로컬 토양수분 ──────────────────────────────────────────────────────────
    w_score = _local_soil_moisture(lat_deg, ic.precip_mode)

    # ── GPP 추정 ───────────────────────────────────────────────────────────────
    # 밴드 인덱스 매핑 (위도 → 0~11 인덱스)
    band_idx = min(11, max(0, int((lat_deg + 90) / 15.0)))
    gpp_band = float(b.GPP[band_idx])
    # 경도 편차: 대륙 내부는 건조 → GPP 10~20% 감소
    lon_factor = 1.0 - 0.15 * abs(math.sin(math.radians(lon_deg)))
    gpp_local = gpp_band * lon_factor
    # 궁창(mist) 모드: 극지도 안개 수분 공급 → GPP 하한 보정
    if ic.precip_mode == 'mist' and abs(lat_deg) > 60:
        # 에덴 시대 극지: 균온 + 안개 → 현재 아열대 수준 GPP 보장
        gpp_local = max(gpp_local, 0.35)
    gpp_score = min(1.0, gpp_local / 0.8)

    # ── 자기장 보호 ────────────────────────────────────────────────────────────
    mag_score = _local_magnetic_protection(lat_deg)
    # UV 차폐 반영
    if ic.UV_shield > 0:
        mag_score = mag_score * (0.5 + 0.5 * ic.UV_shield)
    else:
        mag_score = mag_score * 0.3  # UV 차폐 없으면 극지 노출↑

    # ── 종합 점수 ──────────────────────────────────────────────────────────────
    score = (
        t_score   * 0.35 +
        w_score   * 0.20 +
        gpp_score * 0.25 +
        mag_score * 0.20
    )

    # 빙하 패널티: 극지방 (|lat| > 67.5°) 빙하 여부
    # 궁창(mist) 모드: 빙하 없음 (균온) → 패널티 면제
    if abs(lat_deg) > 67.5 and ic.precip_mode != 'mist':
        ice_band = b.ice_mask[0 if lat_deg < 0 else 11]
        if ice_band:
            score *= 0.1  # 빙하 지역은 에덴 불가

    return round(max(0.0, min(1.0, score)), 4)


# ── 히트맵 결과 ────────────────────────────────────────────────────────────────

@dataclass
class EdenZone:
    """에덴 판정 클러스터 영역."""
    lat_center: float    # 중심 위도 [°]
    lon_center: float    # 중심 경도 [°]
    lat_range:  Tuple[float, float]  # 위도 범위
    lon_range:  Tuple[float, float]  # 경도 범위
    mean_score: float    # 평균 에덴 점수
    peak_score: float    # 최고 에덴 점수
    cell_count: int      # 셀 수
    area_frac:  float    # 전체 표면 대비 비율 [0~1]

    def __str__(self) -> str:
        lat_n = "N" if self.lat_center >= 0 else "S"
        lon_e = "E" if self.lon_center >= 0 else "W"
        return (
            f"EdenZone({abs(self.lat_center):.1f}°{lat_n}, "
            f"{abs(self.lon_center):.1f}°{lon_e}  "
            f"score={self.mean_score:.3f}  "
            f"area={self.area_frac*100:.1f}%  "
            f"cells={self.cell_count})"
        )


@dataclass
class SpatialHeatmap:
    """2D 에덴 점수 히트맵 결과.

    Attributes
    ----------
    scores    : 2D 배열 [lat_steps × lon_steps] 에덴 점수
    lats      : 위도 중심값 리스트 [lat_steps]
    lons      : 경도 중심값 리스트 [lon_steps]
    ic        : 기반 InitialConditions
    global_mean : 전 표면 평균 에덴 점수
    global_max  : 전 표면 최고 에덴 점수
    """
    scores:      List[List[float]]     # [lat_i][lon_j]
    lats:        List[float]
    lons:        List[float]
    ic:          InitialConditions
    global_mean: float = 0.0
    global_max:  float = 0.0
    global_min:  float = 0.0

    def __post_init__(self) -> None:
        flat = [s for row in self.scores for s in row]
        if flat:
            self.global_mean = round(sum(flat) / len(flat), 4)
            self.global_max  = round(max(flat), 4)
            self.global_min  = round(min(flat), 4)

    # ── ASCII 히트맵 출력 ─────────────────────────────────────────────────────

    def print_ascii(
        self,
        title: str = "",
        threshold: float = 0.5,
        chars: str = " ░▒▓█",
    ) -> None:
        """터미널 ASCII 아트 히트맵 출력.

        Parameters
        ----------
        title     : 상단 제목 (없으면 자동 생성)
        threshold : 에덴 판정 임계값 (이상 → ★ 표시)
        chars     : 점수 구간별 표시 문자 (5단계)
        """
        n_lat = len(self.lats)
        n_lon = len(self.lons)

        phase_label = getattr(self.ic, 'phase', 'unknown')
        hdr = title or f"🌍 행성 에덴 점수 히트맵 ({phase_label})"
        width = max(60, n_lon * 2 + 20)

        print("=" * width)
        print(f"  {hdr}")
        print(f"  위도 {n_lat}단계 × 경도 {n_lon}단계  |  "
              f"평균={self.global_mean:.3f}  "
              f"최고={self.global_max:.3f}  "
              f"최저={self.global_min:.3f}")
        print(f"  임계값={threshold:.2f}  위치: " + chars[-1] + " = Eden Zone")
        print("  " + "─" * (width - 4))

        # 경도 헤더 (간략)
        lon_header = "  위도    W←"
        lon_header += "─" * max(0, n_lon - 4)
        lon_header += "→E"
        print(lon_header)
        print()

        # 남→북 순서 (화면 상단=북)
        for i in reversed(range(n_lat)):
            lat = self.lats[i]
            row_scores = self.scores[i]
            row_str = ""
            for s in row_scores:
                idx = min(len(chars) - 1, int(s * (len(chars) - 1) + 0.5))
                c = chars[idx]
                # 에덴 임계값 초과 → 강조
                if s >= threshold:
                    c = "★"
                row_str += c + " "

            lat_label = f"{abs(lat):5.1f}°{'N' if lat >= 0 else 'S'}"
            bar_max = max(row_scores) if row_scores else 0
            print(f"  {lat_label}  {row_str}  {bar_max:.2f}")

        print()
        # 전체 에덴 영역 비율
        eden_cells = sum(1 for row in self.scores for s in row if s >= threshold)
        total_cells = n_lat * n_lon
        eden_pct = eden_cells / total_cells * 100 if total_cells else 0
        print(f"  ★ Eden Zone (≥{threshold:.2f}): "
              f"{eden_cells}/{total_cells} 셀 = {eden_pct:.1f}% 표면")
        print("=" * width)

    # ── 에덴 클러스터 영역 식별 ──────────────────────────────────────────────

    def eden_zones(self, threshold: float = 0.55) -> List[EdenZone]:
        """threshold 이상 셀들을 클러스터링해 EdenZone 목록 반환.

        단순 구현: 임계값 이상 셀을 수집 → 위도 구간별로 묶음.
        """
        n_lat = len(self.lats)
        n_lon = len(self.lons)

        # 위도 구간별 에덴 셀 수집
        lat_zones: Dict[int, List[Tuple[int, int, float]]] = {}
        for i in range(n_lat):
            for j in range(n_lon):
                s = self.scores[i][j]
                if s >= threshold:
                    lat_zones.setdefault(i, []).append((i, j, s))

        zones: List[EdenZone] = []
        total_cells = n_lat * n_lon

        for lat_i, cells in lat_zones.items():
            if not cells:
                continue
            lons_in_zone = [self.lons[j] for _, j, _ in cells]
            scores_in    = [s for _, _, s in cells]
            lats_in_zone = [self.lats[i] for i, _, _ in cells]

            zone = EdenZone(
                lat_center = sum(lats_in_zone) / len(lats_in_zone),
                lon_center = sum(lons_in_zone) / len(lons_in_zone),
                lat_range  = (min(lats_in_zone), max(lats_in_zone)),
                lon_range  = (min(lons_in_zone), max(lons_in_zone)),
                mean_score = round(sum(scores_in) / len(scores_in), 4),
                peak_score = round(max(scores_in), 4),
                cell_count = len(cells),
                area_frac  = round(len(cells) / total_cells, 4),
            )
            zones.append(zone)

        # 점수 내림차순 정렬
        zones.sort(key=lambda z: z.mean_score, reverse=True)
        return zones

    # ── 위도별 평균 에덴 점수 (1D 투영) ─────────────────────────────────────

    def lat_profile(self) -> List[Tuple[float, float]]:
        """각 위도의 평균 에덴 점수 → [(lat, mean_score), ...]."""
        profile = []
        for i, lat in enumerate(self.lats):
            row = self.scores[i]
            mean = sum(row) / len(row) if row else 0.0
            profile.append((lat, round(mean, 4)))
        return profile

    def print_lat_profile(self) -> None:
        """위도 프로파일 ASCII 바 차트."""
        profile = self.lat_profile()
        print("\n  위도별 평균 에덴 점수 (1D 투영)")
        print("  " + "─" * 50)
        for lat, score in reversed(profile):
            bar = "█" * int(score * 30)
            lat_label = f"{abs(lat):5.1f}°{'N' if lat >= 0 else 'S'}"
            flag = " ← PEAK" if score >= self.global_max * 0.95 else ""
            print(f"  {lat_label}  {bar:<30}  {score:.3f}{flag}")
        print()

    # ── JSON 직렬화 ───────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "phase":       getattr(self.ic, 'phase', 'unknown'),
            "lat_steps":   len(self.lats),
            "lon_steps":   len(self.lons),
            "global_mean": self.global_mean,
            "global_max":  self.global_max,
            "global_min":  self.global_min,
            "lats":        self.lats,
            "lons":        self.lons,
            "scores":      self.scores,
        }


# ── 메인 탐사 클래스 ────────────────────────────────────────────────────────────

class EdenSpatialGrid:
    """행성 표면 2D 공간 에덴 탐사 엔진.

    위도×경도 그리드의 각 셀에 대해 에덴 점수를 계산해
    행성 표면의 에덴 분포 지도(히트맵)를 생성한다.

    Parameters
    ----------
    lat_steps : int
        위도 분할 수 (기본 12 = 기존 밴드와 동일)
    lon_steps : int
        경도 분할 수 (기본 24 = 15° 간격)
    score_fn  : callable, optional
        셀 점수 함수. None이면 compute_cell_eden_score 사용.

    Examples
    --------
    >>> grid = EdenSpatialGrid(lat_steps=12, lon_steps=24)
    >>> heatmap = grid.scan(make_antediluvian())
    >>> heatmap.print_ascii()
    >>> zones = heatmap.eden_zones(threshold=0.6)
    """

    def __init__(
        self,
        lat_steps: int = _DEFAULT_LAT_STEPS,
        lon_steps: int = _DEFAULT_LON_STEPS,
        score_fn=None,
    ) -> None:
        self.lat_steps = lat_steps
        self.lon_steps = lon_steps
        self.score_fn  = score_fn or compute_cell_eden_score

        # 위도 중심값 생성 (−90°~+90°)
        lat_half = 90.0 / lat_steps
        self.lats = [
            -90.0 + lat_half + i * (180.0 / lat_steps)
            for i in range(lat_steps)
        ]
        # 경도 중심값 생성 (−180°~+180°)
        lon_half = 180.0 / lon_steps
        self.lons = [
            -180.0 + lon_half + j * (360.0 / lon_steps)
            for j in range(lon_steps)
        ]

    def scan(
        self,
        ic: Optional[InitialConditions] = None,
        verbose: bool = True,
    ) -> SpatialHeatmap:
        """행성 표면 전체 스캔 → SpatialHeatmap 반환.

        Parameters
        ----------
        ic      : InitialConditions. None이면 antediluvian 기본값 사용.
        verbose : True이면 진행 상황 출력.
        """
        if ic is None:
            ic = make_antediluvian()

        if verbose:
            print(f"  🔭 행성 표면 공간 탐사: "
                  f"{self.lat_steps}×{self.lon_steps} = "
                  f"{self.lat_steps * self.lon_steps} 셀 스캔 중...")

        scores: List[List[float]] = []
        for i, lat in enumerate(self.lats):
            row: List[float] = []
            for lon in self.lons:
                s = self.score_fn(lat, lon, ic)
                row.append(s)
            scores.append(row)

        heatmap = SpatialHeatmap(
            scores = scores,
            lats   = self.lats,
            lons   = self.lons,
            ic     = ic,
        )

        if verbose:
            print(f"  ✅ 스캔 완료: 평균 에덴={heatmap.global_mean:.3f}  "
                  f"최고={heatmap.global_max:.3f}")

        return heatmap

    def compare_phases(
        self,
        ic_eden: Optional[InitialConditions] = None,
        ic_post: Optional[InitialConditions] = None,
        verbose: bool = True,
    ) -> Tuple[SpatialHeatmap, SpatialHeatmap]:
        """에덴 시대 vs 현재 지구 히트맵 비교.

        Returns
        -------
        (eden_heatmap, post_heatmap)
        """
        from .initial_conditions import make_postdiluvian

        if ic_eden is None:
            ic_eden = make_antediluvian()
        if ic_post is None:
            ic_post = make_postdiluvian()

        if verbose:
            print("\n  📊 에덴 vs 현재 지구 공간 비교 시작")

        h_eden = self.scan(ic_eden, verbose=verbose)
        h_post = self.scan(ic_post, verbose=verbose)

        if verbose:
            print(f"\n  에덴(antediluvian) 평균 에덴점수: {h_eden.global_mean:.3f}")
            print(f"  현재(postdiluvian) 평균 에덴점수: {h_post.global_mean:.3f}")
            delta = h_eden.global_mean - h_post.global_mean
            print(f"  차이(에덴 - 현재):               {delta:+.3f}")

        return h_eden, h_post


# ── 헬퍼 함수 ──────────────────────────────────────────────────────────────────

def make_spatial_grid(
    lat_steps: int = 12,
    lon_steps: int = 24,
) -> EdenSpatialGrid:
    """EdenSpatialGrid 생성 헬퍼."""
    return EdenSpatialGrid(lat_steps=lat_steps, lon_steps=lon_steps)


def quick_surface_scan(
    ic: Optional[InitialConditions] = None,
    lat_steps: int = 12,
    lon_steps: int = 24,
    threshold: float = 0.55,
    print_map: bool = True,
) -> SpatialHeatmap:
    """빠른 행성 표면 스캔 + 히트맵 출력.

    Parameters
    ----------
    ic         : InitialConditions (None → antediluvian)
    lat_steps  : 위도 분할 수
    lon_steps  : 경도 분할 수
    threshold  : 에덴 임계값
    print_map  : True이면 즉시 ASCII 출력

    Returns
    -------
    SpatialHeatmap
    """
    grid = EdenSpatialGrid(lat_steps=lat_steps, lon_steps=lon_steps)
    heatmap = grid.scan(ic)
    if print_map:
        heatmap.print_ascii(threshold=threshold)
        heatmap.print_lat_profile()
        zones = heatmap.eden_zones(threshold=threshold)
        if zones:
            print(f"  🌟 Eden Zone {len(zones)}개 발견:")
            for z in zones[:5]:
                print(f"     {z}")
        else:
            print(f"  ⚠  threshold={threshold:.2f} 이상 Eden Zone 없음")
    return heatmap


__all__ = [
    "EdenSpatialGrid",
    "SpatialHeatmap",
    "EdenZone",
    "compute_cell_eden_score",
    "make_spatial_grid",
    "quick_surface_scan",
]
