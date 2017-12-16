from pprint import pprint
import clify
from clify.main import list_attrs


def f(a, b, c, x=20, *p, w='1', y=10, z=0, m=True, n=False, **kwargs):
    pprint("Locals:")
    pprint(locals())
    return locals().copy()


def test_wrap_function():
    wrapped = clify.wrap_function(f, verbose=True, collect_kwargs=True,
                                  cl_args='--b=1 --c=2 --x=0 --w=2 --y=1 --k=hellothere --l 0.01 --m 0 --n 1')
    f_locals = wrapped(['a'], z=['z'])
    assert tuple(f_locals['a']) == ('a',)
    assert f_locals['b'] == '1'
    assert f_locals['c'] == '2'
    assert f_locals['x'] == 0
    assert f_locals['w'] == '2'
    assert f_locals['y'] == 1
    assert tuple(f_locals['z']) == ('z',)  # No cast performed because passed in programmatically
    assert f_locals['kwargs']['k'] == 'hellothere'
    assert f_locals['kwargs']['l'] == '0.01'

    assert f_locals['m'] is False
    assert f_locals['n'] is True


class A(object):
    u = '10'
    v = '10'
    w = 10
    x = 0
    y = 'temp'
    z = 2

    p = True
    q = False

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
    wrapped = clify.wrap_object(
        a, cl_args='--x=2 --y 3 --a 100 --c 21 --p False --q True',
        verbose=True, collect_kwargs=True)
    result = wrapped.parse(v=10, w=10, b=100)
    pprint(result)

    assert a.u == A.u == '10'
    assert a.v == A.v == '10'
    assert a.w == A.w == 10
    assert a.x == A.x == 0
    assert a.y == A.y == 'temp'
    assert a.z == A.z == 2
    assert a.p == A.p == True  # noqa: E712
    assert a.q == A.q == False  # noqa: E712
    assert a.c == 20

    assert result['x'] == 2
    assert result['y'] == '3'
    assert result['a'] == '100'
    assert result['c'] == 21
    assert result['p'] == False  # noqa: E712
    assert result['q'] == True  # noqa: E712
    assert result['v'] == 10
    assert result['w'] == 10
    assert result['b'] == 100
    assert 'u' not in result


if __name__ == "__main__":
    test_wrap_function()
    test_wrap_object()
