"""
REM settings initializer
"""

import PySimpleGUI as sg
import os
import REM.program_constants as const
import REM.program_settings as prog_sets
import sys
import textwrap
import yaml


def popup_error(msg):
    """
    Display popup notifying user that there is a fatal program error.
    """
    font = const.MID_FONT
    return sg.popup_error(textwrap.fill(msg, width=40), font=font, title='')


# Global configuration settings
dirname = os.path.dirname(os.path.realpath(__file__))
cnfg_file = os.path.join(dirname, 'settings.yaml')

try:
    fh = open(cnfg_file, 'r', encoding='utf-8')
except FileNotFoundError:
    msg = 'Unable to load configuration file'
    popup_error(msg)
    sys.exit(1)
else:
    cnfg = yaml.safe_load(fh)
    fh.close()
    del fh

settings = prog_sets.ProgramSettings(cnfg)
