"""biology_baseline.py — 생물 기준점 재설정 모듈

설계 철학:
  "현재 우리가 '정상'으로 아는 것이
   실제로는 얼마나 축소된 값인가?"

핵심 주장:
  수명 80년  → 에덴 기준의  9.6%
  키  170cm  → 에덴 기준의 55.6%
  종 다양성  → 에덴 기준의  4.2%
  돌연변이율 → 에덴 기준의 100배 (1.0x vs 0.01x)

원인:
  FirmamentDecayEngine 결과:
  FI=1.0(에덴): 수명 10x, 체형 1.8x, 돌연변이 0.01x
  FI=0.0(현재): 수명 1x,  체형 1.0x, 돌연변이 1.00x

  궁창(UV차폐+균온+고압)이 소멸하면서
  생물 파라미터가 전면 다운그레이드됨

레이어 분리:
  PHYSICAL_FACT : biology.py 계산 결과, FI 곡선 수치
  SCENARIO      : 에덴 기준값 해석, FI=1.0 상태 추정
  LORE          : 창세기 장수 기록 (아담 930년, 므두셀라 969년)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ── 에덴 기준값 (FI=1.0) ───────────────────────────────────────────────────────

EDEN_LIFESPAN_FACTOR  = 10.0    # 수명 배수 (에덴 기준)
EDEN_BODY_FACTOR      = 1.8     # 체형 배수
EDEN_MUTATION_FACTOR  = 0.01    # 돌연변이율 배수
EDEN_UV_SHIELD        = 0.950   # UV 차폐율
EDEN_PRESSURE_ATM     = 1.25    # 대기압
EDEN_GPP_POLAR        = 0.40    # 극지 GPP
EDEN_SPECIES_INDEX    = 1.000   # 종 다양성 기준 (100%)

# ── 현재 기준값 (FI=0.0) ───────────────────────────────────────────────────────

NOW_LIFESPAN_FACTOR   = 1.0
NOW_BODY_FACTOR       = 1.0
NOW_MUTATION_FACTOR   = 1.0
NOW_UV_SHIELD         = 0.0
NOW_PRESSURE_ATM      = 1.0
NOW_GPP_POLAR         = 0.10
NOW_SPECIES_INDEX     = 0.042   # extinction.py eden_index 기준

# ── 현재 관측 기준값 ──────────────────────────────────────────────────────────

OBS_LIFESPAN_YR       = 80.0    # 현대 인간 평균 수명 (년)
OBS_HEIGHT_CM         = 170.0   # 현대 인간 평균 신장 (cm)
OBS_CANCER_RATE       = 0.40    # 생애 암 발생률 (40%)
OBS_MUTATION_RATE     = 1.0     # 현재 돌연변이율 (정규화)

# ── 에덴 추정 기준값 ──────────────────────────────────────────────────────────

EDEN_LIFESPAN_YR      = OBS_LIFESPAN_YR * EDEN_LIFESPAN_FACTOR   # 800년
EDEN_HEIGHT_CM        = OBS_HEIGHT_CM   * EDEN_BODY_FACTOR        # 306cm
EDEN_CANCER_RATE      = OBS_CANCER_RATE * EDEN_MUTATION_FACTOR    # 0.4%
EDEN_MUTATION_RATE    = OBS_MUTATION_RATE * EDEN_MUTATION_FACTOR  # 0.01x

# 창세기 기록 (Lore 레이어)
GENESIS_RECORDS = {
    "아담":    930,
    "셋":      912,
    "에노스":  905,
    "게난":    910,
    "마할랄렐": 895,
    "야렛":    962,
    "에녹":    365,  # "하나님과 동행" 기록
    "므두셀라": 969,  # 최장수
    "라멕":    777,
    "노아":    950,
}
GENESIS_AVG_LIFESPAN = sum(GENESIS_RECORDS.values()) / len(GENESIS_RECORDS)
GENESIS_MAX_LIFESPAN = max(GENESIS_RECORDS.values())


# ── 스냅샷 ────────────────────────────────────────────────────────────────────

@dataclass
class BiologySnapshot:
    """특정 FI에서의 생물 파라미터 상태."""

    firmament_integrity: float    # 궁창 완전도 [0~1]

    # 계산된 값
    lifespan_factor:  float       # 수명 배수
    body_factor:      float       # 체형 배수
    mutation_factor:  float       # 돌연변이율 배수
    uv_shield:        float       # UV 차폐율

    # 현실 단위 변환
    lifespan_yr:      float       # 추정 수명 (년)
    height_cm:        float       # 추정 신장 (cm)
    cancer_rate:      float       # 암 발생률 (%)

    # 에덴 기준 비율
    lifespan_pct:     float       # 에덴 대비 수명 %
    height_pct:       float       # 에덴 대비 신장 %
    mutation_pct:     float       # 에덴 대비 돌연변이율 %

    def summary_line(self) -> str:
        return (
            f"FI={self.firmament_integrity:.2f}  "
            f"수명={self.lifespan_yr:.0f}yr({self.lifespan_pct:.1f}%)  "
            f"키={self.height_cm:.0f}cm({self.height_pct:.1f}%)  "
            f"돌연변이={self.mutation_factor:.3f}x  "
            f"UV={self.uv_shield:.3f}"
        )


# ── 생물 기준점 분석기 ────────────────────────────────────────────────────────

class BiologyBaseline:
    """생물 기준점 재설정 분석기.

    "현재 인간의 수명/신장/돌연변이율이
     에덴 기준의 몇 %인지" 보여준다.

    FirmamentDecayEngine 결과를 생물학 단위로 변환해
    사람들이 직관적으로 이해할 수 있는 수치로 제공.
    """

    def at(self, fi: float) -> BiologySnapshot:
        """특정 FI에서의 생물 파라미터 계산."""
        g = max(0.0, min(1.0, fi))

        # FirmamentDecayEngine physical 곡선과 동일 수식
        uv      = g * EDEN_UV_SHIELD
        mut     = 0.01 * math.exp((1.0 - g) * math.log(100.0))
        lifespan_f = max(1.0, EDEN_LIFESPAN_FACTOR * (g ** 1.8))
        body_f  = 1.0 + (EDEN_BODY_FACTOR - 1.0) * g

        lifespan_yr = OBS_LIFESPAN_YR * lifespan_f
        height_cm   = OBS_HEIGHT_CM   * body_f
        cancer_rate = OBS_CANCER_RATE * mut

        return BiologySnapshot(
            firmament_integrity = g,
            lifespan_factor     = round(lifespan_f, 3),
            body_factor         = round(body_f, 3),
            mutation_factor     = round(mut, 4),
            uv_shield           = round(uv, 3),
            lifespan_yr         = round(lifespan_yr, 1),
            height_cm           = round(height_cm, 1),
            cancer_rate         = round(cancer_rate * 100, 2),
            lifespan_pct        = round(lifespan_yr / EDEN_LIFESPAN_YR * 100, 2),
            height_pct          = round(height_cm   / EDEN_HEIGHT_CM   * 100, 2),
            mutation_pct        = round(mut / EDEN_MUTATION_RATE * 100, 2),
        )

    def print_baseline_comparison(self) -> None:
        """에덴 기준 vs 현재 비교 표."""
        eden = self.at(1.0)
        now  = self.at(0.0)
        width = 72

        print("\n" + "=" * width)
        print("  🧬 생물 기준점 재설정 — 에덴(FI=1.0) vs 현재(FI=0.0)")
        print("  " + "─" * (width - 4))
        print(f"  {'파라미터':<18} {'에덴 기준':>14} {'현재':>14} {'현재/에덴':>10}")
        print("  " + "─" * (width - 4))

        rows = [
            ("수명",         f"{eden.lifespan_yr:.0f}년",
             f"{now.lifespan_yr:.0f}년",
             f"{now.lifespan_yr/eden.lifespan_yr*100:.1f}%"),
            ("신장",         f"{eden.height_cm:.0f}cm",
             f"{now.height_cm:.0f}cm",
             f"{now.height_cm/eden.height_cm*100:.1f}%"),
            ("돌연변이율",   f"{eden.mutation_factor:.4f}x",
             f"{now.mutation_factor:.4f}x",
             f"{now.mutation_factor/eden.mutation_factor:.0f}배 증가"),
            ("UV 차폐",      f"{eden.uv_shield:.3f}",
             f"{now.uv_shield:.3f}",
             "0% 남음"),
            ("암 발생률",    f"{eden.cancer_rate:.2f}%",
             f"{now.cancer_rate:.2f}%",
             f"{now.cancer_rate/eden.cancer_rate:.0f}배 증가"),
            ("종 다양성",    "100%",
             f"{NOW_SPECIES_INDEX*100:.1f}%",
             f"{NOW_SPECIES_INDEX*100:.1f}% 남음"),
        ]
        for name, e_val, n_val, ratio in rows:
            print(f"  {name:<18} {e_val:>14} {n_val:>14} {ratio:>10}")

        print("  " + "─" * (width - 4))
        print(f"\n  결론: 현재 인간은 에덴 기준 생물의 다운그레이드 버전")
        print(f"    수명  {now.lifespan_yr:.0f}년 = 에덴 기준의 {now.lifespan_yr/eden.lifespan_yr*100:.1f}%")
        print(f"    신장  {now.height_cm:.0f}cm = 에덴 기준의 {now.height_cm/eden.height_cm*100:.1f}%")
        print(f"    종류  현재 생태계 = 에덴 기준의 {NOW_SPECIES_INDEX*100:.1f}%")
        print("=" * width)

    def print_fi_transition_table(self, steps: int = 10) -> None:
        """FI 전이에 따른 생물 변화 테이블."""
        width = 80
        print("\n" + "=" * width)
        print("  🧬 궁창 완전도(FI) → 생물 파라미터 전이")
        print("  " + "─" * (width - 4))
        print(
            f"  {'FI':>4}  {'수명(yr)':>8}  {'신장(cm)':>8}  "
            f"{'돌연변이':>8}  {'UV':>6}  {'암 발생률':>8}  이벤트"
        )
        print("  " + "─" * (width - 4))

        prev_snap = None
        for i in range(steps + 1):
            g = 1.0 - i / steps
            snap = self.at(g)
            event = ""
            if prev_snap:
                if prev_snap.lifespan_yr > 100 >= snap.lifespan_yr:
                    event = "← 수명 100년 이하 진입"
                elif prev_snap.lifespan_yr > 200 >= snap.lifespan_yr:
                    event = "← 수명 200년 이하"
                elif prev_snap.lifespan_yr > 500 >= snap.lifespan_yr:
                    event = "← 수명 500년 이하"
            print(
                f"  {g:>4.2f}  {snap.lifespan_yr:>8.1f}  {snap.height_cm:>8.1f}  "
                f"{snap.mutation_factor:>8.4f}  {snap.uv_shield:>6.3f}  "
                f"{snap.cancer_rate:>7.2f}%  {event}"
            )
            prev_snap = snap
        print("=" * width)

    def print_genesis_validation(self) -> None:
        """창세기 장수 기록 vs 엔진 예측값 비교 (Lore 레이어)."""
        width = 72
        print("\n" + "=" * width)
        print("  📖 창세기 장수 기록 × 엔진 예측 비교 [LORE 레이어]")
        print("  ※ 이 섹션은 서사적 맥락입니다. 물리 사실 레이어가 아님.")
        print("  " + "─" * (width - 4))
        print(f"  {'인물':<10} {'기록 수명':>8}  {'엔진 FI 추정':>12}  {'비고'}")
        print("  " + "─" * (width - 4))

        # 각 인물의 기록 수명에 해당하는 FI 역산
        for name, lifespan in GENESIS_RECORDS.items():
            # lifespan = 80 * 10 * g^1.8 → g 역산
            # g = (lifespan / 800)^(1/1.8)
            g_est = (lifespan / EDEN_LIFESPAN_YR) ** (1.0 / 1.8)
            g_est = min(1.0, max(0.0, g_est))
            note = "홍수 전" if lifespan > 500 else ("홍수 후" if lifespan < 600 else "홍수 시대")
            print(f"  {name:<10} {lifespan:>8}년  FI≈{g_est:>6.3f}      {note}")

        print(f"\n  창세기 평균 수명: {GENESIS_AVG_LIFESPAN:.0f}년")
        print(f"  창세기 최장 수명: {GENESIS_MAX_LIFESPAN}년 (므두셀라)")
        print(f"  엔진 에덴 예측:   {EDEN_LIFESPAN_YR:.0f}년 (FI=1.0)")
        print(f"  현재 평균 수명:   {OBS_LIFESPAN_YR:.0f}년  (FI=0.0)")
        print(f"\n  홍수 이후 수명 급감 패턴 = FI 급락 곡선과 구조적으로 일치")
        print("=" * width)

    def print_full_report(self) -> None:
        """전체 리포트 출력."""
        self.print_baseline_comparison()
        self.print_fi_transition_table()
        self.print_genesis_validation()


# ── 헬퍼 함수 ──────────────────────────────────────────────────────────────────

def make_biology_baseline() -> BiologyBaseline:
    """BiologyBaseline 팩토리."""
    return BiologyBaseline()


def quick_biology_report() -> BiologyBaseline:
    """빠른 생물 기준점 리포트 출력."""
    baseline = make_biology_baseline()
    baseline.print_full_report()
    return baseline


__all__ = [
    # 상수
    "EDEN_LIFESPAN_FACTOR", "EDEN_BODY_FACTOR", "EDEN_MUTATION_FACTOR",
    "EDEN_UV_SHIELD", "EDEN_PRESSURE_ATM",
    "EDEN_LIFESPAN_YR", "EDEN_HEIGHT_CM",
    "OBS_LIFESPAN_YR", "OBS_HEIGHT_CM",
    "GENESIS_RECORDS", "GENESIS_AVG_LIFESPAN",
    "TRANSITION_UNIT",
    # 클래스
    "BiologySnapshot", "BiologyBaseline",
    # 팩토리
    "make_biology_baseline", "quick_biology_report",
]

# TRANSITION_UNIT은 calendar.py에서 정의되지만
# biology_baseline.py에서도 참조 가능하도록 재정의
TRANSITION_UNIT = 40
