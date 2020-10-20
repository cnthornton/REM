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
        cash_param = cnfg.cash_rules

        self.rules = []
        if cash_param is not None:
            try:
                cash_name = cash_param['name']
            except KeyError:
                win2.popup_error('Error: cash_rules: the parameter "name" is a required field')
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
                win2.popup_error('Error: cash_rules: the parameter "rules" is a required field')
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
        self.elements = ['Cancel', 'Save', 'Create', 'Edit', 'TransNo', 'Date', 'Deposit', 'Expense', 'ExpenseTotals',
                         'EntryList', 'EntryTable', 'EntryTotals']

        try:
            self.title = adict['Title']
        except KeyError:
            self.title = name

        try:
            self.permissions = adict['Permissions']
        except KeyError:  # default permission for a cash rule is 'user'
            self.permissions = 'user'

        try:
            trans_info = adict['TransactionInfo']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}: missing required field "TransactionInfo".').format(RULE=name)
            win2.popup_error(msg)
            sys.exit(1)

        msg = _('Configuration Error: rule {RULE}, TransactionInfo: missing required parameter "{PARAM}"')
        if 'Title' not in trans_info:
            trans_info['Title'] = 'Transaction Information'
        if 'Elements' not in trans_info:
            win2.popup_error(msg.format(RULE=name, PARAM="Elements"))
        for element_name in trans_info['Elements']:
            element = trans_info['Elements'][element_name]

            self.elements.append(element_name)

            if 'Title' not in element:
                element['Title'] = element_name
            if 'ElementType' not in element:
                msg = _('Configuration Error: rule {RULE}, TransactionInfo: missing required field "ElementType" for '
                        'element "{ELEM}".').format(RULE=name, ELEM=element_name)
                win2.popup_error(msg)
                sys.exit(1)

        self.info = trans_info

        try:
            expenses = adict['Expenses']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}: missing required field "Expenses".').format(RULE=name)
            win2.popup_error(msg)
            sys.exit(1)
        else:
            self.expenses = CashExpenses(name, expenses)

        try:
            records = adict['Records']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}: missing required field "Records".').format(RULE=name)
            win2.popup_error(msg)
            sys.exit(1)
        else:
            self.records = CashRecords(name, records)

    def key_lookup(self, element):
        """
        Lookup element key for input control element.
        """
        if element in self.elements:
            key = lo.as_key('{} {}'.format(self.name, element))
        else:
            key = None

        return key

    def layout(self, win_size: tuple = None):
        """
        Generate a GUI layout for the audit rule.
        """
        if win_size:
            width, height = win_size
        else:
            width, height = (const.WIN_WIDTH, const.WIN_HEIGHT)

        # Rule parameters
        tbl_header = list(self.records.display_columns.keys())
        expense_header = list(self.expenses.display_columns.keys())
        trans_elements = self.info['Elements']

        # Element parameters
        header_col = const.HEADER_COL
        inactive_col = const.INACTIVE_COL
        bg_col = const.ACTION_COL
        default_col = const.DEFAULT_COL
        text_col = const.TEXT_COL
        select_col = const.SELECT_TEXT_COL
        font_h = const.HEADER_FONT
        font_main = const.MAIN_FONT

        pad_el = const.ELEM_PAD
        pad_v = const.VERT_PAD
        pad_frame = const.FRAME_PAD

        layout_width = width - 120 if width >= 200 else width
        spacer = layout_width - 124 if layout_width > 124 else 0
        bwidth = 0.5

        # Layout elements
        panel_title = self.title
        layout_els = [[sg.Col([[sg.Text(panel_title, pad=(0, (pad_v, pad_frame)), font=font_h)]],
                              justification='c', element_justification='c')]]

        # Panel heading layout
        trans_key = self.key_lookup('TransNo')
        date_key = self.key_lookup('Date')
        deposit_key = self.key_lookup('Deposit')
        header_layout = [[sg.Text('Transaction Number'), sg.Input('', key=trans_key, border_width=0),
                          sg.Text('Date'), sg.Input('', key=date_key, border_width=0),
                          sg.Text('Deposit Amount'), sg.Input('', key=deposit_key, border_width=bwidth)]]

        # Transaction Information frame layout
        info_keys = {i: self.key_lookup(i) for i in trans_elements}
        info_layout = []
        for element_name in trans_elements:
            element = trans_elements[element_name]
            element_type = element['ElementType']
            element_title = element['Title']
            if element_type == 'input':
                info_layout += [sg.Text('{}:'.format(element_title), pad=((0, pad_el), 0), background_color=bg_col),
                                sg.Input('', key=info_keys[element_name], pad=((pad_el, 0), 0),
                                         background_color=select_col)]
            elif element_type == 'dropdown':
                try:
                    values = element['Values']
                except KeyError:
                    values = ['']

                try:
                    default = element['DefaultValue']
                except KeyError:
                    default = values[0]

                info_layout += [sg.Text('{}:'.format(element_title), pad=((0, pad_el), 0), background_color=bg_col),
                                sg.Combo(values, key=info_keys[element_name], default_value=default,
                                         pad=((pad_el, 0), 0), background_color=select_col)]

        # Expense frame layout
        expense_key = self.key_lookup('Expense')
        expense_totals_key = self.key_lookup('ExpenseTotals')
        add_key = self.key_lookup('Add')
        expense_layout = [[lo.create_table_layout([[]], expense_header, expense_key, events=True, pad=(0, 0),
                                                  nrow=4, width=layout_width * 0.95,
                                                  tooltip='Click on a row to edit the row fields')],
                          [sg.Text('Totals:', pad=((0, pad_el), pad_el), background_color=bg_col),
                           sg.Input('', key=expense_totals_key, pad=((pad_el, 0), pad_el), background_color=select_col),
                           lo.B2('Add', key=add_key)]]

        # Entries frame layout
        list_key = self.key_lookup('EntryList')
        tbl_key = self.key_lookup('EntryTable')
        totals_key = self.key_lookup('EntryTotals')
        entries_layout = [[
            sg.Col([
                [sg.Listbox(values=[], key=list_key, size=(25, 8), pad=(0, 0), font=font_main,
                            background_color=bg_col, bind_return_key=True,
                            tooltip='Double-click on a column name to add the column to the table')]],
                pad=(pad_frame, 0), justification='l', background_color=bg_col),
            sg.Col([
                [lo.create_table_layout([[]], tbl_header, tbl_key, events=True, pad=(0, 0), nrow=4,
                                        width=layout_width * 0.65, tooltip='Click on a row to edit the row fields')],
                [sg.Text('Total:', pad=((0, pad_el), pad_el), background_color=bg_col),
                 sg.Input('', key=totals_key, pad=((pad_el, 0), pad_el), border_width=bwidth,
                          background_color=select_col)]],
                pad=(pad_frame, 0), justification='r', background_color=bg_col)]]

        # Main panel layout
        main_layout = [[sg.Col(header_layout, pad=(pad_frame, pad_frame), justification='l', background_color=bg_col)],
                       [sg.Frame('Transaction Info', [
                           [sg.Canvas(size=(layout_width, 0), pad=(0, pad_v), visible=True, background_color=bg_col)],
                           [sg.Col([info_layout], pad=(pad_frame, 0), background_color=bg_col)],
                           [sg.Canvas(size=(layout_width, 0), pad=(0, pad_v), visible=True, background_color=bg_col)]
                       ],
                                 pad=(pad_frame, pad_frame), border_width=bwidth, background_color=bg_col,
                                 title_color=select_col, relief='groove')],
                       [sg.Frame('Expenses', [
                           [sg.Canvas(size=(layout_width, 0), pad=(0, pad_v), visible=True,
                                      background_color=bg_col)],
                           [sg.Col(expense_layout, pad=(pad_frame, 0), background_color=bg_col)],
                           [sg.Canvas(size=(layout_width, 0), pad=(0, pad_v), visible=True,
                                      background_color=bg_col)]
                       ],
                                 pad=(pad_frame, pad_frame), border_width=bwidth, background_color=bg_col,
                                 title_color=select_col,
                                 relief='groove')],
                       [sg.Frame('Transaction Entries', [
                           [sg.Canvas(size=(layout_width, 0), pad=(0, pad_v), visible=True,
                                      background_color=bg_col)],
                           [sg.Col(entries_layout, pad=(pad_frame, 0), background_color=bg_col)],
                           [sg.Canvas(size=(layout_width, 0), pad=(0, pad_v), visible=True,
                                      background_color=bg_col)]
                       ],
                                 pad=(pad_frame, pad_frame), border_width=bwidth, background_color=bg_col,
                                 title_color=select_col,
                                 relief='groove')]]

        layout_els.append([sg.Col(main_layout, background_color=bg_col, vertical_alignment='c')])

        cancel_key = self.key_lookup('Cancel')
        save_key = self.key_lookup('Save')
        create_key = self.key_lookup('Create')
        edit_key = self.key_lookup('Edit')
        fill_key = self.key_lookup('Fill')
        bttn_layout = [lo.B2('Create', key=create_key, pad=((0, pad_el), (pad_v, 0)), tooltip=''),
                       lo.B2('Edit', key=edit_key, pad=((pad_el, 0), (pad_v, 0)), tooltip='Start audit'),
                       sg.Canvas(key=fill_key, size=(spacer, 0), visible=True),
                       lo.B2('Cancel', key=cancel_key, pad=((0, pad_el), (pad_v, 0)), tooltip='Cancel current action'),
                       lo.B2('Save', key=save_key, pad=(0, (pad_v, 0)), disabled=True,
                             tooltip='Finalize audit and generate summary report')]
        layout_els.append(bttn_layout)

        # Pane elements must be columns
        layout = sg.Col(layout_els, key=self.element_key, visible=False)

        return layout


class CashExpenses:
    """
    Class to store and manage cash expenses.

    Arguments:

        rule_name (str): cash reconciliation rule name.

        edict (dict): dictionary of configured optional and required cash expense arguments.

    Attributes:

        rule_name (str): cash reconciliation rule name.

        title (str): cash expense title.

        element_key (str): GUI element key.
    """

    def __init__(self, rule_name, edict):

        self.rule_name = rule_name
        self.element_key = lo.as_key('{} Expenses'.format(rule_name))

        try:
            self.title = edict['Title']
        except KeyError:
            self.title = '{} Expenses'.format(rule_name)

        try:
            self.database = edict['DatabaseTable']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}, Expenses: missing required field "DatabaseTable".') \
                .format(RULE=rule_name)
            win2.popup_error(msg)
            sys.exit(1)

        try:
            self.pkey = edict['PrimaryKey']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}, Expenses: missing required field "PrimaryKey".') \
                .format(RULE=rule_name)
            win2.popup_error(msg)
            sys.exit(1)

        try:
            self.table_columns = edict['TableColumns']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}, Expenses: missing required field "TableColumns".') \
                .format(RULE=rule_name)
            win2.popup_error(msg)
            sys.exit(1)

        try:
            self.display_columns = edict['DisplayColumns']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}, Expenses: missing required field "DisplayColumns".') \
                .format(RULE=rule_name)
            win2.popup_error(msg)
            sys.exit(1)

        try:
            self.totals_column = edict['TotalColumn']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}, Expenses: missing required field "TotalColumn".') \
                .format(RULE=rule_name)
            win2.popup_error(msg)
            sys.exit(1)


class CashRecords:
    """
    Class to store and manage included cash audit records.

    Arguments:

        rule_name (str): cash reconciliation rule name.

        rdict (dict): dictionary of configured optional and required cash records arguments.

    Attributes:

        rule_name (str): cash reconciliation rule name.

        title (str): cash records title.

        element_key (str): GUI element key.
    """

    def __init__(self, rule_name, rdict):

        self.rule_name = rule_name
        self.element_key = lo.as_key('{} Expenses'.format(rule_name))

        try:
            self.title = rdict['Title']
        except KeyError:
            self.title = '{} Expenses'.format(rule_name)

        try:
            self.database = rdict['DatabaseTable']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}, Records: missing required field "DatabaseTable".')\
                .format(RULE=rule_name)
            win2.popup_error(msg)
            sys.exit(1)

        try:
            self.pkey = rdict['PrimaryKey']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}, Records: missing required field "PrimaryKey".') \
                .format(RULE=rule_name)
            win2.popup_error(msg)
            sys.exit(1)

        try:
            self.table_columns = rdict['TableColumns']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}, Records: missing required field "TableColumns".') \
                .format(RULE=rule_name)
            win2.popup_error(msg)
            sys.exit(1)

        try:
            self.display_columns = rdict['DisplayColumns']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}, Records: missing required field "DisplayColumns".') \
                .format(RULE=rule_name)
            win2.popup_error(msg)
            sys.exit(1)

        try:
            self.totals_column = rdict['TotalColumn']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}, Records: missing required field "TotalColumn".') \
                .format(RULE=rule_name)
            win2.popup_error(msg)
            sys.exit(1)

