"""
REM transaction audit configuration classes and functions. Includes audit rules, audit objects, and rule parameters.
"""
import datetime
import os
import re
import sys
from random import randint

import PySimpleGUI as sg
import pandas as pd
import pdfkit
from jinja2 import Environment, FileSystemLoader

import REM.constants as mod_const
import REM.data_manipulation as mod_dm
import REM.database as mod_db
import REM.elements as mod_elem
import REM.layouts as mod_lo
import REM.parameters as mod_param
import REM.records as mod_records
import REM.secondary as mod_win2
from REM.client import logger, settings, user


class AuditRule:
    """
    Class to store and manage a configured audit rule.

    Attributes:

        name (str): audit rule name.

        id (int): rule element number.

        element_key (str): GUI element key.

        elements (list): list of rule GUI element keys.

        menu_title (str): menu title for the audit rule.

        menu_flags (dict): submenu flags that change the initial behavior of the rule.

        permissions (str): permissions required to view the audit. Default: user.

        parameters (list): list of filter parameters.

        transactions (list): list of audit transaction tabs.

        records (list): list of audit record tabs.
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
        self.elements = ['-{NAME}_{ID}_{ELEM}-'.format(NAME=self.name, ID=self.id, ELEM=i) for i in
                         ('Cancel', 'Start', 'Back', 'Next', 'Save', 'PanelWidth', 'PanelHeight', 'FrameHeight',
                          'FrameWidth', 'TransactionTG', 'SummaryTG', 'TransactionPanel', 'SummaryPanel', 'Panels',
                          'PanelGroup', 'Buttons', 'Title', 'Frame', 'Header')]

        self.bindings = [self.key_lookup(i) for i in ('Cancel', 'Start', 'Back', 'Next', 'Save')]

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
        except KeyError:  # default permission for an audit rule is 'user'
            self.permissions = 'user'

        self.parameters = []
        try:
            params = entry['RuleParameters']
        except KeyError:
            msg = 'missing required parameter "RuleParameters"'
            logger.error('AuditRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            raise AttributeError(msg)

        for param_name in params:
            param_entry = params[param_name]
            try:
                param = mod_param.initialize_parameter(param_name, param_entry)
            except Exception as e:
                logger.error('AuditRule {NAME}: {MSG}'.format(NAME=self.name, MSG=e))

                raise AttributeError(e)

            self.parameters.append(param)
            self.bindings.extend(param.bindings)

        self.transactions = []
        try:
            transaction_entries = entry['AuditTransactions']
        except KeyError:
            msg = 'AuditRule {NAME}: missing required parameter "AuditTransactions"'.format(NAME=name)
            mod_win2.popup_error(msg)

            raise AttributeError(msg)

        for transaction_name in transaction_entries:
            transaction_entry = transaction_entries[transaction_name]
            transaction = AuditTransaction(transaction_name, transaction_entry, parent=self.name)

            self.transactions.append(transaction)
            self.bindings.extend(transaction.bindings)

        try:
            records = entry['AuditRecords']
        except KeyError:
            msg = 'missing required parameter "AuditRecords"'
            logger.error('AuditRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            raise AttributeError(msg)
        else:
            self.records = []
            for record_type in records:
                record_tab = AuditRecord(record_type, records[record_type], parent=self.name)

                self.records.append(record_tab)
                self.bindings.extend(record_tab.bindings)

        try:
            self._title = entry['Title']
        except KeyError:
            self._title = '{} Summary'.format(name)

        self.in_progress = False

        self.panel_keys = {0: self.key_lookup('TransactionPanel'), 1: self.key_lookup('SummaryPanel')}
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
            logger.warning('AuditRule {NAME}: component {COMP} not found in list of rule components'
                           .format(NAME=self.name, COMP=component))
            key = None

        return key

    def bind_keys(self, window):
        """
        Bind panel-element hotkeys.
        """
        # Bind events to element keys
        logger.debug('AuditRule {NAME}: binding record element hotkeys'.format(NAME=self.name))

        # Bind audit record hotkeys
        for audit_tab in self.records:
            for record_element in audit_tab.record.record_elements():
                record_element.bind_keys(window)

        # Bind transaction table hotkeys
        for transaction_tab in self.transactions:
            transaction_tab.table.bind_keys(window)

    def fetch_tab(self, tab_key):
        """
        Fetch an audit record or a transaction by its tab key.
        """
        all_groups = self.transactions + self.records
        tabs = [i.key_lookup('Tab') for i in all_groups]

        if tab_key in tabs:
            index = tabs.index(tab_key)
            tab_obj = all_groups[index]
        else:
            raise KeyError('tab key {KEY} not found in the list of audit rule object elements'.format(KEY=tab_key))

        return tab_obj

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

    def events(self):
        """
        Return a list of all events allowed under the rule.
        """
        return self.bindings

    def run_event(self, window, event, values):
        """
        Run a transaction audit event.
        """
        current_rule = self.name

        cancel_key = self.key_lookup('Cancel')
        next_key = self.key_lookup('Next')
        back_key = self.key_lookup('Back')
        start_key = self.key_lookup('Start')
        save_key = self.key_lookup('Save')
        tg_key = self.key_lookup('TransactionTG')
        summary_tg_key = self.key_lookup('SummaryTG')

        # Run an audit record event
        summary_keys = [i for j in self.records for i in j.bindings]
        if event in summary_keys:
            # Fetch the current audit record tab
            tab_key = window[summary_tg_key].Get()
            try:
                tab = self.fetch_tab(tab_key)
            except KeyError:
                logger.error('AuditRule {NAME}: unable to find the audit record associated with tab key "{KEY}"'
                             .format(NAME=self.name, KEY=tab_key))
            else:
                tab.run_event(window, event, values)

            return current_rule

        # Run a transaction event
        tab_keys = [i for j in self.transactions for i in j.bindings]
        if event in tab_keys:
            # Fetch the current transaction tab
            tab_key = window[tg_key].Get()
            try:
                tab = self.fetch_tab(tab_key)
            except KeyError:
                logger.error('AuditRule {NAME}: unable to find the transaction associated with tab key "{KEY}"'
                             .format(NAME=self.name, KEY=tab_key))
            else:
                # Run the tab event
                success = tab.run_event(window, event, values)

                # Enable the next tab if an audit event was successful
                if event == tab.key_lookup('Audit') and success is True:
                    logger.info('AuditRule {NAME}: auditing of transaction {TITLE} was successful'
                                .format(NAME=self.name, TITLE=tab.title))
                    tab_key = window[tg_key].Get()
                    tabs = [i.key_lookup('Tab') for i in self.transactions]
                    final_index = len(tabs)
                    current_index = tabs.index(tab_key)

                    # Enable movement to the next tab
                    next_index = current_index + 1
                    if next_index < final_index:
                        next_tab_key = [i.key_lookup('Tab') for i in self.transactions][next_index]
                        next_tab = self.fetch_tab(next_tab_key)
                        logger.debug('AuditRule {NAME}: enabling next tab {TITLE} with index {IND}'
                                     .format(NAME=self.name, TITLE=next_tab.title, IND=next_index))

                        # Enable next tab
                        window[next_tab_key].update(disabled=False, visible=True)
                        window[next_tab_key].metadata['disabled'] = False
                        window[next_tab_key].metadata['visible'] = True

                    # Enable the finalize button when an audit has been run on all tabs.
                    if next_index == final_index:
                        logger.info('AuditRule {NAME}: all audits have been performed - preparing audit summary'
                                    .format(NAME=self.name))
                        window[next_key].update(disabled=False)
                        window[next_key].metadata['disabled'] = False

            return current_rule

        # Run a rule panel event
        param_keys = [i for j in self.parameters for i in j.elements]

        # Cancel button pressed
        if event == cancel_key:
            # Check if reconciliation is currently in progress
            if self.in_progress is True:
                msg = 'Transaction audit is currently in progress. Are you sure you would like to quit without saving?'
                selection = mod_win2.popup_confirm(msg)

                if selection == 'OK':
                    # Reset the rule and update the panel
                    remain_in_panel = True if not values['-AMENU-'] else False
                    if remain_in_panel is True:
                        current_rule = self.reset_rule(window, current=True)
                    else:
                        current_rule = self.reset_rule(window, current=False)
            else:
                current_rule = self.reset_rule(window, current=False)

        # Next button pressed - display summary panel
        elif event == next_key and not window[next_key].metadata['disabled']:
            next_subpanel = self.current_panel + 1

            # Prepare audit records
            if next_subpanel == self.last_panel:
                # Store transaction table summaries for mapping
                transaction_summ = {}
                for tab in self.transactions:
                    tab_name = tab.name
                    summary = tab.table.summarize()
                    for summary_column in summary:
                        summary_value = summary[summary_column]
                        transaction_summ['{TBL}.{COL}'.format(TBL=tab_name, COL=summary_column)] = summary_value

                # Create audit records using data from the transaction audits
                for record_tab in self.records:

                    # Update audit record totals
                    record_tab.map_summary(transaction_summ)

                    # Initialize the new record
                    record_tab.record.initialize(record_tab.record_data, new=False, as_new=True)

                    # Map transactions to transaction records
                    record_tab.map_transactions(self.transactions)

                    # Update the audit record's display
                    record_tab.update_display(window)

                # Disable / enable action buttons
                window[next_key].update(disabled=True)
                window[next_key].metadata['disabled'] = True

                window[back_key].update(disabled=False)
                window[back_key].metadata['disabled'] = False

                window[save_key].update(disabled=False)
                window[save_key].metadata['disabled'] = False

                # Switch to the first audit record tab
                window[summary_tg_key].Widget.select(0)

            # Reset transaction panel table sizes
            for transaction_tab in self.transactions:
                transaction_tab.table.set_table_dimensions(window)

            # Hide the current sub-panel and display the following sub-panel
            window[self.panel_keys[self.current_panel]].update(visible=False)
            window[self.panel_keys[next_subpanel]].update(visible=True)

            # Reset the current panel attribute
            self.current_panel = next_subpanel

        # Back button pressed
        elif event == back_key and not window[back_key].metadata['disabled']:
            current_panel = self.current_panel

            # Delete unsaved keys if returning from summary panel
            if current_panel == self.last_panel:
                for record_tab in self.records:
                    # Reset audit record components
                    record_tab.reset_record_elements(window)

            # Return to previous display
            prev_subpanel = current_panel - 1
            window[self.panel_keys[current_panel]].update(visible=False)
            window[self.panel_keys[prev_subpanel]].update(visible=True)

            window[next_key].update(disabled=False)
            window[next_key].metadata['disabled'] = False

            window[back_key].update(disabled=True)
            window[back_key].metadata['disabled'] = True

            # Switch to first transaction tab
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
        elif event == start_key and not window[start_key].metadata['disabled']:
            # Check for valid parameter values
            params = self.parameters
            inputs = []
            for param in params:
                param.format_value(values)

                if not param.has_value():
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
                window[start_key].metadata['disabled'] = True

                # Verify that the audit has not already been performed with these parameters
                audit_exists = self.load_records()
                if audit_exists is True:
                    msg = 'An audit has already been performed using these parameters. Please edit or delete the ' \
                          'audit records through the records menu'
                    logger.warning('audit initialization failed - an audit has already been performed with the '
                                   'provided parameters')
                    mod_win2.popup_error(msg)
                    current_rule = self.reset_rule(window, current=True)

                    return current_rule

                # Initialize audit
                for transaction_tab in self.transactions:
                    tab_key = transaction_tab.key_lookup('Tab')
                    tab_keys.append(tab_key)

                    # Set tab parameters
                    transaction_tab.parameters = self.parameters

                    # Import tab data from the database
                    try:
                        transaction_tab.load_data()
                    except ImportError as e:
                        msg = 'audit initialization failed - {ERR}'.format(ERR=e)
                        logger.error('AuditRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
                        mod_win2.popup_error(msg)
                        current_rule = self.reset_rule(window, current=True)

                        return current_rule

                logger.info('AuditRule {NAME}: transaction audit in progress with parameters {PARAMS}'
                            .format(NAME=self.name,PARAMS=', '.join(['{}={}'.format(i.name, i.value) for i in params])))
                self.in_progress = True

                # Enable/Disable control buttons and parameter elements
                self.toggle_parameters(window, 'disable')

                for transaction_tab in self.transactions:
                    # Enable table element events
                    transaction_tab.table.enable(window)

                    # Update the tab table display
                    transaction_tab.table.update_display(window)

                    # Update tab ID components
                    transaction_tab.update_id_components()

                    # Enable the tab audit button
                    window[transaction_tab.key_lookup('Audit')].update(disabled=False)

        # Run parameter events
        elif event in param_keys:
            try:
                param = self.fetch_parameter(event, by_key=True)
            except KeyError:
                logger.error('AuditRule {NAME}: unable to find parameter associated with event key {KEY}'
                             .format(NAME=self.name, KEY=event))
            else:
                param.run_event(window, event, values)

        # Save results of the audit
        elif event == save_key:
            # Check if any data elements are in edit mode before saving. Attempt to save if so.
            for audit_record in self.records:
                for record_element in audit_record.record.record_elements():
                    try:
                        edit_mode = record_element.edit_mode
                    except AttributeError:
                        continue
                    else:
                        if edit_mode:  # element is being edited
                            # Attempt to save the data element value
                            success = record_element.run_event(window, record_element.key_lookup('Save'), values)
                            if not success:
                                return current_rule

            # Get output file from user
            report_title = self.update_title()

            title = report_title.replace(' ', '_')
            outfile = sg.popup_get_file('', title='Save As', default_path=title, save_as=True,
                                        default_extension='pdf', no_window=True,
                                        file_types=(('PDF - Portable Document Format', '*.pdf'),))

            if not outfile:
                msg = 'Please select an output file before continuing'
                mod_win2.popup_error(msg)
            else:
                # Save summary to the program database
                try:
                    save_status = self.save_records()
                except Exception as e:
                    msg = 'database save failed - {ERR}'.format(ERR=e)
                    mod_win2.popup_error(msg)

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
                            self.save_report(outfile, title=report_title)
                        except Exception as e:
                            msg = 'Save to file {FILE} failed - {ERR}'.format(FILE=outfile, ERR=e)
                            mod_win2.popup_error(msg)
                            raise

                        # Reset rule elements
                        current_rule = self.reset_rule(window, current=True)

        return current_rule

    def layout(self, size):
        """
        Generate a GUI layout for the audit rule.
        """
        width, height = size

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

        font_h = mod_const.HEADING_FONT

        pad_el = mod_const.ELEM_PAD
        pad_v = mod_const.VERT_PAD
        pad_frame = mod_const.FRAME_PAD

        # Rule parameters
        params = self.parameters

        # Element sizes
        title_w, title_h = (mod_const.TITLE_WIDTH, mod_const.TITLE_HEIGHT)
        pad_h = 22  # horizontal bar with padding
        bttn_h = mod_const.BTTN_HEIGHT
        header_h = 52

        frame_w = width - pad_frame * 2  # width minus padding
        frame_h = height - title_h - bttn_h  # height minus the title bar and buttons height

        tab_w = frame_w  # same as the frame
        tab_h = frame_h - header_h - pad_h  # frame height minus header and padding

        record_h = tab_h - pad_frame * 3  # top and bottom padding
        record_w = tab_w

        # Layout elements

        # Title
        panel_title = 'Transaction Audit: {}'.format(self.menu_title)
        title_key = self.key_lookup('Title')
        title_layout = sg.Col([[sg.Canvas(size=(0, title_h), background_color=header_col),
                                sg.Text(panel_title, pad=(pad_frame, pad_frame), font=font_h,
                                        background_color=header_col)]],
                              key=title_key, size=(title_w, title_h), background_color=header_col,
                              vertical_alignment='c', element_justification='l', justification='l', expand_x=True)

        # Rule parameter elements
        if len(params) > 1:
            param_pad = ((0, pad_h), 0)
        else:
            param_pad = (0, 0)

        param_elements = []
        for param in params:
            element_layout = param.layout(padding=param_pad, auto_size_desc=True)
            param_elements += element_layout

        start_key = self.key_lookup('Start')
        start_layout = [[mod_lo.B2('Start', key=start_key, pad=(0, 0), disabled=False, use_ttk_buttons=True,
                                   button_color=(bttn_text_col, bttn_bg_col), metadata={'disabled': False},
                                   disabled_button_color=(disabled_text_col, disabled_bg_col),
                                   tooltip='Start transaction audit')]]

        header_key = self.key_lookup('Header')
        header = [sg.Canvas(size=(0, header_h), background_color=bg_col),
                  sg.Col([param_elements], pad=(0, pad_v), background_color=bg_col, justification='l',
                         vertical_alignment='c', expand_x=True),
                  sg.Col(start_layout, pad=(0, pad_v), background_color=bg_col, justification='r',
                         element_justification='r', vertical_alignment='c')]
        header_layout = sg.Col([header], key=header_key, background_color=bg_col, expand_x=True, vertical_alignment='c',
                               element_justification='l')

        # Transaction panel layout
        transaction_tabs = []
        for i, tab in enumerate(self.transactions):
            if i == 0:
                visiblity = True
            else:
                visiblity = False

            transaction_tabs.append(tab.layout((tab_w, tab_h), visible=visiblity))

        tg_key = self.key_lookup('TransactionTG')
        tg_layout = [sg.TabGroup([transaction_tabs], key=tg_key, pad=(0, 0), enable_events=True,
                                 tab_background_color=inactive_col, selected_title_color=select_col,
                                 title_color=text_col, selected_background_color=bg_col, background_color=bg_col)]

        tpanel_key = self.key_lookup('TransactionPanel')
        transaction_layout = sg.Col([tg_layout], key=tpanel_key, pad=(0, 0), background_color=bg_col,
                                    vertical_alignment='t', visible=True, expand_y=True, expand_x=True)

        # Summary panel layout
        record_tabs = []
        for tab in self.records:
            tab_key = tab.key_lookup('Tab')
            tab_title = tab.title
            tab_layout = tab.record.layout((record_w, record_h), padding=(pad_frame, pad_frame),
                                           ugroup=user.access_permissions())
            record_tabs.append(sg.Tab(tab_title, tab_layout, key=tab_key, background_color=bg_col,
                                      metadata={'visible': True, 'disabled': False}))

        tg_key = self.key_lookup('SummaryTG')
        tg_layout = sg.TabGroup([record_tabs], key=tg_key, pad=(0, 0), background_color=bg_col,
                                tab_background_color=inactive_col, selected_background_color=bg_col,
                                selected_title_color=select_col, title_color=text_col)

        spanel_key = self.key_lookup('SummaryPanel')
        summary_layout = sg.Col([[tg_layout]], key=spanel_key, background_color=bg_col, vertical_alignment='t',
                                visible=False, expand_y=True, expand_x=True)

        # Panel layout
        panels = [transaction_layout, summary_layout]

        panel_key = self.key_lookup('Panels')
        panel_layout = sg.Pane(panels, key=panel_key, orientation='horizontal', background_color=bg_col,
                               show_handle=False, border_width=0, relief='flat')

        # Standard elements
        next_key = self.key_lookup('Next')
        back_key = self.key_lookup('Back')
        cancel_key = self.key_lookup('Cancel')
        save_key = self.key_lookup('Save')
        buttons_key = self.key_lookup('Buttons')
        bttn_h = mod_const.BTTN_HEIGHT
        bttn_layout = sg.Col([
            [sg.Canvas(size=(0, bttn_h)),
             mod_lo.nav_bttn('', key=cancel_key, image_data=mod_const.CANCEL_ICON, pad=((0, pad_el), 0), disabled=False,
                             tooltip='Return to home screen'),
             mod_lo.nav_bttn('', key=back_key, image_data=mod_const.LEFT_ICON, pad=((0, pad_el), 0), disabled=True,
                             tooltip='Next panel', metadata={'disabled': True}),
             mod_lo.nav_bttn('', key=next_key, image_data=mod_const.RIGHT_ICON, pad=((0, pad_el), 0), disabled=True,
                             tooltip='Previous panel', metadata={'disabled': True}),
             mod_lo.nav_bttn('', key=save_key, image_data=mod_const.SAVE_ICON, pad=(0, 0), disabled=True,
                             tooltip='Save results', metadata={'disabled': True})
             ]], key=buttons_key, vertical_alignment='c', element_justification='c', expand_x=True)

        frame_key = self.key_lookup('Frame')
        frame_layout = sg.Col([[header_layout],
                               [sg.HorizontalSeparator(pad=(0, (0, pad_v)), color=mod_const.HEADER_COL)],
                               [panel_layout]],
                              pad=(pad_frame, 0), key=frame_key, background_color=bg_col, expand_x=True, expand_y=True)

        layout = sg.Col([[title_layout], [frame_layout], [bttn_layout]], key=self.element_key, visible=False,
                        background_color=bg_col, vertical_alignment='t')

        return layout

    def resize_elements(self, window, size):
        """
        Resize Audit Rule GUI elements.
        """
        width, height = size
        pad_frame = mod_const.FRAME_PAD

        pad_h = mod_const.VERT_PAD + 2  # padding plus height of the horizontal bar
        pad_w = pad_frame * 2
        bttn_h = mod_const.BTTN_HEIGHT
        title_h = mod_const.TITLE_HEIGHT
        header_h = 52

        # Resize the panel
        frame_w = width - pad_w  # width minus padding
        frame_h = height - title_h - bttn_h - 4  # height minus the title bar and buttons
        frame_key = self.key_lookup('Frame')
        mod_lo.set_size(window, frame_key, (frame_w, frame_h))

        tab_w = frame_w  # frame width minus the size of the column scrollbar
        tab_h = frame_h - header_h - pad_h  # frame height minus header and padding

        panels_key = self.key_lookup('Panels')
        mod_lo.set_size(window, panels_key, (tab_w, tab_h))

        # Resize panel tab groups

        # Resize transaction tabs
        transactions = self.transactions
        for transaction in transactions:
            transaction.resize_elements(window, size=(tab_w, tab_h))

        # Resize summary audit record tabs
        record_h = tab_h - pad_frame * 3  # top and bottom padding
        record_w = tab_w

        records = self.records
        for audit_record in records:
            audit_record.record.resize(window, (record_w, record_h))

        #window.refresh()
        #print('desired button height: {}'.format(bttn_h))
        #print('actual button height: {}'.format(window[self.key_lookup('Buttons')].get_size()[1]))
        #print('desired title height: {}'.format(title_h))
        #print('actual title height: {}'.format(window[self.key_lookup('Title')].get_size()[1]))
        #print('desired header height: {}'.format(header_h))
        #print('actual header height: {}'.format(window[self.key_lookup('Header')].get_size()[1]))
        #print('desired frame height: {}'.format(frame_h))
        #print('actual frame height: {}'.format(window[frame_key].get_size()[1]))
        #print('desired tab height: {}'.format(tab_h))
        #print('actual tab height: {}'.format(window[panels_key].get_size()[1]))

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

        # Switch to first tab in each panel
        tg_key = self.key_lookup('TransactionTG')
        window[tg_key].Widget.select(0)

        tg_key = self.key_lookup('SummaryTG')
        window[tg_key].Widget.select(0)

        # Reset rule item attributes and parameters.
        self.reset_parameters(window)
        self.toggle_parameters(window, 'enable')

        # Reset summary audit records
        for audit_record in self.records:
            audit_record.reset(window)

        # Reset transactions
        for i, tab in enumerate(self.transactions):
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

    def update_title(self):
        """
        Update summary panel title to include audit parameters.
        """
        params = self.parameters

        # Update summary title with parameter values, if specified in title format
        try:
            title_components = re.findall(r'\{(.*?)\}', self._title)
        except TypeError:
            title_components = []
        else:
            logger.debug('AuditRule {NAME}: report components are {COMPS}'
                         .format(NAME=self.name, COMPS=title_components))

        title_params = {}
        for param in params:
            param_col = param.name

            # Check if parameter composes part of title
            if param_col in title_components:
                display_value = param.format_display()
                logger.debug('AuditRule {NAME}: adding parameter value {VAL} to title'
                             .format(NAME=self.name, VAL=display_value))
                title_params[param_col] = display_value
            else:
                logger.warning('AuditRule {NAME}: parameter {PARAM} not found in title'
                               .format(NAME=self.name, PARAM=param_col))

        try:
            summ_title = self._title.format(**title_params)
        except KeyError as e:
            logger.error('AuditRule {NAME}: formatting summary title failed due to {ERR}'
                         .format(NAME=self.name, ERR=e))
            summ_title = self._title

        logger.info('AuditRule {NAME}: formatted summary title is {TITLE}'
                    .format(NAME=self.name, TITLE=summ_title))

        return summ_title

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
        disabled = False if value == 'enable' else True
        for param in self.parameters:
            param.toggle(window, off=disabled)

    def load_records(self):
        """
        Load existing audit records or create new records.
        """
        params = self.parameters
        audit_records = self.records

        exists = []
        for audit_record in audit_records:
            exists.append(audit_record.load_record(params))

        return any(exists)

    def save_records(self):
        """
        Save results of an audit to the program database defined in the configuration file.

        Returns:
            success (bool): saving records to the database was successful.
        """
        records = self.records

        logger.debug('AuditRule {NAME}: verifying that all required fields have input'.format(NAME=self.name))

        statements = {}
        for audit_record in records:
            try:
                statements = audit_record.save_record(statements=statements)
            except Exception as e:
                msg = 'failed to save {AUDIT} record {ID}'\
                    .format(AUDIT=audit_record.name, ID=audit_record.record.record_id())
                logger.exception('AuditRule {NAME}: {MSG} - {ERR}'.format(NAME=self.name, MSG=msg, ERR=e))

                return False

        logger.info('AuditRule {NAME}: saving audit records and their components'.format(NAME=self.name))
        sstrings = []
        psets = []
        for i, j in statements.items():
            sstrings.append(i)
            psets.append(j)

        success = user.write_db(sstrings, psets)
        #success = True
        #print(statements)

        return success

    def save_report(self, filename, title: str = None):
        """
        Generate the summary report and save the report to the output file.

        Arguments:
            filename (str): save report to file.

            title (str): name of the report [Default: generate from audit parameters].

        Returns:
            success (bool): saving report was successful.
        """
        report_title = title if title else self.update_title()

        logger.info('AuditRule {NAME}: saving summary report {TITLE} to {FILE}'
                    .format(NAME=self.name, TITLE=report_title, FILE=filename))

        audit_reports = []
        for audit_record in self.records:
            tab_report = audit_record.record.generate_report()
            audit_reports.append(tab_report)

        css_url = settings.report_css
        template_vars = {'title': report_title, 'report_tabs': audit_reports}

        env = Environment(loader=FileSystemLoader(os.path.dirname(os.path.abspath(settings.audit_template))))
        template = env.get_template(os.path.basename(os.path.abspath(settings.audit_template)))
        html_out = template.render(template_vars)
        path_wkhtmltopdf = settings.wkhtmltopdf
        config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)
        try:
            pdfkit.from_string(html_out, filename, configuration=config, css=css_url,
                               options={'enable-local-file-access': None})
        except Exception as e:
            logger.error('AuditRule {NAME}: writing to PDF failed - {ERR}'
                         .format(NAME=self.name, ERR=e))
            success = False
        else:
            success = True

        return success


class AuditTransaction:
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
                         ('Tab', 'Audit', 'Panel')]

        self.bindings = [self.key_lookup(i) for i in ('Audit',)]

        try:
            self.title = entry['Title']
        except KeyError:
            self.title = name

        try:
            self.record_type = entry['RecordType']
        except KeyError:
            msg = 'Configuration Error: AuditTransactionTab {NAME}: missing required parameter "RecordType"' \
                .format(NAME=name)
            logger.error(msg)

            raise AttributeError(msg)

        try:
            self.table = mod_elem.RecordTable(name, entry['DisplayTable'])
        except KeyError:
            msg = 'Configuration Error: AuditTransactionTab {NAME}: missing required parameter "DisplayTable"' \
                .format(NAME=name)
            logger.error(msg)

            raise AttributeError(msg)
        except AttributeError as e:
            msg = 'Configuration Error: AuditTransactionTab {NAME}: unable to initialize DisplayTable - {ERR}' \
                .format(NAME=name, ERR=e)
            logger.exception(msg)

            raise AttributeError(msg)
        else:
            self.bindings.extend(self.table.bindings)

        try:
            filter_rules = entry['FilterRules']
        except KeyError:
            filter_rules = {}
        #filter_rules = self.table.filter_rules

        self.filter_rules = {}
        table_columns = self.table.columns
        for filter_key in filter_rules:
            if filter_key in table_columns:
                self.filter_rules[filter_key] = filter_rules[filter_key]
            else:
                logger.warning('DataTable {NAME}: filter rule key {KEY} not found in table columns'
                               .format(NAME=self.name, KEY=filter_key))

#        try:
#            import_rules = entry['ImportRules']
#        except KeyError:
#            msg = 'Configuration Error: AuditTransactionTab {NAME}: missing required field "ImportRules".' \
#                .format(NAME=name)
#            logger.error(msg)
#
#            raise AttributeError(msg)
#        else:
#            self.import_rules = import_rules
#
#        try:
#            self.record_layout = entry['RecordLayout']
#        except KeyError:
#            self.record_layout = None

        try:
            self.id_format = re.findall(r'\{(.*?)\}', entry['IDFormat'])
        except KeyError:
            msg = 'Configuration Error: AuditTransaction {NAME}: missing required field "IDFormat".' \
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
            logger.warning('AuditTransaction {NAME}: component {COMP} not found in list of audit rule elements'
                           .format(NAME=self.name, COMP=component))
            key = None

        return key

    def fetch_parameter(self, element, by_key: bool = False, by_type: bool = False):
        """
        Fetch a GUI parameter element by name or event key.
        """
        parameters = self.parameters

        if by_key is True:
            element_type = element[1:-1].split('_')[-1]
            element_names = [i.key_lookup(element_type) for i in parameters]
        elif by_type is True:
            element_names = [i.dtype for i in parameters]
        else:
            element_names = [i.name for i in parameters]

        if element in element_names:
            index = element_names.index(element)
            parameter = parameters[index]
        else:
            raise KeyError('element {ELEM} not found in list of {NAME} data elements'
                           .format(ELEM=element, NAME=self.name))

        return parameter

    def reset(self, window, first: bool = False):
        """
        Reset the elements and attributes of the audit rule transaction tab.
        """

        # Reset the data table
        self.table.reset(window)

        # Disable table element events
        self.table.disable(window)

        # Disable the audit button
        window[self.key_lookup('Audit')].update(disabled=True)

        # Reset dynamic attributes
        self.parameters = None
        self.id_components = []

        # Reset visible tabs
        visible = True if first is True else False
        logger.debug('AuditTransactionTab {NAME}: re-setting visibility to {STATUS}'
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

        font = mod_const.MAIN_FONT

        # Element sizes
        bffr_h = (18 + 4) + pad_frame * 3 + 30  # height of the tabs, padding, and button
        tbl_width = width - pad_frame * 2
        tbl_height = height - bffr_h

        # Layout
        audit_key = self.key_lookup('Audit')
        main_layout = [[self.table.layout(size=(tbl_width, tbl_height), padding=(0, 0))],
                       [sg.Col([[mod_lo.B1('Run Audit', key=audit_key, pad=(0, (pad_frame, 0 )), disabled=True,
                                           font=font, button_color=(bttn_text_col, bttn_bg_col),
                                           disabled_button_color=(disabled_text_col, disabled_bg_col),
                                           tooltip='Run audit on the transaction records', use_ttk_buttons=True)]],
                               pad=(0, 0), background_color=bg_col, element_justification='c',
                               expand_x=True, expand_y=True, vertical_alignment='c')]]

        panel_key = self.key_lookup('Panel')
        layout = [[sg.Col(main_layout, key=panel_key, pad=((pad_frame, 0), pad_frame), justification='c',
                          vertical_alignment='c', background_color=bg_col, expand_x=True, expand_y=True,
                          scrollable=True, vertical_scroll_only=True)]]

        return sg.Tab(self.title, layout, key=self.key_lookup('Tab'), background_color=bg_col, visible=visible,
                      disabled=False, font=font, metadata={'visible': visible, 'disabled': False})

    def resize_elements(self, window, size):
        """
        Resize the transaction tab.
        """
        width, height = size
        pad_frame = mod_const.FRAME_PAD
        pad_v = pad_h = pad_frame * 2
        scroll_w = mod_const.SCROLL_WIDTH
        tbl_pad = pad_frame - scroll_w

        # Reset tab element size
        tab_key = self.key_lookup('Tab')
        mod_lo.set_size(window, tab_key, (width, height))

        panel_w = width - pad_h
        panel_h = height - pad_v
        panel_key = self.key_lookup('Panel')
        mod_lo.set_size(window, panel_key, (panel_w, panel_h))

        # Reset the tab table element size
        bffr_h = (18 + 8) + pad_frame + 30  # height of the tabs, padding, and button
        tbl_width = panel_w - tbl_pad  # minus padding
        tbl_height = panel_h - bffr_h
        self.table.resize(window, size=(tbl_width, tbl_height))

    def run_event(self, window, event, values):
        """
        Run an audit rule transaction event.
        """
        audit_key = self.key_lookup('Audit')

        success = True

        # Run component table events
        table_keys = self.table.bindings
        if event in table_keys:
            table = self.table

            table.run_event(window, event, values)

        # Run a transaction audit
        elif event == audit_key:
            try:
                self.audit_transactions()
            except Exception as e:
                msg = 'audit failed on transaction {NAME} - {ERR}'.format(NAME=self.title, ERR=e)
                mod_win2.popup_error(msg)
                logger.exception('AuditTransaction {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                success = False
            else:
                delete_rows = self.filter_table()
                if len(delete_rows) > 0:
                    self.table.delete_rows(delete_rows)

                self.table.update_display(window)

        return success

    def filter_table(self):
        """
        Filter the data table by applying the filter rules specified in the configuration.
        """
        # Tab attributes
        filter_rules = self.filter_rules
        df = self.table.data()

        if df.empty or not filter_rules:
            return []

        logger.debug('AuditTransaction {NAME}: filtering display table on configured filter rules'
                     .format(NAME=self.name))

        failed_rows = set()
        for column in filter_rules:
            filter_rule = filter_rules[column]
            logger.debug('AuditTransaction {NAME}: filtering table on column {COL} based on rule "{RULE}"'
                         .format(NAME=self.name, COL=column, RULE=filter_rule))

            try:
                #filter_cond = mod_dm.evaluate_rule(df, filter_rule, as_list=False)
                filter_results = mod_dm.evaluate_condition_set(df, {column: filter_rule})
            except Exception as e:
                logger.warning('AuditTransaction {NAME}: filtering table on column {COL} failed - {ERR}'
                               .format(NAME=self.name, COL=column, ERR=e))
                continue

            try:
                #failed = df[(df.duplicated(subset=[column], keep=False)) & (filter_cond)].index.tolist()
                failed = df[(df.duplicated(subset=[column], keep=False)) & (filter_results)].index.tolist()
            except Exception as e:
                logger.warning('AuditTransaction {NAME}: filtering table on column {COL} failed - {ERR}'
                               .format(NAME=self.name, COL=column, ERR=e))
                continue
            else:
                failed_rows.update(failed)

        return list(failed_rows)

    def load_data(self):
        """
        Load data from the database.
        """
        parameters = self.parameters
        record_type = self.record_type
        record_entry = settings.records.fetch_rule(record_type)

        # Prepare the database query statement
        try:
            df = record_entry.import_records(params=parameters)
        except Exception as e:
            msg = 'failed to import data from the database'
            logger.exception('AuditTransaction {NAME}: {MSG} - {ERR}'.format(NAME=self.name, MSG=msg, ERR=e))

            raise ImportError(msg)

        logger.info('AuditTransaction {NAME}: successfully loaded record data from the database'.format(NAME=self.name))
        self.table.append(df)

    def audit_transactions(self):
        """
        Search for missing transactions using scan.
        """
        strptime = datetime.datetime.strptime

        # Class attributes
        record_type = self.record_type
        record_entry = settings.records.fetch_rule(record_type)
        import_rules = record_entry.import_rules

#        import_rules = self.import_rules
        table = self.table
        collection = table.collection
        pkey = collection.id_column
        id_list = sorted(table.row_ids(), reverse=False)
        missing_df = table.data(deleted_rows=True)
        existing_imports = table.row_ids(indices=missing_df.index.tolist())

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
        logger.info('AuditTransaction {NAME}: searching for missing transactions'.format(NAME=self.name))
        missing_transactions = []
        first_id = None
        first_number_comp = None
        first_date_comp = None
        for index, record_id in enumerate(id_list):
            number_comp = int(self.get_id_component(record_id, 'variable'))
            date_comp = self.get_id_component(record_id, 'date')
            if record_id == self.format_id(number_comp, date=date_comp):  # skip IDs that dont conform to defined format
                first_id = record_id
                first_number_comp = number_comp
                first_date_comp = date_comp
                id_list = id_list[index:]

                break

        if audit_date and first_id:  # data table not empty
            logger.debug('AuditTransaction {NAME}: first transaction ID is {ID}'.format(NAME=self.name, ID=first_id))

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
                logger.warning('AuditTransaction {NAME}: no date found prior to current audit date {DATE}'
                               .format(NAME=self.name, DATE=audit_date_iso))
                prev_date = None
            except ValueError:
                logger.warning('AuditTransaction {NAME}: unknown date format {DATE} provided'
                               .format(NAME=self.name, DATE=unq_dates_iso[current_date_index - 1]))
                prev_date = None

            # Query the last transaction from the previous date
            if prev_date:
                logger.info('AuditTransaction {NAME}: searching for most recent transaction created on last '
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
                        logger.warning('AuditTransaction {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
                        logger.warning('AuditTransaction {NAME}: record with unknown format is {ID}'
                                       .format(NAME=self.name, ID=last_df[last_df[pkey] == prev_id]))
                        continue

                    prev_date_comp = self.get_id_component(prev_id, 'date')

                    if prev_number_comp > first_number_comp:
                        continue

                    # Search only for IDs with correct ID formats (skip potential errors)
                    if prev_id == self.format_id(prev_number_comp, date=prev_date_comp):
                        last_id = prev_id
                        break

                if last_id:
                    logger.debug('AuditTransaction {NAME}: last transaction ID is {ID} from {DATE}'
                                 .format(NAME=self.name, ID=last_id, DATE=prev_date.strftime('%Y-%m-%d')))

                    logger.debug('AuditTransaction {NAME}: searching for skipped transactions between last ID '
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

                    msg = ('found {N} skipped transactions between last ID {PREV_ID} from last transaction date '
                           '{PREV_DATE} and first ID {ID} of current transaction date {DATE}'
                           .format(N=nskipped, PREV_ID=last_id, PREV_DATE=prev_date.strftime('%Y-%m-%d'), ID=first_id,
                                   DATE=audit_date_iso))
                    logger.debug('AuditTransactionTab {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            # Search for skipped transaction numbers
            logger.debug('AuditTransaction {NAME}: searching for skipped transactions within the current '
                         'transaction date {DATE}'.format(NAME=self.name, DATE=audit_date_iso))
            prev_number = first_number_comp - 1
            nskipped = 0
            for record_id in id_list:
                try:
                    record_no = int(self.get_id_component(record_id, 'variable'))
                except ValueError:
                    msg = 'inconsistent format found in record ID {ID}'.format(ID=record_id)
                    mod_win2.popup_notice(msg)
                    logger.warning('AuditTransaction {NAME}: ID with unknown format is {ID}'
                                   .format(NAME=self.name, ID=record_id))

                    continue

                record_date = self.get_id_component(record_id, 'date')

                if record_id != self.format_id(record_no, date=record_date):  # skip IDs that don't conform to format
                    msg = 'record ID {ID} does not conform to ID format specifications'.format(ID=record_id)
                    logger.warning('AuditTransaction {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                    continue

                if (prev_number + 1) != record_no:
                    missing_range = list(range(prev_number + 1, record_no))
                    for missing_number in missing_range:
                        missing_id = self.format_id(missing_number, date=first_date_comp)
                        if (missing_id not in id_list) and (missing_id not in existing_imports):
                            missing_transactions.append(missing_id)
                            nskipped += 1

                prev_number = record_no

            logger.debug('AuditTransaction {NAME}: found {N} skipped transactions from within current '
                         'transaction date {DATE}'.format(NAME=self.name, N=nskipped, DATE=audit_date_iso))

            # Search for missed numbers at end of day
            logger.info('AuditTransaction {NAME}: searching for transactions created at the end of the day'
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
                    logger.warning('AuditTransaction {NAME}: ID with unknown format is {ID}'
                                   .format(NAME=self.name, ID=current_df[current_df[pkey] == current_id]))

                    continue

                if (current_id == self.format_id(current_number_comp, date=first_date_comp)) and \
                        (current_id not in existing_imports):
                    missing_transactions.append(current_id)

        logger.debug('AuditTransaction {NAME}: potentially missing transactions: {MISS}'
                     .format(NAME=self.name, MISS=missing_transactions))

        # Query database for the potentially missing transactions
        if missing_transactions:
            pkey_db = mod_db.get_import_column(import_rules, pkey)

            filter_values = ['?' for _ in missing_transactions]
            filter_str = '{PKEY} IN ({VALUES})'.format(PKEY=pkey_db, VALUES=', '.join(filter_values))

            filters = [(filter_str, tuple(missing_transactions))]

            # Drop missing transactions if they don't meet the import parameter requirements
            missing_df.append(user.read_db(*user.prepare_query_statement(table_statement, columns=import_columns,
                              filter_rules=filters, order=pkey_db)), ignore_index=True)

        # Display import window with potentially missing data
        if not missing_df.empty:
            try:
                import_rows = table.import_rows(import_df=missing_df)
            except Exception as e:
                msg = 'failed to run table import event'
                logger.exception('AuditTransaction {NAME}: {MSG} - {ERR}'.format(NAME=self.name, MSG=msg, ERR=e))
            else:
                if not import_rows.empty:
                    collection.append(import_rows, new=True)

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
                    logger.warning('AuditTransactionTab {NAME}: no date provided for ID number {NUM} ... reverting to '
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
                    logger.warning('AuditTransactionTab {NAME}: ID component {COMP} cannot be found in identifier '
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


class AuditRecord:
    """
    Class to store information about an audit record.
    """
    def __init__(self, name, entry, parent: str = None):

        self.name = name
        self.parent = parent
        self.id = randint(0, 1000000000)
        self.element_key = '{NAME}_{ID}'.format(NAME=name, ID=self.id)
        self.elements = ['-{NAME}_{ID}_{ELEM}-'.format(NAME=self.name, ID=self.id, ELEM=i) for i in
                         ('Tab',)]

        record_entry = settings.records.fetch_rule(name)
        self.record = mod_records.DatabaseRecord(name, record_entry.record_layout, level=0)
        #self.record.metadata = []
        self.elements.extend(self.record.elements)
        self.bindings = self.record.record_events()

        self.record_data = self.record.export_values()

        try:
            self.merge = bool(int(entry['MergeTransactions']))
        except KeyError:
            msg = 'missing required configuration parameter "MergeTransactions"'
            logger.error('AuditRecord {NAME}: {MSG}'.format(NAME=name, MSG=msg))

            raise AttributeError(msg)
        except ValueError:
            msg = 'unsupported value provided to configuration parameter "MergeTransactions". Supported values are 0 ' \
                  '(False) or 1 (True)'
            logger.error('AuditRecord {NAME}: {MSG}'.format(NAME=name, MSG=msg))

            raise AttributeError(msg)

        try:
            self.merge_columns = entry['MergeOn']
        except KeyError:
            self.merge_columns = []

        try:
            self.title = entry['Title']
        except KeyError:
            self.title = name

        try:
            self.summary_mapping = entry['SummaryMapping']
        except KeyError:
            msg = 'missing required configuration parameter "SummaryMapping"'
            logger.error('AuditRecord {NAME}: {MSG}'.format(NAME=name, MSG=msg))

            raise AttributeError(msg)
        try:
            self.record_mapping = entry['RecordMapping']
        except KeyError:
            msg = 'missing required configuration parameter "RecordMapping"'
            logger.error('AuditRecord {NAME}: {MSG}'.format(NAME=name, MSG=msg))

            raise AttributeError(msg)

    def key_lookup(self, component):
        """
        Lookup a component's GUI element key using the component's name.
        """
        element_names = [i[1:-1].split('_')[-1] for i in self.elements]
        if component in element_names:
            key_index = element_names.index(component)
            key = self.elements[key_index]
        else:
            logger.warning('AuditRecord {NAME}: component {COMP} not found in list of components'
                           .format(NAME=self.name, COMP=component))
            key = None

        return key

    def reset(self, window):
        """
        Reset Summary tab record.
        """
        self.record.reset(window)

    def reset_record_elements(self, window):
        """
        Reset summary tab record components.
        """
        for record_element in self.record.modules:
            record_element.reset(window)

    def run_event(self, window, event, values):
        """
        Run an audit summary record event.
        """
        self.record.run_event(window, event, values)

    def load_record(self, params):
        """
        Load previous audit (if exists) and IDs from the program database.

        Arguments:
            params (list): filter record table when importing the records on the data parameter values.

        Returns:
            success (bool): record importing was successful.
        """
        # Prepare the database query statement
        record_entry = settings.records.fetch_rule(self.name)
        import_rules = record_entry.import_rules
        program_records = record_entry.program_record

        filters = mod_db.format_import_filters(import_rules)
        table_statement = mod_db.format_tables(import_rules)
        columns = mod_db.format_import_columns(import_rules)

        # Add parameter values to the filter statement
        param_filters = [i.query_statement(mod_db.get_import_column(import_rules, i.name)) for i in params]
        filters += param_filters

        logger.info('AuditRecord {NAME}: attempting to load an existing audit record'.format(NAME=self.name))

        # Import record from database
        try:
            import_df = user.read_db(*user.prepare_query_statement(table_statement, columns=columns,
                                                                   filter_rules=filters), prog_db=program_records)
        except Exception as e:
            mod_win2.popup_error('Attempt to import data from the database failed. Use the debug window for more '
                                 'information')
            raise IOError('failed to import data for audit {NAME} from the database - {ERR}'
                          .format(NAME=self.name, ERR=e))
        else:
            if not import_df.empty:  # Audit record already exists in database for the chosen parameters
                msg = 'AuditRecord {NAME}: an audit record already exists for the chosen parameters'\
                    .format(NAME=self.name)
                logger.info(msg)
                return True
            else:  # audit has not been performed yet
                logger.info('AuditRecord {NAME}: no existing audit record for the supplied parameters ... '
                            'creating a new record'.format(NAME=self.name))

                param_types = [i.dtype for i in params]
                try:
                    date_index = param_types.index('date')
                except IndexError:
                    raise AttributeError('failed to create record - audit {NAME} is missing the date parameter'
                                         .format(NAME=self.name))

                # Create new record
                record_date = params[date_index].value
                self.record_data['RecordDate'] = record_date
                record_id = record_entry.create_record_ids(record_date, offset=settings.get_date_offset())
                if not record_id:
                    raise IOError('failed to create record - unable to create record ID for the {NAME} audit'
                                  .format(NAME=self.name))
                self.record_data['RecordID'] = record_id

                #record_data = {'RecordID': record_id, 'RecordDate': record_date}
                for param in params:
                    param_name = param.name
                    if param_name in self.record_data:
                        self.record_data[param_name] = param.value

                #self.record.initialize(record_data, new=False)

                return False

    def save_record(self, statements: dict = None):
        """
        Save the audit record to the program database defined in the configuration file.

        Arguments:
            statements (dict): optional dictionary of transaction statements to add to.
        """
        record = self.record

        # Prepare to export associated deposit records for the relevant account records
        if not statements:
            statements = {}

        # Export audit record
        statements = record.prepare_save_statements(statements=statements, save_all=True)

        return statements

    def map_summary(self, summary_map):
        """
        Populate the audit record element values with transaction summaries.

        Arguments:
            summary_map (dict): transaction table summary variables (<table>.<variable>) with their final values.
        """
        logger.debug('AuditRecord {NAME}: mapping transaction summaries to audit record elements'
                     .format(NAME=self.name))

        # Map audit totals columns to transaction table summaries
        mapping_columns = self.summary_mapping
        for column in mapping_columns:
            mapper = mapping_columns[column]
            try:
                summary_total = mod_dm.evaluate_operation(summary_map, mapper)
            except Exception as e:
                logger.warning('AuditRecord {NAME}: failed to evaluate summary totals - {ERR}'
                               .format(NAME=self.name, ERR=e))
                summary_total = 0

            logger.debug('AuditRecord {NAME}: adding {SUMM} to column {COL}'
                         .format(NAME=self.name, SUMM=summary_total, COL=column))

            self.record_data[column] = summary_total

    def map_summary_old(self, summary_map):
        """
        Populate the audit record element values with transaction summaries.

        Arguments:
            summary_map (dict): transaction table summary variables (<table>.<variable>) with their final values.
        """
        operators = set('+-*/%')

        name = self.name

        logger.debug('AuditRecord {NAME}: mapping transaction summaries to audit record elements'
                     .format(NAME=self.name))

        # Map audit totals columns to transaction table summaries
        mapping_columns = self.summary_mapping
        for column in mapping_columns:
            mapper = mapping_columns[column]
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
                        logger.error('AuditRecord {NAME}: column {COL} not found in transaction table summaries'
                                     .format(NAME=name, COL=component))
                        rule_values.append(0)

                else:
                    rule_values.append(component)

            try:
                summary_total = eval(' '.join([str(i) for i in rule_values]))
            except Exception as e:
                logger.warning('AuditRecord {NAME}: failed to evaluate summary totals - {ERR}'
                               .format(NAME=self.name, ERR=e))
                summary_total = 0

            logger.debug('AuditRecord {NAME}: adding {SUMM} to column {COL}'
                         .format(NAME=name, SUMM=summary_total, COL=column))

            self.record_data[column] = summary_total

    def map_transactions(self, rule_tabs):
        """
        Map transaction records from the audit to the audit accounting records.
        """
        pd.set_option('display.max_columns', None)
        tab_names = [i.name for i in rule_tabs]

        logger.debug('AuditRecord {NAME}: creating component records from the transaction records'
                     .format(NAME=self.name))

        record = self.record
        component_table = record.fetch_element('account')
        header = component_table.columns

        # Map transaction data to transaction records
        comp_df = pd.DataFrame(columns=header)
        record_mapping = self.record_mapping
        for payment_type in record_mapping:
            table_rules = record_mapping[payment_type]
            for table in table_rules:
                table_rule = table_rules[table]
                try:
                    subset_rule = table_rule['Subset']
                except KeyError:
                    logger.warning('AuditRecord {NAME}: record mapping transaction type {TYPE}, table {TBL} is missing '
                                   'required parameter "Subset"'.format(NAME=self.name, TYPE=payment_type, TBL=table))
                    continue

                try:
                    column_map = table_rule['ColumnMapping']
                except KeyError:
                    logger.warning('AuditRecord {NAME}: record mapping payment type {TYPE}, table {TBL} is missing '
                                   'required parameter "ColumnMapping"'
                                   .format(NAME=self.name, TYPE=payment_type, TBL=table))
                    continue

                if table not in tab_names:
                    logger.warning('AuditRecord {NAME}: unknown transaction table {TBL} provided to record_mapping '
                                   '{TYPE}'.format(NAME=self.name, TBL=table, TYPE=payment_type))
                    continue
                else:
                    tab = rule_tabs[tab_names.index(table)]

                # Subset transaction records using defined subset rules
                logger.debug('AuditRecord {NAME}: sub-setting reference table {REF} based on defined payment "{TYPE}" '
                             'rule {RULE}'.format(NAME=self.name, REF=table, TYPE=payment_type, RULE=subset_rule))
                subset_df = tab.table.subset(subset_rule)
                if subset_df.empty:
                    logger.debug('AuditRecord {NAME}: no data from reference table {REF} to add to the audit record'
                                 .format(NAME=self.name, REF=table))
                    continue

                # Add transaction records to the set of transaction records that will get mapped to the audit component
                # records
                for index, row in subset_df.iterrows():
                    record_data = pd.Series(index=header)
                    record_data['PaymentType'] = payment_type

                    # Map row values to the account record elements
                    for column in column_map:
                        if column not in header:
                            logger.warning('AuditRecord {NAME}: mapped column {COL} not found in record elements'
                                           .format(COL=column, NAME=self.name))
                            continue

                        reference_col = column_map[column]
                        try:
                            ref_val = row[reference_col]
                        except KeyError:
                            msg = 'failed to add values for mapped column {COL} - reference column {REFCOL} not ' \
                                  'found in the transaction table'.format(COL=column, REFCOL=reference_col)
                            logger.warning('AuditRecord {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
                        else:
                            record_data[column] = ref_val
                        #try:
                        #    ref_val = mod_dm.evaluate_rule(row, reference, as_list=True)[0]
                        #except Exception as e:
                        #    msg = 'failed to add mapped column {COL} - {ERR}'.format(COL=column, ERR=e)
                        #    logger.warning('AuditRecord {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
                        #else:
                        #    record_data[column] = ref_val

                    # Add record to the components table
                    comp_df = comp_df.append(record_data, ignore_index=True)

        # Remove NA columns
        comp_df = comp_df[comp_df.columns[~comp_df.isna().all()]]

        if self.merge is True:  # transaction records should be merged into one (typical for cash transactions)
            merge_on = [i for i in comp_df.columns.tolist() if i not in self.merge_columns]
            logger.debug('AuditRecord {NAME}: merging rows on columns {COLS}'.format(NAME=self.name, COLS=merge_on))
            comp_df = comp_df.groupby(merge_on).sum().reset_index()

        if not comp_df.empty:
            final_df = record.create_components(component_table, record_data=comp_df)
            print('creating component records from transactions:')
            print(final_df)
            component_table.append(final_df)

    def update_display(self, window):
        """
        Update the audit record summary tab's record display.
        """
        self.record.update_display(window)


def replace_nth(s, sub, new, ns: list = None):
    """
    Replace the nth occurrence of an substring in a string

    Arguments:
        s (str): string to modify.

        sub (str): substring within the string to replace.

        new (str): new string that will replace the substring.

        ns (list): optional list of indices of the substring instance to replace [Default: replace all].
    """
    if isinstance(ns, str):
        ns = [ns]

    where = [m.start() for m in re.finditer(sub, s)]
    new_s = s
    for count, start_index in enumerate(where):
        if ns and count not in ns:
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
