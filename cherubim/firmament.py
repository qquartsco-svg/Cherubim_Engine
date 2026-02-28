"""firmament.py — 궁창(Raqia) 레이어

창세기 1:6-7: "하나님이 궁창을 만드사 궁창 위의 물과 궁창 아래의 물로 나뉘게 하시니라"

역할:
  - 대기 상층 수증기 캐노피(H2O_canopy)의 물리 효과를 AtmosphereColumn에 주입
  - 궁창이 활성(firmament_active=True)이면 에덴 환경 파라미터 적용
  - 궁창이 붕괴(collapse)되면 대홍수 이벤트로 전이

물리 효과 (궁창 활성 시):
  1. 추가 온실효과:   H2O_canopy → τ 증가 → T_surface 상승
  2. UV 차폐:        uv_shield_factor = 1 - H2O_canopy / 0.10
  3. 강수 모드:       'mist' (안개) — 강우 없음 (창2:6)
  4. 알베도 감소:     빙하·구름 없음 → albedo ~0.20
  5. 온도 균등화:     극적도 온도차 억제 (pole_eq_delta ↓)
  6. 대기압 증가:     P_surface_atm ≈ 1.0 + H2O_canopy * 5

붕괴 조건 (FirmamentState.collapse_triggered):
  - 외부에서 trigger_flood() 호출 시 즉시 붕괴
  - 또는 누적 스트레스가 임계값 초과 시 자동 붕괴 (선택적)

단위: SI
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional


# ── 궁창 단계 타입 ──────────────────────────────────────────
PhaseType = Literal['antediluvian', 'flood', 'postdiluvian']
PrecipMode = Literal['mist', 'drizzle', 'rain', 'none']


# ── 보정 상수 ───────────────────────────────────────────────
_H2O_CANOPY_EDEN     = 0.05   # 에덴 초기 H2O 캐노피 비율
_H2O_CANOPY_MIN      = 0.00   # 붕괴 후
_ALBEDO_EDEN         = 0.20   # 빙하 없음
_ALBEDO_POSTFLOOD    = 0.306  # 현재 지구
_POLE_EQ_DELTA_EDEN  = 15.0  # K — 에덴: 극적도 온도차 작음
_POLE_EQ_DELTA_NOW   = 48.0  # K — 현재: 극적도 온도차 큼
_MUTATION_FACTOR_EDEN= 0.01  # 에덴: 돌연변이율 기본의 1%
_MUTATION_FACTOR_NOW = 1.00  # 현재: 정상


@dataclass
class FirmamentState:
    """궁창의 현재 물리 상태."""

    # ── 핵심 파라미터 ──
    phase: PhaseType = 'antediluvian'       # 현재 시대 단계
    H2O_canopy: float = _H2O_CANOPY_EDEN   # 상층 수증기 비율 [0~0.10]
    albedo_override: Optional[float] = None # None이면 자동 계산
    precip_mode: PrecipMode = 'mist'        # 강수 방식

    # ── 파생 상태 ──
    active: bool = True                     # 궁창 존재 여부
    collapse_triggered: bool = False        # 대홍수 트리거

    # ── 누적 ──
    years_elapsed: float = 0.0
    collapse_year: Optional[float] = None

    # ── 효과값 (step() 후 갱신) ──
    uv_shield_factor: float = 0.95          # 0=차폐없음, 1=완전차폐
    mutation_rate_factor: float = _MUTATION_FACTOR_EDEN
    pressure_atm: float = 1.25             # 대기압 (1.0=현재)
    pole_eq_delta_K: float = _POLE_EQ_DELTA_EDEN
    albedo: float = _ALBEDO_EDEN
    delta_tau: float = 0.0                 # 궁창이 추가하는 광학 깊이


@dataclass
class FloodEvent:
    """대홍수 이벤트 결과 스냅샷."""
    trigger_year: float = 0.0
    H2O_released: float = 0.0             # 대기에서 방출된 H2O 비율
    sea_level_rise_m: float = 0.0         # 해수면 상승 추정 (m)
    f_land_change: float = 0.0            # 대륙 비율 변화 (음수)
    albedo_jump: float = 0.0              # 알베도 급변
    T_drop_K: float = 0.0                 # 홍수 후 냉각량
    uv_shield_lost: float = 0.0           # UV 차폐 소실량
    mutation_rate_jump: float = 0.0       # 돌연변이율 변화 배수


class FirmamentLayer:
    """궁창 레이어 — AtmosphereColumn에 주입되는 환경 수정자.

    사용법:
        fl = FirmamentLayer()              # 에덴 초기 상태
        env = fl.get_env_overrides()       # dict → PlanetRunner에 주입
        fl.step(dt_yr=1.0)
        fl.trigger_flood()                 # 대홍수 이벤트
        event = fl.flood_event             # 결과 조회

    Parameters
    ----------
    initial_H2O_canopy : float
        초기 수증기 캐노피 비율. 에덴 기본값 = 0.05 (5%).
    decay_rate_per_yr : float
        캐노피 자연 소멸 속도 [/yr]. 0이면 홍수 때만 붕괴.
    """

    def __init__(
        self,
        initial_H2O_canopy: float = _H2O_CANOPY_EDEN,
        decay_rate_per_yr: float = 0.0,
    ) -> None:
        self.state = FirmamentState(H2O_canopy=initial_H2O_canopy)
        self._decay_rate = decay_rate_per_yr
        self.flood_event: Optional[FloodEvent] = None
        self._update_derived()

    # ── 공개 메서드 ────────────────────────────────────────

    def step(self, dt_yr: float = 1.0) -> FirmamentState:
        """시간 진행. 자연 소멸 + 붕괴 처리."""
        s = self.state
        s.years_elapsed += dt_yr

        if s.active and self._decay_rate > 0:
            s.H2O_canopy = max(0.0, s.H2O_canopy - self._decay_rate * dt_yr)
            if s.H2O_canopy < 1e-4:
                self._do_collapse()

        if s.collapse_triggered and s.active:
            self._do_collapse()

        self._update_derived()
        return s

    def trigger_flood(self) -> FloodEvent:
        """외부에서 대홍수 이벤트를 강제 발동."""
        self.state.collapse_triggered = True
        self._do_collapse()
        self._update_derived()
        return self.flood_event  # type: ignore

    def get_env_overrides(self) -> dict:
        """PlanetRunner / AtmosphereColumn에 주입할 환경 수정값 dict.

        반환 키:
            H2O_override       : float  — 대기 수증기 비율 (궁창 포함)
            albedo_override    : float  — 실효 알베도
            delta_tau          : float  — 추가 광학 깊이
            uv_shield_factor   : float  — UV 차폐율
            mutation_rate_factor: float — 돌연변이율 배수
            pressure_atm       : float  — 대기압 (1.0=현재)
            precip_mode        : str    — 강수 모드
            pole_eq_delta_K    : float  — 극적도 온도차 (K)
            phase              : str    — 시대 단계
            firmament_active   : bool
        """
        s = self.state
        return {
            'H2O_override':          0.01 + s.H2O_canopy,  # 기본 1% + 캐노피
            'albedo_override':       s.albedo,
            'delta_tau':             s.delta_tau,
            'uv_shield_factor':      s.uv_shield_factor,
            'mutation_rate_factor':  s.mutation_rate_factor,
            'pressure_atm':          s.pressure_atm,
            'precip_mode':           s.precip_mode,
            'pole_eq_delta_K':       s.pole_eq_delta_K,
            'phase':                 s.phase,
            'firmament_active':      s.active,
        }

    # ── 내부 ───────────────────────────────────────────────

    def _do_collapse(self) -> None:
        """궁창 붕괴 처리 — 대홍수 이벤트 생성."""
        s = self.state
        if not s.active:
            return  # 이미 붕괴됨

        H2O_released = s.H2O_canopy

        # 해수면 상승 추정
        # 대기 질량 ≈ 5.15e18 kg, 물밀도 1000 kg/m³, 지표면적 5.1e14 m²
        atm_mass_kg = 5.15e18
        water_mass  = atm_mass_kg * H2O_released
        ocean_area  = 3.6e14  # m² (해양 면적)
        sea_rise_m  = water_mass / (1000 * ocean_area)

        # 지하수 추가 분출 (창7:11 "깊음의 샘") — 경험적 배수
        sea_rise_m_total = sea_rise_m + 80.0  # 지하수 80m 추정

        self.flood_event = FloodEvent(
            trigger_year       = s.years_elapsed,
            H2O_released       = H2O_released,
            sea_level_rise_m   = sea_rise_m_total,
            f_land_change      = -0.19,          # 0.29 → 0.10
            albedo_jump        = _ALBEDO_POSTFLOOD - s.albedo,
            T_drop_K           = -(34.1 - 13.3), # -20.8K
            uv_shield_lost     = s.uv_shield_factor,
            mutation_rate_jump = _MUTATION_FACTOR_NOW / max(_MUTATION_FACTOR_EDEN, 1e-6),
        )

        # 상태 전환
        s.active              = False
        s.H2O_canopy          = _H2O_CANOPY_MIN
        s.phase               = 'postdiluvian'
        s.collapse_year       = s.years_elapsed
        s.collapse_triggered  = False  # 처리 완료

    def _update_derived(self) -> None:
        """파생 상태값 갱신."""
        s = self.state
        c = s.H2O_canopy  # 0 ~ 0.10

        # UV 차폐: H2O 5%일 때 0.95, 0%일 때 0.0
        s.uv_shield_factor = min(0.95, c / 0.05 * 0.95) if s.active else 0.0

        # 돌연변이율 배수: 에덴=0.01, 현재=1.0
        s.mutation_rate_factor = (
            _MUTATION_FACTOR_EDEN + (_MUTATION_FACTOR_NOW - _MUTATION_FACTOR_EDEN)
            * (1.0 - c / _H2O_CANOPY_EDEN)
        ) if s.active else _MUTATION_FACTOR_NOW

        # 알베도: 캐노피 많을수록 낮음 (빙하 없음)
        s.albedo = (
            _ALBEDO_EDEN + (_ALBEDO_POSTFLOOD - _ALBEDO_EDEN)
            * (1.0 - c / _H2O_CANOPY_EDEN)
        ) if s.active else _ALBEDO_POSTFLOOD

        # 대기압: 캐노피 H2O마다 압력 증가
        s.pressure_atm = 1.0 + c * 5.0  # H2O 5% → 1.25 atm

        # 극적도 온도차 억제
        s.pole_eq_delta_K = (
            _POLE_EQ_DELTA_EDEN + (_POLE_EQ_DELTA_NOW - _POLE_EQ_DELTA_EDEN)
            * (1.0 - c / _H2O_CANOPY_EDEN)
        ) if s.active else _POLE_EQ_DELTA_NOW

        # 추가 광학 깊이 (캐노피 온실효과)
        # H2O 5% → delta_tau ≈ 1.10 추가 (greenhouse.py optical_depth 계산 기반)
        import math
        if c > 0:
            alpha_H2O = 0.940
            H2O_ref   = 0.01
            s.delta_tau = alpha_H2O * (math.sqrt(c / H2O_ref) - math.sqrt(0.01 / H2O_ref))
        else:
            s.delta_tau = 0.0

        # 강수 모드
        if not s.active:
            s.precip_mode = 'rain'
        elif c > 0.03:
            s.precip_mode = 'mist'
        elif c > 0.01:
            s.precip_mode = 'drizzle'
        else:
            s.precip_mode = 'rain'

        # 단계 갱신 (활성 중)
        if s.active:
            s.phase = 'antediluvian'


def make_firmament(
    phase: PhaseType = 'antediluvian',
    H2O_canopy: float = _H2O_CANOPY_EDEN,
    decay_rate_per_yr: float = 0.0,
) -> FirmamentLayer:
    """FirmamentLayer 팩토리.

    Parameters
    ----------
    phase : 'antediluvian' | 'flood' | 'postdiluvian'
    H2O_canopy : float
        초기 캐노피 수증기 비율.
    decay_rate_per_yr : float
        자연 소멸 속도. 0이면 수동 trigger_flood()로만 붕괴.
    """
    fl = FirmamentLayer(
        initial_H2O_canopy=H2O_canopy,
        decay_rate_per_yr=decay_rate_per_yr,
    )
    if phase == 'postdiluvian':
        fl.trigger_flood()
    return fl
