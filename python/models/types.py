"""
python/models/types.py
──────────────────────
Typed Python representations of on-chain structs.
Pure data — no web3 dependency here.

Each dataclass mirrors the corresponding Solidity struct field-for-field.
from_tuple() deserialises the raw tuple that web3.py returns from a .call().

GPA SCALE:
  Marks are stored on-chain as integers 0–100 (percentage).
  All GPA values exposed through this module use the standard 4.0 scale.
  The conversion is done entirely client-side — the contracts are unchanged.

  Conversion table (standard US letter-grade mapping):

    A+  97-100  →  4.0        C+  77-79   →  2.3
    A   93-96   →  4.0        C   73-76   →  2.0
    A-  90-92   →  3.7        C-  70-72   →  1.7
    B+  87-89   →  3.3        D+  67-69   →  1.3
    B   83-86   →  3.0        D   63-66   →  1.0
    B-  80-82   →  2.7        D-  60-62   →  0.7
                               F    0-59   →  0.0
"""
from __future__ import annotations

from dataclasses import dataclass, field


# ─── GPA conversion ───────────────────────────────────────────────────────────

# Thresholds are inclusive lower bounds, highest first.
_GPA_TABLE: list[tuple[int, float]] = [
    (97, 4.0),   # A+
    (93, 4.0),   # A
    (90, 3.7),   # A-
    (87, 3.3),   # B+
    (83, 3.0),   # B
    (80, 2.7),   # B-
    (77, 2.3),   # C+
    (73, 2.0),   # C
    (70, 1.7),   # C-
    (67, 1.3),   # D+
    (63, 1.0),   # D
    (60, 0.7),   # D-
    (0,  0.0),   # F
]


def mark_to_gpa(mark: int) -> float:
    """
    Convert a percentage mark (0–100) to a 4.0-scale GPA point.

    >>> mark_to_gpa(95)   # A
    4.0
    >>> mark_to_gpa(85)   # B
    3.0
    >>> mark_to_gpa(55)   # F
    0.0
    """
    if mark <= 0:
        return 0.0
    for threshold, points in _GPA_TABLE:
        if mark >= threshold:
            return points
    return 0.0


def letter_grade(mark: int) -> str:
    """
    Return the letter grade for a percentage mark.

    >>> letter_grade(91)
    'A-'
    """
    _LETTER: list[tuple[int, str]] = [
        (97, "A+"), (93, "A"), (90, "A-"),
        (87, "B+"), (83, "B"), (80, "B-"),
        (77, "C+"), (73, "C"), (70, "C-"),
        (67, "D+"), (63, "D"), (60, "D-"),
        (0,  "F"),
    ]
    if mark <= 0:
        return "F"
    for threshold, grade in _LETTER:
        if mark >= threshold:
            return grade
    return "F"


# ─── Dataclasses ──────────────────────────────────────────────────────────────

@dataclass
class MajorInfo:
    id:          int
    code:        str   # "CS", "AI", "IT", "CYB"
    name:        str   # "Computer Science"
    description: str
    active:      bool

    @classmethod
    def from_tuple(cls, t: tuple) -> "MajorInfo":
        return cls(id=t[0], code=t[1], name=t[2], description=t[3], active=t[4])


@dataclass
class ProfessorInfo:
    id:                int
    professor_address: str   # the professor's own EOA
    name:              str
    department:        str
    active:            bool

    @classmethod
    def from_tuple(cls, t: tuple) -> "ProfessorInfo":
        return cls(id=t[0], professor_address=t[1], name=t[2], department=t[3], active=t[4])


@dataclass
class StudentInfo:
    id:                  int
    name:                str
    major_id:            int   # references Major.id
    year:                int
    academic_supervisor: str   # professor's EOA
    wallet_address:      str   # student's own EOA (may be zero address)
    active:              bool

    @classmethod
    def from_tuple(cls, t: tuple) -> "StudentInfo":
        return cls(
            id=t[0], name=t[1], major_id=t[2], year=t[3],
            academic_supervisor=t[4], wallet_address=t[5], active=t[6],
        )


@dataclass
class CourseInfo:
    id:           str
    name:         str
    professor_id: int
    active:       bool

    @classmethod
    def from_tuple(cls, t: tuple) -> "CourseInfo":
        return cls(id=t[0], name=t[1], professor_id=t[2], active=t[3])


@dataclass
class EnrollmentRecord:
    student_id:           int
    course_id:            str
    semester:             str    # "spring2025", "autumn2026"
    mark:                 int    # 0–100 percentage; 0 = not yet graded
    active:               bool
    student_array_index:  int = 0   # internal — do not use in application code
    course_array_index:   int = 0
    semester_array_index: int = 0

    @property
    def gpa_points(self) -> float:
        """This record's contribution to GPA (0.0–4.0). 0.0 if ungraded."""
        return mark_to_gpa(self.mark) if self.mark > 0 else 0.0

    @property
    def grade(self) -> str:
        """Letter grade for this record's mark. Empty string if ungraded."""
        return letter_grade(self.mark) if self.mark > 0 else ""

    @classmethod
    def from_tuple(cls, t: tuple) -> "EnrollmentRecord":
        return cls(
            student_id=t[0], course_id=t[1], semester=t[2], mark=t[3], active=t[4],
            student_array_index=t[5], course_array_index=t[6], semester_array_index=t[7],
        )


@dataclass
class SemesterSummary:
    """
    Client-side aggregate for a single semester.
    Not stored on-chain — computed from EnrollmentRecord data.
    GPA is on the 4.0 scale.
    """
    semester:    str
    enrollments: list[EnrollmentRecord] = field(default_factory=list)

    @property
    def gpa(self) -> float | None:
        """
        Semester GPA on a 4.0 scale.
        Computed as the unweighted average of grade points for all
        active, graded (mark > 0) enrollments.
        Returns None if no courses have been graded yet.
        """
        graded = [e for e in self.enrollments if e.active and e.mark > 0]
        if not graded:
            return None
        total = sum(mark_to_gpa(e.mark) for e in graded)
        return round(total / len(graded), 2)

    @property
    def course_ids(self) -> list[str]:
        """IDs of all active enrolled courses this semester."""
        return [e.course_id for e in self.enrollments if e.active]

    @property
    def graded_count(self) -> int:
        return sum(1 for e in self.enrollments if e.active and e.mark > 0)

    @property
    def total_courses(self) -> int:
        return sum(1 for e in self.enrollments if e.active)
