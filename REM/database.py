"""
REM database import and export functions.
"""

import datetime
import pandas as pd

from REM.client import logger, settings, user


class SQLStatementError(Exception):
    """A simple exception that is raised when an SQL statement is formatted incorrectly.
    """

    def __init__(self, *args, **kwargs):
        Exception.__init__(self, *args)


# Database transaction functions
def construct_where_clause(filter_rules):
    """
    Construct an SQL statement where clause for querying and updating database tables.
    """
    if filter_rules is None or len(filter_rules) == 0:  # no filtering rules
        return ('', None)

    # Construct filtering rules
    if isinstance(filter_rules, list):  # multiple filter parameters
        all_params = []
        statements = []
        for rule in filter_rules:
            if isinstance(rule, tuple):
                try:
                    statement, params = rule
                except ValueError:
                    msg = 'incorrect data type for filter rule {}'.format(rule)
                    raise SQLStatementError(msg)

                if type(params) in (type(tuple()), type(list())):
                    # Unpack parameters
                    for param_value in params:
                        all_params.append(param_value)
                elif type(params) in (type(str()), type(int()), type(float())):
                    all_params.append(params)
                else:
                    msg = 'unknown parameter type {} in rule {}'.format(params, rule)
                    raise SQLStatementError(msg)

                statements.append(statement)
            else:
                statements.append(rule)

        params = tuple(all_params) if len(all_params) > 0 else None
        where = 'WHERE {}'.format(' AND '.join(statements))

    elif isinstance(filter_rules, tuple):  # single filter parameter
        try:
            statement, params = filter_rules
        except ValueError:
            statement = filter_rules[0]

        where = 'WHERE {COND}'.format(COND=statement)

    else:  # unaccepted data type provided
        msg = 'unaccepted data type {} provided in rule {}'.format(type(filter_rules), filter_rules)
        raise SQLStatementError(msg)

    return (where, params)


def convert_datatypes(value):
    """
    Convert values with numpy data-types to native data-types.
    """
    is_float_dtype = pd.api.types.is_float_dtype
    is_integer_dtype = pd.api.types.is_integer_dtype
    is_bool_dtype = pd.api.types.is_bool_dtype
    is_datetime_dtype = pd.api.types.is_datetime64_any_dtype

    if pd.isna(value):
        converted_value = None
    elif is_float_dtype(type(value)) is True or isinstance(value, float):
        converted_value = float(value)
    elif is_integer_dtype(type(value)) is True or isinstance(value, int):
        try:
            converted_value = int(value)
        except TypeError:
            converted_value = None
    elif is_bool_dtype(type(value)) is True or isinstance(value, bool):
        converted_value = bool(value)
    elif is_datetime_dtype(type(value)) or isinstance(value, datetime.datetime) or isinstance(value, datetime.date):
        strptime = datetime.datetime.strptime
        date_fmt = settings.date_format

        converted_value = strptime(value.strftime(date_fmt), date_fmt)
    else:
        converted_value = str(value)

    return converted_value


def prepare_sql_query(tables, columns='*', filter_rules=None, order=None, distinct: bool = False):
    """
    Prepare a statement and parameters for querying an ODBC database.

    Arguments:

        tables (str): primary table ID.

        columns: list or string containing the column(s) to select from the database table.

        filter_rules: tuple or list of tuples containing where clause and value tuple for a given filter rule.

        order: string or list of strings containing columns to sort results by.

        distinct (bool): add the distinct clause to the statement to return only unique entries.
    """
    # Define sorting component of query statement
    if type(order) in (type(list()), type(tuple())):
        if len(order) > 0:
            order_by = ' ORDER BY {}'.format(', '.join(order))
        else:
            order_by = ''
    elif isinstance(order, str):
        order_by = ' ORDER BY {}'.format(order)
    else:
        order_by = ''

    # Define column component of query statement
    colnames = ', '.join(columns) if type(columns) in (type(list()), type(tuple())) else columns

    # Construct filtering rules
    try:
        where_clause, params = construct_where_clause(filter_rules)
    except SQLStatementError as e:
        msg = 'failed to generate the query statement - {}'.format(e)
        logger.error(msg)

        raise SQLStatementError(msg)

    # Prepare the database transaction statement
    if not distinct:
        query_str = 'SELECT {COLS} FROM {TABLE} {WHERE} {SORT};'.format(COLS=colnames, TABLE=tables,
                                                                        WHERE=where_clause, SORT=order_by)
    else:
        query_str = 'SELECT DISTINCT {COLS} FROM {TABLE} {WHERE} {SORT};'.format(COLS=colnames, TABLE=tables,
                                                                                 WHERE=where_clause, SORT=order_by)

    logger.debug('query string is "{STR}" with parameters "{PARAMS}"'.format(STR=query_str, PARAMS=params))

    return (query_str, params)


def prepare_sql_insert(table, columns, values, statements: dict = None):
    """
    Prepare a statement and parameters for inserting a new entry into an ODBC database.
    """
    if not statements:
        statements = {}

    if isinstance(columns, str):
        columns = [columns]

    # Format parameters
    if isinstance(values, list):  # multiple insertions requested
        if not all([isinstance(i, tuple) for i in values]):
            msg = 'failed to generate insertion statement - individual transactions must be formatted as tuple'
            logger.error(msg)

            raise SQLStatementError(msg)

        if not all([len(columns) == len(i) for i in values]):
            msg = 'failed to generate insertion statement - the number of columns is not equal to the number ' \
                  'of provided parameters for all transactions requested'
            logger.error(msg)

            raise SQLStatementError(msg)

        params = []
        for param_tup in values:
            params.append(tuple([convert_datatypes(i) for i in param_tup]))

    elif isinstance(values, tuple):  # single insertion
        if len(columns) != len(values):
            msg = 'failed to generate insertion statement - the number of columns is not equal to the number ' \
                  'of parameters for the transaction'
            logger.error(msg)

            raise SQLStatementError(msg)

        params = [tuple([convert_datatypes(i) for i in values])]

    elif isinstance(values, str):  # single insertion for single column
        if len(columns) > 1:
            msg = 'failed to generate insertion statement - the number of columns is not equal to the number of ' \
                  'parameters for the transaction'
            logger.error(msg)

            raise SQLStatementError(msg)

        params = [(convert_datatypes(values),)]
    else:
        msg = 'failed to generate insertion statement - unknown values type {}'.format(type(values))
        logger.error(msg)

        raise SQLStatementError(msg)

    # Prepare the database transaction statement
    markers = '({})'.format(','.join(['?' for _ in columns]))
    insert_str = 'INSERT INTO {TABLE} {COLS} VALUES {VALS};' \
        .format(TABLE=table, COLS='({})'.format(','.join(columns)), VALS=markers)
    logger.debug('insertion string is "{STR}" with parameters "{PARAMS}"'.format(STR=insert_str, PARAMS=params))

    if insert_str not in statements:  # new transaction statement
        statements[insert_str] = []

    for param_tuple in params:  # only append unique parameter sets
        if param_tuple not in statements[insert_str]:
            statements[insert_str].append(param_tuple)

    return statements


def prepare_sql_update(table, columns, values, where_clause, filter_values, statements: dict = None):
    """
    Prepare a statement and parameters for updating an existing entry in an ODBC database.
    """
    if not statements:
        statements = {}

    # Format parameters
    if isinstance(values, list):  # multiple updates requested
        if not all([isinstance(i, tuple) for i in values]):
            msg = 'failed to generate update statement - individual transactions must be formatted as tuple'
            logger.error(msg)

            raise SQLStatementError(msg)

        if not all([len(columns) == len(i) for i in values]):
            msg = 'failed to generate update statement - the number of columns is not equal to the number ' \
                  'of provided parameters for all transactions requested'
            logger.error(msg)

            raise SQLStatementError(msg)

        if not isinstance(filter_values, list) or len(values) != len(filter_values):
            msg = 'failed to generate update statement - the number of transactions requested do not match the ' \
                  'number of filters provided'
            logger.error(msg)

            raise SQLStatementError(msg)

        params = []
        for index, param_tup in enumerate(values):
            # Convert parameter types
            mod_params = [convert_datatypes(i) for i in param_tup]

            # Add filter parameters to the end of the parameter list
            filter_tup = filter_values[index]
            mod_filter_params = [convert_datatypes(i) for i in filter_tup]
            mod_params = mod_params + mod_filter_params

            params.append(tuple(mod_params))

    elif isinstance(values, tuple):  # single update requested
        if len(columns) != len(values):
            msg = 'failed to generate update statement - the number of columns is not equal to the number of ' \
                  'provided parameters for the transaction'
            logger.error(msg)

            raise SQLStatementError(msg)

        if not isinstance(filter_values, tuple):
            msg = 'failed to generate update statement - the number of transactions requested do not match the ' \
                  'number of filters provided'
            logger.error(msg)

            raise SQLStatementError(msg)

        params = [tuple([convert_datatypes(i) for i in values] + [convert_datatypes(j) for j in filter_values])]

    elif isinstance(values, str) or pd.isna(values):  # single update of one column is requested
        if not isinstance(columns, str):
            msg = 'failed to generate update statement - the number of columns is not equal to the number of ' \
                  'provided parameters for the transaction'
            logger.error(msg)

            raise SQLStatementError(msg)

        params = [tuple([convert_datatypes(values)] + [convert_datatypes(j) for j in filter_values])]
    else:
        msg = 'failed to generate update statement - unknown values type {}'.format(type(values))
        logger.error(msg)

        raise SQLStatementError(msg)

    pair_list = ['{}=?'.format(colname) for colname in columns]

    # Prepare the database transaction statement
    update_str = 'UPDATE {TABLE} SET {PAIRS} WHERE {WHERE};' \
        .format(TABLE=table, PAIRS=','.join(pair_list), WHERE=where_clause)
    logger.debug('update string is "{STR}" with parameters "{PARAMS}"'.format(STR=update_str, PARAMS=params))

    if update_str not in statements:  # new transaction statement
        statements[update_str] = []

    for param_tuple in params:  # only append unique parameter sets
        if param_tuple not in statements[update_str]:
            statements[update_str].append(param_tuple)

    return statements


def prepare_sql_upsert(table, columns, values, conditionals, statements: dict = None):
    """
    Prepare a statement and parameters for inserting or updating an existing entry in an ODBC database, depending
    on whether it currently exists in the database or not.

    Arguments:
        table (str): name of the database table to modify.

        columns (list): list of database table columns that will be modified.

        values (tuple): tuple or list of tuples containing column values for the table entry / entries.

        conditionals (list): table column(s) used to match the existing table entries and the upsert entries.

        statements (dict): dictionary of current transaction statements to add to.
    """
    if not statements:
        statements = {}

    if isinstance(conditionals, str):
        conditionals = [conditionals]

    # Format parameters
    if isinstance(values, list):  # multiple updates requested
        if not all([isinstance(i, tuple) for i in values]):
            msg = 'failed to generate upsert statement - individual transactions must be formatted as tuple'
            logger.error(msg)

            raise SQLStatementError(msg)

        if not all([len(columns) == len(i) for i in values]):
            msg = 'failed to generate upsert statement - the number of columns is not equal to the number ' \
                  'of provided parameters for all transactions requested'
            logger.error(msg)

            raise SQLStatementError(msg)

        params = []
        for index, param_tup in enumerate(values):
            # Convert parameter types
            mod_params = [convert_datatypes(i) for i in param_tup]

            params.append(tuple(mod_params))

    elif isinstance(values, tuple):  # single update requested
        if len(columns) != len(values):
            msg = 'failed to generate upsert statement - the number of columns is not equal to the number of ' \
                  'provided parameters for the transaction'
            logger.error(msg)

            raise SQLStatementError(msg)

        params = [tuple([convert_datatypes(i) for i in values])]

    elif isinstance(values, str) or pd.isna(values):  # single update of one column is requested
        if not isinstance(columns, str):
            msg = 'failed to generate upsert statement - the number of columns is not equal to the number of ' \
                  'provided parameters for the transaction'
            logger.error(msg)

            raise SQLStatementError(msg)

        params = [tuple([convert_datatypes(values)])]
    else:
        msg = 'failed to generate upsert statement - unknown values type {}'.format(type(values))
        logger.error(msg)

        raise SQLStatementError(msg)

    # Conditional statement
    where_clause = ' AND '.join(['Target.{COL}=Source.{COL}'.format(COL=i) for i in conditionals])

    # Query terms of the command
    markers = '({})'.format(','.join(['?' for _ in columns]))

    # Insert terms of the command
    insert_cols = ','.join(columns)
    sr_cols_list = ['Source.{COL}'.format(COL=i) for i in columns]
    sr_cols_list_query = ','.join(sr_cols_list)

    # Update terms of the command
    up_cols_list = ['{COL}=Source.{COL}'.format(COL=i) for i in columns]
    up_cols_list_query = ','.join(up_cols_list)

    # Prepare the database transaction statement
    upsert_str = f'''
                  MERGE {table} AS Target 
                  USING (SELECT * FROM (VALUES {markers}) AS s ({insert_cols})) AS Source
                  ON {where_clause}
                  WHEN NOT MATCHED THEN
                  INSERT ({insert_cols}) VALUES ({sr_cols_list_query})
                  WHEN MATCHED THEN
                  UPDATE SET {up_cols_list_query};
                  '''
    logger.debug('update string is "{STR}" with parameters "{PARAMS}"'.format(STR=upsert_str, PARAMS=params))

    if upsert_str not in statements:  # new transaction statement
        statements[upsert_str] = []

    for param_tuple in params:  # only append unique parameter sets
        if param_tuple not in statements[upsert_str]:
            statements[upsert_str].append(param_tuple)

    return statements


def prepare_sql_delete(table, columns, values, statements: dict = None):
    """
    Prepare a statement and parameters for deleting an existing entry from an ODBC database.
    """
    if not statements:
        statements = {}

    if isinstance(columns, str):
        columns = [columns]

    # Format parameters
    if isinstance(values, list):
        if not all([isinstance(i, tuple) for i in values]):
            msg = 'failed to generate insertion statement - individual transactions must be formatted as tuple'
            logger.error(msg)

            raise SQLStatementError(msg)

        if not all([len(columns) == len(i) for i in values]):
            msg = 'failed to generate insertion statement - the number of columns is not equal to the number ' \
                  'of provided parameters for all transactions requested'
            logger.error(msg)

            raise SQLStatementError(msg)

        params = []
        for param_tup in values:
            params.append(tuple([convert_datatypes(i) for i in param_tup]))

    elif isinstance(values, tuple):  # single insertion
        if len(columns) != len(values):
            msg = 'failed to generate insertion statement - the number of columns is not equal to the number ' \
                  'of parameters for the transaction'
            logger.error(msg)

            raise SQLStatementError(msg)

        params = [tuple([convert_datatypes(i) for i in values])]

    elif isinstance(values, str):
        if len(columns) > 1:
            msg = 'failed to generate deletion statement - the number of columns is not equal to the number of ' \
                  'parameters for the transaction'
            logger.error(msg)

            raise SQLStatementError(msg)

        params = [(convert_datatypes(values),)]

    else:
        msg = 'failed to generate deletion statement - unknown values type {}'.format(type(values))
        logger.error(msg)

        raise SQLStatementError(msg)

    pairs = {}
    for colname in columns:
        if colname in pairs:
            pairs[colname].append('?')
        else:
            pairs[colname] = ['?']

    pair_list = []
    for colname in pairs:
        col_params = pairs[colname]
        if len(col_params) > 1:
            pair_list.append('{COL} IN ({VALS})'.format(COL=colname, VALS=', '.join(col_params)))
        elif len(col_params) == 1:
            pair_list.append('{COL}=?'.format(COL=colname))
        else:
            logger.warning('failed to generate deletion statement - column "{}" has no associated parameters'
                           .format(colname))
            continue

    # Prepare the database transaction statement
    delete_str = 'DELETE FROM {TABLE} WHERE {PAIRS}'.format(TABLE=table, PAIRS=' AND '.join(pair_list))
    logger.debug('deletion string is "{STR}" with parameters "{PARAMS}"'.format(STR=delete_str, PARAMS=params))

    if delete_str not in statements:  # new transaction statement
        statements[delete_str] = []

    for param_tuple in params:  # only append unique parameter sets
        if param_tuple not in statements[delete_str]:
            statements[delete_str].append(param_tuple)

    return statements


# DB formatting functions
def format_import_filters(import_rules):
    """
    Format filter parameters for querying.
    """
    operators = {'=', '!=', '>', '<', '>=', '<=', 'IN', 'NOT IN'}

    filters = []
    for import_table in import_rules:
        import_rule = import_rules[import_table]

        try:
            filter_rules = import_rule["Filters"]
        except KeyError:
            continue

        if filter_rules is None or not isinstance(filter_rules, dict):
            continue

        for filter_column in filter_rules:
            filter_entry = filter_rules[filter_column]

            try:
                operator = filter_entry[0].upper()
            except (IndexError, AttributeError):
                logger.error('the "Filters" parameter of import table {TBL} is missing the operator'
                             .format(TBL=import_table))
                continue
            else:
                if operator not in operators:
                    logger.error('unknown operator {OPER} supplied the "Filters" parameters of import table {TBL}'
                                 .format(OPER=operator, TBL=import_table))
                    continue

            try:
                parameters = filter_entry[1:]
            except IndexError:
                logger.error('the "Filters" parameters of import table {TBL} requires one or more import values'
                             .format(TBL=import_table))
                continue
            else:
                if len(parameters) == 1:
                    parameters = parameters[0]
                else:
                    parameters = tuple(parameters)

            if isinstance(parameters, list) or isinstance(parameters, tuple):
                values = ['?' for _ in parameters]
                value = '({VALS})'.format(VALS=', '.join(values))
            else:
                value = '?'

            if operator in ('IN', 'NOT IN') and 'NULL' not in parameters:
                filters.append(('({TBL}.{COL} {OPER} {VAL} OR {TBL}.{COL} IS NULL)'
                                .format(TBL=import_table, COL=filter_column, OPER=operator, VAL=value), parameters))
            else:
                filters.append(('{TBL}.{COL} {OPER} {VAL}'
                                .format(TBL=import_table, COL=filter_column, OPER=operator, VAL=value), parameters))

    return filters


def format_record_columns(import_rules):
    """
    Format columns for record creation.
    """
    columns = []
    for import_table in import_rules:
        import_rule = import_rules[import_table]

        import_columns = import_rule['Columns']
        for import_column in import_columns:
            column_alias = import_columns[import_column]
            if isinstance(column_alias, list):
                column = import_column
            else:
                column = column_alias

            columns.append(column)

    return columns


def get_import_column(import_rules, column):
    """
    Format a table column for querying.
    """
    query_column = None

    for import_table in import_rules:
        import_rule = import_rules[import_table]

        import_columns = import_rule['Columns']
        for import_column in import_columns:

            column_alias = import_columns[import_column]
            if isinstance(column_alias, list):
                if import_column == column:
                    column_alias = ['{TBL}.{COL}'.format(TBL=import_table, COL=i) for i in column_alias]
                    query_column = 'COALESCE({})'.format(','.join(column_alias), import_column)
            else:
                if column_alias == column:
                    query_column = '{TBL}.{COL}'.format(TBL=import_table, COL=import_column)

    return query_column


def format_tables(import_rules):
    """
    Define the table component of query statement.
    """
    joins = ('INNER JOIN', 'JOIN', 'LEFT JOIN', 'LEFT OUTER JOIN',
             'RIGHT JOIN', 'RIGHT OUTER JOIN', 'FULL JOIN',
             'FULL OUTER JOIN', 'CROSS JOIN')

    table_rules = []
    for i, import_table in enumerate(import_rules):
        import_rule = import_rules[import_table]

        join_rule = import_rule.get('Join', None)
        if join_rule is None and i == 0:
            table_rules.append(import_table)
        elif join_rule is None and i > 0:
            logger.error('a join rule is required to join data from import table {TBL}'
                         .format(TBL=import_table))
        else:
            try:
                join_type, join_on = join_rule[0:2]
            except ValueError:
                logger.error('import table {TBL} join rule {RULE} requires three components'
                             .format(TBL=import_table, RULE=join_rule))
                continue
            if join_type not in joins:
                logger.error('unknown join type {JOIN} provided for import table {TBL}'
                             .format(TBL=import_table, JOIN=join_type))
                continue

            opt_filters = ' AND '.join(join_rule[2:])
            if opt_filters:
                join_statement = '{JOIN} {TABLE} ON {ON} AND {OPTS}' \
                    .format(JOIN=join_type, TABLE=import_table, ON=join_on, OPTS=opt_filters)
            else:
                join_statement = '{JOIN} {TABLE} ON {ON}'.format(JOIN=join_type, TABLE=import_table, ON=join_on)
            table_rules.append(join_statement)

    return ' '.join(table_rules)

