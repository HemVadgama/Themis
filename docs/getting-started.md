# Getting started

## Install

Use Python 3.11 or 3.12 from the repository root:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install ".[dev]"
```

The core closed-loop testbed has no third-party runtime dependency. From a package index use `pip install themis-testbed`; use `pip install "themis-testbed[viewer]"` when declaring viewer use explicitly. The current viewer extra adds no dependency because its server is standard-library-only. Install the optional TLE propagation stack with `python -m pip install ".[dev,orbit]"` if you want to run `src.propagation` or the legacy TLE experiment. TLE access is local by default; a network refresh requires `--refresh-tle`, and the demo reports the exact input hash.

## Run and inspect

```bash
themis --help
themis run --help
themis run examples/basic.toml
```

Copy the printed artifact path. `summary.json` is the quickest machine-readable answer, `metrics.csv` imports directly into analysis tools, and `events.jsonl` explains the lifecycle in order. Inspect it with `themis replay results/<run-id>`.

Open the same artifacts in the local visual debugger:

```bash
themis view results/<run-id>
```

The [viewer guide](viewer.md) explains timeline navigation, agent-local knowledge, communication events, comparisons, and sweep exploration.

For a quantitative sweep, include repeated seeds and run `themis analyze results/<name>-sweep`. Read the [researcher guide](researcher-guide.md) and [methodology](methodology.md) before interpreting intervals.

## Modify and reproduce

Copy the example, change one parameter, and run the copy. Output paths are relative to that configuration file. Each run saves the fully resolved config; rerunning that saved file reproduces model-derived results when the seed and software version match.

For installation or modeling problems, use the repository issue tracker and the [feedback template](../.github/ISSUE_TEMPLATE/feedback.yml). Include the resolved config, version, expected result, actual result, and whether the concern is about installation, a model assumption, a protocol, a metric, or a scenario need.
