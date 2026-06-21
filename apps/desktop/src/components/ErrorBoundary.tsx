import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = {
  children: ReactNode;
};

type State = {
  error: Error | null;
  resetKey: number;
};

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null, resetKey: 0 };

  static getDerivedStateFromError(error: Error): State {
    return { error, resetKey: 0 };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("DreamForge UI error:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex h-full flex-col items-center justify-center gap-3 bg-dfui-bg p-6 text-center">
          <p className="text-sm font-semibold text-dfui-fg">DreamForge hit a UI error</p>
          <p className="max-w-md font-mono text-[11px] text-red-300">{this.state.error.message}</p>
          <button
            type="button"
            onClick={() =>
              this.setState((prev) => ({
                error: null,
                resetKey: prev.resetKey + 1,
              }))
            }
            className="rounded-md border border-dfui-border/60 px-3 py-1.5 text-xs text-dfui-secondary hover:border-dfui-accent/40"
          >
            Try again
          </button>
        </div>
      );
    }
    return (
      <div key={this.state.resetKey} className="h-full min-h-0">
        {this.props.children}
      </div>
    );
  }
}
