"""eden_os.eden_os_runner — EdenOS 7단계 실행기  (Step 7 / 7)

"하나님이 그 일곱째 날을 복되게 하사 거룩하게 하셨으니
 이는 하나님이 그 창조하시며 만드시던 모든 일을 마치시고
 그 날에 안식하셨음이니라"
— 창세기 2:3

역할
────
  EdenOS 전체를 **7단계 고정 순서**로 실행하는 메인 러너.
  Day7Runner 와 동일한 패턴으로 설계되어 전체 엔진과 일관성을 유지한다.

7단계 실행 순서 (매 틱)
──────────────────────────────────────────────
  Step 1  env      — EdenWorldEnv 상태 확인 (환경/궁창/계절)
  Step 2  rivers   — 4대강 유량 갱신
  Step 3  tree     — 생명나무 상태 갱신
  Step 4  guard    — 체루빔 접근 판정 (이전 틱 의도 검사)
  Step 5  agents   — Adam/Eve 의사결정 + 행동
  Step 6  lineage  — 계승 조건 검사 + 계승 실행
  Step 7  log      — 틱 로그 저장 + 재현성 기록

재현성
──────────────────────────────────────────────
  seed 동일 → 로그 동일 (Eve mutation_rate seed 통일)

빠른 시작
──────────────────────────────────────────────
  from cherubim.eden_os import EdenOSRunner, make_eden_os_runner
  runner = make_eden_os_runner()
  runner.run(steps=24)
  runner.print_report()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .eden_world  import EdenWorldEnv, make_eden_world
from .rivers      import RiverNetwork, make_river_network, RiverState
from .tree_of_life import TreeOfLife, KnowledgeTree, make_trees
from .cherubim_guard import CherubimGuard, GuardDecision, make_cherubim_guard
from .adam        import Adam, ActionResult, make_adam
from .eve         import Eve, SuccessionEvent, make_eve
from .lineage     import LineageGraph, make_lineage

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
    notes:              List[str] = field(default_factory=list)

    def one_line(self) -> str:
        succ = f"  ★SUCCESSION({self.succession_trigger})" if self.succession_fired else ""
        ok   = "✅" if self.adam_success else "❌"
        return (
            f"[{self.tick:04d}]  eden={self.env_eden_index:.3f}  "
            f"flow={self.river_flow_total:.3f}  "
            f"tree={self.tree_state:9s}  "
            f"guard={self.guard_verdict:5s}  "
            f"{ok} {self.adam_intent:25s}  "
            f"agent={self.active_agent}{succ}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  EdenOSRunner — 7단계 메인 실행기
# ═══════════════════════════════════════════════════════════════════════════════

class EdenOSRunner:
    """EdenOS 7단계 실행기.

    Parameters
    ----------
    world   : EdenWorldEnv        — 환경 스냅샷 (불변)
    rivers  : RiverNetwork        — 4대강 그래프
    life_tree : TreeOfLife        — 생명나무
    know_tree : KnowledgeTree     — 선악과
    guard   : CherubimGuard       — 체루빔 접근 제어
    adam    : Adam                — 초기 관리자
    eve     : Eve                 — 계승 트리거
    lineage : LineageGraph        — 계승 그래프
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
        self._adam      = adam      # 현재 활성 관리자 (계승 시 교체)
        self._eve       = eve
        self._lineage   = lineage
        self._tick      = 0
        self._logs:  List[TickLog] = []

        # Lineage 에 1세대 등록
        self._lineage.add_generation(
            agent_id  = adam.id,
            policy    = adam._policy,
            born_tick = 0,
        )

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
        #   EdenWorldEnv 는 불변(frozen) 이므로 참조만 한다.
        #   미래 확장: FI 감쇄 모델 연결 시 여기서 갱신.
        env_eden = self._world.eden_index

        # ─────────────────────────────────────────────────────────────────────
        # STEP 2  RIVERS — 4대강 유량 갱신
        # ─────────────────────────────────────────────────────────────────────
        river_state: RiverState = self._rivers.step(tick=1)
        self._rivers.step(tick=0)  # rivers 내부 tick 과 runner tick 동기화

        # ─────────────────────────────────────────────────────────────────────
        # STEP 3  TREE — 생명나무 상태 갱신
        # ─────────────────────────────────────────────────────────────────────
        self._life_tree.step(tick=1)
        self._know_tree.step(tick=1)
        tree_state_str = self._life_tree.state.value

        # ─────────────────────────────────────────────────────────────────────
        # STEP 4  GUARD — 체루빔 접근 판정
        # ─────────────────────────────────────────────────────────────────────
        #   이 단계에서는 에이전트의 '관찰 후 의도'를 미리 검사하지 않고,
        #   Step 5 act() 내부에서 guard.check()가 호출된다.
        #   여기서는 guard 틱만 갱신한다.
        self._guard.step(tick=1)
        last_guard_verdict = "none"

        # ─────────────────────────────────────────────────────────────────────
        # STEP 5  AGENTS — Adam/Eve 의사결정 + 행동
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
        # ─────────────────────────────────────────────────────────────────────
        succession_fired   = False
        succession_trigger = ""
        succession_event: Optional[SuccessionEvent] = self._eve.check_succession(
            self._adam, obs
        )
        if succession_event is not None:
            succession_fired   = True
            succession_trigger = succession_event.trigger
            # 새 세대 Adam 생성 → 현재 관리자 교체
            new_adam = self._lineage.succeed(
                event        = succession_event,
                current_tick = self._tick,
            )
            self._adam = new_adam
            # Eve 도 새 아담에 연결
            self._eve  = make_eve(adam=new_adam, seed=self._tick)
            notes.append(f"  ★ 계승 발동: {succession_trigger}")
        self._lineage.step(tick=1)

        # ─────────────────────────────────────────────────────────────────────
        # STEP 7  LOG — 틱 로그 저장
        # ─────────────────────────────────────────────────────────────────────
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

    def print_report(self, last_n: int = 0) -> None:
        """실행 결과 리포트 출력.

        Parameters
        ----------
        last_n : int  — 0 이면 전체, n > 0 이면 마지막 n 틱만
        """
        width = 78
        logs_to_show = self._logs if last_n == 0 else self._logs[-last_n:]

        print("=" * width)
        print("  🌍 EdenOS Runner — 실행 리포트")
        print("=" * width)

        # 환경 요약
        pf = self._world.layer[PHYSICAL]
        print(f"\n  [{PHYSICAL}]  환경 스냅샷")
        print(f"    지표 온도   : {pf['T_surface_C']:.1f}°C  |  극지 온도: {pf['pole_T_C']:.1f}°C")
        print(f"    UV 차폐     : {pf['UV_shield']*100:.0f}%  |  강수 모드: {pf['precip_mode']}")
        print(f"    얼음 밴드   : {pf['ice_bands']}  |  거주밴드: {pf['hab_bands']}/12")
        print(f"    에덴 지수   : {self._world.eden_index:.4f}")
        print(f"    합격 여부   : {'✅ PASS' if self._world.valid else '❌ FAIL'}")

        # 실행 통계
        total = len(self._logs)
        success_cnt = sum(1 for l in self._logs if l.adam_success)
        succ_cnt    = self.get_succession_count()
        print(f"\n  [{SCENARIO}]  실행 통계")
        print(f"    총 틱       : {total}")
        print(f"    성공률      : {success_cnt}/{total} = {success_cnt/max(total,1)*100:.1f}%")
        print(f"    계승 횟수   : {succ_cnt}")
        print(f"    현재 관리자 : {self._adam.id}")
        print(f"    계보 깊이   : {self._lineage.depth()} 세대")

        # 틱별 로그
        print(f"\n  {'─'*74}")
        print(f"  틱 로그 (총 {total}건" + (f", 마지막 {last_n}건 표시" if last_n > 0 else "") + ")")
        print(f"  {'─'*74}")
        print(f"  [tick]  eden   flow   tree       guard  결과 의도                      agent")
        print(f"  {'─'*74}")
        for log in logs_to_show:
            print(f"  {log.one_line()}")
            for note in log.notes:
                print(f"         {note}")

        # 계승 트리
        if succ_cnt > 0:
            print()
            self._lineage.print_tree()

        print(f"\n  [{LORE}]")
        print(f"    아담 → 관리자 계보 → 네오 (매 계승 = 정책 진화)")
        print(f"    체루빔 = 생명나무 가드  |  4강 = 전 지구 리소스 공급")
        print(f"    생명나무 접속 유지 → 엔트로피 억제 → 에덴 유지")
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

    Examples
    --------
    >>> runner = make_eden_os_runner()
    >>> runner.run(steps=24)
    >>> runner.print_report()
    """
    world     = make_eden_world(ic=world_ic)
    rivers    = make_river_network(world=world)
    life_tree, know_tree = make_trees(world=world)
    guard     = make_cherubim_guard(world=world)
    adam      = make_adam(agent_id="adam")
    eve       = make_eve(adam=adam, seed=seed)
    lineage   = make_lineage()

    return EdenOSRunner(
        world     = world,
        rivers    = rivers,
        life_tree = life_tree,
        know_tree = know_tree,
        guard     = guard,
        adam      = adam,
        eve       = eve,
        lineage   = lineage,
    )
