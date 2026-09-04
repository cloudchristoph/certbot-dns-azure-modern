DNS delegation
==============

DNS delegation, also called DNS aliasing, lets a secondary zone answer the
``dns-01`` challenge on behalf of the primary one. To get a certificate for
``example.com`` while the validation happens in ``example.org``, create a CNAME
``_acme-challenge.example.com`` pointing at a record in ``example.org``. The ACME
server follows the CNAME and checks the TXT record it ends up at.

Certbot itself knows nothing about such CNAMEs; it always asks the plugin to create
``_acme-challenge.<name>``. This plugin therefore lets a zone mapping redirect where
that record is actually written.

Typical reasons for delegation:

- The primary zone is hosted somewhere without API access, or with a DNS provider
  that has no certbot plugin.
- Security: certbot should not get write access to the primary zone at all, or only
  to a single record.

The examples below use ``foo.com`` as the primary zone and ``bar.com`` as the zone
hosted in Azure that certbot writes to.

Redirecting to another zone
---------------------------

Goal: a certificate for ``test.foo.com``. Certbot will ask for the validation record
``_acme-challenge.test.foo.com``. Without API access to ``foo.com``, create this
CNAME there once, by hand:

.. code-block:: text

   _acme-challenge.test.foo.com.  CNAME  _acme-challenge.test.foo.com.bar.com.

Then map ``test.foo.com`` to the ``bar.com`` zone by using the **zone's** resource
id instead of the resource group's:

.. code-block:: ini

   dns_azure_zone1 = test.foo.com:/subscriptions/c135abce-d87d-48df-936c-15596c6968a5/resourceGroups/dns1/providers/Microsoft.Network/dnszones/bar.com

When the plugin is asked to create ``_acme-challenge.test.foo.com``, the target zone
is overridden to ``bar.com`` and the record is created there under the full name
``_acme-challenge.test.foo.com.bar.com``. That is why the CNAME above has to carry
the whole ``_acme-challenge.test.foo.com`` prefix in front of ``bar.com``.

Redirecting to a single record
------------------------------

Instead of granting certbot write access to a whole zone, you can point the mapping
at one specific TXT record set and grant the DNS Zone Contributor role on that record
only.

Again the goal is a certificate for ``test.foo.com``. This time the CNAME can point
at any name, it does not have to contain ``_acme-challenge``:

.. code-block:: text

   _acme-challenge.test.foo.com.  CNAME  test_validation.bar.com.

The mapping names the record set explicitly:

.. code-block:: ini

   dns_azure_zone1 = test.foo.com:/subscriptions/c135abce-d87d-48df-936c-15596c6968a5/resourceGroups/dns1/providers/Microsoft.Network/dnszones/bar.com/TXT/test_validation

This **requires** you to create the TXT record ``test_validation`` in ``bar.com`` up
front with the value ``-``, and to give certbot's identity write access to it:

.. code-block:: bash

   az network dns record-set txt add-record \
     --resource-group dns1 --zone-name bar.com \
     --record-set-name test_validation --value '-'

   az role assignment create \
     --assignee <identity> \
     --role "DNS Zone Contributor" \
     --scope /subscriptions/c135abce-d87d-48df-936c-15596c6968a5/resourceGroups/dns1/providers/Microsoft.Network/dnszones/bar.com/TXT/test_validation

Now both the zone and the record name are overridden; the plugin writes the
validation token into ``test_validation`` in ``bar.com``, which is exactly where
the ACME server ends up after following the CNAME.

Why the record must exist and is never deleted
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Role assignments on an individual record are attached to that resource. If the
plugin deleted the record after validation, the assignment would be gone as well and
the next renewal would fail with an authorization error. For this reason, whenever
a mapping contains a record id, the plugin does not delete the record on cleanup; it
resets its value to ``-`` (the value you were told to set initially).

Restricting permissions without delegation
------------------------------------------

The record-level mapping also works inside the primary zone, for setups that only
want to limit certbot's permissions and do not need a CNAME. For ``test.foo.com``,
create the TXT record ``_acme-challenge.test`` in the ``foo.com`` zone with the value
``-``, assign the role on that record, and map:

.. code-block:: ini

   dns_azure_zone1 = test.foo.com:/subscriptions/c135abce-d87d-48df-936c-15596c6968a5/resourceGroups/dns1/providers/Microsoft.Network/dnszones/foo.com/TXT/_acme-challenge.test

The zone stays ``foo.com`` and the record name is the one certbot would have used
anyway, but now the plugin only ever touches this one record and never deletes it.
