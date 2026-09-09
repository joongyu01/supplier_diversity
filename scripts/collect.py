"""Collect an explicit supplier cohort; publish only an entirely successful snapshot."""
import datetime as dt
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://apis.data.go.kr/1230000/ao/UsrInfoService02/'
SOURCE = 'https://www.data.go.kr/data/15129466/openapi.do'
CATEGORIES = {'사회적기업', '장애인기업', '여성기업', '중소기업', '중증장애인생산품 생산시설'}


def validate_suppliers(suppliers):
    if not isinstance(suppliers, list) or not suppliers:
        raise ValueError('config/suppliers.json에 조사 대상 업체를 먼저 등록하세요.')
    seen = set()
    for s in suppliers:
        bizno = s.get('bizno', '')
        if not isinstance(bizno, str) or not re.fullmatch(r'\d{10}', bizno) or bizno in seen:
            raise ValueError('사업자등록번호는 중복 없는 10자리 문자열이어야 합니다.')
        seen.add(bizno)
        if not s.get('name') or not s.get('evidence'):
            raise ValueError('업체명과 기업 유형 근거가 필요합니다.')
        for evidence in s['evidence']:
            if evidence.get('category') not in CATEGORIES:
                raise ValueError('지원하지 않는 기업 유형입니다.')
            url = urllib.parse.urlparse(evidence.get('url', ''))
            if url.scheme not in ('https', 'http') or not url.netloc:
                raise ValueError('기업 유형 근거의 출처 URL이 필요합니다.')
            checked = dt.date.fromisoformat(evidence.get('checkedAt', ''))
            if checked > dt.date.today():
                raise ValueError('근거 확인일이 미래입니다.')
            if evidence.get('validUntil'):
                expiry = dt.date.fromisoformat(evidence['validUntil'])
                if expiry < dt.date.today():
                    raise ValueError('만료된 기업 유형 근거가 있습니다. 갱신 후 수집하세요.')
    return suppliers


def parse_response(payload):
    response = payload.get('response', payload)
    header = response.get('header', {})
    if str(header.get('resultCode')) not in ('00', '0'):
        # Do not echo upstream payloads, URLs, or keys into public Actions logs.
        raise ValueError('API가 정상 응답을 반환하지 않았습니다. 인증키·활용승인·호출한도를 확인하세요.')
    body = response.get('body')
    if not isinstance(body, dict):
        raise ValueError('API body 형식이 변경되었습니다.')
    total = int(body['totalCount'])
    items = body.get('items') or []
    if isinstance(items, dict):
        items = items.get('item') or []
    if isinstance(items, dict):
        items = [items]
    if not isinstance(items, list) or any(not isinstance(i, dict) for i in items):
        raise ValueError('API items 형식이 변경되었습니다.')
    return items, total


def request_page(operation, bizno, page, key):
    params = {'serviceKey': urllib.parse.unquote(key), 'type': 'json',
              'inqryDiv': '3', 'bizno': bizno, 'pageNo': str(page), 'numOfRows': '100'}
    url = BASE + operation + '?' + urllib.parse.urlencode(params)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=45) as res:
                raw = res.read().decode('utf-8-sig')
            try:
                return parse_response(json.loads(raw))
            except json.JSONDecodeError:
                raise ValueError('API가 JSON 대신 XML/오류 문서를 반환했습니다. 인증 및 서비스 상태를 확인하세요.') from None
        except urllib.error.HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise RuntimeError(f'API HTTP 오류 {error.code}. 기존 데이터는 유지됩니다.') from None
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise RuntimeError('API 연결에 실패했습니다. 기존 데이터는 유지됩니다.') from None
        time.sleep(2 ** (attempt + 1))


def fetch_all(operation, bizno, key, request=request_page):
    result = []
    expected = None
    for page in range(1, 101):
        items, total = request(operation, bizno, page, key)
        if total < 0 or (expected is not None and total != expected):
            raise ValueError('수집 중 전체 건수가 변경되었습니다. 다시 실행하세요.')
        expected = total
        if any(str(i.get('bizno', '')) != bizno for i in items):
            raise ValueError('응답 업체 식별자가 요청과 일치하지 않습니다.')
        result.extend(items)
        if len(result) == total:
            return result
        if not items or len(result) > total:
            raise ValueError('API 페이지 건수 불일치. 불완전한 결과를 게시하지 않습니다.')
        time.sleep(0.2)
    raise ValueError('업체당 100페이지 수집 한도를 초과했습니다.')


def build_catalog(suppliers, key, fetch=fetch_all):
    output_suppliers, products = [], []
    seen = set()
    for s in validate_suppliers(suppliers):
        basic = fetch('getPrcrmntCorpBasicInfo02', s['bizno'], key)
        if len(basic) != 1:
            raise ValueError('업체 기본정보가 없거나 여러 건입니다. 사업자등록번호를 확인하세요.')
        info = basic[0]
        evidence = [{k: e.get(k, '') for k in ('category', 'url', 'checkedAt', 'validUntil')} for e in s['evidence']]
        company = {'bizno': s['bizno'], 'companyName': info.get('corpNm') or s['name'],
                   'region': info.get('rgnNm', ''), 'categories': sorted({e['category'] for e in evidence}),
                   'evidence': evidence}
        output_suppliers.append(company)
        for p in fetch('getPrcrmntCorpSplyPrdctInfo02', s['bizno'], key):
            name, code = p.get('dtilPrdctClsfcNoNm'), p.get('dtilPrdctClsfcNo')
            if not name or not code:
                raise ValueError('세부품명 필드가 없습니다. 참고문서와 실제 응답 스키마를 확인하세요.')
            ident = (s['bizno'], str(code))
            if ident in seen:
                continue
            seen.add(ident)
            products.append({**company, 'productName': name, 'productCode': str(code),
                             'manufacturer': p.get('mnfctYn', ''), 'changedAt': p.get('chgDt', '')})
        print(f'업체 {len(output_suppliers)}/{len(suppliers)} 수집 완료')
    return {'schemaVersion': 1, 'updatedAt': dt.datetime.now(dt.timezone.utc).isoformat(),
            'source': SOURCE, 'suppliers': output_suppliers, 'products': products}


def main():
    key = os.environ.get('DATA_GO_KR_SERVICE_KEY', '').strip()
    if not key:
        raise ValueError('DATA_GO_KR_SERVICE_KEY 환경변수 또는 GitHub Actions Secret이 필요합니다.')
    suppliers = json.loads((ROOT / 'config/suppliers.json').read_text(encoding='utf-8-sig'))
    catalog = build_catalog(suppliers, key)
    destination = ROOT / 'site/data/catalog.json'
    temporary = destination.with_suffix('.tmp')
    temporary.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(destination)
    print(f'공급물품 {len(catalog["products"])}건 저장 완료')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, OSError) as error:
        print(f'수집 중단: {error}', file=sys.stderr)
        sys.exit(1)
