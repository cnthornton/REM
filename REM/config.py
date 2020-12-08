"""
REM settings initializer
"""

import PySimpleGUI as sg
import os
from pymongo import MongoClient, errors
import pyodbc
import REM.constants as const
import REM.settings as prog_sets
import sys
import textwrap
import yaml


class Config:
    """
    Class to the program configuration from a MongoDB document.
    """

    def __init__(self, cnfg):
        # Database parameters
        try:
            self.mongod_port = cnfg['configuration']['mongod_port']
        except KeyError:
            self.mongod_port = 27017
        try:
            self.mongod_server = cnfg['configuration']['mongod_server']
        except KeyError:
            self.mongod_server = 'localhost'
        try:
            self.mongod_database = cnfg['configuration']['mongod_database']
        except KeyError:
            self.mongod_database = 'REM'
        try:
            self.mongod_config = cnfg['configuration']['mongod_config']
        except KeyError:
            self.mongod_config = 'configuration'
        try:
            self.mongod_user = cnfg['configuration']['mongod_user']
        except KeyError:
            self.mongod_user = 'mongo'
        try:
            self.mongod_pwd = cnfg['configuration']['mongod_pwd']
        except KeyError:
            self.mongod_pwd = ''
        try:
            self.mongod_authdb = cnfg['configuration']['mongod_authdb']
        except KeyError:
            self.mongod_authdb = 'REM'

        # Table field parameters
        try:
            self.creator_code = cnfg['fields']['creator_code_field']
        except KeyError:
            self.creator_code = 'CreatorCode'
        try:
            self.creation_date = cnfg['fields']['creation_date_field']
        except KeyError:
            self.creation_date = 'CreationDateTime'
        try:
            self.editor_code = cnfg['fields']['editor_code_field']
        except KeyError:
            self.editor_code = 'LastEditor'
        try:
            self.edit_date = cnfg['fields']['edit_date_field']
        except KeyError:
            self.edit_date = 'LastEditTime'

        # Connection parameters
        self.cnx = None
        self.database = None
        self.collection = None

        # Program configuration parameters
        self.audit_rules = None
        self.cash_rules = None
        self.bank_rules = None
        self.startup_msgs = None
        self.ids = None
        self.db_records = None
        self.data_db = None

    def connect(self, timeout=5000):
        """
        Connect to the NoSQL database using the pymongo driver.
        """
        print('Info: connecting to the configuration database')
        connection_info = {'username': self.mongod_user, 'password': self.mongod_pwd,
                           'host': self.mongod_server, 'port': self.mongod_port,
                           'authSource': self.mongod_authdb, 'serverSelectionTimeoutMS': timeout}
        try:
            cnx = MongoClient(**connection_info)
        except errors.ConnectionFailure as e:
            print('Error: connection to configuration database failed - {}'.format(e))
            cnx = None
        else:
            self.cnx = cnx

        return cnx

    def load_database(self):
        """
        Load the NoSQL database containing the configuration collection.
        """
        if self.cnx is None:
            cnx = self.connect()
            if cnx is None:
                return None
            else:
                self.cnx = cnx
        else:
            cnx = self.cnx

        print('Info: loading the configuration database')
        try:
            database = cnx[self.mongod_database]
        except errors.InvalidName:
            print('Error: cannot access database {}'.format(self.mongod_database))
            database = None
        else:
            self.database = database

        return database

    def load_collection(self):
        """
        Load the configuration collection.
        """
        if self.database is None:
            database = self.load_database()
            if database is None:
                return {}
        else:
            database = self.database

        print('Info: loading the database collection')
        try:
            collection = database[self.mongod_config]
        except errors.InvalidName:
            collection = {}
        else:
            self.collection = collection

        return collection

    def load_configuration(self):
        """
        Load the configuration documents.
        """
        if self.collection is None:
            collection = self.load_collection()
            if collection is None:
                popup_error('Unable to load configuration from the configuration database')
                sys.exit(1)
        else:
            collection = self.collection

        try:
            print(self.cnx.server_info())
        except Exception as e:
            popup_error('Unable to load the configuration from the database - {}'.format(e))
            print(e)
            sys.exit(1)
        else:
            self.audit_rules = collection.find_one({'name': 'audit_rules'})
            self.cash_rules = collection.find_one({'name': 'cash_rules'})
            self.bank_rules = collection.find_one({'name': 'bank_rules'})
            self.startup_msgs = collection.find_one({'name': 'startup_messages'})
            self.db_records = collection.find_one({'name': 'records'})
            self.ids = collection.find_one({'name': 'ids'})


class ProgramAccount:
    """
    Program account object.

    Attributes:
        uid (str): existing account username.

        pwd (str): associated account password.
    """

    def __init__(self, cnfg):
        self.uid = cnfg['database']['odbc_user']
        self.pwd = cnfg['database']['odbc_pwd']

        self.database = cnfg['database']['odbc_database']
        self.server = cnfg['database']['odbc_server']
        self.port = cnfg['database']['odbc_port']
        self.driver = cnfg['database']['odbc_driver']

    def db_connect(self, timeout=5):
        """
        Generate a pyODBC Connection object.
        """
        uid = self.uid
        pwd = self.pwd
        if r'"' in pwd or r';' in pwd or r"'" in pwd:
            pwd = "{{{}}}".format(pwd)

        driver = self.driver
        server = self.server
        port = self.port
        dbname = self.database

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

    def query_ids(self, table, column, timeout=2):
        """
        Query table for list of unique entry IDs.
        """

        # Define query statement
        query_str = 'SELECT DISTINCT {COL} FROM {TABLE} ORDER BY {COL};'.format(COL=column, TABLE=table)

        # Connect to database
        id_list = []
        try:
            conn = self.db_connect(timeout=timeout)
        except Exception as e:
            print('DB Write Error: connection to database cannot be established - {ERR}'.format(ERR=e))
        else:
            try:
                cursor = conn.cursor()
            except AttributeError:
                print('DB Write Error: connection to database {DB} cannot be established'.format(DB=self.database))
            else:
                try:
                    cursor.execute(query_str)
                except pyodbc.Error as e:  # possible duplicate entries
                    print('DB Write Error: {ERR}'.format(ERR=e))
                else:
                    print('Info: database {DB} successfully read'.format(DB=self.database))

                    for row in cursor.fetchall():
                        id_list.append(row[0])

                    # Close the connection
                    cursor.close()
                    conn.close()

        # Add return value to the queue
        return id_list


def popup_error(msg):
    """
    Display popup notifying user that there is a fatal program error.
    """
    font = const.MID_FONT
    return sg.popup_error(textwrap.fill(msg, width=40), font=font, title='')


# Determine if application is a script file or frozen exe
if getattr(sys, 'frozen', False):
    _dirname = os.path.dirname(sys.executable)
elif __file__:
    _dirname = os.path.dirname(__file__)
else:
    popup_error('Unable to determine file type of the program')
    sys.exit(1)

# Load global configuration settings
_prog_cnfg_name = 'configuration.yaml'
_prog_cnfg_file = os.path.join(_dirname, _prog_cnfg_name)

try:
    _prog_fh = open(_prog_cnfg_file, 'r', encoding='utf-8')
except FileNotFoundError:
    msg = 'Unable to load configuration file at {}'.format(_prog_cnfg_file)
    popup_error(msg)
    sys.exit(1)
else:
    _prog_cnfg = yaml.safe_load(_prog_fh)
    _prog_fh.close()
    del _prog_fh

print('Info: loading the configuration')
configuration = Config(_prog_cnfg)
configuration.load_configuration()

# Connect to database as program user
program_account = ProgramAccount(_prog_cnfg)

# Obtain lists of used entry IDs for the program tables
current_tbl_pkeys = {}
for _db_table in configuration.ids['PrimaryKeys']:
    _tbl_id_column = configuration.ids['PrimaryKeys'][_db_table]
    current_tbl_pkeys[_db_table] = program_account.query_ids(_db_table, _tbl_id_column)

# Load user-defined configuration settings
_user_cnfg_name = 'settings.yaml'
_user_cnfg_file = os.path.join(_dirname, _user_cnfg_name)

try:
    _user_fh = open(_user_cnfg_file, 'r', encoding='utf-8')
except FileNotFoundError:
    msg = 'Unable to load configuration file at {}'.format(_user_cnfg_file)
    popup_error(msg)
    sys.exit(1)
else:
    _user_cnfg = yaml.safe_load(_user_fh)
    _user_fh.close()
    del _user_fh

settings = prog_sets.UserSettings(_user_cnfg, _dirname)
