"""신호진 담당: 최종 졸업 로드맵 생성 및 대안 비교 모듈.

사용 자료구조 1: Stack
사용 자료구조 2: Set / Constraint Matrix
사용 알고리즘 1: Backtracking
사용 알고리즘 2: Binary Search
"""
from __future__ import annotations

from typing import Dict, Set

from .models import Course, RoadmapResult
from .prerequisite_graph import PrerequisiteGraphService
from .graduation_optimizer import GraduationOptimizer


class RoadmapGenerator:
    def __init__(
        self,
        courses: Dict[str, Course],
        graph_service: PrerequisiteGraphService,
        optimizer: GraduationOptimizer,
    ):
        self.courses = courses
        self.graph_service = graph_service
        self.optimizer = optimizer

    @staticmethod
    def semester_sequence(start_season: str, count: int) -> list[str]:
        start = start_season.lower()
        if start not in {"spring", "fall"}:
            raise ValueError("start_season은 spring 또는 fall이어야 합니다.")
        seq = []
        cur = start
        for _ in range(count):
            seq.append(cur)
            cur = "fall" if cur == "spring" else "spring"
        return seq

    def _topological_index(self) -> dict[str, int]:
        return {
            cid: i
            for i, cid in enumerate(self.graph_service.topological_order(include_flexible=False))
        }

    def _include_prerequisites(self, selected: Set[str], completed: Set[str]) -> Set[str]:
        """선택 과목의 미이수 선수과목을 목표 과목 집합에 자동 포함한다."""
        changed = True
        while changed:
            changed = False
            for cid in list(selected):
                for req in self.graph_service.direct_prerequisites(cid):
                    if req not in completed and req not in selected:
                        selected.add(req)
                        changed = True
        return selected

    @staticmethod
    def _canonical_category(category: str) -> str:
        if category in {"필수전공", "전공필수"}:
            return "필수전공"
        if category in {"선택전공", "전공선택"}:
            return "선택전공"
        return category

    def _credit_sum(self, course_ids: Set[str]) -> int:
        return sum(self.courses[cid].credit for cid in course_ids if cid in self.courses)

    def _category_credit_sum(self, course_ids: Set[str], category: str) -> int:
        return sum(
            self.courses[cid].credit
            for cid in course_ids
            if cid in self.courses and self._canonical_category(self.courses[cid].category) == category
        )

    def select_goal_courses(self, completed: Set[str]) -> Set[str]:
        """졸업요건 충족에 필요한 목표 과목 집합을 선정한다."""
        topo = self._topological_index()
        selected: Set[str] = set()

        def candidate_sort_key(course: Course, category: str) -> tuple:
            if category == "필수전공":
                return (topo.get(course.course_id, 999), course.year_level, course.difficulty, course.course_id)
            if category == "선택전공":
                return (
                    -self.optimizer.priority_score(course.course_id, completed),
                    topo.get(course.course_id, 999),
                    course.year_level,
                    course.course_id,
                )
            return (course.year_level, course.difficulty, topo.get(course.course_id, 999), course.course_id)

        earned = self.optimizer.earned_credits(completed)
        for category in ["기초교양", "융합교양", "계열교양", "필수전공", "선택전공"]:
            required = self.optimizer.requirements.get(category, 0)
            if required <= 0:
                continue
            need = max(0, required - earned.get(category, 0) - self._category_credit_sum(selected, category))
            candidates = [
                course for course in self.courses.values()
                if self._canonical_category(course.category) == category
                and course.course_id not in completed
                and course.course_id not in selected
            ]
            candidates.sort(key=lambda course: candidate_sort_key(course, category))
            for course in candidates:
                if need <= 0:
                    break
                selected.add(course.course_id)
                need -= course.credit

        selected = self._include_prerequisites(selected, completed)

        total_required = self.optimizer.requirements.get("총전공학점", 0)
        total_need = max(0, total_required - self._credit_sum(completed | selected))
        if total_need > 0:
            remaining_candidates = [
                cid for cid in self.courses
                if cid not in completed and cid not in selected and self.courses[cid].credit > 0
            ]
            remaining_candidates.sort(
                key=lambda cid: (
                    -self.optimizer.priority_score(cid, completed | selected),
                    topo.get(cid, 999),
                    self.courses[cid].year_level,
                    self.courses[cid].course_id,
                )
            )
            for cid in remaining_candidates:
                if total_need <= 0:
                    break
                selected.add(cid)
                selected = self._include_prerequisites(selected, completed)
                total_need = max(0, total_required - self._credit_sum(completed | selected))

        return self._include_prerequisites(selected, completed)

    def _feasible_subsets(self, candidates: list[str], max_credit: int, completed: Set[str], limit: int = 10) -> list[list[str]]:
        """한 학기에 넣을 수 있는 과목 부분집합을 만든다.

        모든 조합을 만들면 지수적으로 폭증하므로, 추천점수·위상순서·난이도
        기준의 대표 묶음만 백트래킹 후보로 사용한다.
        """
        if not candidates:
            return []

        topo = self._topological_index()
        ordered = sorted(
            candidates,
            key=lambda cid: (
                -self.optimizer.priority_score(cid, completed),
                -self.graph_service.unlock_count(cid),
                topo.get(cid, 999),
                self.courses[cid].difficulty,
                cid,
            ),
        )
        seen: dict[tuple[str, ...], list[str]] = {}

        def add_subset(subset: list[str]) -> None:
            unique = tuple(sorted(set(subset), key=lambda cid: topo.get(cid, 999)))
            if not unique:
                return
            credits = sum(self.courses[cid].credit for cid in unique)
            if credits <= max_credit and unique not in seen:
                seen[unique] = list(unique)

        def greedy_pack(seed_order: list[str]) -> list[str]:
            pack: list[str] = []
            credit_sum = 0
            for cid in seed_order:
                credit = self.courses[cid].credit
                if credit_sum + credit <= max_credit:
                    pack.append(cid)
                    credit_sum += credit
            return pack

        add_subset(greedy_pack(ordered))
        add_subset(greedy_pack(sorted(ordered, key=lambda cid: topo.get(cid, 999))))
        add_subset(greedy_pack(sorted(ordered, key=lambda cid: (self.courses[cid].difficulty, topo.get(cid, 999)))))
        add_subset(greedy_pack(sorted(ordered, key=lambda cid: (-self.graph_service.unlock_count(cid), topo.get(cid, 999)))))

        for start, cid in enumerate(ordered[:8]):
            rotated = [cid] + [other for other in ordered if other != cid]
            add_subset(greedy_pack(rotated))

        for cid in ordered[:12]:
            add_subset([cid])

        subsets = list(seen.values())
        subsets.sort(
            key=lambda subset: (
                sum(self.courses[cid].credit for cid in subset),
                sum(self.optimizer.priority_score(cid, completed) for cid in subset),
                sum(self.graph_service.unlock_count(cid) for cid in subset),
                -sum(self.courses[cid].difficulty for cid in subset),
            ),
            reverse=True,
        )
        return subsets[:limit]

    def _build_constraint_matrix(self, target_ids: Set[str], seasons: list[str]) -> dict[tuple[str, int], bool]:
        """자료구조: Constraint Matrix. (과목, 학기)별 개설 가능 여부를 저장한다."""
        return {
            (cid, idx): self.graph_service.is_offered(cid, season)
            for idx, season in enumerate(seasons)
            for cid in target_ids
        }

    def generate_roadmap_backtracking(
        self,
        target_ids: Set[str],
        completed: Set[str],
        start_season: str,
        max_semesters: int,
        max_credit: int,
    ) -> RoadmapResult:
        """알고리즘: Backtracking.

        선수과목, 개설학기, 최대학점 제약조건을 만족하도록 학기별 과목 배치를 탐색한다.
        """
        seasons = self.semester_sequence(start_season, max_semesters)
        constraint_matrix = self._build_constraint_matrix(target_ids, seasons)
        topo = self._topological_index()
        target_ids = set(sorted(target_ids, key=lambda cid: topo.get(cid, 999)))

        plan: list[dict] = []
        # 자료구조: Stack. 백트래킹의 현재 선택 상태를 push/pop으로 관리한다.
        state_stack: list[tuple[int, list[str]]] = []
        failed_states: set[tuple[int, tuple[str, ...]]] = set()
        checked_states = 0
        max_checked_states = 3000

        def dfs(sem_idx: int, completed_now: Set[str], remaining: Set[str]) -> bool:
            nonlocal checked_states
            if not remaining:
                return True
            if sem_idx >= max_semesters:
                return False
            checked_states += 1
            if checked_states > max_checked_states:
                return False
            state_key = (sem_idx, tuple(sorted(remaining)))
            if state_key in failed_states:
                return False
            remaining_credit = self._credit_sum(remaining)
            remaining_capacity = max_credit * (max_semesters - sem_idx)
            if remaining_credit > remaining_capacity:
                failed_states.add(state_key)
                return False
            if any(
                not any(constraint_matrix.get((cid, idx), False) for idx in range(sem_idx, max_semesters))
                for cid in remaining
            ):
                failed_states.add(state_key)
                return False

            candidates = [
                cid for cid in sorted(remaining, key=lambda x: topo.get(x, 999))
                if self.graph_service.direct_prerequisites(cid).issubset(completed_now)
                and constraint_matrix.get((cid, sem_idx), False)
            ]
            subsets = self._feasible_subsets(candidates, max_credit, completed_now)

            if not subsets:
                plan.append({"semester_no": sem_idx + 1, "season": seasons[sem_idx], "courses": []})
                state_stack.append((sem_idx, []))
                if dfs(sem_idx + 1, completed_now, remaining):
                    return True
                state_stack.pop()
                plan.pop()
                failed_states.add(state_key)
                return False

            for subset in subsets:
                plan.append({"semester_no": sem_idx + 1, "season": seasons[sem_idx], "courses": subset})
                state_stack.append((sem_idx, subset))
                if dfs(sem_idx + 1, completed_now | set(subset), remaining - set(subset)):
                    return True
                state_stack.pop()
                plan.pop()
            failed_states.add(state_key)
            return False

        feasible = dfs(0, set(completed), set(target_ids))
        message = "목표 학기 내 졸업 로드맵 생성 성공" if feasible else "목표 학기 내 조건을 만족하는 로드맵을 찾지 못했습니다."
        return RoadmapResult(feasible=feasible, semesters=plan.copy(), target_courses=target_ids, message=message)

    def can_finish(self, target_ids: Set[str], completed: Set[str], start_season: str, semester_count: int, max_credit: int) -> bool:
        return self.generate_roadmap_backtracking(target_ids, completed, start_season, semester_count, max_credit).feasible

    def find_minimum_semesters(
        self,
        target_ids: Set[str],
        completed: Set[str],
        start_season: str,
        max_credit: int,
        high: int = 8,
    ) -> int | None:
        """알고리즘: Binary Search. 졸업 가능 최소 학기 수를 탐색한다."""
        low, answer = 1, None
        while low <= high:
            mid = (low + high) // 2
            if self.can_finish(target_ids, completed, start_season, mid, max_credit):
                answer = mid
                high = mid - 1
            else:
                low = mid + 1
        return answer

    def make_roadmap(self, completed: Set[str], start_season: str = "spring", max_semesters: int = 4, max_credit: int = 18) -> RoadmapResult:
        target_ids = self.select_goal_courses(completed)
        result = self.generate_roadmap_backtracking(target_ids, completed, start_season, max_semesters, max_credit)
        if result.feasible:
            min_sem = self.find_minimum_semesters(target_ids, completed, start_season, max_credit, high=max_semesters)
            result.message += f" / 최소 필요 학기: {min_sem}학기"
        else:
            min_sem = self.find_minimum_semesters(target_ids, completed, start_season, max_credit, high=8)
            if min_sem:
                result.message += f" / {max_semesters}학기는 어렵지만 최소 {min_sem}학기면 가능합니다."
                alternative = self.generate_roadmap_backtracking(target_ids, completed, start_season, min_sem, max_credit)
                if alternative.feasible:
                    result.semesters = alternative.semesters
        return result

    def roadmap_to_text(self, result: RoadmapResult, start_year: int = 1) -> str:
        lines: list[str] = []
        lines.append(result.message)
        lines.append("목표 과목: " + ", ".join(sorted(result.target_courses)))
        if not result.semesters:
            return "\n".join(lines)
        for sem in result.semesters:
            season_ko = "1학기" if sem["season"] == "spring" else "2학기"
            courses = sem["courses"]
            credit_sum = sum(self.courses[cid].credit for cid in courses)
            semester_no = int(sem.get("semester_no", 0))
            season_offset = 0 if sem["season"] == "spring" else 1
            academic_year = start_year + (semester_no - 1 + season_offset) // 2 if semester_no > 0 else start_year
            lines.append(f"\n[{academic_year}학년 {season_ko}({sem['semester_no']}번째 학기) / {credit_sum}학점]")
            if not courses:
                lines.append("- 배치 가능한 목표 과목 없음")
            for cid in courses:
                lines.append("- " + self.courses[cid].display())
        return "\n".join(lines)
