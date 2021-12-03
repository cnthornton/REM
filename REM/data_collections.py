"""
REM data container classes.
"""

import numpy as np
import pandas as pd

import REM.data_manipulation as mod_dm
from REM.client import logger, settings


# Data scalar classes
class DataVector:
    """
    Single variable data.
    """

    def __init__(self, name, entry):
        """
        Initialize class attributes.

        Arguments:
            name (str): name of the data vector.

            entry (dict): attribute default values.
        """
        self.name = name

        try:
            self.dtype = entry['DataType']
        except KeyError:
            self.dtype = 'varchar'
        else:
            supported_dtypes = settings.get_supported_dtypes()
            if self.dtype not in supported_dtypes:
                msg = 'unsupported data type provided - supported data types are {DTYPES}' \
                    .format(DTYPES=', '.join(supported_dtypes))
                logger.warning('DataVector {NAME}: {MSG}'.format(NAME=name, MSG=msg))

                self.dtype = 'varchar'

        # Starting value
        try:
            self.default = self._set_dtype(value=entry['Default'])
        except KeyError:
            self.default = None
        except TypeError as e:
            msg = 'failed to format configured default value {DEF} - {ERR}' \
                .format(DEF=entry['DefaultValue'], ERR=e)
            logger.warning('DataElement {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            self.default = None

        # Dynamic variables
        self.value = self.default

    def _set_dtype(self, value=None):
        """
        Format an input value according to the vector's dtype.
        """
        value = value if value else self.value
        dtype = self.dtype

        if dtype in ('date', 'datetime', 'timestamp', 'time'):
            value = np.datetime64(value)
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
        elif dtype in ('char', 'varchar', 'binary', 'text', 'string'):
            value = np.str_(value)
        else:
            logger.warning('DataVector {NAME}: data vector has unknown dtype "{DTYPE}" - setting to string'
                           .format(NAME=self.name, DTYPE=dtype))
            value = np.str_(value)

        return value

    def reset(self):
        """
        Reset the vector to default.
        """
        self.value = self.default

    def data(self):
        """
        Return the value of the data vector as a python object.
        """
        return self.value.item()

    def update_value(self, input_value):
        """
        Update the value of the vector.

        Arguments:
            input_value: value input into the GUI element.
        """
        if input_value == '' or pd.isna(input_value):
            value = None
        else:
            value = self._set_dtype(input_value)

        self.value = value

        return value


# Data collection classes
class DataCollection:
    """
    Collection of related data.
    """

    def __init__(self, name, entry):
        """
        Initialize class attributes.

        Arguments:
            name (str): name of the data collection.

            entry (dict): attribute default values.
        """
        self._deleted_column = '_RowDeleted_'
        self._added_column = '_RowAdded_'
        self._edited_column = '_RowEdited_'

        self._state_fields = {'deleted': self._deleted_column, 'edited': self._edited_column,
                              'added': self._added_column}

        self.name = name

        self.dtypes = {self._deleted_column: 'bool', self._edited_column: 'bool', self._added_column: 'bool'}
        try:
            dtypes = entry['Columns']
        except KeyError:
            raise AttributeError('missing required parameter "Columns"')
        else:
            supported_dtypes = settings.get_supported_dtypes()
            for field, dtype in dtypes.items():
                if dtype not in supported_dtypes:
                    msg = 'the data type specified for field "{COL}" is not a supported data type - supported data ' \
                          'types are {TYPES}'.format(COL=field, TYPES=', '.join(supported_dtypes))
                    logger.warning(msg)
                    self.dtypes[field] = 'varchar'
                else:
                    self.dtypes[field] = dtype

        try:
            dependant_fields = entry['DependantColumns']
        except KeyError:
            dependant_fields = {}

        self.dependant_columns = {}
        for field in dependant_fields:
            if field not in self.dtypes:
                logger.warning('DataCollection {NAME}: no data type set for dependant field "{COL}"'
                               .format(NAME=self.name, COL=field))
                continue

            self.dependant_columns[field] = dependant_fields[field]

        try:
            default = entry['Defaults']
        except KeyError:
            default = {}

        self.default = {}
        for field in default:
            if field not in dtypes:
                logger.warning('DataTable {NAME}: no data type set for default field "{COL}"'
                               .format(NAME=self.name, COL=field))
                continue

            self.default[field] = default[field]

        self.df = self._set_dtypes(df=pd.DataFrame(columns=list(self.dtypes)))

    def _deleted_rows(self):
        """
        Return real indices of the deleted rows.
        """
        is_bool_dtype = pd.api.types.is_bool_dtype

        del_column = self._deleted_column
        df = self.df.copy()

        if df.empty:
            return []

        if del_column not in df.columns:
            df[del_column] = False

        df[del_column].fillna(False, inplace=True)
        if not is_bool_dtype(df[del_column].dtype):  # datatype was modified from original boolean
            logger.debug('DataCollection {NAME}: setting datatype of the deletion field "{COL}" to boolean'
                         .format(NAME=self.name, COL=del_column))
            try:
                df = df.astype({del_column: 'bool'})
            except ValueError:
                logger.warning('DataCollection {NAME}: unable to set the datatype of the deletion field "{COL}" to '
                               'boolean'.format(NAME=self.name, COL=del_column))
                return []

        logger.debug('DataCollection {NAME}: filtering deleted entries on deletion field "{COL}"'
                     .format(NAME=self.name, COL=del_column))

        deleted_inds = df[df[del_column]].index

        return deleted_inds

    def _set_defaults(self, df: pd.DataFrame = None):
        """
        Update empty cells with default values.
        """
        dtypes = self.dtypes
        if df is None:
            df = self.df.copy()

        logger.info('DataCollection {NAME}: setting default values'.format(NAME=self.name))

        header = df.columns
        default_columns = self.default
        for column in default_columns:
            try:
                dtype = dtypes[column]
            except KeyError:
                logger.warning('DataCollection {NAME}: no data type set for default field "{COL}"'
                               .format(NAME=self.name, COL=column))
                continue

            if column not in header:
                df[column] = None

            logger.debug('DataCollection {NAME}: setting defaults for field "{COL}"'
                         .format(NAME=self.name, COL=column))

            column_default = default_columns[column]
            if isinstance(column_default, dict):  # column default is a set of conditions
                default_values = pd.Series(None, index=df.index, dtype='object')
                for default_value in column_default:  # defaults are the values of another field in the collection
                    if default_value in dtypes:
                        values = df[default_value]
                    else:
                        values = pd.Series(default_value, index=df.index)

                    default_rule = column_default[default_value]
                    #results = mod_dm.evaluate_condition_set(df, {default_value: default_rule})
                    results = mod_dm.evaluate_condition(df, default_rule)
                    for index in results[results].index:  # only "passing", or true, indices
                        default_values[index] = values[index]

                default_values = format_values(default_values, dtype)
            else:  # single condition supplied
                results = mod_dm.evaluate_operation(df, column_default)

                if isinstance(results, pd.Series):  # defaults are the values of another field in the collection
                    default_values = format_values(results, dtype)
                else:  # single default value supplied
                    default_values = format_value(results, dtype)

            df[column].fillna(default_values, inplace=True)

        return df

    def _set_dependants(self, df=None):
        """
        Update dependant columns on configured conditions.
        """
        logger.debug('DataCollection {NAME}: setting dependant field values'.format(NAME=self.name))

        df = self.df.copy() if df is None else df
        if isinstance(df, pd.Series):  # need to convert series to dataframe first
            df = df.to_frame().T

        header = df.columns.tolist()
        columns = self.dependant_columns
        if not columns:
            return df

        for column in columns:
            logger.debug('DataCollection {NAME}: setting dependant values for dependant field "{COL}"'
                         .format(NAME=self.name, COL=column))

            try:
                dtype = self.dtypes[column]
            except KeyError:
                logger.warning('DataCollection {NAME}: no data type set for dependant field "{COL}"'
                               .format(NAME=self.name, COL=column))
                continue

            if column not in header:
                df.loc[:, column] = None

            rule = columns[column]
            try:
                #default_values = mod_dm.evaluate_rule(df, rule, as_list=False)
                default_values = mod_dm.evaluate_operation(df, rule)
            except Exception as e:
                msg = 'failed to evaluate rule expression {RULE} - {ERR}'.format(RULE=rule, ERR=e)
                logger.exception(msg)
            else:
                default_values = format_values(default_values, dtype)
                print('dependant field {} has values:'.format(column))
                print(default_values)
                df.loc[:, column] = default_values

        return df

    def _set_dtypes(self, df=None, dtypes: dict = None):
        """
        Set field data types based on header mapping.
        """
        df = self.df.copy() if df is None else df
        dtype_map = self.dtypes if dtypes is None else dtypes

        if isinstance(df, pd.Series):  # need to convert series to dataframe first
            df = df.to_frame().T

        header = df.columns.tolist()

        if not isinstance(dtype_map, dict):
            msg = 'failed to set field datatypes - fields must be configured as a dictionary to specify data types'
            logger.warning('DataCollection {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            return df

        for column_name in dtype_map:
            if column_name not in header:
                msg = 'configured field "{COL}" is not in the header - setting initial value to NaN'\
                    .format(COL=column_name)
                logger.warning('DataCollection {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

                df[column_name] = None

            dtype = dtype_map[column_name]
            column = df[column_name]
            try:
                column_values = format_values(column, dtype)
            except Exception as e:
                logger.exception('DataCollection {NAME}: unable to set field "{COL}" to data type "{DTYPE}" - {ERR}'
                                 .format(NAME=self.name, COL=column_name, DTYPE=dtype, ERR=e))
            else:
                try:
                    df.loc[:, column_name] = column_values
                except ValueError as e:
                    logger.exception('DataTable {NAME}: unable to set field "{COL}" to data type "{DTYPE}" - {ERR}'
                                     .format(NAME=self.name, COL=column_name, DTYPE=dtype, ERR=e))

        return df

    def _update_row_values(self, index, values):
        """
        Update data values at the given real index.

        Arguments:
            index (int): real index of the entry to update.

            values (DataFrame): single row dataframe containing row values to use to update the dataframe at the
               given index.
        """
        pd.set_option('display.max_columns', None)
        df = self.df
        header = df.columns.tolist()

        if isinstance(values, dict):
            if isinstance(index, int):
                index = [index]
            values = pd.DataFrame(values, index=index)
        elif isinstance(values, pd.Series):  # single set of row values
            values.name = index
            values = values.to_frame().T
        else:  # dataframe of row values
            values = values.set_index(pd.Index(index))

        #shared_cols = [i for i in values.columns if i in header]
        #new_values = self.enforce_conformity(values)[shared_cols]
        new_values = self.enforce_conformity(values)[header]
        print('new values after enforcing conformity are:')
        print(new_values)

        edited_rows = set()
        edited_cols = []
        for row_ind, row in new_values.iterrows():
            for column, row_value in row.iteritems():
                orig_value = df.loc[row_ind, column]
                if row_value != orig_value:
                    df.at[index, column] = row_value
                    edited_rows.add(row_ind)
                    edited_cols.append(column)

        edited = False
        if len(edited_rows) > 0:
            edited_col = self._edited_column
            edited = True
            for edited_ind in edited_rows:
                df.loc[edited_ind, edited_col] = True

        for column in edited_cols:
            dtype = self.dtypes[column]
            current_vals = df[column]
            try:
                column_values = format_values(current_vals, dtype)
            except Exception as e:
                logger.exception('DataCollection {NAME}: unable to set field "{COL}" to data type "{DTYPE}" - {ERR}'
                                 .format(NAME=self.name, COL=column, DTYPE=dtype, ERR=e))
            else:
                try:
                    df.loc[:, column] = column_values
                except ValueError as e:
                    logger.exception('DataTable {NAME}: unable to set field "{COL}" to data type "{DTYPE}" - {ERR}'
                                     .format(NAME=self.name, COL=column, DTYPE=dtype, ERR=e))

        return edited

    def enforce_conformity(self, add_df):
        """
        Enforce conformity with the collection data for a new set of data.
        """
        pd.set_option('display.max_columns', None)

        # Set default values for the data
        add_df = self._set_defaults(df=add_df)
        add_df = self._set_dependants(df=add_df)

        # Make sure the data types of the columns are consistent
        add_df = self._set_dtypes(df=add_df)

        return add_df

    def data(self, current: bool = True, indices: list = None, edited_only: bool = False, deleted_only: bool = False,
             added_only: bool = False):
        """
        Return the collection data.

        Arguments:
            current (bool): return only the current entries, excluding the deleted entries [Default: True].

            indices (list): return entries at the given indices [Default: None]

            edited_only (bool): return only the entries that have been edited [Default: False].

            deleted_only (bool): return only the entries that have been deleted from the collection [Default: False].

            added_only (bool): return only the entries that have been added to the collection [Default: False].

        Returns:
            df (DataFrame): data matching the selection requirements.
        """
        df = self.df.copy()

        if current and (indices is not None or deleted_only is True):
            logger.warning('the current and indices arguments are mutually exclusive - setting current to False')
            current = False

        if current:
            deleted_indices = self._deleted_rows()
            df.drop(deleted_indices, inplace=True)

        if indices is not None:
            df = df.loc[indices]

        # Filter on edited rows, if desired
        if edited_only:  # all edited, current edited, or edited and deleted
            df = df[(df[self._added_column]) | (df[self._edited_column])]
        elif added_only:  # all added, current added, or added and then deleted
            df = df[df[self._added_column]]
        elif deleted_only:
            df = df[df[self._deleted_column]]

        # Remove the state fields from the data
        df.drop(columns=[self._added_column, self._edited_column, self._deleted_column], inplace=True)

        return df

    def append(self, add_df, inplace: bool = True, new: bool = False, reindex: bool = True):
        """
        Add data to the collection.

        Arguments:
            add_df: new data entries to append to the collection.

            inplace (bool): append to the dataframe in-place [Default: True].

            new (bool): set the added state of the new data to True [Default: False].

            reindex (bool): reset collection entry indices after append.
        """
        df = self.df.copy()

        if add_df.empty:  # no data to add
            return df

        # Convert add_df to dataframe
        if isinstance(add_df, pd.Series):
            add_df = add_df.to_frame().T
        elif isinstance(add_df, dict):
            add_df = pd.DataFrame(add_df)

        # Add the "state" columns to the new data
        add_df.loc[:, [self._added_column, self._edited_column, self._deleted_column]] = [new, False, False]

        # Enforce conformity of the new data
        add_df = self.enforce_conformity(add_df)

        # Add new data to the table
        logger.debug('DataCollection {NAME}: adding {NROW} entries to the collection'
                     .format(NAME=self.name, NROW=add_df.shape[0]))
        df = df.append(add_df, ignore_index=reindex)

        if inplace:
            self.df = df

        return df

    def delete(self, indices, inplace: bool = True):
        """
        Remove data from the collection.

        Arguments:
            indices (list): real indices of the desired data to remove from the collection.

            inplace (bool): delete data in place [Default: True].
        """
        if inplace:
            df = self.df
        else:
            df = self.df.copy()

        if isinstance(indices, str):
            indices = [indices]

        logger.info('DataCollection {NAME}: deleting data entries at indices {IDS} from the collection'
                    .format(NAME=self.name, IDS=indices))

        # Set the deleted and edited "state" fields for the indicated rows to True
        df.loc[indices, [self._deleted_column, self._edited_column]] = [True, True]

        return df

    def set_state(self, field, flag, indices: list = None, inplace: bool = True):
        """
        Set the value for the state field at the given indices.
        """
        state_fields = self._state_fields
        try:
            column = state_fields[field]
        except KeyError:
            raise KeyError('field must be one of {}'.format(list(state_fields)))

        if inplace:
            df = self.df
        else:
            df = self.df.copy()

        if indices is None:
            indices = df.index

        df.loc[indices, column] = flag

        return df

    def summarize_field(self, field, indices: list = None, statistic: str = None):
        """
        Summarize the values of a field.
        """
        supported_stats = ['sum', 'count', 'product', 'mean', 'median', 'mode', 'min', 'max', 'std', 'unique']
        is_numeric_dtype = pd.api.types.is_numeric_dtype

        if statistic and statistic not in supported_stats:
            msg = 'unable to summarize field "{COL}" - unknown statistic {STAT} supplied' \
                .format(STAT=statistic, COL=field)
            logger.warning('DataCollection {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
            statistic = None

        if indices:
            df = self.df.copy().loc[indices]
        else:
            df = self.data()

        try:
            col_values = df[field]
        except KeyError:
            logger.error('DataCollection {NAME}: unable to summarize field "{COL}" - {COL} not found in the collection'
                         .format(NAME=self.name, COL=field))

            return 0

        print('summary field {} has values:'.format(field))
        print(col_values)

        if col_values.empty:
            return 0

        dtype = col_values.dtype
        if statistic == 'sum':
            col_summary = col_values.sum()
        elif statistic == 'count':
            col_summary = col_values.count()
        elif statistic == 'unique':
            col_summary = col_values.nunique()
        elif statistic == 'min':
            col_summary = col_values.min()
        elif statistic == 'max':
            col_summary = col_values.max()
        elif statistic == 'product' and is_numeric_dtype(dtype):
            col_summary = col_values.product()
        elif statistic == 'mean' and is_numeric_dtype(dtype):
            col_summary = col_values.mean()
        elif statistic == 'mode' and is_numeric_dtype(dtype):
            col_summary = col_values.mode()
        elif statistic == 'median' and is_numeric_dtype(dtype):
            col_summary = col_values.median()
        elif statistic == 'std' and is_numeric_dtype(dtype):
            col_summary = col_values.std()
        else:
            if is_numeric_dtype(dtype):  # default statistic for numeric data types like ints, floats, and bools
                col_summary = col_values.sum()
            else:  # default statistic for non-numeric data types like strings and datetime objects
                col_summary = col_values.nunique()

        return col_summary

    def fill(self, indices, field, method: str = 'ffill'):
        """
        Fill field NA values in-place using the desired fill method.

        Arguments:
            indices (list): list of real indices to fill data on.

            field (str): collection field with NA values to fill.

            method (str): method to use to fill gaps (NA values) in the data 'ffill', 'bfill', 'pad', or 'backfill'
                [Default: ffill].
        """
        edited = False
        df = self.df

        logger.info('DataCollection {NAME}: filling field "{COL}" rows {ROWS} using fill method "{METHOD}"'
                    .format(NAME=self.name, COL=field, ROWS=len(indices), METHOD=method))

        if len(indices) > 1:
            column_index = self.df.columns.get_loc(field)
            try:
                df.loc[indices, column_index] = df.loc[indices, column_index].fillna(method=method)
            except IndexError:
                logger.warning('DataCollection {NAME}: unable to fill field "{COL}" values - no rows found at indices '
                               '{ROWS}'.format(NAME=self.name, COL=field, ROWS=indices))
            except ValueError:
                logger.warning('DataCollection {NAME}: unable to fill field "{COL}" values - unknown fill method '
                               '{METHOD} provided'.format(NAME=self.name, COL=field, METHOD=method))
            else:  # indicate that the specific rows and the table have been edited
                df.loc[indices, self._edited_column] = True
                edited = True
        else:
            logger.warning('DataCollection {NAME}: unable to fill field "{COL}" values - too few rows selected for '
                           'filling'.format(NAME=self.name, COL=field))

        return edited

    def sort(self, sort_on=None, ascending: bool = True, inplace: bool = True):
        """
        Sort the data on provided column name.

        Arguments:
            sort_on: sort data on the given field names. Sort order is determined on the order of the iterable.

            ascending (bool): sort values from least to greatest [Default: True].

            inplace (bool): sort collection data in-place [Default: True].
        """
        if inplace:
            df = self.df
        else:
            df = self.df.copy()

        if df.empty:
            return df

        # Prepare the columns to sort the table on
        sort_keys = []
        header = df.columns.tolist()
        if isinstance(sort_on, str):
            sort_keys.append(sort_on)
        elif isinstance(sort_on, list):
            for sort_col in sort_on:
                if sort_col in header:
                    sort_keys.append(sort_col)
                else:
                    logger.warning('DataCollection {NAME}: sort field "{COL}" not found in the header'
                                   .format(NAME=self.name, COL=sort_col))

        if len(sort_keys) > 0:
            logger.debug('DataCollection {NAME}: sorting data on {KEYS}'.format(NAME=self.name, KEYS=sort_keys))
            try:
                df.sort_values(by=sort_keys, inplace=True, ascending=ascending)
            except KeyError:  # sort key is not in table header
                logger.warning('DataCollection {NAME}: one or more sort fields ({COLS}) not find in the header '
                               '- values will not be sorted.'.format(NAME=self.name, COLS=', '.join(sort_keys)))
            else:
                df.reset_index(drop=True, inplace=True)

        return df

    def reset(self):
        """
        Reset the collection to default.
        """
        self.df = self._set_dtypes(df=pd.DataFrame(columns=list(self.dtypes)))

    def set_index(self, indices):
        """
        Set the index for the collection entries.
        """
        df = self.df

        if isinstance(indices, list):
            indices = pd.Index(indices)

        df.set_index(indices)

    def update_entry(self, index, values):
        """
        Update the values of a given data entry in-place.

        Arguments:
            index (int): index of the data entry.

            values (Series): values to replace.
        """
        edited = self._update_row_values(index, values)

        return edited

    def update_field(self, column, values, indices: list = None):
        """
        Update the entry values for a given field in-place.

        Arguments:
            column (str): name of the field to modify.

            values: list, series, or scalar of new field values.

            indices (list): optional list of entry indices to modify [Default: update all entries].
        """
        df = self.df
        edited = False

        if indices is None:  # update all rows
            indices = df.index.tolist()
        elif isinstance(indices, int):
            indices = [indices]

        try:
            col_values = df.loc[indices, column]
        except IndexError:
            msg = 'DataCollection {NAME}: failed to update column "{COL}" - one or more row indices from {INDS} are ' \
                  'missing from the table'.format(NAME=self.name, COL=column, INDS=indices)
            raise IndexError(msg)

        if not isinstance(values, pd.Series):
            values = pd.Series(values, index=indices)

        dtype = self.dtypes[column]
        values = format_values(values, dtype)

        # Set "Is Edited" to True where existing column values do not match the update values
        try:
            edited_results = ~((col_values.eq(values)) | (col_values.isna() & values.isna()))
        except ValueError:
            msg = 'DataCollection {NAME}: failed to update column "{COL}" - the length of the update values must be ' \
                  'equal to the length of the indices to update'.format(NAME=self.name, COL=column)
            raise ValueError(msg)
        else:
            edited_indices = edited_results[edited_results].index  # only True values selected
            if len(edited_indices) > 0:
                df.loc[edited_indices, self._edited_column] = True
                edited = True

        # Replace existing column values with new values and set dependant values
        df.loc[indices, column] = values
        self._set_dependants(df=df)

        return edited


class RecordCollection(DataCollection):
    """
    Collections of record data.
    """

    def __init__(self, name, entry):
        """
        Initialize collection attributes.

        Arguments:
            name (str): name of the collection.

            entry (dict): attribute default values.
        """
        super(RecordCollection, self).__init__(name, entry)

        try:
            self.id_column = entry['IDColumn']
        except KeyError:
            self.id_column = 'RecordID'

        try:
            self.date_column = entry['DateColumn']
        except KeyError:
            self.date_column = 'RecordDate'

    def as_reference(self, edited_only: bool = False):
        """
        Export data as a reference.
        """
        deleted_col = self._deleted_column
        added_col = self._added_column
        edited_col = self._edited_column

        df = self.df

        # Filter out added rows that were later removed from the table
        conditions = df[deleted_col] & df[added_col]
        export_df = df[~conditions]

        if edited_only:
            export_df = export_df[(export_df[added_col]) | (export_df[edited_col])]

        # Create the reference entries
        ref_df = export_df[[self.id_column, deleted_col]]
        ref_df.rename(columns={self.id_column: 'ReferenceID', deleted_col: 'IsDeleted'}, inplace=True)

        return ref_df

    def record_index(self, record_ids):
        """
        Return a list of collection indices corresponding to the supplied record IDs.

        Arguments:
            record_ids: list of record IDs contained in the collection.
        """
        df = self.df

        if isinstance(record_ids, str):
            record_ids = [record_ids]
        elif isinstance(record_ids, pd.Series):
            record_ids = record_ids.tolist()

        indices = df.loc[df[self.id_column].isin(record_ids)].index.tolist()

        return indices

    def row_ids(self, indices: list = None, deleted: bool = False):
        """
        Return a list of the current record IDs stored in the collection.

        Arguments:
            indices (list): optional list of indices to subset collection on [Default: get all record IDs in the
                table].

            deleted (bool): include deleted rows [Default: False].
        """
        id_field = self.id_column
        if isinstance(indices, int):
            indices = [indices]

        if deleted or (indices is not None and len(indices) > 0):
            df = self.data(current=False)  # all rows, not just current
        else:
            df = self.data()

        if indices is None:
            indices = df.index

        try:
            row_ids = df.loc[indices, id_field].tolist()
        except KeyError as e:
            logger.exception('DataCollection {NAME}: unable to return a list of row IDs - {ERR}'
                             .format(NAME=self.name, COL=id_field, ERR=e))
            row_ids = []

        return row_ids


class ReferenceCollection(DataCollection):
    """
    Collections of record reference data.
    """

    def __init__(self, name, entry):
        """
        Initialize collection attributes.

        Arguments:
            name (str): name of the collection.

            entry (dict): attribute default values.
        """
        super(ReferenceCollection, self).__init__(name, entry)
        self._state_fields = {'deleted': self._deleted_column, 'edited': self._edited_column,
                              'added': self._added_column, 'approved': 'IsApproved', 'child': 'IsChild',
                              'link': 'IsHardLink'}

        self.dtypes = {self._deleted_column: 'bool', self._edited_column: 'bool', self._added_column: 'bool',
                       'RecordID': 'varchar', 'ReferenceID': 'varchar', 'ReferenceDate': 'date',
                       'RecordType': 'varchar', 'ReferenceType': 'varchar', 'IsApproved': 'bool', 'IsHardLink': 'bool',
                       'IsChild': 'bool', 'IsDeleted': 'bool'}

        self.df = pd.DataFrame(columns=list(self.dtypes))

#    def merge(self, df: pd.DataFrame = None, ref_df: pd.DataFrame = None):
#        """
#        Merge the records table and the reference table on configured reference map columns.
#
#        Arguments:
#            df (DataFrame): records data [Default: use full records dataframe].
#
#            ref_df (DataFrame): record reference data [Default: use full reference dataframe].
#
#        Returns:
#            df (DataFrame): dataframe of records merged with their corresponding reference entries.
#        """
#        pd.set_option('display.max_columns', None)
#
#        ref_map = self.reference_columns
#        id_col = self.id_column
#
#        df = self.data() if df is None else df
#        ref_df = self.ref_df.copy() if ref_df is None else ref_df
#
#        # Reorder the references dataframe to match the order of the records in the records table
#        ref_df.set_index(id_col, inplace=True)
#        ref_df = ref_df.reindex(index=df[id_col])
#
#        # Get shared indices in case the references dataframe does not contain all of the data of the records dataframe
#        if df.shape[0] != ref_df.shape[0]:
#            logger.warning('BankAccount {NAME}: the records dataframe and reference dataframe of of unequal sizes'
#                           .format(NAME=self.name))
#            indices = df[df[id_col].isin(ref_df.index.tolist())].index
#        else:
#            indices = df.index.tolist()
#
#        # Update the configured references columns in the records dataframe to be the same as the columns in references
#        # dataframe
#        for column in ref_map:
#            mapped_col = ref_map[column]
#
#            new_values = ref_df[column].tolist()
#            self.update_field(mapped_col, new_values, indices=indices)


def format_value(value, dtype):
    """
    Set the datatype for a single value.

    Arguments:
        value (Series): non-iterable value to set.

        dtype (str): scalar data type.
    """
    if dtype in ('date', 'datetime', 'timestamp', 'time'):
        value = np.datetime64(value)
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
    elif dtype in ('char', 'varchar', 'binary', 'text', 'string'):
        value = np.object_(value)
    else:
        value = np.object_(value)

    return value


def format_values(values, dtype):
    """
    Set the datatype for an array of values.

    Arguments:
        values (Series): pandas Series containing array values.

        dtype (str): array data type.
    """
    if not isinstance(values, pd.Series):
        values = pd.Series(values)

    if dtype in ('date', 'datetime', 'timestamp', 'time'):
        is_datetime_dtype = pd.api.types.is_datetime64_any_dtype

        if not is_datetime_dtype(values.dtype):
            try:
                values = pd.to_datetime(values.fillna(pd.NaT), errors='coerce', format=settings.date_format,
                                        utc=False)
            except Exception as e:
                msg = 'failed to set column values to datatype {DTYPE} - {ERR}'.format(DTYPE=dtype, ERR=e)

                raise ValueError(msg)
        else:  # is datetime dtype
            values = values.dt.tz_localize(None)
            # values = column_values.apply(lambda x: x.replace(tzinfo=None))

    elif dtype in ('int', 'integer', 'bigint'):
        try:
            values = values.astype('Int64')
        except TypeError:
            values = values.astype(float).astype('Int64')
    elif dtype == 'mediumint':
        try:
            values = values.astype('Int32')
        except TypeError:
            values = values.astype(float).astype('Int32')
    elif dtype == 'smallint':
        try:
            values = values.astype('Int16')
        except TypeError:
            values = values.astype(float).astype('Int16')
    elif dtype in ('tinyint', 'bit'):
        try:
            values = values.astype('Int8')
        except TypeError:
            values = values.astype(float).astype('Int8')
    elif dtype in ('float', 'real', 'double'):  # approximate numeric data types for saving memory
        values = pd.to_numeric(values, errors='coerce', downcast='float')
    elif dtype in ('decimal', 'dec', 'numeric', 'money'):  # exact numeric data types
        values = pd.to_numeric(values, errors='coerce')
    elif dtype in ('bool', 'boolean'):
        values = values.fillna(False).astype(np.bool_, errors='raise')
    elif dtype in ('char', 'varchar', 'binary', 'text', 'string'):
        values = values.astype(np.object_, errors='raise')
    else:
        values = values.astype(np.object_, errors='raise')

    return values
