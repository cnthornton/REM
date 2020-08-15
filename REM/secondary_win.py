"""
REM secondary window functions, including popups, a window for importing 
missing data, the debugger, and the login window.
"""
import pandas as pd
import PySimpleGUI as sg
import REM.authentication as auth
import REM.layouts as lo
import REM.program_settings as const
import textwrap


# Popups
def confirm_action(msg):
    """Display popup asking user if they would like to continue without 
    completing the current action.
    """
    return(sg.popup_ok_cancel(textwrap.fill(msg, width=40), title=''))

def selection_reqd(msg):
    """
    Display popup asking user to make a required selection
    """
    return(sg.popup_ok(textwrap.fill(msg, width=40), title=''))

# Windows
def debugger(win_size:tuple=(1920, 1080)):
    """
    Display the debugger window.
    """
    # Window and element size parameters
    pad_frame = const.FRAME_PAD

    main_font = const.MAIN_FONT
    
    # GUI layout
    layout = [[sg.Output(size=(60, 20), pad=(pad_frame, pad_frame))]]

    window = sg.Window('Debug', layout, font=main_font, modal=False)

    return(window)

def login_window(cnfg, win_size:tuple=(1920, 1080)):
    """
    Display the login window.
    """
    # Window and element size parameters
    pad_frame = const.FRAME_PAD
    pad_v = const.VERT_PAD
    pad_h = const.HORZ_PAD
    pad_el = const.ELEM_PAD

    bg_col = const.ACTION_COL
    input_col = const.DEFAULT_COL
    login_col = const.LOGIN_BUTTON_COL
    cancel_col = const.CANCEL_BUTTON_COL
    def_text_col = const.TEXT_COL
    text_col = const.WHITE_TEXT_COL
    help_col = const.HELP_TEXT_COL
    bold_text = const.BOLD_FONT

    lock_icon = const.LOCK_ICON
    username_icon = const.USERNAME_ICON

    isize = const.IN1_SIZE
    bsize = const.B1_SIZE

    main_font = const.MAIN_FONT
    small_font = const.SMALL_FONT

    # GUI layout
    column_layout = [[sg.Image(filename=cnfg.logo, background_color=bg_col, 
                        pad=(pad_frame, (pad_frame, pad_el)))],
                     [sg.Text('', pad=(pad_frame, pad_el), background_color=bg_col)],
                     [sg.Frame('', [[sg.Image(data=username_icon, 
                                       background_color=input_col, 
                                       pad=((pad_el, pad_h), 0)), 
                                     sg.Input(default_text='username', 
                                       key='-USER-', size=(isize - 2, 1), 
                                       text_color=help_col,
                                       border_width=0, do_not_clear=True,
                                       background_color=input_col, 
                                       enable_events=True,
                                       pad=((0, 2), 0),
                                       tooltip='Input account username')]], 
                        background_color=input_col, pad=(pad_frame, pad_el),
                        relief='sunken')], 
                     [sg.Frame('', [[sg.Image(data=lock_icon, 
                                       background_color=input_col, 
                                       pad=((pad_el, pad_h), 0)), 
                                     sg.Input(default_text='password', 
                                       key='-PASSWORD-', size=(isize - 2, 1), 
                                       text_color=help_col,
                                       border_width=0, do_not_clear=True,
                                       background_color=input_col,
                                       enable_events=True,
                                       pad=((0, 2), 0), password_char='*',
                                       tooltip='Input account password')]], 
                        background_color=input_col, pad=(pad_frame, pad_el), 
                        relief='sunken')],
                     [sg.Text('', key='-SUCCESS-', size=(20, 2), 
                        pad=(pad_frame, pad_frame), font=small_font,
                        justification='center',
                        text_color='Red', background_color=bg_col)],
                     [sg.Button('Sign In', size=(bsize, 1), 
                        pad=(pad_frame, pad_el), font=bold_text, 
                        button_color=(text_col, login_col))],
                     [sg.Button('Cancel', size=(bsize, 1), 
                        pad=(pad_frame, (pad_el, pad_frame)), font=bold_text, button_color=(text_col, cancel_col))]]

    layout = [[sg.Col(column_layout, element_justification='center', 
                 justification='center', background_color=bg_col)]]

    auth_man = auth.AuthenticationManager()
    account = None

    window = sg.Window('', layout, font=main_font, modal=True, keep_on_top=True, no_titlebar=True)
    window.finalize()
    window['-USER-'].update(select=True)
    window.refresh()

#    pass_list = []
    # Event window
    while True:
        event, values = window.read()
        print(event, values)

        if event in (sg.WIN_CLOSED, 'Cancel'):  #selected close-window
            break

        if event == '-USER-':
            window['-USER-'].update(text_color=def_text_col)
            window['-SUCCESS-'].update(value='')

        if event == '-PASSWORD-':
            window['-PASSWORD-'].update(text_color=def_text_col)
            window['-SUCCESS-'].update(value='')
            print('password is {}'.format(values['-PASSWORD-']))
#            value = values['-PASSWORD-']
#            if value:
#                if len(value) > len(pass_list):  #added character
#                    pass_list.append(value[-1])
#                    print('password is {}'.format(''.join(pass_list)))
#                elif len(value) < len(pass_list):  #deleted character
#                    pass_list = pass_list[0:-1]
#                    print('password is {}'.format(''.join(pass_list)))

#            window['-PASSWORD-'].update(value='*' * len(value), text_color=def_text_col)

        if event == 'Sign In':
            uname = values['-USER-']
#            pwd = ''.join(pass_list)
            pwd = values['-PASSWORD-']
            # Verify values for username and password fields
            if not uname:
                msg = 'username is required'
                window['-SUCCESS-'].update(value=msg)
            elif not pwd:
                msg = 'password is required'
                window['-SUCCESS-'].update(value=msg)
            else:
                try:
                    account = auth_man.login(uname, pwd)
                except auth.PasswordMismatch:
                    msg = 'incorrect password provided'
                    window['-SUCCESS-'].update(value=msg)
                except auth.UserNotFound:
                    msg = 'unknown username {}'.format(uname)
                    window['-SUCCESS-'].update(value=msg)
                else:
                    break

    window.close()

    return(account)

def import_window(df, db, db_params, win_size:tuple=(1920, 1080)):
    """
    Display the transaction importer window.
    """
    # Format dataframe as list for input into sg
    data = df.values.tolist()
    header = df.columns.values.tolist()

    db_key = db_params['key']
    key_index = header.index(db_key)

    # Transaction information
    row_keys = [data[key_index] for i in data]
    all_rows = list(range(df.shape[0]))

    # Window and element size parameters
    font_h = const.HEADER_FONT
    main_font = const.MAIN_FONT

    pad_v = const.VERT_PAD
    pad_h = const.HORZ_PAD
    pad_el = const.ELEM_PAD
    pad_frame = const.FRAME_PAD

    bg_col = const.ACTION_COL
    tbl_bg_col = const.TBL_BG_COL
    tbl_alt_col = const.TBL_ALT_COL
    tbl_vfy_col = const.TBL_VFY_COL

    # GUI layout
    bttn_layout = [[lo.B2('Cancel', tooltip='Cancel import', 
                      pad=(pad_el, pad_v)), 
                    lo.B2('Import', bind_return_key=True, key='-IMPORT-',
                      tooltip='Import the selected transaction orders', 
                      pad=(pad_el, pad_v))]]

    tbl_key = lo.as_key('Import Table')
    layout = [[sg.Col([[sg.Text('Import Missing Data', font=font_h)]], 
                 pad=(0, pad_v), justification='center')],
              [sg.Frame('', [[lo.create_table(data, header, tbl_key, bind=True)], 
                         [sg.Text('Include order:', pad=(pad_el, pad_v),
                            background_color=bg_col,
                            tooltip='Input order number to add the order to the table'),
                          sg.Input('', key='-INPUT-', pad=(pad_el, pad_v)),
                          lo.B2('Add', pad=(pad_el, pad_v), 
                            tooltip='Add order to the table', key='-ADD-')]], 
                 background_color=bg_col, element_justification='c', pad=(pad_frame, pad_v))],
              [sg.Col(bttn_layout, justification='right', 
                 pad=((0, pad_frame), pad_v))]]

    window = sg.Window('Import Data', layout, font=main_font, modal=True)

    # Start event loop
    vfy_orders = []
    while True:
        event, values = window.read()
        print(event, values)

        if event in (sg.WIN_CLOSED, 'Cancel'):  #selected close-window or Cancel
            break

        if event == tbl_key:  #double-clicked on row in table
            row_index = int(values[tbl_key][0])
            print('Row selected is {}'.format(row_index))

            if row_index != None and row_index not in vfy_orders:
                vfy_orders.append(row_index)  #add row to list of verified

            elif row_index != None and row_index in vfy_orders:
                vfy_orders.remove(row_index)  #remove row from list of verified

            # Get row colors for rows that have been selected
            print('Selected orders are {}'.format(', '.join([str(i) for i in vfy_orders])))
            selected = [(i, tbl_vfy_col) for i in vfy_orders]

            # Get row colors for rows that have not been selected
            unselected = []
            for index in all_rows:
                if index not in vfy_orders: 
                    if index % 2 == 0:
                        color = tbl_bg_col
                    else:
                        color = tbl_alt_col
                    unselected.append((index, color))

            # Update table row colors
            all_row_colors = selected + unselected
            window[tbl_key].update(row_colors=all_row_colors)
            window.Refresh()

            row_index = None
            continue

        if event == '-ADD-':  #clicked the 'Add' button
            # Extract order information from database
            new_order = values['-INPUT-']
            if not new_order in row_keys:
                filter_rules = [(db_key, '=', new_order)]
                order_info = db.query(db_params, filter_rules)
            else:
                print('Order already in table')
                continue

            if not order_info:  #query returned nothing
                print("{} is not a valid order number".format(new_order))
                continue

            # Clear user input from Input element
            window['-INPUT-'].update(value='')

            # Add order information to table and checkbox column
            order_nums.append(new_order)
            data.append(order_info)
            window[tbl_key].update(values=data)

        if event == '-IMPORT-':  #click 'Import' button
            if len(data) != len(vfy_orders):  #not all orders selected
                selection = confirm_action("Not all rows have been selected "
                    "importing. Are you sure you would like to continue?")
                if selection == 'OK':  #continue anyway
                    break
                else:  #oops, a mistake was made
                    continue
            else:  #all orders selected already
                break

    window.close()

    vfy_data = [data[i] for i in vfy_orders]

    return(pd.DataFrame(vfy_data, columns=header))
