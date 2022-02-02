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
                msg = 'connection to {ADDR} was closed for unknown reason ... attempting to reconnect' \
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

    def process_request(self, request, timeout: int = 60):
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

        # STATIC PARAMETERS
        # Supported data types
        self.supported_date_dtypes = ('date', 'datetime', 'timestamp', 'time')
        self.supported_int_dtypes = ('bit', 'int', 'integer', 'tinyint', 'smallint', 'mediumint', 'bigint')
        self.supported_float_dtypes = ('float', 'decimal', 'dec', 'double', 'numeric', 'money', 'real')
        self.supported_bool_dtypes = ('bool', 'boolean')
        self.supported_str_dtypes = ('varchar', 'string', 'str', 'binary', 'text', 'tinytext', 'mediumtext', 'longtext')
        self.supported_cat_dtypes = ('char',)

        # Supported record modifiers
        self.supported_modifiers = ['ImportUnsavedReferences']

        # Supported localization parameters
        #        self._locales = ['en_US', 'en_UK', 'th_TH']
        self._locales = {'English': 'en', 'Thai': 'th'}
        self.supported_display_date_formats = ['YYYY-MM-DD', 'YY-MM-DD', 'DD-MM-YYYY', 'DD-MM-YY', 'MM-DD-YY',
                                               'MM-DD-YYYY']

        # CONFIGURABLE PARAMETERS
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
            report_template = cnfg['display']['record_template']
        except KeyError:
            self.report_template = os.path.join(dirname, 'templates', 'report.html')
        else:
            if not report_template:
                self.report_template = os.path.join(dirname, 'templates', 'report.html')
            else:
                self.report_template = report_template

        try:
            audit_template = cnfg['display']['audit_template']
        except KeyError:
            self.audit_template = os.path.join(dirname, 'templates', 'audit_report.html')
        else:
            if not audit_template:
                self.audit_template = os.path.join(dirname, 'templates', 'audit_report.html')
            else:
                self.audit_template = audit_template

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

        # Keyboard bindings
        self.hotkeys = {'-HK_ESCAPE-': ('Cancel Action', 'Key-Escape', 'Esc', 'General'),
                        '-HK_ENTER-': ('Start Action', 'Key-Return', 'Enter', 'General'),
                        '-HK_RIGHT-': ('Move Right', 'Key-Right', 'Right', 'Navigation'),
                        '-HK_LEFT-': ('Move Left', 'Key-Left', 'Left', 'Navigation'),
                        '-HK_TAB1-': ('Tab1', 'Key-F1', 'F1', 'Navigation'),
                        '-HK_TAB2-': ('Tab2', 'Key-F2', 'F2', 'Navigation'),
                        '-HK_TAB3-': ('Tab3', 'Key-F3', 'F3', 'Navigation'),
                        '-HK_TAB4-': ('Tab4', 'Key-F4', 'F4', 'Navigation'),
                        '-HK_TAB5-': ('Tab5', 'Key-F5', 'F5', 'Navigation'),
                        '-HK_TAB6-': ('Tab6', 'Key-F6', 'F6', 'Navigation'),
                        '-HK_TAB7-': ('Tab7', 'Key-F7', 'F7', 'Navigation'),
                        '-HK_TAB8-': ('Tab8', 'Key-F8', 'F8', 'Navigation'),
                        '-HK_TAB9-': ('Tab9', 'Key-F9', 'F9', 'Navigation'),
                        '-HK_RECORD_DEL-': ('Delete Record', 'Control-Shift-d', 'CTRL+Shift+d', 'Record'),
                        '-HK_RECORD_SAVE-': ('Save Record', 'Control-Shift-s', 'CTRL+Shift+s', 'Record'),
                        '-HK_DE_SAVE-': ('Save changes', 'Control-s', 'CTRL+S', 'Data Element'),
                        '-HK_DE_CANCEL-': ('Cancel editing', 'Control-c', 'CTRL+C', 'Data Element'),
                        '-HK_TBL_ADD-': ('Add row', 'Control-a', 'CTRL+A', 'Table'),
                        '-HK_TBL_IMPORT-': ('Import row(s)', 'Control-q', 'CTRL+Q', 'Table'),
                        '-HK_TBL_DEL-': ('Delete row(s)', 'Control-d', 'CTRL+D', 'Table'),
                        '-HK_TBL_OPTS-': ('Toggle Options', 'Control-o', 'CTRL+O', 'Table'),
                        '-HK_TBL_FILTER-': ('Apply filters', 'Control-f', 'CTRL+F', 'Table')}

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
        self.aliases = None

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

        self.default_pgroup = 'admin'  # default permissions group when not configured

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
        elif attr == 'audit_template':
            self.audit_template = value
        elif attr == 'display_date':
            self.display_date_format = value

    def get_unsaved_ids(self, internal: bool = True):
        """
        Get unsaved record IDs for all record entry types.
        """
        entries = self.records.rules
        unsaved_ids = {}
        for entry in entries:
            id_list = entry.get_unsaved_ids(internal_only=internal)
            unsaved_ids[entry.id_code] = id_list

        return unsaved_ids

    def remove_unsaved_ids(self):
        """
        Remove unsaved record IDs for all record entry types.
        """
        value = {'ids': None, 'id_code': None, 'instance': self.instance_id}
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

    def fetch_alias_definition(self, parameter):
        """
        Get parameter alias definitions.
        """
        aliases = self.aliases
        if not aliases:
            msg = 'no alias definitions were defined in the configuration'
            logger.warning(msg)

            return {}

        if parameter in aliases:
            logger.debug('fetching alias definition for parameter {PARAM}'.format(PARAM=parameter))
            param_aliases = aliases[parameter]
        else:
            param_aliases = {}

        return param_aliases

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

            configuration = {}
        else:
            configuration = response['value']

        self.audit_rules = configuration.get('audit_rules', None)
        self.cash_rules = configuration.get('cash_rules', None)
        self.bank_rules = configuration.get('bank_rules', None)
        self.record_rules = configuration.get('records', None)
        param_def = configuration.get('parameters', {})
        try:
            self.aliases = param_def['definition']
        except KeyError:
            logger.warning('parameter configuration is missing the definitions entry')

        constants = configuration.get('constants', {})
        try:
            self.default_pgroup = constants['default_pgroup']
        except KeyError:
            self.default_pgroup = 'admin'

        database_attrs = configuration.get('database', {})
        self.prog_db = database_attrs.get('program_database', 'REM')
        self.alt_dbs = database_attrs.get('databases', [])
        if not self.dbname or self.dbname not in self.alt_dbs:
            self.dbname = database_attrs.get('default_database', 'REM')
        self.date_format = database_attrs.get('db_date_format', self.format_date_str('YYYY-MM-DD HH:MI:SS'))

        # Reserved tables and table columns
        table_field_attrs = configuration.get('table_fields', {})
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

    def layout(self, win_size: tuple = None):
        """
        Generate GUI layout for the settings window.
        """
        if not win_size:
            width, height = (mod_const.WIN_WIDTH, mod_const.WIN_HEIGHT)
        else:
            width, height = win_size

        # Window and element size parameters
        main_font = mod_const.MID_FONT
        bold_font = mod_const.BOLD_MID_FONT

        pad_el = mod_const.ELEM_PAD
        pad_v = mod_const.VERT_PAD
        pad_frame = mod_const.FRAME_PAD

        bg_col = mod_const.ACTION_COL
        in_col = mod_const.INPUT_COL
        select_col = mod_const.SELECT_TEXT_COL

        bwidth = 1
        spacer_h = 0
        h_diff = height - mod_const.WIN_HEIGHT  # current width over default width
        spacer_h = spacer_h + int(h_diff / 2)  # increase window width by 1 for every 2 pixel increase in screen width
        win_h = mod_const.WIN_HEIGHT + spacer_h
        container_h = win_h - 120  # window height minus header and buttons

        spacer_w = 0  # default extra size in pixels
        w_diff = width - mod_const.WIN_WIDTH  # current width over default width
        spacer_w = spacer_w + int(w_diff / 5)  # increase window width by 1 for every 5 pixel increase in screen width
        win_w = mod_const.WIN_WIDTH + spacer_w

        # Set column sizes
        dcol1_w = int(win_w * 0.4)
        dcol2_w = int(win_w * 0.6)

        hotkey_groups = {}
        for hotkey in settings.hotkeys:
            hotkey_action, hotkey_binding, hotkey_shortcut, hotkey_group = settings.hotkeys[hotkey]
            hotkey_title = sg.Text(hotkey_action, font=main_font, background_color=bg_col)
            hotkey_element = sg.Text(hotkey_shortcut, key=hotkey, font=main_font, background_color=bg_col)
            if hotkey_group in hotkey_groups:
                hotkey_groups[hotkey_group].append((hotkey_title, hotkey_element))
            else:
                hotkey_groups[hotkey_group] = [(hotkey_title, hotkey_element)]

        hotkey_layout = []
        for hotkey_group in hotkey_groups:
            group_layout = [sg.Col([[sg.Text(hotkey_group, font=bold_font, background_color=bg_col)],
                                    [sg.HorizontalSeparator(color=mod_const.FRAME_COL)]],
                                   pad=(pad_v, (pad_v, pad_el)), background_color=bg_col, expand_x=True)]
            hotkey_layout.append(group_layout)
            group_col1 = [[sg.Canvas(size=(dcol1_w, 0), background_color=bg_col)]]
            group_col2 = [[sg.Canvas(size=(dcol2_w, 0), background_color=bg_col)]]
            for hotkey_pair in hotkey_groups[hotkey_group]:
                hotkey_title, hotkey_element = hotkey_pair
                group_col1.append([hotkey_title])
                group_col2.append([hotkey_element])
            hotkey_layout.append([sg.Col(group_col1, pad=(pad_v, pad_el), background_color=bg_col),
                                  sg.Col(group_col2, pad=(pad_v, pad_el), background_color=bg_col)])

        layout = [sg.Canvas(size=(1, container_h), background_color=bg_col),
                  sg.Col([
                      [sg.Frame('Localization', [
                          [sg.Col([[sg.Canvas(size=(dcol1_w, 0), background_color=bg_col)],
                                   [sg.Text('Language:', pad=(0, (0, pad_el)), font=main_font, background_color=bg_col)],
                                   [sg.Text('Locale:', pad=(0, (0, pad_el)), font=main_font, background_color=bg_col)],
                                   [sg.Text('Display Date Format:', pad=(0, (0, pad_el)), font=main_font,
                                            background_color=bg_col)]],
                                  pad=(pad_v, pad_el), background_color=bg_col),
                           sg.Col([[sg.Canvas(size=(dcol2_w, 0), background_color=bg_col)],
                                   [sg.Combo(list(self._locales.values()), key='-LANGUAGE-', pad=(0, (0, pad_el)),
                                             default_value=self.language, background_color=in_col)],
                                   [sg.Combo(list(self._locales), key='-LOCALE-', pad=(0, (0, pad_el)),
                                             default_value=self.locale, background_color=in_col)],
                                   [sg.Combo(list(self.supported_display_date_formats), key='-DISPLAY_DATE-',
                                             pad=(0, (0, pad_el)), default_value=self.display_date_format,
                                             background_color=in_col)]],
                                  pad=(pad_v, pad_el), background_color=bg_col)]],
                                pad=(pad_v, pad_v), border_width=bwidth, background_color=bg_col,
                                title_color=select_col, relief='groove')],
                      [sg.Frame('Display', [
                          [sg.Col([[sg.Canvas(size=(dcol1_w, 0), background_color=bg_col)],
                                   [sg.Text('Record Report Template:', pad=(0, (0, pad_el)), font=main_font,
                                            background_color=bg_col)],
                                   [sg.Text('Audit Report Template:', pad=(0, (0, pad_el)), font=main_font,
                                            background_color=bg_col)],
                                   [sg.Text('Report Stylesheet:', pad=(0, (0, pad_el)), font=main_font,
                                            background_color=bg_col)]],
                                  pad=(pad_v, pad_el), background_color=bg_col),
                           sg.Col([[sg.Canvas(size=(dcol2_w, 0), background_color=bg_col)],
                                   [sg.Input(self.report_template, key='-TEMPLATE-', pad=((0, pad_el), (0, pad_el)),
                                             font=main_font, background_color=in_col),
                                    sg.FileBrowse('Browse...', font=mod_const.SMALL_FONT)],
                                   [sg.Input(self.audit_template, key='-AUDIT_TEMPLATE-',
                                             pad=((0, pad_el), (0, pad_el)), font=main_font, background_color=in_col),
                                    sg.FileBrowse('Browse...', font=mod_const.SMALL_FONT)],
                                   [sg.Input(self.report_css, key='-CSS-', pad=((0, pad_el), (0, pad_el)),
                                             font=main_font, background_color=in_col),
                                    sg.FileBrowse('Browse...', font=mod_const.SMALL_FONT)]],
                                  pad=(pad_v, pad_el), background_color=bg_col)]],
                                pad=(pad_v, pad_v), border_width=bwidth, background_color=bg_col,
                                title_color=select_col, relief='groove')],
                      [sg.Frame('Server', [
                          [sg.Col([[sg.Canvas(size=(dcol1_w, 0), background_color=bg_col)],
                                   [sg.Text('Server Port:', pad=(0, (0, pad_el)), font=main_font,
                                            background_color=bg_col)],
                                   [sg.Text('Server Host:', pad=(0, (0, pad_el)), font=main_font,
                                            background_color=bg_col)],
                                   [sg.Text('Database:', pad=(0, (0, pad_el)), font=main_font,
                                            background_color=bg_col)]],
                                  pad=(pad_v, pad_el), background_color=bg_col),
                           sg.Col([[sg.Canvas(size=(dcol2_w, 0), background_color=bg_col)],
                                   [sg.Input(self.port, key='-PORT-', pad=(0, (0, pad_el)), font=main_font,
                                             background_color=in_col)],
                                   [sg.Input(self.host, key='-SERVER-', pad=(0, (0, pad_el)), font=main_font,
                                             background_color=in_col)],
                                   [sg.Combo(self.alt_dbs, default_value=self.dbname, key='-DATABASE-',
                                             pad=(0, (0, pad_el)), font=main_font, background_color=in_col)]],
                                  pad=(pad_v, pad_el), background_color=bg_col)]],
                                pad=(pad_v, pad_v), border_width=bwidth, background_color=bg_col,
                                title_color=select_col, relief='groove')],
                      [sg.Frame('Keyboard', hotkey_layout, pad=(pad_v, pad_v), border_width=bwidth,
                                background_color=bg_col, title_color=select_col, relief='groove')]
                  ], background_color=bg_col, scrollable=True, vertical_scroll_only=True, expand_y=True)]

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

    def format_display(self, value, dtype):
        """
        Format value for display.
        """
        if value == '' or pd.isna(value):
            return ''

        if dtype == 'money':
            display_value = settings.format_display_money(value)

        elif dtype in self.supported_int_dtypes or dtype in self.supported_float_dtypes:
            display_value = str(value)

        elif dtype in self.supported_date_dtypes:
            if isinstance(value, datetime.datetime):
                display_value = self.format_display_date(value)  # default format is ISO
            else:
                display_value = value

        else:
            display_value = str(value).rstrip('\n\r')

        return str(display_value)

    def format_display_money(self, value):
        """
        Format a money data type value for displaying.
        """
        dec_sep = self.decimal_sep
        group_sep = self.thousands_sep

        if pd.isna(value):
            return '0.00'

        value = str(value)

        # Get the sign of the number
        if value[0] in ('-', '+'):  # sign of the number
            numeric_sign = value[0]
            value = value[1:]
        else:
            numeric_sign = ''

        if '.' in value:  # substitute common decimal separator "." for local-dependant separator
            integers, decimals = value.split('.')
            decimals = decimals[0:2].ljust(2, '0')
            display_value = '{SIGN}{VAL}{SEP}{DEC}' \
                .format(SIGN=numeric_sign, VAL=''.join([group_sep * (n % 3 == 2) + i for n, i in
                                                        enumerate(integers[::-1])][::-1]).lstrip(','),
                        SEP=dec_sep, DEC=decimals)
        else:
            display_value = '{SIGN}{VAL}{SEP}00' \
                .format(SIGN=numeric_sign, VAL=''.join([group_sep * (n % 3 == 2) + i for n, i in
                                                        enumerate(value[::-1])][::-1]).lstrip(','),
                        SEP=dec_sep)

        return display_value

    def format_display_date(self, dt, offset: bool = True):
        """
        Format a datetime value for displaying based on configured date format.

        Arguments:
            dt (datetime.datetime): datetime instance.

            offset (bool): add a localization-dependant offset to the display date [default: True].
        """
        is_datetime_dtype = pd.api.types.is_datetime64_any_dtype

        if pd.isna(dt):
            return ''

        if not is_datetime_dtype(type(dt)) and not isinstance(dt, datetime.datetime) and not isinstance(dt, datetime.date):
            raise ValueError('a datetime object is required in order to format a date for display - an object of '
                             'type "{TYPE}" was provided instead'.format(TYPE=type(dt)))

        if offset:
            date = self.apply_date_offset(dt)
        else:
            date = dt

        date_str = self.format_date_str(date_str=self.display_date_format)
        display_date = date.strftime(date_str)

        return display_date

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

    def get_icon_path(self, icon: str = None):
        """
        Return the path of an icon, if exists.
        """
        icon = "{}.png".format(icon) if icon else 'blank_icon.png'

        icon_path = os.path.join(self.icons_dir, icon)
        if not os.path.exists(icon_path):
            logger.warning('unable to open icon PNG {ICON}'.format(ICON=icon))
            icon_path = os.path.join(self.icons_dir, 'blank_icon.png')

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

    def get_supported_dtypes(self):
        """
        Return a tuple of all supported dtypes.
        """
        dtypes = (self.supported_float_dtypes + self.supported_int_dtypes + self.supported_bool_dtypes +
                  self.supported_date_dtypes + self.supported_str_dtypes + self.supported_cat_dtypes)

        return tuple(set(dtypes))

    def format_value(self, value, dtype, date_format: str = None):
        """
        Set the data type of the provided value.
        """
        if pd.isna(value):
            return None

        cnvrt_failure_msg = 'failed to format value "{VAL}" as "{DTYPE}" - {ERR}'
        if dtype in self.supported_float_dtypes:
            try:
                value_fmt = self.format_as_float(value)
            except ValueError as e:
                msg = cnvrt_failure_msg.format(VAL=value, DTYPE=dtype, ERR=e)
                logger.warning(msg)

                raise ValueError(msg)

        elif dtype in self.supported_int_dtypes:
            try:
                value_fmt = self.format_as_int(value)
            except ValueError as e:
                msg = cnvrt_failure_msg.format(VAL=value, DTYPE=dtype, ERR=e)
                logger.warning(msg)

                raise ValueError(msg)

        elif dtype in self.supported_bool_dtypes:
            try:
                value_fmt = self.format_as_bool(value)
            except ValueError as e:
                msg = cnvrt_failure_msg.format(VAL=value, DTYPE=dtype, ERR=e)
                logger.warning(msg)

                raise ValueError(msg)

        elif dtype in self.supported_date_dtypes:
            try:
                value_fmt = self.format_as_datetime(value, date_format=date_format)
            except ValueError as e:
                msg = cnvrt_failure_msg.format(VAL=value, DTYPE=dtype, ERR=e)
                logger.warning(msg)

                raise ValueError(msg)

        else:
            value_fmt = str(value)

        return value_fmt

    def format_as_bool(self, value):
        """
        Format a value as a boolean.
        """
        if pd.isna(value) or value == '':
            return False

        if isinstance(value, bool):
            value_fmt = value
        else:
            try:
                value_fmt = bool(int(value))
            except (ValueError, TypeError):
                try:
                    value_fmt = bool(value)
                except ValueError:
                    msg = 'unable to convert value {VAL} of type "{TYPE}" to a boolean value'\
                        .format(VAL=value, TYPE=type(value))

                    raise ValueError(msg)

        return value_fmt

    def format_as_int(self, value, group_sep: str = None, dec_sep: str = None):
        """
        Format a value as an integer.
        """
        group_sep = group_sep if group_sep else self.thousands_sep
        dec_sep = dec_sep if dec_sep else self.decimal_sep

        if pd.isna(value) or value == '':
            return None

        try:
            value_fmt = int(value)
        except (ValueError, TypeError):
            try:
                value_fmt = int(value.replace(group_sep, '').replace(dec_sep, '.'))
            except (ValueError, TypeError, AttributeError):
                msg = 'unable to convert value {VAL} of type "{TYPE}" to an integer value'\
                    .format(VAL=value, TYPE=type(value))

                raise ValueError(msg)

        return value_fmt

    def format_as_float(self, value, group_sep: str = None, dec_sep: str = None):
        """
        Format a value as a float.
        """
        group_sep = group_sep if group_sep else self.thousands_sep
        dec_sep = dec_sep if dec_sep else self.decimal_sep

        if pd.isna(value) or value == '':
            return None

        try:
            value_fmt = float(value)
        except (ValueError, TypeError):
            try:
                value_fmt = float(value.replace(group_sep, '').replace(dec_sep, '.'))
            except (ValueError, TypeError, AttributeError):
                msg = 'unable to convert value {VAL} of type "{TYPE}" to an float value' \
                    .format(VAL=value, TYPE=type(value))

                raise ValueError(msg)

        return value_fmt

    def format_as_datetime(self, value, date_format: str = None):
        """
        Format a value as a float.
        """
        is_datetime_dtype = pd.api.types.is_datetime64_any_dtype
        date_format = self.format_date_str(date_format) if date_format else self.date_format

        if pd.isna(value) or value == '':
            return None

        if isinstance(value, str):
            try:
                value_fmt = pd.to_datetime(value, format=date_format)
            except (ValueError, TypeError):
                msg = 'unable to parse the provided date format'.format(VAL=value, TYPE=type(value))

                raise ValueError(msg)
        elif isinstance(value, datetime.datetime) or is_datetime_dtype(value):
            value_fmt = value.replace(tzinfo=None)
        elif isinstance(value, datetime.date):
            value_fmt = value
        else:
            msg = 'unable to convert value {VAL} of type "{TYPE}" to an datetime value' \
                .format(VAL=value, TYPE=type(value))

            raise ValueError(msg)

        return value_fmt

    def format_as_iso(self, value):
        """
        Set a date string to be in ISO format.

        Arguments:
            value (list): value to be formatted as an ISO date string.
        """
        if isinstance(value, str):
            logger.warning('input {IN} is a string value'.format(IN=value))
            value = list(value)

        buff = []
        for index, char in enumerate(value):
            if index == 3:
                if len(value) != 4:
                    buff.append('{}-'.format(char))
                else:
                    buff.append(char)
            elif index == 5:
                if len(value) != 6:
                    buff.append('{}-'.format(char))
                else:
                    buff.append(char)
            else:
                buff.append(char)

        formatted_date = ''.join(buff)

        return formatted_date

    def set_shortcuts(self, window, hk_groups: list = None):
        """
        Bind keyboard shortcuts to text.
        """
        if isinstance(hk_groups, str):
            hk_groups = [hk_groups]

        hotkeys = self.hotkeys
        for hotkey in hotkeys:
            hotkey_action, hotkey_binding, hotkey_shortcut, hotkey_group = settings.hotkeys[hotkey]
            if hk_groups and hotkey_group not in hk_groups:
                continue

            try:
                window.bind('<{}>'.format(hotkey_binding), hotkey)
            except Exception:
                logger.exception('failed to bind keyboard shortcut {}'.format(hotkey_binding))
                print(hotkey_action, hotkey_binding, hotkey_shortcut, hotkey_group)

                raise

        return window

    def get_shortcuts(self, hk_groups: list = None):
        """
        Return a list of hotkeys belonging to a given shortcut group.
        """
        if not hk_groups:
            return list(self.hotkeys)

        if isinstance(hk_groups, str):
            hk_groups = [hk_groups]

        elements = []
        for hotkey in self.hotkeys:
            hotkey_action, hotkey_binding, hotkey_shortcut, hotkey_group = settings.hotkeys[hotkey]
            if hotkey_group in hk_groups:
                elements.append(hotkey)

        return elements


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
        self.roles = None
        self.logged_in = False
        self.admin = False

    def _prepare_conn_str(self, database: str = None):
        """
        Prepare the connection string.
        """
        db = database if database is not None else settings.prog_db

        #return {'UID': self.uid, 'PWD': self.pwd, 'Database': db}
        return {'UID': self.uid, 'PWD': cipher.decrypt(self.pwd).decode('utf-8'), 'Database': db}

    def login_new(self, uid, pwd, timeout: int = 10):
        """
        Verify username and password exists in the database accounts table and obtain user permissions.

        Args:
            uid (str): existing account username.

            pwd (str): password associated with the existing account.

            timeout (int): server connection timeout.
        """
        # Prepare the server request
        value = {'connection_string': self._prepare_conn_str()}
        content = {'action': 'db_login', 'value': value}
        request = {'content': content, 'encoding': "utf-8"}

        # Send the request for data to the server
        response = server_conn.process_request(request, timeout=timeout)
        if response['success'] is False:
            msg = response['value']
            logger.error(msg)

            return False

        self.uid = uid
        self.pwd = cipher.encrypt(pwd.encode('utf-8'))
        self.roles = response['value']
        self.logged_in = True

        return True

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
        params = (uid,)

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

    def access_permissions_new(self):
        """
        Return escalated privileges for a given user group.
        """
        ugroup = self.group

        if ugroup == 'admin':
            return ['admin', 'user']
        else:
            return ['user']

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

            raise ConnectionError(msg)
        else:
            try:
                df = pd.DataFrame(response['value'])
            except Exception as e:
                msg = 'failed to read the results of the database query - {ERR}'.format(ERR=e)
                logger.error(msg)

                raise

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


def popup_error(msg):
    """
    Display popup notifying user that there is a fatal program error.
    """
    font = mod_const.LARGE_FONT
    return sg.popup_error(textwrap.fill(msg, width=40), font=font, title='')


def load_config(cnfg_file):
    """
    Load the contents of the configuration file into a python dictionary.
    """
    try:
        fh = open(cnfg_file, 'r', encoding='utf-8')
    except FileNotFoundError:
        msg = 'Unable to load user settings file at {PATH}. Please verify that the file path is correct.' \
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
cnf_file = os.path.join(os.getcwd(), 'settings.yaml')
if os.path.exists(cnf_file):  # first attempt to find configuration from the current working directory
    CNF_FILE = cnf_file
else:  # fallback to default config in the program directory
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
