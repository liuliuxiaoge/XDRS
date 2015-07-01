"""
Provides Jinja Views
"""

import jinja2


class JinjaView(object):
    """
    A Jinja View
    """

    def __init__(self, path=None, text=None):
        try:
            self._text = self.VIEW_TEXT
        except AttributeError:
            if path is not None:
                with open(path, 'r') as f:
                    self._text = f.read()
            elif text is not None:
                self._text = text
            else:
                self._text = ""

        if self._text[0] == "\n":
            self._text = self._text[1:]

        newtext = self._text.lstrip()
        amt = len(self._text) - len(newtext)
        if (amt > 0):
            base_indent = self._text[0:amt]
            lines = self._text.splitlines()
            newlines = []
            for line in lines:
                if line.startswith(base_indent):
                    newlines.append(line[amt:])
                else:
                    newlines.append(line)
            self._text = "\n".join(newlines)

        if self._text[-1] == "\n":
            self._text = self._text[:-1]

        self._regentemplate = True
        self._templatecache = None

    def __call__(self, model):
        return self.template.render(**model)

    @property
    def template(self):
        """
        Get the Compiled Template

        Gets the compiled template, using a cached copy if possible
        (stored in attr:`_templatecache`) or otherwise recompiling
        the template if the compiled template is not present or is
        invalid (due to attr:`_regentemplate` being set to True).

        :returns: the compiled Jinja template
        :rtype: :class:`jinja2.Template`
        """

        if self._templatecache is None or self._regentemplate:
            self._templatecache = jinja2.Template(self._text)
            self._regentemplate = False

        return self._templatecache

    def _gettext(self):
        """
        Get the Template Text

        Gets the text of the current template

        :returns: the text of the Jinja template
        :rtype: str
        """

        return self._text

    def _settext(self, textval):
        """
        Set the Template Text

        Sets the text of the current template, marking it
        for recompilation next time the compiled template
        is retrived via attr:`template` .

        :param str textval: the new text of the Jinja template
        """

        self._text = textval
        self.regentemplate = True

    text = property(_gettext, _settext)
