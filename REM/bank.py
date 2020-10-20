"""
REM bank reconciliation configuration classes and objects.
"""
import datetime
import os
import re
import sys

import dateutil.parser
from jinja2 import Environment, FileSystemLoader
import numpy as np
import pandas as pd
import PySimpleGUI as sg
import pdfkit

import REM.constants as const
import REM.data_manipulation as dm
import REM.layouts as lo
import REM.secondary as win2
from REM.config import settings


class BankRules:
    """
    Class to store and manage program bank_reconciliation configuration settings.

    Arguments:

        cnfg (Config): program configuration class.

    Attributes:

        rules (list): List of BankRule objects.
    """

    def __init__(self, cnfg):

        # Audit parameters
        bank_param = cnfg.bank_rules

        self.rules = []
        if bank_param is not None:
            try:
                bank_name = bank_param['name']
            except KeyError:
                win2.popup_error('Error: bank_rules: the parameter "name" is a required field')
                sys.exit(1)
            else:
                self.name = bank_name

            try:
                self.title = bank_param['title']
            except KeyError:
                self.title = bank_name

            try:
                bank_rules = bank_param['rules']
            except KeyError:
                win2.popup_error('Error: bank_rules: the parameter "rules" is a required field')
                sys.exit(1)

            for rule_name in bank_rules:
                self.rules.append(BankRule(rule_name, bank_rules[rule_name]))

    def print_rules(self, title=True):
        """
        Return name of all bank rules defined in configuration file.
        """
        if title is True:
            return [i.title for i in self.rules]
        else:
            return [i.name for i in self.rules]

    def fetch_rule(self, name, title=True):
        """
        Fetch a given rule from the rule set by its name or title.
        """
        rule_names = self.print_rules(title=title)
        try:
            index = rule_names.index(name)
        except IndexError:
            print('Rule {NAME} not in list of configured bank reconciliation rules. Available rules are {ALL}'
                  .format(NAME=name, ALL=', '.join(self.print_rules())))
            rule = None
        else:
            rule = self.rules[index]

        return rule


class BankRule:
    """
    Class to store and manage a configured bank reconciliation rule.

    Arguments:

        name (str): bank reconciliation rule name.

        adict (dict): dictionary of optional and required bank rule arguments.

    Attributes:

        name (str): bank reconciliation rule name.

        title (str): bank reconciliation rule title.

        element_key (str): GUI element key.

        permissions (str): permissions required to view the accounting method. Default: user.
    """

    def __init__(self, name, adict):

        self.name = name
        self.element_key = lo.as_key(name)
        self.elements = ['Cancel', 'Save', 'Create', 'Edit', 'TransNo', 'DocDate', 'Amount']

        try:
            self.title = adict['Title']
        except KeyError:
            self.title = name

        try:
            self.permissions = adict['Permissions']
        except KeyError:  # default permission for a cash rule is 'user'
            self.permissions = 'user'

    def key_lookup(self, element):
        """
        Lookup element key for input control element.
        """
        if element in self.elements:
            key = lo.as_key('{} {}'.format(self.name, element))
        else:
            key = None

        return key
