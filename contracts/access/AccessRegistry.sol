// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title  AccessRegistry
/// @notice On-chain RBAC with three roles: ADMIN > REGISTRAR > INSTRUCTOR.
///
///         Design decisions:
///         - superAdmin (deployer) can never lose ADMIN_ROLE — prevents lockout.
///         - Member lists are maintained with swap-and-pop so enumeration is O(N)
///           and grant/revoke are O(1) after the index lookup.
///         - The University contract is granted ADMIN_ROLE post-deployment so it
///           can call grantRole/revokeRole internally (e.g. auto-granting
///           INSTRUCTOR_ROLE when addProfessor is called).
contract AccessRegistry {
    bytes32 public constant ADMIN_ROLE      = keccak256("ADMIN_ROLE");
    bytes32 public constant REGISTRAR_ROLE  = keccak256("REGISTRAR_ROLE");
    bytes32 public constant INSTRUCTOR_ROLE = keccak256("INSTRUCTOR_ROLE");

    address public immutable superAdmin;

    mapping(bytes32 => mapping(address => bool))    private _has;
    mapping(bytes32 => address[])                   private _members;
    mapping(bytes32 => mapping(address => uint256)) private _idx; // 1-based

    event RoleGranted(bytes32 indexed role, address indexed account, address indexed sender);
    event RoleRevoked(bytes32 indexed role, address indexed account, address indexed sender);

    modifier onlyAdmin() {
        require(_has[ADMIN_ROLE][msg.sender], "AR: admin only");
        _;
    }

    constructor() {
        superAdmin = msg.sender;
        _grant(ADMIN_ROLE, msg.sender);
    }

    // ─── External ────────────────────────────────────────────────────────────

    function grantRole(bytes32 role, address account) external onlyAdmin {
        _grant(role, account);
    }

    function revokeRole(bytes32 role, address account) external onlyAdmin {
        require(
            !(role == ADMIN_ROLE && account == superAdmin),
            "AR: cannot revoke superAdmin"
        );
        _revoke(role, account);
    }

    function hasRole(bytes32 role, address account) external view returns (bool) {
        return _has[role][account];
    }

    function getRoleMembers(bytes32 role) external view returns (address[] memory) {
        return _members[role];
    }

    function getRoleMemberCount(bytes32 role) external view returns (uint256) {
        return _members[role].length;
    }

    // ─── Internal ────────────────────────────────────────────────────────────

    function _grant(bytes32 role, address account) internal {
        if (_has[role][account]) return;
        _has[role][account] = true;
        _members[role].push(account);
        _idx[role][account] = _members[role].length; // 1-based
        emit RoleGranted(role, account, msg.sender);
    }

    function _revoke(bytes32 role, address account) internal {
        if (!_has[role][account]) return;
        _has[role][account] = false;

        uint256 i    = _idx[role][account] - 1; // 0-based
        uint256 last = _members[role].length - 1;
        if (i != last) {
            address moved       = _members[role][last];
            _members[role][i]   = moved;
            _idx[role][moved]   = i + 1;
        }
        _members[role].pop();
        delete _idx[role][account];

        emit RoleRevoked(role, account, msg.sender);
    }
}
