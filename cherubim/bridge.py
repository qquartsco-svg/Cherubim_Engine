"""cherubim.bridge — Cherubim_Engine ↔ solar 연결 브릿지

"독립 엔진을 완성하고, 메인 시스템에 연결한다."

역할
────
  Cherubim_Engine 의 InitialConditions 를
  CookiieBrain/solar 의 PlanetRunner 가 받는
  initial_conditions dict 형식으로 변환한다.

  방향: Cherubim → solar  (단방향 변환)

  ┌──────────────────────┐      ┌──────────────────────────┐
  │  Cherubim_Engine     │      │  CookiieBrain / solar    │
  │                      │      │                          │
  │  InitialConditions   │─────▶│  PlanetRunner(           │
  │  (antediluvian)      │bridge│    initial_conditions=   │
  │  eden_os/            │      │    runner_kwargs)         │
  │  EdenOSRunner        │      │  Day7 물리 엔진           │
  └──────────────────────┘      └──────────────────────────┘

변환 키 매핑 (1:1 완벽 대응 확인됨)
──────────────────────────────────────────────────────────
  Cherubim IC 필드       →  solar runner_kwargs 키
  ─────────────────────────────────────────────────────
  CO2_ppm               →  CO2_ppm_init
  O2_frac               →  O2_frac_init
  albedo                →  albedo_init
  f_land                →  f_land_init
  mutation_factor       →  mutation_factor
  precip_mode           →  precip_mode
  T_surface_K           →  T_surface_K_init
  pole_eq_delta_K       →  pole_eq_delta_K
  pressure_atm          →  pressure_atm

사용 방법
──────────────────────────────────────────────────────────
  # ① 기본 사용 (Cherubim IC → solar runner)
  from cherubim.bridge import to_solar_runner_kwargs
  from cherubim.initial_conditions import make_antediluvian

  ic      = make_antediluvian()
  kwargs  = to_solar_runner_kwargs(ic)

  # solar PlanetRunner 에 주입
  from solar.day7 import make_planet_runner
  runner  = make_planet_runner(initial_conditions=kwargs)
  snap    = runner.step()

  # ② EdenOS + solar Day7 동시 실행
  from cherubim.bridge import run_eden_then_solar
  result  = run_eden_then_solar(eden_steps=24, solar_steps=12)
  result.print_report()

레이어 분리
──────────────────────────────────────────────────────────
  PHYSICAL_FACT : IC 수치 변환 (1:1 매핑, 오차 없음)
  SCENARIO      : EdenOS → solar 연결 시나리오
  LORE          : "에덴(창 2장)이 Day7(창 1장) 위에서 작동한다"
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Optional

# Cherubim 내부 임포트
from .initial_conditions import InitialConditions, make_antediluvian

# 레이어 상수
PHYSICAL = "PHYSICAL_FACT"
SCENARIO  = "SCENARIO"
LORE      = "LORE"


# ═══════════════════════════════════════════════════════════════════════════════
#  핵심 변환 함수 — Cherubim IC → solar runner_kwargs
# ═══════════════════════════════════════════════════════════════════════════════

def to_solar_runner_kwargs(ic: InitialConditions) -> Dict[str, Any]:
    """Cherubim InitialConditions → solar PlanetRunner initial_conditions dict.

    Parameters
    ----------
    ic : InitialConditions
        Cherubim 초기 조건 (make_antediluvian() 또는 임의 IC).

    Returns
    -------
    dict  —  solar.day7.make_planet_runner(initial_conditions=...) 에 직접 주입 가능.

    Examples
    --------
    >>> from cherubim.bridge import to_solar_runner_kwargs
    >>> from cherubim.initial_conditions import make_antediluvian
    >>> kwargs = to_solar_runner_kwargs(make_antediluvian())
    >>> # solar 쪽에서:
    >>> from solar.day7 import make_planet_runner
    >>> runner = make_planet_runner(initial_conditions=kwargs)
    """
    return {
        # ── 대기 ────────────────────────────────────────────────────────────
        "CO2_ppm_init":     ic.CO2_ppm,
        "O2_frac_init":     ic.O2_frac,
        "albedo_init":      ic.albedo,
        "pressure_atm":     ic.pressure_atm,

        # ── 지표 ────────────────────────────────────────────────────────────
        "f_land_init":      ic.f_land,
        "precip_mode":      ic.precip_mode,

        # ── 온도 ────────────────────────────────────────────────────────────
        "T_surface_K_init": ic.T_surface_K,
        "pole_eq_delta_K":  ic.pole_eq_delta_K,

        # ── 생물 ────────────────────────────────────────────────────────────
        "mutation_factor":  ic.mutation_factor,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  BridgeResult — 연결 실행 결과
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class BridgeResult:
    """EdenOS + solar Day7 동시 실행 결과."""
    ic_phase:         str
    eden_index:       float
    eden_valid:       bool
    runner_kwargs:    Dict[str, Any]
    solar_available:  bool        # solar 패키지 임포트 성공 여부
    solar_snapshot:   Any         # PlanetSnapshot (없으면 None)
    eden_os_logs:     Any         # EdenOS TickLog 리스트 (없으면 None)
    notes:            list

    def print_report(self) -> None:
        width = 68
        print("=" * width)
        print("  🌉 Bridge Report — Cherubim ↔ solar")
        print("=" * width)

        print(f"\n  [{PHYSICAL}]  IC 변환 결과")
        for k, v in self.runner_kwargs.items():
            print(f"    {k:<25}: {v}")

        print(f"\n  [{SCENARIO}]  실행 결과")
        print(f"    IC 시대       : {self.ic_phase}")
        print(f"    에덴 지수     : {self.eden_index:.4f}")
        print(f"    EdenOS 합격   : {'✅' if self.eden_valid else '❌'}")
        print(f"    solar 연결    : {'✅ 성공' if self.solar_available else '⚠ solar 패키지 없음 (독립 모드)'}")

        if self.solar_snapshot is not None:
            snap = self.solar_snapshot
            print(f"\n    solar Day7 스냅샷:")
            print(f"      {snap.summary() if hasattr(snap, 'summary') else snap}")

        if self.eden_os_logs:
            success = sum(1 for l in self.eden_os_logs if l.adam_success)
            print(f"\n    EdenOS 틱 로그: {len(self.eden_os_logs)}틱  성공률={success/len(self.eden_os_logs):.0%}")

        if self.notes:
            print(f"\n  노트:")
            for n in self.notes:
                print(f"    {n}")

        print(f"\n  [{LORE}]")
        print("    에덴(창 2장) 이 Day7 행성 OS(창 1장) 위에서 작동한다")
        print("    Cherubim_Engine = 독립 에덴 탐색기")
        print("    solar/day7      = 전체 행성 물리 실행기")
        print("    bridge          = 두 시스템을 연결하는 변환 레이어")
        print("=" * width)


# ═══════════════════════════════════════════════════════════════════════════════
#  run_eden_then_solar — EdenOS 실행 후 solar 에 연결
# ═══════════════════════════════════════════════════════════════════════════════

def run_eden_then_solar(
    ic:           Optional[InitialConditions] = None,
    eden_steps:   int = 24,
    solar_steps:  int = 12,
    seed:         int = 42,
) -> BridgeResult:
    """EdenOS 실행 → solar PlanetRunner 연결 통합 실행.

    solar 패키지가 없어도 EdenOS 단독 실행 결과를 반환한다.
    (독립 모드 fallback)

    Parameters
    ----------
    ic          : InitialConditions, optional  — None이면 make_antediluvian()
    eden_steps  : int  — EdenOS 실행 틱 수
    solar_steps : int  — solar PlanetRunner 실행 스텝 수
    seed        : int  — 재현성 시드

    Returns
    -------
    BridgeResult
    """
    if ic is None:
        ic = make_antediluvian()

    notes: list = []
    runner_kwargs = to_solar_runner_kwargs(ic)

    # ── EdenOS 실행 ────────────────────────────────────────────────────────
    from .eden_os.eden_os_runner import make_eden_os_runner
    from .eden_os.eden_world import make_eden_world
    eden_world = make_eden_world(ic=ic)
    runner = make_eden_os_runner(world_ic=ic, seed=seed)
    eden_logs = runner.run(steps=eden_steps)
    notes.append(f"EdenOS {eden_steps}틱 완료 (성공률={sum(1 for l in eden_logs if l.adam_success)/eden_steps:.0%})")

    # ── solar 연결 시도 ────────────────────────────────────────────────────
    solar_available = False
    solar_snapshot  = None

    try:
        import sys, os
        # solar 패키지 경로 자동 탐색
        _solar_candidates = [
            "/Users/jazzin/Desktop/00_BRAIN/CookiieBrain",
            "/Users/jazzin/Desktop/00_BRAIN/CookiieBrain/cookiie_brain",
        ]
        for _path in _solar_candidates:
            if _path not in sys.path and os.path.isdir(_path):
                sys.path.insert(0, _path)

        from solar.day7 import make_planet_runner
        planet_runner = make_planet_runner(
            seed               = seed,
            initial_conditions = runner_kwargs,
        )
        for _ in range(solar_steps):
            solar_snapshot = planet_runner.step()

        solar_available = True
        notes.append(f"solar Day7 {solar_steps}스텝 완료: {solar_snapshot.summary()}")

    except ImportError as e:
        notes.append(f"solar 패키지 없음 — 독립 모드로 실행됨 ({e})")
    except Exception as e:
        notes.append(f"solar 실행 중 오류: {e}")

    return BridgeResult(
        ic_phase        = ic.phase,
        eden_index      = eden_world.eden_index,
        eden_valid      = eden_world.valid,
        runner_kwargs   = runner_kwargs,
        solar_available = solar_available,
        solar_snapshot  = solar_snapshot,
        eden_os_logs    = eden_logs,
        notes           = notes,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  연결 상태 확인
# ═══════════════════════════════════════════════════════════════════════════════

def check_bridge_status() -> None:
    """Cherubim ↔ solar 연결 상태 체크 및 출력."""
    print("\n  🌉 Bridge 연결 상태 체크")
    print("  " + "─" * 50)

    # Cherubim 확인
    try:
        from .initial_conditions import make_antediluvian
        ic = make_antediluvian()
        kwargs = to_solar_runner_kwargs(ic)
        print(f"  ✅ Cherubim_Engine    IC 변환 가능  ({len(kwargs)}개 키)")
    except Exception as e:
        print(f"  ❌ Cherubim_Engine    오류: {e}")

    # solar 확인
    import sys, os
    _solar_candidates = [
        "/Users/jazzin/Desktop/00_BRAIN/CookiieBrain",
        "/Users/jazzin/Desktop/00_BRAIN/CookiieBrain/cookiie_brain",
    ]
    for _path in _solar_candidates:
        if _path not in sys.path and os.path.isdir(_path):
            sys.path.insert(0, _path)

    try:
        from solar.day7 import make_planet_runner
        print(f"  ✅ solar.day7         PlanetRunner 임포트 성공")
    except ImportError:
        print(f"  ⚠  solar.day7         패키지 없음 (독립 모드)")

    try:
        from solar.eden import make_antediluvian as solar_make_ante
        print(f"  ✅ solar.eden         InitialConditions 임포트 성공")
    except ImportError:
        print(f"  ⚠  solar.eden         패키지 없음")

    print("  " + "─" * 50)
    print("  변환 키 매핑:")
    _cherubim_fields = [
        ("CO2_ppm",         "CO2_ppm_init"),
        ("O2_frac",         "O2_frac_init"),
        ("albedo",          "albedo_init"),
        ("pressure_atm",    "pressure_atm"),
        ("f_land",          "f_land_init"),
        ("precip_mode",     "precip_mode"),
        ("T_surface_K",     "T_surface_K_init"),
        ("pole_eq_delta_K", "pole_eq_delta_K"),
        ("mutation_factor", "mutation_factor"),
    ]
    for cherubim_key, solar_key in _cherubim_fields:
        print(f"    Cherubim.{cherubim_key:<20} → solar.{solar_key}")
    print()
