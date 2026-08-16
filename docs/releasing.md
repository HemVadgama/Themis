# Release and archival checklist

1. Run the full Python and JavaScript test suites and build a wheel/sdist in a clean environment.
2. Install the wheel without extras and verify run, validate, replay, analyze, and programmatic artifact access. Verify the viewer separately through `[viewer]`.
3. Update version, changelog, `CITATION.cff`, schemas, compatibility notes, and screenshots when behavior changes.
4. Tag the exact tested commit and publish matching GitHub and package releases.
5. Connect the repository to Zenodo and archive the GitHub release. Zenodo's [GitHub integration](https://support.zenodo.org/help/en-gb/24-github-integration) creates a new deposit for enabled releases.
6. Replace the placeholder citation/Zenodo DOI only after the deposit exists; verify that the DOI resolves to the tagged source.
7. Preserve old schema documentation and include migrations for breaking public-contract changes.

No DOI is currently asserted by this repository.
