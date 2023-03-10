"""
REM function for manipulating data.
"""

import numpy as np
import pandas as pd
import re

from REM.client import logger, settings


def calc_column_widths(header, width: int = 1200, font_size: int = 13, pixels=False):
    """
    Calculate width of table columns based on the number of columns displayed.
    """
    # Size of data
    ncol = len(header)

    # When table columns not long enough, need to adjust so that the table fills the empty space.
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


def format_value(value, dtype, date_format: str = None):
    """
    Set the datatype for a single value.

    Arguments:
        value (Series): non-iterable value to set.

        dtype (str): scalar data type.

        date_format (str): formatted date string to use instead of the program default.
    """
    if dtype in ('date', 'datetime', 'timestamp', 'time'):
        dt = settings.date_format if date_format is None else date_format
        value = np.datetime64(pd.to_datetime(value, format=dt, utc=False))
    elif dtype in ('int', 'integer', 'bigint'):
        value = np.int_(value)
    elif dtype == 'mediumint':
        value = np.intc(value)
    elif dtype == 'smallint':
        value = np.short(value)
    elif dtype in ('tinyint', 'bit'):
        value = np.byte(value)
    elif dtype in ('float', 'real', 'double'):  # approximate numeric data types for saving memory
        value = np.single(value)
    elif dtype in ('decimal', 'dec', 'numeric', 'money'):  # exact numeric data types
        value = np.double(value)
    elif dtype in ('bool', 'boolean'):
        value = np.bool_(value)
    else:
        value = np.str_(value)

    return value


def format_values(values, dtype, formatters: dict = None, extended: bool = True):
    """
    Set the datatype for an array of values.

    Arguments:
        values (Series): pandas Series containing array values.

        dtype (str): array data type.

        formatters (dict): custom formatting options.

        extended (bool): use Pandas extended data types for integers.
    """
    formatters = settings.formatters if not formatters else formatters

    if not isinstance(values, pd.Series):
        values = pd.Series(values)

    if dtype in ('date', 'datetime', 'timestamp', 'time'):
        date_formatters = formatters.get('date', {})
        date_format = date_formatters.get('format', settings.date_format)

        try:
            values = pd.to_datetime(values.fillna(pd.NaT), errors='coerce', format=date_format).dt.tz_localize(None)
        except Exception as e:
            msg = 'failed to set column values to datatype {DTYPE} - {ERR}'.format(DTYPE=dtype, ERR=e)

            raise ValueError(msg)

    elif dtype in ('int', 'integer', 'bigint'):
        if extended:
            try:
                values = values.astype('Int64')
            except TypeError:
                values = values.astype(float).astype('Int64')
        else:
            values = values.fillna(-1).astype(int)
    elif dtype == 'mediumint':
        if extended:
            try:
                values = values.astype('Int32')
            except TypeError:
                values = values.astype(float).astype('Int32')
        else:
            values = values.fillna(-1).astype(int)
    elif dtype == 'smallint':
        if extended:
            try:
                values = values.astype('Int16')
            except TypeError:
                values = values.astype(float).astype('Int16')
        else:
            values = values.fillna(-1).astype(int)
    elif dtype in ('tinyint', 'bit'):
        if extended:
            try:
                values = values.astype('Int8')
            except TypeError:
                values = values.astype(float).astype('Int8')
        else:
            values = values.fillna(-1).astype(int)
    elif dtype in ('float', 'real', 'double'):  # approximate numeric data types for saving memory
        values = pd.to_numeric(values, errors='coerce', downcast='float')
    elif dtype in ('decimal', 'dec', 'numeric', 'money'):  # exact numeric data types
        values = pd.to_numeric(values, errors='coerce')
    elif dtype in ('bool', 'boolean'):
        values = values.fillna(False).astype(np.bool_, errors='raise')
    else:  # convert anything else to an object
        values = values.astype(np.object_, errors='raise')

    return values


def downcast_extended(values):
    """
    Convert extended Pandas data types to numpy data types.
    """
    is_bool_dtype = pd.api.types.is_bool_dtype
    is_int_dtype = pd.api.types.is_integer_dtype
    is_float_dtype = pd.api.types.is_float_dtype
    is_string_dtype = pd.api.types.is_string_dtype
    is_extension_dtype = pd.api.types.is_extension_array_dtype

    if is_extension_dtype(values):
        if is_int_dtype(values):
            downcast_values = values.fillna(-1).astype(int)
        elif is_bool_dtype(values):
            downcast_values = values.fillna(False).astype(np.bool_, errors='raise')
        elif is_float_dtype(values):
            downcast_values = pd.to_numeric(values, errors='coerce')
        elif is_string_dtype(values):
            downcast_values = values.astype(np.object_, errors='raise')
        else:
            raise TypeError('unsupported extended datatype {TYPE} provided'.format(TYPE=values.dtype))
    else:
        downcast_values = values

    return downcast_values


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
    is_bool_dtype = pd.api.types.is_bool_dtype
    is_extension_dtype = pd.api.types.is_extension_array_dtype

    reserved_chars = ('and', 'or', 'in', 'not', '+', '-', '/', '//', '*', '**', '%', '>', '>=', '<', '<=', '==', '!=',
                      '~', ',', '(', ')', '[', ']', '{', '}')

    if isinstance(data, pd.Series):  # single data entry
        df = data.to_frame().T
    elif isinstance(data, pd.DataFrame):  # one or more entries
        df = data.copy()
    elif isinstance(data, dict):  # one or more entries
        try:
            df = pd.DataFrame(data)
        except ValueError:  # single entry was given
            df = pd.DataFrame(data, index=[0])
    else:
        raise ValueError('data must be either a pandas DataFrame or Series')

    header = df.columns.tolist()

    if isinstance(expression, str):
        components = parse_expression(expression)
    elif isinstance(expression, list):
        components = expression
    else:
        raise ValueError('expression {} must be provided as either a string or list'.format(expression))

    logger.debug('creating evaluation expression from components: {}'.format(components))
    if len(components) > 1:
        # Quote non-numeric, static expression variables
        exp_comps = []
        for component in components:
            if component in header:
                col_values = df[component]
                if is_extension_dtype(col_values):
                    try:
                        df.loc[:, component] = downcast_extended(col_values)
                    except TypeError:
                        logger.exception('failed to downcast component {COMP} values'.format(COMP=component))

                        raise

                exp_comp = '`{}`'.format(component)
            elif is_numeric(component) or component in reserved_chars:
                exp_comp = component
            else:  # component is a string
                exp_comp = '"{}"'.format(component)

            exp_comps.append(exp_comp)

        expression = ' '.join(exp_comps)
        logger.info('evaluating conditional on expression {}'.format(expression))
        try:
            df_match = df.eval(expression)
        except ValueError:
            print(df)
            print(df.dtypes)

            raise
    else:  # component is a single static value or column values
        expression = ' '.join(components)
        logger.info('evaluating conditional on expression {}'.format(expression))
        if expression in header:
            values = df[expression]
            if is_bool_dtype(values.dtype):
                logger.debug('conditional expression is a header column with a boolean data type')
                df_match = values
            else:
                logger.debug('conditional expression is a header column with a non-boolean data type')
                df_match = ~ values.isna()
        else:
            logger.debug('conditional expression is a static value')
            df_match = df.eval(expression)

    if not isinstance(df_match, pd.Series):
        df_match = pd.Series(df_match, df.index)

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
    is_extension_dtype = pd.api.types.is_extension_array_dtype

    if isinstance(data, pd.Series):
        df = data.to_frame().T
    elif isinstance(data, pd.DataFrame):
        df = data.copy()
    elif isinstance(data, dict):
        try:
            df = pd.DataFrame(data)
        except ValueError:  # single entry was given
            df = pd.DataFrame(data, index=[0])
    else:
        raise ValueError('data must be either a pandas DataFrame, Series, or a dictionary')

    header = df.columns.tolist()

    if isinstance(expression, str):
        components = parse_expression(expression)
    elif isinstance(expression, list):
        components = expression
    else:
        components = parse_expression(str(expression))

    logger.debug('creating evaluation expression from components: {}'.format(components))
    if len(components) > 1:
        exp_comps = []
        for component in components:
            if component in header:
                col_values = df[component]
                if is_extension_dtype(col_values):
                    try:
                        df.loc[:, component] = downcast_extended(col_values)
                    except TypeError:
                        logger.exception('failed to downcast component {COMP} values'.format(COMP=component))

                        raise

                exp_comp = '`{}`'.format(component)
            else:
                exp_comp = component

            exp_comps.append(exp_comp)

        exp_str = ' '.join(exp_comps)
        logger.info('evaluating operation on expression {}'.format(exp_str))
        results = df.eval(exp_str).squeeze()
    else:  # results are a single static value or the values of a column in the dataframe
        exp_str = ' '.join(components)
        logger.info('evaluating operation on expression {}'.format(exp_str))
        if exp_str in header:
            logger.debug('expression is a header column')
            results = df[exp_str].squeeze()
        else:
            logger.debug('expression is a constant')
            results = exp_str

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
    #bool_pttrn = '|'.join(map(re.escape, ('and', 'or', 'not', 'in')))
    bool_pttrn = '|'.join(map(re.escape, (' and ', ' or ', ' not ', ' in ')))
    expression = re.sub(bool_pttrn, lambda match: match.group().lower(), expression, flags=re.IGNORECASE)

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
