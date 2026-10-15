import React from 'react';
import { NavLink, Outlet, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  Database,
  LayoutDashboard,
  UploadCloud,
  FileSearch,
  ShieldCheck,
  Filter,
  MessageSquare,
  BarChart3,
  AlertTriangle,
  TrendingUp,
  Lightbulb,
  FileText,
  Settings,
  Clock,
  User,
  LogOut,
  ChevronRight,
} from 'lucide-react';

const NAV_SECTIONS = [
  {
    title: null, // Top primary items
    items: [
      { name: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
      { name: 'Upload Dataset', path: '/upload', icon: UploadCloud },
    ],
  },
  {
    title: 'DATA',
    items: [
      { name: 'Datasets', path: '/datasets', icon: Database },
      { name: 'Data Profile', path: '/profile-data', icon: FileSearch },
      { name: 'Data Quality', path: '/data-quality', icon: ShieldCheck },
      { name: 'Data Cleaning', path: '/data-cleaning', icon: Filter },
    ],
  },
  {
    title: 'ANALYSIS',
    items: [
      { name: 'Data Analyst', path: '/data-analyst', icon: MessageSquare },
      { name: 'Analytics', path: '/analytics', icon: BarChart3 },
      { name: 'Anomalies', path: '/anomalies', icon: AlertTriangle },
      { name: 'Predictions', path: '/predictions', icon: TrendingUp },
    ],
  },
  {
    title: 'OUTPUT',
    items: [
      { name: 'Insights', path: '/insights', icon: Lightbulb },
      { name: 'Reports', path: '/reports', icon: FileText },
    ],
  },
  {
    title: 'SYSTEM',
    items: [
      { name: 'Settings', path: '/settings', icon: Settings },
      { name: 'History', path: '/history', icon: Clock },
      { name: 'Profile', path: '/profile', icon: User },
    ],
  },
];

export const MainLayout = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  // Helper to determine if a nav item is active, supporting route aliases
  const isItemActive = (path) => {
    const current = location.pathname;
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

  // Find active page title across all sections
  const allItems = NAV_SECTIONS.flatMap((sec) => sec.items);
  const activeItem = allItems.find((item) => isItemActive(item.path));
  const currentTitle = activeItem ? activeItem.name : (location.pathname === '/datasets' ? 'Datasets' : 'AI Data Analyst Agent');
  const displayName = user?.full_name || user?.name || 'Analyst';

  return (
    <div className="flex h-screen bg-[#F8FAFC] text-[#0F172A] overflow-hidden">
      {/* Sidebar Navigation */}
      <aside className="w-64 bg-[#0F172A] text-white flex flex-col justify-between shrink-0 shadow-lg select-none">
        {/* Sidebar Header & Nav Items */}
        <div className="flex flex-col min-h-0 flex-1">
          {/* Brand Header */}
          <div className="px-5 py-4 border-b border-[#1E293B] shrink-0">
            <h1 className="text-base font-bold tracking-tight text-white flex items-center gap-2">
              <span>AI Data Analyst</span>
              <span className="text-[#2563EB] text-[10px] font-semibold px-1.5 py-0.5 rounded bg-[#2563EB]/20 border border-[#2563EB]/40">
                AGENT
              </span>
            </h1>
            <p className="text-[11px] text-[#94A3B8] mt-0.5">Intelligent Analytics Workspace</p>
          </div>

          {/* Grouped Navigation */}
          <nav className="px-3 py-3 space-y-3 overflow-y-auto flex-1">
            {NAV_SECTIONS.map((section, sIdx) => (
              <div key={sIdx} className="space-y-1">
                {section.title && (
                  <div className="px-3 pt-2 pb-1 text-[10px] font-bold text-[#64748B] tracking-wider uppercase">
                    {section.title}
                  </div>
                )}
                {section.items.map((item) => {
                  const Icon = item.icon;
                  const active = isItemActive(item.path);
                  return (
                    <NavLink
                      key={item.path}
                      to={item.path}
                      className={`flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                        active
                          ? 'bg-[#2563EB] text-white shadow-sm font-semibold'
                          : 'text-[#94A3B8] hover:text-white hover:bg-[#1E293B]'
                      }`}
                    >
                      <Icon className="w-4 h-4 shrink-0" />
                      <span className="truncate">{item.name}</span>
                    </NavLink>
                  );
                })}
              </div>
            ))}
          </nav>
        </div>

        {/* User Card & Logout */}
        <div className="p-3.5 border-t border-[#1E293B] bg-[#0A0F1D]/80 space-y-2.5 shrink-0">
          <div className="flex items-center gap-2.5 overflow-hidden">
            <div className="w-7 h-7 rounded-full bg-[#2563EB] text-white flex items-center justify-center font-bold text-xs uppercase shrink-0">
              {displayName ? displayName.charAt(0) : 'U'}
            </div>
            <div className="truncate">
              <div className="text-xs font-semibold text-white truncate">{displayName}</div>
              <div className="text-[10px] text-[#94A3B8] truncate">{user?.email || ''}</div>
            </div>
          </div>

          <button
            onClick={handleLogout}
            className="w-full flex items-center justify-center gap-2 py-1.5 px-3 rounded-lg text-xs font-medium text-red-400 hover:text-red-300 hover:bg-red-500/10 border border-transparent hover:border-red-500/20 transition-all cursor-pointer"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span>Sign Out</span>
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Header */}
        <header className="h-14 bg-white border-b border-[#E2E8F0] px-6 flex items-center justify-between shrink-0 shadow-xs">
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-[#64748B]">Workspace</span>
            <ChevronRight className="w-3.5 h-3.5 text-[#94A3B8]" />
            <h2 className="text-xs font-semibold text-[#0F172A]">{currentTitle}</h2>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#EFF6FF] border border-[#BFDBFE]">
              <span className="w-2 h-2 rounded-full bg-[#16A34A] animate-pulse"></span>
              <span className="text-[11px] font-medium text-[#1D4ED8]">FastAPI Connected</span>
            </div>
          </div>
        </header>

        {/* Page Content Outlet */}
        <main className="flex-1 overflow-y-auto p-6 bg-[#F8FAFC]">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default MainLayout;
