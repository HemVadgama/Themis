# Executed smoke study results

The stored aggregate contains 36 successful run-level observations and 0 excluded failures.
Seeds are paired protocol replicates. Each table row reports a mean and two-sided 95% Student-t interval under the assumptions recorded in `analysis/analysis.json`.

`boundary-analysis.json` reports only the first sampled condition crossing a predeclared 0.5 modeled-resolution threshold and condition-specific rankings. It makes no significance or universal-boundary claim.
Observed values are in `summary-table.csv`; causal explanations require inspection of the referenced run traces. The publication profile has not been executed merely because this analysis function exists.

## Observed smoke outcomes

At zero loss/zero latency, centralized and greedy each resolved a mean 1.000 and 1.000 fraction of created modeled risks; auction resolved 0.200.
At loss 0.3/latency 0, the observed means were greedy 0.750, centralized 0.439, and auction 0.067. This is an observed ranking change between centralized and greedy, not a significance result.
With zero loss/latency 1, observed means fell to centralized 0.600, greedy 0.500, and auction 0.200.
The auction's sampled 0.5 failure boundary is already at loss 0 under both latency settings. Trace inspection shows concurrent auction reservations and multi-message deadlines as visible failure modes, but this mechanism is an explanation of these configured traces, not proof of a general auction property.
Three replicates produce wide or degenerate intervals, including bounds outside the feasible [0,1] range because untransformed Student-t intervals were preregistered. The data are underdetermined for significance, fine crossover location, and universal protocol ranking.
