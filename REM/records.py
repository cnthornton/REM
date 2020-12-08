"""
REM records classes and functions. Includes audit records and account records.
"""
import datetime
import dateutil
import re
import sys

import numpy as np
import pandas as pd
import PySimpleGUI as sg

import REM.constants as const
import REM.data_manipulation as dm
import REM.layouts as lo
import REM.secondary as win2
from REM.config import configuration, current_tbl_pkeys, settings


class AuditRecord:
    """
    """

    def __init__(self, rule_name, name, sdict):

        self.rule_name = rule_name
        self.name = name
        self.element_key = lo.as_key('{RULE} Summary {NAME}'.format(RULE=rule_name, NAME=name))
        self.elements = ['DocNo', 'Totals', 'Table', 'Add', 'Delete', 'Total', 'Remainder', 'TabHeight', 'Note']
        self.type = None

        try:
            self.title = sdict['Title']
        except KeyError:
            self.title = '{} Summary'.format(name)

        try:
            ids = sdict['IDs']
        except KeyError:
            win2.popup_error('Configuration Error: rule {RULE}, summary {NAME}: missing required parameter "IDs"'
                             .format(RULE=self.rule_name, NAME=self.name))
            sys.exit(1)

        if len(ids) < 1:
            win2.popup_error('Configuration Error: rule {RULE}, summary {NAME}: "IDs" must include at least one '
                             'primary ID field'.format(RULE=self.rule_name, NAME=self.name))
            sys.exit(1)

        has_primary = False
        for id_field in ids:
            id_param = ids[id_field]

            if 'Title' not in id_param:
                id_param['Title'] = id_field
            if 'Format' not in id_param:
                win2.popup_error('Configuration Error: rule {RULE}, summary {NAME}: "Format" is a required field for '
                                 'IDs entry "{ID}"'.format(RULE=self.rule_name, NAME=self.name, ID=id_field))
                sys.exit(1)
            else:
                id_param['Format'] = re.findall(r'\{(.*?)\}', id_param['Format'])
            if 'DatabaseTable' not in id_param:
                win2.popup_error('Configuration Error: rule {RULE}, summary {NAME}: "DatabaseTable" is a required '
                                 'field for IDs entry "{ID}"'.format(RULE=self.rule_name, NAME=self.name, ID=id_field))
                sys.exit(1)
            if 'DatabaseField' not in id_param:
                win2.popup_error('Configuration Error: rule {RULE}, summary {NAME}: "DatabaseField" is a required '
                                 'field for IDs entry "{ID}"'.format(RULE=self.rule_name, NAME=self.name, ID=id_field))
                sys.exit(1)
            if 'IsUnique' not in id_param:
                id_param['IsUnique'] = False
            else:
                try:
                    is_unique = bool(int(id_param['IsUnique']))
                except ValueError:
                    win2.popup_error('Configuration Error: rule {RULE}, summary {NAME}: "IsUnique" must be either 0 '
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
                    win2.popup_error('Configuration Error: rule {RULE}, summary {NAME}: "IsPrimary" must be either 0 '
                                     '(False) or 1 (True)'.format(RULE=self.rule_name, NAME=self.name))
                    sys.exit(1)
                else:
                    id_param['IsPrimary'] = is_primary
                    if is_primary is True:
                        if has_primary is True:
                            win2.popup_error('Configuration Error: rule {RULE}, summary {NAME}: only one "IDs" '
                                             'parameter can be set as the primary ID field'
                                             .format(RULE=self.rule_name, NAME=self.name))
                            sys.exit(1)
                        else:
                            has_primary = True

        if has_primary is False:
            win2.popup_error('Configuration Error: rule {RULE}, summary {NAME}: "IDs" must include at least one '
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
            win2.popup_error(msg)
            sys.exit(1)
        self.db_columns = all_columns

        try:
            records = sdict['Records']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}, summary {NAME}: missing required parameter "Records".') \
                .format(RULE=rule_name, NAME=name)
            win2.popup_error(msg)
            sys.exit(1)
        msg = _('Configuration Error: rule {RULE}, summary {NAME}: missing required field "{FIELD}" '
                'in the "Records" parameter.')
        if 'TableColumns' not in records:
            win2.popup_error(msg.format(RULE=rule_name, NAME=name, FEILD='TableColumns'))
            sys.exit(1)
        if 'SumColumn' not in records:
            win2.popup_error(msg.format(RULE=rule_name, NAME=name, FEILD='SumColumn'))
            sys.exit(1)
        else:
            if records['SumColumn'] not in records['TableColumns']:
                win2.popup_error('Configuration Error: rule {RULE}, name {NAME}: SumColumn {SUM} not in list of table '
                                 'columns'.format(RULE=rule_name, NAME=name, SUM=records['SumColumn']))
                sys.exit(1)
        if 'DisplayHeader' not in records:
            records['DisplayHeader'] = ''
        if 'DisplayColumns' not in records:
            win2.popup_error(msg.format(RULE=rule_name, NAME=name, FEILD='DisplayColumns'))
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
            win2.popup_error(msg)
            sys.exit(1)

        msg = _('Configuration Error: rule {RULE}, summary {NAME}: missing required field "{FIELD}" '
                'in the "Totals" parameter.')
        if 'TableColumns' not in totals:
            win2.popup_error(msg.format(RULE=rule_name, NAME=name, FEILD='TableColumns'))
            sys.exit(1)
        if 'DisplayHeader' not in totals:
            totals['DisplayHeader'] = ''
        if 'DisplayColumns' not in totals:
            win2.popup_error(msg.format(RULE=rule_name, NAME=name, FEILD='DisplayColumns'))
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
                win2.popup_error(msg)
                sys.exit(1)
            if 'Parameters' not in param_entry:
                msg = 'Configuration Error: rule {RULE}, summary {NAME}: missing required parameter "Parameters" for ' \
                      'ImportParameters entry {ENTRY}'.format(RULE=rule_name, NAME=name, ENTRY=import_param)
                win2.popup_error(msg)
                sys.exit(1)

        self.import_parameters = import_parameters

        # Dynamic attributes
        header = [dm.colname_from_query(i) for i in all_columns]
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

            all_ids = self.df[id_field].dropna().unique().tolist()
            existing_ids = self.import_df[id_field].dropna().unique().tolist()
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
            key = lo.as_key('{RULE} Summary {NAME} {ELEM}'.format(RULE=self.rule_name, NAME=self.name, ELEM=element))
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
            width, height = (const.WIN_WIDTH, const.WIN_HEIGHT)

        display_columns = self.records['DisplayColumns']
        totals_columns = self.totals['DisplayColumns']

        # Window and element size parameters
        bg_col = const.ACTION_COL
        text_col = const.TEXT_COL

        font = const.MID_FONT
        font_b = const.BOLD_MID_FONT

        pad_frame = const.FRAME_PAD
        pad_el = const.ELEM_PAD
        pad_v = const.VERT_PAD

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
        #        header_layout = [
        #            [sg.Frame('', [
        #                [sg.Text('{}:'.format(tab_title), pad=((pad_el * 2, pad_el), pad_el * 2), font=font_b,
        #                         background_color=bg_col),
        #                 sg.Text('', key=no_key, size=(20, 1), pad=((pad_el, pad_el * 2), pad_el * 2), justification='l',
        #                         font=font, background_color=bg_col, auto_size_text=True, border_width=0)]],
        #                      pad=(0, 0), background_color=header_col, border_width=1, relief='ridge'),
        #             sg.Col([[sg.Button('', key=note_key, pad=(0, 0), image_data=const.NOTES_ICON, visible=True,
        #                                button_color=(text_col, bg_col), border_width=0, tooltip=self.notes['Title'])]],
        #                    pad=(pad_v, 0), background_color=bg_col, vertical_alignment='c')]]

        header_layout = [
            [sg.Col([
                [sg.Text('{}:'.format(tab_title), pad=((0, pad_el), 0), font=font_b,
                         background_color=bg_col),
                 sg.Text('', key=no_key, size=(20, 1), pad=((pad_el, 0), 0), justification='l',
                         font=font_b, background_color=bg_col, auto_size_text=True, border_width=0)],
                [sg.HorizontalSeparator(pad=(0, (pad_el*2, 0)), color=const.HEADER_COL)]],
                pad=(0, 0), background_color=bg_col, vertical_alignment='t'),
                sg.Col([[sg.Button('', key=note_key, pad=(0, 0), image_data=const.NOTES_ICON, visible=True,
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
        data = dm.create_empty_table(nrow=5, ncol=len(records_header))
        records_layout = [[lo.create_table_layout(data, records_header, tbl_key, bind=True, height=height, width=width,
                                                  pad=tbl_pad, add_key=add_key, delete_key=delete_key,
                                                  table_name=records_title)],
                          [sg.Col([[sg.Text('Remainder:', pad=((0, pad_el), 0), font=font_b, background_color=bg_col),
                                    sg.Text('', key=remain_key, size=(14, 1), pad=((pad_el, 0), 0), font=font,
                                            background_color=bg_col, justification='r', relief='sunken')]],
                                  pad=(0, (pad_v, 0)), background_color=bg_col, justification='r')], ]

        totals_title = self.totals['DisplayHeader']
        totals_data = dm.create_empty_table(nrow=1, ncol=len(totals_header))
        totals_key = self.key_lookup('Totals')
        total_key = self.key_lookup('Total')
        totals_layout = [[lo.create_table_layout(totals_data, totals_header, totals_key, bind=True, height=height,
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
            width, height = (const.WIN_WIDTH, const.WIN_HEIGHT)

        tbl_key = self.key_lookup('Table')
        totals_key = self.key_lookup('Totals')
        element_key = self.element_key  # Tab item key

        # Reset table size
        # For every five-pixel increase in window size, increase tab size by one
        tab_pad = 120
        win_diff = width - const.WIN_WIDTH
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
        lengths = dm.calc_column_widths(header, width=tbl_width, pixels=True)
        for col_index, col_name in enumerate(header):
            col_width = lengths[col_index]
            window[tbl_key].Widget.column(col_name, width=col_width)

        window[tbl_key].expand((True, True))
        window[tbl_key].table_frame.pack(expand=True, fill='both')

        totals_columns = self.totals['DisplayColumns']
        totals_header = list(totals_columns.keys())
        lengths = dm.calc_column_widths(totals_header, width=tbl_width, pixels=True)
        for col_index, col_name in enumerate(totals_header):
            col_width = lengths[col_index]
            window[totals_key].Widget.column(col_name, width=col_width)

        window[totals_key].expand((True, True))
        window[totals_key].table_frame.pack(expand=True, fill='both')

        window.refresh()

        # Expand 1 row every 40 pixel increase in window size
        height_diff = int((height - const.WIN_HEIGHT) / 40)
        nrows = 3 + height_diff if height_diff > -3 else 1
        window[totals_key].update(num_rows=1)
        window[tbl_key].update(num_rows=nrows)

    def fetch_parameter(self, name, by_key: bool = False, by_type: bool = False):
        """
        """
        if by_key and by_type:
            print('Warning: rule {RULE}, summary {NAME}, parameter {PARAM}: the "by_key" and "by_type" arguments are '
                  'mutually exclusive. Defaulting to "by_key".'.format(RULE=self.rule_name, NAME=self.name, PARAM=name))
            by_type = False

        if by_key:
            names = [i.element_key for i in self.parameters]
        elif by_type:
            names = [i.type for i in self.parameters]
        else:
            names = [i.name for i in self.parameters]

        try:
            index = names.index(name)
        except IndexError:
            param = None
        else:
            param = self.parameters[index]

        return param

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
            current_ids = df[id_field].dropna().unique().tolist()

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
        df = dm.fill_na(df)

        # Display the add row window
        display_map = {display_columns[i]: i for i in display_columns}
        df = win2.modify_record(df, new_index, edit_columns, header_map=display_map, win_size=win_size, edit=False)

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

    def edit_row(self, index, element_key, win_size: tuple = None):
        """
        Edit row using modify record window.
        """
        if element_key == self.key_lookup('Table'):
            parameter = self.records
            df = self.df.copy()
            table = 'records'
        elif element_key == self.key_lookup('Totals'):
            parameter = self.totals
            df = self.totals_df.copy()
            table = 'totals'
        else:
            raise KeyError('element key {} does not correspond to either the Totals or Records tables'
                           .format(element_key))

        display_columns = parameter['DisplayColumns']
        edit_columns = parameter['EditColumns']

        display_map = {display_columns[i]: i for i in display_columns}
        df = win2.modify_record(df, index, edit_columns, header_map=display_map, win_size=win_size, edit=True)

        if table == 'records':
            self.df = df
        elif table == 'totals':
            self.totals_df = df

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

            col_to_add = dm.generate_column_from_rule(dataframe, col_rule)
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

        results = dm.evaluate_rule_set(df, error_rules)
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
                    results = dm.evaluate_rule_set(df, {default_value: edit_rule}, as_list=True)
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
                    results = dm.evaluate_rule_set(df, {default_value: static_rule}, as_list=True)
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
                totals_sum = dm.evaluate_rule(self.totals_df.iloc[[0]], tally_rule, as_list=False).sum()
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
                subset_df = dm.subset_dataframe(tab_df, subset_rule)
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
                col_to_add = dm.generate_column_from_rule(subset_df, mapping_rule)
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
            df = dm.append_to_table(df, append_df)

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


