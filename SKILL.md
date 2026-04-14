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
    _summary-index.json  # 페이지별 압축 메타데이터 (LINT/QUERY 토큰 절감용)
    _last-lint.json      # 마지막 lint 시점·범위 (점진적 lint용)
    _lint-cache.json     # 검사 완료된 페이지 쌍 캐시 (재검사 스킵용)
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
4. `wiki/sources/`에 source summary 페이지를 만든다. (카탈로그 역할 — 간결하게)
5. 관련 `entities/`, `topics/`를 아래 **통합 규칙**에 따라 생성 또는 업데이트한다.
6. 필요하면 `analysis/` 페이지를 추가한다.
7. `index.md`와 `log.md`를 함께 갱신한다.
8. **`_summary-index.json` 갱신**: 생성·갱신한 페이지의 메타데이터(경로, 제목, 타입, 키워드, 한 줄 요약, 소스 목록, 주요 수치)를 `wiki/_summary-index.json`에 반영한다. 이 인덱스는 LINT와 QUERY의 토큰 절감에 사용된다.
9. **누적 효과 보고**: 변경 사항 요약 시, 각 엔티티/토픽 페이지가 몇 개 소스로부터 정보를 누적하고 있는지 함께 보고한다.
10. **inbox → references 이동**: `1. inbox/`에서 ingest한 파일은 같은 계층의 `2. references/`로 이동한다. inbox에 남아 있는 파일 = 아직 ingest되지 않은 파일로 즉시 판별 가능.

source summary 최소 규칙:

- 파일명: `wiki/sources/source-<slug>.md`
- frontmatter에 `title`, `date`, `source_type`, `reliability`, `raw_path`, `source_url`
- `source_url`: 정제본의 `# 원본 위치` 섹션에 URL(Google Drive, 웹 링크 등)이 있으면 반드시 source 카탈로그 frontmatter의 `source_url`로 승격한다. URL이 복수이면 YAML 리스트. **원본으로 직접 점프할 수 있는 1급 메타데이터.**
- 본문에 핵심 요점, 중요 수치, 관련 페이지 링크
- 소스 요약은 **카탈로그** 역할이다. "이 소스에 무엇이 있었는지" 빠르게 확인하는 용도이므로 간결하게 유지한다.

엔티티/토픽 페이지 통합 규칙:

LLM Wiki의 핵심 가치는 소스 요약의 깊이가 아니라, **흩어진 정보의 교차 집계**에 있다.
소스 하나를 깊이 파는 것은 원본이 낫지만, 여러 소스에 걸친 하나의 개체나 주제를 한눈에 보는 것은 위키가 낫다.
따라서 ingest의 무게중심은 엔티티/토픽 페이지의 통합 품질에 둔다.

- **맥락 삽입**: 새 정보는 기존 페이지의 관련 섹션 안에 삽입한다. 단순 추가(append)가 아니라, 기존 내용의 흐름 속에 자연스럽게 녹인다.
- **출처 병기**: 삽입하는 모든 수치·사실에 `([[source-xxx]])` 형태로 출처를 붙인다.
- **시계열 배치**: 동일 항목의 수치가 시점별로 다르면 시간순으로 나란히 배치한다.
  예: `매출: 450억(2023, [[source-A]]) → 520억(2024, [[source-B]])`
- **새 관점 추가**: 기존 페이지에 없던 관점이 나오면 새 섹션을 만들되, 기존 구조와 일관되게 배치한다.
- **모순 처리**: 기존 내용과 충돌하면 덮어쓰지 않고 ⚠️로 병기한다. (기존 규칙 유지)

페이지 분할 규칙:

엔티티/토픽 페이지가 소스 누적으로 비대해지면 가독성이 떨어진다.
다음 기준에 따라 분할한다.

- **분할 기준**: 페이지 본문이 약 200줄 또는 하위 섹션이 5개를 초과하면 분할을 검토한다.
- **분할 방법**: 독립적으로 읽힐 수 있는 하위 주제를 별도 토픽/분석 페이지로 분리하고, 원래 페이지에는 한 줄 요약 + `[[분리된-페이지]]` 링크로 대체한다.
- **분할 보고**: 분할 시 log.md에 `split` 작업으로 기록하고, index.md에 새 페이지를 추가한다.

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

lint는 **2계층 아키텍처**로 동작한다. 모든 시맨틱 검사를 LLM이 처리하면 컨텍스트 한계에 부딪히므로, 스크립트가 범위를 좁히고 LLM은 좁혀진 범위만 판단한다.

**lint 등급:**

- `light` — 스크립트 결과 + 요약 인덱스만 읽고 보고. 일상적 점검용.
- `standard` — 후보 페이지 10~20개를 실제 비교. 기본값.
- `deep` — 주요 페이지 전수 검사. 수동 요청 시.

#### Layer 1 — 스크립트 (`wiki_lint.py`)

토큰 소모 0. 파일을 파싱하되 의미 판단은 하지 않는다.

```powershell
python wiki_lint.py <wiki_folder_path>
```

구조 점검 (기존):

- duplicate page stem, missing wikilink, ambiguous wikilink
- orphan page, weak entity/topic page, stale page, `index.md` 누락

시맨틱 후보 추출 (확장):

- **중복 후보 (#1)**: 같은 폴더 내 제목 편집거리(Levenshtein)로 유사 쌍 추출
- **출처 신뢰도 (#5)**: source 페이지 `reliability` frontmatter 조회 → low 단독 의존 페이지 보고
- **시계열 패턴 (#6)**: 연도+숫자 정규식으로 순서 검증
- **상호참조 부족 (#7)**: frontmatter `sources` 목록으로 공유 소스 쌍 계산 → 3개 이상 공유하는데 상호 링크 없는 쌍 추출
- **Coverage gap (#3)**: entity/topic별 인바운드 소스 수 카운팅 → 소스에서 언급되지만 entity 페이지에 미반영된 항목

산출물: `_lint_result.json`에 구조 문제 + 시맨틱 후보 목록 포함.

#### Layer 2 — LLM 시맨틱 패스

Layer 1이 좁혀준 후보 페이지 쌍/목록만 읽고 최종 판정한다.

- **시맨틱 중복 (#1)**: 후보 쌍의 제목 + 개요(첫 100자) 비교로 실제 동일 대상인지 판정. 병합 권고.
- **수치·사실 모순 (#2)**: 교차 수치가 실제 모순인지, 시점/기준 차이인지 판정. 출처 신뢰도 비교.
- **관점 누락 (#3)**: Layer 1이 올린 coverage gap이 실제로 중요한 누락인지 판단.
- **분류 불일치 (#4)**: 페이지 내용이 entity 성격(고유 속성: 설립일, 대표, 소재지)인지, topic 성격(현상, 트렌드, 방법론)인지 판정. 이동 권고.
- **Layer 1 후보 최종 판정**: 스크립트가 올린 경고가 실제 문제인지 확인.

#### 7가지 시맨틱 점검 유형 요약

| # | 유형 | Layer 1 (스크립트) | Layer 2 (LLM) |
|---|------|-------------------|---------------|
| 1 | 엔티티/토픽 중복 | 제목 편집거리 유사 쌍 | 실제 동일 대상 판정 |
| 2 | 수치·사실 모순 | 수치 패턴 추출 + 링크 페이지 목록 | 모순 vs 시점차이 판정 |
| 3 | 관점 누락 (Coverage Gap) | 소스 언급 vs entity 반영 비교 | 누락 중요도 판단 |
| 4 | 분류 불일치 | — | entity/topic 성격 판정 |
| 5 | 출처 신뢰도 불균형 | reliability 집계, low 단독 의존 추출 | — (스크립트만으로 충분) |
| 6 | 시계열 단절 | 연도+수치 정규식 순서 검증 | — (스크립트만으로 충분) |
| 7 | 상호참조 부족 | 공유 소스 쌍 계산 + 링크 유무 | — (스크립트만으로 충분) |

#### 토큰 절감 전략

**요약 인덱스**: `wiki/_summary-index.json`에 각 페이지의 압축 메타데이터(경로, 제목, 타입, 키워드 3~5개, 한 줄 요약, 소스 목록, 주요 수치)를 유지한다. 100페이지 기준 약 3,000~5,000 토큰. LLM은 이 인덱스만 읽고 비교 대상을 선별한 뒤 해당 페이지만 연다. ingest 시 해당 페이지 항목만 갱신.

**점진적 lint**: 매번 전체를 검사하지 않는다. `wiki/_last-lint.json`에서 마지막 lint 시점을 확인하고, `log.md`에서 이후 변경된 페이지 + 1-hop 이웃만 비교 대상에 포함한다.

**결과 캐싱**: `wiki/_lint-cache.json`에 검사 완료된 페이지 쌍을 기록한다. 두 페이지 모두 `last_updated`가 변하지 않았다면 재검사를 건너뛴다.

#### 실행 흐름

```
lint 시작
  │
  ├─ Phase 0: wiki_lint.py 실행 (토큰 0)
  │   → 구조 문제 + 시맨틱 후보 목록 생성
  │
  ├─ Phase 1: _summary-index.json 읽기 (3,000~5,000 토큰)
  │   → 중복 후보, 분류 불일치 후보 식별
  │
  ├─ Phase 2: 후보 페이지만 선택적 읽기 (페이지당 200~400 토큰)
  │   → 모순, 중복, 분류 최종 판정
  │   → _lint-cache.json 대조해 이미 검사한 쌍은 스킵
  │
  └─ Phase 3: 결과 보고 + 캐시 갱신
      → log.md에 lint 기록
      → _last-lint.json, _lint-cache.json 갱신
```

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
  - 구조 lint + 시맨틱 후보 추출 스크립트 (Layer 1)

## 금지 사항

- raw source를 요약본으로 덮어쓰지 않는다.
- 출처 없는 내용을 사실처럼 적지 않는다.
- `index.md`와 `log.md`를 빼먹고 page만 추가하지 않는다.
- 모순을 발견했는데 기존 서술을 조용히 삭제하지 않는다.
