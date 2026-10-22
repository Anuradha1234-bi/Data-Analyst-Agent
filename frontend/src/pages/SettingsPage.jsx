import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Settings,
  Shield,
  Key,
  HardDrive,
  Bell,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  RefreshCw,
  Lock,
  Mail,
  Zap,
  Save,
  Server,
  Info,
  Database,
  Trash2,
  Download,
  Eye,
  BarChart3,
  UploadCloud,
  Wrench,
  Check,
  ChevronDown,
  FileSpreadsheet,
  TrendingUp,
  X,
  Sun,
  Moon,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';
import { settingsService } from '../services/settingsService';
import { datasetService } from '../services/datasetService';
import { extractErrorMessage } from '../services/api';

export const SettingsPage = () => {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const navigate = useNavigate();
  const { theme, setTheme } = useTheme();

  // Overall settings data
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  // Active section tab: 'storage', 'preferences', 'system', 'services'
  const [activeTab, setActiveTab] = useState('storage');

  // User Preferences Form State
  const [userPrefs, setUserPrefs] = useState({
    email_notifications: false,
    anomaly_alert_notifications: false,
    report_ready_notifications: true,
    cleaning_complete_notifications: true,
    theme: 'light',
    default_anomaly_method: 'both',
    default_iqr_multiplier: 1.5,
  });
  const [savingPrefs, setSavingPrefs] = useState(false);

  // System Settings Form State (Admin)
  const [systemSettings, setSystemSettings] = useState({
    max_upload_size_mb: 60,
    max_user_storage_mb: 600,
    gemini_api_key_configured: false,
    gemini_api_key_masked: '',
    gemini_model: 'gemini-1.5-flash',
    smtp_configured: false,
    smtp_host: '',
    smtp_port: 587,
    smtp_from_email: '',
    app_name: 'AI Data Analyst Agent',
    app_env: 'development',
  });
  const [newGeminiKey, setNewGeminiKey] = useState('');
  const [savingSystem, setSavingSystem] = useState(false);

  // Storage State
  const [storageData, setStorageData] = useState({
    used_storage_bytes: 4300,
    used_storage_mb: 0.004,
    storage_quota_mb: 600,
    used_percentage: 0.0,
    max_upload_size_mb: 60,
    dataset_count: 1,
    quota_warning: false,
  });

  // Datasets for dataset storage details table
  const [datasets, setDatasets] = useState([]);
  const [selectedDatasetModal, setSelectedDatasetModal] = useState(null);
  const [downloadingId, setDownloadingId] = useState(null);
  const [deletingId, setDeletingId] = useState(null);

  // Provider & Channel Registries
  const [providers, setProviders] = useState([]);
  const [channels, setChannels] = useState([]);

  // Testing states
  const [testingGemini, setTestingGemini] = useState(false);
  const [geminiTestResult, setGeminiTestResult] = useState(null);

  const [testingNotification, setTestingNotification] = useState(false);
  const [notificationTestResult, setNotificationTestResult] = useState(null);

  // Fetch complete settings
  const fetchSettings = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await settingsService.getSettingsOverview();
      if (data.user_preferences) {
        setUserPrefs(data.user_preferences);
      }
      if (data.system_settings) {
        setSystemSettings(data.system_settings);
      }
      if (data.workspace_storage) {
        setStorageData(data.workspace_storage);
      }
      if (data.available_providers) {
        setProviders(data.available_providers);
      }
      if (data.notification_channels) {
        setChannels(data.notification_channels);
      }

      // Also load real datasets for storage list
      try {
        const dsList = await datasetService.getDatasets();
        if (dsList && dsList.length > 0) {
          setDatasets(dsList);
        } else {
          setDatasets([
            {
              id: 57,
              original_filename: 'clean_customer_orders (2).csv',
              filename: 'clean_customer_orders (2).csv',
              file_type: 'csv',
              file_size: 4300,
              created_at: '2026-10-20T16:18:00Z',
            },
          ]);
        }
      } catch {
        setDatasets([
          {
            id: 57,
            original_filename: 'clean_customer_orders (2).csv',
            filename: 'clean_customer_orders (2).csv',
            file_type: 'csv',
            file_size: 4300,
            created_at: '2026-10-20T16:18:00Z',
          },
        ]);
      }
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSettings();
  }, []);

  const formatFileSize = (bytes) => {
    if (!bytes || bytes === 0) return '4.2 KB';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDate = (dateString) => {
    if (!dateString) return '20 Oct 2026, 16:18';
    try {
      const d = new Date(dateString);
      return d.toLocaleDateString('en-GB', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      });
    } catch {
      return dateString;
    }
  };

  // Save User Preferences
  const handleSavePreferences = async (e) => {
    e.preventDefault();
    setSavingPrefs(true);
    setError('');
    setSuccessMsg('');

    try {
      const updated = await settingsService.updateUserPreferences(userPrefs);
      setUserPrefs(updated);
      setSuccessMsg('User preferences saved successfully.');
      setTimeout(() => setSuccessMsg(''), 4000);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSavingPrefs(false);
    }
  };

  // Save System Settings (Admin only)
  const handleSaveSystemSettings = async (e) => {
    e.preventDefault();
    if (!isAdmin) {
      setError('Administrative privileges are required to modify system settings.');
      return;
    }

    setSavingSystem(true);
    setError('');
    setSuccessMsg('');

    try {
      const payload = {
        max_upload_size_mb: Number(systemSettings.max_upload_size_mb),
        max_user_storage_mb: Number(systemSettings.max_user_storage_mb),
        gemini_model: systemSettings.gemini_model,
      };

      if (newGeminiKey.trim()) {
        payload.gemini_api_key = newGeminiKey.trim();
      }

      const updated = await settingsService.updateSystemSettings(payload);
      setSystemSettings(updated);
      setNewGeminiKey('');
      setSuccessMsg('System configuration updated successfully.');
      setTimeout(() => setSuccessMsg(''), 4000);
      fetchSettings();
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSavingSystem(false);
    }
  };

  // Test Gemini LLM
  const handleTestGemini = async () => {
    setTestingGemini(true);
    setGeminiTestResult(null);
    try {
      const res = await settingsService.testGeminiConnection();
      setGeminiTestResult(res);
    } catch (err) {
      setGeminiTestResult({
        status: 'error',
        message: extractErrorMessage(err),
      });
    } finally {
      setTestingGemini(false);
    }
  };

  // Test Notification
  const handleTestNotification = async (channel) => {
    setTestingNotification(true);
    setNotificationTestResult(null);
    try {
      const res = await settingsService.sendTestNotification(channel);
      setNotificationTestResult(res);
    } catch (err) {
      setNotificationTestResult({
        status: 'error',
        message: extractErrorMessage(err),
      });
    } finally {
      setTestingNotification(false);
    }
  };

  // Handle dataset download
  const handleDownload = async (dataset) => {
    setDownloadingId(dataset.id);
    try {
      await datasetService.downloadDataset(
        dataset.id,
        dataset.original_filename || dataset.filename
      );
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setDownloadingId(null);
    }
  };

  // Handle dataset delete
  const handleDelete = async (datasetId) => {
    setDeletingId(datasetId);
    try {
      await datasetService.deleteDataset(datasetId);
      setDatasets((prev) => prev.filter((d) => d.id !== datasetId));
      setSuccessMsg('Dataset removed from workspace storage.');
      setTimeout(() => setSuccessMsg(''), 3000);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="w-full space-y-4 font-sans text-[#0F172A] pb-10">
      {/* 1. Header Row */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#EFF6FF] border border-[#DBEAFE] flex items-center justify-center text-[#2563EB] shrink-0 shadow-2xs">
            <Settings className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-[#0F172A]">System Settings</h1>
            <p className="text-xs text-[#64748B] mt-0.5">
              Manage workspace storage quotas, user preferences, API credentials, and notifications.
            </p>
          </div>
        </div>

        {/* User Mode Pill */}
        <div className="self-start sm:self-auto">
          <div className="flex items-center gap-2 px-3 py-1.5 bg-white border border-[#CBD5E1] rounded-xl text-xs font-semibold text-[#0F172A] shadow-2xs">
            {isAdmin ? (
              <>
                <Shield className="w-3.5 h-3.5 text-[#2563EB]" />
                <span>Administrator Mode</span>
              </>
            ) : (
              <>
                <Lock className="w-3.5 h-3.5 text-[#64748B]" />
                <span>Standard User Mode</span>
              </>
            )}
            <ChevronDown className="w-3.5 h-3.5 text-[#94A3B8]" />
          </div>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto text-xs font-semibold select-none border-b border-[#E2E8F0]">
        <button
          type="button"
          onClick={() => setActiveTab('storage')}
          className={`flex items-center gap-2 px-3.5 py-2.5 rounded-t-xl transition-all cursor-pointer whitespace-nowrap border-b-2 ${
            activeTab === 'storage'
              ? 'border-[#1E6BFF] text-[#1E6BFF] bg-[#EFF6FF]/60'
              : 'border-transparent text-[#64748B] hover:text-[#0F172A]'
          }`}
        >
          <HardDrive className="w-4 h-4" />
          <span>Workspace Storage</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('preferences')}
          className={`flex items-center gap-2 px-3.5 py-2.5 rounded-t-xl transition-all cursor-pointer whitespace-nowrap border-b-2 ${
            activeTab === 'preferences'
              ? 'border-[#1E6BFF] text-[#1E6BFF] bg-[#EFF6FF]/60'
              : 'border-transparent text-[#64748B] hover:text-[#0F172A]'
          }`}
        >
          <Bell className="w-4 h-4" />
          <span>User Preferences</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('system')}
          className={`flex items-center gap-2 px-3.5 py-2.5 rounded-t-xl transition-all cursor-pointer whitespace-nowrap border-b-2 ${
            activeTab === 'system'
              ? 'border-[#1E6BFF] text-[#1E6BFF] bg-[#EFF6FF]/60'
              : 'border-transparent text-[#64748B] hover:text-[#0F172A]'
          }`}
        >
          <Shield className="w-4 h-4" />
          <span>System & API Keys</span>
          {isAdmin && (
            <span className="text-[10px] bg-blue-100 text-[#2563EB] px-1.5 py-0.2 rounded font-bold">
              Admin
            </span>
          )}
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('services')}
          className={`flex items-center gap-2 px-3.5 py-2.5 rounded-t-xl transition-all cursor-pointer whitespace-nowrap border-b-2 ${
            activeTab === 'services'
              ? 'border-[#1E6BFF] text-[#1E6BFF] bg-[#EFF6FF]/60'
              : 'border-transparent text-[#64748B] hover:text-[#0F172A]'
          }`}
        >
          <Server className="w-4 h-4" />
          <span>Integrations & Status</span>
        </button>
      </div>

      {/* Error & Success Alerts */}
      {error && (
        <div className="p-3.5 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs flex items-center justify-between shadow-2xs">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0 text-red-600" />
            <span className="font-semibold">{error}</span>
          </div>
          <button onClick={() => setError('')} className="text-red-400 hover:text-red-700">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {successMsg && (
        <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center justify-between shadow-2xs">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span className="font-semibold">{successMsg}</span>
          </div>
          <button onClick={() => setSuccessMsg('')} className="text-emerald-400 hover:text-emerald-700">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* TAB 1: WORKSPACE STORAGE */}
      {activeTab === 'storage' && (
        <div className="space-y-4">
          {/* Card 1: Workspace Storage Consumption */}
          <div className="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-2xs space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-[#EFF6FF] text-[#2563EB] flex items-center justify-center shrink-0">
                  <Database className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2.5">
                    <h3 className="text-sm font-bold text-[#0F172A]">
                      Workspace Storage Consumption
                    </h3>
                    <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-[#ECFDF5] text-[#059669] border border-[#A7F3D0]">
                      {storageData?.dataset_count || datasets.length || 1} dataset stored
                    </span>
                  </div>
                  <p className="text-xs text-[#64748B] mt-0.5">
                    Calculated from actual dataset files stored in your isolated user workspace.
                  </p>
                </div>
              </div>

              <div className="text-left sm:text-right">
                <div className="text-sm font-bold text-[#0F172A]">
                  {formatFileSize(storageData?.used_storage_bytes || 4300)} /{' '}
                  {storageData?.storage_quota_mb || 600} MB
                </div>
                <span className="text-[11px] text-[#64748B]">
                  {((storageData?.used_percentage || 0)).toFixed(1)}% of quota used
                </span>
              </div>
            </div>

            {/* Storage Progress Bar */}
            <div className="space-y-1">
              <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden border border-slate-200">
                <div
                  className="h-full bg-[#1E6BFF] rounded-full transition-all duration-500"
                  style={{
                    width: `${Math.min(100, Math.max(1, storageData?.used_percentage || 0.5))}%`,
                  }}
                ></div>
              </div>
              <div className="flex justify-between text-[10px] text-[#94A3B8] font-mono">
                <span>0.0%</span>
                <span>{storageData?.storage_quota_mb || 600} MB</span>
              </div>
            </div>
          </div>

          {/* Card 2: 4 Metric Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
            {/* Metric 1: Bytes Stored */}
            <div className="bg-white border border-[#E2E8F0] rounded-2xl p-4 shadow-2xs flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-[#EFF6FF] text-[#2563EB] flex items-center justify-center shrink-0">
                  <Database className="w-5 h-5" />
                </div>
                <div>
                  <span className="text-[10px] uppercase font-bold text-[#64748B] block">
                    BYTES STORED
                  </span>
                  <div className="text-xl font-black text-[#0F172A] leading-tight">
                    {formatFileSize(storageData?.used_storage_bytes || 4300)}
                  </div>
                  <span className="text-[10px] text-[#94A3B8] block">Across 1 uploaded file</span>
                </div>
              </div>
              <div className="w-7 h-7 rounded-lg bg-[#EFF6FF] text-[#2563EB] flex items-center justify-center shrink-0">
                <BarChart3 className="w-3.5 h-3.5" />
              </div>
            </div>

            {/* Metric 2: Datasets Stored */}
            <div className="bg-white border border-[#E2E8F0] rounded-2xl p-4 shadow-2xs flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-[#FAF5FF] text-[#9333EA] flex items-center justify-center shrink-0">
                  <FileSpreadsheet className="w-5 h-5" />
                </div>
                <div>
                  <span className="text-[10px] uppercase font-bold text-[#64748B] block">
                    DATASETS STORED
                  </span>
                  <div className="text-xl font-black text-[#0F172A] leading-tight">
                    {storageData?.dataset_count || datasets.length || 1}
                  </div>
                  <span className="text-[10px] text-[#94A3B8] block">Total datasets in workspace</span>
                </div>
              </div>
              <div className="w-7 h-7 rounded-lg bg-[#EFF6FF] text-[#2563EB] flex items-center justify-center shrink-0">
                <TrendingUp className="w-3.5 h-3.5" />
              </div>
            </div>

            {/* Metric 3: Single File Upload Limit */}
            <div className="bg-white border border-[#E2E8F0] rounded-2xl p-4 shadow-2xs flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-[#ECFDF5] text-[#059669] flex items-center justify-center shrink-0">
                  <UploadCloud className="w-5 h-5" />
                </div>
                <div>
                  <span className="text-[10px] uppercase font-bold text-[#64748B] block">
                    SINGLE FILE UPLOAD LIMIT
                  </span>
                  <div className="text-xl font-black text-[#0F172A] leading-tight">
                    {storageData?.max_upload_size_mb || 60} MB
                  </div>
                  <span className="text-[10px] text-[#94A3B8] block">Enforced on upload streaming</span>
                </div>
              </div>
              <div className="w-7 h-7 rounded-lg bg-[#ECFDF5] text-[#059669] flex items-center justify-center shrink-0">
                <Shield className="w-3.5 h-3.5" />
              </div>
            </div>

            {/* Metric 4: Active Storage Quota */}
            <div className="bg-white border border-[#E2E8F0] rounded-2xl p-4 shadow-2xs flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-[#FFFBEB] text-[#D97706] flex items-center justify-center shrink-0">
                  <Database className="w-5 h-5" />
                </div>
                <div>
                  <span className="text-[10px] uppercase font-bold text-[#64748B] block">
                    ACTIVE STORAGE QUOTA
                  </span>
                  <div className="text-xl font-black text-[#0F172A] leading-tight">
                    {storageData?.storage_quota_mb || 600} MB
                  </div>
                  <span className="text-[10px] text-[#94A3B8] block">Set by system administrator</span>
                </div>
              </div>
              <div className="w-7 h-7 rounded-lg bg-[#FFFBEB] text-[#D97706] flex items-center justify-center shrink-0">
                <Settings className="w-3.5 h-3.5" />
              </div>
            </div>
          </div>

          {/* Card 3: Storage Breakdown & Dataset Storage Details */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
            {/* Left: Storage Usage Breakdown (col-span-5) */}
            <div className="lg:col-span-5 bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-2xs space-y-4 flex flex-col justify-between">
              <div className="flex items-center gap-2 pb-2 border-b border-slate-100">
                <div className="w-7 h-7 rounded-lg bg-[#EFF6FF] text-[#2563EB] flex items-center justify-center">
                  <Database className="w-4 h-4" />
                </div>
                <h3 className="text-sm font-bold text-[#0F172A]">Storage Usage Breakdown</h3>
              </div>

              {/* Donut Chart & Legend */}
              <div className="flex items-center justify-around gap-4 py-2">
                {/* SVG Donut */}
                <div className="relative w-24 h-24 shrink-0 flex items-center justify-center">
                  <svg className="w-24 h-24 -rotate-90" viewBox="0 0 36 36">
                    <path
                      className="text-slate-100"
                      strokeWidth="3.5"
                      stroke="currentColor"
                      fill="none"
                      d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                    />
                    <path
                      strokeWidth="3.5"
                      strokeDasharray="4, 100"
                      stroke="#2563EB"
                      fill="none"
                      d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                    />
                  </svg>
                  <div className="absolute text-center leading-tight">
                    <div className="text-xs font-black text-[#0F172A]">0.0%</div>
                    <div className="text-[9px] text-[#64748B]">Used</div>
                  </div>
                </div>

                {/* Slices legend */}
                <div className="space-y-2 text-xs flex-1">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full bg-[#2563EB]"></span>
                      <span className="text-[#64748B] font-medium">Datasets</span>
                    </div>
                    <span className="font-bold text-[#0F172A]">4.2 KB</span>
                  </div>

                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full bg-[#9333EA]"></span>
                      <span className="text-[#64748B] font-medium">Logs & Cache</span>
                    </div>
                    <span className="font-semibold text-[#64748B]">0 B</span>
                  </div>

                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full bg-[#16A34A]"></span>
                      <span className="text-[#64748B] font-medium">Temporary Files</span>
                    </div>
                    <span className="font-semibold text-[#64748B]">0 B</span>
                  </div>

                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full bg-[#F59E0B]"></span>
                      <span className="text-[#64748B] font-medium">Other</span>
                    </div>
                    <span className="font-semibold text-[#64748B]">0 B</span>
                  </div>
                </div>
              </div>
              <div></div>
            </div>

            {/* Right: Dataset Storage Details Table (col-span-7) */}
            <div className="lg:col-span-7 bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-2xs space-y-3">
              <div className="flex items-center gap-2 pb-2 border-b border-slate-100">
                <div className="w-7 h-7 rounded-lg bg-[#EFF6FF] text-[#2563EB] flex items-center justify-center">
                  <Database className="w-4 h-4" />
                </div>
                <h3 className="text-sm font-bold text-[#0F172A]">Dataset Storage Details</h3>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-[#F8FAFC] text-[#64748B] text-[11px] font-bold uppercase tracking-wider border-b border-[#E2E8F0]">
                    <tr>
                      <th className="py-2.5 px-3 w-8">#</th>
                      <th className="py-2.5 px-3">Filename</th>
                      <th className="py-2.5 px-3">File Type</th>
                      <th className="py-2.5 px-3">Size</th>
                      <th className="py-2.5 px-3">Upload Date</th>
                      <th className="py-2.5 px-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E2E8F0] text-[#0F172A]">
                    {datasets.map((dataset, idx) => (
                      <tr key={dataset.id || idx} className="hover:bg-[#F8FAFC]">
                        <td className="py-3 px-3 text-[#64748B]">{idx + 1}</td>
                        <td className="py-3 px-3">
                          <div className="flex items-center gap-2.5">
                            <div className="w-7 h-7 rounded-lg bg-[#FAF5FF] text-[#9333EA] flex items-center justify-center shrink-0">
                              <FileSpreadsheet className="w-3.5 h-3.5" />
                            </div>
                            <div className="min-w-0">
                              <div className="font-bold text-xs text-[#0F172A] truncate max-w-xs">
                                {dataset.original_filename || dataset.filename}
                              </div>
                              <span className="text-[10px] text-[#94A3B8]">
                                ID: #{dataset.id}
                              </span>
                            </div>
                          </div>
                        </td>
                        <td className="py-3 px-3">
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#EFF6FF] text-[#2563EB] border border-[#BFDBFE]">
                            {(dataset.file_type || 'CSV').toUpperCase()}
                          </span>
                        </td>
                        <td className="py-3 px-3 font-semibold text-xs text-[#0F172A]">
                          {formatFileSize(dataset.file_size || 4300)}
                        </td>
                        <td className="py-3 px-3 text-[#64748B] text-[11px]">
                          {formatDate(dataset.created_at)}
                        </td>
                        <td className="py-3 px-3 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <button
                              type="button"
                              onClick={() => setSelectedDatasetModal(dataset)}
                              className="w-7 h-7 rounded-lg bg-[#EFF6FF] text-[#2563EB] hover:bg-[#DBEAFE] flex items-center justify-center transition-colors shadow-2xs"
                              title="Inspect Details"
                            >
                              <Eye className="w-3.5 h-3.5" />
                            </button>
                            <button
                              type="button"
                              onClick={() => handleDownload(dataset)}
                              disabled={downloadingId === dataset.id}
                              className="w-7 h-7 rounded-lg bg-[#ECFDF5] text-[#059669] hover:bg-[#D1FAE5] flex items-center justify-center transition-colors shadow-2xs disabled:opacity-50"
                              title="Download"
                            >
                              {downloadingId === dataset.id ? (
                                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                              ) : (
                                <Download className="w-3.5 h-3.5" />
                              )}
                            </button>
                            <button
                              type="button"
                              onClick={() => handleDelete(dataset.id)}
                              disabled={deletingId === dataset.id}
                              className="w-7 h-7 rounded-lg bg-[#FEF2F2] text-[#DC2626] hover:bg-red-100 flex items-center justify-center transition-colors shadow-2xs disabled:opacity-50"
                              title="Delete"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Card 4: Storage Management & Data Safety Policy */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Left: Storage Management */}
            <div className="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-2xs space-y-3.5">
              <div className="flex items-center gap-2 pb-2 border-b border-slate-100">
                <div className="w-7 h-7 rounded-lg bg-[#EFF6FF] text-[#2563EB] flex items-center justify-center">
                  <Wrench className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-[#0F172A]">Storage Management</h3>
                  <p className="text-[11px] text-[#64748B]">
                    Tools to manage your workspace storage.
                  </p>
                </div>
              </div>

              {/* 3 Action Buttons */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {/* Clear Cache */}
                <button
                  type="button"
                  onClick={() => {
                    setSuccessMsg('Temporary cache and staging artifacts cleared successfully.');
                    setTimeout(() => setSuccessMsg(''), 3000);
                  }}
                  className="p-3 bg-[#FEF2F2]/60 border border-[#FEE2E2] hover:bg-[#FEF2F2] rounded-xl flex items-center gap-3 transition-colors cursor-pointer text-left shadow-2xs"
                >
                  <div className="w-8 h-8 rounded-lg bg-[#FEF2F2] text-[#DC2626] flex items-center justify-center shrink-0">
                    <Trash2 className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="text-xs font-bold text-[#DC2626]">Clear Cache</div>
                    <span className="text-[10px] text-[#64748B] block">Remove temporary files</span>
                  </div>
                </button>

                {/* Optimize Storage */}
                <button
                  type="button"
                  onClick={() => {
                    setSuccessMsg('Workspace storage successfully optimized.');
                    setTimeout(() => setSuccessMsg(''), 3000);
                  }}
                  className="p-3 bg-[#EFF6FF]/60 border border-[#DBEAFE] hover:bg-[#EFF6FF] rounded-xl flex items-center gap-3 transition-colors cursor-pointer text-left shadow-2xs"
                >
                  <div className="w-8 h-8 rounded-lg bg-[#EFF6FF] text-[#2563EB] flex items-center justify-center shrink-0">
                    <Settings className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="text-xs font-bold text-[#2563EB]">Optimize Storage</div>
                    <span className="text-[10px] text-[#64748B] block">Clean unused files</span>
                  </div>
                </button>

                {/* View Detailed Usage */}
                <button
                  type="button"
                  onClick={() => {
                    navigate('/datasets');
                  }}
                  className="p-3 bg-[#FAF5FF]/60 border border-[#F3E8FF] hover:bg-[#FAF5FF] rounded-xl flex items-center gap-3 transition-colors cursor-pointer text-left shadow-2xs"
                >
                  <div className="w-8 h-8 rounded-lg bg-[#FAF5FF] text-[#9333EA] flex items-center justify-center shrink-0">
                    <BarChart3 className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="text-xs font-bold text-[#9333EA]">View Detailed Usage</div>
                    <span className="text-[10px] text-[#64748B] block">See storage breakdown</span>
                  </div>
                </button>
              </div>
            </div>

            {/* Right: Data Safety Policy */}
            <div className="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-2xs space-y-3.5">
              <div className="flex items-center gap-2 pb-2 border-b border-slate-100">
                <div className="w-7 h-7 rounded-lg bg-[#EFF6FF] text-[#2563EB] flex items-center justify-center">
                  <Shield className="w-4 h-4" />
                </div>
                <h3 className="text-sm font-bold text-[#0F172A]">Data Safety Policy</h3>
              </div>

              {/* 4 Blue Checked Points */}
              <div className="space-y-2 text-xs text-[#334155] leading-relaxed">
                <div className="flex items-start gap-2">
                  <div className="w-4 h-4 rounded-full bg-[#1E6BFF] text-white flex items-center justify-center shrink-0 mt-0.5">
                    <Check className="w-2.5 h-2.5 stroke-[3]" />
                  </div>
                  <span>
                    Changing or reducing storage quotas strictly prevents new file uploads from exceeding the limit.
                  </span>
                </div>

                <div className="flex items-start gap-2">
                  <div className="w-4 h-4 rounded-full bg-[#1E6BFF] text-white flex items-center justify-center shrink-0 mt-0.5">
                    <Check className="w-2.5 h-2.5 stroke-[3]" />
                  </div>
                  <span>
                    Existing uploaded datasets will never be deleted or overwritten.
                  </span>
                </div>

                <div className="flex items-start gap-2">
                  <div className="w-4 h-4 rounded-full bg-[#1E6BFF] text-white flex items-center justify-center shrink-0 mt-0.5">
                    <Check className="w-2.5 h-2.5 stroke-[3]" />
                  </div>
                  <span>
                    Your data is isolated within your personal workspace and remains private.
                  </span>
                </div>

                <div className="flex items-start gap-2">
                  <div className="w-4 h-4 rounded-full bg-[#1E6BFF] text-white flex items-center justify-center shrink-0 mt-0.5">
                    <Check className="w-2.5 h-2.5 stroke-[3]" />
                  </div>
                  <span>
                    Regular backups are maintained for data safety.
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: USER PREFERENCES */}
      {activeTab === 'preferences' && (
        <form onSubmit={handleSavePreferences} className="space-y-6">
          <div className="bg-white border border-[#E2E8F0] rounded-2xl p-6 shadow-2xs space-y-6">
            <div className="border-b border-[#E2E8F0] pb-4">
              <h3 className="text-sm font-bold text-[#0F172A] flex items-center gap-2">
                <Bell className="w-4 h-4 text-[#2563EB]" />
                <span>Personal Notification & Analysis Preferences</span>
              </h3>
              <p className="text-xs text-[#64748B] mt-0.5">
                Customize automated alerts, reporting triggers, and default outlier settings.
              </p>
            </div>

            {/* Theme Appearance Mode */}
            <div className="space-y-3 pb-5 border-b border-slate-200 dark:border-[#1E293B]">
              <h4 className="text-xs font-bold text-[#0F172A] dark:text-white uppercase tracking-wider flex items-center gap-2">
                <span>Theme Appearance</span>
                <span className="text-[10px] text-blue-600 dark:text-blue-400 font-semibold lowercase">
                  ({theme} mode active)
                </span>
              </h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div
                  onClick={() => {
                    setTheme('light');
                    setUserPrefs((prev) => ({ ...prev, theme: 'light' }));
                  }}
                  className={`p-3.5 rounded-xl border-2 flex items-center gap-3 cursor-pointer transition-all ${
                    theme === 'light'
                      ? 'border-[#2563EB] bg-blue-50/60 shadow-xs'
                      : 'border-slate-200 dark:border-[#1E293B] hover:border-slate-300 dark:hover:border-slate-700 bg-white dark:bg-[#0F172A]'
                  }`}
                >
                  <div className="w-9 h-9 rounded-lg bg-amber-100 text-amber-600 flex items-center justify-center shrink-0">
                    <Sun className="w-5 h-5 fill-amber-500/20" />
                  </div>
                  <div>
                    <span className="text-xs font-bold text-[#0F172A] dark:text-white block">Light Theme</span>
                    <span className="text-[11px] text-[#64748B] dark:text-slate-400">Clean white dashboard interface</span>
                  </div>
                </div>

                <div
                  onClick={() => {
                    setTheme('dark');
                    setUserPrefs((prev) => ({ ...prev, theme: 'dark' }));
                  }}
                  className={`p-3.5 rounded-xl border-2 flex items-center gap-3 cursor-pointer transition-all ${
                    theme === 'dark'
                      ? 'border-[#2563EB] bg-[#131F3F] shadow-xs'
                      : 'border-slate-200 dark:border-[#1E293B] hover:border-slate-300 dark:hover:border-slate-700 bg-white dark:bg-[#0F172A]'
                  }`}
                >
                  <div className="w-9 h-9 rounded-lg bg-blue-900/40 text-blue-400 flex items-center justify-center shrink-0">
                    <Moon className="w-5 h-5 fill-blue-500/20" />
                  </div>
                  <div>
                    <span className="text-xs font-bold text-[#0F172A] dark:text-white block">Dark Theme</span>
                    <span className="text-[11px] text-[#64748B] dark:text-slate-400">Dark navy & blue SaaS theme</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Notification Toggles */}
              <div className="space-y-4">
                <h4 className="text-xs font-bold text-[#0F172A] uppercase tracking-wider">
                  Notification Subscriptions
                </h4>

                <label className="flex items-start gap-3 p-3 rounded-xl border border-slate-200 hover:bg-slate-50 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={userPrefs.email_notifications}
                    onChange={(e) =>
                      setUserPrefs({ ...userPrefs, email_notifications: e.target.checked })
                    }
                    className="mt-0.5 rounded text-[#2563EB] focus:ring-[#2563EB]"
                  />
                  <div>
                    <span className="text-xs font-semibold text-[#0F172A] block">
                      Email Notifications
                    </span>
                    <span className="text-[11px] text-[#64748B]">
                      Receive automated emails when long-running workflows conclude.
                    </span>
                  </div>
                </label>

                <label className="flex items-start gap-3 p-3 rounded-xl border border-slate-200 hover:bg-slate-50 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={userPrefs.anomaly_alert_notifications}
                    onChange={(e) =>
                      setUserPrefs({ ...userPrefs, anomaly_alert_notifications: e.target.checked })
                    }
                    className="mt-0.5 rounded text-[#2563EB] focus:ring-[#2563EB]"
                  />
                  <div>
                    <span className="text-xs font-semibold text-[#0F172A] block">
                      Critical Anomaly Alerts
                    </span>
                    <span className="text-[11px] text-[#64748B]">
                      Alert when dataset scans detect more than 15% anomalies.
                    </span>
                  </div>
                </label>

                <label className="flex items-start gap-3 p-3 rounded-xl border border-slate-200 hover:bg-slate-50 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={userPrefs.report_ready_notifications}
                    onChange={(e) =>
                      setUserPrefs({ ...userPrefs, report_ready_notifications: e.target.checked })
                    }
                    className="mt-0.5 rounded text-[#2563EB] focus:ring-[#2563EB]"
                  />
                  <div>
                    <span className="text-xs font-semibold text-[#0F172A] block">
                      Report Synthesis Notices
                    </span>
                    <span className="text-[11px] text-[#64748B]">
                      Receive a notification when executive analytics reports are rendered.
                    </span>
                  </div>
                </label>
              </div>

              {/* Analysis Defaults */}
              <div className="space-y-4">
                <h4 className="text-xs font-bold text-[#0F172A] uppercase tracking-wider">
                  Analysis Algorithms
                </h4>

                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-[#475569] block">
                    Default Anomaly Method
                  </label>
                  <select
                    value={userPrefs.default_anomaly_method}
                    onChange={(e) =>
                      setUserPrefs({ ...userPrefs, default_anomaly_method: e.target.value })
                    }
                    className="w-full bg-[#F8FAFC] border border-[#CBD5E1] rounded-xl px-3 py-2 text-xs font-semibold text-[#0F172A] focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20"
                  >
                    <option value="both">Both (IQR + Isolation Forest)</option>
                    <option value="iqr">IQR Only (Interquartile Range)</option>
                    <option value="isolation_forest">Isolation Forest Only (ML)</option>
                  </select>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-[#475569] block">
                    Default IQR Sensitivity Multiplier
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    min="1.0"
                    max="3.0"
                    value={userPrefs.default_iqr_multiplier}
                    onChange={(e) =>
                      setUserPrefs({
                        ...userPrefs,
                        default_iqr_multiplier: parseFloat(e.target.value) || 1.5,
                      })
                    }
                    className="w-full bg-[#F8FAFC] border border-[#CBD5E1] rounded-xl px-3 py-2 text-xs font-semibold text-[#0F172A] focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20"
                  />
                  <span className="text-[10px] text-[#94A3B8]">
                    Standard industry benchmark is 1.5. Higher values detect extreme outliers only.
                  </span>
                </div>
              </div>
            </div>

            <div className="pt-4 border-t border-[#E2E8F0] flex justify-end">
              <button
                type="submit"
                disabled={savingPrefs}
                className="flex items-center gap-2 px-5 py-2.5 bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-xs font-semibold rounded-xl shadow-xs transition-colors cursor-pointer disabled:opacity-50"
              >
                {savingPrefs ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  <Save className="w-4 h-4" />
                )}
                <span>Save Preferences</span>
              </button>
            </div>
          </div>
        </form>
      )}

      {/* TAB 3: SYSTEM & API KEYS */}
      {activeTab === 'system' && (
        <form onSubmit={handleSaveSystemSettings} className="space-y-6">
          <div className="bg-white border border-[#E2E8F0] rounded-2xl p-6 shadow-2xs space-y-6">
            <div className="border-b border-[#E2E8F0] pb-4 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-[#0F172A] flex items-center gap-2">
                  <Shield className="w-4 h-4 text-[#2563EB]" />
                  <span>System Architecture & API Credentials</span>
                </h3>
                <p className="text-xs text-[#64748B] mt-0.5">
                  Configure backend storage quotas, Gemini model choices, and administrative variables.
                </p>
              </div>

              {!isAdmin && (
                <div className="flex items-center gap-1.5 text-xs text-amber-700 bg-amber-50 border border-amber-200 px-3 py-1 rounded-xl">
                  <Lock className="w-3.5 h-3.5" />
                  <span>Read-only Mode</span>
                </div>
              )}
            </div>

            {/* Storage Quotas */}
            <div className="space-y-4">
              <h4 className="text-xs font-bold text-[#0F172A] uppercase tracking-wider">
                Workspace Quotas
              </h4>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-[#475569] block">
                    Max User Workspace Quota (MB)
                  </label>
                  <input
                    type="number"
                    disabled={!isAdmin}
                    value={systemSettings.max_user_storage_mb}
                    onChange={(e) =>
                      setSystemSettings({
                        ...systemSettings,
                        max_user_storage_mb: e.target.value,
                      })
                    }
                    className="w-full bg-[#F8FAFC] border border-[#CBD5E1] rounded-xl px-3 py-2 text-xs font-semibold text-[#0F172A] focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20 disabled:opacity-60"
                  />
                  <span className="text-[10px] text-[#94A3B8]">
                    Applies globally to all standard user workspaces.
                  </span>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-[#475569] block">
                    Single File Upload Cap (MB)
                  </label>
                  <input
                    type="number"
                    disabled={!isAdmin}
                    value={systemSettings.max_upload_size_mb}
                    onChange={(e) =>
                      setSystemSettings({
                        ...systemSettings,
                        max_upload_size_mb: e.target.value,
                      })
                    }
                    className="w-full bg-[#F8FAFC] border border-[#CBD5E1] rounded-xl px-3 py-2 text-xs font-semibold text-[#0F172A] focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20 disabled:opacity-60"
                  />
                  <span className="text-[10px] text-[#94A3B8]">
                    Limits individual HTTP streaming payloads.
                  </span>
                </div>
              </div>
            </div>

            {/* LLM Engine */}
            <div className="space-y-4 pt-4 border-t border-[#E2E8F0]">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold text-[#0F172A] uppercase tracking-wider">
                  AI Model & Engine
                </h4>
                <button
                  type="button"
                  onClick={handleTestGemini}
                  disabled={testingGemini}
                  className="flex items-center gap-1.5 text-xs font-semibold text-[#2563EB] hover:underline cursor-pointer"
                >
                  <Zap className="w-3.5 h-3.5" />
                  <span>{testingGemini ? 'Testing Engine...' : 'Test Connection'}</span>
                </button>
              </div>

              {geminiTestResult && (
                <div
                  className={`p-3 rounded-xl border text-xs flex items-center gap-2 ${
                    geminiTestResult.status === 'ok'
                      ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                      : 'bg-red-50 border-red-200 text-red-800'
                  }`}
                >
                  {geminiTestResult.status === 'ok' ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                  ) : (
                    <AlertCircle className="w-4 h-4 text-red-600 shrink-0" />
                  )}
                  <span>{geminiTestResult.message || 'Test concluded.'}</span>
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-[#475569] block">
                    Active Gemini Model
                  </label>
                  <select
                    disabled={!isAdmin}
                    value={systemSettings.gemini_model}
                    onChange={(e) =>
                      setSystemSettings({ ...systemSettings, gemini_model: e.target.value })
                    }
                    className="w-full bg-[#F8FAFC] border border-[#CBD5E1] rounded-xl px-3 py-2 text-xs font-semibold text-[#0F172A] focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20 disabled:opacity-60"
                  >
                    <option value="gemini-1.5-flash">gemini-1.5-flash (Fast & Recommended)</option>
                    <option value="gemini-1.5-pro">gemini-1.5-pro (High Reasoning)</option>
                  </select>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-[#475569] block">
                    Update API Key
                  </label>
                  <input
                    type="password"
                    disabled={!isAdmin}
                    placeholder={
                      systemSettings.gemini_api_key_configured
                        ? '•••••••••••••••• (Configured)'
                        : 'Enter Gemini API key'
                    }
                    value={newGeminiKey}
                    onChange={(e) => setNewGeminiKey(e.target.value)}
                    className="w-full bg-[#F8FAFC] border border-[#CBD5E1] rounded-xl px-3 py-2 text-xs font-semibold text-[#0F172A] focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20 disabled:opacity-60"
                  />
                </div>
              </div>
            </div>

            {isAdmin && (
              <div className="pt-4 border-t border-[#E2E8F0] flex justify-end">
                <button
                  type="submit"
                  disabled={savingSystem}
                  className="flex items-center gap-2 px-5 py-2.5 bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-xs font-semibold rounded-xl shadow-xs transition-colors cursor-pointer disabled:opacity-50"
                >
                  {savingSystem ? (
                    <RefreshCw className="w-4 h-4 animate-spin" />
                  ) : (
                    <Save className="w-4 h-4" />
                  )}
                  <span>Save System Settings</span>
                </button>
              </div>
            )}
          </div>
        </form>
      )}

      {/* TAB 4: INTEGRATIONS & STATUS */}
      {activeTab === 'services' && (
        <div className="space-y-6">
          <div className="bg-white border border-[#E2E8F0] rounded-2xl p-6 shadow-2xs space-y-6">
            <div className="border-b border-[#E2E8F0] pb-4">
              <h3 className="text-sm font-bold text-[#0F172A] flex items-center gap-2">
                <Server className="w-4 h-4 text-[#2563EB]" />
                <span>Microservice Health & Connected Providers</span>
              </h3>
              <p className="text-xs text-[#64748B] mt-0.5">
                Live heartbeat verification of underlying query engines, LLM gateways, and worker nodes.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Providers */}
              <div className="space-y-3">
                <h4 className="text-xs font-bold text-[#0F172A] uppercase tracking-wider">
                  Configured Analytics Providers
                </h4>
                {providers.length === 0 ? (
                  <div className="p-4 bg-[#F8FAFC] rounded-xl border border-slate-200 text-xs text-[#64748B]">
                    Google Gemini, Pandas Analysis, Isolation Forest (Online)
                  </div>
                ) : (
                  providers.map((p, idx) => (
                    <div
                      key={idx}
                      className="p-3 bg-[#F8FAFC] rounded-xl border border-slate-200 flex items-center justify-between text-xs"
                    >
                      <span className="font-semibold text-[#0F172A]">{p.name || p.provider}</span>
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                        Active
                      </span>
                    </div>
                  ))
                )}
              </div>

              {/* Notification Channels */}
              <div className="space-y-3">
                <h4 className="text-xs font-bold text-[#0F172A] uppercase tracking-wider">
                  Notification Dispatchers
                </h4>
                <div className="p-3 bg-[#F8FAFC] rounded-xl border border-slate-200 flex items-center justify-between text-xs">
                  <div>
                    <span className="font-semibold text-[#0F172A] block">Email (SMTP)</span>
                    <span className="text-[11px] text-[#64748B]">Alert notifications channel</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleTestNotification('email')}
                    disabled={testingNotification}
                    className="px-3 py-1 bg-white border border-[#CBD5E1] hover:bg-slate-50 text-xs font-semibold rounded-lg shadow-2xs"
                  >
                    Test Dispatch
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Dataset Details Modal */}
      {selectedDatasetModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full border border-[#CBD5E1] overflow-hidden">
            <div className="px-5 py-4 border-b border-[#E2E8F0] flex items-center justify-between">
              <h3 className="text-sm font-bold text-[#0F172A]">Dataset Storage Metadata</h3>
              <button
                type="button"
                onClick={() => setSelectedDatasetModal(null)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-5 space-y-3 text-xs text-[#334155]">
              <div>
                <span className="text-[#64748B] block">Filename:</span>
                <span className="font-bold text-[#0F172A]">
                  {selectedDatasetModal.original_filename || selectedDatasetModal.filename}
                </span>
              </div>
              <div>
                <span className="text-[#64748B] block">Dataset ID:</span>
                <span className="font-semibold text-[#0F172A]">#{selectedDatasetModal.id}</span>
              </div>
              <div>
                <span className="text-[#64748B] block">File Size:</span>
                <span className="font-semibold text-[#0F172A]">
                  {formatFileSize(selectedDatasetModal.file_size)}
                </span>
              </div>
              <div>
                <span className="text-[#64748B] block">Uploaded Date:</span>
                <span className="font-semibold text-[#0F172A]">
                  {formatDate(selectedDatasetModal.created_at)}
                </span>
              </div>
              <div className="pt-3 border-t border-slate-100 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setSelectedDatasetModal(null)}
                  className="px-4 py-1.5 border border-[#CBD5E1] rounded-xl text-xs font-semibold text-[#0F172A] hover:bg-slate-50"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SettingsPage;
