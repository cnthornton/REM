"""
REM data container classes.
"""

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
            self.default = mod_dm.format_value(entry['DefaultValue'], self.dtype)
        except KeyError:
            self.default = None
        except TypeError as e:
            msg = 'failed to format configured default value {DEF} - {ERR}' \
                .format(DEF=entry['DefaultValue'], ERR=e)
            logger.warning('DataElement {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            self.default = None

        # Formatting options
        try:
            aliases = entry['Aliases']
        except KeyError:
            aliases = settings.fetch_alias_definition(self.name)

        self.aliases = {}  # only str and int types can have aliases - aliases dict reversed during value formatting
        if self.dtype in settings.supported_int_dtypes + settings.supported_cat_dtypes + settings.supported_str_dtypes:
            for alias in aliases:  # alias should have same datatype as the element
                alias_value = aliases[alias]
                self.aliases[settings.format_value(alias, self.dtype)] = alias_value

        try:
            self.date_format = entry['DateFormat']
        except KeyError:
            self.date_format = settings.display_date_format

        # Dynamic variables
        self.value = self.default

    def reset(self):
        """
        Reset the vector to default.
        """
        self.value = self.default

    def data(self):
        """
        Return the value of the data vector as a python object.
        """
        try:
            value = self.value.item()
        except AttributeError:
            #logger.debug('DataVector {NAME}: no value set for the data vector'.format(NAME=self.name))
            value = None

        return value

    def update_value(self, input_value):
        """
        Update the value of the vector.

        Arguments:
            input_value: value input into the GUI element.
        """
        current_value = self.value
        logger.debug('DataVector {NAME}: updating the value of the data vector with existing value {VAL}'
                     .format(NAME=self.name, VAL=current_value))

        if input_value == '' or pd.isna(input_value):
            new_value = None
        else:
            new_value = mod_dm.format_value(input_value, self.dtype)

        edited = False
        if current_value != new_value:
            self.value = new_value
            edited = True

        return edited

    def format_display(self, editing: bool = False, value=None):
        """
        Format the vector's value for displaying.
        """
        value = value if value is not None else self.data()

        logger.debug('DataVector {NAME}: formatting the display for value "{VAL}"'.format(NAME=self.name, VAL=value))

        dtype = self.dtype
        if dtype == 'money':
            if pd.isna(value):
                return ''

            value = str(value)
            if not editing:
                display_value = settings.format_display_money(value)
            else:
                display_value = value

        elif dtype in settings.supported_float_dtypes:
            if pd.isna(value):
                return ''

            display_value = str(value)

        elif dtype in settings.supported_int_dtypes:
            if pd.isna(value):
                return ''

            display_value = value

        elif dtype in settings.supported_date_dtypes:
            if pd.isna(value):
                return ''

            if not editing:  # use global settings to determine how to format date
                display_value = settings.format_display_date(value)  # default format is ISO
            else:  # enforce ISO formatting if element is editable
                display_value = value.strftime(settings.format_date_str(date_str=self.date_format))

        elif dtype in settings.supported_bool_dtypes:
            if pd.isna(value):
                return False

            try:
                display_value = bool(int(value))
            except ValueError:
                logger.warning('DataVector {NAME}: unsupported value {VAL} of type {TYPE} provided'
                               .format(NAME=self.name, VAL=value, TYPE=type(value)))
                display_value = False

        else:
            if pd.isna(value):
                return ''

            display_value = str(value).rstrip('\n\r')

        # Set display value alias, if applicable
        aliases = self.aliases
        if display_value in aliases:
            display_value = aliases[display_value]

        logger.debug('DataVector {NAME}: setting display value to {VAL}'.format(NAME=self.name, VAL=display_value))

        return display_value


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

        self._default_attrs = {'unique': False, 'required': False, 'hidden': False, 'editable': False, 'default': None}

        self.name = name

        self.dtypes = {self._deleted_column: 'bool', self._edited_column: 'bool', self._added_column: 'bool'}
        self._fields = []
        try:
            dtypes = entry['Columns']
        except KeyError:
            raise AttributeError('missing required parameter "Columns"')
        else:
            supported_dtypes = settings.get_supported_dtypes()
            for field, dtype in dtypes.items():
                self._fields.append(field)
                if dtype not in supported_dtypes:
                    msg = 'the data type specified for field "{COL}" is not a supported data type - supported data ' \
                          'types are {TYPES}'.format(COL=field, TYPES=', '.join(supported_dtypes))
                    logger.warning(msg)
                    self.dtypes[field] = 'varchar'
                else:
                    self.dtypes[field] = dtype

        try:
            column_attrs = entry['ColumnAttributes']
        except KeyError:
            self.column_attrs = {}
        else:
            if isinstance(column_attrs, dict):
                self.column_attrs = column_attrs
            else:
                self.column_attrs = {}

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
            aliases = entry['Aliases']
        except KeyError:
            aliases = {}
            for column in dtypes:
                alias_def = settings.fetch_alias_definition(column)
                if alias_def:
                    aliases[column] = alias_def

        self.aliases = {}
        for alias_column in aliases:
            if alias_column in dtypes:
                alias_map = aliases[alias_column]

                # Convert values into correct column datatype
                column_dtype = dtypes[alias_column]
                if column_dtype in (settings.supported_int_dtypes + settings.supported_cat_dtypes +
                                    settings.supported_str_dtypes):
                    alias_map = {settings.format_value(i, column_dtype): j for i, j in alias_map.items()}

                    self.aliases[alias_column] = alias_map
            else:
                msg = 'DataCollection {NAME}: alias column {COL} not found in list of display columns'\
                    .format(NAME=self.name, COL=alias_column)
                logger.warning(msg)

        try:
            default = entry['Defaults']
        except KeyError:
            default = {}

        self.default = {}
        for field in default:
            if field not in dtypes:
                logger.warning('DataCollection {NAME}: no data type set for default field "{COL}"'
                               .format(NAME=self.name, COL=field))
                continue

            self.default[field] = default[field]

        self.df = self._set_dtypes(df=pd.DataFrame(columns=list(self.dtypes)))

    def _get_attr(self, field, attr: str = None):
        """
        Get an attribute for a collection field.
        """
        defaults = self._default_attrs
        attrs = self.column_attrs

        if field in self.dtypes:
            if not attr:  # get all attributes for a column when none specified
                field_attr = [attrs.get(field, {}).get(i, defaults.get(i, None)) for i in defaults]
            elif isinstance(attr, list):
                field_attr = [attrs.get(field, {}).get(i, defaults.get(i, None)) for i in attr]
            elif isinstance(attr, str):
                field_attr = attrs.get(field, {}).get(attr, defaults.get(attr, None))
            else:
                field_attr = None
        else:  # the provided field is not a collection field
            field_attr = None

        return field_attr

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

                default_values = mod_dm.format_values(default_values, dtype)
            else:  # single condition supplied
                results = mod_dm.evaluate_operation(df, column_default)

                if isinstance(results, pd.Series):  # defaults are the values of another field in the collection
                    default_values = mod_dm.format_values(results, dtype)
                else:  # single default value supplied
                    default_values = mod_dm.format_value(results, dtype)

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
                default_values = mod_dm.evaluate_operation(df, rule)
            except Exception as e:
                msg = 'failed to evaluate rule expression {RULE} - {ERR}'.format(RULE=rule, ERR=e)
                logger.exception(msg)
            else:
                default_values = mod_dm.format_values(default_values, dtype).squeeze()
                df.loc[:, column] = default_values

        return df

    def _set_dtypes(self, df=None, dtypes: dict = None):
        """
        Set field data types based on header mapping.

        Arguments:
            df (DataFrame): set data types for the given dataframe instead of the collection dataframe. The alternative
                dataframe must have the same structure as the collection dataframe.

            dtypes (dict): provide a custom set of field data types to use instead of the collection set.
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
                column_values = mod_dm.format_values(column, dtype)
            except Exception as e:
                logger.exception('DataCollection {NAME}: unable to set field "{COL}" to data type "{DTYPE}" - {ERR}'
                                 .format(NAME=self.name, COL=column_name, DTYPE=dtype, ERR=e))
            else:
                try:
                    df.loc[:, column_name] = column_values
                except ValueError as e:
                    logger.warning('DataTable {NAME}: unable to set field "{COL}" to data type "{DTYPE}" - {ERR}'
                                   .format(NAME=self.name, COL=column_name, DTYPE=dtype, ERR=e))

        return df

    def _subset(self, on: pd.DataFrame = None):
        """
        Return the collections indices corresponding to the subset.

        Arguments:
            on (DataFrame): conditions specifying which entries should be selected. The number of entries should match
                the length of the value set [Default: return all indices of non-deleted entries].
        """
        df = self.data()

        # Find update indices based on the condition set
        if isinstance(on, pd.Series):
            if on.name in df.columns:
                on = on.to_frame()
                keys = on.columns.tolist()
                update_indices = get_row_intersection(df, on, keys)
            else:
                update_indices = on
        elif isinstance(on, dict):
            on = pd.DataFrame(on)
            keys = on.columns.tolist()
            update_indices = get_row_intersection(df, on, keys)
        elif isinstance(on, pd.DataFrame):
            keys = on.columns.tolist()
            update_indices = get_row_intersection(df, on, keys)
        else:
            update_indices = df.index

        return update_indices

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

        new_values = self.enforce_conformity(values)

        edited_rows = set()
        edited_cols = []
        for row_ind, row in new_values.iterrows():
            for column, row_value in row.iteritems():
                if column not in header:
                    continue

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
                column_values = mod_dm.format_values(current_vals, dtype)
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

    def data(self, current: bool = True, indices: list = None, on=None, edited_only: bool = False,
             deleted_only: bool = False, added_only: bool = False, drop_na: bool = False, fields: list = None):
        """
        Return the collection data.

        Arguments:
            current (bool): return only the current entries, excluding the deleted entries [Default: True].

            indices (list): return entries at the given indices [Default: None].

            on: conditions specifying how to select the proper indices based on collection field values. on and indices
                are mutually exclusive.

            edited_only (bool): return only the entries that have been edited [Default: False].

            deleted_only (bool): return only the entries that have been deleted from the collection [Default: False].

            added_only (bool): return only the entries that have been added to the collection [Default: False].

            drop_na (bool): drop columns with all NA/NULL values [Default: False].

            fields (list): return data only for the listed fields [Default: return all].

        Returns:
            df (DataFrame): data matching the selection requirements.
        """
        df = self.df.copy()
        dtypes = self.dtypes
        state_fields = [self._added_column, self._edited_column, self._deleted_column]
        if not (isinstance(fields, list) or isinstance(fields, tuple)):
            fields = list(dtypes)

        select_fields = [i for i in fields if i not in state_fields]

        if current and (indices is not None or deleted_only is True):
            current = False

        if current:
            deleted_indices = self._deleted_rows()
            df.drop(deleted_indices, inplace=True)

        if isinstance(indices, int):
            sub_inds = [indices]
        elif isinstance(indices, list) or isinstance(indices, tuple):
            sub_inds = indices
        elif on is not None:
            sub_inds = self._subset(on)
        else:
            sub_inds = df.index.tolist()

        df = df.loc[sub_inds]

        # Filter on edited rows, if desired
        if edited_only:  # all edited, current edited, or edited and deleted
            df = df[(df[self._added_column]) | (df[self._edited_column])]
        elif added_only:  # all added, current added, or added and then deleted
            df = df[df[self._added_column]]
        elif deleted_only:
            df = df[df[self._deleted_column]]

        # Remove the state fields from the data
        try:
            df = df[select_fields]
        except KeyError:
            print(df)
            print(select_fields)
            raise

        # Remove columns with all null values
        if drop_na:
            df.dropna(axis=1, how='all', inplace=True)

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
        add_df = add_df.copy()

        state_fields = {self._added_column: new,
                        self._edited_column: False,
                        self._deleted_column: False}

        if add_df.empty:  # no data to add
            return df

        # Convert add_df to dataframe
        if isinstance(add_df, pd.Series):
            add_df = add_df.to_frame().T
        elif isinstance(add_df, dict):
            add_df = pd.DataFrame(add_df)

        # Add the "state" columns to the new data, if not set
        for state_field in state_fields:
            if state_field not in add_df.columns:
                print('adding default for state field {}'.format(state_field))
                add_df.loc[:, state_field] = state_fields[state_field]  # default for the state
            else:
                print('using existing state values for state field {}'.format(state_field))

        # Enforce conformity of the new data
        add_df = self.enforce_conformity(add_df)

        # Drop columns that are not in the header
        extra_cols = [i for i in add_df.columns if i not in df.columns]
        add_df.drop(extra_cols, axis=1, inplace=True)

        # Check for violations of uniqueness among column values
        unq_cols = [i for i in add_df.columns if self._get_attr(i, 'unique') is True]
        for unq_col in unq_cols:
            add_vals = add_df[unq_col]
            dup_inds = add_vals[add_vals.isin(df[unq_col])].index
            print('indices at {} in the add dataframe violate the uniqueness conditions of field {}'.format(dup_inds, unq_col))

            add_df.drop(dup_inds, axis=0, inplace=True)

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

    def get_state(self, state_field, indices: list = None):
        """
        Get the value for the state field at the given indices.

        Arguments:
            state_field (str): retrieve the value of the given state field.

            indices (list): retrieve state values at the given indices [Default: all].
        """
        state_fields = self._state_fields
        try:
            field = state_fields[state_field]
        except KeyError:
            raise KeyError('field must be one of {}'.format(list(state_fields)))

        df = self.df.copy()

        if indices is None:
            indices = df.index

        state = df.loc[indices, field]

        return state.squeeze()

    def set_state(self, state_field, flag, indices: list = None, inplace: bool = True):
        """
        Set the value for the state field at the given indices.

        Arguments:
            state_field (str): set the value for the given state field.

            flag (bool): value to set the state field to.

            indices (list): set the state at the given indices [Default: all].

            inplace (bool): modify the state field in-place [Default: True].
        """
        state_fields = self._state_fields
        try:
            field = state_fields[state_field]
        except KeyError:
            raise KeyError('field must be one of {}'.format(list(state_fields)))

        if inplace:
            df = self.df
        else:
            df = self.df.copy()

        if indices is None:
            indices = df.index

        df.loc[indices, field] = flag

        return df

    def format_display(self, indices: list = None):
        """
        Format the table values for display.
        """
        if indices is not None:
            df = self.data(current=False, indices=indices)
        else:
            df = self.data()

        # Subset dataframe by specified columns to display
        display_df = pd.DataFrame()
        fields = self._fields
        for field in fields:
            try:
                col_to_add = self.format_display_field(field, data=df)
            except Exception as e:
                msg = 'failed to format field {COL} for display'.format(COL=field)
                logger.exception('DataCollection {NAME}: {MSG} - {ERR}'.format(NAME=self.name, MSG=msg, ERR=e))

                continue

            display_df[field] = col_to_add

        return display_df.astype('object').fillna('')

    def format_display_field(self, field, data=None):
        """
        Format the values of a collection field for display.

        Arguments:
            field (str): collection field to summarize.

            data (DataFrame): format field values for a custom subset of the data.
        """
        is_float_dtype = pd.api.types.is_float_dtype
        is_integer_dtype = pd.api.types.is_integer_dtype
        is_bool_dtype = pd.api.types.is_bool_dtype
        is_datetime_dtype = pd.api.types.is_datetime64_any_dtype
        is_string_dtype = pd.api.types.is_string_dtype

        aliases = self.aliases

        if data is None:
            df = self.data()
        else:
            df = data

        try:
            display_col = df[field]
        except KeyError:
            msg = 'field {COL} not found in the collection dataframe'.format(COL=field)
            logger.error('DataCollection {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))

            raise KeyError(msg)

        dtype = display_col.dtype
        if is_float_dtype(dtype) and self.dtypes[field] == 'money':
            display_col = display_col.apply(settings.format_display_money)
        elif is_datetime_dtype(dtype):
            display_col = display_col.apply(settings.format_display_date)
        elif is_bool_dtype(dtype):
            display_col = display_col.apply(lambda x: '✓' if x is True else '')
        elif is_integer_dtype(dtype) or is_string_dtype(dtype):
            if field in aliases:
                alias_map = aliases[field]
                display_col = display_col.apply(lambda x: alias_map[x] if x in alias_map else x)

        return display_col.astype('object').fillna('')

    def summarize_field(self, field, indices: list = None, statistic: str = None):
        """
        Summarize the values of a field.

        Arguments:
            field (str): collection field to summarize.

            indices (list): summarize a subset of the collection at the given indices.

            statistic (str): summarize the field using the provided statistic [Default: sum if field is a numeric
                data type else unique].
        """
        supported_stats = ['sum', 'count', 'product', 'mean', 'median', 'mode', 'min', 'max', 'std', 'unique']
        is_numeric_dtype = pd.api.types.is_numeric_dtype

        if statistic and statistic not in supported_stats:
            msg = 'unable to summarize field "{COL}" - unknown statistic {STAT} supplied' \
                .format(STAT=statistic, COL=field)
            logger.warning('DataCollection {NAME}: {MSG}'.format(NAME=self.name, MSG=msg))
            statistic = None

        if indices:
            df = self.data(current=False, indices=indices)
        else:
            df = self.data()

        try:
            col_values = df[field]
        except KeyError:
            logger.error('DataCollection {NAME}: unable to summarize field "{COL}" - {COL} not found in the collection'
                         .format(NAME=self.name, COL=field))

            return 0

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

    def fill(self, indices: list = None, fields: list = None, method: str = 'ffill'):
        """
        Fill field NA values in-place using the desired fill method.

        Arguments:
            indices (list): list of real indices to fill data on.

            fields (list): collection field with NA values to fill.

            method (str): method to use to fill gaps (NA values) in the data 'ffill', 'bfill', 'pad', or 'backfill'
                [Default: ffill].
        """
        edited = False
        df = self.df

        if not isinstance(indices, list):
            if isinstance(indices, pd.Series):
                indices = indices.tolist()
            else:  # default to all entries in the collection
                indices = df.index.tolist()

        if not isinstance(fields, list):
            if isinstance(fields, str):
                fields = [fields]
            elif isinstance(fields, pd.Series):
                fields = fields.tolist()
            else:  # default to all fields in collection
                fields = [i for i in df.columns.tolist() if i not in self._state_fields]

        logger.info('DataCollection {NAME}: filling fields {COL} rows {ROWS} using fill method "{METHOD}"'
                    .format(NAME=self.name, COL=fields, ROWS=len(indices), METHOD=method))

        if len(indices) <= 1:
            logger.warning('DataCollection {NAME}: unable to fill values - too few rows selected for '
                           'filling'.format(NAME=self.name))
            return False

        for field in fields:
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

    def subset(self, rule):
        """
        Subset the table based on a set of rules.
        """
        df = self.data()
        if df.empty:
            return df

        logger.debug('DataCollection {NAME}: sub-setting collection on rule {RULE}'
                     .format(NAME=self.name, RULE=rule))
        try:
            results = mod_dm.evaluate_condition(df, rule)
        except Exception as e:
            msg = 'failed to subset collection on rule {RULE}'.format(RULE=rule)
            logger.error('DataCollection {NAME}: {MSG} - {ERR}'.format(NAME=self.name, MSG=msg, ERR=e))

            raise ValueError(msg)

        subset_df = df[results]

        return subset_df

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

    def update_field(self, column, values, indices: list = None, on=None):
        """
        Update the entry values for a given field in-place.

        Arguments:
            column (str): name of the field to modify.

            values: list, series, or scalar of new field values.

            indices (list): optional list of entry indices to modify [Default: update all entries].

            on: conditions specifying how to select the proper indices for updating based on collection field values.
                on and indices are mutually exclusive.
        """
        df = self.df

        try:
            dtype = self.dtypes[column]
        except KeyError:
            msg = 'DataCollection {NAME}: failed to update column "{COL}" - {COL} is not a valid collection field' \
                .format(NAME=self.name, COL=column)
            raise IndexError(msg)

        if isinstance(indices, int):
            sub_inds = [indices]
        elif isinstance(indices, list) or isinstance(indices, tuple):
            sub_inds = indices
        elif on is not None:
            sub_inds = self._subset(on)
        else:  # update all field rows
            sub_inds = df.index.tolist()

        try:
            col_values = df.loc[sub_inds, column]
        except IndexError:
            msg = 'DataCollection {NAME}: failed to update column "{COL}" - one or more row indices from {INDS} are ' \
                  'missing from the table'.format(NAME=self.name, COL=column, INDS=sub_inds)
            raise IndexError(msg)

        if not isinstance(values, pd.Series):
            values = pd.Series(values, index=sub_inds)

        values = mod_dm.format_values(values, dtype)

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

        # Replace existing column values with new values and set dependant values
        df.loc[sub_inds, column] = values
        self._set_dependants(df=df)

        return edited_indices

    def update(self, update_df, inplace: bool = True):
        """
        Update a collection using another dataframe. Indices of the external dataframe should match the indices of the
        desired update entries.
        """
        df = self.df.copy()

        if update_df.empty:  # no data to add
            return df

        # Convert add_df to dataframe
        if isinstance(update_df, pd.Series):
            update_df = update_df.to_frame().T
        elif isinstance(update_df, dict):
            update_df = pd.DataFrame(update_df)

        # Edit the edited state field to show that the entries were modified from their original values
        update_df[self._edited_column] = True

        # Only update on common indices
        df.loc[update_df.index, update_df.columns] = update_df
        df = self._set_dtypes(df)  # the replace method does not preserve dtypes

        if inplace:
            self.df = df

        return df

    def transform(self, field, operator, value=None, inplace: bool = True):
        """
        Transform a field's values.
        """
        if inplace:
            df = self.df
        else:
            df = self.df.copy()

        if value is not None:
            math_operators = ('+', '-', '*', '/', '%')
            if operator not in math_operators:
                msg = 'failed to transform field "{COL}" values - unknown operator {OP} provided' \
                    .format(COL=field, OP=operator)
                logger.warning(msg)

                raise TypeError(msg)

            operation = '{COL} {OPER} {VAL}'.format(COL=field, OPER=operator, VAL=value)

            try:
                transformed_values = mod_dm.evaluate_operation(df, operation)
            except Exception as e:
                msg = 'failed to modify field "{COL}" based on modifier rule "{RULE}" - {ERR}' \
                    .format(COL=field, RULE=operation, ERR=e)
                logger.warning(msg)

                raise
        else:
            try:
                transformed_values = df[field].transform(operator)
            except Exception as e:
                msg = 'failed to transform field "{COL}" using transformation function "{RULE}" - {ERR}' \
                    .format(COL=field, RULE=operator, ERR=e)
                logger.warning(msg)

                raise

        df.loc[:, field] = transformed_values

        return transformed_values

    def list_fields(self):
        """
        Return a list of fields belonging to the collection.
        """
        return self._fields


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
        add_df = add_df.copy()
        id_col = self.id_column

        state_fields = {self._added_column: new,
                        self._edited_column: False,
                        self._deleted_column: False}

        if add_df.empty:  # no data to add
            return df

        # Convert add_df to dataframe
        if isinstance(add_df, pd.Series):
            add_df = add_df.to_frame().T
        elif isinstance(add_df, dict):
            add_df = pd.DataFrame(add_df)

        # Enforce conformity of the new data
        add_df = self.enforce_conformity(add_df)

        # Drop columns that are not in the header
        extra_cols = [i for i in add_df.columns if i not in df.columns]
        add_df.drop(extra_cols, axis=1, inplace=True)
        print('initial add dataframe for appending')
        print(add_df)

        # Find shared entries between the collection and the new data to add
        if not df.empty:
            df.set_index(id_col, inplace=True)
            add_df.set_index(id_col, inplace=True)

            common_inds = add_df.index.intersection(df.index).tolist()

            if len(common_inds) > 0:
                mod_df = add_df.loc[common_inds]
                mod_df.loc[:, [self._edited_column, self._deleted_column]] = [True, False]
                logger.debug('DataCollection {NAME}: modifying {NROW} entries in the collection'
                             .format(NAME=self.name, NROW=mod_df.shape[0]))

                real_inds = self.record_index(mod_df.index.tolist())
                mod_df = mod_df.reset_index().set_index(pd.Index(real_inds))
                df.reset_index(inplace=True)

                df.loc[mod_df.index, mod_df.columns] = mod_df
                #df = self._set_dtypes(df)  # the replace method does not preserve dtypes
            else:
                df.reset_index(inplace=True)

            # Find new entries to be appended to the collection
            new_df = add_df.loc[~add_df.index.isin(common_inds)]
            new_df.reset_index(inplace=True)

        else:  # collection is empty, so all data must be new
            new_df = add_df

        # Add the "state" columns to the new data, if not set
        for state_field in state_fields:
            if state_field not in new_df.columns:
                new_df.loc[:, state_field] = state_fields[state_field]  # default for the state

        logger.debug('DataCollection {NAME}: adding {NROW} entries to the collection'
                     .format(NAME=self.name, NROW=new_df.shape[0]))

        # Check for violations of uniqueness among column values
        unq_cols = [i for i in new_df.columns if self._get_attr(i, 'unique') is True]
        for unq_col in unq_cols:
            new_vals = new_df[unq_col]
            dup_inds = new_vals[new_vals.isin(df[unq_col])].index
            print('indices at {} in the add dataframe violate the uniqueness conditions of field {}'.format(dup_inds, unq_col))

            new_df.drop(dup_inds, axis=0, inplace=True)

        # Add new data to the collection
        df = df.append(new_df, ignore_index=reindex)

        if inplace:
            self.df = df

        return df

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

        if deleted or (indices is not None and len(indices) > 0):  # must include deleted rows if indices provided
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
                              'added': self._added_column}

        self.dtypes = {'RecordID': 'varchar', 'ReferenceID': 'varchar', 'ReferenceDate': 'date',
                       'RecordType': 'varchar', 'ReferenceType': 'varchar', 'IsApproved': 'bool',
                       'IsHardLink': 'bool', 'IsChild': 'bool', 'IsDeleted': 'bool', 'ReferenceWarnings': 'varchar',
                       'ReferenceNotes': 'varchar', self._deleted_column: 'bool', self._edited_column: 'bool',
                       self._added_column: 'bool'}

        self.df = self._set_dtypes(df=pd.DataFrame(columns=list(self.dtypes)))

    def get_index(self, record_ids, combined: bool = False):
        """
        Return a list of collection indices corresponding to the supplied record IDs.

        Arguments:
            record_ids (list): list of record IDs contained in the collection.

            combined (bool): record IDs and reference IDs are provided as one [Default: False].
        """
        df = self.df.copy()

        if isinstance(record_ids, str) or isinstance(record_ids, tuple):
            record_ids = [record_ids]
        elif isinstance(record_ids, pd.Series):
            record_ids = record_ids.tolist()

        if combined:
            indices = []
            for id_pair in record_ids:
                try:
                    record_id, ref_id = id_pair
                except ValueError:
                    msg = 'combined was set to True but both the record ID and reference ID was not provided in the ' \
                          'proper format'
                    raise ValueError(msg)
                pair_index = df[(df['RecordID'] == record_id) & (df['ReferenceID'] == ref_id)].index.tolist()
                indices.extend(pair_index)
        else:
            id_field = 'RecordID'
            indices = df.loc[df[id_field].isin(record_ids)].index.tolist()

        return indices

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
        add_df = add_df.copy()

        state_fields = {self._added_column: new,
                        self._edited_column: False,
                        self._deleted_column: False}

        if add_df.empty:  # no data to add
            return df

        # Convert add_df to dataframe
        if isinstance(add_df, pd.Series):
            add_df = add_df.to_frame().T
        elif isinstance(add_df, dict):
            add_df = pd.DataFrame(add_df)

        # Enforce conformity of the new data
        add_df = self.enforce_conformity(add_df)

        # Drop columns that are not in the header
        extra_cols = [i for i in add_df.columns if i not in df.columns]
        add_df.drop(extra_cols, axis=1, inplace=True)
        print('initial add dataframe for appending')
        print(add_df)

        # Find shared entries between the collection and the new data to add
        if not df.empty:
            df.set_index(['RecordID', 'ReferenceID'], inplace=True)
            add_df.set_index(['RecordID', 'ReferenceID'], inplace=True)

            common_inds = add_df.index.intersection(df.index).tolist()

            if len(common_inds) > 0:
                mod_df = add_df.loc[common_inds]
                mod_df.loc[:, [self._edited_column, self._deleted_column]] = [True, False]
                logger.debug('DataCollection {NAME}: modifying {NROW} entries in the collection'
                             .format(NAME=self.name, NROW=mod_df.shape[0]))

                real_inds = self.get_index(mod_df.index.tolist(), combined=True)
                mod_df = mod_df.reset_index().set_index(pd.Index(real_inds))
                df.reset_index(inplace=True)

                df.loc[mod_df.index, mod_df.columns] = mod_df
                #df = self._set_dtypes(df)  # the replace method does not preserve dtypes
            else:
                df.reset_index(inplace=True)

            # Find new entries to be appended to the collection
            new_df = add_df.loc[~add_df.index.isin(common_inds)]
            new_df.reset_index(inplace=True)

        else:  # collection is empty, so all data must be new
            new_df = add_df

        # Add the "state" columns to the new data, if not set
        for state_field in state_fields:
            if state_field not in new_df.columns:
                new_df.loc[:, state_field] = state_fields[state_field]  # default for the state

        logger.debug('DataCollection {NAME}: adding {NROW} entries to the collection'
                     .format(NAME=self.name, NROW=new_df.shape[0]))

        # Check for violations of uniqueness among column values
        unq_cols = [i for i in new_df.columns if self._get_attr(i, 'unique') is True]
        for unq_col in unq_cols:
            new_vals = new_df[unq_col]
            dup_inds = new_vals[new_vals.isin(df[unq_col])].index
            print('indices at {} in the add dataframe violate the uniqueness conditions of field {}'.format(dup_inds, unq_col))

            new_df.drop(dup_inds, axis=0, inplace=True)

        # Add new data to the collection
        df = df.append(new_df, ignore_index=reindex)

        if inplace:
            self.df = df

        return df

    def data(self, indices: list = None, on=None, edited: bool = None, added: bool = None, deleted: bool = False,
             drop_na: bool = False, fields: list = None, reference: bool = False, include_state: bool = False):
        """
        Return the collection data.

        Arguments:
            indices (list): return entries at the given indices [Default: None].

            on: conditions specifying how to select the proper indices based on collection field values. on and indices
                are mutually exclusive.

            edited (bool): return entries that have been edited [Default: None - don't filter on edited].

            deleted (bool): return entries that have been deleted from the collection [Default: False - don't return
                entries that have been set as "deleted"].

            added (bool): return entries that have been added to the collection [Default: None - don't filter on added].

            drop_na (bool): drop columns with all NA/NULL values [Default: False].

            fields (list): return data only for the listed fields [Default: return all].

            reference (bool): reverse the record and the reference information [Default: False].

            include_state (bool): include state fields in the output [Default: False].

        Returns:
            df (DataFrame): data matching the selection requirements.
        """
        df = self.df.copy()
        dtypes = self.dtypes

        add_field = self._added_column
        edit_field = self._edited_column
        del_field = self._deleted_column
        state_fields = {edit_field: edited, add_field: added, del_field: deleted}

        if not (isinstance(fields, list) or isinstance(fields, tuple)):
            fields = list(dtypes)

        select_fields = [i for i in fields if i not in state_fields] if not include_state else fields

        if isinstance(indices, int):
            sub_inds = [indices]
        elif isinstance(indices, list) or isinstance(indices, tuple):
            sub_inds = indices
        elif on is not None:
            sub_inds = self._subset(on)
        else:  # no subsetting specified, return all entries
            sub_inds = df.index.tolist()

        df = df.loc[sub_inds]

        # Filter by row state information
        include = []
        exclude = []
        for field in state_fields:
            field_state = state_fields[field]
            if field_state is True:
                include.append(field)
            elif field_state is False:
                exclude.append(field)

        n_include = len(include)
        n_exclude = len(exclude)
        if n_include > 0 and n_exclude > 0:
            state_filter = '({IN}) & ~({EX})'.format(IN='|'.join(include), EX='|'.join(exclude))
        elif n_include > 0 and n_exclude == 0:
            state_filter = '{IN}'.format(IN='|'.join(include))
        elif n_include == 0 and n_exclude > 0:
            state_filter = '~({EX})'.format(EX='|'.join(exclude))
        else:
            state_filter = None

        if state_filter is not None:
            df = df.query(state_filter)

        # Filter by selected fields, excluding state fields
        df = df[select_fields]

        # Remove columns with all null values
        if drop_na:
            df.dropna(axis=1, how='all', inplace=True)

        if reference:
            df.rename(columns={'RecordID': 'ReferenceID', 'ReferenceID': 'RecordID',
                               'RecordType': 'ReferenceType', 'ReferenceType': 'RecordType'}, inplace=True)

        return df


# Functions
def get_row_intersection(df1, df2, keys: list = None):
    """
    Find the row indices from the first dataframe where dataframe column values intersect.
    """
    if not keys:
        keys = list(set(df1.columns.tolist()).intersection(df2.columns.tolist()))

    i1 = df1.set_index(keys).index
    i2 = df2.set_index(keys).index
    indices = df1[i1.isin(i2)].index

    return indices