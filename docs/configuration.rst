Configuration
=============

Command-line options
--------------------

The plugin adds the following options to certbot. They are also accepted in
``/etc/letsencrypt/cli.ini`` without the leading dashes.

======================================  ========================================================
``--dns-azure-config``                  Path to the config file described below. (Required)
``--dns-azure-credentials``             Alias for ``--dns-azure-config``, kept for integrations
                                        that pass a ``--<plugin>-credentials`` option, such as
                                        Nginx Proxy Manager.
``--dns-azure-propagation-seconds``     Seconds to wait after creating the TXT record before
                                        asking the ACME server to validate. Default: 10.
``--dns-azure-ttl``                     TTL in seconds of the ``_acme-challenge`` TXT record
                                        the plugin creates. Default: 120.
======================================  ========================================================

Select the plugin with ``--authenticator dns-azure`` (or ``-a dns-azure``).

The config file
---------------

All settings that are specific to your Azure setup live in one INI-style file of
``key = value`` lines. It contains the credentials (or the choice of a credential
method) and the mapping from DNS zones to their location in Azure:

.. code-block:: ini
   :caption: /etc/letsencrypt/azure.ini

   dns_azure_sp_client_id = 912ce44a-0156-4669-ae22-c16a17d34ca5
   dns_azure_sp_client_secret = example-client-secret-not-real
   dns_azure_tenant_id = ed1090f3-ab18-4b12-816c-599af8a88cf7

   dns_azure_environment = "AzurePublicCloud"

   dns_azure_zone1 = example.com:/subscriptions/c135abce-d87d-48df-936c-15596c6968a5/resourceGroups/dns1
   dns_azure_zone2 = example.org:/subscriptions/99800903-fb14-4992-9aff-12eaf2744622/resourceGroups/dns2

The path is given with ``--dns-azure-config`` or entered interactively. Certbot
records the path for renewal but does not store the file's contents, so keep the file
in place.

Keys
~~~~

===============================================  =============================================
Key                                              Meaning
===============================================  =============================================
``dns_azure_zone<N>``                            Zone mapping, see below. At least one is
                                                 required; ``N`` is any unique number.
``dns_azure_environment``                        Azure cloud, see :ref:`azure-environment`.
                                                 Default ``AzurePublicCloud``.
``dns_azure_sp_client_id``                       Service principal (application) client id.
``dns_azure_sp_client_secret``                   Service principal client secret.
``dns_azure_sp_certificate_path``                Path to a PEM certificate with private key,
                                                 alternative to the client secret.
``dns_azure_tenant_id``                          Entra ID tenant id. Required for service
                                                 principals.
``dns_azure_msi_client_id``                      Client id of a user-assigned managed
                                                 identity.
``dns_azure_msi_system_assigned``                ``true`` to use the system-assigned
                                                 managed identity.
``dns_azure_use_cli_credentials``                ``true`` to use the Azure CLI login.
``dns_azure_use_workload_identity_credentials``  ``true`` to use Azure Workload Identity.
===============================================  =============================================

Exactly one authentication method should be configured. The methods and what each
one needs are described in :doc:`authentication`.

Zone mappings
-------------

Azure DNS zones can live in any resource group of any subscription, so the plugin
needs to be told where each zone is. Each ``dns_azure_zone<N>`` line maps a domain to
an Azure resource id:

.. code-block:: text

   dns_azure_zone1 = DOMAIN:RESOURCE_ID

- ``DOMAIN`` is the name of the DNS zone in Azure, for example ``example.com``.
- ``RESOURCE_ID`` is normally the id of the resource group that holds the zone:
  ``/subscriptions/<subscription id>/resourceGroups/<resource group>``. The zone name
  is taken from ``DOMAIN``.

  It can also be the id of a DNS zone (``.../providers/Microsoft.Network/dnszones/<zone>``)
  or even of a single TXT record set. Those forms redirect the validation record to a
  different zone or record and are explained in :doc:`dns-delegation`.

The resource group id can be looked up with the Azure CLI:

.. code-block:: bash

   az group show --name dns1 --query id --output tsv

How domains are matched
~~~~~~~~~~~~~~~~~~~~~~~

When certbot asks for a certificate for a name, the plugin picks the configured
``DOMAIN`` that the name equals or is a subdomain of, trying the longest configured
domain first. One mapping for ``example.com`` therefore covers ``www.example.com``,
``*.example.com`` and any deeper subdomain, as long as they are all served from the
``example.com`` zone. Matching happens on label boundaries: ``myexample.com`` is not
covered by ``example.com`` and needs its own mapping.

If a subdomain is its own zone in Azure (say ``dev.example.com`` is delegated to a
separate zone), add a mapping for it as well; the longer match wins and the TXT
record is created in the subdomain's zone.

A name that matches none of the configured domains fails with
``Domain <name> does not have a valid domain to resource group id mapping``.

.. _azure-environment:

Azure environment
-----------------

The plugin talks to the Azure public cloud by default. For sovereign clouds set
``dns_azure_environment`` in the config file or the ``AZURE_ENVIRONMENT`` environment
variable; the config file takes precedence. This changes both the Resource Manager
endpoint and the Entra ID authority used for authentication.

============================  ==========================================
Value                         Resource Manager endpoint
============================  ==========================================
``AzurePublicCloud``          https://management.azure.com/
``AzureUSGovernmentCloud``    https://management.usgovcloudapi.net/
``AzureChinaCloud``           https://management.chinacloudapi.cn/
``AzureGermanCloud``          https://management.microsoftazure.de/
============================  ==========================================

Protecting the config file
--------------------------

.. caution::
   Treat the config file like the password to your Azure account. Anyone who can
   read it can call the Azure API with these credentials, and anyone who can make
   certbot run with it can obtain certificates for every domain the identity has
   access to.

Restrict the file to the user that runs certbot:

.. code-block:: bash

   chmod 600 /etc/letsencrypt/azure.ini

Certbot warns with ``Unsafe permissions on configuration file`` every time it uses a
file that other users can read, including on renewal. The warning cannot be silenced
other than by fixing the permissions.

Where possible prefer a credential method without secrets in the file, such as a
managed identity or workload identity, see :doc:`authentication`.
