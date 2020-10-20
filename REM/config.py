"""
REM settings initializer
"""

import PySimpleGUI as sg
import os
from pymongo import MongoClient, errors
import REM.constants as const
import REM.settings as prog_sets
import sys
import textwrap
import yaml


class Config:
    """
    Class to store program configuration.
    """

    def __init__(self):
        # Database parameters
        self.cnx = None
        self.database = None
        self.collection = None

        # Program configuration parameters
        self.audit_rules = None
        self.cash_rules = None
        self.bank_rules = None
        self.startup_msgs = None

    def connect(self, timeout=2000):
        """
        Connect to the NoSQL database using the pymongo driver.
        """
        connection_info = {'username': settings.mongod_user, 'password': settings.mongod_pwd,
                           'host': settings.mongod_server, 'port': settings.mongod_port,
                           'authSource': settings.mongod_authdb, 'connectTimeoutMS': timeout}
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

        try:
            database = cnx[settings.mongod_database]
        except errors.InvalidName:
            print('Error: cannot access database {}'.format(settings.mongod_database))
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

        try:
            collection = database[settings.mongod_config]
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
            popup_error('Unable to load configuration from database - {}'.format(e))
            sys.exit(1)
        else:
            self.audit_rules = collection.find_one({'name': 'audit_rules'})
            self.cash_rules = collection.find_one({'name': 'cash_rules'})
            self.bank_rules = collection.find_one({'name': 'bank_rules'})
            self.startup_msgs = collection.find_one({'name': 'startup_messages'})


def popup_error(msg):
    """
    Display popup notifying user that there is a fatal program error.
    """
    font = const.MID_FONT
    return sg.popup_error(textwrap.fill(msg, width=40), font=font, title='')


# Global configuration settings
user_cnfg_name = 'settings.yaml'

# Determine if application is a script file or frozen exe
if getattr(sys, 'frozen', False):
    dirname = os.path.dirname(sys.executable)
elif __file__:
    dirname = os.path.dirname(__file__)

user_cnfg_file = os.path.join(dirname, user_cnfg_name)

try:
    fh = open(user_cnfg_file, 'r', encoding='utf-8')
except FileNotFoundError:
    msg = 'Unable to load configuration file at {}'.format(user_cnfg_file)
    popup_error(msg)
    sys.exit(1)
else:
    user_cnfg = yaml.safe_load(fh)
    fh.close()
    del fh

settings = prog_sets.ProgramSettings(user_cnfg, dirname)
