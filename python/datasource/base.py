"""
python/datasource/base.py
─────────────────────────
BaseDataSource — shared infrastructure for all domain datasources.

All concrete datasources (MajorDS, ProfessorDS, …) inherit this.
They call self._tx() for writes and self._call() for reads.
Neither method should ever be called directly by application code.

_tx(fn, wait=True):
  Submits a transaction using the deployer key from config.
  If wait=True (default), blocks until mined and raises RuntimeError
  if the transaction was reverted (status == 0). Returns TxReceipt.
  If wait=False, returns the hex tx hash immediately without blocking.

_call(fn):
  Calls a view/pure function. Never consumes gas. Returns the raw result
  (tuple, int, str, list, etc.) as returned by web3.py. Callers are
  responsible for wrapping in the appropriate dataclass.

ERROR MESSAGES:
  Solidity revert reasons are surfaced in the RuntimeError message.
  Example: RuntimeError("Transaction reverted: execution reverted: admin only")
"""
from __future__ import annotations

from typing import Any

from web3.contract import Contract
from web3.types import TxReceipt

from python.blockchain import provider
from python.config import settings


class BaseDataSource:
    def __init__(self, contract: Contract) -> None:
        self._contract = contract
        self._w3       = provider.get()

    # ─── Transaction (write) ─────────────────────────────────────────────────

    def _tx(
        self,
        fn,
        *,
        wait: bool = True,
        gas: int | None = None,
        gas_price: int | None = None,
        use_admin: bool = False,
    ) -> TxReceipt | str:
        """
        Execute a contract write function.

        Args:
            fn:        Bound function call, e.g. contract.functions.addStudent(...)
            wait:      Block until mined (default True). Raises on revert.
            gas:       Override gas limit (optional; normally estimated by node).
            gas_price: Override gas price (optional).
            use_admin: Currently a no-op (single-key setup); hook for future
                       multi-account support.

        Returns:
            TxReceipt dict if wait=True, else hex tx hash string.
        """
        cfg   = settings.load()
        params: dict[str, Any] = {"from": cfg["deployer_address"]}
        if gas:       params["gas"]      = gas
        if gas_price: params["gasPrice"] = gas_price

        try:
            tx_hash = fn.transact(params)
        except Exception as exc:
            raise RuntimeError(f"Transaction submission failed: {exc}") from exc

        if not wait:
            return tx_hash.hex()

        receipt: TxReceipt = self._w3.eth.wait_for_transaction_receipt(tx_hash)
        if receipt["status"] == 0:
            raise RuntimeError(
                f"Transaction reverted.\n"
                f"  Hash: {tx_hash.hex()}\n"
                f"  Check revert reason with: cast run {tx_hash.hex()}"
            )
        return receipt

    # ─── Call (read-only) ─────────────────────────────────────────────────────

    def _call(self, fn) -> Any:
        """
        Execute a read-only contract call (view/pure). Zero gas cost.
        Wraps exceptions with context for easier debugging.
        """
        try:
            return fn.call()
        except Exception as exc:
            raise RuntimeError(f"Contract call failed: {exc}") from exc
