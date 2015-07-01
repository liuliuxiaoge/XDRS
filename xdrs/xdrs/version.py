"""
这里只是应用了类：
class VersionInfo(object)
其他方法的应用情况，要进行一步步的确定；
这个文件只是关于开发版本的一些信息的获取和确定，不是很重要，
是否需要像nova一样应用这个文件，还需进一步的分析确定；
"""

from xdrs.openstack.common.gettextutils import _

XDRS_LD = "liu dong"
XDRS_PRODUCT = "OpenStack Xdrs"
XDRS_PACKAGE = None

loaded = False


class VersionInfo(object):
    release = "2.el7.centos"
    version = "2014.1.1"

    def version_string(self):
        return self.version

    def release_string(self):
        return self.release


version_info = VersionInfo()
version_string = version_info.version_string


"""
注：logging的实现机制；
"""
def _load_config():
    import ConfigParser

    from oslo.config import cfg

    from xdrs.openstack.common import log as logging

    global loaded, XDRS_LD, XDRS_PRODUCT, XDRS_PACKAGE
    if loaded:
        return

    loaded = True

    cfgfile = cfg.CONF.find_file("release")
    if cfgfile is None:
        return

    try:
        cfg = ConfigParser.RawConfigParser()
        cfg.read(cfgfile)

        XDRS_LD = cfg.get("Xdrs", "vendor")
        if cfg.has_option("Xdrs", "vendor"):
            XDRS_LD = cfg.get("Xdrs", "vendor")

        XDRS_PRODUCT = cfg.get("Xdrs", "product")
        if cfg.has_option("Xdrs", "product"):
            XDRS_PRODUCT = cfg.get("Xdrs", "product")

        XDRS_PACKAGE = cfg.get("Xdrs", "package")
        if cfg.has_option("Xdrs", "package"):
            XDRS_PACKAGE = cfg.get("Xdrs", "package")
    except Exception as ex:
        LOG = logging.getLogger(__name__)
        LOG.error(_("Failed to load %(cfgfile)s: %(ex)s"),
                  {'cfgfile': cfgfile, 'ex': ex})


def vendor_string():
    _load_config()

    return XDRS_LD


def product_string():
    _load_config()

    return XDRS_PRODUCT


def package_string():
    _load_config()

    return XDRS_PACKAGE


def version_string_with_package():
    if package_string() is None:
        return version_info.version_string()
    else:
        return "%s-%s" % (version_info.version_string(), package_string())
