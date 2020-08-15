"""
REM Layout classes and functions.
"""
import PySimpleGUI as sg
import numpy as np
import pandas as pd
import REM.program_settings as const
import REM.secondary_win as win2


### Placeholder functions ###
def scan_for_missing(params, filters):
    """
    Scan database for missing transaction numbers.
    """
    header = params['columns']
    df = pd.DataFrame(np.random.randint(0, 100, size=(5, 10)), columns=header)

    return(df)
###

# Schema Layout Classes
class Schema:
    def __init__(self, rule_name, name, tdict):
        self.name = name
        element_name = "{RULE} {TAB}".format(RULE=rule_name, TAB=name)
        self.element_name = element_name
        self.element_key = as_key(element_name)
        self.type = tdict['layout_schema']
        columns = tdict['columns']
        self.db_columns = columns
        self.db_key = tdict['key']
        self.db_name = tdict['database']
        self.db_table = tdict['table']
        self.df = pd.DataFrame(empty_data_table(nrow=20, ncol=len(columns)), columns=columns)
        self.data_elements = ['Table', 'Summary']

        self.action_elements = ['Next']

    def update(self, window, element_tup):
        """
        """
        for element, new_param in element_tup:
            element_key = self.key_lookup(element)
            if element_key:
                expression = "window['{}'].update({})"\
                    .format(element_key, new_param)
                eval(expression)

                print('Updated element {} in {} to {}'\
                    .format(element, self.name, new_param))

    def update_table(self, window):
        """
        Update Table element with data
        """
        data = self.df.values.tolist()

        tbl_key = self.key_lookup('Table')
        window[tbl_key].update(values=data)

    def update_summary(self, window):
        """
        Update Summary element with data summary
        """
        df = self.df
        headers = df.columns.values.tolist()

        output = []
        # Determine object type of the values in each column
        for i, column in enumerate(headers):
            dtype = df.dtypes[column]
            if dtype == np.int64:
                col_summary = '{}: {}'.format(column, str(df[column].sum()))
            elif dtype == np.object:
                col_summary = '{}: {}'.format(column, str(df[column].value_counts()))

            output.append(col_summary)

        final_output = '\n'.join(output)
        summary_key = self.key_lookup('Summary')
        window[summary_key].update(value=final_output)

    def key_lookup(self, element):
        """
        Lookup key for element in schema.
        """
        elements = self.data_elements + self.action_elements
        if element in elements:
            key = as_key('{} {}'.format(self.name, element))
        else:
            key = None

        return(key)

    def toggle_action_buttons(self, window, value='enable'):
        """
        Enable / Disable schema action buttons.
        """
        status = False if value == 'enable' else True

        element_tup = []
        for element in self.action_elements:
            element_tup.append((element, 'disabled={}'.format(status)))
        
        self.update(window, element_tup)

    def layout(self, admin:bool=False):
        """
        Tab schema for layout type 'reviewable'.
        """
        # Window and element size parameters
        bg_col = const.ACTION_COL
        default_col = const.DEFAULT_COL

        pad_frame = const.FRAME_PAD
        pad_el = const.ELEM_PAD

        frozen = False if admin else True

        header = self.df.columns.values.tolist()
        data = self.df.values.tolist()

        summary_key = self.key_lookup('Summary')
        next_key = self.key_lookup('Next')
        table_key = self.key_lookup('Table')
        layout = [[create_table(data, header, table_key)],
                  [sg.Text('Summary', pad=((pad_frame, 0), pad_el),
                     background_color=bg_col),
                   sg.Text(' ' * 180, pad=((pad_frame, 0), pad_el),
                     background_color=bg_col),
                   B2('Next', key=next_key, pad=((0, pad_el), pad_el),
                     disabled=True, tooltip='Move to next tab')],
                  [sg.Multiline('', pad=((pad_frame, 0), (pad_el, pad_frame)),
                     size=(50, 8), key=summary_key, disabled=True, 
                     background_color=default_col)],
                  [sg.Text('', pad=(pad_frame, 0), background_color=bg_col)]]

        return(layout)

    def fetch_db_params(self):
        params = {'name': self.db_name, 
                  'table': self.db_table, 
                  'key': self.db_key, 
                  'columns': self.db_columns}

        return(params)

    def run_action(self, *args, **kwargs):
        pass


class SchemaScanable(Schema):
    def __init__(self, rule_name, name, tdict):
        super().__init__(rule_name, name, tdict)
        self.action_elements = ['Scan']

    def layout(self, admin:bool=False):
        """
        Tab schema for layout type 'scanable'.
        """
        # Window and element size parameters
        bg_col = const.ACTION_COL
        default_col = const.DEFAULT_COL

        pad_frame = const.FRAME_PAD
        pad_el = const.ELEM_PAD

        frozen = False if admin else True

        header = self.df.columns.values.tolist()
        data = self.df.values.tolist()

        summary_key = self.key_lookup('Summary')
        scan_key = self.key_lookup('Scan')
        table_key = self.key_lookup('Table')
        layout = [[create_table(data, header, table_key)],
                  [sg.Text('Summary', pad=((pad_frame, 0), pad_el),
                     background_color=bg_col),
                   sg.Text(' ' * 180, pad=((pad_frame, 0), pad_el),
                     background_color=bg_col),
                   B2('Scan', key=scan_key, pad=((0, pad_el), pad_el),
                     disabled=True, tooltip='Scan for missing data')],
                  [sg.Multiline('', size=(50, 8), background_color=default_col,
                     disabled=True, pad=((pad_frame, 0), (pad_el, 0)), 
                     key=summary_key)],
                  [sg.Text('', pad=(pad_frame, 0), background_color=bg_col)]]

        return(layout)

    def run_action(self, *args, **kwargs):
        """
        Search for missing orders using scan.
        """
        db = kwargs['database']
        
        # Search for missing data
        params = self.fetch_db_params()
        filters = None
#        missing_data = db.query(params, filters)
        missing_data = scan_for_missing(params, filters)

        # Display import window with potentially missing data
        import_data = win2.import_window(missing_data, db, params)

        # Updata dataframe with imported data
        df = self.df.append(import_data, ignore_index=True, sort=True)
        df.sort_values(by=[self.db_key], inplace=True, ascending=True)
        self.df = df
        print('New size of {0} dataframe is {1} rows and {2} columns'\
            .format(self.name, *df.shape))

        return(df)


class SchemaVerifiable(Schema):
    def __init__(self, rule_name, name, tdict):
        super().__init__(rule_name, name, tdict)
        self.action_elements = ['Confirm']
        self.verified = []

    def layout(self, admin:bool=False):
        """
        GUI layout for schema type 'verifiable'.
        """
        # Window and element size parameters
        bg_col = const.ACTION_COL
        default_col = const.DEFAULT_COL

        pad_v = const.VERT_PAD
        pad_h = const.HORZ_PAD
        pad_el = const.ELEM_PAD
        pad_frame = const.FRAME_PAD
        tbl_height = const.TBL_HEIGHT
        nrow = const.TBL_NROW
        tt = 'Select all of the rows that should be confirmed'

        frozen = False if admin else True

        header = self.df.columns.values.tolist()
        data = self.df.values.tolist()

        summary_key = self.key_lookup('Summary')
        confirm_key = self.key_lookup('Confirm')
        table_key = self.key_lookup('Table')
        layout = [[create_table(data, header, table_key, bind=True, tooltip=tt)],
                  [sg.Text('Summary', pad=((pad_frame, 0), pad_el),
                     background_color=bg_col),
                   sg.Text(' ' * 180, pad=((pad_frame, 0), pad_el),
                     background_color=bg_col),
                   B2('Confirm', key=confirm_key, pad=((0, pad_el), pad_el),
                     disabled=True, tooltip='Confirm selection')],
                  [sg.Multiline('', size=(50, 8), background_color=default_col,
                     disabled=True, pad=((pad_frame, 0), (pad_el, 0)), 
                     key=summary_key)],
                  [sg.Text('', pad=(pad_frame, 0), background_color=bg_col)]]

        return(layout)

    def verify_row(self, row_index):
        """
        Add row to verified list, returning list of updated row colors.
        """
        tbl_bg_col = const.TBL_BG_COL
        tbl_alt_col = const.TBL_ALT_COL
        tbl_vfy_col = const.TBL_VFY_COL

        if row_index != None and row_index not in self.verified:
            self.verified.append(row_index)  #add row to list of verified

        elif row_index != None and row_index in self.verified:
            self.verified.remove(row_index)  #remove row from list of verified

        # Get row colors for rows that have been selected
        print('Selected orders are {}'.format(', '.join([str(i) for i in self.verified])))
        selected = [(i, tbl_vfy_col) for i in self.verified]

        # Get row colors for rows that have not been selected
        unselected = []
        for index in range(self.df.shape[0]):  #all rows in dataframe
            if index not in self.verified:
                if index % 2 == 0:
                    color = tbl_bg_col
                else:
                    color = tbl_alt_col
                    
                unselected.append((index, color))

        # Update table row colors
        all_row_colors = selected + unselected

        return(all_row_colors)

    def run_action(self, *args, **kwargs):
        """
        Confirm selected orders.
        """
        # Filter dataframe using list of verified
        verified = self.verified
        if len(verified) != self.df.shape[0]:
            selection = win2.confirm_action("Not all rows have been selected "
                    "for importing. Are you sure you would like to continue?")
            if selection == 'OK':  #continue anyway
                final_df = self.df.iloc[verified]
                print('The following rows were selected from {}:\n{}'\
                    .format(self.name, final_df))
            else:
                final_df = self.df

        # Modify attributes to reflect selection
        self.df = final_df
        self.verified = []

        return(final_df)


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

def control_layout_dropdown(rule_name, ctrl_name, params):
    """
    Dropdown menu control elements.
    """
    pad_el = const.ELEM_PAD
    pad_v = const.VERT_PAD

    key = as_key('{} {}'.format(rule_name, ctrl_name))
    desc = params['desc']
    values = params['values']
    width = max([len(i) for i in values]) + 10

    layout = [sg.Text(desc, pad=((0, pad_el), (0, pad_v))),
              sg.Combo(values, key=key, enable_events=True, 
                size=(width, 1), pad=(0, (0, pad_v)))]

    return(layout)

def control_layout_date(rule_name, ctrl_name, params):
    """
    """
    pad_el = const.ELEM_PAD
    pad_v = const.VERT_PAD
    date_ico = const.CALENDAR_ICON

    key = as_key('{} {}'.format(rule_name, ctrl_name))
    desc = params['desc']

    layout = [sg.Text(desc, pad=((0, pad_el), (0, pad_v))),
              sg.Input('', key=key, size=(16, 1), enable_events=True,
                 pad=((0, pad_el), (0, pad_v)), 
                 tooltip='Input date as YYYY-MM-DD or use the calendar ' \
                         'button to select the date'),
               sg.CalendarButton('', format='%Y-%m-%d', image_data=date_ico, 
                 border_width=0, size=(2, 1), pad=(0, (0, pad_v)), 
                 tooltip='Select date from calendar menu')]

    return(layout)

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

    layout = sg.Table(data, headings=header, pad=(pad_frame, (pad_frame, pad_el)),
               key=keyname, row_height=height, alternating_row_color=alt_col,
               text_color=text_col, selected_row_colors=(text_col, select_col), 
               background_color=bg_col, num_rows=nrows,
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
                   [B1('Update Database', pad=(pad_frame, pad_el), 
                      key='-DB-', disabled=True)],
                   [sg.HorizontalSeparator(pad=(pad_frame, pad_v))],
                   [B1('Summary Statistics', pad=(pad_frame, pad_el), 
                      key='-STATS-', disabled=True)],
                   [B1('Summary Reports', pad=(pad_frame, pad_el), 
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
