Troubleshooting
===============

Run certbot with ``-v`` (or ``--debug``) to see the plugin's log output, including
the zone it picked and the Azure API errors in full.

``AttributeError: module 'OpenSSL.crypto' has no attribute 'X509Extension'``
-------------------------------------------------------------------------------

Certbot itself fails to start, typically right after installing an Azure DNS plugin
in Nginx Proxy Manager 2.15 or later. The upstream package ``certbot-dns-azure``
pins ``certbot<4.0``, so pip downgraded certbot and acme to 3.3.0, and that acme
release does not import against pyOpenSSL 26.

Fix: replace the upstream package with this fork and restore certbot. In a plain
virtual environment:

.. code-block:: bash

   pip uninstall certbot-dns-azure
   pip install -U certbot certbot-dns-azure-modern

In Nginx Proxy Manager, patch ``dns-plugins.json`` and recreate the container as
described in :doc:`installation`; a fresh container comes with an intact certbot.

Plugin not listed by ``certbot plugins``
----------------------------------------

The plugin was installed into a different Python environment than certbot. Compare
the locations:

.. code-block:: bash

   pip show certbot certbot-dns-azure-modern
   which certbot

Install the plugin with the ``pip`` that belongs to the certbot you run, for example
``/opt/certbot/bin/pip`` in Nginx Proxy Manager or ``/usr/bin/pip3`` for a distro
certbot. Snap-installed certbot only accepts plugins from snaps; this fork ships
none, so use a pip installation of certbot instead.

``No authentication methods have been configured for Azure DNS``
----------------------------------------------------------------

The config file names no complete credential method. Check the spelling of the keys
and that a service principal has all three of ``dns_azure_sp_client_id``,
``dns_azure_tenant_id`` and either ``dns_azure_sp_client_secret`` or
``dns_azure_sp_certificate_path``. See :doc:`authentication`.

Zone mapping errors on startup
------------------------------

``At least one zone mapping needs to be provided`` or ``DNS Zone mapping is not in
the format of DOMAIN:DNS_ZONE_RESOURCE_GROUP_ID``: every ``dns_azure_zone<N>`` line
must look like ``example.com:/subscriptions/...`` with a colon between domain and
resource id, and at least one such line must exist.

``Domain <name> does not have a valid domain to resource group id mapping``
---------------------------------------------------------------------------

None of the configured domains is a suffix of the requested name. Add a mapping for
the zone that serves the name. See "How domains are matched" in :doc:`configuration`.

Authorization failed (HTTP 403)
-------------------------------

The identity is authenticated but has no write access to the zone. Assign the
**DNS Zone Contributor** role on the zone or its resource group and wait a few
minutes for the assignment to propagate. When the mapping points at a single record,
the assignment must be on that record and the record must exist, see
:doc:`dns-delegation`.

A 404 on the zone usually means the resource id in the mapping names the wrong
subscription or resource group, or the domain in the mapping is not the exact name
of the zone in Azure.

Authentication errors (AADSTS codes, ``ClientAuthenticationError``)
-------------------------------------------------------------------

- ``AADSTS7000215`` invalid client secret: the secret is wrong or expired. Create a
  new one in the app registration.
- ``AADSTS700016`` application not found: client id and tenant id do not belong
  together.
- Managed identity errors on a host that is not an Azure resource: managed identities
  only work on Azure VMs, containers and services with an identity attached. Use a
  service principal elsewhere.
- Azure CLI credentials: the user running certbot must be the one that ran
  ``az login``; cron jobs and services usually run as a different user.
- Sovereign clouds: make sure ``dns_azure_environment`` matches the cloud the
  identity lives in.

``ManagedIdentityCredential authentication unavailable`` behind a proxy
------------------------------------------------------------------------

A managed identity obtains its token from the instance metadata service at
``169.254.169.254``. That address must be reached directly; the metadata service
rejects requests that arrive through a proxy (the debug log shows
``Header contains 'X-Forwarded-For' are not supported``). If the host uses
``HTTP_PROXY`` / ``HTTPS_PROXY``, exclude the metadata address:

.. code-block:: bash

   export NO_PROXY=169.254.169.254

Set it in the environment certbot runs in, for a systemd timer via
``Environment=NO_PROXY=169.254.169.254`` in the service unit. The Azure DNS API calls
themselves may still go through the proxy.

Validation fails although the record was created
-------------------------------------------------

Check what the public DNS returns while certbot is waiting:

.. code-block:: bash

   dig +short TXT _acme-challenge.example.com

- Nothing at all: the zone in Azure is not the one the domain delegates to. Compare
  the NS records of the domain with the name servers of the Azure zone.
- A CNAME: you are using delegation; make sure the target matches the mapping, see
  :doc:`dns-delegation`.
- An old value or intermittent failures: raise ``--dns-azure-propagation-seconds``.

``Unsafe permissions on configuration file``
--------------------------------------------

The config file is readable by other users. Restrict it:

.. code-block:: bash

   chmod 600 /etc/letsencrypt/azure.ini

The warning is emitted on every run, including renewals, until the permissions are
fixed.

Reporting a bug
---------------

Open an issue at
https://github.com/cloudchristoph/certbot-dns-azure-modern/issues with the certbot
and plugin versions (``pip show certbot certbot-dns-azure-modern``), the
command you ran and the relevant part of ``/var/log/letsencrypt/letsencrypt.log``.
Remove secrets, subscription ids and tenant ids before posting.
