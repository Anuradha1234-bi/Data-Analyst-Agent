import React, { useState, useEffect } from 'react';
import {
  X,
  Mail,
  Phone,
  Send,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  ExternalLink,
  Sparkles,
  Copy,
  Check,
} from 'lucide-react';
import { supportService } from '../services/supportService';
import { extractErrorMessage } from '../services/api';

const SUPPORT_EMAIL = 'dataanalystagent@gmail.com';
const SUPPORT_HELPLINE = '+91 9021964018';
const SUPPORT_HELPLINE_TEL = '+919021964018';

export const SupportModal = ({ isOpen, onClose }) => {
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [subject, setSubject] = useState('');
  const [message, setMessage] = useState('');

  const [fieldErrors, setFieldErrors] = useState({});
  const [submitError, setSubmitError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');
  const [copied, setCopied] = useState(false);
  const [copiedPhone, setCopiedPhone] = useState(false);
  const [supportStatus, setSupportStatus] = useState(null);

  // Close on Escape key press
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  // Reset states and fetch readiness when modal opens
  useEffect(() => {
    if (isOpen) {
      setSubmitError('');
      setFieldErrors({});
      setCopied(false);
      setCopiedPhone(false);
      supportService
        .getSupportStatus()
        .then((data) => setSupportStatus(data))
        .catch((err) => console.warn('Could not retrieve support status:', err));
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const validateEmail = (val) => {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val);
  };

  const validateForm = () => {
    const errors = {};
    const trimmedName = fullName.trim();
    const trimmedEmail = email.trim();
    const trimmedSubject = subject.trim();
    const trimmedMessage = message.trim();

    if (!trimmedName) {
      errors.fullName = 'Full Name is required.';
    } else if (trimmedName.length < 2) {
      errors.fullName = 'Full Name must be at least 2 characters.';
    }

    if (!trimmedEmail) {
      errors.email = 'Email Address is required.';
    } else if (!validateEmail(trimmedEmail)) {
      errors.email = 'Please enter a valid email address.';
    }

    if (!trimmedSubject) {
      errors.subject = 'Subject is required.';
    } else if (trimmedSubject.length < 3) {
      errors.subject = 'Subject must be at least 3 characters.';
    }

    if (!trimmedMessage) {
      errors.message = 'Message is required.';
    } else if (trimmedMessage.length < 10) {
      errors.message = 'Please provide a detailed message (minimum 10 characters).';
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitError('');

    if (!validateForm()) {
      return;
    }

    try {
      setIsSubmitting(true);
      const result = await supportService.submitContactMessage({
        fullName,
        email,
        subject,
        message,
      });

      if (result && result.success) {
        setIsSuccess(true);
        setSuccessMessage(
          result.message ||
            'Thank you! Your message has been sent to dataanalystagent@gmail.com. We will respond shortly.'
        );
      } else {
        setSubmitError(
          result?.message || 'Could not verify delivery. Please contact our support team directly.'
        );
      }
    } catch (err) {
      const friendlyError = extractErrorMessage(err);
      setSubmitError(friendlyError);
      setIsSuccess(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResetForm = () => {
    setFullName('');
    setEmail('');
    setSubject('');
    setMessage('');
    setFieldErrors({});
    setSubmitError('');
    setIsSuccess(false);
    setSuccessMessage('');
    setCopied(false);
    setCopiedPhone(false);
  };

  // Copy email address to clipboard with robust fallback
  const handleCopyEmail = async (e) => {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(SUPPORT_EMAIL);
      } else {
        const textArea = document.createElement('textarea');
        textArea.value = SUPPORT_EMAIL;
        textArea.style.position = 'fixed';
        textArea.style.left = '-999999px';
        textArea.style.top = '-999999px';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
      }
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch (err) {
      console.error('Failed to copy email:', err);
    }
  };

  // Copy helpline phone number to clipboard with robust fallback
  const handleCopyPhone = async (e) => {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(SUPPORT_HELPLINE);
      } else {
        const textArea = document.createElement('textarea');
        textArea.value = SUPPORT_HELPLINE;
        textArea.style.position = 'fixed';
        textArea.style.left = '-999999px';
        textArea.style.top = '-999999px';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
      }
      setCopiedPhone(true);
      setTimeout(() => setCopiedPhone(false), 2500);
    } catch (err) {
      console.error('Failed to copy phone:', err);
    }
  };

  // Construct meaningful subject
  const getMeaningfulSubject = () => {
    const trimmed = subject.trim();
    return trimmed
      ? `AI Data Analyst Agent - Support Request: ${trimmed}`
      : 'AI Data Analyst Agent - Support Request';
  };

  // Construct prefilled email body
  const getFormattedBody = () => {
    const bodyParts = [];
    if (fullName.trim()) bodyParts.push(`Sender Name: ${fullName.trim()}`);
    if (email.trim()) bodyParts.push(`Contact Email: ${email.trim()}`);
    if (message.trim()) {
      bodyParts.push(`\nMessage:\n${message.trim()}`);
    } else {
      bodyParts.push('\n[Please describe your request or issue below]');
    }
    return bodyParts.join('\n');
  };

  // Prefer Gmail compose in a new tab
  const getGmailComposeUrl = () => {
    const su = getMeaningfulSubject();
    const body = getFormattedBody();
    return `https://mail.google.com/mail/?view=cm&fs=1&to=${encodeURIComponent(
      SUPPORT_EMAIL
    )}&su=${encodeURIComponent(su)}&body=${encodeURIComponent(body)}`;
  };

  // Desktop client mailto fallback
  const getMailtoUrl = () => {
    const su = getMeaningfulSubject();
    const body = getFormattedBody();
    return `mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent(
      su
    )}&body=${encodeURIComponent(body)}`;
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/75 backdrop-blur-xs overflow-y-auto animate-fade-in"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="support-modal-title"
    >
      <div className="relative w-full max-w-xl my-8 bg-[#0B132B] text-white border border-[#1E293B] rounded-2xl shadow-2xl overflow-hidden">
        {/* Modal Top Header */}
        <div className="px-6 py-5 border-b border-[#1E293B] flex items-center justify-between bg-gradient-to-r from-[#0B132B] to-[#111C44]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-[#1D4ED8] to-[#2563EB] text-white flex items-center justify-center shadow-sm">
              <HelpCircle className="w-5 h-5 text-white" />
            </div>
            <div>
              <h3 id="support-modal-title" className="text-base sm:text-lg font-bold text-white tracking-tight">
                Help &amp; Support
              </h3>
              <p className="text-xs text-slate-400">
                Contact our support team or send us a message
              </p>
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

        {/* Modal Content */}
        <div className="p-6 space-y-6 max-h-[calc(90vh-130px)] overflow-y-auto">
          {/* Quick Direct Contact Channels */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {/* Clickable Email Card (Opens Gmail in new tab + Copy Action) */}
            <div className="flex items-center justify-between p-3 rounded-xl bg-[#131F3F] border border-[#1E293B] hover:border-[#2563EB]/60 hover:bg-[#182852] transition-all group">
              <a
                href={getGmailComposeUrl()}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-3 min-w-0 flex-1 cursor-pointer"
                title="Compose message in Gmail in a new tab"
              >
                <div className="w-9 h-9 rounded-lg bg-[#2563EB]/20 text-[#60A5FA] flex items-center justify-center group-hover:scale-105 transition-transform shrink-0">
                  <Mail className="w-4 h-4" />
                </div>
                <div className="min-w-0">
                  <span className="block text-[11px] uppercase tracking-wider text-slate-400 font-semibold flex items-center gap-1">
                    <span>Official Email</span>
                    <ExternalLink className="w-2.5 h-2.5 text-slate-500 group-hover:text-[#60A5FA]" />
                  </span>
                  <span className="block text-xs font-medium text-white truncate group-hover:text-[#60A5FA] transition-colors">
                    {SUPPORT_EMAIL}
                  </span>
                </div>
              </a>
              <button
                type="button"
                onClick={handleCopyEmail}
                className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-[#1E293B] transition-colors shrink-0 ml-1 cursor-pointer"
                title={copied ? 'Copied email to clipboard!' : 'Copy email address'}
                aria-label="Copy email address"
              >
                {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
              </button>
            </div>

            {/* Clickable Phone / Helpline (tel link + copy action for desktop users) */}
            <div className="flex items-center justify-between p-3 rounded-xl bg-[#131F3F] border border-[#1E293B] hover:border-[#2563EB]/60 hover:bg-[#182852] transition-all group">
              <a
                href={`tel:${SUPPORT_HELPLINE_TEL}`}
                className="flex items-center gap-3 min-w-0 flex-1 cursor-pointer"
                title="Call AI Data Analyst Agent Helpline"
              >
                <div className="w-9 h-9 rounded-lg bg-[#2563EB]/20 text-[#60A5FA] flex items-center justify-center group-hover:scale-105 transition-transform shrink-0">
                  <Phone className="w-4 h-4" />
                </div>
                <div className="min-w-0">
                  <span className="block text-[11px] uppercase tracking-wider text-slate-400 font-semibold">
                    Helpline Support
                  </span>
                  <span className="block text-xs font-medium text-white truncate group-hover:text-[#60A5FA] transition-colors">
                    {SUPPORT_HELPLINE}
                  </span>
                </div>
              </a>
              <button
                type="button"
                onClick={handleCopyPhone}
                className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-[#1E293B] transition-colors shrink-0 ml-1 cursor-pointer"
                title={copiedPhone ? 'Copied phone number!' : 'Copy phone number'}
                aria-label="Copy helpline phone number"
              >
                {copiedPhone ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {/* Form or Success State */}
          {isSuccess ? (
            <div className="p-6 rounded-xl bg-emerald-950/40 border border-emerald-500/40 text-center space-y-4">
              <div className="w-12 h-12 mx-auto rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center">
                <CheckCircle2 className="w-7 h-7" />
              </div>
              <div>
                <h4 className="text-base font-bold text-white">Message Delivered Successfully</h4>
                <p className="text-xs text-slate-300 mt-1.5 leading-relaxed max-w-md mx-auto">
                  {successMessage}
                </p>
              </div>
              <div className="pt-2 flex flex-wrap items-center justify-center gap-3">
                <button
                  type="button"
                  onClick={handleResetForm}
                  className="px-4 py-2 text-xs font-semibold rounded-lg bg-[#1E293B] hover:bg-[#334155] text-white transition-colors cursor-pointer"
                >
                  Send Another Message
                </button>
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 text-xs font-semibold rounded-lg bg-[#2563EB] hover:bg-[#1D4ED8] text-white transition-colors cursor-pointer"
                >
                  Close
                </button>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Proactive Info Notice when SMTP is unconfigured */}
              {supportStatus && supportStatus.smtp_configured === false && !submitError && (
                <div className="p-3 rounded-xl bg-blue-950/30 border border-blue-500/30 text-slate-300 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-[#60A5FA] shrink-0 animate-pulse" />
                    <span>Direct support inbox: <strong className="text-white">{SUPPORT_EMAIL}</strong></span>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      type="button"
                      onClick={handleCopyEmail}
                      className="px-2.5 py-1 rounded bg-[#131F3F] hover:bg-[#1E293B] text-[#60A5FA] hover:text-white border border-[#2563EB]/40 text-[11px] font-medium transition-colors cursor-pointer inline-flex items-center gap-1"
                    >
                      {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                      <span>{copied ? 'Copied' : 'Copy Email'}</span>
                    </button>
                    <a
                      href={getGmailComposeUrl()}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="px-2.5 py-1 rounded bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-[11px] font-semibold transition-colors cursor-pointer inline-flex items-center gap-1"
                    >
                      <span>Open in Email</span>
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                </div>
              )}

              {/* Submission Error Banner with Full Fallback Suite */}
              {submitError && (
                <div className="p-4 rounded-xl bg-red-950/40 border border-red-500/50 text-red-200 text-xs space-y-3 animate-in fade-in duration-200">
                  <div className="flex items-start gap-2.5">
                    <AlertCircle className="w-4 h-4 shrink-0 text-red-400 mt-0.5" />
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold text-white">Message Submission Failed</p>
                      <p className="text-red-300 mt-0.5 leading-relaxed text-[11px] sm:text-xs">
                        {submitError}
                      </p>
                    </div>
                  </div>

                  {/* Fallback Action Suite */}
                  <div className="pt-3 border-t border-red-500/30 space-y-2.5">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 text-[11px]">
                      <span className="text-slate-300 font-medium">
                        Send directly to our support inbox:
                      </span>
                      <span className="font-mono text-[#60A5FA] bg-[#0B132B]/80 px-2 py-0.5 rounded border border-[#1E293B] select-all font-semibold">
                        {SUPPORT_EMAIL}
                      </span>
                    </div>

                    <p className="text-[11px] text-slate-400 leading-relaxed">
                      Your message has been preserved. Open your email compose window or copy our email address to send directly:
                    </p>

                    <div className="flex flex-wrap items-center gap-2 pt-1">
                      {/* 1. Primary Open in Email (Gmail Web Compose in New Tab) */}
                      <a
                        href={getGmailComposeUrl()}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-[#2563EB] hover:bg-[#1D4ED8] text-white font-semibold text-xs transition-colors shadow-xs cursor-pointer"
                        title="Compose message in Gmail in a new browser tab"
                      >
                        <Mail className="w-3.5 h-3.5" />
                        <span>Open in Email</span>
                        <ExternalLink className="w-3 h-3 text-blue-200" />
                      </a>

                      {/* 2. Copy Email Address */}
                      <button
                        type="button"
                        onClick={handleCopyEmail}
                        className={`inline-flex items-center gap-1.5 px-3 py-2 rounded-lg font-medium text-xs transition-colors border cursor-pointer ${
                          copied
                            ? 'bg-emerald-950/70 border-emerald-500 text-emerald-300'
                            : 'bg-[#1E293B] hover:bg-[#334155] border-slate-700 text-slate-200 hover:text-white'
                        }`}
                        title="Copy support email address to clipboard"
                      >
                        {copied ? (
                          <>
                            <Check className="w-3.5 h-3.5 text-emerald-400" />
                            <span>Copied Address!</span>
                          </>
                        ) : (
                          <>
                            <Copy className="w-3.5 h-3.5 text-slate-300" />
                            <span>Copy Email Address</span>
                          </>
                        )}
                      </button>

                      {/* 3. Open in Desktop Client (mailto) */}
                      <a
                        href={getMailtoUrl()}
                        className="inline-flex items-center gap-1.5 px-2.5 py-2 rounded-lg bg-[#131F3F] hover:bg-[#182852] border border-[#1E293B] hover:border-slate-600 text-slate-400 hover:text-slate-200 text-xs transition-colors"
                        title="Open default desktop mail application (e.g. Outlook, Thunderbird)"
                      >
                        <ExternalLink className="w-3 h-3 text-slate-400" />
                        <span>Desktop App</span>
                      </a>
                    </div>
                  </div>
                </div>
              )}

              {/* Full Name */}
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  Full Name <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => {
                    setFullName(e.target.value);
                    if (fieldErrors.fullName) {
                      setFieldErrors((prev) => ({ ...prev, fullName: '' }));
                    }
                  }}
                  placeholder="Enter your full name"
                  disabled={isSubmitting}
                  className={`w-full px-3.5 py-2.5 text-xs sm:text-sm bg-[#131F3F] text-white border ${
                    fieldErrors.fullName ? 'border-red-500 focus:ring-red-500/30' : 'border-[#1E293B] focus:border-[#2563EB]'
                  } rounded-xl focus:outline-none focus:ring-2 focus:ring-[#2563EB]/30 transition-all placeholder:text-slate-500 disabled:opacity-50`}
                />
                {fieldErrors.fullName && (
                  <p className="text-[11px] text-red-400 mt-1">{fieldErrors.fullName}</p>
                )}
              </div>

              {/* Email Address */}
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  Email Address <span className="text-red-400">*</span>
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    if (fieldErrors.email) {
                      setFieldErrors((prev) => ({ ...prev, email: '' }));
                    }
                  }}
                  placeholder="name@example.com"
                  disabled={isSubmitting}
                  className={`w-full px-3.5 py-2.5 text-xs sm:text-sm bg-[#131F3F] text-white border ${
                    fieldErrors.email ? 'border-red-500 focus:ring-red-500/30' : 'border-[#1E293B] focus:border-[#2563EB]'
                  } rounded-xl focus:outline-none focus:ring-2 focus:ring-[#2563EB]/30 transition-all placeholder:text-slate-500 disabled:opacity-50`}
                />
                {fieldErrors.email && (
                  <p className="text-[11px] text-red-400 mt-1">{fieldErrors.email}</p>
                )}
              </div>

              {/* Subject */}
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  Subject <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  value={subject}
                  onChange={(e) => {
                    setSubject(e.target.value);
                    if (fieldErrors.subject) {
                      setFieldErrors((prev) => ({ ...prev, subject: '' }));
                    }
                  }}
                  placeholder="What can we help you with?"
                  disabled={isSubmitting}
                  className={`w-full px-3.5 py-2.5 text-xs sm:text-sm bg-[#131F3F] text-white border ${
                    fieldErrors.subject ? 'border-red-500 focus:ring-red-500/30' : 'border-[#1E293B] focus:border-[#2563EB]'
                  } rounded-xl focus:outline-none focus:ring-2 focus:ring-[#2563EB]/30 transition-all placeholder:text-slate-500 disabled:opacity-50`}
                />
                {fieldErrors.subject && (
                  <p className="text-[11px] text-red-400 mt-1">{fieldErrors.subject}</p>
                )}
              </div>

              {/* Message */}
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  Message <span className="text-red-400">*</span>
                </label>
                <textarea
                  value={message}
                  onChange={(e) => {
                    setMessage(e.target.value);
                    if (fieldErrors.message) {
                      setFieldErrors((prev) => ({ ...prev, message: '' }));
                    }
                  }}
                  placeholder="Describe your issue, dataset question, or feedback in detail..."
                  rows={4}
                  disabled={isSubmitting}
                  className={`w-full px-3.5 py-2.5 text-xs sm:text-sm bg-[#131F3F] text-white border ${
                    fieldErrors.message ? 'border-red-500 focus:ring-red-500/30' : 'border-[#1E293B] focus:border-[#2563EB]'
                  } rounded-xl focus:outline-none focus:ring-2 focus:ring-[#2563EB]/30 transition-all placeholder:text-slate-500 resize-none disabled:opacity-50`}
                />
                {fieldErrors.message && (
                  <p className="text-[11px] text-red-400 mt-1">{fieldErrors.message}</p>
                )}
              </div>

              {/* Action Buttons */}
              <div className="pt-2 flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={onClose}
                  disabled={isSubmitting}
                  className="px-4 py-2 text-xs font-semibold rounded-lg bg-[#1E293B] hover:bg-[#334155] text-slate-300 hover:text-white transition-colors cursor-pointer disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-xs font-semibold shadow-md hover:shadow-lg transition-all cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {isSubmitting ? (
                    <>
                      <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      <span>Sending Message...</span>
                    </>
                  ) : (
                    <>
                      <Send className="w-3.5 h-3.5" />
                      <span>Send Message</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};

export default SupportModal;
