"""
REM configuration classes and functions. Includes audit rules, audit objects, and rule parameters.
"""
import datetime
from typing import List
import dateutil.parser
import numpy as np
import pandas as pd
import PySimpleGUI as sg
import re
import REM.data_manipulation as dm
from REM.config import settings
import REM.layouts as lo
import REM.program_constants as const
import REM.secondary as win2
import sys


class AuditRules:
    """
    Class to store and manage program audit_rule configuration settings.

    Arguments:

        cnfg: parsed YAML file.

    Attributes:

        rules (list): List of AuditRule objects.
    """

    def __init__(self, cnfg):

        # Audit parameters
        audit_rules = cnfg['audit_rules']
        self.rules = []
        for audit_rule in audit_rules:
            self.rules.append(AuditRule(audit_rule, audit_rules[audit_rule]))

    def print_rules(self):
        """
        Return name of all audit rules defined in configuration file.
        """
        return [i.name for i in self.rules]

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

        return rule


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

    def resize_elements(self, window, win_size: tuple = None):
        """
        Resize Audit Rule GUI elements based on window size
        """
        if win_size:
            width, height = win_size
        else:
            width, height = (const.WIN_WIDTH, const.WIN_HEIGHT)

        # Resize space between action buttons
        # For every five-pixel increase in window size, increase tab size by one
        layout_pad = 120
        win_diff = width - const.WIN_WIDTH
        layout_pad = layout_pad + (win_diff / 5)

        layout_width = width - layout_pad if layout_pad > 0 else width
        spacer = layout_width - 124 if layout_width > 124 else 0

        fill_key = self.key_lookup('Fill')
        window[fill_key].set_size((spacer, None))

        # Resize tab elements
        tabs = self.tabs
        for tab in tabs:
            tab.resize_elements(window, win_size)

        # Resize summary elements
        summary = self.summary
        summary_fill_key = summary.key_lookup('Fill')
        window[summary_fill_key].set_size((spacer, None))
        for summary_item in summary.summary_items:
            summary_item.resize_elements(window, win_size)

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
            print('Warning: rule {NAME}, parameter {PARAM}: the "by_key" and "by_type" arguments are mutually '
                  'exclusive. Defaulting to "by_key".'.format(NAME=self.name, PARAM=name))
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

    def layout(self, win_size: tuple = None):
        """
        Generate a GUI layout for the audit rule.
        """
        if win_size:
            width, height = win_size
        else:
            width, height = (const.WIN_WIDTH, const.WIN_HEIGHT)

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
        audit_layout = [sg.TabGroup([lo.tab_layout(self.tabs, win_size=win_size)],
                                    key= tabgroub_key, pad=(pad_v, (pad_frame, pad_v)),
                                    tab_background_color=inactive_col, selected_title_color=text_col,
                                    selected_background_color=bg_col, background_color=default_col)]
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
            print('Info: rule {RULE}, parameter {NAME}: updated element to "disabled={VAL}"'
                  .format(NAME=parameter.name, RULE=self.name, VAL=status))

            window[element_key].update(disabled=status)


class SummaryPanel:
    """

    """

    def __init__(self, rule_name, sdict):

        self.rule_name = rule_name
        self.element_key = lo.as_key('{} Summary'.format(rule_name))
        self.elements = ['Cancel', 'Back', 'Save', 'Title', 'Fill', 'TG']

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
            try:
                summ_type = si_dict['Type']
            except KeyError:
                msg = _('Configuration Error: rule {RULE}, summary {NAME}:  missing required field "Type".') \
                    .format(RULE=rule_name, NAME=table_name)
                win2.popup_error(msg)
                sys.exit(1)

            if summ_type == 'Subset':
                self.summary_items.append(SummaryItemSubset(rule_name, table_name, si_dict))
            elif summ_type == 'Add':
                self.summary_items.append(SummaryItemAdd(rule_name, table_name, si_dict))
            else:
                msg = _('Configuration Error: rule {RULE}, summary {NAME}:  unknown type "{TYPE}" provided to the '
                        'Types parameter.').format(RULE=rule_name, NAME=table_name, TYPE=summ_type)
                win2.popup_error(msg)
                sys.exit(1)

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
            print('Warning: rule {RULE}, Summary: unable to find GUI element {ELEM} in list of elements'
                  .format(RULE=self.rule_name, ELEM=element))
            key = None

        return key

    def fetch_tab(self, name, by_key: bool = False):
        """
        Fetch a select summary item by the summary item name or element key.
        """
        if not by_key:
            names = [i.name for i in self.summary_items]
        else:
            names = [i.element_key for i in self.summary_items]

        try:
            index = names.index(name)
        except ValueError:
            print('Error: rule {RULE}, Summary: summary item {TAB} not in list of summary items'
                  .format(RULE=self.rule_name, TAB=name))
            tab_item = None
        else:
            tab_item = self.summary_items[index]

        return tab_item

    def layout(self, win_size: tuple = None):
        """
        Generate a GUI layout for the Audit Rule Summary.
        """
        if win_size:
            width, height = win_size
        else:
            width, height = (const.WIN_WIDTH, const.WIN_HEIGHT)

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

        layout_width = width - 120 if width >= 200 else width
        spacer = layout_width - 124 if layout_width > 124 else 0

        # Layout elements
        ## Title
        title_key = self.key_lookup('Title')
        layout_els = [[sg.Col([[sg.Text(self.rule_name, pad=(0, (pad_v, pad_frame)), font=font_h)]],
                              justification='c', element_justification='c')]]

        layout_els.append([sg.Text(self.title, key=title_key, pad=(0, (0, pad_v)), font=font_h)])

        ## Main screen
        tg_key = self.key_lookup('TG')
        summ_layout = [sg.TabGroup([lo.tab_layout(summary_items, win_size=win_size, initial_visibility='all')],
                                   key=tg_key, pad=(pad_v, (pad_frame, pad_v)), background_color=default_col,
                                   tab_background_color=inactive_col, selected_background_color=bg_col,
                                   selected_title_color=text_col)]

        layout_els.append(summ_layout)

        ## Control buttons
        b1_key = self.key_lookup('Cancel')
        b2_key = self.key_lookup('Back')
        b3_key = self.key_lookup('Save')
        fill_key = self.key_lookup('Fill')
        bttn_layout = [lo.B2(_('Cancel'), key=b1_key,
                             tooltip=_('Cancel audit'), pad=((0, pad_el), (pad_v, 0))),
                       lo.B2(_('Back'), key=b2_key,
                             tooltip=_('Back to transactions'), pad=((pad_el, 0), (pad_v, 0))),
                       sg.Canvas(key=fill_key, size=(spacer, 0), visible=True),
                       lo.B2(_('Save'), key=b3_key,
                             tooltip=_('Save summary'), pad=(0, (pad_v, 0)))]

        layout_els.append(bttn_layout)

        # Pane elements must be columns
        layout = sg.Col(layout_els, key=self.element_key, visible=False)

        return layout

    def format_tables(self, window):
        """
        Format summary item tables for display. Also update sum and remainder elements.
        """
        default_col = const.ACTION_COL
        greater_col = const.PASS_COL
        lesser_col = const.FAIL_COL

        summary_items = self.summary_items
        for summary_item in summary_items:
            # Modify records tables for displaying
            print('Info: rule {RULE}, summary {NAME}: formatting records table for displaying'
                  .format(RULE=self.rule_name, NAME=summary_item.name))
            print(summary_item.df)
            display_df = summary_item.format_display_table(table='records')
            data = display_df.values.tolist()

            tbl_key = summary_item.key_lookup('Table')
            window[tbl_key].update(values=data)

            # Modify records tables for displaying
            print('Info: rule {RULE}, summary {NAME}: formatting totals table for displaying'
                  .format(RULE=self.rule_name, NAME=summary_item.name))
            print(summary_item.totals_df)
            totals_display_df = summary_item.format_display_table(table='totals')
            totals_data = totals_display_df.values.tolist()

            totals_key = summary_item.key_lookup('Totals')
            window[totals_key].update(values=totals_data)

            # Update summary totals elements
            total_key = summary_item.key_lookup('Total')
            tally_rule = summary_item.totals['TallyRule']

            if tally_rule:
                totals_sum = dm.evaluate_rule(summary_item.totals_df.iloc[[0]], tally_rule, as_list=False).sum()
            else:
                totals_sum = summary_item.totals_df.iloc[0].sum()

            window[total_key].update(value='{:,.2f}'.format(totals_sum))

            sum_column = summary_item.records['SumColumn']
            records_sum = summary_item.df[sum_column].sum()
            remainder = totals_sum - records_sum
            if remainder > 0:
                bg_color = greater_col
            elif remainder < 0:
                bg_color = lesser_col
            else:
                bg_color = default_col

            remain_key = summary_item.key_lookup('Remainder')
            window[remain_key].update(value='{:,.2f}'.format(remainder), background_color=bg_color)

    def update_tables(self, rule):
        """
        Update summary item tables with data from tab item dataframes.
        """
        summary_items = self.summary_items
        for summary_item in summary_items:
            summary_item.update_table(rule)

    def reset_attributes(self):
        """
        Reset summary item attributes.
        """
        summary_items = self.summary_items
        for summary_item in summary_items:
            # Reset summary item attributes
            summary_item.reset_attributes()

    def resize_elements(self, window, win_size: tuple = None):
        """
        Resize summary items tables
        """
        win_size = win_size if win_size else window.size

        summary_items = self.summary_items
        for summary_item in summary_items:
            # Reset summary item attributes
            summary_item.resize_elements(window, win_size=win_size)

    def update_totals(self, rule):
        """
        Populate totals table with audit tab summary totals.
        """
        operators = set('+-*/')

        summary_items = self.summary_items
        for summary_item in summary_items:
            name = summary_item.name
            totals = summary_item.totals
            df = summary_item.totals_df

            db_columns = totals['TableColumns']
            mapping_columns = totals['MappingColumns']
            edit_columns = totals['EditColumns']
            for column in db_columns:
                try:
                    reference = mapping_columns[column]
                except KeyError:
                    if column not in edit_columns:
                        print('Error: rule {RULE}, summary {NAME}: column {COL} not found in either mapping columns or '
                              'edit columns'.format(RULE=self.rule_name, NAME=name, COL=column))
                    df.at[0, column] = 0
                    df[column] = pd.to_numeric(df[column], downcast='float')
                    continue

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
                            if component in edit_columns:
                                rule_values.append(0)
                                continue
                            else:
                                print('Error: rule {RULE}, summary {NAME}: unknown data type {COMP} in rule {REF}'
                                      .format(RULE=self.rule_name, NAME=name, COMP=component, REF=reference))
                                rule_values.append(0)
                                continue
                        else:
                            try:
                                tab_summary = rule.fetch_tab(ref_table).summary_rules
                            except AttributeError:
                                print('Error: rule {RULE}, summary {NAME}: tab item {TAB} not in list of Tabs'
                                      .format(RULE=self.rule_name, NAME=name, TAB=ref_table))
                                rule_values.append(0)
                                continue

                            if ref_col in tab_summary:
                                try:
                                    rule_values.append(tab_summary[ref_col]['Total'])
                                except KeyError:
                                    rule_values.append(0)
                            else:
                                print('Error: rule {RULE}, summary {NAME}: column {COL} not found in tab {TAB} summary'
                                      .format(RULE=self.rule_name, NAME=name, COL=ref_col, TAB=ref_table))
                                rule_values.append(0)

                    else:
                        rule_values.append(component)

                try:
                    summary_total = eval(' '.join([str(i) for i in rule_values]))
                except Exception as e:
                    print('Error: rule {RULE}, summary {NAME}: {ERR}'
                          .format(RULE=self.rule_name, NAME=summary_item.name, ERR=e))
                    summary_total = 0

                print('Info: rule {RULE}, summary {NAME}: adding {SUMM} to column {COL}'
                      .format(RULE=self.rule_name, NAME=name, SUMM=summary_total, COL=column))

                df.at[0, column] = summary_total
                df[column] = pd.to_numeric(df[column], downcast='float')

            summary_item.totals_df = df

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
            value = param.value_obj

            print('Info: rule {RULE}, Summary: value for summary parameter {PARAM} is {VAL}'
                  .format(RULE=self.rule_name, PARAM=param_col, VAL=value))

            # Check if parameter composes part of title
            if param_col in title_components:
                if param_col in aliases:
                    try:
                        final_val = aliases[param_col][value]
                    except KeyError:
                        print('Warning: rule {RULE}, Summary: value {VAL} not found in alias list for alias {ALIAS}'
                              .format(RULE=self.rule_name, VAL=value, ALIAS=param_col))
                        final_val = value
                else:
                    final_val = value

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
                # Update table value
                try:
                    summary_item.df[param_col] = value
                except KeyError:
                    print('Error: rule {RULE}, summary {SUMM}: parameter column {COL} not found in dataframe'
                          .format(RULE=self.rule_name, SUMM=summary_item.name, COL=param))

                # Update identifier components
                summary_item.update_id_components(params)

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

    def save_to_database(self, user):
        """
        Save results of an audit to the program database defined in the configuration file.
        """
        summary_items = self.summary_items

        success = []
        for summary_item in summary_items:
            table = summary_item.name
            id_field = summary_item.records['IDColumn']

            df = summary_item.df
            columns = df.columns.values.tolist()

            try:
                ids = df[id_field].tolist()
            except KeyError:
                print('Error: rule {RULE}, Summary: cannot find IDColumn {ID} in data frame'
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
                else:  # update existing values in table (requires admin privileges)
                    if user.admin:
                        success.append(user.update(table, columns, values, filters))
                    else:
                        msg = 'Transaction {} already exists in the summary database'.format(ident)
                        win2.popup_notice(msg)
                        success.append(False)

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
        self.elements = ['Totals', 'Table', 'Fill', 'Add', 'Total', 'Remainder']
        self.type = None

        try:
            self.title = sdict['Title']
        except KeyError:
            self.title = '{} Summary'.format(name)

        try:
            self.id_format = re.findall(r'\{(.*?)\}', sdict['IDFormat'])
        except KeyError:
            self.id_format = []

        try:
            records = sdict['Records']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}, summary {NAME}: missing required parameter "Records".') \
                .format(RULE=rule_name, NAME=name)
            win2.popup_error(msg)
            sys.exit(1)
        msg = _('Configuration Error: rule {RULE}, summary {NAME}: missing required field "{FIELD}" '
                'in the "Records" parameter.')
        if 'IDColumn' not in records:
            win2.popup_error(msg.format(RULE=rule_name, NAME=name, FEILD='IDColumn'))
            sys.exit(1)
        if 'TableColumns' not in records:
            win2.popup_error(msg.format(RULE=rule_name, NAME=name, FEILD='TableColumns'))
            sys.exit(1)
        if 'SumColumn' not in records:
            win2.popup_error(msg.format(RULE=rule_name, NAME=name, FEILD='SumColumn'))
            sys.exit(1)
        if 'DisplayColumns' not in records:
            win2.popup_error(msg.format(RULE=rule_name, NAME=name, FEILD='DisplayColumns'))
            sys.exit(1)
        if 'MappingColumns' not in records:
            records['MappingColumns'] = {}
        if 'ReferenceTables' not in records:
            records['ReferenceTables'] = {}
        if 'EditColumns' not in records:
            records['EditColumns'] = []

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
        if 'DisplayColumns' not in totals:
            win2.popup_error(msg.format(RULE=rule_name, NAME=name, FEILD='DisplayColumns'))
            sys.exit(1)
        if 'MappingColumns' not in totals:
            totals['MappingColumns'] = {}
        if 'EditColumns' not in totals:
            totals['EditColumns'] = []
        if 'TallyRule' not in totals:
            totals['TallyRule'] = None

        self.totals = totals

        try:
            self.aliases = sdict['Aliases']
        except KeyError:
            self.aliases = []

        # Dynamic attributes
        header = [dm.get_column_from_header(i, self.records['TableColumns']) for i in self.records['TableColumns']]
        self.df = pd.DataFrame(index=[0], columns=header)

        totals_header = [dm.get_column_from_header(i, self.totals["TableColumns"])
                         for i in self.totals["TableColumns"]]
        self.totals_df = pd.DataFrame(index=[0], columns=totals_header)

        self.ids = []
        self.id_components = []

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

        return key

    def update_id_components(self, parameters):
        """
        """
        id_format = self.id_format
        self.id_components = []

        last_index = 0
        print('Info: tab {NAME}, rule {RULE}: ID is formatted as {FORMAT}'
              .format(NAME=self.name, RULE=self.rule_name, FORMAT=id_format))
        param_fields = [i.name for i in parameters]
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

            self.id_components.append(part_tup)

            last_index += component_len

        print('Info: tab {NAME}, rule {RULE}: ID updated with components {COMP}'
              .format(NAME=self.name, RULE=self.rule_name, COMP=self.id_components))

    def get_id_component(self, identifier, component):
        """
        Extract the specified component values from the provided identifier.
        """
        comp_value = ''
        for id_component in self.id_components:
            comp_name, comp_value, comp_index = id_component

            if component == comp_name:
                try:
                    comp_value = identifier[comp_index[0]: comp_index[1]]
                except IndexError:
                    print('Warning: ID component {COMP} cannot be found in identifier {IDENT}'
                          .format(COMP=component, IDENT=identifier))

                break

        return comp_value

    def resize_elements(self, window, win_size: tuple = None):
        """
        Reset Table Columns widths to default when resized.
        """
        if win_size:
            width, height = win_size
        else:
            width, height = (const.WIN_WIDTH, const.WIN_HEIGHT)

        tbl_key = self.key_lookup('Table')
        totals_key = self.key_lookup('Totals')
        fill_key = self.key_lookup('Fill')
        element_key = self.element_key

        # Reset table size
        # For every five-pixel increase in window size, increase tab size by one
        tab_pad = 120
        win_diff = width - const.WIN_WIDTH
        tab_pad = tab_pad + (win_diff / 5)

        tab_width = width - tab_pad if tab_pad > 0 else width
        height = height * 0.5
        nrows = int(height / 60)

        window.bind("<Configure>", window[element_key].Widget.config(width=tab_width))

        fill = 278
        # for every ten pixel increase in window size, increase fill size by one
        tab_fill = tab_width - fill if tab_width > fill else 0
        window[fill_key].set_size((tab_fill, None))

        # Reset table column sizes
        record_columns = self.records['DisplayColumns']
        header = list(record_columns.keys())
        lengths = dm.calc_column_widths(header, width=tab_width, pixels=True)
        for col_index, col_name in enumerate(header):
            col_width = lengths[col_index]
            window[tbl_key].Widget.column(col_name, width=col_width)

        window[tbl_key].expand((True, True))
        window[tbl_key].table_frame.pack(expand=True, fill='both')

        totals_columns = self.totals['DisplayColumns']
        totals_header = list(totals_columns.keys())
        lengths = dm.calc_column_widths(totals_header, width=tab_width, pixels=True)
        for col_index, col_name in enumerate(totals_header):
            col_width = lengths[col_index]
            window[totals_key].Widget.column(col_name, width=col_width)

        window[totals_key].expand((True, True))
        window[totals_key].table_frame.pack(expand=True, fill='both')

        window.refresh()

        window[tbl_key].update(num_rows=nrows)

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
        font = const.MID_FONT
        font_b = const.BOLD_MID_FONT
        pad_frame = const.FRAME_PAD
        pad_el = const.ELEM_PAD

        tbl_pad = (pad_frame, (pad_el, pad_frame))

        header = list(display_columns.keys())
        totals_header = list(totals_columns.keys())

        totals_data = dm.create_empty_table(nrow=1, ncol=len(totals_header))
        data = dm.create_empty_table(nrow=5, ncol=len(header))

        # Set Tab size
        tab_pad = 120
        win_diff = width - const.WIN_WIDTH
        tab_pad = tab_pad + (win_diff / 5)
        tab_width = width - tab_pad if tab_pad > 0 else width

        fill = 278
        tab_fill = tab_width - fill if tab_width > fill else 0
        disabled = False if self.type == 'Add' else True

        tbl_key = self.key_lookup('Table')
        totals_key = self.key_lookup('Totals')
        fill_key = self.key_lookup('Fill')
        add_key = self.key_lookup('Add')
        remain_key = self.key_lookup('Remainder')
        total_key = self.key_lookup('Total')
        layout = [[sg.Col([[sg.Text('Totals', pad=(0, (pad_frame, pad_el)), font=font_b, background_color=bg_col)]],
                          justification='c', background_color=bg_col)],
                  [lo.create_table_layout(totals_data, totals_header, totals_key, bind=True, height=height,
                                          width=width, nrow=1, pad=tbl_pad)],
                  [sg.Text('Total:', size=(10, 1), pad=((pad_frame, pad_el), (0, pad_frame)), font=font_b,
                           background_color=bg_col, justification='r'),
                   sg.Text('', key=total_key, size=(14, 1), pad=(0, (0, pad_frame)), font=font,
                           background_color=bg_col, justification='r', relief='sunken')],
                  [sg.Canvas(size=(0, 20), visible=True, background_color=bg_col)],
                  [sg.Col([[sg.Text('Records', pad=(0, (0, pad_el)), background_color=bg_col, font=font_b)]],
                          justification='c', background_color=bg_col)],
                  [lo.create_table_layout(data, header, tbl_key, bind=True, height=height, width=width, pad=tbl_pad)],
                  [sg.Text('Remainder:', size=(10, 1), pad=((pad_frame, pad_el), (0, pad_frame)), font=font_b,
                           background_color=bg_col, justification='r'),
                   sg.Text('', key=remain_key, size=(14, 1), pad=(0, (0, pad_frame)), font=font,
                           background_color=bg_col, justification='r', relief='sunken'),
                   sg.Canvas(key=fill_key, size=(tab_fill, 0), visible=True, background_color=bg_col),
                   lo.B2('Add', key=add_key, pad=((0, pad_frame), (0, pad_frame)), disabled=disabled)],
                  [sg.Canvas(size=(0, 20), visible=True, background_color=bg_col)]]

        return layout

    def add_row(self, rule, win_size: tuple = None):
        """
        Add row to records table
        """
        df = self.df.copy()
        edit_columns = self.records['EditColumns']
        display_columns = self.records['DisplayColumns']
        id_column = self.records['IDColumn']

        # Initialize new empty row
        nrow = df.shape[0]
        new_index = nrow - 1 + 1  # first index starts at 0

        df = df.append(pd.Series(), ignore_index=True)

        # Create an identifier for the new row
        ident = self.create_id(rule)
        df.at[new_index, id_column] = ident
        self.ids.append(ident)

        # Update the amounts column
        sum_column = self.records['SumColumn']
        df.at[new_index, sum_column] = 0.0

        # Fill in non-editable columns
        df.fillna(inplace=True, method='ffill')

        # Display the add row window
        display_map = {display_columns[i]: i for i in display_columns}
        df = win2.add_record(df, new_index, edit_columns, header_map=display_map, win_size=win_size)

        # Remove identifier from list of ids if creation cancelled
        if nrow == df.shape[0]:
            self.ids.pop()

        self.df = df

    def edit_row(self, index, element_key, win_size: tuple = None):
        """
        Edit row using modify record window
        """
        if element_key == self.key_lookup('Table'):
            parameter = self.records
            df = self.df.copy()
            table = 'records'
            id_column = parameter['IDColumn']
        elif element_key == self.key_lookup('Totals'):
            parameter = self.totals
            df = self.totals_df.copy()
            table = 'totals'
            id_column = None
        else:
            raise KeyError('element key {} does not correspond to either the Totals or Records tables'
                           .format(element_key))

        display_columns = parameter['DisplayColumns']
        edit_columns = parameter['EditColumns']

        display_map = {display_columns[i]: i for i in display_columns}
        df = win2.edit_record(df, index, edit_columns, header_map=display_map, win_size=win_size)

        # Remove identifier from list of ids if record deleted
        if id_column:
            try:
                df.at[index, id_column]
            except KeyError:
                del self.ids[index]

        if table == 'records':
            self.df = df
        elif table == 'totals':
            self.totals_df = df

    def format_display_table(self, table: str = 'records', date_fmt: str = '%d-%m-%Y'):
        """
        Format dataframe for displaying as a table.
        """
        relativedelta = dateutil.relativedelta.relativedelta
        strptime = datetime.datetime.strptime
        is_float_dtype = pd.api.types.is_float_dtype
        is_datetime_dtype = pd.api.types.is_datetime64_any_dtype

        if table == 'records':
            dataframe = self.df
            display_columns = self.records['DisplayColumns']
            display_header = list(display_columns.keys())
        else:
            dataframe = self.totals_df
            display_columns = self.totals['DisplayColumns']
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

        return display_df


class SummaryItemAdd(SummaryItem):
    """
    """

    def __init__(self, rule_name, name, sdict):
        super().__init__(rule_name, name, sdict)
        self.type = 'Add'

        # Dynamic attributes
        header = [dm.get_column_from_header(i, self.records['TableColumns']) for i in self.records['TableColumns']]
        self.df = pd.DataFrame(index=[0], columns=header)

        totals_header = [dm.get_column_from_header(i, self.totals["TableColumns"])
                         for i in self.totals["TableColumns"]]
        self.totals_df = pd.DataFrame(index=[0], columns=totals_header)

    def reset_attributes(self):
        """
        Reset Summary values.
        """
        header = [dm.get_column_from_header(i, self.records['TableColumns']) for i in self.records['TableColumns']]
        self.df = pd.DataFrame(index=[0], columns=header)

        totals_header = [dm.get_column_from_header(i, self.totals["TableColumns"])
                         for i in self.totals["TableColumns"]]
        self.totals_df = pd.DataFrame(index=[0], columns=totals_header)

        self.ids = []
        self.id_components = []

    def create_id(self, rule):
        """
        """
        param_fields = [i.name for i in rule.parameters]

        id_parts = []
        for component in self.id_format:
            if len(component) > 1 and set(component).issubset(set('YMD-/ ')):  # component is datestr
                date_fmt = settings.format_date_str(date_str=component)

                date_param = rule.fetch_parameter('date', by_type=True)
                if date_param:
                    date = settings.apply_date_offset(date_param.value_obj)
                else:
                    date = datetime.datetime.now()

                id_parts.append(date.strftime(date_fmt))
            elif component in param_fields:
                param = rule.fetch_parameter(component)
                if isinstance(param.value_obj, datetime.datetime):
                    value = param.value_obj.strftime('%Y%m%d')
                else:
                    value = param.value
                id_parts.append(value)
            elif component.isnumeric():  # component is an incrementing number
                # Increment last ID by one
                if self.ids:  # search summary ids for most recent id
                    last_id = self.ids[-1]
                    last_var = int(self.get_id_component(last_id, 'variable'))
                else:  # search database for most recent id
                    last_var = 0

                current_var = str(last_var + 1)

                # Append to id parts list
                id_parts.append(current_var.zfill(len(component)))
            else:  # unknown component type, probably separator or constant
                id_parts.append(component)

        return ''.join(id_parts)

    def update_table(self, rule):
        """
        Populate the summary item dataframe with added records.
        """
        df = self.df

        print('Info: rule {RULE}, summary {NAME}: updating table'.format(RULE=self.rule_name, NAME=self.name))

        # Create primary key for row
        id_field = self.records['IDColumn']
        ident = self.create_id(rule)
        df[id_field] = ident
        self.ids.append(ident)

        # Update amount column
        sum_column = self.records['SumColumn']
        df[sum_column] = pd.to_numeric(df[sum_column], downcast='float')

        tally_rule = self.totals['TallyRule']
        if tally_rule:
            totals_sum = dm.evaluate_rule(self.totals_df.iloc[[0]], tally_rule, as_list=False).sum()
        else:
            totals_sum = self.totals_df.iloc[0].sum()

        df.at[0, sum_column] = totals_sum

        self.df = df


class SummaryItemSubset(SummaryItem):
    """
    """

    def __init__(self, rule_name, name, sdict):
        super().__init__(rule_name, name, sdict)
        self.type = 'Subset'

        # Dynamic attributes
        header = [dm.get_column_from_header(i, self.records['TableColumns']) for i in self.records['TableColumns']]
        self.df = pd.DataFrame(columns=header)

        totals_header = [dm.get_column_from_header(i, self.totals["TableColumns"])
                         for i in self.totals["TableColumns"]]
        self.totals_df = pd.DataFrame(index=[0], columns=totals_header)

    def reset_attributes(self):
        """
        Reset Summary values.
        """
        header = [dm.get_column_from_header(i, self.records['TableColumns']) for i in self.records['TableColumns']]
        self.df = pd.DataFrame(columns=header)

        totals_header = [dm.get_column_from_header(i, self.totals["TableColumns"])
                         for i in self.totals["TableColumns"]]
        self.totals_df = pd.DataFrame(index=[0], columns=totals_header)

        self.ids = []
        self.id_components = []

    def update_table(self, rule):
        """
        Populate the summary item dataframe with rows from the TabItem dataframes specified in the configuration.
        """
        df = self.df
        records = self.records

        id_column = records['IDColumn']
        db_columns = records['TableColumns']
        mapping_columns = records['MappingColumns']
        references = records['ReferenceTables']

        print('Info: rule {RULE}, summary {NAME}: updating table'.format(RULE=self.rule_name, NAME=self.name))

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

            # Append data to summary dataframe
            df = dm.append_to_table(df, append_df)

        self.ids = df[id_column].tolist()

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
            print('Warning: rule {RULE}, parameter {PARAM}: no values set for parameter'
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
            print('Configuration Warning: rule {RULE}, parameter {PARAM}: values required for parameter type "dropdown"'
                  .format(PARAM=name, RULE=rule_name))
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

        return layout


class AuditParameterDate(AuditParameter):
    """
    """

    def __init__(self, rule_name, name, cdict):
        super().__init__(rule_name, name, cdict)
        try:
            self.format = settings.format_date_str(date_str=cdict['DateFormat'])
        except KeyError:
            print('Warning: rule {RULE}, parameter {PARAM}: no date format specified ... defaulting to YYYY-MM-DD'
                  .format(PARAM=name, RULE=rule_name))
            self.format = "%Y-%m-%d"

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

        return layout

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
            print('Warning: rule {RULE}, parameter {PARAM}: no values set for parameter'
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
                    print('Configuration Error: rule {RULE}, parameter {PARAM}: invalid format string {STR}'
                          .format(RULE=self.rule_name, PARAM=self.name, STR=self.format))
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
            return True
        else:
            return False


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

        return layout

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

        return statement

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
            return True
        else:
            return False


