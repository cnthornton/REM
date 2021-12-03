"""
REM function for manipulating data.
"""

import re
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


def evaluate_condition(data, expression):
    """
    Evaluate a boolean expression for a set of data.

    Arguments:
        data: dictionary, Series, or DataFrame of data potentially containing one or more variables used in the
            operation.

        expression: string or list of expression components describing a conditional statement to evaluate on the
            provided data.

    Returns:
        results (pd.Series): results of the evaluation for each row of data provided.
    """
    reserved_chars = ('and', 'or', 'in', 'not', '+', '-', '/', '//', '*', '**', '%', '>', '>=', '<', '<=', '==', '!=',
                      '~', ',', '(', ')', '[', ']', '{', '}')

    if isinstance(data, pd.Series):  # single data entry
        df = data.to_frame().T
    elif isinstance(data, pd.DataFrame):  # one or more entries
        df = data
    elif isinstance(data, dict):  # one or more entries
        try:
            df = pd.DataFrame(data)
        except ValueError:  # single entry was given
            df = pd.DataFrame(data, index=[0])
    else:
        raise ValueError('data must be either a pandas DataFrame or Series')

    if isinstance(expression, str):
        components = parse_expression(expression)
    elif isinstance(expression, list):
        components = expression
    else:
        raise ValueError('expression {} must be provided as either a string or list'.format(expression))

    # Quote non-numeric, static expression variables
    header = df.columns.tolist()
    expression = ' '.join([i if (i in header or is_numeric(i) or i in reserved_chars) else '"{}"'.format(i) for i in
                           components])

    print('evaluating conditional expression: {}'.format(expression))
    df_match = df.eval(expression)
    print('results of the evaluation are:')
    print(df_match)

    return df_match


def evaluate_operation(data, expression):
    """
    Evaluate a mathematical expression for a set of data.

    Arguments:
        data: dictionary, Series, or DataFrame of data potentially containing one or more variables used in the
            operation.

        expression: string or list of expression components describing an operation to evaluate on the provided data.

    Returns:
        results (pd.Series): results of the evaluation for each row of data provided.
    """
    if isinstance(data, pd.Series):
        df = data.to_frame().T
    elif isinstance(data, pd.DataFrame):
        df = data
    elif isinstance(data, dict):
        try:
            df = pd.DataFrame(data)
        except ValueError:  # single entry was given
            df = pd.DataFrame(data, index=[0])
    else:
        raise ValueError('data must be either a pandas DataFrame, Series, or a dictionary')

    if isinstance(expression, str):
        components = parse_expression(expression)
    elif isinstance(expression, list):
        components = expression
    else:
        components = parse_expression(str(expression))

    expression = ' '.join(components)
    header = df.columns.tolist()

    print('evaluating math expression: {}'.format(expression))
    if len(components) > 1:
        results = df.eval(expression).squeeze()
    else:
        if expression in header:
            results = df[expression].squeeze()
        else:
            results = expression
    print('results of the evaluation are:')
    print(results)

    return results


def parse_expression(expression):
    """
    Prepare an expression for evaluation.

    Arguments:
        expression (str): expression string to parse.
    """
    operators = set('+-*/%><=!^')
    group_chars = set('()[]{},')

    # Remove any quotations around expression components
    expression = re.sub(r'"|\'', '', expression)

    # Ensure that any boolean word operators are lowercase (pandas requirement)
    bool_pttrn = ' | '.join(map(re.escape, ('and', 'or', 'not', 'in')))
    expression = re.sub(bool_pttrn, lambda match: match.group(0).lower(), expression, flags=re.IGNORECASE)

    # Separate the different components of the expression
    parsed_expression = []
    buff = []
    prev_char = None
    for char in expression:
        if char.isspace():  # skip whitespace, flush buffer
            parsed_expression.append(''.join(buff))
            buff = []
        elif char in group_chars:  # flush buffer and append grouping character
            parsed_expression.append(''.join(buff))
            parsed_expression.append(char)
            buff = []
        elif char in operators:  # character is an operator
            if prev_char not in operators:  # flush buffer for non-operator
                parsed_expression.append(''.join(buff))

                buff = [char]
            else:  # previous character was also in the operator set
                buff.append(char)
                parsed_expression.append(''.join(buff))

                buff = []
        else:  # character is not operator or whitespace, append to buffer
            if prev_char in operators:  # flush buffer for single char operator
                parsed_expression.append(''.join(buff))

                buff = [char]
            else:
                buff.append(char)

        prev_char = char

    parsed_expression.append(''.join(buff))  # flush remaining characters in buffer

    # Replace common operators with their python/pandas equivalents
    substitutions = {'^': '**', '!': '~', '=': '=='}
    parsed_expression[:] = [substitutions[i] if i in substitutions else i for i in parsed_expression if i]

    return parsed_expression


def is_numeric(input):
    """
    Test if a string can be converted into a numeric data type.

    Arguments:
        input (str): input string.
    """
    try:
        pd.to_numeric(input)
        return True
    except ValueError:
        return False
