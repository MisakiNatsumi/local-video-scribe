# Local Video Scribe · 本地视频批量转文字

**大批量视频 → 可检索全文与字幕。全本地处理，GPU 高倍速转写。**

Fully local, GPU-accelerated batch video transcription. Pick videos or a folder, get TXT / SRT / JSON.

一个轻量的 Windows 桌面工具：把整批课程、讲座或录屏加入队列，自动处理音轨，
在本机完成语音识别，按文件保存结果。无需逐个手动转音频。

## 功能

- 选择多个视频，或递归扫描整个文件夹；支持常见视频和音频格式。
- FFmpeg 自动提取音轨，临时音轨在任务结束后清理，原文件保留。
- faster-whisper + CTranslate2 批量推理，优先使用 NVIDIA GPU；无可用 GPU 时使用 CPU。
- 默认 `turbo`，可选 `large-v3`；支持自动语言识别或指定语言。
- 导出 TXT 全文、SRT 时间戳字幕、JSON 分段及处理记录。
- 跳过已完成任务；不同目录下的同名文件分别保存；单个文件失败后继续处理。
- 可以停止队列并重新开始；已经完整写出的结果保留。
- 音视频不上传。模型未缓存时需要下载，缓存后可以离线转写。

## 有多快？

本机测试：RTX 5080、`turbo`、FP16、批量大小 16，
**10 分钟的英文合成语音测试视频，包含音轨处理和模型加载约 30 秒，即约 20 倍速。**

这是特定合成样本，不是所有课程的速度或准确率保证。
真实耗时取决于硬件、语言、音频内容、模型、批量大小与显存占用。
详细条件和验证边界见 [验证记录](docs/VALIDATION.md)。

## 从源码运行

已验证 Windows x64、Python 3.14；需要带 Tkinter 的 Python 和可用的 FFmpeg。
GPU 加速还需要正常工作的 NVIDIA 驱动，运行库由依赖包提供。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

之后也可以双击 `Start.cmd`。

1. 点击「添加视频 / 音频」或「添加文件夹」。
2. 选择课程语言，默认模型 `turbo`、批量大小 `16`。
3. 选择保存位置，点击「开始转写」。

显存不足时将批量大小降至 `8` 或 `4`。CPU 模式主要用于兼容，速度通常会下降。

源码版默认保存到 `results/<模型>_<语言>/`。
本地便携构建默认保存到 `data/results/`，可在界面更改。
JSON 记录会包含输入文件的本机路径；分享结果前请自行检查。

## 便携版状态

自带运行时、FFmpeg、GPU 依赖和 `turbo` 模型的一键便携构建已在本机测试。
**当前公开仓库先发布源码；完整下载包将在再分发材料和附件大小问题处理后单独发布。**
源码页的 “Code → Download ZIP” 是源码，不是已安装依赖的应用包。
打包方法和发布事项见 [发布说明](docs/PUBLISHING.md)。

## 范围与限制

- 转写音频中的原语言；尚未提供自动翻译、摘要或说话人分离。
- 不是零误差识别；人名、专业术语、公式等需要核对。
- 默认提取视频中的第一个音轨；没有包含视频画面 OCR。
- 停止会等待当前下载或推理片段结束。
- 当前是个人小工具，已做本机验证，欢迎报告具体输入与错误日志。

## 上游项目与许可

语音识别由 **faster-whisper、CTranslate2、OpenAI Whisper** 及其模型提供，
静音检测使用 **Silero VAD / ONNX Runtime**，音轨处理使用 **FFmpeg**。

项目自有代码采用 [MIT](LICENSE)。第三方依赖和模型保留原许可；
FFmpeg 和 NVIDIA 运行库的分发要求不能由本项目 MIT 许可替代。

- [致谢、模型来源与论文引用](ACKNOWLEDGEMENTS.md)
- [第三方声明和二进制分发说明](THIRD_PARTY_NOTICES.md)

不附带课程、视频、转写内容、用户模型缓存或本机日志。
