# Changelog — 03-architecture

## [1.1.0] — 2026-10-17
### Added
- `system-design_v1.0.md` (USS-SDD-001): consolidated system design document covering requirements summary, capacity, architecture, component, data and interface design, allocation and concurrency design, NFR design, deployment, ADR trade-offs, the **architectural plan** (phased evolution, cut-over strategy), risks and open issues. All 8 Mermaid diagrams were render-checked with mermaid-cli.
- ADR-007 Day-0 infrastructure automation (Terraform modules, cluster add-ons with opt-out, DB role bootstrap, infra pipeline).
- ADR-008 Amazon ECR as container registry.
### Changed
- ADR-006 status: registry choice amended by ADR-008.
- `architecture_v1.1.md` (new version; v1.0 marked superseded): §6 deployment view uses **Amazon ECR** instead of GHCR and gains Registry and Infrastructure rows. The container view adds ECR and GitHub Actions; `diagrams/c4-container_v1.1.mmd` is added.

## [1.0.0] — 2026-10-15
### Added
- `architecture_v1.0.md` (C4 context, containers, components, deployment, cross-cutting concerns).
- ADR-001..ADR-006 and `adr/index.md`.
- `diagrams/c4-context_v1.0.mmd`, `diagrams/c4-container_v1.0.mmd`.
