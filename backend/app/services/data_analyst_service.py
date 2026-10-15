"""Data Analyst Service - Safe Natural Language Data Analysis.

Translates user questions into validated deterministic analytical routines.
Traceable evidence, strict read-only execution, schema validation, and visualization generation.
"""

import os
import json
import time
import math
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.dataset import Dataset
from app.models.user import User
from app.models.analysis_history import AnalysisHistory
from app.schemas.analyst import (
    AnalysisAskRequest,
    AnalysisAskResponse,
    AnalysisResultItem,
    ChartData,
    SuggestedQuestionItem,
    SuggestedQuestionsResponse,
    AnalysisHistoryItem,
    AnalysisHistoryListResponse,
)
from utils.file_loader import FileLoader
from query.orchestrator import run_ask_analyst_query
from query.context_manager import ConversationContextManager
from services.relationship_detector import RelationshipDetector


def _sanitize_for_json(val: Any) -> Any:
    """Sanitize float values such as NaN and Infinity for valid JSON serialization."""
    if val is None:
        return None
    if isinstance(val, (float, np.floating)):
        if math.isnan(val) or np.isnan(val):
            return None
        if math.isinf(val) or np.isinf(val):
            return "Infinity" if val > 0 else "-Infinity"
        return round(float(val), 4)
    if isinstance(val, (np.integer, int)):
        return int(val)
    if isinstance(val, (datetime, pd.Timestamp)):
        return val.isoformat()
    return str(val) if not isinstance(val, (bool, str, list, dict)) else val


class DataAnalystService:
    """Service orchestrating natural language analytical queries, suggested questions, and history."""

    # In-memory DataFrame cache: key = file_path, value = (mtime, size, df)
    _df_cache: Dict[str, Tuple[float, int, pd.DataFrame]] = {}

    @classmethod
    def _get_cached_or_load_df(cls, active_filepath: Path, filename: str) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
        """Retrieve cached DataFrame or safely load with mtime & size invalidation."""
        file_path_str = str(active_filepath.resolve())
        stat = active_filepath.stat()
        mtime = stat.st_mtime
        size = stat.st_size

        cached = cls._df_cache.get(file_path_str)
        if cached:
            c_mtime, c_size, c_df = cached
            if c_mtime == mtime and c_size == size:
                return c_df.copy(), None

        load_res = FileLoader.load_file(
            file_obj=file_path_str,
            filename=filename,
            file_size_bytes=size,
        )
        if not load_res.success or load_res.df is None or load_res.df.empty:
            return None, load_res.error_message or f"Dataset '{filename}' is empty or unreadable."

        if len(cls._df_cache) >= 16:
            cls._df_cache.pop(next(iter(cls._df_cache)))

        cls._df_cache[file_path_str] = (mtime, size, load_res.df.copy())
        return load_res.df, None

    @classmethod
    def ask_question(
        cls,
        request: AnalysisAskRequest,
        current_user: User,
        db: Session,
    ) -> AnalysisAskResponse:
        """Process a natural language analytical question against a selected dataset and version."""
        start_time = time.time()
        warnings: List[str] = []
        errors: List[str] = []

        # 1. Fetch and validate dataset ownership
        dataset = (
            db.query(Dataset)
            .filter(Dataset.id == request.dataset_id, Dataset.user_id == current_user.id)
            .first()
        )
        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataset #{request.dataset_id} not found or access denied.",
            )

        # 2. Determine file path based on requested version (Original vs Cleaned)
        use_version = (request.version or "original").lower().strip()
        active_filepath: Path
        actual_version_used = "original"

        if use_version == "cleaned":
            if dataset.has_cleaned and dataset.cleaned_file_path:
                cleaned_p = Path(dataset.cleaned_file_path)
                if cleaned_p.exists() and cleaned_p.is_file():
                    active_filepath = cleaned_p
                    actual_version_used = "cleaned"
                else:
                    active_filepath = Path(dataset.file_path)
                    warnings.append("Cleaned file was missing on disk; fell back to original dataset version.")
            else:
                active_filepath = Path(dataset.file_path)
                warnings.append("No cleaned version exists for this dataset; analyzed original dataset version.")
        else:
            active_filepath = Path(dataset.file_path)

        if not active_filepath.exists() or not active_filepath.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataset file '{dataset.filename}' is missing from physical storage.",
            )

        # 3. Read dataset into Pandas DataFrame (with in-memory cache)
        df, load_err = cls._get_cached_or_load_df(active_filepath, dataset.filename)
        if df is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=load_err or f"Dataset '{dataset.filename}' is empty or unreadable.",
            )

        ds_name = dataset.original_filename or dataset.filename or f"dataset_{dataset.id}"

        # 4. Extract schema metadata and verified join history
        join_history = []
        try:
            join_records = (
                db.query(AnalysisHistory)
                .filter(
                    AnalysisHistory.dataset_id == dataset.id,
                    AnalysisHistory.analysis_type == "dataset_join",
                )
                .all()
            )
            for jr in join_records:
                if jr.result_json:
                    jdata = json.loads(jr.result_json) if isinstance(jr.result_json, str) else jr.result_json
                    join_history.append(jdata)
        except Exception:
            pass

        meta_dict = {
            "column_names": [str(c) for c in df.columns],
            "data_types": {str(c): str(df[c].dtype) for c in df.columns},
            "rows": int(len(df)),
            "columns": int(len(df.columns)),
            "join_history": join_history,
        }

        # 5. Check if user has other datasets for potential cross-dataset queries
        other_datasets = (
            db.query(Dataset)
            .filter(Dataset.user_id == current_user.id, Dataset.id != dataset.id)
            .all()
        )
        datasets_dict = {ds_name: df}
        meta_dict_all = {ds_name: meta_dict}

        # Add other user datasets (read-only for cross-dataset referencing if needed)
        for od in other_datasets[:3]:
            od_path = Path(od.file_path)
            if od_path.exists():
                od_load = FileLoader.load_file(str(od_path), od.filename, od.file_size_bytes or 0)
                if od_load.success and od_load.df is not None:
                    o_name = od.original_filename or od.filename or f"dataset_{od.id}"
                    datasets_dict[o_name] = od_load.df
                    meta_dict_all[o_name] = {
                        "column_names": [str(c) for c in od_load.df.columns],
                        "data_types": {str(c): str(od_load.df[c].dtype) for c in od_load.df.columns},
                    }

        # 6. Resolve conversation session context
        session_ctx = request.context
        if not session_ctx:
            session_ctx = ConversationContextManager.get_context(current_user.id, dataset.id, actual_version_used)

        # Execute through Query Orchestrator
        try:
            orch_resp = run_ask_analyst_query(
                question=request.question,
                datasets=datasets_dict,
                metadata=meta_dict_all,
                context=session_ctx,
            )
        except Exception as e:
            errors.append(f"Query execution error: {str(e)}")
            orch_resp = {
                "status": "error",
                "question": request.question,
                "answer": {"answer": f"An error occurred while analyzing the question: {str(e)}"},
                "errors": errors,
            }

        warnings.extend(orch_resp.get("warnings", []))
        errors.extend(orch_resp.get("errors", []))

        # 7. Format structured result data
        res_payload = orch_resp.get("result", {})
        result_item: Optional[AnalysisResultItem] = None

        if res_payload:
            raw_data = res_payload.get("data")
            if isinstance(raw_data, pd.DataFrame) and not raw_data.empty:
                cols = [str(c) for c in raw_data.columns]
                # Limit to 100 rows for response payload
                head_df = raw_data.head(100)
                rows = []
                for _, r in head_df.iterrows():
                    row_dict = {str(k): _sanitize_for_json(v) for k, v in r.items()}
                    rows.append(row_dict)
                result_item = AnalysisResultItem(
                    columns=cols,
                    rows=rows,
                    total_rows=int(len(raw_data)),
                    result_type=res_payload.get("result_type", "table"),
                )
            elif isinstance(raw_data, (dict, list)):
                result_item = AnalysisResultItem(
                    columns=list(raw_data.keys()) if isinstance(raw_data, dict) else [],
                    rows=[raw_data] if isinstance(raw_data, dict) else raw_data,
                    total_rows=1 if isinstance(raw_data, dict) else len(raw_data),
                    result_type="scalar",
                )
            elif raw_data is not None:
                # Single scalar
                result_item = AnalysisResultItem(
                    columns=["Metric"],
                    rows=[{"Metric": _sanitize_for_json(raw_data)}],
                    total_rows=1,
                    result_type="scalar",
                )

        # 8. Format structured visualization specification
        vis_payload = orch_resp.get("visualization", {})
        chart_data: Optional[ChartData] = None

        if vis_payload and vis_payload.get("recommended"):
            chart_type = vis_payload.get("chart_type", "bar")
            x_col = vis_payload.get("x")
            y_col = vis_payload.get("y")
            title = f"{chart_type.capitalize()} Chart: {request.question}"

            # Extract data points for native frontend chart rendering
            data_points: List[Dict[str, Any]] = []
            if result_item and result_item.rows and x_col:
                for row in result_item.rows[:30]:  # Limit to 30 bars/points
                    x_val = row.get(x_col)
                    y_val = row.get(y_col) if y_col else row.get(result_item.columns[1] if len(result_item.columns) > 1 else x_col)
                    try:
                        num_y = float(y_val) if y_val is not None else 0.0
                    except (ValueError, TypeError):
                        num_y = 0.0

                    data_points.append({
                        "label": str(x_val if x_val is not None else ""),
                        "value": round(num_y, 2),
                    })

            chart_data = ChartData(
                recommended=True,
                chart_type=chart_type,
                title=title,
                x_axis=str(x_col),
                y_axis=str(y_col) if y_col else "",
                data_points=data_points,
                reason=vis_payload.get("reason"),
            )

        # 9. Extract answer components
        answer_block = orch_resp.get("answer", {})
        if isinstance(answer_block, dict):
            final_answer = answer_block.get("answer", "No textual answer could be generated.")
            key_points = answer_block.get("key_points", [])
            evidence = answer_block.get("evidence", [])
            limitations = answer_block.get("limitations", [])
            confidence = answer_block.get("confidence", "High")
        else:
            final_answer = str(answer_block)
            key_points = []
            evidence = []
            limitations = []
            confidence = "High"

        # Evidence dictionary
        evidence_dict = orch_resp.get("evidence", {})
        if isinstance(evidence_dict, dict):
            evidence_clean = {k: _sanitize_for_json(v) for k, v in evidence_dict.items()}
        else:
            evidence_clean = {"raw": str(evidence_dict)}

        if evidence and isinstance(evidence, list):
            evidence_clean["key_findings"] = evidence

        # Clarification handling
        clarification_q = None
        clarification_opts = []
        clarification_cands = []
        op_status = orch_resp.get("status", "success")

        if op_status == "needs_clarification":
            validation_blk = orch_resp.get("validation", {})
            clarification_q = validation_blk.get("clarification_question") or orch_resp.get("query_plan", {}).get("clarification_question")
            clarification_opts = validation_blk.get("clarification_options") or orch_resp.get("query_plan", {}).get("clarification_options", [])
            clarification_cands = (
                orch_resp.get("clarification_candidates")
                or validation_blk.get("clarification_candidates")
                or orch_resp.get("query_plan", {}).get("metadata", {}).get("clarification_candidates", [])
            )

        selection_explanation = (
            orch_resp.get("query_plan", {}).get("metadata", {}).get("selection_explanation")
            or evidence_clean.get("selection_explanation")
        )

        # 10. Update Conversational Memory Context
        extracted_entities = []
        if result_item and result_item.rows and len(result_item.columns) > 0:
            first_col = result_item.columns[0]
            extracted_entities = [str(r.get(first_col)) for r in result_item.rows[:10] if r.get(first_col) is not None]

        ConversationContextManager.update_context(
            user_id=current_user.id,
            dataset_id=dataset.id,
            version=actual_version_used,
            question=request.question,
            plan=orch_resp.get("query_plan", {}),
            result_payload=res_payload,
            entities=extracted_entities,
        )

        # 11. Extract Advanced Statistical Metrics & Insights
        automated_insights = evidence_clean.get("automated_insights") or orch_resp.get("result", {}).get("evidence", {}).get("automated_insights", [])
        engine_label = res_payload.get("engine", "Pandas & SciPy Statistical Engine")
        llm_prov = orch_resp.get("provider", "Deterministic Semantic Engine")

        raw_ev = evidence_clean.get("raw_evidence", {}) if isinstance(evidence_clean.get("raw_evidence"), dict) else {}
        reg_details = evidence_clean.get("regression_details") or raw_ev.get("regression_details")
        test_details = evidence_clean.get("test_details") or raw_ev.get("test_details")
        chi_details = evidence_clean.get("chi_details") or raw_ev.get("chi_details")

        stats_metrics = {}
        if reg_details:
            stats_metrics["regression"] = reg_details
            # Attach trendline points to scatter chart
            if chart_data and chart_data.chart_type == "scatter":
                chart_data.trendline = reg_details.get("line_points")
        if test_details:
            stats_metrics["hypothesis_test"] = test_details
        if chi_details:
            stats_metrics["chi_square"] = chi_details

        # 12. Synthesize Contextual Follow-Up Suggestions
        follow_ups = []
        intent_code = str(orch_resp.get("query_plan", {}).get("intent", "")).upper()
        if intent_code in ("TOP_N", "BOTTOM_N"):
            follow_ups = [
                "Now show only the top 5",
                "Compare their monthly trends over time",
                "What is the average modal price?",
            ]
        elif intent_code in ("AVERAGE", "SUM", "COUNT"):
            follow_ups = [
                "Which category has the highest average?",
                "Show the trend over time",
                "Which numerical columns have the strongest correlation?",
            ]
        elif intent_code in ("TREND", "DATE_RANGE"):
            follow_ups = [
                "Run a linear regression on this trend",
                "Are there unusual outliers or peaks?",
                "Summarize the important findings in this dataset",
            ]
        elif intent_code == "CORRELATION":
            follow_ups = [
                "Run a linear regression between the strongest pair",
                "Show a scatter plot of these features",
                "Which categories have unusual values?",
            ]
        elif intent_code == "REGRESSION":
            follow_ups = [
                "Are there unusual outliers in this model?",
                "What is the average of the predictor variable?",
                "Which products have the highest values?",
            ]
        else:
            follow_ups = [
                "Summarize the important findings in this dataset",
                "Which columns have missing values?",
                "Which product or category has the highest revenue?",
            ]

        exec_duration = round((time.time() - start_time) * 1000.0, 2)

        # 13. Persist to AnalysisHistory audit trail
        try:
            hist_entry = AnalysisHistory(
                user_id=current_user.id,
                dataset_id=dataset.id,
                dataset_name=ds_name,
                query=request.question,
                analysis_type=orch_resp.get("intent", {}).get("intent", "general"),
                status=op_status,
                result_json=json.dumps({
                    "answer": final_answer,
                    "version": actual_version_used,
                    "has_chart": bool(chart_data and chart_data.recommended),
                    "chart_type": chart_data.chart_type if chart_data else None,
                    "row_count": result_item.total_rows if result_item else 0,
                    "engine": engine_label,
                    "provider": llm_prov,
                    "duration_ms": exec_duration,
                }),
            )
            db.add(hist_entry)
            db.commit()
        except Exception:
            db.rollback()

        plan_obj = orch_resp.get("query_plan", {})
        used_cols = []
        if plan_obj.get("column"):
            used_cols.append(plan_obj["column"])
        for gc in plan_obj.get("group_by", []):
            if gc and gc not in used_cols:
                used_cols.append(gc)
        if plan_obj.get("date_column") and plan_obj["date_column"] not in used_cols:
            used_cols.append(plan_obj["date_column"])

        op_name = plan_obj.get("intent") or orch_resp.get("intent", {}).get("intent", "Analysis")
        op_display = op_name.replace("_", " ").title() if op_name else "Analysis"
        interp_q = orch_resp.get("question") or request.question
        if used_cols:
            interp_q = f"{op_display} of {', '.join(used_cols)} in {ds_name}"

        return AnalysisAskResponse(
            status=op_status,
            question=request.question,
            interpreted_question=interp_q,
            dataset_id=dataset.id,
            dataset_name=ds_name,
            dataset_version=actual_version_used,
            operation_performed=op_display,
            columns_used=used_cols,
            filters_applied=plan_obj.get("filters", []),
            assumptions_applied=limitations,
            answer=final_answer,
            key_points=key_points,
            evidence=evidence_clean,
            limitations=limitations,
            confidence=confidence,
            execution_engine=engine_label,
            llm_provider=llm_prov,
            automated_insights=automated_insights,
            statistical_metrics=stats_metrics or None,
            follow_up_suggestions=follow_ups,
            result=result_item,
            visualization=chart_data,
            clarification_question=clarification_q,
            clarification_options=clarification_opts,
            clarification_candidates=clarification_cands,
            selection_explanation=selection_explanation,
            warnings=warnings,
            errors=errors,
            execution_time_ms=exec_duration,
        )

    @classmethod
    def get_suggested_questions(
        cls,
        dataset_id: int,
        current_user: User,
        db: Session,
    ) -> SuggestedQuestionsResponse:
        """Synthesize contextual questions based on the dataset's actual columns and types."""
        dataset = (
            db.query(Dataset)
            .filter(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
            .first()
        )
        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dataset not found or access denied.",
            )

        ds_name = dataset.original_filename or dataset.filename
        file_p = Path(dataset.file_path)
        if not file_p.exists():
            return SuggestedQuestionsResponse(
                dataset_id=dataset.id,
                dataset_name=ds_name,
                questions=[],
            )

        df, load_err = cls._get_cached_or_load_df(file_p, dataset.filename)
        if df is None or df.empty:
            return SuggestedQuestionsResponse(
                dataset_id=dataset.id,
                dataset_name=ds_name,
                questions=[],
            )

        # Fetch verified join history if available
        join_history = []
        try:
            join_records = (
                db.query(AnalysisHistory)
                .filter(
                    AnalysisHistory.dataset_id == dataset.id,
                    AnalysisHistory.analysis_type == "dataset_join",
                )
                .all()
            )
            for jr in join_records:
                if jr.result_json:
                    jdata = json.loads(jr.result_json) if isinstance(jr.result_json, str) else jr.result_json
                    join_history.append(jdata)
        except Exception:
            pass

        from query.column_lineage import inspect_column_lineage
        from query.column_resolver import filter_metadata_columns, is_metadata_column
        lineage_map = inspect_column_lineage(df.columns, {"join_history": join_history})

        raw_numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        raw_categorical_cols = [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c]) and not pd.api.types.is_datetime64_any_dtype(df[c])]
        date_cols = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c]) or "date" in str(c).lower() or "time" in str(c).lower()]

        # Filter out join-generated suffixed duplicates to suggest clean, unambiguous questions
        clean_numeric_cols = [c for c in raw_numeric_cols if not (lineage_map.get(str(c)) and lineage_map[str(c)].is_join_generated)]
        numeric_cols = clean_numeric_cols if clean_numeric_cols else raw_numeric_cols

        # Separate domain numerical metrics from extraction/system metadata
        domain_numeric_cols = filter_metadata_columns(numeric_cols)
        metadata_numeric_cols = [c for c in numeric_cols if is_metadata_column(str(c))]

        clean_cat_cols = [c for c in raw_categorical_cols if not (lineage_map.get(str(c)) and lineage_map[str(c)].is_join_generated)]
        categorical_cols = clean_cat_cols if clean_cat_cols else raw_categorical_cols
        domain_cat_cols = [c for c in categorical_cols if not is_metadata_column(str(c))]

        questions: List[SuggestedQuestionItem] = []

        # 1. High-level Overview
        questions.append(
            SuggestedQuestionItem(
                category="Overview",
                question="How many total records and features are in this dataset?",
                description="General structural breakdown and volume count.",
            )
        )

        # 2. Missing values & hygiene
        questions.append(
            SuggestedQuestionItem(
                category="Data Quality",
                question="Which columns have missing or null values?",
                description="Completeness and data hygiene assessment.",
            )
        )

        # 3. Numeric descriptive statistics (Average, Max) - Domain Metrics Only
        if domain_numeric_cols:
            primary_num = domain_numeric_cols[0]
            # Prioritize columns with meaningful monetary or measurement names
            sales_candidates = [c for c in domain_numeric_cols if any(k in str(c).lower() for k in ["price", "sales", "revenue", "amount", "salary", "cost", "total"])]
            if sales_candidates:
                primary_num = sales_candidates[0]

            clean_num_name = str(primary_num).replace("_", " ")
            questions.append(
                SuggestedQuestionItem(
                    category="Descriptive Statistics",
                    question=f"What is the average {clean_num_name}?",
                    description=f"Calculates mean, median, min, and max for {clean_num_name}.",
                )
            )
            questions.append(
                SuggestedQuestionItem(
                    category="Descriptive Statistics",
                    question=f"What is the maximum {clean_num_name} and which record has it?",
                    description=f"Finds peak value and highest ranked observation for {clean_num_name}.",
                )
            )
        elif metadata_numeric_cols:
            # Metadata-only dataset (e.g. OCR text extraction): suggest structural inspection
            questions.append(
                SuggestedQuestionItem(
                    category="Extraction Overview",
                    question="How many distinct pages and text lines were extracted?",
                    description="Inspects document layout volume across extracted pages.",
                )
            )

        # 4. Grouping & Ranking (Category + Domain Numeric)
        if domain_cat_cols and domain_numeric_cols:
            primary_cat = domain_cat_cols[0]
            cat_candidates = [c for c in domain_cat_cols if any(k in str(c).lower() for k in ["product", "category", "region", "market", "customer", "department", "city", "country"])]
            if cat_candidates:
                primary_cat = cat_candidates[0]

            clean_cat_name = str(primary_cat).replace("_", " ")
            clean_num_name = str(domain_numeric_cols[0]).replace("_", " ")

            questions.append(
                SuggestedQuestionItem(
                    category="Grouping & Ranking",
                    question=f"Which {clean_cat_name} has the highest average {clean_num_name}?",
                    description=f"Aggregates {clean_num_name} by {clean_cat_name} and sorts highest to lowest.",
                )
            )
            questions.append(
                SuggestedQuestionItem(
                    category="Grouping & Ranking",
                    question=f"Show the top 5 {clean_cat_name}s by total {clean_num_name}.",
                    description=f"Ranks top categories and generates a comparison bar chart.",
                )
            )
        elif categorical_cols:
            clean_cat = str(categorical_cols[0]).replace("_", " ")
            questions.append(
                SuggestedQuestionItem(
                    category="Distribution",
                    question=f"What are the most frequent values in {clean_cat}?",
                    description=f"Frequency counts and percentages for {clean_cat}.",
                )
            )

        # 5. Trend Analysis (if Date Column and Domain Numeric exist)
        if date_cols and domain_numeric_cols:
            clean_date = str(date_cols[0]).replace("_", " ")
            clean_num = str(domain_numeric_cols[0]).replace("_", " ")
            questions.append(
                SuggestedQuestionItem(
                    category="Trend Analysis",
                    question=f"Show the trend of {clean_num} over {clean_date}.",
                    description=f"Chronological trajectory and line chart visualization.",
                )
            )

        # 6. Correlation (if >= 2 domain numeric columns exist)
        if len(domain_numeric_cols) >= 2:
            questions.append(
                SuggestedQuestionItem(
                    category="Relationships",
                    question="Which numerical columns have the strongest correlation?",
                    description="Computes Pearson correlation coefficient with causation safeguards.",
                )
            )

        return SuggestedQuestionsResponse(
            dataset_id=dataset.id,
            dataset_name=ds_name,
            questions=questions[:8],
        )

    @classmethod
    def get_query_history(
        cls,
        dataset_id: Optional[int],
        limit: int = 50,
        current_user: Optional[User] = None,
        db: Optional[Session] = None,
    ) -> AnalysisHistoryListResponse:
        """Fetch audit trail of previous analytical queries for user and dataset."""
        if not current_user or not db:
            return AnalysisHistoryListResponse(history=[], total_count=0)

        query = db.query(AnalysisHistory).filter(AnalysisHistory.user_id == current_user.id)
        if dataset_id:
            query = query.filter(AnalysisHistory.dataset_id == dataset_id)

        records = query.order_by(AnalysisHistory.created_at.desc()).limit(limit).all()

        items: List[AnalysisHistoryItem] = []
        for r in records:
            ans_preview = None
            has_chart = False
            parsed_data = None
            if r.result_json:
                try:
                    parsed = json.loads(r.result_json)
                    ans_preview = parsed.get("answer")
                    has_chart = bool(parsed.get("has_chart", False))
                    parsed_data = parsed
                except Exception:
                    ans_preview = r.result_json[:120]

            created_str = r.created_at.isoformat() if r.created_at else ""
            items.append(
                AnalysisHistoryItem(
                    id=r.id,
                    dataset_id=r.dataset_id,
                    dataset_name=r.dataset_name,
                    query=r.query,
                    analysis_type=r.analysis_type,
                    status=r.status,
                    answer_preview=ans_preview[:160] if ans_preview else None,
                    has_chart=has_chart,
                    created_at=created_str,
                    result_data=parsed_data,
                )
            )

        return AnalysisHistoryListResponse(
            history=items,
            total_count=len(items),
        )

    @classmethod
    def delete_history_item(
        cls,
        history_id: int,
        current_user: User,
        db: Session,
    ) -> Dict[str, Any]:
        """Delete a single query history record."""
        entry = (
            db.query(AnalysisHistory)
            .filter(AnalysisHistory.id == history_id, AnalysisHistory.user_id == current_user.id)
            .first()
        )
        if not entry:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="History entry not found.")

        db.delete(entry)
        db.commit()
        return {"success": True, "message": "History entry removed."}

    @classmethod
    def clear_history(
        cls,
        dataset_id: Optional[int],
        current_user: User,
        db: Session,
    ) -> Dict[str, Any]:
        """Clear analytical query history for the user, optionally scoped to a dataset."""
        query = db.query(AnalysisHistory).filter(AnalysisHistory.user_id == current_user.id)
        if dataset_id:
            query = query.filter(AnalysisHistory.dataset_id == dataset_id)

        deleted_count = query.delete(synchronize_session=False)
        db.commit()
        return {"success": True, "deleted_count": deleted_count, "message": "Query history cleared."}
