"""
REM function for manipulating data.
"""

import numpy as np
import pandas as pd
import re


def create_empty_table(nrow: int = 20, ncol: int = 10):
    """
    Generate an empty table as a list of lists where each list is a row and number of columns is the length.
    """
    return [['' for col in range(ncol)] for row in range(nrow)]


def calc_column_widths(header, width: int = 1200, font_size: int = 13, pixels=False):
    """
    Calculate width of table columns based on the number of columns displayed.
    """
    # Size of data
    ncol = len(header)

    # When table columns not long enough, need to adjust so that the
    # table fills the empty space.
    width = width

    max_size_per_col = width / ncol
    if pixels:
        max_size_per_col = int(max_size_per_col)
    else:
        width = int(width / font_size)
        max_size_per_col = int(max_size_per_col / font_size)

    # Each column has size == max characters per column
    lengths = [max_size_per_col for i in header]

    # Add any remainder evenly between columns
    remainder = width - (ncol * max_size_per_col)
    index = 0
    for one in [1 for i in range(int(remainder))]:
        if index > ncol - 1:
            index = 0
        lengths[index] += one
        index += one

    return lengths


def get_query_from_header(colname, header):
    """
    Find full query column (Table + Column) from the column name.
    """
    query_name = None
    for table_column in header:
        try:
            table_comp, col_comp = table_column.split('.')
        except IndexError:  # use main table as table portion of full name
            col_comp = table_column
            table_comp = None

        col_comp_alias = col_comp.rsplit('AS', 1)[-1]
        col_comp_alias = col_comp_alias.strip()
        if colname in (col_comp_alias, col_comp_alias.lower()):
            if table_comp:
                query_name = '{}.{}'.format(table_comp, col_comp)
            else:
                query_name = col_comp
            break

    if not query_name:
        print('Warning: unable to find column {COL} in list of table columns {COLS}'
              .format(COL=colname, COLS=header))
        query_name = colname

    return query_name


def get_column_from_header(column, header):
    """
    Extract the column name or alias component from a list of query columns.
    """
    alias = None
    for query_column in header:
        try:
            table_comp, col_comp = query_column.split('.')
        except ValueError:  # use main table as table portion of full name
            col_comp = query_column

        try:
            col_name, col_alias = col_comp.rsplit('AS', 1)  # use alias name if exists
        except ValueError:
            col_name = col_comp.strip()
            col_alias = col_comp.strip()
        else:
            col_name = col_name.strip()
            col_alias = col_alias.strip()

        if col_name == column:
            alias = col_alias
            break

    if not alias:
        print('Warning: unable to find column {COL} in list of table columns {COLS}'
              .format(COL=column, COLS=header))
        alias = column

    return alias


def get_column_from_oper(df, condition):
    """
    Extract the column name from a condition rule
    """
    headers = df.columns.values.tolist()

    if isinstance(condition, str):
        conditional = parse_operation_string(condition)
    elif isinstance(condition, list):
        conditional = condition
    else:
        raise ValueError('condition argument must be either a string or list')

    colnames = []
    for component in conditional:
        if component in headers:
            colnames.append(component)
        elif component.lower() in headers:
            colnames.append(component.lower())
        else:  # component is a string or integer
            continue

    return colnames


def fill_na(df, colname=None):
    """
    Fill fields NaNs with default values that depend on data type.
    """
    is_float_dtype = pd.api.types.is_float_dtype
    is_string_dtype = pd.api.types.is_string_dtype
    is_datetime_dtype = pd.api.types.is_datetime64_any_dtype
    is_bool_dtype = pd.api.types.is_bool_dtype

    columns = [colname] if colname else df.columns.values.tolist()
    for column in columns:
        dtype = df.dtypes[column]

        if is_float_dtype(dtype):
            df[column].fillna(0.0, inplace=True)
        elif is_string_dtype(dtype):
            df[column].fillna('', inplace=True)
        elif is_datetime_dtype(dtype):
            df[column].fillna(inplace=True, method='ffill')
        elif is_bool_dtype(dtype):
            df[column].fillna(False, inplace=True)
        else:  # empty df?
            print('Warning: unable to fill missing values from column {COL} with unsupported data type {DTYPE}.'
                  .format(COL=column, DTYPE=dtype))

    return df


def subset_dataframe(df, subset_rule):
    """
    Subset a dataframe based on a set of rules.
    """
    operators = {'>', '>=', '<', '<=', '==', '!=', 'IN', 'In', 'in'}
    chain_map = {'or': '|', 'OR': '|', 'Or': '|', 'and': '&', 'AND': '&', 'And': '&'}

    header = df.columns.values.tolist()

    rule_list = [i.strip() for i in
                 re.split('({})'.format('|'.join([' {} '.format(i) for i in chain_map])), subset_rule)]

    conditionals = []
    for component in rule_list:
        if component in chain_map:
            conditionals.append(chain_map[component])
        else:
            conditional = parse_operation_string(component)
            cond_items = []
            for item in conditional:
                if item in operators:  # item is operator
                    cond_items.append(item)
                elif item in header:  # item is in header
                    cond_items.append('df["{}"]'.format(item))
                elif item.lower() in header:  # item is header converted by ODBC implementation
                    cond_items.append('df["{}"]'.format(item.lower()))
                else:  # item is string or int
                    cond_items.append(item)

            conditionals.append('({})'.format(' '.join(cond_items)))

    cond_str = ' '.join(conditionals)

    try:
        print('Info: subsetting evaluation string is {}'.format(cond_str))
        subset_df = eval('df[{}]'.format(cond_str))
    except SyntaxError:
        raise SyntaxError('invalid syntax for subset rule {NAME}'.format(NAME=subset_rule))
    except NameError:
        raise NameError('unknown column specified in subset rule {NAME}'.format(NAME=subset_rule))

    return subset_df


def generate_column_from_rule(dataframe, rule):
    """
    Generate dataframe column using a rule set
    """
    chain_operators = ('or', 'and', 'OR', 'AND', 'Or', 'And')

    # Split string by any chain operator
    col_list = [i.strip() for i in re.split('{}'.format('|'.join([' {} '.format(i) for i in chain_operators])), rule)]

    col_to_add = pd.Series(np.full([dataframe.shape[0]], np.nan))

    merge_cols = []
    dtype = None
    for i, sub_rule in enumerate(col_list):
        col_oper_list = parse_operation_string(sub_rule)

        sub_colnames = get_column_from_oper(dataframe, col_oper_list)
        for sub_colname in sub_colnames:
            merge_cols.append(sub_colname)

            column_dtype = dataframe.dtypes[sub_colname]
            if i == 0:
                dtype = column_dtype
            elif i > 0:
                if dtype != column_dtype:
                    print('Warning: attempting to combine column {COL} with dtype {COL_DTYPE} different from the '
                          'original dtype {DTYPE}'.format(COL=sub_colname, COL_DTYPE=column_dtype, DTYPE=dtype))
        try:
            sub_values = evaluate_rule(dataframe, col_oper_list)
        except Exception as e:
            print('Warning: merging of columns {COLS} failed due to {ERR}'.format(COLS=merge_cols, ERR=e))
            continue
        else:
            try:
                col_to_add.fillna(pd.Series(sub_values), inplace=True)
            except Exception as e:
                print('Warning: filling new column with values from rule {COND} failed due to {ERR}'
                      .format(COND=sub_rule, ERR=e))

    # Attempt to set column dtype
    return col_to_add.astype(dtype, errors='raise')


def append_to_table(df, add_df, ignore_dtypes=False):
    """
    Append new data to dataframe.
    """
    if add_df.empty:
        return df
    elif df.empty:
        return add_df

    # Add row information to the table
    if not add_df.dtypes.equals(df.dtypes) and not ignore_dtypes:
        print('Warning: data to be appended has some dtypes that are different from the dataframe dtypes')
        wrong_types = []
        for header in add_df.columns.tolist():
            new_dtype = add_df[header].dtypes
            tab_dtype = df[header].dtypes

            print('Info: comparing data type of {COL} with dtype {TYPEN} to dtype {TYPEO}'
                  .format(COL=header, TYPEN=new_dtype, TYPEO=tab_dtype))
            if new_dtype != tab_dtype:
                print(
                    'Warning: trying to append new data with column {COL} having a non-matching data type. '
                    'Coercing datatype to {TYPE}'.format(COL=header, TYPE=tab_dtype))
                wrong_types.append(header)

        # Set data type to df column data type
        try:
            add_df = add_df.astype(df[wrong_types].dtypes.to_dict(), errors='raise')
        except Exception as e:
            print('Error: unable to add new data due to: {}'.format(e))
            add_df = None

    return df.append(add_df, ignore_index=True, sort=False)


def sort_table(df, sort_key, ascending: bool = True):
    """
    Sort dataframe on provided column.
    """
    if not df.empty:
        try:
            df.sort_values(by=[sort_key], inplace=True, ascending=ascending)
        except KeyError:
            print('Warning: sort key column {} not find in dataframe. Values will not be sorted.'.format(sort_key))
            return df
        else:
            df.reset_index(drop=True, inplace=True)

    return df


def evaluate_rule_set(df, conditions, rule_key=None, as_list: bool = True):
    """
    Check whether rows in a dataframe pass a set of conditions.
    """
    if not as_list:
        chain_map = {'or': '|', 'OR': '|', 'Or': '|', 'and': '&', 'AND': '&', 'And': '&'}
    else:
        chain_map = {'or': 'or', 'OR': 'or', 'Or': 'or', 'and': 'and', 'AND': 'and', 'And': 'and'}

    eval_values = []  # stores list of lists or pandas Series of bools to pass into formatter
    rule_eval_list = []
    for i, rule_name in enumerate(conditions):
        if i != 0:
            rule_eval_list.append(chain_map['and'])

        if rule_key:
            rule_str = conditions[rule_name][rule_key]
        else:
            rule_str = conditions[rule_name]  # db column name is dictionary key

        rule_list = [i.strip() for i in
                     re.split('({})'.format('|'.join([' {} '.format(i) for i in chain_map])), rule_str)]

        for component in rule_list:
            if component not in chain_map:
                rule_eval_list.append('{}')

                try:
                    failed_condition = evaluate_rule(df, component, as_list=as_list)
                except Exception as e:
                    print('Warning: evaluation failed due to {}. Setting values to default "True"'.format(e))
                    nrow = df.shape[0]
                    eval_values.append([True for i in range(nrow)])
                else:
                    eval_values.append(failed_condition)
            else:  # item is chain operators and / or
                rule_eval_list.append(chain_map[component])

    rule_eval_str = ' '.join(rule_eval_list)
    if as_list:
        failed_set = []
        for row, results_tup in enumerate(zip(*eval_values)):
            results = eval(rule_eval_str.format(*results_tup))
            if not results:
                print('Info: table row {ROW} failed one or more condition rule'.format(ROW=row))
                failed_set.append(row)
    else:
        failed_set = eval(rule_eval_str.format(*eval_values))

    return failed_set


def evaluate_rule(df, condition, as_list: bool = True):
    """
    Check whether rows in dataframe pass a given condition rule.
    """
    operators = {'+', '-', '*', '/', '>', '>=', '<', '<=', '==', '!=', 'in'}

    header = df.columns.values.tolist()

    if isinstance(condition, str):
        conditional = parse_operation_string(condition)
    elif isinstance(condition, list):
        conditional = condition
    else:
        raise ValueError('condition argument must be either a string or list')

    rule_value = []
    for i, component in enumerate(conditional):
        if component in operators:  # component is an operator
            rule_value.append(component)
        elif component in header:
            rule_value.append('df["{}"]'.format(component))
        elif component.lower() in header:
            rule_value.append('df["{}"]'.format(component.lower()))
        else:  # component is a string or integer
            rule_value.append(component)

    eval_str = ' '.join(rule_value)
    try:
#        print('Info: evaluating rule string {}'.format(eval_str))
        row_status = eval(eval_str)
    except SyntaxError:
        raise SyntaxError('invalid syntax for condition rule {NAME}'.format(NAME=condition))
    except NameError:
        raise NameError('unknown column found in condition rule {NAME}'.format(NAME=condition))

    if as_list:
        row_status = list(row_status)
    else:
        if not isinstance(row_status, pd.Series):
            raise SyntaxError('invalid syntax for condition rule {NAME}'.format(NAME=condition))

    return row_status


def parse_operation_string(condition, equivalent: bool = True):
    """
    Split operation string into a list.
    """
    operators = set('+-*/><=!')

    # Find the column names and operators defined in the condition rule
    parsed_condition = []
    buff = []
    prev_char = None
    for char in condition:
        if char.isspace():  # skip whitespace
            continue
        elif char in operators:  # character is an operator
            if prev_char not in operators:  # flush buffer for non-operator
                parsed_condition.append(''.join(buff))

                buff = [char]
            else:  # previous character was also an operator
                buff.append(char)
                parsed_condition.append(''.join(buff))

                buff = []
        else:  # character is not operator or whitespace, append to buffer
            if prev_char in operators:  # flush buffer for single char operator
                parsed_condition.append(''.join(buff))

                buff = [char]
            else:
                buff.append(char)

        prev_char = char

    parsed_condition.append(''.join(buff))

    if equivalent:
        parsed_condition_fmt = [i.replace('=', '==') if len(i) == 1 else i for i in parsed_condition if i]
    else:
        parsed_condition_fmt = [i for i in parsed_condition if i]

    return parsed_condition_fmt
