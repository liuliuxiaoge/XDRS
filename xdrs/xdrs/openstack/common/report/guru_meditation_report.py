from __future__ import print_function

import signal
import sys

from xdrs.openstack.common.report.generators import conf as cgen
from xdrs.openstack.common.report.generators import threading as tgen
from xdrs.openstack.common.report.generators import version as pgen
from xdrs.openstack.common.report import report


class GuruMeditation(object):
    """
    A Guru Meditation Report Mixin/Base Class
    """

    def __init__(self, version_obj, *args, **kwargs):
        self.version_obj = version_obj

        super(GuruMeditation, self).__init__(*args, **kwargs)
        self.start_section_index = len(self.sections)

    @classmethod
    def register_section(cls, section_title, generator):
        """
        Register a New Section
        """

        try:
            cls.persistent_sections.append([section_title, generator])
        except AttributeError:
            cls.persistent_sections = [[section_title, generator]]
    
    @classmethod
    def setup_autorun(cls, version, signum=None):
        """
        Set Up Auto-Run
        """

        if not signum and hasattr(signal, 'SIGUSR1'):
            # SIGUSR1 is not supported on all platforms
            signum = signal.SIGUSR1

        if signum:
            signal.signal(signum,
                          lambda *args: cls.handle_signal(version, *args))

    @classmethod
    def handle_signal(cls, version, *args):
        """
        The Signal Handler
        """

        try:
            res = cls(version).run()
        except Exception:
            print("Unable to run Guru Meditation Report!",
                  file=sys.stderr)
        else:
            print(res, file=sys.stderr)

    def _readd_sections(self):
        del self.sections[self.start_section_index:]

        self.add_section('Package',
                         pgen.PackageReportGenerator(self.version_obj))

        self.add_section('Threads',
                         tgen.ThreadReportGenerator())

        self.add_section('Green Threads',
                         tgen.GreenThreadReportGenerator())

        self.add_section('Configuration',
                         cgen.ConfigReportGenerator())

        try:
            for section_title, generator in self.persistent_sections:
                self.add_section(section_title, generator)
        except AttributeError:
            pass

    def run(self):
        self._readd_sections()
        return super(GuruMeditation, self).run()


# GuruMeditation must come first to get the correct MRO
class TextGuruMeditation(GuruMeditation, report.TextReport):
    """
    A Text Guru Meditation Report
    """

    def __init__(self, version_obj):
        super(TextGuruMeditation, self).__init__(version_obj,
                                                 'Guru Meditation')
