from pathlib import Path
import sysconfig
from PyInstaller.utils.hooks import collect_all, copy_metadata

project = Path(SPECPATH).parent
site = Path(sysconfig.get_paths()['purelib'])
datas, binaries, hiddenimports = [], [], []
for package in ['faster_whisper', 'ctranslate2', 'tokenizers', 'onnxruntime']:
    package_data, package_binaries, package_imports = collect_all(package)
    datas += package_data
    binaries += package_binaries
    hiddenimports += package_imports
datas += copy_metadata('faster-whisper', recursive=True)
for dll in (site / 'nvidia').rglob('*.dll'):
    datas.append((str(dll), str(Path('nvidia') / dll.parent.relative_to(site / 'nvidia'))))
datas += [(str(project / 'packaging' / 'app.ico'), '.')]

a = Analysis([str(project / 'app.py')], pathex=[str(project)],
             binaries=binaries, datas=datas, hiddenimports=hiddenimports,
             hookspath=[], hooksconfig={}, runtime_hooks=[],
             excludes=['torch', 'torchaudio', 'tensorflow', 'transformers', 'matplotlib',
                       'pandas', 'scipy', 'IPython', 'pytest'],
             noarchive=False, optimize=1)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True,
          name='视频转文字', debug=False, bootloader_ignore_signals=False,
          strip=False, upx=False, console=False,
          icon=str(project / 'packaging' / 'app.ico'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='视频转文字')
