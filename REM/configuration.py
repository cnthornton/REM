"""
REM configuration classes and functions. Includes audit rules, audit objects,
and rule controls.
"""
import pyodbc
import PySimpleGUI as sg
import REM.layouts as lo
import REM.program_settings as const
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
        self.database = DataBase(dbdict)

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
        except:
            pass

        return(self.audit_rules[index])

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
        self.permissions = adict['permissions']

        controls = adict['controls']
        self.controls = [ControlItem(name, i, controls[i]) for i in controls]

        tdict = adict['items']

        self.tabs = []
        for item in tdict:
            layout = tdict[item]['layout_schema']
            if layout == 'reviewable':
                self.tabs.append(lo.Schema(name, item, tdict[item]))
            elif layout == 'scanable':
                self.tabs.append(lo.SchemaScanable(name, item, tdict[item]))
            elif layout == 'verifiable':
                self.tabs.append(lo.SchemaVerifiable(name, item, tdict[item]))

        self.elements = ['TG', 'Cancel', 'Start', 'Finalize'] + list(controls.keys())

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

    def fetch_control(self, name, by_key:bool=False):
        """
        """
        if not by_key:
            names = [i.name for i in self.controls]
        else:
            names = [i.element_key for i in self.controls]

        try:
            index = names.index(name)
        except IndexError:
            control_item = None
        else:
            control_item = self.controls[index]
        
        return(control_item)

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
        controls = self.controls

        # Layout elements
        layout_els = [[sg.Col([[sg.Text(audit_name, pad=(0, (pad_v, pad_frame)),
                         font=font_h)]], justification='c', 
                         element_justification='c')]]

        # Control elements
        ncontrol = len(controls)
        control_elements = []
        for control in controls:
            if ncontrol > 1:
                pad_text = sg.Text(' ' * 4) 
            else:
                pad_text = sg.Text('')

            control_layout = control.layout
            control_layout.append(pad_text)

            control_elements += control.layout
        layout_els.append(control_elements)

        # Tab elements
        tabgroub_key = self.key_lookup('TG')
        audit_layout = [sg.TabGroup([lo.tab_layout(self.tabs)],
                          pad=(pad_v, pad_v), tab_background_color=inactive_col,
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
                         sg.Text(' ' * 174, pad=(0, (pad_v, 0))),
                         lo.B2('Finalize', key=report_key, pad=(0, (pad_v, 0)),
                           disabled=True,
                           tooltip='Finalize audit and generate summary report')]
        layout_els.append(bottom_layout)

        # Pane elements must be columns
        layout = sg.Col(layout_els, key=self.element_key, visible=False)

        return(layout)


class ControlItem:
    """
    """

    def __init__(self, rule_name, name, cdict):
        
        self.rule = rule_name
        self.name = name
        self.element_key = lo.as_key('{} {}'.format(rule_name, name))
        self.db_key = cdict['key']
        self.desc = cdict['desc']
        self.value = None
        self.operator = cdict['operator']

        layout = cdict['type']
        if layout == 'dropdown':
            self.elements = [name]
            self.layout = lo.control_layout_dropdown(rule_name, name, cdict)
        elif layout == 'calendar':
            self.elements = [name]
            self.layout = lo.control_layout_date(rule_name, name, cdict)


class DataBase:
    """
    """

    def __init__(self, dbdict):
        """

        Attributes:
        
            location (str): Path to database files

            server (str): Name of the ODBC server

            driver (str): Server driver

            username (str): Account username

            password (str): Account password
        """
        self.server = dbdict['odbc_server']
        self.driver = dbdict['odbc_driver']
        self.port = dbdict['odbc_port']
        self.username = None
        self.password = None

    def query(self, params, filter_rules):
        """
        Query database for the given order number.

        Arguments:

            params (dict): Audit-specific database parameters.

            filter_rules (list): List of tuples, each containing three 
                elements: column name, operator, and value.
        """
        # Database configuration settings
        uid = self.username
        pwd = self.password

        if not uid or not pwd:
            print('No account information available for querying')
            raise

        server = self.server
        driver = self.driver
        dbname = params['name']
        table = params['table']
        colnames = ', '.join(params['columns'])

        # Connect to database
        db_settings = 'Driver={DRIVER};Server={SERVER};Database={DB};UID={USER};' \
                      'PWD={PASS};sslmode=require;'.format(DRIVER=driver, \
                      SERVER=server, DB=dbname, USER=uid, PASS=pwd)

        conn = pyodbc.connect(db_settings)
        cursor = conn.cursor()

        # Construct filtering rules
#        where_clause = ' AND '.join(['{COL}{OP}{VAL}'.format(COL=controls[i].name, OP=controls[i].operator, VAL=controls[i].value) for i in controls])
        where_clause = ' AND '.join(['{COL}{OP}{VAL}'.format(COL=i[0], OP=i[1], VAL=i[2]) for i in filter_rules])

        # Query database and format results as a Pandas dataframe
        query = 'SELECT {COLS} FROM {DB}.{TABLE} WHERE {FILTER};'.format(COLS=colnames, DB=dbname, TABLE=table, FILTER=where_clause)

        df = pd.read_sql(conn, query)

        return(df)

    def insert(self):
        """
        Insert data into the daily summary table.
        """
        success = True

        return(success)

    def update_account(self, user):
        """
        """
        self.username = user.name
        self.password = user.password
