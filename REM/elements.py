"""
REM standard GUI element classes such as tables and information boxes.
"""

import datetime
import re
import sys
from random import randint

import PySimpleGUI as sg
import dateutil
import numpy as np
import pandas as pd

import REM.constants as mod_const
import REM.data_manipulation as mod_dm
import REM.database as mod_db
import REM.layouts as mod_lo
import REM.parameters as mod_param
import REM.records as mod_records
import REM.secondary as mod_win2
from REM.client import logger, settings, user


class TableElement:
    """
    Generic GUI table element.

    Attributes:

        name (str): table element configuration name.

        id (int): table element number.

        elements (list): list of table GUI element keys.

        title (str): display title.

        actions (dict): allowed table actions.

        record_type (str): table is composed of records of this type.

        columns (list): list of table columns.

        display_columns (dict): dictionary mapping display names to table column rules.

        search_field (str): column used when searching the table.

        parameters (list): list of filter parameters.

        aliases (dict): dictionary of column value aliases.

        tally_rule (str): rules used to calculate totals.

        annotation_rules (dict): rules used to annotate the data table.

        filter_rules (dict): rules used to automatically filter the data table.

        summary_rules (dict): rules used to summarize the data table.

        import_rules (dict): rules used to import records from the database.

        df (DataFrame): pandas dataframe containing table data.

        icon (str): name of the icon file containing the image to represent the table.

        nrow (int): number of rows to display.

        widths (list): list of relative column widths. If values are fractions < 1, values will be taken as percentages,
            else relative widths will be calculated relative to size of largest column.

        sort_on (list): columns to sort the table by

        row_color (str): hex code for the color of alternate rows.

        dimensions (tuple): size of the data table in pixels.

        tooltip (str): table tooltip.
    """

    def __init__(self, name, entry, parent=None):
        """
        Table attributes.

        Arguments:
            name (str): name of the configured table element.

            entry (dict): configuration entry for the table element.
        """
        self.name = name
        self.parent = parent
        self.id = randint(0, 1000000000)
        self.elements = ['-TBL_ADD-', '-TBL_DEL-', '-TBL_IMP-']
        self.elements.extend(['-{NAME}_{ID}_{ELEM}-'.format(NAME=name, ID=self.id, ELEM=i) for i in
                              ['Element', 'Import', 'Add', 'Delete', 'Export', 'Total', 'Search', 'Filter', 'Fill',
                               'FilterFrame', 'FilterButton', 'SummaryFrame', 'SummaryButton', 'Width', 'CollapseButton',
                               'CollapseFrame', 'SummaryWidth', 'Options', 'Cancel', 'Sort', 'OptionsFrame',
                               'OptionsWidth']])
        self.etype = 'table'

        try:
            self.title = entry['Title']
        except KeyError:
            self.title = name

        try:
            actions = entry['Actions']
        except KeyError:
            self.actions = {'open': False, 'edit': False, 'export': False, 'search': False, 'filter': False,
                            'import': False, 'add': False, 'delete': False, 'fill': False, 'options': False,
                            'sort': False}
        else:
            self.actions = {'open': actions.get('open', 0), 'edit': actions.get('edit', 0),
                            'export': actions.get('export', 0), 'import': actions.get('import', 0),
                            'search': actions.get('search', 0), 'filter': actions.get('filter', 0),
                            'add': actions.get('add', 0), 'delete': actions.get('delete', 0),
                            'fill': actions.get('fill', 0), 'options': actions.get('options', 0),
                            'sort': actions.get('sort', 0)}
            for action in self.actions.keys():
                try:
                    action_val = bool(int(self.actions[action]))
                except ValueError:
                    logger.warning('DataTable {TBL}: action {ACT} must be either 0 (False) or 1 (True)'
                                   .format(TBL=self.name, ACT=action))
                    action_val = False

                self.actions[action] = action_val

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
                self.columns = {i: None for i in columns}

        try:
            self.display_columns = entry['DisplayColumns']
        except KeyError:
            self.display_columns = {i: i for i in columns.keys()}

        try:
            self.record_type = entry['RecordType']
        except KeyError:
            self.record_type = None

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
                self.search_field = search_field

        try:
            params = entry['FilterParameters']
        except KeyError:
            self.parameters = []
        else:
            self.parameters = []
            for param in params:
                param_entry = params[param]

                try:
                    param_layout = param_entry['ElementType']
                except KeyError:
                    msg = 'filter parameter {PARAM} is missing the required field "{FIELD}"' \
                        .format(PARAM=param, FIELD='ElementType')
                    raise KeyError(msg)

                if param_layout == 'dropdown':
                    param_class = mod_param.DataParameterCombo
                elif param_layout == 'input':
                    param_class = mod_param.DataParameterInput
                elif param_layout == 'date':
                    param_class = mod_param.DataParameterDate
                elif param_layout == 'date_range':
                    param_class = mod_param.DataParameterDateRange
                elif param_layout == 'checkbox':
                    param_class = mod_param.DataParameterCheckbox
                else:
                    msg = 'unknown element type {TYPE} for filter parameter {PARAM}'.format(PARAM=param,
                                                                                            TYPE=param_layout)
                    raise TypeError(msg)

                try:
                    param_obj = param_class(param, param_entry)
                except Exception as e:
                    logger.warning('DataTable {NAME}: unable to add parameter to table - {ERR}'
                                   .format(NAME=name, ERR=e))
                    continue
                else:
                    if param_obj.name in self.columns:
                        self.parameters.append(param_obj)
                        self.elements += param_obj.elements
                    else:
                        logger.warning('DataTable {NAME}: filter parameters "{PARAM}" must be listed in '
                                       'the table columns'.format(NAME=name, PARAM=param))

        try:
            edit_columns = entry['EditColumns']
        except KeyError:
            self.edit_columns = {}
        else:
            self.edit_columns = {}
            for edit_column in edit_columns:
                if edit_column not in columns:
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
                    continue
                else:
                    self.defaults[default_col] = column_defaults[default_col]

        try:
            self.aliases = entry['Aliases']
        except KeyError:
            self.aliases = {}

        try:
            self.tally_rule = entry['TallyRule']
        except KeyError:
            self.tally_rule = None

        try:
            annot_rules = entry['AnnotationRules']
        except KeyError:
            self.annotation_rules = {}
        else:
            self.annotation_rules = {}
            for annot_code in annot_rules:
                annot_rule = annot_rules[annot_code]

                if 'Condition' not in annot_rule:
                    mod_win2.popup_notice('No condition set for configured annotation rule {RULE}'
                                          .format(RULE=annot_code))
                    continue

                self.annotation_rules[annot_code] = {'BackgroundColor': annot_rule.get('BackgroundColor',
                                                                                       mod_const.FAIL_COL),
                                                     'Description': annot_rule.get('Description', annot_code),
                                                     'Condition': annot_rule['Condition']}

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
                    continue

                self.summary_rules[summary_name] = {'Column': summary_rule['Column'],
                                                    'Description': summary_rule.get('Description', summary_name),
                                                    'Condition': summary_rule.get('Condition', None)}

                self.elements.append('-{NAME}_{ID}_{ELEM}-'.format(NAME=self.name, ID=self.id, ELEM=summary_name))

        try:
            self.import_rules = entry['ImportRules']
        except KeyError:
            self.import_rules = None

        try:
            self.id_column = entry['IDColumn']
        except KeyError:
            self.id_column = 'RecordID'

        try:
            self.date_column = entry['DateColumn']
        except KeyError:
            self.date_column = 'RecordDate'

        try:
            self.deleted_column = entry['DeletedColumn']
        except KeyError:
            self.deleted_column = 'RowDeleted'
        if self.deleted_column not in self.columns:
            self.columns[self.deleted_column] = 'bool'

        try:
            self.icon = entry['Icon']
        except KeyError:
            self.icon = None

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
            self.nrow = None
        except ValueError:
            logger.warning('DataTable {TBL}: input to the Rows parameter must be an integer value'
                           .format(TBL=self.name))
            self.nrow = None

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
            self.tooltip = entry['Tooltip']
        except KeyError:
            self.tooltip = None

        try:
            self.required_columns = entry['RequiredColumns']
        except KeyError:
            self.required_columns = []

        try:
            required = bool(int(entry['IsRequired']))
        except KeyError:
            self.required = False
        except ValueError:
            logger.warning('DataElement {NAME}: "IsRequired" must be either 0 (False) or 1 (True)'
                           .format(NAME=name))
            sys.exit(1)
        else:
            self.required = required

        self.dimensions = (mod_const.TBL_WIDTH_PX, mod_const.TBL_ROW_HEIGHT)

        self.df = self.set_datatypes(pd.DataFrame(columns=list(self.columns)))
        self.import_df = self.set_datatypes(pd.DataFrame(columns=list(self.columns)))
        self.index_map = {}

    def key_lookup(self, component):
        """
        Lookup a component's GUI element key using the component's name.
        """
        element_names = [i[1:-1].split('_')[-1] for i in self.elements]
        if component in element_names:
            key_index = element_names.index(component)
            key = self.elements[key_index]
        else:
            logger.warning('DataTable {NAME}: component {COMP} not found in list of element components'
                           .format(NAME=self.name, COMP=component))
            key = None

        return key

    def reset(self, window):
        """
        Reset data table to default.
        """
        columns = list(self.columns)

        self.df = self.set_datatypes(pd.DataFrame(columns=columns))
        self.import_df = self.set_datatypes(pd.DataFrame(columns=columns))

        self.update_display(window)

    def fetch_parameter(self, element, by_key: bool = False):
        """
        Fetch a GUI parameter element by name or event key.
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

    def data(self, deleted: bool = False):
        """
        Return the table dataframe.
        """
        if deleted:
            df = self.df.copy()
        else:
            df = self._filter_deleted(self.df.copy())

        return df

    def run_event(self, window, event, values):
        """
        Perform a table action.
        """
        tbl_key = self.key_lookup('Element')
        options_key = self.key_lookup('Options')
        frame_key = self.key_lookup('OptionsFrame')
        cancel_key = self.key_lookup('Cancel')
        sort_key = self.key_lookup('Sort')
        fill_key = self.key_lookup('Fill')
        export_key = self.key_lookup('Export')
        filter_key = self.key_lookup('Filter')
        add_key = self.key_lookup('Add')
        delete_key = self.key_lookup('Delete')
        import_key = self.key_lookup('Import')

        param_elems = [i for param in self.parameters for i in param.elements]

        # Row click event
        if event == tbl_key:
            # Close options panel, if open
            if window[frame_key].metadata['visible'] is True:
                window[frame_key].metadata['visible'] = False
                window[frame_key].update(visible=False)
                self.resize(window, size=self.dimensions)

            # Find row selected by user
            try:
                select_row_index = values[event][0]
            except IndexError:  # user double-clicked too quickly
                msg = 'table row could not be selected'
                logger.debug('DataTable {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
            else:
                # Get the real index of the selected row
                try:
                    index = self.index_map[select_row_index]
                except KeyError:
                    index = select_row_index

                logger.debug('DataTable {NAME}: opening record at real index {IND}'.format(NAME=self.name, IND=index))
                if self.actions['open'] is True:
                    self.df = self.export_row(index)
                elif self.actions['open'] is False and self.actions['edit'] is True:
                    self.edit_row(index)

        elif event == self.key_lookup('CollapseButton'):
            self.collapse_expand(window)

        elif event == self.key_lookup('FilterButton'):
            self.collapse_expand(window, frame='filter')

        elif event == self.key_lookup('SummaryButton'):
            self.collapse_expand(window, frame='summary')

        # Click filter Apply button to apply filtering to table
        elif event == filter_key or event == '-HK_TBL_FILTER-':
            # Update parameter values
            for param in self.parameters:
                param.value = param.format_value(values)

        # Click to open table options panel
        elif event == options_key or event == '-HK_TBL_OPTS-':
            if window[frame_key].metadata['visible'] is False:
                window[frame_key].metadata['visible'] = True

                tbl_width, tbl_height = window[tbl_key].get_size()

                # Reveal the options panel
                window[tbl_key].update(visible=False)
                window[frame_key].update(visible=True)
                window[frame_key].expand(expand_row=True, expand_y=True, expand_x=True)
                window.refresh()

                frame_w, frame_h = window[frame_key].get_size()

                # Reduce table size
                columns = self.display_columns
                header = list(columns.keys())
                new_width = tbl_width - frame_w - 2 if tbl_width - frame_w - 2 > 0 else 0
                logger.debug('DataTable {NAME}: resizing the table from {W} to {NW} to accommodate the options frame '
                             'of width {F}'.format(NAME=self.name, W=tbl_width, NW=new_width, F=frame_w))
                lengths = self._calc_column_widths(width=new_width, pixels=True)
                for col_index, col_name in enumerate(header):
                    col_width = lengths[col_index]
                    window[tbl_key].Widget.column(col_name, width=col_width)

                # Reveal the table frame
                window[tbl_key].update(visible=True)
            else:
                self.resize(window, size=self.dimensions)

        elif event == cancel_key:
            self.resize(window, size=self.dimensions)

        # Sort column selected from menu of sort columns
        elif event == sort_key:
            sort_on = self.sort_on
            display_map = self.display_columns

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

        # NA value fill method selected from menu of fill methods
        elif event == fill_key:
            display_map = self.display_columns

            # Get selected rows, if any
            select_row_indices = values[tbl_key]

            # Get the real indices of the selected rows
            try:
                indices = [self.index_map[i] for i in select_row_indices]
            except KeyError:
                msg = 'missing index information for one or more rows selected for deletion'.format(NAME=self.name)
                logger.warning('DataTable {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
                mod_win2.popup_notice(msg)
                indices = []

            # Find selected fill method
            display_col = values[fill_key]
            try:
                fill_col = display_map[display_col]
            except KeyError:
                logger.warning('DataTable {NAME}: fill display column {COL} must have a one-to-one '
                               'mapping with a table column to sort'.format(NAME=self.name, COL=display_col))
            else:
                # Fill in NA values
                self.fill(fill_col, rows=indices)

        elif event in param_elems:
            try:
                param = self.fetch_parameter(event, by_key=True)
            except KeyError:
                logger.error('DataTable {TBL}: unable to find parameter associated with event key {KEY}'
                             .format(TBL=self.name, KEY=event))
            else:
                param.run_event(window, event, values)

        elif event == add_key or (event == '-HK_TBL_ADD-' and (not window[add_key].metadata['disabled'] and
                                                            window[add_key].metadata['visible'])):
            self.add_row()

        elif event == delete_key or (event == '-HK_TBL_DEL-' and (not window[delete_key].metadata['disabled'] and
                                                               window[delete_key].metadata['visible'])):
            # Find rows selected by user for deletion
            select_row_indices = values[tbl_key]

            # Get the real indices of the selected rows
            try:
                indices = [self.index_map[i] for i in select_row_indices]
            except KeyError:
                msg = 'missing index information for one or more rows selected for deletion'.format(NAME=self.name)
                logger.warning('DataTable {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
                mod_win2.popup_notice(msg)
                indices = []

            self.delete_rows(indices)

        elif event == import_key or (event == '-HK_TBL_IMPORT-' and (not window[import_key].metadata['disabled'] and
                                                               window[import_key].metadata['visible'])):
            self.import_rows()

        elif event == export_key:
            export_df = self.update_display(window, values)
            annotations = self.annotate_display(self.df)
            annotation_map = {i: self.annotation_rules[j]['BackgroundColor'] for i, j in annotations.items()}
            self.export_table(export_df, annotation_map)

        result = self.update_display(window, values)

        return result

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

    def update_display(self, window, window_values: dict = None):
        """
        Format object elements for display.
        """
        is_float_dtype = pd.api.types.is_float_dtype
        highlight_col = mod_const.SELECT_BG_COL
        white_text_col = mod_const.WHITE_TEXT_COL
        def_bg_col = mod_const.ACTION_COL
        text_col = mod_const.TEXT_COL

        # Sort table and update table sorting information
        sort_key = self.key_lookup('Sort')
        display_map = self.display_columns
        search_field = self.search_field

        # Modify records tables for displaying
        logger.debug('DataTable {TBL}: formatting table for displaying'.format(TBL=self.name))

        self.sort(self.sort_on)

        if self.actions['sort'] is True:
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
        if search_field is not None and window_values is not None:
            search_key = self.key_lookup('Search')
            try:
                search_value = window_values[search_key]
            except KeyError:
                msg = 'DataTable {NAME}: search field key {KEY} not found in list of window GUI elements'\
                    .format(NAME=self.name, KEY=search_key)
                logger.warning(msg)
                search_value = None
        else:
            search_value = None

        if not search_value:  # no search value provided in the search field, try the filter parameters
            df = self._apply_filter()
        else:
            df = self.data()
            try:
                df = df[df[search_field] == search_value]
            except KeyError:
                msg = 'DataTable {NAME}: search field {COL} not found in list of table columns'\
                    .format(NAME=self.name, COL=search_field)
                logger.warning(msg)

        # Edit the index map to reflect what is currently displayed
        self.index_map = {i: j for i, j in enumerate(df.index.tolist())}

        df = df.reset_index()

        # Highlight table rows using configured annotation rules
        annotations = self.annotate_display(df)
        row_colors = [(i, self.annotation_rules[j]['BackgroundColor']) for i, j in annotations.items()]

        # Format the table
        display_df = self.format_display_table(df)

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
            logger.debug('DataTable {NAME}: table totals "{TOT}" are formatted as float'
                         .format(NAME=self.name, TOT=tbl_total))
            tbl_total = '{:,.2f}'.format(tbl_total)
        else:
            logger.debug('DataTable {NAME}: table totals "{TOT}" are formatted as a string'
                         .format(NAME=self.name, TOT=tbl_total))
            tbl_total = str(tbl_total)

        total_key = self.key_lookup('Total')
        window[total_key].update(value=tbl_total)

        # Update the table summary
        summary = self.summarize_table(df)
        for summary_item in summary:
            summ_rule, summ_value = summary_item
            if isinstance(summ_value, float):
                summ_value = '{:,.2f}'.format(summ_value)

            summ_key = self.key_lookup(summ_rule)
            window[summ_key].update(value=summ_value)

        return display_df

    def format_display_table(self, df, date_fmt: str = None):
        """
        Format the table for display.
        """
        relativedelta = dateutil.relativedelta.relativedelta
        strptime = datetime.datetime.strptime
        is_float_dtype = pd.api.types.is_float_dtype
        is_integer_dtype = pd.api.types.is_integer_dtype
        is_bool_dtype = pd.api.types.is_bool_dtype
        is_datetime_dtype = pd.api.types.is_datetime64_any_dtype
        is_string_dtype = pd.api.types.is_string_dtype

        display_map = self.display_columns
        aliases = self.aliases

        # Set display parameters
        date_fmt = date_fmt if date_fmt is not None else settings.format_date_str(date_str=settings.display_date_format)

        display_header = list(display_map.keys())

        # Localization specific options
        date_offset = settings.get_date_offset()

        display_df = pd.DataFrame()

        # Subset dataframe by specified columns to display
        for col_name in display_map:
            col_rule = display_map[col_name]

            try:
                col_to_add = mod_dm.generate_column_from_rule(df, col_rule)
            except Exception as e:
                logger.error('DataTable {TBL}: unable to generate column from display rule {RULE} - {ERR}'
                             .format(TBL=self.name, RULE=col_rule, ERR=e))
                continue

            dtype = col_to_add.dtype
            if is_float_dtype(dtype):
                col_to_add = col_to_add.apply('{:,.2f}'.format)
            elif is_datetime_dtype(dtype):
                col_to_add = col_to_add.apply(lambda x: (strptime(x.strftime(date_fmt), date_fmt) +
                                                         relativedelta(years=+date_offset)).strftime(date_fmt)
                if pd.notnull(x) else '')
            elif is_string_dtype(dtype):
                col_to_add = col_to_add.fillna('')

            display_df[col_name] = col_to_add

        # Map column values to the aliases specified in the configuration
        for alias_col in aliases:
            alias_map = aliases[alias_col]  # dictionary of mapped values
            if alias_col not in display_header:
                logger.warning('DataTable {TBL}: alias column {ALIAS} not found in the list of display columns'
                               .format(TBL=self.name, ALIAS=alias_col))
                continue

            try:
                col_dtype = display_df[alias_col].dtype
                if is_integer_dtype(col_dtype):  # convert integer-type alias keys to integer values
                    alias_map = {int(i): j for i, j in alias_map.items()}
                elif is_bool_dtype(col_dtype):  # convert boolean-type alias keys to boolean values
                    alias_map = {bool(i): j for i, j in alias_map.items()}
            except KeyError:
                logger.warning('DataTable {TBL}: alias {ALIAS} not found in the list of display columns'
                               .format(TBL=self.name, ALIAS=alias_col))
            except ValueError:
                logger.warning('DataTable {TBL}: aliases provided to column {ALIAS} does not match data type {DTYPE} '
                               'of the column'.format(TBL=self.name, ALIAS=alias_col, DTYPE=col_dtype))
            else:
                try:
                    display_df[alias_col] = display_df[alias_col].apply(lambda x: alias_map[x] if x in alias_map else x)
                except TypeError:
                    logger.warning('DataTable {TBL}: cannot replace values for column {ALIAS} with their aliases as '
                                   'alias values are not of the same data type'.format(TBL=self.name, ALIAS=alias_col))

        return display_df.astype('object').fillna('')

    def format_display_column(self, df, colname, date_fmt: str = None):
        """
        Format a specific column for displaying.
        """
        relativedelta = dateutil.relativedelta.relativedelta
        strptime = datetime.datetime.strptime
        is_float_dtype = pd.api.types.is_float_dtype
        is_integer_dtype = pd.api.types.is_integer_dtype
        is_bool_dtype = pd.api.types.is_bool_dtype
        is_datetime_dtype = pd.api.types.is_datetime64_any_dtype
        is_string_dtype = pd.api.types.is_string_dtype

        display_map = {j: i for i, j in self.display_columns.items()}
        aliases = self.aliases

        date_fmt = date_fmt if date_fmt is not None else settings.format_date_str(date_str=settings.display_date_format)
        date_offset = settings.get_date_offset()

        try:
            display_col = df[colname]
        except KeyError:
            logger.error('DataTable {TBL}: column {COL} not found in the table columns'
                         .format(TBL=self.name, COL=colname))

            raise

        if colname in display_map:
            display_name = display_map[colname]
            if display_name in aliases:
                alias_map = aliases[display_name]  # dictionary of mapped values
            else:
                alias_map = {}
        else:
            alias_map = {}

        dtype = display_col.dtype
        if is_float_dtype(dtype):
            display_col = display_col.apply('{:,.2f}'.format)
        elif is_datetime_dtype(dtype):
            display_col = display_col.apply(lambda x: (strptime(x.strftime(date_fmt), date_fmt) +
                relativedelta(years=+date_offset)).strftime(date_fmt) if pd.notnull(x) else '')
        elif is_bool_dtype(dtype):
            try:
                alias_map = {bool(i): j for i, j in alias_map.items()}
            except ValueError:
                logger.warning('DataTable {TBL}: aliases provided to column {COL} does not match data type {DTYPE} '
                               'of the column'.format(TBL=self.name, COL=colname, DTYPE=dtype))
        elif is_integer_dtype(dtype):
            try:
                alias_map = {int(i): j for i, j in alias_map.items()}
            except ValueError:
                logger.warning('DataTable {TBL}: aliases provided to column {COL} does not match data type {DTYPE} '
                               'of the column'.format(TBL=self.name, COL=colname, DTYPE=dtype))

        try:
            display_col = display_col.apply(lambda x: alias_map[x] if x in alias_map else x)
        except TypeError:
            logger.warning('DataTable {TBL}: cannot replace values for column {COL} with their aliases as '
                           'alias values are not of the same data type'.format(TBL=self.name, COL=colname))

        return display_col.fillna('')

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

    def summarize_column(self, colname, df: pd.DataFrame = None):
        """
        Summarize a table column.
        """
        is_numeric_dtype = pd.api.types.is_numeric_dtype
        is_string_dtype = pd.api.types.is_string_dtype
        is_datetime_dtype = pd.api.types.is_datetime64_any_dtype
        is_bool_dtype = pd.api.types.is_bool_dtype

        df = df if df is not None else self.data()

        logger.debug('DataTable {NAME}: summarizing column {COL}'.format(NAME=self.name, COL=colname))

        try:
            col_values = df[colname]
        except KeyError:
            logger.error('DataTable {NAME}: missing table column "{COL}" from the dataframe'
                         .format(NAME=self.name, COL=colname))

            raise

        dtype = col_values.dtype
        if is_numeric_dtype(dtype) or is_bool_dtype(dtype):
            col_summary = col_values.sum()
        elif is_string_dtype(dtype) or is_datetime_dtype(dtype):
            col_summary = col_values.nunique()
        else:  # possibly empty dataframe
            col_summary = 0

        return col_summary

    def summarize_table(self, df: pd.DataFrame = None):
        """
        Update Summary element with data summary
        """
#        is_numeric_dtype = pd.api.types.is_numeric_dtype
#        is_string_dtype = pd.api.types.is_string_dtype
#        is_datetime_dtype = pd.api.types.is_datetime64_any_dtype
#        is_bool_dtype = pd.api.types.is_bool_dtype

        operators = set('+-*/')

        df = df if df is not None else self.data()

        logger.debug('DataTable {NAME}: summarizing display table on configured summary rules'.format(NAME=self.name))

        # Calculate totals defined by summary rules
        outputs = []
        summ_rules = self.summary_rules
        for rule_name in summ_rules:
            summ_rule = summ_rules[rule_name]

            logger.debug('DataTable {NAME}: summarizing display table on configured summary rule "{RULE}"'
                         .format(NAME=self.name, RULE=summ_rule))

            column = summ_rule['Column']

            # Subset df if subset rule provided
            condition = summ_rule['Condition']
            if condition is not None:
                try:
                    subset_df = self.subset(summ_rule['Condition'])
                except Exception as e:
                    logger.warning('DataTable {NAME}: unable to subset dataframe with subset rule {SUB} - {ERR}'
                                   .format(NAME=self.name, SUB=summ_rule['Subset'], ERR=e))
                    break
            else:
                subset_df = df

            rule_values = []
            for component in mod_dm.parse_operation_string(column):
                if component in operators:
                    rule_values.append(component)
                    continue

                if component in self.columns:  # component is header column
                    col_summary = self.summarize_column(component, df=subset_df)
#                    try:
#                        dtype = subset_df.dtypes[component]
#                    except KeyError:
#                        logger.error('DataTable {NAME}: missing table column "{COL}" from the subsetted dataframe'
#                                     .format(NAME=self.name, COL=component))
#                        raise
#                    if is_numeric_dtype(dtype) or is_bool_dtype(dtype):
#                        col_summary = subset_df[component].sum()
#                    elif is_string_dtype(dtype) or is_datetime_dtype(dtype):
#                        col_summary = subset_df[component].nunique()
#                    else:  # possibly empty dataframe
#                        col_summary = 0

                    rule_values.append(col_summary)
                else:
                    try:  # component is a number
                        float(component)
                    except ValueError:  # component is an unsupported character
                        logger.warning('DataTable {NAME}: unsupported character "{ITEM}" found in summary rule '
                                       '"{SUMM}"'.format(NAME=self.name, ITEM=component, SUMM=rule_name))
                        rule_values = [0]
                        break
                    else:
                        rule_values.append(component)

            summary_total = eval(' '.join([str(i) for i in rule_values]))
            outputs.append((rule_name, summary_total))

        return outputs

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
#            param_value = param.value
#            match_pattern = param.pattern_matching
#            dtype = param.dtype
#            column = param.name
#
#            try:
#                if dtype in settings.supported_date_dtypes:
#                    col_values = pd.to_datetime(df[column], errors='coerce', format=settings.date_format)
#                elif dtype in settings.supported_int_dtypes:
#                    col_values = pd.to_numeric(df[column].fillna(0), errors='coerce', downcast='integer')
#                elif dtype in settings.supported_float_dtypes:
#                    col_values = pd.to_numeric(df[column], errors='coerce')
#                elif dtype in settings.supported_bool_dtypes:
#                    col_values = df[column].fillna(False).astype(np.bool, errors='raise')
#                else:
#                    col_values = df[column].astype(np.object, errors='raise')
#            except Exception as e:
#                logger.error('DataTable {NAME}: unable to set column {COL} to parameter data type {DTYPE} - {ERR}'
#                             .format(NAME=self.name, COL=column, DTYPE=dtype, ERR=e))
#                col_values = df[column]
#
#            if isinstance(param_value, tuple) or isinstance(param_value, list):  # parameter is range element
#                try:
#                    from_value, to_value = param_value
#                except ValueError:
#                    logger.error('DataTable {NAME}: ranged parameter {PARAM} requires exactly two values'
#                                 .format(NAME=self.name, PARAM=param.name))
#                    continue
#
#                if from_value not in (None, '') and to_value not in (None, ''):  # select rows in range
#                    logger.debug('DataTable {NAME}: filtering table on parameter {PARAM} values {VAL1} and {VAL2}'
#                                 .format(NAME=self.name, PARAM=param.name, VAL1=from_value, VAL2=to_value))
#                    try:
#                        df = df[(col_values >= from_value) & (col_values <= to_value)]
#                    except KeyError:
#                        logger.warning('DataTable {TBL}: filter parameter {PARAM} not found in the table header'
#                                       .format(TBL=self.name, PARAM=column))
#                        continue
#                    except SyntaxError:
#                        logger.warning('DataTable {TBL}: unable to filter table on parameter {PARAM} values '
#                                       '{VAL1} and {VAL2}'
#                                       .format(TBL=self.name, PARAM=param.name, VAL1=from_value, VAL2=to_value))
#                elif from_value not in (None, '') and to_value in (None, ''):  # rows equal to from component
#                    logger.debug('DataTable {NAME}: filtering table on parameter {PARAM} value {VAL}'
#                                 .format(NAME=self.name, PARAM=param.name, VAL=from_value))
#                    try:
#                        df = df[col_values == from_value]
#                    except KeyError:
#                        logger.warning('DataTable {TBL}: filter parameter {PARAM} not found in the table header'
#                                       .format(TBL=self.name, PARAM=column))
#                        continue
#                    except SyntaxError:
#                        logger.warning('DataTable {TBL}: unable to filter table on parameter {PARAM} value '
#                                       '{VAL},'.format(TBL=self.name, PARAM=column, VAL=from_value))
#                elif to_value not in (None, '') and from_value in (None, ''):  # rows equal to the to component
#                    logger.debug('DataTable {NAME}: filtering table on parameter {PARAM} value {VAL}'
#                                 .format(NAME=self.name, PARAM=param.name, VAL=to_value))
#                    try:
#                        df = df[col_values == to_value]
#                    except KeyError:
#                        logger.warning('DataTable {TBL}: filter parameter {PARAM} not found in the table header'
#                                       .format(TBL=self.name, PARAM=column))
#                        continue
#                    except SyntaxError:
#                        logger.warning('DataTable {TBL}: unable to filter table on parameter {PARAM} value '
#                                       '{VAL}'.format(TBL=self.name, PARAM=column, VAL=to_value))
#            else:  # parameter is a single element
#                if not param_value:
#                    continue
#
#                logger.debug('DataTable {NAME}: filtering table on parameter {PARAM} value {VAL}'
#                             .format(NAME=self.name, PARAM=param.name, VAL=param_value))
#
#                if match_pattern is True:
#                    df = df[col_values.str.contains(param_value, case=False, regex=True)]
#                else:
#                    df = df[col_values == param_value]

        return df

    def annotate_display(self, df):
        """
        Annotate the display table using configured annotation rules.
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

#            logger.debug('DataTable {NAME}: annotation results of rule {RULE} are {RES}'
#                         .format(NAME=self.name, RULE=annot_code, RES=list(results)))
            for row_index, result in results.iteritems():
                if result:
                    logger.debug('DataTable {NAME}: table row {ROW} annotated on annotation code {CODE}'
                                 .format(NAME=self.name, ROW=row_index, CODE=annot_code))
                    if row_index in rows_annotated:
                        logger.warning('DataTable {NAME}: table row {ROW} has passed two or more annotation rules ... '
                                       'defaulting to the first configured'.format(NAME=self.name, ROW=row_index))
                    else:
                        annotations[row_index] = annot_code
                        rows_annotated.append(row_index)

        return annotations

    def layout(self, tooltip: str = None, nrow: int = None, height: int = None, width: int = None, font: tuple = None,
               padding: tuple = None, collapsible: bool = False, editable: bool = True, overwrite_edit: bool = False):
        """
        Create table elements that have consistency in layout.
        """
        table_name = self.title
        df = self.df
        display_df = self.format_display_table(df)

        tooltip = tooltip if tooltip is not None else self.tooltip

        disabled = True if editable is False and overwrite_edit is False else False

        # Element keys
        keyname = self.key_lookup('Element')
        import_key = self.key_lookup('Import')
        add_key = self.key_lookup('Add')
        delete_key = self.key_lookup('Delete')
        print_key = self.key_lookup('Export')
        search_key = self.key_lookup('Search')
        total_key = self.key_lookup('Total')
        fill_key = self.key_lookup('Fill')
        cancel_key = self.key_lookup('Cancel')
        options_key = self.key_lookup('Options')
        sort_key = self.key_lookup('Sort')

        # Element settings
        text_col = mod_const.TEXT_COL  # standard text color
        select_text_col = mod_const.WHITE_TEXT_COL  # row text highlight color
        select_bg_col = mod_const.TBL_SELECT_COL
        disabled_text_col = mod_const.DISABLED_TEXT_COL  # disabled button text
        disabled_bg_col = mod_const.INACTIVE_COL  # disabled button background
        alt_col = self.row_color  # alternate row color
        bg_col = mod_const.TBL_BG_COL  # primary table color is white
        header_col = mod_const.TBL_HEADER_COL  # color of the header background
        filter_bg_col = mod_const.DEFAULT_COL  # color of the filter parameter background
        filter_head_col = mod_const.BORDER_COL  # color of filter header and selected row background

        pad_frame = mod_const.FRAME_PAD

        pad = padding if padding and isinstance(padding, tuple) else (pad_frame, pad_frame)
        pad_el = mod_const.ELEM_PAD
        pad_h = mod_const.HORZ_PAD
        pad_v = mod_const.VERT_PAD

        font = font if font else mod_const.LARGE_FONT
        bold_font = mod_const.BOLD_FONT
        bold_l_font = mod_const.BOLD_HEADER_FONT
        font_size = font[1]

        # Hotkey text
        hotkeys = settings.hotkeys
        add_shortcut = hotkeys['-HK_TBL_ADD-'][2]
        delete_shortcut = hotkeys['-HK_TBL_DEL-'][2]
        import_shortcut = hotkeys['-HK_TBL_IMPORT-'][2]
        options_shortcut = hotkeys['-HK_TBL_OPTS-'][2]
        filter_shortcut = hotkeys['-HK_TBL_FILTER-'][2]

        # Table dimensions
        row_height = mod_const.TBL_ROW_HEIGHT
        if nrow:
            nrow = nrow
        elif nrow is None and height is not None:
            # Expand 1 row every N-pixel increase in window size
            initial_nrow = self.nrow if self.nrow is not None else mod_const.TBL_NROW
            height_diff = int((height - mod_const.WIN_HEIGHT) / 40)
            nrow = initial_nrow + height_diff if height_diff > -initial_nrow else 1
        else:
            nrow = self.nrow if self.nrow is not None else mod_const.TBL_NROW

        width = width if width is not None else mod_const.TBL_WIDTH

        isize = mod_const.IN1_SIZE

        header_col_size = 200
        option_col_size = 40

        # Row layouts

        # Table filters
        filter_params = self.parameters
        use_center = True
        if len(filter_params) <= 2 or len(filter_params) == 4:
            use_center = False

        left_cols = []
        center_cols = []
        right_cols = []
        left_sizes = []

        i = 0
        for parameter in filter_params:
            param_cols = parameter.layout(padding=(0, pad_el * 2), size=(14, 1), bg_col=filter_bg_col)
            for param_layout in param_cols:
                i += 1
                if use_center is True:
                    index_mod = i % 3
                else:
                    index_mod = i % 2

                if use_center is True and index_mod == 1:
                    left_cols.append([param_layout])
                    left_sizes.append(len(parameter.description))
                elif use_center is True and index_mod == 2:
                    center_cols.append([param_layout])
                elif use_center is True and index_mod == 0:
                    right_cols.append([param_layout])
                elif use_center is False and index_mod == 1:
                    left_sizes.append(len(parameter.description))
                    left_cols.append([param_layout])
                    center_cols.append([sg.Canvas(size=(0, 0), visible=True)])
                elif use_center is False and index_mod == 0:
                    right_cols.append([param_layout])
                else:
                    logger.warning('DataTable {NAME}: cannot assign layout for table filter parameter {PARAM}'
                                   .format(NAME=self.name, PARAM=parameter.name))

        if len(right_cols) < 1:
            right_cols.append([sg.Col([[sg.Canvas(size=(0, 0), background_color=filter_bg_col)]],
                                      background_color=filter_bg_col, expand_x=True)])
        if len(left_cols) < 1:
            left_cols.append([sg.Col([[sg.Canvas(size=(0, 0), background_color=filter_bg_col)]],
                                     background_color=filter_bg_col, expand_x=True)])
        if len(center_cols) < 1:
            center_cols.append([])

        filters = [[sg.Frame('', [
            [sg.Canvas(size=(width / 13, 0), key=self.key_lookup('Width'), background_color=alt_col)],
            [sg.Col(left_cols, pad=(0, 0), background_color=filter_bg_col, justification='l',
                    element_justification='r', vertical_alignment='t', expand_x=True),
             sg.Col(center_cols, pad=(0, 0), background_color=filter_bg_col, justification='c',
                    element_justification='c', vertical_alignment='t', expand_x=True),
             sg.Col(right_cols, pad=(0, 0), background_color=filter_bg_col, justification='r',
                    element_justification='l', vertical_alignment='t', expand_x=True)],
            [sg.Col([[mod_lo.B2('Apply', key=self.key_lookup('Filter'), pad=(0, (0, pad_h)), disabled=disabled,
                                button_color=(alt_col, filter_head_col),
                                disabled_button_color=(disabled_text_col, disabled_bg_col),
                                tooltip='Apply table filters ({})'.format(filter_shortcut))]],
                    element_justification='c', background_color=filter_bg_col, expand_x=True)]],
                             border_width=1, background_color=filter_bg_col)]]

        if len(filter_params) > 0 and self.actions['filter'] is True:
            visible_filter = True
        else:
            visible_filter = False

        row1 = [
            sg.Col([[sg.Image(data=mod_const.FILTER_ICON, pad=((0, pad_h), 0), background_color=filter_head_col),
                     sg.Text('Table filters', pad=((0, pad_h), 0), text_color=select_text_col,
                             background_color=filter_head_col),
                     sg.Button('', image_data=mod_const.HIDE_ICON, key=self.key_lookup('FilterButton'),
                               button_color=(text_col, filter_head_col), border_width=0,
                               tooltip='Hide / reveal table filter parameters')]],
                   pad=(0, 0), element_justification='c', background_color=filter_head_col, expand_x=True,
                   visible=visible_filter)]
        row2 = [sg.pin(sg.Col(filters, key=self.key_lookup('FilterFrame'), background_color=filter_bg_col,
                              visible=visible_filter, expand_x=True, metadata={'visible': visible_filter}))]

        # Table title
        row3 = []
        if self.actions['search'] is True and self.search_field is not None:
            row3.append(sg.Col([
                [sg.Frame('', [[sg.Image(data=mod_const.SEARCH_ICON, background_color=bg_col, pad=((0, pad_h), 0)),
                                sg.Input(default_text='', key=search_key, size=(isize - 2, 1),
                                         border_width=0, do_not_clear=True, background_color=bg_col,
                                         enable_events=True, tooltip='Search table')]],
                          background_color=bg_col, pad=(pad_el, int(pad_el / 2)), relief='sunken')],
                [sg.Canvas(size=(header_col_size, 0), background_color=header_col)]],
                justification='l', background_color=header_col))
        else:
            row3.append(sg.Col([[sg.Canvas(size=(header_col_size, 0), background_color=header_col)]],
                               justification='l', element_justification='l', background_color=header_col))

        if self.title is not None:
            row3.append(sg.Col([[sg.Text(table_name, pad=(pad_el, int(pad_el / 2)), font=bold_font,
                                         background_color=header_col)]], expand_x=True,
                               justification='c', element_justification='c', background_color=header_col))
        else:
            row3.append(sg.Col([[sg.Canvas(size=(0, 0), background_color=header_col)]],
                               justification='c', background_color=header_col, expand_x=True))

        if self.actions['options'] is True:
            row3.append(sg.Col([
                [sg.Canvas(size=(header_col_size, 0), background_color=header_col)],
                [sg.Button('', key=options_key, image_data=mod_const.OPTIONS_ICON, border_width=0,
                           button_color=(text_col, header_col),
                           tooltip='Show additional table options ({})'.format(options_shortcut))]],
                pad=((pad_el, pad_el), int(pad_el / 2)), justification='r', element_justification='r',
                background_color=header_col, vertical_alignment='c'))
        else:
            row3.append(sg.Col([[sg.Canvas(size=(header_col_size, 0), background_color=header_col)]],
                               justification='r', element_justification='r', background_color=header_col))

        # Data table
        row4 = []
        header = display_df.columns.values.tolist()
        data = display_df.values.tolist()
        bind = True if (self.actions['edit'] is True or self.actions['open'] is True) and editable is True else False
        events = False

        col_widths = self._calc_column_widths(width=width - 16, size=font_size, pixels=False)
        row4.append(sg.Table(data, key=keyname, headings=header, pad=(0, 0), num_rows=nrow,
                             row_height=row_height, alternating_row_color=alt_col, background_color=bg_col,
                             text_color=text_col, selected_row_colors=(select_text_col, select_bg_col), font=font,
                             display_row_numbers=False, auto_size_columns=False, col_widths=col_widths,
                             enable_events=events, bind_return_key=bind, tooltip=tooltip, vertical_scroll_only=False,
                             metadata={'events': events, 'bind': bind, 'disabled': False, 'visible': True,
                                       'nrow': nrow}))

        # Table options
        options = [
            [sg.Col([[sg.Col([[sg.Canvas(size=(option_col_size, 0), background_color=filter_head_col)]],
                             pad=(0, int(pad_el/2)), background_color=filter_head_col, justification='l'),
                      sg.Col([[sg.Text('Options', text_color=select_text_col, background_color=filter_head_col)]],
                             pad=(0, int(pad_el / 2)), background_color=filter_head_col, element_justification='c',
                             expand_x=True, vertical_alignment='c'),
                      sg.Col([[sg.Canvas(size=(option_col_size, 0), background_color=filter_head_col)],
                              [sg.Button('', image_data=mod_const.EXIT_ICON, key=cancel_key, border_width=0,
                                         button_color=(text_col, filter_head_col))]],
                             pad=(pad_el, int(pad_el / 2)), background_color=filter_head_col, justification='r',
                             element_justification='r', vertical_alignment='c')]],
                    pad=(0, (0, pad_v)), background_color=filter_head_col, vertical_alignment='c', expand_x=True)]]

        if self.actions['fill'] is True:
            fill_menu = ['&Fill', list(self.display_columns)]
            options.append([sg.ButtonMenu('', fill_menu, key=fill_key, image_data=mod_const.FILL_ICON,
                                          image_size=(240, 40), pad=(pad_h, (0, int(pad_v/2))), border_width=1,
                                          button_color=(text_col, bg_col), tooltip='Fill NA values')])

        if self.actions['export'] is True:
            options.append([sg.Button('', key=print_key, image_data=mod_const.EXPORT_ICON,
                                      image_size=(240, 40), pad=(pad_h, (0, int(pad_v/2))), border_width=1,
                                      button_color=(text_col, bg_col), tooltip='Export to spreadsheet')])

        if self.actions['sort'] is True:
            sort_menu = ['&Sort', list(self.display_columns)]
            options.append(
                [sg.ButtonMenu('', sort_menu, key=sort_key, image_data=mod_const.SORT_ICON,
                               image_size=(240, 40), pad=(pad_h, (0, int(pad_v/2))), border_width=1,
                               button_color=(text_col, bg_col), tooltip='Sort table on columns')])

        row4.append(sg.Col(options, key=self.key_lookup('OptionsFrame'), background_color=filter_bg_col,
                           justification='r', expand_y=True, visible=False, metadata={'visible': False}))

        # Control buttons and totals row
        row5 = []

        mod_row = [sg.Button('', key=import_key, image_data=mod_const.IMPORT_ICON, border_width=2,
                             button_color=(text_col, header_col), disabled=disabled, visible=self.actions['import'],
                             tooltip='Add an existing database record to the table ({})'.format(import_shortcut),
                             metadata={'visible': self.actions['import'], 'disabled': disabled}),
                   sg.Button('', key=add_key, image_data=mod_const.ADD_ICON, border_width=2,
                             button_color=(text_col, header_col), disabled=disabled, visible=self.actions['add'],
                             tooltip='Add a new row to the table ({})'.format(add_shortcut),
                             metadata={'visible': self.actions['add'], 'disabled': disabled}),
                   sg.Button('', key=delete_key, image_data=mod_const.MINUS_ICON, border_width=2,
                             button_color=(text_col, header_col), disabled=disabled, visible=self.actions['delete'],
                             tooltip='Remove the selected row(s) from the table ({})'.format(delete_shortcut),
                             metadata={'visible': self.actions['delete'], 'disabled': disabled})]

        row5.append(sg.Col([mod_row], pad=(pad_el, int(pad_el / 2)), justification='l', vertical_alignment='c',
                           background_color=header_col, expand_x=True))

        if self.tally_rule is None:
            total_desc = 'Rows:'
        else:
            total_desc = 'Total:'

        init_totals = self.calculate_total()
        if isinstance(init_totals, float):
            init_totals = '{:,.2f}'.format(init_totals)
        else:
            init_totals = str(init_totals)
        row5.append(sg.Col([[sg.Text(total_desc, pad=((0, pad_el), 0), font=bold_font,
                                     background_color=header_col),
                             sg.Text(init_totals, key=total_key, size=(14, 1), pad=((pad_el, 0), 0),
                                     font=font, background_color=bg_col, justification='r', relief='sunken')]],
                           pad=(pad_el, int(pad_el / 2)), vertical_alignment='b', justification='r',
                           background_color=header_col))

        # Table summary rows
        summary_rules = self.summary_rules
        summ_width = self.key_lookup('SummaryWidth')
        if summary_rules:
            summary_c1 = []
            summary_c2 = []
            for summary_rule_name in summary_rules:
                summary_rule = summary_rules[summary_rule_name]
                summary_title = summary_rule.get('Description', summary_rule_name)
                summary_c1.append([sg.Text('{}:'.format(summary_title), pad=((0, pad_h), 0), font=font,
                                           text_color=text_col, background_color=filter_bg_col)])
                summary_c2.append([sg.Text('0.00', key=self.key_lookup(summary_rule_name), size=(14, 1), font=font,
                                           justification='r', text_color=text_col, background_color=filter_bg_col)])
            summary_elements = [[sg.Canvas(key=summ_width, size=(width, 0), background_color=filter_bg_col)],
                                [sg.Col(summary_c1, background_color=filter_bg_col, vertical_alignment='t',
                                        element_justification='r'),
                                 sg.Col(summary_c2, background_color=filter_bg_col, vertical_alignment='t',
                                        expand_x=True)]]

            row6 = [sg.Col([[sg.Text('Summary', pad=((0, pad_h), 0), text_color='white',
                                     background_color=filter_head_col),
                             sg.Button('', image_data=mod_const.HIDE_ICON, key=self.key_lookup('SummaryButton'),
                                       button_color=(text_col, filter_head_col), border_width=0,
                                       tooltip='Hide / reveal table summary')]],
                           pad=(0, 0), element_justification='c', background_color=filter_head_col, expand_x=True)]
            row7 = [sg.pin(sg.Col(summary_elements, key=self.key_lookup('SummaryFrame'), pad=(pad_h, pad_v),
                                  background_color=filter_bg_col, visible=True, expand_x=True, expand_y=True,
                                  metadata={'visible': True}))]
        else:
            row6 = row7 = []

        # Layout
        if collapsible is True:  # display the element as a collapsible frame
            # First row
            icon = self.icon
            if icon is not None:
                icon_path = settings.get_icon_path(icon)
                if icon_path is not None:
                    icon_layout = [sg.Image(filename=icon_path, pad=((0, pad_el), 0), background_color=bg_col)]
                else:
                    icon_layout = []
            else:
                icon_layout = []

            # Element name
            description_layout = [
                sg.Text(self.title, pad=((0, pad_el), 0), background_color=bg_col, font=bold_l_font,
                        auto_size_text=True)]

            hide_key = self.key_lookup('CollapseButton')
            collapse_layout = icon_layout + description_layout
            collapse_layout.append(sg.Button('', pad=(0, 0), image_data=mod_const.HIDE_ICON, key=hide_key,
                                             button_color=(text_col, bg_col), border_width=0))

            # Second row
            element_layout = sg.Frame('', [row1, row2, row3, row4, row5, row6, row7], background_color=header_col,
                                      relief='ridge', border_width=2)

            frame_key = self.key_lookup('CollapseFrame')
            collapse_frame_layout = [sg.pin(sg.Col([[element_layout]], key=frame_key, pad=pad,
                                                   background_color=header_col, visible=True,
                                                   vertical_alignment='t', element_justification='l',
                                                   metadata={'visible': True}))]

            layout = sg.Col([collapse_layout, collapse_frame_layout], pad=padding, background_color=bg_col)
        else:  # display the element in a single row
            layout = sg.Frame('', [row1, row2, row3, row4, row5, row6, row7], pad=pad, element_justification='l',
                              vertical_alignment='t', background_color=header_col, relief='ridge', border_width=2)

        return layout

    def enable(self, window):
        """
        Enable data table element actions.
        """
        params = self.parameters
        add_key = self.key_lookup('Add')
        delete_key = self.key_lookup('Delete')
        import_key = self.key_lookup('Import')

        logger.debug('DataTable {NAME}: enabling table action elements'.format(NAME=self.name))

        # Enable filter parameters
        if len(params) > 0 and self.actions['filter'] is True:
            # Enable the apply button
            filter_key = self.key_lookup('Filter')
            window[filter_key].update(disabled=False)

        # Enable table modification buttons
        window[add_key].update(disabled=False)
        window[add_key].metadata['disabled'] = False

        window[delete_key].update(disabled=False)
        window[delete_key].metadata['disabled'] = False

        window[import_key].update(disabled=False)
        window[import_key].metadata['disabled'] = False

    def disable(self, window):
        """
        Disable data table element actions.
        """
        params = self.parameters
        add_key = self.key_lookup('Add')
        delete_key = self.key_lookup('Delete')
        import_key = self.key_lookup('Import')

        logger.debug('DataTable {NAME}: disabling table action elements'.format(NAME=self.name))

        # Enable filter parameters
        if len(params) > 0 and self.actions['filter'] is True:
            # Enable the apply button
            filter_key = self.key_lookup('Filter')
            window[filter_key].update(disabled=True)

            # Enable parameter input

        # Enable table modification buttons
        window[add_key].update(disabled=True)
        window[add_key].metadata['disabled'] = True

        window[delete_key].update(disabled=True)
        window[delete_key].metadata['disabled'] = True

        window[import_key].update(disabled=True)
        window[import_key].metadata['disabled'] = True

    def _calc_column_widths(self, width: int = 1200, size: int = 13, pixels: bool = False):
        """
        Calculate the width of the table columns based on the number of columns displayed.
        """
        header = list(self.display_columns.keys())
        widths = self.widths

        logger.debug('DataTable {NAME}: calculating table column widths'.format(NAME=self.name))

        # Size of data
        ncol = len(header)

        if ncol < 1:  # no columns in table
            return []

        # Set table width based on whether size in pixels or characters
        if pixels:
            tbl_width = width
        else:
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

    def collapse_expand(self, window, frame: str = None):
        """
        Hide/unhide the filter table frame.
        """
        if frame == 'filter':
            hide_key = self.key_lookup('FilterButton')
            frame_key = self.key_lookup('FilterFrame')
        elif frame == 'summary':
            hide_key = self.key_lookup('SummaryButton')
            frame_key = self.key_lookup('SummaryFrame')
        else:
            hide_key = self.key_lookup('CollapseButton')
            frame_key = self.key_lookup('CollapseFrame')

        if window[frame_key].metadata['visible'] is True:  # already visible, so want to collapse the frame
            logger.debug('DataTable {TBL}: collapsing {FRAME} frame'.format(TBL=self.name, FRAME=frame))
            window[hide_key].update(image_data=mod_const.UNHIDE_ICON)
            window[frame_key].update(visible=False)

            window[frame_key].metadata['visible'] = False
        else:  # not visible yet, so want to expand the frame
            logger.debug('DataTable {TBL}: expanding {FRAME} frame'.format(TBL=self.name, FRAME=frame))
            window[hide_key].update(image_data=mod_const.HIDE_ICON)
            window[frame_key].update(visible=True)

            window[frame_key].metadata['visible'] = True

    def resize(self, window, size: tuple = None, row_rate: int = 80):
        """
        Resize the table element.
        """
        if size is not None:
            width, height = size
        else:
            width, height = window.size

        row_rate = row_rate if row_rate > mod_const.TBL_ROW_HEIGHT else mod_const.TBL_ROW_HEIGHT

        logger.debug('DataTable {TBL}: resizing element display to {W}, {H}'
                     .format(TBL=self.name, W=int(width), H=int(height)))
        self.dimensions = (width, height)

        tbl_key = self.key_lookup('Element')

        # Close options panel, if open
        frame_key = self.key_lookup('OptionsFrame')
        if window[frame_key].metadata['visible'] is True:
            window[frame_key].metadata['visible'] = False
            window[frame_key].update(visible=False)

        # Reset table column sizes
        columns = self.display_columns
        header = list(columns.keys())

        tbl_width = width - 16  # for border sizes on either side of the table
        lengths = self._calc_column_widths(width=tbl_width, pixels=True)
        for col_index, col_name in enumerate(header):
            col_width = lengths[col_index]
            window[tbl_key].Widget.column(col_name, width=col_width)

        window[tbl_key].expand((True, True))
        window[tbl_key].table_frame.pack(expand=True, fill='both')

        # Expand 1 row every N-pixel increase in window size
        initial_nrow = self.nrow if self.nrow is not None else mod_const.TBL_NROW
        orig_height = initial_nrow * mod_const.TBL_ROW_HEIGHT
        height_diff = int((height - orig_height) / row_rate)
        nrows = initial_nrow + height_diff if height_diff > -initial_nrow else 1
        logger.debug('DataTable {NAME}: changing the number of rows in the table from {IROW} to {CROW} based on table '
                     'size difference {DIFF}'.format(NAME=self.name, IROW=initial_nrow, CROW=nrows, DIFF=height_diff))

        window[tbl_key].update(num_rows=nrows)

        # Expand the table frames
        filter_params = self.parameters
        if len(filter_params) > 0 and self.actions['filter'] is True:
            width_key = self.key_lookup('Width')
            window[width_key].set_size((width, None))

        swidth_key = self.key_lookup('SummaryWidth')
        if self.summary_rules:
            window[swidth_key].set_size(size=(tbl_width, None))

    def append(self, add_df, imports: bool = False):
        """
        Add a new row of data to the data table.
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
        add_df = self.set_datatypes(add_df)

        # Add new data to the table
        logger.debug('DataTable {NAME}: appending {NROW} rows to the {TBL}'
                     .format(NAME=self.name, NROW=add_df.shape[0], TBL=table_name))
        df = df.append(add_df, ignore_index=True)

        pd.set_option('display.max_columns', None)
        print(df)

#        df = df.append(add_df, ignore_index=True)
#        df = self.set_datatypes(df)

        return df

    def fill(self, column, fill_method: str = 'ffill', rows: list = None):
        """
        Forward fill table NA values.
        """
        logger.info('DataTable {NAME}: filling {NROW} rows using fill method {METHOD}'
                    .format(NAME=self.name, NROW=len(rows), METHOD=fill_method))

        if rows is not None:  # fill only specified rows
            if len(rows) > 0:
                try:
                    self.df.iloc[rows, self.df.columns.get_loc(column)] = \
                        self.df.iloc[rows, self.df.columns.get_loc(column)].fillna(method=fill_method)
                except IndexError:
                    logger.warning('DataTable {NAME}: unable to fill table on selected rows - unknown rows selected'
                                   .format(NAME=self.name))
                except ValueError:
                    logger.warning('DataTable {NAME}: unable to fill table on selected rows - invalid method provided'
                                   .format(NAME=self.name))
            else:
                logger.warning('DataTable {NAME}: unable to fill table - no rows selected for filling'
                               .format(NAME=self.name))
        else:  # fill all column values
            try:
                self.df[column].fillna(method=fill_method, inplace=True)
            except ValueError:
                logger.warning('DataTable {NAME}: unable to fill table on selected rows - invalid method provided'
                               .format(NAME=self.name))

    def sort(self, sort_on=None, ascending: bool = True):
        """
        Sort the table on provided column name.
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

    def subset(self, subset_rule):
        """
        Subset the table based on a set of rules.
        """
        operators = {'>', '>=', '<', '<=', '==', '!=', '=', 'IN', 'In', 'in'}
        chain_map = {'or': '|', 'OR': '|', 'Or': '|', 'and': '&', 'AND': '&', 'And': '&'}

        df = self.data()
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

    def export_table(self, df, annotation_map):
        """
        Export table to spreadsheet.
        """
        logger.info('DataTable {NAME}: exporting the display table to a spreadsheet'.format(NAME=self.name))
        outfile = sg.popup_get_file('', title='Export table display', save_as=True,
                                    default_extension='xlsx', no_window=True,
                                    file_types=(
                                        ('XLS - Microsoft Excel', '*.xlsx'), ('Comma-Separated Values', '*.csv')))

        out_fmt = outfile.split('.')[-1]

        if outfile:
            if out_fmt == 'csv':
                df.to_csv(outfile, sep=',', header=True, index=False)
            else:
                df.style.apply(
                    lambda x: ['background-color: {}'.format(annotation_map.get(x.name, 'white')) for _ in x],
                    axis=1).to_excel(outfile, engine='openpyxl', header=True, index=False)

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

        logger.debug('DataTable {NAME}: calculating table totals'.format(NAME=self.name))

        total = 0
        if tally_rule is not None:
            try:
                result = mod_dm.evaluate_rule(df, tally_rule, as_list=False)
            except Exception as e:
                msg = 'DataTable {NAME}: unable to calculate table total - {ERR}'\
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

    def row_ids(self, imports: bool = False):
        """
        Return a list of all current row IDs in the dataframe.
        """
        id_field = self.id_column
        if imports:
            df = self.import_df
        else:
            df = self.data()  # don't include deleted IDs

        try:
            row_ids = df[id_field].tolist()
        except KeyError:  # database probably PostGreSQL
            logger.warning('DataTable {NAME}: unable to return a list of row IDs from the table - ID column "{COL}" '
                           'not found in the data table'.format(NAME=self.name, COL=id_field))
            row_ids = []

        return row_ids

    def value_set(self):
        """
        Return True if no NAs in the table else return False.
        """
        if self.df.isnull().values.any() is True:
            return False
        else:
            return True

    def add_row(self, record_date: datetime.datetime = None, defaults: dict = None):
        """
        Add a new row to the records table.
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
            record = mod_records.create_record(record_entry, record_data)
        except Exception as e:
            msg = 'failed to add record at row {IND} - {ERR}'.format(IND=df.shape[0] + 2, ERR=e)
            mod_win2.popup_error(msg)
            logger.error('DataTable {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
            return df

        # Display the record window
        record = mod_win2.record_window(record)
        try:
            record_values = record.table_values()
        except AttributeError:  # record creation was cancelled
            return df
        else:
            logger.debug('DataTable {NAME}: appending values {VALS} to the table'
                         .format(NAME=self.name, VALS=record_values))
            df = self.append(record_values)

        self.df = df

        return df

    def import_rows(self, import_rules: dict = None, reftype: str = None, program_database: bool = False):
        """
        Import one or more records from a table of records.
        """
        import_df = self.import_df.copy()
        import_rules = import_rules if import_rules is None else self.import_rules
        record_type = self.record_type
        id_col = self.id_column

        record_entry = settings.records.fetch_rule(record_type)
        if import_rules is None and record_entry is None:
            msg = 'unable to display the record import window - record type was not configured for the table'
            mod_win2.popup_error(msg)
            logger.error('DataTable {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            return self.df
        elif record_entry is not None and import_rules is None:
            import_rules = record_entry.import_rules

        # Initialize the import table
        if record_entry is not None:
            table_layout = record_entry.import_table
            table_layout['RecordType'] = record_type
            table_layout['Actions'] = {'filter': 1, 'search': 1, 'export': 1, 'options': 1, 'sort': 1}
        else:
            table_layout = {'Columns': self.columns, 'DisplayColumns': self.display_columns, 'Aliases': self.aliases,
                            'RowColor': self.row_color, 'Widths': self.widths, 'IDColumn': self.id_column,
                            'RecordType': self.record_type, 'Title': self.title, 'ImportRules': import_rules,
                            'Actions': {'search': 1, 'filter': 1, 'export': 1, 'options': 1, 'sort': 1},
                            'FilterParameters': self.parameters}

        import_table = TableElement(self.name, table_layout)

        if reftype is not None:  # search for records without an existing reference to provided reference type
            # Prepare query arguments
            import_filters = mod_db.format_import_filters(import_rules)
            table_statement = mod_db.format_tables(import_rules)
            import_columns = mod_db.format_import_columns(import_rules)

            # Search for records in record reference table with associations
            ref_table = settings.reference_lookup
            ref_filter = ('RefType = ? AND DocType = ? AND IsDeleted = ?', (record_type, reftype, 0))
            references = user.read_db(*user.prepare_query_statement(ref_table, filter_rules=ref_filter), prog_db=True)

            try:
                df = user.read_db(*user.prepare_query_statement(table_statement, columns=import_columns,
                                                                filter_rules=import_filters), prog_db=True)
            except Exception as e:
                logger.warning('DataTable {NAME}: failed to import data from the database - {ERR}'
                               .format(NAME=self.name, ERR=e))
            else:
                # Drop records that already have associations to reference type records
                ids_with_reference = references['RefNo'].tolist()
                df.drop(df[df[id_col].isin(ids_with_reference)].index, inplace=True)

                # Drop records that are already in the import table
                import_ids = import_df[id_col].tolist()
                df.drop(df[df[id_col].isin(import_ids)].index, inplace=True)

                # Drop records that are already in the table
                current_ids = self.df[id_col].tolist()
                df.drop(df[df[id_col].isin(current_ids)].index, inplace=True)

                # Add import dataframe to data table object
                import_table.df = import_df.append(df, ignore_index=True)
        else:
            import_table.df = import_df

        # Add relevant search parameters
        if self.search_field:
            display_map = {j: i for i, j in self.display_columns.items()}
            try:
                search_desc = display_map[self.search_field]
            except KeyError:
                search_desc = self.search_field
            search_entry = {'Description': search_desc, 'ElementType': 'input', 'DataType': 'string'}
            search_params = [mod_param.DataParameterInput(self.search_field, search_entry)]
        else:
            search_params = None

        import_table.sort()

        # Get table of user selected import records
        select_df = mod_win2.import_window(import_table, import_rules, program_database=program_database,
                                           params=search_params)

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
        df = self.append(select_df)
        self.df = df

        # Remove selected rows from the table of available import rows
        self.import_df = import_df[~import_df[self.id_column].isin(select_ids)]

        return df

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
        display_map = {j: i for i, j in self.display_columns.items()}
        mod_row = mod_win2.edit_row_window(row, edit_columns=edit_columns, header_map=display_map)

        # Update record table values
        df.loc[index] = mod_row
        self.df = df

        return df

    def translate_row(self, row, layout: dict = None, level: int = 1, new_record: bool = False,
                      references: pd.DataFrame = None, custom: bool = False):
        """
        Translate row data into a record object.
        """
        # Create a record object from the row data
        if custom is True:
            if layout is None:
                raise AttributeError('a layout must be provided when custom is set to True')
            record_entry = mod_records.CustomRecordEntry({'RecordLayout': layout})
            record_group = 'custom'
        else:
            record_entry = settings.records.fetch_rule(self.record_type)
            record_group = record_entry.group

        if record_group in ('custom', 'account', 'bank_statement', 'cash_expense'):
            record_class = mod_records.StandardRecord
        elif record_group == 'bank_deposit':
            record_class = mod_records.DepositRecord
        elif record_group == 'audit':
            record_class = mod_records.TAuditRecord
        else:
            raise AttributeError('unknown record group provided {GROUP}'.format(NAME=self.name, GROUP=record_group))

        record = record_class(record_entry, level=level, record_layout=layout)
        record.initialize(row, new=new_record, references=references)

        return record

    def export_row(self, index, layout: dict = None, view_only: bool = False, new_record: bool = False,
                   level: int = 1, references: pd.DataFrame = None, custom: bool = False):
        """
        Open selected record in new record window.
        """
        df = self.df.copy()
        header = df.columns.values.tolist()

        try:
            row = df.loc[index]
        except IndexError:
            msg = 'no record found at table index {IND} to edit'.format(IND=index + 1)
            mod_win2.popup_error(msg)
            logger.error('DataTable {NAME}: failed to open record at row {IND} - {MSG}'
                         .format(NAME=self.name, IND=index + 1, MSG=msg))

            return df

        # Add any annotations to the exported row
        annotations = self.annotate_display(df)
        annot_code = annotations.get(index, None)
        if annot_code is not None:
            row['Warnings'] = self.annotation_rules[annot_code]['Description']

        try:
            record = self.translate_row(row, layout, level=level, new_record=new_record, references=references,
                                        custom=custom)
        except Exception as e:
            msg = 'failed to open record at row {IND}'.format(IND=index + 1)
            mod_win2.popup_error(msg)
            logger.error('DataTable {NAME}: {MSG} - {ERR}'.format(NAME=self.name, MSG=msg, ERR=e))

            return df
        else:
            logger.info('DataTable {NAME}: opening record {ID} at row {IND}'
                        .format(NAME=self.name, ID=record.record_id(), IND=index))

        # Display the record window
        record = mod_win2.record_window(record, view_only=view_only)

        # Update record table values
        try:
            record_values = record.table_values()
        except AttributeError:  # user selected to cancel editing the record
            return df
        else:
            for col_name, col_value in record_values.iteritems():
                if col_name not in header:
                    continue

                try:
                    df.at[index, col_name] = col_value
                except KeyError:
                    continue
                except ValueError as e:
                    logger.error('DataTable {NAME}: failed to assign value {VAL} to column {COL} at index {IND} - {ERR}'
                                 .format(NAME=self.name, VAL=col_value, COL=col_name, IND=index, ERR=e))

        df = self.set_datatypes(df)

        return df

    def delete_rows(self, indices):
        """
        Remove records from the records table.
        """
        df = self.df.copy()
        select_df = df.iloc[indices]

        # Get record IDs of selected rows
        record_ids = select_df[self.id_column].tolist()
        logger.info('DataTable {TBL}: removing records {IDS} from the table'
                    .format(TBL=self.name, IDS=record_ids))

        # Add removed rows to the import dataframe
        self.import_df = self.append(select_df, imports=True)

        # Set deleted rows to True
        df.loc[df[self.id_column].isin(record_ids), self.deleted_column] = True
        self.df = df

        # Drop selected rows from the dataframe
#        df.drop(indices, axis=0, inplace=True)
#        df.reset_index(drop=True, inplace=True)

        # Remove unsaved ID, if relevant
#        record_entry = settings.records.fetch_rule(self.record_type)
#        if record_entry is not None:
#            for record_id in record_ids:
#                record_entry.remove_unsaved_ids(record_ids=[record_id])

        return df

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

    def initialize_defaults(self):
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

        df = self.df.copy()
        header = df.columns.tolist()
        columns = self.defaults
        for column in columns:
            try:
                dtype = self.columns[column]
            except KeyError:
                logger.warning('DataTable {NAME}: default column {COL} not found in table header'
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
                            df.at[index, column] = default_value
            elif 'DefaultRule' in entry:
                default_values = mod_dm.evaluate_rule(df, entry['DefaultRule'], as_list=True)
                logger.debug('DataTable {NAME}: assigning values "{VAL}" to empty cells in column "{COL}"'
                             .format(NAME=self.name, VAL=default_values, COL=column))
                for index, default_value in enumerate(default_values):
                    if pd.isna(df.at[index, column]):
                        df.at[index, column] = default_value
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

        df = self.set_datatypes(df)

        return df

    def set_datatypes(self, df):
        """
        Set column data types based on header mapping
        """
        CategoricalDtype = pd.api.types.CategoricalDtype

        dtype_map = self.columns
        header = df.columns.tolist()

        logger.debug('DataTable {NAME}: setting column data types to configured data types'.format(NAME=self.name))

        if not isinstance(dtype_map, dict):
            logger.warning('DataTable {NAME}: unable to set column datatypes. Columns must be configured '
                           'as an object to specify data types'.format(NAME=self.name))
            return df

        for column in dtype_map:
            if column not in header:
                logger.warning('DataTable {NAME}: unable to specify the data type for configured column "{COL}" - '
                               '"{COL}" is not in the dataframe header'.format(NAME=self.name, COL=column))
                continue

            dtype = dtype_map[column]
            if isinstance(dtype, list) or isinstance(dtype, tuple):
                dtype = dtype.append('')  # categories should contain empty string
                cat_type = CategoricalDtype(categories=dtype, ordered=False)
                df[column] = df[column].astype(cat_type)
            elif isinstance(dtype, str):
                try:
                    if dtype in ('date', 'datetime', 'timestamp', 'time'):
                        df.loc[:, column] = pd.to_datetime(df[column], errors='coerce', format=settings.date_format,
                                                           utc=False)
                    elif dtype in ('int', 'integer', 'bigint'):
                        try:
                            df.loc[:, column] = df[column].astype('Int64')
                        except TypeError:
                            df.loc[:, column] = df[column].astype(float).astype('Int64')
                    elif dtype == 'mediumint':
                        try:
                            df.loc[:, column] = df[column].astype('Int32')
                        except TypeError:
                            df.loc[:, column] = df[column].astype(float).astype('Int32')
                    elif dtype == 'smallint':
                        try:
                            df.loc[:, column] = df[column].astype('Int16')
                        except TypeError:
                            df.loc[:, column] = df[column].astype(float).astype('Int16')
                    elif dtype in ('tinyint', 'bit'):
                        try:
                            df.loc[:, column] = df[column].astype('Int8')
                        except TypeError:
                            df.loc[:, column] = df[column].astype(float).astype('Int8')
                    elif dtype in ('float', 'real', 'double'):  # approximate numeric data types for saving memory
                        df.loc[:, column] = pd.to_numeric(df[column], errors='coerce', downcast='float')
                    elif dtype in ('decimal', 'dec', 'numeric', 'money'):  # exact numeric data types
                        df.loc[:, column] = pd.to_numeric(df[column], errors='coerce')
                    elif dtype in ('bool', 'boolean'):
                        df.loc[:, column] = df[column].fillna(False).astype(np.bool, errors='raise')
                    elif dtype in ('char', 'varchar', 'binary', 'text', 'string'):
                        df.loc[:, column] = df[column].astype(np.object, errors='raise')
                    else:
                        df.loc[:, column] = df[column].astype(np.object, errors='raise')
                except Exception as e:
                    logger.warning('DataTable {NAME}: unable to set column "{COL}" to data type "{DTYPE}" - {ERR}'
                                   .format(NAME=self.name, COL=column, DTYPE=dtype, ERR=e))
                    logger.debug('DataTable {NAME}: column values are {VALS}'.format(NAME=self.name, VALS=df[column]))
            else:
                logger.warning('DataTable {NAME}: unable to specify the data type for column "{COL}" - data type is '
                               'provided in an unaccepted format'.format(NAME=self.name, COL=column))

        print(df.dtypes)

        return df


class ReferenceElement:
    """
    GUI reference box element.

    Attributes:

        name (str): reference box element configuration name.

        id (int): reference box element number.

        elements (list): list of reference box element GUI keys.
    """

    def __init__(self, name, entry, parent=None, inverted: bool = False):
        """
        GUI data element.

        Arguments:
            name (str): reference box element configuration name.

            entry (pd.Series): configuration entry for the element.
        """
        is_datetime_dtype = pd.api.types.is_datetime64_any_dtype

        self.name = name
        self.parent = parent
        self.id = randint(0, 1000000000)
        self.elements = ['-{NAME}_{ID}_{ELEM}-'.format(NAME=name, ID=self.id, ELEM=i) for i in
                         ['Element', 'Reference', 'Unlink', 'Width', 'Height']]

        if inverted is True:
            colmap = {'DocNo': 'RecordID', 'RefNo': 'ReferenceID', 'DocType': 'RecordType', 'RefType': 'ReferenceType'}
            self.inverted = True
        else:
            colmap = {'DocNo': 'ReferenceID', 'RefNo': 'RecordID', 'DocType': 'ReferenceType', 'RefType': 'RecordType'}
            self.inverted = False

        entry = entry.rename(index=colmap)

        try:
            self.record_id = entry['RecordID']
        except KeyError:
            raise AttributeError('missing required Reference parameter "DocNo"')

        try:
            self.reference_id = entry['ReferenceID']
        except KeyError:
            raise AttributeError('missing required Reference parameter "RefNo"')

        try:
            ref_date = entry['RefDate']
        except KeyError:
            raise AttributeError('missing required Reference parameter "RefDate"')
        else:
            if is_datetime_dtype(ref_date) or isinstance(ref_date, datetime.datetime):
                self.ref_date = ref_date
            elif isinstance(ref_date, str):
                try:
                    self.ref_date = datetime.datetime.strptime(ref_date, '%Y-%m-%d')
                except ValueError:
                    raise AttributeError('unknown format for "RefDate" value {}'.format(ref_date))
            else:
                raise AttributeError('unknown format for "RefDate" value {}'.format(ref_date))

        try:
            self.record_type = entry['RecordType']
        except KeyError:
            raise AttributeError('missing required Reference parameter "RefType"')

        try:
            self.reference_type = entry['ReferenceType']
        except KeyError:
            raise AttributeError('missing required Reference parameter "RefType"')

        try:
            self.warnings = entry['Warnings']
        except KeyError:
            self.warnings = None

        record_entry = settings.records.fetch_rule(self.record_type)
        record_data = record_entry.load_record_data(self.record_id)
        nrow = record_data.shape[0]

        if nrow < 1:
            logger.warning('RecordType {NAME}: record ID {ID} not found in the database'
                           .format(NAME=self.name, ID=self.record_id))
            self.record_data = record_data
        elif nrow == 1:
            self.record_data = record_data.iloc[0]
        else:
            logger.warning('RecordType {NAME}: more than one database entry found for record ID {ID}'
                           .format(NAME=self.name, ID=self.record_id))
            self.record_data = record_data.iloc[0]

        if record_entry is not None:
            self.title = record_entry.menu_title
        else:
            self.title = name

        try:
            self.linked = not bool(int(entry['IsDeleted']))
        except (ValueError, KeyError):
            self.linked = True

    def key_lookup(self, component):
        """
        Lookup a component's GUI element key using the component's name.
        """
        element_names = [i[1:-1].split('_')[-1] for i in self.elements]
        if component in element_names:
            key_index = element_names.index(component)
            key = self.elements[key_index]
        else:
            logger.warning('ReferenceElement {NAME}: component "{COMP}" not found in list of element components'
                           .format(NAME=self.name, COMP=component))
            key = None

        return key

    def resize(self, window, size: tuple = None):
        """
        Resize the reference box element.
        """
        if size is None:
            width = int(window.size[0] * 0.5 / 11)
            height = 40
        else:
            width, height = size

        width_key = self.key_lookup('Width')
        window[width_key].set_size(size=(width, None))

        height_key = self.key_lookup('Height')
        window[height_key].set_size(size=(None, height))

    def layout(self, size: tuple = (200, 40), padding: tuple = (0, 0), editable: bool = False):
        """
        GUI layout for the reference box element.
        """
        is_disabled = not editable
        width, height = size
        linked = self.linked
        warnings = self.warnings if self.warnings is not None else ''

        # Layout options
        pad_el = mod_const.ELEM_PAD
        pad_v = mod_const.VERT_PAD
        pad_h = mod_const.HORZ_PAD

        font = mod_const.LARGE_FONT
        bold_font = mod_const.BOLD_FONT

        bg_col = mod_const.ACTION_COL if not warnings else mod_const.WARNING_COL
        text_col = mod_const.TEXT_COL
        if editable is True:
            select_text_col = mod_const.SELECT_TEXT_COL
        else:
            select_text_col = mod_const.DISABLED_TEXT_COL

        discard_key = self.key_lookup('Unlink')
        row1 = [sg.Col([[sg.Text(self.title, auto_size_text=True, text_color=text_col, font=bold_font,
                                 background_color=bg_col)]],
                       pad=(pad_h, pad_v), justification='l', background_color=bg_col, expand_x=True),
                sg.Col([[sg.Button(image_data=mod_const.DISCARD_ICON, key=discard_key, disabled=is_disabled,
                                   button_color=(text_col, bg_col), border_width=0)]],
                       pad=(pad_h, pad_v), justification='r', background_color=bg_col)]

        ref_key = self.key_lookup('Reference')
        elem_key = self.key_lookup('Element')
        height_key = self.key_lookup('Height')
        row2 = [sg.Canvas(key=height_key, size=(0, height)),
                sg.Col([[sg.Text('ID:', auto_size_text=True, pad=((0, pad_el), 0), text_color=text_col,
                                 font=font, background_color=bg_col),
                         sg.Text(self.record_id, key=ref_key, auto_size_text=True, pad=((0, pad_h), 0),
                                 enable_events=editable, text_color=select_text_col, font=font, background_color=bg_col,
                                 tooltip='Open reference record'),
                         sg.Text('Date:', auto_size_text=True, pad=((0, pad_el), 0), text_color=text_col,
                                 font=font, background_color=bg_col),
                         sg.Text(settings.format_display_date(self.ref_date), auto_size_text=True,
                                 enable_events=True, text_color=text_col, font=font, background_color=bg_col)]],
                       pad=(pad_h, (0, pad_v)), background_color=bg_col, expand_x=True)]

        width_key = self.key_lookup('Width')
        layout = sg.Frame('', [[sg.Canvas(key=width_key, size=(width, 0))], row1, row2],
                          key=elem_key, pad=padding, background_color=bg_col, relief='raised', visible=linked,
                          metadata={'deleted': False}, tooltip=warnings)

        return layout

    def run_event(self, window, event, values):
        """
        Run a record reference event.
        """
        result = True
        elem_key = self.key_lookup('Element')
        del_key = self.key_lookup('Unlink')
        ref_key = self.key_lookup('Reference')

        # Delete a reference from the record reference database table
        logger.info('ReferenceElement {NAME}: running event {EVENT}'.format(NAME=self.name, EVENT=event))
        if event == del_key:
            msg = 'Are you sure that you would like to disassociate reference {REF} from {RECORD}? This action ' \
                  'cannot be undone. Disassociating a reference does not delete the reference record.' \
                .format(REF=self.record_id, RECORD=self.reference_id)
            user_action = mod_win2.popup_confirm(msg)

            if user_action.upper() == 'OK':
                self.linked = False
                # Set element to deleted in metadata
                window[elem_key].metadata['deleted'] = True
                window[elem_key].update(visible=False)

        # Load a reference record in a new window
        elif event == ref_key:
            try:
                record = self.initialize_record()
            except Exception as e:
                msg = 'failed to open the reference record {ID} - {ERR}'.format(ID=self.record_id, ERR=e)
                mod_win2.popup_error(msg)
                logger.error('ReferenceElement {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
            else:
                # Display the record window
                mod_win2.record_window(record, view_only=True)

        return result

    def initialize_record(self, level: int = 1):
        """
        Create a record object from the reference.
        """
        record_entry = settings.records.fetch_rule(self.record_type)
        record_group = record_entry.group
        if record_group in ('account', 'bank_statement', 'cash_expense'):
            record_class = mod_records.StandardRecord
        elif record_group == 'bank_deposit':
            record_class = mod_records.DepositRecord
        elif record_group == 'audit':
            record_class = mod_records.TAuditRecord
        else:
            raise TypeError('unknown record group provided {}'.format(record_group))

        record = record_class(record_entry, level=level)
        record.initialize(self.record_data, new=False)

        return record

    def as_table(self):
        """
        Format reference as a table entry.
        """
        if self.inverted is True:
            reference = pd.Series([self.record_id, self.reference_id, self.ref_date, self.record_type,
                                   self.reference_type, not self.linked, self.warnings],
                                  index=['DocNo', 'RefNo', 'RefDate', 'DocType', 'RefType', 'IsDeleted', 'Warnings'])
        else:
            reference = pd.Series([self.reference_id, self.record_id, self.ref_date, self.reference_type,
                                   self.record_type, not self.linked, self.warnings],
                                  index=['DocNo', 'RefNo', 'RefDate', 'DocType', 'RefType', 'IsDeleted', 'Warnings'])

        return reference


class DataElement:
    """
    GUI data element.

    Attributes:

        name (str): data element configuration name.

        id (int): data element number.

        elements (list): list of data element GUI keys.

        description (str): display name of the data element.

        etype (str): GUI element type. Can be dropdown, input, date, or checkbox

        dtype (str): element data type.

        editable (bool): element is editable. [Default: False]

        hidden (bool): element is not visible to the user. [Default: False]

        required (bool): element requires a value [Default: False].

        value: value of the data element.
    """

    def __init__(self, name, entry, parent=None):
        """
        GUI data element.

        Arguments:
            name (str): data element configuration name.

            entry (dict): configuration entry for the data element.
        """
        self.name = name
        self.parent = parent
        self.id = randint(0, 1000000000)
        self.elements = ['-{NAME}_{ID}_{ELEM}-'.format(NAME=name, ID=self.id, ELEM=i) for i in
                         ['Element', 'CollapseButton', 'CollapseFrame']]

        try:
            self.etype = entry['ElementType']
        except KeyError:
            raise AttributeError('missing required parameter "ElementType".')
        else:
            if self.etype == 'date':
                self.elements.append('-{NAME}_{ID}_Calendar-'.format(NAME=name, ID=self.id))

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
            self.description = entry['Description']
        except KeyError:
            raise AttributeError('missing required parameter "Description".')

        try:
            editable = bool(int(entry['IsEditable']))
        except KeyError:
            self.editable = True
        except ValueError:
            logger.warning('DataElement {NAME}: "IsEditable" must be either 0 (False) or 1 (True)'.format(NAME=name))
            self.editable = False
        else:
            self.editable = editable

        try:
            hidden = bool(int(entry['IsHidden']))
        except KeyError:
            self.hidden = False
        except ValueError:
            logger.warning('DataElement {NAME}: configuration parameter "IsHidden" must be either 0 (False) or 1 (True)'
                           .format(NAME=name))
            sys.exit(1)
        else:
            self.hidden = hidden

        try:
            required = bool(int(entry['IsRequired']))
        except KeyError:
            self.required = False
        except ValueError:
            logger.warning('DataElement {NAME}: configuration parameter "IsRequired" must be either 0 (False) or 1 '
                           '(True)'.format(NAME=name))
            sys.exit(1)
        else:
            self.required = required

        try:
            self.options = entry['Options']
        except KeyError:
            self.options = {}

        try:
            self.default = entry['DefaultValue']
        except KeyError:
            self.default = None

        self.value = None
        try:
            self.value = self.format_value(self.default)
        except (KeyError, TypeError):
            self.value = self.format_value(None)

        logger.debug('DataElement {NAME}: initializing {ETYPE} element of data type {DTYPE} with default value {DEF} '
                     'and formatted value {VAL}'
                     .format(NAME=self.name, ETYPE=self.etype, DTYPE=self.dtype, DEF=self.default, VAL=self.value))

        self.disabled = False

    def key_lookup(self, component):
        """
        Lookup a component's GUI element key using the component's name.
        """
        element_names = [i[1: -1].split('_')[-1] for i in self.elements]
        if component in element_names:
            key_index = element_names.index(component)
            key = self.elements[key_index]
        else:
            msg = 'DataElement {NAME}: component "{COMP}" not found in list of element components'\
                .format(NAME=self.name, COMP=component)
            logger.warning(msg)
            logger.debug('DataElement {NAME}: data element contains components {COMP}'
                         .format(NAME=self.name, COMP=element_names))

            raise KeyError(msg)

        return key

    def reset(self, window):
        """
        Reset data element value to default.
        """
        try:
            default = self.format_value(self.default)
        except (KeyError, TypeError):
            default = self.format_value(None)

        if not pd.isna(self.default) and not pd.isna(self.value):
            logger.debug('DataElement {NAME}: resetting data element value "{VAL}" to default "{DEF}"'
                         .format(NAME=self.name, VAL=self.value, DEF=self.default))

        self.value = default

        # Update the parameter window element
        window[self.key_lookup('Element')].update(value=default)

    def resize(self, window, size: tuple = None):
        """
        Resize the data element.
        """
        if size is None:
            width = int(window.size[0] * 0.5)
            height = 1
            # Remove width of the combobox from element width, if needed
            if self.etype == 'dropdown':  # remove width of combobox from element width
                width_offset = 10
                height = 10
            else:
                width_offset = 0

            # Convert from pixels to characters
            width = int(((width - width % 9) / 9) - ((width_offset - width_offset % 9) / 9))
        else:
            width, height = size

        elem_key = self.key_lookup('Element')
        window[elem_key].set_size(size=(width, height))
        window[elem_key].expand(expand_x=True)

    def run_event(self, window, event, values):
        """
        Perform an action.
        """
        elem_key = self.key_lookup('Element')
        expand_key = self.key_lookup('CollapseButton')
        if event == expand_key:
            self.collapse_expand(window)
        elif event == elem_key:
            try:
                display_value = self.enforce_formatting(window, values)
            except Exception as e:
                logger.error('DataElement {NAME}: failed to update the display - {ERR}'.format(NAME=self.name, ERR=e))

                return False
            else:
                window[elem_key].update(value=display_value)

        return True

    def layout(self, padding: tuple = (0, 0), size: tuple = (20, 1), collapsible: bool = False, editable: bool = True,
               overwrite_edit: bool = False):
        """
        GUI layout for the data element.
        """
        etype = self.etype
        dtype = self.dtype
        is_disabled = False if overwrite_edit is True or (editable is True and self.editable is True) else True
        self.disabled = is_disabled
        is_required = self.required

        element_options = self.options
        aliases = element_options.get('Aliases', {})
        background = element_options.get('BackgroundColor', None)
        if isinstance(background, str) and (not background.startswith('#') or len(background) != 7):  # hex color codes
            background = None

        # Layout options
        pad_el = mod_const.ELEM_PAD

        font = mod_const.LARGE_FONT
        bold_font = mod_const.BOLD_HEADER_FONT

        bg_col = mod_const.ACTION_COL
        if is_disabled is True:
            text_col = mod_const.DISABLED_TEXT_COL
            input_col = mod_const.DISABLED_BG_COL if background is None else background
        else:
            input_col = mod_const.INPUT_COL if background is None else background
            text_col = mod_const.TEXT_COL

        # Element Icon, if provided
        icon = element_options.get('Icon', None)
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
                                       text_color=mod_const.WARNING_COL, tooltip='required')]
        else:
            required_layout = []

        # Element name
        description_layout = [sg.Text(self.description, pad=((0, pad_el), 0), background_color=bg_col, font=bold_font,
                                      auto_size_text=True)]

        # Element box
        elem_key = self.key_lookup('Element')
        param_value = self.value
        if isinstance(param_value, datetime.datetime):
            display_value = param_value.strftime('%Y-%m-%d')
            stored_value = param_value.strftime('%Y%m%d')
        elif dtype == 'money' and (isinstance(param_value, float) or isinstance(param_value, int)):
            display_value = '{:,.2f}'.format(param_value)
            stored_value = display_value.replace(',', '')
        elif isinstance(param_value, type(None)):
            display_value = stored_value = ''
        elif isinstance(param_value, bool):
            display_value = stored_value = param_value
        else:
            try:
                display_value = stored_value = aliases[str(param_value)]
            except KeyError:
                display_value = stored_value = str(param_value)

        if etype == 'dropdown':
            try:
                values = element_options['Values']
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

            element_layout = [sg.Combo(display_values, default_value=display_value, key=elem_key, size=size, font=font,
                                       text_color=text_col, background_color=input_col,
                                       enable_events=True, disabled=is_disabled,
                                       tooltip='Select value from list for {}'.format(self.description),
                                       metadata={'disabled': is_disabled, 'value': stored_value})]
        elif etype == 'input':
            element_layout = [sg.Input(display_value, key=elem_key, size=size, enable_events=True, font=font,
                                       background_color=input_col, text_color=text_col, disabled=is_disabled,
                                       disabled_readonly_background_color=input_col,
                                       disabled_readonly_text_color=text_col,
                                       tooltip='Input value for {}'.format(self.description),
                                       metadata={'disabled': is_disabled, 'value': stored_value})]
        elif etype == 'date':
            date_key = self.key_lookup('Calendar')
            element_layout = [sg.Input(display_value, key=elem_key, pad=((0, pad_el), 0), size=size, font=font,
                                       background_color=input_col, text_color=text_col,
                                       disabled=is_disabled, enable_events=True,
                                       tooltip='Input date as YYYY-MM-DD or select date with the calendar button',
                                       metadata={'disabled': is_disabled, 'value': stored_value}),
                              sg.CalendarButton('', target=elem_key, key=date_key, format='%Y-%m-%d',
                                                image_data=mod_const.CALENDAR_ICON,
                                                font=font, border_width=0, disabled=is_disabled,
                                                tooltip='Select the date from the calendar dropdown')]
        elif etype == 'text':
            element_layout = [sg.Text(display_value, key=elem_key, size=size, font=font,
                                      background_color=input_col, text_color=text_col,
                                      border_width=1, relief='sunken',
                                      metadata={'disabled': is_disabled, 'value': stored_value})]
        elif etype == 'multiline':
            nrow = element_options.get('Rows', 1)
            width = size[0]
            element_layout = [sg.Multiline(display_value, key=elem_key, size=(width, nrow), font=font,
                                           background_color=input_col, text_color=text_col, write_only=False,
                                           border_width=1, disabled=is_disabled, enable_events=True,
                                           tooltip='Input value for {}'.format(self.description),
                                           metadata={'disabled': is_disabled, 'value': param_value})]
        elif etype == 'checkbox':
            element_layout = [sg.Checkbox('', default=param_value, key=elem_key, font=bold_font,
                                          enable_events=True, background_color=bg_col, disabled=is_disabled,
                                          metadata={'disabled': is_disabled, 'value': stored_value})]
        else:
            raise TypeError('unknown element type {TYPE} for parameter {PARAM}'.format(TYPE=etype, PARAM=self.name))

        # Layout
        if collapsible is True:  # display the element as a collapsible frame
            # First row
            hide_key = self.key_lookup('CollapseButton')
            row1 = icon_layout + description_layout
            row1.append(sg.Button('', pad=(0, 0), image_data=mod_const.HIDE_ICON, key=hide_key,
                                  button_color=(text_col, bg_col), border_width=0))

            # Second row
            frame_key = self.key_lookup('CollapseFrame')
            row2 = [sg.pin(sg.Col([element_layout + required_layout], key=frame_key, background_color=bg_col,
                                  visible=True, metadata={'visible': True}))]

            layout = sg.Col([row1, row2], pad=padding, background_color=bg_col)
        else:  # display the element in a single row, parameter style
            row = icon_layout + description_layout + element_layout + required_layout
            layout = sg.Col([row], pad=padding, background_color=bg_col)

        return layout

    def update_display(self, window, window_values: dict = None):
        """
        Format element for display.
        """
        elem_key = self.key_lookup('Element')
        options = self.options

        # Update element display value
        logger.debug('DataElement {NAME}: disabled {EDIT}; hidden {VIS}'
                     .format(NAME=self.name, EDIT=self.disabled, VIS=self.hidden))
        if not self.disabled and not self.hidden:  # element is not disabled and is visible to the user
            logger.debug("DataElement {NAME}: updating the element's display value using current window values"
                         .format(NAME=self.name))

            try:
                param_value = window_values[elem_key]
            except KeyError:
                logger.warning('DataElement {NAME}: unable to locate values for element key "{KEY}"'
                               .format(NAME=self.name, KEY=elem_key))
                if self.value:
                    display_value = self.format_display()
                    window[elem_key].update(value=display_value)
                else:
                    display_value = None
            except TypeError:
                display_value = None
            else:
                self.value = self.format_value(param_value)
                display_value = self.format_display()
                window[elem_key].update(value=display_value)
        else:  # element is either disabled or hidden
            if self.value:
                logger.debug("DataElement {NAME}: updating the element's display value using existing element value"
                             .format(NAME=self.name))

                display_value = self.format_display()
                window[elem_key].update(value=display_value)
            else:
                logger.debug("DataElement {NAME}: no values provided to update the element's display"
                             .format(NAME=self.name))

                display_value = None

        # Update element background color
        bg_col = options.get('BackgroundColor', None)
        default_bg_col = mod_const.DISABLED_BG_COL if self.disabled is True else mod_const.INPUT_COL
        if display_value and self.etype in ('input', 'multiline'):
            window[elem_key].update(background_color=bg_col)
        elif not display_value and self.etype in ('input', 'multiline'):
            window[elem_key].update(background_color=default_bg_col)

    def enforce_formatting(self, window, values):
        """
        Format the display value.
        """
        strptime = datetime.datetime.strptime
        dec_sep = settings.decimal_sep
        group_sep = settings.thousands_sep

        dtype = self.dtype

        elem_key = self.key_lookup('Element')
        try:
            value = values[elem_key]
        except KeyError:
            window.refresh()
            try:
                value = values[elem_key]
            except KeyError:
                msg = 'no values provided to update the display'
                logger.debug('DataElement {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
                raise KeyError(msg)

        if pd.isna(value) is True:
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
                    logger.warning('DataElement {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

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
                    if new_char.isnumeric():  # can add integers
                        current_value[new_index] = new_char

                display_value = self.format_date(current_value)
            else:
                display_value = self.format_date(current_value)

            window[elem_key].metadata['value'] = ''.join(current_value)

        elif dtype == 'money':
            current_value = list(window[elem_key].metadata['value'])

            # Remove currency and grouping separator
            #            new_value = value[len(currency_sym):].replace(group_sep, '')
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
            else:  # user replaced a character
                # Find the character and location of the user input
                new_char = None
                new_index = None
                for new_index, new_char in enumerate(new_value):  # defaults to the last character
                    old_char = current_value[new_index]
                    if old_char != new_char:
                        break

                # Validate added character
                if new_char.isnumeric():  # can add integers
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

        elif dtype in settings.supported_float_dtypes:
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

        else:  # remove newline and carriage return characters created by multiline elements for some reason
            display_value = value.rstrip('\n\r')

        return display_value

    def format_display(self):
        """
        Format the parameter's value for displaying.
        """
        dec_sep = settings.decimal_sep
        group_sep = settings.thousands_sep

        dtype = self.dtype
        value = self.value
        options = self.options
        if value == '' or value is None:
            return ''

        if (isinstance(value, float) or isinstance(value, int) or isinstance(value, str)) and dtype == 'money':
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

        elif isinstance(value, float) and dtype != 'money':
            display_value = str(value)

        elif isinstance(value, datetime.datetime):
            if self.disabled is True:  # use global settings to determine how to format date
                display_value = settings.format_display_date(value)
            else:  # enforce ISO formatting if element is editable
                display_value = value.strftime(settings.format_date_str(date_str='YYYY-MM-DD'))

        else:  # remove newline and carriage return characters created by multiline elements for some reason
            aliases = options.get('Aliases', {})
            display_value = aliases.get(value, str(value).rstrip('\n\r'))

        return display_value

    def format_value(self, input_value):
        """
        Set the value of the data element from user input.

        Arguments:

            input_value: value input into the GUI element.
        """
        dparse = dateutil.parser.parse
        group_sep = settings.thousands_sep

        dtype = self.dtype
        options = self.options

        if input_value == '' or pd.isna(input_value):
            return self.value

        try:  # reverse the alias map
            aliases = {j: i for i, j in options['Aliases'].items()}
        except (AttributeError, KeyError):  # no aliases defined
            input_value = input_value
        else:
            try:
                alias_value = aliases[input_value]
            except KeyError:
                logger.debug('DataElement {NAME}: failed to find an alias for value "{VAL}"'
                             .format(NAME=self.name, VAL=input_value))
                input_value = input_value
            else:
                logger.debug('DataElement {NAME}: setting value to "{VAL}" with alias "{ALIAS}"'
                             .format(NAME=self.name, VAL=input_value, ALIAS=alias_value))
                input_value = alias_value

        if dtype in settings.supported_date_dtypes:
            if isinstance(input_value, str):
                try:
                    date_format = self.options['DateFormat']
                except KeyError:
                    logger.warning(
                        'DataElement {NAME}: date was selected for the data element but a date '
                        'format was not provided ... defaulting to "YYYY-MM-DD"'.format(NAME=self.name))
                    year_first = True
                else:
                    year_first = True if date_format[0] == 'Y' else False

                try:
                    value_fmt = dparse(input_value, yearfirst=year_first)
                except (ValueError, TypeError):
                    logger.warning('DataElement {PARAM}: unable to parse date {VAL}'
                                   .format(PARAM=self.name, VAL=input_value))
                    return self.value
            elif isinstance(input_value, datetime.datetime):  # value is already formatted properly
                value_fmt = input_value
            else:
                logger.warning('DataElement {PARAM}: unknown object type for {VAL}'
                               .format(PARAM=self.name, VAL=input_value))
                return self.value
        elif dtype in settings.supported_float_dtypes:
            try:
                value_fmt = float(input_value)
            except (ValueError, TypeError):
                try:
                    value_fmt = float(input_value.replace(group_sep, ''))
                except (ValueError, TypeError, AttributeError):
                    logger.warning('DataElement {PARAM}: unknown object type for parameter value {VAL}'
                                   .format(PARAM=self.name, VAL=input_value))
                    return None
        elif dtype in settings.supported_int_dtypes:
            try:
                value_fmt = int(input_value)
            except (ValueError, TypeError, AttributeError):
                try:
#                    value_fmt = input_value.replace(',', '')
                    value_fmt = int(input_value.replace(',', ''))
                except (ValueError, TypeError):
                    logger.warning('DataElement {PARAM}: unknown object type for parameter value {VAL}'
                                   .format(PARAM=self.name, VAL=input_value))
                    return self.value
        elif dtype in settings.supported_bool_dtypes:
            if isinstance(input_value, bool):
                value_fmt = input_value
            else:
                try:
                    value_fmt = bool(int(input_value))
                except (ValueError, TypeError):
                    value_fmt = bool(input_value)
        else:
            value_fmt = str(input_value).strip()

        logger.debug('DataElement {NAME}: input value "{VAL}" formatted as "{FMT}"'
                     .format(NAME=self.name, VAL=input_value, FMT=value_fmt))

        return value_fmt

    def value_set(self):
        """
        Return True if element has a valid value else False
        """
        if self.value is not None:
            return True
        else:
            return False

    def format_date(self, date_str):
        """
        Forces user input to date element to be in ISO format (YYYY-MM-DD).
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

    def collapse_expand(self, window):
        """
        Hide/unhide element frame.
        """
        hide_key = self.key_lookup('CollapseButton')
        frame_key = self.key_lookup('CollapseFrame')

        if window[frame_key].metadata['visible'] is True:  # already visible, so want to collapse the frame
            logger.debug('DataElement {ELEM}: collapsing filter frame'.format(ELEM=self.name))
            window[hide_key].update(image_data=mod_const.UNHIDE_ICON)
            window[frame_key].update(visible=False)

            window[frame_key].metadata['visible'] = False
        else:  # not visible yet, so want to expand the frame
            logger.debug('DataElement {ELEM}: expanding filter frame'.format(ELEM=self.name))
            window[hide_key].update(image_data=mod_const.HIDE_ICON)
            window[frame_key].update(visible=True)

            window[frame_key].metadata['visible'] = True
