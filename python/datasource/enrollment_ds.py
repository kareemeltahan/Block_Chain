"""
python/datasource/enrollment_ds.py
────────────────────────────────────
Enrollment datasource — enrollment CRUD, semester queries, and GPA.

GPA SCALE:
  All GPA values returned by this module are on the standard 4.0 scale.
  Marks are stored on-chain as integers 0–100 (percentage). The conversion
  to grade points is done client-side via mark_to_gpa() in models/types.py.
  The on-chain calculateStudentGPA() returns an integer 0–100 average, which
  we then convert. Per-semester GPA is computed entirely in Python from the
  individual EnrollmentRecord marks.
"""
from __future__ import annotations

from web3.contract import Contract

from python.datasource.base import BaseDataSource
from python.models.types import EnrollmentRecord, SemesterSummary, mark_to_gpa


class EnrollmentDataSource(BaseDataSource):
    def __init__(self, contract: Contract) -> None:
        super().__init__(contract)

    # ─── Write ────────────────────────────────────────────────────────────────

    def enroll(self, student_id: int, course_id: str, semester: str) -> dict:
        _validate(student_id, course_id, semester)
        return self._tx(
            self._contract.functions.enrollStudentInCourse(student_id, course_id, semester)
        )

    def batch_enroll(self, student_ids: list[int], course_id: str, semester: str) -> dict:
        if not student_ids:  raise ValueError("student_ids must not be empty")
        if not course_id:    raise ValueError("course_id is required")
        if not semester:     raise ValueError("semester is required")
        return self._tx(self._contract.functions.batchEnroll(student_ids, course_id, semester))

    def unenroll(self, student_id: int, course_id: str, semester: str) -> dict:
        _validate(student_id, course_id, semester)
        return self._tx(
            self._contract.functions.removeCourseFromStudent(student_id, course_id, semester)
        )

    def update_mark(self, student_id: int, course_id: str, semester: str, mark: int) -> dict:
        _validate(student_id, course_id, semester)
        if not (0 <= mark <= 100):
            raise ValueError(f"mark must be 0–100, got {mark}")
        return self._tx(
            self._contract.functions.updateStudentMark(student_id, course_id, semester, mark)
        )

    # ─── Read ─────────────────────────────────────────────────────────────────

    def get_student_enrollments(self, student_id: int) -> list[EnrollmentRecord]:
        """All enrollment records for a student across all semesters."""
        raw = self._call(self._contract.functions.getStudentEnrollments(student_id))
        return [EnrollmentRecord.from_tuple(r) for r in raw]

    def get_semester_enrollments(self, student_id: int, semester: str) -> list[EnrollmentRecord]:
        """All enrollment records for a student in one specific semester."""
        raw = self._call(
            self._contract.functions.getStudentSemesterEnrollments(student_id, semester)
        )
        return [EnrollmentRecord.from_tuple(r) for r in raw]

    def get_student_semesters(self, student_id: int) -> list[str]:
        """Ordered list of distinct semesters a student has enrolled in."""
        return self._call(self._contract.functions.getStudentSemesters(student_id))

    def get_course_enrollments(self, course_id: str) -> list[EnrollmentRecord]:
        """All enrollment records for a course across all semesters."""
        raw = self._call(self._contract.functions.getCourseEnrollments(course_id))
        return [EnrollmentRecord.from_tuple(r) for r in raw]

    def get_semester_summary(self, student_id: int, semester: str) -> SemesterSummary:
        """
        SemesterSummary with all enrollments for that semester.
        SemesterSummary.gpa is on the 4.0 scale.
        """
        return SemesterSummary(
            semester=semester,
            enrollments=self.get_semester_enrollments(student_id, semester),
        )

    def get_full_transcript(self, student_id: int) -> list[SemesterSummary]:
        """
        Complete academic transcript: all semesters in insertion order,
        each with its enrollments, letter grades, and 4.0-scale GPA.
        """
        semesters = self.get_student_semesters(student_id)
        return [self.get_semester_summary(student_id, sem) for sem in semesters]

    def get_gpa(self, student_id: int) -> float | None:
        """
        Overall cumulative GPA on the 4.0 scale across all semesters.

        HOW IT WORKS:
          1. Fetch all enrollment records for the student.
          2. Filter to active records with mark > 0 (graded courses).
          3. Convert each mark to grade points via mark_to_gpa().
          4. Return the unweighted average (all courses weighted equally).

        This is computed client-side from individual records rather than
        converting the integer average returned by calculateStudentGPA()
        on-chain, because converting the average of marks ≠ average of
        GPA points (due to non-linear conversion steps like A vs A- vs B+).

        Returns None if no courses have been graded yet.
        """
        records = self.get_student_enrollments(student_id)
        graded  = [r for r in records if r.active and r.mark > 0]
        if not graded:
            return None
        total = sum(mark_to_gpa(r.mark) for r in graded)
        return round(total / len(graded), 2)


def _validate(student_id: int, course_id: str, semester: str) -> None:
    if not isinstance(student_id, int) or student_id <= 0:
        raise ValueError(f"student_id must be a positive integer, got {student_id!r}")
    if not course_id:
        raise ValueError("course_id is required")
    if not semester:
        raise ValueError("semester is required")
