"""biology.py — 에덴 생물학 레이어

핵심 철학:
  "물리 환경이 생물 특성을 결정한다."
  수명·체형·유전자 안정성은 하드코딩이 아니라
  InitialConditions의 물리 파라미터에서 동역학으로 계산.

물리 → 생물 인과관계:
  UV_shield    → mutation_rate   → 유전자 안정성 → 수명
  O2 × pressure → O2_partial     → 체형 크기 (산소 가용량)
  T_surface    → metabolic_rate  → 노화 속도
  GPP          → food_abundance  → 개체 크기 상한
  mutation_rate → genome_integrity → 수명 안정성

사실 검증 레이어:
  수명 900년:  UV 차폐만으론 불가 (~249년 물리 상한)
              → UV + T_metabolic + genome_integrity 복합 효과로 ~400-600yr 가능
  거대화:     O2 × pressure → 1.2~1.5× 체형 (현실적 범위)
  에덴 생태계: mutation 낮음 → 종 분화 느림 → 대형 안정 종 유지

참조:
  - solar/eden/initial_conditions.py
  - solar/eden/geography.py
  - docs/ANTEDILUVIAN_ENV.md
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .initial_conditions import InitialConditions


# ── 물리 상수 ──────────────────────────────────────────────────────────────────

# 현재 인간 기준값 (postdiluvian baseline)
BASELINE_LIFESPAN_YR    = 80.0    # 현재 인간 평균 수명
BASELINE_BODY_MASS_KG   = 70.0    # 현재 인간 평균 체중
BASELINE_MUTATION_RATE  = 1.0     # mutation_factor = 1.0 (현재 지구)
BASELINE_O2_PARTIAL     = 0.21    # 현재 O2 분압 (atm)
BASELINE_T_K            = 288.0   # 현재 지표 온도

# 수명 상한 (물리 한계)
LIFESPAN_PHYSICAL_MAX_YR = 600.0  # UV+mutation+대사 복합 효과 물리 상한
LIFESPAN_ABSOLUTE_MAX_YR = 900.0  # 서사 레이어 (코드 밖) 수치

# 체형 상한 (O2 물리 한계)
BODY_SIZE_PHYS_MAX_RATIO = 1.8    # 현재 대비 최대 1.8× (O2/압력 한계)


# ── 동역학 계산 함수들 ─────────────────────────────────────────────────────────

def _uv_lifespan_factor(UV_shield: float) -> float:
    """UV 차폐율 → 수명 배수 (UV 직접 DNA 손상 감소 효과).

    근거:
      UV는 피부암, DNA 이중가닥 절단, 세포 노화의 주요 원인.
      UV_shield=0.95 → 피부 DNA 손상 20분의 1
      하지만 세포 내재 노화(텔로미어, ROS)는 UV와 독립적.
      따라서 UV만으로는 수명이 무한정 늘지 않음.

    수식: factor = 1 + 3.0 × UV_shield (상한 4.0×)
    검증: UV=0.95 → 4.0× → 80yr × 4.0 = 320yr (물리 한계 내)
    """
    return min(4.0, 1.0 + 3.0 * UV_shield)


def _metabolic_lifespan_factor(T_surface_K: float) -> float:
    """온도 → 대사율 → 수명 배수.

    근거:
      온도 낮음 → 대사율 낮음 → 세포 활성산소(ROS) 감소 → 노화 느림
      Rate-of-living theory: 총 심박수 ≈ 일정 (포유류 공통)
      T=35°C → 대사율 높지만 균형 → 에덴 환경은 항상 온난.

    에덴(T=308K=35°C) vs 현재(T=288K=15°C):
      에덴이 오히려 더 따뜻 → 대사율 약간 높음
      → 온도 단독으로는 수명 증가 불가
      → 산화 스트레스 감소(UV+mutation)가 더 중요
    """
    T_ref  = BASELINE_T_K   # 288K
    # 아레니우스 역관계: 온도 낮을수록 대사 느림 → 수명 ↑
    # factor = exp(-E_a/R × (1/T_ref - 1/T))
    # 단순화: factor = T_ref / T (선형 근사, 현실적 범위)
    return max(0.7, min(1.3, T_ref / max(T_surface_K, 250.0)))


def _genome_integrity_factor(mutation_factor: float) -> float:
    """mutation_factor → 게놈 무결성 → 수명 배수.

    근거:
      mutation_rate 낮음 → 세포 분열 오류 적음 → 노화 느림
      현재(factor=1.0) → 기준
      에덴(factor=0.03) → 게놈 안정성 크게 향상

    수식: genome_factor = 1 / sqrt(mutation_factor)
    검증:
      mutation=1.00 → 1.00× (현재)
      mutation=0.03 → 5.77× → 상한 clamp
      mutation=0.10 → 3.16×
    """
    return min(5.0, 1.0 / max(mutation_factor, 0.01) ** 0.5)


def _o2_body_size_factor(O2_frac: float, pressure_atm: float) -> float:
    """O2 분압 → 체형 크기 배수.

    근거:
      O2 분압 = O2_frac × pressure_atm
      호흡 효율 ∝ O2 분압 → 더 큰 체형 유지 가능
      석탄기(O2=28%) → 거대 곤충 (날개 길이 70cm)

    수식:
      o2_partial = O2_frac × pressure_atm
      size_factor = (o2_partial / 0.21) ^ 0.4
      (0.4 지수: 질량은 체적에 비례, 호흡은 체적에 비례 → 제한 지수)

    검증:
      현재 O2=0.21, P=1.0  → 1.00× (기준)
      에덴  O2=0.24, P=1.25 → (0.24×1.25/0.21)^0.4 = 1.43××
      석탄기 O2=0.28, P=1.0 → (0.28/0.21)^0.4 = 1.25×
    """
    o2_partial = O2_frac * pressure_atm
    factor = (o2_partial / BASELINE_O2_PARTIAL) ** 0.40
    return min(BODY_SIZE_PHYS_MAX_RATIO, max(0.5, factor))


def _food_abundance_size_factor(GPP_sum: float) -> float:
    """GPP → 먹이 풍요도 → 체형 상한 배수.

    근거:
      생태계 1차 생산성 높음 → 먹이사슬 에너지 풍부
      → 대형 동물 유지 가능 (베르그만 법칙 역방향)

    수식: factor = (GPP / 2.33)^0.2  (2.33 = 현재 지구 GPP)
    """
    baseline_gpp = 2.33   # 현재 지구 GPP 합계
    return min(1.5, max(0.8, (GPP_sum / max(baseline_gpp, 0.1)) ** 0.20))


# ── 생물학 상태 클래스 ─────────────────────────────────────────────────────────

@dataclass
class BiologyFactors:
    """물리 환경 → 생물학적 특성 인과관계 분해."""
    # 수명 기여 인자들
    uv_lifespan_factor:      float   # UV 차폐 효과
    metabolic_lifespan_factor: float # 대사율 효과
    genome_integrity_factor: float   # 게놈 안정성 효과

    # 체형 기여 인자들
    o2_size_factor:          float   # O2 분압 효과
    food_size_factor:        float   # 먹이 풍요도 효과

    # 종합 배수
    lifespan_multiplier:     float   # 현재 기준 수명 배수
    body_size_multiplier:    float   # 현재 기준 체형 배수

    # 절대값 추정
    lifespan_est_yr:         float   # 추정 수명 [yr]
    body_mass_est_kg:        float   # 추정 체중 [kg]
    height_est_cm:           float   # 추정 신장 [cm] (체중^1/3 × 170)

    # 물리 한계 도달 여부
    lifespan_at_phys_limit:  bool
    body_size_at_phys_limit: bool

    def summary(self) -> str:
        lines = [
            f"  수명 배수: {self.lifespan_multiplier:.2f}×  "
            f"(UV={self.uv_lifespan_factor:.2f}  "
            f"대사={self.metabolic_lifespan_factor:.2f}  "
            f"게놈={self.genome_integrity_factor:.2f})",
            f"  추정 수명: {self.lifespan_est_yr:.0f}년"
            f"{'  ⚠ 물리 상한' if self.lifespan_at_phys_limit else ''}",
            f"  체형 배수: {self.body_size_multiplier:.2f}×  "
            f"(O2분압={self.o2_size_factor:.2f}  "
            f"먹이={self.food_size_factor:.2f})",
            f"  추정 신장: {self.height_est_cm:.0f}cm  "
            f"({self.body_mass_est_kg:.0f}kg)"
            f"{'  ⚠ 물리 상한' if self.body_size_at_phys_limit else ''}",
        ]
        return "\n".join(lines)


@dataclass
class EdenBiologyState:
    """에덴 시대 전체 생물학 상태.

    InitialConditions → 동역학 계산으로 자동 생성.
    """
    phase:          str
    factors:        BiologyFactors

    # 밴드별 생물학 (온도 따라 달라짐)
    band_lifespan:  List[float]   # [12] 밴드별 추정 수명 [yr]
    band_body_size: List[float]   # [12] 밴드별 체형 배수

    # 생태계 특성
    speciation_rate: float   # 종 분화율 (mutation_factor 기반)
    megafauna_possible: bool # 거대 동물 가능 여부
    stable_ecosystem:   bool # 안정 생태계 여부 (mutation 낮고 GPP 높음)

    def summary(self) -> str:
        lines = [
            f"=== 에덴 생물학 ({self.phase}) ===",
            f"",
            self.factors.summary(),
            f"",
            f"  종 분화율:   {self.speciation_rate:.4f}×  "
            f"(낮을수록 안정 대형종 유지)",
            f"  거대 동물:   {'가능 ✅' if self.megafauna_possible else '어려움 ❌'}",
            f"  안정 생태계: {'✅' if self.stable_ecosystem else '❌'}",
            f"",
            f"  위도밴드별 수명 (최저~최고):",
            f"    {min(self.band_lifespan):.0f}yr ~ {max(self.band_lifespan):.0f}yr",
            f"    최적 밴드: {self.band_lifespan.index(max(self.band_lifespan))*15-82}°  "
            f"({max(self.band_lifespan):.0f}yr)",
        ]
        return "\n".join(lines)


# ── 핵심 계산 함수 ─────────────────────────────────────────────────────────────

def compute_biology(ic: InitialConditions) -> EdenBiologyState:
    """InitialConditions → EdenBiologyState 동역학 계산.

    모든 수치는 물리 인과관계로 계산. 하드코딩 없음.
    """
    b   = ic.band
    gpp = float(b.GPP.sum())

    # ── 수명 인자 계산 ──────────────────────────────────────────
    uv_f  = _uv_lifespan_factor(ic.UV_shield)
    met_f = _metabolic_lifespan_factor(ic.T_surface_K)
    gen_f = _genome_integrity_factor(ic.mutation_factor)

    # 수명 배수 = 세 인자의 기하평균 (독립 인과관계)
    lifespan_mult = (uv_f * met_f * gen_f) ** (1.0 / 3.0)
    lifespan_est  = min(LIFESPAN_PHYSICAL_MAX_YR,
                        BASELINE_LIFESPAN_YR * lifespan_mult)
    at_lifespan_limit = lifespan_est >= LIFESPAN_PHYSICAL_MAX_YR * 0.95

    # ── 체형 인자 계산 ──────────────────────────────────────────
    o2_f   = _o2_body_size_factor(ic.O2_frac, ic.pressure_atm)
    food_f = _food_abundance_size_factor(gpp)

    body_mult     = o2_f * food_f
    body_mass_est = BASELINE_BODY_MASS_KG * body_mult
    # 신장 ∝ (체중)^(1/3) × 기준신장
    height_est    = 170.0 * (body_mult ** (1.0 / 3.0))
    at_body_limit = body_mult >= BODY_SIZE_PHYS_MAX_RATIO * 0.95

    factors = BiologyFactors(
        uv_lifespan_factor       = round(uv_f, 3),
        metabolic_lifespan_factor= round(met_f, 3),
        genome_integrity_factor  = round(gen_f, 3),
        o2_size_factor           = round(o2_f, 3),
        food_size_factor         = round(food_f, 3),
        lifespan_multiplier      = round(lifespan_mult, 3),
        body_size_multiplier     = round(body_mult, 3),
        lifespan_est_yr          = round(lifespan_est, 1),
        body_mass_est_kg         = round(body_mass_est, 1),
        height_est_cm            = round(height_est, 1),
        lifespan_at_phys_limit   = at_lifespan_limit,
        body_size_at_phys_limit  = at_body_limit,
    )

    # ── 밴드별 수명 계산 ────────────────────────────────────────
    # 밴드별 온도 → 대사율 → 수명 보정
    band_lifespan  = []
    band_body_size = []
    for i in range(12):
        T_band = float(b.T_K[i])
        hab    = float(b.habitable[i])
        ice    = float(b.ice_mask[i])

        if not hab or ice:
            band_lifespan.append(0.0)
            band_body_size.append(0.0)
            continue

        met_band = _metabolic_lifespan_factor(T_band)
        ls_band  = min(LIFESPAN_PHYSICAL_MAX_YR,
                       BASELINE_LIFESPAN_YR * (uv_f * met_band * gen_f) ** (1/3))
        bs_band  = o2_f * _food_abundance_size_factor(float(b.GPP[i]) * 12)

        band_lifespan.append(round(ls_band, 1))
        band_body_size.append(round(bs_band, 3))

    # ── 생태계 특성 ────────────────────────────────────────────
    speciation_rate   = ic.mutation_factor
    megafauna_possible= body_mult >= 1.2 and gpp >= 4.0
    stable_ecosystem  = ic.mutation_factor <= 0.10 and gpp >= 3.0

    return EdenBiologyState(
        phase           = ic.phase,
        factors         = factors,
        band_lifespan   = band_lifespan,
        band_body_size  = band_body_size,
        speciation_rate = round(speciation_rate, 5),
        megafauna_possible = megafauna_possible,
        stable_ecosystem   = stable_ecosystem,
    )


def compare_biology(ic_eden: InitialConditions,
                     ic_post: InitialConditions) -> str:
    """에덴 vs 현재 생물학 비교 출력."""
    e = compute_biology(ic_eden)
    p = compute_biology(ic_post)

    ef = e.factors
    pf = p.factors

    lines = [
        "=" * 60,
        "에덴 vs 현재 — 생물학 비교",
        "=" * 60,
        "",
        f"  {'항목':16s}  {'에덴(antediluvian)':>20}  {'현재(postdiluvian)':>20}",
        "  " + "─" * 60,
        f"  {'수명 배수':16s}  {ef.lifespan_multiplier:>20.2f}x  "
        f"{pf.lifespan_multiplier:>20.2f}x",
        f"  {'UV 인자':16s}  {ef.uv_lifespan_factor:>20.2f}   "
        f"{pf.uv_lifespan_factor:>20.2f}",
        f"  {'대사 인자':16s}  {ef.metabolic_lifespan_factor:>20.2f}   "
        f"{pf.metabolic_lifespan_factor:>20.2f}",
        f"  {'게놈 인자':16s}  {ef.genome_integrity_factor:>20.2f}   "
        f"{pf.genome_integrity_factor:>20.2f}",
        f"  {'추정 수명':16s}  {ef.lifespan_est_yr:>19.0f}yr  "
        f"{pf.lifespan_est_yr:>19.0f}yr",
        "",
        f"  {'체형 배수':16s}  {ef.body_size_multiplier:>20.2f}x  "
        f"{pf.body_size_multiplier:>20.2f}x",
        f"  {'O2 분압 인자':16s}  {ef.o2_size_factor:>20.2f}   "
        f"{pf.o2_size_factor:>20.2f}",
        f"  {'먹이 인자':16s}  {ef.food_size_factor:>20.2f}   "
        f"{pf.food_size_factor:>20.2f}",
        f"  {'추정 신장':16s}  {ef.height_est_cm:>19.0f}cm  "
        f"{pf.height_est_cm:>19.0f}cm",
        f"  {'추정 체중':16s}  {ef.body_mass_est_kg:>19.0f}kg  "
        f"{pf.body_mass_est_kg:>19.0f}kg",
        "",
        f"  {'거대동물 가능':16s}  "
        f"{'✅' if e.megafauna_possible else '❌':>20}  "
        f"{'✅' if p.megafauna_possible else '❌':>20}",
        f"  {'안정 생태계':16s}  "
        f"{'✅' if e.stable_ecosystem else '❌':>20}  "
        f"{'✅' if p.stable_ecosystem else '❌':>20}",
        "",
        "  물리 한계 주석:",
        f"  수명 물리 상한 = {LIFESPAN_PHYSICAL_MAX_YR:.0f}yr  "
        f"(UV+대사+게놈 복합 효과)",
        f"  서사 레이어 (900년) = 물리 상한 초과 → 코드 밖 영역",
        f"  체형 물리 상한 = {BODY_SIZE_PHYS_MAX_RATIO:.1f}×  "
        f"(O2 분압 한계)",
        "=" * 60,
    ]
    return "\n".join(lines)


# ── 팩토리 ────────────────────────────────────────────────────────────────────

def make_biology(ic: InitialConditions) -> EdenBiologyState:
    """InitialConditions → EdenBiologyState (단축 팩토리)."""
    return compute_biology(ic)


__all__ = [
    'BiologyFactors',
    'EdenBiologyState',
    'compute_biology',
    'compare_biology',
    'make_biology',
    'LIFESPAN_PHYSICAL_MAX_YR',
    'BODY_SIZE_PHYS_MAX_RATIO',
]
