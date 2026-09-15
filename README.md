# Raw Material Price Tracker

원부자재 협상 리포트에 쓰는 참고 지표 시계열을 매일 자동으로 쌓는다.

- **Trading Economics** → 폴리에틸렌(PE)·폴리프로필렌(PP) 선물 스팟
  (다롄상품거래소, CNY/T) → `data/pe_futures_spot.csv`, `data/pp_futures_spot.csv`
- **SunSirs** → 황산(Sulfuric Acid)·유황(Sulfur) 현물가 (중국 대량 상품 시세)
  → `data/sulfuric_acid_spot.csv`, `data/sulfur_spot.csv`
- **Opinet(한국석유공사)** → 국제 원유(Dubai/Brent/WTI)·나프타(Naphtha) **월별 평균가**
  ($/Bbl), 2024-01부터 → `data/opinet_monthly_avg.csv`

## 매일 실행 (클라우드 크론)

Claude Code 클라우드 라우틴이 매일 18:00 KST(09:00 UTC)에 이 저장소를 열어
`scripts/fetch_spot.py`(PE/PP), `scripts/fetch_sunsirs.py`(황산/유황),
`scripts/fetch_opinet.py`(원유/나프타 월평균)를 실행하고, 변경된 데이터가 있으면
커밋·푸시한다. PE/PP·SunSirs는 이미 있는 날짜는 건드리지 않는(idempotent) 방식이고,
Opinet은 매번 2024-01부터 전체를 다시 계산해 덮어쓴다(진행 중인 이번 달 평균이
매일 갱신되므로).

## 로컬에서 수동 실행

```
pip install requests

# Trading Economics (PE/PP)
python scripts/fetch_spot.py                # PE + PP 둘 다
python scripts/fetch_spot.py polyethylene    # PE만
python scripts/fetch_spot.py polypropylene   # PP만

# SunSirs (황산/유황)
python scripts/fetch_sunsirs.py              # 황산 + 유황 둘 다
python scripts/fetch_sunsirs.py sulfuric_acid
python scripts/fetch_sunsirs.py sulfur

# Opinet (원유/나프타 월평균, 2024-01 ~ 오늘)
python scripts/fetch_opinet.py
```

## 데이터 스키마

### `data/pe_futures_spot.csv`, `data/pp_futures_spot.csv` (Trading Economics)

| 컬럼 | 설명 |
|---|---|
| date | 가격 기준일 (YYYY-MM-DD) |
| value | 가격 |
| unit | 단위 (CNY/T) |
| change_1d_pct | 전일 대비 %. 보합("traded flat")일 땐 0 |
| change_1m_pct | 1개월 전 대비 % |
| change_1y_pct | 1년 전 대비 % (YoY) |
| collected_at_utc | 실제 수집 시각(UTC) |
| source_date_label | TE 페이지 원문 날짜 표기 |

### `data/sulfuric_acid_spot.csv`, `data/sulfur_spot.csv` (SunSirs)

| 컬럼 | 설명 |
|---|---|
| date | 가격 기준일 (YYYY-MM-DD) |
| value | 가격 |
| unit | **CNY/T(추정)** — SunSirs 페이지에 단위가 명시되어 있지 않아 중국 대량 상품 시세 관례(위안/톤)로 추정한 값. 확정된 사실 아님, 재확인 필요 |
| category | SunSirs가 분류한 업종(예: 화학공업) |
| collected_at_utc | 실제 수집 시각(UTC) |

SunSirs 가격 페이지는 항상 최근 6일치를 보여준다. 그래서 `fetch_sunsirs.py`는
"오늘 날짜"만 확인하는 게 아니라 표에 있는 날짜 중 CSV에 없는 것만 채워 넣는다 —
실행이 하루 이틀 빠져도 6일 안이면 자동으로 백필된다.

**SunSirs 접근 방식**: 페이지가 JS 챌린지("HW_CHECK" 쿠키)로 봇을 막는데, 첫 응답
본문에 쿠키 값이 그대로 박혀 있어(`var _0x2 = "<hex>"`) 그 값을 파싱해 두 번째
요청에 실으면 통과된다. 자세한 내용은 `scripts/fetch_sunsirs.py` 상단 주석 참고.

### `data/opinet_monthly_avg.csv` (Opinet)

| 컬럼 | 설명 |
|---|---|
| month | YYYY-MM |
| Dubai / Brent / WTI / Naphtha | 해당 월 일별 현물가($/Bbl)의 평균, 소수 둘째 자리 반올림 |

**Opinet 접근 방식**: 공식 유가정보 API는 국내 주유소 가격 위주라 국제유가/나프타를
안 주므로, 화면의 CSV 다운로드 기능(`POST /glopcoil_csv.do` 원유,
`POST /glopopd_csv.do` 석유제품)을 그대로 호출한다. 응답은 EUC-KR 인코딩,
날짜는 "YY년MM월DD일" 형식. 자세한 내용은 `scripts/fetch_opinet.py` 상단 주석 참고.
