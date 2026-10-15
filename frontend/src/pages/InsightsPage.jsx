import React, { useState, useEffect, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Lightbulb,
  RefreshCw,
  Search,
  AlertTriangle,
  AlertCircle,
  Info,
  CheckCircle2,
  ChevronDown,
  Download,
  Database,
  Layers,
  Sparkles,
  ShieldAlert,
  ArrowUpRight,
  TrendingUp,
} from 'lucide-react';
import { datasetService } from '../services/datasetService';
import { analyticsService } from '../services/analyticsService';
import { extractErrorMessage } from '../services/api';

export const InsightsPage = () => {
  const [searchParams, setSearchParams] = useSearchParams();

  // Dataset states
  const [datasets, setDatasets] = useState([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState(null);
  const [selectedVersion, setSelectedVersion] = useState('original');
  const [loadingDatasets, setLoadingDatasets] = useState(true);

  // Insights data states
  const [insightsData, setInsightsData] = useState(null);
  const [loadingInsights, setLoadingInsights] = useState(false);
  const [insightsError, setInsightsError] = useState('');

  // UI Filter states
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const [severityFilter, setSeverityFilter] = useState('all');

  // 1. Fetch user's real datasets
  useEffect(() => {
    const fetchDatasets = async () => {
      setLoadingDatasets(true);
      try {
        const list = await datasetService.getDatasets();
        const validList = list || [];
        setDatasets(validList);

        const paramId = searchParams.get('dataset_id') || searchParams.get('id');
        const savedId = localStorage.getItem('selected_dataset_id');

        if (paramId && validList.some((d) => d.id === parseInt(paramId, 10))) {
          setSelectedDatasetId(parseInt(paramId, 10));
        } else if (savedId && validList.some((d) => d.id === parseInt(savedId, 10))) {
          setSelectedDatasetId(parseInt(savedId, 10));
        } else if (validList.length > 0) {
          setSelectedDatasetId(validList[0].id);
        }
      } catch (err) {
        setInsightsError(extractErrorMessage(err));
      } finally {
        setLoadingDatasets(false);
      }
    };
    fetchDatasets();
  }, [searchParams]);

  // Persist dataset selection to localStorage
  useEffect(() => {
    if (selectedDatasetId) {
      localStorage.setItem('selected_dataset_id', String(selectedDatasetId));
    }
  }, [selectedDatasetId]);

  // 2. Fetch insights when dataset or version changes
  const fetchInsights = async () => {
    if (!selectedDatasetId) {
      setInsightsData(null);
      return;
    }

    setLoadingInsights(true);
    setInsightsError('');
    try {
      const data = await analyticsService.getInsights(selectedDatasetId, selectedVersion);
      setInsightsData(data);
    } catch (err) {
      setInsightsError(extractErrorMessage(err));
      setInsightsData(null);
    } finally {
      setLoadingInsights(false);
    }
  };

  useEffect(() => {
    fetchInsights();
  }, [selectedDatasetId, selectedVersion]);

  // Selected dataset object helper
  const selectedDataset = useMemo(() => {
    return datasets.find((d) => d.id === selectedDatasetId) || null;
  }, [datasets, selectedDatasetId]);

  const hasCleanedVersion = Boolean(
    selectedDataset?.cleaned_filename || selectedDataset?.has_cleaned_version
  );

  // Filtered insights list
  const filteredInsights = useMemo(() => {
    if (!insightsData?.insights) return [];
    return insightsData.insights.filter((item) => {
      // Type filter
      if (typeFilter !== 'all' && item.type.toLowerCase() !== typeFilter.toLowerCase()) {
        return false;
      }
      // Severity filter
      if (severityFilter !== 'all' && item.severity.toLowerCase() !== severityFilter.toLowerCase()) {
        return false;
      }
      // Text search
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesTitle = item.title?.toLowerCase().includes(q);
        const matchesStatement = item.statement?.toLowerCase().includes(q);
        const matchesCols = item.columns_involved?.some((c) => c.toLowerCase().includes(q));
        if (!matchesTitle && !matchesStatement && !matchesCols) return false;
      }
      return true;
    });
  }, [insightsData, typeFilter, severityFilter, searchQuery]);

  // Export insights as Markdown report
  const handleExportMarkdown = () => {
    if (!insightsData || !insightsData.insights) return;
    const title = `# Automated Insights Report: ${insightsData.dataset_name || 'Dataset'}\n\n`;
    const meta = `*Generated on:* ${new Date().toLocaleString()}\n*Total Insights:* ${insightsData.insights.length}\n*Version:* ${insightsData.version || selectedVersion}\n\n---\n\n`;

    const body = insightsData.insights
      .map((ins, idx) => {
        return `### ${idx + 1}. ${ins.title}\n\n` +
          `- **Type:** ${ins.type}\n` +
          `- **Severity:** ${ins.severity}\n` +
          `- **Confidence:** ${ins.confidence}\n` +
          (ins.metric ? `- **Key Metric:** ${ins.metric}\n` : '') +
          `- **Columns Involved:** ${ins.columns_involved.join(', ')}\n\n` +
          `**Statement:** ${ins.statement}\n\n` +
          (ins.limitations ? `*Limitations / Caveats:* ${ins.limitations}\n\n` : '') +
          `---\n\n`;
      })
      .join('');

    const blob = new Blob([title + meta + body], { type: 'text/markdown;charset=utf-8;' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `insights_report_${insightsData.dataset_id}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  };

  // Helper styling for severity badges
  const getSeverityBadge = (severity) => {
    const s = (severity || '').toLowerCase();
    if (s === 'critical') {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-red-50 text-red-700 border border-red-200">
          <ShieldAlert className="w-3 h-3 text-red-600" />
          Critical
        </span>
      );
    }
    if (s === 'warning') {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
          <AlertTriangle className="w-3 h-3 text-amber-600" />
          Warning
        </span>
      );
    }
    if (s === 'positive') {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
          <CheckCircle2 className="w-3 h-3 text-emerald-600" />
          Positive
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-blue-50 text-blue-700 border border-blue-200">
        <Info className="w-3 h-3 text-blue-600" />
        Informational
      </span>
    );
  };

  // Helper styling for insight type tags
  const getTypeBadge = (type) => {
    const t = (type || '').toLowerCase();
    const colors = {
      concentration: 'bg-purple-50 text-purple-700 border-purple-200',
      correlation: 'bg-cyan-50 text-cyan-700 border-cyan-200',
      trend: 'bg-indigo-50 text-indigo-700 border-indigo-200',
      anomaly: 'bg-rose-50 text-rose-700 border-rose-200',
      distribution: 'bg-teal-50 text-teal-700 border-teal-200',
      general: 'bg-slate-50 text-slate-700 border-slate-200',
    };
    return (
      <span
        className={`px-2 py-0.5 rounded-md text-[11px] font-medium border uppercase tracking-wider ${
          colors[t] || colors.general
        }`}
      >
        {type}
      </span>
    );
  };

  return (
    <div className="space-y-6">
      {/* Top Header & Dataset Selection Bar */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-xs">
        <div>
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-xl bg-[#EFF6FF] text-[#2563EB]">
              <Lightbulb className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-[#0F172A]">Automated Insights</h1>
              <p className="text-xs text-[#64748B] mt-0.5">
                Autonomous dataset observations, category concentrations, distributions, and key drivers.
              </p>
            </div>
          </div>
        </div>

        {/* Dataset & Version Selectors */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Dataset Dropdown */}
          <div className="relative min-w-[240px]">
            <select
              value={selectedDatasetId || ''}
              onChange={(e) => {
                const id = parseInt(e.target.value, 10);
                setSelectedDatasetId(id);
                setSearchParams({ dataset_id: id }, { replace: true });
              }}
              disabled={loadingDatasets || datasets.length === 0}
              className="w-full appearance-none bg-[#F8FAFC] border border-[#CBD5E1] rounded-xl px-3.5 py-2 pr-9 text-xs font-semibold text-[#0F172A] focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20 cursor-pointer disabled:opacity-50"
            >
              {datasets.length === 0 ? (
                <option value="">No datasets available</option>
              ) : (
                datasets.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.original_filename || d.filename} (#{d.id})
                  </option>
                ))
              )}
            </select>
            <ChevronDown className="w-4 h-4 text-[#64748B] absolute right-3 top-2.5 pointer-events-none" />
          </div>

          {/* Cleaned vs Original Version Toggle */}
          {hasCleanedVersion && (
            <div className="flex items-center bg-[#F1F5F9] rounded-xl p-1 border border-[#E2E8F0] text-xs font-semibold">
              <button
                onClick={() => setSelectedVersion('original')}
                className={`px-3 py-1 rounded-lg transition-colors cursor-pointer ${
                  selectedVersion === 'original'
                    ? 'bg-white text-[#0F172A] shadow-xs'
                    : 'text-[#64748B] hover:text-[#0F172A]'
                }`}
              >
                Original
              </button>
              <button
                onClick={() => setSelectedVersion('cleaned')}
                className={`px-3 py-1 rounded-lg transition-colors cursor-pointer ${
                  selectedVersion === 'cleaned'
                    ? 'bg-[#2563EB] text-white shadow-xs'
                    : 'text-[#64748B] hover:text-[#0F172A]'
                }`}
              >
                Cleaned
              </button>
            </div>
          )}

          {/* Refresh Button */}
          <button
            onClick={fetchInsights}
            disabled={loadingInsights || !selectedDatasetId}
            className="p-2 border border-[#CBD5E1] rounded-xl hover:bg-[#F8FAFC] text-[#64748B] hover:text-[#0F172A] transition-colors cursor-pointer disabled:opacity-50"
            title="Refresh Insights"
          >
            <RefreshCw className={`w-4 h-4 ${loadingInsights ? 'animate-spin text-[#2563EB]' : ''}`} />
          </button>

          {/* Export Report */}
          <button
            onClick={handleExportMarkdown}
            disabled={!insightsData || !insightsData.insights || insightsData.insights.length === 0}
            className="flex items-center gap-1.5 px-3.5 py-2 bg-white border border-[#CBD5E1] hover:bg-[#F8FAFC] text-xs font-semibold text-[#0F172A] rounded-xl shadow-2xs transition-colors cursor-pointer disabled:opacity-40"
            title="Export Insights Summary as Markdown"
          >
            <Download className="w-3.5 h-3.5 text-[#64748B]" />
            <span>Export Report</span>
          </button>
        </div>
      </div>

      {/* Error Alert */}
      {insightsError && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs flex items-center justify-between shadow-xs">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0 text-red-600" />
            <span>{insightsError}</span>
          </div>
          <button
            onClick={fetchInsights}
            className="px-3 py-1 bg-white border border-red-300 rounded-lg text-red-700 hover:bg-red-50 font-semibold cursor-pointer"
          >
            Retry
          </button>
        </div>
      )}

      {/* Search & Filters Bar (shown when insights exist) */}
      {!loadingInsights && insightsData?.insights && insightsData.insights.length > 0 && (
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-white border border-[#E2E8F0] rounded-xl px-4 py-3 shadow-xs">
          {/* Search Input */}
          <div className="flex items-center gap-2 flex-1 w-full max-w-sm">
            <Search className="w-4 h-4 text-[#94A3B8] shrink-0" />
            <input
              type="text"
              placeholder="Search insights by title, column, or statement..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="text-xs text-[#0F172A] placeholder-[#94A3B8] focus:outline-none w-full bg-transparent"
            />
          </div>

          <div className="flex items-center gap-2.5 w-full sm:w-auto">
            {/* Type Filter */}
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="text-xs bg-[#F8FAFC] border border-[#CBD5E1] rounded-lg px-2.5 py-1.5 text-[#0F172A] font-medium cursor-pointer"
            >
              <option value="all">All Types</option>
              <option value="concentration">Concentration</option>
              <option value="correlation">Correlation</option>
              <option value="trend">Trend</option>
              <option value="anomaly">Anomaly</option>
              <option value="distribution">Distribution</option>
            </select>

            {/* Severity Filter */}
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="text-xs bg-[#F8FAFC] border border-[#CBD5E1] rounded-lg px-2.5 py-1.5 text-[#0F172A] font-medium cursor-pointer"
            >
              <option value="all">All Severities</option>
              <option value="critical">Critical</option>
              <option value="warning">Warning</option>
              <option value="informational">Informational</option>
              <option value="positive">Positive</option>
            </select>

            <span className="text-xs text-[#64748B] font-medium ml-1 whitespace-nowrap">
              {filteredInsights.length} of {insightsData.insights.length}
            </span>
          </div>
        </div>
      )}

      {/* Loading Skeleton */}
      {loadingInsights && (
        <div className="bg-white border border-[#E2E8F0] rounded-2xl p-16 text-center shadow-xs">
          <RefreshCw className="w-8 h-8 text-[#2563EB] animate-spin mx-auto mb-3" />
          <h3 className="text-sm font-semibold text-[#0F172A]">Synthesizing automated insights...</h3>
          <p className="text-xs text-[#64748B] mt-1">
            Analyzing distributions, key drivers, and statistical patterns across records.
          </p>
        </div>
      )}

      {/* Empty State: No Datasets */}
      {!loadingDatasets && datasets.length === 0 && (
        <div className="bg-white border border-[#E2E8F0] rounded-2xl p-14 text-center shadow-xs">
          <Database className="w-12 h-12 text-[#94A3B8] mx-auto mb-3" />
          <h3 className="text-sm font-bold text-[#0F172A]">No Datasets Available</h3>
          <p className="text-xs text-[#64748B] max-w-sm mx-auto mt-1">
            Please upload a dataset to generate automated insights and observations.
          </p>
        </div>
      )}

      {/* Empty State: No Insights for Dataset */}
      {!loadingInsights && selectedDatasetId && (!insightsData?.insights || insightsData.insights.length === 0) && !insightsError && (
        <div className="bg-white border border-[#E2E8F0] rounded-2xl p-14 text-center shadow-xs">
          <Sparkles className="w-12 h-12 text-[#94A3B8] mx-auto mb-3" />
          <h3 className="text-sm font-bold text-[#0F172A]">No Substantial Insights Detected</h3>
          <p className="text-xs text-[#64748B] max-w-sm mx-auto mt-1">
            All variables in this dataset appear normally balanced without critical class skew or correlations above baseline thresholds.
          </p>
        </div>
      )}

      {/* Insights Cards Grid */}
      {!loadingInsights && filteredInsights.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredInsights.map((insight) => (
            <div
              key={insight.id}
              className="bg-white border border-[#E2E8F0] hover:border-[#CBD5E1] rounded-2xl p-5 shadow-xs transition-all flex flex-col justify-between"
            >
              <div>
                {/* Header tags: Type, Severity, Confidence */}
                <div className="flex items-center justify-between gap-2 mb-3">
                  <div className="flex items-center gap-2">
                    {getTypeBadge(insight.type)}
                    {getSeverityBadge(insight.severity)}
                  </div>
                  <span className="text-[11px] font-medium text-[#64748B]">
                    {insight.confidence} Confidence
                  </span>
                </div>

                {/* Title */}
                <h3 className="text-sm font-bold text-[#0F172A] leading-snug">
                  {insight.title}
                </h3>

                {/* Metric callout if available */}
                {insight.metric && (
                  <div className="mt-2.5 inline-block px-2.5 py-1 rounded-lg bg-[#EFF6FF] text-[#1D4ED8] text-xs font-semibold">
                    {insight.metric}
                  </div>
                )}

                {/* Narrative Statement */}
                <p className="text-xs text-[#334155] mt-2.5 leading-relaxed">
                  {insight.statement}
                </p>

                {/* Limitations / Caveats Note */}
                {insight.limitations && (
                  <div className="mt-3 p-2.5 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0] text-[11px] text-[#64748B] flex items-start gap-1.5">
                    <Info className="w-3.5 h-3.5 text-[#94A3B8] shrink-0 mt-0.5" />
                    <span>{insight.limitations}</span>
                  </div>
                )}
              </div>

              {/* Columns involved footer */}
              {insight.columns_involved && insight.columns_involved.length > 0 && (
                <div className="mt-4 pt-3 border-t border-[#F1F5F9] flex items-center justify-between text-[11px]">
                  <span className="text-[#94A3B8] font-medium">Columns:</span>
                  <div className="flex flex-wrap gap-1">
                    {insight.columns_involved.map((col, idx) => (
                      <span
                        key={idx}
                        className="px-2 py-0.5 rounded bg-[#F1F5F9] text-[#475569] font-mono text-[10px]"
                      >
                        {col}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* No matching filter results */}
      {!loadingInsights && insightsData?.insights && insightsData.insights.length > 0 && filteredInsights.length === 0 && (
        <div className="bg-white border border-[#E2E8F0] rounded-2xl p-12 text-center shadow-xs">
          <p className="text-xs text-[#64748B]">No insights match your active search filters.</p>
          <button
            onClick={() => {
              setSearchQuery('');
              setTypeFilter('all');
              setSeverityFilter('all');
            }}
            className="mt-2 text-xs font-semibold text-[#2563EB] hover:underline cursor-pointer"
          >
            Reset Filters
          </button>
        </div>
      )}
    </div>
  );
};

export default InsightsPage;
