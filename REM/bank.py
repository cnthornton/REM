"""
REM bank reconciliation configuration classes and objects.
"""

import pandas as pd
import PySimpleGUI as sg
from random import randint
import sys

import REM.constants as mod_const
import REM.database as mod_db
import REM.elements as mod_elem
import REM.layouts as mod_layout
import REM.parameters as mod_param
import REM.secondary as mod_win2


class BankRules:
    """
    Class to store and manage program bank_reconciliation configuration settings.

    Arguments:

        cnfg (Config): program configuration class.

    Attributes:

        rules (list): List of BankRule objects.
    """

    def __init__(self, cnfg):

        # Audit parameters
        bank_param = cnfg.bank_rules

        self.rules = []
        if bank_param is not None:
            try:
                bank_name = bank_param['name']
            except KeyError:
                mod_win2.popup_error('Error: bank_rules: the parameter "name" is a required field')
                sys.exit(1)
            else:
                self.name = bank_name

            try:
                self.title = bank_param['title']
            except KeyError:
                self.title = bank_name

            try:
                bank_rules = bank_param['rules']
            except KeyError:
                mod_win2.popup_error('Error: bank_rules: the parameter "rules" is a required field')
                sys.exit(1)

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
            print('Rule {NAME} not in list of configured bank reconciliation rules. Available rules are {ALL}'
                  .format(NAME=name, ALL=', '.join(self.print_rules())))
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

        menu_title (str): bank reconciliation rule title.

        element_key (str): panel element key.

        elements (list): list of rule GUI element keys.

        permissions (str): permissions required to view the accounting method. Default: user.
    """

    def __init__(self, name, entry):
        """
        Arguments:

            name (str): bank reconciliation rule name.

            entry (dict): dictionary of optional and required bank rule arguments.
        """

        self.name = name
        self.id = randint(0, 1000000000)
        self.element_key = '{NAME}_{ID}'.format(NAME=name, ID=self.id)
        self.elements = ['{NAME}_{ID}_{ELEM}'.format(NAME=self.name, ID=self.id, ELEM=i) for i in
                         ['Main', 'Summary', 'Cancel', 'Save', 'Next', 'Back', 'Start', 'Reconcile', 'FrameWidth',
                          'FrameHeight', 'PanelWidth', 'PanelHeight', 'MoneyOutTabHeight', 'MoneyInTabHeight',
                          'MoneyOutTab', 'MoneyInTab', 'TG', 'SinkTG', 'SourceTG']]

        try:
            self.menu_title = entry['MenuTitle']
        except KeyError:
            self.menu_title = name

        try:
            self.permissions = entry['AccessPermissions']
        except KeyError:  # default permission for a cash rule is 'user'
            self.permissions = 'user'

        self.parameters = []
        try:
            params = entry['RuleParameters']
        except KeyError:
            msg = 'Configuration Error: BankRule {RULE}: missing required "Main" parameter "RuleParameters"' \
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
                msg = 'Configuration Error: BankRule {NAME}: unknown type {TYPE} provided to RuleParameter {PARAM}' \
                    .format(NAME=name, TYPE=param_layout, PARAM=param)
                mod_win2.popup_error(msg)
                sys.exit(1)

            param = param_class(param, param_entry)
            self.parameters.append(param)
            self.elements += param.elements

        try:
            main_entry = entry['Main']
        except KeyError:
            msg = 'Configuration Error: BankRule {NAME}: missing required parameter "Main"'.format(NAME=name)
            mod_win2.popup_error(msg)
            sys.exit(1)

        try:
            self.table = mod_elem.TableElement(name, main_entry['DisplayTable'])
        except KeyError:
            msg = 'Configuration Error: BankRule {NAME}: missing required "Main" parameter "Table"'.format(NAME=name)
            mod_win2.popup_error(msg)
            sys.exit(1)
        except AttributeError as e:
            msg = 'Configuration Error: BankRule {NAME}: unable to initialize DisplayTable - {ERR}' \
                .format(NAME=name, ERR=e)
            mod_win2.popup_error(msg)
            sys.exit(1)
        else:
            self.elements += self.table.elements

        try:
            self.import_rules = main_entry['ImportRules']
        except KeyError:
            msg = 'Configuration Error: BankRule {NAME}: missing required "Main" parameter "ImportRules"' \
                .format(NAME=name)
            mod_win2.popup_error(msg)
            sys.exit(1)

        try:
            assoc_entries = entry['Associations']
        except KeyError:
            msg = 'Configuration Error: BankRule {NAME}: missing required parameter "Associations"'.format(NAME=name)
            mod_win2.popup_error(msg)
            sys.exit(1)

        self.associations = []
        for assoc_name in assoc_entries:
            assoc_entry = assoc_entries[assoc_name]
            assoc = AssociationRule(assoc_name, assoc_entry)

            self.associations.append(assoc)
            self.elements += assoc.elements

        self.panel_keys = {0: self.key_lookup('Main'), 1: self.key_lookup('Summary')}
        self.current_panel = 0
        self.first_panel = 0
        self.last_panel = 1

        self.in_progress = False

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

    def fetch_association(self, fetch_key, by_key: bool = False):
        """
        Fetch an association rule by name or event key.
        """
        if by_key is True:
            element_type = fetch_key.split('_')[-1]
            associations = [i.key_lookup(element_type) for i in self.associations]
        else:
            associations = [i.name for i in self.associations]

        if fetch_key in associations:
            index = associations.index(fetch_key)
            association_rule = self.associations[index]
        else:
            raise KeyError('association {ELEM} not found in list of {NAME} associations'
                           .format(ELEM=fetch_key, NAME=self.name))

        return association_rule

    def summary_layout(self, win_size: tuple = None):
        """
        Generate a GUI layout for the bank reconciliation summary.
        """
        if win_size:
            width, height = win_size
        else:
            width, height = (mod_const.WIN_WIDTH, mod_const.WIN_HEIGHT)

        # Element parameters
        bg_col = mod_const.ACTION_COL
        inactive_col = mod_const.INACTIVE_COL
        select_col = mod_const.SELECT_TEXT_COL
        text_col = mod_const.TEXT_COL
        disabled_col = mod_const.DISABLED_TEXT_COL

        font_h = mod_const.HEADER_FONT

        pad_frame = mod_const.FRAME_PAD

        # Association tables
        associations = self.associations

        # Element sizes
        layout_height = height * 0.8
        frame_height = layout_height * 0.70
        panel_height = frame_height - 80
        tbl_height = panel_height * 0.7
        tab_height = panel_height - 30

        layout_pad = 120
        win_diff = width - mod_const.WIN_WIDTH
        layout_pad = layout_pad + (win_diff / 5)

        frame_width = width - layout_pad if layout_pad > 0 else width
        panel_width = frame_width - 30
        tbl_width = panel_width - 30

        # Layout elements

        # Tab layouts
        sink_tabs = []
        source_tabs = []
        for assoc in associations:
            assoc_layout = assoc.layout(width=tbl_width, height=tbl_height)

            assoc_type = assoc.type
            if assoc_type.lower() == 'deposit':
                source_tabs.append(assoc_layout)
            else:
                sink_tabs.append(assoc_layout)

        # Money In layout
        source_tg_key = self.key_lookup('SourceTG')
        source_height_key = self.key_lookup('MoneyInTabHeight')
        source_layout = [[sg.Canvas(key=source_height_key, size=(0, tab_height), background_color=bg_col),
                          sg.Col([[sg.Text('{} Income Sources'.format(self.menu_title), background_color=bg_col,
                                           font=font_h)],
                                  [sg.TabGroup([source_tabs], key=source_tg_key, pad=(0, 0),
                                               tab_background_color=inactive_col,
                                               selected_title_color=select_col,
                                               title_color=text_col, selected_background_color=bg_col,
                                               background_color=bg_col)]],
                                 pad=(pad_frame, pad_frame), background_color=bg_col, element_justification='c',
                                 vertical_alignment='t', expand_x=True, expand_y=True)]]

        source_key = self.key_lookup('MoneyInTab')
        source_disabled = True if len(source_tabs) < 1 else False
        if source_disabled is True:
            title_col = disabled_col
        else:
            title_col = text_col
        source_tab = [sg.Tab('Money In', source_layout, key=source_key, title_color=title_col, background_color=bg_col,
                             disabled=source_disabled)]

        # Money Out layout
        sink_tg_key = self.key_lookup('SinkTG')
        sink_height_key = self.key_lookup('MoneyOutTabHeight')
        sink_layout = [[sg.Canvas(key=sink_height_key, size=(0, tab_height), background_color=bg_col),
                        sg.Col([[sg.Text('{} Expense Destinations'.format(self.menu_title), background_color=bg_col,
                                         font=font_h)],
                                [sg.TabGroup([sink_tabs], key=sink_tg_key, pad=(0, 0), tab_background_color=inactive_col,
                                             selected_title_color=select_col, title_color=text_col,
                                             selected_background_color=bg_col, background_color=bg_col)]],
                               pad=(pad_frame, (0, pad_frame)), background_color=bg_col, element_justification='c',
                               vertical_alignment='t', expand_x=True, expand_y=True)]]

        sink_key = self.key_lookup('MoneyOutTab')
        sink_disabled = True if len(sink_tabs) < 1 else False
        if sink_disabled is True:
            title_col = disabled_col
        else:
            title_col = text_col
        sink_tab = [sg.Tab('Money Out', sink_layout, key=sink_key, title_color=title_col, background_color=bg_col,
                           disabled=sink_disabled)]

        # TabGroup layout
        tg_key = self.key_lookup('TG')
        panel_layout = [[sg.TabGroup([source_tab, sink_tab], key=tg_key, pad=(0, 0),
                                     tab_background_color=inactive_col, selected_title_color=select_col,
                                     title_color=text_col,
                                     selected_background_color=bg_col, background_color=bg_col)]]

        summary_key = self.key_lookup('Summary')
        layout = sg.Col(panel_layout, key=summary_key, pad=(0, 0), background_color=bg_col, vertical_alignment='t',
                        visible=False, expand_y=True, expand_x=True)

        return layout

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
        tbl_height = panel_height * 0.6

        layout_pad = 120
        win_diff = width - mod_const.WIN_WIDTH
        layout_pad = layout_pad + (win_diff / 5)

        frame_width = width - layout_pad if layout_pad > 0 else width
        panel_width = frame_width - 30
        tbl_width = panel_width - 30

        # Layout elements
        # Title
        panel_title = 'Bank Reconciliation : {}'.format(self.menu_title)
        title_layout = [[sg.Text(panel_title, pad=(pad_frame, pad_frame), font=font_h, background_color=header_col)]]

        # Rule parameter elements
        param_elements = []
        for param in params:
            element_layout = param.layout(padding=((0, pad_h), 0))
            param_elements += element_layout

        start_key = self.key_lookup('Start')
        start_layout = [[mod_layout.B2('Start', key=start_key, pad=(0, 0), disabled=False,
                                       button_color=(bttn_text_col, bttn_bg_col),
                                       disabled_button_color=(disabled_text_col, disabled_bg_col),
                                       tooltip='Start bank reconciliation', use_ttk_buttons=True)]]

        param_layout = [sg.Col([param_elements], pad=(0, 0), background_color=bg_col, justification='l',
                               vertical_alignment='t', expand_x=True),
                        sg.Col(start_layout, pad=(0, 0), background_color=bg_col, justification='r',
                               element_justification='r', vertical_alignment='t')]

        # Table layout
        tbl_layout = [self.table.layout(width=tbl_width, height=tbl_height, padding=(0, 0), disabled=True)]

        # Main Panel layout
        main_key = self.key_lookup('Main')
        reconcile_key = self.key_lookup('Reconcile')
        main_layout = sg.Col([param_layout,
                              [sg.HorizontalSeparator(pad=(0, pad_v), color=mod_const.HEADER_COL)],
                              tbl_layout,
                              [sg.Col([
                                  [mod_layout.B1('Find Associations', key=reconcile_key, disabled=True,
                                                 button_color=(bttn_text_col, bttn_bg_col),
                                                 disabled_button_color=(disabled_text_col, disabled_bg_col),
                                                 tooltip='Reconcile the selected bank records', use_ttk_buttons=True)]],
                                  pad=(pad_frame, pad_frame), background_color=bg_col, element_justification='c',
                                  expand_x=True)]],
                             key=main_key, pad=(0, 0), background_color=bg_col, vertical_alignment='t',
                             visible=True, expand_y=True, expand_x=True)

        # Summary layout
        summary_layout = self.summary_layout(win_size=win_size)

        # Panels
        panels = [main_layout, summary_layout]

        pw_key = self.key_lookup('PanelWidth')
        ph_key = self.key_lookup('PanelHeight')
        panel_layout = [[sg.Canvas(key=pw_key, size=(panel_width, 0), background_color=bg_col)],
                        [sg.Canvas(key=ph_key, size=(0, panel_height), background_color=bg_col),
                         sg.Pane(panels, orientation='horizontal', show_handle=False, border_width=0, relief='flat')]]

        # Control elements
        cancel_key = self.key_lookup('Cancel')
        next_key = self.key_lookup('Next')
        back_key = self.key_lookup('Back')
        save_key = self.key_lookup('Save')
        bttn_layout = [sg.Col([[mod_layout.B2('Cancel', key=cancel_key, pad=((0, pad_el), 0), disabled=False,
                                              tooltip='Return to home screen')]],
                              pad=(0, (pad_v, 0)), justification='l', expand_x=True),
                       sg.Col([[mod_layout.B2('Back', key=back_key, pad=((0, pad_el), 0), disabled=True,
                                              tooltip='Return to bank reconciliation panel'),
                                mod_layout.B2('Next', key=next_key, pad=(pad_el, 0), disabled=True,
                                              tooltip='Review results'),
                                mod_layout.B2('Save', key=save_key, pad=((pad_el, 0), 0), disabled=True,
                                              tooltip='Save to database and generate summary report')]],
                              pad=(0, (pad_v, 0)), justification='r', element_justification='r')]

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
        Resize Bank Reconciliation Rule GUI elements.
        """
        if win_size:
            width, height = win_size
        else:
            width, height = window.size  # current window size (width, height)

        # For every five-pixel increase in window size, increase the frame size by one
        layout_pad = 100  # default padding between the window and border of the frame
        win_diff = width - mod_const.WIN_WIDTH  # difference between current window size and default
        layout_pad = layout_pad + int(win_diff / 5)  # padding +/- difference

        frame_width = width - layout_pad if layout_pad > 0 else width
        panel_width = frame_width - 30

        width_key = self.key_lookup('FrameWidth')
        window[width_key].set_size((frame_width, None))

        pw_key = self.key_lookup('PanelWidth')
        window[pw_key].set_size((panel_width, None))

        layout_height = height * 0.85  # height of the panel, including buttons
        frame_height = layout_height - 120  # minus the approximate height of the button row and title bar, with padding
        panel_height = frame_height - 20  # minus top and bottom padding

        height_key = self.key_lookup('FrameHeight')
        window[height_key].set_size((None, frame_height))

        ph_key = self.key_lookup('PanelHeight')
        window[ph_key].set_size((None, panel_height))

        # Resize table
        tbl_width = panel_width - 30  # includes padding on both sides and scroll bar
        tbl_height = int(panel_height * 0.5)
        self.table.resize(window, size=(tbl_width, tbl_height), row_rate=100)

        # Resize summary tabs and elements
        tab_height = panel_height - 30  # minus size of the tabs
        source_height_key = self.key_lookup('MoneyInTabHeight')
        window[source_height_key].set_size((None, tab_height))

        sink_height_key = self.key_lookup('MoneyOutTabHeight')
        window[sink_height_key].set_size((None, tab_height))

        tab_width = panel_width - 70
        for assoc in self.associations:
            assoc.table.resize(window, size=(tab_width, tab_height), row_rate=80)

    def run_event(self, window, event, values, user):
        """
        Run a bank reconciliation event.
        """
        current_rule = self.name

        # Rule action element events: Cancel, Next, Back, Start, Save, Reconcile
        cancel_key = self.key_lookup('Cancel')
        reconcile_key = self.key_lookup('Reconcile')
        next_key = self.key_lookup('Next')
        back_key = self.key_lookup('Back')
        start_key = self.key_lookup('Start')
        tg_key = self.key_lookup('TG')

        # Component element events
        param_elements = [i for j in self.parameters for i in j.elements]
        association_elements = [i for j in self.associations for i in j.elements]

        # Cancel button pressed
        if event == cancel_key:
            # Check if reconciliation is currently in progress
            if self.in_progress is True:
                msg = 'Bank Reconciliation is currently in progress. Are you sure you would like to quit without ' \
                      'saving?'
                selection = mod_win2.popup_confirm(msg)

                if selection == 'OK':
                    self.in_progress = False

                    # Reset rule and update the panel
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
                initialized = self.load_data(user)

                # Show that a bank reconciliation is in progress
                if initialized is True:
                    self.in_progress = True
                    print('Info: BankRule {NAME}: bank reconciliation in progress with parameters {PARAMS}'
                          .format(NAME=self.name, PARAMS=', '.join(['{}={}'.format(i.name, i.value) for i in params])))

                    # Enable/Disable control buttons and parameter elements
                    window[start_key].update(disabled=True)
                    window[reconcile_key].update(disabled=False)

                    # Update the tab table display
                    self.table.update_display(window)

                    # Update the associate table events
                    for assoc in self.associations:

                        # Update the association display table
                        assoc.table.update_display(window)

                    # Enable table element events
                    self.table.enable(window)

                    self.toggle_parameters(window, 'disable')

        # Switch between tabs
        elif event == tg_key:
            tab_key = window[tg_key].Get()
            tab = self.fetch_association(tab_key, by_key=True)
            print('Info: BankRule {NAME}: moving to bank association {ASSOC}'.format(NAME=self.name, ASSOC=tab.name))
            filter_key = tab.table.key_lookup('FilterFrame')
            if window[filter_key].metadata['visible'] is True:
                tab.table.collapse_expand(window, frame='filter')

        # Run the bank reconciliation algorithm
        elif event == reconcile_key:
            # Enable movement to the summary panels
            window[next_key].update(disabled=False)

        # Run component table events
        elif event in self.table.elements:
            results = self.table.run_event(window, event, values, user)

        # Run association table events
        elif event in association_elements:
            # Fetch the association element
            try:
                association_table = self.fetch_association(event, by_key=True)
            except KeyError:
                print('Error: BankRule {NAME}: unable to find association table associated with event key {KEY}'
                      .format(NAME=self.name, KEY=event))
            else:
                result = association_table.run_event(window, event, values, user)

        # Run component parameter events
        elif event in param_elements:
            try:
                param = self.fetch_parameter(event, by_key=True)
            except KeyError:
                print('Error: BankRule {NAME}: unable to find parameter associated with event key {KEY}'
                      .format(NAME=self.name, KEY=event))
            else:
                result = param.run_event(window, event, values)

        return current_rule

    def reset_rule(self, window, current: bool = False):
        """
        Reset rule to default.
        """
        panel_key = self.element_key
        current_key = self.panel_keys[self.current_panel]

        # Reset the current sub-panel
        self.current_panel = 0

        # Disable the current panel and revert to first sub-panel
        window[current_key].update(visible=False)
        window[self.panel_keys[self.first_panel]].update(visible=True)
        window[panel_key].update(visible=False)
        window['-HOME-'].update(visible=True)

        # Reset action elements to default
        end_key = self.key_lookup('Save')
        next_key = self.key_lookup('Next')
        back_key = self.key_lookup('Back')
        start_key = self.key_lookup('Start')
        reconcile_key = self.key_lookup('Reconcile')
        window[next_key].update(disabled=True)
        window[back_key].update(disabled=True)
        window[end_key].update(disabled=True)
        window[start_key].update(disabled=False)
        window[reconcile_key].update(disabled=True)

        # Switch to first tab in panel
        tg_key = self.key_lookup('TG')
        window[tg_key].Widget.select(0)

        # Reset the parameter elements.
        self.reset_parameters(window)
        self.toggle_parameters(window, 'enable')

        # Reset the table elements
        self.table.df = pd.DataFrame(columns=list(self.table.columns))
        self.table._df = pd.DataFrame(columns=list(self.table.columns))
        self.table.update_display(window)

        # Disable table element events
        self.table.disable(window)

        for association in self.associations:
            association.reset(window)

        if current:
            window['-HOME-'].update(visible=False)
            window[panel_key].update(visible=True)
            window[self.panel_keys[self.first_panel]].update(visible=True)

            return self.name
        else:
            return None

    def reset_parameters(self, window):
        """
        Reset rule item parameter values.
        """
        for param in self.parameters:
            param.reset_parameter(window)

    def toggle_parameters(self, window, value='enable'):
        """
        Enable / Disable audit rule parameter elements.
        """
        for parameter in self.parameters:
            parameter.toggle_parameter(window, value=value)

    def load_data(self, user):
        """
        Load data from the database.
        """
        data_loaded = []

        # Prepare the database query statement
        import_rules = self.import_rules

        main_table = mod_db.get_primary_table(import_rules)
        filters = mod_db.format_import_filters(import_rules)
        table_statement = mod_db.format_tables(import_rules)
        columns = mod_db.format_import_columns(import_rules)

        # Add parameter values to the filter statement
        rule_params = self.parameters  # to filter data tables
        param_filters = [i.query_statement(table=main_table) for i in rule_params]
        filters += param_filters

        # Import primary bank data from database
        try:
            df = user.query(table_statement, columns=columns, filter_rules=filters, prog_db=True)
        except Exception as e:
            mod_win2.popup_error('Error: BankRule {NAME}: failed to import data from the database - {ERR}'
                                 .format(NAME=self.name, ERR=e))
            data_loaded.append(False)
        else:
            if df.empty:
                print('Warning: BankRule {NAME}: no data to display'.format(NAME=self.name))
            else:
                self.table.df = self.table.append(df)
                self.table._df = self.table.df
            data_loaded.append(True)

        # Import association data from database
        for association in self.associations:
            # Set parameter attribute for the association
            association.parameters = self.parameters

            # Load data
            data_loaded.append(association.load_data(user))

        return all(data_loaded)


class AssociationRule:
    """
    Bank Reconciliation income source / expense destination.

        name (str): bank reconciliation rule association name.

        id (int): association element number.

        title (str): association title.

        elements (list): list of rule GUI element keys.
    """

    def __init__(self, name, entry):
        """
        name (str): rule name.

        entry: (dict): association configuration entry.
        """
        self.name = name
        self.id = randint(0, 1000000000)
        self.elements = ['{NAME}_{ID}_{ELEM}'.format(NAME=self.name, ID=self.id, ELEM=i) for i in ['Tab']]

        try:
            self.title = entry['Title']
        except KeyError:
            self.title = name

        try:
            transaction_type = entry['Type']
        except KeyError:
            msg = 'Configuration Error: BankRuleAssociation {NAME}: missing required parameter "Type"' \
                .format(NAME=name)
            mod_win2.popup_error(msg)
            sys.exit(1)
        else:
            if transaction_type not in ('Deposit', 'Withdrawal'):
                msg = 'Configuration Error: BankRuleAssociation {NAME}: unsupported value {VAL} provided to parameter ' \
                      '"Type". Type must be one of "Deposit" or "Withdrawal"'.format(NAME=name, VAL=transaction_type)
                mod_win2.popup_error(msg)
                sys.exit(1)
            else:
                self.type = transaction_type

        try:
            self.table = mod_elem.TableElement(name, entry['DisplayTable'])
        except KeyError:
            msg = 'Configuration Error: BankRuleAssociation {NAME}: missing required parameter "DisplayTable"' \
                .format(NAME=name)
            mod_win2.popup_error(msg)
            sys.exit(1)
        except AttributeError as e:
            msg = 'Configuration Error: BankRuleAssociation {NAME}: unable to initialize DisplayTable - {ERR}' \
                .format(NAME=name, ERR=e)
            mod_win2.popup_error(msg)
            sys.exit(1)
        else:
            self.elements += self.table.elements

        try:
            self.import_rules = entry['ImportRules']
        except KeyError:
            msg = 'Configuration Error: BankRuleAssociation {NAME}: missing required parameter "ImportRules"' \
                .format(NAME=name)
            mod_win2.popup_error(msg)
            sys.exit(1)

        try:
            self.association_rules = entry['AssociationRules']
        except KeyError:
            msg = 'Configuration Error: BankRuleAssociation {NAME}: missing required parameter "AssociationRules"' \
                .format(NAME=name)
            mod_win2.popup_error(msg)
            sys.exit(1)

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
            print('Warning: component {COMP} not found in list of bank rule {PARAM} components'
                  .format(COMP=component, PARAM=self.name))
            key = None

        return key

    def run_event(self, window, event, values, user):
        """
        Run an association table event.
        """
        # Component element events
        tbl_elements = self.table.elements

        # Table event
        if event in tbl_elements:
            self.table.run_event(window, event, values, user)

        return True

    def layout(self, width, height):
        """
        Generate a GUI layout for the bank reconciliation association tab.
        """
        title = self.title

        # Element parameters
        bg_col = mod_const.ACTION_COL

        # Tab layout
        table_layout = [[self.table.layout(width=width, height=height, padding=(0, 0))]]
        layout = sg.Tab(title, table_layout, key=self.key_lookup('Tab'), background_color=bg_col)

        return layout

    def reset(self, window):
        """
        Reset the elements and attributes of the audit rule transaction tab.
        """

        # Reset the data table
        self.table.df = pd.DataFrame(columns=list(self.table.columns))
        self.table.update_display(window)

        # Disable table element events
        self.table.disable(window)

        # Reset the parameter values
        self.parameters = None

        # Disable the reconcile button
#        window[self.key_lookup('Reconcile')].update(disabled=True)

        # Reset visible tabs
#        print('Info: BankRuleAssociation {NAME}: re-setting visibility of rule tab to {STATUS}'
#              .format(NAME=self.name, STATUS=visible))

#        window[self.element_key].update(visible=visible)

    def load_data(self, user):
        """
        Load association data from the database.
        """
        # Prepare the database query statement
        import_rules = self.import_rules

        main_table = mod_db.get_primary_table(import_rules)
        filters = mod_db.format_import_filters(import_rules)
        table_statement = mod_db.format_tables(import_rules)
        columns = mod_db.format_import_columns(import_rules)

        # Add parameter values to the filter statement
        rule_params = self.parameters  # to filter data tables
        filters += [i.query_statement(table=main_table) for i in rule_params]

        # Import primary bank data from database
        try:
            df = user.query(table_statement, columns=columns, filter_rules=filters, prog_db=True)
        except Exception as e:
            mod_win2.popup_error('Error: BankRuleAssociation {NAME}: failed to import data from the database - {ERR}'
                                 .format(NAME=self.name, ERR=e))
            data_loaded = False
        else:
            self.table.df = self.table.append(df)
            self.table._df = self.table.df
            data_loaded = True

        return data_loaded

