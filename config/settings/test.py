from .dev import *  # noqa: F401,F403

# Real PBKDF2 hashing is what's slow (~0.9s/call on this machine) and each
# test's setUp() hashes several passwords creating fixture users — hashing
# strength isn't what's under test, so use the fastest hasher here.
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
