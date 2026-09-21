# ClauseGuard

AI-assisted first-pass compliance/risk analysis for German contracts.

> **ClauseGuard provides AI-assisted first-pass compliance analysis and does
> not constitute legal advice.** It does not determine whether a contract is
> legally valid. Full documentation is being built up milestone by milestone
> as the system is implemented — see below for current status.

## Status

Build in progress. See commit history / project memory for milestone-by-milestone progress.

- [x] Milestone 1 — Repository architecture, configuration, Docker, FastAPI skeleton
- [ ] Milestone 2 — PDF/DOCX ingestion + clause segmentation
- [ ] Milestone 3 — Clause classification baseline
- [ ] Milestone 4 — LoRA fine-tuning pipeline
- [ ] Milestone 5 — Legal corpus ingestion
- [ ] Milestone 6 — Dense + BM25 + RRF retrieval
- [ ] Milestone 7 — Cross-encoder reranking
- [ ] Milestone 8 — Evidence sufficiency + citation verification
- [ ] Milestone 9 — LLM structured reasoning
- [ ] Milestone 10 — End-to-end pipeline
- [ ] Milestone 11 — Evaluation suite
- [ ] Milestone 12 — Frontend
- [ ] Milestone 13 — PDF report
- [ ] Milestone 14 — Security hardening
- [ ] Milestone 15 — CI/CD + documentation

## Quickstart (current: backend skeleton only)

```bash
cp .env.example .env
docker compose up -d --build
curl http://localhost:8004/health
```

Host ports are deliberately non-default (5436 Postgres, 6339/6340 Qdrant, 6383 Redis,
8004 backend) to avoid clashing with other projects' containers on the same machine.
Container-to-container traffic uses the standard ports internally.

## Legal scope

Deliberately constrained. Not yet ingested — will be documented and expanded in Milestone 5.
Planned initial scope: BGB §§ 305–310 (AGB / standard terms), liability, termination,
payment terms, confidentiality, data-processing clauses, GDPR/DSGVO-related provisions.

## Privacy

Contract text is never sent to an external LLM API unless `LLM_PROVIDER=anthropic` and
`ANTHROPIC_API_KEY` are explicitly set. With no key configured, the reasoning stage
reports itself as `NOT_CONFIGURED` rather than fabricating output.
