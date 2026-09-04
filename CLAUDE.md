# certbot-dns-azure-modern

Maintained fork of `terricain/certbot-dns-azure`, published on PyPI as
`certbot-dns-azure-modern`. The Python module (`certbot_dns_azure`), the certbot plugin
name (`dns-azure`), CLI flags and config format are unchanged on purpose: downstream users
(mainly Nginx Proxy Manager) only swap the distribution name.

## Ground rules

- Everything in this repo is English: code, comments, docs, commit messages, issues.
- Never commit or push without explicit approval from Christoph. Prepare the change,
  show the diff, ask.
- Keep the plugin a drop-in replacement. Do not rename the module or the entry point.
- Keep `certbot` unbounded above (`certbot>=3.0`). An upper cap is exactly what broke
  upstream: pip downgraded certbot/acme inside shared venvs.
- Keep `azure-mgmt-dns<9.0.0` until `_get_azure_client()` is adapted to the 9.x
  `DnsManagementClient` constructor (upstream issues #58, #62, #64).

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
- `certbot_dns_azure/__init__.py` - module docstring, doubles as the user documentation
  rendered by Sphinx (`docs/index.rst` uses `automodule`).
- `tests/dns_azure_test.py` - unit tests, mock the Azure SDK. Use `_dns01_challenge()` and
  `_domain()` helpers; they hide the certbot 5 `domain=` -> `identifier=` deprecation.
- `azure_tests/integration_test.py` - real Azure DNS test, needs an OIDC service principal.
- `.github/workflows/release.yml` - test matrix, build, publish on tag via PyPI trusted
  publishing (GitHub environment `pypi`), GitHub release.
- `snap/`, `snap-requirements.txt` - inherited; this fork does not publish a snap.
- `Docker/` - inherited minimal image, installs from PyPI.

## Working locally

```bash
uv venv --python 3.13 .venv && . .venv/bin/activate
uv pip install certbot 'azure-identity>=1.19.0' 'azure-mgmt-dns>=8.2.0,<9' 'azure-core>=1.32.0' pytest build twine
uv pip install --no-deps -e .
python -m pytest -q tests/ -W error::DeprecationWarning
python -m build && python -m twine check dist/*
```

Also test the oldest supported line: `certbot>=3.0,<4.0` together with `pyOpenSSL<26`
(acme 3.x needs it).

Smoke test in the Nginx Proxy Manager image (this is the primary consumer):

```bash
docker run --rm -v "$PWD/dist:/dist:ro" --entrypoint bash jc21/nginx-proxy-manager:2.15.1 -c '
  . /opt/certbot/bin/activate
  pip install --no-cache-dir "certbot-dns-azure-modern~=2.7.0" --find-links /dist
  pip check && certbot --version && certbot plugins --text | grep -A1 dns-azure'
```

Expected: certbot stays at the image version (5.6.0 in 2.15.1), `pip check` clean,
`dns-azure` listed.

## Release process

1. Bump `version` in `setup.py` (also `snap/snapcraft.yaml`), update `CHANGELOG.md`.
2. Commit on `main`, push, wait for the test matrix.
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

Christoph's own NPM config lives in the private `nas_configs` repo
(`nginx-proxy-manager/dns-plugins.json`, bind-mounted over `/app/certbot/dns-plugins.json`).
