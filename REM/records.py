"""
REM records classes and functions. Includes audit records and account records.
"""

from bs4 import BeautifulSoup
import datetime
import sys
from random import randint
import re

import PySimpleGUI as sg
import dateutil
import numpy as np
import pandas as pd

import REM.constants as mod_const
import REM.data_manipulation as mod_dm
import REM.database as mod_db
import REM.elements as mod_elem
import REM.layouts as mod_lo
import REM.parameters as mod_param
import REM.secondary as mod_win2
from REM.client import logger, server_conn, settings, user


class RecordAssociation:
    """
    Manages the relationship between record types.

    Attributes:
        name (str): name of the association.

        association_type (str): can be one_to_one, one_to_many, or many_to_many.

        association_table (str): name of the database junction table, if relevant.

        primary (dict): entity description of the primary record in the association.

        relation (dict): entity description of the relation record in the association.
    """

    def __init__(self, entry):
        """
        Initialize association attributes.

        Arguments:
            entry (dict): configuration entry for the record association.
        """
        try:
            self.name = entry['Name']
        except KeyError:
            raise AttributeError('missing required configuration field "Name"')

        try:
            association_type = entry['AssociationType']
        except KeyError:
            raise AttributeError('missing required configuration field "AssociationType"')
        else:
            if association_type in ['one_to_one', 'one_to_many', 'many_to_many']:
                self.association_type = association_type
            else:
                raise AttributeError('"AssociationType" must be one of "one_to_one", "one_to_many", or "many_to_many"')

        try:
            self.association_table = entry['AssociationTable']
        except KeyError:
            self.association_table = None

        if association_type == 'many_to_many' and self.association_table is None:
            raise AttributeError('the "AssociationTable" field is required for record associations of type '
                                 '"many_to_many"')

        try:
            primary = entry['Primary']
        except KeyError:
            raise AttributeError('missing required configuration field "Primary"')

        self.primary = {}

        required_primary_fields = ['RecordType', 'PrimaryKey', 'ForeignKey']
        for field in required_primary_fields:
            try:
                self.primary[field] = primary[field]
            except KeyError:
                raise AttributeError('Primary entity is missing required field "{FIELD}"'.format(FIELD=field))

        participation_map = {'optional': 0, 'mandatory': 1}
        try:
            participation = primary['Participation']
        except KeyError:
            self.primary['Participation'] = 0  # default optional participation
        else:
            try:
                self.primary['Participation'] = int(participation)
            except ValueError:
                if participation in participation_map:
                    self.primary['Participation'] = participation_map[participation]
                else:
                    raise AttributeError('Unknown value "{VAL}" provided to the primary entities Participation field'
                                         .format(VAL=participation))

        try:
            relation = entry['Relation']
        except KeyError:
            raise AttributeError('missing required configuration field "Relation"')

        self.relation = {}

        required_relation_fields = ['RecordType', 'PrimaryKey']
        if self.association_table is not None:
            required_relation_fields.append('ForeignKey')

        for field in required_relation_fields:
            try:
                self.relation[field] = relation[field]
            except KeyError:
                raise AttributeError('Relation entity is missing required field "{FIELD}"'.format(FIELD=field))

        try:
            participation = relation['Participation']
        except KeyError:
            self.relation['Participation'] = 0  # default optional participation
        else:
            try:
                self.relation['Participation'] = int(participation)
            except ValueError:
                if participation in participation_map:
                    self.relation['Participation'] = participation_map[participation]
                else:
                    raise AttributeError('Unknown value "{VAL}" provided to the relation entities Participation field'
                                         .format(VAL=participation))

    def get_entity(self, identifier):
        """
        Fetch the relevant entity configuration using the provided identifier.
        """
        if identifier == self.primary['RecordType']:
            return self.primary
        elif identifier == self.relation['RecordType']:
            return self.relation
        else:
            raise KeyError('no record entity involved in the association matches the provided key "{IDENT}"'
                           .format(IDENT=identifier))


class RecordEntry:

    def __init__(self, name, entry):
        """
        Configuration record entry.

        Arguments:
            name (str): name of the record entry.

            entry (dict): configuration entry for the record.
        """
        self.name = name

        # Specify whether a record entry is a program record or an external record
        try:
            self.program_record = bool(int(entry['ProgramRecord']))
        except KeyError:  # parameter not specified
            self.program_record = True
        except ValueError:  # wrong data type provided to parameter
            msg = 'Configuration Error: "ProgramRecord" must be either 0 (False) or 1 (True)'
            logger.error('RecordEntry {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
            mod_win2.popup_error(msg)

            self.program_record = True

        # Set record menu parameters
        try:
            menu = entry['Menu']
        except KeyError:
            menu = {'MenuTitle': self.name, 'MenuGroup': None, 'AccessPermissions': 'admin'}
            self.show_menu = False
        else:
            self.show_menu = True
            if 'MenuGroup' not in menu:
                menu['MenuGroup'] = None
            if 'MenuTitle' not in menu:
                menu['MenuTitle'] = self.name
            if 'AccessPermissions' not in menu:
                menu['AccessPermissions'] = 'admin'

        self.permissions = menu['AccessPermissions']
        self.menu_title = menu['MenuTitle']
        self.menu_group = menu['MenuGroup']

        try:
            self.id_code = entry['IDCode']
        except KeyError:
            mod_win2.popup_error('RecordEntry {NAME}: configuration missing required parameter "IDCode"'
                                 .format(NAME=name))
            sys.exit(1)

        # Database import rules
        try:
            import_rules = entry['ImportRules']
        except KeyError:
            mod_win2.popup_error('RecordEntry {NAME}: configuration missing required parameter "ImportRules"'
                                 .format(NAME=name))
            sys.exit(1)
        else:
            for import_table in import_rules:
                import_rule = import_rules[import_table]

                if 'Columns' not in import_rule:
                    mod_win2.popup_error('RecordsEntry {NAME}: configuration missing required "ImportRules" {TBL} '
                                         'parameter "Columns"'.format(NAME=name, TBL=import_table))
                    sys.exit(1)
                if 'Filters' not in import_rule:
                    import_rule['Filters'] = None

        self.import_rules = import_rules

        # Database export rules
        if self.program_record:
            try:
                export_rules = entry['ExportRules']
            except KeyError:
                self.export_rules = {}
                for table in self.import_rules:
                    table_entry = self.import_rules[table]
                    import_columns = table_entry['Columns']

                    export_columns = {}
                    for import_column in import_columns:
                        import_alias = import_columns[import_column]
                        if isinstance(import_alias, list):
                            for export_column in import_alias:
                                export_columns[export_column] = import_column
                        else:
                            export_columns[import_alias] = import_column

                    self.export_rules[table] = {'Columns': export_columns}
            else:
                self.export_rules = {}
                for export_table in export_rules:
                    export_rule = export_rules[export_table]

                    if 'Columns' not in export_rule:
                        mod_win2.popup_error('RecordsEntry {NAME}: configuration missing required "ExportRules" {TBL} '
                                             'parameter "Columns"'.format(NAME=name, TBL=export_table))
                        sys.exit(1)

                    self.export_rules[export_table] = export_rule
        else:  # only program records can export records to the database
            self.export_rules = {}

        # Record association rules
        try:
            association_rules = entry['AssociationRules']
        except KeyError:
            logger.info('RecordsEntry {NAME}: no association rules specified for the record entry'
                        .format(NAME=self.name))
            association_rules = {}

        self.association_rules = {}
        for rule_name in association_rules:
            rule = association_rules[rule_name]

            if 'Primary' not in rule:
                msg = 'RecordEntry {NAME}: AssociationRule {RULE} is missing required parameter "Primary"'\
                    .format(NAME=self.name, RULE=rule_name)

                raise AttributeError(msg)

            if 'ReferenceTable' not in rule:
                msg = 'RecordEntry {NAME}: AssociationRule {RULE} is missing required parameter "ReferenceTable"' \
                    .format(NAME=self.name, RULE=rule_name)

                raise AttributeError(msg)

            if 'Title' not in rule:
                rule['Title'] = rule_name

            if 'AssociationType' in rule:
                assoc_type = rule['AssociationType']
                if assoc_type not in ('parent', 'child', 'reference'):
                    msg = 'RecordEntry {NAME}: unknown association type {TYPE} provided to association rule {RULE}' \
                        .format(NAME=self.name, TYPE=assoc_type, RULE=rule_name)

                    raise AttributeError(msg)

            self.association_rules[rule_name] = {'AssociationType': rule.get('AssociationType', 'reference'),
                                                 'Primary': rule.get('Primary'),
                                                 'ReferenceTable': rule.get('ReferenceTable'),
                                                 'HardLink': rule.get('HardLink', None)}

        # Import table layout configuration
        try:
            self.import_table = entry['ImportTable']
        except KeyError:
            msg = 'RecordEntry {NAME}: missing configuration parameter "ImportTable"'.format(NAME=self.name)
            logger.warning(msg)

            self.import_table = {}

        # Record layout configuration
        try:
            self.record_layout = entry['RecordLayout']
        except KeyError:
            mod_win2.popup_error('RecordsEntry {NAME}: configuration missing required parameter "RecordLayout"'
                                 .format(NAME=name))
            sys.exit(1)

    def load_records(self, id_list, id_field: str = 'RecordID'):
        """
        Load a record from the database using the record ID.

        Arguments:
            id_list (list): load records with these record IDs from the database.

            id_field (str): table field containing the record IDs [Default: RecordID].

        Returns:
            import_df (DataFrame): dataframe of imported records.
        """
        if isinstance(id_list, str):
            record_ids = [id_list]
        else:
            record_ids = id_list

        record_ids = sorted(list(set(record_ids)))  # prevents duplicate IDs
        logger.debug('loading records {IDS} of type "{TYPE}" from the database'.format(IDS=record_ids, TYPE=self.name))

        # Add configured import filters
        table_statement = mod_db.format_tables(self.import_rules)
        columns = mod_db.format_import_columns(self.import_rules)
        id_col = mod_db.get_import_column(self.import_rules, id_field)

        # Query existing database entries
        import_df = pd.DataFrame()
        for i in range(0, len(record_ids), 1000):  # split into sets of 1000 to prevent max parameter errors in SQL
            sub_ids = record_ids[i: i + 1000]
            filter_clause = '{COL} IN ({VALS})'.format(COL=id_col, VALS=','.join(['?' for _ in sub_ids]))
            filters = mod_db.format_import_filters(self.import_rules)
            filters.append((filter_clause, tuple(sub_ids)))

            if import_df.empty:
                import_df = user.read_db(*user.prepare_query_statement(table_statement, columns=columns,
                                                                       filter_rules=filters), prog_db=self.program_record)
            else:
                import_df = import_df.append(user.read_db(*user.prepare_query_statement(table_statement,
                                                                                        columns=columns,
                                                                                        filter_rules=filters),
                                                          prog_db=self.program_record), ignore_index=True)

        logger.debug('{NLOADED} records passed the query filters out of {NTOTAL} requested records'
                     .format(NLOADED=import_df.shape[0], NTOTAL=len(record_ids)))

        return import_df

    def import_records(self, params: list = None, import_rules: dict = None):
        """
        Import entry records from the database.

        Arguments:
            params (list): list of data parameters that will be used to filter the database when importing records.

            import_rules (dict): use custom import rules to import the records from the database.
        """
        params = [] if params is None else params

        import_rules = self.import_rules if not import_rules else import_rules

        # Add configured import filters
        filters = mod_db.format_import_filters(import_rules)
        table_statement = mod_db.format_tables(import_rules)
        columns = mod_db.format_import_columns(import_rules)

        # Add optional parameter-based filters
        for param in params:
            dbcol = mod_db.get_import_column(import_rules, param.name)
            if dbcol:
                param_filter = param.query_statement(dbcol)
                if param_filter is not None:
                    filters.append(param_filter)

        # Query existing database entries
        import_df = user.read_db(*user.prepare_query_statement(table_statement, columns=columns, filter_rules=filters),
                                 prog_db=self.program_record)

        return import_df

    def import_references(self, records, rule: str = None, include_deleted: bool = False):
        """
        Import a record's association.

        Arguments:
            records (list): list of record IDs to extract from the reference table.

            rule (str): name of the association rule to use to gather information about the references to extract
                [Default: import associations for all rules].

            include_deleted (bool): import reference entries that were set to deleted as well.
        """
        association_rules = self.association_rules

        if rule and rule in association_rules:
            import_rules = [rule]
        else:
            import_rules = list(association_rules)

        if isinstance(records, str):
            record_ids = [records]
        elif isinstance(records, pd.Series):
            record_ids = records.tolist()
        elif isinstance(records, pd.DataFrame):
            try:
                record_ids = records['RecordID'].tolist()
            except KeyError:
                msg = 'failed to import reference entries - the provided dataframe is missing required column "{COL}"' \
                    .format(COL='RecordID')
                logger.error('RecordEntry {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                raise ImportError(msg)
        else:
            record_ids = records

        # Remove duplicate IDs
        record_ids = list(set(record_ids))

        # Prepare the import data
        df = pd.DataFrame(columns=['RecordID', 'ReferenceID', 'ReferenceDate', 'RecordType', 'ReferenceType',
                                   'ReferenceNotes', 'ReferenceWarnings', 'IsChild', 'IsHardLink', 'IsApproved',
                                   'IsDeleted'])
        for rule_name in import_rules:
            try:
                rule = association_rules[rule_name]
            except KeyError:
                msg = 'association rule {RULE} not found in the set of association rules for the record entry' \
                    .format(RULE=rule_name)
                logger.exception('RecordEntry {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                raise ImportError(msg)

            is_primary = rule['Primary']
            reference_table = rule['ReferenceTable']

            if is_primary:  # input records are the primary record IDs
                columns = ['DocNo AS RecordID', 'RefNo AS ReferenceID', 'RefDate AS ReferenceDate', 'DocType AS RecordType',
                           'RefType AS ReferenceType', 'Notes AS ReferenceNotes', 'Warnings AS ReferenceWarnings',
                           'IsChild', 'IsHardLink', 'IsApproved']
                filter_str = 'DocNo IN ({VALS})'
            else:  # input records are the reference record ID
                columns = ['DocNo AS ReferenceID', 'RefNo AS RecordID', 'RefDate AS ReferenceDate',
                           'DocType AS ReferenceType', 'RefType AS RecordType', 'Notes AS ReferenceNotes',
                           'Warnings AS ReferenceWarnings', 'IsChild', 'IsHardLink', 'IsApproved']
                filter_str = 'RefNo IN ({VALS})'

            # Import reference entries related to record_id
            for i in range(0, len(record_ids), 1000):  # split into sets of 1000 to prevent max parameter errors in SQL
                sub_ids = record_ids[i: i + 1000]
                sub_vals = ','.join(['?' for _ in sub_ids])

                filters = [(filter_str.format(VALS=sub_vals), tuple(sub_ids))]
                if not include_deleted:
                    filters.append(('IsDeleted = ?', 0))

                import_df = user.read_db(*user.prepare_query_statement(reference_table, columns=columns,
                                                                       filter_rules=filters), prog_db=True)
                df = df.append(import_df, ignore_index=True)

        # Set column data types
        bool_columns = ['IsChild', 'IsHardLink', 'IsApproved', 'IsDeleted']
        df.loc[:, bool_columns] = df[bool_columns].fillna(False).astype(np.bool_, errors='ignore')

        return df

    def import_references_old(self, records, rule_name, include_deleted: bool = False):
        """
        Import a record's association.

        Arguments:
            records (list): list of record IDs to extract from the reference table.

            rule_name (str): name of the association rule to use to gather information about the references to extract.

            include_deleted (bool): import reference entries that were set to deleted as well.
        """
        association_rules = self.association_rules

        if isinstance(records, str):
            record_ids = [records]
        elif isinstance(records, pd.Series):
            record_ids = records.tolist()
        elif isinstance(records, pd.DataFrame):
            try:
                record_ids = records['RecordID'].tolist()
            except KeyError:
                msg = 'failed to import reference entries - the provided dataframe is missing required column "{COL}"'\
                    .format(COL='RecordID')
                logger.error('RecordEntry {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                raise ImportError(msg)
        else:
            record_ids = records

        # Remove duplicate IDs
        record_ids = list(set(record_ids))

        try:
            rule = association_rules[rule_name]
        except KeyError:
            msg = 'association rule {RULE} not found in the set of association rules for the record entry'\
                .format(RULE=rule_name)
            logger.exception('RecordEntry {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            raise ImportError(msg)

        is_primary = rule['Primary']
        reference_table = rule['ReferenceTable']

        if is_primary:  # input records are the primary record IDs
            columns = ['DocNo AS RecordID', 'RefNo AS ReferenceID', 'RefDate AS ReferenceDate', 'DocType AS RecordType',
                       'RefType AS ReferenceType', 'Notes AS ReferenceNotes', 'Warnings AS ReferenceWarnings',
                       'IsChild', 'IsHardLink', 'IsApproved']
            #filter_str = 'DocNo IN ({VALS}) AND IsDeleted = ?'
            filter_str = 'DocNo IN ({VALS})'
        else:  # input records are the reference record ID
            columns = ['DocNo AS ReferenceID', 'RefNo AS RecordID', 'RefDate AS ReferenceDate',
                       'DocType AS ReferenceType', 'RefType AS RecordType', 'Notes AS ReferenceNotes',
                       'Warnings AS ReferenceWarnings', 'IsChild', 'IsHardLink', 'IsApproved']
            #filter_str = 'RefNo IN ({VALS}) AND IsDeleted = ?'
            filter_str = 'RefNo IN ({VALS})'

        # Import reference entries related to record_id
        df = pd.DataFrame(columns=['RecordID', 'ReferenceID', 'ReferenceDate', 'RecordType', 'ReferenceType',
                                   'ReferenceNotes', 'ReferenceWarnings', 'IsChild', 'IsHardLink', 'IsApproved',
                                   'IsDeleted'])
        for i in range(0, len(record_ids), 1000):  # split into sets of 1000 to prevent max parameter errors in SQL
            sub_ids = record_ids[i: i + 1000]
            sub_vals = ','.join(['?' for _ in sub_ids])

            filters = [(filter_str.format(VALS=sub_vals), tuple(sub_ids))]
            if not include_deleted:
                filters.append(('IsDeleted = ?', 0))

            import_df = user.read_db(*user.prepare_query_statement(reference_table, columns=columns,
                                                                   filter_rules=filters), prog_db=True)
            df = df.append(import_df, ignore_index=True)

        # Set column data types
        bool_columns = ['IsChild', 'IsHardLink', 'IsApproved', 'IsDeleted']
        df.loc[:, bool_columns] = df[bool_columns].fillna(False).astype(np.bool_, errors='ignore')

        return df

    def load_unreferenced_records(self, rule_name):
        """
        Load entry records that do not have a record reference for the given association rule.
        """
        association_rules = self.association_rules
        import_rules = self.import_rules

        try:
            rule = association_rules[rule_name]
        except KeyError:
            msg = 'association rule {RULE} not found in the set of association rules for the record entry' \
                .format(RULE=rule_name)
            logger.exception('RecordEntry {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            raise ImportError(msg)

        is_primary = rule['Primary']
        reference_table = rule['ReferenceTable']

        if not is_primary:  # records are used as references, not primary records
            msg = 'unable to import unreferenced records - {TYPE} records must be the primary records in reference ' \
                  'table {TBL}'.format(TYPE=self.name, TBL=reference_table)
            logger.exception('RecordEntry {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            raise ImportError(msg)

        # Import reference entries related to record_id
        id_col = mod_db.get_import_column(import_rules, 'RecordID')
        columns = mod_db.format_import_columns(import_rules)
        filters = mod_db.format_import_filters(import_rules)
        filters_clause = '{TBL}.RefNo IS NULL'.format(TBL=reference_table)
        filters.append(filters_clause)
        import_rules[reference_table] = {'Columns': {'RefNo': 'RefNo'},
                                         'Join': ["LEFT JOIN", "{} = {}.DocNo".format(id_col, reference_table)]}
        table_statement = mod_db.format_tables(import_rules)
        import_df = user.read_db(*user.prepare_query_statement(table_statement, columns=columns, filter_rules=filters),
                                 prog_db=True)

        return import_df

    def confirm_saved(self, id_list, id_field: str = 'RecordID', table: str = None):
        """
        Check whether or not records have already been saved to the database.

        Arguments:
            id_list (list): check to see if these record IDs are found in the database or the given database table.

            id_field (str): table field containing the record IDs [Default: RecordID].

            table (str): search this database table for the record IDs.

        Returns:
            records_saved (list): list of corresponding booleans giving the status of the record ID in the database.
        """
        if isinstance(id_list, str):
            record_ids = [id_list]
        elif isinstance(id_list, pd.Series):
            record_ids = id_list.tolist()
        else:
            record_ids = id_list

        if not len(id_list) > 0:
            return []

        record_ids = sorted(list(set(record_ids)))  # prevents duplicate IDs
        logger.debug('verifying whether records {IDS} of type "{TYPE}" have been previously saved to the database'
                     .format(IDS=record_ids, TYPE=self.name))

        # Add configured import filters
        if table is None:
            prog_db = self.program_record
            table_statement = mod_db.format_tables(self.import_rules)
            id_col = mod_db.get_import_column(self.import_rules, id_field)
            if not id_col:
                id_col = id_field
        else:
            prog_db = True
            table_statement = table
            id_col = id_field

        # Query existing database entries
        import_df = pd.DataFrame()
        for i in range(0, len(record_ids), 1000):  # split into sets of 1000 to prevent max parameter errors in SQL
            sub_ids = record_ids[i: i + 1000]
            filter_clause = '{COL} IN ({VALS})'.format(COL=id_col, VALS=','.join(['?' for _ in sub_ids]))
            filters = (filter_clause, tuple(sub_ids))

            if import_df.empty:
                import_df = user.read_db(*user.prepare_query_statement(table_statement, columns=id_col,
                                                                       filter_rules=filters), prog_db=prog_db)
            else:
                import_df = import_df.append(user.read_db(*user.prepare_query_statement(table_statement,
                                                                                        columns=id_col,
                                                                                        filter_rules=filters),
                                                          prog_db=prog_db), ignore_index=True)

        try:
            import_ids = import_df.iloc[:, 0].values.tolist()
        except IndexError as e:
            msg = 'failed to verify whether records {IDS} of type "{TYPE}" have been previously saved to the ' \
                  'database - {ERR}'.format(IDS=record_ids, TYPE=self.name, ERR=e)
            logger.error(msg)
            raise

        records_saved = pd.Series(index=record_ids, dtype='bool')
        for record_id in record_ids:
            if record_id in import_ids:
                records_saved[record_id] = True
            else:
                records_saved[record_id] = False

        if isinstance(id_list, str):
            return records_saved[id_list]
        else:
            return records_saved

    def save_database_references(self, ref_data, rule_name, statements: dict = None):
        """
        Prepare to save database references.

        Arguments:
            ref_data (DataFrame): reference entries to save to the database table specified by the association rule.

            rule_name (str): name of the association rule that indicates which database table to save the reference
                entries to.

            statements (dict): optional dictionary of transactions statements to append to.

        Returns:
            statements (dict): dictionary of transactions statements.
        """
        if statements is None:
            statements = {}

        if isinstance(ref_data, pd.DataFrame):
            df = ref_data
        elif isinstance(ref_data, pd.Series):
            df = ref_data.to_frame().transpose()
        elif isinstance(ref_data, dict):
            df = pd.DataFrame(ref_data)
        else:
            raise ValueError('ref_data must be one of DataFrame, Series, or dictionary')

        association_rules = self.association_rules
        try:
            rule = association_rules[rule_name]
        except KeyError:
            msg = 'association rule {RULE} not found in the set of association rules for the record entry' \
                .format(RULE=rule_name)
            logger.exception('RecordEntry {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            raise ImportError(msg)

        reference_table = rule['ReferenceTable']
        is_primary = rule['Primary']
        if is_primary:  # input record is the primary record ID
            primary_col = 'RecordID'
            export_col_map = {'RecordID': 'DocNo', 'ReferenceID': 'RefNo', 'ReferenceDate': 'RefDate',
                              'RecordType': 'DocType', 'ReferenceType': 'RefType', 'ReferenceNotes': 'Notes',
                              'ReferenceWarnings': 'Warnings', 'IsApproved': 'IsApproved', 'IsChild': 'IsChild',
                              'IsHardLink': 'IsHardLink', 'IsDeleted': 'IsDeleted'}
        else:  # reference record is the primary record ID
            primary_col = 'ReferenceID'
            export_col_map = {'ReferenceID': 'DocNo', 'RecordID': 'RefNo', 'ReferenceDate': 'RefDate',
                              'ReferenceType': 'DocType', 'RecordType': 'RefType', 'ReferenceNotes': 'Notes',
                              'ReferenceWarnings': 'Warnings', 'IsApproved': 'IsApproved', 'IsChild': 'IsChild',
                              'IsHardLink': 'IsHardLink', 'IsDeleted': 'IsDeleted'}

        # Remove rows where the primary column is NULL
        df.drop(df[df[primary_col].isna()].index, inplace=True)
        if df.empty:
            logger.warning('RecordType {NAME}: no reference entries provided for saving'.format(NAME=self.name))
            return statements

        # Prepare separate update and insert statements depending on whether an individual reference entry exists
        export_df = df[[i for i in export_col_map if i in df.columns]].rename(columns=export_col_map)

        # Prepare the upsert statement
        export_columns = export_df.columns.tolist()
        export_values = [tuple(i) for i in export_df.values.tolist()]

        statements = user.prepare_upsert_statement(reference_table, export_columns, export_values, ['DocNo', 'RefNo'],
                                                   statements=statements)

        return statements

    def delete_database_references(self, ref_data, rule_name, statements: dict = None):
        """
        Prepare to delete database reference entries from the database.

        Arguments:
            ref_data (DataFrame): reference entries to delete from the database table specified by the association rule.

            rule_name (str): name of the association rule linking the relevant records.

            statements (dict): optional dictionary of transactions statements to append to.

        Returns:
            statements (dict): dictionary of transactions statements.
        """
        if statements is None:
            statements = {}

        if isinstance(ref_data, pd.DataFrame):
            df = ref_data
        elif isinstance(ref_data, pd.Series):
            df = ref_data.to_frame().transpose()
        elif isinstance(ref_data, dict):
            df = pd.DataFrame(ref_data)
        else:
            raise ValueError('ref_data must be one of DataFrame, Series, or dictionary')

        if df.empty:
            logger.warning('RecordEntry {NAME}: no reference entries provided for deleting'.format(NAME=self.name))
            return statements

        association_rules = self.association_rules
        try:
            rule = association_rules[rule_name]
        except KeyError:
            msg = 'association rule {RULE} not found in the set of association rules for the record entry' \
                .format(RULE=rule_name)
            logger.exception('RecordEntry {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            raise ImportError(msg)

        reference_table = rule['ReferenceTable']
        is_primary = rule['Primary']
        if is_primary:  # input record is the primary record ID
            export_col_map = {'RecordID': 'DocNo', 'ReferenceID': 'RefNo', 'IsDeleted': 'IsDeleted'}
        else:  # reference record is the primary record ID
            export_col_map = {'ReferenceID': 'DocNo', 'RecordID': 'RefNo', 'IsDeleted': 'IsDeleted'}

        # Prepare the export reference entries
        df = df[(~df['RecordID'].isna()) & (~df['ReferenceID'].isna())]
        export_df = df[[i for i in export_col_map if i in df.columns]].rename(columns=export_col_map)

        # Prepare the update statement
        export_columns = [export_col_map['IsDeleted']]
        export_values = [(1, ) for _ in range(export_df.shape[0])]

        filter_clause = '{COL} = ? AND {REFCOL} = ?'.format(COL=export_col_map['RecordID'],
                                                            REFCOL=export_col_map['ReferenceID'])
        filter_params = [(row[export_col_map['RecordID']], row[export_col_map['ReferenceID']]) for _, row in export_df.iterrows()]

        statements = user.prepare_update_statement(reference_table, export_columns, export_values, filter_clause,
                                                   filter_params, statements=statements)

        return statements

    def save_database_records(self, records, id_field: str = 'RecordID', statements: dict = None,
                              export_columns: bool = True, ref_ids: list = []):
        """
        Create insert and update database transaction statements for records.

        Arguments:
            records (DataFrame): record data that will be exported to the database.

            id_field (str): name of the column containing the record IDs.

            statements (dict): optional dictionary of database transaction statements to append to.

            export_columns (bool): use import column mapping to transform column names to database names before
                exporting [Default: True].

            ref_ids (list): list of references that have already been modified within the current save action.
                Required to prevent endless recursion.

        Returns:
            statements (dict): dictionary of transactions statements.
        """
        # pd.set_option('display.max_columns', None)
        export_rules = self.export_rules
        association_rules = self.association_rules

        if not statements:
            statements = {}

        save_time = datetime.datetime.now().strftime(settings.date_format)

        if isinstance(records, pd.DataFrame):
            df = records
        elif isinstance(records, pd.Series):
            df = records.to_frame().transpose()
        elif isinstance(records, dict):
            df = pd.DataFrame(records)
        else:
            raise ValueError('records argument must be one of DataFrame, Series, or dictionary')

        if df.empty:
            logger.warning('RecordType {NAME}: no records provided for saving'.format(NAME=self.name))
            return statements

        exists = self.confirm_saved(df[id_field].values.tolist(), id_field=id_field)
        existing_ids = exists[exists].index.tolist()
        new_ids = exists[~exists].index.tolist()

        # Prepare a separate database transaction statement for each database table containing the record's data
        columns = df.columns.tolist()
        for table in export_rules:
            table_entry = export_rules[table]

            if export_columns:
                export_col_map = table_entry['Columns']
            else:
                export_col_map = {i: i for i in table_entry['Columns'].values()}

            try:
                id_col = export_col_map[id_field]
            except KeyError:
                msg = 'RecordEntry {NAME}: missing ID column "{COL}" from record import columns {COLS}' \
                    .format(NAME=self.name, COL=id_field, COLS=list(export_col_map.keys()))
                logger.error(msg)

                raise KeyError(msg)

            # Prepare column value updates
            include_columns = [i for i in columns if i in export_col_map]
            export_df = df[include_columns]

            # Prepare separate update and insert statements depending on whether an individual record already exists

            # Extract all currently existing records from the table
            current_df = export_df[export_df[id_field].isin(existing_ids)]

            # Prepare update statements for the existing records
            if not current_df.empty:
                # Add edit details to records table
                current_df.loc[:, settings.editor_code] = user.uid
                current_df.loc[:, settings.edit_date] = save_time

                export_columns = current_df.rename(columns=export_col_map).columns.tolist()
                export_values = [tuple(i) for i in current_df.values.tolist()]

                record_ids = current_df[id_field]
                if not isinstance(record_ids, pd.Series):
                    record_ids = [record_ids]
                else:
                    record_ids = record_ids.values.tolist()
                filter_params = [(i,) for i in record_ids]
                filter_clause = '{COL} = ?'.format(COL=id_col)
                statements = user.prepare_update_statement(table, export_columns, export_values, filter_clause,
                                                           filter_params, statements=statements)

            # Extract all new records from the table
            new_df = export_df[export_df[id_field].isin(new_ids)]

            # Prepare insertion statements for the new records
            if not new_df.empty:
                # Add record creation details to records table
                try:
                    new_df[settings.creator_code].fillna(user.uid, inplace=True)
                    new_df[settings.creation_date].fillna(save_time, inplace=True)
                except KeyError:
                    new_df.loc[:, settings.creator_code] = user.uid
                    new_df.loc[:, settings.creation_date] = save_time

                export_columns = new_df.rename(columns=export_col_map).columns.tolist()
                export_values = [tuple(i) for i in new_df.values.tolist()]
                statements = user.prepare_insert_statement(table, export_columns, export_values, statements=statements)

        # If relevant, create or edit hard-linked reference records for new database records
        new_df = df[df[id_field].isin(new_ids)].rename(columns={id_field: 'RecordID'})
        exist_df = df[df[id_field].isin(existing_ids)].rename(columns={id_field: 'RecordID'})
        for association in association_rules:
            rule = association_rules[association]

            # Create or edit any hard-linked records
            link_rules = rule['HardLink']
            if link_rules is not None:
                record_type = self.name

                for ref_type in link_rules:
                    ref_entry = settings.records.fetch_rule(ref_type)
                    link_rule = link_rules[ref_type]

                    try:
                        condition = link_rule['Condition']
                    except KeyError:
                        condition = None
                    try:
                        colmap = link_rule['ColumnMap']
                    except KeyError:
                        msg = 'missing required HardLink parameter "ColumnMap"'
                        logger.error('RecordEntry {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                        raise KeyError(msg)

                    sub_cols = [i for i in colmap if i in df.columns]

                    # Edit existing linked-records

                    # Get hard-linked references of the existing records
                    current_ids = exist_df['RecordID'].tolist()
                    exist_ref_df = self.import_references(current_ids, rule=association)
                    assoc_record_ids = exist_ref_df['RecordID'].tolist()

                    # Update hard-linked record element values to match record element values
                    exist_ref_df = exist_ref_df[(exist_ref_df['IsHardLink']) & (~exist_ref_df['ReferenceID'].isin(ref_ids))]
                    if not exist_ref_df.empty:
                        # Merge the relevant columns of the records dataframe with the reference dataframe
                        merged_df = pd.merge(exist_df[['RecordID'] + sub_cols], exist_ref_df, on='RecordID')

                        # Subset the dataframe on the mapped columns and rename the columns
                        merged_df = merged_df[['ReferenceID'] + sub_cols].rename(columns=colmap)
                        merged_df.rename(columns={'ReferenceID': 'RecordID'}, inplace=True)

                        # Prepare the update statements for the hard-linked records
                        statements = ref_entry.save_database_records(merged_df, statements=statements, ref_ids=current_ids)

                    if not rule['Primary']:  # restricting to primary record types prevents endless recursion
                        continue

                    # Allow the user to delete dependent records when dependency conditions are no longer met
                    #if condition and not exist_df.empty:
                    #    delete_ids = exist_df.loc[~mod_dm.evaluate_condition(exist_df, condition), 'RecordID']
                    #    delete_ref_df = exist_ref_df[exist_ref_df['RecordID'].isin(delete_ids.tolist())]
                    #    to_delete = []
                    #    for index, row in delete_ref_df.iterrows():
                    #        delete_id = row['ReferenceID']
                    #        parent_id = row['RecordID']
                    #        msg = ''.format(DOCTYPE=self.menu_title, PID=parent_id, ID=delete_id, REFTYPE=ref_entry.menu_title)
                    #        confirm = mod_win2.popup_confirm(msg)
                    #        if confirm == 'OK':
                    #            to_delete.append(delete_id)

                    #    statements = ref_entry.delete_database_records(to_delete, statements=statements)

                    # Create new hard-linked records
                    create_df = new_df.copy()
                    if condition and not create_df.empty:
                        create_df = create_df[mod_dm.evaluate_condition(create_df, condition)]

                    # Add existing records w/o hard-links to the "add df" so that new hard-linked records can be created
                    missing_df = exist_df[~exist_df['RecordID'].isin(assoc_record_ids)]
                    if condition and not missing_df.empty:
                        missing_df = missing_df[mod_dm.evaluate_condition(missing_df, condition)]

                    for index, row in missing_df.iterrows():
                        msg = 'Existing {DOCTYPE} record {ID} does not currently have an associated {REFTYPE} record. '\
                              'Would you like to create one now?'.format(DOCTYPE=self.menu_title, ID=row['RecordID'],
                                                                         REFTYPE=ref_entry.menu_title)
                        confirm = mod_win2.popup_confirm(msg)
                        if confirm == 'OK':
                            create_df = create_df.append(row, ignore_index=True)

                    if create_df.empty:
                        continue

                    # Create new record IDs for the hard-linked records
                    primary_ids = create_df['RecordID'].tolist()
                    try:
                        ref_dates = pd.to_datetime(create_df['RecordDate'], errors='coerce')
                    except KeyError:
                        msg = 'failed to create IDs for the new records - failed to create associated "{TYPE}" ' \
                              'records'.format(TYPE=record_type, RTYPE=ref_type)
                        logger.error('RecordEntry {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                        raise KeyError(msg)
                    else:
                        ref_dates = ref_dates.tolist()

                    ref_ids = ref_entry.create_record_ids(ref_dates, offset=settings.get_date_offset())

                    # Subset the dataframe on the mapped columns and rename the columns
                    ref_df = create_df[sub_cols].rename(columns=colmap)
                    ref_df['RecordID'] = ref_ids
                    ref_df['RecordDate'] = ref_dates

                    # Create the hard-linked records
                    statements = ref_entry.save_database_records(ref_df, statements=statements)

                    # Create the record references
                    ref_data = pd.DataFrame({'RecordID': primary_ids, 'ReferenceID': ref_ids,
                                             'ReferenceDate': datetime.datetime.now(), 'RecordType': record_type,
                                             'ReferenceType': ref_type, 'IsApproved': True, 'IsChild': False,
                                             'IsHardLink': True, 'IsDeleted': False})
                    statements = self.save_database_references(ref_data, association, statements=statements)

        return statements

    def delete_database_records(self, records, statements: dict = None, id_field: str = 'RecordID',
                                ref_ids: list = None):
        """
        Delete records from the database.

        Arguments:
            records (list): delete records with these record IDs from the database.

            statements (dict): optional dictionary of database transaction statements to add to.

            id_field (str): name of the column containing the record IDs [Default: RecordID].

            ref_ids (list): list of references that have already been modified within the current delete action.
                Required to prevent endless recursion.

        Returns:
            statements (dict): dictionary of transaction statements.
        """
        # pd.set_option('display.max_columns', None)

        if not statements:
            statements = {}

        if ref_ids is None:
            ref_ids = []

        if isinstance(records, str):
            records = [records]
        elif isinstance(records, pd.Series):
            records = records.tolist()

        if not len(records) > 0:  # empty list provided
            return statements

        records = list(set(records))  # duplicate filtering

        # Check existence of the records in the database
        exists = self.confirm_saved(records, id_field=id_field)

        record_ids = []
        for record_id in records:
            record_exists = exists[record_id]
            if record_exists:  # only attempt to delete records that already exist in the database
                record_ids.append(record_id)

        if len(record_ids) < 1:  # no currently existing records to delete
            return statements

        # Set existing records as deleted in the database
        export_rules = self.export_rules
        for export_table in export_rules:
            table_entry = export_rules[export_table]

            export_col_map = table_entry['Columns']
            if 'Deleted' not in export_col_map:
                continue

            id_col = export_col_map[id_field]
            delete_col = export_col_map['Deleted']

            export_columns = [delete_col, settings.editor_code, settings.edit_date]
            export_values = [(1, user.uid, datetime.datetime.now().strftime(settings.date_format)) for _ in record_ids]

            filter_params = [(i,) for i in record_ids]
            filter_clause = '{COL} = ?'.format(COL=id_col)

            # Remove records from the export table
            statements = user.prepare_update_statement(export_table, export_columns, export_values, filter_clause,
                                                       filter_params, statements=statements)

        # Remove record associations and potentially delete associated records if associated records are child records
        # or hard-linked to the deleted records
        association_rules = self.association_rules
        for association in association_rules:
            rule = association_rules[association]
            assoc_type = rule['AssociationType']

            # Import reference entries to be deleted
            import_df = self.import_references(record_ids, rule=association)

            # Delete the reference entries and remove already used references from the list - this is necessary for
            # hard-linked records to avoid endless looping
            import_df['IsDeleted'] = True
            export_df = import_df.drop(import_df[import_df['ReferenceID'].isin(ref_ids)].index)
            if export_df.empty:
                continue
            statements = self.save_database_references(export_df, association, statements=statements)

            # Subset reference entries to include those that are child records or hard-linked
            if assoc_type == 'parent':  # referenced records are child records and should be deleted with parent
                condition = export_df['IsChild'].astype(bool)
            elif assoc_type == 'reference':  # deleting hard-linked records should also delete reference records
                condition = export_df['IsHardLink'].astype(bool)
            else:  # record is a child record - deleted child records should have no affect on the parent records
                continue

            linked_df = export_df[condition]
            if linked_df.empty:
                continue

            # Update the list of used reference IDs
            ignore_ids = list(set(ref_ids + record_ids))

            # Remove hard-linked and child records. Do not include reference entries that have already been deleted.
            record_types = import_df['ReferenceType'].unique()
            for record_type in record_types:
                record_entry = settings.records.fetch_rule(record_type)
                if record_entry is None:
                    msg = 'unable to delete dependant records of record type "{TYPE}"' \
                        .format(TYPE=record_type)
                    logger.error('RecordEntry {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                    raise AttributeError(msg)

                # Subset imported reference entries by record class of the reference record
                sub_df = linked_df[linked_df['ReferenceType'] == record_type]

                # Prepare deletion statements for reference records
                ref_ids = sub_df['ReferenceID'].values.tolist()
                statements = record_entry.delete_database_records(ref_ids, statements=statements, ref_ids=ignore_ids)

        return statements

    def _search_saved_ids(self, record_dates, id_field: str = 'RecordID'):
        """
        Get a list of saved record IDs for records with record date within the provided range of dates.
        """
        # Prepare query parameters
        table_statement = mod_db.format_tables(self.import_rules)
        id_col = mod_db.get_import_column(self.import_rules, id_field)

        # Prepare the date range
        sorted_dates = sorted(record_dates)
        try:
            first_date = sorted_dates[0]
            last_date = sorted_dates[-1]
        except IndexError:
            logger.error('failed to import saved record IDs - no dates provided to the method')
            raise

        first_day = first_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_day = datetime.datetime(last_date.year + last_date.month // 12, last_date.month % 12 + 1, 1) - \
                   datetime.timedelta(1)

        # Connect to database
        params = (first_day, last_day)
        filters = ('{DATE} BETWEEN ? AND ?'.format(DATE=settings.date_field), params)
        import_rows = user.read_db(*user.prepare_query_statement(table_statement, columns=id_col, filter_rules=filters,
                                                                 order=id_col), prog_db=self.program_record)

        try:
            id_list = import_rows.iloc[:, 0]
        except IndexError:
            logger.info('no existing record IDs found')
            record_ids = []
        except Exception as e:
            logger.error('failed to import saved record IDs - {ERR}'.format(ERR=e))
            raise
        else:
            record_ids = id_list.values.tolist()

        return record_ids

    def create_record_ids(self, date_list, offset: int = 0):
        """
        Create a new set of record IDs.

        Arguments:
            date_list (list): create IDs from these dates.

            offset (int): apply an offset to the date list that will be used within the new record IDs by this amount
                [Default: do not apply a date offset].

        Returns:
            record_ids (list): list of new, unique record IDs.
        """
        relativedelta = dateutil.relativedelta.relativedelta
        is_datetime_dtype = pd.api.types.is_datetime64_any_dtype
        strptime = datetime.datetime.strptime

        record_type = self.name
        id_code = self.id_code

        if isinstance(date_list, str) or is_datetime_dtype(type(date_list)) or isinstance(date_list, datetime.datetime):
            record_dates = [date_list]
            single_value = True
        elif isinstance(date_list, list) or isinstance(date_list, tuple):
            if len(date_list) < 1:
                return []

            record_dates = date_list
            single_value = False
        else:
            logger.error('failed to create IDs for the record entries of type "{TYPE}" - record_dates must be '
                         'formatted as a list, string, or datetime object not {OTYPE}'
                         .format(TYPE=record_type, OTYPE=type(date_list)))
            return None

        logger.info('creating {N} new record IDs for records of type "{TYPE}"'
                    .format(N=len(record_dates), TYPE=record_type))

        # Get list of unsaved record IDs of the same record type
        unsaved_ids = self.get_unsaved_ids(internal_only=False)
        if unsaved_ids is None:
            logger.error('failed to create IDs for the record entries of type "{TYPE}" - unable to obtain a list of '
                         'unsaved record IDs'.format(TYPE=record_type))
            return None

        # Get list of saved record IDs of the same record type within the range of provided dates
        try:
            saved_ids = self._search_saved_ids(record_dates)
        except Exception as e:
            logger.exception('failed to create IDs for the record entries of type {TYPE} - {ERR}'
                             .format(TYPE=record_type, ERR=e))
            return None

        # Format the date component of the new ID
        record_ids = []
        for record_date in record_dates:
            try:
                id_date = (record_date + relativedelta(years=+offset)).strftime(
                    settings.format_date_str(date_str='YYMM'))
            except Exception as e:
                logger.debug(e)
                id_date = (strptime(record_date.strftime('%Y-%m-%d %H:%M:%S'), '%Y-%m-%d %H:%M:%S')
                           + relativedelta(years=+offset)).strftime(settings.format_date_str(date_str='YYMM'))

            logger.debug('RecordEntry {NAME}: new ID has date component {COMP}'.format(NAME=record_type, COMP=id_date))

            # Search list of unsaved IDs occurring within the current date cycle
            logger.debug('RecordEntry {NAME}: searching for unsaved record IDs with date component {DATE}'
                         .format(NAME=record_type, DATE=id_date))
            prev_ids = []
            for unsaved_id in unsaved_ids:
                prev_date = self._id_date_component(unsaved_id)
                if prev_date == id_date:
                    prev_ids.append(unsaved_id)

            logger.debug('RecordEntry {NAME}: found {NUM} unsaved records with date component {DATE}'
                         .format(NAME=record_type, NUM=len(prev_ids), DATE=id_date))

            # Search list of saved IDs occurring within the current date cycle
            logger.debug('RecordEntry {NAME}: searching for database record IDs with date component {DATE}'
                         .format(NAME=record_type, DATE=id_date))

            for saved_id in saved_ids:
                prev_date = self._id_date_component(saved_id)
                if prev_date == id_date:
                    prev_ids.append(saved_id)

            # Get the number of the last ID used in the current date cycle
            logger.debug('RecordEntry {NAME}: found {NUM} records with date component {DATE}'
                         .format(NAME=self.name, NUM=len(prev_ids), DATE=id_date))

            if len(prev_ids) > 0:
                prev_ids.sort()
                last_id = prev_ids[-1]
            else:
                last_id = None

            # Create the new ID
            if last_id:
                logger.debug('RecordEntry {NAME}: last ID encountered is {ID}'.format(NAME=record_type, ID=last_id))
                try:
                    last_num = int(last_id.split('-')[-1])
                except ValueError:
                    msg = 'RecordEntry {NAME}: incorrect formatting for previous ID {ID}' \
                        .format(NAME=record_type, ID=last_id)
                    logger.error(msg)
                    record_ids.append(None)
                    continue
            else:
                logger.debug('RecordEntry {NAME}: no previous IDs found for date {DATE} - starting new iteration at 1'
                             .format(NAME=record_type, DATE=id_date))
                last_num = 0

            record_id = '{CODE}{DATE}-{NUM}'.format(CODE=id_code, DATE=id_date, NUM=str(last_num + 1).zfill(4))

            logger.info('RecordEntry {NAME}: new record ID is {ID}'.format(NAME=record_type, ID=record_id))
            record_ids.append(record_id)
            unsaved_ids.append(record_id)

        failed_rows = [i + 1 for i, j in enumerate(record_ids) if not j]
        if len(failed_rows) > 0:
            msg = 'failed to create record IDs for table entries at rows {ROW}'.format(ROW=failed_rows)
            logger.error(msg)

            return None

        success = self.add_unsaved_ids(record_ids)
        if not success:
            logger.error('failed to create IDs for the record entries of type "{TYPE}" - unable to add record IDs to '
                         'the list unsaved record IDs'.format(TYPE=record_type))
            return None

        if single_value:
            return record_ids[0]
        else:
            return record_ids

    def _id_date_component(self, record_id):
        """
        Get the date component of a record ID.
        """
        id_code = self.id_code
        code_len = len(id_code)
        try:
            id_name, id_num = record_id.split('-')
        except ValueError:
            raise AttributeError('no date component found for {TYPE} record ID {ID}'
                                 .format(TYPE=self.name, ID=record_id))

        return id_name[code_len:]

    def remove_unsaved_ids(self, record_ids: list = None, internal_only: bool = True):
        """
        Remove a record ID from the database of unsaved IDs associated with the record type.

        Arguments:
            record_ids (list): optional list of record IDs to remove from the set of unsaved record IDs with ID code
                corresponding to the ID code configured for the record entry.

            internal_only (bool): only remove recordIDs from the unsaved record IDs if they were created within the
                program instance.

        Returns:
            success (bool): removal of unsaved record IDs was successful.
        """
        unsaved_ids = self.get_unsaved_ids(internal_only=internal_only)

        if isinstance(record_ids, str):
            remove_ids = [record_ids] if record_ids in unsaved_ids else []
        elif isinstance(record_ids, list):
            remove_ids = [i for i in record_ids if i in unsaved_ids]
        else:
            remove_ids = unsaved_ids

        if not len(record_ids) > 0:
            logger.debug('RecordEntry {NAME}: no unsaved record IDs to remove'.format(NAME=self.name))
            return True

        logger.debug('RecordEntry {NAME}: attempting to remove IDs {ID} from the list of unsaved record IDs'
                     .format(NAME=self.name, ID=remove_ids))

        value = {'ids': remove_ids, 'id_code': self.id_code}
        content = {'action': 'remove_ids', 'value': value}
        request = {'content': content, 'encoding': "utf-8"}
        response = server_conn.process_request(request)

        success = response['success']
        if success is False:
            msg = 'RecordEntry {NAME}: failed to remove IDs {ID} from the list of unsaved record IDs of type ' \
                  '{TYPE} - {ERR}'.format(NAME=self.name, ID=remove_ids, TYPE=self.name, ERR=response['value'])
            logger.error(msg)
        else:
            logger.debug('RecordEntry {NAME}: successfully removed {ID} from the list of unsaved record IDs '
                         'associated with the record entry'.format(NAME=self.name, ID=remove_ids))

        return success

    def get_unsaved_ids(self, internal_only: bool = False):
        """
        Retrieve a list of unsaved record IDs from the database of unsaved record IDs associated with the record type.

        Arguments:
            internal_only (bool): only retrieve unsaved record IDs that they were created within the current program
                instance.

        Returns:
            unsaved_ids (list): list of unsaved record IDs.
        """
        if internal_only is True:
            instance = settings.instance_id
            logger.debug('RecordEntry {NAME}: attempting to obtain an instance-specific list of unsaved record IDs '
                         'associated with the record entry'.format(NAME=self.name))
        else:
            instance = None
            logger.debug('RecordEntry {NAME}: attempting to obtain list of unsaved record IDs associated with the '
                         'record entry'.format(NAME=self.name))

        value = {'instance': instance, 'id_code': self.id_code}
        content = {'action': 'request_ids', 'value': value}
        request = {'content': content, 'encoding': "utf-8"}
        response = server_conn.process_request(request)

        if response['success'] is False:
            msg = 'failed to obtain list of unsaved record IDs of type {TYPE} from the server - {ERR}' \
                .format(TYPE=self.name, ERR=response['value'])
            logger.error(msg)

            return []
        else:
            logger.debug('RecordEntry {NAME}: successfully obtained a list of unsaved record IDs associated with the '
                         'record entry'.format(NAME=self.name))

        unsaved_ids = response['value']

        return unsaved_ids

    def add_unsaved_ids(self, record_ids):
        """
        Add a record ID to the list of unsaved record IDs associated with the record type.

        Arguments:
            record_ids (list): list of record IDs to add to the set of unsaved record IDs with ID code corresponding to
                the ID code of the record entry.

        Returns:
            success (bool): addition of records to the set of unsaved record IDs was successful.
        """
        logger.debug('RecordEntry {NAME}: attempting to add record IDs {ID} to the list of unsaved record IDs '
                     'associated with the record entry'.format(NAME=self.name, ID=record_ids))

        if isinstance(record_ids, str):
            id_set = [(record_ids, settings.instance_id)]
        else:
            id_set = [(i, settings.instance_id) for i in record_ids]

        value = {'ids': id_set, 'id_code': self.id_code}
        content = {'action': 'add_ids', 'value': value}
        request = {'content': content, 'encoding': "utf-8"}
        response = server_conn.process_request(request)

        success = response['success']
        if success is False:
            msg = 'failed to add {ID} to the list of unsaved record IDs of type {TYPE} on the server - {ERR}' \
                .format(NAME=self.name, ID=record_ids, TYPE=self.name, ERR=response['value'])
            logger.error(msg)
        else:
            logger.debug('RecordEntry {NAME}: successfully added record IDs {ID} to the list of unsaved record IDs '
                         'associated with the record entry'.format(NAME=self.name, ID=record_ids))

        return success


class DatabaseRecord:
    """
    Generic database record account.

    Attributes:
        name (str): name of the parent record entry.

        id (int): record element number.

        elements (list): list of GUI element keys.

        title (str): record display title.

        permissions (dict): dictionary mapping permission rules to permission groups

        modules (list): list of record elements comprising the data component of the record.

        report (dict): report definition
    """

    def __init__(self, name, entry, level: int = 0):
        """
        Arguments:
            name (str): name of the parent record entry (record type).

            entry (class): configuration entry for the record layout.

            level (int): depth at which record was opened [Default: 0].
        """
        # Reserved fields
        self.id_field = 'RecordID'
        self.date_field = 'RecordDate'
        self.delete_field = 'Deleted'

        # Record properties
        self.new = False
        self.level = level

        self.name = name

        self.id = randint(0, 1000000000)
        self.elements = ['-{NAME}_{ID}_{ELEM}-'.format(NAME=self.name, ID=self.id, ELEM=i) for i in
                         ('ReferencesButton', 'ReferencesFrame', 'ComponentsButton', 'ComponentsFrame', 'DetailsButton',
                          'DetailsFrame', 'DetailsTab', 'DetailsCol', 'MetaTab', 'MetaCol', 'TG', 'Header', 'Record')]

        try:
            permissions = entry['Permissions']
        except KeyError:
            self.permissions = {'edit': None, 'delete': None, 'report': None}
        else:
            self.permissions = {'edit': permissions.get('Edit', None),
                                'delete': permissions.get('Delete', None),
                                'report': permissions.get('Report', None),
                                }

        try:
            self.title = entry['Title']
        except KeyError:
            self.title = self.name

        # Record header
        try:
            headers = entry['Header']
        except KeyError:
            headers = {}

        try:
            id_entry = headers[self.id_field]
        except KeyError:
            id_entry = {'ElementType': 'text', 'DataType': 'varchar', 'Description': 'Record ID'}
        else:
            id_entry['Modifiers'] = {}
            id_entry['ElementType'] = 'text'
            id_entry['DataType'] = 'varchar'
        try:
            self._record_id = mod_elem.MetaVariable(self.id_field, id_entry)
        except Exception as e:
            logger.error('RecordType {NAME}: {MSG}'.format(NAME=self.name, MSG=e))
            raise AttributeError(e)

        try:
            date_entry = headers[self.date_field]
        except KeyError:
            date_entry = {'ElementType': 'text', 'DataType': 'date', 'Description': 'Record Date'}
        else:
            date_entry['Modifiers'] = {}
            date_entry['ElementType'] = 'text'
            date_entry['DataType'] = 'date'
        try:
            self._record_date = mod_elem.MetaVariable(self.date_field, date_entry)
        except Exception as e:
            logger.error('RecordType {NAME}: {MSG}'.format(NAME=self.name, MSG=e))
            raise AttributeError(e)

        # Record metadata elements
        self.metadata = []
        try:
            metadata = entry['Metadata']
        except KeyError:
            metadata = []
        for param_name in metadata:
            param_entry = metadata[param_name]
            try:
                param = mod_elem.MetaVariable(param_name, param_entry, parent=self.name)
            except Exception as e:
                logger.error('RecordType {NAME}: {MSG}'.format(NAME=self.name, MSG=e))

                raise AttributeError(e)

            self.metadata.append(param)

        # Record data components
        self.sections = {}
        self.modules = []
        try:
            sections = entry['Sections']
        except KeyError:
            msg = 'missing configuration parameter "Sections"'
            logger.error('RecordEntry {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
        else:
            for i, section in enumerate(sections):
                section_entry = sections[section]
                self.elements.extend(['-{NAME}_{ID}_{ELEM}-'.format(NAME=self.name, ID=self.id, ELEM=i) for i in
                                      ['SectionBttn{}'.format(i), 'SectionFrame{}'.format(i)]])

                self.sections[section] = {'Title': section_entry.get('Title', section),
                                          'Elements': []}

                try:
                    section_elements = section_entry['Elements']
                except KeyError:
                    raise AttributeError('Section {} is missing required parameter "Elements"'.format(section))
                for element_name in section_elements:
                    self.sections[section]['Elements'].append(element_name)
                    elem_entry = section_elements[element_name]
                    try:
                        etype = elem_entry['ElementType']
                    except KeyError:
                        raise AttributeError('"Details" element {NAME} is missing the required field "ElementType"'
                                             .format(NAME=element_name))

                    # Set the object type of the record element.
                    if etype in ('data_table', 'table'):
                        element_class = mod_elem.DataTable
                    elif etype in ('component_table', 'components'):
                        element_class = mod_elem.ComponentTable
                    #elif etype in ('refbox', 'reference'):
                    #    element_class = mod_elem.ReferenceBox
                    elif etype in ('data_list', 'list'):
                        element_class = mod_elem.DataList
                    elif etype in ('reference_list', 'reference'):
                        element_class = mod_elem.ReferenceList
                    elif etype in ('dependent_variable', 'dependent'):
                        element_class = mod_elem.DependentVariable
                    elif etype in ('text_variable', 'text'):
                        element_class = mod_elem.RecordVariable
                    elif etype in ('input_variable', 'date_variable', 'input', 'date'):
                        element_class = mod_elem.RecordVariableInput
                    elif etype in ('dropdown_variable', 'combo_variable', 'combo', 'dropdown'):
                        element_class = mod_elem.RecordVariableCombo
                    elif etype in ('multiline_variable', 'multiline', 'multi'):
                        element_class = mod_elem.RecordVariableMultiline
                    else:
                        raise AttributeError('unknown element type {ETYPE} provided to element {ELEM}'
                                             .format(ETYPE=etype, ELEM=element_name))

                    # Initialize the record element
                    try:
                        elem_obj = element_class(element_name, elem_entry, parent=self.name)
                    except Exception as e:
                        raise AttributeError('failed to initialize {NAME} element {ELEM} - {ERR}'
                                             .format(NAME=self.name, ELEM=element_name, ERR=e))

                    # Add the element to the set of record components
                    self.modules.append(elem_obj)

        # Record report layout definition
        try:
            report = entry['Report']
        except KeyError:
            self.report = None
        else:
            if 'Info' not in report:
                report['Info'] = []
            if 'Subsections' not in report:
                report['Subsections'] = {}

            self.report = report

        self._minimum_height = 0
        self._padding = (0, 0)

    def key_lookup(self, component):
        """
        Lookup a component's GUI element key using the component's name.
        """
        element_names = [i[1:-1].split('_')[-1] for i in self.elements]
        if component in element_names:
            key_index = element_names.index(component)
            key = self.elements[key_index]
        else:
            raise KeyError('component {COMP} not found in list of record {NAME} components'
                           .format(COMP=component, NAME=self.name))

        return key

    def record_id(self):
        """
        Convenience method for returning the record ID of the record object.
        """
        return self._record_id.data()

    def record_date(self):
        """
        Convenience method for returning the record date of the record object.
        """
        return self._record_date.data()

    def initialize(self, data, new: bool = False, as_new: bool = False, references: dict = None):
        """
        Initialize record attributes.

        Arguments:
            data (dict): dictionary, series, or dataframe containing the record data used to populate the data fields.

            new (bool): record is newly created [default: False]. New records allow editing of all data
                element fields, even those normally disabled.

            as_new (bool): set record metadata as if the record is newly created [Default: False].

            references (dict): optional reference imports by association rule. If provided, will not attempt to import
                references for the given association rule but will use the reference entries provided instead.
        """
        # pd.set_option('display.max_columns', None)
        meta_params = self.metadata
        record_elements = self.modules

        if not references:
            references = {}

        self.new = new
        record_entry = settings.records.fetch_rule(self.name)

        if isinstance(data, pd.Series):
            record_data = data.to_dict()
        elif isinstance(data, dict):
            record_data = data
        elif isinstance(data, pd.DataFrame):
            if data.shape[0] > 1:
                raise ImportError('more than one record provided to record of type "{TYPE}"'.format(TYPE=self.name))
            elif data.shape[0] < 1:
                raise ImportError('empty dataframe provided to record of type "{TYPE}"'.format(TYPE=self.name))
            else:
                record_data = data.iloc[0]
        else:
            raise AttributeError('unknown object type provided to record class "{TYPE}"'.format(TYPE=self.name))

        logger.info('RecordType {NAME}: initializing record'.format(NAME=self.name))
        logger.debug('RecordType {NAME}: {DATA}'.format(NAME=self.name, DATA=record_data))

        # Set header values from required columns
        try:
            self._record_id.format_value(record_data)
        except KeyError:
            raise ImportError('input record data is missing required column "{}"'.format(self.id_field))
        try:
            self._record_date.format_value(record_data)
        except KeyError:
            raise ImportError('input record data is missing required column "{}"'.format(self.date_field))

        if new or as_new:
            record_data[settings.creator_code] = user.uid
            record_data[settings.creation_date] = datetime.datetime.now()

        # Set metadata element values
        for meta_param in meta_params:
            param_name = meta_param.name

            try:
                meta_param.format_value(record_data)
            except KeyError:
                logger.warning('RecordType {NAME}: input data is missing a value for metadata field "{COL}"'
                               .format(NAME=self.name, COL=param_name))

        # Populate the record elements with data
        record_id = self.record_id()
        if not record_id:
            raise ImportError('failed to initialize the record - no record ID found in the data provided')

        logger.info('RecordType {NAME}: initialized record has ID {ID}'.format(NAME=self.name, ID=record_id))

        for record_element in record_elements:
            element_name = record_element.name
            etype = record_element.etype

            if etype in ('table', 'list'):  # data table or data list
                element_fields = record_element.columns
                element_data = pd.Series(index=element_fields)
                for element_field in element_fields:
                    try:
                        element_data[element_field] = record_data[element_field]
                    except KeyError:
                        continue

                record_element.append(element_data)

            elif etype == 'component':  # component table
                assoc_rule = record_element.association_rule
                ref_entry = settings.records.fetch_rule(record_element.record_type)

                logger.debug('RecordType {NAME}: initializing component table "{PARAM}" with association "{TYPE}"'
                             .format(NAME=self.name, PARAM=element_name, TYPE=assoc_rule))

                # Load the reference entries defined by the given association rule
                if assoc_rule in references:  # use provided reference entries instead of importing from reference table
                    assoc_refs = references[assoc_rule]
                    ref_data = assoc_refs[(assoc_refs['RecordID'] == record_id) & (~assoc_refs['IsDeleted'])]
                else:
                    ref_data = record_entry.import_references(record_id, rule=assoc_rule)

                if ref_data.empty:
                    logger.debug('RecordType {NAME}: record {ID} has no current "{TYPE}" associations'
                                 .format(NAME=self.name, ID=record_id, TYPE=assoc_rule))
                    continue

                import_ids = ref_data['ReferenceID']

                # Load the component records
                import_df = ref_entry.load_records(import_ids)
                import_df = import_df[[i for i in import_df.columns if i in record_element.columns]]
                record_element.append(import_df)

            elif etype == 'reference':  # reference list
                assoc_rule = record_element.association_rule

                logger.debug('RecordType {NAME}: initializing reference list "{PARAM}" with association "{TYPE}"'
                             .format(NAME=self.name, PARAM=element_name, TYPE=assoc_rule))

                # Load the reference entries defined by the given association rule
                if assoc_rule in references:  # use provided reference entries instead of importing from reference table
                    assoc_refs = references[assoc_rule]
                    ref_data = assoc_refs[(assoc_refs['RecordID'] == record_id) & (~assoc_refs['IsDeleted'])]
                else:
                    ref_data = record_entry.import_references(record_id, rule=assoc_rule)

                if ref_data.empty:
                    logger.debug('RecordType {NAME}: record {ID} has no current "{TYPE}" associations'
                                 .format(NAME=self.name, ID=record_id, TYPE=assoc_rule))
                    continue

                record_element.append(ref_data, new=False)

            #elif etype == 'refbox':  # reference box
            #    assoc_rule = record_element.association_rule

            #    if assoc_rule in references:  # use provided reference entries instead of importing from reference table
            #        assoc_refs = references[assoc_rule]
            #        ref_data = assoc_refs[(assoc_refs['RecordID'] == record_id) & (~assoc_refs['IsDeleted'])]
            #    else:
            #        ref_data = record_entry.import_references(record_id, assoc_rule)

            #    if ref_data.empty:
            #        logger.debug('RecordType {NAME}: record {ID} has no {TYPE} associations'
            #                     .format(NAME=self.name, ID=record_id, TYPE=assoc_rule))
            #        continue

            #    elif ref_data.shape[0] > 1:
            #        logger.warning('RecordType {NAME}: more than one {TYPE} reference found for record {ID}'
            #                       .format(NAME=self.name, TYPE=assoc_rule, ID=self.record_id))

            #    logger.debug('RecordType {NAME}: loading reference information for reference box {REF}'
            #                 .format(NAME=self.name, REF=element_name))
            #    record_element.referenced = record_element.import_reference(ref_data)
                #record_element.append(ref_data)
            #    if record_element.referenced:
            #        logger.info('RecordType {NAME}: successfully loaded reference information for reference box {REF}'
            #                    .format(NAME=self.name, REF=element_name))
            #    else:
            #        logger.warning('RecordType {NAME}: failed to load reference information for reference box {REF}'
            #                       .format(NAME=self.name, REF=element_name))

            else:  # record variable element (dependent or record variables)
                try:
                    value = record_data[element_name]
                except KeyError:
                    logger.warning('RecordType {NAME}: input data is missing a value for data element "{PARAM}"'
                                   .format(NAME=self.name, PARAM=element_name))
                else:
                    if not pd.isna(value):
                        logger.debug('RecordType {NAME}: initializing data element "{PARAM}" with value "{VAL}"'
                                     .format(NAME=self.name, PARAM=element_name, VAL=value))
                        record_element.update_value(value)
                    else:
                        logger.debug('RecordType {NAME}: no value set for parameter "{PARAM}"'
                                     .format(NAME=self.name, PARAM=element_name))

    def reset(self, window):
        """
        Reset record attributes.
        """
        self.new = False

        # Reset the header elements record ID and record date
        self._record_id.reset(window)
        self._record_date.reset(window)

        # Reset metadata elements
        for meta_param in self.metadata:
            meta_param.reset(window)

        # Reset record data component elements
        for component in self.modules:
            component.reset(window)

    def remove_unsaved_ids(self):
        """
        Remove any unsaved IDs associated with the record, including the records own ID.
        """
        record_id = self.record_id()
        record_elements = self.modules

        record_entry = settings.records.fetch_rule(self.name)

        # Remove unsaved ID if record ID is found in the list of unsaved record IDs
        unsaved_ids = record_entry.get_unsaved_ids()
        if record_id in unsaved_ids:
            logger.debug('RecordType {NAME}: removing unsaved record ID {ID}'
                         .format(NAME=self.name, ID=record_id))
            record_entry.remove_unsaved_ids(record_ids=[record_id])

        # Remove unsaved components
        for record_element in record_elements:
            if record_element.etype != 'component':
                continue

            comp_type = record_element.record_type
            if comp_type is None:
                continue
            else:
                comp_entry = settings.records.fetch_rule(comp_type)

            # Get a list of components added to the component table (i.e. not in the database yet)
            unsaved_ids = comp_entry.get_unsaved_ids()

            ids_to_remove = []
            comp_ids = record_element.row_ids()
            for row_id in comp_ids:
                if row_id in unsaved_ids:  # don't attempt to remove IDs if already in the database
                    ids_to_remove.append(row_id)

            logger.debug('RecordType {NAME}: removing unsaved component IDs {IDS}'
                         .format(NAME=self.name, IDS=ids_to_remove))
            comp_entry.remove_unsaved_ids(record_ids=ids_to_remove)

    def fetch_element(self, identifier, by_key: bool = False, by_type: bool = False):
        """
        Fetch a record data element by name or event key.

        Arguments:
            identifier (str): identifying key.

            by_key (bool): fetch a record element by its element key [Default: False].

            by_type (bool): fetch record elements by element type [Default: False].
        """
        elements = self.modules

        if by_key is True:
            # Remove any binding strings and get last component of element key
            match = re.match(r'-(.*?)-', identifier)
            if not match:
                raise KeyError('unknown format provided for element identifier {ELEM}'.format(ELEM=identifier))
            identifier = match.group(0)  # identifier returned if match
            element_key = match.group(1)  # element key part of the identifier after removing any binding

            element_type = element_key.split('_')[-1]
            element_names = []
            for element in elements:
                try:
                    element_name = element.key_lookup(element_type)
                except KeyError:
                    element_name = None

                element_names.append(element_name)
            logger.debug('RecordType {NAME}: searching record elements for record element by element key {KEY}'
                         .format(NAME=self.name, KEY=identifier))
            logger.debug('RecordType {NAME}: there are {N} record elements with element type {TYPE}'
                         .format(NAME=self.name, N=len(element_names), TYPE=element_type))
        elif by_type is True:
            logger.debug('RecordType {NAME}: searching record elements for record element by element type {KEY}'
                         .format(NAME=self.name, KEY=identifier))
            element_names = [i.etype for i in elements]
        else:
            logger.debug('RecordType {NAME}: searching record elements for record element by name {KEY}'
                         .format(NAME=self.name, KEY=identifier))
            element_names = [i.name for i in elements]

        element = [elements[i] for i, j in enumerate(element_names) if j == identifier]
        if len(element) == 0:
            raise KeyError('element {ELEM} not found in list of record {NAME} elements'
                           .format(ELEM=identifier, NAME=self.name))
        elif len(element) == 1 and by_type is False:
            return element[0]
        else:
            return element

    def fetch_metadata(self, element, by_key: bool = False):
        """
        Fetch a record metadata by name or event key.
        """
        if by_key is True:
            element_type = element[1:-1].split('_')[-1]
            element_names = [i.key_lookup(element_type) for i in self.metadata]
        else:
            element_names = [i.name for i in self.metadata]

        if element in element_names:
            index = element_names.index(element)
            parameter = self.metadata[index]
        else:
            raise KeyError('element {ELEM} not found in list of record {NAME} metadata'
                           .format(ELEM=element, NAME=self.name))

        return parameter

    def run_event(self, window, event, values):
        """
        Perform a record action.
        """
        triggers = {'ValueEvent': False, 'ResizeEvent': False, 'DisplayEvent': False}

        # Collapse or expand a section frame
        section_bttns = [self.key_lookup('SectionBttn{}'.format(i)) for i in range(len(self.sections))]
        if event in section_bttns:
            section_index = section_bttns.index(event)
            self.collapse_expand(window, index=section_index)

            return False

        # Run a modifier event
        meta_events = [i for param in self.metadata for i in param.bindings]
        if event in meta_events:
            try:
                meta_param = self.fetch_metadata(event, by_key=True)
            except KeyError:
                logger.error('RecordType {NAME}, Record {ID}: unable to find the metadata element associated with '
                             'event key "{KEY}"'.format(NAME=self.name, ID=self.record_id(), KEY=event))
            else:
                triggers = meta_param.run_event(window, event, values)

            return False

        # Record element events
        elem_events = self.record_events(components_only=True)
        record_elements = self.modules

        # Get record element that is currently in focus
        try:
            focus_element = window.find_element_with_focus().Key
        except AttributeError:
            focus_element = None
        logger.debug('RecordType {NAME}: element in focus is {ELEM}'.format(NAME=self.name, ELEM=focus_element))

        # Check if any data elements are in edit mode
        for record_element in record_elements:
            try:
                edit_mode = record_element.edit_mode
            except AttributeError:
                continue
            else:
                if not edit_mode:  # element is not currently being edited
                    continue

            if focus_element not in record_element.elements:  # element is edited but is no longer in focus
                logger.debug('RecordType {NAME}, Record {ID}: data element {PARAM} is no longer in focus - saving '
                             'changes'.format(NAME=self.name, ID=self.record_id(), PARAM=record_element.name))

                # Attempt to save the data element value
                record_element.run_event(window, record_element.key_lookup('Save'), values)
            else:  # edited element is still in focus
                break

        # Get relevant record element
        if event in elem_events:
            try:
                record_element = self.fetch_element(event, by_key=True)
            except KeyError as e:
                logger.error('Record {ID}: unable to find the record element associated with event key {KEY} - {ERR}'
                             .format(ID=self.record_id(), KEY=event, ERR=e))

                return False
        else:
            record_element = None

        # Run a record element event
        if record_element is not None:
            logger.debug('RecordType {NAME}: record event {EVENT} is in record element {ELEM}'
                         .format(NAME=self.name, EVENT=event, ELEM=record_element.name))
            if record_element.etype == 'component':
                try:
                    add_bttn = record_element.fetch_parameter('Add', filters=False)
                    add_key, add_hkey = add_bttn.key_lookup()
                except KeyError:
                    add_key = add_hkey = None

                if event in (add_key, add_hkey):
                    # Close options panel, if open
                    record_element.set_table_dimensions(window)

                    try:
                        record_data = self.create_components(record_element)
                    except Exception as e:
                        msg = ''
                        logger.exception('DataTable {NAME}: {MSG} - {ERR}'.format(NAME=self.name, MSG=msg, ERR=e))
                        mod_win2.popup_error(msg)
                    else:
                        record_created = record_element.add_record(record_data)
                        if record_created:
                            record_element.update_display(window)
                else:
                    triggers = record_element.run_event(window, event, values)
            else:
                triggers = record_element.run_event(window, event, values)

        if triggers['DisplayEvent']:
            self.update_display(window)

        if triggers['ResizeEvent']:
            window.visibility_changed()
            window[self.key_lookup('DetailsCol')].contents_changed()
            window[self.key_lookup('MetaCol')].contents_changed()

        if triggers['ValueEvent']:
            # Update any element references with new values
            record_values = self.export_values(header=False)
            try:
                element_references = self.fetch_element('dependent', by_type=True)
            except KeyError:
                pass
            else:
                for record_element in element_references:
                    record_element.run_event(window, record_element.key_lookup('Element'), record_values.to_dict())

        return True

    def update_display(self, window):
        """
        Update the record display.
        """
        record_id = self.record_id()

        # Update the records header
        logger.debug('Record {ID}: updating the display header'.format(ID=record_id))
        self._record_id.update_display(window)
        self._record_date.update_display(window)

        for meta_elem in self.metadata:
            meta_elem.update_display(window)

        # Update the record elements
        logger.debug('Record {ID}: updating record element displays'.format(ID=record_id))
        for record_element in self.modules:
            record_element.update_display(window)

    def record_events(self, components_only: bool = False):
        """
        Return a list of available record events.

        Arguments:
            components_only (bool):
        """
        if components_only:
            events = []
        else:
            events = self.elements

        # Add record component events
        events.extend([i for record_element in self.modules for i in record_element.bindings])

        # Add record metadata events
        events.extend([i for param in self.metadata for i in param.bindings])

        return events

    def record_elements(self):
        """
        Return a list of all record elements.
        """
        elements = self.modules
        elements.extend(self.metadata)

        return elements

    def check_required_parameters(self):
        """
        Verify that required record element values exist.
        """
        record_id = self.record_id()

        all_passed = True
        for element in self.modules:
            passed = element.check_requirements()
            if not passed:
                msg = 'values missing for required element {ELEM}'.format(ELEM=element.description)
                logger.warning('Record {ID}: {MSG}'.format(ID=record_id, MSG=msg))
                mod_win2.popup_error(msg)

                all_passed = False
                break

        return all_passed

    def create_components(self, component_table, record_data=None):
        """
        Create new component records.
        """
        header = component_table.columns
        record_type = component_table.record_type
        record_date = self.record_date()

        if record_type is None:
            msg = 'required attribute "RecordType" missing from the configuration'
            raise AttributeError(msg)

        record_entry = settings.records.fetch_rule(record_type)

        # Create a new record object
        if record_data is None:
            record_data = pd.Series(index=header)
            creation_date = record_date
        else:
            if isinstance(record_data, pd.DataFrame):
                if record_data.empty:
                    msg = 'Record {ID}: unable to create record IDs when no components were provided'\
                        .format(ID=self.record_id())
                    logger.warning(msg)

                    return record_data
                creation_date = [record_date for _ in range(record_data.shape[0])]
            elif isinstance(record_data, pd.Series):  # single row (pandas series)
                creation_date = record_date
            elif isinstance(record_data, dict):
                record_data = pd.DataFrame(record_data)
                creation_date = [record_date for _ in range(record_data.shape[0])]
            else:
                record_data = pd.Series(index=header)
                creation_date = record_date

        print('creating record IDs for list of dates : {}'.format(creation_date))
        record_id = record_entry.create_record_ids(creation_date, offset=settings.get_date_offset())
        if not record_id:
            msg = 'unable to create an ID for the new record'
            raise AssertionError(msg)

        record_data['RecordID'] = record_id
        record_data['RecordDate'] = creation_date
        record_data[settings.creator_code] = user.uid
        record_data[settings.creation_date] = datetime.datetime.now()

        # Use record data to populate component fields when fields are shared between the component and record
        if isinstance(record_data, pd.Series):
            record_data = record_data.to_frame().T

        #defaults = self.export_values(header=False, references=False).to_dict()
        defaults = self.export_values(header=False).to_dict()
        for default_col in defaults:
            if default_col in header:
                default_value = defaults[default_col]
                if pd.isna(default_value):
                    continue

                try:
                    record_data[default_col].fillna(default_value, inplace=True)
                except KeyError:
                    record_data[default_col] = default_value

        return record_data.squeeze()

    def export_values(self, header: bool = True, edited_only: bool = False):
        """
        Export record data as a Series.

        Arguments:
            header (bool): include header components in the exported values [Default: True].

            edited_only (bool): only include values for record elements that were edited [Default: False].

        Returns:
            values (Series): values of the record's elements.
        """
        values = {}

        if header:
            record_id = self._record_id
            record_date = self._record_date

            # Add header values
            values[record_id.name] = record_id.data()
            values[record_date.name] = record_date.data()

            # Add modifier values
            for meta_elem in self.metadata:
                mod_value = meta_elem.data()
                if not pd.isna(mod_value):
                    values[meta_elem.name] = mod_value

        # Add parameter values
        record_elements = self.modules
        for record_element in record_elements:
            #if record_element.eclass == 'references' and not references:  # reference boxes and component tables
            #    continue
            values = {**values, **record_element.export_values(edited_only=edited_only)}

        return pd.Series(values)

    def export_associations(self, association_rule: str = None):
        """
        Export record data as a Series.

        Arguments:
            association_rule (str): only export associated records under the given association rule
                [Default: export all].

        Returns:
            df (DataFrame): reference dataframe of associated records.
        """
        ref_df = pd.DataFrame(columns=['RecordID', 'ReferenceID', 'ReferenceDate', 'RecordType', 'ReferenceType',
                                       'ReferenceNotes', 'ReferenceWarnings', 'IsChild', 'IsHardLink', 'IsApproved',
                                       'IsDeleted'])

        print('exporting record {} associated records'.format(self.name))

        try:
            refbox_elements = self.fetch_element('reference', by_type=True)
        except KeyError:
            refbox_elements = []

        for refbox in refbox_elements:
            refbox_rule = refbox.association_rule
            if association_rule and association_rule != refbox_rule:
                continue

            data = refbox.data()
            print('adding reference {} entries:'.format(refbox_rule))
            print(data)
            ref_df = ref_df.append(data, ignore_index=True)

        try:
            comp_elements = self.fetch_element('components', by_type=True)
        except KeyError:
            comp_elements = []

        for comp_tbl in comp_elements:
            comp_rule = comp_tbl.association_rule
            if association_rule and association_rule != comp_rule:
                continue

            data = comp_tbl.export_references(self.record_id())
            print('adding component {} entries:'.format(comp_rule))
            print(data)
            ref_df = ref_df.append(data, ignore_index=True)

        return ref_df

    def prepare_delete_statements(self, statements: dict = None):
        """
        Prepare statements for deleting the record and child records from the database.

        Arguments:
            statements (dict): optional dictionary of transaction statements to add the delete statements to.

        Returns:
            statements (dict): dictionary of transaction statements.
        """
        record_id = self.record_id()
        record_entry = settings.records.fetch_rule(self.name)
        association_rules = record_entry.association_rules

        if not statements:
            statements = {}

        nchild = 0
        nlink = 0
        for rule_name in association_rules:
            rule = association_rules[rule_name]
            assoc_type = rule['AssociationType']

            if assoc_type == 'child':
                continue

            ref_df = record_entry.import_references(record_id, rule=rule_name)

            # Subset references to include those that are child records or hard-linked
            if assoc_type == 'parent':  # reference table may contain child records
                nrow = ref_df[ref_df['IsChild']].shape[0]
                nchild += nrow
            elif assoc_type == 'reference':  # reference table may contain hard-linked records
                nrow = ref_df[ref_df['IsHardLink']].shape[0]
                nlink += nrow
            else:  # child records don't affect parent records
                continue

        if nlink > 0 or nchild > 0:  # Record is hard-linked to other records
            msg = 'Deleting record {ID} will also delete {N} dependent records and {NH} direct hard-linked records ' \
                  'as well. Would you like to continue with record deletion?'.format(ID=record_id, N=nchild, NH=nlink)
        else:
            msg = 'Are you sure that you would like to delete this record?'

        user_input = mod_win2.popup_confirm(msg)
        if user_input != 'OK':
            raise IOError('user selected to cancel record deletion')

        # Prepare statements for the removal of the record
        logger.debug('Record {ID}: preparing database transaction statements'.format(ID=record_id))

        try:
            statements = record_entry.delete_database_records(record_id, statements=statements)
        except Exception as e:
            msg = 'failed to delete record from the database - {ERR}'.format(ERR=e)
            logger.exception('Record {ID}: {MSG}'.format(ID=record_id, MSG=msg))

            raise

        return statements

    def delete(self, statements: dict = None):
        """
        Delete the record and child records from the database.

        Arguments:
            statements (dict): optional dictionary of transaction statement dictionary to add to.

        Returns:
            success (bool): record deletion was successful.
        """
        record_id = self.record_id()

        # Prepare deletion statements for the record and any child and hard-linked records
        try:
            statements = self.prepare_delete_statements(statements=statements)
        except Exception as e:
            msg = 'Record {ID}: failed to prepare database transaction statements for deletion - {ERR}' \
                .format(ID=record_id, ERR=e)
            logger.exception(msg)
            mod_win2.popup_error(msg)

            return False
        else:
            if len(statements) < 1:
                logger.debug('Record {ID}: no records needed deleting from the database'.format(ID=record_id))

                return True

        # Write record to the database
        logger.info('preparing to delete record {ID} and any child records'.format(ID=record_id))
        sstrings = []
        psets = []
        for i, j in statements.items():
            sstrings.append(i)
            psets.append(j)

        #success = user.write_db(sstrings, psets)
        success = True
        print(statements)

        return success

    def prepare_save_statements(self, statements: dict = None, save_all: bool = False):
        """
        Prepare to the statements for saving the record to the database.

        Arguments:
            statements (dict): optional dictionary of transaction statement dictionary to add to.

            save_all (bool): save all record element values, regardless of whether they were edited or not
                [Default: False]

        Returns:
            statements (dict): dictionary of transaction statements.
        """
        if not statements:
            statements = {}

        record_id = self.record_id()
        record_entry = settings.records.fetch_rule(self.name)

        # Verify that required parameters have values
        can_continue = self.check_required_parameters()
        if not can_continue:
            msg = 'failed to prepare save statements - not all required parameters have values'
            logger.warning('Record {ID}: {MSG}'.format(ID=record_id, MSG=msg))

            raise AttributeError(msg)

        # Prepare to save the record values
        logger.debug('Record {ID}: preparing database transaction statements'.format(ID=record_id))
        try:
            logger.debug('RecordEntry {NAME}, Record {ID}: exporting record values'
                         .format(NAME=self.name, ID=record_id))
            record_data = self.export_values()
            statements = record_entry.save_database_records(record_data, id_field=self.id_field, statements=statements)
        except Exception as e:
            msg = 'failed to save record "{ID}" - {ERR}'.format(ID=record_id, ERR=e)
            logger.exception(msg)

            raise
        else:
            del record_data

        # Prepare to save record references
        try:
            refbox_elements = self.fetch_element('reference', by_type=True)
        except KeyError:
            refbox_elements = []

        for refbox in refbox_elements:
            association_rule = refbox.association_rule

            if self.new or save_all:  # export all reference entries if record is new or if indicated to do so
                logger.debug('Record {ID}: preparing export statements for all "{ASSOC}" references'
                             .format(ID=record_id, ASSOC=association_rule))
                ref_data = refbox.data()
            else:  # export only the added or edited reference entries
                logger.debug('Record {ID}: preparing export statements for edited or new "{ASSOC}" references'
                             .format(ID=record_id, ASSOC=association_rule))
                ref_data = refbox.data(edited_rows=True)
            print(ref_data)
            statements = record_entry.save_database_references(ref_data, association_rule, statements=statements)

            logger.debug('Record {ID}: preparing export statements for deleted "{ASSOC}" references'
                         .format(ID=record_id, ASSOC=association_rule))
            deleted_df = refbox.data(deleted_rows=True)
            print(deleted_df)
            statements = record_entry.delete_database_references(deleted_df, association_rule, statements=statements)

        # Prepare to save record components
        try:
            component_tables = self.fetch_element('component', by_type=True)
        except KeyError:
            component_tables = []

        for comp_table in component_tables:
            comp_type = comp_table.record_type
            comp_entry = settings.records.fetch_rule(comp_type)

            if self.new or save_all:
                logger.debug('Record {ID}: preparing export statements for all components in component table "{COMP}"'
                             .format(ID=record_id, COMP=comp_table.name))
                exist_df = comp_table.data()
                ref_data = comp_table.export_references(record_id)
            else:
                logger.debug('Record {ID}: preparing export statements for only the edited components in component '
                             'table {COMP}'.format(ID=record_id, COMP=comp_table.name))
                ref_data = comp_table.export_references(record_id, edited_only=True)
                exist_df = comp_table.data(edited_rows=True)

            deleted_df = comp_table.data(all_rows=True, deleted_rows=True)

            if deleted_df.empty and exist_df.empty:
                logger.debug('Record {ID}: no components in component table {COMP} available to export'
                             .format(ID=record_id, COMP=comp_table.name))
                continue

            logger.debug('Record {ID}: preparing statements for component table "{TBL}"'
                         .format(ID=record_id, TBL=comp_table.name))

            assoc_rule_name = comp_table.association_rule
            assoc_rule = comp_entry.association_rules.get(assoc_rule_name)
            if assoc_rule['AssociationType'] == 'child':  # component records are a child records
                # Fully remove deleted component records if parent-child relationship
                deleted_ids = comp_table.row_ids(indices=deleted_df.index)
                if not deleted_df.empty:
                    statements = comp_entry.delete_database_records(deleted_ids, statements=statements)

                    # Subset ref_data so that references are not updated twice
                    ref_data = ref_data[~ref_data['ReferenceID'].isin(deleted_ids)]

                # Set reference flags
                ref_data['IsChild'] = True
            else:
                # Set reference flags
                ref_data['IsChild'] = False

            statements = record_entry.save_database_references(ref_data, assoc_rule_name, statements=statements)

            # Prepare transaction statements for the component records
            try:
                statements = comp_entry.save_database_records(exist_df, statements=statements)
            except Exception as e:
                msg = 'failed to save record "{ID}" - {ERR}'.format(ID=record_id, ERR=e)
                logger.error(msg)

                raise

        return statements

    def save(self, statements: dict = None):
        """
        Save the record and child records to the database.

        Arguments:
            statements (dict): optional dictionary of transaction statement dictionary to add to.

        Returns:
            success (bool): record deletion was successful.
        """
        record_id = self.record_id()

        try:
            statements = self.prepare_save_statements(statements=statements)
        except Exception as e:
            msg = 'failed to save record {ID}'.format(ID=record_id)
            logger.exception('Record {ID}: {MSG} - {ERR}'.format(ID=record_id, MSG=msg, ERR=e))

            mod_win2.popup_error(msg)

            return False
        else:
            if len(statements) < 1:
                logger.error('Record {ID}: failed to create transaction statements'.format(ID=record_id))

                return False

        logger.info('Record {ID}: preparing to save record and record components'.format(ID=record_id))
        sstrings = []
        psets = []
        for i, j in statements.items():
            sstrings.append(i)
            psets.append(j)

        success = user.write_db(sstrings, psets)
        #success = True
        print('final save statements:')
        print(statements)

        return success

    def generate_report(self):
        """
        Generate a summary report for the record.
        """
        record_id = self._record_id.format_display()
        record_date = self._record_date.format_display()
        report_title = self.title

        report_dict = {'title': '{TITLE}: {ID} ({DATE})'.format(TITLE=report_title, ID=record_id, DATE=record_date),
                       'info': [],
                       'sections': []}

        report_def = self.report
        if not report_def:
            return report_dict

        logger.info('{NAME}: generating the template for the record report'.format(NAME=report_title))

        # Add Info elements to the report, if defined
        info_def = report_def['Info']
        for element_name in info_def:
            logger.debug('{NAME}: formatting report element {ELEM}'.format(NAME=report_title, ELEM=element_name))
            try:
                element = self.fetch_element(element_name)
            except KeyError:
                logger.warning('{NAME}: report item {ELEM} is not a valid record element'
                               .format(NAME=report_title, ELEM=element_name))
                continue

            elem_title = element.description
            elem_value = element.format_display()
            if not elem_value or elem_value == "":
                elem_value = 'N/A'

            report_dict['info'].append((elem_title, elem_value))

        # Add sub-sections to the report, if defined
        section_def = report_def['Subsections']
        for heading in section_def:
            section = section_def[heading]

            try:
                heading_title = section['Title']
            except KeyError:
                heading_title = heading

            logger.debug('{NAME}: formatting report heading {HEAD}'.format(NAME=report_title, HEAD=heading_title))

            try:
                component = section['Component']
            except KeyError:
                logger.warning('{NAME}, Heading {SEC}: missing required parameter "Component" in report configuration'
                               .format(NAME=report_title, SEC=heading))
                continue
            else:
                try:
                    comp_table = self.fetch_element(component)
                except KeyError:
                    logger.warning('{NAME}, Heading {SEC}: unknown Component "{COMP}" defined in report configuration'
                                   .format(NAME=report_title, SEC=heading, COMP=component))
                    continue
                else:
                    if comp_table.etype != 'component':
                        logger.warning('{NAME}, Heading {SEC}: Component "{COMP}" defined in report configuration must '
                                       'be a component table'.format(NAME=report_title, SEC=heading, COMP=component))
                        continue

            # Subset table rows based on configured subset rules
            try:
                sub_rule = section['Subset']
            except KeyError:
                subset_df = comp_table.data()
            else:
                try:
                    subset_df = comp_table.subset(sub_rule)
                except ValueError:
                    continue
                else:
                    if subset_df.empty:
                        logger.warning('{NAME}, Heading {SEC}: sub-setting on rule "{SUB}" '
                                       'removed all records'.format(NAME=report_title, SEC=heading, SUB=sub_rule))
                        continue

            # Select columns configured
            try:
                subset_df = subset_df[section['Columns']]
            except KeyError as e:
                logger.warning('{NAME}, Heading {SEC}: unknown column provided to the report configuration - {ERR}'
                               .format(NAME=report_title, SEC=heading, ERR=e))
                continue

            if subset_df.empty:
                logger.warning('{NAME}, Heading {SEC}: no records remaining after sub-setting'
                               .format(NAME=report_title, SEC=heading))
                html_out = '<p>N/A</p>'
                report_dict['sections'].append((heading_title, html_out))

                continue

            # Format table for display
            display_df = subset_df.copy()
            for column in subset_df.columns:
                try:
                    display_df[column] = comp_table.format_display_column(subset_df, column)
                except Exception as e:
                    logger.exception('{NAME}, Heading {SEC}: failed to format column "{COL}" - {ERR}'
                                     .format(NAME=report_title, SEC=heading, COL=column, ERR=e))

            # Index rows using grouping list in configuration
            try:
                grouping = section['Group']
            except KeyError:
                grouped_df = display_df
            else:
                grouped_df = display_df.set_index(grouping).sort_index()

            html_str = grouped_df.to_html(header=False, index_names=False, float_format='{:,.2f}'.format,
                                          sparsify=True, na_rep='')

            # Highlight errors in html string
            annotations = comp_table.annotate_rows(grouped_df.reset_index())
            colors = {i: comp_table.annotation_rules[j]['BackgroundColor'] for i, j in annotations.items()}
            try:  # colors should be a dictionary of row index with matching color
                html_out = replace_nth(html_str, '<tr>', '<tr style="background-color: {}">', colors)
            except Exception as e:
                logger.warning('{NAME}, Heading {SEC}: failed to annotate output - {ERR}'
                               .format(NAME=report_title, SEC=heading, ERR=e))
                html_out = html_str

            # Add summary totals
            try:
                total_col = section['Totals']
            except KeyError:
                pass
            else:
                if total_col in subset_df.columns:
                    try:
                        col_total = comp_table.summarize_column(total_col, indices=subset_df.index.tolist())
                    except Exception as e:
                        logger.warning('{NAME}, Heading {SEC}: failed to summarize column "{COL}" - {ERR}'
                                       .format(NAME=report_title, SEC=heading, COL=total_col, ERR=e))
                    else:
                        if isinstance(col_total, float):
                            summ_value = '{:,.2f}'.format(col_total)
                        else:
                            summ_value = '{}'.format(col_total)

                        soup = BeautifulSoup(html_out, 'html.parser')

                        # Add a totals footer to the table
                        footer = soup.new_tag('tfoot')
                        footer_row = soup.new_tag('tr')
                        footer_header = soup.new_tag('td')
                        footer_header['id'] = 'total'
                        footer_header['colspan'] = '{}'.format(subset_df.shape[1] - 1)
                        footer_header['style'] = 'text-align:right; font-weight:bold;'
                        footer_header.string = 'Total:'
                        footer_row.append(footer_header)

                        footer_data = soup.new_tag('td')
                        footer_data.string = summ_value
                        footer_row.append(footer_data)

                        footer.append(footer_row)
                        soup.table.append(footer)

                        html_out = soup.decode()
                else:
                    logger.warning('{NAME}, Heading {SEC}: Totals column "{COL}" not found in list of output columns'
                                   .format(NAME=report_title, SEC=heading, COL=total_col))

            report_dict['sections'].append((heading_title, html_out))

        return report_dict

    def layout(self, size, padding: tuple = None, view_only: bool = False, ugroup: list = None):
        """
        Generate a GUI layout for the database record.
        """
        width, height = size

        # Permissions
        level = self.level
        is_new = self.new

        logger.debug('RecordType {NAME}: creating {NEW}record layout at level {LEVEL}'
                     .format(NAME=self.name, NEW=('new ' if is_new else ''), LEVEL=level))

        editable = False if (view_only is True and is_new is False) or (level > 1) else True
        user_priv = ugroup if ugroup else user.access_permissions()

        # Element parameters
        bg_col = mod_const.ACTION_COL
        text_col = mod_const.TEXT_COL
        inactive_col = mod_const.INACTIVE_COL
        select_col = mod_const.SELECT_TEXT_COL
        frame_col = mod_const.FRAME_COL

        bold_font = mod_const.BOLD_HEADING_FONT
        main_font = mod_const.MAIN_FONT

        pad_el = mod_const.ELEM_PAD
        pad_v = mod_const.VERT_PAD

        padding = self._padding if not padding else padding
        self._padding = padding
        pad_w, pad_h = padding

        bar_h = 22
        header_h = 32

        min_h = header_h + bar_h
        self._minimum_height = min_h

        tab_w = width - pad_w * 2
        tab_h = height - (header_h + bar_h + pad_h * 2)

        # Layout elements

        # Record header
        headers = [sg.Canvas(size=(0, header_h), background_color=bg_col)]
        #headers.extend(self._record_id.layout(padding=((0, pad_el * 2), 0), auto_size_desc=True, size=(20, 1)))
        #headers.extend(self._record_date.layout(padding=(0, 0), auto_size_desc=True, size=(20, 1)))
        headers.append(self._record_id.layout(padding=((0, pad_h), 0), editable=False))
        headers.append(self._record_date.layout(editable=False))
        header_key = self.key_lookup('Header')
        header_layout = sg.Col([headers], key=header_key, expand_x=True, background_color=bg_col, justification='l',
                               vertical_alignment='c')

        # Create the layout for the record information panel
        sections = self.sections

        sections_layout = []
        for index, section_name in enumerate(sections):
            section_entry = sections[section_name]

            section_title = section_entry['Title']
            section_bttn_key = self.key_lookup('SectionBttn{}'.format(index))
            section_header = [sg.Col([[sg.Canvas(size=(0, bar_h), background_color=frame_col),
                                       sg.Text(section_title, pad=((0, pad_el * 2), 0), background_color=frame_col,
                                               font=bold_font),
                                       sg.Button('', image_data=mod_const.HIDE_ICON, key=section_bttn_key,
                                                 disabled=False,
                                                 button_color=(text_col, frame_col), border_width=0, visible=True,
                                                 metadata={'visible': True, 'disabled': False})
                                       ]], background_color=frame_col, expand_x=True)]
            sections_layout.append(section_header)

            section_elements = section_entry['Elements']
            section_layout = []
            for element_name in section_elements:
                element = self.fetch_element(element_name)

                can_edit = editable and element.permissions in user_priv
                element_layout = [element.layout(padding=(0, int(pad_v / 2)), editable=can_edit, overwrite=is_new,
                                                 level=level)]
                section_layout.append(element_layout)

            section_panel_key = self.key_lookup('SectionFrame{}'.format(index))
            sections_layout.append([sg.pin(sg.Col(section_layout, key=section_panel_key, background_color=bg_col,
                                                  visible=True, expand_x=True, metadata={'visible': True}))])

        tab_key = self.key_lookup('DetailsTab')
        col_key = self.key_lookup('DetailsCol')
        details_tab = sg.Tab('{:^40}'.format('Details'),
                             [[sg.Col(sections_layout, key=col_key, size=(tab_w, tab_h), pad=(0, pad_v),
                                      background_color=bg_col, expand_y=True, expand_x=True, scrollable=True,
                                      vertical_scroll_only=True, vertical_alignment='t', element_justification='l')]],
                             key=tab_key, background_color=bg_col)

        # Create layout for record metadata
        metadata = self.metadata
        if len(metadata) > 0:
            metadata_visible = True
            annotation_layout = []
            for param in metadata:
                param_name = param.name
                can_edit = editable and param.permissions in user_priv

                annotation_layout.append([param.layout(editable=can_edit, level=level)])
        else:  # don't show tab for new records or record w/o configured metadata
            metadata_visible = False
            annotation_layout = [[]]

        meta_tab_key = self.key_lookup('MetaTab')
        meta_key = self.key_lookup('MetaCol')
        info_tab = sg.Tab('{:^40}'.format('Metadata'),
                          [[sg.Col(annotation_layout, key=meta_key, pad=(0, pad_v), size=(tab_w, tab_h),
                                   background_color=bg_col, scrollable=True, vertical_scroll_only=True, expand_x=True,
                                   expand_y=True, vertical_alignment='t', element_justification='l')]],
                          key=meta_tab_key, background_color=bg_col, visible=metadata_visible)

        main_layout = sg.TabGroup([[details_tab, info_tab]], key=self.key_lookup('TG'),
                                  background_color=inactive_col, tab_background_color=inactive_col,
                                  selected_background_color=bg_col, selected_title_color=select_col,
                                  title_color=text_col, border_width=0, tab_location='topleft', font=main_font)

        # Pane elements must be columns
        record_key = self.key_lookup('Record')
        layout = [[sg.Col([[header_layout], [main_layout]], key=record_key, pad=padding,
                          background_color=bg_col, expand_x=True, expand_y=True)]]

        return layout

    def resize(self, window, size):
        """
        Resize the record elements.
        """
        width, height = size

        logger.debug('Record {ID}: resizing display to {W}, {H}'.format(ID=self.record_id(), W=width, H=height))

        # Expand the record containers
        min_h = self._minimum_height
        record_h = height if height > min_h else min_h

        pad_w, pad_h = self._padding
        scroll_w = mod_const.SCROLL_WIDTH
        tab_h = 22
        header_h = 32

        # Set the size of the record container
        record_w = width - pad_w * 2
        record_size = (record_w, record_h)
        mod_lo.set_size(window, self.key_lookup('Record'), record_size)

        # Set the size of the tab containers
        bffr_h = tab_h + header_h + pad_h * 2
        tab_size = (record_w, height - bffr_h)
        mod_lo.set_size(window, self.key_lookup('DetailsCol'), tab_size)
        mod_lo.set_size(window, self.key_lookup('MetaCol'), tab_size)

        # Set the size of the header elements
        for header in (self._record_id, self._record_date):
            header.resize(window)

        # Set the size of the metadata elements
        meta_h = None
        meta_w = int(width * 0.5)
        for meta_param in self.metadata:
            meta_param.resize(window, size=(meta_w, meta_h))

        # Expand the size of the record elements
        for record_element in self.modules:
            etype = record_element.etype
            if etype == 'multiline':  # multiline data variable
                elem_h = None
                elem_w = width - (pad_w * 2 + scroll_w)
            elif etype in ('table', 'component'):  # data table type
                elem_h = None
                elem_w = width - (pad_w * 2 + scroll_w)
            elif etype in ('list', 'reference'):  # data list type
                elem_h = mod_const.LISTBOX_HEIGHT
                elem_w = width - (pad_w * 2 + scroll_w)
            else:  # data variable type
                elem_h = None
                elem_w = int(width * 0.5)

            elem_size = (elem_w, elem_h)
            record_element.resize(window, size=elem_size)

    def collapse_expand(self, window, index: int = 0):
        """
        Collapse record frames.
        """
        hide_key = self.key_lookup('SectionBttn{}'.format(index))
        frame_key = self.key_lookup('SectionFrame{}'.format(index))

        if window[frame_key].metadata['visible'] is True:  # already visible, so want to collapse the frame
            logger.debug('RecordType {NAME}, Record {ID}: collapsing section frame {FRAME}'
                         .format(NAME=self.name, ID=self.record_id(), FRAME=index))
            window[hide_key].update(image_data=mod_const.UNHIDE_ICON)
            window[frame_key].update(visible=False)

            window[frame_key].metadata['visible'] = False
        else:  # not visible yet, so want to expand the frame
            logger.debug('RecordType {NAME}, Record {ID}: expanding section frame {FRAME}'
                         .format(NAME=self.name, ID=self.record_id(), FRAME=index))
            window[hide_key].update(image_data=mod_const.HIDE_ICON)
            window[frame_key].update(visible=True)

            window[frame_key].metadata['visible'] = True


def replace_nth(s, sub, new, ns):
    """
    Replace the nth occurrence of an substring in a string
    """
    if isinstance(ns, str):
        ns = [ns]

    where = [m.start() for m in re.finditer(sub, s)]
    new_s = s
    for count, start_index in enumerate(where):
        if count not in ns:
            continue

        if isinstance(ns, dict):
            new_fmt = new.format(ns[count])
        else:
            new_fmt = new

        before = new_s[:start_index]
        after = new_s[start_index:]
        after = after.replace(sub, new_fmt, 1)  # only replace first instance of substring
        new_s = before + after

    return new_s
