# Python Datasource API Reference

All application code goes through `UniversityDataSource`.
Never instantiate domain datasources directly.

```python
from python.datasource.university_ds import UniversityDataSource
ds = UniversityDataSource()
```

On construction, `get_or_deploy(ContractType.UNIVERSITY)` is called.
If contracts are missing or undeployed, the full stack is deployed automatically.
Subsequent instantiations are fast — addresses are cached in `config.json`.

---

## Return types

**Write operations** return a `TxReceipt` dict (web3.py standard) with keys:
`transactionHash`, `blockNumber`, `status` (1=success), `gasUsed`, etc.

**Read operations** return typed dataclasses from `python.models.types`.

---

## Error handling

```python
# ValueError — raised before any chain interaction, for bad arguments:
ds.update_mark("spring2025", student_id=1, course_id="CS101", mark=150)
# ValueError: mark must be 0–100, got 150

# RuntimeError — raised when the chain reverts:
ds.enroll("spring2025", student_id=1, course_id="CS101")
# RuntimeError: Transaction reverted.
#   Hash: 0x...
# Revert reason surfaces in the exception message.
```

---

## Role Management

### `grant_role(role_name, address) → TxReceipt`
```python
ds.grant_role("REGISTRAR_ROLE", "0xAddr")
ds.grant_role("INSTRUCTOR_ROLE", "0xAddr")
```
`role_name` must be `"ADMIN_ROLE"`, `"REGISTRAR_ROLE"`, or `"INSTRUCTOR_ROLE"`.
Raises `ValueError` for unknown names before hitting the chain.

### `revoke_role(role_name, address) → TxReceipt`

### `has_role(role_name, address) → bool`
```python
if ds.has_role("ADMIN_ROLE", my_address):
    print("I am admin")
```

### `get_all_roles() → dict[str, list[str]]`
```python
{
  "ADMIN_ROLE":      ["0xDeployer..."],
  "INSTRUCTOR_ROLE": ["0xProf1...", "0xProf2..."],
  "REGISTRAR_ROLE":  ["0xStaff..."],
}
```

---

## Majors

### `add_major(code, name, description="") → TxReceipt`
```python
ds.add_major("CS",  "Computer Science",       "Algorithms and software")
ds.add_major("AI",  "Artificial Intelligence","ML, NLP, vision")
ds.add_major("IT",  "Information Technology", "Networks and sysadmin")
ds.add_major("CYB", "Cybersecurity",          "Offensive and defensive security")
ds.add_major("EE",  "Electrical Engineering", "Circuits and signals")
```
`code` is uppercased automatically. Duplicate codes revert on-chain.

### `update_major(major_id, name="", description="") → TxReceipt`
Empty strings are ignored — pass only what you want to change.

### `deactivate_major(major_id) → TxReceipt`
Soft-delete. Existing students with this `major_id` are unaffected.

### `get_major(major_id) → MajorInfo`
```python
@dataclass
class MajorInfo:
    id: int
    code: str          # "CS"
    name: str          # "Computer Science"
    description: str
    active: bool
```

### `get_major_by_code(code) → MajorInfo`
```python
m = ds.get_major_by_code("AI")
print(m.id, m.name)  # 2  Artificial Intelligence
```

### `get_all_majors() → list[MajorInfo]`

---

## Professors

### `add_professor(name, department, professor_address) → TxReceipt`
```python
ds.add_professor("Dr. Smith",   "Computer Science", accounts[1])
ds.add_professor("Dr. Johnson", "Mathematics",      accounts[2])
```
`professor_address` must be:
- A valid non-zero Ethereum address
- Unique — not already registered as a professor
- **Not** the deployer's address (would make all professors share one address)

`INSTRUCTOR_ROLE` is automatically granted to `professor_address`.

### `update_professor(professor_id, name="", department="", new_address=ZERO) → TxReceipt`
Pass `new_address=ZERO` (default) to leave address unchanged.

### `delete_professor(professor_id) → TxReceipt`
**Cascade** (all atomic, one transaction):
1. Delete all courses the professor owns.
2. Unenroll all students from those courses (all semesters).
3. Revoke `INSTRUCTOR_ROLE` from professor's address.
4. Delete the professor record.

Requires `ADMIN_ROLE`.

### `get_professor(professor_id) → ProfessorInfo`
```python
@dataclass
class ProfessorInfo:
    id: int
    professor_address: str   # their own EOA
    name: str
    department: str
    active: bool
```

### `get_all_professors() → list[ProfessorInfo]`

---

## Students

### `add_student(name, major_id, year, professor_id, wallet_address=ZERO) → TxReceipt`
```python
ds.add_student("Alice", major_id=1, year=2024, professor_id=1)
ds.add_student("Bob",   major_id=2, year=2025, professor_id=2,
               wallet_address="0xBobWallet")
```
- `major_id` must reference an active Major.
- `professor_id` assigns academic supervisor — their EOA is resolved and stored.
- `wallet_address` is optional. When set, the student is findable by address.

### `update_student(student_id, name="", major_id=0, year=0, professor_id=0, wallet_address=ZERO) → TxReceipt`
Zero/empty values are ignored.

### `delete_student(student_id) → TxReceipt`
**Cascade:** unenrolls from all active courses (all semesters) before deletion.

### `get_student(student_id) → StudentInfo`
```python
@dataclass
class StudentInfo:
    id: int
    name: str
    major_id: int            # references Major.id
    year: int
    academic_supervisor: str # professor's EOA
    wallet_address: str      # student's EOA (may be zero address)
    active: bool
```

### `get_all_students(offset=0, limit=100) → list[StudentInfo]`
Paginated. Returns full `StudentInfo` objects.

---

## Courses

### `create_course(course_id, name, professor_id) → TxReceipt`
```python
ds.create_course("CS101",   "Intro to Programming",  professor_id=1)
ds.create_course("AI301",   "Machine Learning",      professor_id=2)
ds.create_course("MATH101", "Discrete Mathematics",  professor_id=2)
```
`course_id` is user-defined and must be unique across all courses.

### `update_course(course_id, name) → TxReceipt`

### `reassign_course(course_id, new_professor_id) → TxReceipt`
Moves course from one professor's list to another. Existing enrollments are unaffected.

### `delete_course(course_id) → TxReceipt`
**Cascade:** unenrolls all students (all semesters) before deletion.

### `get_course(course_id) → CourseInfo`
```python
@dataclass
class CourseInfo:
    id: str
    name: str
    professor_id: int
    active: bool
```

### `get_all_courses() → list[CourseInfo]`

---

## Enrollment

### Semester format

Semesters are free-form strings stored verbatim on-chain. Recommended format:

```
"spring2024"    "autumn2024"
"spring2025"    "autumn2025"
"summer2025"    "winter2026"
```

Any consistent string works. The contract stores and returns it exactly as given.

### Argument order

`semester` is always the **first** argument in write methods.
This reflects typical usage where you work within a semester context.

---

### `enroll(semester, student_id, course_id) → TxReceipt`
```python
ds.enroll("spring2025", student_id=1, course_id="CS101")
ds.enroll("spring2025", student_id=1, course_id="MATH101")

# Same student, same course, different semester = independent record (retake)
ds.enroll("spring2026", student_id=1, course_id="CS101")
```

Reverts if already enrolled in this exact semester+course combination.

### `batch_enroll(semester, student_ids, course_id) → TxReceipt`
```python
ds.batch_enroll("spring2025", student_ids=[1, 2, 3, 4], course_id="CS101")
```
Silently skips inactive students and already-enrolled pairs. All valid
enrollments happen in one atomic transaction.

### `unenroll(semester, student_id, course_id) → TxReceipt`
```python
ds.unenroll("spring2025", student_id=1, course_id="MATH101")
```

### `update_mark(semester, student_id, course_id, mark) → TxReceipt`
```python
ds.update_mark("spring2025", student_id=1, course_id="CS101", mark=88)
```
`mark` must be 0–100. 0 conventionally means "not yet graded".
INSTRUCTOR callers may only grade courses they own.

---

### `get_student_semesters(student_id) → list[str]`
```python
ds.get_student_semesters(1)
# ["spring2025", "autumn2025", "spring2026"]
```
Insertion-ordered. Stable even after unenrollments.

### `get_semester_enrollments(student_id, semester) → list[EnrollmentRecord]`
```python
recs = ds.get_semester_enrollments(1, "spring2025")
for r in recs:
    print(r.course_id, r.mark, r.active)
```

### `get_semester_summary(student_id, semester) → SemesterSummary`
```python
@dataclass
class SemesterSummary:
    semester: str
    enrollments: list[EnrollmentRecord]

    @property
    def gpa(self) -> float | None: ...         # None if nothing graded
    @property
    def course_ids(self) -> list[str]: ...
    @property
    def graded_count(self) -> int: ...
    @property
    def total_courses(self) -> int: ...
```
```python
s = ds.get_semester_summary(1, "spring2025")
print(s.semester)      # "spring2025"
print(s.gpa)           # 81.0
print(s.course_ids)    # ["CS101", "MATH101"]
print(s.total_courses) # 2
print(s.graded_count)  # 2
```

### `get_full_transcript(student_id) → list[SemesterSummary]`
Complete academic history. One `SemesterSummary` per semester.

```python
transcript = ds.get_full_transcript(1)
for sem in transcript:
    gpa = f"{sem.gpa:.1f}" if sem.gpa else "ungraded"
    print(f"{sem.semester}: {sem.course_ids}  GPA={gpa}")

# spring2025: ['CS101', 'MATH101']  GPA=81.0
# autumn2025: ['CS201', 'AI301']    GPA=88.5
# spring2026: ['CS101']             GPA=97.0
```

### `get_gpa(student_id) → float | None`
Overall GPA across all semesters. `None` if no graded courses.

### `get_student_enrollments(student_id) → list[EnrollmentRecord]`
All records across all semesters (flat list).

### `get_course_enrollments(course_id) → list[EnrollmentRecord]`
All students enrolled in a course across all semesters.

---

## EnrollmentRecord fields

```python
@dataclass
class EnrollmentRecord:
    student_id:           int
    course_id:            str
    semester:             str    # "spring2025"
    mark:                 int    # 0 = ungraded
    active:               bool
    # Internal index fields — do not use in application code:
    student_array_index:  int
    course_array_index:   int
    semester_array_index: int
```
