Development
===========

Source, issues and pull requests live at
https://github.com/cloudchristoph/certbot-dns-azure-modern. The plugin is a single
module, ``certbot_dns_azure/_internal/dns_azure.py``, implementing certbot's
:class:`certbot.plugins.dns_common.DNSAuthenticator`. There is no public Python API
beyond the certbot plugin interface.

Local setup
-----------

.. code-block:: bash

   git clone https://github.com/cloudchristoph/certbot-dns-azure-modern.git
   cd certbot-dns-azure-modern
   python -m venv .venv && . .venv/bin/activate
   pip install certbot 'azure-identity>=1.19.0' 'azure-mgmt-dns>=8.2.0' 'azure-core>=1.32.0' pytest build
   pip install --no-deps -e .

Unit tests
----------

The unit tests mock the Azure SDK and run without any Azure access:

.. code-block:: bash

   python -m pytest -q tests/ -W error::DeprecationWarning

CI runs them on Python 3.10 to 3.13 against certbot 3.x and the latest release, and
against both supported ``azure-mgmt-dns`` lines (8.x and 9.x). When touching
compatibility, also test the oldest supported line locally (``certbot>=3.0,<4.0``
together with ``pyOpenSSL<26``, and ``azure-mgmt-dns<9``).

Integration tests
-----------------

``azure_tests/`` issues real certificates from the Let's Encrypt staging
environment against dedicated Azure DNS zones. They need a zone whose name starts
with ``certbot-test.`` (the test module refuses anything else, so it can never touch
a production zone) plus the following environment variables:

.. code-block:: bash

   export AZURE_TENANT_ID=... AZURE_SUBSCRIPTION_ID=... \
          AZURE_DNS_RESOURCE_GROUP=... AZURE_DNS_TEST_DOMAIN=certbot-test.example.com \
          EMAIL=you@example.com
   pytest -rA azure_tests/

The tests authenticate with the Azure CLI credential of the current login and only
delete ``_acme-challenge*`` TXT records that they created themselves. The required
zone layout (a base zone with static CNAME/TXT records for the delegation tests plus
the delegated ``zone1`` and ``zone2``) is described at the top of
``azure_tests/integration_test.py``.

In CI the integration tests are a required check for pull requests that change code
(documentation-only changes skip them), run again on release tags before publishing,
and once a week against the latest certbot and Azure SDK releases to catch breaking
upstream changes early.

Building the docs
-----------------

.. code-block:: bash

   pip install -r docs/requirements.txt
   sphinx-build -W -b html docs docs/_build/html

The docs are published to GitHub Pages by ``.github/workflows/docs.yml`` on every
push to ``main``. Pull requests only build them.

Release checklist
-----------------

1. Bump ``version`` in ``setup.py`` and update ``CHANGELOG.md``.
2. Open a pull request, wait for the checks and merge it; ``main`` only accepts
   changes through pull requests.
3. Tag with the bare version (``git tag 2.7.0 && git push origin 2.7.0``). The build
   job refuses a tag that differs from the ``setup.py`` version.
4. The workflow builds the wheel and sdist, runs the integration tests, publishes to
   PyPI via trusted publishing and creates the GitHub release.
