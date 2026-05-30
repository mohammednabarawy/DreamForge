from __future__ import annotations

import json
import os
import sys
import threading
import traceback
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
from pathlib import Path

from _paths import BACKEND_ROOT, PROJECT_ROOT, extend_sys_path
extend_sys_path()

import dreamforge_output_index
import dreamforge_generation
from dreamforge_brain import plan_user_intent
from dreamforge_cli_inventory import list_model_inventory

_GPU_LOCK = threading.Lock()

class DreamForgeEngine:
    """
    Unified facade core for DreamForge AI Operating System.
    Ensures that all client entry points (CLI, REST, MCP, Desktop Bridge)
    call the same normalized, single-flight GPU execution interface.
    """

    @staticmethod
    def _to_namespace(params: dict) -> SimpleNamespace:
        mapping = {
            "model": "model",
            "base_model": "model",
            "prompt": "prompt",
            "negative_prompt": "negative_prompt",
            "aspect_ratio": "aspect_ratio",
            "width": "width",
            "height": "height",
            "seed": "seed",
            "image_number": "image_number",
            "output": "output",
            "performance": "performance",
            "steps": "steps",
            "cfg_scale": "cfg_scale",
            "sampler": "sampler",
            "scheduler": "scheduler",
            "styles": "styles",
            "lora": "lora",
            "input_image": "input_image",
            "reference_images": "reference_images",
            "control_images": "control_images",
            "upscale_image": "upscale_image",
            "upscale_method": "upscale_method",
            "edit_type": "edit_type",
            "edit_strength": "edit_strength",
            "use_comfy_server": "use_comfy_server",
            "inpaint_mask_path": "inpaint_mask_path",
            "cn_selection": "cn_selection",
            "cn_type": "cn_type",
            "controlnet_model": "controlnet_model",
            "cn_strength": "cn_strength",
            "cn_start": "cn_start",
            "cn_stop": "cn_stop",
            "outpaint_left": "outpaint_left",
            "outpaint_top": "outpaint_top",
            "outpaint_right": "outpaint_right",
            "outpaint_bottom": "outpaint_bottom",
            "outpaint_amount": "outpaint_amount",
            "outpaint_direction": "outpaint_direction",
            "outpaint_feathering": "outpaint_feathering",
            "hires": "hires",
            "hires_first_pass_scale": "hires_first_pass_scale",
            "hires_first_width": "hires_first_width",
            "hires_first_height": "hires_first_height",
            "hires_first_steps": "hires_first_steps",
            "hires_second_steps": "hires_second_steps",
            "hires_denoise": "hires_denoise",
            "hires_latent_upscale_method": "hires_latent_upscale_method",
            "reference_mode": "reference_mode",
            "ipadapter_model": "ipadapter_model",
            "clip_vision_model": "clip_vision_model",
            "reference_weight": "reference_weight",
            "region_prompt": "region_prompt",
            "region_prompts": "region_prompts",
            "region_prompts_json": "region_prompts_json",
            "composition_regions": "composition_regions",
            "vram_profile": "vram_profile",
            "use_case": "use_case",
            "brand_kit": "brand_kit",
            "subject": "subject",
            "composition": "composition",
            "lighting": "lighting",
            "camera": "camera",
            "brand_colors": "brand_colors",
            "materials": "materials",
            "visual_style": "visual_style",
            "validate_output": "validate_output",
            "no_manifest": "no_manifest",
            "workflow_mode": "workflow_mode",
            "arabic_text": "arabic_text",
            "execute_workflow_plan": "execute_workflow_plan",
            "workflow_plan": "workflow_plan",
            "detail_target": "detail_target",
            "detail_prompt": "detail_prompt",
        }
        # Populate with standard CLI defaults to keep hasattr behavior identical
        data = {
            "model": None,
            "prompt": "",
            "negative_prompt": "",
            "aspect_ratio": None,
            "width": None,
            "height": None,
            "seed": -1,
            "image_number": 1,
            "output": None,
            "performance": "Speed",
            "steps": None,
            "cfg_scale": None,
            "sampler": None,
            "scheduler": None,
            "styles": None,
            "lora": [],
            "input_image": None,
            "reference_images": None,
            "control_images": None,
            "comfy_workflow_api": None,
            "use_comfy_server": False,
            "upscale_image": None,
            "upscale_method": "2x",
            "edit_type": "auto",
            "edit_strength": None,
            "inpaint_mask_path": None,
            "cn_selection": "None",
            "cn_type": "None",
            "controlnet_model": None,
            "cn_strength": None,
            "cn_start": None,
            "cn_stop": None,
            "outpaint_left": 0,
            "outpaint_top": 0,
            "outpaint_right": 0,
            "outpaint_bottom": 0,
            "outpaint_amount": 256,
            "outpaint_direction": "",
            "outpaint_feathering": 40,
            "hires": False,
            "hires_first_pass_scale": 0.5,
            "hires_first_width": None,
            "hires_first_height": None,
            "hires_first_steps": None,
            "hires_second_steps": None,
            "hires_denoise": 0.35,
            "hires_latent_upscale_method": "bislerp",
            "reference_mode": "",
            "ipadapter_model": None,
            "clip_vision_model": None,
            "reference_weight": 0.65,
            "region_prompt": [],
            "region_prompts": None,
            "region_prompts_json": None,
            "composition_regions": None,
            "vram_profile": "auto",
            "stream_file": None,
            "dry_run": False,
            "brain_plan": False,
            "brain_provider": "auto",
            "brain_base_url": "",
            "brain_model": "",
            "brain_api_key": "",
            "workflow_mode": None,
            "arabic_text": None,
            "execute_workflow_plan": False,
            "workflow_plan": None,
            "detail_target": None,
            "detail_prompt": None,
            "use_case": "none",
            "json": True,
        }
        for key, attr in mapping.items():
            if key in params and params[key] is not None:
                data[attr] = params[key]
        return SimpleNamespace(**data)

    @classmethod
    def execute_job(cls, params: dict, *, stream_sink=None, job_id: Optional[str] = None) -> dict:
        """
        Normalized execution with a single-flight GPU lock to avoid concurrency conflicts.
        """
        base_args = cls._to_namespace(params)
        
        # Enforce single-flight GPU generation execution
        print(f"[DreamForge Engine] Acquiring GPU execution lock...", file=sys.stderr)
        with _GPU_LOCK:
            print(f"[DreamForge Engine] GPU lock acquired. Executing job.", file=sys.stderr)
            try:
                result = dreamforge_generation.run_generation(base_args, params, stream_sink=stream_sink, job_id=job_id)
                if result.get("status") == "success":
                    try:
                        from dreamforge_user_style_profile import record_successful_job

                        record_successful_job(params, result)
                    except Exception:
                        pass
                return result
            except Exception as e:
                print(f"[DreamForge Engine Error] Execution failed: {e}", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
                return {
                    "status": "error",
                    "message": f"Execution failed: {e}",
                    "traceback": traceback.format_exc()
                }

    @classmethod
    def generate(cls, prompt: str, **kwargs) -> dict:
        """Text-to-image generation."""
        params = {"prompt": prompt, "use_case": "none", **kwargs}
        return cls.execute_job(params)

    @classmethod
    def edit(cls, input_image: str, prompt: str, **kwargs) -> dict:
        """Global edits, style transfer, or object swap."""
        params = {
            "input_image": input_image,
            "prompt": prompt,
            "use_case": "image_edit",
            "edit_type": kwargs.get("edit_type", "auto"),
            "use_comfy_server": True,
            **kwargs
        }
        return cls.execute_job(params)

    @classmethod
    def inpaint(cls, input_image: str, mask_image: str, prompt: str, **kwargs) -> dict:
        """Targeted region masked editing."""
        params = {
            "input_image": input_image,
            "inpaint_mask_path": mask_image,
            "prompt": prompt,
            "use_case": "image_edit",
            "edit_type": "inpaint",
            "use_comfy_server": True,
            **kwargs
        }
        return cls.execute_job(params)

    @classmethod
    def upscale(cls, image_path: str, **kwargs) -> dict:
        """Resolution upscaling."""
        params = {
            "upscale_image": image_path,
            "use_case": "image_edit",
            "cn_type": "upscale",
            "use_comfy_server": True,
            **kwargs
        }
        return cls.execute_job(params)

    @staticmethod
    def plan(instruction: str, **kwargs) -> dict:
        """Classify and orchestrate agent workflow plan."""
        current_settings = kwargs.get("current_settings") if isinstance(kwargs.get("current_settings"), dict) else kwargs
        return plan_user_intent(
            instruction,
            current_settings=current_settings,
            selected_image=str(kwargs.get("selected_image") or kwargs.get("input_image") or ""),
            gallery=kwargs.get("gallery") if isinstance(kwargs.get("gallery"), list) else [],
            provider_id=str(kwargs.get("brain_provider") or "auto"),
            base_url=str(kwargs.get("brain_base_url") or ""),
            model=str(kwargs.get("brain_model") or ""),
            api_key=str(kwargs.get("brain_api_key") or ""),
        )

    @staticmethod
    def list_models() -> dict:
        """Normalized catalog of available checkpoints, LORAs, etc."""
        inv = list_model_inventory()
        categories = inv.get("categories", {})
        summary = {}
        for cat, items in categories.items():
            if items:
                summary[cat] = [
                    {
                        "name": item.get("name"),
                        "relative_path": item.get("relative_path"),
                        "family": item.get("family", "unknown")
                    }
                    for item in items
                ]
        return summary

    @staticmethod
    def list_outputs(limit: int = 40, offset: int = 0, **kwargs) -> dict:
        """Normalized listing of project history and gallery manifests."""
        since = kwargs.get("since")
        model = kwargs.get("model")
        use_case = kwargs.get("use_case")
        
        items, total = dreamforge_output_index.list_outputs(
            since=since, model=model, use_case=use_case, limit=limit, offset=offset
        )
        return {
            "projects": items,
            "total": total,
            "limit": limit,
            "offset": offset
        }

    @classmethod
    def analyze_project(cls) -> dict:
        """Summarize and critique folder structure, output history, and inventory availability."""
        models_inv = cls.list_models()
        outputs_list = cls.list_outputs(limit=10)
        
        return {
            "project_root": str(PROJECT_ROOT),
            "total_generations": outputs_list.get("total", 0),
            "installed_models_summary": {cat: len(items) for cat, items in models_inv.items()},
            "recent_generations": [
                {
                    "prompt": item.get("prompt"),
                    "model": item.get("model"),
                    "timestamp": item.get("timestamp"),
                    "image": item.get("image")
                }
                for item in outputs_list.get("projects", [])
            ]
        }

    @classmethod
    def dry_run(cls, params: dict) -> dict:
        """Preview generation plan without loading GPU models. Resolves parameters and checks dependencies."""
        from dreamforge_cli_direct import build_plan
        base_args = cls._to_namespace(params)
        base_args.dry_run = True
        return build_plan(base_args, params)
