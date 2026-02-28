"""initial_conditions.py — 지구 초기 환경 조건 (동역학 기반)

핵심 철학:
  "하드코딩이 아니라 물리 인과관계로 초기조건을 결정한다."
  상수/계수는 EDEN_IC_CONFIG로 모아 override 가능 (규약 준수).

  초기조건(IC)은 6개 독립 파라미터:
    CO2, H2O_atm, O2, albedo, f_land, precip_mode

  나머지는 전부 동역학으로 자동 계산:
    CO2 + H2O + O2  → greenhouse.py → τ → ε_a → T_surface
    T_surface + δT  → LatitudeBands → band_T[12]
    precip_mode     → soil_moisture[12]
    band_T + W + CO2→ BiosphereColumn → GPP[12]
    O2 + GPP        → FoodWeb → TrophicState
    UV_shield       → mutation_rate_factor

시대별 프리셋:
  antediluvian  — 에덴 (궁창 존재, 대홍수 이전)
  postdiluvian  — 현재 Day7 기준 (대홍수 이후)

참조:
  - docs/ANTEDILUVIAN_ENV.md
  - solar/eden/firmament.py
  - docs/EDEN_ENGINEERING_FINAL.md (τ/알베도/ΔT 중복 방지 규칙)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Literal, Optional, Any

import numpy as np

# 물리 상수 (EDEN_IC_CONFIG에서 읽음, 하위 호환용 모듈 상수 유지)
F_SOLAR = 1361.0       # W/m²
SIGMA   = 5.6704e-8    # W/(m²·K⁴)

# 규약: 모든 상수/계수는 이 dict로 모아 override 가능 (docs/EDEN_ENGINEERING_FINAL.md)
EDEN_IC_CONFIG: Dict[str, Any] = {
    "F_SOLAR": F_SOLAR,
    "SIGMA": SIGMA,
    "tau_base": 0.12,
    "alpha_CO2": 0.462,
    "CO2_ref": 280e-6,
    "alpha_H2O": 0.940,
    "H2O_ref": 0.01,
    "alpha_CH4": 0.056,
    "CH4_ref": 0.7e-6,
    "pole_eq_delta_now_K": 48.0,
    "pole_eq_delta_eden_K": 15.0,
    "H2O_canopy_ref": 0.05,
    "P_MAX": 2.0,
    "F_HALF": 100.0,
    "K_C": 40e-6,
    "T_OPT": 298.0,
    "SIG_T": 15.0,
    "f_I": 0.6,
    "mutation_uv_floor": 0.01,
}

# 위도 밴드 중심 (12개)
_BAND_LATS = np.array([
    -82.5, -67.5, -52.5, -37.5, -22.5, -7.5,
      7.5,  22.5,  37.5,  52.5,  67.5,  82.5,
])

PhaseType   = Literal['antediluvian', 'postdiluvian']
PrecipMode  = Literal['mist', 'drizzle', 'rain']


# ── 동역학 계산 함수들 ─────────────────────────────────────

def _optical_depth(
    CO2: float, H2O: float, CH4: float = 1.8e-6,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """greenhouse.py 동일 공식. config 없으면 EDEN_IC_CONFIG 사용."""
    c = config or EDEN_IC_CONFIG
    tau_base = c["tau_base"]
    alpha_CO2, CO2_ref  = c["alpha_CO2"], c["CO2_ref"]
    alpha_H2O, H2O_ref  = c["alpha_H2O"], c["H2O_ref"]
    alpha_CH4, CH4_ref  = c["alpha_CH4"], c["CH4_ref"]

    tau = tau_base
    if CO2 > 1e-12:
        tau += alpha_CO2 * math.log(1.0 + CO2 / CO2_ref)
    if H2O > 1e-12:
        tau += alpha_H2O * math.sqrt(H2O / H2O_ref)
    if CH4 > 1e-12:
        tau += alpha_CH4 * math.sqrt(CH4 / CH4_ref)
    return max(tau, 0.0)


def _T_surface(
    tau: float, albedo: float,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """1-layer 온실 평형온도. config 없으면 EDEN_IC_CONFIG 사용."""
    c = config or EDEN_IC_CONFIG
    F_SOLAR, SIGMA = c["F_SOLAR"], c["SIGMA"]
    eps_a = 1.0 - math.exp(-tau)
    F_abs = F_SOLAR * (1.0 - albedo) / 4.0
    denom = 1.0 - eps_a / 2.0
    return (F_abs / (SIGMA * max(denom, 1e-6))) ** 0.25


def _pole_eq_delta(
    H2O_canopy: float,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """궁창 수증기량 → 극적도 온도차.

    H2O_canopy=0.00 → delta=48K (현재)
    H2O_canopy=0.05 → delta=15K (에덴)
    선형 보간. config 없으면 EDEN_IC_CONFIG 사용.
    """
    c = config or EDEN_IC_CONFIG
    now_K = c["pole_eq_delta_now_K"]
    eden_K = c["pole_eq_delta_eden_K"]
    ref = c["H2O_canopy_ref"]
    return now_K - (now_K - eden_K) * min(H2O_canopy / ref, 1.0)


def _band_temperatures(T_mean: float, pole_eq_delta: float) -> np.ndarray:
    """위도별 온도: T_mean ± delta × cos(lat) 변조."""
    cos_lats = np.cos(np.radians(_BAND_LATS))
    return T_mean + pole_eq_delta * (cos_lats - 0.5) * 2.0


def _soil_moisture(precip_mode: PrecipMode) -> np.ndarray:
    """강수 모드 → 위도별 토양 수분.

    mist   : 균일 0.75 (안개가 전 위도 골고루 적심)
    drizzle: 균일 0.65
    rain   : 위도 함수 (적도 0.85, 극지 0.25)
    """
    if precip_mode == 'mist':
        return np.full(12, 0.75)
    elif precip_mode == 'drizzle':
        return np.full(12, 0.65)
    else:
        abs_lats = np.abs(_BAND_LATS)
        W = np.where(abs_lats < 30,  0.85,
            np.where(abs_lats < 60,  0.55, 0.25))
        return W


def _gpp_per_band(
    band_T_K: np.ndarray,
    soil_W: np.ndarray,
    CO2: float,
    O2: float,
    pressure_atm: float = 1.0,
    config: Optional[Dict[str, Any]] = None,
) -> np.ndarray:
    """위도별 GPP 추정 (BiosphereColumn 동일 공식).

    GPP = P_MAX · f_I · f_C(CO2) · f_T(T) · f_W(W)
    config 없으면 EDEN_IC_CONFIG 사용.
    """
    c = config or EDEN_IC_CONFIG
    P_MAX  = c["P_MAX"]
    K_C    = c["K_C"]
    T_OPT  = c["T_OPT"]
    SIG_T  = c["SIG_T"]
    f_I    = c["f_I"]

    f_C = CO2 / (CO2 + K_C)
    f_T = np.exp(-0.5 * ((band_T_K - T_OPT) / SIG_T) ** 2)
    f_W = np.minimum(soil_W, 1.0)

    o2_pressure = O2 * pressure_atm
    f_O2 = 1.0 + 0.2 * max(0, o2_pressure - 0.21) / 0.21

    return P_MAX * f_I * f_C * f_T * f_W * f_O2


def _mutation_factor(
    UV_shield: float,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """UV 차폐율 → mutation_rate 배수. config 없으면 EDEN_IC_CONFIG 사용."""
    c = config or EDEN_IC_CONFIG
    floor = c["mutation_uv_floor"]
    return max(1.0 - UV_shield * 0.99, floor)


# ── InitialConditions 데이터 클래스 ──────────────────────

@dataclass
class EarthBandState:
    """12개 위도 밴드의 초기 상태 (동역학으로 계산된 결과)."""
    T_K:         np.ndarray  # [12] 온도 (K)
    soil_W:      np.ndarray  # [12] 토양 수분 [0~1]
    GPP:         np.ndarray  # [12] GPP (kg C/m²/yr)
    ice_mask:    np.ndarray  # [12] bool — 빙하 존재 여부
    habitable:   np.ndarray  # [12] bool — 거주 가능


@dataclass
class InitialConditions:
    """지구 초기 환경 전체 상태.

    독립 입력 파라미터 (6개):
      CO2_ppm, H2O_atm_frac, O2_frac, albedo, f_land, precip_mode

    동역학 계산 결과 (자동):
      tau, eps_a, T_surface_K, band, mutation_factor, etc.
    """

    # ── 독립 입력 ──────────────────────────────────────────
    phase:          PhaseType   = 'postdiluvian'
    CO2_ppm:        float       = 400.0
    H2O_atm_frac:  float       = 0.01     # 대기 중 수증기 (궁창 포함)
    H2O_canopy:    float       = 0.00     # 궁창 추가분만
    O2_frac:        float       = 0.21
    CH4_ppm:        float       = 1.8
    albedo:         float       = 0.306
    f_land:         float       = 0.29
    precip_mode:    PrecipMode  = 'rain'
    pressure_atm:   float       = 1.0
    UV_shield:      float       = 0.0

    # ── 동역학 계산 결과 (build()에서 채워짐) ──────────────
    tau:                float       = field(default=0.0,  init=False)
    eps_a:              float       = field(default=0.0,  init=False)
    T_surface_K:        float       = field(default=0.0,  init=False)
    pole_eq_delta_K:    float       = field(default=48.0, init=False)
    mutation_factor:    float       = field(default=1.0,  init=False)
    band:               Optional[EarthBandState] = field(default=None, init=False)

    def __post_init__(self) -> None:
        self._build()

    def _build(self) -> None:
        """독립 파라미터 → 동역학 계산."""
        CO2  = self.CO2_ppm * 1e-6
        H2O  = self.H2O_atm_frac
        CH4  = self.CH4_ppm * 1e-6

        # ① 광학깊이 → 온실효과 → 지표 온도
        self.tau         = _optical_depth(CO2, H2O, CH4)
        self.eps_a       = 1.0 - math.exp(-self.tau)
        self.T_surface_K = _T_surface(self.tau, self.albedo)

        # ② 극적도 온도차 (궁창 캐노피 균온화)
        self.pole_eq_delta_K = _pole_eq_delta(self.H2O_canopy)

        # ③ 위도별 온도
        band_T = _band_temperatures(self.T_surface_K, self.pole_eq_delta_K)

        # ④ 토양 수분 (강수 모드 기반)
        soil_W = _soil_moisture(self.precip_mode)

        # ⑤ GPP
        gpp = _gpp_per_band(band_T, soil_W, CO2, self.O2_frac, self.pressure_atm)

        # ⑥ 빙하 / 거주가능 마스크
        T_C      = band_T - 273.15
        ice_mask = T_C < -10.0
        hab_mask = (-40.0 < T_C) & (T_C < 65.0)

        self.band = EarthBandState(
            T_K      = band_T,
            soil_W   = soil_W,
            GPP      = gpp,
            ice_mask = ice_mask,
            habitable= hab_mask,
        )

        # ⑦ 돌연변이율
        self.mutation_factor = _mutation_factor(self.UV_shield)

    def to_runner_kwargs(self) -> Dict:
        """PlanetRunner 생성자에 넘길 kwargs dict."""
        return {
            'CO2_ppm_init':       self.CO2_ppm,
            'O2_frac_init':       self.O2_frac,
            'albedo_init':        self.albedo,
            'f_land_init':        self.f_land,
            'mutation_factor':    self.mutation_factor,
            'precip_mode':        self.precip_mode,
            'T_surface_K_init':   self.T_surface_K,
            'pole_eq_delta_K':    self.pole_eq_delta_K,
            'pressure_atm':       self.pressure_atm,
        }

    def summary(self) -> str:
        """사람이 읽기 좋은 요약 문자열."""
        b = self.band
        ice_n = int(b.ice_mask.sum())
        hab_n = int(b.habitable.sum())
        T_C = self.T_surface_K - 273.15

        lines = [
            f'  phase           = {self.phase}',
            f'  CO2             = {self.CO2_ppm:.0f} ppm',
            f'  H2O (대기)      = {self.H2O_atm_frac*100:.1f}%',
            f'  H2O (궁창)      = {self.H2O_canopy*100:.1f}%',
            f'  O2              = {self.O2_frac*100:.1f}%',
            f'  albedo          = {self.albedo:.3f}',
            f'  f_land          = {self.f_land:.2f}',
            f'  pressure        = {self.pressure_atm:.2f} atm',
            f'  precip_mode     = {self.precip_mode}',
            f'  ─────────────────────────────',
            f'  τ (광학깊이)    = {self.tau:.3f}',
            f'  ε_a (온실효율)  = {self.eps_a:.3f}',
            f'  T_surface       = {self.T_surface_K:.1f} K  ({T_C:.1f}°C)',
            f'  극적도 ΔT       = {self.pole_eq_delta_K:.1f} K',
            f'  mutation factor = {self.mutation_factor:.4f}x',
            f'  빙하 밴드       = {ice_n}/12',
            f'  거주가능 밴드   = {hab_n}/12',
            f'  GPP 합계        = {b.GPP.sum():.2f} kg C/m²/yr',
            f'  UV_shield       = {self.UV_shield:.2f}',
        ]
        return '\n'.join(lines)


# ── 프리셋 팩토리 ────────────────────────────────────────

def make_antediluvian() -> InitialConditions:
    """에덴 초기조건 — 궁창 완전체, 대홍수 이전.

    물리적 근거:
      CO2 250ppm   : 식물 활발, 홍수 전 pre-industrial 수준
      H2O_atm 6%   : 기본 1% + 궁창 5%
      O2 24%       : 현재보다 약간 높음 (산불 임계 0.25 미만 유지)
                     석탄기 28%보다 보수적 — 에덴의 안정 생태계와 일치
      albedo 0.20  : 빙하·구름 없음
      f_land 0.40  : 해수면 낮음 (빙하수 없음)
      precip=mist  : 창세기 2:6 안개
      pressure 1.25: 캐노피 추가 대기압
      UV_shield 0.95: 수증기층 UV 차폐
    """
    return InitialConditions(
        phase         = 'antediluvian',
        CO2_ppm       = 250.0,
        H2O_atm_frac  = 0.06,   # 기본 + 궁창
        H2O_canopy    = 0.05,   # 궁창 분량만
        O2_frac       = 0.24,   # 현재 21% + 약간 (산불 임계 25% 미만)
        CH4_ppm       = 0.5,
        albedo        = 0.20,
        f_land        = 0.40,
        precip_mode   = 'mist',
        pressure_atm  = 1.25,
        UV_shield     = 0.95,
    )


def make_postdiluvian() -> InitialConditions:
    """대홍수 이후 초기조건 — 현재 Day7 기준점.

    물리적 근거:
      CO2 280ppm   : pre-industrial (홍수 직후)
      H2O_atm 1%   : 궁창 소멸 후 표준
      O2 21%       : 현재
      albedo 0.306 : 빙하+구름 형성
      f_land 0.29  : 현재 대륙 비율
      precip=rain  : 강우 시작
      pressure 1.0 : 현재 대기압
      UV_shield 0.0: 차폐 없음
    """
    return InitialConditions(
        phase         = 'postdiluvian',
        CO2_ppm       = 280.0,
        H2O_atm_frac  = 0.01,
        H2O_canopy    = 0.00,
        O2_frac       = 0.21,
        CH4_ppm       = 0.7,
        albedo        = 0.306,
        f_land        = 0.29,
        precip_mode   = 'rain',
        pressure_atm  = 1.0,
        UV_shield     = 0.0,
    )


def make_flood_peak() -> InitialConditions:
    """대홍수 절정 — 대륙 침수 최대."""
    return InitialConditions(
        phase         = 'antediluvian',  # 사건 진행 중
        CO2_ppm       = 280.0,
        H2O_atm_frac  = 0.03,   # 궁창 붕괴 중간
        H2O_canopy    = 0.02,
        O2_frac       = 0.23,
        CH4_ppm       = 0.7,
        albedo        = 0.10,   # 대륙 침수 → 반사 감소
        f_land        = 0.10,   # 대부분 침수
        precip_mode   = 'rain',
        pressure_atm  = 1.10,
        UV_shield     = 0.30,   # 부분 붕괴
    )
