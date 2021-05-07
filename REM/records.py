"""
REM records classes and functions. Includes audit records and account records.
"""

import datetime
import dateutil
import pandas as pd
import PySimpleGUI as sg
from random import randint
import sys

import REM.constants as mod_const
import REM.database as mod_db
import REM.elements as mod_elem
import REM.parameters as mod_param
import REM.secondary as mod_win2
#from REM.settings import settings, user
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

        import_ids = import_df.iloc[:, 0].values.tolist()
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
        filters = mod_db.format_import_filters(self.import_rules)
        table_statement = mod_db.format_tables(self.import_rules)
        columns = mod_db.format_import_columns(self.import_rules)
        id_col = mod_db.get_import_column(self.import_rules, id_field)

        # Query existing database entries
        import_df = pd.DataFrame()
        for i in range(0, len(record_ids), 1000):  # split into sets of 1000 to prevent max parameter errors in SQL
            sub_ids = record_ids[i: i + 1000]
            filter_clause = '{COL} IN ({VALS})'.format(COL=id_col, VALS=','.join(['?' for _ in sub_ids]))
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

    def export_table(self, df, id_field: str = 'RecordID', id_exists: bool = False, statements: dict = {},
                     export_columns: bool = True):
        import_rules = self.import_rules

        if not isinstance(df, pd.DataFrame):
            raise ValueError('df must be a DataFrame or Series')
        else:
            columns = df.columns.values.tolist()

        if df.empty:
            return statements

        if id_exists:  # record already exists in the database
            # Add edit details to records table
            df[settings.editor_code] = user.uid
            df[settings.edit_date] = datetime.datetime.now().strftime(settings.date_format)
        else:  # new record was created
            # Add record creation details to records table
            df[settings.creator_code] = user.uid
            df[settings.creation_date] = datetime.datetime.now().strftime(settings.date_format)

        # Prepare transaction for each export table containing fields comprising the record
        for table in import_rules:
            table_entry = import_rules[table]

            if export_columns:
                references = {j: i for i, j in table_entry['Columns'].items()}
            else:
                references = {i: i for i in table_entry['Columns']}

            try:
                id_col = references[id_field]
            except KeyError:
                logger.error('missing ID column {COL} from record import columns {COLS}'
                             .format(COL=id_field, COLS=list(references.keys())))

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

    def delete_record(self, record_ids, statements: dict = {}, id_field: str = 'RecordID'):
        """
        Delete a record from the database.
        """
        ref_table = settings.reference_lookup
        delete_code = settings.delete_field

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

    def import_record_ids(self, record_date: datetime.datetime = None, id_field: str = 'RecordID'):
        """
        Import existing record IDs.
        """
        # Prepare query parameters
        table_statement = mod_db.format_tables(self.import_rules)
        id_col = mod_db.get_import_column(self.import_rules, id_field)

        # Define query statement
#        params = None
        if record_date is not None:
            # Search for database records with date within the same month
            try:
                first_day = record_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                last_day = datetime.datetime(record_date.year + record_date.month // 12, record_date.month % 12 + 1,
                                             1) - datetime.timedelta(1)
            except AttributeError:
                filters = None
            else:
                params = (first_day, last_day)
                filters = ('{DATE} BETWEEN ? AND ?'.format(DATE=settings.date_field), params)
        else:
            filters = None
        import_rows = user.read_db(*user.prepare_query_statement(table_statement, columns=id_col, filter_rules=filters,
                                                                 order=id_col), prog_db=True)

        # Connect to database
        try:
            id_list = import_rows.iloc[:, 0]
        except IndexError:
            logger.info('no existing record IDs found')
            id_list = []
        except Exception as e:
            logger.error('failed to import saved record ids - {ERR}'.format(ERR=e))
            logger.error(import_rows)
            raise

        return id_list

    def create_id(self, record_date, offset: int = 0):
        """
        Create a new record ID.
        """
        logger.info('creating a new ID for the record')
        relativedelta = dateutil.relativedelta.relativedelta
        strptime = datetime.datetime.strptime

        id_code = self.id_code
        unsaved_ids = self.get_unsaved_ids()
        if unsaved_ids is None:
            return None

        # Format the date component of the new ID
        try:
            id_date = (record_date + relativedelta(years=+offset)).strftime(settings.format_date_str(date_str='YYMM'))
        except Exception as e:
            logger.debug(e)
            id_date = (strptime(record_date.strftime('%Y-%m-%d %H:%M:%S'), '%Y-%m-%d %H:%M:%S')
                       + relativedelta(years=+offset)).strftime(settings.format_date_str(date_str='YYMM'))

        logger.debug('RecordEntry {NAME}: new ID has date component {COMP}'.format(NAME=self.name, COMP=id_date))

        # Search list of unsaved IDs occurring within the current date cycle
        logger.debug('RecordEntry {NAME}: searching for unsaved record IDs with date component {DATE}'
                     .format(NAME=self.name, DATE=id_date))
        prev_ids = []
        for unsaved_id in unsaved_ids:
            prev_date = self._id_date_component(unsaved_id)
            if prev_date == id_date:
                prev_ids.append(unsaved_id)

        logger.debug('RecordEntry {NAME}: found {NUM} unsaved records with date component {DATE}'
                     .format(NAME=self.name, NUM=len(prev_ids), DATE=id_date))

        # Search list of saved IDs occurring within the current date cycle
        if len(prev_ids) < 1:
            logger.debug('RecordEntry {NAME}: searching for database record IDs with date component {DATE}'
                         .format(NAME=self.name, DATE=id_date))

            # Search list of saved IDs occurring within the current date cycle for the last created ID
            db_ids = self._import_saved_ids([record_date])
            for db_id in db_ids:
                prev_date = self._id_date_component(db_id)
                if prev_date == id_date:
                    prev_ids.append(db_id)

            logger.debug('RecordEntry {NAME}: found {NUM} database records with date component {DATE}'
                         .format(NAME=self.name, NUM=len(prev_ids), DATE=id_date))

        # Get the number of the last ID used in the current date cycle
        if len(prev_ids) > 0:
            last_id = sorted(prev_ids)[-1]
        else:
            last_id = None

        # Create the new ID
        if last_id:
            logger.info('RecordEntry {NAME}: last ID encountered is {ID}'.format(NAME=self.name, ID=last_id))
            try:
                last_num = int(last_id.split('-')[-1])
            except ValueError:
                msg = 'Record {NAME}: incorrect formatting for previous ID {ID}'.format(NAME=self.name, ID=last_id)
                logger.error(msg)
                return None
        else:
            logger.info('RecordEntry {NAME}: no previous IDs found for date {DATE} - starting new iteration at 1'
                        .format(NAME=self.name, DATE=id_date))
            last_num = 0
        record_id = '{CODE}{DATE}-{NUM}'.format(CODE=id_code, DATE=id_date, NUM=str(last_num + 1).zfill(4))

        logger.info('RecordEntry {NAME}: new record ID is {ID}'.format(NAME=self.name, ID=record_id))

        # Add ID to the list of unsaved IDs
        success = self.add_unsaved_ids(record_id)
        if success is False:
            return None

        return record_id

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
            print(import_rows)
            raise
        else:
            record_ids = id_list.values.tolist()

        return record_ids

    def create_record_ids(self, record_dates, offset: int = 0):
        """
        Create a new set of record IDs.
        """
        relativedelta = dateutil.relativedelta.relativedelta
        strptime = datetime.datetime.strptime

        record_type = self.name
        id_code = self.id_code

        if not isinstance(record_dates, list):
            logger.error('failed to create IDs for the record entries of type {TYPE} - record_dates must be formatted '
                         'as a list'.format(TYPE=record_type))
            return None

        logger.info('creating {N} new record IDs for records of type "{TYPE}"'
                    .format(N=len(record_dates), TYPE=record_type))

        # Get list of unsaved record IDs of the same record type
        unsaved_ids = self.get_unsaved_ids(record_type)
        if unsaved_ids is None:
            logger.error('failed to create IDs for the record entries of type {TYPE} - unable to obtain a list of '
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
                id_date = (record_date + relativedelta(years=+offset)).strftime(settings.format_date_str(date_str='YYMM'))
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
            logger.error('failed to create IDs for the record entries of type {TYPE} - unable to add record IDs to '
                         'the list unsaved record IDs'.format(TYPE=record_type))
            return None

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
        if internal_only:
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

            return None
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


class CustomRecordEntry:
    """
    Custom record entry object.
    """

    def __init__(self, entry):
        """
        Arguments:

            entry (dict): dictionary of parameters for the custom record entry.
        """
        self.name = 'CustomRecord'
        self.group = 'custom'

        # Record layout configuration
        try:
            self.record_layout = entry['RecordLayout']
        except KeyError:
            raise AttributeError('missing required parameter "RecordLayout"')

#        self.ids = []

    def remove_unsaved_id(self, record_id):
        """
        Remove record ID from the list of unsaved IDs
        """
        return True
#        try:
#            self.ids.remove(record_id)
#        except ValueError:
#            print('Warning: RecordEntry {NAME}: record {ID} was not found in the list of unsaved {TYPE} record IDs'
#                  .format(NAME=self.name, ID=record_id, TYPE=self.name))
#            success = False
#        else:
#            print('Info: RecordEntry {NAME}: removing unsaved record ID {ID} from the list of unsaved records'
#                  .format(NAME=self.name, ID=record_id))
#            success = True
#
#        return success

    def import_references(self, *args, **kwargs):
        """
        Dummy method.
        """
        return pd.DataFrame()


class DatabaseRecord:
    """
    Generic database record account.

    Attributes:
        name (str): name of the configured record entry.

        id (int): record element number.

        elements (list): list of GUI element keys.

        title (str): record display title.

        permissions (dict): dictionary mapping permission rules to permission groups

        parameters (list): list of data and other GUI elements used to display information about the record.

        references (list): list of reference records.

        components (list): list of record components.
    """

    def __init__(self, record_entry, level: int = 0, record_layout: dict = None):
        """
        Arguments:
            record_entry (class): configuration entry for the record.

            level (int): depth at which record was opened [Default: 0].
        """
        approved_record_types = settings.records.get_approved_groups()

        # Reserved fields
        self.id_field = 'RecordID'
        self.date_field = 'RecordDate'
        self.delete_field = 'Deleted'

        # Record properties
        self.record_entry = record_entry
        self.new = False
        self.level = level

        self.name = record_entry.name

        self.id = randint(0, 1000000000)
        self.elements = ['-{NAME}_{ID}_{ELEM}-'.format(NAME=self.name, ID=self.id, ELEM=i) for i in
                         ['ReferencesButton', 'ReferencesFrame', 'ComponentsButton', 'ComponentsFrame',
                          'Height', 'Width', 'DetailsTab', 'InfoTab', 'TG', 'FrameHeight', 'FrameWidth']]

        entry = record_entry.record_layout if record_layout is None else record_layout

        # User permissions when accessing record
        try:
            permissions = entry['Permissions']
        except KeyError:
            self.permissions = {'edit': 'admin', 'delete': 'admin', 'mark': 'admin', 'references': 'admin',
                                'components': 'admin', 'approve': 'admin'}
        else:
            self.permissions = {'edit': permissions.get('Edit', 'admin'),
                                'delete': permissions.get('Delete', 'admin'),
                                'mark': permissions.get('MarkForDeletion', 'admin'),
                                'references': permissions.get('ModifyReferences', 'admin'),
                                'components': permissions.get('ModifyComponents', 'admin'),
                                'approve': permissions.get('Approve', 'admin')}

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
                elif param_layout == 'date':
                    param_class = mod_param.DataParameterDate
                elif param_layout == 'date_range':
                    param_class = mod_param.DataParameterDateRange
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
                elif param_layout == 'date':
                    param_class = mod_param.DataParameterDate
                elif param_layout == 'date_range':
                    param_class = mod_param.DataParameterDateRange
                elif param_layout == 'checkbox':
                    param_class = mod_param.DataParameterCheckbox
                else:
                    raise AttributeError('unknown type {TYPE} provided to record header {PARAM}'
                                         .format(TYPE=param_layout, PARAM=param_name))

                param = param_class(param_name, param_entry)

                self.metadata.append(param)
                self.elements += param.elements

        # Required record elements
        self.parameters = []
        try:
            details = entry['Details']
        except KeyError:
            raise AttributeError('missing required configuration parameter "Details"')
        else:
            try:
                parameters = details['Elements']
            except KeyError:
                raise AttributeError('missing required Details parameter "Elements"')

            for param in parameters:
                param_entry = parameters[param]
                try:
                    param_type = param_entry['ElementType']
                except KeyError:
                    raise AttributeError('"Details" element {PARAM} is missing the required field "ElementType"'
                                         .format(PARAM=param))

                # Set the object type of the record parameter.
                if param_type == 'table':
                    element_class = mod_elem.TableElement

                    # Format entry for table
                    description = param_entry.get('Description', param)
                    try:
                        param_entry = param_entry['Options']
                    except KeyError:
                        raise AttributeError('the "Options" parameter is required for table element {PARAM}'
                                             .format(PARAM=param))
                    param_entry['Title'] = description
                else:
                    element_class = mod_elem.DataElement

                # Initialize parameter object
                try:
                    param_obj = element_class(param, param_entry, parent=self.name)
                except Exception as e:
                    raise AttributeError('failed to initialize {NAME} record {ID}, element {PARAM} - {ERR}'
                                         .format(NAME=self.name, ID=self.record_id, PARAM=param, ERR=e))

                # Add the parameter to the record
                self.parameters.append(param_obj)
                self.elements += param_obj.elements

        self.references = []
        self.reference_types = []
        try:
            ref_entry = entry['References']
        except KeyError:
            logger.warning('no reference record types configured for {NAME}'.format(NAME=self.name))
        else:
            try:
                ref_elements = ref_entry['Elements']
            except KeyError:
                logger.warning('missing required References parameter "Elements"'.format(NAME=self.name))
            else:
                for ref_element in ref_elements:
                    if ref_element not in [i.name for i in settings.records.rules]:
                        logger.warning('RecordEntry {NAME}: reference {TYPE} must be a pre-configured '
                                       'record type'.format(NAME=self.name, TYPE=ref_element))
                    else:
                        self.reference_types.append(ref_element)

        self.components = []
        self.component_types = []
        try:
            comp_entry = entry['Components']
        except KeyError:
            logger.warning('RecordEntry: no component record types configured'.format(NAME=self.name))
        else:
            try:
                comp_elements = comp_entry['Elements']
            except KeyError:
                logger.warning('RecordEntry {NAME}: missing required configuration References parameter "Elements"'
                               .format(NAME=self.name))
            else:
                for comp_element in comp_elements:
                    if comp_element not in approved_record_types:
                        logger.warning('RecordEntry {NAME}: component table {TBL} must be an acceptable '
                                       'record type'.format(NAME=self.name, TBL=comp_element))
                        continue
                    table_entry = comp_elements[comp_element]
                    comp_table = mod_elem.TableElement(comp_element, table_entry, parent=self.name)
                    self.component_types.append(comp_table.record_type)
                    self.components.append(comp_table)
                    self.elements += comp_table.elements

        self.ref_df = pd.DataFrame(
            columns=['DocNo', 'RefNo', 'RefDate', 'DocType', 'RefType', 'IsDeleted', 'IsParentChild'])

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

    def initialize(self, data, new: bool = False, references: pd.DataFrame = None):
        """
        Initialize record attributes.

        Arguments:
            data (dict): dictionary or pandas series containing record data.

            new (bool): record is newly created [default: False].

            references (DataFrame): dataframe of references and components [default: load from database].
        """
        headers = self.headers
        parameters = self.parameters
        modifiers = self.metadata
        comp_types = self.component_types
        ref_types = self.reference_types

        self.new = new
        record_entry = self.record_entry

        if isinstance(data, pd.Series):
            record_data = data.to_dict()
        elif isinstance(data, dict):
            record_data = data
        elif isinstance(data, pd.DataFrame):
            if data.shape[0] > 1:
                raise AttributeError('more than one record provided to record class {TYPE}'.format(TYPE=self.name))
            elif data.shape[0] < 1:
                raise AttributeError('empty dataframe provided to record class {TYPE}'.format(TYPE=self.name))
            else:
                record_data = data.iloc[0]
        else:
            raise AttributeError('unknown object type provided to record class {TYPE}'.format(TYPE=self.name))

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
                logger.warning('RecordType {NAME}: input data is missing a value for header {COL}'
                               .format(NAME=self.name, COL=header_name))
            else:
                logger.debug('RecordType {NAME}: initializing header {PARAM} with value {VAL}'
                             .format(NAME=self.name, PARAM=header_name, VAL=value))
                header.value = header.format_value({header.key_lookup('Element'): value})

        # Set modifier values
        if new is True:
            self.metadata = []
        else:
            for modifier in modifiers:
                modifier_name = modifier.name

                try:
                    value = record_data[modifier_name]
                except KeyError:
                    logger.warning('RecordType {NAME}: input data is missing a value for modifier {COL}'
                                   .format(NAME=self.name, COL=modifier_name))
                else:
                    logger.debug('RecordType {NAME}: initializing modifier {PARAM} with value {VAL}'
                                 .format(NAME=self.name, PARAM=modifier_name, VAL=value))
                    modifier.value = modifier.format_value({modifier.key_lookup('Element'): value})

        # Set data element values
        for param in parameters:
            param_name = param.name
            param_type = param.etype

            if param_type == 'table':  # parameter is a data table
                param_cols = list(param.columns)
                table_data = pd.Series(index=param_cols)
                for param_col in param_cols:
                    try:
                        table_data[param_col] = record_data[param_col]
                    except KeyError:
                        continue

                param.df = param.df.append(table_data, ignore_index=True)
            else:  # parameter is a data element
                try:
                    value = record_data[param_name]
                except KeyError:
                    logger.warning('RecordType {NAME}: input data is missing a value for data element {PARAM}'
                                   .format(NAME=self.name, PARAM=param_name))
                else:
                    if not pd.isna(value):
                        logger.debug('RecordType {NAME}: initializing data element {PARAM} with value {VAL}'
                                     .format(NAME=self.name, PARAM=param_name, VAL=value))
                        param.value = param.format_value(value)
                    else:
                        logger.debug('RecordType {NAME}: no value set for parameter {PARAM}'
                                     .format(NAME=self.name, PARAM=param_name))

        # Import components and references for existing records
        record_id = self.record_id()
        logger.info('RecordType {NAME}: initialized record has ID {ID}'.format(NAME=self.name, ID=record_id))
        if record_id is not None and (references is not None or record_entry is not None):
            logger.info('RecordType {NAME}: importing references and components'.format(NAME=self.name))

            component_ids = {}
            ref_df = references if references is not None else import_references(record_id)
            for index, row in ref_df.iterrows():
                if row['DocNo'] != record_id and row['RefNo'] != record_id:
                    continue

                try:
                    deleted = bool(int(row['IsDeleted']))
                except (KeyError, ValueError):
                    deleted = False

                if deleted is True:  # don't include deleted record associations
                    continue

                doctype = row['DocType']
                reftype = row['RefType']

                # Store imported references as references box objects
                if doctype in ref_types and reftype == self.name:
                    ref_id = row['DocNo']
                    if ref_id == record_id:
                        continue
                    logger.debug('RecordType {NAME}: adding reference record {ID} with record type {TYPE}'
                                 .format(NAME=self.name, ID=ref_id, TYPE=doctype))

                    try:
                        ref_box = mod_elem.ReferenceElement(doctype, row, parent=self.name, inverted=True)
                    except Exception as e:
                        logger.warning('RecordType {NAME}: failed to add reference {ID} to list of references - {ERR}'
                                       .format(NAME=self.name, ID=ref_id, ERR=e))
                        continue
                    else:
                        self.references.append(ref_box)
                        self.elements += ref_box.elements

                elif doctype == self.name and reftype in ref_types:
                    ref_id = row['RefNo']
                    if ref_id == record_id:
                        continue
                    logger.debug('RecordType {NAME}: adding reference record {ID} with record type {TYPE}'
                                 .format(NAME=self.name, ID=ref_id, TYPE=reftype))

                    try:
                        ref_box = mod_elem.ReferenceElement(doctype, row, parent=self.name, inverted=False)
                    except Exception as e:
                        logger.warning('RecordType {NAME}: failed to add reference {ID} to list of references - {ERR}'
                                       .format(NAME=self.name, ID=ref_id, ERR=e))
                        continue
                    else:
                        self.references.append(ref_box)
                        self.elements += ref_box.elements

                # Store imported components as table rows
                elif doctype == self.name and reftype in comp_types:
                    ref_id = row['RefNo']
                    logger.debug('RecordType {NAME}: adding component record {ID} with record type {TYPE}'
                                 .format(NAME=self.name, ID=ref_id, TYPE=reftype))
                    # Fetch the relevant components table
                    #                    comp_table = self.fetch_component(reftype, by_type=True)

                    # Append record to the components table
                    #                    comp_table.df = comp_table.import_row(ref_id)

                    try:
                        component_ids[reftype].append(ref_id)
                    except KeyError:
                        component_ids[reftype] = [ref_id]

            for comp_type in component_ids:
                import_ids = component_ids[comp_type]

                comp_table = self.fetch_component(comp_type, by_type=True)
                record_entry = settings.records.fetch_rule(comp_table.record_type)
                comp_table.df = comp_table.append(record_entry.load_record_data(import_ids))
                pd.set_option('display.max_columns', None)
                print(comp_table.name)
                print(comp_table.df)

            self.ref_df = self.ref_df.append(ref_df, ignore_index=True)

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

        # Reset data element values
        for param in self.parameters:
            param.reset(window)

        # Reset components
        for comp_table in self.components:
            comp_table.reset(window)

        # Reset references
        self.references = []

        self.ref_df = pd.DataFrame(
            columns=['DocNo', 'RefNo', 'RefDate', 'DocType', 'RefType', 'IsDeleted', 'IsParentChild'])

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

    def fetch_element(self, element, by_key: bool = False):
        """
        Fetch a record data element by name or event key.
        """
        if by_key is True:
            element_type = element[1:-1].split('_')[-1]
            element_names = [i.key_lookup(element_type) for i in self.parameters]
        else:
            element_names = [i.name for i in self.parameters]

        if element in element_names:
            index = element_names.index(element)
            parameter = self.parameters[index]
        else:
            raise KeyError('element {ELEM} not found in list of record {NAME} elements'
                           .format(ELEM=element, NAME=self.name))

        return parameter

    def fetch_modifier(self, element, by_key: bool = False):
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

    def fetch_reference(self, reference, by_key: bool = False, by_id: bool = False):
        """
        Display a reference record in a new window.
        """
        if by_key is True:
            element_type = reference[1:-1].split('_')[-1]
            references = [i.key_lookup(element_type) for i in self.references]
        elif by_id is True:
            references = [i.record_id() for i in self.references]
        else:
            references = [i.name for i in self.references]

        if reference in references:
            index = references.index(reference)
            ref_elem = self.references[index]
        else:
            raise KeyError('reference {ELEM} not found in list of record {NAME} references'
                           .format(ELEM=reference, NAME=self.name))

        return ref_elem

    def fetch_component(self, component, by_key: bool = False, by_type: bool = False):
        """
        Fetch a component table by name.
        """
        if by_key is True:
            element_type = component[1:-1].split('_')[-1]
            components = [i.key_lookup(element_type) for i in self.components]
        elif by_type is True:
            components = [i.record_type for i in self.components]
        else:
            components = [i.name for i in self.components]

        if component in components:
            index = components.index(component)
            comp_tbl = self.components[index]
        else:
            raise KeyError('component {ELEM} not found in list of record {NAME} component tables'
                           .format(ELEM=component, NAME=self.name))

        return comp_tbl

    def get_original_components(self, table):
        """
        Return a list of record IDs of the original records imported from the database.
        """
        record_id = self.record_id()

        try:
            comp_table = self.fetch_component(table)
        except KeyError:
            logger.warning('RecordEntry {NAME}: component table {TBL} not found'.format(NAME=self.name, TBL=table))
            return []

        import_df = self.ref_df
        if import_df.empty:
            return []

        comp_type = comp_table.record_type
        if comp_type is None:
            logger.warning('RecordEntry {NAME}: component table {TBL} has no record type assigned'
                           .format(NAME=self.name, TBL=comp_table.name))
            return []

        try:
            orig_ids = import_df[(import_df['DocNo'] == record_id) &
                                 (import_df['RefType'] == comp_type)]['RefNo'].tolist()
        except Exception as e:
            logger.warning('RecordEntry {NAME}: failed to extract existing components from component table '
                           '{TBL} - {ERR}'.format(NAME=self.name, TBL=comp_table.name, ERR=e))
            orig_ids = []

        return orig_ids

    def get_added_components(self, table):
        """
        Return a list of record IDs added to a component table post-record initialization.
        """
        try:
            comp_table = self.fetch_component(table)
        except KeyError:
            logger.warning('RecordEntry {NAME}: component table {TBL} not found'.format(NAME=self.name, TBL=table))
            return []

        orig_ids = self.get_original_components(table)
        current_ids = comp_table.df[comp_table.id_column].tolist()
        added_ids = list(set(current_ids).difference(set(orig_ids)))

        return added_ids

    def get_deleted_components(self, table):
        """
        Return a list of original record IDs deleted from component table post-record initialization.
        """
        try:
            comp_table = self.fetch_component(table)
        except KeyError:
            logger.warning('RecordEntry {NAME}: component table {TBL} not found'.format(NAME=self.name, TBL=table))
            return []

        orig_ids = self.get_original_components(table)
        current_ids = comp_table.df[comp_table.id_column].tolist()
        deleted_ids = list(set(orig_ids).difference(set(current_ids)))

        return deleted_ids

    def table_values(self):
        """
        Format parameter values as a table row.
        """
        is_numeric_dtype = pd.api.types.is_numeric_dtype
        is_string_dtype = pd.api.types.is_string_dtype
        is_bool_dtype = pd.api.types.is_bool_dtype
        is_datetime_dtype = pd.api.types.is_datetime64_any_dtype

        headers = self.headers
        parameters = self.parameters
        modifiers = self.metadata

        columns = []
        values = []

        # Add header values
        for header in headers:
            columns.append(header.name)
            values.append(header.value)

        # Add modifier values
        for modifier in modifiers:
            columns.append(modifier.name)
            values.append(modifier.value)

        # Add parameter values
        for param in parameters:
            param_type = param.etype
            if param_type == 'table':  # parameter is a data table object
                df = param.df
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
            else:  # parameter is a data element object
                columns.append(param.name)
                values.append(param.value)

        return pd.Series(values, index=columns)

    def delete(self, statements: dict = {}):
        """
        Delete the record and child records from the database.
        """
        record_entry = self.record_entry
        record_type = record_entry.name
        record_id = self.record_id()
        ref_df = self.ref_df

        # Get a list of record IDs that have yet to be saved in the database
        unsaved_ids = settings.get_unsaved_ids()

        # Determine associations to delete as well
        ref_df['IsParentChild'].fillna(False, inplace=True)
        child_df = ref_df[ref_df['IsParentChild']]

        logger.info('preparing to delete record {ID} and any child records'.format(ID=record_id))

        # Prepare statements for removal of record and associations
        nchild = child_df.shape[0]
        marked = {}
        if nchild > 0:  # Record contains child records
            msg = 'Deleting record {ID} will also delete {N} dependant records as well. Would you like to continue ' \
                  'with record deletion?'.format(ID=record_id, N=nchild)
            user_input = mod_win2.popup_confirm(msg)
            if user_input == 'OK':
                # Prepare statement to remove child references
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
                        logger.debug(
                            'Record {ID}: will not delete dependant record {REFID} from database - '
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
                        msg = 'Record {ID}: unable to delete dependant records {REFID} - invalid record type "{TYPE}"'\
                            .format(ID=record_id, REFID=ref_ids, TYPE=ref_type)
                        logger.error(msg)
                        mod_win2.popup_error(msg)
                        continue

                    statements = ref_entry.delete_record(ref_ids, statements=statements)
            else:
                return False

        # Prepare statement for the removal of the record
        try:
            unsaved_record_ids = unsaved_ids[record_type]
        except KeyError:
            logger.error('Record {ID}: unable to delete record from the database - record of type '
                         'type "{TYPE}" has no representation in the database of unsaved record IDs'
                         .format(ID=record_id, TYPE=record_type))
            return False

        if record_id not in unsaved_record_ids:
            logger.info('Record {ID}: preparing to delete the record'.format(ID=record_id))
            statements = record_entry.delete_record(record_id, statements=statements)
        else:
            logger.debug('Record {ID}: will not delete record from database - record does not exist in the database yet'
                         .format(ID=record_id))

        sstrings = []
        psets = []
        for i, j in statements.items():
            sstrings.append(i)
            psets.append(j)

        success = user.write_db(sstrings, psets)

        return success

    def save(self, statements: dict = {}):
        """
        Save the record and child records to the database.
        """
        ref_table = settings.reference_lookup

        record_entry = self.record_entry
        record_id = self.record_id()
        import_df = self.ref_df

        # Verify that required parameters have values
        for param in self.parameters:
            if param.required is True and param.value_set() is False:
                msg = 'Record {ID}: no value provided for the required field {FIELD}' \
                    .format(ID=record_id, FIELD=param.description)
                logger.warning(msg)
                mod_win2.popup_error(msg)

                return False

        # Prepare to save the record
        logger.info('Record {ID}: preparing to save record and record components'.format(ID=record_id))

        try:
            id_exists = record_entry.confirm_saved(record_id, id_field=self.id_field)
            record_data = self.table_values().to_frame().transpose()
            statements = record_entry.export_table(record_data, statements=statements, id_field=self.id_field,
                                                   id_exists=id_exists)
        except Exception as e:
            msg = 'failed to save record {ID} - {ERR}'.format(ID=record_id, ERR=e)
            logger.exception(msg)
            return False
        else:
            del record_data

        # Prepare to save record references
        for reference in self.references:
            ref_data = reference.as_table()
            ref_id = ref_data['DocNo']  # reference record ID
            if ref_id == record_id:
                logger.warning('RecordType {NAME}, Record {ID}: oops ... got the order wrong'
                               .format(NAME=self.name, ID=record_id))
                return False

            # Determine if reference entry already exists in the database
            nrow = import_df[
                (import_df['DocNo'].isin([ref_id, record_id])) & (import_df['RefNo'].isin([ref_id, record_id]))].shape[
                0]
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

            if comp_table.actions['add']:  # component records can be created and deleted through parent record
                pc = True  # parent-child relationship
            else:
                pc = False

            # Prepare the reference entries for the components
            comp_df = comp_table.df
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
                        continue

                    # Prepare the insert statement for the existing reference entry to the references table
                    comp_columns.extend([settings.creation_date, settings.creator_code])

                    logger.info('RecordType {NAME}, Record {ID}: saving reference to {REF}'
                                .format(NAME=self.name, ID=record_id, REF=comp_id))
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
            print(saved_records)
            existing_comps = comp_df[saved_records]
            try:
                statements = comp_entry.export_table(existing_comps, statements=statements,
                                                     id_field=comp_table.id_column, id_exists=True)
            except Exception as e:
                msg = 'failed to save record {ID} - {ERR}'.format(ID=record_id, ERR=e)
                logger.error(msg)
                return False

            # Prepare insert statements for new record components
#            new_comps = comp_df[comp_df[comp_table.id_column].isin(unsaved_ids)]
            new_comps = comp_df[[not x for x in saved_records]]
            try:
                statements = comp_entry.export_table(new_comps, statements=statements,
                                                     id_field=comp_table.id_column, id_exists=False)
            except Exception as e:
                msg = 'failed to save record {ID} - {ERR}'.format(ID=record_id, ERR=e)
                logger.error(msg)
                return False

        sstrings = []
        psets = []
        for i, j in statements.items():
            sstrings.append(i)
            psets.append(j)

        success = user.write_db(sstrings, psets)

        return success

    def layout(self, win_size: tuple = None, view_only: bool = False, ugroup: list = None):
        """
        Generate a GUI layout for the account record.
        """
        if win_size:
            width, height = win_size
        else:
            width, height = (mod_const.WIN_WIDTH * 0.8, mod_const.WIN_HEIGHT * 0.8)

        record_layout = self.record_entry.record_layout

        # GUI data elements
        editable = True if view_only is False or self.new is True else False
        ugroup = ugroup if ugroup is not None and len(ugroup) > 0 else ['admin']

        # Element parameters
        bg_col = mod_const.ACTION_COL
        text_col = mod_const.TEXT_COL
        inactive_col = mod_const.INACTIVE_COL
        select_col = mod_const.SELECT_TEXT_COL

        bold_font = mod_const.BOLD_LARGE_FONT
        main_font = mod_const.MAIN_FONT

        pad_el = mod_const.ELEM_PAD
        pad_v = mod_const.VERT_PAD
        pad_h = mod_const.HORZ_PAD
        pad_frame = mod_const.FRAME_PAD

        # Layout elements
        try:
            reference_title = record_layout['References'].get('Title', 'References')
        except KeyError:
            reference_title = 'References'
            has_references = False
        else:
            has_references = True

        try:
            components_title = record_layout['Components'].get('Title', 'Components')
        except KeyError:
            components_title = 'Components'
            has_components = False
        else:
            has_components = True

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

        # Create layout for record details
        details_layout = []
        for data_elem in self.parameters:
            details_layout.append([data_elem.layout(padding=(0, pad_el), collapsible=True, editable=editable,
                                                    overwrite_edit=self.new)])

        # Add reference boxes to the details section
        ref_key = self.key_lookup('ReferencesButton')
        ref_layout = [[sg.Image(data=mod_const.NETWORK_ICON, pad=((0, pad_el), 0), background_color=bg_col),
                       sg.Text(reference_title, pad=((0, pad_el), 0), background_color=bg_col, font=bold_font),
                       sg.Button('', image_data=mod_const.HIDE_ICON, key=ref_key, button_color=(text_col, bg_col),
                                 border_width=0, disabled=False, visible=True,
                                 metadata={'visible': True, 'disabled': False})]]

        ref_boxes = []
        modify_reference = True if editable is True and self.level < 1 and self.permissions['references'] in ugroup \
            else False
        for ref_box in self.references:
            ref_boxes.append([ref_box.layout(padding=(0, pad_v), editable=modify_reference)])

        ref_layout.append([sg.pin(sg.Col(ref_boxes, key=self.key_lookup('ReferencesFrame'), background_color=bg_col,
                                         visible=True, expand_x=True, metadata={'visible': True}))])

        if has_references is True and self.new is False:
            details_layout.append([sg.Col(ref_layout, expand_x=True, pad=(0, pad_el), background_color=bg_col)])

        # Add components to the details section
        comp_key = self.key_lookup('ComponentsButton')
        comp_layout = [[sg.Image(data=mod_const.COMPONENTS_ICON, pad=((0, pad_el), 0), background_color=bg_col),
                        sg.Text(components_title, pad=((0, pad_el), 0), background_color=bg_col, font=bold_font),
                        sg.Button('', image_data=mod_const.HIDE_ICON, key=comp_key, button_color=(text_col, bg_col),
                                  border_width=0, visible=True, disabled=False,
                                  metadata={'visible': True, 'disabled': False})]]

        modify_component = True if editable is True and self.level < 1 and self.permissions['components'] in ugroup \
            else False

        comp_tables = []
        for comp_table in self.components:
            comp_table.df = comp_table.set_datatypes(comp_table.df)
            comp_tables.append([comp_table.layout(padding=(0, pad_v), width=width, height=height,
                                                  editable=modify_component)])

        comp_layout.append([sg.pin(sg.Col(comp_tables, key=self.key_lookup('ComponentsFrame'), background_color=bg_col,
                                          visible=True, expand_x=True, metadata={'visible': False}))])

        if has_components is True:
            details_layout.append([sg.Col(comp_layout, pad=(0, pad_el), expand_x=True, background_color=bg_col)])

        height_key = self.key_lookup('Height')
        width_key = self.key_lookup('Width')
        details_tab = sg.Tab('{:^40}'.format('Details'),
                             [[sg.Canvas(size=(width, 0), key=width_key, background_color=bg_col)],
                              [sg.Canvas(size=(0, height), key=height_key, background_color=bg_col),
                               sg.Col(details_layout, pad=(0, pad_v), background_color=bg_col, expand_y=True,
                                      expand_x=True, scrollable=True, vertical_scroll_only=True)]],
                             key=self.key_lookup('DetailsTab'), background_color=bg_col)

        # Create layout for record metadata
        markable = True if self.permissions['mark'] in ugroup and self.new is False \
                           and view_only is False else False
        approvable = True if self.permissions['approve'] in ugroup and self.new is False \
                             and view_only is False else False
        modifier_perms = {'MarkedForDeletion': markable, 'Approved': approvable, 'Deleted': False}
        if len(self.metadata) > 0:
            metadata_visible = True
            annotation_layout = []
            for param in self.metadata:
                param_name = param.name
                if param_name in modifier_perms:
                    param.editable = modifier_perms[param_name]

                annotation_layout.append(param.layout())
        else:
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
        for param in self.parameters:
            param_type = param.etype
            if param_type == 'multiline':
                param_size = (int((width - width % 9) / 9) - int((64 - 64 % 9) / 9), None)
            elif param_type == 'table':
                param_size = (width - 64, 1)
            else:
                param_size = None
            param.resize(window, size=param_size)

        # Resize the reference boxes
        ref_width = width - 62  # accounting for left and right padding and border width
        for refbox in self.references:
            refbox.resize(window, size=(ref_width, 40))

        # Resize component tables
        tbl_width = width - 64  # accounting for left and right padding and border width
        tbl_height = int(height * 0.2)  # each table has height that is 20% of window height
        for comp_table in self.components:
            comp_table.resize(window, size=(tbl_width, tbl_height), row_rate=80)

    def collapse_expand(self, window, frame: str = 'references'):
        """
        Hide/unhide record frames.
        """
        if frame == 'references':
            hide_key = self.key_lookup('ReferencesButton')
            frame_key = self.key_lookup('ReferencesFrame')
        else:
            hide_key = self.key_lookup('ComponentsButton')
            frame_key = self.key_lookup('ComponentsFrame')

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


class StandardRecord(DatabaseRecord):

    def run_event(self, window, event, values):
        """
        Perform a record action.
        """
        param_elems = [i for param in self.parameters for i in param.elements]
        modifier_elems = [i for param in self.metadata for i in param.elements]
        component_elems = [i for component in self.components for i in component.elements]
        reference_elems = [i for reference in self.references for i in reference.elements]

        # Expand or collapse the references frame
        if event == self.key_lookup('ReferencesButton'):
            self.collapse_expand(window, frame='references')

        # Expand or collapse the component tables frame
        elif event == self.key_lookup('ComponentsButton'):
            self.collapse_expand(window, frame='components')

        # Run a modifier event
        elif event in modifier_elems:
            try:
                param = self.fetch_modifier(event, by_key=True)
            except KeyError:
                logger.error('RecordType {NAME}, Record {ID}: unable to find modifier associated with event key {KEY}'
                             .format(NAME=self.name, ID=self.record_id(), KEY=event))
            else:
                param.run_event(window, event, values)

        # Run a component element event
        elif event in param_elems:  # parameter event
            try:
                param = self.fetch_element(event, by_key=True)
            except KeyError:
                logger.error('RecordType {NAME}, Record {ID}: unable to find parameter associated with event key {KEY}'
                             .format(NAME=self.name, ID=self.record_id(), KEY=event))
            else:
                param.run_event(window, event, values)

        # Run a component table event
        elif event in component_elems:  # component table event
            # Update data elements
            for param in self.parameters:
                param.update_display(window, window_values=values)

            try:
                component_table = self.fetch_component(event, by_key=True)
            except KeyError:
                logger.error('RecordType {NAME}, Record {ID}: unable to find component associated with event key {KEY}'
                             .format(NAME=self.name, ID=self.record_id(), KEY=event))
            else:
                component_table.run_event(window, event, values)

        # Run a reference-box event
        elif event in reference_elems:
            try:
                refbox = self.fetch_reference(event, by_key=True)
            except KeyError:
                logger.error('RecordType {NAME}, Record {ID}: unable to find reference associated with event key {KEY}'
                             .format(NAME=self.name, ID=self.record_id(), KEY=event))
            else:
                refbox.run_event(window, event, values)

        return True

    def update_display(self, window, window_values: dict = None):
        """
        Update the display of the record's elements and components.
        """
        # Update data elements
        for param in self.parameters:
            param.update_display(window, window_values=window_values)

        # Update the components display table
        for component in self.components:
            component.update_display(window, window_values=window_values)

        # Update records header
        for header in self.headers:
            elem_key = header.key_lookup('Element')
            display_value = header.format_display()
            window[elem_key].update(value=display_value)


class DepositRecord(DatabaseRecord):
    """
    Class to manage the layout and display of an REM Deposit Record.
    """

    def __init__(self, record_entry, level: int = 0, record_layout: dict = None):
        super().__init__(record_entry, level, record_layout)

        header_names = [i.name for i in self.headers]
        if 'DepositAmount' not in header_names:
            raise AttributeError('missing required header "DepositAmount"')

    def run_event(self, window, event, values):
        """
        Perform a record action.
        """
        param_elems = [i for param in self.parameters for i in param.elements]
        modifier_elems = [i for modifier in self.metadata for i in modifier.elements]
        component_elems = [i for component in self.components for i in component.elements]
        reference_elems = [i for reference in self.references for i in reference.elements]

        # Collapse or expand the references frame
        if event == self.key_lookup('ReferencesButton'):
            self.collapse_expand(window, frame='references')

        # Collapse or expand the component tables frame
        elif event == self.key_lookup('ComponentsButton'):
            self.collapse_expand(window, frame='components')

        # Run a modifier event
        elif event in modifier_elems:
            try:
                param = self.fetch_modifier(event, by_key=True)
            except KeyError:
                logger.error('RecordType {NAME}, Record {ID}: unable to find modifier associated with event key {KEY}'
                             .format(NAME=self.name, ID=self.record_id(), KEY=event))
            else:
                param.run_event(window, event, values)

        # Run a data element event
        elif event in param_elems:  # parameter event
            try:
                param = self.fetch_element(event, by_key=True)
            except KeyError:
                logger.error('Record {ID}: unable to find parameter associated with event key {KEY}'
                             .format(ID=self.record_id(), KEY=event))
            else:
                param.run_event(window, event, values)

        elif event in component_elems:  # component table event
            # Update data elements
            for param in self.parameters:
                param.update_display(window, window_values=values)

            try:
                component_table = self.fetch_component(event, by_key=True)
            except KeyError:
                logger.error('Record {ID}: unable to find component associated with event key {KEY}'
                             .format(ID=self.record_id(), KEY=event))
            else:
                if event == component_table.key_lookup('Import'):  # import account records
                    component_table.import_rows(reftype=self.name, program_database=True)
                elif event == component_table.key_lookup('Add'):  # add account records
                    default_values = {i.name: i.value for i in self.parameters if i.etype != 'table'}
                    component_table.add_row(record_date=self.record_date(), defaults=default_values)
                else:
                    component_table.run_event(window, event, values)

                self.update_display(window, window_values=values)

        elif event in reference_elems:
            try:
                refbox = self.fetch_reference(event, by_key=True)
            except KeyError:
                logger.error('Record {ID}: unable to find reference associated with event key {KEY}'
                             .format(ID=self.record_id(), KEY=event))
            else:
                refbox.run_event(window, event, values)

        return True

    def update_display(self, window, window_values: dict = None):
        """
        Update the display of the record's elements and components.
        """
        default_col = mod_const.ACTION_COL
        greater_col = mod_const.PASS_COL
        lesser_col = mod_const.FAIL_COL

        # Update parameter values
        for param in self.parameters:
            param.update_display(window, window_values=window_values)

        # Update the components display table
        for component in self.components:
            component.update_display(window, window_values=window_values)

        # Update the deposit total
        try:
            account_table = self.fetch_component('account')
        except KeyError:
            logger.warning('RecordEntry {TYPE}: missing required component records of type "account"'
                           .format(TYPE=self.name))
            account_total = 0
        else:
            account_total = account_table.calculate_total()
            logger.debug('Record {ID}: total income was calculated from the accounts table is {VAL}'
                         .format(ID=self.record_id(), VAL=account_total))

        try:
            expense_table = self.fetch_component('cash_expense')
        except KeyError:
            logger.warning('RecordEntry {TYPE}: missing component records of type "cash_expense"'
                           .format(TYPE=self.name))
            expense_total = 0
        else:
            expense_total = expense_table.calculate_total()
            logger.debug('Record {ID}: total expenditures was calculated from the expense table to be {VAL}'
                         .format(ID=self.record_id(), VAL=expense_total))

        deposit_total = account_total - expense_total

        if deposit_total > 0:
            bg_color = greater_col
        elif deposit_total < 0:
            bg_color = lesser_col
        else:
            bg_color = default_col

        deposit_param = self.fetch_header('DepositAmount')
        deposit_key = deposit_param.key_lookup('Element')
        deposit_param.value = deposit_param.format_value({deposit_key: deposit_total})
        window[deposit_key].update(background_color=bg_color)

        # Update records header
        for header in self.headers:
            elem_key = header.key_lookup('Element')
            display_value = header.format_display()
            window[elem_key].update(value=display_value)


class TAuditRecord(DatabaseRecord):
    """
    Class to manage the layout of an audit record.
    """

    def __init__(self, record_entry, level: int = 0, record_layout: dict = None):
        super().__init__(record_entry, level, record_layout)
        header_names = [i.name for i in self.headers]
        if 'Remainder' not in header_names:
            raise AttributeError('missing required header "Remainder"')

    def run_event(self, window, event, values):
        """
        Perform a record action.
        """
        param_elems = [i for param in self.parameters for i in param.elements]
        modifier_elems = [i for modifier in self.metadata for i in modifier.elements]
        component_elems = [i for component in self.components for i in component.elements]
        reference_elems = [i for reference in self.references for i in reference.elements]

        if event == self.key_lookup('ReferencesButton'):
            self.collapse_expand(window, frame='references')

        elif event == self.key_lookup('ComponentsButton'):
            self.collapse_expand(window, frame='components')

        # Run a modifier event
        elif event in modifier_elems:
            try:
                param = self.fetch_modifier(event, by_key=True)
            except KeyError:
                logger.error('RecordType {NAME}, Record {ID}: unable to find modifier associated with event key {KEY}'
                             .format(NAME=self.name, ID=self.record_id(), KEY=event))
            else:
                param.run_event(window, event, values)

        # Run a data element event
        elif event in param_elems:
            try:
                param = self.fetch_element(event, by_key=True)
            except KeyError:
                logger.error('Record {ID}: unable to find parameter associated with event key {KEY}'
                             .format(ID=self.record_id(), KEY=event))
            else:
                param.run_event(window, event, values)
                self.update_display(window, window_values=values)

        elif event in component_elems:  # component table event
            # Update data elements
            for param in self.parameters:
                param.update_display(window, window_values=values)

            try:
                component_table = self.fetch_component(event, by_key=True)
            except KeyError:
                logger.error('Record {ID}: unable to find component associated with event key {KEY}'
                             .format(ID=self.record_id(), KEY=event))
            else:
                if event == component_table.key_lookup('Import'):  # import account records
                    component_table.import_rows(reftype=self.name, program_database=True)
                elif event == component_table.key_lookup('Add'):  # add account records
                    default_values = {i.name: i.value for i in self.parameters if i.etype != 'table'}
                    component_table.add_row(record_date=self.record_date(), defaults=default_values)
                else:
                    component_table.run_event(window, event, values)

                self.update_display(window, window_values=values)

        elif event in reference_elems:
            try:
                refbox = self.fetch_reference(event, by_key=True)
            except KeyError:
                logger.error('Record {ID}: unable to find reference associated with event key {KEY}'
                             .format(ID=self.record_id(), KEY=event))
            else:
                refbox.run_event(window, event, values)

        return True

    def update_display(self, window, window_values: dict = None):
        """
        Update the display of the record's elements and components.
        """
        default_col = mod_const.ACTION_COL
        greater_col = mod_const.PASS_COL
        lesser_col = mod_const.FAIL_COL

        # Update parameter values
        for param in self.parameters:
            param.update_display(window, window_values=window_values)

        # Update the components display table
        for component in self.components:
            component.update_display(window, window_values=window_values)

        # Update the remainder
        totals_table = self.fetch_element('Totals')
        totals_sum = totals_table.calculate_total()

        try:
            account_table = self.fetch_component('account')
        except KeyError:
            logger.warning('Record {ID}: missing required component records of type "account"'
                           .format(ID=self.record_id()))
            account_total = 0
        else:
            account_total = account_table.calculate_total()

        remainder = totals_sum - account_total

        if remainder > 0:
            logger.info('Record {ID}: account records are under-allocated by {AMOUNT}'
                        .format(NAME=self.name, ID=self.record_id(), AMOUNT=remainder))
            bg_color = greater_col
        elif remainder < 0:
            logger.info('Record {ID}: account records are over-allocated by {AMOUNT}'
                        .format(NAME=self.name, ID=self.record_id(), AMOUNT=abs(remainder)))
            bg_color = lesser_col
        else:
            bg_color = default_col

        remainder_param = self.fetch_header('Remainder')
        remainder_key = remainder_param.key_lookup('Element')
        remainder_param.value = remainder_param.format_value({remainder_key: remainder})
        window[remainder_key].update(background_color=bg_color)

        # Update records header
        for header in self.headers:
            elem_key = header.key_lookup('Element')
            display_value = header.format_display()
            window[elem_key].update(value=display_value)


def create_record(record_entry, record_data, level: int = 1):
    """
    Create a new database record.
    """
    record_type = record_entry.group
    if record_type in ('account', 'transaction', 'bank_statement', 'cash_expense'):
        record_class = StandardRecord
    elif record_type == 'bank_deposit':
        record_class = DepositRecord
    elif record_type == 'audit':
        record_class = TAuditRecord
    else:
        logger.warning('unknown record layout type provided {}'.format(record_type))
        return None

    record = record_class(record_entry, level=level)
    record.initialize(record_data, new=True)

    return record


def remove_unsaved_keys(record):
    """
    Remove any unsaved IDs associated with the record, including the records own ID.
    """
    # Remove unsaved ID if record is new
    record_entry = record.record_entry
    record_entry.remove_unsaved_ids(record_ids=[record.record_id()])

    # Remove unsaved components
    for comp_table in record.components:
        comp_type = comp_table.record_type
        if comp_type is None:
            continue
        else:
            comp_entry = settings.records.fetch_rule(comp_type)

        # Get a list of added components added to the component table (i.e. not in the database yet)
        added_ids = record.get_added_components(comp_table.name)

        ids_to_remove = []
        for index, row in comp_table.df.iterrows():
            row_id = row[comp_table.id_column]
            if row_id not in added_ids:  # don't attempt to remove IDs if already in the database
                continue

            ids_to_remove.append(row_id)

        comp_entry.remove_unsaved_ids(record_ids=ids_to_remove)


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

