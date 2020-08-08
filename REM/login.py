import hashlib
import PySimpleGUI as sg
import sys

# Classes
class Authentication():
    """Class to manage user accounts and logins.
    """
    def login(self, username:str=None, password:str=None)
        """
        Verify username and password exists in the database accounts table
        and obtain user permissions.

        Args:
            username (str): existing account username.

            password (str): password associated with the existing account.
        """
        pass_hash =  hash_password(password)
        db_user, db_pass, db_admin = query_db(username)

        if pass_hash != db_pass:
            raise PasswordMismatchError

        if not db_user:
            raise MissingUserError

        if exists and db_admin:
            user = AdminUserAccount()
        elif exists and not admin:
            user = UserAccount()
        else:
            user = None

        return(user)


    def register(self, username:str=None, password:str=None, superuser:bool=False):
        """
        Register a new user in the database accounts table.

        Args:
            username (str): new account username.

            password (str): new account password.

            superuser (bool): new account is a admin account
        """
        pass


class UserAccount:
    """
    Class to store user account information, such as name, pw, and associated
    security group.

    Attributes:
        name (str): existing account username.

        password (str): hash value for associated account password.

        _superuser (bool): existing account is an admin account.
    """

    def __init__(self):
        """
        """
        self._name = None
        self._password = None
        self._superuser = False

    def change_username(self, username):
        """
        Change the username associated with the account.

        Args:
            username (str): new username to be associated with the account.
        """
        success = True
        # Change username in database accounts table
        new_row = [username, self._password, self._superuser]
        self.update_account(username, new_row)

        self._name = username

        return(success)

    def change_password(self, password):
        """
        Change the password associated with the account.

        Args:
            password (str): new password to be associated with the account.
        """
        success = True
        pass_hash = hash_password(password)

        new_row = [self._user, pass_hash, self._superuser]
        self.update_account(username, new_row)

        self._password = pass_hash

        return(success)


class AdminUserAccount(UserAccount):
    """Class to change
    """

    def change_permissions(self, group):
        """
        """
        pass

# Functions
def hash_password(password):
    """
    Obtain passwords hash-code.
    """
    password_utf = password.encode('utf-8')
    sha1hash = hashlib.sha1()
    sha1hash.update(password_utf)
    password_hash = sha1hash.hexdigest()
    return(password_hash)

# Layouts
def login_layout():
    """
    """
    column_layout = [[sg.Image()], [sg.Input('', size=(20, 1), tooltip='Input account username')], [sg.Input('', size=(20, 1), do_not_clear=False, tooltip='Input account password', password_char='*')], [sg.Text('', pad=(20, 20))], [sg.Button('Sign In', size=(20, 1), button_color='Green')]]

    layout = [[sg.Col(column_layout, justification='center', element_justification='center', pad=(20, 20))]]

    return(layout)
