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


class BankRuleController:
    """
    Class to store and manage configured bank reconciliation definitions.

    Arguments:

        bank_param (dict): configuration for the bank reconciliation definitions.

    Attributes:

        rules (list): list of bank reconciliation definitions as BankRule objects.
    """

    def __init__(self, bank_param):

        self.rules = []
        if bank_param is not None:
            try:
                bank_name = bank_param['name']
            except KeyError:
                msg = 'missing required field "name"'
                logger.error('BankRuleController: {MSG}'.format(MSG=msg))
                mod_win2.popup_error('Configuration Error: bank_rules: {MSG}'.format(MSG=msg))

                raise AttributeError(msg)
            else:
                self.name = bank_name

            try:
                self.title = bank_param['title']
            except KeyError:
                self.title = bank_name

            try:
                bank_rules = bank_param['rules']
            except KeyError:
                msg = 'missing required field "rules"'.format(NAME=self.name)
                logger.error('BankRuleController: {MSG}'.format(MSG=msg))
                mod_win2.popup_error('Configuration Error: bank_rules: {MSG}'.format(MSG=msg))

                raise AttributeError(msg)

            for rule_name in bank_rules:
                self.rules.append(BankRule(rule_name, bank_rules[rule_name]))

    def print_rules(self, title=True):
        """
        Return name of all bank rules defined in configuration file.
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
            msg = 'rule "{RULE}" is not in the list of configured bank reconciliation definitions ({ALL})'\
                .format(RULE=name, ALL=', '.join(self.print_rules()))
            logger.error('BankRuleController {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            rule = None
        else:
            rule = self.rules[index]

        return rule


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
                         ('MainPanel', 'Title', 'Reconcile', 'Parameters', 'Expand', 'Cancel', 'Save', 'FrameHeight',
                          'FrameWidth', 'PanelHeight', 'PanelWidth')]

        try:
            self.menu_title = entry['MenuTitle']
        except KeyError:
            self.menu_title = name

        try:
            self.menu_flags = entry['MenuFlags']
        except KeyError:
            self.menu_flags = {}

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
            print('adding panel key {} for account {}'.format(acct.key_lookup('Panel'), acct_id))
            self.panel_keys[acct_id] = acct.key_lookup('Panel')
            self.elements += acct.elements

        # Dynamic Attributes
        self.in_progress = False
        self.current_account = None
        self.current_panel = None
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
            logger.warning('BankRule {NAME}: component {COMP} not found in list of rule components'
                           .format(NAME=self.name, COMP=component))
            key = None

        return key

    def fetch_account(self, account_id):
        """
        Fetch a GUI parameter element by name or event key.
        """
        accounts = [i.name for i in self.accts]

        if account_id in accounts:
            index = accounts.index(account_id)
            account = self.accts[index]
        else:
            raise KeyError('account ID {ACCT} not found in list of {NAME} account entries'
                           .format(ACCT=account_id, NAME=self.name))

        return account

    def run_event(self, window, event, values):
        """
        Run a bank reconciliation event.
        """
        # Get elements of current account
        current_acct = self.current_account
        acct = self.fetch_account(current_acct)
        current_rule = self.name

        reconcile_key = self.key_lookup('Reconcile')
        expand_key = self.key_lookup('Expand')
        param_key = self.key_lookup('Parameters')
        cancel_key = self.key_lookup('Cancel')
        save_key = self.key_lookup('Save')
        acct_keys = acct.elements

        # Run event from a current primary account element. Pass on to account class.
        if event in acct_keys:
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
            default_title = acct.title + '.xlsx'
            outfile = sg.popup_get_file('', title='Save As', default_path=default_title, save_as=True,
                                        default_extension='pdf', no_window=True,
                                        file_types=(('PDF - Portable Document Format', '*.pdf'),))

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

        # Set parameters button was pressed. Will open parameter settings window for user to input parameter values,
        # then load the relevant account record data
        if event == param_key:
            # Get the parameter settings
            params = mod_win2.parameter_window(acct)

            # Load the account records
            if params:  # parameters were saved (selection not cancelled)
                for acct_name in params:
                    acct_params = params[acct_name]
                    if not acct_params:
                        continue

                    if acct_name == acct.name:
                        logger.debug('AuditRule {NAME}: loading database records for account {ACCT}'
                                     .format(NAME=self.name, ACCT=acct_name))
                        acct.load_data(acct_params)
                    else:
                        assoc_acct = self.fetch_account(acct_name)
                        assoc_acct.load_data(acct_params)

                # Update the display
                self.update_display(window)

                # Enable the reconciliation button
                window[reconcile_key].update(disabled=False)
                window[expand_key].update(disabled=False)

                # Mark that a reconciliation is currently in progress
                self.in_progress = True

        # Reconcile button was pressed. Will run the reconcile method to find associations with the current primary
        # account and any associated accounts with data.
        if event == reconcile_key:
            expand_search = values[expand_key]

            self.reconcile_statement(expand_search)

        return current_rule

    def reset_rule(self, window, current: bool = False):
        """
        Reset rule to default.
        """
        panel_key = self.element_key
        reconcile_key = self.key_lookup('Reconcile')
        expand_key = self.key_lookup('Expand')

        # Disable current panel
        window[self.current_panel].update(visible=False)
        window[panel_key].update(visible=False)
        window['-HOME-'].update(visible=True)

        # Disable the reconciliation button
        window[reconcile_key].update(disabled=True)
        window[expand_key].update(disabled=True)

        # Reset account entries
        for acct in self.accts:
            acct.reset(window)

        self.in_progress = False

        if current:
            window['-HOME-'].update(visible=False)
            window[self.current_panel].update(visible=True)
            window[panel_key].update(visible=True)

            return self.name
        else:
            # Reset the current account display
            self.current_panel = None

            panel_title_key = self.key_lookup('Title')
            window[panel_title_key].update(value='')

            self.current_account = None
            self.title = None

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
        panel_width = frame_width - 30

        # Keyboard shortcuts
        hotkeys = settings.hotkeys
        cancel_shortcut = hotkeys['-HK_ESCAPE-'][2]
        save_shortcut = hotkeys['-HK_ENTER-'][2]

        # Layout elements
        # Title
        panel_title = 'Bank Reconciliation: {}'.format(self.menu_title)
        title_layout = sg.Text(panel_title, pad=(pad_frame, pad_frame), font=font_h, background_color=header_col)

        # Header
        acct_text = '' if not self.title else self.title
        title_key = self.key_lookup('Title')
        param_key = self.key_lookup('Parameters')
        reconcile_key = self.key_lookup('Reconcile')
        expand_key = self.key_lookup('Expand')
        header = [sg.Col([[sg.Text(acct_text, key=title_key, pad=((0, pad_h), 0), size=(20, 1), font=font_bold,
                                   background_color=bg_col),
                           sg.Button('', key=param_key, image_data=mod_const.PARAM_ICON,
                                     button_color=(text_col, bg_col), tooltip='Set parameters')]],
                         expand_x=True, justification='l', background_color=bg_col),
                  sg.Col([[sg.Button('Reconcile', key=reconcile_key, pad=((0, pad_el), 0), disabled=True,
                                     button_color=(bttn_text_col, bttn_bg_col),
                                     disabled_button_color=(disabled_text_col, disabled_bg_col),
                                     tooltip='Run reconciliation'),
                           sg.Checkbox('Expand search', key=expand_key, background_color=bg_col, font=font,
                                       disabled=True)]],
                         pad=((0, pad_frame), 0), justification='r', background_color=bg_col)]

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
        main_layout = sg.Col([header,
                              [sg.HorizontalSeparator(pad=(0, pad_v), color=mod_const.HEADER_COL)],
                              [sg.Col(panel_layout, pad=(0, 0), background_color=bg_col, expand_x=True)]],
                             key=main_key, pad=(0, 0), background_color=bg_col, vertical_alignment='t',
                             visible=True, expand_y=True, expand_x=True)

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
            [sg.Col([[sg.Canvas(key=fh_key, size=(0, frame_height), background_color=bg_col)]], vertical_alignment='t'),
             sg.Col([[main_layout]], pad=((pad_frame, pad_v), pad_v), background_color=bg_col, vertical_alignment='t',
                    expand_x=True, expand_y=True, scrollable=True, vertical_scroll_only=True)]],
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

        # Resize account panels
        accts = self.accts
        for acct in accts:
            acct.resize(window, size=(panel_width, panel_height))

    def update_display(self, window):
        """
        Update the audit record summary tab's record display.
        """
        current_acct = self.current_account
        acct = self.fetch_account(current_acct)

        acct.update_display(window)

    def reconcile_statement(self, expand: bool = False):
        """
        Run the primary Bank Reconciliation rule algorithm for the record tab.
        """
        # Fetch primary account and prepare data
        acct = self.fetch_account(self.current_account)

        refmap = acct.refmap
        table = acct.table
        id_column = table.id_column
        df = table.data()
        header = df.columns.tolist()

        # Filter out records already associated with transaction account records
        df = df.drop(df[~df[refmap['ReferenceID']].isna()].index)

        # Define the fields that will be included in the merged association account table
        required_fields = ["Account", "RecordID", "RecordType"]

        # Initialize a merged association account table
        merged_df = pd.DataFrame(columns=required_fields)

        # Fetch associated account data
        transactions = acct.transactions
        assoc_ref_maps = {}
        for assoc_acct_name in transactions:
            assoc_acct = self.fetch_account(assoc_acct_name)

            assoc_ref_map = assoc_acct.refmap
            assoc_df = assoc_acct.table.data()

            if assoc_df.empty:  # no records loaded to match to, so skip
                continue

            # Filter association account records that are already associated with a record
            ref_id_col = assoc_ref_map['ReferenceID']
            assoc_df = assoc_df.drop(assoc_df[~assoc_df[ref_id_col].isna()])
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
                    msg = 'AssociationRule reference column {COL} is missing from transaction account {ACCT} data'\
                        .format(COL=assoc_colname, ACCT=assoc_acct_name)
                    logger.warning('BankRule: {NAME}: {MSG}'.format(NAME=acct.name, MSG=msg))
                    del assoc_rules[acct_colname]

                    continue

                colmap[assoc_colname] = acct_colname

            colmap[assoc_acct.table.id_column] = "RecordID"

            # Remove all but the relevant columns from the association account table
            assoc_df = assoc_df[list(colmap)]

            # Change column names of the association account table using the column map
            assoc_df.rename(columns=colmap, inplace=True)

            # Add association account name and record type to the association account table
            assoc_df['Account'] = assoc_acct_name
            assoc_df['RecordType'] = assoc_acct.record_type

            # Store column mappers for fast recall during matching
            assoc_ref_maps[assoc_acct_name] = {'RefMap': assoc_ref_map, 'RuleMap': assoc_rules}

            # Concatenate association tables
            merged_df = merged_df.append(assoc_df, ignore_index=True)

        # Iterate over record rows, attempting to find matches in associated transaction records
        for index, row in df.iterrows():
            record_id = row[id_column]

            # Attempt to find a match for the record to each of the associated transaction accounts
            matches = pd.DataFrame(columns=merged_df.columns)
            for assoc_acct_name in assoc_ref_maps:
                # Filter merged df by account name
                assoc_df = merged_df[merged_df['Account'] == assoc_acct_name]

                # Select columns that will be used to compare records
                cols = list(assoc_ref_maps[assoc_acct_name]['RuleMap'])

                # Find exact matches between account record and the associated account records using relevant columns
                acct_matches = assoc_df[assoc_df[cols].eq(row[cols]).all(axis=1)]
                matches.append(acct_matches)

            # Check matches and find correct association
            nmatch = matches.shape[0]
            if nmatch == 0 and expand is True:  # no matching entries in the merged dataset
                # Attempt to find matches using only the core columns
                matches = pd.DataFrame(columns=merged_df.columns)
                expanded_cols = []
                for assoc_acct_name in assoc_ref_maps:
                    # Filter merged df by account name
                    assoc_df = merged_df[merged_df['Account'] == assoc_acct_name]

                    # Select columns that will be used to compare records
                    assoc_rules = assoc_ref_maps[assoc_acct_name]['RuleMap']
                    cols = []
                    for col in assoc_rules:
                        rule_entry = assoc_rules[col]
                        if rule_entry['Expanded']:
                            expanded_cols.append(col)
                            continue

                        cols.append(col)

                    # Find exact matches between account record and the associated account records using relevant cols
                    acct_matches = assoc_df[assoc_df[cols].eq(row[cols]).all(axis=1)]
                    matches.append(acct_matches)

                nmatch = matches.shape[0]
                if nmatch == 0:  # no matches found given the parameters supplied
                    continue

                elif nmatch == 1:  # found one exact match using the column subset
                    results = matches.iloc[0]
                    assoc_acct_name = results['Account']
                    ref_id = results['RecordID']
                    ref_type = results['RecordType']

                    # Remove the found match from the dataframe of unmatched associated account records
                    merged_df.drop(matches.index.tolist()[0], inplace=True)

                    # Determine appropriate warning for the expanded search
                    assoc_rules = assoc_ref_maps[assoc_acct_name]['RuleMap']
                    warning = ["Potential false positive: the association is the result of an expanded search"]
                    for column in expanded_cols:
                        if row[column] != results[column]:
                            try:
                                warning.append('- {}'.format(assoc_rules[column]['Description']))
                            except KeyError:
                                logger.warning('BankRecordTab {NAME}: no description provided for expanded '
                                               'association rule {COL}'.format(NAME=self.name, COL=column))

                    warning = '\n'.join(warning)

                    # Add the reference information to the account record's table entry
                    ref_cols = [refmap['ReferenceID'], refmap['ReferenceType'], refmap['ReferenceDate'],
                                refmap['Warnings']]
                    ref_values = [ref_id, ref_type, datetime.datetime.now(), warning]
                    df.at[index, ref_cols] = ref_values

                    # Add the reference information to the referenced record's table entry
                    assoc_acct = self.fetch_account(assoc_acct_name)
                    assoc_refmap = assoc_acct.refmap
                    assoc_ref_cols = [assoc_refmap['ReferenceID'], assoc_refmap['ReferenceType'],
                                      assoc_refmap['ReferenceDate'], assoc_refmap['Warnings']]
                    assoc_ref_values = [record_id, acct.record_type, datetime.datetime.now(), warning]
                    assoc_acct.table.df.loc[assoc_acct.table.id_column == ref_id, assoc_ref_cols] = assoc_ref_values

                elif nmatch > 1:  # too many matches
                    logger.debug('BankRule {NAME}: found more than one match for account {ACCT} record "{RECORD}"'
                                 .format(NAME=self.name, ACCT=self.current_account, RECORD=record_id))
                    continue

            elif nmatch == 1:  # found one exact match
                results = matches.iloc[0]
                ref_id = results['RecordID']
                ref_type = results['RecordType']
                assoc_acct_name = results['Account']

                # Remove the found match from the dataframe of unmatched associated account records
                merged_df.drop(matches.index.tolist()[0], inplace=True)

                # Add the reference information to the account record's table entry
                ref_cols = [refmap['ReferenceID'], refmap['ReferenceType'], refmap['ReferenceDate']]
                ref_values = [ref_id, ref_type, datetime.datetime.now()]
                df.at[index, ref_cols] = ref_values

                # Add the reference information to the referenced record's table entry
                assoc_acct = self.fetch_account(assoc_acct_name)
                assoc_refmap = assoc_acct.refmap
                assoc_ref_cols = [assoc_refmap['ReferenceID'], assoc_refmap['ReferenceType'],
                                  assoc_refmap['ReferenceDate']]
                assoc_ref_values = [record_id, acct.record_type, datetime.datetime.now()]
                assoc_acct.table.df.loc[assoc_acct.table.id_column == ref_id, assoc_ref_cols] = assoc_ref_values

            elif nmatch > 1:  # too many matches
                logger.debug('BankRule {NAME}: found more than one match for account {ACCT} record "{RECORD}"'
                             .format(NAME=self.name, ACCT=self.current_account, RECORD=record_id))

                # Match the first of the exact matches
                results = matches.iloc[0]
                ref_id = results['RecordID']
                ref_type = results['RecordType']
                assoc_acct_name = results['Account']

                # Remove match from list of unmatched association records
                merged_df.drop(matches.index.tolist()[0], inplace=True)

                # Add the reference information to the account record's table entry
                ref_cols = [refmap['ReferenceID'], refmap['ReferenceType'], refmap['ReferenceDate']]
                ref_values = [ref_id, ref_type, datetime.datetime.now()]
                df.at[index, ref_cols] = ref_values

                # Add the reference information to the referenced record's table entry
                assoc_acct = self.fetch_account(assoc_acct_name)
                assoc_refmap = assoc_acct.refmap
                assoc_ref_cols = [assoc_refmap['ReferenceID'], assoc_refmap['ReferenceType'],
                                  assoc_refmap['ReferenceDate']]
                assoc_ref_values = [record_id, acct.record_type, datetime.datetime.now()]
                assoc_acct.table.df.loc[assoc_acct.table.id_column == ref_id, assoc_ref_cols] = assoc_ref_values

    def save_records(self):
        """
        Save any changes to the records made during the reconciliation process.
        """
        primary = self.fetch_account(self.current_account)
        transactions = primary.transactions

        accts = [primary]
        for transaction in transactions:
            trans_acct = self.fetch_account(transaction)
            accts.append(trans_acct)

        statements = {}
        for acct in accts:
            record_type = acct.record_type
            record_entry = settings.records.fetch_rule(record_type)

            # Prepare to save the record
            logger.debug('BankRule {NAME}: preparing account {ACCT} statements'.format(NAME=self.name, ACCT=acct.name))
            try:
                statements = record_entry.export_table(acct.table.data(), id_field=acct.table.id_column, exists=True,
                                                       statements=statements)
            except Exception as e:
                msg = 'failed to prepare the export statement for the account {ACCT} records - {ERR}'\
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
            for acct in self.accts:
                sheet_name = acct.title
                table = acct.table
                df = table.data()
                if df.empty:
                    continue

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
                msg = 'no column mapping specified in the {RTYPE} configuration for reference {REF}'\
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
                    if table.actions['open'] is True:
                        view_only = not table.actions['edit']
                        table.df = table.export_row(index, layout=self.record_layout, view_only=view_only)

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
        tbl_height = height * 0.60

        # Layout
        tbl_layout = [[self.table.layout(width=tbl_width, height=tbl_height, padding=(0, 0))]]

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
        tbl_height = int(height * 0.60)
        self.table.resize(window, size=(tbl_width, tbl_height), row_rate=40)

    def update_display(self, window):
        """
        Update the audit record summary tab's record display.
        """
        self.table.update_display(window)

        pd.set_option('display.max_columns', None)
        print(self.table.df)
        print(self.table.df.dtypes)

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
            msg = 'failed to import data from the database - {ERR}'.format(ERR=e)
            logger.error('AccountEntry {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
            mod_win2.popup_error(msg)
            data_loaded = False
        else:
            logger.debug('AccountEntry {NAME}: loaded data for bank reconciliation "{RULE}"'
                         .format(NAME=self.name, RULE=self.parent))
            data_loaded = True

            # Update record table with imported data
            self.table.df = self.table.append(df)

        return data_loaded

