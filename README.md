# ComfyUI Workflow Optimizer Skill

一个面向 **ComfyUI 工作流 JSON** 的 Codex Skill，重点服务于 **RTX 3060 12GB 显卡** 用户。

它可以帮助你检查网上下载的 ComfyUI 工作流，自动发现缺失模型、疑似缺失自定义节点，并把容易爆显存的参数调整到更适合 3060 12G 的范围。同时会优先扫描本地 `D:\ComfyUI\models`，为缺失模型寻找相似的本地平替方案。

---

## 项目简介

很多 ComfyUI 工作流来自不同作者、不同模型环境，直接导入后常见问题包括：

- 模型文件不存在
- LoRA、VAE、ControlNet、放大模型路径不匹配
- 自定义节点没有安装
- 分辨率、batch、steps、cfg 等参数过高导致显存爆掉
- 工作流里使用的模型，本地其实有相似模型可以替换

本 Skill 的目标是让 Codex 在处理 ComfyUI workflow JSON 时，先做一轮结构化审计，再输出能跑通的优化版本。

---

## 核心功能

- **3060 12G 参数优化**：自动限制 `batch_size`、`steps`、`cfg`、分辨率、放大倍率等高风险参数
- **本地模型扫描**：默认扫描 `D:\ComfyUI\models`
- **模型缺失检查**：识别 checkpoint、LoRA、VAE、ControlNet、upscale model 等常见模型字段
- **相似模型平替**：优先选择本地同类型、同扩展名、名称相似的模型
- **缺失节点检查**：扫描 `D:\ComfyUI\custom_nodes`，提示疑似缺失的自定义节点
- **生成补丁工作流**：保留原 JSON，输出一份优化后的新 JSON
- **中文报告**：适合直接看结论，知道哪里缺、哪里改、能不能跑

---

## 目录结构

```text
├── SKILL.md                    # Codex Skill 主说明
├── agents/
│   └── openai.yaml             # Codex UI 元数据
├── references/
│   └── model-fields.md         # 常见 ComfyUI 模型字段参考
├── scripts/
│   └── workflow_audit.py       # 工作流审计与优化脚本
└── images/
    ├── wechat-qr.png           # 作者微信二维码
    └── zanshang.png            # 打赏二维码
```

---

## 安装方法

### 方式一：安装到 Codex Skills 目录

在 Windows PowerShell 中执行：

```powershell
git clone https://github.com/liudali333/comfyui-workflow-optimizer.git "$env:USERPROFILE\.codex\skills\comfyui-workflow-optimizer"
```

安装完成后，重启 Codex。

之后可以直接对 Codex 说：

```text
用 ComfyUI Workflow Optimizer 帮我优化这个工作流 JSON，按 3060 12G，检查缺模型、缺节点，并优先用 D:\ComfyUI\models 里的本地模型平替。
```

### 方式二：只使用脚本

如果你不需要 Codex Skill，也可以直接运行脚本：

```powershell
python scripts\workflow_audit.py --workflow 你的工作流.json --comfy-root D:\ComfyUI --models-root D:\ComfyUI\models --custom-nodes-root D:\ComfyUI\custom_nodes
```

生成优化后的工作流：

```powershell
python scripts\workflow_audit.py --workflow 你的工作流.json --comfy-root D:\ComfyUI --models-root D:\ComfyUI\models --custom-nodes-root D:\ComfyUI\custom_nodes --write 优化后工作流.json
```

---

## 使用示例

### 检查工作流是否能跑

```powershell
python scripts\workflow_audit.py --workflow workflow.json --comfy-root D:\ComfyUI
```

输出内容会包含：

- 是否可能跑通
- 缺失模型列表
- 本地相似模型候选
- 疑似缺失自定义节点
- 3060 12G 参数优化建议

### 生成 3060 12G 优化版

```powershell
python scripts\workflow_audit.py --workflow workflow.json --comfy-root D:\ComfyUI --write workflow.3060-12g.json
```

脚本会保留原始 `workflow.json`，并写出新的 `workflow.3060-12g.json`。

---

## 3060 12G 默认优化策略

默认采用保守策略，优先保证能跑通：

| 参数 | 默认处理 |
|------|----------|
| `batch_size` | 限制为 1 |
| `steps` | 最高 32 |
| `cfg` | 最高 9 |
| SDXL 分辨率 | 约 1024x1024 以内 |
| SD1.5 分辨率 | 建议 768x768 或更低 |
| 放大倍率 | 避免过高，建议分阶段或 tiled |

如果你想追求更高质量，可以在跑通后再逐步提高分辨率或 steps。

---

## 支持的模型类型

脚本会重点检查以下字段：

- `ckpt_name`
- `lora_name`
- `vae_name`
- `clip_name`
- `unet_name`
- `control_net_name`
- `upscale_model_name`
- `embedding`
- 以及其他常见模型字段

默认支持的模型文件扩展名：

```text
.safetensors, .ckpt, .pt, .pth, .bin, .gguf, .onnx
```

---

## 注意事项

- 自动平替模型只能根据文件名、类型、相似度判断，不能保证风格完全一致
- SDXL 与 SD1.5 模型不要随便互换，除非你明确知道工作流兼容
- 缺失自定义节点只能做启发式判断，最终仍建议打开 ComfyUI 看控制台报错
- 建议永远保留原始 workflow JSON，只对副本做修改

---

## 联系作者 | 打赏支持

扫描下方二维码添加微信或打赏支持：

| 微信好友 | 赞赏码 |
|:---:|:---:|
| ![微信二维码](images/wechat-qr.png) | ![赞赏码](images/zanshang.png) |
| 扫码添加作者微信 | 打赏支持项目开发 |

---

## 获取帮助

- ComfyUI 工作流优化、缺模型、缺节点问题：可以在 Issues 中反馈
- 商务合作 / 定制开发：扫码添加微信联系

---

## 许可证

本项目用于学习、研究和个人工作流优化。实际使用中请遵守 ComfyUI、自定义节点、模型文件及相关资源的各自许可证。

---

如果这个项目对你有帮助，欢迎 Star 支持。
