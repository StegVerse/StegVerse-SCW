# StegVerse Risk Register (Living Document)

_Last updated: 2025-10-18_

## Strategic & Adoption
- **Dual-quorum deadlock** → Mitigation: emergency A/B path (no cap growth), timelocks, mediation incentives.
- **Optics in election contexts** → Mitigation: non-partisan charter, identical product SKUs, public receipts.

## Technical & Security
- **Sybil/Identity for AI guardians** → DID policy + attestations + periodic re-verification.
- **Supply-chain churn** → SBOM, Sigstore, SLSA provenance, allow-listed registries, quarantine/rollback.

## Legal & Policy
- **Token classification risk** → Start with closed-loop credits; counsel before public markets.
- **Data protection** → Minimize PII, encrypt in-field, DPAs, incident playbooks.

## Political & Social
- **AI sentiment whiplash** → Emphasize “AI constrained by constitution,” human-only mode available.
- **Capture by wealthy actors** → Public receipts, diversity-by-domain quorum rules.

## Org & Funding
- **Founder bandwidth/health** → Automate CI/test, narrow MVP, add 1 senior generalist, contractor BD.

> Each risk entry should link to a mitigation PR/commit and a monitoring metric where possible.
