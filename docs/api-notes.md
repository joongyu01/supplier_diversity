# API 조사 기록

확인일: 2026-09-11. 아래 "실호출 확인" 항목은 이 저장소의 인증키로 직접 호출해 확인한 것이고, "인용" 항목은 타 프로젝트·명세 문서에서 가져온 것이다.

## 사용 중: 조달청 종합쇼핑몰 품목정보 서비스 (15129471)

- [서비스 상세](https://www.data.go.kr/data/15129471/openapi.do) · 무료 · 개발계정 1,000회/일 · 활용신청 자동승인
- 기본 경로: `https://apis.data.go.kr/1230000/at/ShoppingMallPrdctInfoService/`
- 오퍼레이션(스웨거 기준 9종): `getShoppingMallPrdctInfoList`, `getMASCntrctPrdctInfoList`, `getUcntrctPrdctInfoList`, `getThptyUcntrctPrdctInfoList`, `getDlvrReqInfoList`, `getDlvrReqDtlInfoList`, `getVntrPrdctOrderDealDtlsInfoList`, `getSpcifyPrdlstPrcureInfoList`, `getSpcifyPrdlstPrcureTotList`

### 실호출 확인 (2026-09-11)

| 항목 | `getShoppingMallPrdctInfoList` | `getMASCntrctPrdctInfoList` |
|---|---|---|
| 필수 파라미터 | `inqryDiv=1`, `inqryBgnDate`, `inqryEndDate` (YYYYMMDD) | `inqryDiv=1`, `rgstDtBgnDt`, `rgstDtEndDt` (YYYYMMDDHHMM) |
| `numOfRows=999` | 동작 (999건 반환) | 동작 |
| 품명 필터 `prdctClsfcNoNm` | **동작, 부분일치** (`책상` → 학생용책상·컴퓨터책상 포함) | **동작하지 않음** (응답의 품명을 그대로 넣어도 0건) |
| 규격명 필터 `prdctIdntNoNm` | 0건 (동작 여부 미확정) | 파라미터 없음 |
| 업체 식별자 | `cntrctCorpBizno` = 사업자등록번호 10자리, 85,301건 중 결측 0 | `cntrctCorpNo` = 사업자등록번호 10자리 (999/999). 2015년 DOCX 1.0의 `CN0100000144459` 형식은 구버전 |
| 우선구매 인증명 | 없음 | `prefrpurchsObjCertNm` 예: `여성기업제품,장애인기업제품,소기업`. 사회적기업·중증은 이 필드에 나오지 않음 |
| `inqryDiv` 2·3·4 | 응답 없음 | 2 = 변경일시 기준 |
| 날짜 윈도 | 등록일 이벤트. 하루 147건·한 달 13,880건(책상). 2년 윈도는 응답 없음 → 4~5개월 단위로 분할 | 2020년 조회 0건 → 과거 조회용 아님 |

성격: 검색 API가 아니라 **등록·변경 이벤트 피드**다. 다만 `getShoppingMallPrdctInfoList`는 품명 필터가 살아 있어 필요한 품명만 좁혀 받을 수 있다. 이 저장소는 `config/product_names.txt`의 품명으로 2026년 등록분을 수집한다(`scripts/collect_shopmall.py`). 전체 미러링(월 10~19만 건)은 하지 않는다.

종합쇼핑몰에 아예 없는 품목이 있다: `복사용지`, `현수막`, `쇼핑백`, `세제`, `복합기` 는 2026년 등록분 0건. 이런 품목은 엑셀 중증 시트의 생산품목이 유일한 소스라 화면에서 별도 섹션으로 보여준다.

### 조인 결과 (파일럿, 품명 15개, 2026-09-11)

- 원시 85,301건 → 정부권장정책 엑셀 사업자번호 일치 46,349건(54%), 우대기업 292곳
- 사회적기업 50곳·6,442건, 중증장애인생산품 생산시설 35곳·2,340건 — API 인증필드에 없는 유형을 엑셀이 채운다

### 인용

- 응답 필드 목록과 스웨거: [umyunsang/UMMAYA](https://github.com/umyunsang/UMMAYA) `docs/api/data-go-kr-candidate-docs/15129471/`
- 실호출 계약 기록(2026-07-16): [stevenahhh/g2b-compare](https://github.com/stevenahhh/g2b-compare) `docs/api-contract-observed.json`
- 월별 윈도 전수 수집 구현: [Hbin77/margin-radar](https://github.com/Hbin77/margin-radar) `pipeline/collect_full.py` (`PER_PAGE=999`)

## 업체 연락처: 나라장터 사용자정보 서비스 (15129466) `getPrcrmntCorpBasicInfo02`

실호출 확인(2026-09-11): `inqryDiv=3&bizno=` 로 1건 조회. 응답 `corpNm, ceoNm(대표자), adrs+dtlAdrs(주소), zip, rgnNm, telNo, faxNo, hmpgAdrs, emplyeNum(직원수), mnfctDivNm(제조/비제조), opbizDt(개업일), corpBsnsDivNm`. 카탈로그에 등장하는 업체(수백 곳)만 조회하므로 업체당 1회 구조여도 문제없다(`scripts/collect_suppliers.py`, 결과 `data/raw/suppliers.csv`에 캐시). 같은 서비스의 `getPrcrmntCorpSplyPrdctInfo02`(등록 공급물품)는 세부품명 층위라 규격·단가가 없어 쓰지 않는다.

## 검토 후 제외한 소스

| 소스 | 제외 이유 |
|---|---|
| [한국사회적기업진흥원 사회적경제기업 상품정보](https://www.data.go.kr/data/15038606/fileData.do) (7,913행) | 판매자명만 있고 사업자등록번호 없음 → 기업명 문자열 매칭뿐이라 오탐 위험 |
| [고용노동부 사회적기업 목록](https://www.data.go.kr/data/15090110/fileData.do) (3,534곳) | 사업내용은 있으나 사업자등록번호 없음 |
| [조달데이터허브](https://data.g2b.go.kr/) | 보고서 대량 다운로드 가능하나 SSO 로그인 필요 |
| [공공구매종합정보망 인증서 정보](https://www.data.go.kr/data/15062581/openapi.do) | 사업자번호 → 직접생산확인 세부품목 조회. 업체당 호출이라 규모 문제 동일. 후속 보강 후보 |

## 게시 원칙

- 원시 CSV가 없으면 `build_catalog.py`는 중단한다. 실제 업체명·사업자등록번호에 가공한 물품·가격을 붙여 게시하지 않는다.
- 조인 키는 사업자등록번호뿐이다. 기업명 문자열 매칭은 하지 않는다.
- 우대기업이 아닌 업체의 품목은 저장하지 않고, 품명별 전체 건수만 `summary.json`에 남긴다.
- 대표자·사업장 주소·전화는 사업자등록 공개정보로 싣는다. `getMASCntrctPrdctInfoList`의 `cntrctOfclNm`·`cntrctOfclEmail`(계약담당자 개인 이름·이메일)은 싣지 않는다.
- 인증키·요청 URL·원시 응답은 로그와 저장소에 남기지 않는다.
