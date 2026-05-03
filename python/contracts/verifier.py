"""python/contracts/verifier.py — checks if bytecode exists at an address."""
from __future__ import annotations

from python.blockchain import provider


def is_deployed(address: str) -> bool:
    """
    Return True if a contract exists at `address`.

    eth_getCode returns "0x" for EOAs and non-existent addresses.
    A deployed contract returns at least "0x60" (the typical PUSH1 opcode
    that starts most contracts). We check len > 2 to exclude the bare "0x".
    """
    if not address:
        return False
    try:
        code = provider.get().eth.get_code(address)
        return len(code) > 2
    except Exception:
        return False
