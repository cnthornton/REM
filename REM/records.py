"""
REM records classes and functions. Includes audit records and account records.
"""
import datetime
from random import randint

import numpy as np
import pandas as pd
import PySimpleGUI as sg

import REM.constants as mod_const
import REM.elements as mod_elem
import REM.layouts as mod_lo
import REM.secondary as mod_win2
from REM.config import configuration, settings


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

    def __init__(self, name, entry, record_data, new_record: bool = False, referenced: bool = False):
        """
        Arguments:
            name (str): configured record type.

            entry (class): configuration entry for the record.

            record_data (dict): dictionary or pandas series containing record data.

            new_record (bool): record is newly created [default: False].
        """
        is_datetime_dtype = pd.api.types.is_datetime64_any_dtype
        record_entry = configuration.records.fetch_rule(name)

        approved_record_types = ['transaction', 'account', 'bank_deposit', 'bank_statement', 'audit', 'cash_expense']
        self.name = name
        self.record_group = record_entry.group

        self.id = randint(0, 1000000000)
        self.elements = ['{NAME}_{ID}_{ELEM}'.format(NAME=self.name, ID=self.id, ELEM=i) for i in
                         ['Delete', 'Save', 'RecordID', 'RecordDate', 'MarkedForDeletion', 'Approved',
                          'ReferencesButton', 'ReferencesFrame', 'ComponentsButton', 'ComponentsFrame', 'Height',
                          'Width']]

        self.record_layout = entry
        self.new = new_record
        self.referenced = referenced
        print('record type {} is a reference link: {}'.format(self.name, self.referenced))

        # User permissions when accessing record
        try:
            permissions = entry['Permissions']
        except KeyError:
            self.permissions = {'edit': 'admin', 'delete': 'admin', 'mark': 'admin', 'unlink': 'admin',
                                'approve': 'admin'}
        else:
            self.permissions = {'edit': permissions.get('Edit', 'admin'),
                                'delete': permissions.get('Delete', 'admin'),
                                'mark': permissions.get('MarkForDeletion', 'admin'),
                                'unlink': permissions.get('RemoveAssociations', 'admin'),
                                'approve': permissions.get('Approve', 'admin')}

        if isinstance(record_data, pd.Series):
            record_data = record_data.to_dict()
        elif isinstance(record_data, dict):
            record_data = record_data
        elif isinstance(record_data, pd.DataFrame):
            if record_data.shape[0] > 1:
                raise AttributeError('more than one record provided to record class {TYPE}'.format(TYPE=self.name))
            elif record_data.shape[0] < 1:
                raise AttributeError('empty dataframe provided to record class {TYPE}'.format(TYPE=self.name))
            else:
                record_data = record_data.iloc[0]
        else:
            raise AttributeError('unknown object type provided to record class {TYPE}'.format(TYPE=self.name))

        try:
            self.record_id = record_data['RecordID']
        except KeyError:
            self.record_id = None

        try:
            record_date = record_data['RecordDate']
        except KeyError:
            self.record_date = None
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

        self.deleted = record_data.get('Deleted', False)
        self.marked_for_deletion = record_data.get('MarkedForDeletion', None)
        self.approved = record_data.get('Approved', None)

        self.creator = record_data.get(configuration.creator_code, None)
        self.creation_date = record_data.get(configuration.creation_date, None)
        self.editor = record_data.get(configuration.editor_code, None)
        self.edit_date = record_data.get(configuration.edit_date, None)

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

                if param_type == 'table':  # parameter is a data table
                    param_cols = list(param_obj.columns)
                    table_data = pd.Series(index=param_cols)
                    for param_col in param_cols:
                        try:
                            table_data[param_col] = record_data[param_col]
                        except KeyError:
                            continue

                    param_obj.df = param_obj.df.append(table_data, ignore_index=True)
                else:  # parameter is a data element
                    try:
                        param_value = record_data[param]
                    except KeyError:
                        print('Warning: record {ID}: imported data is missing a column for parameter {PARAM}'
                              .format(ID=self.record_id, PARAM=param))
                    else:
                        if not pd.isna(param_value):
                            print('Info: record {ID}: setting element {PARAM} value to {VAL}'
                                  .format(ID=self.record_id, PARAM=param_obj.name, VAL=param_value))
                            param_obj.value = param_obj.format_value(param_value)
                        else:
                            print('Info: record {ID}: no value set for parameter {PARAM}'
                                  .format(ID=self.record_id, PARAM=param_obj.name))

                # Add the parameter to the record
                self.parameters.append(param_obj)
                self.elements += param_obj.elements

        self.references = []
        try:
            ref_entry = entry['References']
        except KeyError:
            print('Warning: No reference record types configured for {NAME}'.format(NAME=self.name))
            ref_elements = []
        else:
            try:
                ref_elements = ref_entry['Elements']
            except KeyError:
                print('Configuration Warning: missing required References parameter "Elements"'.format(NAME=self.name))
                ref_elements = []

        self.components = []
        try:
            comp_entry = entry['Components']
        except KeyError:
            print('Warning: No component record types configured for {NAME}'.format(NAME=self.name))
            comp_types = []
        else:
            try:
                comp_elements = comp_entry['Elements']
            except KeyError:
                print('Configuration Warning: missing required References parameter "Elements"'.format(NAME=self.name))
                comp_types = []
            else:
                comp_types = []
                for comp_element in comp_elements:
                    if comp_element not in approved_record_types:
                        print('Configuration Error: RecordEntry {TYPE}: component table {TBL} must be an acceptable '
                              'record type'.format(TYPE=self.name, TBL=comp_element))
                        continue
                    table_entry = comp_elements[comp_element]
                    comp_table = mod_elem.TableElement(comp_element, table_entry, parent=self.name)
                    comp_types.append(comp_table.record_type)
                    self.components.append(comp_table)
                    self.elements += comp_table.elements

        # Import components and references for existing records
        if new_record is False:
            ref_rows = record_entry.import_references(self.record_id)
            for index, row in ref_rows.iterrows():
                doctype = row['DocType']
                reftype = row['RefType']

                # Store imported references as references box objects
                if doctype in ref_elements:
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

    def key_lookup(self, component):
        """
        Lookup a component's GUI element key using the component's name.
        """
        element_names = [i.split('_')[-1] for i in self.elements]
        if component in element_names:
            key_index = element_names.index(component)
            key = self.elements[key_index]
        else:
            raise KeyError('component {COMP} not found in list of record {NAME} components'
                           .format(COMP=component, NAME=self.name))

        return key

    def run_event(self, window, event, values, user):
        """
        Perform a record action.
        """
        save_key = self.key_lookup('Save')
        delete_key = self.key_lookup('Delete')
        approved_key = self.key_lookup('Approved')
        marked_key = self.key_lookup('MarkedForDeletion')

        param_elems = [i for param in self.parameters for i in param.elements]
        component_elems = [i for component in self.components for i in component.elements]
        reference_elems = [i for reference in self.references for i in reference.elements]

        if event == self.key_lookup('ReferencesButton'):
            print('Info: RecordType {NAME}, Record {ID}: expanding / collapsing References frame'
                  .format(NAME=self.name, ID=self.record_id))
            self.collapse_expand(window, frame='references')
        elif event == self.key_lookup('ComponentsButton'):
            print('Info: RecordType {NAME}, Record {ID}: expanding / collapsing Components frame'
                  .format(NAME=self.name, ID=self.record_id))
            self.collapse_expand(window, frame='components')
        elif event in param_elems:  # parameter event
            try:
                param = self.fetch_element(event, by_key=True)
            except KeyError:
                print('Error: RecordType {NAME}, Record {ID}: unable to find parameter associated with event key {KEY}'
                      .format(NAME=self.name, ID=self.record_id, KEY=event))
            else:
                result = param.run_event(window, event, values, user)
        elif event in component_elems:  # component table event
            try:
                component_table = self.fetch_component(event, by_key=True)
            except KeyError:
                print('Error: RecordType {NAME}, Record {ID}: unable to find component associated with event key {KEY}'
                      .format(NAME=self.name, ID=self.record_id, KEY=event))
            else:
                result = component_table.run_event(window, event, values, user)
        elif event in reference_elems:
            try:
                refbox = self.fetch_reference(event, by_key=True)
            except KeyError:
                print('Error: RecordType {NAME}, Record {ID}: unable to find reference associated with event key {KEY}'
                      .format(NAME=self.name, ID=self.record_id, KEY=event))
            else:
                result = refbox.run_event(window, event, values, user)
        elif event == approved_key:
            self.approved = values[approved_key]
            print('Info: RecordType {NAME}, Record {ID}: setting approved to be {VAL}'
                  .format(NAME=self.name, ID=self.record_id, VAL=self.approved))
        elif event == marked_key:
            self.marked_for_deletion = values[marked_key]
            print('Info: RecordType {NAME}, Record {ID}: setting marked for deletion to be {VAL}'
                  .format(NAME=self.name, ID=self.record_id, VAL=self.marked_for_deletion))
        elif event == save_key:
            # Update record parameters in the record database table
            # Remove any deleted references from the record reference table
            for refbox in self.references:
                refkey = refbox.key_lookup('Element')
                ref_removed = window[refkey].metadata['deleted']
                if ref_removed is True:
                    print('Info: RecordType {NAME}, Record {ID}: deleting link between records {ID} and {REF} in '
                          'record reference table'.format(NAME=self.name, ID=self.record_id, REF=refbox.record_id))
            # Remove any deleted components from the record reference table

            return False
        elif event == delete_key:
            # Remove the record from the record table
            # Remove any entry in the record reference table referencing the record
            return False

        return True

    def fetch_element(self, element, by_key: bool = False):
        """
        Fetch a GUI data element by name or event key.
        """
        if by_key is True:
            element_type = element.split('_')[-1]
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

    def fetch_reference(self, reference, by_key: bool = False, by_id: bool = False):
        """
        Display a reference record in a new window.
        """
        if by_key is True:
            element_type = reference.split('_')[-1]
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
            element_type = component.split('_')[-1]
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
        parameters = self.parameters

        columns = ['RecordID', 'RecordDate', 'Approved', 'MarkedForDeletion']
        values = [self.record_id, self.record_date, self.approved, self.marked_for_deletion]

        # Add parameter values
        for param in parameters:
            param_type = param.etype
            if param_type == 'table':  # parameter is a data table object
                col_summs = param.summarize_table()
                columns += col_summs.index.values.tolist()
                values += col_summs.values.tolist()
            else:  # parameter is a data element object
                columns.append(param.name)
                values.append(param.value)

        return pd.Series(values, index=columns)

    def header_layout(self):
        """
        Generate the layout for the header section of the record layout.
        """
        record_layout = self.record_layout

        layout_header = record_layout['Header']
        header_elements = layout_header['Elements']

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

    def layout(self, win_size: tuple = None, user_access: str = 'admin', save: bool = True, delete: bool = False,
               title_bar: bool = True, buttons: bool = True, view_only: bool = False):
        """
        Generate a GUI layout for the account record.
        """
        if win_size:
            width, height = win_size
        else:
            width, height = (mod_const.WIN_WIDTH * 0.8, mod_const.WIN_HEIGHT * 0.8)

        record_layout = self.record_layout

        # GUI data elements
        markable = True if (user_access == 'admin' or self.permissions['mark'] == 'user') and self.new is False \
            and view_only is False else False
        editable = True if user_access == 'admin' or self.permissions['save'] == 'user' else False
        deletable = True if (user_access == 'admin' or self.permissions['delete'] == 'user') and delete is True \
            and view_only is False else False
        approvable = True if (user_access == 'admin' or self.permissions['approve'] == 'user') and self.new is False \
            and view_only is False else False
        savable = True if editable is True and save is True and view_only is False else False

        # Element parameters
        header_col = mod_const.HEADER_COL
        bg_col = mod_const.ACTION_COL
        text_col = mod_const.TEXT_COL

        font_h = mod_const.HEADER_FONT
        main_font = mod_const.MAIN_FONT
        bold_font = mod_const.BOLD_LARGE_FONT

        pad_el = mod_const.ELEM_PAD
        pad_v = mod_const.VERT_PAD
        pad_h = mod_const.HORZ_PAD
        pad_frame = mod_const.FRAME_PAD

        # Element sizes

        # Layout elements
        layout_header = record_layout['Header']
        header_elements = layout_header['Elements']

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

        # Window Title
        if self.marked_for_deletion is not None:
            try:
                is_marked_for_deletion = bool(self.marked_for_deletion)
            except (ValueError, TypeError):
                is_marked_for_deletion = False

            mark_title = header_elements.get('MarkedForDeletion', 'Marked for deletion')
            mark_layout = [sg.Checkbox(mark_title, key=self.key_lookup('MarkedForDeletion'),
                                       default=is_marked_for_deletion, enable_events=True,
                                       font=main_font, background_color=header_col, disabled=(not markable),
                                       metadata={'visible': True, 'disabled': (not markable),
                                                 'value': self.marked_for_deletion})]
        else:
            mark_layout = []

        if self.approved is not None:
            try:
                is_approved = bool(self.approved)
            except (ValueError, TypeError):
                is_approved = False

            approved_title = header_elements.get('Approved', 'Approved')
            approved_layout = [sg.Checkbox(approved_title, default=is_approved,
                                           key=self.key_lookup('Approved'), font=main_font, enable_events=True,
                                           background_color=header_col, disabled=(not approvable),
                                           metadata={'visible': True, 'disabled': (not markable),
                                                     'value': self.approved})]
        else:
            approved_layout = []

        if self.new is True:
            annotation_layout = [[]]
        else:
            annotation_layout = [approved_layout, mark_layout]

        title = layout_header.get('Title', self.name)
        if title_bar is True:
            title_layout = [[sg.Col([[sg.Text(title, pad=(pad_frame, pad_frame), font=font_h,
                                              background_color=header_col)]],
                                    pad=(0, 0), justification='l', background_color=header_col, expand_x=True),
                             sg.Col([[sg.Canvas(size=(0, 0), visible=True)]],
                                    background_color=header_col, justification='c', expand_x=True),
                             sg.Col(annotation_layout, pad=(pad_frame, 0), background_color=header_col,
                                    justification='r', vertical_alignment='c')]]
        else:
            title_layout = [[]]

        # Record header
        header_layout = self.header_layout()

        # Create layout for record details
        details_layout = []
        for data_elem in self.parameters:
            details_layout.append([data_elem.layout(padding=(0, pad_el), collapsible=True, view_only=view_only)])

        # Add reference boxes to the details section
        ref_key = self.key_lookup('ReferencesButton')
        ref_layout = [[sg.Image(data=mod_const.NETWORK_ICON, pad=((0, pad_el), 0), background_color=bg_col),
                       sg.Text(reference_title, pad=((0, pad_el), 0), background_color=bg_col, font=bold_font),
                       sg.Button('', image_data=mod_const.HIDE_ICON, key=ref_key, button_color=(text_col, bg_col),
                                 border_width=0, disabled=False, visible=True,
                                 metadata={'visible': True, 'disabled': False})]]

        ref_boxes = []
        open_reference = True if savable is True and self.referenced is False else False
        for ref_box in self.references:
            ref_boxes.append([ref_box.layout(padding=(0, pad_v), editable=open_reference)])

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

        comp_tables = []
        for comp_table in self.components:
            comp_table.df = comp_table.set_datatypes(comp_table.df)
            comp_tables.append([comp_table.layout(padding=(0, pad_v), width=width, height=height,
                                                  editable=open_reference)])

        comp_layout.append([sg.pin(sg.Col(comp_tables, key=self.key_lookup('ComponentsFrame'), background_color=bg_col,
                                          visible=True, expand_x=True, metadata={'visible': False}))])

        if has_components is True:
            details_layout.append([sg.Col(comp_layout, pad=(0, pad_el), expand_x=True, background_color=bg_col)])

        height_key = self.key_lookup('Height')
        main_layout = [[sg.Canvas(size=(0, height), key=height_key, background_color=bg_col),
                        sg.Col(details_layout, pad=(0, 0), background_color=bg_col, expand_x=True, expand_y=True,
                               scrollable=True, vertical_scroll_only=True, vertical_alignment='t')]]

        # Flow control buttons
        delete_key = self.key_lookup('Delete')
        save_key = self.key_lookup('Save')
        if buttons is True:
            bttn_layout = [[mod_lo.B2('Delete', key=delete_key, pad=(pad_el, 0), visible=deletable,
                                      tooltip='Delete record'),
                            mod_lo.B2('Save', key=save_key, pad=(pad_el, 0), visible=savable,
                                      tooltip='Save record')]]
        else:
            bttn_layout = [[]]

        # Pane elements must be columns
        width_key = self.key_lookup('Width')
        width_layout = [[sg.Canvas(size=(width, 0), key=width_key, background_color=bg_col)]]
        layout = [[sg.Col(width_layout, pad=(0, 0), background_color=bg_col)],
                  [sg.Col(title_layout, background_color=header_col, expand_x=True)],
                  [sg.Col(header_layout, pad=(pad_frame, (pad_frame, 0)), background_color=bg_col, expand_x=True)],
                  [sg.HorizontalSeparator(pad=(pad_frame, (pad_v, pad_frame)), color=mod_const.INACTIVE_COL)],
                  [sg.Col(main_layout, pad=(pad_frame, (0, pad_frame)), background_color=bg_col, expand_x=True)],
                  [sg.HorizontalSeparator(pad=(pad_frame, 0), color=mod_const.INACTIVE_COL)],
                  [sg.Col(bttn_layout, pad=(pad_frame, pad_frame), element_justification='c',
                          background_color=bg_col, expand_x=True)]]

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

        window.refresh()

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

    def __init__(self, name, entry, record_data, new_record: bool = False, referenced: bool = False):
        """
        deposit (float): amount deposited into the bank account.
        """
        super().__init__(name, entry, record_data, new_record, referenced)
        self.elements.append('{NAME}_{ID}_{ELEM}'.format(NAME=self.name, ID=self.id, ELEM='Deposit'))

        try:
            deposit = float(record_data['DepositAmount'])
        except (KeyError, TypeError):
            self.deposit = 0
        else:
            if np.isnan(deposit):
                self.deposit = 0.00
            else:
                self.deposit = deposit

    def header_layout(self):
        """
        Generate the layout for the header section of the record layout.
        """
        greater_col = mod_const.PASS_COL
        lesser_col = mod_const.FAIL_COL

        record_layout = self.record_layout

        layout_header = record_layout['Header']
        header_elements = layout_header['Elements']

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
        parameters = self.parameters

        columns = ['RecordID', 'RecordDate', 'Approved', 'MarkedForDeletion', 'DepositAmount']
        values = [self.record_id, self.record_date, self.approved, self.marked_for_deletion, self.deposit]

        # Add parameter values
        for param in parameters:
            param_type = param.etype
            if param_type == 'table':
                col_summs = param.summarize_table()
                columns += col_summs.index.values.tolist()
                values += col_summs.values.tolist()
            else:
                columns.append(param.name)
                values.append(param.value)

        return pd.Series(values, index=columns)

    def run_event(self, window, event, values, user):
        """
        Perform a record action.
        """
        save_key = self.key_lookup('Save')
        delete_key = self.key_lookup('Delete')
        approved_key = self.key_lookup('Approved')
        marked_key = self.key_lookup('MarkedForDeletion')

        param_elems = [i for param in self.parameters for i in param.elements]
        component_elems = [i for component in self.components for i in component.elements]
        reference_elems = [i for reference in self.references for i in reference.elements]

        if event == self.key_lookup('ReferencesButton'):
            print('Info: table {TBL}: expanding / collapsing References frame'.format(TBL=self.name))
            self.collapse_expand(window, frame='references')
        elif event == self.key_lookup('ComponentsButton'):
            print('Info: table {TBL}: expanding / collapsing Components frame'.format(TBL=self.name))
            self.collapse_expand(window, frame='components')
        elif event in param_elems:  # parameter event
            try:
                param = self.fetch_element(event, by_key=True)
            except KeyError:
                print('Error: record {ID}: unable to find parameter associated with event key {KEY}'
                      .format(ID=self.record_id, KEY=event))
            else:
                param.run_event(window, event, values, user)
        elif event in component_elems:  # component table event
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
                        export_columns = {j: i for i, j in comp_entry.import_rules['Columns']}
                        filters = [[export_columns['Approved'], '=', self.approved],
                                   [export_columns['PaymentType'], '=', self.fetch_element('PaymentType').value]]

                        component_table.df = component_table.import_rows(filters)

                else:
                    component_table.run_event(window, event, values, user)

                self.update_display(window, window_values=values)
        elif event in reference_elems:
            try:
                refbox = self.fetch_reference(event, by_key=True)
            except KeyError:
                print('Error: record {ID}: unable to find reference associated with event key {KEY}'
                      .format(ID=self.record_id, KEY=event))
            else:
                refbox.run_event(window, event, values, user)
        elif event == approved_key:
            self.approved = values[approved_key]
            print('Info: record {ID}: setting approved to be {VAL}'
                  .format(ID=self.record_id, VAL=self.approved))
        elif event == marked_key:
            self.marked_for_deletion = values[marked_key]
            print('Info: record {ID}: setting marked for deletion to be {VAL}'
                  .format(ID=self.record_id, VAL=self.marked_for_deletion))
        elif event == save_key:
            # Update record parameters in the record database table
            # Remove any deleted references from the record reference table
            for refbox in self.references:
                refkey = refbox.key_lookup('Element')
                ref_removed = window[refkey].metadata['deleted']
                if ref_removed is True:
                    print('Info: record {ID}: deleting link between records {ID} and {REF} in record reference table'
                          .format(ID=self.record_id, REF=refbox.record_id))
            # Remove any deleted components from the record reference table

            return False
        elif event == delete_key:
            # Remove the record from the record table
            # Remove any entry in the record reference table referencing the record
            return False

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


class AccountRecord(DatabaseRecord):
    """
    Class to manage the layout and display of an REM Account Record.
    """

    def __init__(self, name, entry, record_data, new_record: bool = False, referenced: bool = False):
        """
        amount (float): amount .
        """
        super().__init__(name, entry, record_data, new_record, referenced)
        self.elements.append('{NAME}_{ID}_{ELEM}'.format(NAME=self.name, ID=self.id, ELEM='Amount'))

        try:
            amount = float(record_data['Amount'])
        except (KeyError, TypeError):
            self.amount = 0
        else:
            if np.isnan(amount):
                self.amount = 0.00
            else:
                self.amount = amount

    def header_layout(self):
        """
        Generate the layout for the header section of the record layout.
        """
        record_layout = self.record_layout

        layout_header = record_layout['Header']
        header_elements = layout_header['Elements']

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
            amount_title = header_elements.get('Amount', 'Amount')
        except KeyError:
            print('Warning: the parameter "Amount" was not included in the list of configured data elements')
            amount_title = 'Amount'

        amount_total = self.amount
        amount_layout = [[sg.Text('{}:'.format(amount_title), pad=((0, pad_el), 0), background_color=bg_col,
                                  font=bold_font),
                          sg.Text('{:,.2f}'.format(amount_total), key=self.key_lookup('Amount'), size=(14, 1),
                                  font=main_font, background_color=bg_col, border_width=1, relief="sunken",
                                  tooltip='Import amount: {}'.format('{:,.2f}'.format(amount_total)))]]

        # Header layout
        layout = [[sg.Col(id_layout, pad=(0, 0), background_color=bg_col, justification='l', expand_x=True),
                   sg.Col([[sg.Canvas(size=(0, 0), visible=True)]],
                          background_color=bg_col, justification='c', expand_x=True),
                   sg.Col(amount_layout, background_color=bg_col, justification='r')]]

        return layout

    def table_values(self):
        """
        Format parameter values as a table row.
        """
        parameters = self.parameters

        columns = ['RecordID', 'RecordDate', 'MarkedForDeletion', 'Amount']
        values = [self.record_id, self.record_date, self.marked_for_deletion, self.amount]

        # Add parameter values
        for param in parameters:
            param_type = param.etype
            if param_type == 'table':
                col_summs = param.summarize_table()
                columns += col_summs.index.values.tolist()
                values += col_summs.values.tolist()
            else:
                columns.append(param.name)
                values.append(param.value)

        return pd.Series(values, index=columns)

    def run_event(self, window, event, values, user):
        """
        Perform a record action.
        """
        save_key = self.key_lookup('Save')
        delete_key = self.key_lookup('Delete')
        approved_key = self.key_lookup('Approved')
        marked_key = self.key_lookup('MarkedForDeletion')

        param_elems = [i for param in self.parameters for i in param.elements]
        component_elems = [i for component in self.components for i in component.elements]
        reference_elems = [i for reference in self.references for i in reference.elements]

        if event == self.key_lookup('ReferencesButton'):
            print('Info: table {TBL}: expanding / collapsing References frame'.format(TBL=self.name))
            self.collapse_expand(window, frame='references')
        elif event == self.key_lookup('ComponentsButton'):
            print('Info: table {TBL}: expanding / collapsing Components frame'.format(TBL=self.name))
            self.collapse_expand(window, frame='components')
        elif event in param_elems:  # parameter event
            try:
                param = self.fetch_element(event, by_key=True)
            except KeyError:
                print('Error: record {ID}: unable to find parameter associated with event key {KEY}'
                      .format(ID=self.record_id, KEY=event))
            else:
                param.run_event(window, event, values, user)
        elif event in component_elems:  # component table event
            try:
                component_table = self.fetch_component(event, by_key=True)
            except KeyError:
                print('Error: record {ID}: unable to find component associated with event key {KEY}'
                      .format(ID=self.record_id, KEY=event))
            else:
                component_table.run_event(window, event, values, user)
                self.update_display(window, window_values=values)
        elif event in reference_elems:
            try:
                refbox = self.fetch_reference(event, by_key=True)
            except KeyError:
                print('Error: record {ID}: unable to find reference associated with event key {KEY}'
                      .format(ID=self.record_id, KEY=event))
            else:
                refbox.run_event(window, event, values, user)
        elif event == approved_key:
            self.approved = values[approved_key]
            print('Info: record {ID}: setting approved to be {VAL}'
                  .format(ID=self.record_id, VAL=self.approved))
        elif event == marked_key:
            self.marked_for_deletion = values[marked_key]
            print('Info: record {ID}: setting marked for deletion to be {VAL}'
                  .format(ID=self.record_id, VAL=self.marked_for_deletion))
        elif event == save_key:
            # Update record parameters in the record database table
            # Remove any deleted references from the record reference table
            for refbox in self.references:
                refkey = refbox.key_lookup('Element')
                ref_removed = window[refkey].metadata['deleted']
                if ref_removed is True:
                    print('Info: record {ID}: deleting link between records {ID} and {REF} in record reference table'
                          .format(ID=self.record_id, REF=refbox.record_id))
            # Remove any deleted components from the record reference table

            return False
        elif event == delete_key:
            # Remove the record from the record table
            # Remove any entry in the record reference table referencing the record
            return False

        return True

    def update_display(self, window, window_values: dict = None):
        """
        Update the display of the record's elements and components.
        """
        # Update data element values
        for param in self.parameters:
            param.update_display(window, window_values=window_values)

        # Update the components display table
        for component in self.components:
            component.update_display(window, window_values=window_values)

        # Update the record's header
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

        # Update the total amount
        try:
            table = self.fetch_component('transaction')
        except KeyError:
            print('Configuration Error: RecordEntry {TYPE}: missing required component records of type "transaction"'
                  .format(TYPE=self.name))
            total = 0
        else:
            total = table.calculate_total()
            print('Info: record {ID}: total income was calculated from the transaction table is {VAL}'
                  .format(ID=self.record_id, VAL=total))

        window[self.key_lookup('Amount')].update(value='{:,.2f}'.format(total))
        self.amount = total


class TAuditRecord(DatabaseRecord):
    """
    Class to manage the layout of an audit record.
    """

    def __init__(self, name, entry, record_data, new_record: bool = False, referenced: bool = False):
        """
        remainder (float): remaining total after subtracting component record totals.
        """
        super().__init__(name, entry, record_data, new_record, referenced)
        for element in ['Remainder', 'Notes', 'NotesButton']:
            self.elements.append('{NAME}_{ID}_{ELEM}'.format(NAME=self.name, ID=self.id, ELEM=element))

        try:
            remainder = float(record_data['Remainder'])
        except (KeyError, TypeError):
            self.remainder = 0.00
        else:
            if np.isnan(remainder):
                self.remainder = 0.00
            else:
                self.remainder = remainder

        try:
            self.note = record_data['Notes']
        except KeyError:
            self.note = ''

    def header_layout(self):
        """
        Generate the layout for the header section of the record layout.
        """
        greater_col = mod_const.PASS_COL
        lesser_col = mod_const.FAIL_COL

        record_layout = self.record_layout

        layout_header = record_layout['Header']
        header_elements = layout_header['Elements']

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
        notes_title = header_elements.get('Notes', 'Notes')

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
                              size=(14, 1), font=main_font, background_color=bg_col),
                      sg.Button('', key=self.key_lookup('NotesButton'), image_data=mod_const.TAKE_NOTE_ICON,
                                button_color=(text_col, bg_col), border_width=0, tooltip=notes_title),
                      sg.Text(self.note, key=self.key_lookup('Notes'), size=(1, 1), visible=False)]
                     ]
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
        parameters = self.parameters

        columns = ['RecordID', 'RecordDate', 'Approved', 'MarkedForDeletion', 'Remainder', 'Notes']
        values = [self.record_id, self.record_date, self.approved, self.marked_for_deletion, self.remainder, self.note]

        # Add parameter values
        for param in parameters:
            param_type = param.etype
            if param_type == 'table':
                col_summs = param.summarize_table()
                columns += col_summs.index.values.tolist()
                values += col_summs.values.tolist()
            else:
                columns.append(param.name)
                values.append(param.value)

        return pd.Series(values, index=columns)

    def run_event(self, window, event, values, user):
        """
        Perform a record action.
        """
        save_key = self.key_lookup('Save')
        delete_key = self.key_lookup('Delete')
        approved_key = self.key_lookup('Approved')
        marked_key = self.key_lookup('MarkedForDeletion')
        notes_key = self.key_lookup('NotesButton')

        param_elems = [i for param in self.parameters for i in param.elements]
        component_elems = [i for component in self.components for i in component.elements]
        reference_elems = [i for reference in self.references for i in reference.elements]

        if event == self.key_lookup('ReferencesButton'):
            print('Info: table {TBL}: expanding / collapsing References frame'.format(TBL=self.name))
            self.collapse_expand(window, frame='references')
        elif event == self.key_lookup('ComponentsButton'):
            print('Info: table {TBL}: expanding / collapsing Components frame'.format(TBL=self.name))
            self.collapse_expand(window, frame='components')
        elif event == notes_key:
            record_layout = self.record_layout
            layout_header = record_layout['Header']
            header_elements = layout_header['Elements']

            notes_title = header_elements.get('Notes', 'Notes')
            id_title = header_elements.get('RecordID', 'Record ID')

            note_text = mod_win2.notes_window(self.record_id, self.note, id_title=id_title, title=notes_title).strip()
            self.note = note_text

            self.update_display(window, window_values=values)
        elif event in param_elems:  # parameter event
            try:
                param = self.fetch_element(event, by_key=True)
            except KeyError:
                print('Error: record {ID}: unable to find parameter associated with event key {KEY}'
                      .format(ID=self.record_id, KEY=event))
            else:
                param.run_event(window, event, values, user)
                self.update_display(window, window_values=values)
        elif event in component_elems:  # component table event
            try:
                component_table = self.fetch_component(event, by_key=True)
            except KeyError:
                print('Error: record {ID}: unable to find component associated with event key {KEY}'
                      .format(ID=self.record_id, KEY=event))
            else:
                component_table.run_event(window, event, values, user)
                self.update_display(window, window_values=values)
        elif event in reference_elems:
            try:
                refbox = self.fetch_reference(event, by_key=True)
            except KeyError:
                print('Error: record {ID}: unable to find reference associated with event key {KEY}'
                      .format(ID=self.record_id, KEY=event))
            else:
                refbox.run_event(window, event, values, user)
        elif event == approved_key:
            self.approved = values[approved_key]
            print('Info: record {ID}: setting approved to be {VAL}'
                  .format(ID=self.record_id, VAL=self.approved))
        elif event == marked_key:
            self.marked_for_deletion = values[marked_key]
            print('Info: record {ID}: setting marked for deletion to be {VAL}'
                  .format(ID=self.record_id, VAL=self.marked_for_deletion))
        elif event == save_key:
            # Update record parameters in the record database table
            # Remove any deleted references from the record reference table
            for refbox in self.references:
                refkey = refbox.key_lookup('Element')
                ref_removed = window[refkey].metadata['deleted']
                if ref_removed is True:
                    print('Info: record {ID}: deleting link between records {ID} and {REF} in record reference table'
                          .format(ID=self.record_id, REF=refbox.record_id))
            # Remove any deleted components from the record reference table

            return False
        elif event == delete_key:
            # Remove the record from the record table
            # Remove any entry in the record reference table referencing the record
            return False

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
        id_key = self.key_lookup('RecordID')
        date_key = self.key_lookup('RecordDate')
        record_id = self.record_id
        record_date = settings.format_display_date(self.record_date)
        window[id_key].set_size(size=(len(record_id) + 1, None))
        window[date_key].set_size(size=(len(record_date) + 1, None))

        window[id_key].update(value=record_id)
        window[date_key].update(value=record_date)

        id_tooltip = '{ID} created {TIME} by {NAME}'.format(ID=record_id, NAME=self.creator, TIME=self.creation_date)
        window[id_key].set_tooltip(id_tooltip)

        # Change edit note button to be highlighted if note field not empty
        note_key = self.key_lookup('NotesButton')
        if self.note:
            window[note_key].update(image_data=mod_const.EDIT_NOTE_ICON)
        else:
            window[note_key].update(image_data=mod_const.TAKE_NOTE_ICON)

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

        window[self.key_lookup('Remainder')].update(value='{:,.2f}'.format(remainder), background_color=bg_color)
        self.remainder = remainder


def load_record(record_entry, record_id):
    """
    Load an existing record from the program database.
    """
    # Extract the record data from the database
    import_df = record_entry.load_record_data(record_id)

    # Set the record object based on the record type
    record_type = record_entry.group
    if record_type in ('transaction', 'bank_statement', 'cash_expense'):
        record_class = DatabaseRecord
    elif record_type == 'account':
        record_class = AccountRecord
    elif record_type == 'bank_deposit':
        record_class = DepositRecord
    elif record_type == 'audit':
        record_class = TAuditRecord
    else:
        print('Warning: unknown record layout type provided {}'.format(record_type))
        return None

    record = record_class(record_entry.name, record_entry.record_layout, import_df, new_record=False, referenced=True)

    return record


def create_record(record_entry, record_data):
    """
    Create a new database record.
    """
    record_type = record_entry.group
    if record_type in ('transaction', 'bank_statement', 'cash_expense'):
        record_class = DatabaseRecord
    elif record_type == 'account':
        record_class = AccountRecord
    elif record_type == 'bank_deposit':
        record_class = DepositRecord
    elif record_type == 'audit':
        record_class = TAuditRecord
    else:
        print('Warning: unknown record layout type provided {}'.format(record_type))
        return None

    record = record_class(record_entry.name, record_entry.record_layout, record_data, new_record=True, referenced=False)

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
