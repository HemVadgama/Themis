# Auction coordination under network faults

## Research question and preregistered hypotheses

How do fixed latency, independent packet loss, per-sender message-count bandwidth, decision deadlines, and modeled system scale affect the safety proxy, efficiency, and reliability of centralized, greedy, and auction-based coordination in `spacecraft-campaign-v1`?

The hypotheses were written before examining the stored smoke output:

1. Auction reliability will degrade earlier than centralized or greedy reliability as loss or latency increases because it needs announcement, bid, and award delivery.
2. When an auction completes, its explicit cost ranking will weakly reduce modeled maneuver cost relative to greedy selection, but the extra messages will increase communication demand.
3. Tighter deadlines and lower bandwidth will interact with latency, producing sampled crossover regions rather than one protocol dominating every condition.
4. Increasing paired agents from 2 to 8 will increase concurrent message demand and make the auction more sensitive to the per-sender message cap.

These are directional hypotheses, not significance claims. The supplied analysis is descriptive and does not implement a hypothesis test.

## Benchmark and model assumptions

The study uses deterministic discrete cycles, exact linear local-frame truth, sampled Euclidean threshold risks, instantaneous velocity-change actions, and a maneuver-resource proxy equal to modeled delta-v magnitude. Network latency is a fixed integer step, loss is seeded independent Bernoulli loss, and bandwidth is a per-sender/per-timestamp message-count cap. None of these values is a collision probability, operational safety estimate, propellant mass, flight maneuver, or packet-level network result.

All three protocols receive the same initial truth for a condition and the same replicate seed. Centralized risk alerts and maneuver directives traverse the configured network. Greedy participants act independently after local alert delivery. Auction participants require announcement, bid, winner selection, and award delivery. Every proposal uses the same independent validator and executor.

## Variables and controls

The smoke profile varies protocol, loss (`0`, `0.3`), latency (`0`, `1`), and three paired seeds. It fixes four agents, bandwidth 8, a six-step deadline, campaign duration, physical state, action bounds, resource budgets, auction weights, and software behavior. Its 36 runs are intended to exercise the complete workflow in CI and reveal gross failures, not estimate a stable publication effect.

The publication profile varies:

| Variable | Values |
|---|---|
| protocol | centralized, greedy, auction |
| packet loss | 0, 0.2, 0.4 |
| latency steps | 0, 1 |
| messages per sender per timestamp | 2, 8 |
| decision deadline steps | 4, 7 |
| agent count | 2, 8 |
| paired replicate seed | 0–4 |

This is 720 short runs. Five seeds per cell are a convenience-bounded pilot sample: enough to expose seed variation and compute an explicitly assumption-limited t interval, but not enough to support strong tail, normality, or significance claims. A larger confirmatory study should justify its effect size and stopping rule before adding seeds. Seeds are replicate units and are never treated as a condition to average indiscriminately.

Dependent variables are modeled risk resolution fraction, unresolved/expired risks, decisions before deadline, deadline misses, validator acceptance/rejection, execution failures, maneuver count and cost proxy, message counts, auction outcomes, bid receipt, per-agent resource use, burden Gini, and wall-clock runtime. Runtime is labeled observational and is not mixed with model outcomes.

For scale conditions other than the four-agent causal reference, agents are initialized as deterministic 30 km paired risks separated by 500 km between pairs. This keeps initial per-pair geometry comparable while increasing concurrent demand. It is a synthetic scale stressor, not a population model.

## Exact reproduction

From a source checkout with the development environment installed:

```bash
python studies/auction-network-faults/study.py all --profile smoke
python studies/auction-network-faults/study.py all --profile publication
```

Runs are resumable by deterministic run ID. Repeating a completed sweep reads each existing summary and does not duplicate a run. To regenerate plots and tables without rerunning simulations:

```bash
python studies/auction-network-faults/study.py analyze --profile smoke
python studies/auction-network-faults/study.py verify --profile smoke
```

Raw run-level rows, runtime/status-free deterministic `model-results.json`, analysis JSON/CSV, separate observational `runtime-scale.csv`, the sampled boundary scan, an SVG plot, and an interpretation note are written beneath `results/<profile>/`. The executed smoke aggregates under `results/smoke/` are tracked as reference evidence. Individual causal traces beneath `results/runs/` are intentionally ignored because they are reproducible from the tracked config and model rows. Inspect a regenerated failed auction with:

```bash
themis replay studies/auction-network-faults/results/runs/<run-id>
themis view studies/auction-network-faults/results/runs/<run-id>
```

## Analysis and failure boundaries

Each condition reports `n`, distinct seed count, mean, sample standard deviation, standard error, and a two-sided 95% Student-t confidence interval. The interval assumes independent seed replicates, a meaningful mean, and an approximately normal sample-mean distribution. There is no multiple-comparison correction, hypothesis test, or statistical-significance label.

`boundary-analysis.json` finds the first sampled loss level where mean modeled resolution falls below 0.5 for each protocol/latency series and lists condition-specific rankings. It is a transparent deterministic scan, not an optimizer. A missing crossing means only that this grid did not locate one. Crossover interpretations are underdetermined whenever intervals are wide or the grid is too coarse; inspect the rows rather than inferring equality or significance.

Safety-versus-cost and communication-versus-reliability tradeoffs can be reconstructed by joining condition keys in `summary-table.csv`. Explanations are intentionally not generated from aggregate rank: use event references to inspect alert loss, missing bids, award timeout, safety rejection, resource exhaustion, execution failure, and later secondary-risk creation.

## Threats to validity

- Threshold separation in a linear local frame is not collision probability or orbital safety.
- The four-agent reference contains deliberately constructed later encounters; scale cases use repeated paired geometry and do not represent an operational population.
- Independent Bernoulli loss, fixed latency, and a message-count cap omit topology, routing, correlated blackout, link scheduling, and bytes.
- Centralized and decentralized baselines embody specific information and messaging rules; results do not generalize to every protocol with the same label.
- Auction weights are exposed and fixed, not calibrated from mission evidence. Alternative weights may change winners.
- Five publication seeds and three smoke seeds give weak uncertainty estimates for bounded/discrete outcomes.
- The boundary scan is limited to sampled loss values and must not be presented as universal.
- Runtime depends on the host and is kept separate from deterministic model outcomes.

The checked-in smoke results are executed evidence. Publication output is deliberately absent until that larger profile is run; no result is fabricated from an unexecuted configuration.
