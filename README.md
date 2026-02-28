# Cherubim — Eden Basin Finder

> *"에덴은 좌표가 아니라 파라미터 상태(state basin)이다."*
> *"Eden is not a coordinate — it is a state basin in parameter space."*

---

창세기에서 **체루빔(Cherubim)** 은 에덴 동산의 입구를 지키며
생명나무로 가는 길을 스캔하는 존재다.

이 엔진은 그 이름을 따,
행성의 물리 파라미터 공간을 스캔해 **에덴 상태(생명 가능 basin)** 의 조건을 찾아낸다.

**지구의 과거(대홍수 이전)** 뿐 아니라
**외계 행성(Exoplanet)** 의 거주 가능성 탐색에도 즉시 투입 가능한 완전 독립 엔진.

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
├── initial_conditions.py  — 6개 파라미터 → 전 지구 동역학 상태 자동 생성
├── firmament.py           — 궁창(수증기 캐노피) 물리 모델 + 대홍수 발동
├── flood.py               — 대홍수 4단계 전이 곡선 (rising → peak → receding → stabilizing)
├── geography.py           — 자기장 좌표계 + 시대별 지형 + 위도별 방사선 보호
├── search.py              — EdenSearchEngine ← Eden Basin Finder 핵심
└── biology.py             — 물리 환경 → 수명 / 체형 / 생태계 안정성
```

### 물리 → 생물 인과관계

```
UV_shield  ──→ mutation_rate ──→ 유전자 안정성 ──→ 수명
O2 × P_atm ──→ O2 분압       ──→ 체형 크기 상한
T_surface  ──→ 대사율         ──→ 노화 속도
GPP        ──→ 먹이 풍요도    ──→ 체형 상한
```

---

## 탐색 결과 (지구 antediluvian 기준)

| 항목 | 에덴 (대홍수 이전) | 현재 지구 |
|------|:-----------------:|:---------:|
| **Eden Score** | **1.000** | 0.000 |
| CO2 | 200~300 ppm | 280 ppm |
| 온도 | 29~35 °C (전 지구 균온) | 14 °C |
| 빙하 밴드 | **0 / 12** | 4 / 12 |
| **추정 수명** | **196 ~ 212 yr** | 80 yr |
| **추정 신장** | **188 ~ 190 cm** | 170 cm |
| 거대동물 가능 | ✅ | ❌ |
| 안정 생태계 | ✅ | ❌ |
| mutation 배수 | **0.03×** | 1.0× |

> 수명 물리 상한 = **600 yr** (UV + 대사 + 게놈 복합 효과)
> 서사 레이어 (900년) = 물리 상한 초과 → 코드 밖 영역

---

## 설치 및 실행

```bash
git clone https://github.com/qquartsco-svg/Cherubim_Engine.git
cd Cherubim_Engine

# 의존성: 표준 라이브러리 + numpy
pip install numpy

# 전체 데모 실행 (5단계)
python examples/cherubim_demo.py
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

### 에덴 환경 시뮬레이션 (궁창 → 대홍수 → 이후)

```python
from cherubim import make_firmament, make_flood_engine

fl = make_firmament(phase='antediluvian')
print(f"T = {fl.T_surface_estimate():.1f} K  UV차폐 = {fl.uv_shield_factor:.2f}")

flood = make_flood_engine()
for _ in range(12):
    snap = flood.step(dt_yr=1.0)
    print(f"{snap.flood_phase:14s}  T={snap.T_surface_K:.1f}K  f_land={snap.f_land:.2f}")
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
    mutation_max = 0.10,   # 최대 mutation 배수
    hab_bands_min= 10,     # 최소 거주 가능 밴드 수
)
```

---

## 블록체인 서명 (PHAM)

| 파일 | 등급 | 점수 |
|------|:----:|:----:|
| `initial_conditions.py` | A_HIGH | 1.0000 |
| `search.py` | A_HIGH | 1.0000 |
| `biology.py` | A_HIGH | 1.0000 |
| `geography.py` | A_HIGH | 1.0000 |
| `firmament.py` | A_HIGH | 1.0000 |
| `flood.py` | A_HIGH | 1.0000 |

서명 파일: `blockchain/pham_chain_*.json`

---

## 아키텍처 원칙

1. **하드코딩 없음** — 모든 수치는 물리 파라미터에서 동역학으로 계산
2. **완전 독립** — 표준 라이브러리 + numpy만으로 동작, 외부 의존 없음
3. **행성 중립** — 지구 전용이 아닌 임의 행성 파라미터 투입 가능
4. **에덴 = state basin** — 특정 좌표가 아닌 파라미터 공간의 안정 평형 영역

---

## 관련 프로젝트

| 레포 | 역할 |
|------|------|
| [cookiie_brain](https://github.com/qquartsco-svg/cookiie_brain) | 전체 창세기 물리 시스템 (Day1~7 + Eden) |
| **Cherubim_Engine** | Eden Basin Finder 독립 추출 버전 |

---

*v1.0.0 · PHAM Signed · GNJz (Qquarts)*
*"Cherubim — 에덴의 입구를 스캔하는 엔진"*
