import React, { useEffect } from 'react';
import { X, Shield, FileText, CheckCircle2 } from 'lucide-react';

export const LegalModal = ({ isOpen, onClose, activeTab = 'privacy', onTabChange }) => {
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/75 backdrop-blur-xs overflow-y-auto animate-fade-in"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="legal-modal-title"
    >
      <div className="relative w-full max-w-2xl my-8 bg-[#0B132B] text-white border border-[#1E293B] rounded-2xl shadow-2xl overflow-hidden">
        {/* Header with Tab Switcher */}
        <div className="px-6 py-4 border-b border-[#1E293B] flex items-center justify-between bg-gradient-to-r from-[#0B132B] to-[#111C44]">
          <div className="flex items-center gap-3">
            <div className="flex bg-[#131F3F] p-1 rounded-xl border border-[#1E293B]">
              <button
                type="button"
                onClick={() => onTabChange && onTabChange('privacy')}
                className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                  activeTab === 'privacy'
                    ? 'bg-[#2563EB] text-white shadow-sm'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                <Shield className="w-3.5 h-3.5" />
                <span>Privacy Policy</span>
              </button>
              <button
                type="button"
                onClick={() => onTabChange && onTabChange('terms')}
                className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                  activeTab === 'terms'
                    ? 'bg-[#2563EB] text-white shadow-sm'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                <FileText className="w-3.5 h-3.5" />
                <span>Terms of Service</span>
              </button>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            aria-label="Close modal"
            className="w-8 h-8 rounded-lg bg-[#1E293B]/70 hover:bg-[#1E293B] text-slate-400 hover:text-white flex items-center justify-center transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Scrollable Legal Content */}
        <div className="p-6 max-h-[70vh] overflow-y-auto space-y-6 text-xs text-slate-300 leading-relaxed">
          {activeTab === 'privacy' ? (
            <div className="space-y-4">
              <div className="border-b border-[#1E293B] pb-3">
                <h4 id="legal-modal-title" className="text-base font-bold text-white">
                  Privacy Policy
                </h4>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  Last updated: January 2026 • AI Data Analyst Agent
                </p>
              </div>

              <div>
                <h5 className="font-semibold text-white mb-1">1. Information We Collect</h5>
                <p>
                  We collect information necessary to facilitate data analysis workflows, including account credentials (full name, email, encrypted passwords) and structured tabular datasets (CSV, Excel) that you voluntarily upload.
                </p>
              </div>

              <div>
                <h5 className="font-semibold text-white mb-1">2. Data Ownership &amp; Isolation</h5>
                <p>
                  You retain complete, exclusive ownership of any data uploaded to the AI Data Analyst Agent. Your files are isolated and stored within protected local server repositories. We do not sell, rent, or share customer datasets with third parties, nor do we train public AI models on your private corporate records.
                </p>
              </div>

              <div>
                <h5 className="font-semibold text-white mb-1">3. Automated Processing &amp; Intelligence</h5>
                <p>
                  Uploaded datasets are processed solely to compute summary statistics, profiling summaries, data quality health scores, anomaly detection flags, cleaning recommendations, and predictive forecasts at your direction.
                </p>
              </div>

              <div>
                <h5 className="font-semibold text-white mb-1">4. Data Retention &amp; Deletion Rights</h5>
                <p>
                  You maintain full administrative control to delete any uploaded dataset or generated analysis report at any time through the Datasets view. Upon deletion, files are permanently purged from active storage.
                </p>
              </div>

              <div>
                <h5 className="font-semibold text-white mb-1">5. Security Safeguards</h5>
                <p>
                  We implement robust enterprise security measures, including Argon2 password hashing algorithms, signed JSON Web Tokens (JWT) for session authentication, strict CORS enforcement, and validation against malicious file uploads.
                </p>
              </div>

              <div>
                <h5 className="font-semibold text-white mb-1">6. Contact &amp; Inquiries</h5>
                <p>
                  For privacy inquiries, contact our Data Protection team at{' '}
                  <a href="mailto:dataanalystagent@gmail.com" className="text-[#60A5FA] underline hover:text-white">
                    dataanalystagent@gmail.com
                  </a>{' '}
                  or call our helpline at{' '}
                  <a href="tel:+919021964018" className="text-[#60A5FA] underline hover:text-white">
                    +91 9021964018
                  </a>
                  .
                </p>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="border-b border-[#1E293B] pb-3">
                <h4 id="legal-modal-title" className="text-base font-bold text-white">
                  Terms of Service
                </h4>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  Last updated: January 2026 • AI Data Analyst Agent
                </p>
              </div>

              <div>
                <h5 className="font-semibold text-white mb-1">1. Acceptance of Terms</h5>
                <p>
                  By accessing or registering an account on AI Data Analyst Agent, you agree to comply with and be bound by these Terms of Service. If you do not agree, you must discontinue using the application.
                </p>
              </div>

              <div>
                <h5 className="font-semibold text-white mb-1">2. Permitted Use &amp; Responsibilities</h5>
                <p>
                  The platform is designed to provide autonomous analytical insights for structured tabular data. You agree to upload only datasets that you possess lawful authority, permissions, and licenses to analyze. You agree not to upload plaintext passwords, secret keys, or unlawful content.
                </p>
              </div>

              <div>
                <h5 className="font-semibold text-white mb-1">3. Analytics &amp; Autonomous Heuristics</h5>
                <p>
                  Our automated agents generate statistical summaries, data cleaning suggestions, and predictive calculations based on established algorithms and machine learning models. These outputs are intended to assist decision-making and should be reviewed by qualified personnel prior to mission-critical operational decisions.
                </p>
              </div>

              <div>
                <h5 className="font-semibold text-white mb-1">4. Account Security</h5>
                <p>
                  You are responsible for safeguarding your login credentials and preventing unauthorized access to your account. Notify us immediately at{' '}
                  <a href="mailto:dataanalystagent@gmail.com" className="text-[#60A5FA] underline hover:text-white">
                    dataanalystagent@gmail.com
                  </a>{' '}
                  if you detect unauthorized activity.
                </p>
              </div>

              <div>
                <h5 className="font-semibold text-white mb-1">5. Limitation of Liability</h5>
                <p>
                  To the maximum extent permitted by applicable law, AI Data Analyst Agent and its operators shall not be liable for any indirect, incidental, or consequential damages resulting from data loss, analysis discrepancies, or service downtime.
                </p>
              </div>

              <div>
                <h5 className="font-semibold text-white mb-1">6. Support &amp; Assistance</h5>
                <p>
                  For assistance regarding these terms, reach our support desk at{' '}
                  <a href="mailto:dataanalystagent@gmail.com" className="text-[#60A5FA] underline hover:text-white">
                    dataanalystagent@gmail.com
                  </a>{' '}
                  or phone{' '}
                  <a href="tel:+919021964018" className="text-[#60A5FA] underline hover:text-white">
                    +91 9021964018
                  </a>
                  .
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3.5 border-t border-[#1E293B] bg-[#0A1128] flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-[11px] text-slate-400">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            <span>Official Policy Documentation</span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1.5 text-xs font-semibold rounded-lg bg-[#2563EB] hover:bg-[#1D4ED8] text-white transition-colors cursor-pointer"
          >
            I Understand
          </button>
        </div>
      </div>
    </div>
  );
};

export default LegalModal;
