"""
REM authentication and user classes.
"""
import hashlib
import pandas as pd
import PySimpleGUI as sg
import sys

# Classes

# Exceptions
class UserNotFound(Exception):
    """
    Exception for when querying a user in the database returns empty.
    """
    def __init__(self,*args,**kwargs):
        Exception.__init__(self,*args,**kwargs)


class PasswordMismatch(Exception):
    """
    Exception for when password does not match user password in the database.
    """
    def __init__(self,*args,**kwargs):
        Exception.__init__(self,*args,**kwargs)


class UserAccount:
    """
    Basic user account object.

    Attributes:
        uid (str): existing account username.

        pwd (str): hash value for associated account password.

        superuser (bool): existing account is an admin account.

        cnxn (class): pyodbc connection object

        logged_in (bool): user is logged in
    """

    def __init__(self):
        """
        """
        self.uid = None
        self.pwd = None
        self.cnxn = None
        self.logged_in = False
        self.superuser = False

    def login(self, db, uid, pwd):
        """
        Verify username and password exists in the database accounts table
        and obtain user permissions.

        Args:
            uid (str): existing account username.

            pwd (str): password associated with the existing account.
        """
        ugroup = db.authenticate(uid, pwd)

        self.uid = uid,
        self.pwd = pwd
        self.logged_in = True

        if ugroup == 'admin':
            self.superuser = True

        cnxn = db.db_connect(uid, pwd, database=db.dbname)
        self.cnxn = cnxn

    def logout(self):
        """
        Reset UserAccount attributes
        """
        self.uid = None
        self.pwd = None
        self.logged_in = False
        self.superuser = False
        try:
            self.cnxn.close()
        except AttributeError:
            self.cnxn = None
        else:
            self.cnxn = None

    def query(self, tables, columns='*', filter_rules=None, order=None):
        """
        Query database for the given order number.

        Arguments:

            tables (str): Database table to pull data from.

            columns: List or string containing the columns to select from the
                database table.

            filter_rules: Tuple or list of tuples containing column name,
                operator, and value for a given filter rule.

            order: String or tuple of strings containing columns to sort
                results by.
        """
        joins = ('INNER JOIN', 'JOIN', 'LEFT JOIN', 'LEFT OUTER JOIN',
                 'RIGHT JOIN', 'RIGHT OUTER JOIN', 'FULL JOIN',
                 'FULL OUTER JOIN', 'CROSS JOIN')

        # Connect to database
        conn = self.cnxn
        try:
            cursor = conn.cursor()
        except AttributeError:
            print('Error: connection to database {} not established'\
                .format(self.dbname))
            return(None)

        # Define sorting component of query statement
        if type(order) == type(list()):
            order_by = ' ORDER BY {}'.format(', '.join(order))
        elif type(order) == type(str()):
            order_by = ' ORDER BY {}'.format(order)
        else:
            order_by = ''

        # Define column component of query statement
        colnames = ', '.join(columns) if type(columns) == type(list()) else columns

        # Define table component of query statement
        table_names = [i for i in tables] if type(tables) == type(dict()) or \
            type(tables) == type(list()) else [tables]
        first_table = table_names[0]
        if len(table_names) > 1:
            table_rules = [first_table]
            for table in table_names[1:]:
                table_rule = tables[table]
                try:
                    tbl1_field, tbl2_field, join_clause = table_rule
                except ValueError:
                    print('Error: table join rule {} requires three '\
                        'components'.format(table_rule))
                    continue
                if join_clause not in joins:
                    print('Error: unknown join type {JOIN} in {RULE} '
                          ''.format(JOIN=join_clause, RULE=table_rule))
                    continue
                join_statement = '{JOIN} {TABLE} ON {F1}={F2}'\
                    .format(JOIN=join_clause, TABLE=table, F1=tbl1_field, \
                    F2=tbl2_field)
                table_rules.append(join_statement)
            table_component = ' '.join(table_rules)
        else:
            table_component = first_table

        # Construct filtering rules
        if type(filter_rules) == type(list()):  #multiple filter parameters
            params_list = []
            for rule in filter_rules:
                param_tup = rule[1]
                for item in param_tup:
                    params_list.append(item)
            params = tuple(params_list)
            where_clause = 'WHERE {}'\
                .format(' AND '.join([i[0] for i in filter_rules]))
        elif type(filter_rules) == type(tuple()):  #single filter parameter
            condition, params = filter_rules
            where_clause = 'WHERE {COND}'.format(COND=condition)
        else:  #no filters
            where_clause = ''

        query_str = 'SELECT {COLS} FROM {TABLE} {WHERE} {SORT};'\
            .format(COLS=colnames, TABLE=table_component, WHERE=where_clause, \
            SORT=order_by)

        # Query database and format results as a Pandas dataframe
        df = pd.read_sql(query_str, conn, params=params)

        cursor.close()

        return(df)

    def insert(self, table=None):
        """
        Insert data into the daily summary table.
        """

        return(True)

    def change_password(self, pwd):
        """
        Change the password associated with the account.

        Args:
            pwd (str): new password to be associated with the account.
        """
        uid = self.uid

        conn = self.cnxn
        try:
            cursor = conn.cursor()
        except AttributeError:
            print('Error: connection to database {} not established'\
                .format(self.dbname))
            return(False)

        update_str = 'UPDATE Users SET PWD = ? WHERE UID = ?'
        try:
            cursor.execute(update_str, (pwd, uid))
        except pyodbc.Error as e:
            print('DB Error: updating password of user {UID} failed due to {EX}'\
                .format(UID=uid, EX=e))
            return(False)
        else:
            self.pwd = pwd

        return(True)


# Functions
def hash_password(password):
    """
    Obtain a password's hash-code.
    """
    password_utf = password.encode('utf-8')

    md5hash = hashlib.md5()
    md5hash.update(password_utf)

    password_hash = md5hash.hexdigest()

    return(password_hash)
