"""datasource/major_ds.py"""
from __future__ import annotations

from web3.contract import Contract

from python.datasource.base import BaseDataSource
from python.models.types import MajorInfo


class MajorDataSource(BaseDataSource):
    def __init__(self, contract: Contract):
        super().__init__(contract)

    # ─── Write ───────────────────────────────────────────────────────────────

    def add_major(self, code: str, name: str, description: str = "") -> dict:
        if not code or not name:
            raise ValueError("code and name are required")
        receipt = self._tx(
            self._contract.functions.addMajor(code.upper(), name, description)
        )
        return receipt

    def update_major(self, major_id: int, name: str = "", description: str = "") -> dict:
        if major_id <= 0:
            raise ValueError("major_id must be positive")
        return self._tx(self._contract.functions.updateMajor(major_id, name, description))

    def deactivate_major(self, major_id: int) -> dict:
        if major_id <= 0:
            raise ValueError("major_id must be positive")
        return self._tx(self._contract.functions.deactivateMajor(major_id))

    # ─── Read ────────────────────────────────────────────────────────────────

    def get_major(self, major_id: int) -> MajorInfo:
        raw = self._call(self._contract.functions.getMajor(major_id))
        return MajorInfo.from_tuple(raw)

    def get_major_by_code(self, code: str) -> MajorInfo:
        raw = self._call(self._contract.functions.getMajorByCode(code.upper()))
        return MajorInfo.from_tuple(raw)

    def get_all_majors(self) -> list[MajorInfo]:
        ids = self._call(self._contract.functions.getAllMajors())
        return [self.get_major(i) for i in ids]
