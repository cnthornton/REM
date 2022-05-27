"""
REM parameter element classes.
"""
import datetime
import sys
from random import randint

import numpy as np
import PySimpleGUI as sg
import pandas as pd

import REM.constants as mod_const
import REM.secondary as mod_win2
from REM.client import logger, settings


class DataParameter:
    """
    Data input parameter element.

    Attributes:

        name (str): data element configuration name.

        id (int): data element number.

        elements (list): list of data element GUI keys.

        description (str): display name of the data element.

        etype (str): GUI element type. Can be dropdown, input, range, or checkbox.

        dtype (str): data type of the parameter's data storage elements [Default: string].

        editable (bool): element is editable. [Default: False]

        hidden (bool): element is not visible to the user. [Default: False]

        required (bool): parameter value is required for an event.

        icon (str): file name of the parameter's icon [Default: None].
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
                         ('Element', 'Description', 'Frame', 'Header', 'Value', 'Width', 'Height')}

        self.bindings = {self.key_lookup(i): i for i in ('Element',)}

        try:
            self.description = entry['Description']
        except KeyError:
            self.description = name

        try:
            self.etype = entry['ElementType']
        except KeyError:
            msg = 'Configuration Error: DataParameter {NAME}: missing required parameter "ElementType".' \
                .format(NAME=name)
            mod_win2.popup_error(msg)
            sys.exit(1)

        try:
            dtype = entry['DataType']
        except KeyError:
            self.dtype = 'varchar'
        else:
            supported_dtypes = settings.get_supported_dtypes()
            if dtype not in supported_dtypes:
                logger.warning('DataElement {NAME}: "DataType" is not a supported data type - supported data types '
                               'are {TYPES}'.format(NAME=name, TYPES=', '.join(supported_dtypes)))
                self.dtype = None
            else:
                self.dtype = dtype

        try:
            editable = bool(int(entry['IsEditable']))
        except KeyError:
            self.editable = True
        except ValueError:
            mod_win2.popup_error('Configuration Error: DataParameter {NAME}: "IsEditable" must be either 0 '
                                 '(False) or 1 (True)'.format(NAME=self.name))
            sys.exit(1)
        else:
            self.editable = editable

        try:
            hidden = bool(int(entry['IsHidden']))
        except KeyError:
            self.hidden = False
        except ValueError:
            mod_win2.popup_error('Configuration Error: DataParameter {NAME}: "IsHidden" must be either 0 '
                                 '(False) or 1 (True)'.format(NAME=self.name))
            sys.exit(1)
        else:
            self.hidden = hidden

        try:
            required = bool(int(entry['IsRequired']))
        except KeyError:
            self.required = False
        except ValueError:
            mod_win2.popup_error('Configuration Error: DataParameter {NAME}: "IsRequired" must be either 0 '
                                 '(False) or 1 (True)'.format(NAME=self.name))
            sys.exit(1)
        else:
            self.required = required

        # Layout attributes
        try:
            self.icon = entry['Icon']
        except KeyError:
            self.icon = None

        try:
            self.justification = entry['Justification']
        except KeyError:
            self.justification = 'right'

        try:
            self.bg_col = entry['BackgroundColor']
        except KeyError:
            self.bg_col = mod_const.DEFAULT_BG_COLOR

        self.auto_size = False

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
            msg = 'DataParameter {NAME}: parameter element {COMP} not found in list of parameter elements' \
                .format(COMP=component, NAME=self.name)
            logger.warning(msg)
            key = None

        return key

    def bind_keys(self, window):
        """
        Set hotkey bindings.
        """
        pass

    def layout(self, size: tuple = None, padding: tuple = (0, 0), bg_col: str = mod_const.DEFAULT_BG_COLOR,
               auto_size_desc: bool = True, hidden: bool = None, justification: str = None, border: bool = False):
        """
        Create a GUI layout for the parameter.
        """
        if bg_col:  # set custom background different from configuration or default
            self.bg_col = bg_col

        justification = justification if justification else self.justification

        is_required = self.required
        visible = not hidden if hidden is not None else not self.hidden

        # Element settings
        pad_el = mod_const.ELEM_PAD
        bold_font = mod_const.BOLD_FONT
        relief = 'flat' if not border else None

        # Parameter settings
        desc = '{}:'.format(self.description)

        # Parameter size
        if size:  # set to fixed size (characters)
            width, height = size
            if auto_size_desc:
                desc_w = 1
                param_w = width - len(desc)
            else:
                desc_w = int(width * 0.4) * 10
                param_w = int(width * 0.6)

            if isinstance(height, int):
                height_px = height * 10
            else:
                height_px = mod_const.PARAM_SIZE_PX[1]

            param_size = (param_w, height)
        else:  # let parameter type determine the size
            desc_w = 1
            height_px = mod_const.PARAM_SIZE_PX[1]
            param_size = None

        value_w = 1
        layout_w = 1

        self.auto_size = auto_size_desc

        # Icon layout
        icon = self.icon
        if icon is None:
            icon_layout = []
        else:
            icon_path = settings.get_icon_path(icon)
            if icon_path is not None:
                icon_layout = [sg.Image(filename=icon_path, pad=((0, pad_el), 0), background_color=bg_col)]
            else:
                icon_layout = []

        # Required symbol
        if is_required is True:
            required_layout = [sg.Text('*', font=bold_font, background_color=bg_col,
                                       text_color=mod_const.NOTE_COLOR, tooltip='required')]
        else:
            required_layout = []

        # Element layout
        desc_key = self.key_lookup('Description')
        desc_layout = [sg.Text(desc, key=desc_key, auto_size_text=True, font=bold_font, background_color=bg_col,
                               tooltip=self.description)]

        header_key = self.key_lookup('Header')
        header_layout = sg.Col([[sg.Canvas(key=header_key, size=(desc_w, 0), background_color=bg_col)],
                                required_layout + icon_layout + desc_layout],
                               pad=(0, (0, pad_el)), background_color=bg_col, element_justification=justification,
                               expand_y=True)

        value_key = self.key_lookup('Value')
        param_layout = sg.Col([[sg.Canvas(key=value_key, size=(value_w, 0), background_color=bg_col)],
                               self.element_layout(size=param_size, bg_col=bg_col)],
                              background_color=bg_col, vertical_alignment='c')

        height_key = self.key_lookup('Height')
        elem_layout = [sg.Canvas(key=height_key, size=(0, height_px), background_color=bg_col), header_layout, param_layout]

        width_key = self.key_lookup('Width')
        frame_key = self.key_lookup('Frame')
        layout = [sg.Frame('', [[sg.Canvas(key=width_key, size=(layout_w, 0), background_color=bg_col)],
                                elem_layout],
                           key=frame_key, pad=padding, visible=visible, background_color=bg_col, relief=relief,
                           border_width=1, vertical_alignment='c')]

        return layout

    def element_layout(self, size: tuple = None, bg_col: str = None):
        """
        Create the type-specific layout for the value element of the parameter.
        """
        return []

    def resize(self, window, size: tuple = None):
        """
        Resize the parameter elements.
        """
        if size:
            width, height = size
        else:
            width, height = mod_const.PARAM_SIZE_PX

        if isinstance(height, int):
            param_h = height
        else:
            param_h = mod_const.PARAM_SIZE_PX[1]

        if isinstance(width, int):
            param_w = width
        else:
            param_w = 1

        width_key = self.key_lookup('Width')
        window[width_key].set_size(size=(param_w, None))

        height_key = self.key_lookup('Height')
        window[height_key].set_size(size=(None, param_h))

        if not self.auto_size:
            # Resize description at 40% of total width and the value element to take up the remaining space
            desc_w = int(param_w * 0.4)
            header_key = self.key_lookup('Header')
            window[header_key].set_size(size=(desc_w, None))

            value_w = int(param_w * 0.6)
            value_key = self.key_lookup('Value')
            window[value_key].set_size(size=(value_w, None))

        elem_key = self.key_lookup('Element')
        window[elem_key].expand(expand_x=True)

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
                logger.warning('DataParameter {NAME}: unsupported value of type {TYPE} provided to parameter with data '
                               'type {DTYPE}'.format(NAME=self.name, TYPE=type(value), DTYPE=dtype))
                display_value = ''
            else:
                display_value = str(new_value)

        elif dtype in settings.supported_int_dtypes:
            try:
                new_value = int(value)
            except ValueError:
                logger.warning('DataParameter {NAME}: unsupported value of type {TYPE} provided to parameter with data '
                               'type {DTYPE}'.format(NAME=self.name, TYPE=type(value), DTYPE=dtype))
                display_value = ''
            else:
                display_value = str(new_value)

        elif dtype in settings.supported_date_dtypes:
            try:
                display_value = settings.format_display_date(value)
            except ValueError:
                logger.warning('DataParameter {NAME}: unsupported value of type {TYPE} provided to parameter with data '
                               'type {DTYPE}'.format(NAME=self.name, TYPE=type(value), DTYPE=dtype))
                display_value = ''

        elif dtype in settings.supported_bool_dtypes:
            try:
                display_value = int(value)
            except ValueError:
                logger.warning('DataParameter {NAME}: unsupported value of type {TYPE} provided to parameter with data '
                               'type {DTYPE}'.format(NAME=self.name, TYPE=type(value), DTYPE=dtype))
                display_value = ''

        else:
            display_value = str(value)

        return display_value

    def toggle(self, window, off: bool = False):
        """
        Toggle the parameter element on or off.
        """
        for element_key in self.bindings:
            window[element_key].update(disabled=off)


# Single value data parameters
class DataParameterInput(DataParameter):
    """
    Data parameter of standard input type.

    Attributes:

        name (str): data element configuration name.

        elements (list): list of data element GUI keys.

        pattern_matching (bool): query parameter using pattern matching [Default: False]

        value: value of the parameter's data storage elements.
    """

    def __init__(self, name, entry):
        super().__init__(name, entry)
        format_value = settings.format_value

        # Enforce supported data types for the input parameter
        supported_dtypes = settings.supported_str_dtypes + settings.supported_cat_dtypes + \
                           settings.supported_int_dtypes + settings.supported_float_dtypes
        if not self.dtype or self.dtype not in supported_dtypes:
            msg = 'unsupported data type {DTYPE} provided for the "{ETYPE}" parameter. Supported data types are ' \
                  '{DTYPES}'.format(ETYPE=self.etype, DTYPE=self.dtype, DTYPES=', '.join(supported_dtypes))
            logger.warning('DataParameter {PARAM}: configuration warning - {MSG}'.format(PARAM=name, MSG=msg))

            self.dtype = 'varchar'

        # Parameter-type specific attributes
        try:  # optional pattern matching flag for string and character data types
            pattern = bool(int(entry['PatternMatching']))
        except KeyError:
            self.pattern_matching = False
        except ValueError:
            msg = 'DataParameter {NAME}: configuration error - "PatternMatching" must be either 0 (False) or 1 (True)' \
                .format(NAME=self.name)
            logger.error(msg)

            raise AttributeError(msg)
        else:
            supported_dtypes = settings.supported_str_dtypes + settings.supported_cat_dtypes
            if self.dtype in supported_dtypes:
                self.pattern_matching = pattern
            else:  # only allow pattern matching for string-like data types
                logger.warning('DataParameter {NAME}: configuration warning - pattern matching is only allowed when '
                               'dtype is set to a supported string or category type'.format(NAME=self.name))
                self.pattern_matching = False

        # Dynamic attributes
        try:
            value_fmt = format_value(entry['DefaultValue'], self.dtype)
        except (KeyError, ValueError):
            self.default = None
            self.value = None
        else:
            self.default = value_fmt
            self.value = value_fmt

        self._value = None

        logger.debug('DataParameter {PARAM}: initializing {ETYPE} parameter of data type {DTYPE} with default '
                     'value {DEF}, and formatted value {VAL}'
                     .format(PARAM=self.name, ETYPE=self.etype, DTYPE=self.dtype, DEF=self.default, VAL=self.value))

    def _enforce_formatting(self, window, value):
        """
        Enforce the correct formatting of user input into the parameter element.
        """
        dec_sep = settings.decimal_sep
        group_sep = settings.thousands_sep

        dtype = self.dtype

        logger.debug('DataParameter {PARAM}: enforcing correct formatting of input value {VAL}'
                     .format(PARAM=self.name, VAL=value))

        if value == '' or pd.isna(value):
            return ''

        elem_key = self.key_lookup('Element')

        if dtype in settings.supported_float_dtypes and dtype == 'money':
            current_value = list(window[elem_key].metadata['value'])

            # Remove currency and grouping separator
            new_value = list(value.replace(group_sep, ''))

            if len(current_value) > len(new_value):  # user removed a character
                # Remove the decimal separator if last character is decimal
                if new_value[-1] == dec_sep:
                    current_value = new_value[0:-1]
                else:
                    current_value = new_value
            elif len(current_value) < len(new_value):  # user added new character
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
            if current_value[0] in ('-', '+'):  # sign of the number
                numeric_sign = current_value[0]
                current_value = current_value[1:]
            else:
                numeric_sign = ''
            if dec_sep in current_value:
                integers, decimals = current_value.split(dec_sep)
                decimals = decimals[0:2]
                current_value = numeric_sign + integers + dec_sep + decimals[0:2]
                display_value = '{SIGN}{VAL}{SEP}{DEC}' \
                    .format(SIGN=numeric_sign, VAL=''.join([group_sep * (n % 3 == 2) + i for n, i in
                                                            enumerate(integers[::-1])][::-1]).lstrip(','),
                            SEP=dec_sep, DEC=decimals)
            else:
                display_value = '{SIGN}{VAL}' \
                    .format(SIGN=numeric_sign, VAL=''.join([group_sep * (n % 3 == 2) + i for n, i in
                                                            enumerate(current_value[::-1])][::-1]).lstrip(','))
                current_value = numeric_sign + current_value

            window[elem_key].metadata['value'] = current_value

        elif dtype in settings.supported_float_dtypes and dtype != 'money':
            current_value = window[elem_key].metadata['value']
            try:
                float(value)
            except ValueError:
                display_value = current_value
            else:
                display_value = value

            window[elem_key].metadata['value'] = display_value

        elif dtype in settings.supported_int_dtypes:
            current_value = window[elem_key].metadata['value']
            try:
                new_value = int(value)
            except ValueError:
                display_value = current_value
            else:
                display_value = str(new_value)

            window[elem_key].metadata['value'] = display_value

        else:
            display_value = value

        return display_value

    def reset(self, window):
        """
        Reset the parameter's values.
        """
        default_value = self.default
        self.value = default_value

        # Update the parameter window element
        if self.hidden is False:
            self.update_display(window)

    def update_display(self, window):
        """
        Update the parameter display.
        """
        elem_key = self.key_lookup('Element')

        # Update element text
        display_value = self.format_display()
        window[elem_key].set_tooltip(display_value)
        window[elem_key].update(value=display_value)

    def run_event(self, window, event, values):
        """
        Run a window event associated with the parameter.
        """
        try:
            param_event = self.bindings[event]
        except KeyError:
            param_event = None

        if param_event == 'Element':
            input_value = values[self.key_lookup('Element')]
            display_value = self._enforce_formatting(input_value)
            window[event].update(value=display_value)

    def format_value(self, values):
        """
        Set the value of the data element from user input.

        Arguments:
            values: GUI element values or a single input value.
        """
        dtype = self.dtype

        if isinstance(values, dict):
            elem_key = self.key_lookup('Element')
            try:
                input_value = values[elem_key]
            except KeyError:
                logger.warning('DataParameter {NAME}: unable to find window values for parameter to update'
                               .format(NAME=self.name))

                return self.value
        else:
            input_value = values

        if input_value == '' or pd.isna(input_value):
            self.value = None

            return None

        try:
            value_fmt = settings.format_value(input_value, dtype)
        except ValueError:
            logger.warning('DataParameter {NAME}: failed to format input value {VAL} as {DTYPE}'
                           .format(NAME=self.name, VAL=input_value, DTYPE=dtype))

            return self.value

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
        logger.debug('DataParameter {NAME}: editable {EDIT}; hidden {VIS}'
                     .format(NAME=self.name, EDIT=self.editable, VIS=self.hidden))

        logger.debug('DataParameter {NAME}: formatting parameter value {VAL} for display as {DISPLAY}'
                     .format(NAME=self.name, VAL=value, DISPLAY=display_value))

        return display_value

    def element_layout(self, size: tuple = None, bg_col: str = None):
        """
        Create the type-specific layout for the value element of the parameter.
        """
        disabled = False if self.editable is True else True

        # Element settings
        font = mod_const.LARGE_FONT
        bg_col = mod_const.DEFAULT_BG_COLOR if bg_col is None else bg_col
        in_col = mod_const.ELEMENT_COLOR if not disabled else bg_col
        text_col = mod_const.DEFAULT_TEXT_COLOR
        pad_el = mod_const.ELEM_PAD

        # Parameter size
        if size:
            elem_w, elem_h = size
            if not isinstance(elem_w, int):
                elem_w = mod_const.PARAM_SIZE_CHAR[0]
            if not isinstance(elem_h, int):
                elem_h = mod_const.PARAM_SIZE_CHAR[1]
        else:
            elem_w, elem_h = mod_const.PARAM_SIZE_CHAR

        # Layout
        elem_key = self.key_lookup('Element')
        display_value = self.format_display()
        layout = [sg.Input(display_value, key=elem_key, size=(elem_w, elem_h), pad=pad_el, enable_events=True,
                           disabled=disabled, font=font, background_color=in_col, text_color=text_col,
                           tooltip='Input value for {}'.format(self.description),
                           metadata={'value': display_value, 'disabled': disabled})]

        return layout

    def query_statement(self, column):
        """
        Generate the filter clause for SQL querying.
        """
        pattern = self.pattern_matching

        query_value = self.value
        if pd.isna(query_value):
            statement = None
        else:
            if pattern is True:
                query_value = '%{VAL}%'.format(VAL=query_value)
                statement = ('{COL} LIKE ?'.format(COL=column), (query_value,))
            else:
                statement = ('{COL} = ?'.format(COL=column), (query_value,))

        return statement

    def filter_table(self, df):
        """
        Use the parameter value to filter a dataframe.
        """
        param_value = self.value
        match_pattern = self.pattern_matching
        dtype = self.dtype
        column = self.name

        if pd.isna(param_value) or param_value == '':  # don't filter on NA values
            return df

        if df.empty:
            return df

        try:
            if dtype in settings.supported_int_dtypes:
                col_values = pd.to_numeric(df[column].fillna(0), errors='coerce', downcast='integer')
            elif dtype in settings.supported_float_dtypes:
                col_values = pd.to_numeric(df[column], errors='coerce')
            else:
                col_values = df[column].astype(np.object_, errors='raise')
        except Exception as e:
            logger.exception('DataParameter {NAME}: unable to set column {COL} to parameter data type {DTYPE} - {ERR}'
                             .format(NAME=self.name, COL=column, DTYPE=dtype, ERR=e))
            col_values = df[column]

        logger.debug('DataParameter {NAME}: filtering table on value {VAL}'.format(NAME=self.name, VAL=param_value))

        if match_pattern is True:
            df = df[col_values.str.contains(param_value, case=False, regex=True)]
        else:
            df = df[col_values == param_value]

        return df

    def has_value(self):
        """
        Return True if element has a valid value else False
        """
        value = self.value
        if pd.isna(value) or value == '':
            return False
        else:
            return True


class DataParameterDate(DataParameter):
    """
    Data parameter split date element.

    Attributes:

        name (str): data element configuration name.

        elements (list): list of data element GUI keys.

        value: value of the parameter's data storage elements.
    """

    def __init__(self, name, entry):
        super().__init__(name, entry)

        calendar_key = '-{NAME}_{ID}_{ELEM}-'.format(NAME=self.name, ID=self.id, ELEM='Calendar')
        self.elements['Calendar'] = calendar_key
        self.bindings[calendar_key] = 'Calendar'

        # Enforce supported data types for the parameter
        supported_dtypes = settings.supported_date_dtypes
        if not self.dtype or self.dtype not in supported_dtypes:
            msg = 'unsupported data type {DTYPE} provided for the "{ETYPE}" parameter. Supported data types are ' \
                  '{DTYPES}'.format(ETYPE=self.etype, DTYPE=self.dtype, DTYPES=', '.join(supported_dtypes))
            logger.warning('DataParameter {PARAM}: {MSG}'.format(PARAM=name, MSG=msg))

            self.dtype = 'datetime'

        # Parameter-type specific attributes
        try:
            self.localize = bool(int(entry['localize']))
        except (KeyError, ValueError):
            self.localize = False

        try:
            self.help_text = entry['HelpText']
        except KeyError:
            self.help_text = 'YYYY/MM/DD'

        self._format = '%Y/%m/%d'

        # Parameters of the split-date type do not accept default values
        self.default = None
        self.value = None
        self._value = ''  # raw unformatted value

        logger.debug('DataParameter {NAME}: initializing {ETYPE} parameter of data type {DTYPE} with default value '
                     '{DEF}, and formatted value {VAL}'
                     .format(NAME=self.name, ETYPE=self.etype, DTYPE=self.dtype, DEF=self.default, VAL=self.value))

    def _enforce_formatting(self, value):
        """
        Enforce the correct formatting of user input into the parameter element.
        """
        strptime = datetime.datetime.strptime

        logger.debug('DataParameter {PARAM}: enforcing correct formatting of input value {VAL}'
                     .format(PARAM=self.name, VAL=value))

        if value == '' or pd.isna(value):
            return ''

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
                logger.warning('DataParameter {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                display_value = format_display_date(raw_value, sep='/')
            else:
                raw_value = new_value
                display_value = new_date.strftime(self._format)
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

    def run_event(self, window, event, values):
        """
        Run a window event associated with the parameter.
        """
        try:
            param_event = self.bindings[event]
        except KeyError:
            param_event = None

        if param_event == 'Element':
            input_value = values[self.key_lookup('Element')]
            display_value = self._enforce_formatting(input_value)
            if display_value == '':
                display_value = self.help_text
                text_color = mod_const.DISABLED_TEXT_COLOR
            else:
                text_color = mod_const.DEFAULT_TEXT_COLOR
            window[event].update(value=display_value, text_color=text_color)

    def reset(self, window):
        """
        Reset the parameter's values.
        """
        logger.debug('DataParameter {NAME}: resetting parameter value "{VAL}" to "{DEF}"'
                     .format(NAME=self.name, VAL=self.value, DEF=self.default))
        self.value = None
        self._value = ''

        # Update the parameter window element
        if self.hidden is False:
            self.update_display(window)

    def element_layout(self, size: tuple = None, bg_col: str = None):
        """
        Create the type-specific layout for the value element of the parameter.
        """
        disabled = False if self.editable is True else True

        # Element settings
        font = mod_const.LARGE_FONT
        bg_col = mod_const.DEFAULT_BG_COLOR if bg_col is None else bg_col
        in_col = mod_const.ELEMENT_COLOR if not disabled else bg_col
        pad_el = mod_const.ELEM_PAD * 2

        # Parameter settings
        display_value = self._enforce_formatting(self._value)
        if display_value == '':
            display_value = self.help_text
            text_col = mod_const.DISABLED_TEXT_COLOR
        else:
            text_col = mod_const.DEFAULT_TEXT_COLOR

        elem_key = self.key_lookup('Element')
        calendar_key = self.key_lookup('Calendar')
        date_ico = mod_const.CALENDAR_ICON

        # Parameter size
        if size:
            elem_w, elem_h = size
            if not isinstance(elem_w, int):
                elem_w = 10 + 2
            if not isinstance(elem_h, int):
                elem_h = 1
        else:
            elem_h = 1
            elem_w = 10 + 2  # number of characters in the date format plus 2

        # Layout
        layout = [sg.Frame('', [[sg.CalendarButton('', target=elem_key, key=calendar_key, format=self._format,
                                                   image_data=date_ico, font=font, pad=(pad_el, 0),
                                                   button_color=(text_col, in_col), border_width=0,
                                                   disabled=disabled,
                                                   tooltip='Select date from calendar menu'),
                                 sg.Input(display_value, key=elem_key, size=(elem_w, elem_h), border_width=0,
                                          background_color=in_col, text_color=text_col, enable_events=True,
                                          disabled=disabled)]],
                           background_color=in_col, border_width=1, expand_x=True)]

        return layout

    def update_display(self, window):
        """
        Update the parameter display.
        """
        elem_key = self.key_lookup('Element')

        # Update element text
        display_value = self.format_display()
        if display_value == '':
            display_value = self.help_text
            text_color = mod_const.DISABLED_TEXT_COLOR
        else:
            text_color = mod_const.DEFAULT_TEXT_COLOR

        window[elem_key].set_tooltip(display_value)
        window[elem_key].update(value=display_value, text_color=text_color)

    def format_display(self):
        """
        Format the parameter's value for displaying.
        """
        if not self.has_value():
            return ''

        display_value = self.value.strftime(self._format)

        return display_value

    def query_statement(self, column):
        """
        Generate the filter clause for SQL querying.
        """
        if self.has_value():
            # query_value = self.value.strftime(settings.date_format)
            query_value = self.value
            statement = ('{COL} = ?'.format(COL=column), (query_value,))
        else:
            statement = None

        return statement

    def filter_table(self, df):
        """
        Use the parameter value to filter a dataframe.
        """
        dtype = self.dtype
        column = self.name

        if not self.has_value():
            return df

        if df.empty:
            return df

        try:
            col_values = pd.to_datetime(df[column], errors='coerce', format=settings.date_format)
        except Exception as e:
            logger.exception('DataParameter {NAME}: unable to set column {COL} to parameter data type {DTYPE} - {ERR}'
                             .format(NAME=self.name, COL=column, DTYPE=dtype, ERR=e))
            col_values = df[column]

        value = self.value
        param_value = value.date()

        logger.debug('DataParameter {NAME}: filtering table on values {VAL}'
                     .format(NAME=self.name, VAL=value.strftime(settings.date_format)))
        df = df[col_values.dt.date == param_value]

        return df

    def has_value(self):
        """
        Return True if element has a valid value else False
        """
        is_datetime_dtype = pd.api.types.is_datetime64_any_dtype

        value = self.value
        if is_datetime_dtype(value):
            return True
        else:
            return False


class DataParameterCombo(DataParameter):
    """
    Dropdown-type data parameter.

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
            logger.warning('DataParameter {PARAM}: {MSG}'.format(PARAM=name, MSG=msg))

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
            logger.warning('DataParameter {PARAM}: {MSG}'.format(PARAM=name, MSG=msg))

            combo_values = []

        self.combo_values = []
        for combo_value in combo_values:
            try:
                value_fmt = settings.format_value(combo_value, self.dtype)
            except ValueError:
                msg = 'unable to format dropdown value "{VAL}" as {DTYPE}'.format(VAL=combo_value, DTYPE=self.dtype)
                mod_win2.popup_notice('Configuration warning: {PARAM}: {MSG}'.format(PARAM=name, MSG=msg))
                logger.warning('DataParameter {PARAM}: {MSG}'.format(PARAM=name, MSG=msg))
            else:
                self.combo_values.append(value_fmt)

                if value_fmt not in self.aliases:
                    self.aliases[value_fmt] = combo_value

        # Dynamic attributes
        try:
            value_fmt = format_value(entry['DefaultValue'], self.dtype)
        except (KeyError, ValueError):
            self.default = None
            self.value = None
        else:
            self.default = value_fmt
            self.value = value_fmt

        logger.debug('DataParameter {PARAM}: initializing {ETYPE} parameter of data type {DTYPE} with default '
                     'value {DEF}, and formatted value {VAL}'
                     .format(PARAM=self.name, ETYPE=self.etype, DTYPE=self.dtype, DEF=self.default, VAL=self.value))

    def reset(self, window):
        """
        Reset the parameter's values.
        """
        default_value = self.default
        self.value = default_value

        # Update the parameter window element
        if self.hidden is False:
            self.update_display(window)

    def update_display(self, window):
        """
        Update the parameter display.
        """
        elem_key = self.key_lookup('Element')

        # Update element text
        display_value = self.format_display()
        window[elem_key].set_tooltip(display_value)
        window[elem_key].update(value=display_value)

    def run_event(self, window, event, values):
        """
        Run a window event associated with the parameter.
        """
        pass

    def format_value(self, values):
        """
        Set the value of the data element from user input.

        Arguments:
            values: GUI element values or a single input value.
        """
        dtype = self.dtype
        aliases = self.aliases

        if isinstance(values, dict):
            elem_key = self.key_lookup('Element')
            try:
                input_value = values[elem_key]
            except KeyError:
                logger.warning('DataParameter {NAME}: unable to find window values for parameter to update'
                               .format(NAME=self.name))

                return self.value
        else:
            input_value = values

        if input_value == '' or pd.isna(input_value):
            self.value = None

            return None

        aliases_rev = {j: i for i, j in aliases.items()}
        try:
            value_fmt = aliases_rev[input_value]
        except KeyError:
            try:
                value_fmt = settings.format_value(input_value, dtype)
            except ValueError:
                logger.warning('DataParameter {NAME}: failed to format input value {VAL} as {DTYPE}'
                               .format(NAME=self.name, VAL=input_value, DTYPE=dtype))

                return self.value

        self.value = value_fmt

        return value_fmt

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

        logger.debug('DataParameter {NAME}: editable {EDIT}; hidden {VIS}'
                     .format(NAME=self.name, EDIT=self.editable, VIS=self.hidden))

        logger.debug('DataParameter {NAME}: formatting parameter value {VAL} for display as {DISPLAY}'
                     .format(NAME=self.name, VAL=value, DISPLAY=display_value))

        return display_value

    def element_layout(self, size: tuple = None, bg_col: str = None):
        """
        Create the type-specific layout for the value element of the parameter.
        """
        disabled = False if self.editable is True else True

        # Element settings
        font = mod_const.LARGE_FONT
        bg_col = mod_const.DEFAULT_BG_COLOR if bg_col is None else bg_col
        in_col = mod_const.ELEMENT_COLOR if not disabled else bg_col
        text_col = mod_const.DEFAULT_TEXT_COLOR

        # Parameter settings
        aliases = self.aliases
        combo_values = self.combo_values
        display_value = self.format_display()

        values = [aliases.get(i, i) for i in combo_values]
        if '' not in values:  # the no selection option
            values.insert(0, '')

        # Parameter element size
        if size:
            elem_w, elem_h = size
        else:
            elem_h = 1
            width = max([len(i) for i in values]) + 1
            elem_w = width if width >= 10 else 10

        # Layout
        elem_key = self.key_lookup('Element')
        layout = [sg.Combo(values, default_value=display_value, key=elem_key, size=(elem_w, elem_h), font=font,
                           background_color=in_col, text_color=text_col, enable_events=True, disabled=disabled,
                           tooltip='Select a value for {}'.format(self.description))]

        return layout

    def query_statement(self, column):
        """
        Generate the filter clause for SQL querying.
        """
        dtype = self.dtype
        value = self.value

        if dtype in settings.supported_bool_dtypes:
            try:
                query_value = int(value)
            except TypeError:
                query_value = None
        else:
            query_value = value

        if pd.isna(query_value):
            statement = None
        else:
            statement = ('{COL} = ?'.format(COL=column), (query_value,))

        return statement

    def filter_table(self, df):
        """
        Use the parameter value to filter a dataframe.
        """
        param_value = self.value
        dtype = self.dtype
        column = self.name

        if pd.isna(param_value):  # don't filter on NA values
            return df

        if df.empty:
            return df

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
            logger.exception('DataParameter {NAME}: unable to set column {COL} to parameter data type {DTYPE} - {ERR}'
                             .format(NAME=self.name, COL=column, DTYPE=dtype, ERR=e))
            col_values = df[column]

        logger.debug('DataParameter {NAME}: filtering table on value {VAL}'.format(NAME=self.name, VAL=param_value))

        df = df[col_values == param_value]

        return df

    def has_value(self):
        """
        Return True if element has a valid value else False
        """
        value = self.value
        if pd.isna(value) or value == '':
            return False
        else:
            return True


class DataParameterCheckbox(DataParameter):
    """
    Checkbox parameter element object.

    Attributes:

        name (str): data element configuration name.

        elements (list): list of data element GUI keys.

        value: value of the parameter's data storage elements.
    """

    def __init__(self, name, entry):
        super().__init__(name, entry)
        format_value = settings.format_value

        self.justification = 'right'

        # Data type check
        supported_dtypes = settings.supported_bool_dtypes
        if self.dtype not in supported_dtypes:
            msg = 'unsupported data type {DTYPE} provided for the "{ETYPE}" parameter. Supported data types are ' \
                  '{DTYPES}'.format(ETYPE=self.etype, DTYPE=self.dtype, DTYPES=', '.join(supported_dtypes))
            logger.warning('DataParameter {PARAM}: {MSG}'.format(PARAM=name, MSG=msg))

            self.dtype = 'bool'

        try:
            default_value = entry['DefaultValue']
        except KeyError:
            default_value = False

        try:
            self.default = self.value = format_value(default_value, self.dtype)
        except ValueError:
            self.default = self.value = False

        # Dynamic attributes
        logger.debug('DataParameter {PARAM}: initializing {ETYPE} parameter of data type {DTYPE} with default '
                     'value {DEF}, and formatted value {VAL}'
                     .format(PARAM=self.name, ETYPE=self.etype, DTYPE=self.dtype, DEF=self.default, VAL=self.value))

    def run_event(self, window, event, values):
        """
        Run a window event associated with the parameter.
        """
        pass

    def reset(self, window):
        """
        Reset the parameter's values.
        """
        # Update the parameter window element
        if self.hidden is False:
            self.value = self.default
            self.update_display(window)

    def resize(self, window, size: tuple = None):
        """
        Resize the checkbox parameter elements.
        """
        if size:
            width, height = size
        else:
            width, height = mod_const.PARAM_SIZE_PX

        # Set the parameter width
        width_key = self.key_lookup('Width')
        param_w = width
        window[width_key].set_size(size=(param_w, None))

        # Resize description at 40% of total width and the value element to take up the remaining space
        desc_w = width - 26
        desc_h = int(height / 10) if height else None

        header_key = self.key_lookup('Header')
        window[header_key].set_size(size=(desc_w, desc_h))

    def update_display(self, window):
        """
        Update the parameter display.
        """
        elem_key = self.key_lookup('Element')

        # Update element text
        display_value = self.format_display()
        window[elem_key].set_tooltip(display_value)
        window[elem_key].update(value=display_value)

    def element_layout(self, size: tuple = None, bg_col: str = None):
        """
        Create the type-specific layout for the value element of the parameter.
        """
        size = size if size else mod_const.PARAM_SIZE_CHAR
        disabled = False if self.editable is True else True

        # Element settings
        bg_col = mod_const.DEFAULT_BG_COLOR if bg_col is None else bg_col
        box_col = bg_col if not disabled else mod_const.DISABLED_BG_COLOR

        # Parameter size
        width, height = size
        elem_w = 0
        elem_h = height

        # Parameter settings
        display_value = self.format_display()

        elem_key = self.key_lookup('Element')
        layout = [sg.Checkbox('', default=display_value, key=elem_key, size=(elem_w, elem_h), enable_events=True,
                              disabled=disabled, background_color=bg_col, checkbox_color=box_col,
                              metadata={'value': display_value, 'disabled': disabled})]

        return layout

    def format_value(self, values):
        """
        Set the value of the data element from user input.

        Arguments:
            values: GUI element values or a single input value.
        """
        dtype = self.dtype

        if isinstance(values, dict):
            elem_key = self.key_lookup('Element')
            try:
                input_value = values[elem_key]
            except KeyError:
                logger.warning('DataParameter {NAME}: unable to find window values for parameter to update'
                               .format(NAME=self.name))

                return self.value
        else:
            input_value = values

        print('parameter {} has initial input value: {}'.format(self.name, input_value))

        if input_value == '' or pd.isna(input_value):
            self.value = None

            return None

        try:
            value_fmt = settings.format_value(input_value, dtype)
        except ValueError:
            logger.warning('DataParameter {NAME}: failed to format input value {VAL} as {DTYPE}'
                           .format(NAME=self.name, VAL=input_value, DTYPE=dtype))

            return self.value

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

        logger.debug('DataParameter {NAME}: editable {EDIT}; hidden {VIS}'
                     .format(NAME=self.name, EDIT=self.editable, VIS=self.hidden))

        logger.debug('DataParameter {NAME}: formatting parameter value {VAL} for display as {DISPLAY}'
                     .format(NAME=self.name, VAL=value, DISPLAY=display_value))

        return display_value

    def has_value(self):
        """
        Return True if element has a valid value else False
        """
        value = self.value
        if pd.isna(value) or value == '':
            return False
        else:
            return True

    def query_statement(self, column):
        """
        Generate the filter clause for SQL querying.
        """
        value = self.value

        try:
            query_value = int(value)
        except ValueError:
            msg = 'unable to format parameter value {VAL} for querying - unsupported value type "{TYPE}" provided' \
                .format(VAL=value, TYPE=type(value))
            logger.error('DataParameter {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            query_value = None

        if pd.isna(query_value):
            statement = None
        else:
            statement = ('{COL} = ?'.format(COL=column), (query_value,))

        return statement

    def filter_table(self, df):
        """
        Use the parameter value to filter a dataframe.
        """
        param_value = self.value
        column = self.name

        if not param_value:  # don't filter on NA values or False values
            return df

        if df.empty:
            return df

        try:
            col_values = df[column].fillna(False).astype(np.bool_, errors='raise')
        except Exception as e:
            logger.exception('DataParameter {NAME}: unable to set column {NAME} to parameter data type bool - {ERR}'
                             .format(NAME=column, ERR=e))
            col_values = df[column]

        logger.debug('DataParameter {NAME}: filtering table on value {VAL}'.format(NAME=self.name, VAL=param_value))

        df = df[col_values == param_value]

        return df


# Multiple component data parameters
class DataParameterComp(DataParameter):
    """
    Parent class for data parameters where the element value is split into components.

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
            logger.warning('DataParameter {PARAM}: {MSG}'.format(PARAM=name, MSG=msg))

            self.dtype = 'float'

        try:
            default_values = entry['DefaultValue']
        except KeyError:
            default_values = (None, None)

        self.default = self.value = default_values

    def reset(self, window):
        """
        Reset the parameter's values.
        """
        # Update the parameter window element
        if self.hidden is False:
            self.value = self.default
            self.update_display(window)

    def update_display(self, window):
        """
        Update the parameter display.
        """
        elem_key = self.key_lookup('Element')

        # Update element text
        display_value = self.format_display()
        window[elem_key].set_tooltip(display_value)
        window[elem_key].update(value=display_value)

    def element_layout(self, size: tuple = None, bg_col: str = None):
        """
        Create the type-specific layout for the value element of the parameter.
        """
        size = size if size else mod_const.PARAM_SIZE_CHAR
        disabled = False if self.editable is True else True

        # Element settings
        font = mod_const.LARGE_FONT
        bg_col = self.bg_col if bg_col is None else bg_col
        in_col = mod_const.ELEMENT_COLOR
        text_col = mod_const.DEFAULT_TEXT_COLOR

        # Parameter size
        width, height = size
        elem_w = int(width * 0.7)
        elem_h = height

        # Parameter settings
        display_value = self.format_display()

        elem_key = self.key_lookup('Element')
        if not disabled:
            layout = [sg.Text(display_value, key=elem_key, size=(elem_w, elem_h),
                              font=font, background_color=in_col, text_color=text_col, relief='ridge',
                              tooltip='Set value range for {}'.format(self.description), enable_events=True,
                              justification='c', metadata={'value': [], 'disabled': disabled})]
        else:
            layout = [sg.Text(display_value, key=elem_key, size=(elem_w, elem_h), font=font,
                              background_color=bg_col, text_color=text_col, border_width=1, justification='c',
                              metadata={'value': [], 'disabled': disabled})]

        return layout


class DataParameterRange(DataParameterComp):
    """
    Data parameter with a range-picking element.

    Attributes:

        name (str): data element configuration name.

        elements (list): list of data element GUI keys.

        value: value of the parameter's data storage elements.
    """

    def __init__(self, name, entry):
        super().__init__(name, entry)
        format_value = settings.format_value

        try:
            default1, default2 = entry['DefaultValue']
        except KeyError:
            default1 = default2 = None
        except ValueError:
            default1 = default2 = entry['DefaultValue']

        # Dynamic attributes
        try:
            self.default = self.value = [format_value(default1, self.dtype), format_value(default2, self.dtype)]
        except ValueError:
            self.default = self.value = (None, None)

        logger.debug('DataParameter {NAME}: initializing {ETYPE} parameter of data type {DTYPE} with default value '
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

        if param_event == 'Element':
            self.value = mod_win2.range_value_window(self.dtype, current=self.value, title=self.description,
                                                     date_format='YYYY-MM-DD', location=window.mouse_location())

            display_value = self.format_display()
            window[event].update(value=display_value)

    def format_value(self, values):
        """
        Set the value of the data element from user input.

        Arguments:
            values: GUI element values or a single input value.
        """
        format_value = settings.format_value

        if isinstance(values, dict):
            try:
                input_values = values[self.key_lookup('Element')]
            except KeyError:
                msg = 'DataParameter {NAME}: unable to find window values for parameter to update'.format(
                    NAME=self.name)
                logger.warning(msg)

                return self.value
        else:
            input_values = values

        try:
            in1, in2 = input_values
        except ValueError:
            in1 = in2 = input_values

        try:
            in1_fmt = format_value(in1, self.dtype)
        except ValueError as e:
            msg = 'DataParameter {NAME}: unable set datatype for the first value - {ERR}'.format(NAME=self.name, ERR=e)
            logger.warning(msg)

            in1_fmt = None

        try:
            in2_fmt = format_value(in2, self.dtype)
        except ValueError as e:
            msg = 'DataParameter {NAME}: unable set datatype for the second value - {ERR}'.format(NAME=self.name, ERR=e)
            logger.warning(msg)

            in2_fmt = None

        value_fmt = [in1_fmt, in2_fmt]
        self.value = value_fmt

        return value_fmt

    def format_display(self):
        """
        Format the parameter's value for displaying.
        """
        values = self.value

        if all([pd.isna(i) for i in values]):  # no parameter values set for either range element
            return ''

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
        try:
            from_val, to_val = values
        except ValueError:
            statement = None
        else:
            if from_val and to_val:
                statement = ('{COL} BETWEEN ? AND ?'.format(COL=column), values)
            elif from_val and not to_val:
                statement = ('{COL} = ?'.format(COL=column), (from_val,))
            elif to_val and not from_val:
                statement = ('{COL} = ?'.format(COL=column), (to_val,))
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
            logger.error('DataParameter {NAME}: ranged parameters require exactly two values'
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
            logger.exception('DataParameter {NAME}: unable to set column {COL} to parameter data type {DTYPE} - {ERR}'
                             .format(NAME=self.name, COL=column, DTYPE=dtype, ERR=e))
            col_values = df[column]

        if from_value not in (None, '') and to_value not in (None, ''):  # select rows in range
            logger.debug('DataParameter {NAME}: filtering table on values {VAL1} and {VAL2}'
                         .format(NAME=self.name, VAL1=from_value, VAL2=to_value))
            try:
                df = df[(col_values >= from_value) & (col_values <= to_value)]
            except KeyError:
                logger.warning('DataParameter {NAME}: parameter name not found in the table header'
                               .format(NAME=self.name))
            except SyntaxError:
                logger.warning('DataParameter {TBL}: unable to filter table on parameter values {VAL1} and {VAL2}'
                               .format(TBL=self.name, VAL1=from_value, VAL2=to_value))
        elif from_value not in (None, '') and to_value in (None, ''):  # rows equal to from component
            logger.debug('DataParameter {NAME}: filtering table on parameter value {VAL}'
                         .format(NAME=self.name, VAL=from_value))
            try:
                df = df[col_values == from_value]
            except KeyError:
                logger.warning('DataParameter {NAME}: parameter not found in the table header'.format(NAME=self.name))
            except SyntaxError:
                logger.warning('DataParameter {NAME}: unable to filter table on parameter value {VAL}'
                               .format(NAME=self.name, VAL=from_value))
        elif to_value not in (None, '') and from_value in (None, ''):  # rows equal to the to component
            logger.debug('DataParameter {NAME}: filtering table on parameter value {VAL}'
                         .format(NAME=self.name, VAL=to_value))
            try:
                df = df[col_values == to_value]
            except KeyError:
                logger.warning('DataParameter {NAME}: parameter not found in the table header'.format(NAME=self.name))
            except SyntaxError:
                logger.warning('DataParameter {NAME}: unable to filter table on parameter value {VAL}'
                               .format(NAME=self.name, VAL=to_value))

        return df

    def has_value(self):
        """
        Return True if element has a valid value else False
        """
        values = self.value

        values_set = []
        for value in values:
            if not pd.isna(value) and not value == '':
                values_set.append(True)
            else:
                values_set.append(False)

        return any(values_set)


class DataParameterCondition(DataParameterComp):
    """
    Data parameter with a condition-picking element.

    Attributes:

        name (str): data element configuration name.

        elements (list): list of data element GUI keys.

        value: value of the parameter's data storage elements.
    """

    def __init__(self, name, entry):
        super().__init__(name, entry)
        self._operators = ['>', '<', '>=', '<=', '=']

        try:
            oper, default = entry['DefaultValue']
        except (KeyError, ValueError):
            oper = default = None

        if oper not in self._operators:
            oper = None

        # Dynamic attributes
        try:
            self.default = self.value = [oper, settings.format_value(default, self.dtype)]
        except ValueError:
            self.default = self.value = (oper, None)

        logger.debug('DataParameter {NAME}: initializing {ETYPE} parameter of data type {DTYPE} with default value '
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

        if param_event == 'Element':
            self.value = mod_win2.conditional_value_window(self.dtype, current=self.value, title=self.description,
                                                           location=window.mouse_location())

            display_value = self.format_display()
            window[event].update(value=display_value)

    def format_value(self, values):
        """
        Set the value of the data element from user input.

        Arguments:
            values: GUI element values or a single input value.
        """
        operators = self._operators

        if isinstance(values, dict):
            try:
                input_values = values[self.key_lookup('Element')]
            except KeyError:
                msg = 'DataParameter {NAME}: unable to find window values for parameter to update'.format(
                    NAME=self.name)
                logger.warning(msg)

                return self.value
        else:
            input_values = values

        try:
            oper, value = input_values
        except ValueError:
            msg = 'DataParameter {NAME}: input value should be a list or tuple of exactly two components' \
                .format(NAME=self.name)
            logger.warning(msg)

            return self.value

        if oper not in operators:
            msg = 'DataParameter {NAME}: unknown operator "{OPER}" provided as the first component of the value set' \
                .format(NAME=self.name, OPER=oper)
            logger.warning(msg)

            return self.value

        try:
            value_fmt = settings.format_value(value, self.dtype)
        except ValueError as e:
            msg = 'DataParameter {NAME}: unable set datatype for the conditional value - {ERR}' \
                .format(NAME=self.name, ERR=e)
            logger.warning(msg)

            value_fmt = None

        value_fmt = [oper, value_fmt]
        self.value = value_fmt

        return value_fmt

    def format_display(self):
        """
        Format the parameter's value for displaying.
        """
        operator, value = self.value

        if not self.has_value():  # no parameter value + operator combo set
            return ''

        logger.debug('DataParameter {NAME}: editable {EDIT}; hidden {VIS}'
                     .format(NAME=self.name, EDIT=self.editable, VIS=self.hidden))

        logger.debug('DataParameter {NAME}: formatting parameter value "{VAL}" for display'
                     .format(NAME=self.name, VAL=value))
        display_value = self.format_display_value(value)

        return '{OPER} {VAL}'.format(OPER=operator, VAL=display_value)

    def query_statement(self, column):
        """
        Generate the filter clause for SQL querying.
        """
        try:
            operator, value = self.value
        except ValueError:
            statement = None
        else:
            if self.has_value():
                statement = ('{COL} {OPER} ?'.format(COL=column, OPER=operator), (value,))
            else:
                statement = None

        return statement

    def filter_table(self, df):
        """
        Use the parameter value to filter a dataframe.
        """
        operator, value = self.value
        dtype = self.dtype
        column = self.name

        if not self.has_value():  # don't filter on NA values
            return df

        if df.empty:
            return df

        try:
            if dtype in settings.supported_int_dtypes:
                col_values = pd.to_numeric(df[column].fillna(0), errors='coerce', downcast='integer')
            elif dtype in settings.supported_float_dtypes:
                col_values = pd.to_numeric(df[column], errors='coerce')
            else:
                col_values = df[column].astype(np.object_, errors='raise')
        except Exception as e:
            logger.exception('DataParameter {NAME}: unable to set column {COL} to parameter data type {DTYPE} - {ERR}'
                             .format(NAME=self.name, COL=column, DTYPE=dtype, ERR=e))
            col_values = df[column]

        logger.debug('DataParameter {NAME}: filtering table on values {OPER} {VAL}'
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
            logger.warning('DataParameter {TBL}: unable to filter table on values {OPER} {VAL}'
                           .format(TBL=self.name, OPER=operator, VAL=value))

        return df

    def has_value(self):
        """
        Return True if element has a valid value else False
        """
        operators = ['>', '<', '>=', '<=', '=']

        operator, value = self.value

        if not pd.isna(value) and not value == '' and operator in operators:
            return True
        else:
            return False


# Special data parameters
class DataParameterMultiple(DataParameter):
    """
    Data parameter multiple selection element.

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
            logger.warning('DataParameter {PARAM}: {MSG}'.format(PARAM=name, MSG=msg))

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
            logger.warning('DataParameter {PARAM}: {MSG}'.format(PARAM=name, MSG=msg))

            menu_values = []

        self.menu_values = []
        for menu_value in menu_values:
            try:
                value_fmt = format_value(menu_value, self.dtype)
            except ValueError:
                msg = 'unable to format dropdown value "{VAL}" as {DTYPE}'.format(VAL=menu_value, DTYPE=self.dtype)
                mod_win2.popup_notice('Configuration warning: {PARAM}: {MSG}'.format(PARAM=name, MSG=msg))
                logger.warning('DataParameter {PARAM}: {MSG}'.format(PARAM=name, MSG=msg))
            else:
                self.menu_values.append(value_fmt)

        # Parameter default selections
        try:
            default_values = entry['DefaultValue']
        except KeyError:
            default_values = []

        self.default = self.value = [format_value(i, self.dtype) for i in default_values if i in menu_values]

        logger.debug('DataParameter {NAME}: initializing {ETYPE} parameter of data type {DTYPE} with default value '
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

        if param_event == 'Element':
            options = self.format_display_components(self.menu_values)
            current_values = self.format_display_components(self.value)
            selected = mod_win2.select_value_window(options, current=current_values, title=self.description,
                                                    location=window.mouse_location())

            element_key = self.key_lookup('Element')
            self.format_value({element_key: selected})
            self.update_display(window)

    def reset(self, window):
        """
        Reset the parameter's values.
        """
        logger.debug('DataParameter {NAME}: resetting parameter value "{VAL}" to "{DEF}"'
                     .format(NAME=self.name, VAL=self.value, DEF=self.default))
        self.value = [i for i in self.default]

        # Update the parameter window element
        if self.hidden is False:
            self.update_display(window)

    def element_layout(self, size: tuple = None, bg_col: str = None):
        """
        Create the type-specific layout for the value element of the parameter.
        """
        size = size if size else mod_const.PARAM_SIZE_CHAR
        disabled = False if self.editable is True else True

        # Element settings
        font = mod_const.LARGE_FONT
        bg_col = self.bg_col if bg_col is None else bg_col
        in_col = mod_const.ELEMENT_COLOR
        text_col = mod_const.DEFAULT_TEXT_COLOR
        bttn_text_col = mod_const.DISABLED_TEXT_COLOR

        # Parameter size
        width, height = size
        elem_w = width
        elem_h = height

        # Parameter settings
        display_value = self.format_display()

        elem_key = self.key_lookup('Element')
        if not disabled:
            nselect = len(self.value)
            text_font = mod_const.SMALL_FONT
            bttn_text = '- Select -' if nselect < 1 else '{} Selected'.format(nselect)
            layout = [sg.Button(bttn_text, key=elem_key, border_width=1, font=text_font,
                                button_color=(bttn_text_col, in_col), tooltip=display_value)]

        else:
            layout = [sg.Text(display_value, key=elem_key, size=(elem_w, elem_h), font=font,
                              background_color=bg_col, text_color=text_col, border_width=0, justification='c',
                              metadata={'value': [], 'disabled': disabled})]

        return layout

    def format_value(self, values):
        """
        Set the value of the data element from user input.

        Arguments:
            values: GUI element values or a single input value.
        """
        format_value = settings.format_value
        aliases = self.aliases
        dtype = self.dtype
        current_values = self.value

        if isinstance(values, dict):
            try:
                selected_values = values[self.key_lookup('Element')]
            except KeyError:
                msg = 'DataParameter {NAME}: unable to find window values for parameter to update'.format(
                    NAME=self.name)
                logger.warning(msg)

                return current_values
        elif isinstance(values, list) or isinstance(values, tuple):
            selected_values = values
        elif values == '' or pd.isna(values):
            return current_values
        else:
            selected_values = [values]

        aliases_rev = {j: i for i, j in aliases.items()}
        try:
            formatted_values = [aliases_rev[i] for i in selected_values]
        except KeyError:
            try:
                formatted_values = [format_value(i, dtype) for i in selected_values]
            except ValueError:
                logger.warning('DataParameter {NAME}: failed to format selected value {VAL} as {DTYPE}'
                               .format(NAME=self.name, VAL=selected_values, DTYPE=dtype))
                return current_values

        self.value = formatted_values

        return formatted_values

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
        display_values = self.format_display_components(self.value)

        return '; '.join(display_values)

    def update_display(self, window):
        """
        Update the parameter display.
        """
        elem_key = self.key_lookup('Element')

        # Update element text
        display_value = self.format_display()
        nselect = len(self.value)
        bttn_text = '- Select -' if nselect < 1 else '{} Selected'.format(nselect)
        window[elem_key].set_tooltip(display_value)
        window[elem_key].Widget.configure(text=bttn_text)

    def query_statement(self, column):
        """
        Generate the filter clause for SQL querying.
        """
        values = self.value
        if len(values) > 0:
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

        if not values:  # don't filter when no values have been selected
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
            logger.exception('DataParameter {NAME}: unable to set column {COL} to parameter data type {DTYPE} - {ERR}'
                             .format(NAME=self.name, COL=column, DTYPE=dtype, ERR=e))
            col_values = df[column]

        logger.debug('DataParameter {NAME}: filtering table on values {VAL}'.format(NAME=self.name, VAL=values))

        df = df[col_values.isin(values)]

        return df

    def has_value(self):
        """
        Return True if element has a valid value else False
        """
        values = self.value

        if len(values) > 0:
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


def fetch_parameter(parameters, identifier, by_key: bool = False, by_type: bool = False):
    """
    Fetch a parameter from a list of parameters by name, event key, or parameter type.
    """
    if by_key:
        element_type = identifier[1:-1].split('_')[-1]
        identifiers = [i.key_lookup(element_type) for i in parameters]
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


def initialize_parameter(name, entry):
    """
    Set the parameter class based on the parameter entry element type.
    """
    etype = entry['ElementType']
    if etype in ('dropdown', 'dd', 'combo', 'combobox'):
        param_class = DataParameterCombo
    elif etype in ('input', 'text'):
        param_class = DataParameterInput
    elif etype in ('datetime', 'date', 'dt'):
        param_class = DataParameterDate
    elif etype in ('range', 'date_range'):
        param_class = DataParameterRange
    elif etype == 'conditional':
        param_class = DataParameterCondition
    elif etype in ('checkbox', 'check', 'bool', 'tf'):
        param_class = DataParameterCheckbox
    elif etype in ('selection', 'multiple', 'mc'):
        param_class = DataParameterMultiple
    else:
        msg = 'unknown element type {TYPE} provided to parameter entry {NAME}'.format(TYPE=etype, NAME=name)

        raise TypeError(msg)

    try:
        parameter = param_class(name, entry)
    except AttributeError as e:
        msg = 'failed to initialize parameter {NAME} - {ERR}'.format(NAME=name, ERR=e)

        raise AttributeError(msg)

    return parameter
