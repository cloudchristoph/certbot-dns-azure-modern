Troubleshooting
===============

Errors from Azure are part of the plugin's error message (``Failed to add TXT record
for domain ...``, ``Failed to remove ...``, ``Failed to check ...``). Run certbot with
``-v`` for more output and ``--debug`` for full tracebacks. The complete log is
``/var/log/letsencrypt/letsencrypt.log``; in Nginx Proxy Manager it is
``/data/logs/letsencrypt.log`` in the container.

.. _plugin-not-listed:

Plugin not listed by ``certbot plugins``
----------------------------------------

The plugin was installed into a different Python environment than certbot. Compare
the locations:

.. code-block:: bash

   pip show certbot certbot-dns-azure-modern
   which certbot

Install the plugin with the ``pip`` that belongs to the certbot you run, for example
``/opt/certbot/bin/pip``. Nginx Proxy Manager installs the plugin on demand, see
:doc:`nginx-proxy-manager`. A snap-installed certbot accepts plugins
from snaps only; this fork ships none, so install certbot with pip instead.

Configuration errors
--------------------

Most of these appear right at the start. Resource ID and domain errors appear when
certbot reaches that name; records already written for other names are removed
again.

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Message
     - Fix
   * - ``No authentication methods have been configured for Azure DNS``, optionally
       with ``(section [name])``
     - No complete method in the top level or in that section. Check the key names,
       that boolean keys are ``true``, and that a service principal has
       ``dns_azure_sp_client_id``, ``dns_azure_tenant_id`` and a secret or
       certificate. See :doc:`authentication`.
   * - ``At least one zone mapping needs to be provided``
     - Add a ``dns_azure_zone1 = DOMAIN:RESOURCE_ID`` line.
   * - ``DNS Zone mapping is not in the format of DOMAIN:DNS_ZONE_RESOURCE_GROUP_ID``
     - Put a colon between domain and resource ID: ``example.com:/subscriptions/...``.
   * - ``zone <name> is mapped more than once``
     - Each zone may appear in one mapping only, across all credential sets.
   * - ``Unknown Azure environment``
     - Use ``AzurePublicCloud``, ``AzureUSGovernmentCloud`` or ``AzureChinaCloud``,
       see :ref:`azure-environment`.
   * - ``Resource ID for <name> must contain /subscriptions/<id>/resourceGroups/<name>``
       or ``Failed to parse resource ID``
     - Copy the resource ID of the resource group (or zone, or record) again; see
       :doc:`configuration`.
   * - ``Domain <name> does not have a valid domain to resource group id mapping``
     - No configured domain equals the name or is a parent domain of it. Add a mapping
       for the zone that serves the name, see "How domains are matched" in
       :doc:`configuration`.
   * - ``argument --dns-azure-ttl: invalid int value`` or ``--dns-azure-ttl must be at
       least 1 second``
     - Pass a positive whole number.

Authentication errors (``AADSTS`` codes)
----------------------------------------

- ``AADSTS7000215`` invalid client secret: the value is wrong. Copy the secret's
  **Value**, not its **Secret ID**.
- ``AADSTS7000222`` client secret expired: create a new secret and update the config,
  see :ref:`secret-expiry`.
- ``AADSTS700016`` application not found: client ID and tenant ID do not belong
  together.
- ``AADSTS90002`` tenant not found: check ``dns_azure_tenant_id`` and that
  ``dns_azure_environment`` matches the cloud the tenant lives in.
- Managed identity unavailable: managed identities work only on Azure resources with
  an identity attached and on Azure Arc-enabled servers. Use a service principal
  elsewhere.
- Azure CLI: the user running certbot must be the one who ran ``az login``; cron jobs
  and services usually run as root. Expired sessions and multifactor prompts make the
  CLI unsuitable for unattended renewals, see :doc:`authentication`.

Authorization failed (HTTP 403)
-------------------------------

The identity signed in but may not write to the zone. Assign **DNS Zone
Contributor** on the zone, see :ref:`required-permissions`, and allow up to 10 minutes
for the assignment to take effect. With a record mapping, the assignment must be on
that record, see :doc:`dns-delegation`.

Zone or record not found (HTTP 404)
-----------------------------------

The resource ID in the mapping names the wrong subscription or resource group, or the
domain in the mapping is not the exact name of the zone in Azure. With a record
mapping, the record must exist before the first run.

``ManagedIdentityCredential authentication unavailable`` behind a proxy
------------------------------------------------------------------------

On Azure VMs and scale sets a managed identity gets its token from the instance
metadata service at ``169.254.169.254``. That address must be reached directly; the
metadata service rejects requests that arrive through a proxy (the debug log shows
``Header contains 'X-Forwarded-For' are not supported``). If the host uses
``HTTP_PROXY`` / ``HTTPS_PROXY``, add the metadata address to the proxy exceptions
without dropping the ones already there:

.. code-block:: bash

   export NO_PROXY="${NO_PROXY:+$NO_PROXY,}169.254.169.254"

Set it in the environment certbot runs in. For a systemd timer, extend the
``Environment=NO_PROXY=...`` line of the service unit. The Azure DNS API calls
themselves may still go through the proxy.

Validation fails although the record was created
-------------------------------------------------

Check what public DNS returns while certbot is waiting:

.. code-block:: bash

   dig +short TXT _acme-challenge.example.com

- Nothing at all: the zone in Azure is not the one the domain delegates to. Compare
  the domain's NS records with the name servers of the Azure zone.
- A CNAME: you are using delegation; make sure the target matches the mapping, see
  :doc:`dns-delegation`.
- The right value, but the request failed with ``No TXT record found`` or ``NXDOMAIN
  looking up TXT``: Let's Encrypt checked too early. Raise
  ``--dns-azure-propagation-seconds`` to 30, see :ref:`propagation`.

``Unsafe permissions on credentials configuration file``
--------------------------------------------------------

Other users can access the config file. Run ``chmod 600`` on it, see
:ref:`protect-config`.

``AttributeError: module 'OpenSSL.crypto' has no attribute 'X509Extension'``
-------------------------------------------------------------------------------

Certbot fails to start because the upstream package ``certbot-dns-azure`` downgraded
certbot and acme to 3.3.0. Replace it with this fork as described in
:doc:`migrating`; in Nginx Proxy Manager, upgrade to 2.16.0 or later.

Report a bug
------------

Open an issue at
https://github.com/cloudchristoph/certbot-dns-azure-modern/issues with the certbot
and plugin versions (``pip show certbot certbot-dns-azure-modern``), the command you
ran and the relevant part of the certbot log. Remove secrets, subscription IDs and
tenant IDs before posting.
