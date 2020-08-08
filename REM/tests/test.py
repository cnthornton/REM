"""
"""
import random
import string


def rand_str():
    return ''.join(random.choice(string.ascii_lowercase) for i in range(10))

def rand_int(min_val=500, max_val=10000):
    return random.randint(min_val, max_val)

