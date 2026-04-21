# AK-Threads-Booster E2E Testing SOP

This SOP defines the repeatable end-to-end validation flow for **AK-Threads-Booster**.

## What Counts As E2E In This Repo

This repository's executable surface is primarily Python CLI scripts.
Accordingly, E2E means:

- invoke the real script entrypoint
- use realistic local fixture input
- verify the output artifact or mutated tracker result
- keep all temporary artifacts inside `.tmp/`

## Script Validation Matrix

### Deterministic local scripts

These should use fixture-based CLI E2E whenever they change:

- `scripts/generate_style_guide.py`
- `scripts/generate_concept_library.py`
- `scripts/generate_brand_voice.py`
- `scripts/run_setup_artifacts.py`
- `scripts/render_companions.py`
- `scripts/update_topic_freshness.py`
- `scripts/parse_export.py` when a suitable local fixture exists

### Credential-dependent scripts

These cannot be validated end-to-end without secrets or a live account:

- `scripts/fetch_threads.py`
- `scripts/update_snapshots.py`

When either script changes, acceptance evidence must include:

- a manual smoke run with valid credentials, or
- an explicit note that credentialed validation was unavailable

## Windows / PowerShell Verified Flow

### 0. Prepare workspace-local temp output

```powershell
New-Item -ItemType Directory -Force .tmp | Out-Null
```

### 1. Style guide generation

```powershell
python scripts/generate_style_guide.py `
  --tracker examples\tracker-example.json `
  --output .tmp\style_guide-e2e.md
```

Expected result:

- exit code `0`
- `.tmp\style_guide-e2e.md` created
- output contains `# Personalized Style Guide`

### 2. Companion rendering

```powershell
python scripts/render_companions.py `
  --tracker examples\tracker-example.json `
  --output-dir .tmp\companions `
  --lang en
```

Expected result:

- exit code `0`
- `.tmp\companions\posts_by_date.md`
- `.tmp\companions\posts_by_topic.md`
- `.tmp\companions\comments.md`

### 3. Concept library generation

```powershell
python scripts/generate_concept_library.py `
  --tracker examples\tracker-example.json `
  --output .tmp\concept_library-e2e.md
```

Expected result:

- exit code `0`
- `.tmp\concept_library-e2e.md` created
- output contains `# Concept Library`

### 4. Brand voice generation

```powershell
python scripts/generate_brand_voice.py `
  --tracker examples\tracker-example.json `
  --output .tmp\brand_voice-e2e.md
```

Expected result:

- exit code `0`
- `.tmp\brand_voice-e2e.md` created
- output contains `# Brand Voice Profile`

### 5. Setup artifact pipeline

```powershell
python scripts/run_setup_artifacts.py `
  --tracker examples\tracker-example.json `
  --output-dir .tmp\setup-artifacts `
  --include-brand-voice
```

Expected result:

- exit code `0`
- `.tmp\setup-artifacts\style_guide.md`
- `.tmp\setup-artifacts\concept_library.md`
- `.tmp\setup-artifacts\brand_voice.md`
- companion markdown files created in the same output directory

### 6. Topic freshness annotation

Use a workspace-local copy because the script mutates the tracker.

```powershell
Copy-Item examples\tracker-example.json .tmp\tracker-topic-freshness.json -Force
python scripts/update_topic_freshness.py --tracker .tmp\tracker-topic-freshness.json
```

Expected result:

- exit code `0`
- `.tmp\tracker-topic-freshness.json` updated in place
- `algorithm_signals.topic_freshness` populated for posts

### 7. Export parsing

Create a minimal JSON export fixture in `.tmp\parse-export-e2e\threads-export.json`, then run:

```powershell
python scripts/parse_export.py `
  --input .tmp\parse-export-e2e\threads-export.json `
  --output .tmp\parse-export-e2e\tracker.json
```

Expected result:

- exit code `0`
- `.tmp\parse-export-e2e\tracker.json` created
- output tracker contains a list-shaped `posts` array

### 8. Headless refresh failure logging

```powershell
python scripts/update_snapshots.py `
  --tracker examples\tracker-example.json `
  --headless `
  --log-file .tmp\threads_refresh.log
```

Expected result:

- exit code is non-zero when no API token is available
- `.tmp\threads_refresh.log` is created
- the appended JSON line contains `ok: false` and a machine-readable `reason`

## Linux / WSL Verified Flow

### 0. Prepare workspace-local temp output

```bash
mkdir -p .tmp
```

### 1. Style guide generation

```bash
python scripts/generate_style_guide.py \
  --tracker examples/tracker-example.json \
  --output .tmp/style_guide-e2e.md
```

### 2. Companion rendering

```bash
python scripts/render_companions.py \
  --tracker examples/tracker-example.json \
  --output-dir .tmp/companions \
  --lang en
```

### 3. Concept library generation

```bash
python scripts/generate_concept_library.py \
  --tracker examples/tracker-example.json \
  --output .tmp/concept_library-e2e.md
```

### 4. Brand voice generation

```bash
python scripts/generate_brand_voice.py \
  --tracker examples/tracker-example.json \
  --output .tmp/brand_voice-e2e.md
```

### 5. Setup artifact pipeline

```bash
python scripts/run_setup_artifacts.py \
  --tracker examples/tracker-example.json \
  --output-dir .tmp/setup-artifacts \
  --include-brand-voice
```

### 6. Topic freshness annotation

```bash
cp examples/tracker-example.json .tmp/tracker-topic-freshness.json
python scripts/update_topic_freshness.py --tracker .tmp/tracker-topic-freshness.json
```

### 7. Export parsing

Create a minimal JSON export fixture in `.tmp/parse-export-e2e/threads-export.json`, then run:

```bash
python scripts/parse_export.py \
  --input .tmp/parse-export-e2e/threads-export.json \
  --output .tmp/parse-export-e2e/tracker.json
```

### 8. Headless refresh failure logging

```bash
python scripts/update_snapshots.py \
  --tracker examples/tracker-example.json \
  --headless \
  --log-file .tmp/threads_refresh.log
```

## Verification Notes

- Read the generated outputs directly when needed to confirm section headers or mutated fields.
- Do not rely only on process exit code when the task changes output content.
- Clean up `.tmp/` outputs when they are no longer needed for evidence.

## Failure Handling

If E2E fails:

1. capture the exact command
2. capture stderr/stdout
3. identify whether the failure is:
   - fixture problem
   - path/encoding problem
   - script regression
   - environment problem
4. fix the root cause
5. rerun the failed lane and any directly dependent lane
