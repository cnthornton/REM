"""
REM configuration settings.
"""

import dateutil
import gettext
import os
import PySimpleGUI as sg
import REM.constants as const
import sys


class ProgramSettings:
    """
    Class to store and manage program configuration settings.

    Arguments:

        cnfg: Parsed YAML file

    Attributes:

        language (str): Display language. Default: EN.
    """

    def __init__(self, cnfg, dirname):
        self.dirname = dirname

        # Supported locales
        self._locales = ['en_US', 'en_UK', 'th_TH']

        try:
            settings = cnfg['settings']
        except KeyError:
            print('Error: the "settings" parameter is a required field')
            sys.exit(1)

        # User parameters
        try:
            self.username = settings['user']['username']
        except KeyError:
            self.username = 'username'

        # Localization parameters
        try:
            self.language = settings['localization']['language']
        except KeyError:
            self.language = 'en'
        try:
            cnfg_locale = settings['localization']['locale']
        except KeyError:
            cnfg_locale = 'en_US'
        self.locale = cnfg_locale if cnfg_locale in self._locales else 'en_US'
        self.localedir = os.path.join(dirname, 'locale')
        self.domain = 'base'

        self.translation = self.change_locale()
        self.translation.install('base')  # bind gettext to _() in __builtins__ namespace

        # Display parameters
        try:
            logo_name = settings['display']['logo']
        except KeyError:
            logo_file = os.path.join(dirname, 'docs', 'images', 'logo.png')
        else:
            if not logo_name:
                logo_file = os.path.join(dirname, 'docs', 'images', 'logo.png')
            else:
                logo_file = os.path.join(dirname, 'docs', 'images', logo_name)

        try:
            fh = open(logo_file, 'r', encoding='utf-8')
        except FileNotFoundError:
            self.logo = None
        else:
            self.logo = logo_file
            fh.close()

        try:
            report_template = settings['display']['report_template']
        except KeyError:
            self.report_template = os.path.join(dirname, 'templates', 'report.html')
        else:
            if not report_template:
                self.report_template = os.path.join(dirname, 'templates', 'report.html')
            else:
                self.report_template = report_template

        try:
            report_style = settings['display']['report_stylesheet']
        except KeyError:
            self.report_css = os.path.join(dirname, 'static', 'css', 'report.css')
        else:
            if not report_style:
                self.report_css = os.path.join(dirname, 'static', 'css', 'report.css')
            else:
                self.report_css = report_style

        # Dependencies
        try:
            wkhtmltopdf = settings['dependencies']['wkhtmltopdf']
        except KeyError:
            self.wkhtmltopdf = os.path.join(dirname, 'data', 'wkhtmltopdf', 'bin', 'wkhtmltopdf.exe')
        else:
            if not wkhtmltopdf:
                self.wkhtmltopdf = os.path.join(dirname, 'data', 'wkhtmltopdf', 'bin', 'wkhtmltopdf.exe')
            else:
                self.wkhtmltopdf = wkhtmltopdf

        # Database parameters
        ddict = settings['database']
        self.driver = ddict['odbc_driver']
        self.server = ddict['odbc_server']
        self.port = ddict['odbc_port']
        self.dbname = ddict['database']
        self.prog_db = ddict['rem_database']
        self.date_format = ddict['date_format']
        try:
            self.alt_dbs = ddict['alternative_databases']
        except KeyError:
            self.alt_dbs = []

    def translate(self):
        """
        Translate text using language defined in settings.
        """

    def edit_attribute(self, attr, value):
        """
        Modify a settings attribute.
        """
        if attr == 'language':
            self.language = value
        elif attr == 'locale':
            self.locale = value
        elif attr == 'template':
            self.report_template = value
        elif attr == 'css':
            self.report_css = value
        elif attr == 'port':
            self.port = value
        elif attr == 'server':
            self.server = value
        elif attr == 'driver':
            self.driver = value
        elif attr == 'dbname':
            self.dbname = value

    def layout(self):
        """
        Generate GUI layout for the settings window.
        """
        width = 800

        # Window and element size parameters
        main_font = const.MAIN_FONT

        pad_el = const.ELEM_PAD
        pad_v = const.VERT_PAD
        pad_frame = const.FRAME_PAD
        in_size = 18
        spacer = (12, 1)
        dd_size = 8

        bg_col = const.ACTION_COL
        in_col = const.INPUT_COL

        bwidth = 0.5
        select_col = const.SELECT_TEXT_COL

        layout = [[sg.Frame('Localization', [
                      [sg.Canvas(size=(width, 0), pad=(0, pad_v), visible=True, background_color=bg_col)],
                      [sg.Text('Language:', size=(15, 1), pad=((pad_frame, pad_el), pad_el), font=main_font,
                               background_color=bg_col),
                       sg.Combo(list(set([i.split('_')[0] for i in self._locales])), key='-LANGUAGE-',
                                size=(dd_size, 1),
                                pad=(pad_el, pad_el), default_value=self.language, auto_size_text=False,
                                background_color=in_col)],
                      [sg.Text('Locale:', size=(15, 1), pad=((pad_frame, pad_el), pad_el), font=main_font,
                               background_color=bg_col),
                       sg.Combo(self._locales, key='-LOCALE-', size=(dd_size, 1), pad=(pad_el, pad_el),
                                default_value=self.locale,
                                auto_size_text=False, background_color=in_col)],
                      [sg.Canvas(size=(800, 0), pad=(0, pad_v), visible=True, background_color=bg_col)]],
                            pad=(pad_frame, pad_frame), border_width=bwidth, background_color=bg_col,
                            title_color=select_col, relief='groove')],
                  [sg.Frame('Display', [
                      [sg.Canvas(size=(width, 0), pad=(0, pad_v), visible=True, background_color=bg_col)],
                      [sg.Text('Report template:', size=(15, 1), pad=((pad_frame, pad_el), pad_el),
                               font=main_font, background_color=bg_col),
                       sg.Input(self.report_template, key='-TEMPLATE-', size=(60, 1),
                                pad=(pad_el, pad_el), font=main_font, background_color=in_col),
                       sg.FileBrowse('Browse...', pad=((pad_el, pad_frame), pad_el))],
                      [sg.Text('Report stylesheet:', size=(15, 1), pad=((pad_frame, pad_el), pad_el),
                               font=main_font, background_color=bg_col),
                       sg.Input(self.report_css, key='-CSS-', size=(60, 1), pad=(pad_el, pad_el),
                                font=main_font, background_color=in_col),
                       sg.FileBrowse('Browse...', pad=((pad_el, pad_frame), pad_el))],
                      [sg.Canvas(size=(800, 0), pad=(0, pad_v), visible=True, background_color=bg_col)]],
                  pad=(pad_frame, pad_frame), border_width=bwidth, background_color=bg_col,
                            title_color=select_col, relief='groove')],
                  [sg.Frame('Database', [
                      [sg.Canvas(size=(width, 0), pad=(0, pad_v), visible=True, background_color=bg_col)],
                      [sg.Text('ODBC port:', size=(15, 1), pad=((pad_frame, pad_el), pad_el),
                               font=main_font, background_color=bg_col),
                       sg.Input(self.port, key='-PORT-', size=(in_size, 1), pad=((pad_el, pad_frame), pad_el),
                                font=main_font, background_color=in_col),
                       sg.Text('', size=spacer, background_color=bg_col),
                       sg.Text('ODBC server:', size=(15, 1), pad=((pad_frame, pad_el), pad_el), font=main_font,
                               background_color=bg_col),
                       sg.Input(self.server, key='-SERVER-', size=(in_size, 1), pad=((pad_el, pad_frame), pad_el),
                                font=main_font, background_color=in_col)],
                      [sg.Text('ODBC driver:', size=(15, 1), pad=((pad_frame, pad_el), pad_el),
                               font=main_font, background_color=bg_col),
                       sg.Input(self.driver, key='-DRIVER-', size=(in_size, 1), pad=((pad_el, pad_frame), pad_el),
                                font=main_font, background_color=in_col),
                       sg.Text('', size=spacer, background_color=bg_col, pad=(0, pad_el)),
                       sg.Text('Database:', size=(15, 1), pad=((pad_frame, pad_el), pad_el), font=main_font,
                               background_color=bg_col),
                       sg.Combo(self.alt_dbs, default_value=self.dbname, key='-DATABASE-', size=(in_size-1, 1),
                                pad=((pad_el, pad_frame), pad_el), font=main_font, background_color=in_col)],
                      [sg.Canvas(size=(800, 0), pad=(0, pad_v), visible=True, background_color=bg_col)]],
                            pad=(pad_frame, pad_frame), border_width=bwidth, background_color=bg_col,
                            title_color=select_col, relief='groove')]]

        return layout

    def change_locale(self):
        """
        Translate application text based on supplied locale.
        """
        language = self.language
        localdir = self.localedir
        domain = self.domain

        if language not in [i.split('_')[0] for i in self._locales]:
            raise NameError

        try:
            trans = gettext.translation(domain, localedir=localdir, languages=[language])
        except Exception:
            print('Unable to find translations for locale {}'.format(language))
            trans = gettext

        return trans

    def format_date_str(self, date_str: str = None):
        """
        """
        separators = set(':/- ')
        date_fmts = {'YYYY': '%Y', 'YY': '%y',
                     'MMMM': '%B', 'MMM': '%b', 'MM': '%m', 'M': '%-m',
                     'DD': '%d', 'D': '%-d',
                     'HH': '%H', 'MI': '%M', 'SS': '%S'}

        date_str = date_str if date_str else self.date_format

        strfmt = []

        last_char = date_str[0]
        buff = [last_char]
        for char in date_str[1:]:
            if char not in separators:
                if last_char != char:
                    # Check if char is first in a potential series
                    if last_char in separators:
                        buff.append(char)
                        last_char = char
                        continue

                    # Check if component is minute
                    if ''.join(buff + [char]) == 'MI':
                        strfmt.append(date_fmts['MI'])
                        buff = []
                        last_char = char
                        continue

                    # Add characters in buffer to format string and reset buffer
                    component = ''.join(buff)
                    strfmt.append(date_fmts[component])
                    buff = [char]
                else:
                    buff.append(char)
            else:
                component = ''.join(buff)
                try:
                    strfmt.append(date_fmts[component])
                except KeyError:
                    if component:
                        print('Warning: unknown component {} provided to date string {}.'.format(component, date_str))
                        raise

                strfmt.append(char)
                buff = []

            last_char = char

        try:  # format final component remaining in buffer
            strfmt.append(date_fmts[''.join(buff)])
        except KeyError:
            print('Warning: unsupported characters {} found in date string {}'.format(''.join(buff), date_str))
            raise

        return ''.join(strfmt)

    def get_date_offset(self):
        """
        Find date offset for calendar systems other than the gregorian calendar
        """
        locale = self.locale

        if locale == 'th_TH':
            offset = 543
        else:
            offset = 0

        return offset

    def apply_date_offset(self, dt):
        """
        Apply date offset to a datetime object
        """
        relativedelta = dateutil.relativedelta.relativedelta

        offset = self.get_date_offset()
        dt_mod = dt + relativedelta(years=+offset)

        return dt_mod
