# 사회적기업 인증 변경 공고 수집

## 운영

GitHub Actions `Watch social enterprise cancellations`가 매일 한국시간 08:23에 실행됩니다.
GitHub 스케줄은 지연될 수 있으며 기본 브랜치에 workflow가 있어야 동작합니다.
공개 저장소의 장기간 비활동으로 스케줄이 비활성화되는 경우 Actions에서 다시 활성화해야 합니다.
Actions의 **Run workflow**로 수동 실행할 수 있습니다. API 키는 필요하지 않습니다.

수집에 성공하면 `site/data/cancellation-notices.json`만 봇 계정으로 커밋하고 Pages를 직접 배포합니다.
GITHUB_TOKEN 커밋으로 별도의 push workflow가 실행되지 않아도 새 결과가 게시됩니다.
실행 요약에는 신규·정정 공고 링크와 검사 범위가 표시됩니다. 별도의 이메일/이슈 발송은 설정하지 않습니다.
실패는 Actions 실행 결과에 표시되며, 개인 알림은 GitHub 알림 설정을 따릅니다.

조회 화면은 `/cancellations.html`입니다. 마지막 전체 수집 성공시각을 표시하고 48시간 초과 시 경고합니다.

## 범위와 출처

- 관서 목록: [고용노동부 노동포털 관할관서 찾기](https://labor.moel.go.kr/portalGuide/competence_find.do), 2026-09-11 확인 49개 관서.
- 관리 파일: `config/cancellation-sources.json`. 관서 신설·개편 시 공식 목록과 대조하여 갱신합니다.
- 각 관서 **공지사항·공시송달** 게시판의 제목 검색어 `사회적` 결과를 페이지 끝까지 검사합니다.
- 게시일 2026-06-30 이후 중 제목에 `사회적기업`과 `취소/반납/철회/종료`가 함께 있는 공고를 보관합니다.
- 인증취소, 반납수리, 청문·사전통지, 예비사회적기업 관련 공고를 구분합니다. 분류는 제목 기반 검토 후보입니다.
- 게시물 번호 `bbs_seq`로 중복 제거합니다. 공시송달은 여러 관서 경로에서 동일 게시물이 나타날 수 있습니다.
  `sourceOffice`는 발견한 게시 경로이며 반드시 처분 기관을 의미하지 않습니다.

공식 페이지 예시:

- [서울서부지청 인증취소 공고](https://www.moel.go.kr/local/seoulseobu/news/notice/noticeView.do?bbs_seq=20260701078)
- [부산지방고용노동청 인증취소 공고](https://www.moel.go.kr/local/busan/news/notice/noticeView.do?bbs_seq=20260800549)

## 실패·변경 처리

- HTML 구조, 검색어 반영, 게시물 날짜, 반복 페이지, 목록/상세 제목 일치를 검증합니다.
- 관서 게시판 하나라도 실패하거나 페이지/요청 상한에 도달하면 전체 실행을 실패 처리하고 기존 결과를 보존합니다.
- 성공한 전체 결과만 임시 파일에서 원자적으로 교체합니다. 원문에서 사라진 과거 공고도 삭제하지 않습니다.
- 본문 해시·첨부 링크 변경을 정정 후보로 표시하고 최초 발견시각과 마지막 변경시각을 보관합니다.
- 재시도를 포함해 실행당 최대 800 HTTP 요청, 게시판별 최대 50페이지, 요청 간 최소 0.4초입니다.
  상한에 도달하면 일부 수집을 완료로 표시하지 않습니다.
- 본문 전체나 담당자·연락처를 재게시하지 않고 제목·게시일·출처 링크·첨부파일 이름/링크·본문 해시를 보관합니다.

## 판정 한계

이 봇은 공고 탐지용이며 기업 인증 유효성 검증 API가 아닙니다.
제목에 검색어가 없고 첨부파일에만 내용이 있는 공고, 다른 기관 사이트/관보에만 게시된 자료는 놓칠 수 있습니다.
첨부파일 내용 추출/OCR 및 기업 매칭은 구현하지 않았습니다. 같은 URL의 첨부 내용만 바뀐 경우는 탐지하지 못합니다.
따라서 `reviewStatus=needs_review`이며 기업 카탈로그의 인증상태를 자동 변경하지 않습니다.
청문·사전통지를 취소 확정으로 처리하지 않고, 실제 대상의 사업자번호/인증번호와 효력일을 원문에서 확인해야 합니다.
공고 미발견은 현재 유효 인증의 증명이 아닙니다. 공식 기업 명단의 주기적 갱신은 별도로 필요합니다.

## 로컬 실행

```powershell
python -m pip install -r requirements-cancellation.txt
python -m unittest discover -s tests -p test_cancellations.py -v
python scripts/watch_cancellations.py
```

소규모 실조회는 별도 파일에 저장합니다. 부분 관서 실행으로 운영 데이터를 덮어쓰는 것은 금지합니다.

```powershell
python scripts/watch_cancellations.py --offices seoulseobu,busan --output private/cancellations-smoke.json --max-requests 150
```

기본 수집 시작일은 설정 파일의 `initialSince`입니다. `--since YYYY-MM-DD`는 별도 조사 시 사용할 수 있습니다.
테스트의 가상 공고는 파서·중복·정정·실패 보존 검증 전용이며 운영 JSON에 합쳐지지 않습니다.
