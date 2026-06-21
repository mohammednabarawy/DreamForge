import {
  Eraser,
  Minus,
  MousePointer2,
  Paintbrush,
  Plus,
  Trash2,
  User,
} from "lucide-react";
import type { ReactNode } from "react";

export type CanvasMaskTool = "paint" | "erase" | "subject" | "background";

type Props = {
  tool: CanvasMaskTool;
  onToolChange: (tool: CanvasMaskTool) => void;
  brush: number;
  onBrushChange: (brush: number) => void;
  onClear: () => void;
  busy?: boolean;
  disabled?: boolean;
};

function ToolButton({
  active,
  disabled,
  title,
  onClick,
  children,
}: {
  active: boolean;
  disabled?: boolean;
  title: string;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      title={title}
      disabled={disabled}
      onClick={onClick}
      className={`inline-flex h-8 w-8 items-center justify-center rounded-md border transition ${
        active
          ? "border-dfui-accent/50 bg-dfui-accent/20 text-dfui-accent"
          : "border-dfui-border/55 bg-dfui-panel/80 text-dfui-secondary hover:border-dfui-accent/35 hover:text-dfui-fg"
      } disabled:cursor-not-allowed disabled:opacity-45`}
    >
      {children}
    </button>
  );
}

export function CanvasToolRail({
  tool,
  onToolChange,
  brush,
  onBrushChange,
  onClear,
  busy = false,
  disabled = false,
}: Props) {
  const locked = disabled || busy;

  return (
    <div
      className="pointer-events-auto flex items-center gap-1 rounded-lg border border-dfui-border/60 bg-dfui-panel/90 px-1.5 py-1 shadow-glass backdrop-blur-md"
      role="toolbar"
      aria-label="Mask tools"
    >
      <ToolButton
        active={tool === "paint"}
        disabled={locked}
        title="Brush — paint the fix region"
        onClick={() => onToolChange("paint")}
      >
        <Paintbrush size={15} />
      </ToolButton>
      <ToolButton
        active={tool === "erase"}
        disabled={locked}
        title="Erase — remove from selection"
        onClick={() => onToolChange("erase")}
      >
        <Eraser size={15} />
      </ToolButton>
      <div className="mx-0.5 h-5 w-px bg-dfui-border/50" aria-hidden />
      <ToolButton
        active={false}
        disabled={locked || brush <= 4}
        title="Smaller brush"
        onClick={() => onBrushChange(Math.max(4, brush - 8))}
      >
        <Minus size={15} />
      </ToolButton>
      <span className="min-w-[2rem] text-center font-mono text-[10px] tabular-nums text-dfui-muted">
        {brush}
      </span>
      <ToolButton
        active={false}
        disabled={locked || brush >= 96}
        title="Larger brush"
        onClick={() => onBrushChange(Math.min(96, brush + 8))}
      >
        <Plus size={15} />
      </ToolButton>
      <div className="mx-0.5 h-5 w-px bg-dfui-border/50" aria-hidden />
      <ToolButton
        active={tool === "subject"}
        disabled={locked}
        title="Select subject"
        onClick={() => onToolChange("subject")}
      >
        <User size={15} />
      </ToolButton>
      <ToolButton
        active={tool === "background"}
        disabled={locked}
        title="Select background"
        onClick={() => onToolChange("background")}
      >
        <MousePointer2 size={15} />
      </ToolButton>
      <div className="mx-0.5 h-5 w-px bg-dfui-border/50" aria-hidden />
      <ToolButton
        active={false}
        disabled={locked}
        title="Clear selection"
        onClick={onClear}
      >
        <Trash2 size={15} />
      </ToolButton>
    </div>
  );
}
