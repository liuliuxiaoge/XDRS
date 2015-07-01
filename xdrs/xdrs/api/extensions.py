"""
用于实现功能扩展的若干实现类；
"""
import xdrs.policy

def core_authorizer(api_name, extension_name):
    """
    ======================================================================================
    api_name = xdrs
    extension_name = get_algorithms
    ======================================================================================
    """
    def authorize(context, target=None, action=None):
        """
        ======================================================================================
        context = <xdrs.context.RequestContext object at 0x6dcf050>
        target = None
        action = None
        ======================================================================================
        """
        if target is None:
            target = {'project_id': context.project_id,
                      'user_id': context.user_id}
        if action is None:
            act = '%s:%s' % (api_name, extension_name)
        else:
            act = '%s:%s:%s' % (api_name, extension_name, action)
        
        """
        ======================================================================================
        context = <xdrs.context.RequestContext object at 0x6dcf050>
        target = {'project_id': u'4537aca4a4a4462fa4c59ad5b5581f00', 'user_id': u'91d732b65831491d8bd952b3111e62dd'}
        act = xdrs:get_algorithms
        ======================================================================================
        """
        xdrs.policy.enforce(context, act, target)
    return authorize


def extension_authorizer(api_name, extension_name):
    """
    ======================================================================================
    api_name = xdrs
    extension_name = get_algorithms
    ======================================================================================
    """
    return core_authorizer(api_name, extension_name)