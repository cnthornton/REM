"""
REM secondary window functions, including popups, a window for importing 
missing data, the debugger, and the login window.
"""
import dateutil
import datetime
import gc
import numpy as np
import pandas as pd
import pyodbc
import PySimpleGUI as sg
import textwrap

from REM.config import configuration, settings
import REM.constants as mod_const
import REM.data_manipulation as mod_dm
import REM.layouts as mod_lo
from REM.main import __version__
import REM.records as mod_records


# Popups
def popup_confirm(msg):
    """Display popup asking user if they would like to continue without completing the current action.
    """
    font = mod_const.MID_FONT
    return sg.popup_ok_cancel(textwrap.fill(msg, width=40), font=font, title='')


def popup_notice(msg):
    """
    Display popup notifying user that an action is required or couldn't be undertaken.
    """
    font = mod_const.MID_FONT
    return sg.popup_ok(textwrap.fill(msg, width=40), font=font, title='')


def popup_error(msg):
    """
    Display popup notifying user that there is a fatal program error.
    """
    font = mod_const.MID_FONT
    return sg.popup_error(textwrap.fill(msg, width=40), font=font, title='')


# Functions
def verify_row(self, row_index):
    """
    Add row to verified list, returning list of updated row colors.
    """
    tbl_bg_col = mod_const.TBL_BG_COL
    tbl_alt_col = mod_const.TBL_ALT_COL
    tbl_vfy_col = mod_const.TBL_VFY_COL

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
    pad_frame = mod_const.FRAME_PAD

    main_font = mod_const.MAIN_FONT

    # GUI layout
    layout = [[sg.Output(key='-DEBUG-', size=(60, 20), pad=(pad_frame, pad_frame))]]

    window = sg.Window('Debug', layout, font=main_font, modal=False, resizable=True)

    return window


def login_window(account):
    """
    Display the login window.
    """
    # Window and element size parameters
    pad_frame = mod_const.FRAME_PAD
    pad_h = mod_const.HORZ_PAD
    pad_el = mod_const.ELEM_PAD

    bg_col = mod_const.ACTION_COL
    input_col = mod_const.INPUT_COL
    login_col = mod_const.LOGIN_BUTTON_COL
    cancel_col = mod_const.CANCEL_BUTTON_COL
    def_text_col = mod_const.TEXT_COL
    text_col = mod_const.WHITE_TEXT_COL
    help_col = mod_const.HELP_TEXT_COL
    bold_text = mod_const.BOLD_FONT

    lock_icon = mod_const.LOCK_ICON
    username_icon = mod_const.USERNAME_ICON

    isize = mod_const.IN1_SIZE
    bsize = mod_const.B1_SIZE

    main_font = mod_const.MAIN_FONT
    small_font = mod_const.SMALL_FONT

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


def record_window(record, user, win_size: tuple = None, save: bool = False, delete: bool = False, view_only: bool = False):
    """
    Display the record window.
    """
    if win_size:
        width, height = win_size
    else:
        width, height = (mod_const.WIN_WIDTH, mod_const.WIN_HEIGHT)

    # GUI layout
    pad_v = mod_const.VERT_PAD
    bg_col = mod_const.ACTION_COL

    layout = [[sg.Col(record.layout(win_size=(600, height), save=save, delete=delete, view_only=view_only),
                      pad=(pad_v, pad_v), background_color=bg_col, expand_x=True)]]
    window = sg.Window('Database Record', layout, modal=True, keep_on_top=False, return_keyboard_events=True)
    window.finalize()

    # Resize window
    screen_w, screen_h = window.get_screen_dimensions()
    win_w = int(screen_w * 0.45)
    win_h = int(screen_h * 0.6)

    record.resize(window, win_size=(win_w, win_h))
    window = center_window(window)

    # Update record display
    record.update_display(window)

    # Event window
    record_elements = [i for i in record.elements]
    while True:
        event, values = window.read()

        if event == sg.WIN_CLOSED:  # selected close-window without accepting changes
            # Remove unsaved ID if record is new
            if record.new is True:
                record_entry = configuration.records.fetch_rule(record.name)
                try:
                    record_entry.remove_unsaved_id(record.record_id)
                except AttributeError:
                    print('Warning: unknown record type provided to record {ID}'.format(ID=record.record_id))

                record = None

            break

        # Update the record parameters with user-input
        if event in record_elements:
            print(event)
            result = record.run_event(window, event, values, user)
            if result is True:  # event is something other than the action buttons save or delete
                continue
            else:  # event is save or delete
                if event == record.key_lookup('Delete'):  # delete the record selected
                    record = None
                else:  # save changes selected
                    # Update parameter values
                    for param in record.parameters:
                        elem_key = param.key_lookup('Element')
                        try:
                            param_value = values[elem_key]
                        except KeyError:
                            continue
                        param.value = param.format_value(param_value)

                break

    window.close()
    layout = None
    window = None
    gc.collect()

    return record


def notes_window(docno, note, id_title='RecordID', title='Note'):
    """
    Display the note-taking window.
    """
    # Window and element size parameters
    pad_frame = mod_const.FRAME_PAD
    pad_v = mod_const.VERT_PAD
    pad_el = mod_const.ELEM_PAD

    bg_col = mod_const.ACTION_COL
    default_col = mod_const.DEFAULT_COL
    input_col = mod_const.INPUT_COL
    text_col = mod_const.TEXT_COL
    header_col = mod_const.HEADER_COL

    main_font = mod_const.MAIN_FONT
    header_font = mod_const.HEADER_FONT
    bold_font = mod_const.BOLD_MID_FONT

    width = 80
    height = 20

    # GUI layout
    title_layout = [[sg.Canvas(size=(0, 1), pad=(0, pad_v), visible=True, background_color=header_col)],
                    [sg.Text('Add Note to Record', pad=((pad_frame, 0), (0, pad_v)), font=header_font,
                             background_color=header_col)]]

    header_layout = [
        [sg.Text('{}:'.format(id_title), pad=((pad_el*2, pad_el), pad_el*2), font=bold_font, background_color=bg_col),
         sg.Text(docno, size=(12, 1), pad=((pad_el, pad_el*2), pad_el*2), justification='l', font=main_font,
                 background_color=bg_col, auto_size_text=True, border_width=0)]]

    note_layout = [[sg.Text('{}:'.format(title), pad=(0, (0, pad_el)), background_color=bg_col, font=bold_font)],
                   [sg.Multiline(default_text=note, key='-NOTE-', size=(width, height), pad=(0, 0),
                                 background_color=bg_col, text_color=text_col, border_width=1, focus=False)]]

    main_layout = [[sg.Frame('', header_layout, pad=(pad_frame, pad_frame), background_color=header_col,
                             border_width=1, relief='raised')],
                   [sg.Col(note_layout, pad=(pad_frame, (0, pad_frame)), background_color=input_col, justification='l')]]

    bttn_layout = [[mod_lo.B2('Cancel', key='-CANCEL-', pad=((0, pad_el), 0), tooltip='Cancel'),
                    mod_lo.B2('Save', key='-SAVE-', pad=((pad_el, 0), 0), tooltip='Save note')]]

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


def database_importer_window(user, win_size: tuple = None):
    """
    Display the database importer window.
    """
    is_numeric_dtype = pd.api.types.is_numeric_dtype
    is_datetime_dtype = pd.api.types.is_datetime64_any_dtype
    relativedelta = dateutil.relativedelta.relativedelta

    dtype_map = {'date': np.datetime64, 'datetime': np.datetime64, 'timestamp': np.datetime64, 'time': np.datetime64,
                 'float': float, 'decimal': float, 'dec': float, 'double': float, 'numeric': float, 'money': float,
                 'int': int, 'integer': int, 'bit': int, 'bool': bool, 'boolean': bool, 'char': str,
                 'varchar': str, 'binary': str, 'varbinary': str, 'tinytext': str, 'text': str, 'string': str}

    date_types = ['date', 'datetime', 'time', 'timestamp']

    oper_map = {'+': 'addition', '-': 'subtraction', '/': 'division', '*': 'multiplication', '%': 'modulo operation'}

    cond_operators = ['==', '!=', '>', '<', '>=', '<=']
    math_operators = ['+', '-', '*', '/', '%']

    # Layout settings
    main_font = mod_const.MAIN_FONT

    text_col = mod_const.TEXT_COL
    select_col = mod_const.SELECT_TEXT_COL

    # Window and element size parameters
    if win_size is not None:
        width = win_size[0] * 0.7
        height = win_size[1] * 0.8
    else:
        width, height = (int(mod_const.WIN_WIDTH * 0.7), int(mod_const.WIN_HEIGHT * 0.8))

    # Window layout
    layout = mod_lo.importer_layout(win_size=(width, height))

    window = sg.Window(_('Import to Database'), layout, font=main_font, modal=True, return_keyboard_events=True)
    window.finalize()

    deletion_keys = ['d', 'Delete', 'BackSpace']

    # Element values
    panel_keys = {0: '-P1-', 1: '-P2-', 2: '-P3-'}
    panel_names = {0: '-PN1-', 1: '-PN2-', 2: '-PN3-'}
    current_panel = 0
    first_panel = 0
    last_panel = 2

    req_df = pd.DataFrame(columns=['Table Column Name', 'Data Type', 'Default Value'])
    map_df = pd.DataFrame(columns=['Table Column Name', 'Data Type', 'File Column Name'])

    table = None
    record_ids = []
    record_entry = None
    subset_df = None
    reserved_values = [configuration.id_field, configuration.edit_date, configuration.editor_code,
                       configuration.creation_date, configuration.creator_code]
    listbox_values = []

    add_keys = ['-SUBSET_ADD_{}-'.format(i) for i in range(9)]  # last rule has no add button
    delete_keys = ['-SUBSET_DELETE_{}-'.format(i) for i in range(1, 10)]  # first rule has no delete button
    subs_in_view = [0]

    mod_add_keys = ['-MODIFY_ADD_{}-'.format(i) for i in range(9)]  # last rule has no add button
    mod_delete_keys = ['-MODIFY_DELETE_{}-'.format(i) for i in range(1, 10)]  # first rule has no delete button
    mods_in_view = [0]

    # Start event loop
    while True:
        event, values = window.read(timeout=1000)

        if event in (sg.WIN_CLOSED, '-CANCEL-'):  # selected close-window or Cancel
            # Delete any unsaved record IDs created in the final step
            if len(record_ids) > 0 and record_entry is not None:
                print('Info: removing unsaved record IDs')
                record_entry.remove_ids(record_ids)
                record_ids = []
            break

        # Import selected data into the database table
        if event == '-IMPORT-':
            if subset_df is None or table is None or record_entry is None:
                continue

            # Prepare the insertion statement
            tbl_columns = subset_df.columns.values.tolist()
            records_saved = []
            for index, row in subset_df.iterrows():
                # Prepare update parameters
                row_values = row.replace({np.nan: None}).values.tolist()
                records_saved.append(user.insert(table, tbl_columns, row_values))

            msg = 'Successfully saved {SUCCESS} rows to the database. Failed to save {FAIL} rows'\
                .format(SUCCESS=len([i for i in records_saved if i is True]),
                        FAIL=len([i for i in records_saved if i is False]))
            popup_notice(msg)
            print('Info: {}'.format(msg))

            # Delete saved record IDs from list of unsaved IDs
            print('Info: removing saved records from the list of unsaved IDs')
            record_entry.remove_ids(record_ids)

            # Export report describing success of import by row
            success_col = 'Successfully saved'
            subset_df[success_col] = records_saved
            outfile = sg.popup_get_file('', title='Save Database import report', save_as=True,
                                        default_extension='xlsx', no_window=True,
                                        file_types=(
                                            ('XLS - Microsoft Excel', '*.xlsx'), ('Comma-Separated Values', '*.csv')))

            try:
                out_fmt = outfile.split('.')[-1]
            except AttributeError:
                break

            if out_fmt == 'csv':
                subset_df.to_csv(outfile, sep=',', header=True, index=False)
            else:
                subset_df.style.apply(highlight_bool, column=success_col, axis=1).to_excel(outfile, engine='openpyxl', header=True, index=False)

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

            # Populate Preview table with top 10 and bottom 10 values from spreadsheet
            if next_panel == last_panel:
                table = values['-TABLE-']
                record_type = values['-RECORDTYPE-']
                if not table:
                    popup_notice('Please select a valid table from the "Table" dropdown')
                    continue
                elif not record_type:
                    popup_notice('Please select a valid record type from the "Record Type" dropdown')
                    continue
                else:
                    # Specify the import column data types
                    convert_map = {}
                    for index, row in map_df.iterrows():
                        fcolname = row['File Column Name']
                        colname = row['Table Column Name']

                        db_type = columns[colname][0]
                        if db_type in date_types:
                            continue

                        try:
                            coltype = dtype_map[db_type.lower()]
                        except KeyError:
                            print('Info: database data type {DTYPE} not in list of expected data types'
                                  .format(DTYPE=db_type))
                            continue
                        else:
                            convert_map[fcolname] = coltype

                    # Import spreadsheet into dataframe
                    file_format = values['-FORMAT-']
                    if file_format == 'xls':
                        formatting_options = {'convert_float': values['-INTS-'],
                                              'skiprows': skiptop, 'skipfooter': skipbottom, 'header': header_row,
                                              'thousands': thousands_sep, 'dtype': convert_map}
                        reader = pd.read_excel
                    else:
                        formatting_options = {'sep': values['-FSEP-'], 'skiprows': skiptop,
                                              'skipfooter': skipbottom, 'header': header_row,
                                              'thousands': thousands_sep, 'encoding': 'utf-8',
                                              'error_bad_lines': False,
                                              'skip_blank_lines': True, 'dtype': convert_map}
                        reader = pd.read_csv

                    print('Info: formatting import file options: {}'.format(formatting_options))

                    # Import data from the file into a pandas dataframe
                    import_df = reader(infile, **formatting_options)

                    # Rename columns based on mapping information
                    col_mapper = pd.Series(map_df['Table Column Name'].values,
                                           index=map_df['File Column Name']).to_dict()
                    import_df.rename(col_mapper, axis=1, inplace=True)

                    # Set values for the required columns.
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
                    else:
                        # Set columns dtypes
                        dtypes = {}
                        date_cols = []
                        for final_col in all_cols:
                            if final_col in columns:
                                coltype = columns[final_col][0]
                                if coltype in date_types:  # set the datatype of datetime columns separately
                                    date_cols.append(final_col)
                                    continue

                                try:
                                    dtype = dtype_map[coltype.lower()]
                                except KeyError:
                                    dtype = np.object
                                dtypes[final_col] = dtype

                        final_df = final_df.astype(dtypes)
                        if values['-DATES-']:
                            for date_col in date_cols:
                                try:
                                    final_df[date_col] = pd.to_datetime(final_df[date_col],
                                                                        dayfirst=values['-DAYFIRST-'],
                                                                        yearfirst=values['-YEARFIRST-'])
                                except Exception as e:
                                    msg = 'Unable to convert values in column {COL} to a datetime format - {ERR}'\
                                        .format(COL=date_col, ERR=e)
                                    popup_error(msg)
                                    print('Error: {}'.format(msg))

                    # Subset table based on specified subset rules
                    subset_df = final_df
                    for sub_num in subs_in_view:
                        sub_col = values['-SUBSET_COL_{}-'.format(sub_num)]
                        sub_oper = values['-SUBSET_OPER_{}-'.format(sub_num)]
                        sub_val = values['-SUBSET_VALUE_{}-'.format(sub_num)]
                        if not sub_col or not sub_oper:
                            continue

                        if sub_col not in all_cols.values.tolist():
                            msg = 'The column {COL} selected in subset rule {RULE} must be one of the required or ' \
                                  'mapping columns chosen for importing'.format(COL=sub_col, RULE=sub_num + 1)
                            popup_error(msg)
                            print('Warning: {}'.format(msg))
                            continue

                        # Get dtype of subset column and convert value to the correct dtype
                        try:
                            sub_dtype = columns[sub_col][0]
                        except KeyError:
                            msg = 'The column {COL} selected for subset rule {RULE} must be a valid table column'\
                                .format(COL=sub_col, RULE=sub_num + 1)
                            popup_error(msg)
                            print('Warning: {}'.format(msg))
                            continue
                        else:
                            sub_obj = dtype_map[sub_dtype]

                        try:
                            sub_val_fmt = sub_obj(sub_val)
                        except ValueError:
                            msg = 'Unable to convert the value {VAL} from subset rule {RULE} to {DTYPE}'\
                                .format(VAL=sub_val, RULE=sub_num + 1, DTYPE=sub_dtype)
                            popup_error(msg)
                            print('Warning: {}'.format(msg))
                            continue
                        else:
                            print('Info: sub-setting table column {COL} by value {VAL}'
                                  .format(COL=sub_col, VAL=sub_val_fmt))

                        if sub_oper == '<':
                            cond_results = subset_df[sub_col] < sub_val_fmt
                        elif sub_oper == '>':
                            cond_results = subset_df[sub_col] > sub_val_fmt
                        elif sub_oper == '<=':
                            cond_results = subset_df[sub_col] <= sub_val_fmt
                        elif sub_oper == '>=':
                            cond_results = subset_df[sub_col] >= sub_val_fmt
                        elif sub_oper == '=':
                            cond_results = subset_df[sub_col] == sub_val_fmt
                        elif sub_oper == '!=':
                            cond_results = subset_df[sub_col] != sub_val_fmt
                        else:
                            msg = 'The operator {OPER} selected for subset rule {RULE} is not a supported ' \
                                  'subset operator'.format(OPER=sub_oper, RULE=sub_num + 1)
                            popup_error(msg)
                            print('Warning: {}'.format(msg))
                            continue

                        try:
                            subset_df = subset_df[cond_results]
                        except Exception as e:
                            msg = 'Failed to subset the dataframe using subset rule {RULE}. Use the debug window for ' \
                                  'more information'.format(RULE=sub_num)
                            popup_error(msg)
                            print('Warning: {MSG} - {ERR}'.format(MSG=msg, ERR=e))

                    # Create record IDs for each row in the final import table
                    record_entry = configuration.records.fetch_rule(record_type, by_title=True)

                    failed_rows = []
                    for index, row in subset_df.iterrows():
                        try:
                            date_list = pd.to_datetime(subset_df[configuration.date_field], errors='coerce')
                        except KeyError:
                            record_date = datetime.datetime.now()
                        else:
                            record_date = date_list[index]

                        record_id = record_entry.create_id(record_date)
                        if record_id is None:
                            msg = 'Failed to create a record ID for row {}'.format(row)
                            popup_notice(msg)
                            print('Error: {}'.format(msg))
                            failed_rows.append(index)
                        else:
                            record_ids.append(record_id)

                    subset_df = subset_df[~subset_df.index.isin(failed_rows)]

                    subset_df[configuration.id_field] = record_ids

                    # Set values for the creator fields
                    subset_df[configuration.creator_code] = user.uid
                    subset_df[configuration.creation_date] = datetime.datetime.now()

                    # Modify table column values based on the modify column rules
                    for elem_num in mods_in_view:
                        elem_col = values['-MODIFY_COL_{}-'.format(elem_num)]
                        elem_oper = values['-MODIFY_OPER_{}-'.format(elem_num)]
                        elem_val = values['-MODIFY_VALUE_{}-'.format(elem_num)]
                        if not elem_col or not elem_oper:
                            continue

                        if elem_col not in all_cols.values.tolist():
                            msg = 'The column {COL} selected in modify column rule {RULE} must be one of the required ' \
                                  'or mapping columns chosen for importing'.format(COL=elem_col, RULE=elem_num + 1)
                            popup_error(msg)
                            print('Warning: {}'.format(msg))
                            continue

                        if elem_oper not in math_operators:
                            msg = 'The operator {OPER} selected for modify column rule {RULE} is not a supported math ' \
                                  'operator'.format(OPER=elem_oper, RULE=elem_num + 1)
                            popup_error(msg)
                            print('Warning: {}'.format(msg))
                            continue

                        # Get the datatype of the column to modify
                        try:
                            elem_dtype = columns[elem_col][0]
                        except KeyError:
                            msg = 'The column {COL} selected for modify column rule {RULE} must be a valid table ' \
                                  'column'.format(COL=elem_col, RULE=elem_num + 1)
                            popup_error(msg)
                            print('Warning: {}'.format(msg))
                            continue
                        else:
                            elem_obj = dtype_map[elem_dtype]

                        # Convert value to numeric datatype
                        try:
                            elem_val_fmt = float(elem_val)
                        except ValueError:
                            msg = 'Unable to convert the value {VAL} from modify column rule {RULE} to numeric' \
                                .format(VAL=elem_val, RULE=elem_num + 1)
                            popup_error(msg)
                            print('Warning: {}'.format(msg))
                            continue
                        else:
                            print('Info: modifying table column {COL} by value {VAL} based on rule {RULE}'
                                  .format(COL=elem_col, VAL=elem_val_fmt, RULE=elem_num + 1))

                        # Create the evaluation string
                        if is_numeric_dtype(elem_obj):
                            eval_str = 'subset_df["{COL}"] {OPER} {VAL}'\
                                .format(COL=elem_col, OPER=elem_oper, VAL=elem_val_fmt)
                            try:
                                subset_df[elem_col] = eval(eval_str)
                            except SyntaxError:
                                msg = 'Failed to modify the values of column {COL} using rule {NAME}. Use the debug ' \
                                      'window for more information'.format(COL=elem_col, NAME=elem_num + 1)
                                popup_error(msg)
                                print('Warning: invalid syntax in evaluation string {RULE} for rule {NAME}'
                                      .format(RULE=eval_str, NAME=elem_num))
                                print(subset_df)
                            except NameError:
                                msg = 'Failed to modify the values of column {COL} using rule {NAME}. Use the debug ' \
                                      'window for more information'.format(COL=elem_col, NAME=elem_num + 1)
                                popup_error(msg)
                                print('Warning: unknown column {COL} specified in modify rule {NAME}'
                                      .format(COL=elem_col, NAME=eval_str))
                                print(subset_df)
                                print(subset_df.columns)
                            else:
                                print('Info: successfully modified column {COL} values based on specified rule {RULE}'
                                      .format(COL=elem_col, RULE=elem_num + 1))
                        elif is_datetime_dtype(elem_obj):
                            if elem_oper == '+':
                                offset = relativedelta(days=+elem_val_fmt)
                            elif elem_oper == '-':
                                offset = relativedelta(days=-elem_val_fmt)
                            else:
                                msg = 'Unable to modify column {COL} values in rule {RULE} using "{OPER}". Only ' \
                                      'addition and subtraction is supported for date columns.' \
                                    .format(COL=elem_col, OPER=oper_map[elem_oper], RULE=elem_num + 1)
                                popup_error(msg)
                                print('Warning: {}'.format(msg))
                                continue

                            try:
                                subset_df[elem_col] = subset_df[elem_col].apply(lambda x: x + offset)
                            except Exception as e:
                                msg = 'Failed to modify the values of column {COL} using rule {RULE} - {ERR}'\
                                    .format(COL=elem_col, RULE=elem_num + 1, ERR=e)
                                popup_error(msg)
                                print('Error: {}'.format(msg))
                            else:
                                print('Info: successfully modified column {COL} values based on specified rule {RULE}'
                                      .format(COL=elem_col, RULE=elem_num + 1))
                        else:
                            msg = 'Modify column rule {RULE}: Only columns with numeric or date data type ' \
                                  'can be modified'.format(RULE=elem_num + 1)
                            popup_error(msg)
                            print('Error: {}'.format(msg))
                            continue

                    print(subset_df)
                    print(subset_df.columns)
                    print(subset_df.dtypes)

                    # Populate preview with table values
                    final_cols = subset_df.columns.values.tolist()
                    preview_cols = [configuration.id_field] + [i for i in final_cols if i != configuration.id_field]
                    col_widths = mod_dm.calc_column_widths(preview_cols, width=width * 0.77, pixels=True)
                    window['-PREVIEW-'].Widget['columns'] = tuple(preview_cols)
                    window['-PREVIEW-'].Widget['displaycolumns'] = '#all'
                    for index, column_name in enumerate(preview_cols):
                        col_width = col_widths[index]
                        window['-PREVIEW-'].Widget.column(index, width=col_width)
                        window['-PREVIEW-'].Widget.heading(index, text=column_name)

                    preview_df = subset_df.head(10).append(subset_df.tail(10))[preview_cols]

                    window['-PREVIEW-'].update(values=preview_df.values.tolist())

                    # Update import statistic elements
                    nrow, ncol = subset_df.shape
                    window['-NCOL-'].update(value=ncol)
                    window['-NROW-'].update(value=nrow)
                    window['-TABLENAME-'].update(value=table)

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

            # Delete created record IDs if current panel is the preview panel
            if current_panel == last_panel:
                if len(record_ids) > 0 and record_entry is not None:
                    print('Info: removing unsaved record IDs')
                    record_entry.remove_ids(record_ids)
                    record_ids = []

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

        # Populate data tables based on database table selection
        if event == '-TABLE-':
            table = values['-TABLE-']
            columns = {i.column_name: (i.type_name, i.column_size) for i in
                       user.table_schema(settings.prog_db, table) if i.column_name not in reserved_values}

            listbox_values = list(columns.keys())

            # Reset columns displayed in the listboxes
            window['-REQLIST-'].update(values=listbox_values)
            window['-MAPLIST-'].update(values=listbox_values)

            # Reset the tables
            req_df.drop(req_df.index, inplace=True)
            map_df.drop(map_df.index, inplace=True)

            window['-REQCOL-'].update(values=req_df.values.tolist())
            window['-MAPCOL-'].update(values=map_df.values.tolist())

            # Reset the subset rule columns
            for index in range(10):
                sub_col_key = '-SUBSET_COL_{}-'.format(index)
                window[sub_col_key].update(values=tuple(sorted(listbox_values)))

            # Reset the modify rule columns
            for index in range(10):
                mod_col_key = '-MODIFY_COL_{}-'.format(index)
                window[mod_col_key].update(values=tuple(sorted(listbox_values)))

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

        # Remove rows from the tables
        if event.split(':')[0] in deletion_keys and values['-MAPCOL-']:
            indices = values['-MAPCOL-']
            col_names = map_df.loc[indices, 'Table Column Name']

            # Remove rows from the dataframe
            map_df.drop(indices, axis=0, inplace=True)
            map_df.reset_index(drop=True, inplace=True)
            window['-MAPCOL-'].update(values=map_df.values.tolist())

            # Return columns to the listboxes
            for col_name in col_names:
                if col_name not in req_df['Table Column Name'].tolist():
                    if col_name not in listbox_values:
                        listbox_values.append(col_name)

            window['-REQLIST-'].update(values=listbox_values)
            window['-MAPLIST-'].update(values=listbox_values)

        if event.split(':')[0] in deletion_keys and values['-REQCOL-']:
            indices = values['-REQCOL-']
            col_names = req_df.loc[indices, 'Table Column Name']

            # Remove rows from the dataframe
            req_df.drop(indices, axis=0, inplace=True)
            req_df.reset_index(drop=True, inplace=True)
            window['-REQCOL-'].update(values=req_df.values.tolist())

            # Return columns to the listboxes
            for col_name in col_names:
                if col_name not in map_df['Table Column Name'].tolist():  # not found in other dataframe
                    if col_name not in listbox_values:  # not already somehow in the listboxes
                        listbox_values.append(col_name)

            window['-REQLIST-'].update(values=listbox_values)
            window['-MAPLIST-'].update(values=listbox_values)

        # Edit a table row's values
        if event == '-REQCOL-' and table is not None:
            try:
                row_index = values['-REQCOL-'][0]
            except IndexError:
                continue

            # Find datatype of selected column
            row_name = req_df.at[row_index, 'Table Column Name']
            row_dtype = columns[row_name][0]

            # Modify table row
            row = edit_row_window(req_df.iloc[row_index], edit_columns={'Default Value': {'ElementType': row_dtype}})
            window['-REQCOL-'].update(values=req_df.values.tolist())
            req_df.iloc[row_index] = row

            continue

        if event == '-MAPCOL-' and table is not None:
            try:
                row_index = values['-MAPCOL-'][0]
            except IndexError:
                continue

            # Find datatype of selected column
            row_dtype = 'string'

            # Modify table row
            row = edit_row_window(map_df.iloc[row_index], edit_columns={'File Column Name': {'ElementType': row_dtype}})
            window['-MAPCOL-'].update(values=map_df.values.tolist())
            map_df.iloc[row_index] = row

            continue

        # Add a subset element
        if event in add_keys:
            # Get subset number of current and following rows
            subset_num = int(event.replace('-', '').split('_')[-1])
            next_num = subset_num + 1

            # Make next row visible
            next_key = '-SUBSET_{}-'.format(next_num)
            window[next_key].update(visible=True)
            window[next_key].expand(expand_x=True, expand_row=True)

            # Make add button of current element invisible
            window[event].update(visible=False)

            # Add new row to the list of visible rows
            subs_in_view.append(next_num)

            window['-SUBSET-'].update(visible=False)
            window['-SUBSET-'].expand(expand_y=True, expand_row=True)
            window.refresh()
            window['-SUBSET-'].update(visible=True)

            print('Info: adding subset rule {RULE} with key {KEY}'.format(RULE=next_num, KEY=next_key))
            continue

        # Delete a subset element
        if event in delete_keys:
            # Get subset number
            subset_num = int(event.replace('-', '').split('_')[-1])

            # Make row invisible and remove from list of visible rows
            subset_key = '-SUBSET_{}-'.format(subset_num)
            window[subset_key].update(visible=False)
            subs_in_view.remove(subset_num)

            # Reset the rule values
            elem_col = '-SUBSET_COL_{}-'.format(subset_num)
            elem_oper = '-SUBSET_OPER_{}-'.format(subset_num)
            elem_value = '-SUBSET_VALUE_{}-'.format(subset_num)
            window[elem_col].update(value='')
            window[elem_oper].update(value='')
            window[elem_value].update(value='')

            # Make the add button of previous rule visible again
            prev_num = subset_num - 1
            if prev_num >= 0:
                prev_key = '-SUBSET_ADD_{}-'.format(prev_num)
                window[prev_key].update(visible=True)

            window['-SUBSET-'].update(visible=False)
            window['-SUBSET-'].expand(expand_y=True, expand_row=True)
            window.refresh()
            window['-SUBSET-'].update(visible=True)

            print('Info: deleting subset rule {RULE} with key {KEY}'.format(RULE=subset_num, KEY=subset_key))
            continue

        # Add a modify column element
        if event in mod_add_keys:
            # Get subset number of current and following rows
            mod_num = int(event.replace('-', '').split('_')[-1])
            next_num = mod_num + 1

            # Make next row visible
            next_key = '-MODIFY_{}-'.format(next_num)
            window[next_key].update(visible=True)
            window[next_key].expand(expand_x=True, expand_row=True)

            # Make add button of current element invisible
            window[event].update(visible=False)

            # Add new row to the list of visible rows
            mods_in_view.append(next_num)

            window['-MODIFY-'].update(visible=False)
            window['-MODIFY-'].expand(expand_y=True, expand_row=True)
            window.refresh()
            window['-MODIFY-'].update(visible=True)

            print('Info: adding modify column rule {RULE} with key {KEY}'.format(RULE=next_num, KEY=next_key))
            continue

        # Delete a modify column element
        if event in mod_delete_keys:
            # Get subset number
            elem_num = int(event.replace('-', '').split('_')[-1])

            # Make row invisible and remove from list of visible rows
            mod_key = '-MODIFY_{}-'.format(elem_num)
            window[mod_key].update(visible=False)
            mods_in_view.remove(elem_num)

            # Reset the rule values
            elem_col = '-MODIFY_COL_{}-'.format(elem_num)
            elem_oper = '-MODIFY_OPER_{}-'.format(elem_num)
            elem_value = '-MODIFY_VALUE_{}-'.format(elem_num)
            window[elem_col].update(value='')
            window[elem_oper].update(value='')
            window[elem_value].update(value='')

            # Make the add button of previous rule visible again
            prev_num = elem_num - 1
            if prev_num >= 0:
                prev_key = '-MODIFY_ADD_{}-'.format(prev_num)
                window[prev_key].update(visible=True)

            window['-MODIFY-'].update(visible=False)
            window['-MODIFY-'].expand(expand_y=True, expand_row=True)
            window.refresh()
            window['-MODIFY-'].update(visible=True)

            print('Info: deleting modify column rule {RULE} with key {KEY}'.format(RULE=elem_num, KEY=mod_key))
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
    width = mod_const.WIN_WIDTH - 40

    to_title = 'Collection' if to_title is None else to_title
    from_title = 'Source' if from_title is None else from_title

    column_map = column_map if column_map is not None else {i: i for i in to_df.columns.values.tolist()}
    column_header = list(column_map.values())

    to_df = to_df.copy()
    from_df = from_df.copy()

    to_df.rename(columns=column_map, inplace=True)
    from_df.rename(columns=column_map, inplace=True)

    # Window and element size parameters
    pad_frame = mod_const.FRAME_PAD
    pad_v = mod_const.VERT_PAD
    pad_el = mod_const.ELEM_PAD

    bg_col = mod_const.ACTION_COL
    header_col = mod_const.HEADER_COL

    main_font = mod_const.MAIN_FONT
    header_font = mod_const.HEADER_FONT

    # Layout
    title_layout = [[sg.Canvas(size=(0, 1), pad=(0, pad_v), visible=True, background_color=header_col)],
                    [sg.Text('Associate Data Records', pad=((pad_frame, 0), (0, pad_v)), font=header_font,
                             background_color=header_col)]]

    main_layout = [[mod_lo.create_table_layout(mod_dm.format_display_table(from_df, column_map).values.tolist(),
                                               column_header, '-FROM-', events=True,
                                               tooltip='Double-click row to add row to the collection', nrow=10,
                                               width=int(width / 2), font=main_font, pad=(pad_frame, pad_frame),
                                               table_name=from_title),
                    mod_lo.create_table_layout(mod_dm.format_display_table(to_df, column_map).values.tolist(), column_header,
                                           '-TO-', events=True,
                                               tooltip='Double-click row to remove row from the collection', nrow=10,
                                               width=int(width / 2), font=main_font, pad=(pad_frame, pad_frame),
                                               table_name=to_title)]]

    bttn_layout = [[sg.Col([[mod_lo.B2('Cancel', key='-CANCEL-', disabled=False, tooltip='Cancel selections')]],
                           pad=(0, 0), justification='l', expand_x=True),
                    sg.Col([[sg.Canvas(size=(0, 0), visible=True)]], justification='c', expand_x=True),
                    sg.Col([[mod_lo.B2('Save', key='-SAVE-', pad=((0, pad_el), 0), tooltip='Save selections')]],
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
            window['-FROM-'].update(values=mod_dm.format_display_table(from_df, column_map).values.tolist())
            window['-TO-'].update(values=mod_dm.format_display_table(to_df, column_map).values.tolist())

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
            window['-FROM-'].update(values=mod_dm.format_display_table(from_df, column_map).values.tolist())
            window['-TO-'].update(values=mod_dm.format_display_table(to_df, column_map).values.tolist())

            continue

        if event == '-SAVE-':  # click 'Save' button
            # Add selected rows to the to_df
            break

    window.close()
    layout = None
    window = None
    gc.collect()

    return select_rows


def record_import_window(user, record_layout, table, win_size: tuple = None, enable_new: bool = False):
    """
    Display the import from database window.
    """
    if win_size:
        width, height = win_size
    else:
        width, height = (mod_const.WIN_WIDTH, mod_const.WIN_HEIGHT)

    # Layout
    record_col = None
    for display_col in table.display_columns:
        colname = table.display_columns[display_col]
        if colname == 'RecordID':
            record_col = display_col
            break

    if record_col is None:
        print('Error: "RecordID" is a required display column')
        return None

    # Window and element size parameters
    header_col = mod_const.HEADER_COL
    bg_col = mod_const.ACTION_COL

    header_font = mod_const.HEADER_FONT

    pad_el = mod_const.ELEM_PAD
    pad_v = mod_const.VERT_PAD
    pad_frame = mod_const.FRAME_PAD

    # Title
    title = 'Import {TYPE} records'.format(TYPE=table.title)
    title_layout = [[sg.Canvas(size=(0, 1), pad=(0, pad_v), visible=True, background_color=header_col)],
                    [sg.Text(title, pad=((pad_frame, 0), (0, pad_v)), font=header_font,
                             background_color=header_col)]]

    # Import data table
    main_layout = [[table.layout(width=width, height=height, padding=(0, 0))]]

    # Control buttons
    bttn_layout = [[sg.Col([[mod_lo.B2('Cancel', key='-CANCEL-', disabled=False, tooltip='Cancel data import')]],
                           pad=(0, 0), justification='l', expand_x=True),
                    sg.Col([[sg.Canvas(size=(0, 0), visible=True)]], justification='c', expand_x=True),
                    sg.Col([[mod_lo.B2('New', key='-NEW-', pad=((0, pad_el), 0), visible=enable_new,
                                       tooltip='Create new record'),
                             mod_lo.B2('OK', key='-OK-', disabled=True, tooltip='Import selected data')]],
                           pad=(0, 0), justification='r')]]

    layout = [[sg.Col(title_layout, pad=(0, 0), justification='l', background_color=header_col, expand_x=True)],
              [sg.Col(main_layout, pad=(pad_frame, (pad_frame, 0)), background_color=bg_col, justification='c')],
              [sg.Col(bttn_layout, pad=(pad_frame, (pad_v, pad_frame)), expand_x=True)]]

    # Finalize GUI window
    window = sg.Window('', layout, modal=True, resizable=False)
    window.finalize()

    screen_w, screen_h = window.get_screen_dimensions()
    win_w = int(screen_w * 0.8)
    win_h = int(screen_h * 0.8)

    table.resize(window, size=(win_w, win_h))

    window = center_window(window)

    # Set table datatypes
    table.df = table.set_datatypes(table.df)

    # Update display with default filter values
    tbl_key = table.key_lookup('Element')
    table_elements = [i for i in table.elements if i != tbl_key]

    display_df = table.update_display(window)

    # Main loop
    while True:
        event, values = window.read(timeout=500)

        if event in (sg.WIN_CLOSED, '-CANCEL-'):  # selected close-window or Cancel
            record = None
            break

        if event == '-NEW-':  # selected to create a new record
            if table.record_type is None:
                msg = 'Failed to create a new record - missing required configuration parameter "RecordType"'
                popup_error(msg)
                print('Warning: {}'.format(msg))
                record = None

                break

            # Create a new record object
            record_entry = configuration.records.fetch_rule(table.record_type)

            record_id = record_entry.create_id(table.creation_date)
            print('Info: RecordEntry {NAME}: creating new record {ID}'.format(NAME=record_entry.name, ID=record_id))

            record_data = pd.Series(index=list(table.columns))
            record_data['RecordID'] = record_id
            record_data['RecordDate'] = table.creation_date

            record_type = record_entry.group
            if record_type in ('transaction', 'bank_statement', 'cash_expense'):
                record_class = mod_records.DatabaseRecord
            elif record_type == 'account':
                record_class = mod_records.AccountRecord
            elif record_type == 'bank_deposit':
                record_class = mod_records.DepositRecord
            elif record_type == 'audit':
                record_class = mod_records.TAuditRecord
            else:
                print('Warning: unknown record layout type provided {}'.format(record_type))
                record = None

                break

            record = record_class(record_entry.name, record_layout, record_data, new_record=True, referenced=False)

            break

        # Enable the OK button if a record is selected
        if values[tbl_key]:
            window['-OK-'].update(disabled=False)

        # Disable the OK button if no record is selected
        if not values[tbl_key]:
            window['-OK-'].update(disabled=True)

        if event == '-OK-':  # click 'OK' button
            # retrieve selected row
            try:
                row = values[tbl_key][0]
            except IndexError:
                continue
            else:
                record_id = display_df.at[row, record_col]
                try:
                    trans_df = table.df[table.df['RecordID'] == record_id]
                except KeyError:
                    print('warning: missing required column "RecordID"')
                    return None
                else:
                    if trans_df.empty:
                        print('Warning: could not find record {ID} in data table'.format(ID=record_id))
                        return None
                    else:
                        record_data = trans_df.iloc[0]

                # Set the record object based on the record type
                record_type = table.record_type
                record_group = configuration.records.fetch_rule(record_type).group
                if record_group in ('transaction', 'bank_statement', 'cash_expense'):
                    record_class = mod_records.DatabaseRecord
                elif record_group == 'account':
                    record_class = mod_records.AccountRecord
                elif record_group == 'bank_deposit':
                    record_class = mod_records.DepositRecord
                elif record_group == 'audit':
                    record_class = mod_records.TAuditRecord
                else:
                    print('Warning: unknown record layout type provided {}'.format(record_type))
                    record_class = None

                try:
                    record = record_class(record_type, record_layout, record_data, new_record=False)
                except Exception as e:
                    raise
                    print(e)
                    record = None

                break

        # Run table events
        if event in table_elements:
            display_df = table.run_event(window, event, values, user)
            continue

    window.close()
    layout = None
    window = None
    gc.collect()

    return record


def import_window(df, win_size: tuple = None):
    """
    Display the importer window.
    """
    if win_size:
        width, height = [i * 0.8 for i in win_size]
    else:
        width, height = (mod_const.WIN_WIDTH * 0.8, mod_const.WIN_HEIGHT * 0.8)

    # Format dataframe as list for input into sg
    data = df.values.tolist()
    header = df.columns.values.tolist()
    all_rows = list(range(df.shape[0]))

    # Window and element size parameters
    font_h = mod_const.HEADER_FONT
    main_font = mod_const.MAIN_FONT

    pad_v = mod_const.VERT_PAD
    pad_el = mod_const.ELEM_PAD
    pad_frame = mod_const.FRAME_PAD

    bg_col = mod_const.ACTION_COL
    tbl_bg_col = mod_const.TBL_BG_COL
    tbl_alt_col = mod_const.TBL_ALT_COL
    tbl_vfy_col = mod_const.TBL_VFY_COL
    header_col = mod_const.HEADER_COL

    # GUI layout
    bttn_layout = [[mod_lo.B2(_('Cancel'), key='-CANCEL-', pad=(pad_el, 0), tooltip=_('Cancel import')),
                    mod_lo.B2(_('Import'), bind_return_key=True, key='-IMPORT-', pad=(pad_el, 0),
                              tooltip=_('Import the selected transaction orders'))]]

    tbl_key = mod_lo.as_key('Import Table')
    layout = [[sg.Col([[sg.Text(_('Import Missing Data'), pad=(pad_frame, (pad_frame, pad_v)),
                                background_color=header_col, font=font_h)]],
                      pad=(0, 0), background_color=header_col, justification='l', expand_x=True, expand_y=True)],
              [sg.Frame('', [[mod_lo.create_table_layout(data, header, tbl_key, bind=True, height=height, width=width,
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
    bg_col = mod_const.ACTION_COL
    header_font = mod_const.HEADER_FONT
    sub_font = mod_const.BOLD_MID_FONT
    text_font = mod_const.MID_FONT
    pad_frame = mod_const.FRAME_PAD
    pad_el = mod_const.ELEM_PAD
    header_col = mod_const.HEADER_COL

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
        width, height = (mod_const.WIN_WIDTH * 0.6, mod_const.WIN_HEIGHT * 0.6)

    # Window and element size parameters
    pad_el = mod_const.ELEM_PAD
    pad_frame = mod_const.FRAME_PAD
    pad_v = mod_const.VERT_PAD

    font_h = mod_const.HEADER_FONT
    header_col = mod_const.HEADER_COL

    bg_col = mod_const.ACTION_COL

    # GUI layout
    ## Buttons
    bttn_layout = [[mod_lo.B2(_('Cancel'), key='-CANCEL-', pad=(pad_el, 0), tooltip=_('Cancel edit')),
                    mod_lo.B2(_('Save'), key='-SAVE-', bind_return_key=True, pad=(pad_el, 0),
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


def edit_row_window(row, edit_columns: dict = None, header_map: dict = None, win_size: tuple = None):
    """
    Display window for user to add or edit a row.

    Arguments:
        row (DataFrame): pandas series containing the row data.

        edit_columns (dict): dictionary of columns that are editable.

        header_map (dict): dictionary mapping dataframe columns to display columns.

        win_size (tuple): tuple containing the window width and height.
    """
    is_float_dtype = pd.api.types.is_float_dtype
    is_integer_dtype = pd.api.types.is_integer_dtype
    is_datetime_dtype = pd.api.types.is_datetime64_any_dtype
    is_bool_dtype = pd.api.types.is_bool_dtype

    if not isinstance(edit_columns, dict) and edit_columns is not None:
        print('TypeError: argument edit_columns must be a dictionary but has current type {TYPE}'
              .format(TYPE=type(edit_columns)))
        return row

    if win_size:
        width, height = win_size
    else:
        width, height = (mod_const.WIN_WIDTH, mod_const.WIN_HEIGHT)

    # Format dataframe as a list for the gui
    header = row.index.tolist()

    if header_map is None:
        header_map = {i: i for i in header}

    display_header = []
    for column in header_map:
        if column in header:
            display_header.append(column)
        else:
            continue

    edit_keys = {}
    if edit_columns is not None:
        for column in edit_columns:
            if column not in display_header:
                print('Warning: editable column {COL} not found in the display header'.format(COL=column))
                continue

            element_key = mod_lo.as_key(column)
            edit_keys[column] = element_key

    # Window and element size parameters
    main_font = mod_const.MAIN_FONT
    font_size = main_font[1]

    pad_el = mod_const.ELEM_PAD
    pad_frame = mod_const.FRAME_PAD
    pad_v = mod_const.VERT_PAD

    header_col = mod_const.TBL_HEADER_COL
    in_col = mod_const.INPUT_COL

    # GUI layout
    ## Buttons
    bttn_layout = [[mod_lo.B2(_('Cancel'), key='-CANCEL-', pad=(pad_el, 0), tooltip=_('Cancel edit')),
                    mod_lo.B2(_('Save'), key='-SAVE-', bind_return_key=True, pad=(pad_el, 0),
                              tooltip=_('Save changes'))]]

    ## Table
    lengths = mod_dm.calc_column_widths(display_header, width=width, font_size=font_size, pixels=False)

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
                column_type = edit_columns[display_column]['ElementType']
            except KeyError:
                column_type = 'string'
        else:
            element_key = mod_lo.as_key(display_column)
            readonly = True
            column_type = 'string'

        if column_type == 'dropdown':
            try:
                values = edit_columns[display_column]['Values']
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
            break

        if event == '-SAVE-':  # click 'Save' button
            ready_to_save = []
            for column in edit_keys:
                col_key = edit_keys[column]
                input_val = values[col_key]

                # Get data type of column
                try:
                    dtype = edit_columns[column]['ElementType'].lower()
                except (KeyError, TypeError):
                    dtype = row[column].dtype
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
                    row[column] = field_val
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

    return row


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
        width, height = (mod_const.WIN_WIDTH, mod_const.WIN_HEIGHT)

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
        element_key = mod_lo.as_key(column)
        edit_keys[column] = element_key

    # Window and element size parameters
    main_font = mod_const.MAIN_FONT
    font_size = main_font[1]

    pad_el = mod_const.ELEM_PAD
    pad_frame = mod_const.FRAME_PAD
    pad_v = mod_const.VERT_PAD

    header_col = mod_const.TBL_HEADER_COL
    in_col = mod_const.INPUT_COL

    # GUI layout
    ## Buttons
    #    if edit is True and index > 0:
    bttn_layout = [[mod_lo.B2(_('Cancel'), key='-CANCEL-', pad=(pad_el, 0), tooltip=_('Cancel edit')),
                    mod_lo.B2(_('Save'), key='-SAVE-', bind_return_key=True, pad=(pad_el, 0),
                              tooltip=_('Save changes'))]]

    ## Table
    lengths = mod_dm.calc_column_widths(display_header, width=width, font_size=font_size, pixels=False)

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
            element_key = mod_lo.as_key(display_column)
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

    window = sg.Window(_('Edit Row'), layout, modal=True, resizable=False)
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


def center_window(window):
    """
    Center a secondary window on the screen.
    """
    screen_w, screen_h = window.get_screen_dimensions()

    print('real window size is {}'.format(window.size))
    win_w, win_h = window.size
    win_x = int(screen_w / 2 - win_w / 2)
    win_y = int(screen_h / 2 - win_h / 2)
    print('window new location is ({}, {})'.format(win_x, win_y))
    if win_x + win_w > screen_w:
        win_x = screen_w - win_w
    if win_y + win_h > screen_h:
        win_y = screen_h - win_h

    window.move(win_x, win_y)
    window.refresh()
    print('window real location is {}'.format(window.current_location()))

    return window


def highlight_bool(s, column: str = 'Success'):
    """
    Annotate a pandas dataframe
    """
    ncol = len(s)
    if s[column] is True or s[column] == 1:
        return ['background-color: {}'.format(mod_const.PASS_COL)] * ncol
    else:
        return ['background-color: {}'.format(mod_const.FAIL_COL)] * ncol