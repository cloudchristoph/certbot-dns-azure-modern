Usage
=====

All examples assume a config file at ``/etc/letsencrypt/azure.ini`` as described in
:doc:`configuration`.

Obtaining a certificate
-----------------------

.. code-block:: bash

   certbot certonly \
     --authenticator dns-azure \
     --dns-azure-config /etc/letsencrypt/azure.ini \
     -d example.com

Several names, including names from different zones, can go into one certificate
as long as every zone has a mapping in the config file:

.. code-block:: bash

   certbot certonly \
     --authenticator dns-azure \
     --dns-azure-config /etc/letsencrypt/azure.ini \
     -d example.com \
     -d www.example.com \
     -d example.org

Wildcard certificates require the ``dns-01`` challenge, so they are a natural fit.
Quote the name to keep the shell from expanding it:

.. code-block:: bash

   certbot certonly \
     --authenticator dns-azure \
     --dns-azure-config /etc/letsencrypt/azure.ini \
     -d example.com \
     -d '*.example.com'

Non-interactive use
-------------------

For scripts, containers and cron jobs, add the usual certbot options so it never
prompts:

.. code-block:: bash

   certbot certonly \
     --authenticator dns-azure \
     --dns-azure-config /etc/letsencrypt/azure.ini \
     --non-interactive \
     --agree-tos \
     --email admin@example.com \
     -d example.com

Renewal
-------

Certbot stores the plugin name and the path of the config file in the renewal
configuration under ``/etc/letsencrypt/renewal/``. A plain

.. code-block:: bash

   certbot renew

renews all certificates, including those issued through this plugin, as long as the
config file is still at the recorded path and the credentials in it are valid.
Nothing needs to be passed on the command line.

Propagation time
----------------

After creating the TXT record, the plugin waits ``--dns-azure-propagation-seconds``
(default 10) before certbot asks the ACME server to validate. Azure DNS publishes
changes within seconds, so the default is usually fine. Increase it if validation
fails intermittently, for example when the zone is behind a resolver with
aggressive caching:

.. code-block:: bash

   certbot certonly --authenticator dns-azure --dns-azure-propagation-seconds 30 ...

What the plugin does
--------------------

For every name in the certificate request the plugin

1. picks the matching zone mapping from the config file (longest matching domain
   wins, see :doc:`configuration`),
2. creates or updates the TXT record set ``_acme-challenge.<name>`` in that zone
   with the validation token and a TTL of 120 seconds; existing values in the
   record set are preserved, so several certbot runs against the same name can
   overlap,
3. waits for the propagation time and lets certbot complete the challenge,
4. removes its token from the record set again and deletes the record set once it
   holds no other values.

When the mapping points at a specific TXT record instead of a zone (see
:doc:`dns-delegation`), the record is never deleted; its value is reset to ``-``
so that role assignments on the record survive.
