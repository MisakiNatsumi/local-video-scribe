"""Reproducible onedir bundle, private DLLs, materialized model, portable ZIP."""
from pathlib import Path
import hashlib
import importlib.metadata
import json
import os
import shutil
import struct
import subprocess
import sys
import sysconfig
import time
import zipfile
import zlib

PROJECT = Path(__file__).resolve().parents[1]
NAME = '视频转文字'


def make_icon(path):
    size = 64
    raw = bytearray()
    heights = [8, 15, 23, 13, 20, 28, 17, 10]
    for y in range(size):
        raw.append(0)
        for x in range(size):
            rounded = ((x < 12 and y < 12 and (x-12)**2 + (y-12)**2 > 144) or
                       (x > 51 and y < 12 and (x-51)**2 + (y-12)**2 > 144) or
                       (x < 12 and y > 51 and (x-12)**2 + (y-51)**2 > 144) or
                       (x > 51 and y > 51 and (x-51)**2 + (y-51)**2 > 144))
            color = (37, 83 + y, 210 + y // 2, 0 if rounded else 255)
            for i, height in enumerate(heights):
                if 11 + i * 5 <= x < 14 + i * 5 and abs(y - 31) < height / 2:
                    color = (255, 255, 255, 255)
            raw.extend(color)
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    png = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0)) +
           chunk(b'IDAT', zlib.compress(bytes(raw))) + chunk(b'IEND', b''))
    path.write_bytes(struct.pack('<HHH', 0, 1, 1) +
                     struct.pack('<BBBBHHII', size, size, 0, 0, 1, 32, len(png), 22) + png)


def collect_licenses(destination, ffmpeg):
    destination.mkdir(exist_ok=True)
    packages = []
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata['Name']
        packages.append({'name': name, 'version': distribution.version})
        for member in distribution.files or []:
            if any(word in member.name.lower() for word in ('license', 'notice', 'eula', 'copying')):
                source = Path(distribution.locate_file(member))
                if source.is_file() and source.suffix.lower() not in ('.py', '.pyc'):
                    output = destination / name / str(member).replace('..', '_').replace(':', '_')
                    output.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, output)
    for filename in ('LICENSE', 'README.txt'):
        source = ffmpeg.parent.parent / filename
        if source.is_file():
            target = destination / 'FFmpeg' / filename
            target.parent.mkdir(exist_ok=True)
            shutil.copyfile(source, target)
    (destination / 'packages.json').write_text(json.dumps(packages, indent=2), encoding='utf-8')
    if (PROJECT / 'licenses').is_dir():
        shutil.copytree(PROJECT / 'licenses', destination / 'upstream', dirs_exist_ok=True)
    (destination / 'SOURCES.txt').write_text(
        'Application source: app.py and packaging/ in the development project.\n'
        'faster-whisper: https://github.com/SYSTRAN/faster-whisper\n'
        'CTranslate2: https://github.com/OpenNMT/CTranslate2\n'
        'Whisper model: https://huggingface.co/mobiuslabsgmbh/faster-whisper-large-v3-turbo\n'
        'Original Whisper: https://github.com/openai/whisper (MIT)\n'
        'FFmpeg: https://ffmpeg.org/ ; Windows build: https://www.gyan.dev/ffmpeg/builds/\n'
        'NVIDIA CUDA/cuDNN runtime libraries are included under their bundled license terms.\n',
        encoding='utf-8')


def main():
    os.chdir(PROJECT)
    stamp = time.strftime('%Y%m%d-%H%M%S')
    release_root = PROJECT / 'releases' / stamp
    work = PROJECT / 'build' / stamp
    release_root.mkdir(parents=True, exist_ok=True)
    make_icon(PROJECT / 'packaging' / 'app.ico')
    env = os.environ.copy()
    env['PYINSTALLER_CONFIG_DIR'] = str(PROJECT / 'build' / 'pyinstaller-cache')
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm',
                    '--distpath', str(release_root), '--workpath', str(work),
                    str(PROJECT / 'packaging' / 'VideoTranscriber.spec')], check=True, env=env)
    app = release_root / NAME
    ffmpeg = Path(shutil.which('ffmpeg'))
    (app / '_internal' / 'ffmpeg').mkdir(exist_ok=True)
    shutil.copyfile(ffmpeg, app / '_internal' / 'ffmpeg' / 'ffmpeg.exe')
    sys.path.insert(0, str(PROJECT))
    import app as source_app
    source_app.prepare_runtime()
    from faster_whisper.utils import download_model
    snapshot = Path(download_model('turbo', cache_dir=str(PROJECT / 'models' / 'whisper'),
                                   local_files_only=True))
    # Resolve HF cache links into normal files; the release must not depend on cache paths.
    shutil.copytree(snapshot, app / 'models' / 'turbo', symlinks=False)
    (app / '开始使用.txt').write_text(
        '视频转文字 · Windows 便携版\n\n'
        '1. 将压缩包完整解压到一个普通文件夹。\n'
        '2. 双击「视频转文字.exe」。\n'
        '3. 添加视频或文件夹，选择音频语言，点击「开始转写」。\n\n'
        '默认 turbo 模型已经内置，无需安装 Python、FFmpeg 或配置 PATH。\n'
        '可以把视频文件或文件夹拖到 EXE 图标上，直接加入队列。\n'
        'NVIDIA 显卡会优先加速，需要正常的显卡驱动；没有可用 NVIDIA 显卡时使用 CPU，速度会较慢。\n'
        '默认输出：程序文件夹下 data/results，可在界面更换。\n'
        '如果程序位置不可写，数据改存到当前用户的 LocalAppData/VideoTranscriber。\n'
        '原始视频会保留，临时音轨自动清理；音视频不上传。\n'
        '显存不足时把批量大小从 16 调到 8 或 4。\n'
        'large-v3 模型需要首次联网下载，之后可以离线使用。\n'
        '请保留整个程序文件夹；不要只复制其中的 EXE。\n', encoding='utf-8-sig')
    collect_licenses(app / 'third-party-notices', ffmpeg)
    archive = release_root / (NAME + '-Windows便携版.zip')
    print('Compressing portable bundle...', flush=True)
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=3,
                         allowZip64=True) as bundle:
        for path in sorted(app.rglob('*')):
            if path.is_file():
                bundle.write(path, path.relative_to(release_root))
    summary = {'app': str(app), 'exe': str(app / (NAME + '.exe')), 'zip': str(archive),
               'bytes_unpacked': sum(p.stat().st_size for p in app.rglob('*') if p.is_file()),
               'bytes_zip': archive.stat().st_size}
    with archive.open('rb') as stream:
        summary['sha256'] = hashlib.file_digest(stream, 'sha256').hexdigest()
    (release_root / 'release.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    (PROJECT / 'releases' / 'latest.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
