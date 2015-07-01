"""Provision test environment for specific DB backends"""

import argparse
import os
import random
import string

from six import moves
import sqlalchemy

from xdrs.openstack.common.db import exception as exc


SQL_CONNECTION = os.getenv('OS_TEST_DBAPI_ADMIN_CONNECTION', 'sqlite://')


def _gen_credentials(*names):
    """Generate credentials."""
    auth_dict = {}
    for name in names:
        val = ''.join(random.choice(string.ascii_lowercase)
                      for i in moves.range(10))
        auth_dict[name] = val
    return auth_dict


def _get_engine(uri=SQL_CONNECTION):
    """
    Engine creation
    """
    return sqlalchemy.create_engine(uri, poolclass=sqlalchemy.pool.NullPool)


def _execute_sql(engine, sql, driver):
    """
    Initialize connection, execute sql query and close it.
    """
    try:
        with engine.connect() as conn:
            if driver == 'postgresql':
                conn.connection.set_isolation_level(0)
            for s in sql:
                conn.execute(s)
    except sqlalchemy.exc.OperationalError:
        msg = ('%s does not match database admin '
               'credentials or database does not exist.')
        raise exc.DBConnectionError(msg % SQL_CONNECTION)


def create_database(engine):
    """
    Provide temporary user and database for each particular test.
    """
    driver = engine.name

    auth = _gen_credentials('database', 'user', 'passwd')

    sqls = {
        'mysql': [
            "drop database if exists %(database)s;",
            "grant all on %(database)s.* to '%(user)s'@'localhost'"
            " identified by '%(passwd)s';",
            "create database %(database)s;",
        ],
        'postgresql': [
            "drop database if exists %(database)s;",
            "drop user if exists %(user)s;",
            "create user %(user)s with password '%(passwd)s';",
            "create database %(database)s owner %(user)s;",
        ]
    }

    if driver == 'sqlite':
        return 'sqlite:////tmp/%s' % auth['database']

    try:
        sql_rows = sqls[driver]
    except KeyError:
        raise ValueError('Unsupported RDBMS %s' % driver)
    sql_query = map(lambda x: x % auth, sql_rows)

    _execute_sql(engine, sql_query, driver)

    params = auth.copy()
    params['backend'] = driver
    return "%(backend)s://%(user)s:%(passwd)s@localhost/%(database)s" % params


def drop_database(engine, current_uri):
    """
    Drop temporary database and user after each particular test.
    """
    engine = _get_engine(current_uri)
    admin_engine = _get_engine()
    driver = engine.name
    auth = {'database': engine.url.database, 'user': engine.url.username}

    if driver == 'sqlite':
        try:
            os.remove(auth['database'])
        except OSError:
            pass
        return

    sqls = {
        'mysql': [
            "drop database if exists %(database)s;",
            "drop user '%(user)s'@'localhost';",
        ],
        'postgresql': [
            "drop database if exists %(database)s;",
            "drop user if exists %(user)s;",
        ]
    }

    try:
        sql_rows = sqls[driver]
    except KeyError:
        raise ValueError('Unsupported RDBMS %s' % driver)
    sql_query = map(lambda x: x % auth, sql_rows)

    _execute_sql(admin_engine, sql_query, driver)


def main():
    """
    Controller to handle commands
    """
    parser = argparse.ArgumentParser(
        description='Controller to handle database creation and dropping'
        ' commands.',
        epilog='Under normal circumstances is not used directly.'
        ' Used in .testr.conf to automate test database creation'
        ' and dropping processes.')
    subparsers = parser.add_subparsers(
        help='Subcommands to manipulate temporary test databases.')

    create = subparsers.add_parser(
        'create',
        help='Create temporary test '
        'databases and users.')
    create.set_defaults(which='create')
    create.add_argument(
        'instances_count',
        type=int,
        help='Number of databases to create.')

    drop = subparsers.add_parser(
        'drop',
        help='Drop temporary test databases and users.')
    drop.set_defaults(which='drop')
    drop.add_argument(
        'instances',
        nargs='+',
        help='List of databases uri to be dropped.')

    args = parser.parse_args()

    engine = _get_engine()
    which = args.which

    if which == "create":
        for i in range(int(args.instances_count)):
            print(create_database(engine))
    elif which == "drop":
        for db in args.instances:
            drop_database(engine, db)


if __name__ == "__main__":
    main()
