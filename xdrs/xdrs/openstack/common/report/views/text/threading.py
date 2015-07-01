"""
Provides thread and stack-trace views
"""

import xdrs.openstack.common.report.views.jinja_view as jv


class StackTraceView(jv.JinjaView):
    """
    A Stack Trace View
    """

    VIEW_TEXT = (
        "{% if root_exception is not none %}"
        "Exception: {{ root_exception }}\n"
        "------------------------------------\n"
        "\n"
        "{% endif %}"
        "{% for line in lines %}\n"
        "{{ line.filename }}:{{ line.line }} in {{ line.name }}\n"
        "    {% if line.code is not none %}"
        "`{{ line.code }}`"
        "{% else %}"
        "(source not found)"
        "{% endif %}\n"
        "{% else %}\n"
        "No Traceback!\n"
        "{% endfor %}"
    )


class GreenThreadView(object):
    """
    A Green Thread View
    """

    FORMAT_STR = "------{thread_str: ^60}------" + "\n" + "{stack_trace}"

    def __call__(self, model):
        return self.FORMAT_STR.format(
            thread_str=" Green Thread ",
            stack_trace=model.stack_trace
        )


class ThreadView(object):
    """
    A Thread Collection View
    """

    FORMAT_STR = "------{thread_str: ^60}------" + "\n" + "{stack_trace}"

    def __call__(self, model):
        return self.FORMAT_STR.format(
            thread_str=" Thread #{0} ".format(model.thread_id),
            stack_trace=model.stack_trace
        )
