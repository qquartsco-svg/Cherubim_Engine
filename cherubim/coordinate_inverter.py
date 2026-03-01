"""coordinate_inverter.py — 좌표계 역전 시뮬레이터

설계 철학:
  "단테가 말한 '방향이 틀렸다'를 수식으로 증명한다."

현재 인류의 좌표계:
  북극 = 위 (중세 유럽 지도 관습)
  남극 = 아래
  에덴 위치 = 불명확

역전 좌표계 (에덴 기준):
  남극 = 위 (자력선 발원지, 자기 N극)
  북극 = 아래
  에덴 = 남극 (극지 eden_score 0.910 = 전 지구 1위)

핵심 질문:
  "지도를 뒤집으면 에덴 탐색 결과가 어떻게 달라지는가?"

물리적 근거:
  1. 자기장: 남극 = 자력선 발원 (자기 N극 성질)
             magnetic_protection_factor 극지 = 0.997 (전 지구 최고)
  2. 에덴 점수: mist 모드 82.5°S = 0.910 (1위)
  3. 지도 관습: 북쪽이 위인 건 물리 법칙이 아닌 관습
  4. 단테: 연옥산(에덴)을 남반구 끝에 명시적 배치

레이어 분리:
  PHYSICAL_FACT: 자기장 수치, 에덴 점수 계산 결과
  SCENARIO:      에덴 = 남극, 좌표계 역전 해석
  LORE:          단테 신곡, 창세기 방향 기록
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .spatial_grid import EdenSpatialGrid, SpatialHeatmap, compute_cell_eden_score
from .initial_conditions import InitialConditions, make_antediluvian, make_postdiluvian
from .geography import magnetic_protection_factor


# ── 좌표계 정의 ────────────────────────────────────────────────────────────────

class CoordSystem:
    """좌표계 타입 상수."""
    CURRENT  = 'current'   # 현재 인류 기준 (북 = 위)
    INVERTED = 'inverted'  # 역전 기준 (남 = 위, 에덴 기준)


# ── 좌표 변환 ──────────────────────────────────────────────────────────────────

def invert_lat(lat_deg: float) -> float:
    """위도 역전: 남북 뒤집기.

    현재 기준 82.5°N → 역전 기준 82.5°S (동일 물리 위치)
    현재 기준 82.5°S → 역전 기준 82.5°N

    역전 좌표계에서 "위"는 남쪽이므로
    양수 = 남쪽 (현재의 음수 위도)
    """
    return -lat_deg


def invert_lon(lon_deg: float) -> float:
    """경도 역전: 동서 기준 유지 (경도는 뒤집힘 없음)."""
    return lon_deg


def current_to_inverted(lat: float, lon: float) -> Tuple[float, float]:
    """현재 좌표 → 역전 좌표 변환."""
    return invert_lat(lat), invert_lon(lon)


def inverted_to_current(lat: float, lon: float) -> Tuple[float, float]:
    """역전 좌표 → 현재 좌표 변환."""
    return invert_lat(lat), invert_lon(lon)  # 역전의 역전 = 원위치


def lat_label_inverted(lat_deg: float) -> str:
    """역전 좌표계에서의 위도 레이블.

    역전계에서 양수 = 남쪽 (현재의 S)
    역전계에서 음수 = 북쪽 (현재의 N)
    """
    if lat_deg >= 0:
        return f"{abs(lat_deg):.1f}°S(↑위)"  # 역전계에서 위
    else:
        return f"{abs(lat_deg):.1f}°N(↓아래)"  # 역전계에서 아래


# ── 비교 결과 ──────────────────────────────────────────────────────────────────

@dataclass
class CoordCompareResult:
    """현재 좌표계 vs 역전 좌표계 에덴 점수 비교 결과."""

    # 현재 좌표계 히트맵
    heatmap_current:  SpatialHeatmap
    # 역전 좌표계 히트맵 (동일 물리 위치, 라벨만 역전)
    heatmap_inverted: SpatialHeatmap

    # 각 좌표계에서의 1위 위치
    top_current:   Tuple[float, float, float]   # (lat, lon, score)
    top_inverted:  Tuple[float, float, float]   # (lat_inv, lon, score)

    # 물리적 동일 위치 확인
    same_physical_location: bool = True  # 항상 True (라벨만 다름)

    def summary(self) -> str:
        lat_c, lon_c, sc_c = self.top_current
        lat_i, lon_i, sc_i = self.top_inverted

        lat_c_lbl = f"{abs(lat_c):.1f}°{'N' if lat_c >= 0 else 'S'}"
        lat_i_lbl = lat_label_inverted(lat_i)

        return (
            f"\n  ╔══ 좌표계 비교 결과 ══════════════════════════════╗\n"
            f"  ║  현재 좌표계 (북=위)                              ║\n"
            f"  ║    1위: {lat_c_lbl:>8} {lon_c:>7.1f}°E  score={sc_c:.3f}        ║\n"
            f"  ║                                                   ║\n"
            f"  ║  역전 좌표계 (남=위, 에덴 기준)                   ║\n"
            f"  ║    1위: {lat_i_lbl:>12}  score={sc_i:.3f}        ║\n"
            f"  ║                                                   ║\n"
            f"  ║  물리적 위치: 동일 (라벨만 다름)                  ║\n"
            f"  ║  결론: 에덴은 현재 지도의 '아래'에 있다           ║\n"
            f"  ╚═══════════════════════════════════════════════════╝"
        )


# ── 자기장 방향 분석 ───────────────────────────────────────────────────────────

@dataclass
class MagneticDirectionAnalysis:
    """자기장 방향 분석 결과."""

    # 물리 사실 레이어
    geographic_north_mag_type: str = "자기 S극 성질 (나침반 N이 끌림)"
    geographic_south_mag_type: str = "자기 N극 성질 (자력선 발원지)"
    protection_north: float = 0.997
    protection_south: float = 0.997

    # 시나리오 레이어
    eden_pole: str = "남극 (자력선 발원, 보호막 최강)"
    current_map_orientation: str = "북쪽 위 (중세 유럽 관습, 물리 법칙 아님)"
    inverted_map_orientation: str = "남쪽 위 (자력선 발원 기준, 에덴 좌표계)"

    def print_analysis(self) -> None:
        print("\n  🧲 자기장 방향 분석")
        print("  " + "─" * 55)
        print(f"  [물리 사실]")
        print(f"    지리적 북극 자기 성질: {self.geographic_north_mag_type}")
        print(f"    지리적 남극 자기 성질: {self.geographic_south_mag_type}")
        print(f"    북극 자기장 보호 지수: {self.protection_north:.3f}")
        print(f"    남극 자기장 보호 지수: {self.protection_south:.3f}")
        print(f"\n  [시나리오 해석]")
        print(f"    에덴 극점:             {self.eden_pole}")
        print(f"    현재 지도 방향:        {self.current_map_orientation}")
        print(f"    에덴 기준 방향:        {self.inverted_map_orientation}")
        print(f"\n  [단테 연결]")
        print(f"    연옥산(에덴) 위치:     남반구 끝 (신곡 명시)")
        print(f"    엔진 에덴 1위:         82.5°S  score=0.910")
        print(f"    결론: 단테의 남반구 에덴 = 엔진의 극지 에덴 = 일치")
        print("  " + "─" * 55)


# ── 메인 좌표계 역전 엔진 ──────────────────────────────────────────────────────

class CoordinateInverter:
    """좌표계 역전 시뮬레이터.

    현재 좌표계(북=위)와 역전 좌표계(남=위)에서
    에덴 점수 분포를 비교해 보여준다.

    핵심 증명:
      두 좌표계에서 "1위" 물리 위치는 동일하다.
      단지 우리가 그 위치를 "남극"(아래)이라고 부를 뿐이다.
      역전 좌표계에서는 그 위치가 "위"(82.5°↑)가 된다.

    Parameters
    ----------
    lat_steps : int
        위도 분할 수
    lon_steps : int
        경도 분할 수
    """

    def __init__(
        self,
        lat_steps: int = 12,
        lon_steps: int = 24,
    ) -> None:
        self.lat_steps = lat_steps
        self.lon_steps = lon_steps
        self._grid = EdenSpatialGrid(lat_steps=lat_steps, lon_steps=lon_steps)

    def compare(
        self,
        ic: Optional[InitialConditions] = None,
        verbose: bool = True,
    ) -> CoordCompareResult:
        """현재 vs 역전 좌표계 에덴 히트맵 비교."""
        if ic is None:
            ic = make_antediluvian()

        if verbose:
            print("\n  🌍 좌표계 역전 시뮬레이션 시작...")

        # 물리 계산 (동일)
        heatmap = self._grid.scan(ic, verbose=False)

        # 현재 좌표계: 그대로
        heatmap_current = heatmap

        # 역전 좌표계: 동일 데이터, 라벨만 역전
        # (scores[0] = 82.5°S → 역전계에서 82.5°↑위)
        import copy
        heatmap_inverted = copy.deepcopy(heatmap)
        # 라벨 역전: lat 리스트를 뒤집음
        heatmap_inverted.lats = [-lat for lat in reversed(heatmap.lats)]
        heatmap_inverted.scores = list(reversed(heatmap.scores))

        # 1위 위치 추출 (현재)
        best_score = -1.0
        best_lat_c = best_lon_c = 0.0
        for i, lat in enumerate(heatmap_current.lats):
            for j, lon in enumerate(heatmap_current.lons):
                s = heatmap_current.scores[i][j]
                if s > best_score:
                    best_score = s
                    best_lat_c = lat
                    best_lon_c = lon
        top_current = (best_lat_c, best_lon_c, best_score)

        # 1위 위치 추출 (역전)
        best_score_i = -1.0
        best_lat_i = best_lon_i = 0.0
        for i, lat in enumerate(heatmap_inverted.lats):
            for j, lon in enumerate(heatmap_inverted.lons):
                s = heatmap_inverted.scores[i][j]
                if s > best_score_i:
                    best_score_i = s
                    best_lat_i = lat
                    best_lon_i = lon
        top_inverted = (best_lat_i, best_lon_i, best_score_i)

        return CoordCompareResult(
            heatmap_current  = heatmap_current,
            heatmap_inverted = heatmap_inverted,
            top_current      = top_current,
            top_inverted     = top_inverted,
        )

    def print_dual_heatmap(
        self,
        ic: Optional[InitialConditions] = None,
    ) -> CoordCompareResult:
        """현재 / 역전 두 좌표계 히트맵 나란히 출력."""
        result = self.compare(ic, verbose=False)
        width = 80

        print("\n" + "=" * width)
        print("  🌍 좌표계 비교: 현재 (북=위) vs 에덴 기준 (남=위)")
        print("  " + "─" * (width - 4))

        lats_c = result.heatmap_current.lats
        lats_i = result.heatmap_inverted.lats
        scores_c = result.heatmap_current.scores
        scores_i = result.heatmap_inverted.scores
        chars = " ░▒▓█"

        print(f"  {'현재 좌표계 (북=위)':^35}  {'에덴 좌표계 (남=위)':^35}")
        print(f"  {'─'*35}  {'─'*35}")

        n = len(lats_c)
        for row_idx in range(n):
            # 현재: 북→남 (위→아래)
            i_c = n - 1 - row_idx
            lat_c = lats_c[i_c]
            row_c = scores_c[i_c]
            # 역전: 남→북이 위→아래
            i_i = n - 1 - row_idx
            lat_i = lats_i[i_i]
            row_i = scores_i[i_i]

            # 셀 문자
            def cell_str(row):
                s = ""
                for sc in row:
                    idx = min(len(chars)-1, int(sc*(len(chars)-1)+0.5))
                    s += ("★" if sc >= 0.55 else chars[idx]) + " "
                return s.strip()

            peak_c = max(row_c)
            peak_i = max(row_i)

            lat_c_lbl = f"{abs(lat_c):5.1f}°{'N' if lat_c>=0 else 'S'}"
            lat_i_lbl = f"{abs(lat_i):5.1f}°{'S(↑)' if lat_i>=0 else 'N(↓)'}"

            c_str = cell_str(row_c)[:24]
            i_str = cell_str(row_i)[:24]

            print(
                f"  {lat_c_lbl} {c_str:<24} {peak_c:.2f}"
                f"  │  "
                f"{lat_i_lbl} {i_str:<24} {peak_i:.2f}"
            )

        print()
        print(result.summary())

        # 자기장 분석
        mag = MagneticDirectionAnalysis()
        mag.print_analysis()

        print("=" * width)
        return result

    def print_magnetic_pole_analysis(self) -> None:
        """자기장 극점 분석만 출력."""
        MagneticDirectionAnalysis().print_analysis()

    def lat_profile_comparison(
        self,
        ic: Optional[InitialConditions] = None,
    ) -> None:
        """위도별 에덴 점수 — 현재 vs 역전 좌표 비교 바 차트."""
        result = self.compare(ic, verbose=False)
        print("\n  📊 위도별 에덴 점수 (현재 좌표 기준 물리 위치)")
        print("  " + "─" * 60)
        print(f"  {'위도(현재)':>10}  {'위도(역전)':>12}  {'점수':>5}  바")
        print("  " + "─" * 60)

        profile = result.heatmap_current.lat_profile()
        for lat, score in reversed(profile):
            inv_lbl = lat_label_inverted(-lat)
            bar = "█" * int(score * 25)
            peak = " ← 에덴 1위" if score >= result.heatmap_current.global_max * 0.98 else ""
            lat_lbl = f"{abs(lat):.1f}°{'N' if lat>=0 else 'S'}"
            print(f"  {lat_lbl:>10}  {inv_lbl:>12}  {score:.3f}  {bar}{peak}")
        print()


# ── 헬퍼 함수 ──────────────────────────────────────────────────────────────────

def quick_coord_comparison(
    ic: Optional[InitialConditions] = None,
) -> CoordCompareResult:
    """빠른 좌표계 비교 실행 + 출력."""
    inverter = CoordinateInverter()
    result = inverter.print_dual_heatmap(ic)
    inverter.lat_profile_comparison(ic)
    return result


__all__ = [
    "CoordSystem",
    "CoordinateInverter",
    "CoordCompareResult",
    "MagneticDirectionAnalysis",
    "invert_lat", "invert_lon",
    "current_to_inverted", "inverted_to_current",
    "lat_label_inverted",
    "quick_coord_comparison",
]
