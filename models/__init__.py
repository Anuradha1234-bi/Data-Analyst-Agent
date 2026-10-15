"""Data models package for AI Data Analyst Agent."""

from .relationship import Relationship, JoinAudit
from .dataset_metadata import DatasetMetadata
from .anomaly import (
    IQROutlierColumnResult,
    IQRAnalysisResult,
    IsolationForestResult,
    DeepStatisticalMetric,
    DeepStatisticalResult,
    MultivariateAnomalyRecord,
    MultivariateAnalysisResult,
    AnomalyTreatmentSummary,
    ZScoreColumnResult,
    ZScoreAnalysisResult,
    RobustZScoreColumnResult,
    RobustZScoreAnalysisResult,
    SingleAnomalyRecord,
    CombinedAnomalyResult,
    AnomalySummary,
    AnomalyExplanation,
)

__all__ = [
    "Relationship",
    "JoinAudit",
    "DatasetMetadata",
    "IQROutlierColumnResult",
    "IQRAnalysisResult",
    "IsolationForestResult",
    "DeepStatisticalMetric",
    "DeepStatisticalResult",
    "MultivariateAnomalyRecord",
    "MultivariateAnalysisResult",
    "AnomalyTreatmentSummary",
    "ZScoreColumnResult",
    "ZScoreAnalysisResult",
    "RobustZScoreColumnResult",
    "RobustZScoreAnalysisResult",
    "SingleAnomalyRecord",
    "CombinedAnomalyResult",
    "AnomalySummary",
    "AnomalyExplanation",
    "Insight",
    "TrendAnalysisResult",
    "TopBottomCategoryResult",
    "DistributionAnalysisResult",
    "CorrelationPair",
    "CorrelationAnalysisResult",
    "CategoryBreakdownItem",
    "CategoryBreakdownResult",
    "CrossDatasetInsightResult",
    "DatasetAnalysisResult",
    "PredictionMode",
    "ProblemType",
    "TargetRecommendation",
    "DateColumnInfo",
    "SuitabilityReport",
    "LeakageReport",
    "ModelEvaluationMetrics",
    "ModelCandidateResult",
    "PredictionPoint",
    "FeatureImportanceItem",
    "PredictionResult",
]

from .insight import (
    Insight,
    TrendAnalysisResult,
    TopBottomCategoryResult,
    DistributionAnalysisResult,
    CorrelationPair,
    CorrelationAnalysisResult,
    CategoryBreakdownItem,
    CategoryBreakdownResult,
    CrossDatasetInsightResult,
    DatasetAnalysisResult,
)

from .prediction import (
    PredictionMode,
    ProblemType,
    TargetRecommendation,
    DateColumnInfo,
    SuitabilityReport,
    LeakageReport,
    ModelEvaluationMetrics,
    ModelCandidateResult,
    PredictionPoint,
    FeatureImportanceItem,
    PredictionResult,
)

from .report import (
    DatasetInfoSection,
    ColumnProfileItem,
    DataProfileSection,
    CleaningSection,
    AnomalyMethodResult,
    AnomalySection,
    PredictionSection,
    ForecastSection,
    AskAnalystQueryItem,
    AskAnalystSection,
    UnifiedReport,
)



