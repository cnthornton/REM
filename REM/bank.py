"""
REM bank reconciliation configuration classes and objects.
"""

import datetime
import pandas as pd
import PySimpleGUI as sg
from random import randint
import sys

from REM.config import configuration
import REM.constants as mod_const
import REM.database as mod_db
import REM.elements as mod_elem
import REM.layouts as mod_layout
import REM.parameters as mod_param
import REM.secondary as mod_win2
from REM.settings import user


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
                mod_win2.popup_error('Error: BankRules: the parameter "name" is a required field')
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
                mod_win2.popup_error('Error: BankRules: the parameter "rules" is a required field')
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
            print('BankRules {NAME}, Rule {RULE} not in list of configured bank reconciliation rules. Available rules '
                  'are {ALL}'.format(NAME=self.name, RULE=name, ALL=', '.join(self.print_rules())))
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
        self.element_key = '-{NAME}_{ID}-'.format(NAME=name, ID=self.id)
        self.elements = ['-{NAME}_{ID}_{ELEM}-'.format(NAME=self.name, ID=self.id, ELEM=i) for i in
                         ['Main', 'Summary', 'Cancel', 'Save', 'Next', 'Back', 'Start', 'FrameWidth',
                          'FrameHeight', 'PanelWidth', 'PanelHeight', 'MoneyOutTabHeight', 'MoneyInTabHeight',
                          'Withdrawal', 'Deposit', 'MainTG', 'SummaryTG', 'SinkTG', 'SourceTG']]

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
                param_class = mod_param.DataParameterCombo
            elif param_layout == 'input':
                param_class = mod_param.DataParameterInput
            elif param_layout == 'date':
                param_class = mod_param.DataParameterDate
            elif param_layout == 'date_range':
                param_class = mod_param.DataParameterDateRange
            elif param_layout == 'checkbox':
                param_class = mod_param.DataParameterCheckbox
            elif param_layout == 'button':
                param_class = mod_param.DataParameterButton
            else:
                msg = 'Configuration Error: BankRule {NAME}: unknown type {TYPE} provided to DataParameter {PARAM}' \
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
            self.title = main_entry['Title']
        except KeyError:
            self.title = self.name

        self.tabs = []
        try:
            tab_entries = main_entry['Tabs']
        except KeyError:
            msg = 'Configuration Error: BankRule {NAME}: missing required "Main" parameter "Tabs"'.format(NAME=name)
            mod_win2.popup_error(msg)
            sys.exit(1)
        else:
            for tab_name in tab_entries:
                tab_rule = BankRecordTab(tab_name, tab_entries[tab_name], parent=self.name)

                self.tabs.append(tab_rule)
                self.elements += tab_rule.elements

        try:
            summary_entry = entry["Summary"]
        except KeyError:
            msg = 'Configuration Error: BankRule {NAME}: missing required "Summary"' \
                .format(NAME=name)
            mod_win2.popup_error(msg)
            sys.exit(1)

        try:
            self.summary_title = summary_entry["Title"]
        except KeyError:
            self.summary_title = self.name

        try:
            assoc_entries = summary_entry['Tabs']
        except KeyError:
            msg = 'Configuration Error: BankRule {NAME}: missing required parameter "Associations"'.format(NAME=name)
            mod_win2.popup_error(msg)
            sys.exit(1)

        self.associations = []
        for assoc_name in assoc_entries:
            assoc_entry = assoc_entries[assoc_name]
            assoc = BankAssociationTab(assoc_name, assoc_entry)

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
        element_names = [i[1:-1].split('_')[-1] for i in self.elements]
        if component in element_names:
            key_index = element_names.index(component)
            key = self.elements[key_index]
        else:
            print('Warning: BankRule {NAME}: component {COMP} not found in list of rule components'
                  .format(NAME=self.name, COMP=component))
            key = None

        return key

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
                print('Error: BankRule {RULE}: {TAB} not found in list of bank record tabs'
                      .format(RULE=self.name, TAB=fetch_key))
            else:
                tab_item = tabs[index]

        return tab_item

    def fetch_association(self, fetch_key, by_key: bool = False, by_title: bool = False):
        """
        Fetch an association rule by name or event key.
        """
        if by_key is True:
            element_type = fetch_key[1:-1].split('_')[-1]
            associations = [i.key_lookup(element_type) for i in self.associations]
        elif by_title is True:
            associations = [i.title for i in self.associations]
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
        titles = {i.name: i.title for i in self.tabs}

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
                                  [sg.TabGroup([source_tabs], key=source_tg_key, pad=(0, 0), enable_events=True,
                                               tab_background_color=inactive_col, selected_title_color=select_col,
                                               title_color=text_col, selected_background_color=bg_col,
                                               background_color=bg_col)]],
                                 pad=(pad_frame, pad_frame), background_color=bg_col, element_justification='c',
                                 vertical_alignment='t', expand_x=True, expand_y=True)]]

        source_key = self.key_lookup('Deposit')
        source_disabled = True if len(source_tabs) < 1 else False
        if source_disabled is True:
            title_col = disabled_col
        else:
            title_col = text_col

        deposit_title = titles.get('Deposit', 'Money In')
        source_tab = [sg.Tab(deposit_title, source_layout, key=source_key, title_color=title_col, background_color=bg_col,
                             disabled=source_disabled)]

        # Money Out layout
        sink_tg_key = self.key_lookup('SinkTG')
        sink_height_key = self.key_lookup('MoneyOutTabHeight')
        sink_layout = [[sg.Canvas(key=sink_height_key, size=(0, tab_height), background_color=bg_col),
                        sg.Col([[sg.Text('{} Expense Destinations'.format(self.menu_title), background_color=bg_col,
                                         font=font_h)],
                                [sg.TabGroup([sink_tabs], key=sink_tg_key, pad=(0, 0), enable_events=True,
                                             tab_background_color=inactive_col, selected_title_color=select_col,
                                             title_color=text_col, selected_background_color=bg_col,
                                             background_color=bg_col)]],
                               pad=(pad_frame, pad_frame), background_color=bg_col, element_justification='c',
                               vertical_alignment='t', expand_x=True, expand_y=True)]]

        sink_key = self.key_lookup('Withdrawal')
        sink_disabled = True if len(sink_tabs) < 1 else False
        if sink_disabled is True:
            title_col = disabled_col
        else:
            title_col = text_col

        withdrawal_title = titles.get('Withdrawal', 'Money Out')
        sink_tab = [sg.Tab(withdrawal_title, sink_layout, key=sink_key, title_color=title_col, background_color=bg_col,
                           disabled=sink_disabled)]

        # TabGroup layout
        tg_key = self.key_lookup('SummaryTG')
        panel_layout = [[sg.TabGroup([source_tab, sink_tab], key=tg_key, pad=(0, 0), enable_events=True,
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
        panel_title = 'Bank Reconciliation : {}'.format(self.title)
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

        # Tab layout
        tg_key = self.key_lookup('MainTG')
        tab_layouts = []
        for i, tab in enumerate(self.tabs):
            tab_layouts.append(tab.layout((tab_width, tab_height)))

        tg_layout = [sg.TabGroup([tab_layouts], key=tg_key, pad=(0, 0), enable_events=True,
                                 tab_background_color=inactive_col, selected_title_color=select_col,
                                 title_color=text_col, selected_background_color=bg_col, background_color=bg_col)]

        # Main panel layout
        main_key = self.key_lookup('Main')
        main_layout = sg.Col([param_layout,
                              [sg.HorizontalSeparator(pad=(0, pad_v), color=mod_const.HEADER_COL)],
                              tg_layout],
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

        # Resize tab elements
        tab_height = panel_height - 320  # minus size of the tabs and the panel title
        tab_width = panel_width - mod_const.FRAME_PAD * 2  # minus left and right padding

        tabs = self.tabs
        for tab in tabs:
            tab.resize_elements(window, (tab_width, tab_height))

        # Resize summary tab elements
        tab_height = panel_height - 30  # minus size of the tabs
        source_height_key = self.key_lookup('MoneyInTabHeight')
        window[source_height_key].set_size((None, tab_height))

        sink_height_key = self.key_lookup('MoneyOutTabHeight')
        window[sink_height_key].set_size((None, tab_height))

        tab_width = panel_width - 70
        for assoc in self.associations:
            assoc.table.resize(window, size=(tab_width, tab_height), row_rate=80)

    def run_event(self, window, event, values):
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
        main_tg_key = self.key_lookup('MainTG')
        summary_tg_key = self.key_lookup('SummaryTG')
        sink_tg_key = self.key_lookup('SinkTG')
        source_tg_key = self.key_lookup('SourceTG')

        # Component element events
        tab_keys = [i for j in self.tabs for i in j.elements]
        param_keys = [i for j in self.parameters for i in j.elements]
        association_keys = [i for j in self.associations for i in j.elements]

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

            # Collapse the filter frame of the first summary tab
            summary_tab = window[summary_tg_key].Get()
            trans_type = summary_tab[1:-1].split('_')[-1]
            if trans_type.lower() == 'deposit':
                tg_key = self.key_lookup('SourceTG')
            else:
                tg_key = self.key_lookup('SinkTG')

            tab_key = window[tg_key].Get()
            tab = self.fetch_association(tab_key, by_key=True)
            filter_key = tab.table.key_lookup('FilterFrame')
            if window[filter_key].metadata['visible'] is True:
                tab.table.collapse_expand(window, frame='filter')

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

            # Un-collapse the filter frame of all summary tabs
            for tab in self.associations:
                filter_key = tab.table.key_lookup('FilterFrame')
                if window[filter_key].metadata['visible'] is False:
                    tab.table.collapse_expand(window, frame='filter')

            # Switch to first tab
            tg_key = self.key_lookup('MainTG')
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
                elif (isinstance(param.value, list) or isinstance(param.value, tuple)) and any(param.value) is False:
                    param_desc = param.description
                    msg = 'Parameters {} and {} requires correctly formatted input in both fields'.format(*param_desc)
                    mod_win2.popup_notice(msg)
                    inputs.append(False)
                else:
                    inputs.append(True)

            # Load data from the database
            if all(inputs):  # all rule parameters have input
                initialized = []
                # Import tab data from the database
                for tab in self.tabs:
                    reftypes = tab.reference_record_types(self.associations)
                    initialized.append(tab.load_data(self.parameters, reftypes))

                # Import association data from the database
                for association in self.associations:
                    reftypes = association.reference_record_types(self.tabs)
                    initialized.append(association.load_data(self.parameters, reftypes))

                # Show that a bank reconciliation is in progress
                if all(initialized) is True:
                    self.in_progress = True
                    print('Info: BankRule {NAME}: bank reconciliation in progress with parameters {PARAMS}'
                          .format(NAME=self.name, PARAMS=', '.join(['{}={}'.format(i.name, i.value) for i in params])))

                    # Enable/Disable control buttons and parameter elements
                    window[start_key].update(disabled=True)
                    window[reconcile_key].update(disabled=False)

                    # Update the tab table display
                    for tab in self.tabs:
                        # Enable table element events
                        tab.table.enable(window)

                        # Add reference information to record table
                        tab.merge_references()

                        # Update the tab table display
                        tab.table.update_display(window)

                        # Enable the tab reconciliation button
                        window[tab.key_lookup('Reconcile')].update(disabled=False)

                    # Update the associate table events
                    for assoc in self.associations:
                        # Enable table element events
                        assoc.table.enable(window)

                        # Add reference information to record table
                        assoc.merge_references()

                        # Update the association display table
                        assoc.table.update_display(window)

                    self.toggle_parameters(window, 'disable')

        # Switch between tabs
        elif event == main_tg_key:
            tab_key = window[main_tg_key].Get()
            tab = self.fetch_tab(tab_key, by_key=True)
            print('Info: BankRule {NAME}: moving to bank record tab {TAB}'.format(NAME=self.name, TAB=tab.name))

            # Collapse the filter frame of current tab
            filter_key = tab.table.key_lookup('FilterFrame')
            if window[filter_key].metadata['visible'] is True:
                tab.table.collapse_expand(window, frame='filter')

            # Un-collapse the filter frame of all other tabs
            for unselected_tab in self.tabs:
                if tab.name == unselected_tab.name:
                    continue
                else:
                    filter_key = unselected_tab.table.key_lookup('FilterFrame')
                    if window[filter_key].metadata['visible'] is False:
                        unselected_tab.table.collapse_expand(window, frame='filter')

        # Switch between summary tabs
        elif event == summary_tg_key:
            summary_tab = window[summary_tg_key].Get()
            print('Info: BankRule {NAME}: moving to summary tab {TAB}'.format(NAME=self.name, TAB=summary_tab))

            trans_type = summary_tab[1:-1].split('_')[-1]
            if trans_type.lower() == 'deposit':
                tg_key = self.key_lookup('SourceTG')
            else:
                tg_key = self.key_lookup('SinkTG')

            tab_key = window[tg_key].Get()
            tab = self.fetch_association(tab_key, by_key=True)

            # Collapse the filter frame of current tab
            filter_key = tab.table.key_lookup('FilterFrame')
            if window[filter_key].metadata['visible'] is True:
                tab.table.collapse_expand(window, frame='filter')

            # Un-collapse the filter frame of all other tabs
            for unselected_tab in self.associations:
                if tab.name == unselected_tab.name:
                    continue
                else:
                    filter_key = unselected_tab.table.key_lookup('FilterFrame')
                    if window[filter_key].metadata['visible'] is False:
                        unselected_tab.table.collapse_expand(window, frame='filter')

        # Switch between summary sink tabs
        elif event == sink_tg_key:
            tab_key = window[sink_tg_key].Get()
            tab = self.fetch_association(tab_key, by_key=True)
            print('Info: BankRule {NAME}: moving to bank association tab {TAB}'.format(NAME=self.name, TAB=tab.name))

            # Collapse the filter frame of current tab
            filter_key = tab.table.key_lookup('FilterFrame')
            if window[filter_key].metadata['visible'] is True:
                tab.table.collapse_expand(window, frame='filter')

            # Un-collapse the filter frame of all other tabs
            for unselected_tab in self.associations:
                if tab.name == unselected_tab.name:
                    continue
                else:
                    filter_key = unselected_tab.table.key_lookup('FilterFrame')
                    if window[filter_key].metadata['visible'] is False:
                        unselected_tab.table.collapse_expand(window, frame='filter')

        # Switch between summary source tabs
        elif event == source_tg_key:
            tab_key = window[source_tg_key].Get()
            tab = self.fetch_association(tab_key, by_key=True)
            print('Info: BankRule {NAME}: moving to bank association tab {TAB}'.format(NAME=self.name, TAB=tab.name))

            # Collapse the filter frame of current tab
            filter_key = tab.table.key_lookup('FilterFrame')
            if window[filter_key].metadata['visible'] is True:
                tab.table.collapse_expand(window, frame='filter')

            # Un-collapse the filter frame of all other tabs
            for unselected_tab in self.associations:
                if tab.name == unselected_tab.name:
                    continue
                else:
                    filter_key = unselected_tab.table.key_lookup('FilterFrame')
                    if window[filter_key].metadata['visible'] is False:
                        unselected_tab.table.collapse_expand(window, frame='filter')

        # Run a tab event
        elif event in tab_keys:
            # Fetch the transaction tab
            try:
                tab = self.fetch_tab(event, by_key=True)
            except KeyError:
                print('Error: AuditRule {NAME}: unable to find transaction tab associated with event key {KEY}'
                      .format(NAME=self.name, KEY=event))
            else:
                if event == tab.key_lookup('Reconcile'):
                    # Run the primary reconciliation algorithm
                    tab.reconcile_statement(self.associations)

                    # Update the tab table display
                    for tab in self.tabs:
                        # Add reference information to record table
                        tab.merge_references()

                        # Update the tab table display
                        tab.table.update_display(window)

                    # Update the associate table events
                    for assoc in self.associations:
                        # Add reference information to record table
                        assoc.merge_references()

                        # Update the association display table
                        assoc.table.update_display(window)
                else:
                    tab.run_event(window, event, values)

            # Enable movement to summary panel if reconciliation has been performed for all tabs
            is_performed = []
            for tab in self.tabs:
                is_performed.append(tab.reconciled)

            if all(is_performed) is True:
                window[next_key].update(disabled=False)

        # Run an association event
        elif event in association_keys:
            # Fetch the association element
            try:
                association_table = self.fetch_association(event, by_key=True)
            except KeyError:
                print('Error: BankRule {NAME}: unable to find association table associated with event key {KEY}'
                      .format(NAME=self.name, KEY=event))
            else:
                association_table.run_event(window, event, values)

        # Run parameter events
        elif event in param_keys:
            try:
                param = self.fetch_parameter(event, by_key=True)
            except KeyError:
                print('Error: BankRule {NAME}: unable to find parameter associated with event key {KEY}'
                      .format(NAME=self.name, KEY=event))
            else:
                param.run_event(window, event, values)

        return current_rule

    def reset_rule(self, window, current: bool = False):
        """
        Reset rule to default.
        """
        self.in_progress = False

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
        tg_key = self.key_lookup('MainTG')
        window[tg_key].Widget.select(0)

        # Reset the parameter elements.
        self.reset_parameters(window)
        self.toggle_parameters(window, 'enable')

        # Reset tab attributes
        for i, tab in enumerate(self.tabs):
            tab.reset(window)

        # Reset association attributes
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
            param.reset(window)

    def toggle_parameters(self, window, value='enable'):
        """
        Enable / Disable audit rule parameter elements.
        """
        for parameter in self.parameters:
            parameter.toggle_parameter(window, value=value)


class BankRecordTab:
    """
    Bank record tab.

        name (str): rule name.

        id (int): rule element number.

        title (str): rule title.

        element_key (str): rule element key.

        elements (list): list of rule GUI element keys.
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
                         ['Tab', 'Reconcile']]

        try:
            self.title = entry['Title']
        except KeyError:
            self.title = name

        try:
            self.import_rules = entry['ImportRules']
        except KeyError:
            msg = 'Configuration Error: BankRecordTab {NAME}: missing required field "ImportRules".' \
                .format(NAME=name)
            mod_win2.popup_error(msg)
            sys.exit(1)

        try:
            self.table = mod_elem.TableElement(name, entry['DisplayTable'])
        except KeyError:
            msg = 'Configuration Error: BankRecordTab {NAME}: missing required parameter "DisplayTable"' \
                .format(NAME=name)
            mod_win2.popup_error(msg)
            sys.exit(1)
        except AttributeError as e:
            msg = 'Configuration Error: BankRecordTab {NAME}: unable to initialize DisplayTable - {ERR}' \
                .format(NAME=name, ERR=e)
            mod_win2.popup_error(msg)
            sys.exit(1)
        else:
            self.elements += self.table.elements

        try:
            association_rules = entry['AssociationRules']
        except KeyError:
            msg = 'Configuration Error: BankRecordTab {NAME}: missing required parameter "AssociationRules"' \
                .format(NAME=name)
            mod_win2.popup_error(msg)
            sys.exit(1)
        else:
            if 'Columns' in association_rules:
                self.association_columns = association_rules['Columns']
            else:
                msg = 'Configuration Error: BankRecordTab {NAME}: missing required "AssociationRules" parameter ' \
                      '"Columns"'.format(NAME=name)
                mod_win2.popup_error(msg)
                sys.exit(1)

            if 'Tables' in association_rules:
                self.association_tables = association_rules['Tables']
            else:
                msg = 'Configuration Error: BankRecordTab {NAME}: missing required "AssociationRules" parameter ' \
                      '"Tables"'.format(NAME=name)
                mod_win2.popup_error(msg)
                sys.exit(1)

        self.reconciled = False
        self.ref_df = pd.DataFrame(columns=['RecordID', 'ReferenceID', 'ReferenceWarnings'])

    def key_lookup(self, component):
        """
        Lookup a component's GUI element key using the component's name.
        """
        element_names = [i[1:-1].split('_')[-1] for i in self.elements]
        if component in element_names:
            key_index = element_names.index(component)
            key = self.elements[key_index]
        else:
            print('Warning: BankRecordTab {NAME}: component {COMP} not found in list of elements'
                  .format(NAME=self.name, COMP=component))
            key = None

        return key

    def reset(self, window):
        """
        Reset the elements and attributes of the bank record tab.
        """

        # Reset the data tables
        self.table.df = pd.DataFrame(columns=list(self.table.columns))
        self.table._df = pd.DataFrame(columns=list(self.table.columns))
        self.table.update_display(window)

        self.ref_df = pd.DataFrame(columns=['RecordID', 'ReferenceID', 'ReferenceWarnings'])

        # Disable table element events
        self.table.disable(window)

        # Un-collapse the tab filter frame
        filter_key = self.table.key_lookup('FilterFrame')
        if window[filter_key].metadata['visible'] is False:
            self.table.collapse_expand(window, frame='filter')

        # Disable the associate button
        window[self.key_lookup('Reconcile')].update(disabled=True)

    def layout(self, size):
        """
        GUI layout for the bank record tab.
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
        tbl_width = width - 30
        tbl_height = height * 0.9

        # Layout
        reconcile_key = self.key_lookup('Reconcile')
        main_layout = [[self.table.layout(width=tbl_width, height=tbl_height, padding=(0, 0))],
                       [sg.Col([[mod_layout.B1('Find Associations', key=reconcile_key, disabled=True,
                                               button_color=(bttn_text_col, bttn_bg_col),
                                               disabled_button_color=(disabled_text_col, disabled_bg_col),
                                               tooltip='Reconcile the selected bank records', use_ttk_buttons=True)]],
                               pad=(pad_frame, pad_frame), background_color=bg_col, element_justification='c',
                               expand_x=True)]]

        layout = [[sg.Col(main_layout, pad=(pad_frame, pad_frame), justification='c', vertical_alignment='t',
                          background_color=bg_col, expand_x=True)]]

        return sg.Tab(self.title, layout, key=self.key_lookup('Tab'), background_color=bg_col)

    def resize_elements(self, window, size):
        """
        Resize the bank record tab.
        """
        width, height = size

        # Reset table size
        tbl_width = width - 30  # includes padding on both sides and scroll bar
        tbl_height = int(height * 0.90)
        self.table.resize(window, size=(tbl_width, tbl_height), row_rate=40)

    def run_event(self, window, event, values):
        """
        Run a bank record tab event.
        """
        reconcile_key = self.key_lookup('Reconcile')
        table_keys = self.table.elements

        success = True
        # Run component table events
        if event in table_keys:
            table = self.table

            import_key = self.table.key_lookup('Import')
            export_key = self.table.key_lookup('Element')
            if event == import_key:
                table.df = table.import_rows(self.import_rules, id_only=True)
                table.update_display(window, window_values=values)
            elif event == export_key:
                # Find row selected by user
                try:
                    select_row_index = values[event][0]
                except IndexError:  # user double-clicked too quickly
                    print('Warning: DataTable {NAME}: table row could not be selected'.format(NAME=self.name))
                else:
                    if table.actions['open'] is True:
                        table.df = table.export_row(select_row_index, level=0)
                    elif table.actions['open'] is False and table.actions['edit'] is True:
                        table.df = table.edit_row(select_row_index)

            else:
                table.run_event(window, event, values)

        return success

    def load_data(self, parameters, reference_types):
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
            df = user.query(table_statement, columns=columns, filter_rules=filters, prog_db=True)
        except Exception as e:
            mod_win2.popup_error('Error: BankRecordTab {NAME}: failed to import data from the database - {ERR}'
                                 .format(NAME=self.name, ERR=e))
            data_loaded = False
        else:
            print('Info: BankRecordTab {NAME}: loaded data for bank reconciliation {RULE}'
                  .format(NAME=self.name, RULE=self.parent))
            # Update record table with imported data
            self.table.df = self.table.append(df)
            self.table.initialize_defaults()
            self.table._df = self.table.df
            data_loaded = True

            # Update reference table with reference data
            if len(reference_types) > 0:
                ref_filters = [('DocType IN ({})'.format(','.join(['?' for _ in reference_types])),
                                tuple(reference_types))]
            else:
                ref_filters = []

            ref_map = {'DocNo': 'ReferenceID', 'RefNo': 'RecordID', 'Warnings': 'ReferenceWarnings'}
            record_ids = tuple(df[self.table.id_column].tolist())
            if len(record_ids) > 0:
                ref_filters += [('RefNo IN ({})'.format(','.join(['?' for _ in record_ids])), record_ids)]
                try:
                    ref_df = user.query(configuration.reference_lookup, filter_rules=ref_filters, prog_db=True)
                except Exception as e:
                    mod_win2.popup_error('Error: BankRecordTab {NAME}: failed to import data from the database - {ERR}'
                                         .format(NAME=self.name, ERR=e))
                    data_loaded = False
                else:
                    ref_df = ref_df[list(ref_map)]
                    ref_df.rename(columns=ref_map, inplace=True)
                    self.ref_df = self.ref_df.append(ref_df, ignore_index=True)
                    print(self.ref_df)

        return data_loaded

    def merge_references(self):
        """
        Merge references with record table.
        """
        pd.set_option('display.max_columns', None)
        table = self.table
        df = table.df.copy()
        ref_df = self.ref_df

        df = df.set_index(table.id_column)
        df = df.combine_first(ref_df.set_index('RecordID'))
        df.rename_axis(table.id_column, inplace=True)
        df.reset_index(inplace=True)

        self.table.df = df

    def reference_record_types(self, associations):
        """
        Get list of relevant record types for association.
        """
        reftypes = []
        for association in associations:
            if association.type != self.name:
                continue

            record_type = association.table.record_type
            if record_type not in reftypes:
                reftypes.append(record_type)

        return reftypes

    def reconcile_statement(self, associations):
        """
        Run the primary Bank Reconciliation rule algorithm for the record tab.
        """
        rule_columns = self.association_columns
        rule_tables = self.association_tables
        table = self.table
        df = table.df.copy()
        ref_df = self.ref_df
        ref_table = configuration.reference_lookup

        # Filter out rows that are already associated with another record
        df.drop(df[df[table.id_column].isin(ref_df['RecordID'].tolist())].index, inplace=True)

        # Define the fields that will be included in the merged association table
        core_cols = []
        expanded_cols = []
        rule_fields = ["Association", "RecordID", "RecordType"]
        for assoc_column in rule_columns:
            rule_entry = rule_columns[assoc_column]
            if assoc_column not in rule_fields:
                rule_fields.append(assoc_column)
            try:
                expanded = bool(int(rule_entry['Expand']))
            except (KeyError, ValueError, TypeError):
                expanded = False

            if expanded is False:
                core_cols.append(assoc_column)
            else:
                expanded_cols.append(assoc_column)

        # Initialize the merged association table
        merged_df = pd.DataFrame(columns=rule_fields)

        # Add association table data to the merged table
        assoc_names = []
        for association in associations:
            assoc_name = association.name
            assoc_names.append(assoc_name)

            if assoc_name in rule_tables:
                rule_entry = rule_tables[assoc_name]

                # Create the column mapping
                col_map = {rule_entry[i]: i for i in rule_entry}
                col_map[association.table.id_column] = "RecordID"

                # Filter out rows that are already associated with another record
                assoc_df = association.table.df.copy()
                assoc_df.drop(assoc_df[assoc_df[association.table.id_column].isin(association.ref_df['RecordID'])].index,
                              inplace=True)

                # Subset by relevant columns
                assoc_df = assoc_df[list(col_map)]

                # Change relevant column names
                assoc_df.rename(columns=col_map, inplace=True)

                # Add table name and index columns
                assoc_df["Association"] = assoc_name
#                assoc_df["Index"] = assoc_df.index
                assoc_df["RecordType"] = association.table.record_type

                # Subset dataframe on relevant columns
                assoc_df = assoc_df[rule_fields]

                # Concatentate association tables
                merged_df = merged_df.append(assoc_df, ignore_index=True)

        print('merged df is:')
        print(merged_df.head())

        # Iterate over record rows, attempting to find matches in the merged table
        for index, row in df.iterrows():
            record_id = row[table.id_column]

            # Attempt to find exact matches using all columns, both core and expanded
            matches = merged_df[merged_df[core_cols + expanded_cols].eq(row[core_cols + expanded_cols]).all(axis=1)]
            nmatch = matches.shape[0]
            if nmatch == 0:  # no matching entries in the merged dataset
                # Attempt to find matches using only the core columns
                matches = merged_df[merged_df[core_cols].eq(row[core_cols]).all(axis=1)]
                nmatch = matches.shape[0]
                if nmatch == 0:  # no matches found given the parameters supplied
                    continue

                elif nmatch == 1:  # found one exact match using the column subset
                    results = matches.iloc[0]

                    # Get the relevant association table
                    assoc_name = results['Association']
                    association = associations[assoc_names.index(assoc_name)]

                    # Determine appropriate warning for the expanded search
                    warning = "expanded search"

                    # Create an entry in the association reference table for the match
                    ref_id = results['RecordID']
                    ref_table_columns = ['DocNo', 'RefNo', 'RefDate', 'DocType', 'RefType', 'Warnings',
                                         configuration.creator_code, configuration.creation_date]

                    ref_entry = [record_id, ref_id, datetime.datetime.now(), table.record_type, results['RecordType'],
                                 warning, user.uid, datetime.datetime.now()]
                    entry_saved = user.insert(ref_table, ref_table_columns, ref_entry)
                    if entry_saved is False:
                        msg = 'failed to save record {ID} references to {REF} to database table {TBL}' \
                            .format(ID=ref_id, REF=record_id, TBL=ref_table)
                        mod_win2.popup_error(msg)

                    reference = pd.Series([ref_id, record_id, warning],
                                          index=['RecordID', 'ReferenceID', 'ReferenceWarnings'])
                    association.ref_df = association.ref_df.append(reference, ignore_index=True)

                    # Create an entry in the reference table for the match
                    ref_entry = [ref_id, record_id, datetime.datetime.now(), results['RecordType'], table.record_type,
                                 warning, user.uid, datetime.datetime.now()]
                    entry_saved = user.insert(ref_table, ref_table_columns, ref_entry)
                    if entry_saved is False:
                        msg = 'failed to save record {ID} references to {REF} to database table {TBL}' \
                            .format(ID=record_id, REF=ref_id, TBL=ref_table)
                        mod_win2.popup_error(msg)

                    reference = pd.Series([record_id, ref_id, warning],
                                          index=['RecordID', 'ReferenceID', 'ReferenceWarnings'])
                    ref_df = ref_df.append(reference, ignore_index=True)

                elif nmatch > 1:  # too many matches
                    print('too many matches for record: {}'.format(row["RecordID"]))

            elif nmatch == 1:  # found one exact match
                results = matches.iloc[0]

                # Get the relevant association table
                assoc_name = results['Association']
                association = associations[assoc_names.index(assoc_name)]

                # Create an entry in the association reference table for the match
                ref_id = results['RecordID']
                ref_table_columns = ['DocNo', 'RefNo', 'RefDate', 'DocType', 'RefType',
                                     configuration.creator_code, configuration.creation_date]

                ref_entry = [record_id, ref_id, datetime.datetime.now(),
                             table.record_type, results['RecordType'], user.uid, datetime.datetime.now()]
                entry_saved = user.insert(ref_table, ref_table_columns, ref_entry)
                if entry_saved is False:
                    msg = 'failed to save record {ID} references to {REF} to database table {TBL}' \
                        .format(ID=ref_id, REF=record_id, TBL=ref_table)
                    mod_win2.popup_error(msg)

                reference = pd.Series([ref_id, record_id, None],
                                      index=['RecordID', 'ReferenceID', 'ReferenceWarnings'])
                association.ref_df = association.ref_df.append(reference, ignore_index=True)

                # Create an entry in the reference table for the match
                ref_entry = [ref_id, record_id, datetime.datetime.now(), results['RecordType'], table.record_type,
                             user.uid, datetime.datetime.now()]
                entry_saved = user.insert(ref_table, ref_table_columns, ref_entry)
                if entry_saved is False:
                    msg = 'failed to save record {ID} references to {REF} to database table {TBL}' \
                        .format(ID=record_id, REF=ref_id, TBL=ref_table)
                    mod_win2.popup_error(msg)

                reference = pd.Series([record_id, ref_id, None],
                                      index=['RecordID', 'ReferenceID', 'ReferenceWarnings'])
                ref_df = ref_df.append(reference, ignore_index=True)

            elif nmatch > 1:  # too many matches
                print('too many matches for record: {}'.format(row["RecordID"]))

        self.reconciled = True
        self.ref_df = ref_df


class BankAssociationTab:
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
        self.elements = ['-{NAME}_{ID}_{ELEM}-'.format(NAME=self.name, ID=self.id, ELEM=i) for i in ['Tab']]

        try:
            self.title = entry['Title']
        except KeyError:
            self.title = name

        try:
            transaction_type = entry['Type']
        except KeyError:
            msg = 'Configuration Error: BankAssociationTab {NAME}: missing required parameter "Type"' \
                .format(NAME=name)
            mod_win2.popup_error(msg)
            sys.exit(1)
        else:
            if transaction_type not in ('Deposit', 'Withdrawal'):
                msg = 'Configuration Error: BankAssociationTab {NAME}: unsupported value {VAL} provided to parameter ' \
                      '"Type". Type must be one of "Deposit" or "Withdrawal"'.format(NAME=name, VAL=transaction_type)
                mod_win2.popup_error(msg)
                sys.exit(1)
            else:
                self.type = transaction_type

        try:
            self.table = mod_elem.TableElement(name, entry['DisplayTable'])
        except KeyError:
            msg = 'Configuration Error: BankAssociationTab {NAME}: missing required parameter "DisplayTable"' \
                .format(NAME=name)
            mod_win2.popup_error(msg)
            sys.exit(1)
        except AttributeError as e:
            msg = 'Configuration Error: BankAssociationTab {NAME}: unable to initialize DisplayTable - {ERR}' \
                .format(NAME=name, ERR=e)
            mod_win2.popup_error(msg)
            sys.exit(1)
        else:
            self.elements += self.table.elements

        try:
            self.import_rules = entry['ImportRules']
        except KeyError:
            msg = 'Configuration Error: BankAssociationTab {NAME}: missing required parameter "ImportRules"' \
                .format(NAME=name)
            mod_win2.popup_error(msg)
            sys.exit(1)

        self.ref_df = pd.DataFrame(columns=['RecordID', 'ReferenceID', 'ReferenceWarnings'])

    def key_lookup(self, component):
        """
        Lookup a component's GUI element key using the component's name.
        """
        element_names = [i[1:-1].split('_')[-1] for i in self.elements]
        if component in element_names:
            key_index = element_names.index(component)
            key = self.elements[key_index]
        else:
            print('Warning: BankAssociationTab {NAME}: component {COMP} not found in list of class components'
                  .format(NAME=self.name, COMP=component))
            key = None

        return key

    def run_event(self, window, event, values):
        """
        Run an association table event.
        """
        # Component element events
        table_keys = self.table.elements

        # Table event
        if event in table_keys:
            table = self.table

            import_key = self.table.key_lookup('Import')
            export_key = self.table.key_lookup('Element')
            if event == import_key:
                table.df = table.import_rows(self.import_rules, id_only=True)
                table.update_display(window, window_values=values)
            elif event == export_key:
                # Find row selected by user
                try:
                    select_row_index = values[event][0]
                except IndexError:  # user double-clicked too quickly
                    print('Warning: DataTable {NAME}: table row could not be selected'.format(NAME=self.name))
                else:
                    if table.actions['open'] is True:
                        table.df = table.export_row(select_row_index, level=0)
                    elif table.actions['open'] is False and table.actions['edit'] is True:
                        table.df = table.edit_row(select_row_index)

                    # Check if reference was removed
            else:
                table.run_event(window, event, values)

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
        self.table._df = pd.DataFrame(columns=list(self.table.columns))
        self.table.update_display(window)

        self.ref_df = pd.DataFrame(columns=['RecordID', 'ReferenceID', 'ReferenceWarnings'])

        # Disable table element events
        self.table.disable(window)

        # Un-collapse the table filter frame
        filter_key = self.table.key_lookup('FilterFrame')
        if window[filter_key].metadata['visible'] is False:
            self.table.collapse_expand(window, frame='filter')

    def load_data(self, parameters, reference_types):
        """
        Load association data from the database.
        """
        # Prepare the database query statement
        import_rules = self.import_rules

        filters = mod_db.format_import_filters(import_rules)
        table_statement = mod_db.format_tables(import_rules)
        columns = mod_db.format_import_columns(import_rules)

        # Add parameter values to the filter statement
        rule_params = parameters  # to filter data tables
        filters += [i.query_statement(mod_db.get_import_column(import_rules, i.name)) for i in rule_params]

        # Import primary bank data from database
        try:
            df = user.query(table_statement, columns=columns, filter_rules=filters, prog_db=True)
        except Exception as e:
            mod_win2.popup_error('Error: BankRuleAssociation {NAME}: failed to import data from the database - {ERR}'
                                 .format(NAME=self.name, ERR=e))
            data_loaded = False
        else:
            # Update the record table with imported data
            self.table.df = self.table.append(df)
            self.table.initialize_defaults()
            self.table._df = self.table.df
            data_loaded = True

            # Update reference table with imported reference data
            if len(reference_types) > 0:
                ref_filters = [('DocType IN ({})'.format(','.join(['?' for _ in reference_types])),
                                tuple(reference_types))]
            else:
                ref_filters = []

            ref_map = {'DocNo': 'ReferenceID', 'RefNo': 'RecordID', 'Warnings': 'ReferenceWarnings'}
            record_ids = tuple(df[self.table.id_column].tolist())
            if len(record_ids) > 0:
                ref_filters += [('RefNo IN ({})'.format(','.join(['?' for _ in record_ids])), record_ids)]
                try:
                    ref_df = user.query(configuration.reference_lookup, filter_rules=ref_filters, prog_db=True)
                except Exception as e:
                    mod_win2.popup_error(
                        'Error: BankRuleAssociation {NAME}: failed to import data from the database - {ERR}'
                            .format(NAME=self.name, ERR=e))
                    data_loaded = False
                else:
                    ref_df = ref_df[list(ref_map)]
                    ref_df.rename(columns=ref_map, inplace=True)
                    self.ref_df = self.ref_df.append(ref_df, ignore_index=True)
                    print(self.ref_df)

        return data_loaded

    def merge_references(self):
        """
        Merge references with record table.
        """
        table = self.table
        df = table.df.copy()
        ref_df = self.ref_df

        df = df.set_index(table.id_column)
        df = df.combine_first(ref_df.set_index('RecordID'))
        df.rename_axis(table.id_column, inplace=True)
        df.reset_index(inplace=True)

        self.table.df = df

    def reference_record_types(self, tabs):
        """
        Get list of relevant record types for association.
        """
        reftypes = []
        for tab in tabs:
            if tab.name != self.type:
                continue

            record_type = tab.table.record_type
            if record_type not in reftypes:
                reftypes.append(record_type)

        return reftypes
