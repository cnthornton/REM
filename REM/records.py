"""
REM records classes and functions. Includes audit records and account records.
"""
import datetime
import dateutil
from random import randint
import re
import sys

import numpy as np
import pandas as pd
import PySimpleGUI as sg

import REM.constants as mod_const
import REM.data_manipulation as mod_dm
import REM.elements as mod_elem
import REM.layouts as mod_lo
import REM.secondary as mod_win2
from REM.config import configuration, current_tbl_pkeys, settings


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

    def __init__(self, record_entry, record_data, new_record: bool = False):
        """
        Arguments:
            record_entry (class): configuration entry for the record.

            record_data (dict): dictionary or pandas series containing record data.
        """
        is_datetime_dtype = pd.api.types.is_datetime64_any_dtype

        approved_record_types = ['transaction', 'account', 'bank_deposit', 'bank_statement', 'audit', 'cash_expense']
        self.name = record_entry.name
        self.record_type = record_entry.type

        self.id = randint(0, 1000000000)
        self.elements = ['{NAME}_{ID}_{ELEM}'.format(NAME=self.name, ID=self.id, ELEM=i) for i in
                         ['Delete', 'Save', 'RecordID', 'RecordDate', 'MarkedForDeletion', 'Approved',
                          'ReferencesButton', 'ReferencesFrame', 'ComponentsButton', 'ComponentsFrame', 'Height',
                          'Width']]

        entry = record_entry.record_layout
        self.record_layout = entry
        self.new = new_record

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
            raise AttributeError('missing required import data column "RecordID"')

        try:
            record_date = record_data['RecordDate']
        except KeyError:
            raise AttributeError('missing required import data column "RecordDate"')
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
                    print(param_obj.df)
                else:  # parameter is a data element
                    try:
                        param_value = record_data[param]
                    except KeyError:
                        print('Warning: record {ID}: imported data is missing a column for parameter {PARAM}'
                              .format(ID=self.record_id, PARAM=param))
                    else:
                        print('Info: record {ID}: setting parameter {PARAM} to value {VAL}'
                              .format(ID=self.record_id, PARAM=param_obj.name, VAL=param_value))
                        param_obj.value = param_obj.format_value(param_value)

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
                              'record type'.format(TYPE=self.record_type, TBL=comp_element))
                        continue
                    table_entry = comp_elements[comp_element]
                    comp_table = mod_elem.TableElement(comp_element, table_entry, parent=self.name, date=self.record_date)
                    comp_types.append(comp_table.record_type)
                    self.components.append(comp_table)
                    self.elements += comp_table.elements

        ref_rows = record_entry.import_references(self.record_id)
        for index, row in ref_rows.iterrows():
            # Store imported references as references box objects
            print(row)
            print(ref_elements)
            doctype = row['DocType']
            if doctype in ref_elements:
                print('Info: record {ID}: adding reference {NAME} with record type {TYPE}'
                      .format(ID=self.record_id, NAME=row['DocNo'], TYPE=doctype))
                try:
                    ref_box = mod_elem.ReferenceElement('{}_Reference'.format(doctype), row, parent=self.name)
                except Exception as e:
                    print('Warning: record {ID}: failed to add reference {NAME} to list of references - {ERR}'
                          .format(ID=self.record_id, NAME=row['DocNo'], ERR=e))
                    continue
                else:
                    self.references.append(ref_box)
                    self.elements += ref_box.elements

            # Store imported components as table rows
            reftype = row['RefType']
            if reftype in comp_types:
                print('Info: record {ID}: adding component {NAME} with record type {TYPE}'
                      .format(ID=self.record_id, NAME=row['RefNo'], TYPE=reftype))
                # Fetch the relevant components table
                comp_table = self.fetch_component(reftype, by_type=True)

                # Import data to the table
                ref_id = row['RefNo']
                ref_record_entry = configuration.records.fetch_entry(reftype)
                ref_record = ref_record_entry.load_record(ref_id)

                comp_table.df = comp_table.append(ref_record)

    def key_lookup(self, component):
        """
        Lookup a component's GUI element key using the component's name.
        """
        element_names = [i.split('_')[-1] for i in self.elements]
        if component in element_names:
            key_index = element_names.index(component)
            key = self.elements[key_index]
        else:
            raise KeyError('component {COMP} not found in list of data element {PARAM} components'
                           .format(COMP=component, PARAM=self.name))

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
                result = param.run_event(window, event, values, user)
        elif event in component_elems:  # component table event
            try:
                component_table = self.fetch_component(event, by_key=True)
            except KeyError:
                print('Error: record {ID}: unable to find component associated with event key {KEY}'
                      .format(ID=self.record_id, KEY=event))
            else:
                result = component_table.run_event(window, event, values, user)
        elif event in reference_elems:
            try:
                refbox = self.fetch_reference(event, by_key=True)
            except KeyError:
                print('Error: record {ID}: unable to find reference associated with event key {KEY}'
                      .format(ID=self.record_id, KEY=event))
            else:
                result = refbox.run_event(window, event, values, user)
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
            raise KeyError('element {ELEM} not found in list of {NAME} data elements'
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
            raise KeyError('reference {ELEM} not found in list of {NAME} references'
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
            raise KeyError('component {ELEM} not found in list of {NAME} component tables'
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
                      sg.Text(self.record_id, key=self.key_lookup('RecordID'), pad=((0, pad_h), 0), auto_size_text=True,
                              font=main_font, background_color=bg_col, tooltip=id_tooltip,
                              metadata={'visible': True, 'disabled': False, 'value': self.record_id}),
                      sg.Text('{}:'.format(date_title), pad=((0, pad_el), 0), background_color=bg_col, font=bold_font),
                      sg.Text(record_date, key=self.key_lookup('RecordDate'), font=main_font,
                              background_color=bg_col, auto_size_text=True,
                              metadata={'visible': True, 'disabled': False, 'value': self.record_date})]]

        # Header layout
        layout = [[sg.Col(id_layout, pad=(0, 0), background_color=bg_col, justification='l', expand_x=True)]]

        return layout

    def layout(self, win_size: tuple = None, user_access: str = 'admin', save: bool = True, delete: bool = False,
               title_bar: bool = True):
        """
        Generate a GUI layout for the account record.
        """
        if win_size:
            width, height = win_size
        else:
            width, height = (mod_const.WIN_WIDTH * 0.8, mod_const.WIN_HEIGHT * 0.8)

        record_layout = self.record_layout

        # GUI data elements
        markable = True if user_access == 'admin' or self.permissions['mark'] == 'user' else False
        editable = True if user_access == 'admin' or self.permissions['save'] == 'user' else False
        deletable = True if (user_access == 'admin' or self.permissions[
            'delete'] == 'user') and delete is True else False
        unlinkable = True if user_access == 'admin' or self.permissions['unlink'] == 'user' else False
        approvable = True if user_access == 'admin' or self.permissions['approve'] == 'user' else False
        savable = True if editable is True and save is True else False

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

        title = layout_header.get('Title', self.name)
        title_layout = [[sg.Col([[sg.Text(title, pad=(pad_frame, pad_frame), font=font_h,
                                          background_color=header_col)]],
                                pad=(0, 0), justification='l', background_color=header_col, expand_x=True),
                         sg.Col([[sg.Canvas(size=(0, 0), visible=True)]],
                                background_color=header_col, justification='c', expand_x=True),
                         sg.Col([approved_layout, mark_layout], pad=(pad_frame, 0), background_color=header_col,
                                justification='r', vertical_alignment='c')]]

        # Record header
        header_layout = self.header_layout()

        # Create layout for record details
        details_layout = []
        for data_elem in self.parameters:
            details_layout.append([data_elem.layout(padding=(0, pad_el), collapsible=True, overwrite_edit=self.new)])

        # Add reference boxes to the details section
        ref_key = self.key_lookup('ReferencesButton')
        ref_layout = [[sg.Image(data=mod_const.NETWORK_ICON, pad=((0, pad_el), 0), background_color=bg_col),
                       sg.Text(reference_title, pad=((0, pad_el), 0), background_color=bg_col, font=bold_font),
                       sg.Button('', image_data=mod_const.HIDE_ICON, key=ref_key, button_color=(text_col, bg_col),
                                 border_width=0, disabled=False, visible=True,
                                 metadata={'visible': True, 'disabled': False})]]

        ref_boxes = []
        for ref_box in self.references:
            ref_boxes.append([ref_box.layout(padding=(0, pad_v), editable=unlinkable)])

        ref_layout.append([sg.pin(sg.Col(ref_boxes, key=self.key_lookup('ReferencesFrame'), background_color=bg_col,
                                         visible=True, expand_x=True, metadata={'visible': True}))])

        if has_references is True:
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
            comp_tables.append([comp_table.layout(padding=(0, pad_v), width=width, height=height)])

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
        bttn_layout = [[mod_lo.B2('Delete', key=delete_key, pad=(pad_el, 0), visible=deletable,
                                  tooltip='Delete record'),
                        mod_lo.B2('Save', key=save_key, pad=(pad_el, 0), visible=savable,
                                  tooltip='Save record')]]

        # Pane elements must be columns
        width_key = self.key_lookup('Width')
        width_layout = [[sg.Canvas(size=(width, 0), key=width_key, background_color=bg_col)]]
        if title_bar is True:
            layout = [[sg.Col(width_layout, pad=(0, 0), background_color=bg_col)],
                      [sg.Col(title_layout, background_color=header_col, expand_x=True)],
                      [sg.Col(header_layout, pad=(pad_frame, (pad_frame, 0)), background_color=bg_col, expand_x=True)],
                      [sg.HorizontalSeparator(pad=(pad_frame, (pad_v, pad_frame)), color=mod_const.INACTIVE_COL)],
                      [sg.Col(main_layout, pad=(pad_frame, (0, pad_frame)), background_color=bg_col, expand_x=True)],
                      [sg.HorizontalSeparator(pad=(pad_frame, 0), color=mod_const.INACTIVE_COL)],
                      [sg.Col(bttn_layout, pad=(pad_frame, pad_frame), element_justification='c',
                              background_color=bg_col, expand_x=True)]]
        else:
            layout = [[sg.Col(width_layout, pad=(0, 0), background_color=bg_col)],
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

    def __init__(self, record_entry, record_data):
        """
        deposit (float): amount deposited into the bank account.
        """
        super().__init__(record_entry, record_data)
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
                      sg.Text(self.record_id, key=self.key_lookup('RecordID'), pad=((0, pad_h), 0), auto_size_text=True,
                              font=main_font, background_color=bg_col, tooltip=id_tooltip),
                      sg.Text('{}:'.format(date_title), pad=((0, pad_el), 0), background_color=bg_col, font=bold_font),
                      sg.Text(record_date, key=self.key_lookup('RecordDate'), auto_size_text=True, font=main_font,
                              background_color=bg_col)]]
        try:
            deposit_title = header_elements.get('DepositAmount', 'Deposit Total')
        except KeyError:
            print('Warning: the parameter "DepositAmount" was not included in the list of configured data elements')
            deposit_title = 'Deposit Total'

        orig_amount = self.deposit
        deposit_layout = [[sg.Text('{}:'.format(deposit_title), pad=((0, pad_el), 0), background_color=bg_col,
                                   font=bold_font),
                           sg.Text('{:,.2f}'.format(self.update_deposit()), key=self.key_lookup('Deposit'),
                                   size=(14, 1), font=main_font, background_color=bg_col, border_width=1,
                                   relief="sunken", tooltip='Import amount: {}'.format('{:,.2f}'.format(orig_amount)))]]

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
        default_col = mod_const.ACTION_COL
        greater_col = mod_const.PASS_COL
        lesser_col = mod_const.FAIL_COL

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
                result = param.run_event(window, event, values, user)
        elif event in component_elems:  # component table event
            try:
                component_table = self.fetch_component(event, by_key=True)
            except KeyError:
                print('Error: record {ID}: unable to find component associated with event key {KEY}'
                      .format(ID=self.record_id, KEY=event))
            else:
                result = component_table.run_event(window, event, values, user)

            deposit_total = self.update_deposit()
            if deposit_total > 0:
                bg_color = greater_col
            elif deposit_total < 0:
                bg_color = lesser_col
            else:
                bg_color = default_col

            window[self.key_lookup('Deposit')].update(value='{:,.2f}'.format(deposit_total), background_color=bg_color)
        elif event in reference_elems:
            try:
                refbox = self.fetch_reference(event, by_key=True)
            except KeyError:
                print('Error: record {ID}: unable to find reference associated with event key {KEY}'
                      .format(ID=self.record_id, KEY=event))
            else:
                result = refbox.run_event(window, event, values, user)
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

    def update_deposit(self):
        """
        Update the deposit amount element and deposit attribute based on component table totals.
        """
        # Update the deposit element, in case a component was added or deleted
        try:
            account_table = self.fetch_component('account')
        except KeyError:
            print('Configuration Error: RecordEntry {TYPE}: missing required component records of type "account"'
                  .format(TYPE=self.record_type))
            account_total = 0
        else:
            account_total = account_table.calculate_total()
            print('Info: record {ID}: total income was calculated from the accounts table is {VAL}'
                  .format(ID=self.record_id, VAL=account_total))

        try:
            expense_table = self.fetch_component('cash_expense')
        except KeyError:
            print('Configuration Error: RecordEntry {TYPE}: missing required component records of type "cash_expense"'
                  .format(TYPE=self.record_type))
            expense_total = 0
        else:
            expense_total = expense_table.calculate_total()
            print('Info: record {ID}: total expenditures was calculated from the expense table to be {VAL}'
                  .format(ID=self.record_id, VAL=expense_total))

        deposit_total = account_total - expense_total

        self.deposit = deposit_total
        return deposit_total


class AccountRecord(DatabaseRecord):
    """
    Class to manage the layout and display of an REM Account Record.
    """

    def __init__(self, record_entry, record_data):
        """
        amount (float): amount .
        """
        super().__init__(record_entry, record_data)
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
                      sg.Text(self.record_id, key=self.key_lookup('RecordID'), pad=((0, pad_h), 0), auto_size_text=True,
                              font=main_font, background_color=bg_col, tooltip=id_tooltip),
                      sg.Text('{}:'.format(date_title), pad=((0, pad_el), 0), background_color=bg_col, font=bold_font),
                      sg.Text(record_date, key=self.key_lookup('RecordDate'), auto_size_text=True, font=main_font,
                              background_color=bg_col)]]
        try:
            amount_title = header_elements.get('Amount', 'Amount')
        except KeyError:
            print('Warning: the parameter "Amount" was not included in the list of configured data elements')
            amount_title = 'Amount'

        orig_amount = self.amount
        amount_layout = [[sg.Text('{}:'.format(amount_title), pad=((0, pad_el), 0), background_color=bg_col,
                                  font=bold_font),
                          sg.Text('{:,.2f}'.format(self.update_amount()), key=self.key_lookup('Amount'), size=(14, 1),
                                  font=main_font, background_color=bg_col, border_width=1, relief="sunken",
                                  tooltip='Import amount: {}'.format('{:,.2f}'.format(orig_amount)))]]

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
        default_col = mod_const.ACTION_COL
        greater_col = mod_const.PASS_COL
        lesser_col = mod_const.FAIL_COL

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
                result = param.run_event(window, event, values, user)
        elif event in component_elems:  # component table event
            try:
                component_table = self.fetch_component(event, by_key=True)
            except KeyError:
                print('Error: record {ID}: unable to find component associated with event key {KEY}'
                      .format(ID=self.record_id, KEY=event))
            else:
                result = component_table.run_event(window, event, values, user)

            amount_total = self.update_amount()
            window[self.key_lookup('Amount')].update(value='{:,.2f}'.format(amount_total))
        elif event in reference_elems:
            try:
                refbox = self.fetch_reference(event, by_key=True)
            except KeyError:
                print('Error: record {ID}: unable to find reference associated with event key {KEY}'
                      .format(ID=self.record_id, KEY=event))
            else:
                result = refbox.run_event(window, event, values, user)
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

    def update_amount(self):
        """
        Update the amount element and attribute based on transaction totals.
        """
        # Update the deposit element, in case a component was added or deleted
        try:
            table = self.fetch_component('transaction')
        except KeyError:
            print('Configuration Error: RecordEntry {TYPE}: missing required component records of type "transaction"'
                  .format(TYPE=self.record_type))
            total = 0
        else:
            total = table.calculate_total()
            print('Info: record {ID}: total income was calculated from the transaction table is {VAL}'
                  .format(ID=self.record_id, VAL=total))

        self.amount = total

        return total


class TAuditRecord(DatabaseRecord):
    """
    Class to manage the layout of an audit record.
    """

    def __init__(self, record_entry, record_data):
        """
        remainder (float): remaining total after subtracting component record totals.
        """
        super().__init__(record_entry, record_data)
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
        print('remainder before is {} and after is'.format(record_data['Remainder']), self.remainder)

        try:
            self.note = record_data['Notes']
        except KeyError:
            self.note = ''

    def header_layout(self):
        """
        Generate the layout for the header section of the record layout.
        """
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
                      sg.Text(self.record_id, key=self.key_lookup('RecordID'), pad=((0, pad_h), 0), auto_size_text=True,
                              font=main_font, background_color=bg_col, tooltip=id_tooltip),
                      sg.Text('{}:'.format(date_title), pad=((0, pad_el), 0), background_color=bg_col, font=bold_font),
                      sg.Text(record_date, key=self.key_lookup('RecordDate'), pad=((0, pad_h), 0),
                              auto_size_text=True, font=main_font, background_color=bg_col),
                      sg.Button('', key=self.key_lookup('NotesButton'), image_data=mod_const.TAKE_NOTE_ICON,
                                button_color=(text_col, bg_col), border_width=0, tooltip=notes_title),
                      sg.Text(self.note, key=self.key_lookup('Notes'), size=(1, 1), visible=False)]
                     ]
        try:
            remainder_title = header_elements.get('Remainder', 'Remainder')
        except KeyError:
            print('Warning: the parameter "Remainder" was not included in the list of configured data elements')
            remainder_title = 'Remainder'

        orig_amount = self.remainder
        remainder_layout = [[sg.Text('{}:'.format(remainder_title), pad=((0, pad_el), 0), background_color=bg_col,
                                     font=bold_font),
                             sg.Text('{:,.2f}'.format(self.update_remainder()), key=self.key_lookup('Remainder'),
                                     size=(14, 1), font=main_font, background_color=bg_col, border_width=1,
                                     relief="sunken",
                                     tooltip='Import amount: {}'.format('{:,.2f}'.format(orig_amount)))]]

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
        default_col = mod_const.ACTION_COL
        greater_col = mod_const.PASS_COL
        lesser_col = mod_const.FAIL_COL

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

            # Change edit note button to be highlighted if note field not empty
            if note_text:
                window[event].update(image_data=mod_const.EDIT_NOTE_ICON)
            else:
                window[event].update(image_data=mod_const.TAKE_NOTE_ICON)
        elif event in param_elems:  # parameter event
            try:
                param = self.fetch_element(event, by_key=True)
            except KeyError:
                print('Error: record {ID}: unable to find parameter associated with event key {KEY}'
                      .format(ID=self.record_id, KEY=event))
            else:
                result = param.run_event(window, event, values, user)

            # Update the remainder element, in case a component was added or deleted
            remainder = self.update_remainder()
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
        elif event in component_elems:  # component table event
            try:
                component_table = self.fetch_component(event, by_key=True)
            except KeyError:
                print('Error: record {ID}: unable to find component associated with event key {KEY}'
                      .format(ID=self.record_id, KEY=event))
            else:
                result = component_table.run_event(window, event, values, user)

            # Update the remainder element, in case a component was added or deleted
            remainder = self.update_remainder()
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

        elif event in reference_elems:
            try:
                refbox = self.fetch_reference(event, by_key=True)
            except KeyError:
                print('Error: record {ID}: unable to find reference associated with event key {KEY}'
                      .format(ID=self.record_id, KEY=event))
            else:
                result = refbox.run_event(window, event, values, user)
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

    def update_remainder(self):
        """
        Update the remainder amount element and remainder attribute based on component table totals and totals parameter.
        """
        # Update the remainder element, in case a component was added or deleted
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

        self.remainder = remainder
        return remainder


class AuditRecord:
    """
    Class to store information about an audit record.
    """

    def __init__(self, rule_name, name, sdict):

        self.rule_name = rule_name
        self.name = name
        self.element_key = mod_lo.as_key('{RULE} Summary {NAME}'.format(RULE=rule_name, NAME=name))
        self.elements = ['DocNo', 'Totals', 'Table', 'Add', 'Delete', 'Total', 'Remainder', 'TabHeight', 'Note']
        self.type = None

        try:
            self.title = sdict['Title']
        except KeyError:
            self.title = '{} Summary'.format(name)

        try:
            ids = sdict['IDs']
        except KeyError:
            mod_win2.popup_error('Configuration Error: rule {RULE}, summary {NAME}: missing required parameter "IDs"'
                                 .format(RULE=self.rule_name, NAME=self.name))
            sys.exit(1)

        if len(ids) < 1:
            mod_win2.popup_error('Configuration Error: rule {RULE}, summary {NAME}: "IDs" must include at least one '
                                 'primary ID field'.format(RULE=self.rule_name, NAME=self.name))
            sys.exit(1)

        has_primary = False
        for id_field in ids:
            id_param = ids[id_field]

            if 'Title' not in id_param:
                id_param['Title'] = id_field
            if 'Format' not in id_param:
                mod_win2.popup_error(
                    'Configuration Error: rule {RULE}, summary {NAME}: "Format" is a required field for '
                    'IDs entry "{ID}"'.format(RULE=self.rule_name, NAME=self.name, ID=id_field))
                sys.exit(1)
            else:
                id_param['Format'] = re.findall(r'\{(.*?)\}', id_param['Format'])
            if 'DatabaseTable' not in id_param:
                mod_win2.popup_error('Configuration Error: rule {RULE}, summary {NAME}: "DatabaseTable" is a required '
                                     'field for IDs entry "{ID}"'.format(RULE=self.rule_name, NAME=self.name,
                                                                         ID=id_field))
                sys.exit(1)
            if 'DatabaseField' not in id_param:
                mod_win2.popup_error('Configuration Error: rule {RULE}, summary {NAME}: "DatabaseField" is a required '
                                     'field for IDs entry "{ID}"'.format(RULE=self.rule_name, NAME=self.name,
                                                                         ID=id_field))
                sys.exit(1)
            if 'IsUnique' not in id_param:
                id_param['IsUnique'] = False
            else:
                try:
                    is_unique = bool(int(id_param['IsUnique']))
                except ValueError:
                    mod_win2.popup_error(
                        'Configuration Error: rule {RULE}, summary {NAME}: "IsUnique" must be either 0 '
                        '(False) or 1 (True)'.format(RULE=self.rule_name, NAME=self.name))
                    sys.exit(1)
                else:
                    id_param['IsUnique'] = is_unique
            if 'IsPrimary' not in id_param:
                id_param['IsPrimary'] = False
            else:
                try:
                    is_primary = bool(int(id_param['IsPrimary']))
                except ValueError:
                    mod_win2.popup_error(
                        'Configuration Error: rule {RULE}, summary {NAME}: "IsPrimary" must be either 0 '
                        '(False) or 1 (True)'.format(RULE=self.rule_name, NAME=self.name))
                    sys.exit(1)
                else:
                    id_param['IsPrimary'] = is_primary
                    if is_primary is True:
                        if has_primary is True:
                            mod_win2.popup_error('Configuration Error: rule {RULE}, summary {NAME}: only one "IDs" '
                                                 'parameter can be set as the primary ID field'
                                                 .format(RULE=self.rule_name, NAME=self.name))
                            sys.exit(1)
                        else:
                            has_primary = True

        if has_primary is False:
            mod_win2.popup_error('Configuration Error: rule {RULE}, summary {NAME}: "IDs" must include at least one '
                                 'primary ID field'.format(RULE=self.rule_name, NAME=self.name))

        self.ids = ids

        try:
            self.export_rules = sdict['ExportRules']
        except KeyError:
            self.export_rules = None

        try:
            self.import_rules = sdict['ImportRules']
        except KeyError:
            self.import_rules = None

        try:
            all_columns = sdict['TableColumns']
        except KeyError:
            msg = 'Configuration Error: rule {RULE}, summary {NAME}: missing required field "TableColumns".' \
                .format(NAME=name, RULE=rule_name)
            mod_win2.popup_error(msg)
            sys.exit(1)
        self.db_columns = all_columns

        try:
            records = sdict['Records']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}, summary {NAME}: missing required parameter "Records".') \
                .format(RULE=rule_name, NAME=name)
            mod_win2.popup_error(msg)
            sys.exit(1)
        msg = _('Configuration Error: rule {RULE}, summary {NAME}: missing required field "{FIELD}" '
                'in the "Records" parameter.')
        if 'TableColumns' not in records:
            mod_win2.popup_error(msg.format(RULE=rule_name, NAME=name, FEILD='TableColumns'))
            sys.exit(1)
        if 'SumColumn' not in records:
            mod_win2.popup_error(msg.format(RULE=rule_name, NAME=name, FEILD='SumColumn'))
            sys.exit(1)
        else:
            if records['SumColumn'] not in records['TableColumns']:
                mod_win2.popup_error(
                    'Configuration Error: rule {RULE}, name {NAME}: SumColumn {SUM} not in list of table '
                    'columns'.format(RULE=rule_name, NAME=name, SUM=records['SumColumn']))
                sys.exit(1)
        if 'DisplayHeader' not in records:
            records['DisplayHeader'] = ''
        if 'DisplayColumns' not in records:
            mod_win2.popup_error(msg.format(RULE=rule_name, NAME=name, FEILD='DisplayColumns'))
            sys.exit(1)
        if 'MappingColumns' not in records:
            records['MappingColumns'] = {}
        if 'ReferenceTables' not in records:
            records['ReferenceTables'] = {}
        if 'EditColumns' not in records:
            records['EditColumns'] = {}
        if 'StaticColumns' not in records:
            records['StaticColumns'] = {}

        self.records = records

        try:
            totals = sdict['Totals']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}, summary {NAME}: missing required parameter "Totals".') \
                .format(RULE=rule_name, NAME=name)
            mod_win2.popup_error(msg)
            sys.exit(1)

        msg = _('Configuration Error: rule {RULE}, summary {NAME}: missing required field "{FIELD}" '
                'in the "Totals" parameter.')
        if 'TableColumns' not in totals:
            mod_win2.popup_error(msg.format(RULE=rule_name, NAME=name, FEILD='TableColumns'))
            sys.exit(1)
        if 'DisplayHeader' not in totals:
            totals['DisplayHeader'] = ''
        if 'DisplayColumns' not in totals:
            mod_win2.popup_error(msg.format(RULE=rule_name, NAME=name, FEILD='DisplayColumns'))
            sys.exit(1)
        if 'MappingColumns' not in totals:
            totals['MappingColumns'] = {}
        if 'EditColumns' not in totals:
            totals['EditColumns'] = {}
        if 'TallyRule' not in totals:
            totals['TallyRule'] = None

        self.totals = totals

        try:
            notes = sdict['Notes']
        except KeyError:
            notes = {}
        if 'Title' not in notes:
            notes['Title'] = "Notes"
        if 'Field' not in notes:
            notes['Field'] = "Notes"
        notes['Value'] = ''

        self.notes = notes

        try:
            self.error_rules = sdict['ErrorRules']
        except KeyError:
            self.error_rules = {}

        try:
            self.aliases = sdict['Aliases']
        except KeyError:
            self.aliases = []

        try:
            import_parameters = sdict['ImportParameters']
        except KeyError:
            import_parameters = {}
        for import_param in import_parameters:
            param_entry = import_parameters[import_param]
            if 'Statement' not in param_entry:
                msg = 'Configuration Error: rule {RULE}, summary {NAME}: missing required parameter "Statement" for ' \
                      'ImportParameters entry {ENTRY}'.format(RULE=rule_name, NAME=name, ENTRY=import_param)
                mod_win2.popup_error(msg)
                sys.exit(1)
            if 'Parameters' not in param_entry:
                msg = 'Configuration Error: rule {RULE}, summary {NAME}: missing required parameter "Parameters" for ' \
                      'ImportParameters entry {ENTRY}'.format(RULE=rule_name, NAME=name, ENTRY=import_param)
                mod_win2.popup_error(msg)
                sys.exit(1)

        self.import_parameters = import_parameters

        # Dynamic attributes
        header = [mod_dm.colname_from_query(i) for i in all_columns]
        self.df = self.import_df = self.removed_df = pd.DataFrame(columns=header)

        totals_header = list(set(list(totals['MappingColumns'].keys()) + list(totals['EditColumns'].keys())))
        self.totals_df = pd.DataFrame(columns=totals_header)

        self.id = None
        self.parameters = None

    def reset_dynamic_attributes(self):
        """
        Reset Summary values.
        """
        header = self.df.columns.values
        self.df = self.import_df = self.removed_df = pd.DataFrame(columns=header)

        totals_header = self.totals_df.columns.values
        self.totals_df = pd.DataFrame(columns=totals_header)

        self.id = None
        self.parameters = None
        self.notes['Value'] = ''

    def reset_tables(self):
        """
        Reset Summary tables.
        """
        header = self.df.columns.values
        self.df = self.removed_df = pd.DataFrame(columns=header)

        totals_header = self.totals_df.columns.values
        self.totals_df = pd.DataFrame(columns=totals_header)

    def remove_unsaved_keys(self):
        """
        Remove unsaved IDs from the table IDs lists.
        """
        for id_field in self.ids:
            id_param = self.ids[id_field]
            db_table = id_param['DatabaseTable']
            print('Info: rule {RULE}, summary {NAME}: removing unsaved IDs created in cancelled audit from table '
                  '{TBL}, column {ID}'.format(RULE=self.rule_name, NAME=self.name, TBL=db_table, ID=id_field))

            try:
                all_ids = self.df[id_field].dropna().unique().tolist()
                existing_ids = self.import_df[id_field].dropna().unique().tolist()
            except KeyError:
                created_ids = set()
            else:
                created_ids = set(all_ids).difference(set(existing_ids))

            for record_id in created_ids:
                try:
                    current_tbl_pkeys[db_table].remove(record_id)
                except ValueError:
                    print('Warning: attempting to remove non-existent ID "{ID}" from the list of '
                          'database table {TBL} IDs'.format(ID=record_id, TBL=db_table))
                    continue
                else:
                    print('Info: rule {RULE}, summary {NAME}: removed ID {ID} from the list of database table {TBL} IDs'
                          .format(RULE=self.rule_name, NAME=self.name, ID=record_id, TBL=db_table))

    def key_lookup(self, element):
        """
        Lookup element key for input control element.
        """
        if element in self.elements:
            key = mod_lo.as_key('{RULE} Summary {NAME} {ELEM}'.format(RULE=self.rule_name, NAME=self.name, ELEM=element))
        else:
            print('Warning: rule {RULE}, summary {NAME}: unable to find GUI element {ELEM} in list of elements'
                  .format(RULE=self.rule_name, NAME=self.name, ELEM=element))
            key = None

        return key

    def set_datatypes(self):
        """
        Set column data types based on header mapping
        """
        df = self.df.copy()
        header_map = self.records['TableColumns']

        for column in header_map:
            try:
                dtype = header_map[column]
            except KeyError:
                dtype = 'varchar'
                astype = object
            else:
                if dtype in ('date', 'datetime', 'timestamp', 'time', 'year'):
                    astype = np.datetime64
                elif dtype in ('int', 'integer', 'bit'):
                    astype = int
                elif dtype in ('float', 'decimal', 'dec', 'double', 'numeric', 'money'):
                    astype = float
                elif dtype in ('bool', 'boolean'):
                    astype = bool
                elif dtype in ('char', 'varchar', 'binary', 'text'):
                    astype = object
                else:
                    astype = object

            try:
                df[column] = df[column].astype(astype, errors='raise')
            except (ValueError, TypeError):
                print('Warning: rule {RULE}, summary {NAME}: unable to set column {COL} to data type {DTYPE}'
                      .format(RULE=self.rule_name, NAME=self.name, COL=column, DTYPE=dtype))

        self.df = df

    def layout(self, win_size: tuple = None):
        """
        GUI layout for the summary item.
        """
        if win_size:
            width, height = win_size
        else:
            width, height = (mod_const.WIN_WIDTH, mod_const.WIN_HEIGHT)

        display_columns = self.records['DisplayColumns']
        totals_columns = self.totals['DisplayColumns']

        # Window and element size parameters
        bg_col = mod_const.ACTION_COL
        text_col = mod_const.TEXT_COL

        font = mod_const.MID_FONT
        font_b = mod_const.BOLD_MID_FONT

        pad_frame = mod_const.FRAME_PAD
        pad_el = mod_const.ELEM_PAD
        pad_v = mod_const.VERT_PAD

        tbl_pad = (0, 0)

        # Layout
        # Tab header
        for id_field in self.ids:
            id_param = self.ids[id_field]
            if id_param['IsPrimary'] is True:
                tab_title = id_param['Title']
                break

        no_key = self.key_lookup('DocNo')
        note_key = self.key_lookup('Note')
        header_layout = [
            [sg.Col([
                [sg.Text('{}:'.format(tab_title), pad=((0, pad_el), 0), font=font_b,
                         background_color=bg_col),
                 sg.Text('', key=no_key, size=(20, 1), pad=((pad_el, 0), 0), justification='l',
                         font=font_b, background_color=bg_col, auto_size_text=True, border_width=0)],
                [sg.HorizontalSeparator(pad=(0, (pad_el * 2, 0)), color=mod_const.HEADER_COL)]],
                pad=(0, 0), background_color=bg_col, vertical_alignment='t'),
                sg.Col([[sg.Button('', key=note_key, pad=(0, 0), image_data=mod_const.TAKE_NOTE_ICON, visible=True,
                                   button_color=(text_col, bg_col), border_width=0, tooltip=self.notes['Title'])]],
                       pad=(pad_v, 0), background_color=bg_col, vertical_alignment='t')]]

        # Data tables
        records_header = list(display_columns.keys())
        totals_header = list(totals_columns.keys())

        records_title = self.records['DisplayHeader']
        tbl_key = self.key_lookup('Table')
        add_key = self.key_lookup('Add')
        delete_key = self.key_lookup('Delete')
        remain_key = self.key_lookup('Remainder')
        data = mod_dm.create_empty_table(nrow=5, ncol=len(records_header))
        records_layout = [[mod_lo.create_table_layout(data, records_header, tbl_key, bind=True, height=height, width=width,
                                                      pad=tbl_pad, add_key=add_key, delete_key=delete_key,
                                                      table_name=records_title)],
                          [sg.Col([[sg.Text('Remainder:', pad=((0, pad_el), 0), font=font_b, background_color=bg_col),
                                    sg.Text('', key=remain_key, size=(14, 1), pad=((pad_el, 0), 0), font=font,
                                            background_color=bg_col, justification='r', relief='sunken')]],
                                  pad=(0, (pad_v, 0)), background_color=bg_col, justification='r')], ]

        totals_title = self.totals['DisplayHeader']
        totals_data = mod_dm.create_empty_table(nrow=1, ncol=len(totals_header))
        totals_key = self.key_lookup('Totals')
        total_key = self.key_lookup('Total')
        totals_layout = [[mod_lo.create_table_layout(totals_data, totals_header, totals_key, bind=True, height=height,
                                                     width=width, nrow=1, pad=tbl_pad, table_name=totals_title)],
                         [sg.Col([[sg.Text('Total:', pad=((0, pad_el), 0), font=font_b, background_color=bg_col),
                                   sg.Text('', key=total_key, size=(14, 1), pad=((pad_el, 0), 0), font=font,
                                           background_color=bg_col, justification='r', relief='sunken')]],
                                 pad=(0, (pad_v, 0)), background_color=bg_col, justification='r')]]

        main_layout = [
            [sg.Col(header_layout, pad=(pad_frame, (pad_frame, pad_v)), background_color=bg_col, expand_x=False)],
            [sg.Col(totals_layout, pad=(pad_frame, pad_v), background_color=bg_col)],
            [sg.Col(records_layout, pad=(pad_frame, (pad_v, pad_frame)), background_color=bg_col)]]

        height_key = self.key_lookup('TabHeight')
        frame_height = height * 0.8
        layout = [[sg.Canvas(key=height_key, size=(0, frame_height * 0.70)),
                   sg.Col(main_layout, pad=(0, 0), justification='l', vertical_alignment='t',
                          background_color=bg_col, expand_x=True)]]

        return layout

    def resize_elements(self, window, win_size: tuple = None):
        """
        Reset Tab width to default when resized.
        """
        if win_size:
            width, height = win_size
        else:
            width, height = (mod_const.WIN_WIDTH, mod_const.WIN_HEIGHT)

        tbl_key = self.key_lookup('Table')
        totals_key = self.key_lookup('Totals')
        element_key = self.element_key  # Tab item key

        # Reset table size
        # For every five-pixel increase in window size, increase tab size by one
        tab_pad = 120
        win_diff = width - mod_const.WIN_WIDTH
        tab_pad = int(tab_pad + (win_diff / 5))

        frame_width = width - tab_pad if tab_pad > 0 else width
        tab_width = frame_width - 40
        window.bind("<Configure>", window[element_key].Widget.config(width=tab_width))

        layout_height = height * 0.8
        tab_height = layout_height * 0.70
        height_key = self.key_lookup('TabHeight')
        window[height_key].set_size((None, tab_height))

        # Reset table column sizes
        record_columns = self.records['DisplayColumns']
        header = list(record_columns.keys())

        tbl_width = tab_width - 42
        lengths = mod_dm.calc_column_widths(header, width=tbl_width, pixels=True)
        for col_index, col_name in enumerate(header):
            col_width = lengths[col_index]
            window[tbl_key].Widget.column(col_name, width=col_width)

        window[tbl_key].expand((True, True))
        window[tbl_key].table_frame.pack(expand=True, fill='both')

        totals_columns = self.totals['DisplayColumns']
        totals_header = list(totals_columns.keys())
        lengths = mod_dm.calc_column_widths(totals_header, width=tbl_width, pixels=True)
        for col_index, col_name in enumerate(totals_header):
            col_width = lengths[col_index]
            window[totals_key].Widget.column(col_name, width=col_width)

        window[totals_key].expand((True, True))
        window[totals_key].table_frame.pack(expand=True, fill='both')

        window.refresh()

        # Expand 1 row every 40 pixel increase in window size
        height_diff = int((height - mod_const.WIN_HEIGHT) / 40)
        nrows = 3 + height_diff if height_diff > -3 else 1
        window[totals_key].update(num_rows=1)
        window[tbl_key].update(num_rows=nrows)

    def fetch_parameter(self, element, by_key: bool = False):
        """
        Fetch a GUI parameter element by name or event key.
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
            raise KeyError('element {ELEM} not found in list of {NAME} data elements'
                           .format(ELEM=element, NAME=self.name))

        return parameter

    def update_id_components(self, id_param):
        """
        Update the IDs attribute to include a list of component lengths.
        """
        parameters = self.parameters
        param_fields = [i.name for i in parameters]

        id_format = id_param['Format']

        last_index = 0
        id_components = []
        for component in id_format:
            if len(component) > 1 and set(component).issubset(set('YMD-/ ')):  # component is datestr
                component_len = len(component)
                index = (last_index, last_index + component_len)
                part_tup = ('date', component, index)
            elif component in param_fields:
                param = parameters[param_fields.index(component)]
                value = param.value
                component_len = len(value)
                index = (last_index, last_index + component_len)
                part_tup = (component, value, index)
            elif component.isnumeric():  # component is an incrementing number
                component_len = len(component)
                index = (last_index, last_index + component_len)
                part_tup = ('variable', component_len, index)
            else:  # unknown component type, probably separator
                component_len = len(component)
                index = (last_index, last_index + component_len)
                part_tup = ('separator', component, index)

            id_components.append(part_tup)
            last_index += component_len

        return id_components

    def get_id_component(self, identifier, component, id_param):
        """
        Extract the specified component values from the provided identifier.
        """
        id_components = self.update_id_components(id_param)

        comp_value = ''
        for id_component in id_components:
            comp_name, comp_desc, comp_index = id_component

            if component == comp_name:
                try:
                    comp_value = identifier[comp_index[0]: comp_index[1]]
                except IndexError:
                    print('Warning: ID component {COMP} cannot be found in identifier {IDENT}'
                          .format(COMP=component, IDENT=identifier))

                break

        return comp_value

    def create_id(self, id_param, prev_ids):
        """
        Create a new ID based on a list of previous IDs.
        """
        param_fields = [i.name for i in self.parameters]
        id_format = id_param['Format']

        # Get parameter values of new ID

        # Determine date parameter of the new ID
        date_param = self.fetch_parameter('date', by_type=True)
        if date_param:
            date = settings.apply_date_offset(date_param.value_obj)
        else:
            date = settings.apply_date_offset(datetime.datetime.now())

        id_date = date.strftime(settings.format_date_str())
        for component in id_format:
            if len(component) > 1 and set(component).issubset(set('YMD-/ ')):  # component is datestr
                date_fmt = settings.format_date_str(date_str=component)

                id_date = date.strftime(date_fmt)

        # Get parameter values of parameters composing the new ID
        id_param_values = {}
        for param_field in param_fields:
            if param_field in id_format:  # parameter is a component of the ID
                param = self.fetch_parameter(param_field)
                if isinstance(param.value_obj, datetime.datetime):
                    value = param.value_obj.strftime('%Y%m%d')
                else:
                    value = param.value

                id_param_values[param_field] = value

        # Search list of used IDs occurring within the current date cycle
        if len(prev_ids) > 0:
            used_ids = []
            for prev_id in prev_ids:
                prev_date = self.get_id_component(prev_id, 'date', id_param)
                if prev_date != id_date:
                    continue

                matching_params = []
                for param_field in id_param_values:
                    current_param_val = id_param_values[param_field]
                    prev_param_val = self.get_id_component(prev_id, param_field, id_param)
                    if current_param_val != prev_param_val:
                        matching_params.append(False)
                    else:
                        matching_params.append(True)

                if all(matching_params):
                    used_ids.append(prev_id)

            print('Info: rule {RULE}, summary {NAME}: the IDs matching the parameter requirements are {LIST}'
                  .format(RULE=self.rule_name, NAME=self.name, LIST=used_ids))

            if len(used_ids) > 0:
                last_id = sorted(used_ids)[-1]
                print('Info: rule {RULE}, summary {NAME}: most recent ID in list is {ID}'
                      .format(RULE=self.rule_name, NAME=self.name, ID=last_id))
                try:
                    last_var = int(self.get_id_component(last_id, 'variable', id_param))
                except ValueError:
                    last_var = 0
            else:
                last_var = 0
        else:
            last_var = 0

        id_parts = []
        for component in id_format:
            if len(component) > 1 and set(component).issubset(set('YMD-/ ')):  # component is datestr
                id_parts.append(id_date)
            elif component in param_fields:
                param = self.fetch_parameter(component)
                if isinstance(param.value_obj, datetime.datetime):
                    value = param.value_obj.strftime('%Y%m%d')
                else:
                    value = param.value
                id_parts.append(value)
            elif component.isnumeric():  # component is an incrementing number
                number = str(last_var + 1)

                num_length = len(component)
                id_num = number.zfill(num_length)
                id_parts.append(id_num)
            else:  # unknown component type, probably separator or constant
                id_parts.append(component)

        return ''.join(id_parts)

    def assign_record_ids(self, df, index, id_entries: list = None):
        """
        Create and assign new IDs for the audit summary item records.
        """
        id_entries = id_entries if id_entries is not None else self.ids

        # Create identifiers as defined in the configuration
        for id_field in id_entries:
            id_param = id_entries[id_field]
            db_table = id_param['DatabaseTable']

            if 'FilterRules' in id_param:  # don't create IDs for entries with specified filter rules
                continue

            all_ids = current_tbl_pkeys[db_table]
            try:
                current_ids = df[id_field].dropna().unique().tolist()
            except KeyError:
                print('Error: rule {RULE}, summary {NAME}: ID column {ID} missing from the dataframe'
                      .format(RULE=self.rule_name, NAME=self.name, ID=id_field))
                return df

            print('Info: rule {RULE}, summary {NAME}: list of currents IDs for ID {ID} is {LIST}'
                  .format(RULE=self.rule_name, NAME=self.name, ID=id_field, LIST=current_ids))

            if id_param['IsUnique'] is True:
                record_id = self.create_id(id_param, all_ids)
                print('Info: rule {RULE}, summary {NAME}: saving new record {ID} to list of table {TBL} IDs'
                      .format(RULE=self.rule_name, NAME=self.name, ID=record_id, TBL=db_table))
                current_tbl_pkeys[db_table].append(record_id)
            elif id_param['IsPrimary'] is True and self.id is not None:
                record_id = self.id
            else:
                if len(current_ids) > 0:
                    record_id = current_ids[0]
                else:
                    record_id = self.create_id(id_param, all_ids)
                    print('Info: rule {RULE}, summary {NAME}: saving new record {ID} to list of table {TBL} IDs'
                          .format(RULE=self.rule_name, NAME=self.name, ID=record_id, TBL=db_table))
                    current_tbl_pkeys[db_table].append(record_id)

            print('Info: rule {RULE}, summary {NAME}: adding record ID {ID} to the summary table row {INDEX}, column '
                  '{COL}'.format(RULE=self.rule_name, NAME=self.name, ID=record_id, INDEX=index, COL=id_field))
            df.at[index, id_field] = record_id

            if id_param['IsPrimary'] is True and self.id is None:
                print('Info: rule {RULE}, summary {NAME}: the identifier for the audit is {ID}'
                      .format(RULE=self.rule_name, NAME=self.name, ID=record_id))
                self.id = record_id

        return df

    def add_row(self, win_size: tuple = None):
        """
        Add a new row to the records table.
        """
        df = self.df.copy()
        edit_columns = self.records['EditColumns']
        display_columns = self.records['DisplayColumns']

        header = df.columns.values.tolist()

        # Initialize new empty row
        nrow = df.shape[0]
        new_index = nrow - 1 + 1  # first index starts at 0

        df = df.append(pd.Series(), ignore_index=True)

        # Create identifiers for the new row
        df = self.assign_record_ids(df, new_index)

        id_map = {}
        for id_field in self.ids:
            id_map[id_field] = df.at[new_index, id_field]

        # Update the amounts column
        sum_column = self.records['SumColumn']
        df.at[new_index, sum_column] = 0.0

        # Fill in the parameters columns
        params = self.parameters
        for param in params:
            column = param.alias
            if column in header:
                df.at[new_index, column] = param.value_obj

        # Forward fill static columns
        static_cols = list(self.records['StaticColumns'].keys())
        df.loc[:, static_cols] = df.loc[:, static_cols].ffill(axis=0)

        # Forward fill editable columns
        edit_cols = list(self.records['EditColumns'].keys())
        df.loc[:, edit_cols] = df.loc[:, edit_cols].ffill(axis=0)

        # Fill in other columns
        df = mod_dm.fill_na(df)

        # Display the add row window
        display_map = {display_columns[i]: i for i in display_columns}
        df = mod_win2.modify_record(df, new_index, edit_columns, header_map=display_map, win_size=win_size, edit=False)

        # Remove IDs from list of table IDs if record creation cancelled
        if nrow + 1 != df.shape[0]:  # new record creation cancelled
            for id_field in self.ids:
                id_param = self.ids[id_field]
                db_table = id_param['DatabaseTable']

                if id_param['IsPrimary'] is True:  # don't remove primary audit ID
                    continue
                else:
                    id_value = id_map[id_field]

                if pd.isna(id_value):  # don't attempt to remove non-existent IDs
                    continue

                # Remove from list of used IDs
                try:
                    current_tbl_pkeys[db_table].remove(id_value)
                except ValueError:
                    print('Warning: attempting to remove non-existent ID "{ID}" from the list of database '
                          'table {TBL} IDs'.format(ID=id_value, TBL=db_table))
                    continue
                else:
                    print('Info: rule {RULE}, summary {NAME}: removed cancelled record {ID} from list of table {TBL} '
                          'IDs'.format(RULE=self.rule_name, NAME=self.name, ID=id_value, TBL=db_table))
        else:
            print(df.iloc[new_index])

        self.df = df

    def edit_row(self, index, win_size: tuple = None):
        """
        Edit row using modify record window.
        """
        df = self.df.copy()
        try:
            row = df[index]
        except IndexError:
            mod_win2.popup_error('Warning: failed to edit record - no record found at table index {IND} to edit'
                                 .format(IND=index))
            return df

        df = mod_win2.modify_record(df, index, edit_columns, header_map=display_map, win_size=win_size, edit=True)

    def remove_row(self, index):
        """
        Remove row from tab records table.
        """
        df = self.df.copy()
        removed_df = self.removed_df.copy()

        # Remove IDs of the deleted record from the list of table IDs if not already saved in database
        for id_field in self.ids:
            id_param = self.ids[id_field]
            db_table = id_param['DatabaseTable']

            if id_param['IsPrimary'] is True:  # don't remove primary audit ID
                continue

            record_ids = df[id_field][index]
            existing_ids = self.import_df[id_field].values.tolist()
            for record_id in record_ids:
                if pd.isna(record_id):  # don't attempt to remove non-existent IDs
                    continue

                if record_id not in existing_ids:
                    try:
                        current_tbl_pkeys[db_table].remove(record_id)
                    except ValueError:
                        print('Warning: attempting to remove non-existent ID "{ID}" from the list of database '
                              'table {TBL} IDs'.format(ID=record_id, TBL=db_table))
                        continue
                    else:
                        print('Info: rule {RULE}, summary {NAME}: removed ID {ID} from the list of database table {TBL}'
                              ' IDs'.format(RULE=self.rule_name, NAME=self.name, ID=record_id, TBL=db_table))

        # Add row to the dataframe of removed expenses
        removed_df = removed_df.append(df.iloc[index], ignore_index=True)
        removed_df.reset_index(drop=True, inplace=True)

        # Drop row from the dataframe of included expenses
        df.drop(index, axis=0, inplace=True)
        df.reset_index(drop=True, inplace=True)

        self.removed_df = removed_df
        self.df = df

    def format_display_table(self, dataframe, columns: dict = None, date_fmt: str = None):
        """
        Format dataframe for displaying as a table.
        """
        relativedelta = dateutil.relativedelta.relativedelta
        strptime = datetime.datetime.strptime
        is_float_dtype = pd.api.types.is_float_dtype
        is_datetime_dtype = pd.api.types.is_datetime64_any_dtype

        date_fmt = date_fmt if date_fmt is not None else settings.format_date_str(date_str=settings.display_date_format)

        display_columns = columns if columns is not None else {i: i for i in dataframe.columns.values.tolist()}
        display_header = list(display_columns.keys())

        # Localization specific options
        date_offset = settings.get_date_offset()

        display_df = pd.DataFrame()

        # Subset dataframe by specified columns to display
        for col_name in display_columns:
            col_rule = display_columns[col_name]

            col_to_add = mod_dm.generate_column_from_rule(dataframe, col_rule)
            dtype = col_to_add.dtype
            if is_float_dtype(dtype):
                col_to_add = col_to_add.apply('{:,.2f}'.format)
            elif is_datetime_dtype(dtype):
                col_to_add = col_to_add.apply(lambda x: (strptime(x.strftime(date_fmt), date_fmt) +
                                                         relativedelta(years=+date_offset)).strftime(date_fmt)
                if pd.notnull(x) else '')
            display_df[col_name] = col_to_add

        # Map column values to the aliases specified in the configuration
        for alias_col in self.aliases:
            alias_map = self.aliases[alias_col]  # dictionary of mapped values

            if alias_col not in display_header:
                print('Warning: rule {RULE}, tab {NAME}: alias {ALIAS} not found in the list of display columns'
                      .format(NAME=self.name, RULE=self.rule_name, ALIAS=alias_col))
                continue

            print('Info: rule {RULE}, tab {NAME}: applying aliases {MAP} to {COL}'
                  .format(NAME=self.name, RULE=self.rule_name, MAP=alias_map, COL=alias_col))

            try:
                display_df[alias_col].replace(alias_map, inplace=True)
            except KeyError:
                print('Warning: rule {RULE}, tab {NAME}: alias {ALIAS} not found in the list of display columns'
                      .format(NAME=self.name, RULE=self.rule_name, ALIAS=alias_col))
                continue

        return display_df

    def search_for_errors(self, dataframe=None):
        """
        Use error rules specified in configuration file to annotate rows.
        """
        error_rules = self.error_rules
        df = dataframe if dataframe is not None else self.df
        if df.empty:
            return set()

        errors = []

        # Search for errors in the data based on the defined error rules
        print('Info: rule {RULE}, summary {NAME}: searching for errors based on defined error rules {RULES}'
              .format(NAME=self.name, RULE=self.rule_name, RULES=error_rules))

        results = mod_dm.evaluate_rule_set(df, error_rules)
        for row, result in enumerate(results):
            if result is False:
                print('Info: rule {RULE}, summary {NAME}: table row {ROW} failed one or more condition rule'
                      .format(RULE=self.rule_name, NAME=self.name, ROW=row))
                errors.append(row)

        return set(errors)

    def load_from_database(self, user, params):
        """
        Load previous audit (if exists) and IDs from the program database.
        """
        # Find primary audit ID
        for id_field in self.ids:
            id_param = self.ids[id_field]

            if id_param['IsPrimary'] is True:
                primary_id_field = id_field
                break

        # Prepare the filter rules to filter query results
        main_table = [i for i in self.import_rules][0]
        filters = [i.filter_statement(table=main_table) for i in params]

        # Check for tab-specific query parameters
        filters += self.filter_statements()

        # Query database table for the selected parameters
        df = user.query(self.import_rules, columns=self.db_columns, filter_rules=filters, prog_db=True)

        self.import_df = df
        self.df = self.removed_df = pd.DataFrame(columns=df.columns.values)

        if df.empty:  # data does not exist in the database already
            return False
        else:
            # Find audit ID in existing data
            self.id = df[primary_id_field].dropna().unique()[0]
            print('Info: rule {RULE}, summary {NAME}: the identity of the existing audit is: {ID}'
                  .format(RULE=self.rule_name, NAME=self.name, ID=self.id))

            # Determine if audit has existing notes attached
            notes_field = self.notes['Field']
            try:
                note_series = df[notes_field]
            except KeyError:
                note_value = ''
            else:
                note_value = note_series.unique().tolist()[0]

            self.notes['Value'] = note_value

            return True

    def update_edit_columns(self, df):
        """
        Update empty table cells with editable column default values.
        """
        edit_columns = self.records['EditColumns']
        for edit_column in edit_columns:
            edit_item = edit_columns[edit_column]
            try:
                default_rules = edit_item['DefaultRules']
            except KeyError:
                try:
                    element_type = edit_item['ElementType']
                except KeyError:
                    print('Configuration Warning: rule {RULE}, summary {NAME}: the parameter "ElementType" is required '
                          'for EditColumn {COL}'.format(RULE=self.rule_name, NAME=self.name, COL=edit_column))
                    continue

                if element_type in ('date', 'datetime', 'timestamp', 'time', 'year'):
                    df[edit_column].fillna(datetime.datetime.now(), inplace=True)
                elif element_type in ('int', 'integer', 'bit'):
                    df[edit_column].fillna(0, inplace=True)
                elif element_type in ('float', 'decimal', 'dec', 'double', 'numeric', 'money'):
                    df[edit_column].fillna(0.0, inplace=True)
                elif element_type in ('bool', 'boolean'):
                    df[edit_column].fillna(False, inplace=True)
                elif element_type in ('char', 'varchar', 'binary', 'text'):
                    df[edit_column].fillna('', inplace=True)
                else:
                    df[edit_column].fillna('', inplace=True)
            else:
                for default_value in default_rules:
                    edit_rule = default_rules[default_value]
                    results = mod_dm.evaluate_rule_set(df, {default_value: edit_rule}, as_list=True)
                    for row, result in enumerate(results):
                        if result is True:
                            df.at[row, edit_column] = default_value

        return df

    def update_static_columns(self, df):
        """
        Update empty table cells with static column default values.
        """
        static_columns = self.records['StaticColumns']
        for static_column in static_columns:
            static_entry = static_columns[static_column]
            if static_column not in df.columns:
                df[static_column] = None

            try:
                default_rules = static_entry['DefaultRules']
            except KeyError:
                try:
                    default_value = static_entry['DefaultValue']
                except KeyError:
                    print('Configuration Warning: rule {RULE}, summary {NAME}: one of "DefaultRules" or "DefaultValue" '
                          'is required for StaticColumn {COL}'
                          .format(RULE=self.rule_name, NAME=self.name, COL=static_column))
                    continue
                else:
                    for row_index in range(df.shape[0]):
                        if pd.isna(df.at[row_index, static_column]) is True:
                            df.at[row_index, static_column] = default_value
            else:
                for default_value in default_rules:
                    static_rule = default_rules[default_value]
                    results = mod_dm.evaluate_rule_set(df, {default_value: static_rule}, as_list=True)
                    for row_index, result in enumerate(results):
                        if result is True and pd.isna(df.at[row_index, static_column]):
                            df.at[row_index, static_column] = default_value

        return df

    def filter_statements(self):
        """
        Generate the filter statements for import parameters.
        """
        params = self.import_parameters

        if params is None:
            return []

        filters = []
        for param_name in params:
            param_entry = params[param_name]

            statement = param_entry['Statement']
            param_values = param_entry['Parameters']

            if isinstance(param_values, list) or isinstance(param_values, tuple):
                import_filter = (statement, param_values)
            else:
                import_filter = (statement, (param_values,))

            filters.append(import_filter)

        return filters


class AuditRecordAdd(AuditRecord):
    """
    """

    def __init__(self, rule_name, name, sdict):
        super().__init__(rule_name, name, sdict)
        self.type = 'Add'

    def initialize_table(self, rule):
        """
        Populate the summary item dataframe with added records.
        """
        df = self.import_df.copy()
        print('Info: rule {RULE}, summary {NAME}: updating table'
              .format(RULE=self.rule_name, NAME=self.name))

        if self.import_df.empty:  # no records for selected parameters in database
            # Add empty row to the dataframe
            if df.shape[0]:  # no rows in table
                df = df.append(pd.Series(), ignore_index=True)

            # Create identifiers as defined in the configuration
            df = self.assign_record_ids(df, 0)

            # Set parameter values
            for param in rule.parameters:
                colname = param.alias
                value = param.value_obj
                df.at[0, colname] = value

            # Update amount column
            sum_column = self.records['SumColumn']
            df[sum_column] = pd.to_numeric(df[sum_column], downcast='float')

            tally_rule = self.totals['TallyRule']
            if tally_rule:
                totals_sum = mod_dm.evaluate_rule(self.totals_df.iloc[[0]], tally_rule, as_list=False).sum()
            else:
                totals_sum = self.totals_df.iloc[0].sum()

            df.at[0, sum_column] = totals_sum

        # Update static columns with default values, if specified in rules
        df = self.update_static_columns(df)

        # Update edit columns with default values, if specified in rules
        df = self.update_edit_columns(df)

        self.df = df


class AuditRecordSubset(AuditRecord):
    """
    """

    def __init__(self, rule_name, name, sdict):
        super().__init__(rule_name, name, sdict)
        self.type = 'Subset'

    def initialize_table(self, rule):
        """
        Populate the summary item dataframe with rows from the TabItem dataframes specified in the configuration.
        """
        df = import_df = self.import_df.copy()

        records = self.records

        db_columns = records['TableColumns']
        mapping_columns = records['MappingColumns']
        references = records['ReferenceTables']

        # Get list of existing records
        id_column = records['IDColumn']
        try:
            existing_ids = import_df[id_column].tolist()
        except KeyError:
            print('Configuration Warning: rule {RULE}, summary {NAME}: IDColumn "{COL}" not found in the database table'
                  .format(RULE=self.rule_name, NAME=self.name, COL=id_column))
            existing_ids = []

        print('Info: rule {RULE}, summary {NAME}: updating table'.format(RULE=self.rule_name, NAME=self.name))

        # Extract desired records from the audit tab summaries
        for reference in references:
            subset_rule = references[reference]
            try:
                tab_df = rule.fetch_tab(reference).df
            except AttributeError:
                print('Warning: rule {RULE}, summary {NAME}: reference table {REF} not found in tab items'
                      .format(RULE=self.rule_name, NAME=self.name, REF=reference))
                continue

            # Subset tab item dataframe using subset rules defined in the ReferenceTable parameter
            print('Info: rule {RULE}, summary {NAME}: subsetting reference table {REF}'
                  .format(RULE=self.rule_name, NAME=self.name, REF=reference))
            try:
                subset_df = mod_dm.subset_dataframe(tab_df, subset_rule)
            except Exception as e:
                print('Warning: rule {RULE}, summary {NAME}: subsetting table {REF} failed due to {ERR}'
                      .format(RULE=self.rule_name, NAME=self.name, REF=reference, ERR=e))
                continue
            else:
                if subset_df.empty:
                    print('Info: rule {RULE}, summary {NAME}: no data from reference table {REF} to add to summary'
                          .format(RULE=self.rule_name, NAME=self.name, REF=reference))
                    continue

            # Select columns based on MappingColumns parameter
            append_df = pd.DataFrame(columns=df.columns.values.tolist())
            for mapping_column in mapping_columns:
                if mapping_column not in db_columns:
                    print('Error: rule {RULE}, summary {NAME}: mapping column {COL} not in list of table columns'
                          .format(RULE=self.rule_name, NAME=self.name, COL=mapping_column))
                    continue

                mapping_rule = mapping_columns[mapping_column]
                col_to_add = mod_dm.generate_column_from_rule(subset_df, mapping_rule)
                append_df[mapping_column] = col_to_add

            # Find rows from the dataframe to append that are already found in the existing dataset
            append_ids = append_df[id_column].tolist()

            rows_to_drop = []
            for record_index, record_id in enumerate(append_ids):
                if record_id in existing_ids:
                    print('Info: rule {RULE}, summary {NAME}: record "{ID}" already exists in the database'
                          .format(RULE=self.rule_name, NAME=self.name, ID=record_id))
                    rows_to_drop.append(record_id)
                else:
                    append_df = self.assign_record_ids(append_df, record_index)

            # Filter records from dataframe of records to append that were marked for removal
            append_df = append_df[~append_df[id_column].isin(rows_to_drop)]

            # Append data to the records dataframe
            df = mod_dm.append_to_table(df, append_df)

        self.df = df
        if df.empty:  # no records generated from database or tab summaries
            # Create the primary identifier for the summary tab
            for id_field in self.ids:
                id_param = self.ids[id_field]
                if id_param['IsPrimary'] is True:
                    db_table = id_param['DatabaseTable']
                    all_ids = current_tbl_pkeys[db_table]

                    pkey_param = id_param

                    break

            primary_id = self.create_id(pkey_param, all_ids)

            self.id = primary_id
            current_tbl_pkeys[db_table].append(primary_id)
        else:
            # Set parameter values
            for param in self.parameters:
                colname = param.alias
                value = param.value_obj
                df[colname] = value

            # Update static columns with default values, if specified in rules
            df = self.update_static_columns(df)

            # Update edit columns with default values, if specified in rules
            df = self.update_edit_columns(df)

        self.df = df


def import_records(record_entry, user):
    """
    Load existing records from the program database to select from.
    """
    # Import all records of relevant type from the database
    import_df = record_entry.import_records(user)

    # Display the import record window
    import_table = mod_elem.TableElement(record_entry.name, record_entry.import_table)
    import_table.df = import_table.append(import_df)

    record_id = mod_win2.data_import_window(user, import_table, create_new=False)

    if record_id is None:
        print('Warning: there are no existing records in the database to display')
        return None

    try:
        trans_df = import_df[import_df['RecordID'] == record_id]
    except KeyError:
        print('warning: missing required column "RecordID"')
        return None
    else:
        if trans_df.empty:
            print('Warning: could not find record {ID} in data table'.format(ID=record_id))
            return None
        else:
            record_data = trans_df.iloc[0]

    # Set the record object based on the record type
    record_type = record_entry.type
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

    record = record_class(record_entry, record_data)

    return record


def load_record(record_entry, record_id):
    """
    Load an existing record from the program database.
    """
    # Extract the record data from the database
    import_df = record_entry.load_record(record_id)

    # Set the record object based on the record type
    record_type = record_entry.type
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

    record = record_class(record_entry, import_df)

    return record


def create_record(record_entry, record_data):
    """
    Create a new database record.
    """
    record_type = record_entry.type
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

    record = record_class(record_entry, record_data, new_record=True)

    return record
