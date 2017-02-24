# For command_line
from pprint import pprint, pformat
import inspect
import argparse
from future.utils import raise_from


def command_line(func, verbose=False, cl_args=None, allow_abrev=True):
    """ Turn a function into a script that accepts arguments from the command line.

    Inspects the signature of the modified function to get default values. Arguments
    that are passed in from the command line are automatically cast to have the same
    type as the default argument unless the default is None.

    The modified function can accept arguments both programmatically and from
    the command line. Casting is not performed for arguments received programmatically.
    For positional arguments, arguments passed programmatically come *before* arguments
    passed from the command line.

    Supports functions with * and **.

    Function arguments may not be named ``__positional``; this is a reserved name used
    used to capture positional arguments from the command line.

    Example
    -------

    script.py:
    ------------------
    def f(x=1):
        print(x+1)

    command_line(f)()
    ------------------

    Run it:

    python script.py --x 3
    --> 4

    or

    python script.py 2
    --> 3

    or

    python script.py
    --> 2

    Parameters
    ----------
    func: function
        The function to modify.
    verbose: bool
        If true, before calling the function, prints the arguments that
        it will be called with.
    cl_args: str
        String of command line arguments to be used in place of arguments from the
        actual command line, useful for testing.

    """
    EMPTY = object()

    # Construct a list called ``defaults`` of the form (arg_name, default_value, is_kw_only)
    try:
        # python 3
        from inspect import Parameter
        kinds = (Parameter.KEYWORD_ONLY, Parameter.POSITIONAL_OR_KEYWORD)
        signature = inspect.signature(func)
        defaults = [
            (pn, (EMPTY if p.default is Parameter.empty else p.default), p.kind is Parameter.KEYWORD_ONLY)
            for pn, p in signature.parameters.items()
            if p.kind in kinds]
    except AttributeError:
        # python 2
        args, varargs, keywords, _defaults = inspect.getargspec(func)
        _defaults = [EMPTY] * (len(args) - len(_defaults)) + _defaults
        defaults = zip(args, _defaults, [False] * len(args))

    # Using ``defaults``, create a command line argument parser that automatically
    # casts provided arguments to the same type as the default argument, unless default is None.
    parser = argparse.ArgumentParser(
        "Automatically generated argument parser for function {}.".format(func.__name__))
    parser.add_argument('__positional', nargs='*')

    NOT_PROVIDED = object()

    for param_name, default, _ in defaults:
        option = '--' + param_name.replace('_', '-')
        default_type = None if (default is EMPTY or default is None) else type(default)

        parser.add_argument(
            option,
            type=default_type,
            default=NOT_PROVIDED,
            help=type(default).__name__)

    def g(*pargs, **kwargs):
        cl_arg_vals, extra_cl = parser.parse_known_args(cl_args.split())

        # Match each cl-provided positional argument with an argument name,
        # perform a cast if the name has an associated default value
        cl_pargs = cl_arg_vals.__positional

        for i in range(len(cl_pargs)):
            param_name, default, kw_only = defaults[i + len(pargs)]

            if not kw_only and (default not in (None, EMPTY)):
                try:
                    cl_pargs[i] = type(default)(cl_pargs[i])
                except Exception as e:
                    new_e = TypeError(
                        "Exception raised while trying to convert object "
                        "{} to type {} for param with name {}.".format(
                            repr(cl_pargs[i]), repr(type(default).__name__), repr(param_name)))
                    raise_from(new_e, e)

        pargs = list(pargs) + list(cl_pargs)

        # Constuct a dictionary of command line-provided key word args.
        cl_kwargs = {pn: value
                     for pn, value in cl_arg_vals.__dict__.items()
                     if value is not NOT_PROVIDED and pn is not '__positional'}

        # Parse extra command line-provided kwargs (corresponds to **kwargs) in the wrapped function.
        # Supported formats are ``--key=value`` and ``--key value``.
        extra_kwargs = {}
        _key = None
        for s in extra_cl:
            if _key is None:
                if not s.startswith('--'):
                    raise RuntimeError("Expected string beginning with --, got {}.".format(s))
                if '=' in s:
                    idx = s.index('=')
                    _key = s[2:idx]
                    _value = s[idx + 1:]
                    extra_kwargs[_key] = _value
                    _key = None
                else:
                    _key = s[2:]
            else:
                if s.startswith('--'):
                    raise RuntimeError("Expected value for option {}, got {}.".format(_key, s))
                extra_kwargs[_key] = s
                _key = None
        if _key is not None:
            raise RuntimeError("Expected value for option {}, none provided.".format(_key))

        overlap = set(kwargs) & set(cl_kwargs) & set(extra_kwargs)
        if overlap:
            raise TypeError("{} got multiple values for argument(s): {}.".format(func.__name__, pformat(overlap)))

        kwargs.update(cl_kwargs)
        kwargs.update(extra_kwargs)

        if verbose:
            print("Calling function {} with\nargs:\n{}\nkwargs:\n{}".format(func.__name__, pformat(pargs), pformat(kwargs)))

        return func(*pargs, **kwargs)

    return g


def f(a, x=1):
    pprint("Locals:")
    pprint(locals())


def f2(y=20, *, x=1):
    pprint("Locals:")
    pprint(locals())


def f3(a, b, c, x=20, *p, y=1, z=0, **kwargs):
    pprint("Locals:")
    pprint(locals())


if __name__ == "__main__":
    command_line(f3, verbose=True, cl_args='b c 0 p1 p2 --y=1 --w 10 --k=hellothere')(['a'], z=['z'])
