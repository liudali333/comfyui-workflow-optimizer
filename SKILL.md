---
name: comfyui-workflow-optimizer
description: Optimize and repair ComfyUI workflow JSON for a local RTX 3060 12GB setup. Use when Codex works with ComfyUI .json workflows, needs to reduce VRAM-heavy parameters, prefer equivalent local models under D:\ComfyUI\models, find missing checkpoint/LoRA/VAE/ControlNet/upscaler files, identify likely missing custom nodes under D:\ComfyUI\custom_nodes, or produce a runnable patched workflow.
---

# ComfyUI Workflow Optimizer

## Quick Start

Use this skill for ComfyUI workflow JSON tasks, especially workflows downloaded from the internet or hand-written workflows that must run on an RTX 3060 12GB card.

Default local paths:

- ComfyUI root: `D:\ComfyUI`
- Models root: `D:\ComfyUI\models`
- Custom nodes root: `D:\ComfyUI\custom_nodes`

When given a workflow file, first run:

```powershell
python C:\Users\Administrator\.codex\skills\comfyui-workflow-optimizer\scripts\workflow_audit.py --workflow <workflow.json> --comfy-root D:\ComfyUI --models-root D:\ComfyUI\models --custom-nodes-root D:\ComfyUI\custom_nodes --profile rtx3060-12g
```

For a patched copy with conservative 3060 12GB settings and local model substitutions:

```powershell
python C:\Users\Administrator\.codex\skills\comfyui-workflow-optimizer\scripts\workflow_audit.py --workflow <workflow.json> --comfy-root D:\ComfyUI --models-root D:\ComfyUI\models --custom-nodes-root D:\ComfyUI\custom_nodes --profile rtx3060-12g --write <workflow.3060-12g.json>
```

If sandbox restrictions block reading `D:\ComfyUI`, request approval and rerun the same command.

## Workflow

1. Parse the JSON as either ComfyUI API format (`{"1": {"class_type": ...}}`) or UI graph format (`nodes`, `links`).
2. Run the audit script before manual edits. Use the script output to separate hard blockers from optimization suggestions.
3. Treat missing models as blockers unless the script finds a strong local substitute. Prefer same model family and file type before looser similarity matches.
4. Treat missing custom nodes as blockers when a node class is not from ComfyUI core and no matching local custom node folder or Python file is found.
5. Patch a copy of the workflow, never overwrite the user's original unless explicitly asked.
6. Keep generation quality reasonable while protecting 12GB VRAM: batch size 1, SDXL near 1024x1024, SD1.5 near 768x768 or lower, avoid aggressive hires/upscale passes unless tiled or staged.

## 3060 12GB Defaults

Use these as conservative maximums unless the user asks for speed/quality tradeoffs:

- `batch_size`: 1
- `steps`: 20-30, cap at 32
- `cfg`: SDXL 4.5-7.5, SD1.5 5-8, cap at 9
- SDXL latent size: up to 1024x1024 or similar pixel count
- SD1.5 latent size: up to 768x768 or similar pixel count
- hires/upscale: keep first pass modest; prefer tiled VAE/upscale nodes if present
- samplers: prefer stable common samplers such as `dpmpp_2m`, `dpmpp_2m_sde`, `euler`, or workflow-provided values if already reasonable
- precision: mention using `--lowvram` only as a fallback; prefer model/size/batch fixes first

## Model Replacement

When replacing a missing model:

- Prefer exact basename match ignoring extension and case.
- Prefer same subfolder type: checkpoints with checkpoints, LoRAs with loras, VAE with vae, ControlNet with controlnet, upscale models with upscale_models.
- If exact match is unavailable, use the highest similarity local file and state confidence.
- Do not silently replace an obviously different family, such as SDXL checkpoint with SD1.5 checkpoint, unless no better candidate exists and the user accepts risk.
- Preserve the original workflow file and write a new patched JSON.

See `references/model-fields.md` for common ComfyUI input names that usually contain model filenames.

## Output Style

Report in Chinese by default for this user. Include these sections:

- Runnable status: yes/no/likely, with blockers.
- Missing models: original requested filename, local substitute if any.
- Missing nodes: node class and likely custom node package if guessable.
- RTX 3060 12G optimization: exact changed parameters.
- Output file: patched JSON path when written.
