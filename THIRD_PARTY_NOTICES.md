# 第三方声明

根目录 [LICENSE](LICENSE) 仅适用于本项目自有的界面、任务调度、结果导出与打包脚本代码。
第三方程序、Python 包、模型权重及其子依赖保留各自的版权、许可证和通知要求。
不能将整个包含 NVIDIA 运行库和 FFmpeg 的便携包统称为 MIT 软件。

## 源码仓库

源码仓库不包含模型权重、Python 运行时、GPU DLL、FFmpeg 二进制、课程视频、转写结果或本机日志。
上游项目及模型的用途和链接见 [ACKNOWLEDGEMENTS.md](ACKNOWLEDGEMENTS.md)。
`requirements-lock.txt` 记录本机验证的 Python 包版本，不代替各依赖自己的许可文件。

## 发布便携包

便携包公开发布前需要针对实际包含的文件补齐以下材料：

1. 保存所有上游版权及许可正文，并收集子依赖的 NOTICE、COPYING 等文件。
2. 将 Whisper 模型、Silero VAD、CTranslate2 等上游的许可正文单独保留；不能只依赖 wheel 是否携带它们。
3. Python 运行时应保留 Python 许可证，以及 Tcl/Tk 和附带组件要求的声明。
4. 当前使用的 Gyan FFmpeg essentials 为 GPLv3 构建。除许可正文外，分发二进制仍需要符合适用的对应源码提供义务。
   当前本机构建的 README 指向 FFmpeg 提交 `bf1b838f2a`；完整构建的外部库、构建脚本及来源也应核对。
   单独放一个最新上游仓库链接，不能自动证明对应源码义务已经满足。
5. NVIDIA cuBLAS、NVRTC、cuDNN 是专有许可组件，只能在其条款允许的范围内再分发。
   保留实际版本的 EULA、可分发组件清单和必要终端用户条款，不能套用本项目 MIT 许可。
6. PyAV wheel 可能附带 FFmpeg 库；应独立核对该 wheel 的二进制依赖和适用许可证。

现有本地便携包是功能验证产物。源码发布与便携包公开发布分开处理；
在上述再分发材料补齐前，不将本地大包直接作为公开 Release 附件。

参考来源：

- [FFmpeg 许可说明](https://ffmpeg.org/legal.html)
- [FFmpeg 上游 LICENSE](https://github.com/FFmpeg/FFmpeg/blob/master/LICENSE.md)
- [Gyan Windows 构建说明](https://www.gyan.dev/ffmpeg/builds/)
- [NVIDIA CUDA EULA](https://docs.nvidia.com/cuda/eula/index.html)
- [NVIDIA cuDNN EULA](https://docs.nvidia.com/deeplearning/cudnn/backend/latest/reference/eula.html)
- [Python 许可证](https://docs.python.org/3/license.html)

## GitHub 附件大小

GitHub Release 的每个附件必须小于 2 GiB。
当前约 3 GB 的本地 ZIP 不能直接作为单个附件上传。
可选择分成程序包和模型包，或在用户首次启动时从明确标注的上游下载模型。
仅解决附件大小，不等于完成第三方再分发材料。

来源：[GitHub Releases 文档](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases#storage-and-bandwidth-quotas)。
