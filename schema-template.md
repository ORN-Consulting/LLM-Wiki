# {위키_제목} — 운영 규약

## 목적

이 위키는 raw source 문서와 분석 결과 사이에 지속적인 지식 계층을 유지하기 위해 존재한다.
위키는 실무 지식창고이고, raw 문서는 변경되지 않는 원본이다.

## Raw Source 경로

- 소스 폴더: {RAW_SOURCE_경로}
- raw source 파일은 읽기 전용이다. 절대 수정하지 않는다.
- 새 자료는 raw source 폴더에 먼저 추가한 뒤 wiki에 반영한다.

## 디렉토리 구조

```text
wiki/
  index.md       ← 전체 페이지 목록 (탐색 진입점)
  log.md         ← append-only 작업 로그
  sources/       ← 소스별 요약 페이지
  entities/      ← 핵심 개체 프로필
  topics/        ← 주제별 종합 페이지
  analysis/      ← 비교 분석, 메모, 권고안
```

## 페이지 유형

### 소스 요약 (wiki/sources/)

파일명 규칙:

```text
wiki/sources/source-<슬러그>.md
```

frontmatter:

```yaml
---
title: "<소스 제목>"
date: YYYY-MM-DD
source_type: article|report|paper|news|data|transcript|other
reliability: high|medium|low
---
```

reliability 기준:
- **high**: 1차 데이터 — 공식 보고서, 학술 논문, 공시 자료, 직접 인터뷰
- **medium**: 2차 가공 — 언론 기사, 업계 분석, 전문가 블로그
- **low**: 3차 이하 — SNS, 익명 커뮤니티, 날짜 미확인, 출처 불명

source_type 허용값: `article` `report` `paper` `news` `data` `transcript` `other`

필수 섹션:

1. 요약
2. 핵심 포인트
3. 중요 수치 및 근거
4. 관련 페이지

---

### 엔티티 프로필 (wiki/entities/)

파일명 규칙:

```text
wiki/entities/<슬러그>.md
```

frontmatter:

```yaml
---
title: "<개체명>"
type: entity
last_updated: YYYY-MM-DD
sources:
  - source-<슬러그>
---
```

필수 섹션:

1. 개요
2. 현재 상태
3. 근거 있는 주요 사실 (출처 링크 포함)
4. 관련 주제

---

### 주제 페이지 (wiki/topics/)

파일명 규칙:

```text
wiki/topics/<슬러그>.md
```

frontmatter:

```yaml
---
title: "<주제명>"
type: topic
last_updated: YYYY-MM-DD
---
```

필수 섹션:

1. 주제 요약
2. 핵심 논점 또는 구성 요소
3. 미해결 질문 및 모순
4. 관련 엔티티 및 소스

---

### 분석 페이지 (wiki/analysis/)

파일명 규칙:

```text
wiki/analysis/<슬러그>.md
```

frontmatter:

```yaml
---
title: "<분석 제목>"
type: analysis
date: YYYY-MM-DD
---
```

필수 섹션:

1. 질문 또는 목적
2. 종합
3. 근거 페이지
4. 실행 가능한 결론

---

## 링크 규칙

- 내부 참조는 `[[페이지명]]` 형식을 사용한다.
- 같은 이름이 여러 폴더에 존재하면 `[[topics/주제명]]` 처럼 경로형 링크를 쓴다.
- 깨진 링크를 남기지 않는다. 링크 대상이 없으면 먼저 페이지를 만든다.
- 새 페이지를 만들었다면 다른 페이지에서 inbound 링크를 하나 이상 확보한다.

## Ingest 워크플로우

1. `wiki/log.md`에서 동일 소스의 중복 ingest 여부를 먼저 확인한다.
2. raw source를 읽는다.
3. `wiki/sources/`에 소스 요약 페이지를 만든다.
4. 관련 엔티티 페이지를 생성하거나 업데이트한다.
5. 관련 주제 페이지를 생성하거나 업데이트한다.
6. ingest가 분석 결과를 만들었다면 `wiki/analysis/`에 저장한다.
7. `wiki/index.md`를 갱신한다.
8. `wiki/log.md`에 항목을 추가한다.

관련 페이지 업데이트는 넓게 한다. 소스 하나를 ingest할 때 10개 이상의 페이지에 영향을 주는 것이 정상이다.

## Query 워크플로우

1. `wiki/index.md`를 먼저 읽는다.
2. 질문과 관련된 페이지를 추려 읽는다.
3. wiki 내부 링크를 출처로 사용해 답변한다.
4. 재사용 가치가 높은 답변은 `wiki/analysis/`에 저장한다.
5. 저장했다면 `index.md`와 `log.md`도 갱신한다.

## 모순 처리 규칙

- 새 소스가 기존 내용과 충돌할 때 기존 내용을 조용히 삭제하지 않는다.
- 두 주장을 모두 유지하고 `주의`, `충돌`, 또는 `미해결 질문` 섹션으로 명시한다.
- 관련 소스 페이지를 모두 링크한다.

## 로그 형식

모든 로그 항목은 다음 heading으로 시작해야 한다:

```markdown
## [YYYY-MM-DD] 작업유형 | 제목
```

작업유형: `ingest` `query` `lint` `init` `update`

권장 본문:

```markdown
- 소스: <경로 또는 해당 없음>
- 생성: <쉼표로 구분된 경로 또는 없음>
- 갱신: <쉼표로 구분된 경로 또는 없음>
- 메모: <1~2줄>
```

## 유지 관리 규칙

- `index.md`를 현재 페이지 목록과 항상 동기화한다.
- 엔티티·주제 페이지가 실질적으로 변경되면 `last_updated`를 갱신한다.
- 장황한 요약보다 간결하고 출처 근거가 있는 서술을 선호한다.
- 위키를 메모 더미가 아닌 유지 관리되는 시스템으로 다룬다.

## 도메인별 참고사항

{도메인_특화_지침}
