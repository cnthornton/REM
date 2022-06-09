"""
REM standard GUI element classes such as tables and information boxes.
"""

import datetime
from math import ceil as ceiling
from random import randint

import PySimpleGUI as sg
import pandas as pd
import re

import REM.data_collections as mod_col
import REM.constants as mod_const
import REM.data_manipulation as mod_dm
import REM.layouts as mod_lo
import REM.parameters as mod_param
import REM.records as mod_records
import REM.secondary as mod_win2
from REM.client import logger, settings


class RecordElement:
    """
    Record element parent class.

    Attributes:
        name (str): record element configuration name.

        parent (str): optional name of the parent element.

        id (int): record element number.

        elements (list): list of GUI element keys.

        description (str): record element display title.

        annotation_rules (dict): annotate the element using the configured annotation rules.

        bg_col (str): hexadecimal color code of the element's background.

        icon (str): name of the icon file containing the image representing the record element.

        tooltip (str): element tooltip.

        edited (bool): record element was edited [Default: False].
    """

    def __init__(self, name, entry, parent=None):
        """
        Initialize the record element attributes.

        Arguments:
            name (str): name of the configured element.

            entry (dict): configuration entry for the element.

            parent (str): name of the parent element.
        """
        self.name = name
        self.parent = parent
        self.id = randint(0, 1000000000)

        # self.elements = ['-{NAME}_{ID}_{ELEM}-'.format(NAME=name, ID=self.id, ELEM=i) for i in
        #                 ('Element',)]
        self.elements = {i: '-{NAME}_{ID}_{ELEM}-'.format(NAME=name, ID=self.id, ELEM=i) for i in
                         ('Element',)}

        try:
            self.etype = entry['ElementType']
        except KeyError:
            msg = 'no element type specified for the record element'
            logger.warning('RecordElement {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

        try:
            self.description = entry['Description']
        except KeyError:
            self.description = name

        # Layout styling options
        try:
            annotation_rules = entry['AnnotationRules']
        except KeyError:
            annotation_rules = {}

        self.annotation_rules = {}
        for code in annotation_rules:
            rule = annotation_rules[code]

            if 'Condition' not in rule:
                msg = 'no condition set for configured annotation rule {RULE}'.format(RULE=code)
                logger.warning(self.format_log(msg))

                continue

            self.annotation_rules[code] = {'BackgroundColor': rule.get('BackgroundColor', mod_const.FAIL_COLOR),
                                           'Description': rule.get('Description', code),
                                           'Condition': rule['Condition']}

        try:
            bg_col = entry['BackgroundColor']
        except KeyError:
            self.bg_col = mod_const.DEFAULT_BG_COLOR
        else:
            if isinstance(bg_col, str) and (not bg_col.startswith('#') or len(bg_col) != 7):  # hex color codes
                self.bg_col = mod_const.DEFAULT_BG_COLOR
            else:
                self.bg_col = bg_col

        try:
            self.icon = entry['Icon']
        except KeyError:
            self.icon = None

        try:
            self.tooltip = entry['Tooltip']
        except KeyError:
            self.tooltip = self.description

        self.padding = (0, 0)

        # Dynamic variables
        self.edited = False

    def pad_offset(self):
        """
        Get the total amount of horizontal and vertical padding around the record element.
        """
        padding = self.padding

        try:
            pad_w, pad_h = padding
        except ValueError:
            pad_w = pad_h = padding

        if isinstance(pad_w, tuple) or isinstance(pad_w, list):
            total_w = sum(pad_w)
        elif isinstance(pad_w, int) or isinstance(pad_w, float):
            total_w = int(pad_w) * 2
        elif isinstance(pad_w, type(None)):
            total_w = 0
        else:
            raise TypeError('unsupported value {VAL} provided as horizontal padding around the element'
                            .format(VAL=pad_w))

        if isinstance(pad_h, tuple) or isinstance(pad_h, list):
            total_h = sum(pad_h)
        elif isinstance(pad_h, int) or isinstance(pad_h, float):
            total_h = int(pad_h) * 2
        elif isinstance(pad_h, type(None)):
            total_h = 0
        else:
            raise TypeError('unsupported value {VAL} provided as vertical padding around the element'.format(VAL=pad_h))

        return (total_w, total_h)

    def key_lookup(self, component, rev: bool = False):
        """
        Lookup a record element's GUI element key using the name of the component.

        Arguments:
            component (str): GUI component name (or key if rev is True) of the record element.

            rev (bool): reverse the element lookup map so that element keys are dictionary keys.
        """
        key_map = self.elements if rev is False else {j: i for i, j in self.elements.items()}
        try:
            key = key_map[component]
        except KeyError:
            msg = self.format_log('component "{COMP}" not found in list of element components'.format(COMP=component))
            logger.warning(msg)
            print(key_map)

            raise KeyError(msg)

        return key

    def format_log(self, msg, err: str = None):
        """
        Format the record elements log message.
        """
        msg = '{MSG} - {ERR}'.format(MSG=msg, ERR=err) if err else msg
        msg_fmt = '{TYPE} {NAME}: {MSG}'.format(TYPE=self.etype, NAME=self.name, MSG=msg)

        return msg_fmt

    def is_type(self, etype):
        """
        Determine if a record element is of the given element type.
        """
        map = {'table': ['collection', 'table', 'data_table'],
               'data_table': ['collection', 'table', 'data_table'],
               'component': ['collection', 'table', 'association', 'component', 'component_table'],
               'list': ['collection', 'list', 'data_list'],
               'reference': ['collection', 'list', 'association', 'reference', 'reference_list'],
               'text': ['variable', 'data_variable', 'record_variable', 'text', 'text_variable'],
               'input': ['variable', 'data_variable', 'record_variable', 'input', 'input_variable', 'date',
                         'date_variable'],
               'dropdown': ['variable', 'data_variable', 'record_variable', 'dropdown', 'combo', 'dropdown_variable',
                            'combo_variable'],
               'multiline': ['variable', 'data_variable', 'record_variable', 'multiline', 'multiline_variable',
                             'multi'],
               'checkbox': ['variable', 'data_variable', 'record_variable', 'checkbox'],
               'dependent': ['variable', 'data_variable', 'dependent', 'dependent_variable']
               }

        try:
            element_hierarchy = map[self.etype]
        except KeyError:
            return False

        if etype in element_hierarchy:
            return True
        else:
            return False


class DataTable(RecordElement):
    """
    Record element that displays a data set in the form of a table.

    Attributes:

        elements (list): list of table GUI element keys.

        columns (list): list of table columns.

        display_columns (dict): display names of the table columns.

        display_columns (dict): display columns to hide from the user.

        search_field (str): column used when searching the table.

        parameters (list): list of filter parameters.

        aliases (dict): dictionary of column value aliases.

        tally_rule (str): rules used to calculate totals.

        summary_rules (dict): rules used to summarize the data table.

        nrow (int): number of rows to display.

        widths (list): list of relative column widths. If values are fractions < 1, values will be taken as percentages,
            else relative widths will be calculated relative to size of largest column.

        sort_on (list): columns to sort the table by

        row_color (str): hex code for the color of alternate rows.

        select_mode (str): table selection mode. Options are "browse" and "extended" [Default: extended].
    """

    def __init__(self, name, entry, parent=None):
        """
        Initialize the data table attributes.

        Arguments:
            name (str): name of the configured table element.

            entry (dict): configuration entry for the table element.

            parent (str): name of the parent element.
        """
        super().__init__(name, entry, parent)
        self._supported_stats = ['sum', 'count', 'product', 'mean', 'median', 'mode', 'min', 'max', 'std', 'unique']

        self.etype = 'table'
        record_elements = ('Table', 'Export', 'Total', 'Search', 'Filter', 'Fill', 'FilterFrame', 'CollapseBttn',
                           'Sort', 'Options', 'OptionsFrame', 'OptionsWidth', 'WidthCol1', 'WidthCol2', 'WidthCol3',
                           'TitleBar', 'FilterBar', 'ActionsBar', 'Notes')
        self.elements.update({i: '-{NAME}_{ID}_{ELEM}-'.format(NAME=name, ID=self.id, ELEM=i) for i in record_elements})

        # Element-specific bindings
        elem_key = self.key_lookup('Element')
        return_key = '{}+RETURN+'.format(elem_key)
        open_key = '{}+LCLICK+'.format(elem_key)
        filter_hkey = '{}+FILTER+'.format(elem_key)
        event_elements = ('Element', 'Filter', 'Fill', 'Sort', 'Export', 'CollapseBttn', 'Options')

        self.bindings = {self.elements[i]: i for i in event_elements}
        self.bindings.update({open_key: 'Load', return_key: 'Load', filter_hkey: 'Filter'})

        # Table data collection
        try:
            self.collection = mod_col.DataCollection(name, entry)
        except Exception as e:
            msg = self.format_log('failed to initialize the collection - {ERR}'.format(ERR=e))
            raise AttributeError(msg)

        columns = self.collection.dtypes
        self.columns = list(columns)

        # Control flags that modify the table's behaviour
        try:
            modifiers = entry['Modifiers']
        except KeyError:
            self.modifiers = {'open': True, 'edit': False, 'search': False, 'summary': False, 'filter': False,
                              'export': False, 'fill': False, 'sort': False}
        else:
            self.modifiers = {'open': modifiers.get('open', 1), 'edit': modifiers.get('edit', 0),
                              'search': modifiers.get('search', 0), 'summary': modifiers.get('summary', 0),
                              'filter': modifiers.get('filter', 0), 'export': modifiers.get('export', 0),
                              'fill': modifiers.get('fill', 0), 'sort': modifiers.get('sort', 0)}
            for modifier in self.modifiers:
                try:
                    flag = bool(int(self.modifiers[modifier]))
                except ValueError:
                    logger.warning(self.format_log('modifier {MOD} must be either 0 (False) or 1 (True)'
                                                   .format(MOD=modifier)))
                    flag = False

                self.modifiers[modifier] = flag

        # Buttons that allow modification of the table, such as deleting and importing rows
        try:
            actions = entry['ActionButtons']
        except KeyError:
            actions = {}

        self.actions = []
        for action_name in actions:
            action_entry = actions[action_name]
            try:
                action = TableButton(action_name, self.name, self.id, action_entry)
            except AttributeError as e:
                msg = self.format_log('failed to initialize action {BTTN} - {ERR}'.format(BTTN=action_name, ERR=e))
                logger.error(msg)

                continue
            else:
                self.actions.append(action)
                self.elements[action_name] = action.element_key
                self.bindings.update(action.bindings)

        # Attributes that affect how the table data is displayed
        try:
            display_columns = entry['DisplayColumns']
        except KeyError:
            self.display_columns = {i: i for i in columns}
        else:
            self.display_columns = {}
            for display_column in display_columns:
                if display_column in columns:
                    self.display_columns[display_column] = display_columns[display_column]
                else:
                    msg = self.format_log('display column {COL} not found in the list of table columns'
                                          .format(COL=display_column))
                    logger.warning(msg)

        try:
            hidden_columns = entry['HiddenColumns']
        except KeyError:
            hidden_columns = []

        self.hidden_columns = []
        for hidden_column in hidden_columns:
            if hidden_column in self.display_columns:
                self.hidden_columns.append(hidden_column)
            else:
                msg = self.format_log('hidden column "{COL}" not found in the list of table display columns'
                                      .format(COL=hidden_column))
                logger.warning(msg)
                print(self.display_columns)

        try:
            search_field = entry['SearchField']
        except KeyError:
            self.search_field = None
        else:
            if search_field not in columns:
                msg = self.format_log('search field {FIELD} is not found in list of table columns ... setting to None'
                                      .format(FIELD=search_field))
                logger.warning(msg)
                self.search_field = None
            else:
                self.search_field = (search_field, None)

        try:
            self.filter_entry = entry['FilterParameters']
        except KeyError:
            self.filter_entry = {}

        self.parameters = []
        for param_name in self.filter_entry:
            if param_name not in columns:
                msg = self.format_log('filter parameters "{PARAM}" must be listed in the table columns'
                                      .format(PARAM=param_name))
                logger.warning(msg)
                continue

            param_entry = self.filter_entry[param_name]
            try:
                param = mod_param.initialize_parameter(param_name, param_entry)
            except Exception as e:
                logger.error(self.format_log(e))
                continue

            self.parameters.append(param)
            self.bindings.update(param.bindings)

        try:
            edit_columns = entry['EditColumns']
        except KeyError:
            self.edit_columns = {}
        else:
            self.edit_columns = {}
            for edit_column in edit_columns:
                if edit_column not in columns:
                    msg = self.format_log('editable column "{COL}" must be listed in the table columns'
                                          .format(COL=edit_column))
                    logger.warning(msg)

                    continue
                else:
                    self.edit_columns[edit_column] = edit_columns[edit_column]

        try:
            aliases = entry['Aliases']
        except KeyError:
            aliases = {}
            for display_column in self.display_columns:
                alias_def = settings.fetch_alias_definition(display_column)
                if alias_def:
                    aliases[display_column] = alias_def

        self.aliases = {}
        for alias_column in aliases:
            if alias_column in self.display_columns:
                alias_map = aliases[alias_column]

                # Convert values into correct column datatype
                column_dtype = columns[alias_column]
                if column_dtype in (settings.supported_int_dtypes + settings.supported_cat_dtypes +
                                    settings.supported_str_dtypes):
                    alias_map = {settings.format_value(i, column_dtype): j for i, j in alias_map.items()}

                    self.aliases[alias_column] = alias_map
            else:
                msg = self.format_log('alias column {COL} not found in list of display columns'
                                      .format(COL=alias_column))
                logger.warning(msg)

        try:
            self.tally_rule = entry['TallyRule']
        except KeyError:
            self.tally_rule = None

        try:
            summary_rules = entry['SummaryRules']
        except KeyError:
            summary_rules = {}

        self.summary_rules = {}
        for summary_col in summary_rules:
            if summary_col not in columns:
                msg = self.format_log('summary column "{COL}" is not in the list of table columns'
                                      .format(COL=summary_col))
                logger.warning(msg)
                continue

            summary_stat = summary_rules[summary_col]
            if summary_stat not in self._supported_stats:
                msg = 'unknown statistic {STAT} set for summary column "{COL}"' \
                    .format(STAT=summary_stat, COL=summary_col)
                logger.warning(self.format_log(msg))

                continue

            self.summary_rules[summary_col] = summary_stat

        try:
            self.widths = entry['Widths']
        except KeyError:
            self.widths = None

        try:
            sort_on = entry['SortBy']
        except KeyError:
            sort_on = []

        self._default_sort = []
        for sort_col in sort_on:
            if sort_col in columns:
                self._default_sort.append(sort_col)
            else:
                msg = self.format_log('sort column {COL} not found in table columns'.format(COL=sort_col))
                logger.warning(msg)

        self.sort_on = self._default_sort

        try:
            nrow = int(entry['Rows'])
        except KeyError:
            self.nrow = mod_const.TBL_NROW
        except ValueError:
            msg = self.format_log('input to the Rows parameter must be an integer value')
            logger.warning(msg)
            self.nrow = mod_const.TBL_NROW
        else:  # table must contain at least one row for data display
            self.nrow = 1 if nrow < 1 else nrow

        try:
            row_color = entry['RowColor']
        except KeyError:
            self.row_color = mod_const.TBL_ALT_COLOR
        else:
            if not row_color.startswith('#') or not len(row_color) == 7:
                msg = self.format_log('row color {COL} is not a valid hexadecimal code'.format(COL=row_color))
                logger.warning(msg)
                self.row_color = mod_const.TBL_BG_COLOR
            else:
                self.row_color = row_color

        try:
            select_mode = entry['SelectMode']
        except KeyError:
            self.select_mode = None
        else:
            if select_mode not in ('extended', 'browse'):
                self.select_mode = None
            else:
                self.select_mode = select_mode

        try:
            self.required_columns = entry['RequiredColumns']
        except KeyError:
            self.required_columns = []

        self.level = 0

        # Dynamic attributes
        self._height_offset = 0
        self._frame_height = 0
        self._dimensions = (0, 0)
        self._min_size = (0, 0)

        self._selected_rows = []
        self.index_map = {}
        self._colors = []

    def _display_header(self):
        """
        Return the visible header of the display table.
        """
        display_map = self.display_columns
        hidden_columns = self.hidden_columns

        header = []
        for column in display_map:
            if column in hidden_columns:
                continue

            display_column = display_map[column]
            header.append(display_column)

        return header

    def _update_column_widths(self, window, width: int = None):
        """
        Update the sizes of the data table or summary table columns.
        """
        header = self._display_header()
        elem_key = self.key_lookup('Element')
        widths = self.widths
        nrow = self.get_table_dimensions(window)[1]

        column_widths = self._calc_column_widths(header, width=width, pixels=True, widths=widths)
        for index, column in enumerate(header):
            column_width = column_widths[index]
            window[elem_key].Widget.column(column, width=column_width)

            window[elem_key].update(num_rows=nrow)  # required for table size to update

    def _calc_column_widths(self, header, width: int = None, size: int = None, pixels: bool = False,
                            widths: dict = None):
        """
        Calculate the width of the table columns based on the number of columns displayed.

        Arguments:
            header (list): list of table headers.

            width (int): width of the table.

            size (int): font size of the table characters.

            pixels (bool): width is in pixels instead of characters [Default: True].

            widths (dict): column relative sizes [Default: all columns are equal].
        """
        # Size of data
        ncol = len(header)

        if ncol < 1:  # no columns in table
            return []

        if not width:
            width = mod_const.TBL_WIDTH

        # Set table width based on whether size in pixels or characters
        if pixels:
            tbl_width = width
        else:
            if not size:
                size = mod_const.TBL_FONT[1]

            tbl_width = width / size

        if widths is not None:
            # Set an average width for unspecified columns
            avg_width = sum(widths.values()) / len(widths.values())
            col_widths = []
            for colname in header:
                try:
                    col_widths.append(float(widths[colname]))
                except (ValueError, KeyError):  # unsupported type or column not specified
                    col_widths.append(avg_width)

            # Adjust widths to the sum total
            width_sum = sum(col_widths)
            adj_widths = [i / width_sum for i in col_widths]

            # Calculate column lengths
            lengths = [int(tbl_width * i) for i in adj_widths]
        else:
            # When table columns not long enough, need to adjust so that the
            # table fills the empty space.
            try:
                max_size_per_col = int(tbl_width / ncol)
            except ZeroDivisionError:
                logger.warning(self.format_log('division by zero error encountered while attempting to calculate '
                                               'column widths'))
                max_size_per_col = int(tbl_width / 10)

            # Each column has size == max characters per column
            lengths = [max_size_per_col for _ in header]

        # Add any remainder evenly between columns
        remainder = tbl_width - sum(lengths)

        index = 0
        for one in [1 for _ in range(int(remainder))]:
            if index > ncol - 1:
                index = 0
            lengths[index] += one
            index += one

        return lengths

    def enabled(self, bttn_name):
        """
        Determine if a table action button is disabled or not.
        """
        try:
            bttn = self.fetch_parameter(bttn_name, filters=False)
        except KeyError:
            enabled = False
        else:
            enabled = not bttn.disabled

        return enabled

    def enable(self, window):
        """
        Enable data table element actions.
        """
        logger.debug(self.format_log('enabling actions'))

        action_bttns = self.actions
        for action_bttn in action_bttns:
            action_bttn.toggle(window, off=False)

    def disable(self, window):
        """
        Disable data table element actions.
        """
        logger.debug(self.format_log('disabling actions'))

        action_bttns = self.actions
        for action_bttn in action_bttns:
            action_bttn.toggle(window, off=True)

    def fetch_parameter(self, identifier, by_key: bool = False, filters: bool = True):
        """
        Fetch a filter parameter by name or event key.
        """
        if filters:
            parameters = self.parameters
        else:
            parameters = self.actions

        if by_key is True:
            match = re.match(r'-(.*?)-', identifier)
            if not match:
                raise KeyError('unknown format provided for element identifier {ELEM}'.format(ELEM=identifier))
            identifier = match.group(0)  # identifier returned if match
            element_key = match.group(1)  # element key part of the identifier after removing any binding

            element_type = element_key.split('_')[-1]
            element_names = []
            for parameter in parameters:
                try:
                    element_name = parameter.key_lookup(element_type)
                except KeyError:
                    element_name = None

                element_names.append(element_name)
        else:
            element_names = [i.name for i in parameters]

        if identifier in element_names:
            index = element_names.index(identifier)
            parameter = parameters[index]
        else:
            raise KeyError('element {ELEM} not found in list of {NAME} data elements'
                           .format(ELEM=identifier, NAME=self.name))

        return parameter

    def reset(self, window, reset_filters: bool = True, collapse: bool = True):
        """
        Reset the data table to default.

        Arguments:
            window (Window): GUI window.

            reset_filters (bool): also reset filter parameter values [Default: True].

            collapse (bool): collapse supplementary table frames [Default: True].
        """
        # Reset dynamic attributes
        self.collection.reset()
        self.index_map = {}
        self.edited = False
        self.sort_on = self._default_sort

        # Reset table filter parameters
        if reset_filters:
            for param in self.parameters:
                param.reset(window)

        # Collapse visible frames
        if collapse:
            frame_key = self.key_lookup('FilterFrame')
            if not window[frame_key].metadata['disabled'] and window[frame_key].metadata['visible']:
                self.collapse_expand(window)

        # Reset table dimensions
        self.set_table_dimensions(window)

        # Update the table display
        self.update_display(window)

    def run_event(self, window, event, values):
        """
        Run a table GUI event.
        """
        collection = self.collection
        elem_key = self.key_lookup('Element')

        # Table events
        update_event = False
        triggers = {'ValueEvent': False, 'ResizeEvent': False, 'DisplayEvent': False}

        # Event is a table filter parameter
        param_events = [i for param in self.parameters for i in param.bindings]
        if event in param_events:
            try:
                param = self.fetch_parameter(event, by_key=True)
            except KeyError:
                logger.error(self.format_log('unable to find parameter associated with event key {KEY}'
                                             .format(KEY=event)))
            else:
                param.run_event(window, event, values)

        # Event belongs to a table element
        try:
            element_event = self.bindings[event]
        except KeyError:
            msg = 'GUI event {EVENT} is not a {NAME} event'.format(EVENT=event, NAME=self.name)
            logger.warning(self.format_log(msg))

            return triggers
        else:
            logger.debug(self.format_log('running table event {EVENT}'.format(EVENT=element_event)))

            # Single click to select a table row
            if element_event == 'Element':
                selected_rows = values[elem_key]
                self._selected_rows = selected_rows
                self.update_annotation(window)

            # Double-click or return key pressed to open table row
            elif element_event == 'Load':
                # Close options panel, if open
                self.set_table_dimensions(window)

                # Find the row selected by the user
                try:
                    select_row_index = values[elem_key][0]
                except IndexError:  # user double-clicked too quickly
                    msg = 'table row could not be selected'
                    logger.debug(self.format_log(msg))
                else:
                    self._selected_rows = [select_row_index]
                    self.update_annotation(window)

                    # Get the real index of the selected row
                    index = self.get_index(select_row_index)
                    update_event = self.run_table_event(index)

            elif element_event == 'Search':
                search_key = self.key_lookup('Search')

                # Update the search field value
                search_col = self.search_field[0]
                search_value = values[search_key]
                self.search_field = (search_col, search_value)

                self.update_display(window)

            elif element_event == 'CollapseBttn':
                self.collapse_expand(window)

            # Click filter Apply button to apply filtering to table
            elif element_event == 'Filter':
                # Update parameter values
                for param in self.parameters:
                    try:
                        param.value = param.format_value(values)
                    except ValueError:
                        msg = 'failed to filter table rows'
                        err = 'incorrectly formatted value provided to filter parameter {}'.format(param.description)
                        logger.error(self.format_log(msg, err=err))
                        mod_win2.popup_error(msg)

                        return triggers

                # Update the display table to show the filtered table
                self.update_display(window)

            # Click to open table options panel
            elif element_event == 'Options':
                frame_key = self.key_lookup('OptionsFrame')

                if window[frame_key].metadata['visible'] is False:
                    window[frame_key].metadata['visible'] = True

                    tbl_width, tbl_height = window[elem_key].get_size()

                    # Reduce table size
                    frame_w = 220
                    new_width = tbl_width - frame_w - 4 if tbl_width - frame_w - 4 > 0 else 0
                    logger.debug(self.format_log('resizing the table from {W} to {NW} to accommodate the options frame '
                                                 'of width {F}'.format(W=tbl_width, NW=new_width, F=frame_w)))
                    self._update_column_widths(window, width=new_width)

                    # Reveal the options frame
                    window[frame_key].update(visible=True)
                    window[frame_key].expand(expand_y=True)

                    # Update the display table to show annotations properly
                    self.update_display(window)
                else:
                    self.set_table_dimensions(window)

            # Sort column selected from menu of sort columns
            elif element_event == 'Sort':
                sort_key = self.key_lookup('Sort')
                sort_on = self.sort_on
                display_map = {j: i for i, j in self.display_columns.items()}

                # Get sort column
                display_col = values[sort_key]
                try:
                    sort_col = display_map[display_col]
                except KeyError:
                    logger.warning(self.format_log('column "{COL}" must be a display column in order to sort'
                                                   .format(COL=display_col)))
                else:
                    if sort_col in sort_on:
                        # Remove column from sortby list
                        self.sort_on.remove(sort_col)
                    else:
                        # Add column to sortby list
                        self.sort_on.append(sort_col)

                # Update the display table to show the sorted values
                self.update_display(window)

            # NA value fill method selected from menu of fill methods
            elif element_event == 'Fill':
                fill_key = self.key_lookup('Fill')
                display_map = {j: i for i, j in self.display_columns.items()}

                # Get selected rows, if any
                select_row_indices = values[elem_key]

                # Get the real indices of the selected rows
                indices = self.get_index(select_row_indices)
                if len(indices) < 2:
                    msg = 'table fill requires more than one table rows to be selected'
                    logger.warning(self.format_log(msg))

                    return triggers

                # Find the selected column to fill
                display_col = values[fill_key]
                try:
                    fill_col = display_map[display_col]
                except KeyError:
                    msg = self.format_log('fill display column {COL} must have a one-to-one mapping with a table '
                                          'display column'.format(COL=display_col))
                    logger.warning(msg)

                    return triggers

                # Fill in NA values
                collection.fill(indices=indices, fields=fill_col)
                update_event = True

            elif element_event == 'Export':
                outfile = sg.popup_get_file('', title='Export table display', save_as=True,
                                            default_extension='xlsx', no_window=True,
                                            file_types=(('XLS - Microsoft Excel', '*.xlsx'),))

                if outfile:
                    logger.info(
                        self.format_log('exporting the display table to spreadsheet {FILE}'.format(FILE=outfile)))

                    export_df = self.export_table()
                    try:
                        export_df.to_excel(outfile, engine='openpyxl', header=True, index=False)
                    except Exception as e:
                        msg = 'failed to save table to file to {FILE} - {ERR}'.format(FILE=outfile, ERR=e)
                        logger.exception(self.format_log(msg))
                        mod_win2.popup_error(msg)
                else:
                    logger.warning(self.format_log('no output file selected'))

            # Delete rows button clicked
            elif element_event == 'Delete':
                if not self.enabled(element_event):
                    return triggers

                # Find rows selected by user for deletion
                select_row_indices = values[elem_key]

                # Get the real indices of the selected rows
                indices = self.get_index(select_row_indices)
                if len(indices) > 0:
                    collection.delete(indices)
                    update_event = True

            # Import rows button clicked
            elif element_event == 'Import':
                if not self.enabled(element_event):
                    return triggers

                # Close options panel, if open
                self.set_table_dimensions(window)

                try:
                    import_rows = self.import_rows()
                except Exception as e:
                    msg = 'failed to run table import event'
                    logger.exception(self.format_log(msg, err=e))
                else:
                    if not import_rows.empty:
                        collection.append(import_rows, new=True)

                    update_event = True

        if update_event:
            self.edited = True
            triggers['ValueEvent'] = True

            # Update the display table to show the new table values
            self.update_display(window)

        return triggers

    def run_table_event(self, index):
        """
        Run a table action event.
        """
        collection = self.collection

        logger.debug(self.format_log('opening row at real index {IND} for editing'.format(IND=index)))

        edited_row = self.edit_row(index)
        if edited_row is None:
            update_event = False
        else:
            update_event = collection.update_entry(index, edited_row)

        return update_event

    def deselect(self, window, indices: list = None):
        """
        Deselect selected table rows.

        Arguments:
            window: GUI window.

            indices (list): only deselect rows at these indices.
        """
        elem_key = self.key_lookup('Element')
        current_rows = self._selected_rows

        if isinstance(indices, int):
            indices = [indices]

        if indices:
            selected_rows = [i for i in current_rows if i not in indices]
        else:
            selected_rows = []

        self._selected_rows = selected_rows
        window[elem_key].update(select_rows=selected_rows, row_colors=self._colors)

    def select(self, window, indices):
        """
        Manually select rows at the given display indices.

        Arguments:
            window: GUI window.

            indices: list or series of indices corresponding to the desired rows to select.
        """
        elem_key = self.key_lookup('Element')

        if not isinstance(indices, list) or isinstance(indices, pd.Series):
            raise TypeError('indices argument must be a list or pandas series')

        first_ind = indices[0]
        total_rows = self.data(display_rows=True).shape[0]
        position = first_ind / total_rows

        self._selected_rows = indices
        window[elem_key].update(select_rows=indices, row_colors=self._colors)
        window[elem_key].set_vscroll_position(position)

    def selected(self, real: bool = False):
        """
        Return currently selected table rows.

        Arguments:
            real (bool): return the real indices of the selected rows instead of the display indices [Default: False].
        """
        current_rows = self._selected_rows

        if real:
            index_map = self.index_map

            try:
                selected_rows = [index_map[i] for i in current_rows]
            except KeyError:
                msg = 'missing index information for one or more selected rows'.format(NAME=self.name)
                logger.warning(self.format_log(msg))

                selected_rows = current_rows
        else:
            selected_rows = current_rows

        return selected_rows

    def get_index(self, selected, real: bool = True):
        """
        Return the real indices of selected table rows.

        Arguments:
            selected (list): indices of the selected rows.

            real (bool): get the real index of the selected table row [Default: True]
        """
        if real:
            index_map = self.index_map
        else:
            index_map = {j: i for i, j in self.index_map.items()}

        try:
            if isinstance(selected, int):
                indices = index_map[selected]
            else:
                indices = [index_map[i] for i in selected]
        except KeyError:
            msg = 'missing index information for one or more selected rows'.format(NAME=self.name)
            logger.warning(self.format_log(msg))
            indices = selected

        return indices

    def bind_keys(self, window):
        """
        Set hotkey bindings.
        """
        elem_key = self.key_lookup('Element')
        window[elem_key].bind('<Control-f>', '+FILTER+')

        # Bind parameter hotkeys
        for parameter in self.parameters:
            parameter.bind_keys(window)

        # Bind table element hotkeys
        level = self.level
        if level < 2:
            if self.modifiers['open']:
                window[elem_key].bind('<Return>', '+RETURN+')
                window[elem_key].bind('<Double-Button-1>', '+LCLICK+')

            actions = self.actions
            for action_bttn in actions:
                action_bttn.bind_keys(window, elem_key)

    def data(self, all_rows: bool = False, display_rows: bool = False, edited_rows: bool = False,
             deleted_rows: bool = False, added_rows: bool = False, indices=None):
        """
        Return the collection data.

        Arguments:
            all_rows (bool): return all table rows, including the deleted rows [Default: False].

            display_rows (bool): return only the display rows [Default: False].

            edited_rows (bool): return only rows that have been edited in the table [Default: False].

            deleted_rows (bool): return only rows that have been deleted from the table [Default: False].

            added_rows (bool): return only rows that have been added to the table [Default: False].

            indices: list or series of table indices.

        Returns:
            df (DataFrame): table data matching the selection requirements.
        """
        collection = self.collection

        if display_rows:
            df = collection.data()

            # Filter the table rows, if applicable
            search = self.search_field
            try:
                search_col, search_value = search
            except (TypeError, ValueError):
                search_col = search_value = None

            if not search_value:  # no search value provided in the search field, try the filter parameters
                logger.debug(self.format_log('filtering the display table based on user-supplied parameter values'))

                parameters = self.parameters
                for param in parameters:
                    df = param.filter_table(df)
            else:
                logger.debug(self.format_log('filtering the display table based on search value {VAL}'
                                             .format(VAL=search_value)))

                try:
                    df = df[df[search_col].str.contains(search_value, case=False, regex=True)]
                except KeyError:
                    msg = self.format_log('search field {COL} not found in list of table columns'
                                          .format(NAME=self.name, COL=search_col))
                    logger.warning(msg)
        else:
            current = (not all_rows) if indices is None or deleted_rows is False else False
            df = collection.data(current=current, edited_only=edited_rows, deleted_only=deleted_rows,
                                 added_only=added_rows, indices=indices)

        return df

    def update_display(self, window, annotations: dict = None):
        """
        Format object elements for display.

        Arguments:
            window (Window): GUI window.

            annotations (dict): custom row color annotations to use instead of generating annotations from the
                configured annotation rules.
        """
        is_float_dtype = pd.api.types.is_float_dtype
        highlight_col = mod_const.SELECTED_BG_COLOR
        white_text_col = mod_const.WHITE_TEXT_COLOR
        def_bg_col = mod_const.DEFAULT_BG_COLOR
        text_col = mod_const.DEFAULT_TEXT_COLOR

        tbl_key = self.key_lookup('Element')
        annotations = {} if annotations is None else annotations

        logger.debug(self.format_log('formatting table for displaying'))

        # Sort table and update table sorting information
        self.collection.sort(self.sort_on)

        if self.modifiers['sort']:  # selected sort columns should be highlighted in the sort button menu
            sort_key = self.key_lookup('Sort')

            display_map = {j: i for i, j in self.display_columns.items()}
            for menu_index, display_col in enumerate(display_map):
                display_val = display_map[display_col]
                if display_val in self.sort_on:
                    # Get order of sort column
                    sort_order = self.sort_on.index(display_val) + 1

                    # Add highlight to menu item
                    window[sort_key].TKMenu.entryconfig(menu_index, label='{} - {}'.format(sort_order, display_col),
                                                        foreground=white_text_col, background=highlight_col)
                    window[sort_key].TKButtonMenu.configure(menu=window[sort_key].TKMenu)
                else:
                    # Remove highlight from menu item
                    window[sort_key].TKMenu.entryconfig(menu_index, label=display_col,
                                                        foreground=text_col, background=def_bg_col)
                    window[sort_key].TKButtonMenu.configure(menu=window[sort_key].TKMenu)

        # Find only those rows that should currently be displayed
        df = self.data(display_rows=True)

        # Edit the index map to reflect what is currently displayed
        display_indices = df.index.tolist()
        self.index_map = {i: j for i, j in enumerate(display_indices)}

        annotations = {i: j for i, j in annotations.items() if i in display_indices}

        df = df.reset_index()

        # Prepare annotations
        if len(annotations) < 1:  # highlight table rows using configured annotation rules
            annotations = self.annotate_rows(df)
            row_colors = [(i, self.annotation_rules[j]['BackgroundColor']) for i, j in annotations.items()]
        else:  # use custom annotations to highlight table rows
            row_colors = [(i, j) for i, j in annotations.items()]

        self._colors = row_colors

        # Format the table values
        display_df = self.format_display_values(df)

        # Update the GUI with table values and annotations
        data = display_df.values.tolist()
        window[tbl_key].update(values=data, row_colors=row_colors)

        # Update table totals
        try:
            tbl_total = self.calculate_total(df)
        except Exception as e:
            msg = self.format_log('failed to calculate table totals - {ERR}'.format(ERR=e))
            logger.warning(msg)
            tbl_total = 0

        if is_float_dtype(type(tbl_total)):
            tbl_total = '{:,.2f}'.format(tbl_total)
        else:
            tbl_total = str(tbl_total)

        total_key = self.key_lookup('Total')
        window[total_key].update(value=tbl_total)

        # Update the table tooltip
        tooltip = self.format_tooltip()
        window[tbl_key].set_tooltip(tooltip)

        self.deselect(window)
        self.update_annotation(window)

        return display_df

    def update_annotation(self, window):
        """
        Set the row annotation, if any rows are selected.
        """
        annot_key = self.key_lookup('Notes')

        indices = self.selected(real=True)
        df = self.data(indices=indices)
        annotations = self.annotate_rows(df)

        if len(indices) > 0:
            row_index = indices[0]
            if row_index in annotations:
                annotation_rule = annotations[row_index]
                annotation = self.annotation_rules[annotation_rule]['Description']
            else:
                annotation = ''
        else:
            annotation = ''

        window[annot_key].update(value=annotation)
        window[annot_key].set_tooltip(annotation)

    def format_tooltip(self, annotations: dict = None):
        """
        Set the element tooltip.
        """
        custom_tooltip = self.tooltip

        tooltip = []
        if custom_tooltip:
            tooltip.append(custom_tooltip)
            tooltip.append('')

        summary = self.summarize(display=True)
        for summary_column, summary_value in summary.items():
            tooltip.append('{}: {}'.format(summary_column, summary_value))

        if annotations:
            selected_ind = self.selected()
            if len(selected_ind) == 1 and selected_ind[0] in annotations:
                annotation_rule = annotations[selected_ind[0]]
                annotation = self.annotation_rules[annotation_rule]['Description']

                tooltip.append('')
                tooltip.append(annotation)

        return '\n'.join(tooltip)

    def format_display_values(self, df: pd.DataFrame = None):
        """
        Format the table values for display.
        """
        df = self.data(display_rows=True) if df is None else df

        # Subset dataframe by specified columns to display
        display_df = pd.DataFrame()
        display_map = self.display_columns
        for column in display_map:
            column_alias = display_map[column]

            try:
                col_to_add = self.format_display_column(df, column)
            except Exception as e:
                msg = 'failed to format column {COL} for display'.format(COL=column)
                logger.exception(self.format_log('{MSG} - {ERR}'.format(MSG=msg, ERR=e)))

                continue

            display_df[column_alias] = col_to_add

        return display_df.astype('object').fillna('')

    def format_display_column(self, df, column):
        """
        Format the values of a table column for display.
        """
        try:
            display_col = self.collection.format_display_field(column, data=df)
        except KeyError:
            msg = 'column {COL} not found in the table dataframe'.format(COL=column)
            logger.error(self.format_log(msg))

            raise KeyError(msg)

        return display_col

    def format_display_column_old(self, df, column):
        """
        Format the values of a table column for display.
        """
        is_float_dtype = pd.api.types.is_float_dtype
        is_integer_dtype = pd.api.types.is_integer_dtype
        is_bool_dtype = pd.api.types.is_bool_dtype
        is_datetime_dtype = pd.api.types.is_datetime64_any_dtype
        is_string_dtype = pd.api.types.is_string_dtype

        aliases = self.aliases

        try:
            display_col = df[column]
        except KeyError:
            msg = 'column {COL} not found in the table dataframe'.format(COL=column)
            logger.error(self.format_log(msg))

            raise KeyError(msg)

        dtype = display_col.dtype
        if is_float_dtype(dtype) and self.collection.dtypes[column] == 'money':
            display_col = display_col.apply(settings.format_display_money)
        elif is_datetime_dtype(dtype):
            display_col = display_col.apply(settings.format_display_date)
        elif is_bool_dtype(dtype):
            display_col = display_col.apply(lambda x: '✓' if x is True else '')
        elif is_integer_dtype(dtype) or is_string_dtype(dtype):
            if column in aliases:
                alias_map = aliases[column]
                display_col = display_col.apply(lambda x: alias_map[x] if x in alias_map else x)

        return display_col.astype('object').fillna('')

    def summarize_column(self, column, indices: list = None):
        """
        Summarize table column values.
        """
        try:
            col_stat = self.summary_rules[column]
        except KeyError:
            col_stat = None

        summary = self.collection.summarize_field(column, indices=indices, statistic=col_stat)

        return summary

    def summarize(self, indices: list = None, display: bool = False):
        """
        Generate the table summary on the summary rules.
        """
        collection = self.collection
        if not indices:
            indices = self.data(display_rows=True).index.tolist()

        # Calculate totals defined by summary rules
        summary = {}
        rules = self.summary_rules
        for column in rules:
            summary_stat = rules[column]

            summary_total = collection.summarize_field(column, indices=indices, statistic=summary_stat)
            if display:
                display_cols = self.display_columns
                try:
                    summary_col = display_cols[column]
                except KeyError:
                    summary_col = column

                dtype = collection.dtypes[column]
                summary_total = settings.format_display(summary_total, dtype)
            else:
                summary_col = column

            summary[summary_col] = summary_total

        return summary

    def annotate_rows(self, df):
        """
        Annotate the provided dataframe using configured annotation rules.
        """
        rules = self.annotation_rules
        if df.empty or rules is None:
            return {}

        logger.debug(self.format_log('annotating display table on configured annotation rules'))

        annotations = {}
        rows_annotated = []
        for annot_code in rules:
            logger.debug(self.format_log('annotating table based on configured annotation rule "{CODE}"'
                                         .format(CODE=annot_code)))
            rule = rules[annot_code]
            annot_condition = rule['Condition']
            try:
                # results = mod_dm.evaluate_condition_set(df, {annot_code: annot_condition})
                results = mod_dm.evaluate_condition(df, annot_condition)
            except Exception as e:
                logger.exception(self.format_log('failed to annotate data table using annotation rule {CODE} - {ERR}'
                                                 .format(CODE=annot_code, ERR=e)))
                continue

            for row_index, result in results.iteritems():
                if result:  # condition for the annotation has been met
                    if row_index in rows_annotated:
                        continue
                    else:
                        annotations[row_index] = annot_code
                        rows_annotated.append(row_index)

        return annotations

    def layout(self, size: tuple = (None, None), padding: tuple = None, tooltip: str = None, editable: bool = True,
               overwrite: bool = False, level: int = 0, bg_color: str = None):
        """
        Generate a window layout for the table record element.
        """
        table_name = self.description
        modifiers = self.modifiers

        self.level = level

        display_df = self.format_display_values()

        tooltip = tooltip if tooltip is not None else ''
        search_field = self.search_field
        select_mode = self.select_mode

        is_disabled = False if (editable is True and level < 1) or overwrite is True else True

        # Element keys
        keyname = self.key_lookup('Element')
        print_key = self.key_lookup('Export')
        search_key = self.key_lookup('Search')
        total_key = self.key_lookup('Total')
        fill_key = self.key_lookup('Fill')
        options_key = self.key_lookup('Options')
        sort_key = self.key_lookup('Sort')
        col1width_key = self.key_lookup('WidthCol1')
        col2width_key = self.key_lookup('WidthCol2')
        col3width_key = self.key_lookup('WidthCol3')

        # Element settings
        text_col = mod_const.DEFAULT_TEXT_COLOR  # standard text color
        select_text_col = mod_const.WHITE_TEXT_COLOR  # row text highlight color
        select_bg_col = mod_const.TBL_SELECT_COLOR
        disabled_text_col = mod_const.DISABLED_TEXT_COLOR  # disabled button text
        disabled_bg_col = mod_const.DISABLED_BG_COLOR  # disabled button background
        alt_col = self.row_color  # alternate row color
        row_col = self.bg_col  # default primary table color is white
        header_col = mod_const.TBL_HEADER_COLOR if bg_color is None else bg_color  # color of the header background
        frame_col = mod_const.FRAME_COLOR  # background color of the table frames
        border_col = mod_const.BORDER_COLOR  # background color of the collapsible bars and the table frame

        pad = padding if padding and isinstance(padding, tuple) else self.padding
        self.padding = pad
        pad_el = mod_const.ELEM_PAD
        pad_h = mod_const.HORZ_PAD
        pad_v = mod_const.VERT_PAD

        font = mod_const.MAIN_FONT
        annot_font = mod_const.MID_FONT
        bold_font = mod_const.BOLD_FONT
        tbl_font = mod_const.TBL_FONT
        header_font = mod_const.TBL_HEADER_FONT
        title_font = mod_const.BOLD_LARGE_FONT
        font_size = tbl_font[1]

        # Hotkey text
        hotkeys = settings.hotkeys
        options_shortcut = hotkeys['-HK_TBL_OPTS-'][2]
        filter_shortcut = hotkeys['-HK_TBL_FILTER-'][2]

        # Table dimensions
        width, height = size
        row_h = mod_const.TBL_ROW_HEIGHT
        nrow = self.nrow
        scroll_w = mod_const.SCROLL_WIDTH
        border_w = 1 * 4

        width = width if width is not None else mod_const.TBL_WIDTH

        isize = mod_const.IN1_WIDTH

        header_col_size = 200
        min_col_size = 10

        bar_h = 26  # height of the title and totals bars in pixels
        cbar_h = 22  # height of the collapsible panel bars in pixels
        bttn_h = 30  # height of the filter apply button
        annot_h = 30  # height of the annotation multiline

        height_offset = 0

        # Row layouts

        # Table filter parameters layout
        filter_params = self.parameters
        if len(filter_params) <= 2 or len(filter_params) == 4:
            use_center = False
            param_w = int(width * 0.35 / 10)
            col2_w = int(width * 0.1)
            col1_w = col3_w = int(width * 0.45)
        else:
            use_center = True
            param_w = int(width * 0.30 / 10)
            col1_w = col2_w = col3_w = int(width * 0.33)

        left_cols = [[sg.Canvas(key=col1width_key, size=(col1_w, 0), background_color=frame_col)]]
        center_cols = [[sg.Canvas(key=col2width_key, size=(col2_w, 0), background_color=frame_col)]]
        right_cols = [[sg.Canvas(key=col3width_key, size=(col3_w, 0), background_color=frame_col)]]

        i = 0
        for parameter in filter_params:
            param_cols = parameter.layout(padding=(0, 0), size=(param_w, 1), bg_col=frame_col,
                                          auto_size_desc=False, border=False)
            for param_layout in param_cols:
                i += 1
                if use_center is True:
                    index_mod = i % 3
                else:
                    index_mod = i % 2

                if use_center is True and index_mod == 1:
                    left_cols.append([param_layout])
                elif use_center is True and index_mod == 2:
                    center_cols.append([param_layout])
                elif use_center is True and index_mod == 0:
                    right_cols.append([param_layout])
                elif use_center is False and index_mod == 1:
                    left_cols.append([param_layout])
                    center_cols.append([sg.Canvas(size=(0, 0), visible=True)])
                elif use_center is False and index_mod == 0:
                    right_cols.append([param_layout])
                else:
                    logger.warning(self.format_log('cannot assign layout for table filter parameter {PARAM}'
                                                   .format(PARAM=parameter.name)))

        n_filter_rows = ceiling(i / 3) if use_center else ceiling(i / 2)
        frame_h = row_h * n_filter_rows + (ceiling(bttn_h / row_h) * row_h - bttn_h)
        filters = [[sg.Canvas(size=(0, frame_h), background_color=frame_col),
                    sg.Col(left_cols, pad=(0, 0), background_color=frame_col, justification='l',
                           element_justification='c', vertical_alignment='t'),
                    sg.Col(center_cols, pad=(0, 0), background_color=frame_col, justification='c',
                           element_justification='c', vertical_alignment='t'),
                    sg.Col(right_cols, pad=(0, 0), background_color=frame_col, justification='r',
                           element_justification='c', vertical_alignment='t')],
                   [sg.Col([[mod_lo.B2('Apply', key=self.key_lookup('Filter'), disabled=False,
                                       button_color=(alt_col, border_col),
                                       disabled_button_color=(disabled_text_col, disabled_bg_col),
                                       tooltip='Apply table filters ({})'.format(filter_shortcut))]],
                           element_justification='c', vertical_alignment='c', background_color=frame_col, expand_x=True,
                           expand_y=True)]]

        if len(filter_params) > 0 and modifiers['filter'] is True:
            filter_disabled = False
            height_offset += cbar_h  # height of the collapsible bar
            frame_h = frame_h + bttn_h  # height of the filter parameters and apply button
        else:
            filter_disabled = True
            frame_h = 0
            height_offset += 2  # invisible elements have a footprint

        self._frame_height = frame_h

        row1 = [
            sg.Col([[sg.Canvas(size=(0, cbar_h), background_color=border_col),
                     sg.Image(data=mod_const.FILTER_ICON, pad=((0, pad_h), 0), background_color=border_col),
                     sg.Text('Filter', pad=((0, pad_h), 0), text_color=select_text_col,
                             background_color=border_col),
                     sg.Button('', image_data=mod_const.UNHIDE_ICON, key=self.key_lookup('CollapseBttn'),
                               button_color=(text_col, border_col), border_width=0,
                               tooltip='Collapse filter panel')]],
                   key=self.key_lookup('FilterBar'), element_justification='c', background_color=border_col,
                   expand_x=True, visible=(not filter_disabled), vertical_alignment='c')]
        row2 = [sg.pin(sg.Col(filters, key=self.key_lookup('FilterFrame'), background_color=frame_col,
                              visible=False, expand_x=True, vertical_alignment='c',
                              metadata={'visible': False, 'disabled': filter_disabled}))]

        # Table title
        title_bar = [sg.Canvas(size=(0, bar_h), background_color=header_col)]
        if modifiers['search'] and search_field is not None:
            search_layout = [[sg.Canvas(size=(header_col_size, 0), background_color=header_col)],
                             [sg.Canvas(size=(0, bar_h), background_color=header_col),
                              sg.Frame('', [
                                  [sg.Image(data=mod_const.SEARCH_ICON, background_color=row_col, pad=((0, pad_h), 0)),
                                   sg.Input(default_text='', key=search_key, size=(isize - 2, 1),
                                            border_width=0, do_not_clear=True, background_color=row_col,
                                            enable_events=True, tooltip='Search table')]],
                                       background_color=row_col, relief='sunken')]]
        else:
            search_layout = [[sg.Canvas(size=(header_col_size, 0), background_color=header_col)],
                             [sg.Canvas(size=(0, bar_h), background_color=header_col)]]

        title_bar.append(sg.Col(search_layout, justification='l', element_justification='l', vertical_alignment='c',
                                background_color=header_col))

        if table_name is not None:
            tb_layout = [[sg.Canvas(size=(0, bar_h), background_color=header_col),
                          sg.Text(table_name, font=title_font, background_color=header_col)]]
        else:
            tb_layout = [[sg.Canvas(size=(header_col_size, 0), background_color=header_col)],
                         [sg.Canvas(size=(0, bar_h), background_color=header_col)]]

        title_bar.append(sg.Col(tb_layout, justification='c', element_justification='c', vertical_alignment='c',
                                background_color=header_col, expand_x=True))

        if any([modifiers['fill'], modifiers['sort'], modifiers['export']]):
            options_layout = [[sg.Canvas(size=(header_col_size, 0), background_color=header_col)],
                              [sg.Canvas(size=(0, bar_h), background_color=header_col),
                               sg.Button('', key=options_key, image_data=mod_const.SETTINGS_ICON, border_width=0,
                                         button_color=(text_col, header_col),
                                         tooltip='Show additional table options ({})'.format(options_shortcut))]]
        else:
            options_layout = [[sg.Canvas(size=(header_col_size, 0), background_color=header_col)],
                              [sg.Canvas(size=(0, bar_h), background_color=header_col)]]

        title_bar.append(sg.Col(options_layout, justification='r', element_justification='r', vertical_alignment='c',
                                background_color=header_col))

        row3 = [sg.Col([title_bar], key=self.key_lookup('TitleBar'), background_color=header_col, expand_x=True,
                       expand_y=True, vertical_alignment='c')]

        height_offset += bar_h  # height of the title bar

        # Data table
        row4 = []

        display_header = self._display_header()
        header = display_df.columns.tolist()

        vis_map = []
        for display_column in header:
            if display_column in display_header:
                vis_map.append(True)
            else:
                vis_map.append(False)

        min_w = scroll_w + border_w + len(display_header) * min_col_size
        tbl_width = width - scroll_w - border_w if width >= min_w else min_w - scroll_w - border_w
        col_widths = self._calc_column_widths(display_header, width=tbl_width, size=font_size, pixels=False,
                                              widths=self.widths)

        events = True if level < 2 else False
        data = display_df.values.tolist()
        row4.append(sg.Table(data, key=keyname, headings=header, visible_column_map=vis_map, pad=(0, 0), num_rows=nrow,
                             row_height=row_h, alternating_row_color=alt_col, background_color=row_col,
                             text_color=text_col, selected_row_colors=(select_text_col, select_bg_col), font=tbl_font,
                             header_font=header_font, display_row_numbers=False, auto_size_columns=False,
                             col_widths=col_widths, enable_events=events, bind_return_key=False, tooltip=tooltip,
                             vertical_scroll_only=False, select_mode=select_mode,
                             metadata={'disabled': not events, 'visible': True}))

        # Table option
        options = [[sg.Col([[sg.Text('Options', text_color=select_text_col, background_color=border_col)]],
                           pad=(0, (0, int(pad_v / 2))), background_color=border_col, vertical_alignment='c',
                           element_justification='c', expand_x=True)]]

        if modifiers['fill']:
            fill_menu = ['&Fill', display_header]
            options.append([sg.ButtonMenu('', fill_menu, key=fill_key, image_data=mod_const.FILL_ICON,
                                          image_size=(200, 40), pad=(pad_h, (0, int(pad_v / 2))), border_width=1,
                                          button_color=(text_col, row_col), tooltip='Fill NA values')])

        if modifiers['export']:
            options.append([sg.Button('', key=print_key, image_data=mod_const.EXPORT_ICON,
                                      image_size=(200, 40), pad=(pad_h, (0, int(pad_v / 2))), border_width=1,
                                      button_color=(text_col, row_col), tooltip='Export to spreadsheet')])

        if modifiers['sort']:
            sort_menu = ['&Sort', display_header]
            options.append(
                [sg.ButtonMenu('', sort_menu, key=sort_key, image_data=mod_const.SORT_ICON,
                               image_size=(200, 40), pad=(pad_h, (0, int(pad_v / 2))), border_width=1,
                               button_color=(text_col, row_col), tooltip='Sort table on columns')])

        row4.append(sg.Col(options, key=self.key_lookup('OptionsFrame'), background_color=frame_col,
                           justification='r', expand_y=True, visible=False, metadata={'visible': False}))

        # Annotation display panel
        if len(self.annotation_rules) > 0:
            annot_vis = True
            height_offset += annot_h  # height of the collapsible bar
        else:
            annot_vis = False
            height_offset += 2  # invisible elements have a footprint

        annot_key = self.key_lookup('Notes')
        row5 = [sg.Col([[sg.Canvas(size=(0, annot_h), background_color=header_col),
                         sg.Text('(select row)', key=annot_key, size=(10, 1), pad=(pad_el, 0), auto_size_text=False,
                                 font=annot_font, background_color=row_col, text_color=disabled_text_col,
                                 border_width=1, relief='sunken')]],
                       background_color=header_col, expand_x=True, vertical_alignment='c', element_justification='l',
                       visible=annot_vis, metadata={'visible': annot_vis, 'disabled': True})]

        # Control buttons and totals row
        actions_bar = [sg.Canvas(size=(0, bar_h), background_color=header_col)]
        action_layout = []
        for action in self.actions:
            action_bttn = action.layout(disabled=is_disabled, bg_col=header_col)
            action_layout.append(action_bttn)

        actions_bar.append(sg.Col([action_layout], justification='l', background_color=header_col, expand_x=True))

        if self.tally_rule is None:
            total_desc = 'Rows:'
        else:
            total_desc = 'Total:'

        init_totals = self.calculate_total()
        if isinstance(init_totals, float):
            init_totals = '{:,.2f}'.format(init_totals)
        else:
            init_totals = str(init_totals)
        actions_bar.append(sg.Col([[sg.Text(total_desc, pad=((0, pad_el), 0), font=bold_font,
                                            background_color=header_col),
                                    sg.Text(init_totals, key=total_key, size=(14, 1), pad=((pad_el, 0), 0),
                                            font=font, background_color=row_col, justification='r', relief='sunken',
                                            metadata={'name': self.name})]],
                                  pad=(pad_el, 0), justification='r', element_justification='r', vertical_alignment='b',
                                  background_color=header_col, expand_x=True, expand_y=False))

        row6 = [sg.Col([actions_bar], key=self.key_lookup('ActionsBar'), background_color=header_col,
                       vertical_alignment='c', expand_x=True, expand_y=True)]

        height_offset += bar_h  # height of the totals bar

        # Layout
        relief = 'ridge'
        layout = sg.Frame('', [row1, row2, row3, row4, row5, row6], key=self.key_lookup('Table'),
                          pad=pad, element_justification='c', vertical_alignment='c', background_color=header_col,
                          relief=relief, border_width=2)

        height_offset = height_offset + scroll_w + row_h  # add scrollbar and table header to the offset
        self._height_offset = height_offset

        min_h = nrow * row_h + height_offset

        self._dimensions = (min_w, min_h)
        self._min_size = (min_w, min_h)

        return layout

    def resize(self, window, size: tuple = None):
        """
        Resize the table element.
        """
        table_key = self.key_lookup('Table')
        current_w, current_h = self.dimensions()
        min_w, min_h = self._min_size
        border_w = 1 * 4
        pad_w, pad_h = self.pad_offset()

        if size:
            width, height = size
            new_h = current_h if height is None or height < min_h else height - pad_h
            new_w = current_w if width is None or width < min_w else width - pad_w
        else:
            new_w, new_h = (current_w, current_h)

        logger.debug(self.format_log('resizing display to {W}, {H}'.format(W=new_w, H=new_h)))
        mod_lo.set_size(window, table_key, (new_w, new_h))
        self._dimensions = (new_w, new_h)

        self.set_table_dimensions(window)

        # Expand the table frames
        filter_params = self.parameters
        frame_w = new_w - border_w
        if len(filter_params) > 0 and self.modifiers['filter'] is True:
            # Resize the filter parameters
            col1width_key = self.key_lookup('WidthCol1')
            col2width_key = self.key_lookup('WidthCol2')
            col3width_key = self.key_lookup('WidthCol3')

            if len(filter_params) <= 2 or len(filter_params) == 4:
                param_w = int(frame_w * 0.35)
                col_widths = [int(frame_w * 0.45), int(frame_w * 0.1), int(frame_w * 0.45)]
            else:
                param_w = int(frame_w * 0.30)
                col_widths = [int(frame_w * 0.33) for _ in range(3)]

            remainder = frame_w - sum(col_widths)
            index = 0
            for one in [1 for _ in range(int(remainder))]:
                if index > 2:  # restart at first column
                    index = 0
                col_widths[index] += one
                index += one

            col1_w, col2_w, col3_w = col_widths
            window[col1width_key].set_size(size=(col1_w, None))
            window[col2width_key].set_size(size=(col2_w, None))
            window[col3width_key].set_size(size=(col3_w, None))

            for param in self.parameters:
                param.resize(window, size=(param_w, None))

        window[self.key_lookup('Notes')].expand(expand_x=True)

        return window[table_key].get_size()

    def set_table_dimensions(self, window):
        """
        Reset column widths to calculated widths.
        """
        frame_key = self.key_lookup('OptionsFrame')
        width, nrows = self.get_table_dimensions(window)

        logger.debug(self.format_log('resetting display table dimensions'))

        # Close options panel, if open
        if window[frame_key].metadata['visible'] is True:
            window[frame_key].metadata['visible'] = False
            window[frame_key].update(visible=False)

        # Update column widths
        self._update_column_widths(window, width)

        # Re-annotate the table rows. Row colors often get reset when the number of display rows is changed.
        window[self.key_lookup('Element')].update(row_colors=self._colors)

    def get_table_dimensions(self, window):
        """
        Get the dimensions of the table component of the data table element based on current dimensions.
        """
        width, height = self._dimensions
        border_w = 1 * 4
        scroll_w = mod_const.SCROLL_WIDTH
        row_h = mod_const.TBL_ROW_HEIGHT

        height_offset = self._height_offset
        default_nrow = self.nrow

        # Calculate the width of all the visible table columns
        tbl_width = width - scroll_w - border_w  # approximate size of the table scrollbar

        # Calculate the number of table rows to display based on the desired height of the table.  The desired
        # height allocated to the data table minus the offset height composed of the heights of all the accessory
        # elements, such as the title bar, actions, bar, summary panel, etc., minus the height of the header.
        frame = window[self.key_lookup('FilterFrame')]
        if not frame.metadata['disabled']:
            if frame.metadata['visible']:
                frame_h = self._frame_height + 1
            else:
                frame_h = 1

            height_offset += frame_h

        tbl_height = height - height_offset  # minus offset
        projected_nrows = int(tbl_height / row_h)
        nrows = projected_nrows if projected_nrows > default_nrow else default_nrow

        return (tbl_width, nrows)

    def dimensions(self):
        """
        Return the current dimensions of the element.
        """
        return self._dimensions

    def collapse_expand(self, window):
        """
        Collapse record frames.
        """
        bttn_key = self.key_lookup('CollapseBttn')
        bttn = window[bttn_key]

        frame_key = self.key_lookup('FilterFrame')
        frame = window[frame_key]
        frame_meta = frame.metadata

        if frame_meta['visible']:  # already visible, so want to collapse the frame
            logger.debug(self.format_log('collapsing the filter frame'))
            bttn.update(image_data=mod_const.UNHIDE_ICON)
            frame.update(visible=False)

            frame.metadata['visible'] = False
        else:  # not visible yet, so want to expand the frame
            if not frame_meta['disabled']:
                logger.debug(self.format_log('expanding the filter frame'))
                bttn.update(image_data=mod_const.HIDE_ICON)
                frame.update(visible=True)

                frame.metadata['visible'] = True

        self.resize(window)

    def export_table(self, display: bool = True):
        """
        Export table to spreadsheet.
        """
        df = self.data(display_rows=display)
        logger.info(self.format_log('preparing the table for exporting'))

        # Annotate the table
        annotations = self.annotate_rows(df)
        annotation_map = {i: self.annotation_rules[j]['BackgroundColor'] for i, j in annotations.items()}

        # Format the display values
        display_df = self.format_display_values(df)

        # Style the table by adding the annotation coloring
        style = 'background-color: {}'
        style_df = display_df.style.apply(lambda x: [style.format(annotation_map.get(x.name, 'white')) for _ in x],
                                          axis=1)

        return style_df

    def calculate_total(self, df: pd.DataFrame = None):
        """
        Calculate the data table total using the configured tally rule.
        """
        is_float_dtype = pd.api.types.is_float_dtype
        is_integer_dtype = pd.api.types.is_integer_dtype
        is_bool_dtype = pd.api.types.is_bool_dtype
        is_string_dtype = pd.api.types.is_string_dtype
        is_datetime_dtype = pd.api.types.is_datetime64_any_dtype

        tally_rule = self.tally_rule
        df = df if df is not None else self.data(display_rows=True)
        if df.empty:
            return 0

        if tally_rule:
            header = df.columns.tolist()
            summary_df = pd.DataFrame(columns=header, index=[0])

            for column in header:
                col_values = df[column]
                dtype = col_values.dtype
                if is_float_dtype(dtype) or is_integer_dtype(dtype) or is_bool_dtype(dtype):
                    col_total = col_values.sum()
                elif is_string_dtype(dtype) or is_datetime_dtype(dtype):
                    col_total = col_values.nunique()
                else:  # possibly empty dataframe
                    col_total = 0

                summary_df[column] = col_total

            try:
                total = mod_dm.evaluate_operation(summary_df, tally_rule)
            except Exception as e:
                msg = 'unable to calculate table total'
                logger.warning(self.format_log(msg, err=e))
                total = 0
        else:
            total = df.shape[0]

        return total

    def export_values(self, edited_only: bool = False):
        """
        Export summary values as a dictionary.

        Arguments:
            edited_only (bool): only export table summary values if the table had been edited [Default: False].
        """
        if edited_only and not self.edited:  # table was not edited by the user
            return {}
        else:
            return self.summarize()

    def subset(self, subset_rule):
        """
        Subset the table based on a set of rules.
        """
        subset_df = self.collection.subset(subset_rule)

        return subset_df

    def subset_old(self, subset_rule):
        """
        Subset the table based on a set of rules.
        """
        df = self.data()
        if df.empty:
            return df

        logger.debug(self.format_log('sub-setting table on rule {RULE}'.format(RULE=subset_rule)))
        try:
            # results = mod_dm.evaluate_condition_set(df, {'custom': subset_rule})
            results = mod_dm.evaluate_condition(df, subset_rule)
        except Exception as e:
            msg = 'failed to subset table on rule {RULE}'.format(RULE=subset_rule)
            logger.error(self.format_log(msg, err=e))

            raise ValueError(msg)

        subset_df = df[results]

        return subset_df

    def check_requirements(self):
        """
        Verify that the record element passes requirements.
        """
        comp_df = self.collection.data()

        required_columns = self.required_columns
        for required_column in required_columns:
            has_na = comp_df[required_column].isnull().any()
            logger.debug(self.format_log('required column {COL} has NA values: {HAS}'
                                         .format(COL=required_column, HAS=has_na)))
            if has_na:
                display_map = self.display_columns
                try:
                    display_column = display_map[required_column]
                except KeyError:
                    display_column = required_column

                msg = 'missing values for required column {COL}'.format(COL=display_column)
                logger.warning(self.format_log(msg))

                return False

        return True

    def has_value(self):
        """
        Return True if no NAs in the table else return False.
        """
        return self.check_requirements()

    def edit_row(self, index):
        """
        Edit existing record values.
        """
        can_edit = self.modifiers['edit']
        if can_edit:
            edit_columns = self.edit_columns
        else:
            edit_columns = None

        df = self.collection.data(current=False)

        try:
            row = df.loc[index]
        except IndexError:
            msg = 'no record found at table index "{IND}" to edit'.format(IND=index + 1)
            mod_win2.popup_error(msg)
            logger.error(self.format_log('failed to edit record at row {IND} - {MSG}'.format(MSG=msg, IND=index + 1)))

            return df

        # Display the modify row window
        display_map = self.display_columns
        mod_row = mod_win2.edit_row_window(row, edit_columns=edit_columns, header_map=display_map)

        return mod_row

    def import_rows(self, import_df: pd.DataFrame = None):
        """
        Import one or more records through the record import window.
        """
        # pd.set_option('display.max_columns', None)
        collection = self.collection

        table_layout = {'Columns': collection.dtypes, 'DisplayColumns': self.display_columns, 'Aliases': self.aliases,
                        'RowColor': self.row_color, 'Widths': self.widths, 'Description': self.description,
                        'SortBy': self.sort_on, 'FilterParameters': self.filter_entry, 'SearchField': self.search_field,
                        'Modifiers': {'search': 1, 'filter': 1, 'export': 1, 'sort': 1},
                        'HiddenColumns': self.hidden_columns,
                        'DependantColumns': collection.dependant_columns, 'Defaults': collection.default
                        }
        import_table = DataTable(self.name, table_layout)

        if import_df is None:
            import_df = collection.data(current=False, deleted_only=True)

        import_table.append(import_df, reindex=False)

        # Get table of user selected import records
        select_df = mod_win2.import_window(import_table)

        if not select_df.empty:
            # Change deleted column of existing selected records to False
            logger.debug(self.format_log('changing deleted status of selected records stored in the table to False'))
            collection.set_state('deleted', False, indices=select_df.index.tolist())

        return pd.DataFrame()

    def append(self, add_df, inplace: bool = True, new: bool = False, reindex: bool = True):
        """
        Add data to the table collection.

        Arguments:
            add_df: new data to append to the table.

            inplace (bool): append to the dataframe in-place [Default: True].

            new (bool): append the data as added rows [Default: False - initial added "state" will be set as False].

            reindex (bool): reset the index after appending the new rows to the table [Default: True].
        """
        df = self.collection.append(add_df, inplace=inplace, new=new, reindex=reindex)

        return df

    def delete_rows(self, indices, inplace: bool = True):
        """
        Remove rows from the table collection.

        Arguments:
            indices (list): real indices of the desired data to remove from the collection.

            inplace (bool): delete data in place [Default: True].
        """
        df = self.collection.delete(indices, inplace=inplace)

        return df

    def set_state(self, field, flag, indices: list = None, inplace: bool = True):
        """
        Set the value for the state field at the given indices.
        """
        df = self.collection.set_state(field, flag, indices=indices, inplace=inplace)

        return df

    def update_row(self, index, values):
        """
        Update the values of a given row in-place.

        Arguments:
            index (int): adjusted row index.

            values (Series): values to replace.
        """
        edited = self.collection.update_entry(index, values)

        return edited

    def update_column(self, column, values, indices: list = None):
        """
        Update the values of a given column in-place.

        Arguments:
            column (str): name of the column to modify.

            values: list, series, or scalar of new column values.

            indices (list): optional list of real row indices to modify [Default: update all rows].
        """
        edited = self.collection.update_field(column, values, indices=indices)

        return edited


class RecordTable(DataTable):
    """
    Record tables are a subclass of the data table, but specifically for storing record data. Record tables provide
    additional functionality to the data table, including opening of a record instead of row value editing,
    deleting records, and importing existing records into the table.

    Attributes:

        name (str): table element configuration name.

        elements (list): list of table element keys.

        collection (Class): data collection class storing the table values.
    """

    def __init__(self, name, entry, parent=None):
        """
        Initialize record table attributes.

        Arguments:
            name (str): name of the configured table element.

            entry (dict): configuration entry for the table element.

            parent (str): name of the parent element.
        """
        super().__init__(name, entry, parent)
        self.etype = 'record_table'

        try:
            self.collection = mod_col.RecordCollection(name, entry)
        except Exception as e:
            msg = self.format_log('failed to initialize the collection', err=e)
            raise AttributeError(msg)

        self.id_column = self.collection.id_column

        # Control flags that modify the table's behaviour
        try:
            modifiers = entry['Modifiers']
        except KeyError:
            self.modifiers = {'open': False, 'edit': False, 'search': False, 'summary': False, 'filter': False,
                              'export': False, 'fill': False, 'sort': False}
        else:
            self.modifiers = {'open': modifiers.get('open', 0), 'edit': modifiers.get('edit', 0),
                              'search': modifiers.get('search', 0), 'summary': modifiers.get('summary', 0),
                              'filter': modifiers.get('filter', 0), 'export': modifiers.get('export', 0),
                              'fill': modifiers.get('fill', 0), 'sort': modifiers.get('sort', 0)}
            for modifier in self.modifiers:
                try:
                    flag = bool(int(self.modifiers[modifier]))
                except ValueError:
                    logger.warning(self.format_log('modifier {MOD} must be either 0 (False) or 1 (True)'
                                                   .format(MOD=modifier)))
                    flag = False

                self.modifiers[modifier] = flag

        try:
            self.record_type = entry['RecordType']
        except KeyError:
            self.record_type = None

        try:
            self.import_filters = entry['ImportFilters']
        except KeyError:
            self.import_filters = None

        try:
            import_rules = entry['ImportRules']
        except KeyError:
            import_rules = {}

        self.import_rules = {}
        for import_table in import_rules:
            import_rule = import_rules[import_table]

            if 'Columns' not in import_rule:
                msg = 'missing required "ImportRules" {TBL} parameter "Columns"'.format(TBL=import_table)
                logger.error(self.format_log(msg))

                raise AttributeError(msg)
            if 'Filters' not in import_rule:
                import_rule['Filters'] = None

            self.import_rules[import_table] = import_rule

    def _translate_row(self, row, level: int = 1, new_record: bool = False, references: dict = None):
        """
        Translate row data into a record object.
        """
        record_entry = settings.records.fetch_rule(self.record_type)
        record_class = mod_records.DatabaseRecord

        record = record_class(self.record_type, record_entry.record_layout, level=level)
        record.initialize(row, new=new_record, references=references)

        return record

    def run_table_event(self, index):
        """
        Run a table action event.
        """
        collection = self.collection
        update_event = False

        logger.debug(self.format_log('opening record at real index {IND} for editing'.format(IND=index)))

        record = self.load_record(index)

        # Update record table values
        if record and self.modifiers['edit']:
            try:
                record_values = record.export_values()
            except Exception as e:
                msg = 'unable to update row {IND} values'.format(IND=index)
                logger.exception(self.format_log(msg, err=e))
            else:
                update_event = collection.update_entry(index, record_values)

        return update_event

    def row_ids(self, indices: list = None, deleted: bool = False):
        """
        Return a list of the current record IDs stored in the table collection.

        Arguments:
            indices (list): optional list of indices to subset collection on [Default: get all record IDs in the
                table].

            deleted (bool): include deleted rows [Default: False].
        """
        row_ids = self.collection.row_ids(indices=indices, deleted=deleted)

        return row_ids

    def record_index(self, record_ids):
        """
        Return a list of table indices corresponding to the supplied record IDs.

        Arguments:
            record_ids: list of record IDs contained in the table.
        """
        indices = self.collection.record_index(record_ids)

        return indices

    def add_record(self, record_data):
        """
        Create a new record and add it to the records table.

        Arguments:
            record_data (DataFrame): initial set of record data.

        Returns:
            record_created (bool): boolean indicating whether a new component record was created.
        """
        collection = self.collection

        if isinstance(record_data, pd.Series):  # need to convert series to dataframe first
            record_data = record_data.to_frame().T
        record_data = collection.enforce_conformity(record_data).squeeze()

        try:
            record = self._translate_row(record_data, level=1, new_record=True)
        except Exception as e:
            msg = 'failed to add new record to the table'
            logger.error(self.format_log(msg, err=e))
            mod_win2.popup_error('{MSG} - see log for details'.format(MSG=msg))

            raise

        # Display the record window
        record = mod_win2.record_window(record, modify_database=False)
        try:
            record_values = record.export_values()
        except AttributeError:  # record creation was cancelled
            return False
        else:
            logger.debug(self.format_log('appending values {VALS} to the table'.format(VALS=record_values)))
            collection.append(record_values, inplace=True, new=True)

            self.edited = True

        return True

    def load_record(self, index, level: int = None, references: dict = None, savable: bool = True):
        """
        Open selected record in new record window.

        Arguments:
            index (int): real index of the desired record to load.

            level (int): level at which the record should be loaded [Default: current level + 1]

            references (dict): load record using custom reference dictionary.

            savable (bool): database entry of the record can be updated through the record window [Default: True].
        """
        collection = self.collection
        df = collection.data(current=False)
        modifiers = self.modifiers

        level = level if level is not None else self.level + 1
        view_only = False if modifiers['edit'] is True else True

        try:
            row = df.loc[index]
        except IndexError:
            msg = 'no record found at table index "{IND}" to edit'.format(IND=index + 1)
            mod_win2.popup_error(msg)
            logger.exception(self.format_log('failed to open record at row {IND}'.format(IND=index + 1), err=msg))

            return None

        # Add any annotations to the exported row
        # annotations = self.annotate_rows(df)
        annotations = self.annotate_rows(df.loc[[index]])
        annot_code = annotations.get(index, None)
        if annot_code is not None:
            row['Warnings'] = self.annotation_rules[annot_code]['Description']

        try:
            record = self._translate_row(row, level=level, new_record=False, references=references)
        except Exception as e:
            msg = 'failed to open record at row {IND}'.format(IND=index + 1)
            logger.exception(self.format_log(msg, err=e))
            mod_win2.popup_error(msg)

            return None
        else:
            logger.info(self.format_log('opening record {ID} at row {IND}'.format(ID=record.record_id(), IND=index)))

        # Display the record window
        record = mod_win2.record_window(record, view_only=view_only, modify_database=savable)

        return record

    def import_rows(self, import_df: pd.DataFrame = None):
        """
        Import one or more records through the record import window.
        """
        # pd.set_option('display.max_columns', None)
        record_type = self.record_type

        collection = self.collection
        id_col = collection.id_column
        columns = collection.dtypes

        if import_df is None:
            import_df = collection.data(current=False, deleted_only=True)

        logger.debug(self.format_log('importing rows'))

        table_layout = {'Columns': columns, 'DisplayColumns': self.display_columns, 'Aliases': self.aliases,
                        'RowColor': self.row_color, 'Widths': self.widths, 'IDColumn': id_col,
                        'RecordType': record_type, 'Description': self.description,
                        'SortBy': self.sort_on, 'FilterParameters': self.filter_entry,
                        'Modifiers': {'search': 1, 'filter': 1, 'export': 1, 'sort': 1},
                        'HiddenColumns': self.hidden_columns, 'ImportRules': self.import_rules,
                        'DependantColumns': collection.dependant_columns, 'Defaults': collection.default
                        }

        import_table = RecordTable(self.name, table_layout)
        import_table.append(import_df)

        # Add relevant search parameters
        search_field = self.search_field
        if isinstance(search_field, tuple):
            search_col, search_val = search_field
            try:
                search_description = self.display_columns[search_col]
            except KeyError:
                search_description = search_col

            search_dtype = columns[search_col]
            search_entry = {'Description': search_description, 'ElementType': 'input', 'PatternMatching': True,
                            'DataType': search_dtype, 'DefaultValue': search_val}
            search_params = [mod_param.InputFieldText(search_col, search_entry)]
        else:
            search_params = None

        # Get table of user selected import records
        select_df = mod_win2.import_window(import_table, params=search_params)

        # Verify that selected records are not already in table
        select_ids = select_df[id_col]
        existing_indices = collection.record_index(select_ids)
        existing_ids = collection.row_ids(existing_indices, deleted=True)

        logger.debug(self.format_log('removing selected records {IDS} already stored in the table at rows {ROWS}'
                                     .format(IDS=existing_ids, ROWS=existing_indices)))
        select_df.drop(select_df.loc[select_df[id_col].isin(existing_ids)].index, inplace=True, axis=0, errors='ignore')

        # Change deleted column of existing selected records to False
        logger.debug(self.format_log('changing deleted status of selected records stored in the table to False'))
        collection.set_state('deleted', False, indices=existing_indices)

        return select_df


class ComponentTable(RecordTable):
    """
    Subclass of the records table, but for record components. Allows additional actions such as creating
    associated records.

    Attributes:
        name (str): table element configuration name.

        elements (list): list of table element keys.
    """

    def __init__(self, name, entry, parent=None):
        """
        Initialize component table attributes.

        Arguments:
            name (str): name of the configured table element.

            entry (dict): configuration entry for the table element.

            parent (str): name of the parent element.
        """
        super().__init__(name, entry, parent)
        self.etype = 'component'

        # Control flags that modify the table's behaviour
        try:
            modifiers = entry['Modifiers']
        except KeyError:
            self.modifiers = {'open': False, 'edit': False, 'search': False, 'summary': False, 'filter': False,
                              'export': False, 'fill': False, 'sort': False, 'unassociated': False}
        else:
            self.modifiers = {'open': modifiers.get('open', 0), 'edit': modifiers.get('edit', 0),
                              'search': modifiers.get('search', 0), 'summary': modifiers.get('summary', 0),
                              'filter': modifiers.get('filter', 0), 'export': modifiers.get('export', 0),
                              'fill': modifiers.get('fill', 0), 'sort': modifiers.get('sort', 0),
                              'unassociated': modifiers.get('unassociated', 0)}
            for modifier in self.modifiers:
                try:
                    flag = bool(int(self.modifiers[modifier]))
                except ValueError:
                    logger.warning(self.format_log('modifier {MOD} must be either 0 (False) or 1 (True)'
                                                   .format(MOD=modifier)))
                    flag = False

                self.modifiers[modifier] = flag

        try:
            self.association_rule = entry['AssociationRule']
        except KeyError:
            msg = 'missing required parameter "AssociationRule"'
            logger.error(self.format_log(msg))

            raise AttributeError(msg)

    def import_rows(self, import_df: pd.DataFrame = None):
        """
        Import one or more records through the record import window.
        """
        # pd.set_option('display.max_columns', None)
        modifiers = self.modifiers
        record_type = self.record_type

        collection = self.collection
        id_col = collection.id_column
        columns = collection.dtypes

        if import_df is None:
            import_df = collection.data(current=False, deleted_only=True)
        current_ids = collection.row_ids()

        logger.debug(self.format_log('importing rows'))

        table_layout = {'Columns': columns, 'DisplayColumns': self.display_columns, 'Aliases': self.aliases,
                        'RowColor': self.row_color, 'Widths': self.widths, 'IDColumn': id_col,
                        'RecordType': record_type, 'Description': self.description,
                        'SortBy': self.sort_on, 'FilterParameters': self.filter_entry,
                        'Modifiers': {'search': 1, 'filter': 1, 'export': 1, 'sort': 1},
                        'HiddenColumns': self.hidden_columns, 'ImportRules': self.import_rules,
                        'DependantColumns': collection.dependant_columns, 'Defaults': collection.default
                        }

        import_table = RecordTable(self.name, table_layout)
        import_table.append(import_df)

        # Search for records without an existing reference to the provided reference type
        if modifiers['unassociated']:
            record_entry = settings.records.fetch_rule(record_type)
            rule_name = self.association_rule

            logger.debug(self.format_log('importing unreferenced records on rule "{RULE}"'.format(RULE=rule_name)))

            # Import the entries from the reference table with record references unset
            try:
                df = record_entry.load_unreferenced_records(rule_name)
            except Exception as e:
                msg = 'failed to import unreferenced records from association rule {RULE}'.format(RULE=rule_name)
                logger.exception(self.format_log(msg, err=e))
            else:
                if not df.empty:
                    # Subset on table columns
                    df = df[[i for i in df.columns.values if i in import_df.columns]]

                    # Drop records that are already in the import dataframe
                    import_ids = import_df[id_col].tolist()
                    df.drop(df[df[id_col].isin(import_ids)].index, inplace=True)

                    # Drop records that are already in the component dataframe
                    df.drop(df[df[id_col].isin(current_ids)].index, inplace=True)

                    # Add import dataframe to data table object
                    import_table.append(df)

        # Add relevant search parameters
        search_field = self.search_field
        if isinstance(search_field, tuple):
            search_col, search_val = search_field
            try:
                search_description = self.display_columns[search_col]
            except KeyError:
                search_description = search_col

            search_dtype = columns[search_col]
            search_entry = {'Description': search_description, 'ElementType': 'input', 'PatternMatching': True,
                            'DataType': search_dtype, 'DefaultValue': search_val}
            search_params = [mod_param.InputFieldText(search_col, search_entry)]
        else:
            search_params = None

        # Get table of user selected import records
        select_df = mod_win2.import_window(import_table, params=search_params)

        # Verify that selected records are not already in table
        select_ids = select_df[id_col]
        existing_indices = collection.record_index(select_ids)
        existing_ids = collection.row_ids(existing_indices, deleted=True)

        logger.debug(self.format_log('removing selected records {IDS} already stored in the table at rows {ROWS}'
                                     .format(IDS=existing_ids, ROWS=existing_indices)))
        select_df.drop(select_df.loc[select_df[id_col].isin(existing_ids)].index, inplace=True, axis=0, errors='ignore')

        # Change deleted column of existing selected records to False
        logger.debug(self.format_log('changing delete status of selected records already stored in the table to False'))
        collection.set_state('deleted', False, indices=existing_indices)

        return select_df

    def export_references(self, record_id, edited_only: bool = False):
        """
        Export component table records as reference entries.

        Arguments:
            record_id (str): ID(s) of the record(s) referencing the table records.

            edited_only (bool): export references only for components that were added or edited.
        """
        collection = self.collection
        ref_df = collection.as_reference(edited_only=edited_only)
        if ref_df.empty:
            return ref_df

        ref_df.loc[:, 'RecordID'] = record_id
        ref_df.loc[:, 'RecordType'] = self.parent
        ref_df.loc[:, 'ReferenceDate'] = datetime.datetime.now()
        ref_df.loc[:, 'ReferenceType'] = self.record_type

        # Add reference notes based on row annotations
        export_df = collection.data(indices=ref_df.index)
        annotations = self.annotate_rows(export_df)
        annotation_map = {i: self.annotation_rules[j]['Description'] for i, j in annotations.items()}

        ref_df.loc[:, 'ReferenceNotes'] = ref_df.index.map(annotation_map)

        return ref_df


class DataList(RecordElement):
    """
    Record element that displays a data set in the form of a category list.

    Attributes:

        name (str): record element configuration name.

        elements (list): list of element GUI keys.

        modifiers (dict): flags that alter the element's behavior.
    """

    def __init__(self, name, entry, parent=None):
        """
        Initialize the record element attributes.

        Arguments:
            name (str): record element configuration name.

            entry (dict): configuration entry for the record element.

            parent (str): name of the parent record.
        """
        super().__init__(name, entry, parent)
        self._supported_stats = ['sum', 'count', 'product', 'mean', 'median', 'mode', 'min', 'max', 'std', 'unique']
        self.etype = 'list'

        record_elements = ('Frame', 'Description', 'Options')
        self.elements.update({i: '-{NAME}_{ID}_{ELEM}-'.format(NAME=name, ID=self.id, ELEM=i) for i in record_elements})

        # Element-specific bindings
        elem_key = self.key_lookup('Element')
        frame_key = self.key_lookup('Frame')
        focus_key = '{}+FOCUS+'.format(frame_key)
        element_events = ('Element', 'Options')

        self.bindings = {self.elements[i]: i for i in element_events}
        self.bindings[focus_key] = 'Frame'

        try:
            self.collection = mod_col.DataCollection(name, entry)
        except Exception as e:
            msg = self.format_log('failed to initialize the collection - {ERR}'.format(ERR=e))
            raise AttributeError(msg)

        self.columns = columns = list(self.collection.dtypes)

        # Actions that allow modification of the list, such as importing deleted entries
        try:
            actions = entry['Actions']
        except KeyError:
            actions = {}

        self.actions = {}
        self._actions = {}
        for action_name in actions:
            action_entry = actions[action_name]

            if 'Description' not in action_entry:
                action_entry['Description'] = action_name

            if 'Shortcut' in action_entry:
                bind_key = '{ELEM}+{DESC}+'.format(ELEM=elem_key, DESC=action_name.upper())
                self.bindings[bind_key] = action_name

            self.actions[action_name] = action_entry
            self._actions[action_entry['Description']] = action_name

        try:
            header_field = entry['HeaderField']
        except KeyError:
            msg = self.format_log('missing required parameter "HeaderField"')
            raise AttributeError(msg)
        else:
            if header_field in columns:
                self._header_field = header_field
            else:
                msg = self.format_log('header field "{FIELD}" not found in the set of collection fields'
                                      .format(FIELD=header_field))
                raise AttributeError(msg)

        try:
            notes_field = entry['NotesField']
        except KeyError:
            self._notes_field = None
        else:
            if notes_field in columns:
                self._notes_field = notes_field
            else:
                msg = self.format_log('notes field "{FIELD}" not found in the set of collection fields'
                                      .format(FIELD=notes_field))
                logger.warning(msg)

                self._notes_field = None

        try:
            warning_field = entry['WarningsField']
        except KeyError:
            self._warning_field = None
        else:
            if warning_field in columns:
                self._warning_field = warning_field
            else:
                msg = self.format_log('notes field "{FIELD}" not found in the set of collection fields'
                                      .format(FIELD=warning_field))
                logger.warning(msg)

                self._warning_field = None

        # Control flags that modify the behaviour of the info boxes and info box manager
        try:
            modifiers = entry['Modifiers']
        except KeyError:
            self.modifiers = {'open': None, 'delete': None, 'approve': None, 'require': False}
        else:
            self.modifiers = {'open': modifiers.get('open', None), 'delete': modifiers.get('delete', None),
                              'require': modifiers.get('require', False)}
            for modifier in self.modifiers:
                mod_value = self.modifiers[modifier]
                if pd.isna(mod_value):
                    continue

                try:
                    flag = bool(int(mod_value))
                except ValueError:
                    msg = self.format_log('element modifier {MOD} must be either 0 (False) or 1 (True)'
                                          .format(MOD=modifier))
                    logger.warning(msg)
                    flag = False

                self.modifiers[modifier] = flag

        # Attributes that affect how the data is displayed in the info boxes
        try:
            display_columns = entry['DisplayColumns']
        except KeyError:
            self.display_columns = {i: i for i in columns}
        else:
            self.display_columns = {}
            for display_column in display_columns:
                if display_column in columns:
                    self.display_columns[display_column] = display_columns[display_column]
                else:
                    msg = self.format_log('display field {COL} not found in the list of data fields'
                                          .format(COL=display_column))
                    logger.warning(msg)

        try:
            nrow = int(entry['Rows'])
        except KeyError:
            self.nrow = 1
        except ValueError:
            msg = self.format_log('input to the Rows parameter must be an integer value')
            logger.warning(msg)
            self.nrow = 1
        else:
            self.nrow = 1 if nrow < 1 else nrow

        try:  # boolean fields can be displayed as a symbol - shown if true, hidden if false
            display_flags = entry['Flags']
        except KeyError:
            display_flags = {}

        self.flags = {}
        for flag_column in display_flags:
            if flag_column in columns:
                _flag_entry = display_flags[flag_column]
                flag_entry = {}
                try:
                    flag_entry['Description'] = _flag_entry['Description']
                except KeyError:
                    flag_entry['Description'] = flag_column
                try:
                    flag_entry['Icon'] = settings.get_icon_path(_flag_entry['Icon'])
                except KeyError:
                    logger.warning(self.format_log('no icon specified for flag {FLAG}'.format(FLAG=flag_column)))
                    flag_entry['Icon'] = settings.get_icon_path()  # defaults to a blank icon

                self.flags[flag_column] = flag_entry
            else:
                msg = self.format_log('flag {COL} not found in the list of data fields'
                                      .format(COL=flag_column))
                logger.warning(msg)

        try:
            summary_rules = entry['SummaryRules']
        except KeyError:
            summary_rules = {}

        self.summary_rules = {}
        for summary_col in summary_rules:
            if summary_col not in columns:
                msg = self.format_log('summary field "{COL}" is not in the list of fields'
                                      .format(COL=summary_col))
                logger.warning(msg)
                continue

            summary_stat = summary_rules[summary_col]
            if summary_stat not in self._supported_stats:
                msg = 'unknown statistic {STAT} set for summary field "{COL}"' \
                    .format(STAT=summary_stat, COL=summary_col)
                logger.warning(self.format_log(msg))
                continue

            self.summary_rules[summary_col] = summary_stat

        # Dynamic values
        self.level = 0
        self.indices = []
        self.editable = False
        self._dimensions = (mod_const.LISTBOX_WIDTH, mod_const.LISTBOX_HEIGHT)

    def reset(self, window):
        """
        Reset the record element to default.
        """
        self.edited = False
        self.collection.reset()

        for index in self.indices:
            entry_key = self.key_lookup('Entry:{}'.format(index))
            window[entry_key].update(visible=False)
            window[entry_key].metadata['visible'] = False

        self.update_display(window)

    def bind_keys(self, window):
        """
        Add hotkey bindings to the record element.
        """
        level = self.level

        elem_key = self.key_lookup('Element')
        frame_key = self.key_lookup('Frame')

        if level < 2:
            window[frame_key].bind('<Enter>', '+FOCUS+')

            actions = self.actions
            for action in actions:
                action_entry = actions[action]

                shortcut = action_entry['Shortcut']
                if shortcut:
                    shortcut_name = '<{}>'.format(shortcut)
                    bind_key = '+{DESC}+'.format(DESC=action.upper())
                    window[elem_key].bind(shortcut_name, bind_key)

    def fetch_entry(self, event):
        """
        Get the index of a list entry from a GUI event.
        """
        entry_element = event[1:-1].split('_')[-1]

        try:
            entry_event, index = entry_element.split(':')
        except ValueError:
            msg = self.format_log('unknown entry event "{EVENT}"'.format(EVENT=event))
            raise KeyError(msg)
        else:
            try:
                index = int(index)
            except ValueError:
                msg = self.format_log('index {INDEX} from "{EVENT}" must be an integer value'
                                      .format(EVENT=event, INDEX=index))
                raise KeyError(msg)

        return entry_event, index

    def data(self, all_rows: bool = False, edited_rows: bool = False, deleted_rows: bool = False,
             added_rows: bool = False, indices=None):
        """
        Return the collection data.

        Arguments:
            all_rows (bool): return all table rows, including the deleted rows [Default: False].

            edited_rows (bool): return only rows that have been edited in the table [Default: False].

            deleted_rows (bool): return only rows that have been deleted from the table [Default: False].

            added_rows (bool): return only rows that have been added to the table [Default: False].

            indices: list or series of entry indices.

        Returns:
            df (DataFrame): table data matching the selection requirements.
        """
        collection = self.collection

        current = (not all_rows) if indices is None or deleted_rows is False else False
        df = collection.data(current=current, edited_only=edited_rows, deleted_only=deleted_rows,
                             added_only=added_rows, indices=indices)

        return df

    def run_event(self, window, event, values):
        """
        Run a record element event.
        """
        update_event = False
        triggers = {'ValueEvent': False, 'ResizeEvent': False, 'DisplayEvent': False}

        # List element events
        try:
            element_event = self.bindings[event]
        except KeyError:
            msg = 'GUI event {EVENT} is not a {NAME} event'.format(EVENT=event, NAME=self.name)
            logger.warning(self.format_log(msg))

            return triggers
        else:
            logger.debug(self.format_log('running list event {EVENT}'.format(EVENT=element_event)))

        # Set focus to the element and enable edit mode
        if element_event == 'Frame':
            elem_key = self.key_lookup('Element')
            window[elem_key].set_focus()

            return triggers

        if element_event == 'Options':
            options_key = self.key_lookup('Options')
            selection = values[options_key]
            element_event = self._actions[selection]

        # Add a new entry to the data list
        if element_event == 'Add':
            try:
                import_rows = self.add_entries()
            except Exception as e:
                msg = 'failed to add entries to the list'
                logger.exception(self.format_log(msg, err=e))
            else:
                if not import_rows.empty:
                    self.collection.append(import_rows, new=True)

                update_event = True

        # Import a previously deleted entry
        elif element_event == 'Import':
            try:
                import_rows = self.import_entries()
            except Exception as e:
                msg = 'failed to import entries into the list'
                logger.exception(self.format_log(msg, err=e))
            else:
                if not import_rows.empty:
                    self.collection.append(import_rows, new=True)

                update_event = True

        else:  # event is an entry event
            event_type, index = self.fetch_entry(event)

            if event_type == 'Delete':
                msg = 'Are you sure that you would like to disassociate reference from the record? Disassociating ' \
                      'records does not delete either record involved.'
                user_action = mod_win2.popup_confirm(msg)

                if user_action.upper() == 'OK':
                    update_event = True
                    self.edited = True
                    self.collection.set_state('deleted', True, indices=[index])

            # Edit the notes field of a list entry
            elif event_type == 'Edit':
                note_key = self.key_lookup('Notes:{}'.format(index))
                current_note = window[note_key].metadata['value']
                note = mod_win2.add_note_window(current_note)
                if not pd.isna(note):
                    self.edited = True
                    window[note_key].update(value=note)
                    window[note_key].metadata['value'] = note
                    self.collection.update_field(self._notes_field, note, indices=[index])  # also update "edited" state

            # Run a header event
            elif event_type == 'Header':
                self.run_header_event(index)

        if update_event:
            resize_event = self.update_display(window)
            triggers['ValueEvent'] = True
            triggers['ResizeEvent'] = resize_event

        return triggers

    def run_header_event(self, index):
        logger.debug(self.format_log('running header event at index {INDEX}'.format(INDEX=index)))

    def dimensions(self):
        """
        Return the current dimensions of the element.
        """
        return self._dimensions

    def resize(self, window, size: tuple = None):
        """
        Resize the record element.
        """
        current_w, current_h = self.dimensions()
        border_w = 1
        scroll_w = mod_const.SCROLL_WIDTH
        pad_el = mod_const.ELEM_PAD
        pad_w, pad_h = self.pad_offset()
        nrow = self.nrow
        indices = self.indices

        if size:
            width, height = size
            new_h = None if height is None else height - border_w * 2 - pad_h
            new_w = current_w if width is None else width - border_w * 2 - pad_w
        else:
            new_h = None  # base height on number of configured "rows"
            new_w = current_w

        listbox_h = mod_const.LISTBOX_HEIGHT
        box_h = listbox_h + pad_el * 2 + border_w * 2
        listbox_w = new_w - pad_el * 2 - border_w * 2 - scroll_w

        list_h = 0
        for i, index in enumerate(indices):
            try:
                entry_key = self.key_lookup('Entry:{}'.format(index))
            except KeyError as e:
                msg = self.format_log('failed to find the entry frame for index {IND} - {ERR}'.format(IND=index, ERR=e))
                logger.warning(msg)
                continue

            mod_lo.set_size(window, entry_key, (listbox_w, listbox_h))

            if window[entry_key].metadata['visible'] and (nrow - 1 >= i):
                list_h += box_h

            notes_key = self.key_lookup('Notes:{}'.format(index))
            window[notes_key].expand(expand_x=True)

        if (nrow < 2) and (len(indices) > 1):  # make it obvious that there are is than one entry in the list
            list_h += int(box_h / 5)

        desc_key = self.key_lookup('Description')
        new_h = window[desc_key].get_size()[1] + pad_el * 4 + border_w + list_h if not new_h else new_h

        # Resize the list-box element
        frame_key = self.key_lookup('Frame')
        new_size = (new_w, new_h)
        mod_lo.set_size(window, frame_key, new_size)

        self._dimensions = new_size

        # Resize the column of list entries
        elem_key = self.key_lookup('Element')
        list_w = new_w - pad_el * 2
        mod_lo.set_size(window, elem_key, (list_w, list_h))

        return window[frame_key].get_size()

    def resize_old(self, window, size: tuple = None):
        """
        Resize the record element.
        """
        current_w, current_h = self.dimensions()
        border_w = 1
        pad_el = mod_const.ELEM_PAD
        pad_w, pad_h = self.pad_offset()

        if size:
            width, height = size
            new_h = current_h if height is None else height - border_w * 2 - pad_h
            new_w = current_w if width is None else width - border_w * 2 - pad_w
        else:
            new_w, new_h = (current_w, current_h)

        listbox_h = mod_const.LISTBOX_HEIGHT
        listbox_w = new_w - pad_el * 2

        desc_key = self.key_lookup('Description')
        new_h = window[desc_key].get_size()[1] + pad_el * 5 + border_w
        for index in self.indices:
            try:
                entry_key = self.key_lookup('Entry:{}'.format(index))
            except KeyError as e:
                msg = self.format_log('failed to find the entry frame for index {IND} - {ERR}'.format(IND=index, ERR=e))
                logger.warning(msg)
                continue

            mod_lo.set_size(window, entry_key, (listbox_w, listbox_h))

            if window[entry_key].metadata['visible']:
                new_h += listbox_h + pad_el * 2 + border_w * 2
            else:
                new_h += 1

            notes_key = self.key_lookup('Notes:{}'.format(index))
            window[notes_key].expand(expand_x=True)

        frame_key = self.key_lookup('Frame')
        new_size = (new_w, new_h)
        mod_lo.set_size(window, frame_key, new_size)

        self._dimensions = new_size

        return window[frame_key].get_size()

    def layout(self, size: tuple = None, padding: tuple = None, tooltip: str = None, editable: bool = True,
               overwrite: bool = False, level: int = 0, bg_color: str = None):
        """
        GUI layout for the record element.
        """
        size = self._dimensions if not size else size
        self._dimensions = size

        self.level = level
        self.editable = True if editable or overwrite else False
        actions = self.actions

        tooltip = tooltip if tooltip else ''

        # layout options
        font = mod_const.BOLD_LARGE_FONT
        menu_font = mod_const.MAIN_FONT

        text_col = mod_const.DEFAULT_TEXT_COLOR
        header_col = mod_const.TBL_HEADER_COLOR if bg_color is None else bg_color
        bg_col = mod_const.DEFAULT_BG_COLOR

        pad_el = mod_const.ELEM_PAD
        pad = padding if padding and isinstance(padding, tuple) else self.padding
        self.padding = pad

        # Element description
        desc_key = self.key_lookup('Description')
        desc_layout = sg.Col([[sg.Text(self.description, auto_size_text=True, pad=(0, 0), text_color=text_col,
                                       font=font, background_color=header_col, tooltip=tooltip)]],
                             key=desc_key, pad=(pad_el, pad_el), background_color=header_col, expand_x=True,
                             vertical_alignment='c')

        options_list = []
        for action in actions:
            action_entry = actions[action]
            action_desc = action_entry['Description']
            options_list.append(action_desc)

        if len(options_list) > 0:
            options_visible = True
        else:
            options_visible = False

        menu = ['&Options', options_list]
        options_key = self.key_lookup('Options')
        options_layout = sg.Col([[sg.ButtonMenu('', menu, key=options_key, image_data=mod_const.OPTIONS_ICON,
                                                visible=options_visible, font=menu_font,
                                                button_color=(text_col, header_col), border_width=0)]],
                                pad=(pad_el, pad_el), background_color=header_col, vertical_alignment='c')

        elem_key = self.key_lookup('Element')
        frame_key = self.key_lookup('Frame')
        layout = sg.Frame('', [[desc_layout, options_layout],
                               [sg.Col([[sg.HorizontalSeparator()]], background_color=header_col, expand_x=True)],
                               [sg.Col([[]], key=elem_key, background_color=bg_col, expand_x=True, expand_y=True,
                                       scrollable=True, vertical_scroll_only=True, visible=True)]],
                          key=frame_key, pad=pad, size=size, background_color=header_col)

        return layout

    def create_entry(self, index, window):
        """
        Create a layout for an entry in the data list.
        """
        modifiers = self.modifiers
        level = self.level
        editable = self.editable
        display_cols = self.display_columns
        flag_cols = self.flags
        entries = window[self.key_lookup('Element')]

        row = self.collection.data(indices=index).squeeze()
        display_row = self.collection.format_display(indices=index).squeeze()

        entry_elements = {i: '-{NAME}_{ID}_{ELEM}:{INDEX}-'.format(NAME=self.name, ID=self.id, ELEM=i, INDEX=index) for
                          i in ('Entry', 'Annotation', 'Header', 'Delete', 'Edit', 'Notes', 'Warnings')}

        # Allowed actions and visibility of component elements
        is_disabled = False if (editable is True and level < 1) else True
        can_delete = True if (modifiers['delete'] is True and not is_disabled) else False
        can_open = True if (modifiers['open'] is True and editable and level < 2) else False

        # layout options
        pad_el = mod_const.ELEM_PAD
        pad_h = mod_const.HORZ_PAD
        pad_action = int(pad_h / 2)

        font = mod_const.LARGE_FONT

        text_color = mod_const.DEFAULT_TEXT_COLOR
        icon_color = mod_const.FRAME_COLOR
        disabled_text_color = mod_const.DISABLED_TEXT_COLOR
        bg_color = self.bg_col
        select_text_color = mod_const.SELECTED_TEXT_COLOR if can_open else mod_const.DISABLED_TEXT_COLOR

        width, height = self._dimensions
        frame_w = width - pad_el * 2
        frame_h = mod_const.LISTBOX_HEIGHT

        icon_w = int(frame_h * 0.8)
        annot_w = 5
        flag_size = mod_const.FLAG_ICON_SIZE

        # List entry layout
        if self._notes_field:
            notes = display_row[self._notes_field]
            can_edit = True if not is_disabled else False
        else:
            notes = None
            can_edit = False

        note_text = '' if pd.isna(notes) else notes

        if self._warning_field:
            warning = display_row[self._warning_field]
        else:
            warning = None

        # Annotation strip
        annot_key = entry_elements['Annotation']
        column1 = sg.Col([[sg.Canvas(key=annot_key, size=(annot_w, frame_h), background_color=icon_color)]],
                         background_color=icon_color)

        # Listbox icon
        icon_path = settings.get_icon_path(self.icon)
        if icon_path is None:
            icon_path = settings.get_icon_path('default')

        column2 = sg.Col([[sg.Image(filename=icon_path, size=(icon_w, frame_h), pad=(0, 0),
                                    background_color=icon_color)]],
                         background_color=icon_color, element_justification='c', vertical_alignment='c')

        # List entry data and element action buttons

        # Listbox header and options button
        header = display_row[self._header_field]
        header_key = entry_elements['Header']
        self.bindings[header_key] = 'Header:{INDEX}'.format(INDEX=index)
        header_layout = [sg.Text(header, key=header_key, enable_events=True, font=font, text_color=select_text_color,
                                 background_color=bg_color)]

        for flag_col in flag_cols:
            flag_entry = flag_cols[flag_col]
            flag_name = flag_entry['Description']
            flag_icon = flag_entry['Icon']

            flag_key = '-{NAME}_{ID}_{ELEM}:{INDEX}-'.format(NAME=self.name, ID=self.id, ELEM=flag_col, INDEX=index)
            entry_elements[flag_col] = flag_key

            try:
                flag_visible = bool(int(row[flag_col]))
            except KeyError:
                msg = self.format_log('missing value for flag {FIELD}'.format(FIELD=flag_col))
                logger.warning(msg)
                flag_visible = False
            except (ValueError, TypeError):
                msg = self.format_log('unknown value "{VAL}" set for flag {FIELD}'
                                      .format(VAL=row[flag_col], FIELD=flag_col))
                logger.warning(msg)
                flag_visible = False

            flag_layout = sg.Image(filename=flag_icon, key=flag_key, size=flag_size, pad=((pad_el, 0), 0),
                                   visible=flag_visible, background_color=bg_color, tooltip=flag_name)

            header_layout.append(flag_layout)

        warning_text = '' if pd.isna(warning) else warning
        warnings_key = entry_elements['Warnings']
        warnings_icon = mod_const.WARNING_FLAG_ICON
        warning_visible = True if warning_text else False
        header_layout.append(sg.Image(data=warnings_icon, key=warnings_key, size=flag_size, pad=((pad_el, 0), 0),
                                      visible=warning_visible, background_color=bg_color, tooltip=warning_text))

        row1 = [sg.Col([header_layout], background_color=bg_color, element_justification='l',
                       vertical_alignment='c', expand_x=True)]

        # Listbox details
        row2 = []
        for i, column in enumerate(display_cols):
            col_alias = display_cols[column]
            try:
                col_value = display_row[column]
            except KeyError:
                msg = self.format_log('missing value for display field {FIELD}'.format(FIELD=column))
                logger.warning(msg)
                continue

            col_key = '-{NAME}_{ID}_{ELEM}:{INDEX}-'.format(NAME=self.name, ID=self.id, ELEM=column, INDEX=index)
            entry_elements[column] = col_key

            if i != 0:
                row2.append(sg.VerticalSeparator(pad=(pad_h, 0)))
            row2.append(sg.Text(col_value, key=col_key, font=font, text_color=text_color, background_color=bg_color,
                                tooltip=col_alias))

        # Listbox notes
        notes_key = entry_elements['Notes']
        row3 = [sg.Text(note_text, key=notes_key, size=(20, 1), font=font, text_color=disabled_text_color,
                        background_color=bg_color, tooltip=note_text, metadata={'value': note_text})]

        column3 = sg.Col([row1, row2, row3], pad=(pad_h, pad_h), background_color=bg_color, expand_x=True)

        # Listbox actions
        delete_key = entry_elements['Delete']
        edit_key = entry_elements['Edit']
        self.bindings.update({edit_key: 'Edit:{INDEX}'.format(INDEX=index),
                              delete_key: 'Delete:{INDEX}'.format(INDEX=index)})

        action_layout = [sg.Button('', key=edit_key, image_data=mod_const.TAKE_NOTE_ICON, pad=(pad_action, 0),
                                   border_width=0, button_color=(text_color, bg_color), visible=can_edit),
                         sg.Button('', key=delete_key, image_data=mod_const.DISCARD_ICON, pad=(pad_action, 0),
                                   border_width=0, button_color=(text_color, bg_color), visible=can_delete)
                         ]
        column4 = sg.Col([action_layout], pad=(pad_action, 0), background_color=bg_color, element_justification='c',
                         vertical_alignment='c')

        # Create the entry frame
        entry_key = entry_elements['Entry']
        layout = [[sg.pin(sg.Frame('', [[column1, column2, column3, column4]], key=entry_key, size=(frame_w, frame_h),
                                   pad=(pad_el, pad_el), background_color=bg_color, relief='raised',
                                   metadata={'visible': True}))]]

        # Add the entry frame to the entries column
        window.extend_layout(entries, layout)

        # Add the index to list of entry indices
        self.indices.append(index)

        # for element in entry_elements:
        self.elements.update({'{NAME}:{INDEX}'.format(NAME=i, INDEX=index): j for i, j in entry_elements.items()})

    def update_entry(self, index, window):
        """
        Update an entry layout with new data.
        """
        flag_cols = self.flags
        display_cols = self.display_columns

        row = self.collection.data(indices=index).squeeze()
        display_row = self.collection.format_display(indices=index).squeeze()

        # Update visibility of flag icons
        for flag_col in flag_cols:
            flag_key = self.key_lookup('{NAME}:{INDEX}'.format(NAME=flag_col, INDEX=index))
            flag_visible = row[flag_col]
            window[flag_key].update(visible=flag_visible)

        # Update values of the display data
        header = display_row[self._header_field]
        header_key = self.key_lookup('{NAME}:{INDEX}'.format(NAME='Header', INDEX=index))
        window[header_key].update(value=header)

        for column in display_cols:
            col_value = display_row[column]
            col_key = self.key_lookup('{NAME}:{INDEX}'.format(NAME=column, INDEX=index))
            window[col_key].update(value=col_value)

        # Update note text
        notes_key = self.key_lookup('Notes:{}'.format(index))
        if self._notes_field:
            notes = display_row[self._notes_field]
        else:
            notes = None

        note_text = '' if pd.isna(notes) else notes
        window[notes_key].update(value=note_text)
        window[notes_key].metadata['value'] = note_text
        window[notes_key].set_tooltip(note_text)

        # Update warning tooltip
        warnings_key = self.key_lookup('Warnings:{}'.format(index))
        if self._warning_field:
            warning = display_row[self._warning_field]
        else:
            warning = None

        warning_text = '' if pd.isna(warning) else warning
        warning_visible = True if warning_text else False
        window[warnings_key].set_tooltip(warning_text)
        window[warnings_key].update(visible=warning_visible)

    def update_display(self, window):
        """
        Update the record element display.
        """
        collection = self.collection
        annotation_rules = self.annotation_rules
        entry_indices = self.indices

        df = collection.data(current=False)
        annotations = self.annotate_display(df)

        # Create or update index entries
        resize_event = False
        for index in df.index.tolist():
            if index in entry_indices:
                entry_key = self.key_lookup('Entry:{}'.format(index))
                entry_deleted = collection.get_state('deleted', indices=[index])

                if entry_deleted:  # entry layout should be hidden when entry is set to "deleted"

                    if window[entry_key].metadata['visible']:  # entry layout is not yet hidden from the display
                        window[entry_key].update(visible=False)
                        window[entry_key].metadata['visible'] = False
                        resize_event = True
                else:  # these entries should all have visible layouts
                    if not window[entry_key].metadata['visible']:  # entry layout should be updated and made visible
                        resize_event = True
                        self.update_entry(index, window)

                        window[entry_key].update(visible=True)
                        window[entry_key].metadata['visible'] = True
            else:  # a layout for the entry has not yet been created
                resize_event = True
                self.create_entry(index, window)

            # Annotate the entry
            annotation_key = self.key_lookup('Annotation:{}'.format(index))
            try:
                annotation_code = annotations[index]
            except KeyError:
                bg_color = mod_const.FRAME_COLOR
                tooltip = ''
            else:
                annotation_entry = annotation_rules[annotation_code]
                bg_color = annotation_entry['BackgroundColor']
                tooltip = annotation_entry['Description']

            window[annotation_key].set_tooltip(tooltip)
            window[annotation_key].Widget.config(background=bg_color)

        if resize_event:
            self.resize(window)

        return resize_event

    def annotate_display(self, df):
        """
        Annotate the provided dataframe using configured annotation rules.
        """
        rules = self.annotation_rules
        if df.empty or rules is None:
            return {}

        annotations = {}
        rows_annotated = []
        for annot_code in rules:
            logger.debug(self.format_log('annotating the list entries based on configured annotation rule "{CODE}"'
                                         .format(CODE=annot_code)))
            rule = rules[annot_code]
            annot_condition = rule['Condition']
            try:
                results = mod_dm.evaluate_condition(df, annot_condition)
            except Exception as e:
                logger.exception(self.format_log('failed to annotate list entries using annotation rule {CODE} - {ERR}'
                                                 .format(CODE=annot_code, ERR=e)))
                continue

            for row_index, result in results.iteritems():
                if result:  # condition for the annotation has been met
                    if row_index in rows_annotated:
                        continue
                    else:
                        annotations[row_index] = annot_code
                        rows_annotated.append(row_index)

        return annotations

    def append(self, add_df, inplace: bool = True, new: bool = True, reindex: bool = True):
        """
        Add data to the collection.

        Arguments:
            add_df: new data to append to the list collection.

            inplace (bool): append to the dataframe in-place [Default: True].

            new (bool): append the data as added rows [Default: True - initial added "state" will be set to True].

            reindex (bool): reset the index after appending the new rows to the list [Default: True].
        """
        df = self.collection.append(add_df, inplace=inplace, new=new, reindex=reindex)

        return df

    def summarize(self, indices: list = None):
        """
        Generate the table summary on the summary rules.
        """
        collection = self.collection

        # Calculate totals defined by summary rules
        summary = {}
        rules = self.summary_rules
        for column in rules:
            summary_stat = rules[column]

            summary_total = collection.summarize_field(column, indices=indices, statistic=summary_stat)
            summary[column] = summary_total

        return summary

    def add_entries(self):
        """
        Add a new list entry.
        """
        df = self.data(all_rows=True)
        display_columns = {**{self._header_field: self.description}, **self.display_columns}
        dtypes = self.columns
        columns = df.columns.tolist()

        entry = pd.Series([None for _ in columns], index=columns)
        edited_entry = mod_win2.edit_row_window(entry, edit_columns=dtypes, header_map=display_columns)

        if edited_entry is not None:
            added_df = edited_entry.to_frame().T.fillna(df)
        else:
            added_df = pd.DataFrame()

        return added_df

    def import_entries(self, import_df: pd.DataFrame = None):
        """
        Import deleted list entries through the data import window.
        """
        # pd.set_option('display.max_columns', None)
        collection = self.collection
        display_columns = {**{self._header_field: self.description}, **self.display_columns}

        table_layout = {'Columns': collection.dtypes, 'DisplayColumns': display_columns,
                        'Aliases': collection.aliases, 'Description': self.description,
                        'Modifiers': {'search': 1, 'filter': 1, 'export': 1, 'sort': 1},
                        'DependantColumns': collection.dependant_columns, 'Defaults': collection.default
                        }
        import_table = DataTable(self.name, table_layout)

        if import_df is None:
            import_df = collection.data(current=False, deleted_only=True)

        import_table.append(import_df, reindex=False)

        # Get table of user selected import records
        select_df = mod_win2.import_window(import_table)

        # Change deleted column of existing selected records to False
        if not select_df.empty:
            selected_indices = select_df.index.tolist()
            logger.debug(self.format_log('changing deleted status of selected entries at indices {INDS} '
                                         'to False'.format(INDS=selected_indices)))
            self.collection.set_state('deleted', False, indices=selected_indices)
            self.collection.set_state('added', True, indices=selected_indices)

        return pd.DataFrame()

    def check_requirements(self):
        """
        Verify that the record element passes requirements.
        """
        passed = True if (self.modifiers['require'] and self.has_value()) or not self.modifiers['require'] else False

        return passed

    def has_value(self):
        """
        Confirm whether the list has one or more entries.
        """
        return self.collection.data().empty

    def export_values(self, edited_only: bool = False):
        """
        Export summary values as a dictionary.

        Arguments:
            edited_only (bool): only export table summary values if the table had been edited [Default: False].
        """
        if edited_only and not self.edited:  # table was not edited by the user
            return {}
        else:
            return self.summarize()


class ReferenceList(DataList):
    """
    Record element that displays record associations in the form of a category list.

    Attributes:

        name (str): record element configuration name.

        elements (list): list of element GUI keys.

        association_rule (str): name of the association rule connecting the associated records.
    """

    def __init__(self, name, entry, parent=None):
        """
        Initialize the reference box element attributes.

        Arguments:
            name (str): record element configuration name.

            entry (dict): configuration entry for the record element.

            parent (str): name of the parent record.
        """
        super().__init__(name, entry, parent)
        self.etype = 'reference'

        try:
            type_field = entry['TypeField']
        except KeyError:
            msg = self.format_log('missing required parameter "TypeField"')
            logger.warning(msg)
            self._type_field = None
        else:
            if type_field in self.columns:
                self._type_field = type_field
            else:
                msg = self.format_log('type field "{FIELD}" not found in the set of collection fields'
                                      .format(FIELD=type_field))
                raise AttributeError(msg)

        try:
            ref_type_field = entry['RefTypeField']
        except KeyError:
            msg = self.format_log('missing required parameter "RefTypeField"')
            logger.warning(msg)
            self._ref_type_field = None
        else:
            if ref_type_field in self.columns:
                self._ref_type_field = ref_type_field
            else:
                msg = self.format_log('reference type field "{FIELD}" not found in the set of collection fields'
                                      .format(FIELD=ref_type_field))
                raise AttributeError(msg)

        try:
            self.association_rule = entry['AssociationRule']
        except KeyError:
            msg = self.format_log('missing required parameter "AssociationRule"')
            logger.error(msg)

            raise AttributeError(msg)

        try:
            self.import_filters = entry['ImportFilters']
        except KeyError:
            self.import_filters = None

    def run_header_event(self, index):
        if self._ref_type_field:
            logger.debug(self.format_log('running header event at index {INDEX}'.format(INDEX=index)))
            try:
                record = self.load_record(index)
            except Exception as e:
                msg = 'failed to open record at index {INDEX} - {ERR}'.format(INDEX=index, ERR=e)
                logger.error(self.format_log(msg))
            else:
                # Display the record window
                mod_win2.record_window(record, view_only=True)

    def add_entries(self):
        """
        Add new entries through the data import window.
        """
        rule_name = self.association_rule
        collection = self.collection
        id_col = self._header_field
        df = collection.data(current=False)  # all entries in the collection
        ref_field = self._ref_type_field

        if not ref_field:
            return pd.DataFrame()

        logger.debug(self.format_log('importing unreferenced records on rule "{RULE}"'.format(RULE=rule_name)))
        display_columns = {self._header_field: self.description,
                           ref_field: self.display_columns[ref_field]}

        table_layout = {'Columns': {self._header_field: 'varchar', ref_field: 'varchar'},
                        'DisplayColumns': display_columns,
                        'Aliases': collection.aliases, 'Description': self.description,
                        'Modifiers': {'search': 1, 'filter': 1, 'export': 1, 'sort': 1}
                        }
        import_table = DataTable(self.name, table_layout)

        # Search for records without an existing reference to the provided reference type
        ref_types = df[ref_field].unique().tolist()
        for ref_type in ref_types:
            ref_entry = settings.records.fetch_rule(ref_type)

            # Import the entries from the reference table with record references unset
            try:
                import_df = ref_entry.load_unreferenced_records(rule_name)
            except Exception as e:
                msg = 'failed to import unreferenced records from association rule {RULE}'.format(RULE=rule_name)
                logger.exception(self.format_log('{MSG} - {ERR}'.format(MSG=msg, ERR=e)))
            else:
                if not import_df.empty:
                    # Subset on table columns
                    import_df = import_df[[i for i in import_df.columns.values if i in df.columns]]

                    # Drop records that are already in the component dataframe
                    current_ids = df[id_col].tolist()
                    import_df.drop(import_df[import_df['RecordID'].isin(current_ids)].index, inplace=True)

                    # Add import dataframe to data table object
                    import_df.rename(columns={'RecordID': self._header_field}, inplace=True)
                    import_df.loc[:, ref_field] = ref_type

                    import_table.append(import_df)

        # Get table of user selected import records
        select_df = mod_win2.import_window(import_table)

        added_df = pd.DataFrame(columns=df.columns.tolist())
        if not select_df.empty:
            added_df.append(select_df)
            added_df.fillna(df, inplace=True)

        return added_df

    def import_entries(self, import_df: pd.DataFrame = None):
        """
        Import deleted list entries through the data import window.
        """
        # pd.set_option('display.max_columns', None)
        collection = self.collection
        id_col = self._header_field
        ref_df = collection.data(current=False)  # all entries in the collection
        display_columns = {**{self._header_field: self.description}, **self.display_columns}

        table_layout = {'Columns': collection.dtypes, 'DisplayColumns': display_columns,
                        'Aliases': collection.aliases, 'Description': self.description,
                        'Modifiers': {'search': 1, 'filter': 1, 'export': 1, 'sort': 1},
                        'DependantColumns': collection.dependant_columns, 'Defaults': collection.default
                        }
        import_table = DataTable(self.name, table_layout)

        # Add entries that were deleted in the record window to the import set
        if import_df is None:
            import_df = collection.data(current=False, deleted_only=True)  # only deleted entries in the collection

        import_table.append(import_df, reindex=False)

        # Add entries that were set to deleted in the database to the import set
        if self._type_field and not ref_df.empty:
            record_type = ref_df[self._type_field].unique().squeeze()
            record_entry = settings.records.fetch_rule(record_type)
            db_df = record_entry.import_references(ref_df, rule=self.association_rule, include_deleted=True)

            # Subset on table columns
            db_df = db_df[[i for i in db_df.columns.values if i in import_df.columns]]

            # Drop entries that are already in the import dataframe
            import_ids = import_df[id_col].tolist()
            db_df.drop(db_df[db_df[id_col].isin(import_ids)].index, inplace=True)

            # Drop entries that are already in the component dataframe
            current_ids = ref_df[id_col].tolist()
            db_df.drop(db_df[db_df[id_col].isin(current_ids)].index, inplace=True)

            # Add import dataframe to data table object
            db_ids = db_df[id_col].tolist()
            import_table.append(db_df)
        else:
            db_ids = []

        # Get table of user selected import records
        select_df = mod_win2.import_window(import_table)

        # Verify that selected records are not already in table
        select_ids = select_df[id_col].tolist()
        existing_ids = [i for i in select_ids if i not in db_ids]
        existing_indices = ref_df.loc[ref_df[id_col].isin(existing_ids)].index.tolist()

        logger.debug(self.format_log('removing selected records {IDS} already stored in the table at rows {ROWS}'
                                     .format(IDS=existing_ids, ROWS=existing_indices)))
        select_df.drop(select_df.loc[select_df[id_col].isin(existing_ids)].index, inplace=True, axis=0, errors='ignore')

        # Change deleted column of existing selected records to False
        logger.debug(self.format_log('changing delete status of selected records already stored in the table to False'))
        collection.set_state('deleted', False, indices=existing_indices)

        return select_df

    def load_record(self, index, level: int = None):
        """
        Load the reference record from the database.

        Arguments:
            index (int): index of the record to load.

            level (int): load the referenced record at the given depth [Default: current level + 1].

        Returns:
            record (DatabaseRecord): initialized database record.
        """
        ref_data = self.collection.data(indices=[index]).squeeze()
        ref_type = ref_data[self._ref_type_field]
        record_entry = settings.records.fetch_rule(ref_type)
        record_class = mod_records.DatabaseRecord

        ref_id = ref_data[self._header_field]

        level = level if level is not None else self.level + 1
        logger.info(self.format_log('loading reference record {ID} of type {TYPE} at level {LEVEL}'
                                    .format(ID=ref_id, TYPE=ref_type, LEVEL=level)))

        imports = record_entry.load_records(ref_id, filters=self.import_filters)
        nrow = imports.shape[0]

        if nrow < 1:
            logger.warning(self.format_log('record reference {REF} not found in the database'.format(REF=ref_id)))
            record_data = imports
        elif nrow == 1:
            record_data = imports.iloc[0]
        else:
            logger.warning(self.format_log('more than one database entry found for record reference {REF}'
                                           .format(REF=ref_id)))
            record_data = imports.iloc[0]

        record = record_class(record_entry.name, record_entry.record_layout, level=level)
        record.initialize(record_data, new=False)

        return record


# Data variable classes
class DataUnit(RecordElement):
    """
    Record element that holds information on a single data variable.

    Attributes:

        name (str): record element configuration name.

        elements (list): list of element GUI keys.

        modifiers (dict): flags that alter the element's behavior.

        arrangement (str): layout arrangement of the element components. Possible values are horizontal
            (horz, h, long) or vertical (vert, v, stacked) [Default: vertical].

        justification (str): left-right justification of the element components. Possible values are left
            (left, l), center (center, c), or right (right, r) [Default: left].

        align (bool): align with other record elements by resizing the description as a given percentage of the total
            width of the element [Default: True].

        value: data vector containing the variable's value

        disabled (bool): editing of the record element is disabled [Default: False].
    """

    def __init__(self, name, entry, parent=None):
        """
        Initialize the data element attributes.

        Arguments:
            name (str): record element configuration name.

            entry (dict): configuration entry for the record element.

            parent (str): name of the parent record.
        """
        super().__init__(name, entry, parent)
        record_elements = ('Frame', 'Description', 'Width', 'ContentWidth')
        self.elements.update({i: '-{NAME}_{ID}_{ELEM}-'.format(NAME=name, ID=self.id, ELEM=i) for i in record_elements})

        # Parameters that modify the record element's behavior
        try:
            modifiers = entry['Modifiers']
        except KeyError:
            self.modifiers = {'edit': False, 'require': False, 'hide': False}
        else:
            self.modifiers = {'edit': modifiers.get('edit', 0), 'require': modifiers.get('require', 0),
                              'hide': modifiers.get('hide', 0)}
            for modifier in self.modifiers:
                try:
                    flag = bool(int(self.modifiers[modifier]))
                except ValueError:
                    logger.warning(self.format_log('modifier {MOD} must be either 0 (False) or 1 (True)'
                                                   .format(MOD=modifier)))
                    flag = False

                self.modifiers[modifier] = flag

        # Additional layout modification attributes
        try:
            arrange = entry['Arrangement']  # vertical arrangement of components
        except KeyError:  # default arrangement of element components is "stacked"
            arrange = 'v'

        if arrange in ('h', 'horizontal', 'horz', 'long'):
            self.arrangement = 'h'
        elif arrange in ('v', 'vertical', 'vert', 'stacked'):
            self.arrangement = 'v'
        else:
            logger.warning(self.format_log('unsupported value "{VAL}" provided to arrangement'.format(VAL=arrange)))
            self.arrangement = 'v'

        try:
            justification = entry['Justification']  # left-right justification of components
        except KeyError:
            justification = 'l'

        if justification in ('l', 'left'):
            self.justification = 'l'
        elif justification in ('r', 'right'):
            self.justification = 'r'
        elif justification in ('c', 'center'):
            self.justification = 'c'
        else:
            logger.warning(self.format_log('unsupported value "{VAL}" provided to justification'
                                           .format(VAL=justification)))
            self.justification = 'l'

        try:  # auto-align elements
            self.align = bool(int(entry['Align']))
        except KeyError:
            self.align = True
        except ValueError:
            logger.warning(self.format_log('the "align" parameter must be either 0 (False) or 1 (True)'))
            self.align = True

        # Dynamic variables
        self._offset = 0
        self.value = mod_col.DataVector(name, entry)
        self._dimensions = (mod_const.VARIABLE_WIDTH_PX, mod_const.VARIABLE_HEIGHT_PX)
        self.disabled = False

    def _resize_h(self, window, size: tuple = None):
        """
        Resize the record element display when element components are arranged horizontally.

        Arguments:
            window: GUI window.

            size (tuple): new width and height of the element [Default: set to size of the value + description].
        """
        bold_font = mod_const.BOLD_HEADING_FONT

        elem_key = self.key_lookup('Element')
        desc_key = self.key_lookup('Description')
        width_key = self.key_lookup('Width')
        content_width_key = self.key_lookup('ContentWidth')
        pad_w, pad_h = self.pad_offset()

        current_w, current_h = self.dimensions()

        if size:  # set element to a set size
            width, height = size
            new_h = current_h if height is None else height - pad_h
            new_w = current_w if width is None else width - pad_w
            if self.align:
                desc_w_px = int(new_w * 0.4)  # description is 40% of total width
                desc_w = int(desc_w_px / 9)  # convert to characters for resizing
                window[desc_key].set_size(size=(desc_w, None))
            else:
                desc_w_px = window[desc_key].string_width_in_pixels(bold_font, '{}:'.format(self.description))
            elem_w_px = new_w - self._offset - int(desc_w_px)
        else:  # auto size the element based on the content
            new_h = current_h

            font = mod_const.LARGE_FONT

            desc_w_px = window[desc_key].string_width_in_pixels(bold_font, '{}:'.format(self.description))
            display_value = self.format_display()
            print('display value for element {}:'.format(self.name))
            print(display_value)
            value_w = window[desc_key].string_width_in_pixels(font, display_value) + mod_const.SCROLL_WIDTH + pad_w
            elem_w_px = value_w if value_w >= mod_const.VARIABLE_WIDTH_PX else mod_const.VARIABLE_WIDTH_PX
            new_w = desc_w_px + elem_w_px + self._offset

        window[elem_key].set_size(size=(1, None))
        window[width_key].set_size(size=(new_w, None))

        window[content_width_key].set_size(size=(elem_w_px, None))
        window[elem_key].expand(expand_x=True)

        window.refresh()
        print('resizing record element {}'.format(self.name, new_w))
        print('desired width of record element {}: {}'.format(self.name, new_w))
        print('desired width of record element {} description: {}'.format(self.name, desc_w_px))
        print('size of record element {} description: {}'.format(self.name, window[desc_key].get_size()))
        print('desired width of record element {} value: {}'.format(self.name, elem_w_px))
        print('size of record element {} value: {}'.format(self.name, window[elem_key].get_size()))
        print('final size of record element {}: {}'.format(self.name, window[self.key_lookup('Frame')].get_size()))

        self._dimensions = (new_w, new_h)

        return window[self.key_lookup('Frame')].get_size()

    def _resize_v(self, window, size: tuple = None):
        """
        Resize the record element display when element components are arranged vertically.
        """
        elem_key = self.key_lookup('Element')
        width_key = self.key_lookup('Width')
        content_width_key = self.key_lookup('ContentWidth')
        pad_w, pad_h = self.pad_offset()

        current_w, current_h = self.dimensions()

        if size:  # set element to a specific size
            width, height = size
            new_h = current_h if height is None else height - pad_h
            new_w = current_w if width is None else width - pad_w
            window[elem_key].set_size(size=(1, None))
        else:  # don't modify the size
            new_w, new_h = (current_w, current_h)

        content_w = new_w - self._offset
        window[width_key].set_size(size=(new_w, None))
        window[content_width_key].set_size(size=(content_w, None))
        window[elem_key].expand(expand_x=True, expand_row=True)

        self._dimensions = (new_w, new_h)

        window.refresh()
        #print('resizing record element {}'.format(self.name, new_w))
        #print('desired width of record element {}: {}'.format(self.name, new_w))
        #print('size of record element {} value: {}'.format(self.name, window[elem_key].get_size()))
        #print('final size of record element {}: {}'.format(self.name, window[self.key_lookup('Frame')].get_size()))

        return window[self.key_lookup('Frame')].get_size()

    def annotate_display(self):
        """
        Annotate the element display using configured annotation rules.
        """
        rules = self.annotation_rules
        current_value = self.value.data()

        logger.debug(self.format_log('annotating value {VAL} on configured annotation rules'.format(VAL=current_value)))

        annotation = None
        for annot_code in rules:
            logger.debug(self.format_log('annotating element based on configured annotation rule "{CODE}"'
                                         .format(CODE=annot_code)))
            rule = rules[annot_code]
            annot_condition = rule['Condition']
            try:
                results = mod_dm.evaluate_condition({self.name: current_value}, annot_condition)
            except Exception as e:
                logger.error(self.format_log('failed to annotate element using annotation rule {CODE}'
                                             .format(CODE=annot_code), err=e))
                continue

            result = results.squeeze()
            if result:
                logger.debug(self.format_log('element value {VAL} annotated on annotation code {CODE}'
                                             .format(VAL=current_value, CODE=annot_code)))
                if annotation:
                    logger.warning(self.format_log('element value {VAL} has passed two or more annotation '
                                                   'rules ... defaulting to the first passed "{CODE}"'
                                                   .format(VAL=current_value, CODE=annotation)))
                else:
                    annotation = annot_code

        return annotation

    def check_requirements(self):
        """
        Verify that the record element passes requirements.
        """
        passed = True if (self.modifiers['require'] and self.has_value()) or not self.modifiers['require'] else False

        return passed

    def data(self):
        """
        Return the value of the record element.
        """
        return self.value.data()

    def dimensions(self):
        """
        Return the current dimensions of the element.
        """
        return self._dimensions

    def export_values(self, edited_only: bool = False):
        """
        Export the element's value as a dictionary.

        Arguments:
            edited_only (bool): only export element values if the data element had been edited [Default: False].
        """
        if edited_only and not self.edited:
            return {}
        else:
            return {self.name: self.value.data()}

    def format_display(self, editing: bool = False, value=None):
        """
        Format the element's value for displaying.
        """
        return self.value.format_display(editing=editing, value=value)

    def has_value(self):
        """
        Return True if element has a valid value else False
        """
        value = self.value.data()
        if not pd.isna(value) and not value == '':
            return True
        else:
            return False

    def resize(self, window, size: tuple = None):
        """
        Resize the element display.
        """
        if self.arrangement == 'v':
            new_size = self._resize_v(window, size)
        else:
            new_size = self._resize_h(window, size)

        return new_size

    def update_display(self, window):
        """
        Format element for display.
        """
        bg_col = self.bg_col if self.bg_col else mod_const.DEFAULT_BG_COLOR
        tooltip = self.description

        elem_key = self.key_lookup('Element')
        desc_key = self.key_lookup('Description')
        frame_key = self.key_lookup('Frame')

        # Update element display value
        display_value = self.format_display()
        window[elem_key].update(value=display_value)

        # Check if the display value passes any annotations rules and update background.
        annotation = self.annotate_display()
        if annotation:
            rule = self.annotation_rules[annotation]
            bg_col = rule['BackgroundColor']
            tooltip = rule['Description']

        window[desc_key].update(background_color=bg_col)
        window[frame_key].SetTooltip(tooltip)

    def update_value(self, input_value):
        """
        Update the element's value.
        """
        edited = self.value.update_value(input_value)

        return edited


class DataVariable(DataUnit):
    """
    Record element that holds information on a single data variable.

    Attributes:

        name (str): record element configuration name.

        elements (list): list of element GUI keys.

        edit_mode (bool): element is currently in edit mode [Default: False].
    """

    def __init__(self, name, entry, parent=None):
        """
        Initialize the data element attributes.

        Arguments:
            name (str): record element configuration name.

            entry (dict): configuration entry for the record element.

            parent (str): name of the parent record.
        """
        super().__init__(name, entry, parent)
        self.etype = 'text'

        #record_elements = ('Edit', 'Save', 'Cancel', 'Update', 'Auxiliary')
        #self.elements.update({i: '-{NAME}_{ID}_{ELEM}-'.format(NAME=name, ID=self.id, ELEM=i) for i in record_elements})
        #self.bindings = {self.elements[i]: i for i in ('Element', 'Edit', 'Save', 'Cancel')}
        record_elements = ('Auxiliary',)
        self.elements.update({i: '-{NAME}_{ID}_{ELEM}-'.format(NAME=name, ID=self.id, ELEM=i) for i in record_elements})
        self.bindings = {self.elements[i]: i for i in ('Element',)}

        # Element-specific bindings
        elem_key = self.key_lookup('Element')
        special_bindings = {'LCLICK': 'Edit', 'IN': 'Edit', 'RETURN': 'Save', 'Out': 'Save', 'ESCAPE': 'Cancel'}
        for special_event in special_bindings:
            event_key = '{ELEM}+{EVENT}+'.format(ELEM=elem_key, EVENT=special_event)
            self.bindings[event_key] = special_bindings[special_event]

        # Dynamic variables
        self.edit_mode = False
        self.disabled = True

    def _value_layout(self, size: tuple = None):
        """
        Configure the attributes for the record element's GUI layout.
        """
        font = mod_const.LARGE_FONT
        text_col = mod_const.DISABLED_TEXT_COLOR
        bg_col = self.bg_col
        value_col = mod_const.DEFAULT_BG_COLOR

        elem_key = self.key_lookup('Element')
        tooltip = display_value = self.format_display()

        aux_key = self.key_lookup('Auxiliary')
        aux_layout = [sg.pin(sg.Col([[]], key=aux_key, background_color=self.bg_col, visible=False))]

        layout_attrs = {'Key': elem_key, 'DisplayValue': display_value, 'Font': font, 'Size': size, 'BW': 1,
                        'BackgroundColor': value_col, 'TextColor': text_col, 'Disabled': True, 'Tooltip': tooltip}
        element_layout = mod_lo.generate_layout('text', layout_attrs)

        content_width_key = self.key_lookup('ContentWidth')
        layout = [sg.Col([[sg.Canvas(key=content_width_key, background_color=bg_col, size=(1, 0))],
                          element_layout + aux_layout], background_color=bg_col)]

        return layout

    def bind_keys(self, window):
        """
        Add hotkey bindings to the record element.
        """
        if not self.disabled:
            elem_key = self.key_lookup('Element')

            window[elem_key].bind('<Button-1>', '+LCLICK+')
            window[elem_key].bind('<FocusIn>', '+IN+')
            window[elem_key].bind('<Return>', '+RETURN+')
            window[elem_key].bind('<FocusOut>', '+OUT+')
            window[elem_key].bind('<Key-Escape>', '+ESCAPE+')

    def format_value(self, values):
        """
        Obtain the value of the record element from the set of GUI element values.

        Arguments:
            values (dict): single value or dictionary of element values.
        """
        if isinstance(values, dict):  # dictionary of referenced element values
            try:
                value = values[self.name]
            except KeyError:
                msg = self.format_log('input data is missing a value for the record element')
                logger.warning(msg)

                raise KeyError(msg)
        else:  # single value provided
            value = values

        edited = self.update_value(value)

        return edited

    def reset(self, window):
        """
        Reset record element to default.
        """
        elem_key = self.key_lookup('Element')
        aux_key = self.key_lookup('Auxiliary')

        # Reset element value to its default
        self.value.reset()

        # Reset element editing
        self.edited = False
        self.edit_mode = False
        window[aux_key].update(visible=False)
        window[elem_key].update(disabled=True)

        # Update the element display
        self.update_display(window)

    def reset_old(self, window):
        """
        Reset record element to default.
        """
        elem_key = self.key_lookup('Element')
        edit_key = self.key_lookup('Edit')
        update_key = self.key_lookup('Update')
        aux_key = self.key_lookup('Auxiliary')

        # Reset element value to its default
        self.value.reset()

        # Reset element editing
        self.edited = False
        self.edit_mode = False
        window[edit_key].update(disabled=False)
        window[update_key].update(visible=False)
        window[aux_key].update(visible=False)
        window[elem_key].update(disabled=True)

        # Update the element display
        self.update_display(window)

    def run_event(self, window, event, values):
        """
        Run a record element event.
        """
        text_col = mod_const.DEFAULT_TEXT_COLOR
        disabled_text_col = mod_const.DISABLED_TEXT_COLOR

        elem_key = self.key_lookup('Element')
        aux_key = self.key_lookup('Auxiliary')

        editing = self.edit_mode
        update_event = False
        triggers = {'ValueEvent': False, 'ResizeEvent': False, 'DisplayEvent': False}

        try:
            element_event = self.bindings[event]
        except KeyError:  # possible manual event passed
            element_event = event

        logger.debug(self.format_log('running event {EVENT}'.format(EVENT=element_event)))

        # Set focus to the element and enable edit mode
        if element_event == 'Edit' and not editing:
            window[elem_key].set_focus()

            if self.disabled:
                return triggers

            # Update element to show any current unformatted data
            value_fmt = self.format_display(editing=True)

            # Enable element editing and update colors
            window[elem_key].update(disabled=False, value=value_fmt)
            window[aux_key].update(visible=True)

            if self.etype in ('input', 'multiline', 'text', 'checkbox'):
                window[elem_key].update(text_color=text_col)

            self.edit_mode = True

        # Set element to inactive mode and update the element value
        elif element_event == 'Save' and editing:
            # Update value of the data element
            try:
                value = values[elem_key]
            except KeyError:
                logger.warning(self.format_log('unable to locate values for element key "{KEY}"'
                                               .format(NAME=self.name, KEY=elem_key)))
            else:
                try:
                    edited = self.update_value(value)
                except Exception as e:
                    msg = 'failed to save changes to {DESC}'.format(DESC=self.description)
                    logger.exception(self.format_log(msg, err=e))
                    mod_win2.popup_error(msg)

                else:
                    if edited:
                        self.edited = True
                        update_event = True

                self.update_display(window)

            # Disable element editing and update colors
            window[elem_key].update(disabled=True)
            window[aux_key].update(visible=False)
            if self.etype in ('input', 'multiline', 'text', 'checkbox'):
                window[elem_key].update(text_color=disabled_text_col)

            self.edit_mode = False

        elif element_event == 'Cancel' and editing:
            # Disable element editing and update colors
            window[elem_key].update(disabled=True)
            window[aux_key].update(visible=False)
            if self.etype in ('input', 'multiline', 'text', 'checkbox'):
                window[elem_key].update(text_color=disabled_text_col)

            self.edit_mode = False
            self.update_display(window)

        triggers['ValueEvent'] = update_event

        return triggers

    def run_event_old(self, window, event, values):
        """
        Run a record element event.
        """
        text_col = mod_const.DEFAULT_TEXT_COLOR
        disabled_text_col = mod_const.DISABLED_TEXT_COLOR

        elem_key = self.key_lookup('Element')
        edit_key = self.key_lookup('Edit')
        update_key = self.key_lookup('Update')
        aux_key = self.key_lookup('Auxiliary')

        editing = self.edit_mode
        update_event = False
        triggers = {'ValueEvent': False, 'ResizeEvent': False, 'DisplayEvent': False}

        try:
            element_event = self.bindings[event]
        except KeyError:
            msg = 'GUI event {EVENT} is not a {NAME} event'.format(EVENT=event, NAME=self.name)
            logger.warning(self.format_log(msg))

            return triggers
        else:
            logger.debug(self.format_log('running variable event {EVENT}'.format(EVENT=element_event)))

        # Set focus to the element and enable edit mode
        if element_event == 'Edit' and not editing:
            window[elem_key].set_focus()

            if self.disabled:
                return triggers

            # Update element to show any current unformatted data
            value_fmt = self.format_display(editing=True)

            # Enable element editing and update colors
            window[edit_key].update(disabled=True)
            window[elem_key].update(disabled=False, value=value_fmt)
            window[update_key].update(visible=True)
            window[aux_key].update(visible=True)

            if self.etype in ('input', 'multiline', 'text', 'checkbox'):
                window[elem_key].update(text_color=text_col)

            self.edit_mode = True

        # Set element to inactive mode and update the element value
        elif element_event == 'Save' and editing:
            # Update value of the data element
            try:
                value = values[elem_key]
            except KeyError:
                logger.warning(self.format_log('unable to locate values for element key "{KEY}"'
                                               .format(NAME=self.name, KEY=elem_key)))
            else:
                try:
                    edited = self.update_value(value)
                except Exception as e:
                    msg = 'failed to save changes to {DESC}'.format(DESC=self.description)
                    logger.exception(self.format_log(msg, err=e))
                    mod_win2.popup_error(msg)

                else:
                    if edited:
                        self.edited = True
                        update_event = True

                self.update_display(window)

            # Disable element editing and update colors
            window[edit_key].update(disabled=False)
            window[elem_key].update(disabled=True)
            window[update_key].update(visible=False)
            window[aux_key].update(visible=False)
            if self.etype in ('input', 'multiline', 'text', 'checkbox'):
                window[elem_key].update(text_color=disabled_text_col)

            self.edit_mode = False

        elif element_event == 'Cancel' and editing:
            # Disable element editing and update colors
            window[edit_key].update(disabled=False)
            window[elem_key].update(disabled=True)
            window[update_key].update(visible=False)
            window[aux_key].update(visible=False)
            if self.etype in ('input', 'multiline', 'text', 'checkbox'):
                window[elem_key].update(text_color=disabled_text_col)

            self.edit_mode = False
            self.update_display(window)

        triggers['ValueEvent'] = update_event

        return triggers

    def layout(self, padding: tuple = None, size: tuple = None, tooltip: str = None, editable: bool = True,
               overwrite: bool = False, level: int = 0, bg_color: str = None):
        """
        GUI layout for the record element.
        """
        modifiers = self.modifiers

        if not self.disabled:  # some variables are intrinsically un-editable (i.e. dependent variables, text, etc.)
            is_disabled = False if (overwrite or (editable and modifiers['edit'])) and level < 2 else True
            self.disabled = is_disabled

        is_required = modifiers['require']
        hidden = modifiers['hide']

        size = self._dimensions if not size else size
        width, height = size
        self._dimensions = (width * 10, mod_const.VARIABLE_HEIGHT_PX)

        background = self.bg_col if bg_color is None else bg_color
        tooltip = tooltip if tooltip else self.tooltip

        # Layout options
        pad_el = mod_const.ELEM_PAD
        pad = padding if padding and isinstance(padding, tuple) else self.padding
        self.padding = pad

        bold_font = mod_const.BOLD_HEADING_FONT

        bg_col = mod_const.DEFAULT_BG_COLOR if background is None else background
        self.bg_col = background
        text_col = mod_const.DEFAULT_TEXT_COLOR

        # Element Icon, if provided
        icon = self.icon
        icon_w = 24 + pad_el  # image size (24 pixels) plus padding
        if icon is not None:
            icon_path = settings.get_icon_path(icon)
            if icon_path is not None:
                icon_layout = [sg.Image(filename=icon_path, pad=((0, pad_el), 0), background_color=bg_col)]
            else:
                icon_layout = []
        else:
            icon_layout = []

        # Required symbol
        req_w = 11 + pad_el  # size of asterisk plus padding
        if is_required is True:
            required_layout = [sg.Text('*', pad=((0, pad_el), 0), font=bold_font, background_color=bg_col,
                                       text_color=mod_const.NOTE_COLOR, tooltip='required')]
        else:
            required_layout = []

        # Element description
        desc_key = self.key_lookup('Description')

        annotation = self.annotate_display()
        if annotation:
            rule = self.annotation_rules[annotation]
            desc_bg_col = rule['BackgroundColor']
            tooltip = rule['Description']
        else:
            desc_bg_col = bg_col

        desc = self.description if self.arrangement == 'v' else '{}:'.format(self.description)
        desc_layout = [sg.Text(desc, key=desc_key, pad=((0, pad_el), 0), background_color=desc_bg_col,
                               font=bold_font, auto_size_text=True, tooltip=tooltip)]

        # Element value layout
        element_layout = self._value_layout(size=(width, 1))

        # Element layout
        width_key = self.key_lookup('Width')
        row1 = [sg.Canvas(key=width_key, size=(1, 0), background_color=bg_col)]
        if self.arrangement == 'v':
            offset = 2  # width of the value frame
            row2 = icon_layout + desc_layout + required_layout
            row3 = element_layout
            components = [row1, row2, row3]
        else:
            offset = icon_w + req_w + 2  # icon, and asterisks width plus width of the value frame
            row2 = icon_layout + desc_layout + element_layout + required_layout
            components = [row1, row2]

        frame_key = self.key_lookup('Frame')
        layout = sg.Col(components, key=frame_key, pad=pad, background_color=bg_col, visible=(not hidden),
                        element_justification=self.justification)

        self._offset += offset

        return layout

    def layout_old(self, padding: tuple = None, size: tuple = None, tooltip: str = None, editable: bool = True,
               overwrite: bool = False, level: int = 0, bg_color: str = None):
        """
        GUI layout for the record element.
        """
        modifiers = self.modifiers

        if not self.disabled:  # some variables are intrinsically un-editable (i.e. dependent variables, text, etc.)
            is_disabled = False if (overwrite or (editable and modifiers['edit'])) and level < 2 else True
            self.disabled = is_disabled
        else:
            is_disabled = True

        is_required = modifiers['require']
        hidden = modifiers['hide']

        size = self._dimensions if not size else size
        width, height = size
        self._dimensions = (width * 10, mod_const.VARIABLE_HEIGHT_PX)

        background = self.bg_col if bg_color is None else bg_color
        tooltip = tooltip if tooltip else self.tooltip

        # Layout options
        pad_el = mod_const.ELEM_PAD
        pad = padding if padding and isinstance(padding, tuple) else self.padding
        self.padding = pad

        bold_font = mod_const.BOLD_HEADING_FONT

        bg_col = mod_const.DEFAULT_BG_COLOR if background is None else background
        self.bg_col = background
        text_col = mod_const.DEFAULT_TEXT_COLOR

        # Element Icon, if provided
        icon = self.icon
        icon_w = 24 + pad_el  # image size (24 pixels) plus padding
        if icon is not None:
            icon_path = settings.get_icon_path(icon)
            if icon_path is not None:
                icon_layout = [sg.Image(filename=icon_path, pad=((0, pad_el), 0), background_color=bg_col)]
            else:
                icon_layout = []
        else:
            icon_layout = []

        # Required symbol
        req_w = 11 + pad_el  # size of asterisk plus padding
        if is_required is True:
            required_layout = [sg.Text('*', pad=((0, pad_el), 0), font=bold_font, background_color=bg_col,
                                       text_color=mod_const.NOTE_COLOR, tooltip='required')]
        else:
            required_layout = []

        # Element description
        desc_key = self.key_lookup('Description')

        annotation = self.annotate_display()
        if annotation:
            rule = self.annotation_rules[annotation]
            desc_bg_col = rule['BackgroundColor']
            tooltip = rule['Description']
        else:
            desc_bg_col = bg_col

        desc = self.description if self.arrangement == 'v' else '{}:'.format(self.description)
        desc_layout = [sg.Text(desc, key=desc_key, pad=((0, pad_el), 0), background_color=desc_bg_col,
                               font=bold_font, auto_size_text=True, tooltip=tooltip)]

        # Element action buttons
        edit_key = self.key_lookup('Edit')
        update_key = self.key_lookup('Update')
        save_key = self.key_lookup('Save')
        cancel_key = self.key_lookup('Cancel')

        bttn_w = 16 * 3 + pad_el * 2
        bttn_vis = False if is_disabled else True
        bttn_layout = [sg.Button(image_data=mod_const.EDIT_ICON, key=edit_key, pad=(pad_el, 0),
                                 button_color=(text_col, bg_col), visible=bttn_vis, disabled=is_disabled,
                                 border_width=0, tooltip='Edit value'),
                       sg.pin(
                           sg.Col([[sg.Button(image_data=mod_const.SAVE_CHANGE_ICON, key=save_key,
                                              pad=(0, 0), button_color=(text_col, bg_col),
                                              border_width=0, tooltip='Save changes'),
                                    sg.Button(image_data=mod_const.CANCEL_CHANGE_ICON, key=cancel_key,
                                              pad=(0, 0), button_color=(text_col, bg_col),
                                              border_width=0, tooltip='Cancel changes')
                                    ]],
                                  key=update_key, pad=(0, 0), visible=False, background_color=bg_col))]

        # Element value layout
        element_layout = self._value_layout(size=(width, 1))

        # Element layout
        width_key = self.key_lookup('Width')
        row1 = [sg.Canvas(key=width_key, size=(1, 0), background_color=bg_col)]
        if self.arrangement == 'v':
            offset = bttn_w + 2  # button width plus width of the value frame
            row2 = icon_layout + desc_layout + required_layout
            row3 = element_layout + bttn_layout
            components = [row1, row2, row3]
        else:
            offset = icon_w + req_w + bttn_w + 2  # icon, button, and asterisks width plus width of the value frame
            row2 = icon_layout + desc_layout + element_layout + bttn_layout + required_layout
            components = [row1, row2]

        frame_key = self.key_lookup('Frame')
        layout = sg.Col(components, key=frame_key, pad=pad, background_color=bg_col, visible=(not hidden),
                        element_justification=self.justification)

        self._offset += offset

        return layout


class DataVariableInput(DataVariable):
    """
    Input-style data variable element.

    Attributes:

        name (str): record element configuration name.

        elements (list): list of element GUI keys.
    """

    def __init__(self, name, entry, parent=None):
        """
        Initialize the record element attributes.

        Arguments:
            name (str): record element configuration name.

            entry (dict): configuration entry for the record element.

            parent (str): name of the parent record.
        """
        super().__init__(name, entry, parent)
        self.etype = 'input'

        if entry['DataType'] in settings.supported_date_dtypes:
            calendar_key = '-{NAME}_{ID}_Calendar-'.format(NAME=self.name, ID=self.id)
            self.elements['Calendar'] = calendar_key
            self.bindings[calendar_key] = 'Calendar'

        self.disabled = False

    def _value_layout(self, size: tuple = None):
        """
        Configure the attributes for the record element's GUI layout.
        """
        font = mod_const.LARGE_FONT
        pad_el = mod_const.ELEM_PAD
        text_col = mod_const.DEFAULT_TEXT_COLOR
        bg_col = self.bg_col
        value_col = mod_const.DEFAULT_BG_COLOR

        elem_key = self.key_lookup('Element')
        tooltip = display_value = self.format_display()

        # Add auxiliary elements to the layout, such as a calendar button for datetime elements.
        try:
            date_key = self.key_lookup('Calendar')
        except KeyError:
            date_bttn = []
        else:
            date_bttn = [sg.CalendarButton('', key=date_key, target=elem_key, format='%Y-%m-%d', pad=(pad_el, 0),
                                           image_data=mod_const.CALENDAR_ICON, disabled=False,
                                           button_color=(text_col, value_col), border_width=0,
                                           tooltip='Select the date from the calendar menu')]

        aux_key = self.key_lookup('Auxiliary')
        aux_layout = [sg.pin(sg.Col([date_bttn], key=aux_key, background_color=value_col, visible=False))]

        layout_attrs = {'Key': elem_key, 'DisplayValue': display_value, 'Font': font, 'Size': size, 'BW': 0,
                        'BackgroundColor': value_col, 'TextColor': text_col, 'Disabled': True, 'Tooltip': tooltip}
        element_layout = mod_lo.generate_layout('input', layout_attrs)

        content_width_key = self.key_lookup('ContentWidth')
        layout = [sg.Frame('', [[sg.Canvas(key=content_width_key, background_color=bg_col, size=(1, 0))],
                                element_layout + aux_layout],
                           background_color=bg_col, relief='sunken', border_width=1)]

        return layout


class DataVariableCombo(DataVariable):
    """
    Dropdown-style data variable element.

    Attributes:

        name (str): record element configuration name.

        elements (list): list of element GUI keys.

        combo_values (list): list of possible element values.
    """

    def __init__(self, name, entry, parent=None):
        """
        Initialize data element attributes.

        Arguments:
            name (str): data element configuration name.

            entry (dict): configuration entry for the data element.

            parent (str): name of the parent element.
        """
        super().__init__(name, entry, parent)
        self.etype = 'dropdown'

        # Enforce supported data types for the dropdown parameter
        supported_dtypes = settings.supported_str_dtypes + settings.supported_int_dtypes + settings.supported_cat_dtypes
        if entry['DataType'] not in supported_dtypes:
            msg = self.format_log('unsupported data type provided for the "{ETYPE}" parameter. Supported data types '
                                  'are {DTYPES}'.format(ETYPE=self.etype, DTYPES=', '.join(supported_dtypes)))
            logger.error(msg)

            raise AttributeError(msg)

        # Dropdown values
        self.combo_values = []
        try:
            combo_values = entry['Values']
        except KeyError:
            msg = 'missing required parameter "Values" for data parameters of type "{ETYPE}"'.format(ETYPE=self.etype)
            mod_win2.popup_notice('Configuration warning: {PARAM}: {MSG}'.format(PARAM=name, MSG=msg))
            logger.warning(self.format_log(msg))
        else:
            for combo_value in combo_values:
                try:
                    self.combo_values.append(settings.format_value(combo_value, entry['DataType']))
                except ValueError:
                    msg = 'unable to format dropdown value "{VAL}"'.format(VAL=combo_value)
                    mod_win2.popup_notice('Configuration warning: {PARAM}: {MSG}'.format(PARAM=name, MSG=msg))
                    logger.warning(self.format_log(msg))

        self.disabled = False

    def _value_layout(self, size: tuple = None):
        """
        Configure the attributes for the record element's GUI layout.
        """
        font = mod_const.LARGE_FONT
        text_col = mod_const.DEFAULT_TEXT_COLOR
        bg_col = self.bg_col
        value_col = mod_const.DEFAULT_BG_COLOR

        elem_key = self.key_lookup('Element')
        tooltip = display_value = self.format_display()

        try:
            values = self.combo_values
        except KeyError:
            logger.warning(self.format_log('dropdown was selected for the data element but no '
                                           'values were provided to populate the dropdown'))
            display_values = []
        else:
            display_values = []
            for option in values:
                display_values.append(self.format_display(value=option))

        aux_key = self.key_lookup('Auxiliary')
        aux_layout = [sg.pin(sg.Col([[]], key=aux_key, background_color=value_col, visible=False))]

        layout_attrs = {'Key': elem_key, 'DisplayValue': display_value, 'Font': font, 'Size': size,
                        'BackgroundColor': value_col, 'TextColor': text_col, 'Disabled': True, 'Tooltip': tooltip,
                        'ComboValues': display_values}
        element_layout = mod_lo.generate_layout('dropdown', layout_attrs)

        content_width_key = self.key_lookup('ContentWidth')
        layout = [sg.Col([[sg.Canvas(key=content_width_key, background_color=bg_col, size=(1, 0))],
                           element_layout + aux_layout], background_color=bg_col)]

        return layout


class DataVariableMultiline(DataVariable):
    """
    Multiline-style data variable element.

    Attributes:

        name (str): record element configuration name.

        elements (list): list of element GUI keys.

        nrow (int): number of rows in the multiline element.
    """

    def __init__(self, name, entry, parent=None):
        """
        Initialize the record element attributes.

        Arguments:
            name (str): data element configuration name.

            entry (dict): configuration entry for the data element.

            parent (str): name of the parent element.
        """
        super().__init__(name, entry, parent)

        self.etype = 'multiline'

        # Enforce supported data types for the dropdown parameter
        supported_dtypes = settings.supported_str_dtypes
        if entry['DataType'] not in supported_dtypes:
            msg = self.format_log('unsupported data type provided for the "{ETYPE}" parameter. Supported data types '
                                  'are {DTYPES}'.format(ETYPE=self.etype, DTYPES=', '.join(supported_dtypes)))
            logger.error(msg)

            raise AttributeError(msg)

        # Number of rows to display in the multiline element
        try:
            self.nrow = int(entry['Nrow'])
        except (KeyError, ValueError):
            self.nrow = 1

        self.disabled = False

    def _value_layout(self, size: tuple = None):
        """
        Configure the attributes for the record element's GUI layout.
        """
        font = mod_const.LARGE_FONT
        text_col = mod_const.DEFAULT_TEXT_COLOR
        bg_col = self.bg_col
        value_col = mod_const.DEFAULT_BG_COLOR

        elem_key = self.key_lookup('Element')
        tooltip = display_value = self.format_display()
        nrow = self.nrow

        aux_key = self.key_lookup('Auxiliary')
        aux_layout = [sg.pin(sg.Col([[]], key=aux_key, background_color=value_col, visible=False))]

        layout_attrs = {'Key': elem_key, 'DisplayValue': display_value, 'Font': font, 'Size': size,
                        'BackgroundColor': value_col, 'TextColor': text_col, 'Disabled': True, 'Tooltip': tooltip,
                        'NRow': nrow}
        element_layout = mod_lo.generate_layout('multiline', layout_attrs)

        content_width_key = self.key_lookup('ContentWidth')
        layout = [sg.Col([[sg.Canvas(key=content_width_key, background_color=bg_col, size=(1, 0))],
                          element_layout + aux_layout], background_color=bg_col)]

        return layout


class DataVariableCheckbox(DataVariable):
    """
    Checkbox-style data variable element.

    Attributes:

        name (str): record element configuration name.

        elements (list): list of element GUI keys.

        nrow (int): number of rows in the multiline element.
    """

    def __init__(self, name, entry, parent=None):
        """
        Initialize the record element attributes.

        Arguments:
            name (str): data element configuration name.

            entry (dict): configuration entry for the data element.

            parent (str): name of the parent element.
        """
        super().__init__(name, entry, parent)

        self.etype = 'checkbox'

        # Enforce supported data types for the dropdown parameter
        supported_dtypes = settings.supported_bool_dtypes
        if entry['DataType'] not in supported_dtypes:
            msg = self.format_log('unsupported data type provided for the "{ETYPE}" parameter. Supported data types '
                                  'are {DTYPES}'.format(ETYPE=self.etype, DTYPES=', '.join(supported_dtypes)))
            logger.error(msg)

            raise AttributeError(msg)

        self.arrangement = 'h'
        self.disabled = False

    def _value_layout(self, size: tuple = None):
        """
        Configure the attributes for the record element's GUI layout.
        """
        font = mod_const.LARGE_FONT
        text_col = mod_const.DEFAULT_TEXT_COLOR
        bg_col = self.bg_col

        elem_key = self.key_lookup('Element')
        tooltip = display_value = self.format_display()

        aux_key = self.key_lookup('Auxiliary')
        aux_layout = [sg.pin(sg.Col([[]], key=aux_key, background_color=bg_col, visible=False))]

        layout_attrs = {'Key': elem_key, 'DisplayValue': display_value, 'Font': font, 'Size': size,
                        'BackgroundColor': bg_col, 'TextColor': text_col, 'Disabled': True, 'Tooltip': tooltip}
        element_layout = mod_lo.generate_layout('checkbox', layout_attrs)

        content_width_key = self.key_lookup('ContentWidth')
        layout = [sg.Col([[sg.Canvas(key=content_width_key, background_color=bg_col, size=(1, 0))],
                          element_layout + aux_layout], background_color=bg_col)]

        return layout


# Element reference variable
class DependentVariable(DataVariable):
    """
    Record element that is dependent on the values of other record elements.

    Attributes:

        name (str): data element configuration name.

        elements (list): list of data element GUI keys.

        operation (str): reference operation.
    """

    def __init__(self, name, entry, parent=None):
        """
        Class attributes.

        Arguments:
            name (str): name of the configured element.

            entry (dict): configuration entry for the data storage element.

            parent (str): name of the parent element.
        """
        super().__init__(name, entry, parent)

        self.etype = 'dependent'

        # Data type check
        supported_dtypes = settings.supported_int_dtypes + settings.supported_float_dtypes + \
                           settings.supported_bool_dtypes
        if entry['DataType'] not in supported_dtypes:
            msg = self.format_log('unsupported data type provided for the "{ETYPE}" parameter. Supported data types '
                                  'are {DTYPES}'.format(ETYPE=self.etype, DTYPES=', '.join(supported_dtypes)))
            logger.error(msg)

            raise AttributeError(msg)

        # Reference parameter information
        try:
            self.operation = entry['Operation']
        except KeyError:
            msg = self.format_log('reference element is missing required parameter "Operation".'.format(NAME=name))
            logger.error(msg)

            raise AttributeError(msg)

        self.disabled = True

    def _value_layout(self, size: tuple = None):
        """
        Configure the attributes for the record element's GUI layout.
        """
        font = mod_const.LARGE_FONT
        text_col = mod_const.DISABLED_TEXT_COLOR
        bg_col = self.bg_col
        value_col = mod_const.DEFAULT_BG_COLOR

        elem_key = self.key_lookup('Element')
        tooltip = display_value = self.format_display()

        layout_attrs = {'Key': elem_key, 'DisplayValue': display_value, 'Font': font, 'Size': size, 'BW': 1,
                        'BackgroundColor': value_col, 'TextColor': text_col, 'Disabled': True, 'Tooltip': tooltip}
        element_layout = mod_lo.generate_layout('text', layout_attrs)

        content_width_key = self.key_lookup('ContentWidth')
        layout = [sg.Col([[sg.Canvas(key=content_width_key, background_color=bg_col, size=(1, 0))],
                          element_layout], background_color=bg_col)]

        return layout

    def run_event(self, window, event, values):
        """
        Run a record element event.
        """
        triggers = {'ValueEvent': False, 'ResizeEvent': False, 'DisplayEvent': False}

        try:
            element_event = self.bindings[event]
        except KeyError:  # possible manual event passed
            element_event = event

        logger.debug(self.format_log('running dependent variable event {EVENT}'.format(EVENT=element_event)))

        if element_event == 'Element':
            edited = self.format_value(values)
            if edited:
                self.edited = True
                self.update_display(window)

        return triggers

    def format_value(self, values):
        """
        Set the value of the element reference from user input.

        Arguments:
            values (dict): single value or dictionary of element values.
        """
        # Update element display value
        logger.debug(self.format_log('setting the value of the dependent variable'))
        if isinstance(values, dict):  # dictionary of referenced element values
            try:
                input_value = mod_dm.evaluate_operation(values, self.operation)
            except Exception as e:
                msg = self.format_log('failed to set the value of the dependent variable', err=e)
                logger.error(msg)
                input_value = None

        else:  # single value provided
            input_value = values

        if input_value == '' or pd.isna(input_value):
            return None

        edited = self.update_value(input_value)

        return edited


class DataConstant(DataUnit):
    """
    Flags or text of static record information.

    Attributes:

        name (str): data element configuration name.

        elements (list): list of data element GUI keys.
    """

    def __init__(self, name, entry, parent=None):
        """
        Initialize the record element attributes.

        Arguments:
            name (str): record element configuration name.

            entry (dict): configuration entry for the record element.

            parent (str): name of the parent record.
        """
        super().__init__(name, entry, parent)
        record_elements = ('Description', 'Frame', 'Width')
        self.elements.update({i: '-{NAME}_{ID}_{ELEM}-'.format(NAME=name, ID=self.id, ELEM=i) for i in record_elements})

        if self.etype != 'checkbox':
            self.etype = 'text'

        self.arrangement = 'h'
        self.disabled = True

    def format_value(self, values):
        """
        Obtain the value of the record element from the set of GUI element values.

        Arguments:
            values (dict): single value or dictionary of element values.
        """
        if isinstance(values, dict):  # dictionary of referenced element values
            try:
                value = values[self.name]
            except KeyError:
                msg = self.format_log('input data is missing a value for the record element')
                logger.warning(msg)

                raise KeyError(msg)
        else:  # single value provided
            value = values

        if not pd.isna(value):  # should not update when metadata is missing
            edited = self.update_value(value)
        else:
            edited = False

        return edited

    def reset(self, window):
        """
        Reset record element to default.
        """
        self.value.reset()

        # Update the element display
        self.update_display(window)

    def layout(self, padding: tuple = None, size: tuple = None, tooltip: str = None, bg_color: str = None):
        """
        GUI layout for the record element.
        """
        if size:
            width, height = size
            self._dimensions = (width * 9, height * 9)
        else:  # rough convert to chars if size not set
            width, height = [int(i / 9) for i in self._dimensions]

        tooltip = tooltip if tooltip else self.tooltip

        # Layout options
        pad_el = mod_const.ELEM_PAD
        pad_h = mod_const.HORZ_PAD
        pad = padding if padding and isinstance(padding, tuple) else self.padding
        self.padding = pad

        font = mod_const.LARGE_FONT
        bold_font = mod_const.BOLD_HEADING_FONT

        bg_col = self.bg_col if bg_color is None else bg_color
        self.bg_col = bg_col
        text_col = mod_const.DEFAULT_TEXT_COLOR

        # Element Icon, if provided
        icon = self.icon
        if icon is not None:
            icon_path = settings.get_icon_path(icon)
            if icon_path is not None:
                icon_layout = [sg.Image(filename=icon_path, pad=((0, pad_h), 0), background_color=bg_col)]
            else:
                icon_layout = []
        else:
            icon_layout = []

        # Element description and actions
        elem_key = self.key_lookup('Element')
        desc_key = self.key_lookup('Description')
        display_value = self.format_display()
        desc_bg_col = bg_col

        desc_layout = [sg.Text('{}:'.format(self.description), key=desc_key, pad=((0, pad_el), 0), font=bold_font,
                               background_color=desc_bg_col, auto_size_text=True, tooltip=tooltip)]

        layout_attrs = {'Key': elem_key, 'DisplayValue': display_value, 'Font': font, 'Size': (width, 1),
                        'BackgroundColor': bg_col, 'TextColor': text_col, 'Disabled': True, 'Tooltip': tooltip}
        content_width_key = self.key_lookup('ContentWidth')
        elem_layout = [sg.Col([[sg.Canvas(key=content_width_key, size=(1, 0), background_color=bg_col)],
                                mod_lo.generate_layout('text', layout_attrs)],
                              background_color=bg_col)]

        # Layout
        frame_key = self.key_lookup('Frame')
        width_key = self.key_lookup('Width')
        row1 = icon_layout + desc_layout + elem_layout
        layout = sg.Col([[sg.Canvas(key=width_key, size=(1, 0), background_color=bg_col)], row1],
                        key=frame_key, pad=pad, background_color=bg_col, vertical_alignment='c',
                        element_justification=self.justification)

        return layout


class TableButton:
    """
    Table action button.

    Attributes:

        name (str): data element configuration name.

        elements (list): list of data element GUI keys.

        description (str): display name of the data element.

        icon (str): file name of the parameter's icon [Default: None].
    """

    def __init__(self, name, parent, parent_id, entry):
        """
        GUI data storage element.

        Arguments:
            name (str): name of the configured element.

            parent (str): name of the parent table.

            parent_id (int): ID of the parent table.

            entry (dict): configuration entry for the data storage element.
        """
        self.name = name
        self.element_key = '-{PARENT}_{ID}_{NAME}-'.format(PARENT=parent, NAME=name, ID=parent_id)
        self.parent_key = '-{PARENT}_{ID}_Element-'.format(PARENT=parent, ID=parent_id)
        self.bindings = {self.element_key: name}

        try:
            self.description = entry['Description']
        except KeyError:
            self.description = name

        try:
            self.shortcut = entry['Shortcut']
        except KeyError:
            self.shortcut = None
            self.shortcut_key = None
        else:
            self.shortcut_key = '+{DESC}+'.format(DESC=self.name.upper())
            self.bindings['{ELEM}{KEY}'.format(ELEM=self.parent_key, KEY=self.shortcut_key)] = name

        # Layout attributes
        try:
            self.icon = entry['Icon']
        except KeyError:
            self.icon = None

        try:
            self.bg_col = entry['BackgroundColor']
        except KeyError:
            self.bg_col = mod_const.DEFAULT_BG_COLOR

        self.disabled = False

    def key_lookup(self):
        """
        Lookup an element's component GUI key using the name of the component element.
        """
        return (self.element_key, '{PARENT}{KEY}'.format(PARENT=self.parent_key, KEY=self.shortcut_key))

    def bind_keys(self, window, element_key):
        """
        Add hotkey bindings to the data element.
        """
        shortcut = '<{}>'.format(self.shortcut)
        if shortcut:
            bind_key = self.shortcut_key
            window[element_key].bind(shortcut, bind_key)

    def layout(self, size: tuple = None, padding: tuple = None, bg_col: str = None, disabled: bool = False):
        """
        Create a GUI layout for the parameter.
        """
        bg_col = bg_col if bg_col else self.bg_col
        self.bg_col = bg_col
        self.disabled = disabled

        size = size if size else mod_const.PARAM_SIZE_CHAR

        # Element settings
        text_col = mod_const.DEFAULT_TEXT_COLOR  # standard text color
        highlight_col = mod_const.HIGHLIGHT_COLOR

        # Parameter size
        width, height = size
        bwidth = 1

        # Element icon, if provided
        icon_path = settings.get_icon_path(self.icon) if self.icon else None

        # Element layout
        elem_key = self.element_key
        layout = sg.Button('', key=elem_key, image_filename=icon_path, size=(width, height), pad=padding,
                           disabled=disabled, border_width=bwidth, button_color=(text_col, bg_col),
                           mouseover_colors=(text_col, highlight_col),
                           tooltip=self.description, metadata={'visible': True, 'disabled': disabled})

        return layout

    def toggle(self, window, off: bool = False):
        """
        Toggle the button element on or off.
        """
        element_key = self.element_key
        window[element_key].update(disabled=off)
        self.disabled = off
