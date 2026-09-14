# DeepGaze 可行性记录

> 验证日期：2026-07-13

## 已验证环境

- GPU：NVIDIA GeForce RTX 4060 Laptop GPU，8 GiB 显存。
- Python：3.12.6，独立环境：`.venv-deepgaze`。
- PyTorch：`2.13.0+cu126`，`torch.cuda.is_available()` 为 `True`。
- DeepGaze：DeepGaze III，上游提交 `c87b106e8698497c59998b469c45770e993baca3`。

## 真实推理结果

使用项目内海报素材，缩放为 `360 × 480`，成功在 CUDA 上执行 DeepGaze III：

- 首次模型加载与单次推理：约 `2426.4 ms`。
- 峰值已分配显存：约 `183.9 MiB`。
- 输出热力图尺寸：`480 × 360`，数值全部有效。

DeepGaze III 要求扫描路径条件。服务在首个预测前使用画布中心作为中性起点，随后由服务采样预测注视点；这是**模型模拟的视觉注意力**，不是摄像头或真实用户眼动数据。

## 安装与启动

```powershell
.\.venv-deepgaze\Scripts\python.exe -m pip install -r services\deepgaze\requirements-model.txt
.\scripts\run_deepgaze.ps1
```

服务地址为 `http://127.0.0.1:8001`，提供 `GET /health` 与 `POST /v1/predict`。
