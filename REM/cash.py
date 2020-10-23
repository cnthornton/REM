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
        self.elements = ['Cancel', 'Save', 'TransNo', 'Date', 'Deposit', 'ExpenseTable', 'ExpenseTotals', 'AddExpense',
                         'RemoveExpense', 'EntryList', 'EntryTable', 'EntryTotals', 'FrameWidth', 'Height',
                         'InfoWidth', 'ExpenseWidth', 'EntryWidth', 'EntryHeight', 'InfoHeight', 'ExpenseHeight',
                         'HeaderHeight', 'Pad1Height', 'Pad2Height']

        try:
            self.title = adict['Title']
        except KeyError:
            self.title = name

        try:
            self.permissions = adict['Permissions']
        except KeyError:  # default permission for a cash rule is 'user'
            self.permissions = 'user'

        try:
            table = adict['DatabaseTable']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}: missing required field "DatabaseTable".').format(RULE=name)
            win2.popup_error(msg)
            sys.exit(1)
        else:
            self.table = table

        try:
            self.pkey = adict['PrimaryKey']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}: missing required field "PrimaryKey".').format(RULE=name)
            win2.popup_error(msg)
            sys.exit(1)

        try:
            table_columns = adict['TableColumns']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}: missing required field "TableColumns".').format(RULE=name)
            win2.popup_error(msg)
            sys.exit(1)
        else:
            self.table_columns = table_columns

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

            element['Value'] = element.get('DefaultValue', '')

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

        # Dynamic attributes
        self.df = pd.DataFrame(columns=table_columns)
        self.id = ''
        self.date = datetime.datetime.now().strftime(settings.format_date_str())
        self.amount = 0

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
        Generate a GUI layout for the cash rule.
        """
        if win_size:
            width, height = win_size
        else:
            width, height = (const.WIN_WIDTH, const.WIN_HEIGHT)

        # Rule parameters
        tbl_header = list(self.records.display_columns.keys())
        entry_header = list(self.records.reference_columns.keys())
        expense_header = list(self.expenses.display_columns.keys())

        tbl_title = self.records.display_header
        entry_title = self.records.reference_header
        expense_title = self.expenses.display_header

        trans_elements = self.info['Elements']

        # Element parameters
        header_col = input_col = const.HEADER_COL
        select_col = const.SELECT_TEXT_COL
        bg_col = const.ACTION_COL
        text_col = const.TEXT_COL

        font_h = const.HEADER_FONT
        font_main = const.MAIN_FONT
        bold_font = const.BOLD_FONT

        pad_el = const.ELEM_PAD
        pad_v = const.VERT_PAD
        pad_frame = const.FRAME_PAD

        # Element sizes
        layout_width = width - 120 if width >= 120 else width
        layout_height = height * 0.8
        frame_width = layout_width - 40
        frame_height = layout_height * 0.4
        pad_height = layout_height * 0.05

        expense_width = int((frame_width - 100) * 0.6)
        info_width = int((frame_width - 100) * 0.4)
        entry_width = int((frame_width - 120) * 0.62)
        list_width = int((frame_width - 120) * 0.38)

        bwidth = 1

        # Layout elements
        panel_title = self.title
        width_key = self.key_lookup('FrameWidth')
        layout_els = []

        title_layout = sg.Col([
            [sg.Canvas(key=width_key, size=(layout_width, 1), pad=(0, pad_v), visible=True,
                       background_color=header_col)],
            [sg.Text(panel_title, pad=((pad_frame, 0), (0, pad_v)), font=font_h, background_color=header_col)]],
            pad=(0, 0), justification='l', background_color=header_col, expand_x=True)

        # Panel heading layout
        trans_key = self.key_lookup('TransNo')
        date_key = self.key_lookup('Date')
        deposit_key = self.key_lookup('Deposit')
        header_layout = [
            [sg.Col([[sg.Text('Transaction Number:', pad=((0, pad_el), 0), font=bold_font, background_color=bg_col),
                      sg.Input('', key=trans_key, size=(16, 1), pad=((pad_el, pad_el), 0), border_width=0,
                               disabled_readonly_background_color=bg_col, disabled=True),
                      sg.Text('Date:', pad=((pad_el, pad_el), 0), font=bold_font, background_color=bg_col),
                      sg.Input('', key=date_key, size=(16, 1), pad=((pad_el, 0), 0), border_width=0,
                               disabled_readonly_background_color=bg_col, disabled=True)]],
                    justification='l', background_color=bg_col, expand_x=True),
             sg.Col([[sg.Canvas(size=(0, 0), visible=True, background_color=bg_col)]],
                    justification='c', background_color=bg_col, expand_x=True),
             sg.Col([[sg.Text('Deposit Amount:', pad=((pad_frame, pad_el), 0), font=bold_font, background_color=bg_col),
                      sg.Input('', key=deposit_key, size=(14, 1), pad=((pad_el, 0), 0), background_color=input_col,
                               border_width=1, disabled=True)]],
                    justification='r', background_color=bg_col)],
            [sg.HorizontalSeparator(pad=(0, pad_v), color=const.INACTIVE_COL)]]

        # Transaction Information frame layout
        info_keys = {i: self.key_lookup(i) for i in trans_elements}
        if len(info_keys) > 5:
            scroll = True
        else:
            scroll = False

        text_sizes = []
        for element_name in trans_elements:
            element = trans_elements[element_name]
            element_title = element['Title']
            text_sizes.append(len(element_title))
        text_size = max(text_sizes)

        info_layout = []
        for element_name in trans_elements:
            element = trans_elements[element_name]
            element_type = element['ElementType']
            element_title = element['Title']
            if element_type == 'input':
                info_layout.append([sg.Text('{}:'.format(element_title), size=(text_size, 1), pad=((0, pad_el), pad_el),
                                            background_color=bg_col),
                                    sg.Input('', key=info_keys[element_name], size=(15, 1), pad=((pad_el, 0), pad_el),
                                             background_color=input_col)])
            elif element_type == 'dropdown':
                try:
                    values = element['Values']
                except KeyError:
                    values = ['']

                try:
                    default = element['DefaultValue']
                except KeyError:
                    default = values[0]

                info_layout.append([sg.Text('{}:'.format(element_title), size=(text_size, 1), pad=((0, pad_el), pad_el),
                                            background_color=bg_col),
                                    sg.Combo(values, key=info_keys[element_name], size=(14, 1), default_value=default,
                                             pad=((pad_el, 0), pad_el), background_color=input_col)])

        # Expense frame layout
        expense_key = self.key_lookup('ExpenseTable')
        expense_totals_key = self.key_lookup('ExpenseTotals')
        add_key = self.key_lookup('AddExpense')
        minus_key = self.key_lookup('RemoveExpense')
        expense_layout = [
            [lo.create_table_layout([[]], expense_header, expense_key, events=True, pad=(0, 0), nrow=2,
                                    width=expense_width, add_key=add_key, delete_key=minus_key,
                                    table_name=expense_title, tooltip='Click on a row to edit the row fields')],
            [sg.Col([
                [sg.Text('Total:', pad=((0, pad_el), (pad_v, 0)), background_color=bg_col, font=bold_font),
                 sg.Input('', key=expense_totals_key, size=(14, 1), pad=((pad_el, 0), (pad_v, 0)),
                          background_color=input_col, disabled=True)]
            ], background_color=bg_col, justification='r')]]

        # Entries frame layout
        list_key = self.key_lookup('EntryList')
        tbl_key = self.key_lookup('EntryTable')
        totals_key = self.key_lookup('EntryTotals')
        entries_layout = [
            [sg.Col([
                [lo.create_table_layout([[]], entry_header, list_key, events=True, pad=((0, pad_frame), 0),
                                        nrow=6, width=list_width, table_name=entry_title,
                                        tooltip='Double-click on row to add to table')]
            ], pad=(0, 0), justification='l', vertical_alignment='t', background_color=bg_col),
                sg.Col([
                    [lo.create_table_layout([[]], tbl_header, tbl_key, events=True, pad=(0, 0), nrow=6,
                                            width=entry_width, table_name=tbl_title, delete_key='',
                                            tooltip='Click on a row to edit the row fields')],
                    [sg.Col([
                        [sg.Text('Total:', pad=((0, pad_el), (pad_v, 0)), background_color=bg_col, font=bold_font),
                         sg.Input('', key=totals_key, size=(14, 1), pad=((pad_el, 0), (pad_v, 0)), border_width=bwidth,
                                  background_color=input_col, disabled=True)]],
                        background_color=bg_col, justification='r')]
                ], pad=((pad_frame, 0), 0), justification='r', vertical_alignment='t', background_color=bg_col)]]

        # Main panel layout
        info_w_key = self.key_lookup('InfoWidth')
        expense_w_key = self.key_lookup('ExpenseWidth')
        info_h_key = self.key_lookup('InfoHeight')
        expense_h_key = self.key_lookup('ExpenseHeight')
        entry_w_key = self.key_lookup('EntryWidth')
        entry_h_key = self.key_lookup('EntryHeight')
        pad1_h_key = self.key_lookup('Pad1Height')
        pad2_h_key = self.key_lookup('Pad2Height')
        header_h_key = self.key_lookup('HeaderHeight')
        main_layout = [[title_layout],
                       [sg.Canvas(key=header_h_key, size=(0, frame_height * 0.3), background_color=bg_col),
                        sg.Col(header_layout, pad=(pad_frame, 0), justification='l',
                               background_color=bg_col, vertical_alignment='c', expand_x=True)],
                       [sg.Frame('Transaction Info', [
                           [sg.Canvas(key=info_w_key, size=(info_width, 0), pad=(0, pad_v), visible=True,
                                      background_color=bg_col)],
                           [sg.Canvas(key=info_h_key, size=(0, frame_height), pad=(0, 0), visible=True,
                                      background_color=bg_col),
                            sg.Col(info_layout, pad=(pad_frame, pad_v), background_color=bg_col,
                                   vertical_alignment='t', expand_y=True, expand_x=True, vertical_scroll_only=True,
                                   scrollable=scroll)]],
                                 pad=(pad_frame, 0), border_width=bwidth, background_color=bg_col,
                                 title_color=select_col, element_justification='l', relief='solid'),
                        sg.Frame('Expenses', [
                            [sg.Canvas(key=expense_w_key, size=(frame_width, 0), pad=(0, 0), visible=True,
                                       background_color=bg_col)],
                            [sg.Canvas(key=expense_h_key, size=(0, frame_height), pad=(0, pad_v), visible=True,
                                       background_color=bg_col),
                             sg.Col(expense_layout, pad=(pad_frame, pad_v), background_color=bg_col)]],
                                 pad=(pad_frame, 0), border_width=bwidth, background_color=bg_col,
                                 title_color=select_col, relief='solid')],
                       [sg.Canvas(key=pad1_h_key, size=(0, pad_height), background_color=bg_col)],
                       [sg.Frame('Records', [
                           [sg.Canvas(key=entry_w_key, size=(layout_width, 0), pad=(0, 0), visible=True,
                                      background_color=bg_col)],
                           [sg.Canvas(key=entry_h_key, size=(0, frame_height), pad=(0, pad_v), visible=True,
                                      background_color=bg_col),
                            sg.Col(entries_layout, pad=(pad_frame, pad_v), background_color=bg_col)],
                       ],
                                 pad=(pad_frame, 0), border_width=bwidth, background_color=bg_col,
                                 title_color=select_col, relief='solid')],
                       [sg.Canvas(key=pad2_h_key, size=(0, pad_height), background_color=bg_col)]]

        layout_els.append([sg.Frame('', main_layout, relief='raised', background_color=bg_col)])

        cancel_key = self.key_lookup('Cancel')
        save_key = self.key_lookup('Save')
        bttn_layout = [sg.Col([[lo.B2('Cancel', key=cancel_key, pad=(0, (pad_v, pad_frame)),
                                      tooltip='Return to home screen')]], justification='l', expand_x=True),
                       sg.Col([[sg.Canvas(size=(0, 0), visible=True)]], justification='c', expand_x=True),
                       sg.Col([[lo.B2('Save', key=save_key, pad=(0, (pad_v, pad_frame)), disabled=True,
                                      tooltip='Save transaction')]], justification='r')]
        layout_els.append(bttn_layout)

        # Pane elements must be columns
        layout = sg.Col([[sg.Col(layout_els, vertical_alignment='t')]], key=self.element_key, visible=False)

        return layout

    def resize_elements(self, window, win_size: tuple = None):
        """
        Resize Audit Rule GUI elements based on window size
        """
        if win_size:
            width, height = win_size
        else:
            width, height = (const.WIN_WIDTH, const.WIN_HEIGHT)

        # Resize space between action buttons
        # For every five-pixel increase in window size, increase panel size by one
        layout_pad = 120
        width_diff = width - const.WIN_WIDTH
        layout_pad = layout_pad + (width_diff / 5)

        layout_width = width - layout_pad if layout_pad > 0 else width
        layout_height = height * 0.75

        width_key = self.key_lookup('FrameWidth')
        window[width_key].set_size((layout_width, None))

        # Resize frames
        frame_width = layout_width - 40

        expense_width = int((frame_width - 100) * 0.6)
        info_width = int((frame_width - 100) * 0.4)
        entry_width = int((frame_width - 120) * 0.62)
        list_width = int((frame_width - 120) * 0.38)

        info_w_key = self.key_lookup('InfoWidth')
        expense_w_key = self.key_lookup('ExpenseWidth')
        entry_w_key = self.key_lookup('EntryWidth')
        window[info_w_key].set_size((info_width, None))
        window[expense_w_key].set_size((expense_width, None))
        window[entry_w_key].set_size((entry_width, None))

        info_height = expense_height = layout_height * 0.25
        entry_height = layout_height * 0.35
        header_height = layout_height * 0.12
        pad_height = layout_height * 0.05

        entry_h_key = self.key_lookup('EntryHeight')
        info_h_key = self.key_lookup('InfoHeight')
        expense_h_key = self.key_lookup('ExpenseHeight')
        header_h_key = self.key_lookup('HeaderHeight')
        pad1_h_key = self.key_lookup('Pad1Height')
        pad2_h_key = self.key_lookup('Pad2Height')
        window[header_h_key].set_size((None, header_height))
        window[entry_h_key].set_size((None, entry_height))
        window[info_h_key].set_size((None, info_height))
        window[expense_h_key].set_size((None, expense_height))
        window[pad1_h_key].set_size((None, pad_height))
        window[pad2_h_key].set_size((None, pad_height))

        # Expand transaction info elements
        trans_elements = self.info['Elements']
        info_keys = {i: self.key_lookup(i) for i in trans_elements}
        for element_name in trans_elements:
            element_key = info_keys[element_name]
            window[element_key].expand(expand_x=True, expand_row=True)

        # Reset table sizes
        # Add one row for every 100-pixel increase in window height
        height_diff = int(height - const.WIN_HEIGHT)
        nrows = 4 + int(height_diff / 100) if int(height_diff / 100) > - 2 else 4
        print(height_diff, nrows)
        #        expense_width = frame_width - 60
        #        entry_width = (frame_width - 120) / 2

        # Expenses table
        expenses_key = self.key_lookup('ExpenseTable')
        expense_columns = self.expenses.display_columns
        expense_header = list(expense_columns.keys())
        lengths = dm.calc_column_widths(expense_header, width=expense_width, pixels=True)
        for col_index, col_name in enumerate(expense_header):
            col_width = lengths[col_index]
            window[expenses_key].Widget.column(col_name, width=col_width)

        window[expenses_key].expand((True, True))
        window[expenses_key].table_frame.pack(expand=True, fill='both')

        # Records table
        records_key = self.key_lookup('EntryTable')
        records_columns = self.records.display_columns
        records_header = list(records_columns.keys())
        lengths = dm.calc_column_widths(records_header, width=entry_width, pixels=True)
        for col_index, col_name in enumerate(records_header):
            col_width = lengths[col_index]
            window[records_key].Widget.column(col_name, width=col_width)

        window[records_key].expand((True, True))
        window[records_key].table_frame.pack(expand=True, fill='both')

        list_key = self.key_lookup('EntryList')
        list_columns = self.records.reference_columns
        list_header = list(list_columns.keys())
        lengths = dm.calc_column_widths(list_header, width=list_width, pixels=True)
        for col_index, col_name in enumerate(list_header):
            col_width = lengths[col_index]
            window[list_key].Widget.column(col_name, width=col_width)

        window[list_key].expand((True, True))
        window[list_key].table_frame.pack(expand=True, fill='both')

        window[records_key].update(num_rows=nrows)
        window[list_key].update(num_rows=nrows)
        window[expenses_key].update(num_rows=2)

    def reset_rule(self, window, current: bool = False):
        """
        reset rule to default.
        """
        win_width, win_height = window.size

        current_key = self.element_key

        # Disable current panel
        window[current_key].update(visible=False)
        window['-HOME-'].update(visible=True)

        # Reset rule attributes
        self.reset_attributes()

        if current:
            window['-HOME-'].update(visible=False)
            window[current_key].update(visible=True)

            next_key = current_key
        else:
            next_key = '-HOME-'

        return next_key

    def reset_attributes(self):
        """
        Reset rule attributes.
        """
        pass


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
            table_columns = edict['TableColumns']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}, Expenses: missing required field "TableColumns".') \
                .format(RULE=rule_name)
            win2.popup_error(msg)
            sys.exit(1)
        else:
            self.table_columns = table_columns

        try:
            self.display_header = edict['DisplayHeader']
        except KeyError:
            self.display_header = ''

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

        # Dynamic attributes
        self.df = pd.DataFrame(columns=table_columns)


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
            msg = _('Configuration Error: rule {RULE}, Records: missing required field "DatabaseTable".') \
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
            table_columns = rdict['TableColumns']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}, Records: missing required field "TableColumns".') \
                .format(RULE=rule_name)
            win2.popup_error(msg)
            sys.exit(1)
        else:
            self.table_columns = table_columns

        try:
            self.reference_header = rdict['ReferenceHeader']
        except KeyError:
            self.reference_header = ''

        try:
            reference_columns = rdict['ReferenceColumns']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}, Records: missing required field "TableColumns".') \
                .format(RULE=rule_name)
            win2.popup_error(msg)
            sys.exit(1)

        for column_alias in reference_columns:
            column_name = reference_columns[column_alias]
            if column_name not in table_columns:
                win2.popup_notice('Configuration Warning: rule {RULE}, Records: {COL} not in list of table columns'
                                  .format(RULE=rule_name, COL=column_name))
                del reference_columns[column_alias]
        self.reference_columns = reference_columns

        try:
            self.display_header = rdict['DisplayHeader']
        except KeyError:
            self.display_header = ''

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

        # Dynamic attributes
        self.df = pd.DataFrame(columns=table_columns)
        self.entries = []
