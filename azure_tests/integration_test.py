"""
Integration tests against a real Azure DNS setup and the Let's Encrypt staging CA.

Required environment:

``AZURE_TENANT_ID``          tenant of the identity ``az login`` is using
``AZURE_SUBSCRIPTION_ID``    subscription that holds the test zones
``AZURE_DNS_RESOURCE_GROUP`` resource group that holds the test zones
``AZURE_DNS_TEST_DOMAIN``    base domain, must be ``certbot-test.<domain>``
``EMAIL``                    ACME account email

Expected zones (all in the resource group above):

* ``<base>`` - delegates the two child zones and holds the static records for the
  delegation tests:
  ``_acme-challenge      CNAME _acme-challenge.<base>.zone2.<base>``,
  ``_acme-challenge.test CNAME other.<base>`` and ``other TXT "-"``
* ``zone1.<base>``, ``zone2.<base>`` - the plugin writes ``_acme-challenge*`` TXT
  records here; leftovers from failed runs are removed, nothing else is touched

What the four tests cover: plain dns-01 in one zone, one certificate spanning two
zones, a zone override (challenge for ``<base>`` written into ``zone2``) and a
record override (challenge written into the fixed TXT record ``other``).

Authentication uses the Azure CLI credential (``az login``), or a client secret
when ``AZURE_CLIENT_SECRET`` is set. Certificates come from the staging CA
(``--test-cert``) unless ``CERTBOT_SERVER`` points elsewhere.
"""
import os
import subprocess
import uuid
from typing import TYPE_CHECKING, List, Tuple

import pytest
from azure.mgmt.dns import DnsManagementClient
from azure.identity import ClientSecretCredential, AzureCliCredential

if TYPE_CHECKING:
    import pathlib

REQUIRED_ENV = ['AZURE_TENANT_ID', 'AZURE_SUBSCRIPTION_ID', 'AZURE_DNS_RESOURCE_GROUP',
                'AZURE_DNS_TEST_DOMAIN', 'EMAIL']

azure_creds = pytest.mark.skipif(
    any(env not in os.environ for env in REQUIRED_ENV),
    reason=f"Missing one of {REQUIRED_ENV}"
)

AZURE_ENV = os.getenv("AZURE_ENVIRONMENT", "AzurePublicCloud")
EMAIL = os.getenv('EMAIL', 'NOT_AN_EMAIL')
CERTBOT_SERVER = os.getenv('CERTBOT_SERVER')

SUBSCRIPTION_ID = os.getenv('AZURE_SUBSCRIPTION_ID', '')
RESOURCE_GROUP = os.getenv('AZURE_DNS_RESOURCE_GROUP', '')
BASE_DOMAIN = os.getenv('AZURE_DNS_TEST_DOMAIN', 'certbot-test.invalid')

RG_ID = f'/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{RESOURCE_GROUP}'
ZONE1 = f'zone1.{BASE_DOMAIN}'
ZONE2 = f'zone2.{BASE_DOMAIN}'

# Zones the tests write to (checked for leftovers afterwards)
ZONES = {
    BASE_DOMAIN: RG_ID,
    ZONE1: RG_ID,
    ZONE2: RG_ID,
}
# Zone override: challenges for <base> go into zone2
DELEGATION_ZONE = f'{RG_ID}/providers/Microsoft.Network/dnsZones/{ZONE2}'
# Record override: challenges for test.<base> go into the fixed TXT record "other" of <base>
DELEGATION_RECORD = f'{RG_ID}/providers/Microsoft.Network/dnsZones/{BASE_DOMAIN}/TXT/other'


def get_cert_names(count: int = 1) -> List[str]:
    return [uuid.uuid4().hex for _ in range(count)]


@pytest.fixture(scope='session')
def azure_dns_client() -> DnsManagementClient:
    if 'AZURE_CLIENT_SECRET' in os.environ:
        creds = ClientSecretCredential(
            client_id=os.environ['AZURE_CLIENT_ID'],
            client_secret=os.environ['AZURE_CLIENT_SECRET'],
            tenant_id=os.environ['AZURE_TENANT_ID'],
            authority='https://login.microsoftonline.com/'
        )
    else:
        creds = AzureCliCredential(tenant_id=os.environ['AZURE_TENANT_ID'])
    return DnsManagementClient(creds, SUBSCRIPTION_ID, None, 'https://management.azure.com/', credential_scopes=['https://management.azure.com//.default'])


def _record_key(rr) -> Tuple[str, str]:
    return rr.name, rr.type.rsplit('/', 1)[-1]


def _is_challenge_txt(name: str, rr_type: str) -> bool:
    return rr_type == 'TXT' and (name == '_acme-challenge' or name.startswith('_acme-challenge.'))


@pytest.fixture(scope='session', autouse=True)
def guard_test_domain():
    """Refuse to run against anything that does not look like a dedicated test tree."""
    if 'AZURE_DNS_TEST_DOMAIN' not in os.environ:
        return
    if not BASE_DOMAIN.startswith('certbot-test.') or BASE_DOMAIN.count('.') < 2:
        pytest.exit(f"AZURE_DNS_TEST_DOMAIN={BASE_DOMAIN!r} must be a dedicated "
                    f"'certbot-test.<domain>' subtree, refusing to touch it", returncode=3)


@pytest.fixture(scope='function', autouse=True)
def cleanup_dns(azure_dns_client):
    """
    Removes challenge records the test left behind.

    Never wipes a zone. Only TXT records named ``_acme-challenge*`` that did not
    exist before the test are deleted; everything else in the zone is left alone.
    The plugin normally cleans up after itself, this only catches failed runs.

    :param azure_dns_client: pytest dns client fixture
    """
    before = {
        zone: {_record_key(rr) for rr in azure_dns_client.record_sets.list_by_dns_zone(RESOURCE_GROUP, zone)}
        for zone in ZONES
    }

    yield

    for zone in ZONES:
        for rr in list(azure_dns_client.record_sets.list_by_dns_zone(RESOURCE_GROUP, zone)):
            key = _record_key(rr)
            if key in before[zone] or not _is_challenge_txt(*key):
                continue
            try:
                azure_dns_client.record_sets.delete(RESOURCE_GROUP, zone, *key)
                print(f"Deleted leftover {zone}/{key[0]} ({key[1]})")
            except Exception as err:
                print(f"Tried to delete {zone}/{key[0]}, got: {err}")


def cert_sans(cert_path: 'pathlib.Path') -> List[str]:
    """DNS names in the certificate's subjectAltName extension."""
    from cryptography import x509
    cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
    san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    return san.get_values_for_type(x509.DNSName)


def create_config(tmpdir: 'pathlib.Path', zones: List[str]) -> str:
    """
    Creates a config file for certbot azure dns

    :param tmpdir: Temporary pytest fixture
    :param zones: List of zone entries for config
    :returns: Filepath to config
    """
    config = {
        # 'dns_azure_sp_client_id': os.environ['AZURE_CLIENT_ID'],
        # 'dns_azure_sp_client_secret': os.environ['AZURE_CLIENT_SECRET'],
        'dns_azure_use_cli_credentials': 'true',
        'dns_azure_tenant_id': os.environ['AZURE_TENANT_ID'],
        'dns_azure_environment': AZURE_ENV,
    }
    for index, zone in enumerate(zones, start=1):
        config[f"dns_azure_zone{index}"] = zone

    config_text = '\n'.join([' = '.join(item) for item in config.items()]) + '\n'
    config_file = tmpdir / "config.ini"
    config_file.write_text(config_text)
    config_file.chmod(0o600)
    return str(config_file)


def run_certbot(certbot_path: 'pathlib.Path', config_file: str, fqdns: List[str], *, dry_run: bool = False) -> Tuple[subprocess.Popen, str, str]:
    args = [
        'certbot', 'certonly', '--authenticator', 'dns-azure', '--preferred-challenges', 'dns', '--noninteractive',
        '--agree-tos',
        '--email', EMAIL,
        '--config-dir', certbot_path, '--work-dir', certbot_path, '--logs-dir', certbot_path,
        '--dns-azure-config', config_file,
    ]
    if CERTBOT_SERVER:
        args.extend(['--server', CERTBOT_SERVER])
    else:
        args.append('--test-cert')
    if dry_run:
        args.append('--dry-run')
    for fqdn in fqdns:
        args.extend(['-d', fqdn])

    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout, stderr = proc.communicate()
    if proc.returncode != 0:
        print(f"Error, return code {proc.returncode}\nSTDERR:\n{stderr}\nSTDOUT:\n{stdout}")
        pytest.fail()

    return proc, stdout, stderr


@azure_creds
def test_single_zone(tmp_path, azure_dns_client):
    """
    Tests getting a certificate for a single zone
    """
    certbot_path = tmp_path / "certbot"
    zone = ZONE1
    rr_name = get_cert_names(1)[0]
    fqdn = f"{rr_name}.{zone}"

    zone_entry = f"{zone}:{ZONES[zone]}"
    config_file = create_config(tmp_path, [zone_entry])

    proc, stdout, stderr = run_certbot(certbot_path, config_file, [fqdn])

    cert_path = certbot_path / 'archive' / fqdn / 'cert1.pem'
    if not cert_path.exists():
        print(f"STDOUT:\n{stdout}")
        pytest.fail(f"Certificate path {cert_path} does not exist")


@azure_creds
def test_multi_zone(tmp_path, azure_dns_client):
    """
    Tests getting a certificate for multiple zones
    """
    certbot_path = tmp_path / "certbot"
    zone1 = ZONE1
    zone2 = ZONE2

    rr_name1, rr_name2 = get_cert_names(2)
    fqdn1 = f"{rr_name1}.{zone1}"
    fqdn2 = f"{rr_name2}.{zone2}"

    zone_entry1 = f"{zone1}:{ZONES[zone1]}"
    zone_entry2 = f"{zone2}:{ZONES[zone2]}"
    config_file = create_config(tmp_path, [zone_entry1, zone_entry2])

    proc, stdout, stderr = run_certbot(certbot_path, config_file, [fqdn1, fqdn2])

    # One certificate covering both names, stored under the first name's lineage
    cert_path = certbot_path / 'archive' / fqdn1 / 'cert1.pem'
    if not cert_path.exists():
        print(f"STDOUT:\n{stdout}")
        pytest.fail(f"Certificate path {cert_path} does not exist")
    assert set(cert_sans(cert_path)) == {fqdn1, fqdn2}


@azure_creds
def test_delegation_other_domain(tmp_path, azure_dns_client):
    """
    Tests the zone override: the challenge for one domain is written into another zone
    """
    certbot_path = tmp_path / "certbot"
    fqdn = BASE_DOMAIN

    # domain is <base>, but the zone is explicitly overridden to zone2
    config_file = create_config(tmp_path, [
        f"{fqdn}:{DELEGATION_ZONE}"
    ])

    proc, stdout, stderr = run_certbot(certbot_path, config_file, [fqdn])

    cert_path = certbot_path / 'archive' / fqdn / 'cert1.pem'
    if not cert_path.exists():
        print(f"STDOUT:\n{stdout}")
        pytest.fail(f"Certificate path {cert_path} does not exist")


@azure_creds
def test_delegation_specific_record(tmp_path, azure_dns_client):
    """
    Tests the record override: the challenge is written into a fixed TXT record
    that is reset to "-" instead of being deleted
    """
    certbot_path = tmp_path / "certbot"
    fqdn = f'test.{BASE_DOMAIN}'

    # domain is test.<base>, but the validation record is overridden to <base>/TXT/other
    config_file = create_config(tmp_path, [
        f"{fqdn}:{DELEGATION_RECORD}"
    ])

    proc, stdout, stderr = run_certbot(certbot_path, config_file, [fqdn])

    cert_path = certbot_path / 'archive' / fqdn / 'cert1.pem'
    if not cert_path.exists():
        print(f"STDOUT:\n{stdout}")
        pytest.fail(f"Certificate path {cert_path} does not exist")
