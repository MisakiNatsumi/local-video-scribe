"""Bundle the unmodified, signed Python runtime with the application and model."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from build_portable import make_icon, collect_licenses

PROJECT = Path(__file__).resolve().parents[1]


def main():
    os.chdir(PROJECT)
    if not (PROJECT / 'packaging' / 'app.ico').is_file():
        make_icon(PROJECT / 'packaging' / 'app.ico')
    stamp = time.strftime('%Y%m%d-%H%M%S')
    release = PROJECT / 'releases' / (stamp + '-runtime')
    package = release / '视频转文字'
    runtime = package / 'runtime'
    runtime.mkdir(parents=True)
    base = Path(sys.base_prefix)
    for name in ['DLLs', 'Lib', 'tcl']:
        ignore = shutil.ignore_patterns('__pycache__', '*.pyc', 'site-packages', 'test', 'tests', 'idlelib', 'ensurepip')
        shutil.copytree(base / name, runtime / name, ignore=ignore)
    python_tag = f'python{sys.version_info.major}{sys.version_info.minor}'
    for name in ['python.exe', 'pythonw.exe', 'python3.dll', python_tag + '.dll',
                 'vcruntime140.dll', 'vcruntime140_1.dll', 'LICENSE.txt']:
        source = base / name
        if source.is_file():
            shutil.copyfile(source, runtime / name)
    # Isolate sys.path from the host installation and any PYTHONPATH.
    (runtime / (python_tag + '._pth')).write_text('Lib\nDLLs\nLib/site-packages\nimport site\n', encoding='utf-8')
    site = Path(sys.prefix) / 'Lib' / 'site-packages'
    shutil.copytree(site, runtime / 'Lib' / 'site-packages', ignore=shutil.ignore_patterns(
        '__pycache__', '*.pyc', 'pip', 'pip-*.dist-info', 'PyInstaller', 'pyinstaller*',
        '_pyinstaller_hooks_contrib', 'setuptools', 'setuptools-*.dist-info', 'pkg_resources',
        '_distutils_hack', 'distutils-precedence.pth', 'pefile*', 'peutils*', 'altgraph*',
        'pywin32_ctypes*', 'win32ctypes'))
    shutil.copyfile(PROJECT / 'app.py', package / 'app.py')
    shutil.copyfile(PROJECT / 'packaging' / 'app.ico', package / 'app.ico')
    (package / 'portable.json').write_text(json.dumps({
        'version': 1, 'runtime': sys.version.split()[0]}), encoding='utf-8')
    sys.path.insert(0, str(PROJECT))
    import app as source_app
    source_app.prepare_runtime()
    from faster_whisper.utils import download_model
    from huggingface_hub.errors import LocalEntryNotFoundError
    model_cache = str(PROJECT / 'models' / 'whisper')
    try:
        snapshot = download_model('turbo', cache_dir=model_cache, local_files_only=True)
    except LocalEntryNotFoundError:
        snapshot = download_model('turbo', cache_dir=model_cache)
    shutil.copytree(snapshot, package / 'models' / 'turbo', symlinks=False)
    ffmpeg_dir = package / '_internal' / 'ffmpeg'
    ffmpeg_dir.mkdir(parents=True)
    shutil.copyfile(shutil.which('ffmpeg'), ffmpeg_dir / 'ffmpeg.exe')
    collect_licenses(package / 'third-party-notices', Path(shutil.which('ffmpeg')))
    for name in ['LICENSE', 'ACKNOWLEDGEMENTS.md', 'THIRD_PARTY_NOTICES.md']:
        if (PROJECT / name).is_file():
            shutil.copyfile(PROJECT / name, package / name)
    vbs = '''Option Explicit
Dim fs, sh, root, command, argument
Set fs = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
root = fs.GetParentFolderName(WScript.ScriptFullName)
command = Chr(34) & root & "\\runtime\\pythonw.exe" & Chr(34) & " " & Chr(34) & root & "\\app.py" & Chr(34)
For Each argument In WScript.Arguments
    command = command & " " & Chr(34) & argument & Chr(34)
Next
sh.CurrentDirectory = root
sh.Run command, 1, False
'''
    (package / '启动应用.vbs').write_text(vbs, encoding='utf-8')
    (package / '启动应用.cmd').write_text(
        '@echo off\r\ncd /d "%~dp0"\r\nstart "" "%~dp0runtime\\pythonw.exe" "%~dp0app.py" %*\r\n', encoding='ascii')
    (package / '开始使用.txt').write_text(
        '视频转文字 · 一键便携版\n\n'
        '完整解压，然后双击「启动应用.vbs」。如系统没有 VBScript，也可双击「启动应用.cmd」。\n'
        '添加视频或文件夹，选择音频语言，点击「开始转写」。\n'
        '无需安装 Python、FFmpeg、转写依赖，也无需配置 PATH。\n'
        '默认 turbo 模型已内置，音视频在本机处理；large-v3 需要首次下载。\n'
        '默认结果保存在 data/results；界面可以修改位置。\n'
        '优先使用 NVIDIA 显卡；无可用显卡时使用 CPU，速度较慢。\n'
        '本包包含未修改的、由 Python Software Foundation 签名的 Python 运行时。\n'
        '请保留整个文件夹，可以将整个文件夹复制到其他位置。\n'
        '没有更改 Windows 防护设置；本包依然受机器原有的应用控制策略约束。\n', encoding='utf-8-sig')
    print('Runtime bundle assembled. Compressing...', flush=True)
    archive = release / '视频转文字-一键便携版.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=3,
                         allowZip64=True) as bundle:
        for path in sorted(package.rglob('*')):
            if path.is_file():
                bundle.write(path, path.relative_to(release))
    summary = {'app': str(package), 'launcher': str(package / '启动应用.vbs'),
               'python': str(runtime / 'python.exe'), 'zip': str(archive),
               'bytes_unpacked': sum(p.stat().st_size for p in package.rglob('*') if p.is_file()),
               'bytes_zip': archive.stat().st_size}
    with archive.open('rb') as stream:
        summary['sha256'] = hashlib.file_digest(stream, 'sha256').hexdigest()
    (release / 'release.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    (PROJECT / 'releases' / 'latest-runtime.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
