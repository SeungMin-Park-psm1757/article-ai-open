"""Download pinned model artifacts into an isolated user-selected directory."""
import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath

LOCK = Path(__file__).resolve().parents[1] / 'models.lock.json'
BLOCK = 1024 * 1024


def safe_file(root, name):
    path = PurePosixPath(name)
    if not name or '\\' in name or path.is_absolute() or any(p in ('', '.', '..') or ':' in p for p in path.parts):
        raise ValueError('Invalid file path in model lock')
    current = root
    for part in path.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError('Symbolic links are not allowed in the model directory')
    return current


def verified(path, entry):
    if not path.is_file() or path.stat().st_size != entry['size']:
        return False
    if entry['algorithm'] == 'sha256':
        digest = hashlib.sha256()
    elif entry['algorithm'] == 'git-sha1':
        digest = hashlib.sha1()
        digest.update(f"blob {entry['size']}\0".encode('ascii'))
    else:
        raise ValueError('Unknown checksum algorithm')
    with path.open('rb') as source:
        for block in iter(lambda: source.read(BLOCK), b''):
            digest.update(block)
    return digest.hexdigest() == entry['digest']


def download(model, entry, staging):
    target = safe_file(staging, entry['path'])
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if verified(target, entry):
            return
        raise ValueError(f"Checksum mismatch: {entry['path']}")
    part = target.with_name(target.name + '.part')
    if part.is_symlink():
        raise ValueError('Symbolic links are not allowed')
    offset = part.stat().st_size if part.exists() else 0
    if offset > entry['size']:
        raise ValueError(f"Partial file is too large: {entry['path']}")
    if offset < entry['size']:
        url = f"https://huggingface.co/{model['repo']}/resolve/{model['revision']}/{urllib.parse.quote(entry['path'], safe='/')}"
        request = urllib.request.Request(url, headers={'Range': f'bytes={offset}-'} if offset else {})
        with urllib.request.urlopen(request, timeout=60) as response:
            if offset and (response.status != 206 or not response.headers.get('Content-Range', '').startswith(f'bytes {offset}-')):
                raise ValueError('Server did not accept the requested resume range')
            with part.open('ab' if part.exists() else 'xb') as output:
                while True:
                    chunk = response.read(BLOCK)
                    if not chunk:
                        break
                    offset += len(chunk)
                    if offset > entry['size']:
                        raise ValueError('Download exceeds expected size')
                    output.write(chunk)
    if not verified(part, entry):
        raise ValueError(f"Incomplete or corrupt download: {entry['path']}. Keep the partial file for resume or remove it manually before retrying.")
    part.rename(target)


def install(model, root):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', model['repo']) or not re.fullmatch(r'[0-9a-f]{40}', model['revision']):
        raise ValueError('Invalid model identity')
    root.mkdir(parents=True, exist_ok=True)
    if root.is_symlink():
        raise ValueError('The model root cannot be a symbolic link')
    name = model['repo'].replace('/', '--')
    final = root / name
    staging = root / (name + '.partial')
    if final.exists() or final.is_symlink():
        raise FileExistsError(f'Model destination already exists: {final}')
    if staging.is_symlink():
        raise ValueError('The staging directory cannot be a symbolic link')
    marker = staging / '.article-ai-download.json'
    identity = {'repo': model['repo'], 'revision': model['revision']}
    try:
        staging.mkdir()
    except FileExistsError:
        if marker.is_symlink() or not marker.is_file():
            raise ValueError('Existing staging directory is not owned by this installer')
        if json.loads(marker.read_text(encoding='utf-8')) != identity:
            raise ValueError('Staging directory belongs to a different model or revision')
    else:
        with marker.open('x', encoding='utf-8') as output:
            json.dump(identity, output)
    remaining = 0
    for entry in model['files']:
        target = safe_file(staging, entry['path'])
        part = target.with_name(target.name + '.part')
        if part.is_symlink():
            raise ValueError('Symbolic links are not allowed')
        remaining += max(0, entry['size'] - (entry['size'] if target.exists() else part.stat().st_size if part.exists() else 0))
    if shutil.disk_usage(root).free < remaining + 512 * BLOCK:
        raise OSError('Insufficient free disk space, including 512 MiB reserve')
    for entry in model['files']:
        print(f"Verifying/downloading {model['role']}: {entry['path']}", flush=True)
        download(model, entry, staging)
    expected = {entry['path'] for entry in model['files']} | {marker.name}
    actual = {p.relative_to(staging).as_posix() for p in staging.rglob('*') if p.is_file() or p.is_symlink()}
    if actual != expected:
        raise ValueError('Staging contains unexpected files; inspect it before retrying')
    os.rename(staging, final)
    return final


def main():
    parser = argparse.ArgumentParser(description='Download one pinned model after reviewing its license.')
    parser.add_argument('--model', choices=['llm', 'embedding', 'reranker'], required=True)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--accept-license-and-download', action='store_true', required=True)
    args = parser.parse_args()
    data = json.loads(LOCK.read_text(encoding='utf-8'))
    model = next(item for item in data['models'] if item['role'] == args.model)
    print(f"{model['repo']} @ {model['revision']}, license: {model['license_url']}")
    print(f"Expected total bytes: {sum(item['size'] for item in model['files'])}")
    try:
        print(f'Installed and verified: {install(model, args.destination)}')
    except (OSError, ValueError) as exc:
        print(f'Installation failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
