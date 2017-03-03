from pprint import pprint

from clify import command_line


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
