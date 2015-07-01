import copy

from oslo.config import cfg


database_opts = [
    cfg.StrOpt('sqlite_db',
               deprecated_group='DEFAULT',
               default='xdrs.sqlite',
               help='The file name to use with SQLite'),
    cfg.BoolOpt('sqlite_synchronous',
                deprecated_group='DEFAULT',
                default=True,
                help='If True, SQLite uses synchronous mode'),
    cfg.StrOpt('backend',
               default='sqlalchemy',
               deprecated_name='db_backend',
               deprecated_group='DEFAULT',
               help='The backend to use for db'),
    cfg.StrOpt('connection',
               help='The SQLAlchemy connection string used to connect to the '
                    'database',
               secret=True,
               deprecated_opts=[cfg.DeprecatedOpt('sql_connection',
                                                  group='DEFAULT'),
                                cfg.DeprecatedOpt('sql_connection',
                                                  group='DATABASE'),
                                cfg.DeprecatedOpt('connection',
                                                  group='sql'), ]),
    cfg.StrOpt('mysql_sql_mode',
               help='The SQL mode to be used for MySQL sessions '
                    '(default is empty, meaning do not override '
                    'any server-side SQL mode setting)'),
    cfg.IntOpt('idle_timeout',
               default=3600,
               deprecated_opts=[cfg.DeprecatedOpt('sql_idle_timeout',
                                                  group='DEFAULT'),
                                cfg.DeprecatedOpt('sql_idle_timeout',
                                                  group='DATABASE'),
                                cfg.DeprecatedOpt('idle_timeout',
                                                  group='sql')],
               help='Timeout before idle sql connections are reaped'),
    cfg.IntOpt('min_pool_size',
               default=1,
               deprecated_opts=[cfg.DeprecatedOpt('sql_min_pool_size',
                                                  group='DEFAULT'),
                                cfg.DeprecatedOpt('sql_min_pool_size',
                                                  group='DATABASE')],
               help='Minimum number of SQL connections to keep open in a '
                    'pool'),
    cfg.IntOpt('max_pool_size',
               default=None,
               deprecated_opts=[cfg.DeprecatedOpt('sql_max_pool_size',
                                                  group='DEFAULT'),
                                cfg.DeprecatedOpt('sql_max_pool_size',
                                                  group='DATABASE')],
               help='Maximum number of SQL connections to keep open in a '
                    'pool'),
    cfg.IntOpt('max_retries',
               default=10,
               deprecated_opts=[cfg.DeprecatedOpt('sql_max_retries',
                                                  group='DEFAULT'),
                                cfg.DeprecatedOpt('sql_max_retries',
                                                  group='DATABASE')],
               help='Maximum db connection retries during startup. '
                    '(setting -1 implies an infinite retry count)'),
    cfg.IntOpt('retry_interval',
               default=10,
               deprecated_opts=[cfg.DeprecatedOpt('sql_retry_interval',
                                                  group='DEFAULT'),
                                cfg.DeprecatedOpt('reconnect_interval',
                                                  group='DATABASE')],
               help='Interval between retries of opening a sql connection'),
    cfg.IntOpt('max_overflow',
               default=None,
               deprecated_opts=[cfg.DeprecatedOpt('sql_max_overflow',
                                                  group='DEFAULT'),
                                cfg.DeprecatedOpt('sqlalchemy_max_overflow',
                                                  group='DATABASE')],
               help='If set, use this value for max_overflow with sqlalchemy'),
    cfg.IntOpt('connection_debug',
               default=0,
               deprecated_opts=[cfg.DeprecatedOpt('sql_connection_debug',
                                                  group='DEFAULT')],
               help='Verbosity of SQL debugging information. 0=None, '
                    '100=Everything'),
    cfg.BoolOpt('connection_trace',
                default=False,
                deprecated_opts=[cfg.DeprecatedOpt('sql_connection_trace',
                                                   group='DEFAULT')],
                help='Add python stack traces to SQL as comment strings'),
    cfg.IntOpt('pool_timeout',
               default=None,
               deprecated_opts=[cfg.DeprecatedOpt('sqlalchemy_pool_timeout',
                                                  group='DATABASE')],
               help='If set, use this value for pool_timeout with sqlalchemy'),
    cfg.BoolOpt('use_db_reconnect',
                default=False,
                help='Enable the experimental use of database reconnect '
                     'on connection lost'),
    cfg.IntOpt('db_retry_interval',
               default=1,
               help='seconds between db connection retries'),
    cfg.BoolOpt('db_inc_retry_interval',
                default=True,
                help='Whether to increase interval between db connection '
                     'retries, up to db_max_retry_interval'),
    cfg.IntOpt('db_max_retry_interval',
               default=10,
               help='max seconds between db connection retries, if '
                    'db_inc_retry_interval is enabled'),
    cfg.IntOpt('db_max_retries',
               default=20,
               help='maximum db connection retries before error is raised. '
                    '(setting -1 implies an infinite retry count)'),
]

CONF = cfg.CONF
CONF.register_opts(database_opts, 'database')


def set_defaults(sql_connection, sqlite_db, max_pool_size=None,
                 max_overflow=None, pool_timeout=None):
    """
    Set defaults for configuration variables.
    """
    cfg.set_defaults(database_opts,
                     connection=sql_connection,
                     sqlite_db=sqlite_db)
    # Update the QueuePool defaults
    if max_pool_size is not None:
        cfg.set_defaults(database_opts,
                         max_pool_size=max_pool_size)
    if max_overflow is not None:
        cfg.set_defaults(database_opts,
                         max_overflow=max_overflow)
    if pool_timeout is not None:
        cfg.set_defaults(database_opts,
                         pool_timeout=pool_timeout)


def list_opts():
    """
    Returns a list of oslo.config options available in the library.
    """
    return [('database', copy.deepcopy(database_opts))]
