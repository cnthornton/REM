"""
REM configuration classes and functions. Includes audit rules, audit objects,
and rule parameters.
"""
import datetime
from typing import List

import dateutil.parser
import pandas as pd
import PySimpleGUI as sg
import re
import REM.data_manipulation as dm
import REM.layouts as lo
import REM.program_settings as const
import REM.secondary_win as win2
import sys


class ProgramSettings:
    """
    Class to store and manage program configuration settings.

    Arguments:

        cnfg: Parsed YAML file

    Attributes:

        language (str): Display language. Default: EN.
    """

    def __init__(self, cnfg):
        # Display parameters
        settings = cnfg['settings']
        self.language = settings['language'] if settings['language'] else 'en'

        # Database parameters
        ddict = settings['database']
        self.db = DataBase(ddict)

    def translate(self):
        """
        Translate text using chosen language.
        """

    def modify(self):
        """
        """
        pass

    def display(self):
        """
        """
        pass


class DataBase:
    """
    Primary database object for querying databases and initializing
    authentication.

    Attributes:

        driver (str): ODBC driver

        server (str): Database server.

        port (str): Listening port for database connections

        dbname (str): Database name.

        prog_db (str): Program database name.

        alt_dbs (list): Alternative databases to query if targets not found in primary database.
    """

    def __init__(self, ddict):
        self.driver = ddict['odbc_driver']
        self.server = ddict['odbc_server']
        self.port = ddict['odbc_port']
        self.dbname = ddict['database']
        self.prog_db = ddict['rem_database']
        try:
            self.alt_dbs = ddict['alternative_databases']
        except KeyError:
            self.alt_dbs = []


class AuditRules(ProgramSettings):
    """
    Class to store and manage program audit_rule configuration settings.

    Arguments:

        cnfg: parsed YAML file.

    Attributes:

        rules (list): List of AuditRule objects.
    """

    def __init__(self, cnfg):
        super().__init__(cnfg)

        # Audit parameters
        audit_rules = cnfg['audit_rules']
        self.rules = []
        for audit_rule in audit_rules:
            self.rules.append(AuditRule(audit_rule, audit_rules[audit_rule]))

    def print_rules(self):
        """
        Return name of all audit rules defined in configuration file.
        """
        return ([i.name for i in self.rules])

    def fetch_rule(self, name):
        """
        """
        rule_names = self.print_rules()
        try:
            index = rule_names.index(name)
        except IndexError:
            print('Rule {NAME} not in list of configured audit rules. Available rules are {ALL}'
                  .format(NAME=name, ALL=', '.join(self.print_rules())))
            rule = None
        else:
            rule = self.rules[index]

        return (rule)


class AuditRule:
    """
    Class to store and manage a configured audit rule.

    Arguments:

        name (str): audit rule name.

        adict (dict): dictionary of optional and required audit rule arguments.

    Attributes:

        name (str): audit rule name.

        element_key (str): GUI element key.

        permissions (str): permissions required to view the audit. Default: user.

        parameters (list): list of AuditParameter type objects.

        tabs (list): list of TabItem objects.

        summary (SummaryPanel): SummaryPanel object.
    """

    def __init__(self, name, adict):

        self.name = name
        self.element_key = lo.as_key(name)
        try:
            self.permissions = adict['Permissions']
        except KeyError:  # default permission for an audit is 'user'
            self.permissions = 'user'

        self.parameters = []
        self.tabs = []
        self.elements = ['TG', 'Cancel', 'Start', 'Finalize', 'Fill']

        try:
            params = adict['RuleParameters']
        except KeyError:
            msg = 'Configuration Error: the rule parameter "RuleParameters" is required for rule {}'.format(name)
            win2.popup_error(msg)
            sys.exit(1)

        for param in params:
            cdict = params[param]
            self.elements.append(param)

            layout = cdict['ElementType']
            if layout == 'dropdown':
                self.parameters.append(AuditParameterCombo(name, param, cdict))
            elif layout == 'date':
                self.parameters.append(AuditParameterDate(name, param, cdict))
            elif layout == 'date_range':
                self.parameters.append(AuditParameterDateRange(name, param, cdict))
            else:
                msg = 'Configuration Error: unknown rule parameter type {TYPE} in rule {NAME}' \
                    .format(TYPE=layout, NAME=name)
                win2.popup_error(msg)
                sys.exit(1)

        try:
            tdict = adict['Tabs']
        except KeyError:
            msg = 'Configuration Error: the rule parameter "Tabs" is required for rule {}'.format(name)
            win2.popup_error(msg)
            sys.exit(1)

        for tab_name in tdict:
            self.tabs.append(lo.TabItem(name, tab_name, tdict[tab_name]))

        try:
            sdict = adict['Summary']
        except KeyError:
            msg = 'Configuration Error: the rule parameter "Summary" is required for rule {}'.format(name)
            win2.popup_error(msg)
            sys.exit(1)

        self.summary = SummaryPanel(name, sdict)

    def key_lookup(self, element):
        """
        Lookup element key for input control element.
        """
        if element in self.elements:
            key = lo.as_key('{} {}'.format(self.name, element))
        else:
            key = None

        return key

    def resize_elements(self, window, height=800, width=1200):
        """
        Resize Audit Rule GUI elements based on window size
        """
        # Resize space between action buttons
        layout_width = width - 120 if width >= 200 else width
        spacer = layout_width - 124 if layout_width > 124 else 0

        fill_key = self.key_lookup('Fill')
        window[fill_key].set_size((spacer, None))

        # Resize tab elements
        tabs = self.tabs
        for tab in tabs:
            tab.resize_elements(window, height=height, width=width)

    def fetch_tab(self, name, by_key: bool = False):
        """
        """
        if not by_key:
            names = [i.name for i in self.tabs]
        else:
            names = [i.element_key for i in self.tabs]

        try:
            index = names.index(name)
        except ValueError:
            print('Error: rule {RULE}: tab item {TAB} not in list of tab items'.format(RULE=self.name, TAB=name))
            tab_item = None
        else:
            tab_item = self.tabs[index]

        return tab_item

    def fetch_parameter(self, name, by_key: bool = False, by_type: bool = False):
        """
        """
        if by_key and by_type:
            print('Warning: the "by_key" and "by_type" arguments are mutually exclusive. Defaulting to "by_key".')
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

    def layout(self, height=840, width=1200):
        """
        Generate a GUI layout for the audit rule.
        """
        # Element parameters
        inactive_col = const.INACTIVE_COL
        bg_col = const.ACTION_COL
        default_col = const.DEFAULT_COL
        text_col = const.TEXT_COL
        font_h = const.HEADER_FONT

        pad_el = const.ELEM_PAD
        pad_v = const.VERT_PAD
        pad_frame = const.FRAME_PAD

        layout_width = width - 120 if width >= 200 else width
        spacer = layout_width - 124 if layout_width > 124 else 0

        # Audit parameters
        audit_name = self.name
        params = self.parameters

        # Layout elements
        layout_els = [[sg.Col([[sg.Text(audit_name, pad=(0, (pad_v, pad_frame)), font=font_h)]],
                              justification='c', element_justification='c')]]

        # Control elements
        nparam = len(params)
        param_elements = []
        for param in params:
            if nparam > 1:
                pad_text = sg.Text(' ' * 4)
            else:
                pad_text = sg.Text('')

            param_layout = param.layout()
            param_layout.append(pad_text)

            param_elements += param_layout

        layout_els.append(param_elements)

        # Tab elements
        tabgroub_key = self.key_lookup('TG')
        audit_layout = [sg.TabGroup([lo.tab_layout(self.tabs, height=height, width=width)],
                                    pad=(pad_v, (pad_frame, pad_v)),
                                    tab_background_color=inactive_col,
                                    selected_title_color=text_col,
                                    selected_background_color=bg_col,
                                    background_color=default_col, key=tabgroub_key)]
        layout_els.append(audit_layout)

        # Standard elements
        cancel_key = self.key_lookup('Cancel')
        start_key = self.key_lookup('Start')
        fill_key = self.key_lookup('Fill')
        report_key = self.key_lookup('Finalize')
        bttn_layout = [lo.B2('Cancel', key=cancel_key, pad=((0, pad_el), (pad_v, 0)), tooltip='Cancel current action'),
                       lo.B2('Start', key=start_key, pad=((pad_el, 0), (pad_v, 0)), tooltip='Start audit'),
                       sg.Canvas(key=fill_key, size=(spacer, 0), visible=True),
                       lo.B2('Finalize', key=report_key, pad=(0, (pad_v, 0)), disabled=True,
                             tooltip='Finalize audit and generate summary report')]
        layout_els.append(bttn_layout)

        # Pane elements must be columns
        layout = sg.Col(layout_els, key=self.element_key, visible=False)

        return layout

    def reset_attributes(self):
        """
        Reset rule item attributes.
        """
        # Reset Parameter attributes
        for param in self.parameters:
            print('Info: resetting rule parameter element {} to default'.format(param.name))
            param.value = param.value_raw = param.value_obj = None
            try:
                param.value2 = None
            except AttributeError:
                pass

        # Reset Tab attributes
        for i, tab in enumerate(self.tabs):
            tab.reset_dynamic_attributes()

        # Reset Summary attributes
        for summary_item in self.summary.summary_items:
            summary_item.reset_attributes()

    def toggle_parameters(self, window, value='enable'):
        """
        Enable / Disable audit rule parameter elements.
        """
        status = False if value == 'enable' else True

        for parameter in self.parameters:
            element_key = parameter.element_key
            print('Info: parameter {NAME}, rule {RULE}: updated element to "disabled={VAL}"'
                  .format(NAME=parameter.name, RULE=self.name, VAL=status))

            window[element_key].update(disabled=status)


class SummaryPanel:
    """

    """

    def __init__(self, rule_name, sdict):

        self.rule_name = rule_name
        self.element_key = lo.as_key('{} Summary'.format(rule_name))
        self.elements = ['Cancel', 'Back', 'Save', 'Title']

        self.summary_items = []

        try:
            self.title = sdict['Title']
        except KeyError:
            self.title = '{} Summary'.format(rule_name)

        try:
            tables = sdict['DatabaseTables']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}: Summary missing required field "DatabaseTables".') \
                .format(RULE=rule_name)
            win2.popup_error(msg)
            sys.exit(1)

        for table_name in tables:
            si_dict = tables[table_name]

            if 'ReferenceTables' in si_dict:
                self.summary_items.append(SummaryItemSubset(rule_name, table_name, si_dict))
            else:
                self.summary_items.append(SummaryItem(rule_name, table_name, si_dict))

        try:
            self.aliases = sdict['Aliases']
        except KeyError:
            self.aliases = []

    def key_lookup(self, element):
        """
        Lookup element key for input control element.
        """
        if element in self.elements:
            key = lo.as_key('{} Summary {}'.format(self.rule_name, element))
        else:
            print('Warning: rule {RULE}, summary: unable to find GUI element {ELEM} in list of elements'
                  .format(RULE=self.rule_name, ELEM=element))
            key = None

        return (key)

    def layout(self, height=800, width=1200):
        """
        Generate a GUI layout for the Audit Rule Summary.
        """
        # Layout settings
        pad_frame = const.FRAME_PAD
        pad_el = const.ELEM_PAD
        pad_v = const.VERT_PAD

        bg_col = const.ACTION_COL
        default_col = const.DEFAULT_COL
        inactive_col = const.INACTIVE_COL
        text_col = const.TEXT_COL

        font_h = const.HEADER_FONT

        summary_items = self.summary_items

        # Layout elements
        ## Title
        title_key = self.key_lookup('Title')
        layout_els = [[sg.Col([[sg.Text(self.rule_name, pad=(0, (pad_v, pad_frame)), font=font_h)]],
                              justification='c', element_justification='c')]]

        layout_els.append([sg.Text(self.title, key=title_key, pad=(0, (0, pad_v)), font=font_h)])

        ## Main screen
        summ_layout = [sg.TabGroup([lo.tab_layout(summary_items, height=height, width=width, initial_visibility='all')],
                                   pad=(pad_v, (pad_frame, pad_v)), background_color=default_col,
                                   tab_background_color=inactive_col, selected_background_color=bg_col,
                                   selected_title_color=text_col)]

        layout_els.append(summ_layout)

        ## Control buttons
        b1_key = self.key_lookup('Cancel')
        b2_key = self.key_lookup('Back')
        b3_key = self.key_lookup('Save')
        bttn_layout = [lo.B2(_('Cancel'), key=b1_key,
                             tooltip=_('Cancel audit'), pad=((0, pad_el), (pad_v, 0))),
                       lo.B2(_('Back'), key=b2_key,
                             tooltip=_('Back to transactions'), pad=((pad_el, 0), (pad_v, 0))),
                       sg.Text(' ' * 238, pad=(0, (pad_v, 0))),
                       lo.B2(_('Save'), key=b3_key,
                             tooltip=_('Save summary'), pad=(0, (pad_v, 0)))]

        layout_els.append(bttn_layout)

        # Pane elements must be columns
        layout = sg.Col(layout_els, key=self.element_key, visible=False)

        return (layout)

    def format_tables(self, window):
        """
        Format summary item tables for display.
        """
        summary_items = self.summary_items
        for summary_item in summary_items:
            # Modify tables for displaying
            display_df = summary_item.format_display_table()
            data = display_df.values.tolist()

            tbl_key = summary_item.key_lookup('Table')
            window[tbl_key].update(values=data)

    def update_tables(self, rule, *args):
        """
        Update summary item tables with data from tab item dataframes.
        """
        summary_items = self.summary_items
        for summary_item in summary_items:
            summary_item.update_table(rule, *args)

    def reset_tables(self):
        """
        Reset summary item tables.
        """
        summary_items = self.summary_items
        for summary_item in summary_items:
            summary_item.reset_attributes()

    def update_parameters(self, window, rule):
        """
        Update summary title to include audit parameters.
        """
        aliases = self.aliases

        params = rule.parameters

        title_components = re.findall(r'\{(.*?)\}', self.title)
        print('Info: rule {RULE}, Summary: summary title components are {COMPS}'
              .format(RULE=self.rule_name, COMPS=title_components))

        title_params = {}
        for param in params:
            param_col = param.name
            value = param.value_raw

            if param_col in aliases:
                try:
                    final_val = aliases[param_col][value]
                except KeyError:
                    print('Warning: rule {RULE}, Summary: value {VAL} not found in alias list for alias {ALIAS}'
                          .format(RULE=self.rule_name, VAL=value, ALIAS=param_col))
                    final_val = value
            else:
                final_val = value
            print('Info: rule {RULE}, Summary: value for summary parameter {PARAM} is {VAL} with alias {ALIAS}'
                  .format(RULE=self.rule_name, PARAM=param_col, VAL=value, ALIAS=final_val))

            # Check if parameter composes part of title
            if param_col in title_components:
                print('Info: rule {RULE}, Summary: adding parameter value {VAL} to title'
                      .format(RULE=self.rule_name, VAL=final_val))

                if isinstance(final_val, datetime.datetime):
                    title_params[param_col] = final_val.strftime('%Y-%m-%d')
                else:
                    title_params[param_col] = final_val
            else:
                print('Warning: rule {RULE}, Summary: parameter {PARAM} not found in title'
                      .format(RULE=self.rule_name, PARAM=param_col))

            # Update SummaryItem tables with parameter value
            for summary_item in self.summary_items:
                try:
                    summary_item.df[param_col] = final_val
                    print('df with parameters is {}'.format(summary_item.df))
                except KeyError:
                    print('Error: rule {RULE}, summary {SUMM}: parameter column {COL} not found in dataframe'
                          .format(RULE=self.rule_name, SUMM=summary_item.name, COL=param))

        try:
            summ_title = self.title.format(**title_params)
        except KeyError as e:
            print('Error: rule {RULE}, Summary: formatting summary title failed due to {ERR}'
                  .format(RULE=self.rule_name, ERR=e))
            summ_title = self.title

        print('Info: rule {RULE}, Summary: formatted summary title is {TITLE}'
              .format(RULE=self.rule_name, TITLE=summ_title))

        title_key = self.key_lookup('Title')
        window[title_key].update(value=summ_title)

    def update_input_values(self, values):
        """
        Update summary values for an input column.
        """
        summary_items = self.summary_items

        for summary_item in summary_items:
            input_cols = summary_item.input_columns
            for column in input_cols:
                element_key = summary_item.key_lookup(column)
                try:
                    value = values[element_key]
                except KeyError:
                    print('Error: rule {RULE}, summary {NAME}: input {ELEM} not found in list of window elements'
                          .format(RULE=self.rule_name, NAME=summary_item.name, ELEM=element_key))
                    continue

                try:
                    value_fmt = float(value)
                except ValueError:
                    msg = _('Input {VAL} provided to {FIELD} should be a numeric value').format(VAL=value, FIELD=column)
                    win2.popup_error(msg)
                    value_fmt = 0

                try:
                    summary_item.df[column] = value_fmt
                except KeyError:
                    print('Error: rule {RULE}, summary {NAME}: parameter column {COL} not found in dataframe'
                          .format(RULE=self.rule_name, NAME=summary_item.name, COL=column))

    def save_to_database(self, user):
        """
        Save results of an audit to the program database defined in the configuration file.
        """
        summary_items = self.summary_items

        success = []
        for summary_item in summary_items:
            table = summary_item.name
            id_field = summary_item.pkey

            df = summary_item.df
            columns = df.columns.values.tolist()

            try:
                ids = df[id_field].tolist()
            except KeyError:
                print('Error: rule {RULE}, Summary: cannot find IDField {ID} in data frame'
                      .format(RULE=self.rule_name, ID=id_field))
                return False

            for ident in ids:
                try:
                    values = df.iloc[ident].values.tolist()
                except AttributeError:
                    print('Warning: rule {RULE}, Summary: identifier {ID} has more than one row '
                          .format(RULE=self.rule_name, ID=ident))
                    continue
                else:
                    filters = ('{} = ?'.format(id_field), (ident,))
                    existing_df = user.query(table, filter_rules=filters, prog_db=True)

                if existing_df.empty:  # row doesn't exist in database yet
                    success.append(user.insert(table, columns, values))
                else:  # update existing values in table
                    success.append(user.update(table, columns, values, filters))

        return all(success)

    def save_to_file(self, filename):
        """
        Save results of an audit to a file specified by the user.
        """
        summary_items = self.summary_items

        file_type = filename.split('.')[-1]
        if file_type not in ('csv', 'xls', 'xlsx'):
            print('Error: rule {RULE}, Summary: unknown file type {TYPE} provided'
                  .format(RULE=self.rule_name, TYPE=file_type))
            return False

        # Write to output file
        saved: List[bool] = []
        for summary_item in summary_items:
            df = summary_item.df
            if file_type == 'csv':
                try:
                    df.to_csv(filename, mode='a', index=False, header=True)
                except Exception as e:
                    print('Error: rule {RULE}, Summary: saving to file failed due to {ERR}'
                          .format(RULE=self.rule_name, ERR=e))
                else:
                    saved.append(True)
            else:
                with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
                    try:
                        df.to_excel(writer, sheet_name=summary_item.title, index=False, header=True)
                    except Exception as e:
                        print('Error: rule {RULE}, Summary: saving to file failed due to {ERR}'
                              .format(RULE=self.rule_name, ERR=e))
                    else:
                        saved.append(True)

        return all(saved)


class SummaryItem:
    """
    """

    def __init__(self, rule_name, name, sdict):

        self.rule_name = rule_name
        self.name = name
        self.element_key = lo.as_key('{} {} Summary'.format(rule_name, name))
        self.elements = ['Totals', 'Table']

        try:
            self.title = sdict['Title']
        except KeyError:
            self.title = '{} Summary'.format(name)

        try:
            self.pkey = sdict['IDField']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}, summary {NAME}: missing required field "IDField".') \
                .format(RULE=rule_name, NAME=name)
            win2.popup_error(msg)
            sys.exit(1)

        try:
            self.id_format = re.findall(r'\{(.*?)\}', sdict['IDFormat'])
        except KeyError:
            self.id_format = None

        try:
            all_columns = sdict['TableColumns']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}, summary {NAME}: missing required field "TableColumns".') \
                .format(RULE=rule_name, NAME=name)
            win2.popup_error(msg)
            sys.exit(1)
        else:
            self.db_columns = all_columns

        try:
            display_columns = sdict['DisplayColumns']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}, summary {NAME}: missing required parameter "DisplayColumns".') \
                .format(RULE=rule_name, NAME=name)
            win2.popup_error(msg)
            sys.exit(1)
        else:
            self.display_columns = display_columns

        try:
            map_cols = sdict['MappingColumns']
        except KeyError:
            map_cols = {}
        self.mapping_columns = map_cols

        try:
            in_cols = sdict['InputColumns']
        except KeyError:
            in_cols = []

        for item in in_cols:
            self.elements.append(lo.as_key('{} {} Summary {}'.format(rule_name, name, item)))

        self.input_columns = in_cols

        if not map_cols and not in_cols:
            msg = _('Configuration Error: rule {RULE}, summary {NAME}: one or both of parameters "MappingColumns" and '
                    '"InputColumns" are required.').format(RULE=rule_name, NAME=name)
            win2.popup_error(msg)
            sys.exit(1)

        try:
            self.aliases = sdict['Aliases']
        except KeyError:
            self.aliases = []

        # Dynamic attributes
        header = [dm.get_column_from_header(i, all_columns) for i in all_columns]
        self.df = pd.DataFrame(index=[0], columns=header)

    def key_lookup(self, element):
        """
        Lookup element key for input control element.
        """
        if element in self.elements:
            key = lo.as_key('{} Summary {} {}'.format(self.rule_name, self.name, element))
        else:
            print('Warning: rule {RULE}, summary {NAME}: unable to find GUI element {ELEM} in list of elements'
                  .format(RULE=self.rule_name, NAME=self.name, ELEM=element))
            key = None

        return (key)

    def reset_attributes(self):
        """
        Reset Summary values.
        """
        header = [dm.get_column_from_header(i, self.db_columns) for i in self.db_columns]
        self.df = pd.DataFrame(index=[0], columns=header)

    def layout(self, height=800, width=1200):
        """
        GUI layout for the tab item.
        """
        # Window and element size parameters
        bg_col = const.ACTION_COL

        pad_el = const.ELEM_PAD
        pad_frame = const.FRAME_PAD
        font_l = const.LARGE_FONT
        font_m = const.MID_FONT

        display_columns = self.display_columns
        header = list(display_columns.keys())
        ncol = len(header)
        data = dm.create_empty_table(nrow=5, ncol=ncol)
        input_columns = self.input_columns
        scroll = True if len(input_columns) > 5 else False

        inputs_layout = []
        for input_column in input_columns:
            display_name = input_column
            element_key = self.key_lookup(input_column)
            for dcol in display_columns:
                colname = display_columns[dcol]
                print(dcol, colname, input_column)
                if input_column == colname:
                    display_name = colname
                    break

            inputs_layout.append([sg.Text(display_name, size=(20, 1), pad=(pad_el, pad_el), font=font_m,
                                          background_color=bg_col),
                                  sg.Input('', key=element_key, size=(20, 1), pad=(pad_el, pad_el), font=font_m)])

        inputs_layout.append([sg.Text(' ' * 44, background_color=bg_col)])

        tbl_key = self.key_lookup('Table')
        totals_key = self.key_lookup('Totals')
        layout = [[lo.create_table_layout(data, header, tbl_key, bind=False, height=height, width=width)],
                  [sg.Frame(_('Totals'), [[sg.Multiline('', border_width=0, size=(52, 6), font=font_m, key=totals_key,
                                                        disabled=True, background_color=bg_col)]], font=font_l,
                            pad=((pad_frame, 0), (0, pad_frame)), background_color=bg_col, element_justification='l'),
                   sg.Text(' ' * 56, background_color=bg_col),
                   sg.Col(inputs_layout, scrollable=scroll, vertical_scroll_only=True, vertical_alignment='top',
                          background_color=bg_col)
                   ]]

        return layout

    def create_id(self, params):
        """
        """
        param_fields = [i.name for i in params]

        id_parts = []
        for component in self.id_format:
            if len(component) > 1 and set(component).issubset(set('YMD-/ ')):  # component is datestr
                date_fmt = format_date_str(component)
                id_parts.append(datetime.datetime.now().strftime(date_fmt))
            elif component in param_fields:
                param = params[param_fields.index(component)]
                if isinstance(param.value_obj, datetime.datetime):
                    value = param.value_obj.strftime('%Y%m%d')
                else:
                    print('parameter type is {}'.format(type(param.value)))
                    value = param.value
                id_parts.append(value)
            #            elif component.isnumeric():  # component is an incrementing number
            # Get last value from database
            #                value = query_database()
            # Append to id parts list
            #                id_parts.append(value.zfill(len(component)))
            else:  # unknown component type, probably separator
                id_parts.append(component)

        return ''.join(id_parts)

    def format_display_table(self):
        """
        Format dataframe for displaying as a table.
        """
        display_columns = self.display_columns
        display_header = list(display_columns.keys())
        dataframe = self.df

        display_df = pd.DataFrame()

        # Subset dataframe by specified columns to display
        for col_name in display_columns:
            col_rule = display_columns[col_name]

            col_to_add = dm.generate_column_from_rule(dataframe, col_rule)
            display_df[col_name] = col_to_add

        # Map column values to the aliases specified in the configuration
        for alias_col in self.aliases:
            alias_map = self.aliases[alias_col]  # dictionary of mapped values

            if alias_col not in display_header:
                print('Warning: tab {NAME}, rule {RULE}: alias {ALIAS} not found in the list of display columns'
                      .format(NAME=self.name, RULE=self.rule_name, ALIAS=alias_col))
                continue

            print('Info: tab {NAME}, rule {RULE}: applying aliases {MAP} to {COL}'
                  .format(NAME=self.name, RULE=self.rule_name, MAP=alias_map, COL=alias_col))

            try:
                display_df[alias_col].replace(alias_map, inplace=True)
            except KeyError:
                print('Warning: tab {NAME}, rule {RULE}: alias {ALIAS} not found in the list of display columns'
                      .format(NAME=self.name, RULE=self.rule_name, ALIAS=alias_col))
                continue

        return dm.fill_na(display_df)

    def update_table(self, rule, params):
        """
        Populate the summary item dataframe with values from the TabItem tables defined in the MappingColumns parameter.
        """
        operators = set('+-*/')
        is_numeric_dtype = pd.api.types.is_numeric_dtype
        is_string_dtype = pd.api.types.is_string_dtype
        is_datetime_dtype = pd.api.types.is_datetime64_any_dtype
        is_bool_dtype = pd.api.types.is_bool_dtype

        mapping_columns = self.mapping_columns
        df = self.df

        print('Info: rule {RULE}, summary {NAME}: updating table'.format(RULE=self.rule_name, NAME=self.name))

        # Create primary key for row
        id_field = self.pkey
        ident = self.create_id(params)
        df[id_field] = ident

        # Fill in values from mapping column
        for mapping_column in mapping_columns:
            if mapping_column not in self.db_columns:
                print('Error: rule {RULE}, summary {NAME}: mapping column {COL} not in list of table columns'
                      .format(RULE=self.rule_name, NAME=self.name, COL=mapping_column))
                continue

            reference = self.mapping_columns[mapping_column]

            rule_values = []
            for component in dm.parse_operation_string(reference):
                if component in operators:
                    rule_values.append(component)
                    continue

                try:  # component is numeric
                    float(component)
                except ValueError:
                    try:  # component is potentially a data table column
                        ref_table, ref_col = component.split('.')
                    except ValueError:  # unaccepted type
                        print('Error: rule {RULE}, summary {NAME}: unknown data type {COMP} in mapping rule {REF}'
                              .format(RULE=self.rule_name, NAME=self.name, COMP=component, REF=reference))
                        break
                    else:
                        try:
                            tab_df = rule.fetch_tab(ref_table).df
                        except AttributeError:
                            print('Error: rule {RULE}, summary {NAME}: tab item {TAB} not in list of Tabs'
                                  .format(RULE=self.rule_name, NAME=self.name, TAB=ref_table))
                            break

                        header = tab_df.columns.values.tolist()
                        if ref_col in header:
                            col_values = tab_df[ref_col]
                            dtype = tab_df.dtypes[ref_col]
                        elif ref_col.lower() in header:
                            col_values = tab_df[ref_col.lower()]
                            dtype = tab_df.dtypes[ref_col.lower()]
                        else:
                            print('Error: rule {RULE}, summary {NAME}: column {COL} not found in tab {TAB} header'
                                  .format(RULE=self.rule_name, NAME=self.name, COL=ref_col, TAB=ref_table))
                            break

                        if is_numeric_dtype(dtype) or is_bool_dtype(dtype):
                            rule_values.append(col_values.sum())
                        elif is_string_dtype(dtype) or is_datetime_dtype(dtype):
                            rule_values.append(col_values.nunique())
                        else:
                            print('Error: rule {RULE}, summary {NAME}: unknown data type {TYPE} for mapping reference '
                                  '{COMP}'.format(RULE=self.rule_name, NAME=self.name, TYPE=dtype, COMP=component))
                            break
                else:
                    rule_values.append(component)

            try:
                summary_total = eval(' '.join([str(i) for i in rule_values]))
            except Exception as e:
                print('Error: rule {RULE}, summary {NAME}: {ERR}'.format(RULE=self.rule_name, NAME=self.name, ERR=e))
                summary_total = 0

            print('Info: adding {SUMM} to column {COL}'.format(SUMM=summary_total, COL=mapping_column))

            df[mapping_column] = summary_total

        self.df = df


class SummaryItemSubset(SummaryItem):
    """
    """

    def __init__(self, rule_name, name, sdict):
        super().__init__(rule_name, name, sdict)

        self.reference_tables = sdict['ReferenceTables']

        # Dynamic attributes
        header = [dm.get_column_from_header(i, self.db_columns) for i in self.db_columns]
        self.df = pd.DataFrame(columns=header)

    def reset_attributes(self):
        """
        Reset Summary values.
        """
        header = [dm.get_column_from_header(i, self.db_columns) for i in self.db_columns]
        self.df = pd.DataFrame(columns=header)

    def update_table(self, rule, *args):
        """
        Populate the summary item dataframe with rows from the TabItem dataframes specified in the configuration.
        """
        df = self.df
        mapping_columns = self.mapping_columns

        print('Info: rule {RULE}, summary {NAME}: updating table'.format(RULE=self.rule_name, NAME=self.name))

        references = self.reference_tables
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
                if mapping_column not in self.db_columns:
                    print('Error: rule {RULE}, summary {NAME}: mapping column {COL} not in list of table columns'
                          .format(RULE=self.rule_name, NAME=self.name, COL=mapping_column))
                    continue

                mapping_rule = mapping_columns[mapping_column]
                col_to_add = dm.generate_column_from_rule(subset_df, mapping_rule)
                append_df[mapping_column] = col_to_add

            # Append data to summary dataframe
            df = dm.append_to_table(df, append_df)

        self.df = df


class AuditParameter:
    """
    """

    def __init__(self, rule_name, name, cdict):

        self.name = name
        self.rule_name = rule_name
        self.element_key = lo.as_key('{} {}'.format(rule_name, name))
        self.description = cdict['Description']
        self.type = cdict['ElementType']

        # Dynamic attributes
        self.value = self.value_raw = self.value_obj = None

    def set_value(self, values):
        """
        Set the value of the parameter element from user input.

        Arguments:

            values: dictionary of window element values.
        """
        try:
            elem_key = self.element_key
        except KeyError:
            print('Warning: parameter {PARAM}, rule {RULE}: no values set for parameter'
                  .format(PARAM=self.name, RULE=self.rule_name))
            value = ''
        else:
            value = values[elem_key]

        self.value = self.value_raw = self.value_obj = value

    def values_set(self):
        """
        Check whether all values attributes have been set.
        """
        if self.value:
            return True
        else:
            return False

    def filter_statement(self, table=None):
        """
        Generate the filter clause for SQL querying.
        """
        if table:
            db_field = '{}.{}'.format(table, self.name)
        else:
            db_field = self.name

        value = self.value
        if value:
            statement = ('{}= ?'.format(db_field), (value,))
        else:
            statement = None

        return statement


class AuditParameterCombo(AuditParameter):
    """
    """

    def __init__(self, rule_name, name, cdict):
        super().__init__(rule_name, name, cdict)
        try:
            self.combo_values = cdict['Values']
        except KeyError:
            print('Configuration Warning: parameter {PM}, rule {RULE}: values required for parameter type "dropdown"'
                  .format(PM=name, RULE=rule_name))
            self.combo_values = []

    def layout(self, padding: int = 8):
        """
        Create a layout for rule parameter element 'dropdown'.
        """
        pad_el = const.ELEM_PAD
        pad_v = const.VERT_PAD
        font = const.MID_FONT

        key = self.element_key
        desc = '{}:'.format(self.description)
        values = self.combo_values

        width = max([len(i) for i in values]) + padding

        layout = [sg.Text(desc, font=font, pad=((0, pad_el), (0, pad_v))),
                  sg.Combo(values, font=font, key=key, enable_events=True,
                           size=(width, 1), pad=(0, (0, pad_v)))]

        return (layout)


class AuditParameterDate(AuditParameter):
    """
    """

    def __init__(self, rule_name, name, cdict):
        super().__init__(rule_name, name, cdict)
        try:
            self.format = format_date_str(cdict['DateFormat'])
        except KeyError:
            print('Warning: parameter {PARAM}, rule {RULE}: no date format specified ... defaulting to YYYY-MM-DD'
                  .format(PARAM=name, RULE=rule_name))
            self.format = format_date_str("YYYY-MM-DD")

    def layout(self):
        """
        Layout for the rule parameter element 'date'.
        """
        pad_el = const.ELEM_PAD
        pad_v = const.VERT_PAD
        date_ico = const.CALENDAR_ICON
        font = const.MID_FONT

        desc = '{}:'.format(self.description)

        key = self.element_key
        layout = [sg.Text(desc, font=font, pad=((0, pad_el), (0, pad_v))),
                  sg.Input('', key=key, size=(16, 1), enable_events=True,
                           pad=((0, pad_el), (0, pad_v)), font=font,
                           tooltip=_('Input date as YYYY-MM-DD or use the calendar button to select the date')),
                  sg.CalendarButton('', format='%Y-%m-%d', image_data=date_ico,
                                    border_width=0, size=(2, 1), pad=(0, (0, pad_v)), font=font,
                                    tooltip=_('Select date from calendar menu'))]

        return (layout)

    def set_value(self, values):
        """
        Set the value of the parameter element from user input.

        Arguments:

            values: dictionary of window element values.
        """
        dparse = dateutil.parser.parse

        elem_key = self.element_key

        try:
            value_raw: str = values[elem_key]
        except KeyError:
            print('Warning: parameter {PARAM}, rule {RULE}: no values set for parameter'
                  .format(PARAM=self.name, RULE=self.rule_name))
            value_fmt = ''
            value_raw = ''
        else:
            try:
                date = dparse(value_raw, yearfirst=True)
            except ValueError:
                value_fmt = ''
                value_raw = ''
                date = ''
            else:
                try:
                    value_fmt: str = date.strftime(self.format)
                except ValueError:
                    print('Configuration Error: invalid format string {}'.format(self.format))
                    value_fmt = None
                    date = ''

        self.value = value_fmt
        self.value_raw = value_raw
        self.value_obj = date

    def values_set(self):
        """
        Check whether all values attributes have been set with correct 
        formatting.
        """
        value = self.value_raw

        input_date = value.replace('-', '')
        if input_date and len(input_date) == 8:
            return (True)
        else:
            return (False)


class AuditParameterDateRange(AuditParameterDate):
    """
    Layout for the rule parameter element 'date_range'.
    """

    def __init__(self, rule_name, name, cdict):
        super().__init__(rule_name, name, cdict)
        self.element_key2 = lo.as_key('{} {} 2'.format(rule_name, name))
        self.value2 = None

    def layout(self):
        """
        Layout for the rule parameter element 'date' and 'date_range'.
        """
        pad_el = const.ELEM_PAD
        pad_v = const.VERT_PAD
        pad_h = const.HORZ_PAD
        date_ico = const.CALENDAR_ICON
        font = const.MID_FONT

        desc = self.description

        desc_from = '{} From:'.format(desc)
        desc_to = '{} To:'.format(desc)
        key_from = self.element_key
        key_to = self.element_key2

        layout = [sg.Text(desc_from, font=font, pad=((0, pad_el), (0, pad_v))),
                  sg.Input('', key=key_from, size=(16, 1), enable_events=True, pad=((0, pad_el), (0, pad_v)), font=font,
                           tooltip=_('Input date as YYYY-MM-DD or use the calendar button to select the date')),
                  sg.CalendarButton('', format='%Y-%m-%d', image_data=date_ico, border_width=0, size=(2, 1),
                                    pad=(0, (0, pad_v)), tooltip=_('Select date from calendar menu')),
                  sg.Text(desc_to, font=font, pad=((pad_h, pad_el), (0, pad_v))),
                  sg.Input('', key=key_to, size=(16, 1), enable_events=True, pad=((0, pad_el), (0, pad_v)),
                           tooltip=_('Input date as YYYY-MM-DD or use the calendar button to select the date')),
                  sg.CalendarButton('', format='%Y-%m-%d', image_data=date_ico, border_width=0, size=(2, 1),
                                    pad=(0, (0, pad_v)), tooltip=_('Select date from calendar menu'))]

        return (layout)

    def filter_statement(self, table=None):
        """
        Generate the filter clause for SQL querying.
        """
        if table:
            db_field = '{}.{}'.format(table, self.name)
        else:
            db_field = self.name

        params = (self.value, self.value2)
        statement = ('{} BETWEEN ? AND ?'.format(db_field), params)

        return (statement)

    def set_value(self, values):
        """
        Set the value of the parameter element from user input.

        Arguments:

            values: dictionary of window element values.
        """
        elem_key = self.element_key
        elem_key2 = self.element_key2
        self.value = values[elem_key]

        self.value2 = values[elem_key2]

    def values_set(self):
        """
        Check whether all values attributes have been set.
        """
        if self.value and self.value2:
            return (True)
        else:
            return (False)


def format_date_element(date_str):
    """
    Forces user input to date element to be in ISO format.
    """
    buff = []
    for index, char in enumerate(date_str):
        if index == 3:
            if len(date_str) != 4:
                buff.append('{}-'.format(char))
            else:
                buff.append(char)
        elif index == 5:
            if len(date_str) != 6:
                buff.append('{}-'.format(char))
            else:
                buff.append(char)
        else:
            buff.append(char)

    return (''.join(buff))


def format_date_str(date_str):
    """
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
                    print('Warning: unknown component {} provided to date string {}.'.format(component, date_str))
                    raise

            strfmt.append(char)
            buff = []

        last_char = char

    try:  # format final component remaining in buffer
        strfmt.append(date_fmts[''.join(buff)])
    except KeyError:
        print('Warning: unsupported characters {} found in date string {}'.format(''.join(buff), date_str))
        raise

    return ''.join(strfmt)
