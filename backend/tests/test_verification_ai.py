"""
ChainMed Verification AI — Test Suite
==========================================
Addition 6 from updateprompt.md

Run with:
    cd backend
    pytest tests/ -v

These tests validate the compute_risk_score() pure function which implements
the research paper formula: R = min(Σ wᵢ · fᵢ, 100)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from verification_ai.engine import compute_risk_score


def test_clean_shipment_is_verified():
    """All parties report identical clean data → VERIFIED, risk < 30."""
    result = compute_risk_score(
        quantities=[1000, 1000, 1000],
        expiries=["2027-01-01", "2027-01-01", "2027-01-01"],
        batch_numbers=["B001", "B001", "B001"],
        medicine_names=["Paracetamol", "Paracetamol", "Paracetamol"],
        temps=[22.0, 23.0, 22.5],
    )
    assert result["status"] == "VERIFIED"
    assert result["risk_score"] < 30
    assert result["triggered_rules"] == []


def test_quantity_deviation_over_15pct_flags():
    """18% deviation exceeds the 15% threshold → FLAGGED, risk ≥ 30."""
    result = compute_risk_score(
        quantities=[10000, 8200, 8200],   # 18% deviation
        expiries=["2027-01-01", "2027-01-01", "2027-01-01"],
        batch_numbers=["B001", "B001", "B001"],
        medicine_names=["Amoxicillin", "Amoxicillin", "Amoxicillin"],
        temps=[22.0, 22.0, 22.0],
    )
    assert result["status"] == "FLAGGED"
    assert result["risk_score"] >= 30
    assert "quantity_deviation_gt_15pct" in result["triggered_rules"]


def test_quantity_deviation_over_30pct_adds_severe_rule():
    """50% deviation adds both gt_15pct and gt_30pct rules (additive weight)."""
    result = compute_risk_score(
        quantities=[10000, 5000, 5000],   # 50% deviation
        expiries=["2027-01-01", "2027-01-01", "2027-01-01"],
        batch_numbers=["B001", "B001", "B001"],
        medicine_names=["Amoxicillin", "Amoxicillin", "Amoxicillin"],
        temps=[22.0, 22.0, 22.0],
    )
    assert "quantity_deviation_gt_15pct" in result["triggered_rules"]
    assert "quantity_deviation_gt_30pct" in result["triggered_rules"]
    assert result["risk_score"] >= 50  # 30 + 20 = 50


def test_expiry_mismatch_raises_risk():
    """Mismatched expiry dates → expiry_date_mismatch rule, risk ≥ 40."""
    result = compute_risk_score(
        quantities=[1000, 1000, 1000],
        expiries=["2027-01-01", "2026-06-01", "2027-01-01"],   # mismatch
        batch_numbers=["B001", "B001", "B001"],
        medicine_names=["Paracetamol", "Paracetamol", "Paracetamol"],
        temps=[22.0, 22.0, 22.0],
    )
    assert result["risk_score"] >= 40
    assert "expiry_date_mismatch" in result["triggered_rules"]


def test_temperature_breach_adds_rule():
    """Any party reporting >30°C triggers cold-chain breach rule."""
    result = compute_risk_score(
        quantities=[1000, 1000, 1000],
        expiries=["2027-01-01", "2027-01-01", "2027-01-01"],
        batch_numbers=["B001", "B001", "B001"],
        medicine_names=["Paracetamol", "Paracetamol", "Paracetamol"],
        temps=[22.0, 35.0, 22.0],   # middle party reports 35°C breach
    )
    assert "temperature_breach" in result["triggered_rules"]
    assert result["risk_score"] >= 15


def test_risk_score_never_exceeds_100():
    """Worst-case scenario with all rules triggered → risk capped at 100."""
    result = compute_risk_score(
        quantities=[10000, 5000, 5000],     # >30% deviation
        expiries=["2027-01-01", "2026-01-01", "2025-01-01"],   # all different
        batch_numbers=["B001", "B002", "B003"],   # all different
        medicine_names=["DrugA", "DrugB", "DrugC"],   # all different
        temps=[22.0, 38.0, 22.0],   # breach
    )
    assert result["risk_score"] <= 100


def test_pending_when_less_than_two_parties():
    """Only 1 party submitted — cannot cross-match yet → PENDING."""
    result = compute_risk_score(
        quantities=[1000],
        expiries=["2027-01-01"],
        batch_numbers=["B001"],
        medicine_names=["Paracetamol"],
        temps=[22.0],
    )
    assert result["status"] == "PENDING"
    assert result["risk_score"] == 0.0


def test_batch_number_mismatch_flags():
    """Different batch numbers reported across parties → FLAGGED."""
    result = compute_risk_score(
        quantities=[1000, 1000, 1000],
        expiries=["2027-01-01", "2027-01-01", "2027-01-01"],
        batch_numbers=["BATCH-A", "BATCH-A", "BATCH-B"],   # mismatch
        medicine_names=["Paracetamol", "Paracetamol", "Paracetamol"],
        temps=[22.0, 22.0, 22.0],
    )
    assert "batch_number_mismatch" in result["triggered_rules"]
    assert result["status"] == "FLAGGED"


def test_minor_quantity_deviation_under_15pct_passes():
    """3.3% deviation is below the 15% threshold → should remain VERIFIED."""
    result = compute_risk_score(
        quantities=[3000, 2900, 2900],   # 3.33% deviation
        expiries=["2027-01-01", "2027-01-01", "2027-01-01"],
        batch_numbers=["B001", "B001", "B001"],
        medicine_names=["Paracetamol", "Paracetamol", "Paracetamol"],
        temps=[22.0, 22.0, 22.0],
    )
    assert "quantity_deviation_gt_15pct" not in result["triggered_rules"]
    assert result["status"] == "VERIFIED"
