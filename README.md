# Supplier Diversity · 공공구매 우대기업 물품 카탈로그

공공기관 구매담당자가 **"이 물품을 우대기업 중 어디서 얼마에 살 수 있나"** 를 찾는 도구입니다. 나라장터 종합쇼핑몰 등록 품목을 정부권장정책 대상기업(사회적기업·중증장애인생산품 생산시설·여성기업·장애인기업·장애인표준사업장·창업기업·협동조합·시범구매) 목록과 사업자등록번호로 대조합니다.

- 웹사이트: https://joongyu01.github.io/supplier_diversity/
- 데이터: [조달청 종합쇼핑몰 품목정보 서비스](https://www.data.go.kr/data/15129471/openapi.do) + 조달청 정부권장정책 대상기업 목록(2026-06-30 기준, 엑셀)
- 화면: ① 품명 카드 → 우대유형별 공급업체 수 → ② 규격·제조사·업체명 검색, 계약단가, 대표자·주소·전화, CSV 다운로드 → ③ 종합쇼핑몰에 없는 품목은 중증장애인생산품 생산시설의 생산품목·연락처 검색

## 어떻게 동작하나

```
config/product_names.txt        기관이 실제 구매하는 품명 목록 (수십 개)
        │  scripts/collect_shopmall.py — 품명별 2026년 등록분 수집, 999건/호출
        ▼
data/raw/shopmall/<품명>.csv     원시 응답 (git 미추적)
        │  scripts/collect_suppliers.py — 등장 업체의 대표자·주소·전화 (업체당 1회)
data/raw/suppliers.csv
        │  scripts/build_catalog.py — 엑셀 사업자번호와 대조, 우대기업 품목만 남김
        ▼
site/data/catalog.json          업체 정보 + 품명 인덱스 + 중증 생산시설 (초기 로드, ~250KB)
site/data/chunks/<품명>.json     품목 상세 (품명 선택 시 개별 로드)
```

종합쇼핑몰 API는 검색용이 아니라 등록·변경 이벤트 피드라서 전체를 받으면 월 10~19만 건입니다. 대신 `getShoppingMallPrdctInfoList`의 품명 필터(부분일치)가 살아 있어 **필요한 품명만** 받습니다. 품명 15개 파일럿이 109회 호출·40분이었습니다. 확인된 명세와 한계는 [docs/api-notes.md](docs/api-notes.md), 엑셀 시트별 내용은 [docs/data-sources.md](docs/data-sources.md)에 있습니다.

## 게시 원칙

- **가공하지 않습니다.** 원시 CSV가 없으면 빌드는 중단합니다. 실제 업체명·사업자등록번호에 지어낸 물품·가격을 붙이지 않습니다.
- **사업자등록번호로만 대조합니다.** 기업명 문자열 매칭은 하지 않습니다.
- **우대기업이 아닌 업체의 품목은 싣지 않습니다.** 품명별 전체 건수만 `summary.json`에 남깁니다.
- **사업자등록 공개정보는 싣습니다.** 대표자·사업장 주소·전화·팩스·홈페이지는 나라장터 업체 기본정보(`getPrcrmntCorpBasicInfo02`)와 정부권장정책 목록에서 가져옵니다. 동명 사업체를 대표자로 구분하고 구매 담당자가 바로 연락·방문하기 위한 것입니다. 담당자 개인 이메일 같은 개인 연락처는 싣지 않습니다.
- 인증키·요청 URL·원시 응답은 저장소와 로그에 남기지 않습니다. 엑셀 원본(13.8MB)과 `data/raw/`는 git 미추적입니다.

화면의 단가·계약기간·인증 유효기간은 수집 시점 값입니다. 구매 전 나라장터에서 확인하세요.

## 실행

Python 3.10 이상. 수집·빌드에 `openpyxl`이 필요합니다(`pip install openpyxl`). 사이트와 테스트는 표준 라이브러리만 씁니다.

```powershell
# 1) 품명 목록 편집
notepad config\product_names.txt

# 2) 수집 (공공데이터포털 인증키, 15129471 활용신청 필요)
$env:DATA_GO_KR_SERVICE_KEY = "발급받은 키"
python scripts\collect_shopmall.py            # 이미 있는 품명 파일은 건너뜀
python scripts\collect_shopmall.py 프로젝터 UPS  # 특정 품명만
python scripts\collect_suppliers.py           # 등장 업체 연락처 (이미 있는 업체는 건너뜀)

# 3) 빌드 — 엑셀 원본이 저장소 루트에 있어야 함
python scripts\build_catalog.py

# 4) 확인
python -m unittest discover -s tests -v
node --check site\app.js
python -m http.server 8000 --directory site   # http://localhost:8000
```

수집은 하루 1,000회 한도 안에서 품명 수십 개면 충분합니다. 재수집하려면 `data/raw/shopmall/<품명>.csv`를 지우고 다시 실행합니다.

## 인증취소 공고 모니터 (별도 기능)

사회적기업 인증취소·반납 공고를 GitHub Actions가 매일 08:23(KST)에 고용노동부 관서 게시판에서 수집해 [공고 모니터 화면](https://joongyu01.github.io/supplier_diversity/cancellations.html)에 보여줍니다. 범위·한계는 [docs/cancellation-monitor.md](docs/cancellation-monitor.md). 카탈로그 파이프라인과는 독립적이며 `beautifulsoup4`가 필요합니다(`requirements-cancellation.txt`).

## 구조

```text
site/                        GitHub Pages 정적 사이트
site/data/catalog.json       업체·품명 인덱스·중증 생산시설
site/data/chunks/            품명별 품목 상세
config/product_names.txt     수집 대상 품명
scripts/collect_shopmall.py  품명 기준 수집
scripts/collect_suppliers.py 업체 기본정보(대표자·주소·전화) 수집
scripts/build_catalog.py     엑셀 대조·카탈로그 생성
scripts/collect.py           (보조) 사용자정보 API로 지정 업체의 등록 물품 조회
tests/                       정규화·조인·연락처 병합·산출 스키마 검증
docs/api-notes.md            실호출로 확인한 명세와 한계
docs/data-sources.md         엑셀 시트별 출처·건수·연락처 항목
scripts/watch_cancellations.py 인증취소 공고 모니터 (별도 기능)
```
