"""
REM parameter element classes.
"""
import datetime
import sys
from random import randint

import PySimpleGUI as sg
import pandas as pd

import REM.constants as mod_const
import REM.secondary as mod_win2
from REM.client import logger, settings


class DataParameter:
    """
    GUI data storage element.

    Attributes:

        name (str): data element configuration name.

        id (int): data element number.

        elements (list): list of data element GUI keys.

        description (str): display name of the data element.

        etype (str): GUI element type. Can be dropdown, input, date, date_range, button, or checkbox.

        dtype (str): data type of the parameter's data storage elements [Default: string].

        editable (bool): element is editable. [Default: False]

        hidden (bool): element is not visible to the user. [Default: False]

        required (bool): parameter value is required for an event.

        pattern_matching (bool): query with paramter using pattern matching [Default: False]

        icon (str): file name of the parameter's icon [Default: None].

        value: value of the parameter's data storage elements.
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
                         ['Element', 'Description']]

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
            if self.etype in ('date', 'date_range'):
                if dtype not in settings.supported_date_dtypes:
                    self.dtype = 'datetime'
                else:
                    self.dtype = dtype
            elif self.etype == 'checkbox':
                if dtype not in settings.supported_bool_dtypes:
                    self.dtype = 'bool'
                else:
                    self.dtype = dtype
            else:
                supported_dtypes = settings.get_supported_dtypes()
                if dtype not in supported_dtypes:
                    logger.warning('DataElement {NAME}: "DataType" is not a supported data type - supported data types '
                                   'are {TYPES}'.format(NAME=name, TYPES=', '.join(supported_dtypes)))
                    self.dtype = 'varchar'
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

        try:
            pattern = bool(int(entry['PatternMatching']))
        except KeyError:
            self.pattern_matching = False
        except ValueError:
            mod_win2.popup_error('Configuration Error: DataParameter {NAME}: "PatternMatching" must be either 0 '
                                 '(False) or 1 (True)'.format(NAME=self.name))
            sys.exit(1)
        else:
            self.pattern_matching = pattern

        try:
            self.icon = entry['Icon']
        except KeyError:
            self.icon = None

        try:
            self.justification = entry['Justification']
        except KeyError:
            self.justification = 'left'

        try:
            self.default = entry['DefaultValue']
        except KeyError:
            self.default = None

        self.value = None
        self.bg_col = mod_const.ACTION_COL

    def key_lookup(self, component):
        """
        Lookup an element's component GUI key using the name of the component element.
        """
        element_names = [i[1:-1].split('_')[-1] for i in self.elements]
        if component in element_names:
            key_index = element_names.index(component)
            key = self.elements[key_index]
        else:
            msg = 'DataParameter {NAME}: parameter element {COMP} not found in list of parameter elements'\
                .format(COMP=component, NAME=self.name)
            logger.warning(msg)
            key = None

        return key

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

        value = values[elem_key]
        logger.debug('DataParameter {PARAM}: enforcing correct formatting of input value {VAL}'
                     .format(PARAM=self.name, VAL=value))

        if value == '' or value is None or pd.isna(value):
            return ''

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

                    display_value = self.format_date(''.join(current_value))
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

                display_value = self.format_date(current_value)
            else:
                display_value = self.format_date(current_value)

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

    def format_date(self, date_str):
        """
        Forces user input to date element to be in ISO format.
        """
        buff = []
        for index, char in enumerate(date_str):
            if index == 3:
                if len(date_str) != 4:
                    buff.append('{}-'.format(char))
                else:
                    buff.append(char)
            elif index == 5:
                if len(date_str) != 6:
                    buff.append('{}-'.format(char))
                else:
                    buff.append(char)
            else:
                buff.append(char)

        return ''.join(buff)

    def toggle_parameter(self, window, value: str = 'enable'):
        """
        Toggle parameter elements on and off.
        """
        status = False if value == 'enable' else True

        element_key = self.key_lookup('Element')
        logger.debug('DataParameter {NAME}: updating element to "disabled={VAL}"'
                     .format(NAME=self.name, VAL=status))

        window[element_key].update(disabled=status)

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

        if query_value:
            if pattern is True:
                query_value = '%{VAL}%'.format(VAL=query_value)
                statement = ('{COL} LIKE ?'.format(COL=column), (query_value,))
            else:
                statement = ('{COL} = ?'.format(COL=column), (query_value,))
        else:
            statement = None

        return statement


class DataParameterInput(DataParameter):
    """
    Input-style parameter.
    """
    def __init__(self, name, entry):
        super().__init__(name, entry)

        # Dynamic attributes
        self.value = self.format_value({self.key_lookup('Element'): self.default})
        logger.debug('DataParameter {PARAM}: initializing {ETYPE} parameter of data type {DTYPE} with default '
                     'value {DEF}, and formatted value {VAL}'
                     .format(PARAM=self.name, ETYPE=self.etype, DTYPE=self.dtype, DEF=self.default, VAL=self.value))

    def reset(self, window):
        """
        Reset the parameter's values.
        """
        if not pd.isna(self.value) and not pd.isna(self.default):
            logger.debug('DataParameter {NAME}: resetting parameter value "{VAL}" to "{DEF}"'
                         .format(NAME=self.name, VAL=self.value, DEF=self.default))

        # Update the parameter window element
        if self.hidden is False:
            self.value = self.format_value({self.key_lookup('Element'): self.default})
            display_value = self.format_display()

            window[self.key_lookup('Element')].update(value=display_value)

    def layout(self, size: tuple = (14, 1), padding: tuple = (0, 0), bg_col: str = mod_const.ACTION_COL):
        """
        Create a GUI layout for the parameter.
        """
        self.bg_col = bg_col

        # Element settings
        pad_el = mod_const.ELEM_PAD

        font = mod_const.LARGE_FONT
        bold_font = mod_const.BOLD_FONT

        in_col = mod_const.INPUT_COL

        # Parameter settings
        desc = '{}:'.format(self.description)
        param_value = self.format_display()
        icon = self.icon

        # Icon layout
        if icon is None:
            icon_layout = []
        else:
            icon_path = settings.get_icon_path(icon)
            if icon_path is not None:
                icon_layout = [sg.Image(filename=icon_path, pad=((0, pad_el), 0), background_color=bg_col)]
            else:
                icon_layout = []

        # Element layout
        elem_key = self.key_lookup('Element')
        desc_key = self.key_lookup('Description')
        if self.editable is True:
            param_layout = [sg.Text(desc, key=desc_key, auto_size_text=True, pad=((0, pad_el), 0), font=bold_font,
                                    background_color=bg_col),
                            sg.Input(param_value, key=elem_key, size=size, enable_events=True, font=font,
                                     background_color=in_col, tooltip='Input value for {}'.format(self.description),
                                     metadata={'value': param_value, 'disabled': False})]
        else:
            param_layout = [sg.Text(desc, key=desc_key, auto_size_text=True, pad=((0, pad_el), 0), font=bold_font,
                                    background_color=bg_col),
                            sg.Text(param_value, key=elem_key, size=size, font=font, background_color=bg_col,
                                    border_width=1)]

        layout = [icon_layout + param_layout]

        return [sg.Col(layout, pad=padding, background_color=bg_col, visible=(not self.hidden))]

    def format_value(self, values):
        """
        Set the value of the data element from user input.

        Arguments:

            values (dict): GUI element values.
        """
        group_sep = settings.thousands_sep
        dtype = self.dtype

        try:
            input_value = values[self.key_lookup('Element')]
        except KeyError:
            logger.warning('DataParameter {NAME}: unable to find window values for parameter to update'
                           .format(NAME=self.name))
            return self.value
        else:
            if input_value is None:
                return None

        if dtype in settings.supported_float_dtypes:
            try:
                value_fmt = float(input_value)
            except (ValueError, TypeError):
                try:
                    value_fmt = float(input_value.replace(group_sep, ''))
                except (ValueError, TypeError, AttributeError):
                    logger.warning('DataParameter {PARAM}: unknown object type for parameter value {VAL}'
                                   .format(PARAM=self.name, VAL=input_value))
                    return None
        elif dtype in settings.supported_int_dtypes:
            try:
                value_fmt = int(input_value)
            except (ValueError, TypeError, AttributeError):
                try:
                    value_fmt = input_value.replace(',', '')
                except (ValueError, TypeError):
                    logger.warning('DataParameter {PARAM}: unknown object type for parameter value {VAL}'
                                   .format(PARAM=self.name, VAL=input_value))
                    return None
        elif dtype in settings.supported_bool_dtypes:
            if isinstance(input_value, bool):
                value_fmt = input_value
            else:
                try:
                    value_fmt = bool(int(input_value))
                except (ValueError, TypeError):
                    value_fmt = bool(input_value)
        else:
            value_fmt = str(input_value)

        return value_fmt

    def format_display(self):
        """
        Format the parameter's value for displaying.
        """
        dec_sep = settings.decimal_sep
        group_sep = settings.thousands_sep

        dtype = self.dtype
        value = self.value

        if value == '' or pd.isna(value) is True:
            return ''
        else:
            value = str(value)

        logger.debug('DataParameter {NAME}: formatting parameter value "{VAL}" for display'
                     .format(NAME=self.name, VAL=value))
        if dtype in settings.supported_float_dtypes and dtype == 'money':
            if value[0] in ('-', '+'):  # sign of the number
                numeric_sign = value[0]
                value = value[1:]
            else:
                numeric_sign = ''
            if dec_sep in value:
                integers, decimals = value.split(dec_sep)
                decimals = decimals[0:2]
                display_value = '{SIGN}{VAL}{SEP}{DEC}'\
                    .format(SIGN=numeric_sign, VAL=''.join([group_sep * (n % 3 == 2) + i for n, i in
                                                            enumerate(integers[::-1])][::-1]).lstrip(','),
                            SEP=dec_sep, DEC=decimals)
            else:
                display_value = '{SIGN}{VAL}'\
                    .format(SIGN=numeric_sign, VAL=''.join([group_sep * (n % 3 == 2) + i for n, i in
                                                            enumerate(value[::-1])][::-1]).lstrip(','))

        elif dtype in settings.supported_float_dtypes and dtype != 'money':
            try:
                new_value = float(value)
            except ValueError:
                display_value = value
            else:
                display_value = str(new_value)

        elif dtype in settings.supported_int_dtypes:
            try:
                new_value = int(value)
            except ValueError:
                display_value = value
            else:
                display_value = str(new_value)

        else:
            display_value = str(value)

        return display_value

    def print_value(self):
        """
        Generate printable statement of the parameter's value.
        """
        formatted_value = self.format_display()

        return formatted_value


class DataParameterCombo(DataParameter):
    """
    DropDown-style parameter.
    """

    def __init__(self, name, entry):
        super().__init__(name, entry)
        try:
            self.combo_values = entry['Values']
        except KeyError:
            msg = _('Configuration Warning: DataParameter {PARAM}: values required for parameter type '
                    '"dropdown"').format(PARAM=name)
            mod_win2.popup_notice(msg)

            self.combo_values = []

        try:
            aliases = entry['Aliases']
        except KeyError:
            self.aliases = {i: i for i in self.combo_values}
        else:
            for value in self.combo_values:
                if value not in aliases:
                    aliases[value] = value
            self.aliases = aliases

        self.value = self.format_value({self.key_lookup('Element'): self.default})
        logger.debug('DataParameter {PARAM}: initializing {ETYPE} parameter of data type {DTYPE} with default value '
                     '{DEF}, and formatted value {VAL}'
                     .format(PARAM=self.name, ETYPE=self.etype, DTYPE=self.dtype, DEF=self.default, VAL=self.value))

    def reset(self, window):
        """
        Reset the parameter's values.
        """
        if not pd.isna(self.value) and not pd.isna(self.default):
            logger.debug('DataParameter {NAME}: resetting parameter value "{VAL}" to "{DEF}"'
                         .format(NAME=self.name, VAL=self.value, DEF=self.default))

        # Update the parameter window element
        if self.hidden is False:
            self.value = self.format_value({self.key_lookup('Element'): self.default})
            display_value = self.format_display()

            window[self.key_lookup('Element')].update(value=display_value)

    def layout(self, size: tuple = None, padding: tuple = (0, 0), bg_col: str = mod_const.ACTION_COL):
        """
        Create a GUI layout for the parameter.
        """
        self.bg_col = bg_col

        # Element settings
        pad_el = mod_const.ELEM_PAD

        font = mod_const.LARGE_FONT
        bold_font = mod_const.BOLD_FONT

        in_col = mod_const.INPUT_COL

        # Parameter settings
        aliases = self.aliases
        combo_values = self.combo_values
        icon = self.icon

        elem_key = self.key_lookup('Element')
        desc_key = self.key_lookup('Description')
        desc = '{}:'.format(self.description)
        values = [aliases[i] for i in combo_values if i in aliases]
        if '' not in values:  # the no selection option
            values.insert(0, '')

        param_value = self.format_display()

        # Icon layout
        if icon is None:
            icon_layout = []
        else:
            icon_path = settings.get_icon_path(icon)
            if icon_path is not None:
                icon_layout = [sg.Image(filename=icon_path, pad=((0, pad_el), 0), background_color=bg_col)]
            else:
                icon_layout = []

        # Parameter size
        width = max([len(i) for i in values]) + 1
        size = (width, 1) if size is None else size

        # Element layout
        if self.editable is True:
            param_layout = [sg.Text(desc, key=desc_key, auto_size_text=True, pad=((0, pad_el), 0), font=bold_font,
                                    background_color=bg_col),
                            sg.Combo(values, default_value=param_value, key=elem_key, size=size, font=font,
                                     background_color=in_col, enable_events=True,
                                     tooltip='Select a value for {}'.format(self.description),
                                     metadata={'value': param_value, 'disabled': False})]
        else:
            param_layout = [sg.Text(desc, key=desc_key, auto_size_text=True, pad=((0, pad_el), 0), font=bold_font,
                                    background_color=bg_col),
                            sg.Text(param_value, key=elem_key, size=size, font=font, background_color=bg_col,
                                    border_width=1)]

        layout = [icon_layout + param_layout]

        return [sg.Col(layout, pad=padding, background_color=bg_col, visible=(not self.hidden))]

    def format_value(self, values):
        """
        Set the value of the data element from user input.

        Arguments:

            values (dict): GUI element values.
        """
        try:
            input_value = values[self.key_lookup('Element')]
        except KeyError:
            logger.warning('DataParameter {NAME}: unable to find window values for parameter to update'
                           .format(NAME=self.name))
            return self.value

        aliases = {j: i for i, j in self.aliases.items()}
        value_fmt = aliases.get(input_value, input_value)

        return value_fmt

    def format_display(self):
        """
        Format the parameter's value for displaying.
        """
        value = self.value
        aliases = self.aliases

        if pd.isna(value) is True:
            return ''

        display_value = aliases.get(value, value)

        return display_value

    def print_value(self):
        """
        Generate printable statement of the parameter's value.
        """
        formatted_value = self.format_display()

        return formatted_value


class DataParameterDate(DataParameter):
    """
    Date-style parameter.
    """

    def __init__(self, name, entry):
        super().__init__(name, entry)
        self.elements.append('-{NAME}_{ID}_{ELEM}-'.format(NAME=self.name, ID=self.id, ELEM='Calendar'))

        self.value = self.format_value({self.key_lookup('Element'): self.default})
        logger.debug('DataParameter {PARAM}: initializing {ETYPE} parameter of data type {DTYPE} with default value '
                     '{DEF}, and formatted value {VAL}'
                     .format(PARAM=self.name, ETYPE=self.etype, DTYPE=self.dtype, DEF=self.default, VAL=self.value))

    def reset(self, window):
        """
        Reset the parameter's values.
        """
        if not pd.isna(self.value) and not pd.isna(self.default):
            logger.debug('DataParameter {NAME}: resetting parameter value "{VAL}" to "{DEF}"'
                         .format(NAME=self.name, VAL=self.value, DEF=self.default))

        # Update the parameter window element
        if self.hidden is False:
            self.value = self.format_value({self.key_lookup('Element'): self.default})
            display_value = self.format_display()

            window[self.key_lookup('Element')].update(value=display_value)

    def layout(self, size: tuple = (14, 1), padding: tuple = (0, 0), bg_col: str = mod_const.ACTION_COL):
        """
        Create a GUI layout for the parameter.
        """
        self.bg_col = bg_col

        # Element settings
        pad_el = mod_const.ELEM_PAD

        date_ico = mod_const.CALENDAR_ICON
        font = mod_const.LARGE_FONT
        bold_font = mod_const.BOLD_FONT

        in_col = mod_const.INPUT_COL

        # Parameter settings
        desc = '{}:'.format(self.description)
        param_value = self.format_display()
        icon = self.icon

        # Icon layout
        if icon is None:
            icon_layout = []
        else:
            icon_path = settings.get_icon_path(icon)
            if icon_path is not None:
                icon_layout = [sg.Image(filename=icon_path, pad=((0, pad_el), 0), background_color=bg_col)]
            else:
                icon_layout = []

        # Element layout
        input_key = self.key_lookup('Element')
        desc_key = self.key_lookup('Description')
        calendar_key = self.key_lookup('Calendar')
        if self.editable is True:
            param_layout = [sg.Text(desc, key=desc_key, auto_size_text=True, pad=((0, pad_el), 0), font=bold_font,
                                    background_color=bg_col),
                            sg.Input(param_value, key=input_key, size=size, enable_events=True, pad=((0, pad_el), 0),
                                     font=font, background_color=in_col, disabled=False,
                                     tooltip='Input date as YYYY-MM-DD or use the calendar button to select the date',
                                     metadata={'value': param_value, 'disabled': False}),
                            sg.CalendarButton('', target=input_key, key=calendar_key, format='%Y-%m-%d',
                                              image_data=date_ico, font=font, border_width=0,
                                              tooltip='Select date from calendar menu')]
        else:
            param_layout = [sg.Text(desc, key=desc_key, auto_size_text=True, pad=((0, pad_el), 0), font=bold_font,
                                    background_color=bg_col),
                            sg.Text(param_value, key=input_key, size=size, font=font, background_color=bg_col,
                                    border_width=1, metadata={'value': param_value, 'disabled': True})]

        layout = [icon_layout + param_layout]

        return [sg.Col(layout, pad=padding, background_color=bg_col, visible=(not self.hidden))]

    def format_value(self, values):
        """
        Set the value of the data element from user input.

        Arguments:

            values (dict): GUI element values.
        """
        strptime = datetime.datetime.strptime

        try:
            input_value = values[self.key_lookup('Element')]
        except KeyError:
            logger.warning('DataParameter {NAME}: unable to find window values for parameter to update'
                           .format(NAME=self.name))
            return self.value

        if not input_value:
            return None

        if isinstance(input_value, str):
            try:
                value_fmt = strptime(input_value, '%Y-%m-%d')
            except (ValueError, TypeError):
                logger.warning('DataParameter {NAME}: unable to parse date {VAL}'
                               .format(NAME=self.name, VAL=input_value))
                value_fmt = None
        elif isinstance(input_value, datetime.datetime):
            value_fmt = input_value
        else:
            logger.warning('DataParameter {NAME}: unknown object type for {VAL}'
                           .format(NAME=self.name, VAL=input_value))
            value_fmt = None

        return value_fmt

    def format_display(self):
        """
        Format the parameter's value for displaying.
        """
        value = self.value
        if pd.isna(value) is True:
            return ''

        if isinstance(value, str):
            logger.warning('DataParameter {NAME}: unknown object type {TYPE} provided for parameter value {VAL}'
                           .format(NAME=self.name, TYPE=type(value), VAL=value))
            value_fmt = value
        elif isinstance(value, datetime.datetime):
            value_fmt = settings.format_display_date(value)
        else:
            logger.warning('DataParameter {NAME}: unknown object type {TYPE} provided for parameter value {VAL}'
                           .format(NAME=self.name, TYPE=type(value), VAL=value))
            value_fmt = None

        return value_fmt

    def print_value(self):
        """
        Generate printable statement of the parameter's value.
        """
        formatted_value = self.format_display()

        return formatted_value.replace('-', '')

    def toggle_parameter(self, window, value: str = 'enable'):
        """
        Toggle parameter elements on and off.
        """
        status = False if value == 'enable' else True

        logger.debug('DataParameter {NAME}: setting elements to "disabled={VAL}"'
                     .format(NAME=self.name, VAL=status))

        element_key = self.key_lookup('Element')
        calendar_key = self.key_lookup('Calendar')

        window[element_key].update(disabled=status)
        window[calendar_key].update(disabled=status)


class DataParameterDateRange(DataParameter):
    """
    Date parameter element object.
    """

    def __init__(self, name, entry):
        super().__init__(name, entry)
        self.elements.append('-{NAME}_{ID}_{ELEM}-'.format(NAME=self.name, ID=self.id, ELEM='Calendar'))
        self.elements.append('-{NAME}_{ID}_{ELEM}-'.format(NAME=self.name, ID=self.id, ELEM='Element2'))
        self.elements.append('-{NAME}_{ID}_{ELEM}-'.format(NAME=self.name, ID=self.id, ELEM='Calendar2'))

        try:
            self.value = self.format_value({self.key_lookup('Element'): self.default[0],
                                            self.key_lookup('Element2'): self.default[1]})
        except (IndexError, TypeError):
            self.value = self.format_value({self.key_lookup('Element'): self.default,
                                            self.key_lookup('Element2'): self.default})
        logger.debug('DataParameter {NAME}: initializing {ETYPE} parameter of data type {DTYPE} with default value '
                     '{DEF}, and formatted value {VAL}'
                     .format(NAME=self.name, ETYPE=self.etype, DTYPE=self.dtype, DEF=self.default, VAL=self.value))

    def reset(self, window):
        """
        Reset the parameter's values.
        """
        try:
            def_val1, def_val2 = self.default
        except (ValueError, TypeError):
            def_val1 = def_val2 = None

        if def_val1 is not None or def_val2 is not None:
            logger.debug('DataParameter {NAME}: resetting parameter value "{VAL}" to "{DEF}"'
                         .format(NAME=self.name, VAL=self.value, DEF=self.default))

        # Update the parameter window element
        if self.hidden is False:
            self.value = self.format_value({self.key_lookup('Element'): def_val1,
                                            self.key_lookup('Element2'): def_val2})
            display_val1, display_val2 = self.format_display()
            print('resetting parameter {} to {} and {}'.format(self.name, display_val1, display_val2))

            window[self.key_lookup('Element')].update(value=display_val1)
            window[self.key_lookup('Element2')].update(value=display_val2)

    def layout(self, size: tuple = (14, 1), padding: tuple = (0, 0), bg_col: str = mod_const.ACTION_COL):
        """
        Create a GUI layout for the parameter.
        """
        self.bg_col = bg_col

        # Element settings
        pad_el = mod_const.ELEM_PAD

        date_ico = mod_const.CALENDAR_ICON
        font = mod_const.LARGE_FONT
        bold_font = mod_const.BOLD_FONT

        in_col = mod_const.INPUT_COL

        # Parameter settings
        try:
            from_desc, to_desc = self.description
        except ValueError:
            from_desc = to_desc = self.description

        from_value, to_value = self.format_display()
        icon = self.icon

        # Icon layout
        if icon is None:
            icon_layout = []
        else:
            icon_path = settings.get_icon_path(icon)
            if icon_path is not None:
                icon_layout = [sg.Image(filename=icon_path, pad=((0, pad_el), 0), background_color=bg_col)]
            else:
                icon_layout = []

        # Element layout
        desc_key = self.key_lookup('Description')
        from_key = self.key_lookup('Element')
        from_date_key = self.key_lookup('Calendar')
        to_key = self.key_lookup('Element2')
        to_date_key = self.key_lookup('Calendar2')
        if self.editable is True:
            layout = [
                sg.Col([icon_layout +
                        [sg.Text('{}:'.format(from_desc), key=desc_key, auto_size_text=True, pad=((0, pad_el), 0),
                                 font=bold_font, background_color=bg_col),
                         sg.Input(from_value, key=from_key, size=size, enable_events=True, pad=((0, pad_el), 0),
                                  font=font, background_color=in_col,
                                  tooltip='Input date as YYYY-MM-DD or use the calendar button to select the date',
                                  metadata={'value': [], 'disabled': False}),
                         sg.CalendarButton('', target=from_key, key=from_date_key, format='%Y-%m-%d',
                                           image_data=date_ico, font=font, border_width=0,
                                           tooltip='Select date from calendar menu')]],
                       pad=padding, background_color=bg_col, visible=(not self.hidden)),
                sg.Col([icon_layout +
                        [sg.Text('{}:'.format(to_desc), auto_size_text=True, pad=((0, pad_el), 0),
                                 font=bold_font, background_color=bg_col),
                         sg.Input(to_value, key=to_key, size=size, enable_events=True, pad=((0, pad_el), 0),
                                  font=font, background_color=in_col, disabled=False,
                                  tooltip='Input date as YYYY-MM-DD or use the calendar button to select the date',
                                  metadata={'value': [], 'disabled': False}),
                         sg.CalendarButton('', target=to_key, key=to_date_key, format='%Y-%m-%d', image_data=date_ico,
                                           font=font, border_width=0, tooltip='Select date from calendar menu')]],
                       pad=padding, background_color=bg_col, visible=(not self.hidden))]
        else:
            layout = [
                sg.Col([icon_layout +
                        [sg.Text(from_desc, key=desc_key, auto_size_text=True, pad=((0, pad_el), 0), font=bold_font,
                                 background_color=bg_col),
                         sg.Text(from_value, key=from_key, size=size, font=font, background_color=bg_col,
                                 border_width=1, metadata={'value': [], 'disabled': True})]],
                       pad=padding, background_color=bg_col, visible=(not self.hidden)),
                sg.Col([icon_layout +
                        [sg.Text(to_desc, auto_size_text=True, pad=((0, pad_el), 0), font=bold_font,
                                 background_color=bg_col),
                         sg.Text(to_value, key=to_key, size=size, font=font,
                                 background_color=bg_col, border_width=1, metadata={'value': [], 'disabled': True})]],
                       pad=padding, background_color=bg_col, visible=(not self.hidden))]

        return layout

    def format_value(self, values):
        """
        Set the value of the data element from user input.

        Arguments:

            values (dict): GUI element values.
        """
        strptime = datetime.datetime.strptime

        try:
            input_values = (values[self.key_lookup('Element')], values[self.key_lookup('Element2')])
        except KeyError:
            logger.warning('DataParameter {NAME}: unable to find window values for parameter to update'
                           .format(NAME=self.name))
            return self.value

        formatted_values = []
        for input_value in input_values:
            if not input_value:
                formatted_values.append(None)
                continue

            if isinstance(input_value, str):
                try:
                    value_fmt = strptime(input_value, '%Y-%m-%d')
                except (ValueError, TypeError):
                    logger.warning('DataParameter {PARAM}: unable to parse date {VAL}'
                                   .format(PARAM=self.name, VAL=input_value))
                    value_fmt = None
            elif isinstance(input_value, datetime.datetime):
                value_fmt = input_value
            else:
                logger.warning('DataParameter {PARAM}: unknown object type for {VAL}'
                               .format(PARAM=self.name, VAL=input_value))
                value_fmt = None

            formatted_values.append(value_fmt)

        return formatted_values

    def format_display(self):
        """
        Format the parameter's value for displaying.
        """
        values = self.value
        if pd.isna(values) is True:
            return ('', '')

        formatted_values = []
        for value in values:
            if value is None:
                formatted_values.append('')
                continue

            if isinstance(value, str):
                value_fmt = value
            elif isinstance(value, datetime.datetime):
                value_fmt = value.strftime('%Y-%m-%d')
            else:
                logger.warning('DataParameter {PARAM}: unknown object type for parameter value {VAL}'
                               .format(PARAM=self.name, VAL=value))
                value_fmt = ''

            formatted_values.append(value_fmt)

        return formatted_values

    def print_value(self):
        """
        Generate printable statement of the parameter's value.
        """
        formatted_values = self.format_display()

        nvals = len(formatted_values)
        if nvals == 0:
            return ''
        elif nvals == 1:
            return formatted_values[0].replace('-', '')
        elif nvals == 2:
            formatted_values = [i.replace('-', '') for i in formatted_values]
            return '{}-{}'.format(*formatted_values)
        else:
            return ''

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

    def toggle_parameter(self, window, value: str = 'enable'):
        """
        Toggle parameter elements on and off.
        """
        status = False if value == 'enable' else True

        logger.debug('DataParameter {NAME}: updating elements to "disabled={VAL}"'
                     .format(NAME=self.name, VAL=status))

        element_key = self.key_lookup('Element')
        calendar_key = self.key_lookup('Calendar')
        element2_key = self.key_lookup('Element2')
        calendar2_key = self.key_lookup('Calendar2')

        window[element_key].update(disabled=status)
        window[calendar_key].update(disabled=status)
        window[element2_key].update(disabled=status)
        window[calendar2_key].update(disabled=status)


class DataParameterCheckbox(DataParameter):
    """
    Checkbox parameter element object.
    """

    def __init__(self, name, entry):
        super().__init__(name, entry)

        if self.default is None:
            self.default = False

        self.value = self.format_value({self.key_lookup('Element'): self.default})
        logger.debug('DataParameter {NAME}: initializing {ETYPE} parameter of data type {DTYPE} with default value '
                     '{DEF}, formatted value {VAL}'
                     .format(NAME=self.name, ETYPE=self.etype, DTYPE=self.dtype, DEF=self.default, VAL=self.value))

    def reset(self, window):
        """
        Reset the parameter's values.
        """
        if not pd.isna(self.value) and not pd.isna(self.default):
            logger.debug('DataParameter {NAME}: resetting parameter value "{VAL}" to "{DEF}"'
                         .format(NAME=self.name, VAL=self.value, DEF=self.default))

        # Update the parameter window element
        if self.hidden is False:
            self.value = self.format_value({self.key_lookup('Element'): self.default})
            display_value = self.format_display()

            window[self.key_lookup('Element')].update(value=display_value)

    def layout(self, size: tuple = None, padding: tuple = (0, 0), bg_col: str = mod_const.ACTION_COL):
        """
        Create a GUI layout for the parameter.
        """
        self.bg_col = bg_col

        bold_font = mod_const.BOLD_FONT

        key = self.key_lookup('Element')
        desc_key = self.key_lookup('Description')
        desc = self.description
        disabled = False if self.editable is True else True

        # Element settings
        pad_el = mod_const.ELEM_PAD

        # Parameter settings
        try:
            param_value = bool(int(self.value))
        except (ValueError, TypeError):
            param_value = bool(self.value)
        icon = self.icon

        # Icon layout
        if icon is None:
            icon_layout = []
        else:
            icon_path = settings.get_icon_path(icon)
            if icon_path is not None:
                icon_layout = [sg.Image(filename=icon_path, pad=((0, pad_el), 0), background_color=bg_col)]
            else:
                icon_layout = []

        # Parameter layout
        param_layout = [sg.Text('', key=desc_key, background_color=bg_col),
                        sg.Checkbox(desc, default=param_value, key=key, pad=padding, font=bold_font,
                                    enable_events=True, background_color=bg_col, disabled=disabled)]

        layout = [icon_layout + param_layout]

        return [sg.Col(layout, pad=padding, background_color=bg_col, visible=(not self.hidden))]

    def format_value(self, values):
        """
        Set the value of the parameter element from user input.

        Arguments:

            values (dict): GUI element values.
        """
        try:
            input_value = values[self.key_lookup('Element')]
        except KeyError:
            msg = 'DataParameter {NAME}: unable to find window values for parameter to update'.format(NAME=self.name)
            logger.warning(msg)
            return self.value

        if pd.isna(input_value):
            value_fmt = False
        else:
            try:
                value_fmt = bool(int(input_value))
            except (ValueError, TypeError):
                value_fmt = bool(input_value)

        self.value = value_fmt

        return value_fmt

    def format_display(self):
        """
        Format the parameter's value for displaying.
        """
        return self.value

    def print_value(self):
        """
        Generate printable statement of the parameter's value.
        """
        formatted_value = self.format_display()

        return formatted_value
