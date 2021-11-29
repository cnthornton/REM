"""
REM function for manipulating data.
"""

import re

import numpy as np
import pandas as pd

from REM.client import logger, settings


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

    if pixels:  # output widths are in pixels
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
        if index > ncol - 1:  # restart at first column
            index = 0
        lengths[index] += one
        index += one

    return lengths


def evaluate_condition_set(df, conditions, rule_key=None, as_list: bool = True):
    """
    Check whether rows in a dataframe pass a set of conditions. Returns a list or pandas Series of failed indexes.
    """
    #chain_operators = ['and', 'or', 'OR', 'AND', 'And', 'Or']
    chain_operators = ('and', 'or')

    eval_results = []  # stores list of lists or pandas Series of bools to pass into formatter
    operators = []
    for i, rule_name in enumerate(conditions):
        if i != 0:
            operators.append('and')

        if rule_key:
            rule_str = conditions[rule_name][rule_key]
        else:
            rule_str = conditions[rule_name]  # db column name is dictionary key

        split_pttrn = '({})'.format('|'.join([' {} '.format(i) for i in chain_operators]))
        rule_list = [i.strip() for i in re.split(split_pttrn, rule_str, flags=re.IGNORECASE)]

        for component in rule_list:  # evaluation rules should be considered separately at first
            if component.lower() in chain_operators:  # item is chain operators (and / or)
                operators.append(component.lower())
            else:  # item is a separate rule
                try:
                    logger.debug('dataframe will be evaluated on condition {}'.format(component))
                    cond_results = evaluate_condition(df, component)
                    cond_results = cond_results.fillna(False).astype(np.bool_, errors='raise')
                except Exception as e:
                    logger.warning('evaluation failed - {}. Setting values to default "False"'.format(e))
                    if isinstance(df, pd.DataFrame):
                        nrow = df.shape[0]
                    elif isinstance(df, pd.Series):
                        nrow = 1

                    cond_results = pd.Series([False for _ in range(nrow)])

                eval_results.append(cond_results)

    results = eval_results[0]  # results of first evaluation rule
    for index, cond_results in enumerate(eval_results[1:]):
        try:
            operator = operators[index]
        except IndexError:
            logger.warning('evaluation failed - not enough operators provided for the number of conditions set')
            break

        if operator == 'and':  # must pass all evaluation rules in the set
            results = results & cond_results
        else:  # must pass only one of the evaluation rules in the set
            results = results | cond_results

    if as_list is True:
        return list(results)
    else:
        return results


def evaluate_condition(data, condition):
    """
    Check whether rows in dataframe pass a given condition rule.
    """
    is_bool_dtype = pd.api.types.is_bool_dtype
    is_float_dtype = pd.api.types.is_float_dtype
    is_integer_dtype = pd.api.types.is_integer_dtype
    is_datetime_dtype = pd.api.types.is_datetime64_any_dtype

    operators = {'>': gt, '>=': ge, '<': lt, '<=': le, '==': eq, '=': eq, '!=': ne, 'in': isin, 'not in': notin}
    rev_operators = {'>': lt, '>=': le, '<': gt, '<=': ge, '==': eq, '=': eq, '!=': ne, 'in': isin, 'not in': notin}

    if isinstance(data, pd.Series):
        header = data.index.tolist()
        nrow = data.size
    elif isinstance(data, pd.DataFrame):
        header = data.columns.values.tolist()
        nrow = 1
    else:
        raise ValueError('data must be either a pandas DataFrame or Series')

    split_pttrn = '({})'.format('|'.join([' {} '.format(i) for i in operators]))
    rule = [i.strip() for i in re.split(split_pttrn, condition, flags=re.IGNORECASE)]
    if len(rule) == 3:  # data is evaluated on some condition rule
        left, oper, right = rule
        oper = oper.lower()
        if oper not in operators:
            raise SyntaxError('unable to parse rule condition {COND} - the operator {OPER} must separate two operands'
                              .format(COND=condition, OPER=oper))

        # Prepare the operation components
        if left in header:
            variable = data[left]

            if right in header:
                values = data[right]
            else:
                values = right

            oper_func = operators[oper]
        else:
            if right in header:
                variable = data[right]
                values = left

                oper_func = rev_operators[oper]
            else:
                raise SyntaxError('at least one operand must be a data field')

        # Enforce data type consistency between left and right
        dtype = variable.dtype
        if is_float_dtype(dtype):
            format_func = settings.format_as_float
        elif is_integer_dtype(dtype):
            format_func = settings.format_as_int
        elif is_datetime_dtype(dtype):
            format_func = settings.format_as_datetime
        elif is_bool_dtype(dtype):
            format_func = settings.format_as_bool
        else:
            format_func = str

        if isinstance(values, pd.Series):
            values = values.apply(format_func)
        else:
            values = format_func(values)

        # Evaluate the operation
        results = oper_func(variable, values)

    elif len(rule) == 1:  # data is tested for existence or truth
        eval_str = rule[0]
        if eval_str[0] == '!':  # not column values or NaN values
            colname = eval_str.replace(' ', '')[1:]
            if colname in header:
                if is_bool_dtype(data[colname].dtype) is True:
                    results = ~ data[colname]
                else:  # column values are NaN
                    results = data[colname].isna()
            else:
                results = pd.Series([False for _ in range(nrow)])
        else:  # column values or values that are not NaN
            colname = eval_str
            if colname in header:
                if is_bool_dtype(data[colname].dtype) is True:
                    results = data[colname]
                else:  # column values are not NaN
                    results = ~ data[colname].isna()
            else:
                results = pd.Series([False for _ in range(nrow)])
    else:
        raise SyntaxError('unable to parse rule condition {} - unknown format of the condition rule'.format(condition))

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


def evaluate_operation(data, operation):
    """
    Evaluate a given operation.
    """
    operators = {'+', '-', '*', '/', '>', '>=', '<', '<=', '==', '!='}

    if isinstance(data, pd.Series):
        header = data.index.tolist()
    elif isinstance(data, pd.DataFrame):
        header = data.columns.values.tolist()
    elif isinstance(data, dict):
        header = list(data)
    else:
        raise ValueError('data must be either a pandas DataFrame or Series')

    if isinstance(operation, str):
        components = parse_operation_string(operation)
    elif isinstance(operation, list):
        components = operation
    else:
        raise ValueError('operation {} must be provided as either a string or list'.format(operation))

    rule_value = []
    for i, component in enumerate(components):
        if component in operators:  # component is an operator
            rule_value.append(component)
        elif component in header:
            rule_value.append('data["{}"]'.format(component))
        elif component.lower() in header:
            rule_value.append('data["{}"]'.format(component.lower()))
        else:  # component is an integer or bool
            try:
                pd.to_numeric(component, downcast='integer')
            except Exception:
                logger.error('unsupported component {COMP} found in operation "{NAME}" - only column, operators, and '
                             'numeric values are allowed'.format(COMP=component, NAME=operation))
                raise
            else:
                rule_value.append(str(component))

    eval_str = ' '.join(rule_value)
    try:
        result = eval(eval_str)
    except SyntaxError:
        raise SyntaxError('invalid syntax for operation "{NAME}"'.format(NAME=operation))
    except NameError:  # dataframe does not have column
        raise NameError('unknown column found in operation "{NAME}"'.format(NAME=operation))

    return result


def parse_operation_string(condition, equivalent: bool = True):
    """
    Split operation string into a list.
    """
    operators = set('+-*/%><=!')

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


def isin(column, values):
    if isinstance(values, str):
        values = re.sub(r'[{}()\[\] ]', '', values).split(',')
    elif isinstance(values, pd.Series):
        values = values.tolist()

    return column.isin(values)


def notin(column, values):
    if isinstance(values, str):
        values = re.sub(r'[{}()\[\] ]', '', values).split(',')
    elif isinstance(values, pd.Series):
        values = values.tolist()

    return ~column.isin(values)


def ge(column, values):
    return column.ge(values)


def gt(column, values):
    return column.gt(values)


def eq(column, values):
    return column.eq(values)


def ne(column, values):
    return column.ne(values)


def le(column, values):
    return column.le(values)


def lt(column, values):
    return column.gt(values)
