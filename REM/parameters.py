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
        self.element_key = lo.as_key('{} {}'.format(rule_name, name))
        try:
            self.description = cdict['Description']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}, summary {NAME}: missing required parameter "Description".') \
                .format(RULE=rule_name, NAME=name)
            win2.popup_error(msg)
            sys.exit(1)

        try:
            self.type = cdict['ElementType']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}, summary {NAME}: missing required parameter "ElementType".') \
                .format(RULE=rule_name, NAME=name)
            win2.popup_error(msg)
            sys.exit(1)

        try:
            self.alias = cdict['Alias']
        except KeyError:
            self.alias = name

        # Dynamic attributes
        self.value = self.value_raw = self.value_obj = None

    def set_value(self, values):
        """
        Set the value of the parameter element from user input.

        Arguments:

            values: dictionary of window element values.
        """
        try:
            elem_key = self.element_key
        except KeyError:
            print('Warning: rule {RULE}, parameter {PARAM}: no values set for parameter'
                  .format(PARAM=self.name, RULE=self.rule_name))
            value = ''
        else:
            value = values[elem_key]

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


class AuditParameterCombo(AuditParameter):
    """
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

    def layout(self, padding: int = 8):
        """
        Create a layout for rule parameter element 'dropdown'.
        """
        pad_el = const.ELEM_PAD
        pad_h = const.HORZ_PAD

        font = const.MID_FONT
        bold_font = const.BOLD_FONT

        in_col = const.INPUT_COL
        bg_col = const.ACTION_COL

        key = self.element_key
        desc = '{}:'.format(self.description)
        values = self.combo_values

        width = max([len(i) for i in values]) + padding

        layout = [sg.Text(desc, pad=((0, pad_el), 0), font=bold_font, background_color=bg_col),
                  sg.Combo(values, font=font, key=key, enable_events=True, size=(width, 1), pad=(0, 0),
                           background_color=in_col),
                  sg.Canvas(size=(pad_h, 0), visible=True, background_color=bg_col)]

        return sg.Col([layout], pad=(0, 0), background_color=bg_col)


class AuditParameterDate(AuditParameter):
    """
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

    def layout(self):
        """
        Layout for the rule parameter element 'date'.
        """
        pad_el = const.ELEM_PAD
        pad_h = const.HORZ_PAD
        date_ico = const.CALENDAR_ICON
        font = const.MID_FONT
        bold_font = const.BOLD_FONT
        in_col = const.INPUT_COL
        bg_col = const.ACTION_COL

        desc = '{}:'.format(self.description)

        key = self.element_key
        layout = [sg.Text(desc, pad=((0, pad_el), 0), font=bold_font, background_color=bg_col),
                  sg.Input('', key=key, size=(16, 1), enable_events=True, pad=((0, pad_el), 0), font=font,
                           background_color=in_col,
                           tooltip=_('Input date as YYYY-MM-DD or use the calendar button to select the date')),
                  sg.CalendarButton('', format='%Y-%m-%d', image_data=date_ico, pad=(0, 0),
                                    font=font, border_width=0, tooltip=_('Select date from calendar menu')),
                  sg.Canvas(size=(pad_h, 0), visible=True, background_color=bg_col)]

        return sg.Col([layout], pad=(0, 0), background_color=bg_col)

    def set_value(self, values):
        """
        Set the value of the parameter element from user input.

        Arguments:

            values: dictionary of window element values.
        """
        dparse = dateutil.parser.parse

        elem_key = self.element_key

        try:
            value_raw: str = values[elem_key]
        except KeyError:
            print('Warning: rule {RULE}, parameter {PARAM}: no values set for parameter'
                  .format(PARAM=self.name, RULE=self.rule_name))
            value_fmt = ''
            value_raw = ''
        else:
            try:
                date = dparse(value_raw, yearfirst=True)
            except ValueError:
                value_fmt = ''
                value_raw = ''
                date = ''
            else:
                try:
                    value_fmt: str = date.strftime(self.format)
                except ValueError:
                    print('Configuration Error: rule {RULE}, parameter {PARAM}: invalid format string {STR}'
                          .format(RULE=self.rule_name, PARAM=self.name, STR=self.format))
                    value_fmt = None
                    date = ''

        self.value = value_fmt
        self.value_raw = value_raw
        self.value_obj = date

    def values_set(self):
        """
        Check whether all values attributes have been set with correct
        formatting.
        """
        value = self.value_raw

        input_date = value.replace('-', '')
        if input_date and len(input_date) == 8:
            return True
        else:
            return False


class AuditParameterDateRange(AuditParameterDate):
    """
    Layout for the rule parameter element 'date_range'.
    """

    def __init__(self, rule_name, name, cdict):
        super().__init__(rule_name, name, cdict)
        self.element_key2 = lo.as_key('{} {} 2'.format(rule_name, name))
        self.value2 = None

    def layout(self):
        """
        Layout for the rule parameter element 'date' and 'date_range'.
        """
        pad_el = const.ELEM_PAD
        pad_h = const.HORZ_PAD
        date_ico = const.CALENDAR_ICON
        font = const.MID_FONT
        bold_font = const.BOLD_FONT
        in_col = const.INPUT_COL
        bg_col = const.ACTION_COL

        desc = self.description

        desc_from = '{} From:'.format(desc)
        desc_to = '{} To:'.format(desc)
        key_from = self.element_key
        key_to = self.element_key2

        layout = [[sg.Text(desc_from, pad=((0, pad_el), 0), font=bold_font, background_color=bg_col),
                   sg.Input('', key=key_from, size=(16, 1), enable_events=True, pad=((0, pad_el), 0), font=font,
                            background_color=in_col,
                            tooltip=_('Input date as YYYY-MM-DD or use the calendar button to select the date')),
                   sg.CalendarButton('', format='%Y-%m-%d', image_data=date_ico, border_width=0,
                                     pad=(0, 0), tooltip=_('Select date from calendar menu')),
                   sg.Text(desc_to, pad=((pad_h, pad_el), 0), font=bold_font, background_color=bg_col),
                   sg.Input('', key=key_to, size=(16, 1), enable_events=True, pad=((0, pad_el), 0),
                            background_color=in_col,
                            tooltip=_('Input date as YYYY-MM-DD or use the calendar button to select the date')),
                   sg.CalendarButton('', format='%Y-%m-%d', image_data=date_ico, border_width=0,
                                     pad=(0, 0), tooltip=_('Select date from calendar menu')),
                   sg.Canvas(size=(pad_h, 1), visible=True, background_color=bg_col)]]

        return sg.Col(layout, pad=(0, 0), background_color=bg_col)

    def filter_statement(self, table=None):
        """
        Generate the filter clause for SQL querying.
        """
        if table:
            db_field = '{}.{}'.format(table, self.name)
        else:
            db_field = self.name

        params = (self.value, self.value2)
        statement = ('{} BETWEEN ? AND ?'.format(db_field), params)

        return statement

    def set_value(self, values):
        """
        Set the value of the parameter element from user input.

        Arguments:

            values: dictionary of window element values.
        """
        elem_key = self.element_key
        elem_key2 = self.element_key2
        self.value = values[elem_key]

        self.value2 = values[elem_key2]

    def values_set(self):
        """
        Check whether all values attributes have been set.
        """
        if self.value and self.value2:
            return True
        else:
            return False
