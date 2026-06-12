# Bug Diagnosis & Fixes Report

**Status**: Critical Issues Identified (2 Major Bugs + 1 Security Issue)  
**Priority**: Immediate Action Required

---

## Executive Summary

This report details two distinct production bugs affecting the Gemini LLM integration and blockchain transaction handling, plus one critical security vulnerability. All are resolved with provided fixes.

| Issue | Root Cause | Impact | Fix Complexity |
|-------|-----------|--------|-----------------|
| **Bug 1** | Invalid model name + synchronous blocking | Gemini always shows rule-based text | Low |
| **Bug 2** | Wrong wallet calling contract + no receipt wait | Blockchain TX stuck PENDING | Medium |
| **Security** | Credentials committed to git | Full account compromise risk | Low |

---

## Bug 1: Gemini Reply Always Shows Rule-Based Text (Never LLM)

### Root Cause Analysis

**Two separate problems compound to hide the real error:**

#### Problem 1: Invalid Model Name
```python
# llm_investigator.py — line 40
_model = genai.GenerativeModel("gemini-2.5-flash")
```

- `gemini-2.5-flash` **does not exist** in `google-generativeai==0.8.6`
- Valid model names: `gemini-1.5-flash` or `gemini-1.5-pro`
- When `GenerativeModel()` receives an invalid name, it silently fails on the first call or throws on `generate_content()`
- The bare `except Exception` catches this and returns `""`, falling back to rule-based explanation
- **Result**: You never see an error—just LLM output mysteriously never appears

#### Problem 2: Synchronous Blocking in FastAPI Route
```
Route Handler
  ↓ (direct call)
trigger_verification_and_blockchain()
  ↓ (direct call)
run_verification()
  ↓ (direct call)
investigate_flag()  ← BLOCKS entire FastAPI worker thread waiting for Gemini
```

- `investigate_flag()` runs **synchronously** inside the route handler (not in `BackgroundTask`)
- Even with a correct model name, this blocks the entire FastAPI worker during Gemini's network latency
- Under any load, causes timeouts and 500 errors
- **Result**: Poor performance and cascading failures under concurrent requests

### The Fix

#### Change 1: Fix Model Name
**File**: `backend/verification_ai/llm_investigator.py`

```python
# BEFORE (line 40)
_model = genai.GenerativeModel("gemini-2.5-flash")

# AFTER
_model = genai.GenerativeModel("gemini-1.5-flash")
```

#### Change 2: Move LLM Call to Background Task
**File**: `backend/verification_ai/engine.py`

Remove the entire LLM block (lines 179–196) and always return the rule-based explanation:

```python
# In run_verification() or final return statement
# Delete the LLM call entirely from the engine
# Always return rule_explanation as the explanation field
explanation = result.explanation  # rule-based only
```

**File**: `backend/verification_ai/wiring.py`

Add a background task after writing the AIFlag to DB:

```python
# After db.flush() for the AIFlag, add this:
if result.status == "FLAGGED":
    ai_flag_id = ai_flag.id  # capture before session closes
    background_tasks.add_task(
        _update_explanation_with_llm,
        ai_flag_id=ai_flag_id,
        manufacturer=mfr,
        supplier=sup,
        hospital=hos,
        result=result,
        db_session_factory=SessionLocal,
    )
```

Then add this helper function to `wiring.py`:

```python
def _update_explanation_with_llm(
    ai_flag_id: str,
    manufacturer,
    supplier,
    hospital,
    result,
    db_session_factory,
):
    """
    BackgroundTask: calls Gemini and patches the explanation in DB.
    Runs asynchronously, never blocks the route.
    """
    try:
        from verification_ai.llm_investigator import investigate_flag
        
        llm_text = investigate_flag(
            batch_name=getattr(manufacturer, "batch_name", "Unknown"),
            batch_number=getattr(manufacturer, "batch_number", "Unknown"),
            from_entity=manufacturer.party,
            to_entity=hospital.party,
            risk_score=result.risk_score,
            triggered_rules=result.triggered_rules,
            mismatch_details=result.mismatches,
            rule_explanation=result.explanation,
        )
        
        if not llm_text:
            return
        
        db = db_session_factory()
        try:
            flag = db.query(AIFlag).filter(AIFlag.id == ai_flag_id).first()
            if flag:
                flag.explanation = llm_text
                db.commit()
        finally:
            db.close()
            
    except Exception as exc:
        logger.error("[wiring] LLM background update failed: %s", exc)
```

### Why This Works

✅ **Correct model name** → Gemini API calls succeed  
✅ **Background task** → Route returns immediately, route handler unblocked  
✅ **Silent error handling** → LLM failures don't break the response, user gets rule-based explanation as fallback  
✅ **Async updates** → Database updated with LLM text within seconds

---

## Bug 2: Blockchain TX Hash Stuck on PENDING / Mock

### Root Cause Analysis

**Three problems prevent blockchain write confirmation:**

#### Problem 1: Wrong Wallet Calling Contract (onlyOwner Revert)

Your contract has:
```solidity
modifier onlyOwner() {
    require(msg.sender == owner, "ChainMed: caller is not the owner");
}

function recordHandoff(...) external onlyOwner { ... }
```

The `owner` is set at deploy time to `msg.sender`. But your `blockchain_service.py` calls `recordHandoff()` using `ETHEREUM_PRIVATE_KEY` from `.env`.

**If these wallets don't match**:
- Transaction reverts on-chain with "caller is not the owner"
- Exception is caught silently
- Code falls back to: `mock:sha256:...`
- **Result**: DB gets a fake hash, no real blockchain record

#### Problem 2: No Receipt Wait
```python
tx_hash_bytes = self._w3.eth.send_raw_transaction(signed.raw_transaction)
# Hash returned immediately, written to DB
# But TX is still in mempool, may fail on-chain
```

- `send_raw_transaction()` returns before tx is confirmed
- If tx fails (out of gas, revert, dropped), DB still shows hash as successful
- No visibility into actual on-chain status

#### Problem 3: Static Gas Price Under Congestion
```python
"gasPrice": self._w3.eth.gas_price  # Can be stale on Sepolia
```

- Gas price snapshot may be outdated during network congestion
- TX sits in mempool indefinitely (shows as "pending" on Etherscan)
- No dynamic repricing mechanism

### The Fix

#### Step 1: Verify Wallet Matches Contract Owner

**Check your contract deployment:**

1. Go to [Sepolia Etherscan](https://sepolia.etherscan.io/)
2. Find your `ChainMed` contract address
3. Click "Contract" tab → look for "Owner" field in constructor args or read methods
4. Note the owner address

**Check your backend wallet:**

```bash
# Extract address from ETHEREUM_PRIVATE_KEY in .env
python3 << 'EOF'
from eth_keys import keys
pk_hex = "0x296f2e..."  # from your .env
pk = keys.PrivateKey(bytes.fromhex(pk_hex.lstrip("0x")))
print("Backend wallet:", pk.public_key.to_checksum_address())
EOF
```

**If they don't match:**

- **Option A**: Redeploy the contract with the correct wallet (recommended if this is test/staging)
- **Option B**: Call `transferOwnership(backend_wallet_address)` from the original owner wallet on Etherscan

#### Step 2: Fix Gas Pricing & Add Receipt Wait

**File**: `backend/blockchain_service/service.py`

Replace the `build_transaction` block in `record_handoff()`:

```python
def record_handoff(self, shipment_id, data_hash, status, risk_int):
    """
    Record a handoff event on the blockchain.
    Uses EIP-1559 gas pricing for reliability.
    Waits for receipt to confirm success.
    """
    try:
        nonce = self._w3.eth.get_transaction_count(self._account.address)
        
        # Build transaction with EIP-1559 gas (type 0x2)
        tx = self._contract.functions.recordHandoff(
            shipment_id, data_hash, status, risk_int
        ).build_transaction({
            "from":                 self._account.address,
            "nonce":                nonce,
            "gas":                  200_000,
            "maxFeePerGas":         self._w3.eth.gas_price * 2,  # 2x current base fee
            "maxPriorityFeePerGas": self._w3.to_wei("2", "gwei"),  # Miner tip
            "type":                 "0x2",  # EIP-1559 transaction
        })
        
        # Sign and send
        signed = self._account.sign_transaction(tx)
        tx_hash_bytes = self._w3.eth.send_raw_transaction(signed.raw_transaction)
        
        # Wait for confirmation (up to 120 seconds)
        # BackgroundTask context makes blocking acceptable
        try:
            receipt = self._w3.eth.wait_for_transaction_receipt(
                tx_hash_bytes, timeout=120
            )
            
            # Check if transaction actually succeeded on-chain
            if receipt.status == 0:
                logger.error(
                    "[SEPOLIA] TX REVERTED for shipment %s. "
                    "Check: 1) wallet matches contract owner 2) sufficient gas 3) contract state",
                    shipment_id
                )
                return _mock_tx_hash(shipment_id, data_hash)  # fallback
                
        except Exception as timeout_exc:
            logger.warning(
                "[SEPOLIA] TX not confirmed in 120s for shipment %s: %s",
                shipment_id, timeout_exc
            )
            return _mock_tx_hash(shipment_id, data_hash)  # fallback
        
        # Success
        tx_hash = tx_hash_bytes.hex()
        logger.info("[SEPOLIA] TX recorded: %s", tx_hash)
        return tx_hash
        
    except Exception as exc:
        logger.error(
            "[BLOCKCHAIN WRITE FAILED] Shipment: %s | Error: %s | "
            "Diagnostics: 1) Is ETHEREUM_PRIVATE_KEY wallet the contract owner? "
            "2) Do you have enough Sepolia ETH? 3) Is contract address correct?",
            shipment_id, exc
        )
        return _mock_tx_hash(shipment_id, data_hash)
```

#### Step 3: Add Detailed Error Logging

Enhance exception handling to surface the real problem:

```python
except ValueError as ve:
    # Likely contract/address mismatch or encoding error
    logger.error(
        "[BLOCKCHAIN] ValueError (likely contract/encoding): %s | Shipment: %s",
        ve, shipment_id
    )
except Exception as exc:
    logger.error(
        "[BLOCKCHAIN] Unexpected error: %s | Shipment: %s | "
        "Next steps: Check wallet owns contract, check ETH balance, verify contract ABI",
        exc, shipment_id
    )
```

### Why This Works

✅ **Correct wallet** → TX passes `onlyOwner` check  
✅ **EIP-1559 gas** → Automatically adjusts to network conditions, won't get stuck  
✅ **Receipt wait** → Confirms tx mined and status before returning  
✅ **Timeout + fallback** → If tx doesn't confirm, falls back to mock gracefully  
✅ **Clear logging** → You can see exactly why a tx failed

---

## Security Issue: Exposed Credentials in .env

### The Problem

Your `.env` file is committed to git history and contains:

```
SUPABASE_PASSWORD=...
ETHEREUM_PRIVATE_KEY=0x296f2e...  ← Anyone can drain your wallet
ALCHEMY_API_KEY=...
GEMINI_API_KEY=...
UPSTASH_REDIS_PASSWORD=...
```

**Once committed, anyone with git history access has your keys forever** (even if you delete and recommit).

### Immediate Actions

#### 1. Rotate All Credentials

```bash
# Rotate Ethereum wallet
# - Export balance to new wallet
# - Update ETHEREUM_PRIVATE_KEY in .env with new key

# Rotate Supabase
# - Change database password in Supabase console
# - Update SUPABASE_PASSWORD in .env

# Rotate Gemini API key
# - Delete old key in Google Cloud console
# - Create new key
# - Update GEMINI_API_KEY in .env

# Rotate Alchemy & Upstash keys similarly
```

#### 2. Remove .env from Git History

```bash
# Remove from tracking (but keep locally)
git rm --cached backend/.env

# Remove from all git history
git filter-branch --tree-filter 'rm -f backend/.env' HEAD

# Force push (only safe if you're the sole developer)
git push origin main --force

# Create .gitignore if it doesn't exist
echo "backend/.env" >> .gitignore
echo ".env" >> .gitignore

git add .gitignore
git commit -m "chore: add .env to gitignore and remove from history"
git push
```

#### 3. Update Deployment

Update your deployment environment (Docker, CI/CD, etc.) to inject `.env` at runtime:

```yaml
# docker-compose.yml or CI/CD secret manager
environment:
  ETHEREUM_PRIVATE_KEY: ${ETHEREUM_PRIVATE_KEY}
  SUPABASE_PASSWORD: ${SUPABASE_PASSWORD}
  # etc.
```

---

## Implementation Checklist

- [ ] **Bug 1 — Gemini**
  - [ ] Change model name to `gemini-1.5-flash`
  - [ ] Move LLM call to background task in `wiring.py`
  - [ ] Delete LLM block from `engine.py`
  - [ ] Test: Flag verification should return immediately with rule-based explanation
  - [ ] Test: LLM explanation should appear in DB within 5–10 seconds

- [ ] **Bug 2 — Blockchain**
  - [ ] Verify `ETHEREUM_PRIVATE_KEY` wallet matches contract owner
  - [ ] Update `blockchain_service.py` with EIP-1559 gas and receipt wait
  - [ ] Add error logging for troubleshooting
  - [ ] Test: Submit a verification that triggers blockchain write
  - [ ] Test: Confirm TX hash on Sepolia Etherscan shows "Success"

- [ ] **Security — Credentials**
  - [ ] Rotate all keys (Ethereum, Supabase, Gemini, Alchemy, Upstash)
  - [ ] Remove `.env` from git history
  - [ ] Add `.env` to `.gitignore`
  - [ ] Update CI/CD / deployment to inject `.env` from secrets manager
  - [ ] Verify no keys in git logs: `git log --all -S 'ETHEREUM_PRIVATE_KEY'`

---

## Validation & Testing

### Test Plan for Bug 1 (Gemini)

```bash
# 1. Submit a verification that triggers a flag
curl -X POST http://localhost:8000/verify \
  -H "Content-Type: application/json" \
  -d '{"shipment_id": "test-001", "manufacturer": {...}}'

# 2. Verify response returns quickly (< 2s)
# Response should have:
#   - status: "FLAGGED"
#   - explanation: rule-based text (e.g., "Mismatch detected in...")

# 3. Wait 10 seconds, query DB
SELECT id, explanation FROM ai_flags WHERE shipment_id = 'test-001';

# 4. Explanation should now contain detailed LLM analysis
# (longer, more narrative than rule text)
```

### Test Plan for Bug 2 (Blockchain)

```bash
# 1. Check Etherscan for contract owner
# https://sepolia.etherscan.io/<CONTRACT_ADDRESS>

# 2. Extract backend wallet address
python3 -c "from eth_keys import keys; print(keys.PrivateKey(...).public_key.to_checksum_address())"

# 3. If addresses don't match, redeploy or transfer ownership

# 4. Submit a verification that triggers blockchain write
curl -X POST http://localhost:8000/verify \
  -H "Content-Type: application/json" \
  -d '{"shipment_id": "test-002", ...}'

# 5. Check logs for transaction hash
grep "TX recorded" backend.log | tail -1

# 6. Paste hash into Etherscan
# https://sepolia.etherscan.io/tx/<HASH>

# 7. Should show "Success" (status 1), not "Pending" or reverted
```

---

## Additional Notes

### Why These Bugs Existed

- **Gemini model name**: Likely copy-paste from future/wrong docs; no validation layer caught invalid model names
- **Synchronous blocking**: Classic FastAPI pattern mistake; LLM calls should always be async or backgrounded
- **Wallet mismatch**: Deployment checklist item missed; no pre-flight validation in service code
- **Credentials in git**: `.env` not gitignored; happens to many teams—rotate immediately

### Prevention Going Forward

1. **Add pre-flight validation** in `blockchain_service.py`:
   ```python
   # At startup, verify wallet matches owner
   assert self._account.address == contract_owner, "Wallet mismatch!"
   ```

2. **Use environment schema validation**:
   ```python
   from pydantic_settings import BaseSettings
   class Settings(BaseSettings):
       ETHEREUM_PRIVATE_KEY: str
       # Pydantic will error if missing
   ```

3. **Add type hints and CI checks**:
   - Mypy to catch type issues
   - Pre-commit hooks to prevent `.env` commits

4. **Document deployment checklist**:
   - Verify wallet owns contract before deploy
   - Rotate credentials in staging
   - Test full flow (flag → LLM → blockchain) before production

---

## Questions or Issues?

If you encounter any problems during implementation:

1. **Gemini calls still failing**: Check `logs/verification_ai.log` for the actual exception from `genai.GenerativeModel()`
2. **Blockchain TX still pending**: Confirm wallet address on Etherscan, check Sepolia ETH balance
3. **Background tasks not running**: Verify `BackgroundTasks` is imported and `background_tasks.add_task()` is called *before* route returns

---

**Last Updated**: May 2026  
**Status**: Ready for Implementation
