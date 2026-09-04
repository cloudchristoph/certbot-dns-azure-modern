"""Tests for certbot_dns_azure._internal.dns_azure."""

import unittest

try:
    import mock
except ImportError: # pragma: no cover
    from unittest import mock # type: ignore

from certbot import errors
from certbot.compat import os
from certbot import achallenges
from certbot.plugins import dns_test_common
from certbot.plugins.dns_test_common import KEY
from certbot.tests import util as test_util, acme_util

from azure.mgmt.dns.models import RecordSet, TxtRecord


def _dns01_challenge(domain):
    """Build an annotated DNS-01 challenge for ``domain``.

    certbot >= 5 deprecates ``domain=`` in favour of ``identifier=``; older
    releases only know ``domain=``.
    """
    try:
        from acme import messages
        return achallenges.KeyAuthorizationAnnotatedChallenge(
            challb=acme_util.DNS01, account_key=KEY,
            identifier=messages.Identifier(typ=messages.IDENTIFIER_FQDN, value=domain))
    except (TypeError, KeyError, AttributeError):
        return achallenges.KeyAuthorizationAnnotatedChallenge(
            challb=acme_util.DNS01, domain=domain, account_key=KEY)


def _domain(achall):
    """Domain of an annotated challenge without touching the deprecated ``domain`` attribute."""
    identifier = getattr(achall, 'identifier', None)
    return identifier.value if identifier is not None else achall.domain


MULTI_DOMAIN = [
    _dns01_challenge('example.com'),
    _dns01_challenge('example.org'),
    _dns01_challenge('example.net'),
]
SINGLE_DOMAIN = [
    _dns01_challenge('example.com'),
]
SUB_DOMAIN = [
    _dns01_challenge('a.b.example.com'),
]


class AuthenticatorTest(test_util.TempDirTestCase, dns_test_common.BaseAuthenticatorTest):

    def setUp(self):
        from certbot_dns_azure._internal.dns_azure import Authenticator

        super(AuthenticatorTest, self).setUp()

        # This causes some weird zope errors
        mock.patch("certbot.display.util.notify", lambda x: ...).start()

        # Setup config files
        config_files = (
            ('sp.ini', {
                'azure_sp_client_id': '912ce44a-0156-4669-ae22-c16a17d34ca5',
                'azure_sp_client_secret': 'example-client-secret-not-real',
                'azure_tenant_id': 'ed1090f3-ab18-4b12-816c-599af8a88cf7',
                'azure_zone1': 'example.com:/subscriptions/c135abce-d87d-48df-936c-15596c6968a5/resourceGroups/dns1',
                'azure_zone2': 'example.org:/subscriptions/99800903-fb14-4992-9aff-12eaf2744622/resourceGroups/dns2',
                'azure_zone3': ('example.net:/subscriptions/99800903-fb14-4992-9aff-12eaf2744622/resourceGroups/dns2'
                                '/providers/Microsoft.Network/dnsZones/example.com')
            }),
            ('sp_cert.ini', {
                'azure_sp_client_id': '912ce44a-0156-4669-ae22-c16a17d34ca5',
                'azure_sp_client_secret': 'example-client-secret-not-real',
                'azure_certificate_path': '/path/to/cert.pem',
                'azure_zone1': 'example.com:/subscriptions/c135abce-d87d-48df-936c-15596c6968a5/resourceGroups/dns1',
                'azure_zone2': 'example.org:/subscriptions/99800903-fb14-4992-9aff-12eaf2744622/resourceGroups/dns2'
            }),
            ('user_assigned_msi.ini', {
                'azure_msi_client_id': '912ce44a-0156-4669-ae22-c16a17d34ca5',
                'azure_zone1': 'example.com:/subscriptions/c135abce-d87d-48df-936c-15596c6968a5/resourceGroups/dns1',
                'azure_zone2': 'example.org:/subscriptions/99800903-fb14-4992-9aff-12eaf2744622/resourceGroups/dns2'
            }),
            ('system_msi.ini', {
                'azure_msi_system_assigned': 'true',
                'azure_zone1': 'example.com:/subscriptions/c135abce-d87d-48df-936c-15596c6968a5/resourceGroups/dns1',
                'azure_zone2': 'example.org:/subscriptions/99800903-fb14-4992-9aff-12eaf2744622/resourceGroups/dns2'
            })
        )
        for file, config in config_files:
            dns_test_common.write(config, os.path.join(self.tempdir, file))

        self.sp_config = mock.MagicMock(
            azure_config=os.path.join(self.tempdir, 'sp.ini'),
            azure_propagation_seconds=0)
        self.sp_cert_config = mock.MagicMock(
            azure_config=os.path.join(self.tempdir, 'sp_cert.ini'),
            azure_propagation_seconds=0)
        self.umsi_config = mock.MagicMock(
            azure_config=os.path.join(self.tempdir, 'user_assigned_msi.ini'),
            azure_propagation_seconds=0)
        self.smsi_config = mock.MagicMock(
            azure_config=os.path.join(self.tempdir, 'system_msi.ini'),
            azure_propagation_seconds=0)

        self.auth = Authenticator(self.sp_config, "azure")
        self.mock_credentials = mock.MagicMock()
        self.mock_client = mock.MagicMock()
        self.auth._get_azure_credentials = mock.MagicMock(return_value=self.mock_credentials)
        self.auth._get_azure_client = mock.MagicMock(return_value=self.mock_client)

    def test_perform_multidomain(self):
        self.mock_client.record_sets.get.return_value = RecordSet(txt_records=[])

        # Extract zone TXT record name and value
        zone1_req, zone2_req, zone3_req = MULTI_DOMAIN
        zone1_domain_name = zone1_req.validation_domain_name(_domain(zone1_req))
        zone1_relative_record = zone1_domain_name.replace('example.com', '').strip('.')
        zone1_key = zone1_req.validation(zone1_req.account_key)
        zone2_domain_name = zone2_req.validation_domain_name(_domain(zone2_req))
        zone2_relative_record = zone2_domain_name.replace('example.org', '').strip('.')
        zone2_key = zone2_req.validation(zone2_req.account_key)
        zone3_domain_name = zone3_req.validation_domain_name(_domain(zone3_req))
        zone3_relative_record = zone3_domain_name.replace('example.com', '').strip('.')
        zone3_key = zone3_req.validation(zone3_req.account_key)

        self.auth.perform(MULTI_DOMAIN)

        # Check azure client call counts
        self.assertEqual(self.mock_client.record_sets.get.call_count, 3)
        self.assertEqual(self.mock_client.record_sets.create_or_update.call_count, 3)

        #
        zone1_call, zone2_call, zone3_call = self.mock_client.record_sets.create_or_update.call_args_list
        self.assertEqual(zone1_call[1]['zone_name'], "example.com")
        self.assertEqual(zone1_call[1]['record_type'], "TXT")
        self.assertEqual(zone1_call[1]['relative_record_set_name'], zone1_relative_record)
        zone1_txt_records = zone1_call[1]['parameters'].txt_records
        self.assertEqual(len(zone1_txt_records), 1)
        self.assertEqual(zone1_txt_records[0].value[0], zone1_key)

        self.assertEqual(zone2_call[1]['zone_name'], "example.org")
        self.assertEqual(zone2_call[1]['relative_record_set_name'], zone2_relative_record)
        zone2_txt_records = zone2_call[1]['parameters'].txt_records
        self.assertEqual(len(zone2_txt_records), 1)
        self.assertEqual(zone2_txt_records[0].value[0], zone2_key)

        # Test DNS delegation of example.net to example.com
        self.assertEqual(_domain(zone3_req), "example.net")
        self.assertEqual(zone3_call[1]['zone_name'], "example.com")
        self.assertEqual(zone3_call[1]['relative_record_set_name'], zone3_relative_record)
        zone3_txt_records = zone3_call[1]['parameters'].txt_records
        self.assertEqual(len(zone3_txt_records), 1)
        self.assertEqual(zone3_txt_records[0].value[0], zone3_key)

    def test_perform_existing(self):
        self.mock_client.record_sets.get.return_value = RecordSet(txt_records=[
            TxtRecord(value=['someexistingkey'])
        ])

        # Extract zone TXT record name and value
        zone1_req = SINGLE_DOMAIN[0]
        zone1_domain_name = zone1_req.validation_domain_name(_domain(zone1_req))
        zone1_relative_record = zone1_domain_name.replace('example.com', '').strip('.')
        zone1_key = zone1_req.validation(zone1_req.account_key)

        self.auth.perform(SINGLE_DOMAIN)

        # Check azure client call counts
        self.assertEqual(self.mock_client.record_sets.get.call_count, 1)
        self.assertEqual(self.mock_client.record_sets.create_or_update.call_count, 1)

        #
        expected = [self.mock_client.record_sets.create_or_update.call(
            resource_group_name='dns1',
            zone_name='example.com',
            relative_record_set_name=zone1_domain_name,
            parameters=RecordSet(txt_records=[TxtRecord(value=[zone1_key]), TxtRecord(value=['someexistingkey'])])
        )]
        zone1_call = self.mock_client.record_sets.create_or_update.call_args_list[0]
        self.assertEqual(zone1_call[1]['zone_name'], "example.com")
        self.assertEqual(zone1_call[1]['record_type'], "TXT")
        self.assertEqual(zone1_call[1]['relative_record_set_name'], zone1_relative_record)
        zone1_txt_records = zone1_call[1]['parameters'].txt_records

        self.assertEqual(len(zone1_txt_records), 2)
        txt_values = [rr.value for rr in zone1_txt_records]
        self.assertIn([zone1_key], txt_values)
        self.assertIn(['someexistingkey'], txt_values)

    def test_perform_subdomain(self):
        self.mock_client.record_sets.get.return_value = RecordSet(txt_records=[])

        # Extract zone TXT record name and value
        zone1_req = SUB_DOMAIN[0]
        zone1_domain_name = zone1_req.validation_domain_name(_domain(zone1_req))
        zone1_key = zone1_req.validation(zone1_req.account_key)
        # example.com is azure zone in config
        relative_record = zone1_domain_name.replace('example.com', '').strip('.')

        self.auth.perform(SUB_DOMAIN)

        # Check azure client call counts
        self.assertEqual(self.mock_client.record_sets.get.call_count, 1)
        self.assertEqual(self.mock_client.record_sets.create_or_update.call_count, 1)

        #
        zone1_call = self.mock_client.record_sets.create_or_update.call_args_list[0]
        self.assertEqual(zone1_call[1]['zone_name'], "example.com")
        self.assertEqual(zone1_call[1]['record_type'], "TXT")
        self.assertEqual(zone1_call[1]['relative_record_set_name'], relative_record)
        zone1_txt_records = zone1_call[1]['parameters'].txt_records
        self.assertEqual(len(zone1_txt_records), 1)
        self.assertEqual(zone1_txt_records[0].value[0], zone1_key)

    def test_cleanup_multiple(self):
        self.mock_client.record_sets.get.return_value = RecordSet(txt_records=[])

        # Extract zone TXT record name and value
        zone1_req, zone2_req, zone3_req = MULTI_DOMAIN
        zone1_domain_name = zone1_req.validation_domain_name(_domain(zone1_req))
        zone2_domain_name = zone2_req.validation_domain_name(_domain(zone2_req))
        zone3_domain_name = zone3_req.validation_domain_name(_domain(zone3_req))
        zone1_relative_record = zone1_domain_name.replace('example.com', '').strip('.')
        zone2_relative_record = zone2_domain_name.replace('example.org', '').strip('.')
        zone3_relative_record = zone3_domain_name.replace('example.com', '').strip('.')

        # _attempt_cleanup | pylint: disable=protected-access
        self.auth._attempt_cleanup = True
        self.auth.cleanup(MULTI_DOMAIN)

        # Check azure client call counts
        self.assertEqual(self.mock_client.record_sets.get.call_count, 3)
        self.assertEqual(self.mock_client.record_sets.delete.call_count, 3)

        zone1_call, zone2_call, zone3_call = self.mock_client.record_sets.delete.call_args_list
        self.assertEqual(zone1_call[1]['zone_name'], "example.com")
        self.assertEqual(zone1_call[1]['record_type'], "TXT")
        self.assertEqual(zone1_call[1]['relative_record_set_name'], zone1_relative_record)

        self.assertEqual(zone2_call[1]['zone_name'], "example.org")
        self.assertEqual(zone2_call[1]['record_type'], "TXT")
        self.assertEqual(zone2_call[1]['relative_record_set_name'], zone2_relative_record)

        self.assertEqual(zone3_call[1]['zone_name'], "example.com")
        self.assertEqual(zone3_call[1]['record_type'], "TXT")
        self.assertEqual(zone3_call[1]['relative_record_set_name'], zone3_relative_record)

    def test_cleanup_existing(self):
        self.mock_client.record_sets.get.return_value = RecordSet(txt_records=[
            TxtRecord(value=['someexistingkey'])
        ])

        # Extract zone TXT record name and value
        zone1_req = SINGLE_DOMAIN[0]
        zone1_domain_name = zone1_req.validation_domain_name(_domain(zone1_req))
        zone1_relative_record = zone1_domain_name.replace('example.com', '').strip('.')
        zone1_key = zone1_req.validation(zone1_req.account_key)

        # _attempt_cleanup | pylint: disable=protected-access
        self.auth._attempt_cleanup = True
        self.auth.cleanup(SINGLE_DOMAIN)

        # Check azure client call counts
        self.assertEqual(self.mock_client.record_sets.get.call_count, 1)
        self.assertEqual(self.mock_client.record_sets.delete.call_count, 0)
        self.assertEqual(self.mock_client.record_sets.create_or_update.call_count, 1)

        # Check recordset is updated to not include key
        zone1_call = self.mock_client.record_sets.create_or_update.call_args_list[0]
        self.assertEqual(zone1_call[1]['zone_name'], "example.com")
        self.assertEqual(zone1_call[1]['record_type'], "TXT")
        self.assertEqual(zone1_call[1]['relative_record_set_name'], zone1_relative_record)
        zone1_txt_records = zone1_call[1]['parameters'].txt_records

        self.assertEqual(len(zone1_txt_records), 1)
        txt_values = zone1_txt_records[0].value
        self.assertNotIn(zone1_key, txt_values)
        self.assertIn('someexistingkey', txt_values)

    def test_config_missing_auth(self):
        # Test no auth info
        dns_test_common.write({}, self.sp_config.azure_config)
        with self.assertRaises(errors.PluginError) as cm:
            self.auth.perform(SINGLE_DOMAIN)
        self.assertIn('No authentication methods have been configured', cm.exception.args[0])

    def test_config_missing_zone_info(self):
        # Test missing mapping list
        dns_test_common.write({
            'azure_sp_client_id': '912ce44a-0156-4669-ae22-c16a17d34ca5',
            'azure_sp_client_secret': 'example-client-secret-not-real',
            'azure_tenant_id': 'ed1090f3-ab18-4b12-816c-599af8a88cf7',
        }, self.sp_config.azure_config)
        with self.assertRaises(errors.PluginError) as cm:
            self.auth.perform(SINGLE_DOMAIN)
        self.assertIn('At least one zone mapping needs to be provided', cm.exception.args[0])

    def test_config_bad_zone_info(self):
        # Test missing mapping list
        dns_test_common.write({
            'azure_sp_client_id': '912ce44a-0156-4669-ae22-c16a17d34ca5',
            'azure_sp_client_secret': 'example-client-secret-not-real',
            'azure_tenant_id': 'ed1090f3-ab18-4b12-816c-599af8a88cf7',
            'azure_zone1': 'example.com',
        }, self.sp_config.azure_config)
        with self.assertRaises(errors.PluginError) as cm:
            self.auth.perform(SINGLE_DOMAIN)
        self.assertIn('DNS Zone mapping is not in the format', cm.exception.args[0])

    def test_config_bad_resource_group(self):
        # Test invalid resource group ID
        dns_test_common.write({
            'azure_sp_client_id': '912ce44a-0156-4669-ae22-c16a17d34ca5',
            'azure_sp_client_secret': 'example-client-secret-not-real',
            'azure_tenant_id': 'ed1090f3-ab18-4b12-816c-599af8a88cf7',
            'azure_zone1': 'example.com:/subscriptions/c135abce-d87d-48df-936c-15596c6968a5/invalid',
        }, self.sp_config.azure_config)
        with self.assertRaises(errors.PluginError) as cm:
            self.auth.perform(SINGLE_DOMAIN)
        self.assertIn('Failed to parse resource ID for example.com', cm.exception.args[0])

    def test_zone_match_label_boundary(self):
        # A zone only matches on a label boundary: 'abcxyz.net' must not be treated as a
        # subdomain of 'xyz.net' (upstream issue #61).
        rg = '/subscriptions/c135abce-d87d-48df-936c-15596c6968a5/resourceGroups/dns1'
        self.auth.domain_zoneid = {'xyz.net': rg}

        zone, _, _, record, _ = self.auth._get_ids_for_domain('sub.xyz.net', '_acme-challenge.sub.xyz.net')
        self.assertEqual(zone, 'xyz.net')
        self.assertEqual(record, '_acme-challenge.sub')

        zone, _, _, record, _ = self.auth._get_ids_for_domain('xyz.net', '_acme-challenge.xyz.net')
        self.assertEqual(zone, 'xyz.net')
        self.assertEqual(record, '_acme-challenge')

        for name in ('abcxyz.net', 'www.abcxyz.net'):
            with self.assertRaises(errors.PluginError) as cm:
                self.auth._get_ids_for_domain(name, '_acme-challenge.' + name)
            self.assertIn('does not have a valid domain to resource group id mapping', cm.exception.args[0])

    def test_zone_match_prefers_longest(self):
        # With both zones configured the exact zone wins regardless of config order.
        rg = '/subscriptions/c135abce-d87d-48df-936c-15596c6968a5/resourceGroups/dns1'
        self.auth.domain_zoneid = {'xyz.net': rg, 'abcxyz.net': rg, 'sub.xyz.net': rg}

        self.assertEqual(self.auth._get_ids_for_domain('abcxyz.net', '_acme-challenge.abcxyz.net')[0], 'abcxyz.net')
        self.assertEqual(self.auth._get_ids_for_domain('a.sub.xyz.net', '_acme-challenge.a.sub.xyz.net')[0], 'sub.xyz.net')
        self.assertEqual(self.auth._get_ids_for_domain('other.xyz.net', '_acme-challenge.other.xyz.net')[0], 'xyz.net')

    def test_get_azure_client_uses_keyword_arguments(self):
        # azure-mgmt-dns 9.x dropped the positional api_version parameter; the client
        # must be built with keyword arguments so both 8.x and 9.x work. The scope has
        # a single slash even though the endpoint ends with one.
        from certbot_dns_azure._internal import dns_azure
        auth = dns_azure.Authenticator(self.sp_config, "azure")
        auth.credential = self.mock_credentials
        auth._arm_endpoint = 'https://management.usgovcloudapi.net/'
        with mock.patch.object(dns_azure, 'DnsManagementClient') as client_cls:
            auth._get_azure_client('c135abce-d87d-48df-936c-15596c6968a5')
        client_cls.assert_called_once_with(
            self.mock_credentials, 'c135abce-d87d-48df-936c-15596c6968a5',
            base_url='https://management.usgovcloudapi.net/',
            credential_scopes=['https://management.usgovcloudapi.net/.default'])

    def test_get_relative_domain(self):
        from certbot_dns_azure._internal.dns_azure import Authenticator
        rel = Authenticator._get_relative_domain
        self.assertEqual(rel('example.com', 'example.com'), '@')
        self.assertEqual(rel('_acme-challenge.example.com', 'example.com'), '_acme-challenge')
        self.assertEqual(rel('_acme-challenge.a.b.example.com', 'example.com'), '_acme-challenge.a.b')
        # The zone name occurring inside a label must not be stripped
        self.assertEqual(rel('_acme-challenge.example.com.example.com', 'example.com'), '_acme-challenge.example.com')
        self.assertEqual(rel('_acme-challenge.Example.COM', 'example.com'), '_acme-challenge')
        # Delegated validation into a different zone keeps the previous behaviour
        self.assertEqual(rel('_acme-challenge.example.net', 'example.com'), '_acme-challenge.example.net')


if __name__ == "__main__":
    unittest.main()  # pragma: no cover
