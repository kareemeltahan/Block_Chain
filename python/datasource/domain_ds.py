"""
python/datasource/domain_ds.py
───────────────────────────────
Domain datasources for Major, Professor, Student, Course.
Each class wraps the University contract's ABI and provides a typed interface.
"""
from __future__ import annotations

from web3.contract import Contract

from python.datasource.base import BaseDataSource
from python.models.types import MajorInfo, ProfessorInfo, StudentInfo, CourseInfo

ZERO = "0x0000000000000000000000000000000000000000"


# ══════════════════════════════════════════════════════════════════════════════
# MAJOR
# ══════════════════════════════════════════════════════════════════════════════

class MajorDataSource(BaseDataSource):
    def __init__(self, contract: Contract) -> None:
        super().__init__(contract)

    def add_major(self, code: str, name: str, description: str = "") -> dict:
        if not code or not name:
            raise ValueError("code and name are required")
        return self._tx(self._contract.functions.addMajor(code.upper(), name, description))

    def update_major(self, major_id: int, name: str = "", description: str = "") -> dict:
        _require_positive(major_id, "major_id")
        return self._tx(self._contract.functions.updateMajor(major_id, name, description))

    def deactivate_major(self, major_id: int) -> dict:
        _require_positive(major_id, "major_id")
        return self._tx(self._contract.functions.deactivateMajor(major_id))

    def get_major(self, major_id: int) -> MajorInfo:
        return MajorInfo.from_tuple(self._call(self._contract.functions.getMajor(major_id)))

    def get_major_by_code(self, code: str) -> MajorInfo:
        return MajorInfo.from_tuple(self._call(self._contract.functions.getMajorByCode(code.upper())))

    def get_all_majors(self) -> list[MajorInfo]:
        ids = self._call(self._contract.functions.getAllMajors())
        return [self.get_major(i) for i in ids]


# ══════════════════════════════════════════════════════════════════════════════
# PROFESSOR
# ══════════════════════════════════════════════════════════════════════════════

class ProfessorDataSource(BaseDataSource):
    def __init__(self, contract: Contract) -> None:
        super().__init__(contract)

    def add_professor(self, name: str, department: str, professor_address: str) -> dict:
        if not name or not department:
            raise ValueError("name and department are required")
        if not professor_address or professor_address == ZERO:
            raise ValueError("professor_address is required and must not be the zero address")
        return self._tx(self._contract.functions.addProfessor(name, department, professor_address))

    def update_professor(
        self,
        professor_id: int,
        name: str = "",
        department: str = "",
        new_address: str = ZERO,
    ) -> dict:
        _require_positive(professor_id, "professor_id")
        return self._tx(
            self._contract.functions.updateProfessor(professor_id, name, department, new_address)
        )

    def delete_professor(self, professor_id: int) -> dict:
        _require_positive(professor_id, "professor_id")
        return self._tx(self._contract.functions.deleteProfessor(professor_id))

    def get_professor(self, professor_id: int) -> ProfessorInfo:
        return ProfessorInfo.from_tuple(
            self._call(self._contract.functions.getProfessor(professor_id))
        )

    def get_all_professors(self) -> list[ProfessorInfo]:
        ids = self._call(self._contract.functions.getAllProfessors())
        return [self.get_professor(i) for i in ids]


# ══════════════════════════════════════════════════════════════════════════════
# STUDENT
# ══════════════════════════════════════════════════════════════════════════════

class StudentDataSource(BaseDataSource):
    def __init__(self, contract: Contract) -> None:
        super().__init__(contract)

    def add_student(
        self,
        name: str,
        major_id: int,
        year: int,
        professor_id: int,
        wallet_address: str = ZERO,
    ) -> dict:
        if not name:          raise ValueError("name is required")
        _require_positive(major_id,     "major_id")
        _require_positive(professor_id, "professor_id")
        _require_positive(year,         "year")
        return self._tx(
            self._contract.functions.addStudent(name, major_id, year, professor_id, wallet_address)
        )

    def update_student(
        self,
        student_id: int,
        name: str = "",
        major_id: int = 0,
        year: int = 0,
        professor_id: int = 0,
        wallet_address: str = ZERO,
    ) -> dict:
        _require_positive(student_id, "student_id")
        return self._tx(
            self._contract.functions.updateStudent(
                student_id, name, major_id, year, professor_id, wallet_address
            )
        )

    def delete_student(self, student_id: int) -> dict:
        _require_positive(student_id, "student_id")
        return self._tx(self._contract.functions.deleteStudent(student_id))

    def get_student(self, student_id: int) -> StudentInfo:
        return StudentInfo.from_tuple(
            self._call(self._contract.functions.getStudent(student_id))
        )

    def get_all_students(self, offset: int = 0, limit: int = 100) -> list[StudentInfo]:
        ids = self._call(self._contract.functions.getAllStudents())
        return [self.get_student(i) for i in ids[offset: offset + limit]]


# ══════════════════════════════════════════════════════════════════════════════
# COURSE
# ══════════════════════════════════════════════════════════════════════════════

class CourseDataSource(BaseDataSource):
    def __init__(self, contract: Contract) -> None:
        super().__init__(contract)

    def create_course(self, course_id: str, name: str, professor_id: int) -> dict:
        if not course_id or not name: raise ValueError("course_id and name are required")
        _require_positive(professor_id, "professor_id")
        return self._tx(self._contract.functions.createCourse(course_id, name, professor_id))

    def update_course(self, course_id: str, name: str) -> dict:
        if not course_id or not name: raise ValueError("course_id and name are required")
        return self._tx(self._contract.functions.updateCourse(course_id, name))

    def reassign_course(self, course_id: str, new_professor_id: int) -> dict:
        if not course_id: raise ValueError("course_id is required")
        _require_positive(new_professor_id, "new_professor_id")
        return self._tx(self._contract.functions.reassignCourse(course_id, new_professor_id))

    def delete_course(self, course_id: str) -> dict:
        if not course_id: raise ValueError("course_id is required")
        return self._tx(self._contract.functions.deleteCourse(course_id))

    def get_course(self, course_id: str) -> CourseInfo:
        return CourseInfo.from_tuple(self._call(self._contract.functions.getCourse(course_id)))

    def get_all_courses(self) -> list[CourseInfo]:
        ids = self._call(self._contract.functions.getAllCourses())
        return [self.get_course(cid) for cid in ids]


# ─── Shared validation ────────────────────────────────────────────────────────

def _require_positive(value: int, name: str) -> None:
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer, got {value!r}")
