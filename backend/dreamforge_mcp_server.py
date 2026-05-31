import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional

from _paths import BACKEND_ROOT, PROJECT_ROOT, PYTHON_EXE, extend_sys_path

extend_sys_path()

from mcp.server.fastmcp import FastMCP

from dreamforge_engine import DreamForgeEngine
from dreamforge_agent_tools import (
    STYLE_RECIPES,
    build_agent_catalog,
    list_loras_for_agent,
    list_style_recipes_for_agent,
    recommend_model_for_task,
    validate_image as _validate_image,
)
from dreamforge_cli_inventory import (
    check_model_dependencies,
    model_setup_warnings,
    recommended_generation_models,
    resolve_generation_model,
)

# Define the server. The underlying generation engine is still DreamForge.
mcp = FastMCP("DreamForge")

# State tracking for active context
server_state = {
    "last_generation": None
}

DEFAULT_MCP_CAPABILITIES = {"read", "plan", "execute"}


def _mcp_capabilities() -> set[str]:
    raw = os.environ.get("DREAMFORGE_MCP_CAPABILITIES", "")
    if not raw:
        return set(DEFAULT_MCP_CAPABILITIES)
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def _require_mcp_capability(required: str, tool: str) -> str | None:
    if required in _mcp_capabilities():
        return None
    return json.dumps(
        {
            "status": "error",
            "code": "mcp_capability_denied",
            "message": f"MCP tool '{tool}' requires the '{required}' capability.",
            "capabilities": sorted(_mcp_capabilities()),
        },
        indent=2,
    )


def _mcp_status() -> dict:
    caps = sorted(_mcp_capabilities())
    return {
        "status": "success",
        "local_only_image_backend": True,
        "capabilities": caps,
        "execution_requires_approval": True,
        "arbitrary_shell": False,
        "arbitrary_filesystem": False,
        "agent_guide_tool": "get_agent_catalog",
        "style_parameter": "style",
        "lora_format": "filename.safetensors:weight",
    }


def _needs_execute_approval(tool: str) -> str | None:
    if "execute" not in _mcp_capabilities():
        return json.dumps(
            {
                "status": "error",
                "code": "mcp_capability_denied",
                "message": f"MCP tool '{tool}' requires the 'execute' capability.",
                "capabilities": sorted(_mcp_capabilities()),
            },
            indent=2,
        )
    return json.dumps(
        {
            "status": "needs_approval",
            "code": "mcp_execution_requires_approval",
            "message": f"Approve this local DreamForge job, then call '{tool}' again with approved=true.",
            "local_only_image_backend": True,
        },
        indent=2,
    )


def _execution_allowed(tool: str, approved: bool) -> str | None:
    if approved:
        if "execute" in _mcp_capabilities():
            return None
        return _needs_execute_approval(tool)
    return _needs_execute_approval(tool)

def update_last_generation(result: dict):
    """Update active context with successful generation results."""
    if result.get("status") == "success" and "manifest" in result:
        server_state["last_generation"] = result
        # Also store it in a local file so it survives restarts
        try:
            with open(os.path.join(PROJECT_ROOT, "outputs", ".last_generation.json"), "w") as f:
                json.dump(result, f)
        except Exception:
            pass

def get_last_generation_state():
    """Retrieve last generation, loading from disk if memory is empty."""
    if server_state["last_generation"]:
        return server_state["last_generation"]
    
    path = os.path.join(PROJECT_ROOT, "outputs", ".last_generation.json")
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                server_state["last_generation"] = json.load(f)
                return server_state["last_generation"]
        except Exception:
            pass
    return None

def run_dreamforge_cli(args: list) -> dict:
    """Helper to run the CLI and parse the JSON output."""
    cmd = [str(PYTHON_EXE), os.path.join(BACKEND_ROOT, "dreamforge_cli_direct.py"), "--json"] + args
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)
    
    parsed = None
    if result.returncode != 0:
        for line in result.stdout.splitlines():
            if line.startswith("{") and "error" in line:
                try:
                    parsed = json.loads(line)
                    break
                except:
                    pass
        if not parsed:
            parsed = {"status": "error", "message": f"Process exited with {result.returncode}", "stderr": result.stderr}
    else:
        stdout = result.stdout.strip()
        if stdout:
            try:
                parsed = json.loads(stdout)
            except json.JSONDecodeError:
                pass
        if not parsed:
            for line in result.stdout.splitlines():
                stripped = line.strip()
                if stripped.startswith(("{", "[")) and "status" in stripped:
                    try:
                        parsed = json.loads(stripped)
                        break
                    except json.JSONDecodeError:
                        pass
                        
    if not parsed:
        parsed = {"status": "error", "message": "No JSON output found in stdout", "stderr": result.stderr}
        
    update_last_generation(parsed)
    return parsed

def run_poster_pipeline(args: list) -> dict:
    """Helper to run the arabic poster pipeline."""
    cmd = [str(PYTHON_EXE), "arabic_poster_pipeline.py", "--json"] + args
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)
    
    if result.returncode != 0:
        return {"status": "error", "message": f"Process exited with {result.returncode}", "stderr": result.stderr}

    paths = []
    for line in result.stdout.splitlines():
        if "__OUTPUT_JSON__=" in line:
            try:
                paths = json.loads(line.split("__OUTPUT_JSON__=")[1])
                parsed = {"status": "success", "images": [{"path": p} for p in paths]}
                update_last_generation(parsed)
                return parsed
            except:
                pass
                
    return {"status": "error", "message": "No JSON output found in stdout", "stderr": result.stderr}

# --- ACTIVE CONTEXT & OUTPUT MANAGEMENT TOOLS ---

@mcp.tool()
def get_agent_catalog(
    style_limit: int = 40,
    lora_limit: int = 80,
    include_style_thumbnails: bool = False,
) -> str:
    """
    Return the full DreamForge agent capability guide: style recipes, LoRAs, model
    families, workflow modes, CLI/MCP parameters, and discovery tool index.
    Call this first when planning creative image jobs.
    """
    catalog = build_agent_catalog(style_limit=style_limit, lora_limit=lora_limit)
    if include_style_thumbnails:
        catalog["style_recipes"]["sample"] = list_style_recipes_for_agent(
            include_thumbnail=True,
            limit=style_limit,
        )
    return json.dumps(catalog, ensure_ascii=False, indent=2)

@mcp.tool()
def get_mcp_capabilities() -> str:
    """
    Report DreamForge MCP permissions and safety posture.
    """
    return json.dumps(_mcp_status(), indent=2)

@mcp.tool()
def get_last_generation() -> str:
    """
    Get the active context (the last successful generation).
    Returns the full generation bundle including output paths, manifest, and settings.
    """
    denied = _require_mcp_capability("read", "get_last_generation")
    if denied:
        return denied
    state = get_last_generation_state()
    if not state:
        return json.dumps({"status": "error", "message": "No active generation context found."})
    return json.dumps(state, indent=2)

@mcp.tool()
def list_outputs(since: Optional[int] = None, model: Optional[str] = None, style: Optional[str] = None, limit: int = 20) -> str:
    """
    List recent outputs, optionally filtered by timestamp (unix ms), model name, or style.
    """
    denied = _require_mcp_capability("read", "list_outputs")
    if denied:
        return denied
    res = DreamForgeEngine.list_outputs(limit=limit, since=since, model=model, style=style)
    return json.dumps(res, indent=2)

@mcp.tool()
def search_outputs(query: str, limit: int = 20) -> str:
    """
    Search recent generation manifests for a literal substring in the prompt or negative prompt.
    """
    denied = _require_mcp_capability("read", "search_outputs")
    if denied:
        return denied
    import dreamforge_output_index
    results, total = dreamforge_output_index.search_outputs(query, limit=limit)
    return json.dumps(
        {"status": "success", "results": results, "total": total}, indent=2
    )

@mcp.tool()
def get_generation_bundle(manifest_path: str) -> str:
    """
    Return the full generation metadata bundle for a given manifest JSON path.
    """
    denied = _require_mcp_capability("read", "get_generation_bundle")
    if denied:
        return denied
    import dreamforge_output_index
    bundle = dreamforge_output_index.get_generation_bundle(manifest_path)
    return json.dumps(bundle, indent=2)


# --- GENERATION & EDITING TOOLS ---

@mcp.tool()
def plan_workflow(
    instruction: str,
    selected_image: Optional[str] = None,
    brain_provider: str = "auto",
    brain_base_url: str = "",
    brain_model: str = "",
) -> str:
    """
    Plan local DreamForge operations for an agent without executing generation.
    Image execution stays local-only; optional providers are decision-brain runtimes.
    """
    denied = _require_mcp_capability("plan", "plan_workflow")
    if denied:
        return denied
    decision = DreamForgeEngine.plan(
        instruction,
        selected_image=selected_image,
        brain_provider=brain_provider,
        brain_base_url=brain_base_url,
        brain_model=brain_model,
    )
    return json.dumps(decision, ensure_ascii=False, indent=2)

@mcp.tool()
def generate_image(
    prompt: str,
    model: Optional[str] = None,
    style: str = "none",
    negative_prompt: str = "",
    aspect_ratio: Optional[str] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    performance: str = "Speed",
    image_number: int = 1,
    styles: Optional[List[str]] = None,
    seed: int = -1,
    steps: Optional[int] = None,
    cfg_scale: Optional[float] = None,
    vram_profile: str = "16gb",
    subject: Optional[str] = None,
    composition: Optional[str] = None,
    lighting: Optional[str] = None,
    mood: Optional[str] = None,
    camera: Optional[str] = None,
    validate: bool = True,
    check_fake_text: bool = False,
    brand_kit: Optional[str] = None,
    output: Optional[str] = None,
    control_image: Optional[str] = None,
    cn_type: str = "None",
    controlnet_model: Optional[str] = None,
    cn_strength: Optional[float] = None,
    hires: bool = False,
    hires_denoise: float = 0.35,
    reference_images: Optional[List[str]] = None,
    reference_mode: str = "",
    reference_weight: float = 0.65,
    region_prompts: Optional[List[str]] = None,
    region_prompts_json: str = "",
    lora: Optional[List[str]] = None,
    prompt_enhancer: str = "none",
    approved: bool = False,
) -> str:
    """
    Generate an image using the local DreamForge engine.

    ``style`` selects a DreamForge style recipe (product_ad, cinematic, sai_enhance, …).
    Use ``list_styles`` or ``get_agent_catalog`` to discover recipe ids, models, and aspect defaults.
    ``styles`` is an advanced override for embedded SDXL prompt fragments; usually leave unset
    so the recipe supplies them.
    ``lora`` accepts entries like ``detail_tweaker_xl.safetensors:0.6`` (see ``list_loras``).
    """
    blocked = _execution_allowed("generate_image", approved)
    if blocked:
        return blocked
    params = {
        "prompt": prompt, "model": model, "style": style, "negative_prompt": negative_prompt,
        "aspect_ratio": aspect_ratio, "width": width, "height": height, "performance": performance,
        "image_number": image_number, "styles": styles, "seed": seed, "steps": steps, "cfg_scale": cfg_scale,
        "vram_profile": vram_profile, "subject": subject, "composition": composition, "lighting": lighting,
        "mood": mood, "camera": camera, "validate_output": validate, "check_fake_text": check_fake_text,
        "brand_kit": brand_kit, "output": output, "input_image": control_image,
        "cn_selection": "Custom..." if control_image else "None", "cn_type": cn_type,
        "controlnet_model": controlnet_model, "cn_strength": cn_strength,
        "hires": hires, "hires_denoise": hires_denoise,
        "reference_images": reference_images, "reference_mode": reference_mode,
        "reference_weight": reference_weight, "region_prompts": region_prompts,
        "region_prompts_json": region_prompts_json,
        "lora": lora or [],
        "prompt_enhancer": prompt_enhancer,
    }
    res = DreamForgeEngine.execute_job(params)
    return json.dumps(res, indent=2)

@mcp.tool()
def edit_image(
    input_image: str,
    prompt: str = "",
    model: Optional[str] = None,
    edit_type: str = "auto",
    inpaint_mask_path: Optional[str] = None,
    vram_profile: str = "16gb",
    output: Optional[str] = None,
    approved: bool = False,
) -> str:
    """
    Edit an existing image using img2img, inpaint, Flux Kontext, or Qwen Image Edit.
    input_image must be an absolute path.
    edit_type: auto | kontext | inpaint | img2img | qwen_edit
    inpaint_mask_path: absolute path to mask image when edit_type is inpaint.
    """
    blocked = _execution_allowed("edit_image", approved)
    if blocked:
        return blocked
    params = {
        "input_image": input_image, "prompt": prompt, "model": model, "edit_type": edit_type,
        "inpaint_mask_path": inpaint_mask_path, "vram_profile": vram_profile, "output": output,
        "use_comfy_server": True, "style": "image_edit"
    }
    res = DreamForgeEngine.execute_job(params)
    return json.dumps(res, indent=2)

@mcp.tool()
def generate_arabic_poster(
    arabic_text: str,
    scene_prompt: str,
    preset: str = "balanced",
    text_position: str = "center",
    font_style: str = "default",
    image_number: int = 1,
    aspect_ratio: str = "896x1152",
    approved: bool = False,
) -> str:
    """
    Generate an image with perfectly composited Arabic text using the multi-pass pipeline.
    """
    blocked = _execution_allowed("generate_arabic_poster", approved)
    if blocked:
        return blocked
    args = [
        "--arabic-text", arabic_text,
        "--scene-prompt", scene_prompt,
        "--preset", preset,
        "--text-position", text_position,
        "--font-style", font_style,
        "--image-number", str(image_number),
        "--width", aspect_ratio.split("x")[0],
        "--height", aspect_ratio.split("x")[1]
    ]
    
    res = run_poster_pipeline(args)
    return json.dumps(res, indent=2)

@mcp.tool()
def upscale_image(
    image_path: str,
    method: str = "2x",
    prompt: str = "",
    approved: bool = False,
) -> str:
    """
    Upscale an existing image using DreamForge.
    """
    blocked = _execution_allowed("upscale_image", approved)
    if blocked:
        return blocked
    params = {
        "upscale_image": image_path, "upscale_method": method, "prompt": prompt,
        "use_comfy_server": True, "style": "image_edit", "cn_type": "upscale"
    }
    res = DreamForgeEngine.execute_job(params)
    return json.dumps(res, indent=2)

@mcp.tool()
def dry_run(
    prompt: str,
    model: Optional[str] = None,
    style: str = "none",
    vram_profile: str = "16gb",
    input_image: Optional[str] = None,
    workflow_mode: str = "",
    edit_type: str = "auto",
    reference_images: Optional[List[str]] = None,
    region_prompts: Optional[List[str]] = None,
    lora: Optional[List[str]] = None,
) -> str:
    """
    Preview generation plan without loading GPU models. Checks dependencies and resolves parameters.
    Pass ``style`` recipe id and optional ``lora`` stack before calling ``generate_image``.
    """
    denied = _require_mcp_capability("plan", "dry_run")
    if denied:
        return denied
    params = {
        "prompt": prompt,
        "model": model,
        "style": style,
        "vram_profile": vram_profile,
        "input_image": input_image,
        "workflow_mode": workflow_mode,
        "edit_type": edit_type,
        "reference_images": reference_images,
        "region_prompts": region_prompts,
        "lora": lora or [],
    }
    res = DreamForgeEngine.dry_run(params)
    return json.dumps(res, indent=2)



# --- DISCOVERY & INVENTORY TOOLS ---

@mcp.tool()
def list_models(include_metadata: bool = False) -> str:
    """Return installed models across checkpoints, diffusion_models, loras, controlnet, etc."""
    denied = _require_mcp_capability("read", "list_models")
    if denied:
        return denied
    models = DreamForgeEngine.list_models()
    if include_metadata:
        return json.dumps({"status": "success", "categories": models}, indent=2)
    summary = {}
    for cat, items in models.items():
        if items:
            summary[cat] = [item["name"] for item in items]
    return json.dumps({"status": "success", "categories": summary}, indent=2)

@mcp.tool()
def resolve_model(query: str) -> str:
    """
    Resolve a model by substring or filename and return its metadata and family.
    """
    denied = _require_mcp_capability("read", "resolve_model")
    if denied:
        return denied
    model = resolve_generation_model(query)
    if not model:
        return json.dumps({"status": "error", "message": f"Model not found matching: {query}"})
    return json.dumps({"status": "success", "model": model}, indent=2)

@mcp.tool()
def recommend_model(vram_profile: str = "16gb", limit: int = 5) -> str:
    """
    Get ranked recommendations for generation models based on VRAM profile.
    """
    denied = _require_mcp_capability("read", "recommend_model")
    if denied:
        return denied
    models = recommended_generation_models(profile=vram_profile)
    return json.dumps({"status": "success", "recommendations": models[:limit]}, indent=2)

@mcp.tool()
def check_dependencies(model_name: str) -> str:
    """
    Check if a modern model (Qwen, HiDream, etc) has its required companion files.
    """
    denied = _require_mcp_capability("read", "check_dependencies")
    if denied:
        return denied
    model = resolve_generation_model(model_name)
    if not model:
        return json.dumps({"status": "error", "message": "Model not found."})
        
    missing = check_model_dependencies(model)
    warnings = model_setup_warnings(model)
    
    return json.dumps({
        "status": "success",
        "model": model["name"],
        "ready": len(missing) == 0,
        "missing_dependencies": missing,
        "setup_warnings": warnings
    }, indent=2)

@mcp.tool()
def list_styles(
    include_thumbnail: bool = False,
    limit: int = 0,
    query: str = "",
) -> str:
    """
    List DreamForge style recipes (single-select presets for generate_image ``style``).
    Each recipe may set default models, aspect ratio, performance tier, and SDXL style fragments.
    """
    denied = _require_mcp_capability("read", "list_styles")
    if denied:
        return denied
    recipes = list_style_recipes_for_agent(include_thumbnail=include_thumbnail)
    if query.strip():
        needle = query.strip().lower()
        recipes = [
            item
            for item in recipes
            if needle in item["id"].lower() or needle in item.get("label", "").lower()
        ]
    if limit and limit > 0:
        recipes = recipes[:limit]
    return json.dumps(
        {
            "status": "success",
            "count": len(recipes),
            "parameter": "style",
            "styles": recipes,
        },
        ensure_ascii=False,
        indent=2,
    )

@mcp.tool()
def list_loras(limit: int = 0, query: str = "") -> str:
    """
    List installed LoRA files. Use entries as generate_image ``lora`` values:
    ``relative_or_filename.safetensors:weight`` (example ``detail_tweaker_xl.safetensors:0.6``).
    """
    denied = _require_mcp_capability("read", "list_loras")
    if denied:
        return denied
    items = list_loras_for_agent()
    if query.strip():
        needle = query.strip().lower()
        items = [
            item
            for item in items
            if needle in str(item.get("name", "")).lower()
            or needle in str(item.get("stem", "")).lower()
        ]
    if limit and limit > 0:
        items = items[:limit]
    return json.dumps(
        {
            "status": "success",
            "count": len(items),
            "parameter": "lora",
            "format": "filename.safetensors:weight",
            "loras": items,
        },
        indent=2,
    )

@mcp.tool()
def get_inventory(force_refresh: bool = False) -> str:
    """
    Return the cached desktop inventory: model categories, grouped style recipes, and presets.
    Complements ``list_models`` / ``list_styles`` / ``list_loras`` with gallery-oriented grouping.
    """
    denied = _require_mcp_capability("read", "get_inventory")
    if denied:
        return denied
    from dreamforge_model_library_cache import get_cached_inventory, get_cached_lora_gallery

    inventory, from_cache = get_cached_inventory(force_refresh=force_refresh)
    lora_gallery, lora_from_cache = get_cached_lora_gallery(force_refresh=force_refresh)
    payload = dict(inventory)
    payload["lora_gallery"] = lora_gallery
    payload["from_cache"] = from_cache
    payload["lora_from_cache"] = lora_from_cache
    return json.dumps(payload, ensure_ascii=False, indent=2)

@mcp.tool()
def recommend_for_style(
    style: str = "product_ad",
    vram_profile: str = "16gb",
    prefer_speed: bool = False,
    requires_input_image: bool = False,
    limit: int = 5,
) -> str:
    """
    Rank model families/checkpoints for a style recipe id or creative task name.
    Also checks recipe ``models`` list against installed checkpoints when ``style`` is a recipe id.
    """
    denied = _require_mcp_capability("read", "recommend_for_style")
    if denied:
        return denied
    recommendations = recommend_model_for_task(
        style,
        vram_profile=vram_profile,
        prefer_speed=prefer_speed,
        requires_input_image=requires_input_image,
    )
    recipe_models: list[dict[str, Any]] = []
    if style in STYLE_RECIPES:
        for candidate in STYLE_RECIPES[style].get("models") or []:
            resolved = resolve_generation_model(candidate)
            recipe_models.append(
                {
                    "requested": candidate,
                    "installed": bool(resolved),
                    "resolved_name": (resolved or {}).get("name"),
                    "family": (resolved or {}).get("family"),
                }
            )
    return json.dumps(
        {
            "status": "success",
            "style": style,
            "recipe_models": recipe_models,
            "recommendations": recommendations[: max(limit, 1)],
        },
        indent=2,
    )

@mcp.tool()
def validate_image(image_path: str, check_fake_text: bool = False) -> str:
    """
    Run standalone validation on an image (contrast, blank check, and optional fake-text detection).
    """
    if not os.path.exists(image_path):
        return json.dumps({"status": "error", "message": "Image path does not exist."})
        
    result = _validate_image(image_path, check_fake_text=check_fake_text)
    return json.dumps(result, indent=2)

# --- MCP RESOURCES ---

@mcp.resource("capabilities://guide")
def agent_catalog_resource() -> str:
    """Structured DreamForge agent capability guide (style recipes, LoRAs, workflows)."""
    return get_agent_catalog()

@mcp.resource("styles://catalog")
def styles_catalog_resource() -> str:
    """Full style recipe catalog for generate_image ``style`` parameter."""
    return list_styles()

@mcp.resource("loras://list")
def loras_list_resource() -> str:
    """Installed LoRA files and usage format."""
    return list_loras()

@mcp.resource("models://list")
def list_models_resource() -> str:
    """
    Get the complete list of available local models.
    """
    return list_models()

@mcp.resource("history://list")
def list_history_resource() -> str:
    """
    Get a summary list of recently generated outputs.
    """
    return list_outputs(limit=50)

@mcp.resource("outputs://list")
def list_outputs_resource() -> str:
    """
    Alias resource for history outputs.
    """
    return list_outputs(limit=50)

@mcp.resource("sessions://list")
def list_sessions_resource() -> str:
    """
    List output sessions discovered from local DreamForge manifests.
    """
    payload = DreamForgeEngine.list_outputs(limit=500)
    sessions: dict[str, int] = {}
    for item in payload.get("projects", []):
        session = str(item.get("session") or "unsorted")
        sessions[session] = sessions.get(session, 0) + 1
    return json.dumps(
        {
            "status": "success",
            "sessions": [
                {"id": session, "output_count": count}
                for session, count in sorted(sessions.items())
            ],
        },
        indent=2,
    )

@mcp.resource("projects://summary")
def project_summary_resource() -> str:
    """
    Summarize the local DreamForge project and available agent-safe resources.
    """
    return analyze_project()

# --- NEW MCP DEDICATED TOOLS ---

@mcp.tool()
def inpaint_image(
    input_image: str,
    mask_image: str,
    prompt: str = "",
    model: Optional[str] = None,
    vram_profile: str = "16gb",
    output: Optional[str] = None,
    approved: bool = False,
) -> str:
    """
    Perform local inpainting on a specific masked region of an image.
    input_image: absolute path to the source image.
    mask_image: absolute path to the black-and-white mask image.
    prompt: positive prompt describing what to fill the mask with.
    """
    return edit_image(
        input_image=input_image,
        prompt=prompt,
        model=model,
        edit_type="inpaint",
        inpaint_mask_path=mask_image,
        vram_profile=vram_profile,
        output=output,
        approved=approved,
    )

@mcp.tool()
def remove_object(
    input_image: str,
    mask_image: str,
    vram_profile: str = "16gb",
    output: Optional[str] = None,
    approved: bool = False,
) -> str:
    """
    Erase / remove an object from an image using the local inpaint/fill pipeline.
    input_image: absolute path to the source image.
    mask_image: absolute path to the black-and-white mask image highlighting the object to remove.
    """
    return edit_image(
        input_image=input_image,
        prompt="inpaint fill, erase object, clean background",
        edit_type="inpaint",
        inpaint_mask_path=mask_image,
        vram_profile=vram_profile,
        output=output,
        approved=approved,
    )

@mcp.tool()
def analyze_project() -> str:
    """
    Analyze and summarize the project directory state, outputs, and model availability.
    """
    try:
        models_payload = json.loads(list_models())
        models_inv = models_payload.get("categories") or models_payload
        outputs_list = json.loads(list_outputs(limit=10))
        
        total_outputs = outputs_list.get("total", 0)
        recent_images = outputs_list.get("projects") or outputs_list.get("results") or []
        
        summary = {
            "status": "success",
            "project_root": str(PROJECT_ROOT),
            "total_generations": total_outputs,
            "installed_models_summary": {
                cat: len(items) for cat, items in models_inv.items() if isinstance(items, list)
            },
            "style_recipe_count": len(STYLE_RECIPES),
            "lora_count": len(list_loras_for_agent()),
            "featured_style_recipes": [
                "product_ad",
                "cinematic",
                "fast_draft",
                "concept_art",
                "fashion_editorial",
            ],
            "agent_guide_tool": "get_agent_catalog",
            "recent_generations": [
                {
                    "prompt": item.get("prompt"),
                    "model": item.get("model"),
                    "timestamp": item.get("timestamp"),
                    "image": item.get("image")
                }
                for item in recent_images
            ]
        }
        return json.dumps(summary, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Failed to analyze project: {e}"})

@mcp.tool()
def create_workflow(
    prompt: str,
    mode: str = "generate",
    settings: Optional[dict] = None
) -> str:
    """
    Create a first-party DreamForge workflow blueprint without executing it.
    mode: generate | edit | inpaint | upscale | area_composition | ipadapter | hires
    """
    denied = _require_mcp_capability("plan", "create_workflow")
    if denied:
        return denied
    try:
        from dreamforge_workflow_planner import build_live_workflow_blueprint, resolve_operations_from_intent

        current_settings = dict(settings or {})
        current_settings.setdefault("prompt", prompt)
        current_settings.setdefault("workflow_mode", mode)
        has_image = bool(current_settings.get("input_image") or current_settings.get("upscale_image"))
        has_mask = bool(current_settings.get("inpaint_mask_path") or current_settings.get("mask"))
        has_refs = bool(current_settings.get("reference_images") or current_settings.get("control_images"))
        operations = resolve_operations_from_intent(
            prompt,
            has_image=has_image,
            has_mask=has_mask,
            has_references=has_refs,
        )
        mode_l = (mode or "").lower()
        if mode_l in ("hires", "hires_fix", "two_pass") and "hires_fix" not in operations:
            operations.append("hires_fix")
        if mode_l in ("ipadapter", "reference", "reference_ipadapter") and "reference_guidance" not in operations:
            operations.append("reference_guidance")
        if mode_l in ("area", "area_composition", "composite", "composition") and "composite_layers" not in operations:
            operations.append("composite_layers")
        blueprint = build_live_workflow_blueprint(
            prompt,
            operations=operations,
            has_image=has_image,
            has_mask=has_mask,
            has_references=has_refs,
            current_settings=current_settings,
        )
        return json.dumps({"status": "success", "mode": mode, "workflow_blueprint": blueprint}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": f"Failed to create workflow blueprint: {e}"})

if __name__ == "__main__":
    mcp.run()
