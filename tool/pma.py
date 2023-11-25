import time
from wsgiref.simple_server import make_server, WSGIServer
from socketserver import ThreadingMixIn
import os
import mimetypes
import pymysql
import re
from decimal import Decimal
from datetime import datetime
import json
from urllib.parse import quote, unquote, urlencode
import cgi
from hashlib import md5
from base64 import urlsafe_b64encode, urlsafe_b64decode
from pymysql.cursors import DictCursor


# database
class MysqlConnSettings:
    def __init__(self, token=None):
        self.host = ''
        self.user = ''
        self.password = ''
        self.database = ''
        self.port = 0

        if token is None:
            return

        self.host = token.data.get('mysql_host', '')
        self.user = token.data.get('mysql_user', '')
        self.password = token.data.get('mysql_password', '')
        self.database = token.data.get('mysql_database', '')
        self.port = int(token.data.get('mysql_port', 0))


class Mysql:
    def __init__(self):
        self.connection = None
        self.cursor = None

    def close(self):
        if self.cursor is not None:
            self.cursor.close()

        if self.connection is not None:
            self.connection.close()

    def connect(self, conn_settings):
        self.connection = pymysql.connect(host=conn_settings.host, user=conn_settings.user,
                                          password=conn_settings.password, database=conn_settings.database,
                                          port=conn_settings.port, charset='utf8mb4', cursorclass=DictCursor,
                                          autocommit=True)
        self.cursor = self.connection.cursor()

    def describe(self, params):
        self.cursor.execute('DESCRIBE `{}`.`{}`'.format(params.database, params.table))
        return self.cursor.fetchall()


class SqlParams:
    def __init__(self, cfg, form):
        self.database = form.getvalue('database', '')
        self.table = form.getvalue('table', '')
        self.field1 = form.getvalue('field1', '')
        self.like1 = int(form.getvalue('like1', 0))
        self.keyword1 = form.getvalue('keyword1', '')
        self.is_or = int(form.getvalue('is_or', 0))
        self.field2 = form.getvalue('field2', '')
        self.like2 = int(form.getvalue('like2', 0))
        self.keyword2 = form.getvalue('keyword2', '')
        self.order_by = form.getvalue('order_by', '')
        self.is_asc = int(form.getvalue('is_asc', 0))
        self.limit = int(form.getvalue('limit', cfg.max_limit))
        self.offset = int(form.getvalue('offset', 0))

    def querystring(self):
        return urlencode({
            'database': self.database,
            'table': self.table,
            'field1': self.field1,
            'like1': self.like1,
            'keyword1': self.keyword1,
            'is_or': self.is_or,
            'field2': self.field2,
            'like2': self.like2,
            'keyword2': self.keyword2,
            'order_by': self.order_by,
            'is_asc': self.is_asc,
            'limit': self.limit,
            'offset': self.offset,
        })


def var_type_and_def_value(column_type):
    type_upper = column_type.upper()

    if type_upper.startswith('INT') or 'INT' in type_upper:
        return 'integer', 0
    elif type_upper.startswith('FLOAT'):
        return 'float', 0
    elif type_upper.startswith('DOUBLE'):
        return 'float', 0
    elif type_upper.startswith('DECIMAL'):
        return 'decimal', 0
    elif type_upper == 'CHAR(1)':
        return 'string', 'N'
    elif 'CHAR' in type_upper:
        return 'string', ''
    elif 'TEXT' in type_upper:
        return 'text', ''
    elif type_upper == 'DATETIME':
        return 'string', '1970-01-01 00:00:00'
    elif type_upper == 'DATE':
        return 'string', '1970-01-01'
    elif type_upper == 'TIME':
        return 'string', '00:00:00'
    elif type_upper.startswith('YEAR'):
        return 'integer', 1970
    elif type_upper == 'TIMESTAMP':
        return 'timestamp', None
    elif type_upper.startswith('BIT') or 'BINARY' in type_upper or 'BLOB' in type_upper:
        return 'binary', None
    else:
        return None, ''


def column_types():
    return '''<option>int</option>
    <option>bigint</option>

    <option>float</option>
    <option>double</option>

    <option>char(1)</option>
    <option>varchar(50)</option>
    <option>varchar(190)</option>
    <option>text</option>
    <option>mediumtext</option>

    <option>datetime</option>
    <option>date</option>
    <option>time</option>'''


def column_default(var_type, def_value):
    if var_type == 'integer' or var_type == 'float' or var_type == 'decimal':
        return 'DEFAULT {}'.format(def_value)
    elif var_type == 'string':
        return "DEFAULT '{}'".format(def_value)
    else:
        return ''


# util
def is_float(s):
    try:
        float(s)
        result = True
    except ValueError:
        result = False

    return result


def is_decimal(s):
    try:
        Decimal(s)
        result = True
    except ValueError:
        result = False

    return result


def now_str(cfg):
    return datetime.now().strftime(cfg.datatime_format)


def now_int():
    return int(datetime.now().strftime('%Y%m%d%H%M%S'))


def epoch_str(cfg):
    return datetime(1970, 1, 1, 0, 0, 0, 0).strftime(cfg.datetime_format)


# token
class Token:
    def __init__(self, cfg):
        self.cfg = cfg
        self.exp = {
            'access': int(datetime.now().timestamp()) + cfg.token_access_lifetime_minutes * 60,
            'refresh': int(datetime.now().timestamp()) + cfg.token_refresh_lifetime_minutes * 60,
        }
        self.data = {}

    def load(self, s):
        if len(s) < 32:
            return False

        b64_encoded = s[:-32]
        md5_hex_digest = s[-32:]

        if md5_hex_digest != md5((b64_encoded + self.cfg.secret_key).encode('utf-8')).hexdigest():
            return False

        json_loaded = json.loads(urlsafe_b64decode(b64_encoded))
        self.exp = json_loaded.get('exp', {})

        if int(self.exp.get('access', 0)) < int(datetime.now().timestamp()):
            return False

        self.data = json_loaded.get('data', {})
        return True

    def __str__(self):
        json_dumped = json.dumps({
            'exp': self.exp,
            'data': self.data,
        }).encode('utf-8')

        b64_encoded = urlsafe_b64encode(json_dumped).decode('utf-8')
        md5_hex_digest = md5((b64_encoded + self.cfg.secret_key).encode('utf-8')).hexdigest()

        return b64_encoded + md5_hex_digest


# request
def request_cookie(env):
    http_cookie = env.get('HTTP_COOKIE', '')

    cookie = {}
    if http_cookie == '':
        return cookie

    http_cookie_split = http_cookie.split('; ')
    for name_value in http_cookie_split:
        name_value_split = name_value.split('=')
        if len(name_value_split) != 2:
            continue
        cookie[unquote(name_value_split[0])] = unquote(name_value_split[1])

    return cookie


def request_auth_token(env):
    http_authorization = env.get('HTTP_AUTHORIZATION', '')
    if http_authorization == '':
        return ''

    http_authorization_split = http_authorization.split(' ')
    if len(http_authorization_split) != 2:
        return ''

    if http_authorization_split[0] != 'Token':
        return ''

    return http_authorization_split[1]


def request_form(env):
    return cgi.FieldStorage(env.get('wsgi.input'), environ=env, keep_blank_values=1)


def request_json(env):
    content_type = env.get('CONTENT_TYPE', '')
    content_length = env.get('CONTENT_LENGTH', '')

    json_loaded = {}
    if content_type == '' or not content_type.startswith('application/json') or content_length == '':
        return json_loaded

    wsgi_input = env.get('wsgi.input', None)
    if wsgi_input is None:
        return json_loaded

    wsgi_input_read = wsgi_input.read(int(content_length))
    try:
        json_loaded = json.loads(wsgi_input_read)
    except ValueError:
        pass

    return json_loaded


# response
def response_set_cookie(name, value):
    cookie_parts = ['{}={}'.format(quote(str(name)), quote(str(value))), 'Path=/', 'httpOnly']
    return '; '.join(cookie_parts)


def response_status(func, status, headers=None, message=''):
    _headers = [('Content-type', 'text/plain; charset=utf-8')]
    if headers is not None:
        _headers.extend(headers)

    func(status, _headers)
    return ['\n\n'.join([status, message]).encode('utf-8')]


def response_text(func, text, headers=None):
    _headers = [('Content-type', 'text/plain; charset=utf-8')]
    if headers is not None:
        _headers.extend(headers)

    func('200 OK', _headers)
    return [text.encode('utf8')]


def response_html(func, html, headers=None):
    _headers = [('Content-type', 'text/html; charset=utf-8')]
    if headers is not None:
        _headers.extend(headers)

    func('200 OK', _headers)
    return [html.encode('utf8')]


def response_redirect(func, url, headers=None):
    _headers = []
    if headers is not None:
        _headers.extend(headers)

    body = '''<!DOCTYPE html><html lang="en"><head>
<meta http-equiv="refresh" content="0; url={}"></head></html>'''.format(url)
    return response_html(func, body, _headers)


def response_json(func, data, headers=None):
    _headers = [('Content-type', 'application/json; charset=utf-8')]
    if headers is not None:
        _headers.extend(headers)

    func('200 OK', _headers)
    return [json.dumps(data).encode('utf8')]


# html
def html_head(params=None, nav=True):
    html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=0">

    <title>Python Mysql Admin</title>
    <style>
    body {
        font-family: Arial, Helvetica, sans-serif;
    }

    input, select, textarea, button {
        font-size: 1em;
    }

    a:link {
        text-decoration: none;
    }

    .light-gray {
        color: #d3d3d3;
    }

    .dark-gray {
        color: #a9a9a9;
    }

    .red {
        color: red;
    }

    .form1 {
        line-height: 2em;
    }

    .table-overflow-auto {
        overflow-x: auto;
    }

    table {
        border: 1px solid #a9a9a9;
    }

    tr:hover {
        background: #dcdcdc;
    }

    th, td {
        border: 1px solid #a9a9a9;
        padding: .5em;
    }

    footer {
        margin-top: 2em;
    }
    </style>
</head>
<body>'''

    nav_database = ''
    if params is not None and params.database != '':
        nav_database = '<a href="/mysql/show_tables?database={}">{}</a> |'.format(params.database, params.database)

    nav_table = ''
    if params is not None and params.table != '':
        nav_table = '<a href="/mysql/select_rows?{}">{}</a> |'.format(params.querystring(), params.table)

    if nav:
        html += '''<nav>
    <a href="/mysql/show_databases">databases</a> |
    {}
    {}
    <a href="/mysql/disconnect">disconnect</a>
</nav>
<hr class="light-gray">

<main>'''.format(nav_database, nav_table)
    else:
        html += '<main>'

    return html


def html_tail():
    html = '''</main>

<footer>
    <hr class="light-gray">
    &copy; {} Python Mysql Admin
</footer>

</body>
</html>'''.format(datetime.now().strftime('%Y'))

    return html


# decorator
def mysql_conn_required(original_function):
    def wrapper_function(*args, **kwargs):
        func = args[0]
        token = args[2]

        mysql_host = token.data.get('mysql_host', '')
        if mysql_host == '':
            # return response_status(func, '401 Unauthorized')
            return response_redirect(func, '/mysql/connect_form')
        return original_function(*args, **kwargs)

    return wrapper_function


# handler
def index(func, _env, _token, _cfg):
    return response_redirect(func, '/mysql/connect_form')


def mysql_connect_form(func, _env, _token, _cfg):
    html = html_head(nav=False) + '''<h1>connect</h1>
    <form class="form1" method="post" action="/mysql/connect">
        <input name="host" placeholder="host" type="text" value="127.0.0.1"><br>
        <input name="user" placeholder="user" type="text" value="user"><br>
        <input name="password" placeholder="password" type="text" value="password"><br>
        <input name="database" placeholder="database" type="text" value="mysql"><br>
        <input name="port" placeholder="port" type="text" value="3306"><br>
        <input name="submit" type="submit" value="submit">
    </form>''' + html_tail()

    return response_html(func, html)


def mysql_connect(func, _env, _token, _cfg):
    form = request_form(_env)
    host = form.getvalue('host', '')
    user = form.getvalue('user', '')
    password = form.getvalue('password', '')
    database = form.getvalue('database', '')
    port = int(form.getvalue('port', 0))

    if host == '' or user == '' or password == '' or database == '' or port == 0:
        return response_status(func, '400 Bad Request')

    conn_settings = MysqlConnSettings()
    conn_settings.host = host
    conn_settings.user = user
    conn_settings.password = password
    conn_settings.database = database
    conn_settings.port = port

    db = Mysql()
    try:
        db.connect(conn_settings)

        _token.data['mysql_host'] = host
        _token.data['mysql_user'] = user
        _token.data['mysql_password'] = password
        _token.data['mysql_database'] = database
        _token.data['mysql_port'] = port

        return response_redirect(func, '/mysql/show_databases', [
            ('Set-Cookie', response_set_cookie('token', str(_token)))
        ])
    except pymysql.Error as error:
        return response_status(func, '500 Internal Server Error', message=str(error))
    finally:
        db.close()


@mysql_conn_required
def mysql_disconnect(func, _env, _token, _cfg):
    return response_redirect(func, '/mysql/connect_form', [('Set-Cookie', response_set_cookie('token', ''))])


@mysql_conn_required
def mysql_show_databases(func, _env, _token, _cfg):
    conn_settings = MysqlConnSettings(_token)

    db = Mysql()
    try:
        db.connect(conn_settings)
        db.cursor.execute('SHOW DATABASES')
        _databases = db.cursor.fetchall()

        databases = []
        for _d in _databases:
            d = _d['Database']
            if d in ['information_schema', 'mysql', 'performance_schema', 'sys', 'test']:
                continue
            databases.append(d)
        databases.sort()

        html = html_head() + '<h1>show databases</h1><div class="table-overflow-auto"><table>'
        for d in databases:
            html += '''<tr>
            <th>{}</th>
            <td><a href="/mysql/show_tables?database={}">show tables</a></td>
            <td><button onClick="if (confirm('Are you sure?')) location.href = '/mysql/drop_database?database_name={}'"
            >drop database</button></td>
            <td><a href="/mysql/dump_database?database={}">dump database</a></td>
            </tr>'''.format(d, d, d, d)

        if len(databases) == 0:
            html += '<tr><td class="red">No Databases Found</td></tr>'
        html += '''</table></div>

    <hr>
    <h1>create database</h1>
    <form class="form1" method="post" action="/mysql/create_database">
        <input name="database_name" placeholder="database_name" type="text">
        <input name="submit" type="submit" value="submit">
    </form>''' + html_tail()

        return response_html(func, html)
    except pymysql.Error as error:
        return response_status(func, '500 Internal Server Error', message=str(error))
    finally:
        db.close()


@mysql_conn_required
def mysql_create_database(func, _env, _token, _cfg):
    conn_settings = MysqlConnSettings(_token)
    form = request_form(_env)
    params = SqlParams(_cfg, form)
    database_name = form.getvalue('database_name', '')

    if re.match(r'^\w+$', database_name) is None:
        return response_status(func, '400 Bad Request')

    db = Mysql()
    try:
        db.connect(conn_settings)
        sql = 'CREATE DATABASE `{}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'.format(
            database_name)
        db.cursor.execute(sql)

        html = html_head(params) + '<h1>OK: create database `{}`</h1>'.format(database_name) + html_tail()
        return response_html(func, html)
    except pymysql.Error as error:
        return response_status(func, '500 Internal Server Error', message=str(error))
    finally:
        db.close()


@mysql_conn_required
def mysql_drop_database(func, _env, _token, _cfg):
    conn_settings = MysqlConnSettings(_token)
    form = request_form(_env)
    params = SqlParams(_cfg, form)
    database_name = form.getvalue('database_name', '')

    if re.match(r'^\w+$', database_name) is None:
        return response_status(func, '400 Bad Request')

    db = Mysql()
    try:
        db.connect(conn_settings)
        sql = 'DROP DATABASE `{}`'.format(database_name)
        db.cursor.execute(sql)

        html = html_head(params) + '<h1>OK: drop database `{}`</h1>'.format(database_name) + html_tail()
        return response_html(func, html)
    except pymysql.Error as error:
        return response_status(func, '500 Internal Server Error', message=str(error))
    finally:
        db.close()


@mysql_conn_required
def mysql_dump_database(func, _env, _token, _cfg):
    conn_settings = MysqlConnSettings(_token)
    form = request_form(_env)
    params = SqlParams(_cfg, form)

    if re.match(r'^\w+$', params.database) is None:
        return response_status(func, '400 Bad Request')

    db = Mysql()
    try:
        conn_settings.database = params.database
        db.connect(conn_settings)

        db.cursor.execute('SHOW TABLES')
        show_tables = db.cursor.fetchall()

        tables = []
        for show_table in show_tables:
            tables.append(show_table['Tables_in_' + params.database])

        create_tables = ['CREATE DATABASE `{}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'.format(
            params.database)]
        for table in tables:
            if table.upper().startswith('LOG'):
                continue

            db.cursor.execute('SHOW CREATE TABLE `{0}`'.format(table))
            create_table = db.cursor.fetchone()['Create Table']

            create_table_parts = create_table.split(' ')
            new_create_table_parts = []
            for s in create_table_parts:
                if s.startswith('AUTO_INCREMENT='):
                    continue
                new_create_table_parts.append(s)
            create_tables.append(' '.join(new_create_table_parts))

        return response_text(func, ';\n\n'.join(create_tables) + ';\n')
    except pymysql.Error as error:
        return response_status(func, '500 Internal Server Error', message=str(error))
    finally:
        db.close()


@mysql_conn_required
def mysql_show_tables(func, _env, _token, _cfg):
    conn_settings = MysqlConnSettings(_token)
    form = request_form(_env)
    params = SqlParams(_cfg, form)

    if re.match(r'^\w+$', params.database.replace(' ', '')) is None:
        return response_status(func, '400 Bad Request')

    db = Mysql()
    try:
        conn_settings.database = params.database
        db.connect(conn_settings)
        db.cursor.execute('SHOW TABLES IN `{}`'.format(params.database))
        tables = db.cursor.fetchall()

        html = html_head(params) + '''<h1>show tables in `{}`</h1>
    <div class="table-overflow-auto">
        <table>'''.format(params.database)

        for _t in tables:
            t = _t['Tables_in_{}'.format(params.database)]

            html += '''<tr>
            <th>{}</th>
            <td><a href="/mysql/select_rows?database={}&table={}">select rows</a></td>
            <td><button
            onClick="if (confirm('Are you sure?')) location.href = '/mysql/drop_table?database={}&table_name={}'"
            >drop table</button></td>
            <td><a href="/mysql/alter_table_form?database={}&table={}">alter table</a></td>
            <td><a href="/mysql/rename_table_form?database={}&table={}">rename table</a></td>
            <td><a href="/mysql/describe_table?database={}&table={}">describe table</a></td>
            <td><a href="/mysql/show_create_table?database={}&table={}">show create table</a></td>
            <td><a href="/mysql/show_index?database={}&table={}">show index</a></td>
        </tr>'''.format(t, params.database, t, params.database, t, params.database, t, params.database, t,
                        params.database, t, params.database, t, params.database, t)

        if len(tables) == 0:
            html += '<tr><td class="red">No Tables Found</td></tr>'
        html += '''</table>
    </div>

    <hr>
    <h1>create table</h1>
    <form class="form1" method="post" action="/mysql/create_table_form">
        <input name="database" type="hidden" value="{}">
        <input name="table_name" placeholder="table_name" type="text"><br>
        <input name="number_of_columns" placeholder="number_of_columns" type="text"><br>
        <input name="submit" type="submit" value="submit">
    </form>'''.format(params.database) + html_tail()

        return response_html(func, html)
    except pymysql.Error as error:
        return response_status(func, '500 Internal Server Error', message=str(error))
    finally:
        db.close()


@mysql_conn_required
def mysql_create_table_form(func, _env, _token, _cfg):
    form = request_form(_env)
    params = SqlParams(_cfg, form)

    table_name = form.getvalue('table_name', '')
    number_of_columns = int(form.getvalue('number_of_columns', 0))

    if re.match(r'^\w+$', params.database) is None or re.match(r'^\w+$', table_name) is None or number_of_columns < 1:
        return response_status(func, '400 Bad Request')

    html = html_head(params) + '''<h1>create table `{}`</h1>
    <form method="post" action="/mysql/create_table">
        <input name="database" type="hidden" value="{}">
        <input name="table_name" type="hidden" value="{}">
        <input name="number_of_columns" type="hidden" value="{}">
    <div class="table-overflow-auto">
        <table>
            <tr>					
                <th>Field</th>
                <th>Type</th>
                <th>Null</th>
                <th>Key</th>
                <th>Default</th>
                <th>Extra</th>
            </tr>'''.format(table_name, params.database, table_name, number_of_columns)

    for i in range(number_of_columns):
        html += '''<tr>
            <td><input name="field" type="text"></td>
            <td><select name="type">{}</select></td>
            <td><select name="null">
                <option>NOT NULL</option>
                <option>NULL</option>
            </select></td>
            <td><select name="key">
                <option></option>
                <option>PRIMARY</option>
                <option>UNIQUE</option>
                <option>INDEX</option>
            </select></td>
            <td><input name="default" type="text"></td>
            <td><select name="extra">
                <option></option>
                <option>AUTO_INCREMENT</option>
            </select></td>
        </tr>'''.format(column_types())

    html += '</table></div><p><input name="submit" type="submit" value="submit"></p></form>' + html_tail()
    return response_html(func, html)


@mysql_conn_required
def mysql_create_table(func, _env, _token, _cfg):
    conn_settings = MysqlConnSettings(_token)
    form = request_form(_env)
    params = SqlParams(_cfg, form)

    table_name = form.getvalue('table_name', '')
    number_of_columns = int(form.getvalue('number_of_columns', 0))
    fields = form.getlist('field')
    types = form.getlist('type')
    nulls = form.getlist('null')
    defaults = form.getlist('default')
    keys = form.getlist('key')
    extras = form.getlist('extra')

    if re.match(r'^\w+$', params.database) is None or re.match(r'^\w+$', table_name) is None or number_of_columns < 1:
        return response_status(func, '400 Bad Request')

    db = Mysql()
    try:
        columns = []
        primary_keys = []
        unique_indexes = []
        indexes = []
        auto_increments = []

        for i in range(number_of_columns):
            _field = fields[i]
            _type = types[i]
            _null = nulls[i]
            _default = defaults[i]
            _key = keys[i]
            _extra = extras[i]

            var_type, def_value = var_type_and_def_value(_type)
            if _default == '':
                _default = def_value
            _default = column_default(var_type, _default)

            if _key == 'PRIMARY':
                if _extra == 'AUTO_INCREMENT':
                    _default = 'AUTO_INCREMENT'
            columns.append(' '.join([_field, _type, _null, _default]))

            if _key == 'PRIMARY':
                primary_keys.append(_field)
            elif _key == 'UNIQUE':
                unique_indexes.append(_field)
            elif _key == 'INDEX':
                indexes.append(_field)

            if _extra == 'AUTO_INCREMENT':
                auto_increments.append(_extra)

        if len(primary_keys) > 0:
            columns.append('PRIMARY KEY ({})'.format(', '.join(primary_keys)))

        if len(unique_indexes) > 0:
            columns.append('UNIQUE INDEX {}_{}_unique ({})'.format(table_name, unique_indexes[0],
                                                                   ', '.join(unique_indexes)))

        if len(indexes) > 0:
            columns.append('INDEX {}_{}_index ({})'.format(table_name, indexes[0], ', '.join(indexes)))

        if len(auto_increments) > 1:
            return response_status(func, '400 Bad Request')

        sql = 'CREATE TABLE `{}`.`{}` (\n'.format(params.database, table_name) + ',\n'.join(columns) + \
              '\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci'
        # print(sql)

        conn_settings.database = params.database
        db.connect(conn_settings)
        db.cursor.execute(sql)

        html = html_head(params) + '<h1>OK: create table `{}`</h1>'.format(table_name) + html_tail()
        return response_html(func, html)
    except pymysql.Error as error:
        return response_status(func, '500 Internal Server Error', message=str(error))
    finally:
        db.close()


@mysql_conn_required
def mysql_drop_table(func, _env, _token, _cfg):
    conn_settings = MysqlConnSettings(_token)
    form = request_form(_env)
    params = SqlParams(_cfg, form)
    table_name = form.getvalue('table_name', '')

    if re.match(r'^\w+$', params.database) is None or re.match(r'^\w+$', table_name) is None:
        return response_status(func, '400 Bad Request')

    db = Mysql()
    try:
        conn_settings.database = params.database
        db.connect(conn_settings)
        sql = 'DROP TABLE `{}`.`{}`'.format(params.database, table_name)
        db.cursor.execute(sql)

        html = html_head(params) + '<h1>OK: drop table `{}`</h1>'.format(table_name) + html_tail()
        return response_html(func, html)
    except pymysql.Error as error:
        return response_status(func, '500 Internal Server Error', message=str(error))
    finally:
        db.close()


@mysql_conn_required
def mysql_alter_table_form(func, _env, _token, _cfg):
    conn_settings = MysqlConnSettings(_token)
    form = request_form(_env)
    params = SqlParams(_cfg, form)

    if re.match(r'^\w+$', params.database) is None or re.match(r'^\w+$', params.table) is None:
        return response_status(func, '400 Bad Request')

    db = Mysql()
    try:
        html = html_head(params) + '''<h1>alter table `{}`</h1>
    <div class="table-overflow-auto">
        <table>
            <tr>
                <th>Field</th>
                <th>Type</th>
                <th>Null</th>
                <th>Key</th>
                <th>Default</th>
                <th>Extra</th>
                <td>Primary</td>
                <td>Unique</td>
                <td>Index</td>
                <form class="form1 method="post" action="/mysql/alter_table">
                    <input name="database" type="hidden" value="{}">
                    <input name="table" type="hidden" value="{}">
                <td><input name="new_column_name" placeholder="new_column_name" type="text"></td>
                <td><select name="new_column_type">{}</select></td>
                <td><input name="add_first" type="submit" value="add first"></td>
                </form>
                <td>Change</td>
                <td>Drop</td>
            </tr>'''.format(params.table, params.database, params.table, column_types())

        conn_settings.database = params.database
        db.connect(conn_settings)
        descriptions = db.describe(params)

        for desc in descriptions:
            var_type, _ = var_type_and_def_value(desc['Type'])

            if desc['Default'] is None:
                desc['Default'] = 'NULL'
            elif var_type == 'string':
                desc['Default'] = "'{}'".format(desc['Default'])

            if desc['Key'] == 'PRI':
                add_drop_primary = '<input name="drop_primary" type="submit" value="drop primary">'
            else:
                add_drop_primary = '<input name="add_primary" type="submit" value="add primary">'

            if desc['Key'] == 'UNI':
                add_drop_unique = '<input name="drop_unique" type="submit" value="drop unique">'
            else:
                add_drop_unique = '<input name="add_unique" type="submit" value="add unique">'

            if desc['Key'] == 'MUL':
                add_drop_index = '<input name="drop_index" type="submit" value="drop index">'
            else:
                add_drop_index = '<input name="add_index" type="submit" value="add index">'

            html += '''<tr>
            <td>{}</td>
            <td>{}</td>
            <td>{}</td>
            <td>{}</td>
            <td>{}</td>
            <td>{}</td>
            <form class="form1 method="post" action="/mysql/alter_table">
                <input name="database" type="hidden" value="{}">
                <input name="table" type="hidden" value="{}">
                <input name="column" type="hidden" value="{}">
            <td>{}</td>
            <td>{}</td>
            <td>{}</td>
            <td><input name="new_column_name" placeholder="new_column_name" type="text"></td>
            <td><select name="new_column_type">{}</select></td>
            <td><input name="add_after" type="submit" value="add after"></td>
            <td><input name="change_column" type="submit" value="change"></td>
            <td><input name="drop_column" type="submit" value="drop"></td>
            </form>
        </tr>'''.format(desc['Field'], desc['Type'], desc['Null'], desc['Key'], desc['Default'], desc['Extra'],
                        params.database, params.table, desc['Field'], add_drop_primary, add_drop_unique,
                        add_drop_index, column_types())

        html += '</table></div>'.format(params.database)
        html += '''
        <script>
            window.addEventListener('load', function () {
                window.addEventListener('keydown', function (evt) {
                    if (evt.code === 'Enter') {
                        evt.preventDefault()
                    }
                })
            })
        </script>
        '''
        html += html_tail()
        return response_html(func, html)
    except pymysql.Error as error:
        return response_status(func, '500 Internal Server Error', message=str(error))
    finally:
        db.close()


@mysql_conn_required
def mysql_alter_table(func, _env, _token, _cfg):
    conn_settings = MysqlConnSettings(_token)
    form = request_form(_env)
    params = SqlParams(_cfg, form)

    add_primary = form.getvalue('add_primary', '')
    drop_primary = form.getvalue('drop_primary', '')

    add_unique = form.getvalue('add_unique', '')
    drop_unique = form.getvalue('drop_unique', '')

    add_index = form.getvalue('add_index', '')
    drop_index = form.getvalue('drop_index', '')

    add_first = form.getvalue('add_first', '')
    add_after = form.getvalue('add_after', '')
    change_column = form.getvalue('change_column', '')
    drop_column = form.getvalue('drop_column', '')

    column = form.getvalue('column', '')
    new_column_name = form.getvalue('new_column_name', '')
    new_column_type = form.getvalue('new_column_type', '')

    if re.match(r'^\w+$', params.database) is None or re.match(r'^\w+$', params.table) is None:
        return response_status(func, '400 Bad Request')

    db = Mysql()
    try:
        conn_settings.database = params.database
        db.connect(conn_settings)

        db.cursor.execute('SHOW INDEX FROM `{}`.`{}`'.format(params.database, params.table))
        indexes = db.cursor.fetchall()

        key_name = ''
        for i in indexes:
            if i['Column_name'] == column:
                key_name = i['Key_name']
                break

        sql_parts = ['ALTER TABLE `{}`.`{}`'.format(params.database, params.table)]
        var_type, def_value = var_type_and_def_value(new_column_type)
        new_column_default = column_default(var_type, def_value)

        if add_primary != '':
            sql_parts.append('ADD PRIMARY KEY(`{}`)'.format(column))
        elif drop_primary != '':
            sql_parts.append('DROP PRIMARY KEY')
        elif add_unique != '':
            sql_parts.append('ADD UNIQUE INDEX (`{}`)'.format(column))
        elif drop_unique != '':
            sql_parts.append('DROP INDEX `{}`'.format(key_name))
        elif add_index != '':
            sql_parts.append('ADD INDEX (`{}`)'.format(column))
        elif drop_index != '':
            sql_parts.append('DROP INDEX `{}`'.format(key_name))
        elif add_first != '':
            sql_parts.append('ADD `{}` {} NOT NULL {} FIRST'.format(new_column_name, new_column_type,
                                                                    new_column_default))
        elif add_after != '':
            sql_parts.append('ADD `{}` {} NOT NULL {} AFTER `{}`'.format(new_column_name, new_column_type,
                                                                         new_column_default, column))
        elif change_column != '':
            sql_parts.append('CHANGE `{}` `{}` {} NOT NULL {}'.format(column, new_column_name, new_column_type,
                                                                      new_column_default))
        elif drop_column != '':
            sql_parts.append('DROP `{}`'.format(column))

        sql = ' '.join(sql_parts)
        db.cursor.execute(sql)

        html = html_head(params) + '<h1>OK: alter table `{}`</h1>'.format(params.table)
        html += html_tail()
        return response_html(func, html)
    except pymysql.Error as error:
        return response_status(func, '500 Internal Server Error', message=str(error))
    finally:
        db.close()


@mysql_conn_required
def mysql_rename_table_form(func, _env, _token, _cfg):
    form = request_form(_env)
    params = SqlParams(_cfg, form)

    if re.match(r'^\w+$', params.database) is None or re.match(r'^\w+$', params.table) is None:
        return response_status(func, '400 Bad Request')

    html = html_head(params) + '''<h1>alter table `{}` rename to</h1>
        <form class="form1" method="post" action="/mysql/rename_table">
            <input name="database" type="hidden" value="{}">
            <input name="table_name" type="hidden" value="{}">
            <input name="new_table_name" placeholder="new_table_name" type="text"><br>
            <input name="submit" type="submit" value="submit">
        </form>'''.format(params.table, params.database, params.table) + html_tail()

    return response_html(func, html)


@mysql_conn_required
def mysql_rename_table(func, _env, _token, _cfg):
    conn_settings = MysqlConnSettings(_token)
    form = request_form(_env)
    params = SqlParams(_cfg, form)
    table_name = form.getvalue('table_name', '')
    new_table_name = form.getvalue('new_table_name', '')

    if re.match(r'^\w+$', params.database) is None or re.match(r'^\w+$', table_name) is None or \
            re.match(r'^\w+$', new_table_name) is None:
        return response_status(func, '400 Bad Request')

    db = Mysql()
    try:
        conn_settings.database = params.database
        db.connect(conn_settings)
        sql = 'ALTER TABLE `{}`.`{}` RENAME TO `{}`.`{}`'.format(params.database, table_name, params.database,
                                                                 new_table_name)
        db.cursor.execute(sql)

        html = html_head(params) + '<h1>OK: alter table `{}` renamed to `{}`</h1>'.format(table_name, new_table_name)
        html += html_tail()
        return response_html(func, html)
    except pymysql.Error as error:
        return response_status(func, '500 Internal Server Error', message=str(error))
    finally:
        db.close()


@mysql_conn_required
def mysql_describe_table(func, _env, _token, _cfg):
    conn_settings = MysqlConnSettings(_token)
    form = request_form(_env)
    params = SqlParams(_cfg, form)

    if re.match(r'^\w+$', params.database) is None or re.match(r'^\w+$', params.table) is None:
        return response_status(func, '400 Bad Request')

    db = Mysql()
    try:
        html = html_head(params) + '''<h1>describe `{}`</h1>
    <div class="table-overflow-auto">
        <table>
            <tr>
                <th>Field</th>
                <th>Type</th>
                <th>Null</th>
                <th>Key</th>
                <th>Default</th>
                <th>Extra</th>
            </tr>'''.format(params.table)

        conn_settings.database = params.database
        db.connect(conn_settings)
        descriptions = db.describe(params)

        for desc in descriptions:
            var_type, _ = var_type_and_def_value(desc['Type'])

            if desc['Default'] is None:
                desc['Default'] = 'NULL'
            elif var_type == 'string':
                desc['Default'] = "'{}'".format(desc['Default'])

            html += '''<tr>
            <td>{}</td>
            <td>{}</td>
            <td>{}</td>
            <td>{}</td>
            <td>{}</td>
            <td>{}</td>
        </tr>'''.format(desc['Field'], desc['Type'], desc['Null'], desc['Key'], desc['Default'], desc['Extra'])

        html += '</table></div>'.format(params.database) + html_tail()
        return response_html(func, html)
    except pymysql.Error as error:
        return response_status(func, '500 Internal Server Error', message=str(error))
    finally:
        db.close()


@mysql_conn_required
def mysql_show_create_table(func, _env, _token, _cfg):
    conn_settings = MysqlConnSettings(_token)
    form = request_form(_env)
    params = SqlParams(_cfg, form)

    if re.match(r'^\w+$', params.database) is None or re.match(r'^\w+$', params.table) is None:
        return response_status(func, '400 Bad Request')

    db = Mysql()
    try:
        html = html_head(params) + '''<h1>show create table `{}`</h1>
        <div class="table-overflow-auto">
            <table>
                <tr>
                    <th>Table</th>
                    <th>Create Table</th>
                </tr>'''.format(params.table)

        conn_settings.database = params.database
        db.connect(conn_settings)
        db.cursor.execute('SHOW CREATE TABLE `{}`.`{}`'.format(params.database, params.table))
        show_create_table = db.cursor.fetchall()

        for sct in show_create_table:
            html += '''<tr>
                <td>{}</td>
                <td>{}</td>
            </tr>'''.format(sct['Table'], sct['Create Table'].replace('\n', '<br>'))

        html += '</table></div>'.format(params.database) + html_tail()
        return response_html(func, html)
    except pymysql.Error as error:
        return response_status(func, '500 Internal Server Error', message=str(error))
    finally:
        db.close()


@mysql_conn_required
def mysql_show_index(func, _env, _token, _cfg):
    conn_settings = MysqlConnSettings(_token)
    form = request_form(_env)
    params = SqlParams(_cfg, form)

    if re.match(r'^\w+$', params.database) is None or re.match(r'^\w+$', params.table) is None:
        return response_status(func, '400 Bad Request')

    db = Mysql()
    try:
        html = html_head(params) + '''<h1>show index from `{}`</h1>
        <div class="table-overflow-auto">
            <table>
                <tr>
                    <th>Table</th>
                    <th>Non_unique</th>
                    <th>Key_name</th>
                    <th>Seq_in_index</th>
                    <th>Column_name</th>
                    <th>Collation</th>
                    <th>Cardinality</th>
                    <th>Sub_part</th>
                    <th>Packed</th>
                    <th>Null</th>
                    <th>Index_type</th>
                    <th>Comment</th>
                    <th>Index_comment</th>
                </tr>'''.format(params.table)

        conn_settings.database = params.database
        db.connect(conn_settings)
        db.cursor.execute('SHOW INDEX FROM `{}`.`{}`'.format(params.database, params.table))
        create_table = db.cursor.fetchall()

        for ct in create_table:
            html += '''<tr>
                <td>{}</td>
                <td>{}</td>
                <td>{}</td>
                <td>{}</td>
                <td>{}</td>
                <td>{}</td>
                <td>{}</td>
                <td>{}</td>
                <td>{}</td>
                <td>{}</td>
                <td>{}</td>
                <td>{}</td>
                <td>{}</td>
            </tr>'''.format(ct['Table'], ct['Non_unique'], ct['Key_name'], ct['Seq_in_index'], ct['Column_name'],
                            ct['Collation'], ct['Cardinality'], ct['Sub_part'], ct['Packed'], ct['Null'],
                            ct['Index_type'], ct['Comment'], ct['Index_comment'])

        html += '</table></div>'.format(params.database) + html_tail()
        return response_html(func, html)
    except pymysql.Error as error:
        return response_status(func, '500 Internal Server Error', message=str(error))
    finally:
        db.close()


@mysql_conn_required
def mysql_select_rows(func, _env, _token, _cfg):
    conn_settings = MysqlConnSettings(_token)
    form = request_form(_env)
    params = SqlParams(_cfg, form)

    if re.match(r'^\w+$', params.database.replace(' ', '')) is None or \
            re.match(r'^\w+$', params.table.replace(' ', '')) is None:
        return response_status(func, '400 Bad Request')

    if params.field1 != '' and re.match(r'^\w+$', params.field1.replace(' ', '')) is None:
        return response_status(func, '400 Bad Request')

    if params.field2 != '' and re.match(r'^\w+$', params.field2.replace(' ', '')) is None:
        return response_status(func, '400 Bad Request')

    if params.order_by != '' and re.match(r'^\w+$', params.order_by.replace(' ', '')) is None:
        return response_status(func, '400 Bad Request')

    if params.limit < 1:
        return response_status(func, '400 Bad Request', message='limit is invalid')

    if params.limit > _cfg.max_limit:
        params.limit = _cfg.max_limit

    if params.offset < 0:
        return response_status(func, '400 Bad Request', message='offset is invalid')

    db = Mysql()
    try:
        conn_settings.database = params.database
        db.connect(conn_settings)
        descriptions = db.describe(params)

        column_names = []
        pk_column = ''
        for desc in descriptions:
            column_names.append(desc['Field'])
            if desc['Key'] == 'PRI' and pk_column == '':
                pk_column = desc['Field']

        if pk_column == '':
            pk_column = column_names[0]
        tr_columns = '<tr><th>delete</th><th>update</th><th>' + '</th><th>'.join(column_names) + '</th></tr>'

        if params.order_by == '':
            params.order_by = pk_column

        sql_parts = ['SELECT * FROM `{}`.`{}`'.format(params.database, params.table)]
        values = []
        if params.field1 != '' and params.keyword1 != '':
            sql_parts.append('WHERE `{}`'.format(params.field1))
            if params.like1 == 1:
                sql_parts.append('LIKE %s')
                values.append('%{}%'.format(params.keyword1))
            else:
                sql_parts.append('= %s')
                values.append(params.keyword1)

        if params.field2 != '' and params.keyword2 != '':
            if params.is_or == 1:
                sql_parts.append('OR `{}`'.format(params.field2))
            else:
                sql_parts.append('AND `{}`'.format(params.field2))

            if params.like2 == 1:
                sql_parts.append('LIKE %s')
                values.append('%{}%'.format(params.keyword2))
            else:
                sql_parts.append('= %s')
                values.append(params.keyword2)

        if params.order_by != '':
            sql_parts.append('ORDER BY `{}` {}'.format(params.order_by, 'ASC' if params.is_asc == 1 else 'DESC'))

        sql_parts.append('LIMIT %s OFFSET %s')
        values.extend([params.limit, params.offset])

        sql = ' '.join(sql_parts)
        db.cursor.execute(sql, values)
        rows = db.cursor.fetchall()
        len_rows = len(rows)

        sql_split = sql.split('%s')
        len_sql_split = len(sql_split)
        sql_disp = ''
        for i in range(len_sql_split):
            sql_disp += sql_split[i]
            if i < (len_sql_split - 1):
                sql_disp += str(values[i])

        no_rows_found = ''
        if len_rows == 0:
            no_rows_found = '<p class="red">No Rows Found</p>'

        next_page = True
        if len_rows < params.limit:
            next_page = False

        pagination = ''
        current_offset = params.offset
        if params.offset > 0:
            params.offset = current_offset - params.limit
            pagination += '<a href="/mysql/select_rows?{}">prev</a> | '.format(params.querystring())
        else:
            pagination += 'prev | '

        if next_page:
            params.offset = current_offset + params.limit
            pagination += '<a href="/mysql/select_rows?{}">next</a>'.format(params.querystring())
        else:
            pagination += 'next'
        params.offset = current_offset

        insert_link = '<a href="/mysql/insert_row_form?{}">insert</a>'.format(params.querystring())

        select_field = '<select name="{}"><option></option><option>' + \
                       '</option><option>'.join(column_names) + \
                       '</option></select>'
        select_field1 = select_field.format('field1')
        select_field2 = select_field.format('field2')
        select_order_by = select_field.format('order_by')

        html = html_head(params) + '''<h1>select * from `{}`</h1>
        <form id="search" action="/mysql/select_rows">
            <input name="database" type="hidden" value="{}">
            <input name="table" type="hidden" value="{}">
        <p class="form1">
            <span>where</span>

            {}
            <script>document.querySelector('#search').field1.value = '{}'</script>

            <select name="like1">
                <option value="0">=</option>
                <option value="1">like</option>
            </select>
            <script>document.querySelector('#search').like1.value = '{}'</script>

            <input name="keyword1" placeholder="keyword1" type="text" size="10" value="{}">
        <br>
            <select name="is_or">
                <option value="0">and</option>
                <option value="1">or</option>
            </select>
            <script>document.querySelector('#search').is_or.value = '{}'</script>

            {}
            <script>document.querySelector('#search').field2.value = '{}'</script>

            <select name="like2">
                <option value="0">=</option>
                <option value="1">like</option>
            </select>
            <script>document.querySelector('#search').like2.value = '{}'</script>

            <input name="keyword2" placeholder="keyword2" type="text" size="10" value="{}">
        <br>
            <span>order by</span>
            {}
            <script>document.querySelector('#search').order_by.value = '{}'</script>

            <select name="is_asc">
                <option value="0">desc</option>
                <option value="1">asc</option>
            </select>
            <script>document.querySelector('#search').is_asc.value = '{}'</script>

            <span>limit</span>
            <select name="limit">
                <option>10</option>
                <option>20</option>
                <option>30</option>
                <option>40</option>
                <option>50</option>
            </select>
            <script>document.querySelector('#search').limit.value = '{}'</script>

            <span>offset</span>
            <input name="offset" placeholder="offset" type="text" size="2" value="{}">
            <input name="submit" type="submit" value="submit">
            | <a href="/mysql/select_rows?database={}&table={}">clear</a>
        </p>
        </form>

        <p class="dark-gray">{}</p>
        <hr class="light-gray">
        <p>{} | {}</p>

        <div class="table-overflow-auto">
            <table>'''.format(params.table, params.database, params.table, select_field1, params.field1,
                              params.like1, params.keyword1, params.is_or, select_field2, params.field2,
                              params.like2, params.keyword2, select_order_by, params.order_by, params.is_asc,
                              params.limit, params.offset, params.database, params.table, sql_disp,
                              insert_link, pagination) + tr_columns

        for row in rows:
            html += '''<tr><td><button
onClick="if (confirm('Are you sure?')) location.href = '/mysql/delete_row?database={}&table={}&pk={}'""
>delete</button></td><td><a href="/mysql/update_row_form?database={}&table={}&pk={}">update</a></td>'''.format(
                params.database, params.table, row[pk_column], params.database, params.table, row[pk_column])

            for column_name in column_names:
                html += '<td>{}</td>'.format(row[column_name])
            html += '</tr>'

        html += '</table>{}</div><p>{} | {}</p>'.format(no_rows_found, insert_link, pagination) + \
                html_tail()

        return response_html(func, html)
    except pymysql.Error as error:
        return response_status(func, '500 Internal Server Error', message=str(error))
    finally:
        db.close()


@mysql_conn_required
def mysql_insert_row_form(func, _env, _token, _cfg):
    conn_settings = MysqlConnSettings(_token)
    form = request_form(_env)
    params = SqlParams(_cfg, form)

    if re.match(r'^\w+$', params.database.replace(' ', '')) is None or \
            re.match(r'^\w+$', params.table.replace(' ', '')) is None:
        return response_status(func, '400 Bad Request')

    db = Mysql()
    try:
        html = html_head(params) + '''<h1>insert into table `{}`</h1>
        <form method="post" action="/mysql/insert_row">
            <input name="database" type="hidden" value="{}">
            <input name="table" type="hidden" value="{}">
        <div class="table-overflow-auto">
            <table>'''.format(params.table, params.database, params.table)

        conn_settings.database = params.database
        db.connect(conn_settings)
        descriptions = db.describe(params)

        for desc in descriptions:
            var_type, def_value = var_type_and_def_value(desc['Type'])

            if desc['Default'] is None:
                desc['Default'] = def_value

            if desc['Key'] == 'PRI':
                if desc['Extra'].upper() == 'AUTO_INCREMENT':
                    html += '<tr><th>{}</th><td>{}</td><td>AUTO_INCREMENT</td></tr>'.format(desc['Field'], desc['Type'])
                else:
                    html += '<tr><th>{}</th><td>{}</td><td><input name="{}" type="text"></td></tr>'.format(
                        desc['Field'], desc['Type'], desc['Field'])
            elif var_type == 'text':
                html += '<tr><th>{}</th><td>{}</td><td><textarea name="{}"></textarea></td></tr>'.format(
                    desc['Field'], desc['Type'], desc['Field'])
            elif var_type == 'timestamp' or var_type == 'binary':
                pass
            else:
                html += '<tr><th>{}</th><td>{}</td><td><input name="{}" type="text" value="{}"></td></tr>'.format(
                    desc['Field'], desc['Type'], desc['Field'], desc['Default'])
        html += '</table></div>'.format(params.database) + '<p>'
        html += '</table></div><p><input name="submit" type="submit" value="submit"></p></form>' + html_tail()

        return response_html(func, html)
    except pymysql.Error as error:
        return response_status(func, '500 Internal Server Error', message=str(error))
    finally:
        db.close()


@mysql_conn_required
def mysql_insert_row(func, _env, _token, _cfg):
    conn_settings = MysqlConnSettings(_token)
    form = request_form(_env)
    params = SqlParams(_cfg, form)

    if re.match(r'^\w+$', params.database) is None or re.match(r'^\w+$', params.table) is None:
        return response_status(func, '400 Bad Request')

    db = Mysql()
    try:
        conn_settings.database = params.database
        db.connect(conn_settings)
        descriptions = db.describe(params)

        pk_column = ''
        values = []
        column_names = []
        place_holders = []
        for desc in descriptions:
            var_type, def_value = var_type_and_def_value(desc['Type'])

            if desc['Key'] == 'PRI':
                if pk_column == '':
                    pk_column = desc['Field']
                if var_type == 'integer' and desc['Extra'].upper() == 'AUTO_INCREMENT':
                    continue

            if var_type == 'integer':
                value = form.getvalue(desc['Field'], str(def_value))
                if not value.isdigit():
                    return response_status(func, '400 Bad Request',
                                           message='{} is not an integer'.format(desc['Field']))
                column_names.append('`{}`'.format(desc['Field']))
                place_holders.append('%s')
                values.append(int(value))
            elif var_type == 'float':
                value = form.getvalue(desc['Field'], str(def_value))
                if not is_float(value):
                    return response_status(func, '400 Bad Request',
                                           message='{} is not numeric'.format(desc['Field']))
                column_names.append('`{}`'.format(desc['Field']))
                place_holders.append('%s')
                values.append(float(value))
            elif var_type == 'decimal':
                value = form.getvalue(desc['Field'], def_value)
                if not is_decimal(value):
                    return response_status(func, '400 Bad Request',
                                           message='{} is not numeric'.format(desc['Field']))
                column_names.append('`{}`'.format(desc['Field']))
                place_holders.append('%s')
                values.append(Decimal(value))
            elif var_type == 'timestamp' or var_type == 'binary':
                pass
            else:
                if desc['Default'] == 'current_timestamp()':
                    column_names.append('`{}`'.format(desc['Field']))
                    place_holders.append(desc['Default'])
                else:
                    column_names.append('`{}`'.format(desc['Field']))
                    place_holders.append('%s')
                    values.append(form.getvalue(desc['Field'], ''))

        if pk_column == '':
            pk_column = descriptions[0]['Field']

        sql_parts = ['INSERT INTO `{}`.`{}`('.format(params.database, params.table), ', '.join(column_names),
                     ') VALUES (', ', '.join(place_holders), ')']
        sql = ' '.join(sql_parts)
        # print(sql)
        db.cursor.execute(sql, values)

        last_row_id = db.cursor.lastrowid
        if last_row_id == 0:
            last_row_id = form.getvalue(pk_column)

        html = html_head(params) + '<h1>OK: insert into `{}` ({}: {})</h1>'.format(
            params.table, pk_column, last_row_id) + html_tail()

        return response_html(func, html)
    except pymysql.Error as error:
        return response_status(func, '500 Internal Server Error', message=str(error))
    finally:
        db.close()


@mysql_conn_required
def mysql_delete_row(func, _env, _token, _cfg):
    conn_settings = MysqlConnSettings(_token)
    form = request_form(_env)
    params = SqlParams(_cfg, form)
    pk = form.getvalue('pk', '')

    if re.match(r'^\w+$', params.database.replace(' ', '')) is None or \
            re.match(r'^\w+$', params.table.replace(' ', '')) is None:
        return response_status(func, '400 Bad Request')

    db = Mysql()
    try:
        conn_settings.database = params.database
        db.connect(conn_settings)
        descriptions = db.describe(params)

        pk_column = ''
        for desc in descriptions:
            if desc['Key'] == 'PRI':
                pk_column = desc['Field']
                break

        if pk_column == '':
            pk_column = descriptions[0]['Field']

        sql = 'SELECT COUNT(`{}`) AS _count FROM `{}`.`{}` WHERE `{}` = %s'.format(pk_column, params.database,
                                                                                   params.table, pk_column)
        db.cursor.execute(sql, (pk,))
        if db.cursor.fetchone()['_count'] != 1:
            return response_status(func, '500 Internal Server Error', message='row_count != 1')

        sql = 'DELETE FROM `{}`.`{}` WHERE `{}` = %s'.format(params.database, params.table, pk_column)
        db.cursor.execute(sql, (pk,))

        row_count = db.cursor.rowcount
        if row_count != 1:
            return response_status(func, '500 Internal Server Error', message='row_count != 1')

        html = html_head(params) + '<h1>OK: delete from `{}` where `{}` = {}</h1>'.format(
            params.table, pk_column, pk) + html_tail()
        return response_html(func, html)
    except pymysql.Error as error:
        return response_status(func, '500 Internal Server Error', message=str(error))
    finally:
        db.close()


@mysql_conn_required
def mysql_update_row_form(func, _env, _token, _cfg):
    conn_settings = MysqlConnSettings(_token)
    form = request_form(_env)
    params = SqlParams(_cfg, form)
    pk = form.getvalue('pk', '')

    if re.match(r'^\w+$', params.database.replace(' ', '')) is None or \
            re.match(r'^\w+$', params.table.replace(' ', '')) is None:
        return response_status(func, '400 Bad Request')

    db = Mysql()
    try:
        conn_settings.database = params.database
        db.connect(conn_settings)
        descriptions = db.describe(params)

        pk_column = ''
        for desc in descriptions:
            if desc['Key'] == 'PRI':
                pk_column = desc['Field']
                break

        if pk_column == '':
            pk_column = descriptions[0]['Field']

        sql = 'SELECT * FROM `{}`.`{}` WHERE `{}` = %s'.format(params.database, params.table, pk_column)
        db.cursor.execute(sql, (pk,))
        rows = db.cursor.fetchall()

        if len(rows) == 0:
            return response_status(func, '404 Not Found')

        html = html_head(params) + '''<h1>update `{}` where `{}` = {}</h1>
        <form method="post" action="/mysql/update_row">
            <input name="database" type="hidden" value="{}">
            <input name="table" type="hidden" value="{}">
            <input name="pk" type="hidden" value="{}">
        <div class="table-overflow-auto">
            <table>'''.format(params.table, pk_column, pk, params.database, params.table, pk)

        for desc in descriptions:
            var_type, def_value = var_type_and_def_value(desc['Type'])

            if desc['Key'] == 'PRI':
                html += '<tr><th>{}</th><td>{}</td><td>{}</td></tr>'.format(desc['Field'], desc['Type'], pk)
            elif var_type == 'text':
                html += '<tr><th>{}</th><td>{}</td><td><textarea name="{}">{}</textarea></td></tr>'.format(
                    desc['Field'], desc['Type'], desc['Field'], rows[0][desc['Field']])
            elif var_type == 'binary' or var_type == 'binary':
                pass
            else:
                html += '<tr><th>{}</th><td>{}</td><td><input name="{}" type="text" value="{}"></td></tr>'.format(
                    desc['Field'], desc['Type'], desc['Field'], rows[0][desc['Field']])
        html += '</table></div>'.format(params.database) + '<p>'
        html += '</table></div><p><input name="submit" type="submit" value="submit"></p></form>' + html_tail()

        return response_html(func, html)
    except pymysql.Error as error:
        return response_status(func, '500 Internal Server Error', message=str(error))
    finally:
        db.close()


@mysql_conn_required
def mysql_update_row(func, _env, _token, _cfg):
    conn_settings = MysqlConnSettings(_token)
    form = request_form(_env)
    params = SqlParams(_cfg, form)
    pk = form.getvalue('pk', '')

    if re.match(r'^\w+$', params.database.replace(' ', '')) is None or \
            re.match(r'^\w+$', params.table.replace(' ', '')) is None:
        return response_status(func, '400 Bad Request')

    db = Mysql()
    try:
        conn_settings.database = params.database
        db.connect(conn_settings)
        descriptions = db.describe(params)

        pk_column = ''
        column_equal_place_holders = []
        values = []
        for desc in descriptions:
            var_type, def_value = var_type_and_def_value(desc['Type'])

            if desc['Key'] == 'PRI':
                if pk_column == '':
                    pk_column = desc['Field']
                continue

            if var_type == 'integer':
                value = form.getvalue(desc['Field'], str(def_value))
                if not value.isdigit():
                    return response_status(func, '400 Bad Request',
                                           message='{} is not an integer'.format(desc['Field']))
                column_equal_place_holders.append('`{}` = %s'.format(desc['Field']))
                values.append(int(value))
            elif var_type == 'float':
                value = form.getvalue(desc['Field'], str(def_value))
                if not is_float(value):
                    return response_status(func, '400 Bad Request',
                                           message='{} is not numeric'.format(desc['Field']))
                column_equal_place_holders.append('`{}` = %s'.format(desc['Field']))
                values.append(float(value))
            elif var_type == 'decimal':
                value = form.getvalue(desc['Field'], def_value)
                if not is_decimal(value):
                    return response_status(func, '400 Bad Request',
                                           message='{} is not numeric'.format(desc['Field']))
                column_equal_place_holders.append('`{}` = %s'.format(desc['Field']))
                values.append(Decimal(value))
            elif var_type == 'timestamp' or var_type == 'binary':
                pass
            else:
                column_equal_place_holders.append('`{}` = %s'.format(desc['Field']))
                values.append(form.getvalue(desc['Field'], ''))

        if pk_column == '':
            pk_column = descriptions[0]['Field']

        sql = 'SELECT COUNT(`{}`) AS _count FROM `{}`.`{}` WHERE `{}` = %s'.format(pk_column, params.database,
                                                                                   params.table, pk_column)
        db.cursor.execute(sql, (pk,))
        if db.cursor.fetchone()['_count'] != 1:
            return response_status(func, '500 Internal Server Error', message='row_count != 1')

        sql_parts = ['UPDATE `{}`.`{}` SET'.format(params.database, params.table),
                     ', '.join(column_equal_place_holders), 'WHERE `{}` = %s'.format(pk_column)]
        values.append(pk)

        sql = ' '.join(sql_parts)
        # print(sql)
        db.cursor.execute(sql, values)

        row_count = db.cursor.rowcount
        if row_count != 1:
            return response_status(func, '500 Internal Server Error', message='row_count != 1')

        html = html_head(params) + '<h1>OK: update `{}` where `{}` = {}</h1>'.format(
            params.table, pk_column, pk) + html_tail()

        return response_html(func, html)
    except pymysql.Error as error:
        return response_status(func, '500 Internal Server Error', message=str(error))
    finally:
        db.close()


# config
class Config:
    def __init__(self):
        self.secret_key = '__this_is_your_secret_key__'
        self.debug = True

        self.httpd_host = '0.0.0.0'
        self.httpd_port = 9872

        self.token_access_lifetime_minutes = 14 * 24 * 60  # 14 days * 24 hours * 60 minutes
        self.token_refresh_lifetime_minutes = 28 * 24 * 60  # 28 days * 24 hours * 60 minutes

        self.max_limit = 50
        self.datetime_format = '%Y-%m-%d %H:%M:%S'

        _api = MysqlConnSettings()
        _api.host = '127.0.0.1'
        _api.user = 'root'
        _api.password = 'root'
        _api.database = 'mysql'
        _api.port = 3306

        self.mysql_conn_settings = {
            'api': _api,
        }


# application
def app(env, func):
    cfg = Config()

    handlers = {
        '/': index,

        '/mysql/connect_form': mysql_connect_form,
        '/mysql/connect': mysql_connect,
        '/mysql/disconnect': mysql_disconnect,

        '/mysql/show_databases': mysql_show_databases,
        '/mysql/create_database': mysql_create_database,
        '/mysql/drop_database': mysql_drop_database,
        '/mysql/dump_database': mysql_dump_database,

        '/mysql/show_tables': mysql_show_tables,
        '/mysql/create_table_form': mysql_create_table_form,
        '/mysql/create_table': mysql_create_table,
        '/mysql/drop_table': mysql_drop_table,
        '/mysql/alter_table_form': mysql_alter_table_form,
        '/mysql/alter_table': mysql_alter_table,
        '/mysql/rename_table_form': mysql_rename_table_form,
        '/mysql/rename_table': mysql_rename_table,
        '/mysql/describe_table': mysql_describe_table,
        '/mysql/show_create_table': mysql_show_create_table,
        '/mysql/show_index': mysql_show_index,

        '/mysql/select_rows': mysql_select_rows,
        '/mysql/insert_row_form': mysql_insert_row_form,
        '/mysql/insert_row': mysql_insert_row,
        '/mysql/delete_row': mysql_delete_row,
        '/mysql/update_row_form': mysql_update_row_form,
        '/mysql/update_row': mysql_update_row,
    }

    request_method = env.get('REQUEST_METHOD', 'GET')
    path_info = env.get('PATH_INFO', '/not_found')

    handler = handlers.get(path_info, None)
    if handler is not None:
        cookie = request_cookie(env)
        cookie_token = cookie.get('token', '')
        auth_token = request_auth_token(env)

        token = Token(cfg)
        if cookie_token != '' and not token.load(cookie_token):
            return response_redirect(func, '/', [('Set-Cookie', response_set_cookie('token', ''))])
        elif auth_token != '' and not token.load(auth_token):
            return response_status(func, '401 Unauthorized')

        return handler(func, env, token, cfg)

    if not path_info.startswith('/web/'):
        return response_status(func, '404 Not Found')

    if '..' in path_info:
        return response_status(func, '400 Bad Request', message='there is ".." in path_info')

    file_path = '.{}'.format(path_info)
    if not os.path.exists(file_path):
        return response_status(func, '404 Not Found', message='file does not exists')

    if not os.path.isfile(file_path) or not os.access(file_path, os.R_OK):
        return response_status(func, '403 Forbidden', message='not a file or not readable')

    if request_method not in ['GET', 'HEAD']:
        return response_status(func, '405 Method Now Allowed')

    content_type, _ = mimetypes.guess_type(file_path)
    if content_type is None:
        content_type = 'application/octet-stream'

    func('200 OK', [
        ('Content-Type', content_type),
        ('Content-Length', str(os.stat(file_path).st_size)),
    ])

    if request_method == 'HEAD':
        return []

    f = None
    f_read = ['500 Internal Server Error'.encode('utf-8')]
    try:
        f = open(file_path, 'rb')
        f_read = f.read()
    finally:
        if f is not None:
            f.close()
        return [f_read]


# main
class ServerClass(ThreadingMixIn, WSGIServer):
    pass


def main():
    cfg = Config()
    httpd = make_server(cfg.httpd_host, cfg.httpd_port, app, server_class=ServerClass)

    try:
        print('serving on port {}:{}..'.format(cfg.httpd_host, cfg.httpd_port))
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()

        # wait for self._threads.join()
        time.sleep(1)


if __name__ == '__main__':
    main()
