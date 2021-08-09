# -*- coding: utf-8 -*-
"""
REM main program. Includes primary display.
"""

__version__ = '3.5.18'

import sys
import tkinter as tk
from multiprocessing import freeze_support

import PySimpleGUI as sg

import REM.audit as mod_audit
import REM.bank as mod_bank
import REM.cash as mod_cash
import REM.constants as mod_const
import REM.elements as mod_elem
import REM.layouts as mod_lo
import REM.records as mod_records
import REM.secondary as mod_win2
from REM.client import logger, server_conn, settings, user


# Classes
class ToolBar:
    """
    Toolbar object.
    """

    def __init__(self, account_methods, records):
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

            rules = {}
#            rules = []
            for rule in account_method.rules:
#                rules.append(('!', rule.menu_title))
                rule_title = rule.menu_title
                rules[rule.menu_title] = []

#            acct_menu.append(rules)

                # Add any submenus to the menu definition. Submenus act as flags to main workflow rule.
                try:
                    rule_submenu = rule.menu_flags
                except AttributeError:
                    continue

                for submenu in rule_submenu:
                    rules[rule_title].append(submenu)

            rule_menu = []
            for rule in rules:
                rule_menu.append(('!', rule))

                menu_items = rules[rule]
                if not menu_items:
                    continue
                rule_menu.append([('', i) for i in menu_items])

            acct_menu.append(rule_menu)

        # Program records menu items
        acct_records = {}
        record_rules = records.rules
        for record_entry in record_rules:
            record_type = record_entry.group
            record_title = record_entry.menu_title
            try:
                record_group = record_map[record_type]
            except KeyError:
                msg = 'record type {TYPE} not an accepted program record type'.format(TYPE=record_type)
                logger.error(msg)
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
                          'items': [('!', '&Settings'), ('', '&Debug'), ('', '---'), ('', '&Help'),
                                    ('', 'Ab&out'), ('', '---'), ('', '&Quit')]}

        self.records_title = records.title

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
        report_ico = mod_const.ARCHIVE_ICON
        db_ico = mod_const.DB_ICON
        user_ico = mod_const.USER_ICON
        menu_ico = mod_const.MENU_ICON

        padding = mod_const.TOOLBAR_PAD

        header_col = mod_const.HEADER_COL
        text_col = mod_const.TEXT_COL

        toolbar = [[sg.Canvas(key='-CANVAS_WIDTH-', size=(width, 0), visible=True)],
                   [sg.Col([[sg.ButtonMenu('', menu_audit, key='-AMENU-', image_data=audit_ico,
                                           tooltip='Transaction Audits and Finance Reconciliations',
                                           button_color=(text_col, header_col), pad=(padding, padding), border_width=0),
                             sg.ButtonMenu('', menu_reports, key='-RMENU-', image_data=report_ico,
                                           button_color=(text_col, header_col), border_width=0,
                                           tooltip=self.records_title, pad=(padding, padding)),
                             sg.Button('', image_data=db_ico, key='-DBMENU-', tooltip='Record Importing',
                                       button_color=(text_col, header_col), pad=(padding, padding), border_width=0,
                                       disabled=True)]],
                           justification='l', background_color=header_col, expand_x=True),
                    sg.Col([[sg.Canvas(size=(0, 0), visible=True)]],
                           justification='c', background_color=header_col, expand_x=True),
                    sg.Col([[sg.ButtonMenu('', menu_user, key='-UMENU-', pad=(padding, padding), image_data=user_ico,
                                           button_color=(text_col, header_col), border_width=0,
                                           tooltip='User Settings'),
                             sg.ButtonMenu('', menu_menu, key='-MMENU-', pad=(padding, padding), image_data=menu_ico,
                                           button_color=(text_col, header_col), border_width=0,
                                           tooltip='Help and program settings')]],
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
                msg = 'selected menu {} not list of available menus'.format(menu_item)
                logger.error(msg)
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
            msg = 'selected menu {} not list of available menus'.format(menu)
            logger.error(msg)
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
    panels = [mod_lo.home_screen(win_size=(width, height))]

    # Add Audit rule with summary panel
    for account_method in account_methods:
        for rule in account_method.rules:
            msg = 'creating layout for workflow method {ACCT}, rule {RULE}'\
                .format(ACCT=account_method.name, RULE=rule.name)
            logger.debug(msg)
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
            msg = 'failed to resize window - {}'.format(e)
            logger.error(msg)

            continue


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
    logger.debug('determining screen size')
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
    record_rules = mod_records.RecordsConfiguration(settings.record_rules)
    settings.records = record_rules

    audit_rules = mod_audit.AuditRuleController(settings.audit_rules)
    cash_rules = mod_cash.CashRuleController(settings.cash_rules)
    bank_rules = mod_bank.BankRuleController(settings.bank_rules)

    acct_methods = [audit_rules, bank_rules]
    all_rules = [audit_rules, cash_rules, bank_rules, record_rules]

    # Configure GUI layout
    toolbar = ToolBar([audit_rules, cash_rules, bank_rules], record_rules)
    layout = [toolbar.layout(win_size=(current_w, current_h)),
              get_panels(acct_methods, win_size=(current_w, current_h))]

    # Element keys and names
    audit_names = audit_rules.print_rules()
    cash_names = cash_rules.print_rules()
    bank_names = bank_rules.print_rules()

    # Create the menu mapper
    menu_mapper = {}
    for rule in [i for acct_method in (audit_rules, cash_rules, bank_rules) for i in acct_method.rules]:
        try:
            rule_submenu = rule.menu_flags
        except AttributeError:
            menu_mapper[rule.menu_title] = rule.menu_title
        else:
            if not rule_submenu:
                menu_mapper[rule.menu_title] = rule.menu_title
            else:
                for menu_title in rule_submenu:
                    menu_mapper[menu_title] = rule.menu_title

    # Event metadata
    current_rule = None
    debug_win = None

    # Initialize main window and login window
    window = sg.Window('REM Tila (v{VER})'.format(VER=__version__), layout, icon=settings.icon,
                       font=mod_const.MAIN_FONT, size=(current_w, current_h), resizable=True,
                       return_keyboard_events=True)
    window.finalize()
    window.maximize()
    logger.info('starting the program')

    # Bind keyboard events
    window = settings.set_shortcuts(window)

    screen_w, screen_h = window.get_screen_dimensions()
    logger.debug('screen size is {W} x {H}'.format(W=screen_w, H=screen_h))

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
            logger.info('exiting the program')

            if debug_win:
                debug_win.close()
                settings.reload_logger(sys.stdout)

            break

        # Resize screen
        if resized and current_panel != home_panel:
#            if current_rule is not None:
                window[current_rule.panel_keys[current_rule.current_panel]].update(visible=False)
#                window[current_rule.panel_keys[current_rule.first_panel]].update(visible=True)
                window[current_rule.element_key].update(visible=False)
#
                window.refresh()
#
                window[current_rule.element_key].update(visible=True)
#                window[current_rule.panel_keys[current_rule.first_panel]].update(visible=False)
                window[current_rule.panel_keys[current_rule.current_panel]].update(visible=True)
#
                resized = False

                continue

        # Resize screen
        # Get window dimensions
        try:
            win_w, win_h = window.size
        except AttributeError:
            continue

        if win_w != current_w or win_h != current_h:
            logger.debug('new window size is {W} x {H}'.format(W=win_w, H=win_h))

            # Update sizable elements
            resize_elements(window, acct_rules)

            current_w, current_h = (win_w, win_h)
            resized = True

            continue

        # User login
        if values['-UMENU-'] == 'Sign In':  # user logs on
            logger.debug('displaying user login screen')
            mod_win2.login_window()

            if user.logged_in is True:  # logged on successfully
                logger.info('user signed in as "{}"'.format(user.uid))
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
                logger.warning('failed to login to the program as user {}'.format(user.uid))

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

            # Remove all unsaved record IDs associated with the program instance
            settings.remove_unsaved_ids()

            # Reset User attributes
            logger.info('signing out as user {}'.format(user.uid))
            user.logout()

            # Switch user icon
            window['-UMENU-'].Widget.configure(image=user_image)

            # Disable sign-out and enable sign-in
            toolbar.toggle_menu(window, 'umenu', 'sign in', value='enable')
            toolbar.toggle_menu(window, 'umenu', 'sign out', value='disable')

            # Disable all actions and menus
            toolbar.disable(window, all_rules)

            continue

        # Display the debug window
        if not debug_win and values['-MMENU-'] == 'Debug':
            if settings.log_file:
                mod_win2.popup_notice('The debug window is deactivated when logging to a file. Program logs are '
                                      'being sent to {}'.format(settings.log_file))
            else:
                debug_win = mod_win2.debug_window()
                debug_win.finalize()

                # Reload logger with new log stream
                settings.reload_logger(debug_win['-OUTPUT-'].TKOut)
                logger.info('setting log output stream to the debug window')

            continue
        elif debug_win:
            debug_event, debug_value = debug_win.read(timeout=1000)

            if debug_event in (sg.WIN_CLOSED, '-CANCEL-'):
                debug_win.close()
                debug_win = None

                # Reset logging stream to stdout
                logger.info('resetting log output stream to system output')
                settings.reload_logger(sys.stdout)
            elif debug_event == '-CLEAR-':
                debug_win['-OUTPUT-'].update('')
            elif debug_event == '-LEVEL-':
                # Reload logger with new log level
                log_level = debug_value['-LEVEL-']
                logger.info('resetting logging level to {}'.format(log_level))
                settings.reload_logger(debug_win['-OUTPUT-'].TKOut, log_level=log_level)
            else:
                debug_win['-OUTPUT-'].expand(expand_x=True, expand_y=True, expand_row=True)

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
            try:
                mod_win2.database_importer_window(win_size=window.get_screen_size())
            except Exception as e:
                logger.exception('importing records to the database failed - {ERR}'.format(ERR=e))

            continue

        # Pull up an existing database record
        if event == '-RMENU-':
            # Get Record Type selection
            record_type = values['-RMENU-']
            logger.info('displaying selection window for {TYPE} records'.format(TYPE=record_type))

            # Get record entry
            record_entry = settings.records.fetch_rule(record_type, by_title=True)

            # Display the import record window
            table_entry = record_entry.import_table
            table_entry['RecordType'] = record_entry.name
            import_table = mod_elem.TableElement(record_entry.name, table_entry)

            try:
                mod_win2.record_import_window(import_table, enable_new=False)
            except Exception as e:
                msg = 'record importing failed - {ERR}'.format(ERR=e)
                mod_win2.popup_error(msg)
                logger.exception(msg)
#                raise

            continue

        # Activate appropriate accounting workflow method panel
        selected_menu = values['-AMENU-']
        if selected_menu in menu_mapper:
            selected_rule = menu_mapper[selected_menu]

            if selected_rule in audit_names:  # workflow method is a transaction audit
                # Obtain the selected rule object
                current_rule = audit_rules.fetch_rule(selected_rule)

                # Clear the panel
                current_rule.reset_rule(window, current=True)

                # Update panel-in-display
                window[current_panel].update(visible=False)

                current_panel = current_rule.element_key
                window[current_panel].update(visible=True)
                logger.debug('panel in view is {NAME}'.format(NAME=current_rule.name))

                # Disable the toolbar
                toolbar.disable(window, all_rules)

                continue

            elif selected_rule in cash_names:  # workflow method is cash reconciliation
                # Obtain the selected rule object
                current_rule = cash_rules.fetch_rule(selected_rule)

                # Get the record entry
                record_type = current_rule.record_type
                record_entry = settings.records.fetch_rule(record_type)
                if not record_entry:
                    msg = 'unable to find a configured record type with name {NAME}'.format(NAME=record_type)
                    logger.warning(msg)
                    continue
                else:
                    logger.debug('the record type selected is {TYPE}'.format(TYPE=record_type))

                # Display the import record window
                table_entry = current_rule.import_table_entry
                table_entry['RecordType'] = record_type
                import_table = mod_elem.TableElement(current_rule.name, table_entry)

                try:
                    mod_win2.record_import_window(import_table, enable_new=True,
                                                  record_layout=current_rule.record_layout_entry)
                except Exception as e:
                    msg = 'record importing failed - {ERR}'.format(ERR=e)
                    mod_win2.popup_error(msg)
                    logger.exception(msg)

                continue

#            elif selected_rule in bank_names:  # workflow method is bank reconciliation
#                # Obtain the selected rule object
#                current_rule = bank_rules.fetch_rule(selected_rule)
#
#                # Use the menu flag to find the primary account
#                try:
#                    acct_name = current_rule.menu_flags[selected_menu]
#                except KeyError:
#                    acct_name = selected_rule.name
#
#                # Fetch the primary account
#                current_acct = current_rule.fetch_account(acct_name)
#                current_rule.current_account = current_acct
#                current_rule.current_panel = current_acct.key_lookup('Panel')
#
#                # Update the display title
#                panel_title_key = current_rule.key_lookup('Title')
#                window[panel_title_key].update(value=current_acct.title)
#
#                # Update the panel-in-display and the account panel
#                window[current_panel].update(visible=False)
#
#                current_panel = current_rule.element_key
#                window[current_panel].update(visible=True)
#                window[current_rule.current_panel].update(visible=True)
#
#                # Disable toolbar
#                toolbar.disable(window, all_rules)
#
#                logger.debug('panel in view is {NAME}'.format(NAME=current_rule.name))
#                continue

            elif selected_rule in bank_names:  # workflow method is bank reconciliation
                # Obtain the selected rule object
                current_rule = bank_rules.fetch_rule(selected_rule)

                # Clear the panel
                current_rule.reset_rule(window, current=True)

                # Update panel-in-display
                window[current_panel].update(visible=False)

                current_panel = current_rule.element_key
                window[current_panel].update(visible=True)
                window[current_rule.panel_keys[current_rule.current_panel]].update(visible=True)

                # Collapse the filter frame of the first tab
                tg_key = current_rule.key_lookup('MainTG')
                logger.debug('collapsing the filter frame of the first tab with key {}'.format(tg_key))
                tab_key = window[tg_key].Get()
                tab = current_rule.fetch_tab(tab_key, by_key=True)
                filter_key = tab.table.key_lookup('FilterFrame')
                if window[filter_key].metadata['visible'] is True:
                    tab.table.collapse_expand(window, frame='filter')

                # Disable toolbar
                toolbar.disable(window, all_rules)

                logger.debug('panel in view is {NAME}'.format(NAME=current_rule.name))
                continue

        # Action events
        if current_rule and (event in current_rule.elements or event in settings.hotkeys):
            logger.info('running window event {EVENT} of rule {RULE}'.format(EVENT=event, RULE=current_rule.name))
            try:
                current_rule_name = current_rule.run_event(window, event, values)
            except Exception as e:
                msg = 'failed to run window event {EVENT} of rule {RULE} - {ERR}'\
                    .format(EVENT=event, RULE=current_rule.name, ERR=e)
                mod_win2.popup_error(msg)
                logger.exception(msg)

                continue

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
        logger.exception('fatal program error')
        mod_win2.popup_error('fatal program error - {}'.format(e))

        # Remove all unsaved record IDs associated with the program instance
        settings.remove_unsaved_ids()

        # Close the connection to the server
        server_conn.close()

        # Exit gracefully
        sys.exit(1)
    else:
        # Remove all unsaved record IDs associated with the program instance
        settings.remove_unsaved_ids()

        # Close the connection to the server
        server_conn.close()

        # Exit gracefully
        sys.exit(0)
