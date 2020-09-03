"""
REM function for manipulating data.
"""
import numpy as np
import pandas as pd

def fill_na(df, colname):
    """
    Fill fields Nas with default values that depend on data type.
    """
    dtype = df.dtypes[colname]

    if dtype in (np.int64, np.float64):
        mod_col = df[colname].fillna(0)
    elif dtype == np.object:
        mod_col = df[colname].fillna('')
    else:  #empty df?
        print('Warning: unsupported data type.')
        mod_col = None

    return(mod_col)

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
        if component in operators:  #component is an operator
            rule_value.append(component)
        elif component in headers:
            header_value = component
            rule_value.append('df["{}"]'.format(component))
            print('Info: data type of header {} is {}'\
                .format(header_value, df.dtypes[header_value]))
        elif component.lower() in headers:
            header_value = component.lower()
            rule_value.append('df["{}"]'.format(component.lower()))
            print('Info: data type of header {} is {}'\
                .format(header_value, df.dtypes[header_value]))
        else:  #component is a string or integer
            value_index = i
            rule_value.append(component)

    if header_value != None and value_index != None:
        # Get data type of header column
        dtype = df.dtypes[header_value]
        if dtype == np.object:
            rule_value[value_index] = '"{}"'.format(rule_value[value_index])

    if len(rule_value) == 1:  #handle case where checking for existence
        eval_str = '{VAL} not in {NONE}'\
            .format(VAL=rule_value[0], NONE=nonetypes)
    else:
        eval_str = ' '.join(rule_value)

    try:
        row_status = list(eval(eval_str))
    except SyntaxError:
        nrow = df.shape[0]
        print('Warning: invalid syntax for condition rule {NAME}'\
            .format(NAME=condition_str))
        row_status = [True for i in range(nrow)]

    return(row_status)

def parse_operation_string(condition, equivalent:bool=True):
    """
    Split operation string into a list.
    """
    operators = set('+-*/><=')

    # Find the column names and operators defined in the condition rule
    parsed_condition = []
    buff = []
    prev_char = None
    for char in condition:
        if char.isspace():  #skip whitespace
            continue
        elif char in operators:  #character is an operator
            if prev_char not in operators:  #flush buffer for non-operator
                parsed_condition.append(''.join(buff))

                buff = [char]
            else:  #previous character was also an operator
                buff.append(char)
                parsed_condition.append(''.join(buff))

                buff = []
        else: #character is not operator or whitespace, append to buffer
            if prev_char in operators:  #flush buffer for single char operator
                parsed_condition.append(''.join(buff))

                buff = [char]
            else:
                buff.append(char)

        prev_char = char

    parsed_condition.append(''.join(buff))

    if equivalent:
        parsed_condition_fmt = [i.replace('=', '==') if len(i) == 1 else i for \
                                i in parsed_condition if i]
    else:
        parsed_condition_fmt = [i for i in parsed_condition if i]

    return(parsed_condition_fmt)
