"""
REM Layout classes and functions.
"""
import datetime
import dateutil
import PySimpleGUI as sg
import numpy as np
import pandas as pd
import re
import REM.configuration as config
import REM.program_settings as const
import REM.secondary_win as win2
import sys
import threading


# Schema Layout Classes
class Schema:
    def __init__(self, rule_name, name, tdict):
        self.name = name
        self.rule_name = rule_name
        element_name = "{RULE} {TAB}".format(RULE=rule_name, TAB=name)
        self.element_name = element_name
        self.element_key = as_key(element_name)
        self.data_elements = ['Table', 'Summary']
        self.action_elements = ['Audit', 'Input', 'Add']
        self._actions = ['scan', 'cc', 'errors']

        self.actions = []  
        self.id_format = []

        try:
            columns = tdict['DisplayColumns']
        except KeyError:
            msg = ('Configuration Error: tab {NAME}, rule {RULE}: missing '\
                   'required field "DisplayColumns".')\
                   .format(NAME=name, RULE=rule_name)
            win2.popup_error(msg)
            sys.exit(1)
        self.db_columns = columns

        db_key = tdict['PrimaryKey']
        if db_key not in columns:
            msg = ('Configuration Error: tab {NAME}, rule {RULE}: item '\
                    'PrimaryKey "{KEY}" must also be contained in the '\
                    'Display Column.').format(NAME=name, RULE=rule_name, \
                    KEY=db_key)
            win2.popup_error(msg)
            sys.exit(1)
        self.db_key = db_key

        try:
            self.db_table = tdict['DatabaseTable']
        except KeyError:
            msg = ('Configuration Error: tab {NAME}, rule {RULE}: missing '\
                   'required field "DatabaseTable".')\
                   .format(NAME=name, RULE=rule_name)
            win2.popup_error(msg)
            sys.exit(1)

        try:
            actions = tdict['AuditMethods']
        except KeyError:
            self.actions = []
        else:
            for action in actions:
                if action in self._actions:
                    self.actions.append(action)
                else:
                    print('Configuration Warning: tab {NAME}, rule {RULE}: '\
                          'unknown audit method specified {METHOD}'\
                          .format(Name=name, RULE=rule_name, METHOD=action))

        try:
            self.codes = tdict['Codes']
        except KeyError:
            self.codes = {}

        try:
            self.summary_rules = tdict['SummaryRules']
        except KeyError:
            self.summary_rules = {}

        try:
            self.error_rules = tdict['ErrorRules']
        except KeyError:
            self.error_rules = {}

        try:
            self.id_format = re.findall(r'\{(.*?)\}', tdict['IDFormat'])
        except KeyError:
            msg = ('Configuration Error: tab {NAME}, rule {RULE}: missing '\
                   'required field "IDFormat".')\
                   .format(NAME=name, RULE=rule_name)
            win2.popup_error(msg)
            sys.exit(1)

        # Dynamic attributes
        self.df = pd.DataFrame(empty_data_table(nrow=20, ncol=len(columns)), \
                columns=columns)  #initialize with an empty table

        self.errors = []
        self.audit_performed = False
        self.id_components =[]

    def reset_dynamic_attributes(self):
        """
        Reset class dynamic attributes to default.
        """
        headers = self.db_columns
        ncol = len(headers)
        data = empty_data_table(nrow=10, ncol=ncol)
        self.df = pd.DataFrame(data, columns=headers)
        self.errors = []
        self.audit_performed = False
        self.id_components =[]

    def update(self, window, element_tup):
        """
        """
        for element, new_param in element_tup:
            element_key = self.key_lookup(element)
            if element_key:
                expression = "window['{}'].update({})"\
                    .format(element_key, new_param)
                eval(expression)

                print('Info: tab {NAME}, rule {RULE}: updated element {ELEM} to {VAL}'\
                    .format(NAME=self.name, RULE=self.rule_name,ELEM=element, VAL=new_param))
            else:
                print('Layout Warning: tab {NAME}, rule {RULE}: element '\
                      '{ELEM} not found in list of sub-elements'\
                      .format(Name=self.name, RULE=self.rule_name, ELEM=element))

    def update_table(self, window):
        """
        Update Table element with data
        """
        tbl_error_col = const.TBL_ERROR_COL
        tbl_key = self.key_lookup('Table')

        try:
            self.df.sort_values(by=[self.db_key], inplace=True, ascending=True)
        except KeyError:
            self.df.sort_values(by=[self.db_key.lower()], inplace=True, \
                ascending=True)

        data = self.df.values.tolist()
        window[tbl_key].update(values=data)

        error_rows = self.errors
        if error_rows:
            error_colors = [(i, tbl_error_col) for i in error_rows]
            window[tbl_key].update(row_colors=error_colors)

    def update_id_components(self, parameters):
        """
        """
        id_format = self.id_format
        self.id_components = []

        last_index = 0
        print('Info: tab {NAME}, rule {RULE}: ID is formatted as {FORMAT}'\
            .format(NAME=self.name, RULE=self.rule_name, FORMAT=id_format))
        param_fields = [i.name for i in parameters]
        for component in id_format:
            if len(component) > 1 and set(component).issubset(set('YMD-/ ')):  #component is datestr
                component_len = len(component)
                index = (last_index, last_index + component_len)
                part_tup = ('date', component, index)
            elif component in self.codes:
                value = self.codes[component]
                component_len = len(value)
                index = (last_index, last_index + component_len)
                part_tup = (component, value, index)
            elif component in param_fields:
                param = parameters[param_fields.index(component)]
                value = param.value
                component_len = len(value)
                index = (last_index, last_index + component_len)
                part_tup = (component, value, index)
            elif component.isnumeric():  #component is an incrementing number
                component_len = len(component)
                index = (last_index, last_index + component_len)
                part_tup = ('variable', component_len, index)
            else:  #unknown component type, probably separator
                component_len = len(component)
                index = (last_index, last_index + component_len)
                part_tup = ('separator', component, index)

            self.id_components.append(part_tup)

            last_index += component_len

        print('Info: tab {NAME}, rule {RULE}: ID updated with components {COMP}'\
            .format(NAME=self.name, RULE=self.rule_name, COMP=self.id_components))

    def format_id(self, number, date=None):
        """
        """
        date_items_set = set('YMD-/ ')

        number = str(number)

        id_parts = []
        for component in self.id_components:
            comp_name, comp_value, comp_index = component

            if comp_name == 'date':  #component is datestr
                strfmt = config.format_date_str(comp_value)
                if not date:
                    print('Warning: tab {NAME}, rule {RULE}: no date provided '\
                          'for ID number {NUM} ... reverting to todays date'\
                          .format(NAME=self.name, RULE=self.rule_name, NUM=number))
                    value = datetime.datetime.now().strftime(strfmt)
                else:
                    value = date.strftime(strfmt)
            elif comp_name == 'variable':
                value = number.zfill(comp_value)
            else:
                value = comp_value

            id_parts.append(value)

        return(''.join(id_parts))

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
                    print('Warning: ID component {COMP} cannot be found in '\
                          'identifier {IDENT}'.format(COMP=component, \
                          IDENT=identifier))

                break

        return(comp_value)

    def parse_operation_string(self, rule):
        """
        """
        operators = set('+-*/>=<')

        # Find the column names and operators defined in the rule
        list_out = []
        buff = []
        for char in rule:
            if char in operators:  #char is operator
                list_out.append(''.join(buff))

                buff = []
                list_out.append(char)
            else:  #char is not operator, append to buffer
                if char.isspace():  #skip whitespace
                    continue
                else:
                    buff.append(char)
        list_out.append(''.join(buff))

        return(list_out)

    def update_summary(self, window):
        """
        Update Summary element with data summary
        """
        operators = set('+-*/')

        df = self.df
        headers = df.columns.values.tolist()
        summ_rules = self.summary_rules

        outputs = []
        # Total number of rows
        output = (_('Number of rows in table'), df.shape[0])
        outputs.append(output)

        # Total number of errors identified based on specified error rules
        output = (_('Number of errors identified'), len(self.errors))
        outputs.append(output)

        # Summarize all headers
        totals = {}
        for header in headers:
            # Determine object type of the values in each column
            dtype = df.dtypes[header]
            if dtype in (np.int64, np.float64):
                col_summary = df[header].sum()
            elif dtype == np.object:
                col_summary = df[header].nunique()
            else:  #possibly empty dataframe
                col_summary = 0

            totals[header] = col_summary

            # Summarize number of transactions in the table
            if header in (self.db_key, self.db_key.lower()):
                output = (_('Number of transactions processed'), col_summary)
                outputs.append(output)

        # Calculate totals defined by summary rules
        for rule_name in summ_rules:
            rule = summ_rules[rule_name]
            rule_values = []
            for item in self.parse_operation_string(rule):
                if item in operators:
                    rule_values.append(item)
                else:
                    try:
                        rule_values.append(totals[item])
                    except KeyError:  #try lower-case
                        try:  #ODBC may be PostGreSQL
                            rule_values.append(totals[item.lower()])
                        except KeyError:  #not in display columns
                            print('Warning: tab {TAB}, rule {Rule}: summary '\
                                  'rule item {ITEM} not in display columns'\
                                  .format(NAME=self.name, RULE=self.rule_name, \
                                  ITEM=item))
                            rule_values.append(0)

            summary_total = eval(' '.join([str(i) for i in rule_values]))

            outputs.append((rule_name, summary_total))

        summary_key = self.key_lookup('Summary')
        window[summary_key].update(value='\n'.join(['{}: {}'.format(*i) for \
            i in outputs]))

    def toggle_actions(self, window, value='enable'):
        """
        Enable / Disable schema action buttons.
        """
        status = False if value == 'enable' else True

        for element in self.action_elements:
            element_tup = [(element, 'disabled={}'.format(status))]
            self.update(window, element_tup)

    def key_lookup(self, element):
        """
        Lookup key for element in schema.
        """
        elements = self.data_elements + self.action_elements
        if element in elements:
            key = as_key('{} {}'.format(self.element_name, element))
        else:
            print('Warning: tab {TAB}, rule {RULE}: element {ELEM} not found '\
                  'in list of sub-elements'\
                .format(TAB=self.name, RULE=self.rule_name, ELEM=element))
            key = None

        return(key)

    def layout(self, admin:bool=False):
        """
        Tab schema for layout type 'reviewable'.
        """
        # Window and element size parameters
        bg_col = const.ACTION_COL
        default_col = const.DEFAULT_COL

        pad_frame = const.FRAME_PAD
        pad_el = const.ELEM_PAD
        pad_v = const.VERT_PAD
        pad_h = const.HORZ_PAD

        frozen = False if admin else True

        header = self.df.columns.values.tolist()
        data = self.df.values.tolist()

        summary_key = self.key_lookup('Summary')
        audit_key = self.key_lookup('Audit')
        table_key = self.key_lookup('Table')
        add_key = self.key_lookup('Add')
        input_key = self.key_lookup('Input')
        layout = [[create_table(data, header, table_key, bind=True)],
                  [sg.Frame(_('Summary'), [[sg.Multiline('', border_width=0, 
                        size=(60, 8), font=('Sans Serif', 10), key=summary_key, 
                        disabled=True, background_color=bg_col)]], 
                     pad=((pad_frame, 0), (0, pad_frame)), 
                     background_color=bg_col, element_justification='l'), 
                   sg.Text(' ' * 62, background_color=bg_col),
                   sg.Col([[
                       sg.Input('', key=input_key, size=(20, 1), 
                         pad=(pad_el, 0), font=('Sans Serif', 10),
                         tooltip=_('Input document number to add a '\
                                   'transaction to the table'), disabled=True),
                       B2(_('Add'), key=add_key, pad=((0, pad_h), 0), 
                         tooltip=_('Add order to the table'), disabled=True), 
                       B2(_('Audit'), key=audit_key, disabled=True, 
                         tooltip=_('Run Audit methods'), pad=(0, 0))
                   ]], background_color=bg_col)
                 ]]

        return(layout)

    def row_ids(self):
        """
        Return a list of all row IDs in the dataframe.
        """
        try:
            row_ids = list(self.df[self.db_key])
        except KeyError:  #database probably PostGreSQL
            try:
                row_ids = list(self.df[self.db_key.lower()])
            except KeyError:
                print('Warning: tab {TAB}, rule {RULE}: missing database key '\
                      '{KEY} in column headers'\
                      .format(TAB=self.name, RULE=self.rule_name, KEY=self.db_key))
                row_ids = []

        return(row_ids)

    def run_audit(self, *args, **kwargs):
        """
        """
        method_map = {'scan': self.scan_for_missing, 
                      'errors': self.search_for_errors,
                      'cc': self.crosscheck_reference}

        for action in self.actions:
            action_function = method_map[action]
            try:
#                threading.Thread(target=action_function, args=args, kwargs=kwargs, daemon=True).start()
                action_function(*args, **kwargs)
            except AttributeError:
                print('Warning: "Schema" class has no method named {METHOD}'\
                    .format(TAB=self.name, RULE=self.rule_name, \
                    METHOD=action_function.split('.', 1)[-1]))
                continue

        self.audit_performed = True

    def scan_for_missing(self, *args, **kwargs):
        """
        Search for missing transactions using scan.
        """
        # Arguments
        db = kwargs['database']
        audit_params = kwargs['parameters']
        window = args[0]

        # Update ID components with parameter values
        self.update_id_components(audit_params)

        cursor = db.cnxn.cursor()

        pkey = self.db_key.lower()  #for PostGreSQL only
        df = self.df
        df.sort_values(by=[pkey], inplace=True, ascending=True)
        pkey_list = df[pkey].tolist()

        # Format audit parameters
        for audit_param in audit_params:
            if audit_param.type.lower() == 'date':
                date_col = audit_param.name
                date_fmt = audit_param.format
                try:
                    audit_date = dateutil.parser.parse(audit_param.value, \
                        dayfirst=True)
                except dateutil.parser._parser.ParserError:
                    print('Warning: no date provided ... skipping checks for most recent ID')
                    audit_date = None
                else:
                    audit_date_iso = audit_date.strftime("%Y-%m-%d")
        
        # Search for missing data
        missing_transactions = []

        try:
            first_id = pkey_list[0]
        except IndexError:  #no data in dataframe
            print('Warning: {NAME} Audit: no transactions for audit date {DATE}'\
                .format(NAME=self.name, DATE=audit_date_iso))
            return(False)

        first_number_comp = int(self.get_id_component(first_id, 'variable'))
        first_date_comp = self.get_id_component(first_id, 'date')
        print('Info: {} Audit: first transaction id {} has number {} and date {}'\
              .format(self.name, first_id, first_number_comp, first_date_comp))

        ## Find date of last transaction
        query_str = 'SELECT DISTINCT {DATE} from {TBL}'.format(DATE=date_col, TBL=self.db_table)
        cursor.execute(query_str)

        unq_dates = [dateutil.parser.parse(row[0], dayfirst=True) for row in cursor.fetchall()]
        unq_dates_iso = [i.strftime("%Y-%m-%d") for i in unq_dates]
        unq_dates_iso.sort()

        try:
            current_date_index = unq_dates_iso.index(audit_date_iso)
        except IndexError:
            print('Warning: {NAME} Audit: no transactions for audit date {DATE}'\
                  .format(NAME=self.name, DATE=audit_date_iso))
            return(False)

        try:
            prev_date = dateutil.parser.parse(unq_dates_iso[current_date_index - 1])
        except IndexError:
            prev_date = None

        ## Query last transaction from previous date
        if prev_date:
            print('Info: {NAME} Audit: searching for last transaction created '\
                  'prior to {DATE}'.format(NAME=self.name, DATE=audit_date_iso))

            filters = [('{DATE} = ?'.format(DATE=date_col), (prev_date.strftime(date_fmt),))]
            last_df = db.query(self.db_table, self.db_columns, filters)
            last_df.sort_values(by=[pkey], inplace=True, ascending=False)

            last_id = None
            prev_ids = last_df[pkey].tolist()
            for prev_id in prev_ids:
                prev_number_comp = int(self.get_id_component(prev_id, 'variable'))
                prev_date_comp = self.get_id_component(prev_id, 'date')

                if prev_number_comp > first_number_comp:
                    continue

                # Search only for IDs with correct ID formats 
                # (skip potential errors)
                if prev_id == self.format_id(prev_number_comp, date=prev_date):
                    last_id = prev_id
                    break

            if last_id:
                print('Info: {NAME} Audit: last transaction ID is {ID} from {DATE}'\
                    .format(NAME=self.name, ID=last_id, DATE=prev_date))

                if first_date_comp != prev_date_comp:  #start of new month
                    if first_number_comp != 1:
                        missing_range = list(range(1, first_number_comp))
                    else:
                        missing_range = []

                else:  #still in same month
                    if (prev_number_comp + 1) != first_number_comp:  #first not increment of last
                        missing_range = list(range(prev_number_comp + 1, first_number_comp))
                    else:
                        missing_range = []

                for missing_number in missing_range:
                    missing_id = self.format_id(missing_number, date=audit_date)
                    missing_transactions.append(missing_id)

        ## Search for skipped transaction numbers
        prev_number = first_number_comp
        for transaction_id in pkey_list[1:]:
            trans_number = int(self.get_id_component(transaction_id, 'variable'))
            if (prev_number + 1) != trans_number:
                missing_range = list(range(prev_number + 1, trans_number))
                for missing_number in missing_range:
                    missing_id = self.format_id(missing_number, date=audit_date)
                    missing_transactions.append(missing_id)

            prev_number = trans_number

        print('Info: {NAME} Audit: potentially missing transactions: {MISS}'\
            .format(NAME=self.name, MISS=missing_transactions))

        if missing_transactions:
            filter_values = ['?' for i in missing_transactions]
            filter_str = '{COL} IN ({VALUES})'.format(COL=pkey, VALUES=', '.join(filter_values))
            filters = [(filter_str, tuple(missing_transactions))]

            missing_data = db.query(self.db_table, self.db_columns, filters)
        else:
            missing_data = pd.DataFrame(columns=[i.lower() for i in self.db_columns])

        # Display import window with potentially missing data
        import_data = win2.import_window(missing_data, db, self.db_table, pkey)

        # Updata dataframe with imported data
        df = df.append(import_data, ignore_index=True, sort=False)
        df.sort_values(by=[pkey], inplace=True, ascending=True)
        df.reset_index(drop=True, inplace=True)
        self.df = df
        print('New size of {0} dataframe is {1} rows and {2} columns'\
            .format(self.name, *df.shape))

        # Inform main thread that sub-thread has completed its operations
#        window.write_event_value('-THREAD_DONE-', '')

    def search_for_errors(self, *args, **kwargs):
        """
        Use error rules specified in configuration file to annotate rows.
        """
        operators = set('>=<')

        db = kwargs['database']
        audit_params = kwargs['parameters']
        window = args[0]

        cursor = db.cnxn.cursor()

        headers = self.df.columns.values.tolist()
        pkey = self.db_key if self.db_key in headers else self.db_key.lower()

        #Transaction ID errors

        # Defined rule errors
        error_rules = self.error_rules
        for rule_name in error_rules:
            error_rule = error_rules[rule_name]
            parsed_rule = self.parse_operation_string(error_rule)

            rule_value = []
            for item in parsed_rule:
                if item in operators:
                    if item == '=':
                        rule_value.append('==')
                    else:
                        rule_value.append(item)
                elif item in headers:
                    rule_value.append('self.df["{}"]'.format(item))
                elif item.lower() in headers:
                    rule_value.append('self.df["{}"]'.format(item.lower()))
                else:
                    try:
                        item_num = float(item)
                    except ValueError:
                        print('Warning: tab {TAB}, rule {RULE}: unsupported item '\
                              '{ITEM} provided to error rule {ERROR}'\
                              .format(TAB=self.name, RULE=self.rule_name, \
                              ITEM=item, ERROR=rule_name))
                        rule_value = ['self.df["{}"]'.format(pkey), '==', \
                            'self.df["{}"]'.format(pkey)]
                        break
                    else:
                        rule_value.append(item)

            try:
                error_list = list(eval(' '.join(rule_value)))
            except SyntaxError:
                print('Warning: tab {TAB}, rule {RULE}: invalid syntax for '\
                      'error rule {ERROR}'.format(TAB=self.name, \
                      RULE=self.rule_name, ERROR=rule_name))
                error_list = []

            for index, value in enumerate(error_list):
                if not value:  #False: row failed the error rule test
                    if index not in self.errors:
                        self.errors.append(index)

        # Inform main thread that sub-thread has completed its operations
#        window.write_event_value('-THREAD_DONE-', '')

    def crosscheck_reference(self, *args, **kwargs):
        """
        """
        pass


def transaction_date(transaction_number, number_format):
    """
    """
    return(None)

def transaction_increment(transaction_number, number_format):
    """
    """
    return(None)

def transaction_code(transaction_number, number_format):
    """
    """
    return(None)

def as_key(key):
    """
    Format string as element key.
    """
    return('-{}-'.format(key).replace(' ', ':').upper())

# GUI Element Functions
def B1(*args, **kwargs):
    """
    Action button element defaults.
    """
    size = const.B1_SIZE
    return(sg.Button(*args, **kwargs, size=(size, 1)))

def B2(*args, **kwargs):
    """
    Panel button element defaults.
    """
    size = const.B2_SIZE
    return(sg.Button(*args, **kwargs, size=(size, 1)))

# Element Creation
def empty_data_table(nrow:int=20, ncol:int=10):
    """
    """
    return([['' for col in range(ncol)] for row in range(nrow)])

def create_table(data, header, keyname, events:bool=False, bind:bool=False, \
        tooltip:str=None, nrows:int=const.TBL_NROW, \
        height:int=const.TBL_HEIGHT, width:int=const.TBL_WIDTH):
    """
    Create table elements that have consistency in layout.
    """
    # Element settings
    text_col=const.TEXT_COL
    alt_col = const.TBL_ALT_COL
    bg_col = const.TBL_BG_COL
    select_col = const.TBL_SELECT_COL
    pad_frame = const.FRAME_PAD
    pad_el = const.ELEM_PAD

    # Parameters
    if events and bind:
        bind = False  #only one can be selected at a time
        print('Warning: both bind_return_key and enable_events have been '\
              'selected during table creation. These parameters are mutually '\
              'exclusive.')

    # Size of data
    ncol = len(header)

    # When table columns not long enough, need to adjust so that the
    # table fills the empty space.
    max_char_per_col = int(width / ncol)

    # Each column has size == max characters per column
    lengths = [max_char_per_col for i in header]

    # Add any remainder evenly between columns
    remainder = width - (ncol  * max_char_per_col)
    index = 0
    for one in [1 for i in range(remainder)]:
        if index > ncol - 1:
            index = 0
        lengths[index] += one
        index += one

    new_size = sum(lengths)

    layout = sg.Table(data, headings=header, pad=(pad_frame, pad_frame),
               key=keyname, row_height=height, alternating_row_color=alt_col,
               text_color=text_col, selected_row_colors=(text_col, select_col), 
               background_color=bg_col, num_rows=nrows, font=('Sans Serif', 10),
               display_row_numbers=False, auto_size_columns=False,
               col_widths=lengths, enable_events=events, tooltip=tooltip,
               vertical_scroll_only=False, bind_return_key=bind)

    return(layout)

# Panel layouts
def action_layout(cnfg):
    """
    """
    # Layout settings
    bg_col = const.ACTION_COL
    pad_frame = const.FRAME_PAD
    pad_el = const.ELEM_PAD
    pad_v = const.VERT_PAD
    button_size = 31

    rule_names = cnfg.print_rules()
    nrule = len(rule_names)
    pad_screen = (266 - (nrule * button_size)) / 2

    # Button layout
    buttons = [[sg.Text('', pad=(pad_frame, 0), size=(0, 0),
                  background_color=bg_col)]]

    for rule_name in rule_names:
        rule_el = [B1(rule_name, pad=(pad_frame, pad_el), disabled=True)]
        buttons.append(rule_el)

    other_bttns = [[sg.HorizontalSeparator(pad=(pad_frame, pad_v))],
                   [B1(_('Update Database'), pad=(pad_frame, pad_el), 
                      key='-DB-', disabled=True)],
                   [sg.HorizontalSeparator(pad=(pad_frame, pad_v))],
                   [B1(_('Summary Statistics'), pad=(pad_frame, pad_el), 
                      key='-STATS-', disabled=True)],
                   [B1(_('Summary Reports'), pad=(pad_frame, pad_el), 
                      key='-REPORTS-', disabled=True)],
                   [sg.Text('', pad=(pad_frame, 0), size=(0, 0),
                      background_color=bg_col)]]

    buttons += other_bttns

    layout = sg.Col([[sg.Text('', pad=(0, pad_screen))],
                     [sg.Frame('', buttons, element_justification='center', 
                        relief='raised', background_color=bg_col)],
                     [sg.Text('', pad=(0, pad_screen))]], key='-ACTIONS-')

    return(layout)

def tab_layout(tabs):
    """
    Layout of the audit panel tab groups.
    """
    # Element parameters
    bg_col = const.ACTION_COL

    # Populate tab layouts with elements
    layout = []
    for i, tab in enumerate(tabs):  #iterate over audit rule tabs / items
        tab_name = tab.name
        tab_key = tab.element_key

        # Enable only the first tab to start
        visible = True if i == 0 else False

        # Generate the layout
        tab_layout = tab.layout()

        layout.append(sg.Tab(tab_name, tab_layout, visible=visible, 
            background_color=bg_col, key=tab_key))

    return(layout)
