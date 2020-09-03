"""
REM configuration classes and functions. Includes audit rules, audit objects,
and rule parameters.
"""
import datetime
import dateutil.parser
import pyodbc
import PySimpleGUI as sg
import re
import REM.layouts as lo
import REM.program_settings as const
import REM.secondary_win as win2


class ProgramSettings:
    """
    Class to store and manage program configuration settings.

    Arguments:

        cnfg: Parsed YAML file

    Attributes:

        language (str): Display language. Default: EN.

        logo (str): Logo to display on main screen.

        driver (str): ODBC driver

        server (str): Database server.

        port (str): Listening port for database connections

        dbname (str): Database name.
    """

    def __init__(self, cnfg):

        # Display parameters
        settings = cnfg['settings']
        self.language = settings['language'] if settings['language'] else 'en'
        self.logo = settings['logo']

        # Database parameters
        database = settings['database']
        self.driver = database['odbc_driver']
        self.server = database['odbc_server']
        self.port = database['odbc_port']
        self.dbname = database['database']
        self.prog_db = database['rem_database']
        try:
            self.alt_dbs = database['alternative_databases']
        except KeyError:
            self.alt_dbs = []

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

class AuditRules(ProgramSettings):
    """
    Class to store and manage program configuration settings.

    Arguments:

        cnfg: parsed YAML file.

    Attributes:

        audit_rules (list): List of AuditRule objects.
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
        return([i.name for i in self.rules])

    def fetch_rule(self, name):
        """
        """
        rule_names = self.print_rules()
        try:
            index = rule_names.index(name)
        except IndexError:
            print('Rule {NAME} not in list of configured audit rules. '\
                  'Available rules are {ALL}'\
                  .format(NAME=name, ALL=', '.join(self.print_rules())))
            rule = None
        else:
            rule = self.rules[index] 

        return(rule)


class AuditRule:
    """
    """

    def __init__(self, name, adict):

        self.name = name
        self.element_key = lo.as_key(name)
        try:
            self.permissions = adict['Permissions']
        except KeyError:  #default permission for an audit is 'user'
            self.permissions = 'user'

        self.parameters = []
        self.tabs = []
        self.elements = ['TG', 'Cancel', 'Start', 'Finalize']

        try:
            params = adict['RuleParameters']
        except KeyError:
            msg = 'Configuration Error: the rule parameter "RuleParameters" '\
                  'is required for rule {}'.format(name)
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

        try:
            tdict = adict['Tabs']
        except KeyError:
            msg = 'Configuration Error: the rule parameter "Tabs" is required '\
                  'for rule {}'.format(name)
            win2.popup_error(msg)
            sys.exit(1)

        for tab_name in tdict:
            self.tabs.append(lo.TabItem(name, tab_name, tdict[tab_name]))

        try:
            summary = adict['Summary']
        except KeyError:
            msg = 'Configuration Error: the rule parameter "Summary" is '\
                  'required for rule {}'.format(name)
            win2.popup_error(msg)
            sys.exit(1)

        self.summary = SummaryPanel(name, summary)

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
        bttn_layout = [lo.B2('Cancel', key=cancel_key, pad=((0, pad_el), (pad_v, 0)),
                         tooltip='Cancel current action'),
                       lo.B2('Start', key=start_key, pad=((pad_el, 0), (pad_v, 0)),
                         tooltip='Start audit', bind_return_key=True),
                         sg.Text(' ' * 224, pad=(0, (pad_v, 0))),
                       lo.B2('Finalize', key=report_key, pad=(0, (pad_v, 0)),
                         disabled=True,
                         tooltip='Finalize audit and generate summary report')]
        layout_els.append(bttn_layout)

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


class SummaryPanel:
    """
    """

    def __init__(self, rule_name, sdict):

        self.rule_name = rule_name
        self.element_key = lo.as_key('{} Summary'.format(rule_name))
        try:
            self.title = sdict['Title']
        except KeyError:
            self.title = 'Summary'

        try:
            self.table = sdict['DatabaseTable']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}: Summary missing '\
                   'required field "DatabaseTable".').format(RULE=rule_name)
            win2.popup_error(msg)
            sys.exit(1)

        try:
            all_columns = sdict['TableColumns']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}: Summary missing '\
                   'required field "TableColumns".').format(RULE=rule_name)
            win2.popup_error(msg)
            sys.exit(1)
        else:
            self.db_columns = all_columns

        try:
            display_columns = sdict['DisplayColumns']
        except KeyError:
            msg = _('Configuration Error: rule {RULE}, Summary: missing '\
                   'required parameter "DisplayColumns".').format(RULE=rule_name)
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
            in_cols = sdict['MappingColumns'] 
        except KeyError:
            in_cols = []
        self.input_columns = in_cols

        if not map_cols and not in_cols:
            msg = _('Configuration Error: rule {RULE}, Summary: one or both of '\
                    'parameters "MappingColumns" and "InputColumns" are required.')\
                    .format(RULE=rule_name)
            win2.popup_error(msg)
            sys.exit(1)

        try:
            self.aliases = sdict['Aliases']
        except KeyError:
            self.aliases = []

    def layout(self, params):
        """
        Generate a GUI layout for the Audit Rule Summary.
        """
        # Layout settings
        bg_col = const.ACTION_COL
        pad_frame = const.FRAME_PAD
        pad_el = const.ELEM_PAD
        pad_v = const.VERT_PAD
        inactive_col = const.INACTIVE_COL
        bg_col = const.ACTION_COL
        default_col = const.DEFAULT_COL
        text_col = const.TEXT_COL
        font_h = const.HEADER_FONT

        audit_name = self.rule_name

        # Layout elements
        layout_els = [[sg.Col([[sg.Text(audit_name, pad=(0, (pad_v, pad_frame)),
                         font=font_h)]], justification='c', 
                         element_justification='c')]]

        # Rule parameter elements
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

        # Main screen
        tbl_layout = []
        summ_layout = [[sg.Col([[sg.Text(self.title, font=font_h)]],
                          pad=(0, pad_v), justification='center', background_color=bg_col)],
                       [sg.Frame('', [tbl_layout],
                          background_color=bg_col, element_justification='c',
                          pad=(pad_frame, pad_frame))],
                       [sg.Col(bttn_layout, justification='c',
                          pad=(0, (0, pad_frame)))]]

        # Control buttons
        b1_key = lo.as_key('{} Summary Cancel'.format(audit_name))
        b2_key = lo.as_key('{} Summary Back'.format(audit_name))
        b3_key = lo.as_key('{} Summary Save'.format(audit_name))
        bttn_layout = [[lo.B2(_('Cancel'), key=b1_key,
                          tooltip=_('Cancel save'), pad=(pad_el, 0)),
                        lo.B2(_('Back'), key=b2_key,
                          tooltip=_('Back to transactions'), pad=(pad_el, 0)), 
                        sg.Text(' ' * 224, pad=(0, (pad_v, 0))),
                        lo.B2(_('Save'), bind_return_key=True, key=b3_key,
                            tooltip=_('Save summary'), pad=(0, (pad_v, 0))]]

        layout_els.append(bttn_layout)

        # Pane elements must be columns
        layout = sg.Col(layout_els, key=self.element_key, visible=False)

        return(layout)


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

        desc = '{}:'.format(self.description)

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

    def values_set(self):
        """
        Check whether all values attributes have been set with correct 
        formatting.
        """
        value = self.value_raw

        input_date = value.replace('-', '')
        if input_date and len(input_date) == 8:
            return(True)
        else:
            return(False)

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


class DataBase(ProgramSettings):
    """
    Primary database object for querying databases and initializing 
    authentication.
    """

    def authenticate(self, uid, pwd):
        """
        Query database to validate sign-on and obtain user group information.

        Arguments:

            uid (str): Account user name.

            pwd (str): Account password.
        """
        conn = self.db_connect(uid, pwd, self.prog_db)

        cursor = conn.cursor()

        # Priveleages
        query_str = 'SELECT UID, PWD, UserGroup FROM Users WHERE UID = ?'
        try:
            cursor.execute(query_str, (uid,))
        except pyodbc.Error as e:
            print('DB Error: querying Users table from {DB} failed due to {EX}'\
                .format(DB=self.prog_db, EX=e))
            raise

        results = cursor.fetchall()
        for row in results:
            if row.uid == uid:
                ugroup = row.usergroup
                break

        cursor.close()
        conn.close()

        return(ugroup)

    def db_connect(self, uid, pwd, database=None):
        """
        Generate a pyODBC Connection object
        """
        driver = self.driver
        server = self.server
        port = self.port
        dbname = database if database else self.dbname

        db_settings = {'Driver': driver, 
                       'Server': server, 
                       'Database': dbname, 
                       'Port': port, 
                       'UID': uid, 
                       'PASS': pwd,
                       'Trusted_Connection': 'yes'}

        conn_str = ';'.join(['{}={}'.format(k, db_settings[k]) for k in \
                db_settings if db_settings[k]])

        try:
            conn = pyodbc.connect(conn_str)
        except pyodbc.Error as e:
            print('DB Error: connection to {DB} failed due to {EX}'\
                .format(DB=dbname, EX=e))
            raise

        return(conn)


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
