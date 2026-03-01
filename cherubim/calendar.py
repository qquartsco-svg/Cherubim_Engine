"""calendar.py — 시스템 시간 재계산 모듈

설계 철학:
  "인류는 2,026년짜리 달력을 보고 있지만
   실제 시스템 클럭은 12,926년째 돌고 있다."

세 가지 시계를 동시에 표시:
  1. AD_YEAR       : 서기 달력 (현재 인류 기준)
  2. SYSTEM_YEAR   : 대홍수 기점 경과 (시스템 클럭)
  3. PRECESSION    : 세차운동 위상 (천문 좌표)

피드백 기반 핵심 물리:
  Tropical year  : 365.24219일 (계절 기준, 우리 달력)
  Sidereal year  : 365.25636일 (별 기준)
  차이           : 약 20분 24초/년
  12,900년 누적  : ≈ 179일 ≈ 약 반 년 위상차

세차운동 위상 오차 (Phase Ambiguity):
  세차 반주기    : 12,886년
  대홍수 경과    : 12,926년
  차이           : 40년 (= 모세 광야 유랑 단위)
  의미           : 세차 반주기 근처 위상 정렬 오차 영역

40 단위 패턴:
  홍수 강수      : 40일
  모세 광야      : 40년
  세차 위상 오차 : 40년
  공통 의미      : 시스템 전환 구간 마커

레이어 분리:
  PHYSICAL_FACT : 천문 계산 (tropical/sidereal 차이, 세차 주기)
  SCENARIO      : 대홍수 기점 해석, 위상 오차 의미
  LORE          : 모세 40년, 단테 시간 오류 경고
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ── 천문 상수 (물리 사실) ───────────────────────────────────────────────────────

TROPICAL_YEAR_DAYS   = 365.24219   # 계절의 해 (달력 기준)
SIDEREAL_YEAR_DAYS   = 365.25636   # 별의 해
YEAR_DIFF_DAYS       = SIDEREAL_YEAR_DAYS - TROPICAL_YEAR_DAYS  # ≈ 0.01417일/년
YEAR_DIFF_MINUTES    = YEAR_DIFF_DAYS * 24 * 60                 # ≈ 20.4분/년

PRECESSION_PERIOD_YR = 25_772.0    # 세차운동 완전 주기 (년)
PRECESSION_HALF_YR   = PRECESSION_PERIOD_YR / 2  # 반주기 ≈ 12,886년
PRECESSION_ARCSEC_YR = 50.29       # 세차 속도 (각초/년)

# ── 시나리오 상수 ──────────────────────────────────────────────────────────────

AD_CURRENT           = 2026        # 현재 서기 연도
AD_ORIGIN_ERROR_YR   = 5           # 기원점 오차 추정 (헤롯 기준 4~6년)
FLOOD_BCE_ESTIMATE   = 10_900      # 대홍수(영거 드라이아스) 추정 연도 (BC)
SYSTEM_YEAR          = FLOOD_BCE_ESTIMATE + AD_CURRENT  # 시스템 클럭 경과년

PRECESSION_PHASE_NOW = SYSTEM_YEAR / PRECESSION_PERIOD_YR  # 현재 세차 위상

# 반주기 오차
HALF_CYCLE_OFFSET_YR = SYSTEM_YEAR - PRECESSION_HALF_YR  # ≈ 40년

# ── 전환 마커 ──────────────────────────────────────────────────────────────────

TRANSITION_UNIT      = 40          # 전환 구간 마커 단위
# 40 등장: 홍수 강수(일), 모세 광야(년), 세차 위상 오차(년)

# ── 별자리 시대 (황도 12궁) ────────────────────────────────────────────────────

ZODIAC_AGES = [
    ("물고기자리 (Pisces)",    -2150,    0,   "현재 종료 직전"),
    ("물병자리 (Aquarius)",       0, 2150,   "현재 진입 중"),
    ("염소자리 (Capricorn)",   2150, 4300,   "미래"),
    ("궁수자리 (Sagittarius)", 4300, 6450,   "미래"),
]
# 세차 역행 기준: 물고기자리 → 물병자리 (현재 전환 중)
CURRENT_AGE     = "물고기자리 → 물병자리 전환기"
CURRENT_AGE_AD  = "약 AD 2000±150년"  # 계산법에 따라 차이


# ── 스냅샷 ────────────────────────────────────────────────────────────────────

@dataclass
class TimeSnapshot:
    """현재 시점의 세 가지 시계 동시 표시."""

    # 시계 1: 서기 달력
    ad_year: int                       # 서기 연도
    ad_corrected: int                  # 기원점 오차 보정 후

    # 시계 2: 시스템 클럭 (대홍수 기점)
    system_year: float                 # 대홍수 이후 경과년
    flood_bce: int                     # 대홍수 추정 연도 (BC)

    # 시계 3: 세차 위상
    precession_phase: float            # [0.0 ~ 1.0] 현재 세차 위상
    precession_phase_deg: float        # [0° ~ 360°]
    half_cycle_offset_yr: float        # 반주기 오차 (년)
    phase_ambiguity_window: float      # 위상 불확실 구간 (년)

    # 누적 위상차
    tropical_sidereal_diff_days: float # 경과년 × 20분 누적 (일)

    # 레이어 태그
    layer_physical: Dict[str, str] = field(default_factory=dict)
    layer_scenario: Dict[str, str] = field(default_factory=dict)
    layer_lore:     Dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.layer_physical = {
            "tropical_year":    f"{TROPICAL_YEAR_DAYS}일/년 (계절 기준)",
            "sidereal_year":    f"{SIDEREAL_YEAR_DAYS}일/년 (별 기준)",
            "annual_diff":      f"{YEAR_DIFF_MINUTES:.1f}분/년",
            "precession_period":f"{PRECESSION_PERIOD_YR:,.0f}년",
            "precession_half":  f"{PRECESSION_HALF_YR:,.0f}년",
            "cumulative_drift": f"{self.tropical_sidereal_diff_days:.0f}일 ({self.tropical_sidereal_diff_days/365.25:.1f}년)",
        }
        self.layer_scenario = {
            "flood_estimate":   f"BC {self.flood_bce:,}년 (영거 드라이아스 충격)",
            "system_clock":     f"{self.system_year:,.0f}년 경과",
            "precession_phase": f"{self.precession_phase:.4f} ({self.precession_phase_deg:.1f}°)",
            "half_cycle_gap":   f"세차 반주기 대비 +{self.half_cycle_offset_yr:.0f}년",
            "phase_window":     f"위상 불확실 구간 ±{self.phase_ambiguity_window:.0f}년",
        }
        self.layer_lore = {
            "transition_unit":  f"40 단위 (홍수 40일 / 광야 40년 / 위상 오차 40년)",
            "dante_warning":    "베아트리체: '네가 보는 시간은 착각이다'",
            "current_age":      CURRENT_AGE,
            "dante_pilgrim":    "순례자가 깨달은 것: '내 시간 감각이 뒤집혀 있었다'",
        }


# ── 시스템 클럭 ────────────────────────────────────────────────────────────────

class SystemClock:
    """세 가지 시계를 동시에 관리하는 시스템 클럭.

    인류가 쓰는 2,026년짜리 달력이
    실제 12,926년 시스템 클럭의
    어느 위치에 있는지를 보여준다.

    Parameters
    ----------
    ad_year : int
        현재 서기 연도. 기본값 2026.
    flood_bce : int
        대홍수 추정 연도 (BC). 기본값 10,900.
    """

    def __init__(
        self,
        ad_year: int = AD_CURRENT,
        flood_bce: int = FLOOD_BCE_ESTIMATE,
    ) -> None:
        self.ad_year   = ad_year
        self.flood_bce = flood_bce
        self._system_yr = float(flood_bce + ad_year)

    # ── 공개 메서드 ────────────────────────────────────────────────────────────

    def snapshot(self) -> TimeSnapshot:
        """현재 시점 TimeSnapshot 생성."""
        sys_yr = self._system_yr
        phase  = sys_yr / PRECESSION_PERIOD_YR
        phase_deg = (phase % 1.0) * 360.0
        half_offset = sys_yr - PRECESSION_HALF_YR
        drift_days = sys_yr * YEAR_DIFF_DAYS
        # 위상 불확실 구간: 세차 반주기 근처에서 최대 민감도
        ambiguity = abs(half_offset) + abs(AD_ORIGIN_ERROR_YR)

        return TimeSnapshot(
            ad_year                     = self.ad_year,
            ad_corrected                = self.ad_year + AD_ORIGIN_ERROR_YR,
            system_year                 = sys_yr,
            flood_bce                   = self.flood_bce,
            precession_phase            = phase,
            precession_phase_deg        = phase_deg,
            half_cycle_offset_yr        = half_offset,
            phase_ambiguity_window      = ambiguity,
            tropical_sidereal_diff_days = drift_days,
        )

    def print_three_clocks(self) -> None:
        """세 가지 시계 동시 출력."""
        s = self.snapshot()
        width = 70

        print("\n" + "=" * width)
        print("  ⏱  시스템 시계 — 세 가지 동시 표시")
        print("  " + "─" * (width - 4))

        print(f"\n  [시계 1] 서기 달력 (인류가 보는 시계)")
        print(f"    현재: AD {s.ad_year}년")
        print(f"    기원점 오차 보정: AD {s.ad_corrected}년 (+{AD_ORIGIN_ERROR_YR}년)")
        print(f"    비유: 화면에 표시된 시간 = {s.ad_year}분")

        print(f"\n  [시계 2] 시스템 클럭 (대홍수 기점 경과)")
        print(f"    대홍수 추정: BC {s.flood_bce:,}년")
        print(f"    경과: {s.system_year:,.0f}년")
        print(f"    비유: 컴퓨터 부팅 후 실제 경과 = {s.system_year:,.0f}분")

        bar_len = 40
        phase_pos = int(s.precession_phase * bar_len)
        half_pos  = int(0.5 * bar_len)
        bar = list("─" * bar_len)
        bar[half_pos] = "│"  # 반주기 표시
        if 0 <= phase_pos < bar_len:
            bar[phase_pos] = "◆"
        bar_str = "".join(bar)

        print(f"\n  [시계 3] 세차운동 위상 (천문 좌표)")
        print(f"    위상: {s.precession_phase:.4f}  ({s.precession_phase_deg:.1f}°)")
        print(f"    [시작]{''.join(bar_str)}[완주]")
        print(f"     0년  {'':>17}↑반주기    {PRECESSION_PERIOD_YR:,.0f}년")
        print(f"          {' '*(half_pos-1)}{PRECESSION_HALF_YR:,.0f}년")
        print(f"    현재 위치(◆): {s.system_year:,.0f}년 = 반주기 +{s.half_cycle_offset_yr:.0f}년")

        print(f"\n  [핵심 오차]")
        print(f"    세차 반주기              = {PRECESSION_HALF_YR:,.0f}년")
        print(f"    대홍수 이후 경과         = {s.system_year:,.0f}년")
        print(f"    차이                     = +{s.half_cycle_offset_yr:.0f}년")
        print(f"    → 모세 광야 40년과 동일 단위")
        print(f"    → 위상 불확실 구간 ±{s.phase_ambiguity_window:.0f}년")

        print(f"\n  [누적 천문 위상차]")
        print(f"    Tropical vs Sidereal     = {YEAR_DIFF_MINUTES:.1f}분/년")
        print(f"    {s.system_year:,.0f}년 누적          = {s.tropical_sidereal_diff_days:.0f}일")
        print(f"                             ≈ {s.tropical_sidereal_diff_days/365.25:.1f}년 위상차")

        print("=" * width)

    def print_layer_analysis(self) -> None:
        """레이어 분리 분석 출력."""
        s = self.snapshot()
        width = 70

        print("\n" + "=" * width)
        print("  📋 레이어 분리 분석")
        print("  " + "─" * (width - 4))

        print(f"\n  ① PHYSICAL_FACT (측정/계산 가능한 사실)")
        for k, v in s.layer_physical.items():
            print(f"     {k:<22} : {v}")

        print(f"\n  ② SCENARIO (가설 기반 해석)")
        for k, v in s.layer_scenario.items():
            print(f"     {k:<22} : {v}")

        print(f"\n  ③ LORE (서사적 맥락)")
        for k, v in s.layer_lore.items():
            print(f"     {k:<22} : {v}")

        print("=" * width)

    def print_transition_markers(self) -> None:
        """40 단위 전환 마커 분석."""
        print(f"\n  🔄 전환 마커 단위 = {TRANSITION_UNIT}")
        print("  " + "─" * 55)
        markers = [
            ("홍수 강수 기간",    "40일",  "에덴→홍수 후 전환"),
            ("모세 광야 유랑",    "40년",  "이집트→가나안 세대 전환"),
            ("세차 위상 오차",    "40년",  "세차 반주기→현재 위상 갭"),
            ("예수 광야 시험",    "40일",  "사역 시작 전 전환"),
            ("엘리야 호렙 여정",  "40일",  "선지자 사명 전환"),
        ]
        for name, unit, meaning in markers:
            print(f"  {name:<16} {unit:>5}  →  {meaning}")
        print(f"\n  공통 구조: [이전 상태] → [40 단위 전환 구간] → [새 상태]")
        print()

    def print_calendar_comparison(self) -> None:
        """달력 비교 표."""
        s = self.snapshot()
        print(f"\n  📅 달력 비교")
        print("  " + "─" * 60)
        print(f"  {'구분':<20} {'현재 달력':<15} {'시스템 클럭':<15} {'비율'}")
        print("  " + "─" * 60)

        rows = [
            ("경과 시간",     f"{s.ad_year}년",
             f"{s.system_year:,.0f}년",
             f"{s.ad_year/s.system_year*100:.1f}%"),
            ("세차 위상",     "미반영",
             f"{s.precession_phase_deg:.1f}°",
             "-"),
            ("기원점 보정",   "0년",
             f"+{AD_ORIGIN_ERROR_YR}년",
             "-"),
            ("천문 위상차",   "미반영",
             f"±{s.phase_ambiguity_window:.0f}년",
             "-"),
        ]
        for name, curr, sys, ratio in rows:
            print(f"  {name:<20} {curr:<15} {sys:<15} {ratio}")
        print("  " + "─" * 60)
        print(
            f"\n  결론: 인류가 보는 {s.ad_year}년은\n"
            f"        {s.system_year:,.0f}년 시스템 클럭의\n"
            f"        {s.ad_year/s.system_year*100:.1f}% 구간만 보고 있는 것"
        )


# ── 헬퍼 함수 ──────────────────────────────────────────────────────────────────

def make_system_clock(
    ad_year: int = AD_CURRENT,
    flood_bce: int = FLOOD_BCE_ESTIMATE,
) -> SystemClock:
    """SystemClock 팩토리."""
    return SystemClock(ad_year=ad_year, flood_bce=flood_bce)


def quick_time_analysis() -> SystemClock:
    """빠른 시간 분석 전체 출력."""
    clock = make_system_clock()
    clock.print_three_clocks()
    clock.print_transition_markers()
    clock.print_layer_analysis()
    clock.print_calendar_comparison()
    return clock


__all__ = [
    # 상수
    "TROPICAL_YEAR_DAYS", "SIDEREAL_YEAR_DAYS", "YEAR_DIFF_DAYS",
    "PRECESSION_PERIOD_YR", "PRECESSION_HALF_YR",
    "AD_CURRENT", "FLOOD_BCE_ESTIMATE", "SYSTEM_YEAR",
    "PRECESSION_PHASE_NOW", "HALF_CYCLE_OFFSET_YR",
    "TRANSITION_UNIT",
    # 클래스
    "TimeSnapshot", "SystemClock",
    # 팩토리
    "make_system_clock", "quick_time_analysis",
]
