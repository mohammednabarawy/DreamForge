"""Static capability registry for known model families.

Used by the UI to display capability badges, tooltips, and guidance
so users can quickly assess whether a model is suitable for their
intended generation task.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ModelCapability:
    """Describes what a model family is good (and bad) at."""
    family: str
    display_name: str
    strengths: tuple[str, ...]
    limitations: tuple[str, ...]
    best_for: str
    tips: str
    nsfw_level: str  # "explicit", "soft", "none"
    badges: tuple[str, ...]  # emoji + label pairs for UI
    speed_tier: str  # "fast", "medium", "slow"
    lora_ecosystem: str  # "rich", "growing", "limited", "none"


CAPABILITIES: dict[str, ModelCapability] = {
    "krea2": ModelCapability(
        family="krea2",
        display_name="Krea 2 Turbo",
        strengths=("photorealism", "lighting", "composition", "identity_edit", "speed"),
        limitations=("explicit_anatomy", "text_rendering", "lora_ecosystem"),
        best_for="Photorealistic portraits, identity-preserving edits, architectural scenes, product photography",
        tips=(
            "Use descriptive photographic prose, not tag spam. "
            "For explicit content, switch to Flux Dev + dedicated LoRAs. "
            "Identity Edit mode preserves faces while changing everything else."
        ),
        nsfw_level="soft",
        badges=("📸 Photo", "✏️ Edit", "⚡ Fast"),
        speed_tier="fast",
        lora_ecosystem="limited",
    ),
    "flux": ModelCapability(
        family="flux",
        display_name="Flux Dev",
        strengths=("versatility", "prompt_adherence", "lora_ecosystem", "explicit_anatomy", "text_rendering"),
        limitations=("speed", "vram_usage"),
        best_for="General purpose, LoRA-heavy workflows, text in images, explicit content with dedicated LoRAs",
        tips=(
            "Best LoRA ecosystem. Use Flux Dev for quality, Schnell for speed. "
            "Kontext mode for identity-preserving edits. "
            "Pair with NSFW LoRAs for explicit content."
        ),
        nsfw_level="explicit",
        badges=("📸 Photo", "🎨 Art", "🧩 LoRA", "🔞 Explicit"),
        speed_tier="medium",
        lora_ecosystem="rich",
    ),
    "flux_kontext": ModelCapability(
        family="flux_kontext",
        display_name="Flux Kontext",
        strengths=("identity_edit", "prompt_adherence", "consistency"),
        limitations=("speed", "vram_usage"),
        best_for="Identity-preserving edits, character consistency, scene changes while keeping the same person",
        tips=(
            "Best for changing scenes/outfits while preserving a person's face. "
            "Works with Flux LoRAs. Denoise controls how much changes."
        ),
        nsfw_level="explicit",
        badges=("✏️ Edit", "👤 Identity", "🧩 LoRA"),
        speed_tier="medium",
        lora_ecosystem="rich",
    ),
    "sdxl": ModelCapability(
        family="sdxl",
        display_name="SDXL",
        strengths=("lora_ecosystem", "controlnet", "explicit_anatomy", "speed", "community"),
        limitations=("natural_language_understanding", "text_rendering"),
        best_for="Mature LoRA ecosystem, ControlNet workflows, anime/stylized art, explicit content",
        tips=(
            "Largest LoRA and ControlNet ecosystem. Best with tag-style prompts. "
            "Use dedicated NSFW checkpoints for explicit content. "
            "ControlNet support is strongest here."
        ),
        nsfw_level="explicit",
        badges=("🎨 Art", "🧩 LoRA", "🔞 Explicit", "⚡ Fast"),
        speed_tier="fast",
        lora_ecosystem="rich",
    ),
    "sd15": ModelCapability(
        family="sd15",
        display_name="SD 1.5",
        strengths=("speed", "low_vram", "lora_ecosystem", "controlnet"),
        limitations=("resolution", "detail", "natural_language_understanding"),
        best_for="Low-VRAM systems, fast iteration, legacy LoRA collections",
        tips=(
            "Best at 512x512. Very fast but lower quality than modern models. "
            "Huge legacy LoRA library. Use for quick tests before upscaling."
        ),
        nsfw_level="explicit",
        badges=("⚡ Fast", "🧩 LoRA", "💾 Low VRAM"),
        speed_tier="fast",
        lora_ecosystem="rich",
    ),
    "qwen_image": ModelCapability(
        family="qwen_image",
        display_name="Qwen Image",
        strengths=("text_rendering", "multilingual", "understanding"),
        limitations=("explicit_anatomy", "speed"),
        best_for="Text-heavy images, multilingual prompts, design mockups",
        tips=(
            "Best text rendering of any model. Understands Chinese, Arabic, and other scripts. "
            "Not suited for explicit content."
        ),
        nsfw_level="soft",
        badges=("📝 Text", "🌍 Multilingual"),
        speed_tier="medium",
        lora_ecosystem="growing",
    ),
    "qwen_image_edit": ModelCapability(
        family="qwen_image_edit",
        display_name="Qwen Image Edit",
        strengths=("precision_edit", "text_rendering", "instruction_following"),
        limitations=("explicit_anatomy", "speed"),
        best_for="Precise instruction-based edits, text changes, localized modifications",
        tips=(
            "Give clear editing instructions rather than full scene descriptions. "
            "Lightning variant available for faster edits."
        ),
        nsfw_level="soft",
        badges=("✏️ Edit", "📝 Text", "🎯 Precise"),
        speed_tier="medium",
        lora_ecosystem="limited",
    ),
    "hidream_o1": ModelCapability(
        family="hidream_o1",
        display_name="HiDream o1",
        strengths=("artistic_quality", "composition", "lighting"),
        limitations=("speed", "vram_usage", "lora_ecosystem"),
        best_for="Artistic compositions, cinematic scenes, creative explorations",
        tips=(
            "Produces highly artistic results with expressive lighting. "
            "Slower than Flux/Krea but higher artistic quality. "
            "Limited LoRA support."
        ),
        nsfw_level="soft",
        badges=("🎨 Art", "🎬 Cinematic"),
        speed_tier="slow",
        lora_ecosystem="limited",
    ),
    "z_image": ModelCapability(
        family="z_image",
        display_name="Z-Image Turbo",
        strengths=("speed", "photorealism"),
        limitations=("lora_ecosystem", "explicit_anatomy"),
        best_for="Fast photorealistic generation, real-time previews",
        tips=(
            "Very fast turbo model. Good for quick iterations. "
            "Limited LoRA ecosystem."
        ),
        nsfw_level="soft",
        badges=("📸 Photo", "⚡ Fast"),
        speed_tier="fast",
        lora_ecosystem="limited",
    ),
    "ideogram4": ModelCapability(
        family="ideogram4",
        display_name="Ideogram 4",
        strengths=("text_rendering", "typography", "design", "prompt_adherence"),
        limitations=("explicit_anatomy", "lora_ecosystem", "vram_usage"),
        best_for="Text-heavy images, logos, posters, design work, typography",
        tips=(
            "Best-in-class text rendering and typography. "
            "Use for logos, posters, and any image where text accuracy matters. "
            "High VRAM usage."
        ),
        nsfw_level="none",
        badges=("📝 Text", "🎨 Design", "🔤 Typography"),
        speed_tier="medium",
        lora_ecosystem="none",
    ),
    "sd3": ModelCapability(
        family="sd3",
        display_name="SD 3.x",
        strengths=("prompt_adherence", "composition"),
        limitations=("lora_ecosystem", "community"),
        best_for="Balanced quality and prompt adherence",
        tips="Limited ecosystem. Consider Flux or SDXL for broader LoRA support.",
        nsfw_level="soft",
        badges=("📸 Photo", "🎨 Art"),
        speed_tier="medium",
        lora_ecosystem="limited",
    ),
    "flux2": ModelCapability(
        family="flux2",
        display_name="Flux 2 Klein",
        strengths=("speed", "quality", "efficiency"),
        limitations=("lora_ecosystem"),
        best_for="Fast high-quality generation with lower VRAM than Flux Dev",
        tips="Compact and fast. Consistency LoRA available for character consistency.",
        nsfw_level="explicit",
        badges=("📸 Photo", "⚡ Fast", "💾 Low VRAM"),
        speed_tier="fast",
        lora_ecosystem="growing",
    ),
}


def get_capabilities(family: str) -> ModelCapability | None:
    """Get capability info for a model family."""
    return CAPABILITIES.get((family or "").lower())


def get_all_capabilities() -> dict[str, dict[str, Any]]:
    """Return all capabilities as serializable dicts for the frontend."""
    return {
        fam: {
            "family": cap.family,
            "display_name": cap.display_name,
            "strengths": list(cap.strengths),
            "limitations": list(cap.limitations) if isinstance(cap.limitations, tuple) else [cap.limitations],
            "best_for": cap.best_for,
            "tips": cap.tips,
            "nsfw_level": cap.nsfw_level,
            "badges": list(cap.badges),
            "speed_tier": cap.speed_tier,
            "lora_ecosystem": cap.lora_ecosystem,
        }
        for fam, cap in CAPABILITIES.items()
    }
