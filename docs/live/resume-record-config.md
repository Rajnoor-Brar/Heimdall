---
id: live-resume-record-config
summary: a paused run resumes with the latest attempted Run's recorded config snapshot
affects: live-runs
---

**Now holds:** `heimdall runs --resume` reads the latest attempted Run's `config/snapshot.toml` and copied errand file, setting that record's `config/` as the config root. It does not use the saved command's old config path or the live `configs/` copy.

**No longer holds:** the saved command's original config path is the source of configuration on resume.

**Decisions:** **V235** Use the last record path in the paused job's registry entry. If its snapshot or required config file is missing or unreadable, refuse the resume rather than fall back to live configuration. Keep the saved command's configuration selector and other options.

**Stable pages need:** `internals/live-runs.md`.

**Change log:** `cli.resume_run` replaces the saved config argument with the snapshot's config name and passes its config root to the detached worker. `resume_snapshot` reads the latest recorded folder directly so invoking `runs --resume` from another work dir does not select a different records root. The live-run tests cover choosing the latest of multiple snapshots, distinguishing it from an existing live config, and refusing a missing snapshot. The first test run exposed that the temporary work dir lacked its required `heimdall.toml` marker; the fixture now creates it, and all 16 live-run tests pass. These changes ensure a resume uses the paused run's inputs and cannot silently continue with edited live configuration.
