"""
REM configuration settings.
"""

import datetime
import gettext
import hashlib
import locale
import logging
import logging.handlers as handlers
import os
import socket
import struct
import sys
import textwrap
import time
from random import randint

import PySimpleGUI as sg
import dateutil
import pandas as pd
import yaml
from bson import json_util
from cryptography.fernet import Fernet

import REM.constants as mod_const


class SQLStatementError(Exception):
    """A simple exception that is raised when an SQL statement is formatted incorrectly.
    """

    def __init__(self, *args, **kwargs):
        Exception.__init__(self, *args)


class ServerConnection:
    def __init__(self, sock, addr):
        self.sock = sock
        self.addr = addr

        # Dynamic attributes
        self.request = None
        self._recv_buffer = b""
        self._send_buffer = b""
        self._request_queued = False
        self._ready_to_read = False
        self._header_len = None
        self.action = None
        self.header = None
        self.response = None

    def _reset(self):
        """
        Reset dynamic attributes.
        """
        self._recv_buffer = b""
        self._send_buffer = b""
        self._ready_to_read = False
        self._request_queued = False
        self._header_len = None
        self.action = None
        self.request = None
        self.header = None
        self.response = None

    def _reset_connection(self, timeout: int = 20):
        """
        Reset a lost connection to the server.
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except socket.error as e:
            msg = 'socket creation failed - {ERR}'.format(ERR=e)
            logger.error('{MSG}'.format(MSG=msg))
            raise
        else:
            sock.setblocking(False)

        self.sock = sock

        success = False
        start_time = time.time()
        sg.popup_animated(image_source=None)
        while time.time() - start_time < timeout:
            sg.popup_animated(mod_const.PROGRESS_GIF, time_between_frames=100, keep_on_top=True, alpha_channel=0.5)

            try:
                self.sock.connect(self.addr)
            except BlockingIOError:
                # Resource temporarily unavailable (errno EWOULDBLOCK)
                pass
            except socket.error:
                time.sleep(1)
            else:
                msg = 'connection accepted from server {ADDR}'.format(ADDR=self.addr)
                logger.info(msg)
                success = True

                break

        sg.popup_animated(image_source=None)
        if not success:
            raise TimeoutError('failed to reconnect to the server after {} seconds'.format(timeout))

    def _read(self):
        try:
            # Should be ready to read
            data = self.sock.recv(4096)
        except BlockingIOError:
            # Resource temporarily unavailable (errno EWOULDBLOCK)
            pass
        except ConnectionResetError:
            msg = 'connection to {ADDR} was closed for unknown reason ... attempting to reconnect' \
                .format(ADDR=self.addr)
            logger.error(msg)
            try:
                self._reset_connection()
            except (socket.error, TimeoutError) as e:
                msg = 'connection reset failed - {}'.format(e)
                logger.exception(msg)
                popup_error(msg)
        else:
            if data:  # 0 indicates a closed connection
                self._recv_buffer += data
            else:
                raise RuntimeError("Peer connection closed")

    def _write(self):
        if self._send_buffer:
            try:  # should be ready to write
                sent = self.sock.send(self._send_buffer)
            except BlockingIOError:  # resource temporarily unavailable (errno EWOULDBLOCK)
                pass
            except ConnectionResetError:
                msg = 'connection to {ADDR} was closed for unknown reason ... attempting to reconnect'\
                    .format(ADDR=self.addr)
                logger.error(msg)
                self._reset_connection()
            else:
                # Remove the sent portion of the message from the buffer
                self._send_buffer = self._send_buffer[sent:]

    def _encode(self, obj, encoding):
#        return json.dumps(obj, ensure_ascii=False).encode(encoding)
        return json_util.dumps(obj, ensure_ascii=False).encode(encoding)

    def _decode(self, json_bytes, encoding):
#        tiow = io.TextIOWrapper(
#            io.BytesIO(json_bytes), encoding=encoding, newline=""
#        )
#        obj = json.load(tiow)
#        tiow.close()
        obj = json_util.loads(json_bytes.decode(encoding))

        return obj

    def _create_message(self, *, content_bytes, content_encoding):
        jsonheader = {
            "byteorder": sys.byteorder,
            "content-encoding": content_encoding,
            "content-length": len(content_bytes),
        }
        jsonheader_bytes = self._encode(jsonheader, "utf-8")
        message_hdr = struct.pack(">H", len(jsonheader_bytes))
        message = message_hdr + jsonheader_bytes + content_bytes

        return message

    def process_request(self, request, timeout: int = 20):
        try:
            self.action = request['content']['action']
        except KeyError:
            msg = 'the request made to {} was formatted improperly'.format(settings.host)
            return {'success': False, 'value': msg}

        self.request = request

        start_time = time.time()
        while time.time() - start_time < timeout:
            if time.time() - start_time > 1:
                sg.popup_animated(mod_const.PROGRESS_GIF, time_between_frames=100, keep_on_top=True, alpha_channel=0.5)

            if self.response is not None:
                logger.debug('server process completed')
                result = self.response
                sg.popup_animated(image_source=None)
                break
            else:
                if self._ready_to_read:
                    try:
                        self.read()
                    except Exception as e:
                        msg = 'server request failed - {ERR}'.format(ERR=e)
                        result = {'success': False, 'value': msg}
                        sg.popup_animated(image_source=None)

                        break
                else:
                    try:
                        self.write()
                    except Exception as e:
                        msg = 'server request failed - {ERR}'.format(ERR=e)
                        result = {'success': False, 'value': msg}
                        sg.popup_animated(image_source=None)
                        logger.error(msg)

                        break
        else:
            msg = 'server failed to respond to request after {} seconds'.format(timeout)
            sg.popup_animated(image_source=None)
            result = {'success': False, 'value': msg}
            logger.error(msg)

        # Reset attributes for next event
        self._reset()

        return result

    def read(self):
        # Continuously read until no more data is received
        self._read()

        if self._header_len is None:
            # Check for header length within the first several bytes of the server response
            self.process_protoheader()

        if self._header_len is not None:
            if self.header is None:
                # Process the header once the length of the header is known
                self.process_header()

        if self.header:
            if self.response is None:
                self.process_response()

    def write(self):
        if not self._request_queued:
            # Queue the request for sending to the server
            self.queue_request()
            logger.info('sending request "{REQ}" to {ADDR}'.format(REQ=self.action, ADDR=self.addr))
#            logger.debug('request sent: {}'.format(self.request))

        # Continuously send the request until the send buffer is empty
        self._write()

        # Indicate that writing has finished once the send buffer is empty
        if self._request_queued:
            if not self._send_buffer:
                self._ready_to_read = True

    def close(self):
        logger.info("closing connection to {ADDR}".format(ADDR=self.addr))

        try:
            self.sock.close()
        except OSError as e:
            msg = 'unable to close socket connected to {ADDR} - {ERR}'.format(ADDR=self.addr, ERR=e)
            logger.error(msg)
        finally:
            # Delete reference to socket object for garbage collection
            self.sock = None

    def queue_request(self):
        content = self.request["content"]
        content_encoding = self.request["encoding"]
        req = {
            "content_bytes": cipher.encrypt(self._encode(content, content_encoding)),
            "content_encoding": content_encoding,
        }
        message = self._create_message(**req)
        self._send_buffer += message
        self._request_queued = True

    def process_protoheader(self):
        hdrlen = 2

        if len(self._recv_buffer) >= hdrlen:
            self._header_len = struct.unpack(">H", self._recv_buffer[:hdrlen])[0]
            self._recv_buffer = self._recv_buffer[hdrlen:]

    def process_header(self):
        hdrlen = self._header_len

        if len(self._recv_buffer) >= hdrlen:
            self.header = self._decode(self._recv_buffer[:hdrlen], "utf-8")
            self._recv_buffer = self._recv_buffer[hdrlen:]
            for reqhdr in ("byteorder", "content-length", "content-encoding"):
                if reqhdr not in self.header:
                    raise ValueError('missing required header component {COMP}'.format(COMP=reqhdr))

    def process_response(self):
        content_len = self.header["content-length"]

        if len(self._recv_buffer) >= content_len:
            data = cipher.decrypt(self._recv_buffer[:content_len])
            self._recv_buffer = self._recv_buffer[content_len:]

            encoding = self.header["content-encoding"]
            self.response = self._decode(data, encoding)
            logger.info('receiving response to request "{REQ}" from {ADDR}'.format(REQ=self.action, ADDR=self.addr))
#            logger.debug('response received: {}'.format(self.response))


class SettingsManager:
    """
    Class to store and manage user-specific configuration settings.

    Arguments:

        cnfg: Parsed YAML file

    Attributes:

        language (str): Display language. Default: EN.
    """

    def __init__(self, cnfg, dirname):
        self.dirname = dirname
        self.icons_dir = os.path.join(self.dirname, 'docs', 'images', 'icons')
        self.instance_id = randint(0, 1000000000)

        # Supported locales
        #        self._locales = ['en_US', 'en_UK', 'th_TH']
        self._locales = {'English': 'en', 'Thai': 'th'}

        # User parameters
        try:
            self.username = cnfg['user']['username']
        except KeyError:
            self.username = 'username'

        # Localization parameters
        try:
            self.language = cnfg['localization']['language']
        except KeyError:
            self.language = 'en'
        try:
            cnfg_locale = cnfg['localization']['locale']
        except KeyError:
            cnfg_locale = 'English'
        #        self.locale = cnfg_locale if cnfg_locale in self._locales else 'en_US'
        self.locale = cnfg_locale if cnfg_locale in self._locales else 'English'
        try:
            logger.info('settings locale to {}'.format(self.locale))
            locale.setlocale(locale.LC_ALL, self.locale)
        except Exception as e:
            msg = 'unable to set locale - {ERR}'.format(ERR=e)
            logger.warning(msg)
            popup_error(msg)
            sys.exit(1)
        else:
            logger.info('dates will be offset by {} years'.format(self.get_date_offset()))

        locale_conv = locale.localeconv()
        self.decimal_sep = locale_conv['decimal_point']
        self.thousands_sep = locale_conv['thousands_sep']
        self.currency = locale_conv['int_curr_symbol']
        self.currency_symbol = locale_conv['currency_symbol']

        self.localedir = os.path.join(dirname, 'locale')
        self.domain = 'base'

        try:
            self.display_date_format = cnfg['localization']['display_date']
        except KeyError:
            self.display_date_format = 'YYYY-MM-DD'

        self.translation = self.change_locale()
        self.translation.install('base')  # bind gettext to _() in __builtins__ namespace

        # Display parameters
        try:
            icon_name = cnfg['display']['icon']
        except KeyError:
            icon_file = os.path.join(dirname, 'docs', 'images', 'icon.ico')
        else:
            if not icon_name:
                icon_file = os.path.join(dirname, 'docs', 'images', 'icon.ico')
            else:
                icon_file = os.path.join(dirname, 'docs', 'images', icon_name)

        try:
            fh = open(icon_file, 'r', encoding='utf-8')
        except FileNotFoundError:
            self.icon = None
        else:
            self.icon = icon_file
            fh.close()

        try:
            logo_name = cnfg['display']['logo']
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
            logo_icon = cnfg['display']['logo_icon']
        except KeyError:
            logo_file = os.path.join(dirname, 'docs', 'images', 'icons', 'logo_icon.png')
        else:
            if not logo_icon:
                logo_file = os.path.join(dirname, 'docs', 'images', 'icons', 'logo_icon.png')
            else:
                logo_file = os.path.join(dirname, 'docs', 'images', logo_icon)

        try:
            fh = open(logo_file, 'r', encoding='utf-8')
        except FileNotFoundError:
            self.logo_icon = None
        else:
            self.logo_icon = logo_file
            fh.close()

        try:
            report_template = cnfg['display']['report_template']
        except KeyError:
            self.report_template = os.path.join(dirname, 'templates', 'report.html')
        else:
            if not report_template:
                self.report_template = os.path.join(dirname, 'templates', 'report.html')
            else:
                self.report_template = report_template

        try:
            report_style = cnfg['display']['report_stylesheet']
        except KeyError:
            self.report_css = os.path.join(dirname, 'static', 'css', 'report.css')
        else:
            if not report_style:
                self.report_css = os.path.join(dirname, 'static', 'css', 'report.css')
            else:
                self.report_css = report_style

        # Dependencies
        try:
            wkhtmltopdf = cnfg['dependencies']['wkhtmltopdf']
        except KeyError:
            self.wkhtmltopdf = os.path.join(dirname, 'data', 'wkhtmltopdf', 'bin', 'wkhtmltopdf.exe')
        else:
            if not wkhtmltopdf:
                self.wkhtmltopdf = os.path.join(dirname, 'data', 'wkhtmltopdf', 'bin', 'wkhtmltopdf.exe')
            else:
                self.wkhtmltopdf = wkhtmltopdf

        # Server parameters
        try:
            self.host = cnfg['server']['host']
        except KeyError:
            self.host = '127.0.0.1'  # localhost
        try:
            self.port = int(cnfg['server']['port'])
        except KeyError:
            self.port = 65432
        except ValueError:
            logger.warning('unsupported value {} provided to server configuration parameter "port" ... setting to '
                           'default "65432"'.format(cnfg["server"]["port"]))
            self.port = 65432

        # Logging
        try:
            self.log_file = cnfg['log']['log_file']
        except KeyError:
            self.log_file = None
        try:
            self.log_level = cnfg['log']['log_level'].upper()
        except (KeyError, AttributeError):
            self.log_level = 'WARNING'
        try:
            self.log_fmt = cnfg['log']['log_fmt']
        except KeyError:
            self.log_fmt = '%(asctime)s: %(filename)s: %(levelname)s: %(message)s'

        # Configuration data
        self.audit_rules = None
        self.bank_rules = None
        self.cash_rules = None
        self.record_rules = None

        try:
            self.dbname = cnfg['database']['default_database']
        except KeyError:
            self.dbname = None
        self.prog_db = None
        self.alt_dbs = None
        self.date_format = None

        self.creator_code = None
        self.creation_date = None
        self.editor_code = None
        self.edit_date = None
        self.delete_field = None
        self.id_field = None
        self.date_field = None
        self.notes_field = None
        self.warnings_field = None
        self.reference_lookup = None
        self.bank_lookup = None

    def translate(self):
        """
        Translate text using language defined in settings.
        """
        pass

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
        elif attr == 'host':
            self.host = value
        elif attr == 'dbname':
            self.dbname = value

    def get_unsaved_ids(self, internal: bool = True):
        """
        Get unsaved record IDs for all record entry types.
        """
        entries = self.records.rules
        unsaved_ids = {}
        for entry in entries:
            id_list = entry.get_unsaved_ids(internal_only=internal)
            unsaved_ids[entry.name] = id_list

        return unsaved_ids

    def remove_unsaved_ids(self):
        """
        Remove unsaved record IDs for all record entry types.
        """
        value = {'ids': None, 'record_type': None, 'instance': self.instance_id}
        content = {'action': 'remove_ids', 'value': value}
        request = {'content': content, 'encoding': "utf-8"}
        response = server_conn.process_request(request)

        success = response['success']
        if success is False:
            msg = 'failed to remove IDs created during the program instance from the list of unsaved record IDs - ' \
                  '{ERR}'.format(ERR=response['value'])
            logger.error(msg)
        else:
            msg = 'successfully removed IDs created during the program instance from the list of unsaved record IDs'
            logger.debug(msg)

#        entries = self.records.rules
#        for entry in entries:
#            entry.remove_unsaved_ids(internal_only=internal)

    def load_constants(self, connection):
        """
        Load configuration constants.
        """
        # Prepare the request to the server
        content = {'action': 'constants', 'value': None}
        request = {'content': content, 'encoding': "utf-8"}

        # Send the request for data to the server
        response = connection.process_request(request)
        success = response['success']
        if success is False:
            msg = 'failed to load configuration constants from server - {}'.format(response['value'])
            logger.error(msg)
            popup_error(msg)
            conf_const = {}
        else:
            conf_const = response['value']

        self.audit_rules = conf_const.get('audit_rules', None)
        self.cash_rules = conf_const.get('cash_rules', None)
        self.bank_rules = conf_const.get('bank_rules', None)
        self.record_rules = conf_const.get('records', None)

        database_attrs = conf_const.get('database', {})
        self.prog_db = database_attrs.get('program_database', 'REM')
        self.alt_dbs = database_attrs.get('databases', [])
        if not self.dbname or self.dbname not in self.alt_dbs:
            self.dbname = database_attrs.get('default_database', 'REM')
        self.date_format = database_attrs.get('db_date_format', self.format_date_str('YYYY-MM-DD HH:MI:SS'))

        # Reserved tables and table columns
        table_field_attrs = conf_const.get('table_fields', {})
        self.creator_code = table_field_attrs.get('creator_code', 'CreatorName')
        self.creation_date = table_field_attrs.get('creation_time', 'CreationTime')
        self.editor_code = table_field_attrs.get('editor_code', 'EditorName')
        self.edit_date = table_field_attrs.get('edit_time', 'EditTime')
        self.id_field = table_field_attrs.get('id_field', 'DocNo')
        self.date_field = table_field_attrs.get('date_field', 'DocDate')
        self.notes_field = table_field_attrs.get('notes_field', 'Notes')
        self.warnings_field = table_field_attrs.get('warnings_field', 'Warnings')
        self.delete_field = table_field_attrs.get('delete_field', 'IsDeleted')
        self.reference_lookup = table_field_attrs.get('reference_table', 'RecordReferences')
        self.bank_lookup = table_field_attrs.get('bank_table', 'Bank')

        self.records = None

        return success

    def layout(self):
        """
        Generate GUI layout for the settings window.
        """
        width = 800

        # Window and element size parameters
        main_font = mod_const.MAIN_FONT

        pad_el = mod_const.ELEM_PAD
        pad_v = mod_const.VERT_PAD
        pad_frame = mod_const.FRAME_PAD
        in_size = 18
        spacer = (12, 1)
        dd_size = 8

        bg_col = mod_const.ACTION_COL
        in_col = mod_const.INPUT_COL

        bwidth = 1
        select_col = mod_const.SELECT_TEXT_COL

        layout = [
            [sg.Frame('Localization', [
                [sg.Canvas(size=(width, 0), pad=(0, pad_v), visible=True, background_color=bg_col)],
                [sg.Text('Language:', size=(15, 1), pad=((pad_frame, pad_el), pad_el), font=main_font,
                         background_color=bg_col),
                 sg.Combo(list(self._locales.values()), key='-LANGUAGE-', size=(dd_size, 1), pad=(pad_el, pad_el),
                          default_value=self.language, auto_size_text=False, background_color=in_col)],
                [sg.Text('Locale:', size=(15, 1), pad=((pad_frame, pad_el), pad_el), font=main_font,
                         background_color=bg_col),
                 sg.Combo(list(self._locales), key='-LOCALE-', size=(dd_size, 1), pad=(pad_el, pad_el),
                          default_value=self.locale, auto_size_text=False, background_color=in_col)],
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
                [sg.Text('Database:', size=(15, 1), pad=((pad_frame, pad_el), pad_el), font=main_font,
                         background_color=bg_col),
                 sg.Combo(self.alt_dbs, default_value=self.dbname, key='-DATABASE-', size=(in_size - 1, 1),
                          pad=((pad_el, pad_frame), pad_el), font=main_font, background_color=in_col)],
                [sg.Canvas(size=(800, 0), pad=(0, pad_v), visible=True, background_color=bg_col)]],
                      pad=(pad_frame, pad_frame), border_width=bwidth, background_color=bg_col,
                      title_color=select_col, relief='groove')],
            [sg.Frame('Server', [
                [sg.Canvas(size=(width, 0), pad=(0, pad_v), visible=True, background_color=bg_col)],
                [sg.Text('Server Port:', size=(15, 1), pad=((pad_frame, pad_el), pad_el),
                         font=main_font, background_color=bg_col),
                 sg.Input(self.port, key='-PORT-', size=(in_size, 1), pad=((pad_el, pad_frame), pad_el),
                          font=main_font, background_color=in_col),
                 sg.Text('', size=spacer, background_color=bg_col),
                 sg.Text('Server Host:', size=(15, 1), pad=((pad_frame, pad_el), pad_el), font=main_font,
                         background_color=bg_col),
                 sg.Input(self.host, key='-SERVER-', size=(in_size, 1), pad=((pad_el, pad_frame), pad_el),
                          font=main_font, background_color=in_col)],
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

        #        if language not in [i.split('_')[0] for i in self._locales]:
        #            raise NameError
        if language not in self._locales.values():
            raise NameError

        try:
            trans = gettext.translation(domain, localedir=localdir, languages=[language])
        except Exception as e:
            logger.warning('unable to find translations for locale {LANG} - {ERR}'.format(LANG=language, ERR=e))
            trans = gettext

        return trans

    def format_display_date(self, dt):
        """
        Format a datetime object for displaying based on configured date format.

        Arguments:
            dt (datetime): datetime instance.
        """
        date = self.apply_date_offset(dt)
        date_str = self.format_date_str(date_str=self.display_date_format)

        date_formatted = date.strftime(date_str)

        return date_formatted

    def format_date_str(self, date_str: str = None):
        """
        Format a date string for use as input to datetime method.

        Arguments:
            date_str (str): date string.
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
                        raise TypeError('unknown component {} provided to date string {}.'.format(component, date_str))

                strfmt.append(char)
                buff = []

            last_char = char

        try:  # format final component remaining in buffer
            strfmt.append(date_fmts[''.join(buff)])
        except KeyError:
            raise TypeError('unsupported characters {} found in date string {}'.format(''.join(buff), date_str))

        return ''.join(strfmt)

    def get_date_offset(self):
        """
        Find date offset for calendar systems other than the gregorian calendar
        """
        current_locale = self.locale

        if current_locale == 'Thai':
            offset = 543
        else:
            offset = 0

        return offset

    def apply_date_offset(self, dt):
        """
        Apply date offset to a datetime object.

        Arguments:
            dt (datetime.datetime): datetime instance.
        """
        relativedelta = dateutil.relativedelta.relativedelta
        strptime = datetime.datetime.strptime

        offset = self.get_date_offset()
        try:
            dt_mod = dt + relativedelta(years=+offset)
        except Exception as e:
            logging.debug('encountered warning when attempting to apply offset to date - {ERR}'.format(ERR=e))
            dt_mod = strptime(dt.strftime('%Y-%m-%d %H:%M:%S'), '%Y-%m-%d %H:%M:%S') + relativedelta(years=+offset)

        return dt_mod

    def get_icon_path(self, icon):
        """
        Return the path of an icon, if exists.
        """
        icon = "{}.png".format(icon)
        icon_path = os.path.join(self.icons_dir, icon)
        if not os.path.exists(icon_path):
            logger.warning('unable to open icon PNG {ICON}'.format(ICON=icon))
            icon_path = None

        return icon_path

    def reload_logger(self, stream, log_level: str = None):
        """
        Reload the log configuration
        """
        if log_level:
            self.log_level = log_level

        for handler in logger.handlers[:]:  # removes existing file handlers
            logger.removeHandler(handler)

        logger.addHandler(configure_handler(CNFG, stream=stream, log_level=log_level))


class AccountManager:
    """
    Basic user account manager object.

    Attributes:
        uid (str): existing account username.

        pwd (str): hash value for associated account password.

        admin (bool): existing account is an admin account.

        logged_in (bool): user is logged in
    """

    def __init__(self):
        self.uid = None
        self.pwd = None
        self.group = None
        self.logged_in = False
        self.admin = False

    def _prepare_conn_str(self, database: str = None):
        """
        Prepare the connection string.
        """
        db = database if database is not None else settings.prog_db

        return {'UID': self.uid, 'PWD': self.pwd, 'Database': db}

    def login(self, uid, pwd, timeout: int = 10):
        """
        Verify username and password exists in the database accounts table and obtain user permissions.

        Args:
            uid (str): existing account username.

            pwd (str): password associated with the existing account.

            timeout (int): server connection timeout.
        """
        self.uid = uid
        self.pwd = pwd

        # Prepare query statement and parameters
        query_str = 'SELECT UserName, UserGroup FROM Users WHERE UserName = ?'
        params = (uid, )

        # Prepare the server request
        value = {'connection_string': self._prepare_conn_str(), 'transaction_type': 'read', 'statement': query_str,
                 'parameters': params}
        content = {'action': 'db_transact', 'value': value}
        request = {'content': content, 'encoding': "utf-8"}

        # Send the request for data to the server
        response = server_conn.process_request(request, timeout=timeout)
        if response['success'] is False:
            msg = 'login failure for user {USER} - {ERR}'.format(USER=uid, ERR=response['value'])
            logger.error(msg)
            raise IOError(msg)
        else:
            try:
                series = pd.DataFrame(response['value']).iloc[0]
            except Exception as e:
                msg = 'failed to read the results of the database query - {ERR}'.format(ERR=e)
                logger.error(msg)
                raise IOError(msg)
            else:
                ugroup = series['UserGroup']

#        conn = self.db_connect(database=self.dbname, timeout=timeout)
#        cursor = conn.cursor()

        # Privileges
#        query_str = 'SELECT UserName, UserGroup FROM Users WHERE UserName = ?'
#        cursor.execute(query_str, (uid,))

#        ugroup = None
#        results = cursor.fetchall()
#        for row in results:
#            username, user_group = row
#            if username == uid:
#                ugroup = user_group
#                break

#        cursor.close()
#        conn.close()

        if not ugroup:
            self.uid = None
            self.pwd = None
            return False

        self.uid = uid
        self.pwd = pwd
        self.group = ugroup
        self.logged_in = True

        if ugroup == 'admin':
            self.admin = True

        return True

    def logout(self):
        """
        Reset class attributes.
        """
        self.uid = None
        self.pwd = None
        self.group = None
        self.logged_in = False
        self.admin = False
        success = True

        return success

    def access_permissions(self):
        """
        Return escalated privileges for a given user group.
        """
        ugroup = self.group

        if ugroup == 'admin':
            return ['admin', 'user']
        else:
            return ['user']

    def database_tables(self, database, timeout: int = 5):
        """
        Get database schema information.
        """
        # Prepare the server request
        value = {'connection_string': self._prepare_conn_str(), 'table': None, 'database': database}
        content = {'action': 'db_schema', 'value': value}
        request = {'content': content, 'encoding': "utf-8"}

        # Send the request for data to the server
        response = server_conn.process_request(request, timeout=timeout)
        if response['success'] is False:
            msg = response['value']
            logger.error(msg)

            results = []
        else:
            results = response['value']

        return results

    def table_schema(self, database, table, timeout: int = 5):
        """
        Get table schema information.
        """
        # Prepare the server request
        value = {'connection_string': self._prepare_conn_str(), 'table': table, 'database': database}
        content = {'action': 'db_schema', 'value': value}
        request = {'content': content, 'encoding': "utf-8"}

        # Send the request for data to the server
        response = server_conn.process_request(request, timeout=timeout)
        if response['success'] is False:
            msg = response['value']
            logger.error(msg)

            results = []
        else:
            results = response['value']

        return results

    def prepare_query_statement(self, tables, columns='*', filter_rules=None, order=None, distinct: bool = False):
        """
        Prepare a statement and parameters for querying an ODBC database.

        Arguments:

            tables (str): primary table ID.

            columns: list or string containing the column(s) to select from the database table.

            filter_rules: tuple or list of tuples containing where clause and value tuple for a given filter rule.

            order: string or list of strings containing columns to sort results by.

            distinct (bool): add the distinct clause to the statement to return only unique entries.
        """
        # Define sorting component of query statement
        if type(order) in (type(list()), type(tuple())):
            if len(order) > 0:
                order_by = ' ORDER BY {}'.format(', '.join(order))
            else:
                order_by = ''
        elif isinstance(order, str):
            order_by = ' ORDER BY {}'.format(order)
        else:
            order_by = ''

        # Define column component of query statement
        colnames = ', '.join(columns) if type(columns) in (type(list()), type(tuple())) else columns

        # Construct filtering rules
        try:
            where_clause, params = construct_where_clause(filter_rules)
        except SQLStatementError as e:
            msg = 'failed to generate the query statement - {}'.format(e)
            logger.error(msg)

            raise SQLStatementError(msg)

        # Prepare the database transaction statement
        if not distinct:
            query_str = 'SELECT {COLS} FROM {TABLE} {WHERE} {SORT};'.format(COLS=colnames, TABLE=tables,
                                                                            WHERE=where_clause, SORT=order_by)
        else:
            query_str = 'SELECT DISTINCT {COLS} FROM {TABLE} {WHERE} {SORT};'.format(COLS=colnames, TABLE=tables,
                                                                                     WHERE=where_clause, SORT=order_by)

        logger.debug('query string is "{STR}" with parameters "{PARAMS}"'.format(STR=query_str, PARAMS=params))

        return (query_str, params)

    def prepare_insert_statement(self, table, columns, values):
        """
        Prepare a statement and parameters for inserting a new entry into an ODBC database.
        """
        if isinstance(columns, str):
            columns = [columns]

        # Format parameters
        if isinstance(values, list):  # multiple insertions requested
            if not all([isinstance(i, tuple) for i in values]):
                msg = 'failed to generate insertion statement - individual transactions must be formatted as tuple'
                logger.error(msg)

                raise SQLStatementError(msg)

            if not all([len(columns) == len(i) for i in values]):
                msg = 'failed to generate insertion statement - the number of columns is not equal to the number ' \
                      'of provided parameters for all transactions requested'
                logger.error(msg)

                raise SQLStatementError(msg)

            params = []
            for param_tup in values:
                params.append(tuple([convert_datatypes(i) for i in param_tup]))

        elif isinstance(values, tuple):  # single insertion
            if len(columns) != len(values):
                msg = 'failed to generate insertion statement - the number of columns is not equal to the number ' \
                      'of parameters for the transaction'
                logger.error(msg)

                raise SQLStatementError(msg)

            params = tuple([convert_datatypes(i) for i in values])

        elif isinstance(values, str):  # single insertion for single column
            if len(columns) > 1:
                msg = 'failed to generate insertion statement - the number of columns is not equal to the number of ' \
                      'parameters for the transaction'
                logger.error(msg)

                raise SQLStatementError(msg)

            params = (convert_datatypes(values),)
        else:
            msg = 'failed to generate insertion statement - unknown values type {}'.format(type(values))
            logger.error(msg)

            raise SQLStatementError(msg)

        # Prepare the database transaction statement
        markers = '({})'.format(','.join(['?' for _ in columns]))
        insert_str = 'INSERT INTO {TABLE} {COLS} VALUES {VALS};' \
            .format(TABLE=table, COLS='({})'.format(','.join(columns)), VALS=markers)
        logger.debug('insertion string is "{STR}" with parameters "{PARAMS}"'.format(STR=insert_str, PARAMS=params))

        return (insert_str, params)

    def prepare_update_statement(self, table, columns, values, where_clause, filter_values):
        """
        Prepare a statement and parameters for updating an existing entry in an ODBC dataabase.
        """
        # Format parameters
        if isinstance(values, list):  # multiple updates requested
            if not all([isinstance(i, tuple) for i in values]):
                msg = 'failed to generate update statement - individual transactions must be formatted as tuple'
                logger.error(msg)

                raise SQLStatementError(msg)

            if not all([len(columns) == len(i) for i in values]):
                msg = 'failed to generate update statement - the number of columns is not equal to the number ' \
                      'of provided parameters for all transactions requested'
                logger.error(msg)

                raise SQLStatementError(msg)

            if not isinstance(filter_values, list) or len(values) != len(filter_values):
                msg = 'failed to generate update statement - the number of transactions requested do not match the ' \
                      'number of filters provided'
                logger.error(msg)

                raise SQLStatementError(msg)

            params = []
            for index, param_tup in enumerate(values):
                # Convert parameter types
                mod_params = [convert_datatypes(i) for i in param_tup]

                # Add filter parameters to the end of the parameter list
                filter_tup = filter_values[index]
                mod_filter_params = [convert_datatypes(i) for i in filter_tup]
                mod_params = mod_params + mod_filter_params

                params.append(tuple(mod_params))

        elif isinstance(values, tuple):  # single update requested
            if len(columns) != len(values):
                msg = 'failed to generate update statement - the number of columns is not equal to the number of ' \
                      'provided parameters for the transaction'
                logger.error(msg)

                raise SQLStatementError(msg)

            if not isinstance(filter_values, tuple):
                msg = 'failed to generate update statement - the number of transactions requested do not match the ' \
                      'number of filters provided'
                logger.error(msg)

                raise SQLStatementError(msg)

            params = tuple([convert_datatypes(i) for i in values] + [convert_datatypes(j) for j in filter_values])

        elif isinstance(values, str) or pd.isna(values):  # single update of one column is requested
            if not isinstance(columns, str):
                msg = 'failed to generate update statement - the number of columns is not equal to the number of ' \
                      'provided parameters for the transaction'
                logger.error(msg)

                raise SQLStatementError(msg)

            params = tuple([convert_datatypes(values)] + [convert_datatypes(j) for j in filter_values])
        else:
            msg = 'failed to generate update statement - unknown values type {}'.format(type(values))
            logger.error(msg)

            raise SQLStatementError(msg)

        pair_list = ['{}=?'.format(colname) for colname in columns]

        # Prepare the database transaction statement
        update_str = 'UPDATE {TABLE} SET {PAIRS} WHERE {WHERE};' \
            .format(TABLE=table, PAIRS=','.join(pair_list), WHERE=where_clause)
        logger.debug('update string is "{STR}" with parameters "{PARAMS}"'.format(STR=update_str, PARAMS=params))

        return (update_str, params)

    def prepare_delete_statement(self, table, columns, values):
        """
        Prepare a statement and parameters for deleting an existing entry from an ODBC database.
        """
        if isinstance(columns, str):
            columns = [columns]

        # Format parameters
        if isinstance(values, list):
            if not all([isinstance(i, tuple) for i in values]):
                msg = 'failed to generate insertion statement - individual transactions must be formatted as tuple'
                logger.error(msg)

                raise SQLStatementError(msg)

            if not all([len(columns) == len(i) for i in values]):
                msg = 'failed to generate insertion statement - the number of columns is not equal to the number ' \
                      'of provided parameters for all transactions requested'
                logger.error(msg)

                raise SQLStatementError(msg)

            params = []
            for param_tup in values:
                params.append(tuple([convert_datatypes(i) for i in param_tup]))

        elif isinstance(values, tuple):  # single insertion
            if len(columns) != len(values):
                msg = 'failed to generate insertion statement - the number of columns is not equal to the number ' \
                      'of parameters for the transaction'
                logger.error(msg)

                raise SQLStatementError(msg)

            params = tuple([convert_datatypes(i) for i in values])

        elif isinstance(values, str):
            if len(columns) > 1:
                msg = 'failed to generate deletion statement - the number of columns is not equal to the number of ' \
                      'parameters for the transaction'
                logger.error(msg)

                raise SQLStatementError(msg)

            params = (convert_datatypes(values),)

        else:
            msg = 'failed to generate deletion statement - unknown values type {}'.format(type(values))
            logger.error(msg)

            raise SQLStatementError(msg)

        pairs = {}
        for colname in columns:
            if colname in pairs:
                pairs[colname].append('?')
            else:
                pairs[colname] = ['?']

        pair_list = []
        for colname in pairs:
            col_params = pairs[colname]
            if len(col_params) > 1:
                pair_list.append('{COL} IN ({VALS})'.format(COL=colname, VALS=', '.join(col_params)))
            elif len(col_params) == 1:
                pair_list.append('{COL}=?'.format(COL=colname))
            else:
                logger.warning('failed to generate deletion statement - column "{}" has no associated parameters'
                               .format(colname))
                continue

        # Prepare the database transaction statement
        delete_str = 'DELETE FROM {TABLE} WHERE {PAIRS}'.format(TABLE=table, PAIRS=' AND '.join(pair_list))
        logger.debug('deletion string is "{STR}" with parameters "{PARAMS}"'.format(STR=delete_str, PARAMS=params))

        return (delete_str, params)

    def read_db(self, statement, params, prog_db: bool = False):
        """
        Read from an ODBC database.
        """
        # Prepare the server request
        db = settings.prog_db if prog_db is True else settings.dbname
        value = {'connection_string': self._prepare_conn_str(database=db), 'transaction_type': 'read',
                 'statement': statement, 'parameters': params}
        content = {'action': 'db_transact', 'value': value}
        request = {'content': content, 'encoding': "utf-8"}

        # Send the request for data to the server
        response = server_conn.process_request(request)
        if response['success'] is False:
            msg = response['value']
            logger.error(msg)

            df = pd.DataFrame()
        else:
            try:
                df = pd.DataFrame(response['value'])
            except Exception as e:
                msg = 'failed to read the results of the database query - {ERR}'.format(ERR=e)
                logger.error(msg)

                df = pd.DataFrame()

        return df

    def write_db(self, statement, params):
        """
        Write to an ODBC database.
        """
        # Prepare the server request
        db = settings.prog_db
        value = {'connection_string': self._prepare_conn_str(database=db), 'transaction_type': 'write',
                 'statement': statement, 'parameters': params}
        content = {'action': 'db_transact', 'value': value}
        request = {'content': content, 'encoding': "utf-8"}

        # Send the request for data to the server
        response = server_conn.process_request(request)
        if response['success'] is False:
            msg = response['value']
            logger.error(msg)

            status = False
        else:
            status = True

        return status


# Functions
def hash_password(password):
    """
    Obtain a password's hash-code.
    """
    password_utf = password.encode('utf-8')

    md5hash = hashlib.md5()
    md5hash.update(password_utf)

    password_hash = md5hash.hexdigest()

    return password_hash


def construct_where_clause(filter_rules):
    """
    Construct an SQL statement where clause for querying and updating database tables.
    """
    if filter_rules is None or len(filter_rules) == 0:  # no filtering rules
        return ('', None)

    # Construct filtering rules
    if isinstance(filter_rules, list):  # multiple filter parameters
        all_params = []
        for rule in filter_rules:
            try:
                statement, params = rule
            except ValueError:
                msg = 'incorrect data type for filter rule {}'.format(rule)
                raise SQLStatementError(msg)

            if type(params) in (type(tuple()), type(list())):
                # Unpack parameters
                for param_value in params:
                    all_params.append(param_value)
            elif type(params) in (type(str()), type(int()), type(float())):
                all_params.append(params)
            else:
                msg = 'unknown parameter type {} in rule {}'.format(params, rule)
                raise SQLStatementError(msg)

        params = tuple(all_params)
        where = 'WHERE {}'.format(' AND '.join([i[0] for i in filter_rules]))

    elif isinstance(filter_rules, tuple):  # single filter parameter
        statement, params = filter_rules
        where = 'WHERE {COND}'.format(COND=statement)

    else:  # unaccepted data type provided
        msg = 'unaccepted data type {} provided in rule {}'.format(type(filter_rules), filter_rules)
        raise SQLStatementError(msg)

    return (where, params)


def convert_datatypes(value):
    """
    Convert values with numpy data-types to native data-types.
    """
    strptime = datetime.datetime.strptime
    is_float_dtype = pd.api.types.is_float_dtype
    is_integer_dtype = pd.api.types.is_integer_dtype
    is_bool_dtype = pd.api.types.is_bool_dtype
    is_datetime_dtype = pd.api.types.is_datetime64_any_dtype
    date_fmt = settings.date_format

    if pd.isna(value):
        converted_value = None
    elif is_float_dtype(type(value)) is True or isinstance(value, float):
        converted_value = float(value)
    elif is_integer_dtype(type(value)) is True or isinstance(value, int):
        converted_value = int(value)
    elif is_bool_dtype(type(value)) is True or isinstance(value, bool):
        converted_value = bool(value)
    elif is_datetime_dtype(type(value)) is True or isinstance(value, datetime.datetime):
        converted_value = strptime(value.strftime(date_fmt), date_fmt)
    else:
        converted_value = str(value)

    return converted_value


def popup_error(msg):
    """
    Display popup notifying user that there is a fatal program error.
    """
    font = mod_const.MID_FONT
    return sg.popup_error(textwrap.fill(msg, width=40), font=font, title='')


def load_config(cnfg_file):
    """
    Load the contents of the configuration file into a python dictionary.
    """
    try:
        fh = open(cnfg_file, 'r', encoding='utf-8')
    except FileNotFoundError:
        msg = 'Unable to load user settings file at {PATH}. Please verify that the file path is correct.'\
            .format(PATH=CNF_FILE)
        popup_error(msg)
        sys.exit(1)
    else:
        cnfg = yaml.safe_load(fh)
        fh.close()

    return cnfg


def configure_handler(cnfg, stream=sys.stdout, log_level: str = None):
    """
    Configure the rotating file handler for logging.
    """
    try:
        log_file = cnfg['log']['log_file']
    except (KeyError, ValueError):
        log_file = None

    if log_level:
        level = log_level
    else:
        try:
            level = cnfg['log']['log_level'].upper()
        except (KeyError, AttributeError):
            level = 'WARNING'

    if level == 'WARNING':
        log_level = logging.WARNING
    elif level == 'ERROR':
        log_level = logging.ERROR
    elif level == 'INFO':
        log_level = logging.INFO
    elif level == 'DEBUG':
        log_level = logging.DEBUG
    elif level == 'CRITICAL':
        log_level = logging.CRITICAL
    else:
        log_level = logging.WARNING

    try:
        nbytes = int(cnfg['log']['log_size'])
    except (KeyError, ValueError):  # default 1 MB
        nbytes = 1000000

    try:
        backups = int(cnfg['log']['log_backups'])
    except (KeyError, ValueError):  # default 5 backup files
        backups = 5

    try:
        formatter = logging.Formatter(cnfg['log']['log_fmt'])
    except (KeyError, ValueError):
        formatter = logging.Formatter('%(asctime)s: %(filename)s: %(levelname)s: %(message)s')

    if log_file:
        log_handler = handlers.RotatingFileHandler(log_file, maxBytes=nbytes, backupCount=backups, encoding='utf-8',
                                                   mode='a')
    else:
        log_handler = logging.StreamHandler(stream=stream)

    log_handler.setLevel(log_level)
    log_handler.setFormatter(formatter)

    return log_handler


# Determine if application is a script file or frozen exe
if getattr(sys, 'frozen', False):
    DIRNAME = os.path.dirname(sys.executable)
elif __file__:
    DIRNAME = os.path.dirname(__file__)
else:
    msg = 'Unable to determine file type of the program. Please verify proper program installation.'
    popup_error(msg)
    sys.exit(1)

# Load the encryption key and create the cipher
ENCRYPT_FILE = 'REM.aes'
ENCRYPT_PATH = os.path.join(DIRNAME, ENCRYPT_FILE)
if os.path.isfile(ENCRYPT_PATH) and os.access(ENCRYPT_PATH, os.R_OK):  # encryption key file exists and is readable
    with open(ENCRYPT_PATH, 'rb') as encrypt_h:
        encrypt_key = encrypt_h.read()
else:  # encryption key file has not yet been added to the client
    msg = 'Unable to start the program. Please download the encryption key file from the server to the program base ' \
          'directory before using.'
    popup_error(msg)
    sys.exit(1)

cipher = Fernet(encrypt_key)
del encrypt_key

# Load user-defined configuration settings
CNF_FILE = os.path.join(DIRNAME, 'settings.yaml')
CNFG = load_config(CNF_FILE)

# Create the logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

logger.addHandler(configure_handler(CNFG))

# Initialize manager objects
settings = SettingsManager(CNFG, DIRNAME)
user = AccountManager()

# Open a connection to the odbc_server
logger.info('opening a socket to connect to the server')
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    logger.info('socket successfully created')
except socket.error as e:
    msg = 'socket creation failed - {ERR}'.format(ERR=e)
    logger.error('{MSG}'.format(MSG=msg))
    popup_error(msg)
    sys.exit(1)
else:
    addr = (settings.host, settings.port)

logger.info('initializing connection to server "{ADDR}" on port {PORT}'.format(ADDR=settings.host, PORT=settings.port))
while True:
    try:
        sock.connect(addr)
    except BlockingIOError:
        logger.warning('encountered blocking error')
    except socket.error as e:
        msg = 'connection to server "{ADDR}" failed - {ERR}'.format(ADDR=settings.host, ERR=e)
        popup_error(msg)
        logger.error('{MSG}'.format(MSG=msg))

        sys.exit(1)
    else:
        logger.info('connection accepted from server "{ADDR}"'.format(ADDR=settings.host))
        sock.setblocking(False)

        break

server_conn = ServerConnection(sock, addr)

# Load the configuration constants
logger.info('loading program configuration from the server')
if not settings.load_constants(server_conn):
    logger.error('failed to load configuration from the server')
    sys.exit(1)
