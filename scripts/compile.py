#!/usr/bin/env python3
"""
scripts/compile.py
──────────────────
Compiles all Solidity contracts using solc Standard JSON input.

WHY compile_standard INSTEAD OF compile_files:
  compile_files() accepts optimize= and optimize_runs= keyword arguments,
  but on several py-solc-x versions (especially on Windows) these flags are
  silently ignored — the optimizer is never applied and University.sol comes
  out at ~34 KB, far above the 24,576-byte EVM limit.

  compile_standard() takes a raw Standard JSON input dict that is passed
  directly to the solc binary. Optimizer settings here are ALWAYS honoured
  because they go straight into the --standard-json argument. This is the
  only reliable cross-platform approach.

USAGE:
    python scripts/compile.py

REQUIREMENTS:
    pip install py-solc-x
    python -c "from solcx import install_solc; install_solc('0.8.20')"
"""
import json
import sys
from pathlib import Path

try:
    from solcx import compile_standard, install_solc, get_installed_solc_versions
except ImportError:
    print("ERROR: py-solc-x is not installed.")
    print("       Run:  pip install py-solc-x")
    sys.exit(1)

ROOT         = Path(__file__).resolve().parent.parent
SOLC_VERSION = "0.8.20"
SIZE_LIMIT   = 24_576     # EIP-170 hard limit in bytes

# (path relative to ROOT,  contract name to extract from compiler output)
CONTRACTS = [
    ("contracts/access/AccessRegistry.sol", "AccessRegistry"),
    ("contracts/core/Major.sol",            "Major"),
    ("contracts/core/Professor.sol",        "Professor"),
    ("contracts/core/Student.sol",          "Student"),
    ("contracts/core/Course.sol",           "Course"),
    ("contracts/core/Enrollment.sol",       "Enrollment"),
    ("contracts/core/University.sol",       "University"),
]


# ─── Helpers ─────────────────────────────────────────────────────────────────

def ensure_solc() -> None:
    installed = [str(v) for v in get_installed_solc_versions()]
    if SOLC_VERSION not in installed:
        print(f"Installing solc {SOLC_VERSION} (one-time download, ~30 MB)…")
        install_solc(SOLC_VERSION)
        print(f"solc {SOLC_VERSION} ready.\n")


def load_sources() -> dict:
    """Read every contract file into the Standard JSON `sources` dict."""
    sources = {}
    for rel, _ in CONTRACTS:
        path = ROOT / rel
        if not path.exists():
            print(f"ERROR: source file missing: {path}")
            sys.exit(1)
        # Use forward slashes — solc requires them even on Windows
        sources[rel.replace("\\", "/")] = {"content": path.read_text(encoding="utf-8")}
    return sources


def standard_json_input(sources: dict) -> dict:
    """
    Build the full Standard JSON input object.

    optimizer.runs = 200:
      Optimises for repeated runtime calls (the typical deployment scenario).
      Higher values (e.g. 10000) reduce runtime gas further but increase
      bytecode size. 200 is the conventional safe default.
    """
    return {
        "language": "Solidity",
        "sources": sources,
        "settings": {
            "optimizer": {
                "enabled": True,
                "runs": 200
            },
            "outputSelection": {
                "*": {
                    "*": ["abi", "evm.bytecode.object"]
                }
            }
        }
    }


def extract_artifacts(result: dict, wanted: set[str]) -> dict[str, tuple[list, str]]:
    """
    Extract (abi, bin_hex) for each wanted contract.

    When University.sol imports the other contracts, solc returns those
    contracts a second time under the University.sol source key. We prefer
    the entry from each contract's OWN canonical file to avoid duplicates.
    """
    extracted: dict[str, tuple[list, str]] = {}
    for src_key, contracts in result.get("contracts", {}).items():
        for name, data in contracts.items():
            if name not in wanted:
                continue
            abi     = data.get("abi", [])
            bin_hex = data.get("evm", {}).get("bytecode", {}).get("object", "")
            is_own  = src_key.endswith(f"{name}.sol")
            if name not in extracted or is_own:
                extracted[name] = (abi, bin_hex)
    return extracted


# ─── Main ────────────────────────────────────────────────────────────────────

def compile_all() -> None:
    abi_dir = ROOT / "abi"
    bin_dir = ROOT / "bin"
    abi_dir.mkdir(exist_ok=True)
    bin_dir.mkdir(exist_ok=True)

    sources   = load_sources()
    std_input = standard_json_input(sources)

    print(f"Compiling {len(CONTRACTS)} contracts")
    print(f"  solc {SOLC_VERSION}  ·  optimizer ON  ·  200 runs\n")

    result = compile_standard(
        std_input,
        solc_version=SOLC_VERSION,
        allow_paths=[str(ROOT)],
    )

    # ── Surface warnings / errors ─────────────────────────────────────────────
    errors = result.get("errors", [])
    for e in errors:
        label = "ERROR" if e.get("severity") == "error" else "WARN "
        # formattedMessage includes file + line context
        msg = e.get("formattedMessage") or e.get("message") or str(e)
        print(f"  [{label}] {msg[:200]}")

    if any(e.get("severity") == "error" for e in errors):
        print("\nCompilation failed — fix errors above and retry.")
        sys.exit(1)

    # ── Extract and write artifacts ───────────────────────────────────────────
    wanted    = {name for _, name in CONTRACTS}
    extracted = extract_artifacts(result, wanted)

    if not extracted:
        print("ERROR: compiler produced no output. Check your contract sources.")
        sys.exit(1)

    oversized = []
    written   = 0

    for name in sorted(extracted):
        abi, bin_hex = extracted[name]
        size         = len(bin_hex) // 2   # hex chars → bytes

        (abi_dir / f"{name}.abi").write_text(json.dumps(abi, indent=2), encoding="utf-8")
        (bin_dir / f"{name}.bin").write_text(bin_hex, encoding="utf-8")

        # Size bar (20 chars = 100%)
        pct  = size / SIZE_LIMIT * 100
        fill = min(int(pct / 5), 20)
        bar  = "█" * fill + "░" * (20 - fill)
        flag = "  ← ⚠ OVER LIMIT" if size > SIZE_LIMIT else ""

        print(f"  {name:<18}  {size:>6,} B  [{bar}]  {pct:5.1f}%{flag}")
        written += 1
        if size > SIZE_LIMIT:
            oversized.append((name, size))

    print(f"\n  {written}/{len(CONTRACTS)} contracts written → abi/  bin/")

    if oversized:
        print("\n⛔  The following contracts exceed the 24,576-byte EVM limit:")
        for name, size in oversized:
            print(f"     {name}: {size:,} B  (+{size - SIZE_LIMIT:,} over limit)")
        print("\n  Causes and fixes:")
        print("  • Optimizer not applied → use this script (compile_standard guarantees it).")
        print("  • Contract too large after optimization → split into two façade contracts.")
        print("  • Remove unused imports or inline helper functions.")
        sys.exit(1)

    print(f"\n  ✓ All contracts within the {SIZE_LIMIT:,}-byte EVM limit.")


if __name__ == "__main__":
    ensure_solc()
    compile_all()
