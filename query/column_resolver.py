"""Column Resolver with Semantic Matching, Lineage Inspection, and Ambiguity Safeguards.

Resolves natural language column mentions against dataset columns using:
1. Exact matching (preferred unconditionally when unambiguous).
2. Lineage inspection: distinguishes original base columns from join-generated suffixed duplicates.
3. Token overlap, string distance, and semantic synonyms.
4. Genuine ambiguity safeguards: when multiple distinct business metrics match, prompts for clarification with readable labels.
"""

from difflib import SequenceMatcher
from typing import Dict, Any, List, Optional, Union
import re
import pandas as pd

from query.column_lineage import inspect_column_lineage, ColumnLineageInfo


# Semantic synonyms commonly found in analytical tabular datasets across business, academic, HR, and operations
SEMANTIC_SYNONYMS: Dict[str, List[str]] = {
    # Monetary / Pricing
    "price": ["cost", "rate", "amount", "modal_price", "min_price", "max_price", "value", "unit_price", "pricing", "priced", "expensive", "costly"],
    "sales": ["revenue", "turnover", "income", "amount", "total_sales", "receipts", "sale", "selling", "sold", "sells", "sales_amount"],
    "profit": ["margin", "gain", "earnings", "net_profit", "profitable", "profitability"],
    "cost": ["cost", "expense", "expenses", "spending", "spent", "expenditure", "spending_amount"],
    "discount": ["discount", "rebate", "concession", "discount_amount", "discount_pct"],
    "amount": ["order_amount", "order_amount_inr", "amount", "total_amount", "sales", "revenue", "price", "spending"],
    "spent": ["amount", "order_amount", "order_amount_inr", "spending", "sales", "revenue", "cost", "total_amount"],
    "spend": ["amount", "order_amount", "order_amount_inr", "spending", "sales", "revenue", "cost", "total_amount"],
    "spending": ["amount", "order_amount", "order_amount_inr", "spending", "sales", "revenue", "cost", "total_amount"],
    "money": ["amount", "order_amount", "order_amount_inr", "sales", "revenue", "price", "spending"],

    # Volume & Quantities
    "quantity": ["qty", "volume", "units", "count", "arrivals", "arrival_quantity", "stock", "units_sold", "number_of_units", "items_sold"],

    # Academic & Educational
    "marks": ["marks", "mark", "score", "scores", "grade", "grades", "subject_marks", "total_marks", "theory_marks", "practical_marks", "obtained_marks", "result"],
    "score": ["score", "scores", "marks", "mark", "rating", "points", "result"],
    "percentage": ["percentage", "percent", "pct", "marks_pct", "ratio", "proportion"],
    "sgpa": ["sgpa", "gpa", "sem_sgpa", "semester_sgpa", "spi"],
    "cgpa": ["cgpa", "gpa", "cumulative_gpa", "overall_gpa", "cpi"],
    "student": ["student", "pupil", "candidate", "learner", "student_name", "candidate_name", "roll_no", "roll_number", "roll"],
    "subject": ["subject", "course", "paper", "topic", "subject_name", "course_name"],
    "attendance": ["attendance", "present", "presence", "attendance_pct"],

    # Human Resources & Demographics
    "salary": ["salary", "package", "ctc", "annual_ctc", "wage", "wages", "pay", "compensation", "stipend", "remuneration"],
    "employee": ["employee", "staff", "worker", "personnel", "emp_name", "name"],
    "age": ["age", "years_old", "dob", "birth_year"],

    # Business, Customer & Locations
    "customer": ["client", "buyer", "user", "consumer", "account", "customer_name", "client_name"],
    "market": ["mandi", "bazaar", "location", "center", "city", "region", "district", "place"],
    "commodity": ["product", "item", "crop", "good", "produce", "category"],
    "state": ["province", "region", "territory", "zone"],
    "order": ["order", "order_id", "transaction", "invoice", "purchase"],
    "rating": ["rating", "score", "stars", "feedback", "review", "rated"],
    "rank": ["rank", "position", "standing", "order"],
    "date": ["time", "day", "timestamp", "period", "month", "year", "created_at", "transaction_date"],
    "performance": ["revenue", "sales", "amount", "score", "total"],
}

DERIVABLE_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "target": "profit",
        "synonyms": ["profit", "net_profit", "earnings", "gain"],
        "formula_type": "difference",
        "source1_synonyms": ["revenue", "sales", "income", "turnover"],
        "source2_synonyms": ["cost", "expense", "expenses", "expenditure"],
        "output_name": "Profit",
    },
    {
        "target": "revenue",
        "synonyms": ["revenue", "sales", "total_amount", "amount"],
        "formula_type": "product",
        "source1_synonyms": ["price", "unit_price", "rate"],
        "source2_synonyms": ["quantity", "qty", "units", "units_sold"],
        "output_name": "Revenue",
    },
    {
        "target": "margin",
        "synonyms": ["margin", "profit_margin", "margin_pct"],
        "formula_type": "ratio_pct",
        "source1_synonyms": ["profit", "net_profit"],
        "source2_synonyms": ["revenue", "sales"],
        "output_name": "Profit_Margin_Pct",
    },
]


def check_derivable_metric(requested_col: str, available_cols: List[str]) -> Optional[Dict[str, Any]]:
    """Check if a requested metric can be mathematically derived from available dataset columns."""
    if not requested_col or not available_cols:
        return None
    req_norm = _normalize_name(requested_col)
    for defn in DERIVABLE_DEFINITIONS:
        if req_norm in [_normalize_name(s) for s in defn["synonyms"]]:
            col1 = None
            col2 = None
            for col in available_cols:
                c_norm = _normalize_name(col)
                if not col1 and any(c_norm == _normalize_name(s) or _normalize_name(s) in c_norm for s in defn["source1_synonyms"]):
                    col1 = col
                elif not col2 and any(c_norm == _normalize_name(s) or _normalize_name(s) in c_norm for s in defn["source2_synonyms"]):
                    col2 = col

            if col1 and col2 and col1 != col2:
                formula_str = f"{col1} - {col2}" if defn["formula_type"] == "difference" else (
                    f"{col1} * {col2}" if defn["formula_type"] == "product" else f"({col1} / {col2}) * 100"
                )
                return {
                    "is_derivable": True,
                    "target_metric": defn["target"],
                    "output_name": defn["output_name"],
                    "formula_type": defn["formula_type"],
                    "col1": col1,
                    "col2": col2,
                    "formula": formula_str,
                    "explanation": f"Calculated as '{formula_str}' from available dataset columns."
                }
    return None

# Extraction and system metadata patterns (PDF/OCR pagination, row/line offsets, system IDs)
EXTRACTION_METADATA_PATTERNS: List[str] = [
    r"^pdf[_\s]?page",
    r"^page[_\s]?(?:num|number|no|idx|index)?$",
    r"^line[_\s]?(?:num|number|no|idx|index)?$",
    r"^row[_\s]?(?:num|number|no|idx|index|id)?$",
    r"^unnamed",
    r"^(?:id|_id|index|idx)$",
    r"^bbox",
    r"^offset",
    r"^char[_\s]?(?:start|end|offset)",
    r"^token[_\s]?(?:idx|index|id)",
]

# Conversational and analytical stopwords that must not fuzzy-match to column names
RESOLVER_STOPWORDS = {
    "flagged", "failed", "passed", "case", "cases", "based", "criteria",
    "evidence", "explain", "record", "records", "data", "dataset",
    "which", "what", "where", "when", "show", "list", "find", "give",
    "tell", "highest", "lowest", "average", "mean", "total", "sum",
    "count", "each", "every", "all", "between", "across", "about",
    "risk", "level", "levels", "value", "values", "number", "numbers",
    "row", "rows", "column", "columns", "feature", "features", "metric",
    "metrics", "stat", "stats", "statistic", "statistics", "first",
    "second", "third", "last", "any", "some", "none", "true", "false",
    "method", "methods", "approach", "approaches", "technique", "techniques",
    "algorithm", "algorithms", "way", "ways", "model", "models",
    "name", "names", "column_name", "column_names", "type", "types",
    "data_type", "data_types", "filename", "file_name", "schema", "metadata",
    "summing", "group", "groups", "grouping", "calculating", "aggregating", "totaling",
}


def is_metadata_column(column_name: str) -> bool:
    """Check if a column represents technical or extraction metadata rather than a domain metric."""
    if not column_name:
        return False
    norm = re.sub(r"[^a-zA-Z0-9_]", "_", str(column_name).strip().lower())
    for pattern in EXTRACTION_METADATA_PATTERNS:
        if re.search(pattern, norm):
            return True
    return False


def filter_metadata_columns(columns: List[str]) -> List[str]:
    """Filter out technical and extraction metadata columns, returning domain columns."""
    return [c for c in columns if not is_metadata_column(c)]


def _normalize_name(name: str) -> str:
    """Normalize string by removing special characters, spaces, and converting to lowercase."""
    return re.sub(r"[^a-zA-Z0-9]", "", str(name).lower())


def _extract_columns_from_metadata(metadata: Any) -> List[str]:
    """Extract list of column names from various metadata structures."""
    if not metadata:
        return []
    if isinstance(metadata, list):
        return [str(c) for c in metadata]
    if isinstance(metadata, dict):
        if "column_names" in metadata:
            return [str(c) for c in metadata["column_names"]]
        if "data_types" in metadata and isinstance(metadata["data_types"], dict):
            return [str(c) for c in metadata["data_types"].keys()]
        if "columns" in metadata:
            cols = metadata["columns"]
            if isinstance(cols, list):
                return [str(c) for c in cols]
            if isinstance(cols, dict):
                return [str(c) for c in cols.keys()]
            if isinstance(cols, int):
                pass
        if all(isinstance(v, (str, dict)) for v in metadata.values()):
            return [str(k) for k in metadata.keys() if k not in ("filename", "file_type", "rows", "columns")]
    if hasattr(metadata, "column_names"):
        return list(getattr(metadata, "column_names", []))
    if hasattr(metadata, "columns"):
        return list(getattr(metadata, "columns", []))
    return []


def resolve_column(
    requested_column: str,
    dataset_metadata: Any,
    column_type_filter: Optional[str] = None,  # "numeric", "categorical", "date", or None
    df: Optional[pd.DataFrame] = None,
    join_history: Optional[Dict[str, Any]] = None,
    lineage_map: Optional[Dict[str, ColumnLineageInfo]] = None,
) -> Dict[str, Any]:
    """Resolve a requested column string to an actual dataset column with lineage awareness.

    Contract:
    Returns:
    {
        "resolved": True/False,
        "column": "unit_price",
        "confidence": 1.0,
        "candidates": [...],
        "is_ambiguous": bool,
        "clarification_options": [...],
        "clarification_candidates": [...],
        "selection_explanation": Optional[str],
    }
    """
    if not requested_column or not str(requested_column).strip():
        return {
            "resolved": False,
            "column": None,
            "confidence": 0.0,
            "candidates": [],
            "is_ambiguous": False,
            "clarification_options": [],
            "clarification_candidates": [],
            "selection_explanation": None,
        }

    raw_req = str(requested_column).strip()
    norm_req = _normalize_name(raw_req)
    req_lower = raw_req.lower()

    columns = _extract_columns_from_metadata(dataset_metadata)
    if not columns:
        return {
            "resolved": False,
            "column": None,
            "confidence": 0.0,
            "candidates": [],
            "is_ambiguous": False,
            "clarification_options": [],
            "clarification_candidates": [],
            "selection_explanation": None,
        }

    # Extract data types if available from metadata or DataFrame
    dtypes: Dict[str, str] = {}
    if isinstance(dataset_metadata, dict) and "data_types" in dataset_metadata:
        dtypes = {str(k): str(v) for k, v in dataset_metadata["data_types"].items()}
    elif df is not None:
        dtypes = {str(c): str(df[c].dtype) for c in df.columns}

    # Filter columns by requested data type if specified
    if column_type_filter:
        filtered_cols = []
        for c in columns:
            is_num = False
            if c in dtypes:
                dt_l = str(dtypes[c]).lower()
                is_num = any(t in dt_l for t in ["int", "float", "double", "decimal", "numeric"])
            elif isinstance(dataset_metadata, dict) and "numeric_columns" in dataset_metadata:
                is_num = c in dataset_metadata["numeric_columns"]
            elif df is not None and c in df.columns:
                is_num = pd.api.types.is_numeric_dtype(df[c])

            if column_type_filter == "numeric" and is_num:
                filtered_cols.append(c)
            elif column_type_filter == "categorical" and not is_num:
                filtered_cols.append(c)
            elif column_type_filter not in ("numeric", "categorical"):
                filtered_cols.append(c)

        if filtered_cols:
            columns = filtered_cols

    # Inspect column lineage
    if lineage_map is None:
        ds_name = dataset_metadata.get("filename") if isinstance(dataset_metadata, dict) else None
        lineage_map = inspect_column_lineage(columns, data_types=dtypes, join_history=join_history, dataset_name=ds_name)

    def _to_singular(word: str) -> str:
        w = word.lower()
        if w.endswith("ies") and len(w) > 4:
            return w[:-3] + "y"
        if w.endswith("es") and len(w) > 3:
            return w[:-2]
        if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
            return w[:-1]
        return w

    exact_match: Optional[str] = None
    for col in columns:
        if col.lower() == req_lower:
            exact_match = col
            break

    if not exact_match:
        for col in columns:
            if _normalize_name(col) == norm_req:
                exact_match = col
                break

    if not exact_match:
        sing_req = _to_singular(req_lower)
        for col in columns:
            if _to_singular(col.lower()) == sing_req or _to_singular(_normalize_name(col)) == _to_singular(norm_req):
                exact_match = col
                break

    if not exact_match and len(req_lower.split()) > 1:
        req_words = [w for w in re.split(r"[_\s]+", req_lower) if w]
        if req_words:
            last_w = req_words[-1]
            if last_w not in RESOLVER_STOPWORDS:
                for col in columns:
                    if col.lower() == last_w or _to_singular(col.lower()) == _to_singular(last_w):
                        exact_match = col
                        break
        if not exact_match and req_words:
            entity_qualifiers = {"customer", "client", "user", "order", "item", "product", "student", "employee", "record", "transaction"}
            for w in reversed(req_words):
                if w not in entity_qualifiers and w not in RESOLVER_STOPWORDS and len(w) >= 3:
                    for col in columns:
                        if col.lower() == w or _to_singular(col.lower()) == _to_singular(w):
                            exact_match = col
                            break
                    if exact_match:
                        break

    if exact_match:
        # Check if there are join-generated suffixed duplicates of this exact match
        exact_lineage = lineage_map.get(exact_match)
        base = exact_lineage.base_name if exact_lineage else exact_match
        suffixed_dups = [
            c for c in columns
            if c != exact_match and lineage_map.get(c) and lineage_map[c].base_name.lower() == base.lower() and lineage_map[c].is_join_generated
        ]

        explanation = None
        if suffixed_dups:
            explanation = (
                f"Selected exact matching primary column '{exact_match}' "
                f"(preferred over join-generated duplicate '{suffixed_dups[0]}')."
            )

        return {
            "resolved": True,
            "column": exact_match,
            "confidence": 1.0,
            "candidates": [{"column": exact_match, "score": 1.0, "match_type": "exact"}],
            "is_ambiguous": False,
            "clarification_options": [],
            "clarification_candidates": [],
            "selection_explanation": explanation,
        }

    # -------------------------------------------------------------------------
    # STEP 2: Score Candidate Columns Semantically
    # -------------------------------------------------------------------------
    candidates: List[Dict[str, Any]] = []

    # If the requested token is an ordinary English/analytical stopword, skip fuzzy matching
    is_stopword = (req_lower in RESOLVER_STOPWORDS or norm_req in RESOLVER_STOPWORDS)

    if not is_stopword:
        sing_req = _to_singular(req_lower)
        for col in columns:
            col_lower = col.lower()
            norm_col = _normalize_name(col)
            score = 0.0
            match_type = "none"

            col_lineage = lineage_map.get(col)
            base_lower = col_lineage.base_name.lower() if col_lineage else col_lower
            norm_base = _normalize_name(base_lower)

            # 1. Check substring containment on base name and full name (tokens >= 3 chars)
            if len(norm_req) >= 3 and len(norm_base) >= 3:
                if norm_req in norm_base or sing_req in norm_base:
                    score = 0.80 + (0.15 * (len(norm_req) / max(len(norm_base), 1)))
                    match_type = "base_substring"
                elif norm_base in norm_req and (len(norm_base) / max(len(norm_req), 1)) >= 0.5:
                    score = 0.75 + (0.15 * (len(norm_base) / max(len(norm_req), 1)))
                    match_type = "base_superstring"
                elif norm_req in norm_col:
                    score = 0.70 + (0.15 * (len(norm_req) / max(len(norm_col), 1)))
                    match_type = "substring"
                elif norm_col in norm_req and (len(norm_col) / max(len(norm_req), 1)) >= 0.5:
                    score = 0.65 + (0.15 * (len(norm_col) / max(len(norm_req), 1)))
                    match_type = "superstring"

            # 1b. Check token containment in split column tokens (snake_case / spaces)
            col_tokens = [_to_singular(t) for t in re.split(r"[_\s]+", base_lower) if len(t) >= 3]
            if sing_req in col_tokens:
                token_score = 0.88
                if token_score > score:
                    score = token_score
                    match_type = "token_match"

            # 2. Fuzzy sequence matching against base name (require tokens >= 4 chars and score >= 0.72)
            if len(req_lower) >= 4 and len(base_lower) >= 4:
                seq_base = SequenceMatcher(None, req_lower, base_lower).ratio()
                if seq_base >= 0.72 and seq_base > score:
                    score = seq_base
                    match_type = "fuzzy_base"

                seq_full = SequenceMatcher(None, req_lower, col_lower).ratio()
                if seq_full >= 0.72 and seq_full > score:
                    score = seq_full
                    match_type = "fuzzy"

            # 3. Check semantic synonyms against base name
            for concept, syns in SEMANTIC_SYNONYMS.items():
                concept_syns_norm = [_normalize_name(s) for s in syns] + [_to_singular(_normalize_name(s)) for s in syns]
                req_matches_concept = (
                    req_lower == concept
                    or sing_req == _to_singular(concept)
                    or req_lower in syns
                    or sing_req in [_to_singular(s) for s in syns]
                    or norm_req in concept_syns_norm
                    or sing_req in concept_syns_norm
                )
                col_tokens_sing = [_to_singular(t) for t in re.split(r"[_\s]+", base_lower)]
                col_matches_concept = (
                    base_lower == concept
                    or sing_req == _to_singular(base_lower)
                    or any(s in base_lower for s in syns)
                    or any(s in col_tokens_sing for s in [concept] + syns)
                )
                if req_matches_concept and col_matches_concept:
                    is_direct_concept = (base_lower == concept or _to_singular(base_lower) == _to_singular(concept) or concept in col_tokens_sing)
                    syn_score = 0.93 if is_direct_concept else 0.84
                    if syn_score > score:
                        score = syn_score
                        match_type = f"synonym_{concept}"

            if score >= 0.70:
                candidates.append({
                    "column": col,
                    "score": round(score, 3),
                    "match_type": match_type,
                    "base_name": col_lineage.base_name if col_lineage else col,
                    "is_join_generated": col_lineage.is_join_generated if col_lineage else False,
                })

    # Sort candidates by descending score
    candidates.sort(key=lambda x: x["score"], reverse=True)

    if not candidates:
        return {
            "resolved": False,
            "column": None,
            "confidence": 0.0,
            "candidates": [],
            "is_ambiguous": False,
            "clarification_options": [],
            "clarification_candidates": [],
            "selection_explanation": None,
        }

    # -------------------------------------------------------------------------
    # STEP 3: Inspect Lineage and Ambiguity Among Top Candidates
    # -------------------------------------------------------------------------
    top_candidate = candidates[0]
    top_score = top_candidate["score"]

    if top_score < 0.70:
        return {
            "resolved": False,
            "column": None,
            "confidence": top_score,
            "candidates": candidates,
            "is_ambiguous": False,
            "clarification_options": [],
            "clarification_candidates": [],
            "selection_explanation": None,
        }

    plausible_candidates = [
        c for c in candidates
        if c["score"] >= 0.70 and (top_score - c["score"]) <= 0.05
    ]

    # Also check token containment columns (e.g. "price" inside "modal_price", "min_price")
    matching_token_cols = []
    if not is_stopword:
        matching_token_cols = [
            col for col in columns
            if norm_req in _normalize_name(col).split("_")
            or any(norm_req == token for token in re.findall(r"[a-zA-Z]+", col.lower()))
        ]

    all_matched_cols = list(set([c["column"] for c in plausible_candidates] + matching_token_cols))

    if len(all_matched_cols) > 1:
        # Group candidate columns by their base name using lineage
        unique_bases = set()
        base_to_cols: Dict[str, List[str]] = {}

        for col in all_matched_cols:
            lin = lineage_map.get(col)
            base = lin.base_name if lin else col
            unique_bases.add(base.lower())
            base_to_cols.setdefault(base.lower(), []).append(col)

        # SUB-CASE A: All candidate columns share the EXACT SAME base name!
        # e.g. "unit_price" and "unit_price_joined_orders__1__customers_1"
        if len(unique_bases) == 1:
            matching_cols = list(base_to_cols.values())[0]
            # Check if there is an original (un-suffixed) base column
            original_candidates = [
                c for c in matching_cols
                if lineage_map.get(c) and not lineage_map[c].is_join_generated
            ]
            joined_candidates = [
                c for c in matching_cols
                if lineage_map.get(c) and lineage_map[c].is_join_generated
            ]

            if original_candidates:
                chosen_col = original_candidates[0]
                explanation = (
                    f"Selected primary column '{chosen_col}' "
                    f"(preferred over join-generated duplicate '{joined_candidates[0]}')."
                    if joined_candidates else None
                )
                return {
                    "resolved": True,
                    "column": chosen_col,
                    "confidence": 0.95,
                    "candidates": candidates,
                    "is_ambiguous": False,
                    "clarification_options": [],
                    "clarification_candidates": [],
                    "selection_explanation": explanation,
                }

        # SUB-CASE B: Multiple distinct base names exist!
        # e.g. "Modal_Price", "Min_Price", "Max_Price"
        # Ambiguity is genuine and material!
        candidate_lineage_dicts = [
            lineage_map[c].to_dict() for c in all_matched_cols if c in lineage_map
        ]
        labels = [
            lineage_map[c].clarification_label for c in all_matched_cols if c in lineage_map
        ]

        return {
            "resolved": False,
            "column": None,
            "confidence": top_score,
            "candidates": candidates,
            "is_ambiguous": True,
            "clarification_options": all_matched_cols,
            "clarification_candidates": candidate_lineage_dicts,
            "clarification_labels": labels,
            "selection_explanation": None,
        }

    # Single unambiguous candidate
    chosen = top_candidate["column"]
    chosen_lineage = lineage_map.get(chosen)
    explanation = None
    if chosen_lineage and chosen_lineage.is_join_generated:
        explanation = f"Selected column '{chosen}' ({chosen_lineage.clarification_label})."

    return {
        "resolved": True,
        "column": chosen,
        "confidence": top_score,
        "candidates": candidates,
        "is_ambiguous": False,
        "clarification_options": [],
        "clarification_candidates": [],
        "selection_explanation": explanation,
    }
