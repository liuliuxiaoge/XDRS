"""
Session Handling for SQLAlchemy backend.
"""

import functools
import logging
import re
import time

import six
from sqlalchemy import exc as sqla_exc
from sqlalchemy.interfaces import PoolListener
import sqlalchemy.orm
from sqlalchemy.pool import NullPool, StaticPool
from sqlalchemy.sql.expression import literal_column

from xdrs.openstack.common.db import exception
from xdrs.openstack.common.gettextutils import _LE, _LW, _LI
from xdrs.openstack.common import timeutils


LOG = logging.getLogger(__name__)


class SqliteForeignKeysListener(PoolListener):
    """
    Ensures that the foreign key constraints are enforced in SQLite.
    """
    def connect(self, dbapi_con, con_record):
        dbapi_con.execute('pragma foreign_keys=ON')


_DUP_KEY_RE_DB = {
    "sqlite": (re.compile(r"^.*columns?([^)]+)(is|are)\s+not\s+unique$"),
               re.compile(r"^.*UNIQUE\s+constraint\s+failed:\s+(.+)$")),
    "postgresql": (re.compile(r"^.*duplicate\s+key.*\"([^\"]+)\"\s*\n.*$"),),
    "mysql": (re.compile(r"^.*\(1062,.*'([^\']+)'\"\)$"),),
    "ibm_db_sa": (re.compile(r"^.*SQL0803N.*$"),),
}


def _raise_if_duplicate_entry_error(integrity_error, engine_name):
    """
    Raise exception if two entries are duplicated.
    """

    def get_columns_from_uniq_cons_or_name(columns):
        # note(vsergeyev): UniqueConstraint name convention: "uniq_t0c10c2"
        #                  where `t` it is table name and columns `c1`, `c2`
        #                  are in UniqueConstraint.
        uniqbase = "uniq_"
        if not columns.startswith(uniqbase):
            if engine_name == "postgresql":
                return [columns[columns.index("_") + 1:columns.rindex("_")]]
            return [columns]
        return columns[len(uniqbase):].split("0")[1:]

    if engine_name not in ["ibm_db_sa", "mysql", "sqlite", "postgresql"]:
        return

    # FIXME(johannes): The usage of the .message attribute has been
    # deprecated since Python 2.6. However, the exceptions raised by
    # SQLAlchemy can differ when using unicode() and accessing .message.
    # An audit across all three supported engines will be necessary to
    # ensure there are no regressions.
    for pattern in _DUP_KEY_RE_DB[engine_name]:
        match = pattern.match(integrity_error.message)
        if match:
            break
    else:
        return

    # NOTE(mriedem): The ibm_db_sa integrity error message doesn't provide the
    # columns so we have to omit that from the DBDuplicateEntry error.
    columns = ''

    if engine_name != 'ibm_db_sa':
        columns = match.group(1)

    if engine_name == "sqlite":
        columns = [c.split('.')[-1] for c in columns.strip().split(", ")]
    else:
        columns = get_columns_from_uniq_cons_or_name(columns)
    raise exception.DBDuplicateEntry(columns, integrity_error)


# NOTE(comstud): In current versions of DB backends, Deadlock violation
# messages follow the structure:
#
# mysql:
# (OperationalError) (1213, 'Deadlock found when trying to get lock; try '
#                     'restarting transaction') <query_str> <query_args>
_DEADLOCK_RE_DB = {
    "mysql": re.compile(r"^.*\(1213, 'Deadlock.*")
}


def _raise_if_deadlock_error(operational_error, engine_name):
    """
    Raise exception on deadlock condition.
    """
    re = _DEADLOCK_RE_DB.get(engine_name)
    if re is None:
        return
    # FIXME(johannes): The usage of the .message attribute has been
    # deprecated since Python 2.6. However, the exceptions raised by
    # SQLAlchemy can differ when using unicode() and accessing .message.
    # An audit across all three supported engines will be necessary to
    # ensure there are no regressions.
    m = re.match(operational_error.message)
    if not m:
        return
    raise exception.DBDeadlock(operational_error)


def _wrap_db_error(f):
    #TODO(rpodolyaka): in a subsequent commit make this a class decorator to
    # ensure it can only applied to Session subclasses instances (as we use
    # Session instance bind attribute below)

    @functools.wraps(f)
    def _wrap(self, *args, **kwargs):
        try:
            return f(self, *args, **kwargs)
        except UnicodeEncodeError:
            raise exception.DBInvalidUnicodeParameter()
        except sqla_exc.OperationalError as e:
            _raise_if_db_connection_lost(e, self.bind)
            _raise_if_deadlock_error(e, self.bind.dialect.name)
            # NOTE(comstud): A lot of code is checking for OperationalError
            # so let's not wrap it for now.
            raise
        # note(boris-42): We should catch unique constraint violation and
        # wrap it by our own DBDuplicateEntry exception. Unique constraint
        # violation is wrapped by IntegrityError.
        except sqla_exc.IntegrityError as e:
            # note(boris-42): SqlAlchemy doesn't unify errors from different
            # DBs so we must do this. Also in some tables (for example
            # instance_types) there are more than one unique constraint. This
            # means we should get names of columns, which values violate
            # unique constraint, from error message.
            _raise_if_duplicate_entry_error(e, self.bind.dialect.name)
            raise exception.DBError(e)
        except Exception as e:
            LOG.exception(_LE('DB exception wrapped.'))
            raise exception.DBError(e)
    return _wrap


def _synchronous_switch_listener(dbapi_conn, connection_rec):
    """Switch sqlite connections to non-synchronous mode."""
    dbapi_conn.execute("PRAGMA synchronous = OFF")


def _add_regexp_listener(dbapi_con, con_record):
    """Add REGEXP function to sqlite connections."""

    def regexp(expr, item):
        reg = re.compile(expr)
        return reg.search(six.text_type(item)) is not None
    dbapi_con.create_function('regexp', 2, regexp)


def _thread_yield(dbapi_con, con_record):
    """
    Ensure other greenthreads get a chance to be executed.
    """
    time.sleep(0)


def _ping_listener(engine, dbapi_conn, connection_rec, connection_proxy):
    """
    Ensures that MySQL and DB2 connections are alive.
    """
    cursor = dbapi_conn.cursor()
    try:
        ping_sql = 'select 1'
        if engine.name == 'ibm_db_sa':
            # DB2 requires a table expression
            ping_sql = 'select 1 from (values (1)) AS t1'
        cursor.execute(ping_sql)
    except Exception as ex:
        if engine.dialect.is_disconnect(ex, dbapi_conn, cursor):
            msg = _LW('Database server has gone away: %s') % ex
            LOG.warning(msg)
            raise sqla_exc.DisconnectionError(msg)
        else:
            raise


def _set_mode_traditional(dbapi_con, connection_rec, connection_proxy):
    """
    Set engine mode to 'traditional'.
    """
    _set_session_sql_mode(dbapi_con, connection_rec,
                          connection_proxy, 'TRADITIONAL')


def _set_session_sql_mode(dbapi_con, connection_rec,
                          connection_proxy, sql_mode=None):
    """
    Set the sql_mode session variable.
    """
    cursor = dbapi_con.cursor()
    if sql_mode is not None:
        cursor.execute("SET SESSION sql_mode = %s", [sql_mode])

    # Check against the real effective SQL mode. Even when unset by
    # our own config, the server may still be operating in a specific
    # SQL mode as set by the server configuration
    cursor.execute("SHOW VARIABLES LIKE 'sql_mode'")
    row = cursor.fetchone()
    if row is None:
        LOG.warning(_LW('Unable to detect effective SQL mode'))
        return
    realmode = row[1]
    LOG.info(_LI('MySQL server mode set to %s') % realmode)
    # 'TRADITIONAL' mode enables several other modes, so
    # we need a substring match here
    if not ('TRADITIONAL' in realmode.upper() or
            'STRICT_ALL_TABLES' in realmode.upper()):
        LOG.warning(_LW("MySQL SQL mode is '%s', "
                        "consider enabling TRADITIONAL or STRICT_ALL_TABLES")
                    % realmode)


def _is_db_connection_error(args):
    """Return True if error in connecting to db."""
    # NOTE(adam_g): This is currently MySQL specific and needs to be extended
    #               to support Postgres and others.
    # For the db2, the error code is -30081 since the db2 is still not ready
    conn_err_codes = ('2002', '2003', '2006', '2013', '-30081')
    for err_code in conn_err_codes:
        if args.find(err_code) != -1:
            return True
    return False


def _raise_if_db_connection_lost(error, engine):
    # NOTE(vsergeyev): Function is_disconnect(e, connection, cursor)
    #                  requires connection and cursor in incoming parameters,
    #                  but we have no possibility to create connection if DB
    #                  is not available, so in such case reconnect fails.
    #                  But is_disconnect() ignores these parameters, so it
    #                  makes sense to pass to function None as placeholder
    #                  instead of connection and cursor.
    if engine.dialect.is_disconnect(error, None, None):
        raise exception.DBConnectionError(error)


def create_engine(sql_connection, sqlite_fk=False, mysql_sql_mode=None,
                  mysql_traditional_mode=False, idle_timeout=3600,
                  connection_debug=0, max_pool_size=None, max_overflow=None,
                  pool_timeout=None, sqlite_synchronous=True,
                  connection_trace=False, max_retries=10, retry_interval=10):
    """Return a new SQLAlchemy engine."""

    connection_dict = sqlalchemy.engine.url.make_url(sql_connection)

    engine_args = {
        "pool_recycle": idle_timeout,
        'convert_unicode': True,
    }

    logger = logging.getLogger('sqlalchemy.engine')

    # Map SQL debug level to Python log level
    if connection_debug >= 100:
        logger.setLevel(logging.DEBUG)
    elif connection_debug >= 50:
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.WARNING)

    if "sqlite" in connection_dict.drivername:
        if sqlite_fk:
            engine_args["listeners"] = [SqliteForeignKeysListener()]
        engine_args["poolclass"] = NullPool

        if sql_connection == "sqlite://":
            engine_args["poolclass"] = StaticPool
            engine_args["connect_args"] = {'check_same_thread': False}
    else:
        if max_pool_size is not None:
            engine_args['pool_size'] = max_pool_size
        if max_overflow is not None:
            engine_args['max_overflow'] = max_overflow
        if pool_timeout is not None:
            engine_args['pool_timeout'] = pool_timeout

    engine = sqlalchemy.create_engine(sql_connection, **engine_args)

    sqlalchemy.event.listen(engine, 'checkin', _thread_yield)

    if engine.name in ['mysql', 'ibm_db_sa']:
        ping_callback = functools.partial(_ping_listener, engine)
        sqlalchemy.event.listen(engine, 'checkout', ping_callback)
        if engine.name == 'mysql':
            if mysql_traditional_mode:
                mysql_sql_mode = 'TRADITIONAL'
            if mysql_sql_mode:
                mode_callback = functools.partial(_set_session_sql_mode,
                                                  sql_mode=mysql_sql_mode)
                sqlalchemy.event.listen(engine, 'checkout', mode_callback)
    elif 'sqlite' in connection_dict.drivername:
        if not sqlite_synchronous:
            sqlalchemy.event.listen(engine, 'connect',
                                    _synchronous_switch_listener)
        sqlalchemy.event.listen(engine, 'connect', _add_regexp_listener)

    if connection_trace and engine.dialect.dbapi.__name__ == 'MySQLdb':
        _patch_mysqldb_with_stacktrace_comments()

    try:
        engine.connect()
    except sqla_exc.OperationalError as e:
        if not _is_db_connection_error(e.args[0]):
            raise

        remaining = max_retries
        if remaining == -1:
            remaining = 'infinite'
        while True:
            msg = _LW('SQL connection failed. %s attempts left.')
            LOG.warning(msg % remaining)
            if remaining != 'infinite':
                remaining -= 1
            time.sleep(retry_interval)
            try:
                engine.connect()
                break
            except sqla_exc.OperationalError as e:
                if (remaining != 'infinite' and remaining == 0) or \
                        not _is_db_connection_error(e.args[0]):
                    raise
    return engine


class Query(sqlalchemy.orm.query.Query):
    """Subclass of sqlalchemy.query with soft_delete() method."""
    def soft_delete(self, synchronize_session='evaluate'):
        return self.update({'deleted': literal_column('id'),
                            'updated_at': literal_column('updated_at'),
                            'deleted_at': timeutils.utcnow()},
                           synchronize_session=synchronize_session)


class Session(sqlalchemy.orm.session.Session):
    """Custom Session class to avoid SqlAlchemy Session monkey patching."""
    @_wrap_db_error
    def query(self, *args, **kwargs):
        return super(Session, self).query(*args, **kwargs)

    @_wrap_db_error
    def flush(self, *args, **kwargs):
        return super(Session, self).flush(*args, **kwargs)

    @_wrap_db_error
    def execute(self, *args, **kwargs):
        return super(Session, self).execute(*args, **kwargs)


def get_maker(engine, autocommit=True, expire_on_commit=False):
    """Return a SQLAlchemy sessionmaker using the given engine."""
    return sqlalchemy.orm.sessionmaker(bind=engine,
                                       class_=Session,
                                       autocommit=autocommit,
                                       expire_on_commit=expire_on_commit,
                                       query_cls=Query)


def _patch_mysqldb_with_stacktrace_comments():
    """Adds current stack trace as a comment in queries.

    Patches MySQLdb.cursors.BaseCursor._do_query.
    """
    import MySQLdb.cursors
    import traceback

    old_mysql_do_query = MySQLdb.cursors.BaseCursor._do_query

    def _do_query(self, q):
        stack = ''
        for filename, line, method, function in traceback.extract_stack():
            # exclude various common things from trace
            if filename.endswith('session.py') and method == '_do_query':
                continue
            if filename.endswith('api.py') and method == 'wrapper':
                continue
            if filename.endswith('utils.py') and method == '_inner':
                continue
            if filename.endswith('exception.py') and method == '_wrap':
                continue
            # db/api is just a wrapper around db/sqlalchemy/api
            if filename.endswith('db/api.py'):
                continue

            index = filename.rfind('xdrs')
            if index == -1:
                continue
            stack += "File:%s:%s Method:%s() Line:%s | " \
                     % (filename[index:], line, method, function)

        # strip trailing " | " from stack
        if stack:
            stack = stack[:-3]
            qq = "%s /* %s */" % (q, stack)
        else:
            qq = q
        old_mysql_do_query(self, qq)

    setattr(MySQLdb.cursors.BaseCursor, '_do_query', _do_query)


class EngineFacade(object):
    def __init__(self, sql_connection,
                 sqlite_fk=False, mysql_sql_mode=None,
                 autocommit=True, expire_on_commit=False, **kwargs):
        """
        Initialize engine and sessionmaker instances.
        """

        super(EngineFacade, self).__init__()

        self._engine = create_engine(
            sql_connection=sql_connection,
            sqlite_fk=sqlite_fk,
            mysql_sql_mode=mysql_sql_mode,
            idle_timeout=kwargs.get('idle_timeout', 3600),
            connection_debug=kwargs.get('connection_debug', 0),
            max_pool_size=kwargs.get('max_pool_size'),
            max_overflow=kwargs.get('max_overflow'),
            pool_timeout=kwargs.get('pool_timeout'),
            sqlite_synchronous=kwargs.get('sqlite_synchronous', True),
            connection_trace=kwargs.get('connection_trace', False),
            max_retries=kwargs.get('max_retries', 10),
            retry_interval=kwargs.get('retry_interval', 10))
        self._session_maker = get_maker(
            engine=self._engine,
            autocommit=autocommit,
            expire_on_commit=expire_on_commit)

    def get_engine(self):
        """Get the engine instance (note, that it's shared)."""

        return self._engine

    def get_session(self, **kwargs):
        """
        Get a Session instance.
        """

        for arg in kwargs:
            if arg not in ('autocommit', 'expire_on_commit'):
                del kwargs[arg]

        return self._session_maker(**kwargs)
