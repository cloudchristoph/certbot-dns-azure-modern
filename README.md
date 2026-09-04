# certbot-dns-azure-modern

[![Tests](https://github.com/cloudchristoph/certbot-dns-azure/actions/workflows/release.yml/badge.svg)](https://github.com/cloudchristoph/certbot-dns-azure/actions)
[![Version](https://img.shields.io/pypi/v/certbot-dns-azure-modern)](https://pypi.org/project/certbot-dns-azure-modern/)
[![Python Version](https://img.shields.io/pypi/pyversions/certbot-dns-azure-modern)](https://pypi.org/project/certbot-dns-azure-modern/)
[![Docs](https://github.com/cloudchristoph/certbot-dns-azure/actions/workflows/docs.yml/badge.svg)](https://cloudchristoph.github.io/certbot-dns-azure/)

> **Maintained fork of [terricain/certbot-dns-azure](https://github.com/terricain/certbot-dns-azure).**
>
> The upstream package `certbot-dns-azure` (last release 2.6.1, December 2024) pins
> `certbot<4.0`. Installing it next to a current certbot makes pip downgrade certbot
> and acme to 3.3.0, which no longer imports against pyOpenSSL >= 26
> (`AttributeError: module 'OpenSSL.crypto' has no attribute 'X509Extension'`).
> This is what breaks Azure DNS certificates in Nginx Proxy Manager 2.15+
> ([NginxProxyManager#5606](https://github.com/NginxProxyManager/nginx-proxy-manager/issues/5606)).
> Upstream has not responded to fixes since early 2025
> ([#65](https://github.com/terricain/certbot-dns-azure/pull/65)), hence this fork.
>
> The Python module (`certbot_dns_azure`), the plugin name (`dns-azure`), all CLI flags
> and the config file format are unchanged. Only the distribution name on PyPI differs.
> Both packages install the same module, so replace rather than stack them:
> `pip uninstall certbot-dns-azure && pip install -U certbot certbot-dns-azure-modern`.
> Installing the fork on top of an existing 2.6.1 does not undo the certbot downgrade.

AzureDNS Authenticator plugin for [Certbot](https://certbot.eff.org/).

This plugin is built from the ground up and follows the development style and life-cycle
of other `certbot-dns-*` plugins found in the
[Official Certbot Repository](https://github.com/certbot/certbot). PR is open [here](https://github.com/certbot/certbot/pull/8727) though Certbot is not accepting plugin PR's at the moment.

## Installation


### Via Pip

```
pip3 install certbot certbot-dns-azure-modern
```

### Nginx Proxy Manager

Override the `azure` entry in `/app/certbot/dns-plugins.json` (bind-mount a patched copy)
and recreate the container, so the plugin is installed into a fresh certbot venv:

```json
"azure": {
  "dependencies": "",
  "package_name": "certbot-dns-azure-modern",
  "version": "~=2.7.0"
}
```

Verify inside the container:

```
$ . /opt/certbot/bin/activate && certbot --version && certbot plugins --text | grep dns-azure
```

### Via Snap

The snap in the Snap Store is published by the upstream author and still ships 2.6.1.
This fork does not publish a snap.

### Verification

Verify:

```
$ certbot plugins --text

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
* dns-azure
Description: Obtain certificates using a DNS TXT record (if you are using Azure
for DNS).
Interfaces: Authenticator, Plugin
Entry point: dns-azure = certbot_dns_azure._internal.dns_azure:Authenticator

...
...
```

Docs and instructions on configuration (config file format, authentication methods, DNS delegation) are at [cloudchristoph.github.io/certbot-dns-azure](https://cloudchristoph.github.io/certbot-dns-azure/).


