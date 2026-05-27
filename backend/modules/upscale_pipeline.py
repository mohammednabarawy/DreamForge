import os
import traceback
import numpy as np
import torch
import modules.async_worker as worker
import modules.controlnet
from shared import path_manager
import comfy.utils
from comfy_extras.chainner_models import model_loading
from comfy_extras.nodes_upscale_model import ImageUpscaleWithModel
from PIL import Image
Image.MAX_IMAGE_PIXELS = None

class pipeline:
    pipeline_type = ["template"]
    model_hash = ""

    def parse_gen_data(self, gen_data):
        gen_data["original_image_number"] = gen_data["image_number"]
        gen_data["image_number"] = 1
        gen_data["show_preview"] = False
        return gen_data

    def load_upscaler_model(self, model_path):
        model_path = str(model_path)
        sd = comfy.utils.load_torch_file(model_path, safe_load=True)
        if "module.layers.0.residual_group.blocks.0.norm1.weight" in sd:
            sd = comfy.utils.state_dict_prefix_replace(sd, {"module.": ""})
        out = model_loading.load_state_dict(sd).eval()
        return out

    def _resolve_upscale_path(self, gen_data):
        cn_settings = modules.controlnet.get_settings(gen_data)
        upscaler_key = cn_settings.get("upscaler") or "fast_2x"
        try:
            from dreamforge_krita_resources import resolve_upscaler, upscaler_path

            info = resolve_upscaler(upscaler_key)
            resolved = upscaler_path(upscaler_key)
            if resolved is not None:
                return resolved, info.get("label", info.get("filename", upscaler_key))
        except ImportError:
            info = {"filename": upscaler_key, "label": upscaler_key}

        upscale_path = path_manager.get_file_path(upscaler_key)
        if upscale_path is None:
            upscale_path = path_manager.get_file_path(info.get("filename", upscaler_key))
        if upscale_path is None:
            upscale_path = path_manager.get_file_path("4x-UltraSharp.pth")
        return upscale_path, info.get("label", str(upscaler_key))

    def load_base_model(self, name, hash=None):
        if self.model_hash == name:
            return
        print(f"Loading model: {name}")
        self.model_hash = name
        return

    def load_keywords(self, lora):
        filename = lora.replace(".safetensors", ".txt")
        try:
            with open(filename, "r") as file:
                data = file.read()
            return data
        except FileNotFoundError:
            return " "

    def load_loras(self, loras):
        return

    def refresh_controlnet(self, name=None):
        return

    def clean_prompt_cond_caches(self):
        return

    def process(
        self,
        gen_data=None,
        callback=None,
    ):
        input_image = gen_data["input_image"]
        input_image = input_image.convert("RGB")
        input_image = np.array(input_image).astype(np.float32) / 255.0
        input_image = torch.from_numpy(input_image)[None,]

        worker.add_result(
            gen_data["task_id"],
            "preview",
            (-1, f"Load upscaling model ...", None)
        )

        upscale_path, upscaler_label = self._resolve_upscale_path(gen_data)
        if upscale_path is None:
            worker.add_result(
                gen_data["task_id"],
                "preview",
                (-1, f"Upscaler model missing ...", "html/error.png")
            )
            return []

        upscaler_model = self.load_upscaler_model(upscale_path)

        worker.add_result(
            gen_data["task_id"],
            "preview",
            (-1, f"Upscaling with {upscaler_label} ...", None)
        )

        try:
            decoded_latent = ImageUpscaleWithModel().upscale(
                upscaler_model, input_image
            )[0]

            worker.add_result(
                gen_data["task_id"],
                "preview",
                (-1, f"Converting ...", None)
            )
            images = [
                np.clip(255.0 * y.cpu().numpy(), 0, 255).astype(np.uint8)
                for y in decoded_latent
            ]
            worker.add_result(
                gen_data["task_id"],
                "preview",
                (-1, f"Done ...", None)
            )
        except Exception:
            traceback.print_exc()
            worker.add_result(
                gen_data["task_id"],
                "preview",
                (-1, f"Oops ...", "html/error.png")
            )
            images = []

        return images
