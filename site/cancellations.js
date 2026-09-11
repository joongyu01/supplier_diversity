'use strict';
const labels = {cancellation_notice: '인증취소 관련 · 원문 검토 필요', surrender_notice: '인증반납 관련 · 원문 검토 필요', prior_notice: '청문·사전통지 · 취소 확정 아님', preliminary_enterprise: '예비사회적기업 관련', other_change: '기타 변경'};
let notices = [];
function link(label, url) {
  const a = document.createElement('a');
  const parsed = new URL(url);
  if (parsed.protocol !== 'https:' || parsed.hostname !== 'www.moel.go.kr') throw new Error('출처 URL 오류');
  a.textContent = label; a.href = url; a.target = '_blank'; a.rel = 'noopener noreferrer';
  return a;
}
function renderNotices() {
  const q = document.getElementById('query').value.trim().toLowerCase();
  const kind = document.getElementById('kind').value;
  const selected = notices.filter(n => (!kind || n.kind === kind) && `${n.title} ${n.sourceOffice}`.toLowerCase().includes(q));
  document.getElementById('count').textContent = `공고 ${selected.length}건 (기업 수와 다릅니다)`;
  const container = document.getElementById('notices'); container.replaceChildren();
  for (const n of selected) {
    const article = document.createElement('article');
    const heading = document.createElement('h2'); heading.append(link(n.title, n.url));
    const meta = document.createElement('small'); meta.textContent = `${n.publishedAt} · 게시 경로: ${n.sourceOffice} · ${labels[n.kind] || n.kind}`;
    const files = document.createElement('ul');
    for (const f of n.attachments || []) { const li = document.createElement('li'); li.append(link(f.name, f.url)); files.append(li); }
    article.append(heading, meta, files); container.append(article);
  }
}
for (const id of ['query', 'kind']) document.getElementById(id).addEventListener('input', renderNotices);
fetch('./data/cancellation-notices.json', {cache: 'no-store'}).then(r => {
  if (!r.ok) throw new Error('수집 결과가 아직 없거나 불러오지 못했습니다.');
  return r.json();
}).then(data => {
  if (!Array.isArray(data.notices) || !data.lastSuccessfulScanAt) throw new Error('수집 결과 형식 오류');
  notices = data.notices;
  document.getElementById('status').textContent = `마지막 전체 수집 성공: ${new Date(data.lastSuccessfulScanAt).toLocaleString('ko-KR', {timeZone: 'Asia/Seoul'})} (한국시간) · ${data.officeCount}개 관서 · ${data.since} 이후 게시 공고`;
  if (Date.now() - Date.parse(data.lastSuccessfulScanAt) > 48 * 3600 * 1000) {
    const warning = document.getElementById('freshness'); warning.hidden = false; warning.textContent = '마지막 수집 성공 후 48시간이 지났습니다. 최근 실행 상태를 확인하세요.';
  }
  renderNotices();
}).catch(e => { document.getElementById('status').textContent = e.message; });
