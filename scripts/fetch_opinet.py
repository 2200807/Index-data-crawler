#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""오피넷(한국석유공사, opinet.co.kr)에서 국제 원유(Dubai/Brent/WTI)와
나프타(Naphtha) 일별 현물가($/Bbl)를 2024-01-01부터 오늘까지 통째로 받아
월별 평균가로 집계해 data/opinet_monthly_avg.csv 를 매번 새로 만든다.

왜 "새로 만든다"인가: 이번 달은 아직 진행 중이라 매일 평균이 바뀐다. 어제까지의
행만 append하는 idempotent 방식 대신, 매번 2024-01부터 전체를 다시 계산해
덮어쓰면 "이번 달 평균 갱신" 로직을 따로 만들 필요가 없다. API 호출은 2번
(원유/나프타 각 1번, 각각 700행 안팎)뿐이라 비용이 크지 않다. 실제로 값이
바뀐 경우에만 git diff에 잡히므로 커밋 판단(호출부 라우틴)은 그대로 git
status로 하면 된다.

엔드포인트는 오피넷 공식 API가 아니라 화면의 CSV 다운로드 기능
(POST /glopcoil_csv.do, /glopopd_csv.do)을 그대로 쓴다 — 공식 유가정보 API는
국내 주유소 가격 위주라 국제유가/나프타 항목이 없어서, 화면 자체가 쓰는
엔드포인트를 그대로 재사용했다. 응답은 EUC-KR 인코딩, 날짜는 "YY년MM월DD일"
형식이다.
"""
import csv
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
DATA_DIR = Path(__file__).parent.parent / "data"
OUT_CSV = DATA_DIR / "opinet_monthly_avg.csv"
START_DATE = (2024, 1, 1)
COLUMNS = ["Dubai", "Brent", "WTI", "Naphtha"]

DATE_RE = re.compile(r"(\d{2})년(\d{2})월(\d{2})일")


def _post_csv(url: str, referer: str, extra_fields: dict, sta: tuple, end: tuple) -> str:
    sta_y, sta_m, sta_d = sta
    end_y, end_m, end_d = end
    data = {
        "TERM": "D",
        "STA_Y": str(sta_y), "STA_M": f"{sta_m:02d}", "STA_D": f"{sta_d:02d}",
        "END_Y": str(end_y), "END_M": f"{end_m:02d}", "END_D": f"{end_d:02d}",
        "STDDATE": f"{sta_y}{sta_m:02d}{sta_d:02d}",
        "ENDDATE": f"{end_y}{end_m:02d}{end_d:02d}",
        "SEL_DIV": "div_dar",
        **extra_fields,
    }
    r = requests.post(
        url, data=data, timeout=30,
        headers={"User-Agent": UA, "Referer": referer,
                 "Content-Type": "application/x-www-form-urlencoded"},
    )
    r.raise_for_status()
    return r.content.decode("euc-kr", errors="replace")


def _parse_date(cell: str) -> str:
    """'26년09월14일' -> '2026-09-14'"""
    m = DATE_RE.search(cell)
    if not m:
        raise ValueError(f"날짜 파싱 실패: {cell!r}")
    yy, mm, dd = m.groups()
    return f"20{yy}-{mm}-{dd}"


def fetch_crude(sta: tuple, end: tuple) -> dict:
    """{date: {"Dubai":.., "Brent":.., "WTI":..}}"""
    text = _post_csv(
        "https://www.opinet.co.kr/glopcoil_csv.do",
        "https://www.opinet.co.kr/gloptotSelect.do",
        {"OILSRTCD1": "001", "OILSRTCD2": "002", "OILSRTCD3": "003",
         "OILSRTCD": ["001", "002", "003"]},
        sta, end,
    )
    rows = list(csv.reader(text.splitlines()))
    header = rows[0]  # 기간,Dubai,Brent,WTI
    out = {}
    for row in rows[1:]:
        if not row or not row[0].strip():
            continue
        date = _parse_date(row[0])
        vals = {}
        for name, cell in zip(header[1:], row[1:]):
            cell = cell.strip()
            if cell:
                vals[name] = float(cell)
        out[date] = vals
    return out


def fetch_naphtha(sta: tuple, end: tuple) -> dict:
    """{date: naphtha_price}"""
    text = _post_csv(
        "https://www.opinet.co.kr/glopopd_csv.do",
        "https://www.opinet.co.kr/glopopdSelect.do",
        {"OILSRTCD1": "B001", "OILSRTCD2": "B007", "OILSRTCD3": "C001",
         "OILSRTCD4": "D009", "OILSRTCD5": "D008", "OILSRTCD6": "E001",
         "OILSRTCD7": "F001", "OILSRTCD": "F001"},
        sta, end,
    )
    rows = list(csv.reader(text.splitlines()))
    header = rows[0]
    naphtha_idx = header.index("나프타")
    out = {}
    for row in rows[1:]:
        if not row or not row[0].strip():
            continue
        date = _parse_date(row[0])
        cell = row[naphtha_idx].strip() if len(row) > naphtha_idx else ""
        if cell:
            out[date] = float(cell)
    return out


def build_monthly_avg(crude: dict, naphtha: dict) -> list[dict]:
    monthly = defaultdict(lambda: defaultdict(list))
    for date, vals in crude.items():
        ym = date[:7]
        for name, v in vals.items():
            monthly[ym][name].append(v)
    for date, v in naphtha.items():
        monthly[date[:7]]["Naphtha"].append(v)

    result = []
    for ym in sorted(monthly):
        row = {"month": ym}
        for col in COLUMNS:
            values = monthly[ym].get(col)
            row[col] = round(sum(values) / len(values), 2) if values else ""
        result.append(row)
    return result


def write_csv(rows: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["month"] + COLUMNS)
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    today = datetime.now(timezone.utc)
    end = (today.year, today.month, today.day)

    try:
        crude = fetch_crude(START_DATE, end)
        naphtha = fetch_naphtha(START_DATE, end)
    except Exception as e:
        print(f"[오류] {e}")
        sys.exit(1)

    rows = build_monthly_avg(crude, naphtha)
    write_csv(rows)

    latest = rows[-1] if rows else {}
    print(f"[완료] {len(rows)}개월 집계 (2024-01 ~ {latest.get('month', '?')}). "
          f"최신월 평균: Dubai {latest.get('Dubai')} / Brent {latest.get('Brent')} / "
          f"WTI {latest.get('WTI')} / Naphtha {latest.get('Naphtha')}")
    sys.exit(0)
