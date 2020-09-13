"""
REM Layout classes and functions.
"""
import datetime
import dateutil
import PySimpleGUI as sg
import numpy as np
import pandas as pd
import re
import REM.configuration as config
import REM.data_manipulation as dm
import REM.program_settings as const
import REM.secondary_win as win2
import sys
import threading


# Schema Layout Classes
class TabItem:
    def __init__(self, rule_name, name, tdict):
        self.name = name
        self.rule_name = rule_name
        element_name = "{RULE} {TAB}".format(RULE=rule_name, TAB=name)
        self.element_name = element_name
        self.element_key = as_key(element_name)
        self.data_elements = ['Table', 'Summary']
        self.action_elements = ['Audit', 'Input', 'Add']
        self._actions = ['scan', 'filter']

        self.actions = []
        self.id_format = []

        try:
            tables = tdict['DatabaseTables']
        except KeyError:
            msg = ('Configuration Error: tab {NAME}, rule {RULE}: missing '\
                   'required field "DisplayColumns".')\
                   .format(NAME=name, RULE=rule_name)
            win2.popup_error(msg)
            sys.exit(1)
        self.db_tables = tables

        try:
            pkey = tdict['IDField']
        except KeyError:
            msg = ('Configuration Error: tab {NAME}, rule {RULE}: missing '\
                   'required field "IDField".')\
                   .format(NAME=name, RULE=rule_name)
            win2.popup_error(msg)
            sys.exit(1)
        self.db_key = pkey

        try:
            all_columns = tdict['TableColumns']
        except KeyError:
            msg = ('Configuration Error: tab {NAME}, rule {RULE}: missing '\
                   'required field "DisplayColumns".')\
                   .format(NAME=name, RULE=rule_name)
            win2.popup_error(msg)
            sys.exit(1)
        self.db_columns = all_columns

        try:
            display_columns = tdict['DisplayColumns']
        except KeyError:
            msg = ('Configuration Error: tab {NAME}, rule {RULE}: missing '\
                   'required field "DisplayColumns".')\
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
                    print('Configuration Warning: tab {NAME}, rule {RULE}: '\
                          'unknown audit method specified {METHOD}'\
                          .format(Name=name, RULE=rule_name, METHOD=action))

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
            self.summary_rules = tdict['SummaryRules']
        except KeyError:
            self.summary_rules = {}

        try:
            self.error_rules = tdict['ErrorRules']
        except KeyError:
            self.error_rules = {}

        try:
            self.filter_rules = tdict['FilterRules']
        except KeyError:
            self.filter_rules = {}

        try:
            self.id_format = re.findall(r'\{(.*?)\}', tdict['IDFormat'])
        except KeyError:
            msg = ('Configuration Error: tab {NAME}, rule {RULE}: missing '\
                   'required field "IDFormat".')\
                   .format(NAME=name, RULE=rule_name)
            win2.popup_error(msg)
            sys.exit(1)

        # Dynamic attributes
        display_headers = list(display_columns.keys())
        ncol = len(display_headers)
        self.df = pd.DataFrame(empty_data_table(nrow=20, ncol=ncol), \
            columns=display_headers)  #initialize with an empty table

        self.nerr = 0
        self.audit_performed = False
        self.id_components =[]

    def reset_dynamic_attributes(self):
        """
        Reset class dynamic attributes to default.
        """
        headers = list(self.display_columns.keys())
        ncol = len(headers)
        data = empty_data_table(nrow=20, ncol=ncol)
        self.df = pd.DataFrame(data, columns=headers)
        self.nerr = 0
        self.audit_performed = False
        self.id_components =[]

    def reset_column_widths(self, window):
        """
        Reset Table Columns widths to default when resized.
        """
        headers = list(self.display_columns.keys())
        lengths = calc_column_widths(headers, pixels=True)
        table_key = self.key_lookup('Table')

        for col_index, col_name in enumerate(headers):
            col_width = lengths[col_index]
            window[table_key].Widget.column(col_name, width=col_width)

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
                      .format(Name=self.name, RULE=self.rule_name, ELEM=element))

    def get_query_column(self, colname):
        """
        Find full query column (Table + Column) from the column name.
        """
        table_columns = self.db_columns

        full_col_name = None
        for table_column in table_columns:
            try:
                table_comp, col_comp = table_column.split('.')
            except IndexError:  #use main table as table portion of full name
                col_comp = table_column
                table_comp = [i for i in self.db_tables][0]

            col_comp_alias = col_comp.split('AS')[-1]
            if colname in (col_comp_alias, col_comp_alias.lower()):
                full_col_name = '{}.{}'.format(table_comp, col_comp)
                break

        if not full_col_name:
            print('Warning: tab {NAME}, rule {RULE}: unable to find column {COL} in list of table columns'
                  .format(NAME=self.name, RULE=self.rule_name, COL=colname))

        return(full_col_name)

    def get_column_name(self, header):
        """
        """
        headers = self.df.columns.values.tolist()

        if header in headers:
            col_name = header
        elif header.lower() in headers:
            col_name = header.lower()
        else:
            print('Warning: tab {NAME}, rule {RULE}: column {COL} not in list of table columns'
                  .format(NAME=self.name, RULE=self.rule_name, COL=header))
            col_name = None

        return(col_name)

    def format_display_table(self, dataframe):
        """
        """
        operators = set('+-*/')
        chain_operators = ('or', 'and', 'OR', 'AND', 'Or', 'And')

        display_columns = self.display_columns
        display_df = pd.DataFrame()

        # Subset dataframe by specified columns to display
        orig_cols = {}
        for col_name in display_columns:
            col_rule = display_columns[col_name]
            col_list = [i.strip() for i in re.split('{}'.format('|'.join([' {} '.format(i) for i in chain_operators])),
                                                    col_rule)]  #only return column names
            col_oper_list = dm.parse_operation_string(col_rule)

            if len(col_list) > 1:  #column to display is custom
                merge_cols = []
                agg_func = sum
                for i, merge_col in enumerate(col_list):
                    merge_col_fmt = self.get_column_name(merge_col)
                    try:
                        dataframe[merge_col_fmt] = dm.fill_na(dataframe, merge_col_fmt)
                    except KeyError:  #column not in table
                        continue

                    merge_cols.append(merge_col_fmt)
                    orig_cols[merge_col] = col_name

                    # Determine data type of columns and aggregation function 
                    # to use
                    if i == 0:  #base dtype on first column in list
                        dtype = dataframe.dtypes[merge_col_fmt]
                        if dtype in (np.int64, np.float64):
                            agg_func = sum
                        elif dtype == np.object:
                            agg_func = ' '.join
                    else:
                        if dtype != dataframe.dtypes[merge_col_fmt]:
                            print('Warning: tab {NAME}, rule {RULE}: attempting to combine columns of different type'
                                  .format(NAME=self.name, RULE=self.rule_name))
                            print('... changing data type of columns {COLS} to object'
                                  .format(COLS=col_list))
                            dtype = np.object
                            agg_func = ' '.join
                            for item in col_list:
                                dataframe[item].astype('object')

                try:
                    display_df[col_name] = dataframe[merge_cols].agg(agg_func, axis=1)
                except Exception:
                    print(display_df.head)
                    print(merge_cols, dtype, agg_func)
                    raise Exception
            elif len(col_oper_list) > 1:
                col_to_add = dm.evaluate_rule(dataframe, col_oper_list)
            else:  #column to display already exists in table
                orig_cols[col_rule] = col_name

                col_to_add = self.get_column_name(col_rule)
                try:
                    display_df[col_name] = dm.fill_na(dataframe, col_to_add)
                except KeyError:
                    continue

        # Map column values to the aliases specified in the configuration
        for alias_col in self.aliases:
            alias_map = self.aliases[alias_col]  #dictionary of mapped values

            try:
                alias_col_trans = orig_cols[alias_col]
            except KeyError:
                print('Warning: tab {NAME}, rule {RULE}: alias {ALIAS} not found in the list of display columns'
                      .format(NAME=self.name, RULE=self.rule_name, ALIAS=alias_col))
                continue

            print('Info: tab {NAME}, rule {RULE}: applying aliases {MAP} to {COL}'
                  .format(NAME=self.name, RULE=self.rule_name, MAP=alias_map, COL=alias_col_trans))

            try:
                display_df[alias_col_trans] = display_df[alias_col_trans].map(alias_map)
            except KeyError:
                print('Warning: tab {NAME}, rule {RULE}: alias {ALIAS} not found in the list of display columns'
                      .format(NAME=self.name, RULE=self.rule_name, ALIAS=alias_col))
                continue
            else:
                display_df[alias_col_trans].fillna(display_df[alias_col_trans], inplace=True)

        return(display_df)

    def append_to_table(self, add_df):
        """
        Append new rows to dataframe.
        """

        df = self.df
        if add_df.empty:
            return(df)

        # Add row information to the table
        if not add_df.dtypes.equals(df.dtypes):
            print('Warning: appending row has some dtypes that are different from the dataframe dtypes')
            wrong_types = []
            for header in add_df.columns.tolist():
                new_dtype = add_df[header].dtypes
                tab_dtype = df[header].dtypes

                print('Info: comparing data type of {COL} with dtype {TYPEN} to dtype {TYPEO}'
                      .format(COL=header, TYPEN=new_dtype, TYPEO=tab_dtype))
                if new_dtype != tab_dtype:
                    print(
                        'Warning: trying to append new row with column {COL} having a non-matching data type. '
                        'Coercing datatype to {TYPE}'.format(COL=header, TYPE=tab_dtype))
                    wrong_types.append(header)

            # Set data type to df column data type
            try:
                add_df = add_df.astype(df[wrong_types].dtypes.to_dict(), errors='raise')
            except Exception as e:
                print('Error: unable to add new row due to: {}'.format(e))
                add_df = None

        append_df = df.append(add_df, ignore_index=True, sort=False)

        return(self.sort_table(append_df))

    def update_table(self, window):
        """
        Update Table element with data
        """
        tbl_error_col = const.TBL_ERROR_COL
        tbl_key = self.key_lookup('Table')

        # Modify table for displaying
        df = self.sort_table(self.df)

        display_df = self.format_display_table(df)
        data = display_df.values.tolist()

        window[tbl_key].update(values=data)

        # Highlight rows with identified errors
        errors = self.search_for_errors()
        self.nerr = len(errors)
        error_colors = [(i, tbl_error_col) for i in errors]
        window[tbl_key].update(row_colors=error_colors)

    def update_id_components(self, parameters):
        """
        """
        id_format = self.id_format
        self.id_components = []

        last_index = 0
        print('Info: tab {NAME}, rule {RULE}: ID is formatted as {FORMAT}'\
            .format(NAME=self.name, RULE=self.rule_name, FORMAT=id_format))
        param_fields = [i.name for i in parameters]
        for component in id_format:
            if len(component) > 1 and set(component).issubset(set('YMD-/ ')):  #component is datestr
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
            elif component.isnumeric():  #component is an incrementing number
                component_len = len(component)
                index = (last_index, last_index + component_len)
                part_tup = ('variable', component_len, index)
            else:  #unknown component type, probably separator
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

            if comp_name == 'date':  #component is datestr
                if not date:
                    print('Warning: tab {NAME}, rule {RULE}: no date provided for ID number {NUM} ... reverting to '
                          'today\'s date'.format(NAME=self.name, RULE=self.rule_name, NUM=number))
                    value = datetime.datetime.now().strftime(strfmt)
                else:
                    value = date
            elif comp_name == 'variable':
                value = number.zfill(comp_value)
            else:
                value = comp_value

            id_parts.append(value)

        return(''.join(id_parts))

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

        return(comp_value)

    def get_component(self, comp_id):
        """
        """
        comp_tup = None
        for component in self.id_components:
            comp_name, comp_value, comp_index = component
            if comp_name == comp_id:
                comp_tup = component

        return(comp_tup)

    def update_summary(self, window):
        """
        Update Summary element with data summary
        """
        operators = set('+-*/')

        df = self.df
        headers = df.columns.values.tolist()
        summ_rules = self.summary_rules

        outputs = []
        # Total number of rows
        output = (_('Number of rows in table'), df.shape[0])
        outputs.append(output)

        # Total number of errors identified based on specified error rules
        output = (_('Number of errors identified'), self.nerr)
        outputs.append(output)

        # Summarize all headers
        totals = {}
        for header in headers:
            # Determine object type of the values in each column
            dtype = df.dtypes[header]
            if np.issubdtype(dtype, np.integer) or \
                np.issubdtype(dtype, np.floating):
                col_summary = df[header].sum()
            elif dtype == np.object:
                col_summary = df[header].nunique()
            else:  #possibly empty dataframe
                col_summary = 0

            totals[header] = col_summary

            # Summarize number of transactions in the table
            if header in (self.db_key, self.db_key.lower()):
                output = (_('Number of transactions processed'), col_summary)
                outputs.append(output)

        # Calculate totals defined by summary rules
        for rule_name in summ_rules:
            rule = summ_rules[rule_name]
            rule_values = []
            for component in dm.parse_operation_string(rule):
                if component in operators:
                    rule_values.append(component)
                    continue

                component_col = self.get_column_name(component)
                if component_col:  #component is header column
                    try:
                        rule_values.append(totals[component_col])
                    except KeyError:  #try lower-case
                        print('Warning: tab {NAME}, rule {RULE}: "{ITEM}" '\
                              'from summary rule "{SUMM}" not in display '\
                              'columns'.format(NAME=self.name, \
                              RULE=self.rule_name, ITEM=component, \
                              SUMM=rule_name))
                        rule_values = [0]
                        break
                elif component.isnumeric():  #component is integer
                    rule_values.append(component)
                else:  #component is unsupported character
                    print('Warning: tab {NAME}, rule {RULE}: unsupported '\
                          'character "{ITEM}" provided to summary rule "{SUMM}"'\
                          .format(NAME=self.name, RULE=self.rule_name, \
                          ITEM=component, SUMM=rule_name))
                    rule_values = [0]
                    break

            summary_total = eval(' '.join([str(i) for i in rule_values]))

            outputs.append((rule_name, summary_total))

        summary_key = self.key_lookup('Summary')
        window[summary_key].update(value='\n'.join(['{}: {}'.format(*i) for \
            i in outputs]))

    def toggle_actions(self, window, value='enable'):
        """
        Enable / Disable schema action buttons.
        """
        status = False if value == 'enable' else True

        for element in self.action_elements:
            element_tup = [(element, 'disabled={}'.format(status))]
            self.update(window, element_tup)

    def key_lookup(self, element):
        """
        Lookup key for element in schema.
        """
        elements = self.data_elements + self.action_elements
        if element in elements:
            key = as_key('{} {}'.format(self.element_name, element))
        else:
            print('Warning: tab {TAB}, rule {RULE}: element {ELEM} not found '\
                  'in list of sub-elements'\
                .format(TAB=self.name, RULE=self.rule_name, ELEM=element))
            key = None

        return(key)

    def layout(self):
        """
        Tab schema for layout type 'reviewable'.
        """
        # Window and element size parameters
        bg_col = const.ACTION_COL

        pad_frame = const.FRAME_PAD
        pad_el = const.ELEM_PAD
        pad_h = const.HORZ_PAD
        font_l = const.LARGE_FONT
        font_m = const.MID_FONT

        header = self.df.columns.values.tolist()
        data = self.df.values.tolist()

        summary_key = self.key_lookup('Summary')
        audit_key = self.key_lookup('Audit')
        table_key = self.key_lookup('Table')
        add_key = self.key_lookup('Add')
        input_key = self.key_lookup('Input')
        layout = [[create_table(data, header, table_key, bind=True)],
                  [sg.Frame(_('Summary'), [[sg.Multiline('', border_width=0, size=(52, 6), font=font_m, key=summary_key,
                                                         disabled=True, background_color=bg_col)]], font=font_l,
                            pad=((pad_frame, 0), (0, pad_frame)), background_color=bg_col, element_justification='l'),
                   sg.Text(' ' * 60, background_color=bg_col),
                   sg.Col([[
                       sg.Input('', key=input_key, font=font_l, size=(20, 1), pad=(pad_el, 0), do_not_clear=False,
                         tooltip=_('Input document number to add a transaction to the table'), disabled=True),
                       B2(_('Add'), key=add_key, pad=((0, pad_h), 0), tooltip=_('Add order to the table'), disabled=True),
                       B2(_('Audit'), key=audit_key, disabled=True, pad=((0, pad_frame), 0), tooltip=_('Run Audit methods'))
                   ]], background_color=bg_col)
                 ]]

        return(layout)

    def row_ids(self):
        """
        Return a list of all row IDs in the dataframe.
        """
        try:
            row_ids = list(self.df[self.db_key])
        except KeyError:  #database probably PostGreSQL
            try:
                row_ids = list(self.df[self.db_key.lower()])
            except KeyError:
                print('Warning: tab {TAB}, rule {RULE}: missing database key '\
                      '{KEY} in column headers'\
                      .format(TAB=self.name, RULE=self.rule_name, KEY=self.db_key))
                row_ids = []

        return(row_ids)

    def sort_table(self, df, ascending:bool=True):
        """
        Sort dataframe on primary key defined in configuration.
        """
        pkey = self.get_column_name(self.db_key)

        if not df.empty:
            df.sort_values(by=[pkey], inplace=True, ascending=ascending)
            df.reset_index(drop=True, inplace=True)

        return(df)

    def search_for_errors(self):
        """
        Use error rules specified in configuration file to annotate rows.
        """
        df = self.df
        if df.empty:
            return(set())

        headers = df.columns.values.tolist()
        pkey = self.db_key if self.db_key in headers else self.db_key.lower()

        # Search for errors in the data based on the defined error rules
        error_rules = self.error_rules
        errors = dm.evaluate_rule_set(df, error_rules)

        # Search for errors in the transaction ID using ID format
        try:
            date_cnfg = config.format_date_str(self.get_component('date')[1])
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

        return(set(errors))

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
                print('Warning: tab {NAME}, rule {RULE}: method {METHOD} failed due to {E}'\
                    .format(NAME=self.name, RULE=self.rule_name, METHOD=action, E=e))
                raise Exception
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
        user = kwargs['account']
        audit_params = kwargs['parameters']
        window = args[0]

        # Class attribites
        pkey = self.get_column_name(self.db_key)
        df = self.sort_table(self.df)
        id_list = df[pkey].tolist()
        main_table = [i for i in self.db_tables][0]

        # Format audit parameters
        for audit_param in audit_params:
            if audit_param.type.lower() == 'date':
                date_col = audit_param.name
                date_col_full = self.get_query_column(date_col)
                date_fmt = audit_param.format
                try:
                    audit_date = strptime(audit_param.value, date_fmt)
                except dateutil.parser._parser.ParserError:
                    print('Warning: no date provided ... skipping checks for most recent ID')
                    audit_date = None
                else:
                    audit_date_iso = audit_date.strftime("%Y-%m-%d")
        
        # Search for missing data
        missing_transactions = []

        try:
            first_id = id_list[0]
        except IndexError:  #no data in dataframe
            print('Warning: {NAME} Audit: no transactions for audit date {DATE}'
                  .format(NAME=self.name, DATE=audit_date_iso))
            return(df)

        first_number_comp = int(self.get_id_component(first_id, 'variable'))
        first_date_comp = self.get_id_component(first_id, 'date')
        print('Info: {} Audit: first transaction ID {} has number {} and date {}'\
              .format(self.name, first_id, first_number_comp, first_date_comp))

        ## Find date of last transaction
        query_str = 'SELECT DISTINCT {DATE} FROM {TBL}'.format(DATE=date_col_full, TBL=main_table)
        dates_df = user.thread_transaction(query_str, (), operation='read')

        unq_dates = dates_df[date_col].tolist()
        try:
            unq_dates_iso = [i.strftime("%Y-%m-%d") for i in unq_dates]
        except TypeError:
            print('Warning: {NAME} Audit: date {DATE} is not formatted correctly as a datetime object'
                  .format(NAME=self.name, DATE=audit_date_iso))
            return(False)

        unq_dates_iso.sort()

        try:
            current_date_index = unq_dates_iso.index(audit_date_iso)
        except ValueError:
            print('Warning: {NAME} Audit: no transactions for audit date {DATE} found in list {DATES}'
                  .format(NAME=self.name, DATE=audit_date_iso, DATES=unq_dates_iso))
            return(False)

        try:
            prev_date = dparse(unq_dates_iso[current_date_index - 1], yearfirst=True)
        except IndexError:
            print('Warning: {NAME} Audit: no date found prior to current audit date {DATE}'
                  .format(NAME=self.name, DATE=audit_date_iso))
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
                print('Info: {NAME} Audit: last transaction ID is {ID} from {DATE}'\
                    .format(NAME=self.name, ID=last_id, DATE=prev_date.strftime('%Y-%m-%d')))

                if first_date_comp != prev_date_comp:  #start of new month
                    if first_number_comp != 1:
                        missing_range = list(range(1, first_number_comp))
                    else:
                        missing_range = []

                else:  #still in same month
                    if (prev_number_comp + 1) != first_number_comp:  #first not increment of last
                        missing_range = list(range(prev_number_comp + 1, first_number_comp))
                    else:
                        missing_range = []

                for missing_number in missing_range:
                    missing_id = self.format_id(missing_number, date=first_date_comp)
                    missing_transactions.append(missing_id)

        ## Search for skipped transaction numbers
        prev_number = first_number_comp
        for transaction_id in id_list[1:]:
            trans_number = int(self.get_id_component(transaction_id, 'variable'))
            if (prev_number + 1) != trans_number:
                missing_range = list(range(prev_number + 1, trans_number))
                for missing_number in missing_range:
                    missing_id = self.format_id(missing_number, date=first_date_comp)
                    missing_transactions.append(missing_id)

            prev_number = trans_number

        print('Info: {NAME} Audit: potentially missing transactions: {MISS}'
              .format(NAME=self.name, MISS=missing_transactions))

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

        # Query database for the potentially missing transactions
        if missing_transactions:
            pkey_fmt = self.get_query_column(pkey)

            filter_values = ['?' for i in missing_transactions]
            filter_str = '{PKEY} IN ({VALUES})'.format(PKEY=pkey_fmt, VALUES=', '.join(filter_values))

            filters = [(filter_str, tuple(missing_transactions))]

            # Drop missing transactions if they don't meet tab parameter requirements
            tab_params = self.tab_parameters
            for tab_param in tab_params:
                tab_param_value = tab_params[tab_param]
                tab_param_col = self.get_query_column(tab_param)
                if not tab_param_col:
                    continue

                filters.append(('{} = ?'.format(tab_param_col), (tab_param_value,)))

            missing_df = user.query(self.db_tables, columns=self.db_columns, filter_rules=filters, order=pkey_fmt)
        else:
            missing_df = pd.DataFrame(columns=df.columns)

        # Display import window with potentially missing data
        missing_df_fmt = self.format_display_table(self.sort_table(missing_df))
        import_rows = win2.import_window(missing_df_fmt)
        import_df = missing_df.iloc[import_rows]

        # Updata dataframe with imported data
        df = self.append_to_table(import_df)

        print('Info: new size of {0} dataframe is {1} rows and {2} columns'.format(self.name, *df.shape))

        # Inform main thread that sub-thread has completed its operations
        return(df)

    def filter_transactions(self, *args, **kwargs):
        """
        Filter pandas dataframe using the filter rules specified in the configuration.
        """
        # Method arguments
        window = args[0]

        # Tab attributes
        df = self.df
        filter_rules = self.filter_rules

        if not filter_rules:
            return(df)

        print('Info: tab {NAME}, rule {RULE}: running filter method with filter rules {RULES}'
              .format(NAME=self.name, RULE=self.rule_name, RULES=list(filter_rules.values())))

        failed = dm.evaluate_rule_set(df, filter_rules)

        df.drop(failed, axis=0, inplace=True)
        df.reset_index(drop=True, inplace=True)

        return(df)


def as_key(key):
    """
    Format string as element key.
    """
    return('-{}-'.format(key).replace(' ', ':').upper())

# GUI Element Functions
def B1(*args, **kwargs):
    """
    Action button element defaults.
    """
    size = const.B1_SIZE
    return(sg.Button(*args, **kwargs, size=(size, 1)))

def B2(*args, **kwargs):
    """
    Panel button element defaults.
    """
    size = const.B2_SIZE
    return(sg.Button(*args, **kwargs, size=(size, 1)))

# Element Creation
def empty_data_table(nrow:int=20, ncol:int=10):
    """
    """
    return([['' for col in range(ncol)] for row in range(nrow)])

def create_table(data, header, keyname, events:bool=False, bind:bool=False, \
        tooltip:str=None, nrows:int=const.TBL_NROW, \
        height:int=const.TBL_HEIGHT, width:int=const.TBL_WIDTH):
    """
    Create table elements that have consistency in layout.
    """
    # Element settings
    text_col=const.TEXT_COL
    alt_col = const.TBL_ALT_COL
    bg_col = const.TBL_BG_COL
    select_col = const.TBL_SELECT_COL
    pad_frame = const.FRAME_PAD
    pad_el = const.ELEM_PAD

    # Parameters
    if events and bind:
        bind = False  #only one can be selected at a time
        print('Warning: both bind_return_key and enable_events have been '\
              'selected during table creation. These parameters are mutually '\
              'exclusive.')

    lengths = calc_column_widths(header)
    layout = sg.Table(data, headings=header, pad=(pad_frame, pad_frame),
               key=keyname, row_height=height, alternating_row_color=alt_col,
               text_color=text_col, selected_row_colors=(text_col, select_col), 
               background_color=bg_col, num_rows=nrows, font=('Sans Serif', 10),
               display_row_numbers=False, auto_size_columns=False,
               col_widths=lengths, enable_events=events, tooltip=tooltip,
               vertical_scroll_only=False, bind_return_key=bind)

    return(layout)

def calc_column_widths(header, width=None, pixels=False):
    """
    Calculate width of table columns based on the number of columns displayed.
    """
    # Size of data
    ncol = len(header)

    # When table columns not long enough, need to adjust so that the
    # table fills the empty space.
    if pixels and not width:
        width = const.TBL_WIDTH_PX
    elif not width and not pixels:
        width = const.TBL_WIDTH
    else:
        width = width

    max_size_per_col = int(width / ncol)

    # Each column has size == max characters per column
    lengths = [max_size_per_col for i in header]

    # Add any remainder evenly between columns
    remainder = width - (ncol  * max_size_per_col)
    index = 0
    for one in [1 for i in range(remainder)]:
        if index > ncol - 1:
            index = 0
        lengths[index] += one
        index += one

    return(lengths)

# Panel layouts
def action_layout(audit_rules):
    """
    """
    # Layout settings
    bg_col = const.ACTION_COL
    pad_frame = const.FRAME_PAD
    pad_el = const.ELEM_PAD
    pad_v = const.VERT_PAD
    button_size = const.B3_SIZE

    rule_names = audit_rules.print_rules()
    nrule = len(rule_names)
    pad_screen = (266 - (nrule * button_size)) / 2

    # Button layout
    buttons = [[sg.Text('', pad=(pad_frame, 0), size=(0, 0),
                  background_color=bg_col)]]

    for rule_name in rule_names:
        rule_el = [B1(rule_name, pad=(pad_frame, pad_el), disabled=True)]
        buttons.append(rule_el)

    other_bttns = [[sg.HorizontalSeparator(pad=(pad_frame, pad_v))],
                   [B1(_('Update Database'), pad=(pad_frame, pad_el), 
                      key='-DB-', disabled=True)],
                   [sg.HorizontalSeparator(pad=(pad_frame, pad_v))],
                   [B1(_('Summary Statistics'), pad=(pad_frame, pad_el), 
                      key='-STATS-', disabled=True)],
                   [B1(_('Summary Reports'), pad=(pad_frame, pad_el), 
                      key='-REPORTS-', disabled=True)],
                   [sg.Text('', pad=(pad_frame, 0), size=(0, 0),
                      background_color=bg_col)]]

    buttons += other_bttns

    layout = sg.Col([[sg.Text('', pad=(0, pad_screen))],
                     [sg.Frame('', buttons, element_justification='center', 
                        relief='raised', background_color=bg_col)],
                     [sg.Text('', pad=(0, pad_screen))]], key='-ACTIONS-')

    return(layout)

def tab_layout(tabs):
    """
    Layout of the audit panel tab groups.
    """
    # Element parameters
    bg_col = const.ACTION_COL

    # Populate tab layouts with elements
    layout = []
    for i, tab in enumerate(tabs):  #iterate over audit rule tabs / items
        tab_name = tab.name
        tab_key = tab.element_key

        # Enable only the first tab to start
        visible = True if i == 0 else False

        # Generate the layout
        tab_layout = tab.layout()

        layout.append(sg.Tab(tab_name, tab_layout, visible=visible, 
            background_color=bg_col, key=tab_key))

    return(layout)
