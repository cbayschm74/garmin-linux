"""Read-only preview of local Garmin IMG files and map download archives."""

from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import subprocess

FAT32_MAX_FILE_BYTES = 4 * 1024**3 - 1
ARCHIVE_SUFFIXES = {'.7z', '.zip', '.exe'}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _archive_members(listing: str) -> tuple[str, list[dict]]:
    if '\n----------\n' not in listing:
        raise ValueError('7-Zip did not return an archive member listing')
    header, body = listing.split('\n----------\n', 1)
    archive_type = next((line[7:] for line in header.splitlines() if line.startswith('Type = ')), 'unknown')
    # A PE installer can contain an embedded NSIS archive. The inner archive
    # type is more useful than the outer executable wrapper.
    if 'Type = Nsis' in header:
        archive_type = 'NSIS installer'
    entries = []
    for block in body.strip().split('\n\n'):
        fields = dict(line.split(' = ', 1) for line in block.splitlines() if ' = ' in line)
        name = fields.get('Path')
        if not name:
            continue
        size = fields.get('Size', '')
        entries.append({'name': name, 'size_bytes': int(size) if size.isdecimal() else None,
                        'encrypted': fields.get('Encrypted') == '+'})
    if not entries:
        raise ValueError('Archive contains no listed members')
    return archive_type, entries


def inspect_map(path: Path) -> dict:
    path = path.expanduser().resolve(strict=True)
    if not path.is_file():
        raise ValueError('Select a regular local file')
    suffix = path.suffix.lower()
    if suffix not in ARCHIVE_SUFFIXES | {'.img'}:
        raise ValueError('Map inspection accepts .img, .7z, .zip, or .exe files')
    size = path.stat().st_size
    if size == 0:
        raise ValueError('File is empty')

    if suffix == '.img':
        with path.open('rb') as source:
            header = source.read(512)
        if len(header) < 128 or header[0x10:0x16] != b'DSKIMG' or header[0x41:0x47] != b'GARMIN':
            raise ValueError('File lacks a recognized Garmin IMG header')
        label = header[0x49:0x5D].decode('latin-1').strip(' \x00')
        return {'path': str(path), 'kind': 'garmin_img', 'size_bytes': size,
                'sha256': _sha256(path), 'header_label': label,
                'fits_fat32_single_file': size <= FAT32_MAX_FILE_BYTES,
                'note': 'Recognized header and identifying checksum only; map coverage and device compatibility are unverified.'}

    seven_zip = shutil.which('7z')
    if seven_zip is None:
        raise ValueError('Install 7-Zip (7z) to inspect map archives')
    try:
        result = subprocess.run([seven_zip, 'l', '-slt', str(path)], capture_output=True,
                                text=True, timeout=120, check=True)
    except subprocess.TimeoutExpired as exc:
        raise ValueError('7-Zip listing timed out') from exc
    except subprocess.CalledProcessError as exc:
        raise ValueError(f'7-Zip could not list this archive: {exc.stderr.strip()}') from exc
    archive_type, members = _archive_members(result.stdout)
    images = [member for member in members if member['name'].lower().endswith('.img')]
    ready = [member for member in images if Path(member['name']).name.lower() == 'gmapsupp.img']
    numbered = [member for member in images if Path(member['name']).stem.isdecimal()]
    return {'path': str(path), 'kind': 'map_archive', 'archive_type': archive_type,
            'size_bytes': size, 'sha256': _sha256(path), 'member_count': len(members),
            'img_count': len(images), 'numbered_tile_count': len(numbered),
            'ready_gmapsupp_count': len(ready), 'encrypted_member_count': sum(member['encrypted'] for member in members),
            'note': ('Contains a gmapsupp.img candidate; inspect that IMG after extraction before transfer.'
                     if ready else 'No ready gmapsupp.img; numbered IMG tiles need assembly before device transfer.')}
