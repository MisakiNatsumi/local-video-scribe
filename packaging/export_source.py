"""Allowlist-only source export; never copy a workspace or runtime wholesale."""
from pathlib import Path
import hashlib
import json
import re
import shutil
import time
import zipfile

PROJECT = Path(__file__).resolve().parents[1]
FILES = {
    'app.py': 'app.py', 'Start.cmd': 'Start.cmd', '.gitignore': '.gitignore',
    'requirements.txt': 'requirements.txt', 'requirements-lock.txt': 'requirements-lock.txt',
    'LICENSE': 'LICENSE', 'README.public.md': 'README.md',
    'ACKNOWLEDGEMENTS.md': 'ACKNOWLEDGEMENTS.md',
    'THIRD_PARTY_NOTICES.md': 'THIRD_PARTY_NOTICES.md',
    'docs/VALIDATION.md': 'docs/VALIDATION.md', 'docs/PUBLISHING.md': 'docs/PUBLISHING.md',
    'packaging/app.ico': 'packaging/app.ico',
    'packaging/VideoTranscriber.spec': 'packaging/VideoTranscriber.spec',
    'packaging/build_portable.py': 'packaging/build_portable.py',
    'packaging/build_runtime_portable.py': 'packaging/build_runtime_portable.py',
    'packaging/export_source.py': 'packaging/export_source.py',
}


def main():
    stamp = time.strftime('%Y%m%d-%H%M%S')
    export = PROJECT / 'github-ready' / stamp / 'local-video-scribe'
    export.mkdir(parents=True)
    files = dict(FILES)
    for source in (PROJECT / 'licenses').rglob('*'):
        if source.is_file():
            files[source.relative_to(PROJECT).as_posix()] = source.relative_to(PROJECT).as_posix()
    patterns = {
        'Windows user profile path': r'[A-Za-z]:[\\/]+Users[\\/]+[^\s\\/]+',
        'Email address': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b',
        'GitHub credential': r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b',
        'API credential': r'\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b',
        'Private key': r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
    }
    manifest = []
    for name, target in sorted(files.items()):
        source = PROJECT / name
        data = source.read_bytes()
        if source.suffix != '.ico':
            text = data.decode('utf-8-sig')
            for label, pattern in patterns.items():
                if re.search(pattern, text):
                    raise ValueError(f'{label} found in {name}; export refused')
        destination = export / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        manifest.append({'path': target, 'bytes': len(data),
                         'sha256': hashlib.sha256(data).hexdigest()})
    archive = export.parent / 'local-video-scribe-source.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
        for item in manifest:
            bundle.write(export / item['path'], 'local-video-scribe/' + item['path'])
    result = {'folder': str(export), 'zip': str(archive), 'files': manifest}
    (PROJECT / 'github-ready' / 'latest.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'files': len(manifest), 'bytes': sum(x['bytes'] for x in manifest),
                      'folder': str(export), 'zip': str(archive)}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
