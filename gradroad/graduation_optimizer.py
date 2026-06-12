"""신한서 담당: 졸업요건 분석 및 과목 우선순위 추천 모듈.

사용 자료구조 1: DP Table
사용 자료구조 2: Priority Queue / Heap
사용 알고리즘 1: 0/1 Knapsack Dynamic Programming
사용 알고리즘 2: Greedy Priority Selection
"""
from __future__ import annotations

from collections import defaultdict
import heapq
from typing import Dict, Iterable, Set, Tuple

from .models import Course
from .prerequisite_graph import PrerequisiteGraphService


class GraduationOptimizer:
    """학생의 이수 현황을 분석하고 이번 학기 추천 과목을 계산한다."""

    def __init__(self, courses: Dict[str, Course], requirements: Dict[str, int], graph_service: PrerequisiteGraphService):
        self.courses = courses
        self.requirements = requirements
        self.graph_service = graph_service

    def _canonical_category(self, category: str) -> str:
        if category in {"필수전공", "전공필수"}:
            return "필수전공"
        if category in {"선택전공", "전공선택"}:
            return "선택전공"
        return category

    def earned_credits(self, completed: Set[str]) -> Dict[str, int]:
        earned = defaultdict(int)
        for cid in completed:
            course = self.courses.get(cid)
            if not course:
                continue
            category = self._canonical_category(course.category)
            earned[category] += course.credit
            earned["총전공학점"] += course.credit
        return dict(earned)

    def deficits(self, completed: Set[str]) -> Dict[str, int]:
        earned = self.earned_credits(completed)
        return {key: max(0, required - earned.get(key, 0)) for key, required in self.requirements.items()}

    def priority_score(self, course_id: str, completed: Set[str]) -> int:
        """추천 점수: 필수 여부 + 후속과목 해금 수 + 학년 적합도 - 난이도 부담."""
        course = self.courses[course_id]
        mandatory = 60 if self._canonical_category(course.category) == "필수전공" else 25
        unlock = self.graph_service.unlock_count(course_id) * 8
        year_bonus = max(0, 5 - abs(course.year_level - 3)) * 2
        difficulty_penalty = course.difficulty * 3
        already_done_penalty = 1000 if course_id in completed else 0
        return mandatory + unlock + year_bonus - difficulty_penalty - already_done_penalty

    def greedy_priority_recommendation(self, candidate_ids: Iterable[str], completed: Set[str], limit: int = 8) -> list[Tuple[int, Course]]:
        """알고리즘: Greedy Priority Selection.

        자료구조: Priority Queue/Heap을 사용하여 점수가 높은 과목을 먼저 추출한다.
        """
        heap: list[tuple[int, str]] = []
        for cid in candidate_ids:
            score = self.priority_score(cid, completed)
            heapq.heappush(heap, (-score, cid))

        selected: list[Tuple[int, Course]] = []
        while heap and len(selected) < limit:
            neg_score, cid = heapq.heappop(heap)
            selected.append((-neg_score, self.courses[cid]))
        return selected

    def knapsack_dp(self, candidate_ids: Iterable[str], completed: Set[str], max_credit: int) -> list[Tuple[int, Course]]:
        """알고리즘: 0/1 Knapsack DP.

        자료구조: DP Table. 학기당 최대 학점 안에서 추천 점수 합이 최대인 과목 조합을 찾는다.
        """
        candidates = list(candidate_ids)
        n = len(candidates)
        # dp[i][w] = i개 과목까지 고려했을 때 w학점 이내에서 얻을 수 있는 최대 점수
        dp = [[0] * (max_credit + 1) for _ in range(n + 1)]
        keep = [[False] * (max_credit + 1) for _ in range(n + 1)]

        for i, cid in enumerate(candidates, start=1):
            course = self.courses[cid]
            value = self.priority_score(cid, completed)
            weight = course.credit
            for w in range(max_credit + 1):
                dp[i][w] = dp[i - 1][w]
                if weight <= w and dp[i - 1][w - weight] + value > dp[i][w]:
                    dp[i][w] = dp[i - 1][w - weight] + value
                    keep[i][w] = True

        selected: list[str] = []
        w = max_credit
        for i in range(n, 0, -1):
            if keep[i][w]:
                cid = candidates[i - 1]
                selected.append(cid)
                w -= self.courses[cid].credit
        selected.reverse()
        return [(self.priority_score(cid, completed), self.courses[cid]) for cid in selected]

    def recommend_for_semester(self, completed: Set[str], season: str, max_credit: int = 18) -> dict[str, object]:
        available = self.graph_service.available_courses(completed, season)
        greedy = self.greedy_priority_recommendation(available, completed, limit=8)
        dp = self.knapsack_dp(available, completed, max_credit=max_credit)
        return {
            "earned": self.earned_credits(completed),
            "deficits": self.deficits(completed),
            "available": [self.courses[cid] for cid in available],
            "greedy": greedy,
            "dp": dp,
        }
