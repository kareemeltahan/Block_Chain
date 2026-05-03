// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "../access/AccessRegistry.sol";
import "./Major.sol";
import "./Student.sol";
import "./Professor.sol";
import "./Course.sol";
import "./Enrollment.sol";

/// @title  University
/// @notice Single entry-point façade for the entire system.
///         Sub-contracts accept writes ONLY from this address (onlyAuth)
///         so all access control is enforced here and cannot be bypassed.
///
/// ── Role hierarchy ───────────────────────────────────────────────────────────
///   ADMIN_ROLE      full system access; manages roles; cascade-deletes professors
///   REGISTRAR_ROLE  student / course / enrollment CRUD; cannot manage roles
///   INSTRUCTOR_ROLE update marks for their own courses only; read-only otherwise
///
/// ── Size management (EIP-170: 24,576 byte limit) ─────────────────────────────
///   Sub-contracts are declared `immutable` → inlined in bytecode, saves ~200 gas
///   per read vs `public` storage slots and reduces contract size.
///   Role constants are `private constant` → eliminated from storage entirely.
///   All pass-through functions are single-line delegations.
///   Internal helpers (_dropCourse, _dropStudentEnrollments) are reused across
///   multiple public functions to avoid duplicated bytecode.
///
/// ── Deployment note ──────────────────────────────────────────────────────────
///   The deployer script grants ADMIN_ROLE to THIS contract on AccessRegistry
///   after deployment. This allows University to call grantRole/revokeRole
///   internally (e.g. auto-granting INSTRUCTOR_ROLE when a professor is added).
contract University {

    // Immutables: inlined at compile time — cheaper reads, smaller bytecode
    AccessRegistry public immutable ac;
    Major          public immutable maj;
    Student        public immutable stu;
    Professor      public immutable prof;
    Course         public immutable crs;
    Enrollment     public immutable enr;

    // Private constants: not stored in state, eliminated by optimizer
    bytes32 private constant ADMIN      = keccak256("ADMIN_ROLE");
    bytes32 private constant REGISTRAR  = keccak256("REGISTRAR_ROLE");
    bytes32 private constant INSTRUCTOR = keccak256("INSTRUCTOR_ROLE");

    event BatchEnrollment(uint256[] studentIds, string courseId, string semester);

    // ─── Modifiers ────────────────────────────────────────────────────────────

    modifier onlyAdmin() {
        require(ac.hasRole(ADMIN, msg.sender), "admin only");
        _;
    }

    modifier onlyReg() {
        require(
            ac.hasRole(ADMIN,     msg.sender) ||
            ac.hasRole(REGISTRAR, msg.sender),
            "registrar required"
        );
        _;
    }

    modifier onlyInstr() {
        require(
            ac.hasRole(ADMIN,      msg.sender) ||
            ac.hasRole(REGISTRAR,  msg.sender) ||
            ac.hasRole(INSTRUCTOR, msg.sender),
            "instructor required"
        );
        _;
    }

    // ─── Constructor ──────────────────────────────────────────────────────────

    constructor(
        address _ac, address _maj, address _stu,
        address _prof, address _crs, address _enr
    ) {
        ac   = AccessRegistry(_ac);
        maj  = Major(_maj);
        stu  = Student(_stu);
        prof = Professor(_prof);
        crs  = Course(_crs);
        enr  = Enrollment(_enr);
    }

    // ════════════════════════════════════════════════════════════════════════
    // ROLE MANAGEMENT  (ADMIN only)
    // Note: University itself must hold ADMIN_ROLE on AccessRegistry for
    // these internal calls to succeed — granted by deployer script.
    // ════════════════════════════════════════════════════════════════════════

    function grantRole(bytes32 role, address account) external onlyAdmin {
        ac.grantRole(role, account);
    }
    function revokeRole(bytes32 role, address account) external onlyAdmin {
        ac.revokeRole(role, account);
    }
    function hasRole(bytes32 role, address account) external view returns (bool) {
        return ac.hasRole(role, account);
    }
    function getRoleMembers(bytes32 role) external view returns (address[] memory) {
        return ac.getRoleMembers(role);
    }
    // Expose constants so Python layer can read them without hardcoding hashes
    function ADMIN_ROLE()      external pure returns (bytes32) { return ADMIN; }
    function REGISTRAR_ROLE()  external pure returns (bytes32) { return REGISTRAR; }
    function INSTRUCTOR_ROLE() external pure returns (bytes32) { return INSTRUCTOR; }

    // ════════════════════════════════════════════════════════════════════════
    // MAJOR  (ADMIN only — curriculum policy decisions)
    // ════════════════════════════════════════════════════════════════════════

    function addMajor(string calldata c, string calldata n, string calldata d)
        external onlyAdmin returns (uint256) { return maj.addMajor(c, n, d); }
    function updateMajor(uint256 id, string calldata n, string calldata d)
        external onlyAdmin { maj.updateMajor(id, n, d); }
    function deactivateMajor(uint256 id) external onlyAdmin { maj.deactivateMajor(id); }
    function getMajor(uint256 id) external view returns (Major.MajorInfo memory) { return maj.getMajor(id); }
    function getMajorByCode(string calldata c) external view returns (Major.MajorInfo memory) { return maj.getMajorByCode(c); }
    function getAllMajors() external view returns (uint256[] memory) { return maj.getAllMajors(); }

    // ════════════════════════════════════════════════════════════════════════
    // PROFESSOR  (add/update: REGISTRAR+; delete: ADMIN only)
    // ════════════════════════════════════════════════════════════════════════

    /// @notice Adds professor and auto-grants INSTRUCTOR_ROLE to their address.
    function addProfessor(string calldata n, string calldata d, address a)
        external onlyReg returns (uint256)
    {
        uint256 id = prof.addProfessor(n, d, a);
        if (!ac.hasRole(INSTRUCTOR, a)) ac.grantRole(INSTRUCTOR, a);
        return id;
    }
    function updateProfessor(uint256 id, string calldata n, string calldata d, address a)
        external onlyReg { prof.updateProfessor(id, n, d, a); }

    /// @notice Cascade: deletes all professor's courses → unenrolls students → revokes role.
    function deleteProfessor(uint256 id) external onlyAdmin {
        require(prof.isActive(id), "not found");
        address pa = prof.getProfessor(id).professorAddress;
        Course.CourseInfo[] memory cs = crs.getCoursesByProfessor(id);
        for (uint256 i = 0; i < cs.length; i++) _dropCourse(cs[i].id);
        ac.revokeRole(INSTRUCTOR, pa);
        prof.removeProfessor(id);
    }
    function getProfessor(uint256 id) external view returns (Professor.ProfessorInfo memory) { return prof.getProfessor(id); }
    function getAllProfessors() external view returns (uint256[] memory) { return prof.getActiveProfessors(); }

    // ════════════════════════════════════════════════════════════════════════
    // STUDENT  (REGISTRAR+)
    // ════════════════════════════════════════════════════════════════════════

    function addStudent(string calldata n, uint256 mId, uint256 yr, uint256 pId, address w)
        external onlyReg returns (uint256)
    {
        require(maj.isActive(mId),  "invalid major");
        require(prof.isActive(pId), "invalid professor");
        return stu.addStudent(n, mId, yr, prof.getProfessor(pId).professorAddress, w);
    }
    function updateStudent(uint256 id, string calldata n, uint256 mId, uint256 yr, uint256 pId, address w)
        external onlyReg
    {
        address sup = pId > 0 ? prof.getProfessor(pId).professorAddress : address(0);
        stu.updateStudent(id, n, mId, yr, sup, w);
    }
    /// @notice Cascade: unenrolls from all active courses before deletion.
    function deleteStudent(uint256 id) external onlyReg {
        _dropStudentEnrollments(id);
        stu.deleteStudent(id);
    }
    function getStudent(uint256 id) external view returns (Student.StudentInfo memory) { return stu.getStudent(id); }
    function getAllStudents() external view returns (uint256[] memory) { return stu.getAllStudents(); }

    // ════════════════════════════════════════════════════════════════════════
    // COURSE  (REGISTRAR+)
    // ════════════════════════════════════════════════════════════════════════

    function createCourse(string calldata id, string calldata n, uint256 pId)
        external onlyReg { crs.createCourse(id, n, pId); }
    function updateCourse(string calldata id, string calldata n)
        external onlyReg { crs.updateCourse(id, n); }
    function reassignCourse(string calldata id, uint256 pId)
        external onlyReg { crs.reassignCourse(id, pId); }
    /// @notice Cascade: unenrolls all students from this course before deletion.
    function deleteCourse(string calldata id) external onlyReg { _dropCourse(id); }
    function getCourse(string calldata id) external view returns (Course.CourseInfo memory) { return crs.getCourse(id); }
    function getAllCourses() external view returns (string[] memory) { return crs.getAllCourses(); }

    // ════════════════════════════════════════════════════════════════════════
    // ENROLLMENT  (enroll/unenroll: REGISTRAR+; marks: INSTRUCTOR+)
    // ════════════════════════════════════════════════════════════════════════

    function enrollStudentInCourse(uint256 sid, string calldata cid, string calldata sem)
        external onlyReg
    {
        require(stu.isActive(sid), "invalid student");
        require(crs.exists(cid),   "invalid course");
        require(!enr.getEnrollment(enr.getEnrollmentKey(sid, cid, sem)).active, "already enrolled");
        enr.enrollStudent(sid, cid, sem);
    }

    function batchEnroll(uint256[] calldata sids, string calldata cid, string calldata sem)
        external onlyReg
    {
        require(crs.exists(cid), "invalid course");
        for (uint256 i = 0; i < sids.length; i++) {
            uint256 s = sids[i];
            if (!stu.isActive(s)) continue;
            if (enr.getEnrollment(enr.getEnrollmentKey(s, cid, sem)).active) continue;
            enr.enrollStudent(s, cid, sem);
        }
        emit BatchEnrollment(sids, cid, sem);
    }

    function removeCourseFromStudent(uint256 sid, string calldata cid, string calldata sem)
        external onlyReg
    {
        if (enr.getEnrollment(enr.getEnrollmentKey(sid, cid, sem)).active)
            enr.unenrollStudent(sid, cid, sem);
    }

    /// @notice INSTRUCTOR_ROLE holders may only grade courses they own.
    ///         ADMIN and REGISTRAR may grade any course.
    function updateStudentMark(uint256 sid, string calldata cid, string calldata sem, uint8 mark)
        external onlyInstr
    {
        if (!ac.hasRole(ADMIN, msg.sender) && !ac.hasRole(REGISTRAR, msg.sender)) {
            uint256 myId = prof.getProfessorIdByAddress(msg.sender);
            require(crs.getCourse(cid).professorId == myId, "not your course");
        }
        enr.updateMark(sid, cid, sem, mark);
    }

    // ── Enrollment reads ──────────────────────────────────────────────────────

    function getStudentEnrollments(uint256 sid)
        external view returns (Enrollment.EnrollmentRecord[] memory)
    { return enr.getStudentEnrollments(sid); }

    function getStudentSemesterEnrollments(uint256 sid, string calldata sem)
        external view returns (Enrollment.EnrollmentRecord[] memory)
    { return enr.getStudentSemesterEnrollments(sid, sem); }

    function getStudentSemesters(uint256 sid) external view returns (string[] memory) {
        return enr.getStudentSemesters(sid);
    }

    function getCourseEnrollments(string calldata cid)
        external view returns (Enrollment.EnrollmentRecord[] memory)
    { return enr.getCourseEnrollments(cid); }

    function calculateStudentGPA(uint256 sid) external view returns (uint256) {
        (uint256 t, uint256 c) = enr.calculateGPA(sid);
        return c == 0 ? 0 : t / c;
    }

    // ── Internal cascade helpers ──────────────────────────────────────────────

    /// Unenrolls all students enrolled in a course, then deletes the course.
    function _dropCourse(string memory cid) internal {
        Enrollment.EnrollmentRecord[] memory recs = enr.getCourseEnrollments(cid);
        for (uint256 i = 0; i < recs.length; i++)
            if (recs[i].active) enr.unenrollStudent(recs[i].studentId, cid, recs[i].semester);
        crs.deleteCourse(cid);
    }

    /// Unenrolls a student from all their active courses.
    function _dropStudentEnrollments(uint256 sid) internal {
        Enrollment.EnrollmentRecord[] memory recs = enr.getStudentEnrollments(sid);
        for (uint256 i = 0; i < recs.length; i++)
            if (recs[i].active) enr.unenrollStudent(sid, recs[i].courseId, recs[i].semester);
    }
}
