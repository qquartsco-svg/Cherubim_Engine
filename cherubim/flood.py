"""flood.py — 대홍수 이벤트 엔진 (The Great Flood)

창세기 7:11:
  "노아 육백 세 되던 해 둘째 달 곧 그 달 열이렛날이라
   그 날에 큰 깊음의 샘들이 터지며 하늘의 창문들이 열려"

역할:
  FirmamentLayer.trigger_flood() 이후 지구 환경 파라미터가
  어떻게 전이(transition)되는지를 시간 함수로 기술한다.

  - 홍수 진행 (상승기): 40일/1년 단위
  - 홍수 절정 (침수기): f_land 최소
  - 홍수 후퇴 (하강기): 150일 후 물 빠짐
  - 홍수 종결 (안정화): 새 평형 도달

각 단계에서 바뀌는 파라미터:
  f_land        : 대륙 비율 (0.40 → 0.10 → 0.29)
  albedo        : 알베도    (0.20 → 0.10 → 0.306)
  T_surface     : 지표 온도 (34°C → spike → 13°C)
  mutation_rate : 돌연변이율 (0.01x → 1.0x)
  pole_eq_delta : 극적도차  (15K → 48K)
  ice_fraction  : 빙하 비율 (0.0 → 0.0 → 0.03)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import math


# ── 홍수 단계 ─────────────────────────────────────────────
FLOOD_PHASES = {
    'rising':      (0.0,  0.11),   # 40일 ≈ 0.11 yr
    'peak':        (0.11, 0.50),   # 물 최고 (150일)
    'receding':    (0.50, 1.00),   # 물 빠짐 (150일)
    'stabilizing': (1.00, 10.0),   # 안정화 (수년)
    'complete':    (10.0, 1e9),    # 홍수 종결
}


@dataclass
class FloodSnapshot:
    """홍수 진행 중 특정 시점의 환경 상태."""
    t_since_flood_yr: float     # 홍수 발생 후 경과 시간 (yr)
    flood_phase: str            # 현재 단계
    f_land: float               # 대륙 비율
    albedo: float               # 실효 알베도
    T_surface_K: float          # 지표 온도 (K)
    mutation_rate_factor: float # 돌연변이율 배수
    pole_eq_delta_K: float      # 극-적도 온도차 (K)
    ice_fraction: float         # 빙하 면적 비율
    sea_level_anomaly_m: float  # 현재 해수면 이상 (m)
    UV_exposure: float          # UV 노출 정규화 (0=없음, 1=현재)


class FloodEngine:
    """대홍수 진행 엔진.

    FirmamentLayer가 붕괴된 직후 이 엔진을 생성하고 step()을 호출하면
    홍수 전이 곡선에 따라 환경 파라미터가 변한다.

    Parameters
    ----------
    pre_flood_T_K : float
        홍수 직전 지표 온도 (K). 기본 307.3K (에덴 34°C).
    post_flood_T_K : float
        홍수 완전 종결 후 목표 온도 (K). 기본 286.4K (현재 13°C).
    pre_flood_f_land : float
        홍수 직전 대륙 비율. 기본 0.40 (에덴 — 빙하없어 해수면 낮음).
    post_flood_f_land : float
        홍수 후 대륙 비율. 기본 0.29 (현재).
    """

    def __init__(
        self,
        pre_flood_T_K: float = 307.3,
        post_flood_T_K: float = 286.4,
        pre_flood_f_land: float = 0.40,
        post_flood_f_land: float = 0.29,
    ) -> None:
        self._T_pre    = pre_flood_T_K
        self._T_post   = post_flood_T_K
        self._fl_pre   = pre_flood_f_land
        self._fl_post  = post_flood_f_land
        self._t        = 0.0   # 홍수 발생 후 경과 시간 (yr)
        self._complete = False

    # ── 공개 ──────────────────────────────────────────────

    def step(self, dt_yr: float = 1.0) -> FloodSnapshot:
        """홍수 진행 한 스텝."""
        self._t += dt_yr
        return self._snapshot()

    def get_env_overrides(self) -> dict:
        """PlanetRunner에 주입할 환경 수정 dict."""
        s = self._snapshot()
        return {
            'f_land':               s.f_land,
            'albedo_override':      s.albedo,
            'T_surface_target_K':   s.T_surface_K,
            'mutation_rate_factor': s.mutation_rate_factor,
            'pole_eq_delta_K':      s.pole_eq_delta_K,
            'ice_fraction':         s.ice_fraction,
            'sea_level_anomaly_m':  s.sea_level_anomaly_m,
            'UV_exposure':          s.UV_exposure,
            'flood_phase':          s.flood_phase,
        }

    @property
    def t_yr(self) -> float:
        return self._t

    @property
    def is_complete(self) -> bool:
        return self._t >= 10.0

    # ── 내부 ──────────────────────────────────────────────

    def _snapshot(self) -> FloodSnapshot:
        t = self._t
        phase = self._current_phase(t)

        # ── 전이 곡선 ──────────────────────────────────
        if phase == 'rising':
            # 0 → 0.11yr: 급격한 침수
            p = t / 0.11
            f_land  = self._lerp(self._fl_pre, 0.10, self._ease_in(p))
            albedo  = self._lerp(0.20, 0.10, p)   # 대륙 침수 → 알베도 ↓
            T_K     = self._lerp(self._T_pre, self._T_pre + 5, p)  # 일시 온도 상승
            mut     = self._lerp(0.01, 0.5, p)
            delta   = self._lerp(15.0, 25.0, p)
            ice     = 0.0
            sea     = self._lerp(0, 80, p)
            uv      = self._lerp(0.05, 0.5, p)

        elif phase == 'peak':
            # 0.11 → 0.50yr: 절정 유지
            p = (t - 0.11) / (0.50 - 0.11)
            f_land  = 0.10
            albedo  = 0.10
            T_K     = self._T_pre + 5 - 10 * p   # 구름 가리면서 냉각
            mut     = self._lerp(0.5, 1.0, p)
            delta   = self._lerp(25.0, 35.0, p)
            ice     = 0.0
            sea     = 80.0
            uv      = self._lerp(0.5, 0.8, p)

        elif phase == 'receding':
            # 0.50 → 1.00yr: 물 빠짐
            p = (t - 0.50) / 0.50
            f_land  = self._lerp(0.10, self._fl_post, self._ease_out(p))
            albedo  = self._lerp(0.10, self._fl_post * 0.8, p)
            T_K     = self._lerp(self._T_pre - 5, self._T_post + 10, p)
            mut     = 1.0
            delta   = self._lerp(35.0, 45.0, p)
            ice     = self._lerp(0.0, 0.01, p)
            sea     = self._lerp(80, 10, p)
            uv      = self._lerp(0.8, 1.0, p)

        elif phase == 'stabilizing':
            # 1.00 → 10.0yr: 장기 안정화 (극지 냉각, 빙하 성장)
            p = (t - 1.0) / 9.0
            f_land  = self._fl_post
            albedo  = self._lerp(self._fl_post * 0.8, 0.306, p)
            T_K     = self._lerp(self._T_post + 10, self._T_post, self._ease_out(p))
            mut     = 1.0
            delta   = self._lerp(45.0, 48.0, p)
            ice     = self._lerp(0.01, 0.03, p)
            sea     = self._lerp(10, 0, p)
            uv      = 1.0

        else:  # complete
            f_land  = self._fl_post
            albedo  = 0.306
            T_K     = self._T_post
            mut     = 1.0
            delta   = 48.0
            ice     = 0.03
            sea     = 0.0
            uv      = 1.0

        return FloodSnapshot(
            t_since_flood_yr     = t,
            flood_phase          = phase,
            f_land               = f_land,
            albedo               = albedo,
            T_surface_K          = T_K,
            mutation_rate_factor = mut,
            pole_eq_delta_K      = delta,
            ice_fraction         = ice,
            sea_level_anomaly_m  = sea,
            UV_exposure          = uv,
        )

    @staticmethod
    def _current_phase(t: float) -> str:
        for phase, (t0, t1) in FLOOD_PHASES.items():
            if t0 <= t < t1:
                return phase
        return 'complete'

    @staticmethod
    def _lerp(a: float, b: float, p: float) -> float:
        p = max(0.0, min(1.0, p))
        return a + (b - a) * p

    @staticmethod
    def _ease_in(p: float) -> float:
        """가속 곡선 (홍수 급격히 시작)."""
        return p * p

    @staticmethod
    def _ease_out(p: float) -> float:
        """감속 곡선 (물 서서히 빠짐)."""
        return 1.0 - (1.0 - p) ** 2


def make_flood_engine(
    pre_flood_T_celsius: float = 34.1,
    post_flood_T_celsius: float = 13.3,
    pre_flood_f_land: float = 0.40,
    post_flood_f_land: float = 0.29,
) -> FloodEngine:
    """FloodEngine 팩토리 (섭씨 입력 허용)."""
    return FloodEngine(
        pre_flood_T_K    = pre_flood_T_celsius + 273.15,
        post_flood_T_K   = post_flood_T_celsius + 273.15,
        pre_flood_f_land = pre_flood_f_land,
        post_flood_f_land= post_flood_f_land,
    )
