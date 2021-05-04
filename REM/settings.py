"""
REM configuration settings.
"""

import concurrent.futures
import datetime
import dateutil
import gettext
import hashlib
import locale
import os
import pandas as pd
from pandas.io import sql
import pyodbc
import PySimpleGUI as sg
import sys
import textwrap
import time
import yaml

import REM.constants as mod_const




class SQLStatementError(Exception):
    """A simple exception that is raised when an SQL statement is formatted incorrectly.
    """

    def __init__(self, *args, **kwargs):
        Exception.__init__(self, *args)


class DBConnectionError(Exception):
    """A simple exception that is raised when there is a problem connecting to the database.
    """

    def __init__(self, *args, **kwargs):
        Exception.__init__(self, *args)


class UserSettings:
    """
    Class to store and manage user-specific configuration settings.

    Arguments:

        cnfg: Parsed YAML file

    Attributes:

        language (str): Display language. Default: EN.
    """

    def __init__(self, cnfg, dirname):
        self.dirname = dirname
        self.icons_dir = os.path.join(self.dirname, 'docs', 'images', 'icons')

        # Supported locales
#        self._locales = ['en_US', 'en_UK', 'th_TH']
        self._locales = {'English': 'en', 'Thai': 'th'}

        # User parameters
        try:
            self.username = cnfg['user']['username']
        except KeyError:
            self.username = 'username'

        # Localization parameters
        try:
            self.language = cnfg['localization']['language']
        except KeyError:
            self.language = 'en'
        try:
            cnfg_locale = cnfg['localization']['locale']
        except KeyError:
            cnfg_locale = 'English'
#        self.locale = cnfg_locale if cnfg_locale in self._locales else 'en_US'
        self.locale = cnfg_locale if cnfg_locale in self._locales else 'English'
        try:
            print('Info: settings locale to {}'.format(self.locale))
            locale.setlocale(locale.LC_ALL, self.locale)
        except Exception as e:
            msg = 'unable to set locale - {ERR}'.format(ERR=e)
            print('Warning: {MSG}'.format(MSG=msg))
            popup_error(msg)
            sys.exit(1)
        else:
            print('Info: will offset dates by {} years'.format(self.get_date_offset()))

        locale_conv = locale.localeconv()
        self.decimal_sep = locale_conv['decimal_point']
        self.thousands_sep = locale_conv['thousands_sep']
        self.currency = locale_conv['int_curr_symbol']
        self.currency_symbol = locale_conv['currency_symbol']

        self.localedir = os.path.join(dirname, 'locale')
        self.domain = 'base'

        try:
            self.display_date_format = cnfg['localization']['display_date']
        except KeyError:
            self.display_date_format = 'YYYY-MM-DD'

        self.translation = self.change_locale()
        self.translation.install('base')  # bind gettext to _() in __builtins__ namespace

        # Display parameters
        try:
            icon_name = cnfg['display']['icon']
        except KeyError:
            icon_file = os.path.join(dirname, 'docs', 'images', 'icon.ico')
        else:
            if not icon_name:
                icon_file = os.path.join(dirname, 'docs', 'images', 'icon.ico')
            else:
                icon_file = os.path.join(dirname, 'docs', 'images', icon_name)

        try:
            fh = open(icon_file, 'r', encoding='utf-8')
        except FileNotFoundError:
            self.icon = None
        else:
            self.icon = icon_file
            fh.close()

        try:
            logo_name = cnfg['display']['logo']
        except KeyError:
            logo_file = os.path.join(dirname, 'docs', 'images', 'logo.png')
        else:
            if not logo_name:
                logo_file = os.path.join(dirname, 'docs', 'images', 'logo.png')
            else:
                logo_file = os.path.join(dirname, 'docs', 'images', logo_name)

        try:
            fh = open(logo_file, 'r', encoding='utf-8')
        except FileNotFoundError:
            self.logo = None
        else:
            self.logo = logo_file
            fh.close()

        try:
            logo_icon = cnfg['display']['logo_icon']
        except KeyError:
            logo_file = os.path.join(dirname, 'docs', 'images', 'icons', 'logo_icon.png')
        else:
            if not logo_icon:
                logo_file = os.path.join(dirname, 'docs', 'images', 'icons', 'logo_icon.png')
            else:
                logo_file = os.path.join(dirname, 'docs', 'images', logo_icon)

        try:
            fh = open(logo_file, 'r', encoding='utf-8')
        except FileNotFoundError:
            self.logo_icon = None
        else:
            self.logo_icon = logo_file
            fh.close()

        try:
            report_template = cnfg['display']['report_template']
        except KeyError:
            self.report_template = os.path.join(dirname, 'templates', 'report.html')
        else:
            if not report_template:
                self.report_template = os.path.join(dirname, 'templates', 'report.html')
            else:
                self.report_template = report_template

        try:
            report_style = cnfg['display']['report_stylesheet']
        except KeyError:
            self.report_css = os.path.join(dirname, 'static', 'css', 'report.css')
        else:
            if not report_style:
                self.report_css = os.path.join(dirname, 'static', 'css', 'report.css')
            else:
                self.report_css = report_style

        # Dependencies
        try:
            wkhtmltopdf = cnfg['dependencies']['wkhtmltopdf']
        except KeyError:
            self.wkhtmltopdf = os.path.join(dirname, 'data', 'wkhtmltopdf', 'bin', 'wkhtmltopdf.exe')
        else:
            if not wkhtmltopdf:
                self.wkhtmltopdf = os.path.join(dirname, 'data', 'wkhtmltopdf', 'bin', 'wkhtmltopdf.exe')
            else:
                self.wkhtmltopdf = wkhtmltopdf

        # Database parameters
        try:
            self.driver = cnfg['database']['odbc_driver']
        except KeyError:
            self.driver = 'SQL Server'
        try:
            self.server = cnfg['database']['odbc_server']
        except KeyError:
            self.server = 'localhost'
        try:
            self.port = cnfg['database']['odbc_port']
        except KeyError:
            self.port = '1433'
        try:
            self.dbname = cnfg['database']['default_database']
        except KeyError:
            self.dbname = 'REM'
        try:
            self.prog_db = cnfg['database']['odbc_database']
        except KeyError:
            self.prog_db = 'REM'
        try:
            self.date_format = cnfg['database']['date_format']
        except KeyError:
            self.date_format = 'YYYY-MM-DD HH:MI:SS'
        try:
            self.alt_dbs = cnfg['database']['alternative_databases']
        except KeyError:
            self.alt_dbs = []

    def translate(self):
        """
        Translate text using language defined in settings.
        """
        pass

    def edit_attribute(self, attr, value):
        """
        Modify a settings attribute.
        """
        if attr == 'language':
            self.language = value
        elif attr == 'locale':
            self.locale = value
        elif attr == 'template':
            self.report_template = value
        elif attr == 'css':
            self.report_css = value
        elif attr == 'odbc_port':
            self.port = value
        elif attr == 'odbc_server':
            self.server = value
        elif attr == 'odbc_driver':
            self.driver = value
        elif attr == 'dbname':
            self.dbname = value

    def layout(self):
        """
        Generate GUI layout for the settings window.
        """
        width = 800

        # Window and element size parameters
        main_font = mod_const.MAIN_FONT

        pad_el = mod_const.ELEM_PAD
        pad_v = mod_const.VERT_PAD
        pad_frame = mod_const.FRAME_PAD
        in_size = 18
        spacer = (12, 1)
        dd_size = 8

        bg_col = mod_const.ACTION_COL
        in_col = mod_const.INPUT_COL

        bwidth = 0.5
        select_col = mod_const.SELECT_TEXT_COL

        layout = [[sg.Frame('Localization', [
            [sg.Canvas(size=(width, 0), pad=(0, pad_v), visible=True, background_color=bg_col)],
            [sg.Text('Language:', size=(15, 1), pad=((pad_frame, pad_el), pad_el), font=main_font,
                     background_color=bg_col),
             sg.Combo(list(self._locales.values()), key='-LANGUAGE-', size=(dd_size, 1), pad=(pad_el, pad_el),
                      default_value=self.language, auto_size_text=False, background_color=in_col)],
            [sg.Text('Locale:', size=(15, 1), pad=((pad_frame, pad_el), pad_el), font=main_font,
                     background_color=bg_col),
             sg.Combo(list(self._locales), key='-LOCALE-', size=(dd_size, 1), pad=(pad_el, pad_el),
                      default_value=self.locale, auto_size_text=False, background_color=in_col)],
            [sg.Canvas(size=(800, 0), pad=(0, pad_v), visible=True, background_color=bg_col)]],
                            pad=(pad_frame, pad_frame), border_width=bwidth, background_color=bg_col,
                            title_color=select_col, relief='groove')],
                  [sg.Frame('Display', [
                      [sg.Canvas(size=(width, 0), pad=(0, pad_v), visible=True, background_color=bg_col)],
                      [sg.Text('Report template:', size=(15, 1), pad=((pad_frame, pad_el), pad_el),
                               font=main_font, background_color=bg_col),
                       sg.Input(self.report_template, key='-TEMPLATE-', size=(60, 1),
                                pad=(pad_el, pad_el), font=main_font, background_color=in_col),
                       sg.FileBrowse('Browse...', pad=((pad_el, pad_frame), pad_el))],
                      [sg.Text('Report stylesheet:', size=(15, 1), pad=((pad_frame, pad_el), pad_el),
                               font=main_font, background_color=bg_col),
                       sg.Input(self.report_css, key='-CSS-', size=(60, 1), pad=(pad_el, pad_el),
                                font=main_font, background_color=in_col),
                       sg.FileBrowse('Browse...', pad=((pad_el, pad_frame), pad_el))],
                      [sg.Canvas(size=(800, 0), pad=(0, pad_v), visible=True, background_color=bg_col)]],
                            pad=(pad_frame, pad_frame), border_width=bwidth, background_color=bg_col,
                            title_color=select_col, relief='groove')],
                  [sg.Frame('Database', [
                      [sg.Canvas(size=(width, 0), pad=(0, pad_v), visible=True, background_color=bg_col)],
                      [sg.Text('ODBC odbc_port:', size=(15, 1), pad=((pad_frame, pad_el), pad_el),
                               font=main_font, background_color=bg_col),
                       sg.Input(self.port, key='-PORT-', size=(in_size, 1), pad=((pad_el, pad_frame), pad_el),
                                font=main_font, background_color=in_col),
                       sg.Text('', size=spacer, background_color=bg_col),
                       sg.Text('ODBC odbc_server:', size=(15, 1), pad=((pad_frame, pad_el), pad_el), font=main_font,
                               background_color=bg_col),
                       sg.Input(self.server, key='-SERVER-', size=(in_size, 1), pad=((pad_el, pad_frame), pad_el),
                                font=main_font, background_color=in_col)],
                      [sg.Text('ODBC odbc_driver:', size=(15, 1), pad=((pad_frame, pad_el), pad_el),
                               font=main_font, background_color=bg_col),
                       sg.Input(self.driver, key='-DRIVER-', size=(in_size, 1), pad=((pad_el, pad_frame), pad_el),
                                font=main_font, background_color=in_col),
                       sg.Text('', size=spacer, background_color=bg_col, pad=(0, pad_el)),
                       sg.Text('Database:', size=(15, 1), pad=((pad_frame, pad_el), pad_el), font=main_font,
                               background_color=bg_col),
                       sg.Combo(self.alt_dbs, default_value=self.dbname, key='-DATABASE-', size=(in_size - 1, 1),
                                pad=((pad_el, pad_frame), pad_el), font=main_font, background_color=in_col)],
                      [sg.Canvas(size=(800, 0), pad=(0, pad_v), visible=True, background_color=bg_col)]],
                            pad=(pad_frame, pad_frame), border_width=bwidth, background_color=bg_col,
                            title_color=select_col, relief='groove')]]

        return layout

    def change_locale(self):
        """
        Translate application text based on supplied locale.
        """
        language = self.language
        localdir = self.localedir
        domain = self.domain

#        if language not in [i.split('_')[0] for i in self._locales]:
#            raise NameError
        if language not in self._locales.values():
            raise NameError

        try:
            trans = gettext.translation(domain, localedir=localdir, languages=[language])
        except Exception as e:
            print('Unable to find translations for locale {LANG} - {ERR}'.format(LANG=language, ERR=e))
            trans = gettext

        return trans

    def format_display_date(self, dt):
        """
        Format a datetime object for displaying based on configured date format.

        Arguments:
            dt (datetime): datetime instance.
        """
        date = self.apply_date_offset(dt)
        date_str = self.format_date_str(date_str=self.display_date_format)

        date_formatted = date.strftime(date_str)

        return date_formatted

    def format_date_str(self, date_str: str = None):
        """
        Format a date string for use as input to datetime method.

        Arguments:
            date_str (str): date string.
        """
        separators = set(':/- ')
        date_fmts = {'YYYY': '%Y', 'YY': '%y',
                     'MMMM': '%B', 'MMM': '%b', 'MM': '%m', 'M': '%-m',
                     'DD': '%d', 'D': '%-d',
                     'HH': '%H', 'MI': '%M', 'SS': '%S'}

        date_str = date_str if date_str else self.date_format

        strfmt = []

        last_char = date_str[0]
        buff = [last_char]
        for char in date_str[1:]:
            if char not in separators:
                if last_char != char:
                    # Check if char is first in a potential series
                    if last_char in separators:
                        buff.append(char)
                        last_char = char
                        continue

                    # Check if component is minute
                    if ''.join(buff + [char]) == 'MI':
                        strfmt.append(date_fmts['MI'])
                        buff = []
                        last_char = char
                        continue

                    # Add characters in buffer to format string and reset buffer
                    component = ''.join(buff)
                    strfmt.append(date_fmts[component])
                    buff = [char]
                else:
                    buff.append(char)
            else:
                component = ''.join(buff)
                try:
                    strfmt.append(date_fmts[component])
                except KeyError:
                    if component:
                        raise TypeError('unknown component {} provided to date string {}.'.format(component, date_str))

                strfmt.append(char)
                buff = []

            last_char = char

        try:  # format final component remaining in buffer
            strfmt.append(date_fmts[''.join(buff)])
        except KeyError:
            raise TypeError('unsupported characters {} found in date string {}'.format(''.join(buff), date_str))

        return ''.join(strfmt)

    def get_date_offset(self):
        """
        Find date offset for calendar systems other than the gregorian calendar
        """
        current_locale = self.locale

        if current_locale == 'Thai':
            offset = 543
        else:
            offset = 0

        return offset

    def apply_date_offset(self, dt):
        """
        Apply date offset to a datetime object.

        Arguments:
            dt (datetime.datetime): datetime instance.
        """
        relativedelta = dateutil.relativedelta.relativedelta
        strptime = datetime.datetime.strptime

        offset = self.get_date_offset()
        try:
            dt_mod = dt + relativedelta(years=+offset)
        except Exception as e:
            print('Info: encountered warning when attempting to apply offset to date - {ERR}'.format(ERR=e))
            dt_mod = strptime(dt.strftime('%Y-%m-%d %H:%M:%S'), '%Y-%m-%d %H:%M:%S') + relativedelta(years=+offset)

        return dt_mod

    def get_icon_path(self, icon):
        """
        Return the path of an icon, if exists.
        """
        icon = "{}.png".format(icon)
        icon_path = os.path.join(self.icons_dir, icon)
        if not os.path.exists(icon_path):
            print('Error: unable to open icon PNG {ICON}'.format(ICON=icon))
            icon_path = None

        return icon_path


class UserAccount:
    """
    Basic user account object.

    Attributes:
        uid (str): existing account username.

        pwd (str): hash value for associated account password.

        admin (bool): existing account is an admin account.

        logged_in (bool): user is logged in
    """

    def __init__(self, cnfg):
        # Database parameters
        try:
            self.driver = cnfg['database']['odbc_driver']
        except KeyError:
            self.driver = 'SQL Server'
        try:
            self.server = cnfg['database']['odbc_server']
        except KeyError:
            self.server = 'localhost'
        try:
            self.port = cnfg['database']['odbc_port']
        except KeyError:
            self.port = '1433'
        try:
            self.dbname = cnfg['database']['odbc_database']
        except KeyError:
            self.dbname = 'REM'
        try:
            self.date_format = format_date_str(cnfg['database']['date_format'])
        except KeyError:
            self.date_format = format_date_str('YYYY-MM-DD HH:MI:SS')

        # Dynamic variables
        self.uid = None
        self.pwd = None
        self.group = None
        self.logged_in = False
        self.admin = False

    def login(self, uid, pwd, timeout: int = 5):
        """
        Verify username and password exists in the database accounts table and obtain user permissions.

        Args:
            db (class): DataBase object.

            uid (str): existing account username.

            pwd (str): password associated with the existing account.
        """
        self.uid = uid
        self.pwd = pwd

        conn = self.db_connect(database=self.dbname, timeout=timeout)

        cursor = conn.cursor()

        # Privileges
        query_str = 'SELECT UserName, UserGroup FROM Users WHERE UserName = ?'
        cursor.execute(query_str, (uid,))

        ugroup = None
        results = cursor.fetchall()
        for row in results:
            username, user_group = row
            if username == uid:
                ugroup = user_group
                break

        cursor.close()
        conn.close()

        if not ugroup:
            self.uid = None
            self.pwd = None
            return False

        self.uid = uid
        self.pwd = pwd
        self.group = ugroup
        self.logged_in = True

        if ugroup == 'admin':
            self.admin = True

        return True

    def logout(self):
        """
        Reset class attributes.
        """
        self.uid = None
        self.pwd = None
        self.group = None
        self.logged_in = False
        self.admin = False

        return True

    def access_permissions(self):
        """
        Return escalated privileges for a given user group.
        """
        ugroup = self.group

        if ugroup == 'admin':
            return ['admin', 'user']
        else:
            return ['user']

    def db_connect(self, database=None, timeout=5):
        """
        Generate a pyODBC Connection object.
        """
        uid = self.uid
        pwd = self.pwd

        driver = settings.driver
        server = settings.server
        port = settings.port
        dbname = database if database else settings.dbname

        db_settings = {'Driver': driver,
                       'Server': server,
                       'Database': dbname,
                       'Port': port,
                       'UID': uid,
                       'PWD': pwd,
                       'Trusted_Connection': 'no'}

        conn_str = ';'.join(['{}={}'.format(k, db_settings[k]) for k in db_settings if db_settings[k]])
        print('Info: connecting to database {DB}'.format(DB=dbname))

        try:
            conn = pyodbc.connect(conn_str, timeout=timeout)
        except pyodbc.Error as e:
            print('DB Error: connection to {DB} failed due to {EX}'.format(DB=dbname, EX=e))
            print('Connection string is: {}'.format(conn_str))
            raise
        else:
            print('Info: successfully established a connection to {}'.format(dbname))

        return conn

    def database_tables(self, database, timeout: int = 5):
        """
        Get database schema information.
        """
        try:
            conn = self.db_connect(database=database, timeout=timeout)
        except DBConnectionError:
            print('DB Read Error: connection to database cannot be established')
            return None
        else:
            try:
                cursor = conn.cursor()
            except AttributeError:
                print('DB Read Error: connection to database cannot be established')
                return None
            else:
                try:
                    return cursor.tables()
                except pyodbc.Error:
                    print('DB Read Error: unable to find tables associated with database {}'.format(database))
                    return None

    def table_schema(self, database, table, timeout: int = 5):
        """
        Get table schema information.
        """
        try:
            conn = self.db_connect(database=database, timeout=timeout)
        except DBConnectionError:
            print('DB Read Error: connection to database cannot be established')
            return None
        else:
            try:
                cursor = conn.cursor()
            except AttributeError:
                print('DB Read Error: connection to database cannot be established')
                return None
            else:
                try:
                    return cursor.columns(table=table)
                except pyodbc.Error:
                    print('DB Read Error: unable to read the schema for table {}'.format(table))
                    return None

    def thread_transaction(self, statement, params, database: str = None, operation: str = 'read', timeout: int = 20):
        """
        Thread a database operation.
        """
        db = database if database else settings.dbname

        if operation == 'read':
            p = self.read_db
            alt_result = pd.DataFrame()
        elif operation == 'write':
            p = self.write_db
            alt_result = False
        else:
            raise ValueError('Database Error: unknown operation {}. operation must be either read or write'
                             .format(operation))

        with concurrent.futures.ThreadPoolExecutor(1) as executor:
            future = executor.submit(p, statement, params, db)

            start_time = time.time()
            while time.time() - start_time < timeout:
                sg.popup_animated(mod_const.PROGRESS_GIF, time_between_frames=100, keep_on_top=True, alpha_channel=0.5)

                if future.done():
                    sg.popup_animated(image_source=None)
                    print('Info: database process {} completed'.format(operation))
                    try:
                        result = future.result()
                    except Exception as e:
                        print('Info: database process failed - {}'.format(e))
                        raise

                    break
            else:
                try:
                    result = future.result(1)
                except concurrent.futures.TimeoutError:
                    result = alt_result
                popup_error('Error: database unresponsive after {} seconds'.format(timeout))
                sg.popup_animated(image_source=None)

        return result

    def read_db(self, statement, params, database):
        """
        Thread database read function.
        """
        # Connect to database
        try:
            conn = self.db_connect(database=database)
        except DBConnectionError:
            print('DB Read Error: connection to database cannot be established')
            df = pd.DataFrame()
        else:
            try:
                if params:
                    print('Info: query statement supplied is {} with parameters {}'.format(statement, params))
                    df = pd.read_sql(statement, conn, params=params)
                else:
                    print('Info: query statement supplied is {} with no parameters'.format(statement))
                    df = pd.read_sql(statement, conn)
            except sql.DatabaseError as ex:
                print('Query Error: {}'.format(ex))
                df = pd.DataFrame()
            else:
                print('Info: database {} successfully read'.format(database))

            conn.close()

        # Add return value to the queue
        return df

    def write_db(self, statement, params, database):
        """
        Thread database write functions.
        """
        # Connect to database
        try:
            conn = self.db_connect(database=database)
        except DBConnectionError:
            print('DB Write Error: connection to database cannot be established')
            status = False
        else:
            try:
                cursor = conn.cursor()
            except AttributeError:
                print('DB Write Error: connection to database cannot be established')
                status = False
            else:
                try:
                    cursor.execute(statement, params)
                except pyodbc.Error as e:  # possible duplicate entries
                    print('DB Write Error: {}'.format(e))
                    status = False
                else:
                    print('Info: database {} successfully modified'.format(database))

                    conn.commit()
                    status = True

                    # Close the connection
                    cursor.close()
                    conn.close()

        # Add return value to the queue
        return status

    def query(self, tables, columns='*', filter_rules=None, order=None, prog_db=False):
        """
        Query an ODBC database.

        Arguments:

            tables (str): primary table ID.

            columns: list or string containing the column(s) to select from the database table.

            filter_rules: tuple or list of tuples containing where clause and value tuple for a given filter rule.

            order: string or list of strings containing columns to sort results by.

           prog_db (bool): query from program database.
        """
        # Define sorting component of query statement
        if type(order) in (type(list()), type(tuple())):
            if len(order) > 0:
                order_by = ' ORDER BY {}'.format(', '.join(order))
            else:
                order_by = ''
        elif isinstance(order, str):
            order_by = ' ORDER BY {}'.format(order)
        else:
            order_by = ''

        # Define column component of query statement
        colnames = ', '.join(columns) if type(columns) in (type(list()), type(tuple())) else columns

        # Construct filtering rules
        try:
            where_clause, params = construct_where_clause(filter_rules)
        except SQLStatementError as e:
            print('Query Error: {}'.format(e))
            return pd.DataFrame()

        query_str = 'SELECT {COLS} FROM {TABLE} {WHERE} {SORT};'.format(COLS=colnames, TABLE=tables,
                                                                        WHERE=where_clause, SORT=order_by)

        print('Query string supplied was: {} with parameters {}'.format(query_str, params))

        db = self.dbname if prog_db else settings.dbname
        df = self.thread_transaction(query_str, params, operation='read', database=db)

        return df

    def insert(self, table, columns, values):
        """
        Insert data into the daily summary table.
        """
        values = self.convert_datatypes(values)

        # Format parameters
        if isinstance(values, list):
            if any(isinstance(i, list) for i in values):
                if not all([len(columns) == len(i) for i in values]):
                    print('Insertion Error: columns size is not equal to values size')
                    return False

                params = tuple([i for sublist in values for i in sublist])
                marker_list = []
                for value_set in values:
                    marker_list.append('({})'.format(','.join(['?' for _ in value_set])))
                markers = ','.join(marker_list)
            else:
                if len(columns) != len(values):
                    print('Insertion Error: header size is not equal to values size')
                    return False

                params = tuple(values)
                markers = '({})'.format(','.join(['?' for _ in params]))
        elif isinstance(values, tuple):
            if len(columns) != len(values):
                print('Insertion Error: header size is not equal to values size')
                return False

            params = values
            markers = '({})'.format(','.join(['?' for _ in params]))
        elif isinstance(values, str):
            if not isinstance(columns, str):
                print('Insertion Error: header size is not equal to values size')
                return False

            params = (values,)
            markers = '({})'.format(','.join(['?' for _ in params]))
        else:
            print('Insertion Error: unknown values type {}'.format(type(values)))
            return False

        insert_str = 'INSERT INTO {TABLE} ({COLS}) VALUES {VALS}' \
            .format(TABLE=table, COLS=','.join(columns), VALS=markers)
        print('Info: insertion string is: {}'.format(insert_str))
        print('Info: with parameters: {}'.format(params))

        db = self.dbname
        status = self.thread_transaction(insert_str, params, operation='write', database=db)

        return status

    def update(self, table, columns, values, filters):
        """
        Insert data into the daily summary table.
        """
        values = self.convert_datatypes(values)

        # Format parameters
        if isinstance(values, list):
            if len(columns) != len(values):
                print('Update Error: header size is not equal to values size')
                return False

            params = tuple(values)
        elif isinstance(values, tuple):
            if len(columns) != len(values):
                print('Update Error: header size is not equal to values size')
                return False

            params = values
        elif isinstance(values, str):
            if not isinstance(columns, str):
                print('Update Error: header size is not equal to values size')
                return False

            params = (values,)
        else:
            print('Update Error: unknown values type {}'.format(type(values)))
            return False

        pair_list = ['{}=?'.format(colname) for colname in columns]

        where_clause, filter_params = construct_where_clause(filters)
        if filter_params is not None:  # filter parameters go at end of parameter list
            params = params + filter_params

        update_str = 'UPDATE {TABLE} SET {PAIRS} {CLAUSE}' \
            .format(TABLE=table, PAIRS=','.join(pair_list), CLAUSE=where_clause)
        print('Info: update string is: {}'.format(update_str))
        print('Info: with parameters: {}'.format(params))

        db = self.dbname
        status = self.thread_transaction(update_str, params, operation='write', database=db)

        return status

    def delete(self, table, columns, values):
        """
        Delete data from a summary table.
        """
        values = self.convert_datatypes(values)

        # Format parameters
        if isinstance(values, list):
            params = tuple(values)

            if len(columns) != len(values):
                print('Deletion Error: columns size is not equal to values size')
                return False
        elif isinstance(values, tuple):
            params = values

            if len(columns) != len(values):
                print('Deletion Error: columns size is not equal to values size')
                return False
        elif isinstance(values, str):
            params = (values,)

            if not isinstance(columns, str):
                print('Deletion Error: columns size is not equal to values size')
                return False
        else:
            print('Deletion Error: unknown values type {}'.format(type(values)))
            return False

        #        pair_list = ['{}=?'.format(colname) for colname in columns]
        pairs = {}
        for colname in columns:
            if colname in pairs:
                pairs[colname].append('?')
            else:
                pairs[colname] = ['?']

        pair_list = []
        for colname in pairs:
            col_params = pairs[colname]
            if len(col_params) > 1:
                pair_list.append('{COL} IN ({VALS})'.format(COL=colname, VALS=', '.join(col_params)))
            elif len(col_params) == 1:
                pair_list.append('{COL}=?'.format(COL=colname))
            else:
                print('Deletion Warning: column {} has no associated parameters'.format(colname))
                continue

        delete_str = 'DELETE FROM {TABLE} WHERE {PAIRS}'.format(TABLE=table, PAIRS=' AND '.join(pair_list))
        print('Info: deletion string is: {}'.format(delete_str))
        print('Info: with parameters: {}'.format(params))

        db = settings.prog_db
        status = self.thread_transaction(delete_str, params, operation='write', database=db)

        return status

    def convert_datatypes(self, values):
        """
        Convert values with numpy data-types to native data-types.
        """
        strptime = datetime.datetime.strptime
        is_float_dtype = pd.api.types.is_float_dtype
        is_integer_dtype = pd.api.types.is_integer_dtype
        is_bool_dtype = pd.api.types.is_bool_dtype
        is_datetime_dtype = pd.api.types.is_datetime64_any_dtype
        date_fmt = self.date_format

        converted_values = []
        for value in values:
            if is_float_dtype(type(value)) is True or isinstance(value, float):
                converted_value = float(value)
            elif is_integer_dtype(type(value)) is True or isinstance(value, int):
                converted_value = int(value)
            elif is_bool_dtype(type(value)) is True or isinstance(value, bool):
                converted_value = bool(value)
            elif is_datetime_dtype(type(value)) is True or isinstance(value, datetime.datetime):
                converted_value = strptime(value.strftime(date_fmt), date_fmt)
            else:
                converted_value = str(value)

            converted_values.append(converted_value)

        return converted_values


# Functions
def hash_password(password):
    """
    Obtain a password's hash-code.
    """
    password_utf = password.encode('utf-8')

    md5hash = hashlib.md5()
    md5hash.update(password_utf)

    password_hash = md5hash.hexdigest()

    return password_hash


def construct_where_clause(filter_rules):
    """
    Construct an SQL statement where clause for querying and updating database tables.
    """
    if filter_rules is None or len(filter_rules) == 0:  # no filtering rules
        return ('', None)

    # Construct filtering rules
    if isinstance(filter_rules, list):  # multiple filter parameters
        all_params = []
        for rule in filter_rules:
            try:
                statement, params = rule
            except ValueError:
                print(rule)
                msg = 'incorrect data type for filter rule {}'.format(rule)
                raise SQLStatementError(msg)

            if type(params) in (type(tuple()), type(list())):
                # Unpack parameters
                for param_value in params:
                    all_params.append(param_value)
            elif type(params) in (type(str()), type(int()), type(float())):
                all_params.append(params)
            else:
                msg = 'unknown parameter type {} in rule {}'.format(params, rule)
                raise SQLStatementError(msg)

        params = tuple(all_params)
        where = 'WHERE {}'.format(' AND '.join([i[0] for i in filter_rules]))

    elif isinstance(filter_rules, tuple):  # single filter parameter
        statement, params = filter_rules
        where = 'WHERE {COND}'.format(COND=statement)

    else:  # unaccepted data type provided
        msg = 'unaccepted data type {} provided in rule {}'.format(type(filter_rules), filter_rules)
        raise SQLStatementError(msg)

    return (where, params)


def format_date_str(date_str):
    """
    Format a date string for use as input to datetime method.
    """
    separators = set(':/- ')
    date_fmts = {'YYYY': '%Y', 'YY': '%y',
                 'MMMM': '%B', 'MMM': '%b', 'MM': '%m', 'M': '%-m',
                 'DD': '%d', 'D': '%-d',
                 'HH': '%H', 'MI': '%M', 'SS': '%S'}

    strfmt = []
    last_char = date_str[0]
    buff = [last_char]
    for char in date_str[1:]:
        if char not in separators:
            if last_char != char:
                # Check if char is first in a potential series
                if last_char in separators:
                    buff.append(char)
                    last_char = char
                    continue

                # Check if component is minute
                if ''.join(buff + [char]) == 'MI':
                    strfmt.append(date_fmts['MI'])
                    buff = []
                    last_char = char
                    continue

                # Add characters in buffer to format string and reset buffer
                component = ''.join(buff)
                strfmt.append(date_fmts[component])
                buff = [char]
            else:
                buff.append(char)
        else:
            component = ''.join(buff)
            try:
                strfmt.append(date_fmts[component])
            except KeyError:
                if component:
                    raise TypeError('unknown component {} provided to date string {}.'.format(component, date_str))

            strfmt.append(char)
            buff = []

        last_char = char

    try:  # format final component remaining in buffer
        strfmt.append(date_fmts[''.join(buff)])
    except KeyError:
        raise TypeError('unsupported characters {} found in date string {}'.format(''.join(buff), date_str))

    return ''.join(strfmt)


def popup_error(msg):
    """
    Display popup notifying user that there is a fatal program error.
    """
    font = mod_const.MID_FONT
    return sg.popup_error(textwrap.fill(msg, width=40), font=font, title='')


# Determine if application is a script file or frozen exe
if getattr(sys, 'frozen', False):
    _dirname = os.path.dirname(sys.executable)
elif __file__:
    _dirname = os.path.dirname(__file__)
else:
    popup_error('Unable to determine file type of the program. Please verify proper program installation.')
    sys.exit(1)

# Load user-defined configuration settings
_user_cnfg_name = 'settings.yaml'
_user_cnfg_file = os.path.join(_dirname, _user_cnfg_name)

try:
    _user_fh = open(_user_cnfg_file, 'r', encoding='utf-8')
except FileNotFoundError:
    msg = 'Unable to load user settings file at {PATH}. Please verify that the file path is correct.'\
        .format(PATH=_user_cnfg_file)
    popup_error(msg)
    sys.exit(1)
else:
    _user_cnfg = yaml.safe_load(_user_fh)
    _user_fh.close()
    del _user_fh

settings = UserSettings(_user_cnfg, _dirname)

# Initialize a user account
user = UserAccount(_user_cnfg)
