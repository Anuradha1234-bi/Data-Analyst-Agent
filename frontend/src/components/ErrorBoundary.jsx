import React, { Component } from 'react';
import { AlertTriangle, RotateCcw, Home } from 'lucide-react';

/**
 * Enterprise-grade React Error Boundary.
 * Catches JavaScript errors in child components and renders a friendly fallback UI
 * instead of unmounting the tree and showing a blank white screen.
 */
export class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught a component runtime error:', error, errorInfo);
    this.setState({ errorInfo });
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
    if (this.props.onReset) {
      this.props.onReset();
    }
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="w-full min-h-[400px] flex items-center justify-center p-6 font-sans">
          <div className="max-w-lg w-full bg-white dark:bg-[#0F172A] border border-red-200 dark:border-red-900/60 rounded-2xl p-6 sm:p-8 shadow-xl text-center space-y-4 animate-in fade-in duration-200">
            <div className="w-14 h-14 mx-auto rounded-2xl bg-red-50 dark:bg-red-950/50 border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 flex items-center justify-center shadow-xs">
              <AlertTriangle className="w-7 h-7" />
            </div>

            <div>
              <h2 className="text-base sm:text-lg font-bold text-slate-900 dark:text-white">
                {this.props.title || 'Component Display Error'}
              </h2>
              <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-300 mt-1 leading-relaxed">
                An unexpected error occurred while rendering this view. Your data is safe.
              </p>
            </div>

            {this.state.error && (
              <div className="text-left bg-slate-50 dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 rounded-xl p-3 text-xs font-mono text-red-600 dark:text-red-300 overflow-x-auto max-h-32">
                {this.state.error.toString()}
              </div>
            )}

            <div className="pt-2 flex flex-wrap items-center justify-center gap-3">
              <button
                type="button"
                onClick={this.handleReset}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-[#2563EB] hover:bg-[#1D4ED8] text-white text-xs font-semibold shadow-xs transition-colors cursor-pointer"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Try Again</span>
              </button>
              <a
                href="/dashboard"
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 text-xs font-semibold transition-colors cursor-pointer border border-slate-200 dark:border-slate-700"
              >
                <Home className="w-3.5 h-3.5" />
                <span>Return to Dashboard</span>
              </a>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
