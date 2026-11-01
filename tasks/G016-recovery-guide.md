# G016 — Recovery and troubleshooting guide

- State: active
- Owner: Grok configured default; coordinator supervises run `run_e413c22b78ee`.
- Base: main claim commit containing this card; record actual worktree/HEAD at startup.
- Allowed files: new `docs/recovery-and-troubleshooting.md`, this card only. Read relevant core/docs as needed; no source edits.

Write a concise operator guide based on actual implemented behavior for USB disconnect during backup/course/map operations; backup verification vs target match; map state preservation and Resume, final unmount retry and sibling volumes; moved checkout/broken launcher; missing Qt/FIT/udisks/7z; slow USB2 vs stalled operation. Cover manual recovery limits: there is no app restore command, no firmware/account automation. Explain when source images and state must be retained, never delete old maps/partials or force unmount as generic advice. Do not offer a blanket automatic restore recipe; preserve backups and use reviewed explicit operations. Distinguish checksum verification, file completion and on-device rendering/navigation. Map planning/install progress is per-file and can reset for repeated hash passes. Read CLI help/source for exact available commands; no hardware scans or private files. Include short generic commands only when genuinely safe; no historic /dev/sdX or identifiers. Kubuntu supported evidence vs Omarchy actual host still pending. Do not browse unless primary documentation is necessary; if browsing use authoritative docs and cite exact sources.

Validate every proposed command against argparse/source or --help (no actual write/mount/scan). Record checks and any uncertain points, commit guide and card, mark review not done. No shared global doc/source edits, no delegate/merge; follow injected Orca lifecycle commands.
