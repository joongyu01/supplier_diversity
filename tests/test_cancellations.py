import copy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import watch_cancellations as w


def listing(rows, total=None):
    return ('<input name="searchText" value="사회적"><div class="board_info"><span class="total"><b>'
            + str(len(rows) if total is None else total) + '</b></span></div><div class="board_list"><table><tbody>'
            + ''.join(f'<tr><td><a href="noticeView.do?bbs_seq={i}" title="{title}">{title}</a></td>'
                      f'<td>{date}</td></tr>' for i, title, date in rows) + '</tbody></table></div>')


class CancellationTests(unittest.TestCase):
    def test_stages_are_not_equated(self):
        self.assertEqual(w.classify('사회적기업 인증 취소 공고'), 'cancellation_notice')
        self.assertEqual(w.classify('사회적기업 인증 반납신청 수리 공고'), 'surrender_notice')
        self.assertEqual(w.classify('사회적기업 인증취소 청문 공고'), 'prior_notice')
        self.assertEqual(w.classify('예비사회적기업 지정종료'), 'preliminary_enterprise')
        self.assertEqual(w.classify('예비(부처형)사회적기업 지정 반납 수리 공고'), 'preliminary_enterprise')
        self.assertIsNone(w.classify('사회적기업 사업보고서 안내'))

    def test_markup_failure_is_not_empty_success(self):
        with self.assertRaises(ValueError):
            w.parse_listing('<html>Maintenance</html>', 'https://www.moel.go.kr/')
        with self.assertRaises(ValueError):
            w.parse_listing(listing([], 10), 'https://www.moel.go.kr/')
        self.assertEqual(w.parse_listing(listing([]), 'https://www.moel.go.kr/'), ([], 0))

    def test_real_listing_title_whitespace(self):
        rows, _ = w.parse_listing(listing([('20260701080', '예비(부처형)사회적기업 지정 반납 수리 공고 ', '2026.07.31')]), 'https://www.moel.go.kr/')
        self.assertEqual(rows[0]['title'], '예비(부처형)사회적기업 지정 반납 수리 공고')

    def test_pagination_and_cutoff(self):
        class Client:
            def get(self, url):
                page = int(w.parse_qs(w.urlparse(url).query)['pageIndex'][0])
                return listing([(str(page), '사회적기업 인증 취소', '2026.07.01' if page == 2 else '2025.01.01')], 2)
        rows, pages = w.scan_board(Client(), {'code': 'seoul', 'name': '서울'}, 'notice', '2026-06-30')
        self.assertEqual(pages, 2)
        self.assertEqual([r['id'] for r in rows], ['2'])

    def test_repeated_page_fails(self):
        class Client:
            def get(self, url):
                return listing([('1', '사회적기업 인증 취소', '2026.07.01')], 2)
        with self.assertRaisesRegex(ValueError, 'repeated'):
            w.scan_board(Client(), {'code': 'seoul', 'name': '서울'}, 'notice', '2026-06-30')

    def test_detail_and_revision(self):
        record = {'id': '1', 'title': '사회적기업 인증 취소', 'publishedAt': '2026-07-01',
                  'url': 'https://www.moel.go.kr/local/seoul/news/notice/noticeView.do?bbs_seq=1'}
        html = ('<div class="board_view_wrap"><div class="b_info"><dl><dt>제목</dt><dd>사회적기업 인증 취소</dd></dl>'
                '<dl><dt>등록일</dt><dd>2026-07-01</dd></dl></div><div class="b_content">본문</div>'
                '<div class="file"><a href="/common/downloadFile.do?file_seq=1" title="공고.pdf 다운로드"></a></div></div>')
        detail = w.parse_detail(html, record)
        self.assertEqual(detail['attachments'][0]['name'], '공고.pdf')
        initial, added, _ = w.merge_records([], [detail], 'first')
        self.assertEqual(added, ['1'])
        same, added, changed = w.merge_records(initial, [detail], 'second')
        self.assertEqual(initial, same)
        self.assertEqual((added, changed), ([], []))
        revised = w.parse_detail(html.replace('본문', '정정된 본문'), record)
        updated, _, changed = w.merge_records(initial, [revised], 'third')
        self.assertEqual(changed, ['1'])
        self.assertEqual(updated[0]['firstSeenAt'], 'first')
        self.assertEqual(updated[0]['lastChangedAt'], 'third')
        self.assertEqual(w.merge_records(initial, [], 'fourth')[0], initial)

    def test_partial_failure_preserves_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'snapshot.json'
            path.write_text('{"notices": []}', encoding='utf-8')
            before = path.read_bytes()
            args = SimpleNamespace(offices='seoul', since=None, output=path, max_requests=10, delay=0)
            with patch.object(w, 'scan_board', side_effect=ValueError('layout changed')):
                with self.assertRaisesRegex(RuntimeError, 'Incomplete'):
                    w.run(args)
            self.assertEqual(path.read_bytes(), before)

    def test_external_links_rejected(self):
        with self.assertRaises(ValueError):
            w.official_url('https://example.com/fake')

    def test_parallel_request_budget_is_shared(self):
        client = w.Client(max_requests=2, delay=0)
        def attempt(_):
            try:
                client.get('https://www.moel.go.kr/')
            except RuntimeError:
                return
        with patch.object(w, 'urlopen', side_effect=OSError('network unavailable')), patch.object(w.time, 'sleep'):
            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(attempt, range(8)))
        self.assertEqual(client.count, 2)


if __name__ == '__main__':
    unittest.main()
