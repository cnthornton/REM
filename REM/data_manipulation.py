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


def evaluate_condition_set(data, conditions):
    """
    Check whether data pass a given set of conditions.

    Arguments:
        data: dictionary, Series, or DataFrame of data containing one or more condition variables.

        conditions (dict): set of conditions to evaluate.

    Returns:
        results (pd.Series): indexes that either passed or failed the condition set.
    """
    #chain_operators = ['and', 'or', 'OR', 'AND', 'And', 'Or']
    chain_operators = ('and', 'or')

    if isinstance(data, pd.DataFrame):
        nrow = data.shape[0]
    elif isinstance(data, pd.Series) or isinstance(data, dict):
        nrow = 1
    else:
        raise ValueError('data must be either a DataFrame, Series, or dictionary')

    eval_results = []  # stores list of lists or pandas Series of bools to pass into formatter
    operators = []
    for i, rule_name in enumerate(conditions):
        rule_str = conditions[rule_name]  # db column name is dictionary key

        if i != 0:  # add a join operator for each set of conditions following the first
            operators.append('and')

        split_pttrn = '({})'.format('|'.join([' {} '.format(i) for i in chain_operators]))
        rule_list = [i.strip() for i in re.split(split_pttrn, rule_str, flags=re.IGNORECASE)]

        for component in rule_list:  # each condition in the set is evaluated separately at first
            if component.lower() in chain_operators:  # item is a chain operator (and / or)
                operators.append(component.lower())
            else:  # item is a separate rule
                try:
                    logger.debug('provided data will be evaluated on condition {}'.format(component))
                    cond_results = evaluate_condition(data, component)
                    cond_results = cond_results.fillna(False).astype(np.bool_, errors='raise')
                except Exception as e:
                    logger.warning('evaluation failed - {}. Setting values to default "False"'.format(e))
                    cond_results = pd.Series([False for _ in range(nrow)])

                print('results of the evaluation are:')
                print(cond_results)
                eval_results.append(cond_results)

    results = eval_results[0]  # results of first condition evaluation
    for index, cond_results in enumerate(eval_results[1:]):  # results of subsequent condition evaluations
        try:
            operator = operators[index]
        except IndexError:
            logger.warning('evaluation failed - not enough operators provided for the number of conditions set')
            results = pd.Series([False for _ in range(nrow)])

            break

        if operator == 'and':  # must pass all evaluation rules in the set
            results = results & cond_results
        else:  # must pass only one of the evaluation rules in the set
            results = results | cond_results

    return results


def evaluate_condition(data, condition):
    """
    Check whether rows in dataframe pass a given condition rule.

    Arguments:
        data: dictionary, Series, or DataFrame of data containing one or more condition variables.

        condition: condition to test.

    Returns:
        results (pd.Series): results of the evaluation for each row of data provided.
    """
    is_bool_dtype = pd.api.types.is_bool_dtype
    is_float_dtype = pd.api.types.is_float_dtype
    is_integer_dtype = pd.api.types.is_integer_dtype
    is_datetime_dtype = pd.api.types.is_datetime64_any_dtype

    operators = {'>': gt, '>=': ge, '<': lt, '<=': le, '==': eq, '=': eq, '!=': ne, 'in': isin, 'not in': notin}
    rev_operators = {'>': lt, '>=': le, '<': gt, '<=': ge, '==': eq, '=': eq, '!=': ne, 'in': isin, 'not in': notin}

    if isinstance(data, pd.Series):  # single data entry
        header = data.index.tolist()
        data = data.to_frame().T
        nrow = data.size
    elif isinstance(data, pd.DataFrame):  # one or more entries
        header = data.columns.tolist()
        nrow = 1
    elif isinstance(data, dict):  # one or more entries
        try:
            data = pd.DataFrame(data)
        except ValueError:  # single entry was given
            data = pd.DataFrame(data, index=[0])
        header = data.columns.tolist()
        nrow = data.size
    else:
        raise ValueError('data must be either a pandas DataFrame or Series')

    split_pttrn = '({})'.format('|'.join([' {} '.format(i) for i in operators]))
    rule = [i.strip() for i in re.split(split_pttrn, condition, flags=re.IGNORECASE) if not i.isspace()]
    if len(rule) == 3:  # data is evaluated on some condition rule
        left, oper, right = rule
        oper = oper.lower()
        if oper not in operators:
            raise SyntaxError('unable to parse rule condition {COND} - the operator {OPER} must separate two operands'
                              .format(COND=condition, OPER=oper))

        # Prepare the operation components
        if left in header or left[1:] in header:
            variable = retrieve_values(data, left)

            if right in header or right[1:] in header:
                values = retrieve_values(data, right)
            else:
                values = right

            oper_func = operators[oper]
        else:
            if right in header or right[1:] in header:
                variable = retrieve_values(data, right)
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
        if eval_str[0] == '!':  # reverse truth or existence
            colname = eval_str.replace(' ', '')[1:]
            if colname in header:
                if is_bool_dtype(data[colname].dtype) is True:  # test for truth
                    results = ~ data[colname]
                else:  # test for existence (none NaN values)
                    results = data[colname].isna()
            else:
                logger.warning('condition value {VAL} is not in the data header'.format(VAL=colname))
                results = pd.Series([False for _ in range(nrow)])
        else:  # column values or values that are not NaN
            colname = eval_str
            if colname in header:
                print('data field {} has value'.format(colname))
                print(data[colname])
                if is_bool_dtype(data[colname].dtype) is True:
                    results = data[colname]
                else:  # column values are not NaN
                    results = ~ data[colname].isna()
            else:
                logger.warning('condition value {VAL} is not in the data header'.format(VAL=colname))
                results = pd.Series([False for _ in range(nrow)])
    else:
        raise SyntaxError('unable to parse rule condition {} - unknown format of the condition rule'.format(condition))

    return results


def evaluate_operation(data, operation):
    """
    Evaluate a given operation.

    Arguments:
        data: dictionary, Series, or DataFrame of data containing one or more operation variables.

        operation:  operation to carry out on the data.

    Returns:
        results (pd.Series): results of the evaluation for each row of data provided.
    """
    operators = {'+', '-', '*', '/', '%', '!'}

    if isinstance(data, pd.Series):
        header = data.index.tolist()
    elif isinstance(data, pd.DataFrame):
        header = data.columns.tolist()
    elif isinstance(data, dict):
        header = list(data)
    else:
        raise ValueError('data must be either a pandas DataFrame, Series, or a dictionary')

    if isinstance(operation, str):
        components = parse_operation_string(operation)
    elif isinstance(operation, list):
        components = operation
    else:
        raise ValueError('operation {} must be provided as either a string or list'.format(operation))

    rule_value = []
    for i, component in enumerate(components):
        if component in operators:  # component is an operator
            if component == '!':
                rule_value.append('~')
            else:
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


def parse_operation_string(operation, substitute: dict = None):
    """
    Split operation string into a list.

    Arguments:
        operation (str): operation string to parse.

        substitute (dict): one-to-one dictionary of operator substitutions.
    """
    operators = set('+-*/%><=!')

    if not substitute:
        substitute = {}

    # Find the column names and operators defined in the condition rule
    parsed_condition = []
    buff = []
    prev_char = None
    for char in operation:
        if char.isspace():  # skip whitespace
            parsed_condition.append(''.join(buff))
            buff = []
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

    for oper in substitute:
        oper_sub = substitute[oper]
        #parsed_condition = [i.replace(oper, oper_sub) if len(i) == 1 else i for i in parsed_condition if i]
        parsed_condition = [oper_sub if i == oper else i for i in parsed_condition]

    return parsed_condition


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
    return column.lt(values)


def retrieve_values(df, colname):
    colname = colname.replace(' ', '')

    if colname[0] == '!':
        colname = colname[1:]
        values = ~df[colname]
    else:
        values = df[colname]

    return values
