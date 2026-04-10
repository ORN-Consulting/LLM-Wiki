---
name: llm-wiki
description: |
  Karpathy의 LLM Wiki 패턴을 기반으로, Obsidian 또는 일반 폴더형 지식저장소를
  지속적으로 관리하기 위한 운영 스킬.

  이 스킬은 다음 상황에서 사용한다:
  - 새 vault 또는 프로젝트 폴더에 LLM Wiki 구조를 초기화할 때
  - 새 문서를 wiki에 반영하는 ingest 작업을 수행할 때
  - wiki를 기반으로 질문, 비교, 분석 결과를 만들고 저장할 때
  - orphan page, broken link, index drift 등 구조 문제를 점검할 때
  - 현재 wiki 구조가 목적에 맞는지 진단할 때
---

# LLM Wiki Skill

이 스킬의 목적은 raw source를 그대로 쌓아두는 것이 아니라, LLM이 관리하는
지속형 markdown wiki를 운영하는 것이다.

핵심 계층은 세 가지다.

1. Raw Sources
   - 원문 자료 보관층.
   - LLM은 읽기만 하고 수정하지 않는다.
2. Wiki
   - LLM이 생성·갱신하는 markdown 페이지 집합.
   - 요약, 엔티티, 토픽, 분석 결과가 여기에 쌓인다.
3. Schema
   - `CLAUDE.md` 같은 운영 규약 문서.
   - 구조, 페이지 종류, ingest/query/lint 규칙을 정의한다.

## 기본 원칙

- raw source는 immutable이다.
- `wiki/` 밖의 기존 파일은 사용자가 명시하지 않는 한 수정하지 않는다.
- 모든 주장에는 가능한 한 wiki 내부 출처 링크를 남긴다.
- 모순이 생기면 기존 내용을 지우지 말고 `주의` 또는 `경고` 섹션으로 병기한다.
- 단순 답변도 재사용 가치가 높으면 `wiki/analysis/`에 저장한다.
- `index.md`는 탐색 진입점이고, `log.md`는 append-only 운영 로그다.

## 표준 구조

가능하면 다음 구조를 사용한다.

```text
project/
  raw/                  # 또는 기존 inbox/, references/, sources/ 등
  wiki/
    index.md
    log.md
    sources/
    entities/
    topics/
    analysis/
  CLAUDE.md
```

기존 프로젝트에 `inbox/`, `references/`, `sources/`, `raw/` 같은 폴더가 이미 있으면
그 폴더를 raw source 경로로 인정하고 유지한다. 기존 폴더를 강제로 이동하지 않는다.

## 운영 모드

### 1. INIT

다음 상황에서 사용한다.

- "wiki 만들어줘"
- "Obsidian vault에 LLM Wiki 구조 적용해줘"
- "CLAUDE.md까지 세팅해줘"

작업 순서:

1. 현재 폴더 구조를 확인한다.
2. raw source 후보 폴더를 확인한다.
3. `wiki/`와 하위 디렉터리를 만든다.
4. `wiki/index.md`, `wiki/log.md`를 생성한다.
5. 같은 디렉터리의 `schema-template.md`를 읽고 `CLAUDE.md` 초안을 만든다.
6. 생성 결과와 raw source 경로를 사용자에게 보고한다.

자동화가 필요하면 먼저 아래 스크립트를 실행해도 된다.

```powershell
python wiki_init.py <target_folder> --title "Wiki Title"
```

### 2. INGEST

다음 상황에서 사용한다.

- "이 문서 ingest 해줘"
- "새 자료를 wiki에 반영해줘"
- "raw 문서 요약하고 관련 페이지 업데이트해줘"

작업 순서:

1. `CLAUDE.md`를 읽고 현재 wiki 규약을 확인한다.
2. `wiki/log.md`에서 중복 ingest 여부를 확인한다. 이미 처리된 소스라면 사용자에게 알리고 중단한다.
3. 대상 raw source를 읽는다.
4. `wiki/sources/`에 source summary 페이지를 만든다.
5. 관련 `entities/`, `topics/`를 생성 또는 업데이트한다.
6. 필요하면 `analysis/` 페이지를 추가한다.
7. `index.md`와 `log.md`를 함께 갱신한다.

source summary 최소 규칙:

- 파일명: `wiki/sources/source-<slug>.md`
- frontmatter에 `title`, `date`, `source_type`, `reliability`
- 본문에 핵심 요점, 중요 수치, 관련 페이지 링크

### 3. QUERY

다음 상황에서 사용한다.

- "wiki 기준으로 설명해줘"
- "비교 분석해줘"
- "현재까지 쌓인 자료로 결론 정리해줘"

작업 순서:

1. `index.md`를 먼저 읽는다.
2. 관련 페이지를 추려 읽는다.
3. wiki 내부 링크를 출처로 사용해 답변한다.
4. 재사용 가치가 높으면 `wiki/analysis/`에 결과를 저장한다.
5. 저장했다면 `index.md`, `log.md`도 갱신한다.

### 4. LINT

다음 상황에서 사용한다.

- "wiki lint 해줘"
- "건강 상태 점검해줘"
- "구조 문제 찾아줘"

우선 구조 lint 스크립트를 돌린다.

```powershell
python wiki_lint.py <wiki_folder_path>
```

이 스크립트는 다음을 점검한다.

- duplicate page stem
- missing wikilink
- ambiguous wikilink
- orphan page
- weak entity/topic page
- stale page
- `index.md` 누락

이후 LLM이 추가로 점검한다.

- 페이지 간 의미 충돌
- 상호 참조가 부족한 유사 개념
- 중요한데 아직 페이지가 없는 엔티티/토픽
- 출처 신뢰도 충돌

### 5. DIAGNOSE

다음 상황에서 사용한다.

- "이 구조가 맞는지 검토해줘"
- "Obsidian 지식창고 구조를 진단해줘"

점검 기준:

1. `CLAUDE.md`가 운영 규약으로 충분한가
2. `entities/`, `topics/`, `analysis/` 분리가 도메인에 맞는가
3. raw source 경로 규칙이 실제 폴더 구조와 일치하는가
4. `index.md`, `log.md`를 실제로 운영하고 있는가
5. 이 프로젝트가 정말 LLM Wiki 방식에 적합한가

## `CLAUDE.md` 필수 항목

초기화 시 생성하는 `CLAUDE.md`에는 최소한 다음이 포함되어야 한다.

- wiki의 목적과 범위
- raw source 경로
- 표준 페이지 타입과 파일명 규칙
- 각 페이지 타입의 최소 섹션
- wikilink 규칙
- ingest 절차
- query 결과 저장 기준
- 모순 병기 규칙
- `log.md` 형식

## 링크 규칙

- 내부 참조는 가능한 한 `[[page-name]]` 또는 `[[path/to/page]]`를 사용한다.
- 같은 stem이 여러 폴더에 존재할 수 있으면 경로형 링크를 선호한다.
- 깨진 링크를 남기지 않는다.
- 새 페이지를 만들었다면 가능한 한 다른 페이지에서 inbound link를 확보한다.

## 로그 규칙

`wiki/log.md`는 append-only로 유지한다. 각 엔트리는 반드시 다음 heading 형식을 따른다.

```markdown
## [YYYY-MM-DD] operation | Title
```

예시:

```markdown
## [2026-04-10] ingest | OECD AI policy report
- Source: raw/oecd-ai-policy.pdf
- Created: wiki/sources/source-oecd-ai-policy.md
- Updated: wiki/topics/ai-governance.md, wiki/entities/oecd.md
- Notes: Added policy comparison and flagged a terminology mismatch.
```

## Obsidian 운영 팁

- wikilink를 사용하면 Graph View가 유용해진다.
- frontmatter를 유지하면 Dataview와 연동하기 쉽다.
- attachment는 가능하면 로컬에 저장한다.
- wiki는 git 저장소처럼 다루는 편이 좋다. 변경 이력 관리가 쉬워진다.

## 포함 파일

- `schema-template.md`
  - `CLAUDE.md` 초안 생성용 템플릿
- `wiki_init.py`
  - 표준 구조 생성 스크립트
- `wiki_lint.py`
  - 구조 lint 스크립트

## 금지 사항

- raw source를 요약본으로 덮어쓰지 않는다.
- 출처 없는 내용을 사실처럼 적지 않는다.
- `index.md`와 `log.md`를 빼먹고 page만 추가하지 않는다.
- 모순을 발견했는데 기존 서술을 조용히 삭제하지 않는다.
