import re
import string
import random
import hashlib


def validate_uname(username):
    r = re.compile("^[a-zA-Z0-9_-]{3,20}$")
    if r.match(username):
        return username
    else:
        return False


def validate_pw(password):
    r = re.compile("^.{3,20}$")
    if r.match(password):
        return password
    else:
        return False


def make_salt(length):
    salt = ""
    chars = string.letters + string.digits
    for i in range(length):
        salt += random.choice(chars)
    return salt


def hashs(password, salt = None, salt_length=6):
    if not salt:
        salt = make_salt(salt_length)
    return hashlib.sha256(password + salt).hexdigest() + salt


class UsernameTaken(Exception):
    def __init__(self, message):
        self.message = message
    
    def __str__(self):
        return repr(self.message)


class LoginError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return repr(self.message)


class PasswordError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return repr(self.message)


class UsernameError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return repr(self.message)


