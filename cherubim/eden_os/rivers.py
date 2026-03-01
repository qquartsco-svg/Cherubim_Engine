"""eden_os.rivers — 에덴 4대강 네트워크  (Step 2 / 7)

"강이 에덴에서 흘러나와 동산을 적시고 거기서 나뉘어 네 근원이 되었더니"
— 창세기 2:10

역할
────
  에덴 수원(root node)에서 전 지구로 뻗어나가는
  4대강(비손·기혼·힛데겔·유브라데)을 **방향 그래프**로 모델링한다.

  강은 "좌표 점"이 아니라 "흐름/분기/연결"이다.
  따라서 RiverNode(지점) + RiverEdge(연결) + RiverNetwork(그래프) 로 표현한다.

물리 해석 (SCENARIO 레이어)
──────────────────────────────────────────────
  에덴 수원 = 극점(극지 저기압 중심) 에서 안개(mist)가 솟아올라 지표 전체에 공급
  4대강 분기 = 극점 방사형 흐름이 4방향(사분면)으로 분기
  유량 = mist 수분 공급량 × 밴드 면적 × 경사도(고도차)

  현재 중동 4강(티그리스·유프라테스·나일·인더스) 과의 관계:
    좌표계 역전(coordinate_inverter.py) 적용 시 에덴 4강의 반사 좌표와 근접

레이어 분리
──────────────────────────────────────────────
  PHYSICAL_FACT : 유량·방향·분기점 (물리 계산 가능)
  SCENARIO      : 4강 이름·에덴 수원 위치 (파라미터 주입)
  LORE          : 창세기 명칭·현재 지명 비교 (서사 맥락)

빠른 시작
──────────────────────────────────────────────
  from cherubim.eden_os import RiverNetwork, make_river_network
  from cherubim.eden_os import make_eden_world

  world = make_eden_world()
  net   = make_river_network(world)
  net.print_summary()
  net.step(tick=1)   # 유량 1틱 갱신
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .eden_world import EdenWorldEnv

# ── 레이어 상수 ──────────────────────────────────────────────────────────────
PHYSICAL = "PHYSICAL_FACT"
SCENARIO  = "SCENARIO"
LORE      = "LORE"

# ── 4대강 기본 CONFIG (하드코딩 금지 — 여기서만 정의) ───────────────────────
RIVER_CONFIG: Dict[str, Dict] = {
    "pishon": {
        "name_ko":    "비손",
        "name_en":    "Pishon",
        "quadrant":   "SW",          # 에덴 기준 방위 (남=위 좌표계)
        "band_range": (0, 3),        # 12밴드 인덱스 범위
        "mineral":    "gold",        # 창 2:11 "금이 있고"
        "note_lore":  "하윌라 땅을 흐름  (금·베델리엄·홍마노)",
    },
    "gihon": {
        "name_ko":    "기혼",
        "name_en":    "Gihon",
        "quadrant":   "SE",
        "band_range": (0, 3),
        "mineral":    "unknown",
        "note_lore":  "구스 온 땅을 둘러 흐름",
    },
    "hiddekel": {
        "name_ko":    "힛데겔",
        "name_en":    "Hiddekel (Tigris)",
        "quadrant":   "NW",
        "band_range": (9, 12),
        "mineral":    "unknown",
        "note_lore":  "앗수르 동쪽으로 흐름  (현재 좌표계 역전 후: NW→SE)",
    },
    "euphrates": {
        "name_ko":    "유브라데",
        "name_en":    "Euphrates",
        "quadrant":   "NE",
        "band_range": (9, 12),
        "mineral":    "unknown",
        "note_lore":  "창 2:14 이름만 기록 (가장 잘 알려진 강)",
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
#  RiverNode — 강 위의 한 지점
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class RiverNode:
    """강 네트워크의 노드(지점).

    kind
    ----
    'source'   : 에덴 수원 (루트 노드, 단 1개)
    'fork'     : 분기점 (source → 4강으로 갈라지는 지점)
    'river'    : 각 대강의 중간 지점
    'delta'    : 하구 (흐름 종착지)
    """
    id:       str
    kind:     str           # source | fork | river | delta
    band_idx: int           # 12밴드 인덱스 (0=남극, 11=북극)
    river_id: Optional[str] = None   # 소속 강 이름 (source/fork 는 None)
    meta:     Dict = field(default_factory=dict)

    def __str__(self) -> str:
        lat = -82.5 + self.band_idx * 15.0
        return f"RiverNode({self.id}  kind={self.kind}  lat={lat:+.1f}°)"


# ═══════════════════════════════════════════════════════════════════════════════
#  RiverEdge — 노드 사이 흐름 연결
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class RiverEdge:
    """두 노드를 잇는 흐름(directed edge).

    flow_rate   : 현재 유량 [0~1 정규화]
    seasonality : 계절성 팩터 [0=없음, 1=최대 계절 변동]
    """
    src:         str    # 출발 노드 id
    dst:         str    # 도착 노드 id
    river_id:    str    # 소속 강 이름
    flow_rate:   float = 1.0   # 기준 유량 [0~1]
    seasonality: float = 0.0   # 궁창시대 = 계절 없음 → 0.0

    def __str__(self) -> str:
        return (
            f"RiverEdge({self.src} → {self.dst}  "
            f"river={self.river_id}  flow={self.flow_rate:.3f})"
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  RiverState — 틱별 스냅샷
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class RiverState:
    """한 틱(step)에서의 4대강 상태 스냅샷."""
    tick:          int
    total_flow:    float              # 전체 유량 합
    river_flows:   Dict[str, float]   # {강 이름: 유량}
    mist_supply:   float              # 안개 수분 공급량
    log:           List[str] = field(default_factory=list)

    def __str__(self) -> str:
        flows = "  ".join(
            f"{k}={v:.3f}" for k, v in self.river_flows.items()
        )
        return f"[tick={self.tick:04d}]  total={self.total_flow:.3f}  {flows}"


# ═══════════════════════════════════════════════════════════════════════════════
#  RiverNetwork — 4대강 방향 그래프
# ═══════════════════════════════════════════════════════════════════════════════

class RiverNetwork:
    """에덴 4대강 방향 그래프.

    구조
    ────
      [source: EDEN_ROOT]
            │
            ▼
      [fork: GREAT_FORK]
       ┌────┼────┬────┐
       ▼    ▼    ▼    ▼
     비손  기혼  힛데겔  유브라데
       │    │    │       │
       ▼    ▼    ▼       ▼
     delta delta delta  delta
    """

    def __init__(self, world: EdenWorldEnv, config: Dict = None) -> None:
        self._world  = world
        self._config = config or RIVER_CONFIG
        self._nodes: Dict[str, RiverNode] = {}
        self._edges: List[RiverEdge]      = []
        self._history: List[RiverState]   = []
        self._tick = 0
        self._mist_base = self._calc_mist_base()
        self._build_network()

    # ── 내부 구축 ─────────────────────────────────────────────────────────────

    def _calc_mist_base(self) -> float:
        """안개 수분 공급량 계산.
        H2O_atm_frac × pressure_atm 비례 (궁창 효과 반영).
        """
        return min(1.0, self._world.ic.H2O_atm_frac * self._world.ic.pressure_atm * 10.0)

    def _add_node(self, node: RiverNode) -> None:
        self._nodes[node.id] = node

    def _add_edge(self, edge: RiverEdge) -> None:
        self._edges.append(edge)

    def _build_network(self) -> None:
        """SOURCE → FORK → 4강 → DELTA 구조 생성."""
        # 수원 (에덴 극점 = band[0], 남극)
        self._add_node(RiverNode(
            id="EDEN_ROOT", kind="source", band_idx=0,
            meta={"desc_lore": "에덴 수원 — 안개가 땅에서 올라옴 (창 2:6)"},
        ))
        # 분기점 (극점 → 방사형 분기, band[1])
        self._add_node(RiverNode(
            id="GREAT_FORK", kind="fork", band_idx=1,
            meta={"desc_lore": "4대강 분기점 — '거기서 나뉘어 네 근원이 되었더니'"},
        ))
        self._add_edge(RiverEdge(
            src="EDEN_ROOT", dst="GREAT_FORK",
            river_id="main", flow_rate=1.0, seasonality=0.0,
        ))

        # 4강 노드 & 엣지 생성
        for rid, cfg in self._config.items():
            b_start, b_end = cfg["band_range"]

            # 중간 지점
            mid_id = f"{rid.upper()}_MID"
            self._add_node(RiverNode(
                id=mid_id, kind="river",
                band_idx=(b_start + b_end) // 2,
                river_id=rid,
                meta={"quadrant": cfg["quadrant"], "mineral": cfg["mineral"]},
            ))

            # 하구
            delta_id = f"{rid.upper()}_DELTA"
            self._add_node(RiverNode(
                id=delta_id, kind="delta",
                band_idx=min(b_end, 11),
                river_id=rid,
                meta={"note_lore": cfg["note_lore"]},
            ))

            # FORK → MID → DELTA
            flow = self._calc_river_flow(rid, self._mist_base)
            self._add_edge(RiverEdge(
                src="GREAT_FORK", dst=mid_id,
                river_id=rid, flow_rate=flow, seasonality=0.0,
            ))
            self._add_edge(RiverEdge(
                src=mid_id, dst=delta_id,
                river_id=rid, flow_rate=flow * 0.9, seasonality=0.0,
            ))

    def _calc_river_flow(self, river_id: str, mist: float) -> float:
        """강별 기준 유량 계산.
        각 강은 mist 공급량의 25%씩 균등 분배 (분기 4개).
        미래 확장: GPP, 지형, 밴드 고도 등 반영 가능.
        """
        base = mist / 4.0
        # 강마다 소폭 차별화 (CONFIG 기반 확장 여지)
        factor = {"pishon": 1.05, "gihon": 0.98, "hiddekel": 1.02, "euphrates": 0.95}
        return round(base * factor.get(river_id, 1.0), 4)

    # ── 틱 갱신 ───────────────────────────────────────────────────────────────

    def step(self, tick: int = 1) -> RiverState:
        """유량 1틱 갱신 → RiverState 반환.

        궁창시대(seasonality=0)에서는 유량이 안정적으로 유지된다.
        미래 확장: FI 감소 시 seasonality 증가, 유량 감소 모델링 가능.
        """
        self._tick += tick
        mist_now = self._mist_base  # 궁창시대 = 안정 공급

        river_flows: Dict[str, float] = {}
        log_lines: List[str] = []

        for rid in self._config:
            mid_edge = next(
                (e for e in self._edges if e.river_id == rid and e.src == "GREAT_FORK"),
                None,
            )
            if mid_edge:
                # 계절성 적용 (현재 0 → 변동 없음)
                seasonal = 1.0 - mid_edge.seasonality * 0.5 * math.sin(
                    2 * math.pi * self._tick / 365.0
                )
                flow = round(mid_edge.flow_rate * seasonal * mist_now / self._mist_base, 4)
                river_flows[self._config[rid]["name_ko"]] = flow
                log_lines.append(
                    f"  {self._config[rid]['name_ko']:4s}({rid:10s})  flow={flow:.4f}"
                )

        state = RiverState(
            tick        = self._tick,
            total_flow  = round(sum(river_flows.values()), 4),
            river_flows = river_flows,
            mist_supply = round(mist_now, 4),
            log         = log_lines,
        )
        self._history.append(state)
        return state

    # ── 조회 ──────────────────────────────────────────────────────────────────

    def get_node(self, node_id: str) -> Optional[RiverNode]:
        return self._nodes.get(node_id)

    def get_edges_for_river(self, river_id: str) -> List[RiverEdge]:
        return [e for e in self._edges if e.river_id == river_id]

    def history(self) -> List[RiverState]:
        return list(self._history)

    # ── 출력 ──────────────────────────────────────────────────────────────────

    def print_summary(self) -> None:
        width = 70
        print("=" * width)
        print("  🌊 에덴 4대강 네트워크 (RiverNetwork)")
        print("=" * width)

        print(f"\n  수원 위치    : {self._nodes['EDEN_ROOT']}")
        print(f"  분기점       : {self._nodes['GREAT_FORK']}")
        print(f"  안개 공급량  : {self._mist_base:.4f}  "
              f"(H2O={self._world.ic.H2O_atm_frac:.2f} × P={self._world.ic.pressure_atm:.2f})")

        print(f"\n  {'─'*66}")
        print(f"  {'4대강 정보':^66}")
        print(f"  {'─'*66}")
        print(f"  {'강 이름':<8} {'방위':<4} {'밴드':<8} {'기준유량':>8}  서사 메모")
        print(f"  {'─'*66}")
        for rid, cfg in self._config.items():
            edge = next(
                (e for e in self._edges if e.river_id == rid and e.src == "GREAT_FORK"),
                None,
            )
            flow = edge.flow_rate if edge else 0.0
            print(
                f"  {cfg['name_ko']:<4}({cfg['name_en'][:8]:<8})  "
                f"{cfg['quadrant']:<4} "
                f"band{cfg['band_range'][0]}~{cfg['band_range'][1]}  "
                f"{flow:>8.4f}  {cfg['note_lore'][:30]}"
            )

        print(f"\n  [{LORE}]")
        print("    에덴 기준(남=위) 좌표계에서 4강 방위:")
        for rid, cfg in self._config.items():
            print(f"      {cfg['name_ko']}  →  에덴 기준 {cfg['quadrant']} 방향")
        print("    → 현재 지도(북=위)에서는 방향이 반전되어 보인다")
        print("      (coordinate_inverter.py 참조)")

        print(f"\n  노드 수: {len(self._nodes)}  |  엣지 수: {len(self._edges)}")
        print("=" * width)

    def print_flow_log(self) -> None:
        """마지막 틱 유량 로그 출력."""
        if not self._history:
            print("  (유량 이력 없음 — step() 먼저 호출)")
            return
        last = self._history[-1]
        print(f"\n  [tick={last.tick:04d}]  mist={last.mist_supply:.4f}  total={last.total_flow:.4f}")
        for line in last.log:
            print(line)


# ═══════════════════════════════════════════════════════════════════════════════
#  공개 팩토리
# ═══════════════════════════════════════════════════════════════════════════════

def make_river_network(
    world: Optional[EdenWorldEnv] = None,
    config: Optional[Dict] = None,
) -> RiverNetwork:
    """RiverNetwork 생성.

    Parameters
    ----------
    world  : EdenWorldEnv, optional  —  None 이면 make_eden_world() 사용
    config : dict, optional          —  None 이면 기본 RIVER_CONFIG 사용

    Examples
    --------
    >>> from cherubim.eden_os import make_river_network
    >>> net = make_river_network()
    >>> net.print_summary()
    >>> state = net.step()
    >>> print(state)
    """
    if world is None:
        from .eden_world import make_eden_world
        world = make_eden_world()

    return RiverNetwork(world=world, config=config)
