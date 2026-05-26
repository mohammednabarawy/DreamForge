import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional

from _paths import BACKEND_ROOT, PROJECT_ROOT, PYTHON_EXE, extend_sys_path

extend_sys_path()

from mcp.server.fastmcp import FastMCP

import dreamforge_output_index
from dreamforge_agent_tools import USE_CASE_RECIPES, validate_image as _validate_image
from dreamforge_cli_inventory import (
    check_model_dependencies,
    list_model_inventory,
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
def get_last_generation() -> str:
    """
    Get the active context (the last successful generation).
    Returns the full generation bundle including output paths, manifest, and settings.
    """
    state = get_last_generation_state()
    if not state:
        return json.dumps({"status": "error", "message": "No active generation context found."})
    return json.dumps(state, indent=2)

@mcp.tool()
def list_outputs(since: Optional[int] = None, model: Optional[str] = None, use_case: Optional[str] = None, limit: int = 20) -> str:
    """
    List recent outputs, optionally filtered by timestamp (unix ms), model name, or use_case.
    """
    results, total = dreamforge_output_index.list_outputs(
        since=since, model=model, use_case=use_case, limit=limit
    )
    return json.dumps(
        {"status": "success", "results": results, "total": total}, indent=2
    )

@mcp.tool()
def search_outputs(query: str, limit: int = 20) -> str:
    """
    Search recent generation manifests for a literal substring in the prompt or negative prompt.
    """
    results, total = dreamforge_output_index.search_outputs(query, limit=limit)
    return json.dumps(
        {"status": "success", "results": results, "total": total}, indent=2
    )

@mcp.tool()
def get_generation_bundle(manifest_path: str) -> str:
    """
    Return the full generation metadata bundle for a given manifest JSON path.
    """
    bundle = dreamforge_output_index.get_generation_bundle(manifest_path)
    return json.dumps(bundle, indent=2)


# --- GENERATION & EDITING TOOLS ---

@mcp.tool()
def generate_image(
    prompt: str,
    model: Optional[str] = None,
    use_case: str = "none",
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
    output: Optional[str] = None
) -> str:
    """
    Generate an image using the local DreamForge engine. Supports SDXL, Flux, HiDream, Qwen, etc.
    """
    args = ["--prompt", prompt, "--use-case", use_case, "--performance", performance, "--image-number", str(image_number)]
    if model:
        args.extend(["--model", model])
    if negative_prompt:
        args.extend(["--negative-prompt", negative_prompt])
    if aspect_ratio:
        args.extend(["--aspect-ratio", aspect_ratio])
    if width:
        args.extend(["--width", str(width)])
    if height:
        args.extend(["--height", str(height)])
    if styles:
        args.extend(["--styles"] + styles)
    if seed != -1:
        args.extend(["--seed", str(seed)])
    if steps:
        args.extend(["--steps", str(steps)])
    if cfg_scale:
        args.extend(["--cfg-scale", str(cfg_scale)])
    if vram_profile:
        args.extend(["--vram-profile", vram_profile])
        
    # Creative brief
    if subject: args.extend(["--subject", subject])
    if composition: args.extend(["--composition", composition])
    if lighting: args.extend(["--lighting", lighting])
    if mood: args.extend(["--mood", mood])
    if camera: args.extend(["--camera", camera])
    
    if validate:
        args.append("--validate-output")
        if check_fake_text:
            args.append("--check-fake-text")
            
    if brand_kit:
        args.extend(["--brand-kit", brand_kit])
    if output:
        args.extend(["--output", output])
        
    res = run_dreamforge_cli(args)
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
) -> str:
    """
    Edit an existing image using img2img, inpaint, Flux Kontext, or Qwen Image Edit.
    input_image must be an absolute path.
    edit_type: auto | kontext | inpaint | img2img | qwen_edit
    inpaint_mask_path: absolute path to mask image when edit_type is inpaint.
    """
    args = [
        "--input-image",
        input_image,
        "--prompt",
        prompt,
        "--vram-profile",
        vram_profile,
        "--use-case",
        "image_edit",
        "--edit-type",
        edit_type,
    ]
    if model:
        args.extend(["--model", model])
    elif edit_type == "kontext":
        args.extend(["--model", "flux1-dev-kontext_fp8_scaled"])
    elif edit_type == "qwen_edit":
        args.extend(["--model", "Qwen_Image_Edit-Q5_1.gguf"])
    if inpaint_mask_path:
        args.extend(["--inpaint-mask-path", inpaint_mask_path])
    if output:
        args.extend(["--output", output])

    res = run_dreamforge_cli(args)
    return json.dumps(res, indent=2)

@mcp.tool()
def generate_arabic_poster(
    arabic_text: str,
    scene_prompt: str,
    preset: str = "balanced",
    text_position: str = "center",
    font_style: str = "default",
    image_number: int = 1,
    aspect_ratio: str = "896x1152"
) -> str:
    """
    Generate an image with perfectly composited Arabic text using the multi-pass pipeline.
    """
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
    prompt: str = ""
) -> str:
    """
    Upscale an existing image using DreamForge.
    """
    args = ["--upscale-image", image_path, "--upscale-method", method]
    if prompt:
        args.extend(["--prompt", prompt])
        
    res = run_dreamforge_cli(args)
    return json.dumps(res, indent=2)

@mcp.tool()
def dry_run(
    prompt: str,
    model: Optional[str] = None,
    use_case: str = "none",
    vram_profile: str = "16gb",
    input_image: Optional[str] = None
) -> str:
    """
    Preview generation plan without loading GPU models. Checks dependencies and resolves parameters.
    """
    args = ["--dry-run", "--prompt", prompt, "--use-case", use_case, "--vram-profile", vram_profile]
    if model:
        args.extend(["--model", model])
    if input_image:
        args.extend(["--input-image", input_image])
        
    res = run_dreamforge_cli(args)
    return json.dumps(res, indent=2)


# --- DISCOVERY & INVENTORY TOOLS ---

@mcp.tool()
def list_models() -> str:
    """Return a summary of installed models across all categories."""
    inv = list_model_inventory()
    summary = {}
    for cat, items in inv["categories"].items():
        if items:
            summary[cat] = [item["name"] for item in items]
    return json.dumps(summary, indent=2)

@mcp.tool()
def resolve_model(query: str) -> str:
    """
    Resolve a model by substring or filename and return its metadata and family.
    """
    model = resolve_generation_model(query)
    if not model:
        return json.dumps({"status": "error", "message": f"Model not found matching: {query}"})
    return json.dumps({"status": "success", "model": model}, indent=2)

@mcp.tool()
def recommend_model(vram_profile: str = "16gb", limit: int = 5) -> str:
    """
    Get ranked recommendations for generation models based on VRAM profile.
    """
    models = recommended_generation_models(profile=vram_profile)
    return json.dumps({"status": "success", "recommendations": models[:limit]}, indent=2)

@mcp.tool()
def check_dependencies(model_name: str) -> str:
    """
    Check if a modern model (Qwen, HiDream, etc) has its required companion files.
    """
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
def list_styles() -> str:
    """Return a list of available style presets."""
    inv = list_model_inventory()
    return json.dumps({"styles": inv["styles"]}, indent=2)

@mcp.tool()
def list_use_cases() -> str:
    """Return available professional recipes (use_cases)."""
    return json.dumps({"use_cases": list(USE_CASE_RECIPES.keys())}, indent=2)

@mcp.tool()
def validate_image(image_path: str, check_fake_text: bool = False) -> str:
    """
    Run standalone validation on an image (contrast, blank check, and optional fake-text detection).
    """
    if not os.path.exists(image_path):
        return json.dumps({"status": "error", "message": "Image path does not exist."})
        
    result = _validate_image(image_path, check_fake_text=check_fake_text)
    return json.dumps(result, indent=2)

if __name__ == "__main__":
    mcp.run()
