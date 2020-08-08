from collections import OrderedDict
import data_access as db
import layout_mods as lm
import importer
import math
import numpy as np
import pandas as pd
import program_settings as const
import pyodbc
import PySimpleGUI as sg
import random
import string
import sys
import time

# Classes
class ProgramConfig:
    """
    """

    def __init__(self):
        """
        """

        self.odbc_db = None
        self.odbc_server = None
        self.odbc_driver = None
        self.transactions = {'Cash': ['', '', '', '', '', '', '', '', '', ''], 
                             'Return': ['', '', '', '', '', '', '', '', '', ''], 
                             'Receipt': ['', '', '', '', '', '', '', '', '', ''], 
                             'ARV': ['', '', '', '', '', '', '', '', '', ''], 
                             'Deposit': ['', '', '', '', '', '', '', '', '', ''], 
                             'Expenses': ['', '', '', '', '', '', '', '', '', '']}
        self.statments = {'Statements': ['', '', '', '', '', '', '', '', '', ''], 
                          'Summary': ['', '', '', '', '', '', '', '', '', '']}

    def read(self):
        """
        Populate class attributes from configuration file.
        """
        pass

    def modify(self):
        """
        Modify configuration settings.
        """
        pass


# General functions
def confirm_action(msg):
    """Ask user if they would really like to continue without completing 
    whatever action is currently being undertaken.
    """
    return(sg.popup_ok_cancel(msg, title='', font=('Arial', 11)))

def return_order(transaction):
    return(transaction[1])

def rand_str():
    return ''.join(random.choice(string.ascii_lowercase) for i in range(10))

def rand_int(min_val=500, max_val=10000):
    return random.randint(min_val, max_val)

### Placeholder functions ###
def scan_for_missing(tab_key, date):
    """
    Scan database for missing transaction numbers.
    """
    df = pd.DataFrame(np.random.randint(0,100,size=(10, 10)), columns=list('ABCDEFGHIJ'))
    return(df)

def initialize_table(tab_key, date, branch):
    """
    Scan database for missing transaction numbers.
    """
    df = pd.DataFrame(np.random.randint(0, 100, size=(20, 10)), columns=list('ABCDEFGHIJ'))
    return(df)

###

# Layout Funtions
def get_toolbar(frozen:bool=False):
    """
    """
    menu_audit = ['&Audits', ['&Transaction Audit', '&Validate Statements']]
    menu_reports = ['&Reports', ['Summary &Statistics', '!Summary Re&ports']]
    menu_user = ['&User', ['&Manage Account', '---', 'Sign In&', '!Sign &Out']]
    menu_menu = ['&Menu', ['&Configuration', '&Debug', '---', '&Help', 'About &Program', '---', '&Quit']]

    audit_ico = const.AUDIT_ICON
    report_ico = const.REPORT_ICON
    db_ico = const.DB_ICON
    user_ico = const.USER_ICON
    menu_ico = const.MENU_ICON

    toolbar_items = [[sg.ButtonMenu('', menu_audit, image_data=audit_ico, \
                        tooltip='Run Audtis', key='-AMENU-', pad=(5, 5)), \
                      sg.ButtonMenu('', menu_reports, image_data=report_ico, \
                        tooltip='Generate Reports & Statistics', key='-RMENU-', \
                        pad=(5, 5)), \
                      sg.Button('', image_data=db_ico, \
                        tooltip='Modify Database', key='-DB-', pad=(5, 5), \
                        disabled=True),
                      sg.Text('', pad=(450, 0)),
                      sg.ButtonMenu('', menu_user, image_data=user_ico, \
                        tooltip='User Settings', key='-UMENU-', pad=(5, 5)), \
                      sg.ButtonMenu('', menu_menu, image_data=menu_ico, \
                        tooltip='Menu', key='-MMENU-', pad=(5, 5))]]

    toolbar = [sg.Frame('', toolbar_items, relief='groove', pad=(0, 0), \
                 key='-TOOLBAR-')]

    return(toolbar)

def action_layout():
    """
    """
    buttons = [[lm.B1('Transaction Audit', pad=(10, (10, 2)))],
               [lm.B1('Validate Statements', pad=(10, (2, 10)))],
               [sg.HorizontalSeparator()],
               [lm.B1('Modify Database', pad=(10, 10), disabled=True)],
               [sg.HorizontalSeparator()],
               [lm.B1('Summary Statistics', pad=(10, (10, 2)), disabled=True)],
               [lm.B1('Summary Reports', pad=(10, (2, 10)), disabled=True)]]

    layout = sg.Col([[sg.Text('', pad=(1, 100))],
                     [sg.Frame('', buttons, element_justification='center', 
                        relief='raised', background_color=const.ACTION_COL)],
                     [sg.Text('', pad=(1, 100))]], key='-ACTIONS-')

    return(layout)

def empty_data_table(nrow:int=10, ncol:int=10):
    """
    """
    return([['' for col in range(ncol)] for row in range(nrow)])


def tab_layout(cnfg, audit_type:str='transactions'):
    """
    Layout of the audit panel tab groups. 
    """
    # Transaction types
    if audit_type == 'transactions':
        tab_keys = cnfg.transactions
    elif audit_type == 'statements':
        tab_keys = cnfg.statements

    # Element parameters
    background_col = const.ACTION_COL

    pad_frame = 20
    pad_el = 2

    # Populate tab layouts with elements
    layout = []
    for i, tab_key in enumerate(tab_keys):
        # Enable only the first tab to start
        frozen = False if i == 0 else True

        # Generate empty table
        header = tab_keys[tab_key]
        data = empty_data_table(nrow=10, ncol=len(header))

        # Create layout for individual tabs
        tab_layout = [[db.create_table(data, header, tab_key)],
                      [sg.Text('Summary', pad=((pad_frame, 0), pad_el), 
                         background_color=background_col),
                       sg.Text(' ' * 140, pad=((pad_frame, 0), pad_el), 
                         background_color=background_col),
                       lm.B2('Upload', pad=((0, pad_el), pad_el), 
                         key='-UPLOAD-', disabled=True),
                       lm.B2('Scan', pad=((0, pad_el), pad_el), 
                         key='-SCAN_TAUDIT-', disabled=True),
                       lm.B2('Next', pad=((0, pad_frame), pad_el), 
                         key='-NEXT-', disabled=True)],
                      [sg.Multiline('', size=(50, 8),
                         pad=((pad_frame, 0), (pad_el, pad_frame)),
                         key='-{}_SUMMARY-'.format(tab_key.upper()))]]

        layout.append(sg.Tab('{}'.format(tab_key), 
                        tab_layout, background_color=background_col, 
                        disabled=frozen, key='-{}-'.format(tab_key.upper())))

    return(layout)

def taudit_layout(cnfg):
    """
    Layout for the Transactions audit.
    """
    # Element Parameters
    inactive_color = const.INACTIVE_COL
    action_color = const.ACTION_COL
    default_col = const.DEFAULT_COL
    text_color = const.TEXT_COL

    date_ico = const.CALENDAR_ICON

    pad_el = 2
    pad_v = 10

    # Frame Layout
    screen = [[sg.Text('', pad=(0, (0, 0)))], 
              [sg.Text('Date:    ', pad=((0, pad_el), (0, pad_v))),
               sg.Input('', key='-DATE-', size=(16, 1), enable_events=True, 
                 pad=((0, pad_el), (0, pad_v))),
               sg.CalendarButton('', format='%Y-%m-%d', image_data=date_ico, 
                 border_width=0, size=(2, 1), pad=(0, (0, pad_v)), 
                 key='-DATEBUTTON-'),
               sg.Text('Branch Office:', pad=((40, pad_el), (0, pad_v))),
               sg.Combo(['A', 'B', 'C', 'D', 'E'], key='-BRANCH-', 
                 enable_events=True, size=(6, 1), pad=(0, (0, pad_v)))],
              [sg.TabGroup([tab_layout(cnfg, audit_type='transactions')], 
                 pad=(10, 10), tab_background_color=inactive_color,
                 selected_title_color=text_color,
                 selected_background_color=action_color,
                 background_color=default_col, key='-TABS-')],
              [lm.B2('Cancel', key='-CANCEL-', pad=((0, pad_el), (pad_v, 0)), 
                 tooltip='Cancel current action'), 
               lm.B2('Run', key='-RUN_TAUDIT-', pad=((pad_el, 0), (pad_v, 0)), 
                 tooltip='Start transaction audit'),
               sg.Text(' ' * 164, pad=(0, (0, pad_v))),
               sg.Text('Debug mode:', tooltip='Run audit in debug mode', 
                 pad=(0, (pad_v, 0))),
               sg.Checkbox('', pad=(0, (pad_v, 0)), key='-DEBUG-', 
                 enable_events=True)],
              [sg.Text('', pad=(0, 0))]]

    # Pane elements must be columns
    layout = sg.Col(screen, key='-TAUDIT-', visible=False, pad=(10, 10))

    return(layout)

def saudit_layout(cnfg):
    """
    Layout for the Statements audit.
    """
    pass

def get_panels(cnfg):
    """
    """
    panels = [action_layout(), taudit_layout(cnfg)]
#    panels = [action_layout(), taudit_layout(cnfg), saudit_layout(cnfg)]

    pane = [sg.Col([[sg.Pane(panels, orientation='horizontal', \
              show_handle=False, border_width=0, relief='flat', \
              key='-PANELS-')]], \
              pad=(0, 10), justification='center', element_justification='center')]

    return(pane)

def reset_to_default(window, cnfg):
    """
    """
    # Switch back to home screen
    window['-TAUDIT-'].update(visible=False)
    window['-ACTIONS-'].update(visible=True)

    # Enable / disable elements
    window['-RUN_TAUDIT-'].update(disabled=False)
#    window['-RUN_SAUDIT-'].update(disabled=False)
    window['-DEBUG-'].update(disabled=False, value=False)
    window['-SCAN_TAUDIT-'].update(disabled=True)
#    window['-SCAN_SAUDIT-'].update(disabled=True)
    window['-UPLOAD-'].update(disabled=True)
    window['-NEXT-'].update(disabled=True)
    window['-DATE-'].update(value='')
    window['-BRANCH-'].update(value='')

    data = empty_data_table()
    for ttype in cnfg.transactions:
        window['-{}_TABLE-'.format(ttype.upper())].update(values=data)

    return(False)

def main():
    """
    Main function.
    """
    # Theme
    default_col = const.DEFAULT_COL
    action_col = const.ACTION_COL
    text_col = const.TEXT_COL
    inactive_col = const.BUTTON_COL

    sg.set_options(element_padding=(0, 0), margins=(0, 0), \
                   auto_size_buttons=True, auto_size_text=True, \
                   background_color=default_col, text_color=text_col, \
                   element_background_color=default_col, \
                   text_element_background_color=default_col, \
                   input_elements_background_color=action_col, \
                   button_color=(text_col, default_col))

    ## Test
    password = 'helloworld'
    username = 'chris'
    user_signedon = False
    user_group = 'admin'
    ##

    # Settings
    config = ProgramConfig()
    config.read()

#    auth_man = Authentication()
#    account = auth_man.login(username, password)

    layout = [get_toolbar(), get_panels(config)]

    # Initialize main window and login window
    window = sg.Window('REM Tila', layout, font=('Arial', 12), size=(1170, 840))
    win_size = window.GetScreenDimensions()
    print(win_size)
    window.finalize()
    print(window['-TOOLBAR-'].get_size())

    # Event modifiers
    audit_in_progress = False
    taudit_tx = 'Transaction Audit'
    saudit_tx = 'Validate Statements'
    report_tx = 'Summary Report'
    stats_tx = 'Summary Statistics'

    # Event Loop
    while True:
        event, values = window.read()
        print(event, values)
        if event == sg.WIN_CLOSED or values['-MMENU-'] == 'Quit':
            break

        # Cancel action - code block must remain on top
        if not audit_in_progress and event == '-CANCEL-':
            audit_in_progress = reset_to_default(window, config)

        if audit_in_progress and (event in ('-CANCEL-', '-DB-') or values['-AMENU-'] in (taudit_tx, saudit_tx) or values['-RMENU-'] in (report_tx, stats_tx)):
            msg = 'Audit is currently running. Are you sure you would like to exit?'
            selection = importer.confirm_action(msg)

            if selection == 'OK':
                # Reset to defaults
                audit_in_progress = reset_to_default(window, config)
                
        # Transaction Audit Panel
        if event == taudit_tx or values['-AMENU-'] == taudit_tx:
            window['-ACTIONS-'].update(visible=False)
            window['-TAUDIT-'].update(visible=True)

        # Statements Audit Panel
#        if event == saudit_tx or values['-AMENU-'] == saudit_tx:
#            window['-ACTIONS-'].update(visible=False)
#            window['-SAUDIT-'].update(visible=True)

        # Run transactions audit
        if event == '-RUN_TAUDIT-':
            if not values['-DATE-']:
                sg.popup_ok('Please select a date to audit', title='')
            elif not values['-BRANCH-']:
                sg.popup_ok('Please select a branch office to audit', title='')
            else:
                audit_in_progress = True
                date = values['-DATE-']

                # Enable / disable buttons
                window['-RUN_TAUDIT-'].update(disabled=True)
                window['-DEBUG-'].update(disabled=True)

                window['-SCAN_TAUDIT-'].update(disabled=False)
                if values['-DEBUG-']:
                    window['-UPLOAD-'].update(disabled=False)

                # Populate Table with data
                ttype = window['-TABS-'].get().strip('-')
                branch = values['-BRANCH-']
                df = initialize_table(ttype, date, branch)
                header = df.columns.values.tolist()
                data = df.values.tolist()
                print('Running {} transaction audit for branch office {} on date {}'.format(ttype, branch, date))
                window['-{}_TABLE-'.format(ttype)].update(values=data)

        # Run statements audit
#        if event == '-RUN_SAUDIT-':
#            pass

        # Scan for missing data
        if event == '-SCAN_TAUDIT-':
            # Check which tab is active
            ttype = window['-TABS-'].get().strip('-') 

            # Update buttons
            window['-NEXT-'].update(disabled=False)

            # Scan for missing transactions
            df = scan_for_missing(ttype, date)
            missing_data = importer.import_window(df)

        # Enable movement to the next tab
#        if event == '-NEXT-':
            # get next tab

    window.close()

if __name__ == "__main__":
    main()
    sys.exit(0)
