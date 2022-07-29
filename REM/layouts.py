"""
REM Layout classes and functions.
"""
import PySimpleGUI as sg

import REM.constants as mod_const
import REM.data_manipulation as mod_dm
from REM.client import logger, settings, user


# Modifier functions
def set_size(window, element_key, size):
    """
    Set new size for container-like elements.
    """
    options = {'width': size[0], 'height': size[1]}

    element = window[element_key]
    try:
        scrollable = element.Scrollable
    except AttributeError:
        scrollable = False

    if scrollable:
        element.Widget.canvas.configure(**options)
        element.contents_changed()
    else:
        element.Widget.pack_propagate(0)
        element.set_size(size)

    window.refresh()


# GUI Element Functions
def generate_layout(etype, attributes):
    """
    Generate a layout for different element types.
    """
    func_mapper = {'input': input_layout, 'multiline': multiline_layout, 'dropdown': combo_layout,
                   'checkbox': checkbox_layout, 'text': text_layout}
    try:
        layout_func = func_mapper[etype]
    except KeyError:
        logger.warning('unknown element type "{ETYPE}" provided'.format(ETYPE=etype))
        layout_func = func_mapper['text']

    layout = layout_func(attributes)

    return layout


def text_layout(attributes):
    # Standard element parameters
    font = attributes.get('Font', mod_const.LARGE_FONT)
    size = attributes.get('Size', None)
    bw = attributes.get('BW', 0)
    pad = attributes.get('Pad', None)
    bg_col = attributes.get('BackgroundColor', mod_const.DEFAULT_BG_COLOR)
    text_col = attributes.get('TextColor', mod_const.DISABLED_TEXT_COLOR)
    tooltip = attributes.get('Tooltip', None)
    events = not attributes.get('Disabled', False)

    # Element layout
    elem_key = attributes['Key']
    display_value = attributes.get('DisplayValue', None)
    layout = [sg.Text(display_value, key=elem_key, enable_events=events, size=size, pad=pad, background_color=bg_col,
                      text_color=text_col, font=font, border_width=bw, relief='sunken', tooltip=tooltip)]

    return layout


def input_layout(attributes):
    # Standard element parameters
    font = attributes.get('Font', mod_const.LARGE_FONT)
    size = attributes.get('Size', None)
    pad = attributes.get('Pad', None)
    bw = attributes.get('BW', 1)
    bg_col = attributes.get('BackgroundColor', mod_const.DEFAULT_BG_COLOR)
    text_col = attributes.get('TextColor', mod_const.DEFAULT_TEXT_COLOR)

    disabled = attributes.get('Disabled', False)
    tooltip = attributes.get('Tooltip', None)

    # Element layout
    elem_key = attributes['Key']
    display_value = attributes.get('DisplayValue', '')
    layout = [sg.Input(display_value, key=elem_key, enable_events=True, disabled=disabled, size=size, pad=pad,
                       font=font, background_color=bg_col, text_color=text_col, border_width=bw,
                       disabled_readonly_background_color=bg_col, disabled_readonly_text_color=text_col,
                       tooltip=tooltip, metadata={'disabled': disabled})]

    return layout


def combo_layout(attributes):
    # Standard element parameters
    font = attributes.get('Font', mod_const.LARGE_FONT)
    size = attributes.get('Size', None)
    pad = attributes.get('Pad', None)
    bg_col = attributes.get('BackgroundColor', mod_const.DEFAULT_BG_COLOR)
    text_col = attributes.get('TextColor', mod_const.DEFAULT_TEXT_COLOR)

    disabled = attributes.get('Disabled', False)
    tooltip = attributes.get('Tooltip', None)

    # Combobox parameters
    values = attributes.get('ComboValues', [])

    # Element layout
    elem_key = attributes['Key']
    display_value = attributes.get('DisplayValue', '')
    layout = [sg.Combo(values, default_value=display_value, key=elem_key, enable_events=True, size=size, pad=pad,
                       font=font, text_color=text_col, background_color=bg_col,
                       button_arrow_color=mod_const.BORDER_COLOR, button_background_color=bg_col,
                       expand_x=True, expand_y=True,
                       disabled=disabled, tooltip=tooltip, metadata={'disabled': disabled})]

    return layout


def multiline_layout(attributes):
    # Standard element parameters
    font = attributes.get('Font', mod_const.LARGE_FONT)
    size = attributes.get('Size', None)
    pad = attributes.get('Pad', None)
    bw = attributes.get('BW', 1)
    bg_col = attributes.get('BackgroundColor', mod_const.DEFAULT_BG_COLOR)
    def_text_col = attributes.get('TextColor', mod_const.DEFAULT_TEXT_COLOR)
    disabled_text_col = mod_const.DISABLED_TEXT_COLOR

    disabled = attributes.get('Disabled', False)
    tooltip = attributes.get('Tooltip', None)

    if disabled:
        text_col = disabled_text_col
    else:
        text_col = def_text_col

    # Multiline parameters
    height = attributes.get('NRow', 1)
    width = size[0]

    # Element layout
    elem_key = attributes['Key']
    display_value = attributes.get('DisplayValue', '')
    layout = [sg.Multiline(display_value, key=elem_key, size=(width, height), pad=pad, font=font, disabled=disabled,
                           background_color=bg_col, text_color=text_col, border_width=bw,
                           tooltip=tooltip, metadata={'disabled': disabled})]

    return layout


def checkbox_layout(attributes):
    # Standard element parameters
    font = attributes.get('Font', mod_const.LARGE_FONT)
    size = attributes.get('Size', None)
    pad = attributes.get('Pad', None)
    bg_col = attributes.get('BackgroundColor', mod_const.DEFAULT_BG_COLOR)
    text_col = attributes.get('TextColor', mod_const.DEFAULT_TEXT_COLOR)

    disabled = attributes.get('Disabled', False)
    tooltip = attributes.get('Tooltip', None)

    # Checkbox settings
    box_col = bg_col if not disabled else mod_const.DISABLED_BG_COLOR

    width, height = size
    elem_w = 0
    elem_h = height

    # Parameter settings
    elem_key = attributes['Key']
    display_value = attributes.get('DisplayValue', False)
    layout = [sg.Checkbox('', default=display_value, key=elem_key, enable_events=True, disabled=disabled,
                          size=(elem_w, elem_h), pad=pad, font=font, background_color=bg_col, text_color=text_col,
                          checkbox_color=box_col, tooltip=tooltip, metadata={'disabled': disabled})]

    return layout


def button_layout(bttn_key, icon: str = None, **kwargs):
    """
    Program button layout.
    """
    # Button constants
    text_color = mod_const.DEFAULT_TEXT_COLOR
    disabled_text_color = mod_const.DISABLED_TEXT_COLOR
    bg_color = mod_const.BORDER_COLOR
    disabled_bg_color = mod_const.BORDER_COLOR
    highlight_color = mod_const.BUTTON_HOVER_COLOR
    size = mod_const.BTTN_SIZE

    bttn_icon = icon if icon is not None else mod_const.BLANK_ICON
    layout = sg.Button('', key=bttn_key, image_data=bttn_icon, image_size=size, button_color=(text_color, bg_color),
                       disabled_button_color=(disabled_text_color, disabled_bg_color),
                       mouseover_colors=(text_color, highlight_color), border_width=1, use_ttk_buttons=False, **kwargs)

    return layout


def create_table_layout(data, header, keyname, events: bool = False, bind: bool = False, tooltip: str = None,
                        nrow: int = None, height: int = 800, width: int = 1200, font: tuple = None, pad: tuple = None,
                        table_name: str = ''):
    """
    Create table elements that have consistency in layout.
    """
    # Element settings
    text_col = mod_const.DEFAULT_TEXT_COLOR
    alt_col = mod_const.TBL_ALT_COLOR
    bg_col = mod_const.TBL_BG_COLOR
    select_col = mod_const.TBL_SELECT_COLOR
    header_col = mod_const.HEADER_COLOR

    pad_frame = mod_const.FRAME_PAD
    pad = pad if pad else (pad_frame, pad_frame)

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

    if table_name:
        top_layout = [sg.Col([[sg.Text(table_name, pad=(0, 0), font=bold_font, background_color=alt_col)]],
                             justification='c', background_color=header_col, expand_x=True)]
        frame_relief = 'ridge'
    else:
        top_layout = [sg.Canvas(size=(0, 0))]
        frame_relief = 'flat'

    bottom_layout = [sg.Table(data, key=keyname, headings=header, pad=(0, 0), num_rows=nrow,
                              row_height=row_height, alternating_row_color=alt_col, background_color=bg_col,
                              text_color=text_col, selected_row_colors=(text_col, select_col), font=font,
                              display_row_numbers=False, auto_size_columns=False, col_widths=lengths,
                              enable_events=events, bind_return_key=bind, tooltip=tooltip, vertical_scroll_only=False)]

    layout = sg.Frame('', [top_layout, bottom_layout], pad=pad, element_justification='l',
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
    header_col = mod_const.HEADER_COLOR
    input_col = mod_const.FIELD_BG_COLOR
    bg_col = mod_const.DEFAULT_BG_COLOR
    frame_col = mod_const.FRAME_COLOR
    select_col = mod_const.SELECTED_TEXT_COLOR
    text_col = mod_const.DEFAULT_TEXT_COLOR

    pad_el = mod_const.ELEM_PAD
    pad_v = mod_const.VERT_PAD
    pad_h = mod_const.HORZ_PAD
    pad_frame = mod_const.FRAME_PAD

    font_h = mod_const.HEADING_FONT
    font_bold = mod_const.BOLD_FONT
    font_main = mod_const.MAIN_FONT
    font_large = mod_const.BOLD_HEADING_FONT

    # Keyboard shortcuts
    hotkeys = settings.hotkeys
    cancel_shortcut = hotkeys['-HK_ESCAPE-'][2]
    save_shortcut = hotkeys['-HK_ENTER-'][2]
    next_shortcut = hotkeys['-HK_RIGHT-'][2]
    back_shortcut = hotkeys['-HK_LEFT-'][2]

    # Element sizes
    bwidth = 1
    format_param_w = 14
    frame_w = int(width * 0.85)
    frame_pad = pad_frame * 2
    container_w = frame_w - frame_pad
    subset_w = int(container_w * 0.7)

    try:
        record_types = [i.menu_title for i in settings.records.rules if user.check_permission(i.permissions['upload'])]
    except ValueError:
        record_types = []

    file_types = ['xls', 'csv/tsv']
    encodings = ['Default']

    header_req = ['Record Field', 'Data Type', 'Value']
    header_map = ['Record Field', 'Data Type', 'File Column Name']

    cond_operators = ['=', '!=', '>', '<', '>=', '<=']
    math_operators = ['+', '-', '*', '/', '%', '^', '//']
    def_combo_values = ['', '', '', '', '', '']

    # Window Layout

    # Subset layout
    subset_keys = ['-SUBSET_{}-'.format(i) for i in range(10)]
    subset_layout = [[sg.Canvas(size=(container_w, 0), background_color=bg_col)]]
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

        sub_cond_layout = [sg.Col([[sg.Canvas(size=(container_w, 0), background_color=bg_col)],
                                   [sg.Col([[sg.Text('{}.'.format(index + 1), pad=((0, pad_h), 0), font=font_bold,
                                                     background_color=bg_col, auto_size_text=True),
                                             sg.Combo(def_combo_values, key=col_key, pad=((0, pad_h), pad_el),
                                                      size=(int(subset_w * 0.4 / 9), 1), background_color=input_col,
                                                      font=font_main, auto_size_text=False, disabled=True,
                                                      tooltip='Column'),
                                             sg.Combo(cond_operators, key=oper_key, pad=((0, pad_h), pad_el),
                                                      size=(int(subset_w * 0.2 / 9), 1), font=font_bold,
                                                      background_color=input_col, auto_size_text=False, disabled=True,
                                                      tooltip='Operator'),
                                             sg.Input('', key=value_key, pad=((0, pad_el), pad_el),
                                                      size=(int(subset_w * 0.4 / 9), 1), background_color=input_col,
                                                      font=font_main, disabled=True, tooltip='Column value')]],
                                           background_color=bg_col, justification='l', element_justification='l',
                                           expand_x=True),
                                    sg.Col(subset_bttn_layout, pad=(pad_h, 0), justification='r',
                                           element_justification='r', background_color=bg_col)]],
                                  key=subset_key, background_color=bg_col, vertical_alignment='t', justification='l',
                                  element_justification='l', pad=(0, int(pad_el / 2)), visible=visible)
                           ]
        subset_layout.append(sub_cond_layout)

    # Modify layout
    modify_keys = ['-MODIFY_{}-'.format(i) for i in range(10)]
    modify_layout = [[sg.Canvas(size=(container_w, 0), background_color=bg_col)]]
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

        mod_cond_layout = [sg.Col([[sg.Canvas(size=(container_w, 0), background_color=bg_col)],
                                   [sg.Col([[sg.Text('{}.'.format(index + 1), pad=((0, pad_h), 0), font=font_bold,
                                                     background_color=bg_col, auto_size_text=True),
                                             sg.Combo(def_combo_values, key=col_key, pad=((0, pad_h), pad_el),
                                                      size=(int(subset_w * 0.4 / 9), 1), background_color=input_col,
                                                      font=font_main, auto_size_text=False, disabled=True,
                                                      tooltip='Column'),
                                             sg.Combo(math_operators, key=oper_key, pad=((0, pad_h), pad_el),
                                                      size=(int(subset_w * 0.2 / 9), 1), font=font_bold,
                                                      background_color=input_col, auto_size_text=False, disabled=True,
                                                      tooltip='Operator'),
                                             sg.Input('', key=value_key, pad=((0, pad_el), pad_el),
                                                      size=(int(subset_w * 0.4 / 9), 1), background_color=input_col,
                                                      font=font_main, disabled=True, tooltip='Column value')]],
                                           background_color=bg_col, justification='l', element_justification='l',
                                           expand_x=True),
                                    sg.Col(modify_bttn_layout, pad=(pad_h, 0), justification='r',
                                           element_justification='r', background_color=bg_col)]],
                                  key=modify_key, background_color=bg_col, vertical_alignment='t', justification='l',
                                  element_justification='l', pad=(0, int(pad_el / 2)), visible=visible)
                           ]
        modify_layout.append(mod_cond_layout)

    # Panel layout
    p1 = [[sg.Col([[sg.Text('File:', size=(5, 1), pad=((0, pad_el), 0), background_color=bg_col),
                    sg.Input('', key='-FILE-', size=(60, 1), pad=(pad_el, 0), background_color=input_col),
                    sg.FileBrowse('Browse ...', pad=((pad_el, pad_frame), 0))]],
                  pad=(pad_frame, (pad_frame, pad_v)), justification='l', background_color=bg_col)],
          [sg.Frame('File format', [
              [sg.Canvas(size=(frame_w, 0), background_color=bg_col)],
              [sg.Col([[sg.Canvas(size=(int(frame_w * 0.15), 0), background_color=bg_col)]],
                      pad=(0, pad_v), background_color=bg_col, expand_x=True, expand_y=True),
               sg.Col([[sg.Canvas(size=(int(frame_w * 0.15), 0), background_color=bg_col)],
                       [sg.Text('Format:', auto_size_text=True, pad=(pad_el, pad_el), background_color=bg_col),
                        sg.Combo(file_types, key='-FORMAT-', default_value='xls', size=(12, 1),
                                 pad=(pad_el, pad_el), background_color=input_col, tooltip='Format of the input file')],
                       [sg.Text('Encoding:', auto_size_text=True, pad=(pad_el, 0), background_color=bg_col),
                        sg.Combo(encodings, key='-ENCODE-', default_value='Default', size=(12, 1), pad=(pad_el, pad_el),
                                 background_color=input_col)]],
                      pad=((pad_h, 0), pad_v), background_color=bg_col, element_justification='r', expand_x=True),
               sg.Col([[sg.Canvas(size=(int(frame_w * 0.15), 0), background_color=bg_col)]],
                      pad=(0, pad_v), background_color=bg_col, expand_x=True, expand_y=True),
               sg.Col([[sg.Canvas(size=(int(frame_w * 0.15), 0), background_color=bg_col)],
                       [sg.Text('Newline Separator:', auto_size_text=True, pad=(pad_el, pad_el),
                                background_color=bg_col),
                        sg.Input('\\n', key='-NSEP-', size=(8, 1), pad=(pad_el, pad_el), disabled=True,
                                 background_color=input_col,
                                 tooltip='Character used in the CSV file to distinguish between rows')],
                       [sg.Text('Field Separator:', auto_size_text=True, pad=(pad_el, pad_el), background_color=bg_col),
                        sg.Input('\\t', key='-FSEP-', size=(8, 1), pad=(pad_el, pad_el), disabled=True,
                                 background_color=input_col,
                                 tooltip='Character used in the CSV file to distinguish between columns')]],
                      pad=((0, pad_h), pad_v), background_color=bg_col, element_justification='r', expand_x=True),
               sg.Col([[sg.Canvas(size=(int(frame_w * 0.15), 0), background_color=bg_col)]], pad=(0, pad_v),
                      background_color=bg_col, expand_x=True, expand_y=True)]
          ], pad=(pad_frame, pad_v), border_width=bwidth, background_color=bg_col, title_color=select_col,
                    relief='groove')],
          [sg.Frame('Formatting options', [
              [sg.Canvas(size=(frame_w, 0), background_color=bg_col)],
              [sg.Checkbox('Recognize dates', key='-DATES-', pad=(pad_h, (pad_v, pad_el)), default=True, font=font_main,
                           background_color=bg_col,
                           tooltip='Attempt to parse the values of columns containing dates.')],
              [sg.Checkbox('Recognize integers', key='-INTS-', pad=(pad_h, pad_el), default=True, font=font_main,
                           background_color=bg_col,
                           tooltip='Attempt to infer whether data type of a column is an integer or float. '
                                   'Excel files store all numeric values as decimals')],
              [sg.Col([[sg.Canvas(size=(int(frame_w * 0.25), 0), background_color=bg_col)],
                       [sg.Text('Skip n rows at top:', auto_size_text=True, pad=(0, pad_el), font=font_main,
                                background_color=bg_col, tooltip='Do not import the first n rows')],
                       [sg.Text('Skip n rows at bottom:', auto_size_text=True, pad=(0, pad_el), background_color=bg_col,
                                font=font_main, tooltip='Do not import the last n rows')],
                       [sg.Text('Header row (0 indexed):', auto_size_text=True, pad=(0, pad_el),
                                background_color=bg_col, font=font_main,
                                tooltip='Row number, starting at 0, containing the column names (applied '
                                        'after filtering by skipped rows).')],
                       [sg.Text('Thousands separator:', auto_size_text=True, pad=(0, pad_el), background_color=bg_col,
                                font=font_main,
                                tooltip='Thousands character used for parsing string columns into a numeric form')],
                       [sg.Text('Date format:', auto_size_text=True, pad=(0, pad_el), background_color=bg_col,
                                font=font_main, tooltip='Date format used by columns containing date values')],
                       [sg.Text('Date offset:', auto_size_text=True, pad=(0, pad_el), background_color=bg_col,
                                font=font_main, tooltip='Dates are offset by the given number of years')]],
                      pad=((pad_h, 0), (0, pad_v)), background_color=bg_col),
               sg.Col([[sg.Canvas(size=(int(frame_w * 0.5), 0), background_color=bg_col)],
                       [sg.Input('0', key='-TSKIP-', size=(format_param_w, 1), pad=(0, pad_el), font=font_main,
                                 background_color=input_col)],
                       [sg.Input('0', key='-BSKIP-', size=(format_param_w, 1), pad=(0, pad_el), font=font_main,
                                 background_color=input_col)],
                       [sg.Input('0', key='-HROW-', size=(format_param_w, 1), pad=(0, pad_el), font=font_main,
                                 background_color=input_col)],
                       [sg.Input(',', key='-TSEP-', size=(format_param_w, 1), pad=(0, pad_el), font=font_main,
                                 background_color=input_col)],
                       [sg.Input('YYYY-MM-DD', key='-DATE_FORMAT-', size=(format_param_w, 1), pad=(0, pad_el),
                                 font=font_main, background_color=input_col)],
                       [sg.Input('0', key='-DATE_OFFSET-', size=(format_param_w, 1), pad=(0, pad_el), font=font_main,
                                 background_color=input_col)]],
                      pad=((0, pad_h), (0, pad_v)), background_color=bg_col, expand_x=True)]
          ],
                    pad=(pad_frame, (pad_v, pad_frame)), border_width=bwidth, background_color=bg_col,
                    title_color=select_col, relief='groove')]]
    p2 = [[sg.Col([[sg.Text('Record Type:', pad=((0, pad_el), 0), background_color=bg_col),
                    sg.Combo(record_types, key='-RECORDTYPE-', size=(28, 1), pad=(0, 0),
                             enable_events=True, background_color=input_col)]],
                  pad=(pad_frame, (pad_frame, pad_v)), justification='l', background_color=bg_col)],
          [sg.Frame('Required Columns', [
              [sg.Canvas(size=(frame_w, 0), background_color=bg_col)],
              [sg.Col([
                  [sg.Col([[sg.Listbox(values=[], key='-REQLIST-', size=(26, 8), font=font_main, bind_return_key=True,
                                       background_color=bg_col, select_mode='extended',
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
              [sg.Canvas(size=(frame_w, 0), background_color=bg_col)],
              [sg.Col([
                  [sg.Col([[sg.Listbox(values=[], key='-MAPLIST-', size=(26, 8), font=font_main, bind_return_key=True,
                                       background_color=bg_col, select_mode='extended',
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
          [sg.Frame('Subset Rows', [
              [sg.Canvas(size=(frame_w, 0), background_color=bg_col)],
              [sg.Col(subset_layout, pad=(pad_v, pad_v), key='-SUBSET-',
                      background_color=bg_col, expand_x=True, expand_y=True,
                      vertical_alignment='t', scrollable=True, vertical_scroll_only=True, justification='l',
                      element_justification='l')]],
                    pad=(pad_frame, pad_v), background_color=bg_col, border_width=bwidth,
                    title_color=select_col, relief='groove', element_justification='l', vertical_alignment='t',
                    tooltip='Use the subset rules to subset table rows based on the values of the imported columns')],
          [sg.Frame('Transform Values', [
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
        [sg.Canvas(size=(frame_w, 0), background_color=bg_col)],
        [sg.Col([
            [sg.Text('Record type:', size=(28, 1), pad=(0, pad_el), background_color=bg_col,
                     font=font_main),
             sg.Text('0', key='-TABLENAME-', size=(12, 1), pad=(0, pad_el), font=font_main,
                     background_color=bg_col)],
            [sg.Text('Number of data columns:', size=(28, 1), pad=(0, pad_el), background_color=bg_col,
                     font=font_main),
             sg.Text('0', key='-NCOL-', size=(12, 1), pad=(0, pad_el), font=font_main,
                     background_color=bg_col)],
            [sg.Text('Number of import rows:', size=(28, 1), pad=(0, pad_el), background_color=bg_col,
                     font=font_main),
             sg.Text('0', key='-NROW-', size=(12, 1), pad=(0, pad_el), font=font_main, background_color=bg_col)
             ]
        ], pad=(pad_v, pad_v), background_color=bg_col, vertical_alignment='t', expand_x=True, expand_y=True)]],
                    pad=(pad_frame, (pad_frame, pad_v)), border_width=bwidth, background_color=bg_col,
                    title_color=select_col, relief='groove')],
          [sg.Frame('Table Preview', [
              [sg.Canvas(size=(frame_w, 0), background_color=bg_col)],
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

    #bttn_layout = [[sg.Button('', key='-BACK-', image_data=mod_const.LEFT_ICON, image_size=mod_const.BTTN_SIZE,
    #                          pad=(pad_el, 0), disabled=True,
    #                          tooltip='Return to previous panel ({})'.format(back_shortcut)),
    #                sg.Button('', key='-NEXT-', image_data=mod_const.RIGHT_ICON, image_size=mod_const.BTTN_SIZE,
    #                          pad=(pad_el, 0), disabled=False,
    #                          tooltip='Move to next panel ({})'.format(next_shortcut)),
    #                sg.Button('', bind_return_key=True, image_data=mod_const.SAVE_ICON, image_size=mod_const.BTTN_SIZE,
    #                          key='-IMPORT-', pad=(pad_el, 0), disabled=True,
    #                          tooltip='Import file contents to the selected database table ({})'.format(save_shortcut)),
    #                sg.Button('', key='-CANCEL-', image_data=mod_const.CANCEL_ICON, image_size=mod_const.BTTN_SIZE,
    #                          pad=(pad_el, 0), disabled=False,
    #                          tooltip='Cancel importing records to the database ({})'.format(cancel_shortcut))]]

    bttn_layout = [[button_layout('-CANCEL-', icon=mod_const.BTTN_CANCEL_ICON, pad=(pad_el, 0), disabled=False,
                                  tooltip='Cancel importing records to the database ({})'.format(cancel_shortcut)),
                    button_layout('-BACK-', icon=mod_const.BTTN_LEFT_ICON, pad=(pad_el, 0), disabled=True,
                                  tooltip='Return to previous panel ({})'.format(back_shortcut)),
                    button_layout('-NEXT-', icon=mod_const.BTTN_RIGHT_ICON, pad=(pad_el, 0), disabled=False,
                                  tooltip='Move to next panel ({})'.format(next_shortcut)),
                    button_layout('-IMPORT-', icon=mod_const.BTTN_SAVE_ICON, disabled=True,
                                  tooltip='Save records to the selected database table ({})'.format(save_shortcut))]]

    sidebar_layout = [
        [sg.Col([[sg.Canvas(size=(0, height * 0.9), background_color=frame_col)]], background_color=frame_col),
         sg.Col([[sg.Text('• ', pad=((pad_frame, pad_el), (pad_frame, pad_el)), font=font_large,
                          background_color=frame_col),
                  sg.Text('File Options', key='-PN1-', pad=((pad_el, pad_frame), (pad_frame, pad_el)),
                          font=font_main, text_color=select_col, background_color=frame_col)],
                 [sg.Text('• ', pad=((pad_frame, pad_el), pad_el), font=font_large, background_color=frame_col),
                  sg.Text('Import Options', key='-PN2-', pad=((pad_el, pad_frame), pad_el), font=font_main,
                          background_color=frame_col)],
                 [sg.Text('• ', pad=((pad_frame, pad_el), pad_el), font=font_large, background_color=frame_col),
                  sg.Text('Data Preview', key='-PN3-', pad=((pad_el, pad_frame), pad_el), font=font_main,
                          background_color=frame_col)]],
                background_color=frame_col, element_justification='l', vertical_alignment='t', expand_y=True)]]

    layout = [[sg.Col([[sg.Text('Import to Database', pad=(pad_frame, (pad_frame, pad_v)),
                                font=font_h, background_color=header_col)]],
                      pad=(0, 0), justification='l', background_color=header_col, expand_x=True, expand_y=True)],
              [sg.Frame('', sidebar_layout, border_width=bwidth, title_color=text_col, relief='solid',
                        background_color=frame_col),
               sg.Frame('', panel_layout, border_width=bwidth, title_color=text_col, relief='solid',
                        background_color=bg_col)],
              [sg.Col(bttn_layout, justification='r', pad=(pad_frame, (pad_v, pad_frame)))]]

    return layout


# Panel layouts
def home_screen(size):
    """
    Create layout for the home screen.
    """
    bg_col = mod_const.FRAME_COLOR
    width, height = size

    layout = sg.Col([[sg.Canvas(key='-HOME_WIDTH-', size=(width, 0), background_color=bg_col)],
                     [sg.Canvas(key='-HOME_HEIGHT-', size=(0, height), background_color=bg_col),
                      sg.Image(filename=settings.logo, background_color=bg_col, key='-HOME_IMAGE-',
                               size=(width, height))]],
                    key='-HOME-', element_justification='c', vertical_alignment='t', background_color=bg_col,
                    expand_y=True, expand_x=True, visible=False)

    return layout
