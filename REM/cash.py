"""
REM cash reconciliation configuration classes and objects.
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


class CashRules:
    """
    Class to store and manage program cash_reconciliation configuration settings.

    Arguments:

        cnfg (Config): program configuration class.

    Attributes:

        rules (list): List of CashRule objects.
    """

    def __init__(self, cnfg):
        self.name = 'Cash Reconciliation'

        # Individual rules
        cash_param = cnfg.cash_recon

        self.rules = []
        if cash_param is not None:
            try:
                cash_name = cash_param['name']
            except KeyError:
                win2.popup_error('Error: audit_rules: the parameter "name" is a required field')
                sys.exit(1)
            else:
                self.name = cash_name

            try:
                self.title = cash_param['title']
            except KeyError:
                self.title = cash_name

            try:
                cash_rules = cash_param['rules']
            except KeyError:
                win2.popup_error('Error: audit_rules: the parameter "rules" is a required field')
                sys.exit(1)

            for rule_name in cash_rules:
                self.rules.append(CashRule(rule_name, cash_rules[rule_name]))

    def print_rules(self, title=True):
        """
        Return name of all cash rules defined in configuration file.
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
            print('Rule {NAME} not in list of configured cash reconciliation rules. Available rules are {ALL}'
                  .format(NAME=name, ALL=', '.join(self.print_rules())))
            rule = None
        else:
            rule = self.rules[index]

        return rule


class CashRule:
    """
    Class to store and manage a configured cash reconciliation rule.

    Arguments:

        name (str): cash reconciliation rule name.

        adict (dict): dictionary of optional and required cash rule arguments.

    Attributes:

        name (str): cash reconciliation rule name.

        title (str): cash reconciliation rule title.

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
