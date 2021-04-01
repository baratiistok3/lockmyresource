import logging


try:
    from memory_profiler import profile
    memprofiled = profile
    logging.warning("Using memory_profiler")
except ImportError:
    def memprofiled(func):
        return func
    logging.info("Not using memory profiler")


def traced(func):
    def inner(*args, **kwargs):
        logging.debug("%s(%s, %s)", func.__name__, args, kwargs)
        result = func(*args, **kwargs)
        logging.debug("{%s} returns {%s}", func.__name__, result)
        return result

    return inner


def memprofiled2(func):
    if profile is None:
        return func

    # def inner(*args, **kwargs):
    #     result = func(*args, **kwargs)
    #     return result    

    return profile(func)
