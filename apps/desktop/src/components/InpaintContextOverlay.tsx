import type { InpaintContextPlan } from "../lib/studioBridge";
import { inpaintOverlayRects } from "../lib/inpaintContextOverlay";

type Props = {
  context?: InpaintContextPlan;
  className?: string;
};

/** Visualize backend crop box and mask bbox on top of the source image. */
export function InpaintContextOverlay({ context, className = "" }: Props) {
  const { crop, mask } = inpaintOverlayRects(context);
  if (!crop && !mask) return null;

  return (
    <div
      className={`pointer-events-none absolute inset-0 ${className}`}
      aria-hidden={!crop && !mask}
      role="img"
      aria-label={
        crop
          ? "Inpaint context crop region"
          : mask
            ? "Inpaint mask bounding box"
            : undefined
      }
    >
      {mask ? (
        <div
          className="absolute border border-dashed border-amber-300/80 bg-amber-400/10"
          style={{
            left: `${mask.left}%`,
            top: `${mask.top}%`,
            width: `${mask.width}%`,
            height: `${mask.height}%`,
          }}
        />
      ) : null}
      {crop ? (
        <div
          className="absolute border-2 border-sky-400/90 bg-sky-400/10 shadow-[inset_0_0_0_1px_rgba(56,189,248,0.35)]"
          style={{
            left: `${crop.left}%`,
            top: `${crop.top}%`,
            width: `${crop.width}%`,
            height: `${crop.height}%`,
          }}
        >
          <span className="absolute -top-4 left-0 rounded bg-sky-500/90 px-1 py-0.5 font-mono text-[8px] uppercase tracking-wide text-white">
            Context crop
          </span>
        </div>
      ) : null}
    </div>
  );
}
