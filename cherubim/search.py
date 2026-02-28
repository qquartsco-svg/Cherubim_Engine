"""search.py — 에덴 탐색 엔진 (독립 모듈)

핵심 철학:
  "에덴은 특정 좌표가 아니라 특정 파라미터 상태(state basin)이다."

탐색 방식:
  1. 파라미터 공간 정의 (CO2, H2O, albedo, f_land, UV, mag ...)
  2. 각 조합을 InitialConditions → PlanetRunner → 안정 판정
  3. Eden 판정 기준 통과한 조합을 EdenCandidate로 수집
  4. 결과를 위도밴드 × 환경 파라미터 맵으로 출력

확장 가능:
  - 다른 행성 파라미터 (항성 광도, 공전 반지름, 행성 질량)
  - 시대별 스캔 (홍수 전 / 중 / 후)
  - 우선순위 스코어로 랭킹

참조:
  - solar/eden/initial_conditions.py
  - solar/eden/geography.py
  - solar/day7/runner.py
  - solar/day7/sabbath.py
"""

from __future__ import annotations

import itertools
import json
import math
import os
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterator, List, Optional, Tuple, Any

from .initial_conditions import InitialConditions, make_antediluvian, make_postdiluvian
from .geography import (
    EdenGeography,
    make_eden_geography,
    magnetic_protection_factor,
)

# ── 위도 밴드 중심 ─────────────────────────────────────────────────────────────
_BAND_LATS = [-82.5, -67.5, -52.5, -37.5, -22.5, -7.5,
                7.5,  22.5,  37.5,  52.5,  67.5,  82.5]


# ── 에덴 판정 기준 ─────────────────────────────────────────────────────────────

@dataclass
class EdenCriteria:
    """에덴 상태 판정 기준 (모두 만족해야 PASS).

    물리적 근거:
      T_min~T_max   : 액상물 존재 + 단백질 변성 방지
      GPP_min       : 1차 생산성 — 먹이사슬 기반
      stress_max    : 환경 스트레스 낮음 = 안정 생태계
      ice_bands_max : 빙하 밴드 수 — 에덴=0
      mutation_max  : 변이율 낮음 — 유전자 안정
      hab_bands_min : 거주 가능 밴드 수
    """
    T_min_C:        float = 15.0   # 최저 지표온도 [°C]
    T_max_C:        float = 45.0   # 최고 지표온도 [°C]
    GPP_min:        float = 3.0    # 전 지구 GPP 합계 [kg C/m²/yr]
    stress_max:     float = 0.05   # 최대 행성 스트레스 [0~1]
    ice_bands_max:  int   = 0      # 최대 빙하 밴드 수
    mutation_max:   float = 0.10   # 최대 mutation_factor
    hab_bands_min:  int   = 10     # 최소 거주 가능 밴드 수

    def check(self, ic: InitialConditions) -> Tuple[bool, Dict[str, bool]]:
        """InitialConditions에 대해 각 기준 통과 여부 반환."""
        T_C = ic.T_surface_K - 273.15
        b   = ic.band
        detail = {
            'T_range':    self.T_min_C <= T_C <= self.T_max_C,
            'GPP':        float(b.GPP.sum()) >= self.GPP_min,
            'ice_bands':  int(b.ice_mask.sum()) <= self.ice_bands_max,
            'mutation':   ic.mutation_factor <= self.mutation_max,
            'hab_bands':  int(b.habitable.sum()) >= self.hab_bands_min,
        }
        passed = all(detail.values())
        return passed, detail


# ── 에덴 후보 ─────────────────────────────────────────────────────────────────

@dataclass
class EdenCandidate:
    """에덴 판정을 통과한 파라미터 조합."""
    ic:             InitialConditions
    score:          float             # 종합 에덴 점수 [0~1] (높을수록 좋음)
    criteria_detail: Dict[str, bool]  # 각 기준별 통과 여부
    rank:           int   = 0         # 전체 후보 중 순위

    # 밴드별 상세
    band_eden_score: List[float] = field(default_factory=list)  # [12]

    def summary(self) -> str:
        T_C = self.ic.T_surface_K - 273.15
        b   = self.ic.band
        lines = [
            f"  phase={self.ic.phase}  score={self.score:.3f}  rank=#{self.rank}",
            f"  T={T_C:.1f}°C  CO2={self.ic.CO2_ppm:.0f}ppm  "
            f"H2O={self.ic.H2O_atm_frac*100:.1f}%  O2={self.ic.O2_frac*100:.1f}%",
            f"  albedo={self.ic.albedo:.3f}  f_land={self.ic.f_land:.2f}  "
            f"UV={self.ic.UV_shield:.2f}  mut={self.ic.mutation_factor:.3f}x",
            f"  GPP={b.GPP.sum():.2f}  빙하={b.ice_mask.sum()}/12  "
            f"거주={b.habitable.sum()}/12",
            f"  기준: " + "  ".join(
                f"{'✅' if v else '❌'}{k}" for k, v in self.criteria_detail.items()
            ),
        ]
        return "\n".join(lines)


# ── 파라미터 공간 ─────────────────────────────────────────────────────────────

@dataclass
class SearchSpace:
    """탐색할 파라미터 공간 정의.

    각 파라미터는 (min, max, steps) 형태.
    steps=1이면 고정값(min).
    """
    CO2_range:         Tuple[float, float, int] = (200.0, 400.0, 5)
    H2O_atm_range:     Tuple[float, float, int] = (0.01,  0.08,  4)
    H2O_canopy_range:  Tuple[float, float, int] = (0.00,  0.06,  3)
    O2_range:          Tuple[float, float, int] = (0.19,  0.25,  3)
    albedo_range:      Tuple[float, float, int] = (0.15,  0.35,  4)
    f_land_range:      Tuple[float, float, int] = (0.25,  0.45,  4)
    UV_shield_range:   Tuple[float, float, int] = (0.00,  0.95,  4)
    CH4_fixed:         float                    = 0.5     # 고정
    pressure_fixed:    float                    = 1.0     # 고정
    precip_mode:       str                      = 'mist'  # 고정

    def _linspace(self, lo: float, hi: float, n: int) -> List[float]:
        if n == 1:
            return [lo]
        return [lo + (hi - lo) * i / (n - 1) for i in range(n)]

    def grid(self) -> Iterator[Dict]:
        """파라미터 그리드 이터레이터."""
        CO2_vals    = self._linspace(*self.CO2_range)
        H2O_vals    = self._linspace(*self.H2O_atm_range)
        canopy_vals = self._linspace(*self.H2O_canopy_range)
        O2_vals     = self._linspace(*self.O2_range)
        alb_vals    = self._linspace(*self.albedo_range)
        fl_vals     = self._linspace(*self.f_land_range)
        uv_vals     = self._linspace(*self.UV_shield_range)

        for co2, h2o, cnp, o2, alb, fl, uv in itertools.product(
            CO2_vals, H2O_vals, canopy_vals, O2_vals, alb_vals, fl_vals, uv_vals
        ):
            # 캐노피는 대기 H2O 내에서만 유효
            if cnp > h2o:
                continue
            yield {
                'CO2_ppm':      co2,
                'H2O_atm_frac': h2o,
                'H2O_canopy':   cnp,
                'O2_frac':      o2,
                'CH4_ppm':      self.CH4_fixed,
                'albedo':       alb,
                'f_land':       fl,
                'UV_shield':    uv,
                'pressure_atm': self.pressure_fixed,
                'precip_mode':  self.precip_mode,
            }

    def total_combinations(self) -> int:
        n = (self.CO2_range[2] * self.H2O_atm_range[2] *
             self.H2O_canopy_range[2] * self.O2_range[2] *
             self.albedo_range[2] * self.f_land_range[2] *
             self.UV_shield_range[2])
        return n


def make_antediluvian_space() -> SearchSpace:
    """에덴 시대 탐색 공간 (궁창 존재)."""
    return SearchSpace(
        CO2_range        = (200.0, 300.0, 4),
        H2O_atm_range    = (0.03,  0.08,  3),
        H2O_canopy_range = (0.02,  0.06,  3),
        O2_range         = (0.21,  0.24,  2),
        albedo_range     = (0.15,  0.25,  3),
        f_land_range     = (0.35,  0.45,  3),
        UV_shield_range  = (0.80,  0.98,  3),
        CH4_fixed        = 0.5,
        pressure_fixed   = 1.25,
        precip_mode      = 'mist',
    )


def make_postdiluvian_space() -> SearchSpace:
    """대홍수 이후 탐색 공간 (현재 지구 근방)."""
    return SearchSpace(
        CO2_range        = (280.0, 450.0, 4),
        H2O_atm_range    = (0.01,  0.02,  2),
        H2O_canopy_range = (0.00,  0.00,  1),
        O2_range         = (0.20,  0.22,  2),
        albedo_range     = (0.25,  0.40,  3),
        f_land_range     = (0.25,  0.35,  3),
        UV_shield_range  = (0.00,  0.00,  1),
        CH4_fixed        = 0.7,
        pressure_fixed   = 1.0,
        precip_mode      = 'rain',
    )


def make_exoplanet_space(
    stellar_flux_scale: float = 1.0,
    CO2_range: Tuple = (100.0, 1000.0, 6),
) -> SearchSpace:
    """외계 행성 탐색 공간 — 항성 에너지 스케일 조정 가능."""
    return SearchSpace(
        CO2_range        = CO2_range,
        H2O_atm_range    = (0.005, 0.10, 5),
        H2O_canopy_range = (0.00,  0.05, 3),
        O2_range         = (0.10,  0.30, 4),
        albedo_range     = (0.10,  0.50, 5),
        f_land_range     = (0.20,  0.60, 4),
        UV_shield_range  = (0.00,  0.95, 4),
        CH4_fixed        = 1.0,
        pressure_fixed   = stellar_flux_scale,
        precip_mode      = 'rain',
    )


# ── 스코어 계산 ───────────────────────────────────────────────────────────────

def compute_eden_score(ic: InitialConditions,
                        criteria: EdenCriteria,
                        geo: Optional[EdenGeography] = None) -> float:
    """에덴 종합 점수 계산 [0~1].

    가중 합산:
      GPP 생산성    30%
      온도 최적성   25%
      mutation 낮음 20%
      거주 밴드 수  15%
      빙하 없음     10%
    """
    T_C = ic.T_surface_K - 273.15
    b   = ic.band

    # GPP 점수: 목표 6.0 kg C/m²/yr 기준 정규화
    gpp_score = min(1.0, float(b.GPP.sum()) / 6.0)

    # 온도 점수: 25°C 최적, 양쪽으로 감쇄
    T_OPT = 28.0
    T_SIG = 10.0
    t_score = math.exp(-0.5 * ((T_C - T_OPT) / T_SIG) ** 2)

    # mutation 점수: 낮을수록 좋음
    mut_score = max(0.0, 1.0 - ic.mutation_factor)

    # 거주 밴드 점수
    hab_score = int(b.habitable.sum()) / 12.0

    # 빙하 없음 점수
    ice_score = 1.0 - int(b.ice_mask.sum()) / 12.0

    # 자기장 보호 가중 (geo 있으면 적용)
    mag_bonus = 0.0
    if geo is not None:
        prot = geo.band_protection()
        mag_bonus = sum(prot) / len(prot) * 0.1   # 최대 10% 보너스

    score = (
        gpp_score  * 0.30 +
        t_score    * 0.25 +
        mut_score  * 0.20 +
        hab_score  * 0.15 +
        ice_score  * 0.10 +
        mag_bonus
    )
    return min(1.0, score)


def compute_band_eden_scores(ic: InitialConditions,
                               geo: Optional[EdenGeography] = None) -> List[float]:
    """위도밴드별 에덴 점수 [12].

    각 밴드: 온도 + 토양수분 + 자기 보호 + GPP
    """
    b     = ic.band
    prot  = geo.band_protection() if geo else [magnetic_protection_factor(lat)
                                                for lat in _BAND_LATS]
    scores = []
    for i in range(12):
        T_C   = b.T_K[i] - 273.15
        W     = float(b.soil_W[i])
        gpp_i = float(b.GPP[i])
        hab_i = float(b.habitable[i])
        ice_i = float(b.ice_mask[i])

        # 온도 적합도
        T_OPT, T_SIG = 28.0, 12.0
        t_ok = math.exp(-0.5 * ((T_C - T_OPT) / T_SIG) ** 2)

        # 수분 적합도
        w_ok = min(W, 1.0)

        # GPP 정규화 (최대 0.8 kg/m²/yr 기준)
        gpp_ok = min(1.0, gpp_i / 0.8)

        # 자기 보호
        mag_ok = prot[i]

        band_score = (
            t_ok   * 0.35 +
            w_ok   * 0.20 +
            gpp_ok * 0.25 +
            mag_ok * 0.20
        ) * hab_i * (1.0 - ice_i)

        scores.append(round(band_score, 4))
    return scores


# ── 탐색 엔진 ─────────────────────────────────────────────────────────────────

@dataclass
class SearchResult:
    """탐색 완료 결과."""
    candidates:      List[EdenCandidate]   # 통과한 후보 (score 내림차순)
    total_tested:    int
    total_passed:    int
    elapsed_sec:     float
    best:            Optional[EdenCandidate] = None
    grid_agent:      Optional[Any] = None   # Grid Engine 연동 시 위도축 에이전트 (선택)

    def summary(self) -> str:
        lines = [
            f"탐색 결과: {self.total_tested}개 조합 테스트 → "
            f"{self.total_passed}개 통과 ({self.elapsed_sec:.1f}초)",
        ]
        if self.best:
            lines.append(f"\n최우선 에덴 후보 (rank #1):")
            lines.append(self.best.summary())
        return "\n".join(lines)

    def top(self, n: int = 5) -> List[EdenCandidate]:
        return self.candidates[:n]

    def band_heatmap(self) -> str:
        """상위 후보들의 위도밴드 에덴 점수 히트맵."""
        if not self.candidates:
            return "(후보 없음)"
        top5 = self.candidates[:5]
        lats = _BAND_LATS
        lines = ["위도밴드 에덴 점수 히트맵 (상위 5개 후보)"]
        lines.append("  위도    " + "  ".join(f"#{i+1}" for i in range(len(top5))))
        lines.append("  " + "─" * 50)
        for j, lat in enumerate(lats):
            row = f"  {lat:+6.1f}°  "
            for c in top5:
                s = c.band_eden_score[j] if j < len(c.band_eden_score) else 0.0
                bar = '█' * int(s * 8)
                row += f"{bar:<8} "
            lines.append(row)
        return "\n".join(lines)

    def save(self, path: str = "docs/EDEN_SEARCH_RESULT.md",
             also_json: bool = True) -> str:
        """탐색 결과를 Markdown + JSON으로 저장.

        Parameters
        ----------
        path : str
            저장 경로 (Markdown).
        also_json : bool
            True면 .json도 함께 저장.

        Returns
        -------
        str  실제 저장된 파일 경로.
        """
        import datetime
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else '.', exist_ok=True)
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        lines = [
            f"# 에덴 탐색 결과 (Eden Search Result)",
            f"",
            f"생성: {now}  |  탐색: {self.total_tested}개  |  통과: {self.total_passed}개  "
            f"|  소요: {self.elapsed_sec:.1f}초",
            f"",
            f"## 에덴 점수 기준",
            f"",
            f"| 기준 | 설명 |",
            f"|------|------|",
            f"| T_range | 지표 온도 15~45°C |",
            f"| GPP | 전 지구 GPP ≥ 3.0 kg C/m²/yr |",
            f"| ice_bands | 빙하 밴드 수 ≤ 0 |",
            f"| mutation | mutation factor ≤ 10% |",
            f"| hab_bands | 거주 가능 밴드 ≥ 10/12 |",
            f"",
            f"## 상위 후보",
            f"",
        ]

        for c in self.top(10):
            T_C = c.ic.T_surface_K - 273.15
            b   = c.ic.band
            lines += [
                f"### Rank #{c.rank}  (score={c.score:.3f})",
                f"",
                f"| 파라미터 | 값 |",
                f"|---------|-----|",
                f"| phase | {c.ic.phase} |",
                f"| CO2 | {c.ic.CO2_ppm:.0f} ppm |",
                f"| H2O(대기) | {c.ic.H2O_atm_frac*100:.1f}% |",
                f"| H2O(궁창) | {c.ic.H2O_canopy*100:.1f}% |",
                f"| O2 | {c.ic.O2_frac*100:.1f}% |",
                f"| albedo | {c.ic.albedo:.3f} |",
                f"| f_land | {c.ic.f_land:.2f} |",
                f"| UV_shield | {c.ic.UV_shield:.2f} |",
                f"| T_surface | {T_C:.1f}°C |",
                f"| GPP | {float(b.GPP.sum()):.2f} kg C/m²/yr |",
                f"| 빙하 밴드 | {int(b.ice_mask.sum())}/12 |",
                f"| mutation | {c.ic.mutation_factor:.4f}x |",
                f"",
                f"**밴드 점수:** `{' '.join(f'{s:.2f}' for s in c.band_eden_score)}`",
                f"",
            ]

        # 히트맵 추가
        lines += ["## 위도밴드 히트맵", "", "```", self.band_heatmap(), "```", ""]

        md_text = "\n".join(lines)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(md_text)

        # JSON 저장
        json_path = path.replace('.md', '.json')
        if also_json:
            data = {
                "generated": now,
                "total_tested": self.total_tested,
                "total_passed": self.total_passed,
                "elapsed_sec":  self.elapsed_sec,
                "candidates": [
                    {
                        "rank":  c.rank,
                        "score": round(c.score, 4),
                        "phase": c.ic.phase,
                        "CO2_ppm":      c.ic.CO2_ppm,
                        "H2O_atm_frac": c.ic.H2O_atm_frac,
                        "H2O_canopy":   c.ic.H2O_canopy,
                        "O2_frac":      c.ic.O2_frac,
                        "albedo":       c.ic.albedo,
                        "f_land":       c.ic.f_land,
                        "UV_shield":    c.ic.UV_shield,
                        "T_C":          round(c.ic.T_surface_K - 273.15, 2),
                        "GPP":          round(float(c.ic.band.GPP.sum()), 3),
                        "ice_bands":    int(c.ic.band.ice_mask.sum()),
                        "mutation_factor": round(c.ic.mutation_factor, 5),
                        "band_eden_score": [round(s, 4) for s in c.band_eden_score],
                        "criteria_detail": c.criteria_detail,
                    }
                    for c in self.candidates
                ],
            }
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        return path


class EdenSearchEngine:
    """에덴 상태 탐색 엔진.

    독립 모듈 — Day1~7 PlanetRunner 없이도 동작.
    InitialConditions 동역학만으로 빠른 스크리닝.
    PlanetRunner 연동은 옵션(deep_validate).

    Parameters
    ----------
    criteria : EdenCriteria
        에덴 판정 기준.
    geo : EdenGeography, optional
        지리/자기장 컨텍스트. None이면 위도 함수로 자동 계산.
    phase : str
        'antediluvian' | 'postdiluvian' | 'exoplanet'
    verbose : bool
        진행 상황 출력.
    """

    def __init__(
        self,
        criteria:  EdenCriteria              = None,
        geo:       Optional[EdenGeography]   = None,
        phase:     str                       = 'antediluvian',
        verbose:   bool                      = True,
        score_fn:  Optional[Callable]        = None,
    ) -> None:
        self.criteria  = criteria or EdenCriteria()
        self.geo       = geo or make_eden_geography()
        self.phase     = phase
        self.verbose   = verbose
        self.score_fn  = score_fn or compute_eden_score

    def search(
        self,
        space: Optional[SearchSpace] = None,
        max_candidates: int = 50,
        min_score: float = 0.50,
    ) -> SearchResult:
        """파라미터 공간 스캔 → 에덴 후보 수집.

        Parameters
        ----------
        space : SearchSpace
            탐색 공간. None이면 phase에 맞는 기본값 사용.
        max_candidates : int
            수집할 최대 후보 수.
        min_score : float
            최소 에덴 점수 (이하는 수집하지 않음).

        Returns
        -------
        SearchResult
        """
        if space is None:
            if self.phase == 'antediluvian':
                space = make_antediluvian_space()
            elif self.phase == 'postdiluvian':
                space = make_postdiluvian_space()
            else:
                space = make_exoplanet_space()

        # 행성 탐사 확장: Grid Engine 연동 시 탐사 포커스로 후보 트림 성능 향상
        exploration = None
        try:
            from .exploration import EdenExplorationGrid, trim_candidates_by_exploration
            exploration = EdenExplorationGrid()
        except Exception:
            trim_candidates_by_exploration = None

        candidates: List[EdenCandidate] = []
        total_tested = 0
        t0 = time.time()

        for params in space.grid():
            total_tested += 1
            try:
                ic = InitialConditions(
                    phase        = self.phase if self.phase != 'exoplanet' else 'postdiluvian',
                    CO2_ppm      = params['CO2_ppm'],
                    H2O_atm_frac = params['H2O_atm_frac'],
                    H2O_canopy   = params['H2O_canopy'],
                    O2_frac      = params['O2_frac'],
                    CH4_ppm      = params['CH4_ppm'],
                    albedo       = params['albedo'],
                    f_land       = params['f_land'],
                    UV_shield    = params['UV_shield'],
                    pressure_atm = params['pressure_atm'],
                    precip_mode  = params['precip_mode'],
                )
            except Exception:
                continue

            passed, detail = self.criteria.check(ic)
            if not passed:
                continue

            score = self.score_fn(ic, self.criteria, self.geo)
            if score < min_score:
                continue

            band_scores = compute_band_eden_scores(ic, self.geo)
            c = EdenCandidate(
                ic              = ic,
                score           = score,
                criteria_detail = detail,
                band_eden_score = band_scores,
            )
            candidates.append(c)
            if exploration is not None:
                exploration.update_from_candidate(c)

            if len(candidates) >= max_candidates * 3:
                if trim_candidates_by_exploration is not None and exploration is not None:
                    candidates = trim_candidates_by_exploration(candidates, max_candidates, exploration)
                else:
                    candidates.sort(key=lambda x: x.score, reverse=True)
                    candidates = candidates[:max_candidates]

        # 최종 정렬 + 순위 부여 (탐사 그리드 있으면 포커스 밴드 반영)
        if trim_candidates_by_exploration is not None and exploration is not None:
            candidates = trim_candidates_by_exploration(candidates, max_candidates, exploration)
        else:
            candidates.sort(key=lambda x: x.score, reverse=True)
            candidates = candidates[:max_candidates]
        for i, c in enumerate(candidates):
            c.rank = i + 1

        elapsed = time.time() - t0
        grid_agent = None
        if exploration is not None and getattr(exploration, '_grid_agent', None) is not None:
            grid_agent = exploration._grid_agent
        else:
            try:
                pass  # grid_engine_bridge: cookiie_brain 전용, 독립 엔진에서는 미사용
            except Exception:
                pass
        result = SearchResult(
            candidates   = candidates,
            total_tested = total_tested,
            total_passed = len(candidates),
            elapsed_sec  = elapsed,
            best         = candidates[0] if candidates else None,
            grid_agent   = grid_agent,
        )

        if self.verbose:
            print(result.summary())

        return result

    def quick_check(self, ic: InitialConditions) -> Tuple[bool, float, Dict]:
        """단일 InitialConditions에 대한 빠른 에덴 판정."""
        passed, detail = self.criteria.check(ic)
        score = self.score_fn(ic, self.criteria, self.geo) if passed else 0.0
        return passed, score, detail

    def compare_phases(self) -> None:
        """에덴 vs 현재 지구 에덴 점수 비교."""
        eden_ic = make_antediluvian()
        post_ic = make_postdiluvian()

        eden_passed, eden_score, eden_detail = self.quick_check(eden_ic)
        post_passed, post_score, post_detail = self.quick_check(post_ic)

        eden_bands = compute_band_eden_scores(eden_ic, self.geo)
        post_bands = compute_band_eden_scores(post_ic, None)

        print("=" * 60)
        print("에덴 vs 현재 — 에덴 점수 비교")
        print("=" * 60)
        print(f"\n에덴(antediluvian): score={eden_score:.3f}  "
              f"판정={'PASS' if eden_passed else 'FAIL'}")
        print(f"현재(postdiluvian): score={post_score:.3f}  "
              f"판정={'PASS' if post_passed else 'FAIL'}")
        print()
        print("위도밴드별 에덴 점수:")
        print("  위도       에덴        현재")
        print("  " + "─" * 44)
        for i, lat in enumerate(_BAND_LATS):
            e = eden_bands[i]
            p = post_bands[i]
            e_bar = '█' * int(e * 16)
            p_bar = '█' * int(p * 16)
            flag  = ' ←' if e > p + 0.1 else ''
            print(f"  {lat:+6.1f}°  {e:.3f} {e_bar:<16}  "
                  f"{p:.3f} {p_bar:<16}{flag}")
        print()
        print("판정 상세:")
        all_keys = set(eden_detail) | set(post_detail)
        for k in sorted(all_keys):
            ev = eden_detail.get(k, '-')
            pv = post_detail.get(k, '-')
            print(f"  {k:15s}  에덴={'✅' if ev else '❌'}  "
                  f"현재={'✅' if pv else '❌'}")

    def deep_validate(
        self,
        candidates: List[EdenCandidate],
        n_steps: int = 20,
        dt_yr: float = 1.0,
        top_n: int = 5,
    ) -> List[Dict]:
        """상위 후보를 PlanetRunner로 2차 검증 (동역학 안정성).

        IC 스크리닝은 정적 계산이므로
        실제 PlanetRunner로 n_steps 동안 돌려서
        CO2/T 안정성 + 스트레스 지속 여부를 확인.

        Parameters
        ----------
        candidates : List[EdenCandidate]
            1차 통과 후보 (score 내림차순).
        n_steps : int
            검증 스텝 수 (yr 단위).
        dt_yr : float
            스텝 크기.
        top_n : int
            검증할 상위 후보 수.

        Returns
        -------
        List[Dict]  검증 결과 (rank, stable, final_T, final_CO2, stress)
        """
        try:
            from ..day7.runner import make_planet_runner
        except ImportError:
            print("  [deep_validate] PlanetRunner import 실패 — 스킵")
            return []

        results = []
        targets = candidates[:top_n]

        print(f"\n  PlanetRunner 2차 검증 ({top_n}개 후보 × {n_steps}스텝)")
        print("  " + "─" * 52)

        for c in targets:
            kwargs = c.ic.to_runner_kwargs()
            runner = make_planet_runner(initial_conditions=kwargs)

            snaps = []
            for _ in range(n_steps):
                snap = runner.step(dt_yr=dt_yr)
                snaps.append(snap)

            final = snaps[-1]
            # CO2 안정성: 마지막 5스텝 표준편차
            co2_vals = [s.CO2_ppm for s in snaps[-5:]]
            co2_std  = (sum((x - sum(co2_vals)/len(co2_vals))**2
                            for x in co2_vals) / len(co2_vals)) ** 0.5
            # T 안정성
            t_vals  = [s.T_surface_K for s in snaps[-5:]]
            t_std   = (sum((x - sum(t_vals)/len(t_vals))**2
                           for x in t_vals) / len(t_vals)) ** 0.5

            stable = (co2_std < 10.0 and t_std < 1.0
                      and final.planet_stress < self.criteria.stress_max)

            row = {
                "rank":       c.rank,
                "ic_score":   round(c.score, 3),
                "stable":     stable,
                "final_T_C":  round(final.T_surface_K - 273.15, 1),
                "final_CO2":  round(final.CO2_ppm, 1),
                "stress":     round(final.planet_stress, 4),
                "CO2_std":    round(co2_std, 2),
                "T_std":      round(t_std, 3),
            }
            results.append(row)

            flag = "✅ STABLE" if stable else "❌ UNSTABLE"
            print(f"  rank #{c.rank:2d}  {flag}  "
                  f"T={row['final_T_C']:.1f}°C  CO2={row['final_CO2']:.0f}ppm  "
                  f"stress={row['stress']:.4f}")

        return results


# ── 팩토리 ────────────────────────────────────────────────────────────────────

def make_eden_search(
    phase: str = 'antediluvian',
    strict: bool = False,
    verbose: bool = True,
) -> EdenSearchEngine:
    """EdenSearchEngine 생성 helper.

    Parameters
    ----------
    phase : str
        'antediluvian' | 'postdiluvian' | 'exoplanet'
    strict : bool
        True → 엄격한 기준 (빙하=0, mutation<0.05, GPP>4.0)
        False → 관대한 기준 (탐색 범위 넓음)
    verbose : bool
        진행 상황 출력.
    """
    if strict:
        criteria = EdenCriteria(
            T_min_C       = 20.0,
            T_max_C       = 40.0,
            GPP_min       = 4.0,
            stress_max    = 0.02,
            ice_bands_max = 0,
            mutation_max  = 0.05,
            hab_bands_min = 12,
        )
    else:
        criteria = EdenCriteria(
            T_min_C       = 15.0,
            T_max_C       = 45.0,
            GPP_min       = 3.0,
            stress_max    = 0.05,
            ice_bands_max = 0,
            mutation_max  = 0.10,
            hab_bands_min = 10,
        )

    geo = make_eden_geography() if phase == 'antediluvian' else None

    return EdenSearchEngine(
        criteria = criteria,
        geo      = geo,
        phase    = phase,
        verbose  = verbose,
    )


__all__ = [
    'EdenCriteria',
    'EdenCandidate',
    'SearchSpace',
    'SearchResult',
    'EdenSearchEngine',
    'compute_eden_score',
    'compute_band_eden_scores',
    'make_eden_search',
    'make_antediluvian_space',
    'make_postdiluvian_space',
    'make_exoplanet_space',
]
