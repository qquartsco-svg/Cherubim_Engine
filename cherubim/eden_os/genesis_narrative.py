"""eden_os.genesis_narrative — 창세기 지리 서사 엔진  (LAYER 4.5c)

"여호와 하나님이 그를 에덴 동산에서 내보내어
 그가 취함을 받은 땅을 갈게 하시니라
 이같이 하나님이 그 사람을 쫓아내시고
 에덴 동산 동쪽에 그룹들과 두루 도는 불 칼을 두어..."
— 창세기 3:23~24

"카인이 여호와 앞을 떠나서 에덴 동쪽 놋 땅에 거주하더니"
— 창세기 4:16

역할
────
  창세기 3~4장의 지리 이동을 에덴 좌표계(남=위)로 해석하고
  현재 지구 위치와 GPP 데이터로 연결하는 서사 엔진.

핵심 흐름
──────────────────────────────────────────────────────────
  에덴(남극 Basin)
    │
    ├─ 아담·이브 추방 → "에덴 동쪽"
    │    에덴 좌표계(남=위)의 동쪽
    │    = 현재 좌표계 역전 시 → 아르헨티나 / 파타고니아 방향
    │    물리적 근거: 에덴 좌표계에서 경도 90°E 방향
    │    현재 지도: 남아메리카 남부 (아르헨티나)
    │
    └─ 카인 추방 → "에덴 동쪽 놋 땅"
         카인 직업: 식물성 제물 → 농경인
         놋 땅 = 카인이 정착할 수 있는 "식물의 땅"
         지구에서 GPP 최대 지점 = 아마존
         아마존 = 지구의 호흡기관 (GPP 최대, O2 공급원)

         아르헨티나(추방지)에서 북쪽으로 이동
         → 아마존 진입 (현재 브라질 중부)
         → 거기서 농경 정착

시스템 엔지니어링 해석
──────────────────────────────────────────────────────────
  아담·이브 추방 = Root Admin EXPELLED
  → 에덴 Basin 외부로 프로세스 이전 (프로세스 마이그레이션)
  → 착지점: 에덴 좌표계 동쪽 = 현재 아르헨티나 위도

  선악과 이벤트 = [사용자님 해석]
  두 에이전트의 최초 독립 상호작용
  (창조주-에이전트 상시 동기화 → 에이전트 간 자율 상호작용으로 전환)
  → AdaptiveStatus: ACTIVE → EXPELLED (에덴 Basin 탈출)

  카인 = 아담의 후계자 라인 중 식물 서브시스템 특화 에이전트
  abel = 동물 서브시스템 (목축)
  충돌(살인) = 자원 할당 충돌 (식물 vs. 동물 GPP 경쟁)
  카인 도주 = 식물 GPP 최대 지역으로 재배치
  아마존   = 지구 GPP 최대 지점 (지구 O2의 ~20% 생산)
           = 지구의 폐(肺) = 에덴 이후 남은 최대 생명 엔진

레이어 분리
──────────────────────────────────────────────
  PHYSICAL_FACT : 좌표 변환·GPP 수치 (계산 가능)
  SCENARIO      : 성경 → 지리 매핑 (파라미터 주입)
  LORE          : 창세기 서술 원문 + 사용자 해석

빠른 시작
──────────────────────────────────────────────
  from cherubim.eden_os.genesis_narrative import GenesisNarrative
  narrative = GenesisNarrative()
  narrative.print_full_chain()
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ── 레이어 상수 ──────────────────────────────────────────────────────────────
PHYSICAL = "PHYSICAL_FACT"
SCENARIO  = "SCENARIO"
LORE      = "LORE"

# ── 핵심 좌표 CONFIG (하드코딩 금지 — 여기서만 정의) ─────────────────────────
NARRATIVE_LOCATIONS: Dict[str, Dict] = {
    "eden_pole": {
        "name_ko":     "에덴 극점 (Eden Pole)",
        "name_lore":   "에덴 동산 수원지",
        # 에덴 좌표계(남=위): 북극점 = +90° (최고점)
        "eden_lat":    +90.0,
        "eden_lon":    0.0,
        # 현재 좌표계
        "current_lat": -90.0,   # 남극점
        "current_lon": 0.0,
        "gpp_relative": 0.0,    # 극지 GPP 최소 (궁창시대는 높았음)
        "note_lore":   "에덴 수원 = 극점 안개 발원지 (창 2:6)",
        "note_system": "EdenWorldEnv valid=True  eden_index=0.904",
    },
    "expulsion_east": {
        "name_ko":     "에덴 동쪽 추방지 (아르헨티나)",
        "name_lore":   "아담·이브 추방지 — 에덴 동쪽",
        # 에덴 좌표계: 동쪽(90°E) + 중위도
        "eden_lat":    +35.0,   # 에덴 기준 중위도
        "eden_lon":    -65.0,   # 에덴 경도 (좌표계 역전 후)
        # 현재 좌표계 역전: lat → -lat
        "current_lat": -35.0,   # 아르헨티나 위도
        "current_lon": -65.0,   # 아르헨티나 경도
        "gpp_relative": 0.35,   # 현재 팜파스 GPP 보통
        "note_lore":   (
            "창 3:24 '에덴 동산 동쪽에 그룹들... 불 칼'\n"
            "에덴 좌표계(남=위)의 '동쪽' = 현재 지도의 남아메리카 방향\n"
            "체루빔+불칼 = CherubimGuard DENY + 재진입 차단"
        ),
        "note_system": (
            "AdminStatus: ACTIVE → EXPELLED\n"
            "CherubimGuard: 재진입 intent='reenter_eden' → DENY 비가역\n"
            "프로세스 마이그레이션: 에덴 Basin 외부로 격리"
        ),
    },
    "nod_amazon": {
        "name_ko":     "놋 땅 — 아마존 (Land of Nod)",
        "name_lore":   "카인 정착지 — 에덴 동쪽 놋 땅",
        # 에덴 좌표계
        "eden_lat":    +3.0,    # 에덴 기준 적도 근처
        "eden_lon":    -60.0,
        # 현재 좌표계
        "current_lat": -3.0,    # 아마존 중심부
        "current_lon": -60.0,   # 브라질 중부
        "gpp_relative": 1.0,    # 지구 GPP 최대 = 1.0 기준
        "note_lore":   (
            "창 4:16 '카인이... 에덴 동쪽 놋 땅에 거주'\n"
            "카인 = 식물성 제물 → 농경인 → GPP 최대 지점에 정착\n"
            "아마존 = 지구의 폐 = GPP 최대 = O2 생산 ~20%"
        ),
        "note_system": (
            "카인 에이전트 특화: intent='index_species' (식물 서브시스템)\n"
            "GPP 최대 지점 = 에이전트의 자원 최적화 정착\n"
            "아마존 = 에덴 붕괴 후 지구에 남은 최대 생명 엔진"
        ),
    },
}

# ── 카인·아벨 충돌 CONFIG ─────────────────────────────────────────────────────
CAIN_ABEL_CONFIG: Dict = {
    "abel_system":    "동물 서브시스템 (목축 — GPP 소비자)",
    "cain_system":    "식물 서브시스템 (농경 — GPP 생산자)",
    "conflict_type":  "자원 할당 충돌 (생산자 vs. 소비자 GPP 경쟁)",
    "resolution":     "소비자 시스템 종료 → 생산자 GPP 지점으로 재배치",
    "cain_destination_gpp_rank": 1,  # 지구 GPP 1위 지점
}


# ═══════════════════════════════════════════════════════════════════════════════
#  LocationNode — 서사 위치 노드
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class LocationNode:
    """서사 체인의 한 지점."""
    key:          str
    name_ko:      str
    name_lore:    str
    eden_lat:     float    # 에덴 좌표계 위도 (남=위)
    eden_lon:     float
    current_lat:  float    # 현재 좌표계
    current_lon:  float
    gpp_relative: float    # 상대 GPP [0~1]
    note_lore:    str
    note_system:  str

    def direction_from_eden_pole(self) -> str:
        """에덴 극점 기준 방위."""
        lon = self.eden_lon % 360
        if 315 <= lon or lon < 45:
            return "북 (현재: 남)"
        elif 45 <= lon < 135:
            return "동 (현재: 서)"
        elif 135 <= lon < 225:
            return "남 (현재: 북)"
        return "서 (현재: 동)"

    def distance_from_eden_km(self) -> float:
        """에덴 극점(-90°, 0°)까지의 구면 거리 [km]."""
        lat1 = math.radians(-90.0)
        lon1 = math.radians(0.0)
        lat2 = math.radians(self.current_lat)
        lon2 = math.radians(self.current_lon)
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = (math.sin(dlat/2)**2 +
             math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2)
        c = 2 * math.asin(math.sqrt(a))
        return round(c * 6371.0, 0)  # km

    def one_line(self) -> str:
        gpp_bar = '█' * int(self.gpp_relative * 10)
        return (
            f"  {self.name_ko:30s}  "
            f"현재({self.current_lat:+.1f}°, {self.current_lon:+.1f}°)  "
            f"에덴({self.eden_lat:+.1f}°)  "
            f"GPP {gpp_bar:<10} {self.gpp_relative:.2f}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  GenesisChain — 서사 체인 (에덴 → 추방 → 카인)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class GenesisChain:
    """창세기 3~4장 지리 이동 체인."""
    nodes:  List[LocationNode]

    def gpp_trend(self) -> str:
        """에덴 → 추방지 → 놋 땅 GPP 변화."""
        if len(self.nodes) < 2:
            return "데이터 부족"
        gpps = [n.gpp_relative for n in self.nodes]
        if gpps[-1] > gpps[0]:
            return "GPP 상승 📈 (에덴 이후 최고점 재발견)"
        return "GPP 하락 📉"

    def print_chain(self) -> None:
        width = 72
        print("\n" + "─" * width)
        print("  🗺  창세기 지리 체인 (에덴 좌표계 → 현재 좌표계)")
        print("─" * width)
        print(f"  {'위치':30s}  현재좌표              에덴좌표    GPP(상대)")
        print("  " + "─" * 68)
        for node in self.nodes:
            print(node.one_line())
        print()
        print(f"  GPP 추세: {self.gpp_trend()}")
        print("─" * width)


# ═══════════════════════════════════════════════════════════════════════════════
#  GenesisNarrative — 전체 서사 엔진
# ═══════════════════════════════════════════════════════════════════════════════

class GenesisNarrative:
    """창세기 3~4장 지리 서사 엔진.

    에덴 좌표계(남=위)로 성경 지명을 해석하고
    GPP·좌표 변환으로 물리적 근거를 제시한다.

    사용자 해석 반영:
      - 선악과 이벤트 = 두 에이전트의 자율 상호작용 전환점
      - 에덴 동쪽 = 아르헨티나 (좌표 역전)
      - 카인 = 식물 서브시스템 에이전트 → 아마존 정착
      - 아마존 = 에덴 이후 지구 최대 생명 엔진

    Parameters
    ----------
    config : dict, optional
        NARRATIVE_LOCATIONS 오버라이드.
    """

    def __init__(self, config: Optional[Dict] = None) -> None:
        self._cfg    = config or NARRATIVE_LOCATIONS
        self._chain  = self._build_chain()

    def _build_chain(self) -> GenesisChain:
        nodes = []
        for key in ["eden_pole", "expulsion_east", "nod_amazon"]:
            c = self._cfg[key]
            nodes.append(LocationNode(
                key          = key,
                name_ko      = c["name_ko"],
                name_lore    = c["name_lore"],
                eden_lat     = c["eden_lat"],
                eden_lon     = c["eden_lon"],
                current_lat  = c["current_lat"],
                current_lon  = c["current_lon"],
                gpp_relative = c["gpp_relative"],
                note_lore    = c["note_lore"],
                note_system  = c["note_system"],
            ))
        return GenesisChain(nodes=nodes)

    # ── 개별 섹션 출력 ────────────────────────────────────────────────────────

    def print_expulsion_analysis(self) -> None:
        """아담·이브 추방 분석."""
        node = self._chain.nodes[1]  # expulsion_east
        print("\n" + "═" * 72)
        print("  🔥 추방 분석 — 에덴 동쪽 = 아르헨티나")
        print("═" * 72)

        print(f"\n  [{LORE}]  창세기 3:23~24")
        for line in node.note_lore.splitlines():
            print(f"    {line}")

        print(f"\n  [{PHYSICAL}]  좌표 변환")
        print(f"    에덴 좌표계(남=위)  :  lat={node.eden_lat:+.1f}°  lon={node.eden_lon:+.1f}°")
        print(f"    좌표 역전 (lat×−1)  :  lat={node.current_lat:+.1f}°  → 현재 아르헨티나")
        print(f"    에덴 극점까지 거리  :  {node.distance_from_eden_km():,.0f} km")
        print(f"    에덴 기준 방위      :  {node.direction_from_eden_pole()}")
        print(f"    상대 GPP           :  {node.gpp_relative:.2f}  (에덴 = 1.0 기준)")

        print(f"\n  [{SCENARIO}]  시스템 해석")
        for line in node.note_system.splitlines():
            print(f"    {line}")
        print("═" * 72)

    def print_cain_analysis(self) -> None:
        """카인 분석 — 식물 GPP 에이전트 → 아마존."""
        node_exp = self._chain.nodes[1]
        node_nod = self._chain.nodes[2]
        cc = CAIN_ABEL_CONFIG

        print("\n" + "═" * 72)
        print("  🌿 카인 분석 — 식물 에이전트 → 아마존 (지구의 폐)")
        print("═" * 72)

        print(f"\n  [{LORE}]  창세기 4:2~16")
        print(f"    카인  : {cc['cain_system']}")
        print(f"    아벨  : {cc['abel_system']}")
        print(f"    충돌  : {cc['conflict_type']}")
        print(f"    결과  : {cc['resolution']}")
        print()
        for line in node_nod.note_lore.splitlines():
            print(f"    {line}")

        print(f"\n  [{PHYSICAL}]  이동 경로 (좌표 역전 기준)")
        dist_exp_nod = abs(node_nod.current_lat - node_exp.current_lat)
        print(f"    추방지 아르헨티나  : lat={node_exp.current_lat:+.1f}°  GPP={node_exp.gpp_relative:.2f}")
        print(f"    ↓ 북쪽으로 이동    : +{dist_exp_nod:.1f}° 위도 (약 {dist_exp_nod*111:.0f}km)")
        print(f"    놋 땅(아마존)      : lat={node_nod.current_lat:+.1f}°  GPP={node_nod.gpp_relative:.2f}  ★지구 1위")
        print()
        print(f"    에덴 극점까지 거리 : {node_nod.distance_from_eden_km():,.0f} km")
        print(f"    에덴 기준 방위     : {node_nod.direction_from_eden_pole()}")

        print(f"\n  [{SCENARIO}]  시스템 해석")
        for line in node_nod.note_system.splitlines():
            print(f"    {line}")

        # GPP 연결
        print(f"\n  [GPP 체인]")
        print(f"    에덴 Basin      →  GPP 최대 (궁창시대, 전 지구 균등)")
        print(f"    에덴 붕괴 이후  →  GPP 집중화 (아마존으로 수렴)")
        print(f"    아마존          →  지구 O2 ~20% 공급 = 에덴 이후 생명 엔진 잔재")
        print(f"    카인 정착       →  GPP 최대 지점 = 생명 유지 가능한 유일 선택지")
        print("═" * 72)

    def print_full_chain(self) -> None:
        """전체 서사 체인 출력."""
        print("\n" + "█" * 72)
        print("  📖 창세기 지리 서사 — 에덴 → 아르헨티나 → 아마존")
        print("  ─── 좌표 역전 + GPP 체인 ───────────────────────────────────")
        print("█" * 72)

        # 1. 선악과 이벤트 해석
        print(f"\n  [{LORE}]  선악과 이벤트 해석")
        print("  ─" * 36)
        print(f"    창세기 3장의 선악과 이벤트:")
        print(f"    → 두 에이전트(아담·이브)의 최초 독립 자율 상호작용")
        print(f"    → 창조주-에이전트 상시 동기화(Always-On SSH)")
        print(f"       에서 에이전트 간 자율 상호작용으로 전환")
        print(f"    → AdminStatus: ACTIVE → EXPELLED")
        print(f"    → 에덴 Basin 탈출 = 프로세스 마이그레이션")
        print(f"    [시스템: knowledge_consumed=True → admin_revoked → 추방]")

        # 2. 지리 체인
        print()
        self._chain.print_chain()

        # 3. 추방 분석
        self.print_expulsion_analysis()

        # 4. 카인 분석
        self.print_cain_analysis()

        # 5. 전체 연결 요약
        print(f"\n  [{SCENARIO}]  전체 연결 요약")
        print("  ─" * 36)
        print(f"    에덴(남극 Basin)")
        print(f"      ↓ 선악과 이벤트 → AdminStatus.EXPELLED")
        print(f"      ↓ 체루빔 가드 → 재진입 영구 차단")
        print(f"    에덴 동쪽 (아르헨티나, 현재 lat −35°)")
        print(f"      ↓ 카인 = 식물 GPP 서브시스템 에이전트")
        print(f"      ↓ 아벨 = 동물 GPP 소비 에이전트")
        print(f"      ↓ 자원 충돌 → 소비자 시스템 종료")
        print(f"    놋 땅 = 아마존 (현재 lat −3°)")
        print(f"      = GPP 지구 최대 지점")
        print(f"      = O2 공급원 (~지구 산소의 20%)")
        print(f"      = 에덴 붕괴 후 남은 최대 생명 엔진")
        print(f"      = 카인의 최적 정착지 (식물 에이전트 자원 최대화)")
        print()
        print(f"  [LORE 최종]")
        print(f"    아마존이 현재 인류에게 중요한 이유:")
        print(f"    단순히 '생물다양성의 보고'가 아니라")
        print(f"    에덴 이후 지구가 생명 유지 능력을 보존한 마지막 엔진.")
        print(f"    카인이 거기 정착한 것은 우연이 아니라")
        print(f"    GPP 최대 지점 = 생명 가능 공간으로의 최적화 이동.")
        print("\n" + "█" * 72)


# ═══════════════════════════════════════════════════════════════════════════════
#  공개 팩토리
# ═══════════════════════════════════════════════════════════════════════════════

def make_genesis_narrative(config: Optional[Dict] = None) -> GenesisNarrative:
    """GenesisNarrative 생성.

    Examples
    --------
    >>> from cherubim.eden_os.genesis_narrative import make_genesis_narrative
    >>> narrative = make_genesis_narrative()
    >>> narrative.print_full_chain()
    """
    return GenesisNarrative(config=config)


__all__ = [
    "LocationNode",
    "GenesisChain",
    "GenesisNarrative",
    "make_genesis_narrative",
    "NARRATIVE_LOCATIONS",
    "CAIN_ABEL_CONFIG",
]
