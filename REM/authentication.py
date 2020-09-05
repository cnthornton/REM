"""
REM authentication and user classes.
"""
import hashlib
import pandas as pd
import pyodbc
import PySimpleGUI as sg
import sys

# Classes
class SQLStatementError(Exception):
    """A simple exception that is raised when an SQL statemet is formatted
    incorrectly
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
        self.cnxn_prog = None
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

        cnxn_prog = db.db_connect(uid, pwd)
        self.cnxn_prog = cnxn_prog

    def logout(self):
        """
        Reset class attributes.
        """
        self.uid = None
        self.pwd = None
        self.logged_in = False
        self.superuser = False
        try:
            self.cnxn.close()
            self.cnxn_prog.close()
        except AttributeError:
            self.cnxn = None
            self.cnxn_prog = None
        else:
            self.cnxn = None
            self.cnxn_prog = None

    def query(self, tables, columns='*', filter_rules=None, order=None, prog_db=False):
        """
        Query ODBC database.

        Arguments:

            tables (str): database table to query.

            columns: list or string containing the columns to select from the
                database table.

            filter_rules: tuple or list of tuples containing where clause and 
                value tuple for a given filter rule.

            order: string or tuple of strings containing columns to sort
                results by.
        """
        joins = ('INNER JOIN', 'JOIN', 'LEFT JOIN', 'LEFT OUTER JOIN',
                 'RIGHT JOIN', 'RIGHT OUTER JOIN', 'FULL JOIN',
                 'FULL OUTER JOIN', 'CROSS JOIN')

        # Connect to database
        conn = self.cnxn if not prog_db else self.cnxn_prog
        try:
            cursor = conn.cursor()
        except AttributeError:
            print('Query Error: connection to database cannot be established')
            return(pd.DataFrame())

        # Define sorting component of query statement
        if type(order) in (type(list()), type(tuple())):
            order_by = ' ORDER BY {}'.format(', '.join(order))
        elif type(order) == type(str()):
            order_by = ' ORDER BY {}'.format(order)
        else:
            order_by = ''

        # Define column component of query statement
        colnames = ', '.join(columns) if type(columns) in \
            (type(list()), type(tuple())) else columns

        # Define table component of query statement
        table_names = [i for i in tables] if type(tables) in \
            (type(dict()), type(list())) else [tables]
        first_table = table_names[0]
        if len(table_names) > 1:
            table_rules = [first_table]
            for table in table_names[1:]:
                table_rule = tables[table]
                try:
                    tbl1_field, tbl2_field, join_clause = table_rule
                except ValueError:
                    print('Query Error: table join rule {} requires three '\
                        'components'.format(table_rule))
                    continue
                if join_clause not in joins:
                    print('Query Error: unknown join type {JOIN} in {RULE} '
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
        try:
            where_clause, params = self.construct_where_clause(filter_rules)
        except SQLStatementError as e:
            print('Query Error: {}'.format(e))
            return(pd.DataFrame())

        query_str = 'SELECT {COLS} FROM {TABLE} {WHERE} {SORT};'\
            .format(COLS=colnames, TABLE=table_component, WHERE=where_clause, \
            SORT=order_by)

        # Query database and format results as a Pandas dataframe
        try:
            df = pd.read_sql(query_str, conn, params=params)
        except pd.io.sql.DatabaseError as ex:
            sqlstat = ex.args[1]
            print('Query Error: {}'.format(sqlstat))
            df = pd.DataFrame()

        cursor.close()

        return(df)

    def insert(self, table, columns, values):
        """
        Insert data into the daily summary table.
        """
        conn = self.cnxn_prog
        try:
            cursor = conn.cursor()
        except AttributeError:
            print('Insertion Error: connection to database cannot be established')
            return(False)

        if len(columns) != len(values):
            print('Insertion Error: columns size is not equal to values size')
            return(False)

        # Format parameters
        if type(values) == type(list()):
            params = tuple(values)
        elif type(values) == type(tuple()):
            params = values
        elif type(values) == type(str()):
            params = (values,)
        else:
            print('Insertion Error: unknown values type {}'\
                .format(type(values)))
            return(False)

        insert_str = 'INSERT INTO {TABLE} ({COLS}) VALUES ({VALS})'\
            .format(TABLE=table, COLS=','.join(columns), \
            VALS=','.join(['?' for i in params]))
        print('insertion string is: {}'.format(insert_str))
        print('with parameters: {}'.format(params))

        try:
            cursor.execute(insert_str, params)
        except pyodbc.Error as ex1:  #possible duplicate entries
            print('Insertion Error: {}'.format(ex1))
            return(False)
        else:
            conn.commit()

        cursor.close()

        return(True)

    def update(self, table, columns, values, filters):
        """
        Insert data into the daily summary table.
        """
        conn = self.cnxn_prog
        try:
            cursor = conn.cursor()
        except AttributeError:
            print('Update Error: connection to database cannot be established')
            return(False)

        if len(columns) != len(values):
            print('Update Error: columns size is not equal to values size')
            return(False)

        # Format parameters
        if type(values) == type(list()):
            params = tuple(values)
        elif type(values) == type(tuple()):
            params = values
        elif type(values) == type(str()):
            params = (values,)
        else:
            print('Update Error: unknown values type {}'\
                .format(type(values)))
            return(False)

        pair_list = ['{}=?'.format(colname) for colname in columns]

        where_clause, filter_params = self.construct_where_clause(filters)
        if type(filter_params) == type(tuple()):
            params = params + filter_params

        update_str = 'UPDATE {TABLE} SET {PAIRS} {CLAUSE}'\
            .format(TABLE=table, PAIRS=','.join(pair_list), CLAUSE=where_clause)
        print('update string is: {}'.format(update_str))
        print('with parameters: {}'.format(params))

        try:
            cursor.execute(update_str, params)
        except pyodbc.Error as ex:
            print('Update Error: {}'.format(ex))
            return(False)
        else:
            conn.commit()

        cursor.close()

        return(True)

    def construct_where_clause(self, filter_rules):
        """
        Construct an SQL statement where clause for querying and updating 
        database tables.
        """
        if filter_rules is None:  #no filtering rules
            return(('', None))

        # Construct filtering rules
        if type(filter_rules) == type(list()):  #multiple filter parameters
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
                    msg = 'unknown parameter type {} in rule {}'\
                        .format(params, rule)
                    raise SQLStatementError(msg)

            params = tuple(all_params)
            where = 'WHERE {}'.format(' AND '.join([i[0] for i in filter_rules]))

        elif type(filter_rules) == type(tuple()):  #single filter parameter
            statement, params = filter_rules
            where = 'WHERE {COND}'.format(COND=statement)

        else:  #unaccepted data type provided
            msg = 'unaccepted data type {} provided in rule {}'\
                .format(type(rule), rule)
            raise SQLStatementError(msg)

        return((where, params))

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
            print('Error: connection to database cannot be established')
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
