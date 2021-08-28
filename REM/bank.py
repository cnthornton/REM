"""
REM bank reconciliation configuration classes and objects.
"""

import datetime
from random import randint

import PySimpleGUI as sg
import pandas as pd

import REM.constants as mod_const
import REM.database as mod_db
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

        menu_title (str): bank reconciliation rule title.

        menu_flags (dict): submenu flags that change the initial behavior of the rule.

        permissions (str): permissions required to view the accounting method. Default: user.

        accts (list): list of account entry objects.
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
            self.elements += acct.elements

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

    def fetch_account(self, account_id, by_key: bool = False):
        """
        Fetch a GUI parameter element by name or event key.
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

        # Run event from a current primary account element. Pass on to account class.
        if event in acct_keys:
            acct = self.fetch_account(event, by_key=True)
            acct.run_event(window, event, values)

        # Run a table key event. Table event should be sent to the table in the current panel.
        if event in tbl_bttn_keys:
            # Determine which panel to act on
            current_panel = self.current_panel
            acct = self.fetch_account(current_panel, by_key=True)
            acct.run_event(window, event, values)

        # The cancel button or cancel hotkey was pressed. If a reconciliation is in progress, reset the rule but stay
        # in the rule panel. If reconciliation is not in progress, return to home screen.
        if event in (cancel_key, '-HK_ESCAPE-'):
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
        if event == save_key or (event == '-HK_ENTER-' and not window[save_key].metadata['disabled']):
            # Get output file from user
            acct = self.fetch_account(current_acct)
            default_title = acct.title + '.xlsx'
            outfile = sg.popup_get_file('', title='Save As', default_path=default_title, save_as=True,
                                        default_extension='xlsx', no_window=True,
                                        file_types=(
                                            ('XLS - Microsoft Excel', '*.xlsx'), ('Comma-Separated Values', '*.csv'))
                                        )

            if not outfile:
                msg = 'Please select an output file before continuing'
                mod_win2.popup_error(msg)
            else:
                # Save records to the program database
                try:
                    save_status = self.save_records()
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
        if (event == next_key) or (event == '-HK_RIGHT-' and not window[next_key].metadata['disabled']):
            current_index = self.panels.index(self.current_panel)
            next_index = (current_index + 1) % len(self.panels)
            next_panel = self.panels[next_index]

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

            # Hide current panel and un-hide the previous panel
            window[self.current_panel].update(visible=False)
            window[prev_panel].update(visible=True)

            # Reset current panel attribute
            self.current_panel = prev_panel

        # Switch directly between panels using the tab button hotkeys
        if event in tab_bttn_keys:
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
        if event == param_key:
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

                # Update the display
                self.update_display(window)

                # Enable elements
                window[save_key].update(disabled=False)
                if len(self.panels) > 1:
                    window[reconcile_key].update(disabled=False)
                    window[expand_key].update(disabled=False)

                    # Enable the navigation buttons
                    window[next_key].update(disabled=False)
                    window[next_key].metadata['disabled'] = False
                    window[back_key].update(disabled=False)
                    window[back_key].metadata['disabled'] = False

                # Mark that a reconciliation is currently in progress
                self.in_progress = True

        # Reconcile button was pressed. Will run the reconcile method to find associations with the current primary
        # account and any associated accounts with data.
        if event == reconcile_key:
            expand_search = values[expand_key]

            try:
                self.reconcile_statement(expand_search)
            except Exception as e:
                msg = 'failed to reconcile statement - {ERR}'.format(ERR=e)
                logger.exception('AuditRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
                mod_win2.popup_error(msg)
            else:
#                pd.set_option('display.max_columns', None)
                for acct_panel in self.panels:
                    acct = self.fetch_account(acct_panel, by_key=True)
                    acct.table.df = acct.table.set_conditional_values()

                    self.update_display(window)
 #                   print(acct.table.df)

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
#        main_layout = sg.Col([header,
#                              [sg.HorizontalSeparator(pad=(0, pad_v), color=mod_const.HEADER_COL)],
#                              [sg.Col(panel_layout, pad=(0, 0), background_color=bg_col, expand_x=True)]],
#                             key=main_key, pad=(0, 0), background_color=bg_col,
#                             vertical_alignment='t', visible=True, expand_y=True, expand_x=True, scrollable=True,
#                             vertical_scroll_only=True)
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
        #        frame_layout = [sg.Frame('', [
        #            [sg.Canvas(key=fw_key, size=(frame_width, 0), background_color=bg_col)],
        #            [sg.Col([[title_layout]], pad=(0, 0), justification='l', background_color=header_col, expand_x=True)],
        #            [sg.Col([[sg.Canvas(key=fh_key, size=(0, frame_height), background_color=bg_col)]], vertical_alignment='t'),
        #             sg.Col([[main_layout]], pad=((pad_frame, pad_v), pad_v), background_color=bg_col, vertical_alignment='t',
        #                    expand_x=True, expand_y=True, scrollable=True, vertical_scroll_only=True),
        #             sg.Col([nav_layout], background_color=bg_col, element_justification='c', expand_x=True)]],
        #                                 background_color=bg_col, relief='raised')]
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
        layout_pad = 100  # default padding between the window and border of the frame
        win_diff = width - mod_const.WIN_WIDTH
        layout_pad = layout_pad + int(win_diff / 5)

        frame_width = width - layout_pad if layout_pad > 0 else width
        panel_width = frame_width - 36  # padding + scrollbar width

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
        """
        # Fetch primary account and prepare data
        acct = self.fetch_account(self.current_account)
        logger.info('AuditRule {NAME}: reconciling account {ACCT}'.format(NAME=self.name, ACCT=acct.name))
        logger.debug('AuditRule {NAME}: expanded search is set to {VAL}'
                     .format(NAME=self.name, VAL=('on' if expand else 'off')))

        refmap = acct.refmap
        table = acct.table
        id_column = table.id_column
        df = table.data()
        header = df.columns.tolist()

        # Filter out records already associated with transaction account records
        logger.debug('AuditRule {NAME}: dropping {ACCT} records that are already associated with a transaction '
                     'account record'.format(NAME=self.name, ACCT=acct.name))
        df = df.drop(df[~df[refmap['ReferenceID']].isna()].index, axis=0)

        # Define the fields that will be included in the merged association account table
        required_fields = ["_Account_", "_RecordID_", "_RecordType_"]

        # Initialize a merged association account table
        logger.debug('AuditRule {NAME}: creating the merged accounts table'.format(NAME=self.name, ACCT=acct.name))
        merged_df = pd.DataFrame(columns=required_fields)

        # Fetch associated account data
        transactions = acct.transactions
        assoc_ref_maps = {}
        for assoc_acct_name in transactions:
            assoc_acct = self.fetch_account(assoc_acct_name)
            logger.debug('AuditRule {NAME}: adding data from the association account {ACCT} to the merged table'
                         .format(NAME=self.name, ACCT=assoc_acct.name))

            assoc_ref_map = assoc_acct.refmap
            assoc_df = assoc_acct.table.data()

            if assoc_df.empty:  # no records loaded to match to, so skip
                continue

            # Filter association account records that are already associated with a record
            ref_id_col = assoc_ref_map['ReferenceID']
            drop_conds = ~assoc_df[ref_id_col].isna()
            drop_labels = assoc_df[drop_conds].index
            assoc_df = assoc_df.drop(drop_labels, axis=0)
            assoc_header = assoc_df.columns.tolist()

            # Create the account-association account column mapping from the association rules
            assoc_rules = transactions[assoc_acct_name]['AssociationRules']
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
            assoc_ref_maps[assoc_acct_name] = {'RefMap': assoc_ref_map, 'RuleMap': assoc_rules}

            # Concatenate association tables
            merged_df = merged_df.append(assoc_df, ignore_index=True)

        #        pd.set_option('display.max_columns', None)
        #        print(merged_df)
        #        print(merged_df.dtypes)

        # Iterate over record rows, attempting to find matches in associated transaction records
        logger.debug('AuditRule {NAME}: attempting to find associations for account {ACCT} records'
                     .format(NAME=self.name, ACCT=acct.name))
        nfound = 0
        for row in df.itertuples():
            index = getattr(row, 'Index')
            record_id = getattr(row, id_column)

            # Attempt to find a match for the record to each of the associated transaction accounts
            matches = pd.DataFrame(columns=merged_df.columns)
            for assoc_acct_name in assoc_ref_maps:
                # Filter merged df by account name
                assoc_df = merged_df[merged_df['_Account_'] == assoc_acct_name]

                # Select columns that will be used to compare records
                cols = list(assoc_ref_maps[assoc_acct_name]['RuleMap'])

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
                    # Filter merged df by account name
                    assoc_df = merged_df[merged_df['_Account_'] == assoc_acct_name]

                    # Select columns that will be used to compare records
                    assoc_rules = assoc_ref_maps[assoc_acct_name]['RuleMap']
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
                    assoc_rules = assoc_ref_maps[assoc_acct_name]['RuleMap']
                    warning = ["Potential false positive: the association is the result of an expanded search"]
                    for column in expanded_cols:
                        if getattr(row, column) != results[column]:
                            try:
                                warning.append('- {}'.format(assoc_rules[column]['Description']))
                            except KeyError:
                                logger.warning('BankRecordTab {NAME}: no description provided for expanded '
                                               'association rule {COL}'.format(NAME=self.name, COL=column))

                    warning = '\n'.join(warning)

                    # Add the reference information to the account record's table entry
                    ref_cols = [refmap['ReferenceID'], refmap['ReferenceType'], refmap['ReferenceDate']]
                    ref_values = [ref_id, ref_type, datetime.datetime.now()]
                    if 'Warnings' in refmap and refmap['Warnings']:
                        ref_cols.append(refmap['Warnings'])
                        ref_values.append(warning)

                    acct.table.df.at[index, ref_cols] = ref_values

                    # Add the reference information to the referenced record's table entry
                    assoc_acct = self.fetch_account(assoc_acct_name)
                    assoc_refmap = assoc_acct.refmap
                    assoc_ref_cols = [assoc_refmap['ReferenceID'], assoc_refmap['ReferenceType'],
                                      assoc_refmap['ReferenceDate']]
                    assoc_ref_values = [record_id, acct.record_type, datetime.datetime.now()]
                    if 'Warnings' in refmap and refmap['Warnings']:
                        assoc_ref_cols.append(refmap['Warnings'])
                        assoc_ref_values.append(warning)

                    assoc_acct.table.df.loc[assoc_acct.table.df[assoc_acct.table.id_column] == ref_id,
                                            assoc_ref_cols] = assoc_ref_values

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

                # Add the reference information to the account record's table entry
                ref_cols = [refmap['ReferenceID'], refmap['ReferenceType'], refmap['ReferenceDate']]
                ref_values = [ref_id, ref_type, datetime.datetime.now()]
                if 'IsApproved' in refmap and refmap['IsApproved']:
                    ref_cols.append(refmap['IsApproved'])
                    ref_values.append(True)

                acct.table.df.at[index, ref_cols] = ref_values

                # Add the reference information to the referenced record's table entry
                assoc_acct = self.fetch_account(assoc_acct_name)
                assoc_refmap = assoc_acct.refmap
                assoc_ref_cols = [assoc_refmap['ReferenceID'], assoc_refmap['ReferenceType'],
                                  assoc_refmap['ReferenceDate']]
                assoc_ref_values = [record_id, acct.record_type, datetime.datetime.now()]
                if 'IsApproved' in assoc_refmap and assoc_refmap['IsApproved']:
                    assoc_ref_cols.append(refmap['IsApproved'])
                    assoc_ref_values.append(True)

                assoc_acct.table.df.loc[assoc_acct.table.df[assoc_acct.table.id_column] == ref_id, assoc_ref_cols] = \
                    assoc_ref_values

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

                # Add the reference information to the account record's table entry
                ref_cols = [refmap['ReferenceID'], refmap['ReferenceType'], refmap['ReferenceDate']]
                ref_values = [ref_id, ref_type, datetime.datetime.now()]
                if 'Warnings' in refmap and refmap['Warnings']:
                    ref_cols.append(refmap['Warnings'])
                    ref_values.append(warning)

                acct.table.df.at[index, ref_cols] = ref_values

                # Add the reference information to the referenced record's table entry
                assoc_acct = self.fetch_account(assoc_acct_name)
                assoc_refmap = assoc_acct.refmap
                assoc_ref_cols = [assoc_refmap['ReferenceID'], assoc_refmap['ReferenceType'],
                                  assoc_refmap['ReferenceDate']]
                assoc_ref_values = [record_id, acct.record_type, datetime.datetime.now()]
                assoc_acct.table.df.loc[assoc_acct.table.df[assoc_acct.table.id_column] == ref_id, assoc_ref_cols] = \
                    assoc_ref_values

        logger.info('AuditRule {NAME}: found {NMATCH} associations out of {NTOTAL} unreferenced account {ACCT} records'
                    .format(NAME=self.name, NMATCH=nfound, NTOTAL=df.shape[0], ACCT=acct.name))

    def save_records(self):
        """
        Save any changes to the records made during the reconciliation process.
        """
        statements = {}
        for acct_panel in self.panels:
            acct = self.fetch_account(acct_panel, by_key=True)

            record_type = acct.record_type
            record_entry = settings.records.fetch_rule(record_type)

            # Prepare to save the record
            logger.debug('BankRule {NAME}: preparing account {ACCT} statements'.format(NAME=self.name, ACCT=acct.name))
            try:
                statements = record_entry.save_database_records(acct.table.data(), id_field=acct.table.id_column,
                                                                exists=True, statements=statements)
            except Exception as e:
                msg = 'failed to prepare the export statement for the account {ACCT} records - {ERR}' \
                    .format(ACCT=acct.name, ERR=e)
                logger.exception('BankRule {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                raise

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
        """
        status = []
        with pd.ExcelWriter(filename) as writer:
            for acct_panel in self.panels:
                acct = self.fetch_account(acct_panel, by_key=True)

                sheet_name = acct.title
                table = acct.table
                df = table.data()  # show all data

                export_df = table.format_display_table(df)
                annotations = table.annotate_display(df)
                annotation_map = {i: table.annotation_rules[j]['BackgroundColor'] for i, j in annotations.items()}
                try:
                    export_df.style.apply(lambda x: ['background-color: {}'
                                          .format(annotation_map.get(x.name, 'white')) for _ in x], axis=1) \
                        .to_excel(writer, sheet_name=sheet_name, engine='openpyxl', header=True, index=False)
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

        record_type (str): entry database record type.

        import_parameters (list): list of entry data parameters used in the import window.

        table (RecordTable): table for storing account data.

        record_layout (dict): layout for the record table entries.

        refmap (dict): configured reference parameters mapped to database column names.

        transactions (dict): source and sink dynamics of the account.
    """

    def __init__(self, name, entry, parent=None):
        """
        Arguments:

            name (str): configuration entry name for the bank record tab.

            entry (dict): dictionary of optional and required entry arguments.

            parent (str): name of the object's parent element.
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
            self.import_rules = entry['ImportRules']
        except KeyError:
            self.import_rules = record_entry.import_rules

        try:
            self.record_layout = entry['RecordLayout']
        except KeyError:
            self.record_layout = record_entry.record_layout

        try:
            reference = entry['Reference']
        except KeyError:
            msg = 'AccountEntry {NAME}: missing required configuration parameter "Reference".'.format(NAME=name)
            logger.error(msg)

            raise AttributeError(msg)
        else:
            try:
                references = self.record_layout['References2']['Elements']
            except KeyError:
                msg = 'the record layout is missing configured layout parameter "References2"'
                logger.error('AccountEntry {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                raise AttributeError(msg)

            try:
                ref_entry = references[reference]
            except KeyError:
                msg = 'the record layout is missing configured reference component {COMP}'.format(COMP=reference)
                logger.error('AccountEntry {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                raise AttributeError(msg)

            try:
                self.refmap = ref_entry['ColumnMap']
            except KeyError:
                msg = 'no column mapping specified in the {RTYPE} configuration for reference {REF}' \
                    .format(NAME=name, RTYPE=self.record_type, REF=reference)
                logger.error('AccountEntry {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                raise AttributeError(msg)

        try:
            self.table = mod_elem.TableElement(name, entry['DisplayTable'])
        except KeyError:
            self.table = mod_elem.TableElement(name, record_entry.import_table)
        self.elements += self.table.elements

        try:
            self.parameters = entry['ImportParameters']
        except KeyError:
            msg = 'no import parameters specified'
            logger.warning('AccountEntry {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            self.parameters = {}

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

                if 'AssociationRules' not in cnfg_entry:
                    msg = 'AccountEntry {NAME}: Transaction account {ACCT} is missing required parameter ' \
                          '"AssociationRules"'.format(NAME=name, ACCT=transaction_acct)
                    logger.error(msg)

                    continue
                else:
                    trans_entry['AssociationRules'] = cnfg_entry['AssociationRules']

                if 'ImportParameters' not in cnfg_entry:
                    trans_entry['ImportParameters'] = {}
                else:
                    trans_entry['ImportParameters'] = cnfg_entry['ImportParameters']

                if 'Title' not in cnfg_entry:
                    trans_entry['Title'] = transaction_acct
                else:
                    trans_entry['Title'] = cnfg_entry['Title']

                self.transactions[transaction_acct] = trans_entry

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

        # Reset the data tables
        self.table.reset(window)

        # Un-collapse the tab filter frame
        filter_key = self.table.key_lookup('FilterFrame')
        if window[filter_key].metadata['visible'] is False:
            self.table.collapse_expand(window, frame='filter')

    def run_event(self, window, event, values):
        """
        Run a bank record tab event.
        """
        table_keys = self.table.elements
        tbl_bttn_keys = ['-HK_TBL_ADD-', '-HK_TBL_DEL-', '-HK_TBL_IMPORT-', '-HK_TBL_FILTER-', '-HK_TBL_OPTS-']

        success = True
        # Run a record table event.
        if event in table_keys or event in tbl_bttn_keys:
            table = self.table
            import_key = self.table.key_lookup('Import')
            tbl_key = self.table.key_lookup('Element')
            frame_key = self.table.key_lookup('OptionsFrame')

            # A table row was selected
            if event == tbl_key:
                # Close options panel, if open
                if window[frame_key].metadata['visible'] is True:
                    window[frame_key].metadata['visible'] = False
                    window[frame_key].update(visible=False)
                    table.resize(window, size=table.dimensions)

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
                        table.df = table.export_row(index, layout=self.record_layout, level=0)

                        table.update_display(window, window_values=values)

            # Table import button or the import hotkey was pressed
            elif event == import_key or (event == '-HK_TBL_IMPORT-' and (not window[import_key].metadata['disabled'] and
                                                                         window[import_key].metadata['visible'])):
                table.import_rows(import_rules=self.import_rules, program_database=True)
                table.update_display(window, window_values=values)
            else:
                table.run_event(window, event, values)

        return success

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
        tbl_layout = [[self.table.layout(width=tbl_width, height=tbl_height, padding=(0, 0), tooltip=self.title)]]

        panel_key = self.key_lookup('Panel')
        layout = sg.Col(tbl_layout, key=panel_key, pad=(pad_frame, pad_frame), justification='c',
                        vertical_alignment='t', background_color=bg_col, expand_x=True, visible=False)

        return layout

    def resize(self, window, size):
        """
        Resize the bank record tab.
        """
        width, height = size

        # Reset table size
        tbl_width = width - 30  # includes padding on both sides and scroll bar
        tbl_height = int(height * 0.55)
        self.table.resize(window, size=(tbl_width, tbl_height), row_rate=40)

    def update_display(self, window):
        """
        Update the audit record summary tab's record display.
        """
        self.table.update_display(window)

    def load_data(self, parameters):
        """
        Load data from the database.
        """
        # Prepare the database query statement
        import_rules = self.import_rules

        param_filters = [i.query_statement(mod_db.get_import_column(import_rules, i.name)) for i in parameters]
        filters = param_filters + mod_db.format_import_filters(import_rules)
        table_statement = mod_db.format_tables(import_rules)
        columns = mod_db.format_import_columns(import_rules)

        # Import primary bank data from database
        try:
            df = user.read_db(*user.prepare_query_statement(table_statement, columns=columns, filter_rules=filters),
                              prog_db=True)
        except Exception as e:
            msg = 'failed to import data from the database'
            logger.exception('AccountEntry {NAME}: {MSG} - {ERR}'.format(NAME=self.name, MSG=msg, ERR=e))
            mod_win2.popup_error('{MSG} -  see log for details'.format(MSG=msg))
            data_loaded = False
        else:
            logger.debug('AccountEntry {NAME}: loaded data for bank reconciliation "{RULE}"'
                         .format(NAME=self.name, RULE=self.parent))
            data_loaded = True

            # Update record table with imported data
            self.table.df = self.table.append(df)

        return data_loaded
