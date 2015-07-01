from xdrs.api import extensions

def authorize(context, action_name):
    action = action_name
    """
    实际上就是通过文件/etc/xdrs/policy.json中的内容，
    这个文件中规定了API中各个操作方法的执行者权限；
    从而得到：
    ......
    "compute_extension:admin_actions:suspend": "rule:admin_or_owner", 
    ......
    _rules[rule] = rule:admin_or_owner
    result = True
    
    注：撰写/etc/xdrs/policy.json文件；
    """
    extensions.extension_authorizer('xdrs', action)(context)


































