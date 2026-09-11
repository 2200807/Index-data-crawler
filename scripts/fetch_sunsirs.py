#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SunSirs(중국 상품 데이터 그룹)에서 황산(Sulfuric Acid)·유황(Sulfur) 현물 가격을
매일 1회 크롤링해 data/<slug>_spot.csv 에 append한다.

SunSirs는 JS 챌린지("HW_CHECK" 쿠키)로 봇을 막는다: 첫 응답 본문에 쿠키 값이
`var _0x2 = "<hex>"` 형태로 박혀 있고, 그 쿠키를 실어 같은 URL로 다시 요청하면
정상 페이지가 나온다(서버 Set-Cookie 헤더가 아니라 JS로 심는 방식이라 requests
세션의 자동 쿠키 처리로는 못 뚫는다 — 값을 직접 파싱해서 두 번째 요청에 실어야 함).
값 자체는 관찰상 고정돼 있었지만, 바뀔 수 있으니 매번 새로 추출한다.

가격 페이지는 최근 6일치 표를 항상 보여준다. 그래서 이 스크립트는 하루 한 번이
아니라 표에 있는 모든 날짜를 훑어 CSV에 없는 날짜만 채워 넣는다(idempotent).
즉 실행이 하루 이틀 빠지더라도 최근 6일 안이면 자동으로 백필된다.

단위(元/吨, CNY/톤 추정): SunSirs 페이지 어디에도 명시적 단위 텍스트가 없어서
관례상 중국 대량 상품 시세 표기(위안/톤)로 추정한 것 — 확인된 사실이 아니므로
헷갈리지 않도록 CSV의 unit 컬럼에 "CNY/T(추정)"라고 표시한다.
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
FIELDS = ["date", "value", "unit", "category", "collected_at_utc"]

PRODUCTS = {
    "sulfuric_acid": {"prodid": 236, "name_kr": "황산", "csv": "sulfuric_acid_spot.csv"},
    "sulfur": {"prodid": 427, "name_kr": "유황", "csv": "sulfur_spot.csv"},
}


def _bypass_challenge(session: requests.Session, url: str) -> str:
    """HW_CHECK JS 챌린지를 뚫고 실제 페이지 HTML을 반환."""
    r1 = session.get(url, headers={"User-Agent": UA}, timeout=20)
    r1.raise_for_status()
    m = re.search(r'var _0x2 = "([a-f0-9]+)"', r1.text)
    if not m:
        return r1.text  # 이미 챌린지 없이 정상 페이지가 온 경우

    session.cookies.set("HW_CHECK", m.group(1))
    r2 = session.get(url, headers={"User-Agent": UA}, timeout=20)
    r2.raise_for_status()
    return r2.text


def fetch_recent(slug: str) -> list[dict]:
    info = PRODUCTS[slug]
    url = f"https://www.sunsirs.com/kr/prodetail-{info['prodid']}.html"
    with requests.Session() as s:
        html = _bypass_challenge(s, url)

    rows = re.findall(
        r"<tr[^>]*><td>([^<]+)</td><td>([^<]+)</td><td>([\d.]+)</td><td>(\d{4}-\d{2}-\d{2})</td></tr>",
        html,
    )
    if not rows:
        raise RuntimeError(f"[{slug}] 가격 표 파싱 실패 — SunSirs가 페이지 구조를 바꿨을 가능성")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return [
        {
            "date": date,
            "value": float(price),
            "unit": "CNY/T(추정)",
            "category": category,
            "collected_at_utc": now,
        }
        for _name, category, price, date in rows
    ]


def append_new_rows(csv_path: Path, rows: list[dict]) -> list[str]:
    """CSV에 없는 날짜의 행만 추가. 추가된 날짜 목록을 반환."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    exists = csv_path.exists()

    existing_dates = set()
    if exists:
        with open(csv_path, "r", encoding="utf-8", newline="") as f:
            existing_dates = {r["date"] for r in csv.DictReader(f)}

    new_rows = sorted(
        (r for r in rows if r["date"] not in existing_dates),
        key=lambda r: r["date"],
    )
    if not new_rows:
        return []

    with open(csv_path, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if not exists:
            w.writeheader()
        w.writerows(new_rows)
    return [r["date"] for r in new_rows]


if __name__ == "__main__":
    slugs = sys.argv[1:] or list(PRODUCTS.keys())
    any_error = False

    for slug in slugs:
        if slug not in PRODUCTS:
            print(f"[{slug}] [오류] 알 수 없는 상품 (지원: {', '.join(PRODUCTS)})")
            any_error = True
            continue
        try:
            rows = fetch_recent(slug)
            csv_path = DATA_DIR / PRODUCTS[slug]["csv"]
            added_dates = append_new_rows(csv_path, rows)
            if added_dates:
                print(f"[{slug}] [추가됨] {', '.join(added_dates)}")
            else:
                print(f"[{slug}] [이미 존재 (스킵)] 최신 날짜 {rows[0]['date']}")
        except Exception as e:
            any_error = True
            print(f"[{slug}] [오류] {e}")

    sys.exit(1 if any_error else 0)
