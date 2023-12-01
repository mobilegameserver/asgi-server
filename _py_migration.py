import os
import sys
from os import listdir, environ
from os.path import isfile, join, splitext
from datetime import datetime
from urllib.parse import urlparse
from pymysql.cursors import DictCursor
import pymysql


phases = ['dev', 'beta', 'prod']
db_names = ['users', 'services', 'statistics']
root_path = '../migration/'


def print_error(message):
    print('\nERROR: ' + message)
    sys.exit(1)


class MysqlConnSettings:
    def __init__(self, db_url):
        parsed = urlparse(db_url)

        self.host = parsed.hostname
        self.user = parsed.username
        self.password = parsed.password
        self.database = parsed.path.lstrip('/')
        self.port = parsed.port
        self.charset = 'utf8mb4'
        self.cursorclass = DictCursor
        self.autocommit = True


def dotenv_load():
    with open('../.env', 'r') as f:
        lines = f.readlines()

    for line in lines:
        line_strip = line.strip()
        if line_strip == '' or line_strip[0] == '#':
            continue

        line_split = line_strip.split('=')
        if len(line_split) != 2:
            print_error('invalid line in .env: ' + line)

        k = line_split[0].strip()
        v = line_split[1].strip()

        k = k.strip('"')
        v = v.strip('"')

        k = k.strip("'")
        v = v.strip("'")

        environ[k] = v


def create(cs):
    p = join(root_path, cs.database, datetime.utcnow().strftime('%Y%m%d%H%M%S') + '.sql')
    with open(p, 'w'):
        pass

    print('\n{} created.'.format(p))
    print('OK\n')


def execute(cs):
    conn = None
    cursor = None

    try:
        conn = pymysql.connect(
            host=cs.host,
            user=cs.user,
            password=cs.password,
            database=cs.database,
            port=cs.port,
            charset=cs.charset,
            cursorclass=cs.cursorclass,
            autocommit=cs.autocommit,
        )
        cursor = conn.cursor()

        sql = 'SELECT migration_id FROM migrations ORDER BY migration_id ASC'
        cursor.execute(sql)
        rows = cursor.fetchall()

        db_migration_ids = []
        for row in rows:
            db_migration_ids.append(row['migration_id'])

        p = join(root_path, cs.database)
        files = [f for f in listdir(p) if isfile(join(p, f))]
        files.sort()

        for file in files:
            file_migration_id = int(splitext(file)[0])

            if file_migration_id in db_migration_ids:
                continue

            with open(join(root_path, cs.database, file), 'r') as f:
                sql = f.read().strip()
                if sql == '':
                    print_error('sql is empty')

                sql_split = sql.split(';')
                for s in sql_split:
                    if s.strip() == '':
                        continue

                    print(s)
                    cursor.execute(s)

            cursor.execute('INSERT INTO migrations VALUES(%s)', (file_migration_id,))
            print('migration {} executed.')

        print('\nOK\n')

    except pymysql.Error as err:
        print_error(str(err))

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def squash(cs):
    conn = None
    cursor = None

    try:
        conn = pymysql.connect(
            host=cs.host,
            user=cs.user,
            password=cs.password,
            database=cs.database,
            port=cs.port,
            charset=cs.charset,
            cursorclass=cs.cursorclass,
            autocommit=cs.autocommit,
        )
        cursor = conn.cursor()

        cursor.execute('SHOW TABLES')
        show_tables = cursor.fetchall()

        tables = []
        for show_table in show_tables:
            tables.append(show_table['Tables_in_' + cs.database])

        create_tables = ['CREATE DATABASE `{}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'.format(
            cs.database)]
        for table in tables:
            if table.upper().startswith('LOG_'):
                continue

            cursor.execute('SHOW CREATE TABLE `{0}`'.format(table))
            create_table = cursor.fetchone()['Create Table']

            create_table_parts = create_table.split(' ')
            new_create_table_parts = []
            for s in create_table_parts:
                if s.startswith('AUTO_INCREMENT='):
                    continue
                new_create_table_parts.append(s)
            create_tables.append(' '.join(new_create_table_parts))

        p = join(root_path, cs.database, '19700101000001.sql')
        with open(p, 'w') as f:
            f.write(';\n\n'.join(create_tables) + ';\n')

        p = join(root_path, cs.database)
        files = [f for f in listdir(p) if isfile(join(p, f))]
        files.sort()

        for file in files:
            file_migration_id = int(splitext(file)[0])

            if file_migration_id in [19700101000000, 19700101000001]:
                continue

            cursor.execute('DELETE FROM migrations WHERE migration_id = %s', (file_migration_id,))
            os.remove(join(root_path, cs.database, file))

        print('\nmigration squashed.')
        print('OK\n')

    except pymysql.Error as err:
        print_error(str(err))

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def migration_run(command, phase, db_name):
    if phase not in phases:
        print_error('invalid phase: ' + phase)

    if db_name not in db_names:
        print_error('invalid db_name: ' + db_name)

    dotenv_load()
    if phase != environ.get('PHASE'):
        print_error('phase mismatch: ' + phase)

    db_url = environ.get(db_name.upper() + '_DB_URL')
    cs = MysqlConnSettings(db_url)

    if command == 'create':
        create(cs)
    elif command == 'execute':
        execute(cs)
    elif command == 'squash':
        squash(cs)
    else:
        print_error('invalid migration command')


def print_usage():
    phases_joined = '[' + '|'.join(phases) + ']'
    db_names_joined = '[' + '|'.join(db_names) + ']'

    print('Usage:')
    print('\tpython3 ./_py_migration.py create {} {}'.format(phases_joined, db_names_joined))
    print('\tpython3 ./_py_migration.py execute {} {}'.format(phases_joined, db_names_joined))
    print('\tpython3 ./_py_migration.py squash {} {}'.format(phases_joined, db_names_joined))


def main():
    if len(sys.argv) < 4:
        print_usage()
        return

    migration_run(sys.argv[1], sys.argv[2], sys.argv[3])


if __name__ == '__main__':
    main()
