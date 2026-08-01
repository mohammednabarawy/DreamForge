"""DreamForgeRecipe v2 — normalized generation configuration.

A recipe is the single convergence point for every generation configuration
(plan §31.19): community metadata, styles, creative templates, and local
exports all normalize into a ``DreamForgeRecipe``.

Rules enforced here (plan §5, §20):
- Missing values stay missing — recreation must never invent a model, seed,
  sampler, or CFG.
- A completeness score reports how much of the recipe is populated.
- Provenance/licensing is retained and never inferred from an absent field.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

from dreamforge_assets import Provenance

RECIPE_SCHEMA_VERSION = "2.0"

# Fields considered "known" for completeness scoring. Models/settings always
# count; seeds are optional by design (seed None → random).
_COMPLETE_FIELDS: tuple[str, ...] = (
    "model",
    "positive_prompt",
    "sampler",
    "cfg_scale",
    "steps",
    "aspect_ratio",
)

_SAMPLERS: tuple[str, ...] = (
    "euler",
    "euler_ancestral",
    "dpmpp_2m",
    "dpmpp_2m_sde",
    "dpmpp_3m_sde",
    "dpmpp_sde",
    "dpm_2",
    "dpm_2_ancestral",
    "uni_pc",
    "ddim",
    "lcm",
    "simple",
)


_SAMPLER_ALIASES: dict[str, str] = {
    "euler_a": "euler_ancestral",
    "dpm++_2m_sde": "dpmpp_2m_sde",
    "dpmpp_2m_sde": "dpmpp_2m_sde",
    "dpm++_sde": "dpmpp_sde",
    "dpmpp_sde": "dpmpp_sde",
    "dpm++_2m": "dpmpp_2m",
    "dpmpp_2m": "dpmpp_2m",
    "dpm++_3m_sde": "dpmpp_3m_sde",
    "dpmpp_3m_sde": "dpmpp_3m_sde",
    "uni_pc": "uni_pc",
    "unipc": "uni_pc",
    "ddim": "ddim",
    "euler": "euler",
    "euler_ancestral": "euler_ancestral",
    "lcm": "lcm",
    "simple": "simple",
    "dpm_2": "dpm_2",
    "dpm_2_ancestral": "dpm_2_ancestral",
}


def normalize_sampler(value: str | None) -> str | None:
    if not value:
        return None
    key = str(value).strip().lower()
    key = key.replace("++", "pp").replace("+", "pp")
    key = key.replace(" ", "_").replace("-", "_")
    if key.startswith("euler_a"):
        return "euler_ancestral"
    if key in _SAMPLER_ALIASES:
        return _SAMPLER_ALIASES[key]
    for sampler in sorted(_SAMPLERS, key=len, reverse=True):
        if key.startswith(sampler):
            return sampler
    return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class LoRAComponent:
    filename: str
    weight: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {"filename": self.filename, "weight": self.weight}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "LoRAComponent":
        data = data or {}
        return cls(
            filename=str(data.get("filename") or ""),
            weight=float(1.0 if data.get("weight") is None else data.get("weight")),
        )


@dataclass
class DreamForgeRecipe:
    model: str = ""
    positive_prompt: str = ""
    negative_prompt: str = ""
    seed: int | None = None
    sampler: str = ""
    cfg_scale: float = 0.0
    steps: int = 0
    aspect_ratio: str = ""
    performance: str = ""
    styles: list[str] = field(default_factory=list)
    loras: list[LoRAComponent] = field(default_factory=list)
    settings: dict[str, Any] = field(default_factory=dict)
    source: str = ""  # e.g. "civitai_image", "lexica", "local_export", "style"
    source_url: str = ""
    provenance: Provenance = field(default_factory=Provenance.local)
    created_at: str = field(default_factory=_now_iso)
    schema_version: str = RECIPE_SCHEMA_VERSION

    # -- normalization ---------------------------------------------------------

    def __post_init__(self) -> None:
        self.sampler = normalize_sampler(self.sampler) or ""
        self.positive_prompt = (self.positive_prompt or "").strip()
        self.negative_prompt = (self.negative_prompt or "").strip()
        self.styles = [s for s in (self.styles or []) if s]
        if isinstance(self.loras, list):
            self.loras = [
                item if isinstance(item, LoRAComponent) else LoRAComponent.from_dict(item)
                for item in self.loras
            ]

    # -- completeness ----------------------------------------------------------

    def completeness(self) -> dict[str, Any]:
        """Score how complete the recipe is (0..1) and what is missing."""
        present: list[str] = []
        missing: list[str] = []
        if self.model:
            present.append("model")
        else:
            missing.append("model")
        if self.positive_prompt:
            present.append("positive_prompt")
        else:
            missing.append("positive_prompt")
        if self.sampler:
            present.append("sampler")
        else:
            missing.append("sampler")
        if self.cfg_scale and self.cfg_scale > 0:
            present.append("cfg_scale")
        else:
            missing.append("cfg_scale")
        if self.steps and self.steps > 0:
            present.append("steps")
        else:
            missing.append("steps")
        if self.aspect_ratio:
            present.append("aspect_ratio")
        else:
            missing.append("aspect_ratio")
        # Seed and negative are optional (never invented), but recorded if known.
        if self.seed is not None:
            present.append("seed")
        if self.negative_prompt:
            present.append("negative_prompt")
        score = len([field for field in present if field in _COMPLETE_FIELDS]) / len(_COMPLETE_FIELDS) if _COMPLETE_FIELDS else 0.0
        return {
            "score": round(score, 3),
            "present": present,
            "missing": missing,
            "note": "Missing values are never invented.",
        }

    @property
    def is_runnable(self) -> bool:
        return bool(self.model and self.positive_prompt)

    # -- serialization ---------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "model": self.model,
            "positive_prompt": self.positive_prompt,
            "negative_prompt": self.negative_prompt,
            "seed": self.seed,
            "sampler": self.sampler,
            "cfg_scale": self.cfg_scale,
            "steps": self.steps,
            "aspect_ratio": self.aspect_ratio,
            "performance": self.performance,
            "styles": list(self.styles),
            "loras": [l.to_dict() for l in self.loras],
            "settings": copy.deepcopy(self.settings),
            "source": self.source,
            "source_url": self.source_url,
            "provenance": self.provenance.to_dict(),
            "created_at": self.created_at,
            "completeness": self.completeness(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "DreamForgeRecipe":
        data = data or {}
        recipe = cls(
            model=str(data.get("model") or ""),
            positive_prompt=str(data.get("positive_prompt") or ""),
            negative_prompt=str(data.get("negative_prompt") or ""),
            sampler=str(data.get("sampler") or ""),
            cfg_scale=float(data.get("cfg_scale") or 0.0),
            steps=int(data.get("steps") or 0),
            aspect_ratio=str(data.get("aspect_ratio") or ""),
            performance=str(data.get("performance") or ""),
            styles=[str(s) for s in (data.get("styles") or []) if s is not None and str(s).strip()],
            loras=[LoRAComponent.from_dict(l) for l in (data.get("loras") or [])],
            settings=copy.deepcopy(dict(data.get("settings") or {})),
            source=str(data.get("source") or ""),
            source_url=str(data.get("source_url") or ""),
            provenance=Provenance.from_dict(data.get("provenance")),
            created_at=str(data.get("created_at") or _now_iso()),
            schema_version=str(data.get("schema_version") or RECIPE_SCHEMA_VERSION),
        )
        seed_raw = data.get("seed")
        if seed_raw not in (None, "", "None"):
            try:
                recipe.seed = int(seed_raw)
            except (TypeError, ValueError):
                recipe.seed = None
        return recipe

    # -- builders --------------------------------------------------------------

    @classmethod
    def from_style_recipe(
        cls,
        recipe_id: str,
        style_recipe: Mapping[str, Any],
        *,
        prompt: str = "",
    ) -> "DreamForgeRecipe":
        """Build a recipe from the existing ``STYLE_RECIPES`` shape."""
        data = dict(style_recipe or {})
        models = data.get("models") or []
        model = str(models[0]) if models else ""
        positive = str(data.get("prompt_prefix") or "") + prompt
        positive = positive.strip()
        recipe = cls(
            model=model,
            positive_prompt=positive,
            performance=str(data.get("performance") or ""),
            aspect_ratio=str(data.get("aspect_ratio") or ""),
            styles=[str(s) for s in (data.get("styles") or [])],
            settings={
                k: v for k, v in data.items() if k not in
                ("models", "prompt_prefix", "performance", "aspect_ratio", "styles", "thumbnail", "notes", "seed")
            },
            source="style",
            provenance=Provenance(provider="local", source_url=f"style://{recipe_id}"),
        )
        return recipe
