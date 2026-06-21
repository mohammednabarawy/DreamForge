"""Legacy RuinedFooocus prompt processors (``modules.prompt_processing``)."""

from __future__ import annotations

from typing import Any

from dreamforge_prompt.context import backend_working_directory


def process_prompt_with_legacy_modules(
    styles: list[str],
    prompt: str,
    negative: str,
    gen_data: dict[str, Any],
):
    with backend_working_directory():
        from modules.prompt_processing import parse_loras, process_prompt

        positive, negative_out = process_prompt(styles, prompt, negative, gen_data)
        parsed_loras, positive, negative_out = parse_loras(positive, negative_out)
    return positive, negative_out, parsed_loras
