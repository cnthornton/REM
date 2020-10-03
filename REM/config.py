"""
REM settings initializer
"""

import PySimpleGUI as sg
import os
import REM.constants as const
import REM.settings as prog_sets
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
cnfg_name = 'settings.yaml'

# Determine if application is a script file or frozen exe
if getattr(sys, 'frozen', False):
    dirname = os.path.dirname(sys.executable)
elif __file__:
    dirname = os.path.dirname(__file__)

cnfg_file = os.path.join(dirname, cnfg_name)

try:
    fh = open(cnfg_file, 'r', encoding='utf-8')
except FileNotFoundError:
    msg = 'Unable to load configuration file at {}'.format(cnfg_file)
    popup_error(msg)
    sys.exit(1)
else:
    cnfg = yaml.safe_load(fh)
    fh.close()
    del fh

settings = prog_sets.ProgramSettings(cnfg, dirname)
