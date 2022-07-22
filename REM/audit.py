"""
REM transaction audit configuration classes and functions. Includes audit rules, audit objects, and rule parameters.
"""
import datetime
import re
from random import randint

import PySimpleGUI as sg
import pandas as pd

import REM.constants as mod_const
import REM.data_manipulation as mod_dm
import REM.elements as mod_elem
import REM.layouts as mod_lo
import REM.records as mod_records
import REM.secondary as mod_win2
from REM.client import logger, settings, user


class AuditRule:
    """
    Class to store and manage a configured audit rule.

    Attributes:
        name (str): audit rule name.

        id (int): GUI element number.

        element_key (str): panel element key.

        elements (dict): GUI element keys.

        bindings (dict): GUI event bindings.

        menu_title (str): menu title for the audit rule.

        menu_flags (dict): submenu flags that change the initial behavior of the rule.

        permissions (str): permissions required to view the audit. Default: user.

        parameters (list): list of rule parameters.

        transactions (list): list of audit transactions.

        record_data (dict): audit record data.
        
        exists (bool): audit record already exists for the provided parameters [Default: False].
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
        self.elements = {i: '-{NAME}_{ID}_{ELEM}-'.format(NAME=self.name, ID=self.id, ELEM=i) for i in
                         ('Cancel', 'Start', 'Save', 'TG', 'TransactionPanel', 'Panels', 'Title', 'Frame', 'Header',
                          'Database')}

        self.bindings = {self.elements[i]: i for i in ('Cancel', 'Start', 'Save', 'TG', 'Database')}

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

        # self.parameters = []
        # try:
        #    params = entry['RuleParameters']
        # except KeyError:
        #    msg = 'missing required parameter "RuleParameters"'
        #    logger.error('AuditRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

        #    raise AttributeError(msg)

        # for param_name in params:
        #    param_entry = params[param_name]
        #    try:
        #        param = mod_param.initialize_parameter(param_name, param_entry)
        #    except Exception as e:
        #        logger.error('AuditRule {NAME}: {MSG}'.format(NAME=self.name, MSG=e))

        #        raise AttributeError(e)

        #    self.parameters.append(param)
        #    self.bindings.update(param.bindings)

        self.parameters = []
        try:
            self._param_def = entry['RuleParameters']
        except KeyError:
            msg = 'missing required parameter "RuleParameters"'
            logger.error('AuditRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            raise AttributeError(msg)

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
            self.bindings.update(transaction.bindings)

        try:
            record_entry = entry['Record']
        except KeyError:
            msg = 'missing required parameter "Record"'
            logger.error('AuditRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            raise AttributeError(msg)
        else:
            try:
                self.record_type = record_entry['RecordType']
            except KeyError:
                msg = 'missing required "Record" parameter "RecordType"'
                logger.error('AuditRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                raise AttributeError(msg)

            try:
                self.summary_mapping = record_entry['SummaryMapping']
            except KeyError:
                self.summary_mapping = {}

            try:
                self.record_mapping = record_entry['RecordMapping']
            except KeyError:
                self.record_mapping = {}

        self.record_data = {}

        self.in_progress = False

        self.panel_keys = {0: self.key_lookup('TransactionPanel')}
        self.current_panel = 0
        self.exists = False

    def key_lookup(self, component, rev: bool = False):
        """
        Lookup an audit rule element's component GUI key using the name of the component element.

        Arguments:
            component (str): GUI component name (or key if rev is True) of the audit rule element.

            rev (bool): reverse the element lookup map so that element keys are dictionary keys.
        """
        key_map = self.elements if rev is False else {j: i for i, j in self.elements.items()}
        try:
            key = key_map[component]
        except KeyError:
            msg = 'component {COMP} not found in list of audit rule elements'.format(COMP=component)
            logger.warning('AuditRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
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
        logger.debug('AuditRule {NAME}: binding panel element hotkeys'.format(NAME=self.name))

        # Bind transaction table hotkeys
        for transaction_tab in self.transactions:
            transaction_tab.table.bind_keys(window)

    def fetch_tab(self, identifier, by_key: bool = True):
        """
        Fetch a transaction by its tab key.
        """
        tabs = self.transactions
        if by_key:
            identifiers = [i.key_lookup('Tab') for i in tabs]
        else:
            identifiers = [i.name for i in tabs]

        if identifier in identifiers:
            index = identifiers.index(identifier)
            tab = tabs[index]
        else:
            raise KeyError('identifier {KEY} not found in the set of tab identifiers'.format(KEY=identifier))

        return tab

    def fetch_parameter(self, identifier, by_key: bool = False):
        """
        Fetch an audit parameter by name or event key.
        """
        parameters = self.parameters

        if by_key is True:
            match = re.match(r'-(.*?)-', identifier)
            if not match:
                raise KeyError('unknown format provided for element identifier {ELEM}'.format(ELEM=identifier))
            identifier = match.group(0)  # identifier returned if match
            element_key = match.group(1)  # element key part of the identifier after removing any binding

            element_type = element_key.split('_')[-1]
            element_names = []
            for parameter in parameters:
                try:
                    element_name = parameter.key_lookup(element_type)
                except KeyError:
                    element_name = None

                element_names.append(element_name)
        else:
            element_names = [i.name for i in parameters]

        if identifier in element_names:
            index = element_names.index(identifier)
            parameter = parameters[index]
        else:
            raise KeyError('element {ELEM} not found in list of {NAME} data elements'
                           .format(ELEM=identifier, NAME=self.name))

        return parameter

    def run_event(self, window, event, values):
        """
        Run a transaction audit event.
        """
        current_rule = self.name

        start_key = self.key_lookup('Start')
        save_key = self.key_lookup('Save')
        tg_key = self.key_lookup('TG')
        db_key = self.key_lookup('Database')

        if event == tg_key:
            self.set_tab_focus(window)

            return current_rule

        if event == db_key:
            database = values[db_key]
            settings.edit_attribute('dbname', database)

            return current_rule

        # Run a transaction event
        tab_keys = [i for j in self.transactions for i in j.bindings]
        if event in tab_keys:
            # Fetch the current transaction tab
            tab_key = window[tg_key].Get()
            try:
                tab = self.fetch_tab(tab_key)
            except KeyError:
                logger.exception('AuditRule {NAME}: unable to find the transaction associated with tab key "{KEY}"'
                                 .format(NAME=self.name, KEY=tab_key))
            else:
                # Run the tab event
                event_results = tab.run_event(window, event, values)

                # Enable the next tab if an audit event was successful
                if event_results['AuditEvent']:
                    if not event_results['Success']:
                        msg = 'auditing of transaction {TITLE} failed - see log for details'.format(TITLE=tab.title)
                        mod_win2.popup_error(msg)

                        return current_rule

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

                    # Enable the finalize button when an audit has been run on all transactions.
                    if next_index == final_index:
                        # Verify that the user has the right permissions to create an audit
                        if not user.check_permission(self.permissions['create']):
                            msg = '"{UID}" does not have "create" permissions for the audit panel. An audit record ' \
                                  'cannot be created without this permission. Please contact the administrator if ' \
                                  'you suspect that this is in error'.format(UID=user.uid)
                            logger.warning('AuditRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
                            mod_win2.popup_error('warning - {MSG}'.format(MSG=msg))
                        else:
                            logger.info('AuditRule {NAME}: all transaction audits have been performed - preparing the '
                                        'audit record'.format(NAME=self.name))
                            window[save_key].update(disabled=False)
                            window[save_key].metadata['disabled'] = False

            return current_rule

        # Run an audit rule panel event
        try:
            rule_event = self.bindings[event]
        except KeyError:
            rule_event = None

        # Cancel button pressed
        if rule_event == 'Cancel':
            # Check if reconciliation is currently in progress
            if self.in_progress is True:
                msg = 'Transaction audit is currently in progress. Are you sure you would like to quit without saving?'
                selection = mod_win2.popup_confirm(msg)

                if selection == 'OK':
                    # Reset the rule and update the panel
                    current_rule = self.reset_rule(window, current=True)
            else:
                current_rule = self.reset_rule(window, current=False)

        # Start button was pressed. Will open parameter settings window for user to input parameter values,
        # then load the relevant account record data
        elif rule_event == 'Start' and not window[start_key].metadata['disabled']:
            # Get the parameter settings
            param_def = {self.menu_title: self._param_def}
            section_params = mod_win2.parameter_window(param_def, title=self.menu_title)

            # Load data from the database
            if section_params:  # parameters were saved (selection not cancelled)
                params = section_params[self.menu_title]

                window[start_key].update(disabled=True)
                window[start_key].metadata['disabled'] = True

                # Verify that the audit has not already been performed with these parameters
                audit_exists = self.load_record(params)
                if audit_exists is True:
                    if user.check_permission(self.permissions['edit']) is False:
                        msg = 'Additional permissions are required to edit an existing audit.'
                        logger.warning('AuditRule {NAME}: audit initialization failed - {MSG}'
                                       .format(NAME=self.name, MSG=msg))
                        mod_win2.popup_error(msg)
                        current_rule = self.reset_rule(window, current=True)

                        return current_rule
                    else:
                        msg = 'An audit has already been performed using these parameters. Would you like to edit ' \
                              'the existing audit?'
                        user_input = mod_win2.popup_confirm(msg)
                        if not user_input == 'OK':
                            current_rule = self.reset_rule(window, current=True)

                            return current_rule

                # Load the transaction records
                record_id = self.record_data['RecordID']
                transactions = self.transactions
                for transaction_tab in transactions:
                    tab_key = transaction_tab.key_lookup('Tab')
                    tab_keys.append(tab_key)

                    # Import transaction data from the database
                    try:
                        transaction_tab.load_data(params, audit_id=record_id)
                    except ImportError as e:
                        msg = 'failed to initialize the audit transactions'
                        logger.error('AuditRule {NAME}: {MSG} - {ERR}'.format(NAME=self.name, MSG=msg, ERR=e))
                        mod_win2.popup_error('{MSG} - see log for details'.format(MSG=msg))
                        current_rule = self.reset_rule(window, current=True)

                        return current_rule

                    # Enable table element events
                    transaction_tab.table.enable(window)

                    # Update the tab table display
                    transaction_tab.table.update_display(window)

                    # Update tab ID components
                    transaction_tab.update_id_components()

                param_str = ', '.join(['{}={}'.format(i.name, i.value) for i in params])
                logger.info('AuditRule {NAME}: transaction audit in progress with parameters {PARAMS}'
                            .format(NAME=self.name, PARAMS=param_str))
                self.in_progress = True

                #for transaction_tab in transactions:
                    # Enable table element events
                #    transaction_tab.table.enable(window)

                    # Update the tab table display
                #    transaction_tab.table.update_display(window)

                    # Update tab ID components
                #    transaction_tab.update_id_components()

                self.set_tab_focus(window)

        # Save results of the audit
        elif rule_event == 'Save':
            # Create audit record using data from the transaction audits
            db_record = settings.records.fetch_rule(self.record_type)
            record = mod_records.DatabaseRecord(self.record_type, db_record.record_layout, level=0)

            # Prepare the record data for audit record initialization
            mapping = {}
            for field in self.record_data:
                mapping[field] = self.record_data[field]

            # Map transaction table summaries to audit record variables
            mapping = self.map_summary(mapping=mapping)

            # Map transaction records to audit record components
            mapping = self.map_transactions(mapping=mapping)

            # Combine the reference entries of all the transaction tables to pass to the audit record
            refs = {}
            for transaction_tab in self.transactions:
                assoc_type = transaction_tab.association_type
                ref_df = transaction_tab.table.references.data(reference=True, include_state=True)
                ref_df = ref_df.append(transaction_tab.table.references.data(deleted=True, added=False, reference=True,
                                                                             include_state=True),
                                       ignore_index=True)
                if assoc_type in refs:
                    refs[assoc_type] = refs[assoc_type].append(ref_df, ignore_index=True)
                else:
                    refs[assoc_type] = ref_df

            # Initialize the audit record elements
            record.initialize(mapping, new=False, references=refs)

            # Open the audit record in the record window
            record = mod_win2.record_window(record, modify_database=False)

            if record is not None:  # audit accepted by the user
                # Get output file from user
                filename_params = [record.record_id(display=True)]
                for param in self.parameters:
                    filename_params.append(param.format_display())
                default_filename = '_'.join(filename_params)
                outfile = sg.popup_get_file('', title='Save Report As', default_path=default_filename, save_as=True,
                                            default_extension='pdf', no_window=True,
                                            file_types=(('PDF - Portable Document Format', '*.pdf'),))

                if not outfile:
                    msg = 'Please select an output file before continuing'
                    mod_win2.popup_error(msg)

                    return current_rule

                # Save the audit record and audit report
                try:
                    save_status = record.save(save_all=True)
                except Exception as e:
                    msg = 'database save failed - {ERR}'.format(ERR=e)
                    mod_win2.popup_error(msg)

                    return current_rule
                else:
                    if save_status is False:
                        msg = 'Database save failed'
                        mod_win2.popup_error(msg)

                        return current_rule

                try:
                    report_status = record.save_report(outfile)
                except Exception as e:
                    msg = 'failed to save the audit report to {FILE}'.format(FILE=outfile)
                    logger.exception('AuditRule {NAME}: {MSG} - {ERR}'.format(NAME=self.name, MSG=msg, ERR=e))
                    mod_win2.popup_error('{MSG} - see log for details'.format(MSG=msg))
                else:
                    if report_status is False:
                        msg = 'failed to save the audit report to {FILE}'.format(FILE=outfile)
                        mod_win2.popup_error('{MSG} - see log for details'.format(MSG=msg))
                    else:
                        msg = 'audit record was successfully saved to the database'
                        logger.info('AuditRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
                        mod_win2.popup_notice(msg)

                # Reset rule elements
                current_rule = self.reset_rule(window, current=True)

            else:  # user canceled audit creation
                # Reset references for the transaction records
                for transaction_tab in self.transactions:
                    trans_table = transaction_tab.table
                    trans_table.references.reset()
                    trans_table.import_references()

        return current_rule

    def set_tab_focus(self, window):
        """
        Set the window focus on the current transaction table.
        """
        tg_key = self.key_lookup('TG')
        tab_key = window[tg_key].Get()
        try:
            tab = self.fetch_tab(tab_key)
        except KeyError:
            logger.error('AuditRule {NAME}: unable to find the audit record associated with tab key "{KEY}"'
                         .format(NAME=self.name, KEY=tab_key))
        else:
            window[tab.table.key_lookup('Element')].set_focus()

    def layout(self, size):
        """
        Generate a GUI layout for the audit rule.
        """
        width, height = size

        # Element parameters
        bg_col = mod_const.DEFAULT_BG_COLOR
        header_col = mod_const.HEADER_COLOR
        inactive_col = mod_const.DISABLED_BG_COLOR
        text_col = mod_const.DEFAULT_TEXT_COLOR
        select_col = mod_const.SELECTED_TEXT_COLOR

        font_h = mod_const.HEADING_FONT
        param_font = mod_const.XX_FONT

        pad_el = mod_const.ELEM_PAD
        pad_v = mod_const.VERT_PAD
        pad_frame = mod_const.FRAME_PAD

        # Rule parameters
        db_key = self.key_lookup('Database')
        db_size = (max([len(i) for i in settings.alt_dbs]), 1)

        # Panel component size
        title_w, title_h = (mod_const.TITLE_WIDTH, mod_const.TITLE_HEIGHT)
        hbar_h = 2 + pad_v * 2  # horizontal bar with top/bottom padding
        bttn_h = mod_const.BTTN_HEIGHT  # height of the panel navigation buttons
        header_h = 52  # height of the parameter bar

        frame_w = width - pad_frame * 2  # layout width minus audit panel left/right padding
        frame_h = height - title_h - bttn_h  # layout height minus the title bar and buttons height

        tab_w = frame_w  # same as the frame
        tab_h = frame_h - header_h - hbar_h  # frame height minus header and padding

        # Layout elements

        # Title
        panel_title = 'Transaction Audit: {}'.format(self.menu_title)
        title_key = self.key_lookup('Title')
        title_layout = sg.Col([[sg.Canvas(size=(0, title_h), background_color=header_col),
                                sg.Text(panel_title, pad=(pad_frame, pad_frame), font=font_h,
                                        background_color=header_col)]],
                              key=title_key, size=(title_w, title_h), background_color=header_col,
                              vertical_alignment='c', element_justification='l', justification='l', expand_x=True)

        # Panel header
        param_key = self.key_lookup('Start')
        header_key = self.key_lookup('Header')
        header_layout = sg.Col([[sg.Canvas(size=(0, header_h), background_color=bg_col),
                                 sg.Combo(settings.alt_dbs, default_value=settings.dbname, key=db_key, size=db_size,
                                          pad=((0, pad_el * 2), 0), font=param_font, text_color=text_col,
                                          background_color=bg_col, enable_events=True, tooltip='Record database'),
                                 sg.Button('', key=param_key, image_data=mod_const.SELECT_PARAM_ICON,
                                           image_size=(28, 28), button_color=(text_col, bg_col), disabled=True,
                                           metadata={'disabled': False}, tooltip='Parameter selection')
                                 ]],
                               key=header_key, background_color=bg_col, expand_x=True)

        # Panel tab layouts
        transaction_tabs = []
        for i, tab in enumerate(self.transactions):
            visibility = True if i == 0 else False
            transaction_tabs.append(tab.layout((tab_w, tab_h), visible=visibility))

        tg_key = self.key_lookup('TG')
        tg_layout = [sg.TabGroup([transaction_tabs], key=tg_key, pad=(0, 0), enable_events=True,
                                 tab_background_color=inactive_col, selected_title_color=select_col,
                                 title_color=text_col, selected_background_color=bg_col, background_color=bg_col)]

        tpanel_key = self.key_lookup('TransactionPanel')
        transaction_layout = sg.Col([tg_layout], key=tpanel_key, pad=(0, 0), background_color=bg_col,
                                    vertical_alignment='t', visible=True, expand_y=True, expand_x=True)

        # Panel layout
        panels = [transaction_layout]

        panel_key = self.key_lookup('Panels')
        panel_layout = sg.Pane(panels, key=panel_key, orientation='horizontal', background_color=bg_col,
                               show_handle=False, border_width=0, relief='flat')

        # Standard elements
        cancel_key = self.key_lookup('Cancel')
        save_key = self.key_lookup('Save')
        bttn_h = mod_const.BTTN_HEIGHT
        bttn_layout = sg.Col([
            [sg.Canvas(size=(0, bttn_h)),
             mod_lo.nav_bttn('', key=cancel_key, image_data=mod_const.CANCEL_ICON, pad=((0, pad_el), 0), disabled=False,
                             tooltip='Return to home screen'),
             mod_lo.nav_bttn('', key=save_key, image_data=mod_const.SAVE_ICON, pad=(0, 0), disabled=True,
                             tooltip='Save results', metadata={'disabled': True})
             ]], vertical_alignment='c', element_justification='c', expand_x=True)

        frame_key = self.key_lookup('Frame')
        frame_layout = sg.Col([[header_layout],
                               [sg.HorizontalSeparator(pad=(0, (0, pad_v)), color=mod_const.HEADER_COLOR)],
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

        # Resize transaction tabs
        transactions = self.transactions
        for transaction in transactions:
            transaction.resize_elements(window, size=(tab_w, tab_h))

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
        window[panel_key].update(visible=False)
        window['-HOME-'].update(visible=True)

        # Reset "action" elements to default
        start_key = self.key_lookup('Start')
        window[start_key].update(disabled=False)
        window[start_key].metadata['disabled'] = False

        save_key = self.key_lookup('Save')
        window[save_key].update(disabled=True)
        window[save_key].metadata['disabled'] = True

        # Switch to first tab in each panel
        tg_key = self.key_lookup('TG')
        window[tg_key].Widget.select(0)

        # Reset rule parameters.
        self.parameters = []

        # Reset the audit record
        self.record_data = {}

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
            window[current_key].update(visible=True)

            return self.name
        else:
            return None

    def load_record(self, params):
        """
        Load previous audit (if exists) and IDs from the program database.

        Returns:
            success (bool): record importing was successful.
        """
        # Prepare the database query statement
        record_type = self.record_type
        record_entry = settings.records.fetch_rule(record_type)
        logger.info('AuditRecord {NAME}: attempting to load an existing audit record'.format(NAME=record_type))

        # Import record from database
        exists = False

        try:
            import_df = record_entry.import_records(filter_params=params)
        except Exception as e:
            mod_win2.popup_error('Attempt to import data from the database failed. Use the debug window for more '
                                 'information')
            raise IOError('failed to import data from the database for audit record of type {NAME} - {ERR}'
                          .format(NAME=record_type, ERR=e))
        else:
            if not import_df.empty:  # Audit record already exists in database for the chosen parameters
                msg = 'AuditRecord {NAME}: an audit record already exists for the chosen parameters' \
                    .format(NAME=record_type)
                logger.info(msg)

                audit_record = import_df.iloc[0]
                self.record_data = audit_record.to_dict()

                exists = True
            else:  # audit has not been performed yet
                logger.info('AuditRecord {NAME}: no existing audit record for the supplied parameters ... '
                            'creating a new record'.format(NAME=record_type))

                # Prepare a new audit record
                param_types = [i.dtype for i in params]
                try:
                    date_index = param_types.index('date')
                except IndexError:
                    raise AttributeError('failed to create record - audit {NAME} is missing the date parameter'
                                         .format(NAME=record_type))

                # Create new record
                record_date = params[date_index].value
                self.record_data['RecordDate'] = record_date
                record_id = record_entry.create_record_ids(record_date, offset=settings.get_date_offset())
                if not record_id:
                    raise IOError('failed to create record - unable to create record ID for the audit record of type '
                                  '{NAME}'.format(NAME=record_type))

                self.record_data['RecordID'] = record_id

                for param in params:
                    self.record_data[param.name] = param.value

                self.record_data[settings.creator_code] = user.uid
                self.record_data[settings.creation_date] = datetime.datetime.now()

                self.parameters = params

        self.exists = exists

        return exists

    def map_summary(self, mapping: dict = None):
        """
        Populate the audit record elements with transaction summary values.
        """
        # Store transaction table summaries for mapping
        mapping = {} if mapping is None else mapping

        summary_map = {}
        for tab in self.transactions:
            tab_name = tab.name
            summary = tab.table.summarize()
            for summary_column in summary:
                summary_value = summary[summary_column]
                summary_map['{TBL}.{COL}'.format(TBL=tab_name, COL=summary_column)] = summary_value

        logger.debug('AuditRule {NAME}: mapping transaction summaries to audit record elements'
                     .format(NAME=self.name))

        # Map audit totals columns to transaction table summaries
        mapping_columns = self.summary_mapping
        for column in mapping_columns:
            mapper = mapping_columns[column]
            try:
                summary_total = mod_dm.evaluate_operation(summary_map, mapper)
            except Exception as e:
                logger.warning('AuditRule {NAME}: failed to evaluate summary totals - {ERR}'
                               .format(NAME=self.name, ERR=e))
                summary_total = 0

            logger.debug('AuditRule {NAME}: adding {SUMM} to column {COL}'
                         .format(NAME=self.name, SUMM=summary_total, COL=column))

            mapping[column] = summary_total

        return mapping

    def map_transactions(self, mapping: dict = None):
        """
        Map transaction records from the audit to the audit accounting records.

        Returns:
            results (dict): dictionary containing component dataframes of mapped transactions.
        """
        pd.set_option('display.max_columns', None)
        logger.debug('AuditRule {NAME}: creating component records from the transaction records'
                     .format(NAME=self.name))

        audit_id = self.record_data['RecordID']

        # Map transaction data to transaction records
        record_mapping = self.record_mapping
        mapping = {} if mapping is None else mapping
        for component_name in record_mapping:
            dest_entry = record_mapping[component_name]

            comp_df = pd.DataFrame()

            transactions = dest_entry['Transactions']
            for transaction in transactions:
                subsets = transactions[transaction]

                try:
                    tab = self.fetch_tab(transaction, by_key=False)
                except KeyError:
                    logger.warning('AuditRule {NAME}: failed to map transactions from transaction table {TBL} to '
                                   'audit record element {COMP} - unknown transaction table {TBL}'
                                   .format(NAME=self.name, TBL=transaction, COMP=component_name))
                    continue

                table = tab.table

                # Add transaction records to the audit record destination element
                for subset_rule in subsets:
                    rule_entry = subsets[subset_rule]

                    try:
                        column_map = rule_entry['ColumnMapping']
                    except KeyError:
                        logger.warning('AuditRule {NAME}: failed to map transactions from transaction table {TBL} to '
                                       'audit record element {DEST} - no data fields were selected for mapping'
                                       .format(NAME=self.name, TBL=transaction, DEST=component_name))
                        continue

                    dest_cols = [i for i in column_map]

                    try:
                        subset_rule = rule_entry['Subset']
                    except KeyError:
                        add_df = table.data()
                    else:
                        add_df = table.subset(subset_rule)

                    if add_df.empty:
                        logger.debug('AuditRule {NAME}: no records remaining from transaction table {REF} to add '
                                     'to audit record element {DEST} based on rule {RULE}'
                                     .format(NAME=self.name, REF=transaction, DEST=component_name, RULE=subset_rule))
                        continue

                    # Create references for the records

                    # Find any records that are already referenced
                    record_ids = add_df[table.id_column].tolist()
                    records_w_refs = table.has_reference(record_ids)

                    # Remove records that are already referenced from the add dataframe
                    if len(records_w_refs) > 0:
                        msg = '{NUM} {TYPE} records were found to already be associated with an audit - these ' \
                              'records will not be included in this current audit ({RECORDS})' \
                            .format(NUM=len(records_w_refs), TYPE=tab.name, RECORDS=records_w_refs)
                        mod_win2.popup_notice(msg)
                        logger.warning('AuditRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                        add_df = add_df[~add_df[table.id_column].isin(records_w_refs)]

                    # Add references for the remaining records to the references data
                    records_wo_refs = [i for i in record_ids if i not in records_w_refs]
                    print('approved records without current associations:')
                    print(records_wo_refs)
                    for record_id in records_wo_refs:
                        print('adding self reference for record {}'.format(record_id))
                        table.add_reference(record_id, audit_id, self.record_type, approved=True)

                    # Prepare the transaction records
                    add_df = add_df[dest_cols].rename(columns=column_map)

                    # Set defaults, if applicable
                    if 'Defaults' in rule_entry:
                        default_rules = rule_entry['Defaults']

                        for default_col in default_rules:
                            default_value = default_rules[default_col]

                            add_df[default_col] = default_value

                    # Add record to the components table
                    comp_df = comp_df.append(add_df, ignore_index=True)

            # Remove NA columns - required when merging
            comp_df = comp_df[comp_df.columns[~comp_df.isna().all()]]

            # Merge records, if applicable
            if 'Merge' in dest_entry:
                merge_on = [i for i in comp_df.columns if i not in dest_entry['Merge']]
                logger.debug('AuditRule {NAME}: merging new audit record element {DEST} components on columns {COLS}'
                             .format(NAME=self.name, DEST=component_name, COLS=merge_on))
                comp_df = comp_df.groupby(merge_on).sum().reset_index()

            # Add transaction records to the set of transaction records that will get mapped to the audit component
            # records
            logger.debug('AuditRule {NAME}: creating audit record element {DEST} components from transaction records'
                         .format(NAME=self.name, DEST=component_name))
            if not comp_df.empty:
                mapping[component_name] = comp_df

        return mapping

    def map_transactions_old(self, record):
        """
        Map transaction records from the audit to the audit accounting records.

        Arguments:
            record (DatabaseRecord): audit record.
        """
        pd.set_option('display.max_columns', None)
        logger.debug('AuditRule {NAME}: creating component records from the transaction records'
                     .format(NAME=self.name))

        audit_id = self.record_data['RecordID']

        # Map transaction data to transaction records
        record_mapping = self.record_mapping
        for destination in record_mapping:
            dest_entry = record_mapping[destination]

            try:
                dest_element = record.fetch_element(destination)
            except KeyError:
                logger.warning('AuditRule {NAME}: failed to map transactions for destination {COMP} - {COMP} is not '
                               'an audit record element'.format(NAME=self.name, COMP=destination))
                continue
            else:
                if not dest_element.is_type('component'):
                    logger.warning('AuditRule {NAME}: failed to map transactions for destination {COMP} - '
                                   'audit record element {COMP} must be an element of type "component_table"'
                                   .format(NAME=self.name, COMP=destination))
                    continue

            header = dest_element.columns
            comp_df = pd.DataFrame(columns=header)

            transactions = dest_entry['Transactions']
            for transaction in transactions:
                subsets = transactions[transaction]

                try:
                    tab = self.fetch_tab(transaction, by_key=False)
                except KeyError:
                    logger.warning('AuditRule {NAME}: failed to map transactions from transaction table {TBL} to '
                                   'audit record element {COMP} - unknown transaction table {TBL}'
                                   .format(NAME=self.name, TBL=transaction, COMP=destination))
                    continue

                table = tab.table

                # Add transaction records to the audit record destination element
                for subset_rule in subsets:
                    rule_entry = subsets[subset_rule]

                    try:
                        column_map = rule_entry['ColumnMapping']
                    except KeyError:
                        logger.warning('AuditRule {NAME}: failed to map transactions from transaction table {TBL} to '
                                       'audit record element {DEST} - no data fields were selected for mapping'
                                       .format(NAME=self.name, TBL=transaction, DEST=destination))
                        continue

                    dest_cols = [i for i in column_map if column_map[i] in header]

                    try:
                        subset_rule = rule_entry['Subset']
                    except KeyError:
                        add_df = table.data()
                    else:
                        add_df = table.subset(subset_rule)

                    if add_df.empty:
                        logger.debug('AuditRule {NAME}: no records remaining from transaction table {REF} to add '
                                     'to audit record element {DEST} based on rule {RULE}'
                                     .format(NAME=self.name, REF=transaction, DEST=destination, RULE=subset_rule))
                        continue

                    # Create references for the records

                    # Find any records that are already referenced
                    record_ids = add_df[table.id_column].tolist()
                    records_w_refs = table.has_reference(record_ids)

                    # Remove records that are already referenced from the add dataframe
                    if len(records_w_refs) > 0:
                        msg = '{NUM} {TYPE} records were found to already be associated with an audit - these ' \
                              'records will not be included in this current audit ({RECORDS})'\
                            .format(NUM=len(records_w_refs), TYPE=tab.name, RECORDS=records_w_refs)
                        mod_win2.popup_notice(msg)
                        logger.warning('AuditRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                        add_df = add_df[~add_df[table.id_column].isin(records_w_refs)]

                    # Add references for the remaining records to the references data
                    records_wo_refs = [i for i in record_ids if i not in records_w_refs]
                    print('approved records without current associations:')
                    print(records_wo_refs)
                    for record_id in records_wo_refs:
                        print('adding self reference for record {}'.format(record_id))
                        table.add_reference(record_id, audit_id, self.record_type, approved=True)

                    # Prepare the transaction records
                    add_df = add_df[dest_cols].rename(columns=column_map)

                    # Set defaults, if applicable
                    if 'Defaults' in rule_entry:
                        default_rules = rule_entry['Defaults']

                        for default_col in default_rules:
                            default_value = default_rules[default_col]

                            add_df[default_col] = default_value

                    # Add record to the components table
                    comp_df = comp_df.append(add_df, ignore_index=True)

            # Remove NA columns - required when merging
            comp_df = comp_df[comp_df.columns[~comp_df.isna().all()]]

            # Merge records, if applicable
            if 'Merge' in dest_entry:
                merge_on = [i for i in comp_df.columns if i not in dest_entry['Merge']]
                logger.debug('AuditRule {NAME}: merging new audit record element {DEST} components on columns {COLS}'
                             .format(NAME=self.name, DEST=destination, COLS=merge_on))
                comp_df = comp_df.groupby(merge_on).sum().reset_index()

            # Add transaction records to the set of transaction records that will get mapped to the audit component
            # records
            logger.debug('AuditRule {NAME}: creating audit record element {DEST} components from transaction records'
                         .format(NAME=self.name, DEST=destination))
            if not comp_df.empty:
                final_df = record.create_components(dest_element, record_data=comp_df)
                #dest_element.append(final_df)
                dest_element.append(final_df, new=True)

        return record


class AuditTransaction:
    """
    Transaction records to audit.

    Attributes:
        name (str): transaction name.

        parent (str): parent element, if applicable.

        id (int): GUI element number.

        elements (dict): GUI element keys.

        bindings (dict): GUI event bindings.

        title (str): title of the transaction.

        record_type (str): record type of the transaction.

        table (RecordTable): table storing transaction record data.
    """

    def __init__(self, name, entry, parent=None):
        """
        Arguments:

            name (str): configuration entry name for the transactions.

            entry (dict): dictionary of optional and required entry arguments.

            parent (str): name of the object's parent element.
        """
        self.name = name
        self.parent = parent
        self.id = randint(0, 1000000000)

        self.elements = {i: '-{NAME}_{ID}_{ELEM}-'.format(NAME=self.name, ID=self.id, ELEM=i) for i in
                         ('Tab', 'Panel')}
        self.bindings = {}

        try:
            self.title = entry['Title']
        except KeyError:
            self.title = name

        try:
            self.record_type = entry['RecordType']
        except KeyError:
            msg = 'missing required parameter "RecordType"'
            logger.error('AuditTransaction {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            raise AttributeError(msg)

        try:
            #self.table = mod_elem.RecordTable(name, entry['DisplayTable'])
            self.table = mod_elem.ReferenceTable(name, entry['DisplayTable'])
        except Exception as e:
            msg = 'failed to initialize the transaction table - {ERR}'.format(ERR=e)
            logger.error('AuditTransaction {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            raise AttributeError(msg)
        else:
            self.bindings.update(self.table.bindings)

        try:
            filter_rules = entry['FilterRules']
        except KeyError:
            filter_rules = {}

        self.filter_rules = {}
        table_columns = self.table.columns
        for filter_key in filter_rules:
            if filter_key in table_columns:
                self.filter_rules[filter_key] = filter_rules[filter_key]
            else:
                logger.warning('AuditTransaction {NAME}: filter rule key {KEY} not found in table columns'
                               .format(NAME=self.name, KEY=filter_key))

        try:
            self.id_format = re.findall(r'{(.*?)}', entry['IDFormat'])
        except KeyError:
            msg = 'missing required field "IDFormat".'
            logger.error('AuditTransaction {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            raise AttributeError(msg)

        try:
            self.association_type = entry['AssociationType']
        except KeyError:
            msg = 'missing required parameter "AssociationType"'
            logger.error('AuditTransaction {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            raise AttributeError(msg)

        self.parameters = None
        self.id_components = []

    def key_lookup(self, component, rev: bool = False):
        """
        Lookup an audit transaction element's component GUI key using the name of the component element.

        Arguments:
            component (str): GUI component name (or key if rev is True) of the audit transaction element.

            rev (bool): reverse the element lookup map so that element keys are dictionary keys.
        """
        key_map = self.elements if rev is False else {j: i for i, j in self.elements.items()}
        try:
            key = key_map[component]
        except KeyError:
            msg = 'component {COMP} not found in list of audit rule elements'.format(COMP=component)
            logger.warning('AuditTransaction {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
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

        # Disable table actions
        self.table.disable(window)

        # Reset dynamic attributes
        self.parameters = None
        self.id_components = []

        # Reset visible tabs
        visible = True if first is True else False
        logger.debug('AuditTransaction {NAME}: re-setting visibility to {STATUS}'
                     .format(NAME=self.name, STATUS=visible))

        window[self.key_lookup('Tab')].update(visible=visible)

    def layout(self, size, visible: bool = True):
        """
        GUI layout for the audit rule transaction tab.
        """
        width, height = size

        # Element parameters
        bg_col = mod_const.DEFAULT_BG_COLOR
        pad_frame = mod_const.FRAME_PAD
        font = mod_const.MAIN_FONT

        # Element sizes
        bffr_h = (18 + 4) + pad_frame * 2  # height of the tabs, padding, and button
        tbl_width = width - pad_frame * 2
        tbl_height = height - bffr_h

        # Layout
        main_layout = [[self.table.layout(size=(tbl_width, tbl_height), padding=(0, 0))]]

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
        bffr_h = 18 + pad_frame  # height of the tabs and padding
        tbl_width = panel_w - tbl_pad  # minus padding
        tbl_height = panel_h - bffr_h
        self.table.resize(window, size=(tbl_width, tbl_height))

    def run_event(self, window, event, values):
        """
        Run an audit rule transaction event.
        """
        table = self.table
        results = {'AuditEvent': False, 'Success': True}

        # Run component table events
        table_keys = table.bindings
        if event in table_keys:
            tbl_event = table_keys[event]

            if tbl_event == 'Audit' and table.enabled('Audit'):
                results['AuditEvent'] = True

                try:
                    self.audit_transactions()
                except Exception as e:
                    msg = 'audit failed on transaction {NAME} - {ERR}'.format(NAME=self.title, ERR=e)
                    logger.exception('AuditTransaction {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                    results['Success'] = False
                else:
                    delete_rows = self.filter_table()
                    if len(delete_rows) > 0:
                        table.delete_rows(delete_rows)

                    table.update_display(window)
            else:
                table.run_event(window, event, values)

        return results

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
                filter_results = mod_dm.evaluate_condition(df, filter_rule)
            except Exception as e:
                logger.warning('AuditTransaction {NAME}: filtering table on column {COL} failed - {ERR}'
                               .format(NAME=self.name, COL=column, ERR=e))
                continue

            try:
                failed = df[(df.duplicated(subset=[column], keep=False)) & (filter_results)].index.tolist()
            except Exception as e:
                logger.warning('AuditTransaction {NAME}: filtering table on column {COL} failed - {ERR}'
                               .format(NAME=self.name, COL=column, ERR=e))
                continue
            else:
                failed_rows.update(failed)

        return list(failed_rows)

    def load_data(self, parameters, audit_id: str = None):
        """
        Load data from the database.
        """
        record_type = self.record_type
        record_entry = settings.records.fetch_rule(record_type)

        # Load the transaction records
        logger.info('AuditTransaction {NAME}: attempting to load transaction records from the database based on '
                    'the supplied parameters'.format(NAME=self.name))
        try:
            df = record_entry.import_records(filter_params=parameters)
        except Exception as e:
            msg = 'failed to load the transaction records from the database'
            logger.exception('AuditTransaction {NAME}: {MSG} - {ERR}'.format(NAME=self.name, MSG=msg, ERR=e))

            raise ImportError(msg)

        # Load additional records associated with the audit that may not have been captured by the selection parameters
        ref_df = record_entry.import_references(audit_id, is_reference=True)
        if not ref_df.empty:
            records = ref_df.loc[ref_df['RecordType'] == self.record_type, 'RecordID'].tolist()

            imported_ids = df[self.table.id_column].tolist()
            remaining_records = list(set(records).difference(imported_ids))
            print('loading additional records associated with the audit: {}'.format(remaining_records))

            if len(remaining_records) > 0:
                loaded_df = record_entry.load_records(remaining_records)

                df = df.append(loaded_df)

        logger.info('AuditTransaction {NAME}: successfully loaded the transaction records from the database'
                    .format(NAME=self.name))
        self.table.append(df)

        # Load any previous record references
        self.table.import_references()

        # Update parameter attributes
        self.parameters = parameters

    def audit_transactions(self):
        """
        Search for missing transactions using scan.
        """
        strptime = datetime.datetime.strptime

        # Class attributes
        record_type = self.record_type
        record_entry = settings.records.fetch_rule(record_type)

        table = self.table
        collection = table.collection
        pkey = collection.id_column
        id_list = sorted(table.row_ids(), reverse=False)
        missing_df = table.data(deleted_rows=True)
        current_import_ids = table.row_ids(indices=missing_df.index.tolist())

        # Audit parameters
        date_param = self.fetch_parameter('date', by_type=True)
        date_col = date_param.name
        date_db_col = record_entry.map_column(date_col)
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
            unq_dates = record_entry.unique_values(date_col, sort=False)
            unq_dates_iso = [i.strftime("%Y-%m-%d") for i in unq_dates]
            unq_dates_iso.sort()

            print('looking for {}'.format(audit_date_iso))
            print('in {}'.format(unq_dates_iso))
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

                import_filters = ('{} = ?'.format(date_db_col), prev_date.strftime(settings.date_format))
                last_df = record_entry.import_records(filter_rules=import_filters)
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
                        if (missing_id not in id_list) and (missing_id not in current_import_ids):
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
                        if (missing_id not in id_list) and (missing_id not in current_import_ids):
                            missing_transactions.append(missing_id)
                            nskipped += 1

                prev_number = record_no

            logger.debug('AuditTransaction {NAME}: found {N} skipped transactions from within current '
                         'transaction date {DATE}'.format(NAME=self.name, N=nskipped, DATE=audit_date_iso))

            # Search for missed numbers at end of day
            logger.info('AuditTransaction {NAME}: searching for transactions created at the end of the day'
                        .format(NAME=self.name))
            last_id_of_df = id_list[-1]  # last transaction of the dataframe

            import_filters = ('{} = ?'.format(date_db_col), audit_date.strftime(settings.date_format))
            current_df = record_entry.import_records(filter_rules=import_filters)

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
                        (current_id not in current_import_ids):
                    missing_transactions.append(current_id)

        logger.debug('AuditTransaction {NAME}: potentially missing transactions: {MISS}'
                     .format(NAME=self.name, MISS=missing_transactions))

        # Query database for the potentially missing transactions
        if missing_transactions:
            loaded_df = record_entry.load_records(missing_transactions, use_import_rules=False)
            missing_df = missing_df.append(loaded_df, ignore_index=True)

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
        logger.debug('AuditTransaction {NAME}: ID is formatted as {FORMAT}'.format(NAME=self.name, FORMAT=id_format))
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

        logger.debug('AuditTransaction {NAME}: ID updated with components {COMP}'
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
                    logger.warning('AuditTransaction {NAME}: no date provided for ID number {NUM} ... reverting to '
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
                    logger.warning('AuditTransaction {NAME}: ID component {COMP} cannot be found in identifier '
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
