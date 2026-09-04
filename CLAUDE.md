# certbot-dns-azure-modern

Maintained fork of `terricain/certbot-dns-azure`, published on PyPI as
`certbot-dns-azure-modern`. The Python module (`certbot_dns_azure`), the certbot plugin
name (`dns-azure`), CLI flags and config format are unchanged on purpose: downstream users
(mainly Nginx Proxy Manager) only swap the distribution name.

## Ground rules

- Personal/operational details (Azure ids, private repos, the maintainer's own
  deployment) belong in `CLAUDE.local.md`, which is gitignored. Keep this file generic.

- Everything in this repo is English: code, comments, docs, commit messages, issues.
- Never commit or push without explicit approval from Christoph. Prepare the change,
  show the diff, ask.
- Keep the plugin a drop-in replacement. Do not rename the module or the entry point.
- Keep `certbot` unbounded above (`certbot>=3.0`). An upper cap is exactly what broke
  upstream: pip downgraded certbot/acme inside shared venvs.
- `azure-mgmt-dns` 8.x and 9.x are both supported. Construct `DnsManagementClient` with
  keyword arguments only (`base_url=`, `credential_scopes=`); 9.x dropped the positional
  `api_version` parameter, which is what broke upstream (issues #60, #62).

## Why this fork exists

Upstream 2.6.1 (Dec 2024) pins `certbot<4.0`. In Nginx Proxy Manager 2.15+ the image ships
certbot 5.x with pyOpenSSL 26; installing the plugin downgrades certbot/acme to 3.3.0, and
acme 3.3.0 no longer imports against pyOpenSSL 26
(`AttributeError: module 'OpenSSL.crypto' has no attribute 'X509Extension'`).
Tracking issue: https://github.com/NginxProxyManager/nginx-proxy-manager/issues/5606.
Upstream PR fixing the pin (#65) has been open since Feb 2026 with no maintainer response.
The plugin code itself works unchanged with certbot 5.x; only the pin was the problem.

## Layout

- `certbot_dns_azure/_internal/dns_azure.py` - the plugin (single file, ~370 lines).
- `certbot_dns_azure/__init__.py` - short module docstring pointing at the docs site.
- `docs/*.rst` - user documentation (installation, configuration, authentication, usage,
  DNS delegation, troubleshooting, development); `docs/changelog.rst` includes
  `CHANGELOG.md` via myst-parser. Build with `sphinx-build -W`, warnings are errors.
- `tests/dns_azure_test.py` - unit tests, mock the Azure SDK. Use `_dns01_challenge()` and
  `_domain()` helpers; they hide the certbot 5 `domain=` -> `identifier=` deprecation.
- `azure_tests/integration_test.py` - real certificate issuance (Let's Encrypt staging)
  against dedicated Azure DNS test zones, see "Azure integration tests" below.
- `.github/workflows/release.yml` - test matrix, build, publish on tag via PyPI trusted
  publishing (GitHub environment `pypi`), GitHub release.
- `.github/dependabot.yml` - weekly grouped updates of the GitHub Actions only; the
  Python dependencies stay version ranges and are covered by the weekly workflow run.
- `.github/workflows/docs.yml` - builds the Sphinx docs (`docs/`) and deploys them to
  GitHub Pages (https://cloudchristoph.github.io/certbot-dns-azure-modern/) on push to `main`.
  Pages is configured with source "GitHub Actions"; no Read the Docs project.
- `Docker/` - inherited minimal image, installs from PyPI.

## Working locally

```bash
uv venv --python 3.13 .venv && . .venv/bin/activate
uv pip install certbot 'azure-identity>=1.19.0' 'azure-mgmt-dns>=8.2.0' 'azure-core>=1.32.0' pytest build twine
uv pip install --no-deps -e .
python -m pytest -q tests/ -W error::DeprecationWarning
python -m build && python -m twine check dist/*
uv pip install -r docs/requirements.txt && sphinx-build -W -b html docs docs/_build/html
```

Also test the oldest supported line: `certbot>=3.0,<4.0` together with `pyOpenSSL<26`
(acme 3.x needs it), and `azure-mgmt-dns<9` next to the current 9.x.

Smoke test in the Nginx Proxy Manager image (this is the primary consumer):

```bash
docker run --rm -v "$PWD/dist:/dist:ro" --entrypoint bash jc21/nginx-proxy-manager:2.15.1 -c '
  . /opt/certbot/bin/activate
  pip install --no-cache-dir "certbot-dns-azure-modern~=2.7.0" --find-links /dist
  pip check && certbot --version && certbot plugins --text | grep -A1 dns-azure'
```

Expected: certbot stays at the image version (5.6.0 in 2.15.1), `pip check` clean,
`dns-azure` listed.

## Azure integration tests

Dedicated infrastructure: resource group `rg-certbot-test`, base domain
`certbot-test.aznethorizon.com` (delegated with a single NS record from the parent zone).
Three zones: the base zone holds the static CNAME/TXT records for the delegation tests
and delegates `zone1` and `zone2`, which the plugin writes to. Never point the tests at a
production zone. Subscription, tenant and identity ids live in `CLAUDE.local.md`
(gitignored), not here.

Safety rules baked into the test module: it refuses to run unless the base domain starts
with `certbot-test.`, and cleanup only deletes `_acme-challenge*` TXT records that did not
exist before the test. Do not reintroduce the upstream "delete everything but NS/SOA"
cleanup.

CI identity: app registration `sp-certbot-dns-azure-ci` with a
federated credential for the GitHub environment `dev.azure` (note: GitHub puts the
numeric owner/repo ids into the OIDC subject claim, `repo:<owner>@<id>/<repo>@<id>:environment:dev.azure`;
a plain `repo:owner/name:...` subject fails with AADSTS700213, take the exact subject from
the azure/login step output),
role "DNS Zone Contributor" on `rg-certbot-test` only. GitHub environment `dev.azure`
carries the AZURE_* ids as secrets and EMAIL / AZURE_DNS_* as variables (tenant,
subscription and client ids are deliberately not written down in this repo); the repository
variable `RUN_AZURE_TESTS=true` switches the job on. It runs on pull requests from this
repository that touch code (the `changes` job skips it for docs-only changes), on tags,
weekly (Monday 06:00 UTC, to catch dependency drift) and via `workflow_dispatch`. It
does not run on pushes to `main`: the merged commit was already tested as a pull
request. On tags the publish job waits for it. The federated credential is bound to the
environment, not to a branch, so any job that uses `environment: dev.azure` can log in.

`main` is protected by the ruleset `protect-main`: changes only via pull request, the
five `Test (...)` jobs, `Build distribution` and `Azure Test` are required checks (a
skipped Azure Test counts as passed), no force push, no bypass. Work on `fix/`, `ci/`,
`docs/` branches and open a pull request. Every pull request gets a GitHub Copilot
review; wait for it and assess each finding before calling the PR ready.

Locally (`az login` as an account with DNS rights on the resource group):

```bash
export AZURE_TENANT_ID=$(az account show --query tenantId -o tsv) \
       AZURE_SUBSCRIPTION_ID=$(az account show --query id -o tsv) \
       AZURE_DNS_RESOURCE_GROUP=rg-certbot-test \
       AZURE_DNS_TEST_DOMAIN=certbot-test.aznethorizon.com \
       EMAIL=me@cvollmann.de
pytest -rA azure_tests/
```

## Release process

1. Bump `version` in `setup.py`, update `CHANGELOG.md` (turn "Unreleased" into the
   version heading with the date).
2. Open a pull request for the bump (`main` cannot be pushed directly), wait for the
   checks, merge.
3. Tag with the bare version (`git tag 2.7.0 && git push origin 2.7.0`). The build job
   fails if tag and `setup.py` version differ.
4. The publish job needs the GitHub environment `pypi` and a PyPI trusted publisher for
   this repo/workflow/environment. Both are set up by Christoph in the web UIs, not by
   Claude.

## Downstream

Nginx Proxy Manager installs plugins with
`pip install --no-cache-dir <dependencies> '<package_name><version>'` from
`backend/certbot/dns-plugins.json`. Target entry for an upstream PR:

```json
"azure": { "dependencies": "", "package_name": "certbot-dns-azure-modern", "version": "~=2.7.0" }
```

Users can override that file until the PR lands (bind-mount a patched copy over
`/app/certbot/dns-plugins.json` and recreate the container, see README).
