"""
Crisis AI — Rule-based medicine recommendations per event type (Phase 3 MVP).
Communicates with other modules ONLY via the database.

# Phase 3 upgrade: replace manual input with GDELT + OpenWeather + NetworkX rerouting.
"""
from typing import Dict, List


# ── Medicine recommendation rules ────────────────────────────────────────────
# Format: event_type → list of {medicine, rationale, quantity_multiplier}
# quantity_multiplier = how many × normal stock level to pre-position

MEDICINE_RECOMMENDATIONS: Dict[str, List[dict]] = {
    "flood": [
        {"medicine": "ORS (Oral Rehydration Salts)",     "rationale": "Prevent dehydration from flood-contaminated water",    "quantity_multiplier": 3.0},
        {"medicine": "IV Fluids (Normal Saline)",         "rationale": "Severe dehydration / cholera treatment",               "quantity_multiplier": 2.5},
        {"medicine": "Antibiotics (Ciprofloxacin)",       "rationale": "Waterborne infections, typhoid, cholera",              "quantity_multiplier": 2.0},
        {"medicine": "Chlorine tablets",                  "rationale": "Water purification",                                   "quantity_multiplier": 4.0},
        {"medicine": "Anti-diarrheals (Metronidazole)",   "rationale": "Gastroenteritis from contaminated water",              "quantity_multiplier": 2.0},
        {"medicine": "Tetanus toxoid",                    "rationale": "Wound injuries during flood",                          "quantity_multiplier": 1.5},
    ],
    "earthquake": [
        {"medicine": "Morphine / Strong analgesics",      "rationale": "Crush injuries, severe trauma",                        "quantity_multiplier": 3.0},
        {"medicine": "Antibiotics (broad-spectrum)",      "rationale": "Wound infections, trapped-victim injuries",            "quantity_multiplier": 2.5},
        {"medicine": "Blood products / IV plasma",        "rationale": "Haemorrhage from structural collapse injuries",        "quantity_multiplier": 3.0},
        {"medicine": "Surgical sutures / wound supplies", "rationale": "Field surgeries",                                      "quantity_multiplier": 2.0},
        {"medicine": "Tetanus toxoid",                    "rationale": "Open wounds from debris",                              "quantity_multiplier": 2.0},
        {"medicine": "Anticonvulsants",                   "rationale": "Head trauma, crush syndrome",                          "quantity_multiplier": 1.5},
    ],
    "disease_outbreak": [
        {"medicine": "Antivirals (Oseltamivir/Remdesivir)", "rationale": "Direct antiviral treatment",                         "quantity_multiplier": 4.0},
        {"medicine": "PPE (N95, gloves, gowns)",            "rationale": "Healthcare worker protection",                       "quantity_multiplier": 5.0},
        {"medicine": "Antipyretics (Paracetamol)",          "rationale": "Fever management",                                   "quantity_multiplier": 3.0},
        {"medicine": "Electrolyte solutions",               "rationale": "Supportive care for febrile patients",               "quantity_multiplier": 2.0},
        {"medicine": "Vaccines (if applicable)",            "rationale": "Ring vaccination around outbreak zone",               "quantity_multiplier": 6.0},
    ],
    "conflict": [
        {"medicine": "Morphine / Analgesics",             "rationale": "Gunshot / blast injuries",                            "quantity_multiplier": 3.0},
        {"medicine": "Blood products",                    "rationale": "Haemorrhage",                                         "quantity_multiplier": 4.0},
        {"medicine": "Antibiotics (IV)",                  "rationale": "Wound sepsis",                                        "quantity_multiplier": 3.0},
        {"medicine": "Surgical supplies",                 "rationale": "Field surgery",                                       "quantity_multiplier": 2.5},
        {"medicine": "Mental health medications",         "rationale": "PTSD, acute stress disorders",                        "quantity_multiplier": 1.5},
    ],
    "cyclone": [
        {"medicine": "ORS",                               "rationale": "Dehydration from water scarcity post-cyclone",        "quantity_multiplier": 2.5},
        {"medicine": "Antibiotics",                       "rationale": "Wound infections, waterborne disease",                "quantity_multiplier": 2.0},
        {"medicine": "Analgesics",                        "rationale": "Trauma injuries from debris",                         "quantity_multiplier": 2.0},
        {"medicine": "Insulin / Diabetes meds",           "rationale": "Chronic condition continuity in displaced persons",   "quantity_multiplier": 1.5},
    ],
    "port_closure": [
        {"medicine": "Essential medicines buffer stock",  "rationale": "Prevent import disruption from port closure",         "quantity_multiplier": 2.0},
        {"medicine": "Antibiotics",                       "rationale": "High-demand import category",                         "quantity_multiplier": 2.0},
        {"medicine": "Oncology drugs",                    "rationale": "Often imported; stockout risk is critical",           "quantity_multiplier": 2.5},
    ],
    "heatwave": [
        {"medicine": "ORS / Electrolytes",                "rationale": "Heat exhaustion, dehydration",                        "quantity_multiplier": 3.0},
        {"medicine": "Antihistamines",                    "rationale": "Heat rash, allergic reactions",                       "quantity_multiplier": 1.5},
        {"medicine": "Cardiac medications",               "rationale": "Heat stress, increased cardiac events in elderly",    "quantity_multiplier": 2.0},
        {"medicine": "IV Saline",                         "rationale": "Severe heat stroke hospitalisation",                  "quantity_multiplier": 2.5},
    ],
}


SEVERITY_MULTIPLIERS = {
    "low":      0.5,
    "medium":   1.0,
    "high":     1.5,
    "critical": 2.0,
}


def get_recommendations(event_type: str, severity: str = "medium") -> List[dict]:
    """
    Return medicine recommendations for a crisis event type + severity.
    quantity_multiplier is scaled by severity.
    """
    base = MEDICINE_RECOMMENDATIONS.get(event_type.lower(), [])
    sev_factor = SEVERITY_MULTIPLIERS.get(severity.lower(), 1.0)

    result = []
    for item in base:
        result.append({
            **item,
            "quantity_multiplier": round(item["quantity_multiplier"] * sev_factor, 1),
        })
    return result


def supported_event_types() -> List[str]:
    return list(MEDICINE_RECOMMENDATIONS.keys())
