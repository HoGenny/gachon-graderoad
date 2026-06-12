# GradRoad Web Prototype

**위상정렬 알고리즘이 적용된 전공 선수과목 기반 졸업 로드맵 설계 서비스**를 간단한 웹 형태로 구현한 버전입니다.

## 프로젝트 개요

- What: 과목 검색, 선수과목 검증, 졸업요건 분석, 이번 학기 추천, 최종 졸업 로드맵 생성을 제공하는 웹 프로토타입
- Who: 컴퓨터공학과 재학생, 복학/편입/전과 후 이수계획을 점검해야 하는 학생
- When: 수강신청 전, 졸업요건 점검 시, 남은 학기별 전공/교양 배치를 설계할 때
- Why: 교육과정표만으로는 선수과목, 개설학기, 학점 제한, 졸업요건을 동시에 판단하기 어렵기 때문

## 실행 환경

- Python 3.10 이상 권장
- 외부 라이브러리 없음
- Python 표준 라이브러리 `http.server` 기반 로컬 웹 서버 사용

## 실행 방법

```bash
cd GradRoad_Web_Project
python app.py
```

브라우저에서 아래 주소로 접속합니다.

```text
http://127.0.0.1:8000
```

포트를 바꾸고 싶으면 다음처럼 실행합니다.

```bash
python app.py --port 8080
```

## 실행 확인

서버 실행 전 API와 알고리즘 모듈이 정상 동작하는지 확인할 수 있습니다.

```bash
python app.py --test
```

정상 실행 예시는 다음과 같습니다.

```text
GradRoad Web App self-test
[OK] /api/summary
[OK] /api/search
[OK] /api/prerequisite
[OK] /api/recommend
[OK] /api/roadmap
모든 테스트 통과
```

## 웹 기능 구성

| 메뉴 | 담당 | 사용 자료구조 | 사용 알고리즘 |
|---|---|---|---|
| 과목 검색 및 자동완성 | 김유빈 | Trie, Hash Table | Trie Prefix Search, KMP 문자열 탐색 |
| 선수과목 그래프 검증 | 김도훈 | Directed Graph, Queue/Stack | DFS Cycle Detection, Topological Sort |
| 졸업요건 분석 및 추천 | 신한서 | DP Table, Priority Queue/Heap | 0/1 Knapsack DP, Greedy Priority Selection |
| 최종 졸업 로드맵 생성 | 신호진 | Stack, Set/Constraint Matrix | Backtracking, Binary Search |

## 실제 사용 기능

- 현재 학년/학기와 이수 과목 체크 상태에 따라 모든 결과를 즉시 다시 계산합니다.
- 기준 학기를 바꾸면 이전 학기 과목이 자동 선택됩니다. 예: 1학년 2학기 기준은 1학년 1학기 과목, 2학년 1학기 기준은 1학년 전체 과목이 선택됩니다.
- 추천 결과는 JSON으로 저장할 수 있고, 로드맵 결과는 텍스트/JSON으로 저장할 수 있습니다.
- 로드맵 생성은 학점 용량 가지치기와 제한된 백트래킹 후보를 사용해 조합 폭발을 방지합니다.

## 폴더 구성

```text
GradRoad_Web_Project/
├─ app.py
├─ README.md
├─ requirements.txt
├─ GradRoad_프로젝트_설명서.docx
├─ data/
│  ├─ courses.csv
│  ├─ prerequisites.csv
│  ├─ requirements.csv
│  ├─ offerings.csv
│  └─ data_source.txt
├─ gradroad/
│  ├─ course_search.py
│  ├─ prerequisite_graph.py
│  ├─ graduation_optimizer.py
│  ├─ roadmap_generator.py
│  ├─ data_loader.py
│  └─ models.py
├─ templates/
│  └─ index.html
└─ static/
   ├─ style.css
   └─ app.js
```

## Input 데이터 출처

`data/data_source.txt`에 표시했습니다. `courses.csv`, `prerequisites.csv`, `requirements.csv`, `offerings.csv`는
제출된 교육과정 표를 반영해 입력 전용 데이터로 구성했습니다.

## 사용 방법

1. 왼쪽에서 기준 학년/학기를 선택합니다. 이전 학기 과목은 자동으로 체크됩니다.
2. 과목 검색, 선수과목 검증, 추천, 로드맵 탭을 눌러 기능을 실행합니다.
3. 이수 과목 체크를 직접 바꾸면 추천과 로드맵 결과가 달라집니다.