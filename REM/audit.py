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
from random import randint

import REM.constants as mod_const
import REM.database as mod_db
import REM.data_manipulation as mod_dm
import REM.elements as mod_elem
import REM.layouts as mod_lo
import REM.parameters as mod_param
import REM.records as mod_records
import REM.secondary as mod_win2
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
                mod_win2.popup_error('Error: audit_rules: the parameter "name" is a required field')
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
                mod_win2.popup_error('Error: audit_rules: the parameter "rules" is a required field')
                sys.exit(1)

            for audit_rule in audit_rules:
                self.rules.append(AuditRule(audit_rule, audit_rules[audit_rule]))

    def print_rules(self, title=True):
        """
        Return name of all audit rules defined in configuration file.
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
            print('Warning: AuditRules: Rule {NAME} not in list of configured audit rules. Available rules are {ALL}'
                  .format(NAME=name, ALL=', '.join(self.print_rules())))
            rule = None
        else:
            rule = self.rules[index]

        return rule


class AuditRule:
    """
    Class to store and manage a configured audit rule.

    Attributes:

        name (str): audit rule name.

        menu_title (str): menu title for the audit rule.

        element_key (str): GUI element key.

        permissions (str): permissions required to view the audit. Default: user.

        parameters (list): list of RuleParameter type objects.

        tabs (list): list of AuditRuleTransaction objects.

        summary (SummaryPanel): SummaryPanel object.
    """

    def __init__(self, name, entry):
        """
        Arguments:
            name (str): audit rule name.

            entry (dict): dictionary of optional and required audit rule arguments.
        """

        self.name = name
        self.id = randint(0, 1000000000)
        self.element_key = '{NAME}_{ID}'.format(NAME=name, ID=self.id)
        self.elements = ['{NAME}_{ID}_{ELEM}'.format(NAME=self.name, ID=self.id, ELEM=i) for i in
                         ['Main', 'Summary', 'TG', 'Cancel', 'Start', 'Back', 'Next', 'Save', 'PanelWidth',
                          'PanelHeight', 'FrameHeight', 'FrameWidth']]

        try:
            self.menu_title = entry['MenuTitle']
        except KeyError:
            self.menu_title = name

        try:
            self.permissions = entry['AccessPermissions']
        except KeyError:  # default permission for an audit is 'user'
            self.permissions = 'user'

        self.parameters = []
        try:
            params = entry['RuleParameters']
        except KeyError:
            msg = 'Configuration Error: AuditRule {RULE}: missing required "Main" parameter "RuleParameters"' \
                .format(RULE=name)
            mod_win2.popup_error(msg)
            sys.exit(1)

        for param in params:
            param_entry = params[param]

            param_layout = param_entry['ElementType']
            if param_layout == 'dropdown':
                param_class = mod_param.RuleParameterCombo
            elif param_layout == 'input':
                param_class = mod_param.RuleParameterInput
            elif param_layout == 'date':
                param_class = mod_param.RuleParameterDate
            elif param_layout == 'date_range':
                param_class = mod_param.RuleParameterDateRange
            elif param_layout == 'checkbox':
                param_class = mod_param.RuleParameterCheckbox
            else:
                msg = 'Configuration Error: AuditRule {NAME}: unknown type {TYPE} provided to RuleParameter {PARAM}' \
                    .format(NAME=name, TYPE=param_layout, PARAM=param)
                mod_win2.popup_error(msg)
                sys.exit(1)

            param = param_class(param, param_entry)
            self.parameters.append(param)
            self.elements += param.elements

        self.tabs = []
        try:
            tab_entries = entry['Tabs']
        except KeyError:
            msg = 'Configuration Error: AuditRule {NAME}: missing required parameter "Tabs"'.format(NAME=name)
            mod_win2.popup_error(msg)
            sys.exit(1)

        for tab_name in tab_entries:
            tab_rule = AuditRuleTransaction(tab_name, tab_entries[tab_name], parent=self.name)

            self.tabs.append(tab_rule)
            self.elements += tab_rule.elements

        try:
            summary_entry = entry['Summary']
        except KeyError:
            msg = 'Configuration Error: AuditRule {NAME}: missing required parameter "Summary"'.format(NAME=name)
            mod_win2.popup_error(msg)
            sys.exit(1)

        self.summary = SummaryPanel(name, summary_entry)

        self.in_progress = False

        self.panel_keys = {0: self.key_lookup('Main'), 1: self.key_lookup('Summary')}
        self.current_panel = 0
        self.first_panel = 0
        self.last_panel = 1

    def key_lookup(self, component):
        """
        Lookup a component's GUI element key using the component's name.
        """
        element_names = [i.split('_')[-1] for i in self.elements]
        if component in element_names:
            key_index = element_names.index(component)
            key = self.elements[key_index]
        else:
            print('Warning: component {COMP} not found in list of bank rule {PARAM} components'
                  .format(COMP=component, PARAM=self.name))
            key = None

        return key

    def fetch_tab(self, name, by_key: bool = False):
        """
        """
        tabs = self.tabs

        if by_key is True:
            element_type = name.split('_')[-1]
            names = [i.key_lookup(element_type) for i in tabs]
        else:
            names = [i.name for i in tabs]

        try:
            index = names.index(name)
        except ValueError:
            print('Error: AuditRule {RULE}: {TAB} not in list of audit rule transactions'
                  .format(RULE=self.name, TAB=name))
            tab_item = None
        else:
            tab_item = tabs[index]

        return tab_item

    def fetch_parameter(self, element, by_key: bool = False):
        """
        Fetch a GUI parameter element by name or event key.
        """
        if by_key is True:
            element_type = element.split('_')[-1]
            element_names = [i.key_lookup(element_type) for i in self.parameters]
        else:
            element_names = [i.name for i in self.parameters]

        if element in element_names:
            index = element_names.index(element)
            parameter = self.parameters[index]
        else:
            raise KeyError('element {ELEM} not found in list of {NAME} data elements'
                           .format(ELEM=element, NAME=self.name))

        return parameter

    def run_event(self, window, event, values, user):
        """
        Run a transaction audit event.
        """
        current_rule = self.name

        # Rule action element events: Cancel, Next, Back, Start, Save
        cancel_key = self.key_lookup('Cancel')
        next_key = self.key_lookup('Next')
        back_key = self.key_lookup('Back')
        start_key = self.key_lookup('Start')
        save_key = self.key_lookup('Save')

        # Rule component element events
        tab_keys = [i for j in self.tabs for i in j.elements]
        param_keys = [i for j in self.parameters for i in j.elements]

        # Cancel button pressed
        if event == cancel_key:
            # Check if reconciliation is currently in progress
            if self.in_progress is True:
                msg = 'Transaction audit is currently in progress. Are you sure you would like to quit without saving?'
                selection = mod_win2.popup_confirm(msg)

                if selection == 'OK':
                    self.in_progress = False

                    # Remove from the list of used IDs any IDs created during the now cancelled audit
#                    for audit_record in self.summary.tabs:
#                        audit_record.remove_unsaved_keys()

                    # Reset the rule and update the panel
                    remain_in_panel = True if not values['-AMENU-'] else False
                    if remain_in_panel is True:
                        current_rule = self.reset_rule(window, current=True)
                    else:
                        current_rule = self.reset_rule(window, current=False)
            else:
                current_rule = self.reset_rule(window, current=False)

        # Next button pressed
        elif event == next_key:  # display summary panel
            next_subpanel = self.current_panel + 1

            # Hide current panel and un-hide the following panel
            window[self.panel_keys[self.current_panel]].update(visible=False)
            window[self.panel_keys[next_subpanel]].update(visible=True)

            # Reset current panel attribute
            self.current_panel = next_subpanel

            # Enable / disable action buttons
            if next_subpanel == self.last_panel:
                window[self.key_lookup('Next')].update(disabled=True)
                window[self.key_lookup('Back')].update(disabled=False)
                window[self.key_lookup('Save')].update(disabled=False)

        # Back button pressed
        elif event == back_key:
            prev_subpanel = self.current_panel - 1

            # Return to tab display
            window[self.panel_keys[self.current_panel]].update(visible=False)
            window[self.panel_keys[prev_subpanel]].update(visible=True)

            window[self.key_lookup('Next')].update(disabled=False)
            window[self.key_lookup('Back')].update(disabled=True)

            # Switch to first tab
            tg_key = self.key_lookup('TG')
            window[tg_key].Widget.select(0)

            # Reset current panel attribute
            self.current_panel = prev_subpanel

            # Enable / disable action buttons
            if prev_subpanel == self.first_panel:
                window[self.key_lookup('Next')].update(disabled=False)
                window[self.key_lookup('Back')].update(disabled=True)
                window[self.key_lookup('Save')].update(disabled=True)

        # Start button pressed
        elif event == start_key:
            # Check for valid parameter values
            params = self.parameters
            inputs = []
            for param in params:
                param.value = param.format_value(values)

                if param.value is None:
                    param_desc = param.description
                    msg = 'Parameter {} requires correctly formatted input'.format(param_desc)
                    mod_win2.popup_notice(msg)
                    inputs.append(False)
                else:
                    inputs.append(True)

            # Load data from the database
            if all(inputs):  # all rule parameters have input
                # Verify that the audit has not already been performed with these parameters
#                audit_exists = current_rule.summary.load_from_database(user, current_rule.parameters)
#                if audit_exists is True:
#                    continue_audit = mod_win2.popup_confirm('An audit has already been performed using these parameters. '
#                                                            'Only an admin may edit an existing audit. Are you sure you '
#                                                            'would like to continue?')
#                    if continue_audit == 'Cancel':
#                        continue

                # Initialize audit
                initialized = []
                for tab in self.tabs:
                    tab_key = tab.element_key
                    tab_keys.append(tab_key)

                    # Set tab parameters
                    tab.parameters = self.parameters

                    # Import tab data from the database
                    initialized.append(tab.load_data(user))

                    # Update the tab table display
                    tab.table.update_display(window)

#                    # Prepare the filter rules to filter query results
#                    main_table = [i for i in tab.import_rules][0]
#                    rule_params = current_rule.parameters  # to filter data tables
#                    filters = [i.filter_statement(table=main_table) for i in rule_params]
#
#                    # Check for tab-specific query parameters
#                    filters += tab.filter_statements()
#                    print(filters)
#
#                    # Extract data from database
#                    try:
#                        import_df = user.query(tab.import_rules, columns=tab.db_columns, filter_rules=filters)
#                    except Exception as e:
#                        mod_win2.popup_error('Error: audit failed - {}'.format(e))
#                        initialized = False
#                        break
#
#                    # Update tab object and elements
#                    tab.df = tab.table.append(df)  # update tab data

                if all(initialized):  # data successfully imported from all configured audit rule transaction tabs
                    self.in_progress = True
                    print('Info: AuditRule {NAME}: transaction audit in progress with parameters {PARAMS}'
                          .format(NAME=self.name, PARAMS=', '.join(['{}={}'.format(i.name, i.value) for i in params])))

                    # Enable/Disable control buttons and parameter elements
                    window[start_key].update(disabled=True)
                    self.toggle_parameters(window, 'disable')

                    # Enable table element events
                    for tab in self.tabs:
                        tab.table.enable(window)

                else:  # reset tabs that may have already loaded
                    for tab in self.tabs:
                        tab.reset(window)

        # Run component parameter events
        elif event in param_keys:
            try:
                param = self.fetch_parameter(event, by_key=True)
            except KeyError:
                print('Error: AuditRule {NAME}: unable to find parameter associated with event key {KEY}'
                      .format(NAME=self.name, KEY=event))
            else:
                result = param.run_event(window, event, values)

        # Run transaction tab events
        elif event in tab_keys:
            # Fetch the association element
            try:
                tab = self.fetch_tab(event, by_key=True)
            except KeyError:
                print('Error: AuditRule {NAME}: unable to find transaction tab associated with event key {KEY}'
                      .format(NAME=self.name, KEY=event))
            else:
                result = tab.run_event(window, event, values, user)

        return current_rule

    def layout(self, win_size: tuple = None):
        """
        Generate a GUI layout for the audit rule.
        """
        if win_size:
            width, height = win_size
        else:
            width, height = (mod_const.WIN_WIDTH, mod_const.WIN_HEIGHT)

        # Element parameters
        bttn_text_col = mod_const.WHITE_TEXT_COL
        bttn_bg_col = mod_const.BUTTON_COL
        disabled_text_col = mod_const.DISABLED_TEXT_COL
        disabled_bg_col = mod_const.DISABLED_BUTTON_COL
        bg_col = mod_const.ACTION_COL
        header_col = mod_const.HEADER_COL
        inactive_col = mod_const.INACTIVE_COL
#        default_col = mod_const.DEFAULT_COL
        text_col = mod_const.TEXT_COL
        select_col = mod_const.SELECT_TEXT_COL

        font_h = mod_const.HEADER_FONT

        pad_el = mod_const.ELEM_PAD
        pad_v = mod_const.VERT_PAD
        pad_h = mod_const.HORZ_PAD
        pad_frame = mod_const.FRAME_PAD

        # Rule parameters
        params = self.parameters

        # Element sizes
        layout_height = height * 0.8
        frame_height = layout_height * 0.70
        panel_height = frame_height - 80
        tab_height = panel_height * 0.6

        layout_pad = 120
        win_diff = width - mod_const.WIN_WIDTH
        layout_pad = layout_pad + (win_diff / 5)

        frame_width = width - layout_pad if layout_pad > 0 else width
        panel_width = frame_width - 30
        tab_width = panel_width - 30

        # Layout elements
        # Title
        panel_title = self.menu_title
        title_layout = [[sg.Text(panel_title, pad=(pad_frame, pad_frame), font=font_h, background_color=header_col)]]

        # Rule parameter elements
        param_elements = []
        for param in params:
            element_layout = param.layout(padding=((0, pad_h), 0))
            param_elements += element_layout

        start_key = self.key_lookup('Start')
        start_layout = [[mod_lo.B2('Start', key=start_key, pad=(0, 0), disabled=False,
                                   button_color=(bttn_text_col, bttn_bg_col),
                                   disabled_button_color=(disabled_text_col, disabled_bg_col),
                                   tooltip='Start bank reconciliation', use_ttk_buttons=True)]]

        param_layout = [sg.Col([param_elements], pad=(0, 0), background_color=bg_col, justification='l',
                               vertical_alignment='t', expand_x=True),
                        sg.Col(start_layout, pad=(0, 0), background_color=bg_col, justification='r',
                               element_justification='r', vertical_alignment='t')]

        # Tab layout
        tg_key = self.key_lookup('TG')
        audit_tabs = []
        for i, tab in enumerate(self.tabs):
            if i == 0:
                visiblity = True
            else:
                visiblity = False

            audit_tabs.append(tab.layout((tab_width, tab_height), visible=visiblity))

        tg_layout = [sg.TabGroup([audit_tabs], key=tg_key, pad=(0, 0),
                                 tab_background_color=inactive_col, selected_title_color=select_col,
                                 title_color=text_col, selected_background_color=bg_col, background_color=bg_col)]

#        audit_layout.append([sg.Col(tg_layout, pad=(pad_frame, pad_frame), background_color=bg_col, expand_x=True)])

        # Main panel layout
        main_key = self.key_lookup('Main')
        main_layout = sg.Col([param_layout,
                              [sg.HorizontalSeparator(pad=(0, pad_v), color=mod_const.HEADER_COL)],
                              tg_layout],
                             key=main_key, pad=(0, 0), background_color=bg_col, vertical_alignment='t',
                             visible=True, expand_y=True, expand_x=True)

        # Panels
        summary_layout = sg.Col(self.summary.layout(win_size), key=self.summary.element_key, background_color=bg_col,
                                vertical_alignment='c', visible=False, expand_x=True, expand_y=True)

#        audit_key = self.key_lookup('Audit')
#        panels = [sg.Col(audit_layout, key=audit_key, background_color=bg_col, vertical_alignment='c',
#                         visible=True, expand_y=True, expand_x=True),
#                  sg.Col(summary_layout, key=self.summary.element_key, background_color=bg_col, vertical_alignment='c',
#                         visible=False, expand_y=True, expand_x=True)]
#
#        panel_layout = [
#            [sg.Col([[sg.Pane(panels, orientation='horizontal', show_handle=False, border_width=0, relief='flat')]],
#                    pad=(0, pad_v), expand_x=True)]]

        panels = [main_layout, summary_layout]

        pw_key = self.key_lookup('PanelWidth')
        ph_key = self.key_lookup('PanelHeight')
        panel_layout = [[sg.Canvas(key=pw_key, size=(panel_width, 0), background_color=bg_col)],
                        [sg.Canvas(key=ph_key, size=(0, panel_height), background_color=bg_col),
                         sg.Pane(panels, orientation='horizontal', show_handle=False, border_width=0, relief='flat')]]

        # Standard elements
        cancel_key = self.key_lookup('Cancel')
        next_key = self.key_lookup('Next')
        back_key = self.key_lookup('Back')
        save_key = self.key_lookup('Save')
        bttn_layout = [
            sg.Col([[mod_lo.B2('Cancel', key=cancel_key, pad=((0, pad_el), 0), disabled=False,
                               tooltip='Return to home screen')]],
                   pad=(0, (pad_v, 0)), justification='l', expand_x=True),
            sg.Col([[sg.Canvas(size=(0, 0), visible=True)]], justification='c', expand_x=True),
            sg.Col([[mod_lo.B2('Back', key=back_key, pad=((0, pad_el), 0), disabled=True, tooltip='Return to audit'),
                     mod_lo.B2('Next', key=next_key, pad=(pad_el, 0), disabled=True, tooltip='Review audit'),
                     mod_lo.B2('Save', key=save_key, pad=((pad_el, 0), 0), disabled=True,
                               tooltip='Save to database and generate summary report')]],
                   pad=(0, (pad_v, 0)), justification='r')]

        fw_key = self.key_lookup('FrameWidth')
        fh_key = self.key_lookup('FrameHeight')
        frame_layout = [sg.Frame('', [
            [sg.Canvas(key=fw_key, size=(frame_width, 0), background_color=bg_col)],
            [sg.Col(title_layout, pad=(0, 0), justification='l', background_color=header_col, expand_x=True)],
            [sg.Col([[sg.Canvas(key=fh_key, size=(0, frame_height), background_color=bg_col)]], vertical_alignment='t'),
             sg.Col(panel_layout, pad=((pad_frame, pad_v), pad_v), background_color=bg_col, vertical_alignment='t',
                    expand_x=True, expand_y=True, scrollable=True, vertical_scroll_only=True)]],
                                 background_color=bg_col, relief='raised')]

        layout = [frame_layout, bttn_layout]

        return sg.Col(layout, key=self.element_key, visible=False)

    def resize_elements(self, window, win_size: tuple = None):
        """
        Resize Audit Rule GUI elements.
        """
        if win_size:
            width, height = win_size
        else:
            width, height = window.size  # default to current window size

        # For every five-pixel increase in window size, increase frame size by one
        layout_pad = 100  # default padding between the window and border of the frame
        win_diff = width - mod_const.WIN_WIDTH
        layout_pad = layout_pad + int(win_diff / 5)

        frame_width = width - layout_pad if layout_pad > 0 else width
        panel_width = frame_width - 30

        width_key = self.key_lookup('FrameWidth')
        window[width_key].set_size((frame_width, None))

        pw_key = self.key_lookup('PanelWidth')
        window[pw_key].set_size((panel_width, None))

        layout_height = height * 0.85  # height of the container panel, including buttons
        frame_height = layout_height - 120  # minus the approximate height of the button row and title bar, with padding
        panel_height = frame_height - 20  # minus top and bottom padding

        height_key = self.key_lookup('FrameHeight')
        window[height_key].set_size((None, frame_height))

        ph_key = self.key_lookup('PanelHeight')
        window[ph_key].set_size((None, panel_height))

        # Resize tab elements
        tab_height = panel_height - 60  # minus size of the tabs
        tab_width = panel_width - mod_const.FRAME_PAD * 2  # minus left and right padding

        tabs = self.tabs
        for tab in tabs:
            tab.resize_elements(window, size=(tab_width, tab_height))

        # Resize summary elements
#        self.summary.resize_elements(window, win_size)

    def reset_rule(self, window, current: bool = False):
        """
        Reset rule to default.
        """
        panel_key = self.element_key
        current_key = self.panel_keys[self.current_panel]

        # Reset current panel
        self.current_panel = 0

        # Disable current panel
        window[current_key].update(visible=False)
        window[self.panel_keys[self.first_panel]].update(visible=True)
        window[panel_key].update(visible=False)
        window['-HOME-'].update(visible=True)

        # Reset "action" elements to default
        save_key = self.key_lookup('Save')
        next_key = self.key_lookup('Next')
        back_key = self.key_lookup('Back')
        start_key = self.key_lookup('Start')
        window[next_key].update(disabled=True)
        window[back_key].update(disabled=True)
        window[save_key].update(disabled=True)
        window[start_key].update(disabled=False)

        # Switch to first tab in panel
        tg_key = self.key_lookup('TG')
        window[tg_key].Widget.select(0)

        # Switch to first tab in summary panel
#        tg_key = self.summary.key_lookup('TG')
#        window[tg_key].Widget.select(0)

        # Reset rule item attributes and parameters.
        self.reset_parameters(window)
        self.toggle_parameters(window, 'enable')

        # Reset tab attributes
        for i, tab in enumerate(self.tabs):
            if i == 0:
                tab.reset(window, first=True)
            else:
                tab.reset(window, first=False)
#            # Reset displays
#            ## Reset table element
#            table_key = tab.key_lookup('Table')
#            window[table_key].update(values=tab.df.values.tolist())
#
#            tab.resize_elements(window, size=(win_width, win_height))
#
#            ## Reset summary element
#            summary_key = tab.key_lookup('Summary')
#            window[summary_key].update(value='')
#
#            # Reset action buttons
#            tab.toggle_actions(window, 'disable')
#
#            # Reset visible tabs
#            visible = True if i == 0 else False
#            print('Info: rule {RULE}, tab {NAME}: re-setting visibility to {STATUS}'
#                  .format(NAME=tab.name, RULE=tab.rule_name, STATUS=visible))
#            window[tab.element_key].update(visible=visible)

        if current:
            window['-HOME-'].update(visible=False)
            window[panel_key].update(visible=True)
            window[self.panel_keys[self.first_panel]].update(visible=True)

            return self.name
        else:
            return None

    def reset_parameters(self, window):
        """
        Reset audit rule parameter values to default.
        """
        for param in self.parameters:
            param.reset_parameter(window)

    def toggle_parameters(self, window, value='enable'):
        """
        Enable / Disable audit rule parameter elements.
        """
        for param in self.parameters:
            param.toggle_parameter(window, value)


class SummaryPanel:
    """
    AuditRule summary panel object.
    """

    def __init__(self, rule_name, sdict):

        self.rule_name = rule_name
        self.element_key = mod_lo.as_key('{} Summary'.format(rule_name))
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
            mod_win2.popup_error(msg)
            sys.exit(1)

        for tab in tabs:
            si_dict = tabs[tab]
            try:
                summ_type = si_dict['Type']
            except KeyError:
                msg = _('Configuration Error: rule {RULE}, summary {NAME}:  missing required field "Type".') \
                    .format(RULE=rule_name, NAME=tab)
                mod_win2.popup_error(msg)
                sys.exit(1)

            if summ_type == 'Subset':
                self.tabs.append(mod_records.AuditRecordSubset(rule_name, tab, si_dict))
            elif summ_type == 'Add':
                self.tabs.append(mod_records.AuditRecordAdd(rule_name, tab, si_dict))
            else:
                msg = _('Configuration Error: rule {RULE}, summary {NAME}:  unknown type "{TYPE}" provided to the '
                        'Types parameter.').format(RULE=rule_name, NAME=tab, TYPE=summ_type)
                mod_win2.popup_error(msg)
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
            mod_win2.popup_error(msg)
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
                    mod_win2.popup_error(msg.format(RULE=rule_name, PARAM='Columns', NAME=section_name))
                    sys.exit(1)

        self.report = report

    def key_lookup(self, element):
        """
        Lookup element key for input control element.
        """
        if element in self.elements:
            key = mod_lo.as_key('{} Summary {}'.format(self.rule_name, element))
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
            width, height = (mod_const.WIN_WIDTH, mod_const.WIN_HEIGHT)

        # Layout settings
        pad_frame = mod_const.FRAME_PAD
        pad_el = mod_const.ELEM_PAD
        pad_v = mod_const.VERT_PAD

        bg_col = mod_const.ACTION_COL
        default_col = mod_const.DEFAULT_COL
        inactive_col = mod_const.INACTIVE_COL
        text_col = mod_const.TEXT_COL
        select_col = mod_const.SELECT_TEXT_COL
        header_col = mod_const.HEADER_COL

        font_h = mod_const.BOLD_FONT

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
            [sg.HorizontalSeparator(pad=(0, (pad_v, 0)), color=mod_const.HEADER_COL)]]

        layout.append([sg.Col(header_layout, pad=(pad_frame, 0), background_color=bg_col,
                              justification='l', expand_x=True)])

        # Main screen
        tg_key = self.key_lookup('TG')
        tg_layout = [[sg.TabGroup([mod_lo.tab_layout(tabs, win_size=win_size, initial_visibility='all')],
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
        default_col = mod_const.ACTION_COL
        greater_col = mod_const.PASS_COL
        lesser_col = mod_const.FAIL_COL

        tbl_error_col = mod_const.TBL_ERROR_COL

        tabs = self.tabs
        for tab in tabs:
            # Update audit field with the tab document number
            doc_no = tab.id
            elem_size = len(doc_no)

            no_key = tab.key_lookup('DocNo')
            window[no_key].set_size((elem_size, None))
            window[no_key].update(value=doc_no)

            # Reset column data types
            tab.set_datatypes()

            # Modify records tables for displaying
            print('Info: rule {RULE}, summary {NAME}: formatting records table for displaying'
                  .format(RULE=self.rule_name, NAME=tab.name))

            id_column = tab.records['IDColumn']
            record_ids = tab.df[id_column].dropna().unique().tolist()
            if len(record_ids) < 1:
                print('Info: rule {RULE}, summary {NAME}: no records to display'
                      .format(RULE=self.rule_name, NAME=tab.name))
                data = []
                error_colors = []
            else:
                display_df = tab.format_display_table(tab.df, columns=tab.records['DisplayColumns'])
                data = display_df.values.tolist()

                # Highlight rows with discrepancies
                errors = tab.search_for_errors()
                error_colors = [(i, tbl_error_col) for i in errors]

            tbl_key = tab.key_lookup('Table')
            window[tbl_key].update(values=data, row_colors=error_colors)
            window.refresh()

            # Modify totals tables for displaying
            print('Info: rule {RULE}, summary {NAME}: formatting totals table for displaying'
                  .format(RULE=self.rule_name, NAME=tab.name))
            totals_display_df = tab.format_display_table(tab.totals_df, columns=tab.totals['DisplayColumns'])
            totals_data = totals_display_df.values.tolist()

            totals_key = tab.key_lookup('Totals')
            window[totals_key].update(values=totals_data)

            # Update summary totals elements
            total_key = tab.key_lookup('Total')
            tally_rule = tab.totals['TallyRule']

            if tally_rule:
                totals_sum = mod_dm.evaluate_rule(tab.totals_df.iloc[[0]], tally_rule, as_list=False).sum()
            else:
                totals_sum = tab.totals_df.iloc[0].sum()

            window[total_key].update(value='{:,.2f}'.format(totals_sum))

            sum_column = tab.records['SumColumn']
            records_sum = tab.df[sum_column].sum()
            remainder = int(totals_sum - records_sum)
            if remainder > 0:
                print('Info: rule {RULE}, summary {NAME}: records are under-allocated by {AMOUNT}'
                      .format(RULE=self.rule_name, NAME=tab.name, AMOUNT=remainder))
                bg_color = greater_col
            elif remainder < 0:
                print('Info: rule {RULE}, summary {NAME}: records are over-allocated by {AMOUNT}'
                      .format(RULE=self.rule_name, NAME=tab.name, AMOUNT=abs(remainder)))
                bg_color = lesser_col
            else:
                bg_color = default_col

            remain_key = tab.key_lookup('Remainder')
            window[remain_key].update(value='{:,.2f}'.format(remainder), background_color=bg_color)

            # Change edit note button to be highlighted if note field not empty
            note_key = tab.key_lookup('Note')
            note_text = tab.notes['Value']
            if note_text:
                window[note_key].update(image_data=mod_const.EDIT_NOTE_ICON)
            else:
                window[note_key].update(image_data=mod_const.TAKE_NOTE_ICON)

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
                for component in mod_dm.parse_operation_string(reference):
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
                    subset_df = mod_dm.subset_dataframe(reference_df, section['Subset'])
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

                # Format as display table
                display_df = reference_tab.format_display_table(subset_df)

                # Index rows using grouping list in configuration
                try:
                    grouping = section['Group']
                except KeyError:
                    grouped_df = display_df
                else:
                    grouped_df = display_df.set_index(grouping).sort_index()

                html_str = grouped_df.to_html(header=False, index_names=False, float_format='{:,.2f}'.format,
                                              sparsify=True, na_rep='')

                # Highlight errors in html string
                error_col = mod_const.TBL_ERROR_COL
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
                    update_table = mod_win2.popup_confirm(msg)

                    if update_table == 'Cancel':
                        return False
                else:
                    msg = 'Audit results already exist in the summary database. Only an admin can update audit ' \
                          'records'
                    mod_win2.popup_notice(msg)

                    return False

            # Assign IDs to records when filter rules apply
            for id_field in tab.ids:
                id_entry = tab.ids[id_field]

                if 'FilterRules' in id_entry:
                    tbl_filter_param = id_entry['FilterRules']
                    db_table = id_entry['DatabaseTable']
                    db_id_field = id_entry['DatabaseField']

                    import_ids = tab.import_df[id_field]

                    current_results = mod_dm.evaluate_rule_set(tab.df, tbl_filter_param)
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
                                    mod_win2.popup_error('Warning: Failed to remove {ID}. Changes will not be saved to the '
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

                            if id_entry['IsUnique'] is True:
                                record_id = tab.create_id(id_entry, all_ids)
                                print('Info: rule {RULE}, summary {NAME}: saving new record {ID} to list of table {TBL}'
                                      ' IDs'.format(RULE=self.rule_name, NAME=tab.name, ID=record_id, TBL=db_table))
                                current_tbl_pkeys[db_table].append(record_id)
                            else:
                                if len(current_ids) > 0:
                                    record_id = current_ids[0]
                                else:
                                    record_id = tab.create_id(id_entry, all_ids)
                                    print('Info: rule {RULE}, summary {NAME}: saving new record {ID} to list of table '
                                          '{TBL} IDs'.format(RULE=self.rule_name, NAME=tab.name, ID=record_id,
                                                             TBL=db_table))
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

                ref_col_map = {}
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

                    ref_col_map[ref_col] = column

                    if is_audit is True:
                        if len(ref_series.dropna().unique().tolist()) > 1:
                            print(ref_series)
                            print('Warning: rule {RULE}, summary {NAME}: the "IsAuditTable" parameter was selected '
                                  'for output table {TABLE} but the reference column "{REF}" has more than one unique '
                                  'value. Using first value encountered in {COL}'
                                  .format(RULE=self.rule_name, NAME=tab.name, TABLE=table, REF=ref_col, COL=column))

                        try:
                            ref_value = ref_series.dropna().iloc[0]
                        except IndexError:  # df is empty
                            continue
                        else:
                            df.at[0, column] = ref_value
                    else:
                        df[column] = ref_series

                # Add information if export dataframe is empty and table is the audit table
                if df.empty and is_audit is True:
                    print('Warning: rule {RULE}, summary {NAME}: no records exist for output table {TBL}'
                          .format(RULE=self.rule_name, NAME=tab.name, TBL=table))
                    # Add empty row to dataframe
                    df = df.append(pd.Series(), ignore_index=True)

                    # Add audit identifier to dataframe
                    for id_field in tab.ids:
                        id_param = tab.ids[id_field]

                        if id_param['IsPrimary'] is True:
                            pkey = id_param['DatabaseField']
                            break

                    primary_id = tab.id
                    df.at[0, pkey] = primary_id

                    # Add summary totals to column
                    total_cols = tab.totals_df.columns.values.tolist()
                    for total_col in total_cols:
                        try:
                            dbcolumn = ref_col_map[total_col]
                        except KeyError:
                            print('Info: rule {RULE}, summary {NAME}: summary total {COL} not found in the audit '
                                  'reference columns'.format(RULE=self.rule_name, NAME=tab.name, COL=total_col))
                            continue
                        else:
                            value = tab.totals_df.at[0, total_col]
                            df.at[0, dbcolumn] = str(value)

                    # Set parameter values
                    for param in tab.parameters:
                        try:
                            dbcolumn = ref_col_map[param.alias]
                        except KeyError:
                            try:
                                dbcolumn = ref_col_map[param.name]
                            except KeyError:
                                print('Info: rule {RULE}, summary {NAME}: parameter {COL} not found in the audit '
                                      'reference columns'.format(RULE=self.rule_name, NAME=tab.name, COL=param.alias))
                                continue

                        value = param.value_obj
                        df.at[0, dbcolumn] = value

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
                    mod_win2.popup_error(msg)
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
                        row[configuration.editor_code] = user.uid
                        row[configuration.edit_date] = datetime.datetime.now().strftime(settings.format_date_str())

                        # Prepare update parameters
                        row_columns = row.index.tolist()
                        row_values = row.replace({np.nan: None}).values.tolist()

                        # Update existing record in table
                        filters = ('{} = ?'.format(db_id_field), (row_id,))
                        success.append(user.update(table, row_columns, row_values, filters))
                    else:  # new record created
                        # Add creator information
                        row[configuration.creator_code] = user.uid
                        row[configuration.creation_date] = datetime.datetime.now().strftime(settings.format_date_str())

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
                        mod_win2.popup_error(
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


class AuditRuleTransaction:
    """
    Transaction Audit component.

        name (str): rule name.

        id (int): rule element number.

        title (str): rule title.

        element_key (str): rule element key.

        elements (list): list of rule GUI element keys.
    """

    def __init__(self, name, entry, parent=None):
        """
        Arguments:

            name (str): bank reconciliation rule name.

            entry (dict): dictionary of optional and required bank rule arguments.

            parent (str): name of the object's parent element.
        """
        self.name = name
        self.parent = parent
        self.id = randint(0, 1000000000)
        self.element_key = '{NAME}_{ID}_{ELEM}'.format(NAME=self.name, ID=self.id, ELEM='TAB')
        self.elements = ['{NAME}_{ID}_{ELEM}'.format(NAME=self.name, ID=self.id, ELEM=i) for i in
                         ['Audit', 'Width', 'Height']]

        try:
            self.title = entry['Title']
        except KeyError:
            self.title = name

        try:
            import_rules = entry['ImportRules']
        except KeyError:
            msg = 'Configuration Error: AuditRuleTransaction {NAME}: missing required field "ImportRules".'\
                .format(NAME=name)
            mod_win2.popup_error(msg)
            sys.exit(1)
        else:
            self.import_rules = import_rules

        try:
            self.table = mod_elem.TableElement(name, entry['DisplayTable'])
        except KeyError:
            msg = 'Configuration Error: AuditRuleTransaction {NAME}: missing required parameter "DisplayTable"' \
                .format(NAME=name)
            mod_win2.popup_error(msg)
            sys.exit(1)
        except AttributeError as e:
            msg = 'Configuration Error: AuditRuleTransaction {NAME}: unable to initialize DisplayTable - {ERR}' \
                .format(NAME=name, ERR=e)
            mod_win2.popup_error(msg)
            sys.exit(1)
        else:
            self.elements += self.table.elements

        self.in_progress = False
        self.parameters = None

    def key_lookup(self, component):
        """
        Lookup a component's GUI element key using the component's name.
        """
        element_names = [i.split('_')[-1] for i in self.elements]
        if component in element_names:
            key_index = element_names.index(component)
            key = self.elements[key_index]
        else:
            print('Warning: AuditRule {NAME}: component {COMP} not found in list of audit rule elements'
                  .format(NAME=self.name, COMP=component))
            key = None

        return key

    def reset(self, window, first: bool = False):
        """
        Reset the elements and attributes of the audit rule transaction tab.
        """

        # Reset the data table
        self.table.df = pd.DataFrame(columns=list(self.table.columns))
        self.table.update_display(window)

        # Disable table element events
        self.table.disable(window)

        # Reset parameters
        self.parameters = None

        # Reset visible tabs
        visible = True if first is True else False
        print('Info: AuditRuleTransaction {NAME}: re-setting visibility of rule tab to {STATUS}'
              .format(NAME=self.name, STATUS=visible))

        window[self.element_key].update(visible=visible)

    def layout(self, size, visible: bool = True):
        """
        GUI layout for the audit rule transaction tab.
        """
        width, height = size

        # Element parameters
        bg_col = mod_const.ACTION_COL
        bttn_text_col = mod_const.WHITE_TEXT_COL
        bttn_bg_col = mod_const.BUTTON_COL
        disabled_text_col = mod_const.DISABLED_TEXT_COL
        disabled_bg_col = mod_const.DISABLED_BUTTON_COL

        pad_frame = mod_const.FRAME_PAD

        # Element sizes
        tbl_width = width - 40
        tbl_height = height * 0.8

        # Layout
        audit_key = self.key_lookup('Audit')
        main_layout = [[self.table.layout(width=tbl_width, height=tbl_height, padding=(0, 0), disabled=True)],
                       [sg.Col([[mod_lo.B1('Run Audit', key=audit_key, disabled=True,
                                           button_color=(bttn_text_col, bttn_bg_col),
                                           disabled_button_color=(disabled_text_col, disabled_bg_col),
                                           tooltip='Run audit on the transaction records', use_ttk_buttons=True)]],
                               pad=(pad_frame, pad_frame), background_color=bg_col, element_justification='c',
                               expand_x=True)]]

        height_key = self.key_lookup('Height')
        width_key = self.key_lookup('Width')
        layout = [[sg.Canvas(key=width_key, size=(width, 0), background_color=bg_col)],
                  [sg.Canvas(key=height_key, size=(0, height), background_color=bg_col),
                   sg.Col(main_layout, pad=(pad_frame, pad_frame), justification='c', vertical_alignment='t',
                          background_color=bg_col, expand_x=True)]]

        return sg.Tab(self.title, layout, key=self.element_key, background_color=bg_col, visible=visible)

    def resize_elements(self, window, size):
        """
        Resize the transaction tab.
        """
        width, height = size

        # Reset tab element size
        width_key = self.key_lookup('Width')
        window[width_key].set_size(size=(width, None))

        height_key = self.key_lookup('Height')
        window[height_key].set_size(size=(None, height))

        # Reset table size
        tbl_width = width - 30  # includes padding on both sides and scroll bar
        tbl_height = int(height * 0.6)
        self.table.resize(window, size=(tbl_width, tbl_height), row_rate=80)

    def run_event(self, window, event, values, user):
        """
        Run an audit rule transaction event.
        """
        audit_key = self.key_lookup('Audit')
        table_keys = self.table.elements

        # Run component table events
        if event in table_keys:
            results = self.table.run_event(window, event, values, user)

        # Run a transaction audit
        elif event == audit_key:
            self.table.df = self.audit_transactions(user)
            self.table.update_display(window)

        return True

    def load_data(self, user):
        """
        Load association data from the database.
        """
        # Prepare the database query statement
        import_rules = self.import_rules

        main_table = mod_db.get_primary_table(import_rules)

        param_filters = [i.query_statement(table=main_table) for i in self.parameters]
        filters = param_filters + mod_db.format_import_filters(import_rules)
        table_statement = mod_db.format_tables(import_rules)
        columns = mod_db.format_import_columns(import_rules)

        # Import primary bank data from database
        try:
            df = user.query(table_statement, columns=columns, filter_rules=filters)
        except Exception as e:
            mod_win2.popup_error('Error: AuditRuleTransaction {NAME}: failed to import data from the database - {ERR}'
                                 .format(NAME=self.name, ERR=e))
            data_loaded = False
        else:
            print('Info: AuditRuleTransaction {NAME}: loaded data for audit rule {RULE}'
                  .format(NAME=self.name, RULE=self.parent))
            print(df)
            self.table.df = self.table.append(df)
            print(self.table.df)
            self.table._df = self.table.df
            data_loaded = True

        return data_loaded

    def audit_transactions(self, user):
        """
        Search for missing transactions using scan.
        """
        dparse = dateutil.parser.parse
        strptime = datetime.datetime.strptime

        # Class attributes
        table = self.table
        params = self.parameters
        pkey = table.id_column
        df = table.sort()

        id_list = table.row_ids()
        main_table = [i for i in self.import_rules][0]

        # Format audit parameters
        audit_date = None
        for audit_param in params:
            if audit_param.type.lower() == 'date':
                date_col = audit_param.name
                date_col_full = mod_dm.get_query_from_header(date_col, table.columns)
                date_fmt = audit_param.format
                try:
                    audit_date = strptime(audit_param.value, date_fmt)
                except ValueError:
                    print('Warning: AuditRuleTransaction {NAME}: no date provided ... skipping checks for most recent ID'
                          .format(NAME=self.name))
                else:
                    audit_date_iso = audit_date.strftime("%Y-%m-%d")

        missing_transactions = []
        # Search for missing data

        try:
            first_id = id_list[0]
        except IndexError:
            first_id = None
        else:
            first_number_comp = int(self.get_id_component(first_id, 'variable'))
            first_date_comp = self.get_id_component(first_id, 'date')
            print('Info: rule {RULE}, tab {NAME}: first transaction ID is {ID}'
                  .format(RULE=self.rule_name, NAME=self.name, ID=first_id))

        if audit_date and first_id:
            ## Find date of last transaction
            query_str = 'SELECT DISTINCT {DATE} FROM {TBL}'.format(DATE=date_col_full, TBL=main_table)
            try:
                dates_df = user.thread_transaction(query_str, (), operation='read')
            except Exception as e:
                mod_win2.popup_error('Error: audit scan failed due to failure to connect to the database')
                print(e)
                return df

            unq_dates = dates_df[date_col].tolist()
            try:
                unq_dates_iso = [i.strftime("%Y-%m-%d") for i in unq_dates]
            except TypeError:
                print('Warning: AuditRuleTransaction {NAME}: date {DATE} is not formatted correctly as a datetime object'
                      .format(NAME=self.name, DATE=audit_date_iso))
                return df

            unq_dates_iso.sort()

            try:
                current_date_index = unq_dates_iso.index(audit_date_iso)
            except ValueError:
                print('Warning: AuditRuleTransaction {NAME}: no transactions for audit date {DATE} found in list {DATES}'
                      .format(NAME=self.name, DATE=audit_date_iso, DATES=unq_dates_iso))
                return df

            try:
                prev_date = dparse(unq_dates_iso[current_date_index - 1], yearfirst=True)
            except IndexError:
                print('Warning: AuditRuleTransaction {NAME}: no date found prior to current audit date {DATE}'
                      .format(NAME=self.name, DATE=audit_date_iso))
                prev_date = None
            except ValueError:
                print('Warning: AuditRuleTransaction {NAME}: unknown format {DATE} provided'
                      .format(NAME=self.name, DATE=unq_dates_iso[current_date_index - 1]))
                prev_date = None

            ## Query last transaction from previous date
            if prev_date:
                print('Info: AuditRuleTransaction {NAME}: searching for most recent transaction created in {DATE}'
                      .format(NAME=self.name, DATE=prev_date.strftime('%Y-%m-%d')))

                filters = ('{} = ?'.format(date_col_full), (prev_date.strftime(date_fmt),))
                last_df = user.query(self.import_rules, columns=table.columns, filter_rules=filters)
                last_df.sort_values(by=[pkey], inplace=True, ascending=False)

                last_id = None
                prev_ids = last_df[pkey].tolist()
                for prev_id in prev_ids:
                    prev_number_comp = int(self.get_id_component(prev_id, 'variable'))
                    prev_date_comp = self.get_id_component(prev_id, 'date')

                    if prev_number_comp > first_number_comp:
                        continue

                    # Search only for IDs with correct ID formats (skip potential errors)
                    if prev_id == self.format_id(prev_number_comp, date=prev_date_comp):
                        last_id = prev_id
                        break

                if last_id:
                    print('Info: AuditRuleTransaction {NAME}: last transaction ID is {ID} from {DATE}' \
                          .format(NAME=self.name, ID=last_id, DATE=prev_date.strftime('%Y-%m-%d')))

                    if first_date_comp != prev_date_comp:  # start of new month
                        if first_number_comp != 1:
                            missing_range = list(range(1, first_number_comp))
                        else:
                            missing_range = []

                    else:  # still in same month
                        if (prev_number_comp + 1) != first_number_comp:  # first not increment of last
                            missing_range = list(range(prev_number_comp + 1, first_number_comp))
                        else:
                            missing_range = []

                    for missing_number in missing_range:
                        missing_id = self.format_id(missing_number, date=first_date_comp)
                        if missing_id not in id_list:
                            missing_transactions.append(missing_id)

            ## Search for missed numbers at end of day
            last_id_of_df = id_list[-1]

            filters = ('{} = ?'.format(date_col_full), (audit_date.strftime(date_fmt),))
            current_df = user.query(self.import_rules, columns=table.columns, filter_rules=filters)
            current_df.sort_values(by=[pkey], inplace=True, ascending=False)

            current_ids = current_df[pkey].tolist()
            for current_id in current_ids:
                if last_id_of_df == current_id:
                    break

                current_number_comp = int(self.get_id_component(current_id, 'variable'))
                if current_id == self.format_id(current_number_comp, date=first_date_comp):
                    missing_transactions.append(current_id)

        ## Search for skipped transaction numbers
        try:
            id_list[1]
        except IndexError:
            pass
        else:
            prev_number = first_number_comp
            for transaction_id in id_list[1:]:
                trans_number = int(self.get_id_component(transaction_id, 'variable'))
                if (prev_number + 1) != trans_number:
                    missing_range = list(range(prev_number + 1, trans_number))
                    for missing_number in missing_range:
                        missing_id = self.format_id(missing_number, date=first_date_comp)
                        if missing_id not in id_list:
                            missing_transactions.append(missing_id)

                prev_number = trans_number

        print('Info: AuditRuleTransactions {NAME}: potentially missing transactions: {MISS}'
              .format(NAME=self.name, MISS=missing_transactions))

        # Query database for the potentially missing transactions
        if missing_transactions:
            pkey_fmt = mod_dm.get_query_from_header(pkey, table.columns)

            filter_values = ['?' for _ in missing_transactions]
            filter_str = '{PKEY} IN ({VALUES})'.format(PKEY=pkey_fmt, VALUES=', '.join(filter_values))

            filters = [(filter_str, tuple(missing_transactions))]

            # Drop missing transactions if they don't meet the import parameter requirements
            filters += mod_db.format_import_filters(self.import_rules)
            missing_df = user.query(self.import_rules, columns=table.columns, filter_rules=filters, order=pkey_fmt)
        else:
            missing_df = pd.DataFrame(columns=df.columns)

        # Display import window with potentially missing data
        if not missing_df.empty:
            missing_df_fmt = self.format_display_table(mod_dm.sort_table(missing_df, pkey))
            import_rows = mod_win2.import_window(missing_df_fmt)
            import_df = missing_df.iloc[import_rows]

            # Update dataframe with imported data
            if not import_df.empty:
                df = mod_dm.append_to_table(table.df, import_df)

        print('Info: AuditRuleTransactions {NAME}: new size of dataframe is {NROW} rows and {NCOL} columns'
              .format(NAME=self.name, NROW=df.shape[0], NCOL=df.shape[1]))

        return df


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
