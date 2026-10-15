import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { extractErrorMessage } from '../services/api';
import {
  Mail,
  KeyRound,
  AlertCircle,
  CheckCircle2,
  ArrowRight,
  ArrowLeft,
  Terminal,
} from 'lucide-react';

export const ForgotPasswordPage = () => {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [devResetUrl, setDevResetUrl] = useState('');

  const { forgotPassword } = useAuth();

  const validateEmail = (val) => {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    const trimmed = email.trim();
    if (!trimmed) {
      setError('Please enter your email address.');
      return;
    }

    if (!validateEmail(trimmed)) {
      setError('Please enter a valid email address.');
      return;
    }

    try {
      setLoading(true);
      const res = await forgotPassword(trimmed);
      setSubmitted(true);
      if (res?.dev_reset_url) {
        setDevResetUrl(res.dev_reset_url);
      }
    } catch (err) {
      const friendly = extractErrorMessage(err);
      setError(friendly);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full max-w-md mx-auto my-12 px-4">
      <div className="bg-white border border-[#E2E8F0] rounded-2xl shadow-xl p-6 sm:p-8">
        {!submitted ? (
          <div>
            {/* Header */}
            <div className="text-center mb-6">
              <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-blue-50 text-[#2563EB] mb-3">
                <KeyRound className="w-6 h-6" />
              </div>
              <h2 className="text-xl font-bold text-[#0F172A]">Forgot Password?</h2>
              <p className="text-xs text-[#64748B] mt-1 max-w-xs mx-auto">
                Enter your registered account email and we'll dispatch single-use reset instructions.
              </p>
            </div>

            {error && (
              <div className="mb-4 p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-xs flex items-center gap-2" role="alert">
                <AlertCircle className="w-4 h-4 shrink-0 text-red-600" />
                <span>{error}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4" noValidate>
              <div>
                <label
                  htmlFor="forgot-email"
                  className="block text-xs font-semibold text-[#0F172A] mb-1.5"
                >
                  Registered Email Address
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-[#94A3B8]">
                    <Mail className="w-4 h-4" />
                  </div>
                  <input
                    id="forgot-email"
                    type="email"
                    autoComplete="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="name@example.com"
                    disabled={loading}
                    required
                    className="w-full pl-9 pr-3 py-2.5 text-sm bg-white border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB] disabled:bg-slate-50 transition-all text-[#0F172A] placeholder:text-[#94A3B8]"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 px-4 bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-sm font-semibold rounded-lg shadow-sm flex items-center justify-center gap-2 transition-all disabled:opacity-60 cursor-pointer disabled:cursor-not-allowed"
              >
                {loading ? (
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                    <span>Sending Instructions...</span>
                  </div>
                ) : (
                  <>
                    <span>Send Reset Instructions</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </form>

            <div className="mt-6 pt-5 border-t border-[#E2E8F0] text-center">
              <Link
                to="/login"
                className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#64748B] hover:text-[#2563EB] transition-colors"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>Back to Sign In</span>
              </Link>
            </div>
          </div>
        ) : (
          /* Success / Confirmation State */
          <div className="text-center space-y-4">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-emerald-50 text-emerald-600 mb-2">
              <CheckCircle2 className="w-6 h-6" />
            </div>

            <h2 className="text-xl font-bold text-[#0F172A]">Check Your Inbox</h2>

            <p className="text-xs text-[#475569] leading-relaxed">
              If an account with <strong>{email}</strong> exists in our system, we have sent instructions to reset your password.
            </p>

            <p className="text-[11px] text-[#94A3B8]">
              The password reset link will expire in 20 minutes and can only be used once.
            </p>

            {/* Development Mode Helper */}
            {devResetUrl && (
              <div className="mt-4 p-4 rounded-xl bg-blue-50 border border-blue-200 text-left space-y-2.5">
                <div className="flex items-center gap-1.5 text-xs font-bold text-[#1D4ED8]">
                  <Terminal className="w-4 h-4" />
                  <span>Local Development Mode</span>
                </div>
                <p className="text-[11px] text-[#475569] leading-relaxed">
                  SMTP is running in development mode. You can test your password reset link directly:
                </p>
                <a
                  href={devResetUrl}
                  className="inline-flex items-center justify-center gap-1.5 w-full text-xs font-semibold text-white bg-[#2563EB] hover:bg-[#1D4ED8] py-2 px-3 rounded-lg shadow-sm transition-all"
                >
                  <span>Proceed to Reset Password</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </a>
              </div>
            )}

            <div className="pt-4 border-t border-[#E2E8F0]">
              <Link
                to="/login"
                className="inline-flex items-center justify-center gap-1.5 w-full py-2.5 px-4 bg-slate-100 hover:bg-slate-200 text-[#0F172A] text-xs font-semibold rounded-lg transition-colors"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>Return to Sign In</span>
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
