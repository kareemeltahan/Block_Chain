// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title  Major
/// @notice Registry of academic majors (CS, AI, IT, CYB, …).
///         Students reference Major.id instead of a free-form string,
///         giving referential integrity and O(1) existence checks.
///
///         Access model: deployer or University only (onlyAuth).
///         University is bound via setUniversity() after deployment.
contract Major {
    struct MajorInfo {
        uint256 id;
        string  code;        // short uppercase key: "CS", "AI", "IT"
        string  name;        // full name: "Computer Science"
        string  description;
        bool    active;
    }

    uint256 public nextId = 1;

    mapping(uint256 => MajorInfo) public majors;
    mapping(uint256 => bool)      public isActive;
    mapping(string  => uint256)   public codeToId;  // unique code → id
    uint256[] public allMajors;

    address public university;
    address public immutable deployer;

    event MajorAdded(uint256 indexed id, string code);
    event MajorUpdated(uint256 indexed id);
    event MajorDeactivated(uint256 indexed id);

    modifier onlyAuth() {
        require(msg.sender == university || msg.sender == deployer, "Major: unauthorized");
        _;
    }

    constructor() { deployer = msg.sender; }

    /// @notice One-time binding to University. Deployer only.
    function setUniversity(address _u) external {
        require(msg.sender == deployer,   "Major: deployer only");
        require(university  == address(0),"Major: already bound");
        require(_u != address(0),         "Major: zero address");
        university = _u;
    }

    // ─── Write ────────────────────────────────────────────────────────────────

    function addMajor(string calldata code, string calldata name, string calldata desc)
        external onlyAuth returns (uint256)
    {
        require(bytes(code).length > 0 && bytes(name).length > 0, "Major: empty field");
        require(codeToId[code] == 0, "Major: code exists");
        uint256 id = nextId++;
        majors[id] = MajorInfo(id, code, name, desc, true);
        isActive[id]   = true;
        codeToId[code] = id;
        allMajors.push(id);
        emit MajorAdded(id, code);
        return id;
    }

    function updateMajor(uint256 id, string calldata name, string calldata desc)
        external onlyAuth
    {
        require(isActive[id], "Major: not found");
        if (bytes(name).length > 0) majors[id].name        = name;
        if (bytes(desc).length > 0) majors[id].description = desc;
        emit MajorUpdated(id);
    }

    function deactivateMajor(uint256 id) external onlyAuth {
        require(isActive[id], "Major: not found");
        isActive[id]       = false;
        majors[id].active  = false;
        emit MajorDeactivated(id);
    }

    // ─── Read ─────────────────────────────────────────────────────────────────

    function getMajor(uint256 id) external view returns (MajorInfo memory) {
        require(isActive[id], "Major: not found");
        return majors[id];
    }

    function getMajorByCode(string calldata code) external view returns (MajorInfo memory) {
        uint256 id = codeToId[code];
        require(id != 0 && isActive[id], "Major: not found");
        return majors[id];
    }

    function getAllMajors() external view returns (uint256[] memory) { return allMajors; }
}
