Authentication
==============

The plugin authenticates against Azure with the ``azure-identity`` library and
supports six credential methods. Configure exactly one of them in the config file;
if several are present, they are tried in the order of this page (Azure CLI first,
system-assigned managed identity last). Zones that need different identities, for
example because they live in different tenants, get their own credential set in an
INI section, see :ref:`credential-sets`.

Required permissions
--------------------

Whichever identity is used needs the built-in role **DNS Zone Contributor** on the
DNS zone, or on the resource group that contains it. This is the only permission the
plugin needs; it creates, updates and deletes TXT record sets and reads nothing else.

.. code-block:: bash

   az role assignment create \
     --assignee <object id or client id of the identity> \
     --role "DNS Zone Contributor" \
     --scope /subscriptions/<subscription id>/resourceGroups/dns1/providers/Microsoft.Network/dnszones/example.com

Role assignments can take a few minutes to become effective.

If granting write access to a whole zone is too much, the plugin can be limited to a
single TXT record; see :doc:`dns-delegation`.

Azure CLI
---------

Uses the login session of the Azure CLI (``az login``). Convenient on a workstation
or a management host where the CLI is installed and logged in anyway. No secrets are
stored in the config file.

.. code-block:: ini

   dns_azure_use_cli_credentials = true

   dns_azure_zone1 = example.com:/subscriptions/c135abce-d87d-48df-936c-15596c6968a5/resourceGroups/dns1

``dns_azure_tenant_id`` may be added to pin the tenant when the CLI is logged in to
several. Note that the user running certbot (usually root on renewal) must be the
one who ran ``az login``.

Workload identity
-----------------

For pods on Azure Kubernetes Service with
`workload identity <https://learn.microsoft.com/azure/aks/workload-identity-overview>`_
enabled. The identity, tenant and token file are injected into the pod as
environment variables by the AKS webhook, so the config file only switches the
method on.

.. code-block:: ini

   dns_azure_use_workload_identity_credentials = true

   dns_azure_zone1 = example.com:/subscriptions/c135abce-d87d-48df-936c-15596c6968a5/resourceGroups/dns1

Service principal with client secret
------------------------------------

The classic choice for hosts outside Azure, such as a home server or a container
running Nginx Proxy Manager. Create an app registration with a secret and assign the
role in one step:

.. code-block:: bash

   az ad sp create-for-rbac \
     --name certbot-dns-azure \
     --role "DNS Zone Contributor" \
     --scopes /subscriptions/<subscription id>/resourceGroups/dns1

The command prints ``appId`` (client id), ``password`` (client secret) and ``tenant``.

.. code-block:: ini

   dns_azure_sp_client_id = 912ce44a-0156-4669-ae22-c16a17d34ca5
   dns_azure_sp_client_secret = example-client-secret-not-real
   dns_azure_tenant_id = ed1090f3-ab18-4b12-816c-599af8a88cf7

   dns_azure_zone1 = example.com:/subscriptions/c135abce-d87d-48df-936c-15596c6968a5/resourceGroups/dns1

Client secrets expire (two years by default); note the expiry date and rotate the
secret before renewals start failing.

Service principal with certificate
----------------------------------

Same as above, but the app registration authenticates with a certificate instead of
a secret. The file must be a PEM containing both the private key and the
certificate, readable by the user that runs certbot.

.. code-block:: ini

   dns_azure_sp_client_id = 912ce44a-0156-4669-ae22-c16a17d34ca5
   dns_azure_sp_certificate_path = /etc/letsencrypt/certbot-dns-azure.pem
   dns_azure_tenant_id = ed1090f3-ab18-4b12-816c-599af8a88cf7

   dns_azure_zone1 = example.com:/subscriptions/c135abce-d87d-48df-936c-15596c6968a5/resourceGroups/dns1

User-assigned managed identity
------------------------------

For virtual machines, container instances, App Service and similar Azure resources
that have a user-assigned managed identity attached. Assign the role to the identity
and reference it by its client id. No secrets are stored.

.. code-block:: ini

   dns_azure_msi_client_id = 912ce44a-0156-4669-ae22-c16a17d34ca5

   dns_azure_zone1 = example.com:/subscriptions/c135abce-d87d-48df-936c-15596c6968a5/resourceGroups/dns1

System-assigned managed identity
--------------------------------

Same as above for the resource's own system-assigned identity. Nothing to reference;
just switch the method on.

.. code-block:: ini

   dns_azure_msi_system_assigned = true

   dns_azure_zone1 = example.com:/subscriptions/c135abce-d87d-48df-936c-15596c6968a5/resourceGroups/dns1

Sovereign clouds
----------------

All methods work against Azure US Government, Azure China and the other
environments; set ``dns_azure_environment`` as described in
:ref:`azure-environment`. It selects the Resource Manager endpoint for every method
and the sign-in authority for service principals. Managed identities, the Azure CLI
and workload identity obtain their tokens from the surrounding platform, which
already knows its cloud.
