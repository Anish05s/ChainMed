import time
import json
import random
import sys
import os

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from verification_ai.engine import compute_risk_score

def run_benchmarks():
    print("Starting Performance Benchmarks...")
    
    num_trials = 1000
    
    # 1. Pure Formula Latency
    print("1. Testing Risk Score Latency...")
    start_time = time.perf_counter()
    for _ in range(num_trials):
        compute_risk_score(
            quantities=[1000, 1000, 1000],
            expiries=["2025-01-01", "2025-01-01", "2025-01-01"],
            batch_numbers=["BATCH1", "BATCH1", "BATCH1"],
            medicine_names=["MedA", "MedA", "MedA"],
            temps=[20.0, 20.0, 20.0]
        )
    end_time = time.perf_counter()
    avg_latency_ms = ((end_time - start_time) / num_trials) * 1000
    print(f"Average Latency: {avg_latency_ms:.4f} ms")

    # 2. FPR and FNR Testing
    print("2. Testing False Positive / False Negative Rates...")
    
    false_positives = 0
    # Clean data should return risk_score < 30 (VERIFIED)
    for _ in range(num_trials):
        res = compute_risk_score(
            quantities=[1000, 1000, 1000],
            expiries=["2025-01-01", "2025-01-01", "2025-01-01"],
            batch_numbers=["BATCH1", "BATCH1", "BATCH1"],
            medicine_names=["MedA", "MedA", "MedA"],
            temps=[20.0, 20.5, 19.5] # Normal slight temp variation
        )
        if res["risk_score"] >= 30:
            false_positives += 1
            
    false_negatives = 0
    # Fraud data: severe quantity deviation (should return >= 30, FLAGGED)
    for _ in range(num_trials):
        res = compute_risk_score(
            quantities=[1000, 800, 500], # Massive deviation
            expiries=["2025-01-01", "2025-01-01", "2025-01-01"],
            batch_numbers=["BATCH1", "BATCH1", "BATCH1"],
            medicine_names=["MedA", "MedA", "MedA"],
            temps=[20.0, 20.0, 20.0]
        )
        if res["risk_score"] < 30:
            false_negatives += 1

    fpr = (false_positives / num_trials) * 100
    fnr = (false_negatives / num_trials) * 100
    print(f"False Positive Rate (FPR): {fpr:.2f}%")
    print(f"False Negative Rate (FNR): {fnr:.2f}%")

    results = {
        "trials": num_trials,
        "avg_latency_ms": avg_latency_ms,
        "fpr_percentage": fpr,
        "fnr_percentage": fnr
    }
    
    with open("results.json", "w") as f:
        json.dump(results, f, indent=4)
        
    print("Results saved to benchmarks/results.json")

if __name__ == "__main__":
    run_benchmarks()
