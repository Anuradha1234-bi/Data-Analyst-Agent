import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  User,
  Mail,
  Calendar,
  Shield,
  Edit3,
  TrendingUp,
  Database,
  FileText,
  Zap,
  Key,
  Settings,
  Trash2,
  Lock,
  Camera,
  Check,
  CheckCircle2,
  SlidersHorizontal,
  Link as LinkIcon,
  Sparkles,
  Activity,
  AlertCircle,
  X,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { datasetService } from '../services/datasetService';

export const ProfilePage = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  // Active Tab state
  const [activeTab, setActiveTab] = useState('personal'); // 'personal', 'settings', 'preferences', 'security', 'api'

  // User details state (with fallback to Ani / anu@gmail.com matching screenshot)
  const [fullName, setFullName] = useState(() => user?.full_name || user?.name || user?.username || 'Ani');
  const [email, setEmail] = useState(() => user?.email || 'anu@gmail.com');
  const [role, setRole] = useState(() => user?.role || 'Data Analyst');
  const [memberSince] = useState('October 14, 2026');

  // Metrics
  const [datasetCount, setDatasetCount] = useState(5);
  const [analysesCount] = useState(12);
  const [reportsCount] = useState(6);
  const [daysActive] = useState(7);

  // Security & 2FA state
  const [twoFactorEnabled, setTwoFactorEnabled] = useState(false);

  // Modals
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [passwordModalOpen, setPasswordModalOpen] = useState(false);
  const [emailModalOpen, setEmailModalOpen] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);

  // Edit form state
  const [editName, setEditName] = useState(fullName);
  const [editEmail, setEditEmail] = useState(email);
  const [successToast, setSuccessToast] = useState('');

  // Password form state
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordError, setPasswordError] = useState('');

  // Fetch real dataset count if available
  useEffect(() => {
    const loadDatasets = async () => {
      try {
        const list = await datasetService.getDatasets();
        if (list && list.length > 0) {
          setDatasetCount(list.length);
        }
      } catch {
        // Fallback default from screenshot
      }
    };
    loadDatasets();
  }, []);

  // Save profile changes
  const handleSaveProfile = (e) => {
    e.preventDefault();
    setFullName(editName.trim() || 'Ani');
    setEmail(editEmail.trim() || 'anu@gmail.com');
    setEditModalOpen(false);
    setSuccessToast('Profile information updated successfully.');
    setTimeout(() => setSuccessToast(''), 3500);

    // Persist to user in localStorage
    try {
      const saved = localStorage.getItem('user');
      if (saved) {
        const parsed = JSON.parse(saved);
        parsed.full_name = editName.trim();
        parsed.email = editEmail.trim();
        localStorage.setItem('user', JSON.stringify(parsed));
      }
    } catch {
      // Ignored
    }
  };

  // Handle password update
  const handleUpdatePassword = (e) => {
    e.preventDefault();
    if (!currentPassword) {
      setPasswordError('Please enter your current password.');
      return;
    }
    if (newPassword.length < 6) {
      setPasswordError('New password must be at least 6 characters.');
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordError('New passwords do not match.');
      return;
    }
    setPasswordError('');
    setPasswordModalOpen(false);
    setCurrentPassword('');
    setNewPassword('');
    setConfirmPassword('');
    setSuccessToast('Password updated successfully.');
    setTimeout(() => setSuccessToast(''), 3500);
  };

  const displayInitial = (fullName || 'A').charAt(0).toUpperCase();

  return (
    <div className="w-full space-y-5 font-sans text-[#0F172A] pb-10">
      {/* Success Notification Banner */}
      {successToast && (
        <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center justify-between shadow-2xs">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span className="font-semibold">{successToast}</span>
          </div>
          <button
            onClick={() => setSuccessToast('')}
            className="text-emerald-500 hover:text-emerald-700 cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* 1. Top Decorative Banner */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-[#EFF6FF] via-[#E0E7FF] to-[#DBEAFE] border border-[#BFDBFE] p-7 shadow-2xs">
        <div className="relative z-10 max-w-xl">
          <h1 className="text-2xl font-bold tracking-tight text-[#0F172A]">
            User Account Profile
          </h1>
          <p className="text-xs text-[#475569] mt-1.5 leading-relaxed">
            Manage your personal information, preferences, and authentication credentials.
          </p>
        </div>

        {/* 3D Stylized Graphic Illustration on the right */}
        <div className="absolute right-6 top-1/2 -translate-y-1/2 pointer-events-none hidden md:block">
          <div className="relative w-48 h-28 flex items-center justify-center">
            {/* Background glowing orbs */}
            <div className="absolute -top-3 -right-3 w-16 h-16 rounded-full bg-blue-300/40 blur-md"></div>
            <div className="absolute -bottom-2 -left-2 w-14 h-14 rounded-full bg-indigo-300/40 blur-md"></div>

            {/* 3D Floating Credential Card */}
            <div className="relative w-40 h-24 rounded-2xl bg-gradient-to-br from-white/95 to-white/70 border border-white/80 shadow-lg backdrop-blur-xs p-3 flex flex-col justify-between -rotate-3 transform hover:rotate-0 transition-transform">
              <div className="flex items-center justify-between">
                <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-[#1E6BFF] to-[#60A5FA] flex items-center justify-center text-white shadow-xs">
                  <User className="w-5 h-5" />
                </div>
                <div className="space-y-1">
                  <div className="w-16 h-2 rounded-full bg-slate-200"></div>
                  <div className="w-10 h-1.5 rounded-full bg-slate-200"></div>
                </div>
              </div>
              <div className="space-y-1 pt-1 border-t border-slate-100">
                <div className="w-24 h-1.5 rounded-full bg-blue-200"></div>
                <div className="w-16 h-1 rounded-full bg-slate-200"></div>
              </div>
            </div>

            {/* Blue Decorative Gear Cog */}
            <div className="absolute -bottom-1 right-2 w-11 h-11 rounded-2xl bg-gradient-to-tr from-[#2563EB] to-[#3B82F6] text-white flex items-center justify-center shadow-md rotate-12">
              <Settings className="w-6 h-6 animate-spin-slow" />
            </div>

            {/* Floating Soft Spheres */}
            <div className="absolute -top-2 left-6 w-5 h-5 rounded-full bg-gradient-to-br from-blue-400 to-indigo-500 opacity-80 shadow-xs"></div>
            <div className="absolute bottom-1 -left-3 w-3.5 h-3.5 rounded-full bg-sky-400 opacity-70"></div>
          </div>
        </div>
      </div>

      {/* 2. User Overview & Quick KPI Cards */}
      <div className="bg-white border border-[#E2E8F0] rounded-2xl p-6 shadow-2xs">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          {/* Left: User Avatar & Details */}
          <div className="flex items-center gap-5">
            {/* Avatar with Camera Overlay */}
            <div className="relative group shrink-0">
              <div className="w-20 h-20 rounded-full bg-[#1E6BFF] text-white flex items-center justify-center font-bold text-3xl shadow-sm">
                {displayInitial}
              </div>
              <button
                type="button"
                onClick={() => setEditModalOpen(true)}
                title="Change Avatar"
                className="absolute bottom-0 right-0 w-6 h-6 rounded-full bg-[#0F172A] border-2 border-white text-white flex items-center justify-center hover:bg-slate-800 transition-colors cursor-pointer shadow-xs"
              >
                <Camera className="w-3.5 h-3.5" />
              </button>
            </div>

            {/* User Meta Information */}
            <div className="space-y-1">
              <div className="flex items-center gap-2.5">
                <h2 className="text-xl font-bold text-[#0F172A]">{fullName}</h2>
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-[#ECFDF5] text-[#16A34A] border border-[#A7F3D0]">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#16A34A]"></span>
                  <span>Active</span>
                </span>
              </div>
              <p className="text-xs text-[#64748B]">{email}</p>
              <p className="text-xs text-[#64748B]">Member since {memberSince}</p>

              <div className="pt-1">
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md text-xs font-semibold bg-[#EFF6FF] text-[#2563EB] border border-[#BFDBFE]">
                  <Activity className="w-3.5 h-3.5 text-[#2563EB]" />
                  <span>{role}</span>
                </span>
              </div>
            </div>
          </div>

          {/* Right: 4 Stat Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 lg:w-auto w-full">
            {/* Stat 1: Datasets Uploaded */}
            <div className="p-3.5 bg-[#EFF6FF]/60 border border-[#DBEAFE] rounded-xl flex items-center gap-3 shadow-2xs">
              <div className="w-9 h-9 rounded-lg bg-white text-[#2563EB] flex items-center justify-center shrink-0 shadow-2xs">
                <Database className="w-4 h-4" />
              </div>
              <div>
                <div className="text-xl font-black text-[#0F172A] leading-tight">{datasetCount}</div>
                <span className="text-[10px] font-semibold text-[#64748B] block truncate">
                  Datasets Uploaded
                </span>
              </div>
            </div>

            {/* Stat 2: Analyses Run */}
            <div className="p-3.5 bg-[#F0FDF4]/60 border border-[#DCFCE7] rounded-xl flex items-center gap-3 shadow-2xs">
              <div className="w-9 h-9 rounded-lg bg-white text-[#16A34A] flex items-center justify-center shrink-0 shadow-2xs">
                <TrendingUp className="w-4 h-4" />
              </div>
              <div>
                <div className="text-xl font-black text-[#0F172A] leading-tight">{analysesCount}</div>
                <span className="text-[10px] font-semibold text-[#64748B] block truncate">
                  Analyses Run
                </span>
              </div>
            </div>

            {/* Stat 3: Reports Generated */}
            <div className="p-3.5 bg-[#FFFBEB]/60 border border-[#FEF3C7] rounded-xl flex items-center gap-3 shadow-2xs">
              <div className="w-9 h-9 rounded-lg bg-white text-[#D97706] flex items-center justify-center shrink-0 shadow-2xs">
                <FileText className="w-4 h-4" />
              </div>
              <div>
                <div className="text-xl font-black text-[#0F172A] leading-tight">{reportsCount}</div>
                <span className="text-[10px] font-semibold text-[#64748B] block truncate">
                  Reports Generated
                </span>
              </div>
            </div>

            {/* Stat 4: Days Active */}
            <div className="p-3.5 bg-[#FAF5FF]/60 border border-[#F3E8FF] rounded-xl flex items-center gap-3 shadow-2xs">
              <div className="w-9 h-9 rounded-lg bg-white text-[#9333EA] flex items-center justify-center shrink-0 shadow-2xs">
                <Calendar className="w-4 h-4" />
              </div>
              <div>
                <div className="text-xl font-black text-[#0F172A] leading-tight">{daysActive}</div>
                <span className="text-[10px] font-semibold text-[#64748B] block truncate">
                  Days Active
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 3. Horizontal Tab Navigation Bar */}
      <div className="border-b border-[#E2E8F0] flex items-center gap-6 overflow-x-auto text-xs font-semibold select-none">
        <button
          type="button"
          onClick={() => setActiveTab('personal')}
          className={`flex items-center gap-2 pb-3 transition-colors cursor-pointer whitespace-nowrap border-b-2 ${
            activeTab === 'personal'
              ? 'border-[#1E6BFF] text-[#1E6BFF]'
              : 'border-transparent text-[#64748B] hover:text-[#0F172A]'
          }`}
        >
          <User className="w-4 h-4" />
          <span>Personal Information</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('settings')}
          className={`flex items-center gap-2 pb-3 transition-colors cursor-pointer whitespace-nowrap border-b-2 ${
            activeTab === 'settings'
              ? 'border-[#1E6BFF] text-[#1E6BFF]'
              : 'border-transparent text-[#64748B] hover:text-[#0F172A]'
          }`}
        >
          <Settings className="w-4 h-4" />
          <span>Account Settings</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('preferences')}
          className={`flex items-center gap-2 pb-3 transition-colors cursor-pointer whitespace-nowrap border-b-2 ${
            activeTab === 'preferences'
              ? 'border-[#1E6BFF] text-[#1E6BFF]'
              : 'border-transparent text-[#64748B] hover:text-[#0F172A]'
          }`}
        >
          <SlidersHorizontal className="w-4 h-4" />
          <span>Preferences</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('security')}
          className={`flex items-center gap-2 pb-3 transition-colors cursor-pointer whitespace-nowrap border-b-2 ${
            activeTab === 'security'
              ? 'border-[#1E6BFF] text-[#1E6BFF]'
              : 'border-transparent text-[#64748B] hover:text-[#0F172A]'
          }`}
        >
          <Shield className="w-4 h-4" />
          <span>Security</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('api')}
          className={`flex items-center gap-2 pb-3 transition-colors cursor-pointer whitespace-nowrap border-b-2 ${
            activeTab === 'api'
              ? 'border-[#1E6BFF] text-[#1E6BFF]'
              : 'border-transparent text-[#64748B] hover:text-[#0F172A]'
          }`}
        >
          <LinkIcon className="w-4 h-4" />
          <span>API & Integrations</span>
        </button>
      </div>

      {/* 4. Tab Content: Personal Information & Dashboard Layout */}
      {activeTab === 'personal' && (
        <div className="space-y-5">
          {/* Row 1: Personal Information & Account Activity */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            {/* Left Card: Personal Information Form */}
            <div className="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-2xs space-y-4">
              <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                <div className="flex items-center gap-2">
                  <div className="w-7 h-7 rounded-lg bg-[#EFF6FF] text-[#2563EB] flex items-center justify-center">
                    <User className="w-4 h-4" />
                  </div>
                  <h3 className="text-sm font-bold text-[#0F172A]">Personal Information</h3>
                </div>

                <button
                  type="button"
                  onClick={() => {
                    setEditName(fullName);
                    setEditEmail(email);
                    setEditModalOpen(true);
                  }}
                  className="flex items-center gap-1.5 px-3 py-1 bg-white border border-[#CBD5E1] hover:bg-slate-50 text-[#2563EB] text-xs font-semibold rounded-lg shadow-2xs transition-colors cursor-pointer"
                >
                  <Edit3 className="w-3.5 h-3.5" />
                  <span>Edit</span>
                </button>
              </div>

              {/* Form Input style rows */}
              <div className="space-y-3">
                {/* Full Name */}
                <div className="flex flex-col sm:flex-row sm:items-center gap-2">
                  <div className="w-36 flex items-center gap-2 text-xs font-medium text-[#64748B]">
                    <User className="w-4 h-4 text-[#94A3B8]" />
                    <span>Full Name</span>
                  </div>
                  <div className="flex-1 bg-[#F8FAFC] border border-[#CBD5E1]/70 rounded-xl px-3.5 py-2 text-xs font-semibold text-[#0F172A]">
                    {fullName}
                  </div>
                </div>

                {/* Email Address */}
                <div className="flex flex-col sm:flex-row sm:items-center gap-2">
                  <div className="w-36 flex items-center gap-2 text-xs font-medium text-[#64748B]">
                    <Mail className="w-4 h-4 text-[#94A3B8]" />
                    <span>Email Address</span>
                  </div>
                  <div className="flex-1 bg-[#F8FAFC] border border-[#CBD5E1]/70 rounded-xl px-3.5 py-2 text-xs font-semibold text-[#0F172A]">
                    {email}
                  </div>
                </div>

                {/* Member Since */}
                <div className="flex flex-col sm:flex-row sm:items-center gap-2">
                  <div className="w-36 flex items-center gap-2 text-xs font-medium text-[#64748B]">
                    <Calendar className="w-4 h-4 text-[#94A3B8]" />
                    <span>Member Since</span>
                  </div>
                  <div className="flex-1 bg-[#F8FAFC] border border-[#CBD5E1]/70 rounded-xl px-3.5 py-2 text-xs font-semibold text-[#0F172A]">
                    {memberSince}
                  </div>
                </div>

                {/* Account Status */}
                <div className="flex flex-col sm:flex-row sm:items-center gap-2">
                  <div className="w-36 flex items-center gap-2 text-xs font-medium text-[#64748B]">
                    <Shield className="w-4 h-4 text-[#94A3B8]" />
                    <span>Account Status</span>
                  </div>
                  <div className="flex-1 py-1">
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-[#ECFDF5] text-[#16A34A] border border-[#A7F3D0]">
                      <Check className="w-3.5 h-3.5 stroke-[3]" />
                      <span>Active</span>
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Right Card: Account Activity Timeline */}
            <div className="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-2xs space-y-3.5">
              <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                <div className="flex items-center gap-2">
                  <div className="w-7 h-7 rounded-lg bg-[#EFF6FF] text-[#2563EB] flex items-center justify-center">
                    <TrendingUp className="w-4 h-4" />
                  </div>
                  <h3 className="text-sm font-bold text-[#0F172A]">Account Activity</h3>
                </div>

                <button
                  type="button"
                  onClick={() => navigate('/history')}
                  className="text-xs font-semibold text-[#2563EB] hover:underline cursor-pointer"
                >
                  View All Activity
                </button>
              </div>

              {/* Timeline Items */}
              <div className="space-y-3">
                {/* Activity 1 */}
                <div className="flex items-start gap-3">
                  <div className="w-7 h-7 rounded-full bg-[#EFF6FF] text-[#2563EB] flex items-center justify-center shrink-0 mt-0.5">
                    <FileText className="w-3.5 h-3.5" />
                  </div>
                  <div className="w-24 shrink-0 text-xs text-[#64748B]">Oct 21, 2026</div>
                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-bold text-[#0F172A]">Generated analytical report</div>
                    <p className="text-[11px] text-[#64748B]">
                      Executive report for clean_customer_orders.csv
                    </p>
                  </div>
                </div>

                {/* Activity 2 */}
                <div className="flex items-start gap-3">
                  <div className="w-7 h-7 rounded-full bg-[#FFFBEB] text-[#D97706] flex items-center justify-center shrink-0 mt-0.5">
                    <TrendingUp className="w-3.5 h-3.5" />
                  </div>
                  <div className="w-24 shrink-0 text-xs text-[#64748B]">Oct 20, 2026</div>
                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-bold text-[#0F172A]">Ran predictive model</div>
                    <p className="text-[11px] text-[#64748B]">Random Forest (Time Series)</p>
                  </div>
                </div>

                {/* Activity 3 */}
                <div className="flex items-start gap-3">
                  <div className="w-7 h-7 rounded-full bg-[#EFF6FF] text-[#2563EB] flex items-center justify-center shrink-0 mt-0.5">
                    <Database className="w-3.5 h-3.5" />
                  </div>
                  <div className="w-24 shrink-0 text-xs text-[#64748B]">Oct 19, 2026</div>
                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-bold text-[#0F172A]">Uploaded dataset</div>
                    <p className="text-[11px] text-[#64748B]">clean_customer_orders (2).csv</p>
                  </div>
                </div>

                {/* Activity 4 */}
                <div className="flex items-start gap-3">
                  <div className="w-7 h-7 rounded-full bg-[#ECFDF5] text-[#059669] flex items-center justify-center shrink-0 mt-0.5">
                    <Sparkles className="w-3.5 h-3.5" />
                  </div>
                  <div className="w-24 shrink-0 text-xs text-[#64748B]">Oct 18, 2026</div>
                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-bold text-[#0F172A]">Performed data cleaning</div>
                    <p className="text-[11px] text-[#64748B]">Handled missing values and duplicates</p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Row 2: Quick Actions & Account Security */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            {/* Left Card: Quick Actions */}
            <div className="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-2xs space-y-3.5">
              <div className="flex items-center gap-2 pb-2 border-b border-slate-100">
                <div className="w-7 h-7 rounded-lg bg-[#EFF6FF] text-[#2563EB] flex items-center justify-center">
                  <Zap className="w-4 h-4" />
                </div>
                <h3 className="text-sm font-bold text-[#0F172A]">Quick Actions</h3>
              </div>

              {/* 4 Interactive Tiles */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {/* Tile 1: Change Password */}
                <div
                  onClick={() => setPasswordModalOpen(true)}
                  className="p-3 bg-[#F8FAFC] border border-[#E2E8F0] hover:border-[#2563EB] hover:bg-white rounded-xl transition-all cursor-pointer shadow-2xs space-y-1.5"
                >
                  <div className="w-7 h-7 rounded-lg bg-[#EFF6FF] text-[#2563EB] flex items-center justify-center">
                    <Key className="w-3.5 h-3.5" />
                  </div>
                  <div className="text-xs font-bold text-[#0F172A]">Change Password</div>
                  <p className="text-[10px] text-[#64748B] leading-tight">Update your password</p>
                </div>

                {/* Tile 2: Update Email */}
                <div
                  onClick={() => setEmailModalOpen(true)}
                  className="p-3 bg-[#F8FAFC] border border-[#E2E8F0] hover:border-[#059669] hover:bg-white rounded-xl transition-all cursor-pointer shadow-2xs space-y-1.5"
                >
                  <div className="w-7 h-7 rounded-lg bg-[#ECFDF5] text-[#059669] flex items-center justify-center">
                    <Mail className="w-3.5 h-3.5" />
                  </div>
                  <div className="text-xs font-bold text-[#0F172A]">Update Email</div>
                  <p className="text-[10px] text-[#64748B] leading-tight">Modify your email address</p>
                </div>

                {/* Tile 3: Account Settings */}
                <div
                  onClick={() => navigate('/settings')}
                  className="p-3 bg-[#F8FAFC] border border-[#E2E8F0] hover:border-[#9333EA] hover:bg-white rounded-xl transition-all cursor-pointer shadow-2xs space-y-1.5"
                >
                  <div className="w-7 h-7 rounded-lg bg-[#FAF5FF] text-[#9333EA] flex items-center justify-center">
                    <Settings className="w-3.5 h-3.5" />
                  </div>
                  <div className="text-xs font-bold text-[#0F172A]">Account Settings</div>
                  <p className="text-[10px] text-[#64748B] leading-tight">Manage preferences</p>
                </div>

                {/* Tile 4: Delete Account */}
                <div
                  onClick={() => setDeleteModalOpen(true)}
                  className="p-3 bg-[#F8FAFC] border border-[#E2E8F0] hover:border-[#DC2626] hover:bg-white rounded-xl transition-all cursor-pointer shadow-2xs space-y-1.5"
                >
                  <div className="w-7 h-7 rounded-lg bg-[#FEF2F2] text-[#DC2626] flex items-center justify-center">
                    <Trash2 className="w-3.5 h-3.5" />
                  </div>
                  <div className="text-xs font-bold text-[#0F172A]">Delete Account</div>
                  <p className="text-[10px] text-[#64748B] leading-tight">Permanently remove your account</p>
                </div>
              </div>
            </div>

            {/* Right Card: Account Security */}
            <div className="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-2xs space-y-3.5">
              <div className="flex items-center gap-2 pb-2 border-b border-slate-100">
                <div className="w-7 h-7 rounded-lg bg-[#EFF6FF] text-[#2563EB] flex items-center justify-center">
                  <Shield className="w-4 h-4" />
                </div>
                <h3 className="text-sm font-bold text-[#0F172A]">Account Security</h3>
              </div>

              {/* Security Items */}
              <div className="space-y-3">
                {/* Item 1: Password Status */}
                <div className="flex items-center justify-between p-3 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0]">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-[#ECFDF5] text-[#16A34A] flex items-center justify-center shrink-0">
                      <Lock className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="text-xs font-bold text-[#0F172A]">Password Status</div>
                      <p className="text-[11px] text-[#64748B]">Last updated 30 days ago</p>
                    </div>
                  </div>

                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-[#ECFDF5] text-[#16A34A] border border-[#A7F3D0]">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#16A34A]"></span>
                    <span>Secure</span>
                  </span>
                </div>

                {/* Item 2: Two-Factor Authentication */}
                <div className="flex items-center justify-between p-3 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0]">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-[#EFF6FF] text-[#2563EB] flex items-center justify-center shrink-0">
                      <Shield className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="text-xs font-bold text-[#0F172A]">Two-Factor Authentication</div>
                      <p className="text-[11px] text-[#64748B]">Add an extra layer of security</p>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => {
                      setTwoFactorEnabled(!twoFactorEnabled);
                      setSuccessToast(
                        !twoFactorEnabled
                          ? 'Two-Factor Authentication enabled.'
                          : 'Two-Factor Authentication disabled.'
                      );
                      setTimeout(() => setSuccessToast(''), 3000);
                    }}
                    className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold border transition-colors cursor-pointer ${
                      twoFactorEnabled
                        ? 'bg-[#ECFDF5] text-[#16A34A] border-[#A7F3D0]'
                        : 'bg-[#FFFBEB] text-[#D97706] border-[#FEF3C7]'
                    }`}
                  >
                    <span
                      className={`w-1.5 h-1.5 rounded-full ${
                        twoFactorEnabled ? 'bg-[#16A34A]' : 'bg-[#D97706]'
                      }`}
                    ></span>
                    <span>{twoFactorEnabled ? 'Enabled' : 'Not Enabled'}</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Other Tabs Support */}
      {activeTab === 'settings' && (
        <div className="bg-white border border-[#E2E8F0] rounded-2xl p-6 shadow-2xs space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-[#0F172A]">Application & Workspace Settings</h3>
              <p className="text-xs text-[#64748B] mt-0.5">
                Configure your default analytics workflow and workspace environment.
              </p>
            </div>
            <button
              onClick={() => navigate('/settings')}
              className="px-4 py-2 bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-xs font-semibold rounded-xl shadow-2xs"
            >
              Open Full System Settings
            </button>
          </div>
        </div>
      )}

      {activeTab === 'preferences' && (
        <div className="bg-white border border-[#E2E8F0] rounded-2xl p-6 shadow-2xs space-y-4">
          <h3 className="text-sm font-bold text-[#0F172A]">Notification & Visualization Preferences</h3>
          <p className="text-xs text-[#64748B]">
            Customize automated insight alerts, report generation formats, and chart color themes.
          </p>
        </div>
      )}

      {activeTab === 'security' && (
        <div className="bg-white border border-[#E2E8F0] rounded-2xl p-6 shadow-2xs space-y-4">
          <h3 className="text-sm font-bold text-[#0F172A]">Security & Login Sessions</h3>
          <p className="text-xs text-[#64748B]">
            Manage active browser tokens, recent IP access history, and session timeouts.
          </p>
        </div>
      )}

      {activeTab === 'api' && (
        <div className="bg-white border border-[#E2E8F0] rounded-2xl p-6 shadow-2xs space-y-4">
          <h3 className="text-sm font-bold text-[#0F172A]">API Keys & Webhooks</h3>
          <p className="text-xs text-[#64748B]">
            Connect external data pipelines, BI exporters, and LLM integrations.
          </p>
        </div>
      )}

      {/* Modal 1: Edit Profile Information */}
      {editModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full border border-[#CBD5E1] overflow-hidden">
            <div className="px-5 py-4 border-b border-[#E2E8F0] flex items-center justify-between">
              <h3 className="text-sm font-bold text-[#0F172A]">Edit Personal Information</h3>
              <button
                onClick={() => setEditModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <form onSubmit={handleSaveProfile} className="p-5 space-y-3.5">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-[#475569]">Full Name</label>
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  className="w-full bg-[#F8FAFC] border border-[#CBD5E1] rounded-xl px-3 py-2 text-xs font-medium text-[#0F172A] focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20"
                  required
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-[#475569]">Email Address</label>
                <input
                  type="email"
                  value={editEmail}
                  onChange={(e) => setEditEmail(e.target.value)}
                  className="w-full bg-[#F8FAFC] border border-[#CBD5E1] rounded-xl px-3 py-2 text-xs font-medium text-[#0F172A] focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20"
                  required
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setEditModalOpen(false)}
                  className="px-4 py-2 border border-[#CBD5E1] rounded-xl text-xs font-semibold text-[#64748B] hover:bg-slate-50 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-xs font-semibold rounded-xl shadow-2xs cursor-pointer"
                >
                  Save Changes
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal 2: Change Password */}
      {passwordModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full border border-[#CBD5E1] overflow-hidden">
            <div className="px-5 py-4 border-b border-[#E2E8F0] flex items-center justify-between">
              <h3 className="text-sm font-bold text-[#0F172A]">Change Password</h3>
              <button
                onClick={() => setPasswordModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <form onSubmit={handleUpdatePassword} className="p-5 space-y-3.5">
              {passwordError && (
                <div className="p-2.5 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>{passwordError}</span>
                </div>
              )}

              <div className="space-y-1">
                <label className="text-xs font-semibold text-[#475569]">Current Password</label>
                <input
                  type="password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  className="w-full bg-[#F8FAFC] border border-[#CBD5E1] rounded-xl px-3 py-2 text-xs font-medium text-[#0F172A] focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20"
                  required
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-[#475569]">New Password</label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="w-full bg-[#F8FAFC] border border-[#CBD5E1] rounded-xl px-3 py-2 text-xs font-medium text-[#0F172A] focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20"
                  required
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-[#475569]">Confirm New Password</label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full bg-[#F8FAFC] border border-[#CBD5E1] rounded-xl px-3 py-2 text-xs font-medium text-[#0F172A] focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20"
                  required
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setPasswordModalOpen(false)}
                  className="px-4 py-2 border border-[#CBD5E1] rounded-xl text-xs font-semibold text-[#64748B] hover:bg-slate-50 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-xs font-semibold rounded-xl shadow-2xs cursor-pointer"
                >
                  Update Password
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal 3: Update Email */}
      {emailModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full border border-[#CBD5E1] overflow-hidden">
            <div className="px-5 py-4 border-b border-[#E2E8F0] flex items-center justify-between">
              <h3 className="text-sm font-bold text-[#0F172A]">Update Email Address</h3>
              <button
                onClick={() => setEmailModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                setEmailModalOpen(false);
                setSuccessToast('Verification email sent to update your address.');
                setTimeout(() => setSuccessToast(''), 3500);
              }}
              className="p-5 space-y-3.5"
            >
              <div className="space-y-1">
                <label className="text-xs font-semibold text-[#475569]">New Email Address</label>
                <input
                  type="email"
                  defaultValue={email}
                  className="w-full bg-[#F8FAFC] border border-[#CBD5E1] rounded-xl px-3 py-2 text-xs font-medium text-[#0F172A] focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20"
                  required
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setEmailModalOpen(false)}
                  className="px-4 py-2 border border-[#CBD5E1] rounded-xl text-xs font-semibold text-[#64748B] hover:bg-slate-50 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-xs font-semibold rounded-xl shadow-2xs cursor-pointer"
                >
                  Send Verification
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal 4: Delete Account Confirmation */}
      {deleteModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full border border-red-200 overflow-hidden">
            <div className="px-5 py-4 border-b border-red-100 bg-red-50/50 flex items-center justify-between">
              <h3 className="text-sm font-bold text-red-700">Delete Account Confirmation</h3>
              <button
                onClick={() => setDeleteModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-5 space-y-4 text-xs text-[#475569]">
              <p>
                Are you sure you want to permanently delete your account? All datasets, cleanings,
                models, and executive reports associated with your profile will be removed.
              </p>
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setDeleteModalOpen(false)}
                  className="px-4 py-2 border border-[#CBD5E1] rounded-xl text-xs font-semibold text-[#64748B] hover:bg-slate-50 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={async () => {
                    setDeleteModalOpen(false);
                    await logout();
                    navigate('/login');
                  }}
                  className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-xs font-semibold rounded-xl shadow-2xs cursor-pointer"
                >
                  Permanently Delete
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ProfilePage;
