"""DNS Authenticator for Azure DNS."""
import logging
import time
import random
from os import getenv
from typing import Dict, Tuple

from azure.mgmt.dns import DnsManagementClient
from azure.mgmt.dns.models import RecordSet, TxtRecord
from azure.core.exceptions import HttpResponseError
from azure.core.utils import CaseInsensitiveDict
from azure.identity import ClientSecretCredential, ManagedIdentityCredential, CertificateCredential, AzureCliCredential, WorkloadIdentityCredential

from certbot import errors
from certbot.plugins import dns_common

logger = logging.getLogger(__name__)
logging.getLogger('azure').setLevel(logging.WARNING)


class Authenticator(dns_common.DNSAuthenticator):
    """DNS Authenticator for Azure DNS

    This Authenticator uses the Azure DNS API to fulfill a dns-01 challenge.
    """

    description = ('Obtain certificates using a DNS TXT record (if you are using '
                   'Azure for DNS).')
    default_ttl = 120

    def __init__(self, *args, **kwargs):
        super(Authenticator, self).__init__(*args, **kwargs)
        self.credential = None
        self.domain_zoneid: Dict[str, str] = {}
        # zone -> name of the credential set used for it: the [section] it is mapped in
        # when that section has credentials of its own, otherwise '' (the top level)
        self.domain_scope: Dict[str, str] = {}
        # credential set name -> TokenCredential, created on first use
        self._scope_credentials: Dict[str, object] = {}
        self._scope_auth: Dict[str, Dict[str, object]] = {}
        # (subscription id, credential) -> DnsManagementClient, one HTTP session per pair
        self._clients: Dict[Tuple[str, int], DnsManagementClient] = {}
        self.ttl = self._get_ttl()

        # Azure Environmental Support
        self._azure_environment = getenv("AZURE_ENVIRONMENT", "AzurePublicCloud").lower()
        self._azure_endpoints = {
            "azurepubliccloud": {
                "ResourceManagerEndpoint": "https://management.azure.com/",
                "ActiveDirectoryEndpoint": "https://login.microsoftonline.com/"
            },
            "azureusgovernmentcloud": {
                "ResourceManagerEndpoint": "https://management.usgovcloudapi.net/",
                "ActiveDirectoryEndpoint": "https://login.microsoftonline.us/"
            },
            "azurechinacloud": {
                "ResourceManagerEndpoint": "https://management.chinacloudapi.cn/",
                "ActiveDirectoryEndpoint": "https://login.chinacloudapi.cn/"
            },
        }

    @classmethod
    def add_parser_arguments(cls, add):  # pylint: disable=arguments-differ
        super(Authenticator, cls).add_parser_arguments(add)
        add('config', help='Azure config INI file.')
        add('credentials', help='Azure config INI file. Fallback for legacy integrations')
        add('ttl', default=cls.default_ttl, type=int,
            help='TTL in seconds of the _acme-challenge TXT record.')

    def _get_ttl(self):
        """TTL for the validation records from ``--dns-azure-ttl``."""
        ttl = self.conf('ttl')
        if ttl is None:
            return self.default_ttl
        try:
            ttl = int(ttl)
        except (TypeError, ValueError) as exc:
            raise errors.PluginError('--{}-ttl must be a whole number of seconds, got {!r}'
                                     .format(self.name, ttl)) from exc
        if ttl < 1:
            raise errors.PluginError('--{}-ttl must be at least 1 second, got {}'.format(self.name, ttl))
        return ttl

    def more_info(self):  # pylint: disable=missing-function-docstring
        return 'This plugin configures a DNS TXT record to respond to a dns-01 challenge using ' + \
               'the Azure DNS API.'

    AUTH_KEYS = ('sp_client_id', 'sp_client_secret', 'sp_certificate_path', 'tenant_id',
                 'msi_client_id', 'msi_system_assigned', 'use_cli_credentials',
                 'use_workload_identity_credentials')

    @staticmethod
    def _read_auth(section, mapper):
        """Authentication settings of one config section (top level or ``[name]``)."""
        auth = {key: section.get(mapper(key)) for key in Authenticator.AUTH_KEYS}
        for key in Authenticator.AUTH_FLAGS:
            auth[key] = Authenticator._as_bool(auth[key])
        return auth

    AUTH_FLAGS = ('msi_system_assigned', 'use_cli_credentials', 'use_workload_identity_credentials')

    @staticmethod
    def _as_bool(value):
        """INI values are strings; ``false``, ``0``, ``no``, ``off`` and empty mean off."""
        if isinstance(value, str):
            return value.strip().lower() in ('1', 'true', 'yes', 'on')
        return bool(value)

    @staticmethod
    def _has_auth(auth):
        has_sp = all((auth['sp_client_id'],
                      any((auth['sp_client_secret'], auth['sp_certificate_path'])),
                      auth['tenant_id']))
        return any((has_sp, auth['msi_system_assigned'], auth['msi_client_id'],
                    auth['use_cli_credentials'], auth['use_workload_identity_credentials']))

    @staticmethod
    def _zone_items(section):
        """``(key, value)`` of the zone mappings in one config section."""
        return [(key, value) for key, value in section.items()
                if 'azure_zone' in key and isinstance(value, str)]

    def _validate_credentials(self, credentials):
        confobj = credentials.confobj
        mapper = credentials.mapper

        # Credential sets: the top level ('') and every [section]. A section without
        # its own authentication settings uses the top-level ones.
        scopes = {'': confobj}
        for name in confobj.sections:
            scopes[name] = confobj[name]

        top_auth = self._read_auth(confobj, mapper)
        has_top_auth = self._has_auth(top_auth)
        zone_items = {name: self._zone_items(section) for name, section in scopes.items()}

        zones_in_sections = any(items for name, items in zone_items.items() if name)
        for name, section in scopes.items():
            if name == '' and not has_top_auth and not zone_items[''] and zones_in_sections:
                continue  # all zones live in sections with their own credentials
            auth = self._read_auth(section, mapper) if name else top_auth
            if name and not any(auth.values()):
                auth = top_auth
            if not self._has_auth(auth):
                where = '' if name == '' else ' (section [{}])'.format(name)
                raise errors.PluginError('{}{}: No authentication methods have been '
                                         'configured for Azure DNS. Either configure '
                                         'a service principal, system/user assigned '
                                         'managed identity or configure the use of '
                                         'azure cli or workload identity credentials'
                                         .format(confobj.filename, where))

        if not any(zone_items.values()):
            raise errors.PluginError('{}: At least one zone mapping needs to be provided,'
                                     ' e.g dns_azure_zone1 = DOMAIN:DNS_ZONE_RESOURCE_GROUP_ID'
                                     ''.format(confobj.filename))

        # Azure Environment
        environment = credentials.conf('environment')

        if environment:
            self._azure_environment = environment.lower()

        try:
            endpoints = self._azure_endpoints[self._azure_environment]
        except KeyError as exc:
            raise errors.PluginError(
                '{}: Unknown Azure environment {!r}, expected one of {}'.format(
                    confobj.filename, environment or self._azure_environment,
                    ', '.join(sorted(self._azure_endpoints)))
            ) from exc
        self._arm_endpoint = endpoints["ResourceManagerEndpoint"]
        self._aad_endpoint = endpoints["ActiveDirectoryEndpoint"]
        
        # Check we have key value
        for items in zone_items.values():
            if not all(':' in value for _, value in items):
                raise errors.PluginError('{}: DNS Zone mapping is not in the format of '
                                         'DOMAIN:DNS_ZONE_RESOURCE_GROUP_ID'
                                         ''.format(confobj.filename))

    def _setup_credentials(self):
        # --dns-azure-credentials is an alias of --dns-azure-config for integrations
        # that pass the conventional --<plugin>-credentials option
        credentials_path = self.conf('credentials')
        if credentials_path:
            setattr(self.config.namespace, self.dest('config'), credentials_path)

        valid_creds = self._configure_credentials(
            'config',
            'Azure config INI file',
            None,
            self._validate_credentials
        )

        confobj = valid_creds.confobj
        mapper = valid_creds.mapper

        # Convert dns_azure_zoneX = key:value into key:value, remembering which
        # credential set (top level or [section]) each zone belongs to.
        self.domain_zoneid = {}
        self.domain_scope = {}
        self._scope_auth = {'': self._read_auth(confobj, mapper)}
        self._scope_credentials = {}
        self._clients = {}
        for name, section in [('', confobj)] + [(name, confobj[name]) for name in confobj.sections]:
            scope = name
            if name:
                auth = self._read_auth(section, mapper)
                if any(auth.values()):
                    self._scope_auth[name] = auth
                else:
                    scope = ''  # section without credentials of its own: top-level ones
            for _, value in self._zone_items(section):
                domain, zone_id = (part.strip() for part in value.split(':', 1))
                domain = domain.lower()  # DNS names are case-insensitive, so is the duplicate check
                if domain in self.domain_zoneid:
                    raise errors.PluginError('{}: zone {} is mapped more than once'
                                             .format(confobj.filename, domain))
                self.domain_zoneid[domain] = zone_id
                self.domain_scope[domain] = scope

        # The top-level credential; kept as an attribute for compatibility. Stays None
        # when every zone lives in a [section] with credentials of its own.
        if self._has_auth(self._scope_auth['']):
            self.credential = self._credential_for_scope('')

    def _credential_for_scope(self, scope):
        """Azure credential of one credential set, created on first use."""
        if scope not in self._scope_credentials:
            auth = self._scope_auth[scope]
            self._scope_credentials[scope] = self._get_azure_credentials(
                auth['sp_client_id'], auth['sp_client_secret'], auth['sp_certificate_path'],
                auth['tenant_id'], auth['msi_client_id'], auth['use_cli_credentials'],
                auth['use_workload_identity_credentials'], self._aad_endpoint
            )
        return self._scope_credentials[scope]

    def _credential_for_domain(self, domain):
        """Azure credential for the configured zone that serves ``domain``."""
        zone = self._match_zone(domain)
        return self._credential_for_scope(self.domain_scope.get(zone, ''))

    @staticmethod
    def _get_azure_credentials(client_id=None, client_secret=None, certificate_path=None, tenant_id=None, msi_client_id=None,
                               use_azure_cli_creds=None, use_workload_identity_creds=None, aad_endpoint=None):
        has_sp = all((client_id, client_secret, tenant_id))
        has_sp_cert = all((client_id, certificate_path, tenant_id))
        if use_azure_cli_creds:  # TODO move to DefaultAzureCredential
            return AzureCliCredential(tenant_id=tenant_id)
        elif use_workload_identity_creds:
            return WorkloadIdentityCredential(tenant_id=tenant_id)
        elif has_sp:
            return ClientSecretCredential(
                client_id=client_id,
                client_secret=client_secret,
                tenant_id=tenant_id,
                authority=aad_endpoint
            )
        elif has_sp_cert:
            return CertificateCredential(
                client_id=client_id,
                certificate_path=certificate_path,
                tenant_id=tenant_id,
                authority=aad_endpoint
            )
        elif msi_client_id:
            return ManagedIdentityCredential(client_id=msi_client_id)
        else:
            return ManagedIdentityCredential()

    def _get_ids_for_domain(self, domain: str, validation_name: str) -> Tuple[str, str, str, str, bool]:
        """
        :param domain: Domain/subdomain to look up the closest parent in the config file
        :param validation_name: DNS challenge record name, fully qualified

        This returns:
        * The Azure DNS zone for which to add records to
        * The subscription ID for said zone
        * The resource group for said zone
        * The relative validation record name (or if explicitly overrided with an ID, an alternate record name)
        * If the validation record can be deleted, if its explicitly overrided, it wont be deleted but set to `-`
        """
        azure_dns_domain = self._match_zone(domain)
        if azure_dns_domain is None:
            raise errors.PluginError('Domain {} does not have a valid domain to '
                                     'resource group id mapping'.format(domain))
        zone_id = self.domain_zoneid[azure_dns_domain]

        try:
            resource = self.parse_azure_resource_id(zone_id)
        except ValueError as exc:
            raise errors.PluginError('Failed to parse resource ID for {}: {}'
                                     .format(domain, zone_id)) from exc
        subscription_id = resource.get('subscriptions')
        rg_name = resource.get('resourceGroups')
        if not subscription_id or not rg_name:
            raise errors.PluginError('Resource ID for {} must contain /subscriptions/<id>/resourceGroups/<name>: {}'
                                     .format(domain, zone_id))
        if 'dnsZones' in resource:  # An explicit zone id overrides the zone derived from the domain
            azure_dns_domain = resource.get('dnsZones')
        relative_validation_name = self._get_relative_domain(validation_name, azure_dns_domain)
        can_delete = True
        if 'TXT' in resource:  # An explicit record id names the destination record
            relative_validation_name = resource.get('TXT')
            can_delete = False  # a record configured by the user is emptied, not deleted

        return azure_dns_domain, subscription_id, rg_name, relative_validation_name, can_delete

    def _match_zone(self, domain: str):
        """The configured zone that serves ``domain``, or None.

        The longest configured domain wins, so a mapping for test.domain.io beats one
        for domain.io regardless of their order in the config. The match must sit on
        a label boundary: 'abcxyz.net' is not part of the 'xyz.net' zone.
        """
        for azure_dns_domain in sorted(self.domain_zoneid, key=len, reverse=True):
            if self._is_domain_or_subdomain(domain, azure_dns_domain):
                return azure_dns_domain
        return None

    @staticmethod
    def _is_domain_or_subdomain(name: str, zone: str) -> bool:
        """True if ``name`` is ``zone`` itself or a subdomain of it (label boundary aware)."""
        name = name.rstrip('.').lower()
        zone = zone.rstrip('.').lower()
        return name == zone or name.endswith('.' + zone)

    @staticmethod
    def _get_relative_domain(fqdn: str, domain: str) -> str:
        """Record name relative to ``domain``; ``@`` for the zone apex."""
        fqdn = fqdn.rstrip('.')
        domain = domain.rstrip('.')
        if fqdn.lower() == domain.lower():
            return '@'
        if fqdn.lower().endswith('.' + domain.lower()):
            return fqdn[:-(len(domain) + 1)]
        # Not below the zone (e.g. an explicit dnsZones override pointing elsewhere):
        # keep the previous behaviour of stripping the zone name wherever it appears.
        return fqdn.replace(domain, '').strip('.')

    def _perform(self, domain, validation_name, validation):
        self._with_conflict_retry(domain, 'add', self._write_validation, domain, validation_name, validation)

    def _cleanup(self, domain, validation_name, validation):
        self._with_conflict_retry(domain, 'remove', self._remove_validation, domain, validation_name, validation)

    MAX_CONFLICT_RETRIES = 10

    def _with_conflict_retry(self, domain, action, operation, *args):
        """Run ``operation``; on a concurrent modification (HTTP 412) wait and run it again.

        Every attempt re-reads the record set, so the retry merges what the other
        writer left. A 404 while removing means the record is already gone.
        """
        for attempt in range(self.MAX_CONFLICT_RETRIES + 1):
            try:
                operation(*args)
                return
            except HttpResponseError as err:
                if err.status_code == 404 and action == 'remove':
                    return
                if err.status_code != 412:
                    raise errors.PluginError('Failed to {} TXT record for domain {}, error: {}'
                                             .format(action, domain, err)) from err
                if attempt == self.MAX_CONFLICT_RETRIES:
                    raise errors.PluginError('Failed to {} TXT record for domain {}, max retries due to '
                                             'concurrent access exceeded, error: {}'.format(action, domain, err)) from err
                sleep_secs = random.randint(1, 10)
                logger.warning("Concurrent access to record %s, sleeping %s seconds, retry attempt: %s",
                               domain, sleep_secs, attempt + 1)
                time.sleep(sleep_secs)

    def _read_txt_values(self, client, resource_group_name, zone_name, record_name, domain):
        """``(etag, values)`` of a TXT record set; ``(None, empty set)`` if it does not exist."""
        try:
            existing_rr = client.record_sets.get(
                resource_group_name=resource_group_name,
                zone_name=zone_name,
                relative_record_set_name=record_name,
                record_type='TXT')
        except HttpResponseError as err:
            if err.status_code == 404:
                return None, set()
            raise errors.PluginError('Failed to check TXT record for domain '
                                     '{}, error: {}'.format(domain, err)) from err
        values = set()
        for record in existing_rr.txt_records or []:
            values.update(record.value or [])
        return existing_rr.etag, values

    def _write_validation(self, domain, validation_name, validation):
        azure_domain, subscription_id, resource_group_name, record_name, _ = self._get_ids_for_domain(
            domain, validation_name)
        client = self._get_azure_client(subscription_id, self._credential_for_domain(domain))

        # Keep values other certbot runs put there; drop the '-' placeholder of an empty record
        etag, values = self._read_txt_values(client, resource_group_name, azure_domain, record_name, domain)
        values.discard('-')
        values.add(validation)
        client.record_sets.create_or_update(
            resource_group_name=resource_group_name,
            zone_name=azure_domain,
            relative_record_set_name=record_name,
            record_type='TXT',
            # Update only the version we read; when nothing existed, create only if still
            # nothing exists. Either way a concurrent writer causes a 412 and a retry.
            if_match=etag,
            if_none_match=None if etag else '*',
            parameters=RecordSet(ttl=self.ttl, txt_records=[TxtRecord(value=[v]) for v in values])
        )

    def _remove_validation(self, domain, validation_name, validation):
        azure_domain, subscription_id, resource_group_name, record_name, can_delete = self._get_ids_for_domain(
            domain, validation_name)
        client = self._get_azure_client(subscription_id, self._credential_for_domain(domain))

        etag, values = self._read_txt_values(client, resource_group_name, azure_domain, record_name, domain)
        values.discard(validation)
        if not values and can_delete:
            client.record_sets.delete(
                resource_group_name=resource_group_name,
                zone_name=azure_domain,
                relative_record_set_name=record_name,
                record_type='TXT',
                if_match=etag
            )
            return
        if not values:
            values = {'-'}  # a record the user manages (record override) is emptied, not deleted
        client.record_sets.create_or_update(
            resource_group_name=resource_group_name,
            zone_name=azure_domain,
            relative_record_set_name=record_name,
            record_type='TXT',
            if_match=etag,
            parameters=RecordSet(ttl=self.ttl, txt_records=[TxtRecord(value=[v]) for v in values])
        )

    def _get_azure_client(self, subscription_id, credential=None):
        """
        Gets azure DNS client

        :param subscription_id: Azure subscription ID
        :type subscription_id: str
        :param credential: Azure credential to use, defaults to the top-level one
        :return: Azure DNS client
        :rtype: DnsManagementClient
        """
        if credential is None:
            credential = self.credential
        key = (subscription_id, id(credential))
        if key not in self._clients:
            # Keyword arguments on purpose: azure-mgmt-dns 8.x takes (credential, subscription_id,
            # api_version, base_url, ...) positionally, 9.x dropped api_version and takes
            # (credential, subscription_id, base_url, ...). Keywords work for both.
            self._clients[key] = DnsManagementClient(
                credential, subscription_id,
                base_url=self._arm_endpoint,
                credential_scopes=[self._arm_endpoint.rstrip('/') + "/.default"])
        return self._clients[key]

    @staticmethod
    def parse_azure_resource_id(resource_id):
        rsrc_id = resource_id
        if rsrc_id.startswith('/'):
            rsrc_id = rsrc_id[1:]

        if rsrc_id.endswith('/'):
            rsrc_id = rsrc_id[:-1]

        if '/' not in rsrc_id:
            raise ValueError('Invalid resource ID: {}'.format(resource_id))

        parts = rsrc_id.split('/')
        if (len(parts) % 2) != 0 or '' in parts:
            raise ValueError('Invalid resource ID: {}'.format(resource_id))
        return CaseInsensitiveDict(zip(parts[0::2], parts[1::2]))
