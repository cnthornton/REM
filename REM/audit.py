"""
REM transaction audit configuration classes and functions. Includes audit rules, audit objects, and rule parameters.
"""
import datetime
import dateutil
import os
import re
import sys

from jinja2 import Environment, FileSystemLoader
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
#from REM.settings import settings, user
from REM.client import logger, settings, user


class AuditRules:
    """
    Class to store and manage program audit_rule configuration settings.

    Arguments:

        audit_param (dict): configuration for the audit rules.

    Attributes:

        rules (list): List of AuditRule objects.
    """

    def __init__(self, audit_param):

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

        elements (list): list of rule GUI element keys.

        permissions (str): permissions required to view the audit. Default: user.

        parameters (list): list of DataParameter type objects.

        tabs (list): list of AuditTransactionTab objects.

        summary (AuditSummary): SummaryPanel object.
    """

    def __init__(self, name, entry):
        """
        Arguments:
            name (str): audit rule name.

            entry (dict): dictionary of optional and required audit rule arguments.
        """

        self.name = name
        self.id = randint(0, 1000000000)
        self.element_key = '-{NAME}_{ID}-'.format(NAME=name, ID=self.id)
        self.elements = ['-ENTER-', '-ESCAPE-', '-LEFT-', '-RIGHT-']
        self.elements.extend(['-{NAME}_{ID}_{ELEM}-'.format(NAME=self.name, ID=self.id, ELEM=i) for i in
                              ['Panel', 'TG', 'Cancel', 'Start', 'Back', 'Next', 'Save', 'PanelWidth',
                               'PanelHeight', 'FrameHeight', 'FrameWidth']])

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

        for param_name in params:
            param_entry = params[param_name]

            param_layout = param_entry['ElementType']
            if param_layout == 'dropdown':
                param_class = mod_param.DataParameterCombo
            elif param_layout == 'input':
                param_class = mod_param.DataParameterInput
            elif param_layout == 'date':
                param_class = mod_param.DataParameterDate
            elif param_layout == 'date_range':
                param_class = mod_param.DataParameterDateRange
            elif param_layout == 'checkbox':
                param_class = mod_param.DataParameterCheckbox
            else:
                msg = 'Configuration Error: AuditRule {NAME}: unknown type {TYPE} provided to RuleParameter {PARAM}' \
                    .format(NAME=name, TYPE=param_layout, PARAM=param_name)
                mod_win2.popup_error(msg)
                sys.exit(1)

            param = param_class(param_name, param_entry)
            self.parameters.append(param)
            self.elements += param.elements

        self.tabs = []
        try:
            tab_entries = entry['Tabs']
        except KeyError:
            msg = 'Configuration Error: AuditRule {NAME}: missing required parameter "Tabs"'.format(NAME=name)
            mod_win2.popup_error(msg)
            sys.exit(1)

        for tab_i, tab_name in enumerate(tab_entries):
            tab_rule = AuditTransactionTab(tab_name, tab_entries[tab_name], parent=self.name)

            self.tabs.append(tab_rule)
            self.elements += tab_rule.elements
            self.elements.append('-{NAME}_{ID}_Tab{ELEM}-'.format(NAME=self.name, ID=self.id, ELEM=tab_i))

        self.current_tab = 0
        self.final_tab = len(self.tabs)

        try:
            summary_entry = entry['Summary']
        except KeyError:
            msg = 'Configuration Error: AuditRule {NAME}: missing required parameter "Summary"'.format(NAME=name)
            mod_win2.popup_error(msg)
            sys.exit(1)

        self.summary = AuditSummary(name, summary_entry)
        self.elements += self.summary.elements

        self.in_progress = False

        self.panel_keys = {0: self.key_lookup('Panel'), 1: self.summary.element_key}
        self.current_panel = 0
        self.first_panel = 0
        self.last_panel = 1

    def key_lookup(self, component):
        """
        Lookup a component's GUI element key using the component's name.
        """
        element_names = [i[1:-1].split('_')[-1] for i in self.elements]
        if component in element_names:
            key_index = element_names.index(component)
            key = self.elements[key_index]
        else:
            print('Warning: AuditRule {NAME}: component {COMP} not found in list of rule components'
                  .format(NAME=self.name, COMP=component))
            key = None

        return key

    def fetch_tab(self, fetch_key, by_key: bool = False):
        """
        """
        tabs = self.tabs

        tab_item = None
        if by_key is True:
            for tab in tabs:
                if fetch_key in tab.elements:
                    tab_item = tab
                    break
        else:
            names = [i.name for i in tabs]
            try:
                index = names.index(fetch_key)
            except ValueError:
                print('Error: AuditRule {RULE}: {TAB} not found in list of audit rule transaction tabs'
                      .format(RULE=self.name, TAB=fetch_key))
            else:
                tab_item = tabs[index]

        return tab_item

    def fetch_parameter(self, element, by_key: bool = False):
        """
        Fetch a GUI parameter element by name or event key.
        """
        if by_key is True:
            element_type = element[1:-1].split('_')[-1]
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

    def run_event(self, window, event, values):
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
        tg_key = self.key_lookup('TG')

        # Rule component element events
        tab_keys = [i for j in self.tabs for i in j.elements]
        param_keys = [i for j in self.parameters for i in j.elements]
        summary_keys = self.summary.elements

        # Cancel button pressed
        if event in (cancel_key, '-ESCAPE-'):
            # Check if reconciliation is currently in progress
            if self.in_progress is True:
                msg = 'Transaction audit is currently in progress. Are you sure you would like to quit without saving?'
                selection = mod_win2.popup_confirm(msg)

                if selection == 'OK':
                    # Remove from the list of used IDs any IDs created during the now cancelled audit
#                    for tab in self.summary.tabs:
#                        mod_records.remove_unsaved_keys(tab.record)

                    # Reset the rule and update the panel
                    remain_in_panel = True if not values['-AMENU-'] else False
                    if remain_in_panel is True:
                        current_rule = self.reset_rule(window, current=True)
                    else:
                        current_rule = self.reset_rule(window, current=False)
            else:
                current_rule = self.reset_rule(window, current=False)

        # Next button pressed - display summary panel
        elif (event == next_key) or (event == '-RIGHT-' and not window[next_key].metadata['disabled']):
            next_subpanel = self.current_panel + 1

            # Prepare audit records
            if next_subpanel == self.last_panel:
                # Update audit records
                for tab in self.summary.tabs:

                    # Update audit record totals
                    tab.map_summary(self.tabs)

                    # Map transactions to transaction records
                    tab.map_transactions(self.tabs, self.parameters)

                    # Update the audit record's display
                    tab.update_display(window)

                # Disable / enable action buttons
                window[next_key].update(disabled=True)
                window[next_key].metadata['disabled'] = True

                window[back_key].update(disabled=False)
                window[back_key].metadata['disabled'] = False

                window[save_key].update(disabled=False)
                window[save_key].metadata['disabled'] = False

            # Hide current panel and un-hide the following panel
            window[self.panel_keys[self.current_panel]].update(visible=False)
            window[self.panel_keys[next_subpanel]].update(visible=True)

            # Reset current panel attribute
            self.current_panel = next_subpanel

        # Back button pressed
        elif (event == back_key) or (event == '-LEFT-' and not window[back_key].metadata['disabled']):
            current_panel = self.current_panel

            # Delete unsaved keys if returning from summary panel
            if current_panel == self.last_panel:
                for tab in self.summary.tabs:
                    # Remove unsaved IDs associated with the record
                    mod_records.remove_unsaved_keys(tab.record)

                    # Reset audit records
                    tab.reset(window)

                    # Update the audit record's display
                    tab.update_display(window)

            # Return to previous display
            prev_subpanel = current_panel - 1
            window[self.panel_keys[current_panel]].update(visible=False)
            window[self.panel_keys[prev_subpanel]].update(visible=True)

            window[next_key].update(disabled=False)
            window[next_key].metadata['disabled'] = False

            window[back_key].update(disabled=True)
            window[back_key].metadata['disabled'] = True

            # Switch to first tab
            tg_key = self.key_lookup('TG')
            window[tg_key].Widget.select(0)

            # Reset current panel attribute
            self.current_panel = prev_subpanel

            # Enable / disable action buttons
            if prev_subpanel == self.first_panel:
                window[next_key].update(disabled=False)
                window[next_key].metadata['disabled'] = False

                window[back_key].update(disabled=True)
                window[back_key].metadata['disabled'] = True

                window[save_key].update(disabled=True)
                window[save_key].metadata['disabled'] = True

        # Start button pressed
        elif (event == start_key) or (event == '-ENTER-' and not window[start_key].metadata['disabled']):
            # Check for valid parameter values
            params = self.parameters
            inputs = []
            for param in params:
                param.value = param.format_value(values)

                if not param.value:
                    param_desc = param.description
                    msg = 'Parameter {} requires correctly formatted input'.format(param_desc)
                    mod_win2.popup_notice(msg)
                    logger.warning('failed to start audit - parameter {} requires correctly formatted input'
                                   .format(param_desc))
                    inputs.append(False)
                else:
                    inputs.append(True)

            # Load data from the database
            if all(inputs):  # all rule parameters have input
                window[start_key].update(disabled=True)

                # Verify that the audit has not already been performed with these parameters
                audit_exists = self.summary.load_records(self.parameters)
                if audit_exists is True:
                    msg = 'An audit has already been performed using these parameters. Please edit or delete the ' \
                          'audit records through the records menu'
                    mod_win2.popup_error(msg)
                    logger.warning('audit initialization failed - an audit has already been performed with the '
                                   'provided parameters')
                    current_rule = self.reset_rule(window, current=True)

                    return current_rule

                # Initialize audit
                initialized = []
                for tab in self.tabs:
                    tab_key = tab.key_lookup('Tab')
                    tab_keys.append(tab_key)

                    # Set tab parameters
                    tab.parameters = self.parameters

                    # Import tab data from the database
                    initialized.append(tab.load_data())

                if all(initialized):  # data successfully imported from all configured audit rule transaction tabs
                    self.in_progress = True
                    logger.info('AuditRule {NAME}: transaction audit in progress with parameters {PARAMS}'
                                .format(NAME=self.name,
                                        PARAMS=', '.join(['{}={}'.format(i.name, i.value) for i in params])))

                    # Enable/Disable control buttons and parameter elements
                    self.toggle_parameters(window, 'disable')

                    # Update summary panel title with rule parameter values
                    self.summary.update_title(window, self.parameters)

                    for tab in self.tabs:
                        # Enable table element events
                        tab.table.enable(window)

                        # Update the tab table display
                        tab.table.update_display(window)

                        # Update tab ID components
                        tab.update_id_components()

                        # Enable the tab audit button
                        window[tab.key_lookup('Audit')].update(disabled=False)

                else:  # reset tabs that may have already loaded
                    msg = 'failed to load all transaction audit data from the database'
                    mod_win2.popup_error(msg)
                    logger.error('AuditRule {NAME}: audit initialization failed - {ERR}'
                                 .format(NAME=self.name, ERR=msg))
                    current_rule = self.reset_rule(window, current=True)

        # Switch between tabs
        elif event == tg_key:
            tab_key = window[tg_key].Get()
            tab = self.fetch_tab(tab_key, by_key=True)
            logger.debug('AuditRule {NAME}: moving to transaction audit tab {TAB}'.format(NAME=self.name, TAB=tab.name))

            # Collapse the filter frame, if applicable
            filter_key = tab.table.key_lookup('FilterFrame')
            if window[filter_key].metadata['visible'] is True:
                tab.table.collapse_expand(window, frame='filter')

            # Set the current tab index
            tabs = [i.key_lookup('Tab') for i in self.tabs]
            self.current_tab = tabs.index(tab_key)

        # Run component parameter events
        elif event in param_keys:
            try:
                param = self.fetch_parameter(event, by_key=True)
            except KeyError:
                logger.error('AuditRule {NAME}: unable to find parameter associated with event key {KEY}'
                             .format(NAME=self.name, KEY=event))
            else:
                param.run_event(window, event, values)

        # Run transaction tab events
        elif event in tab_keys:
            # Fetch the transaction tab
            try:
                tab = self.fetch_tab(event, by_key=True)
            except KeyError:
                logger.error('AuditRule {NAME}: unable to find transaction tab associated with event key {KEY}'
                             .format(NAME=self.name, KEY=event))
            else:
                success = tab.run_event(window, event, values)
                if event == tab.key_lookup('Audit') and success is True:
                    logger.info('AuditRule {NAME}: auditing of transaction {TITLE} was successful'
                                .format(NAME=self.name, TITLE=tab.title))
                    final_index = self.final_tab
                    current_index = self.current_tab

                    # Enable movement to the next tab
                    next_index = current_index + 1
                    if next_index < final_index:
                        next_tab_key = [i.key_lookup('Tab') for i in self.tabs][next_index]
                        next_tab = self.fetch_tab(next_tab_key, by_key=True)
                        logger.debug('AuditRule {NAME}: enabling next tab {TITLE} with index {IND}'
                                     .format(NAME=self.name, TITLE=next_tab.title, IND=next_index))

                        # Enable next tab
                        window[next_tab_key].update(disabled=False, visible=True)

                    # Enable the finalize button when an audit has been run on all tabs.
                    if next_index == final_index:
                        logger.info('AuditRule {NAME}: all audits have been performed - preparing audit summary'
                                    .format(NAME=self.name))
                        window[next_key].update(disabled=False)
                        window[next_key].metadata['disabled'] = False

        # Run transaction summary events
        elif event in summary_keys:
            self.summary.run_event(window, event, values)

        # Save results of the audit
        elif event == save_key or (event == '-ENTER-' and not window[save_key].metadata['disabled']):
            # Get output file from user
            title = self.summary.title.replace(' ', '_')
            outfile = sg.popup_get_file('', title='Save As', default_path=title, save_as=True,
                                        default_extension='pdf', no_window=True,
                                        file_types=(('PDF - Portable Document Format', '*.pdf'),))

            if not outfile:
                msg = 'Please select an output file before continuing'
                mod_win2.popup_error(msg)
            else:
                # Save summary to the program database
                try:
                    save_status = self.summary.save_records()
                except Exception as e:
                    msg = 'database save failed - {ERR}'.format(ERR=e)
                    mod_win2.popup_error(msg)
                    logger.error('AuditRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
                    raise
                else:
                    if save_status is False:
                        msg = 'Database save failed'
                        mod_win2.popup_error(msg)
                    else:
                        msg = 'audit records were successfully saved to the database'
                        mod_win2.popup_notice(msg)
                        logger.info('AuditRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
                        # Save summary to excel or csv file
                        try:
                            self.summary.save_report(outfile)
                        except Exception as e:
                            msg = 'Save to file {FILE} failed - {ERR}'.format(FILE=outfile, ERR=e)
                            mod_win2.popup_error(msg)
                            raise

                        # Reset rule elements
                        current_rule = self.reset_rule(window, current=True)

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
        panel_title = 'Transaction Audit: {}'.format(self.menu_title)
        title_layout = [[sg.Text(panel_title, pad=(pad_frame, pad_frame), font=font_h, background_color=header_col)]]

        # Rule parameter elements
        param_elements = []
        for param in params:
            element_layout = param.layout(padding=((0, pad_h), 0))
            param_elements += element_layout

        start_key = self.key_lookup('Start')
        start_layout = [[mod_lo.B2('Start', key=start_key, pad=(0, 0), disabled=False,
                                   button_color=(bttn_text_col, bttn_bg_col), metadata={'disabled': False},
                                   disabled_button_color=(disabled_text_col, disabled_bg_col),
                                   tooltip='Start transaction audit', use_ttk_buttons=True)]]

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

        tg_layout = [sg.TabGroup([audit_tabs], key=tg_key, pad=(0, 0), enable_events=True,
                                 tab_background_color=inactive_col, selected_title_color=select_col,
                                 title_color=text_col, selected_background_color=bg_col, background_color=bg_col)]

        # Main panel layout
        main_key = self.key_lookup('Panel')
        main_layout = sg.Col([param_layout,
                              [sg.HorizontalSeparator(pad=(0, pad_v), color=mod_const.HEADER_COL)],
                              tg_layout],
                             key=main_key, pad=(0, 0), background_color=bg_col, vertical_alignment='t',
                             visible=True, expand_y=True, expand_x=True)

        # Panels
        summary_layout = self.summary.layout(win_size)

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
            sg.Col([[sg.Button('', key=cancel_key, image_data=mod_const.CANCEL_ICON, image_size=mod_const.BTTN_SIZE,
                               pad=((0, pad_el), 0), disabled=False, tooltip='Return to home screen')]],
                   pad=(0, (pad_v, 0)), justification='l', expand_x=True),
            sg.Col([[sg.Canvas(size=(0, 0), visible=True)]], justification='c', expand_x=True),
            sg.Col([[sg.Button('', key=back_key, image_data=mod_const.LEFT_ICON, image_size=mod_const.BTTN_SIZE,
                               pad=((0, pad_el), 0), disabled=True, tooltip='Return to audit',
                               metadata={'disabled': True}),
                     sg.Button('', key=next_key, image_data=mod_const.RIGHT_ICON, image_size=mod_const.BTTN_SIZE,
                               pad=(pad_el, 0), disabled=True, tooltip='Review audit',
                               metadata={'disabled': True}),
                     sg.Button('', key=save_key, image_data=mod_const.SAVE_ICON, image_size=mod_const.BTTN_SIZE,
                               pad=((pad_el, 0), 0), disabled=True, metadata={'disabled': True},
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
        tab_height = panel_height - 120  # minus size of the tabs and the panel title
        tab_width = panel_width - mod_const.FRAME_PAD * 2  # minus left and right padding

        tabs = self.tabs
        for tab in tabs:
            tab.resize_elements(window, size=(tab_width, tab_height))

        # Resize summary elements
        self.summary.resize_elements(window, (tab_width, tab_height))

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
        start_key = self.key_lookup('Start')
        window[start_key].update(disabled=False)
        window[start_key].metadata['disabled'] = False

        next_key = self.key_lookup('Next')
        window[next_key].update(disabled=True)
        window[next_key].metadata['disabled'] = True

        back_key = self.key_lookup('Back')
        window[back_key].update(disabled=True)
        window[back_key].metadata['disabled'] = True

        save_key = self.key_lookup('Save')
        window[save_key].update(disabled=True)
        window[save_key].metadata['disabled'] = True

        # Switch to first tab in panel
        tg_key = self.key_lookup('TG')
        window[tg_key].Widget.select(0)
        self.current_tab = 0

        # Switch to first tab in summary panel
        tg_key = self.summary.key_lookup('TG')
        window[tg_key].Widget.select(0)

        # Reset rule item attributes and parameters.
        self.reset_parameters(window)
        self.toggle_parameters(window, 'enable')

        # Reset summary panel
        self.summary.reset(window)

        # Reset tab attributes
        for i, tab in enumerate(self.tabs):
            if i == 0:
                tab.reset(window, first=True)
            else:
                tab.reset(window, first=False)

        # Remove any unsaved IDs created during the audit
        if self.in_progress:
            settings.remove_unsaved_ids()

        self.in_progress = False

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
            param.reset(window)

    def toggle_parameters(self, window, value='enable'):
        """
        Enable / Disable audit rule parameter elements.
        """
        for param in self.parameters:
            param.toggle_parameter(window, value)


class AuditTransactionTab:
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

            name (str): configuration entry name for the transaction tab.

            entry (dict): dictionary of optional and required entry arguments.

            parent (str): name of the object's parent element.
        """
        self.name = name
        self.parent = parent
        self.id = randint(0, 1000000000)
        self.elements = ['-{NAME}_{ID}_{ELEM}-'.format(NAME=self.name, ID=self.id, ELEM=i) for i in
                         ['Tab', 'Audit', 'Width', 'Height']]

        try:
            self.title = entry['Title']
        except KeyError:
            self.title = name

        try:
            import_rules = entry['ImportRules']
        except KeyError:
            msg = 'Configuration Error: AuditTransactionTab {NAME}: missing required field "ImportRules".' \
                .format(NAME=name)
            mod_win2.popup_error(msg)
            sys.exit(1)
        else:
            self.import_rules = import_rules

        try:
            self.table = mod_elem.TableElement(name, entry['DisplayTable'])
        except KeyError:
            msg = 'Configuration Error: AuditTransactionTab {NAME}: missing required parameter "DisplayTable"' \
                .format(NAME=name)
            mod_win2.popup_error(msg)
            sys.exit(1)
        except AttributeError as e:
            msg = 'Configuration Error: AuditTransactionTab {NAME}: unable to initialize DisplayTable - {ERR}' \
                .format(NAME=name, ERR=e)
            mod_win2.popup_error(msg)
            sys.exit(1)
        else:
            self.elements += self.table.elements

        try:
            self.record_layout = entry['RecordLayout']
        except KeyError:
            self.record_layout = None

        try:
            self.id_format = re.findall(r'\{(.*?)\}', entry['IDFormat'])
        except KeyError:
            msg = 'Configuration Error: AuditTransactionTab {NAME}: missing required field "IDFormat".' \
                .format(NAME=name)
            mod_win2.popup_error(msg)
            sys.exit(1)

        self.in_progress = False
        self.parameters = None
        self.id_components = []

    def key_lookup(self, component):
        """
        Lookup a component's GUI element key using the component's name.
        """
        element_names = [i[1:-1].split('_')[-1] for i in self.elements]
        if component in element_names:
            key_index = element_names.index(component)
            key = self.elements[key_index]
        else:
            logger.warning('AuditTransactionTab {NAME}: component {COMP} not found in list of audit rule elements'
                           .format(NAME=self.name, COMP=component))
            key = None

        return key

    def fetch_parameter(self, element, by_key: bool = False, by_type: bool = False):
        """
        Fetch a GUI parameter element by name or event key.
        """
        if by_key is True:
            element_type = element[1:-1].split('_')[-1]
            element_names = [i.key_lookup(element_type) for i in self.parameters]
        elif by_type is True:
            element_names = [i.etype for i in self.parameters]
        else:
            element_names = [i.name for i in self.parameters]

        if element in element_names:
            index = element_names.index(element)
            parameter = self.parameters[index]
        else:
            raise KeyError('element {ELEM} not found in list of {NAME} data elements'
                           .format(ELEM=element, NAME=self.name))

        return parameter

    def reset(self, window, first: bool = False):
        """
        Reset the elements and attributes of the audit rule transaction tab.
        """

        # Reset the data table
        self.table.df = pd.DataFrame(columns=list(self.table.columns))
        self.table.update_display(window)

        # Disable table element events
        self.table.disable(window)

        # Disable the audit button
        window[self.key_lookup('Audit')].update(disabled=True)

        # Reset dynamic attributes
        self.parameters = None
        self.id_components = []

        # Reset visible tabs
        visible = True if first is True else False
        logger.debug('AuditTransactionTab {NAME}: re-setting visibility of rule tab to {STATUS}'
                     .format(NAME=self.name, STATUS=visible))

        window[self.key_lookup('Tab')].update(visible=visible)

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
        main_layout = [[self.table.layout(width=tbl_width, height=tbl_height, padding=(0, 0))],
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

        return sg.Tab(self.title, layout, key=self.key_lookup('Tab'), background_color=bg_col, visible=visible,
                      metadata={'visible': visible})

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

    def run_event(self, window, event, values):
        """
        Run an audit rule transaction event.
        """
        audit_key = self.key_lookup('Audit')
        table_keys = self.table.elements

        success = True
        # Run component table events
        if event in table_keys:
            table = self.table

            tbl_key = self.table.key_lookup('Element')
            import_key = self.table.key_lookup('Import')
            if event == tbl_key:  # user clicked to open a table record
                if self.record_layout is not None:
                    # Find index of row
                    try:
                        row_index = values[event][0]
                    except IndexError:  # user double-clicked too quickly
                        logger.warning('AuditTransactionTab {NAME}: no row selected for exporting'
                                       .format(NAME=self.name))
                    else:
                        table.export_row(row_index, layout=self.record_layout, custom=True)
                else:
                    logger.warning('AuditTransactionTab {NAME}: no layout specified for the transaction type'
                                   .format(NAME=self.name))

            elif event == import_key:
                table.import_rows(import_rules=self.import_rules)
                table.update_display(window, window_values=values)

            else:
                table.run_event(window, event, values)

        # Run a transaction audit
        elif event == audit_key:
            try:
                self.audit_transactions()
            except Exception as e:
                msg = 'audit failed on transaction {NAME} - {ERR}'.format(NAME=self.title, ERR=e)
                mod_win2.popup_error(msg)
                logger.error('AuditTransactionTab {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                success = False
            else:
                self.table.df = self.table.filter_table()
                self.table.sort()
                self.table.update_display(window)

        return success

    def load_data(self):
        """
        Load data from the database.
        """
        # Prepare the database query statement
        import_rules = self.import_rules

        param_filters = [i.query_statement(mod_db.get_import_column(import_rules, i.name)) for i in self.parameters]
        filters = param_filters + mod_db.format_import_filters(import_rules)
        table_statement = mod_db.format_tables(import_rules)
        columns = mod_db.format_import_columns(import_rules)

        # Import primary mod_bank data from database
        try:
            df = user.read_db(*user.prepare_query_statement(table_statement, columns=columns, filter_rules=filters))
        except Exception as e:
            msg = 'failed to import data from the database - {ERR}'.format(ERR=e)
            mod_win2.popup_error(msg)
            logger.error('AuditTransactionTab {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
            data_loaded = False
        else:
            logger.info('AuditTransactionTab {NAME}: loaded data for audit rule {RULE}'
                        .format(NAME=self.name, RULE=self.parent))
            self.table.df = self.table.append(df)
            self.table.initialize_defaults()
            self.table._df = self.table.df
            data_loaded = True

        return data_loaded

    def audit_transactions(self):
        """
        Search for missing transactions using scan.
        """
        strptime = datetime.datetime.strptime

        # Class attributes
        import_rules = self.import_rules
        table = self.table

        pkey = table.id_column
        df = table.data()
        id_list = sorted(table.row_ids(), reverse=False)
        existing_imports = table.row_ids(imports=True)

        # Data importing parameters
        filters = mod_db.format_import_filters(import_rules)
        table_statement = mod_db.format_tables(import_rules)
        import_columns = mod_db.format_import_columns(import_rules)

        # Audit parameters
        date_param = self.fetch_parameter('date', by_type=True)
        date_db_col = mod_db.get_import_column(import_rules, date_param.name)
        audit_date = date_param.value
        audit_date_iso = audit_date.strftime("%Y-%m-%d")

        # Search for missing data
        logger.info('AuditTransactionTab {NAME}: searching for missing transactions'.format(NAME=self.name))
        missing_transactions = []
        first_id = None
        first_number_comp = None
        first_date_comp = None
        for index, record_id in enumerate(id_list):
            number_comp = int(self.get_id_component(record_id, 'variable'))
            date_comp = self.get_id_component(record_id, 'date')
            if record_id == self.format_id(number_comp, date=date_comp):  # skip ID that don't conform to proper format
                first_id = record_id
                first_number_comp = number_comp
                first_date_comp = date_comp
                id_list = id_list[index:]

                break

        if audit_date and first_id:  # data table not empty
            logger.debug('AuditTransactionTab {NAME}: first transaction ID is {ID}'.format(NAME=self.name, ID=first_id))

            # Find the date of the most recent transaction prior to current date
            query_str = 'SELECT DISTINCT {DATE} FROM {TBL}'.format(DATE=date_db_col, TBL=table_statement)
            logger.debug('query string is "{STR}" with parameters {PARAMS}'.format(STR=query_str, PARAMS=None))
            dates_df = user.read_db(query_str, None)

            unq_dates = dates_df.iloc[:, 0].tolist()
            unq_dates_iso = [i.strftime("%Y-%m-%d") for i in unq_dates]

            unq_dates_iso.sort()

            current_date_index = unq_dates_iso.index(audit_date_iso)

            try:
                prev_date = strptime(unq_dates_iso[current_date_index - 1], '%Y-%m-%d')
            except IndexError:
                logger.warning('AuditTransactionTab {NAME}: no date found prior to current audit date {DATE}'
                               .format(NAME=self.name, DATE=audit_date_iso))
                prev_date = None
            except ValueError:
                logger.warning('AuditTransactionTab {NAME}: unknown date format {DATE} provided'
                               .format(NAME=self.name, DATE=unq_dates_iso[current_date_index - 1]))
                prev_date = None

            # Query the last transaction from the previous date
            if prev_date:
                logger.info('AuditTransactionTab {NAME}: searching for most recent transaction created on last '
                            'transaction date {DATE}'.format(NAME=self.name, DATE=prev_date.strftime('%Y-%m-%d')))

                import_filters = filters + [('{} = ?'.format(date_db_col),
                                             (prev_date.strftime(settings.date_format),))]
                last_df = user.read_db(*user.prepare_query_statement(table_statement, columns=import_columns,
                                                                     filter_rules=import_filters))
                last_df.sort_values(by=[pkey], inplace=True, ascending=False)

                last_id = None
                prev_date_comp = None
                prev_number_comp = None
                prev_ids = last_df[pkey].tolist()
                for prev_id in prev_ids:
                    try:
                        prev_number_comp = int(self.get_id_component(prev_id, 'variable'))
                    except ValueError:
                        msg = 'inconsistent format found in previous record ID {ID}'.format(ID=prev_id)
                        mod_win2.popup_notice(msg)
                        logger.warning('AuditTransactionTab {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
                        logger.warning('AuditTransactionTab {NAME}: record with unknown format is {ID}'
                                       .format(NAME=self.name, ID=last_df[last_df[pkey] == prev_id]))
                        continue

                    prev_date_comp = self.get_id_component(prev_id, 'date')

                    if prev_number_comp > first_number_comp:
                        continue

                    # Search only for IDs with correct ID formats (skip potential errors)
                    if prev_id == self.format_id(prev_number_comp, date=prev_date_comp):
                        last_id = prev_id
                        break

                if prev_date_comp and prev_number_comp:
                    logger.debug('AuditTransactionTab {NAME}: last transaction ID is {ID} from {DATE}'
                                 .format(NAME=self.name, ID=last_id, DATE=prev_date.strftime('%Y-%m-%d')))

                    logger.debug('AuditTransactionTab {NAME}: searching for skipped transactions between last ID '
                                 '{PREVID} from last transaction date {PREVDATE} and first ID {ID} of current '
                                 'transaction date {DATE}'
                                 .format(NAME=self.name, PREVID=last_id, PREVDATE=prev_date.strftime('%Y-%m-%d'),
                                         ID=first_id, DATE=audit_date_iso))
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

                    nskipped = 0
                    for missing_number in missing_range:
                        missing_id = self.format_id(missing_number, date=first_date_comp)
                        if (missing_id not in id_list) and (missing_id not in existing_imports):
                            nskipped += 1
                            missing_transactions.append(missing_id)

                    logger.debug('AuditTransactionTab {NAME}: found {N} skipped transactions between last ID '
                                 '{PREVID} from last transaction date {PREVDATE} and first ID {ID} of current '
                                 'transaction date {DATE}'
                                 .format(NAME=self.name, N=nskipped, PREVID=last_id,
                                         PREVDATE=prev_date.strftime('%Y-%m-%d'), ID=first_id, DATE=audit_date_iso))

            # Search for skipped transaction numbers
            logger.debug('AuditTransactionTab {NAME}: searching for skipped transactions within the current '
                         'transaction date {DATE}'.format(NAME=self.name, DATE=audit_date_iso))
            prev_number = first_number_comp - 1
            nskipped = 0
            for record_id in id_list:
                record_no = int(self.get_id_component(record_id, 'variable'))
                record_date = self.get_id_component(record_id, 'date')

                if record_id != self.format_id(record_no, date=record_date):  # skip IDs that don't conform to format
                    msg = 'record ID {ID} does not conform to ID format specifications'.format(ID=record_id)
                    logger.warning('AuditTransactionTab {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
                    continue

                if (prev_number + 1) != record_no:
                    missing_range = list(range(prev_number + 1, record_no))
                    for missing_number in missing_range:
                        missing_id = self.format_id(missing_number, date=first_date_comp)
                        if (missing_id not in id_list) and (missing_id not in existing_imports):
                            missing_transactions.append(missing_id)
                            nskipped += 1

                prev_number = record_no

            logger.debug('AuditTransactionTab {NAME}: found {N} skipped transactions from within current '
                         'transaction date {DATE}'.format(NAME=self.name, N=nskipped, DATE=audit_date_iso))

            # Search for missed numbers at end of day
            logger.info('AuditTransactionTab {NAME}: searching for transactions created at the end of the day'
                        .format(NAME=self.name))
            last_id_of_df = id_list[-1]  # last transaction of the dataframe

            import_filters = filters + [('{} = ?'.format(date_db_col),
                                         (audit_date.strftime(settings.date_format),))]
            current_df = user.read_db(*user.prepare_query_statement(table_statement, columns=import_columns,
                                                                    filter_rules=import_filters))

            current_ids = sorted(current_df[pkey].tolist(), reverse=True)
            for current_id in current_ids:
                if last_id_of_df == current_id:
                    break

                try:
                    current_number_comp = int(self.get_id_component(current_id, 'variable'))
                except ValueError:
                    msg = 'inconsistent format found in record ID {ID}'.format(ID=current_id)
                    mod_win2.popup_notice(msg)
                    logger.warning('AuditTransactionTab {NAME}: ID with unknown format is {ID}'
                                   .format(NAME=self.name, ID=current_df[current_df[pkey] == current_id]))
                    continue

                if (current_id == self.format_id(current_number_comp, date=first_date_comp)) and \
                        (current_id not in existing_imports):
                    missing_transactions.append(current_id)

        logger.debug('AuditRuleTransactions {NAME}: potentially missing transactions: {MISS}'
                     .format(NAME=self.name, MISS=missing_transactions))

        # Query database for the potentially missing transactions
        if missing_transactions:
            pkey_db = mod_db.get_import_column(import_rules, pkey)

            filter_values = ['?' for _ in missing_transactions]
            filter_str = '{PKEY} IN ({VALUES})'.format(PKEY=pkey_db, VALUES=', '.join(filter_values))

            filters = [(filter_str, tuple(missing_transactions))]

            # Drop missing transactions if they don't meet the import parameter requirements
            missing_df = user.read_db(*user.prepare_query_statement(table_statement, columns=import_columns,
                                                                    filter_rules=filters, order=pkey_db))
        else:
            missing_df = pd.DataFrame(columns=df.columns)

        # Display import window with potentially missing data
        table.import_df = table.append(missing_df, imports=True)
        if not table.import_df.empty:
            table.import_rows(import_rules=self.import_rules, program_database=False)

    def update_id_components(self):
        """
        """
        parameters = self.parameters
        id_format = self.id_format
        self.id_components = []

        last_index = 0
        logger.debug('AuditTransactionTab {NAME}: ID is formatted as {FORMAT}'.format(NAME=self.name, FORMAT=id_format))
        param_fields = [i.name for i in parameters]
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

            self.id_components.append(part_tup)

            last_index += component_len

        logger.debug('AuditTransactionTab {NAME}: ID updated with components {COMP}'
                     .format(NAME=self.name, COMP=self.id_components))

    def format_id(self, number, date=None):
        """
        """
        number = str(number)

        id_parts = []
        for component in self.id_components:
            comp_name, comp_value, comp_index = component

            if comp_name == 'date':  # component is datestr
                if not date:
                    print('Warning: AuditTransactionTab {NAME}: no date provided for ID number {NUM} ... reverting to '
                          'today\'s date'.format(NAME=self.name, NUM=number))
                    value = datetime.datetime.now().strftime(comp_value)
                else:
                    value = date
            elif comp_name == 'variable':
                value = number.zfill(comp_value)
            else:
                value = comp_value

            id_parts.append(value)

        return ''.join(id_parts)

    def get_id_component(self, identifier, component):
        """
        Extract the specified component values from the provided identifier.
        """
        comp_value = ''
        for id_component in self.id_components:
            comp_name, comp_value, comp_index = id_component

            if component == comp_name:
                try:
                    comp_value = identifier[comp_index[0]: comp_index[1]]
                except IndexError:
                    print('Warning: AuditTransactionTab {NAME}: ID component {COMP} cannot be found in identifier '
                          '{IDENT}'.format(NAME=self.name, COMP=component, IDENT=identifier))

                break

        return comp_value

    def get_component(self, comp_id):
        """
        """
        comp_tup = None
        for component in self.id_components:
            comp_name, comp_value, comp_index = component
            if comp_name == comp_id:
                comp_tup = component

        return comp_tup


class AuditSummary:
    """
    AuditRule summary panel object.
    """

    def __init__(self, name, entry, parent=None):

        self.name = name
        self.parent = parent
        self.id = randint(0, 1000000000)
        self.element_key = '{NAME}_{ID}'.format(NAME=name, ID=self.id)
        self.elements = ['-{NAME}_{ID}_{ELEM}-'.format(NAME=self.name, ID=self.id, ELEM=i) for i in
                         ['TG', 'Title']]

        try:
            self._title = entry['Title']
        except KeyError:
            self._title = '{} Summary'.format(name)

        try:
            record_tabs = entry['Tabs']
        except KeyError:
            msg = 'Configuration Error: AuditRuleSummary {NAME}: missing required configuration parameter "Tabs".'\
                .format(NAME=name)
            mod_win2.popup_error(msg)
            sys.exit(1)
        else:
            self.tabs = []
            for record_type in record_tabs:
                tab = AuditRecordTab(record_type, record_tabs[record_type])

                self.tabs.append(tab)
                self.elements += tab.elements

        try:
            report = entry['Report']
        except KeyError:
            msg = 'Configuration Error: AuditRuleSummary {NAME}: missing required configuration parameter "Report".'\
                .format(NAME=name)
            mod_win2.popup_error(msg)
            sys.exit(1)
        for tab_name in report:
            report_tab = report[tab_name]
            for section_name in report_tab:
                section = report_tab[section_name]

                msg = 'Configuration Error: AuditRuleSummary {NAME}: summary report {SEC} is missing required ' \
                      'parameter "{PARAM}"'
                if 'Title' not in section:
                    section['Title'] = section_name
                if 'Columns' not in section:
                    mod_win2.popup_error(msg.format(NAME=name, PARAM='Columns', SEC=section_name))
                    sys.exit(1)

        self.report = report

        # Dynamic attributes
        self.parameters = None
        self.title = None

    def key_lookup(self, component):
        """
        Lookup a component's GUI element key using the component's name.
        """
        element_names = [i[1:-1].split('_')[-1] for i in self.elements]
        if component in element_names:
            key_index = element_names.index(component)
            key = self.elements[key_index]
        else:
            print('Warning: AuditRuleSummary {NAME}: component {COMP} not found in list of components'
                  .format(NAME=self.name, COMP=component))
            key = None

        return key

    def fetch_tab(self, fetch_key, by_key: bool = False):
        """
        Fetch a transaction audit summary tab object from the list of tabs.
        """
        tabs = self.tabs

        if by_key is True:
            tab_item = None
            for tab in self.tabs:
                if fetch_key in tab.elements:
                    tab_item = tab
                    break

            if tab_item is None:
                raise KeyError('{TAB} not in list of audit rule summary tab elements'.format(TAB=fetch_key))
        else:
            names = [i.name for i in tabs]

            try:
                index = names.index(fetch_key)
            except ValueError:
                raise KeyError('{TAB} not in list of audit rule summary tabs'.format(TAB=fetch_key))
            else:
                tab_item = tabs[index]

        return tab_item

    def reset(self, window):
        """
        Reset summary records.
        """
        self.title = None

        for tab in self.tabs:
            tab.reset(window)

    def run_event(self, window, event, values):
        """
        Run a transaction audit summary event.
        """
        # Run a summary tab event
        tab_keys = [i for j in self.tabs for i in j.elements]
        if event in tab_keys:
            try:
                tab = self.fetch_tab(event, by_key=True)
            except Exception as e:
                print('Error: AuditRuleSummary {NAME}: failed to run event {EVENT} - {ERR}'
                      .format(NAME=self.name, EVENT=event, ERR=e))
            else:
                tab.run_event(window, event, values)

    def layout(self, win_size: tuple = None):
        """
        Generate a GUI layout for the Audit Rule Summary.
        """
        if win_size:
            width, height = win_size
        else:
            width, height = (mod_const.WIN_WIDTH, mod_const.WIN_HEIGHT)

        # Layout settings
        pad_v = mod_const.VERT_PAD

        bg_col = mod_const.ACTION_COL
        inactive_col = mod_const.INACTIVE_COL
        text_col = mod_const.TEXT_COL
        select_col = mod_const.SELECT_TEXT_COL

        font_h = mod_const.BOLD_FONT

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

        # Panel Title
        title_key = self.key_lookup('Title')
        title_layout = [sg.Col([[sg.Text(self.title, key=title_key, size=(int(frame_width / int(font_h[1])), 1),
                                         font=font_h, background_color=bg_col, tooltip=self.title)]],
                               vertical_alignment='c', background_color=bg_col, expand_x=True)]

        # Record tabs
        record_tabs = []
        for tab in self.tabs:
            tab_key = tab.key_lookup('Tab')
            tab_title = tab.title
            tab_layout = tab.record.layout(win_size=(tab_width, tab_height), ugroup=user.access_permissions())
            record_tabs.append(sg.Tab(tab_title, tab_layout, key=tab_key, background_color=bg_col))

        tg_key = self.key_lookup('TG')
        tg_layout = [sg.TabGroup([record_tabs], key=tg_key, pad=(0, 0), background_color=bg_col,
                                 tab_background_color=inactive_col, selected_background_color=bg_col,
                                 selected_title_color=select_col, title_color=text_col)]

        # Panel layout
        layout = sg.Col([title_layout, [sg.HorizontalSeparator(pad=(0, pad_v), color=mod_const.HEADER_COL)], tg_layout],
                        key=self.element_key, background_color=bg_col, vertical_alignment='t', visible=False,
                        expand_y=True, expand_x=True)

        return layout

    def resize_elements(self, window, size):
        """
        Resize the summary panel.
        """
        width, height = size

        tabs = self.tabs
        for tab in tabs:
            # Reset summary item attributes
            tab.record.resize(window, win_size=(width, height * 0.9))

    def update_title(self, window, params):
        """
        Update summary panel title to include audit parameters.
        """
        # Update summary title with parameter values, if specified in title format
        try:
            title_components = re.findall(r'\{(.*?)\}', self._title)
        except TypeError:
            title_components = []
        else:
            logger.debug('AuditRuleSummary {NAME}: summary title components are {COMPS}'
                         .format(NAME=self.name, COMPS=title_components))

        title_params = {}
        for param in params:
            param_col = param.name

            # Check if parameter composes part of title
            if param_col in title_components:
                display_value = param.format_display()
                logger.debug('AuditRuleSummary {NAME}: adding parameter value {VAL} to title'
                             .format(NAME=self.name, VAL=display_value))
                title_params[param_col] = display_value
            else:
                logger.warning('AuditRuleSummary {NAME}: parameter {PARAM} not found in title'
                               .format(NAME=self.name, PARAM=param_col))

        try:
            summ_title = self._title.format(**title_params)
        except KeyError as e:
            logger.error('AuditRuleSummary {NAME}: formatting summary title failed due to {ERR}'
                         .format(NAME=self.name, ERR=e))
            summ_title = self._title

        logger.info('AuditRuleSummary {NAME}: formatted summary title is {TITLE}'
                    .format(NAME=self.name, TITLE=summ_title))

        title_key = self.key_lookup('Title')
        window[title_key].update(value=summ_title)

        self.title = summ_title

    def load_records(self, params):
        """
        Load existing audit records or create new records.
        """
        tabs = self.tabs

        exists = []
        for tab in tabs:
            exists.append(tab.load_record(params))

        return any(exists)

    def save_report(self, filename):
        """
        Generate summary report and save to a PDF file.
        """
        relativedelta = dateutil.relativedelta.relativedelta
        strptime = datetime.datetime.strptime
        is_float_dtype = pd.api.types.is_float_dtype
        is_datetime_dtype = pd.api.types.is_datetime64_any_dtype
        date_fmt = settings.format_date_str(date_str=settings.display_date_format)
        date_offset = settings.get_date_offset()

        report_def = self.report

        print('Info: AuditRule {NAME}: saving summary report to {FILE}'.format(NAME=self.name, FILE=filename))

        tabs = []
        for tab_name in report_def:
            reference_tab = self.fetch_tab(tab_name)
            try:
                notes = reference_tab.record.fetch_element('Notes')
            except KeyError:
                notes_title = notes_value = ""
            else:
                notes_title = notes.description
                notes_value = notes.format_display()

            tab_dict = {'title': '{TITLE}: {ID}'.format(TITLE=reference_tab.record.title,
                                                        ID=reference_tab.record.record_id()),
                        'notes': (notes_title, notes_value)}

            # Fetch component accounts table from
            comp_table = reference_tab.record.fetch_component('account')
            print(comp_table.df.head())

            section_def = report_def[tab_name]
            sections = []
            for section_name in section_def:
                section = section_def[section_name]
                title = section['Title']

                # Subset table rows based on configured subset rules
                try:
                    sub_rule = section['Subset']
                except KeyError:
                    subset_df = comp_table.data()
                else:
                    try:
                        subset_df = comp_table.filter_deleted(comp_table.subset(sub_rule))
                    except (NameError, SyntaxError) as e:
                        print('Error: AuditRuleSummary {NAME}, Report {SEC}: unable to subset table on rule {SUB} - '
                              '{ERR}'.format(NAME=self.name, SEC=section_name, SUB=sub_rule, ERR=e))
                        continue
                    else:
                        if subset_df.empty:
                            print('Warning: AuditRuleSummary {NAME}, Report {SEC}: sub-setting on rule "{SUB}" '
                                  'removed all records'.format(NAME=self.name, SEC=tab_name, SUB=sub_rule))
                            continue

                # Select columns configured
                try:
                    subset_df = subset_df[section['Columns']]
                except KeyError as e:
                    print('Error: AuditRuleSummary {NAME}, Report {SEC}: unknown column provided - {ERR}'
                          .format(NAME=self.name, SEC=section_name, ERR=e))
                    continue

                # Format table for display
                display_df = subset_df.copy()
                for column in subset_df.columns:
                    dtype = subset_df[column].dtype
                    if is_float_dtype(dtype):
                        display_df[column] = display_df[column].apply('{:,.2f}'.format)
                    elif is_datetime_dtype(dtype):
                        display_df[column] = \
                            display_df[column].apply(lambda x: (strptime(x.strftime(date_fmt), date_fmt)
                                                                + relativedelta(years=+date_offset)).strftime(date_fmt)
                                                                if pd.notnull(x) else '')

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
                annotations = comp_table.annotate_display(grouped_df)
                colors = {i: comp_table.annotation_rules[j]['BackgroundColor'] for i, j in annotations.items()}
                try:
                    html_out = replace_nth(html_str, '<tr>', '<tr style="background-color: {}">', colors)
                except Exception as e:
                    print('Warning: AuditRuleSummary {NAME}, Report {SEC}: failed to annotate output - {ERR}'
                          .format(NAME=self.name, SEC=section_name, ERR=e))
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
            print('Error: AuditRuleSummary {NAME}: writing to PDF failed - {ERR}'
                  .format(NAME=self.name, ERR=e))
            status = False
        else:
            status = True

        return status

    def save_records(self):
        """
        Save results of an audit to the program database defined in the configuration file.
        """
        tabs = self.tabs

        logger.debug('AuditRuleSummary {NAME}: verifying that all required fields have input'.format(NAME=self.name))
        for tab in tabs:
            # Verify that all required fields for tab record have values
            for param in tab.record.parameters:
                if param.required is True and param.value_set() is False:
                    msg = 'record {ID} is missing values for required field {FIELD}' \
                        .format(ID=tab.record.record_id(), FIELD=param.description)
                    logger.warning('AuditRuleSummary {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
                    mod_win2.popup_error(msg)

                    return False

            # Verify that tab record components have values for their required fields.
            for component_table in tab.record.components:
                comp_df = component_table.data()

                required_columns = component_table.required_columns
                for required_column in required_columns:
                    has_na = comp_df[required_column].isnull().any()
                    logger.debug('AuditRuleSummary {NAME}: required column {COL} in component table {TBL} has NA '
                                 'values: {HAS}'.format(NAME=self.name, COL=required_column, TBL=component_table.name,
                                                        HAS=has_na))
                    if has_na:
                        display_map = {j: i for i, j in component_table.display_columns.items()}
                        try:
                            display_column = display_map[required_column]
                        except KeyError:
                            display_column = required_column

                        msg = 'missing values for required column {COL} in component table {TBL}'\
                            .format(COL=display_column, TBL=component_table.name)
                        logger.warning('AuditRuleSummary {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
                        mod_win2.popup_error(msg)

                        return False

        logger.info('AuditRuleSummary {NAME}: saving audit records and their components'.format(NAME=self.name))
        success = []
        for tab in tabs:
            # Save audit tab record
            success.append(tab.save_record())

        return all(success)


class AuditRecordTab:
    """
    Class to store information about an audit record.
    """

    def __init__(self, name, entry):

        self.name = name
        self.id = randint(0, 1000000000)
        self.element_key = '{NAME}_{ID}'.format(NAME=name, ID=self.id)
        self.elements = ['-{NAME}_{ID}_{ELEM}-'.format(NAME=self.name, ID=self.id, ELEM=i) for i in
                         ['Tab']]

        record_entry = settings.records.fetch_rule(name)
        self.record = mod_records.TAuditRecord(record_entry, level=0)
        self.record.metadata = []
        self.elements += self.record.elements

        try:
            self.merge = bool(int(entry['MergeTransactions']))
        except KeyError:
            msg = 'missing required configuration parameter "MergeTransactions"'
            logger.error('TransactionAuditRecord {NAME}: {MSG}'.format(NAME=name, MSG=msg))
            sys.exit(1)
        except ValueError:
            msg = 'unsupported value provided to configuration parameter "MergeTransactions". Supported values are 0 ' \
                  '(False) or 1 (True)'
            logger.error('TransactionAuditRecord {NAME}: {MSG}'.format(NAME=name, MSG=msg))
            sys.exit(1)

        try:
            self.merge_columns = entry['MergeOn']
        except KeyError:
            self.merge_columns = []

        try:
            self.title = entry['Title']
        except KeyError:
            self.title = name

        try:
            self.deposit_type = entry['DepositRecordType']
        except KeyError:
            self.deposit_type = None

        try:
            self.summary_mapping = entry['SummaryMapping']
        except KeyError:
            msg = 'missing required configuration parameter "SummaryMapping"'
            logger.error('TransactionAuditRecord {NAME}: {MSG}'.format(NAME=name, MSG=msg))
            sys.exit(1)

        try:
            self.record_mapping = entry['RecordMapping']
        except KeyError:
            msg = 'missing required configuration parameter "RecordMapping"'
            logger.error('TransactionAuditRecord {NAME}: {MSG}'.format(NAME=name, MSG=msg))
            sys.exit(1)

        try:
            self.defaults = entry['Defaults']
        except KeyError:
            self.defaults = {}

    def key_lookup(self, component):
        """
        Lookup a component's GUI element key using the component's name.
        """
        element_names = [i[1:-1].split('_')[-1] for i in self.elements]
        if component in element_names:
            key_index = element_names.index(component)
            key = self.elements[key_index]
        else:
            logger.warning('AuditRecordTab {NAME}: component {COMP} not found in list of components'
                           .format(NAME=self.name, COMP=component))
            key = None

        return key

    def reset(self, window):
        """
        Reset Summary tab record.
        """
        self.record.reset(window)

    def run_event(self, window, event, values):
        """
        Run an audit summary record event.
        """
        record = self.record
        record_keys = record.elements

        if event in record_keys:
            self.record.run_event(window, event, values)

    def load_record(self, params):
        """
        Load previous audit (if exists) and IDs from the program database.
        """
        # Prepare the database query statement
        record_entry = settings.records.fetch_rule(self.name)
        import_rules = record_entry.import_rules

        filters = mod_db.format_import_filters(import_rules)
        table_statement = mod_db.format_tables(import_rules)
        columns = mod_db.format_import_columns(import_rules)

        # Add parameter values to the filter statement
        param_filters = [i.query_statement(mod_db.get_import_column(import_rules, i.name)) for i in params]
        filters += param_filters

        logger.info('AuditRecordTab {NAME}: attempting to load an existing audit record'.format(NAME=self.name))

        # Import record from database
        try:
            import_df = user.read_db(*user.prepare_query_statement(table_statement, columns=columns,
                                                                   filter_rules=filters), prog_db=True)
        except Exception as e:
            mod_win2.popup_error('Attempt to import data from the database failed. Use the debug window for more '
                                 'information')
            raise IOError('AuditSummaryTab {NAME}: failed to import data from the database - {ERR}'
                          .format(NAME=self.name, ERR=e))
        else:
            if not import_df.empty:  # Audit record already exists in database for the chosen parameters
                msg = 'AuditSummaryTab {NAME}: an audit record already exists for the chosen parameters'\
                    .format(NAME=self.name)
                logger.info(msg)
                return True
            else:  # audit has not been performed yet
                logger.info('AuditSummaryTab {NAME}: no existing audit record for the supplied parameters ... '
                            'creating a new record'.format(NAME=self.name))
                record = self.record
                record_entry = settings.records.fetch_rule(self.name)
                param_types = [i.etype for i in params]
                param_names = [i.name for i in params]
                date_index = param_types.index('date')

                # Create new record
                record_date = params[date_index].value
                record_id = record_entry.create_id(record_date, offset=settings.get_date_offset())
                if not record_id:
                    raise IOError('failed to create a record ID for the {NAME} audit'.format(NAME=self.name))

                record_data = {'RecordID': record_id, 'RecordDate': record_date}

                for element in record.parameters:
                    element_name = element.name
                    if element_name in param_names:
                        param = params[param_names.index(element_name)]
                        logger.debug('AuditRuleTab {NAME}: adding value {VAL} from parameter {PARAM} to data element '
                                     '{ELEM}'.format(NAME=self.name, VAL=param.value, PARAM=param.name,
                                                     ELEM=element_name))
                        record_data[param.name] = param.value
                    else:
                        logger.debug('AuditRuleTab {NAME}: no values found for data element {ELEM}'
                                     .format(NAME=self.name, ELEM=element_name))

                record.initialize(record_data, new=False)

                return False

    def save_record(self):
        """
        Save audit record to the program database defined in the configuration file.
        """
        record = self.record
        ref_table = settings.reference_lookup

        # Prepare to export associated deposit records for the relevant account records
        statements = {}

        account_table = self.record.fetch_component('account')
        ref_type = account_table.record_type
        account_df = account_table.data()
        account_header = account_df.columns.tolist()
        if 'Account' not in account_header:
            logger.warning('AuditRecordTab {NAME}: required column "Account" not found in the account table header'
                           .format(NAME=self.name))
            return False

        record_entry = settings.records.fetch_rule(self.deposit_type)
        if not record_entry:
            logger.warning('AuditRecordTab {NAME}: a deposit record type was not configured for the audit record. No '
                           'deposit records will be automatically created for the account records.'
                           .format(NAME=self.name))
            return False
        else:
            record_type = record_entry.name

        # Create deposit records for current account records
        deposit_header = mod_db.format_record_columns(record_entry.import_rules)
        deposit_df = pd.DataFrame(columns=deposit_header)
        for index, row in account_df.iterrows():
            deposit_data = pd.Series(index=deposit_header)

            account_id = row[account_table.id_column]
            deposit_data['AccountID'] = account_id

            try:
                account_no = row['Account']
            except KeyError:
                msg = 'missing the required column "Account" from the "{TYPE}" table'.format(TYPE=ref_type)
                logger.warning('AuditRecordTab {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
                mod_win2.popup_error(msg)

                return False

            if account_no == 'resting':  # do not create deposit records for account records in the resting account
                continue

            # Add value to new deposit record based on account record values
            for colname in account_header:
                if colname in deposit_header:
                    deposit_data[colname] = row[colname]

#            # Create a new record ID for the deposit record
#            deposit_date = row[account_table.date_column]
#            deposit_id = record_entry.create_id(deposit_date, offset=settings.get_date_offset())
#            if not deposit_id:
#                msg = 'failed to create a {TYPE} record associated with the {RTYPE} record {ID}'\
#                    .format(NAME=self.name, TYPE=record_type, RTYPE=ref_type, ID=account_id)
#                logger.error('AuditRecordTab {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
#                mod_win2.popup_error(msg)
#
#                continue
#
#            deposit_data['RecordID'] = deposit_id
            # Add the deposit date
            try:
                payment_date = row['PaymentDate']
            except KeyError:
                msg = 'missing the column "PaymentDate" from the "{TYPE}" table'.format(TYPE=ref_type)
                logger.warning('AuditRecordTab {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
                mod_win2.popup_error(msg)
            else:
                if payment_date:
                    deposit_data['DepositDate'] = payment_date
                else:
                    msg = 'no deposit date set for the new "{TYPE}" record associated with "{RTYPE}" record "{ID}"'\
                        .format(TYPE=record_type, RTYPE=ref_type, ID=account_id)
                    logger.warning('AuditRecordTab {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
                    mod_win2.popup_error(msg)

            # Add the deposit amount
            try:
                deposit_amount = row['CorrectedAmount']
            except KeyError:
                msg = 'missing deposit amount for new "{TYPE}" record associated with "{RTYPE}" record "{ID}"'\
                    .format(TYPE=record_type, RTYPE=ref_type, ID=account_id)
                logger.warning('AuditRecordTab {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
                mod_win2.popup_error(msg)
            else:
                if deposit_amount is not None:
                    deposit_data['DepositAmount'] = deposit_amount
                else:
                    msg = 'no deposit amount set for new "{TYPE}" record associated with "{RTYPE}" record "{ID}"'\
                        .format(TYPE=record_type, RTYPE=ref_type, ID=account_id)
                    logger.warning('AuditRecordTab {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
                    mod_win2.popup_error(msg)

            deposit_df = deposit_df.append(deposit_data, ignore_index=True)

        # Create new record IDs for the deposit records
        try:
            date_list = pd.to_datetime(deposit_df[account_table.date_column], errors='coerce')
        except KeyError:
            msg = 'failed to create "{TYPE}" records associated with "{RTYPE}" records - failed to create IDs for ' \
                  'the new records'.format(TYPE=record_type, RTYPE=ref_type)
            logger.error('AuditRecordTab {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
            mod_win2.popup_error(msg)

            return False
        else:
            date_list = date_list.tolist()

        deposit_ids = record_entry.create_record_ids(date_list, offset=settings.get_date_offset())
        if not deposit_ids:
            msg = 'failed to create {TYPE} records associated with the {RTYPE} record IDs' \
                .format(NAME=self.name, TYPE=record_type, RTYPE=ref_type)
            logger.error('AuditRecordTab {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
            mod_win2.popup_error(msg)

            return False

        deposit_df['RecordID'] = deposit_ids
        statements = record_entry.export_table(deposit_df, statements=statements, id_field='RecordID', id_exists=False)

        # Save the associations to the references database table
        for index, row in deposit_df.iterrows():
            deposit_id = row['RecordID']
            account_id = row['AccountID']

            # Save reference to the account record
            ref_columns = ['DocNo', 'DocType', 'RefNo', 'RefType', 'RefDate', settings.creator_code,
                           settings.creation_date, 'IsParentChild']
            ref_values = (deposit_id, record_type, account_id, ref_type, datetime.datetime.now(), user.uid,
                          datetime.datetime.now(), True)

            statement, params = user.prepare_insert_statement(ref_table, ref_columns, ref_values)
            try:
                statements[statement].append(params)
            except KeyError:
                statements[statement] = [params]

            # Save reference to the audit record
            audit_id = record.record_id()
            audit_record_type = record.name
            ref_columns = ['DocNo', 'DocType', 'RefNo', 'RefType', 'RefDate', settings.creator_code,
                           settings.creation_date, 'IsParentChild']
            ref_values = (audit_id, audit_record_type, deposit_id, record_type, datetime.datetime.now(), user.uid,
                          datetime.datetime.now(), True)

            statement, params = user.prepare_insert_statement(ref_table, ref_columns, ref_values)
            try:
                statements[statement].append(params)
            except KeyError:
                statements[statement] = [params]

        # Export audit record
        saved = record.save(statements=statements)

        return saved

    def map_summary(self, rule_tabs):
        """
        Populate totals table with audit tab summary totals.
        """
        operators = set('+-*/%')

        name = self.name
        totals = self.record.fetch_element('Totals')
        df = totals.df.copy()

        logger.debug('AuditRuleTab {NAME}: mapping transaction summaries to audit totals'
                     .format(NAME=self.name))

        # Store transaction table summaries for mapping
        summary_map = {}
        for tab in rule_tabs:
            tab_name = tab.name
            summary = tab.table.summarize_table()
            for rule_name, rule_value in summary:
                summary_map['{TBL}.{COL}'.format(TBL=tab_name, COL=rule_name)] = rule_value

        # Map audit totals columns to transaction table summaries
        db_columns = totals.df.columns.tolist()
        mapping_columns = self.summary_mapping
        for column in db_columns:
            try:
                mapper = mapping_columns[column]
            except KeyError:
                logger.debug('AuditSummaryTab {NAME}: column {COL} not found in list of mapping columns ... '
                             'setting value to zero'.format(NAME=name, COL=column))
                summary_total = 0
            else:
                # Add audit tab summaries to totals table
                rule_values = []
                for component in mod_dm.parse_operation_string(mapper):
                    if component in operators:
                        rule_values.append(component)
                        continue

                    try:  # component is numeric
                        float(component)
                    except ValueError:
                        if component in summary_map:
                            rule_values.append(summary_map[component])
                        else:
                            logger.error('AuditSummaryTab {NAME}: column {COL} not found in transaction table summaries'
                                         .format(NAME=name, COL=component))
                            rule_values.append(0)

                    else:
                        rule_values.append(component)

                try:
                    summary_total = eval(' '.join([str(i) for i in rule_values]))
                except Exception as e:
                    logger.warning('AuditSummaryTab {NAME}: failed to evaluate summary totals - {ERR}'
                                   .format(NAME=self.name, ERR=e))
                    summary_total = 0

            logger.debug('AuditSummaryTab {NAME}: adding {SUMM} to column {COL}'
                         .format(NAME=name, SUMM=summary_total, COL=column))

            df.at[0, column] = summary_total
            df[column] = pd.to_numeric(df[column], downcast='float')

        totals.df = df

    def map_transactions(self, rule_tabs, params):
        """
        Map transaction records from the audit to account records.
        """
        tab_names = [i.name for i in rule_tabs]

        logger.debug('AuditRuleTab {NAME}: mapping records from the transaction tables to the audit record'
                     .format(NAME=self.name))

        component_table = self.record.fetch_component('account')
        header = component_table.df.columns.tolist()
        record_entry = settings.records.fetch_rule(component_table.record_type)
        append_df = pd.DataFrame(columns=header)

        record_date = None
        for param in params:
            if param.etype == 'date':
                record_date = param.value

        # Map transaction data to transaction records
        record_mapping = self.record_mapping
        for payment_type in record_mapping:
            table_rules = record_mapping[payment_type]
            for table in table_rules:
                table_rule = table_rules[table]
                try:
                    subset_rule = table_rule['Subset']
                except KeyError:
                    logger.warning('AuditRuleTab {NAME}: record mapping payment type {TYPE}, table {TBL} is missing '
                                   'required parameter "Subset"'.format(NAME=self.name, TYPE=payment_type, TBL=table))
                    continue

                try:
                    column_map = table_rule['ColumnMapping']
                except KeyError:
                    logger.warning('AuditRuleTab {NAME}: record mapping payment type {TYPE}, table {TBL} is missing '
                                   'required parameter "ColumnMapping"'
                                   .format(NAME=self.name, TYPE=payment_type, TBL=table))
                    continue

                if table not in tab_names:
                    logger.warning('AuditRuleTab {NAME}: unknown transaction table {TBL} provided to record_mapping '
                                   '{TYPE}'.format(NAME=self.name, TBL=table, TYPE=payment_type))
                    continue
                else:
                    tab = rule_tabs[tab_names.index(table)]

                # Subset tab item dataframe using subset rules defined in the ReferenceTable parameter
                logger.debug('AuditRuleTab {NAME}: sub-setting reference table {REF} based on defined payment {TYPE} '
                             'rule {RULE}'.format(NAME=self.name, REF=table, TYPE=payment_type, RULE=subset_rule))
                try:
                    subset_df = tab.table.subset(subset_rule)
                except Exception as e:
                    logger.warning('AuditRuleTab {NAME}: unable to subset reference table {REF} - {ERR}'
                                   .format(NAME=self.name, REF=table, ERR=e))
                    continue

                if subset_df.empty:
                    logger.debug('AuditRuleTab {NAME}: no data from reference table {REF} to add to the audit record'
                                 .format(NAME=self.name, REF=table))
                    continue

                for index, row in subset_df.iterrows():
                    record_data = pd.Series(index=header)

                    # Add parameter values to the account record elements
                    for param in params:
                        try:
                            record_data[param.name] = param.value
                        except KeyError:
                            continue

                    if record_date is None:
                        record_date = record_data['RecordDate']

                    record_data['PaymentType'] = payment_type
                    record_data['RecordDate'] = record_date

                    # Map row values to the account record elements
                    for column in column_map:
                        if column not in header:
                            logger.warning('AuditRecordTab {NAME}: mapped column {COL} not found in record elements'
                                           .format(COL=column, NAME=self.name))
                            continue

                        reference = column_map[column]
                        try:
                            ref_val = mod_dm.evaluate_rule(row, reference, as_list=True)[0]
                        except Exception as e:
                            msg = 'failed to add mapped column {COL} - {ERR}'.format(COL=column, ERR=e)
                            logger.warning('AuditRecordTab {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
                        else:
                            record_data[column] = ref_val

                    # Add record to the components table
                    append_df = append_df.append(record_data, ignore_index=True)

        # Remove NA columns
        append_df = append_df[append_df.columns[~append_df.isna().all()]]

        if self.merge is True:  # transaction records should be merged into one (typical for mod_cash transactions)
            merge_on = [i for i in append_df.columns.tolist() if i not in self.merge_columns]
            logger.debug('AuditRecordTab {NAME}: merging rows on columns {COLS}'.format(NAME=self.name, COLS=merge_on))
            final_df = append_df.groupby(merge_on).sum().reset_index()
        else:  # create individual records for each transaction
            final_df = append_df

        final_df = component_table.set_datatypes(final_df)

        record_ids = record_entry.create_record_ids([record_date for _ in range(final_df.shape[0])],
                                                    offset=settings.get_date_offset())
        if not record_ids:
            msg = 'failed to create a record IDs for the table entries'
            logger.error(msg)
            raise IOError(msg)
        else:
            final_df[component_table.id_column] = record_ids

    #        for index, row in final_df.iterrows():
    #            record_id = record_entry.create_id(record_date, offset=settings.get_date_offset())
#            if not record_id:
#                msg = 'failed to create a record ID for transaction {TRANS}'.format(TRANS=row)
#                logger.error('Error: {MSG}'.format(MSG=msg))
#                mod_win2.popup_error(msg)
#
#                continue
#
#            logger.info('AuditRecordTab {NAME}: adding transaction record {ID} to the audit record accounts table'
#                        .format(NAME=self.name, ID=record_id))
#            final_df.at[index, 'RecordID'] = record_id

        component_table.df = component_table.append(final_df)

        # Add defaults to the account records
        component_table.df = component_table.initialize_defaults()
        component_table._df = component_table.df

    def update_display(self, window):
        """
        Update the audit record summary tab's record display.
        """
        self.record.update_display(window)


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

        if isinstance(ns, dict):
            new_fmt = new.format(ns[count])
        else:
            new_fmt = new

        before = new_s[:start_index]
        after = new_s[start_index:]
        after = after.replace(sub, new_fmt, 1)  # only replace first instance of substring
        new_s = before + after

    return new_s
