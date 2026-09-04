"""
Azure DNS authenticator plugin for certbot.

The `~certbot_dns_azure.dns_azure` plugin completes the ``dns-01`` challenge
(`~acme.challenges.DNS01`) by creating, and subsequently removing, TXT records in
Azure DNS through the Azure Resource Manager API.

Install it next to certbot with ``pip install certbot certbot-dns-azure-modern`` and
select it with ``--authenticator dns-azure --dns-azure-config <file>``. The config
file holds the Azure credentials and the mapping of DNS zones to resource groups.

Full documentation, including all authentication methods, the config file format
and DNS delegation, is at https://cloudchristoph.github.io/certbot-dns-azure-modern/.
"""
