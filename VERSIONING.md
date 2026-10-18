# Versioning Policy

Everything in this repository is versioned, and the versions are linked so that any production
deployment can be traced back to the exact requirements it satisfies.

## 1. What carries a version

| Artefact | Scheme | Where the version lives | Example |
|---|---|---|---|
| **System release** | SemVer `MAJOR.MINOR.PATCH` | `VERSION`, root `CHANGELOG.md`, `releases/vX.Y.Z/` | 1.0.0 |
| **Service** | SemVer | `services/scheduler-service/VERSION`, `pyproject.toml`, `app/__init__.py`, service `CHANGELOG.md` (CI checks they match) | 1.0.0 |
| **API contract** | URL major (`/v1`) + SemVer document | `04-design/api/scheduler-service/v1/openapi_X.Y.Z.yaml` | openapi_1.0.0.yaml |
| **Event schemas** | Integer per event | `04-design/events/<event>/vN.schema.json` | appointment.confirmed/v1 |
| **Database schema** | Flyway `V<NNN>` | `services/scheduler-service/migrations/` | V001 |
| **Baselined documents** | `MAJOR.MINOR` in the file name + full SemVer in the header | `*_vX.Y.md` | requirements_v1.0.md (1.0.0) |
| **ADRs** | Immutable, superseded by a new ADR | `03-architecture/adr/ADR-NNN_*.md` | ADR-002 |
| **AI prompts** | SemVer per prompt | `00-ai-instructions/prompts/` | phase-prompts_v1.0.0.md |
| **Container image** | Immutable git-SHA tag (SemVer tag added once per release), deployed **by digest** | Amazon ECR `unified-service-scheduler/scheduler-service` (ADR-008) | `<account>.dkr.ecr.ap-south-1.amazonaws.com/unified-service-scheduler/scheduler-service@sha256:…` |

## 2. Bump rules

| Change | Service | API contract | System release |
|---|---|---|---|
| Bug fix, no behaviour change at the interface | PATCH | — | PATCH |
| New optional field or endpoint; new FR within the same contract | MINOR | MINOR (new `openapi_1.(x+1).0.yaml`) | MINOR |
| Removed or renamed field, changed semantics, new required input | MAJOR | MAJOR (`/v2`, migration guide, `DEPRECATIONS.md`) | MAJOR |
| Docs-only clarification of a baselined doc | — | — | — (doc header PATCH, same file) |
| Requirement added, changed or removed (via CR) | — | — | new doc `_vX.(Y+1).md` |

## 3. API compatibility
- `/v1` is supported until `/v2` has been generally available for at least 6 months.
- Deprecated operations send `Deprecation` and `Sunset` headers and are listed in `DEPRECATIONS.md`.
- The contract test (`tests/contract/`) pins the implementation to the current contract file.

## 4. Documents
- A **baselined** document (status Baselined or Released) is never edited in place except for
  typo-level PATCH changes. Content changes create a new file (`requirements_v1.1.md`), and the old
  file stays for audit. CI (`docs-version-check.yml`) enforces this on files contained in a release tag.
- Every document has a header table (ID, version, status, date) and a revision-history table.
- Each phase folder keeps its own `CHANGELOG.md` (Keep a Changelog format).

## 5. Database
- Forward-only and **expand/contract**: (1) add new nullable columns or tables and deploy code that
  writes both; (2) backfill; (3) switch reads; (4) drop the old shape in a later release.
  The previous image must always run against the new schema (rollback safety, NFR-11).

## 6. Release record
Each release has `releases/vX.Y.Z/` with:
- `RELEASE-NOTES.md`
- `release-manifest.yaml`, which pins the versions of every artefact above
- `approvals.md`
- `test-evidence.md`

Git tags: `vX.Y.Z` (system), `scheduler-service-vX.Y.Z`, `requirements-vX.Y`.
