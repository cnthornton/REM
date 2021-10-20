"""
REM bank reconciliation configuration classes and objects.
"""

import datetime
from random import randint

import numpy as np
import pandas as pd
import PySimpleGUI as sg

import REM.constants as mod_const
import REM.elements as mod_elem
import REM.layouts as mod_lo
import REM.parameters as mod_param
import REM.secondary as mod_win2
from REM.client import logger, settings, user


class BankRule:
    """
    Class to store and manage a configured bank reconciliation rule.

    Attributes:

        name (str): bank reconciliation rule name.

        id (int): rule element number.

        element_key (str): panel element key.

        elements (list): list of rule GUI element keys.

        menu_title (str): rule menu title.

        menu_flags (dict): submenu flags that change the initial behavior of the rule.

        permissions (str): permissions required to view the accounting method. Default: user.

        accts (list): list of account entry objects composing the rule.
    """

    def __init__(self, name, entry):
        """
        Arguments:

            name (str): bank reconciliation rule name.

            entry (dict): dictionary of optional and required bank rule arguments.
        """

        self.name = name
        self.id = randint(0, 1000000000)
        self.element_key = '-{NAME}_{ID}-'.format(NAME=name, ID=self.id)
        self.elements = ['-{NAME}_{ID}_{ELEM}-'.format(NAME=self.name, ID=self.id, ELEM=i) for i in
                         ('Panel', 'Account', 'Association', 'Reconcile', 'Parameters', 'Cancel', 'Save',
                          'Panel1', 'Panel2', 'Warning1', 'Warning2', 'Frame', 'Buttons', 'Title')]

        self.bindings = [self.key_lookup(i) for i in
                         ('Cancel', 'Save', 'Account', 'Association', 'Parameters', 'Reconcile')]

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
        except KeyError:  # default permission for a bank rule is 'admin'
            self.permissions = 'admin'

        self.parameters = []
        try:
            params = entry['RuleParameters']
        except KeyError:
            msg = 'missing required parameter "RuleParameters"'
            logger.error('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            raise AttributeError(msg)

        for param_name in params:
            param_entry = params[param_name]

            param_layout = param_entry['ElementType']
            if param_layout in ('dropdown', 'combo'):
                param_class = mod_param.DataParameterCombo
            elif param_layout in ('input', 'date'):
                param_class = mod_param.DataParameterInput
            elif param_layout in ('range', 'date_range'):
                param_class = mod_param.DataParameterRange
            elif param_layout == 'checkbox':
                param_class = mod_param.DataParameterCheckbox
            else:
                msg = 'unknown type {TYPE} provided to RuleParameter {PARAM}' \
                    .format(TYPE=param_layout, PARAM=param_name)
                logger.error('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                raise AttributeError(msg)

            param = param_class(param_name, param_entry)
            self.parameters.append(param)
            self.bindings.extend(param.bindings)

        try:
            accts = entry['Entries']
        except KeyError:
            msg = 'BankRule {RULE}: missing required configuration parameter "Entries"'.format(RULE=name)
            logger.error(msg)

            raise AttributeError(msg)

        self.accts = []
        self.panel_keys = {}
        for acct_id in accts:  # account entries
            acct_entry = accts[acct_id]

            acct = BankAccount(acct_id, acct_entry, parent=self.name)
            self.accts.append(acct)

            self.panel_keys[acct_id] = acct.key_lookup('Panel')
            self.bindings.extend(acct.events())

        # Dynamic Attributes
        self.in_progress = False
        self.current_account = None
        self.current_panel = None
        self.current_association = None
        self.current_assoc_panel = None
        self.panels = []

    def key_lookup(self, component):
        """
        Lookup a component's GUI element key using the component's name.
        """
        element_names = [i[1:-1].split('_')[-1] for i in self.elements]
        if component in element_names:
            key_index = element_names.index(component)
            key = self.elements[key_index]
        else:
            logger.warning('BankRule {NAME}: component {COMP} not found in list of rule components'
                           .format(NAME=self.name, COMP=component))
            key = None

        return key

    def bind_keys(self, window):
        """
        Bind panel-element hotkeys.
        """
        # Bind events to element keys
        logger.debug('BankRule {NAME}: binding record element hotkeys'.format(NAME=self.name))

        # Bind account table hotkeys
        for acct in self.accts:
            acct.table.bind_keys(window)
            acct.assoc_table.bind_keys(window)

    def events(self):
        """
        Return a list of all events allowed under the rule.
        """
        return self.bindings

    def fetch_account(self, account_id, by_title: bool = False, by_key: bool = False):
        """
        Fetch a GUI parameter element by name or event key.

        Arguments:
            account_id (str): identifier used to find the correct account entry.

            by_title (bool): identifier is the title of an account [Default: False].

            by_key (bool): identifier is an element of the account entry [Default: False].
        """
        account = None
        for acct in self.accts:
            if by_key:
                elements = acct.elements
            elif by_title:
                elements = [acct.title]
            else:
                elements = [acct.name]

            if account_id in elements:
                account = acct
                break

        if account is None:
            raise KeyError('account ID {ACCT} not found in list of {NAME} account entries'
                           .format(ACCT=account_id, NAME=self.name))

        return account

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
            param.toggle_elements(window, value)

    def run_event(self, window, event, values):
        """
        Run a bank reconciliation event.
        """
        pd.set_option('display.max_columns', None)

        # Get elements of current account
        current_rule = self.name

        current_acct = self.current_account
        current_assoc = self.current_association

        entry_key = self.key_lookup('Account')
        assoc_key = self.key_lookup('Association')
        param_key = self.key_lookup('Parameters')
        reconcile_key = self.key_lookup('Reconcile')
        warn1_key = self.key_lookup('Warning1')
        warn2_key = self.key_lookup('Warning2')
        cancel_key = self.key_lookup('Cancel')
        save_key = self.key_lookup('Save')

        if current_acct:
            acct = self.fetch_account(current_acct)
            acct_keys = acct.bindings
            link_key = acct.key_lookup('Link')
            link_hkey = '{}+LINK+'.format(acct.get_table().key_lookup('Element'))
        else:
            acct_keys = []
            link_key = None
            link_hkey = None

        if current_assoc:
            assoc_acct = self.fetch_account(current_assoc)
            assoc_keys = assoc_acct.bindings
        else:
            assoc_keys = []

        can_save = not window[save_key].metadata['disabled']

        # Run an account entry event
        if event in (link_key, link_hkey):
            try:
                self.link_records(current_acct, current_assoc)
            except Exception as e:
                msg = 'failed to link records - {ERR}'.format(ERR=e)
                logger.exception('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
                mod_win2.popup_error(msg)
            else:
                self.update_display(window)

        elif event in acct_keys:
            acct = self.fetch_account(self.current_account)

            results = acct.run_event(window, event, values)

            # Update reference dataframes when an account entry event is a reference event. A reference event is any
            # event that may modify one side of a reference, which requires an update to the other side of the
            # reference.
            ref_indices = results.get('ReferenceIndex')
            if ref_indices:
                logger.debug('BankRule {NAME}: references at indices {INDS} were modified from account table {ACCT}'
                             .format(NAME=self.name, INDS=ref_indices, ACCT=acct.name))
                ref_df = acct.ref_df.copy()
                # Update account reference dataframes for currently active panels
                for panel in self.panels:
                    ref_acct = self.fetch_account(panel, by_key=True)

                    logger.debug('BankRule {NAME}: updating transaction account {ACCT} references matching those '
                                 'that were modified'.format(NAME=self.name, ACCT=ref_acct.name))
                    ref_acct.ref_df = ref_acct.update_references(ref_df.loc[ref_indices])

                self.update_display(window)

            # Update warning element with the reference notes of the selected record, if any.
            record_indices = results.get('RecordIndex')
            if record_indices:
                logger.debug('BankRule {NAME}: record indices {INDS} were selected from account table {ACCT}'
                             .format(NAME=self.name, INDS=record_indices, ACCT=acct.name))

                if len(record_indices) > 1:
                    record_warning = None
                else:  # single primary account record selected
                    # Set the reference warning, if any
                    record_warning = acct.fetch_reference_parameter('ReferenceNotes', record_indices).squeeze()

                    # Select the reference in the associated table, if any
                    if current_assoc:
                        assoc_acct = self.fetch_account(current_assoc)
                        assoc_table = assoc_acct.get_table()

                        reference_id = acct.fetch_reference_parameter('ReferenceID', record_indices).squeeze()
                        assoc_display = assoc_table.data(display_rows=True)
                        ref_ind = assoc_display[assoc_display['RecordID'] == reference_id].index
                        if not ref_ind.empty:
                            select_ind = assoc_table.get_index(ref_ind.tolist(), real=False)
                            assoc_table.select(window, select_ind)

                window[warn1_key].update(value=settings.format_display(record_warning, 'varchar'))

            return current_rule

        # Run an association account event
        if event in assoc_keys:
            assoc_acct = self.fetch_account(current_assoc)
            print('running event {} from association account {}'.format(event, current_assoc))
            results = assoc_acct.run_event(window, event, values)

            # Store indices of the selected row(s)
            record_indices = results.get('RecordIndex')
            if record_indices:
                logger.debug('BankRule {NAME}: record indices {INDS} were selected from account table {ACCT}'
                             .format(NAME=self.name, INDS=record_indices, ACCT=assoc_acct.name))

                if len(record_indices) > 1:
                    record_warning = None
                else:
                    record_warning = assoc_acct.fetch_reference_parameter('ReferenceNotes', record_indices).squeeze()
                window[warn2_key].update(value=settings.format_display(record_warning, 'varchar'))

            return current_rule

        # Run a rule panel event

        # The cancel button or cancel hotkey was pressed. If a reconciliation is in progress, reset the rule but stay
        # in the rule panel. If reconciliation is not in progress, return to home screen.
        if event == cancel_key:
            # Check if reconciliation is currently in progress
            if self.in_progress is True:
                msg = 'Reconciliation is currently in progress. Are you sure you would like to quit without saving?'
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

        # The save button or enter hotkey was pressed. Save the account records and associated account records and
        # generate a summary report.
        elif event == save_key and can_save:
            # Get output file from user
            acct = self.fetch_account(current_acct)
            default_title = acct.title + '.xlsx'
            outfile = sg.popup_get_file('', title='Save As', default_path=default_title, save_as=True,
                                        default_extension='xlsx', no_window=True,
                                        file_types=(('XLS - Microsoft Excel', '*.xlsx'),))

            if not outfile:
                msg = 'Please select an output file before continuing'
                mod_win2.popup_error(msg)
            else:
                # Save records to the program database
                try:
                    save_status = self.save()
                except Exception as e:
                    msg = 'database save failed - {ERR}'.format(ERR=e)
                    mod_win2.popup_error(msg)
                    logger.error('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
                    raise
                else:
                    if save_status is False:
                        msg = 'Database save failed'
                        mod_win2.popup_error(msg)
                    else:
                        msg = 'account records were successfully saved to the database'
                        mod_win2.popup_notice(msg)
                        logger.info('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
                        # Save summary to excel or csv file
                        try:
                            self.save_report(outfile)
                        except Exception as e:
                            msg = 'Save to file {FILE} failed - {ERR}'.format(FILE=outfile, ERR=e)
                            mod_win2.popup_error(msg)
                            raise

                        # Reset rule elements
                        current_rule = self.reset_rule(window, current=True)

        # An account was selected from the account entry dropdown. Selecting an account will display the associated
        # sub-panel.
        elif event == entry_key:
            acct_title = values[event]
            if not acct_title:
                self.current_account = None
                self.current_panel = None

                # Disable the parameter selection button
                window[param_key].update(disabled=True)

                return current_rule

            # Hide the current panel
            if self.current_panel:
                prev_acct = self.fetch_account(self.current_panel, by_key=True)
                window[self.current_panel].update(visible=False)
                prev_acct.reset(window)

            # Set the current account attributes to the selected account
            current_acct = self.fetch_account(acct_title, by_title=True)
            self.current_account = current_acct.name
            self.current_panel = current_acct.key_lookup('Panel')
            current_acct.primary = True

            # Display the selected account table
            window[self.current_panel].update(visible=True)

            # Enable the parameter selection button
            window[param_key].update(disabled=False)

        # An associated account was selected from the associated accounts dropdown. Selecting an associated account will
        # display the relevant sub-panel.
        elif event == assoc_key:
            acct_title = values[event]
            if not acct_title:
                self.current_account = None
                self.current_panel = None

                return current_rule

            # Hide the current association panel
            if self.current_assoc_panel:
                window[self.current_assoc_panel].update(visible=False)

                # Clear current table selections
                current_assoc_acct = self.fetch_account(current_assoc)
                current_assoc_acct.get_table().deselect(window)
                window[warn2_key].update(value='')

            # Set the current association account attributes to the selected association account
            assoc_acct = self.fetch_account(acct_title, by_title=True)
            self.current_association = assoc_acct.name
            self.current_assoc_panel = assoc_acct.key_lookup('AssocPanel')

            # Display the selected association account table
            window[self.current_assoc_panel].update(visible=True)

        # Set parameters button was pressed. Will open parameter settings window for user to input parameter values,
        # then load the relevant account record data
        elif event == param_key:
            # Get the parameter settings
            params = mod_win2.parameter_window(self.fetch_account(current_acct))

            # Load the account records
            if params:  # parameters were saved (selection not cancelled)
                # Load the main transaction account data using the defined parameters
                main_acct = self.current_account
                acct_params = params[main_acct]
                if not acct_params:
                    msg = 'no parameters supplied for main account {ACCT}'.format(ACCT=main_acct)
                    mod_win2.popup_error('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                    return self.reset_rule(window, current=True)

                acct = self.fetch_account(main_acct)

                try:
                    acct.load_data(acct_params)
                except Exception as e:
                    msg = 'failed to load data for current account {ACCT} - {ERR}'.format(ACCT=main_acct, ERR=e)
                    logger.error('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                    return self.reset_rule(window, current=True)

                # Get a list of records referenced by the main account records
                ref_df = acct.ref_df.copy()
                ref_df = ref_df[~ref_df['ReferenceID'].isna()]

                # Enable table action buttons for the main account
                acct.table.enable(window)

                self.panels.append(self.panel_keys[main_acct])

                # Load the association account data using the defined parameters
                assoc_accounts = []
                for acct_name in params:
                    if acct_name == main_acct:  # data already loaded
                        continue

                    acct_params = params[acct_name]
                    if not acct_params:
                        msg = 'no parameters supplied for association account {ACCT}'.format(ACCT=main_acct)
                        logger.warning('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                        continue

                    logger.debug('BankRule {NAME}: loading database records for association account {ACCT}'
                                 .format(NAME=self.name, ACCT=acct_name))
                    assoc_acct = self.fetch_account(acct_name)
                    assoc_type = assoc_acct.record_type
                    assoc_accounts.append(assoc_acct.title)

                    refs = ref_df.copy()
                    reference_records = refs.loc[refs['ReferenceType'] == assoc_type, 'ReferenceID'].tolist()

                    try:
                        assoc_acct.load_data(acct_params, records=reference_records)
                    except Exception as e:
                        mod_win2.popup_error('{MSG} -  see log for details'.format(MSG=e))

                        return self.reset_rule(window, current=True)

                    assoc_acct.primary = False
                    self.panels.append(self.panel_keys[acct_name])

                # Update the display
                window[assoc_key].update(values=assoc_accounts, size=(mod_const.PARAM_SIZE_CHAR[0], len(assoc_accounts)))

                self.update_display(window)

                # Disable the account entry selection dropdown
                window[entry_key].update(disabled=True)
                window[assoc_key].update(disabled=False)
                window[param_key].update(disabled=True)

                # Enable elements
                window[save_key].update(disabled=False)
                window[save_key].metadata['disabled'] = False
                if len(self.panels) > 1:
                    window[reconcile_key].update(disabled=False)

                self.toggle_parameters(window, 'enable')

                # Mark that a reconciliation is currently in progress
                self.in_progress = True

        # Reconcile button was pressed. Will run the reconcile method to find associations with the current primary
        # account and any associated accounts with data.
        elif event == reconcile_key:
            expand_param = self.fetch_parameter('ExpandSearch')
            failed_param = self.fetch_parameter('SearchFailed')
            expand_search = values[expand_param.key_lookup('Element')]
            search_for_failed = values[failed_param.key_lookup('Element')]

            try:
                self.reconcile_statement(expand_search=expand_search, search_failed=search_for_failed)
            except Exception as e:
                msg = 'failed to reconcile statement - {ERR}'.format(ERR=e)
                logger.exception('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
                mod_win2.popup_error(msg)
            else:
                # Update the sub-panel displays
                self.update_display(window)

        return current_rule

    def reset_rule(self, window, current: bool = False):
        """
        Reset rule to default.
        """
        panel_key = self.element_key
        entry_key = self.key_lookup('Account')
        assoc_key = self.key_lookup('Association')
        param_key = self.key_lookup('Parameters')
        warn1_key = self.key_lookup('Warning1')
        warn2_key = self.key_lookup('Warning2')

        # Disable current panel
        if self.current_panel:
            window[self.current_panel].update(visible=False)

        window[panel_key].update(visible=False)
        window['-HOME-'].update(visible=True)

        # Disable the reconciliation button
        reconcile_key = self.key_lookup('Reconcile')
        save_key = self.key_lookup('Save')
        window[reconcile_key].update(disabled=True)
        window[save_key].update(disabled=True)
        window[save_key].metadata['disabled'] = True

        # Enable the account entry selection dropdown
        window[entry_key].update(disabled=False)
        window[assoc_key].update(disabled=True)
        window[assoc_key].update(value='')

        self.reset_parameters(window)
        self.toggle_parameters(window, 'disable')

        # Clear the warning element
        window[warn1_key].update(value='')
        window[warn2_key].update(value='')

        # Reset all account entries
        for acct in self.accts:
            acct.reset(window)

        self.in_progress = False
        self.panels = []

        if self.current_assoc_panel:
            window[self.current_assoc_panel].update(visible=False)
        self.current_association = None
        self.current_assoc_panel = None

        if current:
            window['-HOME-'].update(visible=False)
            if self.current_panel:
                window[self.current_panel].update(visible=True)
                current_acct = self.fetch_account(self.current_account)
                current_acct.primary = True

                # Enable the parameter selection button
                window[param_key].update(disabled=False)

            window[panel_key].update(visible=True)

            return self.name
        else:
            # Reset the current account display
            self.current_panel = None
            self.current_account = None

            # Reset the account entry dropdown
            window[entry_key].update(value='')

            # Disable the parameter selection button
            window[param_key].update(disabled=True)

            return None

    def layout(self, size):
        """
        Generate a GUI layout for the bank reconciliation rule.
        """
        width, height = size

        params = self.parameters

        # Element parameters
        bttn_text_col = mod_const.WHITE_TEXT_COL
        bttn_bg_col = mod_const.BUTTON_COL
        disabled_text_col = mod_const.DISABLED_TEXT_COL
        disabled_bg_col = mod_const.DISABLED_BUTTON_COL
        bg_col = mod_const.ACTION_COL
        header_col = mod_const.HEADER_COL
        text_col = mod_const.TEXT_COL

        font = mod_const.MAIN_FONT
        param_font = mod_const.XX_FONT
        font_h = mod_const.HEADING_FONT

        pad_el = mod_const.ELEM_PAD
        pad_v = mod_const.VERT_PAD
        pad_frame = mod_const.FRAME_PAD

        param_size = mod_const.PARAM_SIZE_CHAR

        # Element sizes
        title_w, title_h = (mod_const.TITLE_WIDTH, mod_const.TITLE_HEIGHT)
        pad_h = 22  # horizontal bar with padding
        bttn_h = mod_const.BTTN_HEIGHT
        header_h = 52
        warn_h = 50

        frame_w = width - pad_frame * 2
        frame_h = height - title_h - warn_h - bttn_h  # height minus title bar, warning multiline, and buttons height

        panel_w = frame_w
        panel_h = frame_h - header_h - pad_h  # minus panel title, padding, and button row

        # Layout elements

        # Title
        panel_title = 'Bank Reconciliation: {}'.format(self.menu_title)
        title_key = self.key_lookup('Title')
        title_layout = sg.Col([[sg.Canvas(size=(0, title_h), background_color=header_col),
                                sg.Text(panel_title, pad=(pad_frame, pad_frame), font=font_h,
                                        background_color=header_col)]],
                              key=title_key, size=(title_w, title_h), background_color=header_col,
                              vertical_alignment='c', element_justification='l', justification='l', expand_x=True)

        # Column 1

        # Column 1 header
        entry_key = self.key_lookup('Account')
        param_key = self.key_lookup('Parameters')

        entries = [i.title for i in self.accts]
        header1 = sg.Col([[sg.Canvas(size=(0, header_h), background_color=bg_col),
                           sg.Combo(entries, default_value='', key=entry_key, size=param_size, pad=((0, pad_el * 2), 0),
                                    font=param_font, text_color=text_col, background_color=bg_col, disabled=False,
                                    enable_events=True, tooltip='Select reconciliation account'),
                           sg.Button('', key=param_key, image_data=mod_const.PARAM_ICON, image_size=(28, 28),
                                     button_color=(text_col, bg_col), disabled=True, tooltip='Set parameters')]],
                         expand_x=True, justification='l', element_justification='l', vertical_alignment='b',
                         background_color=bg_col)

        # Column 1 Panels
        panels = []
        for acct in self.accts:
            layout = acct.layout(size=(panel_w, panel_h))
            panels.append(layout)

        pg1 = [[sg.Pane(panels, orientation='horizontal', background_color=bg_col, show_handle=False, border_width=0,
                        relief='flat')]]

        panel_key = self.key_lookup('Panel1')
        panel1 = sg.Frame('', pg1, key=panel_key, background_color=bg_col, visible=True, vertical_alignment='c',
                          element_justification='c')

        warn1_key = self.key_lookup('Warning1')
        warn_w = 10  # width of the display panel minus padding on both sides
        warn_h = 2
        warn_layout = sg.Col([[sg.Canvas(size=(0, 70), background_color=bg_col),
                               sg.Multiline('', key=warn1_key, size=(warn_w, warn_h), font=font, disabled=True,
                                            background_color=bg_col, text_color=disabled_text_col, border_width=1)]],
                             background_color=bg_col, expand_x=True, vertical_alignment='c', element_justification='l')

        col1_layout = sg.Col([[header1], [panel1], [warn_layout]], pad=((0, pad_v), 0), background_color=bg_col)

        # Column 2

        # Column 2 header
        reconcile_key = self.key_lookup('Reconcile')

        # Rule parameter elements
        if len(params) > 1:
            param_pad = ((0, pad_el * 2), 0)
        else:
            param_pad = (0, 0)

        assoc_key = self.key_lookup('Association')
        param_elements = [sg.Canvas(size=(0, header_h), background_color=bg_col),
                          sg.Combo(entries, default_value='', key=assoc_key, size=param_size, pad=((0, pad_el * 2), 0),
                                   font=param_font, text_color=text_col, background_color=bg_col, disabled=False,
                                   enable_events=True, tooltip='Select association account'),
                          sg.Button('Reconcile', key=reconcile_key, pad=((0, pad_el), 0), disabled=True,
                                    button_color=(bttn_text_col, bttn_bg_col),
                                    disabled_button_color=(disabled_text_col, disabled_bg_col),
                                    tooltip='Run reconciliation')]
        for param in params:
            element_layout = param.layout(padding=param_pad, auto_size_desc=True)
            param_elements.extend(element_layout)

        header2 = sg.Col([param_elements], expand_x=True,
                         justification='l', element_justification='l', vertical_alignment='b', background_color=bg_col)

        # Column 2 Panels
        panels = []
        for acct in self.accts:
            layout = acct.layout(size=(panel_w, panel_h), primary=False)
            panels.append(layout)

        pg2 = [[sg.Pane(panels, orientation='horizontal', background_color=bg_col, show_handle=False, border_width=0,
                        relief='flat')]]

        panel_key = self.key_lookup('Panel2')
        panel2 = sg.Frame('', pg2, key=panel_key, background_color=bg_col, visible=True,
                          vertical_alignment='c', element_justification='c')

        warn2_key = self.key_lookup('Warning2')
        warn_w = 10  # width of the display panel minus padding on both sides
        warn_h = 2
        warn_layout = sg.Col([[sg.Canvas(size=(0, 70), background_color=bg_col),
                               sg.Multiline('', key=warn2_key, size=(warn_w, warn_h), font=font, disabled=True,
                                            background_color=bg_col, text_color=disabled_text_col, border_width=1)]],
                             background_color=bg_col, expand_x=True, vertical_alignment='c', element_justification='l')

        col2_layout = sg.Col([[header2], [panel2], [warn_layout]], pad=((pad_v, 0), 0), background_color=bg_col)

        # Control elements
        cancel_key = self.key_lookup('Cancel')
        save_key = self.key_lookup('Save')
        buttons_key = self.key_lookup('Buttons')
        bttn_h = mod_const.BTTN_HEIGHT
        bttn_layout = sg.Col([
            [sg.Canvas(size=(0, bttn_h)),
             mod_lo.nav_bttn('', key=cancel_key, image_data=mod_const.CANCEL_ICON, pad=((0, pad_el), 0), disabled=False,
                             tooltip='Return to home screen'),
             mod_lo.nav_bttn('', key=save_key, image_data=mod_const.SAVE_ICON, pad=(0, 0), disabled=True,
                             tooltip='Save results', metadata={'disabled': True})
             ]], key=buttons_key, vertical_alignment='c', element_justification='c', expand_x=True)

        frame_key = self.key_lookup('Frame')
        frame_layout = sg.Col([[col1_layout, col2_layout]],
                              pad=(pad_frame, 0), key=frame_key, background_color=bg_col, expand_x=True, expand_y=True)
        #frame_layout = sg.Col([[col1_layout, col2_layout], [warn_layout]],
        #                      pad=(pad_frame, 0), key=frame_key, background_color=bg_col, expand_x=True, expand_y=True)

        layout = sg.Col([[title_layout], [frame_layout], [bttn_layout]], key=self.element_key,
                        visible=False, background_color=bg_col, vertical_alignment='t')

        return layout

    def resize_elements(self, window, size):
        """
        Resize Bank Reconciliation Rule GUI elements.

        Arguments:
            window (Window): GUI window.

            size (tuple): new panel size (width, height).
        """
        width, height = size
        pad_frame = mod_const.FRAME_PAD
        pad_v = mod_const.VERT_PAD
        #scroll_w = mod_const.SCROLL_WIDTH

        title_w, title_h = (mod_const.TITLE_WIDTH, mod_const.TITLE_HEIGHT)
        pad_h = pad_v + 2  # horizontal bar height with padding
        pad_w = pad_frame * 2
        bttn_h = mod_const.BTTN_HEIGHT
        header_h = 52
        warn_h = 70

        frame_w = width - pad_w
        frame_h = height - title_h - bttn_h - 4  # height minus title bar and buttons height
        frame_key = self.key_lookup('Frame')
        mod_lo.set_size(window, frame_key, (frame_w, frame_h))

        panel_w = int(frame_w / 2) - pad_v
        panel_h = frame_h - header_h - warn_h - pad_h  # frame minus panel header row, warning, and vertical padding
        mod_lo.set_size(window, self.key_lookup('Panel1'), (panel_w, panel_h))
        mod_lo.set_size(window, self.key_lookup('Panel2'), (panel_w, panel_h))

        window[self.key_lookup('Warning1')].expand(expand_x=True)
        window[self.key_lookup('Warning2')].expand(expand_x=True)

        # Resize account panels
        accts = self.accts
        for acct in accts:
            acct.resize(window, size=(panel_w, panel_h))

        #window.refresh()
        #print('desired button height: {}'.format(bttn_h))
        #print('actual button height: {}'.format(window[self.key_lookup('Buttons')].get_size()[1]))
        #print('desired title height: {}'.format(title_h))
        #print('actual title height: {}'.format(window[self.key_lookup('Title')].get_size()[1]))
        #print('desired header height: {}'.format(header_h))
        #print('actual combo height: {}'.format(window[self.key_lookup('Account')].get_size()[1]))
        #print('actual frame height: {}'.format(window[frame_key].get_size()[1]))
        #print('desired panel height: {}'.format(panel_h))
        #print('actual panel height: {}'.format(window[self.key_lookup('Panel1')].get_size()[1]))

    def update_display(self, window):
        """
        Update the audit record summary tab's record display.
        """
        # Update the relevant account panels
        for acct_panel in self.panels:
            acct = self.fetch_account(acct_panel, by_key=True)
            acct.update_display(window)

    def link_records(self, acct_name, assoc_name: str = None):
        """
        Link two or more selected records.
        """
        # Get selected row(s) of the transaction accounts
        acct = self.fetch_account(acct_name)
        acct_table = acct.get_table()
        rows = acct_table.selected(real=True)

        if assoc_name:
            assoc_acct = self.fetch_account(assoc_name)
            assoc_table = assoc_acct.get_table()
            acct_rows = rows[0]
            assoc_rows = assoc_table.selected(real=True)[0]
        else:
            assoc_acct = acct
            assoc_name = acct_name
            assoc_table = acct_table
            acct_rows = rows[0]
            assoc_rows = rows[1]

        record_id = acct_table.row_ids(indices=acct_rows)[0]
        reference_id = assoc_table.row_ids(indices=assoc_rows)[0]

        # Verify that the selected records do not already have references
        if acct.has_reference(record_id) or assoc_acct.has_reference(reference_id):
            msg = 'one or more of the selected records already have references'
            raise AssertionError(msg)

        # Link records
        msg = 'manually link record {ID} from {ACCT} to record {REFID} from {ASSOC}?'\
            .format(ID=record_id, REFID=reference_id, ACCT=acct_name, ASSOC=assoc_name)
        confirm = mod_win2.popup_confirm(msg)
        if confirm:
            # Allow user to set a note
            user_note = mod_win2.add_note_window()

            # Manually set a mutual references for the selected records
            acct.add_reference(record_id, reference_id, assoc_acct.record_type, approved=True, warning=user_note)
            assoc_acct.add_reference(reference_id, record_id, acct.record_type, approved=True, warning=user_note)

    def link_records_new(self, acct_name, assoc_name: str = None):
        """
        Link two or more selected records.
        """
        # Get selected row(s) of the transaction accounts
        acct = self.fetch_account(acct_name)
        acct_table = acct.get_table()
        rows = acct_table.selected()

        if assoc_name:
            assoc_acct = self.fetch_account(assoc_name)
            assoc_table = assoc_acct.get_table()
            acct_rows = rows
            assoc_rows = assoc_table.selected()
        else:
            assoc_acct = acct
            assoc_table = acct_table
            acct_rows = [rows[0]]
            assoc_rows = rows[1:]

        n_select_acct = len(acct_rows)
        n_select_assoc = len(assoc_rows)

        if n_select_acct == 0:
            msg = 'at least one record must be selected from account {}'.format(acct_name)
            raise AssertionError(msg)

        success = True
        if (n_select_assoc >= 1 and n_select_acct == 1) or (n_select_acct >= 1 and n_select_assoc == 1):
            record_ids = acct_table.row_ids(indices=acct_rows, deleted=True)
            reference_ids = assoc_table.row_ids(indices=assoc_rows, deleted=True)

        else:
            msg = ''.format(ACCT=acct_name, ASSOC=assoc_name)
            raise AssertionError(msg)

        if acct.has_reference(record_ids) or assoc_acct.has_reference(reference_ids):
            msg = 'one or more of the selected records already have references'
            raise AssertionError(msg)

        # Allow user to set a note
        user_note = mod_win2.add_note_window()

        # Manually set a mutual references for the selected records
        for record_id in record_ids:
            for reference_id in reference_ids:
                acct.add_reference(record_id, reference_id, assoc_acct.record_type, approved=True, warning=user_note)
                assoc_acct.add_reference(reference_id, record_id, acct.record_type, approved=True, warning=user_note)

        return success

    def reconcile_statement(self, expand_search: bool = False, search_failed: bool = False):
        """
        Run the primary Bank Reconciliation rule algorithm for the record tab.

        Arguments:
            expand_search (bool): expand the search by ignoring association parameters designated as expanded
                [Default: False].

            search_failed (bool): search for failed transactions, such as mistaken payments and bounced cheques
                [Default: False].

        Returns:
            success (bool): bank reconciliation was successful.
        """
        pd.set_option('display.max_columns', None)

        # Fetch primary account and prepare data
        acct = self.fetch_account(self.current_account)
        logger.info('BankRule {NAME}: reconciling account {ACCT}'.format(NAME=self.name, ACCT=acct.name))
        logger.debug('BankRule {NAME}: expanded search is set to {VAL}'
                     .format(NAME=self.name, VAL=('on' if expand_search else 'off')))

        table = acct.get_table()
        id_column = table.id_column

        # Drop reference columns from the dataframe and then re-merge the reference dataframe and the records dataframe
        ref_df = acct.ref_df.copy()
        ref_df = ref_df[~ref_df['IsDeleted']]
        df = pd.merge(table.data().drop(columns=list(acct.ref_map.values())), ref_df, how='left', on='RecordID')
        header = df.columns.tolist()

        if df.empty:
            return True

        # Filter out records already associated with transaction account records
        logger.debug('BankRule {NAME}: dropping {ACCT} records that are already associated with a transaction '
                     'account record'.format(NAME=self.name, ACCT=acct.name))
        df.drop(df[~df['ReferenceID'].isna()].index, axis=0, inplace=True)

        # Filter out void transactions
        if search_failed:
            logger.debug('BankRule {NAME}: searching for void transactions for account {ACCT}'
                         .format(NAME=self.name, ACCT=acct.name))
            df = acct.search_void(df)
        else:
            logger.debug('BankRule {NAME}: skipping void transactions from account {ACCT}'
                         .format(NAME=self.name, ACCT=acct.name))
            df = acct.filter_void(df)

        # Initialize the merged associated account dataframe
        logger.debug('BankRule {NAME}: initializing the merged accounts table'.format(NAME=self.name, ACCT=acct.name))
        required_fields = ['_Account_', '_RecordID_', '_RecordType_']
        merged_df = pd.DataFrame(columns=required_fields)

        # Fetch associated account data
        transactions = acct.transactions
        assoc_ref_maps = {}
        for assoc_acct_name in transactions:
            assoc_acct = self.fetch_account(assoc_acct_name)
            logger.debug('BankRule {NAME}: adding data from the association account {ACCT} to the merged table'
                         .format(NAME=self.name, ACCT=assoc_acct.name))

            assoc_table = assoc_acct.get_table()
            assoc_df = assoc_table.data()
            if assoc_df.empty:  # no records loaded to match to, so skip
                continue

            # Merge the associated records and references tables
            assoc_ref_df = assoc_acct.ref_df.copy()
            assoc_ref_df = assoc_ref_df[~assoc_ref_df['IsDeleted']]
            assoc_df = pd.merge(assoc_df.drop(columns=list(assoc_acct.ref_map.values())), assoc_ref_df, how='left',
                                on='RecordID')
            assoc_header = assoc_df.columns.tolist()

            # Filter association account records that are already associated with a record
            drop_conds = ~assoc_df['ReferenceID'].isna()
            drop_labels = assoc_df[drop_conds].index
            assoc_df = assoc_df.drop(drop_labels, axis=0)

            # Filter out void transactions
            if search_failed:
                logger.debug('BankRule {NAME}: searching for void transactions for account {ACCT}'
                             .format(NAME=self.name, ACCT=acct.name))
                assoc_df = assoc_acct.search_void(assoc_df)
            else:
                logger.debug('BankRule {NAME}: skipping void transactions from association account {ACCT}'
                             .format(NAME=self.name, ACCT=assoc_acct_name))
                assoc_df = assoc_acct.filter_void(assoc_df)

            # Create the account-association account column mapping from the association rules
            assoc_rules = transactions[assoc_acct_name]['AssociationParameters']
            colmap = {}
            rule_map = {}
            for acct_colname in assoc_rules:
                if acct_colname not in header:  # attempting to use a column that was not defined in the table config
                    msg = 'AssociationRule column {COL} is missing from the account data'.format(COL=acct_colname)
                    logger.warning('BankRule: {NAME}: {MSG}'.format(NAME=acct.name, MSG=msg))

                    continue

                rule_entry = assoc_rules[acct_colname]
                assoc_colname = rule_entry['Column']
                if assoc_colname not in assoc_header:
                    msg = 'AssociationRule reference column {COL} is missing from transaction account {ACCT} data' \
                        .format(COL=assoc_colname, ACCT=assoc_acct_name)
                    logger.warning('BankRule: {NAME}: {MSG}'.format(NAME=acct.name, MSG=msg))

                    continue

                colmap[assoc_colname] = acct_colname
                rule_map[acct_colname] = rule_entry

            # Store column mappers for fast recall during matching
            assoc_ref_maps[assoc_acct_name] = rule_map

            # Remove all but the relevant columns from the association account table
            colmap[assoc_acct.table.id_column] = "_RecordID_"
            assoc_df = assoc_df[list(colmap)]

            # Change column names of the association account table using the column map
            assoc_df.rename(columns=colmap, inplace=True)

            # Add association account name and record type to the association account table
            assoc_df['_Account_'] = assoc_acct_name
            assoc_df['_RecordType_'] = assoc_acct.record_type

            # Concatenate association tables
            merged_df = merged_df.append(assoc_df, ignore_index=True)

        # Iterate over record rows, attempting to find matches in associated transaction records
        logger.debug('BankRule {NAME}: attempting to find associations for account {ACCT} records'
                     .format(NAME=self.name, ACCT=acct.name))
        nfound = 0
        matched_indices = []
        for index, row in df.iterrows():
            record_id = getattr(row, id_column)

            # Attempt to find a match for the record to each of the associated transaction accounts
            matches = pd.DataFrame(columns=merged_df.columns)
            for assoc_acct_name in assoc_ref_maps:
                # Subset merged df to include only the association records with the given account name
                assoc_df = merged_df[merged_df['_Account_'] == assoc_acct_name]

                assoc_rules = assoc_ref_maps[assoc_acct_name]
                cols = list(assoc_rules)

                # Find exact matches between account record and the associated account records using only the
                # relevant columns
                row_vals = [getattr(row, i) for i in cols]
                acct_matches = assoc_df[assoc_df[cols].eq(row_vals).all(axis=1)]
                matches = matches.append(acct_matches)

            # Check matches and find correct association
            nmatch = matches.shape[0]
            if nmatch == 1:  # found one exact match
                nfound += 1
                matched_indices.append(index)

                results = matches.iloc[0]
                ref_id = results['_RecordID_']
                ref_type = results['_RecordType_']
                assoc_acct_name = results['_Account_']

                logger.debug('BankRule {NAME}: associating {ACCT} record {REFID} to account record {ID}'
                             .format(NAME=self.name, ACCT=assoc_acct_name, REFID=ref_id, ID=record_id))

                # Remove the found match from the dataframe of unmatched associated account records
                merged_df.drop(matches.index.tolist()[0], inplace=True)

                # Insert the reference into the account records reference dataframe
                acct.add_reference(record_id, ref_id, ref_type, approved=True)

                # Insert the reference into the associated account's reference dataframe
                assoc_acct = self.fetch_account(assoc_acct_name)
                assoc_acct.add_reference(ref_id, record_id, acct.record_type, approved=True)

            elif nmatch > 1:  # too many matches
                nfound += 1
                matched_indices.append(index)

                warning = 'Found more than one match for account {ACCT} record "{RECORD}"' \
                    .format(ACCT=self.current_account, RECORD=record_id)
                logger.debug('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=warning))

                # Match the first of the exact matches
                results = matches.iloc[0]
                ref_id = results['_RecordID_']
                ref_type = results['_RecordType_']
                assoc_acct_name = results['_Account_']

                # Remove match from list of unmatched association records
                merged_df.drop(matches.index.tolist()[0], inplace=True)

                # Insert the reference into the account records reference dataframe
                acct.add_reference(record_id, ref_id, ref_type, approved=True, warning=warning)

                # Insert the reference into the associated account's reference dataframe
                assoc_acct = self.fetch_account(assoc_acct_name)
                assoc_acct.add_reference(ref_id, record_id, acct.record_type, approved=True, warning=warning)

        if expand_search:
            df.drop(matched_indices, inplace=True)
            for index, row in df.iterrows():
                record_id = getattr(row, id_column)

                match = self.find_expanded_match(row, merged_df, assoc_ref_maps, expand_level=0)
                if match.empty:
                    continue

                assoc_acct_name = match['_Account_']
                ref_id = match['_RecordID_']
                ref_type = match['_RecordType_']
                warning = match['_Warning_']

                logger.debug('BankRule {NAME}: associating {ACCT} record {REF_ID} to account record {ID} from an '
                             'expanded search'.format(NAME=self.name, ACCT=assoc_acct_name, REF_ID=ref_id,
                                                      ID=record_id))

                # Remove the found match from the dataframe of unmatched associated account records
                merged_df.drop(match.name, inplace=True)

                # Insert the reference into the account records reference dataframe
                acct.add_reference(record_id, ref_id, ref_type, approved=False, warning=warning)

                # Insert the reference into the associated account's reference dataframe
                assoc_acct = self.fetch_account(assoc_acct_name)
                assoc_acct.add_reference(ref_id, record_id, acct.record_type, approved=False, warning=warning)

        logger.info('BankRule {NAME}: found {NMATCH} associations out of {NTOTAL} unreferenced account {ACCT} records'
                    .format(NAME=self.name, NMATCH=nfound, NTOTAL=df.shape[0], ACCT=acct.name))

        return True

    def find_expanded_match(self, row, ref_df, ref_map, expand_level: int = 0, closest_match: list = None):
        """
        Attempt to find matching records using iterative expansion of reference columns.
        """
        results = pd.Series()
        ref_df['_Warning_'] = None

        matches = pd.DataFrame(columns=ref_df.columns)
        expanded_cols = []
        for assoc_acct_name in ref_map:
            # Subset merged df to include only the association records with the given account name
            assoc_df = ref_df[ref_df['_Account_'] == assoc_acct_name]

            assoc_rules = ref_map[assoc_acct_name]
            cols = []
            for col in assoc_rules:
                rule_entry = assoc_rules[col]

                # Select the columns that will be used to compare records. All expanded search columns with level
                # greater than current level will be left flexible
                param_level = rule_entry.get('Level', 0)
                if param_level > expand_level:
                    if col not in expanded_cols:
                        expanded_cols.append(col)

                    continue
                else:
                    cols.append(col)

            # Find exact matches between account record and the associated account records using relevant cols
            row_vals = [getattr(row, i) for i in cols]
            acct_matches = assoc_df[assoc_df[cols].eq(row_vals).all(axis=1)]
            matches = matches.append(acct_matches)

        nmatch = matches.shape[0]
        if nmatch == 0:  # if level > 0, return to the previous expand level and find the closest match
            if expand_level > 0:
                prev_level = expand_level - 1
                expanded_cols = []
                for assoc_acct_name in ref_map:
                    assoc_rules = ref_map[assoc_acct_name]
                    for col in assoc_rules:
                        rule_entry = assoc_rules[col]

                        param_level = rule_entry.get('Level', 0)
                        if param_level == expand_level:
                            if col not in expanded_cols:
                                expanded_cols.append(col)

                msg = 'no matches found for account {ACCT}, row {ROW} at expanded search level {L} - returning to ' \
                      'previous search level matches to find for the closest match on columns {COLS}' \
                    .format(ACCT=self.current_account, ROW=row.name, L=expand_level, COLS=expanded_cols)
                logger.info('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
                results = self.find_expanded_match(row, ref_df, ref_map, expand_level=prev_level,
                                                   closest_match=expanded_cols)
            else:
                msg = 'no matches found for account {ACCT}, row {ROW} from an expanded search'\
                    .format(ACCT=self.current_account, ROW=row.name)
                logger.warning('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

        elif nmatch == 1:  # potential match, add with a warning
            results = matches.iloc[0].copy()

            # Determine appropriate warning for the expanded search
            acct_name = results['_Account_']
            assoc_rules = ref_map[acct_name]

            warning = ["Potential false positive:"]
            for column in expanded_cols:
                if getattr(row, column) != results[column]:
                    alt_warn = 'values for expanded column {COL} do not match'.format(COL=column)
                    col_warning = assoc_rules[column].get('Description', alt_warn)
                    warning.append('- {}'.format(col_warning))

            warning = '\n'.join(warning)
            results['_Warning_'] = warning

        elif nmatch > 1:  # need to increase specificity to get the best match by adding higher level expand columns
            msg = 'found more than one expanded match for account {ACCT}, row {ROW} at search level {L} - ' \
                  'searching for the best match'.format(ACCT=self.current_account, ROW=row.name, L=expand_level)
            logger.warning('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            # Find the closest match by iterative expanded column inclusion
            if not closest_match:
                results = self.find_expanded_match(row, matches, ref_map, expand_level=expand_level+1)
            else:
                results = nearest_match(row, matches, closest_match)
                if results.empty:
                    msg = 'multiple matches found for account {ACCT}, row {ROW} but enough specificity in the data ' \
                          'to narrow it down to one match'.format(ACCT=self.current_account, ROW=row.name)
                    logger.warning('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
                else:
                    warning = 'association is the result of searching for the closest match on {}'\
                        .format(','.join(closest_match))
                    results['_Warning_'] = warning

        return results

    def save(self):
        """
        Save record modifications and new record associations to the database.
        """
        statements = {}

        # Prepare to save the account references and records
        for panel_key in self.panels:
            acct = self.fetch_account(panel_key, by_key=True)

            record_type = acct.record_type
            record_entry = settings.records.fetch_rule(record_type)

            # Save any changes to the records to the records database table
            logger.debug('BankRule {NAME}: preparing account {ACCT} record statements'
                         .format(NAME=self.name, ACCT=acct.name))
            record_data = acct.get_table().data(edited_rows=True)
            try:
                statements = record_entry.save_database_records(record_data, statements=statements)
            except Exception as e:
                msg = 'failed to prepare the export statement for the account {ACCT} records - {ERR}' \
                    .format(ACCT=acct.name, ERR=e)
                logger.exception('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                return False

        # Save record references to the references table
        acct = self.fetch_account(self.current_account)

        record_type = acct.record_type
        record_entry = settings.records.fetch_rule(record_type)

        association_name = acct.association_rule
        association_rule = record_entry.association_rules[association_name]

        save_df = acct.ref_df.copy()
        try:
            existing_df = acct.load_references(save_df['RecordID'].tolist())
        except Exception as e:
            mod_win2.popup_error('{MSG} -  see log for details'.format(MSG=e))

            return False

        # Drop reference entries that were not changed
        save_df.set_index('RecordID', inplace=True)
        existing_df.set_index('RecordID', inplace=True)
        save_df = save_df.loc[save_df.compare(existing_df).index].reset_index()

        # Get changed reference entries where the reference was deleted
        deleted_ids = save_df.loc[save_df['ReferenceID'].isna(), 'RecordID'].tolist()
        print('will update deleted references: {}'.format(deleted_ids))
        deleted_df = existing_df[(existing_df.index.isin(deleted_ids)) & (~existing_df['ReferenceID'].isna())].reset_index()
        print('deleted entries are:')
        print(deleted_df)

        # Save references for the account if component records are the primary records in the reference table
        is_primary = association_rule['Primary']
        if is_primary:
            print('reference entries from the transaction account will be saved:')
            print(save_df)
            logger.debug('BankRule {NAME}: preparing account {ACCT} reference statements'
                         .format(NAME=self.name, ACCT=acct.name))
            try:
                statements = record_entry.save_database_references(save_df, acct.association_rule,
                                                                   statements=statements)
            except Exception as e:
                msg = 'failed to prepare the export statement for the account {ACCT} references - {ERR}' \
                    .format(ACCT=acct.name, ERR=e)
                logger.exception('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                return False

        # Iterate over unique reference types to determine if any referenced records of the given type should have
        # saved entries due to their status as the primary record type in the reference table
        ref_types = save_df['ReferenceType'].append(deleted_df['ReferenceType']).dropna().unique().tolist()
        print('iterating over reference types: {}'.format(ref_types))
        for ref_type in ref_types:
            ref_entry = settings.records.fetch_rule(ref_type)
            try:
                association_rule = ref_entry.association_rules[association_name]
            except KeyError:
                continue

            is_primary = association_rule['Primary']
            if is_primary:
                # Subset modified reference entries by the primary reference type and save changes
                sub_df = save_df[save_df['ReferenceType'] == ref_type].copy()
                sub_df.rename(columns={'ReferenceID': 'RecordID', 'RecordID': 'ReferenceID',
                                       'RecordType': 'ReferenceType', 'ReferenceType': 'RecordType'}, inplace=True)

                print('associated reference entries will also be saved:')
                print(sub_df)
                try:
                    statements = ref_entry.save_database_references(sub_df, acct.association_rule,
                                                                    statements=statements)
                except Exception as e:
                    msg = 'failed to prepare the export statement for the account {ACCT} references - {ERR}' \
                        .format(ACCT=acct.name, ERR=e)
                    logger.exception('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                    return False

                # Find reference entries where the original reference was of the given reference type but was deleted
                # during the reconciliation
                sub_df = deleted_df[deleted_df['ReferenceType'] == ref_type].copy()
                if sub_df.empty:
                    continue

                sub_df.rename(columns={'ReferenceID': 'RecordID', 'RecordID': 'ReferenceID',
                                       'RecordType': 'ReferenceType', 'ReferenceType': 'RecordType'}, inplace=True)
                ref_columns = {'ReferenceID': None, 'ReferenceDate': None, 'ReferenceType': None,
                               'ReferenceNotes': None, 'IsApproved': False}
                sub_df = sub_df.assign(**ref_columns)
                try:
                    statements = ref_entry.save_database_references(sub_df, acct.association_rule,
                                                                    statements=statements)
                except Exception as e:
                    msg = 'failed to prepare the export statement for the account {ACCT} references - {ERR}' \
                        .format(ACCT=acct.name, ERR=e)
                    logger.exception('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                    return False

        logger.info('BankRule {NAME}: saving the results of account {ACCT} reconciliation'
                    .format(NAME=self.name, ACCT=self.current_account))

        sstrings = []
        psets = []
        for i, j in statements.items():
            sstrings.append(i)
            psets.append(j)

        success = user.write_db(sstrings, psets)
        print(statements)
        #success = True

        return success

    def save_references_old(self):
        """
        Save record associations to the reference database.
        """
        statements = {}

        # Prepare to save the account references
        for panel in self.panels:
            acct = self.fetch_account(panel, by_key=True)

            record_type = acct.record_type
            record_entry = settings.records.fetch_rule(record_type)

            # Save any changes to the records to the records table
            logger.debug('BankRule {NAME}: preparing account {ACCT} record statements'
                         .format(NAME=self.name, ACCT=acct.name))
            record_data = acct.table.data(edited_rows=True)
            try:
                statements = record_entry.save_database_records(record_data, statements=statements)
            except Exception as e:
                msg = 'failed to prepare the export statement for the account {ACCT} records - {ERR}' \
                    .format(ACCT=acct.name, ERR=e)
                logger.exception('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                return False

            # Save record references to the references table
            association_name = acct.association_rule
            association_rule = record_entry.association_rules[association_name]

            is_primary = association_rule['Primary']
            if not is_primary:  # only save references if the record is the primary record in the reference table
                logger.debug('BankRule {NAME}: account {ACCT} records are not primary records in the reference table '
                             '... skipping'.format(NAME=self.name, ACCT=acct.name))
                continue

            logger.debug('BankRule {NAME}: preparing account {ACCT} reference statements'
                         .format(NAME=self.name, ACCT=acct.name))
            try:
                statements = record_entry.save_database_references(acct.ref_df, acct.association_rule,
                                                                   statements=statements)
            except Exception as e:
                msg = 'failed to prepare the export statement for the account {ACCT} references - {ERR}' \
                    .format(ACCT=acct.name, ERR=e)
                logger.exception('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                return False

        logger.info('BankRule {NAME}: saving the results of account {ACCT} reconciliation'
                    .format(NAME=self.name, ACCT=self.current_account))

        sstrings = []
        psets = []
        for i, j in statements.items():
            sstrings.append(i)
            psets.append(j)

        #success = user.write_db(sstrings, psets)
        print(statements)
        success = True

        return success

    def save_report(self, filename):
        """
        Generate a summary report of the reconciliation to a PDF.

        Arguments:
            filename (str): name of the file to save the report to.
        """
        status = []
        with pd.ExcelWriter(filename) as writer:
            for acct_panel in self.panels:
                acct = self.fetch_account(acct_panel, by_key=True)

                sheet_name = acct.title
                table = acct.table

                # Write table to the output file
                export_df = table.export_table(display=False)
                try:
                    export_df.to_excel(writer, sheet_name=sheet_name, engine='openpyxl', header=True, index=False)
                except Exception as e:
                    msg = 'failed to save table {SHEET} to file to {FILE} - {ERR}' \
                        .format(SHEET=sheet_name, FILE=filename, ERR=e)
                    logger.error(msg)
                    mod_win2.popup_error(msg)

                    status.append(False)
                else:
                    status.append(True)

        return all(status)


class BankAccount:
    """
    Bank transaction account entry.

        name (str): rule name.

        id (int): rule element number.

        element_key (str): rule element key.

        elements (list): list of rule GUI element keys.

        title (str): account entry title.

        permissions (str): user access permissions.

        record_type (str): account entry database record type.

        association_rule (str): name of the association rule referenced when attempting to find associations between
            account entries.

        import_parameters (list): list of entry data parameters used in the import window.

        table (RecordTable): table for storing account data.

        ref_df (DataFrame): table for storing record references.

        _col_map (dict): required account parameters with corresponding record names.

        ref_map (dict): reference columns to add to the records table along with their table aliases.

        transactions (dict): money in and money out definitions.

        void_transactions (dict): failed transaction definitions.
    """

    def __init__(self, name, entry, parent=None):
        """
        Arguments:

            name (str): configuration entry name for the bank record tab.

            entry (dict): dictionary of optional and required entry arguments.

            parent (str): name of the parent element.
        """
        self.name = name
        self.parent = parent
        self.id = randint(0, 1000000000)
        self.elements = ['-{NAME}_{ID}_{ELEM}-'.format(NAME=self.name, ID=self.id, ELEM=i) for i in
                         ('Panel', 'AssocPanel', 'Approve', 'Reset', 'Link')]

        self.bindings = [self.key_lookup(i) for i in ('Approve', 'Reset', 'Link')]

        try:
            self.title = entry['Title']
        except KeyError:
            self.title = name

        try:
            self.record_type = entry['RecordType']
        except KeyError:
            msg = 'BankAccount {NAME}: missing required configuration parameter "RecordType".'.format(NAME=name)
            logger.error(msg)

            raise AttributeError(msg)
        else:
            record_entry = settings.records.fetch_rule(self.record_type)

        try:
            self.association_rule = entry['AssociationRule']
        except KeyError:
            msg = 'ReferenceBox {NAME}: missing required parameter "AssociationRule"'.format(NAME=self.name)
            logger.error(msg)

            raise AttributeError(msg)

        try:
            table_entry = entry['DisplayTable']
        except KeyError:
            table_entry = record_entry.import_table

        action_bttns = {'Approve': {'Key': self.key_lookup('Approve'),
                                    'Icon': mod_const.TBL_APPROVE_ICON,
                                    'Description': 'Approve record (CTRL+A)',
                                    'Shortcut': 'Control-A'},
                        'Link': {'Key': self.key_lookup('Link'),
                                 'Icon': mod_const.TBL_LINK_ICON,
                                 'Description': 'Link records (CTRL+L)',
                                 'Shortcut': 'Control-L'},
                        'Reset': {'Key': self.key_lookup('Reset'),
                                  'Icon': mod_const.TBL_RESET_ICON,
                                  'Description': 'Reset record status (CTRL+R)',
                                  'Shortcut': 'Control-R'}}

        table_entry['CustomActions'] = action_bttns

        self.table = mod_elem.RecordTable(name, table_entry)
        self.bindings.extend(self.table.bindings)

        elem_key = self.table.key_lookup('Element')
        approve_hkey = '{}+APPROVE+'.format(elem_key)
        reset_hkey = '{}+RESET+'.format(elem_key)
        link_hkey = '{}+LINK+'.format(elem_key)
        self.bindings.extend([approve_hkey, reset_hkey, link_hkey])

        modifiers = table_entry['Modifiers']
        modifiers['open'] = 1
        modifiers['edit'] = 1
        modifiers['import'] = 0
        modifiers['delete'] = 0
        modifiers['fill'] = 0
        table_entry['Modifiers'] = modifiers
        table_entry['CustomActions'] = {}
        self.assoc_table = mod_elem.RecordTable(name, table_entry)
        self.bindings.extend(self.assoc_table.bindings)

        try:
            self.parameters = entry['ImportParameters']
        except KeyError:
            msg = 'no import parameters specified'
            logger.warning('BankAccount {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            self.parameters = {}

        try:
            ref_map = entry['ReferenceMap']
        except KeyError:
            ref_map = {}
        ref_cols = ['ReferenceID', 'ReferenceDate', 'ReferenceType', 'ReferenceNotes', 'IsApproved', 'IsHardLink',
                    'IsChild', 'IsDeleted']
        self.ref_map = {}
        for column in ref_map:
            if column not in ref_cols:
                msg = 'reference map column {COL} is not a valid reference column name'.format(COL=column)
                logger.warning('BankAccount {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                continue

            self.ref_map[column] = ref_map[column]

        try:
            self._col_map = entry['ColumnMap']
        except KeyError:
            self._col_map = {'TransactionCode': 'TransactionCode', 'TransactionType': 'TransactionType',
                             'Notes': 'Notes', 'Withdrawal': 'Withdrawal', 'Deposit': 'Deposit'
                             }

        try:
            transactions = entry['Transactions']
        except KeyError:
            self.transactions = {}
        else:
            self.transactions = {}
            for transaction_acct in transactions:
                cnfg_entry = transactions[transaction_acct]
                trans_entry = {}

                if 'ImportParameters' not in cnfg_entry:
                    trans_entry['ImportParameters'] = {}
                else:
                    trans_entry['ImportParameters'] = cnfg_entry['ImportParameters']

                if 'Title' not in cnfg_entry:
                    trans_entry['Title'] = transaction_acct
                else:
                    trans_entry['Title'] = cnfg_entry['Title']

                if 'AssociationParameters' not in cnfg_entry:
                    msg = 'BankAccount {NAME}: Transaction account {ACCT} is missing required parameter ' \
                          '"AssociationParameters"'.format(NAME=name, ACCT=transaction_acct)
                    logger.error(msg)

                    continue

                assoc_params = cnfg_entry['AssociationParameters']
                params = {}
                for assoc_column in list(assoc_params):
                    if assoc_column not in self.table.columns:
                        msg = 'BankAccount {NAME}: the associated column "{COL}" for transaction account {ACCT} is ' \
                              'not found in the list of table columns'\
                            .format(NAME=name, ACCT=transaction_acct, COL=assoc_column)
                        logger.error(msg)

                        continue

                    param_entry = assoc_params[assoc_column]
                    if 'Column' not in param_entry:
                        msg = 'BankAccount {NAME}: the association parameter "{COL}" for transaction account {ACCT} ' \
                              'requires the "Column" field to be specified in the configuration'\
                            .format(NAME=name, ACCT=transaction_acct, COL=assoc_column)
                        logger.error(msg)

                        continue

                    try:
                        param_entry['Level'] = int(param_entry['Level'])
                    except (KeyError, ValueError):
                        param_entry['Level'] = 0

                    params[assoc_column] = param_entry

                trans_entry['AssociationParameters'] = params

                self.transactions[transaction_acct] = trans_entry

        self.void_transactions = entry.get('VoidTransactions', entry.get('FailedTransactions', {}))

        try:
            self.import_rules = entry['ImportRules']
        except KeyError:
            self.import_rules = record_entry.import_rules

        self.ref_df = None
        self.primary = False

    def key_lookup(self, component):
        """
        Lookup a component's GUI element key using the component's name.
        """
        element_names = [i[1:-1].split('_')[-1] for i in self.elements]
        if component in element_names:
            key_index = element_names.index(component)
            key = self.elements[key_index]
        else:
            logger.warning('BankAccount {NAME}: component "{COMP}" not found in list of elements'
                           .format(NAME=self.name, COMP=component))
            key = None

        return key

    def bind_keys(self, window):
        """
        Add hotkey bindings to the data element.
        """
        elem_key = self.table.key_lookup('Element')
        window[elem_key].bind('<Control-a>', '+APPROVE+')
        window[elem_key].bind('<Control-r>', '+RESET+')
        window[elem_key].bind('<Control-l>', '+LINK+')

    def get_table(self):
        """
        Return the relevant account table for the current reconciliation.
        """
        if self.primary:
            return self.table
        else:
            return self.assoc_table

    def events(self):
        """
        Return GUI event elements.
        """
        return self.bindings

    def reset(self, window):
        """
        Reset the elements and attributes of the bank record tab.
        """
        table = self.table

        # Reset the record table and the reference dataframe
        self.table.reset(window)
        self.assoc_table.reset(window)
        self.ref_df = None
        self.primary = False

        # Disable table element events
        table.disable(window)

    def run_event(self, window, event, values):
        """
        Run a bank account entry event.
        """
        pd.set_option('display.max_columns', None)

        colmap = self._col_map
        table = self.get_table()
        table_keys = table.bindings
        tbl_key = table.key_lookup('Element')
        approve_key = self.key_lookup('Approve')
        approve_hkey = '{}+APPROVE+'.format(tbl_key)
        reset_key = self.key_lookup('Reset')
        reset_hkey = '{}+RESET+'.format(tbl_key)

        # Return values
        reference_indices = None
        record_indices = None

        # Run a record table event.
        if event in table_keys:
            open_key = '{}+LCLICK+'.format(tbl_key)
            return_key = '{}+RETURN+'.format(tbl_key)

            can_open = table.modifiers['open']
            can_edit = table.modifiers['edit']

            # Record was selected for opening
            if event in (open_key, return_key) and can_open:
                association_rule = self.association_rule

                # Close options panel, if open
                table.set_table_dimensions(window)

                # Find row selected by user
                try:
                    select_row_index = values[tbl_key][0]
                except IndexError:  # user double-clicked too quickly
                    msg = 'table row could not be selected'
                    logger.debug('DataTable {NAME}: {MSG}'.format(NAME=table.name, MSG=msg))
                else:
                    # Get the real index of the selected row
                    index = table.get_index(select_row_index)
                    record_indices = [index]

                    logger.debug('DataTable {NAME}: opening record at real index {IND}'
                                 .format(NAME=table.name, IND=index))
                    if can_open:
                        ref_df = self.ref_df
                        #level = 0 if self.primary else 1
                        level = 1

                        record = table.load_record(index, level=level, savable=False,
                                                   references={association_rule: ref_df})
                        if record is None:
                            msg = 'unable to update references for record at index {IND} - no record was returned' \
                                .format(IND=index)
                            logger.error('DataTable {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                            return {}

                        # Update reference values
                        if can_edit:  # only update references if table is editable
                            record_id = record.record_id()

                            # Update record values
                            try:
                                record_values = record.export_values()
                            except Exception as e:
                                msg = 'unable to update row {IND} values'.format(IND=index)
                                logger.exception(
                                    'DataTable {NAME}: {MSG} - {ERR}'.format(NAME=self.name, MSG=msg, ERR=e))
                            else:
                                table.update_row(index, record_values)
                                print('new values for table row {}'.format(index))
                                print(table.df.loc[index])

                                self.update_display(window)

                            # Update the references dataframe
                            try:
                                refboxes = record.fetch_element('refbox', by_type=True)
                            except KeyError:
                                msg = 'no references defined for record type {TYPE}'.format(TYPE=record.name)
                                logger.error('DataTable {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                                return {}

                            for refbox in refboxes:
                                if refbox.association_rule != association_rule:
                                    continue

                                if not refbox.edited:  # only update the references if the refbox was modified
                                    continue

                                ref_values = refbox.export_reference().drop(labels=['RecordID', 'RecordType'])
                                reference_indices = ref_df.index[ref_df['RecordID'] == record_id]
                                try:
                                    ref_df.loc[reference_indices, ref_values.index.tolist()] = ref_values.tolist()
                                except KeyError as e:
                                    msg = 'failed to update reference {REF} for record {ID}'\
                                        .format(REF=refbox.name, ID=record_id)
                                    logger.error(
                                        'DataTable {NAME}: {MSG} - {ERR}'.format(NAME=self.name, MSG=msg, ERR=e))
                                else:
                                    reference_indices = reference_indices.tolist()

            # Single-clicked table row(s)
            elif event == tbl_key:
                table.run_event(window, event, values)

                # Get index of the selected rows
                record_indices = table.selected(real=True)
                print('selected real indices are: {}'.format(record_indices))

            else:
                table.run_event(window, event, values)

        elif event in (approve_key, approve_hkey):
            # Find rows selected by user for approval
            select_row_indices = values[tbl_key]

            # Get the real indices of the selected rows
            indices = table.get_index(select_row_indices)

            # Get record IDs for the selected rows
            record_ids = table.df.loc[indices, table.id_column].tolist()

            try:
                reference_indices = self.approve(record_ids)
            except Exception as e:
                msg = 'failed to approve records at table indices {INDS}'.format(INDS=indices)
                logger.error('BankAccount {NAME}: {MSG} - {ERR}'.format(NAME=self.name, MSG=msg, ERR=e))

            # Update the status in the records table. This will also update the "is edited" column of the table to
            # indicate that the records at the given indices were edited wherever the new values do not match the old
            # values.
            if 'Approved' in colmap:
                table.update_column(colmap['Approved'], True, indices=indices)

            # Deselect selected rows
            table.deselect(window)

        elif event in (reset_key, reset_hkey):
            # Find rows selected by user for deletion
            select_row_indices = values[tbl_key]

            # Get the real indices of the selected rows
            indices = table.get_index(select_row_indices)

            # Get record IDs for the selected rows
            record_ids = table.df.loc[indices, table.id_column].tolist()

            # Delete references and approval for the selected records
            try:
                reference_indices = self.reset_references(record_ids, index=False)
            except Exception as e:
                msg = 'failed to reset record references at table indices {INDS}'.format(INDS=indices)
                logger.error('BankAccount {NAME}: {MSG} - {ERR}'.format(NAME=self.name, MSG=msg, ERR=e))

            # Deselect selected rows
            table.deselect(window)

            # Reset void transaction status
            self.reset_records(indices, index=True)

        return {'ReferenceIndex': reference_indices, 'RecordIndex': record_indices}

    def layout(self, size, primary: bool = True):
        """
        GUI layout for the account sub-panel.
        """
        width, height = size
        if primary:
            table = self.table
            panel_key = self.key_lookup('Panel')
        else:
            table = self.assoc_table
            panel_key = self.key_lookup('AssocPanel')

        # Element parameters
        bg_col = mod_const.ACTION_COL
        pad_frame = mod_const.FRAME_PAD

        # Element sizes
        tbl_width = width - 30
        tbl_height = height * 0.55

        # Layout
        tbl_layout = [[table.layout(tooltip=self.title, size=(tbl_width, tbl_height), padding=(0, 0))]]

        #panel_key = self.key_lookup('Panel')
        layout = sg.Col(tbl_layout, key=panel_key, pad=(pad_frame, pad_frame), justification='c',
                        vertical_alignment='t', background_color=bg_col, expand_x=True, visible=False)

        return layout

    def resize(self, window, size):
        """
        Resize the account sub-panel.
        """
        width, height = size

        # Reset table size
        tbl_width = width
        tbl_height = height
        self.table.resize(window, size=(tbl_width, tbl_height))
        self.assoc_table.resize(window, size=(tbl_width, tbl_height))

    def fetch_reference_parameter(self, param, indices):
        """
        Fetch reference parameter values at provided record table row indices.
        """
        refmap = self.ref_map
        table = self.get_table()
        header = table.df.columns.tolist()

        try:
            column = refmap[param]
        except KeyError:
            msg = 'reference parameter "{PARAM}" is not in the configured reference map'.format(PARAM=param)
            logger.error('BankAccount {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            return None

        if column not in header:
            msg = 'reference parameter "{PARAM}" is not in the configured reference map'.format(PARAM=param)
            logger.error('BankAccount {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            return None

        try:
            param_values = table.df.loc[indices, column]
        except KeyError:
            msg = 'row indices {INDS} are not found in the records table'.format(INDS=indices)
            logger.error('BankAccount {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            param_values = None

        return param_values

    def merge_references(self, df: pd.DataFrame = None):
        """
        Merge the records table and the reference table on configured reference map columns.

        Arguments:
            df (DataFrame): merge references with the provided records dataframe [Default: use full records dataframe].

        Returns:
            df (DataFrame): dataframe of records merged with their corresponding reference entries.
        """
        pd.set_option('display.max_columns', None)

        ref_map = self.ref_map
        ref_df = self.ref_df.copy()
        table = self.get_table()

        df = table.data() if df is None else df

        # Reorder the references dataframe to match the order of the records in the records table
        ref_df.set_index('RecordID', inplace=True)
        ref_df = ref_df.reindex(index=df['RecordID'])

        # Get shared indices in case the references dataframe does not contain all of the data of the records dataframe
        if df.shape[0] != ref_df.shape[0]:
            logger.warning('BankAccount {NAME}: the records dataframe and reference dataframe of of unequal sizes'
                           .format(NAME=self.name))
            indices = df[df['Records'].isin(ref_df.index.tolist())].index
        else:
            indices = df.index.tolist()

        # Update the configured references columns in the records dataframe to be the same as the columns in references
        # dataframe
        for column in ref_map:
            mapped_col = ref_map[column]

            new_values = ref_df[column].tolist()
            table.update_column(mapped_col, new_values, indices=indices)

    def update_references(self, ref_df):
        """
        Update the reference dataframe using a corresponding reference dataframe.
        """
        pd.set_option('display.max_columns', None)

        df = self.ref_df.copy()

        # Drop references records that are not found as corresponding references in the reference dataframe
        ref_ids = df['ReferenceID'].dropna()
        ref_df = ref_df[ref_df['RecordID'].isin(ref_ids)]

        if ref_df.empty:
            logger.debug('BankAccount {NAME}: no references remaining after filtering references that are not shared'
                         .format(NAME=self.name))
            return df

        # Delete reference entries that were deleted in the corresponding reference dataframe
        deleted_references = ref_df.loc[ref_df['ReferenceID'].isna(), 'RecordID']
        if not deleted_references.empty:
            ids_to_delete = df.loc[df['ReferenceID'].isin(deleted_references.tolist()), 'RecordID'].tolist()

            logger.debug('BankAccount {NAME}: removing references {REFS}'.format(NAME=self.name, REFS=ids_to_delete))
            self.reset_references(ids_to_delete, index=False)
            self.reset_records(ids_to_delete, index=False)

            ref_df.drop(deleted_references.index, inplace=True)
            df = self.ref_df.copy()

        # Subset reference table on matching reference records
        if ref_df.empty:
            logger.debug('BankAccount {NAME}: no references remaining to modify after removing the deleted references'
                         .format(NAME=self.name))
            return df

        df.set_index('RecordID', inplace=True)
        ref_df.set_index('ReferenceID', inplace=True)

        mod_cols = ['ReferenceDate', 'ReferenceNotes', 'IsApproved']
        df.loc[ref_df.index, mod_cols] = ref_df[mod_cols]

        df.reset_index(inplace=True)

        return df

    def approve(self, record_ids):
        """
        Manually approve references for the selected records.

        Arguments:
            record_ids (list): list of record IDs to approve.

        Returns:
            ref_indices (list): list of affected references indices.
        """
        ref_df = self.ref_df

        # Set the approved column of the reference entries corresponding to the selected records to True.
        logger.info('DataTable {TBL}: approving references for records {IDS}'
                    .format(TBL=self.name, IDS=record_ids))
        ref_indices = ref_df.index[ref_df['RecordID'].isin(record_ids)]
        ref_df.loc[ref_indices, ['IsApproved']] = True

        return ref_indices.tolist()

    def reset_records(self, identifiers, index: bool = True):
        """
        Reset reconciliation parameters for the selected records.

        Arguments:
            identifiers (list): list of record identifiers corresponding to the records to modify.

            index (bool): record identifiers are table indices [Default: True].

        Returns:
            indices (list): list of affected record indices.
        """
        table = self.get_table()
        colmap = self._col_map

        if index:
            indices = identifiers
        else:
            df = table.df
            indices = df.index[df[table.id_column].isin(identifiers)].tolist()

        if 'Void' in colmap:
            table.update_column(colmap['Void'], False, indices=indices)

        if 'Approved' in colmap:
            table.update_column(colmap['Approved'], False, indices=indices)

        return indices

    def reset_references(self, identifiers, index: bool = False):
        """
        Reset record references for the selected records.

        Arguments:
            identifiers (list): list of record identifiers corresponding to the records to modify.

            index (bool): record identifiers are table indices [Default: False - identifiers are record IDs].

        Returns:
            indices (list): list of affected references indices.
        """
        ref_df = self.ref_df

        if index:
            indices = identifiers
        else:
            indices = ref_df.index[ref_df['RecordID'].isin(identifiers)].tolist()

        # Clear the reference entries corresponding to the selected record
        logger.info('DataTable {TBL}: removing references for records {IDS}'
                    .format(TBL=self.name, IDS=identifiers))
        ref_columns = ['ReferenceID', 'ReferenceDate', 'ReferenceType', 'ReferenceNotes', 'IsApproved']
        ref_df.loc[indices, ref_columns] = [None, None, None, None, False]

        return indices

    def search_void(self, df):
        """
        Set the correct transaction type for failed transaction records.
        """
        pd.set_option('display.max_columns', None)

        table = self.get_table()
        record_type = self.record_type
        column_map = self._col_map
        void_transactions = self.void_transactions

        if not void_transactions:
            return df

        try:
            type_col = column_map['TransactionType']
            failed_col = column_map['Void']
            withdraw_col = column_map['Withdrawal']
            deposit_col = column_map['Deposit']
            date_col = column_map['TransactionDate']
            tcode_col = column_map['TransactionCode']
        except KeyError as e:
            msg = 'missing required column mapping {ERR}'.format(ERR=e)
            raise KeyError(msg)

        void_records = []
        # Search for bounced cheques
        bc_entry = void_transactions.get('ChequeBounce', None)
        print('BankAccount {}: searching for bounced cheques'.format(self.name))
        if bc_entry:
            bc_code = bc_entry.get('Code', 'RT')
            bounced = df[(df[tcode_col] == bc_code) & (df[type_col] == 1)]
            print('BankAccount {}: finding nearest matches for all records with code {}:'.format(self.name, bc_code))
            print(bounced)
            deposits = df[df[type_col] == 0]
            matches = nearest_matches(bounced.rename(columns={date_col: 'Date', withdraw_col: 'Amount'}),
                                      deposits.rename(columns={date_col: 'Date', deposit_col: 'Amount'}), 'Date',
                                      on='Amount', value_range=bc_entry.get('DateRange', 1))

            print('BankAccount {}: all matched indices:'.format(self.name))
            print(matches)
            for matching_inds in matches:
                record_ind, ref_ind = matching_inds

                record_id = bounced.loc[record_ind, 'RecordID']
                ref_id = deposits.loc[ref_ind, 'RecordID']
                match_pair = (record_id, ref_id)
                print('record IDs of the matching bounced check transactions are {} and {}'.format(*match_pair))

                # Insert the reference into the account records reference dataframe
                warning = bc_entry.get('Description', 'bounced check')

                self.add_reference(record_id, ref_id, record_type, warning=warning)
                self.add_reference(ref_id, record_id, record_type, warning=warning)

                # Set the transaction code for the bounced cheque
                void_records.extend(list(match_pair))
                df.drop(df[df['RecordID'].isin(match_pair)].index, inplace=True)

        # Search for mistaken payments
        print('BankAccount {}: searching for mistaken payments'.format(self.name))
        mp_entry = void_transactions.get('MistakenPayments', None)
        if mp_entry:
            withdrawals = df[df[type_col] == 1]
            deposits = df[df[type_col] == 0]
            matches = nearest_matches(deposits.rename(columns={date_col: 'Date', deposit_col: 'Amount'}),
                                      withdrawals.rename(columns={date_col: 'Date', withdraw_col: 'Amount'}), 'Date',
                                      on='Amount', value_range=mp_entry.get('DateRange', 1))

            print('BankAccount {}: all matched indices:'.format(self.name))
            print(matches)
            for matching_inds in matches:
                record_ind, ref_ind = matching_inds

                record_id = deposits.loc[record_ind, 'RecordID']
                ref_id = withdrawals.loc[ref_ind, 'RecordID']
                match_pair = (record_id, ref_id)

                # Insert the reference into the account records reference dataframe
                warning = mp_entry.get('Description', 'mistaken payment')

                self.add_reference(record_id, ref_id, record_type, warning=warning)
                self.add_reference(ref_id, record_id, record_type, warning=warning)

                # Set the transaction code for the bounced cheque
                void_records.extend(list(match_pair))
                df.drop(df[df['RecordID'].isin(match_pair)].index, inplace=True)

        # Update the record tables
        void_inds = table.df.loc[table.df['RecordID'].isin(void_records)].index.tolist()
        if len(void_inds) > 0:
            print('BankAccount {}: setting void column {} to true for indices:'.format(self.name, failed_col))
            print(void_inds)
            table.update_column(failed_col, True, indices=void_inds)

        return df

    def filter_void(self, df: pd.DataFrame = None):
        """
        Remove void transactions from a dataframe.
        """
        column_map = self._col_map
        table = self.get_table()

        df = df if df is not None else table.data()

        try:
            failed_col = column_map['Void']
        except KeyError:
            return df

        df.drop(df[df[failed_col]].index, inplace=True)

        return df

    def add_reference(self, record_id, reference_id, reftype, approved: bool = False, warning: str = None):
        """
        Add a record reference to the references dataframe.
        """
        ref_cols = ['ReferenceID', 'ReferenceDate', 'ReferenceType', 'ReferenceNotes', 'IsApproved', 'IsHardLink',
                    'IsChild', 'IsDeleted']

        ref_values = [reference_id, datetime.datetime.now(), reftype, warning, approved, False, False, False]

        self.ref_df.loc[self.ref_df['RecordID'] == record_id, ref_cols] = ref_values

    def has_reference(self, record_id):
        """
        Confirm whether an account record is referenced.
        """
        ref_df = self.ref_df
        reference = ref_df.loc[ref_df['RecordID'] == record_id, 'ReferenceID']

        if reference.empty:
            return False
        elif pd.isna(reference.squeeze()):
            return False
        else:
            return True

    def update_display(self, window):
        """
        Update the account's record table display.
        """
        table = self.get_table()

        # Deselect selected rows
        table.deselect(window)

        # Merge records and references dataframes
        self.merge_references()
        table.df = table.set_conditional_values()

        # Update the display table
        table.update_display(window)

    def load_data(self, params, records: list = None):
        """
        Load record and reference data from the database.
        """
        table = self.get_table()

        logger.debug('BankAccount {NAME}: loading record data'.format(NAME=self.name))

        try:
            df = self.load_records(params, records=records)
        except Exception as e:
            msg = '{MSG} -  see log for details'.format(MSG=e)
            raise ImportError(msg)

        # Load the record references from the reference table connected with the association rule
        record_ids = df[self.table.id_column].tolist()
        logger.debug('BankAccount {NAME}: loading reference data'.format(NAME=self.name))
        try:
            self.ref_df = self.load_references(record_ids)
        except Exception as e:
            msg = '{MSG} -  see log for details'.format(MSG=e)
            raise ImportError(msg)

        # Merge the configured reference columns with the records table
        ref_map = self.ref_map
        ref_df = self.ref_df.copy()

        # Set index to record ID for updating
        df.set_index('RecordID', inplace=True)
        ref_df.set_index('RecordID', inplace=True)

        # Rename reference columns to record columns using the reference map
        mapped_df = ref_df[list(ref_map)].rename(columns=ref_map)

        # Update record reference columns
        drop_cols = [i for i in mapped_df.columns if i in df.columns]
        df = df.drop(columns=drop_cols).join(mapped_df)
        df.reset_index(inplace=True)

        # Update the record table dataframe with the data imported from the database
        table.df = table.append(df)

    def load_references(self, record_ids):
        """
        Load record references from the database.
        """
        rule_name = self.association_rule
        record_type = self.record_type
        record_entry = settings.records.fetch_rule(record_type)

        # Import reference entries from the database
        try:
            import_df = record_entry.import_references(record_ids, rule_name)
        except Exception as e:
            msg = 'failed to import references from association rule {RULE}'.format(RULE=rule_name)
            logger.exception('BankAccount {NAME}: {MSG} - {ERR}'.format(NAME=self.name, MSG=msg, ERR=e))

            raise ImportError(msg)

        # Create new reference entries for records with IDs not currently found in the database
        ref_df = pd.merge(pd.DataFrame({'RecordID': record_ids}), import_df, how='left', on='RecordID')
        ref_df['RecordType'].fillna(record_type, inplace=True)

        # Set datatypes
        bool_columns = ['IsChild', 'IsHardLink', 'IsApproved', 'IsDeleted']
        ref_df[bool_columns] = ref_df[bool_columns].fillna(False)
        ref_df = ref_df.astype({i: np.bool for i in bool_columns})

        return ref_df

    def load_records(self, parameters, records: list = None):
        """
        Load record and reference data from the database based on the supplied parameter set.

        Arguments:
            parameters (list): list of data parameters to filter the records database table on.

            records (list): also load records in the list of record IDs.

        Returns:
            success (bool): records and references were loaded successfully.
        """
        #pd.set_option('display.max_columns', None)

        record_type = self.record_type
        record_entry = settings.records.fetch_rule(record_type)

        # Prepare the database query statement
        try:
            df = record_entry.import_records(params=parameters, import_rules=self.import_rules)
        except Exception as e:
            msg = 'failed to import data from the database'
            logger.exception('BankAccount {NAME}: {MSG} - {ERR}'.format(NAME=self.name, MSG=msg, ERR=e))

            raise ImportError(msg)

        # Load remaining records not yet loaded using the parameters
        imported_ids = df[self.table.id_column].tolist()
        if records:
            remaining_records = list(set(records).difference(imported_ids))

            if not len(remaining_records) > 0:
                return df

            loaded_df = record_entry.load_records(remaining_records)

            # Filter loaded records by static parameters, if any
            for parameter in parameters:
                if parameter.editable:
                    continue

                try:
                    loaded_df = parameter.filter_table(loaded_df)
                except Exception as e:
                    msg = 'failed to filter loaded records on parameter {PARAM}'.format(PARAM=parameter.name)
                    logger.exception('BankAccount {NAME}: {MSG} - {ERR}'.format(NAME=self.name, MSG=msg, ERR=e))
                    raise

            df = df.append(loaded_df, ignore_index=True)

        return df


def nearest_match(row, ref_df, columns):
    """
    Find closest matches between dataframes on a shared column.

    Arguments:
        row (Series): series containing the data to compare to the reference dataframe.

        ref_df (DataFrame): reference dataframe to match to the dataframe rows.

        columns (list): name of the columns used to find the closest match.
    """
    is_float_dtype = pd.api.types.is_float_dtype
    is_integer_dtype = pd.api.types.is_integer_dtype
    is_datetime_dtype = pd.api.types.is_datetime64_any_dtype
    match = pd.Series()

    diffs = 1
    for column in columns:
        dtype = ref_df[column].dtype
        if not (is_float_dtype(dtype) or is_integer_dtype(dtype) or is_datetime_dtype(dtype)):
            msg = 'match column "{COL}" must have a numeric or datatime data type'.format(COL=column)
            logger.warning(msg)

            continue

        diffs = diffs * (ref_df[column] - row[column])

    if not isinstance(diffs, pd.Series):
        return match

    print('product of differences are:')
    print(diffs)

    min_diff = diffs.abs().idxmin()
    print('index of minimum is: {}'.format(min_diff))
    print(ref_df)
    match = ref_df.loc[min_diff]

    return match


def nearest_matches(df, ref_df, column, on: str = None, value_range: int = None):
    """
    Find closest matches between dataframes on a shared column.

    Arguments:
        df (DataFrame): dataframe containing the rows to find matches for.

        ref_df (DataFrame): reference dataframe to match to the dataframe rows.

        column (str): name of the column used to find the closest match.

        on (str): join the dataframe and the reference dataframe on the provided column before searching for the
            closest match [Default: None]

        value_range (int): optional filter range. The matching algorithm will only consider references with
            column values within the provided range [Default: consider all values].
    """
    is_float_dtype = pd.api.types.is_float_dtype
    is_integer_dtype = pd.api.types.is_integer_dtype
    is_datetime_dtype = pd.api.types.is_datetime64_any_dtype
    dtype = ref_df[column].dtype

    if value_range:
        if is_datetime_dtype(dtype):
            deviation = datetime.timedelta(days=value_range)
        elif is_float_dtype(dtype) or is_integer_dtype(dtype):
            deviation = value_range
        else:
            deviation = None
    else:
        deviation = None

    matches = []
    for i, row in df.iterrows():
        row_value = row[column]

        if on:
            match_df = ref_df[ref_df[on] == row[on]]
        else:
            match_df = ref_df

        if deviation is not None:
            ref_values = match_df[column]
            match_df = match_df[(ref_values >= row_value - deviation) &
                                (ref_values <= row_value + deviation)]

        if match_df.empty:  # no matches found after value filtering
            continue

        closest_ind = match_df[column].sub(row_value).abs().idxmin()
        matches.append((i, closest_ind))

    return matches
