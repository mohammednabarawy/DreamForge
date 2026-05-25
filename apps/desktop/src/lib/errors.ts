/**
 * Friendly UI strings for the structured error codes emitted by the
 * DreamForge worker.  Keep this file in sync with
 * `backend/dreamforge_errors.py`.
 *
 * Each entry returns a title, a paragraph-length message, and an
 * ordered list of suggestions (preferred over the backend's defaults
 * because UI copy is allowed to be less terse than worker logs).
 *
 * Components should call {@link describeError} once per failure and
 * render the result however they want (status line, modal, toast,
 * inline panel, ...).
 */

import type {
  DreamForgeErrorCode,
  StructuredError,
} from "./tauri-api";

export type FriendlyError = {
  code: string;
  title: string;
  message: string;
  suggestions: string[];
  recoverable: boolean;
};

type CopyEntry = {
  title: string;
  message: string;
  suggestions: string[];
  recoverable: boolean;
};

const COPY: Record<DreamForgeErrorCode, CopyEntry> = {
  out_of_memory: {
    title: "Ran out of GPU memory",
    message:
      "The selected model needs more VRAM than is currently available. " +
      "DreamForge stopped before producing a broken image.",
    suggestions: [
      "Lower the resolution (try 1024x1024 or smaller).",
      "Reduce the batch / image count.",
      "Switch the VRAM profile to 'low' or 'no' in Settings.",
      "Use a quantized variant of the model (look for fp8 / Q4_K / Q5_K).",
      "Close other GPU apps (browsers, games, video editors).",
    ],
    recoverable: true,
  },
  missing_input_image: {
    title: "Reference image required",
    message:
      "This model or use case needs an input image (Kontext, Qwen-Edit, " +
      "image edit / upscale).",
    suggestions: [
      "Drop an image onto the canvas or set Input image in Settings.",
      "If you wanted text-to-image, switch the use case to a non-edit option.",
    ],
    recoverable: true,
  },
  invalid_input_image: {
    title: "Could not read the reference image",
    message:
      "DreamForge failed to load the chosen image. The file may be " +
      "missing, corrupted, or an unsupported format.",
    suggestions: [
      "Verify the file exists and is a PNG, JPEG, or WebP.",
      "Re-import the image from disk.",
    ],
    recoverable: true,
  },
  missing_model_dependencies: {
    title: "Companion files missing",
    message:
      "The selected model needs additional files (CLIP / VAE / text " +
      "encoders) that were not found on disk.",
    suggestions: [
      "Open the Models panel and click 'Download missing companions'.",
      "Or place the listed files into backend/models/{vae,text_encoders,clip_vision}.",
    ],
    recoverable: true,
  },
  model_not_found: {
    title: "Model not found",
    message: "The selected model is not present on disk.",
    suggestions: [
      "Pick a different model from the gallery.",
      "Re-run model organization (Settings -> Models -> Organize).",
      "Use the download surface to fetch the model again.",
    ],
    recoverable: true,
  },
  model_file_unreadable: {
    title: "Model file is unreadable",
    message:
      "DreamForge could not read the model file. It is likely truncated " +
      "or corrupted.",
    suggestions: [
      "Re-download the model.",
      "Check disk health if other files also fail to read.",
    ],
    recoverable: false,
  },
  unsupported_model_format: {
    title: "Unsupported model file",
    message:
      "The selected file is not a supported image-generation model.",
    suggestions: [
      "Run 'Organize models' so files move to their correct folders.",
      "Pick a different model from the gallery.",
    ],
    recoverable: false,
  },
  disk_full: {
    title: "Disk is full",
    message:
      "DreamForge tried to save an output image but the disk is out of " +
      "space.",
    suggestions: [
      "Free up space on the output drive.",
      "Move the outputs/ folder to a larger disk.",
    ],
    recoverable: true,
  },
  worker_crashed: {
    title: "GPU worker crashed",
    message:
      "The GPU worker process exited unexpectedly. The most recent " +
      "generation could not finish.",
    suggestions: [
      "Click 'Restart GPU engine'.",
      "Check worker.log for the underlying error.",
    ],
    recoverable: true,
  },
  generation_cancelled: {
    title: "Generation cancelled",
    message: "You cancelled the generation before it finished.",
    suggestions: [],
    recoverable: true,
  },
  generation_in_progress: {
    title: "Generation already running",
    message:
      "Another generation is already running on the GPU worker.",
    suggestions: [
      "Wait for the current job to finish.",
      "Or click Cancel to stop it and start a new one.",
    ],
    recoverable: true,
  },
  invalid_request: {
    title: "Invalid request",
    message:
      "DreamForge rejected the generation request because the parameters " +
      "were not valid.",
    suggestions: ["Try again with different settings."],
    recoverable: true,
  },
  generation_failed: {
    title: "Generation failed",
    message:
      "Something went wrong during generation. The GPU worker is still " +
      "alive; you can retry.",
    suggestions: [
      "Click 'Restart GPU engine' if retries keep failing.",
      "Check worker.log for the underlying traceback.",
    ],
    recoverable: true,
  },
};

const FALLBACK: CopyEntry = {
  title: "Generation failed",
  message:
    "Something went wrong. See worker.log or the details below for more.",
  suggestions: [
    "Try again.",
    "Click 'Restart GPU engine' if retries keep failing.",
  ],
  recoverable: true,
};

function asCode(value: unknown): DreamForgeErrorCode | undefined {
  if (typeof value !== "string") return undefined;
  if (value in COPY) return value as DreamForgeErrorCode;
  return undefined;
}

export function describeError(
  payload?: StructuredError | string | null,
): FriendlyError {
  if (!payload) {
    return { code: "unknown", ...FALLBACK };
  }
  if (typeof payload === "string") {
    const known = asCode(payload);
    if (known) {
      return { code: known, ...COPY[known] };
    }
    return {
      code: payload,
      ...FALLBACK,
      message: payload,
    };
  }

  const code =
    asCode(payload.code) ?? asCode(payload.error) ?? null;
  const entry = code ? COPY[code] : FALLBACK;
  const message =
    payload.message && payload.message.trim().length > 0
      ? payload.message
      : entry.message;
  const suggestions =
    payload.suggestions && payload.suggestions.length > 0
      ? payload.suggestions
      : entry.suggestions;
  return {
    code: code ?? String(payload.code ?? payload.error ?? "unknown"),
    title: entry.title,
    message,
    suggestions,
    recoverable: payload.recoverable ?? entry.recoverable,
  };
}

/**
 * Convenience for status-line use: returns a short single-line summary.
 */
export function shortErrorLine(payload?: StructuredError | string | null): string {
  const friendly = describeError(payload);
  return `${friendly.title} — ${friendly.message}`;
}
