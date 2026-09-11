# Raw Material Price Tracker

원부자재 협상 리포트에 쓰는 참고 지표 시계열을 매일 자동으로 쌓는다.

- **Trading Economics** → 폴리에틸렌(PE)·폴리프로필렌(PP) 선물 스팟
  (다롄상품거래소, CNY/T) → `data/pe_futures_spot.csv`, `data/pp_futures_spot.csv`
- **SunSirs** → 황산(Sulfuric Acid)·유황(Sulfur) 현물가 (중국 대량 상품 시세)
  → `data/sulfuric_acid_spot.csv`, `data/sulfur_spot.csv`

## 매일 실행 (클라우드 크론)

Claude Code 클라우드 라우틴이 매일 09:00 KST(00:00 UTC)에 이 저장소를 열어
`scripts/fetch_spot.py`(PE/PP)와 `scripts/fetch_sunsirs.py`(황산/유황)를 실행하고,
새 행이 추가됐으면 커밋·푸시한다. 이미 있는 날짜는 건드리지 않는다(idempotent).

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
