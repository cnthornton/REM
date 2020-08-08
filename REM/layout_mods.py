import PySimpleGUI as sg

# GUI Element Functions
def B1(*args, **kwargs):
    """
    Action button element defaults.
    """
    return(sg.Button(*args, **kwargs, size=(20, 1)))

def B2(*args, **kwargs):
    """
    Panel button element defaults.
    """
    return(sg.Button(*args, **kwargs, size=(6, 1)))
