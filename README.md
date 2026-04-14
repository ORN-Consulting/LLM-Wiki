# LLM Wiki Skill

Andrej Karpathy의 [LLM Wiki 패턴](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)을 기반으로,
Claude Code에서 Obsidian Vault 또는 일반 폴더형 지식저장소를 체계적으로 구축·운영하기 위한 스킬이다.

---

## 개념: 왜 LLM Wiki인가

일반적인 RAG는 질문할 때마다 원본 문서에서 정보를 검색한다.
LLM Wiki는 다르다. **소스를 받아들일 때 한 번 정리하고, 그 결과를 누적 자산으로 쌓는다.**

```
RAG    : 질문 → 원본 검색 → 답변 (매번 처음부터)
LLM Wiki: 소스 → wiki 반영 → 질문 → wiki 기반 답변 (지식이 복리로 쌓임)
```

### 3계층 구조

| 계층 | 위치 | 역할 |
|------|------|------|
| Raw Sources | `raw/`, `inbox/` 등 | 원본 문서. 절대 수정하지 않음 |
| Wiki | `wiki/` | LLM이 생성·유지하는 마크다운 페이지 집합 |
| Schema | `CLAUDE.md` | 위키 운영 규칙 (페이지 구조, 워크플로우 정의) |

---

## 파일 구성

```
LLM-Wiki/
├── SKILL.md             ← Claude Code 스킬 정의 (핵심 파일)
├── schema-template.md   ← CLAUDE.md 생성용 템플릿
├── wiki_init.py         ← 위키 폴더 구조 초기화 스크립트 (운영 JSON 포함)
├── wiki_lint.py         ← 구조 lint + 시맨틱 후보 추출 스크립트 (Layer 1)
└── README.md            ← 이 문서
```

---

## 설치

### 1단계 — 스킬 등록

Claude Code 스킬 디렉토리에 이 저장소를 복사한다.

```powershell
# 스킬 디렉토리 생성 (없을 경우)
New-Item -ItemType Directory -Force "$env:USERPROFILE\.claude\skills\llm-wiki"

# 파일 복사
Copy-Item -Path ".\*" -Destination "$env:USERPROFILE\.claude\skills\llm-wiki\" -Recurse
```

### 2단계 — 의존성 설치 (선택)

PyYAML과 Levenshtein을 설치하면 `wiki_lint.py`의 파싱 정확도와 중복 탐지 성능이 향상된다.

```powershell
pip install pyyaml python-Levenshtein
```

---

## 빠른 시작

### 새 위키 만들기

1. 대상 폴더를 Claude Code에서 연다.
2. 다음과 같이 요청한다:

```
이 폴더에 LLM Wiki 구조 만들어줘. 주제는 "AI 정책 동향 분석"이야.
```

Claude가 `wiki/` 폴더 구조와 `CLAUDE.md`를 자동 생성한다.

### 소스 반영하기

raw 폴더에 문서를 넣은 뒤:

```
raw/oecd-ai-report.pdf 를 wiki에 ingest 해줘.
```

### 위키 기반 질의

```
AI 거버넌스 관련해서 지금까지 쌓인 내용을 정리해줘.
```

### 위키 점검

```
wiki lint 해줘.
```

---

## 운영 모드 상세

### INIT — 위키 구조 초기화

**언제 쓰나**: 새 프로젝트에 위키를 처음 적용할 때

**Claude에게 요청하는 방법**:
- `"wiki 만들어줘"`
- `"Obsidian vault에 LLM Wiki 구조 적용해줘"`
- `"CLAUDE.md까지 세팅해줘"`

**Claude가 수행하는 작업**:
1. 현재 폴더 구조 확인 및 기존 `inbox/`, `references/` 등 raw source 폴더 감지
2. `wiki/sources/`, `wiki/entities/`, `wiki/topics/`, `wiki/analysis/` 생성
3. `wiki/index.md`, `wiki/log.md` 초기화
4. `schema-template.md` 기반으로 도메인에 맞는 `CLAUDE.md` 생성

**스크립트로 폴더 구조만 먼저 만들고 싶을 때**:

```powershell
python wiki_init.py "C:\Projects\MyWiki" --title "시장 조사 위키"
```

생성 결과 예시:
```
=== LLM Wiki initialized ===
Target: C:\Projects\MyWiki
Title:  시장 조사 위키

Created:
  + wiki\sources
  + wiki\entities
  + wiki\topics
  + wiki\analysis
  + wiki\index.md
  + wiki\log.md
  + wiki\_summary-index.json
  + wiki\_last-lint.json
  + wiki\_lint-cache.json

Using existing raw-source folders: 1. inbox, 2. references

Next steps:
  1. Create CLAUDE.md from schema-template.md.
  2. Add a source file and run an ingest workflow.
```

> `_summary-index.json`, `_last-lint.json`, `_lint-cache.json`은 LINT와 QUERY의 토큰 절감을 위한 운영 파일이다. `wiki_init.py`가 자동 생성한다.

---

### INGEST — 소스 수집 및 위키 반영

**언제 쓰나**: 새 문서를 위키에 통합할 때

**Claude에게 요청하는 방법**:
- `"이 문서 ingest 해줘"` (파일을 첨부하거나 경로 지정)
- `"raw 폴더의 보고서를 wiki에 반영해줘"`

**Claude가 수행하는 작업**:

| 순서 | 작업 |
|------|------|
| 1 | `CLAUDE.md` 읽기 — 현재 위키 규약 확인 |
| 2 | `wiki/log.md` 확인 — 중복 ingest 여부 검사 |
| 3 | raw source 읽기 및 분석 |
| 4 | `wiki/sources/source-<이름>.md` 생성 (카탈로그 역할, 간결하게) |
| 5 | 관련 `wiki/entities/`, `wiki/topics/` 생성 또는 **통합 규칙에 따라** 업데이트 |
| 6 | 필요 시 `wiki/analysis/` 페이지 추가 |
| 7 | `wiki/index.md`, `wiki/log.md` 갱신 |
| 8 | `wiki/_summary-index.json` 갱신 (토큰 절감용 메타데이터) |
| 9 | 누적 효과 보고 (각 페이지가 몇 개 소스에서 정보를 누적 중인지) |
| 10 | `inbox/` → `references/` 이동 (처리 완료 파일 분리) |
| 11 | 자동 light lint 실행 (구조 문제 즉시 확인·수정) |

> **핵심**: 소스 하나를 ingest할 때 10개 이상의 페이지에 영향을 주는 것이 정상이다.
> 이것이 지식이 복리로 쌓이는 메커니즘이다.

**엔티티/토픽 통합 규칙**: LLM Wiki의 핵심 가치는 **흩어진 정보의 교차 집계**에 있다. 새 정보는 기존 페이지의 관련 섹션 안에 맥락적으로 삽입하고, 모든 수치·사실에 출처를 병기하며, 시계열 데이터는 시간순으로 배치한다.

**페이지 분할**: 엔티티/토픽 페이지가 약 200줄 또는 하위 섹션 5개를 초과하면 독립 페이지로 분리를 검토한다.

**모순 처리**: 기존 위키 내용과 새 소스가 충돌하면 기존 내용을 삭제하지 않고
`주의` 또는 `충돌` 섹션으로 양쪽을 병기한다.

---

### QUERY — 위키 기반 질의 및 분석

**언제 쓰나**: 축적된 지식을 바탕으로 질문하거나 분석이 필요할 때

**Claude에게 요청하는 방법**:
- `"wiki 기준으로 A와 B를 비교해줘"`
- `"현재까지 쌓인 자료로 결론 정리해줘"`
- `"지원사업 추천해줘"` (정부지원사업 위키의 경우)

**작동 방식**:
1. `index.md`를 먼저 읽어 관련 페이지 목록 파악
2. 관련 페이지를 추려 읽고 내용 합성
3. wiki 내부 링크를 출처로 사용해 답변
4. 재사용 가치가 높은 답변은 `wiki/analysis/`에 자동 저장

> **팁**: `"이 분석 결과 저장해줘"`라고 명시하면 반드시 저장한다.

---

### LINT — 위키 건강 점검

**언제 쓰나**: ingest 시 자동(light), 주기적 수동(standard/deep)

**Claude에게 요청하는 방법**:
- `"wiki lint 해줘"` → standard (기본)
- `"wiki deep lint 해줘"` → deep (전수 검사)
- `"구조 문제 찾아줘"` → standard

**lint는 2계층 아키텍처로 동작한다.** Layer 1(Python 스크립트)이 토큰 소모 0으로 후보를 좁히고, Layer 2(LLM)가 좁혀진 범위만 읽고 최종 판정한다.

**lint 등급 및 권고 주기**:

| 등급 | 범위 | 권고 주기 | 토큰 |
|------|------|----------|------|
| `light` | 스크립트만 실행, 구조 문제 보고 | 매 ingest 후 자동 | 0 (스크립트) |
| `standard` | 후보 페이지 10~20개 비교 | 주 1회 또는 소스 5개 ingest 후 | ~15,000 (30p 기준) |
| `deep` | 전수 검사, 캐시 무시 | 월 1회 또는 구조 개편 후 | ~36,000 (100p 기준) |

**스크립트 실행**:

```powershell
python wiki_lint.py "C:\Projects\MyWiki\wiki"                    # standard (기본)
python wiki_lint.py "C:\Projects\MyWiki\wiki" --level light      # light
python wiki_lint.py "C:\Projects\MyWiki\wiki" --level deep       # deep (캐시 무시)
```

**Layer 1 — 스크립트 점검 항목** (토큰 소모 0):

| 구분 | 항목 | 설명 |
|------|------|------|
| 구조 | duplicate stems | 같은 이름의 파일이 여러 폴더에 있음 |
| 구조 | missing links | `[[링크]]`는 있지만 파일이 없음 |
| 구조 | ambiguous links | 같은 이름의 파일이 여러 개 존재해 링크가 모호함 |
| 구조 | orphan pages | 어떤 페이지에서도 링크되지 않는 페이지 |
| 구조 | weak pages | entities/, topics/ 중 본문이 200자 미만인 페이지 |
| 구조 | stale pages | `last_updated`가 90일 이상 지난 페이지 |
| 구조 | index drift | 실제 파일이 있지만 `index.md`에 누락된 페이지 |
| 시맨틱 #1 | 중복 후보 | 제목 편집거리(Levenshtein) 유사 쌍 추출 |
| 시맨틱 #2 | 모순 후보 | 같은 연도·다른 수치 쌍 추출 (standard/deep) |
| 시맨틱 #3 | Coverage gap | 소스에서 언급되지만 entity에 미반영된 항목 |
| 시맨틱 #4 | 분류 불일치 | entity/topic 키워드 점수 비교 (standard/deep) |
| 시맨틱 #5 | 출처 신뢰도 | low 단독 의존 페이지 |
| 시맨틱 #6 | 시계열 단절 | 연도+수치 비순차 |
| 시맨틱 #7 | 상호참조 부족 | 공유 소스 3개 이상인데 상호 링크 없는 쌍 |

**Layer 2 — LLM이 추가로 판정하는 항목**:
- #1 시맨틱 중복: 실제 동일 대상인지 확인, 병합 권고
- #2 수치·사실 모순: 같은 지표인지 확인 후 모순 vs 시점 차이 판정
- #3 관점 누락: coverage gap이 실제로 중요한 누락인지 판단
- #4 분류 불일치: entity/topic 성격 판정, 이동 권고

스크립트 실행 후 JSON 결과가 위키 상위 폴더에 `_lint_result.json`으로 저장된다.

---

### DIAGNOSE — 위키 구조 적합성 진단

**언제 쓰나**: 위키 구조가 목적에 맞는지 처음 검토하거나, 도메인이 바뀐 경우

**Claude에게 요청하는 방법**:
- `"이 wiki 구조가 맞는지 검토해줘"`
- `"Obsidian 지식창고 구조를 진단해줘"`

**점검 기준**:
1. `CLAUDE.md`가 운영 규약으로 충분한가
2. `entities/`, `topics/`, `analysis/` 분리가 도메인에 맞는가
3. raw source 경로 규칙이 실제 폴더 구조와 일치하는가
4. `index.md`, `log.md`를 실제로 운영하고 있는가
5. 이 프로젝트가 LLM Wiki 방식에 적합한가 (솔직한 평가 포함)

---

## 위키 페이지 구조

### 소스 요약 페이지 (`wiki/sources/source-<이름>.md`)

```yaml
---
title: "OECD AI 정책 보고서 2025"
date: 2025-03-15
source_type: report
reliability: high
raw_path: "raw/oecd-ai-report-2025.pdf"
source_url: "https://example.com/original-report"
---
```

- **reliability 기준**
  - `high`: 공식 보고서, 학술 논문, 공시 자료, 직접 인터뷰
  - `medium`: 언론 기사, 업계 분석, 전문가 블로그
  - `low`: SNS, 익명 커뮤니티, 날짜 미확인, 출처 불명

### 엔티티 프로필 (`wiki/entities/<이름>.md`)

사람, 기관, 제품, 정책 등 핵심 개체의 프로필.

```yaml
---
title: "OECD"
type: entity
last_updated: 2025-03-15
sources:
  - source-oecd-ai-policy-2025
---
```

### 주제 페이지 (`wiki/topics/<주제>.md`)

여러 소스에 걸쳐 나타나는 주제를 종합.

```yaml
---
title: "AI 거버넌스"
type: topic
last_updated: 2025-03-15
---
```

### 분석 페이지 (`wiki/analysis/<제목>.md`)

비교 분석, SWOT, 전망, 권고안 등 query 결과 중 재사용 가치가 높은 것.

---

## 로그 형식

`wiki/log.md`는 append-only로 유지한다.

```markdown
## [2026-04-10] ingest | OECD AI policy report
- 소스: raw/oecd-ai-policy.pdf
- 생성: wiki/sources/source-oecd-ai-policy.md
- 갱신: wiki/topics/ai-governance.md, wiki/entities/oecd.md
- 메모: 정책 비교표 추가. 용어 정의 불일치 1건 충돌 표시.
```

---

## Obsidian 연동

이 스킬로 생성한 wiki는 Obsidian Vault로 바로 열 수 있다.

| 기능 | 활용 방법 |
|------|----------|
| Graph View | `[[wikilink]]` 형식 덕분에 페이지 연결 관계를 시각적으로 확인 |
| Dataview | frontmatter의 `type`, `last_updated`, `reliability` 등으로 동적 테이블 생성 |
| 검색 | Obsidian 내장 검색 또는 qmd (로컬 마크다운 검색 엔진) 활용 |
| Web Clipper | 웹 기사를 마크다운으로 변환해 raw 폴더에 저장 후 ingest |

---

## CLAUDE.md 커스터마이징

`schema-template.md`를 기반으로 Claude가 자동 생성하지만, 도메인에 따라 추가 커스터마이징이 유용하다.

### 포함해야 할 핵심 항목

- wiki의 목적과 범위
- raw source 폴더 경로
- 페이지 유형별 파일명 규칙 및 필수 섹션
- wikilink 규칙
- ingest 절차
- query 결과 저장 기준
- 모순 병기 규칙
- `log.md` 형식

### 도메인별 추가 권장 사항

**경영컨설팅**: `entities/`에 고객사·경쟁사, `topics/`에 방법론·규제, `analysis/`에 전략 권고안

**연구·학술**: `entities/`에 연구자·기관·논문, `topics/`에 이론·방법론, 소스 요약에 연구방법론·표본 크기 필수 포함

**정부지원사업**: `entities/`에 지원기관, `programs/`(추가 폴더)에 개별 사업 프로필, `analysis/`에 사업 간 비교

**기술·제품 분석**: `entities/`에 기업·제품·기술표준, `topics/`에 트렌드·아키텍처, `analysis/`에 벤치마크

---

## 금지 사항

- raw source를 수정하거나 요약본으로 덮어쓰지 않는다.
- 출처 없는 내용을 사실처럼 위키에 기재하지 않는다.
- `index.md`와 `log.md` 갱신 없이 페이지만 추가하지 않는다.
- 모순을 발견했을 때 기존 서술을 조용히 삭제하지 않는다.

---

## 변경 이력

### v0.3.0 (2026-04-14)
- **LINT 2-Layer 아키텍처**: Layer 1(Python 스크립트, 토큰 0)이 후보를 좁히고 Layer 2(LLM)가 최종 판정하는 구조로 개편
- **7가지 시맨틱 검사**: 중복(#1), 모순(#2), Coverage Gap(#3), 분류 불일치(#4), 출처 신뢰도(#5), 시계열 단절(#6), 상호참조 부족(#7)
- **lint 3등급**: light(매 ingest 자동) / standard(주 1회) / deep(월 1회, 캐시 무시)
- **운영 JSON 3종**: `_summary-index.json`, `_last-lint.json`, `_lint-cache.json` — 토큰 절감 및 점진적 lint 지원
- **deep 레벨 캐시 무시**: deep lint 시 캐시를 건너뛰고 전수 재검사
- **INGEST 자동 light lint**: ingest 완료 후 자동으로 light lint 실행하여 구조 문제 즉시 확인

### v0.2.0 (2026-04-12)
- **INGEST 통합 규칙**: 엔티티/토픽 페이지의 맥락 삽입, 출처 병기, 시계열 배치, 모순 병기
- **페이지 분할 규칙**: 200줄 / 5섹션 기준
- **누적 효과 보고**: ingest 시 각 페이지의 소스 누적 수 보고
- **inbox → references 이동**: 처리 완료 파일 자동 분리
- **source summary 확장**: `raw_path`, `source_url` frontmatter 필드 추가
- **`_summary-index.json` 갱신**: ingest 시 메타데이터 자동 갱신

### v0.1.0 (2026-04-10)
- 최초 릴리스: INIT, INGEST, QUERY, LINT, DIAGNOSE 5개 운영 모드
- `wiki_init.py`, `wiki_lint.py`, `schema-template.md` 포함

## 참고

- [Andrej Karpathy — LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
- [Obsidian](https://obsidian.md)
- [Dataview Plugin](https://github.com/blacksmithgu/obsidian-dataview)
