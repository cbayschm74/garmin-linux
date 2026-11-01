# Portable source release

The alpha is a versioned source archive for a writable user-owned installation.
Use the same shared application on Kubuntu and Omarchy; the GUI selects Omarchy
colors automatically and otherwise follows the native Qt palette. No OS libraries
or prebuilt venv are bundled. A source archive is not a distro package or wheel.

## Build from a Git checkout

    mkdir -p /path/to/output
    /usr/bin/python3 tools/build-release.py --output-dir /path/to/output

The builder reads committed Git objects, not uncommitted/untracked files. Commit
the intended source first. VERSION is canonical; runtime --version reads it.
The manifest pins the full source commit and hashes all packaged files. Adjacent
.tar.gz.sha256 records the archive digest. Same commit/version and Python gzip
implementation produce identical bytes; output filenames are never overwritten.

An explicit --ref selects an older source snapshot. --version is useful only for
a snapshot lacking VERSION, and cannot contradict a tracked VERSION file. An
older snapshot given a packaging label is a validation baseline, not evidence of
a previously published release.

## Install

Install matching distro Python/PyQt6 and UDisks first: see [Linux setup](linux-setup.md).
The tested hosts use system Python, not mise Python. Verify the archive checksum
with sha256sum -c beside the downloaded archive, then extract into a writable
location you intend to keep, such as ~/Applications/garmin-linux-0.1.0a1.

From the extracted directory:

    /usr/bin/python3 tools/setup-linux.py install
    .venv/bin/python tools/setup-linux.py check
    .venv/bin/python -m garmin_companion --version

Installation creates .venv there and fetches pinned FIT SDK requirements from
PyPI; no offline-install claim. It writes three managed files under ~/.local.
The source tree and .venv remain needed by the launcher. Existing unmanaged or
symlink launcher targets are refused. A mismatched base Python is refused before
creating a fresh venv; existing environments are not automatically deleted.

## Upgrade and rollback

Keep the prior working tree and its venv. Extract the candidate beside it and run
the candidate's setup helper with the same prefix. This repoints the managed
launcher, desktop entry and icon to the candidate. After confirming it works,
you may retire an unreferenced old tree. Rollback means running the old tree's
install again; it repoints those same files to the old tree.

On Omarchy regenerate the widget's command settings from the selected tree and
refresh, using [the widget guide](omarchy-widget.md). Those paths are absolute;
the setup helper deliberately does not edit live shell configuration. Check both
the status interpreter/working directory and click launcher after moving trees.

## Uninstall

    /usr/bin/python3 tools/setup-linux.py uninstall

This removes only the three managed launcher files. It preserves source, venv,
backups and cache. Disable an unwanted Omarchy widget separately:

    omarchy plugin disable org.garminlinux.status

Widget folder removal is separately ownership-checked in the widget guide.
A desktop-database updater error can occur after files have changed (documented
G015 F3); inspect state rather than assuming rollback.

## Validate in isolation

From a trusted checkout with the validation tool:

    /usr/bin/python3 tools/validate-install.py --archive /path/to/candidate.tar.gz --artifacts /tmp/new-validation-directory --previous-archive /path/to/baseline.tar.gz

Archive layout, links/traversal/duplicates, sidecar and all file digests are
checked before any archive code is executed. Checksums establish integrity, not
authorship: execute only locally built or otherwise trusted source. The validator
uses new artifact-local exports, HOME/XDG roots, venvs and prefix; it never changes
the live launcher/widget or opens Garmin data. It runs actual system-Python venv,
pip and setup processes, verifies launcher pinning and synthetic sentinel
preservation, and leaves extracted trees/logs/summary.json for inspection. It
does not launch the normal GUI, exercise devices or prove a clean OS install.

The real lifecycle acceptance result will be recorded after the coordinator run.
No release tag, marketplace submission or public publication is part of building
this local candidate.
