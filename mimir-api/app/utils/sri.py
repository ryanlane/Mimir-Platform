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
SRI (Subresource Integrity) utilities for secure asset loading
Provides SHA-384 hash computation for web assets
"""
import base64
import hashlib
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger("app.utils.sri")


def compute_sri_hash(file_path: Path) -> str:
    """
    Compute SHA-384 hash for Subresource Integrity

    Args:
        file_path: Path to the file to hash

    Returns:
        SRI hash string in format: sha384-{base64_hash}
        Empty string if file doesn't exist
    """
    if not file_path.exists():
        logger.warning(f"SRI hash requested for non-existent file: {file_path}")
        return ""

    try:
        hasher = hashlib.sha384()
        with open(file_path, 'rb') as f:
            # Read in chunks to handle large files efficiently
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)

        hash_bytes = hasher.digest()
        hash_b64 = base64.b64encode(hash_bytes).decode('ascii')
        return f"sha384-{hash_b64}"

    except OSError as e:
        logger.error(f"Failed to compute SRI hash for {file_path}: {e}")
        return ""


def verify_sri_hash(file_path: Path, expected_hash: str) -> bool:
    """
    Verify a file against an expected SRI hash

    Args:
        file_path: Path to the file to verify
        expected_hash: Expected SRI hash (sha384-...)

    Returns:
        True if hash matches, False otherwise
    """
    computed_hash = compute_sri_hash(file_path)
    return computed_hash == expected_hash


def compute_sri_for_directory(directory: Path, extensions: list = None) -> dict:
    """
    Compute SRI hashes for all files in a directory

    Args:
        directory: Directory to scan
        extensions: List of file extensions to include (e.g., ['.js', '.css'])
                   If None, includes all files

    Returns:
        Dictionary mapping relative file paths to SRI hashes
    """
    if extensions is None:
        extensions = ['.js', '.css', '.html', '.svg', '.png', '.jpg', '.jpeg']

    sri_hashes = {}

    if not directory.exists():
        logger.warning(f"SRI directory scan requested for non-existent directory: {directory}")
        return sri_hashes

    try:
        for file_path in directory.rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in extensions:
                relative_path = file_path.relative_to(directory)
                sri_hash = compute_sri_hash(file_path)
                if sri_hash:
                    sri_hashes[str(relative_path)] = sri_hash

    except (OSError, ValueError) as e:
        logger.error(f"Failed to scan directory for SRI hashes {directory}: {e}")

    return sri_hashes


def generate_script_tag(src: str, sri_hash: str | None = None, **attributes) -> str:
    """
    Generate a script tag with optional SRI hash

    Args:
        src: Script source URL
        sri_hash: Optional SRI hash
        **attributes: Additional script tag attributes

    Returns:
        HTML script tag string
    """
    attrs = f'src="{src}"'

    if sri_hash:
        attrs += f' integrity="{sri_hash}" crossorigin="anonymous"'

    for key, value in attributes.items():
        attrs += f' {key}="{value}"'

    return f'<script {attrs}></script>'


def generate_link_tag(href: str, sri_hash: str | None = None, **attributes) -> str:
    """
    Generate a link tag with optional SRI hash

    Args:
        href: Link href URL
        sri_hash: Optional SRI hash
        **attributes: Additional link tag attributes

    Returns:
        HTML link tag string
    """
    attrs = f'href="{href}"'

    if 'rel' not in attributes:
        attributes['rel'] = 'stylesheet'

    if sri_hash:
        attrs += f' integrity="{sri_hash}" crossorigin="anonymous"'

    for key, value in attributes.items():
        attrs += f' {key}="{value}"'

    return f'<link {attrs}>'
