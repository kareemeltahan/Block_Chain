// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title  Professor
/// @notice Registry of professors with correct per-professor address ownership.
///
///         v1 bug fixed: professorAddress was msg.sender at call time.
///         Since University called addProfessor, all professors shared the
///         admin address and the addressToId reverse-lookup was broken.
///         Now professorAddress is an explicit parameter with a unique constraint.
contract Professor {
    struct ProfessorInfo {
        uint256 id;
        address professorAddress; // the professor's own EOA — unique
        string  name;
        string  department;
        bool    active;
    }

    uint256 public nextId = 1;

    mapping(uint256 => ProfessorInfo) public professors;
    mapping(uint256 => bool)          public isActive;
    mapping(address => uint256)       public addressToId;
    uint256[] public allProfessors;

    address public university;
    address public immutable deployer;

    event ProfessorAdded(uint256 indexed id, address indexed addr);
    event ProfessorRemoved(uint256 indexed id);
    event ProfessorUpdated(uint256 indexed id);

    modifier onlyAuth() {
        require(msg.sender == university || msg.sender == deployer, "Prof: unauthorized");
        _;
    }

    constructor() { deployer = msg.sender; }

    function setUniversity(address _u) external {
        require(msg.sender == deployer,   "Prof: deployer only");
        require(university  == address(0),"Prof: already bound");
        require(_u != address(0),         "Prof: zero address");
        university = _u;
    }

    // ─── Write ────────────────────────────────────────────────────────────────

    function addProfessor(string calldata name, string calldata dept, address addr)
        external onlyAuth returns (uint256)
    {
        require(addr != address(0),           "Prof: zero address");
        require(addressToId[addr] == 0,       "Prof: address taken");
        require(bytes(name).length > 0,       "Prof: empty name");
        uint256 id = nextId++;
        professors[id] = ProfessorInfo(id, addr, name, dept, true);
        isActive[id]   = true;
        allProfessors.push(id);
        addressToId[addr] = id;
        emit ProfessorAdded(id, addr);
        return id;
    }

    function updateProfessor(uint256 id, string calldata name, string calldata dept, address newAddr)
        external onlyAuth
    {
        require(isActive[id], "Prof: not found");
        if (bytes(name).length > 0) professors[id].name       = name;
        if (bytes(dept).length > 0) professors[id].department = dept;
        if (newAddr != address(0) && newAddr != professors[id].professorAddress) {
            require(addressToId[newAddr] == 0, "Prof: address taken");
            delete addressToId[professors[id].professorAddress];
            professors[id].professorAddress = newAddr;
            addressToId[newAddr] = id;
        }
        emit ProfessorUpdated(id);
    }

    function removeProfessor(uint256 id) external onlyAuth {
        require(isActive[id], "Prof: not found");
        delete addressToId[professors[id].professorAddress];
        // swap-and-pop
        for (uint256 i = 0; i < allProfessors.length; i++) {
            if (allProfessors[i] == id) {
                allProfessors[i] = allProfessors[allProfessors.length - 1];
                allProfessors.pop();
                break;
            }
        }
        isActive[id]          = false;
        professors[id].active = false;
        emit ProfessorRemoved(id);
    }

    // ─── Read ─────────────────────────────────────────────────────────────────

    function getProfessor(uint256 id) external view returns (ProfessorInfo memory) {
        require(isActive[id], "Prof: not found");
        return professors[id];
    }

    function getProfessorIdByAddress(address addr) external view returns (uint256) {
        uint256 id = addressToId[addr];
        require(id != 0 && isActive[id], "Prof: not found");
        return id;
    }

    function getActiveProfessors() external view returns (uint256[] memory) { return allProfessors; }
}
