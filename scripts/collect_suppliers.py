"""카탈로그에 등장하는 우대기업의 사업자등록 공개정보(대표자·주소·전화 등)를 수집한다.

- 나라장터 사용자정보 서비스 getPrcrmntCorpBasicInfo02 (15129466), 사업자등록번호 1건당 1회
- 대상: data/raw/shopmall/*.csv 에 나오는 업체 중 엑셀 우대기업과 일치하는 곳 + 중증 생산시설
- 결과: data/raw/suppliers.csv (이미 있는 사업자번호는 건너뜀)
- 인증키는 DATA_GO_KR_SERVICE_KEY 환경변수로만 읽고 로그에 남기지 않는다.
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
sys.path.insert(0, str(ROOT / 'scripts'))
from build_catalog import load_excel_registry, load_raw, normalize_bizno, CONTACT_PATH  # noqa: E402

URL = 'https://apis.data.go.kr/1230000/ao/UsrInfoService02/getPrcrmntCorpBasicInfo02'
FIELDS = ['bizno', 'name', 'ceo', 'tel', 'fax', 'address', 'zip', 'region', 'homepage', 'employees',
          'manufacturer', 'opened', 'fetchedAt']


def fetch(key, bizno):
    params = {'serviceKey': key, 'type': 'json', 'inqryDiv': '3', 'bizno': bizno, 'pageNo': '1', 'numOfRows': '5'}
    for attempt in range(3):
        try:
            with urllib.request.urlopen(URL + '?' + urllib.parse.urlencode(params), timeout=60) as res:
                body = json.loads(res.read().decode('utf-8-sig')).get('response', {}).get('body', {}) or {}
            items = body.get('items') or []
            if isinstance(items, dict):
                items = items.get('item') or []
            items = items if isinstance(items, list) else [items]
            return next((i for i in items if str(i.get('bizno', '')).zfill(10) == bizno), None)
        except Exception:
            if attempt == 2:
                return None
            time.sleep(3)


def row_from(bizno, it):
    addr = ' '.join(x for x in (it.get('adrs', ''), it.get('dtlAdrs', '')) if x).strip()
    return {'bizno': bizno, 'name': it.get('corpNm', ''), 'ceo': it.get('ceoNm', ''), 'tel': it.get('telNo', ''),
            'fax': it.get('faxNo', ''), 'address': addr, 'zip': it.get('zip', ''), 'region': it.get('rgnNm', ''),
            'homepage': it.get('hmpgAdrs', ''), 'employees': it.get('emplyeNum', ''),
            'manufacturer': it.get('mnfctDivNm', ''), 'opened': str(it.get('opbizDt', ''))[:10],
            'fetchedAt': time.strftime('%Y-%m-%d')}


def targets():
    registry = load_excel_registry()
    biznos = {normalize_bizno(r.get('cntrctCorpBizno')) for _, r in load_raw()}
    catalog = sorted(b for b in biznos if b in registry)
    # 중증 생산시설은 엑셀에 전화·주소가 이미 있으므로 뒤에 둔다(한도 초과 시 다음 날 이어서)
    facilities = sorted(b for b, c in registry.items() if c['items'] and b not in set(catalog))
    return catalog + facilities


def main():
    key = os.environ.get('DATA_GO_KR_SERVICE_KEY', '').strip()
    if not key:
        raise SystemExit('DATA_GO_KR_SERVICE_KEY 환경변수가 필요합니다.')
    done = {}
    if CONTACT_PATH.exists():
        with open(CONTACT_PATH, encoding='utf-8-sig', newline='') as f:
            done = {r['bizno']: r for r in csv.DictReader(f)}
    todo = [b for b in targets() if b not in done]
    print(f'대상 {len(todo):,}곳 (기존 {len(done):,}곳)', flush=True)
    missing = 0
    with open(CONTACT_PATH, 'a', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if not done:
            w.writeheader()
        for i, b in enumerate(todo, 1):
            it = fetch(key, b)
            if it:
                w.writerow(row_from(b, it))
            else:
                missing += 1
            f.flush()
            if i % 50 == 0:
                print(f'  {i}/{len(todo)} (미조회 {missing})', flush=True)
            time.sleep(0.15)
    print(f'완료: 수집 {len(todo) - missing:,}곳, API에 없음 {missing:,}곳 → {CONTACT_PATH}')


if __name__ == '__main__':
    main()
