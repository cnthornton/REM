"""
REM parameter element classes.
"""
import sys

import datetime
import pandas as pd
import PySimpleGUI as sg
from random import randint

import REM.constants as mod_const
import REM.secondary as mod_win2
from REM.config import configuration, settings


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
        self.elements = ['-{NAME}_{ID}_{ELEM}-'.format(NAME=self.name, ID=self.id, ELEM=i) for i in ['Element']]

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
            self.dtype = entry['DataType']
        except KeyError:
            self.dtype = 'string'

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
            self.icon = entry['Icon']
        except KeyError:
            self.icon = None

        try:
            self.default = entry['DefaultValue']
        except KeyError:
            self.default = None

        self.value = None

    def key_lookup(self, component):
        """
        Lookup an element's component GUI key using the name of the component element.
        """
        element_names = [i[1:-1].split('_')[-1] for i in self.elements]
        if component in element_names:
            key_index = element_names.index(component)
            key = self.elements[key_index]
        else:
            print('Warning: DataParameter {NAME}: component {COMP} not found in list of data element components'
                  .format(COMP=component, NAME=self.name))
            key = None

        return key

    def run_event(self, window, event, values, user):
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
        print('Info: parameter {PARAM}: enforcing correct formatting of input value {VAL}'
              .format(PARAM=self.name, VAL=value))

        if value == '' or value is None or pd.isna(value):
            return ''

        elem_key = self.key_lookup('Element')

        if dtype in ('date', 'datetime', 'timestamp', 'time', 'year'):
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
                    print('Warning: {}'.format(msg))

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

        elif dtype == 'money':
            current_value = list(window[elem_key].metadata['value'])
            print(current_value)

            # Remove currency and grouping separator
            #            new_value = value[len(currency_sym):].replace(group_sep, '')
            new_value = list(value.replace(group_sep, ''))
            print(new_value)

            if len(current_value) > len(new_value):  # user removed a character
                print('removing a character')
                # Remove the decimal separator if last character is decimal
                if new_value[-1] == dec_sep:
                    print('removing decimal')
                    current_value = new_value[0:-1]
                else:
                    current_value = new_value
            elif len(current_value) < len(new_value):  # user added new character
                print('adding a character')
                # Find the character and location of the user input
                new_char = new_value[-1]  # defaults to the last character
                new_index = len(new_value)  # defaults to the end of the string
                for index, old_char in enumerate(current_value):
                    character = new_value[index]
                    if old_char != character:
                        new_char = character
                        new_index = index
                        break

                print(new_char, new_index)

                # Validate added character
                if new_char.isnumeric():  # can add integers
                    print('inserting new character {} at index {}'.format(new_char, new_index))
                    current_value.insert(new_index, new_char)
                elif new_char == dec_sep:  # and also decimal character
                    if dec_sep not in current_value:  # can only add one decimal character
                        print('inserting new character {} at index {}'.format(new_char, new_index))
                        current_value.insert(new_index, new_char)
            else:  # user replaced a character
                print('replacing a character')
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

            current_value = ''.join(current_value)
            if dec_sep in current_value:
                integers, decimals = current_value.split(dec_sep)
                decimals = decimals[0:2]
                current_value = integers + dec_sep + decimals[0:2]
                display_value = ''.join([group_sep * (n % 3 == 2) + i
                                         for n, i in enumerate(integers[::-1])][::-1]).lstrip(',') + dec_sep + decimals
            else:
                display_value = ''.join([group_sep * (n % 3 == 2) + i
                                         for n, i in enumerate(current_value[::-1])][::-1]).lstrip(',')

            window[elem_key].metadata['value'] = current_value

        elif dtype in ('float', 'decimal', 'dec', 'double', 'numeric'):
            current_value = window[elem_key].metadata['value']
            try:
                float(value)
            except ValueError:
                display_value = current_value
            else:
                display_value = value

            window[elem_key].metadata['value'] = display_value

        elif dtype in ('int', 'integer', 'bit'):
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

    def reset(self, window):
        """
        Reset the parameter's values.
        """
        print('Info: DataParameter {NAME}: resetting parameter value {VAL} to {DEF}'
              .format(NAME=self.name, VAL=self.value, DEF=self.default))

        self.value = None

        # Update the parameter window element
        if self.hidden is False:
            window[self.key_lookup('Element')].update(value='')

    def toggle_parameter(self, window, value: str = 'enable'):
        """
        Toggle parameter elements on and off.
        """
        status = False if value == 'enable' else True

        element_key = self.key_lookup('Element')
        print('Info: DataParameter {NAME}: updating element to "disabled={VAL}"'
              .format(NAME=self.name, VAL=status))

        window[element_key].update(disabled=status)

    def query_statement(self, column):
        """
        Generate the filter clause for SQL querying.
        """
        dtype = self.dtype

        value = self.value
        if dtype in ('date', 'datetime', 'timestamp', 'time', 'year'):
            query_value = self.value.strftime(configuration.date_format)
        elif dtype in ('bool', 'boolean'):
            query_value = int(value)
        else:
            query_value = value

        if query_value is not None:
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
        print('Info: {PARAM}: initializing {ETYPE} parameter of data type {DTYPE} with default value {DEF}, formatted '
              'value {VAL}, and display value {DIS}'.format(PARAM=self.name, ETYPE=self.etype, DTYPE=self.dtype,
                                                            DEF=self.default, VAL=self.value, DIS=self.format_display()))

    def layout(self, size: tuple = (14, 1), padding: tuple = (0, 0), bg_col: str = mod_const.ACTION_COL):
        """
        Create a GUI layout for the parameter.
        """
        # Element settings
        pad_el = mod_const.ELEM_PAD

        font = mod_const.MID_FONT
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
            icon_path = configuration.get_icon_path(icon)
            if icon_path is not None:
                icon_layout = [sg.Image(filename=icon_path, pad=((0, pad_el), 0), background_color=bg_col)]
            else:
                icon_layout = []

        # Element layout
        elem_key = self.key_lookup('Element')
        if self.editable is True:
            param_layout = [sg.Text(desc, auto_size_text=True, pad=((0, pad_el), 0), font=bold_font,
                                    background_color=bg_col),
                            sg.Input(param_value, key=elem_key, size=size, enable_events=True, font=font,
                                     background_color=in_col, tooltip='Input value for {}'.format(self.description),
                                     metadata={'value': param_value, 'disabled': False})]
        else:
            param_layout = [sg.Text(desc, auto_size_text=True, pad=((0, pad_el), 0), font=bold_font,
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
            print('Info: Parameter {NAME}: unable to find window values for parameter to update'
                  .format(NAME=self.name))
            return self.value
        else:
            print('Info: Parameter {NAME}: updating parameter value {ORIG} to {NEW}'
                  .format(NAME=self.name, ORIG=self.value, NEW=input_value))
            if input_value is None:
                return None

        if dtype in ('float', 'decimal', 'dec', 'double', 'numeric', 'money'):
            try:
                value_fmt = float(input_value)
            except (ValueError, TypeError):
                try:
                    value_fmt = float(input_value.replace(group_sep, ''))
                except (ValueError, TypeError, AttributeError):
                    print('Warning: parameter {PARAM}: unknown object type for parameter value {VAL}'
                          .format(PARAM=self.name, VAL=input_value))
                    return None
        elif dtype in ('int', 'integer', 'bit'):
            try:
                value_fmt = int(input_value)
            except (ValueError, TypeError, AttributeError):
                try:
                    value_fmt = input_value.replace(',', '')
                except (ValueError, TypeError):
                    print('Warning: parameter {PARAM}: unknown object type for parameter value {VAL}'
                          .format(PARAM=self.name, VAL=input_value))
                    return None
        elif dtype in ('bool', 'boolean'):
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
        print('Info: formatting parameter {PARAM} value {VAL} for display'
              .format(PARAM=self.name, VAL=value))

        if value == '' or value is None:
            return ''

        if dtype == 'money':
            if dec_sep in value:
                integers, decimals = value.split(dec_sep)
                decimals = decimals[0:2]
                display_value = ''.join([group_sep * (n % 3 == 2) + i
                                         for n, i in enumerate(integers[::-1])][::-1]).lstrip(',') + dec_sep + decimals
            else:
                display_value = ''.join([group_sep * (n % 3 == 2) + i
                                         for n, i in enumerate(value[::-1])][::-1]).lstrip(',')

        elif dtype in ('float', 'decimal', 'dec', 'double', 'numeric'):
            try:
                new_value = float(value)
            except ValueError:
                display_value = value
            else:
                display_value = str(new_value)

        elif dtype in ('int', 'integer', 'bit'):
            try:
                new_value = int(value)
            except ValueError:
                display_value = value
            else:
                display_value = str(new_value)

        else:
            display_value = str(value)

        return display_value


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
        print('Info: {PARAM}: initializing {ETYPE} parameter of data type {DTYPE} with default value {DEF}, formatted '
              'value {VAL}, and display value {DIS}'.format(PARAM=self.name, ETYPE=self.etype, DTYPE=self.dtype,
                                                            DEF=self.default, VAL=self.value, DIS=self.format_display()))

    def layout(self, size: tuple = None, padding: tuple = (0, 0), bg_col: str = mod_const.ACTION_COL):
        """
        Create a GUI layout for the parameter.
        """
        # Element settings
        pad_el = mod_const.ELEM_PAD

        font = mod_const.MID_FONT
        bold_font = mod_const.BOLD_FONT

        in_col = mod_const.INPUT_COL

        # Parameter settings
        aliases = self.aliases
        combo_values = self.combo_values
        icon = self.icon

        elem_key = self.key_lookup('Element')
        desc = '{}:'.format(self.description)
        values = [aliases[i] for i in combo_values if i in aliases]
        if '' not in values:  # the no selection option
            values.insert(0, '')

        param_value = self.format_display()

        # Icon layout
        if icon is None:
            icon_layout = []
        else:
            icon_path = configuration.get_icon_path(icon)
            if icon_path is not None:
                icon_layout = [sg.Image(filename=icon_path, pad=((0, pad_el), 0), background_color=bg_col)]
            else:
                icon_layout = []

        # Parameter size
        width = max([len(i) for i in values]) + 1
        size = (width, 1) if size is None else size

        # Element layout
        if self.editable is True:
            param_layout = [sg.Text(desc, auto_size_text=True, pad=((0, pad_el), 0), font=bold_font,
                                    background_color=bg_col),
                            sg.Combo(values, default_value=param_value, key=elem_key, size=size, font=font,
                                     background_color=in_col, enable_events=True,
                                     tooltip='Select a value for {}'.format(self.description),
                                     metadata={'value': param_value, 'disabled': False})]
        else:
            param_layout = [sg.Text(desc, auto_size_text=True, pad=((0, pad_el), 0), font=bold_font,
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
            print('Info: Parameter {NAME}: unable to find window values for parameter to update'
                  .format(NAME=self.name))
            return self.value
        else:
            print('Info: Parameter {NAME}: updating parameter value {ORIG} to {NEW}'
                  .format(NAME=self.name, ORIG=self.value, NEW=input_value))

        aliases = {j: i for i, j in self.aliases.items()}
        value_fmt = aliases.get(input_value, input_value)

        return value_fmt

    def format_display(self):
        """
        Format the parameter's value for displaying.
        """
        value = self.value
        aliases = self.aliases

        display_value = aliases.get(value, value)

        return display_value


class DataParameterDate(DataParameter):
    """
    Date-style parameter.
    """

    def __init__(self, name, entry):
        super().__init__(name, entry)
        self.elements.append('-{NAME}_{ID}_{ELEM}-'.format(NAME=self.name, ID=self.id, ELEM='Calendar'))

        self.value = self.format_value({self.key_lookup('Element'): self.default})
        print('Info: {PARAM}: initializing {ETYPE} parameter of data type {DTYPE} with default value {DEF}, formatted '
              'value {VAL}, and display value {DIS}'.format(PARAM=self.name, ETYPE=self.etype, DTYPE=self.dtype,
                                                            DEF=self.default, VAL=self.value, DIS=self.format_display()))

    def layout(self, size: tuple = (14, 1), padding: tuple = (0, 0), bg_col: str = mod_const.ACTION_COL):
        """
        Create a GUI layout for the parameter.
        """
        pad_el = mod_const.ELEM_PAD

        # Element settings
        date_ico = mod_const.CALENDAR_ICON
        font = mod_const.MID_FONT
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
            icon_path = configuration.get_icon_path(icon)
            if icon_path is not None:
                icon_layout = [sg.Image(filename=icon_path, pad=((0, pad_el), 0), background_color=bg_col)]
            else:
                icon_layout = []

        # Element layout
        input_key = self.key_lookup('Element')
        calendar_key = self.key_lookup('Calendar')
        if self.editable is True:
            param_layout = [sg.Text(desc, auto_size_text=True, pad=((0, pad_el), 0), font=bold_font,
                                    background_color=bg_col),
                            sg.Input(param_value, key=input_key, size=size, enable_events=True, pad=((0, pad_el), 0),
                                     font=font, background_color=in_col, disabled=False,
                                     tooltip='Input date as YYYY-MM-DD or use the calendar button to select the date',
                                     metadata={'value': param_value, 'disabled': False}),
                            sg.CalendarButton('', target=input_key, key=calendar_key, format='%Y-%m-%d',
                                              image_data=date_ico, font=font, border_width=0,
                                              tooltip='Select date from calendar menu')]
        else:
            param_layout = [sg.Text(desc, auto_size_text=True, pad=((0, pad_el), 0), font=bold_font,
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
            print('Info: Parameter {NAME}: unable to find window values for parameter to update'
                  .format(NAME=self.name))
            return self.value
        else:
            print('Info: Parameter {NAME}: updating parameter value {ORIG} to {NEW}'
                  .format(NAME=self.name, ORIG=self.value, NEW=input_value))

        if not input_value:
            return None

        if isinstance(input_value, str):
            try:
                value_fmt = strptime(input_value, '%Y-%m-%d')
            except (ValueError, TypeError):
                print('Warning: parameter {PARAM}: unable to parse date {VAL}'
                      .format(PARAM=self.name, VAL=input_value))
                value_fmt = None
        elif isinstance(input_value, datetime.datetime):
            value_fmt = input_value
        else:
            print('Warning: parameter {PARAM}: unknown object type for {VAL}'
                  .format(PARAM=self.name, VAL=input_value))
            value_fmt = None

        return value_fmt

    def format_display(self):
        """
        Format the parameter's value for displaying.
        """
        value = self.value
        if value is None:
            return ''

        if isinstance(value, str):
            value_fmt = value
        elif isinstance(value, datetime.datetime):
            value_fmt = value.strftime('%Y-%m-%d')
        else:
            print('Warning: parameter {PARAM}: unknown object type for parameter value {VAL}'
                  .format(PARAM=self.name, VAL=value))
            value_fmt = None

        return value_fmt

    def toggle_parameter(self, window, value: str = 'enable'):
        """
        Toggle parameter elements on and off.
        """
        status = False if value == 'enable' else True

        print('Info: DataParameter {NAME}: updating elements to "disabled={VAL}"'
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
        print('Info: {PARAM}: initializing {ETYPE} parameter of data type {DTYPE} with default value {DEF}, formatted '
              'value {VAL}, and display value {DIS}'.format(PARAM=self.name, ETYPE=self.etype, DTYPE=self.dtype,
                                                            DEF=self.default, VAL=self.value, DIS=self.format_display()))

    def layout(self, size: tuple = (14, 1), padding: tuple = (0, 0), bg_col: str = mod_const.ACTION_COL):
        """
        Create a GUI layout for the parameter.
        """
        # Element settings
        pad_el = mod_const.ELEM_PAD

        date_ico = mod_const.CALENDAR_ICON
        font = mod_const.MID_FONT
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
            icon_path = configuration.get_icon_path(icon)
            if icon_path is not None:
                icon_layout = [sg.Image(filename=icon_path, pad=((0, pad_el), 0), background_color=bg_col)]
            else:
                icon_layout = []

        # Element layout
        from_key = self.key_lookup('Element')
        from_date_key = self.key_lookup('Calendar')
        to_key = self.key_lookup('Element2')
        to_date_key = self.key_lookup('Calendar2')
        if self.editable is True:
            layout = [
                sg.Col([icon_layout +
                        [sg.Text('{}:'.format(from_desc), auto_size_text=True, pad=((0, pad_el), 0), font=bold_font,
                                 background_color=bg_col),
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
                        [sg.Text(from_desc, auto_size_text=True, pad=((0, pad_el), 0), font=bold_font,
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
            print('Info: Parameter {NAME}: unable to find window values for parameter to update'
                  .format(NAME=self.name))
            return self.value
        else:
            print('Info: Parameter {NAME}: updating parameter value {ORIG} to {NEW}'
                  .format(NAME=self.name, ORIG=self.value, NEW=input_values))

        formatted_values = []
        for input_value in input_values:
            if not input_value:
                formatted_values.append(None)
                continue

            if isinstance(input_value, str):
                try:
                    value_fmt = strptime(input_value, '%Y-%m-%d')
                except (ValueError, TypeError):
                    print('Warning: parameter {PARAM}: unable to parse date {VAL}'
                          .format(PARAM=self.name, VAL=input_value))
                    value_fmt = None
            elif isinstance(input_value, datetime.datetime):
                value_fmt = input_value
            else:
                print('Warning: parameter {PARAM}: unknown object type for {VAL}'
                      .format(PARAM=self.name, VAL=input_value))
                value_fmt = None

            formatted_values.append(value_fmt)

        return formatted_values

    def format_display(self):
        """
        Format the parameter's value for displaying.
        """
        values = self.value
        if values is None:
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
                print('Warning: parameter {PARAM}: unknown object type for parameter value {VAL}'
                      .format(PARAM=self.name, VAL=value))
                value_fmt = ''

            formatted_values.append(value_fmt)

        return formatted_values

    def query_statement(self, column):
        """
        Generate the filter clause for SQL querying.
        """
        values = self.value
        if len(values) == 2:
            statement = ('{COL} BETWEEN ? AND ?'.format(COL=column), values)
        else:
            statement = None

        return statement

    def reset(self, window):
        """
        Reset the parameter's values.
        """
        print('Info: DataParameter {NAME}: resetting parameter value {VAL} to {DEF}'
              .format(NAME=self.name, VAL=self.value, DEF=self.default))

        try:
            def_val1, def_val2 = self.default
        except (ValueError, TypeError):
            def_val1 = def_val2 = None

        self.format_value({self.key_lookup('Element'): def_val1, self.key_lookup('Element2'): def_val2})
        print('Info: DataParameter {NAME}: values reset to {VAL}'.format(NAME=self.name, VAL=self.value))

        # Update the parameter window element
        window[self.key_lookup('Element')].update(value='')
        window[self.key_lookup('Element2')].update(value='')

    def toggle_parameter(self, window, value: str = 'enable'):
        """
        Toggle parameter elements on and off.
        """
        status = False if value == 'enable' else True

        print('Info: DataParameter {NAME}: updating elements to "disabled={VAL}"'
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
        print('Info: {PARAM}: initializing {ETYPE} parameter of data type {DTYPE} with default value {DEF}, formatted '
              'value {VAL}, and display value {DIS}'.format(PARAM=self.name, ETYPE=self.etype, DTYPE=self.dtype,
                                                            DEF=self.default, VAL=self.value, DIS=self.format_display()))

    def layout(self, size: tuple = None, padding: tuple = (0, 0), bg_col: str = mod_const.ACTION_COL):
        """
        Create a GUI layout for the parameter.
        """
        bold_font = mod_const.BOLD_FONT

        key = self.key_lookup('Element')
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
            icon_path = configuration.get_icon_path(icon)
            if icon_path is not None:
                icon_layout = [sg.Image(filename=icon_path, pad=((0, pad_el), 0), background_color=bg_col)]
            else:
                icon_layout = []

        # Parameter layout
        param_layout = [sg.Checkbox(desc, default=param_value, key=key, pad=padding, font=bold_font,
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
            print('Info: Parameter {NAME}: unable to find window values for parameter to update'
                  .format(NAME=self.name))
            return self.value
        else:
            print('Info: Parameter {NAME}: updating parameter value {ORIG} to {NEW}'
                  .format(NAME=self.name, ORIG=self.value, NEW=input_value))

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


class DataParameterButton(DataParameter):
    """
    Button data storage parameter.
    """
    def __init__(self, name, entry):
        super().__init__(name, entry)
        self.elements.append('-{NAME}_{ID}_{ELEM}-'.format(NAME=self.name, ID=self.id, ELEM='Button'))

        # Dynamic attributes
        self.value = self.format_value({self.key_lookup('Element'): self.default})
        print('Info: {PARAM}: initializing {ETYPE} parameter of data type {DTYPE} with default value {DEF}, formatted '
              'value {VAL}, and display value {DIS}'.format(PARAM=self.name, ETYPE=self.etype, DTYPE=self.dtype,
                                                            DEF=self.default, VAL=self.value, DIS=self.format_display()))

    def layout(self, size: tuple = (14, 1), padding: tuple = (0, 0), bg_col: str = mod_const.ACTION_COL):
        """
        Create a GUI layout for the parameter.
        """
        # Element settings
        pad_el = mod_const.ELEM_PAD

        font = mod_const.MID_FONT
        bold_font = mod_const.BOLD_FONT

        in_col = mod_const.INPUT_COL
        text_col = mod_const.TEXT_COL

        # Parameter settings
        desc = '{}:'.format(self.description)
        param_value = self.format_display()
        icon = self.icon

        # Icon layout
        bttn_key = self.key_lookup('Button')
        elem_key = self.key_lookup('Element')
        if icon is None:
            icon_layout = []
        else:
            icon_path = configuration.get_icon_path(icon)
            if icon_path is not None:
                icon_layout = [sg.Button('', key=bttn_key, target=elem_key, image_filename=icon_path, font=font,
                                         button_color=(text_col, bg_col), border_width=0, tooltip=desc,
                                         disabled=(not self.editable), enable_events=True)]
            else:
                icon_layout = [sg.Button('', key=bttn_key, target=elem_key, button_color=(text_col, bg_col), font=font,
                                         tooltip=desc, border_width=0, disabled=(not self.editable),
                                         enable_events=True)]

        # Element layout
        param_layout = [sg.Input(param_value, key=elem_key, visible=False,
                                 tooltip='Input value for {}'.format(self.description),
                                 metadata={'value': param_value, 'disabled': (not self.editable), 'visible': False})]

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
            print('Info: Parameter {NAME}: unable to find window values for parameter to update'
                  .format(NAME=self.name))
            return self.value
        else:
            print('Info: Parameter {NAME}: updating parameter value {ORIG} to {NEW}'
                  .format(NAME=self.name, ORIG=self.value, NEW=input_value))
            if input_value is None:
                return None

        if dtype in ('float', 'decimal', 'dec', 'double', 'numeric', 'money'):
            try:
                value_fmt = float(input_value)
            except (ValueError, TypeError):
                try:
                    value_fmt = float(input_value.replace(group_sep, ''))
                except (ValueError, TypeError, AttributeError):
                    print('Warning: parameter {PARAM}: unknown object type for parameter value {VAL}'
                          .format(PARAM=self.name, VAL=input_value))
                    return None
        elif dtype in ('int', 'integer', 'bit'):
            try:
                value_fmt = int(input_value)
            except (ValueError, TypeError, AttributeError):
                try:
                    value_fmt = input_value.replace(',', '')
                except (ValueError, TypeError):
                    print('Warning: parameter {PARAM}: unknown object type for parameter value {VAL}'
                          .format(PARAM=self.name, VAL=input_value))
                    return None
        elif dtype in ('bool', 'boolean'):
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
        print('Info: formatting parameter {PARAM} value {VAL} for display'
              .format(PARAM=self.name, VAL=value))

        if value == '' or value is None:
            return ''

        if dtype == 'money':
            if dec_sep in value:
                integers, decimals = value.split(dec_sep)
                decimals = decimals[0:2]
                display_value = ''.join([group_sep * (n % 3 == 2) + i
                                         for n, i in enumerate(integers[::-1])][::-1]).lstrip(',') + dec_sep + decimals
            else:
                display_value = ''.join([group_sep * (n % 3 == 2) + i
                                         for n, i in enumerate(value[::-1])][::-1]).lstrip(',')

        elif dtype in ('float', 'decimal', 'dec', 'double', 'numeric'):
            try:
                new_value = float(value)
            except ValueError:
                display_value = value
            else:
                display_value = str(new_value)

        elif dtype in ('int', 'integer', 'bit'):
            try:
                new_value = int(value)
            except ValueError:
                display_value = value
            else:
                display_value = str(new_value)

        else:
            display_value = str(value)

        return display_value
