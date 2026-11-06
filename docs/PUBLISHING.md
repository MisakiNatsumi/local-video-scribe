# 源码与发行包

仓库只提交源码、文档、图标、依赖版本和打包脚本。

`packaging/export_source.py` 使用明确的文件清单导出待上传源码，同时拒绝本机路径、
电子邮件地址及常见凭据格式。导出目录不会包含会话记录、视频、模型、日志、转写结果或本地验证 JSON。

## 从源码生成本地便携包

在 Windows x64 上，安装带 Tkinter 的 Python，创建独立虚拟环境并安装 `requirements.txt`。
准备可用的 FFmpeg，运行：

```powershell
.\.venv\Scripts\python.exe packaging\build_runtime_portable.py
```

脚本使用当前 Python 的原始运行时文件，并复制项目依赖和默认模型。
已缓存的模型先读本地；缺失时从 faster-whisper 对应的上游获取。
本地功能打包不代表已经满足公开再分发条件，公开附件前应完成
[第三方声明中的发布材料](../THIRD_PARTY_NOTICES.md)。

`packaging/build_portable.py` 是可选 PyInstaller 构建路径，需额外安装 PyInstaller。
部分 Windows 应用控制策略可能拦截新生成的 EXE；不要求用户关闭系统防护。

公开发布时应额外提供版本号、源码标签、第三方许可正文、文件 SHA-256、验证范围及已知限制。
模型可与程序分开发布，或在首次启动时从清晰标注的来源下载。
