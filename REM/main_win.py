"""
REM main program. Includes primary display.
"""
from collections import OrderedDict
import numpy as np
import pandas as pd
import PySimpleGUI as sg
from REM.configuration import ConfigParameters
import REM.layouts as lo
import REM.secondary_win as win2
import REM.program_settings as const
import sys
import time


# Classes
class ToolBar:
    """
    Toolbar object.
    """
    def __init__(self, cnfg):
        """
        Initialize toolbar parameters.
        """
        audit_rules = cnfg.print_rules()

        self.name = 'toolbar'
        self.elements = ['amenu', 'rmenu', 'umenu', 'mmenu']
        self.audit_menu = {'name': '&Audits', 
                           'items': [('!', i) for i in audit_rules]}
        self.reports_menu = {'name': '&Reports', 
                             'items': [('!', 'Summary S&tatistics'), 
                             ('!', '&Summary Reports')]}
        self.user_menu = {'name': '&User', 
                          'items': [('!', '&Manage Accounts'), ('', '---'), 
                          ('', 'Sign &In'), ('!', 'Sign &Out')]}
        self.menu_menu = {'name': '&Menu', 
                          'items': [('!', '&Configuration'), ('', '&Debug'), 
                          ('', '---'), ('', '&Help'), ('', 'About &Program'), 
                          ('', '---'), ('', '&Quit')]}

    def key_lookup(self, element):
        """
        Lookup key for element in schema.
        """
        elements = self.elements
        if element in elements:
            key = lo.as_key('{}'.format(element))
        else:
            key = None

        return(key)

    def layout(self):
        """
        Create the layout for the toolbar GUI element.
        """
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

        toolbar = [[sg.ButtonMenu('', menu_audit, image_data=audit_ico,
                      tooltip='Run Audits', key='-AMENU-', 
                      pad=(padding, padding)),
                    sg.ButtonMenu('', menu_reports, image_data=report_ico,
                      tooltip='Generate Reports & Statistics', key='-RMENU-',
                      pad=(padding, padding)),
                    sg.Button('', image_data=db_ico,
                      tooltip='Modify Database', key='-DBMENU-', 
                      pad=(padding, padding), disabled=True),
                    sg.Text('', pad=(450, 0)),
                    sg.ButtonMenu('', menu_user, image_data=user_ico,
                      tooltip='User Settings', key='-UMENU-', 
                      pad=(padding, padding)),
                    sg.ButtonMenu('', menu_menu, image_data=menu_ico,
                      tooltip='Menu', key='-MMENU-', pad=(padding, padding))]]

        layout = [sg.Frame('', toolbar, relief='groove', pad=(0, 0),
                    key='-TOOLBAR-')]

        return(layout)

    def menu_definition(self, menu):
        """
        Return the menu definition for a menu.
        """
        menus = {'amenu': self.audit_menu, 'rmenu': self.reports_menu, 
                 'umenu': self.user_menu, 'mmenu': self.menu_menu}

        try:
            menu_object = menus[menu.lower()]
        except KeyError:
            print('Selected menu {} not list of available menus'.format(menu))
            return(None)

        menu_def = [menu_object['name'], ['{}{}'.format(*i) for i in \
                    menu_object['items']]]

        return(menu_def)

    def toggle_menu(self, window, menu, menu_item, value:str='enable'):
        """
        Enable / disable menu items.
        """
        menus = {'amenu': self.audit_menu, 'rmenu': self.reports_menu, 
                 'umenu': self.user_menu, 'mmenu': self.menu_menu}

        try:
            menu_object = menus[menu.lower()]
        except KeyError:
            print('Selected menu {} not list of available menus'.format(menu))
            return(False)

        menu_name = menu_object['name']

        status = '' if value == 'enable' else '!'

        menu_items = menus[menu]['items']
        items_clean = [i[1].replace('&', '').lower() for i in menu_items]
        try:
            index = items_clean.index(menu_item.lower())
        except IndexError:
            print('Seleted menu item {} not found in {} item list'.format(menu_item, menu))
            return(False)

        # Set status of menu item
        item = menu_items[index]
        new_item = (status, item[1])

        # Replace menu item with updated status
        menu_items[index] = new_item
        menus[menu.lower()]['items'] = menu_items

        # Update window to reflect updated status of the menu item
        element_key = self.key_lookup(menu.lower())
        window[element_key].update(self.menu_definition(menu))

        return(True)


# General functions
### Placeholder functions ###
def initialize_table(params, filters):
    """
    Scan database for missing transaction numbers.
    """
    header = params['columns']
    df = pd.DataFrame(np.random.randint(0, 100, size=(20, 10)), columns=header)

    return(df)

###

def get_panels(cnfg):
    """
    """
    panels = [lo.action_layout(cnfg)]

    audit_rules = cnfg.audit_rules
    for audit_rule in audit_rules:
        panels.append(audit_rule.layout())

    pane = [sg.Col([[sg.Pane(panels, orientation='horizontal', \
              show_handle=False, border_width=0, relief='flat', \
              key='-PANELS-')]], \
              pad=(0, 10), justification='center', element_justification='center')]

    return(pane)

def reset_to_default(window, rule):
    """
    Reset main window to program defaults.
    """
    if not rule:
        return(None)

    current_key = rule.element_key

    # Disable current panel
    window['-ACTIONS-'].update(visible=True)
    window[current_key].update(visible=False)

    # Reset 'Start' element in case audit was in progress
    start_key = rule.key_lookup('Start')
    window[start_key].update(disabled=False)

    # Reset 'Generate Report' element in case audit was nearly complete
    end_key = rule.key_lookup('Finalize')
    window[end_key].update(disabled=True)

    # Reset audit parameters. Audit specific parameters include actions
    # buttons Scan and Confirm, for instance.

    # Reset control element values
    controls = rule.controls
    for control in controls:
        control_key = rule.key_lookup(control.name)
        print('Re-setting control element {} to default'.format(control.name))
        window[control_key].update(value='')

    # Reset tab-specific element values
    for i, tab in enumerate(rule.tabs):
        # Reset table and summary values
        # Generate default table values
        header = tab.db_columns
        ncol = len(header)
        data = lo.empty_data_table(nrow=10, ncol=ncol)

        table_key = tab.key_lookup('Table')
        window[table_key].update(values=data)

        # Reset summary element
        summary_key = tab.key_lookup('Summary')
        window[summary_key].update(value='')

        # Reset action buttons
        tab.toggle_action_buttons(window, 'disable')

        # Reset visible tabs
        visible = True if i == 0 else False
        print('Re-setting visibility of {} tab to {}'.format(tab.name, visible))
        window[tab.element_key].update(visible=visible)

    return(None)

def main():
    """
    Main function.
    """
    # Theme
    default_col = const.DEFAULT_COL
    action_col = const.ACTION_COL
    text_col = const.TEXT_COL
    inactive_col = const.BUTTON_COL
    font = const.MAIN_FONT

    sg.set_options(element_padding=(0, 0), margins=(0, 0), \
                   auto_size_buttons=True, auto_size_text=True, \
                   background_color=default_col, element_text_color=text_col, \
                   element_background_color=default_col, font=font, \
                   input_text_color=text_col, text_color=text_col, \
                   text_element_background_color=default_col, \
                   input_elements_background_color=action_col, \
                   button_color=(text_col, default_col))

    # Settings
    infile = '/home/cthornton/dev/configuration.yaml'  #change!!!
    cp = ConfigParameters(infile)
    db = cp.database

    toolbar = ToolBar(cp)
    layout = [toolbar.layout(), get_panels(cp)]

    # Element keys and names
    audit_names = cp.print_rules()

    cancel_keys =  [i.key_lookup('Cancel') for i in cp.audit_rules]
    start_keys = [i.key_lookup('Start') for i in cp.audit_rules]

    print('Current audit rules are {}'.format(', '.join(audit_names)))
    report_tx = 'Summary Report'
    stats_tx = 'Summary Statistics'

    # Event modifiers
    audit_in_progress = False
    rule = None
    debug_win = None
    summary = {}
    
    # Initialize main window and login window
    window = sg.Window('REM Tila', layout, font=('Arial', 12), size=(1170, 840))

    # Event Loop
    while True:
        event, values = window.read()
        print(event, values)

        # Quit program
        if event == sg.WIN_CLOSED or values['-MMENU-'] == 'Quit':
            break

        # User login
        if values['-UMENU-'] == 'Sign In':  #user logs on
            print('Starting up')
            print('Displaying user login screen')
            user = win2.login_window(cp)

            if user:  #logged on successfully
                user_active = True

                # Disable sign-in and enable sign-off
                toolbar.toggle_menu(window, 'umenu', 'sign in', value='disable')
                toolbar.toggle_menu(window, 'umenu', 'sign out', value='enable')

                # Enable permission specific actions and menus

                # Admin only actions and menus
                admin = user._superuser
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
                    toolbar.toggle_menu(window, 'mmenu', 'configuration', value='enable')

                # Enable permissions on per audit rule basis defined in config
                for rule_name in audit_names:
                    if admin:
                        toolbar.toggle_menu(window, 'amenu', rule_name, value='enable')
                        window[rule_name].update(disabled=False)

                    rule = cp.fetch_rule(rule_name)

                    perms = rule.permissions
                    if perms != 'admin':
                        toolbar.toggle_menu(window, 'amenu', rule_name, value='enable')
                        window[rule_name].update(disabled=False)

        # User log-off
        if values['-UMENU-'] == 'Sign Out':  #user signs out
            # Confirm sign-out
            msg = 'Are you sure you would like to sign-out?'
            selection = win2.confirm_action(msg)

            if selection == 'Cancel':
                continue

            audit_in_progress = False
            rule = reset_to_default(window, rule)  #reset to home screen

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
            toolbar.toggle_menu(window, 'mmenu', 'configuration', value='disable')

            # Audit rules
            for rule_name in audit_names:
                window[rule_name].update(disabled=True)
                toolbar.toggle_menu(window, 'amenu', rule_name, value='disable')

        # Debugger window
        if not debug_win and values['-MMENU-'] == 'Debug':
            debug_win = win2.debugger()
            debug_win.finalize()
            print('Starting debugger')
        elif debug_win:
            debug_event, debug_value = debug_win.read(timeout=100)

            if debug_event == sg.WIN_CLOSED:
                debug_win.close()
                debug_win = None

        # Cancel action - code block must remain on top
        if not audit_in_progress and event in cancel_keys:
            rule = reset_to_default(window, rule)
            continue

        # Switch panels when audit in progress
        if audit_in_progress and (event == '-DB-' or event in cancel_keys or values['-AMENU-'] in audit_names or values['-RMENU-'] in (report_tx, stats_tx)):
            msg = 'Audit is currently running. Are you sure you would like to exit?'
            selection = win2.confirm_action(msg)

            if selection == 'OK':
                # Reset to defaults
                audit_in_progress = False
                rule = reset_to_default(window, rule)
            else:
                continue

        # Switch panels when audit not in progress
        if rule and (event == '-DB-' or event in cancel_keys or values['-AMENU-'] in audit_names or values['-RMENU-'] in (report_tx, stats_tx)):
            rule = reset_to_default(window, rule)

        # Activate appropriate audit panel
        if values['-AMENU-'] or event in audit_names:
            # Obtain the selected audit rule object
            action_value = values['-AMENU-'] if values['-AMENU-'] else event
            rule = cp.fetch_rule(action_value)

            panel_key = rule.element_key
            window['-ACTIONS-'].update(visible=False)
            window[panel_key].update(visible=True)

            tab_windows = [i.name for i in rule.tabs]
            final_index = len(tab_windows) - 1

            print('Panel in view is {} with tabs {}'.format(rule.name, ', '.join(tab_windows)))

        # Start the selected audit
        if event in start_keys:
            # Check if all control elements have input
            controls = rule.controls
            has_input = []
            for control in controls:
                ctrl_key = rule.key_lookup(control.name)
                ctrl_value = values[ctrl_key]

                if not ctrl_value:
                    ctrl_desc = control.desc
                    msg = 'Input required for the "{}" field'.format(ctrl_desc)
                    win2.selection_reqd(msg)

                    has_input.append(False)
                else:
                    has_input.append(True)

                    # Update value in object
                    control.value = ctrl_value

            # Start Audit
            if all(has_input):  #all controls have input
                audit_in_progress = True
                print('{} audit in progress with parameters {}'\
                    .format(rule.name, ', '.join(['{}={}'\
                    .format(i.name, i.value) for i in controls])))

                # Disable start key
                start_key = rule.key_lookup('Start')
                window[start_key].update(disabled=True)

                # Initialize audit
                tab_keys = []  #to track tabs displayed
                for tab in rule.tabs:
                    tab_key = tab.element_key
                    tab_keys.append(tab_key)

                    # Extract data from database
                    controls = rule.controls  #for query filter parameters
                    filters = [(control.name, control.operator, control.value) for control in controls]
                    params = tab.fetch_db_params()
#                    df = cp.db.query(params, filters)
                    df = initialize_table(params, filters)

                    # Update tab object and elements
                    tab.df = df  #update tab data
                    tab.update_table(window)  #display tab data in table
                    tab.update_summary(window)  #summarize individual tab data

                    # Enable / disable action buttons
                    schema = tab.toggle_action_buttons(window, 'enable')

        action_performed = False
        # Scan for missing data if applicable
        if audit_in_progress:
            tg_key = rule.key_lookup('TG')
            current_tab = window[tg_key].Get()

            # Get current tab object
            tab = rule.fetch_tab(current_tab, by_key=True)
            controls = rule.controls

            # Find selected rows whenever the table is interactive.
            tbl_key = tab.key_lookup('Table')
            if event == tbl_key:
                row_colors = tab.verify_row(values[tbl_key][0])
                window[tbl_key].update(row_colors=row_colors)
                window.Refresh()

            # Run schema action
            action_buttons = [tab.key_lookup(i) for i in tab.action_elements]
            if event in action_buttons:
                # Use schema action method
                 print('Running {LAYOUT} algorithms on {NAME} data'\
                     .format(LAYOUT=tab.type, NAME=tab.element_name))
                 df = tab.run_action(database=db, controls=controls)
                 action_performed = True

                 # Update information elements - most actions modify tab data 
                 # in some way.
                 tab.update_table(window)
                 tab.update_summary(window)

            # Enable movement to the next tab
            current_index = tab_keys.index(current_tab)
            print('Current tab in view is {}'.format(tab_windows[current_index]))
            next_index = current_index + 1
            if action_performed and not next_index > final_index:
                next_key = tab_keys[next_index]

                # Enable next tab
                print('Enabling tab {}'.format(tab_windows[next_index]))
                window[next_key].update(disabled=False, visible=True)

            # Enable the finalize button when all actions have been performed
            # on all tabs.
            if action_performed and current_index == final_index:
                print('Allow generation of final report')
                final_key = rule.key_lookup('Finalize')
                window[final_key].update(disabled=False)
            

    window.close()

if __name__ == "__main__":
    main()
    sys.exit(0)
