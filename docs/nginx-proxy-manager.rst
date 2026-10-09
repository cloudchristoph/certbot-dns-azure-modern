Nginx Proxy Manager
===================

Nginx Proxy Manager 2.16.0 and later use this plugin for the "Azure" DNS provider
(`NginxProxyManager#5831 <https://github.com/NginxProxyManager/nginx-proxy-manager/pull/5831>`_).
There is nothing to install; you only need an identity in Azure and its credentials.

Create the identity in Azure
----------------------------

Nginx Proxy Manager usually runs outside Azure, so use a service principal (an app
registration with a client secret).

In the Azure portal:

1. **Microsoft Entra ID → App registrations → New registration.** Any name, for
   example ``certbot-dns-azure``; no redirect URI.
2. On the app's **Overview** page, note the **Application (client) ID** and the
   **Directory (tenant) ID**.
3. **Certificates & secrets → New client secret.** Copy the **Value** right away; it
   is shown only once. The **Secret ID** next to it is not the secret.
4. Open your **DNS zone → Access control (IAM) → Add role assignment**, choose
   **DNS Zone Contributor**, and select the app registration as member.
5. Open the **resource group** that holds the zone → **Properties**, and copy the
   **Resource ID** (``/subscriptions/.../resourceGroups/...``).

The same with the Azure CLI, which prints ``appId``, ``password`` and ``tenant``:

.. code-block:: bash

   az ad sp create-for-rbac --name certbot-dns-azure \
     --role "DNS Zone Contributor" \
     --scopes /subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.Network/dnszones/example.com

.. warning::
   Client secrets expire: after one year with the CLI, after the period you chose in
   the portal (at most 24 months). When the secret has expired, renewals fail.
   Nginx Proxy Manager cannot change the credentials of an existing certificate, so
   before the date: add a new secret in Azure, create a new certificate with it,
   switch the proxy hosts to the new certificate, then delete the old certificate
   and the old secret.

Request the certificate
-----------------------

Under **SSL Certificates → Add Certificate → Let's Encrypt via DNS** (or in a proxy
host's **SSL** tab with **Use DNS Challenge** switched on), choose **Azure** as **DNS
Provider** and replace the template in **Credentials File Content** with:

.. code-block:: ini

   dns_azure_sp_client_id = <Application (client) ID>
   dns_azure_sp_client_secret = <client secret Value>
   dns_azure_tenant_id = <Directory (tenant) ID>

   dns_azure_zone1 = example.com:<Resource ID of the resource group>

Add one ``dns_azure_zone<N>`` line per zone. Leave **Propagation Seconds** empty to
use the default of 10 seconds. If a request fails with ``No TXT record found``, request
it again with 30; renewals that fail once are retried automatically every hour.

Nginx Proxy Manager stores these credentials in plain text in its database (and,
during each certbot run, in a file in the container). Scope the role assignment to the zone, as above, rather
than to the whole resource group or subscription.

Only the service principal works in a typical Nginx Proxy Manager setup. A managed
identity works only when the container runs on an Azure VM or another Azure resource
with an identity attached; the Azure CLI and workload identity are not available in
the container. All methods are described in :doc:`authentication`.

Upgrade from 2.15
-----------------

Nginx Proxy Manager 2.15.x installs the broken upstream package. Set the image tag in
your compose file to ``2.16.0`` or later (or ``latest``) and recreate the container,
so that a certbot downgraded by the upstream plugin is not left behind:

.. code-block:: bash

   docker compose pull && docker compose up -d --force-recreate

If you used the earlier workaround and bind-mounted a patched
``/app/certbot/dns-plugins.json``, remove that entry from ``volumes:``. The patched copy
replaces the whole plugin list of the image and would hide later updates to other DNS
plugins.

Verify the installation
-----------------------

Nginx Proxy Manager installs the plugin on the first certificate request with the
Azure provider, or at container start when existing certificates use it. Afterwards,
from the directory of your compose file (``app`` is the service name in Nginx Proxy
Manager's example):

.. code-block:: bash

   docker compose exec app bash -c \
     '. /opt/certbot/bin/activate && certbot --version && certbot plugins --text | grep -A1 dns-azure'

When a request fails, the error is shown in the web UI; the full certbot log is
``/data/logs/letsencrypt.log`` in the container (``./data/logs/`` on the host with
Nginx Proxy Manager's example compose file). The common errors are listed in :doc:`troubleshooting`.
