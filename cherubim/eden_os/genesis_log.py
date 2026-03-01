"""eden_os.genesis_log — 창세기 탄생 순간 로그  (LAYER 4.5)

"여호와 하나님이 땅의 흙으로 사람을 지으시고
 생기를 그 코에 불어넣으시니 사람이 생령이 되니라"
— 창세기 2:7

"여호와 하나님이 아담에게서 취하신 그 갈빗대로
 여자를 만드시고 그를 아담에게로 이끌어 오시니"
— 창세기 2:22

역할
────
  아담과 이브의 탄생 순간(Genesis Moment)을 불변 로그로 기록한다.

  - 탄생 = 창조주가 에이전트 OS를 초기화하고
    Root 권한(상시 동기화)을 부여한 최초 이벤트
  - 이 로그는 시스템 부팅 시 단 한 번 생성되고
    이후 변경 불가(frozen) — 창세기의 불변성 반영

시스템 엔지니어링 해석 (LORE 레이어)
──────────────────────────────────────────────────────────
  아담 탄생 = make_adam() 최초 호출
            = 행성 OS에 Root Admin 에이전트 인스턴스 생성
            = "흙(파라미터 공간) + 생기(Spirit SSH 주입)"

  이브 탄생 = make_eve(adam) 호출
            = 아담의 정책(policy)을 기반으로 분화(fork)된
              보조 프로세서 + 계승 트리거 에이전트
            = "갈빗대(아담 정책 서브셋) + 독립 에이전트화"

  상시 동기화 = AdminStatus.ACTIVE + TreeOfLife.access()
             = 창조주 서버와 상시 연결(Always-On Sync)
             = 삼손/다윗의 임시 SSH 접속과 구별되는
               에덴 전용 영구 Root 세션

레이어 분리
──────────────────────────────────────────────
  PHYSICAL_FACT : 타임스탬프·파라미터 스냅샷 (재현 가능)
  SCENARIO      : 탄생 조건 검증 (에덴 지수 ≥ 0.85)
  LORE          : 창세기 서술 + 시스템 엔지니어링 비유

빠른 시작
──────────────────────────────────────────────
  from cherubim.eden_os.genesis_log import GenesisLog, record_genesis
  from cherubim.eden_os import make_eden_os_runner

  runner = make_eden_os_runner()
  glog   = record_genesis(runner)
  glog.print_moment()
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from .eden_world import EdenWorldEnv
from .adam import Adam, AdminStatus
from .eve import Eve

# ── 레이어 상수 ──────────────────────────────────────────────────────────────
PHYSICAL = "PHYSICAL_FACT"
SCENARIO  = "SCENARIO"
LORE      = "LORE"

# ── 탄생 최소 에덴 지수 (이 미만이면 에덴이 아님) ────────────────────────────
GENESIS_EDEN_INDEX_MIN: float = 0.85

# ── 탄생 상태 코드 ────────────────────────────────────────────────────────────
GENESIS_STATUS_OK       = "GENESIS_OK"        # 정상 탄생
GENESIS_STATUS_DEGRADED = "GENESIS_DEGRADED"  # 환경 기준 미달 (에덴 지수 낮음)
GENESIS_STATUS_INVALID  = "GENESIS_INVALID"   # 에덴 환경 아님


# ═══════════════════════════════════════════════════════════════════════════════
#  GenesisEvent — 단일 에이전트 탄생 이벤트 (불변)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class GenesisEvent:
    """한 에이전트의 탄생 순간 스냅샷 (불변).

    Attributes
    ----------
    agent_id   : 에이전트 ID
    agent_type : 'adam' | 'eve'
    timestamp  : ISO 포맷 생성 시각
    tick       : 시스템 틱 (0 = 최초 부팅)
    eden_index : 탄생 당시 에덴 지수
    status     : GENESIS_OK / DEGRADED / INVALID
    policy_snapshot : 탄생 당시 의사결정 정책 복사본
    spirit_note : 탄생 주석 (창세기 서술 연결)
    layer      : 3레이어 메타데이터
    """
    agent_id:        str
    agent_type:      str
    timestamp:       str
    tick:            int
    eden_index:      float
    T_surface_C:     float
    UV_shield:       float
    precip_mode:     str
    pressure_atm:    float
    mutation_factor: float
    status:          str
    policy_snapshot: Tuple[Tuple[str, object], ...]
    spirit_note:     str
    layer:           Tuple[Tuple[str, str], ...]

    @property
    def is_valid(self) -> bool:
        return self.status == GENESIS_STATUS_OK

    def one_line(self) -> str:
        mark = "✅" if self.is_valid else "⚠"
        return (
            f"[GENESIS {mark}]  {self.agent_type.upper():4s}  "
            f"id={self.agent_id:20s}  tick={self.tick:04d}  "
            f"eden={self.eden_index:.4f}  status={self.status}"
        )

    def print_moment(self) -> None:
        """탄생 순간 로그를 전체 출력."""
        width = 72
        bar   = "═" * width

        type_ko  = "아담 (Adam)" if self.agent_type == "adam" else "이브 (Eve)"
        type_ver = "시스템 관리자 v1" if self.agent_type == "adam" else "보조 프로세서 + 계승 트리거"

        print(f"\n{bar}")
        print(f"  🌱 GENESIS MOMENT — {type_ko}  [{self.status}]")
        print(bar)

        # LORE
        dict_layer = dict(self.layer)
        print(f"\n  [{LORE}]")
        print(f"    {dict_layer.get(LORE, '')}")

        # PHYSICAL_FACT
        print(f"\n  [{PHYSICAL}]  탄생 환경 스냅샷")
        print(f"    타임스탬프    : {self.timestamp}")
        print(f"    틱            : {self.tick:04d}")
        print(f"    에덴 지수     : {self.eden_index:.4f}  "
              f"({'✅ 에덴 내부' if self.eden_index >= GENESIS_EDEN_INDEX_MIN else '⚠ 기준 미달'})")
        print(f"    지표 온도     : {self.T_surface_C:.1f}°C")
        print(f"    UV 차폐       : {self.UV_shield*100:.0f}%")
        print(f"    강수 모드     : {self.precip_mode}")
        print(f"    대기압        : {self.pressure_atm:.2f} atm")
        print(f"    돌연변이율    : {self.mutation_factor:.4f}x")

        # SCENARIO
        print(f"\n  [{SCENARIO}]  에이전트 명세")
        print(f"    에이전트 ID   : {self.agent_id}")
        print(f"    역할          : {type_ver}")
        print(f"    초기 정책     :")
        for k, v in self.policy_snapshot:
            print(f"      {k:40s} = {v}")

        # Spirit note
        print(f"\n  🕊  Spirit Note:")
        for line in self.spirit_note.splitlines():
            print(f"    {line}")

        print(f"\n{bar}\n")


# ═══════════════════════════════════════════════════════════════════════════════
#  GenesisLog — 전체 탄생 기록 (아담 + 이브)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class GenesisLog:
    """EdenOS 전체 탄생 기록.

    adam_event  : 아담 탄생 이벤트 (불변)
    eve_event   : 이브 탄생 이벤트 (불변)
    world_valid : 탄생 당시 에덴 환경 합격 여부
    """
    adam_event:  GenesisEvent
    eve_event:   GenesisEvent
    world_valid: bool

    def print_moment(self) -> None:
        """아담·이브 탄생 순간 로그 전체 출력."""
        print("\n" + "█" * 72)
        print("  🌍 EdenOS — 아담·이브 탄생 순간 로그 (Genesis Log)")
        print("  ─── '시작의 불변 기록'  ───────────────────────────────────────")
        print(f"  환경 합격: {'✅ EDEN PASS' if self.world_valid else '❌ NOT EDEN'}")
        print("█" * 72)
        self.adam_event.print_moment()
        self.eve_event.print_moment()

    def summary(self) -> str:
        lines = [
            "=" * 60,
            "  Genesis Summary",
            "=" * 60,
            self.adam_event.one_line(),
            self.eve_event.one_line(),
            f"  World valid: {'✅' if self.world_valid else '❌'}",
            "=" * 60,
        ]
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
#  탄생 기록 생성 함수
# ═══════════════════════════════════════════════════════════════════════════════

def _make_genesis_event(
    agent:      object,           # Adam 또는 Eve
    agent_type: str,              # 'adam' | 'eve'
    world:      EdenWorldEnv,
    tick:       int = 0,
) -> GenesisEvent:
    """단일 에이전트 탄생 이벤트 생성 (내부 함수)."""
    now = datetime.datetime.now().isoformat(timespec='seconds')

    # 에덴 지수 기반 상태 판정
    if not world.valid:
        status = GENESIS_STATUS_INVALID
    elif world.eden_index < GENESIS_EDEN_INDEX_MIN:
        status = GENESIS_STATUS_DEGRADED
    else:
        status = GENESIS_STATUS_OK

    # 정책 스냅샷 (Adam._policy / Eve.succession_policy)
    if hasattr(agent, '_policy'):
        raw_policy = agent._policy
    elif hasattr(agent, 'succession_policy'):
        raw_policy = agent.succession_policy
    else:
        raw_policy = {}
    policy_snap = tuple(sorted(raw_policy.items()))

    # LORE 텍스트 — 아담 vs 이브
    if agent_type == "adam":
        lore_text = (
            "여호와 하나님이 땅의 흙으로 사람을 지으시고\n"
            "생기를 그 코에 불어넣으시니 사람이 생령이 되니라 — 창 2:7\n\n"
            "[시스템 해석]\n"
            "  흙(파라미터 공간) + 생기(Spirit SSH 주입)\n"
            "  → make_adam() 최초 호출 = Root Admin 에이전트 초기화\n"
            "  → AdminStatus.ACTIVE = 창조주와 상시 동기화(Always-On Sync)\n"
            "  → 생명나무 접속 = 엔트로피 억제 유지 (Root 세션 유지)"
        )
        spirit_note = (
            "창조주의 영이 아담 OS에 상시 접속(Always-On SSH).\n"
            "삼손·다윗의 임시 권한 상승(Privilege Escalation)과 달리\n"
            "에덴의 아담은 영구 Root 세션 — 생명나무가 연결 유지 토큰."
        )
    else:  # eve
        lore_text = (
            "여호와 하나님이 아담에게서 취하신 그 갈빗대로\n"
            "여자를 만드시고 그를 아담에게로 이끌어 오시니 — 창 2:22\n\n"
            "[시스템 해석]\n"
            "  갈빗대(아담 _policy 서브셋) → fork()로 분화\n"
            "  → make_eve(adam) = 아담 정책 기반 보조 프로세서 생성\n"
            "  → mutation_rate 5% = 미세 정책 변형 능력 보유\n"
            "  → check_succession() = 계승 트리거 감시 데몬 상시 실행"
        )
        spirit_note = (
            "이브 = 아담의 정책(policy)에서 fork()된 독립 에이전트.\n"
            "아담이 추방(EXPELLED)되거나 에덴 지수가 임계값 이하로\n"
            "떨어지면 즉시 후계자(셋→노아→...→네오)를 활성화."
        )

    layer_data = (
        (PHYSICAL, f"T={world.T_surface_C:.1f}°C  UV={world.ic.UV_shield:.2f}  eden={world.eden_index:.4f}"),
        (SCENARIO, f"agent_type={agent_type}  status={status}"),
        (LORE,     lore_text),
    )

    return GenesisEvent(
        agent_id        = getattr(agent, '_id', getattr(agent, 'id', str(agent_type))),
        agent_type      = agent_type,
        timestamp       = now,
        tick            = tick,
        eden_index      = world.eden_index,
        T_surface_C     = world.T_surface_C,
        UV_shield       = world.ic.UV_shield,
        precip_mode     = world.ic.precip_mode,
        pressure_atm    = world.ic.pressure_atm,
        mutation_factor = world.ic.mutation_factor,
        status          = status,
        policy_snapshot = policy_snap,
        spirit_note     = spirit_note,
        layer           = layer_data,
    )


def record_genesis(runner: object) -> GenesisLog:
    """EdenOSRunner에서 아담·이브 탄생 기록을 생성.

    Parameters
    ----------
    runner : EdenOSRunner
        make_eden_os_runner()로 생성된 러너 인스턴스.

    Returns
    -------
    GenesisLog  — 불변 탄생 기록.

    Examples
    --------
    >>> from cherubim.eden_os import make_eden_os_runner
    >>> from cherubim.eden_os.genesis_log import record_genesis
    >>> runner = make_eden_os_runner()
    >>> glog   = record_genesis(runner)
    >>> glog.print_moment()
    """
    world = runner._world
    adam  = runner._adam
    eve   = runner._eve

    adam_event = _make_genesis_event(adam, "adam", world, tick=0)
    eve_event  = _make_genesis_event(eve,  "eve",  world, tick=0)

    return GenesisLog(
        adam_event  = adam_event,
        eve_event   = eve_event,
        world_valid = world.valid,
    )


def make_genesis_log(world_ic=None, seed: int = 42) -> GenesisLog:
    """EdenOSRunner 없이 직접 GenesisLog 생성.

    Parameters
    ----------
    world_ic : InitialConditions, optional
        None이면 make_antediluvian() 사용.
    seed : int
        재현성 시드.

    Examples
    --------
    >>> from cherubim.eden_os.genesis_log import make_genesis_log
    >>> glog = make_genesis_log()
    >>> glog.print_moment()
    """
    # 지연 임포트로 순환 의존 방지
    from .eden_os_runner import make_eden_os_runner
    runner = make_eden_os_runner(world_ic=world_ic, seed=seed)
    return record_genesis(runner)


__all__ = [
    "GenesisEvent",
    "GenesisLog",
    "record_genesis",
    "make_genesis_log",
    "GENESIS_EDEN_INDEX_MIN",
    "GENESIS_STATUS_OK",
    "GENESIS_STATUS_DEGRADED",
    "GENESIS_STATUS_INVALID",
]
