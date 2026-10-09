Authentication
==============

The plugin signs in to Azure with the ``azure-identity`` library. The config file
selects one of six methods; the examples on this page show only the authentication
keys, add your ``dns_azure_zone<N>`` lines as described in :doc:`configuration`.

Which method?
-------------

.. list-table::
   :header-rows: 1
   :widths: 55 45

   * - Where certbot runs
     - Method
   * - Outside Azure: home server, NAS, Nginx Proxy Manager, other clouds
     - Service principal, with a certificate if possible, else a client secret
   * - Azure VM, scale set, container instance, App Service, Container Apps
     - User-assigned managed identity (system-assigned works too)
   * - On-premises server connected with Azure Arc
     - System-assigned managed identity
   * - Kubernetes with Microsoft Entra Workload ID (AKS)
     - Workload identity
   * - Interactive use on a workstation
     - Azure CLI

Managed identities and workload identity store no secret at all; prefer them where
they are available.

.. note::
   Each credential set uses exactly one method. If keys for several methods are
   present, the first one in this order wins and the others are ignored, with no
   fallback if it fails: Azure CLI, workload identity, service principal with secret,
   service principal with certificate, user-assigned managed identity,
   system-assigned managed identity. A leftover ``dns_azure_use_cli_credentials =
   true`` therefore overrides a service principal. Zones that need different
   identities get their own credential set, see :ref:`credential-sets`.

.. _required-permissions:

Required permissions
--------------------

The plugin reads, creates, updates and deletes the TXT record sets used for validation
(the ``_acme-challenge`` records, or the record named in a record mapping) and touches
nothing else. Assign the built-in role **DNS Zone Contributor** to the
identity; broader roles such as Contributor or Owner are not needed. Keep the scope as
small as possible:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Scope
     - Covers
   * - DNS zone (recommended)
     - That zone only.
   * - Resource group
     - Every zone in the group, including zones added later.
   * - Single TXT record set
     - Only that record. Needs a record mapping, see :doc:`dns-delegation`.

.. code-block:: bash

   az role assignment create \
     --assignee-object-id <object-id> --assignee-principal-type ServicePrincipal \
     --role "DNS Zone Contributor" \
     --scope /subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.Network/dnszones/example.com

``<object-id>`` is the identity's object (principal) ID, for a service principal
``az ad sp show --id <app-id> --query id -o tsv``. In the portal, use **DNS zone →
Access control (IAM) → Add role assignment**. New assignments can take up to 10
minutes to become effective.

Service principal with client secret
------------------------------------

The simplest choice for hosts outside Azure. One command creates the app
registration and its secret and assigns the role on the zone:

.. code-block:: bash

   az ad sp create-for-rbac --name certbot-dns-azure \
     --role "DNS Zone Contributor" \
     --scopes /subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.Network/dnszones/example.com

It prints ``appId`` (client ID, ``<app-id>`` in the commands below), ``password``
(client secret) and ``tenant`` (tenant ID). The portal steps are described in :doc:`nginx-proxy-manager`.

.. code-block:: ini

   dns_azure_sp_client_id = 912ce44a-0156-4669-ae22-c16a17d34ca5
   dns_azure_sp_client_secret = example-client-secret-not-real
   dns_azure_tenant_id = ed1090f3-ab18-4b12-816c-599af8a88cf7

.. _secret-expiry:

Secret expiry and rotation
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. warning::
   Client secrets expire: after one year with ``az ad sp create-for-rbac`` (change it
   with ``--years``), after the period chosen in the portal (at most 24 months).
   Renewals fail from that day on, typically with ``AADSTS7000222``.

Check the expiry date and rotate without downtime by adding a new secret before
removing the old one:

.. code-block:: bash

   az ad app credential list --id <app-id> \
     --query "[].{name:displayName, id:keyId, end:endDateTime}" -o table
   az ad app credential reset --id <app-id> --append --display-name certbot-2027 --years 1

Put the printed ``password`` into the config file, test with ``certbot renew
--dry-run``, then delete the old secret with ``az ad app credential delete --id
<app-id> --key-id <old-key-id>``.

Service principal with certificate
----------------------------------

Same as above, but the app registration authenticates with a certificate, which
Microsoft recommends over secrets. Create the service principal with a certificate
in one step:

.. code-block:: bash

   az ad sp create-for-rbac --name certbot-dns-azure --create-cert --years 1 \
     --role "DNS Zone Contributor" \
     --scopes /subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.Network/dnszones/example.com

The command writes a PEM file with the certificate and the private key and prints
its path. For an existing app registration use ``az ad app credential reset --id
<app-id> --create-cert --append``. Move the file next to the config file and make it
readable for root only (``chmod 600``).

.. code-block:: ini

   dns_azure_sp_client_id = 912ce44a-0156-4669-ae22-c16a17d34ca5
   dns_azure_sp_certificate_path = /etc/letsencrypt/certbot-dns-azure.pem
   dns_azure_tenant_id = ed1090f3-ab18-4b12-816c-599af8a88cf7

The file may be PEM or PKCS#12 (``.pfx``) and must contain both the certificate and
the private key. The key must not be password-protected. Certificates expire as well;
rotate them like secrets.

User-assigned managed identity
------------------------------

For Azure resources with a user-assigned managed identity attached: virtual machines,
scale sets, container instances, App Service, Container Apps. Assign the role to the
identity's principal ID and reference the identity by its client ID:

.. code-block:: bash

   az identity show --name <identity> --resource-group <resource-group> \
     --query "{clientId:clientId, principalId:principalId}"

.. code-block:: ini

   dns_azure_msi_client_id = 912ce44a-0156-4669-ae22-c16a17d34ca5

Every process on the resource that can reach the identity endpoint can use the
identity. A user-assigned identity dedicated to certbot keeps that exposure limited
to DNS.

System-assigned managed identity
--------------------------------

Uses the resource's own identity. Besides Azure resources this also works on
on-premises servers connected with Azure Arc; there, certbot must run as root or as a
member of the ``himds`` group. Assign the role to the resource's identity and switch
the method on:

.. code-block:: ini

   dns_azure_msi_system_assigned = true

Workload identity
-----------------

For pods in Kubernetes with
`Microsoft Entra Workload ID <https://learn.microsoft.com/azure/aks/workload-identity-overview>`_
(AKS, also Azure Arc-enabled Kubernetes). Its webhook injects ``AZURE_CLIENT_ID``,
``AZURE_TENANT_ID`` and ``AZURE_FEDERATED_TOKEN_FILE`` into labelled pods; the linked
guide covers the service account and federated credential. The config file only
switches the method on:

.. code-block:: ini

   dns_azure_use_workload_identity_credentials = true

``dns_azure_tenant_id``, if set, overrides ``AZURE_TENANT_ID``.

Azure CLI
---------

Uses the Azure CLI login (``az login``) of the user that runs certbot. No secrets are
stored in the config file.

.. code-block:: ini

   dns_azure_use_cli_credentials = true

.. note::
   Intended for interactive and one-off use. A user login is subject to Microsoft's
   mandatory multifactor authentication for Azure Resource Manager write operations,
   and its session expires, so unattended renewals start failing sooner or later. For
   renewals use a managed identity or a service principal instead.

``dns_azure_tenant_id`` pins the tenant when the CLI is logged in to several. The
token cache lives in ``~/.azure`` of the user that ran ``az login``; renewals from
cron or systemd usually run as root and need that user's login. For sovereign
clouds, run ``az cloud set --name <cloud>`` before ``az login``.
