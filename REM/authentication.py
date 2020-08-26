"""
REM authentication and user classes.
"""
import hashlib
import PySimpleGUI as sg
import sys

# Classes

# Exceptions
class UserNotFound(Exception):
    """
    Exception for when querying a user in the database returns empty.
    """
    def __init__(self,*args,**kwargs):
        Exception.__init__(self,*args,**kwargs)


class PasswordMismatch(Exception):
    """
    Exception for when password does not match user password in the database.
    """
    def __init__(self,*args,**kwargs):
        Exception.__init__(self,*args,**kwargs)


# Objects
class AuthenticationManager:
    """
    Class to manage user accounts and logins.
    """

    def register(self, username:str=None, password:str=None, superuser:bool=False):
        """
        Register a new user in the database accounts table.

        Args:
            username (str): new account username.

            password (str): new account password.

            superuser (bool): new account is a admin account
        """
        pass

    def login(self, db, username:str=None, password:str=None):
        """
        Verify username and password exists in the database accounts table
        and obtain user permissions.

        Args:
            username (str): existing account username.

            password (str): password associated with the existing account.
        """
        pass_hash =  hash_password(password)

        db_group = db.authenticate(username, password)

        if not db_group:
            return(None)

        if db_group == 'admin':
            user = AdminAccount(username, pass_hash)
        else:
            user = UserAccount(username, pass_hash)

        return(user)


class UserAccount:
    """
    Basic user account object.

    Attributes:
        _name (str): existing account username.

        _password (str): hash value for associated account password.

        _superuser (bool): existing account is an admin account.
    """

    def __init__(self, name, password):
        """
        """
        self._name = name
        self._password = password
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


class AdminAccount(UserAccount):
    """
    Admin account object.
    """
    def __init__(self, name, password):
        """
        """
        super().__init__(name, password)
        self._superuser = True

    def change_permissions(self, group):
        """
        """
        pass

# Functions
def hash_password(password):
    """
    Obtain a password's hash-code.
    """
    password_utf = password.encode('utf-8')

    md5hash = hashlib.md5()
    md5hash.update(password_utf)

    password_hash = md5hash.hexdigest()

    return(password_hash)
