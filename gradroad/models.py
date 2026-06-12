"""GradRoad 공통 데이터 모델."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Set


@dataclass(frozen=True)
class Course:
    """전공 과목 1개를 표현하는 자료형."""

    course_id: str
    course_name: str
    category: str
    credit: int
    difficulty: int
    keywords: str
    year_level: int

    def display(self) -> str:
        return f"{self.course_id} | {self.course_name} | {self.category} | {self.credit}학점 | 난이도 {self.difficulty}"


@dataclass
class RoadmapResult:
    """로드맵 생성 결과."""

    feasible: bool
    semesters: list[dict]
    target_courses: Set[str]
    message: str
