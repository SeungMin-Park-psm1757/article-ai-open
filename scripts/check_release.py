"""Check the available Git history against a reviewed file list and simple leak rules."""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_BLOB = 1024 * 1024
PATTERNS = [
    re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    re.compile((r'gh' + r'p_[A-Za-z0-9]{20,}').encode()),
    re.compile((r'github_' + r'pat_[A-Za-z0-9_]{20,}').encode()),
    re.compile((r'sk-' + r'proj-[A-Za-z0-9_-]{20,}').encode()),
    re.compile(rb'(?i)\b[A-Z]:\\(?:Users|dev)\\'),
]


def git(*args, input_bytes=None):
    return subprocess.run(['git', *args], cwd=ROOT, input=input_bytes,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout


def scan_blob(data):
    return len(data) > MAX_BLOB or b'\0' in data or any(pattern.search(data) for pattern in PATTERNS)


def main():
    lines = (ROOT / 'PUBLIC_FILES.txt').read_text(encoding='utf-8').splitlines()
    allowed = set(lines)
    if not allowed or '' in allowed or len(allowed) != len(lines):
        raise ValueError('Invalid file allowlist')
    staged = git('ls-files', '--stage', '-z').split(b'\0')
    staged_paths, staged_ids = set(), []
    for record in filter(None, staged):
        metadata, name = record.split(b'\t', 1)
        mode, object_id, stage = metadata.split()
        if stage != b'0' or mode not in (b'100644', b'100755'):
            raise ValueError('Unmerged, linked or unsupported staged file')
        staged_paths.add(name.decode('utf-8'))
        staged_ids.append(object_id)
    if staged_paths != allowed:
        raise ValueError(f'Index differs from allowlist: unexpected={sorted(staged_paths - allowed)}, missing={sorted(allowed - staged_paths)}')
    commits = git('rev-list', '--all').decode('ascii').splitlines()
    if not commits:
        raise ValueError('No Git commits available for history inspection')
    for commit in commits:
        identities = git('show', '-s', '--format=%ae%x00%ce', commit).decode('utf-8').strip().split('\0')
        if len(identities) != 2 or any(
            email.lower() != 'noreply@github.com' and not email.lower().endswith('@users.noreply.github.com')
            for email in identities
        ):
            raise ValueError(f'Commit {commit[:12]} has an email that is not a GitHub no-reply address')
        paths = set()
        for record in filter(None, git('ls-tree', '-r', '-z', commit).split(b'\0')):
            metadata, name = record.split(b'\t', 1)
            mode, kind, _ = metadata.split()
            if mode not in (b'100644', b'100755') or kind != b'blob':
                raise ValueError(f'Commit {commit[:12]} contains a link or unsupported object')
            paths.add(name.decode('utf-8'))
        unexpected = paths - allowed
        if unexpected:
            raise ValueError(f'Commit {commit[:12]} contains unapproved paths: {sorted(unexpected)}')
    ids = list(set(git('rev-list', '--objects', '--all', '--no-object-names').splitlines() + staged_ids))
    info = git('cat-file', '--batch-check=%(objectname) %(objecttype) %(objectsize)', input_bytes=b'\n'.join(ids) + b'\n')
    checked = 0
    for line in info.splitlines():
        object_id, kind, size = line.split()
        if kind != b'blob':
            continue
        if int(size) > MAX_BLOB:
            raise ValueError(f'Oversize Git blob: {object_id.decode()}')
        if scan_blob(git('cat-file', 'blob', object_id.decode('ascii'))):
            raise ValueError(f'Possible sensitive or binary Git blob: {object_id.decode()}')
        checked += 1
    print(f'Checked index, {len(commits)} commits and {checked} unique blobs. Heuristic checks do not establish publication rights.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f'Release check failed: {exc}', file=sys.stderr)
        sys.exit(1)
