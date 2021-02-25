"""
REM records classes and functions. Includes audit records and account records.
"""
import datetime
from random import randint

import pandas as pd
import PySimpleGUI as sg

import REM.constants as mod_const
import REM.database as mod_db
import REM.elements as mod_elem
import REM.parameters as mod_param
from REM.config import configuration
from REM.settings import settings


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

    def __init__(self, name, entry, level: int = 0):
        """
        Arguments:
            name (str): configured record type.

            entry (class): configuration entry for the record.

            level (int): depth at which record was opened [Default: 0].
        """
        record_entry = configuration.records.fetch_rule(name)

        approved_record_types = ['transaction', 'account', 'bank_deposit', 'bank_statement', 'audit', 'cash_expense']
        self.name = name
        try:
            self.record_group = record_entry.group
        except AttributeError:
            self.record_group = None

        self.id = randint(0, 1000000000)
        self.elements = ['-{NAME}_{ID}_{ELEM}-'.format(NAME=self.name, ID=self.id, ELEM=i) for i in
                         ['RecordID', 'RecordDate', 'ReferencesButton', 'ReferencesFrame', 'ComponentsButton',
                          'ComponentsFrame', 'Height', 'Width']]

        self.record_layout = entry
        self.new = False
        self.level = level

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
            self.title = name

        self.record_id = None
        self.record_date = None
        self.creator = None
        self.creation_date = None
        self.editor = None
        self.edit_date = None

        # Record modifiers
        self.modifiers = []
        try:
            modifiers = entry['Modifiers']
        except KeyError:
            self.modifiers = []
        else:
            for param_name in modifiers:
                param_entry = modifiers[param_name]
                param_entry['ElementType'] = 'checkbox'
                param_entry['DataType'] = 'bool'
                param = mod_param.DataParameterCheckbox(param_name, param_entry)

                self.modifiers.append(param)
                self.elements += param.elements

        # Required record elements
        self.parameters = []
        try:
            details = entry['Details']
        except KeyError:
            raise AttributeError('missing required parameter "Details"'.format(NAME=self.name))
        else:
            try:
                parameters = details['Elements']
            except KeyError:
                raise AttributeError('missing required Details parameter "Elements"'.format(NAME=self.name))

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

                    # Format entry for table initialization
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
            print('Warning: No reference record types configured for {NAME}'.format(NAME=self.name))
        else:
            try:
                ref_elements = ref_entry['Elements']
            except KeyError:
                print('Configuration Warning: missing required References parameter "Elements"'.format(NAME=self.name))
            else:
                for ref_element in ref_elements:
                    if ref_element not in [i.name for i in configuration.records.rules]:
                        print('Configuration Error: RecordEntry {NAME}: reference {TYPE} must be a pre-configured '
                              'record type'.format(NAME=self.name, TYPE=ref_element))
                    else:
                        self.reference_types.append(ref_element)

        self.components = []
        self.component_types = []
        try:
            comp_entry = entry['Components']
        except KeyError:
            print('Warning: No component record types configured for {NAME}'.format(NAME=self.name))
        else:
            try:
                comp_elements = comp_entry['Elements']
            except KeyError:
                print('Configuration Warning: missing required References parameter "Elements"'.format(NAME=self.name))
            else:
                for comp_element in comp_elements:
                    if comp_element not in approved_record_types:
                        print('Configuration Error: RecordEntry {TYPE}: component table {TBL} must be an acceptable '
                              'record type'.format(TYPE=self.name, TBL=comp_element))
                        continue
                    table_entry = comp_elements[comp_element]
                    comp_table = mod_elem.TableElement(comp_element, table_entry, parent=self.name)
                    self.component_types.append(comp_table.record_type)
                    self.components.append(comp_table)
                    self.elements += comp_table.elements

        self.import_df = pd.DataFrame(columns=['DocNo', 'RefNo', 'RefDate', 'DocType', 'RefType'])

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

    def initialize(self, data, new: bool = False):
        """
        Initialize record attributes.

        Arguments:
            data (dict): dictionary or pandas series containing record data.

            new (bool): record is newly created [default: False].
        """
        is_datetime_dtype = pd.api.types.is_datetime64_any_dtype

        parameters = self.parameters
        modifiers = self.modifiers
        comp_types = self.component_types
        ref_types = self.reference_types

        self.new = new

        record_entry = configuration.records.fetch_rule(self.name)

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

        # Set attributes from required columns
        try:
            self.record_id = record_data['RecordID']
        except KeyError:
            raise AttributeError('input data is missing required column "RecordID"')

        try:
            record_date = record_data['RecordDate']
        except KeyError:
            raise AttributeError('input data is missing required column "RecordDate"')
        else:
            if is_datetime_dtype(record_date) or isinstance(record_date, datetime.datetime):
                self.record_date = record_date
            elif isinstance(record_date, str):
                try:
                    self.record_date = datetime.datetime.strptime(record_date, '%Y-%m-%d')
                except ValueError:
                    raise AttributeError('unknown format for "RecordDate" value {}'.format(record_date))
            else:
                raise AttributeError('unknown format for "RecordDate" value {}'.format(record_date))

        self.creator = record_data.get(configuration.creator_code, None)
        self.creation_date = record_data.get(configuration.creation_date, None)
        self.editor = record_data.get(configuration.editor_code, None)
        self.edit_date = record_data.get(configuration.edit_date, None)

        # Set modifier values
        if new is True:
            self.modifiers = []
        else:
            for modifier in modifiers:
                modifier_name = modifier.name

                try:
                    value = record_data[modifier_name]
                except KeyError:
                    print('Warning: record {ID}: input data is missing a value for modifier {COL}'
                          .format(ID=self.record_id, COL=modifier_name))
                else:
                    modifier.value = modifier.format_value({modifier_name: value})

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
                    print('Warning: record {ID}: input data is missing a value for data element {PARAM}'
                          .format(ID=self.record_id, PARAM=param_name))
                else:
                    if not pd.isna(value):
                        print('Info: record {ID}: setting element {PARAM} value to {VAL}'
                              .format(ID=self.record_id, PARAM=param_name, VAL=value))
                        param.value = param.format_value(value)
                    else:
                        print('Info: record {ID}: no value set for parameter {PARAM}'
                              .format(ID=self.record_id, PARAM=param_name))

        # Import components and references for existing records
        if new is False and self.record_id is not None and record_entry is not None:
            import_df = record_entry.import_references(self.record_id)
            for index, row in import_df.iterrows():
                doctype = row['DocType']
                reftype = row['RefType']

                # Store imported references as references box objects
                if doctype in ref_types:
                    ref_id = row['DocNo']
                    print('Info: record {ID}: adding reference record {NAME} with record type {TYPE}'
                          .format(ID=self.record_id, NAME=ref_id, TYPE=doctype))

                    try:
                        ref_box = mod_elem.ReferenceElement(doctype, row, parent=self.name)
                    except Exception as e:
                        print('Warning: record {ID}: failed to add reference {NAME} to list of references - {ERR}'
                              .format(ID=self.record_id, NAME=ref_id, ERR=e))
                        continue
                    else:
                        self.references.append(ref_box)
                        self.elements += ref_box.elements

                # Store imported components as table rows
                if reftype in comp_types:
                    ref_id = row['RefNo']
                    print('Info: record {ID}: adding component record {NAME} with record type {TYPE}'
                          .format(ID=self.record_id, NAME=ref_id, TYPE=reftype))

                    # Fetch the relevant components table
                    comp_table = self.fetch_component(reftype, by_type=True)

                    # Append record to the components table
                    comp_table.df = comp_table.import_row(ref_id)

            self.import_df = self.import_df.append(import_df, ignore_index=True)

    def reset(self, window):
        """
        Reset record attributes.
        """
        self.record_id = None
        self.record_date = None
        self.creator = None
        self.creation_date = None
        self.editor = None
        self.edit_date = None
        self.new = False

        # Reset modifier values
        for modifier in self.modifiers:
            modifier.reset(window)

        # Reset data element values
        for param in self.parameters:
            param.reset(window)

        # Reset components
        for comp_table in self.components:
            comp_table.reset(window)

        # Reset references
        self.references = []

    def run_event(self, window, event, values):
        """
        Perform a record action.
        """
        param_elems = [i for param in self.parameters for i in param.elements]
        modifier_elems = [i for modifier in self.modifiers for i in modifier.elements]
        component_elems = [i for component in self.components for i in component.elements]
        reference_elems = [i for reference in self.references for i in reference.elements]

        # Expand or collapse the references frame
        if event == self.key_lookup('ReferencesButton'):
            print('Info: RecordType {NAME}, Record {ID}: expanding / collapsing References frame'
                  .format(NAME=self.name, ID=self.record_id))
            self.collapse_expand(window, frame='references')

        # Expand or collapse the component tables frame
        elif event == self.key_lookup('ComponentsButton'):
            print('Info: RecordType {NAME}, Record {ID}: expanding / collapsing Components frame'
                  .format(NAME=self.name, ID=self.record_id))
            self.collapse_expand(window, frame='components')

        # Run a modifier event
        elif event in modifier_elems:
            try:
                param = self.fetch_modifier(event, by_key=True)
            except KeyError:
                print('Error: RecordType {NAME}, Record {ID}: unable to find modifier associated with event key {KEY}'
                      .format(NAME=self.name, ID=self.record_id, KEY=event))
            else:
                param.run_event(window, event, values)

        # Run a component element event
        elif event in param_elems:  # parameter event
            try:
                param = self.fetch_element(event, by_key=True)
            except KeyError:
                print('Error: RecordType {NAME}, Record {ID}: unable to find parameter associated with event key {KEY}'
                      .format(NAME=self.name, ID=self.record_id, KEY=event))
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
                print('Error: RecordType {NAME}, Record {ID}: unable to find component associated with event key {KEY}'
                      .format(NAME=self.name, ID=self.record_id, KEY=event))
            else:
                component_table.run_event(window, event, values)

        # Run a reference-box event
        elif event in reference_elems:
            try:
                refbox = self.fetch_reference(event, by_key=True)
            except KeyError:
                print('Error: RecordType {NAME}, Record {ID}: unable to find reference associated with event key {KEY}'
                      .format(NAME=self.name, ID=self.record_id, KEY=event))
            else:
                refbox.run_event(window, event, values)

        return True

    def fetch_element(self, element, by_key: bool = False):
        """
        Fetch a GUI data element by name or event key.
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
        Fetch a GUI data element by name or event key.
        """
        if by_key is True:
            element_type = element[1:-1].split('_')[-1]
            element_names = [i.key_lookup(element_type) for i in self.modifiers]
        else:
            element_names = [i.name for i in self.modifiers]

        if element in element_names:
            index = element_names.index(element)
            parameter = self.modifiers[index]
        else:
            raise KeyError('element {ELEM} not found in list of record {NAME} elements'
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
            references = [i.record_id for i in self.references]
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

    def table_values(self):
        """
        Format parameter values as a table row.
        """
        is_numeric_dtype = pd.api.types.is_numeric_dtype
        is_string_dtype = pd.api.types.is_string_dtype
        is_bool_dtype = pd.api.types.is_bool_dtype
        is_datetime_dtype = pd.api.types.is_datetime64_any_dtype

        parameters = self.parameters
        modifiers = self.modifiers

        columns = ['RecordID', 'RecordDate']
        values = [self.record_id, self.record_date]

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

    def header_layout(self):
        """
        Generate the layout for the header section of the record layout.
        """
        record_layout = self.record_layout

        header_elements = record_layout['Header']

        # Element parameters
        bg_col = mod_const.ACTION_COL

        main_font = mod_const.MAIN_FONT
        bold_font = mod_const.BOLD_LARGE_FONT

        pad_el = mod_const.ELEM_PAD
        pad_h = mod_const.HORZ_PAD

        # Header components
        try:
            id_title = header_elements.get('RecordID', 'Record ID')
        except KeyError:
            print('Warning: the parameter "RecordID" was not included in the list of configured data elements')
            id_title = 'ID'
        try:
            date_title = header_elements.get('RecordDate', 'Record Date')
        except KeyError:
            print('Warning: the parameter "RecordDate" was not included in the list of configured data elements')
            date_title = 'Date'

        if isinstance(self.record_date, datetime.datetime):
            record_date = settings.format_display_date(self.record_date)
        else:
            record_date = self.record_date

        id_tooltip = 'Created {TIME} by {NAME}'.format(NAME=self.creator, TIME=self.creation_date)
        id_layout = [[sg.Text('{}:'.format(id_title), pad=((0, pad_el), 0), background_color=bg_col, font=bold_font),
                      sg.Text(self.record_id, key=self.key_lookup('RecordID'), pad=((0, pad_h), 0), size=(14, 1),
                              font=main_font, background_color=bg_col, tooltip=id_tooltip,
                              metadata={'visible': True, 'disabled': False, 'value': self.record_id}),
                      sg.Text('{}:'.format(date_title), pad=((0, pad_el), 0), background_color=bg_col, font=bold_font),
                      sg.Text(record_date, key=self.key_lookup('RecordDate'), font=main_font,
                              background_color=bg_col, size=(14, 1),
                              metadata={'visible': True, 'disabled': False, 'value': self.record_date})]]

        # Header layout
        layout = [[sg.Col(id_layout, pad=(0, 0), background_color=bg_col, justification='l', expand_x=True)]]

        return layout

    def layout(self, win_size: tuple = None, view_only: bool = False, ugroup: list = None):
        """
        Generate a GUI layout for the account record.
        """
        if win_size:
            width, height = win_size
        else:
            width, height = (mod_const.WIN_WIDTH * 0.8, mod_const.WIN_HEIGHT * 0.8)

        record_layout = self.record_layout

        # GUI data elements
        editable = True if view_only is False or self.new is True else False
        ugroup = ugroup if ugroup is not None and len(ugroup) > 0 else ['admin']

        # Element parameters
        bg_col = mod_const.ACTION_COL
        text_col = mod_const.TEXT_COL

        bold_font = mod_const.BOLD_LARGE_FONT

        pad_el = mod_const.ELEM_PAD
        pad_v = mod_const.VERT_PAD
        pad_frame = mod_const.FRAME_PAD

        # Element sizes

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
        header_layout = self.header_layout()

        # Create layout for record details
        details_layout = []
        for data_elem in self.parameters:
            print(data_elem.name, data_elem.key_lookup('Element'))
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
        main_layout = [[sg.Canvas(size=(0, height), key=height_key, background_color=bg_col),
                        sg.Col(details_layout, pad=(0, 0), background_color=bg_col, expand_x=True, expand_y=True,
                               scrollable=True, vertical_scroll_only=True, vertical_alignment='t')]]

        # Pane elements must be columns
        width_key = self.key_lookup('Width')
        width_layout = [[sg.Canvas(size=(width, 0), key=width_key, background_color=bg_col)]]
        layout = [[sg.Col(width_layout, pad=(0, 0), background_color=bg_col)],
#                  [sg.Col(title_layout, background_color=header_col, expand_x=True)],
                  [sg.Col(header_layout, pad=(pad_frame, (pad_frame, 0)), background_color=bg_col, expand_x=True)],
                  [sg.HorizontalSeparator(pad=(pad_frame, (pad_v, pad_frame)), color=mod_const.INACTIVE_COL)],
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

        print('Info: record {ID}: resizing display to {W}, {H}'.format(ID=self.record_id, W=width, H=height))

        # Expand the frame width and height
        width_key = self.key_lookup('Width')
        window[width_key].set_size((width, None))

        height_key = self.key_lookup('Height')
        window[height_key].set_size((None, height))
        window.bind("<Configure>", window[height_key].Widget.config(height=int(height)))

        # Expand the size of multiline parameters
        for param in self.parameters:
            param_type = param.etype
            if param_type == 'multiline':
                param_size = (int((width - width % 9) / 9) - int((64 - 64 % 9)/9), None)
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

    def update_display(self, window, window_values: dict = None):
        """
        Update the display of the record's elements and components.
        """
        for param in self.parameters:
            param.update_display(window, window_values=window_values)

        # Update the components display table
        for component in self.components:
            component.update_display(window, window_values=window_values)

        # Update records header
        id_key = self.key_lookup('RecordID')
        date_key = self.key_lookup('RecordDate')
        record_id = self.record_id
        record_date = settings.format_display_date(self.record_date)
        window[id_key].set_size(size=(len(record_id) + 1, None))
        window[id_key].update(value=record_id)
        window[date_key].set_size(size=(len(record_date) + 1, None))
        window[date_key].update(value=record_date)

        id_tooltip = '{ID} created {TIME} by {NAME}'.format(ID=record_id, NAME=self.creator, TIME=self.creation_date)
        window[id_key].set_tooltip(id_tooltip)

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
            window[hide_key].update(image_data=mod_const.UNHIDE_ICON)
            window[frame_key].update(visible=False)

            window[frame_key].metadata['visible'] = False
        else:  # not visible yet, so want to expand the frame
            window[hide_key].update(image_data=mod_const.HIDE_ICON)
            window[frame_key].update(visible=True)

            window[frame_key].metadata['visible'] = True


class DepositRecord(DatabaseRecord):
    """
    Class to manage the layout and display of an REM Deposit Record.
    """

    def __init__(self, name, entry, level: int = 0):
        """
        deposit (float): amount deposited into the bank account.
        """
        super().__init__(name, entry, level)
        self.elements.append('-{NAME}_{ID}_{ELEM}-'.format(NAME=self.name, ID=self.id, ELEM='Deposit'))

        self.deposit = 0

    def header_layout(self):
        """
        Generate the layout for the header section of the record layout.
        """
        greater_col = mod_const.PASS_COL
        lesser_col = mod_const.FAIL_COL

        record_layout = self.record_layout

        header_elements = record_layout['Header']

        # Element parameters
        bg_col = mod_const.ACTION_COL

        main_font = mod_const.MAIN_FONT
        bold_font = mod_const.BOLD_LARGE_FONT

        pad_el = mod_const.ELEM_PAD
        pad_h = mod_const.HORZ_PAD

        # Header components
        try:
            id_title = header_elements.get('RecordID', 'Record ID')
        except KeyError:
            print('Warning: the parameter "RecordID" was not included in the list of configured data elements')
            id_title = 'ID'
        try:
            date_title = header_elements.get('RecordDate', 'Record Date')
        except KeyError:
            print('Warning: the parameter "RecordDate" was not included in the list of configured data elements')
            date_title = 'Date'

        if isinstance(self.record_date, datetime.datetime):
            record_date = settings.format_display_date(self.record_date)
        else:
            record_date = self.record_date

        id_tooltip = 'Created {TIME} by {NAME}'.format(NAME=self.creator, TIME=self.creation_date)
        id_layout = [[sg.Text('{}:'.format(id_title), pad=((0, pad_el), 0), background_color=bg_col, font=bold_font),
                      sg.Text(self.record_id, key=self.key_lookup('RecordID'), pad=((0, pad_h), 0), size=(14, 1),
                              font=main_font, background_color=bg_col, tooltip=id_tooltip),
                      sg.Text('{}:'.format(date_title), pad=((0, pad_el), 0), background_color=bg_col, font=bold_font),
                      sg.Text(record_date, key=self.key_lookup('RecordDate'), size=(14, 1), font=main_font,
                              background_color=bg_col)]]
        try:
            deposit_title = header_elements.get('DepositAmount', 'Deposit Total')
        except KeyError:
            print('Warning: the parameter "DepositAmount" was not included in the list of configured data elements')
            deposit_title = 'Deposit Total'

        deposit_total = self.deposit
        if deposit_total > 0:
            bg_color = greater_col
        elif deposit_total < 0:
            bg_color = lesser_col
        else:
            bg_color = bg_col
        deposit_layout = [[sg.Text('{}:'.format(deposit_title), pad=((0, pad_el), 0), background_color=bg_col,
                                   font=bold_font),
                           sg.Text('{:,.2f}'.format(deposit_total), key=self.key_lookup('Deposit'),
                                   size=(14, 1), font=main_font, background_color=bg_color, border_width=1,
                                   relief="sunken", tooltip='Import amount: {}'.format('{:,.2f}'.format(deposit_total)))]]

        # Header layout
        layout = [[sg.Col(id_layout, pad=(0, 0), background_color=bg_col, justification='l', expand_x=True),
                   sg.Col([[sg.Canvas(size=(0, 0), visible=True)]],
                          background_color=bg_col, justification='c', expand_x=True),
                   sg.Col(deposit_layout, background_color=bg_col, justification='r')]]

        return layout

    def table_values(self):
        """
        Format parameter values as a table row.
        """
        is_numeric_dtype = pd.api.types.is_numeric_dtype
        is_string_dtype = pd.api.types.is_string_dtype
        is_bool_dtype = pd.api.types.is_bool_dtype
        is_datetime_dtype = pd.api.types.is_datetime64_any_dtype

        parameters = self.parameters
        modifiers = self.modifiers

        columns = ['RecordID', 'RecordDate', 'DepositAmount']
        values = [self.record_id, self.record_date, self.deposit]

        # Add modifier values
        for modifier in modifiers:
            columns.append(modifier.name)
            values.append(modifier.value)

        # Add parameter values
        for param in parameters:
            param_type = param.etype
            if param_type == 'table':
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
            else:
                columns.append(param.name)
                values.append(param.value)

        return pd.Series(values, index=columns)

    def run_event(self, window, event, values):
        """
        Perform a record action.
        """
        param_elems = [i for param in self.parameters for i in param.elements]
        modifier_elems = [i for modifier in self.modifiers for i in modifier.elements]
        component_elems = [i for component in self.components for i in component.elements]
        reference_elems = [i for reference in self.references for i in reference.elements]

        # Collapse or expand the references frame
        if event == self.key_lookup('ReferencesButton'):
            print('Info: {NAME}, Record {ID}: expanding / collapsing References frame'
                  .format(NAME=self.name, ID=self.record_id))
            self.collapse_expand(window, frame='references')

        # Collapse or expand the component tables frame
        elif event == self.key_lookup('ComponentsButton'):
            print('Info: {NAME}, Record {ID}: expanding / collapsing Components frame'
                  .format(NAME=self.name, ID=self.record_id))
            self.collapse_expand(window, frame='components')

        # Run a modifier event
        elif event in modifier_elems:
            try:
                param = self.fetch_modifier(event, by_key=True)
            except KeyError:
                print('Error: RecordType {NAME}, Record {ID}: unable to find modifier associated with event key {KEY}'
                      .format(NAME=self.name, ID=self.record_id, KEY=event))
            else:
                param.run_event(window, event, values)

        # Run a data element event
        elif event in param_elems:  # parameter event
            try:
                param = self.fetch_element(event, by_key=True)
            except KeyError:
                print('Error: record {ID}: unable to find parameter associated with event key {KEY}'
                      .format(ID=self.record_id, KEY=event))
            else:
                param.run_event(window, event, values)

        elif event in component_elems:  # component table event
            # Update data elements
            for param in self.parameters:
                param.update_display(window, window_values=values)

            try:
                component_table = self.fetch_component(event, by_key=True)
            except KeyError:
                print('Error: record {ID}: unable to find component associated with event key {KEY}'
                      .format(ID=self.record_id, KEY=event))
            else:
                # Check if component table is an account table
                comp_record_type = component_table.record_type
                if comp_record_type in configuration.records.group_elements('account'):
                    if event == component_table.key_lookup('Import'):  # import account records
                        comp_entry = configuration.records.fetch_rule(comp_record_type)

                        # Filter out import records that are already referenced
                        referenced_ids = self.import_df['RefType' == comp_record_type]['RefNo'].tolist()
                        id_col = mod_db.get_import_column(comp_entry.import_rules, 'RecordID')
                        filters = [('{COL} NOT IN ({IDS})'
                                    .format(COL=id_col, IDS=','.join(['?' for _ in referenced_ids])),
                                   referenced_ids)]

                        # Filter component records with payment type different from parent payment type
                        payment_col = mod_db.get_import_column(comp_entry.import_rules, 'PaymentType')
                        filters += [('{COL} = ?'.format(COL=payment_col), (self.fetch_element('PaymentType').value,))]

                        component_table.df = component_table.import_rows(filter_rules=filters, program_database=True)
                    elif event == component_table.key_lookup('Add'):  # add account records
                        default_values = {i.name: i.value for i in self.parameters if i.etype != 'table'}
                        component_table.df = component_table.add_row(record_date=self.record_date,
                                                                     defaults=default_values)
                    else:
                        component_table.run_event(window, event, values)
                else:
                    component_table.run_event(window, event, values)

                self.update_display(window, window_values=values)

        elif event in reference_elems:
            try:
                refbox = self.fetch_reference(event, by_key=True)
            except KeyError:
                print('Error: record {ID}: unable to find reference associated with event key {KEY}'
                      .format(ID=self.record_id, KEY=event))
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

        # Update records header
        id_key = self.key_lookup('RecordID')
        date_key = self.key_lookup('RecordDate')
        record_id = self.record_id
        record_date = settings.format_display_date(self.record_date)
        window[id_key].set_size(size=(len(record_id) + 1, None))
        window[id_key].update(value=record_id)
        window[date_key].set_size(size=(len(record_date) + 1, None))
        window[date_key].update(value=record_date)

        id_tooltip = '{ID} created {TIME} by {NAME}'.format(ID=record_id, NAME=self.creator, TIME=self.creation_date)
        window[id_key].set_tooltip(id_tooltip)

        # Update the deposit total
        try:
            account_table = self.fetch_component('account')
        except KeyError:
            print('Configuration Error: RecordEntry {TYPE}: missing required component records of type "account"'
                  .format(TYPE=self.name))
            account_total = 0
        else:
            account_total = account_table.calculate_total()
            print('Info: record {ID}: total income was calculated from the accounts table is {VAL}'
                  .format(ID=self.record_id, VAL=account_total))

        try:
            expense_table = self.fetch_component('cash_expense')
        except KeyError:
            print('Configuration Error: RecordEntry {TYPE}: missing component records of type "cash_expense"'
                  .format(TYPE=self.name))
            expense_total = 0
        else:
            expense_total = expense_table.calculate_total()
            print('Info: record {ID}: total expenditures was calculated from the expense table to be {VAL}'
                  .format(ID=self.record_id, VAL=expense_total))

        deposit_total = account_total - expense_total

        if deposit_total > 0:
            bg_color = greater_col
        elif deposit_total < 0:
            bg_color = lesser_col
        else:
            bg_color = default_col

        window[self.key_lookup('Deposit')].update(value='{:,.2f}'.format(deposit_total), background_color=bg_color)
        self.deposit = deposit_total


class TAuditRecord(DatabaseRecord):
    """
    Class to manage the layout of an audit record.
    """

    def __init__(self, name, entry, level: int = 0):
        """
        remainder (float): remaining total after subtracting component record totals.
        """
        super().__init__(name, entry, level)
        for element in ['Remainder']:
            self.elements.append('-{NAME}_{ID}_{ELEM}-'.format(NAME=self.name, ID=self.id, ELEM=element))

        self.remainder = 0.00

    def header_layout(self):
        """
        Generate the layout for the header section of the record layout.
        """
        greater_col = mod_const.PASS_COL
        lesser_col = mod_const.FAIL_COL

        record_layout = self.record_layout

        header_elements = record_layout['Header']

        # Element parameters
        bg_col = mod_const.ACTION_COL
        text_col = mod_const.TEXT_COL

        main_font = mod_const.MAIN_FONT
        bold_font = mod_const.BOLD_LARGE_FONT

        pad_el = mod_const.ELEM_PAD
        pad_h = mod_const.HORZ_PAD

        # Header components
        id_title = header_elements.get('RecordID', 'Record ID')
        date_title = header_elements.get('RecordDate', 'Record Date')

        if isinstance(self.record_date, datetime.datetime):
            record_date = settings.format_display_date(self.record_date)
        else:
            record_date = self.record_date

        id_tooltip = 'Created {TIME} by {NAME}'.format(NAME=self.creator, TIME=self.creation_date)
        id_layout = [[sg.Text('{}:'.format(id_title), pad=((0, pad_el), 0), background_color=bg_col, font=bold_font),
                      sg.Text(self.record_id, key=self.key_lookup('RecordID'), pad=((0, pad_h), 0), size=(14, 1),
                              font=main_font, background_color=bg_col, tooltip=id_tooltip),
                      sg.Text('{}:'.format(date_title), pad=((0, pad_el), 0), background_color=bg_col, font=bold_font),
                      sg.Text(record_date, key=self.key_lookup('RecordDate'), pad=((0, pad_h), 0),
                              size=(14, 1), font=main_font, background_color=bg_col)]]
        try:
            remainder_title = header_elements.get('Remainder', 'Remainder')
        except KeyError:
            print('Warning: the parameter "Remainder" was not included in the list of configured data elements')
            remainder_title = 'Remainder'

        remainder = self.remainder
        if remainder > 0:
            print('Info: {NAME}, record {ID}: account records are under-allocated by {AMOUNT}'
                  .format(NAME=self.name, ID=self.record_id, AMOUNT=remainder))
            bg_color = greater_col
        elif remainder < 0:
            print('Info: {NAME}, record {ID}: account records are over-allocated by {AMOUNT}'
                  .format(NAME=self.name, ID=self.record_id, AMOUNT=abs(remainder)))
            bg_color = lesser_col
        else:
            bg_color = bg_col
        remainder_layout = [[sg.Text('{}:'.format(remainder_title), pad=((0, pad_el), 0), background_color=bg_col,
                                     font=bold_font),
                             sg.Text('{:,.2f}'.format(remainder), key=self.key_lookup('Remainder'),
                                     size=(14, 1), font=main_font, background_color=bg_color, border_width=1,
                                     relief="sunken",
                                     tooltip='Import amount: {}'.format('{:,.2f}'.format(remainder)))]]

        # Header layout
        layout = [[sg.Col(id_layout, pad=(0, 0), background_color=bg_col, justification='l', expand_x=True),
                   sg.Col([[sg.Canvas(size=(0, 0), visible=True)]],
                          background_color=bg_col, justification='c', expand_x=True),
                   sg.Col(remainder_layout, background_color=bg_col, justification='r')]]

        return layout

    def table_values(self):
        """
        Format parameter values as a table row.
        """
        is_numeric_dtype = pd.api.types.is_numeric_dtype
        is_string_dtype = pd.api.types.is_string_dtype
        is_bool_dtype = pd.api.types.is_bool_dtype
        is_datetime_dtype = pd.api.types.is_datetime64_any_dtype

        parameters = self.parameters
        modifiers = self.modifiers

        columns = ['RecordID', 'RecordDate', 'Remainder']
        values = [self.record_id, self.record_date, self.remainder]

        # Add modifier values
        for modifier in modifiers:
            columns.append(modifier.name)
            values.append(modifier.value)

        # Add parameter values
        for param in parameters:
            param_type = param.etype
            if param_type == 'table':
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
            else:
                columns.append(param.name)
                values.append(param.value)

        return pd.Series(values, index=columns)

    def run_event(self, window, event, values):
        """
        Perform a record action.
        """
        param_elems = [i for param in self.parameters for i in param.elements]
        modifier_elems = [i for modifier in self.modifiers for i in modifier.elements]
        component_elems = [i for component in self.components for i in component.elements]
        reference_elems = [i for reference in self.references for i in reference.elements]

        if event == self.key_lookup('ReferencesButton'):
            print('Info: table {TBL}: expanding / collapsing References frame'.format(TBL=self.name))
            self.collapse_expand(window, frame='references')

        elif event == self.key_lookup('ComponentsButton'):
            print('Info: table {TBL}: expanding / collapsing Components frame'.format(TBL=self.name))
            self.collapse_expand(window, frame='components')

        # Run a modifier event
        elif event in modifier_elems:
            try:
                param = self.fetch_modifier(event, by_key=True)
            except KeyError:
                print('Error: RecordType {NAME}, Record {ID}: unable to find modifier associated with event key {KEY}'
                      .format(NAME=self.name, ID=self.record_id, KEY=event))
            else:
                param.run_event(window, event, values)

        # Run a data element event
        elif event in param_elems:
            try:
                param = self.fetch_element(event, by_key=True)
            except KeyError:
                print('Error: record {ID}: unable to find parameter associated with event key {KEY}'
                      .format(ID=self.record_id, KEY=event))
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
                print('Error: record {ID}: unable to find component associated with event key {KEY}'
                      .format(ID=self.record_id, KEY=event))
            else:
                # Check if component table is an account table
                comp_record_type = component_table.record_type
                if comp_record_type in configuration.records.group_elements('account'):
                    if event == component_table.key_lookup('Import'):  # import account records
                        comp_entry = configuration.records.fetch_rule(comp_record_type)

                        # Filter out import records that are already referenced
                        referenced_ids = self.import_df['RefType' == comp_record_type]['RefNo'].tolist()
                        id_col = mod_db.get_import_column(comp_entry.import_rules, 'RecordID')
                        filters = [('{COL} NOT IN ({IDS})'
                                    .format(COL=id_col, IDS=','.join(['?' for _ in referenced_ids])),
                                    referenced_ids)]

                        # Filter component records with the same record date
                        date_col = mod_db.get_import_column(comp_entry.import_rules, 'RecordDate')
                        filters += [('{COL} = ?'.format(COL=date_col), (self.record_date,))]

                        component_table.df = component_table.import_rows(filter_rules=filters, program_database=True)
                    elif event == component_table.key_lookup('Add'):  # add account records
                        default_values = {i.name: i.value for i in self.parameters if i.etype != 'table'}
                        component_table.df = component_table.add_row(record_date=self.record_date,
                                                                     defaults=default_values)
                    else:
                        component_table.run_event(window, event, values)
                else:
                    component_table.run_event(window, event, values)

                self.update_display(window, window_values=values)

        elif event in reference_elems:
            try:
                refbox = self.fetch_reference(event, by_key=True)
            except KeyError:
                print('Error: record {ID}: unable to find reference associated with event key {KEY}'
                      .format(ID=self.record_id, KEY=event))
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

        # Update the record's header
        record_id = self.record_id
        id_tooltip = '{ID} created {TIME} by {NAME}'.format(ID=record_id, NAME=self.creator, TIME=self.creation_date)
        id_key = self.key_lookup('RecordID')
        window_element = window.find_element(id_key, silent_on_error=False)
        try:
            window_element.set_size(size=(len(record_id) + 1, None))
        except TypeError:
            window_element.set_size(size=(14, None))

        window_element.update(value=record_id)
        window_element.set_tooltip(id_tooltip)

        date_key = self.key_lookup('RecordDate')
        try:
            record_date = settings.format_display_date(self.record_date)
        except AttributeError:
            record_date = None
        window_element = window.find_element(date_key, silent_on_error=False)
        try:
            window_element.set_size(size=(len(record_date) + 1, None))
        except TypeError:
            window_element.set_size(size=(14, None))
        window_element.update(value=record_date)

        # Update the remainder
        totals_table = self.fetch_element('Totals')
        totals_sum = totals_table.calculate_total()

        try:
            account_table = self.fetch_component('account')
        except KeyError:
            print('Configuration Error: missing required component records of type "account"')
            account_total = 0
        else:
            account_total = account_table.calculate_total()

        remainder = totals_sum - account_total

        if remainder > 0:
            print('Info: {NAME}, record {ID}: account records are under-allocated by {AMOUNT}'
                  .format(NAME=self.name, ID=self.record_id, AMOUNT=remainder))
            bg_color = greater_col
        elif remainder < 0:
            print('Info: {NAME}, record {ID}: account records are over-allocated by {AMOUNT}'
                  .format(NAME=self.name, ID=self.record_id, AMOUNT=abs(remainder)))
            bg_color = lesser_col
        else:
            bg_color = default_col

        window_element = window.find_element(self.key_lookup('Remainder'), silent_on_error=False)
        window_element.update(value='{:,.2f}'.format(remainder), background_color=bg_color)

        self.remainder = remainder


def load_record(record_entry, record_id, level: int = 1):
    """
    Load an existing record from the program database.
    """
    # Extract the record data from the database
    import_df = record_entry.load_record_data(record_id)

    # Set the record object based on the record type
    record_type = record_entry.group
    if record_type in ('account', 'bank_statement', 'cash_expense'):
        record_class = DatabaseRecord
    elif record_type == 'bank_deposit':
        record_class = DepositRecord
    elif record_type == 'audit':
        record_class = TAuditRecord
    else:
        print('Warning: unknown record layout type provided {}'.format(record_type))
        return None

    record = record_class(record_entry.name, record_entry.record_layout, level=level)
    record.initialize(import_df)

    return record


def create_record(record_entry, record_data, level: int = 1):
    """
    Create a new database record.
    """
    record_type = record_entry.group
    if record_type in ('account', 'transaction', 'bank_statement', 'cash_expense'):
        record_class = DatabaseRecord
    elif record_type == 'bank_deposit':
        record_class = DepositRecord
    elif record_type == 'audit':
        record_class = TAuditRecord
    else:
        print('Warning: unknown record layout type provided {}'.format(record_type))
        return None

    record = record_class(record_entry.name, record_entry.record_layout, level=level)
    record.initialize(record_data, new=True)

    return record


def remove_unsaved_keys(record):
    """
    Remove any unsaved IDs associated with the record, including the records own ID.
    """
    # Remove unsaved ID if record is new
    if record.new is True:
        record_entry = configuration.records.fetch_rule(record.name)
        record_entry.remove_unsaved_id(record.record_id)

    # Remove unsaved components
    for comp_table in record.components:
        comp_type = comp_table.record_type
        if comp_type is None:
            continue
        else:
            comp_entry = configuration.records.fetch_rule(comp_type)

        for index, row in comp_table.df.iterrows():
            row_id = row[comp_table.id_column]
            comp_entry.remove_unsaved_id(row_id)
