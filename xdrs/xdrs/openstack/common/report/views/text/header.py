"""
Text Views With Headers
"""


class HeaderView(object):
    """
    A Text View With a Header
    """

    def __init__(self, header):
        self.header = header

    def __call__(self, model):
        return str(self.header) + "\n" + str(model)


class TitledView(HeaderView):
    """
    A Text View With a Title
    """

    FORMAT_STR = ('=' * 72) + "\n===={0: ^64}====\n" + ('=' * 72)

    def __init__(self, title):
        super(TitledView, self).__init__(self.FORMAT_STR.format(title))
