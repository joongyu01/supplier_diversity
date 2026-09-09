import copy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from collect import parse_response, fetch_all, build_catalog, validate_suppliers

SEED = [{'bizno':'0000000000','name':'테스트 전용 가상 업체','evidence':[
    {'category':'여성기업','url':'https://example.org/evidence','checkedAt':'2026-01-01'}]}]


class CollectorTests(unittest.TestCase):
    def test_response_shapes(self):
        item = {'bizno':'0000000000'}
        for items in ([item], {'item':[item]}, {'item':item}):
            self.assertEqual(parse_response({'response':{'header':{'resultCode':'00'},'body':{'items':items,'totalCount':1}}}), ([item],1))

    def test_api_error_rejected_without_echo(self):
        with self.assertRaises(ValueError) as ctx:
            parse_response({'response':{'header':{'resultCode':'30','resultMsg':'secret-test'}}})
        self.assertNotIn('secret-test', str(ctx.exception))

    def test_pagination(self):
        pages=[]
        def request(op,bizno,page,key):
            pages.append(page)
            return [{'bizno':bizno,'n':page}],2
        self.assertEqual(len(fetch_all('op','0000000000','key',request)),2)
        self.assertEqual(pages,[1,2])

    def test_incomplete_and_wrong_company_rejected(self):
        for response in (([],1),([{'bizno':'9999999999'}],1)):
            with self.assertRaises(ValueError):
                fetch_all('op','0000000000','key',lambda *args:response)

    def test_join_and_minimal_public_fields(self):
        def fetch(op,bizno,key):
            if 'Basic' in op:
                return [{'bizno':bizno,'corpNm':'가상 업체','ceoNm':'PRIVATE','rgnNm':'서울'}]
            return [{'bizno':bizno,'dtilPrdctClsfcNoNm':'테스트 물품','dtilPrdctClsfcNo':'1234567890'}]*2
        data=build_catalog(SEED,'secret-test',fetch)
        self.assertEqual(len(data['products']),1)
        self.assertEqual(data['products'][0]['categories'],['여성기업'])
        self.assertNotIn('PRIVATE',json.dumps(data))
        self.assertNotIn('secret-test',json.dumps(data))

    def test_evidence_required_and_expiry_checked(self):
        for seed in ([], SEED*2, [{'bizno':'123'}]):
            with self.assertRaises(ValueError): validate_suppliers(seed)
        seed=copy.deepcopy(SEED)
        seed[0]['evidence'][0]['validUntil']='2000-01-01'
        with self.assertRaises(ValueError): validate_suppliers(seed)

    def test_product_schema_mismatch_fails(self):
        with self.assertRaises(ValueError):
            build_catalog(SEED,'key',lambda *args:[{'bizno':'0000000000','corpNm':'test','indstrytyNm':'wrong schema'}])

    def test_initial_catalog(self):
        root=Path(__file__).resolve().parents[1]
        data=json.loads((root/'site/data/catalog.json').read_text(encoding='utf-8'))
        self.assertEqual(data['schemaVersion'],1)
        self.assertIsInstance(data['products'],list)


if __name__ == '__main__': unittest.main()
