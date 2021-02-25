# -*- coding: utf-8 -*-
"""
REM main program. Includes primary display.
"""

__version__ = '2.0.0'

from multiprocessing import freeze_support
import PySimpleGUI as sg
import sys
import tkinter as tk

import REM.audit as audit
import REM.bank as bank
import REM.cash as cash
from REM.config import configuration
import REM.constants as mod_const
import REM.elements as mod_elem
import REM.layouts as mod_lo
import REM.secondary as mod_win2
from REM.settings import user, settings


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
        self.elements = ['-{ELEM}-'.format(ELEM=i) for i in ['amenu', 'rmenu', 'umenu', 'mmenu']]

        record_map = {'account': '&Account Records', 'bank_deposit': 'Bank &Deposit Records',
                      'bank_statement': '&Bank Statement Records', 'audit': 'Audi&t Records',
                      'transaction': '&Transaction Records', 'cash_expense': '&Expense Records'}

        # Accounting method menu items
        acct_menu = []
        for account_method in account_methods:
            acct_menu.append(('', account_method.title))

            rules = []
            for rule in account_method.rules:
                rules.append(('!', rule.menu_title))

            acct_menu.append(rules)

        # Program records menu items
        acct_records = {}
        record_rules = configuration.records.rules
        for record_entry in record_rules:
            record_type = record_entry.group
            record_title = record_entry.menu_title
            try:
                record_group = record_map[record_type]
            except KeyError:
                print('Configuration Error: record type {TYPE} not an accepted program record type'
                      .format(TYPE=record_type))
                continue
            try:
                acct_records[record_group].append(record_title)
            except KeyError:
                acct_records[record_group] = [record_title]

        record_menu = []
        for record_group in acct_records:
            record_menu.append(('', record_group))

            menu_items = acct_records[record_group]
            record_menu.append([('!', i) for i in menu_items])

        self.acct_menu = {'name': '&Validation', 'items': acct_menu}
        self.reports_menu = {'name': '&Records', 'items': record_menu}
        self.user_menu = {'name': '&User',
                          'items': [('!', 'Manage &Users'), ('!', '&Messages'), ('', '---'), ('', 'Sign &In'),
                                    ('!', 'Sign &Out')]}
        self.menu_menu = {'name': '&Menu',
                          'items': [('!', '&Settings'), ('', 'Debu&g'), ('', '---'), ('', '&Help'),
                                    ('', 'Ab&out'), ('', '---'), ('', '&Quit')]}

    def key_lookup(self, element):
        """
        Lookup key for element in schema.
        """
        elements = [i[1:-1] for i in self.elements]

        if element in elements:
            key = '-{ELEM}-'.format(ELEM=element.upper())
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
            width, height = (mod_const.WIN_WIDTH, mod_const.WIN_HEIGHT)

        # Menu items
        menu_audit = self.menu_definition('amenu')
        menu_reports = self.menu_definition('rmenu')
        menu_user = self.menu_definition('umenu')
        menu_menu = self.menu_definition('mmenu')

        # Layout settings
        audit_ico = mod_const.AUDIT_ICON
        report_ico = mod_const.REPORT_ICON
        db_ico = mod_const.DB_ICON
        user_ico = mod_const.USER_ICON
        menu_ico = mod_const.MENU_ICON

        padding = mod_const.TOOLBAR_PAD

        header_col = mod_const.HEADER_COL
        text_col = mod_const.TEXT_COL

        toolbar = [[sg.Canvas(key='-CANVAS_WIDTH-', size=(width, 0), visible=True)],
                   [sg.Col([[sg.ButtonMenu('', menu_audit, key='-AMENU-', image_data=audit_ico, tooltip=_('Run Audits'),
                                           button_color=(text_col, header_col), pad=(padding, padding)),
                             sg.ButtonMenu('', menu_reports, key='-RMENU-', image_data=report_ico,
                                           button_color=(text_col, header_col),
                                           tooltip=configuration.records.title, pad=(padding, padding)),
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

    def disable(self, window, rules):
        """
        Disable toolbar buttons
        """
        menu_groups = {'audit_rules': 'amenu', 'bank_rules': 'amenu', 'cash_rules': 'amenu', 'records': 'rmenu'}

        # Database administration
        window['-DBMENU-'].update(disabled=True)

        # User administration
        self.toggle_menu(window, 'umenu', 'manage accounts', value='disable')

        # Disable settings modification
        self.toggle_menu(window, 'mmenu', 'settings', value='disable')

        # Disable all menu items
        for rule_group in rules:
            for rule in rule_group.rules:
                menu_group = menu_groups[rule_group.name]
                self.toggle_menu(window, menu_group, rule.menu_title, value='disable')

    def enable(self, window, rules):
        """
        Enable toolbar buttons
        """
        admin = user.admin

        menu_groups = {'audit_rules': 'amenu', 'bank_rules': 'amenu', 'cash_rules': 'amenu', 'records': 'rmenu'}

        # Enable admin-only privileges
        if admin is True:
            # Database administration
            window['-DBMENU-'].update(disabled=False)

            # User administration
            self.toggle_menu(window, 'umenu', 'manage accounts', value='enable')

        # Allow user to modify user-settings
        self.toggle_menu(window, 'mmenu', 'settings', value='enable')

        # Enable menu items based on configured permissions
        for rule_group in rules:
            for rule in rule_group.rules:
                if admin is True or rule.permissions in user.access_permissions():
                    menu_group = menu_groups[rule_group.name]
                    self.toggle_menu(window, menu_group, rule.menu_title, value='enable')

    def update_username(self, window, username):
        """
        Update user menu to display username after a user is logged in.
        """
        select_col = mod_const.SELECT_TEXT_COL

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
        width, height = (mod_const.WIN_WIDTH, mod_const.WIN_HEIGHT)

    # Home page action panel
    panels = [mod_lo.home_screen()]

    # Add Audit rule with summary panel
    for account_method in account_methods:
        for rule in account_method.rules:
            print('Info: creating layout for accounting method {ACCT}, rule {RULE}'
                  .format(ACCT=account_method.name, RULE=rule.name))
            panels.append(rule.layout(win_size=win_size))

    # Layout
    pane = [sg.Canvas(size=(0, height), key='-CANVAS_HEIGHT-', visible=True),
            sg.Col([[sg.Pane(panels, key='-PANEWINDOW-', orientation='horizontal', show_handle=False, border_width=0,
                             relief='flat')]], pad=(0, 10), justification='c', element_justification='c')]

    return pane


def resize_elements(window, rules):
    """
    Resize GUI elements when window is resized
    """
    width, height = window.size

    # Update toolbar and pane elements
    window['-CANVAS_HEIGHT-'].set_size((None, height))
    window['-CANVAS_WIDTH-'].set_size((width, None))

    # Update audit rule elements
    for rule in rules:
        try:
            rule.resize_elements(window)
        except Exception as e:
            raise
            print('Error: {}'.format(e))
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
    # Theme
    default_col = mod_const.DEFAULT_COL
    action_col = mod_const.ACTION_COL
    text_col = mod_const.TEXT_COL
    font = mod_const.MAIN_FONT

    sg.set_options(element_padding=(0, 0), margins=(0, 0),
                   auto_size_buttons=True, auto_size_text=True,
                   background_color=default_col, element_text_color=text_col,
                   element_background_color=default_col, font=font,
                   input_text_color=text_col, text_color=text_col,
                   text_element_background_color=default_col,
                   input_elements_background_color=action_col,
                   button_color=(text_col, default_col), tooltip_font=(mod_const.TOOLTIP_FONT))

    # Original window size
    root = tk.Tk()
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    root.destroy()
    del root

    if screen_w >= mod_const.WIN_WIDTH:
        current_w = mod_const.WIN_WIDTH
    else:
        current_w = screen_w

    if screen_h >= mod_const.WIN_HEIGHT:
        current_h = mod_const.WIN_HEIGHT
    else:
        current_h = screen_h

    # Load the program configuration
    audit_rules = audit.AuditRules(configuration)
    cash_rules = cash.CashRules(configuration)
    bank_rules = bank.BankRules(configuration)
    record_rules = configuration.records
    startup_msgs = configuration.startup_msgs

    acct_methods = [audit_rules, bank_rules]
    all_rules = [audit_rules, cash_rules, bank_rules, record_rules]

    # Configure GUI layout
    toolbar = ToolBar([audit_rules, cash_rules, bank_rules])
    layout = [toolbar.layout(win_size=(current_w, current_h)),
              get_panels(acct_methods, win_size=(current_w, current_h))]

    # Element keys and names
    audit_names = audit_rules.print_rules()
    cash_names = cash_rules.print_rules()
    bank_names = bank_rules.print_rules()

    # Event modifiers
    current_rule = None
    debug_win = None

    # Initialize main window and login window
    window = sg.Window('REM Tila', layout, icon=settings.logo, font=mod_const.MAIN_FONT, size=(current_w, current_h),
                       resizable=True, return_keyboard_events=True)
    window.finalize()
    window.maximize()
    print('Info: starting up')

    screen_w, screen_h = window.get_screen_dimensions()
    print('Info: screen size is {W} x {H}'.format(W=screen_w, H=screen_h))

    user_image = tk.PhotoImage(data=mod_const.USER_ICON)
    userin_image = tk.PhotoImage(data=mod_const.USERIN_ICON)

    acct_rules = [i for acct_method in acct_methods for i in acct_method.rules]
    resize_elements(window, acct_rules)
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

                continue

        # Resize screen
        ## Get window dimensions
        win_w, win_h = window.size
        if win_w != current_w or win_h != current_h:
            print('Info: new window size is {W} x {H}'.format(W=win_w, H=win_h))

            # Update sizable elements
            resize_elements(window, acct_rules)

            current_w, current_h = (win_w, win_h)
            resized = True

            continue

        # User login
        if values['-UMENU-'] == 'Sign In':  # user logs on
            print('Info: displaying user login screen')
            mod_win2.login_window()

            if user.logged_in is True:  # logged on successfully
                # Disable sign-in and enable sign-off
                toolbar.toggle_menu(window, 'umenu', 'sign in', value='disable')
                toolbar.toggle_menu(window, 'umenu', 'sign out', value='enable')

                # Switch user icon
                window['-UMENU-'].Widget.configure(image=userin_image)

                # Enable permission specific actions and menus
                toolbar.enable(window, all_rules)

                # Update user menu items to include the login name
                toolbar.update_username(window, user.uid)
            else:
                print('Error: unable to login to the program')

            continue

        # User log-off
        if values['-UMENU-'] == 'Sign Out':  # user signs out
            try:
                in_progress = current_rule.in_progress
            except AttributeError:
                in_progress = False

            # Confirm sign-out
            if in_progress:  # ask to switch first
                msg = 'An audit is ongoing. Are you sure you would like to quit without saving?'
                selection = mod_win2.popup_confirm(msg)

                if selection == 'OK':
                    # Reset to defaults
                    # Remove from the list of used IDs any IDs created during the now cancelled audit
                    for tab in current_rule.summary.tabs:
                        tab.remove_unsaved_keys()

                    # Reset the rule and update the panel
                    current_rule = current_rule.reset_rule(window)
                    current_panel = '-HOME-'
                else:
                    continue
            else:  # no action being taken so ok to switch without asking
                msg = 'Are you sure you would like to sign-out?'
                selection = mod_win2.popup_confirm(msg)

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
            toolbar.disable(window, all_rules)

            continue

        # Display the edit settings window
        if values['-MMENU-'] == 'Settings':
            mod_win2.edit_settings(win_size=window.size)
            continue

        # Display "About" window
        if values['-MMENU-'] == 'About':
            mod_win2.about()
            continue

        # Display the database update window
        if event == '-DBMENU-':
            mod_win2.database_importer_window(win_size=window.get_screen_size())
            continue

        # Display debugger window
        if not debug_win and values['-MMENU-'] == 'Debug':
            debug_win = mod_win2.debugger()
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

        # Pull up an existing database record
        if event == '-RMENU-':
            # Get Record Type selection
            record_type = values['-RMENU-']
            print('Info: displaying selection window for {TYPE} records'.format(TYPE=record_type))

            # Get record entry
            record_entry = configuration.records.fetch_rule(record_type, by_title=True)

            # Import all records of relevant type from the database
            import_df = record_entry.import_records(user)

            # Display the import record window
            table_entry = record_entry.import_table
            table_entry['RecordType'] = record_entry.name
            import_table = mod_elem.TableElement(record_entry.name, table_entry)
            import_table.df = import_table.append(import_df)

            try:
                record = mod_win2.record_import_window(record_entry.record_layout, import_table, enable_new=False)
            except Exception as e:
                msg = 'Record importing failed - {ERR}'.format(ERR=e)
                mod_win2.popup_error(msg)
                print('Error: {}'.format(msg))
                continue
            else:
                if record is None:
                    print('Info: no record selected for importing')
                    continue

            # Open the record display window
            mod_win2.record_window(record)

            continue

        # Activate appropriate panel
        selected_action = values['-AMENU-']
        if selected_action in audit_names:
            # Obtain the selected rule object
            current_rule = audit_rules.fetch_rule(selected_action)

            # Clear the panel
            current_rule.reset_rule(window, current=True)

            # Update panel-in-display
            window[current_panel].update(visible=False)

            current_panel = current_rule.element_key
            window[current_panel].update(visible=True)

            # Disable toolbar
            toolbar.disable(window, all_rules)

            print('Info: panel in view is {NAME}'.format(NAME=current_rule.name))
            continue

        elif selected_action in cash_names:
            # Obtain the selected rule object
            current_rule = cash_rules.fetch_rule(selected_action)

            # Get the record entry
            record_type = current_rule.record_type
            record_entry = configuration.records.fetch_rule(record_type)
            if not record_entry:
                print('Error: unable to find a configured record type with name {NAME}'.format(NAME=record_type))
                continue
            else:
                print('Info: the record type selected is {TYPE}'.format(TYPE=record_type))

            # Import all records of relevant type from the database
            import_df = record_entry.import_records(user)

            # Display the import record window
            table_entry = current_rule.import_table_entry
            table_entry['RecordType'] = record_type
            import_table = mod_elem.TableElement(current_rule.name, table_entry)
            import_table.df = import_table.append(import_df)

            record_layout = current_rule.record_layout_entry
            try:
                record = mod_win2.record_import_window(record_layout, import_table, enable_new=True)
            except Exception as e:
                msg = 'Record importing failed - {ERR}'.format(ERR=e)
                mod_win2.popup_error(msg)
                print('Error: {}'.format(msg))

                raise
                continue
            else:
                if record is None:
                    print('Info: no record selected for importing')
                    continue

            # Open the record in a new window
            mod_win2.record_window(record)

            continue

        elif values['-AMENU-'] in bank_names:
            # Obtain the selected rule object
            current_rule = bank_rules.fetch_rule(selected_action)

            # Clear the panel
            current_rule.reset_rule(window, current=True)

            # Update panel-in-display
            window[current_panel].update(visible=False)

            current_panel = current_rule.element_key
            window[current_panel].update(visible=True)
            window[current_rule.panel_keys[current_rule.current_panel]].update(visible=True)

            # Disable toolbar
            toolbar.disable(window, all_rules)

            print('Info: panel in view is {NAME}'.format(NAME=current_rule.name))
            continue

        # Action events
        if current_rule and event in current_rule.elements:
            print('Info: running window event {EVENT} of rule {RULE}'.format(EVENT=event, RULE=current_rule.name))
            try:
                current_rule_name = current_rule.run_event(window, event, values)
            except Exception as e:
                msg = 'failed to run window event {EVENT} of rule {RULE} - {ERR}'\
                    .format(EVENT=event, RULE=current_rule.name, ERR=e)
                mod_win2.popup_error(msg)
                print('Error: {MSG}'.format(MSG=msg))
                raise

            if current_rule_name is None:
                # Enable toolbar
                toolbar.enable(window, all_rules)

                # Reset current_rule
                current_rule = None
                current_panel = '-HOME-'

            continue

    window.close()


if __name__ == "__main__":
    freeze_support()
    try:
        main()
    except Exception as e:
        raise
        mod_win2.popup_error('Error: fatal program error - {}'.format(e))
        sys.exit(1)
    else:
        sys.exit(0)
