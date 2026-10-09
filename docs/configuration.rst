Configuration
=============

The config file
---------------

All settings for your Azure setup live in one INI file of ``key = value`` lines: the
credentials (or the choice of a credential method) and the mapping from DNS zones to
their location in Azure.

.. code-block:: ini
   :caption: /etc/letsencrypt/azure.ini

   dns_azure_sp_client_id = 912ce44a-0156-4669-ae22-c16a17d34ca5
   dns_azure_sp_client_secret = example-client-secret-not-real
   dns_azure_tenant_id = ed1090f3-ab18-4b12-816c-599af8a88cf7

   dns_azure_zone1 = example.com:/subscriptions/c135abce-d87d-48df-936c-15596c6968a5/resourceGroups/dns1
   dns_azure_zone2 = example.org:/subscriptions/99800903-fb14-4992-9aff-12eaf2744622/resourceGroups/dns2

The IDs in the examples are made up. Pass the path with ``--dns-azure-config``;
certbot asks for it if the option is missing. Keep the file in place, renewals read
it again (see :ref:`renewal`). In Nginx Proxy Manager the same content goes into the
credentials box, see :doc:`nginx-proxy-manager`.

Keys
~~~~

===============================================  =============================================
Key                                              Meaning
===============================================  =============================================
``dns_azure_zone<N>``                            Zone mapping, see below. At least one is
                                                 required; ``N`` is any unique number.
``dns_azure_environment``                        Azure cloud, see :ref:`azure-environment`.
                                                 Default ``AzurePublicCloud``.
``dns_azure_sp_client_id``                       Client ID of a service principal (app
                                                 registration).
``dns_azure_sp_client_secret``                   Client secret of the service principal.
``dns_azure_sp_certificate_path``                Path to a certificate file with private key,
                                                 alternative to the client secret.
``dns_azure_tenant_id``                          Entra ID tenant ID. Required for service
                                                 principals; pins the tenant for the Azure
                                                 CLI and workload identity.
``dns_azure_msi_client_id``                      Client ID of a user-assigned managed
                                                 identity.
``dns_azure_msi_system_assigned``                ``true`` to use the system-assigned
                                                 managed identity.
``dns_azure_use_cli_credentials``                ``true`` to use the Azure CLI login.
``dns_azure_use_workload_identity_credentials``  ``true`` to use workload identity.
===============================================  =============================================

Boolean keys accept ``true``, ``yes``, ``on`` or ``1`` in any case; every other value,
including a typo, counts as off. Which keys each authentication method needs is
described in :doc:`authentication`.

Zone mappings
-------------

Azure DNS zones can live in any resource group of any subscription, so the plugin
needs to be told where each zone is. Each ``dns_azure_zone<N>`` line maps a domain to
an Azure resource ID:

.. code-block:: text

   dns_azure_zone1 = DOMAIN:RESOURCE_ID

- ``DOMAIN`` is the name of the DNS zone in Azure, for example ``example.com``.
- ``RESOURCE_ID`` is normally the ID of the resource group that holds the zone,
  ``/subscriptions/<subscription-id>/resourceGroups/<resource-group>``. The zone name
  is taken from ``DOMAIN``.

  It can also be the ID of a DNS zone (``.../providers/Microsoft.Network/dnszones/<zone>``)
  or of a single TXT record set. Those forms redirect the validation record to a
  different zone or record, see :doc:`dns-delegation`.

The resource group ID is shown in the portal under **resource group → Properties →
Resource ID**, or with the Azure CLI:

.. code-block:: bash

   az group show --name dns1 --query id --output tsv

How domains are matched
~~~~~~~~~~~~~~~~~~~~~~~

For every name in the certificate, the plugin picks the configured ``DOMAIN`` that the
name equals or is a subdomain of; the longest configured domain wins. One mapping for
``example.com`` therefore covers ``www.example.com``, ``*.example.com`` and any deeper
subdomain, as long as they are all served from the ``example.com`` zone. Matching
happens on label boundaries and ignores case: ``myexample.com`` is not covered by
``example.com`` and needs its own mapping.

If a subdomain is its own zone in Azure (say ``dev.example.com`` is delegated to a
separate zone), add a mapping for it as well; the longer match wins and the TXT
record is created in the subdomain's zone.

.. _credential-sets:

Several credential sets (zones in different tenants)
-----------------------------------------------------

One identity is enough as long as it has access to every zone. When zones live in
different Entra ID tenants, or you want a separate identity per zone, put the zones
that share an identity into an INI section with that identity's settings:

.. code-block:: ini
   :caption: /etc/letsencrypt/azure.ini

   dns_azure_sp_client_id = 912ce44a-0156-4669-ae22-c16a17d34ca5
   dns_azure_sp_client_secret = example-client-secret-not-real
   dns_azure_tenant_id = ed1090f3-ab18-4b12-816c-599af8a88cf7
   dns_azure_zone1 = example.com:/subscriptions/c135abce-d87d-48df-936c-15596c6968a5/resourceGroups/dns1

   [partner]
   dns_azure_sp_client_id = 0d4e2f4c-5b3a-4b8c-9a1e-2f6d7c8b9a0e
   dns_azure_sp_client_secret = another-secret-not-real
   dns_azure_tenant_id = 7b1c9e2d-3f4a-4c5b-8d6e-9f0a1b2c3d4e
   dns_azure_zone1 = partner.example:/subscriptions/99800903-fb14-4992-9aff-12eaf2744622/resourceGroups/dns2

Rules:

- The section name is free; it only labels the credential set in error messages.
- A section takes the same authentication keys as the top level, so every method from
  :doc:`authentication` works per section. ``dns_azure_environment`` is global.
- A section without authentication keys uses the top-level credentials; it merely
  groups zones.
- Zone numbering restarts in every section. Each zone may be mapped only once across
  all sets.
- The top-level credentials can be left out when every zone is in a section with
  credentials of its own.
- Domain matching works across all sets: the longest configured domain wins, and the
  credentials of its set are used for that name. A certificate can therefore span
  zones from several sets.

.. _azure-environment:

Azure environment
-----------------

The plugin talks to the Azure public cloud by default. For a sovereign cloud set
``dns_azure_environment`` in the config file or the ``AZURE_ENVIRONMENT`` environment
variable; the config file takes precedence. Values are case-insensitive and differ
from the cloud names of the Azure CLI.

============================  ==========================================
Value                         Resource Manager endpoint
============================  ==========================================
``AzurePublicCloud``          ``https://management.azure.com/``
``AzureUSGovernmentCloud``    ``https://management.usgovcloudapi.net/``
``AzureChinaCloud``           ``https://management.chinacloudapi.cn/``
============================  ==========================================

The environment selects the Resource Manager endpoint for every method and the
Entra ID sign-in authority for service principals. Managed identities, the Azure CLI
(``az cloud set``) and workload identity get their tokens from the platform, which
already knows its cloud.

.. _protect-config:

Protect the config file
-----------------------

.. caution::
   Treat the config file like the password to your Azure account. Anyone who can
   read it can call the Azure API with these credentials, and anyone who can make
   certbot run with it can obtain certificates for every domain the identity has
   access to.

Restrict the file, and a certificate file if you use one, to the user that runs
certbot:

.. code-block:: bash

   chmod 600 /etc/letsencrypt/azure.ini

Certbot warns with ``Unsafe permissions on credentials configuration file`` on every
run, including renewals, as long as other users have any access to the file.

Prefer, in this order: a managed identity or workload identity, which keep no secret
in the file; a service principal with a certificate; a client secret only where
nothing else works, with a short lifetime (see :ref:`secret-expiry`).

Command-line options
--------------------

Select the plugin with ``--authenticator dns-azure`` (or ``-a dns-azure``). It adds
the following options to certbot, which are also accepted in
``/etc/letsencrypt/cli.ini`` without the leading dashes.

======================================  ========================================================
``--dns-azure-config``                  Path to the config file. Prompted for if missing.
``--dns-azure-credentials``             Alias for ``--dns-azure-config`` for integrations that
                                        pass ``--<plugin>-credentials``, such as Nginx Proxy
                                        Manager. Takes precedence if both are given.
``--dns-azure-propagation-seconds``     Seconds to wait after creating the TXT record before
                                        the ACME server validates. Default: 60, see
                                        :ref:`propagation`.
``--dns-azure-ttl``                     TTL in seconds (whole number, at least 1) of the
                                        ``_acme-challenge`` TXT record. Default: 120.
======================================  ========================================================
