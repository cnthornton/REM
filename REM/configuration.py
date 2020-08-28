"""
REM configuration classes and functions. Includes audit rules, audit objects,
and rule parameters.
"""
import datetime
import dateutil.parser
import pandas as pd
import pyodbc
import PySimpleGUI as sg
import REM.layouts as lo
import REM.program_settings as const
import sqlalchemy as sqla
import yaml


class ConfigParameters:
    """
    Class to store and manage program configuration settings.

    Arguments:

        infile: Path to configuration file

    Attributes:

        language (str): Display language. Default: EN.

        logo (str): Logo to display on main screen.

        db (Class): 

        audit_rules (list): List of AuditRule objects.
    """

    def __init__(self, infile):

        try:
            fh = open(infile, 'r')
        except FileNotFoundError:
            print('Unable to load configuration file')
            sys.exit(1)

        cnfg = yaml.safe_load(fh)
        fh.close()

        # Display parameters
        self.language = cnfg['display']['language']
        self.logo = cnfg['display']['logo']

        # Database parameters
        dbdict = cnfg['database']
        self.database = DataBase(dbdict['odbc_driver'], dbdict['odbc_server'],\
                                 dbdict['odbc_port'], dbdict['database'])

        # Audit parameters
        audit_rules = cnfg['audit_rules']
        self.audit_rules = []
        for audit_rule in audit_rules:
            self.audit_rules.append(AuditRule(audit_rule, audit_rules[audit_rule]))

    def print_rules(self):
        """
        Return name of all audit rules defined in configuration file.
        """
        return([i.name for i in self.audit_rules])

    def fetch_rule(self, name):
        """
        """
        rules = self.print_rules()
        try:
            index = rules.index(name)
        except IndexError:
            print('Rule {NAME} not in list of configured audit rules. '\
                  'Available rules are {ALL}'\
                  .format(NAME=name, ALL=', '.join(self.print_rules())))
            rule = None
        else:
            rule = self.audit_rules[index] 

        return(rule)

    def modify(self):
        """
        """
        pass

    def display(self):
        """
        """
        pass


class AuditRule:
    """
    """

    def __init__(self, name, adict):

        self.name = name
        self.element_key = lo.as_key(name)
        self.permissions = adict['Permissions']
        self.parameters = []
        self.tabs = []
        self.elements = ['TG', 'Cancel', 'Start', 'Finalize']

        params = adict['Parameters']
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

        tdict = adict['Tabs']
        for tab_name in tdict:
            self.tabs.append(lo.Schema(name, tab_name, tdict[tab_name]))

    def key_lookup(self, element):
        """
        Lookup element key for input control element.
        """
        if element in self.elements:
            key = lo.as_key('{} {}'.format(self.name, element))
        else:
            key = None

        return(key)

    def fetch_tab(self, name, by_key:bool=False):
        """
        """
        if not by_key:
            names = [i.name for i in self.tabs]
        else:
            names = [i.element_key for i in self.tabs]

        try:
            index = names.index(name)
        except IndexError:
            tab_item = None
        else:
            tab_item = self.tabs[index]
        
        return(tab_item)

    def fetch_parameter(self, name, by_key:bool=False, by_type:bool=False):
        """
        """
        if by_key and by_type:
            print('Warning: the "by_key" and "by_type" arguments are mutually '\
                  'exclusive. Defaulting to "by_key".')
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
        
        return(param)

    def layout(self):
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

        # Audit parameters
        audit_name = self.name
        params = self.parameters

        # Layout elements
        layout_els = [[sg.Col([[sg.Text(audit_name, pad=(0, (pad_v, pad_frame)),
                         font=font_h)]], justification='c', 
                         element_justification='c')]]

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
        audit_layout = [sg.TabGroup([lo.tab_layout(self.tabs)],
                          pad=(pad_v, (pad_frame, pad_v)), 
                          tab_background_color=inactive_col,
                          selected_title_color=text_col,
                          selected_background_color=bg_col,
                          background_color=default_col, key=tabgroub_key)]
        layout_els.append(audit_layout)

        # Standard elements
        cancel_key = self.key_lookup('Cancel')
        start_key = self.key_lookup('Start')
        report_key = self.key_lookup('Finalize')
        bottom_layout = [lo.B2('Cancel', key=cancel_key, pad=((0, pad_el), (pad_v, 0)),
                           tooltip='Cancel current action'),
                         lo.B2('Start', key=start_key, pad=((pad_el, 0), (pad_v, 0)),
                           tooltip='Start audit'),
                         sg.Text(' ' * 224, pad=(0, (pad_v, 0))),
                         lo.B2('Finalize', key=report_key, pad=(0, (pad_v, 0)),
                           disabled=True,
                           tooltip='Finalize audit and generate summary report')]
        layout_els.append(bottom_layout)

        # Pane elements must be columns
        layout = sg.Col(layout_els, key=self.element_key, visible=False)

        return(layout)

    def toggle_parameters(self, window, value='enable'):
        """
        Enable / Disable audit rule parameter elements.
        """
        status = False if value == 'enable' else True

        for parameter in self.parameters:
            element_key = parameter.element_key
            print('Info: parameter {NAME}, rule {RULE}: updated element to '\
                  '"disabled={VAL}"'.format(NAME=parameter.name, \
                  RULE=self.name, VAL=status))

            window[element_key].update(disabled=status)


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
        self.value = None

    def set_value(self, values):
        """
        Set the value of the parameter element from user input.

        Arguments:

            values: dictionary of window element values.
        """
        try:
            elem_key = self.element_key
        except KeyError:
            print('Warning: parameter {PARAM}, rule {RULE}: no values set for '\
                  'parameter'.format(PARAM=self.name, RULE=self.rule_name))
            value = ''
        else:
            value = values[elem_key]

        self.value = value

    def values_set(self):
        """
        Check whether all values attributes have been set.
        """
        if self.value:
            return(True)
        else:
            return(False)

    def filter_statement(self):
        """
        Generate the filter clause for SQL querying.
        """
        db_field = self.name
        value = self.value
        if value:
            statement = ("{KEY} = ?".format(KEY=db_field), (value,))
        else:
            statement = ""

        return(statement)


class AuditParameterCombo(AuditParameter):
    """
    """

    def __init__(self, rule_name, name, cdict):
        super().__init__(rule_name, name, cdict)
        try:
            self.combo_values = cdict['Values']
        except KeyError:
            print('Configuration Warning: parameter {PM}, rule {RULE}: '\
                  'values required for parameter type "dropdown"'\
                  .format(PM=name, RULE=rule_name))
            self.combo_values = []
        
    def layout(self, padding:int=8):
        """
        Create a layout for rule parameter element 'dropdown'.
        """
        pad_el = const.ELEM_PAD
        pad_v = const.VERT_PAD

        key = self.element_key
        desc = '{}:'.format(self.description)
        values = self.combo_values

        width = max([len(i) for i in values]) + padding

        layout = [sg.Text(desc, pad=((0, pad_el), (0, pad_v))),
                  sg.Combo(values, key=key, enable_events=True,
                    size=(width, 1), pad=(0, (0, pad_v)))]

        return(layout)


class AuditParameterDate(AuditParameter):
    """
    """
    def __init__(self, rule_name, name, cdict):
        super().__init__(rule_name, name, cdict)
        try:
            self.format = format_date_str(cdict['DateFormat'])
        except KeyError:
            self.format = format_date_str("DD/MM/YYYY")

        self.value_raw = ''

    def layout(self):
        """
        Layout for the rule parameter element 'date'.
        """
        pad_el = const.ELEM_PAD
        pad_v = const.VERT_PAD
        pad_h = const.HORZ_PAD
        date_ico = const.CALENDAR_ICON

        desc = self.description

        key = self.element_key
        layout = [sg.Text(desc, pad=((0, pad_el), (0, pad_v))),
                  sg.Input('', key=key, size=(16, 1), enable_events=True,
                     pad=((0, pad_el), (0, pad_v)),
                     tooltip=_('Input date as YYYY-MM-DD or use the calendar ' \
                               'button to select the date')),
                   sg.CalendarButton('', format='%Y-%m-%d', image_data=date_ico,
                     border_width=0, size=(2, 1), pad=(0, (0, pad_v)),
                     tooltip=_('Select date from calendar menu'))]

        return(layout)

    def set_value(self, values):
        """
        Set the value of the parameter element from user input.

        Arguments:

            values: dictionary of window element values.
        """
        dparse = dateutil.parser.parse

        elem_key = self.element_key

        try:
            value_raw = values[elem_key]
        except KeyError:
            print('Warning: parameter {PARAM}, rule {RULE}: no values set for '\
                  'parameter'.format(PARAM=self.name, RULE=self.rule_name))
            value_fmt = ''
            value_raw = ''
        else:
            try:
                date = dparse(value_raw, yearfirst=True)
            except dateutil.parser._parser.ParserError:
                value_fmt = ''
                value_raw = ''
            else:
                value_fmt = date.strftime(self.format)

        self.value = value_fmt
        self.value_raw = value_raw

    def format_date_element(self, date_str):
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

        return(''.join(buff))


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

        desc = self.description

        desc_from = '{} From:'.format(desc)
        desc_to = '{} To:'.format(desc)
        key_from = self.element_key
        key_to = self.element_key2

        layout = [sg.Text(desc_from, pad=((0, pad_el), (0, pad_v))),
                  sg.Input('', key=key_from, size=(16, 1), enable_events=True,
                     pad=((0, pad_el), (0, pad_v)),
                     tooltip=_('Input date as YYYY-MM-DD or use the calendar ' \
                               'button to select the date')),
                   sg.CalendarButton('', format='%Y-%m-%d', image_data=date_ico,
                     border_width=0, size=(2, 1), pad=(0, (0, pad_v)),
                     tooltip=_('Select date from calendar menu')),
                   sg.Text(desc_to, pad=((pad_h, pad_el), (0, pad_v))),
                   sg.Input('', key=key_to, size=(16, 1), enable_events=True,
                     pad=((0, pad_el), (0, pad_v)),
                     tooltip=_('Input date as YYYY-MM-DD or use the calendar ' \
                               'button to select the date')),
                   sg.CalendarButton('', format='%Y-%m-%d', image_data=date_ico,
                     border_width=0, size=(2, 1), pad=(0, (0, pad_v)),
                     tooltip=_('Select date from calendar menu'))]

        return(layout)

    def filter_statement(self):
        """
        Generate the filter clause for SQL querying.
        """
        db_field = self.name

        params = (self.value, self.value2)
        statement = ("{KEY} BETWEEN ? AND ?".format(KEY=db_field), params)

        return(statement)

    def set_value(self, values):
        """
        Set the value of the parameter element from user input.

        Arguments:

            values: dictionary of window element values.
        """
        elem_key = self.element_key
        elem_key2 = self.element_key2
        self.value = values[elem_key]
        self.value2 = values[elem_key]

    def values_set(self):
        """
        Check whether all values attributes have been set.
        """
        if self.value and self.value2:
            return(True)
        else:
            return(False)


class DataBase:
    """
    Primary database object for querying databases and initializing 
    authentication.
    """

    def __init__(self, driver, server, port, database):
        """
        Initialize database attributes.

        Attributes:
        
            server (str): Name of the ODBC server.

            driver (str): ODBC server driver.

            port (str): Connection port to ODBC server.

            dbname (str): Database name.

            cnxn (obj): pyodbc connection object
        """
        self.driver = driver
        self.server = server
        self.port = port
        self.dbname = database
        self.cnxn = None

    def query(self, table, columns, filter_rules):
        """
        Query database for the given order number.

        Arguments:

            params (dict): Tab-specific database parameters.

            filter_rules (list): List of tuples, each containing three 
                elements: column name, operator, and value.
        """
        # Connect to database
        conn = self.cnxn

        if not conn:
            print('Connection to database {} not established'.format(self.dbname))
            return(None)

        cursor = conn.cursor()

        # Construct filtering rules
        where_str = ' AND '.join([i[0] for i in filter_rules])
        params = ()
        for j in [i[1] for i in filter_rules]:
            params += j

        # Query database and format results as a Pandas dataframe
        colnames = ', '.join(columns)
        dbname = self.dbname
        query_str = 'SELECT {COLS} FROM {TABLE} WHERE {FILTER};'\
            .format(COLS=colnames, TABLE=table, FILTER=where_str)

        df = pd.read_sql(query_str, conn, params=params)

        cursor.close()

        return(df)

    def authenticate(self, uid, pwd):
        """
        Query database as user to validate sign-on.

        Arguments:

            uid (str): Account user name.

            pwd (str): Account password.
        """
        ugroup = 'user'

        # Connect to database
        db_settings = {'Driver': self.driver, 
                       'Server': self.server, 
                       'Database': self.dbname, 
                       'Port': self.port, 
                       'UID': uid, 
                       'PASS': pwd}

        conn_str = ';'.join(['{}={}'.format(k, db_settings[k]) for k in \
                             db_settings if db_settings[k]])

        try:
            conn = pyodbc.connect(conn_str)
        except pyodbc.OperationalError as e:
            print('Authentication failed for user {UID} while attempting to '\
                  'access databse {DB}'.format(UID=uid, DB=self.dbname))
            print('Relevant error is: {}'.format(e))
            return(None)

        cursor = conn.cursor()

        # Priveleages
        try:
            cursor.execute("SELECT user_name, user_group FROM users")
        except pyodbc.ProgrammingError:
            print('Error while accessing the users table in database {}'\
                .format(self.dbname))
            print('Relevant error is: {}'.format(e))
            return(None)

        for row in cursor.fetchall():
            if row.user_name == uid:
                ugroup = row.user_group
                break

        cursor.close()

        # Database configuration settings
        self.cnxn = conn

        return(ugroup)

class DatabaseREM(DataBase):
    """
    Database object for querying the REM database and initializing 
    authentication.
    """

    def __init__(self, driver, server, port):
        """
        Initialize database attributes.

        Attributes:
        
            server (str): Name of the ODBC server.

            driver (str): ODBC server driver.

            port (str): Connection port to ODBC server.

            dbname (str): Database name.

            cnxn (obj): pyodbc connection object
        """
        super().__init__(driver, server, port)
        self.database = 'REM'

    def layout():
        """
        Generate GUI layout for the DB Update panel.
        """
        layout = sg.Col()

        return(layout)

    def insert(self):
        """
        Insert data into the daily summary table.
        """
        success = True

        return(success)


def format_date_str(date_str):
    """
    """
    separators = set('/- ')
    date_fmts = {'YY': '%y', 'YYYY': '%Y', 
                 'MM': '%m', 'M': '%-m', 
                 'DD': '%d', 'D': '%-d'}

    strfmt = []

    last_char = date_str[0]
    buff = [last_char]
    for char in date_str[1:]:
        if char == last_char:
            buff.append(char)
        else:
            component = ''.join(buff)
            try:
                strfmt.append(date_fmts[component])
            except KeyError:
                if component in separators:
                    strfmt.append(component)
                else:
                    print('Warning: unknown date format {} provided in date '\
                          'string {}'.format(component, date_str))
            buff = [char]
        last_char = char

    try:
        strfmt.append(date_fmts[''.join(buff)])
    except KeyError:
        print('Warning: unsupported characters found at the end of the date '\
              'str {}'.format(date_str))

    return(''.join(strfmt))
