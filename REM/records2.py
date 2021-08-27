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
import pandas as pd

import REM.constants as mod_const
import REM.database as mod_db
import REM.elements as mod_elem
import REM.parameters as mod_param
import REM.secondary as mod_win2
from REM.client import logger, server_conn, settings, user


class RecordsConfiguration:
    """
    Class to store and manage program records configuration settings.

    Attributes:

        name (str): name of the configuration document.

        title (str): descriptive name of the configuration document.

        rules (list): List of record entries.
    """

    def __init__(self, records_doc):
        """
        Class to store and manage program records configuration settings.

        Arguments:

            records_doc: records document.
        """

        if records_doc is None:
            mod_win2.popup_error('missing required configuration document Records')
            sys.exit(1)

        try:
            audit_name = records_doc['name']
        except KeyError:
            mod_win2.popup_error('the "Records" parameter configuration "name" is a required field')
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
            mod_win2.popup_error('the "Records" configuration parameter "rules" is a required field')
            sys.exit(1)

        self.rules = []
        for record_group in record_entries:
            record_entry = record_entries[record_group]
            self.rules.append(RecordEntry(record_group, record_entry))

        self.approved_groups = ['account', 'bank_deposit', 'bank_statement', 'audit', 'cash_expense']

    def print_rules(self, by_title: bool = False):
        """
        Print rules of a the rule set by its name or title.
        """
        if by_title is True:
            rule_names = [i.menu_title for i in self.rules]
        else:
            rule_names = [i.name for i in self.rules]

        return rule_names

    def fetch_rule(self, name, by_title: bool = False):
        """
        Fetch a given rule from the rule set by its name or title.
        """
        if by_title is True:
            rule_names = [i.menu_title for i in self.rules]
        else:
            rule_names = [i.name for i in self.rules]

        try:
            index = rule_names.index(name)
        except ValueError:
            logger.warning('record entry {NAME} not in Records configuration. Available record entries are {ALL}'
                           .format(NAME=name, ALL=', '.join(rule_names)))
            rule = None
        else:
            rule = self.rules[index]

        return rule

    def get_approved_groups(self):
        """
        Return a list of approved record-type groups
        """
        return self.approved_groups


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
            self.group = entry['RecordGroup']
        except KeyError:
            mod_win2.popup_error('RecordEntry {NAME}: configuration missing required parameter "RecordGroup"'
                                 .format(NAME=name))
            sys.exit(1)

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

        # Import table layout configuration
        try:
            self.import_table = entry['ImportTable']
        except KeyError:
            mod_win2.popup_error('RecordEntry {NAME}: configuration missing required parameter "ImportTable"'
                                 .format(NAME=name))
            sys.exit(1)

        # Record layout configuration
        try:
            self.record_layout = entry['RecordLayout']
        except KeyError:
            mod_win2.popup_error('RecordsEntry {NAME}: configuration missing required parameter "RecordLayout"'
                                 .format(NAME=name))
            sys.exit(1)

    def import_records(self, params: list = None):
        """
        Import all records from the database.
        """
        params = [] if params is None else params

        # Add configured import filters
        filters = mod_db.format_import_filters(self.import_rules)
        table_statement = mod_db.format_tables(self.import_rules)
        columns = mod_db.format_import_columns(self.import_rules)

        # Add optional parameter-based filters
        for param in params:
            dbcol = mod_db.get_import_column(self.import_rules, param.name)
            if dbcol:
                param_filter = param.query_statement(dbcol)
                if param_filter is not None:
                    filters.append(param_filter)

        # Query existing database entries
        import_df = user.read_db(*user.prepare_query_statement(table_statement, columns=columns, filter_rules=filters),
                                 prog_db=True)
        return import_df

    def confirm_saved(self, id_list, id_field: str = 'RecordID'):
        """
        Check whether or not records have already been saved to the database.
        """
        if isinstance(id_list, str):
            record_ids = [id_list]
        else:
            record_ids = id_list

        if not len(id_list) > 0:
            return []

        record_ids = sorted(list(set(record_ids)))  # prevents duplicate IDs
        logger.debug('verifying whether records {IDS} of type "{TYPE}" have been previously saved to the database'
                     .format(IDS=record_ids, TYPE=self.name))

        # Add configured import filters
        table_statement = mod_db.format_tables(self.import_rules)
        id_col = mod_db.get_import_column(self.import_rules, id_field)

        # Query existing database entries
        import_df = pd.DataFrame()
        for i in range(0, len(record_ids), 1000):  # split into sets of 1000 to prevent max parameter errors in SQL
            sub_ids = record_ids[i: i + 1000]
            filter_clause = '{COL} IN ({VALS})'.format(COL=id_col, VALS=','.join(['?' for _ in sub_ids]))
            filters = (filter_clause, tuple(sub_ids))

            if import_df.empty:
                import_df = user.read_db(*user.prepare_query_statement(table_statement, columns=id_col,
                                                                       filter_rules=filters), prog_db=True)
            else:
                import_df = import_df.append(user.read_db(*user.prepare_query_statement(table_statement,
                                                                                        columns=id_col,
                                                                                        filter_rules=filters),
                                                          prog_db=True), ignore_index=True)

        try:
            import_ids = import_df.iloc[:, 0].values.tolist()
        except IndexError as e:
            msg = 'failed to verify whether records {IDS} of type "{TYPE}" have been previously saved to the ' \
                  'database - {ERR}'.format(IDS=record_ids, TYPE=self.name, ERR=e)
            logger.error(msg)
            raise

        records_saved = []
        for record_id in record_ids:
            if record_id in import_ids:
                records_saved.append(True)
            else:
                records_saved.append(False)

        if isinstance(id_list, str):
            return records_saved[0]
        else:
            return records_saved

    def load_record_data(self, id_list, id_field: str = 'RecordID'):
        """
        Load a record from the database using the record ID.
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
                                                                       filter_rules=filters), prog_db=True)
            else:
                import_df = import_df.append(user.read_db(*user.prepare_query_statement(table_statement,
                                                                                        columns=columns,
                                                                                        filter_rules=filters),
                                                          prog_db=True), ignore_index=True)

        logger.debug('{NLOADED} records passed the query filters out of {NTOTAL} requested records'
                     .format(NLOADED=import_df.shape[0], NTOTAL=len(record_ids)))

        return import_df

    def export_table(self, df, id_field: str = 'RecordID', id_exists: bool = False, statements: dict = None,
                     export_columns: bool = True):
        import_rules = self.import_rules

        if not statements:
            statements = {}

        if not isinstance(df, pd.DataFrame):
            raise ValueError('df must be a DataFrame or Series')

        if df.empty:
            return statements

        if id_exists:  # record already exists in the database
            # Add edit details to records table
            df.loc[:, settings.editor_code] = user.uid
            df.loc[:, settings.edit_date] = datetime.datetime.now().strftime(settings.date_format)
        else:  # new record was created
            # Add record creation details to records table
            df.loc[:, settings.creator_code] = user.uid
            df.loc[:, settings.creation_date] = datetime.datetime.now().strftime(settings.date_format)

        # Prepare transaction for each export table containing fields comprising the record
        columns = df.columns.values.tolist()
        for table in import_rules:
            table_entry = import_rules[table]

            if export_columns:
                references = {j: i for i, j in table_entry['Columns'].items()}
            else:
                references = {i: i for i in table_entry['Columns']}

            try:
                id_col = references[id_field]
            except KeyError:
                msg = 'missing ID column "{COL}" from record import columns {COLS}' \
                    .format(COL=id_field, COLS=list(references.keys()))
                logger.error(msg)
                raise KeyError(msg)

            # Prepare column value updates
            include_columns = [i for i in columns if i in references]
            export_df = df[include_columns]

            export_columns = [references[i] for i in include_columns]
            export_values = [tuple(i) for i in export_df.values.tolist()]

            if id_exists:
                record_ids = df[id_field]
                if not isinstance(record_ids, pd.Series):
                    record_ids = [record_ids]
                else:
                    record_ids = record_ids.values.tolist()
                filter_params = [(i,) for i in record_ids]
                filter_clause = '{COL} = ?'.format(COL=id_col)
                statement, param = user.prepare_update_statement(table, export_columns, export_values, filter_clause,
                                                                 filter_params)
            else:
                statement, param = user.prepare_insert_statement(table, export_columns, export_values)

            if isinstance(param, list):
                try:
                    statements[statement].extend(param)
                except KeyError:
                    statements[statement] = param
            elif isinstance(param, tuple):
                try:
                    statements[statement].append(param)
                except KeyError:
                    statements[statement] = [param]

        return statements

    def delete_record(self, record_ids, statements: dict = None, id_field: str = 'RecordID'):
        """
        Delete a record from the database.
        """
        ref_table = settings.reference_lookup
        delete_code = settings.delete_field

        if not statements:
            statements = {}

        if isinstance(record_ids, str):
            record_ids = [record_ids]

        record_ids = list(set(record_ids))

        # Set record as deleted in the database
        import_rules = self.import_rules

        for table in import_rules:
            table_entry = import_rules[table]

            references = {j: i for i, j in table_entry['Columns'].items()}
            id_col = references[id_field]

            # Remove record from the export table
            for i in range(0, len(record_ids), 1000):  # split into sets of 1000 to prevent max parameter errors in SQL
                sub_ids = record_ids[i: i + 1000]
                filter_clause = '{COL} IN ({VALS})'.format(COL=id_col, VALS=','.join(['?' for _ in sub_ids]))
                filters = tuple(sub_ids)
                statement, param = user.prepare_update_statement(table, [delete_code], (1,), filter_clause, filters)

                if isinstance(param, list):
                    try:
                        statements[statement].extend(param)
                    except KeyError:
                        statements[statement] = param
                elif isinstance(param, tuple):
                    try:
                        statements[statement].append(param)
                    except KeyError:
                        statements[statement] = [param]

        # Remove all record associations
        for record_id in record_ids:
            filter_clause = 'DocNo=? OR RefNo=?'
            ref_filters = (record_id, record_id)
            ref_cols = [settings.editor_code, settings.edit_date, delete_code]
            ref_params = (user.uid, datetime.datetime.now(), 1)
            statement, param = user.prepare_update_statement(ref_table, ref_cols, ref_params, filter_clause,
                                                             ref_filters)
            if isinstance(param, list):
                try:
                    statements[statement].extend(param)
                except KeyError:
                    statements[statement] = param
            elif isinstance(param, tuple):
                try:
                    statements[statement].append(param)
                except KeyError:
                    statements[statement] = [param]

        return statements

    def _import_saved_ids(self, record_dates, id_field: str = 'RecordID'):
        """
        Get a list of saved record IDs for records with record date within the provided range of dates.
        """
        # Prepare query parameters
        table_statement = mod_db.format_tables(self.import_rules)
        id_col = mod_db.get_import_column(self.import_rules, id_field)

        # Prepare the date range
        record_dates.sort()
        try:
            first_date = record_dates[0]
            last_date = record_dates[-1]
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
                                                                 order=id_col), prog_db=True)

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
            saved_ids = self._import_saved_ids(record_dates)
        except Exception as e:
            logger.error('failed to create IDs for the record entries of type {TYPE} - {ERR}'
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
        """
        if not record_ids:
            record_ids = self.get_unsaved_ids(internal_only=internal_only)
            if not record_ids:
                return False

        if not len(record_ids) > 0:
            return True

        logger.debug('RecordEntry {NAME}: attempting to remove IDs {ID} from the list of unsaved record IDs'
                     .format(NAME=self.name, ID=record_ids))

        value = {'ids': record_ids, 'record_type': self.name}
        content = {'action': 'remove_ids', 'value': value}
        request = {'content': content, 'encoding': "utf-8"}
        response = server_conn.process_request(request)

        success = response['success']
        if success is False:
            msg = 'RecordEntry {NAME}: failed to remove IDs {ID} from the list of unsaved record IDs of type ' \
                  '{TYPE} - {ERR}'.format(NAME=self.name, ID=record_ids, TYPE=self.name, ERR=response['value'])
            logger.error(msg)
        else:
            logger.debug('RecordEntry {NAME}: successfully removed {ID} from the list of unsaved record IDs '
                         'associated with the record entry'.format(NAME=self.name, ID=record_ids))

        return success

    def get_unsaved_ids(self, internal_only: bool = False):
        """
        Retrieve a list of unsaved record IDs from the database of unsaved record IDs associated with the record type.
        """
        if internal_only is True:
            instance = settings.instance_id
            logger.debug('RecordEntry {NAME}: attempting to obtain an instance-specific list of unsaved record IDs '
                         'associated with the record entry'.format(NAME=self.name))
        else:
            instance = None
            logger.debug('RecordEntry {NAME}: attempting to obtain list of unsaved record IDs associated with the '
                         'record entry'.format(NAME=self.name))

        value = {'instance': instance, 'record_type': self.name}
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
        """
        logger.debug('RecordEntry {NAME}: attempting to add record IDs {ID} to the list of unsaved record IDs '
                     'associated with the record entry'.format(NAME=self.name, ID=record_ids))

        if isinstance(record_ids, str):
            id_set = [(record_ids, settings.instance_id)]
        else:
            id_set = [(i, settings.instance_id) for i in record_ids]

        value = {'ids': id_set, 'record_type': self.name}
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
        name (str): name of the configured record entry.

        id (int): record element number.

        elements (list): list of GUI element keys.

        title (str): record display title.

        permissions (dict): dictionary mapping permission rules to permission groups.

        sections (dict): component elements mapped to their respective sections.

        headers (list): list of header parameters.

        metadata (list): list of metadata parameters.

        components (list): list of record elements used to display information about the record.

        _references (dict): elements that are referenced by another element.

        report (dict): report definition
    """

    def __init__(self, name, entry, level: int = 0):
        """
        Arguments:
            entry (class): configuration entry for the record.

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
                         ['ReferencesButton', 'ReferencesFrame', 'ComponentsButton', 'ComponentsFrame',
                          'Height', 'Width', 'DetailsTab', 'InfoTab', 'TG', 'FrameHeight', 'FrameWidth']]

        # User access permissions
        try:
            permissions = entry['Permissions']
        except KeyError:
            self.permissions = {'edit': 'admin', 'delete': 'admin', 'mark': 'admin', 'references': 'admin',
                                'components': 'admin', 'approve': 'admin', 'report': 'admin'}
        else:
            self.permissions = {'edit': permissions.get('Edit', 'admin'),
                                'delete': permissions.get('Delete', 'admin'),
                                'mark': permissions.get('MarkForDeletion', 'admin'),
                                'references': permissions.get('ModifyReferences', 'admin'),
                                'components': permissions.get('ModifyComponents', 'admin'),
                                'approve': permissions.get('Approve', 'admin'),
                                'report': permissions.get('Report', 'admin')}

        try:
            self.title = entry['Title']
        except KeyError:
            self.title = self.name

        # Record header
        self.headers = []
        try:
            headers = entry['Header']
        except KeyError:
            raise AttributeError('missing required configuration parameter "Header"')
        else:
            for param_name in headers:
                param_entry = headers[param_name]
                param_entry['IsEditable'] = False
                param_layout = param_entry['ElementType']
                if param_layout == 'dropdown':
                    param_class = mod_param.DataParameterCombo
                elif param_layout == 'input':
                    param_class = mod_param.DataParameterInput
                elif param_layout == 'range':
                    param_class = mod_param.DataParameterRange
                elif param_layout == 'checkbox':
                    param_class = mod_param.DataParameterCheckbox
                else:
                    raise AttributeError('unknown type {TYPE} provided to record header {PARAM}'
                                         .format(TYPE=param_layout, PARAM=param_name))

                param = param_class(param_name, param_entry)

                self.headers.append(param)
                self.elements += param.elements

        header_names = [i.name for i in self.headers]
        if self.id_field not in header_names:
            raise AttributeError('missing required header "{}"'.format(self.id_field))
        if self.date_field not in header_names:
            raise AttributeError('missing required header "{}"'.format(self.date_field))

        # Record metadata
        self.metadata = []
        try:
            metadata = entry['Metadata']
        except KeyError:
            self.metadata = []
        else:
            for param_name in metadata:
                param_entry = metadata[param_name]
                param_layout = param_entry['ElementType']
                if param_layout == 'dropdown':
                    param_class = mod_param.DataParameterCombo
                elif param_layout == 'input':
                    param_class = mod_param.DataParameterInput
                elif param_layout == 'range':
                    param_class = mod_param.DataParameterRange
                elif param_layout == 'checkbox':
                    param_class = mod_param.DataParameterCheckbox
                else:
                    raise AttributeError('unknown type {TYPE} provided to record header {PARAM}'
                                         .format(TYPE=param_layout, PARAM=param_name))

                param = param_class(param_name, param_entry)

                self.metadata.append(param)
                self.elements += param.elements

        # Record data elements
        self.sections = {}
        self.components = []
        self._references = {}
        try:
            components = entry['Components']
        except KeyError:
            raise AttributeError('missing required configuration parameter "Body"')
        else:
            for i, section in enumerate(components):
                section_entry = components[section]
                self.elements.extend(['-{NAME}_{ID}_{ELEM}-'.format(NAME=self.name, ID=self.id, ELEM=i) for i in
                                      ['SectionBttn{}'.format(i), 'SectionFrame{}'.format(i)]])
                self.sections[section] = {'Title': section_entry.get('Title', section),
                                          'Icon': section_entry.get('Icon', None),
                                          'Elements': []}

                try:
                    section_elements = section_entry['Elements']
                except KeyError:
                    raise AttributeError('Record section {} is missing required parameter "Elements"'.format(section))
                for element_name in section_elements:
                    self.sections[section]['Elements'].append(element_name)
                    elem_entry = section_elements[element_name]
                    try:
                        etype = elem_entry['ElementType']
                    except KeyError:
                        raise AttributeError('"Details" element {NAME} is missing the required field "ElementType"'
                                             .format(NAME=element_name))

                    # Set the object type of the record element.
                    if etype == 'table':
                        element_class = mod_elem.TableElement
                    elif etype == 'record_table':
                        element_class = mod_elem.RecordTable
                    elif etype == 'reference':
                        if 'RecordType' not in elem_entry:
                            elem_entry['RecordType'] = self.name
                        element_class = mod_elem.ReferenceElement
                    elif etype == 'element_reference':
                        element_class = mod_elem.ElementReference
                    elif etype == 'text':
                        element_class = mod_elem.DataElement
                    elif etype == 'input':
                        element_class = mod_elem.DataElementInput
                    elif etype == 'dropdown':
                        element_class = mod_elem.DataElementCombo
                    elif etype == 'mulitline':
                        element_class = mod_elem.DataElementMultiline
                    else:
                        raise AttributeError('unknown element type {ETYPE} provided to element {ELEM}'
                                             .format(ETYPE=etype, ELEM=element_name))

                    # Initialize parameter object
                    try:
                        elem_obj = element_class(element_name, elem_entry, parent=self.name)
                    except Exception as e:
                        raise AttributeError('failed to initialize {NAME} element {ELEM} - {ERR}'
                                             .format(NAME=self.name, ELEM=element_name, ERR=e))

                    # Add the parameter to the record
                    self.components.append(elem_obj)
                    self.elements += elem_obj.elements

                    if etype == 'element_reference':
                        ref_elements = elem_obj.references
                        for ref_elem in ref_elements:
                            self._references[ref_elem] = element_name

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
        param = self.fetch_header(self.id_field)
        return param.value

    def record_date(self):
        """
        Convenience method for returning the record date of the record object.
        """
        param = self.fetch_header(self.date_field)
        return param.value

    def initialize(self, data, new: bool = False):
        """
        Initialize record attributes.

        Arguments:
            data (dict): dictionary or pandas series containing record data.

            new (bool): record is newly created [default: False].
        """
        metadata = self.metadata
        headers = self.headers
        components = self.components

        self.new = new

        if isinstance(data, pd.Series):
            record_data = data.to_dict()
        elif isinstance(data, dict):
            record_data = data
        elif isinstance(data, pd.DataFrame):
            if data.shape[0] > 1:
                raise AttributeError('more than one record provided to record class "{TYPE}"'.format(TYPE=self.name))
            elif data.shape[0] < 1:
                raise AttributeError('empty dataframe provided to record class "{TYPE}"'.format(TYPE=self.name))
            else:
                record_data = data.iloc[0]
        else:
            raise AttributeError('unknown object type provided to record class "{TYPE}"'.format(TYPE=self.name))

        if self.id_field not in record_data:
            raise AttributeError('input data is missing required column "{}"'.format(self.id_field))
        if self.date_field not in record_data:
            raise AttributeError('input data is missing required column "{}"'.format(self.date_field))

        logger.info('RecordType {NAME}: initializing record'.format(NAME=self.name))
        logger.debug('RecordType {NAME}: {DATA}'.format(NAME=self.name, DATA=record_data))

        # Set header values from required columns
        for header in headers:
            header_name = header.name

            try:
                value = record_data[header_name]
            except KeyError:
                logger.warning('RecordType {NAME}: input data is missing a value for header "{COL}"'
                               .format(NAME=self.name, COL=header_name))
            else:
                logger.debug('RecordType {NAME}: initializing header "{PARAM}" with value "{VAL}"'
                             .format(NAME=self.name, PARAM=header_name, VAL=value))
                header.value = header.format_value({header.key_lookup('Element'): value})

        # Set metadata parameter values
        for meta_param in metadata:
            param_name = meta_param.name

            try:
                value = record_data[param_name]
            except KeyError:
                logger.warning('RecordType {NAME}: input data is missing a value for metadata field "{COL}"'
                               .format(NAME=self.name, COL=param_name))
            else:
                if not pd.isna(value):
                    logger.debug('RecordType {NAME}: initializing metadata field "{PARAM}" with value "{VAL}"'
                                 .format(NAME=self.name, PARAM=param_name, VAL=value))
                    meta_param.value = meta_param.format_value({meta_param.key_lookup('Element'): value})

        # Set data element values
        for element in components:
            element_name = element.name
            etype = element.etype

            if etype == 'table':  # record element is a simple data table
                elem_cols = list(element.columns)
                table_data = pd.Series(index=elem_cols)
                for elem_col in elem_cols:
                    try:
                        table_data[elem_col] = record_data[elem_col]
                    except KeyError:
                        continue

                element.df = element.df.append(table_data, ignore_index=True)
            elif etype == 'record_table':  # record element is a component record table
                element.load_references(self.record_id())
                pass
            elif etype == 'reference':  # record element is a reference box
                element.load_reference(data)
            else:  # record element is a data element or element reference
                try:
                    value = record_data[element_name]
                except KeyError:
                    logger.warning('RecordType {NAME}: input data is missing a value for data element "{PARAM}"'
                                   .format(NAME=self.name, PARAM=element_name))
                else:
                    if not pd.isna(value):
                        logger.debug('RecordType {NAME}: initializing data element "{PARAM}" with value "{VAL}"'
                                     .format(NAME=self.name, PARAM=element_name, VAL=value))
                        element.value = element.format_value(value)
                    else:
                        logger.debug('RecordType {NAME}: no value set for parameter "{PARAM}"'
                                     .format(NAME=self.name, PARAM=element_name))

    def reset(self, window):
        """
        Reset record attributes.
        """
        self.new = False

        # Reset header values
        for header in self.headers:
            header.reset(window)

        # Reset modifier values
        for modifier in self.metadata:
            modifier.reset(window)

        # Reset components
        for component in self.components:
            component.reset(window)

    def remove_unsaved_ids(self):
        """
        Remove any unsaved IDs associated with the record, including the records own ID.
        """
        record_id = self.record_id()
        record_entry = settings.records.fetch_rule(self.name)

        # Remove unsaved ID if record ID is found in the list of unsaved record IDs
        unsaved_ids = record_entry.get_unsaved_ids()
        if record_id in unsaved_ids:
            record_entry.remove_unsaved_ids(record_ids=[record_id])

        # Remove unsaved components
        for element in self.components:
            etype = element.etype
            if etype != 'record_table':
                continue

            record_type = element.record_type
            if not record_type:
                continue

            record_entry = settings.records.fetch_rule(record_type)

            # Get a list of components added to the component table (i.e. not in the database yet)
            unsaved_ids = record_entry.get_unsaved_ids()
            ids_to_remove = set(unsaved_ids).intersection(element.row_ids())
            record_entry.remove_unsaved_ids(record_ids=ids_to_remove)

    def fetch_header(self, element, by_key: bool = False):
        """
        Fetch a record header element by name or event key.
        """
        if by_key is True:
            element_type = element[1:-1].split('_')[-1]
            element_names = [i.key_lookup(element_type) for i in self.headers]
        else:
            element_names = [i.name for i in self.headers]

        if element in element_names:
            index = element_names.index(element)
            parameter = self.headers[index]
        else:
            raise KeyError('element {ELEM} not found in list of record {NAME} headers'
                           .format(ELEM=element, NAME=self.name))

        return parameter

    def fetch_metadata(self, element, by_key: bool = False):
        """
        Fetch a record modifier by name or event key.
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

    def fetch_component(self, component, by_key: bool = False, by_type: bool = False):
        """
        Fetch a component table by name.
        """
        if by_key is True:
            element_type = component[1:-1].split('_')[-1]
            components = [i.key_lookup(element_type) for i in self.components]
        elif by_type is True:
            components = [i.etype for i in self.components]
        else:
            components = [i.name for i in self.components]

        if component in components:
            index = components.index(component)
            element = self.components[index]
        else:
            raise KeyError('component {ELEM} not found in list of record {NAME} component tables'
                           .format(ELEM=component, NAME=self.name))

        return element

    def run_event(self, window, event, values):
        """
        Perform a record action.
        """
        modifier_elems = [i for param in self.metadata for i in param.elements]
        component_elems = [i for component in self.components for i in component.elements]
        section_bttns = [self.key_lookup('SectionBttn{}'.format(i) for i in range(len(self.sections)))]

        # Expand or collapse the selected section frame
        if event in section_bttns:
            index = section_bttns.index(event)
            self.collapse_expand(window, frame=index)

        # Run a modifier event
        if event in modifier_elems:
            try:
                param = self.fetch_metadata(event, by_key=True)
            except KeyError:
                logger.error('RecordType {NAME}, Record {ID}: unable to find modifier associated with event key {KEY}'
                             .format(NAME=self.name, ID=self.record_id(), KEY=event))
            else:
                param.run_event(window, event, values)

        # Run a component element event
        if event in component_elems:  # record component event
            try:
                element = self.fetch_component(event, by_key=True)
            except KeyError:
                logger.error('RecordType {NAME}, Record {ID}: unable to find record element associated with event key '
                             '{KEY}'.format(NAME=self.name, ID=self.record_id(), KEY=event))
            else:
                element.run_event(window, event, values)
                element.update_display(window, window_values=values)

                elem_name = element.name
                if elem_name in self._references:
                    try:
                        ref_elem = self.fetch_component(self._references[elem_name])
                    except KeyError:
                        logger.error('RecordType {NAME}, Record {ID}: unable to find reference element associated with '
                                     'record element {ELEM}'.format(NAME=self.name, ID=self.record_id(), ELEM=elem_name))
                    else:
                        ref_elem.update_display(window, window_values=values)

        return True

    def as_row(self):
        """
        Format parameter values as a table row.
        """
        is_numeric_dtype = pd.api.types.is_numeric_dtype
        is_string_dtype = pd.api.types.is_string_dtype
        is_bool_dtype = pd.api.types.is_bool_dtype
        is_datetime_dtype = pd.api.types.is_datetime64_any_dtype

        headers = self.headers
        metadata = self.metadata
        components = self.components

        columns = []
        values = []

        # Add header values
        for param in headers:
            columns.append(param.name)
            values.append(param.value())

        # Add modifier values
        for param in metadata:
            columns.append(param.name)
            values.append(param.value())

        # Add parameter values
        for element in components:
            etype = element.etype
            if etype == 'table':  # parameter is a data table object
                df = element.data()
                for column in df.columns.tolist():  # component is header column
                    dtype = df[column].dtype
                    if is_numeric_dtype(dtype) or is_bool_dtype(dtype):
                        col_summary = df[column].sum()
                    elif is_string_dtype(dtype) or is_datetime_dtype(dtype):
                        col_summary = df[column].nunique()
                    else:  # possibly empty dataframe
                        col_summary = 0

                    columns.append(column)
                    values.append(col_summary)
            elif etype == 'record_table':  # parameter is a record table object
                continue
            elif etype == 'reference':  # parameter is a reference box object
                continue
            else:  # parameter is a data element or element reference object
                columns.append(element.name)
                values.append(element.value)

        return pd.Series(values, index=columns)

    def prepare_delete_statements(self, statements: dict = None):
        """
        Prepare statements for deleting the record and child records from the database.
        """
        record_type = self.name
        record_entry = settings.records.fetch_rule(record_type)
        record_id = self.record_id()

        if not statements:
            statements = {}

        logger.debug('Record {ID}: preparing database transaction statements'.format(ID=record_id))

        # Get a list of record IDs that have yet to be saved in the database
        unsaved_ids = settings.get_unsaved_ids()

        # Determine any hard-linked or child records to delete as well
        ref_df['IsParentChild'].fillna(False, inplace=True)
        ref_df[settings.delete_field].fillna(False, inplace=True)
        child_df = ref_df[(ref_df['IsParentChild']) & (~ref_df[settings.delete_field])]

        # Prepare statements to remove any child or hard-linked references
        marked = {}
        for index, row in child_df.iterrows():
            if record_id != row['DocNo']:  # only remove entries where primary record is the parent
                continue

            ref_id = row['RefNo']
            ref_type = row['RefType']
            try:
                unsaved_ref_ids = unsaved_ids[ref_type]
            except KeyError:
                logger.debug('Record {ID}: will not delete dependant record {REFID} from database - reference '
                             'type "{TYPE}" has no representation in the database of unsaved record IDs'
                             .format(ID=record_id, REFID=ref_id, TYPE=ref_type))
                continue

            if ref_id in unsaved_ref_ids:
                logger.debug('Record {ID}: will not delete dependant record {REFID} from database - '
                             'record does not exist in the database yet'.format(ID=record_id, REFID=ref_id))
            else:
                logger.debug('Record {ID}: preparing to delete dependant record {REFID} of type {TYPE}'
                             .format(ID=record_id, REFID=ref_id, TYPE=ref_type))
                try:
                    marked[ref_type].append(ref_id)
                except KeyError:
                    marked[ref_type] = [ref_id]

        for ref_type in marked:
            ref_ids = marked[ref_type]

            ref_entry = settings.records.fetch_rule(ref_type)
            if ref_entry is None:
                msg = 'unable to delete record {ID} dependant records {REFID} - invalid record type "{TYPE}"' \
                    .format(ID=record_id, REFID=ref_ids, TYPE=ref_type)
                logger.error('Record {ID}: {MSG}'.format(ID=record_id, MSG=msg))

                raise AttributeError(msg)

            statements = ref_entry.delete_record(ref_ids, statements=statements)

        # Prepare statement for the removal of the record
        try:
            unsaved_record_ids = unsaved_ids[record_type]
        except KeyError:
            msg = 'unable to delete record {ID} from the database - record of type type "{TYPE}" has no ' \
                  'representation in the database of unsaved record IDs'.format(ID=record_id, TYPE=record_type)
            logger.error('Record {ID}: {MSG}'.format(ID=record_id, MSG=msg))

            raise KeyError(msg)

        if record_id not in unsaved_record_ids:
            logger.info('Record {ID}: preparing to delete the record'.format(ID=record_id))
            statements = record_entry.delete_record(record_id, statements=statements)
        else:
            logger.debug('Record {ID}: will not delete record from database - record does not exist in the database yet'
                         .format(ID=record_id))

        return statements

    def delete(self, statements: dict = None):
        """
        Delete the record and child records from the database.
        """
        record_id = self.record_id()

        # Check if the record contains any child references
        ref_df['IsParentChild'].fillna(False, inplace=True)
        ref_df[settings.delete_field].fillna(False, inplace=True)
        child_df = ref_df[(ref_df['IsParentChild']) & (~ref_df[settings.delete_field])]

        nchild = child_df.shape[0]
        if nchild > 0:  # Record contains child records
            msg = 'Deleting record {ID} will also delete {N} dependant records as well. Would you like to continue ' \
                  'with record deletion?'.format(ID=record_id, N=nchild)
            user_input = mod_win2.popup_confirm(msg)
            if user_input != 'OK':
                return False

        # Prepare deletion statements for the record and any child or hard-linked records
        try:
            statements = self.prepare_delete_statements(statements=statements)
        except Exception as e:
            mod_win2.popup_error(e)
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

        success = user.write_db(sstrings, psets)

        return success

    def prepare_save_statements(self, statements: dict = None):
        """
        Prepare to the statements for saving the record to the database.
        """
        ref_table = settings.reference_lookup

        if not statements:
            statements = {}

        record_entry = self.record_entry
        record_id = self.record_id()
        import_df = self.ref_df

        # Verify that required parameters have values
        for param in self.parameters:
            if param.required is True and param.has_value() is False:
                msg = 'no value provided for the required field {FIELD}'.format(FIELD=param.description)
                logger.warning('Record {ID}: {MSG}'.format(ID=record_id, MSG=msg))

                raise AttributeError(msg)

        # Prepare to save the record
        logger.debug('Record {ID}: preparing database transaction statements'.format(ID=record_id))
        try:
            id_exists = record_entry.confirm_saved(record_id, id_field=self.id_field)
            record_data = self.table_values().to_frame().transpose()
            statements = record_entry.export_table(record_data, id_field=self.id_field, exists=id_exists,
                                                   statements=statements)
        except Exception as e:
            msg = 'failed to save record "{ID}" - {ERR}'.format(ID=record_id, ERR=e)
            logger.exception(msg)

            raise
        else:
            del record_data

        # Prepare to save record references
        for reference in self.references:
            ref_data = reference.as_row()
            ref_id = ref_data['DocNo']  # reference record ID
            logger.debug('Record {ID}: preparing reference statement for reference {REF}'
                         .format(ID=record_id, REF=ref_id))
            if ref_id == record_id:
                logger.error('RecordType {NAME}, Record {ID}: oops ... got the order wrong'
                             .format(NAME=self.name, ID=record_id))

                raise AssertionError('reference IDs were found in the wrong order')

            # Determine if reference entry already exists in the database
            nrow = import_df[(import_df['DocNo'].isin([ref_id, record_id])) &
                             (import_df['RefNo'].isin([ref_id, record_id]))].shape[0]
            comp_columns = ref_data.index.tolist()
            comp_values = tuple(ref_data.values.tolist() + [user.uid, datetime.datetime.now()])
            if nrow > 0:  # reference already exists in the database
                # Prepare the update statement for the existing reference entry in the references table
                # If mutually referenced, deleting one entry will also delete its partner
                comp_columns.extend([settings.editor_code, settings.edit_date])
                update_filters = '(DocNo = ? AND RefNo = ?) OR (DocNo = ? AND RefNo = ?)'
                filter_params = (ref_id, record_id, record_id, ref_id)

                logger.info('RecordType {NAME}, Record {ID}: updating reference {REF}'
                            .format(NAME=self.name, ID=record_id, REF=ref_id))
                statement, params = user.prepare_update_statement(ref_table, comp_columns, comp_values, update_filters,
                                                                  filter_params)
            else:
                # Prepare the insert statement for the existing reference entry to the references table
                comp_columns.extend([settings.creator_code, settings.creation_date])

                logger.info('RecordType {NAME}, Record {ID}: saving reference to {REF}'
                            .format(NAME=self.name, ID=record_id, REF=ref_id))
                statement, params = user.prepare_insert_statement(ref_table, comp_columns, comp_values)

            try:
                statements[statement].append(params)
            except KeyError:
                statements[statement] = [params]

        # Prepare to save record components
        comp_tables = self.components
        for comp_table in comp_tables:
            logger.debug('Record {ID}: preparing statements for component table "{TBL}"'
                         .format(ID=record_id, TBL=comp_table.name))
            comp_df = comp_table.df
            if comp_df.empty:
                continue

            comp_type = comp_table.record_type
            if comp_type is None:
                logger.warning('RecordEntry {NAME}: component table "{TBL}" has no record type assigned'
                               .format(NAME=self.name, TBL=comp_table.name))
                continue

            try:
                import_ids = import_df[(import_df['DocNo'] == record_id) &
                                       (import_df['RefType'] == comp_type)]['RefNo'].tolist()
            except Exception as e:
                logger.warning('RecordEntry {NAME}: failed to extract existing components from component table '
                               '"{TBL}" - {ERR}'.format(NAME=self.name, TBL=comp_table.name, ERR=e))
                continue

            if comp_table.modifiers['add']:  # component records can be created and deleted through parent record
                pc = True  # parent-child relationship
            else:
                pc = False

            # Prepare the reference entries for the components
            for index, row in comp_df.iterrows():
                comp_id = row[comp_table.id_column]
                is_deleted = row[comp_table.deleted_column]
                comp_columns = ['DocNo', 'DocType', 'RefNo', 'RefType', 'RefDate', 'IsParentChild', 'IsDeleted']
                comp_values = (record_id, self.name, comp_id, comp_type, datetime.datetime.now(), pc, is_deleted,
                               datetime.datetime.now(), user.uid)
                if comp_id in import_ids:  # existing reference
                    comp_columns.extend([settings.edit_date, settings.editor_code])
                    update_filters = 'DocNo = ? AND RefNo = ?'
                    filter_params = (record_id, comp_id)
                    statement, params = user.prepare_update_statement(ref_table, comp_columns, comp_values,
                                                                      update_filters,
                                                                      filter_params)
                else:  # new reference
                    if is_deleted:  # don't add reference for new associations that were removed.
                        logger.warning('Record {ID}: new component "{REF}" from component table "{TBL}" was deleted '
                                       'and therefore will not be saved'
                                       .format(ID=record_id, REF=comp_id, TBL=comp_table.name))
                        continue

                    # Prepare the insert statement for the existing reference entry to the references table
                    comp_columns.extend([settings.creation_date, settings.creator_code])

                    logger.info('RecordType {NAME}, Record {ID}: saving reference to "{REF}" from component table '
                                '"{TBL}"'.format(NAME=self.name, ID=record_id, REF=comp_id, TBL=comp_table.name))
                    statement, params = user.prepare_insert_statement(ref_table, comp_columns, comp_values)

                try:
                    statements[statement].append(params)
                except KeyError:
                    statements[statement] = [params]

            # Prepare the record entries for the components
            comp_entry = settings.records.fetch_rule(comp_type)
            #            unsaved_ids = comp_entry.get_unsaved_ids()
            comp_ids = comp_df[comp_table.id_column].values.tolist()
            saved_records = comp_entry.confirm_saved(comp_ids, id_field=comp_table.id_column)

            # Update the delete field
            if pc:  # removed records should be deleted if parent-child is true
                comp_df[self.delete_field] = comp_df[comp_table.deleted_column]

            # Prepare update statements for existing record components
            #            existing_comps = comp_df[~comp_df[comp_table.id_column].isin(unsaved_ids)]
            existing_comps = comp_df[saved_records]
            try:
                statements = comp_entry.export_table(existing_comps, id_field=comp_table.id_column, exists=True,
                                                     statements=statements)
            except Exception as e:
                msg = 'failed to save record "{ID}" - {ERR}'.format(ID=record_id, ERR=e)
                logger.error(msg)

                raise

            # Prepare insert statements for new record components
            #            new_comps = comp_df[comp_df[comp_table.id_column].isin(unsaved_ids)]
            new_comps = comp_df[[not x for x in saved_records]]
            try:
                statements = comp_entry.export_table(new_comps, id_field=comp_table.id_column, exists=False,
                                                     statements=statements)
            except Exception as e:
                msg = 'failed to save record "{ID}" - {ERR}'.format(ID=record_id, ERR=e)
                logger.error(msg)

                raise

        return statements

    def save(self, statements: dict = None):
        """
        Save the record and child records to the database.
        """
        record_id = self.record_id()

        try:
            statements = self.prepare_save_statements(statements=statements)
        except Exception as e:
            mod_win2.popup_error(e)

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

        return success

    def generate_report(self):
        """
        Generate a summary report for the record.
        """
        record_id = self.record_id()
        report_title = self.title

        report_dict = {'title': '{TITLE}: {ID}'.format(TITLE=report_title, ID=record_id),
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
                element = self.fetch_component(element_name)
            except KeyError:
                try:
                    element = self.fetch_header(element_name)
                except KeyError:
                    logger.warning('{NAME}: report element {ELEM} is not a valid record details or header element'
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
                    comp_table = self.fetch_component(component)
                except KeyError:
                    logger.warning('{NAME}, Heading {SEC}: unknown Component "{COMP}" defined in report configuration'
                                   .format(NAME=report_title, SEC=heading, COMP=component))
                    continue

            # Subset table rows based on configured subset rules
            try:
                sub_rule = section['Subset']
            except KeyError:
                subset_df = comp_table.data()
            else:
                try:
                    subset_df = comp_table.subset(sub_rule)
                except (NameError, SyntaxError) as e:
                    logger.error('{NAME}, Heading {SEC}: unable to subset table on rule {SUB} - '
                                 '{ERR}'.format(NAME=report_title, SEC=heading, SUB=sub_rule, ERR=e))
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
                except Exception:
                    logger.exception('{NAME}, Heading {SEC}: failed to format column "{COL}"'
                                     .format(NAME=report_title, SEC=heading, COL=column))

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
            annotations = comp_table.annotate_display(grouped_df.reset_index())
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
                        col_total = comp_table.summarize_column(total_col, df=subset_df)
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

    def update_display(self, window, window_values: dict = None):
        """
        Update the display of the record's elements and components.
        """
        record_id = self.record_id()

        # Update record data elements
        logger.debug('Record {ID}: updating display component tables'.format(ID=record_id))
        for component in self.components:
            component.update_display(window, window_values=window_values)

        # Update records header
        logger.debug('Record {ID}: updating display header elements'.format(ID=record_id))
        for header in self.headers:
            elem_key = header.key_lookup('Element')
            display_value = header.format_display()
            window[elem_key].update(value=display_value)

    def layout(self, win_size: tuple = None, view_only: bool = False, ugroup: list = None):
        """
        Generate a GUI layout for the database record.
        """
        if win_size:
            width, height = win_size
        else:
            width, height = (mod_const.WIN_WIDTH * 0.8, mod_const.WIN_HEIGHT * 0.8)

        sections = self.sections

        # GUI data elements
        editable = True if view_only is False or self.new is True else False
        ugroup = ugroup if ugroup is not None and len(ugroup) > 0 else ['admin']

        # Element parameters
        bg_col = mod_const.ACTION_COL
        text_col = mod_const.TEXT_COL
        inactive_col = mod_const.INACTIVE_COL
        select_col = mod_const.SELECT_TEXT_COL

        bold_font = mod_const.BOLD_HEADER_FONT
        main_font = mod_const.MAIN_FONT

        pad_el = mod_const.ELEM_PAD
        pad_v = mod_const.VERT_PAD
        pad_h = mod_const.HORZ_PAD
        pad_frame = mod_const.FRAME_PAD

        # Record header
        left_layout = []
        right_layout = []
        for param in self.headers:
            if param.justification == 'right':
                right_layout += param.layout(padding=((0, pad_h), 0))
            else:
                left_layout += param.layout(padding=((0, pad_h), 0))

        header_layout = [[sg.Col([left_layout], pad=(0, 0), background_color=bg_col, justification='l',
                                 element_justification='l', expand_x=True),
                          sg.Col([right_layout], background_color=bg_col, justification='r',
                                 element_justification='r')]]

        # Record body layout
        modify_component = True if editable is True and self.level < 1 and self.permissions['components'] in ugroup \
            else False
        modify_reference = True if editable is True and self.level < 1 and self.permissions['references'] in ugroup \
            else False

        section_layouts = []
        for i, section in sections:
            section_parts = sections[section]
            section_title = section_parts['Title']
            section_icon = section_parts['Icon']
            section_elements = section_parts['Elements']

            section_bttn_key = self.key_lookup('SectionBttn{}'.format(i))
            section_layout = [[sg.Image(filename=section_icon, pad=((0, pad_el), 0), background_color=bg_col),
                               sg.Text(section_title, pad=((0, pad_el), 0), background_color=bg_col, font=bold_font),
                               sg.Button('', image_data=mod_const.HIDE_ICON, key=section_bttn_key,
                                         button_color=(text_col, bg_col), border_width=0, visible=True, disabled=False,
                                         metadata={'visible': True, 'disabled': False})]]

            elem_layouts = []
            for element_name in section_elements:
                element = self.fetch_component(element_name)

                etype = element.etype
                if etype == 'reference':
                    edit_element = modify_reference
                elif etype == 'record_table':
                    edit_element = modify_component
                else:
                    edit_element = editable

                elem_layouts.append([element.layout(padding=(0, pad_el), editable=edit_element, overwrite=self.new)])

            section_frame_key = self.key_lookup('SectionFrame{}'.format(i))
            section_layout.append([sg.pin(sg.Col(elem_layouts, key=section_frame_key, background_color=bg_col,
                                                 visible=True, expand_x=True, metadata={'visible': True}))])

            section_layouts.append([sg.Col(section_layout, pad=(0, pad_el), expand_x=True, background_color=bg_col)])

        height_key = self.key_lookup('Height')
        width_key = self.key_lookup('Width')
        details_tab = sg.Tab('{:^40}'.format('Details'),
                             [[sg.Canvas(size=(width, 0), key=width_key, background_color=bg_col)],
                              [sg.Canvas(size=(0, height), key=height_key, background_color=bg_col),
                               sg.Col(section_layouts, pad=(0, pad_v), background_color=bg_col, expand_y=True,
                                      expand_x=True, scrollable=True, vertical_scroll_only=True)]],
                             key=self.key_lookup('DetailsTab'), background_color=bg_col)

        # Create layout for record metadata
        markable = True if self.permissions['mark'] in ugroup and self.new is False \
                           and view_only is False else False
        approvable = True if self.permissions['approve'] in ugroup and self.new is False \
                             and view_only is False else False
        meta_perms = {'MarkedForDeletion': markable, 'Approved': approvable, 'Deleted': False}
        if len(self.metadata) > 0 and not self.new:
            metadata_visible = True
            annotation_layout = []
            for param in self.metadata:
                param_name = param.name
                if param_name in meta_perms:
                    param.editable = meta_perms[param_name]

                annotation_layout.append(param.layout())
        else:  # don't show tab for new records or record w/o configured metadata
            metadata_visible = False
            annotation_layout = [[]]

        info_tab = sg.Tab('{:^40}'.format('Metadata'),
                          [[sg.Col(annotation_layout, pad=(0, pad_v), background_color=bg_col, scrollable=True,
                                   vertical_scroll_only=True, expand_x=True, expand_y=True)]],
                          key=self.key_lookup('InfoTab'), background_color=bg_col, visible=metadata_visible)

        main_layout = [[sg.TabGroup([[details_tab, info_tab]], key=self.key_lookup('TG'),
                                    background_color=inactive_col, tab_background_color=inactive_col,
                                    selected_background_color=bg_col, selected_title_color=select_col,
                                    title_color=text_col, border_width=0, tab_location='topleft', font=main_font)]]

        # Pane elements must be columns
        layout = [[sg.Col(header_layout, pad=(pad_frame, pad_v), background_color=bg_col, expand_x=True)],
                  [sg.Col(main_layout, pad=(pad_frame, (0, pad_frame)), background_color=bg_col, expand_x=True)]]

        return layout

    def resize(self, window, win_size: tuple = None):
        """
        Resize the record elements.
        """
        if win_size is not None:
            width, height = win_size
        else:
            width, height = window.size

        logger.debug('Record {ID}: resizing display to {W}, {H}'.format(ID=self.record_id(), W=width, H=height))

        # Expand the frame width and height
        width_key = self.key_lookup('Width')
        window.bind("<Configure>", window[width_key].Widget.config(width=int(width - 40)))

        height_key = self.key_lookup('Height')
        window.bind("<Configure>", window[height_key].Widget.config(height=int(height)))

        # Expand the size of multiline parameters
        for element in self.components:
            etype = element.etype
            if etype == 'multiline':  # multiline data element
                param_size = (int((width - width % 9) / 9) - int((64 - 64 % 9) / 9), None)
            elif etype in ('table', 'record_table'):  # data tables
                param_size = (width - 64, int(height * 0.2))
            elif etype == 'reference':  # reference box element
                param_size = (width - 62, 40)
            else:
                param_size = None

            element.resize(window, size=param_size)

    def collapse_expand(self, window, frame: int = 0):
        """
        Hide/unhide record frames.
        """
        hide_key = self.key_lookup('SectionBttn{}'.format(frame))
        frame_key = self.key_lookup('SectionFrame{}'.format(frame))

        if window[frame_key].metadata['visible'] is True:  # already visible, so want to collapse the frame
            logger.debug('RecordType {NAME}, Record {ID}: collapsing {FRAME} frame'
                         .format(NAME=self.name, ID=self.record_id(), FRAME=frame))
            window[hide_key].update(image_data=mod_const.UNHIDE_ICON)
            window[frame_key].update(visible=False)

            window[frame_key].metadata['visible'] = False
        else:  # not visible yet, so want to expand the frame
            logger.debug('RecordType {NAME}, Record {ID}: expanding {FRAME} frame'
                         .format(NAME=self.name, ID=self.record_id(), FRAME=frame))
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


def create_record(record_entry, record_data, level: int = 1):
    """
    Create a new database record.
    """
    record = DatabaseRecord(record_entry, level=level)
    record.initialize(record_data, new=True)

    return record


def import_references(record_id):
    """
    Import record references.
    """
    # Define query parameters
    ref_table = settings.reference_lookup
    columns = ['DocNo', 'RefNo', 'RefDate', 'DocType', 'RefType', 'IsDeleted', 'Warnings', 'IsParentChild']
    filters = ('{COL1} = ? OR {COL2} = ?'.format(COL1='DocNo', COL2='RefNo'), (record_id, record_id))

    # Import reference entries related to record_id
    import_df = user.read_db(*user.prepare_query_statement(ref_table, columns=columns, filter_rules=filters),
                             prog_db=True)

    return import_df
