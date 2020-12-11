"""
REM secondary window functions, including popups, a window for importing 
missing data, the debugger, and the login window.
"""
import datetime
import dateutil
import gc
import numpy as np
import pandas as pd
import pyodbc
import PySimpleGUI as sg
import REM.authentication as auth
from REM.config import settings
import REM.constants as const
import REM.data_manipulation as dm
import REM.layouts as lo
from REM.main import __version__
import math
import sys
import textwrap
import time


# Popups
def popup_confirm(msg):
    """Display popup asking user if they would like to continue without completing the current action.
    """
    font = const.MID_FONT
    return sg.popup_ok_cancel(textwrap.fill(msg, width=40), font=font, title='')


def popup_notice(msg):
    """
    Display popup notifying user that an action is required or couldn't be undertaken.
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
    input_col = const.INPUT_COL
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
                                     sg.Input(default_text=settings.username, key='-USER-', size=(isize - 2, 1),
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
                except pyodbc.Error as e:
                    sqlstat = e.args[1]
                    window['-SUCCESS-'].update(value=sqlstat)
                    print(e)
                else:
                    if login_success:
                        print('Info: successfully logged in as {}'.format(uname))
                    break

    window.close()
    layout = None
    window = None
    gc.collect()

    return account


def account_record_window(record):
    """
    Display the account record window.
    """
    # GUI layout
    layout = record.layout(editable=True, markable=True)
    if not layout:
        return False

    window = sg.Window('Database Record', layout, modal=True, keep_on_top=False, return_keyboard_events=True)
    window.finalize()

    note_param = record.fetch_parameter(record.required_parameters['Note'])
    note_key = note_param.element_key
    window[note_key].expand(expand_x=True)

    cancel_key = record.key_lookup('Cancel')
    save_key = record.key_lookup('Save')
    delete_key = record.key_lookup('Delete')
    # Event window
    user_action = 'cancel'
    while True:
        event, values = window.read()

        if event in (sg.WIN_CLOSED, cancel_key):  # selected close-window
            break

        if event == delete_key:
            user_action = 'delete'
            break

        if event == save_key:
            # Update parameter values
            for param in record.parameters:
                param.set_value(values)
                print(param.name, param.value)

            # Save updated parameters to the database
            user_action = 'save'
            break

    window.close()
    layout = None
    window = None
    gc.collect()

    return user_action


def notes_window(docno, note, record='DocNo', title='Note'):
    """
    Display the note-taking window.
    """
    # Window and element size parameters
    pad_frame = const.FRAME_PAD
    pad_v = const.VERT_PAD
    pad_el = const.ELEM_PAD

    bg_col = const.ACTION_COL
    default_col = const.DEFAULT_COL
    input_col = const.INPUT_COL
    text_col = const.TEXT_COL
    header_col = const.HEADER_COL

    main_font = const.MAIN_FONT
    header_font = const.HEADER_FONT
    bold_font = const.BOLD_MID_FONT

    width = 80
    height = 20

    # GUI layout
    title_layout = [[sg.Canvas(size=(0, 1), pad=(0, pad_v), visible=True, background_color=header_col)],
                    [sg.Text('Add Note to Record', pad=((pad_frame, 0), (0, pad_v)), font=header_font,
                             background_color=header_col)]]

    header_layout = [
        [sg.Text('{}:'.format(record), pad=((pad_el*2, pad_el), pad_el*2), font=bold_font, background_color=bg_col),
         sg.Text(docno, size=(12, 1), pad=((pad_el, pad_el*2), pad_el*2), justification='l', font=main_font,
                 background_color=bg_col, auto_size_text=True, border_width=0)]]

    note_layout = [[sg.Text('{}:'.format(title), pad=(0, (0, pad_el)), background_color=bg_col, font=bold_font)],
                   [sg.Multiline(default_text=note, key='-NOTE-', size=(width, height), pad=(0, 0),
                                 background_color=bg_col, text_color=text_col, border_width=1, focus=False)]]

    main_layout = [[sg.Frame('', header_layout, pad=(pad_frame, pad_frame), background_color=header_col,
                             border_width=1, relief='raised')],
                   [sg.Col(note_layout, pad=(pad_frame, (0, pad_frame)), background_color=input_col, justification='l')]]

    bttn_layout = [[lo.B2('Cancel', key='-CANCEL-', pad=((0, pad_el), 0), tooltip='Cancel'),
                    lo.B2('Save', key='-SAVE-', pad=((pad_el, 0), 0), tooltip='Save note')]]

    layout = [[sg.Col(title_layout, pad=(0, 0), justification='l', background_color=header_col, expand_x=True)],
              [sg.Frame('', main_layout, pad=(pad_frame, 0), background_color=bg_col)],
              [sg.Col(bttn_layout, pad=(0, (pad_v, pad_frame)), background_color=default_col, justification='c')]]

    window = sg.Window('', layout, font=main_font, modal=True, keep_on_top=True, return_keyboard_events=True)
    window.finalize()

    # Event window
    while True:
        event, values = window.read()

        if event in (sg.WIN_CLOSED, '-CANCEL-'):  # selected close-window
            break

        if event == '-SAVE-':
            note = values['-NOTE-']
            break

    window.close()
    layout = None
    window = None
    gc.collect()

    return note


def database_importer_window(user):
    """
    Display the database importer window.
    """
    # Window and element size parameters
    main_font = const.MAIN_FONT

    text_col = const.TEXT_COL
    select_col = const.SELECT_TEXT_COL

    width = 1200
    height = 800

    try:
        tables = [i.table_name for i in user.database_tables(settings.prog_db)]
    except ValueError:
        tables = []

    layout = lo.importer_layout(tables, win_size=(width, height))

    window = sg.Window(_('Import into Database'), layout, font=main_font, size=(width, height), modal=True)
    window.finalize()

    panel_keys = {0: '-P1-', 1: '-P2-', 2: '-P3-'}
    panel_names = {0: '-PN1-', 1: '-PN2-', 2: '-PN3-'}
    current_panel = 0
    first_panel = 0
    last_panel = 2

    req_df = pd.DataFrame(columns=['Table Column Name', 'Data Type', 'Default Value'])
    map_df = pd.DataFrame(columns=['Table Column Name', 'Data Type', 'File Column Name'])

    table = None
    listbox_values = []

    # Start event loop
    while True:
        event, values = window.read(timeout=500)

        if event in (sg.WIN_CLOSED, '-CANCEL-'):  # selected close-window or Cancel
            break

        # Enable next button when a file is selected
        infile = values['-FILE-']

        # Make sure the flow control buttons enabled
        if current_panel != last_panel:
            window['-NEXT-'].update(disabled=False)

        # Move to next panel
        if event == '-NEXT-':
            next_panel = current_panel + 1

            # Verify that required fields have values
            if not infile:
                popup_notice('Please select an input file')
                continue
            else:
                skiptop = values['-TSKIP-']
                skipbottom = values['-BSKIP-']
                try:
                    skiptop = int(skiptop)
                    skipbottom = int(skipbottom)
                except ValueError:
                    popup_notice('Only integer values allowed when indicating number of rows to skip')
                    continue

                header_row = values['-HROW-']
                try:
                    header_row = int(header_row)
                except ValueError:
                    popup_notice('Header row must be an integer value')
                    continue

                thousands_sep = values['-TSEP-']
                if len(thousands_sep) > 1:
                    popup_notice('Unsupported character provided as the thousands separator')
                    continue

            # Populate Preview table with top 20 values from spreadsheet
            if next_panel == last_panel:
                if table is None:
                    popup_notice('Please select a valid table from the "Table" dropdown')
                    continue
                else:
                    file_format = values['-FORMAT-']

                    # Import spreadsheet into dataframe
                    if file_format == 'xls':
                        formatting_options = {'parse_dates': values['-DATES-'], 'convert_float': values['-INTS-'],
                                              'skiprows': skiptop, 'skipfooter': skipbottom, 'header': header_row,
                                              'thousands': thousands_sep}
                        reader = pd.read_excel
                    else:
                        formatting_options = {'parse_dates': values['-DATES-'], 'sep': values['-FSEP-'],
                                              'lineterminator': values['-NSEP-'], 'skiprows': skiptop,
                                              'skipfooter': skipbottom, 'header': header_row,
                                              'thousands': thousands_sep, 'encoding': 'utf-8', 'error_bad_lines': False,
                                              'skip_blank_lines': True}
                        reader = pd.read_csv

                    import_df = reader(infile, **formatting_options)

                    # Rename columns based on mapping information
                    col_mapper = pd.Series(map_df['Table Column Name'].values,
                                           index=map_df['File Column Name']).to_dict()
                    import_df.rename(col_mapper, axis=1, inplace=True)

                    for index, row in req_df.iterrows():
                        column_name = row['Table Column Name']
                        column_value = row['Default Value']
                        import_df[column_name] = column_value

                    all_cols = req_df['Table Column Name'].append(map_df['Table Column Name'], ignore_index=True)
                    try:
                        final_df = import_df[all_cols]
                    except KeyError:
                        popup_notice('Please verify that column names are mapped correctly')
                        continue

                    # Populate preview with table values
                    col_widths = dm.calc_column_widths(all_cols, width=width * 0.77, pixels=True)
                    window['-PREVIEW-'].Widget['columns'] = tuple(all_cols.values.tolist())
                    window['-PREVIEW-'].Widget['displaycolumns'] = '#all'
                    for index, column_name in enumerate(all_cols):
                        col_width = col_widths[index]
                        window['-PREVIEW-'].Widget.column(index, width=col_width)
                        window['-PREVIEW-'].Widget.heading(index, text=column_name)

                    window['-PREVIEW-'].update(values=final_df.head(n=20).values.tolist())

                    # Enable import button
                    window['-IMPORT-'].update(disabled=False)

            # Enable /disable panels
            window[panel_keys[current_panel]].update(visible=False)
            window[panel_keys[next_panel]].update(visible=True)

            # Change high-lighted flow control text
            window[panel_names[current_panel]].update(text_color=text_col)
            window[panel_names[next_panel]].update(text_color=select_col)

            # Disable next button if next panel is last panel
            if next_panel == last_panel:
                window['-NEXT-'].update(disabled=True)

            # Enable back button if not on first panel
            if next_panel != first_panel:
                window['-BACK-'].update(disabled=False)

            # Reset current panel variable
            current_panel = next_panel
            continue

        # Enable / disable formatting fields
        file_format = values['-FORMAT-'].strip()
        if file_format != 'xls':
            window['-NSEP-'].update(disabled=False)
            window['-FSEP-'].update(disabled=False)
        else:
            window['-NSEP-'].update(disabled=True)
            window['-FSEP-'].update(disabled=True)

        # Move to previous panel
        if event == '-BACK-':
            prev_panel = current_panel - 1

            # Enable /disable panels
            window[panel_keys[current_panel]].update(visible=False)
            window[panel_keys[prev_panel]].update(visible=True)

            # Change high-lighted flow control text
            window[panel_names[current_panel]].update(text_color=text_col)
            window[panel_names[prev_panel]].update(text_color=select_col)

            # Disable back button if on first panel
            if prev_panel == first_panel:
                window['-BACK-'].update(disabled=True)

            # Disable import button if not on last panel
            if prev_panel != last_panel:
                window['-IMPORT-'].update(disabled=True)

            # Reset current panel variable
            current_panel = prev_panel
            continue

        # Populate database table tables based on table selection
        if event == '-TABLE-':
            table = values['-TABLE-']
            columns = {i.column_name: (i.type_name, i.column_size) for i in
                       user.table_schema(settings.prog_db, table)}

            listbox_values = list(columns.keys())

            # Reset columns displayed in the listboxes
            window['-REQLIST-'].update(values=listbox_values)
            window['-MAPLIST-'].update(values=listbox_values)

            # Reset the tables
            req_df.drop(req_df.index, inplace=True)
            map_df.drop(map_df.index, inplace=True)

            window['-REQCOL-'].update(values=req_df.values.tolist())
            window['-MAPCOL-'].update(values=map_df.values.tolist())
            continue

        # Populate tables with columns selected from the list-boxes
        if event == '-REQLIST-' and table is not None:
            # Get index of column in listbox values
            try:
                column = values['-REQLIST-'][0]
            except IndexError:
                continue

            # Add column to required columns dataframe
            req_df.loc[len(req_df.index)] = [column, '{TYPE} ({SIZE})'.format(TYPE=columns[column][0].upper(),
                                                                              SIZE=columns[column][1]), '']
            window['-REQCOL-'].update(values=req_df.values.tolist())

            # Remove column from listbox list
            listbox_values.remove(column)

            window['-REQLIST-'].update(values=listbox_values)
            window['-MAPLIST-'].update(values=listbox_values)
            continue

        if event == '-MAPLIST-' and table is not None:
            # Get index of column in listbox values
            try:
                column = values['-MAPLIST-'][0]
            except IndexError:
                continue

            # Add column to mapping columns dataframe
            map_df.loc[len(map_df.index)] = [column, '{TYPE} ({SIZE})'.format(TYPE=columns[column][0].upper(),
                                                                              SIZE=columns[column][1]), '']
            window['-MAPCOL-'].update(values=map_df.values.tolist())

            # Remove column from listbox list
            listbox_values.remove(column)

            window['-REQLIST-'].update(values=listbox_values)
            window['-MAPLIST-'].update(values=listbox_values)
            continue

        # Edit table row
        if event == '-REQCOL-' and table is not None:
            try:
                col_index = values['-REQCOL-'][0]
            except IndexError:
                continue

            # Find datatype of selected column
            col_name = req_df.at[col_index, 'Table Column Name']
            dtype = columns[col_name][0]

            # Modify table row
            req_df = modify_record(req_df, col_index, {'Default Value': {'ElementType': dtype}})
            window['-REQCOL-'].update(values=req_df.values.tolist())

            # Return column to listbox if row is deleted
            if col_name not in req_df['Table Column Name'].tolist():
                if col_name not in listbox_values:
                    listbox_values.append(col_name)
                window['-REQLIST-'].update(values=listbox_values)
                window['-MAPLIST-'].update(values=listbox_values)

            continue

        if event == '-MAPCOL-' and table is not None:
            try:
                col_index = values['-MAPCOL-'][0]
            except IndexError:
                continue

            col_name = map_df.at[col_index, 'Table Column Name']

            # Modify table row
            map_df = modify_record(map_df, col_index, {'File Column Name': {'ElementType': 'string'}})
            window['-MAPCOL-'].update(values=map_df.values.tolist())

            # Return column to listbox if row is deleted
            if col_name not in map_df['Table Column Name'].tolist():
                if col_name not in listbox_values:
                    listbox_values.append(col_name)
                window['-REQLIST-'].update(values=listbox_values)
                window['-MAPLIST-'].update(values=listbox_values)

            continue

    window.close()
    layout = None
    window = None
    gc.collect()

    return True


def associate_data(to_df, from_df, pkey, column_map: dict = None, to_title: str = None, from_title: str = None):
    """
    Associate data from one table with data in another table.
    """
    width = const.WIN_WIDTH - 40

    to_title = 'Collection' if to_title is None else to_title
    from_title = 'Source' if from_title is None else from_title

    column_map = column_map if column_map is not None else {i: i for i in to_df.columns.values.tolist()}
    column_header = list(column_map.values())

    to_df = to_df.copy()
    from_df = from_df.copy()

    to_df.rename(columns=column_map, inplace=True)
    from_df.rename(columns=column_map, inplace=True)

    # Window and element size parameters
    pad_frame = const.FRAME_PAD
    pad_v = const.VERT_PAD
    pad_el = const.ELEM_PAD

    bg_col = const.ACTION_COL
    header_col = const.HEADER_COL

    main_font = const.MAIN_FONT
    header_font = const.HEADER_FONT

    # Layout
    title_layout = [[sg.Canvas(size=(0, 1), pad=(0, pad_v), visible=True, background_color=header_col)],
                    [sg.Text('Associate Data Records', pad=((pad_frame, 0), (0, pad_v)), font=header_font,
                             background_color=header_col)]]

    main_layout = [[lo.create_table_layout(dm.format_display_table(from_df, column_map).values.tolist(),
                                           column_header, '-FROM-', events=True,
                                           tooltip='Double-click row to add row to the collection', nrow=10,
                                           width=int(width / 2), font=main_font, pad=(pad_frame, pad_frame),
                                           table_name=from_title),
                    lo.create_table_layout(dm.format_display_table(to_df, column_map).values.tolist(), column_header,
                                           '-TO-', events=True,
                                           tooltip='Double-click row to remove row from the collection', nrow=10,
                                           width=int(width / 2), font=main_font, pad=(pad_frame, pad_frame),
                                           table_name=to_title)]]

    bttn_layout = [[sg.Col([[lo.B2('Cancel', key='-CANCEL-', disabled=False, tooltip='Cancel selections')]],
                           pad=(0, 0), justification='l', expand_x=True),
                    sg.Col([[sg.Canvas(size=(0, 0), visible=True)]], justification='c', expand_x=True),
                    sg.Col([[lo.B2('Save', key='-SAVE-', pad=((0, pad_el), 0), tooltip='Save selections')]],
                           pad=(0, 0), justification='r')]]

    layout = [[sg.Col(title_layout, pad=(0, 0), justification='l', background_color=header_col, expand_x=True)],
              [sg.Col(main_layout, pad=(pad_frame, 0), background_color=bg_col, justification='c')],
              [sg.Col(bttn_layout, pad=(pad_frame, (pad_v, pad_frame)), expand_x=True)]]

    window = sg.Window('', layout, modal=False, resizable=False)

    select_rows = to_df[column_map[pkey]].tolist()
    while True:
        event, values = window.read(close=False)

        if event in (sg.WIN_CLOSED, '-CANCEL-'):  # selected close-window or Cancel
            select_rows = []
            break

        if event == '-FROM-':  # click to add row to collection
            row_index = values['-FROM-'][0]

            # Add row ID to list of selected rows
            row_id = from_df.at[row_index, column_map[pkey]]
            select_rows.append(row_id)

            # Add row to collection
            to_df = to_df.append(from_df.iloc[row_index], ignore_index=True)
            to_df.reset_index(drop=True, inplace=True)

            # Remove row from source
            from_df.drop(row_index, axis=0, inplace=True)
            from_df.reset_index(drop=True, inplace=True)

            # Update display tables
            window['-FROM-'].update(values=dm.format_display_table(from_df, column_map).values.tolist())
            window['-TO-'].update(values=dm.format_display_table(to_df, column_map).values.tolist())

            continue

        if event == '-TO-':  # click to remove row from collection
            row_index = values['-TO-'][0]

            # Remove row ID from list of selected rows
            row_id = to_df.at[row_index, column_map[pkey]]
            try:
                select_rows.remove(row_id)
            except ValueError:
                continue

            # Add row to source
            from_df = from_df.append(to_df.iloc[row_index], ignore_index=True)
            from_df.reset_index(drop=True, inplace=True)

            # Remove row from collection
            to_df.drop(row_index, axis=0, inplace=True)
            to_df.reset_index(drop=True, inplace=True)

            print(to_df.dtypes)

            # Update display tables
            window['-FROM-'].update(values=dm.format_display_table(from_df, column_map).values.tolist())
            window['-TO-'].update(values=dm.format_display_table(to_df, column_map).values.tolist())

            continue

        if event == '-SAVE-':  # click 'Save' button
            # Add selected rows to the to_df
            break

    window.close()
    layout = None
    window = None
    gc.collect()

    return select_rows


def data_import_window(df, parameters, header_map: dict = None, aliases: dict = None, create_new: bool = False):
    """
    Display the import from database window.
    """
    relativedelta = dateutil.relativedelta.relativedelta
    strptime = datetime.datetime.strptime
    is_float_dtype = pd.api.types.is_float_dtype
    is_datetime_dtype = pd.api.types.is_datetime64_any_dtype

    date_fmt = settings.format_date_str(date_str=settings.display_date_format)
    date_offset = settings.get_date_offset()

    display_df = df.copy()
    header = display_df.columns.values.tolist()

    if header_map is None:
        header_map = {i: i for i in header}

    display_header = []
    display_indices = []
    for column_index, column in enumerate(header):
        try:
            display_header.append(header_map[column])
        except KeyError:
            print('Configuration Warning: display column {COL} not found in configured table columns'
                  .format(COL=column))
        else:
            display_indices.append(column_index)

    # Filter data by default parameters
    filter_params = []
    for param in parameters:
        filter_params.append(param.element_key)

        param_value = param.value
        if param_value:
            try:
                display_df = display_df[display_df[param.name] == param_value]
            except KeyError:
                print('Configuration Warning: parameter {PARAM} not found in imported table'.format(PARAM=param.name))
                continue

    # Map column values to the aliases specified in the configuration
    for alias_col in aliases:
        alias_map = aliases[alias_col]  # dictionary of mapped values

        if alias_col not in header:
            continue
        else:
            display_df[alias_col].replace(alias_map, inplace=True)

    for column in display_df.columns:
        column_values = display_df[column]
        dtype = column_values.dtype
        if is_float_dtype(dtype):
            column_values = column_values.apply('{:,.2f}'.format)
        elif is_datetime_dtype(dtype):
            column_values = column_values.apply(lambda x: (strptime(x.strftime(date_fmt), date_fmt) +
                                                         relativedelta(years=+date_offset)).strftime(date_fmt)
                if pd.notnull(x) else '')
        display_df[column] = column_values

    data = display_df.iloc[:, display_indices].values.tolist()

    # Layout
    # Window and element size parameters
    width = const.WIN_WIDTH

    header_col = const.HEADER_COL
    bg_col = const.ACTION_COL

    header_font = const.HEADER_FONT

    pad_el = const.ELEM_PAD
    pad_v = const.VERT_PAD
    pad_frame = const.FRAME_PAD

    layout_params = []
    for param in parameters:
        if param.hidden is False:
            layout_params.append(param)

    # Title
    title_layout = [[sg.Canvas(size=(0, 1), pad=(0, pad_v), visible=True, background_color=header_col)],
                    [sg.Text('Import Database Records', pad=((pad_frame, 0), (0, pad_v)), font=header_font,
                             background_color=header_col)]]

    use_center = True
    if len(layout_params) <= 2:
        use_center = False

    left_cols = []
    center_cols = []
    right_cols = []
    left_sizes = []
    for i, parameter in enumerate(layout_params):
        param_index = i + 1
        if use_center is True:
            index_mod = param_index % 3
        else:
            index_mod = param_index % 2

        param_layout = parameter.layout(padding=(0, pad_el * 2), size=(14, 1), text_size=(14, 1), filter_layout=True)

        if use_center is True and index_mod == 1:
            left_cols.append(param_layout)
            left_sizes.append(len(parameter.description))
        elif use_center is True and index_mod == 2:
            center_cols.append(param_layout)
        elif use_center is True and index_mod == 0:
            right_cols.append(param_layout)
        elif use_center is False and index_mod == 1:
            left_cols.append(param_layout)
            center_cols.append([sg.Canvas(size=(0, 0), visible=True)])
        elif use_center is False and index_mod == 0:
            right_cols.append(param_layout)
        else:
            print('Warning: cannot assign layout for filter parameter {PARAM}'.format(PARAM=parameter.name))

    pad_diff = 14 - max(left_sizes)
    param_pad_r = pad_frame + pad_diff * 13 if pad_diff > 0 else pad_frame

    header_layout = [[sg.Col([[sg.Canvas(size=(0, 0), background_color=bg_col)]],
                             pad=(0, (pad_v, 0)), background_color=bg_col, expand_x=True)],
                     [sg.Col(left_cols, pad=((pad_frame, 0), 0), background_color=bg_col, justification='l',
                             vertical_alignment='t', expand_x=True),
                      sg.Col(center_cols, pad=(0, 0), background_color=bg_col, justification='c',
                             vertical_alignment='t', expand_x=True),
                      sg.Col(right_cols, pad=((0, param_pad_r), 0), background_color=bg_col, justification='r',
                             vertical_alignment='t', expand_x=True)],
                     [sg.HorizontalSeparator(pad=(0, (pad_v, 0)), color=const.INACTIVE_COL)]]

    # Import data table
    main_layout = [[lo.create_table_layout(data, display_header, '-TABLE-', events=False, width=width, nrow=20,
                                           pad=(0, 0))]]

    # Control buttons
    bttn_layout = [[sg.Col([[lo.B2('Cancel', key='-CANCEL-', disabled=False, tooltip='Cancel data import')]],
                           pad=(0, 0), justification='l', expand_x=True),
                    sg.Col([[sg.Canvas(size=(0, 0), visible=True)]], justification='c', expand_x=True),
                    sg.Col([[lo.B2('New', key='-NEW-', pad=((0, pad_el), 0), visible=create_new,
                                   tooltip='Create new record'),
                             lo.B2('OK', key='-OK-', disabled=True, tooltip='Import selected data')]],
                           pad=(0, 0), justification='r')]]

    layout = [[sg.Col(title_layout, pad=(0, 0), justification='l', background_color=header_col, expand_x=True)],
              [sg.Col(header_layout, pad=(pad_frame, 0), background_color=bg_col, expand_x=True, expand_y=True)],
              [sg.Col(main_layout, pad=(pad_frame, (pad_frame, 0)), background_color=bg_col, justification='c')],
              [sg.Col(bttn_layout, pad=(pad_frame, (pad_v, pad_frame)), expand_x=True)]]

    window = sg.Window('', layout, modal=True, resizable=False)

    # Main loop
    import_data = None
    while True:
        event, values = window.read(timeout=1000, close=False)
#        event, values = window.read()

        if event in (sg.WIN_CLOSED, '-CANCEL-'):  # selected close-window or Cancel
            import_data = None
            break

        # Filter table rows based on parameter values
        if event in filter_params:
            display_df = df.copy()

            # Filter table
            for param in parameters:
                if param.hidden is True:
                    param_value = param.value
                else:
                    param_value = values[param.element_key]

                if param_value:
                    display_df = display_df[display_df[param.name] == param_value]

            # Map column values to the aliases specified in the configuration
            for alias_col in aliases:
                alias_map = aliases[alias_col]  # dictionary of mapped values

                if alias_col not in header:
                    continue
                else:
                    display_df[alias_col].replace(alias_map, inplace=True)

            for column in display_df.columns:
                column_values = display_df[column]
                dtype = column_values.dtype
                if is_float_dtype(dtype):
                    column_values = column_values.apply('{:,.2f}'.format)
                elif is_datetime_dtype(dtype):
                    column_values = column_values.apply(lambda x: (strptime(x.strftime(date_fmt), date_fmt) +
                                                                   relativedelta(years=+date_offset)).strftime(date_fmt)
                    if pd.notnull(x) else '')
                display_df[column] = column_values

            window['-TABLE-'].update(values=display_df.iloc[:, display_indices].values.tolist())

            continue

        # Enable the OK button if a record is selected
        if values['-TABLE-']:
            window['-OK-'].update(disabled=False)

        # Disable the OK button if no record is selected
        if not values['-TABLE-']:
            window['-OK-'].update(disabled=True)

        if event == '-NEW-':  # click 'NEW' button
            import_data = pd.DataFrame(columns=df.columns.values.tolist())
            break

        if event == '-OK-':  # click 'OK' button
            # retrieve selected row
            try:
                row = values['-TABLE-'][0]
            except IndexError:
                continue
            import_data = display_df.iloc[row]
            break

    window.close()
    layout = None
    window = None
    gc.collect()

    return import_data


def import_window(df, win_size: tuple = None):
    """
    Display the audit importer window.
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
    header_col = const.HEADER_COL

    # GUI layout
    bttn_layout = [[lo.B2(_('Cancel'), key='-CANCEL-', pad=(pad_el, 0), tooltip=_('Cancel import')),
                    lo.B2(_('Import'), bind_return_key=True, key='-IMPORT-', pad=(pad_el, 0),
                          tooltip=_('Import the selected transaction orders'))]]

    tbl_key = lo.as_key('Import Table')
    layout = [[sg.Col([[sg.Text(_('Import Missing Data'), pad=(pad_frame, (pad_frame, pad_v)),
                                background_color=header_col, font=font_h)]],
                      pad=(0, 0), background_color=header_col, justification='l', expand_x=True, expand_y=True)],
              [sg.Frame('', [[lo.create_table_layout(data, header, tbl_key, bind=True, height=height, width=width,
                                                     pad=(0, 0))]],
                        background_color=bg_col, element_justification='c', pad=(pad_frame, 0), border_width=0)],
              [sg.Col(bttn_layout, justification='c', pad=(pad_frame, (pad_v, pad_frame)))]]

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
    layout = None
    window = None
    gc.collect()

    return vfy_orders


def about():
    """
    Display the "about program" window.
    """
    bg_col = const.ACTION_COL
    header_font = const.HEADER_FONT
    sub_font = const.BOLD_MID_FONT
    text_font = const.MID_FONT
    pad_frame = const.FRAME_PAD
    pad_el = const.ELEM_PAD
    header_col = const.HEADER_COL

    layout = [[sg.Frame('', [[sg.Col([[sg.Image(filename=settings.logo)]], pad=((0, pad_el), 0),
                                     background_color=bg_col),
                              sg.Col(
                                  [[sg.Col([[sg.Text('REM', pad=((pad_el, pad_frame), 0), background_color=header_col,
                                                     font=header_font)],
                                            [sg.Text('Revenue & Expense Management',
                                                     pad=((pad_el, pad_frame), (0, pad_el)),
                                                     background_color=header_col, font=sub_font)]],
                                           background_color=header_col, expand_y=True, expand_x=True)],
                                   [sg.Text('version:', size=(8, 1), pad=(pad_el, 0),
                                            background_color=bg_col, font=text_font),
                                    sg.Text(__version__, pad=((pad_el, pad_frame), 0), background_color=bg_col,
                                            font=text_font)],
                                   [sg.Text('copyright:', size=(8, 1), pad=(pad_el, 0),
                                            background_color=bg_col, font=text_font),
                                    sg.Text('2020 Tila Construction Co.', pad=((pad_el, pad_frame), 0),
                                            background_color=bg_col, font=text_font)],
                                   [sg.Text('license:', size=(8, 1), pad=(pad_el, 0),
                                            background_color=bg_col, font=text_font),
                                    sg.Text('GPL v3', pad=((pad_el, pad_frame), 0), background_color=bg_col,
                                            font=text_font)]],
                                  element_justification='l', background_color=bg_col, vertical_alignment='t')]],
                        background_color=bg_col, border_width=0)]]

    window = sg.Window(_('About REM'), layout, modal=True, resizable=False)

    # Start event loop
    while True:
        event, values = window.read()

        if event == sg.WIN_CLOSED:  # selected close-window or Cancel
            break

    window.close()
    layout = None
    window = None
    gc.collect()


def edit_settings(win_size: tuple = None):
    """
    Display window for editing the configuration.
    """
    if win_size:
        width, height = [i * 0.6 for i in win_size]
    else:
        width, height = (const.WIN_WIDTH * 0.6, const.WIN_HEIGHT * 0.6)

    # Window and element size parameters
    pad_el = const.ELEM_PAD
    pad_frame = const.FRAME_PAD
    pad_v = const.VERT_PAD

    font_h = const.HEADER_FONT
    header_col = const.HEADER_COL

    bg_col = const.ACTION_COL

    # GUI layout
    ## Buttons
    bttn_layout = [[lo.B2(_('Cancel'), key='-CANCEL-', pad=(pad_el, 0), tooltip=_('Cancel edit')),
                    lo.B2(_('Save'), key='-SAVE-', bind_return_key=True, pad=(pad_el, 0),
                          tooltip=_('Save changes'))]]

    layout = [[sg.Col([[sg.Text('Edit Settings', pad=(pad_frame, (pad_frame, pad_v)), font=font_h,
                                background_color=header_col)]], pad=(0, 0), justification='l',
                      background_color=header_col, expand_x=True, expand_y=True)],
              [sg.Frame('', settings.layout(), relief='sunken', border_width=1, pad=(0, 0),
                        background_color=bg_col)],
              [sg.Col(bttn_layout, justification='c', pad=(0, (pad_v, pad_frame)))]]

    window = sg.Window(_('Settings'), layout, modal=True, resizable=False)
    window.finalize()

    element_keys = {'-LANGUAGE-': 'language', '-LOCALE-': 'locale', '-TEMPLATE-': 'template',
                    '-CSS-': 'css', '-PORT-': 'port', '-SERVER-': 'server', '-DRIVER-': 'driver',
                    '-DATABASE-': 'dbname'}

    # Start event loop
    while True:
        event, values = window.read()

        if event in (sg.WIN_CLOSED, '-CANCEL-'):  # selected close-window or Cancel
            break

        if event == '-SAVE-':
            for element_key in element_keys:
                attribute = element_keys[element_key]
                element_value = values[element_key]
                settings.edit_attribute(attribute, element_value)
            break

    window.close()
    layout = None
    window = None
    gc.collect()


def modify_record(df, index, edit_cols, header_map: dict = None, win_size: tuple = None, edit: bool = True):
    """
    Display window for user to add or edit a row.

    Arguments:
        df (DataFrame): pandas dataframe.

        index (int): dataframe index of row to edit.

        edit_cols (dict): dictionary of columns that are editable.

        header_map (dict): dictionary mapping dataframe columns to display columns.

        win_size (tuple): tuple containing the window width and height.

        edit (bool): edit an existing record [default: True].
    """
    is_float_dtype = pd.api.types.is_float_dtype
    is_integer_dtype = pd.api.types.is_integer_dtype
    is_datetime_dtype = pd.api.types.is_datetime64_any_dtype
    is_bool_dtype = pd.api.types.is_bool_dtype

    if not isinstance(edit_cols, dict):
        print('TypeError: argument edit_cols must be a dictionary')
        return df

    if not isinstance(index, int):
        print('TypeError: argument index must be an integer value')
        return df

    if win_size:
        width, height = win_size
    else:
        width, height = (const.WIN_WIDTH, const.WIN_HEIGHT)

    # Format dataframe as a list for the gui
    row = df.iloc[index]
    header = df.columns.values.tolist()

    if header_map is None:
        header_map = {i: i for i in header}

    display_header = []
    for column in header_map:
        if column in header:
            display_header.append(column)
        else:
            continue

    edit_keys = {}
    for column in edit_cols:
        element_key = lo.as_key(column)
        edit_keys[column] = element_key

    # Window and element size parameters
    main_font = const.MAIN_FONT
    font_size = main_font[1]

    pad_el = const.ELEM_PAD
    pad_frame = const.FRAME_PAD
    pad_v = const.VERT_PAD

    header_col = const.TBL_HEADER_COL
    in_col = const.INPUT_COL

    # GUI layout
    ## Buttons
    #    if edit is True and index > 0:
    bttn_layout = [[lo.B2(_('Cancel'), key='-CANCEL-', pad=(pad_el, 0), tooltip=_('Cancel edit')),
                    lo.B2(_('Save'), key='-SAVE-', bind_return_key=True, pad=(pad_el, 0),
                          tooltip=_('Save changes'))]]

    ## Table
    lengths = dm.calc_column_widths(display_header, width=width, font_size=font_size, pixels=False)

    tbl_layout = []
    for i, display_column in enumerate(display_header):
        display_name = header_map[display_column]

        col_width = lengths[i]
        column_layout = [[sg.Text(display_name, size=(col_width, 1), auto_size_text=False, border_width=1,
                                  relief='sunken', background_color=header_col, justification='c', font=main_font,
                                  tooltip=display_name)]]

        field_val = row[display_column]
        if display_column in edit_keys:
            element_key = edit_keys[display_column]
            readonly = False
            try:
                column_type = edit_cols[display_column]['ElementType']
            except KeyError:
                column_type = 'string'
        else:
            element_key = lo.as_key(display_column)
            readonly = True
            column_type = 'string'

        if column_type == 'dropdown':
            try:
                values = edit_cols[display_column]['Values']
            except KeyError:
                values = [field_val]
            column_layout.append([sg.DropDown(values, default_value=field_val, key=element_key, size=(col_width - 2, 1),
                                              font=main_font, readonly=readonly,
                                              tooltip='Select item from the dropdown menu')])
        else:
            column_layout.append([sg.Input(field_val, key=element_key, size=(col_width, 1), border_width=1,
                                           font=main_font, justification='r', readonly=readonly,
                                           background_color=in_col, tooltip=field_val)])

        tbl_layout.append(sg.Col(column_layout, pad=(0, 0), expand_x=True))

    layout = [[sg.Frame('', [tbl_layout], relief='sunken', border_width=1, pad=(pad_frame, (pad_frame, 0)))],
              [sg.Col(bttn_layout, justification='c', pad=(pad_frame, (pad_v, pad_frame)))]]

    window = sg.Window(_('Modify Record'), layout, modal=True, resizable=False)
    window.finalize()

    for display_column in display_header:
        if display_column in edit_keys:
            element_key = edit_keys[display_column]
            window[element_key].expand(expand_x=True)

    # Start event loop
    while True:
        event, values = window.read()

        if event in (sg.WIN_CLOSED, '-CANCEL-'):  # selected close-window or Cancel
            if edit is False:
                df.drop(index, axis=0, inplace=True)
                df.reset_index(drop=True, inplace=True)

            break

        if event == '-SAVE-':  # click 'Save' button
            ready_to_save = []
            for column in edit_keys:
                col_key = edit_keys[column]
                input_val = values[col_key]

                # Get data type of column
                try:
                    dtype = edit_cols[column]['ElementType'].lower()
                except (KeyError, TypeError):
                    dtype = df[column].dtype
                else:
                    if dtype in ('date', 'datetime', 'timestamp', 'time', 'year'):
                        dtype = np.datetime64
                    elif dtype == 'dropdown':
                        dtype = np.object
                    elif dtype in ('float', 'decimal', 'dec', 'double', 'numeric', 'money'):
                        dtype = float
                    elif dtype in ('int', 'integer', 'bit'):
                        dtype = int
                    elif dtype in ('bool', 'boolean'):
                        dtype = bool
                    else:
                        dtype = np.object

                # Set field value based on data type
                print('Info: the data type of column {COL} is {DTYPE}'.format(COL=header_map[column], DTYPE=dtype))
                msg = 'The value "{VAL}" provided to column "{COL}" is the wrong type'
                if is_float_dtype(dtype):
                    try:
                        field_val = float(input_val)
                    except ValueError:
                        print(msg.format(VAL=input_val, COL=header_map[column]))
                        popup_notice(msg.format(VAL=input_val, COL=header_map[column]))
                        ready_to_save.append(False)
                        break
                elif is_integer_dtype(dtype):
                    try:
                        field_val = int(input_val)
                    except ValueError:
                        print(msg.format(VAL=input_val, COL=header_map[column]))
                        popup_notice(msg.format(VAL=input_val, COL=header_map[column]))
                        ready_to_save.append(False)
                        break
                elif is_bool_dtype(dtype):
                    try:
                        field_val = bool(input_val)
                    except ValueError:
                        print(msg.format(VAL=input_val, COL=header_map[column]))
                        popup_notice(msg.format(VAL=input_val, COL=header_map[column]))
                        ready_to_save.append(False)
                        break
                elif is_datetime_dtype(dtype):
                    try:
                        field_val = pd.to_datetime(input_val, format=settings.format_date_str(), errors='coerce')
                    except ValueError:
                        print(msg.format(VAL=input_val, COL=header_map[column]))
                        popup_notice(msg.format(VAL=input_val, COL=header_map[column]))
                        ready_to_save.append(False)
                        break
                else:
                    field_val = input_val

                # Replace field value with modified value
                try:
                    df.at[index, column] = field_val
                except ValueError as e:
                    msg = 'The value "{VAL}" provided to column "{COL}" is of the wrong type - {ERR}' \
                        .format(VAL=field_val, COL=header_map[column], ERR=e)
                    popup_notice(msg)
                    ready_to_save.append(False)
                else:
                    ready_to_save.append(True)

            if all(ready_to_save):
                break
            else:
                continue

    window.close()
    layout = None
    window = None
    gc.collect()

    return df
