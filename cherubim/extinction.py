"""extinction.py — 궁창 붕괴 전이 곡선 & 대멸종 시뮬레이터

설계 철학:
  "대멸종은 독립된 사건이 아니라, firmament_integrity 곡선 위의 임계점들이다."

이 모듈은 두 가지 질문에 답한다:
  1. 궁창이 서서히 무너질 때 환경 변수가 어떻게 변하는가?
     → FirmamentDecayEngine (firmament_integrity: 1.0 → 0.0)
  2. 실제 지질 대멸종 이벤트와 궁창 붕괴 곡선이 어디서 겹치는가?
     → ExtinctionMapper (지질 이벤트 프록시 기능 매핑)

핵심 파라미터:
  firmament_integrity  : 궁창 완전도 [0.0 ~ 1.0]
                          1.0 = 에덴 초기 상태 (완전 활성)
                          0.5 = 절반 손상 (데본기/페름기 스트레스 추정)
                          0.0 = 완전 붕괴 (대홍수 이후)

지질 이벤트 프록시 (Geological Event Proxy):
  각 대멸종을 firmament 기능 변수로 기능적으로 매핑한다.
  (시간축 동일화가 목적이 아닌, 물리 메커니즘 유사성 매핑)

  Snowball Earth  → firmament_integrity ≈ 0.0 (궁창 이전 상태)
  Cambrian Exp.   → firmament_integrity ≈ 1.0 (궁창 가동 → 생명 폭발)
  End-Ordovician  → integrity ≈ 0.75 (1차 교란)
  Late Devonian   → integrity ≈ 0.60 (식물 CO2 흡수 → 캐노피 스트레스)
  End-Permian     → integrity ≈ 0.30 (화산 → 캐노피 화학적 공격)
  End-Triassic    → integrity ≈ 0.20 (판게아 분열 연동)
  K-Pg            → integrity ≈ 0.05 (충돌 → 물리적 파괴)
  Post-Flood      → integrity = 0.00 (완전 소멸)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ── 환경 변수 곡선 상수 ─────────────────────────────────────────────────────────

# 에덴 상태 (integrity=1.0)
_EDEN = {
    'pole_eq_delta_K': 15.0,   # 극-적도 온도차 (K)
    'UV_shield':       0.95,   # UV 차폐율
    'mutation_factor': 0.01,   # 돌연변이율 배수
    'pressure_atm':    1.25,   # 대기압
    'albedo':          0.20,   # 알베도
    'ice_fraction':    0.00,   # 빙하 비율
    'precip_mode':     'mist', # 강수 모드
    'T_bias_pole_C':   -15.0,  # 극지 온도 편차 (°C)
    'gpp_polar':       0.40,   # 극지 GPP
    'lifespan_factor': 10.0,   # 수명 배수 (에덴 기준)
    'body_size_factor':1.8,    # 체형 배수
}

# 현재 상태 (integrity=0.0)
_NOW = {
    'pole_eq_delta_K': 48.0,
    'UV_shield':       0.00,
    'mutation_factor': 1.00,
    'pressure_atm':    1.00,
    'albedo':          0.306,
    'ice_fraction':    0.03,
    'precip_mode':     'rain',
    'T_bias_pole_C':   -40.0,
    'gpp_polar':       0.10,
    'lifespan_factor': 1.0,
    'body_size_factor':1.0,
}


# ── 임계값 (Threshold) 정의 ─────────────────────────────────────────────────────

# firmament_integrity가 이 값 이하로 떨어질 때 각 현상 발생
THRESHOLD_UV_DAMAGE    = 0.80  # UV 차폐 약화 → 피부암/돌연변이 증가
THRESHOLD_POLAR_COLD   = 0.65  # 극지 냉각 가시화 → 빙하 씨앗
THRESHOLD_SEASON_START = 0.55  # 계절 효과 발현 (자전축 효과 노출)
THRESHOLD_ICE_SHEET    = 0.40  # 극지 빙상 형성 시작
THRESHOLD_MASS_EXT1    = 0.30  # 1차 대멸종급 환경 스트레스
THRESHOLD_RAIN_START   = 0.25  # 강수 모드 전환 (mist → rain)
THRESHOLD_MASS_EXT2    = 0.10  # 2차 대멸종급 (거의 붕괴)
THRESHOLD_COLLAPSE     = 0.05  # 사실상 완전 붕괴


# ── 궁창 붕괴 상태 스냅샷 ──────────────────────────────────────────────────────

@dataclass
class FirmamentSnapshot:
    """특정 firmament_integrity 값에서의 환경 상태."""

    integrity: float              # 궁창 완전도 [0~1]

    # ── 환경 변수 ──
    pole_eq_delta_K: float        # 극-적도 온도차 (K)
    UV_shield:       float        # UV 차폐율
    mutation_factor: float        # 돌연변이율 배수
    pressure_atm:    float        # 대기압 (atm)
    albedo:          float        # 알베도
    ice_fraction:    float        # 빙하 면적 비율
    precip_mode:     str          # 강수 모드
    T_bias_pole_C:   float        # 극지 온도 편차 (°C)
    gpp_polar:       float        # 극지 GPP
    lifespan_factor: float        # 수명 배수
    body_size_factor:float        # 체형 배수

    # ── 임계값 돌파 플래그 ──
    flags: Dict[str, bool] = field(default_factory=dict)

    # ── 종합 에덴 점수 ──
    eden_index: float = 0.0       # [0~1] 에덴 환경 품질

    def __post_init__(self) -> None:
        self._compute_flags()
        self._compute_eden_index()

    def _compute_flags(self) -> None:
        g = self.integrity
        self.flags = {
            'UV_damage_start':   g <= THRESHOLD_UV_DAMAGE,
            'polar_cold_start':  g <= THRESHOLD_POLAR_COLD,
            'season_exposed':    g <= THRESHOLD_SEASON_START,
            'ice_sheet_forming': g <= THRESHOLD_ICE_SHEET,
            'mass_extinction_1': g <= THRESHOLD_MASS_EXT1,
            'rain_mode':         g <= THRESHOLD_RAIN_START,
            'mass_extinction_2': g <= THRESHOLD_MASS_EXT2,
            'near_collapse':     g <= THRESHOLD_COLLAPSE,
            'fully_active':      g >= 0.95,
        }

    def _compute_eden_index(self) -> None:
        """환경 변수 → 에덴 품질 종합 점수 [0~1]."""
        uv_score  = self.UV_shield
        mut_score = 1.0 - min(1.0, (self.mutation_factor - 0.01) / 0.99)
        ice_score = 1.0 - min(1.0, self.ice_fraction / 0.03)
        T_score   = 1.0 - min(1.0, abs(self.T_bias_pole_C + 15.0) / 25.0)
        gpp_score = min(1.0, self.gpp_polar / 0.40)
        self.eden_index = round(
            uv_score  * 0.25 +
            mut_score * 0.25 +
            ice_score * 0.20 +
            T_score   * 0.15 +
            gpp_score * 0.15,
            4
        )

    def summary(self) -> str:
        lines = [
            f"  firmament_integrity = {self.integrity:.2f}",
            f"  eden_index          = {self.eden_index:.3f}",
            f"  pole_eq_delta       = {self.pole_eq_delta_K:.1f} K",
            f"  UV_shield           = {self.UV_shield:.3f}",
            f"  mutation_factor     = {self.mutation_factor:.3f}x",
            f"  pressure            = {self.pressure_atm:.3f} atm",
            f"  albedo              = {self.albedo:.3f}",
            f"  ice_fraction        = {self.ice_fraction:.4f}",
            f"  precip_mode         = {self.precip_mode}",
            f"  T_bias_pole         = {self.T_bias_pole_C:.1f} °C",
            f"  lifespan_factor     = {self.lifespan_factor:.2f}x",
            f"  body_size_factor    = {self.body_size_factor:.2f}x",
        ]
        active_flags = [k for k, v in self.flags.items() if v]
        if active_flags:
            lines.append(f"  ⚠  flags: {', '.join(active_flags)}")
        return "\n".join(lines)


# ── 전이 곡선 엔진 ──────────────────────────────────────────────────────────────

class FirmamentDecayEngine:
    """궁창 완전도(firmament_integrity) 전이 곡선 엔진.

    integrity 1.0(에덴) → 0.0(홍수 이후) 사이의 임의 값에서
    환경 변수를 interpolation + 비선형 보정으로 계산한다.

    각 변수는 integrity에 대해 다른 곡선을 따른다:
      - UV_shield      : 선형 감소 (캐노피 두께 비례)
      - mutation_factor: 지수 증가 (UV 노출의 비선형 효과)
      - pole_eq_delta  : S자 곡선 (임계점 전후 급변)
      - ice_fraction   : 계단 + 지수 (임계값 이하에서 급증)
      - T_bias_pole    : S자 곡선 (균온→냉각 전환점 존재)

    Parameters
    ----------
    decay_curve : str
        'linear'    : 모든 변수 선형 보간
        'physical'  : 각 변수별 물리 기반 비선형 곡선 (기본)
        'instant'   : 계단 함수 (임계값 즉시 전환)
    """

    def __init__(self, decay_curve: str = 'physical') -> None:
        self.decay_curve = decay_curve

    def at(self, integrity: float) -> FirmamentSnapshot:
        """특정 integrity 값에서의 FirmamentSnapshot 반환."""
        g = max(0.0, min(1.0, integrity))

        if self.decay_curve == 'linear':
            snap = self._linear(g)
        elif self.decay_curve == 'instant':
            snap = self._instant(g)
        else:
            snap = self._physical(g)

        return snap

    def scan(
        self,
        steps: int = 20,
        start: float = 1.0,
        end: float = 0.0,
    ) -> List[FirmamentSnapshot]:
        """integrity 범위를 steps 단계로 스캔해 스냅샷 목록 반환."""
        snaps = []
        for i in range(steps + 1):
            g = start + (end - start) * i / steps
            snaps.append(self.at(g))
        return snaps

    def print_transition_table(
        self,
        steps: int = 20,
        show_flags: bool = True,
    ) -> None:
        """궁창 붕괴 전이 테이블 출력."""
        snaps = self.scan(steps=steps)
        width = 110

        print("=" * width)
        print("  🌊 궁창 붕괴 전이 곡선 (FirmamentDecayEngine)")
        print(f"  curve='{self.decay_curve}'  steps={steps}")
        print("  " + "─" * (width - 4))
        print(
            f"  {'integrity':>9}  {'eden_idx':>8}  "
            f"{'UV_shield':>9}  {'mut_x':>6}  "
            f"{'pole_dT':>7}  {'ice%':>5}  "
            f"{'T_pole':>7}  {'life_x':>6}  "
            f"{'precip':<8}  이벤트"
        )
        print("  " + "─" * (width - 4))

        prev_flags: Dict[str, bool] = {}
        for s in snaps:
            new_flags = [k for k, v in s.flags.items()
                         if v and not prev_flags.get(k, False)]
            flag_str = ""
            if show_flags and new_flags:
                flag_str = "  ← " + ", ".join(new_flags)

            bar = "█" * int(s.integrity * 20)
            print(
                f"  {s.integrity:>9.2f}  {s.eden_index:>8.3f}  "
                f"{s.UV_shield:>9.3f}  {s.mutation_factor:>6.3f}  "
                f"{s.pole_eq_delta_K:>7.1f}  {s.ice_fraction*100:>5.2f}  "
                f"{s.T_bias_pole_C:>7.1f}  {s.lifespan_factor:>6.2f}  "
                f"{s.precip_mode:<8}{flag_str}"
            )
            prev_flags = dict(s.flags)

        print("=" * width)

    # ── 곡선 구현 ──────────────────────────────────────────────────────────────

    def _lerp(self, a: float, b: float, t: float) -> float:
        t = max(0.0, min(1.0, t))
        return a + (b - a) * t

    def _sigmoid(self, x: float, center: float = 0.5, steepness: float = 10.0) -> float:
        """S자 곡선: x < center → 에덴값, x > center → 현재값."""
        z = (x - center) * steepness
        return 1.0 / (1.0 + math.exp(z))  # 0(현재)→1(에덴) 방향

    def _linear(self, g: float) -> FirmamentSnapshot:
        """단순 선형 보간."""
        def L(key): return self._lerp(_NOW[key], _EDEN[key], g)
        return FirmamentSnapshot(
            integrity        = g,
            pole_eq_delta_K  = L('pole_eq_delta_K'),
            UV_shield        = L('UV_shield'),
            mutation_factor  = L('mutation_factor'),
            pressure_atm     = L('pressure_atm'),
            albedo           = L('albedo'),
            ice_fraction     = L('ice_fraction'),
            precip_mode      = 'mist' if g > 0.25 else 'rain',
            T_bias_pole_C    = L('T_bias_pole_C'),
            gpp_polar        = L('gpp_polar'),
            lifespan_factor  = L('lifespan_factor'),
            body_size_factor = L('body_size_factor'),
        )

    def _physical(self, g: float) -> FirmamentSnapshot:
        """물리 기반 비선형 전이 곡선.

        각 변수의 물리적 특성에 맞게 다른 곡선 사용:
          UV_shield      : 선형 (캐노피 두께 직접 비례)
          mutation_factor: 지수 (UV 제곱 비례, 비선형 손상)
          pole_eq_delta  : S자 (임계점 전후 급변 — 궁창 임계 붕괴)
          ice_fraction   : 계단+지수 (임계값 이하에서만 급증)
          T_bias_pole    : S자 (균온→냉각 전환)
          lifespan       : 지수 감소 (돌연변이 누적 비선형)
        """
        # UV 차폐: 선형
        UV = g * _EDEN['UV_shield']

        # 돌연변이: 지수 (UV 손상 비선형 — UV 반감 → 돌연변이 4배)
        # g=1: 0.01, g=0: 1.0
        mut = 0.01 * math.exp((1.0 - g) * math.log(100.0))

        # 극-적도 온도차: S자 (0.55 임계점에서 급변)
        # g=1.0(에덴)→15K, g=0.0(현재)→48K
        # p = g가 커질수록 에덴값에 가까워짐
        def s_curve(x, c=0.5, k=8.0):
            """x가 클수록 1에 가까운 S자 [0~1]."""
            return 1.0 / (1.0 + math.exp(-k * (x - c)))
        pole_dT = _NOW['pole_eq_delta_K'] + (
            (_EDEN['pole_eq_delta_K'] - _NOW['pole_eq_delta_K'])
            * s_curve(g, c=0.55, k=8.0)
        )

        # 빙하: 임계값(0.40) 이하에서 지수 증가
        if g > THRESHOLD_ICE_SHEET:
            ice = 0.0
        else:
            # 0.40 → 0.0 구간에서 0.0 → 0.03 지수 증가
            p_ice = (THRESHOLD_ICE_SHEET - g) / THRESHOLD_ICE_SHEET
            ice = 0.03 * (p_ice ** 1.5)

        # 대기압: 선형 (캐노피 수증기 비례)
        pressure = self._lerp(_NOW['pressure_atm'], _EDEN['pressure_atm'], g)

        # 알베도: 선형 (빙하 없을 때 낮음)
        albedo = self._lerp(_NOW['albedo'], _EDEN['albedo'], g)

        # 극지 온도 편차: S자 (균온→냉각 전환)
        # g=1.0(에덴)→-15°C, g=0.0(현재)→-40°C
        T_bias = _NOW['T_bias_pole_C'] + (
            (_EDEN['T_bias_pole_C'] - _NOW['T_bias_pole_C'])
            * s_curve(g, c=0.60, k=9.0)
        )

        # 극지 GPP: S자 (온도+수분 동시 의존)
        # g=1.0(에덴)→0.40, g=0.0(현재)→0.10
        gpp_polar = _NOW['gpp_polar'] + (
            (_EDEN['gpp_polar'] - _NOW['gpp_polar'])
            * s_curve(g, c=0.50, k=7.0)
        )

        # 수명: 지수 감소 (돌연변이 비선형 누적)
        lifespan = max(1.0, _EDEN['lifespan_factor'] * (g ** 1.8))

        # 체형: 대기압+O2 연동 (선형)
        body = self._lerp(_NOW['body_size_factor'], _EDEN['body_size_factor'], g)

        # 강수 모드
        if g > 0.35:
            precip = 'mist'
        elif g > 0.15:
            precip = 'drizzle'
        else:
            precip = 'rain'

        return FirmamentSnapshot(
            integrity        = g,
            pole_eq_delta_K  = round(pole_dT, 2),
            UV_shield        = round(UV, 3),
            mutation_factor  = round(mut, 4),
            pressure_atm     = round(pressure, 3),
            albedo           = round(albedo, 3),
            ice_fraction     = round(ice, 5),
            precip_mode      = precip,
            T_bias_pole_C    = round(T_bias, 2),
            gpp_polar        = round(gpp_polar, 3),
            lifespan_factor  = round(lifespan, 2),
            body_size_factor = round(body, 3),
        )

    def _instant(self, g: float) -> FirmamentSnapshot:
        """계단 함수 — 임계값에서 즉시 전환."""
        is_eden = g >= 0.5
        return FirmamentSnapshot(
            integrity        = g,
            pole_eq_delta_K  = _EDEN['pole_eq_delta_K'] if is_eden else _NOW['pole_eq_delta_K'],
            UV_shield        = _EDEN['UV_shield'] if is_eden else _NOW['UV_shield'],
            mutation_factor  = _EDEN['mutation_factor'] if is_eden else _NOW['mutation_factor'],
            pressure_atm     = _EDEN['pressure_atm'] if is_eden else _NOW['pressure_atm'],
            albedo           = _EDEN['albedo'] if is_eden else _NOW['albedo'],
            ice_fraction     = 0.0 if is_eden else _NOW['ice_fraction'],
            precip_mode      = _EDEN['precip_mode'] if is_eden else _NOW['precip_mode'],
            T_bias_pole_C    = _EDEN['T_bias_pole_C'] if is_eden else _NOW['T_bias_pole_C'],
            gpp_polar        = _EDEN['gpp_polar'] if is_eden else _NOW['gpp_polar'],
            lifespan_factor  = _EDEN['lifespan_factor'] if is_eden else _NOW['lifespan_factor'],
            body_size_factor = _EDEN['body_size_factor'] if is_eden else _NOW['body_size_factor'],
        )


# ── 지질 이벤트 프록시 매핑 ─────────────────────────────────────────────────────

@dataclass
class ExtinctionEvent:
    """단일 지질 대멸종 이벤트 + 궁창 기능 매핑."""

    name:            str    # 이벤트 이름
    ma:              float  # 연대 (Ma, 백만년 전)
    extinction_pct:  float  # 종 멸종율 (%)
    geo_cause:       str    # 지질학적 원인 (주류 과학)
    firmament_proxy: float  # 기능적 firmament_integrity 추정값 [0~1]
    mechanism:       str    # 궁창 관점 메커니즘
    snap:            Optional[FirmamentSnapshot] = None  # 계산된 상태

    def __str__(self) -> str:
        bar = "█" * int(self.firmament_proxy * 20)
        bar += "░" * (20 - int(self.firmament_proxy * 20))
        return (
            f"  [{self.ma:>7.1f} Ma]  {self.name:<28}  "
            f"멸종={self.extinction_pct:>5.1f}%  "
            f"FI={self.firmament_proxy:.2f}  |{bar}|"
        )


# 지질 이벤트 사전 정의
GEOLOGICAL_EVENTS: List[ExtinctionEvent] = [
    ExtinctionEvent(
        name           = "Snowball Earth (Sturtian)",
        ma             = 717.0,
        extinction_pct = 60.0,  # 에디아카라 이전 — 추정
        geo_cause      = "전구적 빙하 (원인 불명)",
        firmament_proxy= 0.00,
        mechanism      = "궁창 이전 상태 — 보호막 없음, 전 지구 빙결",
    ),
    ExtinctionEvent(
        name           = "Cambrian Explosion",
        ma             = 541.0,
        extinction_pct = 0.0,   # 멸종이 아닌 폭발적 생성
        geo_cause      = "산소 급증, 눈덩이 지구 이후 영양 공급",
        firmament_proxy= 1.00,
        mechanism      = "궁창 가동 → UV차폐+균온+안개 → 생명 폭발",
    ),
    ExtinctionEvent(
        name           = "End-Ordovician",
        ma             = 443.0,
        extinction_pct = 85.0,
        geo_cause      = "히르난트 빙하기 (Gondwana 빙상) + 해양 무산소",
        firmament_proxy= 0.75,
        mechanism      = "1차 궁창 교란 — 극지 냉각 시작, UV 부분 노출",
    ),
    ExtinctionEvent(
        name           = "Late Devonian",
        ma             = 372.0,
        extinction_pct = 75.0,
        geo_cause      = "육상식물 CO2 흡수 → 해양 무산소",
        firmament_proxy= 0.60,
        mechanism      = "식물 진화로 CO2 급감 → 캐노피 탄소 균형 교란",
    ),
    ExtinctionEvent(
        name           = "End-Permian (Great Dying)",
        ma             = 251.9,
        extinction_pct = 96.0,
        geo_cause      = "시베리아 트랩 화산 (CO2+SO2+할로겐)",
        firmament_proxy= 0.30,
        mechanism      = "화산 화학물질 → 캐노피 화학적 공격 → 대부분 붕괴",
    ),
    ExtinctionEvent(
        name           = "End-Triassic",
        ma             = 201.5,
        extinction_pct = 76.0,
        geo_cause      = "CAMP 화산 (판게아 분열)",
        firmament_proxy= 0.20,
        mechanism      = "대륙 분열 → 지하수 노출 → 잔존 캐노피 추가 손상",
    ),
    ExtinctionEvent(
        name           = "K-Pg (Chicxulub Impact)",
        ma             = 66.0,
        extinction_pct = 76.0,
        geo_cause      = "칙술루브 소행성 충돌 (직경 10km)",
        firmament_proxy= 0.05,
        mechanism      = "충돌 에너지 → 수증기층 물리적 파괴 → 사실상 완전 붕괴",
    ),
    ExtinctionEvent(
        name           = "Quaternary Glaciation",
        ma             = 2.6,
        extinction_pct = 5.0,   # 대형 포유류 중심
        geo_cause      = "파나마 지협 형성 → 해양 순환 변화",
        firmament_proxy= 0.00,
        mechanism      = "궁창 완전 소멸 상태 고착 → 현재 빙하기 체제",
    ),
]


class ExtinctionMapper:
    """지질 대멸종 이벤트 × 궁창 붕괴 곡선 매핑 분석기.

    FirmamentDecayEngine과 지질 이벤트 프록시를 결합해
    각 대멸종 시점의 궁창 상태를 계산하고 비교한다.

    Parameters
    ----------
    engine : FirmamentDecayEngine
        전이 곡선 엔진. None이면 'physical' 곡선으로 생성.
    events : list[ExtinctionEvent]
        분석할 이벤트 목록. None이면 GEOLOGICAL_EVENTS 전체 사용.
    """

    def __init__(
        self,
        engine: Optional[FirmamentDecayEngine] = None,
        events: Optional[List[ExtinctionEvent]] = None,
    ) -> None:
        self.engine = engine or FirmamentDecayEngine('physical')
        self.events = events or list(GEOLOGICAL_EVENTS)
        self._compute_snaps()

    def _compute_snaps(self) -> None:
        for ev in self.events:
            ev.snap = self.engine.at(ev.firmament_proxy)

    def print_timeline(self) -> None:
        """시간 역순 타임라인 출력 (오래된 것 → 최근 순)."""
        width = 100
        print("=" * width)
        print("  🌍 대멸종 × 궁창 붕괴 타임라인 매핑")
        print(f"  curve='{self.engine.decay_curve}'")
        print("  " + "─" * (width - 4))
        print(
            f"  {'연대(Ma)':>9}  {'이벤트':^28}  "
            f"{'멸종율':>6}  {'FI':>4}  "
            f"{'UV':>5}  {'돌연변이':>8}  {'극온도차':>8}  {'에덴지수':>8}"
        )
        print("  " + "─" * (width - 4))

        for ev in sorted(self.events, key=lambda e: e.ma, reverse=True):
            s = ev.snap
            if s is None:
                continue
            marker = "💥" if ev.extinction_pct >= 80 else (
                      "⚠ " if ev.extinction_pct >= 50 else (
                      "🌱" if ev.extinction_pct == 0 else "▪ "))
            print(
                f"  {ev.ma:>9.1f}  {marker}{ev.name:<27}  "
                f"{ev.extinction_pct:>5.1f}%  {ev.firmament_proxy:>4.2f}  "
                f"{s.UV_shield:>5.3f}  {s.mutation_factor:>8.3f}  "
                f"{s.pole_eq_delta_K:>8.1f}K  {s.eden_index:>8.3f}"
            )
        print("=" * width)

    def print_mechanism_analysis(self) -> None:
        """각 이벤트의 궁창 메커니즘 상세 분석 출력."""
        width = 100
        print("\n" + "=" * width)
        print("  🔬 대멸종 원인 × 궁창 메커니즘 분석")
        print("  " + "─" * (width - 4))

        for ev in sorted(self.events, key=lambda e: e.ma, reverse=True):
            if ev.snap is None:
                continue
            print(f"\n  ▶ {ev.name}  [{ev.ma} Ma]  멸종율={ev.extinction_pct}%")
            print(f"    지질 원인   : {ev.geo_cause}")
            print(f"    궁창 메커니즘: {ev.mechanism}")
            print(f"    FI={ev.firmament_proxy:.2f}  →  {ev.snap.summary()}")

        print("\n" + "=" * width)

    def find_critical_transitions(self) -> List[Tuple[str, float, float]]:
        """임계값 돌파 이벤트 목록 반환.

        Returns
        -------
        list of (임계값 이름, 돌파 시점 FI, 해당 멸종율)
        """
        thresholds = {
            'UV_damage_start':   THRESHOLD_UV_DAMAGE,
            'polar_cold_start':  THRESHOLD_POLAR_COLD,
            'season_exposed':    THRESHOLD_SEASON_START,
            'ice_sheet_forming': THRESHOLD_ICE_SHEET,
            'mass_extinction_1': THRESHOLD_MASS_EXT1,
            'rain_mode':         THRESHOLD_RAIN_START,
            'mass_extinction_2': THRESHOLD_MASS_EXT2,
            'near_collapse':     THRESHOLD_COLLAPSE,
        }
        results = []
        for name, fi_val in thresholds.items():
            # 이 임계값에 가장 가까운 이벤트 찾기
            closest = min(
                self.events,
                key=lambda e: abs(e.firmament_proxy - fi_val)
            )
            results.append((name, fi_val, closest.extinction_pct))
        return results

    def eden_index_curve(self, steps: int = 10) -> List[Tuple[float, float]]:
        """integrity → eden_index 곡선 [(fi, eden_idx), ...]."""
        return [
            (s.integrity, s.eden_index)
            for s in self.engine.scan(steps=steps)
        ]

    def print_eden_curve(self, steps: int = 20) -> None:
        """에덴 지수 곡선 ASCII 바 차트."""
        print("\n  📉 firmament_integrity → eden_index 곡선")
        print("  " + "─" * 60)
        for s in self.engine.scan(steps=steps):
            bar = "█" * int(s.eden_index * 30)
            flags = [k for k, v in s.flags.items() if v and k != 'fully_active']
            flag_str = f"  ← {flags[0]}" if flags else ""
            print(
                f"  FI={s.integrity:.2f}  {bar:<30}  "
                f"{s.eden_index:.3f}{flag_str}"
            )
        print()


# ── 헬퍼 함수 ──────────────────────────────────────────────────────────────────

def make_extinction_mapper(
    curve: str = 'physical',
) -> ExtinctionMapper:
    """ExtinctionMapper 팩토리."""
    engine = FirmamentDecayEngine(decay_curve=curve)
    return ExtinctionMapper(engine=engine)


def quick_extinction_analysis(curve: str = 'physical') -> ExtinctionMapper:
    """빠른 전체 분석 실행 + 출력."""
    mapper = make_extinction_mapper(curve)
    mapper.print_timeline()
    mapper.print_eden_curve()
    return mapper


__all__ = [
    # 스냅샷
    "FirmamentSnapshot",
    # 전이 곡선 엔진
    "FirmamentDecayEngine",
    # 이벤트 & 매핑
    "ExtinctionEvent",
    "ExtinctionMapper",
    "GEOLOGICAL_EVENTS",
    # 임계값 상수
    "THRESHOLD_UV_DAMAGE",
    "THRESHOLD_POLAR_COLD",
    "THRESHOLD_SEASON_START",
    "THRESHOLD_ICE_SHEET",
    "THRESHOLD_MASS_EXT1",
    "THRESHOLD_RAIN_START",
    "THRESHOLD_MASS_EXT2",
    "THRESHOLD_COLLAPSE",
    # 환경 상수
    "_EDEN",
    "_NOW",
    # 팩토리
    "make_extinction_mapper",
    "quick_extinction_analysis",
]
