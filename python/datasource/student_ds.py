"""datasource/student_ds.py"""
from __future__ import annotations

from web3.contract import Contract

from python.datasource.base import BaseDataSource
from python.models.types import StudentInfo

ZERO_ADDR = "0x0000000000000000000000000000000000000000"


class StudentDataSource(BaseDataSource):
    def __init__(self, contract: Contract):
        super().__init__(contract)

    # ─── Write ───────────────────────────────────────────────────────────────

    def add_student(
        self,
        name: str,
        major_id: int,
        year: int,
        professor_id: int,
        wallet_address: str = ZERO_ADDR,
    ) -> dict:
        if not name:
            raise ValueError("name is required")
        if major_id <= 0:
            raise ValueError("major_id must be positive")
        if professor_id <= 0:
            raise ValueError("professor_id must be positive")
        if year <= 0:
            raise ValueError("year must be positive")
        return self._tx(
            self._contract.functions.addStudent(name, major_id, year, professor_id, wallet_address)
        )

    def update_student(
        self,
        student_id: int,
        name: str = "",
        major_id: int = 0,
        year: int = 0,
        professor_id: int = 0,
        wallet_address: str = ZERO_ADDR,
    ) -> dict:
        if student_id <= 0:
            raise ValueError("student_id must be positive")
        return self._tx(
            self._contract.functions.updateStudent(
                student_id, name, major_id, year, professor_id, wallet_address
            )
        )

    def delete_student(self, student_id: int) -> dict:
        if student_id <= 0:
            raise ValueError("student_id must be positive")
        return self._tx(self._contract.functions.deleteStudent(student_id))

    # ─── Read ────────────────────────────────────────────────────────────────

    def get_student(self, student_id: int) -> StudentInfo:
        raw = self._call(self._contract.functions.getStudent(student_id))
        return StudentInfo.from_tuple(raw)

    def get_all_students(self, offset: int = 0, limit: int = 100) -> list[StudentInfo]:
        ids = self._call(self._contract.functions.getAllStudents())
        return [self.get_student(i) for i in ids[offset : offset + limit]]
