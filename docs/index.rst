certbot-dns-azure-modern
========================

Azure DNS authenticator plugin for `Certbot <https://certbot.eff.org/>`_. It completes
the ACME ``dns-01`` challenge by creating, and afterwards removing, TXT records in
Azure DNS, which also makes wildcard certificates possible.

.. note::
   This is the maintained, drop-in replacement for the upstream package
   ``certbot-dns-azure``, which no longer installs cleanly next to a current certbot.
   Module, plugin name (``dns-azure``), options and config format are unchanged. To
   switch, see :doc:`migrating`.

Pick your path
--------------

- **Nginx Proxy Manager 2.16 or later:** nothing to install, see
  :doc:`nginx-proxy-manager`.
- **Certbot on a server or in a container:** follow the quick start below.
- **Coming from** ``certbot-dns-azure``: see :doc:`migrating`.

Quick start
-----------

1. Install certbot and the plugin into the same Python environment:

   .. code-block:: bash

      pip install certbot certbot-dns-azure-modern

2. Create a service principal that may write to your zone. Run ``az login`` first, as
   an account that may create app registrations and assign roles on the zone (for
   example Owner of the resource group); ``az account show --query id -o tsv`` prints
   the ``<subscription-id>``. The command prints ``appId``, ``password`` and
   ``tenant``; you need them in the next step.

   .. code-block:: bash

      az ad sp create-for-rbac --name certbot-dns-azure \
        --role "DNS Zone Contributor" \
        --scopes /subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.Network/dnszones/example.com

   Managed identities and the other methods are covered in :doc:`authentication`.

3. Create the config file ``/etc/letsencrypt/azure.ini`` and make it readable for
   root only (``chmod 600``). The zone mapping points to the resource group that
   holds the zone:

   .. code-block:: ini

      dns_azure_sp_client_id = <appId>
      dns_azure_sp_client_secret = <password>
      dns_azure_tenant_id = <tenant>

      dns_azure_zone1 = example.com:/subscriptions/<subscription-id>/resourceGroups/<resource-group>

4. Test against the Let's Encrypt staging server, then request the real certificate:

   .. code-block:: bash

      certbot certonly --dry-run -a dns-azure \
        --dns-azure-config /etc/letsencrypt/azure.ini \
        -d example.com -d '*.example.com'

      certbot certonly -a dns-azure \
        --dns-azure-config /etc/letsencrypt/azure.ini \
        -d example.com -d '*.example.com'

Then make sure ``certbot renew`` runs regularly, see :ref:`renewal`.

.. toctree::
   :maxdepth: 1
   :caption: Get started

   installation
   nginx-proxy-manager
   migrating

.. toctree::
   :maxdepth: 1
   :caption: Guides

   authentication
   configuration
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
