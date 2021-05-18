"""
REM function for manipulating data.
"""

import re

import numpy as np
import pandas as pd

from REM.client import logger


def calc_column_widths(header, width: int = 1200, font_size: int = 13, pixels=False):
    """
    Calculate width of table columns based on the number of columns displayed.
    """
    # Size of data
    ncol = len(header)

    # When table columns not long enough, need to adjust so that the
    # table fills the empty space.
    width = width

    try:
        col_fraction = width / ncol
    except ZeroDivisionError:
        logger.warning('division by zero error encountered while attempting to calculate column widths')
        col_fraction = width / 10

    if pixels:
        max_size_per_col = int(col_fraction)
    else:
        width = int(width / font_size)
        max_size_per_col = int(col_fraction / font_size)

    # Each column has size == max characters per column
    lengths = [max_size_per_col for _ in header]

    # Add any remainder evenly between columns
    if len(lengths) < 1:
        remainder = 0
    else:
        remainder = width - (ncol * max_size_per_col)
    index = 0
    for one in [1 for _ in range(int(remainder))]:
        if index > ncol - 1:
            index = 0
        lengths[index] += one
        index += one

    return lengths


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


def generate_column_from_rule(dataframe, rule):
    """
    Generate the values of a dataframe column using the defined rule set.
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
                    logger.warning('attempting to combine column {COL} with dtype {COL_DTYPE} different from the '
                                   'original dtype {DTYPE}'
                                   .format(COL=sub_colname, COL_DTYPE=column_dtype, DTYPE=dtype))
        try:
            sub_values = evaluate_rule(dataframe, col_oper_list)
        except Exception as e:
            logger.warning('merging of columns {COLS} failed - {ERR}'.format(COLS=merge_cols, ERR=e))
            continue
        else:
            try:
                col_to_add.fillna(pd.Series(sub_values), inplace=True)
            except Exception as e:
                logger.error('filling new column with values from rule {COND} failed - {ERR}'
                             .format(COND=sub_rule, ERR=e))

    # Attempt to set the column data type
    return col_to_add.astype(dtype, errors='raise')


def evaluate_rule_set(df, conditions, rule_key=None, as_list: bool = True):
    """
    Check whether rows in a dataframe pass a set of conditions. Returns a list or pandas Series of failed indexes.
    """
    chain_operators = ['and', 'or', 'OR', 'AND', 'And', 'Or']

    eval_results = []  # stores list of lists or pandas Series of bools to pass into formatter
    operators = []
    for i, rule_name in enumerate(conditions):
        if i != 0:
            operators.append('and')

        if rule_key:
            rule_str = conditions[rule_name][rule_key]
        else:
            rule_str = conditions[rule_name]  # db column name is dictionary key

        rule_list = [i.strip() for i in
                     re.split('({})'.format('|'.join([' {} '.format(i) for i in chain_operators])), rule_str)]

        for component in rule_list:
            if component.lower() in chain_operators:  # item is chain operators and / or
                operators.append(component.lower())
            else:
                try:
                    cond_results = evaluate_condition(df, component, as_list=False).fillna(False).astype(np.bool,
                                                                                                        errors='raise')
                except Exception as e:
                    logger.warning('evaluation failed - {}. Setting values to default "False"'.format(e))
                    if isinstance(df, pd.DataFrame):
                        nrow = df.shape[0]
                    elif isinstance(df, pd.Series):
                        nrow = 1

                    cond_results = pd.Series([False for _ in range(nrow)])

                eval_results.append(cond_results)

    results = eval_results[0]
    for index, cond_results in enumerate(eval_results[1:]):
        try:
            operator = operators[index]
        except IndexError:
            logger.warning('evaluation failed - not enough operators provided for the number of conditions set')
            break

        if operator == 'and':
            results = results & cond_results
        else:
            results = results | cond_results

    if as_list is True:
        return list(results)
    else:
        return results


def evaluate_condition(data, condition, as_list: bool = True):
    """
    Check whether rows in dataframe pass a given condition rule.
    """
    is_bool_dtype = pd.api.types.is_bool_dtype
    operators = {'>', '>=', '<', '<=', '==', '!=', '=', 'in', 'not in'}

    if isinstance(data, pd.Series):
        header = data.index.tolist()
        nrow = data.size
    elif isinstance(data, pd.DataFrame):
        header = data.columns.values.tolist()
        nrow = 1
    else:
        raise ValueError('data must be either a pandas DataFrame or Series')

    rule = [i.strip() for i in re.split('({})'.format('|'.join([' {} '.format(i) for i in operators])), condition)]
    if len(rule) == 3:
        left, oper, right = rule
        if oper not in operators:
            raise SyntaxError('unable to parse rule condition {} - operator must separate the operands'
                              .format(condition))
        else:
            if oper == '=':
                oper = '=='

        if oper.lower() == 'in':
            for column in header:
                left = re.sub(r'\b{}\b'.format(column), 'data["{}"]'.format(column), left)
            eval_str = '{}.isin(right)'.format(left)
            right = right.replace(' ', '').split(',')
        elif oper.lower() == 'not in':
            for column in header:
                left = re.sub(r'\b{}\b'.format(column), 'data["{}"]'.format(column), left)
            eval_str = '~{}.isin(right)'.format(left)
            right = right.replace(' ', '').split(',')
        else:
            for column in header:
                left = re.sub(r'\b{}\b'.format(column), 'data["{}"]'.format(column), left)
                right = re.sub(r'\b{}\b'.format(column), 'data["{}"]'.format(column), right)
            eval_str = "{} {} {}".format(left, oper, right)

        try:
            results = eval(eval_str)
        except SyntaxError:
            raise SyntaxError('invalid syntax for condition rule {NAME}'.format(NAME=condition))
        except NameError:  # dataframe does not have column
            raise NameError('unknown column found in condition rule {NAME}'.format(NAME=condition))

    elif len(rule) == 1:
        eval_str = rule[0]
        if eval_str[0] == '!':
            colname = eval_str.replace(' ', '')[1:]
            if colname in header:
                if is_bool_dtype(data[colname].dtype) is True:
                    results = data[colname]
                else:
                    results = data[colname].isna()
            else:
                results = pd.Series([False for _ in range(nrow)])
        else:
            colname = eval_str
            if colname in header:
                if is_bool_dtype(data[colname].dtype) is True:
                    results = ~ data[colname]
                else:
                    results = ~ data[colname].isna()
            else:
                results = pd.Series([False for _ in range(nrow)])
    else:
        raise SyntaxError('unable to parse rule condition {} - unknown format of the condition rule'.format(condition))

    if as_list is True:
        results = list(results)

    return results


def evaluate_rule(data, condition, as_list: bool = True):
    """
    Check whether rows in dataframe pass a given condition rule.
    """
    operators = {'+', '-', '*', '/', '>', '>=', '<', '<=', '==', '!=', 'in', 'not in', '!', 'not'}

    if isinstance(data, pd.Series):
        header = data.index.tolist()
    elif isinstance(data, pd.DataFrame):
        header = data.columns.values.tolist()
    else:
        raise ValueError('data must be either a pandas DataFrame or Series')

    if isinstance(condition, str):
        conditional = parse_operation_string(condition)
    elif isinstance(condition, list):
        conditional = condition
    else:
        raise ValueError('condition argument {} must be either a string or list'.format(condition))

    rule_value = []
    for i, component in enumerate(conditional):
        if component.lower() in operators:  # component is an operator
            if component.lower() in ('!', 'not'):
                rule_value.append('~')
            else:
                rule_value.append(component)
        elif component in header:
            rule_value.append('data["{}"]'.format(component))
        elif component.lower() in header:
            rule_value.append('data["{}"]'.format(component.lower()))
        else:  # component is a string or integer
            if component.isalpha() and '"' not in component:
                rule_value.append('"{}"'.format(component))
            else:
                rule_value.append(component)

    eval_str = ' '.join(rule_value)
    try:
        row_status = eval(eval_str)
    except SyntaxError:
        raise SyntaxError('invalid syntax for condition rule {NAME}'.format(NAME=condition))
    except NameError:  # dataframe does not have column
        raise NameError('unknown column found in condition rule {NAME}'.format(NAME=condition))

    if as_list is True:
        if isinstance(row_status, pd.Series):
            row_status = row_status.tolist()
        else:
            row_status = [row_status]
    else:
        if not isinstance(row_status, pd.Series):
            row_status = pd.Series(row_status)

    return row_status


def evaluate_rule(data, condition, as_list: bool = True):
    """
    Check whether rows in dataframe pass a given condition rule.
    """
    operators = {'+', '-', '*', '/', '>', '>=', '<', '<=', '==', '!=', 'in', 'not in', '!', 'not'}

    if isinstance(data, pd.Series):
        header = data.index.tolist()
    elif isinstance(data, pd.DataFrame):
        header = data.columns.values.tolist()
    else:
        raise ValueError('data must be either a pandas DataFrame or Series')

    if isinstance(condition, str):
        conditional = parse_operation_string(condition)
    elif isinstance(condition, list):
        conditional = condition
    else:
        raise ValueError('condition argument {} must be either a string or list'.format(condition))

    rule_value = []
    for i, component in enumerate(conditional):
        if component.lower() in operators:  # component is an operator
            if component.lower() in ('!', 'not'):
                rule_value.append('~')
            else:
                rule_value.append(component)
        elif component in header:
            rule_value.append('data["{}"]'.format(component))
        elif component.lower() in header:
            rule_value.append('data["{}"]'.format(component.lower()))
        else:  # component is a string or integer
            if component.isalpha() and '"' not in component:
                rule_value.append('"{}"'.format(component))
            else:
                rule_value.append(component)

    eval_str = ' '.join(rule_value)
    try:
        row_status = eval(eval_str)
    except SyntaxError:
        raise SyntaxError('invalid syntax for condition rule {NAME}'.format(NAME=condition))
    except NameError:  # dataframe does not have column
        raise NameError('unknown column found in condition rule {NAME}'.format(NAME=condition))

    if as_list is True:
        if isinstance(row_status, pd.Series):
            row_status = row_status.tolist()
        else:
            row_status = [row_status]
    else:
        if not isinstance(row_status, pd.Series):
            row_status = pd.Series(row_status)

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
            parsed_condition.append(''.join(buff))
            buff = []
#            continue
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
