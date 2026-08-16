# Security policy

Themis is research software and must not control spacecraft or other safety-critical systems. Supported security fixes target the latest release line.

Do not open a public issue for a vulnerability that could put users at risk. Contact the repository owner privately through GitHub. Include affected version, reproduction steps, impact, and any suggested mitigation. Avoid accessing data or systems beyond what is necessary to demonstrate the issue.

External protocol entry points execute installed third-party Python code. Installing such a distribution is a trust decision; configuration files themselves cannot specify arbitrary import paths. The viewer binds to loopback by default and reads completed artifacts, but untrusted artifacts should still be treated as untrusted data.
