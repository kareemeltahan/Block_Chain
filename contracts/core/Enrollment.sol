// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./Student.sol";
import "./Course.sol";

/// @title  Enrollment
/// @notice Tracks student–course–semester records.
///
///         KEY DESIGN: enrollment key = keccak256(studentId ++ courseId ++ semester)
///         This means a student can enroll in the same course in different semesters
///         (retake / repeated course), each being a fully independent record.
///
///         PER-STUDENT SEMESTER MAP:
///           studentSemesterKeys[sid][semester] → bytes32[]
///         Enables O(1) "what did student X take in spring2025?" without scanning
///         all enrollments.
///
///         DELETION (swap-and-pop):
///         Each EnrollmentRecord stores three array indices (one per index structure).
///         On unenrollment, all three arrays are updated in O(1) — the displaced
///         element's index fields are updated to reflect its new position.
///         v1 bug fixed: the original code had a _swapPop() that did NOT update
///         the displaced element's index, making subsequent deletions corrupt.
contract Enrollment {

    struct EnrollmentRecord {
        uint256 studentId;
        string  courseId;
        string  semester;            // "spring2025", "autumn2026", etc.
        uint8   mark;                // 0-100; 0 = not yet graded
        bool    active;
        uint256 studentArrayIndex;   // position in studentEnrollmentKeys[sid]
        uint256 courseArrayIndex;    // position in courseEnrollmentKeys[cid]
        uint256 semesterArrayIndex;  // position in studentSemesterKeys[sid][sem]
    }

    // ─── Storage ─────────────────────────────────────────────────────────────

    // Primary lookup: key → record
    mapping(bytes32 => EnrollmentRecord) public enrollments;

    // All enrollment keys for a student (all semesters combined)
    mapping(uint256 => bytes32[]) public studentEnrollmentKeys;

    // All enrollment keys for a course (all semesters combined)
    mapping(string  => bytes32[]) public courseEnrollmentKeys;

    // Per-student per-semester enrollment keys
    mapping(uint256 => mapping(string => bytes32[])) public studentSemesterKeys;

    // Ordered list of distinct semesters a student has enrolled in
    mapping(uint256 => string[])                  public studentSemesters;
    mapping(uint256 => mapping(string => bool))   public studentHasSemester;

    Student public immutable studentContract;
    Course  public immutable courseContract;

    address public university;
    address public immutable deployer;

    // ─── Events ──────────────────────────────────────────────────────────────

    event StudentEnrolled  (uint256 indexed studentId, string indexed courseId, string semester);
    event StudentUnenrolled(uint256 indexed studentId, string indexed courseId, string semester);
    event MarkUpdated      (uint256 indexed studentId, string indexed courseId, string semester, uint8 mark);

    modifier onlyAuth() {
        require(msg.sender == university || msg.sender == deployer, "Enr: unauthorized");
        _;
    }

    constructor(address _student, address _course) {
        deployer        = msg.sender;
        studentContract = Student(_student);
        courseContract  = Course(_course);
    }

    function setUniversity(address _u) external {
        require(msg.sender == deployer,   "Enr: deployer only");
        require(university  == address(0),"Enr: already bound");
        require(_u != address(0),         "Enr: zero address");
        university = _u;
    }

    // ─── Key helper ──────────────────────────────────────────────────────────

    function getEnrollmentKey(uint256 sid, string memory cid, string memory sem)
        public pure returns (bytes32)
    {
        return keccak256(abi.encodePacked(sid, cid, sem));
    }

    function getEnrollment(bytes32 key) external view returns (EnrollmentRecord memory) {
        return enrollments[key];
    }

    // ─── Write ────────────────────────────────────────────────────────────────

    function enrollStudent(uint256 sid, string memory cid, string memory sem)
        external onlyAuth
    {
        require(studentContract.isActive(sid), "Enr: invalid student");
        require(courseContract.exists(cid),     "Enr: invalid course");
        require(bytes(sem).length > 0,          "Enr: empty semester");

        bytes32 key = getEnrollmentKey(sid, cid, sem);
        require(!enrollments[key].active, "Enr: already enrolled");

        // Track first appearance of this semester for the student
        if (!studentHasSemester[sid][sem]) {
            studentSemesters[sid].push(sem);
            studentHasSemester[sid][sem] = true;
        }

        enrollments[key] = EnrollmentRecord({
            studentId:          sid,
            courseId:           cid,
            semester:           sem,
            mark:               0,
            active:             true,
            studentArrayIndex:  studentEnrollmentKeys[sid].length,
            courseArrayIndex:   courseEnrollmentKeys[cid].length,
            semesterArrayIndex: studentSemesterKeys[sid][sem].length
        });

        studentEnrollmentKeys[sid].push(key);
        courseEnrollmentKeys[cid].push(key);
        studentSemesterKeys[sid][sem].push(key);

        emit StudentEnrolled(sid, cid, sem);
    }

    function unenrollStudent(uint256 sid, string memory cid, string memory sem)
        external onlyAuth
    {
        bytes32 key = getEnrollmentKey(sid, cid, sem);
        require(enrollments[key].active, "Enr: not enrolled");

        // Remove from all three index arrays, updating displaced elements' indices.
        _pop(studentEnrollmentKeys[sid],       key, 0);
        _pop(courseEnrollmentKeys[cid],        key, 1);
        _pop(studentSemesterKeys[sid][sem],    key, 2);

        enrollments[key].active = false;
        emit StudentUnenrolled(sid, cid, sem);
    }

    function updateMark(uint256 sid, string memory cid, string memory sem, uint8 mark)
        external onlyAuth
    {
        require(mark <= 100, "Enr: mark > 100");
        bytes32 key = getEnrollmentKey(sid, cid, sem);
        require(enrollments[key].active, "Enr: not enrolled");
        enrollments[key].mark = mark;
        emit MarkUpdated(sid, cid, sem, mark);
    }

    // ─── Read ─────────────────────────────────────────────────────────────────

    /// All enrollments for a student across all semesters
    function getStudentEnrollments(uint256 sid)
        external view returns (EnrollmentRecord[] memory)
    { return _resolve(studentEnrollmentKeys[sid]); }

    /// All enrollments for a student in a specific semester
    function getStudentSemesterEnrollments(uint256 sid, string memory sem)
        external view returns (EnrollmentRecord[] memory)
    { return _resolve(studentSemesterKeys[sid][sem]); }

    /// Ordered list of distinct semesters a student has appeared in
    function getStudentSemesters(uint256 sid)
        external view returns (string[] memory)
    { return studentSemesters[sid]; }

    /// All enrollments for a course (all semesters)
    function getCourseEnrollments(string memory cid)
        external view returns (EnrollmentRecord[] memory)
    { return _resolve(courseEnrollmentKeys[cid]); }

    /// Returns raw (totalMarks, gradedCount) for external GPA computation.
    /// Only counts active records with mark > 0.
    function calculateGPA(uint256 sid)
        external view returns (uint256 totalMarks, uint256 count)
    {
        bytes32[] memory keys = studentEnrollmentKeys[sid];
        for (uint256 i = 0; i < keys.length; i++) {
            EnrollmentRecord storage r = enrollments[keys[i]];
            if (r.active && r.mark > 0) {
                totalMarks += r.mark;
                count++;
            }
        }
    }

    // ─── Internal ─────────────────────────────────────────────────────────────

    /// @dev Swap-and-pop `key` from `arr`.
    ///      `which`: 0 = studentArrayIndex, 1 = courseArrayIndex, 2 = semesterArrayIndex
    ///      Updates the displaced element's correct index field after the swap.
    function _pop(bytes32[] storage arr, bytes32 key, uint8 which) internal {
        uint256 idx;
        if      (which == 0) idx = enrollments[key].studentArrayIndex;
        else if (which == 1) idx = enrollments[key].courseArrayIndex;
        else                 idx = enrollments[key].semesterArrayIndex;

        uint256 last = arr.length - 1;
        if (idx != last) {
            bytes32 moved = arr[last];
            arr[idx] = moved;
            if      (which == 0) enrollments[moved].studentArrayIndex  = idx;
            else if (which == 1) enrollments[moved].courseArrayIndex   = idx;
            else                 enrollments[moved].semesterArrayIndex = idx;
        }
        arr.pop();
    }

    function _resolve(bytes32[] memory keys)
        internal view returns (EnrollmentRecord[] memory out)
    {
        out = new EnrollmentRecord[](keys.length);
        for (uint256 i = 0; i < keys.length; i++) out[i] = enrollments[keys[i]];
    }
}
