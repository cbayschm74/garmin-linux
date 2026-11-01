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

## Local alpha acceptance — 2026-11-01

Built alpha 0.1.0a1 from source commit
3957c0c918a0cb9491405bf13adfcf4493f2fd84, containing 92 allowlisted source files,
including the adaptive GUI theme module and lifecycle validator. Two independent
build directories produced identical archive bytes. Archive SHA-256:

    3a839154dda35ed10beacb60a0b2a4f14030e5dfea7c1a18f478625e49be0d60

Local artifact: ~/Downloads/GarminLinuxReleases/0.1.0a1/garmin-linux-0.1.0a1.tar.gz
with adjacent .sha256. Validation logs and summary:
~/Downloads/GarminLinuxReleases/validation-0.1.0a1/.

Actual system-Python helper/venv/pip lifecycle passed nine steps, zero warnings:
fresh check (expected exit 1), install, ready check, reinstall, earlier-source
baseline install, candidate upgrade, baseline rollback, candidate re-upgrade,
candidate uninstall. Every successful step was exit 0. Managed targets were
removed at the end, unrelated sentinel contents survived, and source trees/venvs
were retained for inspection. Baseline was exported from 0523281 and labeled
0.1.0a0 only for validation; it was never a published release.

Extracted candidate runtime reports 0.1.0a1. Its native Wayland desktop-entry
launch passed all five page/empty-state checks, expected compositor identity
(xwayland=false), clean close, and automatic current Omarchy theme detection
(background #282828). Source suite: 394 tests OK; compilation/diff/setup checks
pass. Primary launcher, desktop entry, icon, plugin source and shell config hashes
match their pre-validation snapshot after all tests. No device or private Garmin
data was accessed during packaging.

This is a fresh source-release install on the already verified Omarchy host,
not a clean OS or native package test. Actual Kubuntu archive install/live theme
retest, offline install and fresh OS acceptance remain open. Documentation after
the frozen source commit records these results; the archive intentionally retains
that exact tested commit rather than silently changing the candidate bytes.
No release tag, marketplace submission or public publication is part of building
this local candidate.
