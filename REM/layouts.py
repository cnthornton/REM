"""
REM Layout classes and functions.
"""
import datetime
import dateutil
import PySimpleGUI as sg
import pandas as pd
import re
import REM.data_manipulation as dm
from REM.config import settings
import REM.constants as const
import REM.secondary as win2
import sys


# Schema Layout Classes
class TabItem:
    def __init__(self, rule_name, name, tdict):
        self.name = name
        self.rule_name = rule_name
        element_name = "{RULE} {TAB}".format(RULE=rule_name, TAB=name)
        self.element_name = element_name
        self.element_key = as_key(element_name)
        self.data_elements = ['Table', 'Summary', 'Width', 'Fill']
        self.action_elements = ['Audit', 'Input', 'Add']
        self._actions = ['scan', 'filter']

        self.actions = []
        self.id_format = []

        try:
            self.title = tdict['Title']
        except KeyError:
            self.title = name

        try:
            tables = tdict['DatabaseTables']
        except KeyError:
            msg = ('Configuration Error: tab {NAME}, rule {RULE}: missing required field "DisplayColumns".') \
                .format(NAME=name, RULE=rule_name)
            win2.popup_error(msg)
            sys.exit(1)
        self.db_tables = tables

        try:
            pkey = tdict['IDField']
        except KeyError:
            msg = ('Configuration Error: tab {NAME}, rule {RULE}: missing required field "IDField".') \
                .format(NAME=name, RULE=rule_name)
            win2.popup_error(msg)
            sys.exit(1)
        self.db_key = pkey

        try:
            all_columns = tdict['TableColumns']
        except KeyError:
            msg = ('Configuration Error: tab {NAME}, rule {RULE}: missing required field "DisplayColumns".') \
                .format(NAME=name, RULE=rule_name)
            win2.popup_error(msg)
            sys.exit(1)
        self.db_columns = all_columns

        try:
            display_columns = tdict['DisplayColumns']
        except KeyError:
            msg = ('Configuration Error: tab {NAME}, rule {RULE}: missing required field "DisplayColumns".') \
                .format(NAME=name, RULE=rule_name)
            win2.popup_error(msg)
            sys.exit(1)
        self.display_columns = display_columns

        try:
            actions = tdict['AuditMethods']
        except KeyError:
            self.actions = []
        else:
            for action in actions:
                if action in self._actions:
                    self.actions.append(action)
                else:
                    print('Configuration Warning: tab {NAME}, rule {RULE}: unknown audit method specified {METHOD}'
                          .format(NAME=name, RULE=rule_name, METHOD=action))

        try:
            self.tab_parameters = tdict['TabParameters']
        except KeyError:
            self.tab_parameters = None

        try:
            self.aliases = tdict['Aliases']
        except KeyError:
            self.aliases = []

        try:
            self.codes = tdict['Codes']
        except KeyError:
            self.codes = {}

        try:
            summary_rules = tdict['SummaryRules']
        except KeyError:
            summary_rules = {}
        for summary_name in summary_rules:
            summary_rule = summary_rules[summary_name]
            if 'Reference' not in summary_rule:
                msg = ('Configuration Error: tab {NAME}, rule {RULE}: the parameter "Reference" is required for '
                       'SummaryRule {SUMM}').format(NAME=name, RULE=rule_name, SUMM=summary_rule)
                win2.popup_error(msg)
                sys.exit(1)
            if 'Title' not in summary_rule:
                summary_rule['Title'] = summary_name
        self.summary_rules = summary_rules

        try:
            self.error_rules = tdict['ErrorRules']
        except KeyError:
            self.error_rules = {}

        try:
            filter_rules = tdict['FilterRules']
        except KeyError:
            filter_rules = {}
        for filter_rule in filter_rules:
            if 'Reference' not in filter_rules[filter_rule]:
                msg = ('Configuration Error: tab {NAME}, rule {RULE}: the parameter "Reference" is required for '
                       'FilterRule {FILT}').format(NAME=name, RULE=rule_name, FILT=filter_rule)
                win2.popup_error(msg)
                sys.exit(1)
        self.filter_rules = filter_rules

        try:
            self.id_format = re.findall(r'\{(.*?)\}', tdict['IDFormat'])
        except KeyError:
            msg = ('Configuration Error: tab {NAME}, rule {RULE}: missing required field "IDFormat".') \
                .format(NAME=name, RULE=rule_name)
            win2.popup_error(msg)
            sys.exit(1)

        # Dynamic attributes
        display_header = list(display_columns.keys())
        ncol = len(display_header)
        self.df = pd.DataFrame(dm.create_empty_table(nrow=20, ncol=ncol),
                               columns=display_header)  # initialize with empty table

        self.nerr = 0
        self.audit_performed = False
        self.id_components = []

    def key_lookup(self, element):
        """
        Lookup key for element in schema.
        """
        elements = self.data_elements + self.action_elements
        if element in elements:
            key = as_key('{} {}'.format(self.element_name, element))
        else:
            print('Warning: tab {TAB}, rule {RULE}: element {ELEM} not found in list of sub-elements'
                  .format(TAB=self.name, RULE=self.rule_name, ELEM=element))
            key = None

        return key

    def reset_dynamic_attributes(self):
        """
        Reset class dynamic attributes to default.
        """
        headers = list(self.display_columns.keys())
        ncol = len(headers)
        data = dm.create_empty_table(nrow=20, ncol=ncol)
        self.df = pd.DataFrame(data, columns=headers)
        self.nerr = 0
        self.audit_performed = False
        self.id_components = []

    def resize_elements(self, window, win_size: tuple = None):
        """
        Reset Table Columns widths to default when resized.
        """
        if win_size:
            width, height = win_size
        else:
            width, height = (const.WIN_WIDTH, const.WIN_HEIGHT)

        tbl_key = self.key_lookup('Table')
        fill_key = self.key_lookup('Fill')
        element_key = self.element_key

        # Reset table size
        # for every five-pixel increase in window size, increase tab size by one
        tab_pad = 120
        win_diff = width - const.WIN_WIDTH
        tab_pad = tab_pad + (win_diff / 5)

        tab_width = width - tab_pad if tab_pad > 0 else width
        height = height * 0.5
        nrows = int(height / 40)

        window.bind("<Configure>", window[element_key].Widget.config(width=tab_width))

        fill = 832
        # for every ten pixel increase in window size, increase fill size by one
        tab_fill = tab_width - fill if tab_width > fill else 0
        window[fill_key].set_size((tab_fill, None))

        # Reset table column size
        header = list(self.display_columns.keys())
        lengths = dm.calc_column_widths(header, width=tab_width, pixels=True)
        for col_index, col_name in enumerate(header):
            col_width = lengths[col_index]
            window[tbl_key].Widget.column(col_name, width=col_width)

        window[tbl_key].expand((True, True))
        window[tbl_key].table_frame.pack(expand=True, fill='both')

        window.refresh()

        window[tbl_key].update(num_rows=nrows)

    def update(self, window, element_tup):
        """
        """
        for element, new_param in element_tup:
            element_key = self.key_lookup(element)
            if element_key:
                expression = "window['{}'].update({})".format(element_key, new_param)
                eval(expression)

                print('Info: tab {NAME}, rule {RULE}: updated element {ELEM} to {VAL}'
                      .format(NAME=self.name, RULE=self.rule_name, ELEM=element, VAL=new_param))
            else:
                print('Layout Warning: tab {NAME}, rule {RULE}: element {ELEM} not found in list of sub-elements'
                      .format(NAME=self.name, RULE=self.rule_name, ELEM=element))

    def get_column_name(self, column):
        """
        """
        header = self.df.columns.values.tolist()

        if column in header:
            col_name = column
        elif column.lower() in header:
            col_name = column.lower()
        else:
            print('Warning: tab {NAME}, rule {RULE}: column {COL} not in list of table columns'
                  .format(NAME=self.name, RULE=self.rule_name, COL=column))
            col_name = None

        return col_name

    def format_display_table(self, dataframe, date_fmt: str = '%d-%m-%Y'):
        """
        Format dataframe for displaying in GUI
        """
        relativedelta = dateutil.relativedelta.relativedelta
        strptime = datetime.datetime.strptime
        is_float_dtype = pd.api.types.is_float_dtype
        is_datetime_dtype = pd.api.types.is_datetime64_any_dtype

        display_columns = self.display_columns
        display_header = list(display_columns.keys())
        display_df = pd.DataFrame()

        # Localization specific options
        date_offset = settings.get_date_offset()

        # Subset dataframe by specified columns to display
        for col_name in display_columns:
            col_rule = display_columns[col_name]

            col_to_add = dm.generate_column_from_rule(dataframe, col_rule)
            dtype = col_to_add.dtype
            if is_float_dtype(dtype):
                col_to_add = col_to_add.apply('{:,.2f}'.format)
            elif is_datetime_dtype(dtype):
                col_to_add = col_to_add.apply(lambda x: (strptime(x.strftime(date_fmt), date_fmt) +
                                                         relativedelta(years=+date_offset)).strftime(date_fmt)
                if pd.notnull(x) else '')
            display_df[col_name] = col_to_add

        # Map column values to the aliases specified in the configuration
        for alias_col in self.aliases:
            alias_map = self.aliases[alias_col]  # dictionary of mapped values

            if alias_col not in display_header:
                print('Warning: tab {NAME}, rule {RULE}: alias {ALIAS} not found in the list of display columns'
                      .format(NAME=self.name, RULE=self.rule_name, ALIAS=alias_col))
                continue

            print('Info: tab {NAME}, rule {RULE}: applying aliases {MAP} to {COL}'
                  .format(NAME=self.name, RULE=self.rule_name, MAP=alias_map, COL=alias_col))

            try:
                display_df[alias_col].replace(alias_map, inplace=True)
            except KeyError:
                print('Warning: tab {NAME}, rule {RULE}: alias {ALIAS} not found in the list of display columns'
                      .format(NAME=self.name, RULE=self.rule_name, ALIAS=alias_col))
                continue

        return display_df

    def update_table(self, window):
        """
        Update Table element with data
        """
        tbl_error_col = const.TBL_ERROR_COL
        tbl_key = self.key_lookup('Table')

        # Modify table for displaying
        df = dm.sort_table(self.df, self.db_key)

        display_df = self.format_display_table(df)
        data = display_df.values.tolist()

        window[tbl_key].update(values=data)

        # Highlight rows with identified errors
        errors = self.search_for_errors()
        self.nerr = len(errors)
        error_colors = [(i, tbl_error_col) for i in errors]
        window[tbl_key].update(row_colors=error_colors)
        window.refresh()

    def update_id_components(self, parameters):
        """
        """
        id_format = self.id_format
        self.id_components = []

        last_index = 0
        print('Info: tab {NAME}, rule {RULE}: ID is formatted as {FORMAT}' \
              .format(NAME=self.name, RULE=self.rule_name, FORMAT=id_format))
        param_fields = [i.name for i in parameters]
        for component in id_format:
            if len(component) > 1 and set(component).issubset(set('YMD-/ ')):  # component is datestr
                component_len = len(component)
                index = (last_index, last_index + component_len)
                part_tup = ('date', component, index)
            elif component in self.codes:
                value = self.codes[component]
                component_len = len(value)
                index = (last_index, last_index + component_len)
                part_tup = (component, value, index)
            elif component in param_fields:
                param = parameters[param_fields.index(component)]
                value = param.value
                component_len = len(value)
                index = (last_index, last_index + component_len)
                part_tup = (component, value, index)
            elif component.isnumeric():  # component is an incrementing number
                component_len = len(component)
                index = (last_index, last_index + component_len)
                part_tup = ('variable', component_len, index)
            else:  # unknown component type, probably separator
                component_len = len(component)
                index = (last_index, last_index + component_len)
                part_tup = ('separator', component, index)

            self.id_components.append(part_tup)

            last_index += component_len

        print('Info: tab {NAME}, rule {RULE}: ID updated with components {COMP}'
              .format(NAME=self.name, RULE=self.rule_name, COMP=self.id_components))

    def format_id(self, number, date=None):
        """
        """
        number = str(number)

        id_parts = []
        for component in self.id_components:
            comp_name, comp_value, comp_index = component

            if comp_name == 'date':  # component is datestr
                if not date:
                    print('Warning: tab {NAME}, rule {RULE}: no date provided for ID number {NUM} ... reverting to '
                          'today\'s date'.format(NAME=self.name, RULE=self.rule_name, NUM=number))
                    value = datetime.datetime.now().strftime(comp_value)
                else:
                    value = date
            elif comp_name == 'variable':
                value = number.zfill(comp_value)
            else:
                value = comp_value

            id_parts.append(value)

        return ''.join(id_parts)

    def get_id_component(self, identifier, component):
        """
        Extract the specified component values from the provided identifier.
        """
        comp_value = ''
        for id_component in self.id_components:
            comp_name, comp_value, comp_index = id_component

            if component == comp_name:
                try:
                    comp_value = identifier[comp_index[0]: comp_index[1]]
                except IndexError:
                    print('Warning: ID component {COMP} cannot be found in identifier {IDENT}'
                          .format(COMP=component, IDENT=identifier))

                break

        return comp_value

    def get_component(self, comp_id):
        """
        """
        comp_tup = None
        for component in self.id_components:
            comp_name, comp_value, comp_index = component
            if comp_name == comp_id:
                comp_tup = component

        return comp_tup

    def update_summary(self, window):
        """
        Update Summary element with data summary
        """
        is_numeric_dtype = pd.api.types.is_numeric_dtype
        is_string_dtype = pd.api.types.is_string_dtype
        is_datetime_dtype = pd.api.types.is_datetime64_any_dtype
        is_bool_dtype = pd.api.types.is_bool_dtype

        operators = set('+-*/')

        df = self.df
        summ_rules = self.summary_rules

        outputs = []

        # Total number of rows
        output = (_('Number of rows in table'), df.shape[0])
        outputs.append(output)

        # Total number of errors identified based on specified error rules
        output = (_('Number of errors identified'), self.nerr)
        outputs.append(output)

        # Calculate totals defined by summary rules
        for rule_name in summ_rules:
            summ_rule = summ_rules[rule_name]
            reference = summ_rule['Reference']
            title = summ_rule['Title']

            # Subset df if subset rule provided
            if 'Subset' in summ_rule:
                try:
                    subset_df = dm.subset_dataframe(df, summ_rule['Subset'])
                except Exception as e:
                    print('Warning: tab {NAME}, rule {RULE}: unable to subset dataframe with subset rule {SUB} - {ERR}'
                          .format(NAME=self.name, RULE=self.rule_name, SUB=summ_rule['Subset'], ERR=e))
                    break
            else:
                subset_df = df

            rule_values = []
            for component in dm.parse_operation_string(reference):
                if component in operators:
                    rule_values.append(component)
                    continue

                component_col = self.get_column_name(component)
                if component_col:  # component is header column
                    dtype = subset_df.dtypes[component_col]
                    if is_numeric_dtype(dtype) or is_bool_dtype(dtype):
                        col_summary = subset_df[component_col].sum()
                    elif is_string_dtype(dtype) or is_datetime_dtype(dtype):
                        col_summary = subset_df[component_col].nunique()
                    else:  # possibly empty dataframe
                        col_summary = 0

                    rule_values.append(col_summary)
                else:
                    try:  # component is a number
                        float(component)
                    except ValueError:  # component is an unsupported character
                        print('Warning: tab {NAME}, rule {RULE}: unsupported character "{ITEM}" found in summary rule '
                              '"{SUMM}"'.format(NAME=self.name, RULE=self.rule_name, ITEM=component, SUMM=rule_name))
                        rule_values = [0]
                        break
                    else:
                        rule_values.append(component)

            summary_total = eval(' '.join([str(i) for i in rule_values]))

            outputs.append((title, summary_total))
            summ_rule['Total'] = summary_total

        summary_key = self.key_lookup('Summary')
        window[summary_key].update(value='\n'.join(['{}: {}'.format(*i) for i in outputs]))

    def toggle_actions(self, window, value='enable'):
        """
        Enable / Disable schema action buttons.
        """
        status = False if value == 'enable' else True

        for element in self.action_elements:
            element_tup = [(element, 'disabled={}'.format(status))]
            self.update(window, element_tup)

    def layout(self, win_size: tuple = None):
        """
        GUI layout for the tab item.
        """
        if win_size:
            width, height = win_size
        else:
            width, height = (const.WIN_WIDTH, const.WIN_HEIGHT)

        # Window and element size parameters
        bg_col = const.ACTION_COL

        pad_frame = const.FRAME_PAD
        pad_el = const.ELEM_PAD
        pad_h = const.HORZ_PAD
        font_l = const.LARGE_FONT
        font_m = const.MID_FONT
        in_col = const.INPUT_COL

        tab_width = width - 120 if width >= 200 else width
        tab_fill = tab_width - 832 if tab_width > 832 else 0

        header = self.df.columns.values.tolist()
        data = self.df.values.tolist()

        summary_key = self.key_lookup('Summary')
        audit_key = self.key_lookup('Audit')
        table_key = self.key_lookup('Table')
        add_key = self.key_lookup('Add')
        input_key = self.key_lookup('Input')
        fill_key = self.key_lookup('Fill')
        layout = [[create_table_layout(data, header, table_key, bind=True, height=height, width=tab_width)],
                  [sg.Frame(_('Summary'), [[sg.Multiline('', border_width=0, size=(52, 6), font=font_m, key=summary_key,
                                                         disabled=True, background_color=bg_col)]], font=font_l,
                            pad=((pad_frame, 0), (0, pad_frame)), background_color=bg_col, element_justification='l'),
                   sg.Canvas(key=fill_key, size=(tab_fill, 0), visible=True),
                   sg.Col([[
                       sg.Input('', key=input_key, font=font_l, size=(20, 1), pad=(pad_el, 0), do_not_clear=False,
                                background_color=in_col, disabled=True,
                                tooltip=_('Input document number to add a transaction to the table')),
                       B2(_('Add'), key=add_key, pad=((0, pad_h), 0), tooltip=_('Add order to the table'),
                          disabled=True),
                       B2(_('Audit'), key=audit_key, disabled=True, pad=((0, pad_frame), 0),
                          tooltip=_('Run Audit methods'))
                   ]], vertical_alignment='top', background_color=bg_col)
                   ]]

        return layout

    def row_ids(self):
        """
        Return a list of all row IDs in the dataframe.
        """
        try:
            row_ids = list(self.df[self.db_key])
        except KeyError:  # database probably PostGreSQL
            try:
                row_ids = list(self.df[self.db_key.lower()])
            except KeyError:
                print('Warning: tab {TAB}, rule {RULE}: missing database key {KEY} in column headers'
                      .format(TAB=self.name, RULE=self.rule_name, KEY=self.db_key))
                row_ids = []

        return row_ids

    def filter_statements(self):
        """
        Generate the filter statements for tab query parameters.
        """
        operators = {'>', '>=', '<', '<=', '=', '!=', 'IN', 'in', 'In'}

        params = self.tab_parameters

        filters = []
        for param in params:
            param_rule = params[param]

            param_col = dm.get_query_from_header(param, self.db_columns)
            if not param_col:
                print('Error: rule {RULE}, tab {NAME}: tab parameter {PARAM} not found in TableColumns'
                      .format(RULE=self.rule_name, NAME=self.name, PARAM=param))
                continue

            param_oper = None
            param_values = []
            conditional = dm.parse_operation_string(param_rule, equivalent=False)
            for component in conditional:
                if component in operators:
                    if not param_oper:
                        param_oper = component
                    else:
                        print(
                            'Error: rule {RULE}, tab {NAME}: only one operator allowed in tab parameters for parameter '
                            '{PARAM}'.format(RULE=self.rule_name, NAME=self.name, PARAM=param))
                        break
                else:
                    param_values.append(component)

            if not (param_oper and param_values):
                print('Error: rule {RULE}, tab {NAME}: tab parameter {PARAM} requires both an operator and a value'
                      .format(RULE=self.rule_name, NAME=self.name, PARAM=param))
                break

            if param_oper.upper() == 'IN':
                vals_fmt = ', '.join(['?' for i in param_values])
                filters.append(('{COL} {OPER} ({VALS})'.format(COL=param_col, OPER=param_oper, VALS=vals_fmt),
                                (param_values,)))
            else:
                if len(param_values) == 1:
                    filters.append(('{COL} {OPER} ?'.format(COL=param_col, OPER=param_oper), (param_values[0],)))
                else:
                    print('Error: rule {RULE}, tab {NAME}: tab parameter {PARAM} has too many values {COND}'
                          .format(RULE=self.rule_name, NAME=self.name, PARAM=param, COND=param_rule))
                    break

        return filters

    def search_for_errors(self):
        """
        Use error rules specified in configuration file to annotate rows.
        """
        error_rules = self.error_rules
        df = self.df
        if df.empty:
            return set()

        errors = []

        # Search for errors in the data based on the defined error rules
        print('Info: rule {RULE}, tab {NAME}: searching for errors based on defined error rules {ERR}'
              .format(NAME=self.name, RULE=self.rule_name, ERR=error_rules))
        results = dm.evaluate_rule_set(df, error_rules)  # returns list of booleans
        for row, result in enumerate(results):
            if result is False:
                print('Info: rule {RULE}, tab {NAME}: table row {ROW} failed one or more condition rule'
                      .format(RULE=self.rule_name, NAME=self.name, ROW=row))
                errors.append(row)

        # Search for errors in the transaction ID using ID format
        headers = df.columns.values.tolist()
        pkey = self.db_key if self.db_key in headers else self.db_key.lower()
        try:
            date_cnfg = settings.format_date_str(date_str=self.get_component('date')[1])
        except TypeError:
            date_cnfg = None

        id_list = df[pkey].tolist()
        for index, trans_id in enumerate(id_list):
            trans_number_comp = self.get_id_component(trans_id, 'variable')
            if date_cnfg:
                trans_date_comp = self.get_id_component(trans_id, 'date')
            else:
                trans_date_comp = None

            trans_id_fmt = self.format_id(trans_number_comp, date=trans_date_comp)
            if trans_id != trans_id_fmt:
                print('Info: tab {NAME}, rule {RULE}: transaction ID {ID} does not comply with format specified in the '
                      'configuration'.format(NAME=self.name, RULE=self.rule_name, ID=trans_id))
                if index not in errors:
                    errors.append(index)

        return set(errors)

    def run_audit(self, *args, **kwargs):
        """
        """
        method_map = {'scan': self.scan_for_missing,
                      'filter': self.filter_transactions}

        for action in self.actions:
            print('Info: tab {NAME}, rule {RULE}: running audit method {METHOD}'
                  .format(NAME=self.name, RULE=self.rule_name, METHOD=action))

            action_function = method_map[action]
            try:
                df = action_function(*args, **kwargs)
            except Exception as e:
                print('Warning: tab {NAME}, rule {RULE}: method {METHOD} failed due to {E}'
                      .format(NAME=self.name, RULE=self.rule_name, METHOD=action, E=e))
            else:
                self.df = df

        self.audit_performed = True

    def scan_for_missing(self, *args, **kwargs):
        """
        Search for missing transactions using scan.
        """
        dparse = dateutil.parser.parse
        strptime = datetime.datetime.strptime

        # Arguments
        window = args[0]
        user = kwargs['account']
        audit_params = kwargs['parameters']

        # Class attributes
        pkey = self.get_column_name(self.db_key)
        df = dm.sort_table(self.df, pkey)

        id_list = df[pkey].tolist()
        main_table = [i for i in self.db_tables][0]

        # Format audit parameters
        audit_date = None
        for audit_param in audit_params:
            if audit_param.type.lower() == 'date':
                date_col = audit_param.name
                date_col_full = dm.get_query_from_header(date_col, self.db_columns)
                date_fmt = audit_param.format
                try:
                    audit_date = strptime(audit_param.value, date_fmt)
                except ValueError:
                    print('Warning: rule {RULE}, tab {NAME}: no date provided ... skipping checks for most recent ID'
                          .format(RULE=self.rule_name, NAME=self.name))
                else:
                    audit_date_iso = audit_date.strftime("%Y-%m-%d")

        missing_transactions = []
        # Search for missing data

        try:
            first_id = id_list[0]
        except IndexError:
            first_id = None
        else:
            first_number_comp = int(self.get_id_component(first_id, 'variable'))
            first_date_comp = self.get_id_component(first_id, 'date')
            print('Info: {NAME} Audit: first transaction ID is {ID}'.format(NAME=self.name, ID=first_id))

        if audit_date and first_id:
            ## Find date of last transaction
            query_str = 'SELECT DISTINCT {DATE} FROM {TBL}'.format(DATE=date_col_full, TBL=main_table)
            dates_df = user.thread_transaction(query_str, (), operation='read')

            unq_dates = dates_df[date_col].tolist()
            try:
                unq_dates_iso = [i.strftime("%Y-%m-%d") for i in unq_dates]
            except TypeError:
                print('Warning: {NAME} Audit: date {DATE} is not formatted correctly as a datetime object'
                      .format(NAME=self.name, DATE=audit_date_iso))
                return df

            unq_dates_iso.sort()

            try:
                current_date_index = unq_dates_iso.index(audit_date_iso)
            except ValueError:
                print('Warning: {NAME} Audit: no transactions for audit date {DATE} found in list {DATES}'
                      .format(NAME=self.name, DATE=audit_date_iso, DATES=unq_dates_iso))
                return df

            try:
                prev_date = dparse(unq_dates_iso[current_date_index - 1], yearfirst=True)
            except IndexError:
                print('Warning: {NAME} Audit: no date found prior to current audit date {DATE}'
                      .format(NAME=self.name, DATE=audit_date_iso))
                prev_date = None
            except ValueError:
                print('Warning: {NAME} Audit: unknown format {DATE} provided'
                      .format(NAME=self.name, DATE=unq_dates_iso[current_date_index - 1]))
                prev_date = None

            ## Query last transaction from previous date
            if prev_date:
                print('Info: {NAME} Audit: searching for most recent transaction created in {DATE}'
                      .format(NAME=self.name, DATE=prev_date.strftime('%Y-%m-%d')))

                filters = ('{} = ?'.format(date_col_full), (prev_date.strftime(date_fmt),))
                last_df = user.query(self.db_tables, columns=self.db_columns, filter_rules=filters)
                last_df.sort_values(by=[pkey], inplace=True, ascending=False)

                last_id = None
                prev_ids = last_df[pkey].tolist()
                for prev_id in prev_ids:
                    prev_number_comp = int(self.get_id_component(prev_id, 'variable'))
                    prev_date_comp = self.get_id_component(prev_id, 'date')

                    if prev_number_comp > first_number_comp:
                        continue

                    # Search only for IDs with correct ID formats (skip potential errors)
                    if prev_id == self.format_id(prev_number_comp, date=prev_date_comp):
                        last_id = prev_id
                        break

                if last_id:
                    print('Info: {NAME} Audit: last transaction ID is {ID} from {DATE}' \
                          .format(NAME=self.name, ID=last_id, DATE=prev_date.strftime('%Y-%m-%d')))

                    if first_date_comp != prev_date_comp:  # start of new month
                        if first_number_comp != 1:
                            missing_range = list(range(1, first_number_comp))
                        else:
                            missing_range = []

                    else:  # still in same month
                        if (prev_number_comp + 1) != first_number_comp:  # first not increment of last
                            missing_range = list(range(prev_number_comp + 1, first_number_comp))
                        else:
                            missing_range = []

                    for missing_number in missing_range:
                        missing_id = self.format_id(missing_number, date=first_date_comp)
                        if missing_id not in id_list:
                            missing_transactions.append(missing_id)

            ## Search for missed numbers at end of day
            last_id_of_df = id_list[-1]
            filters = ('{} = ?'.format(date_col_full), (audit_date.strftime(date_fmt),))
            current_df = user.query(self.db_tables, columns=self.db_columns, filter_rules=filters)
            current_df.sort_values(by=[pkey], inplace=True, ascending=False)

            current_ids = current_df[pkey].tolist()
            for current_id in current_ids:
                if last_id_of_df == current_id:
                    break

                current_number_comp = int(self.get_id_component(current_id, 'variable'))
                if current_id == self.format_id(current_number_comp, date=first_date_comp):
                    missing_transactions.append(current_id)

        ## Search for skipped transaction numbers
        try:
            id_list[1]
        except IndexError:
            pass
        else:
            prev_number = first_number_comp
            for transaction_id in id_list[1:]:
                trans_number = int(self.get_id_component(transaction_id, 'variable'))
                if (prev_number + 1) != trans_number:
                    missing_range = list(range(prev_number + 1, trans_number))
                    for missing_number in missing_range:
                        missing_id = self.format_id(missing_number, date=first_date_comp)
                        if missing_id not in id_list:
                            missing_transactions.append(missing_id)

                prev_number = trans_number

        print('Info: {NAME} Audit: potentially missing transactions: {MISS}'
              .format(NAME=self.name, MISS=missing_transactions))

        # Query database for the potentially missing transactions
        if missing_transactions:
            pkey_fmt = dm.get_query_from_header(pkey, self.db_columns)

            filter_values = ['?' for i in missing_transactions]
            filter_str = '{PKEY} IN ({VALUES})'.format(PKEY=pkey_fmt, VALUES=', '.join(filter_values))

            filters = [(filter_str, tuple(missing_transactions))]

            # Drop missing transactions if they don't meet tab parameter requirements
            filters += self.filter_statements()

            missing_df = user.query(self.db_tables, columns=self.db_columns, filter_rules=filters, order=pkey_fmt)
        else:
            missing_df = pd.DataFrame(columns=df.columns)

        # Display import window with potentially missing data
        if not missing_df.empty:
            missing_df_fmt = self.format_display_table(dm.sort_table(missing_df, pkey))
            import_rows = win2.import_window(missing_df_fmt, win_size=window.size)
            import_df = missing_df.iloc[import_rows]

            # Update dataframe with imported data
            if not import_df.empty:
                df = dm.append_to_table(self.df, import_df)

        print('Info: new size of {0} dataframe is {1} rows and {2} columns'.format(self.name, *df.shape))

        return df

    def filter_transactions(self, *args, **kwargs):
        """
        Filter pandas dataframe using the filter rules specified in the configuration.
        """
        # Tab attributes
        filter_rules = self.filter_rules
        df = self.df.copy()

        if df.empty or not filter_rules:
            return df

        print('Info: tab {NAME}, rule {RULE}: running filter duplicates method with filter rules {RULES}'
              .format(NAME=self.name, RULE=self.rule_name, RULES=list(filter_rules.values())))

        for filter_number in filter_rules:
            filter_rule = filter_rules[filter_number]['Reference']
            try:
                filter_key = filter_rules[filter_number]['Key']
            except KeyError:
                filter_key = None

            try:
                filter_cond = dm.evaluate_rule(df, filter_rule, as_list=False)
            except Exception as e:
                print('Info: tab {NAME}, rule {RULE}: filtering duplicates with rule {NO} failed due to {ERR}'
                      .format(NAME=self.name, RULE=self.rule_name, NO=filter_number, ERR=e))
                continue

            if filter_key:
                cond_str = '(df.duplicated(subset=["{KEY}"], keep=False)) & (filter_cond)'.format(KEY=filter_key)
            else:
                cond_str = '(filter_cond)'.format(KEY=filter_key, RES=filter_cond)

            try:
                print(cond_str)
                failed = eval('df[{}].index'.format(cond_str))
            except Exception as e:
                print('Info: tab {NAME}, rule {RULE}: filtering duplicates with rule {NO} failed due to {ERR}'
                      .format(NAME=self.name, RULE=self.rule_name, NO=filter_number, ERR=e))
                continue

            df.drop(failed, axis=0, inplace=True)
            df.reset_index(drop=True, inplace=True)

        return df


def as_key(key):
    """
    Format string as element key.
    """
    return '-{}-'.format(key).replace(' ', ':').upper()


# GUI Element Functions
def B1(*args, **kwargs):
    """
    Action button element defaults.
    """
    size = const.B1_SIZE
    return sg.Button(*args, **kwargs, size=(size, 1))


def B2(*args, **kwargs):
    """
    Panel button element defaults.
    """
    size = const.B2_SIZE
    return sg.Button(*args, **kwargs, size=(size, 1))


def create_table_layout(data, header, keyname, events: bool = False, bind: bool = False, tooltip: str = None,
                        nrow: int = None, height: int = 800, width: int = 1200, font: tuple = None, pad: tuple = None,
                        add_key: str = '', delete_key: str = '', table_name: str = ''):
    """
    Create table elements that have consistency in layout.
    """
    # Element settings
    text_col = const.TEXT_COL
    alt_col = const.TBL_ALT_COL
    bg_col = const.TBL_BG_COL
    select_col = const.TBL_SELECT_COL
    header_col = const.HEADER_COL

    pad_frame = const.FRAME_PAD

    pad = pad if pad else (pad_frame, pad_frame)

    font = font if font else const.MID_FONT
    bold_font = const.BOLD_FONT
    font_size = font[1]

    # Arguments
    row_height = const.TBL_ROW_HEIGHT
    width = width
    height = height * 0.5
    nrow = nrow if nrow else int(height / 40)

    # Parameters
    if events and bind:
        bind = False  # only one can be selected at a time
        print('Warning: both bind_return_key and enable_events have been selected during table creation. '
              'These parameters are mutually exclusive.')

    lengths = dm.calc_column_widths(header, width=width, font_size=font_size, pixels=False)

    header_layout = []
    balance_layout = []
    if add_key:
        header_layout.append(sg.Button('', key=add_key, image_data=const.ADD_ICON, border_width=2,
                                       button_color=(text_col, alt_col), tooltip='Add new row to table'))
        balance_layout.append(sg.Canvas(size=(24, 0), visible=True, background_color=header_col))
    if delete_key:
        header_layout.append(sg.Button('', key=delete_key, image_data=const.MINUS_ICON, border_width=2,
                                       button_color=(text_col, alt_col), tooltip='Remove selected row from table'))
        balance_layout.append(sg.Canvas(size=(24, 0), visible=True, background_color=header_col))

    if table_name or len(header_layout) > 0:
        layout = sg.Frame('', [
            [sg.Col([header_layout], justification='l', background_color=header_col, expand_x=True),
             sg.Col([[sg.Text(table_name, pad=(0, 0), font=bold_font, background_color=alt_col)]],
                    justification='c', background_color=header_col, expand_x=True),
             sg.Col([balance_layout], justification='r', background_color=header_col)],
            [sg.Table(data, key=keyname, headings=header, pad=(0, 0), num_rows=nrow,
                      row_height=row_height, alternating_row_color=alt_col, background_color=bg_col,
                      text_color=text_col, selected_row_colors=(text_col, select_col), font=font,
                      display_row_numbers=False, auto_size_columns=False, col_widths=lengths,
                      enable_events=events, bind_return_key=bind, tooltip=tooltip, vertical_scroll_only=False)]
        ], pad=pad, element_justification='l', vertical_alignment='t', background_color=alt_col, relief='ridge')
    else:
        layout = sg.Table(data, key=keyname, headings=header, pad=pad, num_rows=nrow, row_height=row_height,
                          alternating_row_color=alt_col, background_color=bg_col,
                          text_color=text_col, selected_row_colors=(text_col, select_col), font=font,
                          display_row_numbers=False, auto_size_columns=False, col_widths=lengths,
                          enable_events=events, bind_return_key=bind, tooltip=tooltip,
                          vertical_scroll_only=False)

    return layout


def importer_layout(db_tables, win_size: tuple = None):
    """
    Create the layout for the database import window.
    """
    if win_size:
        width, height = win_size
    else:
        width, height = (int(const.WIN_WIDTH * 0.8), int(const.WIN_HEIGHT * 0.8))

    # Layout settings
    header_col = const.HEADER_COL
    bg_col = const.ACTION_COL
    def_col = const.DEFAULT_COL
    select_col = const.SELECT_TEXT_COL
    text_col = const.TEXT_COL

    pad_el = const.ELEM_PAD
    pad_v = const.VERT_PAD
    pad_frame = const.FRAME_PAD

    font_h = const.HEADER_FONT
    font_main = const.MAIN_FONT
    font_large = const.LARGE_FONT

    bwidth = 0.5

    file_types = ['xls', 'csv/tsv']
    encodings = ['Default']

    header_req = ['Table Column Name', 'Data Type', 'Default Value']
    header_map = ['Table Column Name', 'Data Type', 'File Column Name']

    p1 = [[sg.Col([[sg.Text('File:', size=(5, 1), pad=((0, pad_el), 0), background_color=bg_col),
                    sg.Input('', key='-FILE-', size=(60, 1), pad=(pad_el, 0), background_color=header_col),
                    sg.FileBrowse('Browse ...', pad=((pad_el, pad_frame), 0))]],
                  pad=(pad_frame, pad_frame), justification='l', background_color=bg_col)],
          [sg.Frame('File format', [
              [sg.Canvas(size=(int(width * 0.85), 0), pad=(0, pad_v), visible=True, background_color=bg_col)],
              [sg.Col([
                  [sg.Text('Format:', size=(16, 1), pad=(pad_el, pad_el), background_color=bg_col),
                   sg.Combo(file_types, key='-FORMAT-', default_value='xls', size=(12, 1),
                            pad=(pad_el, pad_el), background_color=header_col),
                   sg.Text('', size=(10, 1), background_color=bg_col),
                   sg.Text('Newline Separator:', size=(16, 1), pad=(pad_el, pad_el), background_color=bg_col),
                   sg.Input('\\n', key='-NSEP-', size=(8, 1), pad=(pad_el, pad_el), disabled=True,
                            background_color=header_col)],
                  [sg.Text('Encoding:', size=(16, 1), pad=(pad_el, 0), background_color=bg_col),
                   sg.Combo(encodings, key='-ENCODE-', default_value='Default', size=(12, 1), pad=(pad_el, pad_el),
                            background_color=header_col),
                   sg.Text('', size=(10, 1), background_color=bg_col),
                   sg.Text('Field Separator:', size=(16, 1), pad=(pad_el, pad_el), background_color=bg_col),
                   sg.Input('\\t', key='-FSEP-', size=(8, 1), pad=(pad_el, pad_el), disabled=True,
                            background_color=header_col)]],
                  pad=(pad_frame, 0), background_color=bg_col)],
              [sg.Canvas(size=(int(width * 0.85), 0), pad=(0, pad_v), visible=True, background_color=bg_col)]
          ],
                    pad=(pad_frame, pad_frame), border_width=bwidth, background_color=bg_col, title_color=select_col,
                    relief='groove')],
          [sg.Frame('Formatting options', [
              [sg.Canvas(size=(int(width * 0.85), 0), pad=(0, pad_v), visible=True, background_color=bg_col)],
              [sg.Col([
                  [sg.Checkbox('Recognize dates', key='-DATES-', pad=(0, pad_el), default=True, font=font_main,
                               background_color=bg_col)],
                  [sg.Checkbox('Recognize integers', key='-INTS-', pad=(0, pad_el), default=True,
                               font=font_main, background_color=bg_col)],
                  [sg.Text('Skip n rows at top:', size=(28, 1), pad=(0, pad_el), background_color=bg_col,
                           font=font_main),
                   sg.Input('0', key='-TSKIP-', size=(8, 1), pad=(0, pad_el), font=font_main,
                            background_color=header_col)],
                  [sg.Text('Skip n rows at bottom:', size=(28, 1), pad=(0, pad_el), background_color=bg_col,
                           font=font_main),
                   sg.Input('0', key='-BSKIP-', size=(8, 1), pad=(0, pad_el), font=font_main,
                            background_color=header_col)],
                  [sg.Text('header row (0 indexed):', size=(28, 1), pad=(0, pad_el), background_color=bg_col,
                           font=font_main),
                   sg.Input('0', key='-HROW-', size=(8, 1), pad=(0, pad_el), font=font_main,
                            background_color=header_col)],
                  [sg.Text('Thousands separator:', size=(28, 1), pad=(0, pad_el), background_color=bg_col,
                           font=font_main),
                   sg.Input(',', key='-TSEP-', size=(8, 1), pad=(0, pad_el), font=font_main,
                            background_color=header_col)],
                  [sg.Checkbox('Trim white-space around field values', key='-WHITESPACE-', pad=(0, pad_el),
                               default=True, font=font_main, background_color=bg_col)]],
                  pad=(pad_frame, 0), background_color=bg_col)],
              [sg.Canvas(size=(int(width * 0.85), 0), pad=(0, pad_v), visible=True, background_color=bg_col)]
          ],
                    pad=(pad_frame, pad_frame), border_width=bwidth, background_color=bg_col, title_color=select_col,
                    relief='groove')]]
    p2 = [[sg.Col([[sg.Text('Database Table:', size=(20, 1), pad=((0, pad_el), 0), background_color=bg_col),
                    sg.Combo(db_tables, key='-TABLE-', size=(28, 1), pad=(pad_el, 0), enable_events=True,
                             background_color=header_col)],
                   [sg.Checkbox('Replace table data (default: append to the end)', pad=(0, (pad_el, 0)),
                                default=False, font=font_main, background_color=bg_col)]],
                  pad=(pad_frame, pad_frame), justification='l', background_color=bg_col)],
          [sg.Frame('Required columns', [
              [sg.Canvas(size=(int(width * 0.85), 0), pad=(0, pad_v), visible=True, background_color=bg_col)],
              [sg.Col([
                  [sg.Listbox(values=[], key='-REQLIST-', size=(25, 8), pad=((0, pad_frame), 0), font=font_main,
                              background_color=bg_col, bind_return_key=True,
                              tooltip='Double-click on a column name to add the column to the table'),
                   create_table_layout([[]], header_req, '-REQCOL-', events=True, pad=(0, 0), nrow=4,
                                       width=width * 0.65, tooltip='Click on a row to edit the row fields')]],
                  pad=(pad_frame, 0), background_color=bg_col)],
              [sg.Canvas(size=(int(width * 0.85), 0), pad=(0, pad_v), visible=True, background_color=bg_col)]],
                    pad=(pad_frame, pad_frame), border_width=bwidth, background_color=bg_col, title_color=select_col,
                    relief='groove')],
          [sg.Frame('Column mapping', [
              [sg.Canvas(size=(int(width * 0.85), 0), pad=(0, pad_v), visible=True, background_color=bg_col)],
              [sg.Col([
                  [sg.Listbox(values=[], key='-MAPLIST-', size=(25, 8), pad=((0, pad_frame), 0), font=font_main,
                              background_color=bg_col, bind_return_key=True,
                              tooltip='Double-click on a column name to add the column to the table'),
                   create_table_layout([[]], header_map, '-MAPCOL-', events=True, pad=(0, 0), nrow=4,
                                       width=width * 0.65, tooltip='Click on a row to edit the row fields')]],
                  pad=(pad_frame, 0), background_color=bg_col)],
              [sg.Canvas(size=(int(width * 0.85), 0), pad=(0, pad_v), visible=True, background_color=bg_col)]],
                    pad=(pad_frame, pad_frame), border_width=bwidth, background_color=bg_col, title_color=select_col,
                    relief='groove')]]
    p3 = [[sg.Frame('Preview', [
        [sg.Canvas(size=(int(width * 0.85), 0), pad=(0, pad_v), visible=True, background_color=bg_col)],
        [sg.Col([
            [create_table_layout([[]], ['{}'.format(i) for i in range(1)], '-PREVIEW-', pad=(0, 0), nrow=15,
                                 width=width * 0.94)]],
            pad=(pad_frame, 0), background_color=bg_col)],
        [sg.Canvas(size=(int(width * 0.85), 0), pad=(0, pad_v), visible=True, background_color=bg_col)]],
                    pad=(pad_frame, pad_frame), border_width=bwidth, background_color=bg_col, title_color=select_col,
                    relief='groove')]]

    panels = [sg.Col(p1, key='-P1-', background_color=bg_col, vertical_alignment='c', visible=True, expand_y=True,
                     expand_x=True),
              sg.Col(p2, key='-P2-', background_color=bg_col, vertical_alignment='c', visible=False, expand_y=True,
                     expand_x=True),
              sg.Col(p3, key='-P3-', background_color=bg_col, vertical_alignment='c', visible=False, expand_y=True,
                     expand_x=True)]

    bttn_layout = [[B2(_('Back'), key='-BACK-', pad=(pad_el, 0), disabled=True, tooltip=_('Return to last step')),
                    B2(_('Next'), key='-NEXT-', pad=(pad_el, 0), disabled=False, tooltip=_('Proceed to next step')),
                    B2(_('Import'), bind_return_key=True, key='-IMPORT-', pad=(pad_el, 0), disabled=True,
                       tooltip=_('Import file contents into the selected database table')),
                    B2(_('Cancel'), key='-CANCEL-', pad=(pad_el, 0), disabled=False, tooltip=_('Cancel import'))]]

    sidebar_layout = [
        [sg.Col([[sg.Canvas(size=(0, height * 0.8), background_color=def_col)]], background_color=def_col),
         sg.Col([[sg.Text('• ', pad=((pad_frame, pad_el), (pad_frame, pad_el)), font=font_large),
                  sg.Text('Import data', key='-PN1-', pad=((pad_el, pad_frame), (pad_frame, pad_el)),
                          font=font_main, text_color=select_col)],
                 [sg.Text('• ', pad=((pad_frame, pad_el), pad_el), font=font_large),
                  sg.Text('Database table', key='-PN2-', pad=((pad_el, pad_frame), pad_el), font=font_main)],
                 [sg.Text('• ', pad=((pad_frame, pad_el), pad_el), font=font_large),
                  sg.Text('Preview', key='-PN3-', pad=((pad_el, pad_frame), pad_el), font=font_main)]],
                background_color=def_col, element_justification='l', vertical_alignment='t', expand_y=True)]]

    panel_layout = [[sg.Col([[sg.Canvas(size=(0, height * 0.8), background_color=bg_col)]], background_color=bg_col),
                     sg.Col([[sg.Pane(panels, key='-PANELS-', orientation='horizontal', show_handle=False,
                                      border_width=0, relief='flat')]], pad=(0, pad_v), expand_x=True)]]

    layout = [[sg.Col([[sg.Text('Import into Database Table', pad=(pad_frame, (pad_frame, pad_v)),
                                font=font_h, background_color=header_col)]],
                      pad=(0, 0), justification='l', background_color=header_col, expand_x=True, expand_y=True)],
              [sg.Frame('', sidebar_layout, border_width=bwidth, title_color=text_col, relief='solid',
                        background_color=def_col),
               sg.Frame('', panel_layout, border_width=bwidth, title_color=text_col, relief='solid',
                        background_color=bg_col)],
              [sg.Col(bttn_layout, justification='r', pad=(pad_frame, (pad_v, pad_frame)))]]

    return layout


# Panel layouts
def home_screen(win_size: tuple = None):
    """
    Create layout for the home screen.
    """
    if win_size:
        width, height = win_size
    else:
        width, height = (const.WIN_WIDTH, const.WIN_HEIGHT)

    layout = sg.Col([[sg.Image(filename=settings.logo, size=(int(width * 0.6), int(height * 0.6)))]], key='-HOME-',
                    element_justification='c', vertical_alignment='c')

    return layout


def action_layout(account_methods):
    """
    Create layout for the home panel.
    """
    # Layout settings
    bg_col = const.ACTION_COL
    pad_frame = const.FRAME_PAD
    pad_el = const.ELEM_PAD
    pad_v = const.VERT_PAD

    # Button layout
    buttons = [[sg.Text('', pad=(pad_frame, 0), size=(0, 0), background_color=bg_col)]]

    for account_method in account_methods:
        menu = [account_method.name]
        for rule in account_method.rules:
            menu.append(rule.title)

        rule_el = [BM1(account_method.name, menu, pad=(pad_frame, pad_el), disabled=True)]
        buttons.append(rule_el)

    other_bttns = [[sg.HorizontalSeparator(pad=(pad_frame, pad_v))],
                   #                   [B1(_('Update Database'), key='-DB-', pad=(pad_frame, pad_el), disabled=True)],
                   [B1(_('Update Database'), key='-DB-', pad=(pad_frame, pad_el), disabled=True)],
                   [sg.HorizontalSeparator(pad=(pad_frame, pad_v))],
                   [B1(_('Summary Statistics'), key='-STATS-', pad=(pad_frame, pad_el), disabled=True)],
                   [B1(_('Summary Reports'), key='-REPORTS-', pad=(pad_frame, pad_el), disabled=True)],
                   [sg.Text('', pad=(pad_frame, 0), size=(0, 0), background_color=bg_col)]]

    buttons += other_bttns

    layout = sg.Col([[sg.Frame('', buttons, element_justification='center', relief='raised', background_color=bg_col)]],
                    key='-ACTIONS-', vertical_alignment='b', justification='c', expand_y=True)

    return layout


def tab_layout(tabs, win_size: tuple = None, initial_visibility='first'):
    """
    Layout of the audit panel tab groups.
    """
    if not win_size:
        win_size = (const.WIN_WIDTH, const.WIN_HEIGHT)

    # Element parameters
    bg_col = const.ACTION_COL

    # Populate tab layouts with elements
    layout = []
    for i, tab in enumerate(tabs):  # iterate over audit rule tabs / items
        tab_name = tab.title
        tab_key = tab.element_key

        # Enable only the first tab to start
        if initial_visibility == 'first':
            visible = True if i == 0 else False
        else:
            visible = True

        # Generate the layout
        tab_layout = tab.layout()

        layout.append(sg.Tab(tab_name, tab_layout, key=tab_key, visible=visible, background_color=bg_col))

    return layout
