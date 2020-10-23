# -*- coding: utf-8 -*-
"""
REM main program. Includes primary display.
"""

__version__ = '0.6.2'

import datetime
from multiprocessing import freeze_support
import PySimpleGUI as sg
import REM.audit as audit
import REM.bank as bank
import REM.cash as cash
import REM.data_manipulation as dm
from REM.config import Config, settings
import REM.layouts as lo
import REM.secondary as win2
import REM.constants as const
import sys
import tkinter as tk


# Classes
class ToolBar:
    """
    Toolbar object.
    """

    def __init__(self, account_methods):
        """
        Initialize toolbar parameters.
        """
        acct_menu = []
        for account_method in account_methods:
            acct_menu.append(('', account_method.title))

            rules = []
            for rule in account_method.rules:
                rules.append(('!', rule.title))

            acct_menu.append(rules)

        self.name = 'toolbar'
        self.elements = ['amenu', 'rmenu', 'umenu', 'mmenu']
        self.acct_menu = {'name': '&Audits', 'items': acct_menu}
        self.reports_menu = {'name': 'Reports',
                             'items': [('!', 'Summary S&tatistics'), ('!', 'Summary &Reports')]}
        self.user_menu = {'name': '&User',
                          'items': [('!', '&Manage Accounts'), ('!', 'M&essages'), ('', '---'), ('', 'Sign &In'),
                                    ('!', 'Sign &Out')]}
        self.menu_menu = {'name': '&Menu',
                          'items': [('!', '&Settings'), ('', '&Debug'), ('', '---'), ('', '&Help'),
                                    ('', 'A&bout'), ('', '---'), ('', '&Quit')]}

    def key_lookup(self, element):
        """
        Lookup key for element in schema.
        """
        elements = self.elements
        if element in elements:
            key = lo.as_key('{}'.format(element))
        else:
            key = None

        return key

    def layout(self, win_size: tuple = None):
        """
        Create the layout for the toolbar GUI element.
        """
        if win_size:
            width, height = win_size
        else:
            width, height = (const.WIN_WIDTH, const.WIN_HEIGHT)

        # Menu items
        menu_audit = self.menu_definition('amenu')
        menu_reports = self.menu_definition('rmenu')
        menu_user = self.menu_definition('umenu')
        menu_menu = self.menu_definition('mmenu')

        # Layout settings
        audit_ico = const.AUDIT_ICON
        report_ico = const.REPORT_ICON
        db_ico = const.DB_ICON
        user_ico = const.USER_ICON
        menu_ico = const.MENU_ICON
        padding = const.TOOLBAR_PAD
        header_col = const.HEADER_COL
        text_col = const.TEXT_COL

        toolbar = [[sg.Col([[sg.ButtonMenu('', menu_audit, key='-AMENU-', image_data=audit_ico, tooltip=_('Run Audits'),
                                           button_color=(text_col, header_col), pad=(padding, padding)),
                             sg.ButtonMenu('', menu_reports, key='-RMENU-', image_data=report_ico,
                                           button_color=(text_col, header_col),
                                           tooltip=_('Generate Reports & Statistics'), pad=(padding, padding)),
                             sg.Button('', image_data=db_ico, key='-DBMENU-', tooltip=_('Modify Database'),
                                       button_color=(text_col, header_col), pad=(padding, padding), border_width=0,
                                       disabled=True)]],
                           justification='l', background_color=header_col),
                    sg.Canvas(key='-CANVAS_WIDTH-', size=(width - 260, 0), visible=True),
                    sg.Col([[sg.ButtonMenu('', menu_user, key='-UMENU-', pad=(padding, padding), image_data=user_ico,
                                           button_color=(text_col, header_col),
                                           tooltip=_('User Settings')),
                             sg.ButtonMenu('', menu_menu, key='-MMENU-', pad=(padding, padding), image_data=menu_ico,
                                           button_color=(text_col, header_col),
                                           tooltip=_('Help and program settings'))]],
                           justification='r', background_color=header_col)]]

        layout = [sg.Frame('', toolbar, key='-TOOLBAR-', relief='groove', pad=(0, 0), background_color=header_col)]

        return layout

    def update_username(self, window, username):
        """
        Update user menu to display username after a user is logged in.
        """
        select_col = const.SELECT_TEXT_COL

        element_key = '-UMENU-'

        # Update menu list to include the username
        user_items = [('', username), ('', '---')] + self.user_menu['items']
        user_menu = {'name': '&User', 'items': user_items}

        menu_def = self.menu_definition('umenu', menu=user_menu)

        window[element_key].update(menu_def)

        # Change username color
        window[element_key].TKMenu.entryconfig(0, foreground=select_col)
        window[element_key].TKButtonMenu.configure(menu=window[element_key].TKMenu)

    def menu_definition(self, menu_item, menu=None):
        """
        Return the menu definition for a menu.
        """
        menus = {'amenu': self.acct_menu, 'rmenu': self.reports_menu,
                 'umenu': self.user_menu, 'mmenu': self.menu_menu}

        if menu is None:
            try:
                menu_object = menus[menu_item.lower()]
            except KeyError:
                print('Error: selected menu {} not list of available menus'.format(menu_item))
                return None
        else:
            menu_object = menu

        menu_items = []
        for item in menu_object['items']:
            if isinstance(item, tuple):
                menu_items.append('{}{}'.format(*item))
            elif isinstance(item, list):
                sub_list = []
                for sub_item in item:
                    sub_list.append('{}{}'.format(*sub_item))
                menu_items.append(sub_list)

        menu_def = [menu_object['name'], menu_items]

        return menu_def

    def toggle_menu(self, window, menu, menu_item, value: str = 'enable'):
        """
        Enable / disable menu items.
        """
        menus = {'amenu': self.acct_menu, 'rmenu': self.reports_menu,
                 'umenu': self.user_menu, 'mmenu': self.menu_menu}

        try:
            select_menu = menus[menu.lower()]
        except KeyError:
            print('Error: selected menu {} not list of available menus'.format(menu))
            return False

        status = '' if value == 'enable' else '!'

        new_menu = []
        menu_items = select_menu['items']
        for item in menu_items:
            if isinstance(item, tuple):
                clean_item = item[1].replace('&', '')
                if menu_item in (clean_item, clean_item.lower()):
                    item_name = item[1]

                    # Replace menu item with updated status
                    new_menu.append((status, item_name))
                else:
                    new_menu.append(item)
            elif isinstance(item, list):
                sub_menu = []
                for sub_item in item:
                    clean_item = sub_item[1].replace('&', '')
                    if menu_item in (clean_item, clean_item.lower()):
                        item_name = sub_item[1]

                        # Replace menu item with updated status
                        sub_menu.append((status, item_name))
                    else:
                        sub_menu.append(sub_item)

                new_menu.append(sub_menu)

        # Replace menu item with updated status
        select_menu['items'] = new_menu

        # Update window to reflect updated status of the menu item
        element_key = self.key_lookup(menu.lower())
        window[element_key].update(self.menu_definition(menu))

        return True


# General functions
def get_panels(account_methods, win_size: tuple = None):
    """
    """
    if win_size:
        width, height = win_size
    else:
        width, height = (const.WIN_WIDTH, const.WIN_HEIGHT)

    # Home page action panel
#    panels = [lo.action_layout(account_methods)]
    panels = [lo.home_screen()]

    # Add Audit rule with summary panel
    for account_method in account_methods:
        for rule in account_method.rules:
            panels.append(rule.layout(win_size=win_size))
            try:
                panels.append(rule.summary.layout(win_size=win_size))
            except AttributeError:
                continue

    # Layout
    pane = [sg.Canvas(size=(0, height), key='-CANVAS_HEIGHT-', visible=True),
            sg.Col([[sg.Pane(panels, key='-PANEWINDOW-', orientation='horizontal', show_handle=False, border_width=0,
                             relief='flat')]], pad=(0, 10), justification='c', element_justification='c')]

    return pane


def resize_elements(window, rules, win_size: tuple = None):
    """
    Resize GUI elements when window is resized
    """
    win_size = win_size if win_size else window.size
    width, height = win_size

    # Update toolbar and pane elements
    menu_size = 260
    window['-CANVAS_HEIGHT-'].set_size((None, height))
    window['-CANVAS_WIDTH-'].set_size((width - menu_size, None))

    # Update audit rule elements
    for rule in rules:
        rule.resize_elements(window, win_size=win_size)
        try:
            rule.summary.resize_elements(window, win_size=win_size)
        except AttributeError:
            continue


def format_date_element(date_str):
    """
    Forces user input to date element to be in ISO format.
    """
    buff = []
    for index, char in enumerate(date_str):
        if index == 3:
            if len(date_str) != 4:
                buff.append('{}-'.format(char))
            else:
                buff.append(char)
        elif index == 5:
            if len(date_str) != 6:
                buff.append('{}-'.format(char))
            else:
                buff.append(char)
        else:
            buff.append(char)

    return ''.join(buff)


def main():
    """
    Main function.
    """
    strptime = datetime.datetime.strptime

    # Theme
    default_col = const.DEFAULT_COL
    action_col = const.ACTION_COL
    text_col = const.TEXT_COL
    font = const.MAIN_FONT

    sg.set_options(element_padding=(0, 0), margins=(0, 0),
                   auto_size_buttons=True, auto_size_text=True,
                   background_color=default_col, element_text_color=text_col,
                   element_background_color=default_col, font=font,
                   input_text_color=text_col, text_color=text_col,
                   text_element_background_color=default_col,
                   input_elements_background_color=action_col,
                   button_color=(text_col, default_col))

    # Original window size
    root = tk.Tk()
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    root.destroy()
    del root

    if screen_w >= const.WIN_WIDTH:
        current_w = const.WIN_WIDTH
    else:
        current_w = screen_w

    if screen_h >= const.WIN_HEIGHT:
        current_h = const.WIN_HEIGHT
    else:
        current_h = screen_h

    # Load the program configuration
    cnfg = Config()
    cnfg.load_configuration()

    audit_rules = audit.AuditRules(cnfg)
    cash_rules = cash.CashRules(cnfg)
    bank_rules = bank.BankRules(cnfg)
    startup_msgs = cnfg.startup_msgs

    acct_methods = [audit_rules, cash_rules]

    # Configure GUI layout
    toolbar = ToolBar([audit_rules, cash_rules, bank_rules])
    layout = [toolbar.layout(win_size=(current_w, current_h)),
              get_panels(acct_methods, win_size=(current_w, current_h))]

    # Element keys and names
    audit_names = audit_rules.print_rules()
    cash_names = cash_rules.print_rules()
    bank_names = bank_rules.print_rules()

    cancel_keys = [i.key_lookup('Cancel') for i in audit_rules.rules]
    cancel_keys += [i.summary.key_lookup('Cancel') for i in audit_rules.rules]
    cancel_keys += [i.key_lookup('Cancel') for i in cash_rules.rules]
    #    start_keys = [i.key_lookup('Start') for i in audit_rules.rules]

    summ_tbl_keys = []
    for rule in audit_rules.rules:
        for summary_item in rule.summary.summary_items:
            summ_tbl_keys.append(summary_item.key_lookup('Table'))
            summ_tbl_keys.append(summary_item.key_lookup('Totals'))

    date_key = None

    print('Info: current audit rules are {}'.format(', '.join(audit_names)))
    report_tx = 'Summary Report'
    stats_tx = 'Summary Statistics'

    # Event modifiers
    action_in_progress = False
    summary_panel_active = False
    current_tab = None
    current_rule = None
    debug_win = None

    # Initialize main window and login window
    window = sg.Window('REM Tila', layout, icon=settings.logo, font=const.MAIN_FONT, size=(current_w, current_h),
                       resizable=True, return_keyboard_events=True)
    window.finalize()
    window.maximize()
    print('Info: starting up')

    screen_w, screen_h = window.get_screen_dimensions()
    print('Info: screen size is {W} x {H}'.format(W=screen_w, H=screen_h))

    user_image = tk.PhotoImage(data=const.USER_ICON)
    userin_image = tk.PhotoImage(data=const.USERIN_ICON)

    all_rules = [i for acct_method in acct_methods for i in acct_method.rules]
    resize_elements(window, all_rules, win_size=(current_w, current_h))
    resized = False

    # Event Loop
    home_panel = current_panel = '-HOME-'
    while True:
        event, values = window.read(timeout=100)

        # Quit program
        if event == sg.WIN_CLOSED or values['-MMENU-'] == 'Quit':
            break

        # Resize screen
        if resized and current_panel != home_panel:
            window[current_panel].update(visible=False)
            window['-HOME-'].update(visible=True)

            window.refresh()

            window['-HOME-'].update(visible=False)
            window[current_panel].update(visible=True)

            resized = False

        # Resize screen
        ## Get window dimensions
        win_w, win_h = window.size
        if win_w != current_w or win_h != current_h:
            print('Info: new window size is {W} x {H}'.format(W=win_w, H=win_h))

            # Update sizable elements
            resize_elements(window, all_rules, win_size=(win_w, win_h))

            current_w, current_h = (win_w, win_h)
            resized = True
            continue

        # User login
        if values['-UMENU-'] == 'Sign In':  # user logs on
            print('Info: displaying user login screen')
            user = win2.login_window()

            if user.logged_in:  # logged on successfully
                # Disable sign-in and enable sign-off
                toolbar.toggle_menu(window, 'umenu', 'sign in', value='disable')
                toolbar.toggle_menu(window, 'umenu', 'sign out', value='enable')

                # Switch user icon
                window['-UMENU-'].Widget.configure(image=userin_image)

                # Enable permission specific actions and menus

                # Admin only actions and menus
                admin = user.admin
                if admin:
                    # Database administration
                    window['-DBMENU-'].update(disabled=False)

                    # Reports and statistics
                    toolbar.toggle_menu(window, 'rmenu', 'summary reports', value='enable')
                    toolbar.toggle_menu(window, 'rmenu', 'summary statistics', value='enable')

                    # User
                    toolbar.toggle_menu(window, 'umenu', 'manage accounts', value='enable')

                    # Menu
                    toolbar.toggle_menu(window, 'mmenu', 'settings', value='enable')

                # Enable permissions on per audit rule basis defined in config
                for acct_method in acct_methods:
                    for acct_rule in acct_method.rules:
                        rule_name = acct_rule.title
                        if admin:
                            toolbar.toggle_menu(window, 'amenu', rule_name, value='enable')
                        else:
                            perms = acct_rule.permissions
                            if perms != 'admin':
                                toolbar.toggle_menu(window, 'amenu', rule_name, value='enable')

                # Update user menu items to include the login name
                toolbar.update_username(window, user.uid)
            else:
                print('Error: unable to login to the program')
                continue

        # User log-off
        if values['-UMENU-'] == 'Sign Out':  # user signs out
            # Confirm sign-out
            msg = _('Are you sure you would like to sign-out?')
            selection = win2.popup_confirm(msg)

            if selection == 'Cancel':
                continue

            action_in_progress = False
            current_panel = current_rule.reset_rule(window)  # reset to home screen
            current_rule = None

            # Reset User attributes
            user.logout()

            # Switch user icon
            window['-UMENU-'].Widget.configure(image=user_image)

            # Disable sign-out and enable sign-in
            toolbar.toggle_menu(window, 'umenu', 'sign in', value='enable')
            toolbar.toggle_menu(window, 'umenu', 'sign out', value='disable')

            # Disable all actions and menus
            # Database administration
            window['-DBMENU-'].update(disabled=True)

            # Reports and statistics
            toolbar.toggle_menu(window, 'rmenu', 'summary reports', value='disable')
            toolbar.toggle_menu(window, 'rmenu', 'summary statistics', value='disable')

            # User
            toolbar.toggle_menu(window, 'umenu', 'manage accounts', value='disable')

            # Menu
            toolbar.toggle_menu(window, 'mmenu', 'settings', value='disable')

            # Audit rules
            for acct_method in acct_methods:
                for acct_rule in acct_method.rules:
                    rule_name = acct_rule.title
                    toolbar.toggle_menu(window, 'amenu', rule_name, value='disable')

        # Display the edit settings window
        if values['-MMENU-'] == 'Settings':
            win2.edit_settings(win_size=window.size)
            continue

        # Display "About" window
        if values['-MMENU-'] == 'About':
            win2.about()
            continue

        # Display the database update window
        if event == '-DBMENU-':
            win2.database_importer_window(user)
            continue

        # Display debugger window
        if not debug_win and values['-MMENU-'] == 'Debug':
            debug_win = win2.debugger()
            debug_win.finalize()

            print('Info: starting debugger')
            continue
        elif debug_win:
            debug_event, debug_value = debug_win.read(timeout=1000)

            if debug_event == sg.WIN_CLOSED:
                debug_win.close()
                debug_win = None
            else:
                debug_win['-DEBUG-'].expand(expand_x=True, expand_y=True)

        # Switch to home panel
        if current_panel != '-HOME-' and (event in cancel_keys or values['-AMENU-'] or values['-RMENU-']):
            if action_in_progress:  # ask to switch first
                msg = _('Current action is ongoing. Are you sure you would like to exit without saving?')
                selection = win2.popup_confirm(msg)

                if selection == 'OK':
                    # Reset to defaults
                    toolbar.toggle_menu(window, 'mmenu', 'settings', value='enable')
                    action_in_progress = False
                    summary_panel_active = False
                    current_panel = current_rule.reset_rule(window)
                    current_rule = None
                else:
                    continue
            else:  # no action being taken so ok to switch without asking
                toolbar.toggle_menu(window, 'mmenu', 'settings', value='enable')
                print(current_rule, current_panel)
                current_panel = current_rule.reset_rule(window)
                current_rule = None

        # Activate appropriate audit panel
        selected_action = values['-AMENU-']
        if selected_action in audit_names:
            # Obtain the selected rule object
            current_rule = audit_rules.fetch_rule(selected_action)

            current_panel = current_rule.element_key
            window['-HOME-'].update(visible=False)
            window[current_panel].update(visible=True)

            tab_windows = [i.name for i in current_rule.tabs]
            final_index = len(tab_windows) - 1

            # Set up variables for updating date parameter fields
            date_param = current_rule.fetch_parameter('date', by_type=True)
            try:
                date_key = current_rule.key_lookup(date_param.name)
            except AttributeError:
                date_key = None

            date_str = []

            print('Info: the panel in view is {} with tabs {}'.format(current_rule.name, ', '.join(tab_windows)))

        elif selected_action in cash_names:
            # Obtain the selected rule object
            current_rule = cash_rules.fetch_rule(selected_action)

            current_panel = current_rule.element_key
            window['-HOME-'].update(visible=False)
            window[current_panel].update(visible=True)

            print('Info: the panel in view is {}'.format(current_rule.name))

        elif values['-AMENU-'] in bank_names:
            # Obtain the selected rule object
            current_rule = bank_rules.fetch_rule(selected_action)
            pass

        # Format date parameter field, if used in a given rule set
        if current_rule and event == date_key:
            elem_value = values[date_key]
            try:
                input_value = strptime(elem_value, '%Y-%m-%d')
            except ValueError:
                input_value = elem_value.replace('-', '')
            else:
                window[date_key].update(value=input_value.strftime('%Y-%m-%d'))
                continue

            if len(input_value) > 8:  # don't go beyond acceptable size
                date_str_fmt = format_date_element(date_str)
                window[date_key].update(value=date_str_fmt)
                continue

            if input_value and not input_value.isnumeric():
                date_str_fmt = format_date_element(date_str)
                window[date_key].update(value=date_str_fmt)
                continue

            if len(input_value) > len(date_str):  # add character
                date_str.append(input_value[-1])

                date_str_fmt = format_date_element(date_str)
                window[date_key].update(value=date_str_fmt)
            elif len(input_value) < len(date_str):  # remove character
                date_str.pop()

                date_str_fmt = format_date_element(date_str)
                window[date_key].update(value=date_str_fmt)
            else:
                date_str_fmt = format_date_element(date_str)
                window[date_key].update(value=date_str_fmt)

        # Start the selected audit
        try:
            start_key = current_rule.key_lookup('Start')
        except AttributeError:
            start_key = None

        if event == start_key:
            # Check if all rule parameters elements have input
            params = current_rule.parameters
            inputs = []
            for param in params:
                param.set_value(values)
                has_value = param.values_set()

                if not has_value:
                    param_desc = param.description
                    msg = _('Correctly formatted input is required in the "{}" field').format(param_desc)
                    win2.popup_notice(msg)

                inputs.append(has_value)

            # Start Audit
            if all(inputs):  # all rule parameters have input
                # Initialize audit
                initialized = True
                tab_keys = []  # to track tabs displayed
                for tab in current_rule.tabs:
                    tab_key = tab.element_key
                    tab_keys.append(tab_key)

                    # Prepare the filter rules to filter query results
                    main_table = [i for i in tab.db_tables][0]
                    rule_params = current_rule.parameters  # to filter data tables
                    filters = [i.filter_statement(table=main_table) for i in rule_params]

                    # Check for tab-specific query parameters
                    filters += tab.filter_statements()

                    # Extract data from database
                    try:
                        df = user.query(tab.db_tables, columns=tab.db_columns, filter_rules=filters)
                    except Exception as e:
                        win2.popup_error('Error: audit failed due to {}'.format(e))
                        initialized = False
                        break

                    # Update tab object and elements
                    tab.df = df  # update tab data
                    tab.update_id_components(rule_params)
                    tab.update_table(window)  # display tab data in table
                    tab.update_summary(window)  # summarize individual tab data

                    # Enable / disable action buttons
                    tab.toggle_actions(window, 'enable')

                if initialized:
                    action_in_progress = True
                    print('Info: {} audit in progress with parameters {}'
                          .format(current_rule.name, ', '.join(['{}={}'.format(i.name, i.value) for i in params])))

                    # Disable start button and parameter elements
                    start_key = current_rule.key_lookup('Start')
                    window[start_key].update(disabled=True)
                    current_rule.toggle_parameters(window, 'disable')

                    # Disable user ability to modify settings while audit is in progress
                    toolbar.toggle_menu(window, 'mmenu', 'settings', value='disable')
                else:
                    for tab in current_rule.tabs:
                        tab.reset_dynamic_attributes()

        # Scan for missing data if applicable
        if action_in_progress and not summary_panel_active:
            tg_key = current_rule.key_lookup('TG')
            previous_tab = current_tab
            current_tab = window[tg_key].Get()

            # Get current tab in view
            tab = current_rule.fetch_tab(current_tab, by_key=True)

            # Refresh audit table
            if current_tab != previous_tab:
                tab.update_table(window)

            # Remove row from table when row is double-clicked.
            tbl_key = tab.key_lookup('Table')
            if event == tbl_key:
                try:
                    row = values[tbl_key][0]
                except IndexError:  # user double-clicked too quickly
                    continue

                print('Info: removing row {ROW} from table element {TBL}'.format(ROW=row, TBL=tbl_key))

                tab.df.drop(row, axis=0, inplace=True)
                tab.df.reset_index(drop=True, inplace=True)

                tab.update_table(window)
                tab.update_summary(window)
                continue

            # Add row to table based on user input
            add_key = tab.key_lookup('Add')
            if event == add_key:  # clicked the 'Add' button
                input_key = tab.key_lookup('Input')

                # Extract transaction information from database
                new_id = values[input_key]
                all_ids = tab.row_ids()
                if new_id not in all_ids:
                    all_cols = tab.db_columns
                    table = list(tab.db_tables.keys())[0]
                    for table_item in all_cols:
                        try:
                            table_name, column_name = table_item.split('.')
                        except ValueError:
                            continue
                        else:
                            if tab.db_key == column_name:
                                table = table_name
                                break
                    filters = ('{TABLE}.{COLUMN} = ?'.format(TABLE=table, COLUMN=tab.db_key), (new_id,))
                    new_row = user.query(tab.db_tables, columns=tab.db_columns, filter_rules=filters)
                else:
                    msg = _("Warning: {} is already in the table").format(new_id)
                    win2.popup_notice(msg)
                    continue

                if new_row.empty:  # query returned nothing
                    msg = _("Warning: unable to find transaction {}").format(new_id)
                    win2.popup_notice(msg)
                    window[input_key].update(value='')
                    continue

                # Clear user input from the Input element
                window[input_key].update(value='')

                # Append new rows to the table
                df = dm.append_to_table(tab.df, new_row)
                tab.df = df

                # Update display table
                tab.update_table(window)
                tab.update_summary(window)
                continue

            # Run audit
            audit_key = tab.key_lookup('Audit')
            if event == audit_key:
                print('Info: tab in view is {}'.format(tab_windows[current_index]))

                # Run schema action methods
                print('Info: running audit on the {NAME} data'.format(NAME=tab.name))
                params = current_rule.parameters
                tab.run_audit(window, account=user, parameters=params)

                # Update information elements - most actions modify tab data 
                # in some way.
                tab.update_table(window)
                tab.update_summary(window)

            # Enable movement to the next tab
            current_index = tab_keys.index(current_tab)
            next_index = current_index + 1
            if tab.audit_performed and not next_index > final_index:
                next_key = tab_keys[next_index]

                # Enable next tab
                window[next_key].update(disabled=False, visible=True)

            # Enable the finalize button when all actions have been performed
            # on all tabs.
            final_key = current_rule.key_lookup('Finalize')
            summary_key = current_rule.summary.element_key
            if tab.audit_performed and current_index == final_index:
                window[final_key].update(disabled=False)

            if event == final_key:  # display summary panel
                summary_panel_active = True
                rule_summ = current_rule.summary

                # Update summary tables with the current audit's parameter values
                rule_summ.update_title(window, rule)

                # Update summary totals with tab summary totals
                rule_summ.update_totals(rule)

                # update summary elements with mapped tab values
                rule_summ.initialize_tables(rule)

                # Format tables for displaying
                rule_summ.update_display(window)

                # Hide tab panel and un-hide summary panel
                window[current_panel].update(visible=False)
                window[summary_key].update(visible=True)

                # Switch the current panel element key to the summary panel
                current_panel = summary_key

                # Reset tab table column widths
                for tab in current_rule.tabs:
                    tab.resize_elements(window, win_size=window.size)

        # Summary Panel
        if action_in_progress and summary_panel_active:
            # Get current tab in view
            tg_key = current_rule.summary.key_lookup('TG')
            current_tab = window[tg_key].Get()
            summ_tab = current_rule.summary.fetch_tab(current_tab, by_key=True)

            # Add a row to the records table
            add_key = summ_tab.key_lookup('Add')
            if event == add_key:
                rule_summ.update_display(window)

                # Show the add row window to the user
                summ_tab.add_row(rule, win_size=window.size)

                # Update display table
                rule_summ.update_display(window)
                continue

            # Edit row in either the totals or records table
            if event in summ_tbl_keys:
                rule_summ.update_display(window)

                # Find table row selected by user
                try:
                    select_row_index = values[event][0]
                except IndexError:  # user double-clicked too quickly
                    continue

                # Show the modify row window to the user
                summ_tab.edit_row(select_row_index, event, win_size=window.size)

                # Update display table
                rule_summ.update_display(window)
                continue

            # Return to the Audit Panel
            back_key = current_rule.summary.key_lookup('Back')
            if event == back_key:
                summary_panel_active = False

                # Return to tab display
                current_panel = current_rule.element_key
                window[summary_key].update(visible=False)
                window[current_panel].update(visible=True)

                # Reset summary values
                rule_summ.reset_attributes()
                rule_summ.resize_elements(window, win_size=window.size)

                # Switch to first tab
                window[tg_key].Widget.select(0)

            # Save results of the audit
            save_key = current_rule.summary.key_lookup('Save')
            if event == save_key:
                # Save summary to excel or csv file
                title = current_rule.summary.title.replace(' ', '_')
                outfile = sg.popup_get_file('', title='Save As', default_path=title, save_as=True,
                                            default_extension='pdf', no_window=True,
                                            file_types=(('PDF - Portable Document Format', '*.pdf'),))

                if not outfile:
                    continue
                else:
                    print('Info: saving summary report to {}'.format(outfile))

                try:
                    rule_summ.save_report(outfile)
                except Exception as e:
                    msg = _('Save to file {} failed due to {}').format(outfile, e)
                    win2.popup_error(msg)

                # Save summary to the program database
                try:
                    rule_summ.save_to_database(user, current_rule.parameters)
                except Exception as e:
                    msg = _('Save to database failed - {}').format(e)
                    win2.popup_error(msg)
                else:
                    # Reset audit elements
                    toolbar.toggle_menu(window, 'mmenu', 'settings', value='enable')
                    action_in_progress = False
                    summary_panel_active = False
                    rule_summ.reset_attributes()
                    rule_summ.resize_elements(window, win_size=window.size)
                    current_panel = current_rule.reset_rule(window, current=True)

    window.close()


if __name__ == "__main__":
    freeze_support()
    main()
    sys.exit(0)
