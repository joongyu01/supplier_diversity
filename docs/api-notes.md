# API 조사 기록

확인일: 2026-09-09

## 공식 자료

- [서비스 상세](https://www.data.go.kr/data/15129466/openapi.do)
- 해당 페이지 첨부 `조달청_OpenAPI참고자료_나라장터_사용자정보서비스_1.1.docx`
- [2026-01-07 서비스 변경 공지](https://www.data.go.kr/bbs/ntc/selectNotice.do?originId=NOTICE_0000000004468)

현행 HTTPS 기본 경로: `https://apis.data.go.kr/1230000/ao/UsrInfoService02`

| 용도 | 오퍼레이션 | 주요 응답 |
|---|---|---|
| 업체 기본정보 | getPrcrmntCorpBasicInfo02 | bizno, corpNm, rgnNm |
| 등록 공급물품 | getPrcrmntCorpSplyPrdctInfo02 | bizno, dtilPrdctClsfcNoNm, dtilPrdctClsfcNo, mnfctYn, chgDt |

공통 요청은 serviceKey, type=json, pageNo, numOfRows와 사업자등록번호 조회를 위한 inqryDiv=3, bizno입니다. 참고문서에서 조회구분 1은 등록일, 2는 변경일, 3은 사업자등록번호입니다.

## 명세 불일치

현재 페이지의 내장 Swagger는 공급물품 응답에 업종 필드(indstrytyNm 등)를 표시합니다. 같은 페이지의 DOCX 참고문서에는 실제 공급물품 필드(dtilPrdctClsfcNoNm 등)가 명시되어 있습니다. 수집기는 DOCX의 물품 필드를 사용하고, 필드가 없으면 오류로 중단하여 업종을 물품으로 오인하지 않습니다. 인증키를 사용한 실응답 검증은 아직 수행하지 못했습니다.

## 인증과 수집 범위

확인된 업체 기본정보 항목에서 사회적기업·여성기업·장애인기업·중소기업·중증장애인생산품 생산시설 여부를 직접 확인할 수 없었습니다. 따라서 업체 유형은 별도 출처를 갖는 입력 자료입니다. 이를 API가 확인한 인증이라고 표시하지 않습니다. 추후 공식 인증 목록을 확보하고 사업자등록번호·유효기간을 검증하는 별도 수집기를 추가할 수 있습니다.

현재 수집은 등록된 대상 업체만 포함하며 전국 전체 기업 또는 전체 제품 카탈로그가 아닙니다. 빈 공급물품 응답은 등록 물품이 조회되지 않았다는 뜻이며 해당 업체가 아무것도 판매하지 않는다는 의미가 아닙니다.

페이지 누락·전체 건수 변경·타 업체 응답·실패 응답은 모두 게시 중단 사유입니다. 업체당 최대 100페이지(페이지 크기 100)로 제한합니다. 재시도는 HTTP 429/일부 서버 오류 및 연결 실패에 최대 3회입니다. API 인증키 없이 실제 네트워크 성공을 주장하지 않으며 테스트는 가상 fixture 기반입니다.
