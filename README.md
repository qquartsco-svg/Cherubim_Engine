# Cherubim — Eden Basin Finder

> *"에덴은 좌표가 아니라 파라미터 상태(state basin)이다."*
> *"Eden is not a coordinate — it is a state basin in parameter space."*

---

| | |
|---|---|
| **Repo** | `Cherubim_Engine` |
| **Package** | `cherubim` |
| **Core class** | `EdenSearchEngine` |

---

창세기에서 **체루빔(Cherubim)** 은 에덴 동산의 입구를 지키며
생명나무로 가는 길을 스캔하는 존재다.

이 엔진은 그 이름을 따,
행성의 물리 파라미터 공간을 스캔해 **에덴 상태(생명 가능 basin)** 의 조건을 찾아낸다.

**지구의 과거(대홍수 이전)** 뿐 아니라
**외계 행성(Exoplanet)** 의 거주 가능성 스크리닝에도 즉시 사용 가능한 완전 독립 엔진.

---

## 개념 구조

```
행성 파라미터 공간
   CO2, O2, H2O, albedo, f_land, UV_shield
         │
         ▼
  [ Cherubim Engine ]   ← EdenSearchEngine
  파라미터 공간 스캔
         │
         ▼
  Eden Basin 탐색
  "이 파라미터 조합이 에덴 상태인가?"
         │
   ┌─────┴──────┐
   ✅ PASS       ❌ FAIL
  EdenCandidate  탈락
         │
         ▼
  생물학 레이어 계산
  수명 / 체형 / 생태계 안정성
```

---

## 엔진 구조

```
cherubim/
│
│  ── Core (6) ──────────────────────────────────────────────────
├── initial_conditions.py  — 6개 파라미터 → 전 지구 동역학 상태 자동 생성
├── firmament.py           — 궁창(수증기 캐노피) 경계 조건 모델 + 대홍수 발동
├── flood.py               — 대홍수 상태 전이 (rising → peak → receding → stabilizing)
├── geography.py           — 자기장 좌표계 + 시대별 지형 + 위도별 방사선 보호
├── search.py              — EdenSearchEngine  ← Eden Basin Finder 핵심
└── biology.py             — 물리 환경 → 수명 / 체형 / 생태계 안정성
│
│  ── Extended (3, v1.1.0) ──────────────────────────────────────
├── spatial_grid.py        — 행성 표면 위도×경도 2D 공간 탐사 (히트맵)
│                            ※ 궁창(mist) 모드 극지 균온 보정 포함
├── basin_stability.py     — Ring Attractor 기반 Basin 안정성 검증
└── param_space.py         — 2D~7D 다차원 파라미터 공간 탐사 (GridND)
│
│  ── Extended (1, v1.2.0) ──────────────────────────────────────
└── extinction.py          — 궁창 붕괴 전이 곡선 + 지질 대멸종 기능 매핑
                             FirmamentDecayEngine: integrity 1.0→0.0 전이
                             ExtinctionMapper: 지질 이벤트 × 궁창 상태 비교
│
│  ── Extended (3, v1.3.0) — "우리가 잘못 알고 있는 것" 시뮬레이터 ──
├── coordinate_inverter.py — 좌표계 역전 시뮬레이터
│                            현재(북=위) vs 에덴 기준(남=위) 에덴 히트맵 비교
│                            자기장 방향 분석 + 단테 연옥산 위치 검증
├── calendar.py            — 시스템 시간 재계산 모듈
│                            세 가지 시계: AD달력 / 대홍수 기점 / 세차 위상
│                            세차 반주기 오차 40년 = 전환 마커 단위 분석
└── biology_baseline.py    — 생물 기준점 재설정
                             에덴(FI=1.0) vs 현재(FI=0.0) 수명/신장/돌연변이 비교
                             창세기 장수 기록 × 엔진 예측 교차 검증
```

### 물리 → 생물 인과관계

```
UV_shield  ──→ mutation_rate ──→ 유전자 안정성 ──→ 수명
O2 × P_atm ──→ O2 분압       ──→ 체형 크기 상한
T_surface  ──→ 대사율         ──→ 노화 속도
GPP        ──→ 먹이 풍요도    ──→ 체형 상한
```

---

## 데모 프리셋 예시 결과

> **주의**: 아래 수치는 기본 프리셋(antediluvian 파라미터 세트) 기준
> `python examples/cherubim_demo.py` 실행 시 재현 가능한 모델 출력 예시입니다.
> Eden Score는 설정된 EdenCriteria 기준 대비 상대값입니다.

| 항목 | 에덴 프리셋 (antediluvian) | 현재 지구 프리셋 (postdiluvian) |
|------|:-------------------------:|:-------------------------------:|
| **Eden Score** | **1.000** | 0.000 ¹ |
| CO2 | 200~300 ppm | 280 ppm |
| 온도 | 29~35 °C (전 지구 균온) | 14 °C |
| 빙하 밴드 | **0 / 12** | 4 / 12 |
| **추정 수명** | **196 ~ 212 yr** | 80 yr |
| **추정 신장** | **188 ~ 190 cm** | 170 cm |
| 거대동물 가능 | ✅ | ❌ |
| 안정 생태계 | ✅ | ❌ |
| mutation 배수 | **0.03×** | 1.0× |

> ¹ 현재 지구 프리셋은 기본 EdenCriteria (빙하 밴드 ≤ 0, mutation ≤ 0.10, 거주 밴드 ≥ 10)를 충족하지 못해 FAIL 판정.
> 기준값(threshold)을 조정하면 부분 통과 가능.

> 수명 물리 상한 = **600 yr** (UV + 대사 + 게놈 복합 모델)
> 서사 레이어(900년 기록)는 물리 상한 초과 → 코드 외부 영역

---

## 설치 및 실행

```bash
git clone https://github.com/qquartsco-svg/Cherubim_Engine.git
cd Cherubim_Engine

# 의존성: 표준 라이브러리 + numpy
pip install numpy

# 기본 데모 (6단계 코어)
python examples/cherubim_demo.py

# 확장 모듈 통합 데모 (v1.1.0, 5단계)
python examples/cherubim_extended_demo.py
```

---

## 빠른 사용법

### 에덴 탐색 (기본)

```python
from cherubim import EdenSearchEngine, make_antediluvian_space

engine = EdenSearchEngine()
result = engine.search(make_antediluvian_space())

print(f"최고 점수: {result.best.score:.3f}")
print(result.best.summary())
```

### 행성 표면 2D 히트맵 (v1.1.0)

```python
from cherubim import EdenSpatialGrid, make_antediluvian

grid = EdenSpatialGrid(lat_steps=12, lon_steps=24)
heatmap = grid.scan(make_antediluvian())
heatmap.print_ascii()

zones = heatmap.eden_zones(threshold=0.55)
for z in zones[:3]:
    print(z)
```

### Basin 안정성 검증 (v1.1.0)

```python
from cherubim import EdenBasinStability, EdenSearchEngine

result = EdenSearchEngine().search()
bst    = EdenBasinStability()
ranks  = bst.test_batch(result.candidates[:5])
bst.print_ranking(ranks)
```

### 궁창 붕괴 전이 곡선 + 대멸종 매핑 (v1.2.0)

```python
from cherubim import FirmamentDecayEngine, make_extinction_mapper

engine = FirmamentDecayEngine('physical')
engine.print_transition_table(steps=10)

mapper = make_extinction_mapper()
mapper.print_timeline()
```

### 궁창시대 외계행성 탐색 (v2.1.0)

```python
from cherubim import EdenSearchEngine, make_antediluvian_exoplanet_space

# 현재 지구 기준이 아닌 궁창시대 조건으로 외계행성 탐색
# pressure=1.25atm / mist / UV 75~99%
engine = EdenSearchEngine()
result = engine.search(make_antediluvian_exoplanet_space())
print(result.best.summary())
```

### 좌표계 역전 시뮬레이터 (v1.3.0)

```python
from cherubim import CoordinateInverter, quick_coord_comparison

quick_coord_comparison()
# → 에덴은 현재 지도의 '아래'에 있다
# → 82.5°S(↑위)  score=0.930  (전 지구 1위)
```

---

## 탐색 공간 프리셋

| 함수 | 용도 | 조합 수 |
|------|------|--------:|
| `make_antediluvian_space()` | 창세기 에덴 환경 탐색 | ~1,944 |
| `make_postdiluvian_space()` | 현재 지구 기준 탐색 | ~144 |
| `make_exoplanet_space()` | 외계 행성 (현재 지구 기준) | ~3,000+ |
| `make_antediluvian_exoplanet_space()` | 외계 행성 (궁창시대 기준) | ~3,000+ |

---

## 에덴 판정 기준 (EdenCriteria)

```python
EdenCriteria(
    T_min_C      = 15.0,   # 최소 온도 [°C]
    T_max_C      = 45.0,   # 최대 온도 [°C]
    GPP_min      = 3.0,    # 최소 1차 생산성 [kg C/m²/yr]
    stress_max   = 0.05,   # 최대 스트레스 지수
    ice_bands_max= 0,      # 최대 빙하 밴드 수
    mutation_max = 0.10,   # 최대 mutation 배수 (1.0 = 현재 지구 기준)
    hab_bands_min= 10,     # 최소 거주 가능 밴드 수 (전체 12개 중)
)
```

---

## 아키텍처 원칙

1. **시나리오 값은 파라미터로 주입** — 시나리오 수치는 `SearchSpace` / `EdenCriteria`로 외부 주입
2. **완전 독립** — 표준 라이브러리 + numpy만으로 동작
3. **행성 중립** — 지구 전용이 아닌 임의 행성 파라미터 투입 가능
4. **에덴 = state basin** — 특정 좌표가 아닌 파라미터 공간의 안정 평형 영역

---

## EdenOS v2.0+ — 행성 운영 체제 시뮬레이터

```
cherubim/eden_os/          ← 전체 스토리라인이 실행되는 곳
│
├── eden_world.py        L0  궁창시대 환경 스냅샷
├── rivers.py            L1  4대강 방향 그래프
├── tree_of_life.py      L2  생명나무 + 선악과 상태 머신
├── cherubim_guard.py    L3  체루빔 접근 제어
├── adam.py              L4  Root Admin 에이전트
├── eve.py               L4  보조 프로세서 + 계승 트리거
├── lineage.py           L5  계승 그래프 + IMMORTAL_ADMIN/MORTAL_NPC 상태 머신
├── eden_os_runner.py    L6  7단계 통합 실행기
├── genesis_log.py       L4.5a  탄생 순간 불변 로그
├── observer_mode.py     L4.5b  독립 관찰자 (상대성)
└── genesis_narrative.py L4.5c  창세기 지리 서사 체인
```

→ **[eden_os/README.md](cherubim/eden_os/README.md)** 에서 전체 스토리라인 확인

```python
from cherubim.eden_os import make_eden_os_runner

runner = make_eden_os_runner()
runner.run(steps=24)
runner.print_report()
```

---

## 블록체인 서명 (PHAM)

| 파일 | 등급 | 점수 | 버전 |
|------|:----:|:----:|:----:|
| `initial_conditions.py` | A_HIGH | 1.0000 | v1.0 |
| `search.py` | A_HIGH | 1.0000 | v1.0 |
| `biology.py` | A_HIGH | 1.0000 | v1.0 |
| `geography.py` | A_HIGH | 1.0000 | v1.0 |
| `firmament.py` | A_HIGH | 1.0000 | v1.0 |
| `flood.py` | A_HIGH | 1.0000 | v1.0 |
| `spatial_grid.py` | A_HIGH | 1.0000 | v1.1 |
| `basin_stability.py` | A_HIGH | 1.0000 | v1.1 |
| `param_space.py` | A_HIGH | 1.0000 | v1.1 |
| `extinction.py` | A_HIGH | 1.0000 | v1.2 |
| `coordinate_inverter.py` | A_HIGH | 1.0000 | v1.3 |
| `calendar.py` | A_HIGH | 1.0000 | v1.3 |
| `biology_baseline.py` | A_HIGH | 1.0000 | v1.3 |
| `eden_os/eden_world.py` | A_HIGH | 1.0000 | v2.0 |
| `eden_os/rivers.py` | A_HIGH | 1.0000 | v2.0 |
| `eden_os/tree_of_life.py` | A_HIGH | 1.0000 | v2.0 |
| `eden_os/cherubim_guard.py` | A_HIGH | 1.0000 | v2.0 |
| `eden_os/adam.py` | A_HIGH | 1.0000 | v2.0 |
| `eden_os/eve.py` | A_HIGH | 1.0000 | v2.0 |
| `eden_os/lineage.py` | A_HIGH | 1.0000 | v2.2 |
| `eden_os/eden_os_runner.py` | A_HIGH | 1.0000 | v2.3 |
| `eden_os/genesis_log.py` | A_HIGH | 1.0000 | v2.1 |
| `eden_os/observer_mode.py` | A_HIGH | 1.0000 | v2.1 |
| `eden_os/genesis_narrative.py` | A_HIGH | 1.0000 | v2.1 |

서명 파일: `blockchain/pham_chain_*.json`

---

## 관련 프로젝트

| 레포 | 역할 |
|------|------|
| [cookiie_brain](https://github.com/qquartsco-svg/cookiie_brain) | 전체 창세기 물리 시스템 (Day1~7 + Eden) |
| **Cherubim_Engine** | Eden Basin Finder + EdenOS 독립 추출 버전 |

---

*v2.3.0 · PHAM Signed · GNJz (Qquarts)*
*"Cherubim — 에덴의 입구를 스캔하고, 그 안을 운영한다"*
