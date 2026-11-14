# Security Policy

## Supported version

Security fixes target the latest commit on `main` during the hackathon.

## Reporting

Do not open a public issue containing a credential, licensed dataset, personal owner information, or exploitable vulnerability. Contact the repository owner privately through GitHub instead and include only the minimum information needed to reproduce the problem.

## Data handling

- Sponsor credentials belong only in the ignored local `.env` file.
- Licensed CoStar extracts and cached sponsor responses must remain under ignored `work/`, `cache/`, or local data directories.
- Individual owner names and raw associate IDs must not enter application-facing ownership artifacts.
- Synthetic fixtures must be visibly labeled as synthetic.
- Rotate any credential that appears in chat, logs, screenshots, commit history, or a public artifact.

CI scans tracked text files for common token formats and non-placeholder credential assignments. This check reduces risk but does not replace provider-side secret scanning or credential rotation.
