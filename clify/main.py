import inspect
import argparse
import warnings
from future.utils import raise_from
from pprint import pformat


def command_line(func, verbose=False, cl_args=None, allow_abbrev=True, collect_kwargs=False, message=None):
    """ Turn a function into a script that accepts arguments from the command line.

    Inspects the signature of the modified function to get default values. Arguments
    that are passed in from the command line are automatically cast to have the same
    type as the default argument unless the default is None.

    The modified function can accept arguments both programmatically and from
    the command line. Casting is not performed for arguments received programmatically.
    For positional arguments, arguments passed programmatically come *before* arguments
    passed from the command line.

    Supports functions with *, and supports functions with ** if ``collect_kwargs`` is True.

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
        The function to wrap.
    verbose: bool
        If true, before calling the wrapped function, prints the arguments that
        it will be called with.
    cl_args: str
        String of command line arguments to be used in place of arguments from the
        actual command line, useful for testing.
    allow_abbrev: bool
        Whether to allow user to specify arguments using unambiguous abbreviations of
        the actual argument name. Defaults to True, can only be turned off in python 3.5
        or later.
    collect_kwargs: bool
        Whether command line arguments that do not correspond to one of the wrapped function's
        parameter names will be collected into a list and turned into a dictionary
        that is then passed to the wrapped function using ** notation. Defaults to True.
        Can be useful to turn this off if, for instance, we want to leave some of the arguments
        for argument parsers that may come later.
    message: str (optional)
        A message to print when the user requests help.

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
    except ImportError:
        # python 2
        args, varargs, keywords, _defaults = inspect.getargspec(func)
        _defaults = [EMPTY] * (len(args) - len(_defaults)) + list(_defaults)
        defaults = zip(args, _defaults, [False] * len(args))  # No kw-only args in python 2

    # Using ``defaults``, create a command line argument parser that automatically
    # casts provided arguments to the same type as the default argument, unless default is None.
    message = message or "Automatically generated argument parser for function {}.".format(func.__name__)
    try:
        parser = argparse.ArgumentParser(message, allow_abbrev=allow_abbrev)
    except TypeError:
        if not allow_abbrev:
            warnings.warn("clify argument ``allow_abbrev`` set to False, but abbrevation functionality "
                          "cannot be turned off in versions of python earlier than 3.5.")
        parser = argparse.ArgumentParser(message)

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
        cl_arg_vals, extra_cl = parser.parse_known_args(
            cl_args.split() if cl_args is not None else None)

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

        extra_kwargs = _parse_extra_kwargs(extra_cl) if collect_kwargs else {}

        overlap = set(kwargs) & set(cl_kwargs) & set(extra_kwargs)
        if overlap:
            raise TypeError("{} got multiple values for argument(s): {}.".format(func.__name__, pformat(overlap)))

        kwargs.update(cl_kwargs)
        kwargs.update(extra_kwargs)

        if verbose:
            print("Calling function {} with\nargs:\n{}\nkwargs:\n{}".format(func.__name__, pformat(pargs), pformat(kwargs)))

        return func(*pargs, **kwargs)

    return g


def _parse_extra_kwargs(extra_cl):
    """ Parse extra command line-provided kwargs in the wrapped function.

    Such arguments are passed to the wrapped function via **kwargs
    if ``collect_kwargs`` is True. Supported formats are ``--key=value``
    and ``--key value``.

    Parameters
    ----------
    extra_cl: list of str
        Extra command line arguments, as given by second return value from ``parse_known_args``.

    """
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

    return extra_kwargs
