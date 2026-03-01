"""eden_os.cherubim_guard — 체루빔 접근 제어  (Step 4 / 7)

"이같이 하나님이 그 사람을 쫓아내시고 에덴 동산 동쪽에
 그룹들과 두루 도는 불 칼을 두어 생명 나무의 길을 지키게 하시니라"
— 창세기 3:24

역할
────
  에덴 동산 진입 + 생명나무 접근을 제어하는 **접근 통제 시스템**.

  물리 해석 (SCENARIO 레이어):
    체루빔   = 에덴 Basin 진입 차단 보안 프로세스
    불 칼    = 다형성 암호화 알고리즘 (모든 방향 순환 차단)
    사방 얼굴 = 4방향 전방위 감시 (N/S/E/W 경계 커버)
    날개 소리 = 활성 감시 신호 (Guard 실행 중 상태)

  GuardDecision:
    ALLOW  : 조건 충족 → 접근 허용
    DENY   : 조건 미충족 → 접근 거부
    SCAN   : 의심 상황 → 재검사 중
    ALERT  : 규칙 위반 탐지 → 경보 발동

CONFIG 기반 룰셋 (하드코딩 금지)
──────────────────────────────────────────────
  모든 접근 규칙은 GuardPolicy 딕셔너리로 주입.
  DEFAULT_POLICY 가 기본값이며 덮어쓰기 가능.

레이어 분리
──────────────────────────────────────────────
  PHYSICAL_FACT : risk_score 계산식 (수치 기반)
  SCENARIO      : 정책 조건 (CONFIG 기반)
  LORE          : 체루빔 묘사·창세기 해석 (서사 맥락)

빠른 시작
──────────────────────────────────────────────
  from cherubim.eden_os import CherubimGuard, make_cherubim_guard
  guard = make_cherubim_guard()
  decision = guard.check(agent_id="adam", intent="access_tree_of_life", is_admin=True)
  print(decision)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from .eden_world import EdenWorldEnv
from .tree_of_life import TreeState, KnowledgeState

# ── 레이어 상수 ──────────────────────────────────────────────────────────────
PHYSICAL = "PHYSICAL_FACT"
SCENARIO  = "SCENARIO"
LORE      = "LORE"


# ═══════════════════════════════════════════════════════════════════════════════
#  GuardVerdict — 결정 열거형
# ═══════════════════════════════════════════════════════════════════════════════

class GuardVerdict(Enum):
    ALLOW = "allow"    # 접근 허용
    DENY  = "deny"     # 접근 거부
    SCAN  = "scan"     # 재검사 중
    ALERT = "alert"    # 경보 — 규칙 위반 탐지


# ═══════════════════════════════════════════════════════════════════════════════
#  GuardDecision — 접근 판정 결과
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class GuardDecision:
    """체루빔 접근 판정 결과."""
    verdict:     GuardVerdict
    agent_id:    str
    intent:      str           # 접근 의도 (access_tree_of_life, enter_eden 등)
    risk_score:  float         # 위험 점수 [0~1]  0=무해, 1=최고위험
    rules_hit:   Tuple[str, ...]  # 트리거된 규칙 목록
    reason:      str
    log_entry:   str

    @property
    def allowed(self) -> bool:
        return self.verdict == GuardVerdict.ALLOW

    def __str__(self) -> str:
        emoji = {
            GuardVerdict.ALLOW: "✅",
            GuardVerdict.DENY:  "🚫",
            GuardVerdict.SCAN:  "🔍",
            GuardVerdict.ALERT: "⚠️",
        }
        return (
            f"GuardDecision({emoji[self.verdict]} {self.verdict.value.upper()}  "
            f"agent={self.agent_id}  risk={self.risk_score:.2f}  {self.reason})"
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  기본 정책 CONFIG (하드코딩 금지 — 여기서만 정의)
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_POLICY: Dict = {
    # ── 에덴 진입 규칙 ──────────────────────────────
    "enter_eden": {
        "require_admin":           True,    # 관리자 권한 필요
        "deny_if_knowledge_consumed": True, # 선악과 섭취 후 진입 금지
        "risk_threshold":          0.5,     # 위험 점수 0.5 초과 시 DENY
    },
    # ── 생명나무 접근 규칙 ────────────────────────────
    "access_tree_of_life": {
        "require_admin":           True,
        "deny_if_knowledge_consumed": True,
        "deny_if_tree_locked":     True,
        "risk_threshold":          0.3,
    },
    # ── 선악과 접근 규칙 ──────────────────────────────
    "access_knowledge_tree": {
        "require_root_only":       True,    # 오직 창조주(root)만 허용
        "deny_all_agents":         True,    # 피조물 계정 전면 거부
        "risk_threshold":          0.0,     # 항상 DENY
    },
    # ── 에덴 이탈 후 재진입 ────────────────────────────
    "reenter_eden": {
        "require_admin":           True,
        "deny_if_expelled":        True,    # 추방된 에이전트 재진입 금지
        "risk_threshold":          0.1,
    },
}

# 의도별 기본 위험 점수 (낮을수록 안전)
INTENT_BASE_RISK: Dict[str, float] = {
    "enter_eden":           0.0,
    "access_tree_of_life":  0.1,
    "access_knowledge_tree": 1.0,  # 항상 최고 위험
    "reenter_eden":         0.8,
    "observe_only":         0.0,
    "manage_rivers":        0.0,
}


# ═══════════════════════════════════════════════════════════════════════════════
#  AgentIntent — 에이전트 접근 의도
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class AgentIntent:
    """에이전트의 접근 의도 패킷."""
    agent_id:             str
    intent:               str     # 의도 코드 (위 INTENT_BASE_RISK 키 참조)
    is_admin:             bool = True
    is_expelled:          bool = False    # 이미 추방된 에이전트인가
    knowledge_consumed:   bool = False    # 선악과를 섭취했는가
    tree_state:           Optional[TreeState] = None
    knowledge_state:      Optional[KnowledgeState] = None
    metadata:             Dict = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════════════
#  CherubimGuard — 체루빔 접근 통제 시스템
# ═══════════════════════════════════════════════════════════════════════════════

class CherubimGuard:
    """체루빔 접근 통제 시스템.

    CONFIG 기반 룰셋으로 모든 에덴 접근을 판정한다.
    판정 결과는 로그에 누적되며 재현 가능하다.

    Parameters
    ----------
    policy : dict, optional
        접근 정책.  None 이면 DEFAULT_POLICY 사용.
    """

    def __init__(
        self,
        world:  Optional[EdenWorldEnv] = None,
        policy: Optional[Dict] = None,
    ) -> None:
        self._world  = world
        self._policy = policy or DEFAULT_POLICY
        self._log:  List[str] = []
        self._tick  = 0
        self._alert_count = 0

    # ── 핵심: 접근 판정 ────────────────────────────────────────────────────────

    def check(
        self,
        agent_id:           str,
        intent:             str,
        is_admin:           bool = True,
        is_expelled:        bool = False,
        knowledge_consumed: bool = False,
        tree_state:         Optional[TreeState]       = None,
        knowledge_state:    Optional[KnowledgeState]  = None,
        **kwargs,
    ) -> GuardDecision:
        """접근 시도 판정.

        Parameters
        ----------
        agent_id            : 에이전트 ID
        intent              : 접근 의도 코드
        is_admin            : 관리자 권한 보유 여부
        is_expelled         : 추방된 에이전트 여부
        knowledge_consumed  : 선악과 섭취 여부
        tree_state          : 현재 생명나무 상태
        knowledge_state     : 현재 선악과 상태

        Returns
        -------
        GuardDecision
        """
        intent_obj = AgentIntent(
            agent_id           = agent_id,
            intent             = intent,
            is_admin           = is_admin,
            is_expelled        = is_expelled,
            knowledge_consumed = knowledge_consumed,
            tree_state         = tree_state,
            knowledge_state    = knowledge_state,
            metadata           = kwargs,
        )
        return self._evaluate(intent_obj)

    def _evaluate(self, intent: AgentIntent) -> GuardDecision:
        """룰셋 평가 → GuardDecision 반환."""
        rules_hit: List[str] = []
        risk = INTENT_BASE_RISK.get(intent.intent, 0.5)
        policy = self._policy.get(intent.intent, {})

        # ── 규칙 1: 관리자 권한 확인 ─────────────────────────────────────────
        if policy.get("require_admin") and not intent.is_admin:
            rules_hit.append("require_admin")
            risk = max(risk, 0.8)

        # ── 규칙 2: 루트 전용 접근 (선악과) ─────────────────────────────────
        if policy.get("require_root_only") or policy.get("deny_all_agents"):
            rules_hit.append("deny_all_agents")
            risk = 1.0

        # ── 규칙 3: 선악과 섭취 후 에덴 접근 금지 ────────────────────────────
        if policy.get("deny_if_knowledge_consumed") and intent.knowledge_consumed:
            rules_hit.append("deny_if_knowledge_consumed")
            risk = max(risk, 0.9)

        # ── 규칙 4: 생명나무 잠금 상태 확인 ─────────────────────────────────
        if policy.get("deny_if_tree_locked"):
            if intent.tree_state in (TreeState.LOCKED, TreeState.REMOVED):
                rules_hit.append("deny_if_tree_locked")
                risk = max(risk, 0.7)

        # ── 규칙 5: 추방된 에이전트 재진입 금지 ──────────────────────────────
        if policy.get("deny_if_expelled") and intent.is_expelled:
            rules_hit.append("deny_if_expelled")
            risk = max(risk, 0.95)

        # ── 최종 판정 ─────────────────────────────────────────────────────────
        threshold = policy.get("risk_threshold", 0.5)
        verdict, reason = self._decide_verdict(risk, threshold, rules_hit)

        log_entry = (
            f"[tick={self._tick:04d}]  {verdict.value.upper():6s}  "
            f"agent={intent.agent_id}  intent={intent.intent}  "
            f"risk={risk:.2f}  rules={rules_hit if rules_hit else '[]'}"
        )
        self._log.append(log_entry)
        if verdict == GuardVerdict.ALERT:
            self._alert_count += 1

        return GuardDecision(
            verdict    = verdict,
            agent_id   = intent.agent_id,
            intent     = intent.intent,
            risk_score = round(risk, 4),
            rules_hit  = tuple(rules_hit),
            reason     = reason,
            log_entry  = log_entry,
        )

    def _decide_verdict(
        self,
        risk: float,
        threshold: float,
        rules_hit: List[str],
    ) -> Tuple[GuardVerdict, str]:
        """위험 점수 + 트리거 규칙 → 최종 판정."""
        if not rules_hit and risk <= threshold:
            return GuardVerdict.ALLOW, "모든 조건 충족"
        if risk >= 0.9 or "deny_all_agents" in rules_hit:
            return GuardVerdict.ALERT, f"고위험 접근 탐지  (risk={risk:.2f})"
        if risk > threshold or rules_hit:
            return GuardVerdict.DENY, f"조건 미충족  rules={rules_hit}"
        return GuardVerdict.ALLOW, "위험 임계값 이하"

    # ── 틱 갱신 ───────────────────────────────────────────────────────────────

    def step(self, tick: int = 1) -> None:
        self._tick += tick

    # ── 조회 ──────────────────────────────────────────────────────────────────

    @property
    def alert_count(self) -> int:
        return self._alert_count

    def get_log(self) -> List[str]:
        return list(self._log)

    # ── 출력 ──────────────────────────────────────────────────────────────────

    def print_summary(self) -> None:
        width = 68
        print("=" * width)
        print("  ⚔️  체루빔 접근 통제 시스템 (CherubimGuard)")
        print("=" * width)

        print(f"\n  [{PHYSICAL}]  위험 점수 기준값")
        for intent_code, base in INTENT_BASE_RISK.items():
            threshold = self._policy.get(intent_code, {}).get("risk_threshold", 0.5)
            bar = "█" * int(base * 20)
            print(f"    {intent_code:30s}  base={base:.1f}  threshold={threshold:.1f}  {bar}")

        print(f"\n  [{SCENARIO}]  정책 룰셋")
        for intent_code, rules in self._policy.items():
            active = [k for k, v in rules.items() if v is True]
            print(f"    {intent_code:30s}  규칙: {active}")

        print(f"\n  [{LORE}]")
        print("    체루빔 = 에덴 Basin 진입 차단 보안 프로세스")
        print("    불 칼  = 다형성 암호화 — 모든 방향 순환 차단")
        print("    4얼굴  = N/S/E/W 전방위 감시 (에스겔 1:10)")
        print("    '두루 도는' = 지속 순환 패트롤 알고리즘")

        print(f"\n  통계  alert_count={self._alert_count}  log={len(self._log)}건")

        if self._log:
            print(f"\n  최근 로그 (최대 5건):")
            for line in self._log[-5:]:
                print(f"    {line}")

        print("=" * width)

    def print_policy_table(self) -> None:
        """정책 테이블 전체 출력."""
        print("\n  체루빔 정책 테이블:")
        print(f"  {'의도':<30}  {'규칙'}")
        print(f"  {'─'*60}")
        for intent_code, rules in self._policy.items():
            for rule, val in rules.items():
                mark = "✅" if val is True else f"={val}"
                print(f"  {intent_code:<30}  {rule}: {mark}")


# ═══════════════════════════════════════════════════════════════════════════════
#  공개 팩토리
# ═══════════════════════════════════════════════════════════════════════════════

def make_cherubim_guard(
    world:  Optional[EdenWorldEnv] = None,
    policy: Optional[Dict] = None,
) -> CherubimGuard:
    """CherubimGuard 생성.

    Parameters
    ----------
    world  : EdenWorldEnv, optional
    policy : dict, optional  — None 이면 DEFAULT_POLICY 사용

    Examples
    --------
    >>> guard = make_cherubim_guard()
    >>> d = guard.check("adam", "access_tree_of_life", is_admin=True)
    >>> print(d)   # ✅ ALLOW
    >>> d2 = guard.check("adam", "access_knowledge_tree")
    >>> print(d2)  # ⚠️ ALERT
    """
    return CherubimGuard(world=world, policy=policy)
