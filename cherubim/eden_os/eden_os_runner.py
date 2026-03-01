"""eden_os.eden_os_runner — EdenOS 7단계 실행기  (Step 7 / 7)

"하나님이 그 일곱째 날을 복되게 하사 거룩하게 하셨으니
 이는 하나님이 그 창조하시며 만드시던 모든 일을 마치시고
 그 날에 안식하셨음이니라"
— 창세기 2:3

역할
────
  EdenOS 전체를 **7단계 고정 순서**로 실행하는 메인 러너.
  Day7Runner 와 동일한 패턴으로 설계되어 전체 엔진과 일관성을 유지한다.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 본편 통합 레이어 (v2.3.0 신규)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  genesis_log      : 아담·이브 탄생 순간 불변 기록 (초기화 시 자동 생성)
  observer_mode    : 매 틱 내부·외부 관찰자 기록 (Step 7에서 자동 기록)
  lineage 전환     : 선악과 이벤트 시 IMMORTAL_ADMIN → MORTAL_NPC (Step 5)
  offspring        : 추방 직후 카인·아벨 자동 스폰 (Step 6)
  genesis_narrative: 에덴→아르헨티나→아마존 GPP 체인 (report에서 출력)

7단계 실행 순서 (매 틱)
──────────────────────────────────────────────
  Step 1  env      — EdenWorldEnv 상태 확인 (환경/궁창/계절)
  Step 2  rivers   — 4대강 유량 갱신
  Step 3  tree     — 생명나무 상태 갱신
  Step 4  guard    — 체루빔 접근 판정 틱 갱신
  Step 5  agents   — Adam/Eve 의사결정 + 행동
                     ★ 선악과 섭취 감지 → lineage.record_expulsion() 자동 실행
  Step 6  lineage  — 계승 조건 검사 + 계승 실행
                     ★ 추방 직후 → spawn_cain_and_abel() 자동 스폰
  Step 7  log      — 틱 로그 저장 + observer_mode 기록

재현성
──────────────────────────────────────────────
  seed 동일 → 로그 동일 (Eve mutation_rate seed 통일)

빠른 시작
──────────────────────────────────────────────
  from cherubim.eden_os import EdenOSRunner, make_eden_os_runner
  runner = make_eden_os_runner()
  runner.run(steps=24)
  runner.print_report()

  # 탄생 순간 로그
  runner.genesis_log.print_moment()

  # 선악과 이벤트 리포트
  runner.print_expulsion_report()

  # 창세기 지리 서사
  runner.print_narrative_report()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .eden_world   import EdenWorldEnv, make_eden_world
from .rivers       import RiverNetwork, make_river_network, RiverState
from .tree_of_life import TreeOfLife, KnowledgeTree, make_trees
from .cherubim_guard import CherubimGuard, GuardDecision, make_cherubim_guard
from .adam         import Adam, ActionResult, make_adam, AdminStatus
from .eve          import Eve, SuccessionEvent, make_eve
from .lineage      import (
    LineageGraph, make_lineage,
    AdamProcessMode, ExpulsionRecord,
    CAIN_CONFIG, ABEL_CONFIG,
)
from .genesis_log      import GenesisLog, record_genesis
from .observer_mode    import (
    InternalObserver, ExternalObserver, RelativeObserver,
    make_observer, OBSERVER_CONFIG,
)
from .genesis_narrative import GenesisNarrative, make_genesis_narrative

# ── 레이어 상수 ──────────────────────────────────────────────────────────────
PHYSICAL = "PHYSICAL_FACT"
SCENARIO  = "SCENARIO"
LORE      = "LORE"


# ═══════════════════════════════════════════════════════════════════════════════
#  TickLog — 한 틱의 전체 실행 기록
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class TickLog:
    """EdenOSRunner 한 틱 실행 기록."""
    tick:               int
    env_eden_index:     float
    river_flow_total:   float
    tree_state:         str
    guard_verdict:      str           # 마지막 guard 결정
    adam_intent:        str
    adam_success:       bool
    succession_fired:   bool
    succession_trigger: str
    active_agent:       str
    process_mode:       str           # 'immortal_admin' | 'mortal_npc'
    expulsion_tick:     Optional[int] # 추방 발생 틱 (None = 미발생)
    observer_judgment:  str           # ExternalObserver 판정 ("좋았더라" 등)
    notes:              List[str] = field(default_factory=list)

    def one_line(self) -> str:
        succ  = f"  ★SUCCESSION({self.succession_trigger})" if self.succession_fired else ""
        ok    = "✅" if self.adam_success else "❌"
        mode  = "🌿" if self.process_mode == AdamProcessMode.IMMORTAL_ADMIN.value else "💀"
        judge = f"  [{self.observer_judgment}]" if self.observer_judgment else ""
        return (
            f"[{self.tick:04d}]  eden={self.env_eden_index:.3f}  "
            f"flow={self.river_flow_total:.3f}  "
            f"tree={self.tree_state:9s}  "
            f"guard={self.guard_verdict:5s}  "
            f"{ok} {self.adam_intent:25s}  "
            f"{mode} agent={self.active_agent}{succ}{judge}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  EdenOSRunner — 7단계 메인 실행기
# ═══════════════════════════════════════════════════════════════════════════════

class EdenOSRunner:
    """EdenOS 7단계 실행기.

    Parameters
    ----------
    world     : EdenWorldEnv        — 환경 스냅샷 (불변)
    rivers    : RiverNetwork        — 4대강 그래프
    life_tree : TreeOfLife          — 생명나무
    know_tree : KnowledgeTree       — 선악과
    guard     : CherubimGuard       — 체루빔 접근 제어
    adam      : Adam                — 초기 관리자
    eve       : Eve                 — 계승 트리거
    lineage   : LineageGraph        — 계승 그래프

    본편 통합 (v2.3.0)
    ------------------
    genesis_log       : 탄생 순간 불변 기록 (초기화 직후 자동 생성)
    internal_observer : 매 틱 아담 내부 기준계 관찰
    external_observer : 매 틱 외부 기준계 "좋았더라" 판정
    relative_observer : 내부·외부 delta 비교
    narrative         : 에덴→아르헨티나→아마존 GPP 체인
    """

    def __init__(
        self,
        world:     EdenWorldEnv,
        rivers:    RiverNetwork,
        life_tree: TreeOfLife,
        know_tree: KnowledgeTree,
        guard:     CherubimGuard,
        adam:      Adam,
        eve:       Eve,
        lineage:   LineageGraph,
    ) -> None:
        self._world     = world
        self._rivers    = rivers
        self._life_tree = life_tree
        self._know_tree = know_tree
        self._guard     = guard
        self._adam      = adam
        self._eve       = eve
        self._lineage   = lineage
        self._tick      = 0
        self._logs:  List[TickLog] = []

        # ── 본편 통합: 관찰자 초기화 ─────────────────────────────────────────
        self._internal_obs: InternalObserver = make_observer(self, mode="internal")
        self._external_obs: ExternalObserver = make_observer(self, mode="external")
        self._relative_obs: RelativeObserver = make_observer(self, mode="relative")

        # ── 본편 통합: 탄생 순간 로그 (불변 기록) ────────────────────────────
        # make_eden_os_runner() 완성 직후 record_genesis()가 호출되어
        # 아담·이브 탄생 환경을 불변 스냅샷으로 저장한다.
        self._genesis_log: Optional[GenesisLog] = None   # _finalize_genesis() 에서 설정

        # ── 본편 통합: 창세기 지리 서사 체인 ─────────────────────────────────
        self._narrative: GenesisNarrative = make_genesis_narrative()

        # ── 추방 상태 추적 ────────────────────────────────────────────────────
        self._expulsion_tick: Optional[int] = None
        self._offspring_spawned: bool = False

        # Lineage 에 1세대 등록
        self._lineage.add_generation(
            agent_id  = adam.id,
            policy    = adam._policy,
            born_tick = 0,
        )

    def _finalize_genesis(self) -> None:
        """탄생 순간 로그 생성 (make_eden_os_runner() 에서 호출)."""
        self._genesis_log = record_genesis(self)

    # ═════════════════════════════════════════════════════════════════════════
    #  속성 (외부 접근용)
    # ═════════════════════════════════════════════════════════════════════════

    @property
    def genesis_log(self) -> Optional[GenesisLog]:
        """탄생 순간 불변 기록."""
        return self._genesis_log

    @property
    def narrative(self) -> GenesisNarrative:
        """창세기 지리 서사 체인."""
        return self._narrative

    @property
    def internal_observer(self) -> InternalObserver:
        return self._internal_obs

    @property
    def external_observer(self) -> ExternalObserver:
        return self._external_obs

    @property
    def relative_observer(self) -> RelativeObserver:
        return self._relative_obs

    # ═════════════════════════════════════════════════════════════════════════
    #  메인 실행
    # ═════════════════════════════════════════════════════════════════════════

    def step(self) -> TickLog:
        """한 틱 실행 (7단계)."""
        self._tick += 1

        notes: List[str] = []

        # ─────────────────────────────────────────────────────────────────────
        # STEP 1  ENV — 환경 상태 확인
        # ─────────────────────────────────────────────────────────────────────
        env_eden = self._world.eden_index

        # ─────────────────────────────────────────────────────────────────────
        # STEP 2  RIVERS — 4대강 유량 갱신
        # ─────────────────────────────────────────────────────────────────────
        river_state: RiverState = self._rivers.step(tick=1)
        self._rivers.step(tick=0)

        # ─────────────────────────────────────────────────────────────────────
        # STEP 3  TREE — 생명나무 상태 갱신
        # ─────────────────────────────────────────────────────────────────────
        self._life_tree.step(tick=1)
        self._know_tree.step(tick=1)
        tree_state_str = self._life_tree.state.value

        # ─────────────────────────────────────────────────────────────────────
        # STEP 4  GUARD — 체루빔 틱 갱신
        # ─────────────────────────────────────────────────────────────────────
        self._guard.step(tick=1)
        last_guard_verdict = "none"

        # ─────────────────────────────────────────────────────────────────────
        # STEP 5  AGENTS — Adam/Eve 의사결정 + 행동
        #         ★ 선악과 섭취 감지 → lineage.record_expulsion() 자동 실행
        # ─────────────────────────────────────────────────────────────────────
        obs = self._adam.observe(
            world            = self._world,
            tree             = self._life_tree,
            river_flow_total = river_state.total_flow,
        )
        intent = self._adam.decide(obs)
        result: ActionResult = self._adam.act(
            intent    = intent,
            guard     = self._guard,
            life_tree = self._life_tree,
            know_tree = self._know_tree,
        )
        self._adam.step(tick=1)
        self._eve.step(tick=1)

        # ── 선악과 섭취 감지 → IMMORTAL_ADMIN → MORTAL_NPC 전환 ─────────────
        if (
            self._adam.knowledge_consumed
            and self._lineage.is_immortal          # 아직 전환 안 된 경우
        ):
            expulsion = self._lineage.record_expulsion(
                tick    = self._tick,
                adam_id = self._adam.id,
                eve_id  = self._eve.id,
            )
            self._expulsion_tick = self._tick
            notes.append(
                f"  🍎 선악과 이벤트: IMMORTAL_ADMIN → MORTAL_NPC  "
                f"(FORKING_ENABLED=True)"
            )
            notes.append(
                f"     체루빔 재진입 방화벽 영구 강화: "
                f"Eden Basin 재진입 차단"
            )

        # guard verdict 추출
        if "guard_verdict" in result.effect:
            last_guard_verdict = result.effect["guard_verdict"]
        elif not result.success and intent.code in ("access_tree_of_life", "enter_eden"):
            last_guard_verdict = "deny"
        else:
            last_guard_verdict = "allow" if result.success else "deny"

        if result.success:
            self._eve.reset_fail()
        else:
            self._eve.record_fail()
            notes.append(f"  ⚠ 실패: {intent.code}")

        # ─────────────────────────────────────────────────────────────────────
        # STEP 6  LINEAGE — 계승 조건 검사 + 실행
        #         ★ 추방 직후 → 카인·아벨 자동 스폰
        # ─────────────────────────────────────────────────────────────────────
        succession_fired   = False
        succession_trigger = ""
        succession_event: Optional[SuccessionEvent] = self._eve.check_succession(
            self._adam, obs
        )
        if succession_event is not None:
            succession_fired   = True
            succession_trigger = succession_event.trigger
            new_adam = self._lineage.succeed(
                event        = succession_event,
                current_tick = self._tick,
            )
            self._adam = new_adam
            self._eve  = make_eve(adam=new_adam, seed=self._tick)
            notes.append(f"  ★ 계승 발동: {succession_trigger}")

        # ── 추방 직후 (다음 틱에서 한 번만) 카인·아벨 스폰 ──────────────────
        if (
            self._lineage.is_expelled
            and not self._offspring_spawned
        ):
            cain, abel = self._lineage.spawn_cain_and_abel(
                spawn_tick = self._tick,
                parent_ids = (self._adam.id, self._eve.id),
            )
            self._offspring_spawned = True
            notes.append(
                f"  🌱 카인 스폰: Agricultural_Agent  "
                f"→ 아마존 분지(-3°,-60°) GPP=1.0"
            )
            notes.append(
                f"  🐑 아벨 스폰: Pastoral_Agent      "
                f"→ 아르헨티나 팜파스(-35°,-65°)"
            )

        self._lineage.step(tick=1)

        # ─────────────────────────────────────────────────────────────────────
        # STEP 7  LOG — 틱 로그 저장 + observer_mode 기록
        # ─────────────────────────────────────────────────────────────────────

        # 외부 관찰자 판정 — runner 로그에서 현재 틱을 읽어 ObservationFrame 생성
        # (observe_all은 self._logs 기준으로 동작하므로 log 추가 전에 임시 로그 삽입 후 읽음)
        # 여기서는 간단히 직접 판정 문자열을 계산한다
        _succ_weight = OBSERVER_CONFIG["succession_weight"]
        _good_th     = OBSERVER_CONFIG["good_eden_threshold"]
        _deg_th      = OBSERVER_CONFIG["degraded_threshold"]
        if succession_fired:
            judge = "보류"
        elif env_eden >= _good_th:
            judge = "좋았더라"
        elif env_eden >= _deg_th:
            judge = "보류"
        else:
            judge = "기준미달"

        # 내부 관찰자: runner 틱이 끝난 뒤 snapshot() 은 _tick 기준으로 읽으므로
        # Step 7 이후(log 추가 뒤)에 observe_all / compare_all 을 한 번에 실행.
        # 여기서는 틱별 즉시 기록 없이 run() 완료 후 일괄 처리 방식을 유지한다.

        log = TickLog(
            tick               = self._tick,
            env_eden_index     = round(env_eden, 4),
            river_flow_total   = round(river_state.total_flow, 4),
            tree_state         = tree_state_str,
            guard_verdict      = last_guard_verdict,
            adam_intent        = intent.code,
            adam_success       = result.success,
            succession_fired   = succession_fired,
            succession_trigger = succession_trigger,
            active_agent       = self._adam.id,
            process_mode       = self._lineage.process_mode.value,
            expulsion_tick     = self._expulsion_tick,
            observer_judgment  = judge,
            notes              = notes,
        )
        self._logs.append(log)
        return log

    def run(self, steps: int = 24) -> List[TickLog]:
        """N 틱 연속 실행.

        Returns
        -------
        list[TickLog]  —  실행된 모든 틱 로그
        """
        for _ in range(steps):
            self.step()
        return list(self._logs)

    # ── 조회 ──────────────────────────────────────────────────────────────────

    @property
    def tick(self) -> int:
        return self._tick

    @property
    def current_agent(self) -> Adam:
        return self._adam

    @property
    def logs(self) -> List[TickLog]:
        return list(self._logs)

    def get_succession_count(self) -> int:
        return sum(1 for l in self._logs if l.succession_fired)

    # ── 출력 ──────────────────────────────────────────────────────────────────

    def print_expulsion_report(self) -> None:
        """선악과 이벤트 + 자손 기록 출력."""
        self._lineage.print_expulsion_event()
        if self._lineage.all_offspring():
            self._lineage.print_offspring()

    def print_narrative_report(self) -> None:
        """창세기 지리 서사 체인 출력 (에덴→아르헨티나→아마존)."""
        self._narrative.print_full_chain()

    def print_genesis_report(self) -> None:
        """탄생 순간 로그 출력."""
        if self._genesis_log:
            self._genesis_log.print_moment()
        else:
            print("  [RUNNER] 탄생 순간 로그 미생성 (make_eden_os_runner() 사용 권장)")

    def print_observer_report(self) -> None:
        """관찰자 모드 리포트 출력."""
        # run() 완료 후 일괄 처리
        self._external_obs.observe_all()
        self._external_obs.print_report()
        self._relative_obs.compare_all()
        self._relative_obs.print_relative_report()

    def print_report(self, last_n: int = 0) -> None:
        """실행 결과 전체 통합 리포트.

        Parameters
        ----------
        last_n : int  — 0 이면 전체, n > 0 이면 마지막 n 틱만
        """
        width = 78
        logs_to_show = self._logs if last_n == 0 else self._logs[-last_n:]

        print("=" * width)
        print("  🌍 EdenOS Runner — 통합 실행 리포트")
        print("=" * width)

        # ── 환경 요약 ─────────────────────────────────────────────────────────
        pf = self._world.layer[PHYSICAL]
        print(f"\n  [{PHYSICAL}]  환경 스냅샷")
        print(f"    지표 온도   : {pf['T_surface_C']:.1f}°C  |  극지 온도: {pf['pole_T_C']:.1f}°C")
        print(f"    UV 차폐     : {pf['UV_shield']*100:.0f}%  |  강수 모드: {pf['precip_mode']}")
        print(f"    얼음 밴드   : {pf['ice_bands']}  |  거주밴드: {pf['hab_bands']}/12")
        print(f"    에덴 지수   : {self._world.eden_index:.4f}")
        print(f"    합격 여부   : {'✅ PASS' if self._world.valid else '❌ FAIL'}")

        # ── 실행 통계 ─────────────────────────────────────────────────────────
        total       = len(self._logs)
        success_cnt = sum(1 for l in self._logs if l.adam_success)
        succ_cnt    = self.get_succession_count()
        mode_str    = (
            "🌿 IMMORTAL_ADMIN (에덴 내 불멸 관리자)"
            if self._lineage.is_immortal
            else "💀 MORTAL_NPC (추방 후 유한 프로세스)"
        )
        print(f"\n  [{SCENARIO}]  실행 통계")
        print(f"    총 틱           : {total}")
        print(f"    성공률          : {success_cnt}/{total} = {success_cnt/max(total,1)*100:.1f}%")
        print(f"    계승 횟수       : {succ_cnt}")
        print(f"    현재 관리자     : {self._adam.id}")
        print(f"    계보 깊이       : {self._lineage.depth()} 세대")
        print(f"    프로세스 모드   : {mode_str}")
        print(f"    번식 API        : {'🔓 ENABLED (선악과 이후)' if self._lineage.forking_enabled else '🔒 DISABLED (에덴 내부)'}")
        if self._expulsion_tick is not None:
            print(f"    추방 발생 틱    : {self._expulsion_tick:04d}")
        if self._lineage.all_offspring():
            offspring_names = [r.offspring_id for r in self._lineage.all_offspring()]
            print(f"    자손 에이전트   : {offspring_names}")

        # ── 외부 관찰자 요약 (일괄 처리) ────────────────────────────────────────
        self._external_obs.observe_all()
        if self._external_obs.frames:
            score = self._external_obs.overall_score()
            good  = sum(1 for f in self._external_obs.frames if f.god_verdict == "좋았더라")
            print(f"\n  [외부 관찰자]  '하나님이 보시기에'")
            print(f"    좋았더라 틱  : {good}/{total}")
            print(f"    종합 점수    : {score:.4f}")

        # ── 틱별 로그 ─────────────────────────────────────────────────────────
        print(f"\n  {'─'*74}")
        print(f"  틱 로그 (총 {total}건" + (f", 마지막 {last_n}건 표시" if last_n > 0 else "") + ")")
        print(f"  {'─'*74}")
        print(f"  [tick]  eden   flow   tree       guard  결과 의도                      모드 agent")
        print(f"  {'─'*74}")
        for log in logs_to_show:
            print(f"  {log.one_line()}")
            for note in log.notes:
                print(f"         {note}")

        # ── 계승 트리 ─────────────────────────────────────────────────────────
        if succ_cnt > 0 or self._lineage.all_offspring():
            print()
            self._lineage.print_tree()

        # ── 추방 이벤트 ───────────────────────────────────────────────────────
        if self._expulsion_tick is not None:
            print()
            self._lineage.print_expulsion_event()
            if self._lineage.all_offspring():
                self._lineage.print_offspring()

        # ── 창세기 지리 서사 ──────────────────────────────────────────────────
        print()
        self._narrative.print_expulsion_analysis()

        # ── LORE ──────────────────────────────────────────────────────────────
        print(f"\n  [{LORE}]")
        print(f"    [에덴 내부] 아담·이브 = Immortal Admin (FORKING_ENABLED=False)")
        print(f"    [선악과]   knowledge_consumed=True → MORTAL_NPC 전환 (비가역)")
        print(f"    [추방 후]  카인(아마존)·아벨(팜파스) 스폰 → 계승 체인 가동")
        print(f"    [계보]     아담 → 셋 → ... → 노아 → ... → 네오 (선택받은 자)")
        print(f"    체루빔 = 생명나무 가드  |  4강 = 전 지구 리소스 공급")
        print("=" * width)


# ═══════════════════════════════════════════════════════════════════════════════
#  공개 팩토리
# ═══════════════════════════════════════════════════════════════════════════════

def make_eden_os_runner(
    world_ic=None,
    seed: int = 42,
) -> EdenOSRunner:
    """EdenOSRunner 생성 — 모든 서브시스템을 조립한다.

    Parameters
    ----------
    world_ic : InitialConditions, optional
        None 이면 make_antediluvian() 사용.
    seed : int
        재현성 시드 (Eve mutation 에 사용).

    Returns
    -------
    EdenOSRunner — 즉시 run() 가능한 상태.
                   genesis_log 자동 생성 완료.

    Examples
    --------
    >>> runner = make_eden_os_runner()
    >>> runner.run(steps=24)
    >>> runner.print_report()

    >>> # 탄생 순간 로그
    >>> runner.genesis_log.print_moment()

    >>> # 선악과 이벤트 리포트 (추방 후에만 유효)
    >>> runner.print_expulsion_report()

    >>> # 창세기 지리 서사
    >>> runner.print_narrative_report()
    """
    world     = make_eden_world(ic=world_ic)
    rivers    = make_river_network(world=world)
    life_tree, know_tree = make_trees(world=world)
    guard     = make_cherubim_guard(world=world)
    adam      = make_adam(agent_id="adam")
    eve       = make_eve(adam=adam, seed=seed)
    lineage   = make_lineage()

    runner = EdenOSRunner(
        world     = world,
        rivers    = rivers,
        life_tree = life_tree,
        know_tree = know_tree,
        guard     = guard,
        adam      = adam,
        eve       = eve,
        lineage   = lineage,
    )

    # 탄생 순간 로그 생성 (runner 조립 완료 직후 한 번만)
    runner._finalize_genesis()

    return runner
