# Quick Start

From zero to a running system in under 10 minutes.

---

## Prerequisites

| Tool | Min version | How to install |
|------|-------------|----------------|
| Python | 3.11+ | [python.org](https://python.org) |
| Foundry (Anvil) | latest | See below |
| py-solc-x | 2.0+ | `pip install py-solc-x` |
| web3.py | 6.15+ | installed via requirements.txt |

### Install Foundry

**macOS / Linux / WSL:**
```bash
curl -L https://foundry.paradigm.xyz | bash
foundryup
```

**Windows native:** Use Git Bash, WSL, or Windows Terminal with WSL.
`anvil` requires a POSIX-compatible shell.

---

## Step 1 — Clone and install

```bash
git clone <repo-url> university-web3
cd university-web3
pip install -r requirements.txt
```

---

## Step 2 — Start a local chain

Open a **separate terminal** and run:

```bash
anvil
```

Anvil prints 10 pre-funded accounts with private keys. **Leave this terminal open.**
It runs a local EVM node at `http://127.0.0.1:8545`.

Example output:
```
Available Accounts
==================
(0) 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266  (10000 ETH)
(1) 0x70997970C51812dc3A010C7d01b50e0d17dc79C8  (10000 ETH)
...

Private Keys
==================
(0) 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
(1) 0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d
...
```

---

## Step 3 — Configure

```bash
cp config.example.json config.json
```

The example config already contains Anvil's well-known account 0 private key.
If you're using the default Anvil setup, **no changes needed**.

```json
{
    "node_url": "http://127.0.0.1:8545",
    "deployer_private_key": "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80",
    "deployer_address": "",
    "contracts": { ... all empty ... }
}
```

`deployer_address` and all contract addresses are **automatically derived and filled**
on first run. You never need to paste them manually.

> ⚠️ **Security:** Never put real private keys in config.json.
> Anvil's keys are public test keys that control nothing of value.

---

## Step 4 — Compile contracts

```bash
python scripts/compile.py
```

This uses solc's Standard JSON interface (not `compile_files`) to guarantee
the optimizer is applied on all platforms including Windows.
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

  7/7 contracts written → abi/  bin/

  ✓ All contracts within 24,576-byte EVM limit.
```

University at ~58% of the limit gives headroom for future features.

---

## Step 5 — Run the demo

```bash
python main.py
```

**First run** deploys all 7 contracts in order, binds sub-contracts, grants roles,
then runs through 14 demo sections covering every feature.

**Subsequent runs** skip deployment entirely (addresses are live in config.json)
and run straight to the demo.

---

## Step 6 — Use the API in your own code

```python
from python.datasource.university_ds import UniversityDataSource

ds = UniversityDataSource()

# Majors
ds.add_major("CS", "Computer Science", "Algorithms and software")
cs = ds.get_major_by_code("CS")

# Professors  ← must use a unique address, not the deployer's
ds.add_professor("Dr. Smith", "Computer Science", "0xUniqueProfAddr")

# Students
ds.add_student("Alice", major_id=1, year=2024, professor_id=1)

# Courses
ds.create_course("CS101", "Intro to Programming", professor_id=1)

# Enrollment — semester first, then student, then course
ds.enroll("spring2025", student_id=1, course_id="CS101")
ds.update_mark("spring2025", student_id=1, course_id="CS101", mark=88)

# Transcript
for sem in ds.get_full_transcript(student_id=1):
    print(sem.semester, sem.gpa, sem.course_ids)
```

---

## Configuration reference

| Key | Description | Default |
|-----|-------------|---------|
| `node_url` | RPC URL of your Ethereum node | `http://127.0.0.1:8545` |
| `deployer_private_key` | Key used to sign all transactions | Anvil account 0 key |
| `deployer_address` | Derived automatically from the key | (auto-filled) |
| `contracts.*` | Deployed contract addresses | (auto-filled on first run) |

**Custom config path:**
```bash
export UW3_CONFIG=/path/to/custom-config.json
python main.py
```

---

## Resetting to a clean state

```bash
# 1. Restart Anvil (clears all chain state)
# 2. Wipe contract addresses from config:
python -c "
import json
cfg = json.load(open('config.json'))
for k in cfg['contracts']:
    cfg['contracts'][k] = ''
json.dump(cfg, open('config.json','w'), indent=4)
print('Config reset.')
"
# 3. Re-run
python main.py
```

---

## Common errors and fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `ConnectionError: Cannot connect to ... 8545` | Anvil not running | Run `anvil` in another terminal |
| `FileNotFoundError: ABI not found` | Contracts not compiled | Run `python scripts/compile.py` first |
| `EVM error CreateContractSizeLimit` | Bytecode > 24 KB (optimizer not applied) | Use `python scripts/compile.py` — it forces optimizer via `compile_standard` |
| `admin only` revert | Caller doesn't have ADMIN_ROLE | Use the deployer account (account 0 from Anvil) |
| `Professor: address taken` | Two professors given same address | Each professor needs a distinct EOA |
| `deployer_address is empty` | Private key set but address not derived yet | Restart — provider.py derives it on connect |
