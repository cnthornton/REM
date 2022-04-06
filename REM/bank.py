"""
REM bank reconciliation configuration classes and objects.
"""

import datetime
from random import randint

import pandas as pd
import PySimpleGUI as sg

import REM.constants as mod_const
import REM.elements as mod_elem
import REM.layouts as mod_lo
import REM.parameters as mod_param
import REM.secondary as mod_win2
from REM.client import logger, settings, user, thread_operation


class BankRule:
    """
    Class to store and manage a configured bank reconciliation rule.

    Attributes:

        name (str): bank reconciliation rule name.

        id (int): GUI element number.

        element_key (str): panel element key.

        elements (dict): GUI element keys.

        bindings (dict): GUI event bindings.

        menu_title (str): rule menu title.

        menu_flags (dict): submenu flags that change the initial behavior of the rule.

        permissions (str): permissions required to view the accounting method. Default: user.

        parameters (list): list of rule parameters.

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
        self.elements = {i: '-{NAME}_{ID}_{ELEM}-'.format(NAME=self.name, ID=self.id, ELEM=i) for i in
                         ('Panel', 'Account', 'Association', 'Reconcile', 'Parameters', 'Cancel', 'Save',
                          'Panel1', 'Panel2', 'Warning1', 'Warning2', 'Frame', 'Buttons', 'Title')}

        self.bindings = {self.elements[i]: i for i in
                         ('Cancel', 'Save', 'Account', 'Association', 'Parameters', 'Reconcile')}

        try:
            self.menu_title = entry['MenuTitle']
        except KeyError:
            self.menu_title = name

        try:
            self.menu_flags = entry['MenuFlags']
        except KeyError:
            self.menu_flags = None

        try:
            permissions = entry['Permissions']
        except KeyError:
            self.permissions = {'view': None, 'create': None, 'edit': None}
        else:
            self.permissions = {'view': permissions.get('View', None),
                                'create': permissions.get('Create', None),
                                'edit': permissions.get('Edit', None),
                                }

        self.parameters = []
        try:
            params = entry['RuleParameters']
        except KeyError:
            msg = 'missing required parameter "RuleParameters"'
            logger.error('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            raise AttributeError(msg)

        for param_name in params:
            param_entry = params[param_name]
            try:
                param = mod_param.initialize_parameter(param_name, param_entry)
            except Exception as e:
                logger.error('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=e))

                raise AttributeError(e)

            self.parameters.append(param)
            self.bindings.update(param.bindings)

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
            self.bindings.update(acct.bindings)

        # Dynamic Attributes
        self.in_progress = False

        self.current_account = None
        self.current_panel = None
        self.current_association = None
        self.current_assoc_panel = None
        self.panels = []

    def key_lookup(self, component, rev: bool = False):
        """
        Lookup a bank rule element's component GUI key using the name of the component element.

        Arguments:
            component (str): GUI component name (or key if rev is True) of the bank rule element.

            rev (bool): reverse the element lookup map so that element keys are dictionary keys.
        """
        key_map = self.elements if rev is False else {j: i for i, j in self.elements.items()}
        try:
            key = key_map[component]
        except KeyError:
            msg = 'component {COMP} not found in list of bank rule elements'.format(COMP=component)
            logger.warning('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
            print(key_map)
            key = None

        return key

    def events(self):
        """
        Return a list of the rule's GUI events.
        """
        return self.bindings

    def bind_keys(self, window):
        """
        Bind panel-element hotkeys.
        """
        # Bind events to element keys
        logger.debug('BankRule {NAME}: binding record element hotkeys'.format(NAME=self.name))

        # Bind account table hotkeys
        for acct in self.accts:
            acct.bind_keys(window)

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
                elements = list(acct.elements.values())
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
        disabled = False if value == 'enable' else True
        for param in self.parameters:
            param.toggle(window, off=disabled)

    def run_event(self, window, event, values):
        """
        Run a bank reconciliation event.
        """
        pd.set_option('display.max_columns', None)

        # Get elements of current account
        current_rule = self.name

        current_acct = self.current_account
        current_assoc = self.current_association

        if current_acct:
            acct = self.fetch_account(current_acct)
            acct_keys = acct.bindings
        else:
            acct_keys = []

        if current_assoc:
            assoc_acct = self.fetch_account(current_assoc)
            assoc_keys = assoc_acct.bindings
        else:
            assoc_keys = []

        # Run an account entry event
        if event in acct_keys:
            acct = self.fetch_account(self.current_account)

            triggers = acct.run_event(window, event, values)

            link_event = triggers.get('Link')
            if link_event:
                try:
                    self.link_records(current_acct, current_assoc)
                except Exception as e:
                    msg = 'failed to link records - {ERR}'.format(ERR=e)
                    logger.exception('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
                    mod_win2.popup_error(msg)
                else:
                    self.update_display(window)

            # Update reference dataframes when an account entry event is a reference event. A reference event is any
            # event that may modify one side of a reference, which requires an update to the other side of the
            # reference.
            ref_event = triggers.get('ReferenceEvent')
            if ref_event:
                logger.debug('BankRule {NAME}: references for some records were modified from account table {ACCT}'
                             .format(NAME=self.name, ACCT=acct.name))
                ref_df = acct.merge_records()

                # Flip the record and reference values for the external reference dataframe
                ref_df.rename(columns={'RecordID': 'ReferenceID', 'ReferenceID': 'RecordID',
                                       'RecordType': 'ReferenceType', 'ReferenceType': 'RecordType'}, inplace=True)

                # Update account reference dataframes for currently active panels
                for panel in self.panels:
                    ref_acct = self.fetch_account(panel, by_key=True)

                    logger.debug('BankRule {NAME}: updating transaction account {ACCT} references matching those '
                                 'that were modified'.format(NAME=self.name, ACCT=ref_acct.name))
                    ref_acct.update_references(ref_df)

                self.update_display(window)

            # Update warning element with the reference notes of the selected record, if any.
            selected_record_indices = triggers.get('RecordIndex')
            if selected_record_indices:
                warn1_key = self.key_lookup('Warning1')

                logger.debug('BankRule {NAME}: record indices {INDS} were selected from account table {ACCT}'
                             .format(NAME=self.name, INDS=selected_record_indices, ACCT=acct.name))
                selected_record_ids = acct.get_table().row_ids(indices=selected_record_indices)
                if len(selected_record_ids) > 0:
                    first_selected_record_id = selected_record_ids[0]

                    # Set the reference warning, if any
                    record_warning = acct.fetch_reference_parameter('ReferenceWarnings', first_selected_record_id)
                    if len(record_warning) > 0:
                        record_warning = record_warning[0]
                    else:
                        record_warning = None

                    # Select the reference in the associated table, if any
                    if current_assoc:
                        assoc_acct = self.fetch_account(current_assoc)
                        assoc_table = assoc_acct.get_table()

                        selected_ref_ids = acct.fetch_reference_parameter('ReferenceID', first_selected_record_id)
                        if len(selected_ref_ids) > 0:
                            assoc_display = assoc_table.data(display_rows=True)
                            ref_ind = assoc_display[assoc_display['RecordID'].isin(selected_ref_ids)].index
                            if not ref_ind.empty:
                                select_ind = assoc_table.get_index(ref_ind.tolist(), real=False)
                                assoc_table.select(window, select_ind)
                else:
                    record_warning = None

                window[warn1_key].update(value=settings.format_display(record_warning, 'varchar'))

            return current_rule

        # Run an association account event
        if event in assoc_keys:
            assoc_acct = self.fetch_account(current_assoc)
            triggers = assoc_acct.run_event(window, event, values)

            # Store indices of the selected row(s)
            selected_record_indices = triggers.get('RecordIndex')
            if selected_record_indices:
                warn2_key = self.key_lookup('Warning2')

                logger.debug('BankRule {NAME}: record indices {INDS} were selected from account table {ACCT}'
                             .format(NAME=self.name, INDS=selected_record_indices, ACCT=assoc_acct.name))
                selected_record_ids = assoc_acct.get_table().row_ids(indices=selected_record_indices)

                if len(selected_record_indices) > 0:
                    first_selected_record_id = selected_record_ids[0]
                    record_warning = assoc_acct.fetch_reference_parameter('ReferenceWarnings', first_selected_record_id)
                    if len(record_warning) > 0:
                        record_warning = record_warning[0]
                    else:
                        record_warning = None
                else:
                    record_warning = None

                window[warn2_key].update(value=settings.format_display(record_warning, 'varchar'))

            return current_rule

        # Run a bank rule panel event
        try:
            rule_event = self.bindings[event]
        except KeyError:
            rule_event = None

        # The cancel button or cancel hotkey was pressed. If a reconciliation is in progress, reset the rule but stay
        # in the rule panel. If reconciliation is not in progress, return to home screen.
        if rule_event == 'Cancel':
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
        elif rule_event == 'Save':
            if window[self.key_lookup('Save')].metadata['disabled']:
                return current_rule

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
                    logger.exception('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
                    mod_win2.popup_error(msg)

                    return current_rule
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
                            logger.exception('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
                            mod_win2.popup_error(msg)

                            return current_rule

                        # Reset rule elements
                        current_rule = self.reset_rule(window, current=True)

        # An account was selected from the account entry dropdown. Selecting an account will display the associated
        # sub-panel.
        elif rule_event == 'Account':
            param_key = self.key_lookup('Parameters')

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
        elif rule_event == 'Association':
            acct_title = values[event]
            if not acct_title:
                self.current_account = None
                self.current_panel = None

                return current_rule

            # Hide the current association panel
            if self.current_assoc_panel:
                warn2_key = self.key_lookup('Warning2')
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
        elif rule_event == 'Parameters':
            acct_key = self.key_lookup('Account')
            assoc_key = self.key_lookup('Association')
            param_key = self.key_lookup('Parameters')
            reconcile_key = self.key_lookup('Reconcile')
            save_key = self.key_lookup('Save')

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
                    logger.exception('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
                    mod_win2.popup_error(msg)

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
                        msg = 'failed to load data for association {ACCT} - {MSG}'.format(ACCT=acct_name, MSG=e)
                        logger.exception('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
                        mod_win2.popup_error(msg)

                        return self.reset_rule(window, current=True)

                    assoc_acct.primary = False
                    self.panels.append(self.panel_keys[acct_name])

                # Update the display
                param_w = mod_const.PARAM_SIZE_CHAR[0]
                param_h = len(assoc_accounts)
                window[assoc_key].update(values=assoc_accounts, size=(param_w, param_h))

                self.update_display(window)

                # Disable the account entry selection dropdown
                window[acct_key].update(disabled=True)
                window[assoc_key].update(disabled=False)
                window[param_key].update(disabled=True)

                # Enable elements
                if not user.check_permission(self.permissions['create']):
                    msg = '"{UID}" does not have "create" permissions for the reconciliation panel. Any changes made ' \
                          'during the reconciliation will not be saved. Please contact the administrator if you ' \
                          'suspect that this is in error'.format(UID=user.uid)
                    logger.warning('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
                    mod_win2.popup_error('warning - {MSG}'.format(MSG=msg))
                else:
                    window[save_key].update(disabled=False)
                    window[save_key].metadata['disabled'] = False

                if len(self.panels) > 1:
                    window[reconcile_key].update(disabled=False)

                self.toggle_parameters(window, 'enable')

                # Mark that a reconciliation is currently in progress
                self.in_progress = True

        # Reconcile button was pressed. Will run the reconcile method to find associations with the current primary
        # account and any associated accounts with data.
        elif rule_event == 'Reconcile':
            expand_param = self.fetch_parameter('ExpandSearch')
            failed_param = self.fetch_parameter('SearchFailed')
            run_expanded_search = values[expand_param.key_lookup('Element')]
            search_for_failed = values[failed_param.key_lookup('Element')]

            try:
                self.reconcile_statement(search_expanded=run_expanded_search, search_failed=search_for_failed)
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
        bttn_text_col = mod_const.WHITE_TEXT_COLOR
        bttn_bg_col = mod_const.BUTTON_COLOR
        disabled_text_col = mod_const.DISABLED_TEXT_COLOR
        disabled_bg_col = mod_const.DISABLED_BUTTON_COLOR
        bg_col = mod_const.DEFAULT_BG_COLOR
        header_col = mod_const.HEADER_COLOR
        text_col = mod_const.DEFAULT_TEXT_COLOR

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
                           sg.Button('', key=param_key, image_data=mod_const.SELECT_PARAM_ICON, image_size=(28, 28),
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
        rows = acct_table.selected(real=True)  # real indices of selected account records

        if assoc_name:
            assoc_acct = self.fetch_account(assoc_name)
            assoc_table = assoc_acct.get_table()
            acct_rows = rows
            assoc_rows = assoc_table.selected(real=True)  # real indices of selected association records
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
            msg = 'only one record from the primary account can be associated of one or more records from the ' \
                  'associated account or one record from the associated account linked with one or more records from ' \
                  'the primary account'.format(ACCT=acct_name, ASSOC=assoc_name)
            raise AssertionError(msg)

        if acct.has_reference(record_ids) or assoc_acct.has_reference(reference_ids):
            msg = 'one or more of the selected records already have references'
            raise AssertionError(msg)

        # Allow user to set a note
        user_note = mod_win2.add_note_window()

        # Manually set a mutual references for the selected records
        refdate = datetime.datetime.now()
        for record_id in record_ids:
            for reference_id in reference_ids:
                acct.add_reference(record_id, reference_id, assoc_acct.record_type, approved=True, note=user_note,
                                   refdate=refdate)
                assoc_acct.add_reference(reference_id, record_id, acct.record_type, approved=True, note=user_note,
                                         refdate=refdate)

        return success

    def reconcile_statement(self, search_expanded: bool = False, search_failed: bool = False):
        """
        Run the primary Bank Reconciliation rule algorithm for the record tab.

        Arguments:
            search_expanded (bool): expand the search by ignoring association parameters designated as expanded
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
                     .format(NAME=self.name, VAL=('on' if search_expanded else 'off')))

        table = acct.get_table()
        id_column = table.id_column
        acct_type = acct.record_type

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

        # Initialize the merged dataframe of associated account records
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
                assoc_colname = rule_entry['ForeignField']
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
        df.set_index(id_column, inplace=True)
        logger.debug('BankRule {NAME}: attempting to find associations for account {ACCT} records'
                     .format(NAME=self.name, ACCT=acct.name))
        func_args = {'df': df, 'ref_df': merged_df, 'rules': assoc_ref_maps}
        func_results = thread_operation(search_associations, func_args)
        if func_results['success']:
            matches = func_results['value']
        else:
            err = func_results['value']
            msg = 'failed to find associations between the account and association account records - {}'.format(err)
            logger.error(msg)
            matches = pd.DataFrame()

        for record_id, row in matches.iterrows():
            refdate = datetime.datetime.now()
            ref_id = row['ReferenceID']
            assoc_acct_name = row['Source']
            approved = row['Approved']
            warning = row['Warning']

            assoc_acct = self.fetch_account(assoc_acct_name)
            ref_type = assoc_acct.record_type

            # Insert the reference into the account records reference dataframe
            acct.add_reference(record_id, ref_id, ref_type, approved=approved, refdate=refdate, warning=warning)

            # Insert the reference into the associated account's reference dataframe
            assoc_acct.add_reference(ref_id, record_id, acct_type, approved=approved, refdate=refdate, warning=warning)

        nfound = matches.shape[0]

        if search_expanded:
            msg = 'using expanded search criteria to find any remaining associations for account {ACCT} records' \
                .format(ACCT=acct.name)
            logger.info('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            matched_indices = matches.index
            df.drop(matched_indices, inplace=True)

            # matches = search_associations_expanded(df, merged_df, assoc_ref_maps)
            func_args = {'df': df, 'ref_df': merged_df, 'rules': assoc_ref_maps}
            func_results = thread_operation(search_associations_expanded, func_args)
            if func_results['success']:
                matches = func_results['value']
            else:
                err = func_results['value']
                msg = 'failed to find associations between the account and association account records from an ' \
                      'expanded search - {ERR}'.format(ERR=err)
                logger.error(msg)
                matches = pd.DataFrame()

            for record_id, row in matches.iterrows():
                refdate = datetime.datetime.now()
                ref_id = row['ReferenceID']
                assoc_acct_name = row['Source']
                approved = row['Approved']
                warning = row['Warning']

                assoc_acct = self.fetch_account(assoc_acct_name)
                ref_type = assoc_acct.record_type

                # Insert the reference into the account records reference dataframe
                acct.add_reference(record_id, ref_id, ref_type, approved=approved, refdate=refdate, warning=warning)

                # Insert the reference into the associated account's reference dataframe
                assoc_acct.add_reference(ref_id, record_id, acct_type, approved=approved, refdate=refdate,
                                         warning=warning)

            nfound += matches.shape[0]

        logger.info('BankRule {NAME}: found {NMATCH} associations out of {NTOTAL} unreferenced account {ACCT} records'
                    .format(NAME=self.name, NMATCH=nfound, NTOTAL=df.shape[0], ACCT=acct.name))

        return True

    def reconcile_statement_old(self, search_expanded: bool = False, search_failed: bool = False):
        """
        Run the primary Bank Reconciliation rule algorithm for the record tab.

        Arguments:
            search_expanded (bool): expand the search by ignoring association parameters designated as expanded
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
                     .format(NAME=self.name, VAL=('on' if search_expanded else 'off')))

        table = acct.get_table()
        id_column = table.id_column
        acct_type = acct.record_type

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

        # Initialize the merged dataframe of associated account records
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
                assoc_colname = rule_entry['ForeignField']
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
                refdate = datetime.datetime.now()
                acct.add_reference(record_id, ref_id, ref_type, approved=True, refdate=refdate)

                # Insert the reference into the associated account's reference dataframe
                assoc_acct = self.fetch_account(assoc_acct_name)
                assoc_acct.add_reference(ref_id, record_id, acct_type, approved=True, refdate=refdate)

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
                refdate = datetime.datetime.now()
                acct.add_reference(record_id, ref_id, ref_type, approved=True, warning=warning, refdate=refdate)

                # Insert the reference into the associated account's reference dataframe
                assoc_acct = self.fetch_account(assoc_acct_name)
                assoc_acct.add_reference(ref_id, record_id, acct_type, approved=True, warning=warning, refdate=refdate)

        if search_expanded:
            msg = 'using expanded search criteria to find any remaining associations for account {ACCT} records'\
                .format(ACCT=acct.name)
            logger.info('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            df.drop(matched_indices, inplace=True)
            for index, row in df.iterrows():
                record_id = getattr(row, id_column)

                match = self.expand_search(row, merged_df, assoc_ref_maps, expand_level=0)
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
                refdate = datetime.datetime.now()
                acct.add_reference(record_id, ref_id, ref_type, approved=False, warning=warning, refdate=refdate)

                # Insert the reference into the associated account's reference dataframe
                assoc_acct = self.fetch_account(assoc_acct_name)
                assoc_acct.add_reference(ref_id, record_id, acct_type, approved=False, warning=warning, refdate=refdate)

        logger.info('BankRule {NAME}: found {NMATCH} associations out of {NTOTAL} unreferenced account {ACCT} records'
                    .format(NAME=self.name, NMATCH=nfound, NTOTAL=df.shape[0], ACCT=acct.name))

        return True

    def expand_search(self, row, ref_df, ref_map, comp_df=None, expand_level: int = 0, closest_match: list = None):
        """
        Attempt to find matching records using iterative expansion of reference columns.

        Arguments:
            row (Series): record entry of interest.

            ref_df (DataFrame): table of record entries to search the record entry against.

            ref_map (dict): transaction associations.

            comp_df (DataFrame): optional table of already performed comparisons.

            expand_level (int): start the search for matching entries at the given expansion level [Default: 0].

            closest_match (list): use these columns to find the closest match to the record entry.
        """
        results = pd.Series()
        ref_df['_Warning_'] = None
        row_index = row.name

        matches = pd.DataFrame(columns=ref_df.columns)
        expanded_cols = []
        if not isinstance(comp_df, pd.DataFrame):
            comp_df = ref_df.copy()
            run_comparison = True
        else:
            run_comparison = False

        for assoc_acct_name in ref_map:
            msg = 'searching for matching entries between account {ACCT}, row {ROW} and association {ASSOC}'\
                .format(ACCT=self.current_account, ROW=row_index, ASSOC=assoc_acct_name)
            logger.debug('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            # Subset merged df to include only the association records with the given account name
            assoc_df = ref_df[ref_df['_Account_'] == assoc_acct_name]
            if assoc_df.empty:
                msg = 'no entries in association {ASSOC} to compare against account {ACCT}, row {ROW}'\
                    .format(ASSOC=assoc_acct_name, ACCT=self.current_account, ROW=row_index)
                logger.debug('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                continue

            assoc_rules = ref_map[assoc_acct_name]
            failed_indices = set()
            for col in assoc_rules:
                rule_entry = assoc_rules[col]

                # Compare reference column values to the record columns values and store in a comparison table
                col_values = assoc_df[col].copy()
                if run_comparison:
                    pm = bool(int(rule_entry.get('PatternMatching', 0)))
                    ignore = rule_entry.get('IgnoreCharacters', None)
                    row_value = getattr(row, col)
                    col_match = compare_record_values(row_value, col_values, match_pattern=pm, ignore_chars=ignore)

                    comp_df.loc[assoc_df.index, col] = col_match
                else:
                    try:
                        col_match = comp_df.loc[assoc_df.index, col].fillna(False).astype(bool)
                    except KeyError:
                        print('extracting column {} comparisons at indices {}'.format(col, col_values.index.tolist()))
                        print(comp_df)
                        raise

                # Select the value fields that will be used to compare records. All fields with expanded search level
                # greater than current iteration level will be left flexible
                param_level = rule_entry.get('ExpandLevel', 0)
                if param_level > expand_level:  # comparison field has an expand level higher than current search level
                    if col not in expanded_cols:
                        expanded_cols.append(col)
                else:
                    not_matched = ~col_match
                    try:
                        col_failed = col_values[not_matched.tolist()].index.tolist()
                    except (TypeError, KeyError):
                        print('comparison dataframe:')
                        print(comp_df)
                        print('matching columns:')
                        print(col_match)
                        print('not matching values:')
                        print(not_matched.tolist())
                        print(col_match.index.tolist())
                        print('column {} values:'.format(col))
                        print(col_values)
                        raise
                    failed_indices.update(col_failed)

            # Find exact matches between account record and the associated account records using relevant cols
            acct_matches = assoc_df[~assoc_df.index.isin(failed_indices)]
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

                        param_level = rule_entry.get('ExpandLevel', 0)
                        if param_level == expand_level:
                            if col not in expanded_cols:
                                expanded_cols.append(col)

                msg = 'no matches found for account {ACCT}, row {ROW} at expanded search level {L} - returning to ' \
                      'previous search level matches to find for the closest match on columns {COLS}' \
                    .format(ACCT=self.current_account, ROW=row_index, L=expand_level, COLS=expanded_cols)
                logger.info('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
                results = self.expand_search(row, ref_df, ref_map, comp_df=comp_df, expand_level=prev_level,
                                             closest_match=expanded_cols)
            else:
                msg = 'no matches found for account {ACCT}, row {ROW} from an expanded search' \
                    .format(ACCT=self.current_account, ROW=row_index)
                logger.warning('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

        elif nmatch == 1:  # potential match, add with a warning
            results = matches.iloc[0].copy()

            # Determine appropriate warning for the expanded search
            acct_name = results['_Account_']
            assoc_rules = ref_map[acct_name]

            warning = []
            for column in expanded_cols:
                try:
                    rule_entry = assoc_rules[column]
                except KeyError:
                    logger.warning('BankRule {NAME}: column {COL} does not have a configured association parameter for '
                                   'association account {ACCT}'.format(NAME=self.name, COL=column, ACCT=acct_name))
                    continue

                if not comp_df.loc[results.name, column]:  # values do not match
                    alt_warn = 'values for expanded column {COL} do not match'.format(COL=column)
                    col_warning = rule_entry.get('Warning', alt_warn)
                    warning.append('- {}'.format(col_warning))

            if len(warning) > 0:
                warning.insert(0, 'Warning:')
                results['_Warning_'] = '\n'.join(warning)

        elif nmatch > 1:  # need to increase specificity to get the best match by adding more comparison fields
            msg = 'found more than one expanded match for account {ACCT}, row {ROW} at search level {L} - ' \
                  'searching for the best match'.format(ACCT=self.current_account, ROW=row_index, L=expand_level)
            logger.warning('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            # Attempt to find the best matching record
            if not closest_match:  # one or more matches were found in previous iteration
                # Find the best match by iterative field inclusion
                msg = 'attempting to find the best match for row {ROW} through iterative field inclusion'\
                    .format(ROW=row.name)
                logger.debug('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                results = self.expand_search(row, matches, ref_map, comp_df=comp_df, expand_level=expand_level + 1)
            else:  # zero matches were found in the previous iteration
                # Find the best match by searching for nearest like value on the closest match fields
                msg = 'attempting to find the best match for row {ROW} by searching for nearest value on fields ' \
                      '{FIELDS}'.format(ROW=row_index, FIELDS=closest_match)
                logger.debug('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                results = nearest_match(row, matches, closest_match)
                if results.empty:
                    msg = 'multiple matches found for account {ACCT}, row {ROW} but enough specificity in the data ' \
                          'to narrow it down to one match'.format(ACCT=self.current_account, ROW=row_index)
                    logger.warning('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
                else:
                    # Determine appropriate warning for the nearest match search
                    acct_name = results['_Account_']
                    assoc_rules = ref_map[acct_name]

                    warning = []
                    for closest_col in closest_match:
                        try:
                            rule_entry = assoc_rules[closest_col]
                        except KeyError:
                            logger.warning(
                                'BankRule {NAME}: column {COL} does not have a configured association parameter for '
                                'association account {ACCT}'.format(NAME=self.name, COL=closest_col, ACCT=acct_name))
                            continue

                        alt_warning = 'association is the result of searching for the closest match on "{}"' \
                            .format(closest_col)
                        col_warning = rule_entry.get('Warning2', alt_warning)
                        warning.append('- {}'.format(col_warning))

                    if len(warning) > 0:
                        warning.insert(0, 'Warning:')
                        results['_Warning_'] = '\n'.join(warning)

        return results

    def save(self):
        """
        Save record modifications and new record associations to the database.
        """
        pd.set_option('display.max_columns', None)
        statements = {}

        # Prepare to save the account references and records

        # Save changes to records from all of the active accounts
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

        # Save record references

        # Prepare reference entries from the primary account
        logger.debug('BankRule {NAME}: preparing to save account {ACCT} reference statements'
                     .format(NAME=self.name, ACCT=self.current_account))
        acct = self.fetch_account(self.current_account)

        record_type = acct.record_type
        record_entry = settings.records.fetch_rule(record_type)

        association_name = acct.association_rule
        association_rule = record_entry.association_rules[association_name]

        ref_df = acct.ref_df.copy()
        try:
            existing_df = acct.load_references(acct.get_table().row_ids(deleted=True))
        except Exception as e:
            mod_win2.popup_error('{MSG} -  see log for details'.format(MSG=e))

            return False

        # Prepare the export reference entries by dropping existing entries that were not changed during the
        # reconciliation
        ref_df.set_index(['RecordID', 'ReferenceID'], inplace=True)
        existing_df.set_index(['RecordID', 'ReferenceID'], inplace=True)
        ref_index = ref_df.index.union(existing_df.index)

        deleted_inds = existing_df.index.difference(ref_df.index)
        print('existing entries that were deleted during the reconciliation:')
        print(deleted_inds)

        ref_df = ref_df.reindex(index=ref_index)
        existing_df = existing_df.reindex(index=ref_index)
        export_df = ref_df.loc[ref_df.compare(existing_df).index]
        print('preparing the export reference dataframe:')
        print(export_df)

        # Prepare the modified reference entries that were deleted
        deleted_df = export_df.loc[deleted_inds].reset_index()
        print('deleted entries are:')
        print(deleted_df)

        # Prepare the modified reference entries that were not deleted
        save_df = export_df.loc[~export_df.index.isin(deleted_inds)].reset_index()
        print('modified entries are:')
        print(save_df)

        # Save references for the account if the account records are the primary records in the reference table
        is_primary = association_rule['Primary']
        if is_primary:
            logger.debug('BankRule {NAME}: preparing account {ACCT} reference statements'
                         .format(NAME=self.name, ACCT=acct.name))
            try:
                statements = record_entry.delete_database_references(deleted_df, acct.association_rule,
                                                                     statements=statements)
            except Exception as e:
                msg = 'failed to prepare the delete statement for the account {ACCT} references - {ERR}' \
                    .format(ACCT=acct.name, ERR=e)
                logger.exception('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                return False

            try:
                statements = record_entry.save_database_references(save_df, acct.association_rule,
                                                                   statements=statements)
            except Exception as e:
                msg = 'failed to prepare the export statement for the account {ACCT} references - {ERR}' \
                    .format(ACCT=acct.name, ERR=e)
                logger.exception('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                return False
            else:
                saved_primary_ids = save_df['RecordID'].tolist()
        else:
            saved_primary_ids = []

        # Iterate over unique reference types to determine if any referenced records of the given type should also have
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

                # Don't save reference entries twice
                sub_df = sub_df[~sub_df['RecordID'].isin(saved_primary_ids)]

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
                try:
                    statements = ref_entry.delete_database_references(sub_df, acct.association_rule,
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
        # success = True

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

        parent (str): parent element, if applicable.

        id (int): GUI element number.

        elements (dict): GUI element keys.

        bindings (dict): GUI event bindings.

        title (str): title of the bank account entry.

        record_type (str): bank account entry database record type.

        association_rule (str): name of the association rule referenced when attempting to find associations between
            account entries.

        import_parameters (list): list of entry data parameters used in the import window.

        table (RecordTable): table storing account record data.

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
        self.elements = {i: '-{NAME}_{ID}_{ELEM}-'.format(NAME=self.name, ID=self.id, ELEM=i) for i in
                         ('Panel', 'AssocPanel', 'Approve', 'Reset', 'Link')}
        self.bindings = {self.elements[i]: i for i in ('Approve', 'Reset', 'Link')}

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

        self.table = mod_elem.RecordTable(name, table_entry)
        self.bindings.update(self.table.bindings)

        table_entry['ActionButtons'] = {}
        self.assoc_table = mod_elem.RecordTable(name, table_entry)
        self.bindings.update(self.assoc_table.bindings)

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
        ref_cols = ['ReferenceID', 'ReferenceDate', 'ReferenceType', 'ReferenceNotes', 'ReferenceWarnings',
                    'IsApproved', 'IsHardLink', 'IsChild', 'IsDeleted']
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
                    if 'ForeignField' not in param_entry:
                        msg = 'BankAccount {NAME}: no foreign field specified for associated column {COL} of ' \
                              'transaction account {ACCT} - setting to {COL}'\
                            .format(NAME=name, ACCT=transaction_acct, COL=assoc_column)
                        logger.warning(msg)

                        param_entry['ForeignField'] = assoc_column

                    try:
                        param_entry['ExpandLevel'] = int(param_entry['ExpandLevel'])
                    except (KeyError, ValueError):
                        param_entry['ExpandLevel'] = 0

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

    def key_lookup(self, component, rev: bool = False):
        """
        Lookup a bank account element's component GUI key using the name of the component element.

        Arguments:
            component (str): GUI component name (or key if rev is True) of the bank account element.

            rev (bool): reverse the element lookup map so that element keys are dictionary keys.
        """
        key_map = self.elements if rev is False else {j: i for i, j in self.elements.items()}
        try:
            key = key_map[component]
        except KeyError:
            msg = 'component {COMP} not found in list of bank account elements'.format(COMP=component)
            logger.warning('BankAccount {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
            print(key_map)
            key = None

        return key

    def bind_keys(self, window):
        """
        Add hotkey bindings to the data element.
        """
        # Bind account and association table hotkeys
        self.table.bind_keys(window)
        self.assoc_table.bind_keys(window)

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

        # Return values
        record_indices = None
        reference_event = False
        link_event = False

        # Run a record table event.
        if event in table_keys:
            tbl_key = table.key_lookup('Element')
            tbl_event = table_keys[event]

            can_open = table.modifiers['open']
            can_edit = table.modifiers['edit']

            # Record was selected for opening
            if tbl_event == 'Load' and can_open:
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
                        level = 1

                        record = table.load_record(index, level=level, savable=False,
                                                   references={association_rule: ref_df})
                        if record is None:
                            msg = 'unable to update references for record at index {IND} - no record was returned' \
                                .format(IND=index)
                            logger.error('DataTable {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                            return {}

                        # Update reference entry values
                        if can_edit:  # only update reference entries if the table is editable
                            # Update record values
                            try:
                                record_values = record.export_values()
                            except Exception as e:
                                msg = 'unable to update row {IND} values'.format(IND=index)
                                logger.exception(
                                    'DataTable {NAME}: {MSG} - {ERR}'.format(NAME=self.name, MSG=msg, ERR=e))
                            else:
                                table.update_row(index, record_values)

                                # Update the reference entry dataframe to reflect changes made to an entry through the
                                # record window
                                ref_values = record.export_associations(association_rule=association_rule)
                                updated_refs = self.update_references(ref_values)

                                if not updated_refs.empty:
                                    reference_event = True

                                self.update_display(window)

            elif tbl_event == 'Approve' and table.enabled('Approve'):
                # Find rows selected by user for approval
                select_row_indices = values[tbl_key]

                # Get the real indices of the selected rows
                indices = table.get_index(select_row_indices)

                # Get record IDs for the selected rows
                record_ids = table.row_ids(indices=indices)

                try:
                    reference_indices = self.approve(record_ids)
                except Exception as e:
                    msg = 'failed to approve records at table indices {INDS}'.format(INDS=indices)
                    logger.error('BankAccount {NAME}: {MSG} - {ERR}'.format(NAME=self.name, MSG=msg, ERR=e))
                else:
                    if len(reference_indices) > 0:
                        reference_event = True

                # Update the status in the records table. This will also update the "is edited" column of the table to
                # indicate that the records at the given indices were edited wherever the new values do not match the
                # old values.
                if 'Approved' in colmap:
                    table.update_column(colmap['Approved'], True, indices=indices)

                # Deselect selected rows
                table.deselect(window)

            elif tbl_event == 'Reset' and table.enabled('Reset'):
                # Find rows selected by user for deletion
                select_row_indices = values[tbl_key]

                # Get the real indices of the selected rows
                indices = table.get_index(select_row_indices)

                # Get record IDs for the selected rows
                record_ids = table.row_ids(indices=indices)

                # Delete references and approval for the selected records
                try:
                    reference_indices = self.reset_references(record_ids, index=False)
                except Exception as e:
                    msg = 'failed to reset record references at table indices {INDS}'.format(INDS=indices)
                    logger.error('BankAccount {NAME}: {MSG} - {ERR}'.format(NAME=self.name, MSG=msg, ERR=e))
                else:
                    if len(reference_indices) > 0:
                        reference_event = True

                # Deselect selected rows
                table.deselect(window)

                # Reset void transaction status
                self.reset_records(indices, index=True)

            elif tbl_event == 'Link' and table.enabled('Link'):
                link_event = True

            # Single-clicked table row(s)
            elif tbl_event == 'Element':
                table.run_event(window, event, values)

                # Get index of the selected rows
                record_indices = table.selected(real=True)

            else:
                table.run_event(window, event, values)

        return {'ReferenceEvent': reference_event, 'Link': link_event, 'RecordIndex': record_indices}

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
        bg_col = mod_const.DEFAULT_BG_COLOR
        pad_frame = mod_const.FRAME_PAD

        # Element sizes
        tbl_width = width - 30
        tbl_height = height * 0.55

        # Layout
        tbl_layout = [[table.layout(tooltip=self.title, size=(tbl_width, tbl_height), padding=(0, 0))]]

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

    def fetch_reference_parameter(self, column, record_ids):
        """
        Fetch reference parameter values at provided record table row indices.
        """
        df = self.ref_df
        if isinstance(record_ids, str):
            record_ids = [record_ids]

        try:
            values = df.loc[df['RecordID'].isin(record_ids), column].tolist()
        except KeyError:
            msg = 'column "{PARAM}" is not a reference entry column'.format(PARAM=column)
            logger.error('BankAccount {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            values = []

        return values

    def _aggregate_references(self):
        """
        Prepare the reference entry dataframe for merging with the records.
        """
        pd.set_option('display.max_columns', None)

        is_numeric_dtype = pd.api.types.is_numeric_dtype
        is_bool_dtype = pd.api.types.is_bool_dtype
        is_datetime_dtype = pd.api.types.is_datetime64_any_dtype
        is_string_dtype = pd.api.types.is_string_dtype

        ref_df = self.ref_df.copy()
        ref_col_map = self.ref_map

        ref_df.set_index('RecordID', inplace=True)

        # Subset reference table columns by the reference map
        ref_df = ref_df[[i for i in ref_col_map]].rename(columns=ref_col_map)
        aggby = {}
        for colname, dtype in ref_df.dtypes.iteritems():
            if is_bool_dtype(dtype) or is_datetime_dtype(dtype):
                aggfunc = 'first'
            elif is_numeric_dtype(dtype):
                aggfunc = 'sum'
            elif is_string_dtype(dtype):
                aggfunc = '; '.join
                ref_df[colname].fillna('', inplace=True)
            else:
                aggfunc = 'sum'

            aggby[colname] = aggfunc

        # Group reference entries with the same record ID
        ref_df = ref_df.groupby(ref_df.index).aggregate(aggby)

        return ref_df

    def merge_records(self):
        """
        Add default reference entries for records without a reference entry.

        Returns:
            df (DataFrame): dataframe of references merged with their corresponding record entries.
        """
        pd.set_option('display.max_columns', None)

        table = self.get_table()
        df = table.data()
        ref_df = self.ref_df.copy()

        df.set_index('RecordID', inplace=True)
        ref_df.set_index('RecordID', inplace=True)

        df_ind = df.index
        ref_ind = ref_df.index
        missing_ind = df_ind.difference(ref_ind)

        missing_df = pd.DataFrame(index=missing_ind)
        ref_df = ref_df.append(missing_df)

        return ref_df.reset_index()

    def merge_references(self, df: pd.DataFrame = None):
        """
        Merge the records table and the reference table on configured reference map columns.

        Arguments:
            df (DataFrame): merge references with the provided records dataframe [Default: use full records dataframe].

        Returns:
            df (DataFrame): dataframe of records merged with their corresponding reference entries.
        """
        pd.set_option('display.max_columns', None)

        table = self.get_table()
        df = table.data() if df is None else df
        ref_df = self._aggregate_references()

        # Reorder the references dataframe to match the order of the records in the records table
        ref_df = ref_df.reindex(index=df['RecordID'].tolist())

        # Update the configured references columns in the records dataframe to be the same as the columns in references
        # dataframe
        for column in ref_df.columns:
            try:
                new_values = ref_df[column].tolist()
            except KeyError:
                new_values = None

            table.update_column(column, new_values)

    def update_references(self, ext_df):
        """
        Update the reference dataframe using an external reference dataframe with overlapping entries.

        Arguments:
            ext_df (DataFrame): external reference entry dataframe that will be used to update the entries of the
                account reference dataframe.
        """
        pd.set_option('display.max_columns', None)
        df = self.ref_df.copy()

        # Drop external reference entries when not also found in the reference entry
        ref_ids = df['ReferenceID'].dropna()
        ref_df = ext_df.loc[ext_df['ReferenceID'].isin(ref_ids)].copy()

        if ref_df.empty:
            logger.debug('BankAccount {NAME}: no references remaining after filtering references that are not shared'
                         .format(NAME=self.name))

        # Delete reference entries that were deleted in the external reference dataframe
        deleted_references = ref_df.loc[ref_df['RecordID'].isna(), 'ReferenceID']
        if not deleted_references.empty:
            ids_to_delete = df.loc[df['ReferenceID'].isin(deleted_references.tolist()), 'RecordID'].tolist()

            self.reset_references(ids_to_delete, index=False)
            self.reset_records(ids_to_delete, index=False)

            ref_df.drop(deleted_references.index, inplace=True)

        # Subset the reference dataframe on the remaining external reference entries
        ref_df.set_index(['RecordID', 'ReferenceID'], inplace=True)
        df.set_index(['RecordID', 'ReferenceID'], inplace=True)

        df = df.reindex(index=ref_df.index)

        ref_df.sort_index(axis=1, inplace=True)
        df.sort_index(axis=1, inplace=True)

        # Compare the reference dataframes and extract the discrepant entries
        diff_df = ref_df.loc[ref_df.compare(df).index]

        # Update the values of the reference entries that were modified in the external reference dataframe
        for index, row in diff_df.iterrows():
            record_id, ref_id = index
            ref_indices = (self.ref_df['RecordID'] == record_id) & (self.ref_df['ReferenceID'] == ref_id)
            self.ref_df.loc[ref_indices, row.index] = row.values

        return diff_df

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
        logger.info('DataTable {TBL}: approving reference entries for records {IDS}'
                    .format(TBL=self.name, IDS=record_ids))
        ref_indices = ref_df.index[ref_df['RecordID'].isin(record_ids)]
        ref_df.loc[ref_indices, ['IsApproved']] = True

        return ref_indices.tolist()

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
            for match_indices in matches:
                record_ind, ref_ind = match_indices

                record_id = bounced.loc[record_ind, 'RecordID']
                ref_id = deposits.loc[ref_ind, 'RecordID']
                match_pair = (record_id, ref_id)
                print('record IDs of the matching bounced check transactions are {} and {}'.format(*match_pair))

                # Insert the reference into the account records reference dataframe
                warning = bc_entry.get('Warning', 'bounced check')

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
            for match_indices in matches:
                record_ind, ref_ind = match_indices

                record_id = deposits.loc[record_ind, 'RecordID']
                ref_id = withdrawals.loc[ref_ind, 'RecordID']
                match_pair = (record_id, ref_id)

                # Insert the reference into the account records reference dataframe
                warning = mp_entry.get('Warning', 'mistaken payment')

                refdate = datetime.datetime.now()
                self.add_reference(record_id, ref_id, record_type, warning=warning, refdate=refdate)
                self.add_reference(ref_id, record_id, record_type, warning=warning, refdate=refdate)

                # Set the transaction code for the bounced cheque
                void_records.extend(list(match_pair))
                df.drop(df[df['RecordID'].isin(match_pair)].index, inplace=True)

        # Update the record tables
        void_inds = table.record_index(void_records)
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
            indices = table.record_index(identifiers)

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
        ref_df.drop(indices, inplace=True)

        return indices

    def add_reference(self, record_id, reference_id, reftype, approved: bool = False, warning: str = None,
                      note: str = None, refdate: datetime.datetime = None):
        """
        Add a record reference to the references dataframe.
        """
        ref_cols = ['RecordID', 'ReferenceID', 'ReferenceDate', 'RecordType', 'ReferenceType', 'ReferenceNotes',
                    'ReferenceWarnings', 'IsApproved',  'IsHardLink', 'IsChild', 'IsDeleted']
        refdate = refdate if refdate is not None else datetime.datetime.now()

        ref_values = pd.Series([record_id, reference_id, refdate, self.record_type, reftype, note,
                                warning, approved, False, False, False], index=ref_cols)
        self.ref_df = self.ref_df.append(ref_values, ignore_index=True)

    def has_reference(self, record_ids):
        """
        Confirm whether an account record is referenced.

        Arguments:
            record_ids (list): list of record IDs to check for references.
        """
        ref_df = self.ref_df
        if isinstance(record_ids, str):
            record_ids = [record_ids]

        references = ref_df.loc[ref_df['RecordID'].isin(record_ids)]

        if references.empty:
            return False
        elif references['ReferenceID'].isna().any():
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

        # Update the display table
        table.update_display(window)

    def load_data(self, params, records: list = None):
        """
        Load record and reference data from the database.
        """
        pd.set_option('display.max_columns', None)

        table = self.get_table()
        id_column = table.id_column

        # Update the record table dataframe with the data imported from the database
        df = self.load_records(params, records=records)

        # Load the record references from the reference table connected with the association rule
        record_ids = df[id_column].tolist()
        self.load_references(record_ids)

        ref_df = self._aggregate_references()

        # Reorder the references dataframe to match the order of the records in the records table
        ref_df = ref_df.reindex(index=df[id_column].tolist())

        # Update the configured references columns in the records dataframe to be the same as the columns in references
        # dataframe
        for tbl_column in ref_df.columns:
            try:
                new_values = ref_df[tbl_column].tolist()
            except KeyError:
                msg = 'missing reference map column {COL} from reference entry dataframe'.format(COL=tbl_column)
                logger.error('BankAccount {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                new_values = None

            df[tbl_column] = new_values

        table.append(df)

    def load_references(self, record_ids):
        """
        Load record references from the database.
        """
        rule_name = self.association_rule
        record_type = self.record_type
        record_entry = settings.records.fetch_rule(record_type)

        # Import reference entries from the database
        try:
            df = record_entry.import_references(record_ids, rule=rule_name)
        except Exception as e:
            msg = 'failed to import references from association rule {RULE}'.format(RULE=rule_name)
            logger.exception('BankAccount {NAME}: {MSG} - {ERR}'.format(NAME=self.name, MSG=msg, ERR=e))

            raise ImportError(msg)

        self.ref_df = df

        return df.copy()

    def load_records(self, parameters, records: list = None):
        """
        Load record and reference data from the database based on the supplied parameter set.

        Arguments:
            parameters (list): list of data parameters to filter the records database table on.

            records (list): also load records in the list of record IDs.

        Returns:
            success (bool): records and references were loaded successfully.
        """
        # pd.set_option('display.max_columns', None)

        record_type = self.record_type
        record_entry = settings.records.fetch_rule(record_type)

        try:
            df = record_entry.import_records(filter_params=parameters, import_rules=self.import_rules)
        except Exception as e:
            msg = 'failed to import data from the database'
            logger.exception('BankAccount {NAME}: {MSG} - {ERR}'.format(NAME=self.name, MSG=msg, ERR=e))

            raise ImportError(msg)

        # Load remaining records not yet loaded using the parameters
        if records:
            imported_ids = df[self.table.id_column].tolist()
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

            df = df.append(loaded_df)

        return df


def search_associations(df, ref_df, rules):
    """
    Find associations between two sets of records using the provided association rules.
    """
    match_cols = ['ReferenceID', 'Source', 'Approved', 'Warning']
    match_df = pd.DataFrame(columns=match_cols)
    for record_id, row in df.iterrows():

        # Attempt to find a match for the record to each of the associated transaction accounts
        matches = pd.DataFrame(columns=ref_df.columns)
        for assoc_acct_name in rules:
            # Subset merged df to include only the association records with the given account name
            assoc_acct_df = ref_df[ref_df['_Account_'] == assoc_acct_name]

            assoc_rules = rules[assoc_acct_name]
            cols = list(assoc_rules)

            # Find exact matches between account record and the associated account records using only the
            # relevant columns
            row_vals = [getattr(row, i) for i in cols]
            acct_matches = assoc_acct_df[assoc_acct_df[cols].eq(row_vals).all(axis=1)]

            matches = matches.append(acct_matches)

        # Check matches and find correct association
        nmatch = matches.shape[0]
        if nmatch == 1:  # found one exact match
            results = matches.iloc[0]
            ref_id = results['_RecordID_']
            source = results['_Account_']

            logger.debug('associating {ACCT} record {REFID} to account record {ID}'
                         .format(ACCT=source, REFID=ref_id, ID=record_id))

            # Remove match from list of unmatched association records
            ref_df.drop(matches.index.tolist()[0], inplace=True)

            # Insert the reference into the matching dataframe
            reference = pd.Series([ref_id, source, True, None], index=match_cols, name=record_id)
            match_df = match_df.append(reference)

        elif nmatch > 1:  # too many matches
            warning = 'found more than one match for account record "{RECORD}"'.format(RECORD=record_id)
            logger.debug('{MSG}'.format(MSG=warning))

            # Match the first of the exact matches
            results = matches.iloc[0]
            ref_id = results['_RecordID_']
            source = results['_Account_']

            logger.debug('associating {ACCT} record {REFID} to account record {ID}'
                         .format(ACCT=source, REFID=ref_id, ID=record_id))

            # Remove match from list of unmatched association records
            ref_df.drop(matches.index.tolist()[0], inplace=True)

            # Insert the reference into the matching dataframe
            reference = pd.Series([ref_id, source, True, warning], index=match_cols, name=record_id)
            match_df = match_df.append(reference)

    return match_df


def search_associations_expanded(df, ref_df, rules):
    """
    Find associations between two sets of records using expanded search options.
    """
    match_cols = ['ReferenceID', 'Source', 'Approved', 'Warning']
    match_df = pd.DataFrame(columns=match_cols)
    for record_id, row in df.iterrows():
        match = expand_search(row, ref_df, rules, expand_level=0)
        if match.empty:
            continue

        source = match['_Account_']
        ref_id = match['_RecordID_']
        warning = match['_Warning_']

        logger.debug('associating {ACCT} record {REF_ID} to account record {ID} from an expanded search'
                     .format(ACCT=source, REF_ID=ref_id, ID=record_id))

        # Remove the found match from the dataframe of unmatched associated account records
        ref_df.drop(match.name, inplace=True)

        # Insert the reference into the matching dataframe
        reference = pd.Series([ref_id, source, False, warning], index=match_cols, name=record_id)
        match_df = match_df.append(reference)

    return match_df


def expand_search(row, ref_df, ref_map, comp_df=None, expand_level: int = 0, closest_match: list = None):
    """
    Attempt to find matching records using iterative expansion of reference columns.

    Arguments:
        row (Series): record entry of interest.

        ref_df (DataFrame): table of record entries to search the record entry against.

        ref_map (dict): transaction associations.

        comp_df (DataFrame): optional table of already performed comparisons.

        expand_level (int): start the search for matching entries at the given expansion level [Default: 0].

        closest_match (list): use these columns to find the closest match to the record entry.
    """
    results = pd.Series()
    ref_df['_Warning_'] = None
    row_index = row.name

    matches = pd.DataFrame(columns=ref_df.columns)
    expanded_cols = []
    if not isinstance(comp_df, pd.DataFrame):
        comp_df = ref_df.copy()
        run_comparison = True
    else:
        run_comparison = False

    for assoc_acct_name in ref_map:
        msg = 'searching for matches between record {ROW} and association {ASSOC} entries' \
            .format(ROW=row_index, ASSOC=assoc_acct_name)
        logger.debug(msg)

        # Subset merged df to include only the association records with the given account name
        assoc_df = ref_df[ref_df['_Account_'] == assoc_acct_name]
        if assoc_df.empty:
            msg = 'no entries in association {ASSOC} to compare against record {ROW}' \
                .format(ASSOC=assoc_acct_name, ROW=row_index)
            logger.debug(msg)

            continue

        assoc_rules = ref_map[assoc_acct_name]
        failed_indices = set()
        for col in assoc_rules:
            rule_entry = assoc_rules[col]

            # Compare reference column values to the record columns values and store in a comparison table
            col_values = assoc_df[col].copy()
            if run_comparison:
                pm = bool(int(rule_entry.get('PatternMatching', 0)))
                ignore = rule_entry.get('IgnoreCharacters', None)
                row_value = getattr(row, col)
                col_match = compare_record_values(row_value, col_values, match_pattern=pm, ignore_chars=ignore)

                comp_df.loc[assoc_df.index, col] = col_match
            else:
                col_match = comp_df.loc[assoc_df.index, col].fillna(False).astype(bool)

            # Select the value fields that will be used to compare records. All fields with expanded search level
            # greater than current iteration level will be left flexible
            param_level = rule_entry.get('ExpandLevel', 0)
            if param_level > expand_level:  # comparison field has an expand level higher than current search level
                if col not in expanded_cols:
                    expanded_cols.append(col)
            else:
                not_matched = ~col_match
                col_failed = col_values[not_matched.tolist()].index.tolist()
                failed_indices.update(col_failed)

        # Find exact matches between account record and the associated account records using relevant cols
        acct_matches = assoc_df[~assoc_df.index.isin(failed_indices)]
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

                    param_level = rule_entry.get('ExpandLevel', 0)
                    if param_level == expand_level:
                        if col not in expanded_cols:
                            expanded_cols.append(col)

            msg = 'no matches found for record {ROW} at expanded search level {L} - returning to ' \
                  'previous search level matches to find for the closest match on columns {COLS}' \
                .format(ROW=row_index, L=expand_level, COLS=expanded_cols)
            logger.info(msg)
            results = expand_search(row, ref_df, ref_map, comp_df=comp_df, expand_level=prev_level,
                                    closest_match=expanded_cols)
        else:
            msg = 'no matches found for record {ROW} from an expanded search'.format(ROW=row_index)
            logger.warning(msg)

    elif nmatch == 1:  # potential match, add with a warning
        results = matches.iloc[0].copy()

        # Determine appropriate warning for the expanded search
        acct_name = results['_Account_']
        assoc_rules = ref_map[acct_name]

        warning = []
        for column in expanded_cols:
            try:
                rule_entry = assoc_rules[column]
            except KeyError:
                msg = 'column {COL} does not have a configured association parameter for association account {ACCT}'\
                    .format(COL=column, ACCT=acct_name)
                logger.warning(msg)
                continue

            if not comp_df.loc[results.name, column]:  # values do not match
                alt_warn = 'values for expanded column {COL} do not match'.format(COL=column)
                col_warning = rule_entry.get('Warning', alt_warn)
                warning.append('- {}'.format(col_warning))

        if len(warning) > 0:
            warning.insert(0, 'Warning:')
            results['_Warning_'] = '\n'.join(warning)

    elif nmatch > 1:  # need to increase specificity to get the best match by adding more comparison fields
        msg = 'found more than one expanded match for record {ROW} at search level {L} - ' \
              'searching for the best match'.format(ROW=row_index, L=expand_level)
        logger.warning(msg)

        # Attempt to find the best matching record
        if not closest_match:  # one or more matches were found in previous iteration
            # Find the best match by iterative field inclusion
            msg = 'attempting to find the best match for row {ROW} through iterative field inclusion' \
                .format(ROW=row_index)
            logger.debug(msg)

            results = expand_search(row, matches, ref_map, comp_df=comp_df, expand_level=expand_level + 1)
        else:  # zero matches were found in the previous iteration
            # Find the best match by searching for nearest like value on the closest match fields
            msg = 'attempting to find the best match for record {ROW} by searching for nearest value on fields ' \
                  '{FIELDS}'.format(ROW=row_index, FIELDS=closest_match)
            logger.debug(msg)

            results = nearest_match(row, matches, closest_match)
            if results.empty:
                msg = 'multiple matches found for record {ROW} but enough specificity in the data ' \
                      'to narrow it down to one match'.format(ROW=row_index)
                logger.warning(msg)
            else:
                # Determine appropriate warning for the nearest match search
                acct_name = results['_Account_']
                assoc_rules = ref_map[acct_name]

                warning = []
                for closest_col in closest_match:
                    try:
                        rule_entry = assoc_rules[closest_col]
                    except KeyError:
                        msg = 'column {COL} does not have a configured association parameter for association account ' \
                              '{ACCT}'.format(COL=closest_col, ACCT=acct_name)
                        logger.warning(msg)
                        continue

                    alt_warning = 'association is the result of searching for the closest match on "{}"' \
                        .format(closest_col)
                    col_warning = rule_entry.get('Warning2', alt_warning)
                    warning.append('- {}'.format(col_warning))

                if len(warning) > 0:
                    warning.insert(0, 'Warning:')
                    results['_Warning_'] = '\n'.join(warning)

    return results


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

    min_diff = diffs.abs().idxmin()
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


def compare_record_values(value, ref_values, match_pattern: bool = False, ignore_chars: list = None):
    """
    Find matches between a record value and the values of a set of references.
    """
    is_string_dtype = pd.api.types.is_string_dtype
    try:
        ign = set(ignore_chars)
    except TypeError:
        ign = None

    if ign and is_string_dtype(ref_values):
        ref_values = ref_values.str.replace('|'.join(ign), '', regex=True)
        value = ''.join([c for c in str(value) if c not in ign])

    if match_pattern and is_string_dtype(ref_values):
        col_match = ref_values.str.contains(str(value))
    else:
        col_match = ref_values.eq(value)

    return col_match

