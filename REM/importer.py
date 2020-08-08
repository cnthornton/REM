"""Contains the functions for importing missing transactions
"""
import data_access as db
import layout_mods as lm
import PySimpleGUI as sg


# General functions
#def return_order(transaction, col_num):
def return_order(transaction):
#    return(transaction[col_num])
    return(transaction[1])

def confirm_action(msg):
    """Ask user if they would really like to continue without completing
    whatever action is currently being undertaken.
    """
    return(sg.popup_ok_cancel(msg, title='', font=('Arial', 11)))

# Layout Functions
def listbox_layout(height:int=38, width:int=20):
    """
    Return listbox layout for column with the orders to import.
    """
    layout = [[sg.Listbox(values=[], enable_events=False, \
                 bind_return_key=True, size=(width, height), key='-ORDERS-',
                 tooltip='Double-click an order to remove from the list')]]

    return(layout)

# Window function
def import_window(df, win_size:tuple=(1920, 1080)):
    """
    Display the transaction importer window.
    """
    # Format dataframe as list for input into sg
    data = df.values.tolist()
    header = df.columns.values.tolist()

    # Transaction information
    order_nums = [return_order(i) for i in data]

    # Window and element size parameters
    tbl_height = 30 #height of rows in pixels
    nrow = 10
    lb_height = round(nrow * tbl_height / 17)
    lb_width = 20
    pad_v = 10
    pad_el = 2

    # Layouts not in a function
    button_col_layout = [[lm.B2('Cancel', tooltip='Cancel import', pad=(2, 10)), 
                          lm.B2('Import', bind_return_key=True, key='-IMPORT-',
                            tooltip='Import the selected transaction orders', pad=(2,10))]]

    add_row = [sg.Text('Include order:', pad=((pad_v, pad_el), pad_v), 
                 tooltip='Input order number to add the order to the table'),
               sg.Input('', key='-INPUT-', pad=(pad_el, pad_v)),
               lm.B2('Add', pad=(pad_el, pad_v), tooltip='Add order to the table', key='-ADD-')]

#    frame_layout = [[sg.Col(listbox_layout(height=lb_height, width=lb_width),
#                       key='-COL1-', scrollable=False, pad=(10, 10)),
#                     sg.Col([[db.create_table(data, header, 'IMPORT', 
#                       bind=True, nrow=nrow, height=tbl_height)], add_row], 
#                       scrollable=False, key='-COL2-', pad=(10, 10))]]

#    layout = [[sg.Text('Import Missing Transactions', justification='center',
#                 font=('Arial', 12, 'bold'), pad=(10, 10))],
#              [sg.Frame('', frame_layout, key='-FRAME-',
#                 element_justification='center', pad=(20, 20))],
#              [sg.Col(button_col_layout, justification='right', pad=(10, 10))]]
    layout = [[sg.Text('Import Missing Transactions', justification='center',
                 font=('Arial', 12, 'bold'), pad=(40, pad_v))],
              [sg.Col(listbox_layout(height=lb_height, width=lb_width),
                 key='-COL1-', scrollable=False, pad=((40, 5), pad_v)),
               sg.Col([[db.create_table(data, header, 'IMPORT', 
                 bind=True, nrow=nrow, height=tbl_height)], add_row], 
                 scrollable=False, key='-COL2-', pad=((5, 20), pad_v))],
              [sg.Col(button_col_layout, justification='right', pad=((0, 40), pad_v))]]

    window = sg.Window('Import Data', layout, font=('Arial', 12))

    vfy_orders = []

    # Start event loop
    while True:
        event, values = window.read()
        print(event, values)

        if event in (sg.WIN_CLOSED, 'Cancel'):  #selected close-window or Cancel
            break

        if event == '-IMPORT_TABLE-':  #double-clicked on row in table
            trans = return_order(data[values['-IMPORT_TABLE-'][0]])
            if trans not in vfy_orders:
                vfy_orders.append(trans)
            window['-ORDERS-'].update(vfy_orders)

        if event == '-ORDERS-':  #double-clicked on item in listbox
            # Obtain value of listbox event
            try:
                import_trans = values['-ORDERS-'][0]
            except IndexError:  #selected new value too quickly for response
                continue

            # Remove order that was double-clicked from the listbox
            try:
                vfy_orders.remove(import_trans)
            except ValueError:  #somehow already missing
                print("Transaction {order} already missing from listbox"\
                    .format(order=import_trans))

            # Update listbox values to reflect changes
            window['-ORDERS-'].update(vfy_orders)

        if event == '-ADD-':  #clicked the 'Add' button
            # Extract order information from database
            new_order = values['-INPUT-']
            order_info = query_order(new_order)

            if not order_info:  #query returned nothing
                print("{} is not a valid order number".format(new_order))
                continue

            # Clear user input from Input element
            window['-INPUT-'].update(value='')

            # Add order information to table and checkbox column
            order_nums.append(new_order)
            data.append(order_info)
            window['-TABLE-'].update(values=data)

        if event == '-IMPORT-':  #click 'Import' button
            if len(data) != len(vfy_orders):  #not all orders selected
                selection = confirm_action("Not all transaction orders have "
                    "been selected for importing. Are you sure you would like "
                    "to continue?")
                if selection == 'OK':  #continue anyway
                    break
                else:  #oops, a mistake was made
                    continue
            else:  #all orders selected already
                break

    window.close()

    vfy_data = [i for i in data if return_order(i) in vfy_orders]

    return(vfy_data)
