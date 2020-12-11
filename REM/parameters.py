"""
REM parameter element classes.
"""
import sys

import datetime
import dateutil.parser
import PySimpleGUI as sg

import REM.constants as const
import REM.layouts as lo
import REM.secondary as win2
from REM.config import settings


class RuleParameter:
    """
    """

    def __init__(self, rule_name, name, cdict):

        self.name = name
        self.rule_name = rule_name
        self.element_key = lo.as_key('{RULE} Parameter {NAME} '.format(RULE=rule_name, NAME=name))
        try:
            self.description = cdict['Description']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}, RuleParameter {NAME}: missing required parameter "Description".') \
                .format(RULE=rule_name, NAME=name)
            win2.popup_error(msg)
            sys.exit(1)

        try:
            self.type = cdict['ElementType']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}, RuleParameter {NAME}: missing required parameter "ElementType".') \
                .format(RULE=rule_name, NAME=name)
            win2.popup_error(msg)
            sys.exit(1)

        try:
            editable = bool(int(cdict['IsEditable']))
        except KeyError:
            self.editable = True
        except ValueError:
            win2.popup_error('Configuration Error: rule {RULE}, Parameter {NAME}: "IsEditable" must be either 0 '
                             '(False) or 1 (True)'.format(RULE=self.rule_name, NAME=self.name))
            sys.exit(1)
        else:
            self.editable = editable

        try:
            hidden = bool(int(cdict['IsHidden']))
        except KeyError:
            self.hidden = False
        except ValueError:
            win2.popup_error('Configuration Error: rule {RULE}, Parameter {NAME}: "IsHidden" must be either 0 '
                             '(False) or 1 (True)'.format(RULE=self.rule_name, NAME=self.name))
            sys.exit(1)
        else:
            self.hidden = hidden

        try:
            justification = cdict['Justification']
        except KeyError:
            self.justification = 'left'
        else:
            if justification not in ['right', 'left', 'center']:
                self.justification = 'left'
            else:
                self.justification = justification

        try:
            self.alias = cdict['Alias']
        except KeyError:
            self.alias = name

        try:
            self.default = cdict['DefaultValue']
        except KeyError:
            self.default = None

        # Dynamic attributes
        self.value = self.value_raw = self.value_obj = None

        self.set_value({self.element_key: self.default})

    def reset_parameter(self):
        """
        Reset the parameter's values.
        """
        print('Info: rule {RULE}, parameter {PARAM}: resetting parameter value {VAL} to {DEF}'
              .format(RULE=self.rule_name, PARAM=self.name, VAL=self.value, DEF=self.default))
        self.set_value({self.element_key: self.default})

    def set_value(self, values, by_key: bool = True):
        """
        Set the value of the parameter element from user input.

        Arguments:

            values (dict): dictionary of window element values.

            by_key (bool): get value of parameter from dictionary using the element key (default: True)
        """
        if by_key is True:
            elem_key = self.element_key
        else:
            elem_key = self.name

        try:
            value = values[elem_key]
        except KeyError:
            print('Warning: rule {RULE}, parameter {PARAM}: no values set for parameter with key {KEY}'
                  .format(PARAM=self.name, RULE=self.rule_name, KEY=elem_key))
        else:
            self.value = self.value_raw = self.value_obj = value

    def values_set(self):
        """
        Check whether all values attributes have been set.
        """
        if self.value:
            return True
        else:
            return False

    def filter_statement(self, table=None, alias: bool = False):
        """
        Generate the filter clause for SQL querying.
        """
        if alias is True:
            colname = self.alias
        else:
            colname = self.name

        if table:
            db_field = '{}.{}'.format(table, colname)
        else:
            db_field = colname

        value = self.value
        if value is not None:
            statement = ('{}= ?'.format(db_field), (value,))
        else:
            statement = None

        return statement


class RuleParameterInput(RuleParameter):
    """
    Input style parameter object.
    """

    def layout(self, text_size: tuple = (None, None), text_justification: str = 'r', size: tuple = (14, 1),
               padding: tuple = (const.HORZ_PAD, 0), default: bool = True, bg_col: str = const.ACTION_COL,
               filter_layout: bool = False):
        """
        Create a layout for rule parameter element 'input'.
        """
        pad_el = const.ELEM_PAD
        pad_h, pad_v = padding

        font = const.MID_FONT
        bold_font = const.BOLD_FONT

        in_col = const.INPUT_COL

        desc = '{}:'.format(self.description)
        param_value = '' if self.value is None or default is False else self.value

        key = self.element_key
        if self.editable is True or filter_layout is True:
            layout = [sg.Text(desc, size=text_size, pad=((pad_h, pad_el), pad_v), justification=text_justification,
                              font=bold_font, background_color=bg_col),
                      sg.Input(param_value, key=key, size=size, enable_events=True, pad=((0, pad_h), pad_v), font=font,
                               background_color=in_col, disabled=False,
                               tooltip=_('Input value for {}'.format(self.description)))]
        else:
            layout = [sg.Text(desc, size=text_size, pad=((pad_h, pad_el), pad_v), justification=text_justification,
                              font=bold_font, background_color=bg_col),
                      sg.Text(param_value, key=key, size=size, pad=((0, pad_h), pad_v), font=font,
                              background_color=bg_col, border_width=1)]

        return layout


class RuleParameterCombo(RuleParameter):
    """
    DropDown parameter element object.
    """

    def __init__(self, rule_name, name, cdict):
        super().__init__(rule_name, name, cdict)
        try:
            self.combo_values = cdict['Values']
        except KeyError:
            msg = _('Configuration Warning: rule {RULE}, parameter {PARAM}: values required for parameter type '
                    '"dropdown"').format(PARAM=name, RULE=rule_name)
            win2.popup_notice(msg)

            self.combo_values = []

    def layout(self, text_size: tuple = (None, None), text_justification: str = 'r', size: tuple = None,
               padding: tuple = (const.HORZ_PAD, 0), default: bool = True, bg_col: str = const.ACTION_COL,
               filter_layout: bool = False):
        """
        Create a layout for rule parameter element 'dropdown'.
        """
        pad_el = const.ELEM_PAD
        pad_h, pad_v = padding

        font = const.MID_FONT
        bold_font = const.BOLD_FONT

        in_col = const.INPUT_COL

        key = self.element_key
        desc = '{}:'.format(self.description)
        values = self.combo_values
        if values[0] != '':
            values.insert(0, '')

        width = max([len(i) for i in values]) + 1
        size = (width, 1) if size is None else size

        param_value = '' if self.value is None or default is False else self.value

        if self.editable is True or filter_layout is True:
            layout = [sg.Text(desc, size=text_size, pad=((pad_h, pad_el), pad_v), justification=text_justification,
                              font=bold_font, background_color=bg_col),
                      sg.Combo(values, default_value=param_value, key=key, size=size, pad=((0, pad_h), pad_v),
                               font=font, background_color=in_col, enable_events=True, disabled=False)]
        else:
            layout = [sg.Text(desc, size=text_size, pad=((pad_h, pad_el), pad_v), justification=text_justification,
                              font=bold_font, background_color=bg_col),
                      sg.Text(param_value, key=key, size=size, pad=((0, pad_h), pad_v), font=font,
                              background_color=bg_col, border_width=1)]

#        return sg.Col([layout], pad=(0, 0), background_color=bg_col)
        return layout


class RuleParameterDate(RuleParameter):
    """
    Date parameter element object.
    """

    def __init__(self, rule_name, name, cdict):
        super().__init__(rule_name, name, cdict)
        try:
            self.format = settings.format_date_str(date_str=cdict['DateFormat'])
        except KeyError:
            msg = _('Warning: rule {RULE}, parameter {PARAM}: no date format specified ... defaulting to '
                    'YYYY-MM-DD').format(PARAM=name, RULE=rule_name)
            win2.popup_notice(msg)
            self.format = "%Y-%m-%d"

    def layout(self, text_size: tuple = (None, None), text_justification: str = 'r', size: tuple = (14, 1),
               padding: tuple = (const.HORZ_PAD, 0), default: bool = True, bg_col: str = const.ACTION_COL,
               filter_layout: bool = False):
        """
        Layout for the rule parameter element 'date'.
        """
        pad_el = const.ELEM_PAD
        pad_h, pad_v = padding

        date_ico = const.CALENDAR_ICON
        font = const.MID_FONT
        bold_font = const.BOLD_FONT

        in_col = const.INPUT_COL

        desc = '{}:'.format(self.description)
        param_value = '' if self.value is None or default is False else self.value

        input_key = self.element_key
        date_key = lo.as_key('{RULE} Parameter {NAME} Button'.format(RULE=self.rule_name, NAME=self.name))
        if self.editable is True or filter_layout is True:
            layout = [sg.Text(desc, size=text_size, pad=((pad_h, pad_el), pad_v), justification=text_justification,
                              font=bold_font, background_color=bg_col),
                      sg.Input(param_value, key=input_key, size=size, enable_events=True, pad=((0, pad_el), pad_v),
                               font=font, background_color=in_col, disabled=False,
                               tooltip='Input date as YYYY-MM-DD or use the calendar button to select the date'),
                      sg.CalendarButton('', key=date_key, format='%Y-%m-%d', image_data=date_ico, pad=((0, pad_h), pad_v),
                                        font=font, border_width=0, disabled=False,
                                        tooltip='Select date from calendar menu')]
        else:
            layout = [sg.Text(desc, size=text_size, pad=((pad_h, pad_el), pad_v), justification=text_justification,
                              font=bold_font, background_color=bg_col),
                      sg.Text(param_value, key=input_key, size=size, pad=((0, pad_el), pad_v), font=font,
                              background_color=bg_col, border_width=1)]
#                      sg.CalendarButton('', key=date_key, format='%Y-%m-%d', image_data=date_ico,
#                                        pad=((0, pad_h), pad_v), font=font, border_width=0, visible=False,
#                                        tooltip='Select date from calendar menu')]

        #        return sg.Col([layout], pad=(0, 0), background_color=bg_col)
        return layout

    def set_value(self, values, by_key: bool = True):
        """
        Set the value of the parameter element from user input.

        Arguments:

            values: dictionary of window element values.
        """
        dparse = dateutil.parser.parse

        if by_key is True:
            elem_key = self.element_key
        else:
            elem_key = self.name

        try:
            value_raw: str = values[elem_key]
        except KeyError:
            print('Warning: rule {RULE}, parameter {PARAM}: no values set for parameter with element key {KEY}'
                  .format(PARAM=self.name, RULE=self.rule_name, KEY=elem_key))
        else:
            if isinstance(value_raw, str):
                try:
                    date = dparse(value_raw, yearfirst=True)
                except (ValueError, TypeError):
                    print('Warning: rule {RULE}, parameter {PARAM}: unable to parse date {VAL}'
                          .format(PARAM=self.name, RULE=self.rule_name, VAL=value_raw))
                    date = None
            elif isinstance(value_raw, datetime.datetime):
                date = value_raw
            else:
                print('Warning: rule {RULE}, parameter {PARAM}: unknown object type for {VAL}'
                      .format(PARAM=self.name, RULE=self.rule_name, VAL=value_raw))
                date = None

            if date is not None:
                try:
                    value_fmt: str = date.strftime(self.format)
                except (ValueError, AttributeError):
                    print('Configuration Error: rule {RULE}, parameter {PARAM}: invalid format string {STR}'
                          .format(RULE=self.rule_name, PARAM=self.name, STR=self.format))
                    value_fmt = date = None
            else:
                value_fmt = date = None

            self.value = value_fmt
            self.value_raw = value_raw
            self.value_obj = date

    def values_set(self):
        """
        Check whether all values attributes have been set with correct formatting.
        """
        value = self.value_raw

        if isinstance(value, str):
            try:
                input_date = value.split()[0].replace('-', '')
            except (AttributeError, IndexError):
                print('configuration error: rule {RULE}, parameter {PARAM}: invalid format string {STR}'
                      .format(RULE=self.rule_name, PARAM=self.name, STR=self.format))
                return False
        elif isinstance(value, datetime.datetime):
            input_date = value.strftime("%Y%m%d")
        else:
            print('configuration error: rule {RULE}, parameter {PARAM}: no value found for parameter'
                  .format(RULE=self.rule_name, PARAM=self.name))
            return False

        if input_date and len(input_date) == 8:
            return True
        else:
            return False


class RuleParameterCheckbox(RuleParameter):
    """
    Checkbox parameter element object.
    """

    def __init__(self, rule_name, name, cdict):
        super().__init__(rule_name, name, cdict)

    def layout(self, text_size: tuple = (None, None), text_justification: str = 'r', size: tuple = (None, None),
               padding: tuple = (const.HORZ_PAD, 0), default: bool = True, bg_col: str = const.ACTION_COL,
               filter_layout: bool = False):
        """
        Create a layout for rule parameter element 'checkbox'.
        """
        bold_font = const.BOLD_FONT

        key = self.element_key
        desc = self.description
        disabled = False if self.editable is True or filter_layout is True else True
        param_value = False if self.value is None or default is False else self.value
        layout = [sg.Col([
            [sg.Checkbox(desc, default=param_value, key=key, pad=padding, font=bold_font, enable_events=True,
                         background_color=bg_col, disabled=disabled)]], background_color=bg_col, justification='c')]

        return layout

    def set_value(self, values, by_key: bool = True):
        """
        Set the value of the parameter element from user input.

        Arguments:

            values (dict): dictionary of window element values.

            by_key (bool): get value of parameter from dictionary using the element key (default: True)
        """
        if by_key is True:
            elem_key = self.element_key
        else:
            elem_key = self.name

        try:
            value = values[elem_key]
        except KeyError:
            print('Warning: rule {RULE}, parameter {PARAM}: no values set for parameter with key {KEY}'
                  .format(PARAM=self.name, RULE=self.rule_name, KEY=elem_key))
        else:
            if isinstance(value, bool):
                self.value = self.value_obj = value
                self.value_raw = int(value)
            else:
                try:
                    self.value = self.value_obj = bool(int(value))
                except (ValueError, TypeError):
                    print('Warning: rule {RULE}, parameter {PARAM}: unable to convert value {VAL} to boolean'
                          .format(PARAM=self.name, RULE=self.rule_name, VAL=value))
                else:
                    self.value_raw = int(self.value)

