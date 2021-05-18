"""
REM mod_cash reconciliation configuration classes and objects.
"""

import sys
from random import randint

import REM.secondary as mod_win2
from REM.client import logger


class CashRules:
    """
    Class to store and manage program cash_reconciliation configuration settings.

    Arguments:

        cnfg (ConfigManager): program configuration class.

    Attributes:

        rules (list): List of CashRule objects.
    """

    def __init__(self, cash_param):
        self.name = 'Cash Reconciliation'

        self.rules = []
        if cash_param is not None:
            try:
                cash_name = cash_param['name']
            except KeyError:
                msg = 'CashRules: the parameter "name" is a required field'
                mod_win2.popup_error(msg)
                logger.error(msg)
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
                msg = 'CashRules {NAME}: the parameter "rules" is a required field'.format(NAME=self.name)
                mod_win2.popup_error(msg)
                logger.error(msg)
                sys.exit(1)

            for rule_name in cash_rules:
                self.rules.append(CashRule(rule_name, cash_rules[rule_name]))

    def print_rules(self, title=True):
        """
        Return name of all mod_cash rules defined in configuration file.
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
            logger.error('CashRules {NAME}: rule "{RULE}" not in list of configured mod_cash reconciliation rules. '
                         'Available rules are {ALL}'
                         .format(NAME=self.name, RULE=name, ALL=', '.join(self.print_rules())))
            rule = None
        else:
            rule = self.rules[index]

        return rule


class CashRule:
    """
    Class to store and manage a configured mod_cash reconciliation rule.

    Attributes:

        name (str): mod_cash reconciliation rule name.

        id (int): rule element number.

        menu_title (str): mod_cash reconciliation rule title.

        element_key (str): panel element key.

        elements (list): list of rule GUI element keys.

        permissions (str): permissions required to view the accounting method. Default: user.
    """

    def __init__(self, name, entry):
        """
        Arguments:

            name (str): mod_bank reconciliation rule name.

            entry (dict): dictionary of optional and required mod_cash reconciliation arguments.
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
        except KeyError:  # default permission for a mod_cash rule is 'user'
            self.permissions = 'user'

        try:
            self.record_type = entry['RecordType']
        except KeyError:
            msg = 'CashRule {RULE}: missing required parameter "RecordType"' \
                .format(RULE=name)
            mod_win2.popup_error(msg)
            logger.error(msg)
            sys.exit(1)

        try:
            self.import_table_entry = entry['ImportTable']
        except KeyError:
            self.import_table_entry = None

        try:
            self.record_layout_entry = entry['RecordLayout']
        except KeyError:
            self.record_layout_entry = None

