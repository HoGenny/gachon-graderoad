"""CSV 데이터 로딩 모듈.

실행 환경: Python 3.10 이상
필요 라이브러리: 표준 라이브러리(csv, pathlib)만 사용
Input 데이터 출처: data/data_source.txt 참고. 팀 자체 제작 더미 데이터.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, Set, Tuple

from .models import Course


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"데이터 파일을 찾을 수 없습니다: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_courses(data_dir: Path) -> Dict[str, Course]:
    rows = read_csv(data_dir / "courses.csv")
    courses: Dict[str, Course] = {}
    for row in rows:
        course = Course(
            course_id=row["course_id"].strip(),
            course_name=row["course_name"].strip(),
            category=row["category"].strip(),
            credit=int(row["credit"]),
            difficulty=int(row["difficulty"]),
            keywords=row["keywords"].strip(),
            year_level=int(row["year_level"]),
        )
        courses[course.course_id] = course
    return courses


def load_prerequisites(data_dir: Path) -> Dict[str, Set[str]]:
    """course_id -> 선수과목 set."""
    rows = read_csv(data_dir / "prerequisites.csv")
    prerequisites: Dict[str, Set[str]] = {}
    for row in rows:
        course_id = row["course_id"].strip()
        prereq = row["prerequisite_id"].strip()
        if not course_id or not prereq:
            continue
        prerequisites.setdefault(course_id, set()).add(prereq)
    return prerequisites


def load_requirements(data_dir: Path) -> Dict[str, int]:
    rows = read_csv(data_dir / "requirements.csv")
    return {row["requirement_type"].strip(): int(row["required_credit"]) for row in rows}


def load_offerings(data_dir: Path) -> Dict[str, Set[str]]:
    rows = read_csv(data_dir / "offerings.csv")
    offerings: Dict[str, Set[str]] = {}
    for row in rows:
        course_id = row["course_id"].strip()
        season = row["semester"].strip().lower()
        offerings.setdefault(course_id, set()).add(season)
    return offerings


def load_completed(data_dir: Path, student_id: str = "S001") -> Set[str]:
    """초기 이수 과목은 비워 둔다.

    기준 학기 선택 시 프론트엔드가 이전 학기 과목을 자동 선택한다.
    """
    return set()


def load_all(data_dir: Path) -> Tuple[Dict[str, Course], Dict[str, Set[str]], Dict[str, int], Dict[str, Set[str]], Set[str]]:
    return (
        load_courses(data_dir),
        load_prerequisites(data_dir),
        load_requirements(data_dir),
        load_offerings(data_dir),
        load_completed(data_dir),
    )
