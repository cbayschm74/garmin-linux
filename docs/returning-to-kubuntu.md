# Return the Omarchy work to Kubuntu by USB

Copy/extract the pack onto the recipient disk before installing or cloning;
launchers must not be pinned to paths on the removable USB stick.

The USB pack contains a complete main-only Git bundle and pinned source release
artifacts. It includes committed project source/docs/history, not user data,
installed environments, user settings or agent sessions. A bundle is a snapshot,
not a shared remote. Existing Kubuntu work must be inspected before integration.

The alpha archive is frozen at source commit
3957c0c918a0cb9491405bf13adfcf4493f2fd84, version 0.1.0a1. The main handoff commit
is newer because it includes evidence/task documentation and the user's actual
theme-switch acceptance. The external HANDOFF.json records both exact pins.

## Verify the pack

Unzip the pack into a new directory on the recipient disk. From that directory:

    sha256sum -c SHA256SUMS
    git bundle list-heads garmin-linux.bundle

The bundle advertises only refs/heads/main and carries its complete reachable
history. It requires no older local bundle. Check the advertised full SHA against
HANDOFF.json. Bundle verification needs a Git repository: run git bundle verify with the absolute
bundle path from inside the existing recipient checkout. A fresh clone also
validates the complete bundle before using its contents.

## Existing Kubuntu checkout

First check pwd, git status --short, git branch --show-current and git worktree
list, then read its local STATUS.md/AGENTS.md/task board. Preserve uncommitted work
and other agents' worktrees; never reset/clean/overwrite them for this transfer.

Verify and fetch the USB bundle to a new review ref, substituting its actual path:

    git bundle verify /path/to/unpacked/garmin-linux.bundle

    git fetch /path/to/unpacked/garmin-linux.bundle main:refs/remotes/omarchy-usb/main
    git log --left-right --oneline HEAD...omarchy-usb/main
    git diff --stat HEAD...omarchy-usb/main
    git merge-base --is-ancestor HEAD omarchy-usb/main

Only if the current clean branch is the intended recipient main and it is an
ancestor, integrate with:

    git merge --ff-only omarchy-usb/main

If histories diverge, have the Kubuntu coordinator create an integration branch
from its own main, review both sides and merge/resolve there. Preserve all local
branches/commits/worktrees. Do not blindly cherry-pick the whole return history.
If the review ref already exists from an earlier transfer, use a new unique ref
rather than force-updating it. An existing bundle origin remains a static path.

## Fresh checkout

Only when the target path is unused:

    git clone -b main /path/to/unpacked/garmin-linux.bundle ~/garmin-linux-omarchy-return

Open that folder as the coordinator. Recreate the environment with matching
system Python; don't copy the laptop venv:

    /usr/bin/python3 -m venv --system-site-packages .venv
    .venv/bin/python -m pip install -r requirements.txt
    .venv/bin/python tools/setup-linux.py check
    QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -q
    .venv/bin/python -m compileall -q garmin_companion tests tools
    git diff --check

Missing PyQt6/FIT dependencies are environment failures. This validation does
not register a launcher. Native and lifecycle checks use temporary prefixes and
data via the documented harnesses, not the normal GUI against personal backups.

## Recipient assignment

Claim G028 in tasks/G028-kubuntu-release-validation.md as Kubuntu coordinator.
Use KUBUNTU-AGENT-PROMPT.txt from the pack as the copyable resume prompt.

Required checks: full suite, native Qt/KDE light/dark readability, matching
launcher/window identity, isolated alpha install/reinstall/upgrade/rollback/
uninstall and native temporary-data GUI. Actual desktop theme changes/taskbar
pinning may need user observation. Device writes and marketplace publication
are outside this assignment. Keep real backups/maps outside Git and prompts.
