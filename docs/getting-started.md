# Getting started

## Install

Use Python 3.11 or 3.12 from the repository root:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install ".[dev]"
```

The core closed-loop testbed has no third-party runtime dependency. Install the optional TLE propagation stack with `python -m pip install ".[dev,orbit]"` if you want to run `src.propagation` or the legacy TLE experiment. TLE access is local by default; missing or malformed input is reported by the loader.

## Run and inspect

```bash
themis --help
themis run --help
themis run examples/basic.toml
```

Copy the printed artifact path. `summary.json` is the quickest machine-readable answer, `metrics.csv` imports directly into analysis tools, and `events.jsonl` explains the lifecycle in order. Inspect it with `themis replay results/<run-id>`.

## Modify and reproduce

Copy the example, change one parameter, and run the copy. Output paths are relative to that configuration file. Each run saves the fully resolved config; rerunning that saved file reproduces model-derived results when the seed and software version match.

For installation or modeling problems, use the repository issue tracker and the [feedback template](../.github/ISSUE_TEMPLATE/feedback.yml). Include the resolved config, version, expected result, actual result, and whether the concern is about installation, a model assumption, a protocol, a metric, or a scenario need.
