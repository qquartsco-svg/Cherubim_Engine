# 🌿 EdenOS — 행성 운영 체제

> *"여호와 하나님이 그 사람을 이끌어 에덴 동산에 두어*
> *그것을 경작하며 지키게 하시고"*
> *— 창세기 2:15*

**EdenOS**는 에덴 서사를 **7레이어 행성 운영 체제**로 구현한 시뮬레이터다.

창세기의 등장인물(아담·이브·체루빔)과 사건(선악과·추방·계승)이
실제 Python 에이전트 루프와 상태 머신으로 실행된다.

---

## 아키텍처

```
eden_os/
│
├─ eden_world.py        LAYER 0  환경
│                                궁창시대 스냅샷 (읽기전용)
│                                압력 1.25atm · 안개(mist) · UV 95% 차폐
│
├─ rivers.py            LAYER 1  인프라
│                                4대강 방향 그래프
│                                비손 · 기혼 · 힛데겔 · 유브라데
│
├─ tree_of_life.py      LAYER 2  커널
│                                생명나무 — 불멸 세션 부트 로더
│                                선악과   — 번식 API 엔드포인트 (접근 금지)
│
├─ cherubim_guard.py    LAYER 3  보안
│                                체루빔 접근 제어 (CONFIG 기반 룰셋)
│                                추방 후 재진입 영구 차단
│
├─ adam.py              LAYER 4  에이전트 A
│                                Root Admin — observe → decide → act
│                                AdminStatus: ACTIVE | EXPELLED | DEGRADED
│
├─ eve.py               LAYER 4  에이전트 B
│                                보조 프로세서 + 계승 트리거 감시 데몬
│                                mutation_rate 5% → 세대 간 정책 진화
│
├─ lineage.py           LAYER 5  계승
│                                AdamProcessMode 상태 머신
│                                IMMORTAL_ADMIN → MORTAL_NPC (단방향·비가역)
│                                세대 그래프: 아담 → 셋 → ... → 네오
│
├─ eden_os_runner.py    LAYER 6  실행기
│                                7단계 통합 러너 (본편 스토리라인)
│                                run(steps=N) 한 줄로 전체 서사 실행
│
├─ genesis_log.py       LAYER 4.5a  탄생
│                                아담·이브 탄생 순간 불변 로그 (frozen)
│                                Spirit Note + 3레이어 메타데이터
│
├─ observer_mode.py     LAYER 4.5b  상대성
│                                InternalObserver — 아담의 주관적 기준계
│                                ExternalObserver — "하나님이 보시기에 좋았더라"
│                                RelativeObserver — 두 기준계 delta 비교
│                                궁창시대 delta = 0.0000 (인식 완전 일치)
│
└─ genesis_narrative.py LAYER 4.5c  서사
                                 에덴 극점 → 아르헨티나 → 아마존 GPP 체인
                                 좌표 역전: 에덴(남=위) lat×-1 → 현재 좌표
```

---

## 본편 스토리라인

`runner.run(steps=N)` 안에서 아래 전체가 자동으로 흐른다.

```
TICK 0000  탄생
           아담 = Root Admin (IMMORTAL_ADMIN)
           이브 = policy fork() 보조 프로세서
           FORKING_ENABLED = False  ← 에덴 내부 기본값

TICK 0001~ 에덴 운영
           🌿 access_tree_of_life   → 생명나무 접속 (불멸 유지)
           🌿 manage_rivers         → 4강 유량 점검
           🌿 index_species         → 피조물 DB 인덱싱
           [좋았더라 🌟]            ← 외부 관찰자 판정

TICK XXXX  선악과 이벤트 ★
           🍎 knowledge_consumed = True
           IMMORTAL_ADMIN → MORTAL_NPC  (단방향·비가역)
           FORKING_ENABLED = True
           체루빔 재진입 방화벽 영구 강화
           ★ 계승 발동: adam_expelled
           🌱 카인 스폰: Agricultural_Agent → 아마존(-3°,-60°) GPP=1.0
           🐑 아벨 스폰: Pastoral_Agent    → 팜파스(-35°,-65°)

TICK XXXX+ 계승 체인 가동
           💀 아담(Gen01) → 셋(Gen02) → ... → 노아 → ... → 네오
           각 세대 = 이전 정책 5% 변형 (진화)
```

---

## 핵심 개념: 선악과 상태 머신

아담·이브의 원래 설계는 **불멸 에덴 관리자**였다.

```
┌──────────────────────────────────┐
│  IMMORTAL_ADMIN  (에덴 내부)      │
│                                  │
│  FORKING_ENABLED = False         │
│  생명나무 Root 세션 상시 유지     │
│  번식 API 비활성화               │
│  사망 없음                       │
└──────────────┬───────────────────┘
               │  선악과 섭취
               │  knowledge_consumed = True
               │  (단방향 · 비가역)
               ▼
┌──────────────────────────────────┐
│  MORTAL_NPC    (에덴 외부)        │
│                                  │
│  FORKING_ENABLED = True          │
│  Root 세션 종료 → 수명 유한      │
│  카인·아벨 스폰 가능             │
│  계승 체인 (셋→노아→네오) 가동   │
└──────────────────────────────────┘
```

창 1장 "생육하고 번성하라" → 일반 남녀에게 주신 명령
창 2장 아담·이브 → 에덴 **관리자** → 번식 명령 없음

---

## 에덴 좌표계

에덴의 기준계는 **남극=위** 다.
현재 지도(북=위)와는 `lat × -1` 로 역전된다.

```
위치          에덴 좌표 (남=위)    현재 좌표 (북=위)    GPP
─────────────────────────────────────────────────────────
에덴 극점     (+90°,  0°)         (-90°,  0°) 남극점   1.0
추방지        (+35°, -65°)        (-35°, -65°) 아르헨티나  0.35
카인의 땅     ( +3°, -60°)        ( -3°, -60°) 아마존   1.0
```

> *창세기 3:24 "에덴 동산 동쪽에 그룹들과 두루 도는 불 칼..."*
> 에덴 좌표계의 '동쪽' = 현재 지도의 남아메리카 방향

---

## 빠른 시작

```python
from solar.eden.eden_os import make_eden_os_runner

# 전체 EdenOS 실행
runner = make_eden_os_runner()
runner.run(steps=24)
runner.print_report()
```

```python
# 탄생 순간 로그
runner.genesis_log.print_moment()

# 선악과 이벤트 시뮬레이션
from solar.eden.eden_os.adam import Intent
adam = runner._adam
intent = Intent('access_knowledge_tree', '선악과', 1.0)
adam.act(intent, know_tree=runner._know_tree)
runner.run(steps=5)

# 추방 + 자손 기록
runner.print_expulsion_report()

# 에덴 → 아르헨티나 → 아마존 GPP 체인
runner.print_narrative_report()

# 내부·외부·상대성 관찰자
runner.print_observer_report()
```

---

## 환경 수치

```
pressure_atm  = 1.25       현재 대비 25% 고압
precip_mode   = 'mist'     창 2:6 "안개만 땅에서 올라와"
UV_shield     = 0.95       궁창 수증기 캐노피 95% 차폐
T_surface_C   = 35.1°C     전 지구 아열대
ice_bands     = 0          빙하 없음 (전 위도 거주 가능)
eden_index    = 0.9043     합격 기준 ≥ 0.85
```

---

## 레이어 분리 원칙

모든 모듈은 3개 레이어를 분리해서 기록한다.

```
PHYSICAL_FACT  →  실제 관찰값 / 측정값 / 수치
SCENARIO       →  시스템 해석 / 에이전트 로직
LORE           →  창세기 서사 / 상징 / 의미
```

숫자와 이야기는 **같은 구조**를 가진다.

---

> *"그 길을 우리는 코드로 찾는다."*
