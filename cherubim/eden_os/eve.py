"""eden_os.eve — 에덴 시스템 관리자 v2 + 계승 트리거  (Step 5b / 7)

"여호와 하나님이 이르시되 사람이 혼자 사는 것이 좋지 아니하니
 내가 그를 위하여 돕는 배필을 지으리라 하시니라"
— 창세기 2:18

역할
────
  이브(Eve) = 아담의 보조 프로세서 + 계승 트리거.

  아담(Adam) 이 전체 환경 관찰·관리에 집중할 때,
  이브는 두 가지 추가 역할을 담당한다:

  1. 정책 변형 (Policy Mutation)
     아담의 의사결정 정책(policy)을 소폭 변형하여
     다음 세대 관리자가 더 나은 정책을 갖도록 진화시킨다.
     → lineage.py 에서 계승 시 정책이 이어진다.

  2. 계승 트리거 (Succession Trigger)
     아담이 추방(EXPELLED)되거나,
     환경이 임계값 이하로 악화되면
     이브가 계승 이벤트를 발동시킨다.
     → lineage.py 가 다음 세대(successor)를 생성한다.

에이전트 루프 (Adam 과 동일 인터페이스)
──────────────────────────────────────────────
  observe(world)  →  Observation (Adam 과 동일 형식)
  decide(obs)     →  Intent      (공유 의도 공간)
  act(intent)     →  ActionResult

계승 트리거 조건 (CONFIG 기반)
──────────────────────────────────────────────
  adam_expelled        : 아담이 추방됨 → 즉시 계승
  eden_index_below     : 에덴 지수 < 0.3 → 계승 검토
  consecutive_fail     : 연속 N번 실패 → 계승 트리거

레이어 분리
──────────────────────────────────────────────
  PHYSICAL_FACT : 환경 관찰값 (Adam 과 공유)
  SCENARIO      : 계승 트리거 조건 (CONFIG 기반)
  LORE          : 이브 역할·창세기 해석

빠른 시작
──────────────────────────────────────────────
  from cherubim.eden_os import Adam, Eve, make_adam, make_eve
  adam = make_adam()
  eve  = make_eve(adam)
  succession = eve.check_succession(adam, obs)
  print(succession)
"""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .eden_world import EdenWorldEnv
from .adam import Adam, AdminStatus, Observation, Intent, ActionResult, make_adam
from .cherubim_guard import CherubimGuard
from .tree_of_life import TreeOfLife, KnowledgeTree

# ── 레이어 상수 ──────────────────────────────────────────────────────────────
PHYSICAL = "PHYSICAL_FACT"
SCENARIO  = "SCENARIO"
LORE      = "LORE"


# ═══════════════════════════════════════════════════════════════════════════════
#  SuccessionEvent — 계승 이벤트
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class SuccessionEvent:
    """계승 발동 이벤트."""
    tick:          int
    trigger:       str         # 트리거 코드 (adam_expelled, eden_degraded 등)
    from_agent:    str         # 이전 관리자 ID
    reason:        str
    mutated_policy: Dict       # 계승 시 적용될 변형 정책
    log_entry:     str

    def __str__(self) -> str:
        return (
            f"SuccessionEvent(tick={self.tick}  trigger={self.trigger}  "
            f"from={self.from_agent}  '{self.reason}')"
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  Eve — 보조 프로세서 + 계승 트리거
# ═══════════════════════════════════════════════════════════════════════════════

class Eve:
    """에덴 시스템 관리자 v2 — 이브.

    Parameters
    ----------
    adam : Adam
        연결된 아담 에이전트.
    succession_policy : dict, optional
        계승 트리거 조건.  None 이면 DEFAULT_SUCCESSION_POLICY 사용.
    mutation_rate : float
        정책 변형 강도 [0~1].  0 = 완전 복사, 1 = 완전 무작위.
    seed : int, optional
        재현성을 위한 난수 시드.
    """

    DEFAULT_SUCCESSION_POLICY: Dict = {
        "trigger_if_adam_expelled":   True,
        "trigger_if_eden_index_below": 0.30,
        "trigger_if_consecutive_fail": 5,
    }

    def __init__(
        self,
        adam:              Adam,
        agent_id:          str = "eve",
        succession_policy: Optional[Dict] = None,
        mutation_rate:     float = 0.05,
        seed:              Optional[int] = None,
    ) -> None:
        self._id       = agent_id
        self._adam     = adam
        self._s_policy = succession_policy or dict(self.DEFAULT_SUCCESSION_POLICY)
        self._mut_rate = mutation_rate
        self._rng      = random.Random(seed)
        self._tick     = 0
        self._consec_fail = 0
        self._succession_events: List[SuccessionEvent] = []
        self._log: List[str] = []

    # ── 속성 ──────────────────────────────────────────────────────────────────

    @property
    def id(self) -> str:
        return self._id

    @property
    def succession_events(self) -> List[SuccessionEvent]:
        return list(self._succession_events)

    # ── 에이전트 루프 (Adam 과 동일 인터페이스) ────────────────────────────────

    def observe(
        self,
        world: EdenWorldEnv,
        tree:  Optional[TreeOfLife] = None,
        river_flow_total: float = 0.0,
    ) -> Observation:
        """환경 관찰 — Adam 과 동일한 Observation 형식."""
        return self._adam.observe(world, tree, river_flow_total)

    def decide(self, obs: Observation) -> Intent:
        """의도 결정.

        이브는 아담 정책을 따르되,
        계승 트리거 조건 감시를 추가로 수행한다.
        """
        # 아담이 정상이면 아담 결정을 따름
        if self._adam.is_active:
            return self._adam.decide(obs)
        # 아담이 추방되면 이브가 독자 판단
        return Intent("trigger_succession", "아담 추방 감지 — 계승 발동", 1.0)

    def act(
        self,
        intent: Intent,
        guard:     Optional[CherubimGuard] = None,
        life_tree: Optional[TreeOfLife]    = None,
        know_tree: Optional[KnowledgeTree] = None,
    ) -> ActionResult:
        """행동 실행 — 계승 트리거 포함."""
        if intent.code == "trigger_succession":
            # 계승은 lineage.py 에서 처리 — 여기서는 이벤트만 기록
            entry = f"[tick={self._tick:04d}]  EVE  trigger_succession  '{intent.reason}'"
            self._log.append(entry)
            from dataclasses import fields as dc_fields
            return ActionResult(
                tick      = self._tick,
                agent_id  = self._id,
                intent    = intent,
                success   = True,
                effect    = {"succession_triggered": True},
                log_entry = entry,
            )
        # 그 외 의도는 아담에게 위임
        return self._adam.act(intent, guard, life_tree, know_tree)

    # ── 계승 감시 ─────────────────────────────────────────────────────────────

    def check_succession(
        self,
        adam: Adam,
        obs:  Observation,
    ) -> Optional[SuccessionEvent]:
        """계승 트리거 조건 검사.

        조건 충족 시 SuccessionEvent 반환, 아니면 None.
        """
        trigger = None
        reason  = ""

        # 조건 1: 아담 추방
        if self._s_policy.get("trigger_if_adam_expelled") and adam.is_expelled:
            trigger = "adam_expelled"
            reason  = "아담 추방 — 선악과 섭취 후 관리자 권한 박탈"

        # 조건 2: 에덴 지수 임계값 이하
        elif obs.eden_index < self._s_policy.get("trigger_if_eden_index_below", 0.30):
            trigger = "eden_degraded"
            reason  = f"에덴 지수 {obs.eden_index:.3f} — 임계값 이하"

        # 조건 3: 연속 실패
        elif self._consec_fail >= self._s_policy.get("trigger_if_consecutive_fail", 5):
            trigger = "consecutive_fail"
            reason  = f"연속 {self._consec_fail}회 실패"

        if trigger is None:
            return None

        # 계승 정책 변형 (mutation)
        mutated = self._mutate_policy(adam)

        event = SuccessionEvent(
            tick           = self._tick,
            trigger        = trigger,
            from_agent     = adam.id,
            reason         = reason,
            mutated_policy = mutated,
            log_entry      = (
                f"[tick={self._tick:04d}]  SUCCESSION  trigger={trigger}  "
                f"from={adam.id}  '{reason}'"
            ),
        )
        self._succession_events.append(event)
        self._log.append(event.log_entry)
        return event

    def _mutate_policy(self, adam: Adam) -> Dict:
        """아담의 정책을 소폭 변형하여 다음 세대 정책 생성.

        mutation_rate = 0.05 → 각 수치 파라미터를 ±5% 범위에서 변형.
        이것이 '세대 간 정책 진화' 메커니즘이다.
        """
        base = dict(adam._policy)
        mutated = {}
        for k, v in base.items():
            if isinstance(v, (int, float)):
                delta = v * self._mut_rate * (self._rng.random() * 2 - 1)
                mutated[k] = round(v + delta, 4)
            else:
                mutated[k] = v
        return mutated

    def record_fail(self) -> None:
        """연속 실패 카운터 증가."""
        self._consec_fail += 1

    def reset_fail(self) -> None:
        """연속 실패 카운터 초기화 (성공 시)."""
        self._consec_fail = 0

    def step(self, tick: int = 1) -> None:
        self._tick += tick

    # ── 출력 ──────────────────────────────────────────────────────────────────

    def get_log(self) -> List[str]:
        return list(self._log)

    def print_summary(self) -> None:
        print("\n" + "=" * 60)
        print(f"  👤 Eve — 보조 프로세서 + 계승 트리거")
        print("=" * 60)
        print(f"  ID              : {self._id}")
        print(f"  연결된 아담     : {self._adam.id}")
        print(f"  계승 이벤트 수  : {len(self._succession_events)}")
        print(f"  연속 실패 횟수  : {self._consec_fail}")
        print(f"  정책 변형 강도  : {self._mut_rate:.2%}")

        print(f"\n  [{SCENARIO}]  계승 트리거 조건")
        for k, v in self._s_policy.items():
            print(f"    {k:<35}: {v}")

        print(f"\n  [{LORE}]")
        print("    이브 = '돕는 배필' = 분산 병렬 처리 보조 프로세서")
        print("    계승 트리거 = 새 세대 관리자 호출 (네오 프로토콜)")
        print("    정책 변형 = 세대 간 관리 전략 진화")

        if self._succession_events:
            print(f"\n  계승 이벤트 목록:")
            for ev in self._succession_events:
                print(f"    {ev}")

        print(f"\n  최근 로그 (최대 5건):")
        for line in self._log[-5:]:
            print(f"    {line}")
        print("=" * 60)


# ═══════════════════════════════════════════════════════════════════════════════
#  공개 팩토리
# ═══════════════════════════════════════════════════════════════════════════════

def make_eve(
    adam:              Optional[Adam] = None,
    agent_id:          str = "eve",
    succession_policy: Optional[Dict] = None,
    mutation_rate:     float = 0.05,
    seed:              Optional[int] = 42,
) -> Eve:
    """Eve 에이전트 생성.

    Parameters
    ----------
    adam : Adam, optional  — None 이면 make_adam() 사용

    Examples
    --------
    >>> adam = make_adam()
    >>> eve  = make_eve(adam)
    >>> event = eve.check_succession(adam, obs)
    """
    if adam is None:
        adam = make_adam()
    return Eve(
        adam              = adam,
        agent_id          = agent_id,
        succession_policy = succession_policy,
        mutation_rate     = mutation_rate,
        seed              = seed,
    )
