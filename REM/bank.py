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
import REM.parameters as mod_param
import REM.secondary as mod_win2
from REM.client import logger, settings


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
                         ('Panel', 'Entry', 'Reconcile', 'Parameters', 'Cancel', 'Save', 'FrameHeight',
                          'FrameWidth', 'PanelHeight', 'PanelWidth', 'Back', 'Next', 'Warnings')]

        self.bindings = [self.key_lookup(i) for i in
                         ('Cancel', 'Save', 'Back', 'Next', 'Entry', 'Parameters', 'Reconcile')]

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
            self.bindings.extend(param.event_bindings())

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
        current_acct = self.current_account
        current_rule = self.name

        reconcile_key = self.key_lookup('Reconcile')
        entry_key = self.key_lookup('Entry')
        param_key = self.key_lookup('Parameters')
        cancel_key = self.key_lookup('Cancel')
        save_key = self.key_lookup('Save')
        next_key = self.key_lookup('Next')
        back_key = self.key_lookup('Back')
        warn_key = self.key_lookup('Warnings')

        can_save = not window[save_key].metadata['disabled']
        print('reconciliation can be saved: {}'.format(can_save))

        # Run an account entry event
        acct_keys = [i for j in self.accts for i in j.bindings]
        if event in acct_keys:
            current_panel = self.current_panel
            acct = self.fetch_account(current_panel, by_key=True)

            results = acct.run_event(window, event, values)

            # Update reference dataframes when an account entry event is a reference event. A reference event is any
            # event that may modify one side of a reference, which requires an update to the other side of the
            # reference.
            ref_indices = results.get('ReferenceIndex')
            if ref_indices:
                ref_df = acct.ref_df.copy()
                # Update account reference dataframes for currently active panels
                for panel in self.panels:
                    if panel == current_panel:  # do not attempt to update the main account's reference dataframe
                        continue

                    ref_acct = self.fetch_account(panel, by_key=True)
                    ref_acct.ref_df = ref_acct.update_references(ref_df.loc[ref_indices])

                self.update_display(window)

            # Update warning element with the reference notes of the selected record, if any.
            record_indices = results.get('RecordIndex')
            print('record indices {} were selected from account table {}'.format(record_indices, acct.name))
            if record_indices:
                if len(record_indices) > 1:
                    record_warning = None
                else:
                    record_warning = acct.fetch_reference_parameter('ReferenceNotes', record_indices).squeeze()
                print('record reference has warning "{}"'.format(record_warning))
                window[warn_key].update(value=settings.format_display(record_warning, 'varchar'))

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
                    save_status = self.save_references()
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

        # Next button pressed - display next panel in transaction workflow. Wrap-around to first panel if next panel
        # goes beyond the number of items in the panel list
        elif event == next_key and not window[next_key].metadata['disabled']:
            current_index = self.panels.index(self.current_panel)
            next_index = (current_index + 1) % len(self.panels)
            next_panel = self.panels[next_index]

            # Reset panel sizes
            next_acct = self.fetch_account(next_panel, by_key=True)
            next_acct.table.set_table_dimensions(window)

            # Hide current panel and un-hide the following panel
            window[self.current_panel].update(visible=False)
            window[next_panel].update(visible=True)

            # Reset current panel attribute
            self.current_panel = next_panel

        # Back button pressed - display previous panel. Wrap-around to last panel if previous panel is less than the
        # number of items in the panel list
        elif event == back_key and not window[back_key].metadata['disabled']:
            current_index = self.panels.index(self.current_panel)
            back_index = current_index - 1
            prev_panel = self.panels[back_index]

            # Reset panel sizes
            prev_acct = self.fetch_account(prev_panel, by_key=True)
            prev_acct.table.set_table_dimensions(window)

            # Hide current panel and un-hide the previous panel
            window[self.current_panel].update(visible=False)
            window[prev_panel].update(visible=True)

            # Reset current panel attribute
            self.current_panel = prev_panel

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
                window[self.current_panel].update(visible=False)

            # Set the new primary account account
            current_acct = self.fetch_account(acct_title, by_title=True)
            self.current_account = current_acct.name
            self.current_panel = current_acct.key_lookup('Panel')

            # Clear the panel
            window[self.current_panel].update(visible=True)

            # Enable the parameter selection button
            window[param_key].update(disabled=False)

        # Set parameters button was pressed. Will open parameter settings window for user to input parameter values,
        # then load the relevant account record data
        elif event == param_key:
            # Get the parameter settings
            params = mod_win2.parameter_window(self.fetch_account(current_acct))

            # Load the account records
            if params:  # parameters were saved (selection not cancelled)
                for acct_name in params:
                    acct_params = params[acct_name]
                    if not acct_params:
                        continue

                    logger.debug('BankRule {NAME}: loading database records for account {ACCT}'
                                 .format(NAME=self.name, ACCT=acct_name))
                    acct = self.fetch_account(acct_name)
                    data_loaded = acct.load_data(acct_params)

                    if not data_loaded:
                        return self.reset_rule(window, current=True)
                    else:
                        self.panels.append(self.panel_keys[acct_name])

                    # Enable table action buttons, but only for the primary table
                    if self.current_account != acct_name:
                        acct.table.enable(window, custom=False)
                    else:
                        acct.table.enable(window)

                # Update the display
                self.update_display(window)

                # Disable the account entry selection dropdown
                window[entry_key].update(disabled=True)
                window[param_key].update(disabled=True)

                # Enable elements
                window[save_key].update(disabled=False)
                window[save_key].metadata['disabled'] = False
                if len(self.panels) > 1:
                    window[reconcile_key].update(disabled=False)

                    # Enable the navigation buttons
                    window[next_key].update(disabled=False)
                    window[next_key].metadata['disabled'] = False
                    window[back_key].update(disabled=False)
                    window[back_key].metadata['disabled'] = False

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
        entry_key = self.key_lookup('Entry')
        param_key = self.key_lookup('Parameters')
        warn_key = self.key_lookup('Warnings')

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

        # Disable the navigation buttons and reconciliation modifier parameters
        next_key = self.key_lookup('Next')
        back_key = self.key_lookup('Back')
        window[next_key].update(disabled=True)
        window[next_key].metadata['disabled'] = True
        window[back_key].update(disabled=True)
        window[back_key].metadata['disabled'] = True

        self.reset_parameters(window)
        self.toggle_parameters(window, 'disable')

        # Clear the warning element
        window[warn_key].update(value='')

        # Reset all account entries
        for acct in self.accts:
            acct.reset(window)

        self.in_progress = False
        self.panels = []

        if current:
            window['-HOME-'].update(visible=False)
            if self.current_panel:
                window[self.current_panel].update(visible=True)

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
        font_h = mod_const.HEADING_FONT

        pad_el = mod_const.ELEM_PAD
        pad_v = mod_const.VERT_PAD
        pad_h = mod_const.HORZ_PAD
        pad_frame = mod_const.FRAME_PAD

        # Element sizes
        frame_height = height
        panel_height = frame_height - 220  # minus panel title, padding, and button row

        frame_width = width
        panel_width = frame_width - 38  # padding + scrollbar width

        # Keyboard shortcuts
        hotkeys = settings.hotkeys
        cancel_shortcut = hotkeys['-HK_ESCAPE-'][2]
        save_shortcut = hotkeys['-HK_ENTER-'][2]
        next_shortcut = hotkeys['-HK_RIGHT-'][2]
        back_shortcut = hotkeys['-HK_LEFT-'][2]

        # Layout elements

        # Title
        panel_title = 'Bank Reconciliation: {}'.format(self.menu_title)
        title_layout = sg.Text(panel_title, pad=(pad_frame, pad_frame), font=font_h, background_color=header_col)

        # Header
        param_key = self.key_lookup('Parameters')
        entry_key = self.key_lookup('Entry')
        reconcile_key = self.key_lookup('Reconcile')

        # Rule parameter elements
        if len(params) > 1:
            param_pad = ((0, pad_h), 0)
        else:
            param_pad = (0, 0)

        param_elements = [sg.Button('Reconcile', key=reconcile_key, pad=((0, pad_el), 0), disabled=True,
                                    button_color=(bttn_text_col, bttn_bg_col),
                                    disabled_button_color=(disabled_text_col, disabled_bg_col),
                                    tooltip='Run reconciliation')]
        for param in params:
            element_layout = param.layout(padding=param_pad, auto_size_desc=True)
            param_elements.extend(element_layout)

        entries = [i.title for i in self.accts]
        header = [sg.Col([[sg.Combo(entries, default_value='', key=entry_key, size=(30, 1), pad=(pad_h, 0), font=font,
                                    text_color=text_col, background_color=bg_col, disabled=False, enable_events=True,
                                    tooltip='Select reconciliation account'),
                           sg.Button('', key=param_key, image_data=mod_const.PARAM_ICON, image_size=(28, 28),
                                     button_color=(text_col, bg_col), disabled=True, tooltip='Set parameters')]],
                         expand_x=True, justification='l', background_color=bg_col),
                  sg.Col([param_elements], pad=(0, 0), justification='r', background_color=bg_col)]

        # Reference warnings
        warn_key = self.key_lookup('Warnings')
        warn_w = width - 40  # width of the display panel minus padding on both sides
        warn_h = 2
        warn_layout = sg.Multiline('', key=warn_key, pad=(0, (pad_v, 0)), size=(warn_w, warn_h), font=font,
                                   disabled=True, background_color=bg_col, text_color=disabled_text_col, border_width=1)

        # Panels
        panels = []
        for acct in self.accts:
            layout = acct.layout(size=(panel_width, panel_height))
            panels.append(layout)

        pw_key = self.key_lookup('PanelWidth')
        ph_key = self.key_lookup('PanelHeight')
        panel_group = [[sg.Canvas(key=pw_key, size=(panel_width, 0), background_color=bg_col)],
                       [sg.Canvas(key=ph_key, size=(0, panel_height), background_color=bg_col),
                        sg.Pane(panels, orientation='horizontal', show_handle=False, border_width=0, relief='flat')]]

        # Panel layout
        panel_layout = sg.Col(panel_group, pad=(0, 0), background_color=bg_col, expand_x=True,
                              vertical_alignment='t', visible=True, expand_y=True, scrollable=True,
                              vertical_scroll_only=True)

        # Control elements
        next_key = self.key_lookup('Next')
        back_key = self.key_lookup('Back')
        cancel_key = self.key_lookup('Cancel')
        save_key = self.key_lookup('Save')
        bttn_layout = sg.Col([
            [sg.Button('', key=cancel_key, image_data=mod_const.CANCEL_ICON,
                       image_size=mod_const.BTTN_SIZE, pad=((0, pad_el), 0), disabled=False,
                       tooltip='Return to home screen ({})'.format(cancel_shortcut)),
             sg.Button('', key=back_key, image_data=mod_const.LEFT_ICON, image_size=mod_const.BTTN_SIZE,
                       pad=((0, pad_el), 0), disabled=True, tooltip='Next panel ({})'.format(back_shortcut),
                       metadata={'disabled': True}),
             sg.Button('', key=next_key, image_data=mod_const.RIGHT_ICON, image_size=mod_const.BTTN_SIZE,
                       pad=((0, pad_el), 0), disabled=True, tooltip='Previous panel ({})'.format(next_shortcut),
                       metadata={'disabled': True}),
             sg.Button('', key=save_key, image_data=mod_const.SAVE_ICON, image_size=mod_const.BTTN_SIZE,
                       pad=(0, 0), disabled=True, tooltip='Save results ({})'.format(save_shortcut),
                       metadata={'disabled': True})
             ]], background_color=bg_col, element_justification='c', expand_x=True)

        fw_key = self.key_lookup('FrameWidth')
        fh_key = self.key_lookup('FrameHeight')
        layout = [[sg.Canvas(key=fw_key, size=(frame_width, 0), background_color=bg_col)],
                  [sg.Col([[title_layout]], background_color=header_col, expand_x=True)],
                  [sg.Canvas(key=fh_key, size=(0, frame_height), background_color=bg_col),
                   sg.Col([header,
                          [sg.HorizontalSeparator(pad=(0, pad_v), color=mod_const.HEADER_COL)],
                          [panel_layout],
                          [warn_layout],
                          [sg.HorizontalSeparator(pad=(0, pad_v), color=mod_const.HEADER_COL)],
                          [bttn_layout]],
                          pad=(pad_frame, pad_frame), background_color=bg_col, expand_x=True, expand_y=True)]]

        return sg.Col(layout, key=self.element_key, visible=False, background_color=bg_col, vertical_alignment='t')

    def resize_elements(self, window, size):
        """
        Resize Bank Reconciliation Rule GUI elements.

        Arguments:
            window (Window): GUI window.

            size (tuple): new panel size (width, height).
        """
        width, height = size

        frame_width = width
        width_key = self.key_lookup('FrameWidth')
        window[width_key].set_size((frame_width, None))

        panel_width = frame_width - 40  # minus frame padding
        pw_key = self.key_lookup('PanelWidth')
        window[pw_key].set_size((panel_width, None))

        height_key = self.key_lookup('FrameHeight')
        window[height_key].set_size((None, height))

        warn_h = 50
        #print('the height of the warnings frame is: {}'.format(window[self.key_lookup('Warnings')].get_size()[1]))
        panel_height = height - 240 - warn_h  # minus panel title, padding, button row, and
        ph_key = self.key_lookup('PanelHeight')
        window[ph_key].set_size((None, panel_height))

        # Resize account panels
        accts = self.accts
        for acct in accts:
            acct.resize(window, size=(panel_width, panel_height))

    def update_display(self, window):
        """
        Update the audit record summary tab's record display.
        """
        # Update the relevant account panels
        for acct_panel in self.panels:
            acct = self.fetch_account(acct_panel, by_key=True)
            acct.update_display(window)

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

        table = acct.table
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

            assoc_df = assoc_acct.table.data()
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
            if nmatch == 0:  # no matching entries in the merged dataset
                continue

            elif nmatch == 1:  # found one exact match
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

                warning = 'found more than one match for account {ACCT} record "{RECORD}"' \
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

                # Attempt to find matches using only the core columns
                #matches = pd.DataFrame(columns=merged_df.columns)
                #expanded_cols = []
                #for assoc_acct_name in assoc_ref_maps:
                #    # Subset merged df to include only the association records with the given account name
                #    assoc_df = merged_df[merged_df['_Account_'] == assoc_acct_name]

                #    assoc_rules = assoc_ref_maps[assoc_acct_name]
                #    cols = []
                #    for col in assoc_rules:
                #        rule_entry = assoc_rules[col]

                        # Select the columns that will be used to compare records
                #        if rule_entry['Expand']:
                #            if col not in expanded_cols:
                #                expanded_cols.append(col)

                #            continue

                #        cols.append(col)

                    # Find exact matches between account record and the associated account records using relevant cols
                #    row_vals = [getattr(row, i) for i in cols]
                #    acct_matches = assoc_df[assoc_df[cols].eq(row_vals).all(axis=1)]
                #    matches = matches.append(acct_matches)

                #nmatch = matches.shape[0]
                #if nmatch == 0:  # no matches found given the parameters supplied
                #    continue

                #elif nmatch == 1:  # potential match, add with a warning
                #    nfound += 1

                #    results = matches.iloc[0]
                #    assoc_acct_name = results['_Account_']
                #    ref_id = results['_RecordID_']
                #    ref_type = results['_RecordType_']

                #    logger.debug('BankRule {NAME}: associating {ACCT} record {REFID} to account record {ID} from an '
                #                 'expanded search'.format(NAME=self.name, ACCT=assoc_acct_name, REFID=ref_id,
                #                                          ID=record_id))

                    # Remove the found match from the dataframe of unmatched associated account records
                #    merged_df.drop(matches.index.tolist()[0], inplace=True)

                    # Determine appropriate warning for the expanded search
                #    assoc_rules = assoc_ref_maps[assoc_acct_name]
                #    warning = ["Potential false positive:"]
                #    for column in expanded_cols:
                #        if getattr(row, column) != results[column]:
                #            alt_warn = 'values for expanded column {COL} do not match'.format(COL=column)
                #            col_warning = assoc_rules[column].get('Description', alt_warn)
                #            warning.append('- {}'.format(col_warning))

                #    warning = '\n'.join(warning)

                    # Insert the reference into the account records reference dataframe
                #    acct.add_reference(record_id, ref_id, ref_type, approved=False, warning=warning)

                    # Insert the reference into the associated account's reference dataframe
                #    assoc_acct = self.fetch_account(assoc_acct_name)
                #    assoc_acct.add_reference(ref_id, record_id, acct.record_type, approved=False, warning=warning)

                #elif nmatch > 1:  # need to use the association parameters expand levels to find the best match
                #    msg = 'found more than one expanded match for account {ACCT} record "{RECORD}" - searching for ' \
                #          'the best match'.format(ACCT=self.current_account, RECORD=record_id)
                #    logger.warning('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                    # Find the closest match by iterative expanded column inclusion

                #    continue

        logger.info('BankRule {NAME}: found {NMATCH} associations out of {NTOTAL} unreferenced account {ACCT} records'
                    .format(NAME=self.name, NMATCH=nfound, NTOTAL=df.shape[0], ACCT=acct.name))

        return True

    def find_expanded_match(self, row, ref_df, ref_map, expand_level: int = 0):
        """
        Attempt to find matching records using iterative expansion of reference columns.
        """
        results = pd.Series()

        matches = pd.DataFrame(columns=ref_df.columns)
        expanded_cols = []
        for assoc_acct_name in ref_map:
            # Subset merged df to include only the association records with the given account name
            assoc_df = ref_df[ref_df['_Account_'] == assoc_acct_name]

            assoc_rules = ref_map[assoc_acct_name]
            cols = []
            for col in assoc_rules:
                rule_entry = assoc_rules[col]

                # Select the columns that will be used to compare records
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
        if nmatch == 1:  # potential match, add with a warning
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

        elif nmatch > 1:  # need to use the association parameters expand levels to find the best match
            msg = 'found more than one expanded match for account {ACCT} row "{ROW}" - searching for ' \
                  'the best match'.format(ACCT=self.current_account, ROW=row.name)
            logger.warning('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            # Find the closest match by iterative expanded column inclusion
            results = self.find_expanded_match(row, matches, ref_map, expand_level=expand_level+1)

        return results

    def save_references(self):
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
                         ('Panel', 'Approve', 'Reset')]

        self.bindings = [self.key_lookup(i) for i in ('Approve', 'Reset')]

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
                        'Reset': {'Key': self.key_lookup('Reset'),
                                  'Icon': mod_const.TBL_RESET_ICON,
                                  'Description': 'Reset record status (CTRL+R)',
                                  'Shortcut': 'Control-R'}}

        table_entry['CustomActions'] = action_bttns

        self.table = mod_elem.RecordTable(name, table_entry)
        self.bindings.extend(self.table.bindings)

        elem_key = self.table.key_lookup('Element')
        approve_hkey = '{}+RETURN+'.format(elem_key)
        reset_hkey = '{}+LCLICK+'.format(elem_key)
        self.bindings.extend([approve_hkey, reset_hkey])

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
        table.reset(window)
        self.ref_df = None

        # Disable table element events
        table.disable(window)

    def run_event(self, window, event, values):
        """
        Run a bank account entry event.
        """
        pd.set_option('display.max_columns', None)

        colmap = self._col_map
        table = self.table
        table_keys = table.bindings
        tbl_key = table.key_lookup('Element')
        approve_key = self.key_lookup('Approve')
        approve_hkey = '{}+RETURN+'.format(tbl_key)
        reset_key = self.key_lookup('Reset')
        reset_hkey = '{}+LCLICK+'.format(tbl_key)

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
                    index = table.get_real_index(select_row_index)
                    record_indices = [index]

                    logger.debug('DataTable {NAME}: opening record at real index {IND}'
                                 .format(NAME=table.name, IND=index))
                    if can_open:
                        ref_df = self.ref_df
                        record = table.load_record(index, level=0, savable=False, references={association_rule: ref_df})
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
                                print('updating table row {} with values:'.format(index))
                                print(record_values)
                                table.update_row(index, record_values)

                                self.update_display(window)
                                print(table.df)

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

            elif event == tbl_key:
                table.run_event(window, event, values)

                # Get index of the selected rows
                try:
                    select_indices = values[tbl_key]
                except IndexError:  # user double-clicked too quickly
                    msg = 'table row could not be selected'
                    logger.debug('DataTable {NAME}: {MSG}'.format(NAME=table.name, MSG=msg))
                else:
                    # Get the real index of the selected row
                    record_indices = table.get_real_index(select_indices)

            else:
                table.run_event(window, event, values)

        elif event in (approve_key, approve_hkey):
            # Find rows selected by user for approval
            select_row_indices = values[tbl_key]

            # Get the real indices of the selected rows
            indices = table.get_real_index(select_row_indices)

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

        elif event in (reset_key, reset_hkey):
            # Find rows selected by user for deletion
            select_row_indices = values[tbl_key]

            # Get the real indices of the selected rows
            indices = table.get_real_index(select_row_indices)

            # Get record IDs for the selected rows
            record_ids = table.df.loc[indices, table.id_column].tolist()

            # Delete references and approval for the selected records
            try:
                reference_indices = self.unapprove(record_ids)
            except Exception as e:
                msg = 'failed to reset record references at table indices {INDS}'.format(INDS=indices)
                logger.error('BankAccount {NAME}: {MSG} - {ERR}'.format(NAME=self.name, MSG=msg, ERR=e))

            # Reset void transaction status
            if 'Void' in colmap:
                table.update_column(colmap['Void'], False, indices=indices)

        return {'ReferenceIndex': reference_indices, 'RecordIndex': record_indices}

    def layout(self, size):
        """
        GUI layout for the account sub-panel.
        """
        width, height = size

        # Element parameters
        bg_col = mod_const.ACTION_COL
        pad_frame = mod_const.FRAME_PAD

        # Element sizes
        tbl_width = width - 30
        tbl_height = height * 0.55

        # Layout
        tbl_layout = [[self.table.layout(tooltip=self.title, size=(tbl_width, tbl_height), padding=(0, 0))]]

        panel_key = self.key_lookup('Panel')
        layout = sg.Col(tbl_layout, key=panel_key, pad=(pad_frame, pad_frame), justification='c',
                        vertical_alignment='t', background_color=bg_col, expand_x=True, visible=False)

        return layout

    def resize(self, window, size):
        """
        Resize the account sub-panel.
        """
        width, height = size

        #print('current size of panel {} is {}'.format(self.name, window[self.key_lookup('Panel')].get_size()))

        # Reset table size
        tbl_width = width - 26  # minus the width of the panel scrollbar
        tbl_height = height
        #print('setting table height to {}'.format(tbl_height))
        self.table.resize(window, size=(tbl_width, tbl_height))

    def fetch_reference_parameter(self, param, indices):
        """
        Fetch reference parameter values at provided record table row indices.
        """
        refmap = self.ref_map
        header = self.table.df.columns.tolist()

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
            param_values = self.table.df.loc[indices, column]
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

        df = self.table.data() if df is None else df

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
            self.table.update_column(mapped_col, new_values, indices=indices)

        print(self.table.df)

    def update_references(self, ref_df):
        """
        Update the reference dataframe using a corresponding reference dataframe.
        """
        pd.set_option('display.max_columns', None)

        df = self.ref_df.copy()

        print('BankAccount {}:selected references:'.format(self.name))
        print(ref_df)

        # Drop references records that are not found as corresponding references in the reference dataframe
        ref_ids = df['ReferenceID'].dropna()
        ref_df = ref_df[ref_df['RecordID'].isin(ref_ids)]
        print('BankAccount {}: references entries that are found both in the reference dataframe and the corresponding dataframe:'.format(self.name))
        print(ref_df)

        if ref_df.empty:
            print('BankAccount {}: no references remaining after filtering references that are not shared'.format(self.name))
            return df

        # Delete reference entries that were deleted in the corresponding reference dataframe
        deleted_references = ref_df.loc[ref_df['ReferenceID'].isna(), 'RecordID']
        if not deleted_references.empty:
            refs_to_delete = df.loc[df['ReferenceID'].isin(deleted_references.tolist()), 'RecordID']
            print('BankAccount {}: removing references for:'.format(self.name))
            print(refs_to_delete)
            self.unapprove(refs_to_delete.tolist())

            ref_df.drop(deleted_references.index, inplace=True)
            df = self.ref_df.copy()

        # Subset reference table on matching reference records
        if ref_df.empty:
            print('BankAccount {}: no references remaining after removing the deleted references'.format(self.name))
            return df

        print('BankAccount {}: remaining reference to update after removing the deleted references:'.format(self.name))
        print(ref_df)

        df.set_index('RecordID', inplace=True)
        ref_df.set_index('ReferenceID', inplace=True)
        #print('BankAccount {}: indexing corresponding reference entries on the current reference entries'.format(self.name))
        #ref_df = ref_df.loc[df.index]
        #print(ref_df)

        mod_cols = ['ReferenceDate', 'ReferenceNotes', 'IsApproved']
        print('BankAccount {}: reference entries to be updated:'.format(self.name))
        print(df.loc[ref_df.index, mod_cols])
        df.loc[ref_df.index, mod_cols] = ref_df[mod_cols]
        print('BankAccount {}: reference entries after updating:'.format(self.name))
        print(df.loc[ref_df.index, mod_cols])

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

    def unapprove(self, record_ids):
        """
        Delete references for the selected records.

        Arguments:
            record_ids (list): list of record IDs corresponding to the records to remove references from.

        Returns:
            ref_indices (list): list of affected references indices.
        """
        ref_df = self.ref_df

        # Clear the reference entries corresponding to the selected record IDs.
        logger.info('DataTable {TBL}: removing references for records {IDS}'
                    .format(TBL=self.name, IDS=record_ids))
        ref_indices = ref_df.index[ref_df['RecordID'].isin(record_ids)]
        ref_columns = ['ReferenceID', 'ReferenceDate', 'ReferenceType', 'ReferenceNotes', 'IsApproved']
        ref_df.loc[ref_indices, ref_columns] = [None, None, None, None, False]

        return ref_indices.tolist()

    def search_void(self, df):
        """
        Set the correct transaction type for failed transaction records.
        """
        pd.set_option('display.max_columns', None)

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
            matches = nearest_match(bounced.rename(columns={date_col: 'Date', withdraw_col: 'Amount'}),
                                    deposits.rename(columns={date_col: 'Date', deposit_col: 'Amount'}),
                                    'Date', on='Amount', value_range=bc_entry.get('DateRange', 1))

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
            matches = nearest_match(deposits.rename(columns={date_col: 'Date', deposit_col: 'Amount'}),
                                    withdrawals.rename(columns={date_col: 'Date', withdraw_col: 'Amount'}),
                                    'Date', on='Amount', value_range=mp_entry.get('DateRange', 1))

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
        void_inds = self.table.df.loc[self.table.df['RecordID'].isin(void_records)].index.tolist()
        if len(void_inds) > 0:
            print('BankAccount {}: setting void column {} to true for indices:'.format(self.name, failed_col))
            print(void_inds)
            self.table.update_column(failed_col, True, indices=void_inds)

        return df

    def filter_void(self, df: pd.DataFrame = None):
        """
        Remove void transactions from a dataframe.
        """
        column_map = self._col_map
        df = df if df is not None else self.table.data()

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

    def update_display(self, window):
        """
        Update the panel's record table display.
        """
        # Merge records and references dataframes
        self.merge_references()
        self.table.df = self.table.set_conditional_values()

        # Update the display table
        self.table.update_display(window)

    def load_data(self, parameters):
        """
        Load record and reference data from the database based on the supplied parameter set.

        Arguments:
            parameters (list): list of data parameters to filter the records database table on.

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
            mod_win2.popup_error('{MSG} -  see log for details'.format(MSG=msg))

            return False

        # Update the record table dataframe with the data imported from the database
        self.table.df = self.table.append(df)

        # Load the record references from the reference table connected with the association rule
        rule_name = self.association_rule
        record_ids = df[self.table.id_column].tolist()

        try:
            import_df = record_entry.import_references(record_ids, rule_name)
        except Exception as e:
            msg = 'failed to import references from association rule {RULE}'.format(RULE=rule_name)
            logger.exception('BankAccount {NAME}: {MSG} - {ERR}'.format(NAME=self.name, MSG=msg, ERR=e))
            mod_win2.popup_error('{MSG} -  see log for details'.format(MSG=msg))

            return False

        ref_df = pd.merge(df.loc[:, ['RecordID']], import_df, how='left', on='RecordID')
        ref_df['RecordType'].fillna(record_type, inplace=True)

        bool_columns = ['IsChild', 'IsHardLink', 'IsApproved', 'IsDeleted']
        ref_df[bool_columns] = ref_df[bool_columns].fillna(False)
        ref_df = ref_df.astype({i: np.bool for i in bool_columns})

        self.ref_df = ref_df

        # Merge the configured reference columns with the records table
        ref_map = self.ref_map
        ref_df = ref_df.copy()

        df = self.table.data()

        # Set index to record ID for updating
        df.set_index('RecordID', inplace=True)
        ref_df.set_index('RecordID', inplace=True)

        # Rename reference columns to record columns using the reference map
        mapped_df = ref_df[list(ref_map)].rename(columns=ref_map)

        # Update record reference columns
        df = df.drop(columns=mapped_df.columns).join(mapped_df)
        df.reset_index(inplace=True)

        self.table.df = df

        return True


def nearest_match(df, ref_df, column, on: str = None, value_range: int = None):
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

    if value_range:
        dtype = ref_df[column].dtype
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
