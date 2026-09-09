# PE Futures Tracker

Trading Economics(다롄상품거래소 폴리에틸렌 선물, CNY/T)에서 매일 스팟 가격을
크롤링해 `data/pe_futures_spot.csv`에 누적한다. 원본 PE격리판 협상 리포트의
참고 지표(HDPE 현물과는 다른 벤치마크)를 시계열로 쌓기 위한 용도.

## 매일 실행 (클라우드 크론)

Claude Code 클라우드 라우틴이 매일 09:00 KST(00:00 UTC)에 이 저장소를 열어
`scripts/fetch_spot.py`를 실행하고, 새 행이 추가됐으면 커밋·푸시한다.
같은 날짜 행이 이미 있으면 아무 것도 하지 않는다(idempotent).

## 로컬에서 수동 실행

```
pip install requests
python scripts/fetch_spot.py
```

## 데이터 스키마 (`data/pe_futures_spot.csv`)

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
