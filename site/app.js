const $ = (id) => document.getElementById(id);
const escape = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const lower = (v) => String(v ?? '').toLocaleLowerCase('ko');
const num = (v) => Number(String(v ?? '').replace(/[^\d.]/g, '')) || 0;
const won = (v) => (num(v) ? num(v).toLocaleString('ko-KR') + '원' : '—');
const TYPE_ORDER = ['사회적기업', '중증장애인생산품 생산시설', '여성기업', '장애인기업', '장애인표준사업장', '창업기업', '사회적협동조합', '기술개발제품 시범구매', '자활용사촌'];
const SHORT = { '중증장애인생산품 생산시설': '중증생산시설', '기술개발제품 시범구매': '시범구매', '사회적협동조합': '협동조합' };
const PAGE = 25;

const state = { catalog: null, chunkCache: new Map(), query: '', products: [], filtered: [], page: 1 };

function empty(el, title, description) {
  el.innerHTML = `<div class="empty"><div class="empty-icon">⌕</div><h3>${escape(title)}</h3><p>${escape(description)}</p></div>`;
}
function supplier(bizno) { return state.catalog.suppliers[bizno] || { name: '', region: '', types: [], excludedAsLargeCorp: false }; }
function typesOf(bizno) { return [...new Set(supplier(bizno).types.map((t) => t.type))].sort((a, b) => TYPE_ORDER.indexOf(a) - TYPE_ORDER.indexOf(b)); }
function contactBlock(c) {
  const parts = [];
  if (c.ceo) parts.push(`<small class="contact">대표 ${escape(c.ceo)}</small>`);
  if (c.tel) parts.push(`<small class="contact"><a href="tel:${escape(c.tel.replace(/[^\d+]/g, ''))}">${escape(c.tel)}</a></small>`);
  if (c.address) parts.push(`<small class="contact addr">${escape(c.address)}</small>`);
  if (c.homepage) parts.push(`<small class="contact"><a href="${escape(c.homepage)}" target="_blank" rel="noopener">홈페이지 ↗</a></small>`);
  return parts.join('');
}
function typeBadge(t, status) { return `<span class="tag tag-type${status === 'expired' ? ' tag-warn' : ''}" title="${escape(t)}${status === 'expired' ? ' · 인증 만료' : ''}">${escape(SHORT[t] || t)}</span>`; }

/* ---------- STEP 1: 품명 카드 ---------- */
function renderCategories() {
  const grid = $('category-grid');
  const chunks = [...state.catalog.chunks].sort((a, b) => b.suppliers - a.suppliers);
  if (!chunks.length) return empty(grid, '아직 수집된 품목이 없습니다', 'scripts/collect_shopmall.py 로 수집한 뒤 build_catalog.py 를 실행하세요.');
  $('category-note').textContent = `${chunks.length}개 품명 · 카드를 누르면 공급 우대기업을 보여줍니다`;
  grid.innerHTML = chunks.map((c) => {
    const top = Object.entries(c.typeSuppliers).sort((a, b) => TYPE_ORDER.indexOf(a[0]) - TYPE_ORDER.indexOf(b[0]));
    return `<button class="category-card${state.query === c.query ? ' active' : ''}" role="listitem" data-query="${escape(c.query)}">
      <strong>${escape(c.query)}</strong>
      <span class="category-count">우대기업 <b>${c.suppliers.toLocaleString()}곳</b> · 품목 ${c.count.toLocaleString()}건 <small>/ 전체 ${c.all.toLocaleString()}건</small></span>
      <span class="category-types">${top.map(([t, n]) => `<span class="mini-tag">${escape(SHORT[t] || t)} ${n}</span>`).join('') || '<span class="text-muted">우대기업 없음</span>'}</span>
    </button>`;
  }).join('');
  grid.querySelectorAll('.category-card').forEach((b) => b.addEventListener('click', () => selectCategory(b.dataset.query)));
}

async function selectCategory(query) {
  const chunk = state.catalog.chunks.find((c) => c.query === query);
  if (!chunk) return;
  state.query = query;
  $('explore').hidden = false;
  $('explore-title').textContent = `${query} · 로드 중…`;
  $('result-count').textContent = `${chunk.count.toLocaleString()}건 불러오는 중`;
  $('results').innerHTML = '';
  renderCategories();
  try {
    if (!state.chunkCache.has(query)) {
      const res = await fetch('./data/' + chunk.file);
      if (!res.ok) throw new Error('chunk');
      state.chunkCache.set(query, (await res.json()).products);
    }
  } catch {
    return empty($('results'), '품목을 불러오지 못했습니다', '잠시 후 다시 시도해 주세요.');
  }
  state.products = state.chunkCache.get(query);
  const nameSel = $('filter-name');
  nameSel.innerHTML = '<option value="">전체</option>' + chunk.names.map((n) => `<option value="${escape(n)}">${escape(n)}</option>`).join('');
  for (const id of ['search', 'filter-type', 'filter-name', 'sort']) $(id).value = '';
  $('hide-large').checked = true;
  state.page = 1;
  $('explore-title').textContent = `${query} · 우대기업 ${chunk.suppliers.toLocaleString()}곳 · ${chunk.count.toLocaleString()}건`;
  render();
  $('explore').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/* ---------- STEP 2: 결과 ---------- */
function render() {
  const q = lower($('search').value.trim());
  const type = $('filter-type').value;
  const name = $('filter-name').value;
  const hideLarge = $('hide-large').checked;
  let rows = state.products.filter((p) => {
    const s = supplier(p.b);
    if (hideLarge && s.excludedAsLargeCorp) return false;
    if (type && !typesOf(p.b).includes(type)) return false;
    if (name && p.n !== name) return false;
    if (q && !lower([p.n, p.s, p.m, p.cn, s.name, p.b, s.ceo, s.address].join(' ')).includes(q)) return false;
    return true;
  });
  const sort = $('sort').value;
  if (sort === 'price-asc') rows = rows.sort((a, b) => num(a.p) - num(b.p));
  else if (sort === 'price-desc') rows = rows.sort((a, b) => num(b.p) - num(a.p));
  else if (sort === 'company') rows = rows.sort((a, b) => a.cn.localeCompare(b.cn, 'ko'));
  state.filtered = rows;

  const corps = new Map();
  for (const p of rows) corps.set(p.b, typesOf(p.b));
  const counts = {};
  for (const ts of corps.values()) for (const t of ts) counts[t] = (counts[t] || 0) + 1;
  $('badge-bar').innerHTML = `<span class="summary-pill primary-pill">우대기업 ${corps.size.toLocaleString()}곳</span>` +
    TYPE_ORDER.filter((t) => counts[t]).map((t) => `<button class="summary-pill${type === t ? ' active' : ''}" data-type="${escape(t)}">${escape(SHORT[t] || t)} <b>${counts[t]}</b>곳</button>`).join('');
  $('badge-bar').querySelectorAll('button').forEach((b) => b.addEventListener('click', () => { $('filter-type').value = $('filter-type').value === b.dataset.type ? '' : b.dataset.type; state.page = 1; render(); }));

  $('result-count').textContent = `${rows.length.toLocaleString()}건`;
  $('export').disabled = !rows.length;
  $('pagination').hidden = rows.length <= PAGE;
  if (!rows.length) return empty($('results'), '조건에 맞는 품목이 없습니다', '검색어나 우대유형 필터를 바꿔 보세요.');
  const pages = Math.ceil(rows.length / PAGE);
  state.page = Math.min(state.page, pages);
  $('page-label').textContent = `${state.page} / ${pages}`;
  $('prev').disabled = state.page === 1;
  $('next').disabled = state.page === pages;
  $('results').innerHTML = `<div class="table-wrap"><table>
    <thead><tr><th scope="col">품명 · 규격</th><th scope="col">제조사</th><th scope="col">계약단가</th><th scope="col">공급 우대기업</th><th scope="col">우대유형</th><th scope="col">계약종료</th></tr></thead>
    <tbody>${rows.slice((state.page - 1) * PAGE, state.page * PAGE).map((p) => {
      const s = supplier(p.b);
      const expired = p.e && p.e < state.catalog.checkDate;
      return `<tr>
        <td><div class="product-title">${escape(p.n)}</div><div class="spec-cell">${escape(p.s)}</div>${p.x ? '<span class="tag tag-accent">우수제품</span>' : ''}${p.k ? '<span class="tag tag-sme">중기간경쟁</span>' : ''}</td>
        <td>${escape(p.m || '—')}</td>
        <td class="price-cell"><strong>${won(p.p)}</strong><small>${escape(p.u || '')}</small></td>
        <td><div class="company-name">${escape(p.cn || s.name)}</div><small class="bizno-code">사업자 ${escape(p.b)}</small>${contactBlock(s)}${s.excludedAsLargeCorp ? '<span class="tag tag-warn">대기업·상호출자</span>' : ''}</td>
        <td>${s.types.map((t) => typeBadge(t.type, t.status)).join('')}</td>
        <td><span class="status-badge ${expired ? 'expired' : 'valid'}">${escape(p.e || '—')}</span></td>
      </tr>`;
    }).join('')}</tbody></table></div>`;
}

for (const id of ['search', 'filter-type', 'filter-name', 'sort', 'hide-large']) $(id).addEventListener('input', () => { state.page = 1; render(); });
$('reset').onclick = () => { for (const id of ['search', 'filter-type', 'filter-name', 'sort']) $(id).value = ''; $('hide-large').checked = true; state.page = 1; render(); };
$('prev').onclick = () => { state.page--; render(); };
$('next').onclick = () => { state.page++; render(); };

const csvCell = (v) => '"' + String(v ?? '').replace(/^[=+@\-\t\r]/, "'$&").replaceAll('"', '""') + '"';
$('export').onclick = () => {
  const head = ['품명', '규격', '제조사', '계약단가', '단위', '업체명', '사업자등록번호', '대표자', '전화', '주소', '홈페이지', '우대유형', '인증만료일', '계약종료일', '우수제품', '중기간경쟁제품', '물품식별번호'];
  const body = state.filtered.map((p) => {
    const s = supplier(p.b);
    return [p.n, p.s, p.m, p.p, p.u, p.cn || s.name, p.b, s.ceo, s.tel, s.address, s.homepage, s.types.map((t) => t.type).join('; '), s.types.map((t) => t.validUntil || '미등록').join('; '), p.e, p.x ? 'Y' : '', p.k ? 'Y' : '', p.id];
  });
  const blob = new Blob(['﻿' + [head, ...body].map((r) => r.map(csvCell).join(',')).join('\r\n')], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = url; a.download = `supplier-diversity-${state.query}.csv`; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};

/* ---------- 중증 생산시설 ---------- */
function renderFacilities() {
  const q = lower($('facility-search').value.trim());
  const region = $('facility-region').value;
  const validOnly = $('facility-valid').checked;
  const rows = state.catalog.facilities.filter((f) => (!validOnly || f.status !== 'expired') && (!region || f.region === region) && (!q || lower([f.name, f.bizno, f.ceo, f.address, ...f.items].join(' ')).includes(q)));
  $('facility-count-label').textContent = `${rows.length.toLocaleString()}곳`;
  if (!rows.length) return empty($('facility-results'), '조건에 맞는 생산시설이 없습니다', '다른 품목명으로 검색해 보세요.');
  $('facility-results').innerHTML = `<div class="table-wrap"><table>
    <thead><tr><th scope="col">생산시설</th><th scope="col">연락처 · 주소</th><th scope="col">생산품목</th><th scope="col">지정 유효기간</th></tr></thead>
    <tbody>${rows.slice(0, 200).map((f) => `<tr>
      <td><div class="company-name">${escape(f.name)}</div><small class="bizno-code">사업자 ${escape(f.bizno)}</small>${f.otherTypes.map((t) => typeBadge(t)).join('')}</td>
      <td>${contactBlock(f) || '<span class="text-muted">—</span>'}</td>
      <td>${f.items.map((i) => `<span class="mini-tag${q && lower(i).includes(q) ? ' hit' : ''}">${escape(i)}</span>`).join(' ')}</td>
      <td><span class="status-badge ${f.status === 'expired' ? 'expired' : 'valid'}">${escape(f.validUntil || '—')}</span></td>
    </tr>`).join('')}</tbody></table></div>${rows.length > 200 ? `<p class="text-muted">상위 200곳만 표시. 검색어로 좁혀 주세요.</p>` : ''}`;
}
for (const id of ['facility-search', 'facility-region', 'facility-valid']) $(id).addEventListener('input', renderFacilities);

/* ---------- init ---------- */
async function init() {
  try {
    const res = await fetch('./data/catalog.json');
    if (!res.ok) throw new Error('load');
    const data = await res.json();
    if (!Array.isArray(data.chunks) || typeof data.suppliers !== 'object') throw new Error('schema');
    state.catalog = data;
    $('product-count').textContent = data.totalCount.toLocaleString();
    $('supplier-count').textContent = Object.keys(data.suppliers).length.toLocaleString();
    $('facility-count').textContent = (data.facilities || []).length.toLocaleString();
    $('updated').textContent = data.checkDate || '—';
    $('status-label').textContent = data.generatedAt ? '종합쇼핑몰 수집 시점' : '수집 전';
    $('notice-collected').textContent = data.checkDate ? `${data.checkDate} 수집` : '수집일 기준';
    for (const r of [...new Set((data.facilities || []).map((f) => f.region).filter(Boolean))].sort()) {
      const o = document.createElement('option'); o.value = r; o.textContent = r; $('facility-region').append(o);
    }
    renderCategories();
    renderFacilities();
  } catch {
    $('status-label').textContent = '데이터 로드 실패';
    empty($('category-grid'), '데이터를 불러오지 못했습니다', '잠시 후 새로고침해 주세요. 문제가 계속되면 GitHub에서 배포 상태를 확인하세요.');
  }
}
init();
