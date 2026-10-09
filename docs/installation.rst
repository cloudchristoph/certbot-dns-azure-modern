Installation
============

Requirements
------------

- Python 3.10 or newer (tested on 3.10 to 3.13).
- certbot 3.0 or newer. There is deliberately no upper bound, so the plugin never
  forces pip to downgrade an existing certbot.
- The Azure SDK packages (``azure-identity``, ``azure-mgmt-dns``, ``azure-core``) are
  installed automatically as dependencies.

The plugin has to be installed into the same Python environment as certbot itself,
otherwise certbot cannot find it.

pip
---

.. code-block:: bash

   pip install certbot certbot-dns-azure-modern

Replacing the upstream package
------------------------------

``certbot-dns-azure`` (upstream) and ``certbot-dns-azure-modern`` (this fork) ship the
same Python module and the same certbot entry point. Never install both at once;
replace the upstream package instead:

.. code-block:: bash

   pip uninstall certbot-dns-azure
   pip install -U certbot certbot-dns-azure-modern

The ``-U`` matters: if the upstream package already downgraded certbot and acme to
3.3.0, installing the fork on top does not undo that. Upgrading certbot explicitly
(or recreating the virtual environment) does.

Nginx Proxy Manager
-------------------

Nginx Proxy Manager 2.16.0 and later use this package for the "Azure" DNS provider
(`NginxProxyManager#5831 <https://github.com/NginxProxyManager/nginx-proxy-manager/pull/5831>`_).
Nothing needs to be installed: pick "Azure" as DNS provider in the web UI and paste the
content of the config file into the credentials text box, see :doc:`configuration`.
Nginx Proxy Manager installs the plugin with ``pip`` into its bundled certbot
environment on first use.

Nginx Proxy Manager 2.15.x still installs the broken upstream package. Upgrade to
2.16.0 or later and recreate the container, so that a certbot downgraded by the
upstream plugin is not left behind:

.. code-block:: bash

   docker compose pull && docker compose up -d --force-recreate

If you used the earlier workaround and bind-mounted a patched
``/app/certbot/dns-plugins.json`` into the container, remove that volume when
upgrading. The patched copy replaces the whole plugin list of the image, so it would
also hide later updates to other DNS plugins.

Verify inside the container that certbot kept the image version and sees the plugin:

.. code-block:: bash

   docker exec nginx-proxy-manager bash -c \
     '. /opt/certbot/bin/activate && certbot --version && certbot plugins --text | grep -A1 dns-azure'

The plugin is only installed after the first certificate request with the "Azure"
provider; before that, ``dns-azure`` is not listed.

Docker
------

The repository contains a minimal ``Docker/Dockerfile`` based on Alpine that installs
certbot and the plugin from PyPI:

.. code-block:: bash

   docker build -t certbot-dns-azure -f Docker/Dockerfile Docker/
   docker run -it --rm \
     -v /etc/letsencrypt:/etc/letsencrypt \
     certbot-dns-azure \
     certbot certonly \
       --authenticator dns-azure \
       --dns-azure-config /etc/letsencrypt/azure.ini \
       --agree-tos --email admin@example.com --non-interactive \
       -d example.com -d '*.example.com'

Snap
----

The ``certbot-dns-azure`` snap in the Snap Store is published by the upstream author
and still ships 2.6.1. This fork does not publish a snap. Use pip or Docker instead.

Verifying the installation
--------------------------

.. code-block:: bash

   certbot plugins --text

The output should list the plugin:

.. code-block:: text

   * dns-azure
   Description: Obtain certificates using a DNS TXT record (if you are using Azure
   for DNS).
   Interfaces: Authenticator, Plugin
   Entry point: dns-azure = certbot_dns_azure._internal.dns_azure:Authenticator

If it is missing, the plugin was installed into a different Python environment than
certbot. Check with ``pip show certbot certbot-dns-azure-modern`` that both report the
same location.
