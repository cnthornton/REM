"""
REM transaction audit configuration classes and functions. Includes audit rules, audit objects, and rule parameters.
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
import REM.parameters as param_els
import REM.secondary as win2
from REM.config import configuration, current_tbl_pkeys, settings


class AuditRules:
    """
    Class to store and manage program audit_rule configuration settings.

    Arguments:

        cnfg: parsed YAML file.

    Attributes:

        rules (list): List of AuditRule objects.
    """

    def __init__(self, cnfg):

        # Audit parameters
        audit_param = cnfg.audit_rules

        self.rules = []
        if audit_param is not None:
            try:
                audit_name = audit_param['name']
            except KeyError:
                win2.popup_error('Error: audit_rules: the parameter "name" is a required field')
                sys.exit(1)
            else:
                self.name = audit_name

            try:
                self.title = audit_param['title']
            except KeyError:
                self.title = audit_name

            try:
                audit_rules = audit_param['rules']
            except KeyError:
                win2.popup_error('Error: audit_rules: the parameter "rules" is a required field')
                sys.exit(1)

            for audit_rule in audit_rules:
                self.rules.append(AuditRule(audit_rule, audit_rules[audit_rule]))

    def print_rules(self, title=True):
        """
        Return name of all audit rules defined in configuration file.
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
            print('Warning: AuditRules: Rule {NAME} not in list of configured audit rules. Available rules are {ALL}'
                  .format(NAME=name, ALL=', '.join(self.print_rules())))
            rule = None
        else:
            rule = self.rules[index]

        return rule


class AuditRule:
    """
    Class to store and manage a configured audit rule.

    Arguments:

        name (str): audit rule name.

        adict (dict): dictionary of optional and required audit rule arguments.

    Attributes:

        name (str): audit rule name.

        title (str): audit rule title.

        element_key (str): GUI element key.

        permissions (str): permissions required to view the audit. Default: user.

        parameters (list): list of AuditParameter type objects.

        tabs (list): list of TabItem objects.

        summary (SummaryPanel): SummaryPanel object.
    """

    def __init__(self, name, adict):

        self.name = name
        self.element_key = lo.as_key(name)
        self.elements = ['TG', 'Cancel', 'Start', 'Back', 'Next', 'Save', 'Audit', 'FrameWidth', 'FrameHeight']
        try:
            self.title = adict['Title']
        except KeyError:
            self.title = name

        try:
            self.permissions = adict['Permissions']
        except KeyError:  # default permission for an audit is 'user'
            self.permissions = 'user'

        self.parameters = []
        try:
            params = adict['RuleParameters']
        except KeyError:
            msg = 'Configuration Error: the rule parameter "RuleParameters" is required for rule {}'.format(name)
            win2.popup_error(msg)
            sys.exit(1)

        for param in params:
            cdict = params[param]
            self.elements.append(param)

            param_layout = cdict['ElementType']
            if param_layout == 'dropdown':
                self.parameters.append(param_els.AuditParameterCombo(name, param, cdict))
            elif param_layout == 'input':
                self.parameters.append(param_els.AuditParameterInput(name, param, cdict))
            elif param_layout == 'date':
                self.parameters.append(param_els.AuditParameterDate(name, param, cdict))
            elif param_layout == 'date_range':
                self.parameters.append(param_els.AuditParameterDateRange(name, param, cdict))
            else:
                msg = 'Configuration Error: unknown rule parameter type {TYPE} in rule {NAME}' \
                    .format(TYPE=param_layout, NAME=name)
                win2.popup_error(msg)
                sys.exit(1)

        self.tabs = []
        try:
            tdict = adict['Tabs']
        except KeyError:
            msg = 'Configuration Error: the rule parameter "Tabs" is required for rule {}'.format(name)
            win2.popup_error(msg)
            sys.exit(1)

        for tab_name in tdict:
            self.tabs.append(lo.TabItem(name, tab_name, tdict[tab_name]))

        try:
            sdict = adict['Summary']
        except KeyError:
            msg = 'Configuration Error: the rule parameter "Summary" is required for rule {}'.format(name)
            win2.popup_error(msg)
            sys.exit(1)

        self.summary = SummaryPanel(name, sdict)

        self.panel_keys = {0: self.key_lookup('Audit'), 1: self.summary.element_key}
        self.current_panel = 0
        self.first_panel = 0
        self.last_panel = 1

    def key_lookup(self, element):
        """
        Lookup element key for input control element.
        """
        if element in self.elements:
            key = lo.as_key('{} {}'.format(self.name, element))
        else:
            key = None

        return key

    def fetch_tab(self, name, by_key: bool = False):
        """
        """
        if not by_key:
            names = [i.name for i in self.tabs]
        else:
            names = [i.element_key for i in self.tabs]

        try:
            index = names.index(name)
        except ValueError:
            print('Error: rule {RULE}: tab item {TAB} not in list of tab items'.format(RULE=self.name, TAB=name))
            tab_item = None
        else:
            tab_item = self.tabs[index]

        return tab_item

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

    def layout(self, win_size: tuple = None):
        """
        Generate a GUI layout for the audit rule.
        """
        if win_size:
            width, height = win_size
        else:
            width, height = (const.WIN_WIDTH, const.WIN_HEIGHT)

        # Element parameters
        inactive_col = const.INACTIVE_COL
        bg_col = const.ACTION_COL
        default_col = const.DEFAULT_COL
        text_col = const.TEXT_COL
        select_col = const.SELECT_TEXT_COL
        font_h = const.HEADER_FONT
        header_col = const.HEADER_COL

        pad_el = const.ELEM_PAD
        pad_v = const.VERT_PAD
        pad_frame = const.FRAME_PAD

        # Audit parameters
        params = self.parameters

        # Element sizes
        layout_width = width - 120 if width >= 120 else width
        layout_height = height * 0.8
        panel_height = layout_height * 0.5

        bwidth = 0.5

        # Layout elements
        # Title
        panel_title = self.title
        width_key = self.key_lookup('FrameWidth')
        title_layout = [[sg.Col([
            [sg.Canvas(key=width_key, size=(layout_width, 1), pad=(0, pad_v), visible=True,
                       background_color=header_col)],
            [sg.Text(panel_title, pad=((pad_frame, 0), (0, pad_v)), font=font_h, background_color=header_col)]],
            pad=(0, 0), justification='l', background_color=header_col, expand_x=True)]]

        # Audit layout
        audit_layout = []

        # Control elements
        param_elements = []
        for param in params:
            element_layout = param.layout()
#            param_elements.append(element_layout)
            param_elements += element_layout

        param_layout = [
            [sg.Col([param_elements], pad=(0, (0, pad_v)), background_color=bg_col, vertical_alignment='c',
                    expand_x=True)],
            [sg.HorizontalSeparator(pad=(0, (pad_v, 0)), color=const.HEADER_COL)]]

        audit_layout.append([sg.Col(param_layout, pad=(pad_frame, 0), background_color=bg_col,
                                    justification='l', expand_x=True)])

        # Audit tabs
        tg_key = self.key_lookup('TG')
        tg_layout = [
            [sg.TabGroup([lo.tab_layout(self.tabs, win_size=win_size)], key=tg_key, pad=(0, 0),
                         tab_background_color=inactive_col, selected_title_color=select_col, title_color=text_col,
                         selected_background_color=bg_col, background_color=bg_col)]
        ]

        audit_layout.append([sg.Col(tg_layout, pad=(pad_frame, pad_frame), background_color=bg_col, expand_x=True)])

        # Panels
        summary_layout = self.summary.layout(win_size)

        audit_key = self.key_lookup('Audit')
        panels = [sg.Col(audit_layout, key=audit_key, background_color=bg_col, vertical_alignment='c',
                         visible=True, expand_y=True, expand_x=True),
                  sg.Col(summary_layout, key=self.summary.element_key, background_color=bg_col, vertical_alignment='c',
                         visible=False, expand_y=True, expand_x=True)]

        panel_layout = [
            [sg.Col([[sg.Pane(panels, orientation='horizontal', show_handle=False, border_width=0, relief='flat')]],
                    pad=(0, pad_v), expand_x=True)]]

        # Standard elements
        cancel_key = self.key_lookup('Cancel')
        start_key = self.key_lookup('Start')
        next_key = self.key_lookup('Next')
        back_key = self.key_lookup('Back')
        save_key = self.key_lookup('Save')
        bttn_layout = [
            sg.Col([[lo.B2('Cancel', key=cancel_key, pad=((0, pad_el), 0), disabled=False,
                           tooltip='Return to home screen'),
                     lo.B2('Start', key=start_key, pad=((pad_el, 0), 0), disabled=False, tooltip='Start audit')]],
                   pad=(0, (pad_v, 0)), justification='l', expand_x=True),
            sg.Col([[sg.Canvas(size=(0, 0), visible=True)]], justification='c', expand_x=True),
            sg.Col([[lo.B2('Back', key=back_key, pad=((0, pad_el), 0), disabled=True, tooltip='Return to audit'),
                     lo.B2('Next', key=next_key, pad=(pad_el, 0), disabled=True, tooltip='Review audit'),
                     lo.B2('Save', key=save_key, pad=((pad_el, 0), 0), disabled=True,
                           tooltip='Save to database and generate summary report')]],
                   pad=(0, (pad_v, 0)), justification='r')]

        # Pane elements must be columns
        height_key = self.key_lookup('FrameHeight')
        layout = [[sg.Col([[sg.Canvas(key=height_key, size=(0, panel_height), visible=True, background_color=bg_col)]]),
                   sg.Col([
                       [sg.Frame('', [
                           [sg.Col(title_layout, pad=(0, 0), justification='l', background_color=header_col,
                                   expand_x=True, expand_y=True)],
                           [sg.Col(panel_layout, pad=(0, 0), background_color=bg_col)]
                       ], background_color=bg_col, title_color=text_col, relief='raised')],
                       bttn_layout])]]

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
        # For every five-pixel increase in window size, increase tab size by one
        layout_pad = 120
        win_diff = width - const.WIN_WIDTH
        layout_pad = layout_pad + int(win_diff / 5)

        layout_width = width - layout_pad if layout_pad > 0 else width

        width_key = self.key_lookup('FrameWidth')
        window[width_key].set_size((layout_width, None))

        layout_height = height * 0.8

        height_key = self.key_lookup('FrameHeight')
        window[height_key].set_size((None, layout_height))

        # Resize tab elements
        tabs = self.tabs
        for tab in tabs:
            tab.resize_elements(window, win_size)

        # Resize summary elements
        self.summary.resize_elements(window, win_size)

    def reset_rule(self, window, current: bool = False):
        """
        Reset rule to default.
        """
        win_width, win_height = window.size

        panel_key = self.element_key
        current_key = self.panel_keys[self.current_panel]

        # Reset current panel
        self.current_panel = 0

        # Disable current panel
        window[current_key].update(visible=False)
        window[self.panel_keys[self.first_panel]].update(visible=True)
        window[panel_key].update(visible=False)
        window['-HOME-'].update(visible=True)

        # Reset 'Start' element in case audit was in progress
        start_key = self.key_lookup('Start')
        window[start_key].update(disabled=False)

        # Reset 'Save' element in case audit was nearly complete
        end_key = self.key_lookup('Save')
        next_key = self.key_lookup('Next')
        back_key = self.key_lookup('Back')
        window[next_key].update(disabled=True)
        window[back_key].update(disabled=True)
        window[end_key].update(disabled=True)

        # Switch to first tab in summary panel
        tg_key = self.summary.key_lookup('TG')
        window[tg_key].Widget.select(0)

        # Reset rule item attributes, including tab, summary, and parameter
        self.reset_attributes()

        # Reset audit parameters. Audit specific parameters include actions
        # buttons Scan and Confirm, for instance.
        self.toggle_parameters(window, 'enable')

        # Reset parameter element values
        params = self.parameters
        for param in params:
            print('Info: rule {RULE}: resetting rule parameter element {PARAM} to default'
                  .format(RULE=self.name, PARAM=param.name))
            window[param.element_key].update(value='')
            try:
                window[param.element_key2].update(vaue='')
            except AttributeError:
                pass

        # Reset tab-specific element values
        for i, tab in enumerate(self.tabs):
            # Reset displays
            ## Reset table element
            table_key = tab.key_lookup('Table')
            window[table_key].update(values=tab.df.values.tolist())

            tab.resize_elements(window, win_size=(win_width, win_height))

            ## Reset summary element
            summary_key = tab.key_lookup('Summary')
            window[summary_key].update(value='')

            # Reset action buttons
            tab.toggle_actions(window, 'disable')

            # Reset visible tabs
            visible = True if i == 0 else False
            print('Info: rule {RULE}, tab {NAME}: re-setting visibility to {STATUS}'
                  .format(NAME=tab.name, RULE=tab.rule_name, STATUS=visible))
            window[tab.element_key].update(visible=visible)

        if current:
            window['-HOME-'].update(visible=False)
            window[panel_key].update(visible=True)
            window[self.panel_keys[self.first_panel]].update(visible=True)

            next_key = panel_key
        else:
            next_key = '-HOME-'

        return next_key

    def reset_attributes(self):
        """
        Reset rule item attributes.
        """
        # Reset Parameter attributes
        for param in self.parameters:
            print('Info: rule {RULE}: resetting rule parameter element {PARAM} to default'
                  .format(RULE=self.name, PARAM=param.name))
            param.value = param.value_raw = param.value_obj = None
            try:
                param.value2 = None
            except AttributeError:
                pass

        # Reset Tab attributes
        for i, tab in enumerate(self.tabs):
            tab.reset_dynamic_attributes()

        # Reset Summary attributes
        for tab in self.summary.tabs:
            tab.reset_dynamic_attributes()

    def toggle_parameters(self, window, value='enable'):
        """
        Enable / Disable audit rule parameter elements.
        """
        status = False if value == 'enable' else True

        for parameter in self.parameters:
            element_key = parameter.element_key
            print('Info: rule {RULE}, parameter {NAME}: updated element to "disabled={VAL}"'
                  .format(NAME=parameter.name, RULE=self.name, VAL=status))

            window[element_key].update(disabled=status)


class SummaryPanel:
    """
    AuditRule summary panel object.
    """

    def __init__(self, rule_name, sdict):

        self.rule_name = rule_name
        self.element_key = lo.as_key('{} Summary'.format(rule_name))
        self.elements = ['Cancel', 'Back', 'Save', 'Title', 'TG', 'FrameWidth']

        self.tabs = []

        try:
            self._title = sdict['Title']
        except KeyError:
            self._title = '{} Summary'.format(rule_name)

        self.title = None

        try:
            tabs = sdict['Tabs']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}: Summary missing required field "Tabs".') \
                .format(RULE=rule_name)
            win2.popup_error(msg)
            sys.exit(1)

        for tab in tabs:
            si_dict = tabs[tab]
            try:
                summ_type = si_dict['Type']
            except KeyError:
                msg = _('Configuration Error: rule {RULE}, summary {NAME}:  missing required field "Type".') \
                    .format(RULE=rule_name, NAME=tab)
                win2.popup_error(msg)
                sys.exit(1)

            if summ_type == 'Subset':
                self.tabs.append(SummaryItemSubset(rule_name, tab, si_dict))
            elif summ_type == 'Add':
                self.tabs.append(SummaryItemAdd(rule_name, tab, si_dict))
            else:
                msg = _('Configuration Error: rule {RULE}, summary {NAME}:  unknown type "{TYPE}" provided to the '
                        'Types parameter.').format(RULE=rule_name, NAME=tab, TYPE=summ_type)
                win2.popup_error(msg)
                sys.exit(1)

        try:
            self.aliases = sdict['Aliases']
        except KeyError:
            self.aliases = []

        try:
            report = sdict['Report']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}: Summary missing required field "Report".') \
                .format(RULE=rule_name)
            win2.popup_error(msg)
            sys.exit(1)
        for tab_name in report:
            report_tab = report[tab_name]
            for section_name in report_tab:
                section = report_tab[section_name]

                msg = _('Configuration Error: rule {RULE}, Summary Report: missing required parameter "{PARAM}"'
                        'in report section {NAME}')
                if 'Title' not in section:
                    section['Title'] = section_name
                if 'Columns' not in section:
                    win2.popup_error(msg.format(RULE=rule_name, PARAM='Columns', NAME=section_name))
                    sys.exit(1)

        self.report = report

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

    def fetch_tab(self, name, by_key: bool = False):
        """
        Fetch a select summary item by the summary item name or element key.
        """
        if not by_key:
            names = [i.name for i in self.tabs]
        else:
            names = [i.element_key for i in self.tabs]

        try:
            index = names.index(name)
        except ValueError:
            print('Error: rule {RULE}, Summary: summary item {TAB} not in list of summary items'
                  .format(RULE=self.rule_name, TAB=name))
            tab_item = None
        else:
            tab_item = self.tabs[index]

        return tab_item

    def layout(self, win_size: tuple = None):
        """
        Generate a GUI layout for the Audit Rule Summary.
        """
        if win_size:
            width, height = win_size
        else:
            width, height = (const.WIN_WIDTH, const.WIN_HEIGHT)

        # Layout settings
        pad_frame = const.FRAME_PAD
        pad_el = const.ELEM_PAD
        pad_v = const.VERT_PAD

        bg_col = const.ACTION_COL
        default_col = const.DEFAULT_COL
        inactive_col = const.INACTIVE_COL
        text_col = const.TEXT_COL
        select_col = const.SELECT_TEXT_COL
        header_col = const.HEADER_COL

        font_h = const.BOLD_FONT

        tabs = self.tabs

        frame_width = width - 120

        # Layout elements
        layout = []

        # Panel heading layout
        title_key = self.key_lookup('Title')
        header_layout = [
            [sg.Col([[sg.Text(self.title, key=title_key, size=(40, 1), pad=(0, 0), font=font_h,
                              background_color=bg_col, tooltip=self.title)]],
                    vertical_alignment='c', background_color=bg_col, expand_x=True)],
            [sg.HorizontalSeparator(pad=(0, (pad_v, 0)), color=const.HEADER_COL)]]

        layout.append([sg.Col(header_layout, pad=(pad_frame, 0), background_color=bg_col,
                              justification='l', expand_x=True)])

        # Main screen
        tg_key = self.key_lookup('TG')
        tg_layout = [[sg.TabGroup([lo.tab_layout(tabs, win_size=win_size, initial_visibility='all')],
                                  key=tg_key, pad=(0, 0), background_color=bg_col,
                                  tab_background_color=inactive_col, selected_background_color=bg_col,
                                  selected_title_color=select_col, title_color=text_col)]]

        layout.append([sg.Col(tg_layout, pad=(pad_frame, pad_frame), background_color=bg_col, expand_x=True)])

        return layout

    def resize_elements(self, window, win_size: tuple = None):
        """
        Resize summary items tables
        """
        win_size = win_size if win_size else window.size

        tabs = self.tabs
        for tab in tabs:
            # Reset summary item attributes
            tab.resize_elements(window, win_size=win_size)

    def update_display(self, window):
        """
        Format summary item data elements for display.
        """
        default_col = const.ACTION_COL
        greater_col = const.PASS_COL
        lesser_col = const.FAIL_COL

        tabs = self.tabs
        for tab in tabs:
            # Update audit field with the tab document number
            doc_no = tab.id
            elem_size = len(doc_no) + 1

            no_key = tab.key_lookup('DocNo')
            window[no_key].set_size((elem_size, None))
            window[no_key].update(value=doc_no)

            # Reset column data types
            tab.set_datatypes()

            # Modify records tables for displaying
            print('Info: rule {RULE}, summary {NAME}: formatting records table for displaying'
                  .format(RULE=self.rule_name, NAME=tab.name))
            display_df = tab.format_display_table(table='records')
            data = display_df.values.tolist()

            tbl_key = tab.key_lookup('Table')
            window[tbl_key].update(values=data)

            # Modify totals tables for displaying
            print('Info: rule {RULE}, summary {NAME}: formatting totals table for displaying'
                  .format(RULE=self.rule_name, NAME=tab.name))
            totals_display_df = tab.format_display_table(table='totals')
            totals_data = totals_display_df.values.tolist()

            totals_key = tab.key_lookup('Totals')
            window[totals_key].update(values=totals_data)

            # Update summary totals elements
            total_key = tab.key_lookup('Total')
            tally_rule = tab.totals['TallyRule']

            if tally_rule:
                totals_sum = dm.evaluate_rule(tab.totals_df.iloc[[0]], tally_rule, as_list=False).sum()
            else:
                totals_sum = tab.totals_df.iloc[0].sum()

            window[total_key].update(value='{:,.2f}'.format(totals_sum))

            sum_column = tab.records['SumColumn']
            records_sum = tab.df[sum_column].sum()
            remainder = totals_sum - records_sum
            if remainder > 0:
                bg_color = greater_col
            elif remainder < 0:
                bg_color = lesser_col
            else:
                bg_color = default_col

            remain_key = tab.key_lookup('Remainder')
            window[remain_key].update(value='{:,.2f}'.format(remainder), background_color=bg_color)

            # Highlight rows with discrepancies
            tbl_error_col = const.TBL_ERROR_COL

            errors = tab.search_for_errors()
            error_colors = [(i, tbl_error_col) for i in errors]
            window[tbl_key].update(row_colors=error_colors)
            window.refresh()

            # Change edit note button to be highlighted if note field not empty
            note_key = tab.key_lookup('Note')
            note_text = tab.notes['Value']
            if note_text:
                window[note_key].update(image_data=const.EDIT_ICON)
            else:
                window[note_key].update(image_data=const.NOTES_ICON)

    def initialize_tables(self, rule):
        """
        Update summary item tables with data from tab item dataframes.
        """
        tabs = self.tabs
        for tab in tabs:
            tab.initialize_table(rule)

    def reset_attributes(self):
        """
        Reset summary item attributes.
        """
        tabs = self.tabs
        for tab in tabs:
            # Reset summary item attributes
            tab.reset_dynamic_attributes()

    def update_totals(self, rule):
        """
        Populate totals table with audit tab summary totals.
        """
        operators = set('+-*/')

        tabs = self.tabs
        for tab in tabs:
            name = tab.name
            totals = tab.totals
            df = tab.totals_df

            db_columns = totals['TableColumns']
            mapping_columns = totals['MappingColumns']
            edit_columns = totals['EditColumns']
            for column in db_columns:
                try:
                    reference = mapping_columns[column]
                except KeyError:
                    if column not in edit_columns:
                        print('Error: rule {RULE}, summary {NAME}: column {COL} not found in either mapping columns or '
                              'edit columns'.format(RULE=self.rule_name, NAME=name, COL=column))
                    df.at[0, column] = 0
                    df[column] = pd.to_numeric(df[column], downcast='float')
                    continue

                # Add audit tab summaries to totals table
                rule_values = []
                for component in dm.parse_operation_string(reference):
                    if component in operators:
                        rule_values.append(component)
                        continue

                    try:  # component is numeric
                        float(component)
                    except ValueError:
                        try:  # component is potentially a data table column
                            ref_table, ref_col = component.split('.')
                        except ValueError:  # unaccepted type
                            if component in edit_columns:
                                rule_values.append(0)
                                continue
                            else:
                                print('Error: rule {RULE}, summary {NAME}: unknown data type {COMP} in rule {REF}'
                                      .format(RULE=self.rule_name, NAME=name, COMP=component, REF=reference))
                                rule_values.append(0)
                                continue
                        else:
                            try:
                                tab_summary = rule.fetch_tab(ref_table).summary_rules
                            except AttributeError:
                                print('Error: rule {RULE}, summary {NAME}: tab item {TAB} not in list of Tabs'
                                      .format(RULE=self.rule_name, NAME=name, TAB=ref_table))
                                rule_values.append(0)
                                continue

                            if ref_col in tab_summary:
                                try:
                                    rule_values.append(tab_summary[ref_col]['Total'])
                                except KeyError:
                                    rule_values.append(0)
                            else:
                                print('Error: rule {RULE}, summary {NAME}: column {COL} not found in tab {TAB} summary'
                                      .format(RULE=self.rule_name, NAME=name, COL=ref_col, TAB=ref_table))
                                rule_values.append(0)

                    else:
                        rule_values.append(component)

                try:
                    summary_total = eval(' '.join([str(i) for i in rule_values]))
                except Exception as e:
                    print('Error: rule {RULE}, summary {NAME}: {ERR}'
                          .format(RULE=self.rule_name, NAME=tab.name, ERR=e))
                    summary_total = 0

                print('Info: rule {RULE}, summary {NAME}: adding {SUMM} to column {COL}'
                      .format(RULE=self.rule_name, NAME=name, SUMM=summary_total, COL=column))

                df.at[0, column] = summary_total
                df[column] = pd.to_numeric(df[column], downcast='float')

            tab.totals_df = df

    def update_static_fields(self, window, rule):
        """
        Update summary panel static fields to include audit parameters.
        """
        aliases = self.aliases

        params = rule.parameters

        # Update summary title with parameter values, if specified in title format
        try:
            title_components = re.findall(r'\{(.*?)\}', self._title)
        except TypeError:
            title_components = []
        else:
            print('Info: rule {RULE}, Summary: summary title components are {COMPS}'
                  .format(RULE=self.rule_name, COMPS=title_components))

        title_params = {}
        for param in params:
            param_col = param.name
            value = param.value_obj

            print('Info: rule {RULE}, Summary: value for summary parameter {PARAM} is {VAL}'
                  .format(RULE=self.rule_name, PARAM=param_col, VAL=value))

            # Check if parameter composes part of title
            if param_col in title_components:
                if param_col in aliases:
                    try:
                        final_val = aliases[param_col][value]
                    except KeyError:
                        print('Warning: rule {RULE}, Summary: value {VAL} not found in alias list for alias {ALIAS}'
                              .format(RULE=self.rule_name, VAL=value, ALIAS=param_col))
                        final_val = value
                else:
                    final_val = value

                print('Info: rule {RULE}, Summary: adding parameter value {VAL} to title'
                      .format(RULE=self.rule_name, VAL=final_val))

                if isinstance(final_val, datetime.datetime):
                    final_val = settings.apply_date_offset(final_val)
                    title_params[param_col] = final_val.strftime('%Y-%m-%d')
                else:
                    title_params[param_col] = final_val
            else:
                print('Warning: rule {RULE}, Summary: parameter {PARAM} not found in title'
                      .format(RULE=self.rule_name, PARAM=param_col))

        try:
            summ_title = self._title.format(**title_params)
        except KeyError as e:
            print('Error: rule {RULE}, Summary: formatting summary title failed due to {ERR}'
                  .format(RULE=self.rule_name, ERR=e))
            summ_title = self._title

        print('Info: rule {RULE}, Summary: formatted summary title is {TITLE}'
              .format(RULE=self.rule_name, TITLE=summ_title))

        title_key = self.key_lookup('Title')
        window[title_key].update(value=summ_title)

        # Add rule parameters to tab parameters
        for tab in self.tabs:
            tab.parameters = params

        self.title = summ_title

    def save_report(self, filename):
        """
        Generate summary report and save to a PDF file.
        """
        report_def = self.report

        tabs = []
        for tab_name in report_def:
            reference_tab = self.fetch_tab(tab_name)
            notes = reference_tab.notes
            tab_dict = {'title': reference_tab.title, 'notes': (notes['Title'], notes['Value'])}

            section_def = report_def[tab_name]
            sections = []
            for section_name in section_def:
                section = section_def[section_name]
                title = section['Title']

                # create a copy of the reference tab reports dataframe
                try:
                    reference_df = reference_tab.df.copy()
                except AttributeError:
                    print('Error: rule {RULE}, Summary Report: no such summary item "{SUMM}" found in list of summary '
                          'panel items'.format(RULE=self.rule_name, SUMM=section['ReferenceTable']))
                    continue
                else:
                    if reference_df.empty:
                        print('Warning: rule {RULE}, Summary Report, tab {NAME}: no records found'
                              .format(RULE=self.rule_name, NAME=tab_name))
                        continue

                # Subset rows based on subset rules in configuration
                try:
                    subset_df = dm.subset_dataframe(reference_df, section['Subset'])
                except KeyError:
                    subset_df = reference_df
                except (NameError, SyntaxError) as e:
                    print('Error: rule {RULE}, Summary Report: error in report item {NAME} with subset rule {SUB} - '
                          '{ERR}'.format(RULE=self.rule_name, NAME=section_name, SUB=section['Subset'], ERR=e))
                    continue
                else:
                    if subset_df.empty:
                        print('Warning: rule {RULE}, Summary Report, tab {NAME}: subsetting rule for section {SECTION} '
                              'removed all records'.format(RULE=self.rule_name, NAME=tab_name, SECTION=section_name))
                        continue

                # Select columns from list in configuration
                try:
                    subset_df = subset_df[section['Columns']]
                except KeyError as e:
                    print('Error: rule {RULE}, Summary Report: unknown column provided in report item {NAME} - {ERR}'
                          .format(RULE=self.rule_name, NAME=section_name, ERR=e))
                    continue

                # Index rows using grouping list in configuration
                try:
                    grouping = section['Group']
                except KeyError:
                    grouped_df = subset_df
                else:
                    grouped_df = subset_df.set_index(grouping).sort_index()

                html_str = grouped_df.to_html(header=False, index_names=False, float_format='{:,.2f}'.format,
                                              sparsify=True, na_rep='')

                # Highlight errors in html string
                error_col = const.TBL_ERROR_COL
                errors = reference_tab.search_for_errors(dataframe=grouped_df)
                try:
                    html_out = replace_nth(html_str, '<tr>', '<tr style="background-color: {}">'.format(error_col),
                                           errors)
                except Exception as e:
                    print('Warning: rule {RULE}, summary {NAME}: unable to apply error rule results to output - {ERR}'
                          .format(RULE=self.rule_name, NAME=reference_tab.name, ERR=e))
                    html_out = html_str

                sections.append((title, html_out))

            tab_dict['sections'] = sections
            tabs.append(tab_dict)

        css_url = settings.report_css
        template_vars = {'title': self.title, 'report_tabs': tabs}

        env = Environment(loader=FileSystemLoader(os.path.dirname(os.path.abspath(settings.report_template))))
        template = env.get_template(os.path.basename(os.path.abspath(settings.report_template)))
        html_out = template.render(template_vars)
        path_wkhtmltopdf = settings.wkhtmltopdf
        config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)
        try:
            pdfkit.from_string(html_out, filename, configuration=config, css=css_url,
                               options={'enable-local-file-access': None})
        except Exception as e:
            print('Error: rule {RULE}, Summary Report: writing to PDF failed - {ERR}'
                  .format(RULE=self.rule_name, ERR=e))
            status = False
        else:
            status = True

        return status

    def save_to_database(self, user):
        """
        Save results of an audit to the program database defined in the configuration file.
        """
        tabs = self.tabs

        success = []
        for tab in tabs:
            import_df = tab.import_df
            nrow = tab.df.shape[0]

            # Check if data already exists in database
            if not import_df.empty:
                if user.admin:  # must be admin to update existing data
                    # Verify that user would like to update the database table
                    msg = 'Some of the audit results already exist in the {TAB} database tables. Would you like to ' \
                          'replace the existing rows of data?'.format(TAB=tab.name)
                    update_table = win2.popup_confirm(msg)

                    if update_table == 'Cancel':
                        return False
                else:
                    msg = 'Audit results already exist in the summary database. Only an admin can update audit ' \
                          'records'
                    win2.popup_notice(msg)

                    return False

            # Assign IDs to records when filter rules apply
            for id_field in tab.ids:
                id_entry = tab.ids[id_field]

                if 'FilterRules' in id_entry:
                    tbl_filter_param = id_entry['FilterRules']
                    db_table = id_entry['DatabaseTable']
                    db_id_field = id_entry['DatabaseField']

                    import_ids = tab.import_df[id_field]

                    current_results = dm.evaluate_rule_set(tab.df, tbl_filter_param)
                    entry_ids = []
                    for row_index, result in enumerate(current_results):
                        # Determine if record already as an associated ID
                        current_id = tab.df.at[row_index, id_field]

                        if result is False and not pd.isna(current_id):  # row fails evaluation rule and has an ID
                            # Check if the ID has been saved in the database
                            if current_id in import_ids:  # row has an ID saved in the database table
                                print('Info: rule {RULE}, summary {NAME}: removing ID {ID} from database table {TBL}'
                                      .format(RULE=self.rule_name, NAME=tab.name, ID=current_id, TBL=db_table))
                                # Delete record from database
                                filters = ('{} = ?'.format(db_id_field), (current_id,))
                                cancelled = user.update(db_table, ['IsCancel'], [1], filters)

                                if cancelled is False:  # failed to update
                                    win2.popup_error('Warning: Failed to remove {ID}. Changes will not be saved to the '
                                                     'database table {TBL}'.format(ID=current_id, TBL=db_table))

                            print('Info: current ID for ID field {}, row {} is {}'.format(id_field, row_index,
                                                                                          current_id))
                            entry_ids.append(None)
                        elif result is False and pd.isna(current_id):  # row fails eval and does not have an ID
                            entry_ids.append(None)
                        elif result is True and not pd.isna(current_id):  # row passes eval and already has an ID
                            print('Info: rule {RULE}, summary {NAME}: current ID for table {TBL}, row {ROW} is {ID}'
                                  .format(RULE=self.rule_name, NAME=tab.name, TBL=db_table, ROW=row_index,
                                          ID=current_id))
                            entry_ids.append(current_id)
                        else:  # row passes evaluation rule and does not currently have an assigned ID
                            all_ids = current_tbl_pkeys[db_table]
                            current_ids = tab.df[id_field].dropna().unique().tolist()

                            print('INFO: rule {RULE}, summary {NAME}: list of currents IDs for ID {ID} is {LIST}'
                                  .format(RULE=self.rule_name, NAME=tab.name, ID=id_field, LIST=current_ids))
                            print('INFO: rule {RULE}, summary {NAME}: list of all IDs for ID {ID} is {LIST}'
                                  .format(RULE=self.rule_name, NAME=tab.name, ID=id_field, LIST=all_ids))

                            if id_entry['IsUnique'] is True:
                                record_id = tab.create_id(id_entry, all_ids)
                                print('Info: saving new record {ID} to list of table {TBL} IDs'
                                      .format(ID=record_id, TBL=db_table))
                                current_tbl_pkeys[db_table].append(record_id)
                            else:
                                if len(current_ids) > 0:
                                    record_id = current_ids[0]
                                else:
                                    record_id = tab.create_id(id_entry, all_ids)
                                    print('Info: saving new record {ID} to list of table {TBL} IDs'
                                          .format(ID=record_id, TBL=db_table))
                                    current_tbl_pkeys[db_table].append(record_id)

                            entry_ids.append(record_id)

                    # Add IDs to table
                    tab.df[id_field] = entry_ids

            # Iterate over output export rules
            export_rules = tab.export_rules
            if export_rules is None:  # tab exports no data
                continue

            for table in export_rules:
                table_fields = export_rules[table]

                references = table_fields['TableColumns']
                if 'Options' in table_fields:
                    options_param = table_fields['Options']
                else:
                    options_param = {}

                if 'IsAuditTable' in options_param:
                    try:
                        is_audit = bool(int(options_param['IsAuditTable']))
                    except ValueError:
                        print('Configuration Warning: rule {RULE}, summary {NAME}: the "IsAuditTable" options parameter'
                              ' must be either 0 (False) or 1 (True)'.format(RULE=self.rule_name, NAME=tab.name))
                        is_audit = False
                else:
                    is_audit = False

                # Populate the output dataframe with defined column values stored in the totals and records tables
                df = pd.DataFrame(columns=list(references.keys()))

                for column in references:
                    reference = references[column]
                    try:
                        ref_tbl, ref_col = reference.split('.')
                    except ValueError:
                        print('Warning: Rule {RULE}, Summary {TAB}: invalid format for reference {REF}'
                              .format(RULE=self.rule_name, TAB=tab.name, REF=column))
                        continue

                    if ref_tbl == 'Records':
                        try:
                            ref_series = tab.df[ref_col]
                        except KeyError:
                            print('Warning: Rule {RULE}, Summary {TAB}: column {COL} does not exist in reference table '
                                  '{TBL}'.format(RULE=self.rule_name, TAB=tab.name, COL=ref_col, TBL=ref_tbl))
                            continue
                    elif ref_tbl == 'Totals':
                        try:
                            ref_value = tab.totals_df.at[0, ref_col]
                        except KeyError:
                            print('Warning: Rule {RULE}, Summary {TAB}: column {COL} does not exist in reference table '
                                  '{TBL}'.format(RULE=self.rule_name, TAB=tab.name, COL=ref_col, TBL=ref_tbl))
                            continue
                        else:
                            ref_series = pd.Series([ref_value for _ in range(nrow)])
                    else:
                        print('Warning: Rule {RULE}, Summary {TAB}: reference table {TBL} does not exist'
                              .format(RULE=self.rule_name, TAB=tab.name, TBL=ref_tbl))
                        continue

                    if is_audit is True:
                        if len(ref_series.dropna().unique().tolist()) > 1:
                            print(ref_series)
                            print('Warning: rule {RULE}, summary {NAME}: the "IsAuditTable" parameter was selected '
                                  'for output table {TABLE} but the reference column "{REF}" has more than one unique '
                                  'value. Using first value encountered in {COL}'
                                  .format(RULE=self.rule_name, NAME=tab.name, TABLE=table, REF=ref_col, COL=column))

                        ref_value = ref_series.dropna().iloc[0]
                        df.at[0, column] = ref_value
                    else:
                        df[column] = ref_series

                print(df)

                # Add additional fields defined in config (reference IDs and static fields)
                if 'AddNote' in options_param:
                    try:
                        row_reference = bool(int(options_param['AddNote']))
                    except ValueError:
                        row_reference = None

                    if row_reference is True:
                        notes_field = tab.notes['Field']
                        notes_value = tab.notes['Value']
                        df[notes_field] = notes_value

                # Prepare the ID mapping between database table and dataframe
                db_id_field = None
                import_id_field = None
                for id_field in tab.ids:
                    id_param = tab.ids[id_field]
                    db_table = id_param['DatabaseTable']
                    if db_table == table:
                        db_id_field = id_param['DatabaseField']
                        import_id_field = id_field
                        break

                if db_id_field is None or import_id_field is None:
                    msg = 'Configuration Error: rule {RULE}, summary {NAME}: Export Database table {TBL} is missing' \
                          ' an entry in the IDs parameter'.format(RULE=tab.rule_name, NAME=tab.name, TBL=table)
                    win2.popup_error(msg)
                    sys.exit(1)

                # Update database with records
                import_record_ids = import_df[import_id_field].dropna().unique().tolist()
                for index, row in df.iterrows():
                    try:
                        row_id = row[db_id_field]
                    except KeyError:
                        print('Error: rule {RULE}, summary {NAME}: cannot find column {COL} in summary records table'
                              .format(RULE=self.rule_name, NAME=tab.name, COL=import_id_field))
                        print(row)
                        sys.exit(1)
                    else:
                        if pd.isna(row_id):  # row has no associated primary key, don't save to database
                            continue

                        print('Info: rule {RULE}, summary {NAME}: saving record {ID} to database table {TBL}'
                              .format(RULE=self.rule_name, NAME=tab.name, ID=row_id, TBL=table))

                    if row_id in import_record_ids:  # record already exists in database table
                        # Add editor information
                        row[settings.editor_code] = user.uid
                        row[settings.edit_date] = datetime.datetime.now().strftime(settings.format_date_str())

                        # Prepare update parameters
                        row_columns = row.index.tolist()
                        row_values = row.replace({np.nan: None}).values.tolist()

                        # Update existing record in table
                        filters = ('{} = ?'.format(db_id_field), (row_id,))
                        success.append(user.update(table, row_columns, row_values, filters))
                    else:  # new record created
                        # Add creator information
                        row[settings.creator_code] = user.uid
                        row[settings.creation_date] = datetime.datetime.now().strftime(settings.format_date_str())

                        # Prepare insertion parameters
                        row_columns = row.index.tolist()
                        row_values = row.replace({np.nan: None}).values.tolist()

                        # Insert new record into table
                        success.append(user.insert(table, row_columns, row_values))

                # Update removed records, if they already exist in the database table
                removed_records = tab.removed_df[import_id_field].dropna().unique().tolist()
                for record_id in removed_records:
                    if record_id not in import_record_ids:  # expense doesn't exist in database yet, no need to save
                        continue

                    if record_id == tab.id:  # user's cannot delete the audit record through this mechanism
                        continue

                    # Update the records removed from the transaction
                    filters = ('{} = ?'.format(db_id_field), (record_id,))
                    cancelled = user.update(table, ['IsCancel'], [1], filters)

                    if cancelled is False:
                        win2.popup_error(
                            'Warning: Failed to remove {ID}. Changes will not be saved to the database table {TBL}'
                            .format(ID=record_id, TBL=table))

        return all(success)

    def load_from_database(self, user, parameters):
        """
        Load previous audit from the program database.
        """
        exists = []
        for tab in self.tabs:
            exists.append(tab.load_from_database(user, parameters))

        return all(exists)


class SummaryItem:
    """
    """

    def __init__(self, rule_name, name, sdict):

        self.rule_name = rule_name
        self.name = name
        self.element_key = lo.as_key('{RULE} Summary {NAME}'.format(RULE=rule_name, NAME=name))
        self.elements = ['DocNo', 'Totals', 'Table', 'Add', 'Delete', 'Total', 'Remainder', 'TabHeight', 'Note']
        self.type = None

        try:
            self.title = sdict['Title']
        except KeyError:
            self.title = '{} Summary'.format(name)

        try:
            ids = sdict['IDs']
        except KeyError:
            win2.popup_error('Configuration Error: rule {RULE}, summary {NAME}: missing required parameter "IDs"'
                             .format(RULE=self.rule_name, NAME=self.name))
            sys.exit(1)

        if len(ids) < 1:
            win2.popup_error('Configuration Error: rule {RULE}, summary {NAME}: "IDs" must include at least one '
                             'primary ID field'.format(RULE=self.rule_name, NAME=self.name))
            sys.exit(1)

        has_primary = False
        for id_field in ids:
            id_param = ids[id_field]

            if 'Title' not in id_param:
                id_param['Title'] = id_field
            if 'Format' not in id_param:
                win2.popup_error('Configuration Error: rule {RULE}, summary {NAME}: "Format" is a required field for '
                                 'IDs entry "{ID}"'.format(RULE=self.rule_name, NAME=self.name, ID=id_field))
                sys.exit(1)
            else:
                id_param['Format'] = re.findall(r'\{(.*?)\}', id_param['Format'])
            if 'DatabaseTable' not in id_param:
                win2.popup_error('Configuration Error: rule {RULE}, summary {NAME}: "DatabaseTable" is a required '
                                 'field for IDs entry "{ID}"'.format(RULE=self.rule_name, NAME=self.name, ID=id_field))
                sys.exit(1)
            if 'DatabaseField' not in id_param:
                win2.popup_error('Configuration Error: rule {RULE}, summary {NAME}: "DatabaseField" is a required '
                                 'field for IDs entry "{ID}"'.format(RULE=self.rule_name, NAME=self.name, ID=id_field))
                sys.exit(1)
            if 'IsUnique' not in id_param:
                id_param['IsUnique'] = False
            else:
                try:
                    is_unique = bool(int(id_param['IsUnique']))
                except ValueError:
                    win2.popup_error('Configuration Error: rule {RULE}, summary {NAME}: "IsUnique" must be either 0 '
                                     '(False) or 1 (True)'.format(RULE=self.rule_name, NAME=self.name))
                    sys.exit(1)
                else:
                    id_param['IsUnique'] = is_unique
            if 'IsPrimary' not in id_param:
                id_param['IsPrimary'] = False
            else:
                try:
                    is_primary = bool(int(id_param['IsPrimary']))
                except ValueError:
                    win2.popup_error('Configuration Error: rule {RULE}, summary {NAME}: "IsPrimary" must be either 0 '
                                     '(False) or 1 (True)'.format(RULE=self.rule_name, NAME=self.name))
                    sys.exit(1)
                else:
                    id_param['IsPrimary'] = is_primary
                    if is_primary is True:
                        if has_primary is True:
                            win2.popup_error('Configuration Error: rule {RULE}, summary {NAME}: only one "IDs" '
                                             'parameter can be set as the primary ID field'
                                             .format(RULE=self.rule_name, NAME=self.name))
                            sys.exit(1)
                        else:
                            has_primary = True

        if has_primary is False:
            win2.popup_error('Configuration Error: rule {RULE}, summary {NAME}: "IDs" must include at least one '
                             'primary ID field'.format(RULE=self.rule_name, NAME=self.name))

        self.ids = ids

        try:
            self.export_rules = sdict['ExportRules']
        except KeyError:
            self.export_rules = None

        try:
            self.import_rules = sdict['ImportRules']
        except KeyError:
            self.import_rules = None

        try:
            all_columns = sdict['TableColumns']
        except KeyError:
            msg = 'Configuration Error: rule {RULE}, summary {NAME}: missing required field "TableColumns".'\
                .format(NAME=name, RULE=rule_name)
            win2.popup_error(msg)
            sys.exit(1)
        self.db_columns = all_columns

        try:
            records = sdict['Records']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}, summary {NAME}: missing required parameter "Records".') \
                .format(RULE=rule_name, NAME=name)
            win2.popup_error(msg)
            sys.exit(1)
        msg = _('Configuration Error: rule {RULE}, summary {NAME}: missing required field "{FIELD}" '
                'in the "Records" parameter.')
        if 'TableColumns' not in records:
            win2.popup_error(msg.format(RULE=rule_name, NAME=name, FEILD='TableColumns'))
            sys.exit(1)
        if 'SumColumn' not in records:
            win2.popup_error(msg.format(RULE=rule_name, NAME=name, FEILD='SumColumn'))
            sys.exit(1)
        else:
            if records['SumColumn'] not in records['TableColumns']:
                win2.popup_error('Configuration Error: rule {RULE}, name {NAME}: SumColumn {SUM} not in list of table '
                                 'columns'.format(RULE=rule_name, NAME=name, SUM=records['SumColumn']))
                sys.exit(1)
        if 'DisplayHeader' not in records:
            records['DisplayHeader'] = ''
        if 'DisplayColumns' not in records:
            win2.popup_error(msg.format(RULE=rule_name, NAME=name, FEILD='DisplayColumns'))
            sys.exit(1)
        if 'MappingColumns' not in records:
            records['MappingColumns'] = {}
        if 'ReferenceTables' not in records:
            records['ReferenceTables'] = {}
        if 'EditColumns' not in records:
            records['EditColumns'] = {}
        if 'StaticColumns' not in records:
            records['StaticColumns'] = {}

        self.records = records

        try:
            totals = sdict['Totals']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}, summary {NAME}: missing required parameter "Totals".') \
                .format(RULE=rule_name, NAME=name)
            win2.popup_error(msg)
            sys.exit(1)

        msg = _('Configuration Error: rule {RULE}, summary {NAME}: missing required field "{FIELD}" '
                'in the "Totals" parameter.')
        if 'TableColumns' not in totals:
            win2.popup_error(msg.format(RULE=rule_name, NAME=name, FEILD='TableColumns'))
            sys.exit(1)
        if 'DisplayHeader' not in totals:
            totals['DisplayHeader'] = ''
        if 'DisplayColumns' not in totals:
            win2.popup_error(msg.format(RULE=rule_name, NAME=name, FEILD='DisplayColumns'))
            sys.exit(1)
        if 'MappingColumns' not in totals:
            totals['MappingColumns'] = {}
        if 'EditColumns' not in totals:
            totals['EditColumns'] = {}
        if 'TallyRule' not in totals:
            totals['TallyRule'] = None

        self.totals = totals

        try:
            notes = sdict['Notes']
        except KeyError:
            notes = {}
        if 'Title' not in notes:
            notes['Title'] = "Notes"
        if 'Field' not in notes:
            notes['Field'] = "Notes"
        notes['Value'] = ''

        self.notes = notes

        try:
            self.error_rules = sdict['ErrorRules']
        except KeyError:
            self.error_rules = {}

        try:
            self.aliases = sdict['Aliases']
        except KeyError:
            self.aliases = []

        try:
            self.tab_parameters = sdict['TabParameters']
        except KeyError:
            self.tab_parameters = None

        # Dynamic attributes
        self.df = self.import_df = self.removed_df = None

        totals_header = list(set(list(totals['MappingColumns'].keys()) + list(totals['EditColumns'].keys())))
        self.totals_df = pd.DataFrame(columns=totals_header)

        self.id = None
        self.parameters = None

    def reset_dynamic_attributes(self):
        """
        Reset Summary values.
        """
        header = self.df.columns.values
        self.df = self.import_df = self.removed_df = pd.DataFrame(columns=header)

        totals_header = self.totals_df.columns.values
        self.totals_df = pd.DataFrame(columns=totals_header)

        self.id = None
        self.parameters = None
        self.notes['Value'] = ''

    def reset_tables(self):
        """
        Reset Summary tables.
        """
        header = self.df.columns.values
        self.df = self.removed_df = pd.DataFrame(columns=header)

        totals_header = self.totals_df.columns.values
        self.totals_df = pd.DataFrame(columns=totals_header)

    def remove_unsaved_keys(self):
        """
        Remove unsaved IDs from the table IDs lists.
        """
        for id_field in self.ids:
            id_param = self.ids[id_field]
            db_table = id_param['DatabaseTable']
            print('Removing created ids in tab {} from table {} with id field {}'.format(self.name, db_table, id_field))

            all_ids = self.df[id_field].dropna().unique().tolist()
            existing_ids = self.import_df[id_field].dropna().unique().tolist()
            created_ids = set(all_ids).difference(set(existing_ids))
            print(all_ids)
            print(existing_ids)
            print(created_ids)

            for record_id in created_ids:
                try:
                    current_tbl_pkeys[db_table].remove(record_id)
                except ValueError:
                    print('Warning: attempting to remove non-existent ID "{ID}" from the list of '
                          'database table {TBL} IDs'.format(ID=record_id, TBL=db_table))
                    continue
                else:
                    print('Info: removed ID {ID} from the list of database table {TBL} IDs'
                          .format(ID=record_id, TBL=db_table))

    def key_lookup(self, element):
        """
        Lookup element key for input control element.
        """
        if element in self.elements:
            key = lo.as_key('{RULE} Summary {NAME} {ELEM}'.format(RULE=self.rule_name, NAME=self.name, ELEM=element))
        else:
            print('Warning: rule {RULE}, summary {NAME}: unable to find GUI element {ELEM} in list of elements'
                  .format(RULE=self.rule_name, NAME=self.name, ELEM=element))
            key = None

        return key

    def set_datatypes(self):
        """
        Set column data types based on header mapping
        """
        df = self.df.copy()
        header_map = self.records['TableColumns']

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
                print('Warning: rule {RULE}, summary {NAME}: unable to set column {COL} to data type {DTYPE}'
                      .format(RULE=self.rule_name, NAME=self.name, COL=column, DTYPE=dtype))

        self.df = df

    def layout(self, win_size: tuple = None):
        """
        GUI layout for the summary item.
        """
        if win_size:
            width, height = win_size
        else:
            width, height = (const.WIN_WIDTH, const.WIN_HEIGHT)

        display_columns = self.records['DisplayColumns']
        totals_columns = self.totals['DisplayColumns']

        # Window and element size parameters
        bg_col = const.ACTION_COL
        header_col = const.HEADER_COL
        text_col = const.TEXT_COL

        font = const.MID_FONT
        font_b = const.BOLD_MID_FONT

        pad_frame = const.FRAME_PAD
        pad_el = const.ELEM_PAD
        pad_v = const.VERT_PAD

        tbl_pad = (0, 0)

        # Layout
        # Tab header
        for id_field in self.ids:
            id_param = self.ids[id_field]
            if id_param['IsPrimary'] is True:
                tab_title = id_param['Title']
                break

        no_key = self.key_lookup('DocNo')
        note_key = self.key_lookup('Note')
        header_layout = [
            [sg.Frame('', [
                     [sg.Text('{}:'.format(tab_title), pad=((pad_el*2, pad_el), pad_el*2), font=font_b,
                              background_color=bg_col),
                      sg.Text('', key=no_key, size=(20, 1), pad=((pad_el, pad_el*2), pad_el*2), justification='l',
                              font=font, background_color=bg_col, auto_size_text=True, border_width=0)]],
                      pad=(0, 0), background_color=header_col, border_width=2, relief='raised'),
             sg.Col([[sg.Button('', key=note_key, pad=(0, 0), image_data=const.NOTES_ICON, visible=True,
                                button_color=(text_col, bg_col), border_width=0, tooltip=self.notes['Title'])]],
                    pad=(pad_v, 0), background_color=bg_col, vertical_alignment='c')]]

        # Data tables
        records_header = list(display_columns.keys())
        totals_header = list(totals_columns.keys())

        records_title = self.records['DisplayHeader']
        tbl_key = self.key_lookup('Table')
        add_key = self.key_lookup('Add')
        delete_key = self.key_lookup('Delete')
        remain_key = self.key_lookup('Remainder')
        data = dm.create_empty_table(nrow=5, ncol=len(records_header))
        records_layout = [[lo.create_table_layout(data, records_header, tbl_key, bind=True, height=height, width=width,
                                                  pad=tbl_pad, add_key=add_key, delete_key=delete_key,
                                                  table_name=records_title)],
                          [sg.Col([[sg.Text('Remainder:', pad=((0, pad_el), 0), font=font_b, background_color=bg_col),
                                    sg.Text('', key=remain_key, size=(14, 1), pad=((pad_el, 0), 0), font=font,
                                            background_color=bg_col, justification='r', relief='sunken')]],
                                  pad=(0, (pad_v, 0)), background_color=bg_col, justification='r')], ]

        totals_title = self.totals['DisplayHeader']
        totals_data = dm.create_empty_table(nrow=1, ncol=len(totals_header))
        totals_key = self.key_lookup('Totals')
        total_key = self.key_lookup('Total')
        totals_layout = [[lo.create_table_layout(totals_data, totals_header, totals_key, bind=True, height=height,
                                                 width=width, nrow=1, pad=tbl_pad, table_name=totals_title)],
                         [sg.Col([[sg.Text('Total:', pad=((0, pad_el), 0), font=font_b, background_color=bg_col),
                                   sg.Text('', key=total_key, size=(14, 1), pad=((pad_el, 0), 0), font=font,
                                           background_color=bg_col, justification='r', relief='sunken')]],
                                 pad=(0, (pad_v, 0)), background_color=bg_col, justification='r')]]

        main_layout = [
            [sg.Col(header_layout, pad=(pad_frame, (pad_frame, pad_v)), background_color=bg_col, expand_x=False)],
            [sg.Col(totals_layout, pad=(pad_frame, pad_v), background_color=bg_col)],
            [sg.Col(records_layout, pad=(pad_frame, (pad_v, pad_frame)), background_color=bg_col)]]

        height_key = self.key_lookup('TabHeight')
        frame_height = height * 0.8
        layout = [[sg.Canvas(key=height_key, size=(0, frame_height * 0.70)),
                   sg.Col(main_layout, pad=(0, 0), justification='l', vertical_alignment='t',
                          background_color=bg_col, expand_x=True)]]

        return layout

    def resize_elements(self, window, win_size: tuple = None):
        """
        Reset Tab width to default when resized.
        """
        if win_size:
            width, height = win_size
        else:
            width, height = (const.WIN_WIDTH, const.WIN_HEIGHT)

        tbl_key = self.key_lookup('Table')
        totals_key = self.key_lookup('Totals')
        element_key = self.element_key  # Tab item key

        # Reset table size
        # For every five-pixel increase in window size, increase tab size by one
        tab_pad = 120
        win_diff = width - const.WIN_WIDTH
        tab_pad = int(tab_pad + (win_diff / 5))

        frame_width = width - tab_pad if tab_pad > 0 else width
        tab_width = frame_width - 40
        window.bind("<Configure>", window[element_key].Widget.config(width=tab_width))

        layout_height = height * 0.8
        tab_height = layout_height * 0.70
        height_key = self.key_lookup('TabHeight')
        window[height_key].set_size((None, tab_height))

        # Reset table column sizes
        record_columns = self.records['DisplayColumns']
        header = list(record_columns.keys())

        tbl_width = tab_width - 42
        lengths = dm.calc_column_widths(header, width=tbl_width, pixels=True)
        for col_index, col_name in enumerate(header):
            col_width = lengths[col_index]
            window[tbl_key].Widget.column(col_name, width=col_width)

        window[tbl_key].expand((True, True))
        window[tbl_key].table_frame.pack(expand=True, fill='both')

        totals_columns = self.totals['DisplayColumns']
        totals_header = list(totals_columns.keys())
        lengths = dm.calc_column_widths(totals_header, width=tbl_width, pixels=True)
        for col_index, col_name in enumerate(totals_header):
            col_width = lengths[col_index]
            window[totals_key].Widget.column(col_name, width=col_width)

        window[totals_key].expand((True, True))
        window[totals_key].table_frame.pack(expand=True, fill='both')

        window.refresh()

        # Expand 1 row every 40 pixel increase in window size
        height_diff = int((height - const.WIN_HEIGHT) / 40)
        nrows = 3 + height_diff if height_diff > -3 else 1
        window[totals_key].update(num_rows=1)
        window[tbl_key].update(num_rows=nrows)

    def fetch_parameter(self, name, by_key: bool = False, by_type: bool = False):
        """
        """
        if by_key and by_type:
            print('Warning: rule {RULE}, summary {NAME}, parameter {PARAM}: the "by_key" and "by_type" arguments are '
                  'mutually exclusive. Defaulting to "by_key".'.format(RULE=self.rule_name, NAME=self.name, PARAM=name))
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

    def update_id_components(self, id_param):
        """
        Update the IDs attribute to include a list of component lengths.
        """
        parameters = self.parameters
        param_fields = [i.name for i in parameters]

        id_format = id_param['Format']

        last_index = 0
        id_components = []
        for component in id_format:
            if len(component) > 1 and set(component).issubset(set('YMD-/ ')):  # component is datestr
                component_len = len(component)
                index = (last_index, last_index + component_len)
                part_tup = ('date', component, index)
            elif component in param_fields:
                param = parameters[param_fields.index(component)]
                value = param.value
                component_len = len(value)
                index = (last_index, last_index + component_len)
                part_tup = (component, value, index)
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

    def get_id_component(self, identifier, component, id_param):
        """
        Extract the specified component values from the provided identifier.
        """
        id_components = self.update_id_components(id_param)

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

    def create_id(self, id_param, prev_ids):
        """
        Create a new ID based on a list of previous IDs.
        """
        param_fields = [i.name for i in self.parameters]
        id_format = id_param['Format']

        # Determine date parameter of the new ID
        date_param = self.fetch_parameter('date', by_type=True)
        if date_param:
            date = settings.apply_date_offset(date_param.value_obj)
        else:
            date = settings.apply_date_offset(datetime.datetime.now())

        id_date = date.strftime(settings.format_date_str())
        for component in id_format:
            if len(component) > 1 and set(component).issubset(set('YMD-/ ')):  # component is datestr
                date_fmt = settings.format_date_str(date_str=component)

                id_date = date.strftime(date_fmt)

        # Search list of used IDs occurring within the current date cycle
        if len(prev_ids) > 0:
            used_ids = []
            for prev_id in prev_ids:
                prev_date = self.get_id_component(prev_id, 'date', id_param)
                if prev_date == id_date:
                    used_ids.append(prev_id)

            if len(used_ids) > 0:
                last_id = sorted(used_ids)[-1]
                print('Info: rule {RULE}, summary {NAME}: last ID encountered is {ID}'
                      .format(RULE=self.rule_name, NAME=self.name, ID=last_id))
                try:
                    last_var = int(self.get_id_component(last_id, 'variable', id_param))
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

    def assign_record_ids(self, df, index, id_entries: list = None):
        """
        Create and assign new IDs for the audit summary item records.
        """
        id_entries = id_entries if id_entries is not None else self.ids

        # Create identifiers as defined in the configuration
        for id_field in id_entries:
            id_param = id_entries[id_field]
            db_table = id_param['DatabaseTable']

            if 'FilterRules' in id_param:  # don't create IDs for entries with specified filter rules
                continue

            all_ids = current_tbl_pkeys[db_table]
            current_ids = df[id_field].dropna().unique().tolist()

            print('INFO: rule {RULE}, summary {NAME}: list of currents IDs for ID {ID} is {LIST}'
                  .format(RULE=self.rule_name, NAME=self.name, ID=id_field, LIST=current_ids))
            print('INFO: rule {RULE}, summary {NAME}: list of all IDs for ID {ID} is {LIST}'
                  .format(RULE=self.rule_name, NAME=self.name, ID=id_field, LIST=all_ids))

            if id_param['IsUnique'] is True:
                record_id = self.create_id(id_param, all_ids)
                print(
                    'Info: saving new record {ID} to list of table {TBL} IDs'.format(ID=record_id, TBL=db_table))
                current_tbl_pkeys[db_table].append(record_id)
            else:
                if len(current_ids) > 0:
                    record_id = current_ids[0]
                else:
                    record_id = self.create_id(id_param, all_ids)
                    print(
                        'Info: saving new record {ID} to list of table {TBL} IDs'.format(ID=record_id, TBL=db_table))
                    current_tbl_pkeys[db_table].append(record_id)

            print('Info: rule {RULE}, summary {NAME}: adding record ID {ID} to the summary table row {INDEX}, column '
                  '{COL}'.format(RULE=self.rule_name, NAME=self.name, ID=record_id, INDEX=index, COL=id_field))
            df.at[index, id_field] = record_id

            if id_param['IsPrimary'] is True and self.id is None:
                print('Info: rule {RULE}, summary {NAME}: the identifier for the audit is {ID}'
                      .format(RULE=self.rule_name, NAME=self.name, ID=record_id))
                self.id = record_id

        return df

    def add_row(self, win_size: tuple = None):
        """
        Add a new row to the records table.
        """
        df = self.df.copy()
        edit_columns = self.records['EditColumns']
        display_columns = self.records['DisplayColumns']

        header = df.columns.values.tolist()

        # Initialize new empty row
        nrow = df.shape[0]
        new_index = nrow - 1 + 1  # first index starts at 0

        df = df.append(pd.Series(), ignore_index=True)

        # Create identifiers for the new row
        df = self.assign_record_ids(df, new_index)

        id_map = {}
        for id_field in self.ids:
            id_map[id_field] = df.at[new_index, id_field]

        # Update the amounts column
        sum_column = self.records['SumColumn']
        df.at[new_index, sum_column] = 0.0

        # Fill in the parameters columns
        params = self.parameters
        for param in params:
            column = param.alias
            if column in header:
                df.at[new_index, column] = param.value_obj

        # Fill in other columns
        df = dm.fill_na(df)

        # Display the add row window
        display_map = {display_columns[i]: i for i in display_columns}
        df = win2.modify_record(df, new_index, edit_columns, header_map=display_map, win_size=win_size, edit=False)

        # Remove IDs from list of table IDs if record creation cancelled
        if nrow + 1 != df.shape[0]:  # new record creation cancelled
            for id_field in self.ids:
                id_param = self.ids[id_field]
                db_table = id_param['DatabaseTable']

                if id_param['IsPrimary'] is True:  # don't remove primary audit ID
                    continue
                else:
                    id_value = id_map[id_field]

                # Remove from list of used IDs
                try:
                    current_tbl_pkeys[db_table].remove(id_value)
                except ValueError:
                    print('Warning: attempting to remove non-existent ID "{ID}" from the list of database '
                          'table {TBL} IDs'.format(ID=id_value, TBL=db_table))
                    continue
                else:
                    print('Info: removed cancelled record {ID} from list of table {TBL} IDs'
                          .format(ID=id_value, TBL=db_table))
        else:
            print(df.iloc[new_index])

        self.df = df

    def edit_row(self, index, element_key, win_size: tuple = None):
        """
        Edit row using modify record window.
        """
        if element_key == self.key_lookup('Table'):
            parameter = self.records
            df = self.df.copy()
            table = 'records'
        elif element_key == self.key_lookup('Totals'):
            parameter = self.totals
            df = self.totals_df.copy()
            table = 'totals'
        else:
            raise KeyError('element key {} does not correspond to either the Totals or Records tables'
                           .format(element_key))

        display_columns = parameter['DisplayColumns']
        edit_columns = parameter['EditColumns']

        display_map = {display_columns[i]: i for i in display_columns}
        df = win2.modify_record(df, index, edit_columns, header_map=display_map, win_size=win_size, edit=True)

        if table == 'records':
            self.df = df
        elif table == 'totals':
            self.totals_df = df

    def remove_row(self, index):
        """
        Remove row from tab records table.
        """
        df = self.df.copy()
        removed_df = self.removed_df.copy()

        # Remove IDs of the deleted record from the list of table IDs if not already saved in database
        for id_field in self.ids:
            id_param = self.ids[id_field]
            db_table = id_param['DatabaseTable']

            record_ids = df[id_field][index]
            existing_expenses = self.import_df[id_field].values.tolist()
            for record_id in record_ids:
                if record_id not in existing_expenses:
                    try:
                        current_tbl_pkeys[db_table].remove(record_id)
                    except ValueError:
                        print('Warning: attempting to remove non-existent ID "{ID}" from the list of database '
                              'table {TBL} IDs'.format(ID=record_id, TBL=db_table))
                        continue
                    else:
                        print('Info: removed ID {ID} from the list of database table {TBL} IDs'
                              .format(ID=record_id, TBL=db_table))

        # Add row to the dataframe of removed expenses
        removed_df = removed_df.append(df.iloc[index], ignore_index=True)
        removed_df.reset_index(drop=True, inplace=True)

        # Drop row from the dataframe of included expenses
        df.drop(index, axis=0, inplace=True)
        df.reset_index(drop=True, inplace=True)

        self.removed_df = removed_df
        self.df = df

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
            dataframe = self.df
            display_columns = self.records['DisplayColumns']
            display_header = list(display_columns.keys())
        else:
            dataframe = self.totals_df
            display_columns = self.totals['DisplayColumns']
            display_header = list(display_columns.keys())

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

        # Map column values to the aliases specified in the configuration
        for alias_col in self.aliases:
            alias_map = self.aliases[alias_col]  # dictionary of mapped values

            if alias_col not in display_header:
                print('Warning: rule {RULE}, tab {NAME}: alias {ALIAS} not found in the list of display columns'
                      .format(NAME=self.name, RULE=self.rule_name, ALIAS=alias_col))
                continue

            print('Info: rule {RULE}, tab {NAME}: applying aliases {MAP} to {COL}'
                  .format(NAME=self.name, RULE=self.rule_name, MAP=alias_map, COL=alias_col))

            try:
                display_df[alias_col].replace(alias_map, inplace=True)
            except KeyError:
                print('Warning: rule {RULE}, tab {NAME}: alias {ALIAS} not found in the list of display columns'
                      .format(NAME=self.name, RULE=self.rule_name, ALIAS=alias_col))
                continue

        return display_df

    def search_for_errors(self, dataframe=None):
        """
        Use error rules specified in configuration file to annotate rows.
        """
        error_rules = self.error_rules
        df = dataframe if dataframe is not None else self.df
        if df.empty:
            return set()

        errors = []

        # Search for errors in the data based on the defined error rules
        print('Info: rule {RULE}, summary {NAME}: searching for errors based on defined error rules {RULES}'
              .format(NAME=self.name, RULE=self.rule_name, RULES=error_rules))

        results = dm.evaluate_rule_set(df, error_rules)
        for row, result in enumerate(results):
            if result is False:
                print('Info: rule {RULE}, summary {NAME}: table row {ROW} failed one or more condition rule'
                      .format(RULE=self.rule_name, NAME=self.name, ROW=row))
                errors.append(row)

        return set(errors)

    def load_from_database(self, user, params):
        """
        Load previous audit (if exists) and IDs from the program database.
        """
        # Find primary audit ID
        for id_field in self.ids:
            id_param = self.ids[id_field]

            if id_param['IsPrimary'] is True:
                primary_id_field = id_field
                break

        # Prepare the filter rules to filter query results
        main_table = [i for i in self.import_rules][0]
        filters = [i.filter_statement(table=main_table) for i in params]

        # Check for tab-specific query parameters
        filters += self.filter_statements()

        # Query database table for the selected parameters
        df = user.query(self.import_rules, columns=self.db_columns, filter_rules=filters, prog_db=True)

        self.import_df = df
        self.df = self.removed_df = pd.DataFrame(columns=df.columns.values)

        if df.empty:  # data does not exist in the database already
            return False
        else:
            # Find audit ID in existing data
            self.id = df[primary_id_field].dropna().unique()[0]
            print('Info: rule {RULE}, summary {NAME}: the identity of the existing audit is: {ID}'
                  .format(RULE=self.rule_name, NAME=self.name, ID=self.id))

            # Determine if audit has existing notes attached
            notes_field = self.notes['Field']
            try:
                note_series = df[notes_field]
            except KeyError:
                note_value = ''
            else:
                note_value = note_series.dropna().unique().tolist()[0]

            self.notes['Value'] = note_value

            return True

    def filter_statements(self):
        """
        Generate the filter statements for tab query parameters.
        """
        operators = {'>', '>=', '<', '<=', '=', '!=', 'IN', 'in', 'In'}

        params = self.tab_parameters
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
                            'Error: rule {RULE}, tab {NAME}: only one operator allowed in tab parameters for parameter '
                            '{PARAM}'.format(RULE=self.rule_name, NAME=self.name, PARAM=param_col))
                        break
                else:
                    param_values.append(component)

            if not (param_oper and param_values):
                print('Error: rule {RULE}, tab {NAME}: tab parameter {PARAM} requires both an operator and a value'
                      .format(RULE=self.rule_name, NAME=self.name, PARAM=param_col))
                break

            if param_oper.upper() == 'IN':
                vals_fmt = ', '.join(['?' for i in param_values])
                filters.append(('{COL} {OPER} ({VALS})'.format(COL=param_col, OPER=param_oper, VALS=vals_fmt),
                                (param_values,)))
            else:
                if len(param_values) == 1:
                    filters.append(('{COL} {OPER} ?'.format(COL=param_col, OPER=param_oper), (param_values[0],)))
                else:
                    print('Error: rule {RULE}, tab {NAME}: tab parameter {PARAM} has too many values {COND}'
                          .format(RULE=self.rule_name, NAME=self.name, PARAM=param_col, COND=param_rule))
                    break

        return filters

    def update_edit_columns(self, df):
        """
        Update empty table cells with editable column default values.
        """
        edit_columns = self.records['EditColumns']
        for edit_column in edit_columns:
            edit_item = edit_columns[edit_column]
            try:
                default_rules = edit_item['DefaultRules']
            except KeyError:
                try:
                    element_type = edit_item['ElementType']
                except KeyError:
                    print('Configuration Warning: rule {RULE}, summary {NAME}: the parameter "ElementType" is required '
                          'for EditColumn {COL}'.format(RULE=self.rule_name, NAME=self.name, COL=edit_column))
                    continue

                if element_type in ('date', 'datetime', 'timestamp', 'time', 'year'):
                    df[edit_column].fillna(datetime.datetime.now(), inplace=True)
                elif element_type in ('int', 'integer', 'bit'):
                    df[edit_column].fillna(0, inplace=True)
                elif element_type in ('float', 'decimal', 'dec', 'double', 'numeric', 'money'):
                    df[edit_column].fillna(0.0, inplace=True)
                elif element_type in ('bool', 'boolean'):
                    df[edit_column].fillna(False, inplace=True)
                elif element_type in ('char', 'varchar', 'binary', 'text'):
                    df[edit_column].fillna('', inplace=True)
                else:
                    df[edit_column].fillna('', inplace=True)
            else:
                for default_value in default_rules:
                    edit_rule = default_rules[default_value]
                    results = dm.evaluate_rule_set(df, {default_value: edit_rule}, as_list=True)
                    for row, result in enumerate(results):
                        if result is True:
                            df.at[row, edit_column] = default_value

        return df

    def update_static_columns(self, df):
        """
        Update empty table cells with static column default values.
        """
        static_columns = self.records['StaticColumns']
        for static_column in static_columns:
            static_entry = static_columns[static_column]
            if static_column not in df.columns:
                df[static_column] = None

            try:
                default_rules = static_entry['DefaultRules']
            except KeyError:
                try:
                    default_value = static_entry['DefaultValue']
                except KeyError:
                    print('Configuration Warning: rule {RULE}, summary {NAME}: one of "DefaultRules" or "DefaultValue" '
                          'is required for StaticColumn {COL}'
                          .format(RULE=self.rule_name, NAME=self.name, COL=static_column))
                    continue
                else:
                    for row_index in range(df.shape[0]):
                        if pd.isna(df.at[row_index, static_column]) is True:
                            df.at[row_index, static_column] = default_value
            else:
                for default_value in default_rules:
                    static_rule = default_rules[default_value]
                    results = dm.evaluate_rule_set(df, {default_value: static_rule}, as_list=True)
                    for row_index, result in enumerate(results):
                        if result is True and pd.isna(df.at[row_index, static_column]):
                            df.at[row_index, static_column] = default_value

        return df


class SummaryItemAdd(SummaryItem):
    """
    """

    def __init__(self, rule_name, name, sdict):
        super().__init__(rule_name, name, sdict)
        self.type = 'Add'

    def initialize_table(self, rule):
        """
        Populate the summary item dataframe with added records.
        """
        df = self.import_df.copy()
        print('Info: rule {RULE}, summary {NAME}: updating table with existing data'
              .format(RULE=self.rule_name, NAME=self.name))

        if self.import_df.empty:  # no records for selected parameters in database
            # Add empty row to the dataframe
            if df.shape[0]:  # no rows in table
                df = df.append(pd.Series(), ignore_index=True)

            # Create identifiers as defined in the configuration
            df = self.assign_record_ids(df, 0)

            # Set parameter values
            for param in rule.parameters:
                colname = param.alias
                value = param.value_obj
                df.at[0, colname] = value

            # Update amount column
            sum_column = self.records['SumColumn']
            df[sum_column] = pd.to_numeric(df[sum_column], downcast='float')

            tally_rule = self.totals['TallyRule']
            if tally_rule:
                totals_sum = dm.evaluate_rule(self.totals_df.iloc[[0]], tally_rule, as_list=False).sum()
            else:
                totals_sum = self.totals_df.iloc[0].sum()

            df.at[0, sum_column] = totals_sum

        # Update static columns with default values, if specified in rules
        df = self.update_static_columns(df)

        # Update edit columns with default values, if specified in rules
        df = self.update_edit_columns(df)

        self.df = df


class SummaryItemSubset(SummaryItem):
    """
    """

    def __init__(self, rule_name, name, sdict):
        super().__init__(rule_name, name, sdict)
        self.type = 'Subset'

    def initialize_table(self, rule):
        """
        Populate the summary item dataframe with rows from the TabItem dataframes specified in the configuration.
        """
        df = import_df = self.import_df.copy()

        records = self.records

        db_columns = records['TableColumns']
        mapping_columns = records['MappingColumns']
        references = records['ReferenceTables']

        # Get list of existing records
        id_column = records['IDColumn']
        try:
            existing_ids = import_df[id_column].tolist()
        except KeyError:
            print('Configuration Warning: rule {RULE}, summary {NAME}: IDColumn "{COL}" not found in the database table'
                  .format(RULE=self.rule_name, NAME=self.name, COL=id_column))
            existing_ids = []

        print('Info: rule {RULE}, summary {NAME}: updating table'.format(RULE=self.rule_name, NAME=self.name))

        # Extract desired records from the audit tab summaries
        for reference in references:
            subset_rule = references[reference]
            try:
                tab_df = rule.fetch_tab(reference).df
            except AttributeError:
                print('Warning: rule {RULE}, summary {NAME}: reference table {REF} not found in tab items'
                      .format(RULE=self.rule_name, NAME=self.name, REF=reference))
                continue

            # Subset tab item dataframe using subset rules defined in the ReferenceTable parameter
            print('Info: rule {RULE}, summary {NAME}: subsetting reference table {REF}'
                  .format(RULE=self.rule_name, NAME=self.name, REF=reference))
            try:
                subset_df = dm.subset_dataframe(tab_df, subset_rule)
            except Exception as e:
                print('Warning: rule {RULE}, summary {NAME}: subsetting table {REF} failed due to {ERR}'
                      .format(RULE=self.rule_name, NAME=self.name, REF=reference, ERR=e))
                continue
            else:
                if subset_df.empty:
                    print('Info: rule {RULE}, summary {NAME}: no data from reference table {REF} to add to summary'
                          .format(RULE=self.rule_name, NAME=self.name, REF=reference))
                    continue

            # Select columns based on MappingColumns parameter
            append_df = pd.DataFrame(columns=df.columns.values.tolist())
            for mapping_column in mapping_columns:
                if mapping_column not in db_columns:
                    print('Error: rule {RULE}, summary {NAME}: mapping column {COL} not in list of table columns'
                          .format(RULE=self.rule_name, NAME=self.name, COL=mapping_column))
                    continue

                mapping_rule = mapping_columns[mapping_column]
                col_to_add = dm.generate_column_from_rule(subset_df, mapping_rule)
                append_df[mapping_column] = col_to_add

            # Find rows from the dataframe to append that are already found in the existing dataset
            append_ids = append_df[id_column].tolist()

            rows_to_drop = []
            for record_index, record_id in enumerate(append_ids):
                if record_id in existing_ids:
                    print('Info: rule {RULE}, summary {NAME}: record "{ID}" already exists in the database'
                          .format(RULE=self.rule_name, NAME=self.name, ID=record_id))
                    rows_to_drop.append(record_id)
                else:
                    append_df = self.assign_record_ids(append_df, record_index)

            # Filter records from dataframe of records to append that were marked for removal
            append_df = append_df[~append_df[id_column].isin(rows_to_drop)]

            # Append data to the records dataframe
            df = dm.append_to_table(df, append_df)

        self.df = df

        # Set parameter values
        for param in self.parameters:
            colname = param.alias
            value = param.value_obj
            df[colname] = value

        # Update static columns with default values, if specified in rules
        df = self.update_static_columns(df)

        # Update edit columns with default values, if specified in rules
        df = self.update_edit_columns(df)

        self.df = df


def replace_nth(s, sub, new, ns):
    """
    Replace the nth occurrence of an substring in a string
    """
    if isinstance(ns, str):
        ns = [ns]

    where = [m.start() for m in re.finditer(sub, s)]
    new_s = s
    for count, start_index in enumerate(where):
        if count not in ns:
            continue

        before = new_s[:start_index]
        after = new_s[start_index:]
        after = after.replace(sub, new, 1)
        new_s = before + after

    return new_s
