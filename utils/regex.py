import re
EMAIL_REGEX='^(([^<>()[\]\\.,;:\s@"]+(\.[^<>()[\]\\.,;:\s@"]+)*)|.(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$'
PASSWORD_REGEX='^(?=.*[0-9])(?=.*[a-z])(?=.*[!"#$%&\'*+,-./:;<=>?@\^_`|~])[a-zA-Z0-9!"#$%&\'*+,-./:;<=>?@\^_`|~]{8,}$'

def verify_password_schema(password):
    regex = re.search(PASSWORD_REGEX, password)
    return regex

def verify_email_schema(email):
    regex = re.search(EMAIL_REGEX, email)
    return regex


