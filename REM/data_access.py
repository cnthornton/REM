import PySimpleGUI as sg
import numpy as np
import pandas as pd
import pyodbc
import program_settings as const

# DB functions
def query(cnfg, user, ttype:str=None, date:str=None, branch:str=None):
    """
    Query database for the given order number.
    """

    # Database configuration settings
    dbname = cnfg.odbc_db
    server = cnfg.odbc_server
    driver = cnfg.odbc_driver

    try:
        colnames = cnfg.transactions[ttype]
    except KeyError:
        print('Cannot find information on table {} in configuration file'.format(ttype), file=sys.stderr)
        return(None)

    # User settings
    user.name
    user.password

    # Connect to database
    db_settings = 'Driver={DRIVER};Server={SERVER};Database={DB};UID={USER};' \
                  'PWD={PASS}'.format(DRIVER=driver, SERVER=server, DB=dbname, \
                                      USER=uid, PASS=pwd)

    conn = pyodbc.connect(db_settings)
    cursor = conn.cursor()

    query = 'SELECT {COLS} from {DB}.{TABLE} WHERE branch = {BRANCH} AND date = {DATE};'.format(COLS=colnames, DB=dbname, TABLE=ttype, BRANCH=branch, date=DATE)
#    query = (date, order, rand_str(), rand_int(), rand_int(), rand_int())

    df = pd.read_sql(conn, query)

    return(df)

def insert(cnfg, user, ttype:str=None):
    """
    Insert data into the daily summary table.
    """
    success = True
    return(success)

def create_table(data, header, keyname, bind=False, nrow:int=10, height:int=30):
    """
    Create table elements that have consistency in layout.
    """
    # Element settings
    text_color=const.TEXT_COL
    background_col = const.ACTION_COL
    tbl_size = 80
    pad_frame = 20
    pad_el = 2

    # Size of data
    lengths = [len(i) for i in header]
    header_size = sum(lengths)
    ncol = len(header)

    # When table columns not long enough, need to adjust so that the
    # table fills the empty space.
    if header_size < tbl_size:
        col_width = int(tbl_size / ncol)
        max_char_per_col = int(tbl_size / ncol)

        # Pad column headers with spaces until length at max size
        for index, length in enumerate(lengths):
            if length >= max_char_per_col:
                continue
            else:
                header[index] = header[index].center(max_char_per_col, ' ')

        # Check remaining space and add any remaining to first column
        remainder = tbl_size - sum([len(i) for i in header])
        header[0] = header[0].center(len(header[0]) + remainder, ' ')

    layout = sg.Table(data, headings=header, pad=(pad_frame, pad_el),
               key='-{}_TABLE-'.format(keyname.upper()),
               row_height=30, text_color=text_color,
               display_row_numbers=False, auto_size_columns=True,
               max_col_width=max_char_per_col, enable_events=False,
               vertical_scroll_only=False, bind_return_key=bind,
               alternating_row_color=background_col)

    return(layout)
