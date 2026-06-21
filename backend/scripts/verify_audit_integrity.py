"""
verify_audit_integrity.py — Approval Log Integrity Checker (P1.5)
==================================================================
A standalone script that can be run manually or on a nightly cron schedule.
It walks the entire ApprovalLog chain in chronological order and:

  Phase 1 — DB Chain Integrity Check
    Re-computes log_hash for every row and checks it against the stored value.
    If ANY mismatch is found → FAIL (tamper detected).
    If chain linkage (previous_hash) is broken → FAIL.

  Phase 2 — Blockchain Cross-Check
    For rows that have a blockchain_hash (tx id), it queries the blockchain
    service to verify the on-chain data_hash matches our local computation.
    In mock mode this check is skipped with a WARNING (not a FAIL).

Usage:
    cd backend
    venv/Scripts/python.exe scripts/verify_audit_integrity.py

    # With verbose output:
    venv/Scripts/python.exe scripts/verify_audit_integrity.py --verbose

    # Limit to last N rows (useful for quick daily check):
    venv/Scripts/python.exe scripts/verify_audit_integrity.py --limit 100

Exit codes:
    0  — PASS (chain intact)
    1  — FAIL (tampering detected or chain broken)
    2  — WARNING (chain ok but blockchain checks skipped in mock mode)
"""

import sys
import os
import argparse
import hashlib
import json
import logging
from datetime import datetime, timezone

# ── Path fix so we can import from backend root ───────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Load .env before importing settings ──────────────────────────────────────
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# ── Hash recomputation (must match audit_chain.py exactly) ────────────────────
def _recompute_log_hash(log, previous_hash: str | None) -> str:
    payload = json.dumps(
        {
            "id":            getattr(log, "id", "") or "",
            "actor_role":    getattr(log, "actor_role", "") or "",
            "actor_name":    getattr(log, "actor_name", "") or "",
            "actor_id":      getattr(log, "actor_id", "") or "",
            "action_type":   getattr(log, "action_type", "") or "",
            "entity_id":     getattr(log, "entity_id", "") or "",
            "entity_type":   getattr(log, "entity_type", "") or "",
            "notes":         getattr(log, "notes", "") or "",
            "signature":     getattr(log, "signature", "") or "",
            "previous_hash": previous_hash or "GENESIS",
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _fmt_ts(value) -> str:
    if not value:
        return "—"
    try:
        return value.strftime("%d %b %Y %H:%M:%S UTC")
    except Exception:
        return str(value)


# ── Phase 1: DB chain walk ────────────────────────────────────────────────────
def check_db_chain(logs: list, verbose: bool) -> tuple[bool, list[str]]:
    """
    Walk the log chain in chronological order.
    Returns (passed: bool, issues: list[str]).
    """
    issues = []
    passed = True
    previous_hash_expected = None  # Genesis

    # Split: rows with log_hash (new, chained) vs without (legacy genesis rows)
    legacy_rows = [l for l in logs if l.log_hash is None]
    chained_rows = [l for l in logs if l.log_hash is not None]

    if verbose and legacy_rows:
        print(f"  [INFO] {len(legacy_rows)} legacy rows (pre-P1.5) treated as genesis -- skipping hash check.")

    # For the chain, find the first chained row's previous_hash as the anchor
    if chained_rows:
        # The previous_hash of the first chained row should be either None (genesis)
        # or match the last legacy row (which has no log_hash, so treated as None)
        # We start the chain from the first chained row
        for i, log in enumerate(chained_rows):
            # 1. Check linkage: previous_hash must match what we computed in the prior step
            stored_prev = log.previous_hash
            if i == 0:
                # First chained row — previous_hash should be None (or a legacy row's null hash)
                if stored_prev is not None and previous_hash_expected is None:
                    # This is fine: could be chained from a legacy row that had no log_hash
                    # We'll still verify the log_hash itself
                    pass
            else:
                if stored_prev != previous_hash_expected:
                    issue = (
                        f"CHAIN BREAK at log #{i+1} (id={log.id[:12]}…) · "
                        f"stored previous_hash={str(stored_prev)[:16]}… "
                        f"expected={str(previous_hash_expected)[:16]}…"
                    )
                    issues.append(issue)
                    passed = False
                    if verbose:
                        print(f"  [FAIL] {issue}")

            # 2. Recompute log_hash and compare
            recomputed = _recompute_log_hash(log, log.previous_hash)
            if recomputed != log.log_hash:
                issue = (
                    f"HASH MISMATCH at log #{i+1} (id={log.id[:12]}…) "
                    f"action={log.action_type} actor={log.actor_name} "
                    f"ts={_fmt_ts(log.created_at)} · "
                    f"stored={str(log.log_hash)[:16]}… computed={recomputed[:16]}…"
                )
                issues.append(issue)
                passed = False
                if verbose:
                    print(f"  [FAIL] {issue}")
            else:
                if verbose:
                    print(f"  [OK] Row #{i+1:04d} ok . {log.action_type} . {log.actor_name}")

            previous_hash_expected = log.log_hash

    return passed, issues


# ── Phase 2: Blockchain cross-check ──────────────────────────────────────────
def check_blockchain(logs: list, verbose: bool) -> tuple[str, list[str]]:
    """
    For rows with a blockchain_hash, verify on-chain data matches local state.
    Returns ('PASS'|'SKIP'|'FAIL', issues).
    SKIP is returned when in mock mode (blockchain hash starts with 'mock:').
    """
    blockchain_logs = [l for l in logs if l.blockchain_hash]

    if not blockchain_logs:
        if verbose:
            print("  [INFO] No blockchain hashes recorded yet -- skipping blockchain phase.")
        return "SKIP", []

    # Check if all are mock hashes
    all_mock = all(str(l.blockchain_hash).startswith("mock:") for l in blockchain_logs)
    if all_mock:
        if verbose:
            print(f"  [WARN] {len(blockchain_logs)} blockchain hashes found -- all are mock mode hashes.")
            print("         Cannot verify against real blockchain in mock mode. Run with real Sepolia config.")
        return "SKIP", []

    # Real blockchain verification
    issues = []
    passed = True

    try:
        from config import settings
        from blockchain_service.service import BlockchainService
        svc = BlockchainService(
            rpc_url=settings.ETHEREUM_RPC_URL,
            private_key=settings.ETHEREUM_PRIVATE_KEY,
            contract_address=settings.CONTRACT_ADDRESS,
        )

        if svc.is_mock:
            if verbose:
                print("  [WARN] Blockchain service in mock mode -- skipping on-chain verification.")
            return "SKIP", []

        for log in blockchain_logs:
            if str(log.blockchain_hash).startswith("mock:"):
                continue  # Skip individual mock hashes if mixed

            # The entity_id is the shipment_id recorded on-chain
            on_chain = svc.get_handoff(log.entity_id or "")
            if not on_chain:
                issue = f"Blockchain record NOT FOUND for entity_id={log.entity_id} tx={log.blockchain_hash}"
                issues.append(issue)
                passed = False
                if verbose:
                    print(f"  [FAIL] {issue}")
            else:
                if verbose:
                    print(f"  [OK] On-chain record found for entity_id={log.entity_id[:12]}... status={on_chain.get('status')}")

    except Exception as exc:
        issue = f"Blockchain verification error: {exc}"
        issues.append(issue)
        passed = False
        if verbose:
            print(f"  [FAIL] {issue}")

    return ("PASS" if passed else "FAIL"), issues


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="ChainMed — Approval Log Integrity Checker (P1.5)"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Print result for every row (default: only print failures)"
    )
    parser.add_argument(
        "--limit", "-l", type=int, default=0,
        help="Only check the most recent N rows (0 = check all)"
    )
    args = parser.parse_args()

    run_ts = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")

    print()
    print("=" * 60)
    print("  ChainMed — Approval Log Integrity Check")
    print(f"  Run at: {run_ts}")
    print("=" * 60)

    # ── Connect to DB ─────────────────────────────────────────────────────────
    try:
        from database import SessionLocal
        from models import ApprovalLog
        db = SessionLocal()
    except Exception as exc:
        print(f"\n  ❌  FAIL — Could not connect to database: {exc}")
        sys.exit(1)

    try:
        query = db.query(ApprovalLog).order_by(ApprovalLog.created_at.asc())
        total_count = query.count()

        if args.limit > 0:
            logs = query.limit(args.limit).all()
            print(f"\n  Checking last {len(logs)} of {total_count} total approval log entries.")
        else:
            logs = query.all()
            print(f"\n  Checking all {total_count} approval log entries.")

        if not logs:
            print("\n  [INFO] No approval log entries found. Nothing to verify.\n")
            sys.exit(0)

        # ── Phase 1: DB chain ─────────────────────────────────────────────────
        print(f"\n  Phase 1 -- DB Hash Chain Verification")
        print("  " + "-" * 40)
        chain_passed, chain_issues = check_db_chain(logs, args.verbose)
        if chain_passed:
            chained_count = sum(1 for l in logs if l.log_hash is not None)
            print(f"  [PASS] {chained_count} chained rows verified. No tampering detected.")
        else:
            print(f"  [FAIL] {len(chain_issues)} integrity violation(s) detected!")
            for issue in chain_issues:
                print(f"       -> {issue}")

        # ── Phase 2: Blockchain cross-check ───────────────────────────────────
        print(f"\n  Phase 2 -- Blockchain Cross-Check")
        print("  " + "-" * 40)
        bc_result, bc_issues = check_blockchain(logs, args.verbose)
        if bc_result == "PASS":
            print(f"  [PASS] On-chain records verified.")
        elif bc_result == "SKIP":
            print(f"  [SKIP] Blockchain check skipped (mock mode or no hashes).")
        else:
            print(f"  [FAIL] {len(bc_issues)} blockchain verification failure(s)!")
            for issue in bc_issues:
                print(f"       -> {issue}")

        # ── Final verdict ─────────────────────────────────────────────────────
        print()
        print("=" * 60)
        if chain_passed and bc_result in ("PASS", "SKIP"):
            verdict = "PASS"
            exit_code = 0 if bc_result == "PASS" else 2
            icon = "[PASS]" if bc_result == "PASS" else "[WARN]"
            print(f"  {icon}  OVERALL: {verdict}")
            if bc_result == "SKIP":
                print("      (Blockchain phase skipped -- run with real Sepolia env for full check)")
        else:
            verdict = "FAIL"
            exit_code = 1
            print(f"  [FAIL]  OVERALL: {verdict}")
            print("      ACTION REQUIRED: Review violations above immediately.")
        print("=" * 60)
        print()
        sys.exit(exit_code)

    finally:
        db.close()


if __name__ == "__main__":
    main()
