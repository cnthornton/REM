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
                         ('MainPanel', 'Reconcile', 'Parameters', 'Expand', 'Cancel', 'Save', 'FrameHeight',
                          'FrameWidth', 'PanelHeight', 'PanelWidth', 'Back', 'Next')]

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

            acct = AccountEntry(acct_id, acct_entry, parent=self.name)
            self.accts.append(acct)
            self.panel_keys[acct_id] = acct.key_lookup('Panel')
            #self.elements += acct.elements

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

    def events(self):
        """
        Return a list of all events allowed under the rule.
        """
        events = self.elements

        for acct in self.accts:
            events.extend(acct.elements)

        return events

    def fetch_account(self, account_id, by_key: bool = False):
        """
        Fetch a GUI parameter element by name or event key.

        Arguments:
            account_id (str): identifier used to find the correct account entry.

            by_key (bool): identifier is an element of the account entry [Default: use account entry name].
        """
        account = None
        for acct in self.accts:
            if by_key:
                elements = acct.elements
            else:
                elements = [acct.name]

            if account_id in elements:
                account = acct
                break

        if account is None:
            raise KeyError('account ID {ACCT} not found in list of {NAME} account entries'
                           .format(ACCT=account_id, NAME=self.name))

        return account

    def run_event(self, window, event, values):
        """
        Run a bank reconciliation event.
        """
        pd.set_option('display.max_columns', None)

        # Get elements of current account
        current_acct = self.current_account
        current_rule = self.name

        reconcile_key = self.key_lookup('Reconcile')
        expand_key = self.key_lookup('Expand')
        param_key = self.key_lookup('Parameters')
        cancel_key = self.key_lookup('Cancel')
        save_key = self.key_lookup('Save')
        next_key = self.key_lookup('Next')
        back_key = self.key_lookup('Back')
        acct_keys = [i for j in self.accts for i in j.elements]
        tab_bttn_keys = ['-HK_TAB{}-'.format(i) for i in range(1, 10)]
        tbl_bttn_keys = ['-HK_TBL_ADD-', '-HK_TBL_DEL-', '-HK_TBL_IMPORT-', '-HK_TBL_FILTER-', '-HK_TBL_OPTS-']

        # Run an account entry event.
        if event in acct_keys or event in tbl_bttn_keys:
            current_panel = self.current_panel
            acct = self.fetch_account(current_panel, by_key=True)

            ref_event = acct.run_event(window, event, values)
            if ref_event:
                ref_df = acct.ref_df
                print(ref_df)
                deleted_records = ref_df.loc[ref_df['IsDeleted'], ['RecordID']].squeeze()
                if isinstance(deleted_records, str):
                    deleted_records = [deleted_records]

                approved_records = ref_df.loc[ref_df['IsApproved'], ['RecordID']].squeeze()
                if isinstance(approved_records, str):
                    approved_records = [approved_records]

                print('records deleted from the {} reference dataframe are:'.format(acct.name))
                print(deleted_records)

                # Update all account reference dataframe for currently active panels
                for panel in self.panels:
                    if panel == current_panel:  # dont' attempt to update the same panel's reference dataframe
                        continue

                    ref_acct = self.fetch_account(panel, by_key=True)
                    assoc_ref_df = ref_acct.ref_df
                    assoc_ref_df.loc[assoc_ref_df['ReferenceID'].isin(deleted_records), ['IsDeleted']] = True
                    assoc_ref_df.loc[~assoc_ref_df['ReferenceID'].isin(deleted_records), ['IsDeleted']] = False
                    assoc_ref_df.loc[assoc_ref_df['ReferenceID'].isin(approved_records), ['IsApproved']] = True
                    assoc_ref_df.loc[~assoc_ref_df['ReferenceID'].isin(approved_records), ['IsApproved']] = False

                self.update_display(window)

        # The cancel button or cancel hotkey was pressed. If a reconciliation is in progress, reset the rule but stay
        # in the rule panel. If reconciliation is not in progress, return to home screen.
        elif event in (cancel_key, '-HK_ESCAPE-'):
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
        elif event == save_key or (event == '-HK_ENTER-' and not window[save_key].metadata['disabled']):
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
                        logger.info('AuditRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
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
        elif (event == next_key) or (event == '-HK_RIGHT-' and not window[next_key].metadata['disabled']):
            current_index = self.panels.index(self.current_panel)
            next_index = (current_index + 1) % len(self.panels)
            next_panel = self.panels[next_index]

            # Reset panel sizes
            next_acct = self.fetch_account(next_panel, by_key=True)
            next_acct.table.set_table_dimensions(window)
#            self.resize_elements(window)

            # Hide current panel and un-hide the following panel
            window[self.current_panel].update(visible=False)
            window[next_panel].update(visible=True)

            # Reset current panel attribute
            self.current_panel = next_panel

        # Back button pressed - display previous panel. Wrap-around to last panel if previous panel is less than the
        # number of items in the panel list
        elif (event == back_key) or (event == '-HK_LEFT-' and not window[back_key].metadata['disabled']):
            current_index = self.panels.index(self.current_panel)
            back_index = current_index - 1
            prev_panel = self.panels[back_index]

            # Reset panel sizes
            prev_acct = self.fetch_account(prev_panel, by_key=True)
            prev_acct.table.set_table_dimensions(window)
#            self.resize_elements(window)

            # Hide current panel and un-hide the previous panel
            window[self.current_panel].update(visible=False)
            window[prev_panel].update(visible=True)

            # Reset current panel attribute
            self.current_panel = prev_panel

        # Switch directly between panels using the tab button hotkeys
        elif event in tab_bttn_keys:
            # Determine which panel to act on
            tab_index = int(event[1:-1][-1]) - 1

            try:
                select_panel = self.panels[tab_index]
            except IndexError:
                return current_rule

            if not window[back_key].metadata['disabled']:
                # Hide current panel and un-hide the previous panel
                window[self.current_panel].update(visible=False)
                window[select_panel].update(visible=True)

                # Reset current panel attribute
                self.current_panel = select_panel

        # Set parameters button was pressed. Will open parameter settings window for user to input parameter values,
        # then load the relevant account record data
        elif event == param_key:
            # Get the parameter settings
            params = mod_win2.parameter_window(self.fetch_account(current_acct))

            # Load the account records
            if params:  # parameters were saved (selection not cancelled)
                pd.set_option('display.max_columns', None)
                for acct_name in params:
                    acct_params = params[acct_name]
                    if not acct_params:
                        continue

                    logger.debug('AuditRule {NAME}: loading database records for account {ACCT}'
                                 .format(NAME=self.name, ACCT=acct_name))
                    acct = self.fetch_account(acct_name)
                    data_loaded = acct.load_data(acct_params)
                    print(acct.table.df)
                    print(acct.table.df.dtypes)

                    if not data_loaded:
                        return self.reset_rule(window, current=True)
                    else:
                        self.panels.append(self.panel_keys[acct_name])

                    # Enable table action buttons
                    acct.table.enable(window)

                # Update the display
                self.update_display(window)

                # Enable elements
                window[save_key].update(disabled=False)
                if len(self.panels) > 1:
                    window[reconcile_key].update(disabled=False)

                    # Enable the navigation buttons
                    window[next_key].update(disabled=False)
                    window[next_key].metadata['disabled'] = False
                    window[back_key].update(disabled=False)
                    window[back_key].metadata['disabled'] = False

                # Mark that a reconciliation is currently in progress
                self.in_progress = True

        # Reconcile button was pressed. Will run the reconcile method to find associations with the current primary
        # account and any associated accounts with data.
        elif event == reconcile_key:
            expand_search = values[expand_key]

            try:
                self.reconcile_statement(expand_search)
            except Exception as e:
                msg = 'failed to reconcile statement - {ERR}'.format(ERR=e)
                logger.exception('AuditRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
                mod_win2.popup_error(msg)
            else:
                for acct_panel in self.panels:
                    acct = self.fetch_account(acct_panel, by_key=True)

                    self.update_display(window)
                    print('{} reference dataframe after reconciliation'.format(acct.name))
                    print(acct.ref_df)

                # Enable expanded search after an initial reconciliation is performed
                window[expand_key].update(disabled=False)

        return current_rule

    def reset_rule(self, window, current: bool = False):
        """
        Reset rule to default.
        """
        panel_key = self.element_key

        # Disable current panel
        window[self.current_panel].update(visible=False)
        window[panel_key].update(visible=False)
        window['-HOME-'].update(visible=True)

        # Disable the reconciliation button
        reconcile_key = self.key_lookup('Reconcile')
        expand_key = self.key_lookup('Expand')
        save_key = self.key_lookup('Save')
        window[reconcile_key].update(disabled=True)
        window[save_key].update(disabled=True)
        window[expand_key].update(disabled=True, value=False)

        # Disable the navigation buttons
        next_key = self.key_lookup('Next')
        back_key = self.key_lookup('Back')
        window[next_key].update(disabled=True)
        window[next_key].metadata['disabled'] = True
        window[back_key].update(disabled=True)
        window[back_key].metadata['disabled'] = True

        # Reset all account entries
        for acct in self.accts:
            acct.reset(window)

        self.in_progress = False
        self.panels = []

        if current:
            window['-HOME-'].update(visible=False)
            self.current_panel = self.panel_keys[self.current_account]
            window[self.current_panel].update(visible=True)
            window[panel_key].update(visible=True)

            return self.name
        else:
            # Reset the current account display
            self.current_panel = None
            self.current_account = None

            return None

    def layout(self, win_size: tuple = None):
        """
        Generate a GUI layout for the bank reconciliation rule.
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
        text_col = mod_const.TEXT_COL

        font = mod_const.MAIN_FONT
        font_h = mod_const.HEADER_FONT
        font_bold = mod_const.BOLD_FONT

        pad_el = mod_const.ELEM_PAD
        pad_v = mod_const.VERT_PAD
        pad_h = mod_const.HORZ_PAD
        pad_frame = mod_const.FRAME_PAD

        # Element sizes
        layout_height = height * 0.8
        frame_height = layout_height * 0.70
        panel_height = frame_height - 80

        layout_pad = 120
        win_diff = width - mod_const.WIN_WIDTH
        layout_pad = layout_pad + (win_diff / 5)

        frame_width = width - layout_pad if layout_pad > 0 else width
        panel_width = frame_width - 36

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
        reconcile_key = self.key_lookup('Reconcile')
        expand_key = self.key_lookup('Expand')
        header = [sg.Col([[sg.Button('', key=param_key, image_data=mod_const.PARAM_ICON, image_size=(28, 28),
                                     button_color=(text_col, bg_col), tooltip='Set parameters')]],
                         expand_x=True, justification='l', background_color=bg_col),
                  sg.Col([[sg.Button('Reconcile', key=reconcile_key, pad=((0, pad_el), 0), disabled=True,
                                     button_color=(bttn_text_col, bttn_bg_col),
                                     disabled_button_color=(disabled_text_col, disabled_bg_col),
                                     tooltip='Run reconciliation'),
                           sg.Checkbox('Expand search', key=expand_key, background_color=bg_col, font=font,
                                       disabled=True)]],
                         pad=(0, 0), justification='r', background_color=bg_col)]

        # Panels
        panels = []
        for acct in self.accts:
            layout = acct.layout(size=(panel_width, panel_height))
            panels.append(layout)

        pw_key = self.key_lookup('PanelWidth')
        ph_key = self.key_lookup('PanelHeight')
        panel_layout = [[sg.Canvas(key=pw_key, size=(panel_width, 0), background_color=bg_col)],
                        [sg.Canvas(key=ph_key, size=(0, panel_height), background_color=bg_col),
                         sg.Pane(panels, orientation='horizontal', show_handle=False, border_width=0, relief='flat')]]

        # Main Panel layout
        main_key = self.key_lookup('Panel')
        main_layout = sg.Col(panel_layout, pad=(0, 0), background_color=bg_col, expand_x=True,
                             key=main_key, vertical_alignment='t', visible=True, expand_y=True, scrollable=True,
                             vertical_scroll_only=True)

        # Navigation elements
        next_key = self.key_lookup('Next')
        back_key = self.key_lookup('Back')
        nav_layout = sg.Col(
            [[sg.Button('', key=back_key, image_data=mod_const.LEFT_ICON, image_size=mod_const.BTTN_SIZE,
                        pad=((0, pad_el), 0), disabled=True,
                        tooltip='Return to audit ({})'.format(back_shortcut), metadata={'disabled': True}),
              sg.Button('', key=next_key, image_data=mod_const.RIGHT_ICON, image_size=mod_const.BTTN_SIZE,
                        pad=(pad_el, 0), disabled=True, tooltip='Review audit ({})'.format(next_shortcut),
                        metadata={'disabled': True})]],
            pad=(0, 0), background_color=bg_col, element_justification='c', expand_x=True)

        # Control elements
        cancel_key = self.key_lookup('Cancel')
        save_key = self.key_lookup('Save')
        bttn_layout = [sg.Col([
            [sg.Button('', key=cancel_key, image_data=mod_const.CANCEL_ICON,
                       image_size=mod_const.BTTN_SIZE, pad=((0, pad_el), 0), disabled=False,
                       tooltip='Return to home screen ({})'.format(cancel_shortcut))]
        ], pad=(0, (pad_v, 0)), justification='l', expand_x=True),
            sg.Col([
                [sg.Button('', key=save_key, image_data=mod_const.SAVE_ICON, image_size=mod_const.BTTN_SIZE,
                           pad=((pad_el, 0), 0), disabled=True,
                           tooltip='Save results ({})'.format(save_shortcut),
                           metadata={'disabled': True})]
            ], pad=(0, (pad_v, 0)), justification='r', element_justification='r')]

        fw_key = self.key_lookup('FrameWidth')
        fh_key = self.key_lookup('FrameHeight')
        frame_layout = [sg.Frame('', [
            [sg.Canvas(key=fw_key, size=(frame_width, 0), background_color=bg_col)],
            [sg.Col([[title_layout]], pad=(0, 0), justification='l', background_color=header_col, expand_x=True)],
            [sg.Canvas(key=fh_key, size=(0, frame_height), background_color=bg_col),
             sg.Col([header, [sg.HorizontalSeparator(pad=(0, pad_v), color=mod_const.HEADER_COL)], [main_layout],
                     [sg.HorizontalSeparator(pad=(0, pad_v), color=mod_const.HEADER_COL)], [nav_layout]],
                    pad=(pad_frame, pad_frame), background_color=bg_col, expand_x=True, expand_y=True)]],
                                 background_color=bg_col, relief='raised')]

        layout = [frame_layout, bttn_layout]

        return sg.Col(layout, key=self.element_key, visible=False)

    def resize_elements(self, window, win_size: tuple = None):
        """
        Resize Bank Reconciliation Rule GUI elements.
        """
        if win_size:
            width, height = win_size
        else:
            width, height = window.size  # current window size (width, height)

        # For every five-pixel increase in window size, increase frame size by one
        #layout_pad = 100  # default padding between the window and border of the frame
        #win_diff = width - mod_const.WIN_WIDTH
        #layout_pad = layout_pad + int(win_diff / 5)

        #frame_width = width - layout_pad if layout_pad > 0 else width
        frame_width = width - 40
        panel_width = frame_width - 36  # padding + scrollbar width

        width_key = self.key_lookup('FrameWidth')
        window[width_key].set_size((frame_width, None))

        pw_key = self.key_lookup('PanelWidth')
        window[pw_key].set_size((panel_width, None))

        #layout_height = height * 0.85  # height of the container panel, including buttons
        layout_height = height - 80  # height of the container panel (minus padding and toolbar height)
        frame_height = layout_height - 120  # minus the approximate height of the button row and title bar, with padding
        panel_height = frame_height - 20  # minus top and bottom padding

        height_key = self.key_lookup('FrameHeight')
        window[height_key].set_size((None, frame_height))

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

    def reconcile_statement(self, expand: bool = False):
        """
        Run the primary Bank Reconciliation rule algorithm for the record tab.

        Arguments:
            expand (bool): expand the search by ignoring association parameters designated as expanded [Default: False].

        Returns:
            success (bool): bank reconciliation was successful.
        """
        # pd.set_option('display.max_columns', None)
        ref_cols = ['ReferenceID', 'ReferenceDate', 'ReferenceType', 'ReferenceNotes', 'IsApproved', 'IsHardLink',
                    'IsChild', 'IsDeleted']

        # Fetch primary account and prepare data
        acct = self.fetch_account(self.current_account)
        logger.info('BankRule {NAME}: reconciling account {ACCT}'.format(NAME=self.name, ACCT=acct.name))
        logger.debug('BankRule {NAME}: expanded search is set to {VAL}'
                     .format(NAME=self.name, VAL=('on' if expand else 'off')))

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
        df = df.drop(df[~df['ReferenceID'].isna()].index, axis=0)

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

            # Create the account-association account column mapping from the association rules
            assoc_rules = transactions[assoc_acct_name]['AssociationParameters']
            colmap = {}
            for acct_colname in assoc_rules:
                if acct_colname not in header:  # attempting to use a column that was not defined in the table config
                    msg = 'AssociationRule column {COL} is missing from the account data'.format(COL=acct_colname)
                    logger.warning('BankRule: {NAME}: {MSG}'.format(NAME=acct.name, MSG=msg))
                    del assoc_rules[acct_colname]

                    continue

                rule_entry = assoc_rules[acct_colname]
                assoc_colname = rule_entry['Column']
                if assoc_colname not in assoc_header:
                    msg = 'AssociationRule reference column {COL} is missing from transaction account {ACCT} data' \
                        .format(COL=assoc_colname, ACCT=assoc_acct_name)
                    logger.warning('BankRule: {NAME}: {MSG}'.format(NAME=acct.name, MSG=msg))
                    del assoc_rules[acct_colname]

                    continue

                colmap[assoc_colname] = acct_colname

            colmap[assoc_acct.table.id_column] = "_RecordID_"

            # Remove all but the relevant columns from the association account table
            assoc_df = assoc_df[list(colmap)]

            # Change column names of the association account table using the column map
            assoc_df.rename(columns=colmap, inplace=True)

            # Add association account name and record type to the association account table
            assoc_df['_Account_'] = assoc_acct_name
            assoc_df['_RecordType_'] = assoc_acct.record_type

            # Store column mappers for fast recall during matching
            assoc_ref_maps[assoc_acct_name] = assoc_rules

            # Concatenate association tables
            merged_df = merged_df.append(assoc_df, ignore_index=True)

        #        print(merged_df)
        #        print(merged_df.dtypes)

        # Iterate over record rows, attempting to find matches in associated transaction records
        logger.debug('AuditRule {NAME}: attempting to find associations for account {ACCT} records'
                     .format(NAME=self.name, ACCT=acct.name))
        nfound = 0
        for row in df.itertuples():
            record_id = getattr(row, id_column)

            # Attempt to find a match for the record to each of the associated transaction accounts
            matches = pd.DataFrame(columns=merged_df.columns)
            for assoc_acct_name in assoc_ref_maps:
                # Subset merged df to include only the association records with the given account name
                assoc_df = merged_df[merged_df['_Account_'] == assoc_acct_name]

                # Select the columns that will be used to compare records
                cols = list(assoc_ref_maps[assoc_acct_name])

                # Find exact matches between account record and the associated account records using relevant columns
                row_vals = [getattr(row, i) for i in cols]
                acct_matches = assoc_df[assoc_df[cols].eq(row_vals).all(axis=1)]
                matches = matches.append(acct_matches)

            # Check matches and find correct association
            nmatch = matches.shape[0]
            if nmatch == 0 and expand is True:  # no matching entries in the merged dataset
                # Attempt to find matches using only the core columns
                matches = pd.DataFrame(columns=merged_df.columns)
                expanded_cols = []
                for assoc_acct_name in assoc_ref_maps:
                    # Subset merged df to include only the association records with the given account name
                    assoc_df = merged_df[merged_df['_Account_'] == assoc_acct_name]

                    # Select columns that will be used to compare records
                    assoc_rules = assoc_ref_maps[assoc_acct_name]
                    cols = []
                    for col in assoc_rules:
                        rule_entry = assoc_rules[col]
                        if rule_entry['Expand']:
                            expanded_cols.append(col)
                            continue

                        cols.append(col)

                    # Find exact matches between account record and the associated account records using relevant cols
                    row_vals = [getattr(row, i) for i in cols]
                    acct_matches = assoc_df[assoc_df[cols].eq(row_vals).all(axis=1)]
                    matches = matches.append(acct_matches)

                nmatch = matches.shape[0]
                if nmatch == 0:  # no matches found given the parameters supplied
                    continue

                elif nmatch == 1:  # found one exact match using the column subset
                    nfound += 1

                    results = matches.iloc[0]
                    assoc_acct_name = results['_Account_']
                    ref_id = results['_RecordID_']
                    ref_type = results['_RecordType_']

                    logger.debug('AuditRule {NAME}: associating {ACCT} record {REFID} to account record {ID} from an '
                                 'expanded search'.format(NAME=self.name, ACCT=assoc_acct_name, REFID=ref_id,
                                                          ID=record_id))

                    # Remove the found match from the dataframe of unmatched associated account records
                    merged_df.drop(matches.index.tolist()[0], inplace=True)

                    # Determine appropriate warning for the expanded search
                    assoc_rules = assoc_ref_maps[assoc_acct_name]
                    warning = ["Potential false positive: the association is the result of an expanded search"]
                    for column in expanded_cols:
                        if getattr(row, column) != results[column]:
                            try:
                                warning.append('- {}'.format(assoc_rules[column]['Description']))
                            except KeyError:
                                logger.warning('BankRecordTab {NAME}: no description provided for expanded '
                                               'association rule {COL}'.format(NAME=self.name, COL=column))

                    warning = '\n'.join(warning)

                    # Insert the reference into the account records reference dataframe
                    ref_values = [ref_id, datetime.datetime.now(), ref_type, warning, False, False, False, False]
                    acct.ref_df.loc[acct.ref_df['RecordID'] == record_id, ref_cols] = ref_values

                    # Insert the reference into the associated account's reference dataframe
                    assoc_acct = self.fetch_account(assoc_acct_name)
                    ref_values = [record_id, datetime.datetime.now(), acct.record_type, warning, False, False, False,
                                  False]
                    assoc_acct.ref_df.loc[assoc_acct.ref_df['RecordID'] == ref_id, ref_cols] = ref_values

                elif nmatch > 1:  # too many matches
                    msg = 'found more than one expanded match for account {ACCT} record "{RECORD}"' \
                        .format(ACCT=self.current_account, RECORD=record_id)
                    logger.debug('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
                    mod_win2.popup_notice(msg)

                    continue

            elif nmatch == 1:  # found one exact match
                nfound += 1

                results = matches.iloc[0]
                ref_id = results['_RecordID_']
                ref_type = results['_RecordType_']
                assoc_acct_name = results['_Account_']

                logger.debug('AuditRule {NAME}: associating {ACCT} record {REFID} to account record {ID}'
                             .format(NAME=self.name, ACCT=assoc_acct_name, REFID=ref_id, ID=record_id))

                # Remove the found match from the dataframe of unmatched associated account records
                merged_df.drop(matches.index.tolist()[0], inplace=True)

                # Insert the reference into the account records reference dataframe
                ref_values = [ref_id, datetime.datetime.now(), ref_type, None, True, False, False, False]
                acct.ref_df.loc[acct.ref_df['RecordID'] == record_id, ref_cols] = ref_values

                # Insert the reference into the associated account's reference dataframe
                assoc_acct = self.fetch_account(assoc_acct_name)
                ref_values = [record_id, datetime.datetime.now(), acct.record_type, None, True, False, False, False]
                assoc_acct.ref_df.loc[assoc_acct.ref_df['RecordID'] == ref_id, ref_cols] = ref_values

            elif nmatch > 1:  # too many matches
                nfound += 1
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
                ref_values = [ref_id, datetime.datetime.now(), ref_type, warning, False, False, False, False]
                acct.ref_df.loc[acct.ref_df['RecordID'] == record_id, ref_cols] = ref_values

                # Insert the reference into the associated account's reference dataframe
                assoc_acct = self.fetch_account(assoc_acct_name)
                ref_values = [record_id, datetime.datetime.now(), acct.record_type, warning, False, False, False, False]
                assoc_acct.ref_df.loc[assoc_acct.ref_df['RecordID'] == ref_id, ref_cols] = ref_values

        logger.info('AuditRule {NAME}: found {NMATCH} associations out of {NTOTAL} unreferenced account {ACCT} records'
                    .format(NAME=self.name, NMATCH=nfound, NTOTAL=df.shape[0], ACCT=acct.name))

        return True

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

        success = user.write_db(sstrings, psets)

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


class AccountEntry:
    """
    Bank record tab.

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

        ref_map (dict): reference columns to add to the records table along with their table aliases.

        transactions (dict): source and sink dynamics of the account.
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
                         ('Panel',)]

        try:
            self.title = entry['Title']
        except KeyError:
            self.title = name

        try:
            self.record_type = entry['RecordType']
        except KeyError:
            msg = 'AccountEntry {NAME}: missing required configuration parameter "RecordType".'.format(NAME=name)
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
            self.table = mod_elem.RecordTable(name, entry['DisplayTable'])
        except KeyError:
            self.table = mod_elem.RecordTable(name, record_entry.import_table)
        self.elements += self.table.elements

        try:
            self.parameters = entry['ImportParameters']
        except KeyError:
            msg = 'no import parameters specified'
            logger.warning('AccountEntry {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            self.parameters = {}

        try:
            ref_map = entry['ReferenceMap']
        except KeyError:
            self.ref_map = {}
        else:
            ref_cols = ['ReferenceID', 'ReferenceDate', 'ReferenceType', 'ReferenceNotes', 'IsApproved', 'IsHardLink',
                        'IsChild', 'IsDeleted']
            self.ref_map = {}
            for column in ref_map:
                if column not in ref_cols:
                    msg = 'reference map column {COL} is not a valid reference column name'.format(COL=column)
                    logger.warning('AccountEntry {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                    continue

                self.ref_map[column] = ref_map[column]

        try:
            transactions = entry['Transactions']
        except KeyError:
            self.transactions = {}
        else:
            self.transactions = {}
            for transaction_acct in transactions:
                cnfg_entry = transactions[transaction_acct]
                trans_entry = {}
                if 'TransactionType' not in cnfg_entry:
                    msg = 'AccountEntry {NAME}: Transaction account {ACCT} is missing required parameter ' \
                          '"TransactionType"'.format(NAME=name, ACCT=transaction_acct)
                    logger.error(msg)

                    continue
                else:
                    trans_entry['TransactionType'] = cnfg_entry['TransactionType']

                if 'AssociationParameters' not in cnfg_entry:
                    msg = 'AccountEntry {NAME}: Transaction account {ACCT} is missing required parameter ' \
                          '"AssociationParameters"'.format(NAME=name, ACCT=transaction_acct)
                    logger.error(msg)

                    continue
                else:
                    trans_entry['AssociationParameters'] = cnfg_entry['AssociationParameters']

                if 'ImportParameters' not in cnfg_entry:
                    trans_entry['ImportParameters'] = {}
                else:
                    trans_entry['ImportParameters'] = cnfg_entry['ImportParameters']

                if 'Title' not in cnfg_entry:
                    trans_entry['Title'] = transaction_acct
                else:
                    trans_entry['Title'] = cnfg_entry['Title']

                self.transactions[transaction_acct] = trans_entry

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
            logger.warning('AccountEntry {NAME}: component "{COMP}" not found in list of elements'
                           .format(NAME=self.name, COMP=component))
            key = None

        return key

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

        table_keys = self.table.elements
        tbl_bttn_keys = ['-HK_TBL_ADD-', '-HK_TBL_DEL-', '-HK_TBL_IMPORT-', '-HK_TBL_FILTER-', '-HK_TBL_OPTS-']

        reference_event = False
        # Run a record table event.
        if event in table_keys or event in tbl_bttn_keys:
            table = self.table
            tbl_key = self.table.key_lookup('Element')
            delete_key = self.table.key_lookup('Delete')
            can_delete = (not window[delete_key].metadata['disabled'] and window[delete_key].metadata['visible'])

            # Record was selected for opening
            if event == tbl_key:
                association_rule = self.association_rule
                reference_event = True
                ref_df = self.ref_df

                # Close options panel, if open
                table.set_table_dimensions(window)

                # Find row selected by user
                try:
                    select_row_index = values[event][0]
                except IndexError:  # user double-clicked too quickly
                    msg = 'table row could not be selected'
                    logger.debug('DataTable {NAME}: {MSG}'.format(NAME=table.name, MSG=msg))
                else:
                    # Get the real index of the selected row
                    try:
                        index = table.index_map[select_row_index]
                    except KeyError:
                        index = select_row_index

                    logger.debug('DataTable {NAME}: opening record at real index {IND}'
                                 .format(NAME=table.name, IND=index))
                    if table.modifiers['open'] is True:
                        record = table.load_record(index, level=0, savable=False, references={association_rule: ref_df})
                        if record is None:
                            msg = 'unable to update references for record at index {IND} - no record was returned'\
                                .format(IND=index)
                            logger.error('DataTable {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                            return False

                        # Update reference values
                        if table.modifiers['edit']:  # only update references if table is editable
                            record_id = record.record_id()
                            for refbox in record.references:
                                if refbox.association_rule != association_rule:
                                    continue

                                ref_values = refbox.export_reference().drop(labels=['RecordID', 'RecordType'])
                                print('updating record {} reference with values:'.format(record_id))
                                print(ref_values)
                                try:
                                    ref_df.loc[ref_df['RecordID'] == record_id, ref_values.index.tolist()] = ref_values.tolist()
                                except KeyError as e:
                                    msg = 'failed to update reference {REF} for record {ID}'.format(REF=refbox.name, ID=record_id)
                                    logger.error('DataTable {NAME}: {MSG} - {ERR}'.format(NAME=self.name, MSG=msg, ERR=e))

            elif event == delete_key or (event == '-HK_TBL_DEL-' and can_delete):
                reference_event = True

                # Find rows selected by user for deletion
                select_row_indices = values[tbl_key]

                # Get the real indices of the selected rows
                try:
                    indices = [table.index_map[i] for i in select_row_indices]
                except KeyError:
                    msg = 'missing index information for one or more rows selected for deletion'.format(NAME=self.name)
                    logger.warning('DataTable {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
                    mod_win2.popup_notice(msg)
                    indices = []

                self.delete_rows(indices)

            else:
                table.run_event(window, event, values)

        return reference_event

    def layout(self, size):
        """
        GUI layout for the bank record tab.
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
        Resize the account panel.
        """
        width, height = size

        # Reset table size
        tbl_width = width - 30  # includes padding on both sides and scroll bar
        tbl_height = int(height * 0.55)
        self.table.resize(window, size=(tbl_width, tbl_height), row_rate=40)

    def merge_references(self, df: pd.DataFrame = None):
        """
        Merge the records table and the reference table on any reference map columns.

        Arguments:
            df (DataFrame): merge references with the provided records dataframe [Default: use full records dataframe].

        Returns:
            df (DataFrame): dataframe of records merged with their corresponding reference entries.
        """
        pd.set_option('display.max_columns', None)

        ref_map = self.ref_map
        ref_df = self.ref_df.copy()

        if df is None:
            df = self.table.data()

        # Remove references that were deleted
        print('reference df to merge with the records df:')
        ref_columns = ['ReferenceID', 'ReferenceDate', 'ReferenceType', 'ReferenceNotes', 'IsApproved']
        ref_df.loc[ref_df['IsDeleted'], ref_columns] = [np.nan, np.nan, np.nan, np.nan, False]
        print(ref_df)
        print(ref_df.dtypes)

        # Set index to record ID for updating
        df.set_index('RecordID', inplace=True)
        ref_df.set_index('RecordID', inplace=True)

        # Rename reference columns to record columns using the reference map
        ref_df = ref_df[list(ref_map)].rename(columns=ref_map)
        print('reference df after column subsetting:')
        print(ref_df)

        # Update record reference columns
#        df.update(ref_df)
#        df.reset_index(inplace=True)
        df = df.drop(columns=ref_df.columns).join(ref_df)
        df.reset_index(inplace=True)
        print('dataframe after updating on record id:')
        print(df)

        return df

    def delete_rows(self, indices):
        """
        Delete references using selected table indices.

        Arguments:
            indices (list): list of row indices to remove references from.

        Returns:
            None
        """
        ref_df = self.ref_df
        df = self.table.df.copy()

        select_df = df.iloc[indices]

        # Get record IDs of selected rows
        record_ids = select_df[self.table.id_column].tolist()
        logger.info('DataTable {TBL}: removing references for records {IDS}'
                    .format(TBL=self.name, IDS=record_ids))

        # Set the deleted column of the reference entries corresponding to the selected records to True.
        ref_df.loc[ref_df['RecordID'].isin(record_ids), ['IsDeleted']] = True

        return None

    def update_display(self, window):
        """
        Update the panel's record table display.
        """
        # Merge records and references dataframes
        self.table.df = self.merge_references()
        self.table.df = self.table.set_conditional_values()

        # Update the display table
        self.table.update_display(window)

    def load_data(self, parameters):
        """
        Load record and reference data from the database based on the supplied parameter set.

        Arguments:
            parameters (list): list of data parameters to filter the records database table on.

        Returns:
            success (bool): records and references were loaded successully.
        """
        pd.set_option('display.max_columns', None)

        record_type = self.record_type
        record_entry = settings.records.fetch_rule(record_type)

        # Prepare the database query statement
        try:
            df = record_entry.import_records(params=parameters, import_rules=self.import_rules)
        except Exception as e:
            msg = 'failed to import data from the database'
            logger.exception('AccountEntry {NAME}: {MSG} - {ERR}'.format(NAME=self.name, MSG=msg, ERR=e))
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
            logger.exception('AccountEntry {NAME}: {MSG} - {ERR}'.format(NAME=self.name, MSG=msg, ERR=e))
            mod_win2.popup_error('{MSG} -  see log for details'.format(MSG=msg))

            return False

        print('imported records:')
        print(df.head)
        print('imported references:')
        print(import_df)

        ref_df = pd.merge(df.loc[:, ['RecordID']], import_df, how='left', on='RecordID')
        ref_df['RecordType'].fillna(record_type, inplace=True)
        print('reference df before changing types:')
        print(ref_df)

        bool_columns = ['IsChild', 'IsHardLink', 'IsApproved', 'IsDeleted']
        ref_df[bool_columns] = ref_df[bool_columns].fillna(False)
        print('reference df after filling boolean na values:')
        ref_df = ref_df.astype({i: np.bool for i in bool_columns})
        print(ref_df)

        self.ref_df = ref_df

        print('reference dataframe after merging')
        print(self.ref_df)
        print(self.ref_df.dtypes)

        return True
