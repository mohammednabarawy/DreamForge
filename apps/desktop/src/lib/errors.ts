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
      "Lower the resolution (try 768x768 first, then raise it if stable).",
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
      "Required helper files for this model or toolbox tool are not on disk yet.",
    suggestions: [
      "Click Download next to Generate, or Download missing assets in the error dialog.",
      "Workflow tools may need annotator weights under ComfyUI custom_nodes.",
      "Large workflow weights (over 500 MB) require approval before download.",
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
  unsupported_model_for_workflow: {
    title: "Model doesn't match this workflow",
    message:
      "The checkpoint and ControlNet (or text encoder) don't match what this toolbox workflow expects. " +
      "This is not a ComfyUI crash — installing the right SDXL ControlNet Union usually fixes it.",
    suggestions: [
      "Install SDXL ControlNet Union under models/controlnet/ (xinsir promax).",
      "Do not use SD 1.5 ControlNet (control_v11p_sd15_*) with SDXL checkpoints.",
      "Keep an SDXL checkpoint such as EpicRealism XL selected.",
    ],
    recoverable: true,
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
  worker_boot_failed: {
    title: "GPU engine failed to start",
    message:
      "The local GPU worker stopped before ComfyUI finished loading. DreamForge will retry once automatically when possible.",
    suggestions: [
      "Click Restart GPU engine once and wait until the title bar shows Engine ready.",
      "If ComfyUI is already running on port 8188, DreamForge reconnects instead of stopping it.",
      "First launch can take 20–90 seconds while PyTorch and ComfyUI load.",
      "Open the worker log if startup keeps failing after a restart.",
    ],
    recoverable: true,
  },
  worker_pipe_closed: {
    title: "GPU worker connection closed",
    message:
      "DreamForge could not send the job because the local GPU worker stopped or restarted.",
    suggestions: [
      "Click 'Restart GPU engine'.",
      "Wait until the engine is ready, then retry the generation.",
      "Check worker.log if the worker stops again.",
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
  comfy_workflow_validation: {
    title: "Workflow didn't pass ComfyUI validation",
    message:
      "ComfyUI rejected the generation graph before sampling could start. " +
      "Usually this means a node setting is missing or incompatible with your ComfyUI version.",
    suggestions: [
      "Restart DreamForge to pick up the latest workflow fix, then generate again.",
      "Restart the GPU engine if the problem persists.",
      "Open Technical diagnostics below for the exact node and field.",
    ],
    recoverable: true,
  },
  generation_failed: {
    title: "Generation failed",
    message:
      "Something went wrong during generation. Your prompt and settings are still here — you can retry.",
    suggestions: [
      "Try generating again with the same settings.",
      "Click 'Restart GPU engine' if retries keep failing.",
      "Open Technical diagnostics below or worker.log for the full traceback.",
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

const PLAIN_ERROR_RULES: Array<{
  test: (text: string) => boolean;
  title: string;
  message: string;
}> = [
  {
    test: (t) => /exited during generation|worker stopped before the job/i.test(t),
    title: "GPU worker stopped during generation",
    message:
      "The GPU worker exited before the image finished. ComfyUI may have run out of memory — try 768×768 or restart the GPU engine.",
  },
  {
    test: (t) => /exited before it became ready|did not become ready in time/i.test(t),
    title: "GPU engine did not finish starting",
    message:
      "The GPU worker stopped before ComfyUI finished loading. Restart the engine and wait until it is ready before generating.",
  },
  {
    test: (t) => /bridge_error|bridge invoke failed/i.test(t),
    title: "Engine connection problem",
    message:
      "DreamForge could not talk to the local GPU engine. Restart the engine and try again.",
  },
  {
    test: (t) => /unknown_cmd/i.test(t),
    title: "This action is not available",
    message:
      "The running engine does not recognize that command. Restart DreamForge or update to the latest build.",
  },
  {
    test: (t) => /generation_in_progress/i.test(t),
    title: "Generation already running",
    message: "Wait for the current image to finish, or cancel it first.",
  },
  {
    test: (t) => /missing_model|model_not_found|missing companion/i.test(t),
    title: "Model or companion files missing",
    message:
      "A required model or companion file is not installed. Open Models or download missing assets.",
  },
  {
    test: (t) => /missing_input_image|reference image/i.test(t),
    title: "Image required",
    message: "Attach or select a source image before running this task.",
  },
  {
    test: (t) => /out of memory|cuda out of memory|oom/i.test(t),
    title: "Ran out of GPU memory",
    message:
      "Try a smaller resolution, fewer variants, or a lower VRAM profile in Settings.",
  },
  {
    test: (t) =>
      /prompt_outputs_failed_validation|required_input_missing|node_errors/i.test(
        t,
      ),
    title: "Workflow didn't pass ComfyUI validation",
    message:
      "ComfyUI rejected the generation graph before sampling started. Restart DreamForge and try again.",
  },
  {
    test: (t) => /^Comfy HTTP \d+/i.test(t),
    title: "ComfyUI rejected the request",
    message:
      "The local ComfyUI engine returned an error before generation could start. Restart the GPU engine and try again.",
  },
  {
    test: (t) => /ENOENT|no such file|not found on disk/i.test(t),
    title: "File not found",
    message: "A file DreamForge expected is missing. Re-attach the image or re-download the model.",
  },
  {
    test: (t) => /^missing_/i.test(t),
    title: "Missing information",
    message: "Something required for this step was not provided. Check settings and try again.",
  },
];

function stripErrorNoise(raw: string): string {
  return raw
    .trim()
    .replace(/^Error:\s*/i, "")
    .replace(/^invoke\s+[^:]+:\s*/i, "")
    .replace(/^bridge_error:\s*/i, "")
    .replace(/^invalid_request:\s*/i, "")
    .replace(/\s+/g, " ");
}

/** Turn raw worker / bridge strings into user-facing copy. */
export function humanizePlainError(raw: string): { title: string; message: string } {
  const text = stripErrorNoise(raw);
  if (!text) {
    return {
      title: "Something went wrong",
      message: "Try again. Restart the GPU engine if the problem continues.",
    };
  }
  for (const rule of PLAIN_ERROR_RULES) {
    if (rule.test(text)) {
      return { title: rule.title, message: rule.message };
    }
  }
  if (/^[a-z][a-z0-9_]*(\s|$|:)/i.test(text) && text.length < 160) {
    const readable = text.replace(/_/g, " ").replace(/:\s*/, " — ");
    return {
      title: "Something went wrong",
      message: readable.charAt(0).toUpperCase() + readable.slice(1),
    };
  }
  return {
    title: "Something went wrong",
    message: text.length > 280 ? `${text.slice(0, 277)}…` : text,
  };
}

export function plainErrorLine(raw: string): string {
  const { title, message } = humanizePlainError(raw);
  return `${title} — ${message}`;
}

function asCode(value: unknown): DreamForgeErrorCode | undefined {
  if (typeof value !== "string") return undefined;
  if (value in COPY) return value as DreamForgeErrorCode;
  return undefined;
}

const COMFY_NODE_LABELS: Record<string, string> = {
  VAEDecodeTiled: "VAE decode (tiled)",
  VAEEncodeTiled: "VAE encode (tiled)",
  KSampler: "sampler",
  DualCLIPLoader: "text encoder loader",
};

function friendlyComfyNode(classType: string): string {
  return COMFY_NODE_LABELS[classType] ?? classType.replace(/_/g, " ");
}

export type ParsedComfyNodeIssue = {
  node: string;
  nodeLabel: string;
  issue: string;
  input?: string;
};

export type ParsedComfyValidation = {
  message: string;
  nodeIssues: ParsedComfyNodeIssue[];
};

/** True when a worker message is raw HTTP/JSON that should not appear in the main UI. */
export function isRawTechnicalMessage(message: string): boolean {
  const text = message.trim();
  if (!text) return false;
  if (/^Comfy HTTP \d+/i.test(text)) return true;
  if (
    /prompt_outputs_failed_validation|node_errors|required_input_missing/i.test(
      text,
    )
  ) {
    return true;
  }
  if (text.startsWith("{") && text.includes('"error"')) return true;
  return text.length > 280 && /"class_type"|"node_errors"/.test(text);
}

function summarizeComfyNodeIssue(
  classType: string,
  err: Record<string, unknown>,
): ParsedComfyNodeIssue {
  const errType = String(err.type ?? "");
  const extra =
    err.extra_info && typeof err.extra_info === "object"
      ? (err.extra_info as Record<string, unknown>)
      : {};
  const input = String(
    err.details ?? extra.input_name ?? extra.input ?? "",
  ).trim();
  let issue: string;
  if (errType === "required_input_missing" && input) {
    issue = `missing required input: ${input}`;
  } else if (errType === "invalid_input_type" && input) {
    issue = `invalid input: ${input}`;
  } else {
    issue = String(err.message ?? errType ?? "validation failed").trim();
  }
  return {
    node: classType,
    nodeLabel: friendlyComfyNode(classType),
    issue,
    ...(input ? { input } : {}),
  };
}

/** Parse Comfy HTTP validation JSON embedded in a worker exception string. */
export function parseComfyHttpError(raw: string): ParsedComfyValidation | null {
  const jsonStart = raw.indexOf("{");
  if (jsonStart < 0) return null;
  let payload: Record<string, unknown>;
  try {
    payload = JSON.parse(raw.slice(jsonStart)) as Record<string, unknown>;
  } catch {
    return null;
  }

  const nodeIssues: ParsedComfyNodeIssue[] = [];
  const nodeErrors = payload.node_errors;
  if (nodeErrors && typeof nodeErrors === "object") {
    for (const nodeBlob of Object.values(nodeErrors)) {
      if (!nodeBlob || typeof nodeBlob !== "object") continue;
      const blob = nodeBlob as Record<string, unknown>;
      const classType = String(blob.class_type ?? "unknown");
      const errors = blob.errors;
      if (!Array.isArray(errors)) continue;
      for (const item of errors) {
        if (item && typeof item === "object") {
          nodeIssues.push(
            summarizeComfyNodeIssue(classType, item as Record<string, unknown>),
          );
        }
      }
    }
  }

  const err = payload.error;
  const errType =
    err && typeof err === "object"
      ? String((err as Record<string, unknown>).type ?? "")
      : "";
  if (nodeIssues.length === 0 && errType !== "prompt_outputs_failed_validation") {
    return null;
  }

  if (nodeIssues.length > 0) {
    const first = nodeIssues[0];
    if (
      first.node === "VAEDecodeTiled" &&
      first.input &&
      ["overlap", "temporal_size", "temporal_overlap"].includes(first.input)
    ) {
      return {
        message:
          `DreamForge's tiled VAE decode step doesn't match your ComfyUI version — ` +
          `a required setting (${first.input}) is missing.`,
        nodeIssues,
      };
    }
    return {
      message:
        `ComfyUI rejected the generation graph before sampling started: ` +
        `${first.nodeLabel} — ${first.issue}.`,
      nodeIssues,
    };
  }

  return {
    message:
      "ComfyUI rejected the generation graph before sampling could start.",
    nodeIssues,
  };
}

function nodeIssuesFromDetails(
  details?: Record<string, unknown>,
): ParsedComfyNodeIssue[] {
  const raw = details?.node_issues;
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((item): item is Record<string, unknown> => !!item && typeof item === "object")
    .map((item) => ({
      node: String(item.node ?? "unknown"),
      nodeLabel: String(item.node_label ?? item.node ?? "unknown"),
      issue: String(item.issue ?? "validation failed"),
      ...(item.input ? { input: String(item.input) } : {}),
    }));
}

function resolveDisplayMessage(
  payload: StructuredError,
  entry: CopyEntry,
  code: DreamForgeErrorCode | null,
): string {
  const raw = payload.message?.trim() ?? "";
  if (!raw) return entry.message;
  if (code === "comfy_workflow_validation" && !isRawTechnicalMessage(raw)) {
    return raw;
  }
  if (isRawTechnicalMessage(raw)) {
    const parsed = parseComfyHttpError(raw);
    if (parsed) return parsed.message;
    return entry.message;
  }
  return raw;
}

function primaryNextStep(suggestions: string[]): string | null {
  const first = suggestions.find((s) => s.trim().length > 0);
  return first ?? null;
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
    const plain = humanizePlainError(payload);
    return {
      code: payload,
      title: plain.title,
      message: plain.message,
      suggestions: FALLBACK.suggestions,
      recoverable: true,
    };
  }

  const code =
    asCode(payload.code) ?? asCode(payload.error) ?? null;
  const entry = code ? COPY[code] : FALLBACK;
  const message = resolveDisplayMessage(payload, entry, code);
  const suggestions =
    payload.suggestions && payload.suggestions.length > 0
      ? payload.suggestions
      : entry.suggestions;
  const isWarning =
    (payload as { type?: string }).type === "warning" ||
    code === "low_system_ram" ||
    code === "vram_headroom_low" ||
    code === "low_disk_space";
  const nodeIssues = nodeIssuesFromDetails(payload.details);
  return {
    code: code ?? String(payload.code ?? payload.error ?? "unknown"),
    title: isWarning && entry.title === FALLBACK.title
      ? "Heads up before generating"
      : entry.title,
    message,
    suggestions,
    recoverable: payload.recoverable ?? entry.recoverable,
    details: {
      ...(payload.details ?? {}),
      ...(nodeIssues.length > 0 ? { node_issues: nodeIssues } : {}),
    },
    failureReport: payload.failure_report,
  };
}

const ENGINE_BOOT_DEFAULT_MESSAGE =
  "The GPU worker stopped before ComfyUI finished loading. DreamForge will retry once automatically when possible.";

/** Boot failures that usually clear after a single engine restart. */
export function isRecoverableBootFailure(
  bootMessage?: string,
  workerLogTail?: string,
): boolean {
  const text = `${bootMessage ?? ""}\n${workerLogTail ?? ""}`;
  return (
    /stdin closed|shutting down|worker exited before/i.test(text) ||
    /Stopped .* existing local ComfyUI/i.test(text) ||
    /did not become ready in time/i.test(text) ||
    /Managed ComfyUI stopped responding/i.test(text)
  );
}

function bootFailureMessage(bootMessage?: string, workerLogTail?: string): string {
  const trimmedBoot = bootMessage?.trim();
  const tail = workerLogTail?.trim();
  if (tail) {
    // Python warnings include an indented source line; neither is a failure cause.
    const lastLine = tail.split("\n").filter((line) =>
      line.trim() && !/^\s/.test(line) && !/\b\w*Warning:/.test(line)
    ).pop()?.trim() ?? "";
    if (/Using existing ComfyUI|Connected to existing ComfyUI/i.test(tail)) {
      return (
        "DreamForge found a healthy ComfyUI instance but the GPU worker exited before " +
        "handoff finished. DreamForge will retry startup once — or click Restart GPU engine."
      );
    }
    if (
      /Stopped .* existing local ComfyUI/i.test(tail) &&
      /stdin closed|shutting down/i.test(tail)
    ) {
      return (
        "DreamForge restarted ComfyUI during startup, then the GPU worker exited early. " +
        "Click Restart GPU engine once and wait — an existing ComfyUI on port 8188 is reused when possible."
      );
    }
    if (/stdin closed|shutting down/i.test(tail)) {
      return (
        "The GPU worker stopped during startup — often from a second Restart click or closing " +
        "the app while ComfyUI was still loading. DreamForge retries once automatically, or click Restart."
      );
    }
    if (/ComfyUI server exited early|did not open port|Timed out waiting for Comfy/i.test(tail)) {
      return lastLine || trimmedBoot || ENGINE_BOOT_DEFAULT_MESSAGE;
    }
    if (lastLine && lastLine.length > 24 && !lastLine.startsWith("{")) {
      return lastLine;
    }
  }
  return trimmedBoot || ENGINE_BOOT_DEFAULT_MESSAGE;
}

/** Structured error when the GPU worker fails during startup (no generation error payload). */
export function engineBootFailureError(
  bootMessage?: string,
  workerLogTail?: string,
): FriendlyError {
  const base = describeError({ code: "worker_boot_failed" });
  const message = bootFailureMessage(bootMessage, workerLogTail);
  const tail = workerLogTail?.trim();
  return {
    ...base,
    message,
    details: tail ? { worker_log_tail: tail } : undefined,
  };
}

/** One-line status copy: title plus an optional short human cause. */
export function shortErrorLine(payload?: StructuredError | string | null): string {
  const friendly = describeError(payload);
  const nextStep = primaryNextStep(friendly.suggestions);
  const firstSentence =
    friendly.message.split(/(?<=[.!?])\s+/)[0]?.trim() ?? "";
  if (
    firstSentence &&
    firstSentence.length <= 120 &&
    firstSentence !== friendly.title &&
    !isRawTechnicalMessage(firstSentence)
  ) {
    return `${friendly.title} — ${firstSentence}`;
  }
  if (nextStep && nextStep.length <= 100) {
    return `${friendly.title} — ${nextStep}`;
  }
  return friendly.title;
}
