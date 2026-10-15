"""Pydantic schemas for Phase 8 Data Analyst Module (Natural Language Data Analysis)."""

from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field


class AnalysisAskRequest(BaseModel):
    """Request payload to ask a natural language analytical question."""
    dataset_id: int = Field(..., description="ID of the dataset to analyze.")
    question: str = Field(..., min_length=1, description="Natural language question.")
    version: Optional[str] = Field(
        default="original",
        description="Dataset version: 'original' or 'cleaned'."
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional conversation context for follow-up questions."
    )


class AnalysisResultItem(BaseModel):
    """Structured tabular result records and metadata."""
    columns: List[str] = Field(default_factory=list)
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    total_rows: int = 0
    result_type: str = "table"  # "table", "scalar", "empty"


class ChartData(BaseModel):
    """Structured visualization specification generated from real computed results."""
    recommended: bool = False
    chart_type: Optional[str] = None  # "bar", "line", "scatter", "histogram", "box", "heatmap"
    title: Optional[str] = None
    x_axis: Optional[str] = None
    y_axis: Optional[str] = None
    data_points: List[Dict[str, Any]] = Field(default_factory=list)
    trendline: Optional[List[Dict[str, Any]]] = None
    matrix: Optional[List[List[Optional[float]]]] = None
    categories: Optional[List[str]] = None
    reason: Optional[str] = None


class AnalysisAskResponse(BaseModel):
    """Comprehensive analytical response with answer, evidence, table, and visualization."""
    status: str = Field(
        ...,
        description="'success', 'needs_clarification', or 'error'"
    )
    question: str
    interpreted_question: Optional[str] = None
    dataset_id: int
    dataset_name: str
    dataset_version: str  # "original" or "cleaned"
    operation_performed: Optional[str] = None
    columns_used: List[str] = Field(default_factory=list)
    filters_applied: List[Dict[str, Any]] = Field(default_factory=list)
    assumptions_applied: List[str] = Field(default_factory=list)
    answer: str
    key_points: List[str] = Field(default_factory=list)
    evidence: Dict[str, Any] = Field(default_factory=dict)
    limitations: List[str] = Field(default_factory=list)
    confidence: str = "High"  # "High", "Medium", "Low"
    execution_engine: Optional[str] = "DuckDB / Pandas"
    llm_provider: Optional[str] = "Deterministic Semantic Engine"
    automated_insights: List[Dict[str, Any]] = Field(default_factory=list)
    statistical_metrics: Optional[Dict[str, Any]] = None
    follow_up_suggestions: List[str] = Field(default_factory=list)
    result: Optional[AnalysisResultItem] = None
    visualization: Optional[ChartData] = None
    clarification_question: Optional[str] = None
    clarification_options: List[str] = Field(default_factory=list)
    clarification_candidates: List[Dict[str, Any]] = Field(default_factory=list)
    selection_explanation: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    execution_time_ms: Optional[float] = None


class SuggestedQuestionItem(BaseModel):
    """Contextual suggested analytical question derived from real dataset schema."""
    category: str  # "Metric Summary", "Ranking", "Trend", "Correlation", "Data Quality"
    question: str
    description: Optional[str] = None


class SuggestedQuestionsResponse(BaseModel):
    """List of valid suggested questions for a specific dataset."""
    dataset_id: int
    dataset_name: str
    questions: List[SuggestedQuestionItem] = Field(default_factory=list)


class AnalysisHistoryItem(BaseModel):
    """Record of a previous analytical question and response."""
    id: int
    dataset_id: Optional[int] = None
    dataset_name: Optional[str] = None
    query: str
    analysis_type: str = "general"
    status: str = "completed"
    answer_preview: Optional[str] = None
    has_chart: bool = False
    created_at: str
    result_data: Optional[Dict[str, Any]] = None


class AnalysisHistoryListResponse(BaseModel):
    """List of analytical query history records for user."""
    history: List[AnalysisHistoryItem] = Field(default_factory=list)
    total_count: int = 0
