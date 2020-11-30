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

import REM.constants as const
import REM.data_manipulation as dm
import REM.layouts as lo
import REM.parameters as param_els
import REM.secondary as win2
from REM.config import configuration, current_tbl_pkeys, settings


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
        self.elements = ['Cancel', 'Save', 'ID', 'Deposit', 'Date', 'ExpenseTable', 'ExpenseTotals', 'AddExpense',
                         'RemoveExpense', 'EntryTable', 'EntryTotals', 'AddEntry', 'RemoveEntry',
                         'FrameWidth', 'FrameHeight', 'PanelHeight', 'Main']

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
            id_entry = adict['ID']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}: missing required field "ID".').format(RULE=name)
            win2.popup_error(msg)
            sys.exit(1)
        msg = 'Configuration Error: rule {RULE}: missing required ID entry field "{FIELD}"'
        if 'Column' not in id_entry:
            win2.popup_error(msg.format(RULE=name, FIELD='Column'))
            sys.exit(1)
        if 'Format' not in id_entry:
            win2.popup_error(msg.format(RULE=name, FIELD='Format'))
            sys.exit(1)
        else:
            id_entry['Format'] = re.findall(r'\{(.*?)\}', id_entry['Format'])
        if 'Description' not in id_entry:
            id_entry['Description'] = 'ID'
        id_entry['Value'] = None
        self.id = id_entry

        try:
            date_entry = adict['Date']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}: missing required field "Date".').format(RULE=name)
            win2.popup_error(msg)
            sys.exit(1)
        msg = 'Configuration Error: rule {RULE}: missing required Date entry field "{FIELD}"'
        if 'Column' not in date_entry:
            win2.popup_error(msg.format(RULE=name, FIELD='Column'))
            sys.exit(1)
        if 'DateFormat' not in date_entry:
            win2.popup_error(msg.format(RULE=name, FIELD='DateFormat'))
            sys.exit(1)
        else:
            date_entry['Format'] = settings.format_date_str(date_entry['DateFormat'])
        if 'Description' not in date_entry:
            date_entry['Description'] = 'Date'
        date_entry['Value'] = None
        self.date = date_entry

        try:
            deposit_entry = adict['Deposit']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}: missing required field "Deposit".').format(RULE=name)
            win2.popup_error(msg)
            sys.exit(1)
        msg = 'Configuration Error: rule {RULE}: missing required Deposit entry field "{FIELD}"'
        if 'Column' not in deposit_entry:
            win2.popup_error(msg.format(RULE=name, Field='Column'))
            sys.exit(1)
        if 'Description' not in deposit_entry:
            deposit_entry['Description'] = 'Deposit Amount'
        deposit_entry['Value'] = None
        self.deposit = deposit_entry

        try:
            table_columns = adict['TableColumns']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}: missing required field "TableColumns".').format(RULE=name)
            win2.popup_error(msg)
            sys.exit(1)
        else:
            self.columns = table_columns

        try:
            display_columns = adict['DisplayColumns']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}: missing required field "DisplayColumns".').format(RULE=name)
            win2.popup_error(msg)
            sys.exit(1)
        else:
            self.display_columns = display_columns

        try:
            import_params = adict['ImportParameters']
        except KeyError:
            self.import_parameters = {}
        else:
            self.import_parameters = import_params

        self.parameters = []
        try:
            params = adict['RuleParameters']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}: missing required field "RuleParameters".').format(RULE=name)
            win2.popup_error(msg)
            sys.exit(1)

        for param in params:
            cdict = params[param]
            self.elements.append(param)

            try:
                param_layout = cdict['ElementType']
            except KeyError:
                msg = 'Configuration Error: rule {RULE}, RuleParameters, {PARAM}: missing required field "{FIELD}"' \
                    .format(RULE=name, PARAM=param, FIELD='ElementType')
                win2.popup_error(msg)
                sys.exit(1)

            if param_layout == 'dropdown':
                self.parameters.append(param_els.AuditParameterCombo(name, param, cdict))
            elif param_layout == 'input':
                self.parameters.append(param_els.AuditParameterInput(name, param, cdict))
            elif param_layout == 'date':
                self.parameters.append(param_els.AuditParameterDate(name, param, cdict))
            elif param_layout == 'date_range':
                self.parameters.append(param_els.AuditParameterDateRange(name, param, cdict))
            else:
                msg = 'Configuration Error: rule {RULE}, RuleParameters, {PARAM}: unknown parameter type {TYPE}' \
                    .format(RULE=name, PARAM=param, TYPE=param_layout)
                win2.popup_error(msg)
                sys.exit(1)

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

        try:
            sdict = adict['Summary']
        except KeyError:
            msg = 'Configuration Error: rule {RULE}: missing required field "Summary"'.format(RULE=name)
            win2.popup_error(msg)
            sys.exit(1)

        self.summary = CashSummaryPanel(name, sdict)

        try:
            self.aliases = adict['Aliases']
        except KeyError:
            self.aliases = {}

        self.panel_keys = {0: self.key_lookup('Main'), 1: self.summary.element_key}
        self.current_panel = 0
        self.first_panel = 0
        self.last_panel = 1

        # Dynamic attributes
        header = [dm.colname_from_query(i) for i in table_columns]
        self.df = pd.DataFrame(columns=header)

        self.exists = False

    def key_lookup(self, element):
        """
        Lookup element key for input control element.
        """
        if element in self.elements:
            key = lo.as_key('{} {}'.format(self.name, element))
        else:
            key = None

        return key

    def fetch_parameter(self, name, by_key: bool = False, by_type: bool = False):
        """
        """
        if by_key and by_type:
            print('Warning: rule {NAME}, parameter {PARAM}: the "by_key" and "by_type" arguments are mutually '
                  'exclusive. Defaulting to "by_key".'.format(NAME=self.name, PARAM=name))
            by_type = False

        if by_key:
            names = [i.element_key for i in self.parameters]
        elif by_type:
            names = [i.type for i in self.parameters]
        else:
            names = [i.name for i in self.parameters]

        try:
            index = names.index(name)
        except IndexError:
            param = None
        else:
            param = self.parameters[index]

        return param

    def reset_rule(self, window, current: bool = False):
        """
        reset rule to default.
        """
        panel_key = self.element_key
        current_key = self.panel_keys[self.current_panel]

        # Reset current paneltable.remove(current_rule.id['Value'])
        self.current_panel = 0

        # Disable current panel
        window[current_key].update(visible=False)
        window[self.panel_keys[self.first_panel]].update(visible=True)
        window[panel_key].update(visible=False)
        window['-HOME-'].update(visible=True)

        # Reset rule attributes
        self.reset_attributes()

        # Reset rule parameters
        self.reset_parameters(window)

        if current:
            window['-HOME-'].update(visible=False)
            window[panel_key].update(visible=True)
            window[self.panel_keys[self.first_panel]].update(visible=True)

            next_key = panel_key
        else:
            next_key = '-HOME-'

        return next_key

    def reset_parameters(self, window):
        """
        Reset rule item parameter values.
        """
        # Reset rule parameters
        for param in self.parameters:
            param.reset_parameter()

            if not param.hidden:
                param_key = param.element_key
                window[param_key].update(value='')

    def reset_attributes(self):
        """
        Reset rule attributes.
        """
        header = [dm.colname_from_query(i) for i in self.columns]
        self.df = pd.DataFrame(columns=header)

        self.id['Value'] = None
        self.date['Value'] = None

        self.exists = False

        self.records.reset_dynamic_attributes()
        self.expenses.reset_dynamic_attributes()

    def remove_unsaved_keys(self):
        """
        Remove unsaved IDs from the table IDs lists.
        """
        # Remove transaction ID from list if not already saved in database
        if self.exists is False:  # newly created transaction
            # Remove transaction ID from list of transaction IDs
            try:
                current_tbl_pkeys[self.table].remove(self.id['Value'])
            except ValueError:
                print('Warning: attempting to remove non-existent ID "{ID}" from the list of database '
                      'table {TBL} IDs'.format(ID=self.id['Value'], TBL=self.expenses.table))
            else:
                print('Info: removed ID {ID} from the list of database table {TBL} IDs'
                      .format(ID=self.id['Value'], TBL=self.table))

        # Remove those expense IDs not already saved in the database from the list
        all_expenses = self.expenses.df[self.expenses.pkey].values.tolist()
        existing_expenses = self.expenses.import_df[self.expenses.pkey].values.tolist()
        created_expenses = set(all_expenses).difference(set(existing_expenses))
        for expense_id in created_expenses:
            try:
                current_tbl_pkeys[self.expenses.table].remove(expense_id)
            except ValueError:
                print('Warning: attempting to remove non-existent ID "{ID}" from the list of database '
                      'table {TBL} IDs'.format(ID=expense_id, TBL=self.expenses.table))
                continue
            else:
                print('Info: removed ID {ID} from the list of database table {TBL} IDs'
                      .format(ID=expense_id, TBL=self.expenses.table))

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
        expense_header = list(self.expenses.display_columns.keys())

        tbl_title = self.records.title
        expense_title = self.expenses.title

        params = self.parameters

        # Element parameters
        header_col = const.HEADER_COL2
        input_col = const.INPUT_COL
        bg_col = const.ACTION_COL
        text_col = const.TEXT_COL

        font_h = const.HEADER_FONT
        font_main = const.MAIN_FONT
        bold_font = const.BOLD_FONT
        bold_l_font = const.BOLD_MID_FONT

        pad_el = const.ELEM_PAD
        pad_v = const.VERT_PAD
        pad_frame = const.FRAME_PAD

        # Element sizes
        layout_width = width - 120 if width >= 120 else width
        tbl_width = layout_width - 42

        layout_height = height * 0.8
        panel_height = layout_height * 0.7

        bwidth = 1

        # Layout elements
        panel_title = self.title
        width_key = self.key_lookup('FrameWidth')
        layout_els = []

        title_layout = [[sg.Col([
            [sg.Canvas(key=width_key, size=(layout_width, 1), pad=(0, pad_v), visible=True,
                       background_color=header_col)],
            [sg.Text(panel_title, pad=((pad_frame, 0), (0, pad_v)), font=font_h, background_color=header_col)]],
            pad=(0, 0), justification='l', background_color=header_col, expand_x=True)]]

        # Panel heading layout
        right_elements = []
        left_elements = []
        for param in params:
            if param.hidden is True:
                continue

            element_layout = param.layout()
            if param.justification == 'right':
                right_elements += element_layout
            else:
                left_elements += element_layout

        deposit_key = self.key_lookup('Deposit')
        deposit_layout = [sg.Text('{}:'.format(self.deposit['Description']), pad=((0, pad_el), 0), justification='r',
                                  font=bold_font, background_color=bg_col),
                          sg.Text('', key=deposit_key, size=(14, 1), enable_events=True, pad=((0, pad_el), 0),
                                  font=font_main, background_color=bg_col, border_width=bwidth, relief='sunken')]
        right_elements += deposit_layout

        id_key = self.key_lookup('ID')
        id_title = self.id['Description']
        header_layout = [
            [sg.Col([[sg.Text('{}:'.format(id_title), pad=((pad_el*2, pad_el), pad_el*2), font=bold_l_font,
                              background_color=bg_col),
                      sg.Text('', key=id_key, size=(20, 1), pad=((pad_el, pad_el*2), pad_el*2), justification='l',
                              font=bold_l_font, background_color=bg_col, auto_size_text=True, border_width=0)]],
                pad=(0, 0), background_color=bg_col)],
            [sg.Col([left_elements], pad=(0, pad_v), justification='l', background_color=bg_col, expand_x=True),
             sg.Col([[sg.Canvas(size=(0, 0), visible=True, background_color=bg_col)]],
                    justification='c', background_color=bg_col, expand_x=True),
             sg.Col([right_elements], pad=(0, pad_v), justification='r', background_color=bg_col)],
            [sg.HorizontalSeparator(pad=(0, (pad_v, 0)), color=const.INACTIVE_COL)]]

        # Expense frame layout
        expense_key = self.key_lookup('ExpenseTable')
        expense_totals_key = self.key_lookup('ExpenseTotals')
        add_expense_key = self.key_lookup('AddExpense')
        remove_expense_key = self.key_lookup('RemoveExpense')
        expense_layout = [
            [lo.create_table_layout([[]], expense_header, expense_key, bind=True, pad=(0, 0), nrow=4,
                                    width=tbl_width, add_key=add_expense_key, delete_key=remove_expense_key,
                                    table_name=expense_title, tooltip='Click on a row to edit the row fields')],
            [sg.Col([
                [sg.Text('Total:', pad=((0, pad_el), (pad_v, 0)), background_color=bg_col, font=bold_font),
                 sg.Text('', key=expense_totals_key, size=(14, 1), pad=((pad_el, 0), (pad_v, 0)),
                         background_color=input_col, border_width=bwidth, relief='sunken')]
            ], background_color=bg_col, justification='r')]
        ]

        # Entries frame layout
        tbl_key = self.key_lookup('EntryTable')
        totals_key = self.key_lookup('EntryTotals')
        add_entry_key = self.key_lookup('AddEntry')
        remove_entry_key = self.key_lookup('RemoveEntry')
        entries_layout = [
            [lo.create_table_layout([[]], tbl_header, tbl_key, bind=True, pad=(0, 0), nrow=6,
                                    width=tbl_width, table_name=tbl_title, add_key=add_entry_key,
                                    delete_key=remove_entry_key, tooltip='Click on a row to edit')],
            [sg.Col([
                [sg.Text('Total:', pad=((0, pad_el), (pad_v, 0)), background_color=bg_col, font=bold_font),
                 sg.Text('', key=totals_key, size=(14, 1), pad=((pad_el, 0), (pad_v, 0)), border_width=bwidth,
                         background_color=input_col, relief='sunken')]],
                background_color=bg_col, justification='r')]
        ]

        # Main panel layout
        panel_height_key = self.key_lookup('PanelHeight')
        main_layout = [[sg.Col([[sg.Canvas(key=panel_height_key, size=(0, panel_height), visible=True)]]),
                        sg.Col([[sg.Col(header_layout, pad=(pad_frame, 0), justification='l', background_color=bg_col, expand_x=True)],
                                [sg.Col(entries_layout, pad=(pad_frame, pad_frame), vertical_alignment='t',
                                        background_color=bg_col)],
                                [sg.Col(expense_layout, pad=(pad_frame, pad_frame), vertical_alignment='t',
                                        background_color=bg_col)]],
                               vertical_alignment='t', background_color=bg_col, expand_x=True, expand_y=True)]]

        layout_els.append([sg.Col(main_layout, background_color=bg_col)])

        # Panels
        main_key = self.key_lookup('Main')
        panels = [sg.Col(layout_els, key=main_key, background_color=bg_col, vertical_alignment='c',
                         visible=True, expand_y=True, expand_x=True)]

        panel_layout = [
            [sg.Col([[sg.Pane(panels, orientation='horizontal', show_handle=False, border_width=0, relief='flat')]],
                    pad=(0, pad_v), expand_x=True, expand_y=True)]]

        # Flow control buttons
        cancel_key = self.key_lookup('Cancel')
        save_key = self.key_lookup('Save')
        bttn_layout = [sg.Col([[lo.B2('Cancel', key=cancel_key, pad=(0, (pad_v, 0)),
                                      tooltip='Return to home screen')]], justification='l', expand_x=True),
                       sg.Col([[sg.Canvas(size=(0, 0), visible=True)]], justification='c', expand_x=True),
                       sg.Col([[lo.B2('Save', key=save_key, pad=(0, (pad_v, 0)), disabled=False,
                                      tooltip='Save transaction')]], justification='r')]

        # Pane elements must be columns
        height_key = self.key_lookup('FrameHeight')
        layout = [[sg.Col([[sg.Canvas(key=height_key, size=(0, panel_height), visible=True, background_color=bg_col)]]),
                   sg.Col([
                       [sg.Frame('', [
                           [sg.Col(title_layout, pad=(0, 0), justification='l', background_color=header_col,
                                   expand_x=True, expand_y=True)],
                           [sg.Col(panel_layout, pad=(0, 0), background_color=bg_col, expand_y=True, expand_x=True)]
                       ], background_color=bg_col, title_color=text_col, relief='raised')],
                       bttn_layout])]]
        #        layout = sg.Col([[sg.Col(layout_els, vertical_alignment='t')]], key=self.element_key, visible=False)

        #        return layout
        return sg.Col(layout, key=self.element_key, visible=False)

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
        win_diff = width - const.WIN_WIDTH
        layout_pad = layout_pad + int(win_diff / 5)

        layout_width = width - layout_pad if layout_pad > 0 else width

        width_key = self.key_lookup('FrameWidth')
        window[width_key].set_size((layout_width, None))

        layout_height = height * 0.8
        panel_height = layout_height * 0.70

        height_key = self.key_lookup('FrameHeight')
        window[height_key].set_size((None, layout_height))

        panel_height_key = self.key_lookup('PanelHeight')
        window[panel_height_key].set_size((None, panel_height))

        # Reset table sizes
        # Add one row for every 100-pixel increase in window height
        height_diff = int(height - const.WIN_HEIGHT)
        nrows = 4 + int(height_diff / 100) if int(height_diff / 100) > - 2 else 4

        # Expenses table
        tbl_width = layout_width - 42

        expenses_key = self.key_lookup('ExpenseTable')
        expense_columns = self.expenses.display_columns
        expense_header = list(expense_columns.keys())
        lengths = dm.calc_column_widths(expense_header, width=tbl_width, pixels=True)
        for col_index, col_name in enumerate(expense_header):
            col_width = lengths[col_index]
            window[expenses_key].Widget.column(col_name, width=col_width)

        window[expenses_key].expand((True, True))
        window[expenses_key].table_frame.pack(expand=True, fill='both')

        # Records table
        records_key = self.key_lookup('EntryTable')
        records_columns = self.records.display_columns
        records_header = list(records_columns.keys())
        lengths = dm.calc_column_widths(records_header, width=tbl_width, pixels=True)
        for col_index, col_name in enumerate(records_header):
            col_width = lengths[col_index]
            window[records_key].Widget.column(col_name, width=col_width)

        window[records_key].expand((True, True))
        window[records_key].table_frame.pack(expand=True, fill='both')

        window[records_key].update(num_rows=nrows)
        window[expenses_key].update(num_rows=nrows)

    def update_display(self, window):
        """
        Format data elements for display.
        """
        default_col = const.ACTION_COL
        greater_col = const.PASS_COL
        lesser_col = const.FAIL_COL

        # Update entry and expense tables
        display_df = self.format_display_table(table='records')
        data = display_df.values.tolist()

        tbl_key = self.key_lookup('EntryTable')
        window[tbl_key].update(values=data)

        display_df = self.format_display_table(table='expenses')
        data = display_df.values.tolist()

        tbl_key = self.key_lookup('ExpenseTable')
        window[tbl_key].update(values=data)

        # Update totals elements
        entry_total = self.records.df[self.records.totals_column].sum()
        entry_totals_key = self.key_lookup('EntryTotals')
        window[entry_totals_key].update(value='{:,.2f}'.format(entry_total))

        expense_total = self.expenses.df[self.expenses.totals_column].sum()
        expense_totals_key = self.key_lookup('ExpenseTotals')
        window[expense_totals_key].update(value='{:,.2f}'.format(expense_total))

        # Update deposit amount
        deposit_total = entry_total - expense_total
        if deposit_total > 0:
            bg_color = greater_col
        elif deposit_total < 0:
            bg_color = lesser_col
        else:
            bg_color = default_col

        deposit_key = self.key_lookup('Deposit')
        window[deposit_key].update(value='{:,.2f}'.format(deposit_total), background_color=bg_color)
        self.deposit['Value'] = deposit_total

    def format_display_table(self, table: str = 'records', date_fmt: str = None):
        """
        Format dataframe for displaying as a table.
        """
        relativedelta = dateutil.relativedelta.relativedelta
        strptime = datetime.datetime.strptime
        is_float_dtype = pd.api.types.is_float_dtype
        is_datetime_dtype = pd.api.types.is_datetime64_any_dtype

        date_fmt = date_fmt if date_fmt is not None else settings.format_date_str(date_str=settings.display_date_format)

        if table == 'records':
            dataframe = self.records.set_datatypes(self.records.df)
            display_columns = self.records.display_columns
        else:
            dataframe = self.expenses.set_datatypes(self.expenses.df)
            display_columns = self.expenses.display_columns

        # Localization specific options
        date_offset = settings.get_date_offset()

        display_df = pd.DataFrame()

        # Subset dataframe by specified columns to display
        for col_name in display_columns:
            col_rule = display_columns[col_name]

            col_to_add = dm.generate_column_from_rule(dataframe, col_rule)
            dtype = col_to_add.dtype
            if is_float_dtype(dtype):
                col_to_add = col_to_add.apply('{:,.2f}'.format)
            elif is_datetime_dtype(dtype):
                col_to_add = col_to_add.apply(lambda x: (strptime(x.strftime(date_fmt), date_fmt) +
                                                         relativedelta(years=+date_offset)).strftime(date_fmt)
                if pd.notnull(x) else '')
            display_df[col_name] = col_to_add

        return display_df

    def create_id(self):
        """
        Create new transaction ID.
        """
        id_format = self.id['Format']
        param_fields = [i.name for i in self.parameters]

        # Determine date parameter of the new ID
        date = settings.apply_date_offset(datetime.datetime.now())

        id_date = date.strftime(settings.format_date_str())
        for component in id_format:
            if len(component) > 1 and set(component).issubset(set('YMD-/ ')):  # component is datestr
                date_fmt = settings.format_date_str(date_str=component)

                id_date = date.strftime(date_fmt)

        # Search list of used IDs occurring within the current date cycle
        try:
            prev_ids = current_tbl_pkeys[self.table]
        except KeyError:
            msg = 'Configuration Warning: missing an IDs entry for database table {}'.format(self.table)
            win2.popup_error(msg)
            sys.exit(1)
        else:
            prev_ids.sort()

        if len(prev_ids) > 0:
            used_ids = []
            for prev_id in prev_ids:
                prev_date = self.get_id_component(prev_id, 'date')
                if prev_date == id_date:
                    used_ids.append(prev_id)

            if len(used_ids) > 0:
                last_id = sorted(used_ids)[-1]
                print('Info: rule {NAME}: last ID encountered is {ID}'.format(NAME=self.name, ID=last_id))
                try:
                    last_var = int(self.get_id_component(last_id, 'variable'))
                except ValueError:
                    last_var = 0
            else:
                last_var = 0
        else:
            last_var = 0

        id_parts = []
        for component in id_format:
            if len(component) > 1 and set(component).issubset(set('YMD-/ ')):  # component is datestr
                id_parts.append(id_date)
            elif component in param_fields:
                param = self.fetch_parameter(component)
                if isinstance(param.value_obj, datetime.datetime):
                    value = param.value_obj.strftime('%Y%m%d')
                else:
                    value = param.value
                id_parts.append(value)
            elif component.isnumeric():  # component is an incrementing number
                number = str(last_var + 1)

                num_length = len(component)
                id_num = number.zfill(num_length)
                id_parts.append(id_num)
            else:  # unknown component type, probably separator or constant
                id_parts.append(component)

        return ''.join(id_parts)

    def update_id_components(self):
        """
        Update the ID components attribute used for creating new transaction IDs
        """
        id_format = self.id['Format']
        id_field = self.id['Column']
        print('Info: rule {RULE}: ID "{ID}" has format {FORMAT}'.format(RULE=self.name, ID=id_field, FORMAT=id_format))

        last_index = 0
        id_components = []
        for component in id_format:
            if len(component) > 1 and set(component).issubset(set('YMD-/ ')):  # component is datestr
                component_len = len(component)
                index = (last_index, last_index + component_len)
                part_tup = ('date', component, index)
            elif component.isnumeric():  # component is an incrementing number
                component_len = len(component)
                index = (last_index, last_index + component_len)
                part_tup = ('variable', component_len, index)
            else:  # unknown component type, probably separator
                component_len = len(component)
                index = (last_index, last_index + component_len)
                part_tup = ('separator', component, index)

            id_components.append(part_tup)
            last_index += component_len

        return id_components

    def get_id_component(self, identifier, component):
        """
        Extract the specified component values from the provided identifier.
        """
        comp_value = ''

        id_components = self.update_id_components()
        for id_component in id_components:
            comp_name, comp_value, comp_index = id_component

            if component == comp_name:
                try:
                    comp_value = identifier[comp_index[0]: comp_index[1]]
                except IndexError:
                    print('Warning: ID component {COMP} cannot be found in identifier {IDENT}'
                          .format(COMP=component, IDENT=identifier))

                break

        return comp_value

    def load_from_database(self, user):
        """
        Load previous cash transactions from the program database.
        """
        table = self.table
        display_mapping = self.display_columns

        # Define the filter parameters
        import_parameters = []
        filters = []

        id_param = self.id
        id_name = id_param['Column']
        id_param['ElementType'] = 'input'
        import_parameters.append(param_els.AuditParameterInput(self.name, id_name, id_param))

        date_param = self.date
        date_name = date_param['Column']
        date_param['ElementType'] = 'date'
        import_parameters.append(param_els.AuditParameterDate(self.name, date_name, date_param))

        for parameter in self.parameters:
            if parameter.editable is False and parameter.filterable is True and parameter.value is not None:
                filters.append(parameter.filter_statement(table=table))

            if parameter.filterable is True:
                import_parameters.append(parameter)

        # Add configured import filters
        filters += self.filter_statements()

        # Query existing database entries
        order_by = [date_name, id_name]
        import_df = user.query(table, columns=self.columns, filter_rules=filters, order=order_by, prog_db=True)
        trans_df = win2.data_import_window(import_df, import_parameters, header_map=display_mapping,
                                           aliases=self.aliases, create_new=True)

        if trans_df is None:  # user selected to cancel importing/creating a bank transaction
            return '-HOME-'
        elif trans_df.empty:  # user selected to create a new bank transaction record
            # Create and add new id to the transaction
            trans_id = self.create_id()

            # Add transaction to the list of transaction IDs
            current_tbl_pkeys[self.table].append(trans_id)

            self.df.at[0, self.id['Column']] = trans_id
            self.id['Value'] = trans_id

            # Add transaction date to table
            trans_date = datetime.datetime.now()
            self.df.at[0, self.date['Column']] = trans_date
            self.date['Value'] = trans_date

            # Add default parameter values to new transaction
            for parameter in self.parameters:
                if parameter.value is not None:
                    self.df.at[0, parameter.name] = parameter.value

            # Set existing attribute to False
            self.exists = False

            return self.element_key
        else:
            trans_id = trans_df[self.id['Column']]
            self.id['Value'] = trans_id

            trans_date = trans_df[self.date['Column']]
            self.date['Value'] = trans_date

            # Set existing attribute to True
            self.exists = True

        self.df = self.df.append(trans_df, ignore_index=True)

        # Update parameter value attributes
        values = {index: value for index, value in trans_df.items()}
        for param in self.parameters:
            param.set_value(values, by_key=False)

        # Import associated expenses and records
        expense_table = self.expenses.table
        qfilter = ('{} = ?'.format(self.expenses.refkey), (trans_id,))

        expenses_df = user.query(expense_table, columns=list(self.expenses.columns.keys()), filter_rules=qfilter, prog_db=True)
        self.expenses.df = self.expenses.import_df = expenses_df
        print(self.expenses.df, type(self.expenses.df))

        records_table = self.records.table
        qfilter = ('{} = ?'.format(self.records.refkey), (trans_id,))

        records_df = user.query(records_table, columns=list(self.records.columns.keys()), filter_rules=qfilter, prog_db=True)
        self.records.df = self.records.import_df = records_df
        print(self.records.df, type(self.records.df))

        return self.element_key

    def save_to_database(self, user):
        """
        Save results of the cash reconciliation to the program database defined in the configuration file.
        """
        df = self.df
        table = self.table

        nrow = df.shape[0]
        if nrow > 1:
            print('Something went wrong')
            return False

        # Add parameters to dataframe
        for param in self.parameters:
            param_col = param.name
            if param_col == self.id['Column']:
                continue

            param_val = param.value
            df[param_col] = param_val

        # Update the transaction table
        exists = self.exists
        if exists is True:  # updating existing transaction
            if user.admin:  # must be admin to update existing data
                # Add editor information
                df[configuration.editor_code] = user.uid
                df[configuration.edit_date] = datetime.datetime.now().strftime(settings.format_date_str())

                # Prepare insertion parameters
                columns = df.columns.values.tolist()
                values = df.values.tolist()[0]

                # Prepare filter parameters
                filters = ('{} = ?'.format(self.id['Column']), (self.id['Value'],))

                # Update existing transaction
                saved = user.update(table, columns, values, filters)
            else:
                msg = 'The transaction already exists in the database. Only an admin can modify data in the database'
                win2.popup_notice(msg)

                return False
        else:  # new transaction
            # Add creator information to the transaction
            df[configuration.creator_code] = user.uid
            df[configuration.creation_date] = datetime.datetime.now().strftime(settings.format_date_str())

            # Prepare insertion parameters
            columns = df.columns.values.tolist()
            values = df.values.tolist()

            # Add new transaction to the database
            saved = user.insert(table, columns, values)

        if saved is False:
            return False

        # Add transaction ID to the expenses table
        self.expenses.df[self.expenses.refkey] = self.id['Value']

        # Update the records added to the transaction
        records_table = self.records.table
        ref_column = self.records.refkey
        ref_key = self.records.pkey
        ref_value = self.id['Value']
        for index, row in self.records.df.iterrows():
            row_id = row[ref_key]
            filters = ('{} = ?'.format(ref_key), (row_id,))
            success = user.update(records_table, [ref_column], [ref_value], filters)
            if success is False:
                print('Warning: Failed to update {}'.format(row_id))

        # Update the records removed from the transaction
        for index, row in self.records.unassociated_df.iterrows():
            row_id = row[ref_key]
            filters = ('{} = ?'.format(ref_key), (row_id,))
            success = user.update(records_table, [ref_column], [None], filters)
            if success is False:
                print('Warning: Failed to update {}'.format(row_id))

        # Update the cash expenses added to the transaction
        expenses_table = self.expenses.table
        expense_pkey = self.expenses.pkey
        expense_refkey = self.expenses.refkey
        import_expenses = self.expenses.import_df[expense_pkey].tolist()
        for index, row in self.expenses.df.iterrows():
            row_id = row[expense_pkey]
            if row_id in import_expenses:
                # Edit existing expense in database table
                row[configuration.editor_code] = user.uid
                row[configuration.edit_date] = datetime.datetime.now().strftime(settings.format_date_str())

                row_columns = row.index.tolist()
                row_values = row.values.tolist()

                filters = ('{} = ?'.format(expense_pkey), (row_id,))
                success = user.update(expenses_table, row_columns, row_values, filters)
            else:
                # Create new entry for expense in database table
                row[configuration.creator_code] = user.uid
                row[configuration.creation_date] = datetime.datetime.now().strftime(settings.format_date_str())

                row_columns = row.index.tolist()
                row_values = row.values.tolist()

                success = user.insert(expenses_table, row_columns, row_values)

            if success is False:
                print('Warning: Failed to update {}'.format(row_id))

        # Handle removed expenses
        removed_expenses = self.expenses.removed_df[expense_pkey].values.tolist()
        for expense_id in removed_expenses:
            if expense_id not in import_expenses:  # expense doesn't exist in database yet, no need to save
                continue

            # Update the cash expenses removed from the transaction
            filters = ('{} = ?'.format(expense_pkey), (expense_id,))
            success = user.update(expenses_table, [expense_refkey, 'IsCancel'], [None, 1], filters)

            if success is False:
                win2.popup_error('Warning: Failed to update {ID}. Changes will not be saved to database table {TBL}'
                                 .format(ID=expense_id, TBL=expenses_table))

        return True

    def filter_statements(self):
        """
        Generate the filter statements for tab query parameters.
        """
        operators = {'>', '>=', '<', '<=', '=', '!=', 'IN', 'in', 'In'}

        params = self.import_parameters
        if params is None:
            return []

        filters = []
        for param_col in params:
            param_rule = params[param_col]

            param_oper = None
            param_values = []
            conditional = dm.parse_operation_string(param_rule, equivalent=False)
            for component in conditional:
                if component in operators:
                    if not param_oper:
                        param_oper = component
                    else:
                        print(
                            'Error: rule {RULE}: only one operator allowed in import parameters for parameter '
                            '{PARAM}'.format(RULE=self.name, PARAM=param_col))
                        break
                else:
                    param_values.append(component)

            if not (param_oper and param_values):
                print('Error: rule {RULE}: import parameter {PARAM} requires both an operator and a value'
                      .format(RULE=self.name, PARAM=param_col))
                break

            if param_oper.upper() == 'IN':
                vals_fmt = ', '.join(['?' for i in param_values])
                filters.append(('{COL} {OPER} ({VALS})'.format(COL=param_col, OPER=param_oper, VALS=vals_fmt),
                                (param_values,)))
            else:
                if len(param_values) == 1:
                    filters.append(('{COL} {OPER} ?'.format(COL=param_col, OPER=param_oper), (param_values[0],)))
                else:
                    print('Error: rule {RULE}: import parameter {PARAM} has too many values {COND}'
                          .format(RULE=self.name, PARAM=param_col, COND=param_rule))
                    break

        return filters


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
            self.table = edict['DatabaseTable']
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
            self.refkey = edict['ReferenceKey']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}, Expenses: missing required field "ReferenceKey".') \
                .format(RULE=rule_name)
            win2.popup_error(msg)
            sys.exit(1)

        try:
            id_format = edict['IDFormat']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}, Expenses: missing required field "IDFormat".') \
                .format(RULE=rule_name)
            win2.popup_error(msg)
            sys.exit(1)
        else:
            self.format = re.findall(r'\{(.*?)\}', id_format)

        try:
            table_columns = edict['TableColumns']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}, Expenses: missing required field "TableColumns".') \
                .format(RULE=rule_name)
            win2.popup_error(msg)
            sys.exit(1)
        else:
            self.columns = table_columns

        try:
            self.display_columns = edict['DisplayColumns']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}, Expenses: missing required field "DisplayColumns".') \
                .format(RULE=rule_name)
            win2.popup_error(msg)
            sys.exit(1)

        try:
            self.edit_columns = edict['EditColumns']
        except KeyError:
            self.edit_columns = {}

        try:
            self.static_columns = edict['StaticColumns']
        except KeyError:
            self.static_columns = {}

        try:
            self.totals_column = edict['TotalColumn']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}, Expenses: missing required field "TotalColumn".') \
                .format(RULE=rule_name)
            win2.popup_error(msg)
            sys.exit(1)

        # Dynamic attributes
        self.df = self.import_df = self.removed_df = pd.DataFrame(columns=list(table_columns.keys()))

        self.ids = []

    def reset_dynamic_attributes(self):
        """
        Reset attributes.
        """
        header = list(self.columns.keys())
        self.df = self.import_df = self.removed_df = pd.DataFrame(columns=header)

        self.ids = []

    def add_row(self):
        """
        Add a new expense to the expenses table.
        """
        df = self.df.copy()
        id_field = self.pkey

        edit_columns = self.edit_columns
        static_columns = self.static_columns
        display_columns = self.display_columns

        # Initialize new empty row
        nrow = df.shape[0]
        new_index = nrow - 1 + 1  # first index starts at 0

        df = df.append(pd.Series(), ignore_index=True)

        # Create an identifier for the new row
        record_id = self.create_id()

        df.at[new_index, id_field] = record_id

        # Fill in any editable columns with default values
        for edit_column in edit_columns:
            edit_entry = edit_columns[edit_column]
            try:
                default_value = edit_entry['DefaultValue']
            except KeyError:
                try:
                    element_type = edit_entry['ElementType']
                except KeyError:
                    print('Configuration Warning: rule {RULE}, Expenses: the parameter "ElementType" is required '
                          'for EditColumn {COL}'.format(RULE=self.rule_name, COL=edit_column))
                    continue

                if element_type in ('date', 'datetime', 'timestamp', 'time', 'year'):
                    default_value = datetime.datetime.now()
                elif element_type in ('int', 'integer', 'bit'):
                    default_value = 0
                elif element_type in ('float', 'decimal', 'dec', 'double', 'numeric', 'money'):
                    default_value = 0.0
                elif element_type in ('bool', 'boolean'):
                    default_value = False
                elif element_type in ('char', 'varchar', 'binary', 'text'):
                    default_value = ''
                else:
                    default_value = ''

            df.at[new_index, edit_column] = default_value

        # Fill in any static columns with default values
        for static_column in static_columns:
            static_entry = static_columns[static_column]
            try:
                default_value = static_entry['DefaultValue']
            except KeyError:
                try:
                    element_type = static_entry['ElementType']
                except KeyError:
                    print('Configuration Warning: rule {RULE}, Expenses: the parameter "ElementType" is required '
                          'for StaticColumn {COL}'.format(RULE=self.rule_name, COL=static_column))
                    continue

                if element_type in ('date', 'datetime', 'timestamp', 'time', 'year'):
                    default_value = datetime.datetime.now()
                elif element_type in ('int', 'integer', 'bit'):
                    default_value = 0
                elif element_type in ('float', 'decimal', 'dec', 'double', 'numeric', 'money'):
                    default_value = 0.0
                elif element_type in ('bool', 'boolean'):
                    default_value = False
                elif element_type in ('char', 'varchar', 'binary', 'text'):
                    default_value = ''
                else:
                    default_value = ''

            df.at[new_index, static_column] = default_value

        # Display the add row window
        display_map = {display_columns[i]: i for i in display_columns}
        df = win2.modify_record(df, new_index, edit_columns, header_map=display_map, edit=False)

        if nrow + 1 == df.shape[0]:  # record successfully saved
            # Save to list of used IDs
            print('Info: saving new record {ID} to list of table {TBL} IDs'.format(ID=record_id, TBL=self.table))
            current_tbl_pkeys[self.table].append(record_id)

        self.df = df

    def edit_row(self, index, win_size: tuple = None):
        """
        Edit a row in the expense table.
        """
        df = self.df.copy()
        display_columns = self.display_columns
        edit_columns = self.edit_columns

        display_map = {display_columns[i]: i for i in display_columns}
        df = win2.modify_record(df, index, edit_columns, header_map=display_map, win_size=win_size, edit=True)

        self.df = df

    def remove_row(self, index):
        """
        Remove row from expense table.
        """
        df = self.df.copy()
        removed_df = self.removed_df.copy()

        # Remove the deleted expense ID from the list of table IDs if not already saved in database
        record_ids = df[self.pkey][index]
        existing_expenses = self.import_df[self.pkey].values.tolist()
        for record_id in record_ids:
            if record_id not in existing_expenses:
                try:
                    current_tbl_pkeys[self.table].remove(record_id)
                except ValueError:
                    print('Warning: attempting to remove non-existent ID "{ID}" from the list of database '
                          'table {TBL} IDs'.format(ID=record_id, TBL=self.table))
                    continue
                else:
                    print('Info: removed ID {ID} from the list of database table {TBL} IDs'
                          .format(ID=record_id, TBL=self.table))

        # Add row to the dataframe of removed expenses
        removed_df = removed_df.append(df.iloc[index], ignore_index=True)
        removed_df.reset_index(drop=True, inplace=True)

        # Drop row from the dataframe of included expenses
        df.drop(index, axis=0, inplace=True)
        df.reset_index(drop=True, inplace=True)

        self.removed_df = removed_df
        self.df = df

    def create_id(self):
        """
        Create a new ID based on a list of previous IDs.
        """
        id_format = self.format

        # Determine date parameter of the new ID
        date = settings.apply_date_offset(datetime.datetime.now())

        id_date = date.strftime(settings.format_date_str())
        for component in id_format:
            if len(component) > 1 and set(component).issubset(set('YMD-/ ')):  # component is datestr
                date_fmt = settings.format_date_str(date_str=component)

                id_date = date.strftime(date_fmt)

        # Search list of used IDs occurring within the current date cycle
        try:
            prev_ids = current_tbl_pkeys[self.table]
        except KeyError:
            msg = 'Configuration Warning: missing an IDs entry for database table {}'.format(self.table)
            win2.popup_error(msg)
            sys.exit(1)
        else:
            prev_ids.sort()

        if len(prev_ids) > 0:
            print('current ids are: {}'.format(prev_ids))
            used_ids = []
            print('current id date is: {}'.format(id_date))
            for prev_id in prev_ids:
                print('previous id is: {}'.format(prev_id))
                prev_date = self.get_id_component(prev_id, 'date')
                print('with id date: {}'.format(prev_date))
                if prev_date == id_date:
                    used_ids.append(prev_id)

            if len(used_ids) > 0:
                print('ids in same cycle are: {}'.format(used_ids))
                last_id = sorted(used_ids)[-1]
                print('with most recent id: {}'.format(last_id))
                print('Info: rule {RULE}, Expenses: last ID encountered is {ID}'
                      .format(RULE=self.rule_name, ID=last_id))
                try:
                    last_var = int(self.get_id_component(last_id, 'variable'))
                except ValueError:
                    last_var = 0
            else:
                last_var = 0
        else:
            last_var = 0

        id_parts = []
        for component in id_format:
            if len(component) > 1 and set(component).issubset(set('YMD-/ ')):  # component is datestr
                id_parts.append(id_date)
            elif component.isnumeric():  # component is an incrementing number
                number = str(last_var + 1)

                num_length = len(component)
                id_num = number.zfill(num_length)
                id_parts.append(id_num)
            else:  # unknown component type, probably separator or constant
                id_parts.append(component)

        return ''.join(id_parts)

    def update_id_components(self):
        """
        Update the IDs attribute to include a list of component lengths for creating new Expense IDs.
        """
        id_format = self.format
        id_field = self.pkey

        last_index = 0
        id_components = []
        for component in id_format:
            if len(component) > 1 and set(component).issubset(set('YMD-/ ')):  # component is datestr
                component_len = len(component)
                index = (last_index, last_index + component_len)
                part_tup = ('date', component, index)
            elif component.isnumeric():  # component is an incrementing number
                component_len = len(component)
                index = (last_index, last_index + component_len)
                part_tup = ('variable', component_len, index)
            else:  # unknown component type, probably separator
                component_len = len(component)
                index = (last_index, last_index + component_len)
                part_tup = ('separator', component, index)

            id_components.append(part_tup)
            last_index += component_len

        return id_components

    def get_id_component(self, identifier, component):
        """
        Extract the specified component values from the provided identifier.
        """
        id_components = self.update_id_components()
        print('id components are: {}'.format(id_components))

        comp_value = ''
        for id_component in id_components:
            comp_name, comp_desc, comp_index = id_component

            if component == comp_name:
                try:
                    comp_value = identifier[comp_index[0]: comp_index[1]]
                except IndexError:
                    print('Warning: ID component {COMP} cannot be found in identifier {IDENT}'
                          .format(COMP=component, IDENT=identifier))

                break

        return comp_value

    def set_datatypes(self, df):
        """
        Set column data types based on header mapping.
        """
        df = df.copy()
        header_map = self.columns

        for column in header_map:
            try:
                dtype = header_map[column]
            except KeyError:
                dtype = 'varchar'
                astype = object
            else:
                if dtype in ('date', 'datetime', 'timestamp', 'time', 'year'):
                    astype = np.datetime64
                elif dtype in ('int', 'integer', 'bit'):
                    astype = int
                elif dtype in ('float', 'decimal', 'dec', 'double', 'numeric', 'money'):
                    astype = float
                elif dtype in ('bool', 'boolean'):
                    astype = bool
                elif dtype in ('char', 'varchar', 'binary', 'text'):
                    astype = object
                else:
                    astype = object

            try:
                df[column] = df[column].astype(astype, errors='raise')
            except (ValueError, TypeError):
                print('Warning: rule {RULE}, Expenses: unable to set column {COL} to data type {DTYPE}'
                      .format(RULE=self.rule_name, COL=column, DTYPE=dtype))

        return df


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
            self.table = rdict['DatabaseTable']
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
            self.refkey = rdict['ReferenceKey']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}, Records: missing required field "ReferenceKey".') \
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
            self.columns = table_columns

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
        self.df = self.import_df = self.unassociated_df = pd.DataFrame(columns=list(table_columns.keys()))

    def reset_dynamic_attributes(self):
        """
        Reset attributes.
        """
        header = list(self.columns.keys())
        self.df = self.import_df = self.unassociated_df = pd.DataFrame(columns=header)

    def add_row(self):
        """
        Add new records to the records table.
        """
        unassoc_df = self.set_datatypes(self.unassociated_df)
        df = self.set_datatypes(self.df)
        pkey = self.pkey
        display_columns = {j: i for i, j in self.reference_columns.items()}

        # Display data selection window
        selected_ids = win2.associate_data(df, unassoc_df, pkey, column_map=display_columns,
                                        to_title=self.title, from_title=self.reference_header)

        if len(selected_ids) > 0:
            selected_indices = unassoc_df.index[unassoc_df[pkey].isin(selected_ids)].tolist()

            # Add selected rows to records
            df = df.append(unassoc_df.iloc[selected_indices], ignore_index=True)
            df.reset_index(drop=True, inplace=True)

            # Remove selected rows from unassociated records
            unassoc_df.drop(selected_indices, axis=0, inplace=True)
            unassoc_df.reset_index(drop=True, inplace=True)

        self.df = df
        self.unassociated_df = unassoc_df

    def remove_row(self, index):
        """
        Remove row from records table.
        """
        df = self.df.copy()
        unassoc_df = self.unassociated_df.copy()

        # Add row to the dataframe of unassociated entries
        unassoc_df = unassoc_df.append(df.iloc[index], ignore_index=True)
        unassoc_df.reset_index(drop=True, inplace=True)

        # Drop row from the dataframe of included entries
        df.drop(index, axis=0, inplace=True)
        df.reset_index(drop=True, inplace=True)

        self.unassociated_df = unassoc_df
        self.df = df

    def set_datatypes(self, df):
        """
        Set column data types based on header mapping.
        """
        df = df.copy()
        header_map = self.columns

        for column in header_map:
            try:
                dtype = header_map[column]
            except KeyError:
                dtype = 'varchar'
                astype = object
            else:
                if dtype in ('date', 'datetime', 'timestamp', 'time', 'year'):
                    astype = np.datetime64
                elif dtype in ('int', 'integer', 'bit'):
                    astype = int
                elif dtype in ('float', 'decimal', 'dec', 'double', 'numeric', 'money'):
                    astype = float
                elif dtype in ('bool', 'boolean'):
                    astype = bool
                elif dtype in ('char', 'varchar', 'binary', 'text'):
                    astype = object
                else:
                    astype = object

            try:
                df[column] = df[column].astype(astype, errors='raise')
            except (ValueError, TypeError):
                print('Warning: rule {RULE}, Expenses: unable to set column {COL} to data type {DTYPE}'
                      .format(RULE=self.rule_name, COL=column, DTYPE=dtype))

        return df


class CashSummaryPanel:
    """

    """

    def __init__(self, rule_name, sdict):

        self.rule_name = rule_name
        self.element_key = lo.as_key('{} Summary'.format(rule_name))
        self.elements = ['Title']

        self.summary_items = []

        try:
            self._title = sdict['Title']
        except KeyError:
            self._title = '{} Summary'.format(rule_name)

        self.title = None

        try:
            self.aliases = sdict['Aliases']
        except KeyError:
            self.aliases = []

    def key_lookup(self, element):
        """
        Lookup element key for input control element.
        """
        if element in self.elements:
            key = lo.as_key('{} Summary {}'.format(self.rule_name, element))
        else:
            print('Warning: rule {RULE}, Summary: unable to find GUI element {ELEM} in list of elements'
                  .format(RULE=self.rule_name, ELEM=element))
            key = None

        return key
