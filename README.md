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

### 행성 표면 빠른 스캔 — 원라이너 (v1.1.0)

```python
from cherubim import quick_surface_scan, make_antediluvian

# 한 줄로 스캔 + ASCII 히트맵 출력 + Eden Zone 목록 반환
heatmap = quick_surface_scan(make_antediluvian(), threshold=0.55)
# → ★ Eden Zone 12개 발견 (52°N·S, 37°N·S 온대 중심)
```

### Basin 안정성 검증 (v1.1.0)

```python
from cherubim import EdenBasinStability, make_antediluvian, EdenSearchEngine

# 탐색 → 상위 후보 Basin 안정성 검증
result = EdenSearchEngine().search()
bst    = EdenBasinStability()   # Ring Attractor 자동 연결 (없으면 Lyapunov 수학 대체)
ranks  = bst.test_batch(result.candidates[:5])
bst.print_ranking(ranks)
# → 🌟 S등급  Basin depth=0.993  복귀율=100%  (완벽한 안정 어트랙터)
```

### 다차원 파라미터 공간 탐사 (v1.1.0)

```python
from cherubim import EdenParamScanner, CO2_AXIS, TEMP_AXIS, O2_AXIS

scanner = EdenParamScanner()

# 2D 기후 상태도
result2d = scanner.scan_2d(CO2_AXIS, TEMP_AXIS)
result2d.print_heatmap()

# 3D Basin 탐색
result3d = scanner.scan_nd([CO2_AXIS, O2_AXIS, TEMP_AXIS])
shape = scanner.analyze_basin_shape(result3d)
print(shape.summary())
```

### 궁창 붕괴 전이 곡선 + 대멸종 매핑 (v1.2.0)

```python
from cherubim import FirmamentDecayEngine, make_extinction_mapper

# 궁창 완전도(1.0→0.0) 전이 테이블 출력
engine = FirmamentDecayEngine('physical')
engine.print_transition_table(steps=10)

# 지질 대멸종 × 궁창 상태 타임라인 매핑
mapper = make_extinction_mapper()
mapper.print_timeline()
mapper.print_eden_curve()
```

**출력 예시:**

```
FI=1.00  캄브리아 대폭발  UV=0.950  돌연변이=0.010x  에덴지수=0.980
FI=0.75  오르도비스기 멸종 UV=0.712  돌연변이=0.032x  85% 종 소멸
FI=0.30  페름기 대멸종    UV=0.285  돌연변이=0.251x  96% 종 소멸
FI=0.05  K-Pg 충돌        UV=0.048  돌연변이=0.794x  에덴지수=0.143
FI=0.00  현재 빙하기      UV=0.000  돌연변이=1.000x  에덴지수=0.042
```

> **결론**: FI(궁창 완전도)가 0.30 이하로 떨어질 때마다 대멸종이 발생한다.
> 궁창은 UV 차단 + 균온 + 돌연변이 억제의 통합 보호막이었다.

```python
# FloodEngine에 홍수 직전 궁창 상태 지정
from cherubim import make_flood_engine

fe = make_flood_engine(firmament_integrity=1.0)   # 창세기 시나리오
fe = make_flood_engine(firmament_integrity=0.30)  # 페름기 시나리오
fe = make_flood_engine(firmament_integrity=0.05)  # K-Pg 시나리오
```

---

### 좌표계 역전 시뮬레이터 — "지도가 뒤집혀 있다" (v1.3.0)

```python
from cherubim import CoordinateInverter, quick_coord_comparison

# 현재(북=위) vs 에덴 기준(남=위) 에덴 히트맵 비교
quick_coord_comparison()
# → 결론: 에덴은 현재 지도의 '아래'에 있다
# → 82.5°S(↑위)  score=0.930  (전 지구 1위)

inverter = CoordinateInverter()
inverter.print_magnetic_analysis()
# → 자기 N극 발원지(남극) = 에덴 기준 좌표계 위쪽
```

### 시스템 시간 재계산 — "달력이 틀렸다" (v1.3.0)

```python
from cherubim import SystemClock, quick_time_analysis

quick_time_analysis()
# → AD 2026년 = 시스템 클럭 12,926년의 15.7% 구간
# → 세차 반주기(12,886년) 대비 +40년 오차
# → TRANSITION_UNIT = 40 (모세 광야 40년과 동일 단위)
```

**출력 예시:**

```
[시계 2] 시스템 클럭 (대홍수 기점 경과)
  대홍수 추정: BC 10,900년
  경과: 12,926년

[핵심 오차]
  세차 반주기        = 12,886년
  대홍수 이후 경과   = 12,926년
  차이               = +40년  → 모세 광야 40년과 동일 단위
```

### 생물 기준점 재설정 — "우리가 다운그레이드됐다" (v1.3.0)

```python
from cherubim import BiologyBaseline, quick_biology_report

quick_biology_report()
# → 수명  80년  = 에덴 기준의 10.0%
# → 신장  170cm = 에덴 기준의 55.6%
# → 돌연변이율  100배 증가
# → 종 다양성   에덴 기준의 4.2% 남음
```

**출력 예시:**

```
파라미터          에덴 기준    현재    현재/에덴
수명               800년     80년     10.0%
신장               306cm    170cm     55.6%
돌연변이율        0.0100x  1.0000x   100배 증가
암 발생률           0.40%   40.00%   100배 증가
종 다양성           100%      4.2%    4.2% 남음
```

### 외계 행성 거주 가능성 탐색

```python
from cherubim import EdenSearchEngine, make_exoplanet_space

# 태양보다 약한 항성 (적색 왜성 등) 궤도 행성
result = EdenSearchEngine().search(
    make_exoplanet_space(stellar_flux_scale=0.85)
)
print(result.best.summary())
```

### 에덴 vs 현재 생물학 비교

```python
from cherubim import compare_biology, make_antediluvian, make_postdiluvian

print(compare_biology(make_antediluvian(), make_postdiluvian()))
```

---

## 탐색 공간 프리셋

| 함수 | 용도 | 조합 수 |
|------|------|--------:|
| `make_antediluvian_space()` | 창세기 에덴 환경 탐색 | ~1,944 |
| `make_postdiluvian_space()` | 현재 지구 기준 탐색 | ~144 |
| `make_exoplanet_space()` | 외계 행성 거주 가능성 스크리닝 | ~3,000+ |

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

모든 기준값은 `EdenCriteria` 파라미터로 주입 가능. 모델 상수는 각 모듈 내 `_constants` 블록으로 분리.

---

## 아키텍처 원칙

1. **시나리오 값은 파라미터로 주입** — 시나리오 수치는 `SearchSpace` / `EdenCriteria`로 외부 주입, 모델 상수는 각 모듈 내 계수로 분리
2. **완전 독립** — 표준 라이브러리 + numpy만으로 동작, 외부 엔진 의존 없음 (Ring Attractor / Grid Engine은 선택적 연동)
3. **행성 중립** — 지구 전용이 아닌 임의 행성 파라미터 투입 가능
4. **에덴 = state basin** — 특정 좌표가 아닌 파라미터 공간의 안정 평형 영역

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

서명 파일: `blockchain/pham_chain_*.json`

---

## 관련 프로젝트

| 레포 | 역할 |
|------|------|
| [cookiie_brain](https://github.com/qquartsco-svg/cookiie_brain) | 전체 창세기 물리 시스템 (Day1~7 + Eden) |
| **Cherubim_Engine** | Eden Basin Finder 독립 추출 버전 |

---

*v1.3.0 · PHAM Signed · GNJz (Qquarts)*
*"Cherubim — 에덴의 입구를 스캔하는 엔진"*
