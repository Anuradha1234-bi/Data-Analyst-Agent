import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

backend_dir = Path(__file__).resolve().parent
project_root = backend_dir.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(backend_dir))

import pandas as pd
import numpy as np
from app.services.cleaning_service import cleaning_service

# Create a realistic test DataFrame reflecting real data issues
df = pd.DataFrame({
    "customer_id": ["C101", "C102", "C103", "C101", None, "C106", "C107", "C108", "C109", "C110"],
    "customer_name": ["Alice", "Bob", "Charlie", "Alice", "Eve", "Frank", "Grace", "Heidi", "Ivan", "Judy"],
    "city": ["Mumbai", "mumbai", " Mumbai ", "Delhi", "DELHI", "Bangalore", "mumbai", "Chennai", "Kolkata", "Pune"],
    "salary": ["₹1,200", "1,500", "2,000", "₹1,800", "2,500", "150,000", "2,200", "1,900", "2,100", "2,300"],
    "quantity": [0, 5, 2, 0, 10, 1, 3, 0, 4, 6],
    "total_amount": [150.0, 500.0, 200.0, 350.0, 1000.0, 150000.0, 300.0, 0.0, 400.0, 600.0],
    "start_date": ["2025-05-10", "2025-01-01", "2025-03-15", "2025-06-01", "2025-02-01", "2025-04-01", "2025-01-10", "2025-07-01", "2025-08-01", "2025-09-01"],
    "end_date":   ["2025-04-10", "2025-01-15", "2025-03-20", "2025-05-01", "2025-02-28", "2025-04-30", "2025-01-20", "2025-06-01", "2025-08-15", "2025-09-30"],
    "signup_date": ["2025-01-15", "01/02/2025", "2025-13-50", "2025-02-01", "Feb 1 2025", "not-a-date", "2025-03-01", "2025-03-15", "32/15/2025", "2025-04-01"],
    "notes": ["Good", "   ", "\t", "Pending", "", "Active", "Verified", "VIP", None, "New"],
    "age": ["25", "32", "45", "28", "39", "51", "not_an_age", "22", "60", "34"]
})

print("Dataset shape:", df.shape)

import tempfile
from types import SimpleNamespace
from app.schemas.cleaning import CustomConsistencyRuleRequest

temp_dir = tempfile.mkdtemp()
temp_csv = Path(temp_dir) / "test_data.csv"
df.to_csv(temp_csv, index=False)

mock_dataset = SimpleNamespace(
    id=999,
    filename="test_data.csv",
    file_size_bytes=temp_csv.stat().st_size,
    has_cleaned=False,
    file_path=str(temp_csv),
    cleaned_file_path=None
)

sugg = cleaning_service.get_smart_suggestions(mock_dataset)
print(f"\nSmart Suggestions ({sugg.total_suggestions}):")
print(f"High: {sugg.high_priority_count}, Med: {sugg.medium_priority_count}, Low: {sugg.low_priority_count}")
for s in sugg.suggestions:
    print(f"  - [{s.priority.upper()}] {s.issue}: {s.evidence} -> Action: {s.recommended_action} (type: {s.action_type})")

chk = cleaning_service.get_consistency_checks(mock_dataset)
print(f"\nConsistency Checks ({chk.total_violations} total violations across {chk.total_checks} checks):")
for c in chk.checks:
    print(f"  - [{c.severity.upper()}] {c.check_name}: {c.violations_count} violations ({c.violations_percentage}%) -> Action: {c.action_label}")

# Test custom cross-column rule
rule_req = CustomConsistencyRuleRequest(
    rule_name="Large Total Amount",
    column_a="total_amount",
    operator=">",
    column_b=None,
    constant_value="1000",
)
rule_res = cleaning_service.evaluate_custom_rule(mock_dataset, rule_req)
print(f"\nCustom Rule Test ({rule_res.rule_name}):")
print(f"Violating rows: {rule_res.violations_count} ({rule_res.violations_percentage}%)")

# Test validation report & cleaning score
orig_df = df.copy()
cleaned_df = df.copy()
# Clean notes whitespace
cleaned_df["notes"] = cleaned_df["notes"].replace(r"^\s*$", np.nan, regex=True)
val_res = cleaning_service._run_validation_comparison(mock_dataset, orig_df, cleaned_df)
print(f"\nValidation score: {val_res.cleaning_score} / 100 ({val_res.score_status})")
for chk_item in val_res.checks:
    print(f"  - {chk_item.check_name}: before={chk_item.before_value}, after={chk_item.after_value}, remaining={chk_item.remaining_issues}, score={chk_item.component_score}/{chk_item.weight}")
