"""datasource/course_ds.py"""
from __future__ import annotations

from web3.contract import Contract

from python.datasource.base import BaseDataSource
from python.models.types import CourseInfo


class CourseDataSource(BaseDataSource):
    def __init__(self, contract: Contract):
        super().__init__(contract)

    def create_course(self, course_id: str, name: str, professor_id: int) -> dict:
        if not course_id or not name:
            raise ValueError("course_id and name are required")
        if professor_id <= 0:
            raise ValueError("professor_id must be positive")
        return self._tx(self._contract.functions.createCourse(course_id, name, professor_id))

    def update_course(self, course_id: str, name: str) -> dict:
        if not course_id or not name:
            raise ValueError("course_id and name are required")
        return self._tx(self._contract.functions.updateCourse(course_id, name))

    def reassign_course(self, course_id: str, new_professor_id: int) -> dict:
        if not course_id or new_professor_id <= 0:
            raise ValueError("course_id and new_professor_id are required")
        return self._tx(self._contract.functions.reassignCourse(course_id, new_professor_id))

    def delete_course(self, course_id: str) -> dict:
        if not course_id:
            raise ValueError("course_id is required")
        return self._tx(self._contract.functions.deleteCourse(course_id))

    def get_course(self, course_id: str) -> CourseInfo:
        raw = self._call(self._contract.functions.getCourse(course_id))
        return CourseInfo.from_tuple(raw)

    def get_all_courses(self) -> list[CourseInfo]:
        ids = self._call(self._contract.functions.getAllCourses())
        return [self.get_course(cid) for cid in ids]
