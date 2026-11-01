# Move the project to the Omarchy laptop

Transfer a Git bundle made from the primary checkout's `main` branch. It carries committed source, assets, documentation and history; it does not carry worktrees, running agent sessions, the virtual environment, or untracked local configuration. Backups and downloaded maps live separately and are not needed for the initial host validation.

1. Copy the prepared `garmin-linux.bundle` to the laptop's `~/Downloads` using a USB drive or your preferred file-transfer method.
2. On the laptop, create a fresh checkout (the destination must not already contain another project):

   ```sh
   git clone -b main ~/Downloads/garmin-linux.bundle ~/garmin-linux
   cd ~/garmin-linux
   ```

3. Open that folder in Codex or Orca and give the agent this handoff:

   > Continue the Garmin Linux project from ~/garmin-linux/STATUS.md on this Omarchy laptop. Work on G004 in tasks/G004-omarchy-validation.md. Verify the actual OS, Omarchy and shell versions, check Python/Qt and mount-tool dependencies, recreate the project virtual environment using tools/setup-linux.py, run the full synthetic suite, and perform an unplugged GUI smoke check with temporary data roots. Follow AGENTS.md. Update the task card and status. Do not connect to Garmin accounts, write device files, or install a shell plugin during this initial validation.

The setup helper's `check` command can run before installation; a missing `.venv` is expected on a fresh clone. The agent should inspect the actual host and prerequisites before running `install`. The Python environment and launcher are created on the laptop; copying the PC's `.venv` would retain machine-specific paths and dependencies.

Git will initially call the local bundle `origin`. It is a transfer snapshot, not a shared server. Do not use `git pull` expecting updates from the PC. Keep this laptop's validation work committed, then arrange a separate bundle or shared Git remote for later synchronization. Orca's local agent sessions and settings are configured separately on each machine.

After host validation, course/device checks and the Omarchy bar integration can be scheduled separately. Copy selected private backups or map builds only when those tests need them.
