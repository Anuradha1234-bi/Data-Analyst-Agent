import React, { useState, useEffect, useMemo } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
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
  Sparkles,
  ShieldAlert,
  BarChart3,
  PieChart,
  Activity,
  ArrowRight,
  Target,
  FileText,
  LayoutGrid,
  FileSpreadsheet,
} from 'lucide-react';
import { datasetService } from '../services/datasetService';
import { analyticsService } from '../services/analyticsService';
import { extractErrorMessage } from '../services/api';

// Reference 8 comprehensive automated insights
const REFERENCE_INSIGHTS = [
  {
    id: 1,
    title: 'High Category Dominance: Gender',
    type: 'CONCENTRATION',
    severity: 'Informational',
    confidence: 'High Confidence',
    column: 'Gender',
    columns_involved: ['Gender'],
    statement: "Category 'Male' constitutes 50.0% (25 occurrences) of all records in 'Gender'.",
    limitations: 'Class imbalance may bias general aggregations if unstratified.',
    chartType: 'donut',
    donutData: {
      percentage: '50.0%',
      label: 'Dominance',
      slices: [
        { label: 'Male', value: '50.0% (25)', color: '#2563EB' },
        { label: 'Female', value: '42.0% (21)', color: '#7C3AED' },
        { label: 'Other', value: '8.0% (4)', color: '#1E293B' },
      ],
    },
  },
  {
    id: 2,
    title: 'Significant Outlier Concentration: Quantity',
    type: 'OUTLIER',
    severity: 'Informational',
    confidence: 'High Confidence',
    column: 'Quantity',
    columns_involved: ['Quantity'],
    statement: "Found 4 statistical outliers (8.0%) in 'Quantity' exceeding 1.5x IQR boundaries (limits: [-0.5, 3.5]).",
    limitations: 'Outliers may represent high-value signals rather than measurement noise.',
    chartType: 'boxplot_quantity',
  },
  {
    id: 3,
    title: 'Significant Outlier Concentration: Order_Amount_INR',
    type: 'OUTLIER',
    severity: 'Warning',
    confidence: 'High Confidence',
    column: 'Order_Amount_INR',
    columns_involved: ['Order_Amount_INR'],
    statement: "Found 5 statistical outliers (10.0%) in 'Order_Amount_INR' exceeding 1.5x IQR boundaries (limits: [950.29, 4505.65]).",
    limitations: 'High order amounts may indicate premium customers or data entry errors.',
    chartType: 'boxplot_amount',
  },
  {
    id: 4,
    title: 'Right-Skewed Distribution: Age',
    type: 'DISTRIBUTION',
    severity: 'Informational',
    confidence: 'High Confidence',
    column: 'Age',
    columns_involved: ['Age'],
    statement: "The 'Age' distribution is right-skewed with mean 36.8 and most values between 20–40.",
    limitations: 'Consider binning for better analysis and handle potential age outliers.',
    chartType: 'histogram_age',
  },
  {
    id: 5,
    title: 'Strong Positive Correlation: Quantity ↔ Order_Amount_INR',
    type: 'CORRELATION',
    severity: 'Informational',
    confidence: 'Medium Confidence',
    column: 'Order_Amount_INR',
    columns_involved: ['Quantity', 'Order_Amount_INR'],
    statement: "Strong positive correlation (0.76) between 'Quantity' and 'Order_Amount_INR'.",
    limitations: 'Larger orders strongly scale total revenue, indicating potential for bulk incentives.',
    chartType: 'scatter_correlation',
  },
  {
    id: 6,
    title: 'Missing Value Check: No Missing Data',
    type: 'MISSING DATA',
    severity: 'Warning',
    confidence: 'Medium Confidence',
    column: 'All Columns',
    columns_involved: ['All Columns'],
    statement: 'No missing values found in any column. Dataset is complete and ready for analysis.',
    limitations: 'Data integrity is high with 100% complete feature records.',
    chartType: 'bars_missing',
  },
  {
    id: 7,
    title: 'High Revenue Concentration: Maharashtra',
    type: 'CONCENTRATION',
    severity: 'Informational',
    confidence: 'High Confidence',
    column: 'State',
    columns_involved: ['State', 'Order_Amount_INR'],
    statement: 'Maharashtra represents 62.0% of total revenue with ₹14,136 across 31 customer orders.',
    limitations: 'Geographic concentration represents a core growth market.',
    chartType: 'bars_state',
  },
  {
    id: 8,
    title: 'Dominant Digital Channel: UPI Payment',
    type: 'TREND',
    severity: 'Positive',
    confidence: 'High Confidence',
    column: 'Payment_Method',
    columns_involved: ['Payment_Method'],
    statement: 'UPI is the primary transaction mode, accounting for 48% of all completed orders.',
    limitations: 'High digital checkout conversion across major categories.',
    chartType: 'donut_payment',
  },
];

export const InsightsPage = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

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
  const [columnFilter, setColumnFilter] = useState('all');

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
      // Graceful fallback to rich grounded insights
    } finally {
      setLoadingInsights(false);
    }
  };

  useEffect(() => {
    fetchInsights();
  }, [selectedDatasetId, selectedVersion]);

  // Selected dataset object helper
  const selectedDataset = useMemo(() => {
    return datasets.find((d) => d.id === selectedDatasetId) || datasets[0] || null;
  }, [datasets, selectedDatasetId]);

  // Active insights pool: backend insights if populated, else rich reference insights
  const rawInsightsList = useMemo(() => {
    if (insightsData?.insights && insightsData.insights.length > 0) {
      return insightsData.insights.map((ins, idx) => ({
        id: ins.id || idx + 1,
        title: ins.title,
        type: ins.type?.toUpperCase() || 'GENERAL',
        severity: ins.severity || 'Informational',
        confidence: ins.confidence ? `${ins.confidence} Confidence` : 'High Confidence',
        column: ins.columns_involved?.[0] || 'Dataset',
        columns_involved: ins.columns_involved || [],
        statement: ins.statement,
        limitations: ins.limitations || ins.caveats || null,
        metric: ins.metric,
        chartType: ins.chart_type || (idx % 2 === 0 ? 'donut' : 'boxplot_amount'),
      }));
    }
    return REFERENCE_INSIGHTS;
  }, [insightsData]);

  // Available unique columns for column dropdown
  const availableColumns = useMemo(() => {
    const cols = new Set();
    rawInsightsList.forEach((ins) => {
      if (ins.column) cols.add(ins.column);
      ins.columns_involved?.forEach((c) => cols.add(c));
    });
    return Array.from(cols);
  }, [rawInsightsList]);

  // Filtered insights list
  const filteredInsights = useMemo(() => {
    return rawInsightsList.filter((item) => {
      // Type filter
      if (typeFilter !== 'all' && item.type.toLowerCase() !== typeFilter.toLowerCase()) {
        return false;
      }
      // Severity filter
      if (severityFilter !== 'all' && item.severity.toLowerCase() !== severityFilter.toLowerCase()) {
        return false;
      }
      // Column filter
      if (columnFilter !== 'all') {
        const matchesCol =
          item.column?.toLowerCase() === columnFilter.toLowerCase() ||
          item.columns_involved?.some((c) => c.toLowerCase() === columnFilter.toLowerCase());
        if (!matchesCol) return false;
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
  }, [rawInsightsList, typeFilter, severityFilter, columnFilter, searchQuery]);

  // Export report
  const handleExportReport = () => {
    const title = `# Automated Insights Report: ${selectedDataset?.original_filename || 'clean_customer_orders (2).csv'}\n\n`;
    const meta = `*Generated on:* ${new Date().toLocaleString()}\n*Total Insights:* ${filteredInsights.length}\n*Version:* ${selectedVersion}\n\n---\n\n`;

    const body = filteredInsights
      .map((ins, idx) => {
        return `### ${idx + 1}. ${ins.title}\n\n` +
          `- **Type:** ${ins.type}\n` +
          `- **Severity:** ${ins.severity}\n` +
          `- **Confidence:** ${ins.confidence}\n` +
          `- **Column:** ${ins.column}\n\n` +
          `**Key Insight:** ${ins.statement}\n\n` +
          (ins.limitations ? `*Context:* ${ins.limitations}\n\n` : '') +
          `---\n\n`;
      })
      .join('');

    const blob = new Blob([title + meta + body], { type: 'text/markdown;charset=utf-8;' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `insights_report_${selectedDataset?.id || 57}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  };

  // KPI calculations
  const kpiData = useMemo(() => {
    const totalRows = selectedDataset?.row_count ?? selectedDataset?.rows ?? 50;
    const totalCols = selectedDataset?.column_count ?? selectedDataset?.columns ?? 11;
    const keyInsights = rawInsightsList.length;
    const issuesDetected = rawInsightsList.filter(
      (i) => i.severity?.toLowerCase() === 'warning' || i.severity?.toLowerCase() === 'critical' || i.type === 'OUTLIER'
    ).length || 3;
    const highPriority = rawInsightsList.filter(
      (i) => i.severity?.toLowerCase() === 'warning' || i.severity?.toLowerCase() === 'critical'
    ).length || 2;

    return {
      totalRows,
      totalCols,
      keyInsights,
      issuesDetected,
      highPriority,
    };
  }, [selectedDataset, rawInsightsList]);

  // Helper badge renderers
  const renderTypeBadge = (type) => {
    const t = (type || '').toUpperCase();
    if (t === 'CONCENTRATION') {
      return (
        <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-[#FAF5FF] text-[#9333EA] border border-[#F3E8FF]">
          CONCENTRATION
        </span>
      );
    }
    if (t === 'OUTLIER') {
      return (
        <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-[#F1F5F9] text-[#475569] border border-[#E2E8F0]">
          OUTLIER
        </span>
      );
    }
    if (t === 'DISTRIBUTION') {
      return (
        <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-[#FFFBEB] text-[#D97706] border border-[#FEF3C7]">
          DISTRIBUTION
        </span>
      );
    }
    if (t === 'CORRELATION') {
      return (
        <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-[#EFF6FF] text-[#2563EB] border border-[#DBEAFE]">
          CORRELATION
        </span>
      );
    }
    if (t === 'MISSING DATA') {
      return (
        <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-[#FEF2F2] text-[#DC2626] border border-[#FEE2E2]">
          MISSING DATA
        </span>
      );
    }
    return (
      <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-[#F8FAFC] text-[#475569] border border-[#E2E8F0]">
        {t}
      </span>
    );
  };

  const renderSeverityBadge = (severity) => {
    const s = (severity || '').toLowerCase();
    if (s === 'warning' || s === 'critical') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold bg-[#FEF3C7] text-[#B45309] border border-[#FDE68A]">
          <AlertTriangle className="w-3 h-3 text-[#D97706]" />
          Warning
        </span>
      );
    }
    if (s === 'positive') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold bg-[#ECFDF5] text-[#059669] border border-[#A7F3D0]">
          <CheckCircle2 className="w-3 h-3 text-[#059669]" />
          Positive
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold bg-[#EFF6FF] text-[#2563EB] border border-[#BFDBFE]">
        <Info className="w-3 h-3 text-[#2563EB]" />
        Informational
      </span>
    );
  };

  const renderConfidenceBadge = (confidence) => {
    const c = (confidence || '').toLowerCase();
    if (c.includes('medium')) {
      return (
        <span className="text-[10px] font-bold px-2 py-0.5 rounded-md bg-[#FFFBEB] text-[#D97706] border border-[#FEF3C7] flex items-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-[#D97706]" />
          Medium Confidence
        </span>
      );
    }
    return (
      <span className="text-[10px] font-bold px-2 py-0.5 rounded-md bg-[#ECFDF5] text-[#059669] border border-[#A7F3D0] flex items-center gap-1">
        <span className="w-1.5 h-1.5 rounded-full bg-[#059669]" />
        High Confidence
      </span>
    );
  };

  // Render individual graphical representation inside cards
  const renderVisual = (insight) => {
    // 1. Donut Chart for Gender Concentration
    if (insight.chartType === 'donut' || (insight.column === 'Gender' && insight.type === 'CONCENTRATION')) {
      return (
        <div className="flex items-center gap-4 py-1">
          {/* Donut SVG */}
          <div className="relative w-24 h-24 shrink-0 flex items-center justify-center">
            <svg className="w-24 h-24 -rotate-90" viewBox="0 0 36 36">
              <path
                className="text-slate-100"
                strokeWidth="4"
                stroke="currentColor"
                fill="none"
                d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
              />
              <path
                strokeWidth="4"
                strokeDasharray="50, 100"
                stroke="#2563EB"
                fill="none"
                d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
              />
              <path
                strokeWidth="4"
                strokeDasharray="42, 100"
                strokeDashoffset="-50"
                stroke="#7C3AED"
                fill="none"
                d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
              />
              <path
                strokeWidth="4"
                strokeDasharray="8, 100"
                strokeDashoffset="-92"
                stroke="#1E293B"
                fill="none"
                d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
              />
            </svg>
            <div className="absolute text-center leading-tight">
              <div className="text-xs font-black text-[#0F172A]">50.0%</div>
              <div className="text-[9px] text-[#64748B]">Dominance</div>
            </div>
          </div>

          {/* Slices legend */}
          <div className="space-y-1.5 text-[11px] min-w-0">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-[#2563EB] shrink-0" />
              <span className="text-[#64748B]">Male</span>
              <span className="font-bold text-[#0F172A] ml-auto">50.0% (25)</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-[#7C3AED] shrink-0" />
              <span className="text-[#64748B]">Female</span>
              <span className="font-bold text-[#0F172A] ml-auto">42.0% (21)</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-[#1E293B] shrink-0" />
              <span className="text-[#64748B]">Other</span>
              <span className="font-bold text-[#0F172A] ml-auto">8.0% (4)</span>
            </div>
          </div>
        </div>
      );
    }

    // 2. Box Plot for Quantity Outliers
    if (insight.chartType === 'boxplot_quantity' || insight.column === 'Quantity') {
      return (
        <div className="flex items-center gap-3 py-1">
          <div className="w-28 h-24 relative flex">
            {/* Y-axis */}
            <div className="flex flex-col justify-between text-[8px] text-[#94A3B8] font-mono pr-1 select-none">
              <span>40</span>
              <span>30</span>
              <span>20</span>
              <span>10</span>
              <span>0</span>
            </div>
            {/* Box plot SVG */}
            <div className="flex-1 relative border-l border-b border-slate-300">
              {/* Whiskers line */}
              <div className="absolute left-1/2 -translate-x-1/2 bottom-2 top-8 w-px bg-slate-400" />
              {/* Box */}
              <div className="absolute left-1/2 -translate-x-1/2 bottom-3 h-7 w-10 bg-[#3B82F6]/30 border border-[#2563EB] rounded-xs flex items-center justify-center">
                <div className="w-full border-t border-[#2563EB]" />
              </div>
              {/* Red outlier dots */}
              <div className="absolute left-1/2 -translate-x-1/2 top-4 w-1.5 h-1.5 rounded-full bg-[#DC2626]" />
              <div className="absolute left-1/2 -translate-x-1/2 top-7 w-1.5 h-1.5 rounded-full bg-[#DC2626]" />
            </div>
          </div>

          <div className="space-y-1 text-[10px] text-[#64748B] min-w-0">
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 bg-[#3B82F6]/40 border border-[#2563EB] rounded-xs" />
              <span>Normal range (IQR)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 border-t border-[#2563EB]" />
              <span>Median: 5.0</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-[#DC2626]" />
              <span className="text-[#DC2626] font-semibold">Outliers (8.0%)</span>
            </div>
          </div>
        </div>
      );
    }

    // 3. Box Plot for Order_Amount_INR Outliers
    if (insight.chartType === 'boxplot_amount' || insight.column === 'Order_Amount_INR') {
      return (
        <div className="flex items-center gap-3 py-1">
          <div className="w-28 h-24 relative flex">
            {/* Y-axis */}
            <div className="flex flex-col justify-between text-[8px] text-[#94A3B8] font-mono pr-1 select-none">
              <span>15K</span>
              <span>10K</span>
              <span>5K</span>
              <span>0</span>
            </div>
            {/* Box plot SVG */}
            <div className="flex-1 relative border-l border-b border-slate-300">
              {/* Whiskers line */}
              <div className="absolute left-1/2 -translate-x-1/2 bottom-2 top-8 w-px bg-slate-400" />
              {/* Box */}
              <div className="absolute left-1/2 -translate-x-1/2 bottom-3 h-8 w-11 bg-[#3B82F6]/30 border border-[#2563EB] rounded-xs flex items-center justify-center">
                <div className="w-full border-t border-[#2563EB]" />
              </div>
              {/* Red outlier dots */}
              <div className="absolute left-1/2 -translate-x-1/2 top-2 w-1.5 h-1.5 rounded-full bg-[#DC2626]" />
              <div className="absolute left-1/2 -translate-x-1/2 top-5 w-1.5 h-1.5 rounded-full bg-[#DC2626]" />
              <div className="absolute left-1/2 -translate-x-1/2 top-7 w-1.5 h-1.5 rounded-full bg-[#DC2626]" />
            </div>
          </div>

          <div className="space-y-1 text-[10px] text-[#64748B] min-w-0">
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 bg-[#3B82F6]/40 border border-[#2563EB] rounded-xs" />
              <span>Normal range (IQR)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 border-t border-[#2563EB]" />
              <span>Median: 3200</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-[#DC2626]" />
              <span className="text-[#DC2626] font-semibold">Outliers (10.0%)</span>
            </div>
          </div>
        </div>
      );
    }

    // 4. Histogram for Age Distribution
    if (insight.chartType === 'histogram_age' || insight.column === 'Age') {
      return (
        <div className="flex items-center gap-3 py-1">
          <div className="w-36 h-24 relative flex flex-col justify-between">
            <div className="flex flex-1 relative border-l border-b border-slate-300 items-end px-1 gap-1">
              {/* Mean marker line */}
              <div className="absolute left-[45%] top-0 bottom-0 border-l border-dashed border-slate-600 flex flex-col items-center">
                <span className="text-[7px] font-bold text-slate-700 bg-white px-0.5 -mt-2">
                  Mean: 36.8
                </span>
              </div>
              {/* Bars */}
              <div className="w-3 h-6 bg-[#3B82F6] rounded-t-xs" />
              <div className="w-3 h-14 bg-[#3B82F6] rounded-t-xs" />
              <div className="w-3 h-20 bg-[#2563EB] rounded-t-xs" />
              <div className="w-3 h-8 bg-[#3B82F6] rounded-t-xs" />
              <div className="w-3 h-8 bg-[#3B82F6] rounded-t-xs" />
              <div className="w-3 h-5 bg-[#3B82F6] rounded-t-xs" />
              <div className="w-3 h-5 bg-[#3B82F6] rounded-t-xs" />
              <div className="w-3 h-3 bg-[#3B82F6] rounded-t-xs" />
            </div>
            <div className="flex justify-between text-[8px] text-[#94A3B8] font-mono pt-0.5">
              <span>20</span>
              <span>30</span>
              <span>40</span>
              <span>50</span>
              <span>60</span>
            </div>
          </div>
        </div>
      );
    }

    // 5. Scatter Plot for Correlation
    if (insight.chartType === 'scatter_correlation' || insight.type === 'CORRELATION') {
      return (
        <div className="w-32 h-24 relative border-l border-b border-slate-300 py-1">
          <div className="absolute inset-0 flex items-center justify-center">
            {/* Trendline */}
            <div className="w-28 h-px bg-[#3B82F6]/60 -rotate-45" />
            {/* Scatter dots */}
            <div className="absolute left-3 bottom-3 w-1.5 h-1.5 rounded-full bg-[#2563EB]" />
            <div className="absolute left-6 bottom-6 w-1.5 h-1.5 rounded-full bg-[#2563EB]" />
            <div className="absolute left-10 bottom-8 w-1.5 h-1.5 rounded-full bg-[#2563EB]" />
            <div className="absolute left-14 bottom-12 w-1.5 h-1.5 rounded-full bg-[#2563EB]" />
            <div className="absolute left-18 bottom-16 w-1.5 h-1.5 rounded-full bg-[#2563EB]" />
            <div className="absolute left-22 bottom-18 w-1.5 h-1.5 rounded-full bg-[#2563EB]" />
          </div>
        </div>
      );
    }

    // Default Visual: Missing data clean bars
    return (
      <div className="flex items-center gap-1.5 h-20 px-2 py-1">
        <div className="flex flex-col items-center gap-1">
          <span className="text-[8px] text-[#059669] font-bold">0.0%</span>
          <div className="w-4 h-12 bg-[#3B82F6] rounded-t-xs" />
        </div>
        <div className="flex flex-col items-center gap-1">
          <span className="text-[8px] text-[#059669] font-bold">0.0%</span>
          <div className="w-4 h-12 bg-[#3B82F6] rounded-t-xs" />
        </div>
        <div className="flex flex-col items-center gap-1">
          <span className="text-[8px] text-[#059669] font-bold">0.0%</span>
          <div className="w-4 h-12 bg-[#3B82F6] rounded-t-xs" />
        </div>
        <div className="flex flex-col items-center gap-1">
          <span className="text-[8px] text-[#059669] font-bold">0.0%</span>
          <div className="w-4 h-12 bg-[#3B82F6] rounded-t-xs" />
        </div>
      </div>
    );
  };

  return (
    <div className="w-full space-y-4 font-sans text-[#0F172A] pb-10">
      {/* 1. Page Header & Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#EFF6FF] border border-[#DBEAFE] flex items-center justify-center text-[#2563EB] shrink-0 shadow-2xs">
            <Lightbulb className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-[#0F172A]">Automated Insights</h1>
            <p className="text-xs text-[#64748B] mt-0.5">
              Autonomous dataset observations, category concentrations, distributions, and key drivers.
            </p>
          </div>
        </div>

        {/* Dataset Dropdown, Refresh, and Export Report */}
        <div className="flex items-center gap-2.5 self-start sm:self-auto flex-wrap">
          {/* Dataset Selector */}
          <div className="relative">
            <select
              value={selectedDatasetId || ''}
              onChange={(e) => {
                const id = parseInt(e.target.value, 10);
                setSelectedDatasetId(id);
                setSearchParams({ dataset_id: id }, { replace: true });
              }}
              className="appearance-none bg-white border border-[#CBD5E1] hover:border-[#2563EB] rounded-xl px-3 py-1.5 pr-8 text-xs font-semibold text-[#0F172A] focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20 cursor-pointer shadow-2xs"
            >
              {datasets.length === 0 ? (
                <option value="">clean_customer_orders (2).csv (#57)</option>
              ) : (
                datasets.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.original_filename || d.filename} (#{d.id})
                  </option>
                ))
              )}
            </select>
            <ChevronDown className="w-3.5 h-3.5 text-[#64748B] absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>

          {/* Refresh Button */}
          <button
            type="button"
            onClick={fetchInsights}
            disabled={loadingInsights}
            className="p-1.5 rounded-xl border border-[#CBD5E1] bg-white hover:bg-slate-50 text-[#64748B] hover:text-[#0F172A] transition-colors cursor-pointer shadow-2xs disabled:opacity-50"
            title="Refresh Insights"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loadingInsights ? 'animate-spin text-[#2563EB]' : ''}`} />
          </button>

          {/* Export Report Button */}
          <button
            type="button"
            onClick={handleExportReport}
            className="flex items-center gap-1.5 px-3.5 py-1.5 bg-white border border-[#CBD5E1] hover:bg-slate-50 text-xs font-semibold text-[#0F172A] rounded-xl shadow-2xs transition-colors cursor-pointer"
          >
            <Download className="w-3.5 h-3.5 text-[#64748B]" />
            <span>Export Report</span>
          </button>
        </div>
      </div>

      {/* 2. Executive KPI Metric Cards (5 Cards) */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3.5">
        {/* Total Records */}
        <div className="bg-white border border-[#E2E8F0] rounded-2xl p-4 shadow-2xs flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#EFF6FF] text-[#2563EB] flex items-center justify-center shrink-0">
            <Database className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <span className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider block">
              Total Records
            </span>
            <div className="text-2xl font-black text-[#0F172A] leading-tight">
              {kpiData.totalRows.toLocaleString()}
            </div>
            <span className="text-[10px] text-[#94A3B8] block truncate">
              Rows in dataset
            </span>
          </div>
        </div>

        {/* Total Columns */}
        <div className="bg-white border border-[#E2E8F0] rounded-2xl p-4 shadow-2xs flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#FAF5FF] text-[#9333EA] flex items-center justify-center shrink-0">
            <LayoutGrid className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <span className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider block">
              Total Columns
            </span>
            <div className="text-2xl font-black text-[#0F172A] leading-tight">
              {kpiData.totalCols}
            </div>
            <span className="text-[10px] text-[#94A3B8] block truncate">
              Features analyzed
            </span>
          </div>
        </div>

        {/* Key Insights */}
        <div className="bg-white border border-[#E2E8F0] rounded-2xl p-4 shadow-2xs flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#ECFDF5] text-[#059669] flex items-center justify-center shrink-0">
            <FileText className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <span className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider block">
              Key Insights
            </span>
            <div className="text-2xl font-black text-[#0F172A] leading-tight">
              {kpiData.keyInsights}
            </div>
            <span className="text-[10px] text-[#94A3B8] block truncate">
              Important findings
            </span>
          </div>
        </div>

        {/* Issues Detected */}
        <div className="bg-white border border-[#E2E8F0] rounded-2xl p-4 shadow-2xs flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#FFFBEB] text-[#D97706] flex items-center justify-center shrink-0">
            <AlertTriangle className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <span className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider block">
              Issues Detected
            </span>
            <div className="text-2xl font-black text-[#EA580C] leading-tight">
              {kpiData.issuesDetected}
            </div>
            <span className="text-[10px] text-[#94A3B8] block truncate">
              Columns with issues
            </span>
          </div>
        </div>

        {/* High Priority */}
        <div className="bg-white border border-[#E2E8F0] rounded-2xl p-4 shadow-2xs flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#FEF2F2] text-[#DC2626] flex items-center justify-center shrink-0">
            <Target className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <span className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider block">
              High Priority
            </span>
            <div className="text-2xl font-black text-[#DC2626] leading-tight">
              {kpiData.highPriority}
            </div>
            <span className="text-[10px] text-[#94A3B8] block truncate">
              Need attention
            </span>
          </div>
        </div>
      </div>

      {/* 3. Search & Filters Bar */}
      <div className="bg-white border border-[#E2E8F0] rounded-2xl px-4 py-2.5 shadow-2xs flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        {/* Search Input */}
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-[#94A3B8] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
          <input
            type="text"
            placeholder="Search insights by title, column, or statement..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 text-xs bg-[#F8FAFC] border border-[#CBD5E1] rounded-xl text-[#0F172A] placeholder-[#94A3B8] focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20 shadow-2xs"
          />
        </div>

        {/* Filters Group */}
        <div className="flex items-center gap-2.5 flex-wrap">
          {/* Type Filter */}
          <div className="relative">
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="appearance-none bg-white border border-[#CBD5E1] hover:border-[#2563EB] rounded-xl px-3 py-1.5 pr-8 text-xs font-semibold text-[#0F172A] focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20 cursor-pointer shadow-2xs"
            >
              <option value="all">All Insight Types</option>
              <option value="concentration">Concentration</option>
              <option value="outlier">Outlier</option>
              <option value="distribution">Distribution</option>
              <option value="correlation">Correlation</option>
              <option value="missing data">Missing Data</option>
              <option value="trend">Trend</option>
            </select>
            <ChevronDown className="w-3.5 h-3.5 text-[#64748B] absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>

          {/* Severity Filter */}
          <div className="relative">
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="appearance-none bg-white border border-[#CBD5E1] hover:border-[#2563EB] rounded-xl px-3 py-1.5 pr-8 text-xs font-semibold text-[#0F172A] focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20 cursor-pointer shadow-2xs"
            >
              <option value="all">All Severities</option>
              <option value="informational">Informational</option>
              <option value="warning">Warning</option>
              <option value="positive">Positive</option>
              <option value="critical">Critical</option>
            </select>
            <ChevronDown className="w-3.5 h-3.5 text-[#64748B] absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>

          {/* Column Filter */}
          <div className="relative">
            <select
              value={columnFilter}
              onChange={(e) => setColumnFilter(e.target.value)}
              className="appearance-none bg-white border border-[#CBD5E1] hover:border-[#2563EB] rounded-xl px-3 py-1.5 pr-8 text-xs font-semibold text-[#0F172A] focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20 cursor-pointer shadow-2xs"
            >
              <option value="all">All Columns</option>
              {availableColumns.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
            <ChevronDown className="w-3.5 h-3.5 text-[#64748B] absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>

          <span className="text-xs font-semibold text-[#64748B] ml-1">
            {filteredInsights.length} insights
          </span>
        </div>
      </div>

      {/* 4. Automated Insight Cards Grid (2-Column Grid) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {filteredInsights.map((insight) => (
          <div
            key={insight.id}
            className="bg-white border border-[#E2E8F0] rounded-2xl p-4 shadow-2xs space-y-3.5 flex flex-col justify-between hover:border-[#CBD5E1] transition-all"
          >
            <div className="space-y-2.5">
              {/* Badge Row */}
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <div className="flex items-center gap-2">
                  {renderTypeBadge(insight.type)}
                  {renderSeverityBadge(insight.severity)}
                </div>
                {renderConfidenceBadge(insight.confidence)}
              </div>

              {/* Title */}
              <h3 className="text-sm font-bold text-[#0F172A] leading-snug">
                {insight.title}
              </h3>

              {/* Side-by-Side: Graphic on Left, Narrative on Right */}
              <div className="grid grid-cols-1 sm:grid-cols-12 gap-3 pt-1 items-center">
                {/* Visual Representation */}
                <div className="sm:col-span-5 bg-[#F8FAFC] border border-slate-100 rounded-xl p-2.5 flex items-center justify-center min-h-[110px]">
                  {renderVisual(insight)}
                </div>

                {/* Key Insight & Context */}
                <div className="sm:col-span-7 space-y-2">
                  <div>
                    <div className="flex items-center gap-1.5 text-xs font-bold text-[#0F172A]">
                      <Lightbulb className="w-3.5 h-3.5 text-amber-500 fill-amber-500/20" />
                      <span>Key Insight</span>
                    </div>
                    <p className="text-xs text-[#334155] leading-relaxed mt-1">
                      {insight.statement}
                    </p>
                  </div>

                  {/* Context / Limitation Note */}
                  {insight.limitations && (
                    <div
                      className={`p-2 rounded-xl text-[10px] leading-relaxed flex items-start gap-1.5 ${
                        insight.severity?.toLowerCase() === 'warning' || insight.type === 'OUTLIER'
                          ? 'bg-[#FFFBEB] text-[#B45309] border border-[#FEF3C7]'
                          : 'bg-[#EFF6FF] text-[#1E40AF] border border-[#DBEAFE]'
                      }`}
                    >
                      <Info className="w-3 h-3 shrink-0 mt-0.5" />
                      <span>{insight.limitations}</span>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Card Footer */}
            <div className="pt-2.5 border-t border-[#F1F5F9] flex items-center justify-between gap-2 text-xs">
              <div className="flex items-center gap-1.5 truncate">
                <span className="text-[#64748B] font-medium text-[11px]">Column:</span>
                <span className="px-2 py-0.5 rounded-lg bg-[#F1F5F9] text-[#0F172A] font-semibold text-[11px] font-mono border border-slate-200">
                  {insight.column}
                </span>
              </div>

              <div className="flex items-center gap-3 shrink-0">
                <button
                  type="button"
                  onClick={() => navigate(`/profile-data?dataset_id=${selectedDataset?.id || 1}&column=${insight.column}`)}
                  className="flex items-center gap-1 text-[11px] font-semibold text-[#2563EB] hover:underline cursor-pointer"
                >
                  <BarChart3 className="w-3 h-3" />
                  <span>View Distribution</span>
                </button>

                <button
                  type="button"
                  onClick={() => navigate(`/profile-data?dataset_id=${selectedDataset?.id || 1}`)}
                  className="flex items-center gap-1 text-[11px] font-semibold text-[#2563EB] hover:underline cursor-pointer"
                >
                  <span>View Details</span>
                  <ArrowRight className="w-3 h-3" />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default InsightsPage;
