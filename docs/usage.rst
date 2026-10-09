Usage
=====

The examples assume a config file at ``/etc/letsencrypt/azure.ini`` as described in
:doc:`configuration`.

Get a certificate
-----------------

.. code-block:: bash

   certbot certonly \
     --authenticator dns-azure \
     --dns-azure-config /etc/letsencrypt/azure.ini \
     -d example.com -d '*.example.com' -d example.org

- One certificate can hold several names, also from different zones, as long as every
  zone has a mapping in the config file.
- Wildcards need the ``dns-01`` challenge, which is what this plugin provides. Quote
  them so the shell does not expand the ``*``.
- In scripts and containers add ``--non-interactive --agree-tos --email
  admin@example.com`` so certbot never prompts.

Test first
----------

Add ``--dry-run`` to run the whole process against the Let's Encrypt staging server
without saving a certificate. Staging has much higher rate limits, so use it while
you get the configuration right.

.. _renewal:

Renewal
-------

Certbot stores the plugin name and the path of the config file in
``/etc/letsencrypt/renewal/``, so a plain ``certbot renew`` renews every certificate,
including those issued through this plugin, as long as the config file is still at
that path and its credentials are valid.

Installing certbot with pip does not schedule renewals. Run ``certbot renew`` twice a
day, for example with ``/etc/cron.d/certbot``:

.. code-block:: text

   0 3,15 * * * root /opt/certbot/bin/certbot renew --quiet

See `Setting up automated renewal
<https://eff-certbot.readthedocs.io/en/stable/using.html#setting-up-automated-renewal>`_
in the certbot documentation for systemd timers. ``certbot renew --dry-run`` tests the
renewal of all certificates, which is worth doing after rotating a secret.

.. _propagation:

Propagation time
----------------

After creating the TXT record the plugin waits ``--dns-azure-propagation-seconds``
(default 10) before the ACME server validates; certbot does not poll DNS. Microsoft
states that changes reach all Azure DNS name servers within 60 seconds, usually much
faster, so the default normally works. If validation fails intermittently, wait
longer:

.. code-block:: bash

   certbot certonly --authenticator dns-azure --dns-azure-propagation-seconds 60 ...

How it works
------------

For every name in the certificate the plugin:

1. Picks the zone mapping (longest matching domain, see :doc:`configuration`).
2. Adds the validation token to the TXT record set ``_acme-challenge.<name>`` with the
   TTL of ``--dns-azure-ttl`` (default 120 seconds). Existing values are kept, so
   overlapping certbot runs for the same name do not overwrite each other.
3. Waits for the propagation time while certbot completes the challenge.
4. Removes its token again and deletes the record set once no values are left.

A mapping that names a single TXT record works differently: that record is never
deleted, see :doc:`dns-delegation`.
