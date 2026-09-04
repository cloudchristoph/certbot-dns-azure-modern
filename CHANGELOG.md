# Changelog

## 2.7.0 (unreleased)

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

See the upstream project: https://github.com/terricain/certbot-dns-azure/releases
