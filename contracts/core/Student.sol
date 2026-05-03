// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title  Student
/// @notice Registry of students.
///
///         Key changes from v1:
///         - `major` (free string) → `majorId` (uint256 ref to Major.id)
///         - `walletAddress` field added for optional student EOA / reverse lookup
///         - `onlyAuth` blocks direct external calls; all writes go through University
contract Student {
    struct StudentInfo {
        uint256 id;
        string  name;
        uint256 majorId;           // references Major.id
        uint256 year;              // enrollment year, e.g. 2024
        address academicSupervisor;// professor's own EOA
        address walletAddress;     // student's own EOA (optional)
        bool    active;
    }

    uint256 public nextId = 1;

    mapping(uint256 => StudentInfo) public students;
    mapping(uint256 => bool)        public isActive;
    mapping(address => uint256)     public addressToId;
    uint256[] public allStudents;

    address public university;
    address public immutable deployer;

    event StudentAdded(uint256 indexed id);
    event StudentUpdated(uint256 indexed id);
    event StudentDeleted(uint256 indexed id);

    modifier onlyAuth() {
        require(msg.sender == university || msg.sender == deployer, "Stu: unauthorized");
        _;
    }

    constructor() { deployer = msg.sender; }

    function setUniversity(address _u) external {
        require(msg.sender == deployer,   "Stu: deployer only");
        require(university  == address(0),"Stu: already bound");
        require(_u != address(0),         "Stu: zero address");
        university = _u;
    }

    // ─── Write ────────────────────────────────────────────────────────────────

    function addStudent(
        string  calldata name,
        uint256 majorId,
        uint256 year,
        address supervisor,
        address wallet
    ) external onlyAuth returns (uint256) {
        require(bytes(name).length > 0, "Stu: empty name");
        require(majorId > 0,            "Stu: invalid major");
        require(year > 0,               "Stu: invalid year");
        uint256 id = nextId++;
        students[id] = StudentInfo(id, name, majorId, year, supervisor, wallet, true);
        isActive[id] = true;
        allStudents.push(id);
        if (wallet != address(0)) addressToId[wallet] = id;
        emit StudentAdded(id);
        return id;
    }

    function updateStudent(
        uint256 id,
        string  calldata name,
        uint256 majorId,
        uint256 year,
        address supervisor,
        address wallet
    ) external onlyAuth {
        require(isActive[id], "Stu: not found");
        StudentInfo storage s = students[id];
        if (bytes(name).length > 0) s.name  = name;
        if (majorId > 0)             s.majorId = majorId;
        if (year > 0)                s.year    = year;
        if (supervisor != address(0)) s.academicSupervisor = supervisor;
        if (wallet != address(0) && wallet != s.walletAddress) {
            if (s.walletAddress != address(0)) delete addressToId[s.walletAddress];
            s.walletAddress    = wallet;
            addressToId[wallet] = id;
        }
        emit StudentUpdated(id);
    }

    function deleteStudent(uint256 id) external onlyAuth {
        require(isActive[id], "Stu: not found");
        if (students[id].walletAddress != address(0))
            delete addressToId[students[id].walletAddress];
        for (uint256 i = 0; i < allStudents.length; i++) {
            if (allStudents[i] == id) {
                allStudents[i] = allStudents[allStudents.length - 1];
                allStudents.pop();
                break;
            }
        }
        isActive[id]        = false;
        students[id].active = false;
        emit StudentDeleted(id);
    }

    // ─── Read ─────────────────────────────────────────────────────────────────

    function getStudent(uint256 id) external view returns (StudentInfo memory) {
        require(isActive[id], "Stu: not found");
        return students[id];
    }

    function getStudentByAddress(address wallet) external view returns (StudentInfo memory) {
        uint256 id = addressToId[wallet];
        require(id != 0 && isActive[id], "Stu: not found");
        return students[id];
    }

    function getAllStudents() external view returns (uint256[] memory) { return allStudents; }
}
