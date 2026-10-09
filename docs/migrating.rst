Switching from certbot-dns-azure
================================

The upstream package ``certbot-dns-azure`` (last release 2.6.1, December 2024) pins
``certbot<4.0``. Installing it next to a current certbot makes pip downgrade certbot
and acme to 3.3.0, which fails to import with pyOpenSSL 26 or newer
(``AttributeError: module 'OpenSSL.crypto' has no attribute 'X509Extension'``). The
upstream fix (`#65 <https://github.com/terricain/certbot-dns-azure/pull/65>`_) has been
waiting for a maintainer since October 2025.

This fork is a drop-in replacement: the Python module (``certbot_dns_azure``), the
plugin name (``dns-azure``), all options and the config file format are unchanged.
Existing config files and renewal configurations keep working. Only the package name
on PyPI differs.

Replace the package
-------------------

Both packages install the same module, so replace one with the other. Run these with
the ``pip`` of the environment certbot is installed in:

.. code-block:: bash

   pip uninstall -y certbot-dns-azure
   pip install -U certbot certbot-dns-azure-modern
   pip install --force-reinstall --no-deps certbot-dns-azure-modern

.. warning::
   Do not skip the ``-U``: if the upstream package already downgraded certbot and acme
   to 3.3.0, installing the fork alone does not undo that. If both packages were
   installed, uninstalling the upstream one also deletes the module files they share;
   the last line puts them back. It is harmless otherwise.

Never install both packages at once. Recreating the virtual environment from scratch
works as well.

Check the result with ``certbot --version`` and ``certbot plugins --text``, see
:ref:`verify-installation`.

Nginx Proxy Manager
-------------------

Nginx Proxy Manager 2.16.0 and later already use this fork; upgrade and recreate the
container, see :doc:`nginx-proxy-manager`.

Snap
----

The ``certbot-dns-azure`` snap in the Snap Store is published by the upstream author
and still ships 2.6.1. This fork does not publish a snap. Remove the snaps first
(``snap remove certbot-dns-azure certbot``) so their renewal timer stops, then install
certbot and the plugin with pip or build the Dockerfile, see :doc:`installation`.
