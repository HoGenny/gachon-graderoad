"""김유빈 담당: 과목 검색 및 과목 DB 관리 모듈.

사용 자료구조 1: Trie
사용 자료구조 2: Hash Table(dict)
사용 알고리즘 1: Trie Prefix Search
사용 알고리즘 2: KMP 문자열 탐색
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List

from .models import Course


def normalize(text: str) -> str:
    """검색 편의를 위해 공백 제거 + 소문자화."""
    return "".join(text.lower().split())


@dataclass
class TrieNode:
    # 자료구조: Trie Node. children은 문자 -> 다음 TrieNode를 저장하는 Hash Table이다.
    children: Dict[str, "TrieNode"] = field(default_factory=dict)
    course_ids: List[str] = field(default_factory=list)
    is_end: bool = False


class CourseSearchService:
    """과목명 자동완성, 키워드 검색, 과목코드 조회 서비스."""

    def __init__(self, courses: Dict[str, Course]):
        # 자료구조: Hash Table. 과목코드로 과목 정보를 평균 O(1)에 조회한다.
        self.course_table: Dict[str, Course] = courses
        # 자료구조: Trie. 과목명 접두어 검색에 사용한다.
        self.trie_root = TrieNode()
        for course in courses.values():
            self._insert_course_name(course)

    def _insert_course_name(self, course: Course) -> None:
        node = self.trie_root
        for ch in normalize(course.course_name):
            node = node.children.setdefault(ch, TrieNode())
            if course.course_id not in node.course_ids:
                node.course_ids.append(course.course_id)
        node.is_end = True

    def get_course(self, course_id: str) -> Course | None:
        # 알고리즘: Hash Search. Hash Table(dict)의 key 기반 조회를 사용한다.
        return self.course_table.get(course_id.strip().upper())

    def autocomplete(self, prefix: str, limit: int = 10) -> list[Course]:
        """알고리즘: Trie Prefix Search. 접두어를 따라 내려간 뒤 후보 과목을 반환한다."""
        node = self.trie_root
        for ch in normalize(prefix):
            if ch not in node.children:
                return []
            node = node.children[ch]
        ids = node.course_ids[:limit]
        return [self.course_table[cid] for cid in ids]

    @staticmethod
    def build_lps(pattern: str) -> list[int]:
        """KMP 전처리: LPS(Longest Prefix Suffix) 배열 생성."""
        lps = [0] * len(pattern)
        length = 0
        i = 1
        while i < len(pattern):
            if pattern[i] == pattern[length]:
                length += 1
                lps[i] = length
                i += 1
            elif length:
                length = lps[length - 1]
            else:
                lps[i] = 0
                i += 1
        return lps

    @classmethod
    def kmp_contains(cls, text: str, pattern: str) -> bool:
        """알고리즘: KMP 문자열 탐색. text 안에 pattern이 존재하는지 확인한다."""
        text = normalize(text)
        pattern = normalize(pattern)
        if not pattern:
            return True
        if not text:
            return False
        lps = cls.build_lps(pattern)
        i = j = 0
        while i < len(text):
            if text[i] == pattern[j]:
                i += 1
                j += 1
                if j == len(pattern):
                    return True
            elif j:
                j = lps[j - 1]
            else:
                i += 1
        return False

    def keyword_search(self, keyword: str, limit: int = 10) -> list[Course]:
        """과목명+키워드 필드에서 KMP로 문자열을 탐색한다."""
        results: list[Course] = []
        for course in self.course_table.values():
            haystack = f"{course.course_name} {course.keywords} {course.category}"
            if self.kmp_contains(haystack, keyword):
                results.append(course)
        return results[:limit]

    def list_courses(self, course_ids: Iterable[str]) -> list[Course]:
        return [self.course_table[cid] for cid in course_ids if cid in self.course_table]
