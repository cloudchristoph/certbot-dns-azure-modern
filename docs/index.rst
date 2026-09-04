certbot-dns-azure-modern
========================

Azure DNS authenticator plugin for `Certbot <https://certbot.eff.org/>`_.

This is the maintained fork of
`terricain/certbot-dns-azure <https://github.com/terricain/certbot-dns-azure>`_,
published on PyPI as
`certbot-dns-azure-modern <https://pypi.org/project/certbot-dns-azure-modern/>`_.
The Python module (``certbot_dns_azure``), the plugin name (``dns-azure``), all
command-line flags and the config file format are unchanged, so it is a drop-in
replacement. See the
`README <https://github.com/cloudchristoph/certbot-dns-azure-modern#readme>`_ for the
background and for Nginx Proxy Manager instructions.

Installation
------------

.. code-block:: bash

   pip install certbot certbot-dns-azure-modern

If the upstream package is already installed, replace it instead of stacking both
(they ship the same module):

.. code-block:: bash

   pip uninstall certbot-dns-azure && pip install -U certbot certbot-dns-azure-modern

Verify that certbot sees the plugin:

.. code-block:: bash

   certbot plugins --text | grep -A1 dns-azure

.. toctree::
   :maxdepth: 2
   :caption: Contents:

.. automodule:: certbot_dns_azure
   :members:

.. toctree::
   :maxdepth: 1

   api


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
