"""
python/datasource/university_ds.py
────────────────────────────────────
UniversityDataSource — the single public API for all application code.

USAGE:
    from python.datasource.university_ds import UniversityDataSource
    ds = UniversityDataSource()

    ds.add_major("CS", "Computer Science")
    ds.add_professor("Dr. Smith", "Computer Science", "0xProfAddr")
    ds.add_student("Alice", major_id=1, year=2024, professor_id=1)
    ds.enroll("spring2025", student_id=1, course_id="CS101")
    ds.update_mark("spring2025", student_id=1, course_id="CS101", mark=88)
    transcript = ds.get_full_transcript(student_id=1)

ARGUMENT ORDER FOR ENROLLMENT METHODS:
    semester comes first in enroll/unenroll/update_mark.
    Rationale: in real usage you typically have a semester context already set
    (e.g. "we're processing spring2025"), then iterate over student+course pairs.

ON FIRST RUN:
    UniversityDataSource() calls get_or_deploy(ContractType.UNIVERSITY) which
    deploys all 7 contracts if they are missing or have no live bytecode.
    All addresses are saved to config.json. Subsequent runs reuse them.
"""
from __future__ import annotations

from python.blockchain.deployer import get_or_deploy
from python.contracts.registry import ContractType
from python.datasource.admin_ds import AdminDataSource
from python.datasource.domain_ds import (
    MajorDataSource,
    ProfessorDataSource,
    StudentDataSource,
    CourseDataSource,
)
from python.datasource.enrollment_ds import EnrollmentDataSource
from python.models.types import (
    CourseInfo,
    EnrollmentRecord,
    MajorInfo,
    ProfessorInfo,
    SemesterSummary,
    StudentInfo,
)

ZERO = "0x0000000000000000000000000000000000000000"


class UniversityDataSource:

    def __init__(self) -> None:
        contract     = get_or_deploy(ContractType.UNIVERSITY)
        self._major  = MajorDataSource(contract)
        self._prof   = ProfessorDataSource(contract)
        self._stu    = StudentDataSource(contract)
        self._crs    = CourseDataSource(contract)
        self._enr    = EnrollmentDataSource(contract)
        self._admin  = AdminDataSource(contract)

    # ════════════════════════════════════════════════════════════════════════
    # ROLE MANAGEMENT
    # ════════════════════════════════════════════════════════════════════════

    def grant_role(self, role_name: str, address: str) -> dict:
        """
        Grant a role to an address. Requires deployer to hold ADMIN_ROLE.

        Args:
            role_name: 'ADMIN_ROLE' | 'REGISTRAR_ROLE' | 'INSTRUCTOR_ROLE'
            address:   Ethereum address to grant the role to.

        Raises:
            ValueError: if role_name is not one of the three known roles.
            RuntimeError: if the transaction reverts (e.g. caller not admin).
        """
        return self._admin.grant_role(role_name, address)

    def revoke_role(self, role_name: str, address: str) -> dict:
        """
        Revoke a role from an address.
        Cannot revoke ADMIN_ROLE from the superAdmin (deployer) — enforced on-chain.
        """
        return self._admin.revoke_role(role_name, address)

    def has_role(self, role_name: str, address: str) -> bool:
        return self._admin.has_role(role_name, address)

    def get_all_roles(self) -> dict[str, list[str]]:
        """
        Returns:
            {'ADMIN_ROLE': [...], 'INSTRUCTOR_ROLE': [...], 'REGISTRAR_ROLE': [...]}
        """
        return self._admin.get_all_roles()

    # ════════════════════════════════════════════════════════════════════════
    # MAJORS
    # ════════════════════════════════════════════════════════════════════════

    def add_major(self, code: str, name: str, description: str = "") -> dict:
        """
        Register a new academic major.

        Args:
            code:        Short uppercase key — e.g. "CS", "AI", "IT", "CYB".
                         Automatically uppercased. Must be unique.
            name:        Full name — e.g. "Computer Science".
            description: Optional longer description.

        Examples:
            ds.add_major("CS",  "Computer Science",       "Algorithms and software")
            ds.add_major("AI",  "Artificial Intelligence","ML, NLP, computer vision")
            ds.add_major("IT",  "Information Technology", "Networks and sysadmin")
            ds.add_major("CYB", "Cybersecurity",          "Offensive and defensive sec")
        """
        return self._major.add_major(code, name, description)

    def update_major(self, major_id: int, name: str = "", description: str = "") -> dict:
        """Partial update — empty strings are ignored by the contract."""
        return self._major.update_major(major_id, name, description)

    def deactivate_major(self, major_id: int) -> dict:
        """
        Soft-delete a major. Existing students retain their majorId.
        New students cannot be assigned to a deactivated major.
        """
        return self._major.deactivate_major(major_id)

    def get_major(self, major_id: int) -> MajorInfo:
        return self._major.get_major(major_id)

    def get_major_by_code(self, code: str) -> MajorInfo:
        """Look up a major by its short code (case-insensitive)."""
        return self._major.get_major_by_code(code)

    def get_all_majors(self) -> list[MajorInfo]:
        return self._major.get_all_majors()

    # ════════════════════════════════════════════════════════════════════════
    # PROFESSORS
    # ════════════════════════════════════════════════════════════════════════

    def add_professor(self, name: str, department: str, professor_address: str) -> dict:
        """
        Add a professor and auto-grant INSTRUCTOR_ROLE to their address.

        Args:
            name:               Full name — e.g. "Dr. Smith".
            department:         Department name — e.g. "Computer Science".
            professor_address:  The professor's own Ethereum EOA.
                                MUST be unique — not the deployer's address.
                                INSTRUCTOR_ROLE is granted to this address automatically.

        Raises:
            ValueError:  if professor_address is zero or missing.
            RuntimeError: if address is already registered, or caller lacks REGISTRAR_ROLE.
        """
        return self._prof.add_professor(name, department, professor_address)

    def update_professor(
        self,
        professor_id: int,
        name: str = "",
        department: str = "",
        new_address: str = ZERO,
    ) -> dict:
        """
        Partial update. Pass new_address=ZERO (default) to leave address unchanged.
        Changing the address updates the addressToId reverse mapping on-chain.
        """
        return self._prof.update_professor(professor_id, name, department, new_address)

    def delete_professor(self, professor_id: int) -> dict:
        """
        Delete a professor with full cascade:
          1. Delete all their courses.
          2. Unenroll all students from those courses.
          3. Revoke INSTRUCTOR_ROLE from their address.
          4. Delete the professor record.

        Requires ADMIN_ROLE.
        """
        return self._prof.delete_professor(professor_id)

    def get_professor(self, professor_id: int) -> ProfessorInfo:
        return self._prof.get_professor(professor_id)

    def get_all_professors(self) -> list[ProfessorInfo]:
        return self._prof.get_all_professors()

    # ════════════════════════════════════════════════════════════════════════
    # STUDENTS
    # ════════════════════════════════════════════════════════════════════════

    def add_student(
        self,
        name: str,
        major_id: int,
        year: int,
        professor_id: int,
        wallet_address: str = ZERO,
    ) -> dict:
        """
        Register a new student.

        Args:
            name:           Full name.
            major_id:       Must reference an active Major (use get_major_by_code).
            year:           Enrollment year, e.g. 2024.
            professor_id:   Academic supervisor. Their EOA is stored on the record.
            wallet_address: Optional student EOA. When set, enables reverse lookup
                            via Student.getStudentByAddress().

        Examples:
            ds.add_student("Alice", major_id=1, year=2024, professor_id=1)
            ds.add_student("Bob",   major_id=2, year=2025, professor_id=2,
                           wallet_address="0xBobWallet")
        """
        return self._stu.add_student(name, major_id, year, professor_id, wallet_address)

    def update_student(
        self,
        student_id: int,
        name: str = "",
        major_id: int = 0,
        year: int = 0,
        professor_id: int = 0,
        wallet_address: str = ZERO,
    ) -> dict:
        """Partial update — zero/empty values are ignored by the contract."""
        return self._stu.update_student(
            student_id, name, major_id, year, professor_id, wallet_address
        )

    def delete_student(self, student_id: int) -> dict:
        """
        Delete a student with cascade:
          1. Unenroll from all active courses (all semesters).
          2. Delete the student record.
        """
        return self._stu.delete_student(student_id)

    def get_student(self, student_id: int) -> StudentInfo:
        return self._stu.get_student(student_id)

    def get_all_students(self, offset: int = 0, limit: int = 100) -> list[StudentInfo]:
        """Paginated. Returns full StudentInfo objects, not just IDs."""
        return self._stu.get_all_students(offset, limit)

    # ════════════════════════════════════════════════════════════════════════
    # COURSES
    # ════════════════════════════════════════════════════════════════════════

    def create_course(self, course_id: str, name: str, professor_id: int) -> dict:
        """
        Create a course.

        Args:
            course_id:    User-defined string key — e.g. "CS101", "AI301".
                          Must be unique across all courses.
            name:         Full name — e.g. "Introduction to Programming".
            professor_id: Owning professor. Must be active.
        """
        return self._crs.create_course(course_id, name, professor_id)

    def update_course(self, course_id: str, name: str) -> dict:
        return self._crs.update_course(course_id, name)

    def reassign_course(self, course_id: str, new_professor_id: int) -> dict:
        """Reassign a course to a different professor. Updates both professors' lists."""
        return self._crs.reassign_course(course_id, new_professor_id)

    def delete_course(self, course_id: str) -> dict:
        """
        Delete a course with cascade:
          1. Unenroll all students across all semesters.
          2. Delete the course record.
        """
        return self._crs.delete_course(course_id)

    def get_course(self, course_id: str) -> CourseInfo:
        return self._crs.get_course(course_id)

    def get_all_courses(self) -> list[CourseInfo]:
        return self._crs.get_all_courses()

    # ════════════════════════════════════════════════════════════════════════
    # ENROLLMENT
    # ════════════════════════════════════════════════════════════════════════
    #
    # SEMESTER FORMAT CONVENTION:
    #   Semesters are free-form strings stored verbatim on-chain.
    #   Recommended format: "{season}{year}"
    #   Examples: "spring2025"  "autumn2025"  "summer2026"  "winter2026"
    #
    # ARGUMENT ORDER:
    #   semester is always the first argument in write methods.
    #   This reflects typical usage: you work within a semester context,
    #   then specify which student and course.
    #
    # RETAKES:
    #   A student can enroll in the same course in different semesters.
    #   Each (studentId, courseId, semester) triple is an independent record
    #   with its own mark. The enrollment key is the keccak256 of all three.

    def enroll(self, semester: str, student_id: int, course_id: str) -> dict:
        """
        Enroll a student in a course for a given semester.

        Reverts if:
          - Student is inactive.
          - Course does not exist.
          - Student is already enrolled in this course+semester combination.

        Examples:
            ds.enroll("spring2025", student_id=1, course_id="CS101")
            ds.enroll("spring2025", student_id=1, course_id="MATH101")
        """
        return self._enr.enroll(student_id, course_id, semester)

    def batch_enroll(self, semester: str, student_ids: list[int], course_id: str) -> dict:
        """
        Enroll multiple students in one transaction.
        Silently skips inactive students and already-enrolled pairs.
        All valid enrollments happen atomically.

        Example:
            ds.batch_enroll("spring2025", student_ids=[1, 2, 3, 4], course_id="CS101")
        """
        return self._enr.batch_enroll(student_ids, course_id, semester)

    def unenroll(self, semester: str, student_id: int, course_id: str) -> dict:
        """Remove a student from a course for a specific semester."""
        return self._enr.unenroll(student_id, course_id, semester)

    def update_mark(self, semester: str, student_id: int, course_id: str, mark: int) -> dict:
        """
        Set a student's mark (0–100) for a course in a specific semester.

        Access rules:
          - ADMIN and REGISTRAR can grade any course.
          - INSTRUCTOR can only grade courses they own (enforced on-chain via
            professorContract.getProfessorIdByAddress(msg.sender)).

        Args:
            mark: Integer 0–100. 0 means "not yet graded" by convention.

        Raises:
            ValueError:  if mark is outside 0–100.
            RuntimeError: if enrollment is not active, or instructor doesn't own course.
        """
        return self._enr.update_mark(student_id, course_id, semester, mark)

    # ─── Enrollment reads ─────────────────────────────────────────────────────

    def get_student_enrollments(self, student_id: int) -> list[EnrollmentRecord]:
        """All enrollment records for a student across all semesters (flat list)."""
        return self._enr.get_student_enrollments(student_id)

    def get_semester_enrollments(self, student_id: int, semester: str) -> list[EnrollmentRecord]:
        """All enrollment records for a student in a specific semester."""
        return self._enr.get_semester_enrollments(student_id, semester)

    def get_student_semesters(self, student_id: int) -> list[str]:
        """
        Ordered list of distinct semesters a student has appeared in.
        Order reflects insertion order (first enrollment in each semester).

        Example:
            ds.get_student_semesters(1)  →  ["spring2025", "autumn2025"]
        """
        return self._enr.get_student_semesters(student_id)

    def get_semester_summary(self, student_id: int, semester: str) -> SemesterSummary:
        """
        SemesterSummary with all enrollments + computed GPA for that semester.

        Example:
            s = ds.get_semester_summary(1, "spring2025")
            print(s.semester)    # "spring2025"
            print(s.gpa)         # 81.0
            print(s.course_ids)  # ["CS101", "MATH101"]
        """
        return self._enr.get_semester_summary(student_id, semester)

    def get_full_transcript(self, student_id: int) -> list[SemesterSummary]:
        """
        Complete academic transcript — all semesters in insertion order,
        each with enrolled courses, marks, and per-semester GPA.

        Example:
            transcript = ds.get_full_transcript(1)
            for sem in transcript:
                gpa = f"{sem.gpa:.1f}" if sem.gpa else "ungraded"
                print(f"{sem.semester}: {sem.course_ids}  GPA={gpa}")
            # spring2025: ['CS101', 'MATH101']  GPA=81.0
            # autumn2025: ['CS201', 'AI301']    GPA=88.5
        """
        return self._enr.get_full_transcript(student_id)

    def get_gpa(self, student_id: int) -> float | None:
        """
        Overall GPA across all semesters and all graded courses.
        Returns None if no courses have been graded yet.
        """
        return self._enr.get_gpa(student_id)

    def get_course_enrollments(self, course_id: str) -> list[EnrollmentRecord]:
        """All enrollment records for a course across all semesters."""
        return self._enr.get_course_enrollments(course_id)
