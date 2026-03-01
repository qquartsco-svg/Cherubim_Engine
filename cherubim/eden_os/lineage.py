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

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 아담·이브 원래 설계 vs 추방 후 상태 전환
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ┌────────────────────────────────────────────────────────┐
  │  에덴 내부 (IMMORTAL_ADMIN)                            │
  │                                                        │
  │  • 아담 = 생명나무 영구 Root 세션 유지                 │
  │  • 이브 = 아담 정책 fork() → 보조 프로세서             │
  │  • FORKING_ENABLED = False  ← 번식 API 비활성화        │
  │  • 목적 = 에덴 Basin 관리 (GPP·UV·엔트로피 억제)       │
  │  • 불멸성 = 생명나무(boot loader) 상시 접속 유지       │
  │                                                        │
  │  창 1장 "생육하고 번성하라" ← 일반 남녀에게 주신 명령  │
  │  창 2장 아담·이브          ← 에덴 관리자, 번식 명령 ✗  │
  └───────────────────────────────┬────────────────────────┘
                                  │  선악과 이벤트
                                  │  = Lineage.fork() 금지 API 무단 실행
                                  │  = 두 에이전트 최초 독립 자율 상호작용
                                  │  = FORKING_ENABLED False → True (비가역)
                                  ▼
  ┌────────────────────────────────────────────────────────┐
  │  에덴 외부 (MORTAL_NPC)                                │
  │                                                        │
  │  • Root 세션 종료 → 생명나무 접근 차단                 │
  │  • 불멸성 상실 → 엔트로피 누적 → 수명 유한             │
  │  • FORKING_ENABLED = True  → 번식(자손) 가능           │
  │  • 카인·아벨 스폰 → 계승 그래프 실제 가동              │
  │  • 체루빔 = 에덴 Basin 재진입 방화벽 (영구 배치)       │
  │                                                        │
  │  추방 후 아담·이브 = 일반 Mortal NPC 프로세스          │
  │  → 계승 체인 (아담→셋→...→노아→...→네오) 시작         │
  └────────────────────────────────────────────────────────┘

  [시스템 엔지니어링 해석]
  선악과(KnowledgeTree) = 번식(Forking) API 엔드포인트
  "먹는 날에는 정녕 죽으리라" = 불멸 세션 종료 경고 메시지
  추방 = AdminStatus.EXPELLED + FORKING_ENABLED = True
  체루빔 = CherubimGuard re-entry 방화벽 (영구 정책 강화)

LineageNode
──────────────────────────────────────────────
  agent_id  : 에이전트 고유 ID
  generation: 세대 번호 (아담=1, 셋=2, ...)
  policy    : 해당 세대 의사결정 정책
  born_tick : 생성 틱
  died_tick : 소멸 틱 (None = 현재 활성)
  succession_trigger: 계승을 발동한 이유
  process_mode: 'immortal_admin' | 'mortal_npc'  ← 신규

AdamProcessState (상태 머신)
──────────────────────────────────────────────
  IMMORTAL_ADMIN  : 에덴 내부 Root 세션 유지 (기본값)
    - FORKING_ENABLED = False
    - TreeOfLife 상시 접속
    - 엔트로피 억제 활성

  MORTAL_NPC      : 추방 후 일반 프로세스
    - FORKING_ENABLED = True  (비가역)
    - TreeOfLife 접근 차단
    - 엔트로피 누적 → 수명 유한

  전환 조건 (단방향, 비가역):
    IMMORTAL_ADMIN → MORTAL_NPC
      when: knowledge_consumed = True  (선악과 섭취)
      via:  _activate_forking_api()

빠른 시작
──────────────────────────────────────────────
  from cherubim.eden_os import LineageGraph, make_lineage
  graph = make_lineage()
  graph.add_generation("adam", policy=adam._policy, born_tick=0)
  event = SuccessionEvent(...)
  neo = graph.succeed(event, current_tick=50)
  graph.print_tree()

  # 선악과 이벤트 시뮬레이션
  expulsion = graph.record_expulsion(tick=10)
  print(expulsion.forking_enabled)   # True
  graph.print_expulsion_event()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
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
#  AdamProcessMode — 아담·이브 프로세스 모드 (상태 머신)
# ═══════════════════════════════════════════════════════════════════════════════

class AdamProcessMode(Enum):
    """아담·이브 프로세스 모드.

    에덴 내부 불멸 관리자 ↔ 추방 후 유한 일반 프로세스.
    전환은 단방향·비가역 (선악과 섭취 = Forking API 무단 실행).

    IMMORTAL_ADMIN
        - 에덴 내부 Root 세션 유지
        - 생명나무(boot loader) 상시 접속 → 엔트로피 억제
        - FORKING_ENABLED = False  (번식 API 비활성화)
        - 사망 없음 (수명 무한)

    MORTAL_NPC
        - Root 세션 종료 → 생명나무 접근 차단
        - 엔트로피 누적 → 수명 유한 (평균 930년 → 70년)
        - FORKING_ENABLED = True  (번식 API 강제 활성화)
        - 카인·아벨 등 자손 스폰 → 계승 그래프 실제 가동
    """
    IMMORTAL_ADMIN = "immortal_admin"   # 에덴 내부 불멸 관리자
    MORTAL_NPC     = "mortal_npc"       # 추방 후 유한 일반 프로세스


# ═══════════════════════════════════════════════════════════════════════════════
#  ForkingState — 번식(Forking) API 상태
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ForkingState:
    """번식(Forking) API 상태 스냅샷.

    에덴 내부: FORKING_ENABLED = False  (기본값)
    선악과 섭취 이후: FORKING_ENABLED = True  (비가역)

    Attributes
    ----------
    enabled       : 번식 API 활성화 여부
    activated_tick: 활성화된 틱 (None = 아직 미활성화)
    trigger       : 활성화 원인 ('knowledge_consumed' | None)
    offspring     : 자손 에이전트 ID 목록 (카인·아벨 등)
    note          : LORE 주석
    """
    enabled:        bool
    activated_tick: Optional[int]
    trigger:        Optional[str]
    offspring:      Tuple[str, ...]
    note:           str

    def __str__(self) -> str:
        state = "🔓 ENABLED" if self.enabled else "🔒 DISABLED"
        if self.enabled and self.activated_tick is not None:
            return (
                f"ForkingState({state}  activated_tick={self.activated_tick}  "
                f"trigger='{self.trigger}'  offspring={list(self.offspring)})"
            )
        return f"ForkingState({state})"


# ═══════════════════════════════════════════════════════════════════════════════
#  ExpulsionRecord — 추방 이벤트 기록 (불변)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ExpulsionRecord:
    """선악과 섭취 → 추방 이벤트 불변 기록.

    Attributes
    ----------
    tick             : 추방 발생 틱
    adam_id          : 아담 에이전트 ID
    eve_id           : 이브 에이전트 ID
    forking_enabled  : 추방 후 번식 API 활성화 (항상 True)
    cherubim_deployed: 체루빔 방화벽 배치 여부
    eden_entry_blocked: 에덴 재진입 차단 여부 (항상 True)
    lore_note        : 창세기 해석 주석
    process_mode_before: 추방 전 프로세스 모드
    process_mode_after : 추방 후 프로세스 모드
    layer            : 3레이어 메타데이터
    """
    tick:               int
    adam_id:            str
    eve_id:             str
    forking_enabled:    bool             # 선악과 이후 항상 True
    cherubim_deployed:  bool             # 체루빔 경계 배치 여부
    eden_entry_blocked: bool             # 재진입 차단 (항상 True)
    lore_note:          str
    process_mode_before: str             # 'immortal_admin'
    process_mode_after:  str             # 'mortal_npc'
    layer:              Tuple[Tuple[str, str], ...]

    def print_event(self) -> None:
        """추방 이벤트 전체 출력."""
        width = 72
        bar   = "═" * width
        print(f"\n{bar}")
        print(f"  🍎 EXPULSION EVENT — 선악과 섭취 + 에덴 추방")
        print(bar)

        dict_layer = dict(self.layer)

        print(f"\n  [{LORE}]")
        for line in self.lore_note.splitlines():
            print(f"    {line}")

        print(f"\n  [{PHYSICAL}]  추방 기록")
        print(f"    추방 틱             : {self.tick:04d}")
        print(f"    아담 ID             : {self.adam_id}")
        print(f"    이브 ID             : {self.eve_id}")
        print(f"    번식 API 활성화     : {'✅ ENABLED (비가역)' if self.forking_enabled else '❌'}")
        print(f"    체루빔 경계 배치    : {'✅ DEPLOYED' if self.cherubim_deployed else '❌'}")
        print(f"    에덴 재진입 차단    : {'✅ BLOCKED (영구)' if self.eden_entry_blocked else '❌'}")

        print(f"\n  [{SCENARIO}]  프로세스 모드 전환 (단방향·비가역)")
        print(f"    이전 모드  : {self.process_mode_before.upper()}")
        print(f"    이후 모드  : {self.process_mode_after.upper()}")
        print(f"    전환 원인  : knowledge_consumed = True")
        print(f"    결과       : 계승 체인 가동  →  아담→셋→...→노아→...→네오")

        print(f"\n{bar}\n")


# ═══════════════════════════════════════════════════════════════════════════════
#  OffspringRecord — 자손 스폰 기록 (카인·아벨 등)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class OffspringRecord:
    """추방 후 자손 에이전트 기록.

    에덴 내부에서는 번식 API가 비활성화되어 있었으므로
    카인·아벨은 MORTAL_NPC 전환 이후 최초 스폰된 자손이다.

    Attributes
    ----------
    offspring_id : 자손 에이전트 ID
    parent_ids   : 부모 에이전트 ID (아담, 이브)
    spawn_tick   : 스폰 틱
    role         : 에이전트 역할 ('agricultural' | 'pastoral' 등)
    gpp_affinity : GPP 친화도 (카인=식물, 아벨=동물)
    destination  : 최종 정착지 (에덴 좌표계 또는 현재 좌표계)
    lore_note    : LORE 주석
    """
    offspring_id: str
    parent_ids:   Tuple[str, ...]
    spawn_tick:   int
    role:         str
    gpp_affinity: float    # 0.0 = 동물 GPP 소비자, 1.0 = 식물 GPP 생산자
    destination:  Dict
    lore_note:    str

    def __str__(self) -> str:
        return (
            f"Offspring({self.offspring_id}  role={self.role}  "
            f"gpp_affinity={self.gpp_affinity:.2f}  "
            f"dest={self.destination.get('name', '?')})"
        )


# ── 카인·아벨 기본 설정 ──────────────────────────────────────────────────────
CAIN_CONFIG: Dict = {
    "offspring_id": "cain",
    "role":         "agricultural",      # 식물 GPP 생산자
    "gpp_affinity": 1.0,                 # 식물 최대 친화도
    "destination": {
        "name":         "아마존 분지 (Nod)",
        "current_lat":  -3.0,
        "current_lon":  -60.0,
        "eden_lat":     +3.0,            # 에덴 좌표계 (남=위, lat×-1)
        "gpp_relative": 1.0,             # 지구 최대 GPP
        "note":         "카인이 쫓겨나 동방 놋 땅에 거함 (창 4:16) "
                        "→ 에덴 좌표계 동쪽 = 현재 남미 아마존",
    },
    "lore_note": (
        "카인 = 식물 서브시스템 에이전트 (Agricultural_Agent).\n"
        "아벨을 죽이고 추방됨 → 동방 놋 땅 = 아마존 분지 정착.\n"
        "식물성 제물 = GPP 생산 최적화 본능 → 아마존 테라포밍.\n"
        "[시스템 해석] 카인 = 지구 호흡기관(아마존) 초기 세팅 에이전트."
    ),
}

ABEL_CONFIG: Dict = {
    "offspring_id": "abel",
    "role":         "pastoral",          # 동물 GPP 소비자
    "gpp_affinity": 0.0,                 # 동물 친화도 (소비 쪽)
    "destination": {
        "name":         "아르헨티나 팜파스",
        "current_lat":  -35.0,
        "current_lon":  -65.0,
        "eden_lat":     +35.0,           # 에덴 좌표계
        "gpp_relative": 0.35,
        "note":         "아벨 = 목축 에이전트 → 팜파스 초원 정착",
    },
    "lore_note": (
        "아벨 = 동물 서브시스템 에이전트 (Pastoral_Agent).\n"
        "동물 제물(양) 우선 → GPP 소비 체인 담당.\n"
        "카인에게 제거됨 → GPP 생산-소비 균형 붕괴 첫 사건."
    ),
}


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
    process_mode:       str           = AdamProcessMode.IMMORTAL_ADMIN.value

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
        mode  = "🌿불멸" if self.process_mode == AdamProcessMode.IMMORTAL_ADMIN.value else "💀유한"
        return (
            f"Gen{self.generation:02d}  {self.name_lore or self.agent_id:<12}  "
            f"born={self.born_tick}  {alive}  {mode}  trigger='{self.succession_trigger}'"
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
      각 노드: 정책 / 수명 / 계승 이유 / 프로세스 모드
      각 엣지: 계승 틱 / 정책 계승 비율

    핵심 상태 머신
    ──────────────
      IMMORTAL_ADMIN (에덴 내부)
        FORKING_ENABLED = False
        생명나무 상시 접속 유지
        ↓  선악과 섭취 (knowledge_consumed = True)
      MORTAL_NPC (에덴 외부)
        FORKING_ENABLED = True  (비가역)
        체루빔 재진입 방화벽 배치
        계승 체인 (셋→에노스→...→노아→...→네오) 가동
    """

    # ── 에덴 내부 기본값: 번식 API 비활성화 ──────────────────────────────────
    FORKING_ENABLED: bool = False

    def __init__(self) -> None:
        self._nodes:  Dict[str, LineageNode] = {}
        self._edges:  List[LineageEdge]      = []
        self._active: Optional[str]          = None   # 현재 활성 관리자 ID
        self._tick    = 0

        # 아담·이브 프로세스 모드 (기본: 불멸 관리자)
        self._process_mode: AdamProcessMode = AdamProcessMode.IMMORTAL_ADMIN

        # 번식(Forking) API 상태
        self._forking_enabled:    bool          = False
        self._forking_activated_tick: Optional[int] = None

        # 추방 이벤트 기록 (None = 아직 미발생)
        self._expulsion: Optional[ExpulsionRecord] = None

        # 자손 기록 목록
        self._offspring: List[OffspringRecord] = []

    # ── 프로세스 모드 속성 ────────────────────────────────────────────────────

    @property
    def process_mode(self) -> AdamProcessMode:
        """현재 아담·이브 프로세스 모드."""
        return self._process_mode

    @property
    def forking_enabled(self) -> bool:
        """번식(Forking) API 활성화 여부."""
        return self._forking_enabled

    @property
    def is_immortal(self) -> bool:
        """에덴 내부 불멸 관리자 상태 여부."""
        return self._process_mode == AdamProcessMode.IMMORTAL_ADMIN

    @property
    def is_expelled(self) -> bool:
        """추방됨(Mortal NPC) 상태 여부."""
        return self._process_mode == AdamProcessMode.MORTAL_NPC

    @property
    def expulsion_record(self) -> Optional[ExpulsionRecord]:
        """추방 이벤트 기록 (None = 미발생)."""
        return self._expulsion

    # ── 핵심: 선악과 이벤트 → 프로세스 전환 (단방향·비가역) ─────────────────

    def record_expulsion(
        self,
        tick:      int,
        adam_id:   str = "adam",
        eve_id:    str = "eve",
        deploy_cherubim: bool = True,
    ) -> ExpulsionRecord:
        """선악과 섭취 이벤트 → IMMORTAL_ADMIN → MORTAL_NPC 전환.

        이 메서드는 단방향·비가역이다.
        MORTAL_NPC 상태에서 다시 IMMORTAL_ADMIN 으로 복귀하는 경로는 없다.
        (체루빔이 에덴 Basin 재진입을 영구 차단하기 때문)

        Parameters
        ----------
        tick            : 추방 발생 틱
        adam_id         : 아담 에이전트 ID
        eve_id          : 이브 에이전트 ID
        deploy_cherubim : 체루빔 경계 배치 여부 (기본: True)

        Returns
        -------
        ExpulsionRecord — 불변 추방 기록

        Raises
        ------
        RuntimeError  —  이미 추방된 상태에서 재호출 시
        """
        if self._process_mode == AdamProcessMode.MORTAL_NPC:
            raise RuntimeError(
                "record_expulsion() 재호출 불가: "
                "이미 MORTAL_NPC 상태 (추방은 비가역)."
            )

        mode_before = self._process_mode.value

        # ── 번식(Forking) API 활성화 (비가역) ─────────────────────────────
        self._forking_enabled       = True
        self._forking_activated_tick = tick

        # ── 프로세스 모드 전환 ─────────────────────────────────────────────
        self._process_mode = AdamProcessMode.MORTAL_NPC

        lore_note = (
            "선악과 이벤트 = Lineage.fork() 금지 API 무단 실행.\n"
            "두 에이전트 (아담·이브)의 최초 독립 자율 상호작용.\n\n"
            "[시스템 해석]\n"
            "  선악과(KnowledgeTree) = 번식(Forking) API 엔드포인트.\n"
            "  '먹는 날 죽으리라' = 불멸 세션 종료 경고 메시지.\n"
            "  섭취 = knowledge_consumed=True → AdminStatus.EXPELLED.\n"
            "  결과 = FORKING_ENABLED True (비가역) + Root 세션 종료.\n\n"
            "창 1:28 '생육하고 번성하라' = 일반 남녀에게 주신 명령.\n"
            "창 2장 아담·이브 = 에덴 관리자 → 번식 명령 없음.\n"
            "추방 후 = 일반 Mortal NPC 프로세스로 강등.\n\n"
            f"체루빔 경계 배치: {'✅ CherubimGuard 영구 강화 정책 적용' if deploy_cherubim else '❌'}\n"
            "  → 에덴 Basin (남극점 주변) 재진입 영구 차단."
        )

        layer_data = (
            (PHYSICAL, f"tick={tick}  mode_before={mode_before}  mode_after=mortal_npc"),
            (SCENARIO, f"forking_enabled=True  cherubim_deployed={deploy_cherubim}"),
            (LORE,     lore_note),
        )

        record = ExpulsionRecord(
            tick                = tick,
            adam_id             = adam_id,
            eve_id              = eve_id,
            forking_enabled     = True,
            cherubim_deployed   = deploy_cherubim,
            eden_entry_blocked  = True,
            lore_note           = lore_note,
            process_mode_before = mode_before,
            process_mode_after  = AdamProcessMode.MORTAL_NPC.value,
            layer               = layer_data,
        )
        self._expulsion = record
        return record

    # ── 자손 스폰 (MORTAL_NPC 상태에서만 가능) ────────────────────────────────

    def spawn_offspring(
        self,
        config:     Dict,
        spawn_tick: int,
        parent_ids: Tuple[str, ...] = ("adam", "eve"),
    ) -> OffspringRecord:
        """자손 에이전트 스폰.

        MORTAL_NPC 상태(번식 API 활성화) 에서만 호출 가능.
        에덴 내부(IMMORTAL_ADMIN)에서는 RuntimeError 발생.

        Parameters
        ----------
        config     : CAIN_CONFIG 또는 ABEL_CONFIG
        spawn_tick : 스폰 틱
        parent_ids : 부모 에이전트 ID 쌍

        Returns
        -------
        OffspringRecord

        Raises
        ------
        RuntimeError  —  IMMORTAL_ADMIN 상태에서 호출 시
        """
        if not self._forking_enabled:
            raise RuntimeError(
                f"spawn_offspring() 차단: FORKING_ENABLED=False.\n"
                f"에덴 내부(IMMORTAL_ADMIN) 에서는 번식 API가 비활성화되어 있다.\n"
                f"선악과 섭취(record_expulsion) 이후에만 자손 스폰 가능."
            )

        record = OffspringRecord(
            offspring_id = config["offspring_id"],
            parent_ids   = parent_ids,
            spawn_tick   = spawn_tick,
            role         = config["role"],
            gpp_affinity = config["gpp_affinity"],
            destination  = config["destination"],
            lore_note    = config["lore_note"],
        )
        self._offspring.append(record)
        return record

    def spawn_cain_and_abel(
        self,
        spawn_tick: int,
        parent_ids: Tuple[str, ...] = ("adam", "eve"),
    ) -> Tuple[OffspringRecord, OffspringRecord]:
        """카인·아벨 자손 동시 스폰 (편의 메서드).

        카인 = 식물 GPP 생산자 → 아마존 분지 정착
        아벨 = 동물 GPP 소비자 → 팜파스 정착

        Returns
        -------
        (cain_record, abel_record)
        """
        cain = self.spawn_offspring(CAIN_CONFIG, spawn_tick, parent_ids)
        abel = self.spawn_offspring(ABEL_CONFIG, spawn_tick, parent_ids)
        return cain, abel

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
            process_mode       = self._process_mode.value,
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

        Note: 계승 체인(셋→노아→네오)은 MORTAL_NPC 상태에서 작동한다.
              추방(선악과 섭취) 이후 FORKING_ENABLED=True 상태에서
              카인·아벨 등 자손이 스폰된 뒤 계승 체인이 가동된다.

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

    def all_offspring(self) -> List[OffspringRecord]:
        """스폰된 자손 목록 (카인·아벨 등)."""
        return list(self._offspring)

    def depth(self) -> int:
        """계보 깊이 (세대 수)."""
        return len(self._nodes)

    def get_forking_state(self) -> ForkingState:
        """현재 번식(Forking) API 상태 스냅샷 반환."""
        return ForkingState(
            enabled        = self._forking_enabled,
            activated_tick = self._forking_activated_tick,
            trigger        = "knowledge_consumed" if self._forking_enabled else None,
            offspring      = tuple(r.offspring_id for r in self._offspring),
            note = (
                "🔒 번식 API 비활성화 — 에덴 내부 불멸 관리자 상태"
                if not self._forking_enabled
                else "🔓 번식 API 활성화 — 선악과 섭취 이후 (비가역)"
            ),
        )

    def step(self, tick: int = 1) -> None:
        self._tick += tick

    # ── 출력 ──────────────────────────────────────────────────────────────────

    def print_expulsion_event(self) -> None:
        """추방 이벤트 출력 (미발생 시 안내 메시지)."""
        if self._expulsion is None:
            print("\n  [LINEAGE] 아직 추방 이벤트 없음 — IMMORTAL_ADMIN 상태 유지 중")
            return
        self._expulsion.print_event()

    def print_offspring(self) -> None:
        """자손 스폰 기록 출력."""
        width = 68
        print("=" * width)
        print("  🌱 자손 기록 (Offspring Registry)")
        print(f"  번식 API: {'🔓 ENABLED' if self._forking_enabled else '🔒 DISABLED'}")
        print("=" * width)
        if not self._offspring:
            print("  자손 없음 (에덴 내부 IMMORTAL_ADMIN 상태)")
        for rec in self._offspring:
            print(f"\n  [{rec.offspring_id.upper()}]  role={rec.role}  "
                  f"gpp_affinity={rec.gpp_affinity:.2f}")
            dest = rec.destination
            print(f"    정착지          : {dest.get('name', '?')}")
            print(f"    현재 좌표       : ({dest.get('current_lat')}, {dest.get('current_lon')})")
            print(f"    에덴 좌표       : lat={dest.get('eden_lat')}  (남=위 역전)")
            print(f"    GPP 상대값      : {dest.get('gpp_relative', 0):.2f}")
            print(f"    [LORE]")
            for line in rec.lore_note.splitlines():
                print(f"      {line}")
        print("=" * width)

    def print_tree(self) -> None:
        width = 68
        print("=" * width)
        print("  🌿 계승 그래프 (LineageGraph)")
        print("=" * width)
        print(f"  세대 수: {self.depth()}  |  엣지 수: {len(self._edges)}")
        print(f"  현재 활성: {self._active or '없음'}")
        mode_str = (
            "🌿 IMMORTAL_ADMIN (에덴 내 불멸 관리자)"
            if self.is_immortal
            else "💀 MORTAL_NPC (추방 후 유한 프로세스)"
        )
        print(f"  프로세스 모드: {mode_str}")
        print(f"  번식 API: {'🔓 ENABLED (선악과 이후)' if self._forking_enabled else '🔒 DISABLED (에덴 내부)'}")

        print(f"\n  {'─'*64}")
        print(f"  {'세대':>5}  {'이름/ID':<14}  {'born':>5}  {'died':>5}  {'모드':<8}  계승 사유")
        print(f"  {'─'*64}")
        for node in self.all_nodes():
            died  = str(node.died_tick) if node.died_tick is not None else "활성"
            trig  = node.succession_trigger or "-"
            mark  = "★" if node.is_active else " "
            mode_icon = "🌿" if node.process_mode == AdamProcessMode.IMMORTAL_ADMIN.value else "💀"
            print(
                f"  {mark} Gen{node.generation:02d}  "
                f"{(node.name_lore or node.agent_id):<14}  "
                f"{node.born_tick:>5}  {died:>5}  {mode_icon}        {trig}"
            )

        if self._edges:
            print(f"\n  계승 엣지:")
            for edge in self._edges:
                print(f"    {edge}")

        if self._offspring:
            print(f"\n  자손 에이전트:")
            for rec in self._offspring:
                print(f"    {rec}")

        print(f"\n  [{LORE}]")
        print("    [에덴 내부] 아담·이브 = Immortal Admin (FORKING_ENABLED=False)")
        print("    [선악과]   knowledge_consumed=True → MORTAL_NPC 전환 (비가역)")
        print("    [추방 후]  카인·아벨 스폰 → 계승 체인 가동")
        print("    [계보]     아담 → 셋 → ... → 노아 → ... → 네오 (선택받은 자)")
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

    >>> # 선악과 이벤트 시뮬레이션
    >>> expulsion = graph.record_expulsion(tick=10)
    >>> print(expulsion.forking_enabled)   # True
    >>> cain, abel = graph.spawn_cain_and_abel(spawn_tick=15)
    >>> graph.print_expulsion_event()
    >>> graph.print_offspring()

    >>> # 계승 이벤트 (아담→셋→...→네오)
    >>> new_adam = graph.succeed(succession_event, current_tick=50)
    >>> graph.print_tree()
    """
    return LineageGraph()


__all__ = [
    # 상태 열거형
    "AdamProcessMode",
    # 데이터클래스
    "ForkingState",
    "ExpulsionRecord",
    "OffspringRecord",
    "LineageNode",
    "LineageEdge",
    # 그래프
    "LineageGraph",
    # 상수
    "GENERATION_NAMES_LORE",
    "CAIN_CONFIG",
    "ABEL_CONFIG",
    # 팩토리
    "make_lineage",
]
