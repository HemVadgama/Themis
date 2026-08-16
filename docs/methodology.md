# Methodology and reporting checklist

## Experimental unit and determinism

A run is identified by the resolved configuration, protocol, seed, and software behavior. The deterministic run ID excludes the output path. Model-derived values repeat for the same resolved config, seed, and Themis version subject to the floating-point caveat in [limitations](assumptions-and-limitations.md). Timestamp, runtime, path, and git discovery are observational.

For stochastic experiments, the seed—not an event, message, or agent—is the replicate unit. Compare protocols over the same seed set when possible. A single seed is a traceable case study, not an estimate of variability.

## Built-in statistical summary

`themis analyze` groups successful sweep rows by condition and reports `n`, distinct seed count, mean, sample standard deviation, standard error, and a two-sided 95% Student-t confidence interval. For sample mean \(\bar{x}\), sample standard deviation \(s\), and \(n\) runs, it reports:

```text
mean ± t(0.975, n - 1) × s / sqrt(n)
```

The implementation uses published 95% t critical values through 30 degrees of freedom and 1.96 above that. This interval assumes independent replicate seeds, an appropriate mean estimand, and an approximately normal sampling distribution for small samples. It is not a multiple-comparison correction, hypothesis test, causal estimator, or guarantee of generalization. The [SciPy bootstrap API](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html) is a useful external option when a justified resampling analysis is needed; save that analysis code beside the artifacts.

## Reporting checklist

- Themis package version and git commit, if present
- benchmark ID and scenario preset
- full resolved config and source-data versions
- protocol package names and versions
- seed selection rule and number of seeds per condition
- all excluded or failed runs and reasons
- metric definitions, units, and whether each is a proxy
- interval/estimator assumptions and any multiple-comparison handling
- relevant limitations and threats to validity
- archive DOI or permanent artifact location, once available

Avoid phrases such as “safer,” “optimal,” or “reduces collision risk” unless the study supplies a validated operational mapping beyond the current benchmark. Prefer precise statements such as “reduced unresolved threshold events in this configuration grid.”
