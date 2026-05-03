"""
python/datasource/admin_ds.py
──────────────────────────────
RBAC operations. Role bytes32 values are computed via Web3.keccak(text=name)
which matches exactly what Solidity's keccak256("ROLE_NAME") produces.

DO NOT hardcode role hashes as hex strings — keccak256 of the UTF-8 bytes of
a string is NOT the same as the UTF-8 bytes padded to 32 bytes.
"""
from __future__ import annotations

from web3 import Web3
from web3.contract import Contract

from python.datasource.base import BaseDataSource

KNOWN_ROLES = {"ADMIN_ROLE", "REGISTRAR_ROLE", "INSTRUCTOR_ROLE"}


def role_bytes(name: str) -> bytes:
    """
    Compute keccak256 of a role name string.
    Matches Solidity: bytes32 public constant X = keccak256("X");
    """
    if name not in KNOWN_ROLES:
        raise ValueError(f"Unknown role '{name}'. Valid roles: {sorted(KNOWN_ROLES)}")
    return Web3.keccak(text=name)


class AdminDataSource(BaseDataSource):
    def __init__(self, contract: Contract) -> None:
        super().__init__(contract)

    def grant_role(self, role_name: str, address: str) -> dict:
        """
        Grant a role to an address. Requires caller to hold ADMIN_ROLE.
        role_name: 'ADMIN_ROLE' | 'REGISTRAR_ROLE' | 'INSTRUCTOR_ROLE'
        """
        return self._tx(
            self._contract.functions.grantRole(role_bytes(role_name), address),
            use_admin=True,
        )

    def revoke_role(self, role_name: str, address: str) -> dict:
        """
        Revoke a role from an address.
        Cannot revoke ADMIN_ROLE from the superAdmin (deployer) — contract enforced.
        """
        return self._tx(
            self._contract.functions.revokeRole(role_bytes(role_name), address),
            use_admin=True,
        )

    def has_role(self, role_name: str, address: str) -> bool:
        return self._call(
            self._contract.functions.hasRole(role_bytes(role_name), address)
        )

    def get_role_members(self, role_name: str) -> list[str]:
        return self._call(
            self._contract.functions.getRoleMembers(role_bytes(role_name))
        )

    def get_all_roles(self) -> dict[str, list[str]]:
        """Returns a dict mapping each role name to its current member addresses."""
        return {name: self.get_role_members(name) for name in sorted(KNOWN_ROLES)}
