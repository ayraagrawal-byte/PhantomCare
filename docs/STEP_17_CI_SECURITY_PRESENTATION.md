# Step 17 - CI, Security, and Presentation Readiness

Date: 2026-11-14

GitHub Actions now verifies Python lint, all tests, the offline evaluation, dashboard tests, ESLint, and the production Next.js build on pushes and pull requests. Dependabot checks Python, npm, and GitHub Actions dependencies weekly.

The repository-native secret scanner checks tracked text files for common provider token formats, private keys, JWTs, and non-placeholder credential assignments without printing candidate values. `SECURITY.md` documents private reporting and sponsor-data handling.

The architecture guide and presentation runbook provide the system flow, a key-free demo command, a five-minute judging narrative, and a pre-demo fallback checklist.
