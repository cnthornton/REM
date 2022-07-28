"""
REM parameter element classes.
"""
import datetime
from random import randint
import re

import numpy as np
import PySimpleGUI as sg
import pandas as pd

import REM.constants as mod_const
import REM.layouts as mod_lo
import REM.secondary as mod_win2
from REM.client import logger, settings


class InputParameter:
    """
    Data input parameter element.

    Attributes:

        name (str): data element configuration name.

        id (int): data element number.

        elements (list): list of data element GUI keys.

        description (str): display name of the data element.

        etype (str): GUI element type. Can be dropdown, input, date, range, conditional, multiple, or checkbox.

        dtype (str): data type of the parameter's data storage elements [Default: string].

        editable (bool): element is editable. [Default: False]

        hidden (bool): element is not visible to the user. [Default: False]

        required (bool): parameter value is required for an event.

        placeholder (str): text to use in the display value field when the parameter does not have a value set.
    """

    def __init__(self, name, entry):
        """
        GUI data storage element.

        Arguments:
            name (str): name of the configured element.

            entry (dict): configuration entry for the data storage element.
        """
        self.name = name
        self.id = randint(0, 1000000000)
        self.elements = {i: '-{NAME}_{ID}_{ELEM}-'.format(NAME=self.name, ID=self.id, ELEM=i) for i in
                         ('Element', 'Description', 'Border', 'Container', 'Frame')}

        self.bindings = {self.key_lookup(i): i for i in ('Element',)}

        elem_key = self.key_lookup('Element')
        for focus_event in ('In', 'Out'):
            event_key = '{ELEM}+{KEY}+'.format(ELEM=elem_key, KEY=focus_event.upper())
            self.bindings[event_key] = focus_event

        try:
            self.description = entry['Description']
        except KeyError:
            self.description = None

        try:
            self.etype = entry['ElementType']
        except KeyError:
            msg = 'Configuration Error: missing required parameter "ElementType"'
            logger.error('InputParameter {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            raise AttributeError(msg)

        try:
            dtype = entry['DataType']
        except KeyError:
            self.dtype = 'varchar'
        else:
            supported_dtypes = settings.get_supported_dtypes()
            if dtype not in supported_dtypes:
                logger.warning('InputParameter {NAME}: "DataType" is not a supported data type - supported data types '
                               'are {TYPES}'.format(NAME=name, TYPES=', '.join(supported_dtypes)))
                self.dtype = None
            else:
                self.dtype = dtype

        try:
            editable = bool(int(entry['IsEditable']))
        except KeyError:
            self.editable = True
        except ValueError:
            msg = 'Configuration Error: "IsEditable" must be either 0 (False) or 1 (True)'
            logger.error('InputParameter {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            raise AttributeError(msg)
        else:
            self.editable = editable

        try:
            hidden = bool(int(entry['IsHidden']))
        except KeyError:
            self.hidden = False
        except ValueError:
            msg = 'Configuration Error: "IsHidden" must be either 0 (False) or 1 (True)'
            logger.error('InputParameter {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            raise AttributeError(msg)
        else:
            self.hidden = hidden

        try:
            required = bool(int(entry['IsRequired']))
        except KeyError:
            self.required = False
        except ValueError:
            msg = 'Configuration Error: "IsRequired" must be either 0 (False) or 1 (True)'
            logger.error('InputParameter {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            raise AttributeError(msg)
        else:
            self.required = required

        # Layout attributes
        try:
            self.justification = entry['Justification']
        except KeyError:
            self.justification = 'right'

        try:
            self.bg_col = entry['BackgroundColor']
        except KeyError:
            self.bg_col = mod_const.DEFAULT_BG_COLOR

        try:
            self.placeholder = entry['PlaceholderText']
        except KeyError:
            self.placeholder = None

        try:
            self.default = entry['DefaultValue']
        except KeyError:
            self.default = None

        self.value = None

        self.disabled = not self.editable
        self.dimensions = None

    def _field_size(self, window):
        """
        Calculate the optimal default size of the parameter input field in pixels.
        """
        size = mod_const.FIELD_SIZE

        return size

    def _label_size(self, window):
        """
        Calculate the optimal default size of the parameter label in pixels.
        """
        label_font = mod_const.BOLD_MID_FONT
        description = self.description
        desc_key = self.key_lookup('Description')

        label = '*{}'.format(description) if (self.required and self.editable) else description
        label_w = window[desc_key].string_width_in_pixels(label_font, label)
        label_h = window[desc_key].char_height_in_pixels(label_font)

        return (label_w, label_h)

    def _set_state(self, window, state: str = 'inactive'):
        """
        Change the border of the input field to match its current state: focus, inactive, or error.

        """
        if state == 'focus':
            color = mod_const.SELECTED_COLOR
        elif state == 'error':
            color = mod_const.ERROR_COLOR
        else:
            color = mod_const.BORDER_COLOR

        container_key = self.key_lookup('Container')
        window[container_key].ParentRowFrame.config(background=color)

        border_key = self.key_lookup('Border')
        element = window[border_key]
        element.Widget.config(background=color)
        element.Widget.config(highlightbackground=color)
        element.Widget.config(highlightcolor=color)

    def _format_value(self, value):
        """
        Format the provided value according to the parameter's data type.

        Arguments:
            value (str): value to be formatted.

        Returns:
            new_value: value formatted according to the parameter's data type.
        """
        dtype = self.dtype

        if value == '' or pd.isna(value):
            return None

        new_value = settings.format_value(value, dtype)

        return new_value

    def key_lookup(self, component, rev: bool = False):
        """
        Lookup a parameter element's component GUI key using the name of the component element.

        Arguments:
            component (str): GUI component name (or key if rev is True) of the parameter element.

            rev (bool): reverse the element lookup map so that element keys are dictionary keys.
        """
        key_map = self.elements if rev is False else {j: i for i, j in self.elements.items()}
        try:
            key = key_map[component]
        except KeyError:
            msg = 'InputParameter {NAME}: parameter element {COMP} not found in list of parameter elements' \
                .format(COMP=component, NAME=self.name)
            logger.warning(msg)
            logger.exception(msg)
            key = None

        return key

    def bind_keys(self, window):
        """
        Set hotkey bindings.
        """
        if self.editable and not self.hidden:
            elem_key = self.key_lookup('Element')
            window[elem_key].bind('<FocusIn>', '+IN+')
            window[elem_key].bind('<FocusOut>', '+OUT+')

    def set_focus(self, window):
        """
        Set the window focus on the parameter field.
        """
        elem_key = self.key_lookup('Element')
        window[elem_key].set_focus()
        self._set_state(window, state='focus')

    def reset(self, window):
        """
        Reset the parameter's values.
        """
        default_value = self.default
        try:
            self.value = self._format_value(default_value)
        except Exception:
            self.value = None

        # Update the parameter window element
        self.update_display(window)

    def layout(self, size: tuple = None, padding: tuple = (0, 0), bg_color: str = None, justification: str = None,
               hidden: bool = None):
        """
        Create a GUI layout for the parameter.
        """
        # Layout settings
        if bg_color:  # set custom background different from configuration or default
            self.bg_col = bg_color
        else:
            bg_color = self.bg_col

        if justification:  # set custom justification of the description label different from configured
            self.justification = justification
        else:  # use configured justification
            justification = self.justification

        is_required = self.required
        visible = not hidden if hidden is not None else not self.hidden

        # Parameter settings
        desc = self.description if self.description else ''
        label_vis = True if self.description else False

        # Layout size
        default_w = mod_const.PARAM_SIZE[0]
        default_h = mod_const.PARAM_SIZE[1] if label_vis else mod_const.PARAM_SIZE2[1]
        if isinstance(size, tuple) and len(size) == 2:  # set to fixed size
            width, height = size
            width = width if (isinstance(width, int) and width >= default_w) else default_w
            height = height if (isinstance(height, int) and height >= default_h) else default_h
        else:  # let parameter type determine the size
            width = default_w
            height = default_h

        # Parameter label
        label_font = mod_const.BOLD_MID_FONT
        label_color = mod_const.LABEL_TEXT_COLOR

        if is_required is True and self.editable:
            required_layout = [sg.Text('*', visible=label_vis, font=label_font, background_color=bg_color,
                                       text_color=mod_const.ERROR_COLOR, tooltip='required',)]
        else:
            required_layout = []

        desc_key = self.key_lookup('Description')
        desc_layout = [sg.Text(desc, key=desc_key, visible=label_vis, font=label_font, text_color=label_color,
                               background_color=bg_color, tooltip=self.description)]

        label_layout = required_layout + desc_layout

        # Parameter value container
        border_key = self.key_lookup('Border')
        param_layout = [sg.Frame('', [[self.element_layout()]],
                                 key=border_key, background_color=mod_const.BORDER_COLOR, border_width=0,
                                 vertical_alignment='c', relief='flat', tooltip=self.placeholder)]

        # Layout
        elem_layout = [label_layout, param_layout]

        frame_key = self.key_lookup('Frame')
        layout = [sg.Frame('', elem_layout, key=frame_key, size=(width, height), pad=padding, visible=visible,
                           border_width=0, background_color=bg_color, relief=None, vertical_alignment='c',
                           tooltip=self.description)]

        self.dimensions = (width, height)

        return layout

    def element_layout(self):
        """
        Create the type-specific layout for the value element of the parameter.
        """
        disabled = False if self.editable is True else True

        # Element settings
        font = mod_const.LARGE_FONT
        bg_col = mod_const.DEFAULT_BG_COLOR
        disabled_text_col = mod_const.DISABLED_TEXT_COLOR
        disabled_bg_col = mod_const.DISABLED_BG_COLOR

        # Parameter size
        size = mod_const.FIELD_SIZE
        border = (1, 1)

        # Parameter settings
        display_value = self.format_display()
        if display_value == '':
            default_display = self.placeholder
            text_col = mod_const.DISABLED_TEXT_COLOR
        else:
            text_col = mod_const.DEFAULT_TEXT_COLOR
            default_display = display_value

        # Layout
        elem_key = self.key_lookup('Element')
        frame_key = self.key_lookup('Container')
        layout = sg.Frame('', [[sg.Input(default_display, key=elem_key, disabled=disabled, enable_events=True,
                                         border_width=0, font=font, background_color=bg_col, text_color=text_col,
                                         disabled_readonly_text_color=disabled_text_col,
                                         disabled_readonly_background_color=disabled_bg_col, expand_x=True)]],
                          key=frame_key, size=size, pad=border, background_color=bg_col, vertical_alignment='c')

        return layout

    def resize(self, window, size: tuple = None):
        """
        Resize the parameter elements.
        """
        default_w, default_h = mod_const.FIELD_SIZE
        current_w, current_h = self.dimensions

        if isinstance(size, tuple) and len(size) == 2:  # set to exact dimensions given
            width, height = size
            width = width if isinstance(width, int) else current_w
            height = height if isinstance(height, int) else current_h
        else:  # adjust dimensions based on parameter content
            # Find label size in pixels
            label_w, label_h = self._label_size(window)

            # Find optimal field size in pixels based on the parameter type
            field_w, field_h = self._field_size(window)

            # Determine which parameter component to base the width on
            width = label_w if label_w >= field_w else field_w
            height = current_h

        frame_key = self.key_lookup('Frame')
        mod_lo.set_size(window, frame_key, (width, height))

        container_w = width if (isinstance(width, int) and width >= default_w) else default_w
        container_key = self.key_lookup('Container')
        mod_lo.set_size(window, container_key, (container_w, default_h))

        elem_key = self.key_lookup('Element')
        window[elem_key].expand(expand_x=True, expand_y=True)

        dimensions = (width, height)
        self.dimensions = dimensions

        return dimensions

    def format_value(self, values):
        """
        Set the value of the data element from user input.

        Arguments:
            values: GUI element values or a single input value.
        """
        current_value = self.value

        if isinstance(values, dict):  # dictionary of GUI element values
            elem_key = self.key_lookup('Element')
            try:
                input_value = values[elem_key]
            except KeyError:
                logger.warning('InputParameter {NAME}: unable to find window values for parameter to update'
                               .format(NAME=self.name))

                return current_value
        else:
            input_value = values

        try:
            value_fmt = self._format_value(input_value)
        except Exception as e:
            msg = "failed to set the parameter's value = {ERR}".format(ERR=e)
            logger.exception('InputParameter {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            value_fmt = current_value
        else:
            self.value = value_fmt

        return value_fmt

    def format_display(self):
        """
        Format the parameter's value for displaying.
        """
        value = self.value

        if not self.has_value():
            return ''

        display_value = self.format_display_value(value)

        logger.debug('InputParameter {NAME}: formatting parameter value {VAL} for display as {DISPLAY}'
                     .format(NAME=self.name, VAL=value, DISPLAY=display_value))

        return display_value

    def format_display_value(self, value):
        """
        Format a value for display.
        """
        dec_sep = settings.decimal_sep
        group_sep = settings.thousands_sep

        dtype = self.dtype

        if pd.isna(value):
            return ''

        if dtype in settings.supported_float_dtypes and dtype == 'money':
            value = str(value)
            if value[0] in ('-', '+'):  # sign of the number
                numeric_sign = value[0]
                value = value[1:]
            else:
                numeric_sign = ''
            if dec_sep in value:
                integers, decimals = value.split(dec_sep)
                decimals = decimals[0:2]
                display_value = '{SIGN}{VAL}{SEP}{DEC}' \
                    .format(SIGN=numeric_sign, VAL=''.join([group_sep * (n % 3 == 2) + i for n, i in
                                                            enumerate(integers[::-1])][::-1]).lstrip(','),
                            SEP=dec_sep, DEC=decimals)
            else:
                display_value = '{SIGN}{VAL}' \
                    .format(SIGN=numeric_sign, VAL=''.join([group_sep * (n % 3 == 2) + i for n, i in
                                                            enumerate(value[::-1])][::-1]).lstrip(','))

        elif dtype in settings.supported_float_dtypes and dtype != 'money':
            try:
                new_value = float(value)
            except ValueError:
                logger.warning(
                    'InputParameter {NAME}: unsupported value of type {TYPE} provided to parameter with data '
                    'type {DTYPE}'.format(NAME=self.name, TYPE=type(value), DTYPE=dtype))
                display_value = ''
            else:
                display_value = str(new_value)

        elif dtype in settings.supported_int_dtypes:
            try:
                new_value = int(value)
            except ValueError:
                logger.warning(
                    'InputParameter {NAME}: unsupported value of type {TYPE} provided to parameter with data '
                    'type {DTYPE}'.format(NAME=self.name, TYPE=type(value), DTYPE=dtype))
                display_value = ''
            else:
                display_value = str(new_value)

        elif dtype in settings.supported_date_dtypes:
            try:
                display_value = settings.format_display_date(value)
            except ValueError:
                logger.warning(
                    'InputParameter {NAME}: unsupported value of type {TYPE} provided to parameter with data '
                    'type {DTYPE}'.format(NAME=self.name, TYPE=type(value), DTYPE=dtype))
                display_value = ''

        elif dtype in settings.supported_bool_dtypes:
            try:
                display_value = int(value)
            except ValueError:
                logger.warning(
                    'InputParameter {NAME}: unsupported value of type {TYPE} provided to parameter with data '
                    'type {DTYPE}'.format(NAME=self.name, TYPE=type(value), DTYPE=dtype))
                display_value = ''

        else:
            display_value = str(value)

        return display_value

    def update_display(self, window):
        """
        Update the parameter display.
        """
        elem_key = self.key_lookup('Element')

        # Update element text
        display_value = self.format_display()
        display_text = self.placeholder if (display_value == '' and self.placeholder) else display_value
        window[elem_key].update(value=display_text)

    def toggle(self, window, off: bool = False):
        """
        Toggle the parameter element on or off.
        """
        elements = self.elements
        bindings = self.bindings

        if self.editable:
            self.disabled = off

            for element in elements:
                element_key = elements[element]
                if element_key in bindings:
                    window[element_key].update(disabled=off)

    def has_value(self):
        """
        Return True if element has a valid value else False
        """
        value = self.value
        if pd.isna(value) or value == '':
            has_value = False
        else:
            has_value = True

        return has_value


# Single value data parameters
class InputParameterStandard(InputParameter):
    """
    Parent class for standard text-style input fields.

    Attributes:

        name (str): data element configuration name.

        elements (list): list of data element GUI keys.

        value: value of the parameter's data storage elements.
    """

    def __init__(self, name, entry):
        super().__init__(name, entry)

        if self.default is not None:
            raw_default = str(self.default)  # raw default value
            self._default = raw_default
            self._value = raw_default
        else:
            self._default = ''
            self._value = ''

    def reset(self, window):
        """
        Reset the parameter's values.
        """
        default_value = self.default
        try:
            self.value = self._format_value(default_value)
        except Exception:
            self.value = None

        self._enforce_formatting(self._default)

        # Update the parameter window element
        self.update_display(window)

    def run_event(self, window, event, values):
        """
        Run a window event associated with the parameter.
        """
        try:
            param_event = self.bindings[event]
        except KeyError:
            param_event = None

        update_event = False

        elem_key = self.key_lookup('Element')
        if param_event == 'In' and not self.disabled:
            self._set_state(window, state='focus')

            if self._value == '':
                window[elem_key].update(value='')
        elif param_event == 'Out' and not self.disabled:
            self._set_state(window, state='inactive')

            if self._value == '':
                window[elem_key].update(value=self.placeholder, text_color=mod_const.DISABLED_TEXT_COLOR)
        elif param_event == 'Element':
            input_value = values[elem_key]
            display_value = self._enforce_formatting(input_value)
            window[elem_key].update(value=display_value, text_color=mod_const.DEFAULT_TEXT_COLOR)

            update_event = True

        return update_event


class InputParameterText(InputParameterStandard):
    """
    For standard text input with no accessory elements.

    Attributes:

        name (str): data element configuration name.

        elements (list): list of data element GUI keys.

        pattern_matching (bool): query parameter using pattern matching [Default: False]

        value: value of the parameter's data storage elements.
    """

    def __init__(self, name, entry):
        super().__init__(name, entry)
        # Enforce supported data types for the input parameter
        supported_dtypes = settings.supported_str_dtypes + settings.supported_cat_dtypes + \
                           settings.supported_int_dtypes + settings.supported_float_dtypes
        if not self.dtype or self.dtype not in supported_dtypes:
            msg = 'unsupported data type {DTYPE} provided for the "{ETYPE}" parameter. Supported data types are ' \
                  '{DTYPES}'.format(ETYPE=self.etype, DTYPE=self.dtype, DTYPES=', '.join(supported_dtypes))
            logger.warning('InputParameter {PARAM}: configuration warning - {MSG}'.format(PARAM=name, MSG=msg))

            self.dtype = 'varchar'

        # Parameter-type specific attributes
        try:  # optional pattern matching flag for string and character data types
            pattern = bool(int(entry['PatternMatching']))
        except KeyError:
            self.pattern_matching = False
        except ValueError:
            msg = 'InputParameter {NAME}: configuration error - "PatternMatching" must be either 0 (False) or 1 (True)' \
                .format(NAME=self.name)
            logger.error(msg)

            raise AttributeError(msg)
        else:
            supported_dtypes = settings.supported_str_dtypes + settings.supported_cat_dtypes
            if self.dtype in supported_dtypes:
                self.pattern_matching = pattern
            else:  # only allow pattern matching for string-like data types
                logger.warning('InputParameter {NAME}: configuration warning - pattern matching is only allowed when '
                               'dtype is set to a supported string or category type'.format(NAME=self.name))
                self.pattern_matching = False

        try:
            self.value = self._format_value(self.default)
        except Exception as e:
            msg = "failed to set the parameter's default value - {ERR}".format(ERR=e)
            logger.exception('InputParameter {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            self.value = None
            self.default = None

        logger.debug('InputParameter {NAME}: initializing {ETYPE} parameter of data type {DTYPE} with default value '
                     '{DEF}, and formatted value {VAL}'
                     .format(NAME=self.name, ETYPE=self.etype, DTYPE=self.dtype, DEF=self.default, VAL=self.value))

    def _enforce_formatting(self, value):
        """
        Enforce the correct formatting of user input into the parameter element.
        """
        dec_sep = settings.decimal_sep
        group_sep = settings.thousands_sep

        dtype = self.dtype

        logger.debug('InputParameter {PARAM}: enforcing correct formatting of input value {VAL}'
                     .format(PARAM=self.name, VAL=value))

        if pd.isna(value):
            value = ''

        raw_value = self._value

        if dtype == 'money':
            current_value = list(raw_value)
            current_len = len(current_value)

            # Remove currency and grouping separator
            new_value = list(value.replace(group_sep, ''))
            new_len = len(new_value)

            if current_len > new_len:  # user removed one or more characters
                try:
                    last_char = new_value[-1]
                except IndexError:  # user deleted all input
                    current_value = new_value
                else:
                    # Remove the decimal separator if last character is decimal
                    if last_char == dec_sep:
                        current_value = new_value[0:-1]
                    else:
                        current_value = new_value
            elif current_len < new_len:  # user added a new character
                # Find the character and location of the user input
                new_char = new_value[-1]  # defaults to the last character
                new_index = len(new_value)  # defaults to the end of the string
                for index, old_char in enumerate(current_value):
                    character = new_value[index]
                    if old_char != character:
                        new_char = character
                        new_index = index
                        break

                # Validate added character
                if new_char.isnumeric():  # can add integers
                    current_value.insert(new_index, new_char)
                elif new_char == dec_sep:  # and also decimal character
                    if dec_sep not in current_value:  # can only add one decimal character
                        current_value.insert(new_index, new_char)
                elif new_char in ('+', '-') and new_index == 0:  # can add value sign at beginning
                    current_value.insert(new_index, new_char)
            else:  # user replaced a character, so lengths of old and new values are equal
                # Find the character and location of the user input
                new_char = None
                new_index = None
                for new_index, new_char in enumerate(new_value):  # defaults to the last character
                    old_char = current_value[new_index]
                    if old_char != new_char:
                        break

                # Validate added character
                if new_char and new_char.isnumeric():  # can add integers
                    current_value[new_index] = new_char
                elif new_char == dec_sep and dec_sep not in current_value:  # or one decimal character
                    current_value[new_index] = new_char
                elif new_char in ('+', '-') and new_index == 0:  # can add value sign at beginning
                    current_value.insert(new_index, new_char)

            current_value = ''.join(current_value)
            try:
                first_char = current_value[0]
            except IndexError:
                numeric_sign = ''
            else:
                if first_char in ('-', '+'):  # sign of the number
                    numeric_sign = first_char
                    current_value = current_value[1:]
                else:
                    numeric_sign = ''

            if dec_sep in current_value:
                integers, decimals = current_value.split(dec_sep)
                decimals = decimals[0:2]
                new_value = numeric_sign + integers + dec_sep + decimals[0:2]
                display_value = '{SIGN}{VAL}{SEP}{DEC}' \
                    .format(SIGN=numeric_sign, VAL=''.join([group_sep * (n % 3 == 2) + i for n, i in
                                                            enumerate(integers[::-1])][::-1]).lstrip(','),
                            SEP=dec_sep, DEC=decimals)
            else:
                display_value = '{SIGN}{VAL}' \
                    .format(SIGN=numeric_sign, VAL=''.join([group_sep * (n % 3 == 2) + i for n, i in
                                                            enumerate(current_value[::-1])][::-1]).lstrip(','))
                new_value = numeric_sign + current_value

        elif dtype in settings.supported_float_dtypes:  # all other float types besides money
            try:
                float(value)
            except ValueError:  # attempted to add an unsupported character
                display_value = raw_value
            else:
                display_value = value

            new_value = display_value

        elif dtype in settings.supported_int_dtypes:  # all integer data types
            try:
                new_value = int(value)
            except ValueError:  # attempted to add an unsupported character
                display_value = raw_value
            else:
                display_value = str(new_value)

            new_value = display_value

        else:  # string or character data types
            display_value = value
            new_value = display_value

        self._value = new_value

        return display_value

    def element_layout(self):
        """
        Create the type-specific layout for the value element of the parameter.
        """
        disabled = False if self.editable is True else True

        # Element settings
        font = mod_const.LARGE_FONT
        bg_col = mod_const.DEFAULT_BG_COLOR
        disabled_text_col = mod_const.DISABLED_TEXT_COLOR
        disabled_bg_col = mod_const.DISABLED_BG_COLOR

        # Parameter size
        size = mod_const.FIELD_SIZE
        border = (1, 1)

        # Parameter settings
        display_value = self._enforce_formatting(self._default)
        if display_value == '':
            display_value = self.placeholder
            text_col = mod_const.DISABLED_TEXT_COLOR
        else:
            text_col = mod_const.DEFAULT_TEXT_COLOR

        # Layout
        elem_key = self.key_lookup('Element')
        frame_key = self.key_lookup('Container')
        layout = sg.Frame('', [[sg.Input(display_value, key=elem_key, disabled=disabled, enable_events=True,
                                         border_width=0, font=font, background_color=bg_col, text_color=text_col,
                                         disabled_readonly_text_color=disabled_text_col,
                                         disabled_readonly_background_color=disabled_bg_col, expand_x=True)]],
                          key=frame_key, size=size, pad=border, background_color=bg_col, vertical_alignment='c')

        return layout

    def query_statement(self, column):
        """
        Generate the filter clause for SQL querying.
        """
        if self.has_value():
            match_pattern = self.pattern_matching
            query_value = self.value

            if match_pattern is True:
                query_value = '%{VAL}%'.format(VAL=query_value)
                statement = ('{COL} LIKE ?'.format(COL=column), (query_value,))
            else:
                statement = ('{COL} = ?'.format(COL=column), (query_value,))
        else:
            statement = None

        return statement

    def filter_table(self, df):
        """
        Use the parameter value to filter a dataframe.
        """
        if not self.has_value():  # don't filter when value not set
            return df

        if df.empty:
            return df

        param_value = self.value
        match_pattern = self.pattern_matching
        dtype = self.dtype
        column = self.name

        try:
            if dtype in settings.supported_int_dtypes:
                col_values = pd.to_numeric(df[column].fillna(0), errors='coerce', downcast='integer')
            elif dtype in settings.supported_float_dtypes:
                col_values = pd.to_numeric(df[column], errors='coerce')
            else:
                col_values = df[column].astype(np.object_, errors='raise')
        except Exception as e:
            logger.exception('InputParameter {NAME}: unable to set column {COL} to parameter data type {DTYPE} - {ERR}'
                             .format(NAME=self.name, COL=column, DTYPE=dtype, ERR=e))
            col_values = df[column]

        logger.debug('InputParameter {NAME}: filtering table on value {VAL}'.format(NAME=self.name, VAL=param_value))

        if match_pattern is True:
            df = df[col_values.str.contains(param_value, case=False, regex=True)]
        else:
            df = df[col_values == param_value]

        return df


class InputParameterDate(InputParameterStandard):
    """
    For date input.

    Attributes:

        name (str): data element configuration name.

        elements (list): list of data element GUI keys.

        value: value of the parameter's data storage elements.
    """

    def __init__(self, name, entry):
        super().__init__(name, entry)

        # Additional bindings and events
        calendar_key = '-{NAME}_{ID}_{ELEM}-'.format(NAME=self.name, ID=self.id, ELEM='Calendar')
        self.elements['Calendar'] = calendar_key
        self.bindings[calendar_key] = 'Calendar'

        # Enforce supported data types for the parameter
        supported_dtypes = settings.supported_date_dtypes
        if not self.dtype or self.dtype not in supported_dtypes:
            msg = 'unsupported data type {DTYPE} provided for the "{ETYPE}" parameter. Supported data types are ' \
                  '{DTYPES}'.format(ETYPE=self.etype, DTYPE=self.dtype, DTYPES=', '.join(supported_dtypes))
            logger.warning('InputParameter {PARAM}: {MSG}'.format(PARAM=name, MSG=msg))

            self.dtype = 'datetime'

        # Parameter-type specific attributes
        try:
            self.localize = bool(int(entry['localize']))
        except (KeyError, ValueError):
            self.localize = False

        if not self.placeholder:
            self.placeholder = 'yyyy/mm/dd'

        try:
            self.value = self._format_value(self.default)
        except Exception as e:
            msg = "failed to set the parameter's default value - {ERR}".format(ERR=e)
            logger.exception('InputParameter {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            self.value = None
            self.default = None

        logger.debug('InputParameter {NAME}: initializing {ETYPE} parameter of data type {DTYPE} with default value '
                     '{DEF}, and formatted value {VAL}'
                     .format(NAME=self.name, ETYPE=self.etype, DTYPE=self.dtype, DEF=self.default, VAL=self.value))

    def _format_value(self, value):
        """
        Format the provided value according to the parameter's data type.

        Arguments:
            value (str): value to be formatted.

        Returns:
            new_value: value formatted according to the parameter's data type.
        """
        if value == '' or pd.isna(value):
            return None

        input_date_format = settings.input_date_format

        try:
            new_value = pd.to_datetime(value, format=input_date_format, utc=False).to_pydatetime()
        except ValueError:
            logger.warning('InputParameter {NAME}: failed to format input value {VAL} as a datetime object'
                           .format(NAME=self.name, VAL=value))

            new_value = None

        return new_value

    def _enforce_formatting(self, value):
        """
        Enforce the correct formatting of user input into the parameter element.
        """
        strptime = datetime.datetime.strptime

        logger.debug('InputParameter {PARAM}: enforcing correct formatting of input value {VAL}'
                     .format(PARAM=self.name, VAL=value))

        if pd.isna(value):
            value = ''

        # Remove separator from the input
        raw_value = list(self._value)
        new_value = list(value.replace('/', ''))

        input_len = len(new_value)
        if input_len == 8:
            try:
                new_date = strptime(''.join(new_value), '%Y%m%d')
            except ValueError:  # date is incorrectly formatted
                msg = '{} is not a valid date format'.format(''.join(new_value))
                mod_win2.popup_notice(msg)
                logger.warning('InputParameter {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                display_value = format_display_date(raw_value, sep='/')
            else:
                raw_value = new_value
                display_value = new_date.strftime(settings.input_date_format)
        elif input_len < 8:
            current_len = len(raw_value)
            if current_len > input_len:  # user deleted a character
                raw_value = new_value
            elif current_len < input_len:  # user added a character
                # Find the character and location of the user input
                new_char = new_value[-1]  # defaults to the last character
                new_index = len(new_value)  # defaults to the end of the string
                for index, old_char in enumerate(raw_value):
                    character = new_value[index]
                    if old_char != character:
                        new_char = character
                        new_index = index
                        break

                # Validate added character
                if new_char.isnumeric():  # can add integers
                    raw_value.insert(new_index, new_char)

            else:  # user replaced a character
                # Find the character and location of the user input
                new_char = None
                new_index = None
                for new_index, new_char in enumerate(new_value):  # defaults to the last character
                    old_char = raw_value[new_index]
                    if old_char != new_char:
                        break

                # Validate added character
                if new_char and new_char.isnumeric():  # can add integers
                    raw_value[new_index] = new_char

            display_value = format_display_date(raw_value, sep='/')
        else:
            display_value = format_display_date(raw_value, sep='/')

        self._value = ''.join(raw_value)

        return display_value

    def element_layout(self):
        """
        Create the type-specific layout for the value element of the parameter.
        """
        disabled = False if self.editable is True else True
        input_date_format = settings.input_date_format

        # Element settings
        font = mod_const.LARGE_FONT
        bg_col = mod_const.DEFAULT_BG_COLOR
        disabled_text_col = mod_const.DISABLED_TEXT_COLOR
        disabled_bg_col = mod_const.DISABLED_BG_COLOR
        pad_el = mod_const.ELEM_PAD * 2

        # Parameter settings
        default_value = self.default
        default_display = '' if pd.isna(default_value) else self.value.strftime(input_date_format)
        display_value = self._enforce_formatting(default_display)
        if display_value == '':
            display_value = self.placeholder
            text_col = mod_const.DISABLED_TEXT_COLOR
        else:
            text_col = mod_const.DEFAULT_TEXT_COLOR

        # Parameter size
        size = mod_const.FIELD_SIZE
        border = (1, 1)

        # Layout
        elem_key = self.key_lookup('Element')
        calendar_key = self.key_lookup('Calendar')
        frame_key = self.key_lookup('Container')
        date_ico = mod_const.CALENDAR_ICON
        layout = sg.Frame('', [[sg.CalendarButton('', target=elem_key, key=calendar_key, format=input_date_format,
                                                  image_data=date_ico, font=font, pad=(pad_el, 0),
                                                  button_color=(text_col, bg_col),
                                                  border_width=0, disabled=disabled),
                                sg.Input(display_value, key=elem_key, enable_events=True, disabled=disabled,
                                         border_width=0, font=font, background_color=bg_col, text_color=text_col,
                                         disabled_readonly_text_color=disabled_text_col,
                                         disabled_readonly_background_color=disabled_bg_col,
                                         use_readonly_for_disable=True, expand_x=True)]],
                          key=frame_key, size=size, pad=border, background_color=bg_col, vertical_alignment='c')

        return layout

    def format_display(self):
        """
        Format the parameter's value for displaying.
        """
        if not self.has_value():
            return ''

        display_value = self.value.strftime(settings.input_date_format)

        return display_value

    def query_statement(self, column):
        """
        Generate the filter clause for SQL querying.
        """
        if self.has_value():
            query_value = self.value
            statement = ('{COL} = ?'.format(COL=column), (query_value,))
        else:
            statement = None

        return statement

    def filter_table(self, df):
        """
        Use the parameter value to filter a dataframe.
        """
        if not self.has_value():
            return df

        if df.empty:
            return df

        dtype = self.dtype
        column = self.name

        try:
            col_values = pd.to_datetime(df[column], errors='coerce', format=settings.date_format)
        except Exception as e:
            logger.exception('InputParameter {NAME}: unable to set column {COL} to parameter data type {DTYPE} - {ERR}'
                             .format(NAME=self.name, COL=column, DTYPE=dtype, ERR=e))
            col_values = df[column]

        value = self.value
        param_value = value.date()

        logger.debug('InputParameter {NAME}: filtering table on values {VAL}'
                     .format(NAME=self.name, VAL=value.strftime(settings.date_format)))
        df = df[col_values.dt.date == param_value]

        return df

    def has_value(self):
        """
        Return True if element has a valid value else False
        """
        is_datetime_dtype = pd.api.types.is_datetime64_any_dtype

        value = self.value
        if is_datetime_dtype(value) or isinstance(value, datetime.datetime) or isinstance(value, datetime.date):
            has_value = True
        else:
            has_value = False

        return has_value


class InputParameterSearch(InputParameter):
    """
    For selection input.

    Attributes:
        value: value of the parameter's data storage elements.
    """

    def __init__(self, name, entry):
        super().__init__(name, entry)

        # Enforce supported data types for the parameter
        supported_dtypes = settings.supported_str_dtypes + settings.supported_cat_dtypes
        if not self.dtype or self.dtype not in supported_dtypes:
            msg = 'unsupported data type {DTYPE} provided for the "{ETYPE}" parameter. Supported data types are ' \
                  '{DTYPES}'.format(ETYPE=self.etype, DTYPE=self.dtype, DTYPES=', '.join(supported_dtypes))
            logger.warning('InputParameter {PARAM}: {MSG}'.format(PARAM=name, MSG=msg))

            self.dtype = 'varchar'

        # Additional bindings and events
        search_key = '-{NAME}_{ID}_{ELEM}-'.format(NAME=self.name, ID=self.id, ELEM='Search')
        self.elements['Search'] = search_key
        self.bindings[search_key] = 'Search'

        if not self.placeholder:
            self.placeholder = 'Search...'

        try:
            self.value = self._format_value(self.default)
        except Exception as e:
            msg = "failed to set the parameter's default value - {ERR}".format(ERR=e)
            logger.exception('InputParameter {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            self.value = None
            self.default = None

        logger.debug('InputParameter {NAME}: initializing {ETYPE} parameter of data type {DTYPE} with default value '
                     '{DEF}, and formatted value {VAL}'
                     .format(NAME=self.name, ETYPE=self.etype, DTYPE=self.dtype, DEF=self.default, VAL=self.value))

    def run_event(self, window, event, values):
        """
        Run a window event associated with the parameter.
        """
        try:
            param_event = self.bindings[event]
        except KeyError:
            param_event = None

        update_event = False
        if param_event == 'In' and not self.disabled:
            self._set_state(window, state='focus')
        elif param_event == 'Out' and not self.disabled:
            self._set_state(window, state='inactive')
        elif param_event == 'Element':
            update_event = True

        return update_event

    def element_layout(self):
        """
        Create the type-specific layout for the value element of the parameter.
        """
        disabled = False if self.editable is True else True

        # Element settings
        font = mod_const.LARGE_FONT
        bg_col = mod_const.DEFAULT_BG_COLOR
        disabled_text_col = mod_const.DISABLED_TEXT_COLOR
        disabled_bg_col = mod_const.DISABLED_BG_COLOR
        border_color = mod_const.BORDER_COLOR
        #pad_el = mod_const.ELEM_PAD * 2

        # Parameter settings
        display_value = self.format_display()
        if display_value == '':
            display_value = self.placeholder
            text_col = mod_const.DISABLED_TEXT_COLOR
        else:
            text_col = mod_const.DEFAULT_TEXT_COLOR

        # Parameter element size
        size = mod_const.FIELD_SIZE
        border = (1, 1)

        # Layout
        elem_key = self.key_lookup('Element')
        frame_key = self.key_lookup('Container')
        search_key = self.key_lookup('Search')
        search_icon = mod_const.SEARCH_ICON
        layout = sg.Frame('', [[sg.Input(display_value, key=elem_key, enable_events=True, disabled=disabled,
                                         border_width=0, font=font, background_color=bg_col,
                                         text_color=text_col, disabled_readonly_text_color=disabled_text_col,
                                         disabled_readonly_background_color=disabled_bg_col,
                                         use_readonly_for_disable=True, expand_x=True),
                                sg.Button('', key=search_key, image_data=search_icon, disabled=disabled,
                                          button_color=(text_col, border_color), border_width=0, expand_y=True)]],
                          key=frame_key, size=size, pad=border, background_color=bg_col, vertical_alignment='c')

        return layout

    def query_statement(self, column):
        """
        Generate the filter clause for SQL querying.
        """
        if self.has_value():
            query_value = '%{VAL}%'.format(VAL=self.value)
            statement = ('{COL} LIKE ?'.format(COL=column), (query_value,))
        else:
            statement = None

        return statement

    def filter_table(self, df):
        """
        Use the parameter value to filter a dataframe.
        """
        if not self.has_value():  # don't filter when value not set
            return df

        if df.empty:
            return df

        param_value = self.value
        dtype = self.dtype
        column = self.name

        try:
            if dtype in settings.supported_int_dtypes:
                col_values = pd.to_numeric(df[column].fillna(0), errors='coerce', downcast='integer')
            elif dtype in settings.supported_float_dtypes:
                col_values = pd.to_numeric(df[column], errors='coerce')
            else:
                col_values = df[column].astype(np.object_, errors='raise')
        except Exception as e:
            logger.exception('InputParameter {NAME}: unable to set column {COL} to parameter data type {DTYPE} - {ERR}'
                             .format(NAME=self.name, COL=column, DTYPE=dtype, ERR=e))
            col_values = df[column]

        logger.debug('InputParameter {NAME}: filtering table on value {VAL}'.format(NAME=self.name, VAL=param_value))

        df = df[col_values.str.contains(param_value, case=False, regex=True)]

        return df


class InputParameterCombo(InputParameter):
    """
    For selection input.

    Attributes:
        combo_values (list): list of possible values for the dropdown menu.

        value: value of the parameter's data storage elements.
    """

    def __init__(self, name, entry):
        super().__init__(name, entry)
        format_value = settings.format_value

        # Enforce supported data types for the dropdown parameter
        supported_dtypes = settings.supported_str_dtypes + settings.supported_int_dtypes + \
                           settings.supported_cat_dtypes + settings.supported_bool_dtypes
        if not self.dtype or self.dtype not in supported_dtypes:
            msg = 'unsupported data type {DTYPE} provided for the "{ETYPE}" parameter. Supported data types are ' \
                  '{DTYPES}'.format(ETYPE=self.etype, DTYPE=self.dtype, DTYPES=', '.join(supported_dtypes))
            logger.warning('InputParameter {PARAM}: {MSG}'.format(PARAM=name, MSG=msg))

            self.dtype = 'varchar'

        # Parameter-type specific attributes
        try:
            aliases = entry['Aliases']
        except KeyError:
            aliases = settings.fetch_alias_definition(self.name)

        self.aliases = {}  # only str and int types can have aliases - aliases dict reversed during value formatting
        for alias in aliases:  # alias should have same datatype as the element
            alias_value = aliases[alias]
            self.aliases[format_value(alias, self.dtype)] = alias_value

        try:
            combo_values = entry['Values']
        except KeyError:
            msg = 'missing required parameter "Values" for data parameters of type "{ETYPE}"'.format(ETYPE=self.etype)
            mod_win2.popup_notice('Configuration warning: {PARAM}: {MSG}'.format(PARAM=name, MSG=msg))
            logger.warning('InputParameter {PARAM}: {MSG}'.format(PARAM=name, MSG=msg))

            combo_values = []

        self.combo_values = []
        for combo_value in combo_values:
            try:
                value_fmt = settings.format_value(combo_value, self.dtype)
            except ValueError:
                msg = 'unable to format dropdown value "{VAL}" as {DTYPE}'.format(VAL=combo_value, DTYPE=self.dtype)
                mod_win2.popup_notice('Configuration warning: {PARAM}: {MSG}'.format(PARAM=name, MSG=msg))
                logger.warning('InputParameter {PARAM}: {MSG}'.format(PARAM=name, MSG=msg))
            else:
                self.combo_values.append(value_fmt)

                if value_fmt not in self.aliases:
                    self.aliases[value_fmt] = combo_value

        try:
            self.value = self._format_value(self.default)
        except Exception as e:
            msg = "failed to set the parameter's default value - {ERR}".format(ERR=e)
            logger.exception('InputParameter {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            self.value = None
            self.default = None

        logger.debug('InputParameter {NAME}: initializing {ETYPE} parameter of data type {DTYPE} with default value '
                     '{DEF}, and formatted value {VAL}'
                     .format(NAME=self.name, ETYPE=self.etype, DTYPE=self.dtype, DEF=self.default, VAL=self.value))

    def _format_value(self, value):
        """
        Format the provided value according to the parameter's data type.

        Arguments:
            value (str): value to be formatted.

        Returns:
            new_value: value formatted according to the parameter's data type.
        """
        if value == '' or pd.isna(value):
            return None

        dtype = self.dtype
        aliases = self.aliases

        aliases_rev = {j: i for i, j in aliases.items()}
        try:
            new_value = aliases_rev[value]
        except KeyError:
            new_value = settings.format_value(value, dtype)

        return new_value

    def _field_size(self, window):
        """
        Calculate the optimal default size of the parameter input field in pixels.
        """
        font = mod_const.LARGE_FONT
        scroll_w = mod_const.SCROLL_WIDTH

        aliases = self.aliases
        combo_values = self.combo_values
        desc_key = self.key_lookup('Description')

        max_len = max([window[desc_key].string_width_in_pixels(font, aliases.get(i, i)) for i in combo_values])
        size = (max_len + scroll_w, mod_const.FIELD_SIZE[1])

        return size

    def run_event(self, window, event, values):
        """
        Run a window event associated with the parameter.
        """
        try:
            param_event = self.bindings[event]
        except KeyError:
            param_event = None

        update_event = False
        if param_event == 'In' and not self.disabled:
            self._set_state(window, state='focus')
        elif param_event == 'Out' and not self.disabled:
            self._set_state(window, state='inactive')
        elif param_event == 'Element':
            update_event = True

        return update_event

    def format_display(self):
        """
        Format the parameter's value for displaying.
        """
        value = self.value
        aliases = self.aliases

        if not self.has_value():
            return ''

        try:
            display_value = aliases[value]
        except KeyError:
            display_value = self.format_display_value(value)

        logger.debug('InputParameter {NAME}: formatting parameter value {VAL} for display as {DISPLAY}'
                     .format(NAME=self.name, VAL=value, DISPLAY=display_value))

        return display_value

    def element_layout(self):
        """
        Create the type-specific layout for the value element of the parameter.
        """
        disabled = False if self.editable is True else True

        # Element settings
        font = mod_const.LARGE_FONT
        bg_col = mod_const.DEFAULT_BG_COLOR
        text_col = mod_const.DEFAULT_TEXT_COLOR

        # Parameter settings
        aliases = self.aliases
        combo_values = self.combo_values
        display_value = self.format_display()

        values = [aliases.get(i, i) for i in combo_values]
        if '' not in values:  # the no selection option
            values.insert(0, '')

        # Parameter element size
        size = mod_const.FIELD_SIZE
        border = (1, 1)

        # Layout
        elem_key = self.key_lookup('Element')
        frame_key = self.key_lookup('Container')
        layout = sg.Frame('', [[sg.Combo(values, default_value=display_value, key=elem_key, font=font,
                                         background_color=bg_col, text_color=text_col,
                                         button_arrow_color=mod_const.BORDER_COLOR,
                                         button_background_color=bg_col,
                                         enable_events=True, disabled=disabled)]],
                          key=frame_key, size=size, pad=border, background_color=bg_col, border_width=0,
                          vertical_alignment='c')

        return layout

    def query_statement(self, column):
        """
        Generate the filter clause for SQL querying.
        """
        dtype = self.dtype
        value = self.value

        if self.has_value():
            if dtype in settings.supported_bool_dtypes:
                try:
                    query_value = int(value)
                except TypeError:
                    query_value = None
            else:
                query_value = value

            statement = ('{COL} = ?'.format(COL=column), (query_value,))
        else:
            statement = None

        return statement

    def filter_table(self, df):
        """
        Use the parameter value to filter a dataframe.
        """
        if not self.has_value():  # don't filter when value not set
            return df

        if df.empty:
            return df

        param_value = self.value
        dtype = self.dtype
        column = self.name

        try:
            if dtype in settings.supported_int_dtypes:
                col_values = pd.to_numeric(df[column].fillna(0), errors='coerce', downcast='integer')
            elif dtype in settings.supported_float_dtypes:
                col_values = pd.to_numeric(df[column], errors='coerce')
            elif dtype in settings.supported_bool_dtypes:
                col_values = df[column].fillna(False).astype(np.bool_, errors='raise')
            else:
                col_values = df[column].astype(np.object_, errors='raise')
        except Exception as e:
            logger.exception('InputParameter {NAME}: unable to set column {COL} to parameter data type {DTYPE} - {ERR}'
                             .format(NAME=self.name, COL=column, DTYPE=dtype, ERR=e))
            col_values = df[column]

        logger.debug('InputParameter {NAME}: filtering table on value {VAL}'.format(NAME=self.name, VAL=param_value))

        df = df[col_values == param_value]

        return df


# Multiple component data parameters
class InputParameterComp(InputParameter):
    """
    Parent class for input fields with the element value split into two or more components.

    Attributes:
        name (str): data element configuration name.

        elements (list): list of data element GUI keys.

        value: value of the parameter's data storage elements.
    """

    def __init__(self, name, entry):
        super().__init__(name, entry)

        # Enforce supported data types for the dropdown parameter
        supported_dtypes = (settings.supported_int_dtypes + settings.supported_float_dtypes +
                            settings.supported_date_dtypes)
        if not self.dtype or self.dtype not in supported_dtypes:
            msg = 'unsupported data type {DTYPE} provided for the "{ETYPE}" parameter. Supported data types are ' \
                  '{DTYPES}'.format(ETYPE=self.etype, DTYPE=self.dtype, DTYPES=', '.join(supported_dtypes))
            logger.warning('InputParameter {PARAM}: {MSG}'.format(PARAM=name, MSG=msg))

            self.dtype = 'float'

        self._function = None

    def update_display(self, window):
        """
        Update the parameter display.
        """
        elem_key = self.key_lookup('Element')

        # Update element text
        display_value = self.format_display()
        window[elem_key].update(text=display_value)

    def element_layout(self):
        """
        Create the type-specific layout for the value element of the parameter.
        """
        disabled = False if self.editable is True else True

        # Element settings
        font = mod_const.SMALL_FONT
        bg_col = mod_const.DEFAULT_BG_COLOR
        text_col = mod_const.DEFAULT_TEXT_COLOR

        # Parameter settings
        display_value = self.format_display()

        # Parameter size
        size = mod_const.FIELD_SIZE
        border = (1, 1)

        elem_key = self.key_lookup('Element')
        frame_key = self.key_lookup('Container')
        layout = sg.Frame('', [[sg.Button(display_value, key=elem_key, disabled=disabled, border_width=1, font=font,
                                          button_color=(text_col, bg_col), tooltip=display_value)]],
                          key=frame_key, size=size, pad=border, border_width=0, background_color=bg_col,
                          vertical_alignment='c')

        return layout

    def run_event(self, window, event, values):
        """
        Run a window event associated with the parameter.
        """
        try:
            param_event = self.bindings[event]
        except KeyError:
            param_event = None

        update_event = False

        if param_event == 'In' and not self.disabled:
            self._set_state(window, state='focus')
        elif param_event == 'Out' and not self.disabled:
            self._set_state(window, state='inactive')
        elif param_event == 'Element' and not self.disabled:
            elem_key = self.key_lookup('Element')
            element = window[elem_key]

            size = window[self.key_lookup('Container')].get_size()
            location = (element.Widget.winfo_rootx(), element.Widget.winfo_rooty() + size[1])

            new_value = self._function(self.dtype, current=self.value, title=self.description, location=location,
                                       size=size)
            self.value = self._format_value(new_value)

            display_value = self.format_display()
            element.update(text=display_value)

            update_event = True

        return update_event


class InputParameterRange(InputParameterComp):
    """
    For ranged value inputs.

    Attributes:

        name (str): data element configuration name.

        elements (list): list of data element GUI keys.

        value: value of the parameter's data storage elements.
    """

    def __init__(self, name, entry):
        super().__init__(name, entry)
        self._function = mod_win2.range_value_window

        try:
            self.value = self._format_value(self.default)
        except Exception as e:
            msg = "failed to set the parameter's default value - {ERR}".format(ERR=e)
            logger.exception('InputParameter {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            self.value = None
            self.default = None

        logger.debug('InputParameter {NAME}: initializing {ETYPE} parameter of data type {DTYPE} with default value '
                     '{DEF}, and formatted value {VAL}'
                     .format(NAME=self.name, ETYPE=self.etype, DTYPE=self.dtype, DEF=self.default, VAL=self.value))

    def _format_value(self, value):
        """
        Format the provided value according to the parameter's data type.

        Arguments:
            value (str): value to be formatted.

        Returns:
            new_value: value formatted according to the parameter's data type.
        """
        format_value = settings.format_value
        dtype = self.dtype

        try:
            in1, in2 = value
        except (ValueError, TypeError):
            in1 = in2 = value

        try:
            in1_fmt = format_value(in1, dtype)
        except ValueError as e:
            msg = 'InputParameter {NAME}: unable set datatype for the first value - {ERR}'.format(NAME=self.name, ERR=e)
            logger.warning(msg)

            in1_fmt = None

        try:
            in2_fmt = format_value(in2, dtype)
        except ValueError as e:
            msg = 'InputParameter {NAME}: unable set datatype for the second value - {ERR}'.format(NAME=self.name,
                                                                                                   ERR=e)
            logger.warning(msg)

            in2_fmt = None

        new_value = (in1_fmt, in2_fmt)

        return new_value

    def format_display(self):
        """
        Format the parameter's value for displaying.
        """
        if not self.has_value():
            return ''

        values = self.value

        formatted_values = []
        for value in values:
            if pd.isna(value):
                continue

            formatted_values.append(self.format_display_value(value))

        return ' - '.join(formatted_values)

    def query_statement(self, column):
        """
        Generate the filter clause for SQL querying.
        """
        values = self.value

        if self.has_value():
            from_val, to_val = values

            if from_val and to_val:
                statement = ('{COL} BETWEEN ? AND ?'.format(COL=column), values)
            elif from_val and not to_val:
                statement = ('{COL} = ?'.format(COL=column), (from_val,))
            elif to_val and not from_val:
                statement = ('{COL} = ?'.format(COL=column), (to_val,))
            else:
                statement = None
        else:
            statement = None

        return statement

    def filter_table(self, df):
        """
        Use the parameter value to filter a dataframe.
        """
        param_values = self.value
        dtype = self.dtype
        column = self.name

        if not self.has_value():  # don't filter on NA values
            return df

        if df.empty:
            return df

        try:
            from_value, to_value = param_values
        except ValueError:
            logger.error('InputParameter {NAME}: ranged parameters require exactly two values'
                         .format(NAME=self.name))
            return df

        try:
            if dtype in settings.supported_date_dtypes:
                col_values = pd.to_datetime(df[column], errors='coerce', format=settings.date_format)
            elif dtype in settings.supported_int_dtypes:
                col_values = pd.to_numeric(df[column].fillna(0), errors='coerce', downcast='integer')
            elif dtype in settings.supported_float_dtypes:
                col_values = pd.to_numeric(df[column], errors='coerce')
            elif dtype in settings.supported_bool_dtypes:
                col_values = df[column].fillna(False).astype(np.bool_, errors='raise')
            else:
                col_values = df[column].astype(np.object_, errors='raise')
        except Exception as e:
            logger.exception('InputParameter {NAME}: unable to set column {COL} to parameter data type {DTYPE} - {ERR}'
                             .format(NAME=self.name, COL=column, DTYPE=dtype, ERR=e))
            col_values = df[column]

        if from_value not in (None, '') and to_value not in (None, ''):  # select rows in range
            logger.debug('InputParameter {NAME}: filtering table on values {VAL1} and {VAL2}'
                         .format(NAME=self.name, VAL1=from_value, VAL2=to_value))
            try:
                df = df[(col_values >= from_value) & (col_values <= to_value)]
            except KeyError:
                logger.warning('InputParameter {NAME}: parameter name not found in the table header'
                               .format(NAME=self.name))
            except SyntaxError:
                logger.warning('InputParameter {TBL}: unable to filter table on parameter values {VAL1} and {VAL2}'
                               .format(TBL=self.name, VAL1=from_value, VAL2=to_value))
        elif from_value not in (None, '') and to_value in (None, ''):  # rows equal to from component
            logger.debug('InputParameter {NAME}: filtering table on parameter value {VAL}'
                         .format(NAME=self.name, VAL=from_value))
            try:
                df = df[col_values == from_value]
            except KeyError:
                logger.warning('InputParameter {NAME}: parameter not found in the table header'.format(NAME=self.name))
            except SyntaxError:
                logger.warning('InputParameter {NAME}: unable to filter table on parameter value {VAL}'
                               .format(NAME=self.name, VAL=from_value))
        elif to_value not in (None, '') and from_value in (None, ''):  # rows equal to the to component
            logger.debug('InputParameter {NAME}: filtering table on parameter value {VAL}'
                         .format(NAME=self.name, VAL=to_value))
            try:
                df = df[col_values == to_value]
            except KeyError:
                logger.warning('InputParameter {NAME}: parameter not found in the table header'.format(NAME=self.name))
            except SyntaxError:
                logger.warning('InputParameter {NAME}: unable to filter table on parameter value {VAL}'
                               .format(NAME=self.name, VAL=to_value))

        return df

    def has_value(self):
        """
        Return True if element has a valid value else False
        """
        current_value = self.value

        if isinstance(current_value, tuple) and len(current_value) == 2:
            values_set = []
            for value in current_value:
                if not pd.isna(value) and not value == '':
                    values_set.append(True)
                else:
                    values_set.append(False)

            if any(values_set):
                has_value = True
            else:
                has_value = False
        else:
            has_value = False

        return has_value


class InputParameterCondition(InputParameterComp):
    """
    For conditional value inputs.

    Attributes:

        name (str): data element configuration name.

        elements (list): list of data element GUI keys.

        value: value of the parameter's data storage elements.
    """

    def __init__(self, name, entry):
        super().__init__(name, entry)
        self._operators = ['>', '<', '>=', '<=', '=']
        self._function = mod_win2.conditional_value_window

        try:
            self.value = self._format_value(self.default)
        except Exception as e:
            msg = "failed to set the parameter's default value - {ERR}".format(ERR=e)
            logger.exception('InputParameter {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            self.value = None
            self.default = None

        logger.debug('InputParameter {NAME}: initializing {ETYPE} parameter of data type {DTYPE} with default value '
                     '{DEF}, and formatted value {VAL}'
                     .format(NAME=self.name, ETYPE=self.etype, DTYPE=self.dtype, DEF=self.default, VAL=self.value))

    def _format_value(self, value):
        """
        Format the provided value according to the parameter's data type.

        Arguments:
            value (str): value to be formatted.

        Returns:
            new_value: value formatted according to the parameter's data type.
        """
        operators = self._operators
        dtype = self.dtype

        try:
            oper, value = value
        except ValueError:
            msg = 'input value should be a list or tuple of containing two components'
            logger.warning('InputParameter {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            raise ValueError(msg)

        if oper not in operators:
            msg = 'unknown operator "{OPER}" provided as the first component of the value set'.format(OPER=oper)
            logger.warning('InputParameter {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            return TypeError(msg)

        try:
            value_fmt = settings.format_value(value, dtype)
        except ValueError as e:
            msg = 'unable set datatype for the conditional value - {ERR}'.format(ERR=e)
            logger.warning('InputParameter {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            raise ValueError(msg)

        new_value = (oper, value_fmt)

        return new_value

    def format_display(self):
        """
        Format the parameter's value for displaying.
        """
        if not self.has_value():  # no parameter value + operator combo set
            return ''

        operator, value = self.value

        logger.debug('InputParameter {NAME}: formatting parameter value "{VAL}" for display'
                     .format(NAME=self.name, VAL=value))
        display_value = self.format_display_value(value)

        return '{OPER} {VAL}'.format(OPER=operator, VAL=display_value)

    def query_statement(self, column):
        """
        Generate the filter clause for SQL querying.
        """
        if self.has_value():
            operator, value = self.value
            statement = ('{COL} {OPER} ?'.format(COL=column, OPER=operator), (value,))
        else:
            statement = None

        return statement

    def filter_table(self, df):
        """
        Use the parameter value to filter a dataframe.
        """
        if not self.has_value():  # don't filter on NA values
            return df

        if df.empty:
            return df

        operator, value = self.value
        dtype = self.dtype
        column = self.name

        try:
            if dtype in settings.supported_int_dtypes:
                col_values = pd.to_numeric(df[column].fillna(0), errors='coerce', downcast='integer')
            elif dtype in settings.supported_float_dtypes:
                col_values = pd.to_numeric(df[column], errors='coerce')
            else:
                col_values = df[column].astype(np.object_, errors='raise')
        except Exception as e:
            logger.exception('InputParameter {NAME}: unable to set column {COL} to parameter data type {DTYPE} - {ERR}'
                             .format(NAME=self.name, COL=column, DTYPE=dtype, ERR=e))
            col_values = df[column]

        logger.debug('InputParameter {NAME}: filtering table on values {OPER} {VAL}'
                     .format(NAME=self.name, OPER=operator, VAL=value))
        try:
            if operator == '<':  # column values are less than value
                df = df[col_values < value]
            elif operator == '>':  # column values are greater than value
                df = df[col_values > value]
            elif operator == '=':  # column values are equal to value
                df = df[col_values == value]
            elif operator == '>=':  # column values are greater than or equal to value
                df = df[col_values >= value]
            elif operator == '<=':  # column values are less than or equal to value
                df = df[col_values <= value]
        except SyntaxError:
            logger.warning('InputParameter {TBL}: unable to filter table on values {OPER} {VAL}'
                           .format(TBL=self.name, OPER=operator, VAL=value))

        return df

    def has_value(self):
        """
        Return True if element has a valid value else False
        """
        operators = self._operators
        current_value = self.value

        if isinstance(current_value, tuple) and len(current_value) == 2:
            oper, value = current_value

            if value != '' and oper in operators:
                has_value = True
            else:
                has_value = False
        else:
            has_value = False

        return has_value


# Special data parameters
class InputParamterMultiple(InputParameter):
    """
    For multiple selection inputs.

    Attributes:

        name (str): data element configuration name.

        elements (list): list of data element GUI keys.

        value: value of the parameter's data storage elements.
    """

    def __init__(self, name, entry):
        super().__init__(name, entry)
        format_value = settings.format_value

        # Enforce supported data types for the selection parameter
        supported_dtypes = settings.supported_cat_dtypes + settings.supported_str_dtypes
        if not self.dtype or self.dtype not in supported_dtypes:
            msg = 'unsupported data type {DTYPE} provided for the "{ETYPE}" parameter. Supported data types are ' \
                  '{DTYPES}'.format(ETYPE=self.etype, DTYPE=self.dtype, DTYPES=', '.join(supported_dtypes))
            logger.warning('InputParameter {PARAM}: {MSG}'.format(PARAM=name, MSG=msg))

            self.dtype = 'varchar'

        # Display value aliases
        try:
            aliases = entry['Aliases']
        except KeyError:
            aliases = settings.fetch_alias_definition(self.name)

        self.aliases = {}  # only str and int types can have aliases - aliases dict reversed during value formatting
        for alias in aliases:  # alias should have the same datatype as the element
            alias_value = aliases[alias]
            self.aliases[format_value(alias, self.dtype)] = alias_value

        # Menu items
        try:
            menu_values = entry['Values']
        except KeyError:
            msg = 'missing required parameter "Values" for data parameters of type "{ETYPE}"'.format(ETYPE=self.etype)
            mod_win2.popup_notice('Configuration warning: {PARAM}: {MSG}'.format(PARAM=name, MSG=msg))
            logger.warning('InputParameter {PARAM}: {MSG}'.format(PARAM=name, MSG=msg))

            menu_values = []

        self.menu_values = []
        for menu_value in menu_values:
            try:
                value_fmt = format_value(menu_value, self.dtype)
            except ValueError:
                msg = 'unable to format dropdown value "{VAL}" as {DTYPE}'.format(VAL=menu_value, DTYPE=self.dtype)
                mod_win2.popup_notice('Configuration warning: {PARAM}: {MSG}'.format(PARAM=name, MSG=msg))
                logger.warning('InputParameter {PARAM}: {MSG}'.format(PARAM=name, MSG=msg))
            else:
                self.menu_values.append(value_fmt)

        try:
            self.value = self._format_value(self.default)
        except Exception as e:
            msg = "failed to set the parameter's default value - {ERR}".format(ERR=e)
            logger.exception('InputParameter {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            self.value = None
            self.default = None

        logger.debug('InputParameter {NAME}: initializing {ETYPE} parameter of data type {DTYPE} with default value '
                     '{DEF}, and formatted value {VAL}'
                     .format(NAME=self.name, ETYPE=self.etype, DTYPE=self.dtype, DEF=self.default, VAL=self.value))

    def _format_value(self, value):
        """
        Format the provided value according to the parameter's data type.

        Arguments:
            value (str): value to be formatted.

        Returns:
            new_value: value formatted according to the parameter's data type.
        """
        format_value = settings.format_value

        dtype = self.dtype
        aliases = self.aliases
        aliases_rev = {j: i for i, j in aliases.items()}

        if not value:
            return []

        if isinstance(value, list) or isinstance(value, tuple):
            selected_values = value
        else:
            selected_values = [value]

        new_value = []
        for select_value in selected_values:
            try:
                value_fmt = aliases_rev[select_value]
            except KeyError:
                value_fmt = format_value(select_value, dtype)

            new_value.append(value_fmt)

        return new_value

    def run_event(self, window, event, values):
        """
        Run a window event associated with the parameter.
        """
        try:
            param_event = self.bindings[event]
        except KeyError:
            param_event = None

        update_event = False

        if param_event == 'In' and not self.disabled:
            self._set_state(window, state='focus')
        elif param_event == 'Out' and not self.disabled:
            self._set_state(window, state='inactive')
        elif param_event == 'Element' and not self.disabled:
            elem_key = self.key_lookup('Element')
            element = window[elem_key]

            size = window[self.key_lookup('Container')].get_size()
            location = (element.Widget.winfo_rootx(), element.Widget.winfo_rooty() + size[1])

            options = self.format_display_components(self.menu_values)
            current_values = self.format_display_components(self.value)
            selected = mod_win2.select_value_window(options, current=current_values, title=self.description,
                                                    location=location, size=size)

            self.format_value({elem_key: selected})
            self.update_display(window)

            update_event = True

        return update_event

    def element_layout(self):
        """
        Create the type-specific layout for the value element of the parameter.
        """
        disabled = False if self.editable is True else True

        # Element settings
        font = mod_const.SMALL_FONT
        bg_col = mod_const.DEFAULT_BG_COLOR
        text_col = mod_const.DISABLED_TEXT_COLOR

        # Parameter settings
        display_value = self.format_display()
        nselect = len(self.value)
        bttn_text = '- Select -' if nselect < 1 else '{} Selected'.format(nselect)

        # Parameter size
        size = mod_const.FIELD_SIZE
        border = (1, 1)

        # Layout
        elem_key = self.key_lookup('Element')
        frame_key = self.key_lookup('Container')
        layout = sg.Frame('', [[sg.Button(bttn_text, key=elem_key, disabled=disabled, border_width=1, font=font,
                                          button_color=(text_col, bg_col), tooltip=display_value)]],
                          key=frame_key, size=size, pad=border, border_width=0, background_color=bg_col,
                          vertical_alignment='c')

        return layout

    def format_display_components(self, values):
        """
        Format the components of the value for displaying.
        """
        aliases = self.aliases

        if all([pd.isna(i) for i in values]):  # no selections have been made
            return []

        display_values = []
        for value in values:
            if pd.isna(value):
                continue

            try:
                display_value = aliases[value]
            except KeyError:
                display_value = self.format_display_value(value)

            display_values.append(display_value)

        return display_values

    def format_display(self):
        """
        Format the parameter's value for displaying.
        """
        if not self.has_value():
            return ''

        display_values = self.format_display_components(self.value)

        return '; '.join(display_values)

    def update_display(self, window):
        """
        Update the parameter display.
        """
        element = window[self.key_lookup('Element')]

        # Update element text
        display_value = self.format_display()
        nselect = len(self.value) if self.has_value() else 0
        bttn_text = '- Select -' if nselect < 1 else '{} Selected'.format(nselect)

        element.update(text=bttn_text)
        element.set_tooltip(display_value)

    def query_statement(self, column):
        """
        Generate the filter clause for SQL querying.
        """
        if self.has_value():
            values = self.value

            param_list = ','.join(['?' for _ in values])
            statement = ('{COL} IN ({VALS})'.format(COL=column, VALS=param_list), values)
        else:
            statement = None

        return statement

    def filter_table(self, df):
        """
        Use the parameter value to filter a dataframe.
        """
        values = self.value
        dtype = self.dtype
        column = self.name

        if not self.has_value():  # don't filter when no values have been selected
            return df

        if df.empty:
            return df

        try:
            if dtype in settings.supported_date_dtypes:
                col_values = pd.to_datetime(df[column], errors='coerce', format=settings.date_format)
            elif dtype in settings.supported_int_dtypes:
                col_values = pd.to_numeric(df[column].fillna(0), errors='coerce', downcast='integer')
            elif dtype in settings.supported_float_dtypes:
                col_values = pd.to_numeric(df[column], errors='coerce')
            elif dtype in settings.supported_bool_dtypes:
                col_values = df[column].fillna(False).astype(np.bool_, errors='raise')
            else:
                col_values = df[column].astype(np.object_, errors='raise')
        except Exception as e:
            logger.exception('InputParameter {NAME}: unable to set column {COL} to parameter data type {DTYPE} - {ERR}'
                             .format(NAME=self.name, COL=column, DTYPE=dtype, ERR=e))
            col_values = df[column]

        logger.debug('InputParameter {NAME}: filtering table on values {VAL}'.format(NAME=self.name, VAL=values))

        df = df[col_values.isin(values)]

        return df

    def has_value(self):
        """
        Return True if element has a valid value else False
        """
        value = self.value

        if isinstance(value, list) and len(value) > 0:
            return True
        else:
            return False


# Independent functions
def format_display_date(value, sep: str = '-'):
    """
    Format a date string for display.

    Arguments:
        value (list): value to be formatted as an ISO date string.

        sep (str): character used to divide the date components (year, month, day) [Default: "-"].
    """
    if isinstance(value, str):
        logger.warning('input {IN} is a string value'.format(IN=value))
        value = list(value)

    buff = []
    for index, char in enumerate(value):
        if index == 3:
            if len(value) != 4:
                buff.append('{CHAR}{SEP}'.format(CHAR=char, SEP=sep))
            else:
                buff.append(char)
        elif index == 5:
            if len(value) != 6:
                buff.append('{CHAR}{SEP}'.format(CHAR=char, SEP=sep))
            else:
                buff.append(char)
        else:
            buff.append(char)

    formatted_date = ''.join(buff)

    return formatted_date


def initialize_parameter(name, entry):
    """
    Set the parameter class based on the parameter entry element type.
    """
    etype = entry['ElementType']
    if etype in ('dropdown', 'dd', 'combo', 'combobox'):
        param_class = InputParameterCombo
    elif etype in ('input', 'text'):
        param_class = InputParameterText
    elif etype in ('datetime', 'date', 'dt'):
        param_class = InputParameterDate
    elif etype in ('range', 'date_range'):
        param_class = InputParameterRange
    elif etype == 'conditional':
        param_class = InputParameterCondition
    elif etype in ('selection', 'multiple', 'multiselect', 'multi', 'mc'):
        param_class = InputParamterMultiple
    else:
        msg = 'unknown element type {TYPE} provided to parameter entry {NAME}'.format(TYPE=etype, NAME=name)
        logger.warning(msg)
        param_class = InputParameter

    try:
        parameter = param_class(name, entry)
    except AttributeError as e:
        msg = 'failed to initialize parameter {NAME} - {ERR}'.format(NAME=name, ERR=e)

        raise AttributeError(msg)

    return parameter


def fetch_parameter(parameters, identifier, by_key: bool = False, by_type: bool = False):
    """
    Fetch a parameter from a list of parameters by name, event key, or parameter type.
    """
    if by_key:
        match = re.match(r'-(.*?)-', identifier)
        if not match:
            raise KeyError('unknown format provided for element identifier {ELEM}'.format(ELEM=identifier))
        identifier = match.group(0)  # identifier returned if match
        element_key = match.group(1)  # element key part of the identifier after removing any binding

        element_type = element_key.split('_')[-1]
        identifiers = []
        for parameter in parameters:
            try:
                element_name = parameter.key_lookup(element_type)
            except KeyError:
                element_name = None

            identifiers.append(element_name)
    elif by_type:
        identifiers = [i.etype for i in parameters]
    else:
        identifiers = [i.name for i in parameters]

    parameter = [parameters[i] for i, j in enumerate(identifiers) if j == identifier]

    if len(parameter) == 0:
        return None
    elif len(parameter) == 1 and by_type is False:  # single parameter expected
        return parameter[0]
    else:  # list of parameters matching the criteria expected
        return parameter