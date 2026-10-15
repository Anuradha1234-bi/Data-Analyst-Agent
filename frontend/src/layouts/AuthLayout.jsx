import React from 'react';
import { Outlet, Navigate, Link, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Sparkles, ShieldCheck, ArrowRight } from 'lucide-react';

export const AuthLayout = () => {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (!isLoading && isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  const isLoginPage = location.pathname === '/login';
  const isRegisterPage = location.pathname === '/register';

  return (
    <div className="min-h-screen bg-[#F8FAFC] flex flex-col text-[#0F172A] selection:bg-[#2563EB] selection:text-white">
      {/* Top Brand Navigation Bar */}
      <header className="sticky top-0 z-40 bg-white/90 backdrop-blur-md border-b border-[#E2E8F0]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <Link to="/login" className="flex items-center gap-3 group">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-[#1D4ED8] to-[#2563EB] text-white flex items-center justify-center shadow-sm group-hover:shadow transition-all">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <div>
              <span className="font-bold text-base sm:text-lg tracking-tight text-[#0F172A] block leading-tight">
                AI Data Analyst Agent
              </span>
              <span className="text-[11px] text-[#64748B] hidden sm:block leading-tight">
                Upload, Understand, Clean & Analyze
              </span>
            </div>
          </Link>

          {/* Quick Guidance Navigation Links */}
          <nav className="hidden md:flex items-center gap-6 text-xs font-semibold text-[#64748B]">
            <a href="/login#who-should-use" className="hover:text-[#2563EB] transition-colors">
              Who It's For
            </a>
            <a href="/login#how-to-use" className="hover:text-[#2563EB] transition-colors">
              How It Works
            </a>
            <a href="/login#supported-data" className="hover:text-[#2563EB] transition-colors">
              Data & Privacy
            </a>
          </nav>

          {/* Right Action Switcher */}
          <div className="flex items-center gap-3">
            {isRegisterPage ? (
              <Link
                to="/login"
                className="text-xs font-semibold text-[#2563EB] hover:text-[#1D4ED8] px-3.5 py-2 rounded-lg hover:bg-blue-50 transition-colors"
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

      {/* Modern Professional Footer */}
      <footer className="bg-white border-t border-[#E2E8F0] mt-16 py-8">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col md:flex-row items-center justify-between gap-4 text-xs text-[#64748B]">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-[#2563EB]" />
            <span>Protected by Argon2 password hashing & signed JWT token sessions.</span>
          </div>
          <div className="flex items-center gap-6 text-[11px]">
            <a href="/login#who-should-use" className="hover:text-[#2563EB] transition-colors">
              Target Audiences
            </a>
            <a href="/login#how-to-use" className="hover:text-[#2563EB] transition-colors">
              Workflow Guide
            </a>
            <a href="/login#supported-data" className="hover:text-[#2563EB] transition-colors">
              Data Governance
            </a>
            <Link to="/forgot-password" className="hover:text-[#2563EB] transition-colors">
              Password Recovery
            </Link>
          </div>
          <div className="text-[11px] text-[#94A3B8]">
            &copy; {new Date().getFullYear()} AI Data Analyst Agent. All rights reserved.
          </div>
        </div>
      </footer>
    </div>
  );
};
