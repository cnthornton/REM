# -*- coding: utf-8 -*-
"""
REM main program. Includes primary display.
"""

__version__ = '3.7.0'

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
class ConfigurationManager:
    """
    Class to store and manage configuration documents.

    Attributes:

        name (str): name of the configuration document.

        title (str): toolbar menu display name.

        rules (list): list of major program objects defined by the configuration.
    """

    def __init__(self, document):
        """
        Configuration manager.

        Arguments:

            document (dict): configuration document.
        """

        doc_id = document["_id"]

        self.rules = []
        if document is not None:
            try:
                rule_name = document['name']
            except KeyError:
                msg = 'configuration document {ID} is missing required field "name"'.format(ID=doc_id)
                logger.error('ConfigurationManager: {MSG}'.format(MSG=msg))
                mod_win2.popup_error('Configuration Error: {MSG}'.format(MSG=msg))

                raise AttributeError(msg)
            else:
                self.name = rule_name

            try:
                self.title = document['title']
            except KeyError:
                self.title = rule_name

            try:
                rules = document['rules']
            except KeyError:
                msg = '{TYPE} configuration is missing required field "rules"'.format(TYPE=self.name)
                logger.error('ConfigurationManager: {MSG}'.format(MSG=msg))
                mod_win2.popup_error('Configuration Error: {MSG}'.format(MSG=msg))

                raise AttributeError(msg)

            if rule_name == 'records':
                manager = mod_records.RecordEntry
            elif rule_name == 'audit_rules':
                manager = mod_audit.AuditRule
            elif rule_name == 'bank_rules':
                manager = mod_bank.BankRule
            elif rule_name == 'cash_rules':
                manager = mod_cash.CashRule
            else:
                msg = 'unknown document type {TYPE} provided'.format(TYPE=self.name)
                logger.error('ConfigurationManager: {MSG}'.format(MSG=msg))
                mod_win2.popup_error('Configuration Error: {MSG}'.format(MSG=msg))

                raise AttributeError(msg)

            for rule_name in rules:
                rule = rules[rule_name]

                self.rules.append(manager(rule_name, rule))

    def print_rules(self, by_title: bool = False):
        """
        Print rules of the rule set by either its name (default) or title.

        Arguments:
            by_title (bool): print the rules managed by the configuration manager by their title instead of their
              name [Default: False]
        """
        if by_title is True:
            rule_names = [i.menu_title for i in self.rules]
        else:
            rule_names = [i.name for i in self.rules]

        return rule_names

    def fetch_rule(self, rule, by_title: bool = False):
        """
        Fetch a given rule from the rule set by its name (default) or title.

        Arguments:
            by_title (bool): fetch a rule managed by the configuration manager by title instead of name [Default: False]
        """
        if by_title is True:
            rule_names = [i.menu_title for i in self.rules]
        else:
            rule_names = [i.name for i in self.rules]

        try:
            index = rule_names.index(rule)
        except ValueError:
            logger.warning('record entry {NAME} not in Records configuration. Available record entries are {ALL}'
                           .format(NAME=rule, ALL=', '.join(rule_names)))
            rule = None
        else:
            rule = self.rules[index]

        return rule


class ToolBar:
    """
    Program toolbar.

    Attributes:
        name (str): object name.

        elements (list): list of GUI element keys.

        account_items (dict): account menu items with their access permissions.

        record_items (dict): record menu items with their access permissions.

        acct_menu (dict): menu definition for the accounting method menu button.

        record_menu (dict): menu definition for the records menu button.

        user_menu (dict): menu definition for the user management menu button.

        menu_menu (dict): menu definition for the program options menu button.
    """

    def __init__(self, account_methods, records):
        """
        Initialize toolbar attributes.

        Arguments:
            account_methods (list): list of accounting method rules.

            records (list): list of records rules.
        """
        self.name = 'toolbar'
        self.elements = ['-{ELEM}-'.format(ELEM=i) for i in ['amenu', 'rmenu', 'umenu', 'mmenu']]

        # Accounting method menu items
        self.account_items = {}
        acct_menu = []
        for account_method in account_methods:
            acct_menu.append(('', account_method.title))

            menu_groups = {}
            rule_menu = []
            for rule_entry in account_method.rules:
                menu_title = rule_entry.menu_title
                user_access = rule_entry.permissions

                # Add any submenus to the menu definition. Submenus act as flags to main workflow rule.
                rule_submenu = rule_entry.menu_flags

                if not rule_submenu:
                    rule_menu.append(('!', menu_title))
                    self.account_items[menu_title] = user_access
                else:
                    menu_groups[menu_title] = []

                    for submenu in rule_submenu:
                        menu_groups[menu_title].append(submenu)
                        self.account_items[submenu] = user_access

            for menu_group in menu_groups:
                rule_menu.append(('', menu_group))

                menu_titles = menu_groups[menu_group]
                if not menu_titles:
                    continue

                rule_menu.append([('', i) for i in menu_titles])

            acct_menu.append(rule_menu)

        # Program record menu items
        menu_groups = {}
        record_menu = []
        self.record_items = {}

        record_rules = records.rules
        for record_entry in record_rules:
            if not record_entry.program_record or not record_entry.show_menu:  # only display program records
                continue

            menu_title = record_entry.menu_title
            menu_group = record_entry.menu_group
            user_access = record_entry.permissions

            if menu_group:  # menu title will be a sub menu
                try:
                    menu_groups[menu_group].append(menu_title)
                except KeyError:
                    menu_groups[menu_group] = [menu_title]
            else:  # no menu group specified for the record entry - top level menu.
                record_menu.append(('!', menu_title))

            self.record_items[menu_title] = user_access

        for menu_group in menu_groups:
            record_menu.append(('', menu_group))

            menu_titles = menu_groups[menu_group]
            record_menu.append([('!', i) for i in menu_titles])

        self.acct_menu = {'name': '&Validation', 'items': acct_menu}
        self.record_menu = {'name': '&Records', 'items': record_menu}
        self.user_menu = {'name': '&User',
                          'items': [('!', 'Manage &Users'), ('!', '&Messages'), ('', '---'), ('', 'Sign &In'),
                                    ('!', 'Sign &Out')]}
        self.menu_menu = {'name': '&Menu',
                          'items': [('!', '&Settings'), ('', '&Debug'), ('', '---'), ('', '&Help'),
                                    ('', 'Ab&out'), ('', '---'), ('', '&Quit')]}

        self.records_title = records.title

    def _define_menu(self, menu_item, menu=None):
        """
        Return the menu definition for a menu.
        """
        menus = {'amenu': self.acct_menu, 'rmenu': self.record_menu,
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
        menu_audit = self._define_menu('amenu')
        menu_reports = self._define_menu('rmenu')
        menu_user = self._define_menu('umenu')
        menu_menu = self._define_menu('mmenu')

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

    def disable(self, window):
        """
        Disable toolbar buttons.

        Arguments:
            window (Window): GUI window.
        """
        logger.info('Toolbar: disabling toolbar menus')

        # Database administration
        window['-DBMENU-'].update(disabled=True)

        # User administration
        self.toggle_menu(window, 'umenu', 'manage accounts', disabled=True)
        self.toggle_menu(window, 'umenu', 'sign in', disabled=False)
        self.toggle_menu(window, 'umenu', 'sign out', disabled=True)

        # Disable settings modification
        self.toggle_menu(window, 'mmenu', 'settings', disabled=True)

        # Disable record menus
        for menu in self.record_items:
            logger.debug('Toolbar: disabling record menu item {}'.format(menu))
            self.toggle_menu(window, 'rmenu', menu, disabled=True)

        # Disable accounting method menus
        for menu in self.account_items:
            logger.debug('Toolbar: disabling accounting method menu item {}'.format(menu))
            self.toggle_menu(window, 'amenu', menu, disabled=True)

    def enable(self, window):
        """
        Enable toolbar buttons.
        """
        admin = user.admin

        record_menus = self.record_items
        account_menus = self.account_items

        logger.info('Toolbar: enabling toolbar menus')

        # User administration

        # Enable admin-only privileges
        if admin is True:
            # Database administration
            window['-DBMENU-'].update(disabled=False)

            # User administration
            self.toggle_menu(window, 'umenu', 'manage accounts', disabled=False)

        self.toggle_menu(window, 'umenu', 'sign in', disabled=True)
        self.toggle_menu(window, 'umenu', 'sign out', disabled=False)

        # Allow user to modify user-settings
        self.toggle_menu(window, 'mmenu', 'settings', disabled=False)

        # Disable record menus
        for menu in record_menus:
            user_access = record_menus[menu]
            if admin is True or user_access in user.access_permissions():
                logger.debug('Toolbar: enabling record menu item {}'.format(menu))
                self.toggle_menu(window, 'rmenu', menu, disabled=False)

        # Disable accounting method menus
        for menu in account_menus:
            user_access = account_menus[menu]
            if admin is True or user_access in user.access_permissions():
                logger.debug('Toolbar: enabling accounting method menu item {}'.format(menu))
                self.toggle_menu(window, 'amenu', menu, disabled=False)

    def toggle_menu(self, window, menu, menu_item, disabled: bool = False):
        """
        Enable or disable a specific menu item.
        """
        menus = {'amenu': self.acct_menu, 'rmenu': self.record_menu,
                 'umenu': self.user_menu, 'mmenu': self.menu_menu}

        try:
            select_menu = menus[menu.lower()]
        except KeyError:
            msg = 'selected menu {} not list of available menus'.format(menu)
            logger.error(msg)

            return False

        status = '' if not disabled else '!'

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

        # Replace the menu item with updated status
        select_menu['items'] = new_menu

        # Update window to reflect updated status of the menu item
        element_key = self.key_lookup(menu.lower())
        window[element_key].update(self._define_menu(menu))

        return True

    def update_username(self, window, username):
        """
        Update user menu to display username after a user is logged in.
        """
        select_col = mod_const.SELECT_TEXT_COL

        element_key = '-UMENU-'

        # Update the menu item list of the user menu to include the username
        user_items = [('', username), ('', '---')] + self.user_menu['items']
        user_menu = {'name': '&User', 'items': user_items}

        menu_def = self._define_menu('umenu', menu=user_menu)

        window[element_key].update(menu_def)

        # Highlight username
        window[element_key].TKMenu.entryconfig(0, foreground=select_col)
        window[element_key].TKButtonMenu.configure(menu=window[element_key].TKMenu)


# General functions
def get_panels(account_methods, win_size: tuple = None):
    """
    Get the GUI layouts for the configuration-dependant panels.
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


def resize_panels(window, rules):
    """
    Resize GUI elements when the window is resized.
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
            msg = 'failed to resize window - {ERR}'.format(ERR=e)
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
    record_rules = ConfigurationManager(settings.record_rules)
    settings.records = record_rules

    audit_rules = ConfigurationManager(settings.audit_rules)
    cash_rules = ConfigurationManager(settings.cash_rules)
    bank_rules = ConfigurationManager(settings.bank_rules)

    acct_methods = [audit_rules, bank_rules]

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
            menu_mapper[rule.menu_title] = rule.name
        else:
            if not rule_submenu:
                menu_mapper[rule.menu_title] = rule.name
            else:
                for menu_title in rule_submenu:
                    menu_mapper[menu_title] = rule.name

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
    resize_panels(window, acct_rules)
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
            if current_rule is not None:
                try:
                    window[current_rule.current_panel].update(visible=False)
                except KeyError:
                    print(current_rule.panel_keys)
#                window[current_rule.panel_keys[current_rule.first_panel]].update(visible=True)
                window[current_rule.element_key].update(visible=False)
#
                window.refresh()
#
                window[current_rule.element_key].update(visible=True)
#                window[current_rule.panel_keys[current_rule.first_panel]].update(visible=False)
                window[current_rule.current_panel].update(visible=True)
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
            resize_panels(window, acct_rules)

            current_w, current_h = (win_w, win_h)
            resized = True

            continue

        # User login
        if values['-UMENU-'] == 'Sign In':  # user logs on
            logger.debug('displaying user login screen')
            mod_win2.login_window()

            if user.logged_in is True:  # logged on successfully
                logger.info('user signed in as "{}"'.format(user.uid))

                # Switch user icon
                window['-UMENU-'].Widget.configure(image=userin_image)

                # Enable permission specific actions and menus
                toolbar.enable(window)

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

            # Disable all actions and menus
            toolbar.disable(window)

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
            print('menu {} was selected'.format(selected_menu))
            selected_rule = menu_mapper[selected_menu]
            print('selected rule is {}'.format(selected_rule))

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
                toolbar.disable(window)

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

            elif selected_rule in bank_names:  # workflow method is bank reconciliation
                # Obtain the selected rule object
                current_rule = bank_rules.fetch_rule(selected_rule)

                # Use the menu flag to find the primary account
                try:
                    acct_name = current_rule.menu_flags[selected_menu]
                except KeyError:
                    acct_name = selected_rule.name

                # Fetch the primary account
                current_acct = current_rule.fetch_account(acct_name)
                current_rule.current_account = current_acct.name
                current_rule.current_panel = current_acct.key_lookup('Panel')

                # Update the panel-in-display and the account panel
                window[current_panel].update(visible=False)

                current_panel = current_rule.element_key
                window[current_panel].update(visible=True)
                window[current_rule.current_panel].update(visible=True)

                # Disable toolbar
                toolbar.disable(window)

                logger.debug('panel in view is {NAME}'.format(NAME=current_rule.name))
                continue

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
                toolbar.disable(window)

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
                toolbar.enable(window)

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
