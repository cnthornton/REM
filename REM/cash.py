"""
REM cash reconciliation configuration classes and objects.
"""

from random import randint

from REM.client import logger


class CashRule:
    """
    Class to store and manage a configured cash reconciliation rule.

    Attributes:

        name (str): cash reconciliation rule name.

        id (int): rule element number.

        element_key (str): main panel element key.

        elements (list): list of rule GUI element keys.

        menu_title (str): rule menu title.

        menu_flags (dict): submenu flags that change the initial behavior of the rule.

        permissions (str): permissions required to view the accounting method. Default: user.
    """

    def __init__(self, name, entry):
        """
        Arguments:

            name (str): cash reconciliation rule name.

            entry (dict): dictionary of optional and required cash reconciliation arguments.
        """

        self.name = name
        self.id = randint(0, 1000000000)
        self.element_key = '{NAME}_{ID}'.format(NAME=name, ID=self.id)
        #self.elements = ['{NAME}_{ID}_{ELEM}'.format(NAME=self.name, ID=self.id, ELEM=i) for i in
        #                 ['Main', 'Cancel', 'Save', 'Next', 'FrameWidth', 'FrameHeight', 'PanelWidth', 'PanelHeight']]
        self.elements = []

        try:
            self.menu_title = entry['MenuTitle']
        except KeyError:
            self.menu_title = name

        try:
            self.menu_flags = entry['MenuFlags']
        except KeyError:
            self.menu_flags = None

        #try:
        #    self.permissions = entry['AccessPermissions']
        #except KeyError:  # default permission for a cash rule is 'user'
        #    self.permissions = 'user'
        try:
            permissions = entry['Permissions']
        except KeyError:
            self.permissions = {'view': None, 'create': None, 'edit': None}
        else:
            self.permissions = {'view': permissions.get('View', None),
                                'create': permissions.get('Create', None),
                                'edit': permissions.get('Edit', None),
                                }

        try:
            self.record_type = entry['RecordType']
        except KeyError:
            msg = 'CashRule {RULE}: missing required parameter "RecordType"' \
                .format(RULE=name)
            logger.error(msg)

            raise AttributeError(msg)

    def events(self):
        """
        Return a list of all events allowed under the rule.
        """
        return self.elements
