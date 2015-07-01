import os
import re

from migrate import exceptions as versioning_exceptions
from migrate.versioning import api as versioning_api
from migrate.versioning.repository import Repository
import sqlalchemy
from sqlalchemy.schema import UniqueConstraint

from xdrs.openstack.common.db import exception
from xdrs.openstack.common.gettextutils import _


def _get_unique_constraints(self, table):
    """
    Retrieve information about existing unique constraints of the table
    """

    data = table.metadata.bind.execute(
        """SELECT sql
           FROM sqlite_master
           WHERE
               type='table' AND
               name=:table_name""",
        table_name=table.name
    ).fetchone()[0]

    UNIQUE_PATTERN = "CONSTRAINT (\w+) UNIQUE \(([^\)]+)\)"
    return [
        UniqueConstraint(
            *[getattr(table.columns, c.strip(' "')) for c in cols.split(",")],
            name=name
        )
        for name, cols in re.findall(UNIQUE_PATTERN, data)
    ]


def _recreate_table(self, table, column=None, delta=None, omit_uniques=None):
    """
    Recreate the table properly
    """

    table_name = self.preparer.format_table(table)

    # we remove all indexes so as not to have
    # problems during copy and re-create
    for index in table.indexes:
        index.drop()

    # reflect existing unique constraints
    for uc in self._get_unique_constraints(table):
        table.append_constraint(uc)
    # omit given unique constraints when creating a new table if required
    table.constraints = set([
        cons for cons in table.constraints
        if omit_uniques is None or cons.name not in omit_uniques
    ])

    self.append('ALTER TABLE %s RENAME TO migration_tmp' % table_name)
    self.execute()

    insertion_string = self._modify_table(table, column, delta)

    table.create(bind=self.connection)
    self.append(insertion_string % {'table_name': table_name})
    self.execute()
    self.append('DROP TABLE migration_tmp')
    self.execute()


def _visit_migrate_unique_constraint(self, *p, **k):
    """
    Drop the given unique constraint
    """

    self.recreate_table(p[0].table, omit_uniques=[p[0].name])


def db_sync(engine, abs_path, version=None, init_version=0):
    """
    Upgrade or downgrade a database.
    """
    if version is not None:
        try:
            version = int(version)
        except ValueError:
            raise exception.DbMigrationError(
                message=_("version should be an integer"))

    current_version = db_version(engine, abs_path, init_version)
    repository = _find_migrate_repo(abs_path)
    _db_schema_sanity_check(engine)
    if version is None or version > current_version:
        return versioning_api.upgrade(engine, repository, version)
    else:
        return versioning_api.downgrade(engine, repository,
                                        version)


def _db_schema_sanity_check(engine):
    """
    Ensure all database tables were created with required parameters.
    """

    if engine.name == 'mysql':
        onlyutf8_sql = ('SELECT TABLE_NAME,TABLE_COLLATION '
                        'from information_schema.TABLES '
                        'where TABLE_SCHEMA=%s and '
                        'TABLE_COLLATION NOT LIKE "%%utf8%%"')

        table_names = [res[0] for res in engine.execute(onlyutf8_sql,
                                                        engine.url.database)]
        if len(table_names) > 0:
            raise ValueError(_('Tables "%s" have non utf8 collation, '
                               'please make sure all tables are CHARSET=utf8'
                               ) % ','.join(table_names))


def db_version(engine, abs_path, init_version):
    """
    Show the current version of the repository.
    """
    repository = _find_migrate_repo(abs_path)
    try:
        return versioning_api.db_version(engine, repository)
    except versioning_exceptions.DatabaseNotControlledError:
        meta = sqlalchemy.MetaData()
        meta.reflect(bind=engine)
        tables = meta.tables
        if len(tables) == 0 or 'alembic_version' in tables:
            db_version_control(engine, abs_path, version=init_version)
            return versioning_api.db_version(engine, repository)
        else:
            raise exception.DbMigrationError(
                message=_(
                    "The database is not under version control, but has "
                    "tables. Please stamp the current version of the schema "
                    "manually."))


def db_version_control(engine, abs_path, version=None):
    """
    Mark a database as under this repository's version control.
    """
    repository = _find_migrate_repo(abs_path)
    versioning_api.version_control(engine, repository, version)
    return version


def _find_migrate_repo(abs_path):
    """
    Get the project's change script repository
    """
    if not os.path.exists(abs_path):
        raise exception.DbMigrationError("Path %s not found" % abs_path)
    return Repository(abs_path)
