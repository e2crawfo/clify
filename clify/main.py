import inspect
import argparse
import warnings
import types
from pprint import pformat


class _NOT_PROVIDED:
    def __str__(self):
        return "NotProvided"

    def __repr__(self):
        return str(self)


class _EMPTY:
    def __str__(self):
        return "Empty"

    def __repr__(self):
        return str(self)


NOT_PROVIDED = _NOT_PROVIDED()
EMPTY = _EMPTY()


class _bool(object):
    def __new__(cls, val):
        if val in ("0", "False", "F", "false", "f"):
            return False
        return bool(val)


class CommandLineFunction(object):
    """ Turn a function into a script that accepts arguments from the command line.

    Inspects the signature of the modified function to get default values. Arguments
    that are passed in from the command line are automatically cast to have the same
    type as the default argument unless the default is None.

    The modified function can accept arguments both programmatically and from
    the command line. Casting is not performed for arguments received programmatically.
    For positional arguments, arguments passed programmatically come *before* arguments
    passed from the command line.

    Supports functions with an * in their signature, and functions with an ** in their
    signature if ``collect_kwargs`` is True.

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
        or later. Ignored if ``parser`` is supplied.
    collect_kwargs: bool
        Whether command line arguments that do not correspond to one of the wrapped function's
        parameter names will be collected into a list and turned into a dictionary
        that is then passed to the wrapped function using ** notation.
        Can be useful to turn this off if, for instance, we want to leave some of the arguments
        for argument parsers that may come later.
    strict: bool
        If True, raise a ValueError if kwargs are provided whose keys are not function
        argument names. This can be useful for protecting against spelling mistakes when providing
        arguments, but only makes sense when using a single parser.
    parser: ArgumentParser instance (optional)
        Add arguments to an existing parser rather than creating a new one.
    message: str (optional)
        A message to print when the user requests help. Ignored if ``parser`` is supplied.

    """
    def __init__(
            self, wrapped, verbose=False, cl_args=None, allow_abbrev=False,
            collect_kwargs=False, strict=False, parser=None, message=None):

        self.wrapped = wrapped
        self.verbose = verbose
        self.cl_args = cl_args
        self.allow_abbrev = allow_abbrev
        self.collect_kwargs = collect_kwargs
        self.strict = strict
        assert not (collect_kwargs and strict)
        self.parser = parser
        self.message = message

        build_parser_kwargs = locals().copy()
        del build_parser_kwargs['self']
        self.defaults, self.parser = self._build_arg_parser(wrapped, allow_abbrev, parser, message)

    def _build_arg_parser(self, wrapped, allow_abbrev, parser, message):

        # Construct a list called ``defaults`` of the form (arg_name, default_value, is_kw_only)
        try:
            # python 3
            from inspect import Parameter
            kinds = (Parameter.KEYWORD_ONLY, Parameter.POSITIONAL_OR_KEYWORD)
            signature = inspect.signature(wrapped)
            defaults = [
                (pn, (EMPTY if p.default is Parameter.empty else p.default), p.kind is Parameter.KEYWORD_ONLY)
                for pn, p in signature.parameters.items()
                if p.kind in kinds]
        except ImportError:
            # python 2
            args, varargs, keywords, _defaults = inspect.getargspec(wrapped)
            _defaults = list(_defaults or [])
            _defaults = [EMPTY] * (len(args) - len(_defaults)) + _defaults
            defaults = zip(args, _defaults, [False] * len(args))

        # Using ``defaults``, create a command line argument parser that automatically
        # casts provided arguments to the same type as the default argument, unless default is None.
        if parser is None:
            if not message:
                message = ("Automatically generated argument parser for "
                           "wrapped function {}.".format(wrapped.__name__))
            try:
                parser = argparse.ArgumentParser(message, allow_abbrev=allow_abbrev)
            except TypeError:
                if not allow_abbrev:
                    warnings.warn("clify argument ``allow_abbrev`` set to False, but abbrevation functionality "
                                  "cannot be turned off in versions of python earlier than 3.5.")
                parser = argparse.ArgumentParser(message)
        else:
            assert isinstance(parser, argparse.ArgumentParser)

        for param_name, default, _ in defaults:
            option = '--' + param_name.replace('_', '-')
            default_type = None if (default is EMPTY or default is None) else type(default)
            default_type = _bool if default_type is bool else default_type

            parser.add_argument(
                option,
                type=default_type,
                default=NOT_PROVIDED,
                help=type(default).__name__)

        return defaults, parser

    def __call__(self, *pargs, **kwargs):
        """ Uses a specially constructed ArgumentParser to parse arguments
            from the command line and pass them to the wrapped function.

        """
        cl_arg_vals, extra_cl = self.parser.parse_known_args(
            self.cl_args.split() if self.cl_args is not None else None)

        return self.call_after_parse(cl_arg_vals, *pargs, extra_cl=extra_cl, **kwargs)

    def call_after_parse(self, cl_arg_vals, *pargs, extra_cl=None, **kwargs):
        extra_kwargs = _parse_extra_kwargs(extra_cl)
        if self.strict and extra_kwargs:
            raise ValueError(
                "\"strict\" kwarg parsing is turned on, but received "
                "unrecognized kwargs:\n{}".format(pformat(extra_kwargs)))
        if not self.collect_kwargs:
            extra_kwargs = {}

        cl_kwargs = {pn: value
                     for pn, value in cl_arg_vals.__dict__.items()
                     if value is not NOT_PROVIDED}

        overlap = set(kwargs) & set(cl_kwargs) & set(extra_kwargs)
        if overlap:
            raise TypeError("{} got multiple values for argument(s): {}.".format(self.wrapped.__name__, pformat(overlap)))

        kwargs.update(cl_kwargs)
        kwargs.update(extra_kwargs)

        if self.verbose:
            print("Calling wrapped function {} with\nargs:\n{}\nkwargs:\n{}".format(
                self.wrapped.__name__, pformat(pargs), pformat(kwargs)))

        return self.wrapped(*pargs, **kwargs)


class DictWrapper(object):
    def __init__(self, dct):
        self.dct = dct

    def __str__(self):
        return "DictWrapper({})".format(pformat(self.dct))

    def __repr__(self):
        return str(self)

    def __dir__(self):
        return self.dct.keys()

    def __getattr__(self, key):
        try:
            return self.dct[key]
        except KeyError:
            raise AttributeError(str(key))


class CommandLineObject(object):
    """ Create an argument parser from an object.

    Accepts arguments for each of the the object's non-hidden, non-method attributes.

    """
    def __init__(
            self, obj, verbose=False, cl_args=None, allow_abbrev=False,
            collect_kwargs=False, strict=False, parser=None, message=None):

        self.obj = DictWrapper(obj) if isinstance(obj, dict) else obj

        self.verbose = verbose
        self.cl_args = cl_args
        self.allow_abbrev = allow_abbrev
        self.collect_kwargs = collect_kwargs
        self.strict = strict
        assert not (collect_kwargs and strict)
        self.parser = parser
        self.message = message

        build_parser_kwargs = locals().copy()
        del build_parser_kwargs['self']
        self.parser = self._build_arg_parser(self.obj, allow_abbrev, parser, message)

    @staticmethod
    def _build_arg_parser(obj, allow_abbrev, parser, message):
        if parser is None:
            message = message or "Automatically generated argument parser for object {}.".format(obj)
            try:
                parser = argparse.ArgumentParser(message, allow_abbrev=allow_abbrev)
            except TypeError:
                if not allow_abbrev:
                    warnings.warn("clify argument ``allow_abbrev`` set to False, but abbrevation functionality "
                                  "cannot be turned off in versions of python earlier than 3.5.")
                parser = argparse.ArgumentParser(message)
        else:
            assert isinstance(parser, argparse.ArgumentParser)

        for attr in list_attrs(obj):
            default = getattr(obj, attr)

            if '_' in attr:
                option_strings = [attr, attr.replace('_', '-')]
            else:
                option_strings = [attr]
            option_strings = ['--' + os for os in option_strings]

            default_type = None if (default is EMPTY or default is None) else type(default)
            default_type = _bool if default_type is bool else default_type

            parser.add_argument(
                *option_strings,
                type=default_type,
                default=NOT_PROVIDED,
                help=type(default).__name__)

        return parser

    def parse(self, **kwargs):
        """ Returns a dictionary containing entries only for attributes that were given non-default values. """
        cl_arg_vals, extra_cl = self.parser.parse_known_args(
            self.cl_args.split() if self.cl_args is not None else None)

        extra_kwargs = _parse_extra_kwargs(extra_cl)
        if self.strict and extra_kwargs:
            raise ValueError(
                "\"strict\" kwarg parsing is turned on, but received "
                "unrecognized kwargs:\n{}".format(pformat(extra_kwargs)))
        if not self.collect_kwargs:
            extra_kwargs = {}

        cl_kwargs = {pn: value
                     for pn, value in cl_arg_vals.__dict__.items()
                     if value is not NOT_PROVIDED}

        overlap = set(kwargs) & set(cl_kwargs) & set(extra_kwargs)
        if overlap:
            raise TypeError("{} got multiple values for argument(s): {}.".format(self.obj.__name__, pformat(overlap)))

        kwargs.update(cl_kwargs)
        kwargs.update(extra_kwargs)

        if self.verbose:
            print("Built dict from command line args:\n{}".format(kwargs))

        return kwargs


def list_attrs(obj):
    return (
        attr for attr in dir(obj)
        if (not attr.startswith('_')
            and not isinstance(getattr(obj, attr), types.MethodType)))


def _parse_extra_kwargs(extra_cl):
    """ Parse extra command line-provided kwargs in the wrapped function.

    Such arguments are passed to the wrapped function via **kwargs
    if ``collect_kwargs`` is True. Supported formats are ``--key=value``
    and ``--key value``. Positional arguments are ignored.

    Parameters
    ----------
    extra_cl: list of str
        Extra command line arguments, as given by second return value from ``parse_known_args``.

    """
    extra_kwargs = {}
    _key = None
    for s in extra_cl:
        if _key is None:
            if s.startswith('--'):
                if '=' in s:
                    # --key=value
                    idx = s.index('=')
                    _key = s[2:idx]
                    _value = s[idx + 1:]
                    extra_kwargs[_key] = _value
                    _key = None
                else:
                    _key = s[2:]
            else:
                # positional
                pass
        else:
            if s.startswith('--'):
                raise RuntimeError("Expected value for option {}, got {}.".format(_key, s))
            extra_kwargs[_key] = s
            _key = None

    if _key is not None:
        raise RuntimeError("Expected value for option {}, none provided.".format(_key))

    return extra_kwargs


def wrap_function(
        wrapped, verbose=False, cl_args=None, allow_abbrev=False,
        collect_kwargs=False, strict=False, parser=None, message=None):
    return CommandLineFunction(**locals().copy())


wrap_function.__doc__ = CommandLineFunction.__doc__


def wrap_object(
        obj, verbose=False, cl_args=None, allow_abbrev=False,
        collect_kwargs=False, strict=False, parser=None, message=None):
    return CommandLineObject(**locals().copy())


wrap_object.__doc__ = CommandLineObject.__doc__


def command_line(wrapped, *args, **kwargs):
    if callable(wrapped):
        return wrap_function(wrapped, *args, **kwargs)
    else:
        return wrap_object(wrapped, *args, **kwargs)
