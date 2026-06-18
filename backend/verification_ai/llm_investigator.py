"""
LLM Investigator — Layer 2 of the Hybrid AI system.

When the rule-based engine (Layer 1) flags a shipment,
this module calls Google Gemini Flash to generate a plain-English
investigation report explaining the root cause and recommending action.

If the API key is missing or the call fails, it degrades gracefully
and returns an empty string so the rule engine explanation is used instead.
"""
import os
import logging

logger = logging.getLogger(__name__)

# Lazily initialised so the app still boots if the key is missing
_model = None


def _get_model():
    global _model
    if _model is not None:
        return _model

    try:
        from config import settings  # noqa: PLC0415
        api_key = settings.GEMINI_API_KEY.strip()
    except Exception:
        api_key = ""

    if not api_key:
        logger.warning(
            "[LLM Investigator] GEMINI_API_KEY not set — LLM explanations disabled."
        )
        return None

    try:
        import google.generativeai as genai  # noqa: WPS433

        genai.configure(api_key=api_key)
        _model = genai.GenerativeModel("gemini-flash")
        logger.info("[LLM Investigator] Gemini Flash (auto-updating alias) model loaded ✓")
        return _model
    except Exception as exc:  # noqa: BLE001
        logger.error("[LLM Investigator] Failed to load Gemini model: %s", exc)
        return None


def investigate_flag(
    *,
    batch_name: str,
    batch_number: str,
    from_entity: str,
    to_entity: str,
    risk_score: float,
    triggered_rules: list,
    mismatch_details: list,
    rule_explanation: str,
    user_notes: str = "",
) -> str:
    """
    Call Gemini Flash to produce a human-readable investigation report.

    Returns an empty string if the LLM is unavailable so the caller can
    fall back to the rule-engine explanation.
    """
    model = _get_model()
    if model is None:
        return ""

    rules_text = ", ".join(triggered_rules) if triggered_rules else "none"
    mismatches_text = ""
    for m in mismatch_details:
        field = m.get("field", "unknown")
        if field == "quantity":
            mfg = m.get("manufacturer")
            sup = m.get("supplier")
            hos = m.get("hospital")
            dev = m.get("deviation_pct", "?")
            if mfg is not None:
                mismatches_text += f"  - Quantity: Manufacturer={mfg}, Supplier={sup}, deviation={dev}%\n"
            else:
                mismatches_text += f"  - Quantity: Supplier={sup}, Hospital={hos}, deviation={dev}%\n"
        elif field == "expiry":
            mismatches_text += f"  - Expiry mismatch: {m}\n"
        elif field == "temperature":
            mismatches_text += (
                f"  - Temperature difference: {m.get('difference_c')}°C "
                f"(reported by: {m})\n"
            )

    prompt = f"""You are a pharmaceutical supply chain compliance investigator AI.

A shipment has been automatically flagged by our rule engine. Analyse the data below and write a concise investigation report (max 3 short paragraphs, no bullet points, plain English) covering:
1. What specifically triggered the flag and what the numbers show.
2. The most likely root cause (e.g. genuine fraud, accidental damage, data-entry error, system delay).
3. The recommended next action for the compliance officer.

--- SHIPMENT ---
Medicine : {batch_name}  (Batch #{batch_number})
Route    : {from_entity} → {to_entity}

--- RULE ENGINE RESULT ---
Risk Score       : {risk_score}/100
Triggered Rules  : {rules_text}
Mismatch Details :
{mismatches_text if mismatches_text else "  (none beyond what the rules list)"}
Rule Explanation : {rule_explanation}

--- USER / OPERATOR NOTES ---
{user_notes if user_notes else "No additional notes provided."}

Write the report now. Keep it factual, professional, and under 160 words.
"""

    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as exc:  # noqa: BLE001
        logger.error("[LLM Investigator] Gemini API call failed: %s", exc)
        return ""
