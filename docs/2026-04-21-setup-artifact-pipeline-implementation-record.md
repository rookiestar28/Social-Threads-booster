# Setup Artifact Pipeline Implementation Record

> Date: 2026-04-21
> Backlog item: AKR-005

## What Changed

- Added `scripts/run_setup_artifacts.py` as a single deterministic setup entrypoint.
- Reused existing local render/build functions instead of shelling out to nested subprocesses.
- Added `tests/test_run_setup_artifacts.py` to pin the bundle contract:
  - default run creates `style_guide.md`, `concept_library.md`, and companion markdown files
  - `brand_voice.md` is created only when `--include-brand-voice` is enabled
- Updated `skills/setup/SKILL.md` so `/setup` prefers the combined pipeline when available.
- Updated `knowledge/_shared/discovery.md` so the setup bundle script is discoverable.
- Updated `tests/E2E_TESTING_SOP.md` to include the current deterministic script matrix, including the setup bundle lane.
- Updated `docs/roadmap.md` to mark AKR-005 complete.

## Why Changed

- `/setup` previously required the agent to stitch together multiple artifact-generation steps manually.
- That manual sequencing created avoidable drift risk in file ordering, optional `brand_voice.md` handling, and companion-file regeneration.
- The new entrypoint provides one stable local command for the artifact chain that already existed conceptually in the skill spec.

## Full Verification Evidence

- Date: 2026-04-21
- Environment: Windows PowerShell, Python `3.13.9`
- Command log reference: inline command list below

### Pre-fix Reproduction Evidence

```powershell
python -m unittest tests.test_run_setup_artifacts
```

- Result: failed before implementation because `scripts/run_setup_artifacts.py` did not exist.

### Post-fix Targeted Regression Evidence

```powershell
python -m unittest tests.test_run_setup_artifacts
```

- Result: passed (`2` tests, `0` failures).

### Final Full-Gate Evidence

```powershell
Get-Command pre-commit | Select-Object -ExpandProperty Source
python -m unittest discover -s tests -p "test_*.py"
python scripts/generate_style_guide.py --tracker examples\tracker-example.json --output .tmp\style_guide-e2e.md
python scripts/generate_concept_library.py --tracker examples\tracker-example.json --output .tmp\concept_library-e2e.md
python scripts/generate_brand_voice.py --tracker examples\tracker-example.json --output .tmp\brand_voice-e2e.md
python scripts/render_companions.py --tracker examples\tracker-example.json --output-dir .tmp\companions --lang en
python scripts/run_setup_artifacts.py --tracker examples\tracker-example.json --output-dir .tmp\setup-artifacts --include-brand-voice
Copy-Item examples\tracker-example.json .tmp\tracker-topic-freshness.json -Force
python scripts/update_topic_freshness.py --tracker .tmp\tracker-topic-freshness.json
```

- `pre-commit` availability check: unavailable in the current environment, so the hygiene lane could not be executed locally.
- Python regression sweep: passed (`5` tests, `0` failures).
- CLI E2E:
  - `generate_style_guide.py`: passed
  - `generate_concept_library.py`: passed
  - `generate_brand_voice.py`: passed
  - `render_companions.py`: passed
  - `run_setup_artifacts.py`: passed
  - `update_topic_freshness.py`: passed on a workspace-local tracker copy

## Known Limitations

- The pipeline assumes the tracker is already in the current list-based schema; legacy migration remains separate work.
- `brand_voice.md` is still opt-in rather than always generated, which matches the current skill requirement but not every future setup workflow.
- The local environment still lacks `pre-commit`, so acceptance evidence records that gate as unavailable rather than green.

## Follow-up Items

- AKR-006 will be the next chain item and should extract shared tracker IO / backup behavior now that setup orchestration exists.
