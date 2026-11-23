"""
Test suite for ml/predict.py verifying triage level predictions,
explainability tags, edge cases, and safety rule overrides.
"""

import sys
from pathlib import Path

# Ensure ml/ is on sys.path when running from repo root or ml/
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "ml"))

from predict import predict


def run_tests():
    print("=" * 60)
    print("Running Hospital Triage Model Prediction Tests")
    print("=" * 60)

    # 1. Five sample patients, one per urgency level (1 to 5)
    sample_patients = [
        {
            "name": "Patient Level 1 (Resuscitation / Immediate)",
            "expected_level": 1,
            "data": {
                "age": 65,
                "gender": "M",
                "sbp": 75,
                "dbp": 50,
                "hr": 150,
                "spo2": 85,
                "temp": 37.2,
                "rr": 30,
                "symptoms": "Severe crushing chest pain, cannot breathe, collapsed and unresponsive",
            },
        },
        {
            "name": "Patient Level 2 (Emergent / High Risk)",
            "expected_level": 2,
            "data": {
                "age": 55,
                "gender": "M",
                "sbp": 148,
                "dbp": 88,
                "hr": 102,
                "spo2": 96,
                "temp": 37.1,
                "rr": 20,
                "symptoms": "Acute substernal chest pain radiating to left arm",
            },
        },
        {
            "name": "Patient Level 3 (Urgent)",
            "expected_level": 3,
            "data": {
                "age": 40,
                "gender": "F",
                "sbp": 130,
                "dbp": 85,
                "hr": 95,
                "spo2": 97,
                "temp": 38.6,
                "rr": 18,
                "symptoms": "Severe lower abdominal pain, high fever and shivering chills",
            },
        },
        {
            "name": "Patient Level 4 (Less Urgent)",
            "expected_level": 4,
            "data": {
                "age": 28,
                "gender": "F",
                "sbp": 118,
                "dbp": 76,
                "hr": 75,
                "spo2": 98,
                "temp": 36.8,
                "rr": 16,
                "symptoms": "Minor injury with shallow laceration and mild headache after bumping knee",
            },
        },
        {
            "name": "Patient Level 5 (Non-Urgent)",
            "expected_level": 5,
            "data": {
                "age": 22,
                "gender": "M",
                "sbp": 120,
                "dbp": 80,
                "hr": 70,
                "spo2": 99,
                "temp": 36.6,
                "rr": 14,
                "symptoms": "Routine wellness checkup, requesting prescription refill, feeling fine",
            },
        },
    ]

    for p in sample_patients:
        res = predict(p["data"])
        print(f"\n[Case] {p['name']}")
        print(f"  Vitals: SpO2={p['data']['spo2']}%, HR={p['data']['hr']} bpm, BP={p['data']['sbp']}/{p['data']['dbp']}, RR={p['data']['rr']}")
        print(f"  Symptoms: \"{p['data']['symptoms']}\"")
        print(f"  Output: urgency_level={res['urgency_level']}, confidence={res['confidence']:.4f}")
        print(f"  Reason tags: {res['reason_tags']}")

        # Validate structure
        assert isinstance(res["urgency_level"], int), "urgency_level must be int"
        assert 1 <= res["urgency_level"] <= 5, "urgency_level must be between 1 and 5"
        assert isinstance(res["confidence"], float), "confidence must be float"
        assert 0.0 <= res["confidence"] <= 1.0, "confidence must be between 0.0 and 1.0"
        assert isinstance(res["reason_tags"], list), "reason_tags must be list"
        assert 1 <= len(res["reason_tags"]) <= 4, "reason_tags must contain between 1 and 4 tags"

        # Explicit assertion for Level 1 patient required by specification
        if p["expected_level"] == 1:
            assert res["urgency_level"] == 1, f"Expected Level 1, got {res['urgency_level']}"
            print("  ✓ Level 1 assertion passed!")

        # Verify matched expected level for all test cases
        assert res["urgency_level"] == p["expected_level"], (
            f"Expected level {p['expected_level']}, got {res['urgency_level']}"
        )
        print(f"  ✓ Level {p['expected_level']} verified!")

    # 2. Test robustness with missing / empty symptoms
    print("\n" + "-" * 60)
    print("Testing edge cases: empty and missing symptoms")
    print("-" * 60)

    empty_symptoms_patient = {
        "age": 35,
        "gender": "F",
        "sbp": 120,
        "dbp": 80,
        "hr": 72,
        "spo2": 99,
        "temp": 36.7,
        "rr": 15,
        "symptoms": "",
    }
    res_empty = predict(empty_symptoms_patient)
    print(f"[Empty string symptoms] -> urgency_level={res_empty['urgency_level']}, tags={res_empty['reason_tags']}")
    assert 1 <= res_empty["urgency_level"] <= 5
    assert 1 <= len(res_empty["reason_tags"]) <= 4
    print("  ✓ Empty string symptoms handled successfully!")

    missing_symptoms_patient = {
        "age": 50,
        "gender": "M",
        "sbp": 125,
        "dbp": 82,
        "hr": 78,
        "spo2": 98,
        "temp": 36.9,
        "rr": 16,
        # 'symptoms' key completely omitted
    }
    res_missing = predict(missing_symptoms_patient)
    print(f"[Missing symptoms key]   -> urgency_level={res_missing['urgency_level']}, tags={res_missing['reason_tags']}")
    assert 1 <= res_missing["urgency_level"] <= 5
    assert 1 <= len(res_missing["reason_tags"]) <= 4
    print("  ✓ Missing symptoms key handled successfully!")

    # 3. Test safety override rule enforcement
    print("\n" + "-" * 60)
    print("Testing clinical safety override rules")
    print("-" * 60)

    # Test Level 1 rule override: patient with mild complaint but critically low SBP (< 80)
    override_l1_patient = {
        "age": 25,
        "gender": "F",
        "sbp": 76,  # Critical hypotension (< 80 mmHg)
        "dbp": 55,
        "hr": 75,
        "spo2": 98,
        "temp": 36.8,
        "rr": 16,
        "symptoms": "Mild headache",
    }
    res_l1 = predict(override_l1_patient)
    print(f"[Critical SBP override] -> urgency_level={res_l1['urgency_level']}, tags={res_l1['reason_tags']}")
    assert res_l1["urgency_level"] == 1, f"Expected Level 1 override, got {res_l1['urgency_level']}"
    assert any("Safety override" in tag for tag in res_l1["reason_tags"]), "Override tag should be present"
    print("  ✓ Level 1 safety override rule verified successfully!")

    # Test Level 2 rule override: patient with mild complaint but tachypnea RR > 28
    override_l2_patient = {
        "age": 25,
        "gender": "F",
        "sbp": 118,
        "dbp": 76,
        "hr": 75,
        "spo2": 98,
        "temp": 36.8,
        "rr": 32,  # Respiratory rate > 28/min
        "symptoms": "Mild headache",
    }
    res_l2 = predict(override_l2_patient)
    print(f"[Tachypnea RR override] -> urgency_level={res_l2['urgency_level']}, tags={res_l2['reason_tags']}")
    assert res_l2["urgency_level"] == 2, f"Expected Level 2 override, got {res_l2['urgency_level']}"
    assert any("Safety override" in tag for tag in res_l2["reason_tags"]), "Override tag should be present"
    print("  ✓ Level 2 safety override rule verified successfully!")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    run_tests()
