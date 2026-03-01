"""basin_stability.py — 에덴 상태 Basin 안정성 검증 모듈

핵심 철학:
  "진짜 에덴은 교란에도 에덴으로 복귀하는 안정 어트랙터다."

Ring Attractor는 입력이 사라진 후에도 상태를 지속적으로 유지하는 엔진이다.
이 모듈은 그 성질을 활용해:

  1. 에덴 후보의 파라미터 상태를 Ring Attractor로 인코딩
  2. 외부 교란(perturbation) 적용
  3. 교란 후 에덴 상태로 복귀하는지 안정성 테스트
  4. "Basin Depth" (복귀력) 계산 → 진정한 에덴 basin 판별

Ring Attractor 의존 여부:
  - ring-attractor-engine 패키지 있으면: 실제 뉴런 시뮬레이션으로 안정성 검증
  - 없으면: 수학적 Lyapunov 함수 기반 대체 구현 (항상 동작)

활용 예시:
  from cherubim.basin_stability import EdenBasinStability
  bst = EdenBasinStability()
  result = bst.test(candidate)
  print(result.summary())
"""

from __future__ import annotations

import math
import sys
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .initial_conditions import InitialConditions, make_antediluvian
from .search import EdenCandidate, compute_eden_score, EdenCriteria


# ── Ring Attractor 선택적 의존 ────────────────────────────────────────────────

_RING_ENGINE_PATH = os.path.join(
    os.path.expanduser("~"),
    "Desktop", "00_BRAIN", "Archive", "Integrated",
    "4.Hippo_Memory_Engine", "Hippo_memory", "v3_Upgraded",
    "hippo_memory_v3.0.0", "release", "ring-attractor-engine"
)

_HAS_RING_ENGINE = False
_RingAttractorEngine = None
_RingState = None

try:
    if os.path.isdir(_RING_ENGINE_PATH):
        if _RING_ENGINE_PATH not in sys.path:
            sys.path.insert(0, _RING_ENGINE_PATH)
        from hippo_memory.ring_engine import RingAttractorEngine as _RAE, RingState as _RS
        _RingAttractorEngine = _RAE
        _RingState = _RS
        _HAS_RING_ENGINE = True
except Exception:
    _HAS_RING_ENGINE = False


# ── 파라미터 → Ring 방향 인코딩 ──────────────────────────────────────────────

_PARAM_ORDER = [
    'CO2_ppm',       # 0
    'H2O_atm_frac',  # 1
    'O2_frac',       # 2
    'albedo',        # 3
    'f_land',        # 4
    'UV_shield',     # 5
    'mutation_factor', # 6
    'T_surface_K',   # 7
]

def _ic_to_direction(ic: InitialConditions, n_directions: int = 64) -> int:
    """InitialConditions의 에덴 점수를 Ring 방향 인덱스로 인코딩.

    에덴 점수 [0~1] → Ring의 [0~n_directions) 위치.
    높은 에덴 점수 = Ring의 안정 위치(center 방향).

    n_directions=64 기본 (Ring Attractor 기본 크기).
    """
    criteria = EdenCriteria()
    score = compute_eden_score(ic, criteria)
    # 점수 → 방향: 0.5 이상 = 상위 절반, 1.0 = 방향 32 (Ring 중심)
    direction = int(score * (n_directions - 1))
    return max(0, min(n_directions - 1, direction))


def _ic_to_vector(ic: InitialConditions) -> List[float]:
    """InitialConditions → 정규화된 파라미터 벡터 [0~1] 반환."""
    # 각 파라미터를 물리적 범위로 정규화
    ranges = {
        'CO2_ppm':       (100.0, 2000.0),
        'H2O_atm_frac':  (0.001, 0.20),
        'O2_frac':       (0.10,  0.35),
        'albedo':        (0.05,  0.70),
        'f_land':        (0.10,  0.80),
        'UV_shield':     (0.00,  1.00),
        'mutation_factor': (0.0, 2.0),
        'T_surface_K':   (220.0, 380.0),
    }
    vec = []
    for param, (lo, hi) in ranges.items():
        val = getattr(ic, param, 0.0)
        normalized = (val - lo) / (hi - lo)
        vec.append(max(0.0, min(1.0, normalized)))
    return vec


def _perturb_ic(ic: InitialConditions, strength: float = 0.1) -> InitialConditions:
    """InitialConditions에 무작위 교란 적용.

    strength : 교란 강도 [0~1] (파라미터 범위 대비 비율)
    """
    import random
    rng = random.Random(42)  # 재현 가능한 난수

    # 교란 범위: 각 파라미터의 ±strength 비율 변동
    perturbations = {
        'CO2_ppm':       strength * 200.0,
        'H2O_atm_frac':  strength * 0.03,
        'O2_frac':       strength * 0.05,
        'albedo':        strength * 0.10,
        'f_land':        strength * 0.10,
        'UV_shield':     strength * 0.20,
    }

    kwargs = {
        'phase':        ic.phase,
        'CO2_ppm':      max(50.0,  ic.CO2_ppm      + rng.uniform(-1, 1) * perturbations['CO2_ppm']),
        'H2O_atm_frac': max(0.001, ic.H2O_atm_frac + rng.uniform(-1, 1) * perturbations['H2O_atm_frac']),
        'H2O_canopy':   ic.H2O_canopy,
        'O2_frac':      max(0.05,  min(0.40, ic.O2_frac + rng.uniform(-1, 1) * perturbations['O2_frac'])),
        'CH4_ppm':      ic.CH4_ppm,
        'albedo':       max(0.05,  min(0.90, ic.albedo   + rng.uniform(-1, 1) * perturbations['albedo'])),
        'f_land':       max(0.05,  min(0.90, ic.f_land   + rng.uniform(-1, 1) * perturbations['f_land'])),
        'UV_shield':    max(0.0,   min(1.0,  ic.UV_shield + rng.uniform(-1, 1) * perturbations['UV_shield'])),
        'pressure_atm': ic.pressure_atm,
        'precip_mode':  ic.precip_mode,
    }
    return InitialConditions(**kwargs)


# ── Basin 안정성 수학적 구현 (Ring Engine 없을 때) ───────────────────────────

def _lyapunov_stability(
    ic_original: InitialConditions,
    n_perturbations: int = 8,
    strengths: Tuple[float, ...] = (0.05, 0.10, 0.20, 0.30),
) -> Dict:
    """Lyapunov 함수 기반 Basin 안정성 테스트.

    에덴 점수를 Lyapunov 함수로 사용:
      V(x) = 1 - eden_score(x)  → 에덴 = V=0 (안정점)
      교란 후 V가 감소하면 → 에덴으로 복귀 (안정)

    Returns
    -------
    dict with keys:
      base_score    : 원본 에덴 점수
      perturb_scores: 교란별 점수 (강도, 평균, 최소)
      basin_depth   : Basin 깊이 [0~1]
      is_stable     : 안정 여부
      recovery_rate : 복귀율 (교란 중 에덴 유지 비율)
    """
    criteria = EdenCriteria()
    base_score = compute_eden_score(ic_original, criteria)

    perturb_scores = []
    for strength in strengths:
        scores_at_strength = []
        for _ in range(n_perturbations):
            ic_p = _perturb_ic(ic_original, strength)
            s = compute_eden_score(ic_p, criteria)
            scores_at_strength.append(s)
        mean_s = sum(scores_at_strength) / len(scores_at_strength)
        min_s  = min(scores_at_strength)
        perturb_scores.append({
            'strength': strength,
            'mean':     round(mean_s, 4),
            'min':      round(min_s, 4),
            'drop':     round(base_score - mean_s, 4),
        })

    # Basin 깊이: 강한 교란(30%)에서도 에덴 점수가 유지되는 정도
    strong_perturb = perturb_scores[-1]  # strength=0.30
    basin_depth = min(1.0, max(0.0, strong_perturb['mean'] / max(0.001, base_score)))

    # 복귀율: 교란 후에도 에덴 기준(0.5) 초과하는 비율
    all_scores = []
    for ps in perturb_scores:
        all_scores.append(ps['mean'])
    recovery_rate = sum(1 for s in all_scores if s >= 0.50) / len(all_scores)

    is_stable = basin_depth >= 0.70 and recovery_rate >= 0.75

    return {
        'base_score':    round(base_score, 4),
        'perturb_scores': perturb_scores,
        'basin_depth':   round(basin_depth, 4),
        'is_stable':     is_stable,
        'recovery_rate': round(recovery_rate, 4),
    }


# ── Ring Attractor 실제 구현 ─────────────────────────────────────────────────

def _ring_attractor_stability(
    ic: InitialConditions,
    n_directions: int = 64,
    hold_ms: float = 200.0,
    n_trials: int = 5,
) -> Dict:
    """Ring Attractor 실제 뉴런 시뮬레이션으로 Basin 안정성 테스트.

    에덴 상태를 Ring에 주입 → 입력 제거 → 상태 유지 여부 확인.

    Returns
    -------
    dict with keys:
      ring_center      : Ring 최종 상태 중심
      ring_stability   : Ring 안정성 점수
      ring_sustained   : 상태 유지 여부
      orbit_stability  : 궤도 안정성
      perturb_sustained: 교란 후 상태 유지 비율
      basin_depth      : Ring 기반 Basin 깊이
    """
    if _RingAttractorEngine is None:
        return {}

    direction = _ic_to_direction(ic, n_directions)
    results = []

    for trial in range(n_trials):
        ring = _RingAttractorEngine()
        # 에덴 상태 주입
        ring.inject(direction, strength=0.9)
        ring.run(duration_ms=50.0)   # 50ms 학습
        ring.release_input()         # 입력 제거
        state = ring.run(duration_ms=hold_ms)  # hold_ms 동안 자유 진화
        results.append(state)

    # 안정성 통계
    centers   = [r.center for r in results]
    stabs     = [r.stability for r in results]
    sustained = [r.sustained for r in results]

    mean_center = sum(centers) / len(centers)
    mean_stab   = sum(stabs) / len(stabs)
    n_sustained = sum(sustained)
    sustain_rate = n_sustained / n_trials

    # 궤도 안정성: center가 초기 방향에서 얼마나 drift했는지
    drift_list = [abs(c - direction) for c in centers]
    mean_drift = sum(drift_list) / len(drift_list)
    orbit_stab = max(0.0, 1.0 - mean_drift / (n_directions / 2))

    # Basin 깊이: sustain_rate × mean_stab × orbit_stab
    basin_depth = sustain_rate * mean_stab * orbit_stab

    return {
        'ring_center':       round(mean_center, 2),
        'ring_stability':    round(mean_stab, 4),
        'ring_sustained':    sustain_rate >= 0.60,
        'orbit_stability':   round(orbit_stab, 4),
        'perturb_sustained': round(sustain_rate, 4),
        'basin_depth':       round(basin_depth, 4),
        'n_trials':          n_trials,
    }


# ── 안정성 결과 컨테이너 ──────────────────────────────────────────────────────

@dataclass
class BasinStabilityResult:
    """에덴 Basin 안정성 테스트 결과.

    Attributes
    ----------
    candidate     : 테스트한 EdenCandidate
    base_score    : 원본 에덴 점수 [0~1]
    basin_depth   : Basin 깊이 — 교란에도 에덴 유지 능력 [0~1]
    is_stable     : 진정한 안정 basin 여부
    recovery_rate : 교란 후 에덴 복귀율 [0~1]
    ring_used     : Ring Attractor 엔진 사용 여부
    ring_details  : Ring 엔진 상세 (사용한 경우)
    lyapunov_details : Lyapunov 분석 상세
    stability_grade  : 등급 (S/A/B/C/F)
    """
    candidate:          EdenCandidate
    base_score:         float
    basin_depth:        float
    is_stable:          bool
    recovery_rate:      float
    ring_used:          bool
    ring_details:       Dict   = field(default_factory=dict)
    lyapunov_details:   Dict   = field(default_factory=dict)
    stability_grade:    str    = "F"

    def __post_init__(self) -> None:
        self.stability_grade = self._compute_grade()

    def _compute_grade(self) -> str:
        bd = self.basin_depth
        rr = self.recovery_rate
        if   bd >= 0.90 and rr >= 0.90: return "S"   # 완벽한 에덴 basin
        elif bd >= 0.80 and rr >= 0.80: return "A"   # 강한 에덴 basin
        elif bd >= 0.65 and rr >= 0.65: return "B"   # 중간 에덴 basin
        elif bd >= 0.50 and rr >= 0.50: return "C"   # 약한 에덴 basin
        else:                           return "F"   # 안정 basin 아님

    def summary(self) -> str:
        mode = "Ring Attractor" if self.ring_used else "Lyapunov 수학적 분석"
        lines = [
            f"  ── Basin 안정성 테스트 결과 ({mode}) ──",
            f"  rank=#{self.candidate.rank}  "
            f"에덴점수={self.base_score:.3f}  "
            f"Basin깊이={self.basin_depth:.3f}  "
            f"복귀율={self.recovery_rate:.2%}",
            f"  안정등급: {self.stability_grade}  "
            f"진정한Basin={'✅' if self.is_stable else '❌'}",
        ]
        if self.ring_used and self.ring_details:
            rd = self.ring_details
            lines.append(
                f"  Ring: 중심={rd.get('ring_center', '?'):.1f}  "
                f"안정성={rd.get('ring_stability', '?'):.3f}  "
                f"유지={rd.get('ring_sustained', '?')}  "
                f"궤도안정성={rd.get('orbit_stability', '?'):.3f}"
            )
        if self.lyapunov_details:
            ld = self.lyapunov_details
            ps = ld.get('perturb_scores', [])
            if ps:
                lines.append(f"  교란 테스트:")
                for p in ps:
                    bar = "█" * int(p['mean'] * 20)
                    lines.append(
                        f"    교란{p['strength']*100:.0f}%  "
                        f"{bar:<20}  score={p['mean']:.3f}  "
                        f"drop={p['drop']:+.3f}"
                    )
        return "\n".join(lines)


# ── 메인 검증 클래스 ──────────────────────────────────────────────────────────

class EdenBasinStability:
    """에덴 상태 Basin 안정성 검증 엔진.

    Ring Attractor를 활용해 에덴 후보가 진정한 안정 어트랙터인지 검증.
    Ring Engine 없으면 Lyapunov 수학적 분석으로 자동 대체.

    Parameters
    ----------
    use_ring_engine : bool
        True이면 Ring Attractor 실제 엔진 시도 (없으면 자동 Lyapunov)
    n_perturbations : int
        교란 시험 횟수
    hold_ms : float
        Ring Attractor 상태 유지 테스트 시간 [ms]

    Examples
    --------
    >>> bst = EdenBasinStability()
    >>> result = bst.test(candidate)
    >>> print(result.summary())
    >>> results = bst.test_batch(candidates[:5])
    >>> bst.print_ranking(results)
    """

    def __init__(
        self,
        use_ring_engine: bool = True,
        n_perturbations: int = 8,
        hold_ms: float = 200.0,
    ) -> None:
        self.use_ring = use_ring_engine and _HAS_RING_ENGINE
        self.n_perturbations = n_perturbations
        self.hold_ms = hold_ms

        if use_ring_engine and not _HAS_RING_ENGINE:
            print("  ℹ  Ring Attractor Engine 미설치 → Lyapunov 수학적 분석 모드")
        elif self.use_ring:
            print("  ✅ Ring Attractor Engine 연결됨 — 실제 뉴런 Basin 검증 활성화")

    def test(self, candidate: EdenCandidate) -> BasinStabilityResult:
        """단일 EdenCandidate에 대해 Basin 안정성 테스트.

        Parameters
        ----------
        candidate : EdenCandidate
            테스트할 에덴 후보

        Returns
        -------
        BasinStabilityResult
        """
        ic = candidate.ic

        # Lyapunov 분석 (항상 실행 — 기준선)
        lyap = _lyapunov_stability(
            ic,
            n_perturbations=self.n_perturbations,
            strengths=(0.05, 0.10, 0.20, 0.30),
        )

        # Ring Attractor 분석 (선택)
        ring_details = {}
        if self.use_ring:
            try:
                ring_details = _ring_attractor_stability(
                    ic,
                    hold_ms=self.hold_ms,
                    n_trials=5,
                )
            except Exception as e:
                print(f"  ⚠ Ring 분석 실패: {e} → Lyapunov 단독 사용")
                self.use_ring = False

        # Basin 깊이: Ring 있으면 결합, 없으면 Lyapunov만
        if ring_details:
            # Ring + Lyapunov 결합 (70% Ring, 30% Lyapunov)
            basin_depth = (
                ring_details.get('basin_depth', 0.0) * 0.70 +
                lyap['basin_depth'] * 0.30
            )
            recovery_rate = (
                ring_details.get('perturb_sustained', 0.0) * 0.60 +
                lyap['recovery_rate'] * 0.40
            )
        else:
            basin_depth   = lyap['basin_depth']
            recovery_rate = lyap['recovery_rate']

        is_stable = basin_depth >= 0.65 and recovery_rate >= 0.65

        return BasinStabilityResult(
            candidate        = candidate,
            base_score       = lyap['base_score'],
            basin_depth      = round(basin_depth, 4),
            is_stable        = is_stable,
            recovery_rate    = round(recovery_rate, 4),
            ring_used        = bool(ring_details),
            ring_details     = ring_details,
            lyapunov_details = lyap,
        )

    def test_batch(
        self,
        candidates: List[EdenCandidate],
        verbose: bool = True,
    ) -> List[BasinStabilityResult]:
        """복수 EdenCandidate 일괄 Basin 안정성 테스트.

        Parameters
        ----------
        candidates : List[EdenCandidate]
        verbose    : True이면 진행 상황 출력

        Returns
        -------
        List[BasinStabilityResult]  (basin_depth 내림차순)
        """
        if verbose:
            print(f"\n  🔬 Basin 안정성 일괄 검증: {len(candidates)}개 후보")
            print("  " + "─" * 60)

        results = []
        for i, c in enumerate(candidates):
            result = self.test(c)
            results.append(result)
            if verbose:
                grade_icon = {"S": "🌟", "A": "✅", "B": "🟡", "C": "🟠", "F": "❌"}.get(
                    result.stability_grade, "❓"
                )
                print(
                    f"  rank #{c.rank:2d}  {grade_icon} {result.stability_grade}  "
                    f"Basin={result.basin_depth:.3f}  "
                    f"복귀율={result.recovery_rate:.2%}  "
                    f"에덴={'STABLE' if result.is_stable else 'UNSTABLE'}"
                )

        # basin_depth 내림차순 정렬
        results.sort(key=lambda r: r.basin_depth, reverse=True)
        return results

    def print_ranking(self, results: List[BasinStabilityResult]) -> None:
        """Basin 안정성 랭킹 출력."""
        print("\n" + "=" * 65)
        print("  🏆 에덴 Basin 안정성 랭킹")
        print("  (교란에도 에덴 상태를 유지하는 진정한 안정 Basin)")
        print("  " + "─" * 63)
        print(f"  {'순위':>4}  {'등급':>4}  {'Basin깊이':>9}  {'복귀율':>7}  "
              f"{'에덴점수':>8}  {'IC rank':>7}")
        print("  " + "─" * 63)

        grade_icons = {"S": "🌟", "A": "✅", "B": "🟡", "C": "🟠", "F": "❌"}
        for i, r in enumerate(results, 1):
            icon = grade_icons.get(r.stability_grade, "❓")
            stable_str = "STABLE" if r.is_stable else "      "
            print(
                f"  {i:>4}  {icon}{r.stability_grade:>2}  "
                f"{r.basin_depth:>9.4f}  "
                f"{r.recovery_rate:>7.2%}  "
                f"{r.base_score:>8.4f}  "
                f"  #{r.candidate.rank:<5}  "
                f"{stable_str}"
            )
        print("=" * 65)

        # 안정 Basin 비율
        n_stable = sum(1 for r in results if r.is_stable)
        print(f"\n  안정 Basin: {n_stable}/{len(results)}개 "
              f"({n_stable/len(results)*100:.0f}%)")
        if results:
            best = results[0]
            print(f"  최고 Basin: rank #{best.candidate.rank}  "
                  f"depth={best.basin_depth:.4f}  grade={best.stability_grade}")
        print()


# ── 헬퍼 함수 ────────────────────────────────────────────────────────────────

def make_basin_stability(use_ring: bool = True) -> EdenBasinStability:
    """EdenBasinStability 생성 헬퍼."""
    return EdenBasinStability(use_ring_engine=use_ring)


def quick_basin_test(
    candidate: EdenCandidate,
    verbose: bool = True,
) -> BasinStabilityResult:
    """단일 후보 빠른 Basin 안정성 테스트."""
    bst = EdenBasinStability(use_ring_engine=True)
    result = bst.test(candidate)
    if verbose:
        print(result.summary())
    return result


__all__ = [
    "EdenBasinStability",
    "BasinStabilityResult",
    "make_basin_stability",
    "quick_basin_test",
    "_HAS_RING_ENGINE",
]
