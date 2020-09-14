"""
REM function for manipulating data.
"""
import numpy as np
import pandas as pd
from pandas.api.types import is_datetime64_any_dtype as is_datetime
import re


def fill_na(df, colname):
    """
    Fill fields Nas with default values that depend on data type.
    """
    dtype = df.dtypes[colname]

    if dtype in (np.int64, np.float64):
        mod_col = df[colname].fillna(0)
    elif dtype == np.object:
        mod_col = df[colname].fillna('')
    elif is_datetime(dtype):
        mod_col = df[colname].apply(lambda x: x.strftime('%Y-%m-%d') if pd.notnull(x) else '')
    else:  # empty df?
        print('Warning: unsupported data type {}.'.format(dtype))
        mod_col = df[colname].fillna('')

    return (mod_col)


def evaluate_rule_set(df, conditions):
    """
    Check whether rows in a dataframe pass a set of conditions.
    """
    chain_operators = ('or', 'and', 'OR', 'AND', 'Or', 'And')

    eval_values = []  # stores list of lists of bools to pass into formatter
    rule_eval_list = []
    for i, rule_name in enumerate(conditions):
        if i != 0:
            rule_eval_list.append('and')

        rule_str = conditions[rule_name]  # dictionary key is a db column name
        rule_list = [i.strip() for i in
                     re.split('({})'.format('|'.join([' {} '.format(i) for i in chain_operators])), rule_str)]

        for component in rule_list:
            if component not in chain_operators:
                rule_eval_list.append('{}')

                failed_condition = evaluate_rule(df, component)
                eval_values.append(failed_condition)
            else:  # item is chain operators and / or
                rule_eval_list.append(component.lower())

    rule_eval_str = ' '.join(rule_eval_list)

    failed_set = []
    for row, results_tup in enumerate(zip(*eval_values)):
        results = eval(rule_eval_str.format(*results_tup))
        if not results:
            print('Info: table row {ROW} failed one or more condition rule'.format(ROW=row))
            failed_set.append(row)

    return(failed_set)


def evaluate_rule(df, condition_str):
    """
    Check whether rows in dataframe pass a given condition rule.
    """
    operators = {'+', '-', '*', '/', '>', '>=', '<', '<=', '=='}
    nonetypes = ('', None, 'nan')

    headers = df.columns.values.tolist()

    conditional = parse_operation_string(condition_str)
    rule_value = []
    header_value = None
    value_index = None
    for i, component in enumerate(conditional):
        if component in operators:  # component is an operator
            rule_value.append(component)
        elif component in headers:
            header_value = component
            rule_value.append('df["{}"]'.format(component))
            print('Info: data type of header {} is {}'
                  .format(header_value, df.dtypes[header_value]))
        elif component.lower() in headers:
            header_value = component.lower()
            rule_value.append('df["{}"]'.format(component.lower()))
            print('Info: data type of header {} is {}'
                  .format(header_value, df.dtypes[header_value]))
        else:  # component is a string or integer
            value_index = i
            rule_value.append(component)

    if header_value is not None and value_index is not None:
        # Get data type of header column
        dtype = df.dtypes[header_value]
        if dtype == np.object:
            rule_value[value_index] = '"{}"'.format(rule_value[value_index])

    if len(rule_value) == 1:  # handle case where checking for existence
        eval_str = '{VAL} not in {NONE}'.format(VAL=rule_value[0], NONE=nonetypes)
    else:
        eval_str = ' '.join(rule_value)

    try:
        row_status = list(eval(eval_str))
    except SyntaxError:
        nrow = df.shape[0]
        print('Warning: invalid syntax for condition rule {NAME}'.format(NAME=condition_str))
        row_status = [True for i in range(nrow)]
    except NameError:
        nrow = df.shape[0]
        print('Warning: unknown column found in condition rule {NAME}'.format(NAME=condition_str))
        row_status = [True for i in range(nrow)]

    return (row_status)


def parse_operation_string(condition, equivalent: bool = True):
    """
    Split operation string into a list.
    """
    operators = set('+-*/><=')

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

    return (parsed_condition_fmt)
