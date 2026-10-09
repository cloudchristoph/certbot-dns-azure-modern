# certbot-dns-azure-modern

[![Tests](https://github.com/cloudchristoph/certbot-dns-azure-modern/actions/workflows/release.yml/badge.svg)](https://github.com/cloudchristoph/certbot-dns-azure-modern/actions)
[![Version](https://img.shields.io/pypi/v/certbot-dns-azure-modern)](https://pypi.org/project/certbot-dns-azure-modern/)
[![Python Version](https://img.shields.io/pypi/pyversions/certbot-dns-azure-modern)](https://pypi.org/project/certbot-dns-azure-modern/)
[![Docs](https://github.com/cloudchristoph/certbot-dns-azure-modern/actions/workflows/docs.yml/badge.svg)](https://cloudchristoph.github.io/certbot-dns-azure-modern/)

Azure DNS authenticator plugin for [Certbot](https://certbot.eff.org/): it completes the
ACME `dns-01` challenge with TXT records in Azure DNS, including wildcard certificates.
Maintained, drop-in replacement for the upstream package `certbot-dns-azure`.

## Pick your path

- **Nginx Proxy Manager 2.16 or later:** nothing to install, choose "Azure" as DNS
  provider. See the [Nginx Proxy Manager guide](https://cloudchristoph.github.io/certbot-dns-azure-modern/nginx-proxy-manager.html).
- **Certbot on a server or in a container:** see the quick start below.
- **Coming from `certbot-dns-azure`:** see
  [Switching from certbot-dns-azure](https://cloudchristoph.github.io/certbot-dns-azure-modern/migrating.html);
  config files keep working.

## Quick start

```bash
pip install certbot certbot-dns-azure-modern
```

Create `/etc/letsencrypt/azure.ini` (`chmod 600`) with the credentials of a service
principal that has the "DNS Zone Contributor" role on the zone, and map each zone to
its resource group:

```ini
dns_azure_sp_client_id = <client-id>
dns_azure_sp_client_secret = <client-secret>
dns_azure_tenant_id = <tenant-id>

dns_azure_zone1 = example.com:/subscriptions/<subscription-id>/resourceGroups/<resource-group>
```

```bash
certbot certonly -a dns-azure --dns-azure-config /etc/letsencrypt/azure.ini \
  -d example.com -d '*.example.com'
```

The [quick start in the docs](https://cloudchristoph.github.io/certbot-dns-azure-modern/)
shows how to create the identity.

## Features

- Service principals (secret or certificate), managed identities, workload identity
  and the Azure CLI
- Any number of zones across subscriptions, and separate credentials per zone, also
  across Entra ID tenants
- Azure public cloud, Azure US Government and Azure China
- DNS delegation via CNAME, and write access limited to a single TXT record

## Compatibility

Python 3.10 or newer, certbot 3.0 or newer (no upper bound, so pip never downgrades
your certbot), `azure-mgmt-dns` 8.x and 9.x.

## Documentation

[cloudchristoph.github.io/certbot-dns-azure-modern](https://cloudchristoph.github.io/certbot-dns-azure-modern/):
[authentication](https://cloudchristoph.github.io/certbot-dns-azure-modern/authentication.html),
[configuration](https://cloudchristoph.github.io/certbot-dns-azure-modern/configuration.html),
[DNS delegation](https://cloudchristoph.github.io/certbot-dns-azure-modern/dns-delegation.html),
[troubleshooting](https://cloudchristoph.github.io/certbot-dns-azure-modern/troubleshooting.html),
[changelog](https://cloudchristoph.github.io/certbot-dns-azure-modern/changelog.html).

## About this fork

The upstream package [terricain/certbot-dns-azure](https://github.com/terricain/certbot-dns-azure)
(last release 2.6.1, December 2024) pins `certbot<4.0`, so installing it next to a
current certbot downgrades certbot and breaks it. This fork removes the pin and keeps
the module, plugin name `dns-azure`, options and config format unchanged. Nginx Proxy
Manager switched to it in 2.16.0.
