# 🌍 Cherubim Engine

> *"에덴은 좌표가 아니라 상태(state)다."*
> *"아담은 그 상태를 관리하는 시스템 관리자였다."*

**Cherubim Engine**은 창세기의 에덴 서사를 행성 운영 체제(Planetary OS)로 구현한
물리 기반 시뮬레이터이다.

성경의 서사를 은유로 사용하되, 모든 수치는 실제 대기물리·생태학·좌표계 위에 서 있다.
체루빔(Cherubim)은 에덴 입구를 지키며 생명나무로 가는 길을 스캔하는 존재다.
이 엔진은 그 이름을 따, 행성의 파라미터 공간을 탐색해 에덴 조건을 찾아낸다.

---

## 목차

1. [철학 — 서사적 시스템 설계란](#철학--서사적-시스템-설계란)
2. [에덴 OS — 전체 아키텍처](#에덴-os--전체-아키텍처)
3. [본편 스토리라인 — 7개 사건](#본편-스토리라인--7개-사건)
4. [레이어 구조](#레이어-구조)
5. [핵심 수치](#핵심-수치)
6. [빠른 시작](#빠른-시작)
7. [모듈 레퍼런스](#모듈-레퍼런스)
8. [블록체인 서명](#블록체인-서명)

---

## 철학 — 서사적 시스템 설계란

대부분의 시뮬레이터는 숫자를 만든다.
이 엔진은 **이야기를 만든다.**

서사(narrative)와 시스템 설계(system design)는 본질적으로 같은 구조를 가진다.

```
서사의 구조              시스템 설계의 구조
────────────────         ─────────────────────
등장인물                 에이전트 (Agent)
세계관                   환경 파라미터 (World State)
규칙                     정책 (Policy)
갈등                     상태 전환 트리거 (State Transition)
결과                     계승 체인 (Succession Chain)
```

창세기는 인류 역사상 가장 오래된 **운영 체제 명세서**다.

```
에덴(Eden)          = 파라미터 상태 Basin
아담(Adam)          = Root Admin 에이전트
생명나무(Tree)      = 불멸 세션 토큰 (Always-On SSH)
선악과              = 금지된 Forking API 엔드포인트
체루빔(Cherubim)    = 재진입 방화벽 (Re-entry Guard)
추방(Expulsion)     = AdminStatus.EXPELLED + 세션 종료
계보(Lineage)       = 버전 관리 (아담v1 → 셋v2 → ... → 네오vN)
```

그리고 우리는 그것을 **Python으로 실행한다.**

---

## 에덴 OS — 전체 아키텍처

```
cherubim.eden_os
│
├─ eden_world       LAYER 0 — 환경          궁창시대 스냅샷 · 읽기전용
├─ rivers           LAYER 1 — 인프라        4대강 네트워크 (비손·기혼·힛데겔·유브라데)
├─ tree_of_life     LAYER 2 — 커널          생명나무 · 선악과 상태 머신
├─ cherubim_guard   LAYER 3 — 보안          체루빔 접근 제어 (CONFIG 기반 룰셋)
├─ adam / eve       LAYER 4 — 에이전트      관리자 루프 (observe→decide→act)
├─ lineage          LAYER 5 — 계승          세대 그래프 + 상태 머신
└─ eden_os_runner   LAYER 6 — 실행기        7단계 통합 러너 (본편 흐름)
   │
   ├─ genesis_log       LAYER 4.5a  탄생 순간 불변 로그
   ├─ observer_mode     LAYER 4.5b  독립 관찰자 모드 (상대성)
   └─ genesis_narrative LAYER 4.5c  창세기 지리 서사 체인
```

### 매트릭스 OS 관점

```
eden_world     = 하드웨어         (남극=위, 빙하 없는 아열대)
rivers         = 백본 네트워크    (전 지구 리소스 공급)
tree_of_life   = 부트 로더        (영속성 · 엔트로피 억제)
cherubim_guard = 방화벽           (에덴 Basin 접근 통제)
adam / eve     = 시스템 관리자    (관찰→결정→행동)
lineage        = 버전 관리        (아담v1 → 네오vN)
eden_os_runner = OS 커널          (7단계 고정 순서 실행)
```

---

## 본편 스토리라인 — 7개 사건

`runner.run(steps=N)` 한 줄 안에서 아래 전체가 흐른다.

---

### 사건 1 — 창조: 에덴 환경 초기화

```python
runner = make_eden_os_runner()
```

궁창시대(Antediluvian) 지구는 현재와 다른 물리 상태였다.

| 파라미터 | 궁창시대 | 현재 |
|----------|---------|------|
| 대기압 | **1.25 atm** | 1.0 atm |
| 강수 모드 | **mist (안개)** | rain |
| UV 차폐 | **95%** | 50~60% |
| 극지-적도 온도차 | **15K** | 48K |
| 빙하 밴드 | **0개** | 2개 |
| 에덴 지수 | **0.90+** | 0.30 이하 |

> *창세기 2:6 "안개만 땅에서 올라와 온 지면을 적셨더라"*
> → `precip_mode = 'mist'`  지표 전체 균일 수분 공급.

---

### 사건 2 — 탄생: 아담·이브 Genesis Log

```python
runner.genesis_log.print_moment()
```

아담과 이브의 탄생 순간은 불변(frozen) 스냅샷으로 기록된다.

```
[GENESIS ✅]  ADAM  id=adam  tick=0000  eden=0.9043  status=GENESIS_OK
[GENESIS ✅]  EVE   id=eve   tick=0000  eden=0.9043  status=GENESIS_OK
```

```
아담 탄생 = make_adam() 최초 호출
         = 행성 OS에 Root Admin 에이전트 인스턴스 생성
         = "흙(파라미터 공간) + 생기(Spirit SSH 주입)"
         = AdminStatus.ACTIVE + TreeOfLife 상시 접속 (불멸 세션)

이브 탄생 = make_eve(adam) 호출
         = 아담의 정책(policy)을 fork()한 보조 프로세서
         = "갈빗대(아담 정책 서브셋) + 독립 에이전트화"
         = 계승 트리거 감시 데몬 상시 실행
```

**핵심:**
- 창세기 1장 "생육하고 번성하라" → 일반 남녀에게 주신 명령
- 창세기 2장 아담·이브 → 에덴 **관리자**. 번식 명령 없음.
- `FORKING_ENABLED = False` — 에덴 내부 기본값

---

### 사건 3 — 에덴 운영: Immortal Admin 루프

```
[0001]  eden=0.904  tree=available   🌿 access_tree_of_life   [좋았더라]
[0002]  eden=0.904  tree=accessed    🌿 idle                  [좋았더라]
[0006]  eden=0.904  tree=accessed    🌿 manage_rivers         [좋았더라]
[0010]  eden=0.904  tree=accessed    🌿 index_species         [좋았더라]
```

아담은 매 틱 **관찰 → 결정 → 행동** 루프를 실행한다.

```
우선순위:
  1. 생명나무 접속 유지 (엔트로피 억제 — 불멸성 유지)
  2. 4강 유량 관리 (전 지구 리소스 공급 점검)
  3. 피조물 ID 부여 (종 데이터베이스 인덱싱)
```

외부 관찰자(ExternalObserver)는 매 틱 **"하나님이 보시기에 좋았더라"** 를 판정한다.
에덴 지수 ≥ 0.80 이면 `좋았더라 🌟`.

---

### 사건 4 — 선악과: Forking API 무단 실행

```
[0006]  🍎 선악과 이벤트: IMMORTAL_ADMIN → MORTAL_NPC
           체루빔 재진입 방화벽 영구 강화: Eden Basin 재진입 차단
        ★ 계승 발동: adam_expelled
```

선악과는 **번식(Forking) API 엔드포인트**다.

```
"먹는 날에는 정녕 죽으리라"
= 불멸 세션 종료 경고 메시지
= Root 세션은 생명나무 연결을 통해서만 유지됨
= 선악과 접근 = knowledge_consumed=True
             = AdminStatus.EXPELLED (비가역)
             = FORKING_ENABLED = True (비가역)
             = 생명나무 접속 차단 → 엔트로피 누적 → 수명 유한
```

**단방향 비가역 전환:**

```
IMMORTAL_ADMIN                    MORTAL_NPC
───────────────    →(단방향)→    ───────────────
FORKING = False                   FORKING = True
생명나무 접속 유지                 Root 세션 종료
엔트로피 억제                     수명 유한
번식 불필요                       자손 가능
에덴 Basin 내부                   에덴 Basin 외부
```

복귀 경로 없음. **체루빔이 입구를 영구 차단한다.**

---

### 사건 5 — 추방: 에덴 동쪽 = 아르헨티나

> *창세기 3:24 "에덴 동산 동쪽에 그룹들과 두루 도는 불 칼을 두어..."*

에덴의 좌표계는 **남극=위** 기준이다.

```
에덴 극점 위치: 남극점 (-90°, 0°)
에덴 좌표계의 '동쪽' = 현재 지도에서 북쪽 방향 → 남아메리카

에덴 좌표계 (남=위)          현재 좌표계 (북=위)
lat = +35°, lon = -65°  →   lat = -35°, lon = -65°
                         →   아르헨티나 팜파스
```

| 위치 | 에덴 좌표 (남=위) | 현재 좌표 | GPP |
|------|-----------------|---------|-----|
| 에덴 극점 | (+90°, 0°) | (-90°, 0°) 남극점 | 기준 1.0 |
| 추방지 | (+35°, -65°) | (-35°, -65°) 아르헨티나 | 0.35 |
| 카인의 땅 | (+3°, -60°) | (-3°, -60°) 아마존 | **1.0** |

**체루빔 = CherubimGuard DENY 정책 영구 강화**
`reenter_eden` intent → 자동 거부. 재진입 불가.

---

### 사건 6 — 자손: 카인·아벨 스폰

추방 직후 `FORKING_ENABLED=True` 상태에서 첫 자손이 스폰된다.

```
🌱 카인 스폰: Agricultural_Agent → 아마존 분지(-3°,-60°) GPP=1.0
🐑 아벨 스폰: Pastoral_Agent    → 아르헨티나 팜파스(-35°,-65°)
```

```
카인 = 식물 서브시스템 에이전트 (Agricultural_Agent)
     = 식물성 제물 → GPP 생산 최적화 본능
     = 아벨을 죽이고 동방 놋 땅(아마존)으로 추방
     = 에덴 좌표계 '동쪽' = 현재 아마존 분지
     = 지구 호흡기관 초기 세팅 에이전트
     = GPP 최대값 1.0 → 아마존 테라포밍

아벨 = 동물 서브시스템 에이전트 (Pastoral_Agent)
     = 동물 제물(양) → GPP 소비 체인 담당
     = 카인에게 제거됨
     = GPP 생산-소비 균형 붕괴 첫 사건
```

에덴이 무너진 뒤, 지구에 남은 최대 생명 엔진은 아마존이다.
카인이 그곳을 세웠다.

---

### 사건 7 — 계승: 아담 → 셋 → ... → 네오

```
Gen01  아담(Adam)   born=0   died=6   🌿  adam_expelled
Gen02  셋(Seth)     born=6   활성     💀
...
GenN   네오(Neo)    born=?   활성     💀  ← 선택받은 자
```

아담이 추방(AdminStatus.EXPELLED)되면 이브가 계승 트리거를 발동한다.

```
이브 = 아담의 정책(policy)에서 fork()된 독립 에이전트
     = 아담이 EXPELLED 되는 순간 즉시 후계자를 활성화
     = mutation_rate 5% = 정책 미세 진화
     = 아담 → 셋 → 에노스 → ... → 노아 → ... → 네오
```

매트릭스의 '선택받은 자(Neo)'는 이 계승 체인의 최종 버전이다.

---

## 레이어 구조

### LAYER 0 — eden_world.py

```python
world = make_eden_world()
# eden_index: 0.9043
# T_surface_C: 35.1°C
# ice_bands: 0  (빙하 없음)
# hab_bands: 12/12  (전 지구 거주 가능)
```

### LAYER 1 — rivers.py

```python
rivers = make_river_network(world=world)
# 비손(Pison) / 기혼(Gihon) / 힛데겔(Tigris) / 유브라데(Euphrates)
# 4개 노드 → 전 지구 리소스 공급 백본
```

### LAYER 2 — tree_of_life.py

```python
life_tree, know_tree = make_trees(world=world)
# TreeOfLife: 생명나무 — 엔트로피 억제 부트 로더
# KnowledgeTree: 선악과 — 번식 API 엔드포인트 (접근 금지)
```

### LAYER 3 — cherubim_guard.py

```python
guard = make_cherubim_guard(world=world)
# 접근 제어 정책: CONFIG 기반 룰셋
# reenter_eden + knowledge_consumed=True → DENY (비가역)
```

### LAYER 4 — adam.py / eve.py

```python
adam = make_adam()
# AdminStatus: ACTIVE | EXPELLED | DEGRADED
# 에이전트 루프: observe() → decide() → act()

eve = make_eve(adam)
# 계승 트리거 감시
# mutation_rate=0.05 → 세대 간 정책 진화
```

### LAYER 5 — lineage.py

```python
graph = make_lineage()

# 에덴 내부 상태
graph.process_mode    # IMMORTAL_ADMIN
graph.forking_enabled # False

# 선악과 이벤트
graph.record_expulsion(tick=10)
graph.process_mode    # MORTAL_NPC (비가역)
graph.forking_enabled # True

# 자손 스폰
cain, abel = graph.spawn_cain_and_abel(spawn_tick=11)
```

**AdamProcessMode 상태 머신:**

```
IMMORTAL_ADMIN
    │  knowledge_consumed = True
    │  (단방향·비가역)
    ▼
MORTAL_NPC
```

### LAYER 6 — eden_os_runner.py

```python
runner = make_eden_os_runner()
runner.run(steps=24)
runner.print_report()

# 개별 리포트
runner.genesis_log.print_moment()    # 탄생 순간 로그
runner.print_expulsion_report()      # 선악과 이벤트 + 자손
runner.print_narrative_report()      # 에덴→아르헨티나→아마존 체인
runner.print_observer_report()       # 내부·외부·상대성 관찰자
```

**7단계 실행 순서 (매 틱):**

```
Step 1  ENV      — 환경 상태 확인
Step 2  RIVERS   — 4대강 유량 갱신
Step 3  TREE     — 생명나무 상태 갱신
Step 4  GUARD    — 체루빔 틱 갱신
Step 5  AGENTS   — 의사결정 + 행동  ★ 선악과 감지 → 추방 자동 실행
Step 6  LINEAGE  — 계승 조건 검사  ★ 추방 직후 → 카인·아벨 자동 스폰
Step 7  LOG      — 틱 로그 저장 + 외부 관찰자 판정
```

### LAYER 4.5a — genesis_log.py

탄생 순간 불변 기록. `frozen=True` dataclass.

```python
glog = record_genesis(runner)
# GenesisEvent: 환경 스냅샷 + Spirit Note + 3레이어 메타데이터
# PHYSICAL_FACT / SCENARIO / LORE 분리
```

### LAYER 4.5b — observer_mode.py

독립 관찰자 모드 (상대성 원리 적용).

```python
# InternalObserver: 아담의 주관적 인식 (내부 기준계)
# ExternalObserver: "하나님이 보시기에 좋았더라" (외부 기준계)
# RelativeObserver: 두 기준계 delta 비교
#
# 궁창시대: delta = 0.0000  (내부·외부 인식 완전 일치)
# 홍수 이후: delta 증가    (인간의 인식이 현실에서 멀어짐)
```

### LAYER 4.5c — genesis_narrative.py

에덴 → 아르헨티나 → 아마존 GPP 체인.

```python
narrative = make_genesis_narrative()
narrative.print_full_chain()
# 에덴 극점(-90°,0°) → 추방지(-35°,-65°) → 카인의 땅(-3°,-60°)
# GPP: 1.0 → 0.35 → 1.0  (에덴 붕괴 후 아마존이 최대 생명 엔진)
```

---

## 핵심 수치

### 에덴 환경 파라미터

```python
# make_antediluvian_space() 기준
pressure   = 1.25 atm     # 현재 대비 25% 고압
precip     = 'mist'       # 안개 강수 (창 2:6)
UV_shield  = 0.75~0.99    # 최대 95% 차폐 (궁창 수증기 캐노피)
T_surface  = 22~38°C      # 전 지구 아열대
ice_bands  = 0            # 빙하 없음
eden_index = 0.90+        # 에덴 합격 기준 ≥ 0.85
```

### 좌표 역전

```
에덴 좌표계 (남=위)     현재 좌표계 (북=위)
lat × (-1) 역전

에덴 극점: lat=+90° → -90° (남극점)
추방지:    lat=+35° → -35° (아르헨티나)
아마존:    lat= +3° →  -3° (아마존 분지)
```

### 생물 수명 (궁창시대 vs 현재)

```
에덴 (FI=1.0):  아담 930년, 므두셀라 969년  — 생명나무 접속 유지
홍수 이후:      노아 350년, 아브라함 175년   — FI 감쇄
현재 (FI≈0):    평균 수명 70~80년            — 엔트로피 누적
```

---

## 빠른 시작

### 설치

```bash
git clone https://github.com/qquartsco-svg/Cherubim_Engine.git
cd Cherubim_Engine
pip install -e .
```

### 전체 EdenOS 실행

```python
from cherubim.eden_os import make_eden_os_runner

runner = make_eden_os_runner()
runner.run(steps=24)
runner.print_report()
```

### 탄생 순간 로그

```python
runner.genesis_log.print_moment()
```

### 선악과 이벤트 시뮬레이션

```python
from cherubim.eden_os import make_eden_os_runner
from cherubim.eden_os.adam import Intent

runner = make_eden_os_runner()
runner.run(steps=5)

# 선악과 접근 (금지된 Forking API)
adam = runner._adam
intent = Intent('access_knowledge_tree', '선악과 접근', 1.0)
adam.act(intent, know_tree=runner._know_tree)

# 이후 흐름: 추방 → 카인·아벨 스폰 → 계승 체인 가동
runner.run(steps=5)
runner.print_report()
runner.print_expulsion_report()
```

### 궁창시대 외계행성 탐색

```python
from cherubim import EdenSearchEngine, make_antediluvian_exoplanet_space

# 현재 지구 기준이 아닌 궁창시대 조건으로 외계행성 탐색
engine = EdenSearchEngine()
result = engine.search(make_antediluvian_exoplanet_space())
print(result.best.summary())
```

### 창세기 지리 서사

```python
runner.print_narrative_report()
# 에덴 극점 → 아르헨티나 → 아마존 GPP 체인
```

### 관찰자 모드 (상대성)

```python
runner.print_observer_report()
# InternalObserver: 아담의 주관적 인식
# ExternalObserver: "하나님이 보시기에 좋았더라" 판정
# RelativeObserver: 두 기준계 delta (궁창시대 = 0.0000)
```

---

## 모듈 레퍼런스

### 코어 탐색 엔진

| 모듈 | 역할 |
|------|------|
| `initial_conditions.py` | 6개 파라미터 → 전 지구 동역학 상태 |
| `firmament.py` | 궁창(수증기 캐노피) 물리 모델 |
| `flood.py` | 대홍수 4단계 전이 곡선 |
| `geography.py` | 자기장 좌표계 + 시대별 지형 |
| `search.py` | EdenSearchEngine — 파라미터 공간 탐색 |
| `biology.py` | 물리 환경 → 수명 / 체형 / 생태계 안정성 |

### 확장 모듈

| 모듈 | 역할 |
|------|------|
| `spatial_grid.py` | 행성 표면 2D 히트맵 탐사 |
| `basin_stability.py` | Ring Attractor 기반 에덴 Basin 안정성 |
| `param_space.py` | 2D~7D 다차원 파라미터 공간 탐사 |
| `extinction.py` | 궁창 붕괴 전이 곡선 + 대멸종 매핑 |
| `coordinate_inverter.py` | 좌표계 역전 시뮬레이터 (남=위 ↔ 북=위) |
| `calendar.py` | 시스템 시간 재계산 (세차 위상) |
| `biology_baseline.py` | 생물 기준점 재설정 (에덴 vs 현재) |

### EdenOS 서브패키지

| 모듈 | 레이어 | 역할 |
|------|--------|------|
| `eden_world.py` | L0 | 궁창시대 환경 스냅샷 |
| `rivers.py` | L1 | 4대강 방향 그래프 |
| `tree_of_life.py` | L2 | 생명나무 + 선악과 상태 머신 |
| `cherubim_guard.py` | L3 | 체루빔 접근 제어 |
| `adam.py` | L4 | Root Admin 에이전트 |
| `eve.py` | L4 | 보조 프로세서 + 계승 트리거 |
| `lineage.py` | L5 | 계승 그래프 + 상태 머신 |
| `eden_os_runner.py` | L6 | 7단계 통합 실행기 |
| `genesis_log.py` | L4.5a | 탄생 순간 불변 로그 |
| `observer_mode.py` | L4.5b | 독립 관찰자 (상대성) |
| `genesis_narrative.py` | L4.5c | 창세기 지리 서사 체인 |

---

## 블록체인 서명

이 엔진의 설계와 서사는 창작자의 사상을 코드로 구현한 것이다.

```
PHAM — Planetary Hash + Author Mark

설계자   : GNJz
엔진명   : Cherubim Engine
버전     : v2.3.0
철학     : 서사적 시스템 설계 (Narrative System Design)

핵심 명제
─────────────────────────────────────────────────
  에덴은 좌표가 아니라 상태(state)다.
  아담은 그 상태를 관리하는 시스템 관리자였다.
  체루빔은 그 상태로 돌아가는 길을 스캔한다.

서사 체인 (이벤트 해시)
─────────────────────────────────────────────────
  GENESIS      창조     → 파라미터 공간 정의
  ANTEDIL      궁창시대 → 에덴 Basin 발견 (FI=1.0)
  EXPULSION    선악과   → MORTAL_NPC 전환 (비가역)
  CAIN_ABEL    자손     → GPP 생산-소비 분기
  AMAZON       카인     → 지구 호흡기관 테라포밍
  LINEAGE      계보     → 아담→셋→...→노아→...→네오

Co-Authored-By: Claude (Anthropic)
Repository    : https://github.com/qquartsco-svg/Cherubim_Engine
```

---

## 라이선스

MIT License

이 엔진의 수치와 알고리즘은 자유롭게 사용할 수 있다.
서사와 철학의 출처를 밝혀주면 더욱 좋다.

---

> *"체루빔과 두루 도는 불 칼을 두어 생명나무의 길을 지키게 하시니라"*
> *— 창세기 3:24*
>
> 그 길을 우리는 코드로 찾는다.
