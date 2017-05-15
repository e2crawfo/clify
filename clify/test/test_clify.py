from pprint import pprint
import clify
from clify.main import list_attrs


def f(a, b, c, x=20, *p, w='1', y=1, z=0, **kwargs):
    pprint("Locals:")
    pprint(locals())
    return locals()


def test_wrap_function():
    wrapped = clify.wrap_function(f, verbose=True, collect_kwargs=True,
                                  cl_args='b c 0 p1 p2 --w=1 --y=1 --k=hellothere --l 0.01')
    f_locals = wrapped(['a'], z=['z'])
    assert tuple(f_locals['a']) == ('a',)
    assert f_locals['b'] == 'b'
    assert f_locals['x'] == 0
    assert tuple(f_locals['p']) == ('p1', 'p2')
    assert f_locals['w'] == '1'
    assert f_locals['y'] == 1
    assert tuple(f_locals['z']) == ('z',)  # No cast performed because passed in programmatically
    assert f_locals['kwargs']['k'] == 'hellothere'
    assert f_locals['kwargs']['l'] == '0.01'


class A(object):
    u = '10'
    v = '10'
    w = 10
    x = 0
    y = 'temp'
    z = 2

    def __str__(self):
        s = ["\n< {}".format(self.__class__.__name__)]
        for attr in list_attrs(self):
            value = getattr(self, attr)
            s.append("    {}={} ({}),".format(attr, value, type(value).__name__))
        return '\n'.join(s) + '\n>\n'

    def __repr__(self):
        return str(self)


def test_wrap_object():
    a = A()
    a.c = 20
    wrapped = clify.wrap_object(a, cl_args='--x=2 --y 3 --a 100 --c 21', verbose=True, collect_kwargs=True)
    result = wrapped.parse(v=10, w=10, b=100)
    pprint(result)

    assert a.u == '10'
    assert a.v == '10'
    assert a.w == 10
    assert a.x == 0
    assert a.y == 'temp'
    assert a.z == 2

    assert a.c == 20
    assert not hasattr(a, 'a')
    assert not hasattr(a, 'b')

    assert result.u == '10'
    assert result.v == 10  # not cast because supplied programmatically
    assert result.w == 10
    assert result.x == 2
    assert result.y == '3'
    assert result.z == 2

    assert result.a == '100'
    assert result.b == 100
    assert result.c == 21


if __name__ == "__main__":
    test_wrap_function()
    test_wrap_object()
