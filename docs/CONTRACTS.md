# Contract Reference

Every contract, every function, every storage variable, every event.
Security notes and design rationale inline.

---

## AccessRegistry.sol

**Path:** `contracts/access/AccessRegistry.sol`
**Purpose:** On-chain RBAC. Single source of truth for role membership.
**Dependencies:** None.

### Roles

| Constant | Value (keccak256 of) | Inherits |
|----------|----------------------|---------|
| `ADMIN_ROLE` | `"ADMIN_ROLE"` | All capabilities |
| `REGISTRAR_ROLE` | `"REGISTRAR_ROLE"` | INSTRUCTOR capabilities |
| `INSTRUCTOR_ROLE` | `"INSTRUCTOR_ROLE"` | Read-only + own-course marks |

### State variables

| Variable | Type | Description |
|----------|------|-------------|
| `superAdmin` | `address immutable` | Deployer. Cannot lose ADMIN_ROLE. |
| `_has` | `mapping(bytes32 => mapping(address => bool))` | role → account → granted |
| `_members` | `mapping(bytes32 => address[])` | Enumerable member list per role |
| `_idx` | `mapping(bytes32 => mapping(address => uint256))` | 1-based index for O(1) removal |

### Functions

#### `constructor()`
Grants `ADMIN_ROLE` to `msg.sender` (deployer). Sets `superAdmin`.

#### `grantRole(bytes32 role, address account)` — `onlyAdmin`
Idempotent — no-op if already granted.
Pushes account to `_members[role]`, sets `_idx` to 1-based position.

#### `revokeRole(bytes32 role, address account)` — `onlyAdmin`
Reverts with `"AR: cannot revoke superAdmin"` if trying to revoke `ADMIN_ROLE`
from the superAdmin. Uses swap-and-pop on `_members` to maintain a compact list.

#### `hasRole(bytes32 role, address account) → bool` — `view`

#### `getRoleMembers(bytes32 role) → address[]` — `view`
Returns all current holders. Safe to enumerate off-chain.

#### `getRoleMemberCount(bytes32 role) → uint256` — `view`

### Events
```
RoleGranted(bytes32 indexed role, address indexed account, address indexed sender)
RoleRevoked(bytes32 indexed role, address indexed account, address indexed sender)
```

---

## Major.sol

**Path:** `contracts/core/Major.sol`
**Purpose:** Registry of academic majors. Students reference `Major.id` (uint256)
instead of a free-form string, giving referential integrity and O(1) lookups.
**Access:** `onlyAuth` — University address or deployer only.

### Struct: `MajorInfo`

| Field | Type | Notes |
|-------|------|-------|
| `id` | `uint256` | Auto-incremented from 1 |
| `code` | `string` | Short uppercase key: "CS", "AI", "IT" |
| `name` | `string` | Full name: "Computer Science" |
| `description` | `string` | Optional |
| `active` | `bool` | False after deactivateMajor |

### Key storage

| Variable | Purpose |
|----------|---------|
| `codeToId[code]` | Unique code → id reverse lookup |
| `isActive[id]` | Separate bool for O(1) existence checks |
| `allMajors[]` | ID list for enumeration |

### Functions

#### `setUniversity(address)` — deployer only, one-time
Binds to University. Cannot be changed after set.

#### `addMajor(code, name, desc) → uint256` — onlyAuth
Reverts if `code` already exists (`codeToId[code] != 0`).

#### `updateMajor(id, name, desc)` — onlyAuth
Empty strings are silently ignored (partial update semantics).

#### `deactivateMajor(id)` — onlyAuth
Soft delete. Existing `StudentInfo.majorId` values are unaffected — students
already assigned to this major retain their record. New students cannot be
assigned to it because `University.addStudent` checks `maj.isActive(majorId)`.

#### `getMajor(uint256) → MajorInfo` — view
Reverts with `"Major: not found"` if inactive.

#### `getMajorByCode(string) → MajorInfo` — view

#### `getAllMajors() → uint256[]` — view
Returns all IDs including deactivated ones. Filter on `isActive` client-side.

---

## Professor.sol

**Path:** `contracts/core/Professor.sol`
**v1 bug fixed:** `professorAddress` was `msg.sender` at call time. Since
University was the caller, all professors shared the deployer's address and
`addressToId` reverse-lookup was broken (always returned the last-added professor).
Now `professorAddress` is an explicit parameter with a `require(addressToId[addr] == 0)`
uniqueness constraint.

### Struct: `ProfessorInfo`

| Field | Type | Notes |
|-------|------|-------|
| `id` | `uint256` | Auto-incremented from 1 |
| `professorAddress` | `address` | The professor's own EOA — unique |
| `name` | `string` | |
| `department` | `string` | |
| `active` | `bool` | |

### Functions

#### `addProfessor(name, dept, addr) → uint256` — onlyAuth
`addr` must be non-zero and not already registered.
When called via University, INSTRUCTOR_ROLE is automatically granted to `addr`.

#### `updateProfessor(id, name, dept, newAddr)` — onlyAuth
Pass `address(0)` for `newAddr` to leave address unchanged.
Address change updates both old and new `addressToId` entries.

#### `removeProfessor(id)` — onlyAuth
Called by `University.deleteProfessor` after cascade-deleting courses.
Clears `addressToId[professorAddress]`.

#### `getProfessorIdByAddress(address) → uint256` — view
Used by `updateStudentMark` to verify an INSTRUCTOR_ROLE caller owns the course.
Reverts if address not registered or professor inactive.

---

## Student.sol

**Path:** `contracts/core/Student.sol`
**v1 change:** `major` (free `string`) replaced by `majorId` (`uint256` ref to `Major.id`).
`walletAddress` field added for optional student EOA / reverse lookup.

### Struct: `StudentInfo`

| Field | Type | Notes |
|-------|------|-------|
| `id` | `uint256` | Auto-incremented from 1 |
| `name` | `string` | |
| `majorId` | `uint256` | References `Major.id` |
| `year` | `uint256` | Enrollment year, e.g. 2024 |
| `academicSupervisor` | `address` | Professor's EOA (resolved in University) |
| `walletAddress` | `address` | Student's own EOA (optional, may be zero) |
| `active` | `bool` | |

### Functions

#### `addStudent(name, majorId, year, supervisor, wallet) → uint256` — onlyAuth
`wallet` may be `address(0)` if the student has no on-chain wallet.
When `wallet` is set, `addressToId[wallet] = id` is recorded.

#### `updateStudent(id, name, majorId, year, supervisor, wallet)` — onlyAuth
Zero/empty values are skipped (partial update).
Wallet address change clears old `addressToId` entry.

#### `deleteStudent(id)` — onlyAuth
Swap-and-pop on `allStudents`. `University.deleteStudent` calls
`_dropStudentEnrollments` before this to unenroll from all courses.

#### `getStudentByAddress(address) → StudentInfo` — view
Reverse lookup by wallet. Reverts if no student mapped.

---

## Course.sol

**Path:** `contracts/core/Course.sol`
**Dependencies:** Professor.sol (constructor injection, stored as `immutable`).

### Struct: `CourseInfo`

| Field | Type | Notes |
|-------|------|-------|
| `id` | `string` | User-defined: "CS101", "AI301" |
| `name` | `string` | Full name |
| `professorId` | `uint256` | Owning professor |
| `active` | `bool` | |

### Key design notes

- String keys require `keccak256` comparison for equality — gas cost is constant
  regardless of string length.
- `professorCourses[professorId]` maintains an inverse index so `getCoursesByProfessor`
  is O(N) for N courses per professor (not O(total courses)).
- `exists[courseId]` is a separate bool for O(1) existence checks in Enrollment.

### Functions

#### `createCourse(id, name, profId)` — onlyAuth
Validates `professorContract.isActive(profId)`. Reverts on duplicate `id`.

#### `reassignCourse(id, newProfId)` — onlyAuth
Removes course from old professor's `professorCourses` list, adds to new one.
No-op if `newProfId == courses[id].professorId`.

#### `deleteCourse(id)` — onlyAuth
Removes from `professorCourses[profId]` and `allCourses`. Sets `active = false`.
`University._dropCourse` unenrolls all students before calling this.

#### `getCoursesByProfessor(profId) → CourseInfo[]` — view
Used by `University.deleteProfessor` for cascade.

---

## Enrollment.sol

**Path:** `contracts/core/Enrollment.sol`
**v1 bug fixed:** `_swapPop` was called but did NOT update the displaced element's
index field. Subsequent deletions used stale indices, causing wrong elements to be
removed. Fixed with `_pop(arr, key, which)` that updates the correct index field.

### Struct: `EnrollmentRecord`

| Field | Type | Notes |
|-------|------|-------|
| `studentId` | `uint256` | |
| `courseId` | `string` | |
| `semester` | `string` | "spring2025", "autumn2026" |
| `mark` | `uint8` | 0–100; 0 = not yet graded |
| `active` | `bool` | False after unenrollment |
| `studentArrayIndex` | `uint256` | Position in `studentEnrollmentKeys[sid]` |
| `courseArrayIndex` | `uint256` | Position in `courseEnrollmentKeys[cid]` |
| `semesterArrayIndex` | `uint256` | Position in `studentSemesterKeys[sid][sem]` |

The three index fields exist for O(1) swap-and-pop deletion. Without them,
finding an element to remove requires O(N) linear scan.

### Enrollment key

```solidity
keccak256(abi.encodePacked(studentId, courseId, semester))
```

Including `semester` in the key means `(1, "CS101", "spring2025")` and
`(1, "CS101", "spring2026")` are two different records — the same student
can retake the same course in a different semester.

### Storage

```
enrollments[key]                              → EnrollmentRecord
studentEnrollmentKeys[studentId]              → bytes32[]  all keys for student
courseEnrollmentKeys[courseId]                → bytes32[]  all keys for course
studentSemesterKeys[studentId][semester]      → bytes32[]  keys for student+semester
studentSemesters[studentId]                   → string[]   ordered semester list
studentHasSemester[studentId][semester]       → bool       dedup guard
```

### Functions

#### `enrollStudent(sid, cid, sem)` — onlyAuth
Creates record with three index fields recording current array lengths.
Tracks first appearance of semester for the student.

#### `unenrollStudent(sid, cid, sem)` — onlyAuth
Calls `_pop(arr, key, which)` three times — once for each index array.
`_pop` swaps the last element into the deleted slot and updates its index field.
Sets `enrollments[key].active = false`.

#### `updateMark(sid, cid, sem, mark)` — onlyAuth
`mark` must be 0–100. Enrollment must be active.

#### `getStudentEnrollments(sid) → EnrollmentRecord[]` — view
All records across all semesters.

#### `getStudentSemesterEnrollments(sid, sem) → EnrollmentRecord[]` — view
Records for one specific semester only.

#### `getStudentSemesters(sid) → string[]` — view
Insertion-ordered list. Remains stable even after unenrollments — the semester
entry is kept to preserve history even if all its courses are dropped.

#### `calculateGPA(sid) → (totalMarks, count)` — view
Returns raw totals so the caller (University or Python) can compute the average.
Only counts `active` records with `mark > 0`.

---

## University.sol

**Path:** `contracts/core/University.sol`
**Purpose:** Single external entry point. All external callers interact ONLY here.
Enforces RBAC. Routes to sub-contracts. Executes cascades on delete.

### Constructor

```solidity
constructor(address _ac, address _maj, address _stu,
            address _prof, address _crs, address _enr)
```

All six addresses stored as `immutable` — inlined in bytecode, not in storage.
This reduces both bytecode size and runtime gas vs `public` storage slots.

### Modifiers

| Modifier | Passes if |
|----------|-----------|
| `onlyAdmin()` | `ac.hasRole(ADMIN, msg.sender)` |
| `onlyReg()` | ADMIN or REGISTRAR |
| `onlyInstr()` | ADMIN, REGISTRAR, or INSTRUCTOR |

### Access Matrix

| Operation | ADMIN | REGISTRAR | INSTRUCTOR |
|-----------|:-----:|:---------:|:----------:|
| Grant / revoke roles | ✓ | ✗ | ✗ |
| Add / update / deactivate major | ✓ | ✗ | ✗ |
| Add / update professor | ✓ | ✓ | ✗ |
| Delete professor (cascade) | ✓ | ✗ | ✗ |
| Add / update / delete student | ✓ | ✓ | ✗ |
| Create / update / delete course | ✓ | ✓ | ✗ |
| Reassign course | ✓ | ✓ | ✗ |
| Enroll / unenroll / batch enroll | ✓ | ✓ | ✗ |
| Update mark (own courses) | ✓ | ✓ | ✓ |
| Update mark (any course) | ✓ | ✓ | ✗ |
| All view functions | ✓ | ✓ | ✓ |

### Cascade behaviours

**`deleteProfessor(id)`** — ADMIN only:
1. Get all courses via `crs.getCoursesByProfessor(id)`.
2. For each course: call `_dropCourse(id)` → unenroll all students → delete course.
3. Revoke `INSTRUCTOR_ROLE` from professor's address.
4. Delete professor record.

**`deleteStudent(id)`** — REGISTRAR+:
1. Get all enrollments via `enr.getStudentEnrollments(id)`.
2. Unenroll from each active one.
3. Delete student record.

**`deleteCourse(id)`** — REGISTRAR+:
1. Get all enrollments via `enr.getCourseEnrollments(id)`.
2. Unenroll each active student.
3. Delete course record.

### Instructor mark-update scoping

```solidity
function updateStudentMark(...) external onlyInstr {
    if (!ac.hasRole(ADMIN, msg.sender) && !ac.hasRole(REGISTRAR, msg.sender)) {
        uint256 myId = prof.getProfessorIdByAddress(msg.sender);
        require(crs.getCourse(cid).professorId == myId, "not your course");
    }
    enr.updateMark(sid, cid, sem, mark);
}
```

INSTRUCTOR callers must own the course being graded. Ownership is verified
by resolving their professor record from their wallet address.

### Size budget (after optimizer, 200 runs)

| Contract | Compiled size | % of 24 KB limit |
|----------|:-------------:|:----------------:|
| AccessRegistry | ~2.3 KB | 9% |
| Major | ~4.6 KB | 19% |
| Professor | ~4.9 KB | 20% |
| Student | ~5.1 KB | 21% |
| Course | ~6.9 KB | 28% |
| Enrollment | ~7.2 KB | 29% |
| **University** | **~14.2 KB** | **58%** |

University is the largest because it imports and delegates to all others.
At 58% of the limit there is headroom for ~10 KB of additional features.
