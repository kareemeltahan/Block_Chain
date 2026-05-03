# University-Web3 — Project Presentation

> A blockchain-backed university management system.  
> All authoritative state lives immutably on-chain. A Python layer provides a typed, validated, access-controlled API over those contracts.

---

## Table of Contents

1. [System at a Glance](#1-system-at-a-glance)
2. [Original System — How v1 Worked](#2-original-system--how-v1-worked)
3. [What Changed and Why — 7 Categories](#3-what-changed-and-why--7-categories)
4. [New System — How the Final Version Works](#4-new-system--how-the-final-version-works)
5. [Change Details — Every Category In Full](#5-change-details--every-category-in-full)
   - [5.1 Major Registry](#51-major-registry)
   - [5.2 Access Control](#52-access-control)
   - [5.3 Enrollment Upgrades](#53-enrollment-upgrades)
   - [5.4 Datasource Architecture](#54-datasource-architecture)
   - [5.5 Compile & Deploy](#55-compile--deploy)
   - [5.6 Professor / Student / Course](#56-professor--student--course)
   - [5.7 Model Layer (types.py)](#57-model-layer-typespy)

---

## 1. System at a Glance

| Metric | Value |
|--------|-------|
| Smart Contracts | 7 |
| GPA Scale | 0.0 – 4.0 |
| Access Roles | 3 (ADMIN / REGISTRAR / INSTRUCTOR) |
| Bugs Fixed | 10 |

### What the System Manages

- Academic majors (CS, AI, IT, CYB, …) — first-class entities with referential integrity
- Professors with their own on-chain Ethereum addresses
- Students assigned to a major and an academic supervisor
- String-keyed courses owned by a professor
- Per-semester enrollment records — retakes supported
- Percentage marks (0–100) stored on-chain, exposed as 4.0-scale GPA in Python
- Role-based write access enforced entirely on-chain

### Architecture Layers

```
Application Code  (main.py / your scripts)
        │
        ▼
UniversityDataSource  ← single public Python facade
        │  composes five domain datasources
        ▼
BaseDataSource  ← shared _tx() / _call() infrastructure
        │  web3.py + signed transactions
        ▼
University.sol  ← on-chain entry-point facade
        │  RBAC via AccessRegistry on every write
        ▼
Major.sol  Professor.sol  Student.sol  Course.sol  Enrollment.sol
        │  all enforce onlyAuth (University or deployer)
        ▼
AccessRegistry.sol  ← ADMIN_ROLE / REGISTRAR_ROLE / INSTRUCTOR_ROLE
```

---

## 2. Original System — How v1 Worked

### v1 Contract Architecture

```
University.sol
    ├── Student.sol      ← no onlyAuthorized guard
    ├── Professor.sol    ← no onlyAuthorized guard
    ├── Course.sol       ← no onlyAuthorized guard
    └── Enrollment.sol   ← no onlyAuthorized guard

⚠ Any address knowing a sub-contract address could write directly to it.
⚠ University.sol's access checks were completely bypassable.
```

### v1 Python Architecture

```
university_datasource.py  ← 700+ lines, all domains in one class
    ├── student methods
    ├── professor methods
    ├── course methods
    └── enrollment methods

⚠ Returns raw dicts — positional field access, no type safety
⚠ Module-level config snapshot — stale writes on rapid deploys
```

### What v1 Could Do

- Add and manage professors, students, courses
- Enroll students in courses and record marks
- Cascade-delete when a professor, student, or course was removed
- Authorize individual addresses as instructors (binary flag)

### Critical Bugs in v1

| # | Bug | Severity |
|---|-----|----------|
| 1 | University.sol compiled to 34 KB — over the 24 KB EVM limit | Critical |
| 2 | Enrollment deletion silently corrupted index state | Critical |
| 3 | All professors shared the deployer's address | Critical |
| 4 | Sub-contracts had no access guard — open to direct writes | Critical |
| 5 | Enrollment modifier was a tautology (`msg.sender == msg.sender`) | Critical |
| 6 | Config writes used a stale module-level snapshot | High |
| 7 | Role hashes computed as raw bytes, not keccak256 | High |
| 8 | `get_courses_by_professor` mapped `active` field to `studentCount` | Medium |
| 9 | Nonce fetched per-transaction — collisions on rapid deploys | High |
| 10 | Zero-address comparison was case-sensitive — re-binding on every run | Low |

---

## 3. What Changed and Why — 7 Categories

| # | Category  One-Line Summary |
|---|----------|------------|-----------------|
| 1 | Major Registry | New first-class entity replacing free-form strings |
| 2 | Access Control| Binary flag replaced by three-tier on-chain RBAC |
| 3 | Enrollment Upgrades | Semester dimension added + critical deletion bug fixed |
| 4 | Datasource Architecture | 700-line monolith decomposed into layered modules |
| 5 | Compile & Deploy | Optimizer guarantee + nonce tracking + two-phase post-deploy binding |
| 6 | Professor / Student / Course | Three targeted correctness fixes on existing contracts |
| 7 | Model Layer (types.py) | Typed dataclasses + 4.0-scale GPA replacing raw dicts |

---

## 4. New System — How the Final Version Works

### Final Contract Architecture

```
AccessRegistry.sol
    ADMIN_ROLE / REGISTRAR_ROLE / INSTRUCTOR_ROLE
    ↑ University.sol reads this on every protected call

University.sol  (entry-point facade)
    onlyAdmin / onlyReg / onlyInstr modifiers
    ├── Major.sol        ● NEW   — isActive(majorId) validation
    ├── Professor.sol    ▲ FIXED — explicit address, uniqueness constraint
    ├── Student.sol      ▲ FIXED — majorId ref, walletAddress
    ├── Course.sol       ▲ FIXED — onlyAuth guard added
    └── Enrollment.sol   ▲ FIXED — semester key, correct swap-and-pop

All sub-contracts enforce: require(msg.sender == university || msg.sender == deployer)
```

### Final Python Architecture

```
UniversityDataSource  (public facade — what callers use)
    ├── MajorDataSource
    ├── ProfessorDataSource
    ├── StudentDataSource
    ├── CourseDataSource
    ├── EnrollmentDataSource
    └── AdminDataSource
        all extend BaseDataSource (_tx / _call)

Supporting modules:
    settings.py   — atomic config reads/writes
    provider.py   — Web3 singleton
    registry.py   — ContractType enum + deployment order
    verifier.py   — is_deployed() bytecode check
    types.py      — MajorInfo, ProfessorInfo, StudentInfo, CourseInfo,
                    EnrollmentRecord, SemesterSummary + GPA conversion
```

### A Write Operation End-to-End

```
ds.enroll("spring2025", 1, "CS101")
    │
    ▼  Python validation (student_id > 0, course_id non-empty, semester non-empty)
EnrollmentDataSource.enroll(student_id=1, course_id="CS101", semester="spring2025")
    │
    ▼  _tx(fn) builds {"from": deployer_address}, calls fn.transact()
web3.py signs and submits transaction
    │
    ▼  on-chain
University.enrollStudentInCourse(1, "CS101", "spring2025")
    │  [onlyReg] → ac.hasRole(ADMIN or REGISTRAR, msg.sender) ✓
    │  require stu.isActive(1)     ✓
    │  require crs.exists("CS101") ✓
    │  require !alreadyEnrolled    ✓
    ▼
Enrollment.enrollStudent(1, "CS101", "spring2025")
    │  [onlyAuth] → msg.sender == university ✓
    │  creates EnrollmentRecord with 3 index fields
    │  pushes key to studentEnrollmentKeys[1]
    │  pushes key to courseEnrollmentKeys["CS101"]
    │  pushes key to studentSemesterKeys[1]["spring2025"]
    ▼
event StudentEnrolled(1, "CS101", "spring2025") emitted
```

### Deployment Sequence (9 steps)

```
Step 1   AccessRegistry.sol    — no constructor args
Step 2   Major.sol             — no constructor args
Step 3   Professor.sol         — no constructor args
Step 4   Student.sol           — no constructor args
Step 5   Course.sol            — constructor(Professor address)
Step 6   Enrollment.sol        — constructor(Student address, Course address)
Step 7   University.sol        — constructor(all six above)
─────────────────────────────────────────────────────────────────
Step 8   setUniversity()       — called on Major, Prof, Stu, Course, Enrollment
                                  locks each sub-contract to University-only writes
Step 9   grantRole(ADMIN_ROLE, University)
                               — called on AccessRegistry by deployer EOA
                                  allows University's internal role calls to succeed
```

### GPA Scale

Marks stored on-chain as `uint8` (0–100). Conversion to 4.0 scale done client-side.

| Range | Letter | Points | | Range | Letter | Points |
|-------|--------|--------|-|-------|--------|--------|
| 97–100 | A+ | 4.0 | | 73–76 | C | 2.0 |
| 93–96 | A | 4.0 | | 70–72 | C– | 1.7 |
| 90–92 | A– | 3.7 | | 67–69 | D+ | 1.3 |
| 87–89 | B+ | 3.3 | | 63–66 | D | 1.0 |
| 83–86 | B | 3.0 | | 60–62 | D– | 0.7 |
| 80–82 | B– | 2.7 | | 0–59 | F | 0.0 |
| 77–79 | C+ | 2.3 | | | | |

> **Critical:** `avg(marks) → convert` ≠ `avg(convert(marks))`.  
> A student with marks 90 and 80 averages to 85 → 3.0 by the wrong method.  
> The correct method: `avg(mark_to_gpa(90), mark_to_gpa(80)) = avg(3.7, 2.7) = 3.2`.  
> Each mark must be converted individually before averaging.

---

## 5. Change Details — Every Category In Full

---

### 5.1 Major Registry

**Summary:** New first-class entity replacing free-form strings

#### v1 — Problems

- `Student.major` was a raw `string`. `"Computer Science"`, `"CS"`, `"computer science"` were all valid and all different — no deduplication, no validation.
- No listing of available majors. No way to enumerate what programs exist at the university.
- Free strings are cosmetic labels — the system had no way to enforce or query them.

#### Final — What Changed

- Built `Major.sol` from scratch: full CRUD, unique code constraint (`codeToId` mapping), `isActive` flag, description field.
- `Student.major` (string) replaced by `Student.majorId` (uint256) referencing `Major.id`.
- `University.addStudent` now validates `maj.isActive(majorId)` before creating the student — invalid major IDs are rejected on-chain.
- Python gains `get_major_by_code("CS")` — O(1) lookup by short code.

#### Why It Matters

Referential integrity. A student with `major = "Compuutr Science"` is indistinguishable from a valid record at the data layer. Free strings can't be listed, validated, or enforced. A majorId reference is validated by the chain itself.

#### Migration

```python
# v1
ds.add_student("Alice", "Computer Science", year=2024, professor_id=1)

# Final — create major first, then reference by ID
ds.add_major("CS", "Computer Science")   # major.id = 1
ds.add_student("Alice", major_id=1, year=2024, professor_id=1)
```

---

### 5.2 Access Control

**Summary:** Binary flag replaced by three-tier on-chain RBAC

#### v1 — Problems

- `mapping(address => bool) authorizedInstructors` — two states: authorized or not. No hierarchy, no distinction between admin, registrar, instructor.
- Admin was identified by address equality to a hardcoded `immutable admin` variable. No role enumeration.
- `Enrollment.sol` modifiers contained `require(msg.sender == msg.sender || ...)` — a tautology. The modifier never blocked anything. Any address could call sub-contracts directly.

#### Final — What Changed

- Built `AccessRegistry.sol`: standalone RBAC with `ADMIN_ROLE`, `REGISTRAR_ROLE`, `INSTRUCTOR_ROLE`.
- Member lists maintained with swap-and-pop for O(1) revoke. `superAdmin` (deployer) permanently holds `ADMIN_ROLE` and cannot be stripped.
- `University.sol` has three modifiers reading live from AccessRegistry: `onlyAdmin`, `onlyReg`, `onlyInstr`.
- Instructor mark-scoping: if caller only holds `INSTRUCTOR_ROLE`, the contract verifies `course.professorId == getProfessorIdByAddress(msg.sender)` before allowing a mark update.
- Post-deploy: the deployer grants `ADMIN_ROLE` to the University contract on AccessRegistry so University's internal `grantRole`/`revokeRole` calls succeed.

#### Role Access Matrix

| Operation | ADMIN | REGISTRAR | INSTRUCTOR |
|-----------|:-----:|:---------:|:----------:|
| Grant / revoke roles | ✓ | ✗ | ✗ |
| Add / update major | ✓ | ✗ | ✗ |
| Add / update professor | ✓ | ✓ | ✗ |
| Delete professor | ✓ | ✗ | ✗ |
| Student CRUD | ✓ | ✓ | ✗ |
| Course CRUD | ✓ | ✓ | ✗ |
| Enroll / unenroll | ✓ | ✓ | ✗ |
| Update mark (own course) | ✓ | ✓ | ✓ |
| Update mark (any course) | ✓ | ✓ | ✗ |
| All reads | ✓ | ✓ | ✓ |

#### Why It Matters

The v1 access model had no hierarchy and a broken sub-contract guard. The tautology modifier meant anyone who discovered a sub-contract address could write data directly — without going through University.sol at all.

#### Migration

```python
# v1
ds.authorize_instructor("0xAddr")

# Final
ds.grant_role("REGISTRAR_ROLE",  "0xStaffAddr")
ds.grant_role("INSTRUCTOR_ROLE", "0xProfAddr")  # happens automatically on addProfessor
```

---

### 5.3 Enrollment Upgrades
 
**Summary:** Semester dimension added + critical deletion bug fixed

#### v1 — Problems

- Enrollment key: `keccak256(studentId, courseId)`. One record per student-course pair, ever. Retaking a course was impossible — the key already existed.
- No semester concept. All enrollments existed in one flat namespace.
- `_swapPop()` moved array elements but never updated the displaced element's index fields. After any unenrollment, subsequent deletions used stale indices — wrong elements were removed silently.
- Three correct `_removeFrom*Full()` functions were defined but **never called**. Dead code.

#### Final — What Changed

**Semester dimension:**
- Key changed to `keccak256(studentId, courseId, semester)`. Same course in a different semester = independent record.
- Added `studentSemesterKeys[sid][sem]`, `studentSemesters[sid]`, `studentHasSemester[sid][sem]` storage structures.
- New view functions: `getStudentSemesterEnrollments`, `getStudentSemesters`.
- `EnrollmentRecord` gains `semester` field and `semesterArrayIndex`.

**Swap-and-pop fix:**
- Replaced three broken/dead functions with one correct `_pop(arr, key, which)`.
- `which` parameter (0/1/2) tells the function which index field to update on the displaced element.
- Called three times per unenrollment — once per index array.

```solidity
// v1 — BROKEN: moved element, never updated its index
function _swapPop(bytes32[] storage arr, uint256 idx, bytes32 key) internal {
    bytes32 movedKey = arr[arr.length - 1];
    arr[idx] = movedKey;
    // enrollments[movedKey].studentArrayIndex still says arr.length - 1
    // but the element is now at idx — stale index
    arr.pop();
}

// Final — CORRECT
function _pop(bytes32[] storage arr, bytes32 key, uint8 which) internal {
    uint256 idx  = which == 0 ? enrollments[key].studentArrayIndex
                 : which == 1 ? enrollments[key].courseArrayIndex
                 :               enrollments[key].semesterArrayIndex;
    uint256 last = arr.length - 1;
    if (idx != last) {
        bytes32 moved = arr[last];
        arr[idx]      = moved;
        // Update the displaced element's index field:
        if      (which == 0) enrollments[moved].studentArrayIndex  = idx;
        else if (which == 1) enrollments[moved].courseArrayIndex   = idx;
        else                 enrollments[moved].semesterArrayIndex = idx;
    }
    arr.pop();
}
```

#### Why It Matters

The swap-and-pop bug was silent — it compiled, appeared to work, but every unenrollment left the index state corrupted. The next deletion would remove the wrong record. This is the type of bug that only surfaces in production under specific usage patterns.

#### Migration

```python
# v1
ds.enroll_student_in_course(student_id=1, course_id="CS101")
ds.update_student_mark(student_id=1, course_id="CS101", mark=88)

# Final — semester is the first argument
ds.enroll("spring2025", student_id=1, course_id="CS101")
ds.update_mark("spring2025", student_id=1, course_id="CS101", mark=88)

# New: per-semester queries
ds.get_semester_summary(student_id=1, semester="spring2025")
ds.get_full_transcript(student_id=1)  # all semesters
```

---

### 5.4 Datasource Architecture

**Summary:** 700-line monolith decomposed into layered modules

#### v1 — Problems

- `UniversityDataSource`: 700+ lines, all domains mixed — student, professor, course, enrollment methods all in one class.
- Direct `web3.py` calls scattered throughout — inconsistent error handling, no shared receipt-waiting logic.
- Module-level config: `config = get_config()` at import time. Seven sequential contract deploys each called `update_config()` with the same initial snapshot, overwriting previously saved addresses.
- All return values were raw `dict` or `tuple` — positional field access, silent `None` on typos.

#### Final — What Changed

```
BaseDataSource (base.py)
    _tx(fn, wait=True)   — signs, submits, waits for receipt, raises on revert
    _call(fn)            — view/pure call, no gas, consistent error wrapping

    └── MajorDataSource      (domain_ds.py)
    └── ProfessorDataSource  (domain_ds.py)
    └── StudentDataSource    (domain_ds.py)
    └── CourseDataSource     (domain_ds.py)
    └── EnrollmentDataSource (enrollment_ds.py)
    └── AdminDataSource      (admin_ds.py)

UniversityDataSource (university_ds.py)
    — thin facade composing the six above
    — the ONLY class application code touches
```

Supporting infrastructure:

| File | Responsibility |
|------|---------------|
| `settings.py` | Load/save config. Reads fresh from disk before every write. Atomic `os.replace()` writes. |
| `provider.py` | Web3 singleton. Lazy init. Derives deployer_address from key on first connect. |
| `registry.py` | `ContractType` enum. Deployment order. `NEEDS_BINDING` list. |
| `verifier.py` | `is_deployed(address)` — checks bytecode via `eth_getCode`. |

#### Why It Matters

A 700-line class with mixed domains is impossible to test, extend, or reason about in isolation. The stale-config bug was invisible in single-contract tests but destroyed deployment state whenever more than one contract was deployed in a session.

---

### 5.5 Compile & Deploy
  
**Summary:** Optimizer guarantee + nonce tracking + two-phase post-deploy binding

This section requires the most explanation because three separate mechanisms each independently failed — and each failure's root cause is non-obvious.

---

#### Problem 1 — The Silent Optimizer Failure

**v1 code:**
```python
result = compile_files(
    [str(f) for f in CONTRACT_FILES],
    output_values=["abi", "bin"],
    solc_version=SOLC_VERSION,
    optimize=True,           # silently ignored on Windows
    optimize_runs=200,       # silently ignored on Windows
)
```

`compile_files` is a py-solc-x high-level wrapper. On Linux it works. On Windows and several versions of py-solc-x, it passes these keyword arguments through an internal argument-builder that has a known bug: the `--optimize` flag is omitted from the `subprocess.Popen` call. The optimizer is never applied. Unoptimized bytecode is emitted.

**EIP-170: the hard limit**

EIP-170 (active since Spurious Dragon, 2016) caps deployed contract bytecode at exactly **24,576 bytes**. This is enforced at the EVM level — the node rejects the deployment transaction before the contract ever lands on-chain:

```
web3.exceptions.Web3RPCError: {'code': -32603, 'message': 'EVM error CreateContractSizeLimit'}
```

University.sol imports six other contracts. Without the optimizer, the compiler generates duplicate ABI encoding/decoding stubs for each imported struct — one copy per import site. The optimizer deduplicates these stubs, inlines small functions, and eliminates dead code.

| | Size | % of limit |
|-|------|-----------|
| Without optimizer | 34,192 bytes | 139% — **CRASH** |
| With optimizer (200 runs) | ~14,000 bytes | 57% — **OK** |

**Final fix — `compile_standard`:**
```python
std_input = {
    "language": "Solidity",
    "sources": sources,
    "settings": {
        "optimizer": {
            "enabled": True,
            "runs": 200     # optimise for repeated runtime calls
        },
        "outputSelection": {"*": {"*": ["abi", "evm.bytecode.object"]}}
    }
}
result = compile_standard(std_input, solc_version=SOLC_VERSION, allow_paths=[str(ROOT)])
```

`compile_standard` serializes the Standard JSON dict and passes it as stdin to the `solc` binary via `--standard-json`. solc reads `optimizer.enabled` and `optimizer.runs` directly from the JSON. No py-solc-x wrapper, no OS-specific bug.

---

#### Problem 2 — Nonce Collisions on Rapid Sequential Deploys

**What a nonce is:** Every Ethereum transaction carries a nonce — the count of confirmed transactions sent from that address. Nodes reject transactions with a nonce they've already seen or processed.

**v1 pattern:**
```python
for ct in DEPLOYMENT_ORDER:
    nonce = w3.eth.get_transaction_count(deployer)  # called per deploy
    tx = factory.constructor(...).build_transaction({"nonce": nonce, ...})
    w3.eth.send_raw_transaction(signed.raw_transaction)
    # tx1 is submitted but not yet mined
    # next iteration: eth_getTransactionCount still returns N (tx1 not confirmed)
    # tx2 gets nonce = N again → collision
```

`eth_getTransactionCount` returns the count of *confirmed* transactions, not pending ones. On a fast local node like Anvil with default settings, transactions are submitted faster than they mine. The second call returns the same value as the first.

**Error:**
```
ValueError: replacement transaction underpriced
```

This error means the node received two transactions with the same `(from, nonce)` pair and rejected the second as a duplicate attempt to replace the first.

**Final fix:**
```python
# Fetch ONCE at the start of the entire deployment
nonce = w3.eth.get_transaction_count(deployer)

for ct in DEPLOYMENT_ORDER:
    contract = deploy_one(ct, args, nonce)  # use current nonce
    nonce += 1                              # increment locally — no race condition
```

The deployer owns the counter. No node calls between transactions. Zero collision risk across all 9 deployment transactions.

---

#### Problem 3 — University Needs ADMIN_ROLE on AccessRegistry

This is the most non-obvious problem because it only becomes visible after the other two are fixed.

**The call chain:**
```
External caller → University.addProfessor(name, dept, addr)
                      │  [onlyReg] checks msg.sender = caller address ✓
                      │
                      ▼  internal call
                  AccessRegistry.grantRole(INSTRUCTOR_ROLE, addr)
                      │  [onlyAdmin] checks msg.sender = ???
```

When University calls `AccessRegistry.grantRole()`, `msg.sender` is **the University contract address** — not the original external caller. The external caller's address is gone.

`AccessRegistry.grantRole` has `modifier onlyAdmin` which checks `_has[ADMIN_ROLE][msg.sender]`. The University contract address holds no roles by default. So the check fails, and every `addProfessor` call reverts with `"AR: admin only"`.

**Why it's non-obvious:** Reading `University.addProfessor` in isolation, it looks like a simple registrar-guarded function that delegates to a sub-contract. You have to trace the internal call chain and realise that `msg.sender` changes at each hop.

**Final fix — post-deploy step:**
```python
# After University is deployed, deployer (who IS superAdmin) grants University ADMIN_ROLE
ADMIN_ROLE = Web3.keccak(text="ADMIN_ROLE")
tx = access.functions.grantRole(ADMIN_ROLE, uni_addr).build_transaction({
    "from":  deployer,
    "nonce": nonce,
})
```

**Security note:** This does NOT open a privilege escalation vector. University's own `onlyAdmin` and `onlyReg` modifiers still control what external callers can trigger. The ADMIN_ROLE grant only allows the contract-to-contract call to succeed when an already-authenticated external call triggers it.

---

#### Problem 4 — Stale Config Writes

**v1:**
```python
# utils/__init__.py — loaded once at import time
config = get_config()   # snapshot: all contract addresses = ""

def update_config():
    from . import config        # still the import-time snapshot
    with open(path, "w") as f:
        json.dump(config, f)    # writes the snapshot — not the live state
```

Seven sequential deploys → seven calls to `update_config()` → each writes the same initial snapshot → contract 7 overwrites the previous 6 addresses with empty strings.

**Final fix:**
```python
def set_contract_address(name: str, address: str) -> None:
    cfg = load()               # ALWAYS reads fresh from disk
    cfg["contracts"][name] = address
    save(cfg)                  # atomic write via os.replace()
```

`os.replace()` writes to a temp file first, then atomically renames it over the target. Partial writes are impossible. Each of the 9 deployment transactions saves exactly one address without touching the others.

---

#### The Complete Deployment Timeline

```
T=0   nonce = eth_getTransactionCount(deployer)   ← one call, store locally

T=1   deploy AccessRegistry   nonce=0  → save address → nonce=1
T=2   deploy Major            nonce=1  → save address → nonce=2
T=3   deploy Professor        nonce=2  → save address → nonce=3
T=4   deploy Student          nonce=3  → save address → nonce=4
T=5   deploy Course(Prof)     nonce=4  → save address → nonce=5
T=6   deploy Enrollment(S,C)  nonce=5  → save address → nonce=6
T=7   deploy University(all)  nonce=6  → save address → nonce=7

── post-deploy binding ──────────────────────────────────────────

T=8   Major.setUniversity(uni)         nonce=7  → nonce=8
T=9   Professor.setUniversity(uni)     nonce=8  → nonce=9
T=10  Student.setUniversity(uni)       nonce=9  → nonce=10
T=11  Course.setUniversity(uni)        nonce=10 → nonce=11
T=12  Enrollment.setUniversity(uni)    nonce=11 → nonce=12
T=13  AccessRegistry.grantRole(ADMIN, uni)  nonce=12 → DONE
```

All 13 transactions use a locally-tracked nonce. No node calls between T=1 and T=13.

#### Why It Matters — All Three Together

These three problems compounded in a specific way: (1) was OS-specific — it worked on Linux CI but crashed on every Windows machine; (2) only triggered when deploying 7+ contracts rapidly — never appeared in single-contract unit tests; (3) only appeared after (1) and (2) were fixed, because deployment never got far enough to reach `addProfessor`.

---

### 5.6 Professor / Student / Course

**Summary:** Three targeted correctness fixes on existing contracts

#### Professor — Address Ownership Bug

**v1:**
```solidity
function addProfessor(string memory _name, string memory _department)
    external returns (uint256)
{
    professors[id] = ProfessorInfo({
        professorAddress: msg.sender,  // ← University is the caller, not the professor
        ...
    });
    addressToId[msg.sender] = id;      // all professors map to deployer address
```

Since University called `addProfessor`, `msg.sender` was the University contract (or deployer). Every professor got the deployer's address. `addressToId` was overwritten on every add — only the last professor was findable by address. `getProfessorIdByAddress` was effectively broken.

**Final:**
```solidity
function addProfessor(string calldata name, string calldata dept, address addr)
    external onlyAuth returns (uint256)
{
    require(addr != address(0),        "Prof: zero address");
    require(addressToId[addr] == 0,    "Prof: address taken");  // unique constraint
    professors[id] = ProfessorInfo(id, addr, name, dept, true);
    addressToId[addr] = id;
```

#### Student — Major Reference + Wallet

| Field | v1 | Final |
|-------|-----|-------|
| `major` | `string` — free text | removed |
| `majorId` | — | `uint256` referencing `Major.id` |
| `walletAddress` | — | `address` (optional student EOA) |

`getStudentByAddress(address)` reverse lookup added.

#### Course — Unguarded Write Functions

**v1:** No `onlyOwner` or equivalent. Any address could call `Course.createCourse()`, `Course.deleteCourse()`, etc. directly.

**Final:** `onlyAuth` modifier added to all write functions. `setUniversity()` binding added so the guard activates post-deploy.

---

### 5.7 Model Layer (types.py)

**Summary:** Typed dataclasses + 4.0-scale GPA replacing raw dicts

#### v1 — Problems

- All contract calls returned raw `dict` or `tuple` — access by string key or integer index.
- No GPA computation existed.
- No type safety: `student['academicSupervisour']` (typo) returns silent `None`.

#### Final — What Changed

**Typed dataclasses** mirror every on-chain struct:

```python
@dataclass
class EnrollmentRecord:
    student_id:   int
    course_id:    str
    semester:     str    # "spring2025"
    mark:         int    # 0–100 on-chain
    active:       bool

    @property
    def gpa_points(self) -> float:
        return mark_to_gpa(self.mark) if self.mark > 0 else 0.0

    @property
    def grade(self) -> str:
        return letter_grade(self.mark) if self.mark > 0 else ""
```

**GPA conversion:**

```python
_GPA_TABLE = [
    (97, 4.0), (93, 4.0), (90, 3.7),
    (87, 3.3), (83, 3.0), (80, 2.7),
    (77, 2.3), (73, 2.0), (70, 1.7),
    (67, 1.3), (63, 1.0), (60, 0.7),
    (0,  0.0),
]

def mark_to_gpa(mark: int) -> float:
    for threshold, points in _GPA_TABLE:
        if mark >= threshold:
            return points
    return 0.0
```

**Why convert per-record, not on the average:**

```
Student marks: 90, 80
Wrong method:  avg(90, 80) = 85  →  mark_to_gpa(85) = 3.0 (B)
Correct method: avg(mark_to_gpa(90), mark_to_gpa(80))
              = avg(3.7, 2.7)
              = 3.2  ← different result, and correct
```

The letter-grade scale has discrete steps. An 89 (B+, 3.3) and an 83 (B, 3.0) average to 86 raw — which is B (3.0). But the correct GPA is `avg(3.3, 3.0) = 3.15`. The non-linearity means the order of operations matters.

**`SemesterSummary`** provides per-semester aggregate:

```python
sem = ds.get_semester_summary(1, "spring2025")
sem.gpa           # 3.15  (4.0 scale, correct per-record conversion)
sem.course_ids    # ["CS101", "MATH101"]
sem.total_courses # 2
sem.graded_count  # 2
```

---

## Quick Reference

### Run Sequence

```bash
# 1. Start local chain
anvil

# 2. Configure
cp config.example.json config.json

# 3. Compile (must print ✓ before proceeding)
python scripts/compile.py

# 4. Deploy + demo
python main.py
```

### Common Errors

| Error | Root Cause | Fix |
|-------|-----------|-----|
| `EVM error CreateContractSizeLimit` | Optimizer not applied | Use `compile_standard` — this script does it automatically |
| `AccessRegistry: admin only` on addProfessor | University lacks ADMIN_ROLE on AccessRegistry | Deployer must call `grantRole(ADMIN_ROLE, University)` post-deploy |
| `replacement transaction underpriced` | Nonce collision on rapid deploys | Fetch nonce once, increment locally |
| `Professor: address taken` | Duplicate professor address | Each professor needs a unique EOA |
| Config shows empty addresses after deploy | Stale module-level config snapshot | Use `settings.set_contract_address()` which reads fresh before each write |
