import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error('Error Boundary caught an error:', error, errorInfo);
    this.setState({
      error,
      errorInfo,
    });
  }

  handleReload = (): void => {
    window.location.reload();
  };

  handleReset = (): void => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-surface-primary flex items-center justify-center p-4">
          <div className="max-w-2xl w-full bg-surface-secondary border border-border rounded-xl shadow-2xl overflow-hidden">
            {/* Header */}
            <div className="bg-red-500/10 border-b border-red-500/20 px-6 py-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-red-500/20 rounded-lg">
                  <AlertTriangle className="w-6 h-6 text-red-500" />
                </div>
                <div>
                  <h1 className="text-xl font-semibold text-text-primary">
                    Something went wrong
                  </h1>
                  <p className="text-sm text-text-muted mt-1">
                    The application encountered an unexpected error
                  </p>
                </div>
              </div>
            </div>

            {/* Error details */}
            <div className="px-6 py-5">
              {this.state.error && (
                <div className="mb-4">
                  <h2 className="text-sm font-medium text-text-primary mb-2">
                    Error Message:
                  </h2>
                  <div className="bg-surface-tertiary border border-border rounded-lg p-3">
                    <code className="text-sm text-red-400 font-mono break-all">
                      {this.state.error.toString()}
                    </code>
                  </div>
                </div>
              )}

              {this.state.errorInfo && (
                <details className="mb-6">
                  <summary className="text-sm font-medium text-text-primary cursor-pointer hover:text-accent mb-2">
                    Stack Trace (click to expand)
                  </summary>
                  <div className="bg-surface-tertiary border border-border rounded-lg p-3 max-h-60 overflow-auto">
                    <pre className="text-xs text-text-muted font-mono whitespace-pre-wrap break-all">
                      {this.state.errorInfo.componentStack}
                    </pre>
                  </div>
                </details>
              )}

              <div className="flex gap-3">
                <button
                  onClick={this.handleReload}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-accent hover:bg-accent-hover text-white rounded-lg font-medium transition-colors"
                >
                  <RefreshCw className="w-4 h-4" />
                  Reload Page
                </button>
                <button
                  onClick={this.handleReset}
                  className="px-4 py-2.5 bg-surface-tertiary hover:bg-surface-tertiary/80 text-text-primary rounded-lg font-medium transition-colors border border-border"
                >
                  Try Again
                </button>
              </div>

              <p className="text-xs text-text-muted mt-4 text-center">
                If this error persists, please check the browser console for more details
              </p>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
