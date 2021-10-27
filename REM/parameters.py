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
        self.elements = ['-{NAME}_{ID}_{ELEM}-'.format(NAME=self.name, ID=self.id, ELEM=i) for i in
                         ('Element', 'Header', 'Value', 'Description', 'Width')]

        self._event_elements = ['Element']
        self.bindings = [self.key_lookup(i) for i in self._event_elements]

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
            self.bg_col = mod_const.ACTION_COL

        self.auto_size = False

    def key_lookup(self, component):
        """
        Lookup an element's component GUI key using the name of the component element.
        """
        element_names = [i[1:-1].split('_')[-1] for i in self.elements]
        if component in element_names:
            key_index = element_names.index(component)
            key = self.elements[key_index]
        else:
            msg = 'DataParameter {NAME}: parameter element {COMP} not found in list of parameter elements' \
                .format(COMP=component, NAME=self.name)
            logger.warning(msg)
            key = None

        return key

    def layout(self, size: tuple = None, padding: tuple = (0, 0), bg_col: str = mod_const.ACTION_COL,
               auto_size_desc: bool = True, hidden: bool = None, justification: str = None, border: bool = False):
        """
        Create a GUI layout for the parameter.
        """
        if bg_col:  # set custom background different from configuration or default
            self.bg_col = bg_col

        size = size if size else mod_const.PARAM_SIZE_CHAR
        justification = justification if justification else self.justification

        is_required = self.required
        visible = not hidden if hidden is not None else not self.hidden

        # Element settings
        pad_el = mod_const.ELEM_PAD
        bold_font = mod_const.BOLD_FONT
        relief = 'flat' if not border else None

        # Parameter size
        width, height = size
        if auto_size_desc:
            desc_w = 1
            value_w = 1
            layout_w = 1
            param_w = width
            self.auto_size = True
        else:
            desc_w = int(width * 0.4) * 10
            param_w = int(width * 0.6)
            value_w = 1
            layout_w = width * 10

        # Parameter settings
        desc = '{}:'.format(self.description)

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
                                       text_color=mod_const.NOTE_COL, tooltip='required')]
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
                               self.element_layout(size=(param_w, height), bg_col=bg_col)],
                              background_color=bg_col, expand_y=True)

        width_key = self.key_lookup('Width')
        elem_layout = [sg.Canvas(size=(0, 28), background_color=bg_col), header_layout, param_layout]
        layout = [[sg.Canvas(key=width_key, size=(layout_w, 0), background_color=bg_col)],
                  elem_layout]

        return [sg.Frame('', layout, pad=padding, visible=visible, background_color=bg_col, relief=relief,
                         border_width=1, vertical_alignment='c')]

    def element_layout(self, size: tuple = None, bg_col: str = None):
        """
        Create the type-specific layout for the value element of the parameter.
        """
        return []

    def resize(self, window, size: tuple = None, pixels: bool = True):
        """
        Resize the parameter elements.
        """
        if size:
            width, height = size
        else:
            width, height = mod_const.PARAM_SIZE_PX if pixels else mod_const.PARAM_SIZE_CHAR

        auto_size = self.auto_size

        # Resize description at 40% of total width and the value element to take up the remaining space
        if pixels:
            desc_w = int(width * 0.4) if not auto_size else 1
            elem_w = int(width * 0.6) if not auto_size else 1
            desc_h = elem_h = height
            param_w = width if not auto_size else 1
        else:
            desc_w = int(width * 0.4) * 10 if not auto_size else 1
            elem_w = int(width * 0.6) * 10 if not auto_size else 1
            desc_h = elem_h = int(height * 10) if height else None
            param_w = width * 10 if not auto_size else 1

        width_key = self.key_lookup('Width')
        window[width_key].set_size(size=(param_w, None))

        header_key = self.key_lookup('Header')
        window[header_key].set_size(size=(desc_w, desc_h))

        value_key = self.key_lookup('Value')
        window[value_key].set_size(size=(elem_w, elem_h))

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
            display_value = value

        else:
            display_value = str(value)

        return display_value

    def toggle_elements(self, window, value: str = 'enable'):
        """
        Toggle parameter elements on and off.
        """
        status = False if value == 'enable' else True

        for element_key in self.elements:
            if window[element_key].metadata and 'disabled' in window[element_key].metadata:
                logger.debug('DataParameter {NAME}: updating element {KEY} to "disabled={VAL}"'
                             .format(NAME=self.name, KEY=element_key, VAL=status))
                window[element_key].update(disabled=status)


# Single value data parameters
class DataParameterSingle(DataParameter):
    """
    Data parameter with multi-value type elements.

    Attributes:

        name (str): data element configuration name.

        elements (list): list of data element GUI keys.

        aliases (dict): optional value aliases.

        value: value of the parameter's data storage elements.
    """

    def __init__(self, name, entry):
        super().__init__(name, entry)
        format_value = settings.format_value

        # Display value aliases
        try:
            aliases = entry['Aliases']
        except KeyError:
            aliases = settings.fetch_alias_definition(self.name)

        self.aliases = {}  # only str and int types can have aliases - aliases dict reversed during value formatting
        if self.dtype in (settings.supported_int_dtypes + settings.supported_cat_dtypes + settings.supported_str_dtypes):
            for alias in aliases:  # alias should have same datatype as the element
                alias_value = aliases[alias]
                self.aliases[format_value(alias, self.dtype)] = alias_value

        try:
            default_value = entry['DefaultValue']
        except KeyError:
            default_value = None

        try:
            self.default = self.value = format_value(default_value, self.dtype)
        except ValueError:
            self.default = self.value = None

        # Dynamic attributes
        logger.debug('DataParameter {PARAM}: initializing {ETYPE} parameter of data type {DTYPE} with default '
                     'value {DEF}, and formatted value {VAL}'
                     .format(PARAM=self.name, ETYPE=self.etype, DTYPE=self.dtype, DEF=self.default, VAL=self.value))

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

    def run_event(self, window, event, values):
        """
        Run a window event associated with the parameter.
        """
        if event in self.elements:
            display_value = self.enforce_formatting(window, values, event)
            window[event].update(value=display_value)

    def enforce_formatting(self, window, values, elem_key):
        """
        Enforce the correct formatting of user input into the parameter element.
        """
        strptime = datetime.datetime.strptime
        dec_sep = settings.decimal_sep
        group_sep = settings.thousands_sep

        dtype = self.dtype
        aliases = {j: i for i, j in self.aliases.items()}

        value = values[elem_key]
        logger.debug('DataParameter {PARAM}: enforcing correct formatting of input value {VAL}'
                     .format(PARAM=self.name, VAL=value))

        if value == '' or pd.isna(value):
            return ''

        if value in aliases:
            return value

        elem_key = self.key_lookup('Element')

        if dtype in settings.supported_date_dtypes:
            current_value = list(window[elem_key].metadata['value'])

            # Remove separator from the input
            new_value = list(value.replace('-', ''))
            input_len = len(new_value)
            if input_len == 8:
                try:
                    new_date = strptime(''.join(new_value), '%Y%m%d')
                except ValueError:  # date is incorrectly formatted
                    msg = '{} is not a valid date format'.format(''.join(new_value))
                    mod_win2.popup_notice(msg)
                    logger.warning('DataParameter {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                    display_value = settings.format_as_iso(''.join(current_value))
                else:
                    current_value = new_value
                    display_value = new_date.strftime('%Y-%m-%d')
            elif input_len < 8:
                current_len = len(current_value)
                if current_len > input_len:  # user deleted a character
                    current_value = new_value
                elif current_len < input_len:  # user added a character
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

                else:  # user replaced a character
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

                display_value = settings.format_as_iso(current_value)
            else:
                display_value = settings.format_as_iso(current_value)

            window[elem_key].metadata['value'] = ''.join(current_value)

        elif dtype in settings.supported_float_dtypes and dtype == 'money':
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


class DataParameterInput(DataParameterSingle):
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

        # Add additional calendar element for input with datetime data types to list of editable elements
        if self.dtype in settings.supported_date_dtypes:
            calendar_key = '-{NAME}_{ID}_{ELEM}-'.format(NAME=self.name, ID=self.id, ELEM='Calendar')
            self.elements.append(calendar_key)
            self.bindings.append(calendar_key)

        # Data type check
        if not self.dtype:
            self.dtype = 'varchar'

        # Optional pattern matching flag for string and character data types
        try:
            pattern = bool(int(entry['PatternMatching']))
        except KeyError:
            self.pattern_matching = False
        except ValueError:
            mod_win2.popup_error('Configuration Error: DataParameter {NAME}: "PatternMatching" must be either 0 '
                                 '(False) or 1 (True)'.format(NAME=self.name))
            sys.exit(1)
        else:
            supported_dtypes = settings.supported_str_dtypes + settings.supported_cat_dtypes
            if self.dtype in supported_dtypes:
                self.pattern_matching = pattern
            else:  # only allow pattern matching for string-like data types
                self.pattern_matching = False

    def element_layout(self, size: tuple = None, bg_col: str = None):
        """
        Create the type-specific layout for the value element of the parameter.
        """
        size = size if size else mod_const.PARAM_SIZE_CHAR

        disabled = False if self.editable is True else True

        pad_el = mod_const.ELEM_PAD
        font = mod_const.LARGE_FONT
        bg_col = mod_const.ACTION_COL if bg_col is None else bg_col
        in_col = mod_const.INPUT_COL
        text_col = mod_const.TEXT_COL

        width, height = size
        elem_w = int(width * 0.7) if self.dtype not in settings.supported_date_dtypes else int((width - 2) * 0.6)
        elem_h = height

        elem_key = self.key_lookup('Element')
        display_value = self.format_display()
        print('initial display value for element {} is {}'.format(self.name, display_value))

        if not disabled:
            layout = [sg.Input(display_value, key=elem_key, size=(elem_w, elem_h), enable_events=True, font=font,
                               background_color=in_col, text_color=text_col,
                               tooltip='Input value for {}'.format(self.description),
                               metadata={'value': display_value, 'disabled': disabled})]

            if self.dtype in settings.supported_date_dtypes:
                calendar_key = self.key_lookup('Calendar')
                date_ico = mod_const.CALENDAR_ICON

                calendar_bttn = sg.CalendarButton('', target=elem_key, key=calendar_key, format='%Y-%m-%d',
                                                  image_data=date_ico, pad=((pad_el, 0), 0), font=font,
                                                  button_color=(text_col, bg_col), border_width=0,
                                                  tooltip='Select date from calendar menu',
                                                  metadata={'disabled': disabled})
                layout.append(calendar_bttn)
        else:
            layout = [sg.Text(display_value, key=elem_key, size=(elem_w, elem_h), font=font, text_color=text_col,
                              background_color=bg_col, border_width=1,
                              metadata={'value': display_value, 'disabled': disabled})]

        return layout

    def query_statement(self, column):
        """
        Generate the filter clause for SQL querying.
        """
        dtype = self.dtype
        pattern = self.pattern_matching

        value = self.value

        if dtype in settings.supported_date_dtypes:
            query_value = self.value.strftime(settings.date_format)
        elif dtype in settings.supported_bool_dtypes:
            query_value = int(value)
        else:
            query_value = value

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
            if dtype in settings.supported_date_dtypes:
                col_values = pd.to_datetime(df[column], errors='coerce', format=settings.date_format)
            elif dtype in settings.supported_int_dtypes:
                col_values = pd.to_numeric(df[column].fillna(0), errors='coerce', downcast='integer')
            elif dtype in settings.supported_float_dtypes:
                col_values = pd.to_numeric(df[column], errors='coerce')
            elif dtype in settings.supported_bool_dtypes:
                col_values = df[column].fillna(False).astype(np.bool, errors='raise')
            else:
                col_values = df[column].astype(np.object, errors='raise')
        except Exception as e:
            logger.exception('DataParameter {NAME}: unable to set column {COL} to parameter data type {DTYPE} - {ERR}'
                         .format(NAME=self.name, COL=column, DTYPE=dtype, ERR=e))
            col_values = df[column]
            print(df[column])

        logger.debug('DataParameter {NAME}: filtering table on value {VAL}'.format(NAME=self.name, VAL=param_value))

        if match_pattern is True:
            df = df[col_values.str.contains(param_value, case=False, regex=True)]
        else:
            df = df[col_values == param_value]

        return df


class DataParameterCombo(DataParameterSingle):
    """
    Dropdown-type data parameter.

    Attributes:
        combo_values (list): list of possible values for the dropdown menu.

        value: value of the parameter's data storage elements.
    """

    def __init__(self, name, entry):
        super().__init__(name, entry)

        # Enforce supported data types for the dropdown parameter
        supported_dtypes = settings.supported_str_dtypes + settings.supported_int_dtypes + settings.supported_cat_dtypes
        if not self.dtype or self.dtype not in supported_dtypes:
            msg = 'unsupported data type {DTYPE} provided for the "{ETYPE}" parameter. Supported data types are ' \
                  '{DTYPES}'.format(ETYPE=self.etype, DTYPE=self.dtype, DTYPES=', '.join(supported_dtypes))
            logger.warning('DataParameter {PARAM}: {MSG}'.format(PARAM=name, MSG=msg))

            self.dtype = 'varchar'

        # Dropdown values
        try:
            combo_values = entry['Values']
        except KeyError:
            msg = 'missing required parameter "Values" for data parameters of type "{ETYPE}"'.format(ETYPE=self.etype)
            mod_win2.popup_notice('Configuration warning: {PARAM}: {MSG}'.format(PARAM=name, MSG=msg))
            logger.warning('DataParameter {PARAM}: {MSG}'.format(PARAM=name, MSG=msg))

            self.combo_values = []
        else:
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

    def element_layout(self, size: tuple = None, bg_col: str = None):
        """
        Create the type-specific layout for the value element of the parameter.
        """
        size = size if size else mod_const.PARAM_SIZE_CHAR
        disabled = False if self.editable is True else True

        # Element settings
        font = mod_const.LARGE_FONT
        bg_col = mod_const.ACTION_COL if bg_col is None else bg_col
        in_col = mod_const.INPUT_COL
        text_col = mod_const.TEXT_COL

        # Parameter size
        width, height = size
        elem_w = int(width * 0.7) if self.dtype not in settings.supported_date_dtypes else int((width - 2) * 0.6)
        elem_h = height

        # Parameter settings
        aliases = self.aliases
        combo_values = self.combo_values
        display_value = self.format_display()
        print('initial display value for element {} is {}'.format(self.name, display_value))

        values = [aliases[i] for i in combo_values if i in aliases]
        if '' not in values:  # the no selection option
            values.insert(0, '')

        elem_key = self.key_lookup('Element')
        if not disabled:
            layout = [sg.Combo(values, default_value=display_value, key=elem_key, size=(elem_w, elem_h), font=font,
                               background_color=in_col, text_color=text_col, enable_events=True,
                               tooltip='Select a value for {}'.format(self.description),
                               metadata={'value': display_value, 'disabled': disabled})]
        else:
            layout = [sg.Text(display_value, key=elem_key, size=(elem_w, elem_h), font=font, text_color=text_col,
                              background_color=bg_col, border_width=1,
                              metadata={'value': display_value, 'disabled': disabled})]

        return layout

    def query_statement(self, column):
        """
        Generate the filter clause for SQL querying.
        """
        dtype = self.dtype
        value = self.value

        if dtype in settings.supported_bool_dtypes:
            query_value = int(value)
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
            if dtype in settings.supported_date_dtypes:
                col_values = pd.to_datetime(df[column], errors='coerce', format=settings.date_format)
            elif dtype in settings.supported_int_dtypes:
                col_values = pd.to_numeric(df[column].fillna(0), errors='coerce', downcast='integer')
            elif dtype in settings.supported_float_dtypes:
                col_values = pd.to_numeric(df[column], errors='coerce')
            elif dtype in settings.supported_bool_dtypes:
                col_values = df[column].fillna(False).astype(np.bool, errors='raise')
            else:
                col_values = df[column].astype(np.object, errors='raise')
        except Exception as e:
            logger.exception('DataParameter {NAME}: unable to set column {COL} to parameter data type {DTYPE} - {ERR}'
                             .format(NAME=self.name, COL=column, DTYPE=dtype, ERR=e))
            col_values = df[column]

        logger.debug('DataParameter {NAME}: filtering table on value {VAL}'.format(NAME=self.name, VAL=param_value))

        df = df[col_values == param_value]

        return df


class DataParameterCheckbox(DataParameterSingle):
    """
    Checkbox parameter element object.

    Attributes:

        name (str): data element configuration name.

        elements (list): list of data element GUI keys.

        value: value of the parameter's data storage elements.
    """

    def __init__(self, name, entry):
        super().__init__(name, entry)

        if pd.isna(self.default):  # the default for checkbox elements is always False if not set in config
            self.default = False

        self.justification = 'right'

        # Data type check
        supported_dtypes = settings.supported_bool_dtypes
        if self.dtype not in supported_dtypes:
            msg = 'unsupported data type {DTYPE} provided for the "{ETYPE}" parameter. Supported data types are ' \
                  '{DTYPES}'.format(ETYPE=self.etype, DTYPE=self.dtype, DTYPES=', '.join(supported_dtypes))
            logger.warning('DataParameter {PARAM}: {MSG}'.format(PARAM=name, MSG=msg))

            self.dtype = 'bool'

    def resize(self, window, size: tuple = None, pixels: bool = True):
        """
        Resize the checkbox parameter elements.
        """
        if size:
            width, height = size
        else:
            width, height = mod_const.PARAM_SIZE_PX if pixels else mod_const.PARAM_SIZE_CHAR

        # Set the parameter width
        width_key = self.key_lookup('Width')
        param_w = width if pixels else width * 10
        window[width_key].set_size(size=(param_w, None))

        # Resize description at 40% of total width and the value element to take up the remaining space
        if pixels:
            desc_w = width - 26
            desc_h = int(height / 10) if height else None
        else:
            desc_w = width - 2
            desc_h = height

        header_key = self.key_lookup('Header')
        window[header_key].set_size(size=(desc_w, desc_h))

#        desc_key = self.key_lookup('Description')
#        window[desc_key].expand(expand_x=True)

    def element_layout(self, size: tuple = None, bg_col: str = None):
        """
        Create the type-specific layout for the value element of the parameter.
        """
        size = size if size else mod_const.PARAM_SIZE_CHAR
        disabled = False if self.editable is True else True

        # Element settings
        bg_col = mod_const.ACTION_COL if bg_col is None else bg_col
        box_col = bg_col if not disabled else mod_const.DISABLED_BG_COL

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
        dtype = self.dtype
        column = self.name

        if not param_value:  # don't filter on NA values or False values
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
                col_values = df[column].fillna(False).astype(np.bool, errors='raise')
            else:
                col_values = df[column].astype(np.object, errors='raise')
        except Exception as e:
            logger.exception('DataParameter {NAME}: unable to set column {COL} to parameter data type {DTYPE} - {ERR}'
                         .format(NAME=self.name, COL=column, DTYPE=dtype, ERR=e))
            col_values = df[column]

        logger.debug('DataParameter {NAME}: filtering table on value {VAL}'.format(NAME=self.name, VAL=param_value))

        df = df[col_values == param_value]

        return df


# Multi-value data parameters
class DataParameterMulti(DataParameter):
    """
    Parent class for data parameters with a multi-value element.

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
        in_col = mod_const.INPUT_COL
        text_col = mod_const.TEXT_COL

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


class DataParameterRange(DataParameterMulti):
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
        element_key = self.key_lookup('Element')
        if event == element_key:
            self.value = mod_win2.range_value_window(self.dtype, current=self.value, title=self.description,
                                                     date_format='YYYY-MM-DD')

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
                msg = 'DataParameter {NAME}: unable to find window values for parameter to update'.format(NAME=self.name)
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
                col_values = df[column].fillna(False).astype(np.bool, errors='raise')
            else:
                col_values = df[column].astype(np.object, errors='raise')
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


class DataParameterCondition(DataParameterMulti):
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
        element_key = self.key_lookup('Element')
        if event == element_key:
            self.value = mod_win2.conditional_value_window(self.dtype, current=self.value, title=self.description)

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
                msg = 'DataParameter {NAME}: unable to find window values for parameter to update'.format(NAME=self.name)
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
            msg = 'DataParameter {NAME}: unknown operator "{OPER}" provided as the first component of the value set'\
                .format(NAME=self.name, OPER=oper)
            logger.warning(msg)

            return self.value

        try:
            value_fmt = settings.format_value(value, self.dtype)
        except ValueError as e:
            msg = 'DataParameter {NAME}: unable set datatype for the conditional value - {ERR}'\
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
                col_values = df[column].astype(np.object, errors='raise')
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


# Multiple Selection parameters
class DataParameterSelection(DataParameter):
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
        element_key = self.key_lookup('Element')

        if event == element_key:
            self.format_value(values)
            self.update_display(window)

    def update_display(self, window):
        """
        Update the parameter display.
        """
        elem_key = self.key_lookup('Element')

        # Update background of selected menu items
        self.update_menu(window)

        # Update element text
        display_value = self.format_display()
        nselect = len(self.value)
        bttn_text = '- Select -' if nselect < 1 else '{} Selected'.format(nselect)
        window[elem_key].set_tooltip(display_value)
        window[elem_key].Widget.configure(text=bttn_text)

    def reset(self, window):
        """
        Reset the parameter's values.
        """
        logger.debug('DataParameter {NAME}: resetting parameter value "{VAL}" to "{DEF}"'
                     .format(NAME=self.name, VAL=self.value, DEF=self.default))
        self.value = self.default

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
        in_col = mod_const.INPUT_COL
        text_col = mod_const.TEXT_COL
        bttn_text_col = mod_const.DISABLED_TEXT_COL

        # Parameter size
        width, height = size
        elem_w = width
        elem_h = height

        # Parameter settings
        menu_values = self.menu_values
        aliases = self.aliases
        menu = ['Menu', [aliases[i] for i in menu_values if i in aliases]]
        display_value = self.format_display()
        print('creating selection menu layout with menu {}'.format(menu))
        print('and initial display value: {}'.format(display_value))

        elem_key = self.key_lookup('Element')
        if not disabled:
            nselect = len(self.value)
            text_font = mod_const.SMALL_FONT
            bttn_text = '- Select -' if nselect < 1 else '{} Selected'.format(nselect)
            layout = [sg.ButtonMenu(bttn_text, menu, key=elem_key, border_width=1, font=text_font, item_font=font,
                                    button_color=(bttn_text_col, in_col), background_color=in_col,
                                    tooltip=display_value)]

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
        current_values = formatted_values = self.value

        if isinstance(values, dict):
            try:
                selected_value = values[self.key_lookup('Element')]
            except KeyError:
                msg = 'DataParameter {NAME}: unable to find window values for parameter to update'.format(NAME=self.name)
                logger.warning(msg)

                return self.value
        else:
            selected_value = values

        if selected_value == '' or pd.isna(selected_value):
            return current_values

        aliases_rev = {j: i for i, j in aliases.items()}
        try:
            value_fmt = aliases_rev[selected_value]
        except KeyError:
            try:
                value_fmt = format_value(selected_value, dtype)
            except ValueError:
                logger.warning('DataParameter {NAME}: failed to format selected value {VAL} as {DTYPE}'
                               .format(NAME=self.name, VAL=selected_value, DTYPE=dtype))
                return current_values

        if value_fmt in current_values:
            formatted_values.remove(value_fmt)
        else:
            formatted_values.append(value_fmt)

        print('selected values are: {}'.format(formatted_values))
        self.value = formatted_values

        return formatted_values

    def format_display(self):
        """
        Format the parameter's value for displaying.
        """
        values = self.value
        aliases = self.aliases

        if all([pd.isna(i) for i in values]):  # no parameter values set for either range element
            return ''

        formatted_values = []
        for value in values:
            if pd.isna(value):
                continue

            try:
                display_value = aliases[value]
            except KeyError:
                display_value = self.format_display_value(value)

            formatted_values.append(display_value)

        return '; '.join(formatted_values)

    def update_menu(self, window):
        """
        Update selected menu items.
        """
        bg_col = mod_const.ACTION_COL
        text_col = mod_const.TEXT_COL
        menu_values = self.menu_values

        bttn_key = self.key_lookup('Element')

        selected_values = self.value
        print('updating selection menu with highlighted values {}'.format(selected_values))
        for menu_index, menu_value in enumerate(menu_values):
            if menu_value in selected_values:
                # Add highlight to menu item
                window[bttn_key].TKMenu.entryconfig(menu_index, foreground=bg_col, background=text_col)
                window[bttn_key].TKButtonMenu.configure(menu=window[bttn_key].TKMenu)
            else:
                # Remove highlight from menu item
                window[bttn_key].TKMenu.entryconfig(menu_index, foreground=text_col, background=bg_col)
                window[bttn_key].TKButtonMenu.configure(menu=window[bttn_key].TKMenu)

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

        if not values:  # don't filter on NA values or False values
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
                col_values = df[column].fillna(False).astype(np.bool, errors='raise')
            else:
                col_values = df[column].astype(np.object, errors='raise')
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
    if etype in ('dropdown', 'combo'):
        param_class = DataParameterCombo
    elif etype in ('input', 'date', 'text'):
        param_class = DataParameterInput
    elif etype in ('range', 'date_range'):
        param_class = DataParameterRange
    elif etype == 'conditional':
        param_class = DataParameterCondition
    elif etype == 'checkbox':
        param_class = DataParameterCheckbox
    elif etype == 'selection':
        param_class = DataParameterSelection
    else:
        msg = 'unknown element type {TYPE} provided to parameter entry {NAME}'.format(TYPE=etype, NAME=name)

        raise TypeError(msg)

    try:
        parameter = param_class(name, entry)
    except AttributeError as e:
        msg = 'failed to initialize parameter {NAME} - {ERR}'.format(NAME=name, ERR=e)

        raise AttributeError(msg)

    return parameter
