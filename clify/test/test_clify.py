from pprint import pprint
import clify


def f(a, b, c, x=20, *p, w='1', y=1, z=0, **kwargs):
    pprint("Locals:")
    pprint(locals())
    return locals()


def test_clify():
    wrapped = clify.wrap(f, verbose=True, collect_kwargs=True,
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


if __name__ == "__main__":
    test_clify()
