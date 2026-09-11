#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Trading Economics에서 폴리에틸렌(PE)·폴리프로필렌(PP) 선물 스팟 가격을 매일
1회씩 크롤링해 data/<slug>_futures_spot.csv 에 append한다.

같은 날짜의 행이 이미 있으면 아무것도 하지 않는다(idempotent) — 크론이
같은 날 여러 번 돌아도 중복이 쌓이지 않는다.

원본 로직은 로컬 프로젝트의 etl/trading_economics.py 와 동일:
- tradingeconomics.com/commodity/<slug> 무료 페이지를 파싱
- 다롄상품거래소(DCE) 선물, CNY/T
- 가격 변동에 따라 문구가 "rose to"/"fell to"/"traded flat at" 세 가지로 갈리므로
  전부 시도한다. 보합("traded flat at")일 때는 전일 대비 문구 자체가 없어
  change_1d_pct를 0으로 둔다.
"""
import csv
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
DATA_DIR = Path(__file__).parent.parent / "data"
FIELDS = ["date", "value", "unit", "change_1d_pct", "change_1m_pct",
          "change_1y_pct", "collected_at_utc", "source_date_label"]

COMMODITIES = {
    "polyethylene": "pe_futures_spot.csv",
    "polypropylene": "pp_futures_spot.csv",
}


def fetch_spot(slug: str) -> dict:
    url = f"https://tradingeconomics.com/commodity/{slug}"
    r = requests.get(url, headers={"User-Agent": UA}, timeout=20)
    r.raise_for_status()
    html = r.text

    if "<title>\n\tTRADING ECONOMICS" in html and slug not in html.lower()[:2000]:
        raise RuntimeError(f"[{slug}] 상품 페이지가 존재하지 않음 (홈으로 폴백됨)")

    m = re.search(
        r"(?:rose|fell) to ([\d,\.]+) ([A-Z/]+) on ([A-Za-z]+ \d+, \d{4}), "
        r"(up|down) ([\d\.]+)% from the previous day\. "
        r"Over the past month, [^.]+ has (risen|fallen) ([\d\.]+)%, "
        r"and is (up|down) ([\d\.]+)% compared to the same time last year",
        html,
    )
    if m:
        value, unit, date_str, d_dir, d_pct, m_dir, m_pct, y_dir, y_pct = m.groups()
    else:
        m = re.search(
            r"traded flat at ([\d,\.]+) ([A-Z/]+) on ([A-Za-z]+ \d+, \d{4})\. "
            r"Over the past month, [^.]+ has (risen|fallen) ([\d\.]+)%, "
            r"and is (up|down) ([\d\.]+)% compared to the same time last year",
            html,
        )
        if not m:
            raise RuntimeError(f"[{slug}] 가격 문구 파싱 실패 — TE가 페이지 문구를 바꿨을 가능성")
        value, unit, date_str, m_dir, m_pct, y_dir, y_pct = m.groups()
        d_dir, d_pct = "up", "0"

    sign = lambda direction, pct: float(pct) * (1 if direction in ("up", "risen") else -1)
    parsed_date = datetime.strptime(date_str, "%B %d, %Y").strftime("%Y-%m-%d")

    return {
        "date": parsed_date,
        "value": float(value.replace(",", "")),
        "unit": unit,
        "change_1d_pct": sign(d_dir, d_pct),
        "change_1m_pct": sign(m_dir, m_pct),
        "change_1y_pct": sign(y_dir, y_pct),
        "collected_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_date_label": date_str,
    }


def append_if_new(csv_path: Path, row: dict) -> bool:
    """CSV에 같은 date 행이 없으면 추가. 추가했으면 True, 이미 있으면 False."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    exists = csv_path.exists()

    if exists:
        with open(csv_path, "r", encoding="utf-8", newline="") as f:
            for existing in csv.DictReader(f):
                if existing.get("date") == row["date"]:
                    return False

    with open(csv_path, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if not exists:
            w.writeheader()
        w.writerow(row)
    return True


if __name__ == "__main__":
    slugs = sys.argv[1:] or list(COMMODITIES.keys())
    any_error = False

    for slug in slugs:
        csv_name = COMMODITIES.get(slug, f"{slug}_futures_spot.csv")
        csv_path = DATA_DIR / csv_name
        try:
            row = fetch_spot(slug)
            added = append_if_new(csv_path, row)
            status = "추가됨" if added else "이미 존재 (스킵)"
            print(f"[{slug}] [{status}] {row['date']}  {row['value']:,.2f} {row['unit']}  "
                  f"1d {row['change_1d_pct']:+.2f}%  1m {row['change_1m_pct']:+.2f}%  "
                  f"1y {row['change_1y_pct']:+.2f}%")
        except Exception as e:
            any_error = True
            print(f"[{slug}] [오류] {e}")

    sys.exit(1 if any_error else 0)
