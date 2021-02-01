"""
REM settings initializer.
"""

import datetime
import PySimpleGUI as sg
import os
import pandas as pd
from pymongo import MongoClient, errors
import pyodbc
import REM.constants as const
import REM.settings as prog_sets
import sys
import textwrap
import yaml


class RecordsConfiguration:
    """
    Class to store and manage program records configuration settings.

    Attributes:

        name (str): name of the configuration document.

        title (str): descriptive name of the configuration document.

        entries (list): List of record entries.
    """

    def __init__(self, records_doc):
        """
        Class to store and manage program records configuration settings.

        Arguments:

            records_doc: records document.
        """

        if records_doc is None:
            popup_error('Configuration Error: missing required configuration document Records')
            sys.exit(1)

        try:
            audit_name = records_doc['name']
        except KeyError:
            popup_error('Configuration Error: Records: the parameter "name" is a required field')
            sys.exit(1)
        else:
            self.name = audit_name

        try:
            self.title = records_doc['title']
        except KeyError:
            self.title = audit_name

        try:
            record_entries = records_doc['rules']
        except KeyError:
            popup_error('Configuration Error: Records: the parameter "rules" is a required field')
            sys.exit(1)

        self.entries = []
        for record_group in record_entries:
            record_entry = record_entries[record_group]
            self.entries.append(RecordEntry(record_group, record_entry))

    def print_entries(self, by_title: bool = False):
        """
        Print rules of a the rule set by its name or title.
        """
        if by_title is True:
            rule_names = [i.menu_title for i in self.entries]
        else:
            rule_names = [i.name for i in self.entries]

        return rule_names

    def fetch_entry(self, name, by_title: bool = False):
        """
        Fetch a given rule from the rule set by its name or title.
        """
        if by_title is True:
            rule_names = [i.menu_title for i in self.entries]
        else:
            rule_names = [i.name for i in self.entries]

        try:
            index = rule_names.index(name)
        except IndexError:
            print('Warning: Records: entry {NAME} not in list of configured records. Available record entries are {ALL}'
                  .format(NAME=name, ALL=', '.join(rule_names)))
            rule = None
        else:
            rule = self.entries[index]

        return rule


class RecordEntry:

    def __init__(self, name, entry):
        """
        Configuration record entry.
        """
        self.name = name

        try:
            self.permissions = entry['AccessPermissions']
        except KeyError:
            self.permissions = 'admin'

        try:
            self.menu_title = entry['MenuTitle']
        except KeyError:
            self.menu_title = name

        try:
            self.type = entry['RecordType']
        except KeyError:
            popup_error('Configuration Error: RecordEntry {NAME}: missing required parameter "RecordType"'
                        .format(NAME=name))
            sys.exit(1)

        try:
            self.id_code = entry['IDCode']
        except KeyError:
            popup_error('Configuration Error: RecordEntry {NAME}: missing required parameter "IDCode"'
                        .format(NAME=name))
            sys.exit(1)

        # Database import rules
        try:
            import_rules = entry['ImportRules']
        except KeyError:
            popup_error('Configuration Error: RecordEntry {NAME}: missing required parameter "ImportRules"'
                        .format(NAME=name))
            sys.exit(1)
        else:
            for import_table in import_rules:
                import_rule = import_rules[import_table]

                if 'Columns' not in import_rule:
                    popup_error('Configuration Error: RecordsEntry {NAME}: missing required "ImportRules" {TBL} parameter '
                                '"Columns"'.format(NAME=name, TBL=import_table))
                    sys.exit(1)
                if 'Filters' not in import_rule:
                    import_rule['Filters'] = None

        self.import_rules = import_rules

        # Database export rules
        try:
            export_rules = entry['ExportRules']
        except KeyError:
            popup_error('Configuration Error: RecordEntry {NAME}: missing required parameter "ExportRules"'
                        .format(NAME=name))
            sys.exit(1)
        else:
            for export_table in export_rules:
                export_rule = export_rules[export_table]
                if 'Columns' not in export_rule:
                    popup_error('Configuration Error: RecordEntry {NAME}: missing required "ExportRules" {TBL} parameter '
                                '"Columns"'.format(NAME=name, TBL=export_table))
                    sys.exit(1)

        self.export_rules = export_rules

        # Import table layout configuration
        try:
            self.import_table = entry['ImportTable']
        except KeyError:
            popup_error('Configuration Error: RecordEntry {NAME}: missing required parameter "ImportTable"'
                        .format(NAME=name))
            sys.exit(1)

        # Record layout configuration
        try:
            self.record_layout = entry['RecordLayout']
        except KeyError:
            popup_error('Configuration Error: RecordsEntry {NAME}: missing required parameter "RecordLayout"'
                        .format(NAME=name))
            sys.exit(1)

        self.ids = []

    def format_import_filters(self):
        """
        Format filter parameters for querying.
        """
        operators = {'=', '!=', '>', '<', '>=', '<=', 'IN', 'NOT IN'}

        import_rules = self.import_rules

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

                if isinstance(parameters, list) or isinstance(parameters, tuple):
                    values = ['?' for _ in parameters]
                    value = '({VALS})'.format(VALS=', '.join(values))
                else:
                    value = '?'

                filters.append(('{TBL}.{COL} {OPER} {VAL}'
                                .format(TBL=import_table, COL=filter_column, OPER=operator, VAL=value), parameters))

        return filters

    def format_import_columns(self):
        """
        Format columns for querying.
        """
        converter_functions = {'CAST', 'CONVERT'}

        import_rules = self.import_rules

        columns = []
        for import_table in import_rules:
            import_rule = import_rules[import_table]

            import_columns = import_rule['Columns']

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
                            column = '{FUNC}({COL} AS {DTYPE}({SIZE}))'\
                                .format(FUNC=converter, COL=column, DTYPE=dtype, SIZE=col_size)
                        else:
                            column = '{FUNC}({COL} AS {DTYPE})'.format(FUNC=converter, COL=column, DTYPE=dtype)
                else:
                    column = column

                if column_alias != import_column:
                    column = '{COL} AS {ALIAS}'.format(COL=column, ALIAS=column_alias)

                columns.append(column)

        return columns

    def format_tables(self):
        """
        Define the table component of query statement.
        """
        joins = ('INNER JOIN', 'JOIN', 'LEFT JOIN', 'LEFT OUTER JOIN',
                 'RIGHT JOIN', 'RIGHT OUTER JOIN', 'FULL JOIN',
                 'FULL OUTER JOIN', 'CROSS JOIN')

        import_rules = self.import_rules

        table_rules = []
        for i, import_table in enumerate(import_rules):
            import_rule = import_rules[import_table]

            join_rule = import_rule.get('Join', None)
            if join_rule is None and i == 0:
                table_rules.append(import_table)
            elif join_rule is None and i > 0:
                print('Configuration Error: RecordEntry {NAME}: a join rule is required to join data from import '
                      'table {TBL}'.format(NAME=self.name, TBL=import_table))
            else:
                try:
                    tbl1_field, tbl2_field, join_clause = join_rule[0:3]
                except ValueError:
                    print('Configuration Error: RecordEntry {NAME}: import table {TBL} join rule {RULE} requires '
                          'three components'.format(NAME=self.name, TBL=import_table, RULE=join_rule))
                    continue
                if join_clause not in joins:
                    print('Configuration Error: RecordEntry {NAME}: unknown join type {JOIN} provided for import table '
                          '{TBL}'.format(NAME=self.name, TBL=import_table, JOIN=join_clause))
                    continue

                opt_filters = ' AND '.join(join_rule[3:])
                if opt_filters:
                    join_statement = '{JOIN} {TABLE} ON {F1}={F2} AND {OPTS}'\
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

    def import_records(self, user):
        """
        Import all records from the database.
        """

        # Add configured import filters
        filters = self.format_import_filters()
        table_statement = self.format_tables()
        columns = self.format_import_columns()

        # Query existing database entries
        import_df = user.query(table_statement, columns=columns, filter_rules=filters, prog_db=True)

        return import_df

    def load_record(self, record_id):
        """
        Load a record from the database using the record ID.
        """
        # Add configured import filters
        table_statement = self.format_tables()
        columns = self.format_import_columns()

        # Query existing database entries
        primary_table = self.get_primary_table()
        id_col = self.get_primary_id_column()

        filters = '{TBL}.{COL} = ?'.format(TBL=primary_table, COL=id_col)
        query_str = 'SELECT {COL} FROM {TBL} WHERE {FILT}'.format(COL=', '.join(columns), TBL=table_statement, FILT=filters)

        import_df = program_account.query(query_str, params=(record_id, ))

        if import_df.empty:
            popup_error('Record {ID} not found in the database'.format(ID=record_id))
            record_data = None
        else:
            record_data = import_df

        return record_data

    def export_record(self, user, record):
        """
        Save a record to the database.
        """
        ref_table = configuration.reference_lookup
        delete_code = configuration.delete_code
        export_rules = self.export_rules

        # Check if the record is already in the database and remove from list of unsaved IDs, if applicable
        record_id = record.record_id

        id_exists = not self.remove_unsaved_id(record_id)

        # Iterate over export columns
        saved = []
        for table in export_rules:
            table_entry = export_rules[table]

            references = table_entry['Columns']
            id_col = references['RecordID']

            # Prepare column value updates
            export_columns = []
            export_values = []
            for param in record.parameters:
                param_col = param.name

                try:
                    db_col = references[param_col]
                except KeyError:
                    print('Warning: RecordEntry {NAME}: parameter {PARAM} not found in list of export columns'
                          .format(NAME=self.name, PARAM=param_col))
                    continue

                export_columns.append(db_col)
                export_values.append(param.value)

            if id_exists is True:  # record already exists in the database
                # Edit an existing record in the database
                export_columns += [configuration.editor_code, configuration.edit_date]
                export_values += [user.id, datetime.datetime.now().strftime(settings.format_date_str())]

                filters = ('{} = ?'.format(id_col), (record_id,))
                saved.append(user.update(table, export_columns, export_values, filters))

                # Add / remove associations

                # References
                orig_refs = [i.ref_id for i in record._references]
                current_refs = [i.ref_id for i in record.references]

                deleted_refs = set(orig_refs).difference(set(current_refs))
                for deleted_ref in deleted_refs:
                    ref_filters = [('DocNo = ?', record_id), ('RefNo = ?', deleted_ref)]
                    saved.append(user.update(ref_table, [configuration.editor_code, configuration.edit_date, delete_code],
                                             [user.name, datetime.datetime.now(), 1], ref_filters))

                added_refs = set(current_refs).difference(set(orig_refs))
                for added_ref in added_refs:
                    ref_record = record.fetch_reference(added_ref, by_id=True)
                    ref_type = ref_record.ref_type
                    ref_columns = ['DocNo', 'DocType', 'RefNo', 'RefType', 'RefDate', configuration.creator_code,
                                   configuration.creation_date]
                    ref_values = [record_id, self.type, added_ref, ref_type, datetime.datetime.now(), user.name,
                                  datetime.datetime.now()]
                    saved.append(user.insert(ref_table, ref_columns, ref_values))

                # Components
                comp_tables = record.components
                for comp_table in comp_tables:
                    try:
                        orig_comps = comp_table._df['RecordID']
                    except KeyError:
                        print('Warning: RecordEntry {NAME}: component table {TBL} has no "RecordID" column'
                              .format(NAME=self.name, TBL=comp_table))
                        continue

                    comp_type = comp_table.record_type
                    if comp_type is None:
                        print('Warning: RecordEntry {NAME}: component table {TBL} has no record type assigned'
                              .format(NAME=self.name, TBL=comp_table))
                        continue

                    current_comps = comp_table.df['RecordID']

                    deleted_comps = set(orig_comps).difference(set(current_comps))
                    for deleted_comp in deleted_comps:
                        comp_filters = [('DocNo = ?', record_id), ('RefNo = ?', deleted_comp)]
                        saved.append(user.update(ref_table, [configuration.editor_code, configuration.edit_date, delete_code],
                                                 [user.name, datetime.datetime.now(), 1], comp_filters))

                    added_comps = set(current_comps).difference(set(orig_comps))
                    for added_comp in added_comps:
                        comp_columns = ['DocNo', 'DocType', 'RefNo', 'RefType', 'RefDate', configuration.creator_code,
                                        configuration.creation_date]
                        comp_values = [record_id, self.type, added_comp, comp_type, datetime.datetime.now(), user.name,
                                       datetime.datetime.now()]
                        saved.append(user.insert(ref_table, comp_columns, comp_values))

            else:  # record does not exist yet, must be inserted
                # Create new entry for the record in the database
                export_columns += [configuration.creator_code, configuration.creation_date]
                export_values += [user.id, datetime.datetime.now().strftime(settings.format_date_str())]

                saved.append(user.insert(table, export_columns, export_values))

                # Add any associations to the reference lookup database
                for reference_record in record.references:
                    ref_id = reference_record.ref_id
                    ref_type = reference_record.ref_type
                    ref_columns = ['DocNo', 'DocType', 'RefNo', 'RefType', 'RefDate', configuration.creator_code,
                                   configuration.creation_date]
                    ref_values = [record_id, self.type, ref_id, ref_type, datetime.datetime.now(), user.name,
                                  datetime.datetime.now()]
                    saved.append(user.insert(ref_table, ref_columns, ref_values))

        return all(saved)

    def delete_record(self, user, record):
        """
        Delete a record from the database.
        """
        ref_table = configuration.reference_lookup
        delete_code = configuration.delete_code

        export_rules = self.export_rules
        record_id = record.record_id

        # Check if the record can be found in the list of unsaved ids
        id_exists = not self.remove_unsaved_id(record_id)

        if id_exists is True:  # record is already saved in the database, must be deleted
            # Delete the record from the database
            updated = []
            for export_table in export_rules:
                table_entry = export_rules[export_table]

                references = table_entry['Columns']
                id_column = references['RecordID']

                # Remove record from the export table
                filters = ('{} = ?'.format(id_column), record_id)
                updated.append(user.update(export_table, [delete_code], [1], filters))

            # Remove all record associations
            ref_filters = [('DocNo = ?', record_id), ('RefNo = ?', record_id)]
            updated.append(user.update(ref_table, [configuration.editor_code, configuration.edit_date, delete_code],
                                       [user.name, datetime.datetime.now(), 1], ref_filters))

        else:  # record was never saved, can remove the ID
            updated = [True]

        return all(updated)

    def import_references(self, record_id):
        """
        Import record references.
        """
        ref_table = configuration.reference_lookup
        columns = ['DocNo', 'RefNo', 'RefDate', 'DocType', 'RefType']

        # Define query statement
        query_str = 'SELECT {COLS} FROM {TABLE} WHERE {COL1} = ? OR {COL2} = ?;'\
            .format(COLS=','.join(columns), COL1='DocNo', COL2='RefNo', TABLE=ref_table)
        import_df = program_account.query(query_str, params=(record_id, record_id))

        return import_df

    def import_record_ids(self, record_date: datetime.datetime = None):
        """
        Import existing record IDs.
        """
        primary_table = self.get_primary_table()
        id_column = self.get_primary_id_column()

        # Define query statement
        params = None
        if record_date is not None:
            # Search for database records with date within the same month
            try:
                first_day = record_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                last_day = datetime.datetime(record_date.year + record_date.month // 12, record_date.month % 12 + 1, 1) - datetime.timedelta(1)
            except AttributeError:
                query_str = 'SELECT {COL} FROM {TABLE} ORDER BY {COL};'\
                    .format(COL=id_column, TABLE=primary_table)
            else:
                query_str = 'SELECT {COL} FROM {TABLE} WHERE {DATE} BETWEEN ? AND ? ORDER BY {COL};'\
                    .format(COL=id_column, TABLE=primary_table, DATE=configuration.date_field)
                params = (first_day, last_day)
        else:
            query_str = 'SELECT {COL} FROM {TABLE} ORDER BY {COL};'.format(COL=id_column, TABLE=primary_table)
        import_rows = program_account.query(query_str, params=params)

        # Connect to database
        id_list = []
        for index, row in import_rows.iterrows():
            record_id = row[id_column]
            if record_id not in id_list:
                id_list.append(record_id)

        return id_list

    def create_id(self, record_date):
        """
        Create a new record ID.
        """
        id_code = self.id_code
        unsaved_ids = self.ids

        # Format the date component of the new ID
        formatted_date = settings.apply_date_offset(record_date)
        id_date = formatted_date.strftime(settings.format_date_str(date_str='YYMM'))

        print('Info: RecordEntry {NAME}: new ID has date component {COMP}'.format(NAME=self.name, COMP=id_date))

        # Search list of unsaved IDs occurring within the current date cycle
        print('Info: RecordEntry {NAME}: searching for unsaved record IDs with date component {DATE}'
              .format(NAME=self.name, DATE=id_date))
        prev_ids = []
        for unsaved_id in unsaved_ids:
            prev_date = self.id_date_component(unsaved_id)
            if prev_date == id_date:
                prev_ids.append(unsaved_id)

        print('Info: RecordEntry {NAME}: found {NUM} unsaved records with date component {DATE}'
              .format(NAME=self.name, NUM=len(prev_ids), DATE=id_date))

        # Search list of saved IDs occurring within the current date cycle
        if len(prev_ids) < 1:
            print('Info: RecordEntry {NAME}: searching for database record IDs with date component {DATE}'
                  .format(NAME=self.name, DATE=id_date))

            # Search list of saved IDs occurring within the current date cycle for the last created ID
            db_ids = self.import_record_ids(record_date=record_date)
            for db_id in db_ids:
                prev_date = self.id_date_component(db_id)
                if prev_date == id_date:
                    prev_ids.append(db_id)

            print('Info: RecordEntry {NAME}: found {NUM} database records with date component {DATE}'
                  .format(NAME=self.name, NUM=len(prev_ids), DATE=id_date))

        # Get the number of the last ID used in the current date cycle
        if len(prev_ids) > 0:
            last_id = sorted(prev_ids)[-1]
        else:
            last_id = None

        print('Info: RecordEntry {NAME}: last ID encountered is {ID}'.format(NAME=self.name, ID=last_id))

        # Create the new ID
        if last_id:
            try:
                last_num = int(last_id.split('-')[-1])
            except ValueError:
                print('Error: Record {NAME}: incorrect formatting for previous ID {ID}'
                      .format(NAME=self.name, ID=last_id))
                return None
        else:
            last_num = 0
        record_id = '{CODE}{DATE}-{NUM}'.format(CODE=id_code, DATE=id_date, NUM=str(last_num + 1).zfill(4))

        print('Info: RecordEntry {NAME}: new record ID is {ID}'.format(NAME=self.name, ID=record_id))

        # Add ID to the list of unsaved IDs
        self.ids.append(record_id)

        return record_id

    def id_date_component(self, record_id):
        """
        Get the date component of a record ID.
        """
        id_code = self.id_code
        code_len = len(id_code)
        try:
            id_name, id_num = record_id.split('-')
        except ValueError:
            raise AttributeError('No date component found for {TYPE} record ID {ID}'
                                 .format(TYPE=self.type, ID=record_id))

        return id_name[code_len:]

    def remove_unsaved_id(self, record_id):
        """
        Remove record ID from the list of unsaved IDs
        """
        try:
            self.ids.remove(record_id)
        except ValueError:
            print('Warning: RecordEntry {NAME}: record {ID} was not found in the list of unsaved {TYPE} record IDs'
                  .format(NAME=self.name, ID=record_id, TYPE=self.type))
            success = False
        else:
            print('Info: RecordEntry {NAME}: removing unsaved record ID {ID}'.format(NAME=self.name, ID=record_id))
            success = True

        return success

    def remove_ids(self, id_list):
        """
        Remove select IDs from the list of unsaved IDs.
        """
        ids = self.ids
        self.ids = [i for i in ids if i not in id_list]


class Config:
    """
    Class to the program configuration from a MongoDB document.
    """

    def __init__(self, cnfg):
        # Program paths
        self.dirname = _dirname

        self.icons_dir = os.path.join(self.dirname, 'docs', 'images', 'icons')

        # Database parameters
        try:
            self.mongod_port = cnfg['configuration']['mongod_port']
        except KeyError:
            self.mongod_port = 27017
        try:
            self.mongod_server = cnfg['configuration']['mongod_server']
        except KeyError:
            self.mongod_server = 'localhost'
        try:
            self.mongod_database = cnfg['configuration']['mongod_database']
        except KeyError:
            self.mongod_database = 'REM'
        try:
            self.mongod_config = cnfg['configuration']['mongod_config']
        except KeyError:
            self.mongod_config = 'configuration'
        try:
            self.mongod_user = cnfg['configuration']['mongod_user']
        except KeyError:
            self.mongod_user = 'mongo'
        try:
            self.mongod_pwd = cnfg['configuration']['mongod_pwd']
        except KeyError:
            self.mongod_pwd = ''
        try:
            self.mongod_authdb = cnfg['configuration']['mongod_authdb']
        except KeyError:
            self.mongod_authdb = 'REM'

        # Table field parameters
        try:
            self.creator_code = cnfg['fields']['creator_code_field']
        except KeyError:
            self.creator_code = 'CreatorName'
        try:
            self.creation_date = cnfg['fields']['creation_date_field']
        except KeyError:
            self.creation_date = 'CreationTime'
        try:
            self.editor_code = cnfg['fields']['editor_code_field']
        except KeyError:
            self.editor_code = 'EditorName'
        try:
            self.edit_date = cnfg['fields']['edit_date_field']
        except KeyError:
            self.edit_date = 'EditTime'
        try:
            self.delete_code = cnfg['fields']['delete_field']
        except KeyError:
            self.delete_code = 'IsDeleted'
        try:
            self.id_field = cnfg['fields']['id_field']
        except KeyError:
            self.id_field = 'DocNo'
        try:
            self.date_field = cnfg['fields']['date_field']
        except KeyError:
            self.date_field = 'DocDate'

        # Lookup tables
        try:
            self.reference_lookup = cnfg['tables']['records']
        except KeyError:
            self.reference_lookup = 'RecordReferences'

        try:
            self.bank_lookup = cnfg['tables']['bank']
        except KeyError:
            self.bank_lookup = 'BankAccounts'

        # Connection parameters
        self.cnx = None
        self.database = None
        self.collection = None

        # Program configuration parameters
        self.audit_rules = None
        self.cash_rules = None
        self.bank_rules = None
        self.startup_msgs = None
        self.ids = None
        self.records = None
        self.data_db = None

    def connect(self, timeout=5000):
        """
        Connect to the NoSQL database using the pymongo driver.
        """
        print('Info: connecting to the configuration database')
        connection_info = {'username': self.mongod_user, 'password': self.mongod_pwd,
                           'host': self.mongod_server, 'port': self.mongod_port,
                           'authSource': self.mongod_authdb, 'serverSelectionTimeoutMS': timeout}
        try:
            cnx = MongoClient(**connection_info)
        except errors.ConnectionFailure as e:
            print('Error: connection to configuration database failed - {}'.format(e))
            cnx = None
        else:
            self.cnx = cnx

        return cnx

    def load_database(self):
        """
        Load the NoSQL database containing the configuration collection.
        """
        if self.cnx is None:
            cnx = self.connect()
            if cnx is None:
                return None
            else:
                self.cnx = cnx
        else:
            cnx = self.cnx

        print('Info: loading the configuration database')
        try:
            database = cnx[self.mongod_database]
        except errors.InvalidName:
            print('Error: cannot access database {}'.format(self.mongod_database))
            database = None
        else:
            self.database = database

        return database

    def load_collection(self):
        """
        Load the configuration collection.
        """
        if self.database is None:
            database = self.load_database()
            if database is None:
                return {}
        else:
            database = self.database

        print('Info: loading the database collection')
        try:
            collection = database[self.mongod_config]
        except errors.InvalidName:
            collection = {}
        else:
            self.collection = collection

        return collection

    def load_configuration(self):
        """
        Load the configuration documents.
        """
        if self.collection is None:
            collection = self.load_collection()
            if collection is None:
                popup_error('Unable to load configuration from the configuration database')
                sys.exit(1)
        else:
            collection = self.collection

        try:
            print(self.cnx.server_info())
        except Exception as e:
            popup_error('Unable to load the configuration from the database - {}'.format(e))
            print(e)
            sys.exit(1)
        else:
            self.audit_rules = collection.find_one({'name': 'audit_rules'})
            self.cash_rules = collection.find_one({'name': 'cash_rules'})
            self.bank_rules = collection.find_one({'name': 'bank_rules'})
            self.startup_msgs = collection.find_one({'name': 'startup_messages'})
            self.records = RecordsConfiguration(collection.find_one({'name': 'records'}))
            self.ids = collection.find_one({'name': 'ids'})

    def get_icon_path(self, icon):
        """
        Return the path of an icon, if exists.
        """
        icon = "{}.png".format(icon)
        icon_path = os.path.join(self.icons_dir, icon)
        if not os.path.exists(icon_path):
            print('Error: unable to open icon PNG {ICON}'.format(ICON=icon))
            icon_path = None

        return icon_path


class ProgramAccount:
    """
    Program account object.

    Attributes:
        uid (str): existing account username.

        pwd (str): associated account password.
    """

    def __init__(self, cnfg):
        self.uid = cnfg['database']['odbc_user']
        self.pwd = cnfg['database']['odbc_pwd']

        self.database = cnfg['database']['odbc_database']
        self.server = cnfg['database']['odbc_server']
        self.port = cnfg['database']['odbc_port']
        self.driver = cnfg['database']['odbc_driver']
        self.date_str = format_date_str(cnfg['database']['date_format'])

    def db_connect(self, timeout: int = 2):
        """
        Generate a pyODBC Connection object.
        """
        uid = self.uid
        pwd = self.pwd
        if r'"' in pwd or r';' in pwd or r"'" in pwd:
            pwd = "{{{}}}".format(pwd)

        driver = self.driver
        server = self.server
        port = self.port
        dbname = self.database

        db_settings = {'Driver': driver,
                       'Server': server,
                       'Database': dbname,
                       'Port': port,
                       'UID': uid,
                       'PWD': pwd,
                       'Trusted_Connection': 'no'}

        conn_str = ';'.join(['{}={}'.format(k, db_settings[k]) for k in db_settings if db_settings[k]])
        print('Info: connecting to database {DB}'.format(DB=dbname))

        try:
            conn = pyodbc.connect(conn_str, timeout=timeout)
        except pyodbc.Error:
            print('Warning: failed to establish a connection to {}'.format(dbname))
            raise
        else:
            print('Info: successfully established a connection to {}'.format(dbname))

        return conn

    def database_tables(self, timeout: int = 2):
        """
        Get database schema information.
        """
        try:
            conn = self.db_connect(timeout=timeout)
        except pyodbc.Error as e:
            print('DB Read Error: connection to database cannot be established - {ERR}'.format(ERR=e))
            return None
        else:
            try:
                cursor = conn.cursor()
            except AttributeError:
                print('DB Read Error: connection to database cannot be established')
                return None
            else:
                try:
                    return cursor.tables()
                except pyodbc.Error:
                    print('DB Read Error: unable to find tables associated with database {}'.format(self.database))
                    return None

    def table_schema(self, table, timeout: int = 2):
        """
        Get table schema information.
        """
        try:
            conn = self.db_connect(timeout=timeout)
        except pyodbc.Error as e:
            print('DB Read Error: connection to database cannot be established - {ERR}'.format(ERR=e))
            return None
        else:
            try:
                cursor = conn.cursor()
            except AttributeError:
                print('DB Read Error: connection to database cannot be established')
                return None
            else:
                try:
                    return cursor.columns(table=table)
                except pyodbc.Error:
                    print('DB Read Error: unable to read the schema for table {}'.format(table))
                    return None

    def query(self, statement, params: tuple = None, timeout=5):
        """
        Query the program database.
        """
        try:
            conn = self.db_connect(timeout=timeout)
        except Exception as e:
            print('DB Read Error: connection to database cannot be established - {ERR}'.format(ERR=e))
            return pd.DataFrame()
        else:
            try:
                cursor = conn.cursor()
            except AttributeError:
                print('DB Read Error: connection to database {DB} cannot be established'.format(DB=self.database))
                results = pd.DataFrame()
            else:
                try:
                    if params is not None:
                        print('Info: query statement supplied is {} with parameters {}'.format(statement, params))
                        results = pd.read_sql(statement, conn, params=params)
                    else:
                        print('Info: query statement supplied is {} with no parameters'.format(statement))
                        results = pd.read_sql(statement, conn)
                    cursor.execute(statement, params)
                except pyodbc.Error as e:  # possible duplicate entries
                    print('DB Read Error: {ERR}'.format(ERR=e))
                    results = pd.DataFrame()
                else:
                    print('Info: database {} successfully queried'.format(self.database))

                # Close the cursor
                cursor.close()

            # Close the connection
            conn.close()

        return results

    def query_ids(self, table, column, timeout=2):
        """
        Query table for list of unique entry IDs.
        """

        # Define query statement
        query_str = 'SELECT DISTINCT {COL} FROM {TABLE} ORDER BY {COL};'.format(COL=column, TABLE=table)

        # Connect to database
        id_list = []
        try:
            conn = self.db_connect(timeout=timeout)
        except Exception as e:
            print('DB Write Error: connection to database cannot be established - {ERR}'.format(ERR=e))
        else:
            try:
                cursor = conn.cursor()
            except AttributeError:
                print('DB Write Error: connection to database {DB} cannot be established'.format(DB=self.database))
            else:
                try:
                    cursor.execute(query_str)
                except pyodbc.Error as e:  # possible duplicate entries
                    print('DB Write Error: {ERR}'.format(ERR=e))
                else:
                    print('Info: database {DB} successfully read'.format(DB=self.database))

                    for row in cursor.fetchall():
                        id_list.append(row[0])

                    # Close the connection
                    cursor.close()
                    conn.close()

        # Add return value to the queue
        return id_list


def popup_error(msg):
    """
    Display popup notifying user that there is a fatal program error.
    """
    font = const.MID_FONT
    return sg.popup_error(textwrap.fill(msg, width=40), font=font, title='')


def format_date_str(date_str):
    """
    Format a date string for use as input to datetime method.
    """
    separators = set(':/- ')
    date_fmts = {'YYYY': '%Y', 'YY': '%y',
                 'MMMM': '%B', 'MMM': '%b', 'MM': '%m', 'M': '%-m',
                 'DD': '%d', 'D': '%-d',
                 'HH': '%H', 'MI': '%M', 'SS': '%S'}

    strfmt = []
    last_char = date_str[0]
    buff = [last_char]
    for char in date_str[1:]:
        if char not in separators:
            if last_char != char:
                # Check if char is first in a potential series
                if last_char in separators:
                    buff.append(char)
                    last_char = char
                    continue

                # Check if component is minute
                if ''.join(buff + [char]) == 'MI':
                    strfmt.append(date_fmts['MI'])
                    buff = []
                    last_char = char
                    continue

                # Add characters in buffer to format string and reset buffer
                component = ''.join(buff)
                strfmt.append(date_fmts[component])
                buff = [char]
            else:
                buff.append(char)
        else:
            component = ''.join(buff)
            try:
                strfmt.append(date_fmts[component])
            except KeyError:
                if component:
                    raise TypeError('unknown component {} provided to date string {}.'.format(component, date_str))

            strfmt.append(char)
            buff = []

        last_char = char

    try:  # format final component remaining in buffer
        strfmt.append(date_fmts[''.join(buff)])
    except KeyError:
        raise TypeError('unsupported characters {} found in date string {}'.format(''.join(buff), date_str))

    return ''.join(strfmt)


# Determine if application is a script file or frozen exe
if getattr(sys, 'frozen', False):
    _dirname = os.path.dirname(sys.executable)
elif __file__:
    _dirname = os.path.dirname(__file__)
else:
    popup_error('Unable to determine file type of the program')
    sys.exit(1)

# Load global configuration settings
_prog_cnfg_name = 'configuration.yaml'
_prog_cnfg_file = os.path.join(_dirname, _prog_cnfg_name)

try:
    _prog_fh = open(_prog_cnfg_file, 'r', encoding='utf-8')
except FileNotFoundError:
    msg = 'Unable to load configuration file at {}'.format(_prog_cnfg_file)
    popup_error(msg)
    sys.exit(1)
else:
    _prog_cnfg = yaml.safe_load(_prog_fh)
    _prog_fh.close()
    del _prog_fh

print('Info: loading the configuration')
configuration = Config(_prog_cnfg)
configuration.load_configuration()

# Connect to database as program user
program_account = ProgramAccount(_prog_cnfg)

# Obtain lists of used entry IDs for the program tables
current_tbl_pkeys = {}
for _db_table in configuration.ids['PrimaryKeys']:
    _tbl_id_column = configuration.ids['PrimaryKeys'][_db_table]
    current_tbl_pkeys[_db_table] = program_account.query_ids(_db_table, _tbl_id_column)

# Load user-defined configuration settings
_user_cnfg_name = 'settings.yaml'
_user_cnfg_file = os.path.join(_dirname, _user_cnfg_name)

try:
    _user_fh = open(_user_cnfg_file, 'r', encoding='utf-8')
except FileNotFoundError:
    msg = 'Unable to load configuration file at {}'.format(_user_cnfg_file)
    popup_error(msg)
    sys.exit(1)
else:
    _user_cnfg = yaml.safe_load(_user_fh)
    _user_fh.close()
    del _user_fh

settings = prog_sets.UserSettings(_user_cnfg, _dirname)
