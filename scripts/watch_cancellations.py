"""Read official MOEL notices. Discovery is NOT an enterprise-status decision."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import time
import threading
from urllib.parse import parse_qs, urlencode, urljoin, urlparse
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'config/cancellation-sources.json'
OUTPUT = ROOT / 'site/data/cancellation-notices.json'
BOARDS = {'notice': 'notice/noticeList.do', 'publicnotice': 'publicnotice/list.do'}


def text(el):
    return normalize_text(el.get_text(' ', strip=True)) if el else ''


def normalize_text(value):
    return re.sub(r'\s+', ' ', value).strip()


def official_url(url):
    p = urlparse(url)
    if p.scheme != 'https' or p.hostname != 'www.moel.go.kr' or p.username or p.port:
        raise ValueError('Unexpected source URL')
    return url


class Client:
    def __init__(self, max_requests=800, delay=0.4):
        self.count, self.max_requests, self.delay = 0, max_requests, delay
        self.lock = threading.Lock()
        self.last_request = 0

    def get(self, url):
        official_url(url)
        for attempt in range(3):
            if attempt:
                time.sleep(2 ** attempt)
            # One shared rate limiter and budget, including retries, across all workers.
            with self.lock:
                if self.count >= self.max_requests:
                    raise RuntimeError('Request budget exhausted; snapshot will not be replaced')
                time.sleep(max(0, self.delay - (time.monotonic() - self.last_request)))
                self.count += 1
                self.last_request = time.monotonic()
            try:
                req = Request(url, headers={'User-Agent': 'SupplierDiversity-NoticeMonitor/1.0'})
                with urlopen(req, timeout=30) as response:
                    official_url(response.url)
                    raw = response.read(4_000_001)
                    if len(raw) > 4_000_000:
                        raise ValueError('HTML too large')
                    return raw.decode(response.headers.get_content_charset() or 'utf-8')
            except (OSError, TimeoutError):
                if attempt == 2:
                    raise RuntimeError('Official website request failed') from None


def classify(title):
    compact = re.sub(r'\s+', '', title)
    if '사회적기업' not in compact or not any(w in compact for w in ('취소', '반납', '철회', '종료')):
        return None
    # Pre-notices and preliminary enterprises must never become cancellation decisions.
    if re.search(r'예비(?:\([^)]*\))?사회적기업', compact):
        return 'preliminary_enterprise'
    if any(w in compact for w in ('청문', '사전통지', '의견제출', '예정')):
        return 'prior_notice'
    if '반납' in compact:
        return 'surrender_notice'
    if '취소' in compact:
        return 'cancellation_notice'
    return 'other_change'


def parse_listing(html, base_url):
    soup = BeautifulSoup(html, 'html.parser')
    table, total_el = soup.select_one('.board_list tbody'), soup.select_one('.board_info .total b')
    search = soup.select_one('input[name=searchText]')
    if table is None or total_el is None or search is None or search.get('value') != '사회적':
        raise ValueError('Listing layout/search changed')
    total = int(text(total_el).replace(',', ''))
    records = []
    for row in table.select('tr'):
        a = row.select_one('a[href*="bbs_seq="]')
        if a is None:
            if total:
                raise ValueError('Missing notice link in nonempty listing')
            continue
        dates = re.findall(r'\b\d{4}[.-]\d{2}[.-]\d{2}\b', text(row))
        if not dates:
            raise ValueError('Missing publication date')
        date = dates[0].replace('.', '-')
        dt.date.fromisoformat(date)
        url = official_url(urljoin(base_url, a['href']))
        seq = parse_qs(urlparse(url).query)['bbs_seq'][0]
        records.append({'id': seq, 'title': normalize_text(a.get('title') or text(a)), 'publishedAt': date, 'url': url})
    if total and not records:
        raise ValueError('Empty page despite nonzero total')
    return records, total


def parse_detail(html, record):
    soup = BeautifulSoup(html, 'html.parser')
    wrap = soup.select_one('.board_view_wrap')
    body = wrap.select_one('.b_content') if wrap else None
    if body is None:
        raise ValueError('Notice detail layout changed')
    fields = {text(dl.find('dt')): text(dl.find('dd')) for dl in wrap.select('.b_info dl')}
    if fields.get('제목') != record['title']:
        raise ValueError('Notice title/detail mismatch')
    published = fields.get('등록일', '')[:10].replace('.', '-')
    if published != record['publishedAt']:
        raise ValueError('Notice date/detail mismatch')
    attachments = []
    for a in wrap.select('.file a[href*="downloadFile.do"]'):
        attachments.append({'name': (a.get('title') or text(a)).removesuffix(' 다운로드'),
                            'url': official_url(urljoin(record['url'], a['href']))})
    # Hash public body for revision detection, without republishing personal information.
    fingerprint = hashlib.sha256(json.dumps({'body': text(body), 'attachments': attachments},
                                           sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return {**record, 'attachments': attachments, 'contentHash': fingerprint,
            'kind': classify(record['title']), 'reviewStatus': 'needs_review'}


def scan_board(client, office, board, since, max_pages=50):
    base = f"https://www.moel.go.kr/local/{office['code']}/news/{BOARDS[board]}"
    found, seen, prior_signature = [], set(), None
    for page in range(1, max_pages + 1):
        url = base + '?' + urlencode({'searchField': '1', 'searchText': '사회적', 'pageIndex': page})
        rows, total = parse_listing(client.get(url), base)
        signature = tuple(r['id'] for r in rows)
        if signature and signature == prior_signature:
            raise ValueError('Pagination repeated; refusing incomplete collection')
        prior_signature = signature
        for r in rows:
            seen.add(r['id'])
            if r['publishedAt'] >= since and classify(r['title']):
                found.append({**r, 'sourceOffice': office['name'], 'board': board})
        # Read every page in the filtered result: pinned/unsorted old rows cannot hide new ones.
        if len(seen) >= total:
            return found, page
    raise ValueError('Pagination limit reached; snapshot will not be replaced')


def merge_records(old, current, now):
    records = {r['id']: r for r in old}
    new_ids, changed_ids = [], []
    for r in current:
        previous = records.get(r['id'])
        if previous is None:
            new_ids.append(r['id'])
        elif any(previous.get(k) != r.get(k) for k in ('contentHash', 'title', 'kind')):
            changed_ids.append(r['id'])
        changed = r['id'] in new_ids or r['id'] in changed_ids
        records[r['id']] = {**r, 'firstSeenAt': previous['firstSeenAt'] if previous else now,
                           'lastChangedAt': now if changed else previous['lastChangedAt'],
                           'reviewStatus': 'needs_review' if changed else previous.get('reviewStatus', 'needs_review')}
    return sorted(records.values(), key=lambda r: (r['publishedAt'], r['id']), reverse=True), new_ids, changed_ids


def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)


def run(args):
    config = json.loads(CONFIG.read_text(encoding='utf-8-sig'))
    offices = config['offices']
    if args.offices:
        requested = set(args.offices.split(','))
        offices = [o for o in offices if o['code'] in requested]
        if {o['code'] for o in offices} != requested:
            raise ValueError('Unknown office')
        if args.output == OUTPUT:
            raise ValueError('Subset runs require a separate --output file')
    since = args.since or config['initialSince']
    dt.date.fromisoformat(since)
    client = Client(args.max_requests, args.delay)
    old = json.loads(args.output.read_text(encoding='utf-8')) if args.output.exists() else {'notices': []}
    found, coverage, errors = {}, [], []
    listings = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        tasks = {pool.submit(scan_board, client, office, board, since): (office, board)
                 for office in offices for board in BOARDS}
        for task in as_completed(tasks):
            office, board = tasks[task]
            try:
                rows, pages = task.result()
                coverage.append({'office': office['code'], 'board': board, 'pages': pages, 'matches': len(rows)})
                listings.extend(rows)
            except (ValueError, RuntimeError) as e:
                errors.append(f"{office['code']}/{board}: {e}")
                print(errors[-1], flush=True)
            print(f"Checked {office['code']}/{board}; {len(coverage)}/{len(tasks)} boards; {client.count} requests", flush=True)
    coverage.sort(key=lambda c: (c['office'], c['board']))
    for row in sorted(listings, key=lambda r: r['url']):
        # Stable canonical URL even when workers finish in a different order.
        found.setdefault(row['id'], row)
    current = []
    def read_detail(record):
        return parse_detail(client.get(record['url']), record)
    if not errors:
        with ThreadPoolExecutor(max_workers=4) as pool:
            tasks = {pool.submit(read_detail, record): record for record in found.values()}
            for task in as_completed(tasks):
                record = tasks[task]
                try:
                    current.append(task.result())
                except (ValueError, RuntimeError) as e:
                    errors.append(f"notice {record['id']}: {e}")
    if len(coverage) != len(offices) * len(BOARDS) or errors:
        raise RuntimeError('Incomplete scan; previous JSON preserved.\n' + '\n'.join(errors))
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    notices, new_ids, changed_ids = merge_records(old['notices'], current, now)
    result = {'schemaVersion': 1, 'lastSuccessfulScanAt': now, 'since': since,
              'scope': 'configured_moel_boards', 'officeCount': len(offices),
              'directorySource': config['directorySource'], 'directoryCheckedAt': config['directoryCheckedAt'],
              'requestCount': client.count, 'coverage': coverage, 'notices': notices}
    atomic_json(args.output, result)
    summary = (f"## Social enterprise notices\n\nSuccessful scan: {now}\n\n"
               f"Offices: {len(offices)}; boards: {len(coverage)}; requests: {client.count}\n\n"
               f"New: {len(new_ids)}; revised: {len(changed_ids)}; retained notices: {len(notices)}\n\n"
               'These are review candidates, not automatic certification decisions.\n')
    for r in notices:
        if r['id'] in new_ids + changed_ids:
            summary += f"\n- {r['publishedAt']} [{r['id']}]({r['url']}) ({r['kind']})"
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as f:
            f.write(summary)
    print(summary)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--offices', help='Comma-separated office codes for a separate smoke-test output')
    p.add_argument('--since', help='Publication cutoff YYYY-MM-DD (default: config initialSince)')
    p.add_argument('--output', type=Path, default=OUTPUT)
    p.add_argument('--max-requests', type=int, default=800)
    p.add_argument('--delay', type=float, default=0.4)
    args = p.parse_args()
    if args.max_requests < 1 or args.delay < 0:
        p.error('Invalid request budget or delay')
    try:
        run(args)
    except (ValueError, RuntimeError, OSError) as e:
        p.exit(1, f'{e}\n')


if __name__ == '__main__':
    main()
