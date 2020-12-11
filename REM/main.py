# -*- coding: utf-8 -*-
"""
REM main program. Includes primary display.
"""

__version__ = '1.1.2'

import datetime
from multiprocessing import freeze_support
import PySimpleGUI as sg
import REM.audit as audit
import REM.bank as bank
import REM.cash as cash
import REM.data_manipulation as dm
from REM.config import configuration, current_tbl_pkeys, settings
import REM.layouts as lo
import REM.records as mod_records
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
        self.name = 'toolbar'
        self.elements = ['amenu', 'rmenu', 'umenu', 'mmenu']

        acct_menu = []
        for account_method in account_methods:
            acct_menu.append(('', account_method.title))

            rules = []
            for rule in account_method.rules:
                rules.append(('!', rule.title))

            acct_menu.append(rules)

        acct_records = []
        record_rules = configuration.db_records['rules']
        for record_group in record_rules:
            acct_records.append(('', record_group))

            record_entries = []
            for record_type in record_rules[record_group]:
                record_entry = record_rules[record_group][record_type]

                try:
                    record_title = record_entry['Title']
                except KeyError:
                    record_title = record_type

                record_entries.append(('!', '{ITEM}::{KEY}'.format(ITEM=record_title, KEY=record_type)))

            acct_records.append(record_entries)

        self.acct_menu = {'name': '&Audits', 'items': acct_menu}
        self.reports_menu = {'name': 'Records',
                             'items': [('!', 'S&tatistics'), ('', '&Records'), acct_records]}
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

        toolbar = [[sg.Canvas(key='-CANVAS_WIDTH-', size=(width, 0), visible=True)],
                   [sg.Col([[sg.ButtonMenu('', menu_audit, key='-AMENU-', image_data=audit_ico, tooltip=_('Run Audits'),
                                           button_color=(text_col, header_col), pad=(padding, padding)),
                             sg.ButtonMenu('', menu_reports, key='-RMENU-', image_data=report_ico,
                                           button_color=(text_col, header_col),
                                           tooltip=_('Generate Record Reports & Statistics'), pad=(padding, padding)),
                             sg.Button('', image_data=db_ico, key='-DBMENU-', tooltip=_('Modify Database'),
                                       button_color=(text_col, header_col), pad=(padding, padding), border_width=0,
                                       disabled=True)]],
                           justification='l', background_color=header_col, expand_x=True),
                    sg.Col([[sg.Canvas(size=(0, 0), visible=True)]],
                           justification='c', background_color=header_col, expand_x=True),
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
                    if isinstance(sub_item, tuple):
                        sub_list.append('{}{}'.format(*sub_item))
                    elif isinstance(sub_item, list):
                        sub_sub_list = []
                        for sub_sub_item in sub_item:
                            sub_sub_list.append('{}{}'.format(*sub_sub_item))
                        sub_list.append(sub_sub_list)
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
                    if isinstance(sub_item, tuple):
                        clean_item = sub_item[1].replace('&', '')
                        if menu_item in (clean_item, clean_item.lower()):
                            item_name = sub_item[1]

                            # Replace menu item with updated status
                            sub_menu.append((status, item_name))
                        else:
                            sub_menu.append(sub_item)
                    elif isinstance(sub_item, list):
                        sub_sub_menu = []
                        for sub_sub_item in sub_item:
                            clean_item = sub_sub_item[1].replace('&', '')
                            if menu_item in (clean_item, clean_item.lower()):
                                item_name = sub_sub_item[1]

                                # Replace menu item with updated status
                                sub_sub_menu.append((status, item_name))
                            else:
                                sub_sub_menu.append(sub_sub_item)

                        sub_menu.append(sub_sub_menu)

                new_menu.append(sub_menu)

        # Replace menu item with updated status
        select_menu['items'] = new_menu
        name = select_menu['name']

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
    panels = [lo.home_screen()]

    # Add Audit rule with summary panel
    for account_method in account_methods:
        for rule in account_method.rules:
            panels.append(rule.layout(win_size=win_size))

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
    window['-CANVAS_HEIGHT-'].set_size((None, height))
    window['-CANVAS_WIDTH-'].set_size((width, None))

    # Update audit rule elements
    for rule in rules:
        rule.resize_elements(window, win_size=win_size)


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
                   button_color=(text_col, default_col), tooltip_font=(const.TOOLTIP_FONT))

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
    audit_rules = audit.AuditRules(configuration)
    cash_rules = cash.CashRules(configuration)
    bank_rules = bank.BankRules(configuration)
    startup_msgs = configuration.startup_msgs

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

    record_rules = configuration.db_records['rules']

    summ_tbl_keys = []
    for rule in audit_rules.rules:
        for tab in rule.summary.tabs:
            summ_tbl_keys.append(tab.key_lookup('Table'))
            summ_tbl_keys.append(tab.key_lookup('Totals'))

    date_key = None

    print('Info: current audit rules are {}'.format(', '.join(audit_names)))

    # Event modifiers
    audit_in_progress = False
    cr_in_progress = False
    br_in_progress = False
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
            if current_rule is not None:
                window[current_rule.panel_keys[current_rule.current_panel]].update(visible=False)
                window[current_rule.panel_keys[current_rule.first_panel]].update(visible=True)
                window[current_rule.element_key].update(visible=False)

                window.refresh()

                window[current_rule.element_key].update(visible=True)
                window[current_rule.panel_keys[current_rule.first_panel]].update(visible=False)
                window[current_rule.panel_keys[current_rule.current_panel]].update(visible=True)

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
                if admin is True:
                    # Database administration
                    window['-DBMENU-'].update(disabled=False)

                    # Reports and statistics
                    toolbar.toggle_menu(window, 'rmenu', 'summary statistics', value='enable')

                    # User
                    toolbar.toggle_menu(window, 'umenu', 'manage accounts', value='enable')

                    # Menu
                    toolbar.toggle_menu(window, 'mmenu', 'settings', value='enable')

                # Enable accounting rules permissions on per rule basis defined in config
                for acct_method in acct_methods:
                    for acct_rule in acct_method.rules:
                        rule_name = acct_rule.title
                        if admin:
                            toolbar.toggle_menu(window, 'amenu', rule_name, value='enable')
                        else:
                            perms = acct_rule.permissions
                            if perms != 'admin':  # permissions allow non-administrator access
                                toolbar.toggle_menu(window, 'amenu', rule_name, value='enable')

                # Enable record view permissions on per rule basis defined in config
                for record_group in record_rules:
                    for record_type in record_rules[record_group]:
                        record_entry = record_rules[record_group][record_type]

                        try:
                            record_title = record_entry['Title']
                        except KeyError:
                            record_title = record_type

                        record_name = '{ITEM}::{KEY}'.format(ITEM=record_title, KEY=record_type)

                        if admin:
                            toolbar.toggle_menu(window, 'rmenu', record_name, value='enable')
                        else:
                            try:
                                perms = record_entry['Permissions']
                            except KeyError:
                                try:
                                    record_viewable = bool(int(perms['View']))
                                except (KeyError, ValueError):
                                    continue

                                if record_viewable is True:
                                    toolbar.toggle_menu(window, 'rmenu', record_name, value='enable')

                # Update user menu items to include the login name
                toolbar.update_username(window, user.uid)
            else:
                print('Error: unable to login to the program')
                continue

        # User log-off
        if values['-UMENU-'] == 'Sign Out':  # user signs out
            # Confirm sign-out
            if audit_in_progress:  # ask to switch first
                msg = _('An audit is ongoing. Are you sure you would like to quit without saving?')
                selection = win2.popup_confirm(msg)

                if selection == 'OK':
                    # Reset to defaults
                    audit_in_progress = False
                    summary_panel_active = False
                    # Remove from the list of used IDs any IDs created during the now cancelled audit
                    for tab in current_rule.summary.tabs:
                        tab.remove_unsaved_keys()

                    # Reset the rule and update the panel
                    current_panel = current_rule.reset_rule(window)
                    current_rule = None
                else:
                    continue
            elif cr_in_progress:  # ask to switch first
                msg = _('Are you sure you would like to quit without saving the transaction?')
                selection = win2.popup_confirm(msg)

                if selection == 'OK':
                    # Reset to defaults
                    cr_in_progress = False

                    # Remove from list of used IDs any IDs created/deleted during the now cancelled reconciliation
                    current_rule.remove_unsaved_keys()

                    # Reset rule and update the panel
                    current_panel = current_rule.reset_rule(window)
                    current_rule = None
                else:
                    continue
            else:  # no action being taken so ok to switch without asking
                msg = _('Are you sure you would like to sign-out?')
                selection = win2.popup_confirm(msg)

                if selection == 'Cancel':
                    continue

                try:
                    current_rule.reset_parameters(window)
                    window[current_rule.element_key].update(visible=False)
                except AttributeError:
                    pass

                window['-HOME-'].update(visible=True)

                current_panel = '-HOME-'

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

            # Reports
            for record_group in record_rules:
                for record_type in record_rules[record_group]:
                    record_entry = record_rules[record_group][record_type]

                    try:
                        record_title = record_entry['Title']
                    except KeyError:
                        record_title = record_type

                    record_name = '{ITEM}::{KEY}'.format(ITEM=record_title, KEY=record_type)
                    toolbar.toggle_menu(window, 'rmenu', record_name, value='disable')

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

        # Pull up record
        if event == '-RMENU-':
            record_name = values['-RMENU-']
            print('Info: pulling up report selection for {}'.format(record_name))
            # Get record entry
            record_title, record_id = record_name.split('::')
            for record_group in record_rules:
                for record_type in record_rules[record_group]:
                    if record_type == record_id:
                        record_entry = record_rules[record_group][record_type]

                        # Obtain the record information
                        try:
                            record_class = record_entry['Type']
                        except KeyError:
                            win2.popup_error('Configuration Error: {RULE}, {NAME}: missing required parameter "Type"'
                                             .format(RULE=record_group, NAME=record_type))
                            break

                        if record_class == 'account_record':
                            db_record = mod_records.load_account_record(user, record_group, record_type, record_entry)
                            if db_record is None:
                                break

                            # Display the account record window
                            user_action = win2.account_record_window(db_record)
                        elif record_class == 'audit_record':
                            #db_record = mod_records.load_audit_record(user, record_group, record_type, record_entry)

                            # Display the audit record window
                            #user_action = win2.audit_record_window(db_record)
                            pass
                        else:
                            win2.popup_error('Configuration Warning: {RULE}, {NAME}: cannot find a class for {TYPE}'
                                             .format(RULE=record_group, NAME=record_type, TYPE=record_type))
                            break

                        if user_action == 'save':
                            db_record.save_to_database(user)
                        elif user_action == 'delete':
                            db_record.delete_record(user)
                        else:
                            continue

            continue

        # Switch to new panel
        if current_panel != '-HOME-' and (event in cancel_keys or values['-AMENU-'] or values['-RMENU-']):
            if audit_in_progress:  # ask to switch first
                msg = _('An audit is ongoing. Are you sure you would like to quit without saving?')
                selection = win2.popup_confirm(msg)

                if selection == 'OK':
                    # Reset to defaults
                    toolbar.toggle_menu(window, 'mmenu', 'settings', value='enable')
                    audit_in_progress = False
                    summary_panel_active = False
                    # Remove from the list of used IDs any IDs created during the now cancelled audit
                    for tab in current_rule.summary.tabs:
                        tab.remove_unsaved_keys()

                    # Reset the rule and update the panel
                    remain_in_panel = True if not values['-AMENU-'] else False
                    if remain_in_panel is True:
                        current_panel = current_rule.reset_rule(window, current=True)
                    else:
                        current_panel = current_rule.reset_rule(window, current=False)
                    current_rule = current_rule if not values['-AMENU-'] else values['-AMENU-']
                else:
                    continue
            elif cr_in_progress:  # ask to switch first
                msg = _('Are you sure you would like to quit without saving the transaction?')
                selection = win2.popup_confirm(msg)

                if selection == 'OK':
                    # Reset to defaults
                    toolbar.toggle_menu(window, 'mmenu', 'settings', value='enable')
                    cr_in_progress = False

                    # Remove from list of used IDs any IDs created/deleted during the now cancelled reconciliation
                    current_rule.remove_unsaved_keys()

                    # Reset rule and update the panel
                    current_panel = current_rule.reset_rule(window)
                    current_rule = None if not values['-AMENU-'] else values['-AMENU-']
                else:
                    continue
            else:  # no action being taken so ok to switch without asking
                toolbar.toggle_menu(window, 'mmenu', 'settings', value='enable')
                current_rule.reset_parameters(window)

                window[current_rule.element_key].update(visible=False)
                window['-HOME-'].update(visible=True)

                current_rule = None if not values['-AMENU-'] else values['-AMENU-']
                current_panel = '-HOME-'

            window.refresh()

        # Activate appropriate audit panel
        selected_action = values['-AMENU-']
        if selected_action in audit_names:
            # Obtain the selected rule object
            current_rule = audit_rules.fetch_rule(selected_action)

            window[current_panel].update(visible=False)

            current_panel = current_rule.element_key
            window[current_panel].update(visible=True)
            window[current_rule.panel_keys[current_rule.current_panel]].update(visible=True)

            tab_windows = [i.name for i in current_rule.tabs]
            final_index = len(tab_windows) - 1

            # Set up variables for updating date parameter fields
            date_param = current_rule.fetch_parameter('date', by_type=True)
            try:
                date_key = date_param.element_key
            except AttributeError:
                date_key = None

            date_str = []

            current_panel = current_rule.element_key

            print('Info: the panel in view is {} with tabs {}'.format(current_rule.name, ', '.join(tab_windows)))
            continue

        elif selected_action in cash_names:
            # Obtain the selected rule object
            current_rule = cash_rules.fetch_rule(selected_action)

            import_panel = current_rule.load_from_database(user)
            if import_panel == '-HOME-':
                current_rule = None
                window[import_panel].update(visible=True)
                continue

            # Update transaction ID field with the transaction number
            id_param = current_rule.fetch_parameter(current_rule.required_parameters['ID'])
            elem_size = len(id_param.value) + 1

            id_key = id_param.element_key
            window[id_key].set_size((elem_size, None))
            window[id_key].update(value=id_param.value)

            # Update parameter elements
            for param in current_rule.parameters:
                if param.hidden is True:
                    continue
                param_key = param.element_key
                param_value = param.value
                window[param_key].update(value=param_value)

            current_rule.update_display(window)

            window[current_panel].update(visible=False)
            window[import_panel].update(visible=True)

            # Query records database for any audit records unassociated with a transaction
            ref_table = current_rule.records.table
            ref_columns = list(current_rule.records.columns.keys())
            filters = ('{COL} IS NULL'.format(COL=current_rule.records.refkey), None)
            import_df = user.query(ref_table, ref_columns, filter_rules=filters, prog_db=True)

            current_rule.records.unassociated_df = current_rule.records.set_datatypes(import_df)

            # Set up variables for updating date parameter fields
            date_param = current_rule.fetch_parameter('date', by_type=True)
            try:
                date_key = date_param.element_key
            except AttributeError:
                date_key = None

            date_str = []

            current_panel = import_panel
            cr_in_progress = True
            print('Info: the panel in view is {}'.format(current_rule.name))

            continue

        elif values['-AMENU-'] in bank_names:
            # Obtain the selected rule object
            current_rule = bank_rules.fetch_rule(selected_action)
            pass

        # Format date parameter field, if used in a given rule set
        if current_rule and event == date_key:
            elem_value = values[event]
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

        # Audit Rules
        # Start the audit
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
                # Verify that the audit has not already been performed with these parameters
                audit_exists = current_rule.summary.load_from_database(user, current_rule.parameters)
                if audit_exists is True:
                    continue_audit = win2.popup_confirm('An audit has already been performed using these parameters. '
                                                        'Only an admin may edit an existing audit. Are you sure you '
                                                        'would like to continue?')
                    if continue_audit == 'Cancel':
                        continue

                # Initialize audit
                initialized = True
                tab_keys = []  # to track tabs displayed
                for tab in current_rule.tabs:
                    tab_key = tab.element_key
                    tab_keys.append(tab_key)

                    # Prepare the filter rules to filter query results
                    main_table = [i for i in tab.import_rules][0]
                    rule_params = current_rule.parameters  # to filter data tables
                    filters = [i.filter_statement(table=main_table) for i in rule_params]

                    # Check for tab-specific query parameters
                    filters += tab.filter_statements()
                    print(filters)

                    # Extract data from database
                    try:
                        df = user.query(tab.import_rules, columns=tab.db_columns, filter_rules=filters)
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
                    audit_in_progress = True
                    print('Info: {} audit in progress with parameters {}'
                          .format(current_rule.name, ', '.join(['{}={}'.format(i.name, i.value) for i in params])))

                    # Enable/Disable control buttons and parameter elements
                    window[current_rule.key_lookup('Start')].update(disabled=True)

                    current_rule.toggle_parameters(window, 'disable')

                    # Disable user ability to modify settings while audit is in progress
                    toolbar.toggle_menu(window, 'mmenu', 'settings', value='disable')
                else:
                    for tab in current_rule.tabs:
                        tab.reset_dynamic_attributes()

        # Scan for missing data if applicable
        if audit_in_progress and not summary_panel_active:
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
            if event == tab.key_lookup('Add'):  # clicked the 'Add' button
                input_key = tab.key_lookup('Input')

                # Extract transaction information from database
                new_id = values[input_key]
                all_ids = tab.row_ids()
                if new_id not in all_ids:
                    all_cols = tab.db_columns
                    table = list(tab.import_rules.keys())[0]
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
                    new_row = user.query(tab.import_rules, columns=tab.db_columns, filter_rules=filters)
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
            if tab.audit_performed and current_index == final_index:
                window[current_rule.key_lookup('Next')].update(disabled=False)

            if event == current_rule.key_lookup('Next'):  # display summary panel
                next_subpanel = current_rule.current_panel + 1

                summary_panel_active = True
                rule_summ = current_rule.summary

                # Update summary table title with the current audit's parameter values
                rule_summ.update_static_fields(window, current_rule)

                # Update summary totals with tab summary totals
                rule_summ.update_totals(current_rule)

                # Update summary elements with mapped tab values
                rule_summ.initialize_tables(current_rule)

                # Format tables for displaying
                window.refresh()
                rule_summ.update_display(window)

                # Hide tab panel and un-hide summary panel
                window[current_rule.panel_keys[current_rule.current_panel]].update(visible=False)
                window[current_rule.panel_keys[next_subpanel]].update(visible=True)

                # Switch the current panel element key to the summary panel
                current_rule.current_panel = next_subpanel

                if next_subpanel == current_rule.last_panel:
                    window[current_rule.key_lookup('Next')].update(disabled=True)
                    window[current_rule.key_lookup('Back')].update(disabled=False)
                    window[current_rule.key_lookup('Save')].update(disabled=False)

                # Reset tab table column widths
                for tab in current_rule.tabs:
                    tab.resize_elements(window, win_size=window.size)

        # Audit summary panel
        if audit_in_progress and summary_panel_active:
            # Get current tab in view
            tg_key = current_rule.summary.key_lookup('TG')
            current_tab = window[tg_key].Get()
            summ_tab = current_rule.summary.fetch_tab(current_tab, by_key=True)

            # Add a row to the records table
            if event == summ_tab.key_lookup('Add'):
                rule_summ.update_display(window)

                # Show the add row window to the user
                summ_tab.add_row(win_size=window.size)

                # Update display table
                rule_summ.update_display(window)
                continue

            # Remove a row from the records table
            if event == summ_tab.key_lookup('Delete'):
                # Get selected row
                tbl_index = values[summ_tab.key_lookup('Table')]
                print('Info: rule {RULE}, summary {NAME}: the rows {IND} have been selected for removal'
                      .format(RULE=summ_tab.rule_name, NAME=summ_tab.name, IND=tbl_index))

                summ_tab.remove_row(tbl_index)
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
            if event == current_rule.key_lookup('Back'):
                summary_panel_active = False
                prev_subpanel = current_rule.current_panel - 1

                # Return to tab display
                window[current_rule.panel_keys[current_rule.current_panel]].update(visible=False)
                window[current_rule.panel_keys[prev_subpanel]].update(visible=True)

                window[current_rule.key_lookup('Next')].update(disabled=False)
                window[current_rule.key_lookup('Back')].update(disabled=True)

                # Reset summary values
                for tab in rule_summ.tabs:
                    tab.remove_unsaved_keys()
                    tab.reset_tables()

                rule_summ.resize_elements(window, win_size=window.size)

                # Switch to first tab
                window[tg_key].Widget.select(0)

                current_rule.current_panel = prev_subpanel

                if prev_subpanel == current_rule.first_panel:
                    window[current_rule.key_lookup('Next')].update(disabled=False)
                    window[current_rule.key_lookup('Back')].update(disabled=True)
                    window[current_rule.key_lookup('Save')].update(disabled=True)

            # Add note to current summary panel
            if event == summ_tab.key_lookup('Note'):
                # Display notes window
                for id_field in summ_tab.ids:
                    id_param = summ_tab.ids[id_field]
                    if id_param['IsPrimary'] is True:
                        tab_title = id_param['Title']
                        break

                notes_title = summ_tab.notes['Title']
                note_text = win2.notes_window(summ_tab.id, summ_tab.notes['Value'], record=tab_title,
                                              title=notes_title).strip()
                summ_tab.notes['Value'] = note_text

                # Change edit note button to be highlighted if note field not empty
                if note_text:
                    window[event].update(image_data=const.EDIT_ICON)
                else:
                    window[event].update(image_data=const.NOTES_ICON)

            # Save results of the audit
            if event == current_rule.key_lookup('Save'):
                # Get output file from user
                title = current_rule.summary.title.replace(' ', '_')
                outfile = sg.popup_get_file('', title='Save As', default_path=title, save_as=True,
                                            default_extension='pdf', no_window=True,
                                            file_types=(('PDF - Portable Document Format', '*.pdf'),))

                if not outfile:
                    msg = _('Please select an output file before continuing')
                    win2.popup_error(msg)
                    continue
                else:
                    print('Info: saving summary report to {}'.format(outfile))

                # Save summary to the program database
                try:
                    save_status = rule_summ.save_to_database(user)
                except Exception as e:
                    raise
                    msg = _('Database save failed - {}').format(e)
                    win2.popup_error(msg)
                else:
                    if save_status is False:
                        msg = _('Database save failed.')
                        win2.popup_error(msg)
                        continue

                # Save summary to excel or csv file
                try:
                    rule_summ.save_report(outfile)
                except Exception as e:
                    print(e)
                    msg = _('Save to file {} failed due to {}').format(outfile, e)
                    win2.popup_error(msg)

                # Reset audit elements
                toolbar.toggle_menu(window, 'mmenu', 'settings', value='enable')
                audit_in_progress = False
                summary_panel_active = False
                rule_summ.reset_attributes()
                rule_summ.resize_elements(window, win_size=window.size)
                current_panel = current_rule.reset_rule(window, current=True)

        # Cash Rules
        if cr_in_progress:
            # Add records to bank transaction
            if event == current_rule.key_lookup('AddEntry'):
                # Display window for adding records
                current_rule.records.add_row()
                current_rule.update_display(window)

                continue

            # Add an expense to the bank transaction
            if event == current_rule.key_lookup('AddExpense'):
                current_rule.expenses.add_row()
                current_rule.update_display(window)

                continue

            # Remove a record from the bank transaction
            if event == current_rule.key_lookup('RemoveEntry'):
                # Get selected row
                tbl_index = values[current_rule.key_lookup('EntryTable')]
                print('Info: rule {RULE}, Records: the rows {IND} have been selected for removal'
                      .format(RULE=current_rule.name, IND=tbl_index))

                current_rule.records.remove_row(tbl_index)
                current_rule.update_display(window)

                continue

            # Remove an expense from the bank transaction
            if event == current_rule.key_lookup('RemoveExpense'):
                # Get selected row
                tbl_index = values[current_rule.key_lookup('ExpenseTable')]
                print('Info: rule {RULE}, Expenses: the rows {IND} have been selected for removal'
                      .format(RULE=current_rule.name, IND=tbl_index))

                current_rule.expenses.remove_row(tbl_index)
                current_rule.update_display(window)

                continue

            # Edit an expense
            if event == current_rule.key_lookup('ExpenseTable'):
                # Get selected row
                tbl_index = values[current_rule.key_lookup('ExpenseTable')][0]
                print('Info: row {} selected for editing'.format(tbl_index))

                current_rule.expenses.edit_row(tbl_index)
                current_rule.update_display(window)

                continue

            # Save bank transaction to database
            if event == current_rule.key_lookup('Save'):
                # Set parameter values
                all_params = True
                for param in current_rule.parameters:
                    if param.hidden is True:
                        continue

                    param.set_value(values)
                    print(param.name, param.value)
                    print(values)
                    has_value = param.values_set()

                    if has_value is False:
                        param_desc = param.description
                        msg = _('Correctly formatted input is required in the "{}" field').format(param_desc)
                        win2.popup_notice(msg)

                        all_params = False
                        break

                if all_params is not True:
                    continue

                save_status = current_rule.save_to_database(user)
                if save_status is False:
                    msg = _('Database save failed.')
                    win2.popup_error(msg)
                    continue

                cr_in_progress = False
                summary_panel_active = False
                current_panel = current_rule.reset_rule(window, current=False)

    window.close()


if __name__ == "__main__":
    freeze_support()
    main()
    sys.exit(0)
