Installation
============

For Nginx Proxy Manager 2.16 or later there is nothing to install, see
:doc:`nginx-proxy-manager`. To replace the upstream package ``certbot-dns-azure``,
see :doc:`migrating`.

Requirements
------------

- Python 3.10 or newer (tested on 3.10 to 3.13).
- certbot 3.0 or newer. There is deliberately no upper bound, so the plugin never
  forces pip to downgrade an existing certbot.
- The Azure SDK packages (``azure-identity``, ``azure-mgmt-dns`` 8.x or 9.x,
  ``azure-core``) are installed automatically as dependencies.

The plugin must be installed into the same Python environment as certbot.

pip
---

A dedicated virtual environment keeps certbot and the plugin apart from the system
Python:

.. code-block:: bash

   python3 -m venv /opt/certbot
   /opt/certbot/bin/pip install certbot certbot-dns-azure-modern
   ln -s /opt/certbot/bin/certbot /usr/local/bin/certbot

If certbot already lives in a virtual environment, install the plugin with that
environment's ``pip``. Do not combine a certbot from the distribution's packages with
a plugin from PyPI (recent distributions refuse ``pip install`` into the system Python,
PEP 668); install certbot itself with pip as shown.

Docker
------

The repository contains a minimal ``Docker/Dockerfile`` based on Alpine that installs
certbot and the plugin from PyPI; no image is published, build it yourself:

.. code-block:: bash

   git clone https://github.com/cloudchristoph/certbot-dns-azure-modern.git
   cd certbot-dns-azure-modern
   docker build -t certbot-dns-azure -f Docker/Dockerfile Docker/
   docker run -it --rm \
     -v /etc/letsencrypt:/etc/letsencrypt \
     certbot-dns-azure \
     certbot certonly \
       --authenticator dns-azure \
       --dns-azure-config /etc/letsencrypt/azure.ini \
       --agree-tos --email admin@example.com --non-interactive \
       -d example.com -d '*.example.com'

.. _verify-installation:

Verify the installation
-----------------------

.. code-block:: bash

   certbot plugins --text

The output should start the plugin's entry with:

.. code-block:: text

   * dns-azure
   Description: Obtain certificates using a DNS TXT record (if you are using Azure
   for DNS).

If it is missing, see :ref:`plugin-not-listed`.
