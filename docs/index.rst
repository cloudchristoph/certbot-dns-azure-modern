certbot-dns-azure-modern
========================

Azure DNS authenticator plugin for `Certbot <https://certbot.eff.org/>`_. It completes
the ACME ``dns-01`` challenge by creating, and afterwards removing, TXT records in
Azure DNS through the Azure Resource Manager API.

The plugin is registered with certbot as ``dns-azure``. It supports service
principals, managed identities, Azure CLI and workload identity credentials, multiple
zones across subscriptions, sovereign clouds and DNS delegation (CNAME aliasing).

About this fork
---------------

This is the maintained fork of
`terricain/certbot-dns-azure <https://github.com/terricain/certbot-dns-azure>`_,
published on PyPI as
`certbot-dns-azure-modern <https://pypi.org/project/certbot-dns-azure-modern/>`_.

The upstream package (last release 2.6.1, December 2024) pins ``certbot<4.0``.
Installing it next to a current certbot makes pip downgrade certbot and acme to 3.3.0,
which no longer imports against pyOpenSSL 26. This is what broke Azure DNS
certificates in Nginx Proxy Manager 2.15 and later
(`NginxProxyManager#5606 <https://github.com/NginxProxyManager/nginx-proxy-manager/issues/5606>`_).
The upstream fix (`#65 <https://github.com/terricain/certbot-dns-azure/pull/65>`_) has
been waiting for a maintainer since early 2026.

The Python module (``certbot_dns_azure``), the plugin name (``dns-azure``), all
command-line flags and the config file format are unchanged. Only the distribution
name on PyPI differs, so the fork is a drop-in replacement. See :doc:`installation`
for how to switch.

Quick start
-----------

1. Install the plugin next to certbot:

   .. code-block:: bash

      pip install certbot certbot-dns-azure-modern

2. Create a config file, for example ``/etc/letsencrypt/azure.ini`` with mode ``600``,
   holding the credentials and at least one zone mapping. The example uses a service
   principal; all methods are listed in :doc:`authentication`.

   .. code-block:: ini

      dns_azure_sp_client_id = 912ce44a-0156-4669-ae22-c16a17d34ca5
      dns_azure_sp_client_secret = example-client-secret-not-real
      dns_azure_tenant_id = ed1090f3-ab18-4b12-816c-599af8a88cf7

      dns_azure_zone1 = example.com:/subscriptions/c135abce-d87d-48df-936c-15596c6968a5/resourceGroups/dns1

3. Request a certificate:

   .. code-block:: bash

      certbot certonly \
        --authenticator dns-azure \
        --dns-azure-config /etc/letsencrypt/azure.ini \
        -d example.com -d '*.example.com'

Renewal works without further options; certbot remembers the plugin and the path to
the config file.

.. toctree::
   :maxdepth: 2
   :caption: User guide

   installation
   configuration
   authentication
   usage
   dns-delegation
   troubleshooting

.. toctree::
   :maxdepth: 1
   :caption: Project

   changelog
   development
   GitHub repository <https://github.com/cloudchristoph/certbot-dns-azure-modern>
   PyPI package <https://pypi.org/project/certbot-dns-azure-modern/>
