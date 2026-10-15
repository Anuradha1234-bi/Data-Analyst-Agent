"""Analytics Router - Interactive Exploratory and Statistical Analytics Endpoints.

Provides RESTful endpoints for dataset-grounded KPIs, multidimensional aggregations,
time-series trend comparisons with causal caveats, correlation matrices,
IQR outlier detection, automated insights, and data exports.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.database import get_db
from app.auth.dependencies import get_current_user
from app.schemas.analytics import (
    AnalyticsOverviewResponse,
    AnalyticsChartRequest,
    AnalyticsChartResponse,
    AnalyticsTrendRequest,
    AnalyticsTrendResponse,
    AnalyticsGroupCompareRequest,
    AnalyticsGroupCompareResponse,
    AnalyticsStatsRequest,
    AnalyticsStatsResponse,
    AnalyticsInsightsResponse,
    AnalyticsExportCSVRequest,
    AnalyticsReportExportRequest,
)
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/status")
def analytics_status(current_user: User = Depends(get_current_user)):
    """Check readiness of the analytics engine."""
    return {"status": "ready", "module": "analytics"}


@router.get("/overview/{dataset_id}", response_model=AnalyticsOverviewResponse)
def get_analytics_overview(
    dataset_id: int,
    version: str = Query("original", description="Dataset version: 'original' or 'cleaned'"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve dynamic KPIs and column profiling summaries computed from actual dataset schema."""
    return AnalyticsService.get_analytics_overview(
        dataset_id=dataset_id,
        version=version,
        current_user=current_user,
        db=db,
    )


@router.post("/chart", response_model=AnalyticsChartResponse)
def generate_chart(
    request: AnalyticsChartRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate dynamic chart points, matching data table, and statistical distributions with filters."""
    return AnalyticsService.generate_chart(
        request=request,
        current_user=current_user,
        db=db,
    )


@router.post("/trend", response_model=AnalyticsTrendResponse)
def analyze_trend(
    request: AnalyticsTrendRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Execute time-series trend analysis, period-over-period comparison, and causal caveats."""
    return AnalyticsService.analyze_trend(
        request=request,
        current_user=current_user,
        db=db,
    )


@router.post("/group-compare", response_model=AnalyticsGroupCompareResponse)
def group_compare(
    request: AnalyticsGroupCompareRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Multidimensional grouping and aggregated comparative evaluation."""
    return AnalyticsService.group_compare(
        request=request,
        current_user=current_user,
        db=db,
    )


@router.post("/stats", response_model=AnalyticsStatsResponse)
def get_deep_statistics(
    request: AnalyticsStatsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Calculate comprehensive descriptive statistics, Pearson correlation matrix, and IQR outliers."""
    return AnalyticsService.deep_stats(
        request=request,
        current_user=current_user,
        db=db,
    )


@router.get("/insights/{dataset_id}", response_model=AnalyticsInsightsResponse)
def get_automated_insights(
    dataset_id: int,
    version: str = Query("original", description="Dataset version: 'original' or 'cleaned'"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Extract automated, evidence-grounded observations and warnings from actual dataset."""
    return AnalyticsService.generate_insights(
        dataset_id=dataset_id,
        version=version,
        current_user=current_user,
        db=db,
    )


@router.post("/export/csv")
def export_analytics_csv(
    request: AnalyticsExportCSVRequest,
    current_user: User = Depends(get_current_user),
):
    """Export tabular analytics results as CSV with UTF-8 BOM."""
    return AnalyticsService.export_csv_stream(request)


@router.post("/export/report")
def export_analytics_report(
    request: AnalyticsReportExportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate structured executive summary report of dataset analytics."""
    return AnalyticsService.export_report_summary(
        request=request,
        current_user=current_user,
        db=db,
    )
