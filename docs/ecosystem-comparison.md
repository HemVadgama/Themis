# Ecosystem comparison and positioning

Themis should complement established simulation ecosystems instead of imitating their breadth.

| Project/practice | Established strength | What Themis should learn | Themis focus today |
|---|---|---|---|
| [Gymnasium custom environments](https://gymnasium.farama.org/main/tutorials/environment_creation/) | A small environment interface and versioned registration make independently packaged environments composable. | Keep extension points narrow, discoverable, and versioned. | Installed protocol entry points plus a strict experiment configuration. |
| [PettingZoo Parallel API](https://pettingzoo.farama.org/main/api/parallel/) | A common multi-agent interaction API and conformance tests support diverse environments and algorithms. | Add formal protocol/benchmark conformance suites before claiming broad interoperability. | Information-restricted protocol contexts inside one benchmark family. |
| [Mesa](https://mesa.readthedocs.io/stable/) | General agent-based modeling components, analysis, examples, and browser visualization. | Grow reusable components and examples from real studies. | Causal coordination traces, independent action validation, and completed-artifact inspection. |
| [ns-3](https://www.nsnam.org/docs/manual/singlehtml/index.html) | Mature discrete-event networking and controlled random streams/substreams. | Make stochastic streams and network-model scope increasingly explicit. | Seeded loss/latency and protocol effects, not packet-level network simulation. |
| [JSON Schema](https://json-schema.org/specification) | Machine-readable validation and interoperable data contracts. | Publish schemas and compatibility rules with artifacts. | Packaged Draft 2020-12 core schemas. |
| [FAIR for Research Software](https://www.researchsoft.org/blog/2022-08/) | Findability, accessibility, interoperability, and reuse principles for research software. | Attach persistent identifiers, rich metadata, and reusable interfaces to releases. | Version/provenance metadata, citation file, schemas, open license; DOI activation remains outstanding. |
| [JOSS review criteria](https://joss.readthedocs.io/en/latest/review_criteria.html) | Research software review expects a statement of need, documentation, tests, contribution guidance, and research impact. | Build adoption evidence and validation studies toward a future submission. | The current engineering foundations align with several review criteria. |

## Defensible differentiation

Themis' strongest current angle is an auditable coordination experiment: simulated truth, agent knowledge, communication, protocol rationale, independent validation, execution, resource changes, and reassessed outcome are linked in one generic event contract. Paired run and sweep views are downstream debugging tools for that evidence.

Themis does not yet compete with general ABM frameworks on domain breadth, reinforcement-learning ecosystems on algorithm volume, or network simulators on packet fidelity. It can stand out by preserving causal inspectability as benchmark fidelity and community extensions grow.
