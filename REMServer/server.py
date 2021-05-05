# -*- coding: utf-8 -*-
"""
REM server.
"""

__version__ = '0.2.3'

from multiprocessing import freeze_support
import logging
import logging.handlers as handlers
#import io
import os
import selectors
import socket
import struct
import sys

from bson import json_util
#import json
import pandas as pd
from pandas.io import sql
import pyodbc
import yaml
from pymongo import MongoClient, errors
import win32serviceutil
import win32service
import servicemanager


class WinServiceManager(win32serviceutil.ServiceFramework):
    _svc_name_ = 'REMServer'
    _svc_display_name_ = 'REM Server'
    _svc_description_ = 'Revenue & Expense Management Server'

    def SvcStop(self):
        """
        Stop the service.
        """
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.service_impl.stop()
        self.ReportServiceStatus(win32service.SERVICE_STOPPED)

    def SvcDoRun(self):
        """
        Start the service.
        """
        self.ReportServiceStatus(win32service.SERVICE_START_PENDING)
        self.service_impl = WinService()
        self.ReportServiceStatus(win32service.SERVICE_RUNNING)
        self.service_impl.run()


class WinService:

    def __init__(self):
        self.running = False

    def stop(self):
        """
        Indicate that service has stopped to terminate the main loop.
        """
        logger.info('stopping the server')
        self.running = False

    def run(self):
        """
        Main service loop.
        """
        self.running = True
        # Load the contents of the configuration file into a python dictionary
        logger.info('loading parameters from the configuration file {}'.format(CNF_FILE))
        try:
            cnfg = load_config(CNF_FILE)
        except Exception:
            logger.exception('failed to load the configuration file')
            raise

        # Configuring the logger
        for handler in logger.handlers[:]:  # removes existing file handlers
            logger.removeHandler(handler)
        logger.addHandler(configure_handler(DIR, cnfg))

        # Load the configuration
        logger.info('initializing program managers')
        configuration.load_configuration(cnfg)

        # Start listening for connections
        logger.info('starting the server')
        logger.info('running REM server version {VER}'.format(VER=__version__))

        sel = selectors.DefaultSelector()
        lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        lsock.bind((configuration.host, configuration.port))
        lsock.listen()
        logger.info('server {HOST} is listening for connections on port {PORT}'
                    .format(HOST=configuration.host, PORT=configuration.port))
        lsock.setblocking(False)
        sel.register(lsock, selectors.EVENT_READ, data=None)

        # Start main loop
        try:
            while self.running:
                events = sel.select(timeout=None)
                for key, mask in events:
                    if key.data is None:  # open connection to client
                        sock = key.fileobj
                        conn, addr = sock.accept()  # should be ready to read
                        logger.info('accepted connection from {ADDR}'.format(ADDR=addr))
                        conn.setblocking(False)
                        message = ClientConnection(sel, conn, addr)
                        sel.register(conn, selectors.EVENT_READ, data=message)
                    else:  # process a client request / return data
                        message = key.data
                        try:
                            message.process_events(mask)
                        except Exception:
                            # Close and remove the connection to the client if any exception raised
                            logger.exception('failed to process client {ADDR} event ... closing the connection'
                                             .format(ADDR=message.addr))
                            message.close()
        except Exception:
            logger.exception('server {HOST} no longer monitoring connections on port {PORT}'
                             .format(HOST=configuration.host, PORT=configuration.port))
        finally:
            sel.close()

        lsock.close()


class ClientConnection:
    """
    Class to process incoming communications from a client.

    Attributes:
        selector (selector): selector object.

        sock (socket): socket connection object.

        addr (str): client network address.

        request (dict): incoming client request. Composed of two parts - the action to be performed and the action
        arguments.

        response_created (bool): indicates whether a response to a request has already been created or not
        [default: False].
    """

    def __init__(self, selector, sock, addr):
        """
        Arguments:
            selector (selector): selector object.

            sock (str): socket connection.

            addr (str): client address.
        """
        self.selector = selector
        self.sock = sock
        self.addr = addr

        # Dynamic attributes
        self._recv_buffer = b""
        self._send_buffer = b""
        self._header_len = None
        self.header = None
        self.request = None
        self.action = None
        self.response_created = False

    def _reset(self):
        """
        Reset attributes.
        """
        self._header_len = None
        self.header = None
        self.request = None
        self.response_created = False
        self.action = None
        self._recv_buffer = b""
        self._send_buffer = b""

    def _set_selector_events_mask(self, mode):
        """
        Set selector to listen for events: mode is 'r', 'w', or 'rw'.
        """
        if mode == "r":
            new_event = selectors.EVENT_READ
        elif mode == "w":
            new_event = selectors.EVENT_WRITE
        elif mode == "rw":
            new_event = selectors.EVENT_READ | selectors.EVENT_WRITE
        else:
            raise ValueError('invalid events mask mode {MODE}'.format(MODE=repr(mode)))

        self.selector.modify(self.sock, new_event, data=self)

    def _read(self):
        try:
            # Should be ready to read
            data = self.sock.recv(4096)
        except BlockingIOError:
            # Resource temporarily unavailable (errno EWOULDBLOCK)
            pass
        else:
            if data:
                self._recv_buffer += data
            else:
                raise RuntimeError("Peer connection closed")

    def _write(self):
        if self._send_buffer:
            try:
                # Should be ready to write
                sent = self.sock.send(self._send_buffer)
            except BlockingIOError:
                # Resource temporarily unavailable (errno EWOULDBLOCK)
                pass
            else:
                self._send_buffer = self._send_buffer[sent:]

    def _encode(self, obj, encoding):
#        try:
#            response_fmt = json.dumps(obj, ensure_ascii=False).encode(encoding)
#        except TypeError:
#            logging.error('unable to serialize the response "{}" for sending'.format(obj))
#            raise
#
#        return response_fmt
        return json_util.dumps(obj).encode(encoding)

    def _decode(self, json_bytes, encoding):
#        tiow = io.TextIOWrapper(io.BytesIO(json_bytes), encoding=encoding, newline="")
#        obj = json.load(tiow)
#        tiow.close()
        obj = json_util.loads(json_bytes.decode(encoding))

        return obj

    def _create_message(self, *, content_bytes, content_encoding):
        header = {
            "byteorder": sys.byteorder,
            "content-encoding": content_encoding,
            "content-length": len(content_bytes),
        }

        header_bytes = self._encode(header, "utf-8")
        message_hdr = struct.pack(">H", len(header_bytes))
        message = message_hdr + header_bytes + content_bytes

        return message

    def _create_response(self):
        action = self.action

        try:
            value = self.request.get('value', None)
        except TypeError:
            value = None

        try:
            if action == 'db_transact':
                try:
                    transaction_type = value.get('transaction_type')
                    conn_str = value.get('connection_string')
                    statement = value.get('statement')
                    params = value.get('parameters')
                except TypeError:
                    msg = 'request value formatted incorrectly'
                    logger.error('{ADDR}: failed to create response - {ERR}'.format(ADDR=self.addr, ERR=msg))
                    content = {'success': False, 'value': msg}
                else:
                    conn_str['Server'] = configuration.odbc_server
                    conn_str['Port'] = configuration.odbc_port
                    conn_str['Driver'] = configuration.odbc_driver
                    db_manager = SQLTransactManager(conn_str)
                    if transaction_type == 'read':
                        content = db_manager.read_db(statement, params)
                    elif transaction_type == 'write':
                        if isinstance(statement, str):
                            content = db_manager.write_db(statement, params)
                            if content['success']:
                                db_manager.commit()
                        elif isinstance(statement, list) and isinstance(params, list):
                            success = True
                            for i, statement_i in enumerate(statement):
                                try:
                                    params_i = params[i]
                                except IndexError:
                                    success = False
                                    break
                                results = db_manager.write_db(statement_i, params_i)
                                if not results['success']:
                                    success = False
                                    break
                            if success:
                                db_manager.commit()
                                content = {'success': True, 'value': None}
                            else:
                                msg = 'batch write failed on transaction - {}'.format(statement)
                                content = {'success': False, 'value': msg}
                        else:
                            msg = 'write failed on transaction - unaccepted combination of statements and parameters'
                            content = {'success': False, 'value': msg}
                    else:
                        msg = 'invalid transaction type provided'
                        logger.error('{ADDR}: failed to create response - {ERR}'.format(ADDR=self.addr, ERR=msg))
                        content = {'success': False, 'value': msg}
                    db_manager.disconnect()
            elif action == 'db_schema':
                try:
                    conn_str = value.get('connection_string')
                    table = value.get('table')
                    database = value.get('database')
                except TypeError:
                    msg = 'request value formatted incorrectly'
                    logger.error('{ADDR}: failed to create response - {ERR}'.format(ADDR=self.addr, ERR=msg))
                    content = {'success': False, 'value': msg}
                else:
                    conn_str['Server'] = configuration.odbc_server
                    conn_str['Port'] = configuration.odbc_port
                    conn_str['Driver'] = configuration.odbc_driver
                    db_manager = SQLTransactManager(conn_str)
                    if table is None:
                        content = db_manager.database_tables(database)
                    else:
                        content = db_manager.table_schema(table)
                    db_manager.disconnect()
            elif action == 'constants':
                content = configuration.format_attrs(value)
            elif action == 'remove_ids':
                try:
                    record_type = value.get('record_type')
                    ids = value.get('ids')
                except TypeError:
                    msg = 'request value formatted incorrectly'
                    logger.error('{ADDR}: failed to create response - {ERR}'.format(ADDR=self.addr, ERR=msg))
                    content = {'success': False, 'value': msg}
                else:
                    content = configuration.remove_unsaved_ids(record_type, ids)
            elif action == 'add_ids':
                try:
                    record_type = value.get('record_type')
                    ids = value.get('ids')
                except TypeError:
                    msg = 'request value formatted incorrectly'
                    logger.error('{ADDR}: failed to create response - {ERR}'.format(ADDR=self.addr, ERR=msg))
                    content = {'success': False, 'value': msg}
                else:
                    content = configuration.add_unsaved_ids(record_type, ids)
            elif action == 'request_ids':
                try:
                    record_type = value.get('record_type')
                    instance = value.get('instance')
                except TypeError:
                    msg = 'request value formatted incorrectly'
                    logger.error('{ADDR}: failed to create response - {ERR}'.format(ADDR=self.addr, ERR=msg))
                    content = {'success': False, 'value': msg}
                else:
                    content = configuration.get_unsaved_ids(record_type, instance_id=instance)
            else:
                msg = 'invalid action {ACTION}'.format(ACTION=action)
                logger.error('{ADDR}: failed to create response - {ERR}'.format(ADDR=self.addr, ERR=msg))
                content = {'success': False, 'value': msg}
        except Exception as e:
            msg = 'action {ACTION} failed - {ERR}'.format(ACTION=action, ERR=e)
            logger.exception('{ADDR}: failed to create response - {ERR}'.format(ADDR=self.addr, ERR=msg))
            content = {'success': False, 'value': msg}

        content_encoding = "utf-8"
        response = {
            "content_bytes": self._encode(content, content_encoding),
            "content_encoding": content_encoding,
        }

        self.action = action

        return response

    def process_events(self, mask):
        if mask & selectors.EVENT_READ:
            self.read()
        if mask & selectors.EVENT_WRITE:
            self.write()

    def read(self):
        self._read()

        if self._header_len is None:
            self.process_protoheader()

        if self._header_len is not None:
            if self.header is None:
                self.process_header()

        if self.header:
            if self.request is None:
                self.process_request()

        if self.request:
            logger.info('receiving request "{REQ}" from {ADDR}'.format(REQ=self.action, ADDR=self.addr))
#            logger.debug('request received: {}'.format(self.request))

            # Set selector to listen for write events, we're done reading.
            self._set_selector_events_mask('w')

            # Reset attributes related to the client's request
            self._header_len = None
            self.header = None

    def write(self):
        if self.request:  # request was previously sent by client
            if not self.response_created:  # first time calling after processing query / request
                self.create_response()
                logger.info('sending response to request "{REQ}" to {ADDR}'.format(REQ=self.action, ADDR=self.addr))
#                logger.debug('response to be sent: {}'.format(self._send_buffer))

        self._write()  # call until send buffer is empty

        if self.response_created and not self._send_buffer:  # full response has been sent
            # Set selector to listen for read events and reset dynamic attributes, we're done writing.
            self._set_selector_events_mask('r')
            self._reset()

    def process_protoheader(self):
        hdrlen = 2
        if len(self._recv_buffer) >= hdrlen:
            self._header_len = struct.unpack('>H', self._recv_buffer[:hdrlen])[0]
            self._recv_buffer = self._recv_buffer[hdrlen:]

    def process_header(self):
        hdrlen = self._header_len
        buff = self._recv_buffer

        if len(buff) >= hdrlen:
            self.header = self._decode(buff[:hdrlen], "utf-8")
            self._recv_buffer = buff[hdrlen:]

            for reqhdr in ("byteorder", "content-length", "content-encoding"):
                if reqhdr not in self.header:
                    raise ValueError('missing required header component {COMP}'.format(COMP=reqhdr))

    def process_request(self):
        content_len = self.header["content-length"]

        if len(self._recv_buffer) >= content_len:
            data = self._recv_buffer[:content_len]
            self._recv_buffer = self._recv_buffer[content_len:]
            encoding = self.header["content-encoding"]
            self.request = self._decode(data, encoding)
            try:
                self.action = self.request.get('action', None)
            except TypeError:
                logger.error('an improperly formatted request was received from {ADDR}'.format(ADDR=self.addr))

    def create_response(self):
        response = self._create_response()

        message = self._create_message(**response)

        self.response_created = True
        self._send_buffer += message

    def close(self):
        logger.info("closing connection to {ADDR}".format(ADDR=self.addr))
        try:
            self.selector.unregister(self.sock)
        except Exception:
            logger.exception('unable to unregister socket connected to {ADDR}'.format(ADDR=self.addr))

        try:
            self.sock.close()
        except OSError:
            logger.exception('unable to close socket connected to {ADDR}'.format(ADDR=self.addr))
        finally:
            # Delete reference to socket object for garbage collection
            self.sock = None


class ConfigManager:
    """
    Class to manage the program configuration.
    """

    def __init__(self):

        # Socket parameters
        self.port = 65432
        self.host = 'localhost'

        # Configuration database parameters
        self.mongod_port = 27017
        self.mongod_server = 'localhost'
        self.mongod_database = 'REM'
        self.mongod_config = 'configuration'
        self.mongod_user = 'mongo'
        self.mongod_pwd = None
        self.mongod_authdb = 'REM'

        # Structured database parameters
        self.odbc_driver = 'SQL Server'
        self.odbc_server = 'localhost'
        self.odbc_port = '1433'
        self.prog_db = 'REM'
        self.default_db = 'REM'
        self.dbs = ['REM']
        self.date_format = format_date_str('YYYY-MM-DD HH:MI:SS')

        # Table field parameters
        self.creator_code = 'CreatorName'
        self.creation_date = 'CreationTime'
        self.editor_code = 'EditorName'
        self.edit_date = 'EditTime'
        self.delete_code = 'IsDeleted'
        self.id_field = 'DocNo'
        self.date_field = 'DocDate'
        self.notes_field = 'Notes'
        self.warnings_field = 'Warnings'

        # Lookup tables
        self.reference_lookup = 'RecordReferences'
        self.bank_lookup = 'BankAccounts'

        # Program configuration parameters
        self.audit_rules = None
        self.cash_rules = None
        self.bank_rules = None
        self.records = None

        # Unsaved record IDs
        self.unsaved_ids = {}

    def _load_config_file(self, cnfg):
        """
        Load attribute constants from the configuration.
        """
        # Socket parameters
        try:
            self.port = int(cnfg['server']['port'])
        except KeyError:
            self.port = 65432
        except ValueError:
            logger.error(f'unsupported value {cnfg["server"]["port"]} provided to server configuration parameter '
                         f'"port"')
            self.port = 65432

        try:
            self.host = cnfg['server']['host']
        except KeyError:
            self.host = 'localhost'

        # Configuration database parameters
        try:
            self.mongod_port = int(cnfg['configuration']['mongod_port'])
        except KeyError:
            self.mongod_port = 27017
        except ValueError:
            logger.error(f'unsupported value {cnfg["configuration"]["mongod_port"]} provided to configuration '
                          f'parameter "mongod_port"')
            self.mongod_port = 27017
        try:
            self.mongod_server = cnfg['configuration']['mongod_server']
        except KeyError:
            self.mongod_server = 'localhost'
        try:
            self.mongod_database = cnfg['configuration']['mongod_database']
        except KeyError:
            self.mongod_database = 'REM'
        try:
            self.mongod_config = cnfg['configuration']['mongod_config']
        except KeyError:
            self.mongod_config = 'configuration'
        try:
            self.mongod_user = cnfg['configuration']['mongod_user']
        except KeyError:
            self.mongod_user = 'mongo'
        try:
            self.mongod_pwd = cnfg['configuration']['mongod_pwd']
        except KeyError:
            self.mongod_pwd = ''
        try:
            self.mongod_authdb = cnfg['configuration']['mongod_authdb']
        except KeyError:
            self.mongod_authdb = 'REM'

        # Structured database parameters
        try:
            self.odbc_driver = cnfg['database']['odbc_driver']
        except KeyError:
            self.odbc_driver = 'SQL Server'
        try:
            self.odbc_server = cnfg['database']['odbc_server']
        except KeyError:
            self.odbc_server = 'localhost'
        try:
            self.odbc_port = cnfg['database']['odbc_port']
        except KeyError:
            self.odbc_port = '1433'
        try:
            self.prog_db = cnfg['database']['odbc_database']
        except KeyError:
            self.prog_db = 'REM'
        try:
            self.default_db = cnfg['database']['default_database']
        except KeyError:
            self.default_db = 'REM'
        try:
            self.dbs = cnfg['database']['databases']
        except KeyError:
            self.dbs = []
        try:
            self.date_format = format_date_str(cnfg['database']['date_format'])
        except KeyError:
            self.date_format = format_date_str('YYYY-MM-DD HH:MI:SS')
        except TypeError:
            logger.error('unsupported date format {} provided to configuration database parameter "date_format"'
                         .format(cnfg['database']['date_format']))
            self.date_format = format_date_str('YYYY-MM-DD HH:MI:SS')

        # Table field parameters
        try:
            self.creator_code = cnfg['fields']['creator_code_field']
        except KeyError:
            self.creator_code = 'CreatorName'
        try:
            self.creation_date = cnfg['fields']['creation_date_field']
        except KeyError:
            self.creation_date = 'CreationTime'
        try:
            self.editor_code = cnfg['fields']['editor_code_field']
        except KeyError:
            self.editor_code = 'EditorName'
        try:
            self.edit_date = cnfg['fields']['edit_date_field']
        except KeyError:
            self.edit_date = 'EditTime'
        try:
            self.delete_code = cnfg['fields']['delete_field']
        except KeyError:
            self.delete_code = 'IsDeleted'
        try:
            self.id_field = cnfg['fields']['id_field']
        except KeyError:
            self.id_field = 'DocNo'
        try:
            self.date_field = cnfg['fields']['date_field']
        except KeyError:
            self.date_field = 'DocDate'
        try:
            self.notes_field = cnfg['field']['notes_field']
        except KeyError:
            self.notes_field = 'Notes'
        try:
            self.warnings_field = cnfg['field']['warnings_field']
        except KeyError:
            self.warnings_field = 'Warnings'

        # Lookup tables
        try:
            self.reference_lookup = cnfg['tables']['records']
        except KeyError:
            self.reference_lookup = 'RecordReferences'
        try:
            self.bank_lookup = cnfg['tables']['mod_bank']
        except KeyError:
            self.bank_lookup = 'BankAccounts'

    def _connect(self, timeout=5000):
        """
        Connect to the NoSQL database using the pymongo odbc_driver.
        """
        logger.info('connecting to the configuration database server "{}"'.format(self.mongod_server))
        connection_info = {'username': self.mongod_user, 'password': self.mongod_pwd,
                           'host': self.mongod_server, 'port': self.mongod_port,
                           'authSource': self.mongod_authdb, 'serverSelectionTimeoutMS': timeout}
        logger.debug('connecting to the configuration database server {SERVER} with parameters {PARAMS}'
                     .format(SERVER=self.mongod_server, PARAMS=connection_info))

        try:
            cnx = MongoClient(**connection_info)
        except errors.ConnectionFailure as e:
            logger.error('connection to configuration database server "{SERVER}" failed - {ERR}'
                         .format(SERVER=self.mongod_server, ERR=e))
            cnx = None
        else:
            logger.info('successfully opened a connection to configuration database server "{}"'
                        .format(self.mongod_server))

        return cnx

    def _load_database(self):
        """
        Load the NoSQL database containing the configuration collection.
        """
        cnx = self._connect()
        if not cnx:
            return None

        logger.info('loading configuration database "{}"'.format(self.mongod_database))
        try:
            database = cnx[self.mongod_database]
        except errors.InvalidName as e:
            logger.error('cannot access database "{DB}" - {ERR}'.format(DB=self.mongod_database, ERR=e))
            database = None
        else:
            logger.info('successfully loaded configuration database "{}"'.format(self.mongod_database))

        cnx.close()

        return database

    def _load_collection(self):
        """
        Load the configuration collection.
        """
        database = self._load_database()
        if not database:
            return None

        logger.info('loading configuration database collection "{}"'.format(self.mongod_config))
        try:
            collection = database[self.mongod_config]
        except errors.InvalidName as e:
            logger.warning('failed to load configuration database collection "{COLL}" - {ERR}'
                            .format(COLL=self.mongod_config, ERR=e))
            collection = None
        else:
            logger.info('successfully loaded configuration database collection "{}"'.format(self.mongod_config))

        return collection

    def load_configuration(self, cnfg):
        """
        Load the configuration documents.
        """
        # Load configuration parameters from file
        self._load_config_file(cnfg)

        # Load configuration parameters from configuration database
        collection = self._load_collection()
        if not collection:
            logger.error('unable to load configuration from the configuration database')
            sys.exit(1)

#        self.audit_rules = self._sanitize(collection.find_one({'name': 'audit_rules'}))
#        self.cash_rules = self._sanitize(collection.find_one({'name': 'cash_rules'}))
#        self.bank_rules = self._sanitize(collection.find_one({'name': 'bank_rules'}))
#        self.records = self._sanitize(collection.find_one({'name': 'records'}))
        self.audit_rules = collection.find_one({'name': 'audit_rules'})
        self.cash_rules = collection.find_one({'name': 'cash_rules'})
        self.bank_rules = collection.find_one({'name': 'bank_rules'})
        self.records = collection.find_one({'name': 'records'})

        logger.info('configuration successfully loaded')

    def format_attrs(self, subset=None):
        """
        Format attributes for messaging.
        """
        logger.debug('formatting attributes for sending')

        if isinstance(subset, str):
            subset = [subset]

        tbl_fields = {'creator_code': self.creator_code, 'creation_date': self.creation_date,
                      'editor_code': self.editor_code, 'edit_date': self.edit_date,
                      'reference_table': self.reference_lookup, 'bank_table': self.bank_lookup,
                      'notes_field': self.notes_field, 'date_field': self.date_field, 'id_field': self.id_field,
                      'warnings_field': self.warnings_field, 'delete_field': self.delete_code}
        database_attrs = {'program_database': self.prog_db, 'default_database': self.default_db,
                          'databases': self.dbs, 'db_date_format': self.date_format}

        attrs = {'audit_rules': self.audit_rules, 'bank_rules': self.bank_rules, 'cash_rules': self.cash_rules,
                 'records': self.records, 'table_fields': tbl_fields, 'database': database_attrs}

        if subset is not None:
            attrs = {i: j for i, j in attrs if i in subset}

        return {'success': True, 'value': attrs}

    def add_unsaved_ids(self, record_type, record_ids):
        """
        Add record IDs to the dictionary of unsaved record IDs.
        """
        try:
            success = self._add_unsaved_ids(record_type, record_ids)
        except Exception as e:
            value = e
            success = False
        else:
            value = None

        return {'success': success, 'value': value}

    def _add_unsaved_ids(self, record_type, record_ids):
        """
        Add record IDs to the dictionary of unsaved record IDs.
        """
        logger.debug('adding record IDs {IDS} of type {TYPE} to the database of unsaved record IDs'
                     .format(IDS=record_ids, TYPE=record_type))

        success = True
        current_ids = self._get_unsaved_ids(record_type)
        for index, id_tup in enumerate(record_ids):
            unsaved_id = id_tup[0]
            if (not unsaved_id) or (unsaved_id in current_ids):
                continue

            try:
                self.unsaved_ids[record_type].append(id_tup)
            except (KeyError, TypeError):
                self.unsaved_ids[record_type] = [id_tup]

        return success

    def remove_unsaved_ids(self, record_type, record_ids):
        """
        Remove record IDs from the dictionary of unsaved record IDs.
        """
        if isinstance(record_ids, str):
            record_ids = [record_ids]

        logger.debug('attempting to remove record IDs {ID} of type {TYPE} from the database of unsaved record IDs'
                     .format(ID=record_ids, TYPE=record_type))

        unsaved_ids = self._get_unsaved_ids(record_type)
        failed_ids = []
        for record_id in record_ids:
            try:
                index = unsaved_ids.index(record_id)
            except IndexError:
                msg = 'ID {ID} not found in list of unsaved record IDs of type {TYPE}'\
                    .format(ID=record_id, TYPE=record_type)
                logger.debug('failed to remove record ID {ID} from the list of unsaved record IDs of type {TYPE} - '
                             '{MSG}'.format(ID=record_id, TYPE=record_type, MSG=msg))
                failed_ids.append(record_id)
            else:
                try:
                    self.unsaved_ids[record_type].pop(index)
                except KeyError:
                    msg = 'no unsaved record IDs found of type {TYPE}'.format(TYPE=record_type)
                    logger.debug('failed to remove record ID {ID} from the list of unsaved record IDs of type {TYPE} - '
                                 '{MSG}'.format(ID=record_id, TYPE=record_type, MSG=msg))
                    failed_ids.append(record_id)
                else:  # need to also remove from the list of unsaved ids so that indices remain the same
                    unsaved_ids.pop(index)

        if len(failed_ids) > 0:
            success = False
            value = 'failed to remove IDs {ID} from the list of unsaved record IDs of type {TYPE}'\
                .format(ID=failed_ids, TYPE=record_type)
        else:
            success = True
            value = None

        return {'success': success, 'value': value}

    def _get_unsaved_ids(self, record_type, instance_id: int = None):
        id_tups = self.unsaved_ids.get(record_type, None)
        if id_tups:
            if instance_id is not None:
                unsaved_ids = [i[0] for i in id_tups if i[1] == instance_id]
            else:
                unsaved_ids = [i[0] for i in id_tups]
        else:
            unsaved_ids = []

        return unsaved_ids

    def get_unsaved_ids(self, record_type, instance_id: int = None):
        """
        Return a list of record IDs from the dictionary of unsaved record IDs by record type.
        """
        logger.debug('retrieving list of IDs of type {TYPE} from the database of unsaved record IDs'
                     .format(TYPE=record_type))
        return {'success': True, 'value': self._get_unsaved_ids(record_type, instance_id)}


class SQLTransactManager:
    """
    Program account object.

    Attributes:
        server (str): ODBC server name.

        port (str): ODBC listening port.

        driver (str): ODBC driver details.
    """

    def __init__(self, conn_obj, timeout: int = 5):
        self.conn = self._connect(conn_obj, timeout=timeout)
        self.cursor = self.conn.cursor()

    def _connect(self, conn_str, timeout: int = 5):
        """
        Generate a pyODBC Connection object.
        """
        try:
            driver = conn_str['Driver']
            server = conn_str['Server']
            port = conn_str['Port']
            uid = conn_str['UID']
            pwd = conn_str['PWD']
            dbname = conn_str['Database']
        except KeyError:
            logger.error('failed to connect to the database - connection string is formatted incorrectly')
            raise
        else:
            if r'"' in pwd or r';' in pwd or r"'" in pwd:
                pwd = "{{{}}}".format(pwd)

        db_settings = {'Driver': driver,
                       'Server': server,
                       'Database': dbname,
                       'Port': port,
                       'UID': uid,
                       'PWD': pwd,
                       'Trusted_Connection': 'no'}

        conn_str = ';'.join(['{}={}'.format(k, db_settings[k]) for k in db_settings if db_settings[k]])
        logger.info('connecting to database {DB} as {UID}'.format(DB=dbname, UID=uid))

        try:
            conn = pyodbc.connect(conn_str, timeout=timeout)
        except pyodbc.Error as e:
            logger.error('failed to establish a connection to {DB} as {UID} - {ERR}'.format(DB=dbname, UID=uid, ERR=e))
            raise ConnectionError(e.args[1])
        else:
            logger.info('successfully established a connection to {DB}'.format(DB=dbname))

        return conn

    def disconnect(self):
        """
        Close the pyODBC connection.
        """
        self.cursor.close()
        self.conn.close()

    def commit(self):
        """
        Commit the executed transactions.
        """
        logger.info('committing database transactions')
        self.conn.commit()

    def database_tables(self, database):
        """
        Get database schema information.
        """
        cursor = self.cursor

        try:
            cursor_val = cursor.tables()
        except pyodbc.Error as e:
            logger.error('unable to find tables associated with database {DB} - {ERR}'.format(DB=database, ERR=e))
            status = False
            value = str(e)
        else:
            status = True
            value = [i.table_name for i in cursor_val]

        return {'success': status, 'value': value}

    def table_schema(self, table):
        """
        Get table schema information.
        """
        cursor = self.cursor
        try:
            cursor_val = cursor.columns(table=table)
        except pyodbc.Error as e:
            logger.error('unable to read the schema for table {TBL} - {ERR}'.format(TBL=table, ERR=e))
            status = False
            value = str(e)
        else:
            status = True
            value = {i.column_name: (i.type_name, i.column_size) for i in cursor_val}

        return {'success': status, 'value': value}

    def read_db(self, statement, params):
        """
        Thread database read function.
        """
        # Connect to database
        conn = self.conn

        try:
            if params:
                logger.debug('transaction statement supplied is {TSQL} with parameters {PARAMS}'
                             .format(TSQL=statement, PARAMS=params))
                df = pd.read_sql(statement, conn, params=params)
            else:
                logger.debug('transaction statement supplied is {TSQL} with no parameters'.format(TSQL=statement))
                df = pd.read_sql(statement, conn)
            value = df.replace({pd.NaT: None}).to_dict()
        except sql.DatabaseError as e:
            logger.error('database read failed - {ERR}'.format(ERR=e))
            status = False
            value = str(e)
        else:
            status = True
            logger.info('database successfully read')

        # Add return value to the queue
        return {'success': status, 'value': value}

    def write_db(self, statement, params):
        """
        Thread database write functions.
        """
        cursor = self.cursor

        if isinstance(params, list):
            if all([isinstance(i, tuple) or isinstance(i, list) for i in params]):
                params = [tuple(i) for i in params]
                cursor_func = cursor.executemany
            else:
                cursor_func = cursor.execute
        else:
            cursor_func = cursor.execute

        logger.debug('transaction statement supplied is {TSQL} with parameters {PARAMS}'
                     .format(TSQL=statement, PARAMS=params))
        try:
            cursor_func(statement, params)
        except pyodbc.Error as e:  # possible duplicate entries
            logger.error('failed to write to database - {ERR}'.format(ERR=e))
            status = False
            value = str(e)
        else:
            logger.info('database successfully written')

            status = True
            value = None

        # Add return value to the queue
        return {'success': status, 'value': value}


def format_date_str(date_str):
    """
    Format a date string for use as input to datetime method.
    """
    separators = set(':/- ')
    date_fmts = {'YYYY': '%Y', 'YY': '%y',
                 'MMMM': '%B', 'MMM': '%b', 'MM': '%m', 'M': '%-m',
                 'DD': '%d', 'D': '%-d',
                 'HH': '%H', 'MI': '%M', 'SS': '%S'}

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


def load_config(cnfg_file):
    """
    Load the contents of the configuration file into a python dictionary.
    """
    with open(cnfg_file, 'r', encoding='utf-8') as fh:
        cnfg = yaml.safe_load(fh)

    return cnfg


def configure_handler(dirname, cnfg):
    """
    Configure the rotating file handler for logging.
    """
    try:
        log_file = cnfg['log']['log_file']
    except KeyError:
        log_file = os.path.join(dirname, 'REM.log')
    try:
        log_level = cnfg['log']['log_level'].upper()
    except (KeyError, AttributeError):
        log_level = logging.WARNING
    else:
        if log_level == 'WARNING':
            log_level = logging.WARNING
        elif log_level == 'ERROR':
            log_level = logging.ERROR
        elif log_level == 'INFO':
            log_level = logging.INFO
        elif log_level == 'DEBUG':
            log_level = logging.DEBUG
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

    log_handler = handlers.RotatingFileHandler(log_file, maxBytes=nbytes, backupCount=backups, encoding='utf-8',
                                               mode='a')
    log_handler.setLevel(log_level)
    log_handler.setFormatter(formatter)

    return log_handler

# Determine if application is a script file or frozen exe
if getattr(sys, 'frozen', False):
    DIR = os.path.dirname(sys.executable)
elif __file__:
    DIR = os.path.dirname(__file__)
else:
    print('failed to determine program running directory', file=sys.stderr)
    sys.exit(1)

CNF_FILE = os.path.join(DIR, 'cnfg.yaml')

#LOG_FILE = os.path.join(DIR, 'server.log')
#LOG_FMT = '%(asctime)s: %(filename)s: %(levelname)s: %(message)s'
#LOG_LEVEL = logging.INFO
#LOG_SIZE = 5000000
#LOG_N = 5

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

#log_handler = handlers.RotatingFileHandler(LOG_FILE, maxBytes=LOG_SIZE, backupCount=LOG_N, encoding='utf-8', mode='a')
#log_handler.setLevel(LOG_LEVEL)
#log_handler.setFormatter(logging.Formatter(LOG_FMT))

#logger.addHandler(log_handler)
logger.addHandler(configure_handler(DIR, load_config(CNF_FILE)))
logger.info('logging successfully configured')

configuration = ConfigManager()

if __name__ == '__main__':
    freeze_support()
    # Initialize or start the service
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(WinServiceManager)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(WinServiceManager)
