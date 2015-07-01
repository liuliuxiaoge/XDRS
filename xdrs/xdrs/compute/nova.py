"""
Handles all requests to Nova.
"""

from novaclient import service_catalog
from novaclient.v1_1 import client as nova_client
from novaclient.v1_1.contrib import assisted_volume_snapshots
from oslo.config import cfg


nova_opts = [
    cfg.StrOpt('nova_catalog_info',
               default='compute:nova:publicURL',
               help='Info to match when looking for nova in the service '
                    'catalog. Format is : separated values of the form: '
                    '<service_type>:<service_name>:<endpoint_type>'),
    cfg.StrOpt('nova_catalog_admin_info',
               default='compute:nova:adminURL',
               help='Same as nova_catalog_info, but for admin endpoint.'),
    cfg.StrOpt('nova_endpoint_template',
               default=None,
               help='Override service catalog lookup with template for nova '
                    'endpoint e.g. http://localhost:8774/v2/%(project_id)s'),
    cfg.StrOpt('nova_endpoint_admin_template',
               default=None,
               help='Same as nova_endpoint_template, but for admin endpoint.'),
    cfg.StrOpt('os_region_name',
               default=None,
               help='region name of this node'),
    cfg.StrOpt('nova_ca_certificates_file',
               default=None,
               help='Location of ca certificates file to use for nova client '
                    'requests.'),
    cfg.BoolOpt('nova_api_insecure',
                default=False,
                help='Allow to perform insecure SSL requests to nova'),
]

CONF = cfg.CONF
CONF.register_opts(nova_opts)


def novaclient(context, admin=False):
    # FIXME: the novaclient ServiceCatalog object is mis-named.
    #        It actually contains the entire access blob.
    # Only needed parts of the service catalog are passed in, see
    # nova/context.py.
    compat_catalog = {
        'access': {'serviceCatalog': context.service_catalog or []}
    }
    sc = service_catalog.ServiceCatalog(compat_catalog)

    nova_endpoint_template = CONF.nova_endpoint_template
    nova_catalog_info = CONF.nova_catalog_info

    if admin:
        nova_endpoint_template = CONF.nova_endpoint_admin_template
        nova_catalog_info = CONF.nova_catalog_admin_info

    if nova_endpoint_template:
        url = nova_endpoint_template % context.to_dict()
    else:
        info = nova_catalog_info
        service_type, service_name, endpoint_type = info.split(':')
        # extract the region if set in configuration
        if CONF.os_region_name:
            attr = 'region'
            filter_value = CONF.os_region_name
        else:
            attr = None
            filter_value = None
        url = sc.url_for(attr=attr,
                         filter_value=filter_value,
                         service_type=service_type,
                         service_name=service_name,
                         endpoint_type=endpoint_type)

    extensions = [assisted_volume_snapshots]

    c = nova_client.Client(context.user_id,
                           context.auth_token,
                           context.project_id,
                           auth_url=url,
                           insecure=CONF.nova_api_insecure,
                           cacert=CONF.nova_ca_certificates_file,
                           extensions=extensions)
    # noauth extracts user_id:project_id from auth_token
    c.client.auth_token = context.auth_token or '%s:%s' % (context.user_id,
                                                           context.project_id)
    c.client.management_url = url
    return c