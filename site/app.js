const $ = (id) => document.getElementById(id);
let rows = [], filtered = [], page = 1;
const size = 25;
const escape = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const safeUrl = (value) => { try { const u = new URL(value); return ['https:', 'http:'].includes(u.protocol) ? escape(u.href) : ''; } catch { return ''; } };
function empty(title, description, setup = false) {
  $('results').innerHTML = `<div class="empty"><div class="empty-icon">⌕</div><h3>${escape(title)}</h3><p>${escape(description)}</p>${setup ? '<a href="https://github.com/joongyu01/supplier_diversity#시작하기">수집 설정 안내 보기 ↗</a>' : ''}</div>`;
}
function render() {
  const query = $('search').value.trim().toLocaleLowerCase('ko');
  filtered = rows.filter(r => [r.productName,r.productCode,r.companyName].join(' ').toLocaleLowerCase('ko').includes(query) && (!$('category').value || r.categories.includes($('category').value)) && (!$('region').value || r.region === $('region').value));
  $('result-count').textContent = `검색 결과 ${filtered.length.toLocaleString()}건`;
  $('export').disabled = !filtered.length;
  $('pagination').hidden = filtered.length <= size;
  if (!rows.length) return empty('아직 수집된 물품이 없습니다', '조사 대상 업체와 API 인증키를 설정하면 등록 공급물품을 탐색할 수 있습니다.', true);
  if (!filtered.length) return empty('검색 조건에 맞는 물품이 없습니다', '검색어를 바꾸거나 기업 유형·지역 필터를 초기화해 보세요.');
  const pages = Math.ceil(filtered.length / size); page = Math.min(page,pages);
  $('page-label').textContent = `${page} / ${pages}`; $('prev').disabled = page === 1; $('next').disabled = page === pages;
  $('results').innerHTML = `<div class="table-wrap"><table><caption hidden>조회 조건에 맞는 나라장터 등록 공급물품</caption><thead><tr><th scope="col">등록 공급물품</th><th scope="col">업체</th><th scope="col">기업 유형 · 근거</th><th scope="col">지역</th><th scope="col">제조 여부</th></tr></thead><tbody>${filtered.slice((page-1)*size,page*size).map(r=>`<tr><td><strong>${escape(r.productName)}</strong><small>${escape(r.productCode)}</small></td><td>${escape(r.companyName)}<small>사업자 ${escape(r.bizno)}</small></td><td>${r.categories.map(c=>`<span class="tag">${escape(c)}</span>`).join('')}${r.evidence.map(e=>safeUrl(e.url)?`<a class="evidence" href="${safeUrl(e.url)}" target="_blank" rel="noopener">${escape(e.category)} 근거 ↗</a><small>확인 ${escape(e.checkedAt)} · 만료 ${escape(e.validUntil || '미등록')}</small>`:'').join('')}</td><td>${escape(r.region || '미제공')}</td><td>${escape(r.manufacturer === 'Y' ? '제조' : r.manufacturer === 'N' ? '비제조' : '미제공')}</td></tr>`).join('')}</tbody></table></div>`;
}
for (const id of ['search','category','region']) $(id).addEventListener('input',()=>{page=1;render();});
$('reset').onclick=()=>{for(const id of ['search','category','region']) $(id).value='';page=1;render();};
$('prev').onclick=()=>{page--;render();}; $('next').onclick=()=>{page++;render();};
const csvCell = v => '"'+String(v ?? '').replace(/^[=+@\-\t\r]/,"'$&").replaceAll('"','""')+'"';
$('export').onclick=()=>{
 const data=[['물품명','세부품명번호','업체명','사업자등록번호','기업 유형','지역','제조 여부','인증 근거','근거 확인일','인증 만료일'],...filtered.map(r=>[r.productName,r.productCode,r.companyName,r.bizno,r.categories.join('; '),r.region,r.manufacturer,r.evidence.map(e=>e.url).join('; '),r.evidence.map(e=>e.checkedAt).join('; '),r.evidence.map(e=>e.validUntil||'미등록').join('; ')])];
 const url=URL.createObjectURL(new Blob(['\uFEFF'+data.map(r=>r.map(csvCell).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'}));
 const a=document.createElement('a');a.href=url;a.download='supplier-diversity.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
};
async function init(){try{
 const response=await fetch('./data/catalog.json'); if(!response.ok) throw new Error('load');
 const data=await response.json(); if(!Array.isArray(data.products)||!Array.isArray(data.suppliers)) throw new Error('schema');
 rows=data.products;
 $('supplier-count').textContent=data.suppliers.length.toLocaleString(); $('product-count').textContent=rows.length.toLocaleString(); $('class-count').textContent=new Set(rows.map(r=>r.productCode)).size.toLocaleString();
 $('updated').textContent=data.updatedAt ? new Date(data.updatedAt).toLocaleDateString('ko-KR') : '수집 전';
 $('status-label').textContent=data.updatedAt ? '수집 시점의 등록 정보' : 'API 수집 설정 대기';
 for(const region of [...new Set(rows.map(r=>r.region).filter(Boolean))].sort()){const o=document.createElement('option');o.value=region;o.textContent=region;$('region').append(o);}
 render();
}catch{$('status-label').textContent='데이터 로드 실패';$('result-count').textContent='데이터를 불러오지 못했습니다';empty('데이터를 불러오지 못했습니다','잠시 후 페이지를 새로고침해 주세요. 문제가 계속되면 GitHub에서 배포 상태를 확인하세요.');}}
init();
