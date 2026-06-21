import os
from shared import state, path_manager
import shared
from pathlib import Path
import re

def _lazy(mod):
    import importlib
    return importlib.import_module(mod)

class NoPipeLine:
    pipeline_type = []

def update(gen_data):
    prompt = gen_data["prompt"] if "prompt" in gen_data else ""
    cn_settings = _lazy("modules.controlnet").get_settings(gen_data)
    cn_type = cn_settings["type"] if "type" in cn_settings else ""

    try:
        if "task_type" in gen_data and gen_data["task_type"] == "llama":
            if (
                state["pipeline"] is None
                or "llama" not in state["pipeline"].pipeline_type
            ):
                state["pipeline"] = _lazy("modules.llama_pipeline").pipeline()

        elif prompt.lower() == "dreamforgelogo":
            if (
                state["pipeline"] is None
                or "template" not in state["pipeline"].pipeline_type
            ):
                state["pipeline"] = _lazy("modules.template_pipeline").pipeline()

        elif prompt.startswith("#!"):
            if (
                state["pipeline"] is None
                or "hashbang" not in state["pipeline"].pipeline_type
            ):
                state["pipeline"] = _lazy("modules.hashbang_pipeline").pipeline()

        elif prompt.lower().startswith("search:"):
            if (
                state["pipeline"] is None
                or "search" not in state["pipeline"].pipeline_type
            ):
                state["pipeline"] = _lazy("modules.search_pipeline").pipeline()

        elif cn_type.lower() == "upscale":
            if (
                state["pipeline"] is None
                or "upscale" not in state["pipeline"].pipeline_type
            ):
                state["pipeline"] = _lazy("modules.upscale_pipeline").pipeline()

        elif cn_type.lower() == "rembg":
            if (
                state["pipeline"] is None
                or "rembg" not in state["pipeline"].pipeline_type
            ):
                state["pipeline"] = _lazy("modules.rembg_pipeline").pipeline()

        else:
            baseModel = None
            if "base_model_name" in gen_data:
                file = shared.models.get_file("checkpoints", gen_data['base_model_name'])
                if file is None:
                    file = ""
                    baseModel = "None"
                else:
                    path = shared.models.get_models_by_path("checkpoints", file)
                    baseModel = shared.models.get_model_base(path)
                baseModelName = gen_data['base_model_name']
            if state["pipeline"] is None:
                state["pipeline"] = NoPipeLine()

            elif (
                baseModel == "Hunyuan Video" or
                Path(gen_data['base_model_name']).parts[0] == "Hunyuan Video" or
                str(Path(file).name).startswith("hunyuan-video-t2v-") or
                str(Path(file).name).startswith("fast-hunyuan-video-t2v-")
            ):
                if (
                    state["pipeline"] is None
                    or "hunyuan_video" not in state["pipeline"].pipeline_type
                ):
                    state["pipeline"] = _lazy("modules.hunyuan_video_pipeline").pipeline()

            elif (
                baseModel == "Wan Video" or
                str(Path(gen_data['base_model_name']).parts[0]).startswith("Wan Video") or
                str(Path(file).name).startswith("wan2.1-t2v-") or
                str(Path(file).name).startswith("wan2.1_t2v_") or
                str(Path(file).name).startswith("wan2.1-i2v-") or
                str(Path(file).name).startswith("wan2.1_i2v_")
            ):
                if (
                    state["pipeline"] is None
                    or "wan_video" not in state["pipeline"].pipeline_type
                ):
                    state["pipeline"] = _lazy("modules.wan_video_pipeline").pipeline()

            elif (
                baseModel == "LTXV2" or
                baseModel == "LTXV 2.3" or
                Path(gen_data['base_model_name']).parts[0] == "LTXV2" or
                Path(gen_data['base_model_name']).parts[0] == "LTXV 2.3"
            ):
                if (
                    state["pipeline"] is None
                    or "ltx2_video" not in state["pipeline"].pipeline_type
                ):
                    state["pipeline"] = _lazy("modules.ltx2_video_pipeline").pipeline()


            elif (
                baseModel == "LTXV" or
                Path(gen_data['base_model_name']).parts[0] == "LTXV"
            ):
                if (
                    state["pipeline"] is None
                    or "ltx_video" not in state["pipeline"].pipeline_type
                ):
                    state["pipeline"] = _lazy("modules.ltx_video_pipeline").pipeline()

            elif baseModel is not None:
                # Try with the sdxl/default pipeline if baseModel is set.
                if ("sdxl" not in state["pipeline"].pipeline_type):
                    state["pipeline"] = _lazy("modules.image_pipeline").pipeline()

        if state["pipeline"] is None or len(state["pipeline"].pipeline_type) == 0:
            print(f"Using default pipeline.")
            state["pipeline"] = _lazy("modules.image_pipeline").pipeline()

        return state["pipeline"]
    except Exception as e:
        # If things fail. Use the template pipeline that only returns a logo
        print(f"Something went wrong. Falling back to template pipeline.")
        print(f"Pipeline selection error: {e}")
        state["pipeline"] = _lazy("modules.template_pipeline").pipeline()
        return state["pipeline"]
