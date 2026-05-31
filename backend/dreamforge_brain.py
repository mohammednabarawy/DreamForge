"""
DreamForge AI Brain layer.
Handles local GGUF execution, API-based routers, cost optimizations, and structured JSON output.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from _paths import BACKEND_ROOT, PROJECT_ROOT, extend_sys_path
extend_sys_path()

# Native xllamacpp loader check
try:
    import xllamacpp as xlc
    XLC_AVAILABLE = True
except ImportError:
    xlc = None
    XLC_AVAILABLE = False


# Cache the server instance at module level to prevent reloading the 4.6GB model on every call.
_EMBEDDED_LLM_SERVER = None

LOCAL_IMAGE_BACKEND = "local_comfy"
DEFAULT_EMBEDDED_BRAIN_MODEL = "Qwen2.5-7B-Instruct-abliterated-v2.Q4_K_M.gguf"


@dataclass
class WorkflowStep:
    id: str
    operation: str
    mode: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BrainDecision:
    schema_version: str = "1.0"
    status: str = "planned"
    operations: List[str] = field(default_factory=list)
    workflow_plan: List[WorkflowStep] = field(default_factory=list)
    mode: str = "generate"
    patch: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    suggested_brain_provider: str = "heuristic"
    suggested_image_backend: str = LOCAL_IMAGE_BACKEND
    workflow_blueprint: Dict[str, Any] = field(default_factory=dict)
    requires_approval: bool = False
    warnings: List[str] = field(default_factory=list)
    message: str = ""
    actions: List[str] = field(default_factory=list)
    downloads: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["workflow_plan"] = [asdict(step) for step in self.workflow_plan]
        payload["actions"] = self.actions or list(self.operations)
        return payload

class BrainProvider:
    """Base class for all reasoning brain providers."""
    def think(self, prompt: str, system_prompt: str) -> str:
        raise NotImplementedError()


class EmbeddedLlamaCppProvider(BrainProvider):
    """Loads and queries GGUF model locally using native xllamacpp (llama.cpp) bindings."""
    def __init__(self, model_name: str = DEFAULT_EMBEDDED_BRAIN_MODEL):
        self.model_name = model_name

    def _get_model_path(self) -> Path:
        # Check standard models/llm and models/LLM directories
        from dreamforge_cli_inventory import MODELS_ROOT
        for root_name in ("llm", "LLM"):
            path = Path(MODELS_ROOT) / root_name / self.model_name
            if path.is_file():
                return path
            fallback = BACKEND_ROOT / "models" / root_name / self.model_name
            if fallback.is_file():
                return fallback

        if self.model_name != DEFAULT_EMBEDDED_BRAIN_MODEL:
            return Path(MODELS_ROOT) / "LLM" / self.model_name

        # Glob patterns if exact name not found
        for root_name in ("llm", "LLM"):
            for base_dir in (Path(MODELS_ROOT), BACKEND_ROOT / "models"):
                root = base_dir / root_name
                if root.is_dir():
                    for pattern in (
                        "Qwen2.5-7B-Instruct*.gguf",
                        "Qwen2.5-3B-Instruct*.gguf",
                        "*Qwen2.5*.gguf",
                        "gemma-3-4b*.gguf",
                        "Gemma-3-4B*.gguf",
                        "Llama-3.2-3B*.gguf",
                        "llama-3.2-3b*.gguf",
                        "*.gguf",
                    ):
                        found = sorted(root.glob(pattern))
                        if found:
                            return found[0]
        # Return default path if nothing else found
        return Path(MODELS_ROOT) / "LLM" / self.model_name

    def think(self, prompt: str, system_prompt: str) -> str:
        global _EMBEDDED_LLM_SERVER
        if not XLC_AVAILABLE:
            raise RuntimeError("xllamacpp package is not installed/available in this Python environment.")

        model_path = self._get_model_path()
        if not model_path.is_file():
            raise FileNotFoundError(f"Embedded GGUF model file not found at {model_path}")

        # Lazy initialize and cache the server
        if _EMBEDDED_LLM_SERVER is None:
            print(f"[DreamForge Brain] Initializing local GGUF server with: {model_path}", file=sys.stderr)
            params = xlc.CommonParams()
            params.prompt = ""
            params.model.path = str(model_path)
            # Auto VRAM routing: use all available GPU layers (-1)
            params.n_gpu_layers = -1
            params.n_ctx = 4096
            params.ctx_shift = True
            params.cpuparams.n_threads = 4
            params.cpuparams_batch.n_threads = 2
            params.endpoint_metrics = False
            
            try:
                _EMBEDDED_LLM_SERVER = xlc.Server(params)
            except Exception as e:
                raise RuntimeError(f"Failed to boot xllamacpp.Server: {e}")

        # Query completions
        result_text = ""
        done = False
        error_msg = None

        def callback(chunk):
            nonlocal result_text, done, error_msg
            if not chunk or 'choices' not in chunk or len(chunk['choices']) == 0:
                return
            delta = chunk['choices'][0].get('delta', {})
            if 'content' in delta:
                content = delta['content']
                if content:
                    result_text += content

        chat = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        try:
            _EMBEDDED_LLM_SERVER.handle_chat_completions(
                {
                    "stream": True,
                    "messages": chat,
                    "temperature": 0.1,
                },
                callback,
            )
        except Exception as e:
            raise RuntimeError(f"xllamacpp execution error: {e}")

        return result_text


class OllamaProvider(BrainProvider):
    """Ollama REST API adapter."""
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "gemma3:4b"):
        self.base_url = base_url.rstrip('/')
        self.model = model

    def think(self, prompt: str, system_prompt: str) -> str:
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "stream": False,
            "options": {
                "temperature": 0.1
            }
        }
        
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
                return data.get("message", {}).get("content", "").strip()
        except Exception as e:
            raise RuntimeError(f"Ollama API request failed: {e}")


class OpenAICompatibleProvider(BrainProvider):
    """Generic OpenAI-compatible local endpoint adapter (LM Studio, llama.cpp server, LocalAI, vLLM)."""
    def __init__(self, base_url: str, model: str, api_key: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.api_key = api_key

    def think(self, prompt: str, system_prompt: str) -> str:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 1024
        }
        
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "").strip()
                raise ValueError("No choices in OpenAI API response")
        except Exception as e:
            raise RuntimeError(f"OpenAI-compatible request failed: {e}")


def _extract_json_object(text: str) -> Dict[str, Any]:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            raise
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("Brain response is not a JSON object")
    return parsed


def _infer_cn_type(text: str) -> str:
    lowered = (text or "").lower()
    checks = (
        (("depth controlnet", "depth map", "depth"), "depth"),
        (("canny", "edge"), "canny"),
        (("openpose", "pose controlnet"), "pose"),
        (("lineart", "line art"), "lineart"),
        (("scribble", "sketch"), "scribble"),
        (("pose",), "pose"),
    )
    for keywords, cn_type in checks:
        if any(keyword in lowered for keyword in keywords):
            return cn_type
    return "depth"


def _first_path(value: Any) -> str:
    if isinstance(value, list):
        for item in value:
            text = str(item or "").strip()
            if text:
                return text
        return ""
    if isinstance(value, str):
        for part in value.split(","):
            text = part.strip()
            if text:
                return text
    return ""


def _dedupe(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for item in items:
        key = str(item or "").strip()
        if key and key not in seen:
            seen.add(key)
            out.append(key)
    return out


def _infer_operations(intent: str, *, has_image: bool = False, has_mask: bool = False) -> List[str]:
    try:
        from dreamforge_workflow_planner import resolve_operations_from_intent

        return resolve_operations_from_intent(intent, has_image=has_image, has_mask=has_mask)
    except Exception:
        text = (intent or "").lower()
        operations: List[str] = []
        if any(word in text for word in ("remove", "erase", "delete", "background people", "object")):
            operations.append("remove_object" if has_image else "inpaint")
        if any(word in text for word in ("smile", "face", "eyes", "expression", "portrait", "identity")):
            operations.append("face_edit")
        if any(word in text for word in ("cinematic", "cyberpunk", "anime", "style", "rainy", "rain", "color grade", "lighting")):
            operations.append("style_transfer")
        if any(word in text for word in ("upscale", "4k", "8k", "higher resolution", "enlarge")):
            operations.append("upscale")
        if any(word in text for word in ("analyze", "suggest", "improve", "critique")):
            operations.append("analyze_image" if has_image else "creative_guidance")
        if has_mask and "inpaint" not in operations:
            operations.append("inpaint")
        if not operations:
            operations.append("edit_image" if has_image else "generate_image")
        return _dedupe(operations)


def _mode_for_operations(operations: List[str], *, has_image: bool = False, has_mask: bool = False) -> str:
    if "upscale" in operations and len(operations) == 1:
        return "upscale"
    if "composite_layers" in operations or "text_integrate" in operations:
        return "agent"
    if has_mask or "inpaint" in operations or "remove_object" in operations or "outpaint" in operations:
        return "inpaint" if has_mask else "edit"
    if has_image:
        return "edit"
    if "analyze_image" in operations or "creative_guidance" in operations:
        return "agent"
    return "generate"


def _workflow_steps(operations: List[str], mode: str) -> List[WorkflowStep]:
    steps = []
    for index, operation in enumerate(operations, start=1):
        step_mode = "upscale" if operation == "upscale" else mode
        if operation in ("remove_object", "inpaint", "outpaint"):
            step_mode = "inpaint"
        elif operation in ("face_edit", "style_transfer", "restyle", "edit_image", "reference_guidance", "face_detail"):
            step_mode = "edit"
        elif operation in ("generate_image", "controlnet_structure", "hires_fix"):
            step_mode = "generate"
        elif operation in ("composite_layers", "text_integrate"):
            step_mode = "composite"
        steps.append(
            WorkflowStep(
                id=f"step_{index}",
                operation=operation,
                mode=step_mode,
                params={},
            )
        )
    return steps


def _primary_workflow_mode(operations: List[str]) -> str | None:
    for operation, mode in (
        ("text_integrate", "arabic_text_composite"),
        ("composite_layers", "area_composition"),
        ("face_detail", "face_detail"),
        ("reference_guidance", "ipadapter"),
        ("controlnet_structure", "controlnet"),
        ("hires_fix", "hires"),
        ("outpaint", "outpaint"),
    ):
        if operation in operations:
            return mode
    return None


def heuristic_brain_decision(
    user_intent: str,
    current_settings: Optional[dict] = None,
    selected_image: str = "",
    gallery: Optional[list] = None,
) -> Dict[str, Any]:
    settings = current_settings or {}
    has_image = bool(selected_image or settings.get("input_image") or settings.get("upscale_image"))
    has_mask = bool(settings.get("inpaint_mask_path") or settings.get("mask"))
    operations = _infer_operations(user_intent, has_image=has_image, has_mask=has_mask)
    mode = _mode_for_operations(operations, has_image=has_image, has_mask=has_mask)
    try:
        from dreamforge_workflow_planner import build_live_workflow_blueprint

        blueprint = build_live_workflow_blueprint(
            user_intent,
            operations=operations,
            has_image=has_image,
            has_mask=has_mask,
            has_references=bool(settings.get("reference_images") or settings.get("control_images")),
            current_settings=settings,
        )
    except Exception as exc:
        blueprint = {"status": "error", "warnings": [str(exc)], "image_backend": LOCAL_IMAGE_BACKEND}
    patch: Dict[str, Any] = {"prompt": user_intent}
    if has_image and mode in ("edit", "inpaint"):
        patch["input_image"] = selected_image or settings.get("input_image")
    if "upscale" in operations:
        patch.setdefault("upscale_method", "4x" if "4k" in (user_intent or "").lower() else "2x")
    if "hires_fix" in operations:
        patch.setdefault("hires_denoise", 0.35)
    primary_mode = _primary_workflow_mode(operations)
    if primary_mode:
        patch.setdefault("workflow_mode", primary_mode)
    if "controlnet_structure" in operations:
        patch.setdefault("cn_type", _infer_cn_type(user_intent))
        if has_image:
            patch.setdefault("input_image", selected_image or settings.get("input_image"))
            control_image = _first_path(settings.get("control_images")) or _first_path(
                settings.get("control_image")
            )
            if control_image:
                patch.setdefault("control_image", control_image)
    if "reference_guidance" in operations:
        reference_image = _first_path(settings.get("reference_images")) or _first_path(
            settings.get("reference_image")
        )
        if reference_image:
            patch.setdefault("reference_image", reference_image)
    if "face_detail" in operations:
        patch.setdefault("workflow_mode", "face_detail")
        if has_image:
            patch.setdefault("input_image", selected_image or settings.get("input_image"))
        text = (user_intent or "").lower()
        if any(word in text for word in ("hand", "hands", "finger", "fingers")):
            patch.setdefault("detail_target", "hand")
        patch.setdefault(
            "detail_prompt",
            "detailed hands, natural fingers"
            if patch.get("detail_target") == "hand"
            else "detailed face, sharp eyes, natural skin",
        )
    if "text_integrate" in operations:
        from dreamforge_arabic_composite import extract_arabic_text

        patch.setdefault("workflow_mode", "arabic_text_composite")
        patch.setdefault("style", "arabic_poster")
        arabic_text = settings.get("arabic_text") or extract_arabic_text(user_intent)
        if arabic_text:
            patch.setdefault("arabic_text", arabic_text)
    if len(operations) > 1:
        patch["execute_workflow_plan"] = True
    if "outpaint" in operations:
        patch.setdefault("edit_type", "outpaint")
        text = (user_intent or "").lower()
        if "left" in text:
            patch.setdefault("outpaint_direction", "left")
        elif "top" in text or "up" in text:
            patch.setdefault("outpaint_direction", "top")
        elif "bottom" in text or "down" in text:
            patch.setdefault("outpaint_direction", "bottom")
        else:
            patch.setdefault("outpaint_direction", "right")
    elif "remove_object" in operations and not has_mask:
        patch.setdefault("edit_type", "kontext")
    elif mode == "inpaint":
        patch.setdefault("edit_type", "inpaint")
    elif mode == "edit":
        patch.setdefault("edit_type", "auto")

    decision = BrainDecision(
        operations=operations,
        workflow_plan=_workflow_steps(operations, mode),
        mode=mode,
        patch=patch,
        confidence=0.68,
        suggested_brain_provider="heuristic",
        suggested_image_backend=LOCAL_IMAGE_BACKEND,
        workflow_blueprint=blueprint,
        requires_approval="remove_object" in operations and not has_mask,
        warnings=list(blueprint.get("warnings", [])) if isinstance(blueprint, dict) else [],
        message="Planned with the built-in local heuristic because no local brain model was required.",
        actions=operations,
    )
    return decision.to_dict()


def coerce_brain_decision(
    parsed: Dict[str, Any],
    *,
    user_intent: str,
    current_settings: Optional[dict] = None,
    selected_image: str = "",
    gallery: Optional[list] = None,
    provider_id: str = "unknown",
) -> Dict[str, Any]:
    fallback = heuristic_brain_decision(user_intent, current_settings, selected_image, gallery)
    raw_ops = parsed.get("operations") or parsed.get("actions") or []
    if isinstance(raw_ops, str):
        raw_ops = [raw_ops]
    operations = _dedupe([str(item) for item in raw_ops]) or fallback["operations"]

    raw_steps = parsed.get("workflow_plan") or parsed.get("steps") or []
    steps: List[WorkflowStep] = []
    if isinstance(raw_steps, list):
        for index, item in enumerate(raw_steps, start=1):
            if isinstance(item, str):
                operation = item
                step_mode = _mode_for_operations([operation], has_image=bool(selected_image))
                params = {}
            elif isinstance(item, dict):
                operation = str(item.get("operation") or item.get("name") or item.get("step") or operations[min(index - 1, len(operations) - 1)])
                step_mode = str(item.get("mode") or _mode_for_operations([operation], has_image=bool(selected_image)))
                params = item.get("params") if isinstance(item.get("params"), dict) else {}
            else:
                continue
            steps.append(WorkflowStep(id=f"step_{index}", operation=operation, mode=step_mode, params=params))
    mode = str(parsed.get("mode") or fallback["mode"])
    if mode not in ("generate", "edit", "inpaint", "upscale", "agent"):
        mode = fallback["mode"]
    patch = parsed.get("patch") if isinstance(parsed.get("patch"), dict) else {}
    if not patch:
        patch = fallback["patch"]
    confidence = parsed.get("confidence", fallback["confidence"])
    try:
        confidence = max(0.0, min(1.0, float(confidence)))
    except (TypeError, ValueError):
        confidence = fallback["confidence"]
    warnings = parsed.get("warnings") if isinstance(parsed.get("warnings"), list) else []
    downloads = parsed.get("downloads") if isinstance(parsed.get("downloads"), list) else []
    decision = BrainDecision(
        operations=operations,
        workflow_plan=steps or _workflow_steps(operations, mode),
        mode=mode,
        patch=patch,
        confidence=confidence,
        suggested_brain_provider=str(parsed.get("suggested_brain_provider") or provider_id),
        suggested_image_backend=LOCAL_IMAGE_BACKEND,
        workflow_blueprint=parsed.get("workflow_blueprint") if isinstance(parsed.get("workflow_blueprint"), dict) else fallback.get("workflow_blueprint", {}),
        requires_approval=bool(parsed.get("requires_approval", fallback["requires_approval"])),
        warnings=[str(item) for item in warnings],
        message=str(parsed.get("message") or fallback["message"]),
        actions=operations,
        downloads=[str(item) for item in downloads],
    )
    return decision.to_dict()


class AiBrain:
    """
    Central AI router/planner that coordinates prompt evaluation,
    workflow planning, model/provider selection, and self-healing.
    """
    def __init__(self):
        self.provider_inst: Optional[BrainProvider] = None
        self.provider_id: str = "auto"

    def configure(self, provider_id: str, base_url: str = "", model: str = "", api_key: str = ""):
        """Instantiate selected provider backend."""
        provider_id = (provider_id or "auto").lower()
        self.provider_id = provider_id
        if provider_id in ("embedded", "llamacpp", "llama.cpp"):
            self.provider_inst = EmbeddedLlamaCppProvider(model or DEFAULT_EMBEDDED_BRAIN_MODEL)
        elif provider_id == "ollama":
            self.provider_inst = OllamaProvider(base_url=base_url or "http://localhost:11434", model=model or "gemma3:4b")
        elif provider_id == "lmstudio":
            self.provider_inst = OpenAICompatibleProvider(base_url=base_url or "http://localhost:1234/v1", model=model or "local-model")
        elif provider_id in ("llama_cpp_server", "llama-server"):
            self.provider_inst = OpenAICompatibleProvider(base_url=base_url or "http://localhost:8080/v1", model=model or "local-model")
        elif provider_id in ("openai_compatible", "custom", "custom_local", "localai", "vllm"):
            self.provider_inst = OpenAICompatibleProvider(base_url=base_url, model=model, api_key=api_key)
        elif provider_id in ("openai", "openrouter", "anthropic", "gemini"):
            raise ValueError("DreamForge only accepts local/OpenAI-compatible brain endpoints; cloud image or cloud brain providers are disabled here.")
        else:
            # Safe default fallback
            if XLC_AVAILABLE:
                self.provider_inst = EmbeddedLlamaCppProvider(model or DEFAULT_EMBEDDED_BRAIN_MODEL)
                self.provider_id = "embedded"
            else:
                self.provider_inst = OllamaProvider()
                self.provider_id = "ollama"

    def think(self, prompt: str, system_prompt: str) -> str:
        """Send prompt to active provider."""
        if not self.provider_inst:
            # Auto-configure if not configured
            self.configure("embedded" if XLC_AVAILABLE else "ollama")
        
        try:
            return self.provider_inst.think(prompt, system_prompt)
        except Exception as e:
            print(f"[DreamForge Brain Warning] Active provider failed: {e}. Attempting local fallback...", file=sys.stderr)
            # Automatic fallback to Embedded LlamaCpp if available, otherwise Ollama
            if not isinstance(self.provider_inst, EmbeddedLlamaCppProvider) and XLC_AVAILABLE:
                try:
                    fallback = EmbeddedLlamaCppProvider()
                    return fallback.think(prompt, system_prompt)
                except Exception as fe:
                    print(f"[DreamForge Brain Warning] Embedded fallback failed: {fe}", file=sys.stderr)
            raise e

    def plan_decision(self, user_intent: str, current_settings: dict, selected_image: str, gallery: list) -> dict:
        """
        Structured operational planning. Matches requested schema:
        {
           "message": "...",
           "mode": "generate | edit | inpaint | upscale | agent",
           "patch": { ... },
           "actions": [...],
           "downloads": [...]
        }
        """
        system = (
            "You are DreamForge's local creative workflow planner and image-editing router.\n"
            "Return ONLY a clean JSON object. Never include markdown wrappers like ```json.\n"
            "Your output must adhere to this schema:\n"
            "{\n"
            '  "schema_version": "1.0",\n'
            '  "operations": ["face_edit", "remove_object", "style_transfer", "upscale"],\n'
            '  "workflow_plan": [{"operation": "face_edit", "mode": "edit", "params": {}}],\n'
            '  "workflow_blueprint": {"template_ids": ["flux_kontext_edit"], "node_patterns": []},\n'
            '  "mode": "generate | edit | inpaint | upscale | agent",\n'
            '  "patch": { "model": "string", "prompt": "string", "negative_prompt": "string", ... },\n'
            '  "confidence": 0.0,\n'
            '  "suggested_brain_provider": "embedded | ollama | lmstudio | llama_cpp_server | openai_compatible",\n'
            '  "suggested_image_backend": "local_comfy",\n'
            '  "requires_approval": false,\n'
            '  "warnings": [],\n'
            '  "message": "A summary explaining your decisions.",\n'
            '  "actions": ["list", "of", "operations"],\n'
            '  "downloads": ["list", "of", "missing", "models"]\n'
            "}\n\n"
            "DreamForge routing guidelines:\n"
            "- Image generation, image editing, and upscaling must always use local ComfyUI/local models.\n"
            "- Optional providers are decision-brain runtimes only, never online image generators.\n"
            "- generate: use for text-to-image when there is no source image. User can pick any model.\n"
            "- edit: use for global changes, style transfer, object swap. Default to FLUX Kontext for continuity.\n"
            "- inpaint: use only when a local region/mask is required or user says mask/erase/remove this area.\n"
            "- upscale: use only for enlargement/resolution repair of an existing image.\n"
            "- agent: use only when intent is completely ambiguous or parameters are missing.\n"
            "\n"
            "Be structured and concise."
        )

        user_context = {
            "instruction": user_intent,
            "current_settings": current_settings,
            "selected_image": selected_image,
            "gallery_count": len(gallery)
        }

        try:
            response = self.think(json.dumps(user_context), system)
            parsed = _extract_json_object(response)
            return coerce_brain_decision(
                parsed,
                user_intent=user_intent,
                current_settings=current_settings,
                selected_image=selected_image,
                gallery=gallery,
                provider_id=self.provider_id,
            )
        except Exception as e:
            payload = heuristic_brain_decision(user_intent, current_settings, selected_image, gallery)
            payload["warnings"].append(f"Local brain provider unavailable or returned invalid JSON: {e}")
            return payload

    def self_heal_workflow(self, workflow_graph: dict, error_message: str) -> dict:
        """
        Workflow repair engine. Parses ComfyUI missing nodes/VRAM crashes
        and suggests replacements or fixes.
        """
        system = (
            "You are DreamForge's self-healing workflow assistant.\n"
            "An error occurred executing a ComfyUI workflow:\n"
            f"ERROR: {error_message}\n\n"
            "Analyze the workflow graph and output a JSON fix matching this schema:\n"
            "{\n"
            '  "action": "replace_node | rebuild | reduce_resolution | fallback_model",\n'
            '  "target_node_id": "string (optional)",\n'
            '  "replacement": "string (optional)",\n'
            '  "explanation": "string"\n'
            "}\n"
            "Return ONLY JSON."
        )

        response = self.think(json.dumps(workflow_graph), system)
        
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`").strip()
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()

        try:
            return _extract_json_object(cleaned)
        except Exception:
            return {
                "action": "fallback_model",
                "explanation": f"Failed to self-heal workflow. Error was: {error_message}"
            }


def plan_user_intent(
    user_intent: str,
    *,
    current_settings: Optional[dict] = None,
    selected_image: str = "",
    gallery: Optional[list] = None,
    provider_id: str = "auto",
    base_url: str = "",
    model: str = "",
    api_key: str = "",
) -> Dict[str, Any]:
    """Plan a DreamForge operation without executing image generation."""
    from dreamforge_dynamic_presets import apply_dynamic_preset

    settings, dynamic_preset = apply_dynamic_preset(
        user_intent,
        current_settings or {},
    )
    brain = AiBrain()
    try:
        brain.configure(provider_id, base_url=base_url, model=model, api_key=api_key)
    except Exception as exc:
        payload = heuristic_brain_decision(user_intent, settings, selected_image, gallery or [])
        payload["dynamic_preset"] = dynamic_preset
        payload["warnings"].append(str(exc))
        return payload
    payload = brain.plan_decision(user_intent, settings, selected_image, gallery or [])
    payload["dynamic_preset"] = dynamic_preset
    return payload
