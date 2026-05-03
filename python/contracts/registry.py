"""
python/contracts/registry.py
─────────────────────────────
ContractType enum and deployment metadata.

DEPLOYMENT_ORDER is the topological sort of the dependency graph:
  AccessRegistry  ← no dependencies
  Major           ← no dependencies
  Professor       ← no dependencies
  Student         ← no dependencies
  Course          ← needs Professor address in constructor
  Enrollment      ← needs Student + Course addresses in constructor
  University      ← needs all six above in constructor

NEEDS_BINDING lists sub-contracts that expose setUniversity(address).
After University is deployed, the deployer calls setUniversity on each of
these so they only accept writes from the University address.
"""
from __future__ import annotations

from enum import Enum


class ContractType(Enum):
    ACCESS_REGISTRY = "AccessRegistry"
    MAJOR           = "Major"
    PROFESSOR       = "Professor"
    STUDENT         = "Student"
    COURSE          = "Course"
    ENROLLMENT      = "Enrollment"
    UNIVERSITY      = "University"

    @property
    def abi_filename(self) -> str:
        return f"{self.value}.abi"

    @property
    def bin_filename(self) -> str:
        return f"{self.value}.bin"


# Topological deployment order — do not reorder.
DEPLOYMENT_ORDER: list[ContractType] = [
    ContractType.ACCESS_REGISTRY,
    ContractType.MAJOR,
    ContractType.PROFESSOR,
    ContractType.STUDENT,
    ContractType.COURSE,
    ContractType.ENROLLMENT,
    ContractType.UNIVERSITY,
]

# Sub-contracts that require setUniversity() to be called after deployment.
NEEDS_BINDING: list[ContractType] = [
    ContractType.MAJOR,
    ContractType.PROFESSOR,
    ContractType.STUDENT,
    ContractType.COURSE,
    ContractType.ENROLLMENT,
]
