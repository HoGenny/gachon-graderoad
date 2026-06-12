"""GradRoad Web App

프로젝트명: 위상정렬 알고리즘이 적용된 전공 선수과목 기반 졸업 로드맵 설계 서비스
실행 환경: Python 3.10 이상, VS Code/터미널 가능
필요 라이브러리: 외부 라이브러리 없음. Python 표준 라이브러리만 사용.

실행 방법:
    python app.py
    브라우저에서 http://127.0.0.1:8000 접속

웹 구현 방식:
    Python 표준 라이브러리 http.server로 간단한 로컬 웹 서버를 실행하고,
    프론트엔드는 HTML/CSS/JavaScript, 백엔드는 JSON API로 구성한다.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from gradroad.data_loader import load_all
from gradroad.course_search import CourseSearchService
from gradroad.prerequisite_graph import PrerequisiteGraphService
from gradroad.graduation_optimizer import GraduationOptimizer
from gradroad.roadmap_generator import RoadmapGenerator
from gradroad.models import Course, RoadmapResult

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"
TEMPLATE_DIR = BASE_DIR / "templates"
SEASON_ORDER = {"spring": 0, "fall": 1, "both": 2}


def season_ko(season: str) -> str:
    season = season.lower()
    if season == "spring":
        return "1학기"
    if season == "fall":
        return "2학기"
    if season == "both":
        return "1,2학기"
    return season


def academic_year_from_semester(start_year: int, start_season: str, semester_no: int) -> int:
    if start_year < 1:
        return 1
    if semester_no <= 0:
        return start_year
    season_offset = 0 if start_season == "spring" else 1
    return start_year + (semester_no - 1 + season_offset) // 2


class GradRoadServices:
    """웹 요청에서 함께 사용하는 서비스 묶음."""

    def __init__(self) -> None:
        courses, prerequisites, requirements, offerings, _completed = load_all(DATA_DIR)
        self.courses: dict[str, Course] = courses
        self.prerequisites = prerequisites
        self.requirements = requirements
        self.offerings = offerings
        self.search = CourseSearchService(courses)
        self.graph = PrerequisiteGraphService(courses, prerequisites, offerings)
        self.optimizer = GraduationOptimizer(courses, requirements, self.graph)
        self.roadmap = RoadmapGenerator(courses, self.graph, self.optimizer)

    def course_to_dict(self, course: Course | str) -> dict[str, Any]:
        if isinstance(course, str):
            course = self.courses[course]
        seasons = sorted(self.offerings.get(course.course_id, set()), key=lambda x: SEASON_ORDER.get(x, 99))
        prereq_ids = sorted(self.graph.direct_prerequisites(course.course_id))
        return {
            "course_id": course.course_id,
            "course_name": course.course_name,
            "category": course.category,
            "credit": course.credit,
            "difficulty": course.difficulty,
            "keywords": course.keywords,
            "year_level": course.year_level,
            "display": course.display(),
            "offerings": seasons,
            "offerings_ko": ", ".join(season_ko(s) for s in seasons) if seasons else "미정",
            "prerequisites": prereq_ids,
            "prerequisite_names": [self.courses[x].course_name for x in prereq_ids if x in self.courses],
        }

    def parse_completed(self, payload: dict[str, Any]) -> set[str]:
        values = payload.get("completed")
        if values is None:
            return set()
        if not isinstance(values, list):
            raise ValueError("completed는 과목코드 문자열 배열이어야 합니다.")
        normalized = {str(x).strip().upper() for x in values if str(x).strip()}
        invalid = sorted(cid for cid in normalized if cid not in self.courses)
        if invalid:
            raise ValueError(f"존재하지 않는 이수 과목코드입니다: {', '.join(invalid)}")
        return normalized

    def roadmap_to_dict(self, result: RoadmapResult, start_year: int = 1) -> dict[str, Any]:
        semesters: list[dict[str, Any]] = []
        for sem in result.semesters:
            course_ids = list(sem.get("courses", []))
            courses = [self.course_to_dict(cid) for cid in course_ids]
            semester_no = int(sem.get("semester_no", 0))
            academic_year = academic_year_from_semester(start_year, str(sem.get("season", "spring")).lower(), semester_no)
            semesters.append(
                {
                    "semester_no": sem.get("semester_no"),
                    "academic_year": academic_year,
                    "season": sem.get("season"),
                    "season_ko": season_ko(str(sem.get("season", ""))),
                    "credit_sum": sum(c["credit"] for c in courses),
                    "courses": courses,
                }
            )
        return {
            "feasible": result.feasible,
            "message": result.message,
            "target_courses": [self.course_to_dict(cid) for cid in sorted(result.target_courses)],
            "semesters": semesters,
            "text": self.roadmap.roadmap_to_text(result, start_year=start_year),
            "start_year": start_year,
        }

    @staticmethod
    def _is_major_category(category: str) -> bool:
        return category in {"필수전공", "전공필수", "선택전공", "전공선택"}

    def major_direct_prerequisites(self, course_id: str) -> set[str]:
        return {
            prereq
            for prereq in self.graph.direct_prerequisites(course_id)
            if self._is_major_course(prereq, self.courses)
        }

    def major_transitive_prerequisites(self, course_id: str) -> set[str]:
        result: set[str] = set()
        stack = list(self.major_direct_prerequisites(course_id))
        while stack:
            current = stack.pop()
            if current in result:
                continue
            result.add(current)
            stack.extend(self.major_direct_prerequisites(current))
        return result

    def major_missing_prerequisites(self, course_id: str, completed: set[str], transitive: bool = False) -> set[str]:
        required = self.major_transitive_prerequisites(course_id) if transitive else self.major_direct_prerequisites(course_id)
        return required - completed

    @staticmethod
    def _is_major_course(course: Course | str, courses: dict[str, Course]) -> bool:
        if isinstance(course, Course):
            target = course
        else:
            target = courses.get(course)
        if target is None:
            return False
        return GradRoadServices._is_major_category(target.category)


SERVICES = GradRoadServices()


def json_bytes(obj: Any, status: int = 200) -> tuple[int, bytes, str]:
    return status, json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8"), "application/json; charset=utf-8"


def error_response(message: str, status: int = 400) -> tuple[int, bytes, str]:
    return json_bytes({"ok": False, "error": message}, status=status)


def ok_response(data: dict[str, Any] | list[Any]) -> tuple[int, bytes, str]:
    return json_bytes({"ok": True, "data": data})


def parse_int_payload(payload: dict[str, Any], key: str, default: int, minimum: int, maximum: int) -> int:
    raw = payload.get(key, default)
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key}는 정수여야 합니다.") from exc
    if value < minimum or value > maximum:
        raise ValueError(f"{key}는 {minimum} 이상 {maximum} 이하로 입력해야 합니다.")
    return value


def dispatch_api(path: str, payload: dict[str, Any] | None = None) -> tuple[int, bytes, str]:
    """API 라우팅 함수. 테스트하기 쉽도록 HTTP 핸들러와 분리했다."""
    payload = payload or {}

    if path == "/api/summary":
        courses = [SERVICES.course_to_dict(c) for c in sorted(SERVICES.courses.values(), key=lambda x: x.course_id)]
        edges = [
            {
                "from": req,
                "from_name": SERVICES.courses[req].course_name if req in SERVICES.courses else req,
                "to": cid,
                "to_name": SERVICES.courses[cid].course_name if cid in SERVICES.courses else cid,
            }
            for cid, reqs in SERVICES.prerequisites.items()
            for req in sorted(reqs)
        ]
        return ok_response(
            {
                "title": "GradRoad 전공 선수과목 기반 졸업 로드맵 설계 서비스",
                "course_count": len(SERVICES.courses),
                "requirements": SERVICES.requirements,
                "courses": courses,
                "edges": edges,
                "has_cycle": SERVICES.graph.has_cycle(),
                "topological_order": [SERVICES.course_to_dict(cid) for cid in SERVICES.graph.topological_order(include_flexible=False)],
                "team_modules": [
                    {
                        "member": "김유빈",
                        "role": "과목 검색 및 DB 관리",
                        "data_structures": ["Trie", "Hash Table"],
                        "algorithms": ["Trie Prefix Search", "KMP 문자열 탐색"],
                    },
                    {
                        "member": "김도훈",
                        "role": "선수과목 그래프 검증",
                        "data_structures": ["Directed Graph", "Queue/Stack"],
                        "algorithms": ["DFS Cycle Detection", "Topological Sort"],
                    },
                    {
                        "member": "신한서",
                        "role": "졸업요건 분석 및 과목 추천",
                        "data_structures": ["DP Table", "Priority Queue/Heap"],
                        "algorithms": ["0/1 Knapsack DP", "Greedy Priority Selection"],
                    },
                    {
                        "member": "신호진",
                        "role": "졸업 로드맵 생성",
                        "data_structures": ["Stack", "Set/Constraint Matrix"],
                        "algorithms": ["Backtracking", "Binary Search"],
                    },
                ],
            }
        )

    if path == "/api/search":
        prefix = str(payload.get("prefix", "")).strip()
        keyword = str(payload.get("keyword", "")).strip()
        prefix_results = SERVICES.search.autocomplete(prefix, limit=12) if prefix else []
        keyword_results = SERVICES.search.keyword_search(keyword, limit=12) if keyword else []
        return ok_response(
            {
                "prefix": prefix,
                "keyword": keyword,
                "autocomplete": [SERVICES.course_to_dict(c) for c in prefix_results],
                "keyword_search": [SERVICES.course_to_dict(c) for c in keyword_results],
                "algorithm_note": "Trie Prefix Search로 과목명 접두어를 찾고, KMP 문자열 탐색으로 과목명·키워드에서 검색어를 찾습니다.",
            }
        )

    if path == "/api/prerequisite":
        completed = SERVICES.parse_completed(payload)
        course_id = str(payload.get("course_id", "")).strip().upper()
        if course_id not in SERVICES.courses:
            return error_response("존재하지 않는 과목코드입니다.")
        direct = SERVICES.graph.direct_prerequisites(course_id)
        transitive = SERVICES.graph.transitive_prerequisites(course_id)
        missing_direct = SERVICES.graph.missing_prerequisites(course_id, completed, transitive=False)
        missing_all = SERVICES.graph.missing_prerequisites(course_id, completed, transitive=True)
        already_completed = course_id in completed
        available = not already_completed and not missing_direct
        if already_completed:
            availability_code = "already_completed"
            availability_title = "이미 이수한 과목"
            availability_message = "선택한 과목이 이수 과목에 포함되어 있어 현재 수강 대상에서 제외됩니다."
        elif missing_direct:
            missing_names = [
                SERVICES.courses[cid].course_name if cid in SERVICES.courses else cid
                for cid in sorted(missing_direct)
            ]
            availability_code = "missing_prerequisite"
            availability_title = "선수과목 미이수"
            availability_message = f"먼저 이수해야 할 직접 선수과목: {', '.join(missing_names)}"
        else:
            availability_code = "available"
            availability_title = "현재 수강 가능"
            availability_message = "아직 이수하지 않았고 직접 선수과목을 모두 충족했습니다."
        blocking_reasons = []
        if already_completed:
            blocking_reasons.append(
                {
                    "code": "already_completed",
                    "title": "이미 이수",
                    "detail": "이미 수강 완료한 과목은 추천 및 신규 수강 대상에서 제외됩니다.",
                }
            )
        if missing_direct:
            blocking_reasons.append(
                {
                    "code": "missing_prerequisite",
                    "title": "선수과목 미이수",
                    "detail": "직접 선수과목을 모두 이수해야 해당 과목을 수강할 수 있습니다.",
                }
            )
        topological_order = [
            SERVICES.course_to_dict(cid)
            for cid in SERVICES.graph.topological_order(include_flexible=False)
            if SERVICES._is_major_course(cid, SERVICES.courses)
        ]
        return ok_response(
            {
                "target": SERVICES.course_to_dict(course_id),
                "is_available_now": available,
                "is_already_completed": already_completed,
                "direct_prerequisites_satisfied": not missing_direct,
                "availability": {
                    "code": availability_code,
                    "title": availability_title,
                    "message": availability_message,
                    "blocking_reasons": blocking_reasons,
                },
                "completed": sorted(completed),
                "direct_prerequisites": [SERVICES.course_to_dict(cid) for cid in sorted(direct)],
                "all_prerequisites": [SERVICES.course_to_dict(cid) for cid in sorted(transitive)],
                "missing_direct": [SERVICES.course_to_dict(cid) for cid in sorted(missing_direct)],
                "missing_all": [SERVICES.course_to_dict(cid) for cid in sorted(missing_all)],
                "has_cycle": SERVICES.graph.has_cycle(),
                "topological_order": topological_order,
                "algorithm_note": "방향 그래프의 DFS Cycle Detection으로 순환 오류를 확인하고, Kahn 방식 위상정렬로 선수과목 순서를 계산합니다.",
            }
        )

    if path == "/api/recommend":
        completed = SERVICES.parse_completed(payload)
        season = str(payload.get("season", "spring")).strip().lower() or "spring"
        max_credit = parse_int_payload(payload, "max_credit", 18, 3, 24)
        if season not in {"spring", "fall"}:
            return error_response("season은 spring 또는 fall이어야 합니다.")
        rec = SERVICES.optimizer.recommend_for_semester(completed, season=season, max_credit=max_credit)
        greedy = [
            {"score": score, "course": SERVICES.course_to_dict(course)}
            for score, course in rec["greedy"]
        ]
        dp = [
            {"score": score, "course": SERVICES.course_to_dict(course)}
            for score, course in rec["dp"]
        ]
        return ok_response(
            {
                "season": season,
                "season_ko": season_ko(season),
                "max_credit": max_credit,
                "earned": rec["earned"],
                "deficits": rec["deficits"],
                "available": [SERVICES.course_to_dict(c) for c in rec["available"]],
                "greedy": greedy,
                "dp": dp,
                "dp_credit_sum": sum(item["course"]["credit"] for item in dp),
                "dp_score_sum": sum(item["score"] for item in dp),
                "algorithm_note": "Priority Queue/Heap 기반 Greedy 추천과 DP Table 기반 0/1 Knapsack으로 학점 제한 내 추천 조합을 계산합니다.",
            }
        )

    if path == "/api/roadmap":
        completed = SERVICES.parse_completed(payload)
        start_season = str(payload.get("start_season", "spring")).strip().lower() or "spring"
        max_semesters = parse_int_payload(payload, "max_semesters", 4, 1, 8)
        max_credit = parse_int_payload(payload, "max_credit", 18, 3, 24)
        start_year = parse_int_payload(payload, "start_year", 1, 1, 4)
        if start_season not in {"spring", "fall"}:
            return error_response("start_season은 spring 또는 fall이어야 합니다.")
        result = SERVICES.roadmap.make_roadmap(
            completed,
            start_season=start_season,
            max_semesters=max_semesters,
            max_credit=max_credit,
        )
        data = SERVICES.roadmap_to_dict(result, start_year=start_year)
        data.update(
            {
                "start_season": start_season,
                "start_season_ko": season_ko(start_season),
                "max_semesters": max_semesters,
                "max_credit": max_credit,
                "algorithm_note": "Backtracking으로 학기별 과목 배치를 탐색하고, Binary Search로 최소 졸업 가능 학기를 찾습니다.",
            }
        )
        return ok_response(data)

    return error_response("존재하지 않는 API 경로입니다.", status=404)


class GradRoadHandler(BaseHTTPRequestHandler):
    server_version = "GradRoadWeb/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {self.address_string()} {fmt % args}")

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/":
            html = (TEMPLATE_DIR / "index.html").read_bytes()
            self._send(200, html, "text/html; charset=utf-8")
            return
        if path.startswith("/static/"):
            rel = path.removeprefix("/static/").replace("..", "")
            target = STATIC_DIR / rel
            if target.exists() and target.is_file():
                ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
                if target.suffix == ".css":
                    ctype = "text/css; charset=utf-8"
                elif target.suffix == ".js":
                    ctype = "application/javascript; charset=utf-8"
                self._send(200, target.read_bytes(), ctype)
                return
        if path.startswith("/api/"):
            try:
                status, body, ctype = dispatch_api(path, {})
            except Exception as exc:
                status, body, ctype = error_response(f"서버 오류: {exc}", status=500)
            self._send(status, body, ctype)
            return
        self._send(404, b"Not Found", "text/plain; charset=utf-8")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if not path.startswith("/api/"):
            self._send(404, b"Not Found", "text/plain; charset=utf-8")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8") if length else "{}"
            payload = json.loads(raw or "{}")
            if not isinstance(payload, dict):
                raise ValueError("JSON 객체만 허용됩니다.")
            status, body, ctype = dispatch_api(path, payload)
        except Exception as exc:
            status, body, ctype = error_response(f"요청 처리 오류: {exc}", status=400)
        self._send(status, body, ctype)


def run_self_test() -> None:
    """주요 API와 알고리즘 모듈이 정상 응답하는지 빠르게 확인한다."""
    base_completed: list[str] = []
    test_cases = [
        ("/api/summary", {}),
        ("/api/search", {"prefix": "알고", "keyword": "데이터"}),
        ("/api/prerequisite", {"course_id": "CSE136", "completed": base_completed}),
        ("/api/recommend", {"season": "spring", "max_credit": 18, "completed": base_completed}),
        ("/api/roadmap", {"start_season": "spring", "max_semesters": 4, "max_credit": 18, "completed": base_completed}),
    ]
    print("GradRoad Web App self-test")
    for path, payload in test_cases:
        status, body, _ctype = dispatch_api(path, payload)
        data = json.loads(body.decode("utf-8"))
        if status != 200 or not data.get("ok"):
            raise RuntimeError(f"{path} 테스트 실패: {data}")
        print(f"[OK] {path} ({len(body)} bytes)")
    prereq_status_cases = [
        ("missing_prerequisite", {"course_id": "CSE136", "completed": []}),
        ("already_completed", {"course_id": "CSE136", "completed": ["CSE136"]}),
        ("available", {"course_id": "CSE136", "completed": ["CSE117", "CSE122"]}),
    ]
    for expected_code, payload in prereq_status_cases:
        status, body, _ctype = dispatch_api("/api/prerequisite", payload)
        data = json.loads(body.decode("utf-8"))
        actual_code = data["data"]["availability"]["code"]
        if status != 200 or actual_code != expected_code:
            raise RuntimeError(f"/api/prerequisite 상태 판정 실패: expected={expected_code}, actual={actual_code}")
    print("모든 테스트 통과")


def main() -> None:
    parser = argparse.ArgumentParser(description="GradRoad 간단 웹 서비스")
    parser.add_argument("--host", default="127.0.0.1", help="서버 호스트, 기본값 127.0.0.1")
    parser.add_argument("--port", type=int, default=8000, help="서버 포트, 기본값 8000")
    parser.add_argument("--test", action="store_true", help="서버 실행 전 API/알고리즘 자체 테스트만 수행")
    args = parser.parse_args()
    if args.test:
        run_self_test()
        return
    server = ThreadingHTTPServer((args.host, args.port), GradRoadHandler)
    print("=" * 72)
    print("GradRoad Web App 실행 중")
    print(f"접속 주소: http://{args.host}:{args.port}")
    print("종료하려면 Ctrl+C를 누르세요.")
    print("=" * 72)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n서버를 종료합니다.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
