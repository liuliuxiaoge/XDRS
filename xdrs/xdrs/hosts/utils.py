import os
import pwd
import grp

def drop_privileges(user):
    """
    Sets the userid/groupid of the current process, get session leader, etc.
    :param user: User name to change privileges to
    设置当前进程的userid/groupid，并获取session leader等；
    """
    if os.geteuid() == 0:
        groups = [g.gr_gid for g in grp.getgrall() if user in g.gr_mem]
        os.setgroups(groups)
    user = pwd.getpwnam(user)
    os.setgid(user[3])
    os.setuid(user[2])
    os.environ['HOME'] = user[5]
    try:
        os.setsid()
    except OSError:
        pass
    os.chdir('/')   # in case you need to rmdir on where you started the daemon
    os.umask(0o22)  # ensure files are created with the correct privileges
    