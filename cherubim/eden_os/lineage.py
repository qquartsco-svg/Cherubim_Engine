"""eden_os.lineage — 계승 그래프  (Step 6 / 7)

"아담이 셋을 낳은 후 팔백 년을 지내며 자녀들을 낳았으며"
— 창세기 5:4

역할
────
  관리자 계승 흐름을 **방향 그래프**로 기록하고,
  각 세대의 정책·수명·계승 이유를 로그로 보존한다.

  이것이 '아담 → 네오' 계보의 코드 구현체다.

  매트릭스 비유:
    아담(v1) → 셋(v2) → ... → 네오(vN)
    각 세대 = 이전 세대 정책의 변형(mutation) 버전
    네오(선택받은 자) = 계승 체인의 최적화된 최신 버전

LineageNode
──────────────────────────────────────────────
  agent_id  : 에이전트 고유 ID
  generation: 세대 번호 (아담=1, 셋=2, ...)
  policy    : 해당 세대 의사결정 정책
  born_tick : 생성 틱
  died_tick : 소멸 틱 (None = 현재 활성)
  succession_trigger: 계승을 발동한 이유

LineageEdge
──────────────────────────────────────────────
  parent → child  (방향)
  inherit_rate    : 정책 계승 비율

빠른 시작
──────────────────────────────────────────────
  from cherubim.eden_os import LineageGraph, make_lineage
  graph = make_lineage()
  graph.add_generation("adam", policy=adam._policy, born_tick=0)
  event = SuccessionEvent(...)
  neo = graph.succeed(event, current_tick=50)
  graph.print_tree()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .adam import make_adam, Adam
from .eve import SuccessionEvent

# ── 레이어 상수 ──────────────────────────────────────────────────────────────
PHYSICAL = "PHYSICAL_FACT"
SCENARIO  = "SCENARIO"
LORE      = "LORE"

# 세대별 LORE 이름 (아담 계보 + 매트릭스 계승)
GENERATION_NAMES_LORE: List[str] = [
    "아담(Adam)",     # 1세대
    "셋(Seth)",       # 2세대
    "에노스(Enos)",   # 3세대
    "게난(Kenan)",    # 4세대
    "마할랄렐",       # 5세대
    "야렛(Jared)",    # 6세대
    "에녹(Enoch)",    # 7세대
    "므두셀라",       # 8세대
    "라멕(Lamech)",   # 9세대
    "노아(Noah)",     # 10세대
    "네오(Neo)",      # 계보 완성 — 선택받은 자
]


# ═══════════════════════════════════════════════════════════════════════════════
#  LineageNode — 계보 그래프의 한 노드(세대)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class LineageNode:
    """한 세대 관리자의 정보."""
    agent_id:           str
    generation:         int           # 1부터 시작
    policy:             Dict          # 해당 세대 정책
    born_tick:          int
    died_tick:          Optional[int] = None
    succession_trigger: str           = ""   # 이 세대가 끝난 이유
    name_lore:          str           = ""   # LORE 이름

    @property
    def is_active(self) -> bool:
        return self.died_tick is None

    @property
    def lifespan_ticks(self) -> Optional[int]:
        if self.died_tick is not None:
            return self.died_tick - self.born_tick
        return None

    def __str__(self) -> str:
        alive = "활성" if self.is_active else f"종료(tick={self.died_tick})"
        return (
            f"Gen{self.generation:02d}  {self.name_lore or self.agent_id:<12}  "
            f"born={self.born_tick}  {alive}  trigger='{self.succession_trigger}'"
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  LineageEdge — 계보 연결
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class LineageEdge:
    """두 세대 관리자 간 계승 연결."""
    parent_id:    str
    child_id:     str
    tick:         int            # 계승 발생 틱
    inherit_rate: float = 1.0    # 정책 계승 비율 (0=완전 새 정책, 1=완전 계승)
    trigger:      str  = ""      # 계승 트리거 코드

    def __str__(self) -> str:
        return (
            f"LineageEdge({self.parent_id} → {self.child_id}  "
            f"tick={self.tick}  inherit={self.inherit_rate:.2f}  "
            f"trigger='{self.trigger}')"
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  LineageGraph — 계승 방향 그래프
# ═══════════════════════════════════════════════════════════════════════════════

class LineageGraph:
    """관리자 계승 방향 그래프.

    구조
    ────
      아담(Gen1) → 셋(Gen2) → 에노스(Gen3) → ... → 네오(GenN)
      각 노드: 정책 / 수명 / 계승 이유
      각 엣지: 계승 틱 / 정책 계승 비율
    """

    def __init__(self) -> None:
        self._nodes:  Dict[str, LineageNode] = {}
        self._edges:  List[LineageEdge]      = []
        self._active: Optional[str]          = None   # 현재 활성 관리자 ID
        self._tick    = 0

    # ── 세대 추가 ─────────────────────────────────────────────────────────────

    def add_generation(
        self,
        agent_id:           str,
        policy:             Dict,
        born_tick:          int,
        succession_trigger: str = "",
        name_lore:          str = "",
    ) -> LineageNode:
        """새 세대 노드 추가."""
        gen = len(self._nodes) + 1
        if not name_lore and gen <= len(GENERATION_NAMES_LORE):
            name_lore = GENERATION_NAMES_LORE[gen - 1]

        node = LineageNode(
            agent_id           = agent_id,
            generation         = gen,
            policy             = dict(policy),
            born_tick          = born_tick,
            succession_trigger = succession_trigger,
            name_lore          = name_lore,
        )
        self._nodes[agent_id] = node
        self._active = agent_id
        return node

    # ── 계승 실행 ─────────────────────────────────────────────────────────────

    def succeed(
        self,
        event:        SuccessionEvent,
        current_tick: int,
    ) -> Adam:
        """계승 이벤트 → 다음 세대 Adam 생성.

        1. 현재 활성 노드를 종료 처리
        2. 변형된 정책으로 새 노드 추가
        3. LineageEdge 연결
        4. 새 Adam 인스턴스 반환

        Returns
        -------
        Adam  —  다음 세대 관리자 (네오)
        """
        # 이전 세대 종료
        if self._active and self._active in self._nodes:
            prev = self._nodes[self._active]
            prev.died_tick          = current_tick
            prev.succession_trigger = event.trigger

        # 새 세대 ID & 정책
        gen_num    = len(self._nodes) + 1
        new_id     = f"successor_{gen_num:02d}"
        new_policy = event.mutated_policy

        new_node = self.add_generation(
            agent_id           = new_id,
            policy             = new_policy,
            born_tick          = current_tick,
            succession_trigger = "",
        )

        # 엣지 연결
        edge = LineageEdge(
            parent_id    = event.from_agent,
            child_id     = new_id,
            tick         = current_tick,
            inherit_rate = 1.0 - 0.05,   # 95% 계승 (5% 변형)
            trigger      = event.trigger,
        )
        self._edges.append(edge)

        # 새 Adam 인스턴스 생성
        new_adam = make_adam(agent_id=new_id, decision_policy=new_policy)
        return new_adam

    # ── 조회 ──────────────────────────────────────────────────────────────────

    def current(self) -> Optional[LineageNode]:
        """현재 활성 세대 노드."""
        if self._active:
            return self._nodes.get(self._active)
        return None

    def all_nodes(self) -> List[LineageNode]:
        return list(self._nodes.values())

    def all_edges(self) -> List[LineageEdge]:
        return list(self._edges)

    def depth(self) -> int:
        """계보 깊이 (세대 수)."""
        return len(self._nodes)

    def step(self, tick: int = 1) -> None:
        self._tick += tick

    # ── 출력 ──────────────────────────────────────────────────────────────────

    def print_tree(self) -> None:
        width = 68
        print("=" * width)
        print("  🌿 계승 그래프 (LineageGraph)")
        print("=" * width)
        print(f"  세대 수: {self.depth()}  |  엣지 수: {len(self._edges)}")
        print(f"  현재 활성: {self._active or '없음'}")

        print(f"\n  {'─'*64}")
        print(f"  {'세대':>5}  {'이름/ID':<14}  {'born':>5}  {'died':>5}  계승 사유")
        print(f"  {'─'*64}")
        for node in self.all_nodes():
            died  = str(node.died_tick) if node.died_tick is not None else "활성"
            trig  = node.succession_trigger or "-"
            mark  = "★" if node.is_active else " "
            print(
                f"  {mark} Gen{node.generation:02d}  "
                f"{(node.name_lore or node.agent_id):<14}  "
                f"{node.born_tick:>5}  {died:>5}  {trig}"
            )

        if self._edges:
            print(f"\n  계승 엣지:")
            for edge in self._edges:
                print(f"    {edge}")

        print(f"\n  [{LORE}]")
        print("    아담 → 셋 → ... → 노아 → ... → 네오")
        print("    각 세대 = 이전 정책의 변형(mutation) 계승")
        print("    네오 = 계보 체인의 최적화된 최신 관리자")
        print("    (매트릭스: 선택받은 자 = 시스템 관리자 재활성화)")
        print("=" * width)


# ═══════════════════════════════════════════════════════════════════════════════
#  공개 팩토리
# ═══════════════════════════════════════════════════════════════════════════════

def make_lineage() -> LineageGraph:
    """LineageGraph 생성.

    Examples
    --------
    >>> graph = make_lineage()
    >>> graph.add_generation("adam", policy=adam._policy, born_tick=0)
    >>> # ... 시뮬레이션 후 계승 이벤트 발생 시:
    >>> new_adam = graph.succeed(succession_event, current_tick=50)
    >>> graph.print_tree()
    """
    return LineageGraph()
