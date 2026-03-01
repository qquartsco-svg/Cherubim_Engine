"""eden_os.tree_of_life — 생명나무 상태 머신  (Step 3 / 7)

"동산 중앙에는 생명나무와 선악을 알게 하는 나무도 있더라"
— 창세기 2:9

역할
────
  생명나무(Tree of Life) 와 선악과(Tree of Knowledge) 를
  접근 조건이 있는 **상태 머신**으로 모델링한다.

  물리 해석 (SCENARIO 레이어):
    생명나무  = 생물학적 엔트로피 억제기
               접속 중 → 돌연변이율 0.01x 유지 (에덴 기준)
               접속 해제 → 엔트로피 상승, 수명 감소

    선악과    = 루트 전용 시스템 API
               호출 시 → 관리자 권한 박탈 + 악성 코드(엔트로피) 주입
               결과   → 생명나무 접근 차단 (체루빔 배치)

상태 전이 (TreeState)
──────────────────────────────────────────────
  AVAILABLE   → ACCESSED   (관리자가 접근)
  ACCESSED    → AVAILABLE  (관리자가 이탈)
  AVAILABLE   → LOCKED     (체루빔 가드가 차단)
  LOCKED      → (복구 불가 — 대홍수 이후 상태)

  선악과 (KnowledgeTree):
  INTACT      → CONSUMED   (금지 API 호출)
  CONSUMED    → (비가역 — 한 번 먹으면 되돌릴 수 없음)

레이어 분리
──────────────────────────────────────────────
  PHYSICAL_FACT : 접근 조건·효과 수치 (파라미터 주입)
  SCENARIO      : 상태 전이 규칙 (CONFIG 기반)
  LORE          : 나무 이름·창세기 해석 (서사 맥락)

빠른 시작
──────────────────────────────────────────────
  from cherubim.eden_os import TreeOfLife, KnowledgeTree, make_trees
  life_tree, know_tree = make_trees()
  life_tree.print_summary()
  result = life_tree.access(agent_id="adam")
  print(result)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from .eden_world import EdenWorldEnv

# ── 레이어 상수 ──────────────────────────────────────────────────────────────
PHYSICAL = "PHYSICAL_FACT"
SCENARIO  = "SCENARIO"
LORE      = "LORE"


# ═══════════════════════════════════════════════════════════════════════════════
#  상태 열거형
# ═══════════════════════════════════════════════════════════════════════════════

class TreeState(Enum):
    AVAILABLE = "available"   # 접근 가능
    ACCESSED  = "accessed"    # 현재 접속 중
    LOCKED    = "locked"      # 체루빔이 차단 (복구 불가)
    REMOVED   = "removed"     # 대홍수로 소멸

class KnowledgeState(Enum):
    INTACT   = "intact"    # 손대지 않음
    CONSUMED = "consumed"  # 금지 API 호출됨 (비가역)


# ═══════════════════════════════════════════════════════════════════════════════
#  AccessResult — 접근 시도 결과
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class AccessResult:
    """생명나무 접근 시도 결과."""
    allowed:          bool
    agent_id:         str
    state_before:     TreeState
    state_after:      TreeState
    effect:           Dict            # 적용된 효과 (허용된 경우)
    reason:           str             # 허용/거부 사유
    log_entry:        str             # 로그 한 줄 요약

    def __str__(self) -> str:
        mark = "✅ ALLOW" if self.allowed else "🚫 DENY"
        return f"AccessResult({mark}  agent={self.agent_id}  {self.reason})"


@dataclass(frozen=True)
class KnowledgeAccessResult:
    """선악과 접근(호출) 결과."""
    agent_id:     str
    state_before: KnowledgeState
    state_after:  KnowledgeState
    entropy_injected: float   # 주입된 엔트로피 (돌연변이율 증가량)
    log_entry:    str


# ═══════════════════════════════════════════════════════════════════════════════
#  TreeEffect — 생명나무 접속 효과
# ═══════════════════════════════════════════════════════════════════════════════

# 기본 효과 (파라미터 주입 가능)
DEFAULT_TREE_EFFECT: Dict = {
    "mutation_suppression": 0.99,   # 돌연변이율 99% 억제
    "lifespan_multiplier":  10.0,   # 수명 10배
    "entropy_drain":        0.001,  # 엔트로피 감소율 (접속 중 매 틱)
    "healing_rate":         1.0,    # 손상 복구율
}

# 선악과 섭취 시 페널티
KNOWLEDGE_PENALTY: Dict = {
    "entropy_injection": 1.0,       # 돌연변이율 1.0 (최대)로 상승
    "lifespan_multiplier": 0.1,     # 수명 10%로 감소
    "admin_revoked": True,          # 관리자 권한 박탈
}


# ═══════════════════════════════════════════════════════════════════════════════
#  TreeOfLife — 생명나무 상태 머신
# ═══════════════════════════════════════════════════════════════════════════════

class TreeOfLife:
    """생명나무 상태 머신.

    Config 파라미터
    ────────────────
    access_condition : dict
        접근 허용 조건.  기본: 관리자 권한 보유 + 체루빔 미차단.
    effect : dict
        접속 시 적용 효과.  기본: DEFAULT_TREE_EFFECT.
    """

    def __init__(
        self,
        world:            Optional[EdenWorldEnv] = None,
        access_condition: Optional[Dict] = None,
        effect:           Optional[Dict] = None,
    ) -> None:
        self._world  = world
        self._state  = TreeState.AVAILABLE
        self._condition = access_condition or {
            "requires_admin":    True,    # 관리자 권한 필요
            "requires_unlocked": True,    # LOCKED 상태면 접근 불가
        }
        self._effect = effect or DEFAULT_TREE_EFFECT
        self._accessed_by: Optional[str] = None
        self._log: List[str] = []
        self._tick = 0

    # ── 상태 조회 ─────────────────────────────────────────────────────────────

    @property
    def state(self) -> TreeState:
        return self._state

    @property
    def is_available(self) -> bool:
        return self._state == TreeState.AVAILABLE

    @property
    def is_accessed(self) -> bool:
        return self._state == TreeState.ACCESSED

    @property
    def is_locked(self) -> bool:
        return self._state in (TreeState.LOCKED, TreeState.REMOVED)

    # ── 접근 시도 ─────────────────────────────────────────────────────────────

    def access(self, agent_id: str, is_admin: bool = True) -> AccessResult:
        """생명나무 접근 시도.

        Parameters
        ----------
        agent_id : str    —  접근 에이전트 ID
        is_admin : bool   —  관리자 권한 보유 여부

        Returns
        -------
        AccessResult  —  허용/거부 + 적용 효과
        """
        before = self._state

        # 거부 조건 확인
        if self._state == TreeState.LOCKED:
            return self._deny(agent_id, before, "체루빔이 접근을 차단함 (LOCKED)")
        if self._state == TreeState.REMOVED:
            return self._deny(agent_id, before, "생명나무가 소멸됨 (REMOVED)")
        if self._condition.get("requires_admin") and not is_admin:
            return self._deny(agent_id, before, "관리자 권한 없음")
        if self._state == TreeState.ACCESSED and self._accessed_by != agent_id:
            return self._deny(agent_id, before, f"이미 {self._accessed_by}가 접속 중")

        # 허용
        self._state = TreeState.ACCESSED
        self._accessed_by = agent_id
        entry = f"[tick={self._tick:04d}] ALLOW  {agent_id} → TreeOfLife"
        self._log.append(entry)

        return AccessResult(
            allowed      = True,
            agent_id     = agent_id,
            state_before = before,
            state_after  = self._state,
            effect       = dict(self._effect),
            reason       = "조건 충족 — 접근 허용",
            log_entry    = entry,
        )

    def release(self, agent_id: str) -> None:
        """접속 해제."""
        if self._state == TreeState.ACCESSED and self._accessed_by == agent_id:
            self._state = TreeState.AVAILABLE
            self._accessed_by = None
            self._log.append(f"[tick={self._tick:04d}] RELEASE  {agent_id} → TreeOfLife")

    def lock(self, reason: str = "체루빔 배치") -> None:
        """생명나무 잠금 (체루빔 가드가 호출).  비가역."""
        if self._state != TreeState.REMOVED:
            self._state = TreeState.LOCKED
            self._accessed_by = None
            self._log.append(
                f"[tick={self._tick:04d}] LOCKED  reason='{reason}'"
            )

    def remove(self) -> None:
        """소멸 (대홍수 이후)."""
        self._state = TreeState.REMOVED
        self._log.append(f"[tick={self._tick:04d}] REMOVED")

    def step(self, tick: int = 1) -> None:
        self._tick += tick

    # ── 내부 ──────────────────────────────────────────────────────────────────

    def _deny(self, agent_id: str, before: TreeState, reason: str) -> AccessResult:
        entry = f"[tick={self._tick:04d}] DENY   {agent_id} → TreeOfLife  ({reason})"
        self._log.append(entry)
        return AccessResult(
            allowed      = False,
            agent_id     = agent_id,
            state_before = before,
            state_after  = self._state,
            effect       = {},
            reason       = reason,
            log_entry    = entry,
        )

    # ── 출력 ──────────────────────────────────────────────────────────────────

    def print_summary(self) -> None:
        state_emoji = {
            TreeState.AVAILABLE: "🌳",
            TreeState.ACCESSED:  "✨",
            TreeState.LOCKED:    "🔒",
            TreeState.REMOVED:   "💀",
        }
        print("\n" + "=" * 60)
        print("  🌳 생명나무 (Tree of Life)")
        print("=" * 60)
        print(f"  상태        : {state_emoji[self._state]} {self._state.value.upper()}")
        print(f"  접속 중     : {self._accessed_by or '없음'}")
        print(f"\n  [{PHYSICAL}]  접속 효과")
        for k, v in self._effect.items():
            print(f"    {k:<26}: {v}")
        print(f"\n  [{SCENARIO}]  접근 조건")
        for k, v in self._condition.items():
            print(f"    {k:<26}: {v}")
        print(f"\n  [{LORE}]")
        print("    '동산 중앙에 있는 생명나무'  (창 2:9)")
        print("    접속 = 엔트로피 억제 = 영생 유지")
        print("    잠금 = 체루빔 배치 이후 (창 3:24)")
        print(f"\n  로그 ({len(self._log)}건):")
        for line in self._log[-5:]:
            print(f"    {line}")
        print("=" * 60)


# ═══════════════════════════════════════════════════════════════════════════════
#  KnowledgeTree — 선악과 상태 머신
# ═══════════════════════════════════════════════════════════════════════════════

class KnowledgeTree:
    """선악과 상태 머신 — 루트 전용 금지 API.

    한 번 호출(섭취)하면 비가역 → CONSUMED 상태.
    """

    def __init__(
        self,
        penalty: Optional[Dict] = None,
    ) -> None:
        self._state   = KnowledgeState.INTACT
        self._penalty = penalty or KNOWLEDGE_PENALTY
        self._log: List[str] = []
        self._tick = 0

    @property
    def state(self) -> KnowledgeState:
        return self._state

    @property
    def is_intact(self) -> bool:
        return self._state == KnowledgeState.INTACT

    def consume(self, agent_id: str) -> KnowledgeAccessResult:
        """금지 API 호출 (선악과 섭취).

        비가역.  호출 즉시 관리자 권한 박탈 + 엔트로피 주입.
        """
        before = self._state
        self._state = KnowledgeState.CONSUMED
        entropy = self._penalty["entropy_injection"]
        entry = (
            f"[tick={self._tick:04d}] CONSUMED  {agent_id} → KnowledgeTree  "
            f"entropy_injected={entropy:.2f}  ⚠ 관리자 권한 박탈"
        )
        self._log.append(entry)

        return KnowledgeAccessResult(
            agent_id          = agent_id,
            state_before      = before,
            state_after       = self._state,
            entropy_injected  = entropy,
            log_entry         = entry,
        )

    def step(self, tick: int = 1) -> None:
        self._tick += tick

    def print_summary(self) -> None:
        intact_emoji = "🍎" if self._state == KnowledgeState.INTACT else "💔"
        print("\n" + "=" * 60)
        print("  🍎 선악을 알게 하는 나무 (Tree of Knowledge)")
        print("=" * 60)
        print(f"  상태   : {intact_emoji} {self._state.value.upper()}")
        print(f"\n  [{PHYSICAL}]  섭취 페널티")
        for k, v in self._penalty.items():
            print(f"    {k:<26}: {v}")
        print(f"\n  [{LORE}]")
        print("    루트(창조주) 전용 API  →  피조물 계정 호출 금지")
        print("    '먹는 날에는 반드시 죽으리라'  (창 2:17)")
        print("    결과: 체루빔 배치 → 에덴 접근 차단 (창 3:24)")
        print(f"\n  로그 ({len(self._log)}건):")
        for line in self._log[-5:]:
            print(f"    {line}")
        print("=" * 60)


# ═══════════════════════════════════════════════════════════════════════════════
#  공개 팩토리
# ═══════════════════════════════════════════════════════════════════════════════

def make_trees(
    world:            Optional[EdenWorldEnv] = None,
    tree_effect:      Optional[Dict] = None,
    knowledge_penalty: Optional[Dict] = None,
) -> Tuple[TreeOfLife, KnowledgeTree]:
    """생명나무 + 선악과 쌍 생성.

    Returns
    -------
    (TreeOfLife, KnowledgeTree)

    Examples
    --------
    >>> life_tree, know_tree = make_trees()
    >>> result = life_tree.access("adam")
    >>> print(result)
    """
    life  = TreeOfLife(world=world, effect=tree_effect)
    know  = KnowledgeTree(penalty=knowledge_penalty)
    return life, know
