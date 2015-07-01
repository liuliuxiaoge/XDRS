import copy
import os

from xdrs.api.openstack import common


def get_view_builder(req):
    base_url = req.application_url
    return ViewBuilder(base_url)


class ViewBuilder(common.ViewBuilder):

    def __init__(self, base_url):
        """:param base_url: url of the root wsgi application."""
        self.base_url = base_url

    def build_choices(self, VERSIONS, req):
        version_objs = []
        for version in VERSIONS:
            version = VERSIONS[version]
            version_objs.append({
                "id": version['id'],
                "status": version['status'],
                "links": [
                    {
                        "rel": "self",
                        "href": self.generate_href(version['id'], req.path),
                    },
                ],
                "media-types": version['media-types'],
            })

        return dict(choices=version_objs)

    def build_versions(self, versions):
        version_objs = []
        for version in sorted(versions.keys()):
            version = versions[version]
            version_objs.append({
                "id": version['id'],
                "status": version['status'],
                "updated": version['updated'],
                "links": self._build_links(version),
            })

        return dict(versions=version_objs)

    def build_version(self, version):
        reval = copy.deepcopy(version)
        reval['links'].insert(0, {
            "rel": "self",
            "href": self.base_url.rstrip('/') + '/',
        })
        return dict(version=reval)

    def _build_links(self, version_data):
        """Generate a container of links that refer to the provided version."""
        href = self.generate_href(version_data['id'])

        links = [
            {
                "rel": "self",
                "href": href,
            },
        ]

        return links

    def generate_href(self, version, path=None):
        """Create an url that refers to a specific version_number."""
        prefix = self._update_compute_link_prefix(self.base_url)
        if version.find('v3.') == 0:
            version_number = 'v3'
        else:
            version_number = 'v2'

        if path:
            path = path.strip('/')
            return os.path.join(prefix, version_number, path)
        else:
            return os.path.join(prefix, version_number) + '/'
