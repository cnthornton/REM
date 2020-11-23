"""
REM parameter element classes.
"""
import sys

import dateutil.parser
import PySimpleGUI as sg

import REM.constants as const
import REM.layouts as lo
import REM.secondary as win2
from REM.config import settings


class AuditParameter:
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
            filterable = bool(int(cdict['IsFilterable']))
        except KeyError:
            self.filterable = True
        except ValueError:
            win2.popup_error('Configuration Error: rule {RULE}, Parameter {NAME}: "IsFilterable" must be either 0 '
                             '(False) or 1 (True)'.format(RULE=self.rule_name, NAME=self.name))
            sys.exit(1)
        else:
            self.filterable = filterable

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
            if justification not in ['right', 'left']:
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
            value = None

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
        if value:
            statement = ('{}= ?'.format(db_field), (value,))
        else:
            statement = None

        return statement


class AuditParameterInput(AuditParameter):
    """
    Input style parameter object.
    """

    def layout(self, text_size: tuple = (None, None), size: tuple = (14, 1), padding: int = None, default=True):
        """
        Create a layout for rule parameter element 'input'.
        """
        pad_el = const.ELEM_PAD
        padding = const.HORZ_PAD if padding is None else padding

        font = const.MID_FONT
        bold_font = const.BOLD_FONT

        in_col = const.INPUT_COL
        bg_col = const.ACTION_COL

        key = self.element_key
        desc = '{}:'.format(self.description)

        disabled = False if self.editable is True else True

        param_value = '' if self.value is None or default is False else self.value

        layout = [sg.Text(desc, size=text_size, pad=((0, pad_el), 0), justification='r', font=bold_font,
                          background_color=bg_col),
                  sg.Input(param_value, key=key, size=size, enable_events=True, pad=((0, pad_el), 0), font=font,
                           background_color=in_col, disabled=disabled,
                           tooltip=_('Input value for {}'.format(self.description))),
                  sg.Canvas(size=(padding, 0), visible=True, background_color=bg_col)]

#        return sg.Col([layout], pad=(0, 0), background_color=bg_col)
        return layout


class AuditParameterCombo(AuditParameter):
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

    def layout(self, text_size: tuple = (None, None), size: tuple = None, padding: int = None, default=True):
        """
        Create a layout for rule parameter element 'dropdown'.
        """
        pad_el = const.ELEM_PAD
        padding = const.HORZ_PAD if padding is None else padding

        font = const.MID_FONT
        bold_font = const.BOLD_FONT

        in_col = const.INPUT_COL
        bg_col = const.ACTION_COL

        key = self.element_key
        desc = '{}:'.format(self.description)
        values = self.combo_values
        if values[0] != '':
            values.insert(0, '')

        width = max([len(i) for i in values]) + 1
        size = (width, 1) if size is None else size

        disabled = False if self.editable is True else True

        param_value = '' if self.value is None or default is False else self.value

        layout = [sg.Text(desc, size=text_size, pad=((0, pad_el), 0), justification='r', font=bold_font,
                          background_color=bg_col),
                  sg.Combo(values, default_value=param_value, key=key, size=size, pad=(0, 0), font=font,
                           background_color=in_col, enable_events=True, disabled=disabled),
                  sg.Canvas(size=(padding, 0), visible=True, background_color=bg_col)]

#        return sg.Col([layout], pad=(0, 0), background_color=bg_col)
        return layout


class AuditParameterDate(AuditParameter):
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

    def layout(self, text_size: tuple = (None, None), size: tuple = (14, 1), padding: int = None, default=True):
        """
        Layout for the rule parameter element 'date'.
        """
        pad_el = const.ELEM_PAD
        padding = const.HORZ_PAD if padding is None else padding

        date_ico = const.CALENDAR_ICON
        font = const.MID_FONT
        bold_font = const.BOLD_FONT

        in_col = const.INPUT_COL
        bg_col = const.ACTION_COL

        desc = '{}:'.format(self.description)

        disabled = False if self.editable is True else True

        param_value = '' if self.value is None or default is False else self.value

        input_key = self.element_key
        date_key = lo.as_key('{RULE} Parameter {NAME} Button'.format(RULE=self.rule_name, NAME=self.name))
        layout = [sg.Text(desc, size=text_size, pad=((0, pad_el), 0), justification='r', font=bold_font,
                          background_color=bg_col),
                  sg.Input(param_value, key=input_key, size=size, enable_events=True, pad=((0, pad_el), 0), font=font,
                           background_color=in_col, disabled=disabled,
                           tooltip=_('Input date as YYYY-MM-DD or use the calendar button to select the date')),
                  sg.CalendarButton('', key=date_key, format='%Y-%m-%d', image_data=date_ico, pad=(0, 0), font=font,
                                    border_width=0, disabled=disabled, tooltip=_('Select date from calendar menu')),
                  sg.Canvas(size=(padding, 0), visible=True, background_color=bg_col)]

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
            value_fmt = None
            value_raw = None
            date = None
        else:
            try:
                date = dparse(value_raw, yearfirst=True)
            except (ValueError, TypeError):
                value_fmt = value_raw = date = None
            else:
                try:
                    value_fmt: str = date.strftime(self.format)
                except ValueError:
                    print('Configuration Error: rule {RULE}, parameter {PARAM}: invalid format string {STR}'
                          .format(RULE=self.rule_name, PARAM=self.name, STR=self.format))
                    value_fmt = date = None

        self.value = value_fmt
        self.value_raw = value_raw
        self.value_obj = date

    def values_set(self):
        """
        Check whether all values attributes have been set with correct formatting.
        """
        value = self.value_raw

        try:
            input_date = value.split()[0].replace('-', '')
        except AttributeError:
            return False
        if input_date and len(input_date) == 8:
            return True
        else:
            return False

