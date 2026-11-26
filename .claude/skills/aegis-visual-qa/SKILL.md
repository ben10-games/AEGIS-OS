---
name: aegis-visual-qa
description: Use when checking how the AEGIS OS desktop actually looks and behaves - running the graphical image in a VM, taking and inspecting screenshots, testing keyboard and pointer interaction, and measuring resource use. Do not report a visual result without having rendered and looked at it.
---

# AEGIS visual QA

## Where the GUI is rendered

The `gui` job of `.github/workflows/build.yml` boots the sealed `aegis-gui` image under
Secure Boot (`make image-gui disk-gui gui-test`). The harness (`tests/vm/harness/qemu.py`)
provides `screenshot()`, `send_keys()`, `type_text()` and `click()` through QMP.

## Getting the screenshots

Artifacts cannot be downloaded from a Claude cloud session, so `scripts/summarize-gui`
prints each screenshot, half size, as base64 into the job log. Recover one:

```bash
gh api repos/ben10-games/AEGIS-OS/actions/jobs/JOB_ID/logs | cut -c30- > gui.log
sed -n '/^AEGIS-SCREENSHOT BEGIN desktop$/,/^AEGIS-SCREENSHOT END/p' gui.log | sed '1d;$d' | base64 -d > desktop.png
```

Then open the PNG and look at it. Check: wallpaper and colours as designed, panel
position and contents, text legible and not clipped, no error dialogs, no black screen.

## Interaction checks

Prefer assertions the system itself can confirm (a typed command creates a file; a
process starts and stays alive) over pixel comparisons. Use pixel differences only to
prove that something changed on screen.

## Resource use

`gui-resources.txt` in the log directory: memory in use, process counts, startup time.
Compare with the previous run in `PROJECT_STATE.md` and report regressions.
