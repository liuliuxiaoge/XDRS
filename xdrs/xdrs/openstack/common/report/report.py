"""
Provides Report classes
"""

import xdrs.openstack.common.report.views.text.header as header_views


class BasicReport(object):
    """
    A Basic Report
    """

    def __init__(self):
        self.sections = []
        self._state = 0

    def add_section(self, view, generator, index=None):
        """
        Add a section to the report
        """

        if index is None:
            self.sections.append(ReportSection(view, generator))
        else:
            self.sections.insert(index, ReportSection(view, generator))

    def run(self):
        """
        Run the report
        """

        return "\n".join(str(sect) for sect in self.sections)


class ReportSection(object):
    """
    A Report Section
    """

    def __init__(self, view, generator):
        self.view = view
        self.generator = generator

    def __str__(self):
        return self.view(self.generator())


class ReportOfType(BasicReport):
    """
    A Report of a Certain Type
    """

    def __init__(self, tp):
        self.output_type = tp
        super(ReportOfType, self).__init__()

    def add_section(self, view, generator, index=None):
        def with_type(gen):
            def newgen():
                res = gen()
                try:
                    res.set_current_view_type(self.output_type)
                except AttributeError:
                    pass

                return res
            return newgen

        super(ReportOfType, self).add_section(
            view,
            with_type(generator),
            index
        )


class TextReport(ReportOfType):
    """
    A Human-Readable Text Report
    """

    def __init__(self, name):
        super(TextReport, self).__init__('text')
        self.name = name
        # add a title with a generator that creates an empty result model
        self.add_section(name, lambda: ('|' * 72) + "\n\n")

    def add_section(self, heading, generator, index=None):
        """
        Add a section to the report
        """

        super(TextReport, self).add_section(header_views.TitledView(heading),
                                            generator,
                                            index)
