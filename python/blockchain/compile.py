#!/usr/bin/env python3
"""
scripts/compile.py
──────────────────
Compiles all Solidity contracts using solc Standard JSON input.
This is the only reliable way to guarantee optimizer settings are applied
across all py-solc-x versions and operating systems.

Usage:
    python scripts/compile.py

Requirements:
    pip install py-solc-x
    python -c "from solcx import install_solc; install_solc('0.8.20')"
"""
import json
import sys
from pathlib import Path

try:
    from solcx import compile_standard, install_solc, get_installed_solc_versions
except ImportError:
    print("ERROR: py-solc-x not installed. Run:  pip install py-solc-x")
    sys.exit(1)

ROOT         = Path(__file__).resolve().parent.parent
CONTRACTS    = ROOT / "contracts"
ABI_DIR      = ROOT / "abi"
BIN_DIR      = ROOT / "bin"
SOLC_VERSION = "0.8.20"
SIZE_LIMIT   = 24_576   # EIP-170: 24 KB hard EVM limit

# (relative path from ROOT, contract name to extract)
CONTRACT_MANIFEST = [
    ("contracts/access/AccessRegistry.sol", "AccessRegistry"),
    ("contracts/core/Major.sol",            "Major"),
    ("contracts/core/Professor.sol",        "Professor"),
    ("contracts/core/Student.sol",          "Student"),
    ("contracts/core/Course.sol",           "Course"),
    ("contracts/core/Enrollment.sol",       "Enrollment"),
    ("contracts/core/University.sol",       "University"),
]


def ensure_solc():
    installed = [str(v) for v in get_installed_solc_versions()]
    if SOLC_VERSION not in installed:
        print(f"  Installing solc {SOLC_VERSION} (one-time)...")
        install_solc(SOLC_VERSION)


def compile_all():
    ABI_DIR.mkdir(exist_ok=True)
    BIN_DIR.mkdir(exist_ok=True)

    # ── Read source files ─────────────────────────────────────────────────────
    sources = {}
    for rel, _ in CONTRACT_MANIFEST:
        path = ROOT / rel
        if not path.exists():
            print(f"ERROR: not found: {path}")
            sys.exit(1)
        sources[rel.replace("\\", "/")] = {"content": path.read_text(encoding="utf-8")}

    # ── Standard JSON input with optimizer ────────────────────────────────────
    std_input = {
        "language": "Solidity",
        "sources": sources,
        "settings": {
            "optimizer": {
                "enabled": True,
                "runs": 200          # optimise for repeated calls (runtime gas)
            },
            "outputSelection": {
                "*": {"*": ["abi", "evm.bytecode.object"]}
            }
        }
    }

    print(f"Compiling {len(CONTRACT_MANIFEST)} contracts")
    print(f"  solc {SOLC_VERSION}  |  optimizer ON  |  200 runs\n")

    result = compile_standard(
        std_input,
        solc_version=SOLC_VERSION,
        allow_paths=[str(ROOT)],
    )

    # ── Surface errors / warnings ─────────────────────────────────────────────
    for e in result.get("errors", []):
        prefix = "ERROR" if e.get("severity") == "error" else "WARN "
        print(f"  {prefix}  {e.get('formattedMessage', e)[:140]}")
    if any(e.get("severity") == "error" for e in result.get("errors", [])):
        sys.exit(1)

    # ── Extract wanted contracts (prefer entry from own source file) ──────────
    wanted    = {name for _, name in CONTRACT_MANIFEST}
    extracted = {}
    for src_key, contracts in result.get("contracts", {}).items():
        for name, data in contracts.items():
            if name not in wanted:
                continue
            abi     = data.get("abi", [])
            bin_hex = data.get("evm", {}).get("bytecode", {}).get("object", "")
            # Prefer the entry whose source file is the contract's own file
            if name not in extracted or src_key.endswith(f"{name}.sol"):
                extracted[name] = (abi, bin_hex)

    if not extracted:
        print("ERROR: compiler returned no matching contracts.")
        sys.exit(1)

    # ── Write artifacts and report sizes ─────────────────────────────────────
    oversized = []
    for name in sorted(extracted):
        abi, bin_hex = extracted[name]
        size = len(bin_hex) // 2

        (ABI_DIR / f"{name}.abi").write_text(json.dumps(abi, indent=2), encoding="utf-8")
        (BIN_DIR / f"{name}.bin").write_text(bin_hex, encoding="utf-8")

        pct  = size / SIZE_LIMIT * 100
        fill = int(pct / 5)
        bar  = "█" * fill + "░" * (20 - fill)
        flag = "  ⚠ OVER LIMIT" if size > SIZE_LIMIT else ""
        print(f"  {name:<18} {size:>6,} B  [{bar}] {pct:5.1f}%{flag}")

        if size > SIZE_LIMIT:
            oversized.append((name, size))

    print(f"\n  {len(extracted)}/{len(CONTRACT_MANIFEST)} contracts written → abi/  bin/")

    if oversized:
        print("\n⛔  Over-limit contracts (EIP-170 max = 24,576 bytes):")
        for name, size in oversized:
            print(f"     {name}: {size:,} B  (+{size - SIZE_LIMIT:,} over)")
        sys.exit(1)
    else:
        print(f"\n✓  All contracts within {SIZE_LIMIT:,}-byte limit.")


if __name__ == "__main__":
    ensure_solc()
    compile_all()
