"""cherubim.eden_os — EdenOS v2.0  "행성 운영 체제 시뮬레이터"

"에덴은 좌표가 아니라 상태(state)다.
 아담은 그 상태를 관리하는 시스템 관리자였다."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 임포트 흐름 (직관적 레이어 순서)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  cherubim.eden_os
  │
  ├─ eden_world       LAYER 0 — 환경 (궁창시대 스냅샷 · 읽기전용)
  ├─ rivers           LAYER 1 — 인프라 (4대강 네트워크)
  ├─ tree_of_life     LAYER 2 — 커널 (생명나무 · 선악과)
  ├─ cherubim_guard   LAYER 3 — 보안 (체루빔 접근 제어)
  ├─ adam / eve       LAYER 4 — 에이전트 (관리자 루프)
  ├─ lineage          LAYER 5 — 계승 (세대 그래프 · 네오)
  └─ eden_os_runner   LAYER 6 — 실행기 (7단계 통합 러너)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 빠른 시작 (원라이너)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  # 전체 EdenOS 24틱 실행
  from cherubim.eden_os import make_eden_os_runner
  runner = make_eden_os_runner()
  runner.run(steps=24)
  runner.print_report()

  # 레이어별 직접 사용
  from cherubim.eden_os import make_eden_world
  from cherubim.eden_os import make_river_network
  from cherubim.eden_os import make_trees
  from cherubim.eden_os import make_cherubim_guard
  from cherubim.eden_os import make_adam, make_eve
  from cherubim.eden_os import make_lineage

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 레이어 비유 (매트릭스 OS 관점)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  eden_world    = 하드웨어 (남극=위, 빙하 없는 아열대)
  rivers        = 백본 네트워크 (전 지구 리소스 공급)
  tree_of_life  = 부트 로더 (영속성 · 엔트로피 억제)
  cherubim_guard= 방화벽 (에덴 Basin 접근 통제)
  adam/eve      = 시스템 관리자 (관찰→결정→행동)
  lineage       = 버전 관리 (아담v1 → 네오vN)
  eden_os_runner= OS 커널 (7단계 고정 순서 실행)
"""

# ── LAYER 0  eden_world ──────────────────────────────────────────────────────
from .eden_world import (
    EdenWorldEnv,
    BandInfo,
    make_eden_world,
)

# ── LAYER 1  rivers ──────────────────────────────────────────────────────────
from .rivers import (
    RiverNode,
    RiverEdge,
    RiverState,
    RiverNetwork,
    RIVER_CONFIG,
    make_river_network,
)

# ── LAYER 2  tree_of_life ────────────────────────────────────────────────────
from .tree_of_life import (
    TreeState,
    KnowledgeState,
    AccessResult,
    KnowledgeAccessResult,
    TreeOfLife,
    KnowledgeTree,
    DEFAULT_TREE_EFFECT,
    KNOWLEDGE_PENALTY,
    make_trees,
)

# ── LAYER 3  cherubim_guard ──────────────────────────────────────────────────
from .cherubim_guard import (
    GuardVerdict,
    GuardDecision,
    AgentIntent,
    CherubimGuard,
    DEFAULT_POLICY,
    INTENT_BASE_RISK,
    make_cherubim_guard,
)

# ── LAYER 4  adam / eve ──────────────────────────────────────────────────────
from .adam import (
    AdminStatus,
    Observation,
    Intent,
    ActionResult,
    Adam,
    make_adam,
)
from .eve import (
    SuccessionEvent,
    Eve,
    make_eve,
)

# ── LAYER 5  lineage ─────────────────────────────────────────────────────────
from .lineage import (
    LineageNode,
    LineageEdge,
    LineageGraph,
    GENERATION_NAMES_LORE,
    make_lineage,
)

# ── LAYER 6  eden_os_runner ──────────────────────────────────────────────────
from .eden_os_runner import (
    TickLog,
    EdenOSRunner,
    make_eden_os_runner,
)

# ── LAYER 4.5a  genesis_log — 탄생 순간 불변 로그 ────────────────────────────
from .genesis_log import (
    GenesisEvent,
    GenesisLog,
    record_genesis,
    make_genesis_log,
    GENESIS_EDEN_INDEX_MIN,
    GENESIS_STATUS_OK,
    GENESIS_STATUS_DEGRADED,
    GENESIS_STATUS_INVALID,
)

# ── LAYER 4.5b  observer_mode — 독립 관찰자 (상대성) ─────────────────────────
from .observer_mode import (
    ObservationFrame,
    InternalObserver,
    ExternalObserver,
    RelativeEvent,
    RelativeObserver,
    make_observer,
    OBSERVER_CONFIG,
)

# ── LAYER 4.5c  genesis_narrative — 창세기 지리 서사 체인 ─────────────────────
from .genesis_narrative import (
    LocationNode,
    GenesisChain,
    GenesisNarrative,
    make_genesis_narrative,
    NARRATIVE_LOCATIONS,
    CAIN_ABEL_CONFIG,
)

__all__ = [
    # LAYER 0 — 환경
    "EdenWorldEnv", "BandInfo", "make_eden_world",
    # LAYER 1 — 4대강
    "RiverNode", "RiverEdge", "RiverState", "RiverNetwork",
    "RIVER_CONFIG", "make_river_network",
    # LAYER 2 — 생명나무
    "TreeState", "KnowledgeState",
    "AccessResult", "KnowledgeAccessResult",
    "TreeOfLife", "KnowledgeTree",
    "DEFAULT_TREE_EFFECT", "KNOWLEDGE_PENALTY", "make_trees",
    # LAYER 3 — 체루빔
    "GuardVerdict", "GuardDecision", "AgentIntent",
    "CherubimGuard", "DEFAULT_POLICY", "INTENT_BASE_RISK",
    "make_cherubim_guard",
    # LAYER 4 — 에이전트
    "AdminStatus", "Observation", "Intent", "ActionResult",
    "Adam", "make_adam",
    "SuccessionEvent", "Eve", "make_eve",
    # LAYER 5 — 계승
    "LineageNode", "LineageEdge", "LineageGraph",
    "GENERATION_NAMES_LORE", "make_lineage",
    # LAYER 6 — 실행기
    "TickLog", "EdenOSRunner", "make_eden_os_runner",
    # LAYER 4.5a — 탄생 순간 로그
    "GenesisEvent", "GenesisLog", "record_genesis", "make_genesis_log",
    "GENESIS_EDEN_INDEX_MIN", "GENESIS_STATUS_OK",
    "GENESIS_STATUS_DEGRADED", "GENESIS_STATUS_INVALID",
    # LAYER 4.5b — 독립 관찰자 (상대성)
    "ObservationFrame", "InternalObserver",
    "ExternalObserver", "RelativeEvent", "RelativeObserver",
    "make_observer", "OBSERVER_CONFIG",
    # LAYER 4.5c — 창세기 지리 서사
    "LocationNode", "GenesisChain", "GenesisNarrative",
    "make_genesis_narrative", "NARRATIVE_LOCATIONS", "CAIN_ABEL_CONFIG",
]
