# G013 — Map editor contrast and planning/install feedback

- State: done
- Owner: Codex coordinator, primary checkout/main; base `21ed40d`
- Scope: GUI destination editor, optional map planning/install/resume progress callbacks, shared progress event helper, focused synthetic tests, coordinator handoff docs.
- Trigger: user completed G008 and reported dark-on-dark destination editing and no measurable planning/replacement progress.

Destination editing now uses explicit readable foreground/background and selection colors, including the Qt editor child. Byte callbacks report backup, current device and source hashing, copy, readback and repeated validation. Progress shows percentage of the current file, filename, bytes, phase speed and elapsed time; separate flush/removal/unmount stages remain indeterminate with explicit labels. Repeated checks reset the current-file percentage; no overall estimate is invented. Safety checks, verification passes, write ordering and resume state schema remain intact. Existing callers can omit callbacks.

Verification: 222 unittest methods pass with mocked USB and temporary storage; compileall and diff checks pass. Added full progress-enabled real planner/installer round trip, failed readback preserving old map and resumable state, GUI progress/busy transitions and dark-palette live editor checks. Synthetic editor screenshot visually inspected. Physical acceptance of the preceding installer version belongs to G008; this change does not claim another hardware run.

No physical storage opened or operation left running. User-owned untracked `mise.toml` preserved. Next: reopen the normal main-checkout app to use the feedback improvements; proceed with another project task without rewriting maps merely for UI acceptance.
