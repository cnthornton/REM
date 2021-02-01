"""
REM database import and export functions.
"""


def format_import_filters(import_rules):
    """
    Format filter parameters for querying.
    """
    operators = {'=', '!=', '>', '<', '>=', '<=', 'IN', 'NOT IN'}

    filters = []
    for import_table in import_rules:
        import_rule = import_rules[import_table]
        filter_rules = import_rule["Filters"]
        if filter_rules is None or not isinstance(filter_rules, dict):
            continue

        for filter_column in filter_rules:
            filter_entry = filter_rules[filter_column]

            try:
                operator = filter_entry[0].upper()
            except (IndexError, AttributeError):
                print('Error: the "Filters" parameter of import table {TBL} is missing the operator'
                      .format(TBL=import_table))
                continue
            else:
                if operator not in operators:
                    print('Error: unknown operator {OPER} supplied the "Filters" parameters of import table {TBL}'
                          .format(OPER=operator, TBL=import_table))
                    continue

            try:
                parameters = filter_entry[1:]
            except IndexError:
                print('Error: the "Filters" parameters of import table {TBL} requires one or more import values'
                      .format(TBL=import_table))
                continue
            else:
                if len(parameters) == 1:
                    parameters = parameters[0]

            if isinstance(parameters, list) or isinstance(parameters, tuple):
                values = ['?' for _ in parameters]
                value = '({VALS})'.format(VALS=', '.join(values))
            else:
                value = '?'

            filters.append(('{TBL}.{COL} {OPER} {VAL}'
                            .format(TBL=import_table, COL=filter_column, OPER=operator, VAL=value), parameters))

    return filters


def format_import_columns(import_rules):
    """
    Format columns for querying.
    """
    converter_functions = {'CAST', 'CONVERT'}

    columns = []
    for import_table in import_rules:
        import_rule = import_rules[import_table]

        import_columns = list(import_rule['Columns'])

        try:
            modifiers = import_rule['Modifiers']
        except KeyError:
            modifiers = {}

        for import_column in import_columns:
            column_alias = import_columns[import_column]
            column_modifier = modifiers.get(import_column, None)

            column = '{TBL}.{COL}'.format(TBL=import_table, COL=import_column)

            if column_modifier is not None:
                try:
                    converter, dtype, col_size = column_modifier
                except ValueError:
                    try:
                        converter, dtype = column_modifier
                    except KeyError:
                        print('Warning: the "Modifiers" parameter of import table {TBL} requires at minimum a '
                              'converter function and data type'.format(TBL=import_table))
                        converter = dtype = col_size = None
                    else:
                        col_size = None
                if converter not in converter_functions:
                    print('Warning: unknown converter function {FUNC} supplied to the "Modifiers parameter of '
                          'import table {TBL}"'.format(FUNC=converter, TBL=import_table))
                    column = import_column
                else:
                    if col_size is not None:
                        column = '{FUNC}({COL} AS {DTYPE}({SIZE}))' \
                            .format(FUNC=converter, COL=column, DTYPE=dtype, SIZE=col_size)
                    else:
                        column = '{FUNC}({COL} AS {DTYPE})'.format(FUNC=converter, COL=column, DTYPE=dtype)
            else:
                column = column

            if column_alias != import_column:
                column = '{COL} AS {ALIAS}'.format(COL=column, ALIAS=column_alias)

            columns.append(column)

    return columns


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
            print('Configuration Error: a join rule is required to join data from import table {TBL}'
                  .format(TBL=import_table))
        else:
            try:
                tbl1_field, tbl2_field, join_clause = join_rule[0:3]
            except ValueError:
                print('Configuration Error: import table {TBL} join rule {RULE} requires three components'
                      .format(TBL=import_table, RULE=join_rule))
                continue
            if join_clause not in joins:
                print('Configuration Error: unknown join type {JOIN} provided for import table {TBL}'
                      .format(TBL=import_table, JOIN=join_clause))
                continue

            opt_filters = ' AND '.join(join_rule[3:])
            if opt_filters:
                join_statement = '{JOIN} {TABLE} ON {F1}={F2} AND {OPTS}' \
                    .format(JOIN=join_clause, TABLE=import_table, F1=tbl1_field, F2=tbl2_field, OPTS=opt_filters)
            else:
                join_statement = '{JOIN} {TABLE} ON {F1}={F2}'.format(JOIN=join_clause, TABLE=import_table,
                                                                      F1=tbl1_field, F2=tbl2_field)
            table_rules.append(join_statement)

    return ' '.join(table_rules)


def get_primary_table(self):
    """
    Get the primary record table.
    """
    import_rules = self.import_rules
    return list(import_rules.keys())[0]


def get_primary_id_column(self):
    """
    Get the ID column of the primary record table
    """
    import_rules = self.import_rules

    id_col = 'DocNo'

    table = self.get_primary_table()
    table_entry = import_rules[table]

    table_cols = table_entry['Columns']
    for column in table_cols:
        column_alias = table_cols[column]
        if column_alias == 'RecordID':
            id_col = column
            break

    return id_col
