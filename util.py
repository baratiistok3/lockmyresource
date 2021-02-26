import logging


def traced(func):
    def inner(*args, **kwargs):
        logging.debug("%s(%s, %s)", func.__name__, args, kwargs)
        result = func(*args, **kwargs)
        logging.debug("{%s} returns {%s}", func.__name__, result)
        return result

    return inner
