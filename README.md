# University-Web3

A blockchain-backed university management system built on Ethereum.
All authoritative state — students, professors, courses, enrollments, grades —
lives immutably on-chain. A Python layer provides a typed, validated,
access-controlled API over those contracts.

---

## What it does

| Domain | Capabilities |
|--------|-------------|
| **Majors** | Register academic programs (CS, AI, IT, CYB, …). Students reference a major by ID — no free-form strings, full referential integrity. |
| **Professors** | Register faculty with their own Ethereum address. Each professor is uniquely identified on-chain. Adding a professor automatically grants them the `INSTRUCTOR_ROLE`. |
| **Students** | Register students assigned to a major and an academic supervisor (professor). Optional wallet address for on-chain identity. |
| **Courses** | Create string-keyed courses (e.g. "CS101") owned by a professor. Supports reassignment and cascade-delete. |
| **Enrollment** | Enroll students in courses per semester. Same student can retake the same course in a different semester — each is an independent record. Batch enrollment in one transaction. |
| **Grades** | Store percentage marks (0–100) on-chain per enrollment. Exposed as 4.0-scale GPA in Python. Per-semester and cumulative GPA computed automatically. |
| **Transcripts** | Full academic history: all semesters in order, each with courses, marks, letter grades, and GPA. |
| **Access Control** | Three-tier RBAC: ADMIN > REGISTRAR > INSTRUCTOR. Enforced on-chain. Instructors can only grade their own courses. |

---

## Architecture

```
Application code  →  UniversityDataSource (Python facade)
                           │
                      web3.py + signed txs
                           │
                   University.sol  (on-chain facade)
                      RBAC via AccessRegistry
                           │
          ┌────────────────┼──────────────────────┐
       Major.sol    Professor.sol             Student.sol
       Course.sol   Enrollment.sol        AccessRegistry.sol
```

**Key design principle:** All writes flow through `University.sol`. Sub-contracts
enforce `onlyAuthorized` (University or deployer only), so access control
in University cannot be bypassed by calling sub-contracts directly.

---

## Quick Start

### Prerequisites

- Python 3.11+
- [Foundry](https://foundry.paradigm.xyz) for the local chain (`anvil`)
- `pip install py-solc-x web3`

### 1 — Start a local chain

```bash
anvil
```

Anvil runs a local EVM node at `http://127.0.0.1:8545` and prints 10 pre-funded
accounts with private keys. Leave this terminal open.

### 2 — Install dependencies

```bash
pip install -r requirements.txt
```

### 3 — Configure

```bash
cp config.example.json config.json
```

The example config already contains Anvil's well-known account 0 key.
No changes needed for a default Anvil setup.

> ⚠️ Never use real private keys. Anvil keys control nothing of value.

### 4 — Compile contracts

```bash
python scripts/compile.py
```

Uses `compile_standard` (Standard JSON interface) to guarantee the solc
optimizer is applied on all platforms including Windows.

Expected output:
```
Compiling 7 contracts
  solc 0.8.20  ·  optimizer ON  ·  200 runs

  AccessRegistry       2,341 B  [████░░░░░░░░░░░░░░░░]   9.5%
  Course               6,891 B  [█████░░░░░░░░░░░░░░░]  28.1%
  Enrollment           7,203 B  [█████░░░░░░░░░░░░░░░]  29.3%
  Major                4,612 B  [████░░░░░░░░░░░░░░░░]  18.8%
  Professor            4,890 B  [████░░░░░░░░░░░░░░░░]  19.9%
  Student              5,101 B  [████░░░░░░░░░░░░░░░░]  20.8%
  University          14,230 B  [███████████░░░░░░░░░]  57.9%

  ✓ All contracts within 24,576-byte EVM limit.
```

### 5 — Run the demo

```bash
python main.py
```

First run deploys all 7 contracts, binds sub-contracts, and grants roles.
Subsequent runs reuse addresses from `config.json` and skip deployment.

---

## API Usage

```python
from python.datasource.university_ds import UniversityDataSource

ds = UniversityDataSource()

# ── Majors ────────────────────────────────────────────────────────────────────
ds.add_major("CS",  "Computer Science",       "Algorithms and software")
ds.add_major("AI",  "Artificial Intelligence","ML, NLP, computer vision")
cs = ds.get_major_by_code("CS")           # MajorInfo(id=1, code='CS', ...)

# ── Professors ────────────────────────────────────────────────────────────────
# Each professor needs a unique Ethereum address (not the deployer's)
ds.add_professor("Dr. Smith", "Computer Science", "0xProfAddr")
# INSTRUCTOR_ROLE is automatically granted to "0xProfAddr"

# ── Students ──────────────────────────────────────────────────────────────────
ds.add_student("Alice", major_id=1, year=2024, professor_id=1)

# ── Courses ───────────────────────────────────────────────────────────────────
ds.create_course("CS101", "Intro to Programming", professor_id=1)

# ── Enrollment  (semester comes first) ────────────────────────────────────────
ds.enroll("spring2025", student_id=1, course_id="CS101")
ds.update_mark("spring2025", student_id=1, course_id="CS101", mark=88)

# ── Grades & GPA  (4.0 scale) ─────────────────────────────────────────────────
gpa = ds.get_gpa(student_id=1)           # e.g. 3.3 (B+)

sem = ds.get_semester_summary(1, "spring2025")
print(sem.gpa)                           # 3.3  (4.0 scale)
print(sem.course_ids)                    # ["CS101"]

# ── Full transcript ────────────────────────────────────────────────────────────
for semester in ds.get_full_transcript(student_id=1):
    print(f"{semester.semester}: GPA={semester.gpa:.2f}/4.00")
    for e in semester.enrollments:
        print(f"  {e.course_id}: {e.mark}/100  {e.grade}  ({e.gpa_points:.1f})")

# ── RBAC ──────────────────────────────────────────────────────────────────────
ds.grant_role("REGISTRAR_ROLE", "0xStaffAddr")
print(ds.get_all_roles())
```

---

## GPA Scale

Marks are stored on-chain as integers 0–100. All GPA values in the Python
layer use the standard 4.0 scale. Conversion is done entirely client-side.

| Range | Letter | Points | Range | Letter | Points |
|-------|--------|--------|-------|--------|--------|
| 97–100 | A+ | 4.0 | 73–76 | C | 2.0 |
| 93–96 | A | 4.0 | 70–72 | C- | 1.7 |
| 90–92 | A- | 3.7 | 67–69 | D+ | 1.3 |
| 87–89 | B+ | 3.3 | 63–66 | D | 1.0 |
| 83–86 | B | 3.0 | 60–62 | D- | 0.7 |
| 80–82 | B- | 2.7 | 0–59 | F | 0.0 |
| 77–79 | C+ | 2.3 | | | |

GPA is the **unweighted average** of grade points across all graded, active
enrollments. All courses contribute equally (no credit-hour weighting).

```python
# Per-enrollment grade info
e = enrollment_record
e.mark        # 88  (stored on-chain)
e.grade       # "B+"
e.gpa_points  # 3.3

# Per-semester GPA (4.0 scale)
sem.gpa       # e.g. 3.15

# Cumulative GPA (4.0 scale)
ds.get_gpa(student_id=1)  # e.g. 3.08
```

---

## Role-Based Access Control

Three roles with strict hierarchy:

```
ADMIN_ROLE
  ├─ All system access (full CRUD on everything)
  ├─ Manage roles (grant / revoke)
  └─ Delete professors (cascade)

    REGISTRAR_ROLE
      ├─ Student, course, and enrollment CRUD
      └─ Cannot manage roles

        INSTRUCTOR_ROLE
          ├─ Update marks for own courses only
          └─ Read-only access to everything else
```

| Operation | ADMIN | REGISTRAR | INSTRUCTOR |
|-----------|:-----:|:---------:|:----------:|
| Manage roles | ✓ | ✗ | ✗ |
| Add/update/deactivate major | ✓ | ✗ | ✗ |
| Add/update professor | ✓ | ✓ | ✗ |
| Delete professor | ✓ | ✗ | ✗ |
| Student CRUD | ✓ | ✓ | ✗ |
| Course CRUD | ✓ | ✓ | ✗ |
| Enroll / unenroll | ✓ | ✓ | ✗ |
| Update mark (own course) | ✓ | ✓ | ✓ |
| Update mark (any course) | ✓ | ✓ | ✗ |
| All reads | ✓ | ✓ | ✓ |

The deployer (`superAdmin`) holds `ADMIN_ROLE` permanently and cannot
be stripped of it — even by another admin.

---

## Semester System

Semesters are free-form strings stored verbatim on-chain. Recommended format:
`"{season}{year}"` — e.g. `"spring2025"`, `"autumn2026"`.

A student can enroll in the same course in different semesters (retake).
Each `(studentId, courseId, semester)` triple is an independent record
with its own mark.

```python
# Enroll Alice in CS101 twice — different semesters
ds.enroll("spring2025", student_id=1, course_id="CS101")
ds.enroll("spring2026", student_id=1, course_id="CS101")  # retake

# Query a specific semester
ds.get_semester_enrollments(student_id=1, semester="spring2025")

# All semesters a student has appeared in
ds.get_student_semesters(student_id=1)
# ["spring2025", "autumn2025", "spring2026"]

# Full transcript (all semesters + per-semester GPA)
ds.get_full_transcript(student_id=1)
```

---

## Project Structure

```
university-web3/
├── main.py                        # Demo / entry point
├── config.json                    # Runtime config (not committed)
├── config.example.json            # Template — copy to config.json
├── requirements.txt
│
├── contracts/
│   ├── access/
│   │   └── AccessRegistry.sol     # On-chain RBAC (ADMIN/REGISTRAR/INSTRUCTOR)
│   └── core/
│       ├── Major.sol              # Major registry
│       ├── Professor.sol          # Professor registry
│       ├── Student.sol            # Student registry
│       ├── Course.sol             # Course registry
│       ├── Enrollment.sol         # Enrollment + semester + GPA (raw)
│       └── University.sol         # Entry-point facade (RBAC enforcement)
│
├── abi/                           # Compiled ABIs (generated by compile.py)
├── bin/                           # Compiled bytecode (generated by compile.py)
│
├── scripts/
│   └── compile.py                 # Compiles with optimizer via compile_standard
│
└── python/
    ├── config/
    │   └── settings.py            # Config load/save/validate (atomic writes)
    ├── blockchain/
    │   ├── provider.py            # Web3 singleton
    │   └── deployer.py            # Full deploy lifecycle + post-deploy binding
    ├── contracts/
    │   ├── registry.py            # ContractType enum + deployment order
    │   └── verifier.py            # is_deployed() check
    ├── datasource/
    │   ├── base.py                # _tx() / _call() infrastructure
    │   ├── domain_ds.py           # Major, Professor, Student, Course datasources
    │   ├── enrollment_ds.py       # Enrollment + 4.0 GPA
    │   ├── admin_ds.py            # RBAC datasource
    │   └── university_ds.py       # Public facade
    └── models/
        └── types.py               # Typed dataclasses + GPA conversion
```

---

## Configuration

`config.json` is created automatically from defaults on first run.
It is safe to delete and recreate by re-running `python main.py`
(against a fresh Anvil session).

| Key | Description |
|-----|-------------|
| `node_url` | RPC endpoint of your Ethereum node |
| `deployer_private_key` | Key used to sign all transactions |
| `deployer_address` | Derived automatically from the key |
| `contracts.*` | Contract addresses (auto-filled after deploy) |

**Custom config path:**
```bash
export UW3_CONFIG=/path/to/other-config.json
python main.py
```

---

## Deployment Details

Contracts deploy in this topological order:

```
1. AccessRegistry    (no constructor args)
2. Major             (no constructor args)
3. Professor         (no constructor args)
4. Student           (no constructor args)
5. Course            ← Professor address
6. Enrollment        ← Student + Course addresses
7. University        ← all six above
```

After University deploys, two post-deploy steps run automatically:

1. **`setUniversity(address)`** on Major, Professor, Student, Course, Enrollment —
   locks each sub-contract so only University (or deployer) can write to it.

2. **`grantRole(ADMIN_ROLE, University)`** on AccessRegistry —
   allows University to call `grantRole`/`revokeRole` internally
   (e.g. auto-granting INSTRUCTOR_ROLE when a professor is added).

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `ConnectionError: Cannot connect to ... 8545` | Anvil not running | Run `anvil` in a separate terminal |
| `FileNotFoundError: ABI not found` | Not compiled yet | Run `python scripts/compile.py` |
| `EVM error CreateContractSizeLimit` | Optimizer not applied | Use `scripts/compile.py` — it forces optimizer via `compile_standard` |
| `admin only` | Caller lacks ADMIN_ROLE | Use the deployer account (Anvil account 0) |
| `Professor: address taken` | Duplicate professor address | Each professor needs a distinct EOA |
| `Enr: not enrolled` | Unenrolling a non-active enrollment | Check semester string matches exactly |
| Duplicate outputs in compile.py | Old compile.py version | Use the latest `scripts/compile.py` |

---

## Documentation

| File | Contents |
|------|----------|
| `docs/QUICKSTART.md` | Step-by-step setup guide with troubleshooting |
| `docs/ARCHITECTURE.md` | System design, data flow diagrams, storage internals |
| `docs/CONTRACTS.md` | Every contract, function, event, and storage variable |
| `docs/DATASOURCE_API.md` | Full Python API reference with examples |
| `docs/RBAC.md` | Role system, access matrix, security guarantees |
| `docs/BUGS_FIXED.md` | All 10 bugs fixed from v1, with root cause and fix |
| `docs/CHANGELOG.md` | What changed from v1 to this version |

---

## License

 GNU GENERAL PUBLIC LICENSE V3.0
#   B l o c k _ C h a i n  
 #   B l o c k _ C h a i n  
 