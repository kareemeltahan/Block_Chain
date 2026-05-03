"""
python/blockchain/provider.py
─────────────────────────────
Web3 connection singleton.

WHY A SINGLETON:
  Creating a Web3 instance is cheap, but every call to Web3(HTTPProvider(...))
  opens a new connection pool. A singleton reuses the pool and avoids the
  overhead of repeated TCP handshakes against Anvil.

LAZY INITIALISATION:
  The connection is NOT created at import time. It is created on the first
  call to get(). This means importing this module in tests or scripts that
  don't actually need a live chain does not immediately fail.

DEPLOYER ADDRESS DERIVATION:
  If config.json has a deployer_private_key but no deployer_address, the
  address is derived from the key on first connect and written back to disk.
  This means you never need to manually paste your address — only the key.
"""
from __future__ import annotations

from web3 import Web3

from python.config import settings

_w3: Web3 | None = None


def get() -> Web3:
    """Return the live Web3 instance, creating it on first call."""
    global _w3
    if _w3 is not None:
        return _w3

    cfg = settings.load()
    _w3 = Web3(Web3.HTTPProvider(cfg["node_url"]))

    # Derive deployer_address from private key if not already set
    if cfg.get("deployer_private_key") and not cfg.get("deployer_address"):
        addr = _w3.eth.account.from_key(cfg["deployer_private_key"]).address
        cfg["deployer_address"] = addr
        settings.save(cfg)

    if not _w3.is_connected():
        raise ConnectionError(
            f"\n\nCannot connect to Ethereum node at: {cfg['node_url']}\n"
            "Ensure Anvil is running:  anvil\n"
            "Or update node_url in config.json to point at your node."
        )

    return _w3


def reset() -> None:
    """Force reconnection on next get(). Useful in tests between runs."""
    global _w3
    _w3 = None
