"""
python/blockchain/deployer.py
─────────────────────────────
Full deployment lifecycle:

  1. Deploy contracts in topological order (DEPLOYMENT_ORDER).
  2. Skip any contract whose saved address already has live bytecode.
  3. After University is deployed, call setUniversity() on each sub-contract
     (NEEDS_BINDING) so they lock writes to University-only.
  4. Grant ADMIN_ROLE to the University contract on AccessRegistry so
     University can internally call grantRole/revokeRole (e.g. auto-granting
     INSTRUCTOR_ROLE on addProfessor, or revoking it on deleteProfessor).
  5. Track nonces locally to avoid nonce collisions on rapid sequential txs.
  6. Persist every deployed address atomically via settings.set_contract_address().

WHY NONCE TRACKING:
  web3.py fetches the current nonce with eth_getTransactionCount before each
  transaction. On a local Anvil node, consecutive transactions are submitted
  so quickly that the second eth_getTransactionCount call may return the same
  nonce as the first (the first tx hasn't been mined yet). This causes
  "replacement transaction underpriced" errors. We increment a local counter
  instead, fetching from the node only once at the start of the deploy run.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from web3 import Web3
from web3.contract import Contract

from python.blockchain import provider
from python.config import settings
from python.contracts.registry import ContractType, DEPLOYMENT_ORDER, NEEDS_BINDING
from python.contracts.verifier import is_deployed

_ROOT    = Path(__file__).resolve().parent.parent.parent
_ABI_DIR = _ROOT / "abi"
_BIN_DIR = _ROOT / "bin"

ZERO_ADDR = "0x" + "0" * 40


# ─── Artifact loading ─────────────────────────────────────────────────────────

def _load(ct: ContractType) -> tuple[list, str]:
    """Load ABI and bytecode for a ContractType from the abi/ bin/ directories."""
    abi_path = _ABI_DIR / ct.abi_filename
    bin_path = _BIN_DIR / ct.bin_filename
    if not abi_path.exists():
        raise FileNotFoundError(
            f"ABI not found: {abi_path}\n"
            "Run:  python scripts/compile.py"
        )
    if not bin_path.exists():
        raise FileNotFoundError(
            f"Bytecode not found: {bin_path}\n"
            "Run:  python scripts/compile.py"
        )
    with open(abi_path, encoding="utf-8") as f:
        abi = json.load(f)
    with open(bin_path, encoding="utf-8") as f:
        bytecode = f.read().strip()
    return abi, bytecode


# ─── Single contract deploy ───────────────────────────────────────────────────

def deploy_one(ct: ContractType, constructor_args: tuple = (), nonce: int | None = None) -> Contract:
    """
    Deploy a single contract, save its address to config, return a Contract instance.

    If `nonce` is provided it is used directly (local tracking).
    If None, fetches the current nonce from the node.
    """
    w3       = provider.get()
    cfg      = settings.load()
    deployer = cfg["deployer_address"]
    pk       = cfg["deployer_private_key"]

    if not deployer:
        raise RuntimeError(
            "deployer_address is empty in config.json.\n"
            "Set deployer_private_key and the address will be derived automatically."
        )

    abi, bytecode = _load(ct)
    factory       = w3.eth.contract(abi=abi, bytecode=bytecode)

    if nonce is None:
        nonce = w3.eth.get_transaction_count(deployer)

    tx = factory.constructor(*constructor_args).build_transaction({
        "from":  deployer,
        "nonce": nonce,
    })
    signed  = w3.eth.account.sign_transaction(tx, pk)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    if receipt["status"] != 1:
        raise RuntimeError(f"Deploy of {ct.value} failed — tx: {tx_hash.hex()}")

    address = receipt.contractAddress
    print(f"  ✓ {ct.value:<18} deployed at {address}")
    settings.set_contract_address(ct.value, address)  # atomic write, fresh read

    return w3.eth.contract(address=address, abi=abi)


# ─── Constructor args per contract ───────────────────────────────────────────

def _constructor_args(ct: ContractType, deployed: dict[ContractType, str]) -> tuple:
    """Return the constructor arguments for a contract given already-deployed addresses."""
    if ct == ContractType.COURSE:
        return (deployed[ContractType.PROFESSOR],)

    if ct == ContractType.ENROLLMENT:
        return (
            deployed[ContractType.STUDENT],
            deployed[ContractType.COURSE],
        )

    if ct == ContractType.UNIVERSITY:
        return (
            deployed[ContractType.ACCESS_REGISTRY],
            deployed[ContractType.MAJOR],
            deployed[ContractType.STUDENT],
            deployed[ContractType.PROFESSOR],
            deployed[ContractType.COURSE],
            deployed[ContractType.ENROLLMENT],
        )

    return ()   # AccessRegistry, Major, Professor, Student have no constructor args


# ─── Full stack deploy ────────────────────────────────────────────────────────

def deploy_all() -> dict[ContractType, str]:
    """
    Deploy all contracts that are missing or have no live bytecode.
    Returns ContractType → deployed address for every contract.
    """
    w3       = provider.get()
    cfg      = settings.load()
    deployer = cfg["deployer_address"]

    nonce    = w3.eth.get_transaction_count(deployer)
    deployed: dict[ContractType, str] = {}

    print("\nDeployment")
    print("─" * 50)

    for ct in DEPLOYMENT_ORDER:
        existing = cfg["contracts"].get(ct.value, "")
        if existing and is_deployed(existing):
            print(f"  ↩ {ct.value:<18} already at {existing}")
            deployed[ct] = existing
            continue

        print(f"  → Deploying {ct.value}…")
        args     = _constructor_args(ct, deployed)
        contract = deploy_one(ct, args, nonce)
        deployed[ct] = contract.address
        nonce += 1
        cfg = settings.load()   # refresh after each write

    # Bind sub-contracts + grant University ADMIN_ROLE
    _post_deploy(deployed, nonce)

    return deployed


def _post_deploy(deployed: dict[ContractType, str], start_nonce: int) -> None:
    """
    Two-step post-deployment setup:

    Step 1 — setUniversity(address) on each sub-contract.
      Locks sub-contracts so only University (or deployer) can write to them.
      Without this, anyone who knows the sub-contract address can bypass
      University.sol's role checks entirely.

    Step 2 — grant ADMIN_ROLE to University on AccessRegistry.
      University.addProfessor calls accessRegistry.grantRole(INSTRUCTOR_ROLE, addr).
      University.deleteProfessor calls accessRegistry.revokeRole(INSTRUCTOR_ROLE, addr).
      Both require msg.sender to hold ADMIN_ROLE on AccessRegistry.
      msg.sender in those calls is the University contract address, which is
      NOT the deployer — so we grant it here explicitly.

      SECURITY NOTE: University's own onlyAdmin / onlyReg modifiers still
      control who can call these functions from outside. Granting ADMIN_ROLE
      to University does NOT mean any random caller can manage roles — it only
      allows University's internal logic to call AccessRegistry's grantRole/
      revokeRole on behalf of an already-authenticated transaction.
    """
    w3       = provider.get()
    cfg      = settings.load()
    deployer = cfg["deployer_address"]
    pk       = cfg["deployer_private_key"]
    uni_addr = deployed.get(ContractType.UNIVERSITY, "")

    if not uni_addr:
        raise RuntimeError("University not in deployed map — cannot run post-deploy setup.")

    nonce = start_nonce

    print("\nPost-deploy binding")
    print("─" * 50)

    # ── Step 1: setUniversity ──────────────────────────────────────────────────
    for ct in NEEDS_BINDING:
        sub_addr = deployed.get(ct, "")
        if not sub_addr:
            continue

        abi, _ = _load(ct)
        sub    = w3.eth.contract(address=sub_addr, abi=abi)

        # Check current binding
        try:
            current = sub.functions.university().call()
            if current.lower() == uni_addr.lower():
                print(f"  ↩ {ct.value:<18} already bound to University")
                continue
            # Non-zero and not University → already bound to something else
            if current.lower() != ZERO_ADDR.lower():
                print(f"  ⚠ {ct.value:<18} bound to unexpected address {current} — skipping")
                continue
        except Exception:
            pass  # function may not exist on old ABI — attempt bind anyway

        tx = sub.functions.setUniversity(uni_addr).build_transaction({
            "from":  deployer,
            "nonce": nonce,
        })
        signed  = w3.eth.account.sign_transaction(tx, pk)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        if receipt["status"] != 1:
            raise RuntimeError(f"setUniversity failed for {ct.value}")
        print(f"  ✓ {ct.value:<18} setUniversity({uni_addr[:12]}…)")
        nonce += 1

    # ── Step 2: grant ADMIN_ROLE to University on AccessRegistry ──────────────
    ADMIN_ROLE = Web3.keccak(text="ADMIN_ROLE")
    access_addr = deployed.get(ContractType.ACCESS_REGISTRY, "")

    if not access_addr:
        print("  ⚠ AccessRegistry address missing — cannot grant ADMIN_ROLE to University")
        return

    access_abi, _ = _load(ContractType.ACCESS_REGISTRY)
    access         = w3.eth.contract(address=access_addr, abi=access_abi)

    if access.functions.hasRole(ADMIN_ROLE, uni_addr).call():
        print(f"  ↩ University          already has ADMIN_ROLE on AccessRegistry")
        return

    tx = access.functions.grantRole(ADMIN_ROLE, uni_addr).build_transaction({
        "from":  deployer,
        "nonce": nonce,
    })
    signed  = w3.eth.account.sign_transaction(tx, pk)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    if receipt["status"] != 1:
        raise RuntimeError("grantRole(ADMIN_ROLE, University) failed")
    print(f"  ✓ AccessRegistry      granted ADMIN_ROLE → University")


# ─── Public entry point ───────────────────────────────────────────────────────

def get_or_deploy(ct: ContractType) -> Contract:
    """
    Return a live Contract instance for `ct`.
    If any contract in the stack is missing or has no live bytecode, deploys
    the entire stack (deploy_all handles idempotency).
    """
    cfg     = settings.load()
    address = cfg["contracts"].get(ct.value, "")

    if address and is_deployed(address):
        abi, _ = _load(ct)
        return provider.get().eth.contract(address=address, abi=abi)

    deploy_all()

    # Re-read after deploy
    cfg     = settings.load()
    address = cfg["contracts"].get(ct.value, "")
    if not address:
        raise RuntimeError(f"{ct.value} address still missing after deploy_all()")

    abi, _ = _load(ct)
    return provider.get().eth.contract(address=address, abi=abi)
