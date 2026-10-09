DNS delegation and least privilege
==================================

Certbot always asks the plugin for the validation record ``_acme-challenge.<name>``.
A zone mapping can redirect where that record is written: to another zone, or to a
single, pre-created TXT record. Combined with a CNAME in the primary zone (DNS
delegation, also called DNS aliasing), the ACME server follows the CNAME and checks
the TXT record it ends up at.

Use this when:

- the primary zone has no API access, or is hosted with a provider that has no
  certbot plugin, or
- certbot should not get write access to the primary zone at all, or only to a single
  record.

The examples use ``example.com`` as the primary zone and ``example.net`` as the Azure
DNS zone that certbot writes to, both in resource group ``dns1``.

Redirect to another zone
------------------------

Goal: a certificate for ``test.example.com`` while certbot only writes to
``example.net``.

1. Map the name to the **zone's** resource ID instead of the resource group's:

   .. code-block:: ini

      dns_azure_zone1 = test.example.com:/subscriptions/<subscription-id>/resourceGroups/dns1/providers/Microsoft.Network/dnszones/example.net

2. The plugin now writes the TXT record ``_acme-challenge.test.example.com`` into the
   zone ``example.net``. Its full name is therefore
   ``_acme-challenge.test.example.com.example.net``.

3. Create this CNAME once in ``example.com``, by hand or at your DNS provider:

   .. code-block:: text

      _acme-challenge.test.example.com.  CNAME  _acme-challenge.test.example.com.example.net.

   Add one such CNAME per name in the certificate; ``*.test.example.com`` shares the
   one for ``test.example.com``.

The identity needs DNS Zone Contributor on ``example.net`` only.

Redirect to a single record
---------------------------

Goal: the same certificate, but certbot may write to one TXT record only.

1. Create the TXT record ``validation`` in ``example.net`` with the value ``-``, and
   assign DNS Zone Contributor on that record alone:

   .. code-block:: bash

      az network dns record-set txt add-record \
        --resource-group dns1 --zone-name example.net \
        --record-set-name validation --value '-'

      az role assignment create \
        --assignee-object-id <object-id> --assignee-principal-type ServicePrincipal \
        --role "DNS Zone Contributor" \
        --scope /subscriptions/<subscription-id>/resourceGroups/dns1/providers/Microsoft.Network/dnszones/example.net/TXT/validation

   For an Azure CLI login use ``--assignee-principal-type User``, see
   :ref:`required-permissions`.

2. Map the name to that record:

   .. code-block:: ini

      dns_azure_zone1 = test.example.com:/subscriptions/<subscription-id>/resourceGroups/dns1/providers/Microsoft.Network/dnszones/example.net/TXT/validation

3. Point the CNAME in ``example.com`` at the record; the target name is free:

   .. code-block:: text

      _acme-challenge.test.example.com.  CNAME  validation.example.net.

.. important::
   The record must exist before the first certbot run; the identity is not allowed to
   create it.

Least privilege without delegation
----------------------------------

The record mapping also works inside the primary zone, without a CNAME. Create the TXT
record ``_acme-challenge.test`` in ``example.com`` with the value ``-``, assign the role
on that record as above, and map:

.. code-block:: ini

   dns_azure_zone1 = test.example.com:/subscriptions/<subscription-id>/resourceGroups/dns1/providers/Microsoft.Network/dnszones/example.com/TXT/_acme-challenge.test

The record name is the one certbot would have used anyway, but the plugin only ever
touches this one record.

Record mappings and subdomains
------------------------------

A mapping that names a record serves every name it matches from that one record:
``test.example.com``, ``*.test.example.com`` and also deeper names such as
``www.test.example.com``. The first two validate at
``_acme-challenge.test.example.com`` and work. A deeper name validates at its own
``_acme-challenge`` name: with delegation, give it its own CNAME to the same record;
without delegation, give it its own mapping and record.

Why the record is never deleted
-------------------------------

A role assignment on a single record is tied to that resource. If the plugin deleted
the record after validation, the next renewal would fail with an authorization error.
For a record mapping the plugin therefore removes only its own token and resets the
value to ``-`` once no tokens are left. Each write also sets the record's TTL to
``--dns-azure-ttl``.
