import { Component, type ErrorInfo, type ReactNode } from 'react';
import { ShieldAlert, RotateCcw, Home } from 'lucide-react';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  public override state: ErrorBoundaryState = {
    hasError: false,
    error: null,
    errorInfo: null,
  };

  public static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error };
  }

  public override componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error('Sentra-X ErrorBoundary intercepted an unhandled runtime exception:', error, errorInfo);
    this.setState({ errorInfo });
  }

  private handleReset = (): void => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  private handleHardReload = (): void => {
    window.location.href = '/queue';
  };

  public override render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="min-h-screen bg-black text-zinc-100 flex flex-col justify-center items-center p-6 selection:bg-zinc-800 selection:text-white">
          <div className="w-full max-w-xl p-6 rounded-2xl bg-zinc-950 border border-zinc-850 shadow-2xl space-y-6">
            {/* Header Shield & Title */}
            <div className="flex items-start gap-4">
              <div className="p-3 rounded-xl bg-red-950/60 border border-red-800/80 text-red-400 shrink-0">
                <ShieldAlert className="size-6" />
              </div>
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <h1 className="text-sm font-mono font-bold text-zinc-100 uppercase tracking-wider">
                    SOC Workstation Diagnostic Intercept
                  </h1>
                  <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-red-950 text-red-300 border border-red-800">
                    Client Error
                  </span>
                </div>
                <p className="text-xs text-zinc-400 font-sans">
                  An unexpected UI runtime exception was safely isolated by the Sentra-X error boundary to prevent session corruption.
                </p>
              </div>
            </div>

            {/* Error Diagnostics Box */}
            <div className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-850 space-y-2 font-mono text-xs">
              <div className="text-zinc-500 text-[10px] uppercase font-bold tracking-wider">
                Exception Diagnostics
              </div>
              <div className="text-red-300 break-words font-semibold">
                {this.state.error?.name || 'Error'}: {this.state.error?.message || 'Unknown runtime error occurred.'}
              </div>
              {this.state.errorInfo && (
                <pre className="max-h-36 overflow-y-auto text-[10px] text-zinc-500 pt-2 border-t border-zinc-800/80 leading-relaxed">
                  {this.state.errorInfo.componentStack}
                </pre>
              )}
            </div>

            {/* Actions Toolbar */}
            <div className="flex flex-wrap items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={this.handleReset}
                className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-zinc-900 hover:bg-zinc-850 border border-zinc-800 text-zinc-300 text-xs font-mono transition-colors cursor-pointer"
              >
                <RotateCcw className="size-3.5 text-zinc-400" />
                <span>Dismiss &amp; Retry View</span>
              </button>

              <button
                type="button"
                onClick={this.handleHardReload}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-white hover:bg-zinc-200 text-black font-semibold text-xs font-mono shadow transition-colors cursor-pointer"
              >
                <Home className="size-3.5 text-black" />
                <span>Reset to Queue</span>
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
