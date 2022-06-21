"""
REM secondary window functions, including popups, a window for importing 
missing data, the debugger, and the login window.
"""

import datetime
import gc
import textwrap

import PySimpleGUI as sg
import dateutil
import numpy as np
import pandas as pd

import REM.constants as mod_const
import REM.data_manipulation as mod_dm
import REM.data_collections as mod_col
import REM.layouts as mod_lo
import REM.parameters as mod_param
import REM.records as mod_records
from REM.client import logger, settings, user
from REM.main import __version__


# Popups
def popup_confirm(msg):
    """Display popup asking user if they would like to continue without completing the current action.
    """
    font = mod_const.LARGE_FONT
    return sg.popup_ok_cancel(textwrap.fill(msg, width=40), font=font, title='')


def popup_notice(msg):
    """
    Display popup notifying user that an action is required or couldn't be undertaken.
    """
    font = mod_const.LARGE_FONT
    return sg.popup_ok(textwrap.fill(msg, width=40), font=font, title='')


def popup_error(msg):
    """
    Display popup notifying user that there is a fatal program error.
    """
    font = mod_const.LARGE_FONT
    return sg.popup_error(textwrap.fill(msg, width=40), font=font, title='')


# Windows
def login_window():
    """
    Display the login window.
    """
    # Window and element size parameters
    pad_frame = mod_const.FRAME_PAD
    pad_h = mod_const.HORZ_PAD
    pad_el = mod_const.ELEM_PAD

    bg_col = mod_const.DEFAULT_BG_COLOR
    input_col = mod_const.FIELD_BG_COLOR
    login_col = mod_const.LOGIN_BUTTON_COLOR
    cancel_col = mod_const.CANCEL_BUTTON_COLOR
    def_text_col = mod_const.DEFAULT_TEXT_COLOR
    disabled_text_col = mod_const.DISABLED_TEXT_COLOR
    text_col = mod_const.WHITE_TEXT_COLOR
    bold_text = mod_const.BOLD_FONT

    lock_icon = mod_const.LOCK_ICON
    username_icon = mod_const.USERNAME_ICON

    isize = mod_const.IN1_WIDTH
    bsize = mod_const.B1_WIDTH

    main_font = mod_const.MAIN_FONT
    small_font = mod_const.SMALL_FONT

    username = settings.username
    default_user_text = '<user name>'
    default_pass_text = '<password>'

    if username:
        user_text_color = def_text_col
        user_text = username
    else:
        user_text_color = disabled_text_col
        user_text = default_user_text

    password = ''

    # GUI layout
    logo = settings.logo_icon
    if logo:
        img_layout = [sg.Image(filename=logo, background_color=bg_col, pad=(pad_frame, (pad_frame, pad_el)))]
    else:
        img_layout = [sg.Text('', background_color=bg_col, pad=(pad_frame, (pad_frame, pad_el)))]

    user_key = '-USER-'
    pass_key = '-PASSWORD-'
    column_layout = [img_layout,
                     [sg.Text('', pad=(pad_frame, pad_el), background_color=bg_col)],
                     [sg.Frame('', [[sg.Image(data=username_icon, background_color=input_col, pad=((pad_el, pad_h), 0)),
                                     sg.Input(default_text=user_text, key=user_key, size=(isize - 2, 1),
                                              pad=((0, 2), 0), text_color=user_text_color, border_width=0,
                                              do_not_clear=True, background_color=input_col, enable_events=True,
                                              tooltip='Input account username')]],
                               background_color=input_col, pad=(pad_frame, pad_el), relief='sunken')],
                     [sg.Frame('', [[sg.Image(data=lock_icon, pad=((pad_el, pad_h), 0), background_color=input_col),
                                     sg.Input(default_text=default_pass_text, key=pass_key, size=(isize - 2, 1),
                                              pad=((0, 2), 0), password_char=None, text_color=disabled_text_col,
                                              background_color=input_col, border_width=0, do_not_clear=True,
                                              enable_events=True, tooltip='Input account password')]],
                               background_color=input_col, pad=(pad_frame, pad_el), relief='sunken')],
                     [sg.Text('', key='-HELP-', size=(20, 6), pad=(pad_frame, pad_frame), font=small_font,
                              justification='center', text_color='Red', background_color=bg_col)],
                     [sg.Button('Sign In', key='-LOGIN-', size=(bsize, 1), pad=(pad_frame, pad_el), font=bold_text,
                                button_color=(text_col, login_col))],
                     [sg.Button('Cancel', key='-CANCEL-', size=(bsize, 1), pad=(pad_frame, (pad_el, pad_frame)),
                                font=bold_text, button_color=(text_col, cancel_col))]]

    layout = [[sg.Frame('', column_layout, element_justification='center', background_color=bg_col, border_width=2,
                        relief='raised')]]

    window = sg.Window('', layout, font=main_font, modal=True, keep_on_top=True, no_titlebar=True,
                       return_keyboard_events=True)
    window.finalize()
    window['-USER-'].update(select=True)
    window.refresh()

    # Bind events to keys
    return_keys = ('Return:36', '\r')

    user_in_key = '-USER-+IN+'
    user_out_key = '-USER-+OUT+'
    window[user_key].bind('<FocusIn>', '+IN+')
    window[user_key].bind('<FocusOut>', '+OUT+')

    pass_in_key = '-PASSWORD-+IN+'
    pass_out_key = '-PASSWORD-+OUT+'
    window[pass_key].bind('<FocusIn>', '+IN+')
    window[pass_key].bind('<FocusOut>', '+OUT+')

    # Event window
    while True:
        event, values = window.read()

        if event in (sg.WIN_CLOSED, '-CANCEL-'):  # selected close-window
            break

        # Focus moved to password or username field
        if event == user_in_key:
            if not username:  # highlight all text
                #window[user_key].update(select=True)
                window[user_key].update(value='')

        if event == pass_in_key:
            if not password:  # highlight all text
                #window[pass_key].update(select=True)
                window[pass_key].update(value='')

        # Focus moved from password or username field
        if event == user_out_key:
            if not username:  # Set default text and color
                window[user_key].update(text_color=disabled_text_col, value=default_user_text)
            else:
                window[user_key].update(text_color=def_text_col)

        if event == pass_out_key:
            if not password:  # Set default text and color
                window[pass_key].update(text_color=disabled_text_col, value=default_pass_text, password_char='')
            else:
                window[pass_key].update(text_color=def_text_col, password_char='*')

        # Input field event
        if event == user_key:
            new_value = values[user_key]
            if new_value != default_user_text:
                username = new_value
                window[user_key].update(text_color=def_text_col)

                window['-HELP-'].update(value='')

        if event == pass_key:
            new_value = values[pass_key]
            if new_value != default_pass_text:
                password = new_value
                window[pass_key].update(text_color=def_text_col, password_char='*')

                window['-HELP-'].update(value='')

        if event in return_keys:
            window['-LOGIN-'].Click()

        if event == '-LOGIN-':
            # Verify values for username and password fields
            if not username:
                msg = 'username is required'
                window['-HELP-'].update(value=msg)
            elif not password:
                msg = 'password is required'
                window['-HELP-'].update(value=msg)
            else:
                try:
                    login_success = user.login(username, password)
                except Exception as e:
                    window['-HELP-'].update(value=e)
                    logger.error('login failed - {}'.format(e))
                else:
                    if login_success:
                        break

    window.close()
    layout = None
    window = None
    gc.collect()


def debug_window():
    """
    Display the debug window.
    """
    # Layout options
    pad_el = mod_const.ELEM_PAD
    pad_frame = mod_const.FRAME_PAD
    pad_v = mod_const.VERT_PAD
    font = mod_const.LARGE_FONT
    bold_font = mod_const.BOLD_FONT
    bg_col = mod_const.DEFAULT_BG_COLOR
    frame_col = mod_const.FRAME_COLOR

    # Layout
    log_levels = ['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG']

    bttn_layout = [[sg.Button('', key='-CANCEL-', image_data=mod_const.CANCEL_ICON, image_size=mod_const.BTTN_SIZE,
                              pad=(pad_el, 0), tooltip='Stop debugging'),
                    sg.Button('', key='-CLEAR-', image_data=mod_const.DELETE_ICON, image_size=mod_const.BTTN_SIZE,
                              bind_return_key=True, pad=(pad_el, 0), tooltip='Clear debug output')]]

    debug_layout = [[sg.Text('Log level:', pad=((pad_frame, pad_el), (pad_frame, pad_v)), font=bold_font,
                             background_color=bg_col),
                     sg.Combo(log_levels, key='-LEVEL-', default_value=settings.log_level, enable_events=True,
                              background_color=bg_col, pad=((0, pad_frame), (pad_frame, pad_v)), font=font)],
                    [sg.Output(size=(40, 10), key='-OUTPUT-', pad=(pad_frame, 0), background_color=bg_col,
                               echo_stdout_stderr=True)]]

    layout = [[sg.Col(debug_layout, pad=(0, 0), background_color=bg_col, expand_y=True, expand_x=True)],
              [sg.Col(bttn_layout, justification='c', element_justification='c',
                      pad=(0, (pad_v, pad_frame)), background_color=frame_col, expand_x=True)]]

    window = sg.Window('Debug Program', layout, modal=False, keep_on_top=False, resizable=True)

    return window


def record_window(record, view_only: bool = False, modify_database: bool = True):
    """
    Display the record window.
    """
    # Initial window size
    min_w, min_h = (int(mod_const.WIN_WIDTH * 0.5), int(mod_const.WIN_HEIGHT * 0.5))

    record_id = record.record_id()
    record_level = record.level

    # GUI layout

    # Element parameters
    pad_el = mod_const.ELEM_PAD
    pad_frame = mod_const.FRAME_PAD

    bg_col = mod_const.DEFAULT_BG_COLOR
    text_col = mod_const.DEFAULT_TEXT_COLOR
    header_col = mod_const.HEADER_COLOR

    font_h = mod_const.HEADING_FONT

    # User permissions
    record_entry = settings.records.fetch_rule(record.name)

    mod_perm = True if ((user.check_permission(record_entry.permissions['edit']) and record.new is False) or
                        (user.check_permission(record_entry.permissions['create']) and record.new is True)) else False
    del_perm = True if user.check_permission(record_entry.permissions['delete']) and record.new is False else False

    can_save = True if mod_perm and record_level < 1 and view_only is False and modify_database is True else False
    can_accept = True if mod_perm and record_level < 2 and view_only is False and modify_database is False else False
    can_delete = True if del_perm and record_level < 1 and view_only is False and modify_database is True else False

    gen_report = True if record.report is not None and (mod_perm or del_perm) else False

    # Window Title
    bffr_h = 2 + pad_el * 2

    title = record.title
    title_w, title_h = (mod_const.TITLE_WIDTH, mod_const.TITLE_HEIGHT)
    title_layout = [[sg.Canvas(size=(0, title_h), background_color=bg_col),
                     sg.Col([[sg.Text(title, pad=(pad_frame, 0), font=font_h, background_color=header_col)]],
                            expand_x=True, justification='l', vertical_alignment='c', background_color=header_col),
                     sg.Col([[sg.Button('', key='-REPORT-', image_data=mod_const.REPORT_ICON, border_width=0,
                                        pad=(pad_frame, 0), button_color=(text_col, header_col),
                                        visible=gen_report, tooltip='Generate record report')]],
                            justification='r', element_justification='r', vertical_alignment='c',
                            background_color=header_col)]]
    bffr_h += title_h

    # Button layout
    bttn_h = mod_const.BTTN_HEIGHT
    bttn_layout = [[sg.Canvas(size=(0, bttn_h)),
                    sg.Button('', key='-DELETE-', image_data=mod_const.DELETE_ICON, image_size=mod_const.BTTN_SIZE,
                              pad=(pad_el, 0), visible=can_delete,
                              tooltip='Delete the record from the database'),
                    sg.Button('', key='-OK-', image_data=mod_const.CONFIRM_ICON, image_size=mod_const.BTTN_SIZE,
                              pad=(pad_el, 0), visible=can_accept,
                              tooltip='Accept changes to the record'),
                    sg.Button('', key='-SAVE-', image_data=mod_const.SAVE_ICON, image_size=mod_const.BTTN_SIZE,
                              pad=(pad_el, 0), visible=can_save,
                              tooltip='Save record changes to the database')]]

    bffr_h += bttn_h

    # Record layout
    record_w = min_w
    record_h = min_h - bffr_h
    record_layout = record.layout((record_w, record_h), padding=(pad_frame, pad_el))

    # Window layout
    layout = [[sg.Col(title_layout, key='-TITLE-', background_color=header_col, vertical_alignment='c', expand_x=True)],
              [sg.HorizontalSeparator(color=mod_const.DISABLED_BG_COLOR)],
              [sg.Col(record_layout, key='-RECORDS-', background_color=bg_col, expand_x=True, expand_y=True)],
              [sg.HorizontalSeparator(color=mod_const.DISABLED_BG_COLOR)],
              [sg.Col(bttn_layout, key='-BUTTONS-', justification='l', element_justification='c',
                      vertical_alignment='c', expand_x=True)]]

    window_title = '{TITLE} ({LEVEL})'.format(TITLE=title, LEVEL=record_level)
    window = sg.Window(window_title, layout, modal=True, keep_on_top=False, return_keyboard_events=True, resizable=True)
    window.finalize()
    window.hide()

    window.set_min_size((min_w, min_h))

    # Bind keys to events
    window = settings.set_shortcuts(window, hk_groups=['Record', 'Navigation'])

    logger.debug('binding record element hotkeys')
    for element in record.record_elements():
        element.bind_keys(window)

    # Resize window and update the record display
    screen_w, screen_h = window.get_screen_dimensions()
    wh_ratio = 0.95  # window width to height ratio
    win_h = int(screen_h * 0.8)  # open at 80% of the height of the screen
    win_w = int(win_h * wh_ratio) if (win_h * wh_ratio) <= screen_w else screen_w

    record_w = win_w if win_w >= min_w else min_w
    record_h = win_h - bffr_h if win_h >= min_h else min_h
    # record.resize(window, size=(record_w, record_h))

    record.update_display(window, size=(record_w, record_h))

    # Center the record window
    window.un_hide()
    window = align_window(window)
    current_w, current_h = [int(i) for i in window.size]

    # Event window
    while True:
        event, values = window.read(timeout=100)

        if event == sg.WIN_CLOSED:  # selected to close window without accepting changes
            # Remove unsaved IDs associated with the record
            record.remove_unsaved_ids()
            record = None

            break

        win_w, win_h = [int(i) for i in window.size]
        if win_w != current_w or win_h != current_h:
            logger.debug('current window size is {W} x {H}'.format(W=current_w, H=current_h))
            logger.debug('new window size is {W} x {H}'.format(W=win_w, H=win_h))

            # Update sizable elements
            record_w = win_w if win_w >= min_w else min_w
            record_h = win_h - bffr_h if win_h >= min_h else min_h
            record.resize(window, size=(record_w, record_h))

            current_w, current_h = (win_w, win_h)

        if event == '-HK_RECORD_SAVE-':
            if not can_save:
                window['-OK-'].click()
            else:
                window['-SAVE-'].click()

        if event == '-HK_RECORD_DEL-':
            if can_delete:
                window['-DELETE-'].click()

        if event == '-OK-':  # selected to accept record changes
            # Check if any data elements are in edit mode before saving. Attempt to save if so.
            elements_updated = True
            for record_element in record.components:
                try:
                    edit_mode = record_element.edit_mode
                except AttributeError:
                    continue
                else:
                    if edit_mode:  # element is being edited
                        # Attempt to save the data element value
                        success = record_element.run_event(window, record_element.key_lookup('Save'), values)
                        if not success:
                            elements_updated = False

                            break

            if not elements_updated:
                continue

            # Verify that required parameters have values
            can_continue = record.check_required_parameters()

            if can_continue is True:
                break
            else:
                continue

        if event == '-SAVE-':  # selected to save the record (changes) to the database
            # Check if any data elements are in edit mode before saving. Attempt to save if so.
            elements_updated = True
            for record_element in record.components:
                try:
                    edit_mode = record_element.edit_mode
                except AttributeError:
                    pass
                else:
                    if edit_mode:  # element is being edited
                        # Attempt to save the data element value
                        success = record_element.run_event(window, record_element.key_lookup('Save'), values)
                        if not success:
                            elements_updated = False

                            break

            if not elements_updated:
                continue

            # Save the record to the database table
            saved = record.save()
            if saved is False:
                popup_error('failed to save record {ID} - see log for details'.format(ID=record_id))
                continue
            else:
                # Remove unsaved IDs associated with the record
                record.remove_unsaved_ids()

                break

        if event == '-DELETE-':
            deleted = record.delete()
            if deleted is False:
                popup_error('failed to delete record {ID} - see log for details'.format(ID=record_id))
                continue
            else:
                # Remove unsaved IDs associated with the record
                record.remove_unsaved_ids()

                break

        # Generate a record report
        if event == '-REPORT-':
            default_filename = '{}_{}'.format(record.record_id(display=True), record.record_date(display=True))
            outfile = sg.popup_get_file('', title='Save Report As', save_as=True, default_extension='pdf',
                                        default_path=default_filename, no_window=True,
                                        file_types=(('PDF - Portable Document Format', '*.pdf'),))

            if not outfile:
                continue

            try:
                save_report = record.save_report(outfile)
            except Exception as e:
                msg = 'failed to generate the record report'
                logger.exception('Record {ID}: {MSG} - {ERR}'.format(ID=record_id, MSG=msg, ERR=e))
                popup_error('{MSG} - see log for details'.format(MSG=msg))
            else:
                if not save_report:
                    msg = 'failed to generate the record report'
                    popup_error('{MSG} - see log for details'.format(MSG=msg))

            continue

        # Update the record parameters with user-input
        if event in record.record_events():  # selected a record event element
            try:
                record.run_event(window, event, values)
            except Exception as e:
                msg = 'Record {ID}: failed to run record event {EVENT} - {ERR}' \
                    .format(ID=record_id, EVENT=event, ERR=e)
                logger.exception(msg)
                popup_notice('failed to run event for record {}'.format(record_id))

                continue

    window.close()
    layout = None
    window = None
    gc.collect()

    return record


def parameter_window(definitions, title: str = None, win_size: tuple = None):
    """
    Display the parameter selection window for a bank reconciliation rule.

    Arguments:
        definitions (dict): dictionary of parameter definitions grouped by section.

        title (str): title of the parameter window.

        win_size (tuple): optional window size parameters (width, height).
    """
    # Initial window size
    if win_size:
        width, height = win_size
    else:
        width, height = mod_const.PARAM_WIN_SIZE

    param_values = {}

    # Element settings
    pad_el = mod_const.ELEM_PAD
    pad_v = mod_const.VERT_PAD
    pad_h = mod_const.HORZ_PAD
    pad_frame = mod_const.FRAME_PAD

    font_h = mod_const.HEADING_FONT
    bold_font = mod_const.BOLD_FONT

    bg_col = mod_const.DEFAULT_BG_COLOR
    header_col = mod_const.HEADER_COLOR
    frame_col = mod_const.FRAME_COLOR
    text_col = mod_const.DEFAULT_TEXT_COLOR

    # Keyboard shortcuts
    hotkeys = settings.hotkeys
    load_shortcut = hotkeys['-HK_ENTER-'][2]

    # Layout elements

    # Window Title
    win_title = 'Parameter Selection' if title is None else title
    title_layout = [[sg.Text(win_title, pad=(pad_frame, pad_frame), font=font_h, background_color=header_col)]]

    # Parameters layout
    params_layout = []
    params = {}
    bindings = {}

    # Associated account parameters
    for section_title in definitions:  # iterate over parameter groups
        section_params = definitions[section_title]

        pgroup_layout = [[sg.Col([[sg.Text(section_title, pad=(0, 0), font=bold_font, text_color=text_col,
                                           background_color=frame_col)]],
                                 expand_x=True, background_color=frame_col, justification='l')],
                         [sg.HorizontalSeparator(color=mod_const.FRAME_COLOR, pad=(0, 0))]]

        # Create the import parameter objects and layouts for the associated account
        for param_name in section_params:
            param_entry = section_params[param_name]
            try:
                param = mod_param.initialize_parameter(param_name, param_entry)
            except Exception as e:
                logger.error(e)

                continue

            pgroup_layout.append(param.layout(padding=(0, pad_el), bg_color=bg_col, justification='left'))
            try:
                params[section_title].append(param)
            except KeyError:
                params[section_title] = [param]

            for element in param.bindings:
                bindings[element] = section_title

        params_layout.append([sg.Col(pgroup_layout, key='-{}-'.format(section_title), pad=(pad_h, pad_v),
                                     background_color=bg_col, visible=True, expand_x=True, metadata={'visible': True})])

    # Control elements
    load_key = '-LOAD-'
    bttn_layout = [[sg.Button('', key=load_key, image_data=mod_const.CONFIRM_ICON, image_size=mod_const.BTTN_SIZE,
                              disabled=False, tooltip='Confirm settings ({})'.format(load_shortcut))]]

    # Window layout
    height_key = '-HEIGHT-'
    width_key = '-WIDTH-'
    layout = [[sg.Canvas(key=width_key, size=(width, 0))],
              [sg.Col([[sg.Canvas(key=height_key, size=(0, height))]]),
               sg.Col([
                   [sg.Col(title_layout, background_color=header_col, expand_x=True)],
                   [sg.HorizontalSeparator(pad=(0, 0), color=mod_const.DISABLED_BG_COLOR)],
                   [sg.Col(params_layout, key='-PARAMS-', pad=(0, 0), background_color=bg_col, scrollable=True,
                           vertical_scroll_only=True, expand_x=True, expand_y=True, vertical_alignment='t')],
                   [sg.HorizontalSeparator(pad=(0, 0), color=mod_const.DISABLED_BG_COLOR)],
                   [sg.Col(bttn_layout, pad=(0, pad_v), element_justification='c', vertical_alignment='c',
                           expand_x=True)]
               ], key='-FRAME-', expand_y=True, expand_x=True)]]

    window = sg.Window(title, layout, modal=True, keep_on_top=False, return_keyboard_events=True, resizable=True)
    window.finalize()

    # Bind keys to events
    window = settings.set_shortcuts(window)

    for pgroup in params:
        for parameter in params[pgroup]:
            parameter.bind_keys(window)

    # Resize window
    #screen_w, screen_h = window.get_screen_dimensions()
    #wh_ratio = 0.75  # window width to height ratio
    #win_h = int(screen_h * 0.8)  # open at 80% of the height of the screen
    #win_w = int(win_h * wh_ratio) if (win_h * wh_ratio) <= screen_w else screen_w

    #window[height_key].set_size(size=(None, int(win_h)))
    #window[width_key].set_size(size=(int(win_w), None))
    w_offset = mod_const.SCROLL_WIDTH + pad_v * 2
    for pgroup in params:
        for param in params[pgroup]:
            #param.resize(window, size=(int(win_w - 40), None))
            param.resize(window, size=(int(width - w_offset), None))

    window = align_window(window)
    current_w, current_h = [int(i) for i in window.size]

    # Event window
    while True:
        event, values = window.read(timeout=100)

        # Cancel parameter selection
        if event in (sg.WIN_CLOSED, '-HK_ESCAPE-'):  # selected to close window without setting param values
            param_values = None

            break

        # Window resized
        win_w, win_h = [int(i) for i in window.size]
        if win_w != current_w or win_h != current_h:
            logger.debug('current window size is {W} x {H}'.format(W=current_w, H=current_h))
            logger.debug('new window size is {W} x {H}'.format(W=win_w, H=win_h))

            # Update sizable elements
            window[height_key].set_size(size=(None, int(win_h)))
            window[width_key].set_size(size=(int(win_w), None))

            for pgroup in params:
                for param in params[pgroup]:
                    param.resize(window, size=(int(win_w - w_offset), None))

            current_w, current_h = (win_w, win_h)

            continue

        # Save parameter settings
        if event == '-HK_ENTER-':
            window['-LOAD-'].click()

        if event == '-LOAD-':
            ready_to_save = True
            for pgroup in params:
                # Ignore parameters from hidden accounts
                if not window['-{}-'.format(pgroup)].metadata['visible']:
                    param_values[pgroup] = None

                    continue

                # Verify that required parameters have values
                acct_params = params[pgroup]
                has_values = []
                for acct_param in acct_params:
                    acct_param.value = acct_param.format_value(values)

                    if not acct_param.has_value():  # no value set for parameter
                        if acct_param.required:  # parameter is required, so notify user that value must be provided
                            msg = 'missing value from required account {ACCT} parameter {PARAM}' \
                                .format(ACCT=pgroup, PARAM=acct_param.name)
                            logger.warning(msg)
                            popup_error(msg)
                            has_values.append(False)

                            break
                        else:  # parameter is not required, so can safely ignore
                            continue

                    try:
                        param_values[pgroup].append(acct_param)
                    except KeyError:
                        param_values[pgroup] = [acct_param]

                if not all(has_values):
                    ready_to_save = False
                    break

            if ready_to_save:
                break
            else:
                continue

        # Associated account parameter events
        if event in bindings:
            # Fetch the parameter corresponding to the window event element
            event_pgroup = bindings[event]
            pgroup_params = params[event_pgroup]
            event_param = mod_param.fetch_parameter(pgroup_params, event, by_key=True)

            # Run the parameter event associated with the window element key
            event_param.run_event(window, event, values)

            # Propagate parameter value to other pgroup parameters that are related by name and element type and that do
            # not currently have values
            if event_param.has_value():
                for pgroup in params:
                    if pgroup == event_pgroup:
                        continue

                    related_params = mod_param.fetch_parameter(params[pgroup], event_param.name)
                    if related_params:
                        if not isinstance(related_params, list):
                            related_params = [related_params]
                        for related_param in related_params:
                            if not related_param.has_value() and related_param.etype == event_param.etype and \
                                    related_param.required:
                                related_param.format_value(event_param.value)
                                related_param.update_display(window)

            continue

    window.close()
    layout = None
    window = None
    gc.collect()

    return param_values


def add_note_window(note: str = None):
    """
    Display a window with a multiline window for capturing a custom note.
    """
    note_text = '' if not note else note

    # Layout options
    pad_frame = mod_const.FRAME_PAD
    font = mod_const.LARGE_FONT

    text_col = mod_const.DEFAULT_TEXT_COLOR
    bttn_text_col = mod_const.BUTTON_TEXT_COLOR
    bg_col = mod_const.DEFAULT_BG_COLOR
    frame_col = mod_const.DISABLED_BG_COLOR
    bttn_col = (mod_const.WHITE_TEXT_COLOR, mod_const.BUTTON_BG_COLOR)
    highlight_cols = (mod_const.DISABLED_TEXT_COLOR, mod_const.DISABLED_BUTTON_COLOR)

    # Window layout
    nrow = 4
    width = 80

    save_key = '-SAVE-'
    cancel_key = '-CANCEL-'
    bttn_layout = [[sg.Button('Save', key=save_key, image_size=mod_const.BTTN_SIZE, button_color=bttn_col,
                              mouseover_colors=highlight_cols, use_ttk_buttons=True),
                    sg.Button('Cancel', key=cancel_key, image_size=mod_const.BTTN_SIZE, border_width=0,
                              button_color=(bttn_text_col, bg_col))]]

    elem_key = '-NOTE-'
    elem_layout = [[sg.Multiline(note_text, key=elem_key, size=(width, nrow), font=font, background_color=bg_col,
                                 text_color=text_col, border_width=1)]]

    layout = [[sg.Col(elem_layout, pad=(pad_frame, pad_frame), expand_x=True, element_justification='l',
                      background_color=bg_col)],
              [sg.HorizontalSeparator(color=frame_col)],
              [sg.Col(bttn_layout, pad=(pad_frame, pad_frame), expand_x=True, element_justification='l',
                      background_color=bg_col)]]

    window = sg.Window('Add note', layout, background_color=bg_col, modal=True, keep_on_top=True,
                       return_keyboard_events=True, resizable=True)
    window.finalize()

    # Resize window to initial size
    screen_w, screen_h = window.get_screen_dimensions()
    window[elem_key].expand(expand_x=True, expand_y=True)

    window = align_window(window)
    current_w, current_h = [int(i) for i in window.size]

    # Event window
    while True:
        event, values = window.read(timeout=100)

        # Cancel parameter selection
        if event in (sg.WIN_CLOSED, cancel_key, '-HK_ESCAPE-'):  # selected to close window without setting param values
            note = None
            break

        # Window resized
        win_w, win_h = [int(i) for i in window.size]
        if win_w != current_w or win_h != current_h:
            logger.debug('current window size is {W} x {H}'.format(W=current_w, H=current_h))
            logger.debug('new window size is {W} x {H}'.format(W=win_w, H=win_h))

            # Update sizable elements
            window[elem_key].expand(expand_x=True, expand_y=True)

            current_w, current_h = (win_w, win_h)

            continue

        # Save parameter settings
        if event in (save_key, '-HK_ENTER-'):
            note = values[elem_key].strip()

            break

    window.close()
    layout = None
    window = None
    gc.collect()

    return note


def database_importer_window(win_size: tuple = None):
    """
    Display the database importer window.
    """
    pd.set_option('display.max_columns', None)

    relativedelta = dateutil.relativedelta.relativedelta
    strptime = datetime.datetime.strptime

    date_types = settings.supported_date_dtypes
    int_types = settings.supported_int_dtypes
    float_types = settings.supported_float_dtypes
    bool_types = settings.supported_bool_dtypes
    str_types = settings.supported_str_dtypes
    cat_dtypes = settings.supported_cat_dtypes

    dtype_map = {}
    for i in int_types:
        dtype_map[i] = np.int64

    for i in float_types:
        dtype_map[i] = np.float64

    for i in bool_types:
        dtype_map[i] = np.bool_

    for i in date_types + str_types + cat_dtypes:
        dtype_map[i] = np.object_

    field_col = 'Record Field'
    def_value_col = 'Value'
    dtype_col = 'Data Type'
    file_col = 'File Column Name'

    # Layout settings
    main_font = mod_const.MAIN_FONT

    text_color = mod_const.DEFAULT_TEXT_COLOR
    select_color = mod_const.SELECTED_TEXT_COLOR

    # Window and element size parameters
    if win_size is not None:
        width = win_size[0] * 0.7
        height = win_size[1] * 0.8
    else:
        width, height = (int(mod_const.WIN_WIDTH * 0.7), int(mod_const.WIN_HEIGHT * 0.8))

    # Window layout
    layout = mod_lo.importer_layout(win_size=(width, height))

    window = sg.Window('Import records to Database', layout, font=main_font, modal=True, return_keyboard_events=True)
    window.finalize()

    # Bind keyboard events
    window = settings.set_shortcuts(window, hk_groups='Navigation')

    deletion_keys = ['<Control-d>', '<Key-Delete>', '<Key-BackSpace>']
    for del_key in deletion_keys:
        window['-MAPCOL-'].bind(del_key, '+DELETE+')
        window['-REQCOL-'].bind(del_key, '+DELETE+')

    nav_keys = ['Up', 'Down']
    for nav_key in nav_keys:
        window['-MAPLIST-'].bind('<Key-{}>'.format(nav_key), '+{}+'.format(nav_key.upper()))
        window['-REQLIST-'].bind('<Key-{}>'.format(nav_key), '+{}+'.format(nav_key.upper()))

    for opt_key in ('-MAPLIST-', '-REQLIST-', '-MAPCOL-', '-REQCOL-', '-IMPORT-'):
        window[opt_key].bind('<Return>', '+RETURN+')

    # Element values
    panel_keys = {0: '-P1-', 1: '-P2-', 2: '-P3-'}
    panel_names = {0: '-PN1-', 1: '-PN2-', 2: '-PN3-'}
    current_panel = 0
    first_panel = 0
    last_panel = 2

    req_df = pd.DataFrame(columns=[field_col, dtype_col, def_value_col])
    map_df = pd.DataFrame(columns=[field_col, dtype_col, file_col])

    record_ids = []
    record_entry = None
    collection = None
    reserved_values = [settings.edit_date, settings.editor_code, settings.creation_date, settings.creator_code]
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
                logger.info('removing unsaved record IDs')
                record_entry.remove_unsaved_ids(record_ids)
                record_ids = []

            break

        if event in ('-IMPORT-', '-IMPORT-+RETURN+'):
            try:
                export_df = collection.data(fields=selected_columns, drop_na=True)
            except AttributeError:
                continue

            try:
                statements = record_entry.save_database_records(export_df)
            except Exception as e:
                msg = 'failed to upload {TYPE} record entries to the database - {ERR}' \
                    .format(TYPE=record_entry.name, ERR=e)
                logger.exception(msg)
                popup_error(msg)

                return False

            sstrings = []
            psets = []
            for i, j in statements.items():
                sstrings.append(i)
                psets.append(j)

            success = user.write_db(sstrings, psets)

            nrecord = export_df.shape[0]
            if success:
                msg = 'successfully saved {NROW} rows to the database'.format(NROW=nrecord)
            else:
                msg = 'failed to save {NROW} rows to the database'.format(NROW=nrecord)

            popup_notice(msg)
            logger.info(msg)

            # Delete saved record IDs from list of unsaved IDs
            logger.info('removing newly saved records from the list of unsaved IDs')
            record_entry.remove_unsaved_ids(record_ids)

            # Export report describing success of import by row
            success_col = 'Successfully saved'
            export_df.loc[:, success_col] = success
            outfile = sg.popup_get_file('', title='Save Database import report', save_as=True,
                                        default_extension='xlsx', no_window=True,
                                        file_types=(('XLS - Microsoft Excel', '*.xlsx'),
                                                    ('Comma-Separated Values', '*.csv')))

            try:
                out_fmt = outfile.split('.')[-1]
            except AttributeError:
                break

            if out_fmt == 'csv':
                export_df.to_csv(outfile, sep=',', header=True, index=False)
            else:
                export_df.style.apply(highlight_bool, column=success_col, axis=1).to_excel(outfile, engine='openpyxl',
                                                                                           header=True, index=False)

            break

        # Enable next button when a file is selected
        infile = values['-FILE-']

        # Make sure the flow control buttons enabled
        if current_panel != last_panel:
            window['-NEXT-'].update(disabled=False)

        # Move to next panel
        if event in ('-NEXT-', '-HK_RIGHT-'):
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
                    msg = 'only integer values allowed when indicating number of rows to skip'
                    popup_notice(msg)
                    logger.warning(msg)

                    continue

                header_row = values['-HROW-']
                try:
                    header_row = int(header_row)
                except ValueError:
                    msg = 'header row must be an integer value'
                    popup_notice(msg)
                    logger.warning(msg)

                    continue

                thousands_sep = values['-TSEP-']
                if len(thousands_sep) > 1:
                    msg = 'unsupported character "{SEP}" provided as the thousands separator' \
                        .format(SEP=values['-TSEP-'])
                    popup_notice(msg)
                    logger.warning(msg)

                    continue

                date_offset = values['-DATE_OFFSET-']
                offset_oper = date_offset[0]
                if offset_oper in ('+', '-'):
                    date_offset = date_offset[1:]
                else:
                    offset_oper = '+'

                try:
                    date_offset = abs(int(date_offset))
                except ValueError:
                    msg = 'unsupported character "{OFFSET}" provided as the date offset - date offset requires an ' \
                          'integer value'.format(OFFSET=date_offset)
                    popup_notice(msg)
                    logger.warning(msg)

                    continue

                try:
                    date_format = settings.format_date_str(values['-DATE_FORMAT-'])
                except TypeError as e:
                    msg = 'unaccepted format "{FMT}" provided to the date format parameter' \
                        .format(FMT=values['-DATE_FORMAT-'])
                    popup_notice(msg)
                    logger.warning('{MSG} - {ERR}'.format(MSG=msg, ERR=e))

                    continue

            # Populate Preview table with top 10 and bottom 10 values from spreadsheet
            if next_panel == last_panel:
                if not record_entry:
                    popup_notice('Please select a valid record type from the "Record Type" dropdown')
                    logger.warning('no record type selected in the "Record Type" dropdown')

                    continue
                else:
                    converters = {row[file_col]: dtype_map.get(row[dtype_col], np.object_) for i, row in map_df.iterrows()}

                    # Import spreadsheet into dataframe
                    file_format = values['-FORMAT-']
                    if file_format == 'xls':
                        formatting_options = {'convert_float': values['-INTS-'], 'parse_dates': False,
                                              'skiprows': skiptop, 'skipfooter': skipbottom, 'header': header_row,
                                              'thousands': thousands_sep, 'dtype': converters}
                        reader = pd.read_excel
                    else:
                        formatting_options = {'sep': values['-FSEP-'], 'skiprows': skiptop,
                                              'skipfooter': skipbottom, 'header': header_row,
                                              'thousands': thousands_sep, 'encoding': 'utf-8',
                                              'error_bad_lines': False, 'parse_dates': False,
                                              'skip_blank_lines': True, 'dtype': converters}
                        reader = pd.read_csv

                    logger.debug('formatting import file options: {}'.format(formatting_options))

                    # Import data from the file into a pandas dataframe
                    try:
                        import_df = reader(infile, **formatting_options)
                    except Exception as e:
                        msg = 'unable to parse the format of the input file {IN}'.format(IN=infile)
                        logger.error('{MSG} - {ERR}'.format(MSG=msg, ERR=e))
                        popup_notice(msg)

                        continue

                    # Rename columns based on mapping information
                    col_mapper = pd.Series(map_df[field_col].values, index=map_df[file_col]).to_dict()
                    try:
                        import_df.rename(col_mapper, axis=1, inplace=True, errors='raise')
                    except KeyError as e:
                        msg = 'failed to map file column names to database table column names'
                        logger.error('{MSG} - {ERR}'.format(MSG=msg, ERR=e))
                        logger.debug('column mapping is: {}'.format(col_mapper))
                        popup_error('{MSG} - please verify that the file column names were accurately recorded'
                                    .format(MSG=msg))

                        continue

                    # Set values for the required / static columns.
                    for index, row in req_df.iterrows():
                        column_name = row[field_col]
                        column_value = row[def_value_col]

                        import_df.loc[:, column_name] = column_value

                    # Subset the imported data on the selected static and mapping columns
                    selected_columns = req_df[field_col].append(map_df[field_col])
                    final_df = import_df[selected_columns]

                    # Set column data types
                    columns = collection.dtypes
                    dtypes_set = True
                    for selected_column in selected_columns:
                        coltype = columns[selected_column]
                        if coltype in date_types:  # need to strip the date offset, if any
                            try:
                                if offset_oper == '+':
                                    formatted_values = final_df[selected_column].apply(lambda x: (
                                            strptime(x, date_format) - relativedelta(years=+date_offset)).strftime(
                                        settings.date_format))
                                else:
                                    formatted_values = final_df[selected_column].apply(lambda x: (
                                            strptime(x, date_format) + relativedelta(years=+date_offset)).strftime(
                                        settings.date_format))
                            except Exception as e:
                                msg = 'unable to convert values in column "{COL}" to a datetime format - {ERR}'.format(
                                    COL=selected_column, ERR=e)
                                print(final_df[selected_column])
                                popup_error(msg)
                                logger.exception(msg)
                                dtypes_set = False

                                break
                        else:
                            try:
                                formatted_values = mod_dm.format_values(final_df[selected_column], coltype)
                            except Exception as e:
                                msg = 'unable to convert values in column "{COL}" to "{FMT}" - {ERR}'.format(
                                    COL=selected_column, FMT=coltype, ERR=e)
                                print(final_df[selected_column])
                                logger.exception(msg)
                                popup_error(msg)
                                dtypes_set = False

                                break

                        final_df.loc[:, selected_column] = formatted_values

                    if not dtypes_set:
                        continue

                    # Subset imported data on the specified subset rules
                    subset_df = final_df
                    for sub_num in subs_in_view:
                        sub_col = values['-SUBSET_COL_{}-'.format(sub_num)]
                        sub_oper = values['-SUBSET_OPER_{}-'.format(sub_num)]
                        sub_val = values['-SUBSET_VALUE_{}-'.format(sub_num)]
                        if not sub_col or not sub_oper:
                            continue

                        if sub_col not in selected_columns.values.tolist():
                            msg = 'column "{COL}" used in subset rule "{RULE}" must be one of the required or ' \
                                  'mapping columns chosen for importing'.format(COL=sub_col, RULE=sub_num + 1)
                            popup_error(msg)
                            logger.warning(msg)
                            continue

                        cond_str = '{COL} {OPER} {VAL}'.format(COL=sub_col, OPER=sub_oper, VAL=sub_val)
                        logger.debug('sub-setting table column "{COL}" on condition {RULE}'
                                     .format(COL=sub_col, RULE=cond_str))

                        try:
                            subset_df = subset_df[mod_dm.evaluate_condition(subset_df, cond_str)]
                        except Exception as e:
                            msg = 'failed to subset data on rule "{RULE}" - {ERR}'.format(RULE=cond_str, ERR=e)
                            popup_error(msg)
                            logger.warning(msg)

                            continue

                    # Create record IDs for each row in the final import table if no record ID column provided
                    id_column = record_entry.id_column
                    if id_column not in subset_df.columns:
                        try:
                            date_list = pd.to_datetime(subset_df[record_entry.date_column].fillna(pd.NaT),
                                                       errors='coerce', format=settings.date_format, utc=False)
                        except KeyError:
                            msg = 'failed to create IDs for the new record entries - record date is required for ' \
                                  'new entries'
                            popup_notice(msg)
                            logger.error(msg)
                            record_ids = []

                            continue
                        else:
                            date_list = date_list.tolist()

                        record_ids = record_entry.create_record_ids(date_list, offset=settings.get_date_offset())
                        if not record_ids:
                            msg = 'failed to create IDs for the new record entries'
                            popup_notice(msg)
                            logger.error(msg)
                            record_ids = []

                            continue

                        subset_df.loc[:, id_column] = record_ids

                    # Modify table column values based on the modify column rules
                    for elem_num in mods_in_view:
                        elem_col = values['-MODIFY_COL_{}-'.format(elem_num)]
                        elem_oper = values['-MODIFY_OPER_{}-'.format(elem_num)]
                        elem_val = values['-MODIFY_VALUE_{}-'.format(elem_num)]
                        if not elem_col or not elem_oper:
                            continue

                        if elem_col not in selected_columns.values.tolist():
                            msg = 'column "{COL}" used in modify rule "{RULE}" must be one of the required ' \
                                  'or mapping columns chosen for importing'.format(COL=elem_col, RULE=elem_num + 1)
                            popup_error(msg)
                            logger.warning(msg)

                            continue

                        oper_str = '{COL} {OPER} {VAL}'.format(COL=elem_col, OPER=elem_oper, VAL=elem_val)
                        logger.debug('modifying table column "{COL}" by value "{VAL}" on rule "{RULE}"'
                                     .format(COL=elem_col, VAL=elem_val, RULE=elem_num + 1))

                        try:
                            subset_df.loc[:, elem_col] = mod_dm.evaluate_operation(subset_df, oper_str)
                        except Exception as e:
                            msg = 'failed to modify data column "{COL}" based on modifier rule "{RULE}" - {ERR}' \
                                .format(COL=elem_col, RULE=oper_str, ERR=e)
                            popup_error(msg)
                            logger.warning(msg)

                            continue

                    collection.append(subset_df)

                    # Populate preview with table values
                    final_cols = subset_df.columns.tolist()
                    preview_cols = [record_entry.id_column] + [i for i in final_cols if i != record_entry.id_column]
                    col_widths = mod_dm.calc_column_widths(preview_cols, width=width * 0.77, pixels=True)
                    window['-PREVIEW-'].Widget['columns'] = tuple(preview_cols)
                    window['-PREVIEW-'].Widget['displaycolumns'] = '#all'
                    for index, column_name in enumerate(preview_cols):
                        col_width = col_widths[index]
                        window['-PREVIEW-'].Widget.column(index, width=col_width)
                        window['-PREVIEW-'].Widget.heading(index, text=column_name)

                    sub_nrow = subset_df.shape[0]
                    if sub_nrow >= 10:
                        nhead = 10
                        if sub_nrow <= 20:
                            ntail = sub_nrow - 10
                        else:
                            ntail = 10
                    else:
                        nhead = sub_nrow
                        ntail = 0
                    preview_df = subset_df.head(nhead).append(subset_df.tail(ntail))[preview_cols]

                    window['-PREVIEW-'].update(values=preview_df.values.tolist())

                    # Update import statistic elements
                    nrow, ncol = subset_df.shape
                    window['-NCOL-'].update(value=ncol)
                    window['-NROW-'].update(value=nrow)
                    window['-TABLENAME-'].update(value=record_type)

                    # Enable import button
                    window['-IMPORT-'].update(disabled=False)
                    window['-IMPORT-'].set_focus()

            # Enable /disable panels
            window[panel_keys[current_panel]].update(visible=False)
            window[panel_keys[next_panel]].update(visible=True)

            # Change high-lighted flow control text
            window[panel_names[current_panel]].update(text_color=text_color)
            window[panel_names[next_panel]].update(text_color=select_color)

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
        if event in ('-BACK-', '-HK_LEFT-'):
            prev_panel = current_panel - 1

            # Delete created record IDs if current panel is the preview panel
            if current_panel == last_panel:
                collection.reset()

                if len(record_ids) > 0 and record_entry is not None:
                    logger.info('removing unsaved record IDs')
                    record_entry.remove_unsaved_ids(record_ids)
                    record_ids = []

            # Enable /disable panels
            window[panel_keys[current_panel]].update(visible=False)
            window[panel_keys[prev_panel]].update(visible=True)

            # Change high-lighted flow control text
            window[panel_names[current_panel]].update(text_color=text_color)
            window[panel_names[prev_panel]].update(text_color=select_color)

            # Disable back button if on first panel
            if prev_panel == first_panel:
                window['-BACK-'].update(disabled=True)

            # Disable import button if not on last panel
            if prev_panel != last_panel:
                window['-IMPORT-'].update(disabled=True)

            # Reset current panel variable
            current_panel = prev_panel
            continue

        # Populate column listboxes based on the record type selection
        if event == '-RECORDTYPE-':
            record_type = values['-RECORDTYPE-']

            record_entry = settings.records.fetch_rule(record_type, by_title=True)
            collection = mod_col.RecordCollection(record_type, record_entry.import_table)
            columns = collection.dtypes

            listbox_values = []
            for column in collection.list_fields():
                if column not in reserved_values:
                    listbox_values.append(column)

            # Reset the columns displayed in the required and mapping listboxes
            window['-REQLIST-'].update(values=listbox_values)
            window['-MAPLIST-'].update(values=listbox_values)

            # Reset the tables
            req_df.drop(req_df.index, inplace=True)
            map_df.drop(map_df.index, inplace=True)

            window['-REQCOL-'].update(values=req_df.values.tolist())
            window['-MAPCOL-'].update(values=map_df.values.tolist())

            # Reset the subset rule columns
            for index in range(10):
                window['-SUBSET_COL_{}-'.format(index)].update(values=tuple(sorted(listbox_values)), value='',
                                                               disabled=False, size=(None, 6))
                window['-SUBSET_OPER_{}-'.format(index)].update(value='', disabled=False)
                window['-SUBSET_VALUE_{}-'.format(index)].update(value='', disabled=False)

            # Reset the modify rule columns
            for index in range(10):
                window['-MODIFY_COL_{}-'.format(index)].update(values=tuple(sorted(listbox_values)), value='',
                                                               disabled=False, size=(None, 6))
                window['-MODIFY_OPER_{}-'.format(index)].update(value='', disabled=False)
                window['-MODIFY_VALUE_{}-'.format(index)].update(value='', disabled=False)

            continue

        # Populate tables with columns selected from the list-boxes
        if event in ('-REQLIST-', '-REQLIST-+RETURN+') and record_entry is not None:
            # Get indices of the selected items
            selected_inds = window['-REQLIST-'].get_indexes()
            try:
                next_ind = selected_inds[-1]
            except KeyError:
                logger.warning('no indices selected for required column list')
                continue

            # Find the value names of the selected indices
            current_values = window['-REQLIST-'].get_list_values()
            selected_values = [current_values[i] for i in selected_inds]

            new_df = pd.DataFrame({field_col: selected_values,
                                   dtype_col: [columns[i] for i in selected_values],
                                   def_value_col: ['' for _ in range(len(selected_inds))]})

            # Add new rows to the table
            req_df = req_df.append(new_df, ignore_index=True)
            window['-REQCOL-'].update(values=req_df.values.tolist())

            # Remove column from listbox list
            for column in selected_values:
                listbox_values.remove(column)

            window['-REQLIST-'].update(values=listbox_values, set_to_index=[next_ind], scroll_to_index=next_ind)
            window['-MAPLIST-'].update(values=listbox_values)

            continue

        if event == '-REQLIST-+UP+':
            print('scrolling up')
            scroll_list_up(window['-REQLIST-'])
            continue

        if event == '-REQLIST-+DOWN+':
            scroll_list_down(window['-REQLIST-'])
            print('scrolling down')
            continue

        if event in ('-MAPLIST-', '-MAPLIST-+RETURN+') and record_entry is not None:
            # Get index of column in listbox values
            selected_inds = window['-MAPLIST-'].get_indexes()
            try:
                next_ind = selected_inds[-1]
            except IndexError:
                logger.warning('no indices selected for mapping column list')
                continue

            # Find the value names of the selected indices
            current_values = window['-MAPLIST-'].get_list_values()
            selected_values = [current_values[i] for i in selected_inds]

            new_df = pd.DataFrame({field_col: selected_values,
                                   dtype_col: [columns[i] for i in selected_values],
                                   file_col: ['' for _ in range(len(selected_inds))]})

            # Add new rows to the table
            map_df = map_df.append(new_df, ignore_index=True)
            window['-MAPCOL-'].update(values=map_df.values.tolist())

            # Remove column from listbox list
            for column in selected_values:
                listbox_values.remove(column)

            window['-REQLIST-'].update(values=listbox_values)
            window['-MAPLIST-'].update(values=listbox_values, set_to_index=[next_ind], scroll_to_index=next_ind)

            continue

        if event == '-MAPLIST-+UP+':
            print('scrolling up')
            scroll_list_up(window['-MAPLIST-'])
            continue

        if event == '-MAPLIST-+DOWN+':
            scroll_list_down(window['-MAPLIST-'])
            print('scrolling down')
            continue

        if event == '-MAPCOL-+DELETE+':
            indices = values['-MAPCOL-']
            if len(indices) < 1:
                continue

            col_names = map_df.loc[indices, field_col]

            # Remove rows from the dataframe
            map_df.drop(indices, axis=0, inplace=True)
            map_df.reset_index(drop=True, inplace=True)
            window['-MAPCOL-'].update(values=map_df.values.tolist())

            # Return columns to the listboxes
            for col_name in col_names:
                if col_name not in req_df[field_col].tolist():
                    if col_name not in listbox_values:
                        listbox_values.append(col_name)

            window['-REQLIST-'].update(values=listbox_values)
            window['-MAPLIST-'].update(values=listbox_values)

            # Highlight the next row in the table
            next_ind = indices[0]
            if next_ind < map_df.shape[0]:
                window['-MAPCOL-'].update(select_rows=[next_ind])

        if event == '-REQCOL-+DELETE+':
            indices = values['-REQCOL-']
            if len(indices) < 1:
                continue

            col_names = req_df.loc[indices, field_col]

            # Remove rows from the dataframe
            req_df.drop(indices, axis=0, inplace=True)
            req_df.reset_index(drop=True, inplace=True)
            window['-REQCOL-'].update(values=req_df.values.tolist())

            # Return columns to the listboxes
            for col_name in col_names:
                if col_name not in map_df[field_col].tolist():  # not found in other dataframe
                    if col_name not in listbox_values:  # not already somehow in the listboxes
                        listbox_values.append(col_name)

            window['-REQLIST-'].update(values=listbox_values)
            window['-MAPLIST-'].update(values=listbox_values)

            # Highlight the next row in the table
            next_ind = indices[0]
            if next_ind < req_df.shape[0]:
                window['-REQCOL-'].update(select_rows=[next_ind])

        # Edit a table row's values
        if event in ('-REQCOL-', '-REQCOL-+RETURN+') and record_entry is not None:
            try:
                row_index = values['-REQCOL-'][0]
            except IndexError:
                continue

            # Find datatype of selected column
            row_name = req_df.at[row_index, field_col]
            row_dtype = columns[row_name]
            edit_map = {'DataType': row_dtype, 'ElementType': 'input'}

            # Modify table row
            row = edit_row_window(req_df.iloc[row_index], edit_columns={def_value_col: edit_map})
            window['-REQCOL-'].update(values=req_df.values.tolist())
            if row is not None:
                req_df.iloc[row_index] = row

            # Highlight the next row in the table
            next_ind = row_index + 1
            if next_ind < req_df.shape[0]:
                window['-REQCOL-'].update(select_rows=[next_ind])

            continue

        if event in ('-MAPCOL-', '-MAPCOL-+RETURN+') and record_entry is not None:
            try:
                row_index = values['-MAPCOL-'][0]
            except IndexError:
                continue

            # Find datatype of selected column
            edit_map = {'DataType': 'string', 'ElementType': 'input', 'Default': map_df.loc[row_index, field_col]}

            # Modify table row
            row = edit_row_window(map_df.iloc[row_index], edit_columns={file_col: edit_map})
            window['-MAPCOL-'].update(values=map_df.values.tolist())
            if row is not None:
                map_df.iloc[row_index] = row

            # Highlight the next row in the table
            next_ind = row_index + 1
            if next_ind < map_df.shape[0]:
                window['-MAPCOL-'].update(select_rows=[next_ind])

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

            window.refresh()
            window['-SUBSET-'].contents_changed()

            logger.debug('adding subset rule "{RULE}" with key "{KEY}"'.format(RULE=next_num, KEY=next_key))
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

            window.refresh()
            window['-SUBSET-'].contents_changed()

            logger.debug('deleting subset rule "{RULE}" with key "{KEY}"'.format(RULE=subset_num, KEY=subset_key))
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

            window.refresh()
            window['-MODIFY-'].contents_changed()

            logger.debug('adding modify column rule "{RULE}" with key "{KEY}"'.format(RULE=next_num, KEY=next_key))
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

            window.refresh()
            window['-MODIFY-'].contents_changed()

            logger.debug('deleting modify column rule "{RULE}" with key "{KEY}"'.format(RULE=elem_num, KEY=mod_key))
            continue

    window.close()
    layout = None
    window = None
    gc.collect()

    return True


def record_import_window(table, enable_new: bool = False):
    """
    Display the import from database window.
    """
    min_w, min_h = (int(mod_const.WIN_WIDTH * 0.5), int(mod_const.WIN_HEIGHT * 0.5))

    # Prepare the associated record entry for the record table
    record_entry = settings.records.fetch_rule(table.record_type)
    import_rules = table.import_rules if table.import_rules else record_entry.import_rules

    record_class = mod_records.DatabaseRecord

    # Check user permissions
    creatable = (True if user.check_permission(record_entry.permissions['create']) and enable_new is True else False)

    # Layout

    # Window and element size parameters
    header_col = mod_const.HEADER_COLOR

    header_font = mod_const.HEADING_FONT

    pad_el = mod_const.ELEM_PAD
    pad_frame = mod_const.FRAME_PAD

    # Keyboard shortcuts
    hotkeys = settings.hotkeys
    cancel_shortcut = hotkeys['-HK_ESCAPE-'][2]
    new_shortcut = hotkeys['-HK_ENTER-'][2]

    # Title
    title_h = mod_const.TITLE_HEIGHT
    title = 'Import {TYPE} records'.format(TYPE=table.description)
    title_layout = [[sg.Canvas(size=(0, title_h), background_color=header_col),
                     sg.Text(title, pad=(pad_frame, 0), background_color=header_col, font=header_font)]]

    # Control buttons
    bttn_h = mod_const.BTTN_HEIGHT
    bttn_layout = [[sg.Canvas(size=(0, bttn_h)),
                    sg.Button('', key='-CANCEL-', image_data=mod_const.CANCEL_ICON, image_size=mod_const.BTTN_SIZE,
                              disabled=False,
                              tooltip='Cancel data import ({})'.format(cancel_shortcut)),
                    sg.Button('', key='-NEW-', image_data=mod_const.NEW_ICON, image_size=mod_const.BTTN_SIZE,
                              pad=((0, pad_el), 0), visible=creatable,
                              tooltip='Create new record ({})'.format(new_shortcut))]]

    other_h = title_h + bttn_h

    # Import data table
    tbl_layout = [[table.layout(size=(min_w, min_h - other_h))]]

    layout = [[sg.Col(title_layout, key='-HEADER-', background_color=header_col,
                      vertical_alignment='c', element_justification='l', justification='l', expand_x=True)],
              [sg.Col(tbl_layout, expand_x=True, expand_y=True, vertical_alignment='t')],
              [sg.Col(bttn_layout, key='-BUTTON-', justification='l', element_justification='c', vertical_alignment='c',
                      expand_x=True)]]

    # Finalize GUI window
    window = sg.Window('', layout, modal=True, resizable=True)
    window.finalize()
    window.hide()

    window.set_min_size((min_w, min_h))

    # Bind event keys
    table.bind_keys(window)

    # Update the table display
    table.update_display(window)

    # Expand the table frames
    frame_key = table.key_lookup('FilterFrame')
    frame = window[frame_key]
    if not frame.metadata['visible']:  # frame is collapsed
        table.collapse_expand(window)

    # Adjust window size
    screen_w, screen_h = window.get_screen_dimensions()
    win_w = int(screen_w * 0.8)
    win_h = int(screen_h * 0.8)

    tbl_w = win_w if win_w > min_w else min_w
    tbl_h = win_h - other_h if win_h > min_h else min_h - other_h
    table.resize(window, size=(tbl_w, tbl_h))

    window.un_hide()
    window = align_window(window)

    current_w, current_h = window.size

    # Main loop
    elem_key = table.key_lookup('Element')
    while True:
        event, values = window.read(timeout=500)

        if event in (sg.WIN_CLOSED, '-CANCEL-'):  # selected close-window or Cancel
            break

        win_w, win_h = window.size
        if win_w != current_w or win_h != current_h:
            logger.debug('new window size is {W} x {H}'.format(W=win_w, H=win_h))
            tbl_w = win_w if win_w > min_w else min_w
            tbl_h = win_h - other_h if win_h > min_h else min_h - other_h

            # Update sizable elements
            table.resize(window, size=(tbl_w, tbl_h))
            current_w, current_h = (win_w, win_h)

        if enable_new and event == '-NEW-':  # selected to create a new record
            if table.record_type is None:
                msg = 'failed to create a new record - missing required configuration parameter "RecordType"'
                popup_error(msg)
                logger.warning(msg)

                continue

            # Create a new record object
            record_date = datetime.datetime.now()
            record_id = record_entry.create_record_ids(record_date, offset=settings.get_date_offset())
            if not record_id:
                msg = 'failed to create a new record - unable to create an ID for the new record'
                logger.error(msg)
                popup_error(msg)

                continue

            logger.info('RecordEntry {NAME}: creating new record {ID}'.format(NAME=record_entry.name, ID=record_id))

            record_data = pd.Series(index=list(table.columns))
            record_data['RecordID'] = record_id
            record_data['RecordDate'] = record_date

            record = record_class(record_entry.name, record_entry.record_layout, level=0)
            try:
                record.initialize(record_data, new=True)
            except Exception as e:
                msg = 'failed to create a new record {ID}'.format(ID=record_id)
                logger.error('{MSG} - {ERR}'.format(MSG=msg, ERR=e))
                popup_error(msg)
            else:
                record = record_window(record)

                # Reload the display records
                if record:
                    import_df = record_entry.import_records(filter_params=table.parameters, import_rules=import_rules)

                    table.reset(window, reset_filters=False, collapse=False)
                    table.append(import_df)
                    table.update_display(window)

            continue

        # Import table events
        try:
            element_event = table.bindings[event]
        except KeyError:
            continue
        else:
            reload = False

            # Load record event
            if element_event == 'Load':  # click to open record
                # Close options panel, if open
                table.set_table_dimensions(window)

                # retrieve selected row
                try:
                    row_index = values[elem_key][0]
                except IndexError:
                    continue
                else:
                    table._selected_rows = [row_index]
                    table.update_annotation(window)

                    # Get the real index of the selected row
                    index = table.get_index(row_index)
                    record = table.load_record(index, level=0)
                    if record:
                        reload = True

            # Table filter event
            elif element_event == 'Filter':
                for param in table.parameters:
                    # Set parameter values from window elements
                    param.format_value(values)

                # Load the display records
                reload = True

            else:
                table.run_event(window, event, values)

            if reload:  # should reload the import records
                table.reset(window, reset_filters=False, collapse=False)

                import_df = record_entry.import_records(filter_params=table.parameters, import_rules=import_rules)
                table.append(import_df)
                table.update_display(window)

    window.close()
    layout = None
    window = None
    gc.collect()


def import_window(table, params: list = None):
    """
    Display the importer window.
    """
    min_w, min_h = (int(mod_const.WIN_WIDTH * 0.5), int(mod_const.WIN_HEIGHT * 0.5))

    params = params if params is not None else []
    try:
        record_type = table.record_type
    except AttributeError:
        enable_search = False
        record_entry = None
        import_rules = None
    else:
        enable_search = True
        record_entry = settings.records.fetch_rule(record_type)
        import_rules = table.import_rules if table.import_rules else record_entry.import_rules

    # Window and element size parameters
    font_h = mod_const.HEADING_FONT
    main_font = mod_const.MAIN_FONT

    pad_v = mod_const.VERT_PAD
    pad_h = mod_const.HORZ_PAD
    pad_el = mod_const.ELEM_PAD
    pad_frame = mod_const.FRAME_PAD

    bttn_text_col = mod_const.WHITE_TEXT_COLOR
    bttn_bg_col = mod_const.BUTTON_BG_COLOR
    bg_col = mod_const.DEFAULT_BG_COLOR
    header_col = mod_const.HEADER_COLOR

    tbl_pad = pad_frame * 2  # padding on both sides of the table

    # GUI layout
    title_h = mod_const.TITLE_HEIGHT
    header_layout = [[sg.Canvas(size=(0, title_h), background_color=header_col),
                      sg.Text('Import Missing Data', pad=(pad_frame, 0), background_color=header_col, font=font_h)]]

    # Search parameter layout
    param_h = 60
    param_layout = []
    for param in params:
        element_layout = param.layout(padding=((0, pad_h), 0))
        param_layout += element_layout

    if len(param_layout) > 0:
        param_layout.append(mod_lo.B2('Find', key='-FIND-', pad=(0, 0), bind_return_key=True, use_ttk_buttons=True,
                                      button_color=(bttn_text_col, bttn_bg_col), disabled=(not enable_search)))
        top_layout = [[sg.Col([param_layout], pad=(pad_frame, 0), background_color=bg_col)],
                      [sg.HorizontalSeparator(pad=(pad_frame, pad_v), color=mod_const.HEADER_COLOR)]]
    else:
        top_layout = [[]]

    bttn_h = mod_const.BTTN_HEIGHT
    bttn_layout = [[sg.Canvas(size=(0, bttn_h)),
                    sg.Button('', key='-CANCEL-', image_data=mod_const.CANCEL_ICON, image_size=mod_const.BTTN_SIZE,
                              pad=(pad_el, 0), tooltip='Cancel importing'),
                    sg.Button('', key='-IMPORT-', image_data=mod_const.DB_IMPORT_ICON, image_size=mod_const.BTTN_SIZE,
                              pad=(pad_el, 0), tooltip='Import the selected transaction orders')]]

    other_h = title_h + bttn_h + param_h

    tbl_size = (min_w - tbl_pad, min_h - other_h)
    tbl_layout = [[table.layout(size=tbl_size, padding=(pad_frame, 0))]]

    layout = [[sg.Col(header_layout, key='-HEADER-', background_color=header_col, element_justification='l',
                      vertical_alignment='c', expand_x=True)],
              [sg.Col(top_layout, key='-PARAMS-', background_color=bg_col, vertical_alignment='c', expand_x=True)],
              [sg.Col(tbl_layout, background_color=bg_col, expand_x=True, expand_y=True, vertical_alignment='t')],
              [sg.Col(bttn_layout, key='-BUTTON-', element_justification='c', expand_x=True, vertical_alignment='c')]]

    window = sg.Window('Import Data', layout, font=main_font, modal=True, resizable=True)
    window.finalize()
    window.hide()

    # Resize and center the screen
    screen_w, screen_h = window.get_screen_dimensions()
    win_w = int(screen_w * 0.8)
    win_h = int(screen_h * 0.8)

    tbl_w = win_w - tbl_pad if win_w > min_w else min_w - tbl_pad
    tbl_h = win_h - other_h if win_h > min_h else min_h - other_h
    table.resize(window, size=(tbl_w, tbl_h))

    window.un_hide()
    window = align_window(window)
    current_w, current_h = window.size

    # Start event loop
    table.update_display(window)

    select_index = []
    while True:
        event, values = window.read(timeout=500)

        if event in (sg.WIN_CLOSED, '-CANCEL-'):  # selected close-window or Cancel
            break

        win_w, win_h = window.size
        if win_w != current_w or win_h != current_h:
            logger.debug('new window size is {W} x {H}'.format(W=win_w, H=win_h))

            # Update sizable elements
            tbl_w = win_w - tbl_pad if win_w > min_w else min_w - tbl_pad
            tbl_h = win_h - other_h if win_h > min_h else min_h - other_h
            table.resize(window, size=(tbl_w, tbl_h))

            current_w, current_h = (win_w, win_h)

        if event == '-FIND-':  # click the find button to query database
            try:
                record_df = record_entry.import_records(filter_params=params, import_rules=import_rules)
            except Exception as e:
                popup_error('failed to import records matching the defined search parameters from the database - {ERR}'
                            .format(ERR=e))
                continue

            table.append(record_df)
            table.update_display(window)

            continue

        if event == '-IMPORT-':  # click 'Import' button
            # Get index of selected rows
            selected_rows = values[table.key_lookup('Element')]

            # Get real index of selected rows
            select_index = [table.index_map[i] for i in selected_rows]

            break

        if event in table.bindings:
            table.run_event(window, event, values)

            continue

    window.close()
    layout = None
    window = None
    gc.collect()

    try:
        return table.data(indices=select_index)
    except KeyError:
        raise KeyError('one or more selected index {} is missing from the import table dataframe'.format(select_index))


def about():
    """
    Display the "about program" window.
    """
    # Window and element size parameters
    bg_col = mod_const.DEFAULT_BG_COLOR
    header_col = mod_const.HEADER_COLOR

    header_font = mod_const.HEADING_FONT
    sub_font = mod_const.BOLD_LARGE_FONT
    text_font = mod_const.LARGE_FONT

    pad_frame = mod_const.FRAME_PAD
    pad_el = mod_const.ELEM_PAD

    # GUI layout
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

    window = sg.Window('About REM', layout, modal=True, resizable=False)

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
    if not win_size:
        win_size = (mod_const.WIN_WIDTH, mod_const.WIN_HEIGHT)

    # Window and element size parameters
    pad_el = mod_const.ELEM_PAD
    pad_frame = mod_const.FRAME_PAD
    pad_v = mod_const.VERT_PAD

    font_h = mod_const.HEADING_FONT
    header_col = mod_const.HEADER_COLOR

    # Keyboard shortcuts
    hotkeys = settings.hotkeys
    cancel_shortcut = hotkeys['-HK_ESCAPE-'][2]
    save_shortcut = hotkeys['-HK_ENTER-'][2]

    # GUI layout

    # Button layout
    bttn_layout = [[sg.Button('', key='-CANCEL-', image_data=mod_const.CANCEL_ICON, image_size=mod_const.BTTN_SIZE,
                              pad=(pad_el, 0),
                              tooltip='Cancel edit ({})'.format(cancel_shortcut)),
                    sg.Button('', key='-SAVE-', image_data=mod_const.CONFIRM_ICON, image_size=mod_const.BTTN_SIZE,
                              bind_return_key=True, pad=(pad_el, 0),
                              tooltip='Save changes ({})'.format(save_shortcut))]]

    # Get parameter layout from settings
    settings_layout = settings.layout(win_size)

    layout = [[sg.Col([[sg.Text('Edit Program Settings', pad=(pad_frame, (pad_frame, pad_v)), font=font_h,
                                background_color=header_col)]],
                      justification='l', background_color=header_col, expand_x=True, expand_y=True)],
              settings_layout,
              [sg.Col(bttn_layout, justification='c', pad=(0, (pad_v, pad_frame)))]]

    # Finalize window and center
    window = sg.Window('Settings', layout, modal=True, resizable=False)
    window.finalize()

    window = align_window(window)

    element_keys = {'-LOCALE-': 'locale', '-TEMPLATE-': 'template',
                    '-CSS-': 'css', '-PORT-': 'port', '-SERVER-': 'host', '-DATABASE-': 'dbname',
                    '-DISPLAY_DATE-': 'display_date'}
    for element_key in element_keys:
        try:
            window[element_key].expand(expand_x=True)
        except KeyError:
            msg = 'failed to find element {} in the settings'.format(element_keys[element_key])
            logger.error(msg)

    # Bind keys to events
    window = settings.set_shortcuts(window)

    # Start event loop
    while True:
        event, values = window.read()

        if event in (sg.WIN_CLOSED, '-CANCEL-', '-HK_ESCAPE-'):  # selected close-window or Cancel
            break

        if event in ('-SAVE-', '-HK_ENTER-'):
            for element_key in element_keys:
                attribute = element_keys[element_key]
                element_value = values[element_key]
                settings.edit_attribute(attribute, element_value)
            break

    window.close()
    layout = None
    window = None
    gc.collect()


def range_value_window(dtype, current: list = None, title: str = None, location: tuple = None, size: tuple = None):
    """
    Display window for obtaining values for a ranged parameter.
    """
    value_range = current if current and len(current) == 2 else [None, None]

    # Element settings
    pad_el = mod_const.ELEM_PAD
    pad_v = mod_const.VERT_PAD
    pad_h = mod_const.HORZ_PAD

    bold_font = mod_const.BOLD_LARGE_FONT

    bg_col = mod_const.DEFAULT_BG_COLOR

    # Component parameters
    orig_val1, orig_val2 = value_range
    etype = 'input' if dtype not in settings.supported_date_dtypes else 'date'

    param1_entry = {'Description': '', 'ElementType': etype, 'DataType': dtype, 'DefaultValue': orig_val1}
    param1 = mod_param.initialize_parameter('First', param1_entry)

    param2_entry = {'Description': '', 'ElementType': etype, 'DataType': dtype, 'DefaultValue': orig_val2}
    param2 = mod_param.initialize_parameter('Second', param2_entry)

    # Window and element sizes
    bttn_h = pad_el * 3 + mod_const.BTTN_SIZE[1]  # button height + top/bottom padding and button border
    sep_w = 1 * 10 + pad_el * 2  # field separator character and spacing

    default_w = mod_const.FIELD_SIZE[0] * 2 + sep_w + pad_h
    default_w2 = mod_const.FIELD_SIZE[0] + sep_w + pad_h
    default_h = mod_const.FIELD_SIZE[1] + bttn_h + pad_v
    if isinstance(size, tuple) and len(size) == 2:
        width, height = size
        if isinstance(width, int):
            win_w = width if width > default_w2 else default_w2
            if win_w < default_w:
                nrow = 2
                default_h = mod_const.FIELD_SIZE[1] * 2 + bttn_h + pad_v
            else:
                nrow = 1
        else:
            win_w = default_w
            nrow = 1
        win_h = height if (isinstance(height, int) and height >= default_h) else default_h
    else:
        win_w = default_w
        win_h = default_h
        nrow = 1

    # Layout
    if nrow == 1:
        row1 = param1.layout() + [sg.Text('-', pad=(pad_el, 0), font=bold_font)] + param2.layout()
        elem_layout = [sg.Col([row1], pad=(int(pad_h / 2), 0), background_color=bg_col)]
    else:
        row1 = param1.layout() + [sg.Text('-', pad=(pad_el, 0), font=bold_font)]
        row2 = param2.layout()
        elem_layout = [sg.Col([row1, row2], pad=(int(pad_h / 2), 0), background_color=bg_col)]

    bttn_layout = sg.Button('', key='-SAVE-', image_data=mod_const.CONFIRM_ICON, image_size=mod_const.BTTN_SIZE,
                            bind_return_key=True, pad=(0, int(pad_v / 2)))

    layout = [[sg.Frame('', [elem_layout, [bttn_layout]], size=(win_w, win_h), background_color=bg_col,
                        title_color=mod_const.BORDER_COLOR, element_justification='c', vertical_alignment='t')]]

    win_title = title if title else 'range'
    window = sg.Window(win_title, layout, modal=True, resizable=False, no_titlebar=True, location=location)
    window.finalize()

    if not location:  # center window if no location provided
        window = align_window(window)

    # Bind keys to events
    window = settings.set_shortcuts(window)

    for parameter in (param1, param2):
        parameter.bind_keys(window)

    # Start event loop
    while True:
        event, values = window.read()

        if event in (sg.WIN_CLOSED, '-HK_ESCAPE-'):  # selected close-window or Cancel
            break

        if event in param1.bindings:
            param1.run_event(window, event, values)

            continue

        if event in param2.bindings:
            param2.run_event(window, event, values)

            continue

        if event in ('-SAVE-', '-HK_ENTER-'):
            try:
                value_range[0] = param1.format_value(values)
                value_range[1] = param2.format_value(values)
            except ValueError:
                msg = 'failed to format values as "{DTYPE}"'.format(DTYPE=dtype)
                popup_error(msg)

                continue

            break

    window.close()
    layout = None
    window = None
    gc.collect()

    return value_range


def conditional_value_window(dtype, current: list = None, title: str = None, location: tuple = None, size: tuple = None):
    """
    Display window for obtaining values for a ranged parameter.
    """
    saved_value = current if current and len(current) == 2 else [None, None]
    operators = ['>', '<', '>=', '<=', '=']

    # Element settings
    pad_el = mod_const.ELEM_PAD
    font = mod_const.LARGE_FONT
    in_col = mod_const.FIELD_BG_COLOR
    bg_col = mod_const.DEFAULT_BG_COLOR
    text_col = mod_const.DEFAULT_TEXT_COLOR

    # Component parameter
    current_oper, current_value = saved_value
    etype = 'input' if dtype not in settings.supported_date_dtypes else 'date'

    param_entry = {'Description': '', 'ElementType': etype, 'DataType': dtype, 'DefaultValue': current_value}
    param = mod_param.initialize_parameter('Value', param_entry)

    # Window and element sizes
    bttn_h = pad_el * 3 + mod_const.BTTN_SIZE[1]  # button height + top/bottm padding and button border
    oper_w = 4 * 9 + pad_el

    default_w = oper_w + mod_const.FIELD_SIZE[0]
    default_h = mod_const.FIELD_SIZE[1] + bttn_h + 10

    if isinstance(size, tuple) and len(size) == 2:
        width, height = size
        win_w = width if (isinstance(width, int) and width >= default_w) else default_w
        win_h = height if (isinstance(height, int) and height >= default_h) else default_h
    else:
        win_w = default_w
        win_h = default_h

    # Layout
    oper_key = '-OPERATOR-'
    elem_layout = [sg.Combo(operators, default_value=current_oper, key=oper_key, enable_events=True, size=(4, 1),
                            pad=((0, pad_el), 0), font=font, background_color=in_col, text_color=text_col,
                            disabled=False)]
    elem_layout += param.layout()

    bttn_layout = sg.Button('', key='-SAVE-', image_data=mod_const.CONFIRM_ICON, image_size=mod_const.BTTN_SIZE,
                            bind_return_key=True, pad=(0, pad_el))

    layout = [[sg.Frame('', [elem_layout, [bttn_layout]], size=(win_w, win_h), background_color=bg_col,
                        title_color=mod_const.BORDER_COLOR, element_justification='c', vertical_alignment='t')]]

    win_title = title if title else 'conditional selection'
    window = sg.Window(win_title, layout, modal=True, resizable=False, no_titlebar=True, location=location)
    window.finalize()

    if not location:  # center window if no location provided
        window = align_window(window)

    # Bind keys to events
    window = settings.set_shortcuts(window)
    param.bind_keys(window)

    window.refresh()

    # Start event loop
    while True:
        event, values = window.read()

        if event in (sg.WIN_CLOSED, '-HK_ESCAPE-', None):  # selected close-window or Cancel
            break

        if event in param.bindings:
            param.run_event(window, event, values)

            continue

        if event == oper_key:
            window[oper_key].Widget.configure(foreground=text_col)

            continue

        if event in ('-SAVE-', '-HK_ENTER-'):
            operator = values[oper_key]
            if operator not in operators:
                # Highlight the operator element red to indicate that the value is not supported
                window[oper_key].Widget.configure(foreground=mod_const.ERROR_COLOR)

                continue

            try:
                saved_value[0] = operator
                saved_value[1] = param.format_value(values)
            except ValueError:
                msg = 'failed to format values as "{DTYPE}"'.format(DTYPE=dtype)
                popup_error(msg)

                continue

            break

    window.close()
    layout = None
    window = None
    gc.collect()

    return saved_value


def select_value_window(values, current: list = None, title: str = None, location: tuple = None, size: tuple = None):
    """
    Display window for obtaining one or more values from a list of possible choices.
    """
    if not isinstance(values, list):
        values = [values]

    if current is not None:
        current_values = [i for i in current if i in values]
    else:
        current_values = []

    selection = current_values

    # Element settings
    pad_el = mod_const.ELEM_PAD
    font = mod_const.LARGE_FONT
    in_col = mod_const.FIELD_BG_COLOR
    bg_col = mod_const.DEFAULT_BG_COLOR

    # Keyboard shortcuts
    hotkeys = settings.hotkeys
    save_shortcut = hotkeys['-HK_ENTER-'][2]

    # Window and element sizes
    nchar = max([len(i) for i in values])
    nvalues = len(values)

    bttn_h = pad_el * 2 + mod_const.BTTN_SIZE[1]

    default_w = nchar * 9 + pad_el
    default_h = nvalues * 9 + bttn_h if nvalues <= 6 else 6 * 9 + bttn_h

    if isinstance(size, tuple) and len(size) == 2:
        width, height = size
        win_w = width if width >= default_w else default_w
        win_h = height if height >= default_h else default_h
    else:
        win_w = default_w
        win_h = default_h

    # Layout
    elem_layout = sg.Listbox(values, default_values=current_values, key='-SELECT-', expand_x=True, expand_y=True,
                             font=font, background_color=in_col, disabled=False, select_mode='multiple',
                             tooltip='Select one or more values from the list')

    bttn_layout = sg.Button('', key='-OK-', image_data=mod_const.CONFIRM_ICON, image_size=mod_const.BTTN_SIZE,
                            bind_return_key=True, pad=(0, pad_el),
                            tooltip='Accept selection ({})'.format(save_shortcut))

    layout = [[sg.Frame('', [[elem_layout], [bttn_layout]], size=(win_w, win_h), background_color=bg_col,
                        title_color=mod_const.BORDER_COLOR, element_justification='c')]]

    window = sg.Window(title, layout, modal=True, resizable=False, no_titlebar=True, location=location)
    window.finalize()

    if not location:  # center window if no location provided
        window = align_window(window)

    # Bind keys to events
    window = settings.set_shortcuts(window)

    # Start event loop
    while True:
        event, values = window.read()

        if event in (sg.WIN_CLOSED, '-HK_ESCAPE-'):  # selected close-window or Cancel
            break

        if event in ('-OK-', '-HK_ENTER-'):
            selection = values['-SELECT-']

            break

    window.close()
    layout = None
    window = None
    gc.collect()

    return selection


def edit_row_window(row, edit_columns: dict = None, header_map: dict = None, win_size: tuple = None):
    """
    Display window for user to add or edit a row.

    Arguments:
        row (Series): pandas Series containing the row data.

        edit_columns (dict): dictionary of columns that are editable along with their datatypes.

        header_map (dict): dictionary mapping dataframe columns to display columns.

        win_size (tuple): tuple containing the window width and height.
    """
    is_float_dtype = pd.api.types.is_float_dtype
    is_integer_dtype = pd.api.types.is_integer_dtype
    is_datetime_dtype = pd.api.types.is_datetime64_any_dtype
    is_bool_dtype = pd.api.types.is_bool_dtype

    date_types = settings.supported_date_dtypes
    int_types = settings.supported_int_dtypes
    float_types = settings.supported_float_dtypes
    bool_types = settings.supported_bool_dtypes
    str_types = settings.supported_str_dtypes
    cat_dtypes = settings.supported_cat_dtypes

    converter = {}
    for i in int_types:
        converter[i] = int

    for i in float_types:
        converter[i] = float

    for i in bool_types:
        converter[i] = bool

    for i in str_types + cat_dtypes:
        converter[i] = np.object_

    for i in date_types:
        converter[i] = np.datetime64

    if not isinstance(edit_columns, dict) and edit_columns is not None:
        logger.error('argument edit_columns must be a dictionary but has current type "{TYPE}"'
                     .format(TYPE=type(edit_columns)))
        return row

    if edit_columns is None:
        edit_columns = {}

    if win_size:
        width, height = win_size
    else:
        width, height = (mod_const.WIN_WIDTH, mod_const.WIN_HEIGHT)

    # Format dataframe as a list for the layout
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
    for column in edit_columns:
        if column not in display_header:
            logger.warning('editable column "{COL}" not found in the display header'.format(COL=column))
            continue

        element_key = '-{COL}-'.format(COL=column)
        edit_keys[column] = element_key

    # Window and element size parameters
    main_font = mod_const.MAIN_FONT
    font_size = main_font[1]

    pad_el = mod_const.ELEM_PAD
    pad_frame = mod_const.FRAME_PAD
    pad_v = mod_const.VERT_PAD

    header_col = mod_const.TBL_HEADER_COLOR
    in_col = mod_const.FIELD_BG_COLOR

    # GUI layout

    # Buttons
    bttn_layout = [[sg.Button('', key='-CANCEL-', image_data=mod_const.CANCEL_ICON, image_size=mod_const.BTTN_SIZE,
                              pad=(pad_el, 0), tooltip='Cancel edit'),
                    sg.Button('', key='-SAVE-', image_data=mod_const.CONFIRM_ICON, image_size=mod_const.BTTN_SIZE,
                              bind_return_key=True, pad=(pad_el, 0), tooltip='Save changes')]]

    # Table
    lengths = mod_dm.calc_column_widths(display_header, width=width, font_size=font_size, pixels=False)

    # Define the layout for each field of the row that will be displayed
    tbl_layout = []
    dtype_map = {}
    focus_element = None
    for i, display_column in enumerate(display_header):
        display_name = header_map[display_column]

        # Column header
        col_width = lengths[i]
        col_key = '-{COL}-'.format(COL=display_column.upper())
        column_layout = [[sg.Text(display_name, key=col_key, size=(col_width, 1), auto_size_text=False, border_width=1,
                                  relief='sunken', background_color=header_col, justification='c', font=main_font,
                                  tooltip=display_name)]]

        # Column value
        field_val = row[display_column]
        print('value of field {} is {}'.format(display_column, field_val))
        if display_column in edit_keys:
            col_def = edit_columns[display_column]
            readonly = False

            # Determine the element and data types of the column
            element_key = edit_keys[display_column]
            try:
                etype = col_def['ElementType'].lower()
            except (KeyError, AttributeError):
                etype = 'input'
                logger.warning('unable to obtain the element type of editable column "{COL}" ... setting to default '
                               '"input"'.format(COL=display_column))
            else:
                logger.debug('column "{COL}" is editable and has element type "{TYPE}"'
                             .format(COL=display_column, TYPE=etype))
            try:
                dtype = col_def['DataType'].lower()
            except (KeyError, AttributeError):
                dtype = 'string'
                logger.warning('unable to obtain the data type of editable column "{COL}" ... setting to default '
                               '"string"'.format(COL=display_column))
            else:
                logger.debug('column "{COL}" has data type "{TYPE}"'
                             .format(COL=display_column, TYPE=dtype))

            if (pd.isna(field_val) or field_val == '') and 'Default' in col_def:
                field_val = col_def['Default']
                print('setting value of editable field {} to default {}'.format(display_column, field_val))

        else:
            logger.debug('column "{COL}" is marked as readonly'.format(COL=display_column))
            element_key = '-{COL}_VALUE-'.format(COL=display_column.upper())
            readonly = True
            etype = 'input'
            dtype = 'string'

        # Add the column data type to the dtype mapper
        dtype_map[display_column] = converter.get(dtype, np.object_)

        # Create the layout for the field value based on the element type. Can either be an input element or dropdown
        if etype == 'dropdown':
            try:
                values = edit_columns[display_column]['Values']
            except KeyError:
                values = [field_val]
            column_layout.append([sg.DropDown(values, default_value=field_val, key=element_key, size=(col_width - 2, 1),
                                              font=main_font, readonly=readonly,
                                              tooltip='Select item from the dropdown menu')])
        else:
            if not focus_element and not readonly:  # sets focus to first editable input element
                focus_element = element_key
                print('focus will be set to display column value {}'.format(display_column))

            column_layout.append([sg.Input(field_val, key=element_key, size=(col_width, 1), border_width=1,
                                           font=main_font, justification='r', readonly=readonly,
                                           background_color=in_col, tooltip=field_val)])

        tbl_layout.append(sg.Col(column_layout, pad=(0, 0), expand_x=True))

    # create the window layout
    layout = [[sg.Frame('', [tbl_layout], relief='sunken', border_width=1, pad=(pad_frame, (pad_frame, 0)))],
              [sg.Col(bttn_layout, justification='c', pad=(pad_frame, (pad_v, pad_frame)))]]

    window = sg.Window('Modify Record', layout, modal=True, resizable=False)
    window.finalize()

    # Resize window
    screen_w, screen_h = window.get_screen_dimensions()
    if win_size:
        win_w, win_h = win_size
    else:
        win_w = int(screen_w * 0.9)

    # Expand column header widths to fit the screen size
    col_lengths = mod_dm.calc_column_widths(display_header, width=win_w, font_size=font_size, pixels=False)

    for i, display_column in enumerate(display_header):
        col_width = col_lengths[i]
        col_key = '-{COL}-'.format(COL=display_column.upper())

        window[col_key].set_size(size=(col_width, None))
        window[col_key].expand(expand_x=True)

        # Expand cells to match header widths
        try:
            element_key = edit_keys[display_column]  # editable column
        except KeyError:
            element_key = '-{COL}_VALUE-'.format(COL=display_column.upper())  # read-only column

        window[element_key].expand(expand_x=True)

    window = align_window(window)

    # Set window focus on first editable input element and highlight any existing text
    if focus_element:
        print('setting focus to {}'.format(focus_element))
        window[focus_element].set_focus()
        window[focus_element].update(select=True)

    # Start event loop
    while True:
        event, values = window.read()

        if event in (sg.WIN_CLOSED, '-CANCEL-'):  # selected close-window or Cancel
            row = None

            break

        if event == '-SAVE-':  # click 'Save' button
            ready_to_save = []
            for column in edit_keys:
                col_key = edit_keys[column]
                input_val = values[col_key]

                # Get data type of column
                try:
                    dtype = dtype_map[column]
                except KeyError:
                    logger.warning('unable to obtain the data type of column "{COL}" from the dictionary of editable '
                                   'columns ... obtaining data type from row data types'.format(COL=column))
                    dtype = row[column].dtype

                # Set field value based on data type
                msg = 'the value "{VAL}" provided to column "{COL}" is the wrong type'
                if is_float_dtype(dtype):
                    try:
                        field_val = float(input_val)
                    except ValueError:
                        logger.warning(msg.format(VAL=input_val, COL=header_map[column]))
                        popup_notice(msg.format(VAL=input_val, COL=header_map[column]))
                        ready_to_save.append(False)
                        break
                elif is_integer_dtype(dtype):
                    try:
                        field_val = int(input_val)
                    except ValueError:
                        logger.warning(msg.format(VAL=input_val, COL=header_map[column]))
                        popup_notice(msg.format(VAL=input_val, COL=header_map[column]))
                        ready_to_save.append(False)
                        break
                elif is_bool_dtype(dtype):
                    try:
                        field_val = bool(input_val)
                    except ValueError:
                        logger.warning(msg.format(VAL=input_val, COL=header_map[column]))
                        popup_notice(msg.format(VAL=input_val, COL=header_map[column]))
                        ready_to_save.append(False)
                        break
                elif is_datetime_dtype(dtype):
                    try:
                        field_val = pd.to_datetime(input_val, format=settings.format_date_str(), errors='coerce')
                    except (ValueError, KeyError):
                        logger.warning(msg.format(VAL=input_val, COL=header_map[column]))
                        popup_notice(msg.format(VAL=input_val, COL=header_map[column]))
                        ready_to_save.append(False)
                        break
                else:
                    field_val = input_val

                # Replace field value with modified value
                try:
                    row[column] = field_val
                except ValueError as e:
                    msg = 'the value "{VAL}" provided to column "{COL}" is of the wrong type - {ERR}' \
                        .format(VAL=field_val, COL=header_map[column], ERR=e)
                    popup_notice(msg)
                    logger.error(msg)
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


def align_window(window, location: tuple = None):
    """
    Center a secondary window on the screen.

    Arguments:
        window: GUI window.

        location (tuple): place upper left corner of the window at the given coordinates [Default: center the window].
    """
    screen_w, screen_h = window.get_screen_dimensions()

    logger.debug('centering window')
    window.refresh()

    win_w, win_h = window.size
    logger.debug('current window size: ({W}, {H})'.format(W=win_w, H=win_h))

    if not isinstance(location, tuple):  # center window by default
        win_x = int(screen_w / 2 - win_w / 2)
        win_y = int(screen_h / 2 - win_h / 2)
    else:
        win_x, win_y = location

    logger.debug('window current location: ({}, {})'.format(*window.current_location()))
    logger.debug('window new location: ({}, {})'.format(win_x, win_y))
    if win_x + win_w > screen_w:
        win_x = screen_w - win_w
    if win_y + win_h > screen_h:
        win_y = screen_h - win_h

    window.refresh()
    window.move(win_x, win_y)
    window.refresh()
    logger.debug('window real location: {}'.format(window.current_location()))

    return window


def highlight_bool(s, column: str = 'Success'):
    """
    Annotate a pandas dataframe
    """
    ncol = len(s)
    if s[column] is True or s[column] == 1:
        return ['background-color: {}'.format(mod_const.PASS_COLOR)] * ncol
    else:
        return ['background-color: {}'.format(mod_const.FAIL_COLOR)] * ncol


def scroll_list_up(element):
    """
    Use the Up navigation arrow to scroll through the options of a listbox.
    """
    current_inds = element.get_indexes()
    print(current_inds)
    try:
        next_ind = current_inds[0] - 1
    except IndexError:
        print('cant find index for next item after ({})'.format(current_inds))
    else:
        print('next indices is {}'.format(next_ind))
        if next_ind >= 0:
            element.update(set_to_index=next_ind, scroll_to_index=next_ind)


def scroll_list_down(element):
    """
    Use the Down navigation arrow to scroll through the options of a listbox.
    """
    current_inds = element.get_indexes()
    print(current_inds)
    try:
        next_ind = current_inds[-1] + 1
    except IndexError:
        print('cant find index for next item after ({})'.format(current_inds))
    else:
        print('next indices is {}'.format(next_ind))
        all_values = element.get_list_values()
        if next_ind < len(all_values):
            element.update(set_to_index=next_ind, scroll_to_index=next_ind)
