import React, { useState } from 'react';
import { Mail, Phone, Sparkles, ShieldCheck, ArrowUpRight, MessageSquareText } from 'lucide-react';
import { SupportModal } from './SupportModal';
import { LegalModal } from './LegalModal';

const SUPPORT_EMAIL = 'dataanalystagent@gmail.com';
const SUPPORT_HELPLINE = '+91 9021964018';
const SUPPORT_HELPLINE_TEL = '+919021964018';

export const AuthFooter = () => {
  const [isSupportModalOpen, setIsSupportModalOpen] = useState(false);
  const [legalModalState, setLegalModalState] = useState({
    isOpen: false,
    tab: 'privacy', // 'privacy' | 'terms'
  });

  const handleOpenPrivacy = (e) => {
    e.preventDefault();
    setLegalModalState({ isOpen: true, tab: 'privacy' });
  };

  const handleOpenTerms = (e) => {
    e.preventDefault();
    setLegalModalState({ isOpen: true, tab: 'terms' });
  };

  const handleOpenSupport = (e) => {
    e.preventDefault();
    setIsSupportModalOpen(true);
  };

  return (
    <>
      <footer
        className="w-full bg-[#0B132B] text-slate-300 border-t border-[#1E293B] mt-auto transition-colors selection:bg-[#2563EB] selection:text-white"
        role="contentinfo"
        aria-label="Authentication Footer"
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 sm:py-12">
          {/* Main Footer Grid */}
          <div className="grid grid-cols-1 md:grid-cols-12 gap-8 lg:gap-10 items-start">
            {/* Column 1: Brand & Tagline */}
            <div className="md:col-span-5 space-y-3.5">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-[#1D4ED8] to-[#2563EB] text-white flex items-center justify-center shadow-sm">
                  <Sparkles className="w-4 h-4 text-white" />
                </div>
                <div className="flex items-center gap-2">
                  <span className="font-bold text-base sm:text-lg text-white tracking-tight">
                    AI Data Analyst Agent
                  </span>
                  <span className="px-1.5 py-0.5 rounded bg-[#131F3F] text-[#60A5FA] border border-[#2563EB]/40 text-[9px] font-mono font-bold uppercase tracking-wider">
                    ENTERPRISE
                  </span>
                </div>
              </div>

              <p className="text-xs sm:text-sm text-slate-400 leading-relaxed max-w-sm">
                Turn your data into meaningful insights.
              </p>

              <div className="flex items-center gap-2 pt-1 text-[11px] text-slate-400">
                <ShieldCheck className="w-4 h-4 text-[#60A5FA] shrink-0" />
                <span>Protected by Argon2 password hashing &amp; signed JWT tokens</span>
              </div>
            </div>

            {/* Column 2: Navigation Links */}
            <div className="md:col-span-3 space-y-3">
              <h4 className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                Navigation
              </h4>
              <ul className="space-y-2 text-xs">
                <li>
                  <button
                    type="button"
                    onClick={handleOpenPrivacy}
                    className="text-slate-300 hover:text-[#60A5FA] transition-colors flex items-center gap-1 group cursor-pointer"
                  >
                    <span>Privacy Policy</span>
                    <ArrowUpRight className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity text-[#60A5FA]" />
                  </button>
                </li>
                <li>
                  <button
                    type="button"
                    onClick={handleOpenTerms}
                    className="text-slate-300 hover:text-[#60A5FA] transition-colors flex items-center gap-1 group cursor-pointer"
                  >
                    <span>Terms of Service</span>
                    <ArrowUpRight className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity text-[#60A5FA]" />
                  </button>
                </li>
                <li>
                  <button
                    type="button"
                    onClick={handleOpenSupport}
                    className="text-slate-300 hover:text-[#60A5FA] transition-colors flex items-center gap-1 group cursor-pointer"
                  >
                    <span>Help &amp; Support</span>
                    <span className="px-1.5 py-0.2 rounded bg-[#131F3F] text-[#93C5FD] text-[10px] font-medium border border-[#2563EB]/30">
                      Form
                    </span>
                  </button>
                </li>
              </ul>
            </div>

            {/* Column 3: Contact Information */}
            <div className="md:col-span-4 space-y-3">
              <h4 className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                Contact Information
              </h4>
              <ul className="space-y-2.5 text-xs">
                {/* Email (mailto) */}
                <li className="flex items-start gap-2.5">
                  <div className="w-6 h-6 rounded-md bg-[#131F3F] text-[#60A5FA] flex items-center justify-center shrink-0 mt-0.5 border border-[#1E293B]">
                    <Mail className="w-3.5 h-3.5" />
                  </div>
                  <div>
                    <span className="block text-[10px] uppercase font-semibold text-slate-400">
                      Email
                    </span>
                    <a
                      href={`mailto:${SUPPORT_EMAIL}`}
                      title="Send email to AI Data Analyst Agent"
                      className="text-white hover:text-[#60A5FA] font-medium transition-colors break-all underline decoration-slate-600 hover:decoration-[#60A5FA]"
                    >
                      {SUPPORT_EMAIL}
                    </a>
                  </div>
                </li>

                {/* Helpline (tel) */}
                <li className="flex items-start gap-2.5">
                  <div className="w-6 h-6 rounded-md bg-[#131F3F] text-[#60A5FA] flex items-center justify-center shrink-0 mt-0.5 border border-[#1E293B]">
                    <Phone className="w-3.5 h-3.5" />
                  </div>
                  <div>
                    <span className="block text-[10px] uppercase font-semibold text-slate-400">
                      Helpline
                    </span>
                    <a
                      href={`tel:${SUPPORT_HELPLINE_TEL}`}
                      title="Call AI Data Analyst Agent Helpline"
                      className="text-white hover:text-[#60A5FA] font-medium transition-colors underline decoration-slate-600 hover:decoration-[#60A5FA]"
                    >
                      {SUPPORT_HELPLINE}
                    </a>
                  </div>
                </li>

                {/* Open Contact Form Quick Action */}
                <li className="pt-1">
                  <button
                    type="button"
                    onClick={handleOpenSupport}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#131F3F] hover:bg-[#182852] text-[#93C5FD] hover:text-white border border-[#2563EB]/40 text-xs font-medium transition-all cursor-pointer shadow-xs"
                  >
                    <MessageSquareText className="w-3.5 h-3.5" />
                    <span>Open Help &amp; Support Form</span>
                  </button>
                </li>
              </ul>
            </div>
          </div>

          {/* Subtle Divider */}
          <div className="border-t border-[#1E293B] my-8" />

          {/* Bottom Bar: Copyright & System Status */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-slate-400">
            <div>
              &copy; 2026 AI Data Analyst Agent. All rights reserved.
            </div>

            <div className="flex items-center gap-4 text-[11px]">
              <span className="inline-flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                <span>System Operational</span>
              </span>
              <span className="text-slate-600">•</span>
              <span>Autonomous Analytics Platform</span>
            </div>
          </div>
        </div>
      </footer>

      {/* Interactive Modals */}
      <SupportModal
        isOpen={isSupportModalOpen}
        onClose={() => setIsSupportModalOpen(false)}
      />

      <LegalModal
        isOpen={legalModalState.isOpen}
        activeTab={legalModalState.tab}
        onTabChange={(tab) => setLegalModalState((prev) => ({ ...prev, tab }))}
        onClose={() => setLegalModalState({ isOpen: false, tab: 'privacy' })}
      />
    </>
  );
};

export default AuthFooter;
