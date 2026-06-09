#!/usr/bin/env python3
"""Audit and conservatively patch ComfyUI workflow JSON for RTX 3060 12GB."""

from __future__ import annotations

import argparse
import json
import math
import os
from copy import deepcopy
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


MODEL_EXTS = {".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".gguf", ".onnx"}
MODEL_FIELD_HINTS = (
    "ckpt",
    "checkpoint",
    "lora",
    "vae",
    "clip",
    "unet",
    "diffusion_model",
    "control_net",
    "controlnet",
    "upscale_model",
    "embedding",
    "style_model",
    "gligen",
    "photomaker",
)
CORE_NODE_PREFIXES = (
    "KSampler",
    "CheckpointLoader",
    "CLIP",
    "VAE",
    "EmptyLatentImage",
    "SaveImage",
    "PreviewImage",
    "LoadImage",
    "Image",
    "Latent",
    "Conditioning",
    "ControlNet",
    "LoraLoader",
    "VAELoader",
    "UpscaleModelLoader",
    "ModelSampling",
    "BasicScheduler",
    "SamplerCustom",
    "RandomNoise",
)


@dataclass
class ModelFile:
    path: Path
    rel: str
    name: str
    stem: str
    ext: str
    kind: str


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def walk_model_files(models_root: Path) -> List[ModelFile]:
    files: List[ModelFile] = []
    if not models_root.exists():
        return files
    for root, _, names in os.walk(models_root):
        root_path = Path(root)
        for name in names:
            p = root_path / name
            if p.suffix.lower() not in MODEL_EXTS:
                continue
            rel = str(p.relative_to(models_root)).replace("\\", "/")
            kind = rel.split("/", 1)[0].lower() if "/" in rel else ""
            files.append(ModelFile(p, rel, name, p.stem.lower(), p.suffix.lower(), kind))
    return files


def custom_node_tokens(custom_nodes_root: Path) -> set[str]:
    tokens: set[str] = set()
    if not custom_nodes_root.exists():
        return tokens
    for p in custom_nodes_root.iterdir():
        if p.is_dir():
            tokens.add(normalize(p.name))
            for py in p.glob("*.py"):
                tokens.add(normalize(py.stem))
        elif p.suffix.lower() == ".py":
            tokens.add(normalize(p.stem))
    return tokens


def normalize(s: str) -> str:
    return "".join(ch.lower() for ch in s if ch.isalnum())


def iter_api_nodes(data: Any) -> Iterable[Tuple[str, Dict[str, Any], Dict[str, Any]]]:
    if not isinstance(data, dict):
        return
    for node_id, node in data.items():
        if isinstance(node, dict) and "class_type" in node:
            inputs = node.get("inputs") if isinstance(node.get("inputs"), dict) else {}
            yield str(node_id), node, inputs


def iter_ui_nodes(data: Any) -> Iterable[Tuple[str, Dict[str, Any], Dict[str, Any]]]:
    if not isinstance(data, dict) or not isinstance(data.get("nodes"), list):
        return
    for node in data["nodes"]:
        if not isinstance(node, dict):
            continue
        inputs: Dict[str, Any] = {}
        widgets = node.get("widgets_values")
        if isinstance(widgets, list):
            for idx, value in enumerate(widgets):
                inputs[f"widget_{idx}"] = value
        if isinstance(node.get("inputs"), list):
            for idx, item in enumerate(node["inputs"]):
                if isinstance(item, dict) and "name" in item and "value" in item:
                    inputs[str(item["name"])] = item["value"]
                elif isinstance(item, dict) and "widget" in item and "value" in item:
                    inputs[str(item["widget"])] = item["value"]
                else:
                    inputs[f"input_{idx}"] = item
        yield str(node.get("id", "?")), node, inputs


def workflow_nodes(data: Any) -> List[Tuple[str, Dict[str, Any], Dict[str, Any], str]]:
    nodes = [(i, n, inp, "api") for i, n, inp in iter_api_nodes(data)]
    if nodes:
        return nodes
    return [(i, n, inp, "ui") for i, n, inp in iter_ui_nodes(data)]


def class_type(node: Dict[str, Any]) -> str:
    return str(node.get("class_type") or node.get("type") or "")


def looks_like_model_field(key: str, value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    low_key = key.lower()
    low_val = value.lower()
    return any(h in low_key for h in MODEL_FIELD_HINTS) or Path(low_val).suffix in MODEL_EXTS


def field_kind(key: str) -> str:
    k = key.lower()
    if "lora" in k:
        return "loras"
    if "vae" in k:
        return "vae"
    if "control" in k:
        return "controlnet"
    if "upscale" in k:
        return "upscale_models"
    if "clip" in k:
        return "clip"
    if "unet" in k or "diffusion" in k:
        return "unet"
    if "embed" in k:
        return "embeddings"
    if "ckpt" in k or "checkpoint" in k or "model" in k:
        return "checkpoints"
    return ""


def model_exists(requested: str, models: List[ModelFile]) -> bool:
    req = requested.replace("\\", "/").lower()
    req_name = Path(req).name
    req_stem = Path(req_name).stem
    for m in models:
        if req == m.rel.lower() or req_name == m.name.lower() or req_stem == m.stem:
            return True
    return False


def best_model_candidates(requested: str, kind: str, models: List[ModelFile], limit: int = 5) -> List[Dict[str, Any]]:
    req_name = Path(requested.replace("\\", "/")).name
    req_stem = Path(req_name).stem.lower()
    req_ext = Path(req_name).suffix.lower()
    scored = []
    for m in models:
        score = SequenceMatcher(None, normalize(req_stem), normalize(m.stem)).ratio()
        if req_ext and req_ext == m.ext:
            score += 0.08
        if kind and (kind == m.kind or kind.replace("_", "") == m.kind.replace("_", "")):
            score += 0.18
        if normalize(req_stem) == normalize(m.stem):
            score += 0.35
        scored.append((score, m))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {"path": s[1].rel, "score": round(min(s[0], 1.0), 3), "kind": s[1].kind}
        for s in scored[:limit]
        if s[0] >= 0.35
    ]


def replace_value_in_node(node: Dict[str, Any], key: str, value: str, fmt: str) -> bool:
    if fmt == "api" and isinstance(node.get("inputs"), dict) and key in node["inputs"]:
        node["inputs"][key] = value
        return True
    return False


def cap_int(inputs: Dict[str, Any], key: str, maximum: int) -> Tuple[bool, Any, Any]:
    if key in inputs and isinstance(inputs[key], (int, float)) and inputs[key] > maximum:
        old = inputs[key]
        inputs[key] = maximum
        return True, old, maximum
    return False, None, None


def cap_float(inputs: Dict[str, Any], key: str, maximum: float) -> Tuple[bool, Any, Any]:
    if key in inputs and isinstance(inputs[key], (int, float)) and inputs[key] > maximum:
        old = inputs[key]
        inputs[key] = maximum
        return True, old, maximum
    return False, None, None


def shrink_dimensions(inputs: Dict[str, Any], max_pixels: int) -> List[Tuple[str, Any, Any]]:
    changes = []
    width_key = "width" if "width" in inputs else "empty_latent_width" if "empty_latent_width" in inputs else None
    height_key = "height" if "height" in inputs else "empty_latent_height" if "empty_latent_height" in inputs else None
    if not width_key or not height_key:
        return changes
    w, h = inputs.get(width_key), inputs.get(height_key)
    if not isinstance(w, (int, float)) or not isinstance(h, (int, float)) or w * h <= max_pixels:
        return changes
    ratio = math.sqrt(max_pixels / (w * h))
    new_w = max(64, int((w * ratio) // 64 * 64))
    new_h = max(64, int((h * ratio) // 64 * 64))
    inputs[width_key], inputs[height_key] = new_w, new_h
    changes.append((width_key, w, new_w))
    changes.append((height_key, h, new_h))
    return changes


def optimize_inputs(inputs: Dict[str, Any], profile: str) -> List[Dict[str, Any]]:
    changes = []
    caps = {"batch_size": 1, "batch": 1, "steps": 32, "hires_steps": 20}
    for key, maximum in caps.items():
        changed, old, new = cap_int(inputs, key, maximum)
        if changed:
            changes.append({"field": key, "from": old, "to": new})
    changed, old, new = cap_float(inputs, "cfg", 9.0)
    if changed:
        changes.append({"field": "cfg", "from": old, "to": new})
    changed, old, new = cap_float(inputs, "scale_by", 1.75)
    if changed:
        changes.append({"field": "scale_by", "from": old, "to": new})
    changed, old, new = cap_float(inputs, "upscale_by", 1.75)
    if changed:
        changes.append({"field": "upscale_by", "from": old, "to": new})
    for key, old, new in shrink_dimensions(inputs, 1024 * 1024):
        changes.append({"field": key, "from": old, "to": new})
    return changes


def is_likely_core_node(name: str) -> bool:
    return name.startswith(CORE_NODE_PREFIXES)


def node_has_local_custom_match(name: str, tokens: set[str]) -> bool:
    n = normalize(name)
    if not n:
        return False
    return any(n in t or t in n for t in tokens if len(t) >= 4)


def audit(data: Any, models_root: Path, custom_nodes_root: Path, profile: str, apply_patch: bool) -> Tuple[Any, Dict[str, Any]]:
    patched = deepcopy(data)
    models = walk_model_files(models_root)
    custom_tokens = custom_node_tokens(custom_nodes_root)
    nodes = workflow_nodes(patched)
    report: Dict[str, Any] = {
        "profile": profile,
        "models_root": str(models_root),
        "custom_nodes_root": str(custom_nodes_root),
        "local_model_count": len(models),
        "node_count": len(nodes),
        "missing_models": [],
        "model_replacements": [],
        "missing_nodes": [],
        "parameter_changes": [],
        "runnable": "likely",
    }

    for node_id, node, inputs, fmt in nodes:
        ctype = class_type(node)
        if ctype and not is_likely_core_node(ctype) and not node_has_local_custom_match(ctype, custom_tokens):
            report["missing_nodes"].append({"node_id": node_id, "class_type": ctype})

        for key, value in list(inputs.items()):
            if not looks_like_model_field(key, value):
                continue
            kind = field_kind(key)
            if model_exists(value, models):
                continue
            candidates = best_model_candidates(value, kind, models)
            item = {"node_id": node_id, "class_type": ctype, "field": key, "requested": value, "kind": kind, "candidates": candidates}
            report["missing_models"].append(item)
            if apply_patch and candidates and candidates[0]["score"] >= 0.62 and fmt == "api":
                if replace_value_in_node(node, key, candidates[0]["path"], fmt):
                    report["model_replacements"].append({"node_id": node_id, "field": key, "from": value, "to": candidates[0]["path"], "score": candidates[0]["score"]})

        changes = optimize_inputs(inputs, profile)
        for ch in changes:
            ch.update({"node_id": node_id, "class_type": ctype})
            report["parameter_changes"].append(ch)

    if report["missing_models"] or report["missing_nodes"]:
        report["runnable"] = "no"
    elif report["parameter_changes"] or report["model_replacements"]:
        report["runnable"] = "likely_after_patch"
    return patched, report


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit ComfyUI workflow JSON for local RTX 3060 12GB usage.")
    parser.add_argument("--workflow", required=True, type=Path)
    parser.add_argument("--comfy-root", type=Path, default=Path(r"D:\ComfyUI"))
    parser.add_argument("--models-root", type=Path)
    parser.add_argument("--custom-nodes-root", type=Path)
    parser.add_argument("--profile", default="rtx3060-12g", choices=["rtx3060-12g"])
    parser.add_argument("--write", type=Path, help="Write a patched workflow JSON copy.")
    parser.add_argument("--report-json", type=Path, help="Write machine-readable report JSON.")
    args = parser.parse_args()

    models_root = args.models_root or args.comfy_root / "models"
    custom_nodes_root = args.custom_nodes_root or args.comfy_root / "custom_nodes"
    data = load_json(args.workflow)
    patched, report = audit(data, models_root, custom_nodes_root, args.profile, apply_patch=bool(args.write))

    if args.write:
        save_json(args.write, patched)
        report["patched_workflow"] = str(args.write)
    if args.report_json:
        save_json(args.report_json, report)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
