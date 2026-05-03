# Role-Based Access Control

## Role Hierarchy

```
ADMIN_ROLE
  ├─ Full system access
  ├─ Manages roles (grant / revoke)
  ├─ Deletes professors (cascade)
  └─ All REGISTRAR capabilities

    REGISTRAR_ROLE
      ├─ Student CRUD
      ├─ Course CRUD (create, update, reassign, delete)
      ├─ Enrollment management (enroll, unenroll, batch enroll)
      └─ All INSTRUCTOR capabilities

        INSTRUCTOR_ROLE
          ├─ Update marks for own courses only
          └─ All read (view) operations
```

`superAdmin` (deployer) permanently holds `ADMIN_ROLE` and cannot have it
revoked — not even by another admin. This is a hard contract-level guarantee
to prevent accidental total lockout.

---

## Access Matrix

| Operation | ADMIN | REGISTRAR | INSTRUCTOR | No role |
|-----------|:-----:|:---------:|:----------:|:-------:|
| **Role management** | | | | |
| Grant any role | ✓ | ✗ | ✗ | ✗ |
| Revoke any role | ✓ | ✗ | ✗ | ✗ |
| **Majors** | | | | |
| Add major | ✓ | ✗ | ✗ | ✗ |
| Update major | ✓ | ✗ | ✗ | ✗ |
| Deactivate major | ✓ | ✗ | ✗ | ✗ |
| **Professors** | | | | |
| Add professor | ✓ | ✓ | ✗ | ✗ |
| Update professor | ✓ | ✓ | ✗ | ✗ |
| Delete professor | ✓ | ✗ | ✗ | ✗ |
| **Students** | | | | |
| Add / update / delete student | ✓ | ✓ | ✗ | ✗ |
| **Courses** | | | | |
| Create / update / delete course | ✓ | ✓ | ✗ | ✗ |
| Reassign course to professor | ✓ | ✓ | ✗ | ✗ |
| **Enrollment** | | | | |
| Enroll / unenroll student | ✓ | ✓ | ✗ | ✗ |
| Batch enroll | ✓ | ✓ | ✗ | ✗ |
| Update mark (own course) | ✓ | ✓ | ✓ | ✗ |
| Update mark (any course) | ✓ | ✓ | ✗ | ✗ |
| **All view/read operations** | ✓ | ✓ | ✓ | ✗ |

> All `get*` and `calculate*` functions are `view` — zero gas, readable by
> any address without authentication.

---

## Scenario Cookbook

### Grant registrar to a new staff member

```python
ds.grant_role("REGISTRAR_ROLE", "0xStaffAddress")

# Verify
assert ds.has_role("REGISTRAR_ROLE", "0xStaffAddress")
print(ds.get_all_roles()["REGISTRAR_ROLE"])
```

### Add a professor (auto-grants INSTRUCTOR_ROLE)

```python
# professor_address must be a unique EOA — not the deployer's address
ds.add_professor("Dr. Smith", "Computer Science", "0xSmithAddr")

# INSTRUCTOR_ROLE is automatically granted inside addProfessor
assert ds.has_role("INSTRUCTOR_ROLE", "0xSmithAddr")
```

This works because `University.addProfessor` calls:
```solidity
if (!ac.hasRole(INSTRUCTOR, addr)) ac.grantRole(INSTRUCTOR, addr);
```
And University itself holds `ADMIN_ROLE` on AccessRegistry (granted by deployer
script), so this internal `grantRole` call succeeds.

### Delete a professor (auto-revokes INSTRUCTOR_ROLE)

```python
ds.delete_professor(professor_id=1)
# INSTRUCTOR_ROLE revoked, all their courses deleted, students unenrolled
assert not ds.has_role("INSTRUCTOR_ROLE", "0xSmithAddr")
```

### Instructor grading restriction

An address holding only INSTRUCTOR_ROLE can grade courses they own:

```python
# Dr. Smith owns CS101 (professorId=1 is the course's professor)
# If Dr. Smith calls updateStudentMark for CS101 → succeeds
# If Dr. Smith calls updateStudentMark for AI301 → reverts: "not your course"
```

The contract enforces this by:
1. Checking `ac.hasRole(ADMIN, msg.sender) || ac.hasRole(REGISTRAR, msg.sender)`.
2. If neither: resolving `prof.getProfessorIdByAddress(msg.sender)` and comparing
   to `crs.getCourse(cid).professorId`.

### Revoke a role

```python
ds.revoke_role("REGISTRAR_ROLE", "0xFormerStaff")

# This reverts — superAdmin is protected:
ds.revoke_role("ADMIN_ROLE", deployer_address)
# RuntimeError: "AR: cannot revoke superAdmin"
```

### Inspect all role holders

```python
roles = ds.get_all_roles()
# {
#   "ADMIN_ROLE":      ["0xDeployer"],
#   "INSTRUCTOR_ROLE": ["0xProf1", "0xProf2", "0xProf3"],
#   "REGISTRAR_ROLE":  ["0xStaff1"],
# }
```

---

## Role Bytes (for direct contract interaction)

If calling the contracts directly (not via Python layer), role values are:

```python
from web3 import Web3
ADMIN_ROLE      = Web3.keccak(text="ADMIN_ROLE")
REGISTRAR_ROLE  = Web3.keccak(text="REGISTRAR_ROLE")
INSTRUCTOR_ROLE = Web3.keccak(text="INSTRUCTOR_ROLE")
```

**Do not** compute these as `"ADMIN_ROLE".encode().ljust(32)` or any other
byte-padding — that produces a completely different value than Solidity's
`keccak256("ADMIN_ROLE")`.

---

## Security Model

**1. Sub-contract isolation.**
All sub-contracts enforce `onlyAuth`:
```solidity
require(msg.sender == university || msg.sender == deployer, "unauthorized");
```
After `setUniversity()` is called, writes from any other address revert.
University.sol is the only path to mutate state — its RBAC cannot be bypassed.

**2. One-time binding.**
`setUniversity(address)` can only be called once per sub-contract (deployer only).
After binding, the University address is permanently fixed.

**3. University holds ADMIN_ROLE — but callers still need roles.**
University is granted `ADMIN_ROLE` on AccessRegistry so it can call
`grantRole`/`revokeRole` internally. This does NOT mean any caller can
manage roles — University's own `onlyAdmin` modifier still gates the external
entry points. The ADMIN_ROLE grant only allows the contract-to-contract call
to succeed when a correctly-authenticated external call triggers it.

**4. Role enumeration is compact.**
`_members[]` uses swap-and-pop, so the array stays compact. No unbounded
loops on grant/revoke. O(N) iteration for `getRoleMembers` where N is current
holder count, not historical grant count.

**5. superAdmin lockout protection.**
```solidity
require(
    !(role == ADMIN_ROLE && account == superAdmin),
    "AR: cannot revoke superAdmin"
);
```
Even if an attacker gains ADMIN_ROLE, they cannot remove the deployer's
access. The deployer always retains recovery capability.
