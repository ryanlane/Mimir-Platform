#!/usr/bin/env python3
"""Add AGPL-3.0 license headers to Python and JavaScript source files."""
import os
import sys

PY_HEADER = """\
# Copyright (C) 2026 Ryan Lane
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
"""

JS_HEADER = """\
// Copyright (C) 2026 Ryan Lane
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published
// by the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with this program. If not, see <https://www.gnu.org/licenses/>.
"""


def already_has_header(content: str) -> bool:
    return "Copyright" in content[:500]


def add_py_header(path: str, content: str) -> str:
    lines = content.splitlines(keepends=True)
    insert_at = 0
    # Preserve shebang and encoding declarations at the top
    for i, line in enumerate(lines[:3]):
        if line.startswith("#!") or line.startswith("# -*-") or line.startswith("# coding"):
            insert_at = i + 1
        else:
            break
    lines.insert(insert_at, PY_HEADER + ("\n" if not lines[insert_at:insert_at+1] or lines[insert_at] != "\n" else ""))
    return "".join(lines)


def add_js_header(path: str, content: str) -> str:
    return JS_HEADER + "\n" + content


def process_file(path: str, header_fn) -> bool:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    if not content.strip():
        return False
    if already_has_header(content):
        return False
    new_content = header_fn(path, content)
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)
    return True


def walk(root: str, extensions: tuple, header_fn, skip_dirs: tuple = ()) -> list[str]:
    updated = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skipped directories in-place
        dirnames[:] = [d for d in dirnames if d not in skip_dirs and not d.startswith(".")]
        for filename in filenames:
            if filename.endswith(extensions):
                path = os.path.join(dirpath, filename)
                if process_file(path, header_fn):
                    updated.append(path)
    return updated


if __name__ == "__main__":
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    py_root = os.path.join(base, "mimir-api", "app")
    js_root = os.path.join(base, "mimir-web", "mimir-ui", "src")

    py_updated = walk(py_root, (".py",), add_py_header, skip_dirs=("__pycache__",))
    js_updated = walk(js_root, (".js", ".jsx"), add_js_header, skip_dirs=("node_modules",))

    all_updated = py_updated + js_updated
    for path in sorted(all_updated):
        print(f"  + {os.path.relpath(path, base)}")

    print(f"\nDone. Updated {len(py_updated)} Python files, {len(js_updated)} JS files.")
