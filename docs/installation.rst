Installation
============

Requirements
------------

- Python 3.9 or newer (tested on 3.11 to 3.13).
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

Nginx Proxy Manager installs DNS plugins on demand with ``pip`` into its bundled
certbot environment, using the package names from ``/app/certbot/dns-plugins.json``.
Until the fork is referenced there upstream, override the ``azure`` entry:

1. Copy the file out of the running container:

   .. code-block:: bash

      docker cp nginx-proxy-manager:/app/certbot/dns-plugins.json ./dns-plugins.json

2. Edit the ``azure`` entry so that it points at this package:

   .. code-block:: json

      "azure": {
        "dependencies": "",
        "package_name": "certbot-dns-azure-modern",
        "version": "~=2.7.0"
      }

3. Bind-mount the patched copy over the original and recreate the container, for
   example with Docker Compose:

   .. code-block:: yaml

      services:
        app:
          image: jc21/nginx-proxy-manager:latest
          volumes:
            - ./data:/data
            - ./letsencrypt:/etc/letsencrypt
            - ./dns-plugins.json:/app/certbot/dns-plugins.json:ro

   .. code-block:: bash

      docker compose up -d --force-recreate

   Recreating the container is required: the certbot environment lives inside the
   container, and a fresh one guarantees that no downgraded certbot from an earlier
   attempt with the upstream plugin is left behind.

4. Request or renew a certificate with the "Azure" DNS provider in the web UI as
   usual. The credentials text box takes the content of the config file, see
   :doc:`configuration`.

Verify inside the container that certbot kept the image version and sees the plugin:

.. code-block:: bash

   docker exec nginx-proxy-manager bash -c \
     '. /opt/certbot/bin/activate && certbot --version && certbot plugins --text | grep -A1 dns-azure'

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
