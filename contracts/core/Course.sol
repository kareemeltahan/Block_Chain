// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./Professor.sol";

/// @title  Course
/// @notice Registry of courses. String-keyed (e.g. "CS101").
///         Maintains a per-professor inverse index for cascade-delete efficiency.
contract Course {
    struct CourseInfo {
        string  id;
        string  name;
        uint256 professorId;
        bool    active;
    }

    mapping(string  => CourseInfo) public courses;
    mapping(string  => bool)       public exists;
    mapping(uint256 => string[])   public professorCourses; // professorId → courseId[]
    string[] public allCourses;

    Professor public immutable professorContract;
    address public university;
    address public immutable deployer;

    event CourseCreated(string indexed id, uint256 professorId);
    event CourseUpdated(string indexed id);
    event CourseDeleted(string indexed id);
    event CourseReassigned(string indexed id, uint256 oldProfId, uint256 newProfId);

    modifier onlyAuth() {
        require(msg.sender == university || msg.sender == deployer, "Crs: unauthorized");
        _;
    }

    constructor(address _prof) {
        deployer          = msg.sender;
        professorContract = Professor(_prof);
    }

    function setUniversity(address _u) external {
        require(msg.sender == deployer,   "Crs: deployer only");
        require(university  == address(0),"Crs: already bound");
        require(_u != address(0),         "Crs: zero address");
        university = _u;
    }

    // ─── Write ────────────────────────────────────────────────────────────────

    function createCourse(string calldata id, string calldata name, uint256 profId)
        external onlyAuth
    {
        require(!exists[id],                          "Crs: already exists");
        require(professorContract.isActive(profId),   "Crs: invalid professor");
        require(bytes(id).length > 0,                 "Crs: empty id");
        require(bytes(name).length > 0,               "Crs: empty name");
        courses[id] = CourseInfo(id, name, profId, true);
        exists[id]  = true;
        allCourses.push(id);
        professorCourses[profId].push(id);
        emit CourseCreated(id, profId);
    }

    function updateCourse(string calldata id, string calldata name) external onlyAuth {
        require(exists[id],               "Crs: not found");
        require(bytes(name).length > 0,   "Crs: empty name");
        courses[id].name = name;
        emit CourseUpdated(id);
    }

    function reassignCourse(string calldata id, uint256 newProfId) external onlyAuth {
        require(exists[id],                         "Crs: not found");
        require(professorContract.isActive(newProfId),"Crs: invalid professor");
        uint256 oldId = courses[id].professorId;
        if (oldId == newProfId) return;
        _removeFromProfList(oldId, id);
        courses[id].professorId = newProfId;
        professorCourses[newProfId].push(id);
        emit CourseReassigned(id, oldId, newProfId);
    }

    function deleteCourse(string calldata id) external onlyAuth {
        require(exists[id], "Crs: not found");
        _removeFromProfList(courses[id].professorId, id);
        _removeFromAll(id);
        delete exists[id];
        courses[id].active = false;
        emit CourseDeleted(id);
    }

    // ─── Read ─────────────────────────────────────────────────────────────────

    function getCourse(string calldata id) external view returns (CourseInfo memory) {
        require(exists[id], "Crs: not found");
        return courses[id];
    }

    function getAllCourses() external view returns (string[] memory) { return allCourses; }

    function getCoursesByProfessor(uint256 profId) external view returns (CourseInfo[] memory) {
        string[] storage ids = professorCourses[profId];
        CourseInfo[] memory out = new CourseInfo[](ids.length);
        for (uint256 i = 0; i < ids.length; i++) out[i] = courses[ids[i]];
        return out;
    }

    // ─── Internal ─────────────────────────────────────────────────────────────

    function _removeFromProfList(uint256 profId, string memory id) internal {
        string[] storage list = professorCourses[profId];
        for (uint256 i = 0; i < list.length; i++) {
            if (keccak256(bytes(list[i])) == keccak256(bytes(id))) {
                list[i] = list[list.length - 1];
                list.pop();
                return;
            }
        }
    }

    function _removeFromAll(string memory id) internal {
        for (uint256 i = 0; i < allCourses.length; i++) {
            if (keccak256(bytes(allCourses[i])) == keccak256(bytes(id))) {
                allCourses[i] = allCourses[allCourses.length - 1];
                allCourses.pop();
                return;
            }
        }
    }
}
