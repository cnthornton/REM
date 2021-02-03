"""
REM cash reconciliation configuration classes and objects.
"""
import datetime
import re
import sys

import dateutil.parser
import numpy as np
import pandas as pd
import PySimpleGUI as sg
from random import randint

import REM.constants as mod_const
import REM.data_manipulation as mod_dm
import REM.layouts as mod_lo
import REM.secondary as mod_win2
from REM.config import configuration, settings


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
        cash_param = cnfg.cash_rules

        self.rules = []
        if cash_param is not None:
            try:
                cash_name = cash_param['name']
            except KeyError:
                mod_win2.popup_error('Error: cash_rules: the parameter "name" is a required field')
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
                mod_win2.popup_error('Error: cash_rules: the parameter "rules" is a required field')
                sys.exit(1)

            for rule_name in cash_rules:
                self.rules.append(CashRule(rule_name, cash_rules[rule_name]))

    def print_rules(self, title=True):
        """
        Return name of all cash rules defined in configuration file.
        """
        if title is True:
            return [i.menu_title for i in self.rules]
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

    Attributes:

        name (str): cash reconciliation rule name.

        id (int): rule element number.

        menu_title (str): cash reconciliation rule title.

        element_key (str): panel element key.

        elements (list): list of rule GUI element keys.

        permissions (str): permissions required to view the accounting method. Default: user.
    """

    def __init__(self, name, entry):
        """
        Arguments:

            name (str): bank reconciliation rule name.

            entry (dict): dictionary of optional and required cash reconciliation arguments.
        """

        self.name = name
        self.id = randint(0, 1000000000)
        self.element_key = '{NAME}_{ID}'.format(NAME=name, ID=self.id)
        self.elements = ['{NAME}_{ID}_{ELEM}'.format(NAME=self.name, ID=self.id, ELEM=i) for i in
                         ['Main', 'Cancel', 'Save', 'Next', 'FrameWidth', 'FrameHeight', 'PanelWidth', 'PanelHeight']]

        try:
            self.menu_title = entry['MenuTitle']
        except KeyError:
            self.menu_title = name

        try:
            self.permissions = entry['AccessPermissions']
        except KeyError:  # default permission for a cash rule is 'user'
            self.permissions = 'user'

        try:
            self.record_type = entry['RecordType']
        except KeyError:
            msg = 'Configuration Error: BankRule {RULE}: missing required parameter "RecordType"' \
                .format(RULE=name)
            mod_win2.popup_error(msg)
            sys.exit(1)

        try:
            self.import_table_entry = entry['ImportTable']
        except KeyError:
            self.import_table_entry = None

        try:
            self.record_layout_entry = entry['RecordLayout']
        except KeyError:
            self.record_layout_entry = None

