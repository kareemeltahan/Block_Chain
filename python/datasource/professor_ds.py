"""datasource/professor_ds.py"""
from __future__ import annotations

from web3.contract import Contract

from python.datasource.base import BaseDataSource
from python.models.types import ProfessorInfo, CourseInfo


class ProfessorDataSource(BaseDataSource):
    def __init__(self, contract: Contract):
        super().__init__(contract)

    # ─── Write ───────────────────────────────────────────────────────────────

    def add_professor(self, name: str, department: str, professor_address: str) -> dict:
        if not name or not department:
            raise ValueError("name and department are required")
        if not professor_address:
            raise ValueError("professor_address is required")
        return self._tx(
            self._contract.functions.addProfessor(name, department, professor_address)
        )

    def update_professor(
        self,
        professor_id: int,
        name: str = "",
        department: str = "",
        new_address: str = "0x0000000000000000000000000000000000000000",
    ) -> dict:
        if professor_id <= 0:
            raise ValueError("professor_id must be positive")
        return self._tx(
            self._contract.functions.updateProfessor(professor_id, name, department, new_address)
        )

    def delete_professor(self, professor_id: int) -> dict:
        if professor_id <= 0:
            raise ValueError("professor_id must be positive")
        return self._tx(self._contract.functions.deleteProfessor(professor_id))

    # ─── Read ────────────────────────────────────────────────────────────────

    def get_professor(self, professor_id: int) -> ProfessorInfo:
        raw = self._call(self._contract.functions.getProfessor(professor_id))
        return ProfessorInfo.from_tuple(raw)

    def get_all_professors(self) -> list[ProfessorInfo]:
        ids = self._call(self._contract.functions.getAllProfessors())
        return [self.get_professor(i) for i in ids]
