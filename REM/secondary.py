"""
REM secondary window functions, including popups, a window for importing 
missing data, the debugger, and the login window.
"""
import pandas as pd
import pyodbc
import PySimpleGUI as sg
import REM.authentication as auth
from REM.config import settings
import REM.layouts as lo
import REM.program_constants as const
import textwrap


# Popups
def popup_confirm(msg):
    """Display popup asking user if they would like to continue without 
    completing the current action.
    """
    font = const.MID_FONT
    return sg.popup_ok_cancel(textwrap.fill(msg, width=40), font=font, title='')


def popup_notice(msg):
    """
    Display popup notifying user that an action is required or couldn't
    be undertaken.
    """
    font = const.MID_FONT
    return sg.popup_ok(textwrap.fill(msg, width=40), font=font, title='')


def popup_error(msg):
    """
    Display popup notifying user that there is a fatal program error.
    """
    font = const.MID_FONT
    return sg.popup_error(textwrap.fill(msg, width=40), font=font, title='')


# Functions
def verify_row(self, row_index):
    """
    Add row to verified list, returning list of updated row colors.
    """
    tbl_bg_col = const.TBL_BG_COL
    tbl_alt_col = const.TBL_ALT_COL
    tbl_vfy_col = const.TBL_VFY_COL

    if row_index is not None and row_index not in self.verified:
        self.verified.append(row_index)  # add row to list of verified

    elif row_index is not None and row_index in self.verified:
        self.verified.remove(row_index)  # remove row from list of verified

    # Get row colors for rows that have been selected
    print('Selected orders are {}'.format(', '.join([str(i) for i in self.verified])))
    selected = [(i, tbl_vfy_col) for i in self.verified]

    # Get row colors for rows that have not been selected
    unselected = []
    for index in range(self.df.shape[0]):  # all rows in dataframe
        if index not in self.verified:
            if index % 2 == 0:
                color = tbl_bg_col
            else:
                color = tbl_alt_col

            unselected.append((index, color))

    # Update table row colors
    all_row_colors = selected + unselected

    return all_row_colors


# Windows
def debugger():
    """
    Display the debugger window.
    """
    # Window and element size parameters
    pad_frame = const.FRAME_PAD

    main_font = const.MAIN_FONT

    # GUI layout
    layout = [[sg.Output(key='-DEBUG-', size=(60, 20), pad=(pad_frame, pad_frame))]]

    window = sg.Window('Debug', layout, font=main_font, modal=False, resizable=True)

    return window


def login_window():
    """
    Display the login window.
    """
    # Window and element size parameters
    pad_frame = const.FRAME_PAD
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

    logo = settings.logo

    # GUI layout
    if logo:
        img_layout = [sg.Image(filename=logo, background_color=bg_col, pad=(pad_frame, (pad_frame, pad_el)))]
    else:
        img_layout = [sg.Text('', background_color=bg_col, pad=(pad_frame, (pad_frame, pad_el)))]

    column_layout = [img_layout,
                     [sg.Text('', pad=(pad_frame, pad_el), background_color=bg_col)],
                     [sg.Frame('', [[sg.Image(data=username_icon, background_color=input_col, pad=((pad_el, pad_h), 0)),
                                     sg.Input(default_text=_('username'), key='-USER-', size=(isize - 2, 1),
                                              pad=((0, 2), 0), text_color=help_col, border_width=0, do_not_clear=True,
                                              background_color=input_col, enable_events=True,
                                              tooltip=_('Input account username'))]],
                               background_color=input_col, pad=(pad_frame, pad_el), relief='sunken')],
                     [sg.Frame('', [[sg.Image(data=lock_icon, pad=((pad_el, pad_h), 0), background_color=input_col),
                                     sg.Input(default_text=_('password'), key='-PASSWORD-', size=(isize - 2, 1),
                                              pad=((0, 2), 0), password_char='*', text_color=help_col,
                                              background_color=input_col, border_width=0, do_not_clear=True,
                                              enable_events=True, tooltip=_('Input account password'))]],
                               background_color=input_col, pad=(pad_frame, pad_el), relief='sunken')],
                     [sg.Text('', key='-SUCCESS-', size=(20, 6), pad=(pad_frame, pad_frame), font=small_font,
                              justification='center', text_color='Red', background_color=bg_col)],
                     [sg.Button(_('Sign In'), key='-LOGIN-', size=(bsize, 1), pad=(pad_frame, pad_el), font=bold_text,
                                button_color=(text_col, login_col))],
                     [sg.Button(_('Cancel'), key='-CANCEL-', size=(bsize, 1), pad=(pad_frame, (pad_el, pad_frame)),
                                font=bold_text, button_color=(text_col, cancel_col))]]

    layout = [[sg.Col(column_layout, element_justification='center', justification='center', background_color=bg_col)]]

    account = auth.UserAccount()

    window = sg.Window('', layout, font=main_font, modal=True, keep_on_top=True, no_titlebar=True,
                       return_keyboard_events=True)
    window.finalize()
    window['-USER-'].update(select=True)
    window.refresh()

    return_keys = ('Return:36', '\r')

    #    pass_list = []
    # Event window
    while True:
        event, values = window.read()

        if event in (sg.WIN_CLOSED, '-CANCEL-'):  # selected close-window
            break

        if event == '-USER-':
            window['-USER-'].update(text_color=def_text_col)
            window['-SUCCESS-'].update(value='')

        if event == '-PASSWORD-':
            window['-PASSWORD-'].update(text_color=def_text_col)
            window['-SUCCESS-'].update(value='')
        #            value = values['-PASSWORD-']
        #            if value:
        #                if len(value) > len(pass_list):  #added character
        #                    pass_list.append(value[-1])
        #                    print('password is {}'.format(''.join(pass_list)))
        #                elif len(value) < len(pass_list):  #deleted character
        #                    pass_list = pass_list[0:-1]
        #                    print('password is {}'.format(''.join(pass_list)))

        #            window['-PASSWORD-'].update(value='*' * len(value), text_color=def_text_col)

        if event in return_keys:
            window['-LOGIN-'].Click()

        if event == '-LOGIN-':
            uname = values['-USER-']
            pwd = values['-PASSWORD-']

            # Verify values for username and password fields
            if not uname:
                msg = _('username is required')
                window['-SUCCESS-'].update(value=msg)
            elif not pwd:
                msg = _('password is required')
                window['-SUCCESS-'].update(value=msg)
            else:
                try:
                    login_success = account.login(uname, pwd)
                except pyodbc.Error as ex:
                    sqlstat = ex.args[1]
                    window['-SUCCESS-'].update(value=sqlstat)
                else:
                    if login_success:
                        print('Info: successfully logged in as {}'.format(uname))
                    break

    window.close()

    return account


def import_window(df, win_size: tuple = None):
    """
    Display the transaction importer window.
    """
    if win_size:
        width, height = [i * 0.8 for i in win_size]
    else:
        width, height = (const.WIN_WIDTH * 0.8, const.WIN_HEIGHT * 0.8)

    # Format dataframe as list for input into sg
    data = df.values.tolist()
    header = df.columns.values.tolist()
    all_rows = list(range(df.shape[0]))

    # Window and element size parameters
    font_h = const.HEADER_FONT
    main_font = const.MAIN_FONT

    pad_v = const.VERT_PAD
    pad_el = const.ELEM_PAD
    pad_frame = const.FRAME_PAD

    bg_col = const.ACTION_COL
    tbl_bg_col = const.TBL_BG_COL
    tbl_alt_col = const.TBL_ALT_COL
    tbl_vfy_col = const.TBL_VFY_COL

    # GUI layout
    bttn_layout = [[lo.B2(_('Cancel'), key='-CANCEL-', pad=(pad_el, 0), tooltip=_('Cancel import')),
                    lo.B2(_('Import'), bind_return_key=True, key='-IMPORT-', pad=(pad_el, 0),
                          tooltip=_('Import the selected transaction orders'))]]

    tbl_key = lo.as_key('Import Table')
    layout = [[sg.Col([[sg.Text(_('Import Missing Data'), font=font_h)]],
                      pad=(0, pad_v), justification='center')],
              [sg.Frame('', [[lo.create_table_layout(data, header, tbl_key, bind=True, height=height, width=width)]],
                        background_color=bg_col, element_justification='c', pad=(pad_frame, pad_frame))],
              [sg.Col(bttn_layout, justification='c', pad=(0, (0, pad_frame)))]]

    window = sg.Window(_('Import Data'), layout, font=main_font, modal=True, resizable=False)

    # Start event loop
    vfy_orders = []
    while True:
        event, values = window.read()

        if event in (sg.WIN_CLOSED, '-CANCEL-'):  # selected close-window or Cancel
            break

        if event == tbl_key:  # double-clicked on row in table
            try:
                row_index = int(values[tbl_key][0])
            except IndexError:  # empty table
                continue

            print('Info: Importer: row selected is {}'.format(row_index))

            if row_index is not None and row_index not in vfy_orders:
                vfy_orders.append(row_index)  # add row to list of verified

            elif row_index is not None and row_index in vfy_orders:
                vfy_orders.remove(row_index)  # remove row from list of verified

            # Get row colors for rows that have been selected
            print('Info: Importer: selected orders are {}'.format(', '.join([str(i) for i in vfy_orders])))
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
            continue

        if event == '-IMPORT-':  # click 'Import' button
            if len(data) != len(vfy_orders):  # not all orders selected
                msg = _("Not all rows have been selected importing. Are you sure you would like to continue?")
                selection = popup_confirm(msg)

                if selection == 'OK':  # continue anyway
                    break
                else:  # oops, a mistake was made
                    continue
            else:  # all transactions selected already
                break

    window.close()

    return vfy_orders


def edit_record(df, index, edit_cols, header_map: dict = {}, win_size: tuple = None):
    """
    Display window for user to modify the editable field in a record.
    """
    is_float_dtype = pd.api.types.is_float_dtype
    is_integer_dtype = pd.api.types.is_integer_dtype
    is_datetime_dtype = pd.api.types.is_datetime64_any_dtype
    is_bool_dtype = pd.api.types.is_bool_dtype

    if win_size:
        width, height = [i * 0.95 for i in win_size]
    else:
        width, height = (const.WIN_WIDTH * 0.95, const.WIN_HEIGHT * 0.95)

    # Format dataframe as list for input into sg
    row = df.iloc[index]
    data = row.tolist()
    print('data to modify {}'.format(data))
    print('dataframe has dtypes:')
    print(df.dtypes)
    header = df.columns.values.tolist()
    display_header = []
    for column in header:
        if column in header_map:
            mapped_column = header_map[column]
        else:
            mapped_column = column
        display_header.append(mapped_column)

    print('with header {}'.format(header))
    print('and display header {}'.format(display_header))

    edit_keys = {}
    edit_keys_mapped = {}
    for column in edit_cols:
        element_key = lo.as_key(column)
        edit_keys[column] = element_key

        try:
            edit_keys_mapped[header_map[column]] = element_key
        except KeyError:
            edit_keys_mapped[column] = element_key

    # Window and element size parameters
    main_font = const.MAIN_FONT

    pad_el = const.ELEM_PAD
    pad_frame = const.FRAME_PAD

    bg_col = const.ACTION_COL

    # GUI layout
    bttn_layout = [[lo.B2(_('Cancel'), key='-CANCEL-', pad=(pad_el, 0), tooltip=_('Cancel edit')),
                    lo.B2(_('Delete'), key='-DELETE-', pad=(pad_el, 0), tooltip=_('Permanently delete record')),
                    lo.B2(_('Save'), key='-SAVE-', bind_return_key=True, pad=(pad_el, 0),
                          tooltip=_('Save changes'))]]

    layout = [[sg.Col([[lo.create_etable_layout(data, display_header, edit_keys_mapped, height=height, width=width)]],
                      background_color=bg_col, element_justification='c', pad=(pad_frame, pad_frame))],
              [sg.Col(bttn_layout, justification='c', pad=(0, (0, pad_frame)))]]

    window = sg.Window(_('Modify Record'), layout, font=main_font, modal=True, resizable=False)
    window.finalize()

    # Start event loop
    while True:
        event, values = window.read()

        if event in (sg.WIN_CLOSED, '-CANCEL-'):  # selected close-window or Cancel
            break

        if event in (sg.WIN_CLOSED, '-DELETE-'):  # selected close-window or Cancel
            df.drop(index, axis=0, inplace=True)
            df.reset_index(drop=True, inplace=True)
            break

        if event == '-SAVE-':  # click 'Save' button
            for column in edit_keys:
                col_key = edit_keys[column]
                input_val = values[col_key]

                dtype = df[column].dtype
                if is_float_dtype(dtype):
                    try:
                        field_val = float(input_val)
                    except ValueError:
                        field_val = input_val
                elif is_integer_dtype(dtype):
                    try:
                        field_val = int(input_val)
                    except ValueError:
                        field_val = input_val
                elif is_bool_dtype(dtype):
                    try:
                        field_val = bool(input_val)
                    except ValueError:
                        field_val = input_val
                elif is_datetime_dtype(dtype):
                    try:
                        field_val = pd.to_datetime(input_val, format=settings.format_date_str(), errors='coerce')
                    except ValueError:
                        field_val = input_val
                else:
                    field_val = input_val

                # Replace field value with modified value
                df.at[index, column] = field_val

            break

    window.close()

    return df


def add_record(df, index, edit_cols, header_map: dict = {}, win_size: tuple = None):
    """
    Display window for user to add new record.
    """
    is_float_dtype = pd.api.types.is_float_dtype
    is_integer_dtype = pd.api.types.is_integer_dtype
    is_datetime_dtype = pd.api.types.is_datetime64_any_dtype
    is_bool_dtype = pd.api.types.is_bool_dtype

    if win_size:
        width, height = [i * 0.95 for i in win_size]
    else:
        width, height = (const.WIN_WIDTH * 0.95, const.WIN_HEIGHT * 0.95)

    # Format dataframe as list for input into sg
    row = df.iloc[index]
    data = row.tolist()
    print('data to modify {}'.format(data))
    header = df.columns.values.tolist()
    display_header = []
    for column in header:
        if column in header_map:
            mapped_column = header_map[column]
        else:
            mapped_column = column
        display_header.append(mapped_column)

    print('with header {}'.format(header))
    print('and display header {}'.format(display_header))

    edit_keys = {}
    edit_keys_mapped = {}
    for column in edit_cols:
        element_key = lo.as_key(column)
        edit_keys[column] = element_key

        try:
            edit_keys_mapped[header_map[column]] = element_key
        except KeyError:
            edit_keys_mapped[column] = element_key

    # Window and element size parameters
    main_font = const.MAIN_FONT

    pad_el = const.ELEM_PAD
    pad_frame = const.FRAME_PAD

    bg_col = const.ACTION_COL

    # GUI layout
    bttn_layout = [[lo.B2(_('Cancel'), key='-CANCEL-', pad=(pad_el, 0), tooltip=_('Cancel adding new record')),
                    lo.B2(_('Save'), key='-SAVE-', bind_return_key=True, pad=(pad_el, 0),
                          tooltip=_('Save new record'))]]

    layout = [[sg.Col([[lo.create_etable_layout(data, display_header, edit_keys_mapped, height=height, width=width)]],
                      background_color=bg_col, element_justification='c', pad=(pad_frame, pad_frame))],
              [sg.Col(bttn_layout, justification='c', pad=(0, (0, pad_frame)))]]

    window = sg.Window(_('Modify Record'), layout, font=main_font, modal=True, resizable=False)
    window.finalize()

    # Start event loop
    while True:
        event, values = window.read()

        if event in (sg.WIN_CLOSED, '-CANCEL-'):  # selected close-window or Cancel
            df.drop(index, axis=0, inplace=True)
            df.reset_index(drop=True, inplace=True)
            break

        if event == '-SAVE-':  # click 'Save' button
            col_key = edit_keys[column]
            input_val = values[col_key]

            dtype = df[column].dtype
            if is_float_dtype(dtype):
                try:
                    field_val = float(input_val)
                except ValueError:
                    field_val = input_val
            elif is_integer_dtype(dtype):
                try:
                    field_val = int(input_val)
                except ValueError:
                    field_val = input_val
            elif is_bool_dtype(dtype):
                try:
                    field_val = bool(input_val)
                except ValueError:
                    field_val = input_val
            elif is_datetime_dtype(dtype):
                try:
                    field_val = pd.to_datetime(input_val, format=settings.format_date_str(), errors='coerce')
                except ValueError:
                    field_val = input_val
            else:
                field_val = input_val

            # Replace field value with modified value
            df.at[index, column] = field_val

            break

    window.close()

    return df
