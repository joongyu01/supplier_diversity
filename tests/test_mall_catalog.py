"""build_catalog.py 단위 테스트. 네트워크·엑셀·원시 CSV에 의존하지 않는다."""
import datetime as dt
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from build_catalog import (normalize_bizno, normalize_date, extract_region, to_iso,
                           build_products, build_facilities, contact_of, CHECK_DATE)


def company(bizno, name, types, region='', items=None, large=False, ceo='', tel='', address=''):
    return {'bizno': bizno, 'name': name, 'region': region, 'ceo': ceo, 'tel': tel, 'address': address,
            'excludedAsLargeCorp': large, 'items': items or [],
            'types': [{'type': t, 'validFrom': None, 'validUntil': u, 'status': 'expired' if u and u < CHECK_DATE else 'valid'}
                      for t, u in types]}


REGISTRY = {
    '1234567890': company('1234567890', '가나 사회적기업', [('사회적기업', None)]),
    '0000000123': company('0000000123', '다라 생산시설', [('중증장애인생산품 생산시설', '2027-01-01'), ('여성기업', '2020-01-01')],
                          region='경기도', items=['현수막', '판촉물인쇄'], ceo='홍길동', tel='031-000-0000', address='경기도 수원시 어디로 1'),
    '9999999999': company('9999999999', '큰회사', [('여성기업', None)], large=True),
}


def raw(bizno, name='책상', spec='책상, 제조사, 모델', end='20280110', **extra):
    row = {'prdctClsfcNoNm': name, 'dtilPrdctClsfcNo': '1', 'prdctIdntNo': '2', 'prdctSpecNm': spec, 'prdctMakrNm': '제조사',
           'prdctUnit': '개', 'cntrctPrceAmt': '1000', 'prdctLrgclsfcNm': '가구', 'cntrctCorpNm': '계약업체', 'cntrctCorpBizno': bizno,
           'entrprsDivNm': '소기업', 'masYn': 'Y', 'exclncPrcrmntPrdctYn': 'N', 'smetprCmptProdctYn': 'Y',
           'cntrctBgnDate': '20260101', 'cntrctEndDate': end, 'shopngCntrctNo': 'C1', 'shopngCntrctSno': '1'}
    row.update(extra)
    return row


class NormalizeTests(unittest.TestCase):
    def test_bizno(self):
        self.assertEqual(normalize_bizno(1010144633), '1010144633')
        self.assertEqual(normalize_bizno('101-01-44633'), '1010144633')
        self.assertEqual(normalize_bizno(123), '0000000123')
        self.assertEqual(normalize_bizno(None), '')
        self.assertEqual(normalize_bizno('CN0100000144459'), '')

    def test_date_three_forms(self):
        self.assertEqual(normalize_date(20241023), '2024-10-23')
        self.assertEqual(normalize_date('2025-06-30 00:00:00'), '2025-06-30')
        self.assertEqual(normalize_date(dt.datetime(2026, 11, 20, 15, 30)), '2026-11-20')
        self.assertIsNone(normalize_date(None))
        self.assertIsNone(normalize_date(''))

    def test_iso_from_api(self):
        self.assertEqual(to_iso('20280110'), '2028-01-10')
        self.assertEqual(to_iso(''), '')
        self.assertEqual(to_iso('bad'), '')

    def test_region_only_province(self):
        self.assertEqual(extract_region('서울특별시 강남구 테헤란로 440 (대치동)'), '서울특별시')
        self.assertEqual(extract_region(''), '')


class JoinTests(unittest.TestCase):
    def test_join_by_bizno_only_and_drop_non_preferred(self):
        rows = [('책상', raw('1234567890')), ('책상', raw('5555555555', cntrctCorpNm='가나 사회적기업')), ('책상', raw('123'))]
        products, totals = build_products(rows, REGISTRY)
        self.assertEqual([p['b'] for p in products], ['1234567890', '0000000123'])
        self.assertEqual(totals['책상'], {'all': 3, 'preferred': 2})

    def test_name_match_is_never_used(self):
        # 업체명이 등록기업과 같아도 사업자번호가 다르면 제외
        products, _ = build_products([('책상', raw('5555555555', cntrctCorpNm='가나 사회적기업'))], REGISTRY)
        self.assertEqual(products, [])

    def test_large_corp_kept_but_flagged_in_registry(self):
        products, _ = build_products([('책상', raw('9999999999'))], REGISTRY)
        self.assertEqual(len(products), 1)
        self.assertTrue(REGISTRY['9999999999']['excludedAsLargeCorp'])

    def test_product_row_is_slim_and_has_no_contract_officer(self):
        # 업체 연락처는 suppliers 맵에 한 번만 싣고, 계약담당자 개인 이름·이메일은 어디에도 싣지 않는다
        products, _ = build_products([('책상', raw('0000000123', cntrctOfclNm='담당자', cntrctOfclEmail='a@b.c'))], REGISTRY)
        self.assertEqual(set(products[0]), {'n', 'd', 'id', 's', 'm', 'u', 'p', 'l', 'b', 'cn', 'x', 'k', 'e', 'q'})

    def test_contract_end_and_flags(self):
        products, _ = build_products([('책상', raw('1234567890', end='20200101', exclncPrcrmntPrdctYn='Y'))], REGISTRY)
        self.assertEqual(products[0]['e'], '2020-01-01')
        self.assertLess(products[0]['e'], CHECK_DATE)
        self.assertTrue(products[0]['x'])


class FacilityTests(unittest.TestCase):
    def test_only_facilities_with_items(self):
        out = build_facilities(REGISTRY)
        self.assertEqual([f['bizno'] for f in out], ['0000000123'])
        f = out[0]
        self.assertEqual(f['items'], ['현수막', '판촉물인쇄'])
        self.assertEqual(f['region'], '경기도')
        self.assertEqual(f['validUntil'], '2027-01-01')
        self.assertEqual(f['otherTypes'], ['여성기업'])
        # 엑셀 연락처가 실린다
        self.assertEqual((f['ceo'], f['tel'], f['address'], f['contactSource']), ('홍길동', '031-000-0000', '경기도 수원시 어디로 1', 'excel'))

    def test_api_contact_overrides_excel(self):
        api = {'ceo': '김대표', 'tel': '02-111-1111', 'fax': '', 'address': '서울 강서구 마곡중앙로 143', 'zip': '07797',
               'homepage': 'http://x', 'employees': '29', 'manufacturer': '제조', 'opened': '2003-08-10'}
        c = contact_of(REGISTRY['0000000123'], api)
        self.assertEqual((c['ceo'], c['tel'], c['address'], c['contactSource']), ('김대표', '02-111-1111', '서울 강서구 마곡중앙로 143', 'api'))
        c = contact_of(REGISTRY['1234567890'], None)
        self.assertEqual((c['ceo'], c['tel'], c['contactSource']), ('', '', ''))


class PublishedCatalogTests(unittest.TestCase):
    def test_catalog_json_shape(self):
        data = json.loads((ROOT / 'site/data/catalog.json').read_text(encoding='utf-8'))
        self.assertEqual(data['schemaVersion'], 2)
        self.assertIsInstance(data['chunks'], list)
        self.assertIsInstance(data['suppliers'], dict)
        self.assertIsInstance(data['facilities'], list)
        for c in data['chunks']:
            self.assertTrue((ROOT / 'site/data' / c['file']).exists(), c['file'])
        for b, s in data['suppliers'].items():
            self.assertRegex(b, r'^\d{10}$')
            self.assertTrue({'name', 'region', 'types', 'excludedAsLargeCorp', 'ceo', 'tel', 'address', 'contactSource'} <= set(s))
        for f in data['facilities']:
            self.assertTrue({'bizno', 'name', 'region', 'items', 'validUntil', 'status', 'otherTypes', 'ceo', 'tel', 'address'} <= set(f))


if __name__ == '__main__':
    unittest.main()
