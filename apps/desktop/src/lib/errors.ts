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
  FailureReport,
  StructuredError,
} from "./tauri-api";

export type FriendlyError = {
  code: string;
  title: string;
  message: string;
  suggestions: string[];
  recoverable: boolean;
  details?: Record<string, unknown>;
  failureReport?: FailureReport;
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
  virtual_memory_low: {
    title: "Windows virtual memory is low",
    message:
      "Windows could not commit enough memory while loading the model. " +
      "This is usually fixable without changing hardware.",
    suggestions: [
      "Close other apps to free RAM.",
      "Increase the Windows paging file, then reboot.",
      "Use a GGUF Q5/Q4 Flux variant or switch to SDXL for this run.",
    ],
    recoverable: true,
  },
  low_system_ram: {
    title: "Memory may be tight during load",
    message:
      "DreamForge estimates that loading this model may need more system " +
      "memory than is currently free. Generation can still proceed.",
    suggestions: [
      "Close browsers and other heavy apps before generating.",
      "Set VRAM profile to 8 GB or 5 GB in the Inspector.",
      "Use t5xxl_fp8.safetensors instead of fp16 T5 if companions are missing.",
    ],
    recoverable: true,
  },
  low_disk_space: {
    title: "Disk space is low",
    message:
      "The output drive has limited free space. Large images or batches " +
      "may fail to save.",
    suggestions: [
      "Free space on the output drive.",
      "Move the outputs/ folder to a larger disk.",
    ],
    recoverable: true,
  },
  vram_headroom_low: {
    title: "VRAM may be tight for this resolution",
    message:
      "Free GPU memory looks lower than this model typically needs at " +
      "full size. Try a lower resolution or a lower VRAM profile.",
    suggestions: [
      "Set VRAM profile to 8 GB or 5 GB in the Inspector.",
      "Generate at 768×768 or 512×512 first.",
      "Close other GPU apps.",
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
  comfy_server_crashed: {
    title: "Local ComfyUI stopped responding",
    message:
      "The managed ComfyUI backend became unreachable during generation. " +
      "This often means memory pressure or a failed workflow node.",
    suggestions: [
      "Review the repair actions below before retrying.",
      "Restart the GPU engine if the backend is still offline.",
      "Lower resolution or switch to a smaller local model.",
    ],
    recoverable: true,
  },
  missing_custom_node_pack: {
    title: "Custom node pack missing",
    message:
      "This workflow needs a ComfyUI custom node that is not installed.",
    suggestions: [
      "Use a first-party fallback workflow when available.",
      "Install custom nodes only after reviewing the exact pack.",
      "Restart ComfyUI after installing node packs.",
    ],
    recoverable: true,
  },
  unsupported_workflow_class: {
    title: "Unsupported workflow",
    message:
      "DreamForge will not execute this workflow class directly. Rebuild it as a first-party local workflow plan.",
    suggestions: [
      "Use the Brain plan to rebuild the request.",
      "Avoid running downloaded ComfyUI graphs directly.",
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

/** Preflight / advisory events from the worker (``type: "warning"``). */
export function describeWarning(
  payload?: StructuredError | string | null,
): FriendlyError {
  const friendly = describeError(payload);
  // Never label advisories as a hard failure.
  if (friendly.title === FALLBACK.title) {
    return {
      ...friendly,
      title: "Heads up before generating",
    };
  }
  return friendly;
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
  const isWarning =
    (payload as { type?: string }).type === "warning" ||
    code === "low_system_ram" ||
    code === "vram_headroom_low" ||
    code === "low_disk_space";
  return {
    code: code ?? String(payload.code ?? payload.error ?? "unknown"),
    title: isWarning && entry.title === FALLBACK.title
      ? "Heads up before generating"
      : entry.title,
    message,
    suggestions,
    recoverable: payload.recoverable ?? entry.recoverable,
    details: payload.details,
    failureReport: payload.failure_report,
  };
}

/**
 * Convenience for status-line use: returns a short single-line summary.
 */
export function shortErrorLine(payload?: StructuredError | string | null): string {
  const friendly = describeError(payload);
  return `${friendly.title} — ${friendly.message}`;
}
