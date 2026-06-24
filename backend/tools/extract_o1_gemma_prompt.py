import json
from pathlib import Path

p = Path(__file__).resolve().parents[1].parent / "agent-tools" / "55f19d92-f061-443f-9d26-183a107619b4.txt"
if not p.exists():
    p = Path(r"C:\Users\moham\.cursor\projects\d-DreamForge\agent-tools\55f19d92-f061-443f-9d26-183a107619b4.txt")
data = json.loads(p.read_text(encoding="utf-8"))

found = None
for n in data.get("nodes", []):
    wv = n.get("widgets_values") or []
    if wv and isinstance(wv[0], str) and "Prompt Engineering Engine" in wv[0]:
        found = wv[0]
        break

if not found:
    for sg in (data.get("definitions") or {}).get("subgraphs", []):
        for n in sg.get("nodes", []):
            wv = n.get("widgets_values") or []
            if wv and isinstance(wv[0], str) and "Prompt Engineering Engine" in wv[0]:
                found = wv[0]
                break
        if found:
            break

if not found:
    raise SystemExit("system prompt not found in workflow template")

out = Path(__file__).resolve().parents[1] / "dreamforge_hidream_o1_gemma_prompt.py"
out.write_text(
    "HIDREAM_O1_GEMMA4_SYSTEM_PROMPT = "
    + repr(found)
    + "\n\n"
    + 'USER_TURN_TEMPLATE = "<|turn>user\\n{user_prompt}<|turn|>\\n<|turn>model\\n"\n\n'
    + 'DEFAULT_GEMMA4_CLIP = "gemma4_e4b_it_fp8_scaled.safetensors"\n\n\n'
    + "def build_gemma4_refine_prompt(user_prompt: str) -> str:\n"
    + '    """Format user text for Comfy TextGenerate (official HiDream O1 Dev template)."""\n'
    + "    user_turn = USER_TURN_TEMPLATE.format(user_prompt=(user_prompt or '').strip())\n"
    + "    return HIDREAM_O1_GEMMA4_SYSTEM_PROMPT + user_turn\n",
    encoding="utf-8",
)
print(f"wrote {out} ({len(found)} chars)")
