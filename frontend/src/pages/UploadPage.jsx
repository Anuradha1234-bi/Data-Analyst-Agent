import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import {
  UploadCloud,
  FolderOpen,
  CheckCircle2,
  AlertCircle,
  ArrowRight,
  X,
  RefreshCw,
  Trash2,
  BookOpen,
  Lightbulb,
  Columns,
  FileCode,
  Database,
  Table,
  Clock,
  MoreVertical,
  BarChart2,
} from 'lucide-react';
import { datasetService } from '../services/datasetService';
import { cleaningService } from '../services/cleaningService';
import { extractErrorMessage } from '../services/api';

const MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024; // 50 MB
const ALLOWED_EXTENSIONS = ['.csv', '.xlsx', '.xls'];

// Default demonstration data matching the reference image
const DEFAULT_DEMO_DATASET = {
  id: 1,
  filename: 'customers_quality_test.csv',
  original_filename: 'customers_quality_test.csv',
  file_type: 'CSV',
  file_size: 2.4 * 1024 * 1024,
  file_size_bytes: 2.4 * 1024 * 1024,
  rows: 50,
  row_count: 50,
  columns: 12,
  column_count: 12,
  created_at: '2026-10-18T14:32:00Z',
};

const DEFAULT_DEMO_ROWS = [
  { id: 1, CustomerID: 'CUST001', Name: 'Aarav Sharma', Age: 28, Gender: 'Male', City: 'Pune', Income: 50000, PurchaseAmount: 1200, JoinDate: '2023-01-15' },
  { id: 2, CustomerID: 'CUST002', Name: 'Riya Patel', Age: 34, Gender: 'Female', City: 'Mumbai', Income: 75000, PurchaseAmount: 2300, JoinDate: '2023-02-10' },
  { id: 3, CustomerID: 'CUST003', Name: 'Neha Singh', Age: 29, Gender: 'Female', City: 'Delhi', Income: 62000, PurchaseAmount: 1800, JoinDate: '2023-03-05' },
  { id: 4, CustomerID: 'CUST004', Name: 'Arjun Mehta', Age: 41, Gender: 'Male', City: 'Bangalore', Income: 85000, PurchaseAmount: 3200, JoinDate: '2023-03-22' },
  { id: 5, CustomerID: 'CUST005', Name: 'Priya Nair', Age: 26, Gender: 'Female', City: 'Chennai', Income: 48000, PurchaseAmount: 950, JoinDate: '2023-04-01' },
];

const DEFAULT_RECENT_CARDS = [
  {
    id: 1,
    filename: 'customers_quality_test.csv',
    rows: 50,
    columns: 12,
    size: '2.4 MB',
    timeAgo: '2 minutes ago',
    type: 'csv',
  },
  {
    id: 2,
    filename: 'sales_data.xlsx',
    rows: 200,
    columns: 8,
    size: '1.8 MB',
    timeAgo: '3 days ago',
    type: 'xlsx',
  },
  {
    id: 3,
    filename: 'employee_data.csv',
    rows: 150,
    columns: 10,
    size: '1.2 MB',
    timeAgo: '1 week ago',
    type: 'csv',
  },
];

export const UploadPage = () => {
  const [fileList, setFileList] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [generalError, setGeneralError] = useState('');
  const [uploadSummary, setUploadSummary] = useState(null);

  // Active / Selected Dataset for Information Card & Live Preview
  const [activeDataset, setActiveDataset] = useState(DEFAULT_DEMO_DATASET);
  const [previewRows, setPreviewRows] = useState(DEFAULT_DEMO_ROWS);
  const [previewColumns, setPreviewColumns] = useState([
    'CustomerID',
    'Name',
    'Age',
    'Gender',
    'City',
    'Income',
    'PurchaseAmount',
    'JoinDate',
  ]);
  const [loadingPreview, setLoadingPreview] = useState(false);

  // Recent Datasets
  const [recentDatasets, setRecentDatasets] = useState(DEFAULT_RECENT_CARDS);

  const fileInputRef = useRef(null);
  const navigate = useNavigate();

  const formatFileSize = (bytes) => {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
  };

  const formatDate = (dateString) => {
    if (!dateString) return '18 Oct 2026, 14:32';
    try {
      const d = new Date(dateString);
      return d.toLocaleDateString('en-GB', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return dateString;
    }
  };

  const validateFile = (file) => {
    const ext = `.${file.name.split('.').pop().toLowerCase()}`;
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      return 'Unsupported format. Supported: CSV, XLSX, XLS.';
    }
    if (file.size > MAX_FILE_SIZE_BYTES) {
      return 'File too large. Maximum size is 50 MB.';
    }
    if (file.size === 0) {
      return 'The file is empty (0 bytes). Please provide a file with data.';
    }
    return null;
  };

  // Fetch recent datasets on mount from API
  const fetchRecentDatasets = async () => {
    try {
      const list = await datasetService.getDatasets();
      if (list && list.length > 0) {
        // Map actual user datasets into recent format
        const mapped = list.slice(0, 3).map((d) => ({
          id: d.id,
          filename: d.original_filename || d.filename,
          rows: d.row_count ?? d.rows ?? 0,
          columns: d.column_count ?? d.columns ?? 0,
          size: formatFileSize(d.file_size ?? d.file_size_bytes),
          timeAgo: 'Recently',
          type: (d.file_type || '').toLowerCase().includes('xls') ? 'xlsx' : 'csv',
          raw: d,
        }));
        setRecentDatasets(mapped);

        // If there's an actual dataset, load it as active
        const first = list[0];
        setActiveDataset(first);
        loadServerPreview(first.id);
      }
    } catch (err) {
      console.warn('Using default preview datasets:', err);
    }
  };

  const loadServerPreview = async (datasetId) => {
    setLoadingPreview(true);
    try {
      const preview = await cleaningService.getOriginalPreview(datasetId);
      if (preview && preview.columns && preview.columns.length > 0) {
        setPreviewColumns(preview.columns);
        const rows = (preview.sample_rows || preview.sample_preview || []).slice(0, 5);
        setPreviewRows(rows);
      }
    } catch (err) {
      console.warn('Server preview fallback:', err);
    } finally {
      setLoadingPreview(false);
    }
  };

  useEffect(() => {
    fetchRecentDatasets();
  }, []);

  // Read first 5 rows locally for immediate client preview on file selection
  const readLocalPreview = (file) => {
    if (!file.name.toLowerCase().endsWith('.csv')) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const text = e.target.result;
        const lines = text.split(/\r\n|\n/).filter((l) => l.trim().length > 0);
        if (lines.length > 0) {
          const cols = lines[0].split(',').map((c) => c.trim().replace(/^["']|["']$/g, ''));
          const rows = lines.slice(1, 6).map((line, idx) => {
            const vals = line.split(',');
            const rowObj = { id: idx + 1 };
            cols.forEach((col, cIdx) => {
              rowObj[col] = (vals[cIdx] || '').trim().replace(/^["']|["']$/g, '');
            });
            return rowObj;
          });
          setPreviewColumns(cols);
          setPreviewRows(rows);
        }
      } catch (err) {
        console.warn('Local preview parse error:', err);
      }
    };
    reader.readAsText(file.slice(0, 64 * 1024));
  };

  const handleAddFiles = (newRawFiles) => {
    setGeneralError('');
    setUploadSummary(null);

    const rawArray = Array.from(newRawFiles);
    if (rawArray.length > 0) {
      const firstFile = rawArray[0];
      readLocalPreview(firstFile);

      // Create an active preview state for this file
      setActiveDataset({
        id: Date.now(),
        filename: firstFile.name,
        original_filename: firstFile.name,
        file_type: firstFile.name.endsWith('.xlsx') || firstFile.name.endsWith('.xls') ? 'XLSX' : 'CSV',
        file_size: firstFile.size,
        file_size_bytes: firstFile.size,
        rows: 50,
        columns: 12,
        created_at: new Date().toISOString(),
      });
    }

    const newEntries = rawArray.map((file) => {
      const validationError = validateFile(file);
      return {
        id: `${file.name}-${file.size}-${Date.now()}-${Math.random()}`,
        file,
        name: file.name,
        size: file.size,
        status: validationError ? 'error' : 'pending',
        error: validationError,
      };
    });

    setFileList((prev) => [...prev, ...newEntries]);

    // Automatically trigger upload if valid file
    if (newEntries.some((f) => f.status === 'pending')) {
      handleUploadAllFiles(newEntries.filter((f) => f.status === 'pending').map((f) => f.file));
    }
  };

  const handleFileInputChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleAddFiles(e.target.files);
      e.target.value = '';
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleAddFiles(e.dataTransfer.files);
    }
  };

  const handleUploadAllFiles = async (filesToUpload) => {
    setIsUploading(true);
    setUploadProgress(0);
    setGeneralError('');

    try {
      const res = await datasetService.uploadDatasets(filesToUpload, (percent) => {
        setUploadProgress(percent);
      });

      const uploadedList = res.uploaded || [];
      if (uploadedList.length > 0) {
        const latest = uploadedList[0];
        setActiveDataset(latest);
        localStorage.setItem('selected_dataset_id', String(latest.id));
        await loadServerPreview(latest.id);
      }
      setUploadSummary({
        totalUploaded: res.total_uploaded || uploadedList.length,
        totalFailed: res.total_failed || (res.failed ? res.failed.length : 0),
      });
      fetchRecentDatasets();
    } catch (err) {
      const msg = extractErrorMessage(err);
      setGeneralError(msg);
    } finally {
      setIsUploading(false);
    }
  };

  const handleReplace = () => {
    fileInputRef.current?.click();
  };

  const handleRemove = () => {
    setActiveDataset(null);
    setPreviewRows([]);
    setPreviewColumns([]);
  };

  const handleSelectRecent = (recentItem) => {
    if (recentItem.raw) {
      setActiveDataset(recentItem.raw);
      localStorage.setItem('selected_dataset_id', String(recentItem.raw.id));
      loadServerPreview(recentItem.raw.id);
    } else {
      setActiveDataset({
        id: recentItem.id,
        filename: recentItem.filename,
        original_filename: recentItem.filename,
        file_type: recentItem.type.toUpperCase(),
        file_size: 2.4 * 1024 * 1024,
        rows: recentItem.rows,
        columns: recentItem.columns,
        created_at: '2026-10-18T14:32:00Z',
      });
      setPreviewRows(DEFAULT_DEMO_ROWS);
    }
  };

  const handleAnalyzeDataset = () => {
    if (activeDataset?.id) {
      localStorage.setItem('selected_dataset_id', String(activeDataset.id));
      navigate(`/data-analyst?dataset_id=${activeDataset.id}`);
    } else {
      navigate('/data-analyst');
    }
  };

  return (
    <div className="max-w-[1240px] mx-auto space-y-6">
      {/* 1. Header Section */}
      <div className="flex items-center justify-between pb-1">
        <div className="flex items-center gap-3.5">
          <div className="w-11 h-11 rounded-2xl bg-[#EFF6FF] border border-[#BFDBFE] text-[#1E6BFF] flex items-center justify-center shrink-0 shadow-2xs">
            <UploadCloud className="w-6 h-6 text-[#1E6BFF]" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-[#0F172A] tracking-tight">Upload Dataset</h1>
            <p className="text-xs text-[#64748B] mt-0.5">
              Upload your CSV or Excel file to start analyzing your data with AI.
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => navigate('/datasets')}
          className="px-4 py-2 bg-white hover:bg-[#F8FAFC] border border-[#E2E8F0] text-[#1E6BFF] text-xs font-semibold rounded-xl shadow-2xs transition-colors inline-flex items-center gap-1.5 cursor-pointer"
        >
          <span>My Datasets</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* General Error Banner */}
      {generalError && (
        <div className="p-3.5 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs flex items-center justify-between shadow-2xs">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0 text-red-600" />
            <span>{generalError}</span>
          </div>
          <button onClick={() => setGeneralError('')} className="text-red-500 hover:text-red-700 p-1">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* 2. Row 1: Drag & Drop Area (Left) + Upload Guidelines (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-stretch">
        {/* Large Dashed Drag & Drop Box */}
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`lg:col-span-8 border-2 border-dashed rounded-2xl p-8 sm:p-10 text-center transition-all bg-white shadow-2xs flex flex-col items-center justify-center min-h-[260px] ${
            isDragging
              ? 'border-[#1E6BFF] bg-[#EFF6FF] ring-4 ring-[#1E6BFF]/10'
              : 'border-[#60A5FA] hover:border-[#1E6BFF]'
          }`}
        >
          <div className="w-14 h-14 rounded-2xl bg-[#EFF6FF] text-[#1E6BFF] flex items-center justify-center mb-3 border border-[#BFDBFE]/40 shadow-2xs">
            <UploadCloud className="w-7 h-7 text-[#1E6BFF]" />
          </div>

          <h3 className="text-base font-bold text-[#0F172A]">
            Drag & drop your CSV or Excel files here
          </h3>
          <p className="text-xs text-[#94A3B8] my-1.5">or</p>

          <div className="my-1">
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".csv,.xlsx,.xls"
              onChange={handleFileInputChange}
              className="hidden"
              id="dataset-file-input"
              disabled={isUploading}
            />
            <button
              type="button"
              disabled={isUploading}
              onClick={() => fileInputRef.current?.click()}
              className="px-6 py-2.5 bg-[#1E6BFF] hover:bg-[#1A5ED8] text-white text-xs font-bold rounded-xl shadow-xs inline-flex items-center gap-2 cursor-pointer transition-colors disabled:opacity-60"
            >
              <FolderOpen className="w-4 h-4" />
              <span>Browse Files</span>
            </button>
          </div>

          <p className="text-xs text-[#64748B] mt-4">
            Supported formats: <strong className="text-[#0F172A]">CSV, XLSX, XLS</strong>
            <span className="mx-2">•</span>
            Maximum size: <strong className="text-[#0F172A]">50 MB</strong>
          </p>

          {isUploading && (
            <div className="w-full max-w-sm mt-4 space-y-1.5">
              <div className="flex justify-between text-xs text-[#64748B]">
                <span>Uploading dataset...</span>
                <span className="font-bold text-[#1E6BFF]">{uploadProgress}%</span>
              </div>
              <div className="w-full bg-[#E2E8F0] h-2 rounded-full overflow-hidden">
                <div
                  className="bg-[#1E6BFF] h-2 transition-all duration-200 rounded-full"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
            </div>
          )}
        </div>

        {/* Upload Guidelines Box */}
        <div className="lg:col-span-4 bg-white border border-[#E5E9F0] rounded-2xl p-6 shadow-2xs flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 pb-3">
              <BookOpen className="w-4 h-4 text-[#1E6BFF]" />
              <h3 className="text-sm font-bold text-[#0F172A]">Upload Guidelines</h3>
            </div>

            <ul className="space-y-2.5 text-xs text-[#334155]">
              <li className="flex items-start gap-2.5">
                <CheckCircle2 className="w-4 h-4 text-[#16A34A] shrink-0 mt-0.5" />
                <span>Supported formats: CSV, XLSX, XLS</span>
              </li>
              <li className="flex items-start gap-2.5">
                <CheckCircle2 className="w-4 h-4 text-[#16A34A] shrink-0 mt-0.5" />
                <span>Maximum file size: 50 MB per file</span>
              </li>
              <li className="flex items-start gap-2.5">
                <CheckCircle2 className="w-4 h-4 text-[#16A34A] shrink-0 mt-0.5" />
                <span>First row should contain column headers</span>
              </li>
              <li className="flex items-start gap-2.5">
                <CheckCircle2 className="w-4 h-4 text-[#16A34A] shrink-0 mt-0.5" />
                <span>Works with numeric, text, date and categorical data</span>
              </li>
              <li className="flex items-start gap-2.5">
                <CheckCircle2 className="w-4 h-4 text-[#16A34A] shrink-0 mt-0.5" />
                <span>Use clean and structured data for better insights</span>
              </li>
            </ul>
          </div>

          {/* Tip Callout */}
          <div className="bg-[#F0F7FF] border border-[#DCEBFF] rounded-xl p-3.5 flex items-start gap-3 mt-4">
            <Lightbulb className="w-5 h-5 text-[#1E6BFF] shrink-0 mt-0.5" />
            <div>
              <div className="text-xs font-bold text-[#1E6BFF]">Tip</div>
              <p className="text-[11px] text-[#475569] mt-0.5 leading-relaxed">
                You can upload multiple files and compare datasets in the Datasets section.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* 3. Row 2: Uploaded Dataset Information Card */}
      {activeDataset && (
        <div className="bg-white border border-[#E5E9F0] rounded-2xl p-4 shadow-2xs flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          {/* File Icon & Name */}
          <div className="flex items-center gap-3.5 min-w-0">
            <div className="w-10 h-10 rounded-xl bg-[#16A34A] text-white flex items-center justify-center shrink-0 shadow-2xs">
              <svg className="w-5 h-5 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <path d="M3 9h18M3 15h18M9 3v18" />
              </svg>
            </div>

            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-bold text-[#0F172A] truncate">
                  {activeDataset.original_filename || activeDataset.filename || 'customers_quality_test.csv'}
                </span>
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-[#EBFDF2] text-[#16A34A] border border-[#B9F5D0] text-[11px] font-semibold">
                  <CheckCircle2 className="w-3.5 h-3.5 text-[#16A34A]" />
                  <span>Upload Successful</span>
                </span>
              </div>
              <p className="text-xs text-[#64748B] mt-0.5">
                {formatFileSize(activeDataset.file_size ?? activeDataset.file_size_bytes ?? 2.4 * 1024 * 1024)}
                <span className="mx-2">•</span>
                Uploaded on {formatDate(activeDataset.created_at)}
              </p>
            </div>
          </div>

          {/* Metric Chips */}
          <div className="flex items-center gap-3 flex-wrap">
            {/* Rows */}
            <div className="flex items-center gap-2.5 px-3 py-1.5 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0]">
              <div className="p-1.5 rounded-lg bg-[#EFF6FF] text-[#1E6BFF]">
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="8" y1="6" x2="21" y2="6" />
                  <line x1="8" y1="12" x2="21" y2="12" />
                  <line x1="8" y1="18" x2="21" y2="18" />
                  <line x1="3" y1="6" x2="3.01" y2="6" />
                  <line x1="3" y1="12" x2="3.01" y2="12" />
                  <line x1="3" y1="18" x2="3.01" y2="18" />
                </svg>
              </div>
              <div>
                <div className="text-[10px] text-[#64748B] font-medium leading-none">Rows</div>
                <div className="text-sm font-bold text-[#0F172A] leading-tight mt-0.5">
                  {(activeDataset.row_count ?? activeDataset.rows ?? 50).toLocaleString()}
                </div>
              </div>
            </div>

            {/* Columns */}
            <div className="flex items-center gap-2.5 px-3 py-1.5 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0]">
              <div className="p-1.5 rounded-lg bg-[#F0FDF4] text-[#16A34A]">
                <Columns className="w-4 h-4" />
              </div>
              <div>
                <div className="text-[10px] text-[#64748B] font-medium leading-none">Columns</div>
                <div className="text-sm font-bold text-[#0F172A] leading-tight mt-0.5">
                  {activeDataset.column_count ?? activeDataset.columns ?? 12}
                </div>
              </div>
            </div>

            {/* File Type */}
            <div className="flex items-center gap-2.5 px-3 py-1.5 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0]">
              <div className="p-1.5 rounded-lg bg-[#FAF5FF] text-[#9333EA]">
                <FileCode className="w-4 h-4" />
              </div>
              <div>
                <div className="text-[10px] text-[#64748B] font-medium leading-none">File Type</div>
                <div className="text-sm font-bold text-[#0F172A] leading-tight mt-0.5 uppercase">
                  {activeDataset.file_type || 'CSV'}
                </div>
              </div>
            </div>

            {/* Size */}
            <div className="flex items-center gap-2.5 px-3 py-1.5 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0]">
              <div className="p-1.5 rounded-lg bg-[#FFF1F2] text-[#E11D48]">
                <Database className="w-4 h-4" />
              </div>
              <div>
                <div className="text-[10px] text-[#64748B] font-medium leading-none">Size</div>
                <div className="text-sm font-bold text-[#0F172A] leading-tight mt-0.5">
                  {formatFileSize(activeDataset.file_size ?? activeDataset.file_size_bytes ?? 2.4 * 1024 * 1024)}
                </div>
              </div>
            </div>
          </div>

          {/* Action Buttons: Replace & Remove */}
          <div className="flex items-center gap-2.5 shrink-0">
            <button
              type="button"
              onClick={handleReplace}
              className="px-4 py-2 bg-white hover:bg-[#EFF6FF] border border-[#1E6BFF] text-[#1E6BFF] text-xs font-semibold rounded-xl flex items-center gap-1.5 transition-colors cursor-pointer"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Replace</span>
            </button>

            <button
              type="button"
              onClick={handleRemove}
              className="px-4 py-2 bg-white hover:bg-red-50 border border-[#EF4444] text-[#EF4444] text-xs font-semibold rounded-xl flex items-center gap-1.5 transition-colors cursor-pointer"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Remove</span>
            </button>
          </div>
        </div>
      )}

      {/* 4. Row 3: Dataset Preview (First 5 Rows) (Left) + What Happens Next? Stepper (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-stretch">
        {/* Dataset Preview Card */}
        <div className="lg:col-span-8 bg-white border border-[#E5E9F0] rounded-2xl p-5 shadow-2xs space-y-3 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3">
              <div className="flex items-center gap-2">
                <Table className="w-4 h-4 text-[#1E6BFF]" />
                <h3 className="text-sm font-bold text-[#0F172A]">Dataset Preview (First 5 Rows)</h3>
              </div>

              <button
                type="button"
                onClick={() => {
                  if (activeDataset?.id) {
                    navigate(`/profile-data?dataset_id=${activeDataset.id}`);
                  }
                }}
                className="text-xs font-semibold text-[#1E6BFF] hover:underline flex items-center gap-1 cursor-pointer"
              >
                <span>View Full Data</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>

            {/* Table */}
            <div className="border border-[#E5E9F0] rounded-xl overflow-hidden">
              <div className="overflow-x-auto max-h-72">
                <table className="w-full text-left text-xs border-collapse">
                  <thead className="bg-[#F8FAFC] border-b border-[#E5E9F0]">
                    <tr>
                      <th className="px-3 py-2.5 text-[11px] font-bold text-[#0F172A] w-10 text-center">
                        #
                      </th>
                      {previewColumns.map((col, idx) => (
                        <th
                          key={idx}
                          className="px-3.5 py-2.5 text-[11px] font-bold text-[#0F172A] whitespace-nowrap"
                        >
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#F1F5F9] text-[#334155]">
                    {previewRows.map((row, rIdx) => (
                      <tr key={rIdx} className="hover:bg-[#F8FAFC] transition-colors">
                        <td className="px-3 py-2.5 text-center text-[11px] text-[#64748B] font-mono">
                          {rIdx + 1}
                        </td>
                        {previewColumns.map((col, cIdx) => (
                          <td
                            key={cIdx}
                            className="px-3.5 py-2.5 whitespace-nowrap text-xs max-w-xs truncate"
                          >
                            {row[col] !== undefined && row[col] !== null ? String(row[col]) : '—'}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>

        {/* What Happens Next? Stepper Card */}
        <div className="lg:col-span-4 bg-white border border-[#E5E9F0] rounded-2xl p-6 shadow-2xs flex flex-col justify-between">
          <div>
            <h3 className="text-sm font-bold text-[#0F172A] pb-4">What happens next?</h3>

            <div className="relative pl-7 space-y-5 before:absolute before:left-3 before:top-3 before:bottom-3 before:w-0.5 before:bg-[#E2E8F0]">
              {/* Step 1 */}
              <div className="relative">
                <div className="absolute -left-7 top-0 w-6 h-6 rounded-full bg-[#1E6BFF] text-white flex items-center justify-center text-xs font-bold shadow-2xs">
                  1
                </div>
                <div>
                  <h4 className="text-xs font-bold text-[#0F172A]">Data Profile</h4>
                  <p className="text-[11px] text-[#64748B] mt-0.5 leading-relaxed">
                    Analyze columns, data types and basic statistics.
                  </p>
                </div>
              </div>

              {/* Step 2 */}
              <div className="relative">
                <div className="absolute -left-7 top-0 w-6 h-6 rounded-full bg-[#1E6BFF] text-white flex items-center justify-center text-xs font-bold shadow-2xs">
                  2
                </div>
                <div>
                  <h4 className="text-xs font-bold text-[#0F172A]">Data Quality Check</h4>
                  <p className="text-[11px] text-[#64748B] mt-0.5 leading-relaxed">
                    Detect missing values, duplicates, outliers and inconsistencies.
                  </p>
                </div>
              </div>

              {/* Step 3 */}
              <div className="relative">
                <div className="absolute -left-7 top-0 w-6 h-6 rounded-full bg-[#1E6BFF] text-white flex items-center justify-center text-xs font-bold shadow-2xs">
                  3
                </div>
                <div>
                  <h4 className="text-xs font-bold text-[#0F172A]">AI Insights</h4>
                  <p className="text-[11px] text-[#64748B] mt-0.5 leading-relaxed">
                    Get key findings, patterns and recommendations.
                  </p>
                </div>
              </div>

              {/* Step 4 */}
              <div className="relative">
                <div className="absolute -left-7 top-0 w-6 h-6 rounded-full bg-[#1E6BFF] text-white flex items-center justify-center text-xs font-bold shadow-2xs">
                  4
                </div>
                <div>
                  <h4 className="text-xs font-bold text-[#0F172A]">Visualizations</h4>
                  <p className="text-[11px] text-[#64748B] mt-0.5 leading-relaxed">
                    Explore charts and interactive analysis.
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Analyze Dataset Button */}
          <button
            type="button"
            onClick={handleAnalyzeDataset}
            className="w-full py-3 bg-[#1E6BFF] hover:bg-[#1A5ED8] text-white text-xs font-bold rounded-xl shadow-xs transition-colors flex items-center justify-center gap-2 cursor-pointer mt-5"
          >
            <BarChart2 className="w-4 h-4" />
            <span>Analyze Dataset</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* 5. Row 4: Recent Datasets Section */}
      <div className="space-y-3 pt-1">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-[#1E6BFF]" />
            <h3 className="text-sm font-bold text-[#0F172A]">Recent Datasets</h3>
          </div>

          <button
            type="button"
            onClick={() => navigate('/datasets')}
            className="text-xs font-semibold text-[#1E6BFF] hover:underline flex items-center gap-1 cursor-pointer"
          >
            <span>View All</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* 3 Dataset Cards in Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {recentDatasets.map((d) => (
            <div
              key={d.id}
              onClick={() => handleSelectRecent(d)}
              className="bg-white border border-[#E5E9F0] hover:border-[#1E6BFF] rounded-2xl p-4 shadow-2xs transition-all flex items-center justify-between cursor-pointer group"
            >
              <div className="flex items-center gap-3 min-w-0">
                <div
                  className={`w-10 h-10 rounded-xl text-white flex items-center justify-center shrink-0 font-bold text-xs shadow-2xs ${
                    d.type === 'xlsx' ? 'bg-[#15803D]' : 'bg-[#16A34A]'
                  }`}
                >
                  {d.type === 'xlsx' ? (
                    <span className="font-bold text-sm tracking-tighter">X</span>
                  ) : (
                    <svg className="w-5 h-5 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <rect x="3" y="3" width="18" height="18" rx="2" />
                      <path d="M3 9h18M3 15h18M9 3v18" />
                    </svg>
                  )}
                </div>

                <div className="min-w-0">
                  <div className="text-xs font-bold text-[#0F172A] truncate group-hover:text-[#1E6BFF] transition-colors">
                    {d.filename}
                  </div>
                  <div className="text-[11px] text-[#64748B] mt-0.5">
                    {d.rows} rows <span className="mx-1">•</span> {d.columns} columns
                  </div>
                  <div className="text-[11px] text-[#94A3B8] mt-0.5">
                    {d.size} <span className="mx-1">•</span> {d.timeAgo}
                  </div>
                </div>
              </div>

              <div className="p-1 text-[#94A3B8] group-hover:text-[#0F172A] transition-colors shrink-0">
                <MoreVertical className="w-4 h-4" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default UploadPage;
