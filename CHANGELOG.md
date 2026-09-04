# Changelog

## Unreleased

- Boolean config keys (`dns_azure_use_cli_credentials`, `dns_azure_msi_system_assigned`,
  `dns_azure_use_workload_identity_credentials`) are parsed as booleans. Previously any
  non-empty value, including `false`, switched the method on, so a service principal
  next to `dns_azure_use_cli_credentials = false` silently used the Azure CLI login.
- An unknown `dns_azure_environment` is reported as a configuration error naming the
  valid values instead of a `KeyError` traceback.
- Retrying a TXT record update after a concurrent-modification response (HTTP 412)
  re-resolves the record from the original validation name; the retry previously
  passed the already relative record name back in.
- Record sets without TXT values no longer raise `TypeError`.
- Creating a new `_acme-challenge` record set is conditional (`If-None-Match: *`). Two
  certbot runs racing for the same name no longer overwrite each other; the loser
  re-reads the record and merges its value, as already happened for updates.
- A zone mapping whose resource id lacks `/subscriptions/<id>/resourceGroups/<name>`
  is rejected with a clear message instead of a `ValueError` from the Azure SDK.
- Zone names in mappings are compared case-insensitively and trimmed, so
  `Example.com` and `example.com` count as the same zone.
- Zones can use different credentials: put zones that share an identity into an INI
  section (`[name]`) together with that identity's settings. Sections without
  authentication keys use the top-level credentials. This allows one certificate to
  span zones in different Entra ID tenants (terricain/certbot-dns-azure#49).
- New option `--dns-azure-ttl` sets the TTL of the `_acme-challenge` TXT records; the
  default stays 120 seconds (terricain/certbot-dns-azure#48).
- Support `azure-mgmt-dns` 9.x and drop the `<9.0.0` pin. 9.x removed the positional
  `api_version` parameter of `DnsManagementClient`, which made the plugin fail with
  `TypeError: __init__() takes from 3 to 4 positional arguments but 5 were given`;
  the client is now constructed with keyword arguments, which works for 8.x and 9.x
  (terricain/certbot-dns-azure#60, #62). The token scope is now
  `https://management.azure.com/.default` (single slash), as used by the Azure SDK
  itself.
- Zone matching now respects label boundaries: a request for `abcxyz.net` no longer
  matches a configured zone `xyz.net`, and the relative record name is derived by
  stripping the zone suffix instead of a substring replace
  (terricain/certbot-dns-azure#61).
- CI: the unit tests run against both `azure-mgmt-dns` lines (8.x and 9.x); the Azure
  integration test (real certificate issuance) is a required check for pull requests
  that change code, runs on release tags and once a week against the latest certbot
  and Azure SDK releases; `main` is protected and only changes via pull request;
  Dependabot keeps the GitHub Actions current.

## 2.7.0 (2026-09-04)

First release of the maintained fork, published on PyPI as `certbot-dns-azure-modern`.
The Python package (`certbot_dns_azure`) and the certbot plugin name (`dns-azure`) are
unchanged, so it is a drop-in replacement for `certbot-dns-azure`.

- Allow certbot >= 4 (`certbot>=3.0`, no upper bound). The old `<4.0` cap made pip
  downgrade certbot/acme to 3.3.0 inside shared venvs such as Nginx Proxy Manager, where
  acme 3.3.0 then failed to import against pyOpenSSL >= 26
  (NginxProxyManager/nginx-proxy-manager#5606, terricain/certbot-dns-azure#65).
- Pin `azure-mgmt-dns<9.0.0`; 9.x changed the `DnsManagementClient` constructor
  (terricain/certbot-dns-azure#58, #62).
- Require Python >= 3.9.
- Tests no longer use the deprecated `domain=` argument of `AnnotatedChallenge`
  when the installed certbot supports `identifier=`.
- CI: test matrix across Python 3.11-3.13 and certbot 3.x/latest, build with
  `python -m build`, publish via PyPI trusted publishing.

## 2.6.1 and earlier

See the upstream project: https://github.com/terricain/certbot-dns-azure
