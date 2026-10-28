"""Check repository-local Markdown links in the tracked public file list."""
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
LINKS = re.compile(r'(?<!!)\[[^\]]+\]\(([^\s)]+)(?:\s+"[^"]*")?\)')


def main():
    allowed = set((ROOT / 'PUBLIC_FILES.txt').read_text(encoding='utf-8').splitlines())
    checked = 0
    for name in sorted(x for x in allowed if x.endswith('.md')):
        path = ROOT / name
        for target in LINKS.findall(path.read_text(encoding='utf-8')):
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            destination = (path.parent / unquote(parsed.path)).resolve()
            if not destination.is_relative_to(ROOT) or not destination.is_file() or destination.relative_to(ROOT).as_posix() not in allowed:
                raise ValueError(f'Invalid local link in {name}: {target}')
            checked += 1
    print(f'Checked {checked} local Markdown links.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as exc:
        print(f'Documentation check failed: {exc}', file=sys.stderr)
        sys.exit(1)
