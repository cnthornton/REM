"""
REM standard GUI element classes such as tables and information boxes.
"""

import datetime
from math import ceil as ceiling
import re
import sys
from random import randint

import PySimpleGUI as sg
import numpy as np
import pandas as pd

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

        self.elements = ['-{NAME}_{ID}_{ELEM}-'.format(NAME=name, ID=self.id, ELEM=i) for i in
                         ('Element',)]

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
                logger.warning('{TYPE} {NAME}: {MSG}'.format(TYPE=self.etype, NAME=self.name, MSG=msg))

                continue

            self.annotation_rules[code] = {'BackgroundColor': rule.get('BackgroundColor', mod_const.FAIL_COL),
                                           'Description': rule.get('Description', code),
                                           'Condition': rule['Condition']}

        try:
            bg_col = entry['BackgroundColor']
        except KeyError:
            self.bg_col = mod_const.ACTION_COL
        else:
            if isinstance(bg_col, str) and (not bg_col.startswith('#') or len(bg_col) != 7):  # hex color codes
                self.bg_col = mod_const.ACTION_COL
            else:
                self.bg_col = bg_col

        try:
            self.icon = entry['Icon']
        except KeyError:
            self.icon = None

        try:
            self.tooltip = entry['Tooltip']
        except KeyError:
            self.tooltip = None

        # Dynamic variables
        self.edited = False

    def key_lookup(self, component):
        """
        Lookup a record element's GUI element key using the name of the component.
        """
        element_names = [i[1: -1].split('_')[-1] for i in self.elements]
        # element_names = [re.match(r'-(.*?)-', i).group(1).split('_')[-1] for i in self.elements]
        if component in element_names:
            key_index = element_names.index(component)
            key = self.elements[key_index]
        else:
            msg = '{ETYPE} {NAME}: component "{COMP}" not found in list of element components' \
                .format(ETYPE=self.etype, NAME=self.name, COMP=component)
            logger.warning(msg)
            logger.debug('{ETYPE} {NAME}: element contains components {COMP}'
                         .format(ETYPE=self.etype, NAME=self.name, COMP=element_names))

            raise KeyError(msg)

        return key


class TableElement(RecordElement):
    """
    Record data table element.

    Attributes:

        name (str): table element configuration name.

        id (int): table element number.

        elements (list): list of table GUI element keys.

        description (str): display title.

        etype (str): record element type.

        eclass (str): record element class.

        columns (list): list of table columns.

        display_columns (dict): display names of the table columns.

        display_columns (dict): display columns to hide from the user.

        search_field (str): column used when searching the table.

        parameters (list): list of filter parameters.

        aliases (dict): dictionary of column value aliases.

        tally_rule (str): rules used to calculate totals.

        annotation_rules (dict): rules used to annotate the data table.

        filter_rules (dict): rules used to automatically filter the data table.

        summary_rules (dict): rules used to summarize the data table.

        df (DataFrame): pandas dataframe containing table data.

        icon (str): name of the icon file containing the image to represent the table.

        nrow (int): number of rows to display.

        widths (list): list of relative column widths. If values are fractions < 1, values will be taken as percentages,
            else relative widths will be calculated relative to size of largest column.

        sort_on (list): columns to sort the table by

        row_color (str): hex code for the color of alternate rows.

        select_mode (str): table selection mode. Options are "browse" and "extended" [Default: extended].

        tooltip (str): table tooltip.

        edited (bool): table was edited [Default: False].
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

        self.etype = 'table'
        self.eclass = 'data'
        self.elements.extend(['-{NAME}_{ID}_{ELEM}-'.format(NAME=name, ID=self.id, ELEM=i) for i in
                              ('Table', 'Export', 'Total', 'Search', 'Filter', 'Fill', 'Frame0', 'FrameBttn0',
                               'Frame1', 'FrameBttn1', 'SummaryTable', 'Sort', 'Options', 'OptionsFrame',
                               'OptionsWidth', 'WidthCol1', 'WidthCol2', 'WidthCol3', 'TitleBar', 'FilterBar',
                               'SummaryBar', 'ActionsBar')])
        self._event_elements = ['Element', 'Filter', 'Fill', 'Sort', 'Export', 'FrameBttn0', 'FrameBttn1', 'Options']

        # Element-specific bindings
        elem_key = self.key_lookup('Element')
        return_key = '{}+RETURN+'.format(elem_key)
        open_key = '{}+LCLICK+'.format(elem_key)
        filter_hkey = '{}+FILTER+'.format(elem_key)
        self.bindings = [self.key_lookup(i) for i in self._event_elements] + [open_key, return_key, filter_hkey]

        self._action_events = [open_key, return_key]
        self._supported_stats = ['sum', 'count', 'product', 'mean', 'median', 'mode', 'min', 'max', 'std', 'unique']

        try:
            self.custom_actions = entry['CustomActions']
        except KeyError:
            self.custom_actions = {}

        try:
            modifiers = entry['Modifiers']
        except KeyError:
            self.modifiers = {'edit': False, 'export': False, 'search': False, 'summary': False, 'filter': False,
                              'fill': False, 'options': False, 'sort': False, 'require': False}
        else:
            self.modifiers = {'edit': modifiers.get('edit', 0), 'export': modifiers.get('export', 0),
                              'search': modifiers.get('search', 0), 'summary': modifiers.get('summary', 0),
                              'filter': modifiers.get('filter', 0), 'fill': modifiers.get('fill', 0),
                              'options': modifiers.get('options', 0), 'sort': modifiers.get('sort', 0),
                              'require': modifiers.get('require', 0)}
            for modifier in self.modifiers:
                try:
                    flag = bool(int(self.modifiers[modifier]))
                except ValueError:
                    logger.warning('DataTable {TBL}: modifier {MOD} must be either 0 (False) or 1 (True)'
                                   .format(TBL=self.name, MOD=modifier))
                    flag = False

                self.modifiers[modifier] = flag

        try:
            columns = entry['Columns']
        except KeyError:
            raise AttributeError('missing required parameter "Columns"')
        except ValueError:
            raise AttributeError('unknown input provided to required parameter "Columns"')
        else:
            if isinstance(columns, dict):
                self.columns = columns
                supported_dtypes = settings.get_supported_dtypes()
                for col_name, col_dtype in columns.items():
                    if col_dtype not in supported_dtypes:
                        logger.warning('DataTable {NAME}: the data type specified for column "{COL}" is not a '
                                       'supported data type - supported data types are {TYPES}'
                                       .format(NAME=name, COL=col_name, TYPES=', '.join(supported_dtypes)))
                        self.columns[col_name] = 'varchar'
            else:
                self.columns = {i: 'varchar' for i in columns}

        try:
            display_columns = entry['DisplayColumns']
        except KeyError:
            self.display_columns = {i: i for i in columns.keys()}
        else:
            self.display_columns = {}
            for display_column in display_columns:
                if display_column in self.columns:
                    self.display_columns[display_column] = display_columns[display_column]
                else:
                    msg = 'display column {COL} not found in the list of table columns'.format(COL=display_column)
                    logger.warning('DataTable {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

        try:
            hidden_columns = entry['HiddenColumns']
        except KeyError:
            hidden_columns = []

        self.hidden_columns = []
        for hide_column in hidden_columns:
            if hide_column in self.display_columns:
                self.hidden_columns.append(self.display_columns[hide_column])
            else:
                msg = 'hidden column "{COL}" not found in the list of table display columns'.format(COL=hide_column)
                logger.warning('DataTable {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

        try:
            search_field = entry['SearchField']
        except KeyError:
            self.search_field = None
        else:
            if search_field not in columns:
                logger.warning('DataTable {NAME}: search field {FIELD} is not found in list of table columns ... '
                               'setting to None'.format(NAME=name, FIELD=search_field))
                self.search_field = None
            else:
                self.search_field = (search_field, None)

        try:
            self.filter_entry = entry['FilterParameters']
        except KeyError:
            self.filter_entry = {}

        self.parameters = []
        for param_name in self.filter_entry:
            if param_name not in self.columns:
                logger.warning('DataTable {NAME}: filter parameters "{PARAM}" must be listed in '
                               'the table columns'.format(NAME=name, PARAM=param_name))
                continue

            param_entry = self.filter_entry[param_name]
            try:
                param = mod_param.initialize_parameter(param_name, param_entry)
            except Exception as e:
                logger.error('DataTable {NAME}: {MSG}'.format(NAME=self.name, MSG=e))
                continue

            self.parameters.append(param)
            self.bindings.extend(param.bindings)

        try:
            edit_columns = entry['EditColumns']
        except KeyError:
            self.edit_columns = {}
        else:
            self.edit_columns = {}
            for edit_column in edit_columns:
                if edit_column not in columns:
                    logger.warning('DataTable {NAME}: editable column "{COL}" must be listed in the table columns'
                                   .format(NAME=name, COL=edit_column))

                    continue
                else:
                    self.edit_columns[edit_column] = edit_columns[edit_column]

        try:
            column_defaults = entry['Defaults']
        except KeyError:
            self.defaults = {}
        else:
            self.defaults = {}
            for default_col in column_defaults:
                if default_col not in columns:
                    logger.warning('DataTable {NAME}: default column {COL} not listed in the table columns'
                                   .format(NAME=self.name, COL=default_col))
                    continue
                else:
                    self.defaults[default_col] = column_defaults[default_col]

        try:
            cond_cols = entry['ConditionalColumns']
        except KeyError:
            self.conditional_columns = {}
        else:
            self.conditional_columns = {}
            for cond_col in cond_cols:
                if cond_col not in columns:
                    logger.warning('DataTable {NAME}: conditional column {COL} not listed in the table columns'
                                   .format(NAME=self.name, COL=cond_col))
                    continue
                else:
                    cond_entry = cond_cols[cond_col]
                    if 'DefaultRule' not in cond_entry and 'DefaultCondition' not in cond_entry:
                        logger.warning('DataTable {NAME}: conditional column "{COL}" is missing required parameter '
                                       '"DefaultRule" or "DefaultCondition"'.format(NAME=self.name, COL=cond_col))

                        continue

                    self.conditional_columns[cond_col] = cond_entry

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
                column_dtype = self.columns[alias_column]
                if column_dtype in (settings.supported_int_dtypes + settings.supported_cat_dtypes +
                                    settings.supported_str_dtypes):
                    alias_map = {settings.format_value(i, column_dtype): j for i, j in alias_map.items()}

                    self.aliases[alias_column] = alias_map
            else:
                msg = 'alias column {COL} not found in list of display columns'.format(COL=alias_column)
                logger.warning('DataTable {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

        try:
            self.tally_rule = entry['TallyRule']
        except KeyError:
            self.tally_rule = None

        try:
            filter_rules = entry['FilterRules']
        except KeyError:
            self.filter_rules = {}
        else:
            self.filter_rules = {}
            for filter_key in filter_rules:
                if filter_key in columns:
                    self.filter_rules[filter_key] = filter_rules[filter_key]
                else:
                    logger.warning('DataTable {NAME}: filter rule key {KEY} not found in table columns'
                                   .format(NAME=self.name, KEY=filter_key))

        try:
            summary_rules = entry['SummaryRules']
        except KeyError:
            self.summary_rules = {}
        else:
            self.summary_rules = {}
            for summary_name in summary_rules:
                summary_rule = summary_rules[summary_name]
                if 'Column' not in summary_rule:
                    msg = 'missing required field "Column" for summary rule {RULE}'.format(RULE=summary_name)
                    logger.warning('DataTable {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                    continue
                else:
                    summary_column = summary_rule['Column']
                    if summary_column not in self.columns:
                        msg = 'summary rule {RULE} column "{COL}" is not in the list of table columns' \
                            .format(RULE=summary_name, COL=summary_column)
                        logger.warning('DataTable {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                        continue

                if 'Statistic' in summary_rule:
                    statistic = summary_rule['Statistic']
                    if statistic not in self._supported_stats:
                        msg = 'unknown statistic {STAT} provided to summary rule "{SUMM}"' \
                            .format(STAT=statistic, SUMM=summary_name)
                        logger.warning('DataTable {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                        summary_rule['Statistic'] = None

                self.summary_rules[summary_name] = {'Column': summary_rule['Column'],
                                                    'Description': summary_rule.get('Description', summary_name),
                                                    'Condition': summary_rule.get('Condition', None),
                                                    'Statistic': summary_rule.get('Statistic', None)}

                self.elements.append('-{NAME}_{ID}_{ELEM}-'.format(NAME=self.name, ID=self.id, ELEM=summary_name))

        try:
            self.deleted_column = entry['DeletedColumn']
        except KeyError:
            self.deleted_column = 'RowDeleted'
        if self.deleted_column not in self.columns:
            self.columns[self.deleted_column] = 'bool'

        try:
            self.added_column = entry['AddedColumn']
        except KeyError:
            self.added_column = 'RowAdded'
        if self.added_column not in self.columns:
            self.columns[self.added_column] = 'bool'

        try:
            self.edited_column = entry['EditedColumn']
        except KeyError:
            self.edited_column = 'RowEdited'
        if self.edited_column not in self.columns:
            self.columns[self.edited_column] = 'bool'

        try:
            self.widths = entry['Widths']
        except KeyError:
            self.widths = None

        try:
            sort_on = entry['SortBy']
        except KeyError:
            self.sort_on = []
        else:
            self.sort_on = []
            for sort_col in sort_on:
                if sort_col in self.columns:
                    self.sort_on.append(sort_col)
                else:
                    logger.warning('DataTable {NAME}: sort column {COL} not found in table columns'
                                   .format(NAME=self.name, COL=sort_col))

        try:
            self.nrow = int(entry['Rows'])
        except KeyError:
            self.nrow = mod_const.TBL_NROW
        except ValueError:
            logger.warning('DataTable {TBL}: input to the Rows parameter must be an integer value'
                           .format(TBL=self.name))
            self.nrow = mod_const.TBL_NROW

        try:
            row_color = entry['RowColor']
        except KeyError:
            self.row_color = mod_const.TBL_ALT_COL
        else:
            if not row_color.startswith('#') or not len(row_color) == 7:
                logger.warning('DataTable {TBL}: row color {COL} is not a valid hexadecimal code'
                               .format(TBL=self.name, COL=row_color))
                self.row_color = mod_const.TBL_BG_COL
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
        self._frame_heights = {0: 0, 1: 0}
        self._dimensions = (0, 0)
        self._min_size = (0, 0)

        self.df = self._set_datatypes(pd.DataFrame(columns=list(self.columns)))
        self._selected_rows = []
        self.index_map = {}
        self._colors = []

    def _apply_filter(self):
        """
        Filter the table based on values supplied to the table filter parameters.
        """
        parameters = self.parameters
        df = self.data()

        if df.empty:
            return df

        logger.debug('DataTable {NAME}: filtering the display table based on user-supplied parameter values'
                     .format(NAME=self.name))

        for param in parameters:
            df = param.filter_table(df)

        return df

    def _display_header(self):
        """
        Return the visible header of the display table.
        """
        display_map = self.display_columns
        hidden_columns = self.hidden_columns
        header = []
        for column in display_map:
            display_column = display_map[column]

            if display_column in hidden_columns:
                continue

            header.append(display_column)

        return header

    def _update_column_widths(self, window, width: int = None, summary: bool = False):
        """
        Update the sizes of the data table or summary table columns.
        """
        if summary:
            summary_rules = self.summary_rules
            header = [summary_rules[summary_name].get('Description') for summary_name in summary_rules]
            elem_key = self.key_lookup('SummaryTable')
            widths = None
            nrow = 1
        else:
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
                logger.warning('DataTable {NAME}: division by zero error encountered while attempting to calculate '
                               'column widths'.format(NAME=self.name))
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

    def _filter_deleted(self, df):
        """
        Filter deleted rows from the table dataframe.
        """
        is_bool_dtype = pd.api.types.is_bool_dtype

        column = self.deleted_column

        if df.empty:
            return df

        if column not in df.columns.values:
            df[column] = False

        df[column].fillna(False, inplace=True)
        if not is_bool_dtype(df[column].dtype):
            logger.debug('DataTable {NAME}: setting datatype of deleted column "{COL}" to boolean'
                         .format(NAME=self.name, COL=column))
            try:
                df = df.astype({column: 'bool'})
            except ValueError:
                logger.warning('DataTable {NAME}: unable to set the datatype of delete column "{COL}" to boolean'
                               .format(NAME=self.name, COL=column))
                return df

        logger.debug('DataTable {NAME}: filtering deleted rows on deleted column "{COL}"'
                     .format(NAME=self.name, COL=column))

        df = df[~df[self.deleted_column]]

        return df

    def _set_column_dtype(self, column_values, name: str = None, dtype: str = None):
        """
        Set the datatype for table column values based on the datatype map.

        Arguments:
            column_values (Series): pandas Series containing column values.

            name (str): optional column name if not set in the series.

            dtype (str): manually set the data type of the column to dtype [Default: set as configured data type].
        """
        dtype_map = self.columns

        if not isinstance(column_values, pd.Series):
            column_values = pd.Series(column_values)

        column_name = column_values.name if not name else name
        try:
            dtype = dtype_map[column_name] if not dtype else dtype
        except KeyError:
            logger.warning('DataTable {NAME}: no datatype configured for column {COL} - setting to varchar'
                           .format(NAME=self.name, COL=column_name))
            dtype = 'varchar'

        if dtype in ('date', 'datetime', 'timestamp', 'time'):
            is_datetime_dtype = pd.api.types.is_datetime64_any_dtype

            if not is_datetime_dtype(column_values.dtype):
                try:
                    values = pd.to_datetime(column_values.fillna(pd.NaT), errors='coerce', format=settings.date_format, utc=False)
                except Exception as e:
                    msg = 'failed to set datatype {DTYPE} for column {COL} - {ERR}'\
                        .format(DTYPE=dtype, COL=column_name, ERR=e)
                    print(column_values)
                    logger.exception('DataTable {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                    raise ValueError(msg)
            else:  # is datetime dtype
                values = column_values.dt.tz_localize(None)
                #values = column_values.apply(lambda x: x.replace(tzinfo=None))

        elif dtype in ('int', 'integer', 'bigint'):
            try:
                values = column_values.astype('Int64')
            except TypeError:
                values = column_values.astype(float).astype('Int64')
        elif dtype == 'mediumint':
            try:
                values = column_values.astype('Int32')
            except TypeError:
                values = column_values.astype(float).astype('Int32')
        elif dtype == 'smallint':
            try:
                values = column_values.astype('Int16')
            except TypeError:
                values = column_values.astype(float).astype('Int16')
        elif dtype in ('tinyint', 'bit'):
            try:
                values = column_values.astype('Int8')
            except TypeError:
                values = column_values.astype(float).astype('Int8')
        elif dtype in ('float', 'real', 'double'):  # approximate numeric data types for saving memory
            values = pd.to_numeric(column_values, errors='coerce', downcast='float')
        elif dtype in ('decimal', 'dec', 'numeric', 'money'):  # exact numeric data types
            values = pd.to_numeric(column_values, errors='coerce')
        elif dtype in ('bool', 'boolean'):
            values = column_values.fillna(False).astype(np.bool, errors='raise')
        elif dtype in ('char', 'varchar', 'binary', 'text', 'string'):
            values = column_values.astype(np.object, errors='raise')
        else:
            values = column_values.astype(np.object, errors='raise')

        return values

    def _set_datatypes(self, df=None):
        """
        Set column_name data types based on header mapping
        """
        df = self.df.copy() if df is None else df
        dtype_map = self.columns

        if isinstance(df, pd.Series):  # need to convert series to dataframe first
            df = df.to_frame().T

        header = df.columns.tolist()

        if not isinstance(dtype_map, dict):
            logger.warning('DataTable {NAME}: unable to set column datatypes. Columns must be configured '
                           'as an object to specify data types'.format(NAME=self.name))
            return df

        for column_name in dtype_map:
            if column_name not in header:
                logger.warning('DataTable {NAME}: configured column "{COL}" is not in the dataframe header - setting '
                               'initial value to NaN'.format(NAME=self.name, COL=column_name))
                df[column_name] = None

            dtype = dtype_map[column_name]
            column = df[column_name]
            try:
                column_values = self._set_column_dtype(column)
            except Exception as e:
                logger.exception('DataTable {NAME}: unable to set column "{COL}" to data type "{DTYPE}" - {ERR}'
                                 .format(NAME=self.name, COL=column_name, DTYPE=dtype, ERR=e))
                logger.debug('DataTable {NAME}: column "{COL}" values are {VALS}'
                             .format(NAME=self.name, COL=column_name, VALS=column.values))
            else:
                try:
                    df.loc[:, column_name] = column_values
                except ValueError as e:
                    logger.exception('DataTable {NAME}: unable to set column "{COL}" to data type "{DTYPE}" - {ERR}'
                                     .format(NAME=self.name, COL=column_name, DTYPE=dtype, ERR=e))
                    logger.debug('DataTable {NAME}: column values are {VALS}'
                                 .format(NAME=self.name, VALS=column_values))

        return df

    def _update_row_values(self, index, values):
        """
        Update row values at the given dataframe index.

        Arguments:
            index (int): real index of the row to update.

            values (DataFrame): single row dataframe containing row values to use to update the dataframe at the
               given index.
        """
        df = self.df
        header = df.columns.tolist()

        if isinstance(values, dict):
            if isinstance(index, int):
                index = [index]
            values = pd.DataFrame(values, index=index)
        elif isinstance(values, pd.Series):  # single set of row values
            values.name = index
            values = values.to_frame().T
        else:  # dataframe of row values
            values = values.set_index(pd.Index(index))

        shared_cols = [i for i in values.columns if i in header]
        new_values = self._set_datatypes(df=values)[shared_cols]

        edited_rows = set()
        for row_ind, row in new_values.iterrows():
            for column, row_value in row.iteritems():
                orig_value = df.loc[row_ind, column]
                if row_value != orig_value:
                    df.at[index, column] = row_value
                    edited_rows.add(row_ind)

        edited = False
        if len(edited_rows) > 0:
            edited_col = self.edited_column
            self.edited = edited = True
            for edited_ind in edited_rows:
                df.loc[edited_ind, edited_col] = True

            # Reset the datatype of the edited columns
            #for column in shared_cols:
            #    df.loc[:, column] = self._set_column_dtype(df[column])

        return edited

    def _update_row_values_old(self, index, values):
        """
        Update row values at the given dataframe index.

        Arguments:
            index (int): real index of the row to update.

            values (DataFrame): single row dataframe containing row values to use to update the dataframe at the
               given index.
        """
        df = self.df
        header = df.columns.tolist()

        if isinstance(values, dict):
            values = pd.Series(values)

        values.name = index

        shared_cols = [i for i in values.index if i in header]
        row_values = self._set_datatypes(df=values[shared_cols])

        new_values = row_values[shared_cols]
        orig_values = df.loc[[index]]
        orig_values = self._set_datatypes(df=orig_values)[shared_cols]
        try:
            diffs = orig_values.compare(new_values, align_axis=0).columns
        except Exception as e:
            logger.error('DataTable {NAME}: failed to compare new and original values - {ERR}'
                         .format(NAME=self.name, ERR=e))
            diffs = shared_cols

        edited = False
        if len(diffs) > 0:
            df.loc[[index], diffs] = new_values[diffs]
            df.at[index, self.edited_column] = True
            edited = True

            # Reset the datatype of the edited columns
            for column in diffs:
                df.loc[:, column] = self._set_column_dtype(df[column])

            self.edited = True

        return edited

    def reset(self, window, reset_filters: bool = True, collapse: bool = True):
        """
        Reset the data table to default.

        Arguments:
            window (Window): GUI window.

            reset_filters (bool): also reset filter parameter values [Default: True].

            collapse (bool): collapse supplementary table frames [Default: True].
        """
        # Reset dynamic attributes
        columns = list(self.columns)
        self.df = self._set_datatypes(pd.DataFrame(columns=columns))
        self.index_map = {}
        self.edited = False

        # Reset table filter parameters
        if reset_filters:
            for param in self.parameters:
                param.reset(window)

        # Collapse visible frames
        if collapse:
            frames = [self.key_lookup('Frame{}'.format(i)) for i in range(2)]
            for i, frame_key in enumerate(frames):
                if window[frame_key].metadata['disabled']:
                    continue

                if window[frame_key].metadata['visible']:  # frame was expanded at some point
                    self.collapse_expand(window, index=i)

        # Reset table dimensions
        self.set_table_dimensions(window)

        # Update the table display
        self.update_display(window)

    def deselect(self, window, indices: list = None):
        """
        Deselect selected table rows.
        """
        elem_key = self.key_lookup('Element')
        current_rows = self._selected_rows

        if indices and not isinstance(indices, list):
            raise TypeError('the indices argument must be a list')

        if indices:
            selected_rows = [i for i in current_rows if i not in indices]
        else:
            selected_rows = []

        self._selected_rows = selected_rows
        window[elem_key].update(select_rows=selected_rows, row_colors=self._colors)

    def select(self, window, indices):
        """
        Select rows at the given indices.
        """
        elem_key = self.key_lookup('Element')

        if not isinstance(indices, list):
            raise TypeError('the indices argument must be a list')

        first_ind = indices[0]
        total_rows = self.data(display_rows=True).shape[0]
        position = first_ind / total_rows

        self._selected_rows = indices
        window[elem_key].update(select_rows=indices, row_colors=self._colors)
        window[elem_key].set_vscroll_position(position)

    def selected(self, real: bool = False):
        """
        Return currently selected table rows.
        """
        current_rows = self._selected_rows

        if real:
            index_map = self.index_map

            try:
                selected_rows = [index_map[i] for i in current_rows]
            except KeyError:
                msg = 'missing index information for one or more selected rows'.format(NAME=self.name)
                logger.warning('DataTable {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                selected_rows = current_rows
        else:
            selected_rows = current_rows

        return selected_rows

    def fetch_parameter(self, element, by_key: bool = False):
        """
        Fetch a filter parameter by name or event key.
        """
        if by_key is True:
            element_type = element[1:-1].split('_')[-1]
            element_names = [i.key_lookup(element_type) for i in self.parameters]
        else:
            element_names = [i.name for i in self.parameters]

        if element in element_names:
            index = element_names.index(element)
            parameter = self.parameters[index]
        else:
            raise KeyError('element {ELEM} not found in list of {NAME} data elements'
                           .format(ELEM=element, NAME=self.name))

        return parameter

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
            logger.warning('DataTable {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
            indices = selected

        return indices

    def data(self, all_rows: bool = False, display_rows: bool = False, edited_rows: bool = False):
        """
        Return the table dataframe.

        Arguments:
            all_rows (bool): return all table rows, including the deleted rows [Default: False].

            display_rows (bool): return only the display rows [Default: False].

            edited_rows (bool): return only rows that have been edited or added to the table [Default: False].
        """
        if all_rows:
            df = self.df.copy()
        elif display_rows:
            search = self.search_field

            # Filter the table rows, if applicable
            try:
                search_col, search_value = search
            except (TypeError, ValueError):
                search_col = search_value = None

            if not search_value:  # no search value provided in the search field, try the filter parameters
                df = self._apply_filter()
            else:
                df = self._filter_deleted(self.df.copy())
                try:
                    df = df[df[search_col].str.contains(search_value, case=False, regex=True)]
                except KeyError:
                    msg = 'DataTable {NAME}: search field {COL} not found in list of table columns' \
                        .format(NAME=self.name, COL=search_col)
                    logger.warning(msg)
        else:
            df = self._filter_deleted(self.df.copy())

        # Filter on edited rows, if desired
        if edited_rows:
            df = df[(df[self.added_column]) | (df[self.edited_column])]

        return df

    def run_event(self, window, event, values):
        """
        Perform a table action.
        """
        elem_key = self.key_lookup('Element')
        search_key = self.key_lookup('Search')
        options_key = self.key_lookup('Options')
        frame_key = self.key_lookup('OptionsFrame')
        sort_key = self.key_lookup('Sort')
        fill_key = self.key_lookup('Fill')
        export_key = self.key_lookup('Export')
        filter_key = self.key_lookup('Filter')
        filter_hkey = '{}+FILTER+'.format(elem_key)
        frame_bttns = [self.key_lookup('FrameBttn{}'.format(i)) for i in range(2)]

        param_elems = [i for param in self.parameters for i in param.elements]
        action_events = self._action_events

        # Table events
        update_event = False
        if event == elem_key:
            selected_rows = values[elem_key]
            current_rows = self._selected_rows
            self._selected_rows = selected_rows

        elif event == search_key:
            # Update the search field value
            search_col = self.search_field[0]
            search_value = values[search_key]
            self.search_field = (search_col, search_value)

            self.update_display(window)

        elif event in frame_bttns:
            frame_index = frame_bttns.index(event)
            self.collapse_expand(window, index=frame_index)

        # Click filter Apply button to apply filtering to table
        elif event in (filter_key, filter_hkey):
            # Update parameter values
            for param in self.parameters:
                try:
                    param.value = param.format_value(values)
                except ValueError:
                    msg = 'failed to filter table rows - incorrectly formatted value provided to filter parameter ' \
                          '{PARAM}'.format(PARAM=param.description)
                    logger.error('DataTable {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
                    mod_win2.popup_error(msg)

                    return False

            # Update the display table to show the filtered table
            self.update_display(window)

        # Click to open table options panel
        elif event == options_key:
            if window[frame_key].metadata['visible'] is False:
                window[frame_key].metadata['visible'] = True

                tbl_width, tbl_height = window[elem_key].get_size()

                # Reduce table size
                frame_w = 220
                new_width = tbl_width - frame_w - 4 if tbl_width - frame_w - 4 > 0 else 0
                logger.debug('DataTable {NAME}: resizing the table from {W} to {NW} to accommodate the options frame '
                             'of width {F}'.format(NAME=self.name, W=tbl_width, NW=new_width, F=frame_w))
                self._update_column_widths(window, width=new_width)

                # Reveal the options frame
                window[frame_key].update(visible=True)
                window[frame_key].expand(expand_y=True)

                # Update the display table to show annotations properly
                self.update_display(window)
            else:
                self.set_table_dimensions(window)

        # Sort column selected from menu of sort columns
        elif event == sort_key:
            sort_on = self.sort_on
            display_map = {j: i for i, j in self.display_columns.items()}

            # Get sort column
            display_col = values[sort_key]
            try:
                sort_col = display_map[display_col]
            except KeyError:
                logger.warning('DataTable {NAME}: sort display column {COL} must have a one-to-one '
                               'mapping with a table column to sort'.format(NAME=self.name, COL=display_col))
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
        elif event == fill_key:
            display_map = {j: i for i, j in self.display_columns.items()}

            # Get selected rows, if any
            select_row_indices = values[elem_key]

            # Get the real indices of the selected rows
            indices = self.get_index(select_row_indices)
            if len(indices) < 2:
                msg = 'table fill requires more than one table rows to be selected'.format(NAME=self.name)
                logger.warning('DataTable {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                return False

            # Find the selected column to fill
            display_col = values[fill_key]
            try:
                fill_col = display_map[display_col]
            except KeyError:
                msg = 'fill display column {COL} must have a one-to-one mapping with a table display column' \
                    .format(COL=display_col)
                logger.warning('DataTable {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                return False

            # Fill in NA values
            self.fill(indices, fill_col)

            # Update the display table to show the new table values
            self.update_display(window)

        elif event in param_elems:
            try:
                param = self.fetch_parameter(event, by_key=True)
            except KeyError:
                logger.error('DataTable {TBL}: unable to find parameter associated with event key {KEY}'
                             .format(TBL=self.name, KEY=event))
            else:
                param.run_event(window, event, values)

        elif event == export_key:
            outfile = sg.popup_get_file('', title='Export table display', save_as=True,
                                        default_extension='xlsx', no_window=True,
                                        file_types=(('XLS - Microsoft Excel', '*.xlsx'),))

            if outfile:
                logger.info('DataTable {NAME}: exporting the display table to spreadsheet {FILE}'
                            .format(NAME=self.name, FILE=outfile))

                export_df = self.export_table()
                try:
                    export_df.to_excel(outfile, engine='openpyxl', header=True, index=False)
                except Exception as e:
                    msg = 'failed to save table to file to {FILE} - {ERR}'.format(FILE=outfile, ERR=e)
                    logger.exception(msg)
                    mod_win2.popup_error(msg)
            else:
                logger.warning('DataTable {NAME}: no output file selected'.format(NAME=self.name))

        elif event in action_events:
            update_event = self.run_action_event(window, event, values)

        return update_event

    def run_action_event(self, window, event, values):
        """
        Run a table action event.
        """
        elem_key = self.key_lookup('Element')
        open_key = '{}+LCLICK+'.format(elem_key)
        return_key = '{}+RETURN+'.format(elem_key)
        update_event = False

        can_open = self.modifiers['edit']

        # Row click event
        if event in (open_key, return_key) and can_open:
            # Close options panel, if open
            self.set_table_dimensions(window)

            # Find row selected by user
            try:
                select_row_index = values[elem_key][0]
            except IndexError:  # user double-clicked too quickly
                msg = 'table row could not be selected'
                logger.debug('DataTable {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
            else:
                self._selected_rows = [select_row_index]

                # Get the real index of the selected row
                index = self.get_index(select_row_index)

                logger.debug('DataTable {NAME}: opening row at real index {IND} for editing'
                             .format(NAME=self.name, IND=index))
                edited_row = self.edit_row(index)
                update_event = self._update_row_values(index, edited_row)

        # All action events require a table update
        if update_event:
            self.update_display(window)

        return update_event

    def bind_keys(self, window):
        """
        Add hotkey bindings to the data element.
        """
        level = self.level

        elem_key = self.key_lookup('Element')
        window[elem_key].bind('<Control-f>', '+FILTER+')

        if level < 2:
            window[elem_key].bind('<Return>', '+RETURN+')
            window[elem_key].bind('<Double-Button-1>', '+LCLICK+')

    def update_display(self, window, annotations: dict = None):
        """
        Format object elements for display.

        Arguments:
            window (Window): GUI window.

            annotations (dict): custom row color annotations to use instead of generating annotations from the
                configured annotation rules.
        """
        is_float_dtype = pd.api.types.is_float_dtype
        highlight_col = mod_const.SELECT_BG_COL
        white_text_col = mod_const.WHITE_TEXT_COL
        def_bg_col = mod_const.ACTION_COL
        text_col = mod_const.TEXT_COL

        dtypes = self.columns

        if not annotations:
            annotations = {}

        # Sort table and update table sorting information
        sort_key = self.key_lookup('Sort')
        #        search_field = self.search_field

        # Modify records tables for displaying
        logger.debug('DataTable {TBL}: formatting table for displaying'.format(TBL=self.name))

        self.sort(self.sort_on)

        if self.modifiers['sort'] is True:
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

        # Filter the table rows, if applicable
        df = self.data(display_rows=True)

        # Edit the index map to reflect what is currently displayed
        passed_indices = df.index.tolist()
        self.index_map = {i: j for i, j in enumerate(passed_indices)}

        annotations = {i: j for i, j in annotations.items() if i in passed_indices}

        df = df.reset_index()

        # Prepare annotations
        if len(annotations) < 1:  # highlight table rows using configured annotation rules
            annotations = self.annotate_rows(df)
            row_colors = [(i, self.annotation_rules[j]['BackgroundColor']) for i, j in annotations.items()]
        else:  # use custom annotations to highlight table rows
            row_colors = [(i, j) for i, j in annotations.items()]

        self._colors = row_colors

        # Format the table
        display_df = self.format_display_values(df)

        # Update the GUI with table values and annotations
        data = display_df.values.tolist()

        tbl_key = self.key_lookup('Element')
        window[tbl_key].update(values=data, row_colors=row_colors)

        # Update table totals
        try:
            tbl_total = self.calculate_total(df)
        except Exception as e:
            msg = 'DataTable {NAME}: failed to calculate table totals - {ERR}'.format(NAME=self.name, ERR=e)
            logger.warning(msg)
            tbl_total = 0

        if is_float_dtype(type(tbl_total)):
            tbl_total = '{:,.2f}'.format(tbl_total)
        else:
            tbl_total = str(tbl_total)

        total_key = self.key_lookup('Total')
        window[total_key].update(value=tbl_total)

        # Update the table summary
        if self.summary_rules:
            table_summary = self.summarize_table(df)
            summary_values = []
            for summary_name in table_summary:
                summary_rule = self.summary_rules[summary_name]

                summary_column = summary_rule['Column']
                summary_dtype = dtypes[summary_column]
                summary_value = settings.format_display(table_summary[summary_name], summary_dtype)
                summary_values.append(summary_value)

            window[self.key_lookup('SummaryTable')].update(values=[summary_values])

        # table_summary = self.summarize_table(df)
        # for summary_name in table_summary:
        #    summary_rule = self.summary_rules[summary_name]
        #    summary_column = summary_rule['Column']

        #    summary_dtype = dtypes[summary_column]
        #    summary_value = settings.format_display(table_summary[summary_name], summary_dtype)

        #    summary_key = self.key_lookup(summary_name)
        #    window[summary_key].update(value=summary_value)

        return display_df

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
                logger.exception('DataTable {NAME}: {MSG} - {ERR}'.format(NAME=self.name, MSG=msg, ERR=e))

                continue

            display_df[column_alias] = col_to_add

        return display_df.astype('object').fillna('')

    def format_display_column(self, df, column):
        """
        Format a specific column for displaying.
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
            logger.error('DataTable {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            raise KeyError(msg)

        dtype = display_col.dtype
        if is_float_dtype(dtype) and self.columns[column] == 'money':
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

    def filter_table(self):
        """
        Filter the data table by applying the filter rules specified in the configuration.
        """
        # Tab attributes
        filter_rules = self.filter_rules
        df = self.df.copy()

        if df.empty or not filter_rules:
            return df

        logger.debug('DataTable {NAME}: filtering display table on configured filter rules'.format(NAME=self.name))

        for column in filter_rules:
            filter_rule = filter_rules[column]
            logger.debug('DataTable {TBL}: filtering table on column {COL} based on rule "{RULE}"'
                         .format(TBL=self.name, COL=column, RULE=filter_rule))

            try:
                filter_cond = mod_dm.evaluate_rule(df, filter_rule, as_list=False)
            except Exception as e:
                logger.warning('DataTable {TBL}: filtering table on column {COL} failed - {ERR}'
                               .format(TBL=self.name, COL=column, ERR=e))
                continue

            try:
                failed = df[(df.duplicated(subset=[column], keep=False)) & (filter_cond)].index
            except Exception as e:
                logger.warning('DataTable {TBL}: filtering table on column {COL} failed - {ERR}'
                               .format(TBL=self.name, COL=column, ERR=e))
                continue

            if len(failed) > 0:
                logger.info('DataTable {TBL}: rows {ROWS} were removed after applying filter rule on column {COL}'
                            .format(TBL=self.name, ROWS=failed.tolist(), COL=column))

                df.drop(failed, axis=0, inplace=True)
                df.reset_index(drop=True, inplace=True)

        return df

    def summarize_column(self, column, df: pd.DataFrame = None, statistic: str = None):
        """
        Summarize a table column.
        """
        is_numeric_dtype = pd.api.types.is_numeric_dtype

        if statistic and statistic not in self._supported_stats:
            msg = 'unknown statistic {STAT} supplied for summarizing table column {COL}' \
                .format(STAT=statistic, COL=column)
            logger.warning('DataTable {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
            statistic = None

        df = df if df is not None else self.data()

        try:
            col_values = df[column]
        except KeyError:
            logger.error('DataTable {NAME}: summary column "{COL}" is missing from the table dataframe'
                         .format(NAME=self.name, COL=column))

            return 0

        if col_values.empty:
            return 0

        dtype = col_values.dtype
        if statistic == 'sum':
            col_summary = col_values.sum()
        elif statistic == 'count':
            col_summary = col_values.count()
        elif statistic == 'unique':
            col_summary = col_values.nunique()
        elif statistic == 'min':
            col_summary = col_values.min()
        elif statistic == 'max':
            col_summary = col_values.max()
        elif statistic == 'product' and is_numeric_dtype(dtype):
            col_summary = col_values.product()
        elif statistic == 'mean' and is_numeric_dtype(dtype):
            col_summary = col_values.mean()
        elif statistic == 'mode' and is_numeric_dtype(dtype):
            col_summary = col_values.mode()
        elif statistic == 'median' and is_numeric_dtype(dtype):
            col_summary = col_values.median()
        elif statistic == 'std' and is_numeric_dtype(dtype):
            col_summary = col_values.std()
        else:
            if is_numeric_dtype(dtype):  # default statistic for numeric data types like ints, floats, and bools
                col_summary = col_values.sum()
            else:  # default statistic for non-numeric data types like strings and datetime objects
                col_summary = col_values.nunique()

        return col_summary

    def summarize_table(self, df: pd.DataFrame = None):
        """
        Update Summary element with data summary
        """
        df = self.data() if df is None else df

        # Calculate totals defined by summary rules
        summary = {}
        rules = self.summary_rules
        for rule_name in rules:
            rule = rules[rule_name]

            column = rule['Column']

            # Subset df if subset rule provided
            condition = rule['Condition']
            if condition is not None:
                try:
                    subset_df = self.subset(rule['Condition'], df=df)
                except Exception as e:
                    logger.warning('DataTable {NAME}: unable to subset dataframe with subset rule {SUB} - {ERR}'
                                   .format(NAME=self.name, SUB=rule['Subset'], ERR=e))
                    break
            else:
                subset_df = df

            summary_stat = rule['Statistic']
            summary_total = self.summarize_column(column, df=subset_df, statistic=summary_stat)
            summary[rule_name] = summary_total

        return summary

    def annotate_rows(self, df):
        """
        Annotate the provided dataframe using configured annotation rules.
        """
        rules = self.annotation_rules
        if df.empty or rules is None:
            return {}

        logger.debug('DataTable {NAME}: annotating display table on configured annotation rules'.format(NAME=self.name))

        annotations = {}
        rows_annotated = []
        for annot_code in rules:
            logger.debug('DataTable {NAME}: annotating table based on configured annotation rule "{CODE}"'
                         .format(NAME=self.name, CODE=annot_code))
            rule = rules[annot_code]
            annot_condition = rule['Condition']
            try:
                results = mod_dm.evaluate_rule_set(df, {annot_code: annot_condition}, as_list=False)
            except Exception as e:
                logger.error('DataTable {NAME}: failed to annotate data table using annotation rule {CODE} - {ERR}'
                             .format(NAME=self.name, CODE=annot_code, ERR=e))
                continue

            for row_index, result in results.iteritems():
                if result:
                    if row_index in rows_annotated:
                        continue
                        # logger.warning('DataTable {NAME}: table row {ROW} has passed two or more annotation rules ... '
                        #               'defaulting to the first configured'.format(NAME=self.name, ROW=row_index))
                    else:
                        annotations[row_index] = annot_code
                        rows_annotated.append(row_index)

        return annotations

    def layout(self, size: tuple = (None, None), padding: tuple = None, tooltip: str = None, editable: bool = True,
               overwrite: bool = False, level: int = 0):
        """
        Generate a window layout for the table record element.
        """
        dtypes = self.columns
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
        text_col = mod_const.TEXT_COL  # standard text color
        select_text_col = mod_const.WHITE_TEXT_COL  # row text highlight color
        select_bg_col = mod_const.TBL_SELECT_COL
        disabled_text_col = mod_const.DISABLED_TEXT_COL  # disabled button text
        disabled_bg_col = mod_const.INACTIVE_COL  # disabled button background
        alt_col = self.row_color  # alternate row color
        bg_col = self.bg_col  # default primary table color is white
        header_col = mod_const.TBL_HEADER_COL  # color of the header background
        frame_col = mod_const.DEFAULT_COL  # background color of the table frames
        border_col = mod_const.BORDER_COL  # background color of the collapsible bars and the table frame

        pad = padding if padding and isinstance(padding, tuple) else (0, 0)
        pad_el = mod_const.ELEM_PAD
        pad_h = mod_const.HORZ_PAD
        pad_v = mod_const.VERT_PAD

        font = mod_const.MAIN_FONT
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

        isize = mod_const.IN1_SIZE

        header_col_size = 200
        min_col_size = 10

        bar_h = 26  # height of the title and totals bars in pixels
        cbar_h = 22  # height of the collapsible panel bars in pixels
        bttn_h = 30  # height of the filter apply button

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
                    logger.warning('DataTable {NAME}: cannot assign layout for table filter parameter {PARAM}'
                                   .format(NAME=self.name, PARAM=parameter.name))

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

        self._frame_heights[0] = frame_h

        row1 = [
            sg.Col([[sg.Canvas(size=(0, cbar_h), background_color=border_col),
                     sg.Image(data=mod_const.FILTER_ICON, pad=((0, pad_h), 0), background_color=border_col),
                     sg.Text('Filter', pad=((0, pad_h), 0), text_color=select_text_col,
                             background_color=border_col),
                     sg.Button('', image_data=mod_const.UNHIDE_ICON, key=self.key_lookup('FrameBttn0'),
                               button_color=(text_col, border_col), border_width=0,
                               tooltip='Collapse filter panel')]],
                   key=self.key_lookup('FilterBar'), element_justification='c', background_color=border_col,
                   expand_x=True, visible=(not filter_disabled), vertical_alignment='c')]
        row2 = [sg.pin(sg.Col(filters, key=self.key_lookup('Frame0'), background_color=frame_col,
                              visible=False, expand_x=True, vertical_alignment='c',
                              metadata={'visible': False, 'disabled': filter_disabled}))]

        # Table title
        title_bar = [sg.Canvas(size=(0, bar_h), background_color=header_col)]
        if modifiers['search'] and search_field is not None:
            search_layout = [[sg.Canvas(size=(header_col_size, 0), background_color=header_col)],
                             [sg.Canvas(size=(0, bar_h), background_color=header_col),
                              sg.Frame('', [
                                 [sg.Image(data=mod_const.SEARCH_ICON, background_color=bg_col, pad=((0, pad_h), 0)),
                                  sg.Input(default_text='', key=search_key, size=(isize - 2, 1),
                                           border_width=0, do_not_clear=True, background_color=bg_col,
                                           enable_events=True, tooltip='Search table')]],
                                       background_color=bg_col, relief='sunken')]]
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

        if modifiers['options'] and any([modifiers['fill'], modifiers['sort'], modifiers['export']]):
            options_layout = [[sg.Canvas(size=(header_col_size, 0), background_color=header_col)],
                              [sg.Canvas(size=(0, bar_h), background_color=header_col),
                               sg.Button('', key=options_key, image_data=mod_const.OPTIONS_ICON, border_width=0,
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
        hidden_columns = self.hidden_columns
        header = display_df.columns.tolist()
        data = display_df.values.tolist()
        events = True if level < 2 else False
        logger.debug('DataTable {NAME}: events are enabled: {EVENT}'.format(NAME=self.name, EVENT=events))
        vis_map = []
        for display_column in header:
            if display_column in hidden_columns:
                vis_map.append(False)
            else:
                vis_map.append(True)

        display_header = self._display_header()
        min_w = scroll_w + border_w + len(display_header) * min_col_size

        tbl_width = width - scroll_w - border_w if width >= min_w else min_w - scroll_w - border_w
        col_widths = self._calc_column_widths(display_header, width=tbl_width, size=font_size, pixels=False,
                                              widths=self.widths)
        row4.append(sg.Table(data, key=keyname, headings=header, visible_column_map=vis_map, pad=(0, 0), num_rows=nrow,
                             row_height=row_h, alternating_row_color=alt_col, background_color=bg_col,
                             text_color=text_col, selected_row_colors=(select_text_col, select_bg_col), font=tbl_font,
                             header_font=header_font, display_row_numbers=False, auto_size_columns=False,
                             col_widths=col_widths, enable_events=events, bind_return_key=False, tooltip=tooltip,
                             vertical_scroll_only=False, select_mode=select_mode,
                             metadata={'disabled': not events, 'visible': True}))

        # Table options
        options = [[sg.Col([[sg.Text('Options', text_color=select_text_col, background_color=border_col)]],
                           pad=(0, (0, int(pad_v / 2))), background_color=border_col, vertical_alignment='c',
                           element_justification='c', expand_x=True)]]

        if modifiers['fill']:
            fill_menu = ['&Fill', display_header]
            options.append([sg.ButtonMenu('', fill_menu, key=fill_key, image_data=mod_const.FILL_ICON,
                                          image_size=(200, 40), pad=(pad_h, (0, int(pad_v / 2))), border_width=1,
                                          button_color=(text_col, bg_col), tooltip='Fill NA values')])

        if modifiers['export']:
            options.append([sg.Button('', key=print_key, image_data=mod_const.EXPORT_ICON,
                                      image_size=(200, 40), pad=(pad_h, (0, int(pad_v / 2))), border_width=1,
                                      button_color=(text_col, bg_col), tooltip='Export to spreadsheet')])

        if modifiers['sort']:
            sort_menu = ['&Sort', display_header]
            options.append(
                [sg.ButtonMenu('', sort_menu, key=sort_key, image_data=mod_const.SORT_ICON,
                               image_size=(200, 40), pad=(pad_h, (0, int(pad_v / 2))), border_width=1,
                               button_color=(text_col, bg_col), tooltip='Sort table on columns')])

        row4.append(sg.Col(options, key=self.key_lookup('OptionsFrame'), background_color=frame_col,
                           justification='r', expand_y=True, visible=False, metadata={'visible': False}))

        # Control buttons and totals row
        actions_bar = [sg.Canvas(size=(0, bar_h), background_color=header_col)]
        actions_bar.extend(self.action_layout(disabled=is_disabled))

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
                                            font=font, background_color=bg_col, justification='r', relief='sunken',
                                            metadata={'name': self.name})]],
                                  pad=(pad_el, 0), justification='r', element_justification='r', vertical_alignment='b',
                                  background_color=header_col, expand_x=True, expand_y=False))

        row5 = [sg.Col([actions_bar], key=self.key_lookup('ActionsBar'), background_color=header_col,
                       vertical_alignment='c', expand_x=True, expand_y=True)]

        height_offset += bar_h  # height of the totals bar

        # Table summary panel
        summary_rules = self.summary_rules
        if len(summary_rules) > 0:  # display summary is set and table contains summary rules
            summary_headings = []
            summary_values = []
            tbl_summary = self.summarize_table()
            for summary_name in tbl_summary:
                summary_entry = summary_rules[summary_name]
                summary_header = summary_entry.get('Description', summary_name)
                summary_headings.append(summary_header)

                summary_column = summary_entry.get('Column')
                summary_dtype = dtypes[summary_column]
                summary_value = settings.format_display(tbl_summary[summary_name], summary_dtype)
                summary_values.append(summary_value)

            summary_key = self.key_lookup('SummaryTable')
            summary_layout = [[sg.Table([summary_values], key=summary_key, headings=summary_headings, num_rows=1,
                                        row_height=row_h, background_color=bg_col, text_color=text_col,
                                        selected_row_colors=(select_text_col, select_bg_col), font=tbl_font,
                                        header_font=header_font, display_row_numbers=False, auto_size_columns=True,
                                        hide_vertical_scroll=True)]]
        else:
            summary_layout = [[]]

        if len(summary_rules) > 0 and modifiers['summary']:
            summary_disabled = False
            height_offset += cbar_h  # height of the collapsible bar
            frame_h = row_h * 2  # height of the summary table
        else:
            summary_disabled = True
            frame_h = 0
            height_offset += 2  # invisible elements have a footprint

        self._frame_heights[1] = frame_h

        row6 = [sg.Col([[sg.Canvas(size=(0, cbar_h), background_color=border_col),
                         sg.Text('Summary', pad=((0, pad_h), 0), text_color='white', background_color=border_col),
                         sg.Button('', image_data=mod_const.UNHIDE_ICON, key=self.key_lookup('FrameBttn1'),
                                   button_color=(text_col, border_col), border_width=0,
                                   tooltip='Collapse summary panel')]],
                       key=self.key_lookup('SummaryBar'), element_justification='c', background_color=border_col,
                       expand_x=True, visible=(not summary_disabled), vertical_alignment='c')]

        frame1_key = self.key_lookup('Frame1')
        row7 = [sg.pin(sg.Col(summary_layout, key=frame1_key, background_color=frame_col, visible=False,
                              expand_x=True, expand_y=True, justification='c', element_justification='c',
                              metadata={'visible': False, 'disabled': summary_disabled}))]

        # Layout
        relief = 'ridge'
        layout = sg.Frame('', [row1, row2, row3, row4, row5, row6, row7], key=self.key_lookup('Table'),
                          pad=pad, element_justification='c', vertical_alignment='c', background_color=header_col,
                          relief=relief, border_width=2)

        height_offset = height_offset + scroll_w + row_h  # add scrollbar and table header to the offset
        self._height_offset = height_offset

        min_h = nrow * row_h + height_offset

        self._dimensions = (min_w, min_h)
        self._min_size = (min_w, min_h)

        return layout

    def action_layout(self, disabled: bool = True):
        """
        Layout for the table action elements.
        """
        custom_bttns = self.custom_actions

        # Element settings
        text_col = mod_const.TEXT_COL  # standard text color
        header_col = mod_const.TBL_HEADER_COL  # color of the header background
        highlight_col = mod_const.HIGHLIGHT_COL
        bwidth = 1

        # Layout
        bttn_layout = []
        for custom_bttn in custom_bttns:
            custom_entry = custom_bttns[custom_bttn]

            custom_layout = sg.Button('', key=custom_entry.get('Key', None), image_data=custom_entry.get('Icon', None),
                                      border_width=bwidth, button_color=(text_col, header_col), disabled=disabled,
                                      visible=True, tooltip=custom_entry.get('Description', custom_bttn),
                                      mouseover_colors=(text_col, highlight_col),
                                      metadata={'visible': True, 'disabled': disabled})
            bttn_layout.append(custom_layout)

        layout = [sg.Col([bttn_layout], justification='l', background_color=header_col, expand_x=True, expand_y=False)]

        return layout

    def resize(self, window, size: tuple = None):
        """
        Resize the table element.
        """
        table_key = self.key_lookup('Table')
        current_w, current_h = self.dimensions()
        min_w, min_h = self._min_size
        border_w = 1 * 4

        if size:
            width, height = size
            new_h = current_h if height is None or height < min_h else height
            new_w = current_w if width is None or width < min_w else width
        else:
            new_w, new_h = (current_w, current_h)

        logger.debug('DataTable {TBL}: resizing display to {W}, {H}'.format(TBL=self.name, W=new_w, H=new_h))
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
                param.resize(window, size=(param_w, None), pixels=True)

        # Fit the summary table to the frame
        if self.summary_rules:
            self._update_column_widths(window, frame_w - 2, summary=True)

        return window[table_key].get_size()

    def set_table_dimensions(self, window):
        """
        Reset column widths to calculated widths.
        """
        frame_key = self.key_lookup('OptionsFrame')
        width, nrows = self.get_table_dimensions(window)

        logger.debug('DataTable {NAME}: resetting display table dimensions'.format(NAME=self.name))

        # Close options panel, if open
        if window[frame_key].metadata['visible'] is True:
            window[frame_key].metadata['visible'] = False
            window[frame_key].update(visible=False)

        # Update column widths
        self._update_column_widths(window, width)

        # Re-annotate the table rows. Row colors often get reset when the number of display rows is changed.
        window[self.key_lookup('Element')].update(row_colors=self._colors)
        #self.update_display(window)

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
        for frame_index in self._frame_heights:
            frame = window[self.key_lookup('Frame{}'.format(frame_index))]
            if not frame.metadata['disabled']:
                if frame.metadata['visible']:
                    frame_h = self._frame_heights[frame_index] + 1
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

    def enable(self, window, custom: bool = True):
        """
        Enable data table element actions.
        """
        # params = self.parameters
        custom_bttns = self.custom_actions

        logger.debug('DataTable {NAME}: enabling actions'.format(NAME=self.name))

        # Enable table modification buttons
        if custom:
            for custom_bttn in custom_bttns:
                custom_entry = custom_bttns[custom_bttn]
                try:
                    bttn_key = custom_entry['Key']
                except KeyError:
                    continue

                window[bttn_key].update(disabled=False)
                window[bttn_key].metadata['disabled'] = False

    def disable(self, window):
        """
        Disable data table element actions.
        """
        # params = self.parameters
        custom_bttns = self.custom_actions

        logger.debug('DataTable {NAME}: disabling table actions'.format(NAME=self.name))

        # Disable table modification buttons
        for custom_bttn in custom_bttns:
            custom_entry = custom_bttns[custom_bttn]
            try:
                bttn_key = custom_entry['Key']
            except KeyError:
                continue

            window[bttn_key].update(disabled=True)
            window[bttn_key].metadata['disabled'] = True

    def collapse_expand(self, window, index: int = 0):
        """
        Collapse record frames.
        """
        bttn_key = self.key_lookup('FrameBttn{}'.format(index))
        bttn = window[bttn_key]

        frame_key = self.key_lookup('Frame{}'.format(index))
        frame = window[frame_key]
        frame_meta = frame.metadata

        if frame_meta['visible']:  # already visible, so want to collapse the frame
            logger.debug('DataTable {NAME}: collapsing table frame {FRAME}'.format(NAME=self.name, FRAME=index))
            bttn.update(image_data=mod_const.UNHIDE_ICON)
            frame.update(visible=False)

            frame.metadata['visible'] = False
        else:  # not visible yet, so want to expand the frame
            if not frame_meta['disabled']:
                logger.debug('DataTable {NAME}: expanding table frame {FRAME}'.format(NAME=self.name, FRAME=index))
                bttn.update(image_data=mod_const.HIDE_ICON)
                frame.update(visible=True)

                frame.metadata['visible'] = True

        self.resize(window)

    def append(self, add_df):
        """
        Add new rows of data to the data table.
        """
        df = self.df.copy()

        if add_df.empty:  # no data to add
            return df

        # Convert add_df to a dataframe first if it is a series
        if isinstance(add_df, pd.Series):
            add_df = add_df.to_frame().T

        # Add the is deleted column if it does not already exist in the dataframe to be appended
        if self.deleted_column not in add_df.columns:
            add_df[self.deleted_column] = False

        # Make sure the data types of the columns are consistent
        add_df = self._set_datatypes(add_df)
        add_df = self.set_conditional_values(add_df)

        # Add new data to the table
        logger.debug('DataTable {NAME}: appending {NROW} rows to the table'
                     .format(NAME=self.name, NROW=add_df.shape[0]))
        df = df.append(add_df, ignore_index=True)

        return df

    def fill(self, indices, column, fill_method: str = 'ffill'):
        """
        Forward fill table NA values.
        """
        if not isinstance(indices, list) and not isinstance(indices, tuple):
            msg = 'table indices provided must be either a list or tuple'
            logger.warning('DataTable {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            return None

        logger.info('DataTable {NAME}: filling table rows {ROWS} using fill method "{METHOD}"'
                    .format(NAME=self.name, ROWS=len(indices), METHOD=fill_method))

        if len(indices) > 1:
            column_index = self.df.columns.get_loc(column)
            try:
                self.df.iloc[indices, column_index] = self.df.iloc[indices, column_index].fillna(method=fill_method)
            except IndexError:
                logger.warning('DataTable {NAME}: unable to fill table on selected rows - unknown rows {ROWS} selected'
                               .format(NAME=self.name, ROWS=indices))
            except ValueError:
                logger.warning('DataTable {NAME}: unable to fill table on selected rows - invalid fill method provided'
                               .format(NAME=self.name))
            else:  # indicate that the specific rows and the table have been edited
                self.df.iloc[indices, self.df.columns.get_loc(self.edited_column)] = True
                self.edited = True
        else:
            logger.warning('DataTable {NAME}: unable to fill table - not enough rows selected for filling'
                           .format(NAME=self.name))

        return None

    def sort(self, sort_on=None, ascending: bool = True):
        """
        Sort the table on the provided column name.
        """
        col_header = self.df.columns.tolist()
        df = self.df.copy()
        if df.empty:
            return df

        # Prepare the columns to sort the table on
        sort_keys = []
        if isinstance(sort_on, str):
            sort_keys.append(sort_on)
        elif isinstance(sort_on, list):
            for sort_col in sort_on:
                if sort_col in col_header:
                    sort_keys.append(sort_col)
                else:
                    logger.warning('DataTable {NAME}: sort column {COL} not found in table header'
                                   .format(NAME=self.name, COL=sort_col))

        if len(sort_keys) > 0:
            logger.debug('DataTable {NAME}: sorting table on {KEYS}'.format(NAME=self.name, KEYS=sort_keys))
            try:
                df.sort_values(by=sort_keys, inplace=True, ascending=ascending)
            except KeyError:  # sort key is not in table header
                logger.warning('DataTable {NAME}: one or more sort key columns ({COLS}) not find in the table header. '
                               'Values will not be sorted.'.format(NAME=self.name, COLS=', '.join(sort_keys)))
            else:
                df.reset_index(drop=True, inplace=True)

            self.df = df

        return df

    def subset(self, subset_rule, df: pd.DataFrame = None):
        """
        Subset the table based on a set of rules.
        """
        operators = {'>', '>=', '<', '<=', '==', '!=', '=', 'IN', 'In', 'in'}
        chain_map = {'or': '|', 'OR': '|', 'Or': '|', 'and': '&', 'AND': '&', 'And': '&'}

        df = self.data() if df is None else df
        if df.empty:
            return df

        header = df.columns.values.tolist()

        logger.debug('DataTable {NAME}: sub-setting table on rule {RULE}'.format(NAME=self.name, RULE=subset_rule))
        rule_list = [i.strip() for i in
                     re.split('({})'.format('|'.join([' {} '.format(i) for i in chain_map])), subset_rule)]

        conditionals = []
        for component in rule_list:
            if component in chain_map:
                conditionals.append(chain_map[component])
            else:
                conditional = mod_dm.parse_operation_string(component)
                cond_items = []
                for item in conditional:
                    if item in operators:  # item is operator
                        if item == '=':
                            cond_items.append('==')
                        else:
                            cond_items.append(item)
                    elif item in header:  # item is in header
                        cond_items.append('df["{}"]'.format(item))
                    elif item.lower() in header:  # item is header converted by ODBC implementation
                        cond_items.append('df["{}"]'.format(item.lower()))
                    else:  # item is string or int
                        try:
                            float(item)
                        except (ValueError, TypeError):  # format as a string
                            cond_items.append('"{}"'.format(item))
                        else:
                            cond_items.append(item)

                conditionals.append('({})'.format(' '.join(cond_items)))

        cond_str = ' '.join(conditionals)

        try:
            subset_df = eval('df[{}]'.format(cond_str))
        except SyntaxError:
            raise SyntaxError('invalid syntax for subset rule {NAME}'.format(NAME=subset_rule))
        except NameError:
            raise NameError('unknown column specified in subset rule {NAME}'.format(NAME=subset_rule))

        return subset_df

    def export_table(self, display=True):
        """
        Export table to spreadsheet.
        """
        df = self.data(display_rows=display)
        logger.info('DataTable {NAME}: preparing the table for exporting'.format(NAME=self.name))

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
        df = df if df is not None else self.data()
        if df.empty:
            return 0

        total = 0
        if tally_rule is not None:
            try:
                result = mod_dm.evaluate_rule(df, tally_rule, as_list=False)
            except Exception as e:
                msg = 'DataTable {NAME}: unable to calculate table total - {ERR}' \
                    .format(NAME=self.name, ERR=e)
                logger.warning(msg)
            else:
                dtype = result.dtype
                if is_float_dtype(dtype) or is_integer_dtype(dtype) or is_bool_dtype(dtype):
                    total = result.sum()
                elif is_string_dtype(dtype) or is_datetime_dtype(dtype):
                    total = result.nunique()
                else:  # possibly empty dataframe
                    total = 0
                logger.debug('DataTable {NAME}: table totals calculated as {TOTAL}'.format(NAME=self.name, TOTAL=total))
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
            return self.summarize_table()

    def check_requirements(self):
        """
        Verify that the record element passes requirements.
        """
        comp_df = self.data()

        required_columns = self.required_columns
        for required_column in required_columns:
            has_na = comp_df[required_column].isnull().any()
            logger.debug('DataTable {NAME}: required column {COL} has NA values: {HAS}'
                         .format(NAME=self.name, COL=required_column, HAS=has_na))
            if has_na:
                display_map = self.display_columns
                try:
                    display_column = display_map[required_column]
                except KeyError:
                    display_column = required_column

                msg = 'missing values for required column {COL}'.format(COL=display_column)
                logger.warning('DataTable {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                return False

        return True

    def has_value(self):
        """
        Return True if no NAs in the table else return False.
        """
        if self.df.isnull().values.any() is True:
            return False
        else:
            return True

    def edit_row(self, index):
        """
        Edit existing record values.
        """
        edit_columns = self.edit_columns
        if not edit_columns:
            logger.warning('DataTable {TBL}: no columns have been configured to be editable'.format(TBL=self.name))

        df = self.df.copy()

        try:
            row = df.loc[index]
        except IndexError:
            msg = 'no record found at table index "{IND}" to edit'.format(IND=index + 1)
            mod_win2.popup_error(msg)
            logger.error('DataTable {NAME}: failed to edit record at row {IND} - {MSG}'
                         .format(NAME=self.name, MSG=msg, IND=index + 1))

            return df

        # Display the modify row window
        display_map = self.display_columns
        mod_row = mod_win2.edit_row_window(row, edit_columns=edit_columns, header_map=display_map)

        return mod_row

    def update_row(self, row, values):
        """
        Replace the values of a table row.

        Arguments:
            row (int): adjusted row index.

            values (Series): values to replace.
        """
        self._update_row_values(row, values)

    def update_column(self, column, values, indices: list = None):
        """
        Replace the values of a table column.

        Arguments:
            column (str): name of the column to modify.

            values (list): list, series, or scalar of new column values.

            indices (list): optional list of row indices to modify [Default: update all rows].
        """
        df = self.df

        if isinstance(indices, type(None)):  # update all rows
            indices = df.index.tolist()
        elif isinstance(indices, int):
            indices = [indices]

        try:
            col_values = df.loc[indices, column]
        except IndexError:
            msg = 'DataTable {NAME}: failed to update column "{COL}" - one or more row indices from {INDS} are ' \
                  'missing from the table'.format(NAME=self.name, COL=column, INDS=indices)
            raise IndexError(msg)

        if not isinstance(values, pd.Series):
            values = pd.Series(values, index=indices)

        values = self._set_column_dtype(values, name=column)

        # Set "Is Edited" to True where existing column values do not match the update values
        try:
            edited = ~((col_values.eq(values)) | (col_values.isna() & values.isna()))
        except ValueError:
            msg = 'DataTable {NAME}: failed to update column "{COL}" - the length of the update values must be ' \
                  'equal to the length of the indices to update'.format(NAME=self.name, COL=column)
            raise ValueError(msg)
        else:
            edited_indices = edited[edited].index
            if len(edited_indices) > 0:
                df.loc[edited_indices, self.edited_column] = True
                self.edited = True

        # Replace existing column values with new values
        df.loc[indices, column] = values

    def set_defaults(self, row):
        """
        Set row defaults.
        """
        dtype_map = {'date': np.datetime64, 'datetime': np.datetime64, 'timestamp': np.datetime64,
                     'time': np.datetime64,
                     'float': float, 'decimal': float, 'dec': float, 'double': float, 'numeric': float, 'money': float,
                     'int': int, 'integer': int, 'bit': int,
                     'bool': bool, 'boolean': bool,
                     'char': str, 'varchar': str, 'binary': str, 'varbinary': str,
                     'tinytext': str, 'text': str, 'string': str}

        logger.debug('DataTable {NAME}: setting column default values'.format(NAME=self.name))

        columns = self.defaults
        for column in columns:
            try:
                dtype = self.columns[column]
            except KeyError:
                logger.warning('DataTable {NAME}: default column "{COL}" not found in table header'
                               .format(NAME=self.name, COL=column))
                continue

            if not pd.isna(row[column]):
                continue

            logger.debug('DataTable {NAME}: setting default values for column "{COL}"'
                         .format(NAME=self.name, COL=column))

            entry = columns[column]
            if 'DefaultConditions' in entry:
                default_rules = entry['DefaultConditions']

                for default_value in default_rules:
                    default_rule = default_rules[default_value]
                    results = mod_dm.evaluate_rule_set(row, {default_value: default_rule}, as_list=True)
                    for result in results:
                        if result is True:
                            row[column] = default_value
            elif 'DefaultRule' in entry:
                default_values = mod_dm.evaluate_rule(row, entry['DefaultRule'], as_list=True)
                logger.debug('DataTable {NAME}: assigning values "{VAL}" to column "{COL}"'
                             .format(NAME=self.name, VAL=default_values, COL=column))
                for default_value in default_values:
                    row[column] = default_value
            elif 'DefaultValue' in entry:
                default_value = entry['DefaultValue']
                logger.debug('DataTable {NAME}: assigning value "{VAL}" to column "{COL}"'
                             .format(NAME=self.name, VAL=default_value, COL=column))
                if pd.isna(default_value):
                    column_value = None
                else:
                    try:
                        column_value = dtype_map[dtype](default_value)
                    except KeyError:
                        column_value = default_value

                row[column] = column_value
            else:
                logger.warning('DataTable {NAME}: neither the "DefaultValue" nor "DefaultRule" parameter was '
                               'provided to column defaults entry "{COL}"'.format(NAME=self.name, COL=column))

        return row

    def set_conditional_values(self, df=None):
        """
        Update conditional columns using current
        """
        dtype_map = {'date': np.datetime64, 'datetime': np.datetime64, 'timestamp': np.datetime64,
                     'time': np.datetime64,
                     'float': float, 'decimal': float, 'dec': float, 'double': float, 'numeric': float, 'money': float,
                     'int': int, 'integer': int, 'bit': int,
                     'bool': bool, 'boolean': bool,
                     'char': str, 'varchar': str, 'binary': str, 'varbinary': str,
                     'tinytext': str, 'text': str, 'string': str}

        logger.debug('DataTable {NAME}: setting conditional column values'.format(NAME=self.name))

        df = self.df.copy() if df is None else df
        if isinstance(df, pd.Series):  # need to convert series to dataframe first
            df = df.to_frame().T

        header = df.columns.tolist()
        columns = self.conditional_columns
        if not columns:
            return df

        for column in columns:
            try:
                dtype = self.columns[column]
            except KeyError:
                logger.warning('DataTable {NAME}: conditional column "{COL}" not found in available table columns'
                               .format(NAME=self.name, COL=column))
                continue

            if column not in header:
                df.loc[:, column] = None

            entry = columns[column]
            if 'DefaultConditions' in entry:
                default_rules = entry['DefaultConditions']

                for default_value in default_rules:
                    default_rule = default_rules[default_value]
                    try:
                        results = mod_dm.evaluate_rule_set(df, {default_value: default_rule}, as_list=False)
                    except Exception as e:
                        msg = 'failed to evaluate condition for rule {RULE} - {ERR}'.format(RULE=default_rule, ERR=e)
                        logger.exception(msg)

                        continue

                    for index, result in results.iteritems():
                        if result:
                            df.at[index, column] = dtype_map[dtype](default_value)

            elif 'DefaultRule' in entry:
                default_rule = entry['DefaultRule']
                try:
                    default_values = mod_dm.evaluate_rule(df, default_rule, as_list=False)
                except Exception as e:
                    msg = 'failed to evaluate condition for rule {RULE} - {ERR}'.format(RULE=default_rule, ERR=e)
                    logger.exception(msg)
                else:
                    default_values = self._set_column_dtype(default_values, name=column)
                    df.loc[:, column] = default_values

            else:
                logger.warning('DataTable {NAME}: neither the "DefaultCondition" nor "DefaultRule" parameter was '
                               'provided to column defaults entry "{COL}"'.format(NAME=self.name, COL=column))

        # df = self._set_datatypes(df)

        return df

    def initialize_defaults(self, df=None):
        """
        Update empty table cells with editable column default values.
        """
        dtype_map = {'date': np.datetime64, 'datetime': np.datetime64, 'timestamp': np.datetime64,
                     'time': np.datetime64,
                     'float': float, 'decimal': float, 'dec': float, 'double': float, 'numeric': float, 'money': float,
                     'int': int, 'integer': int, 'bit': int,
                     'bool': bool, 'boolean': bool,
                     'char': str, 'varchar': str, 'binary': str, 'varbinary': str,
                     'tinytext': str, 'text': str, 'string': str}

        logger.debug('DataTable {NAME}: setting column default values'.format(NAME=self.name))

        df = self.df.copy() if df is None else df
        header = df.columns.tolist()
        columns = self.defaults
        for column in columns:
            try:
                dtype = self.columns[column]
            except KeyError:
                logger.warning('DataTable {NAME}: default column "{COL}" not found in available table columns'
                               .format(NAME=self.name, COL=column))
                continue

            if column not in header:
                df[column] = None

            logger.debug('DataTable {NAME}: setting default values for column {COL}'.format(NAME=self.name, COL=column))

            entry = columns[column]
            if 'DefaultConditions' in entry:
                default_rules = entry['DefaultConditions']

                for default_value in default_rules:
                    default_rule = default_rules[default_value]
                    results = mod_dm.evaluate_rule_set(df, {default_value: default_rule}, as_list=False)
                    for index, result in results.iteritems():
                        if result is True and pd.isna(df.at[index, column]) is True:
                            df.at[index, column] = dtype_map[dtype](default_value)
            elif 'DefaultRule' in entry:
                default_values = mod_dm.evaluate_rule(df, entry['DefaultRule'], as_list=True)
                logger.debug('DataTable {NAME}: assigning values "{VAL}" to empty cells in column "{COL}"'
                             .format(NAME=self.name, VAL=default_values, COL=column))
                for index, default_value in enumerate(default_values):
                    if pd.isna(df.at[index, column]):
                        df.at[index, column] = dtype_map[dtype](default_value)
            elif 'DefaultValue' in entry:
                default_value = entry['DefaultValue']
                logger.debug('DataTable {NAME}: assigning value "{VAL}" to empty cells in column "{COL}"'
                             .format(NAME=self.name, VAL=default_value, COL=column))
                if pd.isna(default_value):
                    column_value = None
                else:
                    try:
                        column_value = dtype_map[dtype](default_value)
                    except KeyError:
                        column_value = default_value

                df[column].fillna(column_value, inplace=True)
            else:
                logger.warning('DataTable {NAME}: neither the "DefaultValue" nor "DefaultRule" parameter was '
                               'provided to column defaults entry "{COL}"'.format(NAME=self.name, COL=column))

        df = self._set_datatypes(df)

        return df


class RecordTable(TableElement):
    """
    Record tables are a subclass of the data table, but specifically for storing record data. Record tables provide
    additional functionality to the data table, including opening of a record instead of row value editing,
    deleting records, and importing existing records into the table.

    Attributes:

        name (str): table element configuration name.

        elements (list): list of table element keys.

        title (str): display title.

        etype (str): program element type.

        modifiers (dict): flags that alter the element's behavior.

        record_type (str): table is composed of records of this type.

        import_rules (dict): rules used to import records from the database.

        id_column (str): name of the column containing the record ID values.

        date_column (str): name of the column containing the record date values.

        df (DataFrame): pandas dataframe containing table data.
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
        self.elements.extend(['-{NAME}_{ID}_{ELEM}-'.format(NAME=name, ID=self.id, ELEM=i) for i in
                              ('Delete', 'Import')])
        self._event_elements.extend(['Delete', 'Import'])

        elem_key = self.key_lookup('Element')
        delete_hkey = '{}+DELETE+'.format(elem_key)
        import_hkey = '{}+IMPORT+'.format(elem_key)
        action_keys = [self.key_lookup(i) for i in ('Delete', 'Import')] + [delete_hkey, import_hkey]
        self._action_events.extend(action_keys)
        self.bindings.extend(action_keys)

        self.etype = 'record_table'
        self.eclass = 'references'

        try:
            modifiers = entry['Modifiers']
        except KeyError:
            self.modifiers = {'open': False, 'edit': False, 'export': False, 'search': False, 'summary': False,
                              'filter': False, 'import': False, 'delete': False, 'fill': False, 'options': False,
                              'sort': False}
        else:
            self.modifiers = {'open': modifiers.get('open', 0), 'edit': modifiers.get('edit', 0),
                              'export': modifiers.get('export', 0), 'import': modifiers.get('import', 0),
                              'search': modifiers.get('search', 0), 'summary': modifiers.get('summary', 0),
                              'filter': modifiers.get('filter', 0), 'delete': modifiers.get('delete', 0),
                              'fill': modifiers.get('fill', 0), 'options': modifiers.get('options', 0),
                              'sort': modifiers.get('sort', 0)}
            for modifier in self.modifiers:
                try:
                    flag = bool(int(self.modifiers[modifier]))
                except ValueError:
                    logger.warning('DataTable {TBL}: modifier {MOD} must be either 0 (False) or 1 (True)'
                                   .format(TBL=self.name, MOD=modifier))
                    flag = False

                self.modifiers[modifier] = flag

        print('table {} has modifiers: {}'.format(self.name, self.modifiers))

        try:
            self.record_type = entry['RecordType']
        except KeyError:
            self.record_type = None

        try:
            import_rules = entry['ImportRules']
        except KeyError:
            if self.record_type:
                record_entry = settings.records.fetch_rule(self.record_type)
                try:
                    self.import_rules = record_entry.import_rules
                except AttributeError:
                    self.import_rules = None
            else:
                self.import_rules = None
        else:
            for import_table in import_rules:
                import_rule = import_rules[import_table]

                if 'Columns' not in import_rule:
                    mod_win2.popup_error('DataTable {NAME}: configuration missing required "ImportRules" {TBL} '
                                         'parameter "Columns"'.format(NAME=self.name, TBL=import_table))
                    sys.exit(1)
                if 'Filters' not in import_rule:
                    import_rule['Filters'] = None

            self.import_rules = import_rules

        try:
            self.id_column = entry['IDColumn']
        except KeyError:
            self.id_column = 'RecordID'

        try:
            self.date_column = entry['DateColumn']
        except KeyError:
            self.date_column = 'RecordDate'

        # Dynamic attributes
        self.import_df = self._set_datatypes(pd.DataFrame(columns=list(self.columns)))

    def _translate_row(self, row, level: int = 1, new_record: bool = False, references: dict = None):
        """
        Translate row data into a record object.
        """
        record_entry = settings.records.fetch_rule(self.record_type)
        record_class = mod_records.DatabaseRecord

        record = record_class(self.record_type, record_entry.record_layout, level=level)
        record.initialize(row, new=new_record, references=references)

        return record

    def bind_keys(self, window):
        """
        Add hotkey bindings to the data element.
        """
        level = self.level

        elem_key = self.key_lookup('Element')
        window[elem_key].bind('<Control-f>', '+FILTER+')
        if level < 2:
            window[elem_key].bind('<Return>', '+RETURN+')
            window[elem_key].bind('<Double-Button-1>', '+LCLICK+')
            window[elem_key].bind('<Key-BackSpace>', '+DELETE+')
            window[elem_key].bind('<Control-d>', '+DELETE+')
            window[elem_key].bind('<Control-i>', '+IMPORT+')

    def reset(self, window, reset_filters: bool = True, collapse: bool = True):
        """
        Reset record table to default.

        Arguments:
            window (Window): GUI window.

            reset_filters (bool): also reset filter parameter values [Default: True].

            collapse (bool): collapse supplementary table frames [Default: True].
        """
        # Attempt to remove any unsaved record IDs first
        record_type = self.record_type
        record_entry = settings.records.fetch_rule(record_type)

        ids_to_remove = self.df[self.id_column].values.tolist()
        record_entry.remove_unsaved_ids(record_ids=ids_to_remove)

        # Reset dynamic attributes
        columns = list(self.columns)
        self.df = self._set_datatypes(pd.DataFrame(columns=columns))
        self.import_df = self._set_datatypes(pd.DataFrame(columns=columns))
        self.index_map = {}
        self.edited = False

        # Reset table filter parameters
        if reset_filters:
            for param in self.parameters:
                param.reset(window)

        # Collapse visible frames
        if collapse:
            frames = [self.key_lookup('Frame{}'.format(i)) for i in range(2)]
            for i, frame_key in enumerate(frames):
                if window[frame_key].metadata['disabled']:
                    continue

                if window[frame_key].metadata['visible']:  # frame was expanded at some point
                    self.collapse_expand(window, index=i)

        # Reset table dimensions
        self.set_table_dimensions(window)

        # Update the table display
        self.update_display(window)

    def run_action_event(self, window, event, values):
        """
        Run a table action event.
        """
        elem_key = self.key_lookup('Element')
        open_key = '{}+LCLICK+'.format(elem_key)
        return_key = '{}+RETURN+'.format(elem_key)
        delete_key = self.key_lookup('Delete')
        delete_hkey = '{}+DELETE+'.format(elem_key)
        import_key = self.key_lookup('Import')
        import_hkey = '{}+IMPORT+'.format(elem_key)

        update_event = False

        can_open = self.modifiers['open']
        can_edit = self.modifiers['edit']
        can_import = not window[import_key].metadata['disabled'] and window[import_key].metadata['visible']
        can_delete = not window[delete_key].metadata['disabled'] and window[delete_key].metadata['visible']

        # Row click event
        if event in (open_key, return_key) and can_open:
            # Close options panel, if open
            self.set_table_dimensions(window)

            # Find row selected by user from the display table of non-deleted rows
            try:
                select_row_index = values[elem_key][0]
            except IndexError:  # user double-clicked too quickly
                msg = 'table row could not be selected'
                logger.debug('DataTable {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
            else:
                self._selected_rows = [select_row_index]

                # Get the real index of the selected row
                index = self.get_index(select_row_index)

                logger.debug('DataTable {NAME}: opening record at real index {IND} for editing'
                             .format(NAME=self.name, IND=index))
                record = self.load_record(index)

                # Update record table values
                if record and can_edit:
                    try:
                        record_values = record.export_values()
                    except Exception as e:
                        msg = 'unable to update row {IND} values'.format(IND=index)
                        logger.exception('DataTable {NAME}: {MSG} - {ERR}'.format(NAME=self.name, MSG=msg, ERR=e))
                    else:
                        update_event = self._update_row_values(index, record_values)

        # Delete rows button clicked
        if event in (delete_key, delete_hkey) and can_delete:
            # Find rows selected by user for deletion
            select_row_indices = values[elem_key]

            # Get the real indices of the selected rows
            indices = self.get_index(select_row_indices)
            if len(indices) > 0:
                self.delete_rows(indices)
                update_event = True

        # Import rows button clicked
        if event in (import_key, import_hkey) and can_import:
            # Close options panel, if open
            self.set_table_dimensions(window)

            try:
                self.import_rows()
            except Exception as e:
                msg = 'failed to run table import event'
                logger.exception('DataTable {NAME}: {MSG} - {ERR}'.format(NAME=self.name, MSG=msg, ERR=e))
            else:
                update_event = True

        # All action events require a table update
        if update_event:
            self.update_display(window)

        return update_event

    def action_layout(self, disabled: bool = True):
        """
        Layout for the table action elements.
        """
        import_key = self.key_lookup('Import')
        delete_key = self.key_lookup('Delete')
        custom_bttns = self.custom_actions

        # Element settings
        text_col = mod_const.TEXT_COL  # standard text color
        header_col = mod_const.TBL_HEADER_COL  # color of the header background
        highlight_col = mod_const.HIGHLIGHT_COL
        bwidth = 1

        # Layout
        bttn_layout = [sg.Button('', key=import_key, image_data=mod_const.TBL_IMPORT_ICON, border_width=bwidth,
                                 button_color=(text_col, header_col), mouseover_colors=(text_col, highlight_col),
                                 disabled=disabled, visible=self.modifiers['import'],
                                 tooltip='Import database records (CTRL+I)',
                                 metadata={'visible': self.modifiers['import'], 'disabled': disabled}),
                       sg.Button('', key=delete_key, image_data=mod_const.TBL_DEL_ICON, border_width=bwidth,
                                 button_color=(text_col, header_col), mouseover_colors=(text_col, highlight_col),
                                 disabled=disabled, visible=self.modifiers['delete'],
                                 tooltip='Remove selected rows (CTRL+D)',
                                 metadata={'visible': self.modifiers['delete'], 'disabled': disabled})]

        for custom_bttn in custom_bttns:
            custom_entry = custom_bttns[custom_bttn]

            custom_layout = sg.Button('', key=custom_entry.get('Key', None), image_data=custom_entry.get('Icon', None),
                                      border_width=bwidth, button_color=(text_col, header_col),
                                      mouseover_colors=(text_col, highlight_col), disabled=disabled,
                                      visible=True, tooltip=custom_entry.get('Description', custom_bttn),
                                      metadata={'visible': True, 'disabled': disabled})
            bttn_layout.append(custom_layout)

        layout = [sg.Col([bttn_layout], justification='l', background_color=header_col, expand_x=True, expand_y=False)]

        return layout

    def row_ids(self, imports: bool = False, indices: list = None, display: bool = False):
        """
        Return a list of all current row IDs in the dataframe.

        Arguments:
            imports (bool): get row IDs from the imports dataframe instead of the records dataframe [Default: False].

            indices (list): optional list of table indices to get record IDs for [Default: get all record IDs in the
                table].

            display (bool): get record IDs from the set of currently displayed records [Default: False].
        """
        id_field = self.id_column
        if imports:
            df = self.import_df
        elif display:  # include deleted rows
            df = self.data(display_rows=True)
        else:
            df = self.data()  # don't include deleted rows

        if indices is None:
            indices = df.index
        else:
            if isinstance(indices, int):
                indices = [indices]

        try:
            row_ids = df.loc[indices, id_field].tolist()
        except KeyError:  # database probably PostGreSQL
            logger.exception('DataTable {NAME}: unable to return a list of row IDs from the table - ID column "{COL}" '
                             'not found in the data table'.format(NAME=self.name, COL=id_field))
            row_ids = []

        return row_ids

    def enable(self, window, custom: bool = True):
        """
        Enable data table element actions.
        """
        # params = self.parameters
        delete_key = self.key_lookup('Delete')
        import_key = self.key_lookup('Import')
        custom_bttns = self.custom_actions

        logger.debug('DataTable {NAME}: enabling table action elements'.format(NAME=self.name))

        # Enable filter parameters
        # if len(params) > 0 and self.modifiers['filter'] is True:
        #    # Enable the apply filters button
        #    filter_key = self.key_lookup('Filter')
        #    window[filter_key].update(disabled=False)

        # Enable table modification buttons
        window[delete_key].update(disabled=False)
        window[delete_key].metadata['disabled'] = False

        window[import_key].update(disabled=False)
        window[import_key].metadata['disabled'] = False

        if custom:
            for custom_bttn in custom_bttns:
                custom_entry = custom_bttns[custom_bttn]
                try:
                    bttn_key = custom_entry['Key']
                except KeyError:
                    continue

                window[bttn_key].update(disabled=False)
                window[bttn_key].metadata['disabled'] = False

    def disable(self, window):
        """
        Disable data table element actions.
        """
        # params = self.parameters
        delete_key = self.key_lookup('Delete')
        import_key = self.key_lookup('Import')
        custom_bttns = self.custom_actions

        logger.debug('DataTable {NAME}: disabling table action elements'.format(NAME=self.name))

        # Disable filter parameters
        # if len(params) > 0 and self.modifiers['filter'] is True:
        #    # Disable the apply filters button
        #    filter_key = self.key_lookup('Filter')
        #    window[filter_key].update(disabled=True)

        # Disable table modification buttons
        window[delete_key].update(disabled=True)
        window[delete_key].metadata['disabled'] = True

        window[import_key].update(disabled=True)
        window[import_key].metadata['disabled'] = True

        for custom_bttn in custom_bttns:
            custom_entry = custom_bttns[custom_bttn]
            try:
                bttn_key = custom_entry['Key']
            except KeyError:
                continue

            window[bttn_key].update(disabled=True)
            window[bttn_key].metadata['disabled'] = True

    def append(self, add_df, imports: bool = False):
        """
        Add new rows of data to the records or import dataframe.

        Arguments:
            add_df (DataFrame): rows to add to the table.

            imports (bool): add rows to the imports dataframe instead of the records dataframe [Default: False].
        """
        if imports:  # add new data to the import dataframe instead of the data table
            df = self.import_df.copy()
            table_name = 'imports table'
        else:  # add new data to the data table
            table_name = 'data table'
            df = self.df.copy()

        if add_df.empty:  # no data to add
            return df

        # Convert add_df to a dataframe first if it is a series
        if isinstance(add_df, pd.Series):
            add_df = add_df.to_frame().T

        # Add the is deleted column if it does not already exist in the dataframe to be appended
        if self.deleted_column not in add_df.columns:
            add_df[self.deleted_column] = False

        # Make sure the data types of the columns are consistent
        add_df = self._set_datatypes(add_df)
        add_df = self.set_conditional_values(add_df)

        # Add new data to the table
        logger.debug('DataTable {NAME}: appending {NROW} rows to the {TBL}'
                     .format(NAME=self.name, NROW=add_df.shape[0], TBL=table_name))
        df = df.append(add_df, ignore_index=True)

        return df

    def load_record(self, index, level: int = None, references: dict = None, savable: bool = True):
        """
        Open selected record in new record window.

        Arguments:
            index (int): real index of the desired record to load.

            level (int): level at which the record should be loaded [Default: current level + 1]

            references (dict): load record using custom reference dictionary.

            savable (bool): database entry of the record can be updated through the record window [Default: True].
        """
        df = self.df.copy()
        modifiers = self.modifiers

        level = level if level is not None else self.level + 1
        view_only = False if modifiers['edit'] is True else True

        try:
            row = df.loc[index]
        except IndexError:
            msg = 'no record found at table index {IND} to edit'.format(IND=index + 1)
            mod_win2.popup_error(msg)
            logger.exception('DataTable {NAME}: failed to open record at row {IND} - {MSG}'
                             .format(NAME=self.name, IND=index + 1, MSG=msg))

            return None

        # Add any annotations to the exported row
        annotations = self.annotate_rows(df)
        annot_code = annotations.get(index, None)
        if annot_code is not None:
            row['Warnings'] = self.annotation_rules[annot_code]['Description']

        try:
            record = self._translate_row(row, level=level, new_record=False, references=references)
        except Exception as e:
            msg = 'failed to open record at row {IND}'.format(IND=index + 1)
            mod_win2.popup_error(msg)
            logger.exception('DataTable {NAME}: {MSG} - {ERR}'.format(NAME=self.name, MSG=msg, ERR=e))

            return None
        else:
            logger.info('DataTable {NAME}: opening record {ID} at row {IND}'
                        .format(NAME=self.name, ID=record.record_id(), IND=index))

        # Display the record window
        logger.debug('DataTable {NAME}: record is set to view only: {VAL}'.format(NAME=self.name, VAL=view_only))
        record = mod_win2.record_window(record, view_only=view_only, modify_database=savable)

        return record

    def delete_rows(self, indices):
        """
        Remove records from the records table.

        Arguments:
            indices (list): real indices of the desired records to remove from the table.
        """
        df = self.df.copy()

        if isinstance(indices, str):
            indices = [indices]

        select_df = df.iloc[indices]
        if select_df.empty:
            return df
        else:
            self.edited = True

        # Get record IDs for all selected rows
        record_ids = select_df[self.id_column].tolist()
        logger.info('DataTable {TBL}: removing records {IDS} from the table'
                    .format(TBL=self.name, IDS=record_ids))

        # Set the deleted field for the selected rows to True
        df.loc[df[self.id_column].isin(record_ids), [self.deleted_column, self.edited_column]] = [True, True]

        # Add removed rows to the import dataframe if the records were not created within the table
        self.import_df = self.append(select_df, imports=True)

        # Set the dataframe
        self.df = df

        return df

    def import_rows(self):
        """
        Import one or more records through the record import window.
        """
        # pd.set_option('display.max_columns', None)
        import_df = self.import_df.copy()
        logger.debug('DataTable {NAME}: importing rows'.format(NAME=self.name))
        id_col = self.id_column

        table_layout = {'Columns': self.columns, 'DisplayColumns': self.display_columns, 'Aliases': self.aliases,
                        'RowColor': self.row_color, 'Widths': self.widths, 'IDColumn': self.id_column,
                        'RecordType': self.record_type, 'Description': self.description,
                        'ImportRules': self.import_rules, 'SortBy': self.sort_on, 'FilterParameters': self.filter_entry,
                        'Modifiers': {'search': 1, 'filter': 1, 'export': 1, 'options': 1, 'sort': 1},
                        'HiddenColumns': self.hidden_columns
                        }

        import_table = RecordTable(self.name, table_layout)
        import_table.df = import_df

        # Add relevant search parameters
        search_field = self.search_field
        if isinstance(search_field, tuple):
            search_col, search_val = search_field
            try:
                search_description = self.display_columns[search_col]
            except KeyError:
                search_description = search_col

            search_dtype = self.columns[search_col]
            search_entry = {'Description': search_description, 'ElementType': 'input', 'PatternMatching': True,
                            'DataType': search_dtype, 'DefaultValue': search_val}
            search_params = [mod_param.DataParameterInput(search_col, search_entry)]
        else:
            search_params = None

        import_table.sort()

        # Get table of user selected import records
        select_df = mod_win2.import_window(import_table, params=search_params)
        if not select_df.empty:
            self.edited = True

        # Verify that selected records are not already in table
        current_ids = self.df[id_col].tolist()
        select_ids = select_df[id_col]
        remove_indices = []
        for index, record_id in select_ids.items():
            if record_id in current_ids:
                remove_indices.append(index)
        logger.debug('DataTable {NAME}: removing selected records already stored in the table at rows {ROWS}'
                     .format(NAME=self.name, ROWS=remove_indices))
        select_df.drop(remove_indices, inplace=True, axis=0, errors='ignore')

        # Change deleted column of existing selected records to False
        logger.debug('DataTable {NAME}: changing deleted status of selected records already stored in the table to '
                     'False'.format(NAME=self.name))
        self.df.loc[self.df[id_col].isin(select_ids), self.deleted_column] = False

        # Append selected rows to the table
        logger.debug('DataTable {NAME}: importing {N} records to the table'
                     .format(NAME=self.name, N=select_df.shape[0]))
        select_df.loc[:, self.added_column] = True
        df = self.append(select_df)
        self.df = df

        # Remove selected rows from the table of available import rows
        self.import_df = import_df[~import_df[self.id_column].isin(select_ids)]

        return df


class ComponentTable(RecordTable):
    """
    Subclass of the records table, but for record components. Allows additional actions such as creating
    associated records.

    Attributes:

        name (str): table element configuration name.

        elements (list): list of table element keys.

        title (str): display title.

        etype (str): program element type.

        modifiers (dict): flags that alter the element's behavior.

        association_rule (str): name of the association rule connecting the associated records.
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

        self.elements.extend(['-{NAME}_{ID}_{ELEM}-'.format(NAME=name, ID=self.id, ELEM=i) for i in
                              ('Add',)])

        elem_key = self.key_lookup('Element')
        add_hkey = '{}+ADD+'.format(elem_key)
        action_keys = [self.key_lookup('Add'), add_hkey]
        self._action_events.extend(action_keys)
        self.bindings.extend(action_keys)

        self.etype = 'component_table'
        self.eclass = 'references'

        try:
            modifiers = entry['Modifiers']
        except KeyError:
            self.modifiers = {'open': False, 'edit': False, 'export': False, 'search': False, 'summary': False,
                              'filter': False, 'import': False, 'add': False, 'delete': False, 'fill': False,
                              'options': False, 'sort': False, 'unassociated': False}
        else:
            self.modifiers = {'open': modifiers.get('open', 0), 'edit': modifiers.get('edit', 0),
                              'export': modifiers.get('export', 0), 'import': modifiers.get('import', 0),
                              'search': modifiers.get('search', 0), 'summary': modifiers.get('summary', 0),
                              'filter': modifiers.get('filter', 0), 'add': modifiers.get('add', 0),
                              'delete': modifiers.get('delete', 0), 'fill': modifiers.get('fill', 0),
                              'options': modifiers.get('options', 0), 'sort': modifiers.get('sort', 0),
                              'unassociated': modifiers.get('unassociated', 0)}
            for modifier in self.modifiers:
                try:
                    flag = bool(int(self.modifiers[modifier]))
                except ValueError:
                    logger.warning('DataTable {TBL}: modifier {MOD} must be either 0 (False) or 1 (True)'
                                   .format(TBL=self.name, MOD=modifier))
                    flag = False

                self.modifiers[modifier] = flag

        try:
            self.association_rule = entry['AssociationRule']
        except KeyError:
            msg = 'ReferenceBox {NAME}: missing required parameter "AssociationRule"'.format(NAME=self.name)
            logger.error(msg)

            raise AttributeError(msg)

    def bind_keys(self, window):
        """
        Add hotkey bindings to the data element.
        """
        level = self.level

        elem_key = self.key_lookup('Element')
        window[elem_key].bind('<Control-f>', '+FILTER+')
        if level < 2:
            window[elem_key].bind('<Return>', '+RETURN+')
            window[elem_key].bind('<Double-Button-1>', '+LCLICK+')
            window[elem_key].bind('<Key-BackSpace>', '+DELETE+')
            window[elem_key].bind('<Control-d>', '+DELETE+')
            window[elem_key].bind('<Control-i>', '+IMPORT+')
            window[elem_key].bind('<Control-a>', '+ADD+')

    def run_action_event(self, window, event, values):
        """
        Run a table action event.
        """
        elem_key = self.key_lookup('Element')
        open_key = '{}+LCLICK+'.format(elem_key)
        return_key = '{}+RETURN+'.format(elem_key)
        add_key = self.key_lookup('Add')
        add_hkey = '{}+ADD+'.format(elem_key)
        delete_key = self.key_lookup('Delete')
        delete_hkey = '{}+DELETE+'.format(elem_key)
        import_key = self.key_lookup('Import')
        import_hkey = '{}+IMPORT+'.format(elem_key)

        can_open = self.modifiers['open']
        can_edit = self.modifiers['edit']
        can_import = not window[import_key].metadata['disabled'] and window[import_key].metadata['visible']
        can_delete = not window[delete_key].metadata['disabled'] and window[delete_key].metadata['visible']
        can_add = not window[add_key].metadata['disabled'] and window[add_key].metadata['visible']

        # Row click event
        update_event = False
        if event in (open_key, return_key) and can_open:
            # Close options panel, if open
            self.set_table_dimensions(window)

            # Find row selected by user from the display table of non-deleted rows
            try:
                select_row_index = values[elem_key][0]
            except IndexError:  # user double-clicked too quickly
                msg = 'table row could not be selected'
                logger.debug('DataTable {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
            else:
                self._selected_rows = [select_row_index]

                # Get the real index of the selected row
                index = self.get_index(select_row_index)

                logger.debug('DataTable {NAME}: loading record at index {IND}'
                             .format(NAME=self.name, IND=index))
                record = self.load_record(index)

                # Update record table values
                if record and can_edit:
                    try:
                        record_values = record.export_values()
                    except Exception as e:
                        msg = 'unable to update row {IND} values'.format(IND=index)
                        logger.exception('DataTable {NAME}: {MSG} - {ERR}'.format(NAME=self.name, MSG=msg, ERR=e))
                    else:
                        update_event = self._update_row_values(index, record_values)

        # Add row button clicked
        if event in (add_key, add_hkey) and can_add:
            # Close options panel, if open
            self.set_table_dimensions(window)

            try:
                self.add_row()
            except Exception as e:
                msg = 'failed to run table add event'
                logger.exception('DataTable {NAME}: {MSG} - {ERR}'.format(NAME=self.name, MSG=msg, ERR=e))
            else:
                update_event = True

        # Delete rows button clicked
        if event in (delete_key, delete_hkey) and can_delete:
            # Find rows selected by user for deletion
            select_row_indices = values[elem_key]

            # Get the real indices of the selected rows
            indices = self.get_index(select_row_indices)
            if len(indices) > 0:
                self.delete_rows(indices)
                update_event = True

        # Import rows button clicked
        if event in (import_key, import_hkey) and can_import:
            # Close options panel, if open
            self.set_table_dimensions(window)

            try:
                self.import_rows()
            except Exception as e:
                msg = 'failed to run table import event'
                logger.exception('DataTable {NAME}: {MSG} - {ERR}'.format(NAME=self.name, MSG=msg, ERR=e))
            else:
                update_event = True

        # All action events require a table update
        if update_event:
            logger.debug('DataTable {NAME}: event {EVENT} is an update event - will update display'
                         .format(NAME=self.name, EVENT=event))
            self.update_display(window)
        else:
            logger.debug('DataTable {NAME}: event {EVENT} is not an update event - will not update display'
                         .format(NAME=self.name, EVENT=event))

        return update_event

    def action_layout(self, disabled: bool = True):
        """
        Layout for the table action elements.
        """
        import_key = self.key_lookup('Import')
        add_key = self.key_lookup('Add')
        delete_key = self.key_lookup('Delete')
        custom_bttns = self.custom_actions

        # Element settings
        text_col = mod_const.TEXT_COL  # standard text color
        header_col = mod_const.TBL_HEADER_COL  # color of the header background
        highlight_col = mod_const.HIGHLIGHT_COL
        bwidth = 1

        # Layout
        bttn_layout = [sg.Button('', key=import_key, image_data=mod_const.TBL_IMPORT_ICON, border_width=bwidth,
                                 button_color=(text_col, header_col), mouseover_colors=(text_col, highlight_col),
                                 disabled=disabled, visible=self.modifiers['import'],
                                 tooltip='Import database records (CTRL+I)',
                                 metadata={'visible': self.modifiers['import'], 'disabled': disabled}),
                       sg.Button('', key=add_key, image_data=mod_const.TBL_ADD_ICON, border_width=bwidth,
                                 button_color=(text_col, header_col), mouseover_colors=(text_col, highlight_col),
                                 disabled=disabled, visible=self.modifiers['add'],
                                 tooltip='Create new component record (CTRL+A)',
                                 metadata={'visible': self.modifiers['add'], 'disabled': disabled}),
                       sg.Button('', key=delete_key, image_data=mod_const.TBL_DEL_ICON, border_width=bwidth,
                                 button_color=(text_col, header_col), mouseover_colors=(text_col, highlight_col),
                                 disabled=disabled, visible=self.modifiers['delete'],
                                 tooltip='Remove selected rows (CTRL+D)',
                                 metadata={'visible': self.modifiers['delete'], 'disabled': disabled})]

        for custom_bttn in custom_bttns:
            custom_entry = custom_bttns[custom_bttn]

            custom_layout = sg.Button('', key=custom_entry.get('Key', None), image_data=custom_entry.get('Icon', None),
                                      border_width=bwidth, disabled=disabled, visible=True,
                                      button_color=(text_col, header_col), mouseover_colors=(text_col, highlight_col),
                                      tooltip=custom_entry.get('Description', custom_bttn),
                                      metadata={'visible': True, 'disabled': disabled})
            bttn_layout.append(custom_layout)

        layout = [sg.Col([bttn_layout], justification='l', background_color=header_col, expand_x=True, expand_y=False)]

        return layout

    def enable(self, window, custom: bool = True):
        """
        Enable data table element actions.
        """
        # params = self.parameters
        add_key = self.key_lookup('Add')
        delete_key = self.key_lookup('Delete')
        import_key = self.key_lookup('Import')
        custom_bttns = self.custom_actions

        logger.debug('DataTable {NAME}: enabling table action elements'.format(NAME=self.name))

        # Enable table modification buttons
        window[add_key].update(disabled=False)
        window[add_key].metadata['disabled'] = False

        window[delete_key].update(disabled=False)
        window[delete_key].metadata['disabled'] = False

        window[import_key].update(disabled=False)
        window[import_key].metadata['disabled'] = False

        if custom:
            for custom_bttn in custom_bttns:
                custom_entry = custom_bttns[custom_bttn]
                try:
                    bttn_key = custom_entry['Key']
                except KeyError:
                    continue

                window[bttn_key].update(disabled=False)
                window[bttn_key].metadata['disabled'] = False

    def disable(self, window):
        """
        Disable data table element actions.
        """
        # params = self.parameters
        add_key = self.key_lookup('Add')
        delete_key = self.key_lookup('Delete')
        import_key = self.key_lookup('Import')
        custom_bttns = self.custom_actions

        logger.debug('DataTable {NAME}: disabling table action elements'.format(NAME=self.name))

        # Disable table modification buttons
        window[add_key].update(disabled=True)
        window[add_key].metadata['disabled'] = True

        window[delete_key].update(disabled=True)
        window[delete_key].metadata['disabled'] = True

        window[import_key].update(disabled=True)
        window[import_key].metadata['disabled'] = True

        for custom_bttn in custom_bttns:
            custom_entry = custom_bttns[custom_bttn]
            try:
                bttn_key = custom_entry['Key']
            except KeyError:
                continue

            window[bttn_key].update(disabled=True)
            window[bttn_key].metadata['disabled'] = True

    def load_record(self, index, level: int = None, references: dict = None, savable: bool = False):
        """
        Open selected record in new record window.

        Arguments:
            index (int): real index of the desired record to load.

            level (int): level at which the record should be loaded [Default: current level + 1]

            references (dict): load record using custom reference dictionary.

            savable (bool): database entry of the record can be updated through the record window [Default: True].
        """
        df = self.df.copy()
        modifiers = self.modifiers

        level = level if level is not None else self.level + 1
        view_only = False if modifiers['edit'] is True else True

        try:
            row = df.loc[index]
        except IndexError:
            msg = 'no record found at table index {IND} to edit'.format(IND=index + 1)
            mod_win2.popup_error(msg)
            logger.exception('DataTable {NAME}: failed to open record at row {IND} - {MSG}'
                             .format(NAME=self.name, IND=index + 1, MSG=msg))

            return None

        # Add any annotations to the exported row
        annotations = self.annotate_rows(df)
        annot_code = annotations.get(index, None)
        if annot_code is not None:
            row['Warnings'] = self.annotation_rules[annot_code]['Description']

        try:
            record = self._translate_row(row, level=level, new_record=False, references=references)
        except Exception as e:
            msg = 'failed to open record at row {IND}'.format(IND=index + 1)
            mod_win2.popup_error(msg)
            logger.exception('DataTable {NAME}: {MSG} - {ERR}'.format(NAME=self.name, MSG=msg, ERR=e))

            return None
        else:
            logger.info('DataTable {NAME}: opening record {ID} at row {IND}'
                        .format(NAME=self.name, ID=record.record_id(), IND=index))

        # Display the record window
        logger.debug('DataTable {NAME}: record is set to view only: {VAL}'.format(NAME=self.name, VAL=view_only))
        record = mod_win2.record_window(record, view_only=view_only, modify_database=savable)

        return record

    def add_row(self, record_date: datetime.datetime = None, defaults: dict = None):
        """
        Create a new record and add it to the records table.

        Arguments:
            record_date (datetime): set record date to date [Default: use current date and time].

            defaults (dict): provide new record with custom default values.
        """
        df = self.df.copy()
        header = list(self.columns)

        creation_date = record_date if isinstance(record_date, datetime.datetime) else datetime.datetime.now()
        defaults = defaults if defaults is not None else {}

        if self.record_type is None:
            msg = 'required attribute "record_type" missing from the configuration'
            logger.warning('DataTable {NAME}: failed to add a new row to the table - {ERR}'
                           .format(NAME=self.name, ERR=msg))
            mod_win2.popup_error(msg)
            return df

        # Create a new record object
        record_entry = settings.records.fetch_rule(self.record_type)

        record_id = record_entry.create_record_ids(creation_date, offset=settings.get_date_offset())
        if not record_id:
            msg = 'unable to create an ID for the new record'
            logger.error('Error: DataTable {NAME}: failed to add new row to the table - {ERR}'
                         .format(NAME=self.name, ERR=msg))
            mod_win2.popup_error(msg)

            return df

        record_data = pd.Series(index=header)

        # Set default values for the new record
        for default_col in defaults:
            if default_col not in header:
                continue

            default_value = defaults[default_col]
            record_data[default_col] = default_value

        record_data[self.id_column] = record_id
        record_data[self.date_column] = creation_date

        record_data = self.set_defaults(record_data)

        try:
            record = self._translate_row(record_data, level=1, new_record=True)
        except Exception as e:
            msg = 'failed to add record at row {IND} - {ERR}'.format(IND=df.shape[0] + 2, ERR=e)
            mod_win2.popup_error(msg)
            logger.error('DataTable {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
            return df

        # Display the record window
        record = mod_win2.record_window(record, modify_database=False)
        try:
            record_values = record.export_values()
        except AttributeError:  # record creation was cancelled
            return df
        else:
            logger.debug('DataTable {NAME}: appending values {VALS} to the table'
                         .format(NAME=self.name, VALS=record_values))
            record_values[self.added_column] = True
            df = self.append(record_values)

            self.edited = True

        self.df = df

        return df

    def import_rows(self):
        """
        Import one or more records through the record import window.
        """
        # pd.set_option('display.max_columns', None)
        import_df = self.import_df.copy()
        rule_name = self.association_rule
        modifiers = self.modifiers
        record_type = self.record_type
        id_col = self.id_column

        logger.debug('DataTable {NAME}: importing rows'.format(NAME=self.name))

        table_layout = {'Columns': self.columns, 'DisplayColumns': self.display_columns, 'Aliases': self.aliases,
                        'RowColor': self.row_color, 'Widths': self.widths, 'IDColumn': self.id_column,
                        'RecordType': record_type, 'Description': self.description,
                        'ImportRules': self.import_rules, 'SortBy': self.sort_on, 'FilterParameters': self.filter_entry,
                        'Modifiers': {'search': 1, 'filter': 1, 'export': 1, 'options': 1, 'sort': 1},
                        'HiddenColumns': self.hidden_columns,
                        }

        import_table = RecordTable(self.name, table_layout)

        # Search for records without an existing reference to the provided reference type
        if modifiers['unassociated']:  # option only available for program records
            record_entry = settings.records.fetch_rule(record_type)
            logger.debug('DataTable {NAME}: importing unreferenced records on rule "{RULE}"'
                         .format(NAME=self.name, RULE=rule_name))

            # Import the entries from the reference table with record references unset
            try:
                ref_ids = record_entry.search_unreferenced_ids(rule_name)
                df = record_entry.load_records(ref_ids)
            except Exception as e:
                msg = 'failed to import unreferenced records from association rule {RULE}'.format(RULE=rule_name)
                logger.exception('DataTable {NAME}: {MSG} - {ERR}'.format(NAME=self.name, MSG=msg, ERR=e))
            else:
                if not df.empty:
                    # Subset on table columns
                    df = df[[i for i in df.columns.values if i in import_df.columns]]

                    # Drop records that are already in the import dataframe
                    import_ids = import_df[id_col].tolist()
                    df.drop(df[df[id_col].isin(import_ids)].index, inplace=True)

                    # Drop records that are already in the component dataframe
                    current_ids = self.df[id_col].tolist()
                    df.drop(df[df[id_col].isin(current_ids)].index, inplace=True)

                    # Add import dataframe to data table object
                    #                    import_table.df = import_df.append(df, ignore_index=True)
                    import_table.df = self.append(df, imports=True)
        else:
            import_table.df = import_df

        # Add relevant search parameters
        search_field = self.search_field
        if isinstance(search_field, tuple):
            search_col, search_val = search_field
            try:
                search_description = self.display_columns[search_col]
            except KeyError:
                search_description = search_col

            search_dtype = self.columns[search_col]
            search_entry = {'Description': search_description, 'ElementType': 'input', 'PatternMatching': True,
                            'DataType': search_dtype, 'DefaultValue': search_val}
            search_params = [mod_param.DataParameterInput(search_col, search_entry)]
        else:
            search_params = None

        import_table.sort()

        # Get table of user selected import records
        select_df = mod_win2.import_window(import_table, params=search_params)
        if not select_df.empty:
            self.edited = True

        # Verify that selected records are not already in table
        current_ids = self.df[id_col].tolist()
        select_ids = select_df[id_col]
        remove_indices = []
        for index, record_id in select_ids.items():
            if record_id in current_ids:
                remove_indices.append(index)
        logger.debug('DataTable {NAME}: removing selected records already stored in the table at rows {ROWS}'
                     .format(NAME=self.name, ROWS=remove_indices))
        select_df.drop(remove_indices, inplace=True, axis=0, errors='ignore')

        # Change deleted column of existing selected records to False
        logger.debug('DataTable {NAME}: changing deleted status of selected records already stored in the table to '
                     'False'.format(NAME=self.name))
        self.df.loc[self.df[id_col].isin(select_ids), self.deleted_column] = False

        # Append selected rows to the table
        logger.debug('DataTable {NAME}: importing {N} records to the table'
                     .format(NAME=self.name, N=select_df.shape[0]))
        select_df[self.added_column] = True
        df = self.append(select_df)

        self.df = df

        # Remove selected rows from the table of available import rows
        self.import_df = import_df[~import_df[self.id_column].isin(select_ids)]

        return df

    def export_reference(self, record_id, edited_only: bool = False):
        """
        Export component table records as reference entries.

        Arguments:
            record_id (str): ID of the referenced record.

            edited_only (bool): export references only for components that were added or edited.
        """
        df = self.df

        # Filter added rows that were later removed from the table
        conditions = df[self.deleted_column] & df[self.added_column]
        export_df = df[~conditions]

        if edited_only:
            export_df = export_df[(export_df[self.added_column]) | (export_df[self.edited_column])]

        # Create the reference entries
        ref_df = export_df[[self.id_column, self.deleted_column]]
        ref_df.rename(columns={self.id_column: 'ReferenceID', self.deleted_column: 'IsDeleted'}, inplace=True)

        if ref_df.empty:
            return ref_df

        ref_df.loc[:, 'RecordID'] = record_id
        ref_df.loc[:, 'RecordType'] = self.parent
        ref_df.loc[:, 'ReferenceDate'] = datetime.datetime.now()
        ref_df.loc[:, 'ReferenceType'] = self.record_type

        # Add reference notes based on row annotations
        annotations = self.annotate_rows(export_df)
        annotation_map = {i: self.annotation_rules[j]['Description'] for i, j in annotations.items()}

        ref_df.loc[:, 'ReferenceNotes'] = ref_df.index.map(annotation_map)

        return ref_df


class ReferenceBox(RecordElement):
    """
    Record reference box element.

    Attributes:

        name (str): reference box element configuration name.

        id (int): reference box element number.

        parent (str): name of the parent element.

        elements (list): list of reference box element GUI keys.

        etype (str): program element type.

        modifiers (dict): flags that alter the element's behavior.

        association_rule (str): name of the association rule connecting the associated records.

        aliases (dict): layout element aliases.

        edited (bool): reference box was edited [Default: False]
    """

    def __init__(self, name, entry, parent=None):
        """
        Initialize the reference box element attributes.

        Arguments:
            name (str): reference box element configuration name.

            entry (dict): configuration entry for the element.

            parent (str): name of the parent element.
        """
        super().__init__(name, entry, parent)
        self.etype = 'refbox'
        self.eclass = 'references'

        self.elements.extend(['-{NAME}_{ID}_{ELEM}-'.format(NAME=name, ID=self.id, ELEM=i) for i in
                              ('Frame', 'RefDate', 'Unlink', 'ParentFlag', 'HardLinkFlag', 'Approved')])
        self._event_elements = ['Element', 'Frame', 'Approved', 'Unlink']

        # Element-specific bindings
        elem_key = self.key_lookup('Element')
        return_key = '{}+RETURN+'.format(elem_key)
        frame_key = self.key_lookup('Frame')
        focus_key = '{}+FOCUS+'.format(frame_key)
        self.bindings = [self.key_lookup(i) for i in self._event_elements] + [return_key, focus_key]

        try:
            modifiers = entry['Modifiers']
        except KeyError:
            self.modifiers = {'open': None, 'delete': None, 'approve': None, 'require': False}
        else:
            self.modifiers = {'open': modifiers.get('open', None), 'delete': modifiers.get('delete', None),
                              'approve': modifiers.get('approve', None), 'require': modifiers.get('require', False)}
            for modifier in self.modifiers:
                mod_value = self.modifiers[modifier]
                if pd.isna(mod_value):
                    continue

                try:
                    flag = bool(int(mod_value))
                except ValueError:
                    logger.warning('ReferenceBox {NAME}: element modifier {MOD} must be either 0 (False) or 1 (True)'
                                   .format(NAME=self.name, MOD=modifier))
                    flag = False

                self.modifiers[modifier] = flag

        try:
            self.association_rule = entry['AssociationRule']
        except KeyError:
            msg = 'ReferenceBox {NAME}: missing required parameter "AssociationRule"'.format(NAME=self.name)
            logger.error(msg)

            raise AttributeError(msg)

        try:
            self.aliases = entry['Aliases']
        except KeyError:
            self.aliases = {}

        try:
            self.colmap = entry['ColumnMap']
        except KeyError:
            self.colmap = {}

        self.level = 0

        # Dynamic values
        self.record_id = None
        self.reference_id = None
        self.reference_type = None
        self.date = None
        self.notes = None
        self.is_hardlink = False
        self.is_pc = False
        self.approved = False
        self.referenced = False

        self._dimensions = (mod_const.REFBOX_WIDTH, mod_const.REFBOX_HEIGHT)

    def reset(self, window):
        """
        Reset the reference box to default.
        """
        self.record_id = None
        self.reference_id = None
        self.reference_type = None
        self.date = None
        self.notes = None
        self.is_hardlink = False
        self.is_pc = False
        self.approved = False
        self.referenced = False
        self.edited = False

        self.update_display(window)

    def bind_keys(self, window):
        """
        Add hotkey bindings to the reference box.
        """
        level = self.level

        elem_key = self.key_lookup('Element')
        frame_key = self.key_lookup('Frame')

        if level < 2:
            window[elem_key].bind('<Return>', '+RETURN+')
            window[frame_key].bind('<Enter>', '+FOCUS+')

    def run_event(self, window, event, values):
        """
        Run a record reference event.
        """
        ref_key = self.key_lookup('Element')
        return_key = '{}+RETURN+'.format(ref_key)
        approved_key = self.key_lookup('Approved')
        del_key = self.key_lookup('Unlink')
        frame_key = self.key_lookup('Frame')
        focus_key = '{}+FOCUS+'.format(frame_key)

        update_event = False

        logger.info('ReferenceBox {NAME}: running event {EVENT}'.format(NAME=self.name, EVENT=event))

        if event == focus_key:
            window[ref_key].set_focus()

        # Delete a reference from the record reference database table
        if event == del_key:
            if self.is_hardlink:  # hard-linked records can be deleted, but not the association between them
                msg = 'failed to remove the association - the association between hard-linked records cannot be deleted'
                mod_win2.popup_notice(msg)
                logger.warning('ReferenceBox {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                return False

            msg = 'Are you sure that you would like to disassociate reference {REF} from the record? Disassociating ' \
                  'records does not delete either record involved.'.format(REF=self.reference_id)
            user_action = mod_win2.popup_confirm(msg)

            if user_action.upper() == 'OK':
                # Reset reference attributes
                self.referenced = False
                self.edited = True

                self.reference_id = None
                self.reference_type = None
                self.date = None
                self.notes = None
                self.is_hardlink = False
                self.is_pc = False
                self.approved = False

                update_event = True
                self.update_display(window)

        # Update approved element
        elif event == approved_key:
            window[approved_key].set_focus()

            self.approved = bool(values[approved_key])
            self.edited = True
            update_event = True

        # Open reference record in a new record window
        elif event in (ref_key, return_key):
            window[ref_key].set_focus()

            try:
                record = self.load_record()
            except Exception as e:
                msg = 'failed to open the reference record {ID} - {ERR}'.format(ID=self.reference_id, ERR=e)
                mod_win2.popup_error(msg)
                logger.error('ReferenceBox {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
            else:
                # Display the record window
                mod_win2.record_window(record, view_only=True)

        return update_event

    def layout(self, size: tuple = None, padding: tuple = (0, 0), tooltip: str = None, editable: bool = True,
               overwrite: bool = False, level: int = 0):
        """
        GUI layout for the reference box element.
        """
        size = self._dimensions if not size else size
        self._dimensions = size
        width, height = size

        is_approved = self.approved
        aliases = self.aliases
        modifiers = self.modifiers
        reference_note = self.notes if self.notes is not None else ''

        self.level = level

        # Layout options
        pad_el = mod_const.ELEM_PAD
        pad_v = mod_const.VERT_PAD
        pad_h = mod_const.HORZ_PAD

        font = mod_const.LARGE_FONT
        bold_font = mod_const.BOLD_FONT

        text_col = mod_const.TEXT_COL
        bg_col = self.bg_col
        tooltip = tooltip if tooltip else ''

        # Allowed actions and visibility of component elements
        is_disabled = False if (editable is True and level < 1) else True
        can_approve = True if (modifiers['approve'] is True and not is_disabled) or (overwrite is True) else False
        can_delete = True if (modifiers['delete'] is True and not is_disabled) or (overwrite is True) else False
        can_open = True if (modifiers['open'] is True and editable and level < 2) or (overwrite is True) else False

        select_text_col = mod_const.SELECT_TEXT_COL if can_open else mod_const.DISABLED_TEXT_COL

        approved_vis = True if modifiers['approve'] is not None else False
        hl_vis = True if self.is_hardlink is True else False
        pc_vis = True if self.is_pc is True else False

        # Element layout
        ref_key = self.key_lookup('Element')
        frame_key = self.key_lookup('Frame')
        discard_key = self.key_lookup('Unlink')
        link_key = self.key_lookup('HardLinkFlag')
        parent_key = self.key_lookup('ParentFlag')
        approved_key = self.key_lookup('Approved')
        ref_id = self.reference_id if self.reference_id else None
        approved_title = 'Reference approved' if 'IsApproved' not in aliases else aliases['IsApproved']
        elem_layout = [[sg.Col([[sg.Text(self.description, auto_size_text=True, pad=((0, pad_el), (0, pad_v)),
                                         text_color=text_col, font=bold_font, background_color=bg_col,
                                         tooltip=tooltip)],
                                [sg.Text(ref_id, key=ref_key, auto_size_text=True, pad=((0, pad_el * 2), 0),
                                         enable_events=can_open, text_color=select_text_col, font=font,
                                         background_color=bg_col, tooltip='open reference record'),
                                 sg.Image(data=mod_const.LINKED_ICON, key=link_key, visible=hl_vis,
                                          pad=(0, 0), background_color=bg_col,
                                          tooltip=('Reference record is hard-linked' if 'IsHardLink' not in aliases else
                                                   aliases['IsHardLink'])),
                                 sg.Image(data=mod_const.PARENT_ICON, key=parent_key, visible=pc_vis,
                                          pad=(0, 0), background_color=bg_col,
                                          tooltip=('Reference record is a parent' if 'IsParentChild' not in aliases else
                                                   aliases['IsParentChild']))]],
                               pad=((pad_h, 0), pad_v), vertical_alignment='t', background_color=bg_col, expand_x=True),
                        sg.Col([[sg.Text(approved_title, font=font, background_color=bg_col, text_color=text_col,
                                         visible=approved_vis),
                                 sg.Checkbox('', default=is_approved, key=approved_key, enable_events=True,
                                             disabled=(not can_approve), visible=approved_vis,
                                             background_color=bg_col)],
                                [sg.Button(image_data=mod_const.DISCARD_ICON, key=discard_key, pad=((0, pad_el * 2), 0),
                                           disabled=(not can_delete), button_color=(text_col, bg_col), border_width=0,
                                           tooltip=('Remove link to reference' if 'RemoveLink' not in aliases else
                                                    aliases['RemoveLink']))]],
                               pad=((0, pad_h), pad_v), justification='r', element_justification='r',
                               vertical_alignment='c', background_color=bg_col)
                        ]]

        layout = sg.Frame('', elem_layout, key=frame_key, size=(width, height), pad=padding, background_color=bg_col,
                          relief='raised', visible=self.referenced, vertical_alignment='c', element_justification='l',
                          metadata={'deleted': False, 'name': self.name}, tooltip=reference_note)

        return layout

    def resize(self, window, size: tuple = None):
        """
        Resize the reference box element.
        """
        current_w, current_h = self.dimensions()
        border_w = 1

        if size:
            width, height = size
            new_h = current_h if height is None else height - border_w * 2
            new_w = current_w if width is None else width - border_w * 2
        else:
            new_w, new_h = (current_w, current_h)

        frame_key = self.key_lookup('Frame')
        new_size = (new_w, new_h)
        mod_lo.set_size(window, frame_key, new_size)

        self._dimensions = new_size

        return window[frame_key].get_size()

    def dimensions(self):
        """
        Return the current dimensions of the element.
        """
        return self._dimensions

    def update_display(self, window):
        """
        Update the display element.
        """
        link_key = self.key_lookup('HardLinkFlag')
        parent_key = self.key_lookup('ParentFlag')
        frame_key = self.key_lookup('Frame')
        ref_key = self.key_lookup('Element')
        date_key = self.key_lookup('RefDate')
        approved_key = self.key_lookup('Approved')
        discard_key = self.key_lookup('Unlink')

        logger.debug('ReferenceBox {NAME}: updating reference box display'.format(NAME=self.name))

        is_hl = self.is_hardlink
        is_pc = self.is_pc
        referenced = self.referenced
        reference_note = self.notes

        # Update value of approved checkbox
        window[approved_key].update(value=self.approved)

        # Update the Date and ID elements if no values
        if not window[ref_key].get():  # current ID and date not set yet
            ref_id = self.reference_id
            ref_date = settings.format_display_date(self.date) if self.date else None
            window[ref_key].update(value=ref_id)
            window[date_key].update(value=ref_date)

        # Update visibility of the element
        if referenced:
            window[frame_key].update(visible=True)
        else:
            window[frame_key].update(visible=False)

        # Set flag badges and disable delete button if reference is a child or hard-linked
        if is_hl:
            window[link_key].update(visible=True)
            window[discard_key].update(disabled=True)
        else:
            window[link_key].update(visible=False)

        if is_pc:
            window[parent_key].update(visible=True)
            window[discard_key].update(disabled=True)
        else:
            window[parent_key].update(visible=False)

        # Set notes
        bg_col = self.bg_col if not reference_note else mod_const.BOX_COL
        window[frame_key].Widget.config(background=bg_col)
        #window[frame_key].Widget.config(highlightbackground=bg_col)
        window[frame_key].Widget.config(highlightcolor=bg_col)

        tooltip = self.format_tooltip()
        #window.Element(frame_key).SetTooltip(reference_note)
        window[frame_key].set_tooltip(tooltip)

    def format_tooltip(self):
        """
        Set the element tooltip.
        """
        aliases = self.aliases
        custom_tooltip = self.tooltip
        reference_note = self.notes

        tooltip = []
        if custom_tooltip:
            tooltip.append(custom_tooltip)
            tooltip.append('')

        info = [[aliases.get('ReferenceType', 'Reference Type'), self.description],
                [aliases.get('ReferenceID', 'Reference ID'), self.reference_id],
                [aliases.get('ReferenceDate', 'Reference Date'), settings.format_display_date(self.date)]]
        for row in info:
            header, data = row
            if data:
                tooltip.append('{}: {}'.format(header, data))

        if reference_note:
            tooltip.append('')
            tooltip.append(reference_note)

        return '\n'.join(tooltip)

    def import_reference(self, entry, new: bool = False):
        """
        Initialize a record reference.

        Arguments:
            entry (Series): reference information.

            new (bool): reference is newly created instead of already existing [Default: False].

        Returns:
            success (bool): reference import was successful.
        """
        if isinstance(entry, pd.DataFrame):  # take first row and reduce dimensionality
            entry = entry.iloc[0].squeeze()
        elif isinstance(entry, dict):
            entry = pd.Series(entry)

        id_col = 'RecordID'
        try:
            self.record_id = entry[id_col]
        except KeyError:
            msg = 'reference entry is missing values for required parameter "{COL}"'.format(COL=id_col)
            logger.error('ReferenceBox {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            return False
        else:
            if pd.isna(self.record_id):
                return False

        ref_id_col = 'ReferenceID'
        try:
            self.reference_id = entry[ref_id_col]
        except KeyError:
            msg = 'reference entry is missing values for required parameter "{COL}"'.format(COL=ref_id_col)
            logger.error('ReferenceBox {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            return False
        else:
            if pd.isna(self.reference_id):
                return False

        logger.info('ReferenceBox {NAME}: loading record {ID} reference {REFID}'
                    .format(NAME=self.name, ID=self.record_id, REFID=self.reference_id))

        date_col = 'ReferenceDate'
        try:
            ref_date = entry[date_col]
        except KeyError:
            msg = 'reference entry is missing values for required parameter "{COL}"'.format(COL=date_col)
            logger.error('ReferenceBox {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            return False
        else:
            try:
                self.date = settings.format_as_datetime(ref_date)
            except ValueError as e:
                msg = 'unable to set reference date {DATE} - {ERR}'.format(DATE=ref_date, ERR=e)
                logger.error('ReferenceBox {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                return False

        ref_type_col = 'ReferenceType'
        try:
            self.reference_type = entry[ref_type_col]
        except KeyError:
            msg = 'reference entry is missing values for required parameter "{COL}"'.format(COL=ref_type_col)
            logger.error('ReferenceBox {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            return False

        warn_col = 'ReferenceNotes'
        try:
            self.notes = entry[warn_col]
        except KeyError:
            msg = 'reference entry is missing values for configured parameter "{COL}"'.format(COL=warn_col)
            logger.debug('ReferenceBox {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
            self.notes = None

        hl_col = 'IsHardLink'
        try:
            self.is_hardlink = bool(int(entry[hl_col]))
        except KeyError:
            msg = 'reference entry is missing values for configured parameter "{COL}"'.format(COL=hl_col)
            logger.debug('ReferenceBox {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
            self.is_hardlink = False
        except ValueError:
            msg = 'parameter "{COL}" was provided unknown value type {VAL}'.format(VAL=entry[hl_col], COL=hl_col)
            logger.debug('ReferenceBox {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
            self.is_hardlink = False

        pc_col = 'IsChild'
        try:
            self.is_pc = bool(int(entry[pc_col]))
        except KeyError:
            msg = 'reference entry is missing values for configured parameter "{COL}"'.format(COL=pc_col)
            logger.debug('ReferenceBox {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
            self.is_pc = False
        except ValueError:
            msg = 'parameter "{COL}" was provided unknown value type {VAL}'.format(VAL=entry[pc_col], COL=pc_col)
            logger.debug('ReferenceBox {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
            self.is_pc = False

        approved_col = 'IsApproved'
        try:
            self.approved = bool(int(entry[approved_col]))
        except KeyError:
            msg = 'reference entry is missing values for configured parameter "{COL}"'.format(COL=approved_col)
            logger.debug('ReferenceBox {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
            self.approved = False
        except ValueError:
            msg = 'parameter "{COL}" was provided unknown value type {VAL}' \
                .format(VAL=entry[approved_col], COL=approved_col)
            logger.debug('ReferenceBox {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
            self.approved = False

        if new:
            self.edited = True

        return True

    def export_reference(self):
        """
        Export the association as a reference entry.

        Returns:
            reference (Series): record reference information in the form of a pandas Series.
        """
        deleted = (not self.referenced)
        indices = ['RecordID', 'ReferenceID', 'ReferenceDate', 'RecordType', 'ReferenceType', 'ReferenceNotes',
                   'IsApproved', 'IsChild', 'IsHardLink', 'IsDeleted']
        values = [self.record_id, self.reference_id, self.date, self.parent, self.reference_type, self.notes,
                  self.approved, self.is_pc, self.is_hardlink, deleted]

        reference = pd.Series(values, index=indices)

        return reference

    def load_record(self, level: int = None):
        """
        Load the reference record from the database.

        Arguments:
            level (int): load the referenced record at the given depth [Default: current level + 1].

        Returns:
            record (DatabaseRecord): initialized database record.
        """
        record_entry = settings.records.fetch_rule(self.reference_type)
        record_class = mod_records.DatabaseRecord

        level = level if level is not None else self.level + 1
        logger.info('ReferenceBox {NAME}: loading reference record {ID} of type {TYPE} at level {LEVEL}'
                    .format(NAME=self.name, ID=self.reference_id, TYPE=self.reference_type, LEVEL=level))

        imports = record_entry.load_records(self.reference_id)
        nrow = imports.shape[0]

        if nrow < 1:
            logger.warning('ReferenceBox {NAME}: record reference {REF} not found in the database'
                           .format(NAME=self.name, REF=self.reference_id))
            record_data = imports
        elif nrow == 1:
            record_data = imports.iloc[0]
        else:
            logger.warning('ReferenceBox {NAME}: more than one database entry found for record reference {REF}'
                           .format(NAME=self.name, REF=self.reference_id))
            record_data = imports.iloc[0]

        record = record_class(record_entry.name, record_entry.record_layout, level=level)
        record.initialize(record_data, new=False)

        return record

    def check_requirements(self):
        """
        Verify that the record element passes requirements.
        """
        passed = True if (self.modifiers['require'] and self.has_value()) or not self.modifiers['require'] else False

        return passed

    def has_value(self):
        """
        True if the reference box contains a record reference else False.
        """
        return self.referenced

    def export_values(self, edited_only: bool = False):
        """
        Export reference attributes as a dictionary.

        Arguments:
            edited_only (bool): only export reference values if the reference had been edited [Default: False].
        """
        if edited_only and not self.edited:
            return {}

        colmap = self.colmap
        reference = self.export_reference()
        values = reference[[i for i in colmap if i in reference.index]].rename(colmap)

        return values.to_dict()


class DataElement(RecordElement):
    """
    Record data element.

    Attributes:

        name (str): data element configuration name.

        id (int): data element number.

        elements (list): list of data element GUI keys.

        description (str): display name of the data element.

        etype (str): program element type. Can be dropdown, input, text, or multiline

        dtype (str): element data type.

        modifiers (dict): flags that alter the element's behavior.

        default: default value of the data element.

        value: value of the data element.

        edited (bool): element value was edited [Default: False].
    """

    def __init__(self, name, entry, parent=None):
        """
        Initialize the data element attributes.

        Arguments:
            name (str): data element configuration name.

            entry (dict): configuration entry for the data element.

            parent (str): name of the parent element.
        """
        super().__init__(name, entry, parent)
        self.etype = 'text'
        self.eclass = 'data'
        self.elements.extend(['-{NAME}_{ID}_{ELEM}-'.format(NAME=name, ID=self.id, ELEM=i) for i in
                              ['Description', 'Edit', 'Save', 'Cancel', 'Frame', 'Update', 'Width', 'Auxiliary']])
        self._event_elements = ['Edit', 'Save', 'Cancel']

        # Element-specific bindings
        elem_key = self.key_lookup('Element')
        lclick_event = '{}+LCLICK+'.format(elem_key)
        return_key = '{}+RETURN+'.format(elem_key)
        escape_key = '{}+ESCAPE+'.format(elem_key)
        self.bindings = [self.key_lookup(i) for i in self._event_elements] + [lclick_event, return_key, escape_key]

        try:
            dtype = entry['DataType']
        except KeyError:
            self.dtype = 'varchar'
        else:
            supported_dtypes = settings.get_supported_dtypes()
            if dtype not in supported_dtypes:
                logger.warning('DataElement {NAME}: "DataType" is not a supported data type - supported data types '
                               'are {TYPES}'.format(NAME=name, TYPES=', '.join(supported_dtypes)))
                self.dtype = 'varchar'
            else:
                self.dtype = dtype

        # Add additional calendar element for input with datetime data types to list of editable elements
        if self.dtype in settings.supported_date_dtypes:
            calendar_key = '-{NAME}_{ID}_Calendar-'.format(NAME=self.name, ID=self.id)
            self.elements.append(calendar_key)
            self.bindings.append(calendar_key)

        # Modifiers
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
                    logger.warning('DataTable {TBL}: modifier {MOD} must be either 0 (False) or 1 (True)'
                                   .format(TBL=self.name, MOD=modifier))
                    flag = False

                self.modifiers[modifier] = flag

        # Formatting options
        try:
            aliases = entry['Aliases']
        except KeyError:
            aliases = settings.fetch_alias_definition(self.name)

        self.aliases = {}  # only str and int types can have aliases - aliases dict reversed during value formatting
        if self.dtype in settings.supported_int_dtypes + settings.supported_cat_dtypes + settings.supported_str_dtypes:
            for alias in aliases:  # alias should have same datatype as the element
                alias_value = aliases[alias]
                self.aliases[settings.format_value(alias, self.dtype)] = alias_value

        try:
            self.date_format = entry['DateFormat']
        except KeyError:
            self.date_format = settings.display_date_format

        # Starting value
        try:
            self.default = self.format_value(entry['DefaultValue'])
        except KeyError:
            self.default = None
        except TypeError as e:
            msg = 'failed to format configured default value {DEF} - {ERR}' \
                .format(DEF=entry['DefaultValue'], ERR=e)
            logger.warning('DataElement {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            self.default = None

        # Dynamic variables
        self._dimensions = (mod_const.DE_WIDTH, mod_const.DE_HEIGHT)
        self.value = self.default

        logger.debug('DataElement {NAME}: initializing {ETYPE} element of data type {DTYPE} with default value {DEF} '
                     'and formatted value {VAL}'
                     .format(NAME=self.name, ETYPE=self.etype, DTYPE=self.dtype, DEF=self.default, VAL=self.value))

        self.disabled = False
        self.edit_mode = False

    def export_values(self, edited_only: bool = False):
        """
        Export the data element value as a dictionary.

        Arguments:
            edited_only (bool): only export element values if the data element had been edited [Default: False].
        """
        if edited_only and not self.edited:
            return {}
        else:
            return {self.name: self.value}

    def reset(self, window):
        """
        Reset data element to default.
        """
        elem_key = self.key_lookup('Element')
        edit_key = self.key_lookup('Edit')
        update_key = self.key_lookup('Update')
        aux_key = self.key_lookup('Auxiliary')

        # Reset element value to its default
        if not pd.isna(self.default) and not pd.isna(self.value):
            logger.debug('DataElement {NAME}: resetting data element value "{VAL}" to default "{DEF}"'
                         .format(NAME=self.name, VAL=self.value, DEF=self.default))

        self.value = self.default
        self.edited = False

        # Reset element editing
        self.edit_mode = False
        window[edit_key].update(disabled=False)
        window[update_key].update(visible=False)
        window[aux_key].update(visible=False)
        window[elem_key].update(disabled=True)

        # Update the element display
        self.update_display(window)

    def run_event(self, window, event, values):
        """
        Perform an element action.
        """
        text_col = mod_const.TEXT_COL
        disabled_text_col = mod_const.DISABLED_TEXT_COL

        elem_key = self.key_lookup('Element')
        edit_key = self.key_lookup('Edit')
        update_key = self.key_lookup('Update')
        save_key = self.key_lookup('Save')
        save_hkey = '{}+RETURN+'.format(elem_key)
        cancel_key = self.key_lookup('Cancel')
        cancel_hkey = '{}+ESCAPE+'.format(elem_key)
        aux_key = self.key_lookup('Auxiliary')
        left_click = '{}+LCLICK+'.format(elem_key)

        currently_editing = self.edit_mode

        update_event = False

        # Set focus to the element and enable edit mode
        if event in (edit_key, left_click) and not currently_editing:
            window[elem_key].set_focus()

            if self.disabled:
                return False

            # Update element to show any current unformatted data
            value_fmt = self.format_display(editing=True)

            # Enable element editing and update colors
            window[edit_key].update(disabled=True)
            window[elem_key].update(disabled=False, value=value_fmt)
            window[update_key].update(visible=True)
            window[aux_key].update(visible=True)

            if self.etype in ('input', 'multiline', 'text'):
                window[elem_key].update(text_color=text_col)
            if self.dtype in settings.supported_date_dtypes:
                date_key = self.key_lookup('Calendar')
                window[date_key].update(disabled=False)

            self.edit_mode = True

        # Set element to inactive mode and update the element value
        elif event in (save_key, save_hkey) and currently_editing:
            # Update value of the data element
            try:
                value = values[elem_key]
            except KeyError:
                logger.warning('DataElement {NAME}: unable to locate values for element key "{KEY}"'
                               .format(NAME=self.name, KEY=elem_key))
            else:
                try:
                    new_value = self.format_value(value)
                except Exception as e:
                    msg = 'failed to save changes to {DESC}'.format(DESC=self.description)
                    logger.exception('DataElement {NAME}: {MSG} - {ERR}'.format(NAME=self.name, MSG=msg, ERR=e))
                    mod_win2.popup_error(msg)

                else:
                    if new_value != self.value:
                        self.value = new_value
                        self.edited = True
                        update_event = True

                self.update_display(window)

            # Disable element editing and update colors
            window[edit_key].update(disabled=False)
            window[elem_key].update(disabled=True)
            window[update_key].update(visible=False)
            window[aux_key].update(visible=False)
            if self.etype in ('input', 'multiline', 'text'):
                window[elem_key].update(text_color=disabled_text_col)
            if self.dtype in settings.supported_date_dtypes:
                date_key = self.key_lookup('Calendar')
                window[date_key].update(disabled=True)

            self.edit_mode = False

        elif event in (cancel_key, cancel_hkey) and currently_editing:
            # Disable element editing and update colors
            window[edit_key].update(disabled=False)
            window[elem_key].update(disabled=True)
            window[update_key].update(visible=False)
            window[aux_key].update(visible=False)
            if self.etype in ('input', 'multiline', 'text'):
                window[elem_key].update(text_color=disabled_text_col)
            if self.dtype in settings.supported_date_dtypes:
                date_key = self.key_lookup('Calendar')
                window[date_key].update(disabled=True)

            self.edit_mode = False

            self.update_display(window)

        return update_event

    def bind_keys(self, window):
        """
        Add hotkey bindings to the data element.
        """
        elem_key = self.key_lookup('Element')

        if not self.disabled:
            window[elem_key].bind('<Button-1>', '+LCLICK+')
            window[elem_key].bind('<Return>', '+RETURN+')
            window[elem_key].bind('<Key-Escape>', '+ESCAPE+')

    def layout(self, padding: tuple = (0, 0), size: tuple = None, tooltip: str = None, editable: bool = True,
               overwrite: bool = False, level: int = 0):
        """
        GUI layout for the data element.
        """
        modifiers = self.modifiers

        is_disabled = (False if (overwrite is True or (editable is True and modifiers['edit'] is True)) and
                       self.etype != 'text' and level < 2 else True)
        self.disabled = is_disabled
        is_required = modifiers['require']
        hidden = modifiers['hide']

        size = self._dimensions if not size else size
        width, height = size
        self._dimensions = (width * 10, mod_const.DE_HEIGHT)

        background = self.bg_col
        tooltip = tooltip if tooltip else ''

        # Layout options
        pad_el = mod_const.ELEM_PAD
        pad_h = mod_const.HORZ_PAD

        bold_font = mod_const.BOLD_HEADING_FONT

        bg_col = mod_const.ACTION_COL if background is None else background
        text_col = mod_const.TEXT_COL

        # Element Icon, if provided
        icon = self.icon
        if icon is not None:
            icon_path = settings.get_icon_path(icon)
            if icon_path is not None:
                icon_layout = [sg.Image(filename=icon_path, pad=((0, pad_el), 0), background_color=bg_col)]
            else:
                icon_layout = []
        else:
            icon_layout = []

        # Required symbol
        if is_required is True:
            required_layout = [sg.Text('*', pad=(pad_el, 0), font=bold_font, background_color=bg_col,
                                       text_color=mod_const.NOTE_COL, tooltip='required')]
        else:
            required_layout = []

        # Add auxiliary elements to the layout, such as a calendar button for datetime elements.
        accessory_layout = []
        if self.dtype in settings.supported_date_dtypes and not is_disabled:
            date_key = self.key_lookup('Calendar')
            elem_key = self.key_lookup('Element')
            accessory_layout.append(sg.CalendarButton('', key=date_key, target=elem_key, format='%Y-%m-%d',
                                                      pad=(pad_el, 0), image_data=mod_const.CALENDAR_ICON,
                                                      button_color=(text_col, bg_col), border_width=0,
                                                      tooltip='Select the date from the calendar menu'))

        aux_key = self.key_lookup('Auxiliary')
        aux_layout = [sg.pin(sg.Col([accessory_layout], key=aux_key, background_color=bg_col, visible=False))]

        # Element description and actions
        annotation = self.annotate_display()
        if annotation:
            rule = self.annotation_rules[annotation]
            desc_bg_col = rule['BackgroundColor']
            tooltip = rule['Description']
        else:
            desc_bg_col = bg_col

        desc_key = self.key_lookup('Description')
        edit_key = self.key_lookup('Edit')
        update_key = self.key_lookup('Update')
        save_key = self.key_lookup('Save')
        cancel_key = self.key_lookup('Cancel')
        bttn_vis = False if is_disabled is True else True
        description_layout = [sg.Text(self.description, key=desc_key, pad=((0, pad_h), 0), background_color=desc_bg_col,
                                      font=bold_font, auto_size_text=True, tooltip=tooltip),
                              sg.Button(image_data=mod_const.EDIT_ICON, key=edit_key, pad=((0, pad_el), 0),
                                        button_color=(text_col, bg_col), visible=bttn_vis, disabled=is_disabled,
                                        border_width=0, tooltip='Edit value'),
                              sg.pin(
                                  sg.Col([[sg.Button(image_data=mod_const.SAVE_CHANGE_ICON, key=save_key,
                                                     pad=((0, pad_el), 0), button_color=(text_col, bg_col),
                                                     border_width=0, tooltip='Save changes'),
                                           sg.Button(image_data=mod_const.CANCEL_CHANGE_ICON, key=cancel_key,
                                                     pad=((0, pad_el), 0), button_color=(text_col, bg_col),
                                                     border_width=0, tooltip='Cancel changes')
                                           ]],
                                         key=update_key, pad=(0, 0), visible=False, background_color=bg_col))]

        # Element layout
        width_key = self.key_lookup('Width')
        element_layout = [sg.Col([[sg.Canvas(key=width_key, size=(1, 0), background_color=bg_col)],
                                  self.element_layout(size=(width, 1), bg_col=bg_col, is_disabled=is_disabled)],
                                 background_color=bg_col)]

        # Layout
        row1 = icon_layout + description_layout
        row2 = element_layout + aux_layout + required_layout

        frame_key = self.key_lookup('Frame')
        layout = sg.Col([row1, row2], key=frame_key, pad=padding, background_color=bg_col, visible=(not hidden))

        return layout

    def element_layout(self, size: tuple = None, bg_col: str = None, is_disabled: bool = True):
        """
        Generate the layout for the data component of the data element.
        """
        font = mod_const.LARGE_FONT
        bg_col = mod_const.ACTION_COL if bg_col is None else bg_col
        disabled_text_col = mod_const.DISABLED_TEXT_COL

        elem_key = self.key_lookup('Element')
        display_value = self.format_display()

        layout = [sg.Text(display_value, key=elem_key, size=size, pad=(0, 0), background_color=bg_col,
                          text_color=disabled_text_col, font=font, enable_events=True, border_width=1,
                          relief='sunken', metadata={'name': self.name, 'disabled': is_disabled})]

        return layout

    def resize(self, window, size: tuple = None):
        """
        Resize the display element.
        """
        current_w, current_h = self.dimensions()
        if size:
            width, height = size
            new_h = current_h if height is None else height
            new_w = current_w if width is None else width
        else:
            new_w, new_h = (current_w, current_h)

        elem_key = self.key_lookup('Element')
        width_key = self.key_lookup('Width')
        window[width_key].set_size(size=(new_w, None))
        window[elem_key].expand(expand_x=True)

        self._dimensions = (new_w, new_h)

        return window[self.key_lookup('Frame')].get_size()

    def dimensions(self):
        """
        Return the current dimensions of the element.
        """
        return self._dimensions

    def update_display(self, window):
        """
        Format element for display.
        """
        modifiers = self.modifiers
        hidden = modifiers['hide']

        bg_col = self.bg_col if self.bg_col else mod_const.ACTION_COL
        tooltip = self.description

        elem_key = self.key_lookup('Element')
        desc_key = self.key_lookup('Description')
        frame_key = self.key_lookup('Frame')

        # Update element display value
        logger.debug('DataElement {NAME}: disabled {EDIT}; hidden {VIS}'
                     .format(NAME=self.name, EDIT=self.disabled, VIS=hidden))
        if not self.disabled and not hidden:  # element is not disabled and is visible to the user
            logger.debug("DataElement {NAME}: updating the element display"
                         .format(NAME=self.name))

            display_value = self.format_display()
            window[elem_key].update(value=display_value)
        else:  # element is either disabled or hidden
            if not pd.isna(self.value):
                display_value = self.format_display()
            else:
                logger.debug("DataElement {NAME}: no values provided to update the element's display"
                             .format(NAME=self.name))

                display_value = ''

            window[elem_key].update(value=display_value)

        # Check if the display value passes any annotations rules and update background.
        annotation = self.annotate_display(display_value)
        if annotation:
            rule = self.annotation_rules[annotation]
            bg_col = rule['BackgroundColor']
            tooltip = rule['Description']

        window[desc_key].update(background_color=bg_col)
        window[frame_key].SetTooltip(tooltip)

    def annotate_display(self, display_value=None):
        """
        Annotate the display element using configured annotation rules.
        """
        rules = self.annotation_rules

        if not display_value:
            display_value = self.format_display()

        if pd.isna(display_value) or not rules:
            return None
        else:
            display_value = settings.format_value(display_value, dtype=self.dtype)

        logger.debug('DataElement {NAME}: annotating display value on configured annotation rules'
                     .format(NAME=self.name))

        annotation = None
        for annot_code in rules:
            logger.debug('DataElement {NAME}: annotating element based on configured annotation rule "{CODE}"'
                         .format(NAME=self.name, CODE=annot_code))
            rule = rules[annot_code]
            annot_condition = rule['Condition']
            try:
                result = mod_dm.evaluate_operation({self.name: display_value}, annot_condition)
            except Exception as e:
                logger.error('DataElement {NAME}: failed to annotate element using annotation rule {CODE} - {ERR}'
                             .format(NAME=self.name, CODE=annot_code, ERR=e))
                continue

            if result:
                logger.debug('DataElement {NAME}: element value {VAL} annotated on annotation code {CODE}'
                             .format(NAME=self.name, VAL=display_value, CODE=annot_code))
                if annotation:
                    logger.warning('DataElement {NAME}: element value {VAL} has passed two or more annotation '
                                   'rules ... defaulting to the first passed "{CODE}"'
                                   .format(NAME=self.name, VAL=display_value, CODE=annotation))
                else:
                    annotation = annot_code

        return annotation

    def format_value(self, input_value):
        """
        Set the value of the data element from user input.

        Arguments:

            input_value: value input into the GUI element.
        """
        if input_value == '' or pd.isna(input_value):
            return None

        # Format the input value as the element datatype
        dtype = self.dtype
        if dtype in settings.supported_date_dtypes:
            date_format = self.date_format
            value_fmt = settings.format_as_datetime(input_value, date_format=date_format)

        elif dtype in settings.supported_float_dtypes:
            value_fmt = settings.format_as_float(input_value)

        elif dtype in settings.supported_int_dtypes:
            value_fmt = settings.format_as_int(input_value)

        elif dtype in settings.supported_bool_dtypes:
            value_fmt = settings.format_as_bool(input_value)

        else:
            try:
                value_fmt = str(input_value).strip()  # trailing newline sometimes added for multiline elements
            except ValueError:
                msg = 'failed to format the input value {VAL} as "{DTYPE}"'.format(VAL=input_value, DTYPE=self.dtype)
                logger.warning('DataElement {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                raise ValueError(msg)

        # Set the value alias, if applicable
        aliases = {j: i for i, j in self.aliases.items()}
        if value_fmt in aliases:
            value_fmt = aliases[value_fmt]

        logger.debug('DataElement {NAME}: input value "{VAL}" formatted as "{FMT}"'
                     .format(NAME=self.name, VAL=input_value, FMT=value_fmt))

        return value_fmt

    def format_display(self, editing: bool = False):
        """
        Format the elements value for displaying.
        """
        value = self.value
        if value == '' or pd.isna(value):
            return ''

        logger.debug('DataElement {NAME}: formatting display for element value {VAL} of type {TYPE}'
                     .format(NAME=self.name, VAL=value, TYPE=type(value)))

        dtype = self.dtype
        if dtype == 'money':
            dec_sep = settings.decimal_sep
            group_sep = settings.thousands_sep

            value = str(value)
            if not editing:
                display_value = settings.format_display_money(value)
            else:
                display_value = value.replace(group_sep, '').replace(dec_sep, '.')

        elif isinstance(value, float):
            display_value = str(value)

        elif isinstance(value, int):
            display_value = value

        elif isinstance(value, datetime.datetime):
            if not editing:  # use global settings to determine how to format date
                display_value = settings.format_display_date(value)  # default format is ISO
            else:  # enforce ISO formatting if element is editable
                display_value = value.strftime(settings.format_date_str(date_str=self.date_format))

        else:
            display_value = str(value).rstrip('\n\r')

        # Set display value alias, if applicable
        aliases = self.aliases
        if display_value in aliases:
            display_value = aliases[display_value]

        logger.debug('DataElement {NAME}: display value is {VAL}'
                     .format(NAME=self.name, VAL=display_value))

        return str(display_value)

    def check_requirements(self):
        """
        Verify that the record element passes requirements.
        """
        passed = True if (self.modifiers['require'] and self.has_value()) or not self.modifiers['require'] else False

        return passed

    def has_value(self):
        """
        Return True if element has a valid value else False
        """
        value = self.value
        if not pd.isna(value) and not value == '':
            return True
        else:
            return False


class DataElementInput(DataElement):
    """
    Input-style record data element.

    Attributes:

        name (str): data element configuration name.

        id (int): data element number.

        elements (list): list of data element GUI keys.

        description (str): display name of the data element.

        etype (str): GUI element type. Can be dropdown, input, multiline, reference, or checkbox

        dtype (str): element data type.

        editable (bool): element is editable. [Default: False]

        hidden (bool): element is not visible to the user. [Default: False]

        required (bool): element requires a value [Default: False].

        default: default value of the data element.

        value: value of the data element.
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

        self.etype = 'input'

    def element_layout(self, size: tuple = (20, 1), bg_col: str = None, is_disabled: bool = True):
        """
        GUI layout for the data element.
        """
        # Layout options
        font = mod_const.LARGE_FONT

        bg_col = mod_const.ACTION_COL if bg_col is None else bg_col
        disabled_bg_col = mod_const.ACTION_COL
        disabled_text_col = mod_const.DISABLED_TEXT_COL

        # Element layout
        display_value = self.format_display()
        elem_key = self.key_lookup('Element')

        layout = [sg.Input(display_value, key=elem_key, size=size, enable_events=True, font=font,
                           background_color=bg_col, text_color='black', disabled=True,
                           disabled_readonly_background_color=disabled_bg_col,
                           disabled_readonly_text_color=disabled_text_col,
                           tooltip='Input value for {}'.format(self.description),
                           metadata={'disabled': is_disabled, 'name': self.name})]

        return layout


class DataElementCombo(DataElement):
    """
    Dropdown-style record data element.

    Attributes:

        name (str): data element configuration name.

        id (int): data element number.

        elements (list): list of data element GUI keys.

        description (str): display name of the data element.

        etype (str): GUI element type. Can be dropdown, input, multiline, reference, or checkbox

        dtype (str): element data type.

        editable (bool): element is editable. [Default: False]

        hidden (bool): element is not visible to the user. [Default: False]

        required (bool): element requires a value [Default: False].

        values (list): list of available combobox values.

        alias (dict): value aliases.

        default: default value of the data element.

        value: value of the data element.
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
        if not self.dtype or self.dtype not in supported_dtypes:
            msg = 'unsupported data type provided for the "{ETYPE}" parameter. Supported data types are {DTYPES}' \
                .format(ETYPE=self.etype, DTYPES=', '.join(supported_dtypes))
            logger.warning('DataParameter {PARAM}: {MSG}'.format(PARAM=name, MSG=msg))

            self.dtype = 'varchar'

        # Dropdown values
        self.combo_values = []
        try:
            combo_values = entry['Values']
        except KeyError:
            msg = 'missing required parameter "Values" for data parameters of type "{ETYPE}"'.format(ETYPE=self.etype)
            mod_win2.popup_notice('Configuration warning: {PARAM}: {MSG}'.format(PARAM=name, MSG=msg))
            logger.warning('DataElement {PARAM}: {MSG}'.format(PARAM=name, MSG=msg))

        else:
            for combo_value in combo_values:
                try:
                    self.combo_values.append(self.format_value(combo_value))
                except ValueError:
                    msg = 'unable to format dropdown value "{VAL}" as {DTYPE}'.format(VAL=combo_value, DTYPE=self.dtype)
                    mod_win2.popup_notice('Configuration warning: {PARAM}: {MSG}'.format(PARAM=name, MSG=msg))
                    logger.warning('DataElement {PARAM}: {MSG}'.format(PARAM=name, MSG=msg))

    def element_layout(self, size: tuple = (20, 1), bg_col: str = None, is_disabled: bool = True):
        """
        GUI layout for the data element.
        """
        aliases = self.aliases

        # Layout options
        font = mod_const.LARGE_FONT

        bg_col = mod_const.ACTION_COL if bg_col is None else bg_col
        text_col = mod_const.TEXT_COL

        # Element layout
        try:
            values = self.combo_values
        except KeyError:
            logger.warning('DataElement {NAME}: dropdown was selected for the data element but no '
                           'values were provided to populate the dropdown'.format(NAME=self.name))
            display_values = []
        else:
            display_values = []
            for option in values:
                if option in aliases:
                    display_values.append(aliases[option])
                else:
                    display_values.append(option)

        display_value = self.format_display()
        elem_key = self.key_lookup('Element')
        layout = [sg.Combo(display_values, default_value=display_value, key=elem_key, size=size,
                           enable_events=True, font=font, text_color=text_col, background_color=bg_col, disabled=True,
                           tooltip='Select value from list for {}'.format(self.description),
                           metadata={'disabled': is_disabled, 'name': self.name})]

        return layout


class DataElementMultiline(DataElement):
    """
    Multiline-style record data element.

    Attributes:

        name (str): data element configuration name.

        id (int): data element number.

        elements (list): list of data element GUI keys.

        description (str): display name of the data element.

        etype (str): GUI element type. Can be dropdown, input, multiline, reference, or checkbox

        dtype (str): element data type.

        editable (bool): element is editable. [Default: False]

        hidden (bool): element is not visible to the user. [Default: False]

        required (bool): element requires a value [Default: False].

        default: default value of the data element.

        value: value of the data element.
    """

    def __init__(self, name, entry, parent=None):
        """
        Initialize the data element attributes.

        Arguments:
            name (str): data element configuration name.

            entry (dict): configuration entry for the data element.

            parent (str): name of the parent element.
        """
        super().__init__(name, entry, parent)

        self.etype = 'multiline'

        # Enforce supported data types for the dropdown parameter
        supported_dtypes = settings.supported_str_dtypes
        if self.dtype not in supported_dtypes:
            msg = 'unsupported data type provided for the "{ETYPE}" parameter. Supported data types are {DTYPES}' \
                .format(ETYPE=self.etype, DTYPES=', '.join(supported_dtypes))
            logger.warning('DataParameter {PARAM}: {MSG}'.format(PARAM=name, MSG=msg))

            self.dtype = 'varchar'

        # Number of rows to display in the multiline element
        try:
            self.nrow = int(entry['Nrow'])
        except (KeyError, ValueError):
            self.nrow = None

    def element_layout(self, size: tuple = (20, 1), bg_col: str = None, is_disabled: bool = True):
        """
        GUI layout for the data element.
        """
        # Layout options
        font = mod_const.LARGE_FONT

        disabled_text_col = mod_const.DISABLED_TEXT_COL
        bg_col = mod_const.ACTION_COL if bg_col is None else bg_col

        # Element layout
        display_value = self.format_display()
        elem_key = self.key_lookup('Element')

        height = self.nrow if self.nrow else size[1]
        width = size[0]
        layout = [sg.Multiline(display_value, key=elem_key, size=(width, height), font=font, disabled=True,
                               background_color=bg_col, text_color=disabled_text_col, border_width=1,
                               metadata={'disabled': is_disabled, 'name': self.name})]

        return layout


# Element references
class ElementReference(RecordElement):
    """
    Record element that references the values of other record elements.

    Attributes:

        name (str): data element configuration name.

        id (int): number of the element reference element.

        elements (list): list of data element GUI keys.

        description (str): display name of the element.

        etype (str): GUI element type.

        dtype (str): data type of the parameter's data storage elements. Must be an integer, float, or bool data type.

        operation (str): reference operation.

        icon (str): file name of the parameter's icon [Default: None].

        value: value of the parameter's data storage elements.

        edited (bool): element value was edited [Default: False].
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

        self.etype = 'reference'
        self.eclass = 'data'
        self.elements.extend(['-{NAME}_{ID}_{ELEM}-'.format(NAME=name, ID=self.id, ELEM=i) for i in
                              ('Description', 'Frame', 'Width')])

        # Element-specific bindings
        elem_key = self.key_lookup('Element')
        self.bindings = ['{}+LCLICK+'.format(elem_key)]

        # Data type check
        supported_dtypes = settings.supported_int_dtypes + settings.supported_float_dtypes + \
                           settings.supported_bool_dtypes
        try:
            self.dtype = entry['DataType']
        except KeyError:
            self.dtype = 'int'
        else:
            if self.dtype not in supported_dtypes:
                msg = 'unsupported data type provided for the "{ETYPE}" parameter. Supported data types are {DTYPES}' \
                    .format(ETYPE=self.etype, DTYPES=', '.join(supported_dtypes))
                logger.warning('ElementReference {NAME}: {MSG}'.format(NAME=name, MSG=msg))

                self.dtype = 'int'

        # Element modifier flags
        try:
            modifiers = entry['Modifiers']
        except KeyError:
            self.modifiers = {'require': False, 'hide': False}
        else:
            self.modifiers = {'require': modifiers.get('require', 0), 'hide': modifiers.get('hide', 0)}
            for modifier in self.modifiers:
                try:
                    flag = bool(int(self.modifiers[modifier]))
                except ValueError:
                    logger.warning('DataTable {TBL}: modifier {MOD} must be either 0 (False) or 1 (True)'
                                   .format(TBL=self.name, MOD=modifier))
                    flag = False

                self.modifiers[modifier] = flag

        # Reference parameter information
        try:
            self.operation = entry['Operation']
        except KeyError:
            msg = 'Configuration Error: ElementReference {NAME}: reference element is missing required parameter ' \
                  '"Operation".'.format(NAME=name)
            logger.error(msg)
            mod_win2.popup_error(msg)

            sys.exit(1)

        try:
            self.default = entry['DefaultValue']
        except KeyError:
            self.default = None

        # Dynamic attributes
        self._dimensions = (mod_const.DE_WIDTH, mod_const.DE_HEIGHT)

        self.value = self.default
        logger.debug('ElementReference {NAME}: initializing {ETYPE} element of data type {DTYPE} with default value '
                     '{DEF} and formatted value {VAL}'
                     .format(NAME=self.name, ETYPE=self.etype, DTYPE=self.dtype, DEF=self.default, VAL=self.value))

        self.disabled = True
        self.edited = False

    def reset(self, window):
        """
        Reset element reference value to default.
        """
        # Reset to default
        if not pd.isna(self.default) and not pd.isna(self.value):
            logger.debug('ElementReference {NAME}: resetting data element value "{VAL}" to default "{DEF}"'
                         .format(NAME=self.name, VAL=self.value, DEF=self.default))

        self.value = self.default
        self.edited = False

        # Update the parameter window element
        display_value = self.format_display()
        window[self.key_lookup('Element')].update(value=display_value)

    def run_event(self, window, event, values):
        """
        Run an element reference event.
        """
        elem_key = self.key_lookup('Element')

        if event == elem_key:
            new_value = self.format_value(values)
            if new_value != self.value:
                self.value = new_value
                self.edited = True

                self.update_display(window)

    def bind_keys(self, window):
        """
        Add hotkey bindings to the element.
        """
        elem_key = self.key_lookup('Element')
        window[elem_key].bind('<Button-1>', '+LCLICK+')

    def layout(self, padding: tuple = (0, 0), size: tuple = None, tooltip: str = None, editable: bool = True,
               overwrite: bool = False, level: int = 0):
        """
        GUI layout for the record element.
        """
        modifiers = self.modifiers

        is_disabled = False if overwrite is True or (editable is True and level < 1) else True
        self.disabled = is_disabled
        is_required = modifiers['require']
        hidden = modifiers['hide']

        size = self._dimensions if not size else size
        width, height = size
        self._dimensions = size

        background = self.bg_col
        tooltip = tooltip if tooltip else ''

        # Layout options
        pad_el = mod_const.ELEM_PAD
        pad_h = mod_const.HORZ_PAD

        font = mod_const.LARGE_FONT
        bold_font = mod_const.BOLD_HEADING_FONT

        bg_col = background
        text_col = mod_const.DISABLED_TEXT_COL

        # Element Icon, if provided
        icon = self.icon
        if icon is not None:
            icon_path = settings.get_icon_path(icon)
            if icon_path is not None:
                icon_layout = [sg.Image(filename=icon_path, pad=((0, pad_el), 0), background_color=bg_col)]
            else:
                icon_layout = []
        else:
            icon_layout = []

        # Required symbol
        if is_required is True:
            required_layout = [sg.Text('*', pad=(pad_el, 0), font=bold_font, background_color=bg_col,
                                       text_color=mod_const.NOTE_COL, tooltip='required')]
        else:
            required_layout = []

        # Element description and actions
        desc_key = self.key_lookup('Description')
        display_value = self.format_display()
        annotation = self.annotate_display(display_value)
        if annotation:
            rule = self.annotation_rules[annotation]
            desc_bg_col = rule['BackgroundColor']
            tooltip = rule['Description']
        else:
            desc_bg_col = bg_col

        description_layout = [sg.Text(self.description, key=desc_key, pad=((0, pad_h), 0), background_color=desc_bg_col,
                                      font=bold_font, auto_size_text=True, tooltip=tooltip)]

        # Element layout
        width_key = self.key_lookup('Width')
        elem_key = self.key_lookup('Element')
        element_layout = [sg.Col([[sg.Canvas(key=width_key, size=(1, 0), background_color=bg_col)],
                                  [sg.Text(display_value, key=elem_key, size=(width, 1), pad=(0, 0),
                                           background_color=bg_col, text_color=text_col, font=font, enable_events=True,
                                           border_width=1, relief='sunken',
                                           metadata={'name': self.name, 'disabled': is_disabled})]],
                                 background_color=bg_col)]

        # Layout
        row1 = icon_layout + description_layout
        row2 = element_layout + required_layout

        frame_key = self.key_lookup('Frame')
        layout = sg.Col([row1, row2], key=frame_key, pad=padding, background_color=bg_col, visible=(not hidden))

        return layout

    def resize(self, window, size: tuple = None):
        """
        Resize the display element.
        """
        current_w, current_h = self.dimensions()
        if size:
            width, height = size
            new_h = current_h if height is None else height
            new_w = current_w if width is None else width
        else:
            new_w, new_h = (current_w, current_h)

        elem_key = self.key_lookup('Element')
        width_key = self.key_lookup('Width')
        window[width_key].set_size(size=(new_w, None))
        window[elem_key].expand(expand_x=True)

        self._dimensions = (new_w, new_h)

        return window[self.key_lookup('Frame')].get_size()

    def dimensions(self):
        """
        Return the current dimensions of the element.
        """
        return self._dimensions

    def format_value(self, values):
        """
        Set the value of the element reference from user input.

        Arguments:

            values (dict): single value or dictionary of reference element values.
        """
        dtype = self.dtype

        # Update element display value
        if isinstance(values, dict):  # dictionary of referenced element values
            input_value = mod_dm.evaluate_operation(values, self.operation)
        else:  # single value provided
            input_value = values

        if input_value == '' or pd.isna(input_value):
            return None

        if dtype in settings.supported_float_dtypes:
            value_fmt = settings.format_as_float(input_value)

        elif dtype in settings.supported_int_dtypes:
            value_fmt = settings.format_as_int(input_value)

        else:  # boolean
            value_fmt = settings.format_as_bool(input_value)

        logger.debug('ElementReference {NAME}: input value "{VAL}" formatted as "{FMT}"'
                     .format(NAME=self.name, VAL=input_value, FMT=value_fmt))

        return value_fmt

    def format_display(self, **kwargs):
        """
        Format the elements value for displaying.
        """
        dtype = self.dtype
        value = self.value

        if value == '' or pd.isna(value):
            return ''

        if dtype == 'money':
            display_value = settings.format_display_money(value)
        else:
            display_value = str(value)

        return display_value

    def update_display(self, window):
        """
        Format record element for display.

        Arguments:
            window: GUI window.
        """
        bg_col = self.bg_col if self.bg_col else mod_const.ACTION_COL
        tooltip = self.description

        elem_key = self.key_lookup('Element')
        desc_key = self.key_lookup('Description')

        display_value = self.format_display()
        window[elem_key].update(value=display_value)

        # Check if the display value passes any annotations rules and update background.
        annotation = self.annotate_display(display_value)
        if annotation:
            rule = self.annotation_rules[annotation]
            bg_col = rule['BackgroundColor']
            tooltip = rule['Description']

        window[desc_key].update(background_color=bg_col)
        window[desc_key].SetTooltip(tooltip)

    def annotate_display(self, display_value=None):
        """
        Annotate the display element using configured annotation rules.
        """
        rules = self.annotation_rules

        if not display_value:
            display_value = self.format_display()

        if pd.isna(display_value) or not rules:
            return None
        else:
            display_value = settings.format_value(display_value, dtype=self.dtype)

        logger.debug('ElementReference {NAME}: annotating display value on configured annotation rules'
                     .format(NAME=self.name))

        annotation = None
        for annot_code in rules:
            logger.debug('ElementReference {NAME}: annotating element based on configured annotation rule "{CODE}"'
                         .format(NAME=self.name, CODE=annot_code))
            rule = rules[annot_code]
            annot_condition = rule['Condition']
            try:
                result = mod_dm.evaluate_operation({self.name: display_value}, annot_condition)
            except Exception as e:
                logger.error('ElementReference {NAME}: failed to annotate element using annotation rule {CODE} - {ERR}'
                             .format(NAME=self.name, CODE=annot_code, ERR=e))
                continue

            if result:
                logger.debug('ElementReference {NAME}: element value {VAL} annotated on annotation code {CODE}'
                             .format(NAME=self.name, VAL=display_value, CODE=annot_code))
                if annotation:
                    logger.warning('ElementReference {NAME}: element value {VAL} has passed two or more annotation '
                                   'rules ... defaulting to the first evaluated "{CODE}"'
                                   .format(NAME=self.name, VAL=display_value, CODE=annotation))
                else:
                    annotation = annot_code

        return annotation

    def export_values(self, edited_only: bool = False):
        """
        Export the element reference value as a dictionary.

        Arguments:
            edited_only (bool): only export element values if the element reference had been edited [Default: False].
        """
        if edited_only and not self.edited:
            return {}
        else:
            return {self.name: self.value}

    def check_requirements(self):
        """
        Verify that the record element passes requirements.
        """
        passed = True if (self.modifiers['require'] and self.has_value()) or not self.modifiers['require'] else False

        return passed

    def has_value(self):
        """
        Return True if the record element has a valid value else False
        """
        value = self.value
        if not pd.isna(value) and not value == '':
            return True
        else:
            return False