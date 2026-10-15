import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { extractErrorMessage } from '../services/api';
import {
  Lock,
  CheckCircle2,
  AlertCircle,
  ArrowRight,
  ArrowLeft,
  Eye,
  EyeOff,
  ShieldCheck,
  RotateCcw,
} from 'lucide-react';

export const ResetPasswordPage = () => {
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const [verifying, setVerifying] = useState(true);
  const [tokenValid, setTokenValid] = useState(false);
  const [tokenError, setTokenError] = useState('');

  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState('');
  const [isSuccess, setIsSuccess] = useState(false);

  const { verifyResetToken, resetPassword } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const token = new URLSearchParams(location.search).get('token') || '';

  // 1. Verify token on component mount
  useEffect(() => {
    let isMounted = true;

    const checkToken = async () => {
      if (!token) {
        if (isMounted) {
          setVerifying(false);
          setTokenValid(false);
          setTokenError('No password reset token was provided. Please use the link sent to your email.');
        }
        return;
      }

      try {
        await verifyResetToken(token);
        if (isMounted) {
          setTokenValid(true);
        }
      } catch (err) {
        if (isMounted) {
          setTokenValid(false);
          setTokenError(extractErrorMessage(err));
        }
      } finally {
        if (isMounted) {
          setVerifying(false);
        }
      }
    };

    checkToken();

    return () => {
      isMounted = false;
    };
  }, [token]);

  // Client-side password validation
  const validateForm = () => {
    if (!newPassword) {
      setFormError('Please enter a new password.');
      return false;
    }
    if (newPassword.length < 8) {
      setFormError('Password must be at least 8 characters long.');
      return false;
    }
    if (!/[A-Za-z]/.test(newPassword) || !/[0-9!@#$%^&*(),.?":{}|<>]/.test(newPassword)) {
      setFormError('Password must contain at least one letter and one number or special character.');
      return false;
    }
    if (newPassword !== confirmPassword) {
      setFormError('Passwords do not match.');
      return false;
    }
    return true;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormError('');

    if (!validateForm()) {
      return;
    }

    try {
      setSubmitting(true);
      await resetPassword(token, newPassword, confirmPassword);
      setIsSuccess(true);
    } catch (err) {
      const friendly = extractErrorMessage(err);
      setFormError(friendly);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="w-full max-w-md mx-auto my-12 px-4">
      <div className="bg-white border border-[#E2E8F0] rounded-2xl shadow-xl p-6 sm:p-8">
        {/* State A: Verifying Token */}
        {verifying && (
          <div className="text-center py-8 space-y-3">
            <div className="w-8 h-8 border-3 border-[#2563EB] border-t-transparent rounded-full animate-spin mx-auto"></div>
            <h3 className="text-sm font-semibold text-[#0F172A]">Verifying reset token...</h3>
            <p className="text-xs text-[#64748B]">Please wait while we validate your security link.</p>
          </div>
        )}

        {/* State B: Invalid / Expired Token */}
        {!verifying && !tokenValid && (
          <div className="text-center space-y-4">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-red-50 text-red-600 mb-2">
              <AlertCircle className="w-6 h-6" />
            </div>
            <h2 className="text-xl font-bold text-[#0F172A]">Invalid or Expired Link</h2>
            <p className="text-xs text-[#64748B] leading-relaxed">
              {tokenError || 'This password reset link is invalid, has expired, or has already been used.'}
            </p>
            <div className="pt-2 space-y-2">
              <Link
                to="/forgot-password"
                className="inline-flex items-center justify-center gap-1.5 w-full py-2.5 px-4 bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-xs font-semibold rounded-lg shadow-sm transition-colors"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Request New Reset Link</span>
              </Link>
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

        {/* State C: Reset Form */}
        {!verifying && tokenValid && !isSuccess && (
          <div>
            <div className="text-center mb-6">
              <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-blue-50 text-[#2563EB] mb-3">
                <ShieldCheck className="w-6 h-6" />
              </div>
              <h2 className="text-xl font-bold text-[#0F172A]">Set New Password</h2>
              <p className="text-xs text-[#64748B] mt-1">
                Enter and confirm your new secure account password below.
              </p>
            </div>

            {formError && (
              <div className="mb-4 p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-xs flex items-center gap-2" role="alert">
                <AlertCircle className="w-4 h-4 shrink-0 text-red-600" />
                <span>{formError}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4" noValidate>
              {/* New Password */}
              <div>
                <label
                  htmlFor="new-password"
                  className="block text-xs font-semibold text-[#0F172A] mb-1.5"
                >
                  New Password
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-[#94A3B8]">
                    <Lock className="w-4 h-4" />
                  </div>
                  <input
                    id="new-password"
                    type={showNewPassword ? 'text' : 'password'}
                    autoComplete="new-password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="Minimum 8 characters"
                    disabled={submitting}
                    required
                    className="w-full pl-9 pr-10 py-2.5 text-sm bg-white border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB] disabled:bg-slate-50 transition-all text-[#0F172A] placeholder:text-[#94A3B8]"
                  />
                  <button
                    type="button"
                    onClick={() => setShowNewPassword(!showNewPassword)}
                    aria-label={showNewPassword ? 'Hide password' : 'Show password'}
                    className="absolute inset-y-0 right-0 pr-3 flex items-center text-[#94A3B8] hover:text-[#0F172A] cursor-pointer"
                  >
                    {showNewPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              {/* Confirm Password */}
              <div>
                <label
                  htmlFor="confirm-new-password"
                  className="block text-xs font-semibold text-[#0F172A] mb-1.5"
                >
                  Confirm New Password
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-[#94A3B8]">
                    <Lock className="w-4 h-4" />
                  </div>
                  <input
                    id="confirm-new-password"
                    type={showConfirmPassword ? 'text' : 'password'}
                    autoComplete="new-password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Re-enter new password"
                    disabled={submitting}
                    required
                    className="w-full pl-9 pr-10 py-2.5 text-sm bg-white border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB] disabled:bg-slate-50 transition-all text-[#0F172A] placeholder:text-[#94A3B8]"
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    aria-label={showConfirmPassword ? 'Hide confirm password' : 'Show confirm password'}
                    className="absolute inset-y-0 right-0 pr-3 flex items-center text-[#94A3B8] hover:text-[#0F172A] cursor-pointer"
                  >
                    {showConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              {/* Password Requirements Guide */}
              <div className="p-3 rounded-lg bg-[#F8FAFC] border border-[#E2E8F0] text-[11px] text-[#64748B] space-y-1">
                <div className="font-semibold text-[#0F172A]">Password Requirements:</div>
                <div className="flex items-center gap-1.5">
                  <span className={newPassword.length >= 8 ? 'text-emerald-600 font-bold' : 'text-slate-400'}>•</span>
                  <span>Minimum 8 characters</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className={/[A-Za-z]/.test(newPassword) ? 'text-emerald-600 font-bold' : 'text-slate-400'}>•</span>
                  <span>At least one letter (a-z, A-Z)</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className={/[0-9!@#$%^&*(),.?":{}|<>]/.test(newPassword) ? 'text-emerald-600 font-bold' : 'text-slate-400'}>•</span>
                  <span>At least one number or special character</span>
                </div>
              </div>

              <button
                type="submit"
                disabled={submitting}
                className="w-full py-2.5 px-4 bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-sm font-semibold rounded-lg shadow-sm flex items-center justify-center gap-2 transition-all disabled:opacity-60 cursor-pointer disabled:cursor-not-allowed"
              >
                {submitting ? (
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                    <span>Updating Password...</span>
                  </div>
                ) : (
                  <>
                    <span>Reset Password</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </form>
          </div>
        )}

        {/* State D: Success State */}
        {!verifying && isSuccess && (
          <div className="text-center space-y-4">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-emerald-50 text-emerald-600 mb-2">
              <CheckCircle2 className="w-6 h-6" />
            </div>
            <h2 className="text-xl font-bold text-[#0F172A]">Password Reset Successful!</h2>
            <p className="text-xs text-[#475569] leading-relaxed">
              Your password has been securely updated. You can now sign in using your new credentials.
            </p>
            <div className="pt-2">
              <button
                type="button"
                onClick={() => navigate('/login', { state: { passwordResetSuccess: true }, replace: true })}
                className="inline-flex items-center justify-center gap-2 w-full py-2.5 px-4 bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-sm font-semibold rounded-lg shadow-sm transition-colors cursor-pointer"
              >
                <span>Proceed to Sign In</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
