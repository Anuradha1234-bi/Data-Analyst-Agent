import React, { useState, useEffect, useRef } from 'react';
import { NavLink, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';
import {
  LayoutDashboard,
  UploadCloud,
  Database,
  FileSearch,
  ShieldCheck,
  Filter,
  MessageSquare,
  BarChart3,
  AlertTriangle,
  Sparkles,
  Lightbulb,
  FileText,
  Settings,
  History,
  LogOut,
  User as UserIcon,
  ChevronDown,
  ChevronRight,
  Bell,
  Search,
  X,
  Shield,
  Sun,
  Moon,
} from 'lucide-react';

// Navigation sections covering all existing application pages
const NAV_SECTIONS = [
  {
    title: 'Core Workspaces',
    items: [
      {
        name: 'Dashboard',
        path: '/dashboard',
        icon: LayoutDashboard,
        desc: 'Central intelligence metrics & dataset status',
        badge: 'Home',
      },
      {
        name: 'Data Analyst',
        path: '/data-analyst',
        icon: MessageSquare,
        desc: 'Autonomous AI analyst for instant NL queries',
        badge: 'AI Agent',
      },
      {
        name: 'Reports',
        path: '/reports',
        icon: FileText,
        desc: 'Executive summaries, KPI exports & downloads',
        badge: 'Reports',
      },
      {
        name: 'Upload Dataset',
        path: '/upload',
        icon: UploadCloud,
        desc: 'Ingest and validate new CSV & Excel files',
      },
    ],
  },
  {
    title: 'Data Management & Quality',
    items: [
      {
        name: 'Datasets',
        path: '/datasets',
        icon: Database,
        desc: 'Manage uploaded datasets, schemas & metadata',
      },
      {
        name: 'Data Profile',
        path: '/profile-data',
        icon: FileSearch,
        desc: 'Deep column profiling, distributions & stats',
      },
      {
        name: 'Data Quality',
        path: '/data-quality',
        icon: ShieldCheck,
        desc: 'Quality scores, validity metrics & null checks',
      },
      {
        name: 'Data Cleaning',
        path: '/data-cleaning',
        icon: Filter,
        desc: 'Imputations, deduplications & transforms',
      },
    ],
  },
  {
    title: 'Advanced AI & Analytics',
    items: [
      {
        name: 'Analytics',
        path: '/analytics',
        icon: BarChart3,
        desc: 'Cross-tabulations, aggregations & metrics',
      },
      {
        name: 'Anomalies',
        path: '/anomalies',
        icon: AlertTriangle,
        desc: 'Unsupervised outlier & pattern shift detection',
      },
      {
        name: 'Predictions',
        path: '/predictions',
        icon: Sparkles,
        desc: 'Automated ML forecasting & regression models',
      },
      {
        name: 'Insights',
        path: '/insights',
        icon: Lightbulb,
        desc: 'Automated business heuristics & takeaways',
      },
    ],
  },
  {
    title: 'System & Account',
    items: [
      {
        name: 'Analysis History',
        path: '/history',
        icon: History,
        desc: 'Audit trail of queries, jobs and executions',
      },
      {
        name: 'Account Settings',
        path: '/settings',
        icon: Settings,
        desc: 'Application configuration & API keys',
      },
      {
        name: 'User Profile',
        path: '/profile',
        icon: UserIcon,
        desc: 'Account details & role-based permissions',
      },
    ],
  },
];

export const Navbar = () => {
  const { user, logout } = useAuth();
  const { isDark, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();

  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [activeDropdown, setActiveDropdown] = useState(null); // 'profile' | null
  const [searchQuery, setSearchQuery] = useState('');

  const menuPanelRef = useRef(null);
  const hamburgerBtnRef = useRef(null);
  const profileDropdownRef = useRef(null);

  // Close menus and restore body scroll on route change
  useEffect(() => {
    setIsMenuOpen(false);
    setActiveDropdown(null);
  }, [location.pathname]);

  // Lock body scroll when hamburger menu is open to prevent background scrolling
  useEffect(() => {
    if (isMenuOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isMenuOpen]);

  // Close menus when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      // Close hamburger drawer if clicking outside the drawer and outside the hamburger toggle button
      if (
        isMenuOpen &&
        menuPanelRef.current &&
        !menuPanelRef.current.contains(event.target) &&
        hamburgerBtnRef.current &&
        !hamburgerBtnRef.current.contains(event.target)
      ) {
        setIsMenuOpen(false);
      }

      // Close profile dropdown if clicking outside
      if (
        profileDropdownRef.current &&
        !profileDropdownRef.current.contains(event.target)
      ) {
        setActiveDropdown(null);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isMenuOpen]);

  // Close on Escape key press
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        setIsMenuOpen(false);
        setActiveDropdown(null);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleLogout = async () => {
    setIsMenuOpen(false);
    setActiveDropdown(null);
    await logout();
    navigate('/login');
  };

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    const q = searchQuery.trim();
    if (q) {
      navigate(`/data-analyst?q=${encodeURIComponent(q)}`);
      setSearchQuery('');
      setIsMenuOpen(false);
    }
  };

  const isItemActive = (path) => {
    const current = location.pathname;
    if (path === '/dashboard') {
      return current === '/dashboard' || current === '/';
    }
    if (path === '/profile-data') {
      return current === '/profile-data' || current === '/profiling';
    }
    if (path === '/data-cleaning') {
      return current === '/data-cleaning' || current === '/cleaning';
    }
    if (path === '/data-analyst') {
      return current === '/data-analyst' || current === '/analysis' || current === '/ask-analyst';
    }
    if (path === '/predictions') {
      return current === '/predictions' || current === '/prediction';
    }
    return current === path;
  };

  const getActivePageLabel = () => {
    for (const section of NAV_SECTIONS) {
      for (const item of section.items) {
        if (isItemActive(item.path)) {
          return item.name;
        }
      }
    }
    return 'Dashboard';
  };

  const displayName = user?.full_name || user?.name || user?.username || 'Analyst';
  const displayEmail = user?.email || 'analyst@datanalyst.ai';
  const displayRole = user?.role || 'user';
  const displayInitial = (displayName || 'A').charAt(0).toUpperCase();

  return (
    <>
      {/* =========================================================================
          APPLICATION / DASHBOARD HEADER (No permanent top navbar or sidebar)
      ========================================================================= */}
      <header
        id="dashboard-header"
        className={`sticky top-0 z-40 w-full transition-colors duration-150 border-b select-none ${
          isDark
            ? 'bg-[#0B132B] text-white border-[#1E293B] shadow-sm'
            : 'bg-white text-[#0F172A] border-[#E2E8F0] shadow-xs'
        }`}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
          {/* =====================================================================
              LEFT SECTION: Three-line Hamburger Button (☰) & Brand Logo
          ===================================================================== */}
          <div className="flex items-center gap-3 shrink-0">
            {/* Three-line hamburger button (☰) visible on ALL viewports */}
            <button
              ref={hamburgerBtnRef}
              type="button"
              id="hamburger-nav-btn"
              onClick={() => setIsMenuOpen((prev) => !prev)}
              aria-expanded={isMenuOpen}
              aria-controls="collapsible-navigation-drawer"
              aria-label={isMenuOpen ? 'Close navigation menu' : 'Open navigation menu (☰)'}
              title={isMenuOpen ? 'Close navigation menu (Esc)' : 'Open navigation menu (☰)'}
              className={`relative flex items-center justify-center w-10 h-10 rounded-xl transition-all duration-200 cursor-pointer border ${
                isMenuOpen
                  ? 'bg-[#1E6BFF] text-white border-[#2563EB] shadow-md shadow-blue-500/25 ring-2 ring-blue-400/30'
                  : isDark
                  ? 'bg-[#131F3F] text-slate-200 border-[#1E293B] hover:text-white hover:border-[#2563EB]/70 hover:bg-[#182852]'
                  : 'bg-slate-50 text-slate-700 border-slate-200 hover:text-[#0F172A] hover:bg-slate-100 hover:border-slate-300'
              }`}
            >
              <span className="sr-only">Toggle navigation menu (☰)</span>
              {/* Three distinct lines representing the hamburger button (☰) */}
              <div className="w-5 h-4 flex flex-col justify-between items-center pointer-events-none">
                <span
                  className={`h-0.5 w-5 rounded-full transition-all duration-300 transform origin-center ${
                    isMenuOpen
                      ? 'rotate-45 translate-y-[7px] bg-white'
                      : isDark
                      ? 'bg-slate-200'
                      : 'bg-slate-700'
                  }`}
                />
                <span
                  className={`h-0.5 w-5 rounded-full transition-all duration-200 ${
                    isMenuOpen
                      ? 'opacity-0 bg-white'
                      : isDark
                      ? 'bg-slate-200'
                      : 'bg-slate-700'
                  }`}
                />
                <span
                  className={`h-0.5 w-5 rounded-full transition-all duration-300 transform origin-center ${
                    isMenuOpen
                      ? '-rotate-45 -translate-y-[7px] bg-white'
                      : isDark
                      ? 'bg-slate-200'
                      : 'bg-slate-700'
                  }`}
                />
              </div>
            </button>

            {/* Brand Logo & Title */}
            <NavLink
              to="/dashboard"
              className="flex items-center gap-2.5 group focus:outline-none"
              aria-label="AI Data Analyst Agent Dashboard"
            >
              <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-[#1D4ED8] to-[#2563EB] text-white flex items-center justify-center shadow-xs group-hover:scale-105 transition-transform shrink-0">
                <svg className="w-4 h-4 text-white" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M4 19h3v-7H4v7zm6 0h3V5h-3v14zm6 0h3v-10h-3v10z" />
                </svg>
              </div>
              <div>
                <div className="flex items-center gap-2 leading-tight">
                  <span
                    className={`font-bold text-sm sm:text-base tracking-tight transition-colors ${
                      isDark ? 'text-white group-hover:text-blue-100' : 'text-[#0F172A] group-hover:text-[#2563EB]'
                    }`}
                  >
                    AI Data Analyst
                  </span>
                  <span
                    className={`px-1.5 py-0.5 rounded text-[9px] font-mono font-bold uppercase tracking-wider hidden sm:inline-block border ${
                      isDark
                        ? 'bg-[#131F3F] text-[#60A5FA] border-[#2563EB]/40'
                        : 'bg-blue-50 text-[#2563EB] border-blue-200'
                    }`}
                  >
                    AGENT
                  </span>
                </div>
                <span
                  className={`text-[10px] hidden md:block leading-none mt-0.5 ${
                    isDark ? 'text-[#8D99AE]' : 'text-[#64748B]'
                  }`}
                >
                  Intelligent Analytics Workspace
                </span>
              </div>
            </NavLink>

            {/* Current Active View Pill in Header */}
            <div className="hidden sm:flex items-center gap-2 ml-1 pl-3 border-l border-[#1E293B]/40 dark:border-[#1E293B]">
              <span className="text-xs text-slate-400 font-mono">/</span>
              <span className="text-xs font-semibold px-2 py-0.5 rounded-lg bg-blue-500/10 text-blue-600 dark:text-[#60A5FA] border border-blue-500/20">
                {getActivePageLabel()}
              </span>
            </div>
          </div>

          {/* =====================================================================
              RIGHT SECTION: Search, API Badge, Notifications, Theme & Profile
          ===================================================================== */}
          <div className="flex items-center gap-2 sm:gap-2.5 shrink-0">
            {/* Quick Search Input */}
            <form onSubmit={handleSearchSubmit} className="hidden xl:flex items-center relative">
              <div
                className={`flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs w-52 focus-within:w-64 border transition-all ${
                  isDark
                    ? 'bg-[#131F3F] border-[#1E293B] text-slate-300 focus-within:border-[#2563EB] focus-within:bg-[#0E172E]'
                    : 'bg-slate-50 border-slate-200 text-[#0F172A] focus-within:border-[#2563EB] focus-within:bg-white'
                }`}
              >
                <Search className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Ask AI or search..."
                  className={`bg-transparent text-xs focus:outline-none w-full ${
                    isDark ? 'text-white placeholder-slate-400' : 'text-[#0F172A] placeholder-slate-400'
                  }`}
                />
                <kbd
                  className={`hidden sm:inline-block px-1 py-0.5 text-[9px] font-mono border rounded ${
                    isDark
                      ? 'text-slate-400 bg-[#0B132B] border-[#1E293B]'
                      : 'text-slate-500 bg-white border-slate-200'
                  }`}
                >
                  ↵
                </kbd>
              </div>
            </form>

            {/* FastAPI Connected Green Badge */}
            <div
              className={`hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[11px] font-medium ${
                isDark
                  ? 'bg-emerald-950/40 border-emerald-500/30 text-emerald-300'
                  : 'bg-emerald-50 border-emerald-200 text-emerald-700'
              }`}
              title="FastAPI server is connected and operational"
            >
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
              <span className="hidden md:inline">API Connected</span>
            </div>

            {/* Notification Bell */}
            <button
              type="button"
              className={`p-2 rounded-xl transition-colors relative cursor-pointer ${
                isDark
                  ? 'text-slate-400 hover:text-white hover:bg-[#1E293B]'
                  : 'text-slate-500 hover:text-[#0F172A] hover:bg-slate-100'
              }`}
              title="Notifications"
              aria-label="View notifications"
            >
              <Bell className="w-4 h-4" />
              <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-[#EF4444] rounded-full ring-2 ring-white dark:ring-[#0B132B]"></span>
            </button>

            {/* Theme Toggle Button (Light / Dark) */}
            <button
              type="button"
              onClick={toggleTheme}
              id="theme-toggle-btn"
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl border transition-all cursor-pointer shadow-2xs ${
                isDark
                  ? 'bg-[#131F3F] border-[#1E293B] text-[#60A5FA] hover:border-[#2563EB]/60 hover:bg-[#182852]'
                  : 'bg-slate-50 border-slate-200 text-amber-600 hover:bg-slate-100 hover:border-slate-300'
              }`}
              title={
                isDark
                  ? 'Current: Dark Mode — Click to switch to Light Mode'
                  : 'Current: Light Mode — Click to switch to Dark Mode'
              }
              aria-label={isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
            >
              {isDark ? (
                <>
                  <Moon className="w-4 h-4 text-[#60A5FA] fill-[#60A5FA]/20" />
                  <span className="text-xs font-semibold text-slate-200 hidden sm:inline">Dark</span>
                </>
              ) : (
                <>
                  <Sun className="w-4 h-4 text-amber-500 fill-amber-500/20" />
                  <span className="text-xs font-semibold text-slate-700 hidden sm:inline">Light</span>
                </>
              )}
            </button>

            {/* User Profile Menu Trigger */}
            <div className="relative" ref={profileDropdownRef}>
              <button
                type="button"
                id="user-profile-btn"
                onClick={() => setActiveDropdown((prev) => (prev === 'profile' ? null : 'profile'))}
                aria-expanded={activeDropdown === 'profile'}
                className={`flex items-center gap-2 p-1.5 sm:px-2.5 sm:py-1.5 rounded-xl border transition-all cursor-pointer ${
                  activeDropdown === 'profile'
                    ? isDark
                      ? 'bg-[#1E293B] border-[#2563EB]/50'
                      : 'bg-slate-100 border-[#2563EB]/50'
                    : isDark
                    ? 'bg-[#131F3F] border-[#1E293B] hover:border-[#2563EB]/40 hover:bg-[#182852]'
                    : 'bg-slate-50 border-slate-200 hover:bg-slate-100'
                }`}
              >
                <div className="w-7 h-7 rounded-lg bg-[#1E6BFF] text-white flex items-center justify-center font-bold text-xs uppercase shadow-xs shrink-0">
                  {displayInitial}
                </div>
                <div className="hidden sm:block text-left leading-tight">
                  <span
                    className={`block text-xs font-semibold max-w-[100px] truncate ${
                      isDark ? 'text-white' : 'text-[#0F172A]'
                    }`}
                  >
                    {displayName}
                  </span>
                  <span className="block text-[10px] text-slate-400 uppercase font-mono tracking-wider">
                    {displayRole}
                  </span>
                </div>
                <ChevronDown
                  className={`w-3.5 h-3.5 text-slate-400 transition-transform duration-200 hidden sm:block ${
                    activeDropdown === 'profile' ? 'rotate-180 text-blue-500' : ''
                  }`}
                />
              </button>

              {/* User Profile Dropdown Panel */}
              {activeDropdown === 'profile' && (
                <div
                  className={`absolute top-full right-0 mt-2 w-64 rounded-2xl p-2 z-50 animate-fade-in border shadow-2xl backdrop-blur-md ${
                    isDark
                      ? 'bg-[#0B132B] border-[#1E293B] text-white'
                      : 'bg-white border-[#E2E8F0] text-[#0F172A]'
                  }`}
                >
                  <div
                    className={`p-3 rounded-xl border mb-1.5 ${
                      isDark ? 'bg-[#131F3F] border-[#1E293B]' : 'bg-slate-50 border-slate-200'
                    }`}
                  >
                    <div className="flex items-center gap-2.5">
                      <div className="w-9 h-9 rounded-lg bg-[#1E6BFF] text-white flex items-center justify-center font-bold text-sm uppercase shadow-xs shrink-0">
                        {displayInitial}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div
                          className={`text-xs font-bold truncate ${
                            isDark ? 'text-white' : 'text-[#0F172A]'
                          }`}
                        >
                          {displayName}
                        </div>
                        <div className="text-[10px] text-slate-400 truncate">{displayEmail}</div>
                        <span className="inline-flex items-center gap-1 mt-1 px-1.5 py-0.5 rounded bg-blue-50 dark:bg-[#0B132B] text-[#2563EB] dark:text-[#60A5FA] border border-blue-200 dark:border-[#2563EB]/30 text-[9px] font-mono font-bold uppercase">
                          {displayRole === 'admin' && <Shield className="w-2.5 h-2.5" />}
                          Role: {displayRole}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="space-y-1">
                    <NavLink
                      to="/profile"
                      onClick={() => setActiveDropdown(null)}
                      className={`flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs transition-colors ${
                        isItemActive('/profile')
                          ? 'bg-[#1E6BFF] text-white font-semibold'
                          : isDark
                          ? 'text-slate-300 hover:text-white hover:bg-[#1E293B]'
                          : 'text-slate-700 hover:text-[#0F172A] hover:bg-slate-100'
                      }`}
                    >
                      <UserIcon className="w-4 h-4 shrink-0 text-[#2563EB]" />
                      <span>My Profile</span>
                    </NavLink>

                    <NavLink
                      to="/settings"
                      onClick={() => setActiveDropdown(null)}
                      className={`flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs transition-colors ${
                        isItemActive('/settings')
                          ? 'bg-[#1E6BFF] text-white font-semibold'
                          : isDark
                          ? 'text-slate-300 hover:text-white hover:bg-[#1E293B]'
                          : 'text-slate-700 hover:text-[#0F172A] hover:bg-slate-100'
                      }`}
                    >
                      <Settings className="w-4 h-4 shrink-0 text-[#2563EB]" />
                      <span>Account Settings</span>
                    </NavLink>

                    <NavLink
                      to="/history"
                      onClick={() => setActiveDropdown(null)}
                      className={`flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs transition-colors ${
                        isItemActive('/history')
                          ? 'bg-[#1E6BFF] text-white font-semibold'
                          : isDark
                          ? 'text-slate-300 hover:text-white hover:bg-[#1E293B]'
                          : 'text-slate-700 hover:text-[#0F172A] hover:bg-slate-100'
                      }`}
                    >
                      <History className="w-4 h-4 shrink-0 text-[#2563EB]" />
                      <span>Analysis History</span>
                    </NavLink>
                  </div>

                  <div
                    className={`border-t my-1.5 ${
                      isDark ? 'border-[#1E293B]' : 'border-slate-100'
                    }`}
                  />

                  <button
                    type="button"
                    onClick={handleLogout}
                    className="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs font-semibold text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-500/20 transition-colors cursor-pointer text-left"
                  >
                    <LogOut className="w-4 h-4 shrink-0" />
                    <span>Sign Out</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* =========================================================================
          COLLAPSIBLE HAMBURGER NAVIGATION MENU (Hidden by default, smooth animation)
          Theme: Enterprise Dark Navy & Blue (#0B132B, #131F3F, #1E293B, #1E6BFF)
      ========================================================================= */}

      {/* Semi-transparent backdrop overlay - Clicking outside closes menu */}
      <div
        id="hamburger-nav-backdrop"
        onClick={() => setIsMenuOpen(false)}
        aria-hidden="true"
        className={`fixed inset-0 bg-black/65 backdrop-blur-xs z-50 transition-opacity duration-300 ${
          isMenuOpen ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'
        }`}
      />

      {/* Collapsible Slide-Over Navigation Drawer */}
      <aside
        ref={menuPanelRef}
        id="collapsible-navigation-drawer"
        role="dialog"
        aria-modal="true"
        aria-label="Application Navigation Menu"
        className={`fixed top-0 left-0 bottom-0 z-50 w-80 sm:w-88 max-w-[85vw] h-full flex flex-col transition-transform duration-300 ease-out shadow-2xl border-r ${
          isMenuOpen ? 'translate-x-0' : '-translate-x-full'
        } bg-[#0B132B] text-[#F8FAFC] border-[#1E293B]`}
      >
        {/* Drawer Header with Brand Logo & Close 'X' Button */}
        <div className="p-4 sm:p-5 border-b border-[#1E293B] flex items-center justify-between gap-3 bg-[#0E172E]">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-[#1D4ED8] to-[#2563EB] text-white flex items-center justify-center shadow-md shrink-0">
              <svg className="w-4 h-4 text-white" viewBox="0 0 24 24" fill="currentColor">
                <path d="M4 19h3v-7H4v7zm6 0h3V5h-3v14zm6 0h3v-10h-3v10z" />
              </svg>
            </div>
            <div>
              <div className="flex items-center gap-1.5 leading-tight">
                <span className="font-bold text-sm sm:text-base text-white tracking-tight">
                  AI Data Analyst
                </span>
                <span className="px-1.5 py-0.5 rounded text-[8px] font-mono font-bold bg-[#131F3F] text-[#60A5FA] border border-[#2563EB]/40 uppercase tracking-wider">
                  AGENT
                </span>
              </div>
              <span className="text-[10px] text-[#8D99AE] block mt-0.5">
                Intelligent Analytics Workspace
              </span>
            </div>
          </div>

          {/* Close Button 'X' */}
          <button
            type="button"
            id="close-nav-drawer-btn"
            onClick={() => setIsMenuOpen(false)}
            aria-label="Close navigation menu"
            className="p-1.5 rounded-xl text-slate-400 hover:text-white hover:bg-[#131F3F] border border-transparent hover:border-[#1E293B] transition-all cursor-pointer flex items-center gap-1 group"
            title="Close menu (Esc)"
          >
            <span className="text-[10px] font-mono text-slate-500 group-hover:text-slate-300 hidden sm:inline">
              ESC
            </span>
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Quick Search inside Drawer */}
        <div className="p-3 border-b border-[#1E293B]/70 bg-[#0B132B]">
          <form onSubmit={handleSearchSubmit}>
            <div className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs bg-[#131F3F] border border-[#1E293B] text-slate-200 focus-within:border-[#2563EB] focus-within:bg-[#0E172E] transition-all">
              <Search className="w-4 h-4 text-slate-400 shrink-0" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Ask AI or jump to page..."
                className="bg-transparent text-xs text-white placeholder-slate-400 focus:outline-none w-full"
              />
            </div>
          </form>
        </div>

        {/* Scrollable Navigation Sections */}
        <div className="flex-1 overflow-y-auto px-3.5 py-4 space-y-5 custom-dark-scrollbar">
          {NAV_SECTIONS.map((section) => (
            <div key={section.title} className="space-y-1">
              <div className="px-2.5 pb-1 text-[10px] font-bold uppercase tracking-wider text-[#60A5FA]/80 flex items-center justify-between">
                <span>{section.title}</span>
                <span className="w-1.5 h-1.5 rounded-full bg-[#2563EB]/50"></span>
              </div>

              <div className="space-y-1">
                {section.items.map((item) => {
                  const ItemIcon = item.icon;
                  const active = isItemActive(item.path);

                  return (
                    <NavLink
                      key={item.path}
                      to={item.path}
                      onClick={() => setIsMenuOpen(false)}
                      className={`group flex items-center justify-between p-2.5 rounded-xl transition-all duration-150 cursor-pointer ${
                        active
                          ? 'bg-[#1E6BFF] text-white font-semibold shadow-md shadow-blue-600/30 ring-1 ring-blue-300/30'
                          : 'text-slate-300 hover:text-white hover:bg-[#131F3F] hover:border-[#1E293B] border border-transparent'
                      }`}
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <div
                          className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 border transition-transform group-hover:scale-105 ${
                            active
                              ? 'bg-white/20 text-white border-white/30'
                              : 'bg-[#131F3F] text-[#60A5FA] border-[#1E293B] group-hover:border-[#2563EB]/40'
                          }`}
                        >
                          <ItemIcon className="w-4 h-4" />
                        </div>
                        <div className="min-w-0 text-left">
                          <div className="flex items-center gap-2">
                            <span className="block text-xs font-medium leading-tight truncate">
                              {item.name}
                            </span>
                            {item.badge && (
                              <span
                                className={`text-[9px] px-1.5 py-0.2 rounded font-mono font-semibold uppercase tracking-wider ${
                                  active
                                    ? 'bg-white/20 text-white'
                                    : 'bg-[#2563EB]/20 text-[#60A5FA] border border-[#2563EB]/40'
                                }`}
                              >
                                {item.badge}
                              </span>
                            )}
                          </div>
                          <span
                            className={`block text-[10px] leading-tight mt-0.5 truncate ${
                              active ? 'text-blue-100' : 'text-[#8D99AE]'
                            }`}
                          >
                            {item.desc}
                          </span>
                        </div>
                      </div>

                      <ChevronRight
                        className={`w-3.5 h-3.5 shrink-0 transition-transform ${
                          active
                            ? 'text-white translate-x-0.5'
                            : 'text-slate-500 group-hover:text-slate-300 group-hover:translate-x-0.5'
                        }`}
                      />
                    </NavLink>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        {/* Drawer Footer with User Info & Quick Actions */}
        <div className="p-3.5 border-t border-[#1E293B] bg-[#0E172E] space-y-2.5">
          {/* User Profile Card */}
          <div className="flex items-center gap-2.5 p-2 rounded-xl bg-[#131F3F] border border-[#1E293B]">
            <div className="w-8 h-8 rounded-lg bg-[#1E6BFF] text-white flex items-center justify-center font-bold text-xs uppercase shadow-xs shrink-0">
              {displayInitial}
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-xs font-semibold text-white truncate">{displayName}</div>
              <div className="text-[10px] text-slate-400 truncate">{displayEmail}</div>
            </div>
            <span className="px-1.5 py-0.5 rounded bg-[#0B132B] text-[#60A5FA] border border-[#2563EB]/30 text-[9px] font-mono font-bold uppercase">
              {displayRole}
            </span>
          </div>

          {/* Quick Buttons: Theme Toggle & Sign Out */}
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={toggleTheme}
              className="flex items-center justify-center gap-1.5 py-2 px-3 rounded-xl border text-xs font-medium bg-[#131F3F] border-[#1E293B] text-slate-200 hover:text-white hover:border-[#2563EB]/50 transition-colors cursor-pointer"
            >
              {isDark ? (
                <>
                  <Sun className="w-3.5 h-3.5 text-amber-400" />
                  <span>Light Mode</span>
                </>
              ) : (
                <>
                  <Moon className="w-3.5 h-3.5 text-[#60A5FA]" />
                  <span>Dark Mode</span>
                </>
              )}
            </button>

            <button
              type="button"
              onClick={handleLogout}
              className="flex items-center justify-center gap-1.5 py-2 px-3 rounded-xl border text-xs font-semibold text-red-400 hover:text-red-300 bg-red-950/20 hover:bg-red-950/40 border-red-900/40 transition-colors cursor-pointer"
            >
              <LogOut className="w-3.5 h-3.5 shrink-0" />
              <span>Sign Out</span>
            </button>
          </div>
        </div>
      </aside>
    </>
  );
};

export default Navbar;
