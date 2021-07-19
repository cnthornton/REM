"""
REM Layout classes and functions.
"""
import PySimpleGUI as sg

import REM.constants as mod_const
import REM.data_manipulation as mod_dm
from REM.client import logger, settings, user


# Schema Layout Classes

# GUI Element Functions
def B1(*args, **kwargs):
    """
    Action button element defaults.
    """
    size = mod_const.B1_SIZE
    return sg.Button(*args, **kwargs, size=(size, 1))


def B2(*args, **kwargs):
    """
    Panel button element defaults.
    """
    size = mod_const.B2_SIZE
    return sg.Button(*args, **kwargs, size=(size, 1))


def create_table_layout(data, header, keyname, events: bool = False, bind: bool = False, tooltip: str = None,
                        nrow: int = None, height: int = 800, width: int = 1200, font: tuple = None, pad: tuple = None,
                        add_key: str = None, delete_key: str = None, total_key: str = None, table_name: str = ''):
    """
    Create table elements that have consistency in layout.
    """
    # Element settings
    text_col = mod_const.TEXT_COL
    alt_col = mod_const.TBL_ALT_COL
    bg_col = mod_const.TBL_BG_COL
    select_col = mod_const.TBL_SELECT_COL
    header_col = mod_const.HEADER_COL

    pad_frame = mod_const.FRAME_PAD

    pad = pad if pad else (pad_frame, pad_frame)
    pad_el = mod_const.ELEM_PAD
    pad_v = mod_const.VERT_PAD

    font = font if font else mod_const.LARGE_FONT
    bold_font = mod_const.BOLD_FONT
    font_size = font[1]

    # Arguments
    row_height = mod_const.TBL_ROW_HEIGHT
    width = width
    height = height * 0.5
    nrow = nrow if nrow else int(height / 40)

    # Parameters
    if events and bind:
        bind = False  # only one can be selected at a time
        logger.warning('both bind_return_key and enable_events have been selected during table creation. '
                       'These parameters are mutually exclusive.')

    lengths = mod_dm.calc_column_widths(header, width=width, font_size=font_size, pixels=False)

    header_layout = []
    balance_layout = []
    if add_key:
        header_layout.append(sg.Button('', key=add_key, image_data=mod_const.ADD_ICON, border_width=2,
                                       button_color=(text_col, alt_col), tooltip='Add new row to table'))
        balance_layout.append(sg.Canvas(size=(24, 0), visible=True, background_color=header_col))
    if delete_key:
        header_layout.append(sg.Button('', key=delete_key, image_data=mod_const.MINUS_ICON, border_width=2,
                                       button_color=(text_col, alt_col), tooltip='Remove selected row from table'))
        balance_layout.append(sg.Canvas(size=(24, 0), visible=True, background_color=header_col))

    if table_name or len(header_layout) > 0:
        top_layout = [sg.Col([balance_layout], justification='r', background_color=header_col, expand_x=True),
                      sg.Col([[sg.Text(table_name, pad=(0, 0), font=bold_font, background_color=alt_col)]],
                             justification='c', background_color=header_col, expand_x=True),
                      sg.Col([header_layout], justification='l', background_color=header_col)]
        frame_relief = 'ridge'
    else:
        top_layout = [sg.Canvas(size=(0, 0))]
        frame_relief = 'flat'

    middle_layout = [sg.Table(data, key=keyname, headings=header, pad=(0, 0), num_rows=nrow,
                              row_height=row_height, alternating_row_color=alt_col, background_color=bg_col,
                              text_color=text_col, selected_row_colors=(text_col, select_col), font=font,
                              display_row_numbers=False, auto_size_columns=False, col_widths=lengths,
                              enable_events=events, bind_return_key=bind, tooltip=tooltip, vertical_scroll_only=False)]

    if total_key:
        bottom_layout = [sg.Col([[sg.Text('Total:', pad=((0, pad_el), 0), font=bold_font, background_color=alt_col),
                                  sg.Text('', key=total_key, size=(14, 1), pad=((pad_el, 0), 0), font=font,
                                          background_color=bg_col, justification='r', relief='sunken')]],
                                pad=(0, (pad_v, 0)), background_color=alt_col, justification='r')]
    else:
        bottom_layout = [sg.Canvas(size=(0, 0))]

    layout = sg.Frame('', [top_layout, middle_layout, bottom_layout], pad=pad, element_justification='l',
                      vertical_alignment='t', background_color=alt_col, relief=frame_relief)

    return layout


def importer_layout(win_size: tuple = None):
    """
    Create the layout for the database import window.
    """
    if win_size:
        width, height = win_size
    else:
        width, height = (int(mod_const.WIN_WIDTH * 0.9), int(mod_const.WIN_HEIGHT * 0.9))

    # Layout settings
    header_col = mod_const.HEADER_COL
    input_col = mod_const.INPUT_COL
    bg_col = mod_const.ACTION_COL
    def_col = mod_const.DEFAULT_COL
    select_col = mod_const.SELECT_TEXT_COL
    text_col = mod_const.TEXT_COL

    pad_el = mod_const.ELEM_PAD
    pad_v = mod_const.VERT_PAD
    pad_h = mod_const.HORZ_PAD
    pad_frame = mod_const.FRAME_PAD

    font_h = mod_const.HEADER_FONT
    font_bold = mod_const.BOLD_FONT
    font_main = mod_const.MAIN_FONT
    font_large = mod_const.BOLD_HEADER_FONT

    # Keyboard shortcuts
    hotkeys = settings.hotkeys
    cancel_shortcut = hotkeys['-HK_ESCAPE-'][2]
    save_shortcut = hotkeys['-HK_ENTER-'][2]
    next_shortcut = hotkeys['-HK_RIGHT-'][2]
    back_shortcut = hotkeys['-HK_LEFT-'][2]

    # Element sizes
    bwidth = 0.5

    # Element selection options
    try:
        db_tables = user.database_tables(settings.prog_db)
    except ValueError:
        db_tables = []

    file_types = ['xls', 'csv/tsv']
    encodings = ['Default']

    header_req = ['Table Column Name', 'Data Type', 'Default Value']
    header_map = ['Table Column Name', 'Data Type', 'File Column Name']

    record_types = settings.records.print_rules(by_title=True)

    cond_operators = ['=', '!=', '>', '<', '>=', '<=']
    math_operators = ['+', '-', '*', '/', '%']

    # Window Layout

    # Subset layout
    subset_keys = ['-SUBSET_{}-'.format(i) for i in range(10)]
    subset_layout = [[sg.Canvas(size=(int(width * 0.85) - 40, 0), background_color=bg_col)]]
    for index, subset_key in enumerate(subset_keys):
        oper_key = '-SUBSET_OPER_{}-'.format(index)
        value_key = '-SUBSET_VALUE_{}-'.format(index)
        col_key = '-SUBSET_COL_{}-'.format(index)
        add_key = '-SUBSET_ADD_{}-'.format(index)
        delete_key = '-SUBSET_DELETE_{}-'.format(index)

        if index == 0:  # no delete key
            visible = True
            subset_bttn_layout = [[sg.Button('', key=add_key, image_data=mod_const.ADD_ICON, border_width=1,
                                             button_color=(text_col, bg_col))]]
        elif index == 9:  # no add key
            visible = False
            subset_bttn_layout = [[sg.Button('', key=delete_key, image_data=mod_const.MINUS_ICON, pad=(0, 0),
                                             border_width=1, button_color=(text_col, bg_col))]]
        else:
            visible = False
            subset_bttn_layout = [[sg.Button('', key=delete_key, image_data=mod_const.MINUS_ICON, pad=((0, pad_el), 0),
                                             border_width=1, button_color=(text_col, bg_col)),
                                   sg.Button('', key=add_key, image_data=mod_const.ADD_ICON, border_width=1,
                                             button_color=(text_col, bg_col))]]

        subset_layout.append(
                [sg.Col([
                    [sg.Col([[sg.Text('Subset Rule {}:'.format(index + 1), pad=((0, pad_h), 0), font=font_bold,
                                      background_color=bg_col, auto_size_text=True)]],
                            justification='l', element_justification='l', background_color=bg_col),
                     sg.Col([[sg.Frame('', [
                         [sg.Text('Column:', pad=(pad_el, pad_el), background_color=def_col, font=font_main),
                          sg.Combo([], key=col_key, pad=((0, pad_h), pad_el), size=(12, 1),
                                   background_color=input_col, font=font_main),
                          sg.Text('Operator:', pad=((0, pad_el), pad_el), background_color=def_col),
                          sg.Combo(cond_operators, key=oper_key, pad=((0, pad_h), pad_el), size=(12, 1),
                                   font=font_bold, background_color=input_col),
                          sg.Text('Value:', pad=((0, pad_el), pad_el), background_color=def_col, font=font_main),
                          sg.Input('', key=value_key, pad=((0, pad_el), pad_el), size=(12, 1),
                                   background_color=bg_col, font=font_main)]],
                                       background_color=def_col, border_width=1)]],
                            justification='c', element_justification='l', background_color=bg_col, expand_x=True),
                     sg.Col(subset_bttn_layout, pad=(pad_h, 0), justification='r', element_justification='r',
                            background_color=bg_col)]],
                    key=subset_key, pad=(0, int(pad_el / 2)), visible=visible, expand_x=True,
                    background_color=bg_col, vertical_alignment='t', justification='l',
                    element_justification='l')])

    # Modify layout
    modify_keys = ['-MODIFY_{}-'.format(i) for i in range(10)]
    modify_layout = [[sg.Canvas(size=(int(width * 0.85) - 40, 0), background_color=bg_col)]]
    for index, modify_key in enumerate(modify_keys):
        oper_key = '-MODIFY_OPER_{}-'.format(index)
        value_key = '-MODIFY_VALUE_{}-'.format(index)
        col_key = '-MODIFY_COL_{}-'.format(index)
        add_key = '-MODIFY_ADD_{}-'.format(index)
        delete_key = '-MODIFY_DELETE_{}-'.format(index)

        if index == 0:  # no delete key
            visible = True
            modify_bttn_layout = [[sg.Button('', key=add_key, image_data=mod_const.ADD_ICON, border_width=1,
                                             button_color=(text_col, bg_col))]]
        elif index == 9:  # no add key
            visible = False
            modify_bttn_layout = [[sg.Button('', key=delete_key, image_data=mod_const.MINUS_ICON, pad=(0, 0),
                                             border_width=1, button_color=(text_col, bg_col))]]
        else:
            visible = False
            modify_bttn_layout = [[sg.Button('', key=delete_key, image_data=mod_const.MINUS_ICON, pad=((0, pad_el), 0),
                                             border_width=1, button_color=(text_col, bg_col)),
                                   sg.Button('', key=add_key, image_data=mod_const.ADD_ICON, border_width=1,
                                             button_color=(text_col, bg_col))]]

        modify_layout.append(
            [sg.Col([
                [sg.Col([[sg.Text('Modify Rule {}:'.format(index + 1), pad=((0, pad_h), 0), font=font_bold,
                                  background_color=bg_col, auto_size_text=True)]],
                        justification='l', element_justification='l', background_color=bg_col),
                 sg.Col([[sg.Frame('', [
                     [sg.Text('Column:', pad=(pad_el, pad_el), background_color=def_col, font=font_main),
                      sg.Combo([], key=col_key, pad=((0, pad_h), pad_el), size=(12, 1),
                               background_color=input_col, font=font_main),
                      sg.Text('Operator:', pad=((0, pad_el), pad_el), background_color=def_col),
                      sg.Combo(math_operators, key=oper_key, pad=((0, pad_h), pad_el), size=(12, 1),
                               font=font_bold, background_color=input_col),
                      sg.Text('Value:', pad=((0, pad_el), pad_el), background_color=def_col, font=font_main),
                      sg.Input('', key=value_key, pad=((0, pad_el), pad_el), size=(12, 1),
                               background_color=bg_col, font=font_main)]],
                                   background_color=def_col, border_width=1)]],
                        justification='c', element_justification='l', background_color=bg_col, expand_x=True),
                 sg.Col(modify_bttn_layout, pad=(pad_h, 0), justification='r', element_justification='r',
                        background_color=bg_col)]],
                key=modify_key, pad=(0, int(pad_el / 2)), visible=visible, expand_x=True,
                background_color=bg_col, vertical_alignment='t', justification='l',
                element_justification='l')])

    # Panel layout
    p1 = [[sg.Col([[sg.Text('File:', size=(5, 1), pad=((0, pad_el), 0), background_color=bg_col),
                    sg.Input('', key='-FILE-', size=(60, 1), pad=(pad_el, 0), background_color=input_col),
                    sg.FileBrowse('Browse ...', pad=((pad_el, pad_frame), 0))]],
                  pad=(pad_frame, (pad_frame, pad_v)), justification='l', background_color=bg_col)],
          [sg.Frame('File format', [
              [sg.Canvas(size=(int(width * 0.85), 0), background_color=bg_col)],
              [sg.Col([
                  [sg.Text('Format:', size=(16, 1), pad=(pad_el, pad_el), background_color=bg_col),
                   sg.Combo(file_types, key='-FORMAT-', default_value='xls', size=(12, 1),
                            pad=(pad_el, pad_el), background_color=input_col, tooltip='Format of the input file'),
                   sg.Text('', size=(10, 1), background_color=bg_col),
                   sg.Text('Newline Separator:', size=(16, 1), pad=(pad_el, pad_el), background_color=bg_col),
                   sg.Input('\\n', key='-NSEP-', size=(8, 1), pad=(pad_el, pad_el), disabled=True,
                            background_color=input_col,
                            tooltip='Character used in the CSV file to distinguish between rows')],
                  [sg.Text('Encoding:', size=(16, 1), pad=(pad_el, 0), background_color=bg_col),
                   sg.Combo(encodings, key='-ENCODE-', default_value='Default', size=(12, 1), pad=(pad_el, pad_el),
                            background_color=input_col),
                   sg.Text('', size=(10, 1), background_color=bg_col),
                   sg.Text('Field Separator:', size=(16, 1), pad=(pad_el, pad_el), background_color=bg_col),
                   sg.Input('\\t', key='-FSEP-', size=(8, 1), pad=(pad_el, pad_el), disabled=True,
                            background_color=input_col,
                            tooltip='Character used in the CSV file to distinguish between columns')]],
                  pad=(pad_v, pad_v), background_color=bg_col, vertical_alignment='t', expand_x=True, expand_y=True)]
          ],
                    pad=(pad_frame, pad_v), border_width=bwidth, background_color=bg_col, title_color=select_col,
                    relief='groove')],
          [sg.Frame('Formatting options', [
              [sg.Canvas(size=(int(width * 0.85), 0), background_color=bg_col)],
              [sg.Col([
                  [sg.Checkbox('Recognize dates', key='-DATES-', pad=(0, pad_el), default=True, font=font_main,
                               background_color=bg_col,
                               tooltip='Attempt to parse the values of columns containing dates.')],
                  [sg.Checkbox('Recognize integers', key='-INTS-', pad=(0, pad_el), default=True,
                               font=font_main, background_color=bg_col,
                               tooltip='Attempt to infer whether the data type of a column is an integer or float. '
                                       'This is especially relevant for excel files, which store all numeric values as '
                                       'decimals')],
                  [sg.Text('Skip n rows at top:', size=(28, 1), pad=(0, pad_el), background_color=bg_col,
                           font=font_main, tooltip='Do not import the first n rows'),
                   sg.Input('0', key='-TSKIP-', size=(8, 1), pad=(0, pad_el), font=font_main,
                            background_color=input_col)],
                  [sg.Text('Skip n rows at bottom:', size=(28, 1), pad=(0, pad_el), background_color=bg_col,
                           font=font_main, tooltip='Do not import the last n rows'),
                   sg.Input('0', key='-BSKIP-', size=(8, 1), pad=(0, pad_el), font=font_main,
                            background_color=input_col)],
                  [sg.Text('Header row (0 indexed):', size=(28, 1), pad=(0, pad_el), background_color=bg_col,
                           font=font_main, tooltip='Row number, starting at 0, containing the column names (applied '
                                                   'after filtering by skipped rows).'),
                   sg.Input('0', key='-HROW-', size=(8, 1), pad=(0, pad_el), font=font_main,
                            background_color=input_col)],
                  [sg.Text('Thousands separator:', size=(28, 1), pad=(0, pad_el), background_color=bg_col,
                           font=font_main,
                           tooltip='Thousands character used for parsing string columns into a numeric form'),
                   sg.Input(',', key='-TSEP-', size=(8, 1), pad=(0, pad_el), font=font_main,
                            background_color=input_col)],
                  [sg.Checkbox('Day before month', key='-DAYFIRST-', pad=(0, pad_el),
                               default=True, font=font_main, background_color=bg_col,
                               tooltip='When parsing a date, the day comes before the month (e.g DD/MM)')],
                  [sg.Checkbox('Year first', key='-YEARFIRST-', pad=(0, pad_el),
                               default=False, font=font_main, background_color=bg_col,
                               tooltip='When parsing a date, the year comes before the month and day (e.g YY/MM/DD)')]],
                  pad=(pad_v, pad_v), background_color=bg_col, vertical_alignment='t', expand_x=True, expand_y=True)]
          ],
                    pad=(pad_frame, (pad_v, pad_frame)), border_width=bwidth, background_color=bg_col,
                    title_color=select_col, relief='groove')]]
    p2 = [[sg.Col([[sg.Text('Database Table:', pad=((0, pad_el), 0), background_color=bg_col),
                    sg.Combo(db_tables, key='-TABLE-', size=(28, 1), pad=((0, pad_h), 0), enable_events=True,
                             background_color=input_col),
                    sg.Text('Record Type:', pad=((0, pad_el), 0), background_color=bg_col),
                    sg.Combo(record_types, key='-RECORDTYPE-', size=(28, 1), pad=(0, 0),
                             enable_events=True, background_color=input_col)]],
                  pad=(pad_frame, (pad_frame, pad_v)), justification='l', background_color=bg_col)],
          [sg.Frame('Required Columns', [
              [sg.Canvas(size=(int(width * 0.85), 0), background_color=bg_col)],
              [sg.Col([
                  [sg.Col([[sg.Listbox(values=[], key='-REQLIST-', size=(26, 8), font=font_main,
                                       background_color=bg_col, bind_return_key=True,
                                       tooltip='Double-click on a column name to add the column to the table')]],
                          background_color=bg_col, justification='l', element_justification='l', expand_x=True),
                   sg.Col([[create_table_layout([[]], header_req, '-REQCOL-', bind=True, pad=(0, 0), nrow=4,
                                                width=width * 0.65,
                                                tooltip='Click on a row to edit the row fields. Use the delete or '
                                                        'backspace keys to remove a row from the table')]],
                          background_color=bg_col, justification='r', element_justification='r')]],
                  pad=(pad_v, pad_v), background_color=bg_col, expand_x=True)]],
                    pad=(pad_frame, pad_v), border_width=bwidth, background_color=bg_col, title_color=select_col,
                    relief='groove', tooltip='Set static values for required import columns.')],
          [sg.Frame('Column Map', [
              [sg.Canvas(size=(int(width * 0.85), 0), background_color=bg_col)],
              [sg.Col([
                  [sg.Col([[sg.Listbox(values=[], key='-MAPLIST-', size=(26, 8), font=font_main,
                                       background_color=bg_col, bind_return_key=True,
                                       tooltip='Double-click on a column name to add the column to the table')]],
                          background_color=bg_col, justification='l', element_justification='l', expand_x=True),
                   sg.Col([[create_table_layout([[]], header_map, '-MAPCOL-', bind=True, pad=(0, 0), nrow=4,
                                                width=width * 0.65,
                                                tooltip='Click on a row to edit the row fields. Use the delete or '
                                                        'backspace keys to remove a row from the table')]],
                          background_color=bg_col, justification='r', element_justification='r')]],
                  pad=(pad_v, pad_v), background_color=bg_col, expand_x=True)]],
                    pad=(pad_frame, pad_v), border_width=bwidth, background_color=bg_col, title_color=select_col,
                    relief='groove', tooltip='Map imported file column names to database table column names')],
          [sg.Frame('Subset Table Rows', [
              [sg.Canvas(size=(int(width * 0.85), 0), background_color=bg_col)],
              [sg.Col(subset_layout, pad=(pad_v, pad_v), key='-SUBSET-',
                      background_color=bg_col, expand_x=True, expand_y=True,
                      vertical_alignment='t', scrollable=True, vertical_scroll_only=True, justification='l',
                      element_justification='l')]],
                    pad=(pad_frame, pad_v), background_color=bg_col, border_width=bwidth,
                    title_color=select_col, relief='groove', element_justification='l', vertical_alignment='t',
                    tooltip='Use the subset rules to subset table rows based on the values of the imported columns')],
          [sg.Frame('Modify Column Values', [
              [sg.Canvas(size=(int(width * 0.85), 0), background_color=bg_col)],
              [sg.Col(modify_layout, pad=(pad_v, pad_v), key='-MODIFY-',
                      background_color=bg_col, expand_x=True, expand_y=True,
                      vertical_alignment='t', scrollable=True, vertical_scroll_only=True, justification='l',
                      element_justification='l')]],
                    pad=(pad_frame, (pad_v, pad_frame)), background_color=bg_col, border_width=bwidth,
                    title_color=select_col, relief='groove', element_justification='l', vertical_alignment='t',
                    tooltip='Use the modify rules to modify the values of an imported column. Only date and numeric '
                            'columns support this operation.')]
          ]
    p3 = [[sg.Frame('Import Statistics', [
              [sg.Canvas(size=(int(width * 0.85), 0), background_color=bg_col)],
              [sg.Col([
                  [sg.Text('Database table:', size=(28, 1), pad=(0, pad_el), background_color=bg_col,
                           font=font_main),
                   sg.Text('0', key='-TABLENAME-', size=(12, 1), pad=(0, pad_el), font=font_main,
                           background_color=bg_col)],
                  [sg.Text('Number of columns selected:', size=(28, 1), pad=(0, pad_el), background_color=bg_col,
                           font=font_main),
                   sg.Text('0', key='-NCOL-', size=(12, 1), pad=(0, pad_el), font=font_main,
                           background_color=bg_col)],
                  [sg.Text('Number of rows to be imported:', size=(28, 1), pad=(0, pad_el), background_color=bg_col,
                           font=font_main),
                   sg.Text('0', key='-NROW-', size=(12, 1), pad=(0, pad_el), font=font_main, background_color=bg_col)
                   ]
              ], pad=(pad_v, pad_v), background_color=bg_col, vertical_alignment='t', expand_x=True, expand_y=True)]],
                    pad=(pad_frame, (pad_frame, pad_v)), border_width=bwidth, background_color=bg_col,
                    title_color=select_col, relief='groove')],
          [sg.Frame('Table Preview', [
              [sg.Canvas(size=(int(width * 0.85), 0), background_color=bg_col)],
              [sg.Col([
                  [create_table_layout([[]], ['{}'.format(i) for i in range(1)], '-PREVIEW-', pad=(0, 0), nrow=15,
                                       width=width * 0.94, tooltip='Preview of the first 10 and last 10 records that '
                                                                   'will be imported into the database table')]],
                  pad=(pad_v, pad_v), background_color=bg_col, expand_x=True, expand_y=True,
                  element_justification='c', vertical_alignment='c')]],
                    pad=(pad_frame, (pad_v, pad_frame)), border_width=bwidth, background_color=bg_col,
                    title_color=select_col, relief='groove')]]

    panels = [sg.Col(p1, key='-P1-', background_color=bg_col, vertical_alignment='c', visible=True, expand_y=True,
                     expand_x=True),
              sg.Col(p2, key='-P2-', background_color=bg_col, vertical_alignment='c', visible=False, expand_y=True,
                     expand_x=True),
              sg.Col(p3, key='-P3-', background_color=bg_col, vertical_alignment='c', visible=False, expand_y=True,
                     expand_x=True)]

    panel_layout = [[sg.Col([[sg.Canvas(size=(0, height * 0.9), background_color=bg_col)]], background_color=bg_col),
                     sg.Col([[sg.Pane(panels, key='-PANELS-', orientation='horizontal', show_handle=False,
                                      border_width=0, relief='flat')]], pad=(0, pad_v), expand_x=True)]]

    bttn_layout = [[sg.Button('', key='-BACK-', image_data=mod_const.LEFT_ICON, image_size=mod_const.BTTN_SIZE,
                              pad=(pad_el, 0), disabled=True,
                              tooltip='Return to previous panel ({})'.format(back_shortcut)),
                    sg.Button('', key='-NEXT-', image_data=mod_const.RIGHT_ICON, image_size=mod_const.BTTN_SIZE,
                              pad=(pad_el, 0), disabled=False,
                              tooltip='Move to next panel ({})'.format(next_shortcut)),
                    sg.Button('', bind_return_key=True, image_data=mod_const.SAVE_ICON, image_size=mod_const.BTTN_SIZE,
                              key='-IMPORT-', pad=(pad_el, 0), disabled=True,
                              tooltip='Import file contents to the selected database table ({})'.format(save_shortcut)),
                    sg.Button('', key='-CANCEL-', image_data=mod_const.CANCEL_ICON, image_size=mod_const.BTTN_SIZE,
                              pad=(pad_el, 0), disabled=False,
                              tooltip='Cancel importing records to the database ({})'.format(cancel_shortcut))]]

    sidebar_layout = [
        [sg.Col([[sg.Canvas(size=(0, height * 0.9), background_color=def_col)]], background_color=def_col),
         sg.Col([[sg.Text('• ', pad=((pad_frame, pad_el), (pad_frame, pad_el)), font=font_large),
                  sg.Text('File Options', key='-PN1-', pad=((pad_el, pad_frame), (pad_frame, pad_el)),
                          font=font_main, text_color=select_col)],
                 [sg.Text('• ', pad=((pad_frame, pad_el), pad_el), font=font_large),
                  sg.Text('Import Options', key='-PN2-', pad=((pad_el, pad_frame), pad_el), font=font_main)],
                 [sg.Text('• ', pad=((pad_frame, pad_el), pad_el), font=font_large),
                  sg.Text('Data Preview', key='-PN3-', pad=((pad_el, pad_frame), pad_el), font=font_main)]],
                background_color=def_col, element_justification='l', vertical_alignment='t', expand_y=True)]]

    layout = [[sg.Col([[sg.Text('Import to Database', pad=(pad_frame, (pad_frame, pad_v)),
                                font=font_h, background_color=header_col)]],
                      pad=(0, 0), justification='l', background_color=header_col, expand_x=True, expand_y=True)],
              [sg.Frame('', sidebar_layout, border_width=bwidth, title_color=text_col, relief='solid',
                        background_color=def_col),
               sg.Frame('', panel_layout, border_width=bwidth, title_color=text_col, relief='solid',
                        background_color=bg_col)],
              [sg.Col(bttn_layout, justification='r', pad=(pad_frame, (pad_v, pad_frame)))]]

    return layout


# Panel layouts
def home_screen(win_size: tuple = None):
    """
    Create layout for the home screen.
    """
    bg_col = mod_const.DEFAULT_COL
    if win_size:
        width, height = win_size
    else:
        width, height = (mod_const.WIN_WIDTH, mod_const.WIN_HEIGHT)

#    layout = sg.Col([[sg.Image(filename=settings.logo, size=(int(width), int(height)),
    layout = sg.Col([[sg.Image(filename=settings.logo, background_color=bg_col)]],
                    key='-HOME-', element_justification='c', vertical_alignment='c', background_color=bg_col)

    return layout

