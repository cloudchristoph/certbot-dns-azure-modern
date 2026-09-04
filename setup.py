from setuptools import find_packages
from setuptools import setup

version = '2.7.0'

install_requires = [
    'azure-identity>=1.19.0',
    # 8.x and 9.x are both supported; DnsManagementClient is constructed with keyword
    # arguments because 9.x changed the positional signature.
    'azure-mgmt-dns>=8.2.0',
    'azure-core>=1.32.0',
    # No upper bound: the old '<4.0' cap forced pip to downgrade certbot/acme in
    # shared venvs (e.g. Nginx Proxy Manager) and broke certbot on import.
    'certbot>=3.0',
]

with open("README.md") as f:
    long_description = f.read()

docs_extras = [
    'Sphinx>=7',
    'sphinx_rtd_theme',
    'myst-parser',  # renders CHANGELOG.md on the docs site
]

setup(
    name='certbot-dns-azure-modern',
    version=version,
    description="Azure DNS Authenticator plugin for Certbot (maintained fork of certbot-dns-azure)",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='https://github.com/cloudchristoph/certbot-dns-azure-modern',
    project_urls={
        'Source': 'https://github.com/cloudchristoph/certbot-dns-azure-modern',
        'Issues': 'https://github.com/cloudchristoph/certbot-dns-azure-modern/issues',
        'Upstream': 'https://github.com/terricain/certbot-dns-azure',
    },
    author="Terri Cain",
    author_email='terri@dolphincorp.co.uk',
    maintainer="Christoph Vollmann",
    maintainer_email='me@cvollmann.de',
    license='Apache License 2.0',
    python_requires='>=3.9',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Plugins',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Security',
        'Topic :: System :: Installation/Setup',
        'Topic :: System :: Networking',
        'Topic :: System :: Systems Administration',
        'Topic :: Utilities',
    ],

    packages=find_packages(),
    include_package_data=True,
    install_requires=install_requires,
    extras_require={
        'docs': docs_extras,
    },
    entry_points={
        'certbot.plugins': [
            'dns-azure = certbot_dns_azure._internal.dns_azure:Authenticator',
        ],
    },
)
