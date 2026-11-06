# 致谢与上游引用

Local Video Scribe 是视频导入、批量任务、转写进度和结果导出的桌面工具。
语音识别能力来自下列上游项目及模型；本项目没有训练新的语音识别模型。
本项目与这些项目及其维护者不存在官方隶属或背书关系。

| 项目 / 模型 | 在本项目中的用途 | 上游许可 / 来源 |
| --- | --- | --- |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | Whisper 推理、批量处理与 VAD 集成 | [MIT](https://github.com/SYSTRAN/faster-whisper/blob/master/LICENSE) |
| [CTranslate2](https://github.com/OpenNMT/CTranslate2) | CPU / NVIDIA GPU 推理后端 | [MIT](https://github.com/OpenNMT/CTranslate2/blob/master/LICENSE) |
| [OpenAI Whisper](https://github.com/openai/whisper) | 原始语音识别模型 | [MIT](https://github.com/openai/whisper/blob/main/LICENSE) |
| [Whisper large-v3-turbo](https://huggingface.co/openai/whisper-large-v3-turbo) | 默认速度优先模型 | 上游模型卡及 MIT 许可 |
| [CTranslate2 格式的 large-v3-turbo](https://huggingface.co/dropbox-dash/faster-whisper-large-v3-turbo) | faster-whisper 使用的 FP16 权重 | 模型卡标注 MIT；旧地址为 `mobiuslabsgmbh/faster-whisper-large-v3-turbo` |
| [Silero VAD](https://github.com/snakers4/silero-vad) | 检测语音片段、过滤静音 | [MIT](https://github.com/snakers4/silero-vad/blob/master/LICENSE) |
| [ONNX Runtime](https://github.com/microsoft/onnxruntime) | 运行 VAD 模型 | [MIT](https://github.com/microsoft/onnxruntime/blob/main/LICENSE) |
| [FFmpeg](https://ffmpeg.org/) | 独立子进程提取、重采样音轨 | 构建相关；当前本机使用的 Gyan essentials 构建为 GPLv3 |
| [Gyan FFmpeg Builds](https://www.gyan.dev/ffmpeg/builds/) | 本机 Windows FFmpeg 二进制来源 | 以具体构建的许可、源码和构建信息为准 |
| [Python / Tkinter](https://www.python.org/) | 应用运行时与桌面界面 | PSF 及 Python 发行版中附带的第三方许可 |
| [Hugging Face Hub](https://github.com/huggingface/huggingface_hub) / [Tokenizers](https://github.com/huggingface/tokenizers) | 模型获取、缓存与分词 | Apache-2.0；保留上游相关声明 |
| [NumPy](https://numpy.org/) | 音频样本转换 | 以发行版附带的完整许可及第三方声明为准 |
| [PyAV](https://github.com/PyAV-Org/PyAV) | faster-whisper 的依赖 | BSD-3-Clause；其二进制中所含 FFmpeg 库另有许可 |
| [NVIDIA CUDA / cuBLAS](https://docs.nvidia.com/cuda/eula/index.html) / [cuDNN](https://docs.nvidia.com/deeplearning/cudnn/backend/latest/reference/eula.html) | NVIDIA GPU 加速运行库 | NVIDIA 专有许可与再分发条款，不属于本项目 MIT 许可 |
| [PyInstaller](https://pyinstaller.org/) | 可选 EXE 打包路径 | 以 PyInstaller 的许可与 bootloader 例外为准 |

Whisper 论文：Alec Radford 等，**Robust Speech Recognition via Large-Scale Weak Supervision**，
[arXiv:2212.04356](https://arxiv.org/abs/2212.04356)。

本机验证的默认模型缓存快照为 `0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf`。
该记录用于说明验证来源，不表示已经验证所有后续上游版本。

许可证正文与发布包再分发说明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
