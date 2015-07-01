import abc
import re

from xdrs.openstack.common import jsonutils


_rules = None
_checks = {}


class Rules(dict):
    """
    A store for rules.  Handles the default_rule setting directly.
    """

    @classmethod
    def load_json(cls, data, default_rule=None):
        """
        Allow loading of JSON rule data.
        """

        # Suck in the JSON data and parse the rules
        rules = dict((k, parse_rule(v)) for k, v in
                     jsonutils.loads(data).items())

        return cls(rules, default_rule)

    
    def __init__(self, rules=None, default_rule=None):
        """
        Initialize the Rules store.
        """

        super(Rules, self).__init__(rules or {})
        self.default_rule = default_rule

    def __missing__(self, key):
        """
        Implements the default rule handling.
        """

        # If the default rule isn't actually defined, do something
        # reasonably intelligent
        if not self.default_rule or self.default_rule not in self:
            raise KeyError(key)

        return self[self.default_rule]

    def __str__(self):
        """
        Dumps a string representation of the rules.
        """

        # Start by building the canonical strings for the rules
        out_rules = {}
        for key, value in self.items():
            # Use empty string for singleton TrueCheck instances
            if isinstance(value, TrueCheck):
                out_rules[key] = ''
            else:
                out_rules[key] = str(value)

        # Dump a pretty-printed JSON representation
        return jsonutils.dumps(out_rules, indent=4)


# Really have to figure out a way to deprecate this
def set_rules(rules):
    """
    Set the rules in use for policy checks.
    """

    global _rules

    _rules = rules


# Ditto
def reset():
    """
    Clear the rules used for policy checks.
    """

    global _rules

    _rules = None



def check(rule, target, creds, exc=None, *args, **kwargs):
    """
    Checks authorization of a rule against the target and credentials.
    """
    """
    ======================================================================================
    rule = xdrs:get_algorithms
    target = <xdrs.objects.instance.Instance object at 0x62b4a50>
    creds = {'project_name': u'admin', 'user_id': u'91d732b65831491d8bd952b3111e62dd', 'roles': [u'heat_stack_owner', u'_member_', u'admin'], 'timestamp': '2015-03-10T06:54:34.936577', 'auth_token': 'MIIT9wYJKoZIhvcNAQcCoIIT6DCCE+QCAQExCTAHBgUrDgMCGjCCEk0GCSqGSIb3DQEHAaCCEj4EghI6eyJhY2Nlc3MiOiB7InRva2VuIjogeyJpc3N1ZWRfYXQiOiAiMjAxNS0wMy0xMFQwNjo1NDozMS4zNjI4MjMiLCAiZXhwaXJlcyI6ICIyMDE1LTAzLTEwVDA3OjU0OjMxWiIsICJpZCI6ICJwbGFjZWhvbGRlciIsICJ0ZW5hbnQiOiB7ImRlc2NyaXB0aW9uIjogImFkbWluIHRlbmFudCIsICJlbmFibGVkIjogdHJ1ZSwgImlkIjogIjQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIiwgIm5hbWUiOiAiYWRtaW4ifX0sICJzZXJ2aWNlQ2F0YWxvZyI6IFt7ImVuZHBvaW50cyI6IFt7ImFkbWluVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4Nzc0L3YyLzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzQvdjIvNDUzN2FjYTRhNGE0NDYyZmE0YzU5YWQ1YjU1ODFmMDAiLCAiaWQiOiAiMTZiMTVjYzVmZjUwNGNiODlmNTg2NjRlMjdhNjljNjkiLCAicHVibGljVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4Nzc0L3YyLzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogImNvbXB1dGUiLCAibmFtZSI6ICJub3ZhIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjk2OTYvIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjk2OTYvIiwgImlkIjogIjFiMjkzYTgxNjk2YjRiN2Y4OTZlYWQ0NjIyYTFjMmExIiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6OTY5Ni8ifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAibmV0d29yayIsICJuYW1lIjogIm5ldXRyb24ifSwgeyJlbmRwb2ludHMiOiBbeyJhZG1pblVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODc3Ni92Mi80NTM3YWNhNGE0YTQ0NjJmYTRjNTlhZDViNTU4MWYwMCIsICJyZWdpb24iOiAiUmVnaW9uT25lIiwgImludGVybmFsVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4Nzc2L3YyLzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIiwgImlkIjogIjNhNzY3OWNjZTdkZjRhY2ZhMTZiM2NhNTJkZGNmYzgyIiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODc3Ni92Mi80NTM3YWNhNGE0YTQ0NjJmYTRjNTlhZDViNTU4MWYwMCJ9XSwgImVuZHBvaW50c19saW5rcyI6IFtdLCAidHlwZSI6ICJ2b2x1bWV2MiIsICJuYW1lIjogImNpbmRlcnYyIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzQvdjMiLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODc3NC92MyIsICJpZCI6ICIwYmIxZDFiODhhZmU0MGRhOTNiY2IxNTg0Y2ExN2ZiOSIsICJwdWJsaWNVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzQvdjMifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAiY29tcHV0ZXYzIiwgIm5hbWUiOiAibm92YXYzIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwODAiLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODA4MCIsICJpZCI6ICIxZTMyZTE3MmU3OWM0YzVhYTZiNWM3ZjhkNzVhZjRmYiIsICJwdWJsaWNVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwODAifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAiczMiLCAibmFtZSI6ICJzd2lmdF9zMyJ9LCB7ImVuZHBvaW50cyI6IFt7ImFkbWluVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo5MjkyIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjkyOTIiLCAiaWQiOiAiM2QxYzc5MjY1MWEwNDljNWE2MWUzNWJmZWZjNGM4OGIiLCAicHVibGljVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo5MjkyIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogImltYWdlIiwgIm5hbWUiOiAiZ2xhbmNlIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzciLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODc3NyIsICJpZCI6ICIzOWE0YzA2NDIzYTg0OTNjOTI4ZGExOGY0YTVjY2MxZiIsICJwdWJsaWNVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzcifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAibWV0ZXJpbmciLCAibmFtZSI6ICJjZWlsb21ldGVyIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwMDAvdjEvIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwMDAvdjEvIiwgImlkIjogIjU1NzBiOGY4MTE0OTRlMWI5NTVkYjZlNTAzZGYyYWZkIiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODAwMC92MS8ifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAiY2xvdWRmb3JtYXRpb24iLCAibmFtZSI6ICJoZWF0LWNmbiJ9LCB7ImVuZHBvaW50cyI6IFt7ImFkbWluVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4Nzc2L3YxLzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzYvdjEvNDUzN2FjYTRhNGE0NDYyZmE0YzU5YWQ1YjU1ODFmMDAiLCAiaWQiOiAiMGExYzhkYTRmMTU2NDk1YWFkMjEzMGUyYzA2OTE5ODIiLCAicHVibGljVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4Nzc2L3YxLzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogInZvbHVtZSIsICJuYW1lIjogImNpbmRlciJ9LCB7ImVuZHBvaW50cyI6IFt7ImFkbWluVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4NzczL3NlcnZpY2VzL0FkbWluIiwgInJlZ2lvbiI6ICJSZWdpb25PbmUiLCAiaW50ZXJuYWxVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjg3NzMvc2VydmljZXMvQ2xvdWQiLCAiaWQiOiAiMDMzZjY3ZTk1MDBjNDljYThmOGIxODkzZTJhN2VkYWYiLCAicHVibGljVVJMIjogImh0dHA6Ly8xNzIuMjEuNy40MDo4NzczL3NlcnZpY2VzL0Nsb3VkIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogImVjMiIsICJuYW1lIjogIm5vdmFfZWMyIn0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwMDQvdjEvNDUzN2FjYTRhNGE0NDYyZmE0YzU5YWQ1YjU1ODFmMDAiLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODAwNC92MS80NTM3YWNhNGE0YTQ0NjJmYTRjNTlhZDViNTU4MWYwMCIsICJpZCI6ICI0YmViNjQ0MjUzYWU0NzdmOWU5NDk2ZWVkZDEwOTNhNSIsICJwdWJsaWNVUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjgwMDQvdjEvNDUzN2FjYTRhNGE0NDYyZmE0YzU5YWQ1YjU1ODFmMDAifV0sICJlbmRwb2ludHNfbGlua3MiOiBbXSwgInR5cGUiOiAib3JjaGVzdHJhdGlvbiIsICJuYW1lIjogImhlYXQifSwgeyJlbmRwb2ludHMiOiBbeyJhZG1pblVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODA4MC8iLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODA4MC92MS9BVVRIXzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIiwgImlkIjogIjNhMTA2MzU0MjYxMDQzMjk5YTVkMjQ3ZTVmMjU5NGQyIiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6ODA4MC92MS9BVVRIXzQ1MzdhY2E0YTRhNDQ2MmZhNGM1OWFkNWI1NTgxZjAwIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogIm9iamVjdC1zdG9yZSIsICJuYW1lIjogInN3aWZ0In0sIHsiZW5kcG9pbnRzIjogW3siYWRtaW5VUkwiOiAiaHR0cDovLzE3Mi4yMS43LjQwOjM1MzU3L3YyLjAiLCAicmVnaW9uIjogIlJlZ2lvbk9uZSIsICJpbnRlcm5hbFVSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6NTAwMC92Mi4wIiwgImlkIjogIjVjNGVlN2MzMTE4NDQyNGM5NDJhMWM1MjgxODU3MmZiIiwgInB1YmxpY1VSTCI6ICJodHRwOi8vMTcyLjIxLjcuNDA6NTAwMC92Mi4wIn1dLCAiZW5kcG9pbnRzX2xpbmtzIjogW10sICJ0eXBlIjogImlkZW50aXR5IiwgIm5hbWUiOiAia2V5c3RvbmUifV0sICJ1c2VyIjogeyJ1c2VybmFtZSI6ICJhZG1pbiIsICJyb2xlc19saW5rcyI6IFtdLCAiaWQiOiAiOTFkNzMyYjY1ODMxNDkxZDhiZDk1MmIzMTExZTYyZGQiLCAicm9sZXMiOiBbeyJuYW1lIjogImhlYXRfc3RhY2tfb3duZXIifSwgeyJuYW1lIjogIl9tZW1iZXJfIn0sIHsibmFtZSI6ICJhZG1pbiJ9XSwgIm5hbWUiOiAiYWRtaW4ifSwgIm1ldGFkYXRhIjogeyJpc19hZG1pbiI6IDAsICJyb2xlcyI6IFsiZDlmZGVlODI1NjE3NGJlNWE3MmFjZGZmNDNkM2VkZDMiLCAiOWZlMmZmOWVlNDM4NGIxODk0YTkwODc4ZDNlOTJiYWIiLCAiN2E1ZTg5MmFiYTE5NDI3NWI3ZjQxZWM4Njg2ZDUwOGYiXX19fTGCAYEwggF9AgEBMFwwVzELMAkGA1UEBhMCVVMxDjAMBgNVBAgMBVVuc2V0MQ4wDAYDVQQHDAVVbnNldDEOMAwGA1UECgwFVW5zZXQxGDAWBgNVBAMMD3d3dy5leGFtcGxlLmNvbQIBATAHBgUrDgMCGjANBgkqhkiG9w0BAQEFAASCAQBQBlspOIEc8ti93kChL5n8kuPx3xZ7pTfZjzYoZXhMO5Ilzc3CUVtb16UrcHHV3eJeDmhm4C1q4BELfLx28M3XsaFb-guEyKR+HAKMouAGloqAm+B+2-6sOch8excyl7-Dv9VvSm7XlFVANjVpboRSt19D0jUau+KaasdNnFy2-o7pbUwQuIH1LfWFB3utLVvCo5kpBwismb6Rv0x6uQ5Eush9fKoIcbBT763v82BsAbm9Ho+zo9sIJZkbNrUSduJzhBDtoBH-IGpNkqOSQGptRSSCveiaz+hdd+iXNDnlu-7X7AdhLQR4r8lVs7ohDmTxVSoX7EQtiJutX9l-C5BR', 'remote_address': '172.21.7.40', 'quota_class': None, 'is_admin': True, 'tenant': u'4537aca4a4a4462fa4c59ad5b5581f00', 'service_catalog': [{u'endpoints_links': [], u'endpoints': [{u'adminURL': u'http://172.21.7.40:8776/v1/4537aca4a4a4462fa4c59ad5b5581f00', u'region': u'RegionOne', u'publicURL': u'http://172.21.7.40:8776/v1/4537aca4a4a4462fa4c59ad5b5581f00', u'id': u'0a1c8da4f156495aad2130e2c0691982', u'internalURL': u'http://172.21.7.40:8776/v1/4537aca4a4a4462fa4c59ad5b5581f00'}], u'type': u'volume', u'name': u'cinder'}], 'request_id': 'req-faf62846-4921-4242-87c8-d19c8df73d6f', 'instance_lock_checked': False, 'project_id': u'4537aca4a4a4462fa4c59ad5b5581f00', 'user_name': u'admin', 'read_deleted': 'no', 'user': u'91d732b65831491d8bd952b3111e62dd'}
    exc = <class 'xdrs.exception.PolicyNotAuthorized'>
    args = ()
    kwargs = {'action': 'xdrs:get_algorithms'}
    ======================================================================================
    """
    
    # Allow the rule to be a Check tree
    if isinstance(rule, BaseCheck):
        result = rule(target, creds)
    elif not _rules:
        # No rules to reference means we're going to fail closed
        result = False
    else:
        try:
            # Evaluate the rule
            result = _rules[rule](target, creds)
            """
            _rules就是文件/etc/xdrs/policy.json中的内容，这个文件中规定了API中各个操作方法的执行者权限；
            从而得到：
            ......
            "compute_extension:admin_actions:suspend": "rule:admin_or_owner", 
            ......
            _rules[rule] = rule:admin_or_owner
            result = True
            """
        except KeyError:
            # If the rule doesn't exist, fail closed
            result = False

    # If it is False, raise the exception if requested
    if exc and result is False:
        raise exc(*args, **kwargs)

    return result


class BaseCheck(object):
    """
    Abstract base class for Check classes.
    """
    
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def __str__(self):
        """
        Retrieve a string representation of the Check tree rooted at
        this node.
        """

        pass

    @abc.abstractmethod
    def __call__(self, target, cred):
        """
        Perform the check.  Returns False to reject the access or a
        true value (not necessary True) to accept the access.
        """

        pass


class FalseCheck(BaseCheck):
    """
    A policy check that always returns False (disallow).
    """

    def __str__(self):
        """
        Return a string representation of this check.
        """

        return "!"

    def __call__(self, target, cred):
        """
        Check the policy.
        """

        return False


class TrueCheck(BaseCheck):
    """
    A policy check that always returns True (allow).
    """

    def __str__(self):
        """
        Return a string representation of this check.
        """

        return "@"

    def __call__(self, target, cred):
        """
        Check the policy.
        """

        return True


class Check(BaseCheck):
    """
    A base class to allow for user-defined policy checks.
    """

    def __init__(self, kind, match):
        """
        :param kind: The kind of the check, i.e., the field before the
                     ':'.
        :param match: The match of the check, i.e., the field after
                      the ':'.
        """

        self.kind = kind
        self.match = match

    def __str__(self):
        """
        Return a string representation of this check.
        """

        return "%s:%s" % (self.kind, self.match)


class NotCheck(BaseCheck):
    """
    A policy check that inverts the result of another policy check.
    Implements the "not" operator.
    """

    def __init__(self, rule):
        """
        Initialize the 'not' check.

        :param rule: The rule to negate.  Must be a Check.
        """

        self.rule = rule

    def __str__(self):
        """
        Return a string representation of this check.
        """

        return "not %s" % self.rule

    def __call__(self, target, cred):
        """
        Check the policy.  Returns the logical inverse of the wrapped
        check.
        """

        return not self.rule(target, cred)


class AndCheck(BaseCheck):
    """
    A policy check that requires that a list of other checks all
    return True.  Implements the "and" operator.
    """

    def __init__(self, rules):
        """
        Initialize the 'and' check.
        :param rules: A list of rules that will be tested.
        """

        self.rules = rules

    def __str__(self):
        """
        Return a string representation of this check.
        """

        return "(%s)" % ' and '.join(str(r) for r in self.rules)

    def __call__(self, target, cred):
        """
        Check the policy.  Requires that all rules accept in order to
        return True.
        """

        for rule in self.rules:
            if not rule(target, cred):
                return False

        return True

    def add_check(self, rule):
        """
        Allows addition of another rule to the list of rules that will
        be tested.  Returns the AndCheck object for convenience.
        """

        self.rules.append(rule)
        return self


class OrCheck(BaseCheck):
    """
    A policy check that requires that at least one of a list of other
    checks returns True.  Implements the "or" operator.
    """

    def __init__(self, rules):
        """
        Initialize the 'or' check.
        :param rules: A list of rules that will be tested.
        """

        self.rules = rules

    def __str__(self):
        """
        Return a string representation of this check.
        """

        return "(%s)" % ' or '.join(str(r) for r in self.rules)

    def __call__(self, target, cred):
        """
        Check the policy.  Requires that at least one rule accept in
        order to return True.
        """

        for rule in self.rules:
            if rule(target, cred):
                return True

        return False

    def add_check(self, rule):
        """
        Allows addition of another rule to the list of rules that will
        be tested.  Returns the OrCheck object for convenience.
        """

        self.rules.append(rule)
        return self


def _parse_check(rule):
    """
    Parse a single base check rule into an appropriate Check object.
    """

    # Handle the special checks
    if rule == '!':
        return FalseCheck()
    elif rule == '@':
        return TrueCheck()

    try:
        kind, match = rule.split(':', 1)
    except Exception:
        # If the rule is invalid, we'll fail closed
        return FalseCheck()

    # Find what implements the check
    if kind in _checks:
        return _checks[kind](kind, match)
    elif None in _checks:
        return _checks[None](kind, match)
    else:
        return FalseCheck()


def _parse_list_rule(rule):
    """
    Provided for backwards compatibility.  Translates the old
    list-of-lists syntax into a tree of Check objects.
    """

    # Empty rule defaults to True
    if not rule:
        return TrueCheck()

    # Outer list is joined by "or"; inner list by "and"
    or_list = []
    for inner_rule in rule:
        # Elide empty inner lists
        if not inner_rule:
            continue

        # Handle bare strings
        if isinstance(inner_rule, basestring):
            inner_rule = [inner_rule]

        # Parse the inner rules into Check objects
        and_list = [_parse_check(r) for r in inner_rule]

        # Append the appropriate check to the or_list
        if len(and_list) == 1:
            or_list.append(and_list[0])
        else:
            or_list.append(AndCheck(and_list))

    # If we have only one check, omit the "or"
    if len(or_list) == 0:
        return FalseCheck()
    elif len(or_list) == 1:
        return or_list[0]

    return OrCheck(or_list)


# Used for tokenizing the policy language
_tokenize_re = re.compile(r'\s+')


def _parse_tokenize(rule):
    """
    Tokenizer for the policy language.

    Most of the single-character tokens are specified in the
    _tokenize_re; however, parentheses need to be handled specially,
    because they can appear inside a check string.  Thankfully, those
    parentheses that appear inside a check string can never occur at
    the very beginning or end ("%(variable)s" is the correct syntax).
    """

    for tok in _tokenize_re.split(rule):
        # Skip empty tokens
        if not tok or tok.isspace():
            continue

        # Handle leading parens on the token
        clean = tok.lstrip('(')
        for i in range(len(tok) - len(clean)):
            yield '(', '('

        # If it was only parentheses, continue
        if not clean:
            continue
        else:
            tok = clean

        # Handle trailing parens on the token
        clean = tok.rstrip(')')
        trail = len(tok) - len(clean)

        # Yield the cleaned token
        lowered = clean.lower()
        if lowered in ('and', 'or', 'not'):
            # Special tokens
            yield lowered, clean
        elif clean:
            # Not a special token, but not composed solely of ')'
            if len(tok) >= 2 and ((tok[0], tok[-1]) in
                                  [('"', '"'), ("'", "'")]):
                # It's a quoted string
                yield 'string', tok[1:-1]
            else:
                yield 'check', _parse_check(clean)

        # Yield the trailing parens
        for i in range(trail):
            yield ')', ')'


class ParseStateMeta(type):
    """
    Metaclass for the ParseState class.  Facilitates identifying
    reduction methods.
    """

    def __new__(mcs, name, bases, cls_dict):
        """
        Create the class.  Injects the 'reducers' list, a list of
        tuples matching token sequences to the names of the
        corresponding reduction methods.
        """

        reducers = []

        for key, value in cls_dict.items():
            if not hasattr(value, 'reducers'):
                continue
            for reduction in value.reducers:
                reducers.append((reduction, key))

        cls_dict['reducers'] = reducers

        return super(ParseStateMeta, mcs).__new__(mcs, name, bases, cls_dict)


def reducer(*tokens):
    """
    Decorator for reduction methods.  Arguments are a sequence of
    tokens, in order, which should trigger running this reduction
    method.
    """

    def decorator(func):
        # Make sure we have a list of reducer sequences
        if not hasattr(func, 'reducers'):
            func.reducers = []

        # Add the tokens to the list of reducer sequences
        func.reducers.append(list(tokens))

        return func

    return decorator


class ParseState(object):
    """
    Implement the core of parsing the policy language.  Uses a greedy
    reduction algorithm to reduce a sequence of tokens into a single
    terminal, the value of which will be the root of the Check tree.

    Note: error reporting is rather lacking.  The best we can get with
    this parser formulation is an overall "parse failed" error.
    Fortunately, the policy language is simple enough that this
    shouldn't be that big a problem.
    """

    __metaclass__ = ParseStateMeta

    def __init__(self):
        """
        Initialize the ParseState.
        """

        self.tokens = []
        self.values = []

    def reduce(self):
        """
        Perform a greedy reduction of the token stream.  If a reducer
        method matches, it will be executed, then the reduce() method
        will be called recursively to search for any more possible
        reductions.
        """

        for reduction, methname in self.reducers:
            if (len(self.tokens) >= len(reduction) and
                    self.tokens[-len(reduction):] == reduction):
                # Get the reduction method
                meth = getattr(self, methname)

                # Reduce the token stream
                results = meth(*self.values[-len(reduction):])

                # Update the tokens and values
                self.tokens[-len(reduction):] = [r[0] for r in results]
                self.values[-len(reduction):] = [r[1] for r in results]

                # Check for any more reductions
                return self.reduce()

    def shift(self, tok, value):
        """
        Adds one more token to the state.  Calls reduce().
        """

        self.tokens.append(tok)
        self.values.append(value)

        # Do a greedy reduce...
        self.reduce()

    @property
    def result(self):
        """
        Obtain the final result of the parse.  Raises ValueError if
        the parse failed to reduce to a single result.
        """

        if len(self.values) != 1:
            raise ValueError("Could not parse rule")
        return self.values[0]

    @reducer('(', 'check', ')')
    @reducer('(', 'and_expr', ')')
    @reducer('(', 'or_expr', ')')
    def _wrap_check(self, _p1, check, _p2):
        """
        Turn parenthesized expressions into a 'check' token.
        """

        return [('check', check)]

    @reducer('check', 'and', 'check')
    def _make_and_expr(self, check1, _and, check2):
        """
        Create an 'and_expr' from two checks joined by the 'and'
        operator.
        """

        return [('and_expr', AndCheck([check1, check2]))]

    @reducer('and_expr', 'and', 'check')
    def _extend_and_expr(self, and_expr, _and, check):
        """
        Extend an 'and_expr' by adding one more check.
        """

        return [('and_expr', and_expr.add_check(check))]

    @reducer('check', 'or', 'check')
    def _make_or_expr(self, check1, _or, check2):
        """
        Create an 'or_expr' from two checks joined by the 'or'
        operator.
        """

        return [('or_expr', OrCheck([check1, check2]))]

    @reducer('or_expr', 'or', 'check')
    def _extend_or_expr(self, or_expr, _or, check):
        """
        Extend an 'or_expr' by adding one more check.
        """

        return [('or_expr', or_expr.add_check(check))]

    @reducer('not', 'check')
    def _make_not_expr(self, _not, check):
        """
        Invert the result of another check.
        """

        return [('check', NotCheck(check))]


def _parse_text_rule(rule):
    """
    Translates a policy written in the policy language into a tree of
    Check objects.
    """

    # Empty rule means always accept
    if not rule:
        return TrueCheck()

    # Parse the token stream
    state = ParseState()
    for tok, value in _parse_tokenize(rule):
        state.shift(tok, value)

    try:
        return state.result
    except ValueError:
        # Fail closed
        return FalseCheck()


def parse_rule(rule):
    """
    Parses a policy rule into a tree of Check objects.
    """

    # If the rule is a string, it's in the policy language
    if isinstance(rule, basestring):
        return _parse_text_rule(rule)
    return _parse_list_rule(rule)