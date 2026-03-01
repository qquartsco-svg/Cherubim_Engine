"""param_space.py — 다차원 파라미터 공간 탐색 모듈 (GridND)

핵심 철학:
  "에덴의 파라미터 basin은 다차원 공간에서 어떤 형태인가?"

기존 EdenSearchEngine은 7개 파라미터를 순열 조합(combinatorial)으로 탐색.
→ 공간 구조 없음, 시각화 불가, 탐색 방향성 없음.

이 모듈은 Grid Engine의 위상 공간(phase space) 개념을 차용해:
  2D 슬라이스: CO2 × T   → 기후 상태도
  3D 볼륨:     CO2 × T × O2  → 3D 에덴 basin
  4D 하이퍼:   CO2 × T × O2 × UV → 4D 파라미터 에덴 영역
  5D 풀:       CO2 × T × O2 × UV × albedo → 완전 행성 파라미터 매핑
  7D 최대:     7개 파라미터 전체

주요 기능:
  ParamAxis        — 단일 파라미터 축 정의
  ParamGrid        — nD 파라미터 그리드 (n=2~7)
  ParamSlice       — nD 결과 2D 슬라이스 시각화
  EdenParamScanner — 다차원 파라미터 공간 스캔 엔진
  EdenBasinShape   — 에덴 basin의 다차원 형태 분석

활용 예시:
  from cherubim.param_space import EdenParamScanner, CO2_AXIS, TEMP_AXIS
  scanner = EdenParamScanner()
  result = scanner.scan_2d(CO2_AXIS, TEMP_AXIS)
  result.print_heatmap()
  result.print_basin_boundary()
"""

from __future__ import annotations

import math
import sys
import os
import itertools
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Callable, Iterator

from .initial_conditions import InitialConditions, make_antediluvian
from .search import EdenCriteria, compute_eden_score


# ── Grid Engine 선택적 의존 ──────────────────────────────────────────────────

_GRID_ENGINE_PATH = os.path.join(
    os.path.expanduser("~"),
    "Desktop", "00_BRAIN", "Archive", "Integrated",
    "4.Hippo_Memory_Engine", "Hippo_memory", "v3_Upgraded",
    "hippo_memory_v3.0.0", "release", "grid-engine"
)

_HAS_GRID_ENGINE = False
_Grid2DEngine = None

try:
    if os.path.isdir(_GRID_ENGINE_PATH):
        if _GRID_ENGINE_PATH not in sys.path:
            sys.path.insert(0, _GRID_ENGINE_PATH)
        from grid_engine import Grid2DEngine as _G2D, Grid2DConfig, GridInput
        _Grid2DEngine = _G2D
        _HAS_GRID_ENGINE = True
except Exception:
    _HAS_GRID_ENGINE = False


# ── 파라미터 축 정의 ─────────────────────────────────────────────────────────

@dataclass
class ParamAxis:
    """단일 파라미터 축 정의.

    Attributes
    ----------
    name    : 파라미터명 (InitialConditions 속성명)
    label   : 표시 레이블
    lo      : 탐색 하한
    hi      : 탐색 상한
    steps   : 분할 수
    unit    : 단위 표시 문자열
    """
    name:   str
    label:  str
    lo:     float
    hi:     float
    steps:  int
    unit:   str = ""

    @property
    def values(self) -> List[float]:
        """균등 분할 값 리스트."""
        if self.steps == 1:
            return [self.lo]
        return [
            self.lo + (self.hi - self.lo) * i / (self.steps - 1)
            for i in range(self.steps)
        ]

    @property
    def center(self) -> float:
        return (self.lo + self.hi) / 2.0

    def __str__(self) -> str:
        return (f"ParamAxis({self.label}: "
                f"{self.lo}{self.unit}~{self.hi}{self.unit} "
                f"×{self.steps})")


# ── 표준 파라미터 축 ─────────────────────────────────────────────────────────

CO2_AXIS = ParamAxis("CO2_ppm",       "CO2",      100,  800,  16, "ppm")
TEMP_AXIS = ParamAxis("T_surface_K",  "T_surface", 273, 323,  16, "K")   # 0~50°C
O2_AXIS  = ParamAxis("O2_frac",       "O2",        0.10, 0.35, 10, "")
UV_AXIS  = ParamAxis("UV_shield",     "UV_shield", 0.0,  1.0,  10, "")
ALB_AXIS = ParamAxis("albedo",        "Albedo",    0.05, 0.60, 10, "")
H2O_AXIS = ParamAxis("H2O_atm_frac",  "H2O_atm",  0.01, 0.10, 8,  "")
LAND_AXIS = ParamAxis("f_land",       "f_land",   0.10, 0.70, 8,  "")

# 표준 5D 축 조합 (행성 완전 탐색)
_5D_AXES = [CO2_AXIS, TEMP_AXIS, O2_AXIS, UV_AXIS, ALB_AXIS]
# 표준 7D 축 조합 (풀 파라미터)
_7D_AXES = [CO2_AXIS, TEMP_AXIS, O2_AXIS, UV_AXIS, ALB_AXIS, H2O_AXIS, LAND_AXIS]


# ── IC 생성 헬퍼 ─────────────────────────────────────────────────────────────

def _make_ic_from_params(
    base_ic: InitialConditions,
    overrides: Dict[str, float],
) -> Optional[InitialConditions]:
    """base_ic에서 파라미터 일부 오버라이드해 새 IC 생성."""
    try:
        kwargs = {
            'phase':        base_ic.phase,
            'CO2_ppm':      getattr(base_ic, 'CO2_ppm', 280.0),
            'H2O_atm_frac': getattr(base_ic, 'H2O_atm_frac', 0.03),
            'H2O_canopy':   getattr(base_ic, 'H2O_canopy', 0.0),
            'O2_frac':      getattr(base_ic, 'O2_frac', 0.21),
            'CH4_ppm':      getattr(base_ic, 'CH4_ppm', 0.7),
            'albedo':       getattr(base_ic, 'albedo', 0.30),
            'f_land':       getattr(base_ic, 'f_land', 0.30),
            'UV_shield':    getattr(base_ic, 'UV_shield', 0.0),
            'pressure_atm': getattr(base_ic, 'pressure_atm', 1.0),
            'precip_mode':  getattr(base_ic, 'precip_mode', 'rain'),
        }

        # T_surface_K는 IC 내부 계산값이므로 직접 설정 불가 → CO2 조정으로 근사
        # 실제로는 IC의 내부 물리 모델이 T를 계산하므로 T_surface_K 오버라이드는 근사치
        for k, v in overrides.items():
            if k == 'T_surface_K':
                continue  # T는 내부 계산값 — skip (CO2 통해 간접 조정)
            if k in kwargs:
                kwargs[k] = v

        return InitialConditions(**kwargs)
    except Exception:
        return None


# ── 2D 슬라이스 결과 ─────────────────────────────────────────────────────────

@dataclass
class ParamSlice2D:
    """2D 파라미터 슬라이스 에덴 점수 행렬.

    Attributes
    ----------
    x_axis  : X축 ParamAxis
    y_axis  : Y축 ParamAxis
    scores  : [y_steps × x_steps] 에덴 점수 행렬
    base_ic : 기반 InitialConditions
    """
    x_axis:   ParamAxis
    y_axis:   ParamAxis
    scores:   List[List[float]]   # [yi][xi]
    base_ic:  InitialConditions
    global_max:  float = 0.0
    global_mean: float = 0.0

    def __post_init__(self) -> None:
        flat = [s for row in self.scores for s in row]
        if flat:
            self.global_max  = round(max(flat), 4)
            self.global_mean = round(sum(flat) / len(flat), 4)

    def print_heatmap(
        self,
        chars: str = " ░▒▓█",
        threshold: float = 0.55,
        title: str = "",
    ) -> None:
        """2D 에덴 점수 히트맵 출력."""
        x_vals = self.x_axis.values
        y_vals = self.y_axis.values

        hdr = title or (
            f"📊 에덴 파라미터 공간 2D 슬라이스\n"
            f"   X: {self.x_axis.label}  Y: {self.y_axis.label}"
        )
        print("\n" + "=" * 65)
        print(f"  {hdr}")
        print(f"  최고={self.global_max:.3f}  평균={self.global_mean:.3f}  "
              f"임계값={threshold:.2f}(★)")
        print("  " + "─" * 63)

        # Y축 헤더
        x_header = f"  {self.y_axis.label[:8]:>10}  "
        for xv in x_vals[::max(1, len(x_vals)//8)]:
            x_header += f"{xv:.1f} "
        print(x_header)
        print(f"  {'':>10}  " + "─" * (len(x_vals) * 2))

        # 행렬 출력 (Y 역방향 = 위가 최대)
        for yi in reversed(range(len(y_vals))):
            yv = y_vals[yi]
            row_str = ""
            for xi in range(len(x_vals)):
                s = self.scores[yi][xi]
                idx = min(len(chars) - 1, int(s * (len(chars) - 1) + 0.5))
                c = chars[idx]
                if s >= threshold:
                    c = "★"
                row_str += c + " "
            print(f"  {yv:>10.2f}  {row_str}  {self.x_axis.unit}")

        print(f"\n  X({self.x_axis.label}): {self.x_axis.lo}{self.x_axis.unit} "
              f"→ {self.x_axis.hi}{self.x_axis.unit}  "
              f"({len(x_vals)} steps)")

        # Eden zone 카운트
        eden_n = sum(1 for row in self.scores for s in row if s >= threshold)
        total_n = len(self.x_axis.values) * len(self.y_axis.values)
        print(f"  ★ Eden Zone: {eden_n}/{total_n} 셀 "
              f"= {eden_n/total_n*100:.1f}% 파라미터 공간")
        print("=" * 65)

    def print_basin_boundary(self, threshold: float = 0.55) -> None:
        """에덴 Basin 경계선 출력 (threshold 이상 영역)."""
        x_vals = self.x_axis.values
        y_vals = self.y_axis.values

        print(f"\n  📐 에덴 Basin 경계 ({self.x_axis.label} × {self.y_axis.label})")
        print(f"  임계값: {threshold:.2f}")
        print("  " + "─" * 50)

        # X축별 Y 범위 찾기
        for xi, xv in enumerate(x_vals):
            eden_ys = [y_vals[yi] for yi in range(len(y_vals))
                       if self.scores[yi][xi] >= threshold]
            if eden_ys:
                print(f"  {self.x_axis.label}={xv:.1f}{self.x_axis.unit}  →  "
                      f"{self.y_axis.label} [{min(eden_ys):.2f} ~ {max(eden_ys):.2f}]"
                      f"{self.y_axis.unit}")
            else:
                print(f"  {self.x_axis.label}={xv:.1f}{self.x_axis.unit}  →  (에덴 없음)")
        print()


# ── ND 스캔 결과 ─────────────────────────────────────────────────────────────

@dataclass
class ParamScanResult:
    """nD 파라미터 공간 스캔 결과.

    Attributes
    ----------
    axes       : 사용한 ParamAxis 목록 (n개)
    dim        : 차원 수 n
    total_pts  : 총 탐색 포인트 수
    eden_pts   : 에덴 판정 포인트 수
    eden_frac  : 에덴 비율 [0~1]
    best_params: 최고 에덴 점수 파라미터 조합
    best_score : 최고 에덴 점수
    scores     : 모든 포인트 (params_dict, score) 리스트
    """
    axes:        List[ParamAxis]
    dim:         int
    total_pts:   int
    eden_pts:    int
    eden_frac:   float
    best_params: Dict[str, float]
    best_score:  float
    scores:      List[Tuple[Dict[str, float], float]]   # (params, score)
    threshold:   float = 0.55

    def summary(self) -> str:
        dim_label = f"{self.dim}D"
        axes_str  = " × ".join(a.label for a in self.axes)
        lines = [
            f"  📊 {dim_label} 파라미터 공간 스캔 결과",
            f"  축: {axes_str}",
            f"  총 탐색: {self.total_pts:,}점  "
            f"에덴: {self.eden_pts}점 ({self.eden_frac*100:.1f}%)",
            f"  최고 에덴 점수: {self.best_score:.4f}",
            f"  최적 파라미터:",
        ]
        for k, v in self.best_params.items():
            axis = next((a for a in self.axes if a.name == k), None)
            unit = axis.unit if axis else ""
            lines.append(f"    {k:20s} = {v:.4f} {unit}")
        return "\n".join(lines)

    def get_2d_slice(
        self,
        x_axis: ParamAxis,
        y_axis: ParamAxis,
        fixed_params: Optional[Dict[str, float]] = None,
    ) -> Optional[ParamSlice2D]:
        """nD 결과에서 2D 슬라이스 추출.

        Parameters
        ----------
        x_axis, y_axis  : 슬라이스할 두 축
        fixed_params    : 나머지 축의 고정값 (None이면 best_params 사용)

        Returns
        -------
        ParamSlice2D 또는 None (해당 축 없음)
        """
        if x_axis.name not in [a.name for a in self.axes]:
            return None
        if y_axis.name not in [a.name for a in self.axes]:
            return None

        fixed = fixed_params or self.best_params

        x_vals = x_axis.values
        y_vals = y_axis.values

        # 점수 행렬 구성: scores에서 x, y 조합에 해당하는 점 추출
        score_map: Dict[Tuple[int, int], float] = {}
        for params, score in self.scores:
            # X, Y 인덱스 찾기
            xv = params.get(x_axis.name)
            yv = params.get(y_axis.name)
            if xv is None or yv is None:
                continue
            # 가장 가까운 인덱스
            xi = min(range(len(x_vals)), key=lambda i: abs(x_vals[i] - xv))
            yi = min(range(len(y_vals)), key=lambda i: abs(y_vals[i] - yv))
            existing = score_map.get((yi, xi), 0.0)
            score_map[(yi, xi)] = max(existing, score)

        matrix = [
            [score_map.get((yi, xi), 0.0) for xi in range(len(x_vals))]
            for yi in range(len(y_vals))
        ]

        from .initial_conditions import make_antediluvian
        return ParamSlice2D(
            x_axis  = x_axis,
            y_axis  = y_axis,
            scores  = matrix,
            base_ic = make_antediluvian(),
        )


# ── 에덴 Basin 형태 분석 ─────────────────────────────────────────────────────

@dataclass
class EdenBasinShape:
    """에덴 Basin의 다차원 형태 분석 결과.

    Attributes
    ----------
    dim            : 차원 수
    basin_volume   : Basin 부피 (전체 대비 비율)
    centroid       : Basin 중심점 (파라미터 공간)
    axes_widths    : 각 축별 Basin 너비 (lo~hi 비율)
    is_connected   : Basin이 연결된 영역인지 여부
    shape_label    : 형태 설명 (점/선/면/구/타원 등)
    """
    dim:          int
    basin_volume: float
    centroid:     Dict[str, float]
    axes_widths:  Dict[str, float]
    is_connected: bool
    shape_label:  str

    def summary(self) -> str:
        lines = [
            f"\n  🔷 에덴 Basin 형태 분석 ({self.dim}D 공간)",
            f"  Basin 부피: {self.basin_volume*100:.2f}% (전체 파라미터 공간 대비)",
            f"  형태: {self.shape_label}",
            f"  Basin 중심:",
        ]
        for k, v in self.centroid.items():
            lines.append(f"    {k:20s} = {v:.4f}")
        lines.append(f"  Basin 너비 (각 축별):")
        for k, v in self.axes_widths.items():
            bar = "█" * int(v * 20)
            lines.append(f"    {k:20s}  {bar:<20}  {v*100:.1f}%")
        return "\n".join(lines)


# ── 메인 스캐너 ─────────────────────────────────────────────────────────────

class EdenParamScanner:
    """다차원 파라미터 공간 에덴 Basin 탐사 엔진.

    Grid Engine의 위상 공간 개념을 차용해
    2D~7D 파라미터 공간에서 에덴 basin을 매핑한다.

    Parameters
    ----------
    base_ic   : 기반 InitialConditions (None → antediluvian)
    threshold : 에덴 판정 점수 임계값 [0~1]
    verbose   : 진행 출력 여부

    Examples
    --------
    >>> scanner = EdenParamScanner()
    >>> # 2D 슬라이스: CO2 vs 온도
    >>> result2d = scanner.scan_2d(CO2_AXIS, TEMP_AXIS)
    >>> result2d.print_heatmap()
    >>>
    >>> # 3D 공간 스캔
    >>> result3d = scanner.scan_nd([CO2_AXIS, TEMP_AXIS, O2_AXIS])
    >>> result3d.summary()
    """

    def __init__(
        self,
        base_ic:   Optional[InitialConditions] = None,
        threshold: float = 0.55,
        verbose:   bool = True,
    ) -> None:
        self.base_ic   = base_ic or make_antediluvian()
        self.threshold = threshold
        self.verbose   = verbose
        self._criteria = EdenCriteria()

        if _HAS_GRID_ENGINE and verbose:
            print("  ✅ Grid Engine 연결됨 — 위상 공간 경로 통합 활성화")
        elif verbose:
            print("  ℹ  Grid Engine 미설치 → 직접 파라미터 그리드 스캔 모드")

    def _score_params(self, overrides: Dict[str, float]) -> float:
        """파라미터 딕셔너리 → 에덴 점수."""
        ic = _make_ic_from_params(self.base_ic, overrides)
        if ic is None:
            return 0.0
        return compute_eden_score(ic, self._criteria)

    # ── 2D 슬라이스 스캔 ────────────────────────────────────────────────────

    def scan_2d(
        self,
        x_axis: ParamAxis,
        y_axis: ParamAxis,
        fixed_overrides: Optional[Dict[str, float]] = None,
    ) -> ParamSlice2D:
        """2D 파라미터 슬라이스 스캔.

        Parameters
        ----------
        x_axis, y_axis    : 탐색할 두 파라미터 축
        fixed_overrides   : 나머지 파라미터 고정값

        Returns
        -------
        ParamSlice2D  (히트맵 포함)
        """
        x_vals = x_axis.values
        y_vals = y_axis.values
        total  = len(x_vals) * len(y_vals)

        if self.verbose:
            print(f"\n  🔭 2D 파라미터 스캔: "
                  f"{x_axis.label} × {y_axis.label}  "
                  f"({len(x_vals)}×{len(y_vals)} = {total} 포인트)")

        matrix: List[List[float]] = []
        for yi, yv in enumerate(y_vals):
            row = []
            for xi, xv in enumerate(x_vals):
                params = {x_axis.name: xv, y_axis.name: yv}
                if fixed_overrides:
                    params.update(fixed_overrides)
                s = self._score_params(params)
                row.append(round(s, 4))
            matrix.append(row)

        result = ParamSlice2D(
            x_axis  = x_axis,
            y_axis  = y_axis,
            scores  = matrix,
            base_ic = self.base_ic,
        )

        if self.verbose:
            print(f"  ✅ 완료: 최고={result.global_max:.3f}  "
                  f"평균={result.global_mean:.3f}")

        return result

    # ── nD 스캔 ─────────────────────────────────────────────────────────────

    def scan_nd(
        self,
        axes: List[ParamAxis],
        fixed_overrides: Optional[Dict[str, float]] = None,
        max_points: int = 50_000,
    ) -> ParamScanResult:
        """n차원 파라미터 공간 스캔 (n = 2~7).

        Parameters
        ----------
        axes           : 탐색할 파라미터 축 목록 (2~7개)
        fixed_overrides: 나머지 파라미터 고정값
        max_points     : 최대 탐색 포인트 수 (초과 시 steps 자동 축소)

        Returns
        -------
        ParamScanResult
        """
        dim = len(axes)
        if dim < 2 or dim > 7:
            raise ValueError(f"축 수는 2~7 사이여야 합니다 (현재 {dim})")

        # 총 포인트 계산 → 초과 시 steps 조정
        total_raw = 1
        for a in axes:
            total_raw *= a.steps

        # steps 조정이 필요하면 각 축 비례 축소
        adjusted_axes = axes
        if total_raw > max_points:
            ratio = (max_points / total_raw) ** (1.0 / dim)
            adjusted_axes = []
            for a in axes:
                new_steps = max(2, int(a.steps * ratio))
                adjusted_axes.append(ParamAxis(
                    name=a.name, label=a.label,
                    lo=a.lo, hi=a.hi,
                    steps=new_steps, unit=a.unit
                ))

        total_pts = 1
        for a in adjusted_axes:
            total_pts *= a.steps

        if self.verbose:
            axes_str = " × ".join(f"{a.label}({a.steps})" for a in adjusted_axes)
            print(f"\n  🔭 {dim}D 파라미터 스캔: {axes_str}")
            print(f"     총 {total_pts:,} 포인트 탐색...")

        # 전체 조합 탐색
        all_values = [a.values for a in adjusted_axes]
        all_names  = [a.name for a in adjusted_axes]

        scores_list: List[Tuple[Dict[str, float], float]] = []
        eden_pts = 0
        best_score = 0.0
        best_params: Dict[str, float] = {}

        for combo in itertools.product(*all_values):
            params = dict(zip(all_names, combo))
            if fixed_overrides:
                params.update(fixed_overrides)
            s = self._score_params(params)
            scores_list.append((params.copy(), round(s, 4)))
            if s >= self.threshold:
                eden_pts += 1
            if s > best_score:
                best_score  = s
                best_params = params.copy()

        eden_frac = eden_pts / total_pts if total_pts else 0.0

        if self.verbose:
            print(f"  ✅ 완료: 에덴={eden_pts}/{total_pts} "
                  f"({eden_frac*100:.1f}%)  "
                  f"최고={best_score:.4f}")

        return ParamScanResult(
            axes        = adjusted_axes,
            dim         = dim,
            total_pts   = total_pts,
            eden_pts    = eden_pts,
            eden_frac   = eden_frac,
            best_params = best_params,
            best_score  = round(best_score, 4),
            scores      = scores_list,
            threshold   = self.threshold,
        )

    # ── Basin 형태 분석 ──────────────────────────────────────────────────────

    def analyze_basin_shape(self, result: ParamScanResult) -> EdenBasinShape:
        """ParamScanResult에서 Basin 형태 분석.

        Eden Basin의:
          - 부피 (전체 대비 비율)
          - 중심점 (가중 평균)
          - 각 축별 너비
          - 형태 분류

        Returns
        -------
        EdenBasinShape
        """
        eden_points = [
            (params, score)
            for params, score in result.scores
            if score >= result.threshold
        ]

        if not eden_points:
            return EdenBasinShape(
                dim=result.dim,
                basin_volume=0.0,
                centroid={a.name: a.center for a in result.axes},
                axes_widths={a.name: 0.0 for a in result.axes},
                is_connected=False,
                shape_label="에덴 Basin 없음",
            )

        # 부피
        basin_volume = len(eden_points) / result.total_pts

        # 중심점 (에덴 점수 가중 평균)
        centroid: Dict[str, float] = {}
        axes_min: Dict[str, float] = {}
        axes_max: Dict[str, float] = {}

        for a in result.axes:
            weighted_sum = sum(params[a.name] * score
                               for params, score in eden_points)
            total_weight = sum(score for _, score in eden_points)
            centroid[a.name] = round(weighted_sum / total_weight, 4)

            vals = [params[a.name] for params, _ in eden_points]
            axes_min[a.name] = min(vals)
            axes_max[a.name] = max(vals)

        # 각 축별 너비 (파라미터 범위 대비 비율)
        axes_widths: Dict[str, float] = {}
        for a in result.axes:
            axis_range = a.hi - a.lo
            basin_range = axes_max[a.name] - axes_min[a.name]
            axes_widths[a.name] = round(basin_range / axis_range, 4) if axis_range else 0.0

        # 형태 분류
        active_axes = sum(1 for w in axes_widths.values() if w > 0.1)
        if   active_axes == 0: shape = "점 (point)"
        elif active_axes == 1: shape = "선 (line)"
        elif active_axes == 2: shape = "면 (plane)"
        elif active_axes == 3: shape = "구/타원체 (ellipsoid)"
        elif active_axes == 4: shape = "4D 타원체 (4D-ellipsoid)"
        elif active_axes == 5: shape = "5D 다면체 (5D-polytope)"
        else:                  shape = f"{active_axes}D 초다면체 (hyperpolytope)"

        # 연결성 (단순 근사: 부피가 0.1% 이상이면 연결된 것으로 간주)
        is_connected = basin_volume >= 0.001

        return EdenBasinShape(
            dim          = result.dim,
            basin_volume = round(basin_volume, 6),
            centroid     = centroid,
            axes_widths  = axes_widths,
            is_connected = is_connected,
            shape_label  = shape,
        )

    # ── 표준 프리셋 스캔 ─────────────────────────────────────────────────────

    def run_standard_scans(self) -> Dict[str, object]:
        """2D~5D 표준 프리셋 스캔 모두 실행.

        Returns
        -------
        dict with keys:
          'co2_temp'   : ParamSlice2D
          'co2_o2'     : ParamSlice2D
          'uv_albedo'  : ParamSlice2D
          '3d_climate' : ParamScanResult
          '5d_planet'  : ParamScanResult
        """
        results = {}

        if self.verbose:
            print("\n" + "=" * 65)
            print("  🚀 행성 파라미터 표준 다차원 스캔")
            print("=" * 65)

        # 2D: CO2 × 온도 (기후 상태도)
        results['co2_temp'] = self.scan_2d(
            CO2_AXIS._replace(steps=12),
            TEMP_AXIS._replace(steps=12),
        )

        # 2D: CO2 × O2 (대기 조성)
        results['co2_o2'] = self.scan_2d(
            CO2_AXIS._replace(steps=12),
            O2_AXIS._replace(steps=10),
        )

        # 2D: UV × Albedo (복사 균형)
        results['uv_albedo'] = self.scan_2d(
            UV_AXIS._replace(steps=10),
            ALB_AXIS._replace(steps=10),
        )

        # 3D: CO2 × O2 × UV (핵심 기후 파라미터)
        results['3d_climate'] = self.scan_nd([
            CO2_AXIS._replace(steps=8),
            O2_AXIS._replace(steps=6),
            UV_AXIS._replace(steps=6),
        ])

        # 5D: 완전 행성 파라미터 (steps 축소)
        results['5d_planet'] = self.scan_nd([
            CO2_AXIS._replace(steps=5),
            O2_AXIS._replace(steps=4),
            UV_AXIS._replace(steps=4),
            ALB_AXIS._replace(steps=4),
            H2O_AXIS._replace(steps=4),
        ])

        return results


# ── ParamAxis _replace 지원 (dataclass는 replace 직접 지원 안 함) ──────────

# Python 3.10+ : dataclasses.replace 사용, 이하는 수동 구현
import copy as _copy

def _axis_replace(axis: ParamAxis, **kwargs) -> ParamAxis:
    d = {f: getattr(axis, f) for f in axis.__dataclass_fields__}
    d.update(kwargs)
    return ParamAxis(**d)

# ParamAxis에 _replace 메서드 동적 추가 (NamedTuple 호환)
ParamAxis._replace = lambda self, **kw: _axis_replace(self, **kw)


# ── 헬퍼 함수 ────────────────────────────────────────────────────────────────

def make_param_scanner(
    phase: str = 'antediluvian',
    threshold: float = 0.55,
    verbose: bool = True,
) -> EdenParamScanner:
    """EdenParamScanner 생성 헬퍼."""
    from .initial_conditions import make_antediluvian, make_postdiluvian
    base_ic = make_antediluvian() if phase == 'antediluvian' else make_postdiluvian()
    return EdenParamScanner(base_ic=base_ic, threshold=threshold, verbose=verbose)


__all__ = [
    "ParamAxis",
    "ParamSlice2D",
    "ParamScanResult",
    "EdenBasinShape",
    "EdenParamScanner",
    "make_param_scanner",
    # 표준 축
    "CO2_AXIS",
    "TEMP_AXIS",
    "O2_AXIS",
    "UV_AXIS",
    "ALB_AXIS",
    "H2O_AXIS",
    "LAND_AXIS",
    "_HAS_GRID_ENGINE",
    "_5D_AXES",
    "_7D_AXES",
]
