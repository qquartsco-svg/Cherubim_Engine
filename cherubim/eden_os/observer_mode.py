"""eden_os.observer_mode — 독립 관찰자 모드  (LAYER 4.5 / 상대성)

"하나님이 보시기에 좋았더라 (And God saw that it was good)"
— 창세기 1장 반복 구절

역할
────
  에덴 OS를 '외부에서' 관찰하는 독립 관찰자(Observer) 모드.

  아담은 에덴 '내부'의 관리자 — 환경을 경작하고 지킨다.
  관찰자는 에덴 '외부'에서 시스템 전체를 조망한다.

  이것이 상대성(Relativity):
    아담의 시간 = 에덴 틱 단위 (내부 기준계)
    관찰자의 시간 = 절대 시뮬레이션 시간 (외부 기준계)
    → 두 기준계의 시간 흐름과 인식이 다를 수 있다.

관찰자 3종
──────────────────────────────────────────────────────────
  1. InternalObserver  — 아담 자신의 관찰 (내부 기준계)
     · 에덴 내부에서 보는 시간/환경
     · 편향: 자신의 행동이 환경에 영향을 준다고 믿음

  2. ExternalObserver  — 시스템 외부에서 보는 관찰 (외부 기준계)
     · 전체 틱 로그를 비동기로 읽는 "신의 시점"
     · 편향 없음 — 아담의 행동과 무관하게 환경을 본다
     · "하나님이 보시기에 좋았더라" = ExternalObserver 평가

  3. RelativeObserver  — 두 기준계를 동시에 기록하는 비교자
     · 아담의 주관적 기록 vs. 외부 객관적 기록 비교
     · 차이(delta)가 발생하면 상대성 이벤트(RelativeEvent) 로그

물리 해석 (SCENARIO 레이어)
──────────────────────────────────────────────────────────
  에덴에서는 아담과 외부 관찰자의 시간 흐름이 동일하다.
  (궁창시대 = 극지-적도 온도차 15K = 시간 균등 분포)

  대홍수 이후 현재 지구:
    - 극지-적도 온도차 48K → 기후 불균형
    - 상대적 시간 인식 차이 발생 가능
    - 관찰자 위치에 따라 에덴 지수 평가가 다름

레이어 분리
──────────────────────────────────────────────
  PHYSICAL_FACT : 틱 로그·관찰값 (객관)
  SCENARIO      : 내부/외부 비교 판정
  LORE          : "하나님이 보시기에 좋았더라" 연결

빠른 시작
──────────────────────────────────────────────
  from cherubim.eden_os import make_eden_os_runner
  from cherubim.eden_os.observer_mode import ExternalObserver, RelativeObserver

  runner   = make_eden_os_runner()
  ext_obs  = ExternalObserver(runner)

  runner.run(steps=10)
  ext_obs.observe_all()
  ext_obs.print_report()

  rel_obs = RelativeObserver(runner)
  runner.run(steps=10)
  rel_obs.compare()
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

# ── 레이어 상수 ──────────────────────────────────────────────────────────────
PHYSICAL = "PHYSICAL_FACT"
SCENARIO  = "SCENARIO"
LORE      = "LORE"

# ── 판정 임계값 CONFIG ────────────────────────────────────────────────────────
OBSERVER_CONFIG: Dict = {
    "good_eden_threshold":    0.80,   # "좋았더라" 판정 기준
    "degraded_threshold":     0.50,   # 에덴 기준 미달
    "relative_delta_alert":   0.10,   # 내부/외부 인식 차이 경보
    "succession_weight":      0.15,   # 계승 횟수 페널티 가중치
    "river_flow_ideal":       0.75,   # 이상적 강 유량
}


# ═══════════════════════════════════════════════════════════════════════════════
#  ObservationFrame — 단일 틱 관찰 프레임
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ObservationFrame:
    """외부 관찰자가 한 틱을 찍은 스냅샷."""
    tick:           int
    eden_index:     float
    river_flow:     float
    tree_state:     str
    adam_intent:    str
    adam_success:   bool
    succession:     bool
    active_agent:   str
    god_verdict:    str     # "좋았더라" | "보류" | "기준미달"
    notes:          tuple   # 관찰 메모

    def one_line(self) -> str:
        mark  = "✅" if self.adam_success else "❌"
        vmark = {"좋았더라": "🌟", "보류": "🔵", "기준미달": "🔴"}.get(self.god_verdict, "?")
        succ  = " ★" if self.succession else "  "
        return (
            f"  [{self.tick:04d}] {vmark} eden={self.eden_index:.3f}  "
            f"flow={self.river_flow:.3f}  tree={self.tree_state:9s}  "
            f"{mark} {self.adam_intent:22s}  "
            f"agent={self.active_agent}{succ}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  InternalObserver — 아담의 내부 기준계 관찰
# ═══════════════════════════════════════════════════════════════════════════════

class InternalObserver:
    """아담 자신의 관찰 기록 — 내부 기준계.

    아담이 매 틱 observe()를 호출한 결과를 수집한다.
    아담의 주관적 인식 = 행동의 성공/실패가 환경에 영향을 준다고 믿음.
    """

    def __init__(self, runner: Any) -> None:
        self._runner = runner
        self._frames: List[Dict] = []

    def snapshot(self) -> Dict:
        """현재 틱의 아담 주관적 상태 스냅샷."""
        adam  = self._runner._adam
        world = self._runner._world
        obs   = adam.observe(
            world            = world,
            tree             = self._runner._life_tree,
            river_flow_total = self._runner._rivers.step(0).total_flow,
        )
        frame = {
            "tick":           self._runner.tick,
            "eden_index":     obs.eden_index,
            "anomaly":        obs.anomaly,
            "tree_state":     obs.tree_state,
            "river_flow":     obs.river_flow_total,
            "hab_bands":      obs.hab_bands,
            "ice_bands":      obs.ice_bands,
            "mutation":       obs.mutation_factor,
            "notes":          obs.notes,
            "agent_status":   adam.status.value,
        }
        self._frames.append(frame)
        return frame

    @property
    def frames(self) -> List[Dict]:
        return list(self._frames)

    def perceived_eden_trend(self) -> str:
        """아담이 체감하는 에덴 지수 추세."""
        if len(self._frames) < 2:
            return "데이터 부족"
        deltas = [
            self._frames[i]["eden_index"] - self._frames[i-1]["eden_index"]
            for i in range(1, len(self._frames))
        ]
        avg_delta = sum(deltas) / len(deltas)
        if avg_delta > 0.001:
            return "상승 📈"
        elif avg_delta < -0.001:
            return "하락 📉"
        return "안정 ─"


# ═══════════════════════════════════════════════════════════════════════════════
#  ExternalObserver — 신의 시점 (외부 기준계)
# ═══════════════════════════════════════════════════════════════════════════════

class ExternalObserver:
    """외부 관찰자 — "하나님이 보시기에 좋았더라" 기준계.

    EdenOSRunner의 tick 로그를 비동기적으로 읽어
    객관적 평가 프레임(ObservationFrame)을 생성한다.

    아담의 행동과 무관하게 환경 자체를 평가한다.
    → 아담이 행동을 잘못해도 에덴이 유지되면 "좋았더라"
    → 아담이 최선을 다해도 환경이 나빠지면 "기준미달"

    Parameters
    ----------
    runner : EdenOSRunner
    config : dict, optional  — OBSERVER_CONFIG 오버라이드
    """

    def __init__(
        self,
        runner: Any,
        config: Optional[Dict] = None,
    ) -> None:
        self._runner = runner
        self._cfg    = config or dict(OBSERVER_CONFIG)
        self._frames: List[ObservationFrame] = []
        self._last_observed_tick = 0

    def observe_all(self) -> List[ObservationFrame]:
        """러너의 모든 틱 로그를 읽어 ObservationFrame 리스트 생성.

        이미 읽은 틱은 건너뛴다 (비동기 safe).
        """
        logs = self._runner.logs
        new_frames = []
        for log in logs:
            if log.tick <= self._last_observed_tick:
                continue

            # "하나님이 보시기에 좋았더라" 판정
            verdict = self._judge(log.env_eden_index, log.succession_fired)

            notes_list = []
            if log.succession_fired:
                notes_list.append(f"계승 발동 → {log.active_agent}")
            if log.env_eden_index < self._cfg["degraded_threshold"]:
                notes_list.append("에덴 기준 미달 ⚠")
            if not log.adam_success:
                notes_list.append(f"행동 실패: {log.adam_intent}")

            frame = ObservationFrame(
                tick          = log.tick,
                eden_index    = log.env_eden_index,
                river_flow    = log.river_flow_total,
                tree_state    = log.tree_state,
                adam_intent   = log.adam_intent,
                adam_success  = log.adam_success,
                succession    = log.succession_fired,
                active_agent  = log.active_agent,
                god_verdict   = verdict,
                notes         = tuple(notes_list),
            )
            self._frames.append(frame)
            new_frames.append(frame)
            self._last_observed_tick = log.tick

        return new_frames

    def _judge(self, eden_index: float, succession: bool) -> str:
        """외부 관찰자 판정 — "좋았더라" / "보류" / "기준미달"."""
        # 계승이 발동되면 내부 불안정 → 보류
        if succession:
            return "보류"
        threshold_good     = self._cfg["good_eden_threshold"]
        threshold_degraded = self._cfg["degraded_threshold"]
        if eden_index >= threshold_good:
            return "좋았더라"
        elif eden_index >= threshold_degraded:
            return "보류"
        return "기준미달"

    @property
    def frames(self) -> List[ObservationFrame]:
        return list(self._frames)

    def overall_score(self) -> float:
        """관찰 전체의 외부 평가 점수 [0~1].

        "좋았더라" 비율 × 에덴 지수 평균 × 계승 페널티
        """
        if not self._frames:
            return 0.0
        good_ratio  = sum(1 for f in self._frames if f.god_verdict == "좋았더라") / len(self._frames)
        eden_avg    = sum(f.eden_index for f in self._frames) / len(self._frames)
        succ_count  = sum(1 for f in self._frames if f.succession)
        succ_penalty = min(1.0, succ_count * self._cfg["succession_weight"])
        return round(max(0.0, good_ratio * 0.4 + eden_avg * 0.6 - succ_penalty), 4)

    def print_report(self, last_n: int = 0) -> None:
        """외부 관찰자 리포트 출력."""
        frames = self._frames if last_n == 0 else self._frames[-last_n:]

        width = 72
        print("=" * width)
        print("  👁  ExternalObserver — 외부 기준계 관찰 리포트")
        print(f"  [{LORE}]  '하나님이 보시기에 좋았더라' (창 1장)")
        print("=" * width)

        # 집계
        total      = len(self._frames)
        good_cnt   = sum(1 for f in self._frames if f.god_verdict == "좋았더라")
        hold_cnt   = sum(1 for f in self._frames if f.god_verdict == "보류")
        bad_cnt    = sum(1 for f in self._frames if f.god_verdict == "기준미달")
        succ_cnt   = sum(1 for f in self._frames if f.succession)
        score      = self.overall_score()

        print(f"\n  [{SCENARIO}]  외부 평가 통계")
        print(f"    총 관찰 틱   : {total}")
        print(f"    🌟 좋았더라  : {good_cnt}/{total} ({good_cnt/max(total,1)*100:.0f}%)")
        print(f"    🔵 보류      : {hold_cnt}/{total}")
        print(f"    🔴 기준미달  : {bad_cnt}/{total}")
        print(f"    ★ 계승 횟수  : {succ_cnt}")
        print(f"    종합 점수    : {score:.4f}")

        print(f"\n  [{PHYSICAL}]  틱별 관찰")
        print(f"  {'─'*68}")
        for f in frames:
            print(f.one_line())
            for note in f.notes:
                print(f"          └─ {note}")

        print(f"\n  [{LORE}]")
        print(f"    외부 관찰자 = 아담의 행동과 무관한 '신의 시점'")
        print(f"    에덴 지수 ≥ {self._cfg['good_eden_threshold']:.2f} = 좋았더라")
        print(f"    에덴 지수 < {self._cfg['degraded_threshold']:.2f} = 기준미달")
        print("=" * width)


# ═══════════════════════════════════════════════════════════════════════════════
#  RelativeObserver — 내부 vs 외부 기준계 비교
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class RelativeEvent:
    """내부·외부 기준계의 인식 차이 이벤트."""
    tick:           int
    internal_eden:  float   # 아담이 인식한 에덴 지수
    external_eden:  float   # 외부 관찰자가 측정한 에덴 지수
    delta:          float   # 차이 (internal - external)
    alert:          bool    # delta > threshold
    note:           str

    def one_line(self) -> str:
        alert_mark = " ⚡ RELATIVE_ALERT" if self.alert else ""
        return (
            f"  [{self.tick:04d}]  Δeden={self.delta:+.4f}  "
            f"internal={self.internal_eden:.4f}  external={self.external_eden:.4f}"
            f"{alert_mark}"
        )


class RelativeObserver:
    """내부 기준계(아담)와 외부 기준계(신의 시점)를 동시에 기록하는 비교자.

    두 기준계의 에덴 지수 인식 차이(delta)를 추적한다.

    궁창시대에는 delta ≈ 0 (아담의 인식 = 외부 현실).
    홍수 이후 현재 지구에서는 delta가 커질 수 있다.
    → 이것이 에덴의 상대성(Relativity of Eden).

    Parameters
    ----------
    runner : EdenOSRunner
    config : dict, optional
    """

    def __init__(
        self,
        runner: Any,
        config: Optional[Dict] = None,
    ) -> None:
        self._runner   = runner
        self._cfg      = config or dict(OBSERVER_CONFIG)
        self._internal = InternalObserver(runner)
        self._external = ExternalObserver(runner, config)
        self._events:  List[RelativeEvent] = []

    def compare(self) -> List[RelativeEvent]:
        """현재 틱까지 내부·외부 기준계 비교 → RelativeEvent 리스트."""
        # 외부 프레임 갱신
        self._external.observe_all()
        # 내부 스냅샷 생성
        int_snap = self._internal.snapshot()

        ext_frames = {f.tick: f for f in self._external.frames}
        current_tick = self._runner.tick

        if current_tick not in ext_frames:
            return []

        ext_frame   = ext_frames[current_tick]
        int_eden    = int_snap["eden_index"]
        ext_eden    = ext_frame.eden_index
        delta       = int_eden - ext_eden
        threshold   = self._cfg["relative_delta_alert"]
        alert       = abs(delta) > threshold

        note = ""
        if alert:
            direction = "과대" if delta > 0 else "과소"
            note = f"아담이 에덴을 {direction}평가 (delta={delta:+.4f})"
        else:
            note = "내부·외부 인식 일치 (에덴 상태 투명)"

        event = RelativeEvent(
            tick           = current_tick,
            internal_eden  = int_eden,
            external_eden  = ext_eden,
            delta          = round(delta, 6),
            alert          = alert,
            note           = note,
        )
        self._events.append(event)
        return [event]

    def compare_all(self) -> List[RelativeEvent]:
        """러너의 전체 로그에 대해 비교 실행."""
        # 외부 먼저 읽기
        self._external.observe_all()
        ext_frames = {f.tick: f for f in self._external.frames}

        events = []
        for log in self._runner.logs:
            if log.tick in ext_frames:
                ext_eden = ext_frames[log.tick].eden_index
                # 내부 인식 = runner log에 기록된 값 (= 아담 observe 결과)
                int_eden = log.env_eden_index
                delta    = int_eden - ext_eden
                threshold = self._cfg["relative_delta_alert"]
                alert    = abs(delta) > threshold
                note     = (
                    f"아담 {'과대' if delta > 0 else '과소'}평가 (delta={delta:+.4f})"
                    if alert else "내부·외부 일치"
                )
                event = RelativeEvent(
                    tick          = log.tick,
                    internal_eden = int_eden,
                    external_eden = ext_eden,
                    delta         = round(delta, 6),
                    alert         = alert,
                    note          = note,
                )
                events.append(event)

        self._events = events
        return events

    def print_relative_report(self) -> None:
        """상대성 리포트 출력."""
        if not self._events:
            self.compare_all()

        events = self._events
        width  = 72

        print("=" * width)
        print("  🔭 RelativeObserver — 내부·외부 기준계 비교 (상대성 리포트)")
        print(f"  [{LORE}]  에덴 = 내부/외부 인식이 일치하는 상태")
        print("=" * width)

        alert_cnt  = sum(1 for e in events if e.alert)
        total      = len(events)
        deltas     = [abs(e.delta) for e in events]
        max_delta  = max(deltas) if deltas else 0.0
        avg_delta  = sum(deltas) / len(deltas) if deltas else 0.0

        print(f"\n  [{SCENARIO}]  상대성 통계")
        print(f"    비교 틱 수     : {total}")
        print(f"    인식 불일치    : {alert_cnt}/{total} 틱  (threshold={self._cfg['relative_delta_alert']:.2f})")
        print(f"    최대 delta     : {max_delta:.6f}")
        print(f"    평균 delta     : {avg_delta:.6f}")
        if avg_delta < 0.001:
            print(f"    판정           : ✅ 에덴 상태 — 내부·외부 인식 일치")
        else:
            print(f"    판정           : ⚠ 상대성 감지 — 기준계 분리 중")

        print(f"\n  [{PHYSICAL}]  틱별 비교")
        print(f"  {'─'*68}")
        for e in events:
            print(e.one_line())
            if e.alert:
                print(f"          └─ ⚡ {e.note}")

        print(f"\n  [{LORE}]")
        print(f"    궁창시대 에덴: delta ≈ 0  → 아담의 인식 = 외부 현실")
        print(f"    대홍수 이후 : delta 증가 → 인간의 인식이 현실에서 멀어짐")
        print(f"    (극지-적도 온도차 15K→48K = 기준계 분리의 물리적 원인)")
        print("=" * width)


# ═══════════════════════════════════════════════════════════════════════════════
#  공개 팩토리
# ═══════════════════════════════════════════════════════════════════════════════

def make_observer(
    runner: Any,
    mode: str = "external",
    config: Optional[Dict] = None,
) -> Any:
    """관찰자 생성 helper.

    Parameters
    ----------
    runner : EdenOSRunner
    mode   : 'internal' | 'external' | 'relative'
    config : dict, optional  — OBSERVER_CONFIG 오버라이드

    Returns
    -------
    InternalObserver | ExternalObserver | RelativeObserver

    Examples
    --------
    >>> from cherubim.eden_os import make_eden_os_runner
    >>> from cherubim.eden_os.observer_mode import make_observer
    >>> runner = make_eden_os_runner()
    >>> runner.run(steps=12)
    >>> obs = make_observer(runner, mode='external')
    >>> obs.observe_all()
    >>> obs.print_report()
    """
    if mode == "internal":
        return InternalObserver(runner)
    elif mode == "relative":
        return RelativeObserver(runner, config)
    return ExternalObserver(runner, config)


__all__ = [
    "ObservationFrame",
    "InternalObserver",
    "ExternalObserver",
    "RelativeEvent",
    "RelativeObserver",
    "make_observer",
    "OBSERVER_CONFIG",
]
