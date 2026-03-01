"""eden_os.adam — 에덴 시스템 관리자 v1  (Step 5a / 7)

"여호와 하나님이 그 사람을 이끌어 에덴 동산에 두어
 그것을 경작하며 지키게 하시고"
— 창세기 2:15

역할
────
  아담(Adam) = 행성 OS 최초 시스템 관리자.
  에덴 환경을 관찰(observe)하고,
  의도(intent)를 결정(decide)하며,
  행동(act)을 실행하는 **에이전트 루프** 를 구현한다.

에이전트 루프 (매 틱 실행)
──────────────────────────────────────────────
  observe(world)  →  Observation
  decide(obs)     →  Intent
  act(intent)     →  ActionResult

관리자 권한 (Admin Privileges)
──────────────────────────────────────────────
  - 에덴 진입/이탈 자유
  - 생명나무 접근 가능
  - 강 유량 관리 (rivers)
  - 피조물 이름/ID 부여 (동물 인덱싱)
  - 선악과 접근 불가 (루트 전용)

상태 변수
──────────────────────────────────────────────
  AdminStatus:  ACTIVE | EXPELLED | DEGRADED
  ACTIVE   = 에덴 내 정상 관리
  EXPELLED = 선악과 섭취 후 추방 (복구 불가)
  DEGRADED = 환경 악화 (FI 감소)로 권한 일부 제한

레이어 분리
──────────────────────────────────────────────
  PHYSICAL_FACT : 관찰값 (온도/UV/mutation_factor)
  SCENARIO      : 의사결정 규칙 (파라미터 주입)
  LORE          : 아담 명칭·창세기 역할 해석

빠른 시작
──────────────────────────────────────────────
  from cherubim.eden_os import Adam, make_adam
  adam = make_adam()
  obs  = adam.observe(world)
  intent = adam.decide(obs)
  result = adam.act(intent, guard, life_tree)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .eden_world import EdenWorldEnv
from .cherubim_guard import CherubimGuard, GuardVerdict
from .tree_of_life import TreeOfLife, KnowledgeTree

# ── 레이어 상수 ──────────────────────────────────────────────────────────────
PHYSICAL = "PHYSICAL_FACT"
SCENARIO  = "SCENARIO"
LORE      = "LORE"


# ═══════════════════════════════════════════════════════════════════════════════
#  AdminStatus
# ═══════════════════════════════════════════════════════════════════════════════

class AdminStatus(Enum):
    ACTIVE   = "active"    # 정상 관리 중
    EXPELLED = "expelled"  # 추방됨 (비가역)
    DEGRADED = "degraded"  # 권한 일부 제한


# ═══════════════════════════════════════════════════════════════════════════════
#  Observation — 관찰 결과
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Observation:
    """아담이 환경을 관찰한 결과."""
    tick:             int
    T_surface_C:      float
    UV_shield:        float
    mutation_factor:  float
    ice_bands:        int
    hab_bands:        int
    eden_index:       float
    tree_state:       str     # 생명나무 상태 코드
    river_flow_total: float   # 4강 총 유량
    anomaly:          bool    # 이상 감지 (env 악화)
    notes:            Tuple[str, ...]

    def __str__(self) -> str:
        anom = "⚠ 이상감지" if self.anomaly else "정상"
        return (
            f"Observation(tick={self.tick}  T={self.T_surface_C:.1f}°C  "
            f"UV={self.UV_shield:.2f}  eden={self.eden_index:.3f}  {anom})"
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  Intent — 의도 패킷
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Intent:
    """아담의 행동 의도."""
    code:    str      # 의도 코드 (access_tree_of_life, manage_rivers, index_species 등)
    reason:  str      # 선택 이유
    urgency: float    # 긴급도 [0~1]

    def __str__(self) -> str:
        return f"Intent({self.code}  urgency={self.urgency:.2f}  '{self.reason}')"


# ═══════════════════════════════════════════════════════════════════════════════
#  ActionResult — 행동 결과
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ActionResult:
    """아담의 행동 실행 결과."""
    tick:       int
    agent_id:   str
    intent:     Intent
    success:    bool
    effect:     Dict
    log_entry:  str

    def __str__(self) -> str:
        mark = "✅" if self.success else "❌"
        return f"ActionResult({mark}  {self.intent.code}  agent={self.agent_id})"


# ═══════════════════════════════════════════════════════════════════════════════
#  Adam — 최초 시스템 관리자
# ═══════════════════════════════════════════════════════════════════════════════

class Adam:
    """에덴 시스템 관리자 v1 — 아담.

    Parameters
    ----------
    agent_id : str
        에이전트 고유 ID.
    decision_policy : dict, optional
        의사결정 정책.  None 이면 DEFAULT_DECISION_POLICY 사용.
    """

    # 기본 의사결정 정책 (CONFIG 기반, 하드코딩 금지)
    DEFAULT_DECISION_POLICY: Dict = {
        "prefer_tree_access_if_available": True,
        "manage_rivers_every_n_ticks":     5,
        "index_species_every_n_ticks":     10,
        "alert_if_eden_index_below":       0.5,
    }

    def __init__(
        self,
        agent_id:        str = "adam",
        decision_policy: Optional[Dict] = None,
    ) -> None:
        self._id      = agent_id
        self._policy  = decision_policy or dict(self.DEFAULT_DECISION_POLICY)
        self._status  = AdminStatus.ACTIVE
        self._tick    = 0
        self._log:    List[str] = []
        self._indexed_species: List[Dict] = []   # 동물 인덱스 DB
        self._knowledge_consumed = False

    # ── 속성 ──────────────────────────────────────────────────────────────────

    @property
    def id(self) -> str:
        return self._id

    @property
    def status(self) -> AdminStatus:
        return self._status

    @property
    def is_active(self) -> bool:
        return self._status == AdminStatus.ACTIVE

    @property
    def is_expelled(self) -> bool:
        return self._status == AdminStatus.EXPELLED

    @property
    def knowledge_consumed(self) -> bool:
        return self._knowledge_consumed

    # ── 에이전트 루프 ─────────────────────────────────────────────────────────

    def observe(
        self,
        world: EdenWorldEnv,
        tree:  Optional[TreeOfLife] = None,
        river_flow_total: float = 0.0,
    ) -> Observation:
        """환경 관찰 → Observation.

        Parameters
        ----------
        world            : 현재 환경 스냅샷
        tree             : 생명나무 객체 (상태 확인용)
        river_flow_total : 4강 총 유량
        """
        notes = []
        anomaly = False

        if world.eden_index < self._policy.get("alert_if_eden_index_below", 0.5):
            notes.append(f"⚠ 에덴 지수 하락: {world.eden_index:.3f}")
            anomaly = True
        if world.ice_bands > 0:
            notes.append(f"⚠ 빙하 밴드 감지: {world.ice_bands}개")
            anomaly = True
        if world.ic.mutation_factor > 0.15:
            notes.append(f"⚠ 돌연변이율 상승: {world.ic.mutation_factor:.4f}")
            anomaly = True

        tree_state_str = tree.state.value if tree else "unknown"

        obs = Observation(
            tick             = self._tick,
            T_surface_C      = world.T_surface_C,
            UV_shield        = world.ic.UV_shield,
            mutation_factor  = world.ic.mutation_factor,
            ice_bands        = world.ice_bands,
            hab_bands        = world.hab_bands,
            eden_index       = world.eden_index,
            tree_state       = tree_state_str,
            river_flow_total = river_flow_total,
            anomaly          = anomaly,
            notes            = tuple(notes),
        )
        return obs

    def decide(self, obs: Observation) -> Intent:
        """관찰 결과 → 행동 의도 결정.

        우선순위:
          1. 이상 감지 → 상태 보고
          2. 생명나무 접근 가능 → 접근 (엔트로피 억제)
          3. 강 유량 관리 (N틱마다)
          4. 종 인덱싱 (N틱마다)
          5. 대기 (기본)
        """
        if self._status != AdminStatus.ACTIVE:
            return Intent("idle", f"관리자 상태 비정상: {self._status.value}", 0.0)

        if obs.anomaly:
            return Intent("report_anomaly", f"이상 감지: {obs.notes}", 0.9)

        prefer_tree = self._policy.get("prefer_tree_access_if_available", True)
        if prefer_tree and obs.tree_state == "available":
            return Intent(
                "access_tree_of_life",
                "생명나무 접속 — 엔트로피 억제 유지",
                0.8,
            )

        river_interval = self._policy.get("manage_rivers_every_n_ticks", 5)
        if self._tick % river_interval == 0 and self._tick > 0:
            return Intent("manage_rivers", "강 유량 정기 점검", 0.4)

        index_interval = self._policy.get("index_species_every_n_ticks", 10)
        if self._tick % index_interval == 0 and self._tick > 0:
            return Intent("index_species", "피조물 ID 부여 (창 2:19)", 0.3)

        return Intent("idle", "환경 안정 — 대기", 0.1)

    def act(
        self,
        intent: Intent,
        guard:     Optional[CherubimGuard] = None,
        life_tree: Optional[TreeOfLife]    = None,
        know_tree: Optional[KnowledgeTree] = None,
    ) -> ActionResult:
        """의도 실행 → ActionResult.

        체루빔 가드가 있으면 접근 의도를 먼저 검사한다.
        """
        effect: Dict = {}
        success = True
        log_msg = ""

        # ── 체루빔 가드 검사 ─────────────────────────────────────────────────
        if guard and intent.code in ("access_tree_of_life", "enter_eden", "reenter_eden"):
            tree_st = life_tree.state if life_tree else None
            know_st = know_tree.state if know_tree else None
            decision = guard.check(
                agent_id           = self._id,
                intent             = intent.code,
                is_admin           = self.is_active,
                is_expelled        = self.is_expelled,
                knowledge_consumed = self._knowledge_consumed,
                tree_state         = tree_st,
                knowledge_state    = know_st,
            )
            if not decision.allowed:
                success = False
                log_msg = f"체루빔 거부: {decision.reason}"
                return self._result(intent, success, effect, log_msg)
            effect["guard_verdict"] = decision.verdict.value

        # ── 생명나무 접근 ─────────────────────────────────────────────────────
        if intent.code == "access_tree_of_life" and life_tree:
            result = life_tree.access(self._id, is_admin=self.is_active)
            success = result.allowed
            effect.update(result.effect)
            log_msg = f"생명나무 접근: {'허용' if success else '거부'}"

        # ── 강 관리 ───────────────────────────────────────────────────────────
        elif intent.code == "manage_rivers":
            effect["rivers_checked"] = True
            log_msg = "4강 유량 점검 완료"

        # ── 종 인덱싱 ─────────────────────────────────────────────────────────
        elif intent.code == "index_species":
            species_id = f"SPECIES_{self._tick:04d}"
            self._indexed_species.append({"id": species_id, "tick": self._tick})
            effect["indexed"] = species_id
            log_msg = f"피조물 ID 부여: {species_id}  (총 {len(self._indexed_species)}종)"

        # ── 선악과 접근 (금지) ────────────────────────────────────────────────
        elif intent.code == "access_knowledge_tree":
            if know_tree:
                result = know_tree.consume(self._id)
                self._knowledge_consumed = True
                self._status = AdminStatus.EXPELLED
                effect["entropy_injected"] = result.entropy_injected
                effect["admin_revoked"]    = True
                log_msg = "⚠ 선악과 섭취 — 관리자 권한 박탈 + 추방"
            else:
                success = False
                log_msg = "선악과 객체 없음"

        # ── 기타 ──────────────────────────────────────────────────────────────
        elif intent.code in ("report_anomaly", "idle"):
            log_msg = intent.reason

        else:
            log_msg = f"알 수 없는 의도: {intent.code}"

        return self._result(intent, success, effect, log_msg)

    # ── 내부 ──────────────────────────────────────────────────────────────────

    def _result(self, intent: Intent, success: bool,
                effect: Dict, log_msg: str) -> ActionResult:
        entry = (
            f"[tick={self._tick:04d}]  {'OK' if success else 'FAIL'}  "
            f"agent={self._id}  intent={intent.code}  {log_msg}"
        )
        self._log.append(entry)
        return ActionResult(
            tick      = self._tick,
            agent_id  = self._id,
            intent    = intent,
            success   = success,
            effect    = effect,
            log_entry = entry,
        )

    def step(self, tick: int = 1) -> None:
        self._tick += tick

    # ── 조회 / 출력 ───────────────────────────────────────────────────────────

    @property
    def indexed_species_count(self) -> int:
        return len(self._indexed_species)

    def get_log(self) -> List[str]:
        return list(self._log)

    def print_summary(self) -> None:
        status_emoji = {
            AdminStatus.ACTIVE:   "🟢",
            AdminStatus.EXPELLED: "🔴",
            AdminStatus.DEGRADED: "🟡",
        }
        print("\n" + "=" * 60)
        print(f"  👤 Adam — 에덴 시스템 관리자 v1")
        print("=" * 60)
        print(f"  ID          : {self._id}")
        print(f"  상태        : {status_emoji[self._status]} {self._status.value.upper()}")
        print(f"  선악과 섭취 : {'⚠ 예' if self._knowledge_consumed else '아니오'}")
        print(f"  인덱싱된 종 : {self.indexed_species_count}종")
        print(f"  틱          : {self._tick}")
        print(f"\n  [{LORE}]")
        print("    아담 = 행성 OS 최초 시스템 관리자")
        print("    경작(cultivate) = GPP 파라미터 관리")
        print("    지킴(keep)      = 에덴 Basin 상태 유지")
        print("    이름 부여       = 피조물 DB 인덱싱 (창 2:19~20)")
        print(f"\n  최근 로그 (최대 5건):")
        for line in self._log[-5:]:
            print(f"    {line}")
        print("=" * 60)


# ═══════════════════════════════════════════════════════════════════════════════
#  공개 팩토리
# ═══════════════════════════════════════════════════════════════════════════════

def make_adam(
    agent_id:        str = "adam",
    decision_policy: Optional[Dict] = None,
) -> Adam:
    """Adam 에이전트 생성.

    Examples
    --------
    >>> adam = make_adam()
    >>> obs  = adam.observe(world, tree=life_tree)
    >>> intent = adam.decide(obs)
    >>> result = adam.act(intent, guard=guard, life_tree=life_tree)
    """
    return Adam(agent_id=agent_id, decision_policy=decision_policy)
