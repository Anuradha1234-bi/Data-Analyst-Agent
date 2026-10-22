import React from 'react';
import { Outlet, Navigate, Link, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';
import { Sparkles, ArrowRight, Sun, Moon } from 'lucide-react';
import { AuthFooter } from '../components/AuthFooter';

export const AuthLayout = () => {
  const { isAuthenticated, isLoading } = useAuth();
  const { isDark, toggleTheme } = useTheme();
  const location = useLocation();

  if (!isLoading && isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  const isRegisterPage = location.pathname === '/register';

  return (
    <div className="min-h-screen bg-[#F8FAFC] dark:bg-[#070D1E] flex flex-col text-[#0F172A] dark:text-[#F8FAFC] selection:bg-[#2563EB] selection:text-white">
      {/* Top Brand Navigation Bar */}
      <header className="sticky top-0 z-40 bg-white/90 dark:bg-[#0B132B]/95 backdrop-blur-md border-b border-[#E2E8F0] dark:border-[#1E293B]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <Link to="/login" className="flex items-center gap-3 group">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-[#1D4ED8] to-[#2563EB] text-white flex items-center justify-center shadow-sm group-hover:shadow transition-all">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <div>
              <span className="font-bold text-base sm:text-lg tracking-tight text-[#0F172A] dark:text-white block leading-tight">
                AI Data Analyst Agent
              </span>
              <span className="text-[11px] text-[#64748B] dark:text-slate-400 hidden sm:block leading-tight">
                Upload, Understand, Clean & Analyze
              </span>
            </div>
          </Link>

          {/* Quick Guidance Navigation Links */}
          <nav className="hidden md:flex items-center gap-6 text-xs font-semibold text-[#64748B] dark:text-slate-400">
            <a href="/login#who-should-use" className="hover:text-[#2563EB] dark:hover:text-[#60A5FA] transition-colors">
              Who It's For
            </a>
            <a href="/login#how-to-use" className="hover:text-[#2563EB] dark:hover:text-[#60A5FA] transition-colors">
              How It Works
            </a>
            <a href="/login#supported-data" className="hover:text-[#2563EB] dark:hover:text-[#60A5FA] transition-colors">
              Data & Privacy
            </a>
          </nav>

          {/* Right Action Switcher & Theme Toggle */}
          <div className="flex items-center gap-3">
            {/* Theme Toggle Button */}
            <button
              type="button"
              onClick={toggleTheme}
              className={`p-2 rounded-lg border transition-all cursor-pointer ${
                isDark
                  ? 'bg-[#131F3F] border-[#1E293B] text-[#60A5FA] hover:bg-[#182852]'
                  : 'bg-slate-50 border-slate-200 text-amber-600 hover:bg-slate-100'
              }`}
              title={isDark ? 'Current: Dark Mode (Click for Light Mode)' : 'Current: Light Mode (Click for Dark Mode)'}
              aria-label={isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
            >
              {isDark ? <Moon className="w-4 h-4 text-[#60A5FA]" /> : <Sun className="w-4 h-4 text-amber-500 fill-amber-500/20" />}
            </button>

            {isRegisterPage ? (
              <Link
                to="/login"
                className="text-xs font-semibold text-[#2563EB] hover:text-[#1D4ED8] px-3.5 py-2 rounded-lg hover:bg-blue-50 dark:hover:bg-[#131F3F] transition-colors"
              >
                Sign In
              </Link>
            ) : (
              <Link
                to="/register"
                className="inline-flex items-center gap-1.5 text-xs font-semibold bg-[#2563EB] hover:bg-[#1D4ED8] text-white px-3.5 py-2 rounded-lg shadow-sm hover:shadow transition-all"
              >
                <span>Create Account</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            )}
          </div>
        </div>
      </header>

      {/* Main Page Area */}
      <main className="flex-1 w-full">
        <Outlet />
      </main>

      {/* Reusable Dark Navy & Blue Theme Footer */}
      <AuthFooter />
    </div>
  );
};
