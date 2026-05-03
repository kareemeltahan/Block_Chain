# Changelog — v1 → Final

This document covers every breaking change, bug fix, and new feature
between the original v1 codebase and this final version.

---

## Breaking Changes

These are not backwards-compatible. Existing deployments must be fully
redeployed against a fresh chain.

---

### Student `major` field replaced by `majorId`

**v1:** `major` was a free-form `string` stored directly on the student record.

**Final:** `majorId` is a `uint256` referencing `Major.id`.

`Major` is now a first-class on-chain entity with its own contract, unique code
constraint (`"CS"`, `"AI"`, `"IT"`, `"CYB"`), and full CRUD. Students reference
it by ID, giving referential integrity. Free strings like `"computer science"`,
`"CS"`, and `"Computer Science"` could all coexist as distinct values in v1.

**Migration:**
```python
# v1
ds.add_student("Alice", "Computer Science", year=2024, professor_id=1)

# Final — create the major first, then reference its ID
ds.add_major("CS", "Computer Science")   # id=1
ds.add_student("Alice", major_id=1, year=2024, professor_id=1)
```

---

### `addProfessor` — explicit address parameter added

**v1:** `professorAddress` was set to `msg.sender` inside the contract.
Since `University.sol` was the caller, every professor was assigned the
deployer's address. The `addressToId` reverse-lookup was broken — it always
returned the last-added professor for the deployer address.

**Final:** `addProfessor(name, department, professorAddress)` takes the
professor's address as an explicit parameter with a uniqueness constraint.

**Migration:**
```python
# v1
ds.add_professor("Dr. Smith", "Computer Science")

# Final — pass the professor's own Ethereum address
ds.add_professor("Dr. Smith", "Computer Science", professor_address="0xSmithAddr")
```

---

### Enrollment key now includes semester

**v1:** Key was `keccak256(abi.encodePacked(studentId, courseId))`.

**Final:** Key is `keccak256(abi.encodePacked(studentId, courseId, semester))`.

This allows a student to enroll in the same course in a different semester
(retake), each being an independent record with its own mark.
All enrollment operations now require a `semester` argument.

**Migration:**
```python
# v1
ds.enroll_student_in_course(student_id=1, course_id="CS101")
ds.update_student_mark(student_id=1, course_id="CS101", mark=88)

# Final — semester comes first
ds.enroll("spring2025", student_id=1, course_id="CS101")
ds.update_mark("spring2025", student_id=1, course_id="CS101", mark=88)
```

---

### `authorizedInstructors` replaced by three-tier RBAC

**v1:** `mapping(address => bool) authorizedInstructors` in University.sol —
a flat binary authorized/not-authorized check.

**Final:** `AccessRegistry.sol` with three distinct roles:
- `ADMIN_ROLE` — full system access, manages roles
- `REGISTRAR_ROLE` — student/course/enrollment CRUD
- `INSTRUCTOR_ROLE` — update marks for own courses only

**Migration:** Replace all `authorizeInstructor(addr)` calls with
`grant_role("REGISTRAR_ROLE", addr)` or `grant_role("INSTRUCTOR_ROLE", addr)`
as appropriate.

---

### New `Major` contract in deployment stack

**v1:** 5 contracts (Professor, Student, Course, Enrollment, University).

**Final:** 7 contracts (AccessRegistry, Major, Professor, Student, Course,
Enrollment, University).

The deployer handles the full order automatically. If you are deploying
manually, follow the topological order in `python/contracts/registry.py`.
After University is deployed, call `setUniversity()` on all five sub-contracts,
then grant `ADMIN_ROLE` to the University address on AccessRegistry.

---

### GPA scale changed from 0–100 to 0–4.0

**v1:** No GPA computation existed.

**Final:** All GPA values are on the standard 4.0 scale. Marks are still
stored on-chain as integers 0–100 — the conversion is done client-side.

```python
# Per-enrollment properties
enrollment.mark        # 88  (stored on-chain, unchanged)
enrollment.grade       # "B+"
enrollment.gpa_points  # 3.3

# Semester GPA (4.0)
sem.gpa  # 3.3

# Cumulative GPA (4.0)
ds.get_gpa(student_id=1)  # e.g. 3.08
```

---

## Bug Fixes

### BUG-01 — `EVM error CreateContractSizeLimit` on University deployment

`University.sol` compiled to ~34,000 bytes without the optimizer — 38% over
the 24,576-byte EIP-170 limit. `compile_files(..., optimize=True)` in
py-solc-x silently ignores the flag on several versions (especially Windows).

**Fix:** `scripts/compile.py` now uses `compile_standard` with a raw Standard
JSON dict, which passes optimizer settings directly to the solc binary.
University compiles to ~14,000 bytes (57% of limit).

---

### BUG-02 — `AccessRegistry: admin only` on `addProfessor`

`University.addProfessor` internally calls `accessRegistry.grantRole()`.
`msg.sender` in that call is the University contract address, which was never
granted `ADMIN_ROLE` on AccessRegistry — so every `addProfessor` reverted.

**Fix:** The deployer script now grants `ADMIN_ROLE` to the University contract
on AccessRegistry after deployment. University's external `onlyAdmin` modifier
still controls who can trigger the operation from outside.

---

### BUG-03 — All professors shared the deployer's address

`Professor.addProfessor` stored `msg.sender` as the professor's address.
Since University was the caller, all professors recorded the deployer's
address. `addressToId` was overwritten on every add — only the last professor
was findable by address.

**Fix:** `professorAddress` is now an explicit parameter with a uniqueness
constraint (`require(addressToId[addr] == 0)`).

---

### BUG-04 — Enrollment swap-and-pop silent data corruption

`Enrollment.unenrollStudent` called a `_swapPop()` helper that moved array
elements but did NOT update the displaced element's stored index fields.
Subsequent deletions used stale indices, targeting wrong elements.
Three correct `_removeFrom*Full()` functions were defined but never called —
they were dead code.

**Fix:** Replaced all broken/dead functions with one correct `_pop(arr, key, which)`
that atomically updates the displaced element's index field after every swap.

---

### BUG-05 — Role hash computed incorrectly in Python

```python
# v1 — WRONG: UTF-8 bytes padded to 32 bytes
ADMIN_ROLE = "0x" + "ADMIN_ROLE".encode().hex().ljust(64, "0")

# Final — CORRECT: keccak256 hash, matching Solidity
from web3 import Web3
role = Web3.keccak(text="ADMIN_ROLE")
```

All role operations silently sent the wrong bytes32 value, causing every
`has_role`, `grant_role`, and `revoke_role` call to operate on the wrong role.

---

### BUG-06 — `update_config()` stale-write on rapid sequential deploys

`config_manager.update_config()` imported a module-level snapshot at import
time. On rapid sequential deploys, each call wrote the same initial snapshot,
overwriting previously saved contract addresses.

**Fix:** `settings.set_contract_address(name, address)` reads fresh from disk
before each write and uses `os.replace()` (atomic rename) to prevent
partial-write corruption.

---

### BUG-07 — `get_courses_by_professor` mapped `active` field to `studentCount`

`CourseInfo` has four fields (id, name, professorId, active — indices 0–3).
The v1 Python code mapped index 3 (`active: bool`) to `"studentCount"` and
tried to read a non-existent index 4.

**Fix:** `CourseInfo.from_tuple` correctly maps `t[3]` to `active: bool`.
The `studentCount` field never existed on-chain and has been removed.

---

### BUG-08 — Broken access control modifier — tautology in Enrollment.sol

```solidity
// v1 — always passes, zero access control
modifier onlyProfessorOrAdmin(string memory courseId) {
    require(msg.sender == msg.sender || ..., "Unauthorized");
    _;
}
```

Any address could call `Enrollment.enrollStudent()` directly, bypassing
University.sol's RBAC checks entirely.

**Fix:** All broken modifiers removed. The only gate needed is:
```solidity
modifier onlyAuth() {
    require(msg.sender == university || msg.sender == deployer, "unauthorized");
    _;
}
```

---

### BUG-09 — `main.py` called `provider.get` as a callable factory

```python
# v1 — TypeError: 'Web3' object is not callable
from python.blockchain.provider import get as w3
accounts = w3().eth.accounts
```

**Fix:**
```python
from python.blockchain.provider import get as get_w3
accounts = get_w3().eth.accounts
```

---

### BUG-10 — Zero-address comparison failed on checksummed addresses

```python
# v1 — string comparison, case-sensitive
if current != "0x" + "0" * 40:   # may fail on checksummed return value
```

**Fix:**
```python
ZERO_ADDR = "0x" + "0" * 40
if current.lower() != ZERO_ADDR.lower():
```

---

## New Features

| Feature | Where |
|---------|-------|
| Major registry (CS, AI, IT, CYB, …) | `Major.sol`, `MajorDataSource` |
| Per-student semester enrollment map | `Enrollment.sol` |
| Semester history (`getStudentSemesters`) | `Enrollment.sol` |
| Per-semester enrollment query | `Enrollment.sol` |
| Course retake (same course, different semester) | `Enrollment.sol` |
| Per-semester GPA (4.0 scale) | `SemesterSummary.gpa` |
| Cumulative GPA (4.0 scale) | `EnrollmentDataSource.get_gpa` |
| Letter grades (A+, A, B+, …) | `EnrollmentRecord.grade` |
| Full academic transcript | `UniversityDataSource.get_full_transcript` |
| Three-tier RBAC (ADMIN/REGISTRAR/INSTRUCTOR) | `AccessRegistry.sol` |
| Auto INSTRUCTOR_ROLE on addProfessor | `University.sol` |
| Auto role revoke on deleteProfessor | `University.sol` |
| Instructor mark-scoping (own courses only) | `University.updateStudentMark` |
| Student wallet address + reverse lookup | `Student.sol` |
| Atomic config writes (no data loss on deploy) | `settings.py` |
| Local nonce tracking (no nonce collision) | `deployer.py` |
| Sub-contract binding (setUniversity) | `deployer._post_deploy` |
| University granted ADMIN_ROLE on AccessRegistry | `deployer._post_deploy` |
| Contract size bar + exit on over-limit | `scripts/compile.py` |
| Optimizer guaranteed via `compile_standard` | `scripts/compile.py` |
