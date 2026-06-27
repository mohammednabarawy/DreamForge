type Props = {
  direction?: "left" | "right" | "top" | "bottom" | "";
  amountDisplayPx?: number;
};

export function OutpaintPreviewOverlay({
  direction = "",
  amountDisplayPx = 0,
}: Props) {
  const dir = direction || "right";
  const amount = Math.max(8, Math.round(amountDisplayPx || 0));
  if (!dir || amount <= 0) return null;

  const style =
    dir === "left"
      ? { left: -amount, top: 0, width: amount, height: "100%" }
      : dir === "right"
        ? { right: -amount, top: 0, width: amount, height: "100%" }
        : dir === "top"
          ? { left: 0, top: -amount, width: "100%", height: amount }
          : { left: 0, bottom: -amount, width: "100%", height: amount };

  return (
    <div
      className="pointer-events-none absolute z-10 border border-violet-300/80 bg-violet-400/15 shadow-[inset_0_0_0_1px_rgba(196,181,253,0.35)]"
      style={style}
      role="img"
      aria-label={`Outpaint preview extending ${dir} by ${amount}px on canvas`}
    >
      <span className="absolute left-1 top-1 rounded bg-violet-500/90 px-1 py-0.5 font-mono text-[8px] uppercase tracking-wide text-white">
        Extend {dir}
      </span>
    </div>
  );
}
