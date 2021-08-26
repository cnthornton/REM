"""
REM mod_cash reconciliation configuration classes and objects.
"""

import sys
from random import randint

import REM.secondary as mod_win2
from REM.client import logger


class CashRule:
    """
    Class to store and manage a configured mod_cash reconciliation rule.

    Attributes:

        name (str): mod_cash reconciliation rule name.

        id (int): rule element number.

        element_key (str): panel element key.

        elements (list): list of rule GUI element keys.

        menu_title (str): mod_cash reconciliation rule title.

        menu_flags (dict): submenu flags that change the initial behavior of the rule.

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
            self.menu_flags = entry['MenuFlags']
        except KeyError:
            self.menu_flags = None

        try:
            self.permissions = entry['AccessPermissions']
        except KeyError:  # default permission for a cash rule is 'user'
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

