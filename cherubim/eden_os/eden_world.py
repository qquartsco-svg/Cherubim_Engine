"""eden_os.eden_world — EdenWorld 환경 스냅샷  (Step 1 / 7)

"궁창시대 지구 OS의 부팅 상태를 확정한다."

역할
────
  EdenSearchEngine 이 찾아낸 최적 후보(EdenCandidate) 혹은
  make_antediluvian() 프리셋을 받아,
  EdenOS 전체가 공유하는 **불변 환경 스냅샷(EdenWorldEnv)** 을 만든다.

  이 객체 하나가 진실의 근원(Single Source of Truth)이다.
    - rivers.py, tree_of_life.py, cherubim_guard.py, adam.py 등
      모든 하위 모듈은 EdenWorldEnv 를 읽기 전용으로 참조만 한다.
    - 직접 수정 불가 (frozen dataclass).

레이어 분리
──────────────────────────────────────────────
  PHYSICAL_FACT : 계산·측정 가능한 수치    (얼음 밴드 수, 온도 등)
  SCENARIO      : 파라미터 기반 해석       (에덴 지수, 거주 밴드 등)
  LORE          : 서사 맥락               (시대 이름, 위상 레이블 등)

합격 조건 (validate() 가 검사)
──────────────────────────────────────────────
  ice_bands        == 0      (전 지구 빙하 없음)
  hab_bands        >= 10     (거주 가능 밴드 ≥10)
  mutation_factor  <= 0.10   (돌연변이 억제 확인)
  precip_mode      == 'mist' (안개 강수 = 궁창 활성)

빠른 시작
──────────────────────────────────────────────
  from cherubim.eden_os import EdenWorldEnv, make_eden_world
  world = make_eden_world()
  world.print_summary()
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ── 물리 엔진에서 읽기 전용으로 가져오기 ────────────────────────────────────
from cherubim.initial_conditions import InitialConditions, EarthBandState, make_antediluvian

# ── 레이어 상수 ──────────────────────────────────────────────────────────────
PHYSICAL = "PHYSICAL_FACT"
SCENARIO  = "SCENARIO"
LORE      = "LORE"

# 12밴드 위도 중심값 (남극 → 북극)
_BAND_LATS: Tuple[float, ...] = tuple(-82.5 + i * 15.0 for i in range(12))

# 합격 기준
_PASS_ICE_BANDS       = 0
_PASS_HAB_BANDS_MIN   = 10
_PASS_MUTATION_MAX    = 0.10
_PASS_PRECIP_MODE     = "mist"


# ═══════════════════════════════════════════════════════════════════════════════
#  BandInfo — 12밴드 한 줄 요약
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class BandInfo:
    """12밴드 중 하나의 요약 정보."""
    index:     int          # 0(남극) ~ 11(북극)
    lat_deg:   float        # 위도 중심값 [°]
    T_C:       float        # 온도 [°C]
    GPP:       float        # 1차 생산성 지수 [0~1]
    soil_W:    float        # 토양 수분 [0~1]
    ice:       bool         # 빙하 존재 여부
    habitable: bool         # 거주 가능 여부

    @property
    def is_polar(self) -> bool:
        return abs(self.lat_deg) >= 67.5

    def __str__(self) -> str:
        pole  = " ← 극지" if self.is_polar else ""
        ice   = "🧊" if self.ice else "🌿"
        hab   = "✅" if self.habitable else "❌"
        return (
            f"band[{self.index:02d}] lat={self.lat_deg:+6.1f}°  "
            f"{self.T_C:5.1f}°C  GPP={self.GPP:.3f}  {hab}{ice}{pole}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  EdenWorldEnv — 전체 EdenOS 가 공유하는 불변 환경 스냅샷
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class EdenWorldEnv:
    """궁창시대 지구 환경 스냅샷 (읽기 전용).

    EdenOS 의 모든 하위 모듈이 참조하는 Single Source of Truth.

    Attributes
    ----------
    ic : InitialConditions
        기반 물리 파라미터 (T, CO2, UV_shield, pressure 등).
    bands : tuple[BandInfo, ...]
        12밴드 요약 (남극=0, 북극=11).
    eden_index : float
        전체 에덴 지수 [0~1].  1.0 = 완전한 에덴.
    valid : bool
        합격 기준 4개를 모두 통과했는가.
    fail_reasons : tuple[str, ...]
        불합격 사유 목록 (valid=True 이면 비어있음).
    layer : dict
        레이어별 주요 수치 {PHYSICAL_FACT, SCENARIO, LORE}.
    """

    ic:           InitialConditions
    bands:        Tuple[BandInfo, ...]
    eden_index:   float
    valid:        bool
    fail_reasons: Tuple[str, ...]
    layer:        Dict[str, Dict]

    # ── 편의 프로퍼티 ─────────────────────────────────────────────────────────

    @property
    def T_surface_C(self) -> float:
        return self.ic.T_surface_K - 273.15

    @property
    def pole_T_C(self) -> float:
        """극지 (band[0] 기준) 온도."""
        return self.bands[0].T_C

    @property
    def equator_T_C(self) -> float:
        """적도 (band[5]/band[6] 평균) 온도."""
        return (self.bands[5].T_C + self.bands[6].T_C) / 2.0

    @property
    def ice_bands(self) -> int:
        return sum(1 for b in self.bands if b.ice)

    @property
    def hab_bands(self) -> int:
        return sum(1 for b in self.bands if b.habitable)

    @property
    def polar_bands(self) -> List[BandInfo]:
        return [b for b in self.bands if b.is_polar]

    # ── 출력 ──────────────────────────────────────────────────────────────────

    def print_summary(self) -> None:
        width = 70
        print("=" * width)
        print("  🌍 EdenWorldEnv — 궁창시대 지구 OS 환경 스냅샷")
        print("=" * width)

        # ① PHYSICAL_FACT
        pf = self.layer[PHYSICAL]
        print(f"\n  [{PHYSICAL}]")
        print(f"    지표 평균 온도   : {pf['T_surface_C']:.1f}°C")
        print(f"    극지 온도        : {pf['pole_T_C']:.1f}°C  (빙점 이상: {'✅' if pf['pole_T_C'] > 0 else '❌'})")
        print(f"    적도 온도        : {pf['equator_T_C']:.1f}°C")
        print(f"    극-적도 온도차   : {pf['pole_eq_delta_K']:.0f} K")
        print(f"    기압             : {pf['pressure_atm']:.2f} atm")
        print(f"    UV 차폐          : {pf['UV_shield']*100:.0f}%")
        print(f"    강수 모드        : {pf['precip_mode']}")
        print(f"    돌연변이 팩터    : {pf['mutation_factor']:.4f}x")
        print(f"    얼음 밴드 수     : {pf['ice_bands']}")
        print(f"    거주가능 밴드    : {pf['hab_bands']} / 12")

        # ② SCENARIO
        sc = self.layer[SCENARIO]
        print(f"\n  [{SCENARIO}]")
        print(f"    에덴 지수        : {sc['eden_index']:.4f}  (1.0 = 완전한 에덴)")
        print(f"    극지 에덴 상태   : {sc['polar_eden_status']}")
        print(f"    수명 팩터        : {sc['lifespan_factor']:.1f}x  → ~{sc['est_lifespan_yr']:.0f}년")
        print(f"    종 다양성        : {sc['biodiversity_pct']:.1f}%  (에덴 기준)")
        print(f"    합격             : {'✅ PASS' if self.valid else '❌ FAIL'}")
        if self.fail_reasons:
            for r in self.fail_reasons:
                print(f"      ✗ {r}")

        # ③ LORE
        lo = self.layer[LORE]
        print(f"\n  [{LORE}]")
        print(f"    시대 이름        : {lo['era_name']}")
        print(f"    남극 좌표 상태   : {lo['south_pole_status']}")
        print(f"    좌표계           : {lo['coord_system']}")
        print(f"    세차운동 상태    : {lo['precession_state']}")

        # ④ 12밴드 테이블
        print(f"\n  {'─'*66}")
        print(f"  {'12밴드 온도 분포 (남극→북극)':^66}")
        print(f"  {'─'*66}")
        for b in self.bands:
            print(f"    {b}")

        print("=" * width)

    def print_pass_fail(self) -> None:
        """합격/불합격 상태만 간결하게 출력."""
        status = "✅ PASS" if self.valid else "❌ FAIL"
        print(f"\n  EdenWorldEnv 합격 검사: {status}")
        checks = [
            (f"ice_bands == 0            ({self.ice_bands})",   self.ice_bands == 0),
            (f"hab_bands >= 10           ({self.hab_bands})",   self.hab_bands >= _PASS_HAB_BANDS_MIN),
            (f"mutation_factor <= 0.10   ({self.ic.mutation_factor:.4f})",
             self.ic.mutation_factor <= _PASS_MUTATION_MAX),
            (f"precip_mode == 'mist'     ({self.ic.precip_mode})",
             self.ic.precip_mode == _PASS_PRECIP_MODE),
        ]
        for label, ok in checks:
            mark = "✅" if ok else "❌"
            print(f"    {mark}  {label}")


# ═══════════════════════════════════════════════════════════════════════════════
#  내부 계산 헬퍼
# ═══════════════════════════════════════════════════════════════════════════════

def _build_bands(ic: InitialConditions) -> Tuple[BandInfo, ...]:
    band: EarthBandState = ic.band
    result = []
    for i, lat in enumerate(_BAND_LATS):
        result.append(BandInfo(
            index     = i,
            lat_deg   = lat,
            T_C       = float(band.T_K[i]) - 273.15,
            GPP       = float(band.GPP[i]),
            soil_W    = float(band.soil_W[i]),
            ice       = bool(band.ice_mask[i]),
            habitable = bool(band.habitable[i]),
        ))
    return tuple(result)


def _compute_eden_index(ic: InitialConditions, bands: Tuple[BandInfo, ...]) -> float:
    """간단한 에덴 지수 계산 [0~1].

    UV 차폐(40%), 극지 온도 적합성(20%), 돌연변이 억제(20%), 거주 밴드 비율(20%)
    """
    uv_score     = ic.UV_shield                                    # 0~1
    polar_score  = min(1.0, max(0.0, (bands[0].T_C + 10) / 50))   # 0°C → 0.2, 40°C → 1.0
    mut_score    = max(0.0, 1.0 - ic.mutation_factor)              # 낮을수록 좋음
    hab_score    = sum(1 for b in bands if b.habitable) / 12.0

    return round(
        0.40 * uv_score +
        0.20 * polar_score +
        0.20 * mut_score +
        0.20 * hab_score,
        4
    )


def _validate(ic: InitialConditions, bands: Tuple[BandInfo, ...]) -> Tuple[bool, Tuple[str, ...]]:
    reasons = []
    ice_cnt = sum(1 for b in bands if b.ice)
    hab_cnt = sum(1 for b in bands if b.habitable)

    if ice_cnt != _PASS_ICE_BANDS:
        reasons.append(f"ice_bands={ice_cnt}  (기준: ==0)")
    if hab_cnt < _PASS_HAB_BANDS_MIN:
        reasons.append(f"hab_bands={hab_cnt}  (기준: >=10)")
    if ic.mutation_factor > _PASS_MUTATION_MAX:
        reasons.append(f"mutation_factor={ic.mutation_factor:.4f}  (기준: <=0.10)")
    if ic.precip_mode != _PASS_PRECIP_MODE:
        reasons.append(f"precip_mode='{ic.precip_mode}'  (기준: 'mist')")

    return (len(reasons) == 0), tuple(reasons)


def _build_layer(ic: InitialConditions, bands: Tuple[BandInfo, ...],
                 eden_index: float) -> Dict[str, Dict]:
    pole_T   = bands[0].T_C
    eq_T     = (bands[5].T_C + bands[6].T_C) / 2.0
    lifespan = max(1.0, 10.0 * (ic.UV_shield ** 1.5) * (1.0 - ic.mutation_factor))
    biodiv   = (1.0 - ic.mutation_factor) * ic.UV_shield * 100.0

    return {
        PHYSICAL: {
            "T_surface_C":    round(ic.T_surface_K - 273.15, 2),
            "pole_T_C":       round(pole_T, 2),
            "equator_T_C":    round(eq_T, 2),
            "pole_eq_delta_K": ic.pole_eq_delta_K,
            "pressure_atm":   ic.pressure_atm,
            "UV_shield":      ic.UV_shield,
            "precip_mode":    ic.precip_mode,
            "mutation_factor": round(ic.mutation_factor, 6),
            "ice_bands":      sum(1 for b in bands if b.ice),
            "hab_bands":      sum(1 for b in bands if b.habitable),
            "CO2_ppm":        ic.CO2_ppm,
            "H2O_atm_frac":   ic.H2O_atm_frac,
        },
        SCENARIO: {
            "eden_index":         eden_index,
            "polar_eden_status":  "최적 거주지 (빙하 없음)" if not bands[0].ice else "빙하 존재",
            "lifespan_factor":    round(lifespan, 2),
            "est_lifespan_yr":    round(lifespan * 80.0, 0),
            "biodiversity_pct":   round(biodiv, 1),
        },
        LORE: {
            "era_name":        "궁창시대 (Antediluvian Era)",
            "south_pole_status": "빙하 없는 아열대 — 에덴 1순위 좌표",
            "coord_system":    "에덴 기준: 남=위 (자기 N극 발원지)",
            "precession_state": "세차 반주기 기점 ±40년 (전환 마커)",
        },
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  공개 팩토리
# ═══════════════════════════════════════════════════════════════════════════════

def make_eden_world(ic: Optional[InitialConditions] = None) -> EdenWorldEnv:
    """EdenWorldEnv 생성.

    Parameters
    ----------
    ic : InitialConditions, optional
        None 이면 make_antediluvian() 프리셋을 사용.

    Returns
    -------
    EdenWorldEnv
        불변 환경 스냅샷.  valid=True 이면 EdenOS 실행 가능.

    Examples
    --------
    >>> world = make_eden_world()
    >>> world.print_summary()
    >>> assert world.valid, world.fail_reasons
    """
    if ic is None:
        ic = make_antediluvian()

    bands      = _build_bands(ic)
    eden_index = _compute_eden_index(ic, bands)
    valid, reasons = _validate(ic, bands)
    layer      = _build_layer(ic, bands, eden_index)

    return EdenWorldEnv(
        ic           = ic,
        bands        = bands,
        eden_index   = eden_index,
        valid        = valid,
        fail_reasons = reasons,
        layer        = layer,
    )
