# -*- coding: utf-8 -*-
"""
REM main program. Includes primary display.
"""
import datetime
from multiprocessing import freeze_support
import PySimpleGUI as sg
import REM.audit as audit
import REM.data_manipulation as dm
from REM.config import cnfg, settings
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

    def __init__(self, audit_rules):
        """
        Initialize toolbar parameters.
        """
        audit_names = audit_rules.print_rules()

        self.name = 'toolbar'
        self.elements = ['amenu', 'rmenu', 'umenu', 'mmenu']
        self.audit_menu = {'name': '&Audits', 'items': [('!', i) for i in audit_names]}
        self.reports_menu = {'name': '&Reports',
                             'items': [('!', 'Summary S&tatistics'), ('!', '&Summary Reports')]}
        self.user_menu = {'name': '&User',
                          'items': [('!', '&Manage Accounts'), ('', '---'), ('', 'Sign &In'), ('!', 'Sign &Out')]}
        self.menu_menu = {'name': '&Menu',
                          'items': [('!', '&Configure'), ('', '&Debug'), ('', '---'), ('', '&Help'),
                                    ('', 'About &Program'), ('', '---'), ('', '&Quit')]}

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

        toolbar = [[sg.Col([[sg.ButtonMenu('', menu_audit, key='-AMENU-', image_data=audit_ico, tooltip=_('Run Audits'),
                                           pad=(padding, padding)),
                             sg.ButtonMenu('', menu_reports, key='-RMENU-', image_data=report_ico,
                                           tooltip=_('Generate Reports & Statistics'), pad=(padding, padding)),
                             sg.Button('', image_data=db_ico, key='-DBMENU-', tooltip=_('Modify Database'),
                                       pad=(padding, padding), border_width=0, disabled=True)]],
                           justification='l'),
                    sg.Canvas(key='-CANVAS_WIDTH-', size=(width - 260, 0), visible=True),
                    sg.Col([[sg.ButtonMenu('', menu_user, key='-UMENU-', image_data=user_ico,
                                           tooltip=_('User Settings'), pad=(padding, padding)),
                             sg.ButtonMenu('', menu_menu, key='-MMENU-', image_data=menu_ico,
                                           tooltip=_('Help and program settings'), pad=(padding, padding))]],
                           justification='r')]]

        layout = [sg.Frame('', toolbar, key='-TOOLBAR-', relief='groove', pad=(0, 0))]

        return layout

    def update_username(self, window, username):
        """
        Update user menu to display username after a user is logged in.
        """
        element_key = '-UMENU-'

        user_menu = {'name': '&User',
                     'items': [('!', username), ('', '---'), ('!', '&Manage Accounts'), ('', '---'),
                               ('!', 'Sign &In'), ('', 'Sign &Out')]}

        menu_def = self.menu_definition('umenu', menu=user_menu)

        window[element_key].update(menu_def)

    def menu_definition(self, menu_item, menu=None):
        """
        Return the menu definition for a menu.
        """
        menus = {'amenu': self.audit_menu, 'rmenu': self.reports_menu,
                 'umenu': self.user_menu, 'mmenu': self.menu_menu}

        if menu is None:
            try:
                menu_object = menus[menu_item.lower()]
            except KeyError:
                print('Error: selected menu {} not list of available menus'.format(menu_item))
                return None
        else:
            menu_object = menu

        menu_def = [menu_object['name'], ['{}{}'.format(*i) for i in menu_object['items']]]

        return menu_def

    def toggle_menu(self, window, menu, menu_item, value: str = 'enable'):
        """
        Enable / disable menu items.
        """
        menus = {'amenu': self.audit_menu, 'rmenu': self.reports_menu,
                 'umenu': self.user_menu, 'mmenu': self.menu_menu}

        try:
            menus[menu.lower()]
        except KeyError:
            print('Error: selected menu {} not list of available menus'.format(menu))
            return False

        status = '' if value == 'enable' else '!'

        menu_items = menus[menu]['items']
        items_clean = [i[1].replace('&', '').lower() for i in menu_items]
        try:
            index = items_clean.index(menu_item.lower())
        except IndexError:
            print('Error: selected menu item {MENU} not found in {MENUS} item list'.format(MENU=menu_item, MENUS=menu))
            return False

        # Set status of menu item
        item = menu_items[index]
        new_item = (status, item[1])

        # Replace menu item with updated status
        menu_items[index] = new_item
        menus[menu.lower()]['items'] = menu_items

        # Update window to reflect updated status of the menu item
        element_key = self.key_lookup(menu.lower())
        window[element_key].update(self.menu_definition(menu))

        return True


# General functions
def get_panels(audit_rules, win_size: tuple = None):
    """
    """
    if win_size:
        width, height = win_size
    else:
        width, height = (const.WIN_WIDTH, const.WIN_HEIGHT)

    # Home page action panel
    panels = [lo.action_layout(audit_rules)]

    # Audit rule panels
    for audit_rule in audit_rules.rules:
        panels.append(audit_rule.layout(win_size=win_size))
        panels.append(audit_rule.summary.layout(win_size=win_size))

    # Database modification panel
    #    panels.append(db_layout())

    # Layout
    pane = [sg.Canvas(size=(0, height), key='-CANVAS_HEIGHT-', visible=True),
            sg.Col([[sg.Pane(panels, key='-PANELS-', orientation='horizontal', show_handle=False, border_width=0,
                             relief='flat')]], pad=(0, 10), justification='c', element_justification='c')]

    return pane


def resize_elements(window, audit_rules, win_size: tuple = None):
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
    for audit_rule in audit_rules:
        audit_rule.resize_elements(window, win_size=win_size)
        audit_rule.summary.resize_elements(window, win_size=win_size)


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


def reset_to_default(window, rule, current: bool = False):
    """
    Reset main window to program defaults.
    """
    if not rule:
        return (None)

    win_width, win_height = window.size

    current_key = rule.element_key
    summ_panel_key = rule.summary.element_key

    # Disable current panel
    window[current_key].update(visible=False)
    window[summ_panel_key].update(visible=False)
    window['-ACTIONS-'].update(visible=True)

    # Reset 'Start' element in case audit was in progress
    start_key = rule.key_lookup('Start')
    window[start_key].update(disabled=False)

    # Reset 'Generate Report' element in case audit was nearly complete
    end_key = rule.key_lookup('Finalize')
    window[end_key].update(disabled=True)

    # Switch to first tab in summary panel
    tg_key = rule.summary.key_lookup('TG')
    window[tg_key].Widget.select(0)

    # Reset rule item attributes, including tab, summary, and parameter
    rule.reset_attributes()

    # Reset audit parameters. Audit specific parameters include actions
    # buttons Scan and Confirm, for instance.
    rule.toggle_parameters(window, 'enable')

    # Reset parameter element values
    params = rule.parameters
    for param in params:
        print('Info: resetting rule parameter element {} to default'.format(param.name))
        window[param.element_key].update(value='')
        try:
            window[param.element_key2].update(vaue='')
        except AttributeError:
            pass

    # Reset tab-specific element values
    for i, tab in enumerate(rule.tabs):
        # Reset displays

        ## Reset table element
        table_key = tab.key_lookup('Table')
        window[table_key].update(values=tab.df.values.tolist())

        tab.resize_elements(window, win_size=(win_width, win_height))

        ## Reset summary element
        summary_key = tab.key_lookup('Summary')
        window[summary_key].update(value='')

        # Reset action buttons
        tab.toggle_actions(window, 'disable')

        # Reset visible tabs
        visible = True if i == 0 else False
        print('Info: tab {TAB}, rule {RULE}: re-setting visibility to {STATUS}'
              .format(TAB=tab.name, RULE=tab.rule_name, STATUS=visible))
        window[tab.element_key].update(visible=visible)

    if current:
        window['-ACTIONS-'].update(visible=False)
        window[current_key].update(visible=True)
        return current_key
    else:
        return '-ACTIONS-'


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

    # Configure GUI layout
    audit_rules = audit.AuditRules(cnfg)
    toolbar = ToolBar(audit_rules)
    layout = [toolbar.layout(win_size=(current_w, current_h)),
              get_panels(audit_rules, win_size=(current_w, current_h))]

    # Element keys and names
    audit_names = audit_rules.print_rules()

    cancel_keys = [i.key_lookup('Cancel') for i in audit_rules.rules]
    cancel_keys += [i.summary.key_lookup('Cancel') for i in audit_rules.rules]
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
    audit_in_progress = False
    summary_panel_active = False
    current_tab = None
    rule = None
    debug_win = None

    # Initialize main window and login window
    window = sg.Window('REM Tila', layout, icon=settings.logo, font=('Arial', 12), size=(current_w, current_h),
                       resizable=True, return_keyboard_events=True)
    window.finalize()
    window.maximize()
    print('Info: starting up')

    screen_w, screen_h = window.get_screen_dimensions()
    print('Info: screen size is {W} x {H}'.format(W=screen_w, H=screen_h))

    user_image = tk.PhotoImage(data=const.USER_ICON)
    userin_image = tk.PhotoImage(data=const.USERIN_ICON)

    resize_elements(window, audit_rules.rules, win_size=(current_w, current_h))
    resized = False

    # Event Loop
    action_panel = current_panel = '-ACTIONS-'
    while True:
        event, values = window.read(timeout=100)

        # Quit program
        if event == sg.WIN_CLOSED or values['-MMENU-'] == 'Quit':
            break

        # Resize screen
        if resized and current_panel != action_panel:
            window[current_panel].update(visible=False)
            window['-ACTIONS-'].update(visible=True)

            window.refresh()

            window['-ACTIONS-'].update(visible=False)
            window[current_panel].update(visible=True)

            resized = False

        # Resize screen
        ## Get window dimensions
        win_w, win_h = window.size
        if win_w != current_w or win_h != current_h:
            print('Info: new window size is {W} x {H}'.format(W=win_w, H=win_h))

            # Update sizable elements
            resize_elements(window, audit_rules.rules, win_size=(win_w, win_h))

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
                    window['-DB-'].update(disabled=False)
                    window['-DBMENU-'].update(disabled=False)

                    # Reports and statistics
                    toolbar.toggle_menu(window, 'rmenu', 'summary reports', value='enable')
                    toolbar.toggle_menu(window, 'rmenu', 'summary statistics', value='enable')

                    window['-STATS-'].update(disabled=False)
                    window['-REPORTS-'].update(disabled=False)

                    # User
                    toolbar.toggle_menu(window, 'umenu', 'manage accounts', value='enable')

                    # Menu
                    toolbar.toggle_menu(window, 'mmenu', 'configure', value='enable')

                # Enable permissions on per audit rule basis defined in config
                for rule_name in audit_names:
                    if admin:
                        toolbar.toggle_menu(window, 'amenu', rule_name, value='enable')
                        window[rule_name].update(disabled=False)

                    rule = audit_rules.fetch_rule(rule_name)

                    perms = rule.permissions
                    if perms != 'admin':
                        toolbar.toggle_menu(window, 'amenu', rule_name, value='enable')
                        window[rule_name].update(disabled=False)

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

            audit_in_progress = False
            current_panel = reset_to_default(window, rule)  # reset to home screen
            rule = None

            # Reset User attributes
            user.logout()

            # Switch user icon
            window['-UMENU-'].Widget.configure(image=user_image)

            # Disable sign-out and enable sign-in
            toolbar.toggle_menu(window, 'umenu', 'sign in', value='enable')
            toolbar.toggle_menu(window, 'umenu', 'sign out', value='disable')

            # Disable all actions and menus
            # Database administration
            window['-DB-'].update(disabled=True)
            window['-DBMENU-'].update(disabled=True)

            # Reports and statistics
            toolbar.toggle_menu(window, 'rmenu', 'summary reports', value='disable')
            toolbar.toggle_menu(window, 'rmenu', 'summary statistics', value='disable')
            window['-STATS-'].update(disabled=True)
            window['-REPORTS-'].update(disabled=True)

            # User
            toolbar.toggle_menu(window, 'umenu', 'manage accounts', value='disable')

            # Menu
            toolbar.toggle_menu(window, 'mmenu', 'configure', value='disable')

            # Audit rules
            for rule_name in audit_names:
                window[rule_name].update(disabled=True)
                toolbar.toggle_menu(window, 'amenu', rule_name, value='disable')

        if values['-MMENU-'] == 'Configure':  # open settings window
            win2.edit_settings(win_size=window.size)
            continue

        # Debugger window
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

        if not audit_in_progress and event in cancel_keys:
            toolbar.toggle_menu(window, 'mmenu', 'configure', value='enable')
            current_panel = reset_to_default(window, rule)
            rule = None
            continue

        # Switch panels when audit in progress
        if audit_in_progress and (event in ('-DB-', '-DBMENU-') or event in cancel_keys
                                  or values['-AMENU-'] in audit_names or values['-RMENU-'] in (report_tx, stats_tx)):

            msg = _('Audit is currently running. Are you sure you would like to exit?')
            selection = win2.popup_confirm(msg)

            if selection == 'OK':
                # Reset to defaults
                toolbar.toggle_menu(window, 'mmenu', 'configure', value='enable')
                audit_in_progress = False
                summary_panel_active = False
                current_panel = reset_to_default(window, rule)
                rule = None
            else:
                continue

        # Switch panels when audit not in progress
        if rule and (event in ('-DB-', '-DBMENU-') or event in cancel_keys or values['-AMENU-'] in audit_names or
                     values['-RMENU-'] in (report_tx, stats_tx)):
            current_panel = reset_to_default(window, rule)
            rule = None

        # Activate appropriate audit panel
        if values['-AMENU-'] or event in audit_names:
            # Obtain the selected audit rule object
            action_value = values['-AMENU-'] if values['-AMENU-'] else event
            rule = audit_rules.fetch_rule(action_value)

            current_panel = rule.element_key
            window['-ACTIONS-'].update(visible=False)
            window[current_panel].update(visible=True)

            tab_windows = [i.name for i in rule.tabs]
            final_index = len(tab_windows) - 1

            # Set up variables for updating date parameter fields
            date_param = rule.fetch_parameter('date', by_type=True)
            try:
                date_key = rule.key_lookup(date_param.name)
            except AttributeError:
                date_key = None

            date_str = []

            print('Info: the panel in view is {} with tabs {}'.format(rule.name, ', '.join(tab_windows)))

        # Format date parameter field, if used in audit rule
        if event == date_key:
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
                removed_char = date_str.pop()

                date_str_fmt = format_date_element(date_str)
                window[date_key].update(value=date_str_fmt)
            else:
                date_str_fmt = format_date_element(date_str)
                window[date_key].update(value=date_str_fmt)

        # Start the selected audit
        try:
            start_key = rule.key_lookup('Start')
        except AttributeError:
            start_key = None

        if event == start_key:
            # Check if all rule parameters elements have input
            params = rule.parameters
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
                for tab in rule.tabs:
                    tab_key = tab.element_key
                    tab_keys.append(tab_key)

                    # Prepare the filter rules to filter query results
                    main_table = [i for i in tab.db_tables][0]
                    rule_params = rule.parameters  # to filter data tables
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
                    audit_in_progress = True
                    print('Info: {} audit in progress with parameters {}'
                          .format(rule.name, ', '.join(['{}={}'.format(i.name, i.value) for i in params])))

                    # Disable start button and parameter elements
                    start_key = rule.key_lookup('Start')
                    window[start_key].update(disabled=True)
                    rule.toggle_parameters(window, 'disable')

                    # Disable user ability to modify settings while audit is in progress
                    toolbar.toggle_menu(window, 'mmenu', 'configure', value='disable')
                else:
                    for tab in rule.tabs():
                        tab.reset_dynamic_attributes()

        action_performed = False
        # Scan for missing data if applicable
        if audit_in_progress and not summary_panel_active:
            tg_key = rule.key_lookup('TG')
            previous_tab = current_tab
            current_tab = window[tg_key].Get()

            # Get current tab in view
            tab = rule.fetch_tab(current_tab, by_key=True)

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
                params = rule.parameters
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
            final_key = rule.key_lookup('Finalize')
            summary_key = rule.summary.element_key
            if tab.audit_performed and current_index == final_index:
                window[final_key].update(disabled=False)

            if event == final_key:  # display summary panel
                summary_panel_active = True
                rule_summ = rule.summary

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
                for tab in rule.tabs:
                    tab.resize_elements(window, win_size=window.size)

        # Summary Panel
        if audit_in_progress and summary_panel_active:
            # Get current tab in view
            tg_key = rule.summary.key_lookup('TG')
            current_tab = window[tg_key].Get()
            summ_tab = rule.summary.fetch_tab(current_tab, by_key=True)

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
            back_key = rule.summary.key_lookup('Back')
            if event == back_key:
                summary_panel_active = False

                # Return to tab display
                current_panel = rule.element_key
                window[summary_key].update(visible=False)
                window[current_panel].update(visible=True)

                # Reset summary values
                rule_summ.reset_attributes()
                rule_summ.resize_elements(window, win_size=window.size)

                # Switch to first tab
                window[tg_key].Widget.select(0)

            # Save results of the audit
            save_key = rule.summary.key_lookup('Save')
            if event == save_key:
                # Save summary to excel or csv file
                title = rule.summary.title.replace(' ', '_')
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
                    rule_summ.save_to_database(user, rule.parameters)
                except Exception as e:
                    msg = _('Save to database failed - {}').format(e)
                    win2.popup_error(msg)
                else:
                    # Reset audit elements
                    toolbar.toggle_menu(window, 'mmenu', 'configure', value='enable')
                    audit_in_progress = False
                    summary_panel_active = False
                    rule_summ.reset_attributes()
                    rule_summ.resize_elements(window, win_size=window.size)
                    current_panel = reset_to_default(window, rule, current=True)

    window.close()


if __name__ == "__main__":
    freeze_support()
    main()
    sys.exit(0)
