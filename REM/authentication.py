"""
REM authentication and user classes.
"""
import concurrent.futures
import hashlib
import pandas as pd
from pandas.io import sql
import pyodbc
import PySimpleGUI as sg
from REM.config import settings
import REM.constants as const
import REM.secondary as win2
import time


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


class UserAccount:
    """
    Basic user account object.

    Attributes:
        uid (str): existing account username.

        pwd (str): hash value for associated account password.

        admin (bool): existing account is an admin account.

        logged_in (bool): user is logged in
    """

    def __init__(self):
        """
        """
        # User account attributes
        self.uid = None
        self.pwd = None
        self.logged_in = False
        self.admin = False

    def login(self, uid, pwd):
        """
        Verify username and password exists in the database accounts table and obtain user permissions.

        Args:
            db (class): DataBase object.

            uid (str): existing account username.

            pwd (str): password associated with the existing account.
        """
        self.uid = uid
        self.pwd = pwd

        conn = self.db_connect(database=settings.prog_db, timeout=2)

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
        self.logged_in = False
        self.admin = False

        return True

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

    def database_tables(self, database, timeout: int = 2):
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
                    return cursor.tables()
                except pyodbc.Error:
                    print('DB Read Error: unable to find tables associated with database {}'.format(database))
                    return None

    def table_schema(self, database, table, timeout: int = 2):
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

    def thread_transaction(self, statement, params, database: str = None, operation: str = 'read', timeout: int = 10):
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
                sg.popup_animated(const.PROGRESS_GIF, time_between_frames=100, keep_on_top=True, alpha_channel=0.5)

                if future.done():
                    print('Info: database process {} completed'.format(operation))
                    try:
                        result = future.result()
                    except Exception as e:
                        print('Info: database process failed due to {}'.format(e))
                        result = alt_result

                    sg.popup_animated(image_source=None)
                    break
            else:
                try:
                    result = future.result(1)
                except concurrent.futures.TimeoutError:
                    result = alt_result
                win2.popup_error('Error: database unresponsive after {} seconds'.format(timeout))
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
                df = pd.read_sql(statement, conn, params=params)
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
        Query ODBC database.

        Arguments:

            tables (dict): database tables to query.

            columns: list or string containing the columns to select from the
                database table.

            filter_rules: tuple or list of tuples containing where clause and 
                value tuple for a given filter rule.

            order: string or tuple of strings containing columns to sort
                results by.

           prog_db (bool): query from program database.
        """
        joins = ('INNER JOIN', 'JOIN', 'LEFT JOIN', 'LEFT OUTER JOIN',
                 'RIGHT JOIN', 'RIGHT OUTER JOIN', 'FULL JOIN',
                 'FULL OUTER JOIN', 'CROSS JOIN')

        # Define sorting component of query statement
        if type(order) in (type(list()), type(tuple())):
            order_by = ' ORDER BY {}'.format(', '.join(order))
        elif type(order) == type(str()):
            order_by = ' ORDER BY {}'.format(order)
        else:
            order_by = ''

        # Define column component of query statement
        colnames = ', '.join(columns) if type(columns) in (type(list()), type(tuple())) else columns

        # Define table component of query statement
        table_names = [i for i in tables] if type(tables) == type(dict()) else [tables]
        first_table = table_names[0]
        if len(table_names) > 1:
            table_rules = [first_table]
            for table in table_names[1:]:
                table_rule = tables[table]
                try:
                    tbl1_field, tbl2_field, join_clause = table_rule
                except ValueError:
                    print('Query Error: table join rule {} requires three components'.format(table_rule))
                    continue
                if join_clause not in joins:
                    print('Query Error: unknown join type {JOIN} in {RULE}'.format(JOIN=join_clause, RULE=table_rule))
                    continue
                join_statement = '{JOIN} {TABLE} ON {F1}={F2}'.format(JOIN=join_clause, TABLE=table, F1=tbl1_field,
                                                                      F2=tbl2_field)
                table_rules.append(join_statement)
            table_component = ' '.join(table_rules)
        else:
            table_component = first_table

        # Construct filtering rules
        try:
            where_clause, params = self.construct_where_clause(filter_rules)
        except SQLStatementError as e:
            print('Query Error: {}'.format(e))
            return pd.DataFrame()

        query_str = 'SELECT {COLS} FROM {TABLE} {WHERE} {SORT};'.format(COLS=colnames, TABLE=table_component,
                                                                        WHERE=where_clause, SORT=order_by)

        print('Query string supplied was: {} with parameters {}'.format(query_str, params))

        db = settings.prog_db if prog_db else settings.dbname
        df = self.thread_transaction(query_str, params, operation='read', database=db)

        return df

    def insert(self, table, columns, values):
        """
        Insert data into the daily summary table.
        """

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

        insert_str = 'INSERT INTO {TABLE} ({COLS}) VALUES {VALS}'\
            .format(TABLE=table, COLS=','.join(columns), VALS=markers)
        print('Info: insertion string is: {}'.format(insert_str))
        print('Info: with parameters: {}'.format(params))

        db = settings.prog_db
        status = self.thread_transaction(insert_str, params, operation='write', database=db)

        return status

    def update(self, table, columns, values, filters):
        """
        Insert data into the daily summary table.
        """

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

        where_clause, filter_params = self.construct_where_clause(filters)
        if isinstance(filter_params, tuple):
            params = params + filter_params

        update_str = 'UPDATE {TABLE} SET {PAIRS} {CLAUSE}'\
            .format(TABLE=table, PAIRS=','.join(pair_list), CLAUSE=where_clause)
        print('Info: update string is: {}'.format(update_str))
        print('Info: with parameters: {}'.format(params))

        db = settings.prog_db
        status = self.thread_transaction(update_str, params, operation='write', database=db)

        return status

    def delete(self, table, columns, values):
        """
        Delete data from a summary table.
        """

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

        pair_list = ['{}=?'.format(colname) for colname in columns]

        delete_str = 'DELETE FROM {TABLE} WHERE {PAIRS}'.format(TABLE=table, PAIRS=' AND '.join(pair_list))
        print('Info: deletion string is: {}'.format(delete_str))
        print('Info: with parameters: {}'.format(params))

        db = settings.prog_db
        status = self.thread_transaction(delete_str, params, operation='write', database=db)

        return status

    def construct_where_clause(self, filter_rules):
        """
        Construct an SQL statement where clause for querying and updating 
        database tables.
        """
        if filter_rules is None:  # no filtering rules
            return ('', None)

        # Construct filtering rules
        if isinstance(filter_rules, list):  # multiple filter parameters
            all_params = []
            for rule in filter_rules:
                try:
                    statement, params = rule
                except ValueError:
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
