---
name: Testing and Deployment Strategy
description: CI/CD pipeline rules — what runs on PRs vs branch pushes
type: project
---

Every PR (regardless of target branch) must deploy to TEST and run e2e smoke tests before it can be merged. This is a gate, not optional.

Pipeline rules:
- PR (any) → unit tests + deploy to TEST + smoke tests against TEST
- Push to `development` → unit tests + deploy to TEST + smoke tests against TEST
- Push to `main` → unit tests + deploy to PROD + smoke tests against PROD

**Why:** The user explicitly requires e2e validation on every PR, not just after merge.

**How to apply:** In ci.yml, `build-deploy-test` and `smoke-test-test` conditions must be:
`if: github.ref == 'refs/heads/development' || github.event_name == 'pull_request'`

Never use `if: github.ref == 'refs/heads/development'` alone on TEST deploy/smoke jobs — that silently skips PRs.
