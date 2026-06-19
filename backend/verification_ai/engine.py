"""
Hybrid AI engine — Layer 1 (rule-based) + Layer 2 (Gemini LLM investigator).

Risk Score Formula (Research Paper — Addition 10):
─────────────────────────────────────────────────
    R = min(Σ wᵢ · fᵢ,  100)

where fᵢ ∈ {0, 1} are binary fraud indicators and wᵢ are weights:

  f1  qty deviation > 15%           w1 = 30   (QUANTITY_DEVIATION_MFG_SUPPLIER)
  f2  qty deviation > 30% (additive)w2 = 20   (QUANTITY_DEVIATION_SEVERE)
  f3  expiry date mismatch          w3 = 40   (EXPIRY_MISMATCH_*)
  f4  temperature deviation > 5°C   w4 = 15   (TEMP_DEVIATION_*)
  f5  unverified digital signature  w5 = 20   (UNVERIFIED_SIGNATURE — future)

Decision thresholds:
  R ≥ 30  →  FLAGGED
  R < 30  →  VERIFIED

Source: Adapted from multi-criteria supply chain risk models in:
  · Kamble et al. (2019). Sustainable Industry 4.0 framework for supply chain.
  · Sylim et al. (2018). Blockchain Technology for Detecting Falsified and Substandard Drugs.
  · Mackey & Nayyar (2017). A review of existing and emerging digital technologies to combat counterfeit drugs.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
import json
import logging

logger = logging.getLogger(__name__)

QUANTITY_DEVIATION_THRESHOLD = 0.15
TEMP_TOLERANCE_CELSIUS = 5.0
FLAG_RISK_THRESHOLD = 30


@dataclass
class PartyReport:
    party: str
    quantity: Optional[int] = None
    expiry: Optional[datetime] = None
    temp: Optional[float] = None
    batch_name: str = "Unknown"
    batch_number: str = "Unknown"
    signature_valid: bool = True


@dataclass
class VerificationResult:
    status: str
    risk_score: float
    triggered_rules: List[str] = field(default_factory=list)
    mismatches: List[dict] = field(default_factory=list)
    explanation: str = ""
    hospital_shipment_id: Optional[str] = None

    def triggered_rules_json(self) -> str:
        return json.dumps(self.triggered_rules)

    def mismatch_details_json(self) -> str:
        return json.dumps(self.mismatches)


def _pct_deviation(expected: int, reported: int) -> float:
    if expected == 0:
        return 0.0
    return abs(reported - expected) / expected


def _same_expiry(a: datetime, b: datetime) -> bool:
    return a.date() == b.date()


def run_verification(
    manufacturer: PartyReport,
    supplier: Optional[PartyReport],
    hospital: Optional[PartyReport],
    hospital_shipment_id: Optional[str],
    supplier_dispatched: Optional[int] = None,
) -> VerificationResult:
    if supplier is None:
        return VerificationResult(
            status="PENDING",
            risk_score=0,
            explanation="Waiting for independent submissions from: supplier.",
            hospital_shipment_id=hospital_shipment_id,
        )

    rules: List[str] = []
    mismatches: List[dict] = []
    risk = 0.0

    # Manufacturer vs supplier quantity
    mfg_qty = manufacturer.quantity or 0
    sup_qty = supplier.quantity or 0
    sup_dev = _pct_deviation(mfg_qty, sup_qty)
    if sup_dev > QUANTITY_DEVIATION_THRESHOLD:
        rules.append("QUANTITY_DEVIATION_MFG_SUPPLIER")
        mismatches.append({
            "field": "quantity",
            "manufacturer": mfg_qty,
            "supplier": sup_qty,
            "deviation_pct": round(sup_dev * 100, 1),
        })
        risk += 30
    elif sup_dev > 0.0:
        rules.append("LOW_QUANTITY_DEVIATION_MFG_SUPPLIER")
        mismatches.append({
            "field": "quantity",
            "manufacturer": mfg_qty,
            "supplier": sup_qty,
            "deviation_pct": round(sup_dev * 100, 1),
        })
        risk += 10

    # Supplier vs hospital quantity
    if hospital is not None:
        hos_qty = hospital.quantity or 0
        sup_expected_for_hospital = supplier_dispatched if supplier_dispatched is not None else sup_qty
        hos_dev = _pct_deviation(sup_expected_for_hospital, hos_qty)
        if hos_dev > QUANTITY_DEVIATION_THRESHOLD:
            rules.append("QUANTITY_DEVIATION_SUPPLIER_HOSPITAL")
            mismatches.append({
                "field": "quantity",
                "supplier": sup_expected_for_hospital,
                "hospital": hos_qty,
                "deviation_pct": round(hos_dev * 100, 1),
            })
            risk += 30
        elif hos_dev > 0.0:
            rules.append("LOW_QUANTITY_DEVIATION_SUPPLIER_HOSPITAL")
            mismatches.append({
                "field": "quantity",
                "supplier": sup_expected_for_hospital,
                "hospital": hos_qty,
                "deviation_pct": round(hos_dev * 100, 1),
            })
            risk += 10

    # Expiry chain
    mfg_exp = manufacturer.expiry
    sup_exp = supplier.expiry
    hos_exp = hospital.expiry if hospital else None
    if mfg_exp and sup_exp and not _same_expiry(mfg_exp, sup_exp):
        rules.append("EXPIRY_MISMATCH_MFG_SUPPLIER")
        mismatches.append({
            "field": "expiry",
            "manufacturer": mfg_exp.isoformat(),
            "supplier": sup_exp.isoformat(),
        })
        risk += 40
    if sup_exp and hos_exp and not _same_expiry(sup_exp, hos_exp):
        rules.append("EXPIRY_MISMATCH_SUPPLIER_HOSPITAL")
        mismatches.append({
            "field": "expiry",
            "supplier": sup_exp.isoformat(),
            "hospital": hos_exp.isoformat(),
        })
        risk += 40

    # Temperature declarations
    mfg_temp = manufacturer.temp
    sup_temp = supplier.temp
    hos_temp = hospital.temp if hospital else None
    if mfg_temp is not None and sup_temp is not None:
        diff = abs(mfg_temp - sup_temp)
        if diff > TEMP_TOLERANCE_CELSIUS:
            rules.append("TEMP_DEVIATION_MFG_SUPPLIER")
            mismatches.append({
                "field": "temperature",
                "manufacturer": mfg_temp,
                "supplier": sup_temp,
                "difference_c": round(diff, 1),
            })
            risk += 15
    if sup_temp is not None and hos_temp is not None:
        diff = abs(sup_temp - hos_temp)
        if diff > TEMP_TOLERANCE_CELSIUS:
            rules.append("TEMP_DEVIATION_SUPPLIER_HOSPITAL")
            mismatches.append({
                "field": "temperature",
                "supplier": sup_temp,
                "hospital": hos_temp,
                "difference_c": round(diff, 1),
            })
            risk += 15

    # Unverified Signatures (f5)
    for party, report in [("manufacturer", manufacturer), ("supplier", supplier), ("hospital", hospital)]:
        if report and not report.signature_valid:
            rules.append(f"UNVERIFIED_SIGNATURE_{party.upper()}")
            mismatches.append({
                "field": "signature",
                "party": party,
                "status": "invalid_or_missing",
            })
            risk += 20

    risk = min(100.0, risk)
    status = "FLAGGED" if risk >= FLAG_RISK_THRESHOLD else "VERIFIED"

    if status == "FLAGGED":
        rule_explanation = _build_flagged_explanation(manufacturer, supplier, hospital, mismatches, risk)

        explanation = rule_explanation

    else:
        if hospital is not None:
            explanation = (
                f"All three parties aligned within thresholds. "
                f"Manufacturer {mfg_qty} units -> Supplier {sup_qty} -> Hospital {hos_qty}. "
                f"Risk score {risk:.0f}/100 (safe)."
            )
        else:
            explanation = (
                f"Two parties aligned within thresholds. "
                f"Manufacturer {mfg_qty} units -> Supplier {sup_qty}. "
                f"Risk score {risk:.0f}/100 (safe)."
            )

    return VerificationResult(
        status=status,
        risk_score=risk,
        triggered_rules=rules,
        mismatches=mismatches,
        explanation=explanation,
        hospital_shipment_id=hospital_shipment_id,
    )


def _build_flagged_explanation(
    manufacturer: PartyReport,
    supplier: PartyReport,
    hospital: Optional[PartyReport],
    mismatches: List[dict],
    risk: float,
) -> str:
    lines = [
        f"Cross-match flagged. Risk score {risk:.0f}/100.",
    ]
    
    # Customise the output if a quantity mismatch was the culprit
    qty_mismatch = next((m for m in mismatches if m.get("field") == "quantity"), None)
    if qty_mismatch:
        if "manufacturer" in qty_mismatch:
            lines.append(f"Manufacturer dispatched: {qty_mismatch['manufacturer']} units")
            lines.append(f"Supplier received: {qty_mismatch['supplier']} units")
        else:
            lines.append(f"Supplier dispatched: {qty_mismatch['supplier']} units")
            lines.append(f"Hospital received: {qty_mismatch['hospital']} units")
    else:
        lines.append(f"Manufacturer qty: {manufacturer.quantity} units")
        lines.append(f"Supplier qty:     {supplier.quantity} units")
        if hospital:
            lines.append(f"Hospital qty:     {hospital.quantity} units")
    for m in mismatches:
        if m.get("field") == "quantity" and "deviation_pct" in m:
            lines.append(
                f"Quantity deviation {m['deviation_pct']}% exceeds "
                f"{QUANTITY_DEVIATION_THRESHOLD * 100:.0f}% threshold."
            )
        elif m.get("field") == "expiry":
            lines.append("Expiry date mismatch detected between parties.")
        elif m.get("field") == "temperature":
            lines.append(
                f"Storage temperature difference {m.get('difference_c')}°C "
                f"exceeds {TEMP_TOLERANCE_CELSIUS}°C tolerance."
            )
    lines.append("Possible diversion or tampering between handoff checkpoints.")
    return " ".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# ADDITION 10 — compute_risk_score()
# Pure function. No DB access. Matches the research paper formula:
#     R = min(Σ wᵢ · fᵢ, 100)
# Used by:  benchmarks/runner.py, tests/test_verification_ai.py
# ─────────────────────────────────────────────────────────────────────────────

def compute_risk_score(
    quantities: List[int],
    expiries: List[str],
    batch_numbers: List[str],
    medicine_names: List[str],
    temps: List[float],
) -> dict:
    """
    Pure function. No DB access. Matches the research paper formula exactly.

    Formula:  R = min(Σ wᵢ · fᵢ,  100)

    Weights:
      f1 (qty deviation > 15%):      w = 30
      f2 (qty deviation > 30% add.): w = 20
      f3 (expiry mismatch):          w = 40
      f4 (batch number mismatch):    w = 30
      f5 (medicine name mismatch):   w = 30
      f6 (temperature > 30°C):       w = 15

    Args:
        quantities:      Reported quantities from each party (at least 2)
        expiries:        Expiry dates as ISO-8601 strings (YYYY-MM-DD)
        batch_numbers:   Batch numbers reported by each party
        medicine_names:  Medicine names reported by each party
        temps:           Reported storage temperatures in Celsius

    Returns:
        dict with keys: status, risk_score, triggered_rules, mismatch_fields
    """
    if len(quantities) < 2:
        return {
            "status": "PENDING",
            "risk_score": 0.0,
            "triggered_rules": [],
            "mismatch_fields": {},
        }

    risk = 0.0
    triggered_rules: List[str] = []
    mismatch_fields: dict = {}

    # f1, f2 — Quantity deviation
    q_max = max(quantities)
    q_min = min(quantities)
    delta_q = ((q_max - q_min) / q_min * 100) if q_min > 0 else 0.0
    if delta_q > 30:
        risk += 30  # f1
        risk += 20  # f2 additive for severe deviation
        triggered_rules.append("quantity_deviation_gt_15pct")
        triggered_rules.append("quantity_deviation_gt_30pct")
        mismatch_fields["quantity"] = {
            "values": quantities,
            "deviation_pct": round(delta_q, 2),
        }
    elif delta_q > 15:
        risk += 30  # f1 only
        triggered_rules.append("quantity_deviation_gt_15pct")
        mismatch_fields["quantity"] = {
            "values": quantities,
            "deviation_pct": round(delta_q, 2),
        }

    # f3 — Expiry date mismatch
    unique_expiries = set(expiries)
    if len(unique_expiries) > 1:
        risk += 40
        triggered_rules.append("expiry_date_mismatch")
        mismatch_fields["expiry"] = {"values": list(unique_expiries)}

    # f4 — Batch number mismatch
    if len(set(batch_numbers)) > 1:
        risk += 30
        triggered_rules.append("batch_number_mismatch")
        mismatch_fields["batch_number"] = {"values": list(set(batch_numbers))}

    # f5 — Medicine name mismatch
    if len(set(medicine_names)) > 1:
        risk += 30
        triggered_rules.append("medicine_name_mismatch")
        mismatch_fields["medicine_name"] = {"values": list(set(medicine_names))}

    # f6 — Temperature breach (any party reports > 30°C cold chain breach)
    if any(t > 30 for t in temps):
        risk += 15
        triggered_rules.append("temperature_breach")
        mismatch_fields["temperature"] = {"max_reported": max(temps)}

    risk = min(risk, 100.0)

    # Decision thresholds (matches run_verification FLAG_RISK_THRESHOLD = 30)
    if risk >= 30:
        status = "FLAGGED"
    else:
        status = "VERIFIED"

    return {
        "status": status,
        "risk_score": risk,
        "triggered_rules": triggered_rules,
        "mismatch_fields": mismatch_fields,
    }
