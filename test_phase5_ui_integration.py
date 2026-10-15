import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Ensure path is included
sys.path.insert(0, str(Path(__file__).parent))

from core.session_manager import SessionManager
from services.phase5_engine import (
    run_phase5_analysis,
    explain_insights_with_ai,
    prepare_analysis_visualizations,
)
from services.report_generator import ReportGeneratorService


def test_single_dataset_ui_workflow():
    print("Testing Single Dataset UI Workflow...")
    dates = pd.date_range("2024-01-01", periods=20, freq="D")
    df = pd.DataFrame({
        "TransactionDate": dates,
        "Category": ["Electronics", "Fashion", "Groceries", "Electronics"] * 5,
        "Revenue": [100.0 + i * 15.0 for i in range(20)],
        "Discount": [5.0 + (i % 4) for i in range(20)],
        "Notes": [f"Order #{i}" for i in range(20)],
    })

    SessionManager.init()
    SessionManager.add_dataset(df, "sales.csv", "CSV")

    config = {
        "selected_datasets": ["sales.csv"],
        "target_dataset": "sales.csv",
        "statistics": {"enabled": True},
        "trends": {"enabled": True, "date_column": "TransactionDate"},
        "correlations": {"enabled": True, "method": "pearson", "strong_threshold": 0.70, "moderate_threshold": 0.40},
        "categories": {"enabled": True, "top_n": 10},
        "anomalies": {"include_phase4": True},
        "insights": {"enabled": True, "max_insights": 20, "min_evidence_score": 0.60},
        "visualizations": {"enabled": True, "max_charts": 10},
        "ai_explanation": {"enabled": True, "only_computed_results": True, "allow_speculation": False},
    }

    result = run_phase5_analysis({"sales.csv": df}, analysis_configuration=config)
    assert result["status"] == "success"
    assert "sales.csv" in result["datasets_analyzed"]
    
    # Statistical moments check
    stats = result["statistics"]["column_statistics"]
    assert "Revenue" in stats
    assert stats["Revenue"]["mean"] is not None
    assert stats["Notes"]["mean"] is None # Categorical has None for numeric mean

    # Trends check
    assert result["trends"]["status"] == "success"
    assert len(result["trends"]["trends"]) > 0

    # Correlations check
    assert result["correlations"]["status"] == "success"
    assert "Revenue" in result["correlations"]["matrix"]

    # Category check
    assert result["categories"]["status"] == "success"
    assert len(result["categories"]["distributions"]) > 0

    # Insights check
    assert len(result["insights"]) > 0

    # Visualizations check
    assert result["visualizations"]["status"] == "success"
    assert "trend" in result["visualizations"]["charts"]

    # AI Explanation grounded check
    ai_expl = explain_insights_with_ai(result["insights"], result)
    assert ai_expl["grounded_in_computed_facts"] is True
    assert "Executive Narrative Summary" in ai_expl["summary"]

    # Custom question check
    q_ans = explain_insights_with_ai(result["insights"], result, user_question="Why is this trend important?")
    assert q_ans["grounded_in_computed_facts"] is True

    # Report check
    md_rep = ReportGeneratorService.generate_markdown_report(
        datasets={"sales.csv": df},
        profiles=SessionManager.get_all_profiles(),
        relationships=[],
        join_audits=[],
        insights=result["insights"],
    )
    assert "# Multi-Dataset Executive Analysis Report" in md_rep
    print("  [PASS] Single dataset UI workflow verified.")


def test_multi_dataset_ui_workflow():
    print("Testing Multi-Dataset UI Workflow...")
    orders = pd.DataFrame({
        "order_id": [1, 2, 3, 4],
        "customer_id": ["C1", "C2", "C3", "C4"],
        "amount": [120.0, 250.0, 90.0, 410.0],
    })
    customers = pd.DataFrame({
        "customer_id": ["C1", "C2", "C3", "C4"],
        "country": ["USA", "UK", "Canada", "Germany"],
    })

    datasets = {"orders.csv": orders, "customers.csv": customers}
    valid_rel = {
        "source_dataset": "orders.csv",
        "source_column": "customer_id",
        "target_dataset": "customers.csv",
        "target_column": "customer_id",
        "confidence": "HIGH",
    }

    config = {
        "selected_datasets": ["orders.csv", "customers.csv"],
        "target_dataset": "orders.csv",
        "cross_dataset": {
            "enabled": True,
            "require_validated_relationships": True,
            "allow_low_confidence": False,
            "allow_many_to_many": False,
            "max_row_growth_ratio": 2.0,
        },
    }

    result = run_phase5_analysis(
        datasets=datasets,
        analysis_configuration=config,
        validated_relationships=[valid_rel],
    )
    assert result["status"] == "success"
    assert len(result["datasets_analyzed"]) == 2
    assert result["cross_dataset"]["status"] == "success"
    assert result["cross_dataset"]["rows_after"] == 4

    # Multi-dataset per_dataset caching check
    assert "orders.csv" in result["per_dataset"]
    assert "customers.csv" in result["per_dataset"]
    print("  [PASS] Multi-dataset UI workflow verified.")


def test_unsafe_many_to_many_join_blocked():
    print("Testing Unsafe Many-to-Many Join Guard...")
    left = pd.DataFrame({"key": ["A", "A", "B"], "v1": [1, 2, 3]})
    right = pd.DataFrame({"key": ["A", "A", "B"], "v2": [10, 20, 30]})
    bad_rel = {
        "source_dataset": "left.csv",
        "source_column": "key",
        "target_dataset": "right.csv",
        "target_column": "key",
        "confidence": "HIGH",
    }

    result = run_phase5_analysis(
        datasets={"left.csv": left, "right.csv": right},
        validated_relationships=[bad_rel],
    )
    assert result["cross_dataset"]["status"] == "blocked"
    assert "many-to-many" in result["cross_dataset"]["reason"].lower()
    print("  [PASS] Unsafe many-to-many join guard verified.")


if __name__ == "__main__":
    print("=====================================================================")
    print("VERIFYING PHASE 5 UI INTEGRATION AND USER CONTROLS WORKFLOW")
    print("=====================================================================")
    test_single_dataset_ui_workflow()
    test_multi_dataset_ui_workflow()
    test_unsafe_many_to_many_join_blocked()
    print("=====================================================================")
    print("ALL PHASE 5 UI INTEGRATION SCENARIOS VERIFIED SUCCESSFULLY!")
    print("=====================================================================")
