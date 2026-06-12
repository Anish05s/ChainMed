// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title ChainMed
 * @notice Records pharmaceutical shipment handoffs immutably on-chain.
 *         Designed for Ethereum Sepolia testnet (MVP).
 *         Production target: Hyperledger Fabric.
 */
contract ChainMed {

    address public owner;

    struct HandoffRecord {
        string  dataHash;       // SHA-256 of verified shipment data
        string  status;         // "VERIFIED" | "FLAGGED" | "PENDING"
        uint8   riskScore;      // 0–100
        uint256 timestamp;
        bool    exists;
        string  flagReason;     // populated only if status == "FLAGGED"
    }

    // shipmentId (string UUID) → HandoffRecord
    mapping(string => HandoffRecord) private _handoffs;

    // ordered list of shipment IDs for iteration
    string[] private _shipmentIds;

    // ── Events ──────────────────────────────────────────────────────────────
    event HandoffRecorded(
        string indexed shipmentId,
        string status,
        uint8  riskScore,
        uint256 timestamp
    );

    event ShipmentFlagged(
        string indexed shipmentId,
        string reason,
        uint256 timestamp
    );

    // ── Modifiers ────────────────────────────────────────────────────────────
    modifier onlyOwner() {
        require(msg.sender == owner, "ChainMed: caller is not the owner");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    // ── Write functions ──────────────────────────────────────────────────────

    /**
     * @notice Record a verified/flagged shipment handoff on-chain.
     * @param shipmentId  UUID of the shipment (string)
     * @param dataHash    SHA-256 hex of the verified data payload
     * @param status      "VERIFIED" | "FLAGGED" | "PENDING"
     * @param riskScore   AI risk score 0–100
     */
    function recordHandoff(
        string calldata shipmentId,
        string calldata dataHash,
        string calldata status,
        uint8 riskScore
    ) external onlyOwner {
        require(bytes(shipmentId).length > 0, "shipmentId required");
        require(bytes(dataHash).length > 0,   "dataHash required");
        require(riskScore <= 100,             "riskScore must be 0-100");

        if (!_handoffs[shipmentId].exists) {
            _shipmentIds.push(shipmentId);
        }

        _handoffs[shipmentId] = HandoffRecord({
            dataHash:   dataHash,
            status:     status,
            riskScore:  riskScore,
            timestamp:  block.timestamp,
            exists:     true,
            flagReason: ""
        });

        emit HandoffRecorded(shipmentId, status, riskScore, block.timestamp);
    }

    /**
     * @notice Flag an existing shipment with a reason.
     * @param shipmentId  UUID of the shipment
     * @param reason      Human-readable flag reason
     */
    function flagShipment(
        string calldata shipmentId,
        string calldata reason
    ) external onlyOwner {
        require(_handoffs[shipmentId].exists, "Handoff not found");

        _handoffs[shipmentId].status     = "FLAGGED";
        _handoffs[shipmentId].flagReason = reason;

        emit ShipmentFlagged(shipmentId, reason, block.timestamp);
    }

    // ── Read functions ───────────────────────────────────────────────────────

    /**
     * @notice Retrieve the handoff record for a shipment.
     */
    function getHandoff(string calldata shipmentId)
        external
        view
        returns (
            string memory dataHash,
            string memory status,
            uint8  riskScore,
            uint256 timestamp,
            string memory flagReason
        )
    {
        require(_handoffs[shipmentId].exists, "Handoff not found");
        HandoffRecord storage r = _handoffs[shipmentId];
        return (r.dataHash, r.status, r.riskScore, r.timestamp, r.flagReason);
    }

    /**
     * @notice Check whether a handoff record exists for a shipment.
     */
    function handoffExists(string calldata shipmentId)
        external view returns (bool)
    {
        return _handoffs[shipmentId].exists;
    }

    /**
     * @notice Total number of recorded shipments.
     */
    function totalHandoffs() external view returns (uint256) {
        return _shipmentIds.length;
    }

    /**
     * @notice Transfer ownership to a new address.
     */
    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "Zero address");
        owner = newOwner;
    }
}
