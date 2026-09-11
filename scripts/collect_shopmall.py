"""나라장터 종합쇼핑몰 품목을 품명 기준으로 수집한다 (전량 미러링 아님).

- getShoppingMallPrdctInfoList 만 사용 (품명 필터가 작동하는 유일한 오퍼레이션)
- 품명별 × 등록일 윈도별 페이징, 999건/호출
- 결과는 data/raw/shopmall/<품명>.csv 에 저장 (git 미추적)
- 인증키는 DATA_GO_KR_SERVICE_KEY 환경변수로만 읽는다. 로그에 키·URL을 남기지 않는다.
"""
import csv
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data' / 'raw' / 'shopmall'
URL = 'https://apis.data.go.kr/1230000/at/ShoppingMallPrdctInfoService/getShoppingMallPrdctInfoList'
KEEP = ['prdctClsfcNo', 'prdctClsfcNoNm', 'dtilPrdctClsfcNo', 'dtilPrdctClsfcNoNm', 'prdctIdntNo',
        'prdctSpecNm', 'prdctMakrNm', 'prdctUnit', 'cntrctPrceAmt', 'cntrctCorpNm', 'cntrctCorpBizno',
        'entrprsDivNm', 'masYn', 'exclncPrcrmntPrdctYn', 'smetprCmptProdctYn', 'prodctCertList',
        'cntrctBgnDate', 'cntrctEndDate', 'rgstDt', 'shopngCntrctNo', 'shopngCntrctSno',
        'prdctLrgclsfcNm', 'prdctMidclsfcNm']
# 등록일 윈도. 1년 이상 넣으면 API가 응답하지 않으므로 4~5개월 단위로 쪼갠다.
WINDOWS = [('20260101', '20260430'), ('20260501', '20261231')]
MAX_PAGES = 60


def fetch(key, name, begin, end, page):
    params = {'serviceKey': key, 'type': 'json', 'pageNo': str(page), 'numOfRows': '999',
              'inqryDiv': '1', 'inqryBgnDate': begin, 'inqryEndDate': end, 'prdctClsfcNoNm': name}
    for attempt in range(3):
        try:
            with urllib.request.urlopen(URL + '?' + urllib.parse.urlencode(params), timeout=90) as res:
                body = json.loads(res.read().decode('utf-8-sig')).get('response', {}).get('body', {}) or {}
            items = body.get('items') or []
            if isinstance(items, dict):
                items = items.get('item') or []
            return int(body.get('totalCount') or 0), (items if isinstance(items, list) else [items])
        except Exception:
            if attempt == 2:
                return None, []
            time.sleep(3)


def collect(key, name):
    rows, calls = {}, 0
    for begin, end in WINDOWS:
        total, items = fetch(key, name, begin, end, 1)
        calls += 1
        if total is None:
            print(f'  {name} {begin}~{end}: 응답 실패', file=sys.stderr)
            continue
        page = 1
        while len(items) < total and page < MAX_PAGES:
            page += 1
            _, more = fetch(key, name, begin, end, page)
            calls += 1
            if not more:
                break
            items += more
            time.sleep(0.15)
        for it in items:
            rows[(it.get('shopngCntrctNo'), it.get('shopngCntrctSno'))] = {k: it.get(k, '') for k in KEEP}
    return list(rows.values()), calls


def main(names):
    key = os.environ.get('DATA_GO_KR_SERVICE_KEY', '').strip()
    if not key:
        raise SystemExit('DATA_GO_KR_SERVICE_KEY 환경변수가 필요합니다.')
    RAW.mkdir(parents=True, exist_ok=True)
    total_calls = 0
    for name in names:
        out = RAW / f'{name}.csv'
        if out.exists():
            print(f'{name}: 이미 수집됨, 건너뜀', flush=True)
            continue
        rows, calls = collect(key, name)
        total_calls += calls
        with open(out, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.DictWriter(f, fieldnames=KEEP)
            w.writeheader()
            w.writerows(rows)
        print(f'{name}: {len(rows):,}건 ({calls}회, 누계 {total_calls}회)', flush=True)


if __name__ == '__main__':
    main(sys.argv[1:] or [l.strip() for l in (ROOT / 'config' / 'product_names.txt').read_text(encoding='utf-8').splitlines() if l.strip() and not l.startswith('#')])
