"""김도훈 담당: 선수과목 그래프 검증 모듈.

사용 자료구조 1: Directed Graph / Adjacency List
사용 자료구조 2: Queue, Stack
사용 알고리즘 1: DFS Cycle Detection
사용 알고리즘 2: Topological Sort(Kahn Algorithm)
"""
from __future__ import annotations

from collections import defaultdict, deque
from typing import Dict, Iterable, List, Set

from .models import Course


class PrerequisiteGraphService:
    """전공 과목의 선수과목 관계를 방향 그래프로 관리한다."""

    def __init__(self, courses: Dict[str, Course], prerequisites: Dict[str, Set[str]], offerings: Dict[str, Set[str]]):
        self.courses = courses
        # 자료구조: Directed Graph - 역방향 인접 리스트. course -> prereq set
        self.prerequisites: Dict[str, Set[str]] = {cid: set(reqs) for cid, reqs in prerequisites.items()}
        # 자료구조: Directed Graph - 정방향 인접 리스트. prereq -> unlock courses
        self.graph: Dict[str, List[str]] = defaultdict(list)
        for course_id in courses:
            self.graph.setdefault(course_id, [])
        for course_id, prereqs in self.prerequisites.items():
            for prereq in prereqs:
                self.graph[prereq].append(course_id)
        self.offerings = offerings

    @staticmethod
    def _is_flexible_course(course_category: str | None) -> bool:
        return (course_category or "").strip() == "융합교양"

    def has_cycle(self) -> bool:
        """알고리즘: DFS Cycle Detection. 방향 그래프의 순환 선수과목 오류를 검사한다."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {cid: WHITE for cid in self.courses}

        def dfs(start: str) -> bool:
            # 자료구조: Stack. 재귀 대신 명시적 스택으로 DFS 상태를 관리한다.
            stack = [(start, iter(self.graph[start]))]
            color[start] = GRAY
            while stack:
                node, children_iter = stack[-1]
                try:
                    nxt = next(children_iter)
                    if color[nxt] == GRAY:
                        return True
                    if color[nxt] == WHITE:
                        color[nxt] = GRAY
                        stack.append((nxt, iter(self.graph[nxt])))
                except StopIteration:
                    color[node] = BLACK
                    stack.pop()
            return False

        for cid in self.courses:
            if color[cid] == WHITE and dfs(cid):
                return True
        return False

    def topological_order(self, include_flexible: bool = True) -> list[str]:
        """알고리즘: Topological Sort. 선수과목이 먼저 나오도록 전체 수강 순서를 생성한다."""
        if include_flexible:
            ordered_ids = set(self.courses.keys())
        else:
            ordered_ids = {
                cid for cid, c in self.courses.items()
                if not self._is_flexible_course(c.category)
            }

        indegree = {cid: 0 for cid in self.courses}
        for prereq, next_courses in self.graph.items():
            if not include_flexible and self._is_flexible_course(self.courses[prereq].category):
                continue
            for nxt in next_courses:
                if nxt not in ordered_ids:
                    continue
                indegree[nxt] += 1

        # 자료구조: Queue. 진입 차수 0인 과목을 순서대로 처리한다.
        q = deque(sorted([cid for cid, deg in indegree.items() if cid in ordered_ids and deg == 0]))
        order: list[str] = []
        while q:
            cur = q.popleft()
            order.append(cur)
            if not include_flexible and self._is_flexible_course(self.courses[cur].category):
                continue
            for nxt in sorted(self.graph[cur]):
                if nxt not in ordered_ids:
                    continue
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    q.append(nxt)
        if len(order) != len(ordered_ids):
            raise ValueError("선수과목 그래프에 순환이 있어 위상정렬을 완료할 수 없습니다.")
        return order

    def unlock_count(self, course_id: str) -> int:
        return len(self.graph.get(course_id, []))

    def direct_prerequisites(self, course_id: str) -> Set[str]:
        return set(self.prerequisites.get(course_id, set()))

    def transitive_prerequisites(self, course_id: str) -> Set[str]:
        """특정 과목에 필요한 모든 직간접 선수과목을 DFS로 수집한다."""
        result: Set[str] = set()
        stack = list(self.direct_prerequisites(course_id))
        while stack:
            cur = stack.pop()
            if cur in result:
                continue
            result.add(cur)
            stack.extend(self.direct_prerequisites(cur))
        return result

    def missing_prerequisites(self, course_id: str, completed: Set[str], transitive: bool = False) -> Set[str]:
        required = self.transitive_prerequisites(course_id) if transitive else self.direct_prerequisites(course_id)
        return required - completed

    def is_available(self, course_id: str, completed: Set[str], season: str | None = None) -> bool:
        if course_id in completed:
            return False
        if not self.direct_prerequisites(course_id).issubset(completed):
            return False
        if season is not None and not self.is_offered(course_id, season):
            return False
        return True

    def is_offered(self, course_id: str, season: str) -> bool:
        seasons = self.offerings.get(course_id, set())
        season = season.lower()
        return "both" in seasons or season in seasons

    def available_courses(self, completed: Set[str], season: str | None = None) -> list[str]:
        return [cid for cid in self.topological_order() if self.is_available(cid, completed, season)]

    def format_course_list(self, course_ids: Iterable[str]) -> str:
        return "\n".join(f"- {self.courses[cid].display()}" for cid in course_ids if cid in self.courses)
